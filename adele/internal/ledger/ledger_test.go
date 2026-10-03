package ledger

import (
	"database/sql"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"
)

func open(t *testing.T, path string) *Ledger {
	t.Helper()
	l, err := Open(path)
	if err != nil {
		t.Fatalf("Open: %v", err)
	}
	t.Cleanup(func() { l.Close() })
	return l
}

func tempLedger(t *testing.T) (*Ledger, string) {
	t.Helper()
	path := filepath.Join(t.TempDir(), "adele.db")
	return open(t, path), path
}

func cents(n int64) *int64 { return &n }

func performed(grant string, cost int64) Row {
	exp := time.Date(2026, 10, 2, 13, 0, 0, 0, time.UTC)
	return Row{
		At: time.Date(2026, 10, 2, 12, 0, 0, 0, time.UTC), Grant: grant, Session: "s-1",
		Capability: "standin.box", Action: "create", Resource: "box-1", CostCents: cents(cost),
		ExpiresAt: &exp,
		Undo:      `{"capability":"standin.box","action":"delete","params":{"name":"box-1"}}`,
	}
}

func refused(grant string) Row {
	return Row{Grant: grant, Session: "s-2", Capability: "standin.box", Action: "create",
		Resource: "box-9", LimitName: "budget", Allowed: "0.40 USD", Needed: "0.50 USD"}
}

func mustRows(t *testing.T, l *Ledger) []Row {
	t.Helper()
	rows, err := l.Rows()
	if err != nil {
		t.Fatalf("Rows: %v", err)
	}
	return rows
}

func TestOpenCreatesSchemaIdempotently(t *testing.T) {
	l, path := tempLedger(t)
	if _, err := l.Performed(performed("demo", 25)); err != nil {
		t.Fatal(err)
	}
	l.Close()
	for i := 0; i < 2; i++ {
		l2 := open(t, path)
		if got := mustRows(t, l2); len(got) != 1 {
			t.Fatalf("reopen %d: %d rows, want 1", i, len(got))
		}
		var n int
		if err := l2.db.QueryRow(`SELECT count(*) FROM meta WHERE key='schema_version' AND value='1'`).
			Scan(&n); err != nil || n != 1 {
			t.Fatalf("schema_version rows = %d, %v", n, err)
		}
		var mode string
		if err := l2.db.QueryRow(`PRAGMA journal_mode`).Scan(&mode); err != nil || mode != "wal" {
			t.Fatalf("journal_mode = %q, %v", mode, err)
		}
		l2.Close()
	}
}

func TestPerformedRoundTrip(t *testing.T) {
	l, _ := tempLedger(t)
	in := performed("demo", 25)
	id, err := l.Performed(in)
	if err != nil {
		t.Fatal(err)
	}
	rows := mustRows(t, l)
	if len(rows) != 1 {
		t.Fatalf("%d rows", len(rows))
	}
	r := rows[0]
	if r.ID != id || r.Outcome != OutcomePerformed || r.Grant != "demo" || r.Session != "s-1" ||
		r.Capability != "standin.box" || r.Action != "create" || r.Resource != "box-1" ||
		*r.CostCents != 25 || !r.ExpiresAt.Equal(*in.ExpiresAt) || r.Undo != in.Undo ||
		!r.At.Equal(in.At) || r.LimitName != "" || r.At.Location() != time.UTC {
		t.Fatalf("round trip: %+v", r)
	}
}

func TestRefusedRoundTrip(t *testing.T) {
	l, _ := tempLedger(t)
	before := time.Now().Add(-time.Second)
	if _, err := l.Refused(refused("")); err != nil {
		t.Fatal(err)
	}
	quoted := refused("demo")
	quoted.CostCents = cents(50)
	if _, err := l.Refused(quoted); err != nil {
		t.Fatal(err)
	}
	rows := mustRows(t, l)
	if len(rows) != 2 {
		t.Fatalf("%d rows", len(rows))
	}
	a, b := rows[0], rows[1]
	if a.Outcome != OutcomeRefused || a.Grant != "" || a.CostCents != nil || a.ExpiresAt != nil ||
		a.Undo != "" || a.LimitName != "budget" || a.Allowed != "0.40 USD" || a.Needed != "0.50 USD" {
		t.Fatalf("refused row: %+v", a)
	}
	if a.At.Before(before) || a.At.After(time.Now().Add(time.Second)) {
		t.Fatalf("default at = %v", a.At)
	}
	if b.Grant != "demo" || b.CostCents == nil || *b.CostCents != 50 || a.ID >= b.ID {
		t.Fatalf("quoted refused row: %+v", b)
	}
}

