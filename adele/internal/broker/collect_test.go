package broker

import (
	"bytes"
	"context"
	"encoding/json"
	"net"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"timelike/adele/internal/engine"
	"timelike/adele/internal/grants"
	"timelike/adele/internal/ledger"
)

func TestASessionEndsOnceAndTheSecondEndSaysSo(t *testing.T) {
	f := newFixture(t, envGrants)
	first := f.b.EndSession("s1", "a1")
	if first.Status != http.StatusOK || first.Body["outcome"] != "ended" {
		t.Fatalf("first: %d %v", first.Status, first.Body)
	}
	second := f.b.EndSession("s1", "")
	if second.Status != http.StatusOK || second.Body["outcome"] != "already ended" ||
		second.Body["ledger_id"] != first.Body["ledger_id"] || second.Body["ended_at"] != first.Body["ended_at"] {
		t.Fatalf("second: %d %v (first %v)", second.Status, second.Body, first.Body)
	}
	rows := f.rows(t)
	if len(rows) != 1 || rows[0].Capability != ledger.CapabilitySession || rows[0].Action != ledger.ActionEnd ||
		rows[0].Resource != "s1" || rows[0].Grant != ledger.NoGrant || rows[0].Agent != "a1" || rows[0].ExpiresAt != nil {
		t.Fatalf("rows %+v", rows)
	}
}

func TestSessionEndAndCollectAreRoutedAndValidated(t *testing.T) {
	f := newFixture(t, envGrants)
	h := f.b.Handler()
	post := func(path, body string) *httptest.ResponseRecorder {
		w := httptest.NewRecorder()
		h.ServeHTTP(w, httptest.NewRequest(http.MethodPost, path, bytes.NewBufferString(body)))
		return w
	}
	if w := post("/v1/sessions/end", `{"session": "bad session"}`); w.Code != http.StatusBadRequest {
		t.Errorf("a bad session: %d", w.Code)
	}
	if w := post("/v1/sessions/end", `{"session": "s1", "grant": "x"}`); w.Code != http.StatusBadRequest {
		t.Errorf("an unknown field: %d", w.Code)
	}
	w := post("/v1/sessions/end", `{"session": "s1"}`)
	var out map[string]any
	if w.Code != http.StatusOK || json.Unmarshal(w.Body.Bytes(), &out) != nil || out["outcome"] != "ended" {
		t.Errorf("session end: %d %s", w.Code, w.Body.String())
	}
	if w := post("/v1/envs/collect", `{"session": "s1"}`); w.Code != http.StatusServiceUnavailable {
		t.Errorf("collect with no daemon: %d %s", w.Code, w.Body.String())
	}
	g := httptest.NewRecorder()
	h.ServeHTTP(g, httptest.NewRequest(http.MethodGet, "/v1/envs/collect", nil))
	if g.Code != http.StatusMethodNotAllowed {
		t.Errorf("GET collect: %d", g.Code)
	}
}

// With no live environment a pass asks the daemon nothing and collects nothing: "0 collected".
func TestAPassWithNothingLiveCollectsNothing(t *testing.T) {
	f := envFixture(t, "/w")
	collected, failed, err := f.b.Collect(context.Background())
	if err != nil || len(collected) != 0 || len(failed) != 0 {
		t.Fatalf("Collect = %v %v %v", collected, failed, err)
	}
}

// collectDaemon answers what a collection pass asks: the agents (none), each environment's containers, and their
// stop and removal, which take removeDelay each. Networks, volumes and images are none. onRemove runs as a container
// is removed: another reaper acting meanwhile (lane 13s2a).
type collectDaemon struct {
	mu          sync.Mutex
	cs          map[string]string // container id → environment
	removed     map[string]int    // container id → removals
	removeDelay time.Duration
	onRemove    func(env string)
}

