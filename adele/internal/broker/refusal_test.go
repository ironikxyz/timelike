package broker

import (
	"strings"
	"testing"

	"timelike/adele/internal/grants"
	"timelike/adele/internal/ledger"
	"timelike/adele/internal/standin"
)

type refusalCase struct {
	name                   string
	grants                 string
	setup                  []Request // performed before the refused request
	req                    Request
	limit, allowed, needed string
	extendTo               string
	cost                   int64 // -1: no quote, so no cost recorded
}

func refusalCases() []refusalCase {
	return []refusalCase{
		{name: "ttl", grants: demoGrant, req: boxReq("b", "2h"),
			limit: "ttl", allowed: "1h", needed: "2h", extendTo: "2h", cost: -1},
		{name: "ports", grants: demoGrant, req: boxReq("b", "", 8080, 22),
			limit: "ports", allowed: "8080", needed: "22", extendTo: "22", cost: -1},
		{name: "ports none", grants: grantText("demo", "1.00 USD", "1h", "2", "none"), req: boxReq("b", "", 8080),
			limit: "ports", allowed: "none", needed: "8080", extendTo: "8080", cost: -1},
		{name: "instances", grants: grantText("demo", "1.00 USD", "1h", "1", "8080"),
			setup: []Request{boxReq("a", "")}, req: boxReq("b", ""),
			limit: "instances", allowed: "1", needed: "2", extendTo: "2", cost: -1},
		{name: "budget", grants: grantText("demo", "0.30 USD", "1h", "5", "8080"),
			setup: []Request{boxReq("a", "")}, req: boxReq("b", ""),
			limit: "budget", allowed: "0.05 USD", needed: "0.25 USD", extendTo: "0.50 USD", cost: 25},
		{name: "budget zero", grants: grantText("demo", "0.00 USD", "1h", "5", "8080"), req: boxReq("b", "30m"),
			limit: "budget", allowed: "0.00 USD", needed: "0.13 USD", extendTo: "0.13 USD", cost: 13},
	}
}

// checkRefusal asserts the 403 envelope, the refused ledger row, and that the stand-in's own record
// did not change. It returns the value the extend command names.
func checkRefusal(t *testing.T, f *fixture, out Outcome, grant string, c refusalCase, before []standin.Box) string {
	t.Helper()
	if out.Status != 403 {
		t.Fatalf("status %d, body %v", out.Status, out.Body)
	}
	if out.Body["outcome"] != ledger.OutcomeRefused || out.Body["grant"] != grant || out.Body["performed"] != false {
		t.Errorf("body = %v", out.Body)
	}
	lim := out.Body["limit"].(map[string]string)
	if lim["name"] != c.limit || lim["allowed"] != c.allowed || lim["needed"] != c.needed {
		t.Errorf("limit = %v, want %s/%s/%s", lim, c.limit, c.allowed, c.needed)
	}
	wantExtend := "docker exec timelike-adele adeled extend " + grant + " " + c.limit + " " + c.extendTo
	if out.Body["extend"] != wantExtend {
		t.Errorf("extend = %q, want %q", out.Body["extend"], wantExtend)
	}
	rows := f.rows(t)
	r := rows[len(rows)-1]
	if r.ID != out.Body["ledger_id"].(int64) || r.Outcome != ledger.OutcomeRefused || r.Grant != grant ||
		r.LimitName != c.limit || r.Allowed != c.allowed || r.Needed != c.needed || r.Resource != c.req.Params.Name {
		t.Errorf("ledger row = %+v", r)
	}
	switch {
	case c.cost < 0 && r.CostCents != nil:
		t.Errorf("refused before the quote but cost %d recorded", *r.CostCents)
	case c.cost >= 0 && (r.CostCents == nil || *r.CostCents != c.cost):
		t.Errorf("cost = %v, want %d", r.CostCents, c.cost)
	}
	f.assertUnchanged(t, before)
	prefix := ExtendCommand(DefaultContainer, grant, c.limit, "")
	if !strings.HasPrefix(wantExtend, prefix) {
		t.Fatalf("extend %q lacks prefix %q", wantExtend, prefix)
	}
	return strings.TrimPrefix(out.Body["extend"].(string), prefix)
}

// Each limit refuses with the documented envelope; applying the refusal's own extend value through the
// ledger then makes the identical request perform (FR-11, FR-12, D-4).
func TestRefusalPerLimitThenExtend(t *testing.T) {
	for _, c := range refusalCases() {
		t.Run(c.name, func(t *testing.T) {
			f := newFixture(t, c.grants)
			for _, s := range c.setup {
				f.mustPerform(t, s)
			}
			performed := f.countOutcome(t, ledger.OutcomePerformed)
			before := f.store.List()
			value := checkRefusal(t, f, f.handle(c.req), "demo", c, before)
			if n := f.countOutcome(t, ledger.OutcomePerformed); n != performed {
				t.Errorf("performed rows %d → %d on a refusal", performed, n)
			}

			base, _ := f.b.Grants.Get("demo")
			if _, err := f.led.Extended("demo", c.limit, grants.FormatLimit(base, c.limit), value, fixedNow); err != nil {
				t.Fatalf("extend %s %q: %v", c.limit, value, err)
			}
			if out := f.handle(c.req); out.Status != 200 {
				t.Fatalf("retry after extend: status %d, body %v", out.Status, out.Body)
			}
			if _, ok := f.hasBox(c.req.Params.Name); !ok {
				t.Errorf("retry performed but the stand-in has no %s", c.req.Params.Name)
			}
		})
	}
}

