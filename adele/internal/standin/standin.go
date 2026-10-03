// Package standin is the stand-in capability: a test-and-demo-only fake that
// "creates" named boxes, prices them, and keeps its own record of them. It
// provisions nothing and is never a real provider (FR-19). It refuses every
// request that does not carry the canary credential (FR-20).
package standin

import (
	"crypto/subtle"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"regexp"
	"strings"
	"time"
)

const (
	// RateCentsPerHour is the stand-in's fixed price (FR-21).
	RateCentsPerHour = 25
	// MinTTLSeconds and MaxTTLSeconds bound a box's lifetime (1 minute to 30 days).
	MinTTLSeconds = 60
	MaxTTLSeconds = 2592000
	// MaxBodyBytes bounds every request body.
	MaxBodyBytes = 64 << 10

	maxCanaryFileBytes = 4 << 10
)

var (
	nameRe   = regexp.MustCompile(`^[a-z][a-z0-9-]{0,62}$`)
	canaryRe = regexp.MustCompile(`^tlcanary-[0-9a-f]{32}$`)
)

// Price is the cost in cents of a box living ttl: 25 cents per hour, pro rata
// per started minute, rounded up.
func Price(ttl time.Duration) int64 {
	if ttl <= 0 {
		return 0
	}
	minutes := int64((ttl + time.Minute - 1) / time.Minute)
	return (minutes*RateCentsPerHour + 59) / 60
}

// ReadCanary reads the canary credential from path. It refuses an empty file
// or one that is not `tlcanary-` and 32 lowercase hex characters. Its errors
// never contain the file's content.
func ReadCanary(path string) (string, error) {
	f, err := os.Open(path)
	if err != nil {
		return "", fmt.Errorf("standin: open canary file %s: %w", path, err)
	}
	defer f.Close()
	data, err := io.ReadAll(io.LimitReader(f, maxCanaryFileBytes+1))
	if err != nil {
		return "", fmt.Errorf("standin: read canary file %s: %w", path, err)
	}
	c := strings.TrimSpace(string(data))
	if c == "" {
		return "", fmt.Errorf("standin: canary file %s is empty", path)
	}
	if len(data) > maxCanaryFileBytes || !canaryRe.MatchString(c) {
		return "", fmt.Errorf("standin: canary file %s is not tlcanary- and 32 lowercase hex characters", path)
	}
	return c, nil
}

type server struct {
	canary []byte
	store  *Store
	now    func() time.Time
}

// Handler serves the stand-in's HTTP interface (contract adele-http.md § The
// stand-in). Every request must carry `Authorization: Bearer <canary>`; an
// empty canary refuses every request rather than run open. A nil now uses
// time.Now.
func Handler(canary string, store *Store, now func() time.Time) http.Handler {
	if now == nil {
		now = time.Now
	}
	return &server{canary: []byte(canary), store: store, now: now}
}

func (s *server) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if !s.authorized(r) {
		writeError(w, http.StatusUnauthorized, "missing or wrong credential")
		return
	}
	r.Body = http.MaxBytesReader(w, r.Body, MaxBodyBytes)
	switch {
	case r.URL.Path == "/v1/quote":
		s.route(w, r, map[string]http.HandlerFunc{http.MethodPost: s.quote})
	case r.URL.Path == "/v1/boxes":
		s.route(w, r, map[string]http.HandlerFunc{http.MethodPost: s.create, http.MethodGet: s.list})
	case strings.HasPrefix(r.URL.Path, "/v1/boxes/"):
		s.route(w, r, map[string]http.HandlerFunc{http.MethodDelete: s.delete})
	default:
		writeError(w, http.StatusNotFound, "no such path")
	}
}

// authorized compares the bearer token to the canary in constant time. The
// header's value is never logged or echoed.
func (s *server) authorized(r *http.Request) bool {
	if len(s.canary) == 0 {
		return false
	}
	token, ok := strings.CutPrefix(r.Header.Get("Authorization"), "Bearer ")
	if !ok {
		return false
	}
	return subtle.ConstantTimeCompare([]byte(token), s.canary) == 1
}

