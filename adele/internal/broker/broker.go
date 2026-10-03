// Package broker is Adele's request path (feature 004, slice 0): choose the grant, check the request
// against it in a fixed order, and either perform it with the credential the agent never sees or
// refuse it before anything is performed — recording both in the ledger (spec FR-8..FR-16).
package broker

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"regexp"
	"strings"
	"sync"
	"time"

	"timelike/adele/internal/grants"
	"timelike/adele/internal/ledger"
)

// DefaultContainer is Adele's fixed container name; the extend command names it (spec D-4).
const DefaultContainer = "timelike-adele"

var nameRe = regexp.MustCompile(`^[a-z][a-z0-9-]{0,62}$`)
var sessionRe = regexp.MustCompile(`^[A-Za-z0-9._-]{1,64}$`)

// Request is what the agent's client sends (data-model § Request).
type Request struct {
	Session    string `json:"session"`
	Grant      string `json:"grant"`
	Capability string `json:"capability"`
	Action     string `json:"action"`
	Params     Params `json:"params"`
}

// Params are the stand-in box's parameters. TTL is empty for "the grant's ttl".
type Params struct {
	Name  string `json:"name"`
	TTL   string `json:"ttl"`
	Ports []int  `json:"ports"`
}

// Upstream is the capability Adele performs with her credential: the stand-in in slice 0.
type Upstream interface {
	Quote(ctx context.Context, ttl time.Duration) (int64, error)
	Create(ctx context.Context, name string, ttl time.Duration, ports []int) (Created, error)
}

// Created is the upstream's account of a resource it made.
type Created struct {
	Name      string
	CreatedAt time.Time
	CostCents int64
}

// Broker holds everything a request needs. Requests are serialised: check-then-perform must not
// interleave, or two requests could each fit a budget that only one of them fits.
type Broker struct {
	Grants    *grants.File
	Ledger    *ledger.Ledger
	Upstream  Upstream
	Now       func() time.Time
	Container string
	Revision  string
	mu        sync.Mutex
}

// Outcome is the HTTP status and JSON body for one request (contracts/adele-http.md).
type Outcome struct {
	Status int
	Body   map[string]any
}

func fail(status int, what, remedy string, names []string) Outcome {
	body := map[string]any{"error": what}
	if remedy != "" {
		body["remediation"] = remedy
	}
	if names != nil {
		body["grants"] = names
	}
	return Outcome{status, body}
}

// Handle decides one request. It never panics on agent input and never performs before checking.
func (b *Broker) Handle(ctx context.Context, req Request) Outcome {
	b.mu.Lock()
	defer b.mu.Unlock()
	if out, bad := validate(req); bad {
		return out
	}
	g, out, ok := b.choose(req)
	if !ok {
		return out
	}
	eff, err := b.effective(g)
	if err != nil {
		return fail(http.StatusInternalServerError, "the grant's extensions do not apply: "+err.Error(),
			"the operator checks: docker exec "+b.container()+" adeled ledger", nil)
	}
	return b.checkAndPerform(ctx, req, eff)
}

func validate(req Request) (Outcome, bool) {
	switch {
	case !sessionRe.MatchString(req.Session):
		return fail(http.StatusBadRequest, fmt.Sprintf("bad session id %q", req.Session),
			"TIMELIKE_SESSION must match ^[A-Za-z0-9._-]{1,64}$", nil), true
	case !grants.KnownCapabilities[req.Capability]:
		return fail(http.StatusBadRequest, fmt.Sprintf("Adele knows no capability %q", req.Capability),
			"slice 0 knows one: "+grants.CapStandinBox, nil), true
	case req.Action != "create":
		return fail(http.StatusBadRequest, fmt.Sprintf("%s has no action %q", req.Capability, req.Action),
			"the action is create", nil), true
	case !nameRe.MatchString(req.Params.Name):
		return fail(http.StatusBadRequest, fmt.Sprintf("bad name %q", req.Params.Name),
			"a name is a lowercase letter, then up to 62 of a-z, 0-9 and -", nil), true
	}
	for _, p := range req.Params.Ports {
		if p < 1 || p > grants.MaxPort {
			return fail(http.StatusBadRequest, fmt.Sprintf("port %d is out of range", p), "ports are 1 to 65535", nil), true
		}
	}
	if req.Params.TTL != "" {
		if _, err := grants.ParseTTL(req.Params.TTL); err != nil {
			return fail(http.StatusBadRequest, fmt.Sprintf("bad ttl %q: %v", req.Params.TTL, err), "e.g. 30m or 1h", nil), true
		}
	}
	return Outcome{}, false
}

// choose applies FR-9: the grant named, else the single grant that allows the capability.
func (b *Broker) choose(req Request) (grants.Grant, Outcome, bool) {
	names := b.Grants.Names()
	if req.Grant != "" {
		g, ok := b.Grants.Get(req.Grant)
		if !ok {
			return g, fail(http.StatusNotFound, "no grant named "+req.Grant, "use one of these", names), false
		}
		return g, Outcome{}, true
	}
	var allowing []grants.Grant
	for _, g := range b.Grants.Grants {
		if g.Allows(req.Capability) {
			allowing = append(allowing, g)
		}
	}
	switch {
	case len(allowing) == 1:
		return allowing[0], Outcome{}, true
	case len(allowing) > 1:
		return grants.Grant{}, fail(http.StatusBadRequest, "more than one grant allows "+req.Capability,
			"name one with --grant", grantNames(allowing)), false
	case len(b.Grants.Grants) == 1:
		return b.Grants.Grants[0], Outcome{}, true // refused below, on capabilities, against that grant
	}
	return grants.Grant{}, fail(http.StatusBadRequest, "no grant allows "+req.Capability,
		"name a grant with --grant; the refusal will name the operator's command that extends it", names), false
}

func grantNames(gs []grants.Grant) []string {
	out := make([]string, len(gs))
	for i, g := range gs {
		out[i] = g.Name
	}
	return out
}

func (b *Broker) effective(g grants.Grant) (grants.Grant, error) {
	exts, err := b.Ledger.Extensions(g.Name)
	if err != nil {
		return g, err
	}
	conv := make([]grants.Extension, len(exts))
	for i, e := range exts {
		conv[i] = grants.Extension{Grant: e.Grant, Limit: e.Limit, Value: e.Value}
	}
	return grants.Effective(g, conv)
}

func (b *Broker) container() string {
	if b.Container == "" {
		return DefaultContainer
	}
	return b.Container
}

func (b *Broker) now() time.Time {
	if b.Now == nil {
		return time.Now().UTC()
	}
	return b.Now().UTC()
}

// ExtendCommand is the operator's exact command (spec D-4); the value is printed unquoted, and
// `adeled extend` joins its remaining arguments, so `2.00 USD` needs no quoting.
func ExtendCommand(container, grant, limit, value string) string {
	return fmt.Sprintf("docker exec %s adeled extend %s %s %s", container, grant, limit, value)
}

func undoFor(req Request) string {
	raw, _ := json.Marshal(map[string]any{
		"capability": req.Capability, "action": "delete", "params": map[string]string{"name": req.Params.Name},
	})
	return string(raw)
}

var errUpstream = errors.New("upstream")

func upstreamFailed(err error) Outcome {
	return Outcome{http.StatusBadGateway, map[string]any{
		"error": "stand-in failed: " + strings.TrimPrefix(err.Error(), errUpstream.Error()+": "), "performed": false,
	}}
}
