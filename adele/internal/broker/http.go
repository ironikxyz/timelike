package broker

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"time"

	"timelike/adele/internal/grants"
	"timelike/adele/internal/ledger"
)

// The denial window (spec FR-36, D-15): refusals in the last DenialWindow, at most DenialsPerHost per host.
const (
	DenialWindow   = 24 * time.Hour
	DenialsPerHost = 20
)

// MaxBodyBytes bounds a request body (contracts/adele-http.md).
const MaxBodyBytes = 64 << 10

// Handler serves Adele's request interface: /v1/health, /v1/grants, /v1/requests, and from slice 1 the
// read-only /v1/denials (spec FR-37). Nothing on it writes the ledger except a request's own row, and
// nothing on it reaps (FR-29).
func (b *Broker) Handler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("/v1/health", b.only(http.MethodGet, b.health))
	mux.HandleFunc("/v1/grants", b.only(http.MethodGet, b.grantsList))
	mux.HandleFunc("/v1/requests", b.only(http.MethodPost, b.requests))
	mux.HandleFunc("/v1/denials", b.only(http.MethodGet, b.denials))
	mux.HandleFunc("/", func(w http.ResponseWriter, _ *http.Request) {
		writeJSON(w, http.StatusNotFound, map[string]any{"error": "no such path"})
	})
	return mux
}

func (b *Broker) only(method string, h http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if r.Method != method {
			w.Header().Set("Allow", method)
			writeJSON(w, http.StatusMethodNotAllowed, map[string]any{"error": "use " + method})
			return
		}
		h(w, r)
	}
}

func (b *Broker) health(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, map[string]any{"service": "adele", "revision": b.Revision, "grants": b.Grants.Names()})
}

func (b *Broker) grantsList(w http.ResponseWriter, _ *http.Request) {
	b.mu.Lock()
	defer b.mu.Unlock()
	out := make([]map[string]any, 0, len(b.Grants.Grants))
	for _, base := range b.Grants.Grants {
		g, err := b.effective(base)
		if err != nil {
			writeJSON(w, http.StatusInternalServerError, map[string]any{"error": err.Error()})
			return
		}
		spent, err1 := b.Ledger.Spent(g.Name)
		live, err2 := b.Ledger.Live(g.Name)
		if err := errors.Join(err1, err2); err != nil {
			writeJSON(w, http.StatusInternalServerError, map[string]any{"error": "the ledger failed: " + err.Error()})
			return
		}
		out = append(out, map[string]any{
			"name": g.Name, "capabilities": g.Capabilities, "budget_cents": g.BudgetCents, "spent_cents": spent,
			"ttl": grants.FormatDuration(g.TTL), "instances": g.Instances, "live": live, "ports": g.Ports.String(),
		})
	}
	writeJSON(w, http.StatusOK, map[string]any{"grants": out})
}

func (b *Broker) denials(w http.ResponseWriter, r *http.Request) {
	host := r.URL.Query().Get("host")
	if len(host) > 255 {
		writeJSON(w, http.StatusBadRequest, map[string]any{"error": "host is longer than 255 bytes"})
		return
	}
	doc, err := Denials(b.Ledger, b.now(), host)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]any{"error": "the ledger failed: " + err.Error()})
		return
	}
	doc["revision"] = b.Revision
	writeJSON(w, http.StatusOK, doc)
}

// Denials is the recent-denial report both `status` commands print (spec FR-36): the window, and each
// refusal newest first with its host, policy, operator's command and ledger row. host "" means every host.
func Denials(led *ledger.Ledger, now time.Time, host string) (map[string]any, error) {
	rows, err := led.Denials(now.Add(-DenialWindow), host, DenialsPerHost)
	if err != nil {
		return nil, err
	}
	out := make([]map[string]any, 0, len(rows))
	for _, d := range rows {
		out = append(out, map[string]any{
			"ledger_id": d.ID, "at": d.At.UTC().Format(time.RFC3339), "host": d.Host, "grant": d.Grant,
			"limit":  map[string]string{"name": d.LimitName, "allowed": d.Allowed, "needed": d.Needed},
			"extend": d.Extend, "extend_by": "operator", "session": d.Session, "agent": d.Agent,
			"capability": d.Capability, "action": d.Action, "resource": d.Resource,
		})
	}
	return map[string]any{
		"window_hours": int(DenialWindow / time.Hour), "per_host": DenialsPerHost, "host": host,
		"since": now.Add(-DenialWindow).UTC().Format(time.RFC3339), "count": len(out), "denials": out,
	}, nil
}

func (b *Broker) requests(w http.ResponseWriter, r *http.Request) {
	var req Request
	dec := json.NewDecoder(http.MaxBytesReader(w, r.Body, MaxBodyBytes))
	dec.DisallowUnknownFields()
	if err := dec.Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]any{"error": "the request is not valid JSON: " + err.Error(),
			"remediation": "use the adele client: adele request …"})
		return
	}
	out := b.Handle(r.Context(), req)
	writeJSON(w, out.Status, out.Body)
}

func writeJSON(w http.ResponseWriter, status int, body any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(body)
}

