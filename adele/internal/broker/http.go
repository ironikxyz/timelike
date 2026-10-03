package broker

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"time"

	"timelike/adele/internal/grants"
)

// MaxBodyBytes bounds a request body (contracts/adele-http.md).
const MaxBodyBytes = 64 << 10

// Handler serves Adele's request interface: /v1/health, /v1/grants, /v1/requests.
func (b *Broker) Handler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("/v1/health", b.only(http.MethodGet, b.health))
	mux.HandleFunc("/v1/grants", b.only(http.MethodGet, b.grantsList))
	mux.HandleFunc("/v1/requests", b.only(http.MethodPost, b.requests))
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
	raw, _ := json.Marshal(body)
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.BaseURL+path, bytes.NewReader(raw))
	if err != nil {
		return fmt.Errorf("%w: %v", errUpstream, err)
	}
	req.Header.Set("Content-Type", "application/json")
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
		return fmt.Errorf("%w: %s answered %d: %s", errUpstream, path, resp.StatusCode, redact(e.Error, c.Canary))
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
