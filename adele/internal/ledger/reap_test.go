package ledger

import (
	"database/sql"
	"errors"
	"path/filepath"
	"sync"
	"testing"
	"time"
)

// schemaV1 is slice 0's ledger exactly as it shipped (schema.go at 004 Cycle 2), so the upgrade is tested
// against the file the operator's live stack holds.
const schemaV1 = `
CREATE TABLE ledger (
	id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL,
	outcome TEXT NOT NULL CHECK (outcome IN ('performed', 'refused', 'extended')),
	"grant" TEXT NOT NULL, session TEXT NOT NULL, capability TEXT, action TEXT, resource TEXT,
	cost_cents INTEGER, expires_at TEXT, undo TEXT, limit_name TEXT, allowed TEXT, needed TEXT);
CREATE INDEX ledger_grant_outcome ON ledger ("grant", outcome);
CREATE TABLE extensions (id INTEGER PRIMARY KEY AUTOINCREMENT, "grant" TEXT NOT NULL,
	limit_name TEXT NOT NULL, value TEXT NOT NULL, at TEXT NOT NULL);
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
INSERT INTO meta VALUES ('schema_version', '1');
INSERT INTO ledger (id, at, outcome, "grant", session, capability, action, resource, cost_cents, expires_at, undo)
	VALUES (3, '2026-10-02T12:00:00Z', 'performed', 'demo', 's-1', 'standin.box', 'create', 'box-a', 25,
	'2026-10-02T13:00:00Z', '{"capability":"standin.box","action":"delete","params":{"name":"box-a"}}');
INSERT INTO ledger (id, at, outcome, "grant", session, capability, action, resource, limit_name, allowed, needed)
	VALUES (7, '2026-10-02T12:05:00Z', 'refused', 'demo', 's-2', 'standin.box', 'create', 'box-b', 'ports', '8080', '22');
INSERT INTO extensions ("grant", limit_name, value, at) VALUES ('demo', 'ports', '22', '2026-10-02T12:06:00Z');
`

func TestSchema1FileIsUpgradedKeepingRowsAndIds(t *testing.T) {
	path := filepath.Join(t.TempDir(), "adele.db")
	db, err := sql.Open("sqlite", path)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := db.Exec(schemaV1); err != nil {
		t.Fatal(err)
	}
	db.Close()

	l := open(t, path)
	rows := mustRows(t, l)
	if len(rows) != 2 || rows[0].ID != 3 || rows[1].ID != 7 || rows[0].Resource != "box-a" ||
		rows[1].LimitName != "ports" || rows[0].Ref != nil || rows[1].Host != "" {
		t.Fatalf("rows after upgrade = %+v", rows)
	}
	exts, err := l.Extensions("demo")
	if err != nil || len(exts) != 1 {
		t.Fatalf("extensions = %v, %v", exts, err)
	}
	var v string
	if err := l.db.QueryRow(`SELECT value FROM meta WHERE key='schema_version'`).Scan(&v); err != nil || v != "2" {
		t.Fatalf("schema_version = %q, %v", v, err)
	}
	// A new row continues the sequence after the highest copied id, and the new outcomes are accepted.
	id, err := l.Performed(performed("demo", 25))
	if err != nil || id != 8 {
		t.Fatalf("next id = %d, %v; want 8", id, err)
	}
	if _, wrote, err := l.Reap(3, OutcomeReaped, "deleted; absent from the stand-in's record", 1, time.Time{}); err != nil || !wrote {
		t.Fatalf("Reap after upgrade: %v %v", wrote, err)
	}
	l.Close()
	l2 := open(t, path) // reopening an upgraded file changes nothing
	if got := mustRows(t, l2); len(got) != 4 {
		t.Fatalf("rows after reopen = %d, want 4", len(got))
	}
}

func expiring(name string, exp time.Time) Row {
	r := performed("demo", 25)
	r.Resource, r.ExpiresAt, r.Agent = name, &exp, "agent-a"
	r.Undo = `{"capability":"standin.box","action":"delete","params":{"name":"` + name + `"}}`
	return r
}

