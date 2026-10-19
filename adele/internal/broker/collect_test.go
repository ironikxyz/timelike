package broker

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

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
