package reaper

import (
	"bytes"
	"context"
	"errors"
	"net/http/httptest"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"

	"timelike/adele/internal/broker"
	"timelike/adele/internal/grants"
	"timelike/adele/internal/ledger"
	"timelike/adele/internal/standin"
)

// The provider in these tests is the REAL stand-in handler, served in-process and reached through the
// real StandinClient, made to fail with its own faults (cross-stack P005). The fake below is only for what
// a correct stand-in cannot do: lie about a delete, or fail to list.

const testCanary = "tlcanary-0123456789abcdef0123456789abcdef"

var t0 = time.Date(2026, 10, 16, 10, 0, 0, 0, time.UTC)

type clock struct {
	mu sync.Mutex
	t  time.Time
}

func (c *clock) now() time.Time      { c.mu.Lock(); defer c.mu.Unlock(); return c.t }
func (c *clock) add(d time.Duration) { c.mu.Lock(); c.t = c.t.Add(d); c.mu.Unlock() }

type fixture struct {
	clk    *clock
	led    *ledger.Ledger
	dbPath string
	store  *standin.Store
	faults *standin.Faults
	srv    *httptest.Server
	b      *broker.Broker
	r      *Reaper
	slept  []time.Duration
}

func newFixture(t *testing.T) *fixture {
	t.Helper()
	dir := t.TempDir()
	clk := &clock{t: t0}
	dbPath := filepath.Join(dir, "adele.db")
	led, err := ledger.Open(dbPath)
	if err != nil {
		t.Fatal(err)
	}
	store, err := standin.NewStore(filepath.Join(dir, "boxes.json"))
	if err != nil {
		t.Fatal(err)
	}
	faults := standin.NewFaults(filepath.Join(dir, "faults.json"))
	srv := httptest.NewServer(standin.HandlerWithFaults(testCanary, store, clk.now, faults))
	t.Cleanup(func() { srv.Close(); _ = led.Close() })
	up := broker.NewStandinClient(srv.URL, testCanary)
	up.HTTP.Timeout = 60 * time.Second // plumbing, as in the broker's fixture
	gf, err := grants.Parse("grants.conf", strings.NewReader(
		"[grant demo]\ncapabilities = standin.box\nbudget = 10.00 USD\nttl = 1h\ninstances = 20\nports = 8080\n"))
	if err != nil {
		t.Fatal(err)
	}
	b := &broker.Broker{Grants: gf, Ledger: led, Upstream: up, Now: clk.now, Revision: "rev-test"}
	f := &fixture{clk: clk, led: led, dbPath: dbPath, store: store, faults: faults, srv: srv, b: b}
	f.r = &Reaper{Ledger: led, Provider: up, Now: clk.now, Lock: b.Locker(),
		Sleep: func(d time.Duration) { f.slept = append(f.slept, d) }}
	return f
}

// create asks Adele for a box through the broker, as the agent's request does.
func (f *fixture) create(t *testing.T, name, ttl, agent string) int64 {
	t.Helper()
	out := f.b.Handle(context.Background(), broker.Request{Session: "sess-1", Agent: agent,
		Capability: grants.CapStandinBox, Action: "create", Params: broker.Params{Name: name, TTL: ttl}})
	if out.Status != 200 {
		t.Fatalf("create %s: %d %v", name, out.Status, out.Body)
	}
	return out.Body["ledger_id"].(int64)
}

func (f *fixture) held(name string) bool {
	for _, b := range f.store.List() {
		if b.Name == name {
			return true
		}
	}
	return false
}

func (f *fixture) pass(t *testing.T, force bool) []Result {
	t.Helper()
	res, err := f.r.Pass(context.Background(), force)
	if err != nil {
		t.Fatalf("pass: %v", err)
	}
	return res
}

