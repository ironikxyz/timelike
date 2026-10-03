package broker

import (
	"context"
	"fmt"
	"net/http"
	"strconv"
	"strings"
	"time"

	"timelike/adele/internal/grants"
	"timelike/adele/internal/ledger"
)

// refusal is one limit the request exceeds: its name, what the grant allows, what the request needs,
// and the extension value that would make this request allowed (contracts/adele-http.md).
type refusal struct {
	limit, allowed, needed, extendTo string
	cost                             *int64
}

// checkAndPerform runs the checks in data-model order — capability, ttl, ports, instances, budget —
// and performs only when every one passes. The budget check needs the stand-in's quote, which is a
// read: nothing is performed before the last check passes.
func (b *Broker) checkAndPerform(ctx context.Context, req Request, g grants.Grant) Outcome {
	ttl := g.TTL
	if req.Params.TTL != "" {
		ttl, _ = grants.ParseTTL(req.Params.TTL) // validated already
	}
	if r := checkStatic(req, g, ttl); r != nil {
		return b.refuse(req, g.Name, *r)
	}
	live, err := b.Ledger.Live(g.Name)
	if err != nil {
		return ledgerFailed(err)
	}
	if live+1 > g.Instances {
		n := strconv.Itoa(live + 1)
		return b.refuse(req, g.Name, refusal{grants.LimitInstances, strconv.Itoa(g.Instances), n, n, nil})
	}
	cost, err := b.Upstream.Quote(ctx, ttl)
	if err != nil {
		return upstreamFailed(err)
	}
	spent, err := b.Ledger.Spent(g.Name)
	if err != nil {
		return ledgerFailed(err)
	}
	if spent+cost > g.BudgetCents {
		remaining := max(g.BudgetCents-spent, 0)
		return b.refuse(req, g.Name, refusal{grants.LimitBudget, grants.FormatMoney(remaining),
			grants.FormatMoney(cost), grants.FormatMoney(spent + cost), &cost})
	}
	return b.perform(ctx, req, g.Name, ttl)
}

func checkStatic(req Request, g grants.Grant, ttl time.Duration) *refusal {
	if !g.Allows(req.Capability) {
		allowed := strings.Join(g.Capabilities, ", ")
		if allowed == "" {
			allowed = "none" // as an empty port set prints; the ledger requires a value
		}
		return &refusal{grants.LimitCapabilities, allowed, req.Capability, req.Capability, nil}
	}
	if ttl > g.TTL {
		d := grants.FormatDuration(ttl)
		return &refusal{grants.LimitTTL, grants.FormatDuration(g.TTL), d, d, nil}
	}
	for _, p := range req.Params.Ports {
		if !g.Ports.Contains(p) {
			n := strconv.Itoa(p)
			return &refusal{grants.LimitPorts, g.Ports.String(), n, n, nil}
		}
	}
	return nil
}

func (b *Broker) refuse(req Request, grant string, r refusal) Outcome {
	extend := ExtendCommand(b.container(), grant, r.limit, r.extendTo)
	id, err := b.Ledger.Refused(ledger.Row{
		At: b.now(), Grant: grant, Session: req.Session, Capability: req.Capability, Action: req.Action,
		Resource: req.Params.Name, CostCents: r.cost, LimitName: r.limit, Allowed: r.allowed, Needed: r.needed,
	})
	if err != nil {
		return ledgerFailed(err)
	}
	return Outcome{http.StatusForbidden, map[string]any{
		"outcome": ledger.OutcomeRefused, "grant": grant,
		"limit":  map[string]string{"name": r.limit, "allowed": r.allowed, "needed": r.needed},
		"extend": extend, "performed": false, "ledger_id": id,
	}}
}

func (b *Broker) perform(ctx context.Context, req Request, grant string, ttl time.Duration) Outcome {
	ports := req.Params.Ports
	if ports == nil {
		ports = []int{}
	}
	made, err := b.Upstream.Create(ctx, req.Params.Name, ttl, ports)
	if err != nil {
		return upstreamFailed(err)
	}
	created := made.CreatedAt.UTC()
	if created.IsZero() {
		created = b.now()
	}
	expires := created.Add(ttl).Truncate(time.Second)
	cost := made.CostCents
	undo := undoFor(req)
	id, err := b.Ledger.Performed(ledger.Row{
		At: b.now(), Grant: grant, Session: req.Session, Capability: req.Capability, Action: req.Action,
		Resource: made.Name, CostCents: &cost, ExpiresAt: &expires, Undo: undo,
	})
	if err != nil {
		// Performed upstream but not recorded: say so plainly; the operator reconciles from the
		// stand-in's own record. This is the one state that must never be silent (P5).
		return Outcome{http.StatusInternalServerError, map[string]any{
			"error":     fmt.Sprintf("box %s was created but the ledger write failed: %v", made.Name, err),
			"performed": true, "remediation": "the operator records or deletes it: docker exec " + b.container() + " adeled ledger",
		}}
	}
	return Outcome{http.StatusOK, map[string]any{
		"outcome": ledger.OutcomePerformed, "grant": grant, "resource": made.Name, "cost_cents": cost,
		"expires_at": expires.Format(time.RFC3339), "ledger_id": id, "undo": undo,
	}}
}

func ledgerFailed(err error) Outcome {
	return fail(http.StatusInternalServerError, "the ledger failed: "+err.Error(),
		"nothing was performed; the operator checks Adele's log: docker logs "+DefaultContainer, nil)
}
