// Package reaper is Adele's reaper (feature 004, slice 1; spec FR-24..FR-28): it destroys resources whose
// time-to-live has expired, with the credential the agent never sees, and records each reap in the ledger.
// It runs in Adele's own container, so nothing the agent does — ending its session, stopping or removing
// its container — starts, stops or delays it (P4).
//
// A reap's outcome is decided from the provider's own record read back after the delete, never from the
// delete's answer (cross-stack P004), and the record is read before it too, so a later box that reuses an
// expired box's name is never deleted (D-11).
package reaper

import (
	"context"
	"errors"
	"fmt"
	"io"
	"sync"
	"time"

	"timelike/adele/internal/broker"
	"timelike/adele/internal/ledger"
)

// Defaults (spec D-12). Each is an environment setting of `adeled serve`; compose sets none.
const (
	DefaultInterval = 5 * time.Second
	DefaultPasses   = 5
	DefaultAttempts = 3
	MaxWait         = 5 * time.Minute
)

// Provider is the capability's own record and its delete: the stand-in in slice 1; from feature 13 also the
// daemon's labelled environments (broker.EnvProvider).
type Provider interface {
	List(ctx context.Context) ([]broker.Box, error)
	Delete(ctx context.Context, name string) error
}

// described is a Provider that names its record and what it holds, for the reap's cause. One that does not is
// the stand-in: "the stand-in's record", "box".
type described interface {
	Record() string
	Noun() string
	Holder() string
}

// Reaper holds what a pass needs. Zero values take the defaults.
type Reaper struct {
	Ledger    *ledger.Ledger
	Provider  Provider            // the provider for any capability not in Providers
	Providers map[string]Provider // by capability (feature 13: docker.compose)
	Now       func() time.Time
	Sleep     func(time.Duration) // between delete attempts; tests replace it
	Lock      sync.Locker         // the broker's request lock; nil for none (the operator's own process)
	Interval  time.Duration
	Passes    int
	Attempts  int
	Container string // Adele's container, named in the given-up row's command
}

// Result is one reap as recorded.
type Result struct {
	Ref      int64  `json:"ref"`
	Resource string `json:"resource"`
	Grant    string `json:"grant"`
	Session  string `json:"session"`
	Agent    string `json:"agent,omitempty"`
	Outcome  string `json:"outcome"`
	Cause    string `json:"cause"`
	Attempts int    `json:"attempts"`
	ID       int64  `json:"ledger_id,omitempty"` // 0 when another reaper recorded this resource's ending first
	GaveUp   bool   `json:"gave_up,omitempty"`
}

func (r *Reaper) now() time.Time {
	if r.Now == nil {
		return time.Now().UTC()
	}
	return r.Now().UTC()
}

func (r *Reaper) interval() time.Duration {
	if r.Interval <= 0 {
		return DefaultInterval
	}
	return r.Interval
}

func (r *Reaper) passes() int {
	if r.Passes <= 0 {
		return DefaultPasses
	}
	return r.Passes
}

func (r *Reaper) attempts() int {
	if r.Attempts <= 0 {
		return DefaultAttempts
	}
	return r.Attempts
}

func (r *Reaper) container() string {
	if r.Container == "" {
		return broker.DefaultContainer
	}
	return r.Container
}

// Wait is how long a due row with failures waits after its last failed pass: the interval doubled per
// failure after the first, at most MaxWait (FR-25).
func (r *Reaper) Wait(failures int) time.Duration {
	w := r.interval()
	for i := 1; i < failures && w < MaxWait; i++ {
		w *= 2
	}
	return min(w, MaxWait)
}

// OperatorCommand is the given-up row's remedy (FR-28).
func (r *Reaper) OperatorCommand() string {
	return "docker exec " + r.container() + " adeled reap"
}

// Pass reaps every due row once and returns what it recorded, in expiry order. The serving reaper calls
// it with force false: a given-up row is skipped, and so is one still inside its wait. The operator's
// `adeled reap` calls it with force true: every due row, now (FR-28).
func (r *Reaper) Pass(ctx context.Context, force bool) ([]Result, error) {
	now := r.now()
	due, err := r.Ledger.Due(now)
	if err != nil {
		return nil, err
	}
	var out []Result
	for _, d := range due {
		if !force && (d.Failures >= r.passes() || (d.Failures > 0 && now.Before(d.LastFailure.Add(r.Wait(d.Failures))))) {
			continue
		}
		if err := ctx.Err(); err != nil {
			return out, err
		}
		res, err := r.reap(ctx, d)
		if err != nil {
			return out, err
		}
		out = append(out, res)
	}
	return out, nil
}

func (r *Reaper) reap(ctx context.Context, d ledger.Due) (Result, error) {
	row := d.Row
	outcome, cause, attempts := r.destroy(ctx, row)
	if err := ctx.Err(); err != nil {
		// Adele is stopping: whatever this pass saw was cut short by her, not by the provider, so nothing is
		// recorded. The row stays due, and her next start reaps it from the ledger (Scenario 7).
		return Result{Ref: row.ID, Resource: row.Resource}, err
	}
	res := Result{Ref: row.ID, Resource: row.Resource, Grant: row.Grant, Session: row.Session, Agent: row.Agent,
		Outcome: outcome, Cause: cause, Attempts: attempts}
	if outcome == ledger.OutcomeReapFailed && d.Failures+1 >= r.passes() {
		res.GaveUp = true
		res.Cause += fmt.Sprintf("; gave up after %d failed passes — the operator retries: %s",
			d.Failures+1, r.OperatorCommand())
	}
	// The broker's lock is held for the ledger write alone, so a request's check sees the ending or not, never
	// half of it. Never across the provider's calls and the waits between attempts: a request then waited
	// out a faulted reap's retries (feedback 12-20261016-174206, E). A name reused meanwhile is a later box,
	// which the same-box check leaves alone, as it does for the operator's `adeled reap`, which has no lock.
	if r.Lock != nil {
		r.Lock.Lock()
	}
	id, wrote, err := r.Ledger.Reap(row.ID, res.Outcome, res.Cause, res.Attempts, r.now())
	if r.Lock != nil {
		r.Lock.Unlock()
	}
	if err != nil {
		return res, err
	}
	if wrote {
		res.ID = id
	}
	return res, nil
}