// noBoxGrant cannot be written in a grant file in slice 0 (standin.box is the only known capability and
// capabilities must be non-empty), so it is built directly.
func noBoxGrant(name string, caps ...string) grants.Grant {
	ports, _ := grants.ParsePorts("8080")
	return grants.Grant{Name: name, Capabilities: caps, BudgetCents: 100, TTL: 3600e9, Instances: 2, Ports: ports}
}

// A capabilities refusal against the one grant: the request also exceeds ttl, and capabilities is
// checked first. The listed capability is a placeholder name only this test uses.
func TestRefusalCapabilitiesThenExtend(t *testing.T) {
	f := newFixtureFile(t, &grants.File{Grants: []grants.Grant{noBoxGrant("solo", "other.cap")}})
	c := refusalCase{req: boxReq("b", "2h"), limit: "capabilities", allowed: "other.cap",
		needed: grants.CapStandinBox, extendTo: grants.CapStandinBox, cost: -1}
	value := checkRefusal(t, f, f.handle(c.req), "solo", c, f.store.List())
	if _, err := f.led.Extended("solo", "capabilities", "other.cap", value, fixedNow); err != nil {
		t.Fatalf("extend: %v", err)
	}
	// Now refused on ttl, the next check in order.
	if out := f.handle(c.req); out.Status != 403 || out.Body["limit"].(map[string]string)["name"] != "ttl" {
		t.Fatalf("after capabilities extend: %d %v", out.Status, out.Body)
	}
	if out := f.handle(boxReq("b", "")); out.Status != 200 {
		t.Fatalf("within the extended grant: %d %v", out.Status, out.Body)
	}
}

// A grant with no capabilities at all is refused on capabilities, not failed with a 500.
func TestRefusalCapabilitiesEmptyList(t *testing.T) {
	f := newFixtureFile(t, &grants.File{Grants: []grants.Grant{noBoxGrant("solo")}})
	out := f.handle(boxReq("b", ""))
	if out.Status != 403 {
		t.Fatalf("status %d (want 403): %v", out.Status, out.Body)
	}
	lim := out.Body["limit"].(map[string]string)
	if lim["name"] != "capabilities" || lim["allowed"] == "" || lim["needed"] != grants.CapStandinBox {
		t.Errorf("limit = %v, want capabilities with a non-empty allowed (e.g. none)", lim)
	}
	if len(f.store.List()) != 0 {
		t.Errorf("performed on a capabilities refusal")
	}
}

// The first failing check in data-model order is the one reported, and the budget check's quote is
// never taken when an earlier check fails.
func TestCheckOrder(t *testing.T) {
	cases := []struct {
		name, grants string
		req          Request
		want         string
		quoted       bool
	}{
		{"ttl before budget", grantText("demo", "0.00 USD", "1h", "5", "8080"), boxReq("b", "2h"), "ttl", false},
		{"ttl before ports", demoGrant, boxReq("b", "2h", 22), "ttl", false},
		{"ports before instances", grantText("demo", "1.00 USD", "1h", "0", "8080"), boxReq("b", "", 22), "ports", false},
		{"instances before budget", grantText("demo", "0.00 USD", "1h", "0", "8080"), boxReq("b", ""), "instances", false},
		{"budget last", grantText("demo", "0.00 USD", "1h", "1", "8080"), boxReq("b", "", 8080), "budget", true},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			f := newFixture(t, c.grants)
			up := f.count()
			before := f.store.List()
			out := f.handle(c.req)
			if out.Status != 403 || out.Body["limit"].(map[string]string)["name"] != c.want {
				t.Fatalf("got %d %v, want refusal on %s", out.Status, out.Body, c.want)
			}
			if q := up.quotes.Load(); (q > 0) != c.quoted {
				t.Errorf("quotes = %d, want quoted=%v", q, c.quoted)
			}
			if up.creates.Load() != 0 {
				t.Errorf("Create called on a refusal")
			}
			f.assertUnchanged(t, before)
		})
	}
}

// The extend command names the container that serves this broker.
func TestRefusalNamesContainer(t *testing.T) {
	f := newFixture(t, demoGrant)
	f.b.Container = "adele-x"
	out := f.handle(boxReq("b", "2h"))
	if out.Body["extend"] != "docker exec adele-x adeled extend demo ttl 2h" {
		t.Errorf("extend = %v", out.Body["extend"])
	}
}