func TestExpiredBoxIsDeletedAndRecordedFromTheReadBack(t *testing.T) {
	f := newFixture(t)
	ref := f.create(t, "box-a", "1m", "agent-a")
	keep := f.create(t, "box-b", "1h", "")
	if got := f.pass(t, false); len(got) != 0 {
		t.Fatalf("nothing expired yet, got %+v", got)
	}
	f.clk.add(time.Minute) // expiry is due at, not only after, its time
	got := f.pass(t, false)
	if len(got) != 1 {
		t.Fatalf("results = %+v", got)
	}
	res := got[0]
	if res.Ref != ref || res.Outcome != ledger.OutcomeReaped || res.Attempts != 1 || res.ID == 0 ||
		res.Agent != "agent-a" || res.Session != "sess-1" || res.Grant != "demo" ||
		!strings.Contains(res.Cause, "absent from the stand-in's record read back") {
		t.Fatalf("result = %+v", res)
	}
	if f.held("box-a") || !f.held("box-b") {
		t.Fatalf("record after the reap: %+v", f.store.List())
	}
	if live, _ := f.led.Live("demo"); live != 1 {
		t.Fatalf("live = %d, want 1", live)
	}
	if again := f.pass(t, true); len(again) != 0 { // reaped is an ending: never reaped twice
		t.Fatalf("second pass = %+v", again)
	}
	_ = keep
}

func TestAlreadyGoneIsRecordedOnceAndNeverRetried(t *testing.T) {
	f := newFixture(t)
	f.create(t, "box-a", "1m", "")
	if err := f.store.Delete("box-a"); err != nil { // gone at the provider first
		t.Fatal(err)
	}
	f.clk.add(2 * time.Minute)
	got := f.pass(t, false)
	if len(got) != 1 || got[0].Outcome != ledger.OutcomeGone || got[0].Attempts != 0 ||
		!strings.Contains(got[0].Cause, "already gone") {
		t.Fatalf("results = %+v", got)
	}
	f.clk.add(time.Hour)
	if again := f.pass(t, false); len(again) != 0 {
		t.Fatalf("gone was retried: %+v", again)
	}
}

func TestALaterBoxReusingTheNameIsNotTouched(t *testing.T) {
	f := newFixture(t)
	f.create(t, "box-a", "1m", "")
	f.clk.add(30 * time.Second)
	if err := f.store.Delete("box-a"); err != nil { // the first box goes; someone makes another of that name
		t.Fatal(err)
	}
	if err := f.store.Create(standin.Box{Name: "box-a", CreatedAt: f.clk.now(), TTLSeconds: 3600}); err != nil {
		t.Fatal(err)
	}
	f.clk.add(time.Minute)
	got := f.pass(t, false)
	if len(got) != 1 || got[0].Outcome != ledger.OutcomeGone || !strings.Contains(got[0].Cause, "later one") {
		t.Fatalf("results = %+v", got)
	}
	if !f.held("box-a") {
		t.Fatal("the later box was deleted")
	}
}