func (d *collectDaemon) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	write := func(v any) {
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(v)
	}
	var filters struct {
		Label []string `json:"label"`
	}
	_ = json.Unmarshal([]byte(r.URL.Query().Get("filters")), &filters)
	parts := strings.Split(strings.Trim(r.URL.Path, "/"), "/")
	switch {
	case r.Method == http.MethodGet && r.URL.Path == "/containers/json":
		d.mu.Lock()
		out := []map[string]any{}
		for id, env := range d.cs {
			l := map[string]string{engine.LabelEnv: env, engine.LabelRequester: "unknown"}
			if len(filters.Label) == 1 && filters.Label[0] == engine.LabelEnv+"="+env {
				out = append(out, map[string]any{"Id": id, "Labels": l, "State": "exited"})
			}
		}
		d.mu.Unlock()
		write(out)
	case r.Method == http.MethodGet && len(parts) == 3 && parts[0] == "containers" && parts[2] == "json":
		write(map[string]any{"State": map[string]any{"Status": "exited"}})
	case r.Method == http.MethodGet && (r.URL.Path == "/networks" || r.URL.Path == "/images/json"):
		write([]any{})
	case r.Method == http.MethodGet && r.URL.Path == "/volumes":
		write(map[string]any{"Volumes": []any{}})
	case r.Method == http.MethodDelete && len(parts) == 2 && parts[0] == "containers":
		time.Sleep(d.removeDelay)
		d.mu.Lock()
		env, ok := d.cs[parts[1]]
		delete(d.cs, parts[1])
		d.removed[parts[1]]++
		hook := d.onRemove
		d.mu.Unlock()
		if ok && hook != nil {
			hook(env)
		}
		w.WriteHeader(http.StatusNoContent)
	default:
		w.WriteHeader(http.StatusTeapot)
	}
}

// collectFixture is a broker with live environments envs, one container each, in session s1, which has ended.
func collectFixture(t *testing.T, delay time.Duration, envs ...string) (*fixture, *collectDaemon, map[string]int64) {
	t.Helper()
	f := newFixture(t, envGrants)
	d := &collectDaemon{cs: map[string]string{}, removed: map[string]int{}, removeDelay: delay}
	dir, err := os.MkdirTemp("", "collect")
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { os.RemoveAll(dir) })
	ln, err := net.Listen("unix", filepath.Join(dir, "d.sock"))
	if err != nil {
		t.Fatal(err)
	}
	srv := &http.Server{Handler: d}
	go srv.Serve(ln) //nolint:errcheck // ends with Close
	t.Cleanup(func() { srv.Close() })
	f.b.Envs = &Envs{Engine: engine.New(filepath.Join(dir, "d.sock")), Workspace: "/w"}
	rows := map[string]int64{}
	expires, zero := fixedNow.Add(time.Hour), int64(0)
	for _, env := range envs {
		d.cs["c-"+env] = env
		id, err := f.led.Performed(ledger.Row{At: fixedNow, Grant: "env", Session: "s1", Capability: grants.CapDockerCompose,
			Action: "up", Resource: env, CostCents: &zero, ExpiresAt: &expires, Undo: `{}`})
		if err != nil {
			t.Fatal(err)
		}
		rows[env] = id
	}
	if out := f.b.EndSession("s1", ""); out.Status != http.StatusOK {
		t.Fatalf("session end: %v", out.Body)
	}
	return f, d, rows
}

func reapedRows(t *testing.T, f *fixture) []ledger.Row {
	var out []ledger.Row
	for _, r := range f.rows(t) {
		if r.Outcome == ledger.OutcomeReaped {
			out = append(out, r)
		}
	}
	return out
}

