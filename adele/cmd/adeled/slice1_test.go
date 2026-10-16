package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"timelike/adele/internal/ledger"
	"timelike/adele/internal/standin"
)

// standinFor serves the real stand-in handler for f and points ADELE_STANDIN_URL at it.
func standinFor(t *testing.T, f *fixture) (*standin.Store, *standin.Faults) {
	t.Helper()
	store, err := standin.NewStore(filepath.Join(f.dir, "boxes.json"))
	if err != nil {
		t.Fatal(err)
	}
	faults := standin.NewFaults(filepath.Join(f.dir, "faults.json"))
	srv := httptest.NewServer(standin.HandlerWithFaults(testCanary, store, nil, faults))
	t.Cleanup(srv.Close)
	f.vars["ADELE_STANDIN_URL"] = srv.URL
	return store, faults
}

// expiredBox puts a box in the stand-in's record and its performed row in the ledger, expired.
func expiredBox(t *testing.T, f *fixture, store *standin.Store, name, agent string) int64 {
	t.Helper()
	created := time.Now().UTC().Add(-2 * time.Minute).Truncate(time.Second)
	if err := store.Create(standin.Box{Name: name, CreatedAt: created, TTLSeconds: 60, Ports: []int{}}); err != nil {
		t.Fatal(err)
	}
	led := openLedger(t, f)
	defer led.Close()
	exp := created.Add(time.Minute)
	cost := int64(1)
	id, err := led.Performed(ledger.Row{At: created, Grant: "demo", Session: "sess-1", Agent: agent,
		Capability: "standin.box", Action: "create", Resource: name, CostCents: &cost, ExpiresAt: &exp,
		Undo: `{"capability":"standin.box","action":"delete","params":{"name":"` + name + `"}}`})
	if err != nil {
		t.Fatal(err)
	}
	return id
}

func TestReapCommandReapsNowAndPrintsEachOutcome(t *testing.T) {
	f := newFixture(t)
	withRevision(t, "rev-1")
	store, faults := standinFor(t, f)
	expiredBox(t, f, store, "box-a", "agent-a")
	expiredBox(t, f, store, "box-b", "")
	_ = faults.Set("box-b", standin.FaultError)

	code, out, errs := f.run("reap")
	if code != exitFailure || !strings.Contains(out, "reaped box-a (ledger #1, grant demo, session sess-1, agent agent-a)") ||
		!strings.Contains(out, "reap-failed box-b") || !strings.Contains(out, "2 reaped or recorded (reaped 1, gone 0, failed 1)") {
		t.Fatalf("reap: %d %q %q", code, out, errs)
	}
	_ = faults.Set("box-b", standin.FaultClear)
	code, out, errs = f.run("reap", "--json")
	var res []map[string]any
	if code != exitOK || json.Unmarshal([]byte(out), &res) != nil || len(res) != 1 || res[0]["outcome"] != "reaped" ||
		res[0]["resource"] != "box-b" {
		t.Fatalf("reap --json: %d %q %q", code, out, errs)
	}
	code, out, _ = f.run("reap", "--json")
	if code != exitOK || strings.TrimSpace(out) != "[]" {
		t.Fatalf("nothing due: %d %q", code, out)
	}
	if len(store.List()) != 0 {
		t.Fatalf("boxes left: %+v", store.List())
	}
	code, out, _ = f.run("ledger")
	if code != exitOK || !strings.Contains(out, "reaped grant=demo session=sess-1 agent=agent-a standin.box.delete resource=box-a of=#1 attempts=1") ||
		!strings.Contains(out, "reap-failed grant=demo session=sess-1 standin.box.delete resource=box-b of=#2 attempts=3") {
		t.Fatalf("ledger: %q", out)
	}
	code, out, _ = f.run("ledger", "--json")
	var rows []map[string]any
	if code != exitOK || json.Unmarshal([]byte(out), &rows) != nil || rows[2]["ref"] != 1.0 || rows[2]["agent"] != "agent-a" ||
		rows[2]["attempts"] != 1.0 || !strings.Contains(rows[2]["cause"].(string), "read back") || rows[0]["host"] != nil {
		t.Fatalf("ledger --json: %q", out)
	}
}

func TestReapCommandRefusesBadSettings(t *testing.T) {
	f := newFixture(t)
	withRevision(t, "rev-1")
	for _, kv := range [][2]string{{"ADELE_REAP_INTERVAL", "soon"}, {"ADELE_REAP_INTERVAL", "1ms"}, {"ADELE_REAP_PASSES", "0"}} {
		f.vars[kv[0]] = kv[1]
		if code, _, errs := f.run("reap"); code != exitUsage || !strings.Contains(errs, kv[0]) {
			t.Errorf("%s=%s: %d %q", kv[0], kv[1], code, errs)
		}
		delete(f.vars, kv[0])
	}
	if code, _, _ := f.run("reap", "extra"); code != exitUsage {
		t.Error("reap with an argument")
	}
	withRevision(t, "")
	if code, _, _ := f.run("reap"); code != exitFailure { // unstamped: setup refuses, as serve does
		t.Error("unstamped reap")
	}
}