func TestErroringProviderIsRetriedOnABoundThenGivenUp(t *testing.T) {
	f := newFixture(t)
	f.create(t, "box-a", "1m", "")
	if err := f.faults.Set("box-a", standin.FaultError); err != nil {
		t.Fatal(err)
	}
	f.clk.add(time.Minute)
	got := f.pass(t, false)
	if len(got) != 1 || got[0].Outcome != ledger.OutcomeReapFailed || got[0].Attempts != 3 ||
		!strings.Contains(got[0].Cause, "the delete failed 3 times from Adele's container") ||
		!strings.Contains(got[0].Cause, "500") || !strings.Contains(got[0].Cause, "still in the stand-in's record") {
		t.Fatalf("first pass = %+v", got)
	}
	if len(f.slept) != 2 || f.slept[0] != time.Second || f.slept[1] != 2*time.Second {
		t.Fatalf("waits between attempts = %v", f.slept)
	}
	// Inside the wait, a pass skips it: interval 5 s, then 10 s, 20 s, 40 s.
	if got := f.pass(t, false); len(got) != 0 {
		t.Fatalf("pass inside the wait = %+v", got)
	}
	for i, wait := range []time.Duration{5, 10, 20, 40} {
		f.clk.add(wait * time.Second)
		got = f.pass(t, false)
		if len(got) != 1 || got[0].Outcome != ledger.OutcomeReapFailed {
			t.Fatalf("pass %d = %+v", i+2, got)
		}
	}
	if !got[0].GaveUp || !strings.Contains(got[0].Cause, "gave up after 5 failed passes — the operator retries: docker exec timelike-adele adeled reap") {
		t.Fatalf("fifth pass = %+v", got[0])
	}
	f.clk.add(time.Hour)
	if got := f.pass(t, false); len(got) != 0 {
		t.Fatalf("given-up row reaped by the serving reaper: %+v", got)
	}
	// The operator's pass reaches it once the provider recovers.
	if err := f.faults.Set("box-a", standin.FaultClear); err != nil {
		t.Fatal(err)
	}
	got = f.pass(t, true)
	if len(got) != 1 || got[0].Outcome != ledger.OutcomeReaped || f.held("box-a") {
		t.Fatalf("operator's pass = %+v", got)
	}
	failed := 0
	for _, r := range mustRows(t, f.led) {
		if r.Outcome == ledger.OutcomeReapFailed {
			failed++
		}
	}
	if failed != 5 {
		t.Fatalf("reap-failed rows = %d, want 5 (one per pass, never silent, never unbounded)", failed)
	}
}

func TestARequestNeverWaitsOnAReapsRetries(t *testing.T) {
	f := newFixture(t)
	f.create(t, "box-a", "1m", "")
	if err := f.faults.Set("box-a", standin.FaultError); err != nil {
		t.Fatal(err)
	}
	mu, ok := f.b.Locker().(*sync.Mutex)
	if !ok {
		t.Fatalf("the broker's lock is a %T", f.b.Locker())
	}
	free := 0
	f.r.Sleep = func(time.Duration) {
		if mu.TryLock() { // what a request's Handle takes
			free++
			mu.Unlock()
		}
	}
	f.clk.add(time.Minute)
	if got := f.pass(t, false); len(got) != 1 || got[0].Outcome != ledger.OutcomeReapFailed {
		t.Fatalf("pass = %+v", got)
	}
	if free != 2 {
		t.Fatalf("the broker's lock was free in %d of the 2 waits between attempts", free)
	}
}

func TestDroppedConnectionIsAFailureThenReapedWhenCleared(t *testing.T) {
	f := newFixture(t)
	f.create(t, "box-a", "1m", "")
	_ = f.faults.Set("box-a", standin.FaultDrop)
	f.clk.add(time.Minute)
	got := f.pass(t, false)
	if len(got) != 1 || got[0].Outcome != ledger.OutcomeReapFailed || !f.held("box-a") {
		t.Fatalf("dropped = %+v", got)
	}
	_ = f.faults.Set("box-a", standin.FaultClear)
	f.clk.add(5 * time.Second)
	got = f.pass(t, false)
	if len(got) != 1 || got[0].Outcome != ledger.OutcomeReaped {
		t.Fatalf("after clearing = %+v", got)
	}
}

func TestUnreachableProviderIsAFailureNamingWhereFrom(t *testing.T) {
	f := newFixture(t)
	f.create(t, "box-a", "1m", "")
	f.srv.Close()
	f.clk.add(time.Minute)
	got := f.pass(t, false)
	if len(got) != 1 || got[0].Outcome != ledger.OutcomeReapFailed || got[0].Attempts != 0 ||
		!strings.Contains(got[0].Cause, "could not be read from Adele's container before the delete") {
		t.Fatalf("unreachable = %+v", got)
	}
}

