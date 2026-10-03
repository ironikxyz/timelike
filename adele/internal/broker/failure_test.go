package broker

import (
	"fmt"
	"strings"
	"sync"
	"testing"
	"time"

	"timelike/adele/internal/grants"
	"timelike/adele/internal/ledger"
	"timelike/adele/internal/standin"
)

// assert502 checks the contract's upstream-failure envelope and that nothing was recorded as performed.
func assert502(t *testing.T, f *fixture, out Outcome, contains string) {
	t.Helper()
	if out.Status != 502 || out.Body["performed"] != false {
		t.Fatalf("got %d %v, want 502 performed:false", out.Status, out.Body)
	}
	msg := out.Body["error"].(string)
	if !strings.HasPrefix(msg, "stand-in failed: ") || !strings.Contains(msg, contains) {
		t.Errorf("error = %q, want it to contain %q", msg, contains)
	}
	if strings.Contains(msg, testCanary) {
		t.Errorf("error text carries the canary: %q", msg)
	}
	if n := f.countOutcome(t, ledger.OutcomePerformed); n != 0 {
		t.Errorf("%d performed rows after an upstream failure", n)
	}
}

func TestUpstreamFailures(t *testing.T) {
	t.Run("wrong credential is 401 upstream, 502 here", func(t *testing.T) {
		f := newFixture(t, demoGrant)
		wrong := "tlcanary-ffffffffffffffffffffffffffffffff"
		f.b.Upstream = NewStandinClient(f.srv.URL, wrong)
		out := f.handle(boxReq("b", ""))
		assert502(t, f, out, "401")
		if strings.Contains(out.Body["error"].(string), wrong) {
			t.Errorf("error text carries the client's credential")
		}
		if len(f.store.List()) != 0 {
			t.Errorf("stand-in performed despite 401")
		}
	})
	t.Run("stand-in down", func(t *testing.T) {
		f := newFixture(t, demoGrant)
		f.srv.Close()
		assert502(t, f, f.handle(boxReq("b", "")), "/v1/quote")
	})
	t.Run("unusable base URL", func(t *testing.T) {
		f := newFixture(t, demoGrant)
		f.b.Upstream = NewStandinClient("http://bad\x7fhost", testCanary)
		assert502(t, f, f.handle(boxReq("b", "")), "invalid")
	})
	t.Run("duplicate name is 409 upstream, 502 with its message", func(t *testing.T) {
		f := newFixture(t, demoGrant)
		if err := f.store.Create(standin.Box{Name: "dup", CreatedAt: fixedNow, TTLSeconds: 60}); err != nil {
			t.Fatal(err)
		}
		before := f.store.List()
		assert502(t, f, f.handle(boxReq("dup", "")), "a box named dup exists")
		f.assertUnchanged(t, before)
	})
}