func TestExtendedWritesBothTables(t *testing.T) {
	l, _ := tempLedger(t)
	at := time.Date(2026, 10, 2, 12, 30, 0, 0, time.FixedZone("x", 3600))
	if _, err := l.Extended("demo", "budget", "2.00 USD", "3.00 USD", at); err != nil {
		t.Fatal(err)
	}
	if _, err := l.Extended("demo", "budget", "3.00 USD", "4.00 USD", time.Time{}); err != nil {
		t.Fatal(err)
	}
	if _, err := l.Extended("other", "ttl", "1h", "2h", at); err != nil {
		t.Fatal(err)
	}
	ext, err := l.Extensions("demo")
	if err != nil || len(ext) != 2 {
		t.Fatalf("extensions = %+v, %v", ext, err)
	}
	if ext[0] != (Extension{"demo", "budget", "3.00 USD", at.UTC()}) || ext[1].Value != "4.00 USD" {
		t.Fatalf("extensions = %+v", ext)
	}
	rows := mustRows(t, l)
	r := rows[0]
	if len(rows) != 3 || r.Outcome != OutcomeExtended || r.Session != OperatorSession ||
		r.LimitName != "budget" || r.Allowed != "2.00 USD" || r.Needed != "3.00 USD" || r.Capability != "" {
		t.Fatalf("extended rows: %+v", rows)
	}
	if none, err := l.Extensions("nobody"); err != nil || len(none) != 0 {
		t.Fatalf("extensions(nobody) = %v, %v", none, err)
	}
}

func TestExtendedIsAtomic(t *testing.T) {
	l, _ := tempLedger(t)
	// Make the ledger insert fail inside the transaction: the extensions row
	// must roll back with it.
	if _, err := l.db.Exec(`CREATE TRIGGER no_ext BEFORE INSERT ON ledger
		WHEN NEW.outcome = 'extended' BEGIN SELECT RAISE(ABORT, 'boom'); END`); err != nil {
		t.Fatal(err)
	}
	if _, err := l.Extended("demo", "ttl", "1h", "2h", time.Now()); err == nil {
		t.Fatal("Extended succeeded despite the trigger")
	}
	if ext, _ := l.Extensions("demo"); len(ext) != 0 {
		t.Fatalf("extension row survived a failed transaction: %+v", ext)
	}
}

func TestValidationWritesNothing(t *testing.T) {
	l, _ := tempLedger(t)
	mut := func(f func(*Row)) Row { r := performed("demo", 25); f(&r); return r }
	badPerformed := []Row{
		mut(func(r *Row) { r.Grant = "" }),
		mut(func(r *Row) { r.Session = " " }),
		mut(func(r *Row) { r.Capability = "" }),
		mut(func(r *Row) { r.Action = "" }),
		mut(func(r *Row) { r.Resource = "" }),
		mut(func(r *Row) { r.Undo = "" }),
		mut(func(r *Row) { r.Undo = "{not json" }),
		mut(func(r *Row) { r.CostCents = nil }),
		mut(func(r *Row) { r.CostCents = cents(-1) }),
		mut(func(r *Row) { r.ExpiresAt = nil }),
		mut(func(r *Row) { r.ExpiresAt = &time.Time{} }),
	}
	for i, r := range badPerformed {
		if _, err := l.Performed(r); !errors.Is(err, ErrInvalid) {
			t.Errorf("performed case %d: err = %v, want ErrInvalid", i, err)
		}
	}
	rmut := func(f func(*Row)) Row { r := refused("demo"); f(&r); return r }
	badRefused := []Row{
		rmut(func(r *Row) { r.Session = "" }),
		rmut(func(r *Row) { r.Capability = "" }),
		rmut(func(r *Row) { r.Action = "" }),
		rmut(func(r *Row) { r.LimitName = "" }),
		rmut(func(r *Row) { r.Allowed = "" }),
		rmut(func(r *Row) { r.Needed = "" }),
		rmut(func(r *Row) { r.CostCents = cents(-5) }),
	}
	for i, r := range badRefused {
		if _, err := l.Refused(r); !errors.Is(err, ErrInvalid) {
			t.Errorf("refused case %d: err = %v, want ErrInvalid", i, err)
		}
	}
	for i, a := range [][4]string{{"", "ttl", "1h", "2h"}, {"demo", "", "1h", "2h"},
		{"demo", "ttl", "", "2h"}, {"demo", "ttl", "1h", ""}, {"demo", "colour", "1h", "2h"}} {
		if _, err := l.Extended(a[0], a[1], a[2], a[3], time.Now()); !errors.Is(err, ErrInvalid) {
			t.Errorf("extended case %d: err = %v, want ErrInvalid", i, err)
		}
	}
	if rows := mustRows(t, l); len(rows) != 0 {
		t.Fatalf("invalid input wrote %d rows", len(rows))
	}
	if ext, _ := l.Extensions("demo"); len(ext) != 0 {
		t.Fatalf("invalid input wrote %d extensions", len(ext))
	}
	_, err := l.Performed(mut(func(r *Row) { r.Grant, r.Action = "", "" }))
	if err == nil || !strings.Contains(err.Error(), "missing action, grant") {
		t.Fatalf("message = %v, want sorted missing fields", err)
	}
}