func TestARestartedAdeleReapsFromTheLedger(t *testing.T) {
	f := newFixture(t)
	f.create(t, "box-a", "1m", "agent-a")
	f.clk.add(10 * time.Minute)
	// A new Adele: a fresh ledger handle on the same file and a fresh reaper — nothing in memory.
	led2, err := ledger.Open(f.dbPath)
	if err != nil {
		t.Fatal(err)
	}
	defer led2.Close()
	r2 := &Reaper{Ledger: led2, Provider: f.r.Provider, Now: f.clk.now, Sleep: func(time.Duration) {}}
	var log bytes.Buffer
	ctx, cancel := context.WithCancel(context.Background())
	done := make(chan struct{})
	go func() { r2.Run(ctx, &log); close(done) }()
	deadline := time.Now().Add(30 * time.Second)
	for time.Now().Before(deadline) {
		if rows := mustRows(t, f.led); len(rows) == 2 && rows[1].Outcome == ledger.OutcomeReaped {
			break
		}
		time.Sleep(10 * time.Millisecond)
	}
	cancel()
	<-done
	if f.held("box-a") || !strings.Contains(log.String(), "adeled: reap: reaped box-a") ||
		!strings.Contains(log.String(), "agent agent-a") {
		t.Fatalf("restart reap: held=%v log=%q", f.held("box-a"), log.String())
	}
}

// liar is a provider a correct stand-in is not: its delete succeeds and changes nothing, or its list fails
// after the delete.
type liar struct {
	boxes      []broker.Box
	listCalls  int
	failListAt int
	deleteErr  error
}

func (l *liar) List(context.Context) ([]broker.Box, error) {
	l.listCalls++
	if l.failListAt == l.listCalls {
		return nil, errors.New("connection reset")
	}
	return l.boxes, nil
}
func (l *liar) Delete(context.Context, string) error { return l.deleteErr }

func liarFixture(t *testing.T, p *liar) (*fixture, int64) {
	f := newFixture(t)
	ref := f.create(t, "box-a", "1m", "")
	p.boxes = []broker.Box{{Name: "box-a", CreatedAt: t0, TTLSeconds: 60}}
	f.r.Provider = p
	f.clk.add(time.Minute)
	return f, ref
}

func TestADeleteThatChangesNothingIsNotAReap(t *testing.T) { // P004
	f, _ := liarFixture(t, &liar{})
	got := f.pass(t, false)
	if len(got) != 1 || got[0].Outcome != ledger.OutcomeReapFailed ||
		got[0].Cause != "the delete answered, but the box is still in the stand-in's record read back" {
		t.Fatalf("lying delete = %+v", got)
	}
}

func TestAReadBackThatFailsIsAFailure(t *testing.T) {
	f, _ := liarFixture(t, &liar{failListAt: 2})
	got := f.pass(t, false)
	if len(got) != 1 || got[0].Outcome != ledger.OutcomeReapFailed || got[0].Attempts != 1 ||
		!strings.Contains(got[0].Cause, "could not be read back from Adele's container after the delete") {
		t.Fatalf("read-back failure = %+v", got)
	}
}

// vanishing: the delete errors but the box is gone from the record read back (the answer was lost).
type vanishing struct{ liar }

func (v *vanishing) List(ctx context.Context) ([]broker.Box, error) {
	b, err := v.liar.List(ctx)
	if v.listCalls > 1 {
		return nil, err
	}
	return b, err
}

func TestALostAnswerWithTheBoxGoneIsAReap(t *testing.T) {
	p := &vanishing{liar{deleteErr: errors.New("EOF")}}
	f := newFixture(t)
	f.create(t, "box-a", "1m", "")
	p.boxes = []broker.Box{{Name: "box-a", CreatedAt: t0, TTLSeconds: 60}}
	f.r.Provider = p
	f.clk.add(time.Minute)
	got := f.pass(t, false)
	if len(got) != 1 || got[0].Outcome != ledger.OutcomeReaped || got[0].Attempts != 3 ||
		!strings.Contains(got[0].Cause, "answer was lost (EOF)") {
		t.Fatalf("lost answer = %+v", got)
	}
}

