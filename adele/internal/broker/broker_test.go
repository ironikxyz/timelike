package broker

import (
	"encoding/json"
	"os"
	"reflect"
	"testing"
	"time"

	"timelike/adele/internal/grants"
	"timelike/adele/internal/ledger"
	"timelike/adele/internal/standin"
)

// SC-5 at unit level: the 200 body, the stand-in's own record and the ledger row agree.
func TestPerformedWithinGrant(t *testing.T) {
	f := newFixture(t, demoGrant)
	out := f.handle(boxReq("web-1", "30m", 8080))
	if out.Status != 200 {
		t.Fatalf("status %d, body %v", out.Status, out.Body)
	}
	cost := standin.Price(30 * time.Minute)
	expires := fixedNow.Add(30 * time.Minute)
	want := map[string]any{"outcome": ledger.OutcomePerformed, "grant": "demo", "resource": "web-1",
		"cost_cents": cost, "expires_at": expires.Format(time.RFC3339)}
	for k, v := range want {
		if out.Body[k] != v {
			t.Errorf("body[%s] = %#v, want %#v", k, out.Body[k], v)
		}
	}
	var undo struct {
		Capability, Action string
		Params             map[string]string
	}
	if err := json.Unmarshal([]byte(out.Body["undo"].(string)), &undo); err != nil {
		t.Fatalf("undo is not JSON: %v", err)
	}
	if undo.Action != "delete" || undo.Params["name"] != "web-1" || undo.Capability != grants.CapStandinBox {
		t.Errorf("undo = %+v, want delete of web-1", undo)
	}

	box, ok := f.hasBox("web-1")
	if !ok {
		t.Fatalf("stand-in record has no web-1: %+v", f.store.List())
	}
	if !reflect.DeepEqual(box.Ports, []int{8080}) || box.TTLSeconds != 1800 || box.CostCents != cost ||
		!box.CreatedAt.Equal(fixedNow) {
		t.Errorf("box = %+v", box)
	}

	rows := f.rows(t)
	if len(rows) != 1 {
		t.Fatalf("ledger has %d rows, want 1", len(rows))
	}
	r := rows[0]
	if r.ID != out.Body["ledger_id"].(int64) || r.Outcome != ledger.OutcomePerformed || r.Grant != "demo" ||
		r.Session != "sess-1" || r.Resource != "web-1" || r.CostCents == nil || *r.CostCents != cost ||
		r.ExpiresAt == nil || !r.ExpiresAt.Equal(expires) || r.Undo != out.Body["undo"] {
		t.Errorf("ledger row = %+v", r)
	}
}

func TestDefaultTTLAndEmptyPorts(t *testing.T) {
	f := newFixture(t, demoGrant)
	out := f.mustPerform(t, boxReq("web-1", ""))
	if out.Body["cost_cents"] != standin.Price(time.Hour) ||
		out.Body["expires_at"] != fixedNow.Add(time.Hour).Format(time.RFC3339) {
		t.Errorf("body = %v, want the grant's 1h", out.Body)
	}
	box, _ := f.hasBox("web-1")
	if box.TTLSeconds != 3600 || box.Ports == nil || len(box.Ports) != 0 {
		t.Errorf("box = %+v, want ttl 3600 and ports []", box)
	}
	// The stand-in's file stores [] (never null) for no ports.
	data, err := os.ReadFile(f.storePath)
	if err != nil {
		t.Fatalf("read record: %v", err)
	}
	var stored []map[string]any
	if err := json.Unmarshal(data, &stored); err != nil || len(stored) != 1 {
		t.Fatalf("record %s: %v", data, err)
	}
	if p, ok := stored[0]["ports"].([]any); !ok || len(p) != 0 {
		t.Errorf("stored ports = %#v, want []", stored[0]["ports"])
	}
}