func TestReapCopiesThePerformedRowAndEndsItOnce(t *testing.T) {
	l, _ := tempLedger(t)
	now := time.Date(2026, 10, 16, 10, 0, 0, 0, time.UTC)
	ref, err := l.Performed(expiring("box-r", now.Add(-time.Minute)))
	if err != nil {
		t.Fatal(err)
	}
	id, wrote, err := l.Reap(ref, OutcomeReapFailed, "the stand-in did not answer", 3, now)
	if err != nil || !wrote || id == 0 {
		t.Fatalf("failed reap: %d %v %v", id, wrote, err)
	}
	if _, wrote, err = l.Reap(ref, OutcomeReaped, "deleted", 1, now.Add(time.Second)); err != nil || !wrote {
		t.Fatalf("reap: %v %v", wrote, err)
	}
	// A second ending is not written, and is not an error: the other reaper got there first (FR-28).
	if _, wrote, err = l.Reap(ref, OutcomeGone, "not in the record", 0, now.Add(2*time.Second)); err != nil || wrote {
		t.Fatalf("second ending: wrote=%v err=%v", wrote, err)
	}
	rows := mustRows(t, l)
	if len(rows) != 3 {
		t.Fatalf("rows = %d, want 3", len(rows))
	}
	r := rows[2]
	if r.Outcome != OutcomeReaped || r.Ref == nil || *r.Ref != ref || r.Grant != "demo" || r.Session != "s-1" ||
		r.Agent != "agent-a" || r.Resource != "box-r" || r.Action != ActionDelete || r.Capability != "standin.box" ||
		r.Attempts == nil || *r.Attempts != 1 || r.Cause != "deleted" {
		t.Fatalf("reap row = %+v", r)
	}
}

func TestReapRefusesWhatIsNotAPerformedRow(t *testing.T) {
	l, _ := tempLedger(t)
	rid, err := l.Refused(refused("demo"))
	if err != nil {
		t.Fatal(err)
	}
	for _, tc := range []struct {
		ref            int64
		outcome, cause string
		attempts       int
	}{
		{rid, OutcomeReaped, "x", 1},    // a refused row has nothing to reap
		{999, OutcomeReaped, "x", 1},    // no such row
		{rid, OutcomePerformed, "x", 1}, // not a reap outcome
		{rid, OutcomeReaped, " ", 1},    // no cause
		{rid, OutcomeReaped, "x", -1},   // negative attempts
	} {
		if _, wrote, err := l.Reap(tc.ref, tc.outcome, tc.cause, tc.attempts, time.Time{}); !errors.Is(err, ErrInvalid) || wrote {
			t.Errorf("Reap(%+v) = %v, %v; want ErrInvalid", tc, wrote, err)
		}
	}
	if got := mustRows(t, l); len(got) != 1 {
		t.Fatalf("rows = %d, want 1", len(got))
	}
}

func TestDueReadsTheLedgerWithFailures(t *testing.T) {
	l, _ := tempLedger(t)
	now := time.Date(2026, 10, 16, 10, 0, 0, 0, time.UTC)
	late, _ := l.Performed(expiring("box-late", now.Add(-time.Minute)))
	early, _ := l.Performed(expiring("box-early", now.Add(-time.Hour)))
	if _, err := l.Performed(expiring("box-future", now.Add(time.Minute))); err != nil {
		t.Fatal(err)
	}
	done, _ := l.Performed(expiring("box-done", now.Add(-2*time.Hour)))
	if _, _, err := l.Reap(done, OutcomeGone, "not in the record", 0, now); err != nil {
		t.Fatal(err)
	}
	failAt := now.Add(-30 * time.Second)
	for i := 0; i < 2; i++ {
		if _, _, err := l.Reap(late, OutcomeReapFailed, "error", 3, failAt.Add(time.Duration(i)*time.Second)); err != nil {
			t.Fatal(err)
		}
	}
	due, err := l.Due(now)
	if err != nil {
		t.Fatal(err)
	}
	if len(due) != 2 || due[0].Row.ID != early || due[1].Row.ID != late {
		t.Fatalf("due = %+v", due)
	}
	if due[0].Failures != 0 || !due[0].LastFailure.IsZero() || due[1].Failures != 2 ||
		!due[1].LastFailure.Equal(failAt.Add(time.Second)) {
		t.Fatalf("failures = %+v", due)
	}
	// An exact expiry is due (at or before now).
	exact, _ := l.Performed(expiring("box-exact", now))
	if due, _ = l.Due(now); len(due) != 3 || due[2].Row.ID != exact {
		t.Fatalf("exact expiry not due: %+v", due)
	}
}