func TestSpentAndLivePerGrant(t *testing.T) {
	l, _ := tempLedger(t)
	for _, c := range []struct {
		grant string
		cost  int64
	}{{"demo", 25}, {"demo", 50}, {"other", 1000}} {
		if _, err := l.Performed(performed(c.grant, c.cost)); err != nil {
			t.Fatal(err)
		}
	}
	quoted := refused("demo")
	quoted.CostCents = cents(700) // refused cost never counts
	if _, err := l.Refused(quoted); err != nil {
		t.Fatal(err)
	}
	if _, err := l.Extended("demo", "instances", "2", "3", time.Now()); err != nil {
		t.Fatal(err)
	}
	for _, c := range []struct {
		grant string
		spent int64
		live  int
	}{{"demo", 75, 2}, {"other", 1000, 1}, {"nobody", 0, 0}} {
		spent, err := l.Spent(c.grant)
		if err != nil || spent != c.spent {
			t.Errorf("Spent(%s) = %d, %v; want %d", c.grant, spent, err, c.spent)
		}
		live, err := l.Live(c.grant)
		if err != nil || live != c.live {
			t.Errorf("Live(%s) = %d, %v; want %d", c.grant, live, err, c.live)
		}
	}
}

// TestConcurrentHandles is `serve` and the operator's `extend` writing the
// same file at once: every write must land, none may fail busy.
func TestConcurrentHandles(t *testing.T) {
	_, path := tempLedger(t)
	a, b := open(t, path), open(t, path)
	const n = 50
	var wg sync.WaitGroup
	errs := make(chan error, 2*n)
	wg.Add(2)
	go func() {
		defer wg.Done()
		for i := 0; i < n; i++ {
			if _, err := a.Performed(performed("demo", 1)); err != nil {
				errs <- fmt.Errorf("performed %d: %w", i, err)
			}
		}
	}()
	go func() {
		defer wg.Done()
		for i := 0; i < n; i++ {
			if _, err := b.Extended("demo", "budget", "x", fmt.Sprint(i), time.Now()); err != nil {
				errs <- fmt.Errorf("extended %d: %w", i, err)
			}
		}
	}()
	wg.Wait()
	close(errs)
	for err := range errs {
		t.Error(err)
	}
	if rows := mustRows(t, a); len(rows) != 2*n {
		t.Fatalf("%d rows, want %d", len(rows), 2*n)
	}
	if ext, _ := a.Extensions("demo"); len(ext) != n {
		t.Fatalf("%d extensions, want %d", len(ext), n)
	}
	if spent, _ := b.Spent("demo"); spent != n {
		t.Fatalf("spent = %d, want %d", spent, n)
	}
}