func (s *server) route(w http.ResponseWriter, r *http.Request, methods map[string]http.HandlerFunc) {
	if h, ok := methods[r.Method]; ok {
		h(w, r)
		return
	}
	allow := make([]string, 0, len(methods))
	for _, m := range []string{http.MethodGet, http.MethodPost, http.MethodDelete} {
		if _, ok := methods[m]; ok {
			allow = append(allow, m)
		}
	}
	w.Header().Set("Allow", strings.Join(allow, ", "))
	writeError(w, http.StatusMethodNotAllowed, "method not allowed")
}

func (s *server) quote(w http.ResponseWriter, r *http.Request) {
	var req struct {
		TTLSeconds int64 `json:"ttl_seconds"`
	}
	if !decode(w, r, &req) {
		return
	}
	if msg := checkTTL(req.TTLSeconds); msg != "" {
		writeError(w, http.StatusBadRequest, msg)
		return
	}
	writeJSON(w, http.StatusOK, map[string]int64{"cost_cents": priceSeconds(req.TTLSeconds)})
}

func (s *server) create(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Name       string `json:"name"`
		TTLSeconds int64  `json:"ttl_seconds"`
		Ports      []int  `json:"ports"`
	}
	if !decode(w, r, &req) {
		return
	}
	if msg := checkBox(req.Name, req.TTLSeconds, req.Ports); msg != "" {
		writeError(w, http.StatusBadRequest, msg)
		return
	}
	b := Box{
		Name:       req.Name,
		CreatedAt:  s.now().UTC(),
		TTLSeconds: req.TTLSeconds,
		Ports:      req.Ports,
		CostCents:  priceSeconds(req.TTLSeconds),
	}
	switch err := s.store.Create(b); {
	case errors.Is(err, ErrExists):
		writeError(w, http.StatusConflict, "a box named "+b.Name+" exists")
	case err != nil:
		writeError(w, http.StatusInternalServerError, "the record could not be written")
	default:
		writeJSON(w, http.StatusCreated, struct {
			Name      string    `json:"name"`
			CreatedAt time.Time `json:"created_at"`
			CostCents int64     `json:"cost_cents"`
		}{b.Name, b.CreatedAt, b.CostCents})
	}
}

func (s *server) delete(w http.ResponseWriter, r *http.Request) {
	name := strings.TrimPrefix(r.URL.Path, "/v1/boxes/")
	if !nameRe.MatchString(name) {
		writeError(w, http.StatusBadRequest, "name must match ^[a-z][a-z0-9-]{0,62}$")
		return
	}
	switch err := s.store.Delete(name); {
	case errors.Is(err, ErrNotFound):
		writeError(w, http.StatusNotFound, "no box named "+name)
	case err != nil:
		writeError(w, http.StatusInternalServerError, "the record could not be written")
	default:
		w.WriteHeader(http.StatusNoContent)
	}
}

func (s *server) list(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, s.store.List())
}

func priceSeconds(ttl int64) int64 { return Price(time.Duration(ttl) * time.Second) }

func checkTTL(ttl int64) string {
	if ttl < MinTTLSeconds || ttl > MaxTTLSeconds {
		return fmt.Sprintf("ttl_seconds must be %d..%d", MinTTLSeconds, MaxTTLSeconds)
	}
	return ""
}

func checkBox(name string, ttl int64, ports []int) string {
	if !nameRe.MatchString(name) {
		return "name must match ^[a-z][a-z0-9-]{0,62}$"
	}
	if msg := checkTTL(ttl); msg != "" {
		return msg
	}
	for _, p := range ports {
		if p < 1 || p > 65535 {
			return fmt.Sprintf("port %d is not 1..65535", p)
		}
	}
	return ""
}

// decode reads exactly one JSON object with no unknown fields, answering 400
// (or 413 past the body limit) itself when it cannot.
func decode(w http.ResponseWriter, r *http.Request, v any) bool {
	dec := json.NewDecoder(r.Body)
	dec.DisallowUnknownFields()
	err := dec.Decode(v)
	if err == nil && dec.More() {
		err = errors.New("trailing data after the JSON object")
	}
	if err == nil {
		return true
	}
	var tooBig *http.MaxBytesError
	if errors.As(err, &tooBig) {
		writeError(w, http.StatusRequestEntityTooLarge, fmt.Sprintf("body exceeds %d bytes", MaxBodyBytes))
		return false
	}
	writeError(w, http.StatusBadRequest, "body is not the expected JSON object: "+err.Error())
	return false
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

func writeError(w http.ResponseWriter, status int, msg string) {
	writeJSON(w, status, map[string]string{"error": msg})
}
