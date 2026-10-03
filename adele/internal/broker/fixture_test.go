package broker

import (
	"context"
	"database/sql"
	"net/http/httptest"
	"reflect"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"timelike/adele/internal/grants"
	"timelike/adele/internal/ledger"
	"timelike/adele/internal/standin"
)

// The broker's upstream in every test is the REAL stand-in handler served in-process, reached through
// the real StandinClient (cross-stack P004/P005: provider paths are never mocked). "Performed" and
// "nothing performed" are read from the stand-in's own record, store.List().

const testCanary = "tlcanary-0123456789abcdef0123456789abcdef"

var fixedNow = time.Date(2026, 10, 2, 12, 0, 0, 0, time.UTC)

func clock() time.Time { return fixedNow }

const demoGrant = `[grant demo]
capabilities = standin.box
budget = 1.00 USD
ttl = 1h
instances = 2
ports = 8080
`

// grantText is one standin.box grant with the given limits.
func grantText(name, budget, ttl, instances, ports string) string {
	return "[grant " + name + "]\ncapabilities = standin.box\nbudget = " + budget + "\nttl = " + ttl +
		"\ninstances = " + instances + "\nports = " + ports + "\n"
}

type fixture struct {
	b         *Broker
	led       *ledger.Ledger
	store     *standin.Store
	srv       *httptest.Server
	dbPath    string
	storePath string
}

func newFixture(t *testing.T, grantFile string) *fixture {
	t.Helper()
	gf, err := grants.Parse("grants.conf", strings.NewReader(grantFile))
	if err != nil {
		t.Fatalf("parse grants: %v", err)
	}
	return newFixtureFile(t, gf)
}

// newFixtureFile takes a grants.File built directly, for grants the parser cannot express (a grant
// without standin.box, while standin.box is the only capability slice 0 knows).
func newFixtureFile(t *testing.T, gf *grants.File) *fixture {
	t.Helper()
	dir := t.TempDir()
	dbPath := dir + "/adele.db"
	led, err := ledger.Open(dbPath)
	if err != nil {
		t.Fatalf("open ledger: %v", err)
	}
	storePath := dir + "/boxes.json"
	store, err := standin.NewStore(storePath)
	if err != nil {
		t.Fatalf("new store: %v", err)
	}
	srv := httptest.NewServer(standin.Handler(testCanary, store, clock))
	t.Cleanup(func() { srv.Close(); _ = led.Close() })
	b := &Broker{Grants: gf, Ledger: led, Upstream: NewStandinClient(srv.URL, testCanary), Now: clock, Revision: "rev-test"}
	return &fixture{b: b, led: led, store: store, srv: srv, dbPath: dbPath, storePath: storePath}
}

func boxReq(name, ttl string, ports ...int) Request {
	return Request{Session: "sess-1", Capability: grants.CapStandinBox, Action: "create",
		Params: Params{Name: name, TTL: ttl, Ports: ports}}
}

func (f *fixture) handle(req Request) Outcome { return f.b.Handle(context.Background(), req) }

func (f *fixture) rows(t *testing.T) []ledger.Row {
	t.Helper()
	rows, err := f.led.Rows()
	if err != nil {
		t.Fatalf("ledger rows: %v", err)
	}
	return rows
}

func (f *fixture) countOutcome(t *testing.T, outcome string) int {
	t.Helper()
	n := 0
	for _, r := range f.rows(t) {
		if r.Outcome == outcome {
			n++
		}
	}
	return n
}

func (f *fixture) hasBox(name string) (standin.Box, bool) {
	for _, b := range f.store.List() {
		if b.Name == name {
			return b, true
		}
	}
	return standin.Box{}, false
}

// mustPerform performs a request and fails the test unless it was performed.
func (f *fixture) mustPerform(t *testing.T, req Request) Outcome {
	t.Helper()
	out := f.handle(req)
	if out.Status != 200 {
		t.Fatalf("setup request %s: status %d, body %v", req.Params.Name, out.Status, out.Body)
	}
	return out
}

// sabotageLedgerTable drops the ledger table behind the ledger's back (a damaged file), leaving the
// extensions table: the effective grant still resolves, and the next ledger read or write fails.
func (f *fixture) sabotageLedgerTable(t *testing.T) {
	t.Helper()
	db, err := sql.Open("sqlite", f.dbPath+"?_pragma=busy_timeout(5000)")
	if err != nil {
		t.Fatalf("open raw: %v", err)
	}
	defer db.Close()
	if _, err := db.Exec(`DROP TABLE ledger`); err != nil {
		t.Fatalf("drop ledger table: %v", err)
	}
}

// assertUnchanged fails unless the stand-in's own record equals before.
func (f *fixture) assertUnchanged(t *testing.T, before []standin.Box) {
	t.Helper()
	if after := f.store.List(); !reflect.DeepEqual(before, after) {
		t.Errorf("stand-in record changed:\nbefore %+v\nafter  %+v", before, after)
	}
}

// countingUpstream wraps the real StandinClient: it counts calls and can run a hook before each, so a
// test can observe "never quoted" or fail the ledger between check and perform.
type countingUpstream struct {
	Upstream
	quotes, creates    atomic.Int32
	beforeQ, afterMake func()
}

func (c *countingUpstream) Quote(ctx context.Context, ttl time.Duration) (int64, error) {
	c.quotes.Add(1)
	if c.beforeQ != nil {
		c.beforeQ()
	}
	return c.Upstream.Quote(ctx, ttl)
}

func (c *countingUpstream) Create(ctx context.Context, name string, ttl time.Duration, ports []int) (Created, error) {
	c.creates.Add(1)
	made, err := c.Upstream.Create(ctx, name, ttl, ports)
	if c.afterMake != nil {
		c.afterMake()
	}
	return made, err
}

func (f *fixture) count() *countingUpstream {
	c := &countingUpstream{Upstream: f.b.Upstream}
	f.b.Upstream = c
	return c
}