func TestNoSuchBoxAtDeleteIsGone(t *testing.T) {
	p := &vanishing{liar{deleteErr: broker.ErrNoSuchResource}}
	f := newFixture(t)
	f.create(t, "box-a", "1m", "")
	p.boxes = []broker.Box{{Name: "box-a", CreatedAt: t0, TTLSeconds: 60}}
	f.r.Provider = p
	f.clk.add(time.Minute)
	got := f.pass(t, false)
	if len(got) != 1 || got[0].Outcome != ledger.OutcomeGone || got[0].Attempts != 1 ||
		!strings.Contains(got[0].Cause, "had no box box-a when the delete ran") {
		t.Fatalf("no such box = %+v", got)
	}
}

func TestPassStopsOnACancelledContextAndOnALedgerFailure(t *testing.T) {
	f := newFixture(t)
	f.create(t, "box-a", "1m", "")
	f.clk.add(time.Minute)
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if _, err := f.r.Pass(ctx, false); !errors.Is(err, context.Canceled) {
		t.Fatalf("cancelled pass = %v", err)
	}
	// Cancelled during a reap (Adele stopping): nothing is recorded and the row stays due.
	stop, halt := context.WithCancel(context.Background())
	f.r.Provider = cancelling{f.r.Provider, halt}
	if _, err := f.r.Pass(stop, false); !errors.Is(err, context.Canceled) {
		t.Fatalf("pass cancelled mid-reap = %v", err)
	}
	if rows := mustRows(t, f.led); len(rows) != 1 {
		t.Fatalf("a reap cut short by shutdown was recorded: %+v", rows)
	}
	_ = f.led.Close()
	if _, err := f.r.Pass(context.Background(), false); err == nil {
		t.Fatal("a pass over a closed ledger succeeded")
	}
	var log bytes.Buffer
	ctx, cancel = context.WithTimeout(context.Background(), 50*time.Millisecond)
	defer cancel()
	(&Reaper{Ledger: f.led, Provider: f.r.Provider, Interval: 10 * time.Millisecond}).Run(ctx, &log)
	if !strings.Contains(log.String(), "reap pass failed") {
		t.Fatalf("Run did not log the failed pass: %q", log.String())
	}
}

func TestWaitDoublesAndIsCapped(t *testing.T) {
	r := &Reaper{}
	for f, want := range map[int]time.Duration{1: 5 * time.Second, 2: 10 * time.Second, 4: 40 * time.Second, 20: MaxWait} {
		if got := r.Wait(f); got != want {
			t.Errorf("Wait(%d) = %v, want %v", f, got, want)
		}
	}
	if (&Reaper{Container: "x"}).OperatorCommand() != "docker exec x adeled reap" {
		t.Error("operator command does not name the container")
	}
}

func TestLineSaysWhoseResourceAndWhetherRecorded(t *testing.T) {
	l := Line(Result{Ref: 4, Resource: "box-a", Grant: "demo", Session: "s", Agent: "a", Outcome: "reaped", Cause: "deleted", ID: 9})
	if l != "reaped box-a (ledger #4, grant demo, session s, agent a): deleted — recorded as #9" {
		t.Errorf("line = %q", l)
	}
	if l := Line(Result{Ref: 4, Resource: "box-a", Outcome: "gone", Cause: "x"}); !strings.Contains(l, "not recorded") {
		t.Errorf("unrecorded line = %q", l)
	}
}

func mustRows(t *testing.T, l *ledger.Ledger) []ledger.Row {
	t.Helper()
	rows, err := l.Rows()
	if err != nil {
		t.Fatal(err)
	}
	return rows
}

// cancelling cancels the pass's context as the delete runs: Adele told to stop mid-reap.
type cancelling struct {
	Provider
	cancel context.CancelFunc
}

func (c cancelling) Delete(ctx context.Context, name string) error {
	c.cancel()
	return c.Provider.Delete(ctx, name)
}