func TestLiveExcludesReapedAndGoneButSpentStays(t *testing.T) {
	l, _ := tempLedger(t)
	now := time.Date(2026, 10, 16, 10, 0, 0, 0, time.UTC)
	a, _ := l.Performed(expiring("box-a", now))
	b, _ := l.Performed(expiring("box-b", now))
	c, _ := l.Performed(expiring("box-c", now))
	_, _, _ = l.Reap(a, OutcomeReaped, "deleted", 1, now)
	_, _, _ = l.Reap(b, OutcomeGone, "not in the record", 0, now)
	_, _, _ = l.Reap(c, OutcomeReapFailed, "error", 3, now) // a failure leaves it live
	live, err := l.Live("demo")
	if err != nil || live != 1 {
		t.Fatalf("live = %d, %v; want 1", live, err)
	}
	spent, err := l.Spent("demo")
	if err != nil || spent != 75 {
		t.Fatalf("spent = %d, %v; want 75", spent, err)
	}
}

func TestDenialsByHostNewestFirstAndBounded(t *testing.T) {
	l, _ := tempLedger(t)
	base := time.Date(2026, 10, 16, 10, 0, 0, 0, time.UTC)
	add := func(host string, at time.Time) int64 {
		r := refused("demo")
		r.Host, r.At, r.Agent = host, at, "agent-b"
		id, err := l.Refused(r)
		if err != nil {
			t.Fatal(err)
		}
		return id
	}
	add("adele-standin:8481", base.Add(-25*time.Hour)) // outside the window
	var standin []int64
	for i := 0; i < 4; i++ {
		standin = append(standin, add("adele-standin:8481", base.Add(time.Duration(i)*time.Minute)))
	}
	other := add("example.invalid:443", base.Add(time.Minute))
	since := base.Add(-24 * time.Hour)

	all, err := l.Denials(since, "", 3)
	if err != nil {
		t.Fatal(err)
	}
	if len(all) != 4 || all[0].ID != standin[3] || all[1].ID != standin[2] || all[2].ID != other || all[3].ID != standin[1] {
		t.Fatalf("all = %v", ids(all))
	}
	one, err := l.Denials(since, "example.invalid:443", 20)
	if err != nil || len(one) != 1 || one[0].ID != other || one[0].Agent != "agent-b" {
		t.Fatalf("one host = %v, %v", ids(one), err)
	}
	none, err := l.Denials(since, "nobody.invalid:1", 20)
	if err != nil || len(none) != 0 {
		t.Fatalf("no denials = %v, %v", ids(none), err)
	}
}

func ids(rows []Row) []int64 {
	out := make([]int64, len(rows))
	for i, r := range rows {
		out[i] = r.ID
	}
	return out
}

func TestConcurrentReapsWriteOneEnding(t *testing.T) {
	l, path := tempLedger(t)
	ref, err := l.Performed(expiring("box-c", time.Now().Add(-time.Minute)))
	if err != nil {
		t.Fatal(err)
	}
	other := open(t, path) // the operator's `adeled reap` opens its own handle
	var wg sync.WaitGroup
	wrote := make([]bool, 8)
	for i := range wrote {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			h := l
			if i%2 == 1 {
				h = other
			}
			_, w, err := h.Reap(ref, OutcomeReaped, "deleted", 1, time.Time{})
			if err != nil {
				t.Errorf("reap %d: %v", i, err)
			}
			wrote[i] = w
		}(i)
	}
	wg.Wait()
	n := 0
	for _, w := range wrote {
		if w {
			n++
		}
	}
	if n != 1 {
		t.Fatalf("%d endings written, want 1", n)
	}
}
