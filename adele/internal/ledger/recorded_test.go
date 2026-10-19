package ledger

import (
	"testing"
	"time"
)

// Feature 13 slice 1: an exec and a session end are performed rows that made nothing that lives on. They are in the
// ledger, and no live count, instance limit, live list or due list sees them.
func TestARecordedRowIsNeverLive(t *testing.T) {
	l, _ := tempLedger(t)
	up := performed("g", 0)
	up.Capability, up.Action, up.Resource = "docker.compose", "up", "tl-a-1"
	if _, err := l.Performed(up); err != nil {
		t.Fatal(err)
	}
	if _, err := l.Recorded(Row{Grant: "g", Session: "s-1", Capability: "docker.compose", Action: "exec",
		Resource: "tl-a-1", Cause: "service web: [true] exit 0"}); err != nil {
		t.Fatal(err)
	}
	if _, err := l.Recorded(Row{Grant: NoGrant, Session: "s-1", Capability: CapabilitySession, Action: ActionEnd,
		Resource: "s-1"}); err != nil {
		t.Fatal(err)
	}
	if n, err := l.Live("g"); err != nil || n != 1 {
		t.Fatalf("Live = %d, %v; want 1 (the up only)", n, err)
	}
	if n, err := l.LiveOf("g", "docker.compose"); err != nil || n != 1 {
		t.Fatalf("LiveOf = %d, %v; want 1", n, err)
	}
	row, live, err := l.LiveResource("docker.compose", "tl-a-1")
	if err != nil || !live || row.Action != "up" {
		t.Fatalf("LiveResource = %+v %v %v; want the up row", row, live, err)
	}
	rows, err := l.LiveRows("docker.compose")
	if err != nil || len(rows) != 1 || rows[0].Action != "up" {
		t.Fatalf("LiveRows = %+v, %v; want the up row only", rows, err)
	}
	due, err := l.Due(time.Date(2030, 1, 1, 0, 0, 0, 0, time.UTC))
	if err != nil || len(due) != 1 || due[0].Row.Action != "up" {
		t.Fatalf("Due = %+v, %v; want the up row only", due, err)
	}
}

func TestRecordedNeedsItsFields(t *testing.T) {
	l, _ := tempLedger(t)
	if _, err := l.Recorded(Row{Session: "s", Capability: "docker.compose", Action: "exec", Resource: "x"}); err == nil {
		t.Fatal("a recorded row with no grant was written")
	}
}

func TestSessionEndedReadsTheFirstEnd(t *testing.T) {
	l, _ := tempLedger(t)
	if _, ended, err := l.SessionEnded("s-1"); err != nil || ended {
		t.Fatalf("SessionEnded before any end = %v, %v", ended, err)
	}
	at := time.Date(2026, 10, 18, 12, 0, 0, 0, time.UTC)
	id, err := l.Recorded(Row{At: at, Grant: NoGrant, Session: "s-1", Capability: CapabilitySession, Action: ActionEnd,
		Resource: "s-1"})
	if err != nil {
		t.Fatal(err)
	}
	if _, err := l.Recorded(Row{Grant: NoGrant, Session: "s-2", Capability: CapabilitySession, Action: ActionEnd,
		Resource: "s-2"}); err != nil {
		t.Fatal(err)
	}
	row, ended, err := l.SessionEnded("s-1")
	if err != nil || !ended || row.ID != id || !row.At.Equal(at) {
		t.Fatalf("SessionEnded = %+v %v %v; want row %d at %s", row, ended, err, id, at)
	}
}