// The ledger failing at each point: before performing it is a 500 saying nothing was performed; after
// performing it is the one 500 that says performed:true.
func TestLedgerFailures(t *testing.T) {
	t.Run("ledger closed before the request", func(t *testing.T) {
		f := newFixture(t, demoGrant)
		_ = f.led.Close()
		out := f.handle(boxReq("b", ""))
		if out.Status != 500 || !strings.Contains(out.Body["error"].(string), "extensions do not apply") {
			t.Fatalf("got %d %v", out.Status, out.Body)
		}
		if len(f.store.List()) != 0 {
			t.Errorf("performed with a closed ledger")
		}
	})
	t.Run("ledger closed after the quote", func(t *testing.T) {
		f := newFixture(t, demoGrant)
		f.count().beforeQ = func() { _ = f.led.Close() }
		out := f.handle(boxReq("b", ""))
		if out.Status != 500 || !strings.Contains(out.Body["error"].(string), "the ledger failed") {
			t.Fatalf("got %d %v", out.Status, out.Body)
		}
		if len(f.store.List()) != 0 {
			t.Errorf("performed despite the ledger failing before the budget check")
		}
	})
	t.Run("ledger closed after the stand-in created", func(t *testing.T) {
		f := newFixture(t, demoGrant)
		f.count().afterMake = func() { _ = f.led.Close() }
		out := f.handle(boxReq("b", ""))
		if out.Status != 500 || out.Body["performed"] != true ||
			!strings.Contains(out.Body["error"].(string), "box b was created but the ledger write failed") ||
			!strings.Contains(out.Body["remediation"].(string), "adeled ledger") {
			t.Fatalf("got %d %v", out.Status, out.Body)
		}
		if _, ok := f.hasBox("b"); !ok {
			t.Errorf("the stand-in has no b, yet the broker says it was performed")
		}
	})
	t.Run("ledger table damaged before the instances check", func(t *testing.T) {
		f := newFixture(t, demoGrant)
		f.sabotageLedgerTable(t)
		out := f.handle(boxReq("b", ""))
		if out.Status != 500 || !strings.Contains(out.Body["error"].(string), "the ledger failed") {
			t.Fatalf("got %d %v", out.Status, out.Body)
		}
		if len(f.store.List()) != 0 {
			t.Errorf("performed with a damaged ledger")
		}
	})
	t.Run("refusal cannot be recorded", func(t *testing.T) {
		f := newFixture(t, demoGrant)
		f.sabotageLedgerTable(t)
		out := f.handle(boxReq("b", "2h"))
		if out.Status != 500 || !strings.Contains(out.Body["error"].(string), "the ledger failed") {
			t.Fatalf("got %d %v", out.Status, out.Body)
		}
	})
	t.Run("a stored extension that does not apply", func(t *testing.T) {
		f := newFixture(t, demoGrant)
		if _, err := f.led.Extended("demo", "budget", "1.00 USD", "lots", fixedNow); err != nil {
			t.Fatal(err)
		}
		out := f.handle(boxReq("b", ""))
		if out.Status != 500 || !strings.Contains(out.Body["error"].(string), "extensions do not apply") {
			t.Fatalf("got %d %v", out.Status, out.Body)
		}
		if len(f.store.List()) != 0 {
			t.Errorf("performed under an unreadable grant")
		}
	})
}

// The broker's mutex: N concurrent requests against a budget that fits exactly K perform exactly K.
func TestConcurrentBudget(t *testing.T) {
	const n, k = 8, 3
	cost := standin.Price(time.Hour)
	f := newFixture(t, grantText("demo", grants.FormatMoney(k*cost), "1h", "100", "8080"))
	outs := make([]Outcome, n)
	var wg sync.WaitGroup
	for i := range n {
		wg.Add(1)
		go func() {
			defer wg.Done()
			outs[i] = f.handle(boxReq(fmt.Sprintf("box-%d", i), ""))
		}()
	}
	wg.Wait()
	performed, refused := 0, 0
	for _, o := range outs {
		switch {
		case o.Status == 200:
			performed++
		case o.Status == 403 && o.Body["limit"].(map[string]string)["name"] == "budget":
			refused++
		default:
			t.Errorf("unexpected outcome %d %v", o.Status, o.Body)
		}
	}
	if performed != k || refused != n-k {
		t.Errorf("performed %d, refused %d; want %d and %d", performed, refused, k, n-k)
	}
	if boxes := f.store.List(); len(boxes) != k {
		t.Errorf("stand-in record has %d boxes, want %d", len(boxes), k)
	}
	if spent, _ := f.led.Spent("demo"); spent != k*cost {
		t.Errorf("spent %d, want %d", spent, k*cost)
	}
}

// With no clock set, the broker uses the wall clock (UTC).
func TestNilNowUsesWallClock(t *testing.T) {
	f := newFixture(t, demoGrant)
	f.b.Now = nil
	start := time.Now().Add(-time.Second)
	f.handle(boxReq("b", "2h"))
	r := f.rows(t)[0]
	if r.At.Before(start.Truncate(time.Second)) {
		t.Errorf("row at %v, before the request at %v", r.At, start)
	}
}