func TestStatusCommandExplainsDenialsByHost(t *testing.T) {
	f := newFixture(t)
	withRevision(t, "rev-2")
	led := openLedger(t, f)
	now := time.Now().UTC()
	for i, host := range []string{"adele-standin:8481", "adele-standin:8481", "other.invalid:443"} {
		if _, err := led.Refused(ledger.Row{At: now.Add(time.Duration(i-5) * time.Minute), Grant: "demo",
			Session: "sess-9", Agent: "agent-z", Capability: "standin.box", Action: "create", Resource: "box",
			LimitName: "ports", Allowed: "8080", Needed: "22", Host: host,
			Extend: "docker exec timelike-adele adeled extend demo ports 22"}); err != nil {
			t.Fatal(err)
		}
	}
	led.Close()

	code, out, errs := f.run("status")
	lines := strings.Split(strings.TrimSpace(out), "\n")
	if code != exitOK || errs != "" || len(lines) != 4 ||
		lines[0] != "Adele revision rev-2 · reaper: 0 due, 0 given up · 3 denials in the last 24 h (newest first, at most 20 per host) · the record: adeled ledger" ||
		!strings.HasPrefix(lines[1], "#3 ") || !strings.Contains(lines[1], "other.invalid:443: grant demo, ports allows 8080, needed 22 — the operator allows it: docker exec timelike-adele adeled extend demo ports 22 (session sess-9, agent agent-z)") {
		t.Fatalf("status: %d %q %q", code, out, errs)
	}
	code, out, _ = f.run("status", "adele-standin:8481")
	if code != exitOK || !strings.HasPrefix(out, "Adele revision rev-2 · reaper: 0 due, 0 given up · 2 denials of adele-standin:8481 in the last 24 h") {
		t.Fatalf("status HOST: %q", out)
	}
	code, out, _ = f.run("status", "nobody.invalid:1")
	if code != exitOK || strings.TrimSpace(out) != "Adele revision rev-2 · reaper: 0 due, 0 given up · no denial of nobody.invalid:1 in the last 24 h · the record: adeled ledger" {
		t.Fatalf("status, no denial: %q", out)
	}
	code, out, _ = f.run("status", "--json")
	var doc map[string]any
	if code != exitOK || json.Unmarshal([]byte(out), &doc) != nil || doc["revision"] != "rev-2" ||
		doc["denials"].(map[string]any)["count"] != 3.0 || doc["reaper"].(map[string]any)["due"] != 0.0 {
		t.Fatalf("status --json: %q", out)
	}
	if code, _, errs := f.run("status", "a", "b"); code != exitUsage || !strings.Contains(errs, "usage: adeled status") {
		t.Fatalf("two hosts: %d %q", code, errs)
	}
}

func TestStatusCommandNamesGivenUpReapsAndTheRetry(t *testing.T) {
	f := newFixture(t)
	withRevision(t, "")
	store, faults := standinFor(t, f)
	expiredBox(t, f, store, "box-a", "")
	_ = faults.Set("box-a", standin.FaultError)
	f.vars["ADELE_REAP_PASSES"] = "1"
	withRevision(t, "rev-3")
	if code, _, _ := f.run("reap"); code != exitFailure {
		t.Fatal("faulted reap")
	}
	code, out, _ := f.run("status")
	if code != exitOK || !strings.Contains(out, "Adele revision rev-3 · reaper: 1 due, 1 given up · no denial in the last 24 h") ||
		!strings.Contains(out, "given up: #1 box-a (grant demo) after 1 failed passes — retry: docker exec timelike-adele adeled reap") {
		t.Fatalf("status: %q", out)
	}
	withRevision(t, "")
	if _, out, _ := f.run("status"); !strings.HasPrefix(out, "Adele revision unstamped") {
		t.Fatalf("unstamped status: %q", out)
	}
	f.vars["ADELE_DB"] = filepath.Join(f.dir, "no", "such", "adele.db")
	if code, _, _ := f.run("status"); code != exitFailure {
		t.Fatal("status over an unopenable ledger")
	}
}

func TestServeReapsAtStartAndOnTheInterval(t *testing.T) {
	f := newFixture(t)
	withRevision(t, "rev-4")
	store, _ := standinFor(t, f)
	expiredBox(t, f, store, "box-a", "agent-a") // expired while Adele was down: reaped at start
	f.vars["ADELE_REAP_INTERVAL"] = "100ms"
	var stderr syncBuffer
	code := serveUntilSignalled(t, func(ready chan<- string) int {
		return serve(f.env(), &stderr, ready)
	}, func(addr string) error {
		deadline := time.Now().Add(20 * time.Second)
		for len(store.List()) != 0 && time.Now().Before(deadline) {
			time.Sleep(20 * time.Millisecond)
		}
		// A request answered proves serve's signal handler is registered (serveUntilSignalled's rule).
		resp, err := http.Get("http://" + addr + "/v1/health")
		if err == nil {
			resp.Body.Close()
		}
		return err
	})
	if code != exitOK || len(store.List()) != 0 || !strings.Contains(stderr.String(), "reaping every 100ms") ||
		!strings.Contains(stderr.String(), "adeled: reap: reaped box-a") {
		t.Fatalf("serve: %d boxes=%v stderr=%q", code, store.List(), stderr.String())
	}
	f.vars["ADELE_REAP_INTERVAL"] = "never"
	if code, _, errs := f.run("serve"); code != exitUsage || !strings.Contains(errs, "ADELE_REAP_INTERVAL") {
		t.Fatalf("bad interval: %d %q", code, errs)
	}
}

func TestUsageSaysWhoRunsExtendAndWhereTheRecordIs(t *testing.T) { // FR-40, Item 14 (a)
	f := newFixture(t)
	code, out, _ := f.run("--help")
	for _, want := range []string{"extend, reap, ledger and status are the OPERATOR's", "docker exec timelike-adele adeled <command>",
		"The agent cannot run them", "Adele's ledger (adeled ledger)", "adeled reap", "adeled status [HOST]"} {
		if code != exitOK || !strings.Contains(out, want) {
			t.Errorf("usage lacks %q", want)
		}
	}
}