// Lane 13s2a, defect B: a collect whose removals outlast the server's write timeout is still answered. The server
// here times writes out at 200 ms, standing in for serve.go's 30 s; the two removals take 300 ms each.
func TestACollectIsAnsweredPastTheServersWriteTimeout(t *testing.T) {
	f, _, _ := collectFixture(t, 300*time.Millisecond, "tl-a", "tl-b")
	srv := httptest.NewUnstartedServer(f.b.Handler())
	srv.Config.WriteTimeout = 200 * time.Millisecond
	srv.Start()
	defer srv.Close()
	start := time.Now()
	resp, err := http.Post(srv.URL+"/v1/envs/collect", "application/json", strings.NewReader(`{"session": "s1"}`))
	if err != nil {
		t.Fatalf("no answer after %s: %v", time.Since(start), err)
	}
	defer resp.Body.Close()
	var out struct {
		Count     int         `json:"count"`
		Collected []Collected `json:"collected"`
	}
	if resp.StatusCode != http.StatusOK || json.NewDecoder(resp.Body).Decode(&out) != nil || out.Count != 2 {
		t.Fatalf("collect: %d %+v", resp.StatusCode, out)
	}
	if took := time.Since(start); took < 600*time.Millisecond {
		t.Fatalf("answered in %s: the pass did not outlast the write timeout, so this proves nothing", took)
	}
	for _, c := range out.Collected {
		if c.LedgerID == 0 || c.Already {
			t.Errorf("%+v: not this pass's own row", c)
		}
	}
	if got := len(reapedRows(t, f)); got != 2 {
		t.Fatalf("%d reaped rows, want 2", got)
	}
}

// Lane 13s2a, defect B: the agent's collect and the reaper's tick at once remove and record each environment once,
// and neither reports a row it did not write (her log said "recorded as #0" three times).
func TestTwoPassesAtOnceRemoveAndRecordEachEnvironmentOnce(t *testing.T) {
	f, d, rows := collectFixture(t, 50*time.Millisecond, "tl-a", "tl-b")
	var wg sync.WaitGroup
	results := make([][]Collected, 2)
	for i := range results {
		wg.Add(1)
		go func() {
			defer wg.Done()
			collected, failed, err := f.b.Collect(context.Background())
			if err != nil || len(failed) != 0 {
				t.Errorf("pass %d: %v %v", i, failed, err)
			}
			results[i] = collected
		}()
	}
	wg.Wait()
	seen := map[string]int64{}
	for _, cs := range results {
		for _, c := range cs {
			if _, twice := seen[c.Name]; twice {
				t.Errorf("%s collected by both passes", c.Name)
			}
			seen[c.Name] = c.LedgerID
		}
	}
	reaped := reapedRows(t, f)
	if len(seen) != 2 || len(reaped) != 2 {
		t.Fatalf("collected %v; reaped rows %+v", seen, reaped)
	}
	for _, r := range reaped {
		if seen[r.Resource] != r.ID || r.Ref == nil || *r.Ref != rows[r.Resource] {
			t.Errorf("reaped row %+v; the pass reported #%d", r, seen[r.Resource])
		}
	}
	d.mu.Lock()
	defer d.mu.Unlock()
	for id, n := range d.removed {
		if n != 1 {
			t.Errorf("%s removed %d times", id, n)
		}
	}
}

// Lane 13s2a, defect B: when another reaper ends the row while this pass removes it, the pass reports that reaper's
// row and cause, never #0.
func TestAPassThatAnotherReaperBeatReportsThatReapersRow(t *testing.T) {
	f, d, rows := collectFixture(t, 0, "tl-a")
	var winner atomic.Int64
	d.onRemove = func(env string) {
		id, wrote, err := f.led.Reap(rows[env], ledger.OutcomeReaped, "ttl reached (the reaper)", 1, fixedNow)
		if err != nil || !wrote {
			t.Errorf("the other reaper: %v %v", wrote, err)
		}
		winner.Store(id)
	}
	collected, failed, err := f.b.Collect(context.Background())
	if err != nil || len(failed) != 0 || len(collected) != 1 {
		t.Fatalf("Collect = %+v %+v %v", collected, failed, err)
	}
	c := collected[0]
	if !c.Already || c.LedgerID == 0 || c.LedgerID != winner.Load() || c.Cause != "ttl reached (the reaper)" {
		t.Fatalf("%+v, want the other reaper's #%d", c, winner.Load())
	}
	if got := len(reapedRows(t, f)); got != 1 {
		t.Fatalf("%d reaped rows, want 1", got)
	}
}
