package ledger

import (
	"errors"
	"testing"
	"time"
)

// Feature 13 slice 2: snapshots and holds are performed rows with an undo and no expiry. They are never live, a
// hold is open until a row refers to it, and a snapshot is listed until its removal is recorded.
func TestSnapshotsAndHoldsAreNeverLive(t *testing.T) {
	l, _ := tempLedger(t)
	up := performed("g", 0)
	up.Capability, up.Action, up.Resource = "docker.compose", "up", "tl-a-1"
	if _, err := l.Performed(up); err != nil {
		t.Fatal(err)
	}
	snap := Row{Grant: "g", Session: "s-1", Capability: "docker.compose", Action: ActionSnapshot,
		Resource: "tl-a-1/s-00000001", Undo: `{"action":"snapshot-rm"}`, Cause: "snapshot s-00000001"}
	sid, err := l.Kept(snap)
	if err != nil {
		t.Fatal(err)
	}
	pause := Row{Grant: "g", Session: "s-1", Capability: "docker.compose", Action: ActionPause, Resource: "tl-a-1",
		Undo: `{"action":"unpause","containers":["c1"]}`}
	pid, err := l.Kept(pause)
	if err != nil {
		t.Fatal(err)
	}
	if n, err := l.Live("g"); err != nil || n != 1 {
		t.Fatalf("Live = %d, %v; want 1 (the up only)", n, err)
	}
	if rows, err := l.LiveRows("docker.compose"); err != nil || len(rows) != 1 {
		t.Fatalf("LiveRows = %+v, %v; want the up only", rows, err)
	}
	holds, err := l.OpenHolds("docker.compose")
	if err != nil || len(holds) != 1 || holds[0].ID != pid {
		t.Fatalf("OpenHolds = %+v, %v; want the pause", holds, err)
	}
	if _, wrote, err := l.Ended(pid, ActionUnpause, "unpaused, read back running", time.Time{}); err != nil || !wrote {
		t.Fatalf("Ended = %v, %v", wrote, err)
	}
	if _, wrote, err := l.Ended(pid, ActionUnpause, "again", time.Time{}); err != nil || wrote {
		t.Fatalf("a second Ended wrote %v, %v; want no row", wrote, err)
	}
	if holds, err := l.OpenHolds("docker.compose"); err != nil || len(holds) != 0 {
		t.Fatalf("OpenHolds after the ending = %+v, %v", holds, err)
	}

	snaps, err := l.Snapshots("docker.compose", "tl-a-1")
	if err != nil || len(snaps) != 1 || snaps[0].ID != sid {
		t.Fatalf("Snapshots = %+v, %v", snaps, err)
	}
	// Another environment whose name has this one's as a prefix is not this one's.
	if _, err := l.Kept(Row{Grant: "g", Session: "s-1", Capability: "docker.compose", Action: ActionSnapshot,
		Resource: "tl-a-10/s-00000002", Undo: `{}`}); err != nil {
		t.Fatal(err)
	}
	if snaps, _ := l.Snapshots("docker.compose", "tl-a-1"); len(snaps) != 1 {
		t.Fatalf("tl-a-1's snapshots = %+v; want its own only", snaps)
	}
	if all, _ := l.Snapshots("docker.compose", ""); len(all) != 2 {
		t.Fatalf("every snapshot = %+v; want 2", all)
	}
	if row, ok, err := l.SnapshotRow("docker.compose", "tl-a-1/s-00000001"); err != nil || !ok || row.ID != sid {
		t.Fatalf("SnapshotRow = %+v %v %v", row, ok, err)
	}
	if _, _, err := l.Reap(sid, OutcomeReaped, "removed with adele env snapshot-rm", 1, time.Time{}); err != nil {
		t.Fatal(err)
	}
	if _, ok, err := l.SnapshotRow("docker.compose", "tl-a-1/s-00000001"); err != nil || ok {
		t.Fatalf("a removed snapshot is still listed: %v %v", ok, err)
	}
}

func TestKeptAndEndedRefuseBadRows(t *testing.T) {
	l, _ := tempLedger(t)
	if _, err := l.Kept(Row{Grant: "g", Session: "s", Capability: "c", Action: "a", Resource: "r", Undo: "{"}); !errors.Is(err, ErrInvalid) {
		t.Fatalf("bad undo: %v", err)
	}
	if _, err := l.Kept(Row{Grant: "g", Session: "s", Capability: "c", Action: "a", Resource: "r"}); !errors.Is(err, ErrInvalid) {
		t.Fatalf("no undo: %v", err)
	}
	neg := int64(-1)
	if _, err := l.Kept(Row{Grant: "g", Session: "s", Capability: "c", Action: "a", Resource: "r", Undo: "{}",
		CostCents: &neg}); !errors.Is(err, ErrInvalid) {
		t.Fatalf("negative cost: %v", err)
	}
	if _, _, err := l.Ended(999, ActionStart, "x", time.Time{}); !errors.Is(err, ErrInvalid) {
		t.Fatalf("no such row: %v", err)
	}
	if _, _, err := l.Ended(1, "", "x", time.Time{}); !errors.Is(err, ErrInvalid) {
		t.Fatalf("no action: %v", err)
	}
	id, err := l.Refused(Row{Session: "s", Capability: "c", Action: "a", LimitName: "volume", Allowed: "x", Needed: "y"})
	if err != nil {
		t.Fatal(err)
	}
	if _, _, err := l.Ended(id, ActionStart, "x", time.Time{}); !errors.Is(err, ErrInvalid) {
		t.Fatalf("a refused row ended: %v", err)
	}
}