func (r *Reaper) provider(capability string) Provider {
	if p, ok := r.Providers[capability]; ok {
		return p
	}
	return r.Provider
}

// destroy deletes row's resource and decides the outcome from the provider's record (FR-26).
func (r *Reaper) destroy(ctx context.Context, row ledger.Row) (outcome, cause string, attempts int) {
	const vantage = "from Adele's container" // P001: a reachability claim says where it was made
	prov := r.provider(row.Capability)
	record, noun, holder := "the stand-in's record", "box", "the stand-in"
	if d, ok := prov.(described); ok {
		record, noun, holder = d.Record(), d.Noun(), d.Holder()
	}
	if prov == nil {
		return ledger.OutcomeReapFailed, "Adele has no provider for " + row.Capability + " to reap it with", 0
	}
	before, err := prov.List(ctx)
	if err != nil {
		return ledger.OutcomeReapFailed, fmt.Sprintf("%s could not be read %s before the delete: %v",
			record, vantage, err), 0
	}
	box, held := find(before, row.Resource)
	if !held {
		return ledger.OutcomeGone, "already gone: no " + noun + " " + row.Resource + " in " + record + " before the delete", 0
	}
	if !sameBox(box, row) {
		return ledger.OutcomeGone, fmt.Sprintf("already gone: the %s named %s in %s is a later one "+
			"(created %s), and was not touched", noun, row.Resource, record, box.CreatedAt.UTC().Format(time.RFC3339)), 0
	}
	var lastErr error
	noSuch := false
	for attempts < r.attempts() {
		attempts++
		err := prov.Delete(ctx, row.Resource)
		if err == nil {
			lastErr = nil
			break
		}
		if errors.Is(err, broker.ErrNoSuchResource) {
			noSuch, lastErr = true, nil
			break
		}
		lastErr = err
		if attempts < r.attempts() {
			r.sleep(time.Duration(attempts) * time.Second) // 1 s, then 2 s (D-12)
		}
	}
	after, err := prov.List(ctx)
	if err != nil {
		return ledger.OutcomeReapFailed, fmt.Sprintf("%s could not be read back %s after the delete: %v",
			record, vantage, err), attempts
	}
	if box, still := find(after, row.Resource); still && sameBox(box, row) {
		if lastErr != nil {
			return ledger.OutcomeReapFailed, fmt.Sprintf("the delete failed %d times %s: %v; the %s is still in %s",
				attempts, vantage, lastErr, noun, record), attempts
		}
		return ledger.OutcomeReapFailed, "the delete answered, but the " + noun + " is still in " + record + " read back", attempts
	}
	switch {
	case noSuch:
		return ledger.OutcomeGone, "already gone: " + holder + " had no " + noun + " " + row.Resource + " when the delete ran, and its record agrees", attempts
	case lastErr != nil:
		return ledger.OutcomeReaped, fmt.Sprintf("the delete's answer was lost (%v), but the %s is absent from %s read back", lastErr, noun, record), attempts
	}
	return ledger.OutcomeReaped, "deleted; absent from " + record + " read back", attempts
}

func (r *Reaper) sleep(d time.Duration) {
	if r.Sleep != nil {
		r.Sleep(d)
		return
	}
	time.Sleep(d)
}

func find(boxes []broker.Box, name string) (broker.Box, bool) {
	for _, b := range boxes {
		if b.Name == name {
			return b, true
		}
	}
	return broker.Box{}, false
}

// sameBox: the box the row created is the one whose creation plus lifetime is the row's expiry (Adele
// records expires_at as created_at + ttl, truncated to the second).
func sameBox(b broker.Box, row ledger.Row) bool {
	if row.ExpiresAt == nil {
		return false
	}
	exp := b.CreatedAt.UTC().Add(time.Duration(b.TTLSeconds) * time.Second).Truncate(time.Second)
	return exp.Equal(row.ExpiresAt.UTC())
}

// Run reaps until ctx ends: one pass at once (so a restarted Adele reaps what an earlier one left), then
// one every interval. Each recorded reap is one line on log (`docker logs timelike-adele`). A pass that
// fails is logged and retried at the next tick; Run itself never stops early.
func (r *Reaper) Run(ctx context.Context, log io.Writer) {
	t := time.NewTicker(r.interval())
	defer t.Stop()
	for {
		results, err := r.Pass(ctx, false)
		for _, res := range results {
			fmt.Fprintln(log, "adeled: reap: "+Line(res))
		}
		if err != nil && ctx.Err() == nil {
			fmt.Fprintf(log, "adeled: reap pass failed: %v (retried at the next pass)\n", err)
		}
		select {
		case <-ctx.Done():
			return
		case <-t.C:
		}
	}
}

// Line is one result in words, as the log and `adeled reap` print it.
func Line(res Result) string {
	s := fmt.Sprintf("%s %s (ledger #%d, grant %s, session %s", res.Outcome, res.Resource, res.Ref, res.Grant, res.Session)
	if res.Agent != "" {
		s += ", agent " + res.Agent
	}
	s += "): " + res.Cause
	if res.ID != 0 {
		s += fmt.Sprintf(" — recorded as #%d", res.ID)
	} else {
		s += " — not recorded: another reap recorded its ending first"
	}
	return s
}