// StandinClient performs the stand-in capability with Adele's canary (contracts/adele-http.md).
// The canary is sent only in the Authorization header and never logged or returned.
type StandinClient struct {
	BaseURL string
	Canary  string
	HTTP    *http.Client
}

// NewStandinClient bounds every upstream call at 10 s, well inside the agent's 30 s limit.
func NewStandinClient(base, canary string) *StandinClient {
	return &StandinClient{BaseURL: base, Canary: canary, HTTP: &http.Client{Timeout: 10 * time.Second}}
}

// Host is where the stand-in client reaches, host:port from its base URL (spec FR-35).
func (c *StandinClient) Host() string {
	u, err := url.Parse(c.BaseURL)
	if err != nil || u.Host == "" {
		return c.BaseURL
	}
	return u.Host
}

// ErrNoSuchResource is Delete's answer when the stand-in has no box of that name (HTTP 404).
var ErrNoSuchResource = errors.New("the stand-in has no box of that name")

// Box is the stand-in's own account of one box, as its record lists it.
type Box struct {
	Name       string    `json:"name"`
	CreatedAt  time.Time `json:"created_at"`
	TTLSeconds int64     `json:"ttl_seconds"`
}

// List reads the stand-in's own record (GET /v1/boxes). The reaper decides a reap's outcome from it,
// never from a delete's answer (cross-stack P004).
func (c *StandinClient) List(ctx context.Context) ([]Box, error) {
	var out []Box
	err := c.do(ctx, http.MethodGet, "/v1/boxes", nil, http.StatusOK, &out)
	return out, err
}

// Delete deletes the named box (DELETE /v1/boxes/NAME): the undo every performed row records (D-7).
func (c *StandinClient) Delete(ctx context.Context, name string) error {
	err := c.do(ctx, http.MethodDelete, "/v1/boxes/"+url.PathEscape(name), nil, http.StatusNoContent, nil)
	var st statusError
	if errors.As(err, &st) && st.code == http.StatusNotFound {
		return fmt.Errorf("%w: %s", ErrNoSuchResource, name)
	}
	return err
}

// Quote asks the stand-in what a box of this lifetime costs. It performs nothing.
func (c *StandinClient) Quote(ctx context.Context, ttl time.Duration) (int64, error) {
	var out struct {
		CostCents int64 `json:"cost_cents"`
	}
	err := c.call(ctx, "/v1/quote", map[string]any{"ttl_seconds": int64(ttl / time.Second)}, http.StatusOK, &out)
	return out.CostCents, err
}

// Create makes the box. Only this call performs anything.
func (c *StandinClient) Create(ctx context.Context, name string, ttl time.Duration, ports []int) (Created, error) {
	var out struct {
		Name      string    `json:"name"`
		CreatedAt time.Time `json:"created_at"`
		CostCents int64     `json:"cost_cents"`
	}
	body := map[string]any{"name": name, "ttl_seconds": int64(ttl / time.Second), "ports": ports}
	err := c.call(ctx, "/v1/boxes", body, http.StatusCreated, &out)
	return Created{Name: out.Name, CreatedAt: out.CreatedAt, CostCents: out.CostCents}, err
}

func (c *StandinClient) call(ctx context.Context, path string, body any, want int, out any) error {
	return c.do(ctx, http.MethodPost, path, body, want, out)
}

// statusError is an upstream answer with the wrong status: the code is kept so Delete can tell "no such
// box" from a failure.
type statusError struct {
	code int
	msg  string
}

func (e statusError) Error() string { return e.msg }

func (c *StandinClient) do(ctx context.Context, method, path string, body any, want int, out any) error {
	var rd io.Reader
	if body != nil {
		raw, _ := json.Marshal(body)
		rd = bytes.NewReader(raw)
	}
	req, err := http.NewRequestWithContext(ctx, method, c.BaseURL+path, rd)
	if err != nil {
		return fmt.Errorf("%w: %v", errUpstream, err)
	}
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	req.Header.Set("Authorization", "Bearer "+c.Canary)
	resp, err := c.HTTP.Do(req)
	if err != nil {
		return fmt.Errorf("%w: %v", errUpstream, redact(err.Error(), c.Canary))
	}
	defer resp.Body.Close()
	data, _ := io.ReadAll(io.LimitReader(resp.Body, MaxBodyBytes))
	if resp.StatusCode != want {
		var e struct {
			Error string `json:"error"`
		}
		_ = json.Unmarshal(data, &e)
		return fmt.Errorf("%w: %w", errUpstream, statusError{resp.StatusCode,
			fmt.Sprintf("%s answered %d: %s", path, resp.StatusCode, redact(e.Error, c.Canary))})
	}
	if out == nil {
		return nil
	}
	if err := json.Unmarshal(data, out); err != nil {
		return fmt.Errorf("%w: %s answered unreadable JSON", errUpstream, path)
	}
	return nil
}

// redact keeps the canary out of any error text that might reach the agent (FR-18).
func redact(s, canary string) string {
	if canary == "" {
		return s
	}
	return string(bytes.ReplaceAll([]byte(s), []byte(canary), []byte("[REDACTED:credential]")))
}
