package broker

import (
	"reflect"
	"strings"
	"testing"

	"timelike/adele/internal/grants"
)

var twoGrants = grantText("alpha", "1.00 USD", "1h", "2", "8080") + "\n" + grantText("beta", "1.00 USD", "1h", "2", "8080")

// assertNothing fails unless the ledger is empty and the stand-in's record has no boxes.
func assertNothing(t *testing.T, f *fixture) {
	t.Helper()
	if rows := f.rows(t); len(rows) != 0 {
		t.Errorf("ledger has %d rows, want none: %+v", len(rows), rows)
	}
	if boxes := f.store.List(); len(boxes) != 0 {
		t.Errorf("stand-in record has %d boxes, want none", len(boxes))
	}
}

// FR-9: the grant named, else the single grant that allows the capability.
func TestGrantChoice(t *testing.T) {
	t.Run("named grant is used", func(t *testing.T) {
		f := newFixture(t, twoGrants)
		req := boxReq("b", "")
		req.Grant = "beta"
		out := f.mustPerform(t, req)
		if out.Body["grant"] != "beta" || f.rows(t)[0].Grant != "beta" {
			t.Errorf("body %v, row %+v: want grant beta", out.Body, f.rows(t)[0])
		}
	})
	t.Run("unknown named grant is 404 with the list", func(t *testing.T) {
		f := newFixture(t, twoGrants)
		req := boxReq("b", "")
		req.Grant = "gamma"
		out := f.handle(req)
		if out.Status != 404 || out.Body["error"] != "no grant named gamma" ||
			!reflect.DeepEqual(out.Body["grants"], []string{"alpha", "beta"}) {
			t.Errorf("got %d %v", out.Status, out.Body)
		}
		assertNothing(t, f)
	})
	t.Run("two grants allow is 400 listing them", func(t *testing.T) {
		f := newFixture(t, twoGrants)
		out := f.handle(boxReq("b", ""))
		if out.Status != 400 || !reflect.DeepEqual(out.Body["grants"], []string{"alpha", "beta"}) ||
			!strings.Contains(out.Body["error"].(string), "more than one grant") {
			t.Errorf("got %d %v", out.Status, out.Body)
		}
		assertNothing(t, f)
	})
	t.Run("none allow among several is 400", func(t *testing.T) {
		f := newFixtureFile(t, &grants.File{Grants: []grants.Grant{noBoxGrant("x", "other.cap"), noBoxGrant("y", "other.cap")}})
		out := f.handle(boxReq("b", ""))
		if out.Status != 400 || !reflect.DeepEqual(out.Body["grants"], []string{"x", "y"}) ||
			!strings.Contains(out.Body["error"].(string), "no grant allows") {
			t.Errorf("got %d %v", out.Status, out.Body)
		}
		assertNothing(t, f)
	})
	t.Run("the single allowing grant among several is chosen", func(t *testing.T) {
		ok, _ := grants.Parse("g", strings.NewReader(grantText("box", "1.00 USD", "1h", "2", "8080")))
		f := newFixtureFile(t, &grants.File{Grants: []grants.Grant{noBoxGrant("x", "other.cap"), ok.Grants[0]}})
		if out := f.mustPerform(t, boxReq("b", "")); out.Body["grant"] != "box" {
			t.Errorf("grant = %v, want box", out.Body["grant"])
		}
	})
	// none allow + one grant → 403 capabilities against it: TestRefusalCapabilitiesThenExtend.
}

// Malformed requests are 400 before any grant is chosen: nothing quoted, performed or recorded.
func TestValidation(t *testing.T) {
	cases := []struct {
		name string
		mod  func(*Request)
		want string
	}{
		{"empty session", func(r *Request) { r.Session = "" }, "bad session"},
		{"session with space", func(r *Request) { r.Session = "a b" }, "bad session"},
		{"session too long", func(r *Request) { r.Session = strings.Repeat("s", 65) }, "bad session"},
		{"unknown capability", func(r *Request) { r.Capability = "standin.vm" }, "knows no capability"},
		{"action delete", func(r *Request) { r.Action = "delete" }, "has no action"},
		{"empty name", func(r *Request) { r.Params.Name = "" }, "bad name"},
		{"uppercase name", func(r *Request) { r.Params.Name = "Web" }, "bad name"},
		{"name too long", func(r *Request) { r.Params.Name = "a" + strings.Repeat("b", 63) }, "bad name"},
		{"port 0", func(r *Request) { r.Params.Ports = []int{8080, 0} }, "port 0 is out of range"},
		{"port 65536", func(r *Request) { r.Params.Ports = []int{65536} }, "port 65536 is out of range"},
		{"ttl unparsable", func(r *Request) { r.Params.TTL = "soon" }, "bad ttl"},
		{"ttl below 1m", func(r *Request) { r.Params.TTL = "30s" }, "bad ttl"},
		{"ttl above 720h", func(r *Request) { r.Params.TTL = "721h" }, "bad ttl"},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			f := newFixture(t, demoGrant)
			up := f.count()
			req := boxReq("b", "")
			c.mod(&req)
			out := f.handle(req)
			if out.Status != 400 || !strings.Contains(out.Body["error"].(string), c.want) || out.Body["remediation"] == "" {
				t.Errorf("got %d %v, want 400 %q", out.Status, out.Body, c.want)
			}
			if up.quotes.Load()+up.creates.Load() != 0 {
				t.Errorf("upstream called on a malformed request")
			}
			assertNothing(t, f)
		})
	}
}