func TestRefusesNewerSchema(t *testing.T) {
	l, path := tempLedger(t)
	if _, err := l.db.Exec(`UPDATE meta SET value = '2' WHERE key = 'schema_version'`); err != nil {
		t.Fatal(err)
	}
	l.Close()
	if _, err := Open(path); !errors.Is(err, ErrNewerSchema) {
		t.Fatalf("Open(v2) err = %v, want ErrNewerSchema", err)
	}
}

func TestRefusesBadSchemaVersion(t *testing.T) {
	path := filepath.Join(t.TempDir(), "adele.db")
	db, err := sql.Open("sqlite", path)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := db.Exec(`CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
		INSERT INTO meta VALUES ('schema_version', 'banana')`); err != nil {
		t.Fatal(err)
	}
	db.Close()
	if _, err := Open(path); err == nil || !strings.Contains(err.Error(), "banana") {
		t.Fatalf("Open(bad version) err = %v", err)
	}
}

func TestMetaWithoutVersionIsAdopted(t *testing.T) {
	path := filepath.Join(t.TempDir(), "adele.db")
	db, err := sql.Open("sqlite", path)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := db.Exec(`CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)`); err != nil {
		t.Fatal(err)
	}
	db.Close()
	l := open(t, path)
	var v string
	if err := l.db.QueryRow(`SELECT value FROM meta WHERE key='schema_version'`).Scan(&v); err != nil || v != "1" {
		t.Fatalf("schema_version = %q, %v", v, err)
	}
}

func TestOpenErrors(t *testing.T) {
	for _, p := range []string{"", "a?b", "a#b"} {
		if _, err := Open(p); err == nil {
			t.Errorf("Open(%q) succeeded", p)
		}
	}
	dir := t.TempDir()
	if _, err := Open(filepath.Join(dir, "missing", "adele.db")); err == nil {
		t.Error("Open in a missing directory succeeded")
	}
	notDB := filepath.Join(dir, "garbage.db")
	if err := os.WriteFile(notDB, []byte(strings.Repeat("not a database ", 100)), 0o600); err != nil {
		t.Fatal(err)
	}
	if _, err := Open(notDB); err == nil {
		t.Error("Open(garbage) succeeded")
	}
}

func TestBadStoredTimeIsAnError(t *testing.T) {
	l, _ := tempLedger(t)
	if _, err := l.Performed(performed("demo", 1)); err != nil {
		t.Fatal(err)
	}
	if _, err := l.Extended("demo", "ttl", "1h", "2h", time.Now()); err != nil {
		t.Fatal(err)
	}
	// Corrupt by hand: Adele itself never updates a row.
	if _, err := l.db.Exec(`UPDATE ledger SET expires_at = 'soon'`); err != nil {
		t.Fatal(err)
	}
	if _, err := l.Rows(); err == nil {
		t.Error("Rows with a bad expires_at succeeded")
	}
	if _, err := l.db.Exec(`UPDATE ledger SET at = 'yesterday'`); err != nil {
		t.Fatal(err)
	}
	if _, err := l.Rows(); err == nil {
		t.Error("Rows with a bad at succeeded")
	}
	if _, err := l.db.Exec(`UPDATE extensions SET at = 'yesterday'`); err != nil {
		t.Fatal(err)
	}
	if _, err := l.Extensions("demo"); err == nil {
		t.Error("Extensions with a bad at succeeded")
	}
}

func TestClosedLedgerErrors(t *testing.T) {
	l, _ := tempLedger(t)
	if err := l.Close(); err != nil {
		t.Fatal(err)
	}
	if _, err := l.Performed(performed("demo", 1)); err == nil {
		t.Error("Performed on a closed ledger succeeded")
	}
	if _, err := l.Refused(refused("demo")); err == nil {
		t.Error("Refused on a closed ledger succeeded")
	}
	if _, err := l.Extended("demo", "ttl", "1h", "2h", time.Now()); err == nil {
		t.Error("Extended on a closed ledger succeeded")
	}
	if _, err := l.Rows(); err == nil {
		t.Error("Rows on a closed ledger succeeded")
	}
	if _, err := l.Spent("demo"); err == nil {
		t.Error("Spent on a closed ledger succeeded")
	}
	if _, err := l.Live("demo"); err == nil {
		t.Error("Live on a closed ledger succeeded")
	}
	if _, err := l.Extensions("demo"); err == nil {
		t.Error("Extensions on a closed ledger succeeded")
	}
}
