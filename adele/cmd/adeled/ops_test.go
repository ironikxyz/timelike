package main

import (
	"encoding/json"
	"path/filepath"
	"reflect"
	"sort"
	"strings"
	"testing"
	"time"

	"timelike/adele/internal/grants"
	"timelike/adele/internal/ledger"
)

func openLedger(t *testing.T, f *fixture) *ledger.Ledger {
	t.Helper()
	led, err := ledger.Open(f.vars["ADELE_DB"])
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { led.Close() })
	return led
}

func TestExtendRefusals(t *testing.T) {
	cases := []struct {
		name string
		args []string
		code int
		want string
	}{
		{"no args", nil, exitUsage, "usage: adeled extend GRANT LIMIT VALUE"},
		{"two args", []string{"demo", "budget"}, exitUsage, "usage: adeled extend"},
		{"unknown grant", []string{"nosuch", "budget", "2.00", "USD"}, exitNotFound, "no grant named nosuch — the grants are: demo, other"},
		{"budget abc", []string{"demo", "budget", "abc"}, exitUsage, "adeled: "},
		{"ttl 0s", []string{"demo", "ttl", "0s"}, exitUsage, "out of range"},
		{"ports 70000", []string{"demo", "ports", "70000"}, exitUsage, "adeled: "},
		{"ports list", []string{"demo", "ports", "1,2"}, exitUsage, "not one port or range"},
		{"instances -1", []string{"demo", "instances", "-1"}, exitUsage, "negative instances"},
		{"unknown limit", []string{"demo", "speed", "9"}, exitUsage, `unknown limit "speed"`},
		{"unknown capability", []string{"demo", "capabilities", "cloud.vm"}, exitUsage, "adeled: "},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			f := newFixture(t)
			code, out, errs := f.run(append([]string{"extend"}, tc.args...)...)
			if code != tc.code || out != "" || !strings.Contains(errs, tc.want) {
				t.Errorf("code %d (want %d), stdout %q, stderr %q (want %q)", code, tc.code, out, errs, tc.want)
			}
			// Nothing was recorded for a refused extension.
			rows, err := openLedger(t, f).Rows()
			if err != nil || len(rows) != 0 {
				t.Errorf("ledger after refusal: %d rows, %v", len(rows), err)
			}
		})
	}
}

func TestExtendBudget(t *testing.T) {
	f := newFixture(t)
	// The value as two arguments, as the refusal prints it unquoted.
	code, out, errs := f.run("extend", "demo", "budget", "2.00", "USD")
	if code != exitOK || out != "extended demo budget: 1.00 USD → 2.00 USD (recorded in the ledger)\n" || errs != "" {
		t.Fatalf("code %d, stdout %q, stderr %q", code, out, errs)
	}
	led := openLedger(t, f)
	rows, err := led.Rows()
	if err != nil || len(rows) != 1 {
		t.Fatalf("rows %d, %v", len(rows), err)
	}
	r := rows[0]
	if r.Outcome != ledger.OutcomeExtended || r.Grant != "demo" || r.LimitName != "budget" ||
		r.Allowed != "1.00 USD" || r.Needed != "2.00 USD" {
		t.Errorf("extended row: %+v", r)
	}
	exts, err := led.Extensions("demo")
	if err != nil || len(exts) != 1 || exts[0].Limit != "budget" || exts[0].Value != "2.00 USD" {
		t.Errorf("extensions: %+v, %v", exts, err)
	}
	if other, _ := led.Extensions("other"); len(other) != 0 {
		t.Errorf("the other grant was extended: %+v", other)
	}

	// A second extension starts from the first one's value, not the file's.
	code, out, _ = f.run("extend", "demo", "budget", "3.50 USD")
	if code != exitOK || out != "extended demo budget: 2.00 USD → 3.50 USD (recorded in the ledger)\n" {
		t.Errorf("second: code %d, stdout %q", code, out)
	}
	rows, _ = led.Rows()
	if len(rows) != 2 || rows[1].Allowed != "2.00 USD" || rows[1].Needed != "3.50 USD" {
		t.Errorf("second row: %+v", rows)
	}
}

func TestExtendAddsAndSets(t *testing.T) {
	f := newFixture(t)
	steps := []struct {
		args []string
		out  string
	}{
		{[]string{"demo", "ports", "9000-9010"}, "extended demo ports: 8080 → 8080, 9000-9010"},
		{[]string{"demo", "ttl", "2h"}, "extended demo ttl: 1h → 2h"},
		{[]string{"demo", "instances", "5"}, "extended demo instances: 2 → 5"},
		{[]string{"demo", "capabilities", "standin.box"}, "extended demo capabilities: standin.box → standin.box"},
		{[]string{"other", "ports", "22"}, "extended other ports: none → 22"},
	}
	for _, s := range steps {
		code, out, errs := f.run(append([]string{"extend"}, s.args...)...)
		if code != exitOK || out != s.out+" (recorded in the ledger)\n" {
			t.Errorf("%v: code %d, stdout %q, stderr %q", s.args, code, out, errs)
		}
	}
	led := openLedger(t, f)
	file, err := grants.Load(f.vars["ADELE_GRANTS"])
	if err != nil {
		t.Fatal(err)
	}
	base, _ := file.Get("demo")
	eff, err := effective(led, base)
	if err != nil {
		t.Fatal(err)
	}
	if eff.Ports.String() != "8080, 9000-9010" || !eff.Ports.Contains(8080) || !eff.Ports.Contains(9005) ||
		eff.TTL != 2*time.Hour || eff.Instances != 5 {
		t.Errorf("effective demo: %+v", eff)
	}
}

func TestExtendFailures(t *testing.T) {
	t.Run("malformed grants", func(t *testing.T) {
		f := newFixture(t)
		bad := f.write("grants.conf", "[grant demo]\n")
		code, _, errs := f.run("extend", "demo", "budget", "2.00 USD")
		if code != exitUsage || !strings.Contains(errs, bad+":1: ") {
			t.Errorf("code %d, stderr %q", code, errs)
		}
	})
	t.Run("ledger unopenable", func(t *testing.T) {
		f := newFixture(t)
		f.vars["ADELE_DB"] = filepath.Join(f.dir, "no", "dir", "adele.db")
		code, _, errs := f.run("extend", "demo", "budget", "2.00 USD")
		if code != exitFailure || !strings.Contains(errs, "adeled: ledger ") {
			t.Errorf("code %d, stderr %q", code, errs)
		}
	})
	t.Run("stored extension does not apply", func(t *testing.T) {
		f := newFixture(t)
		// The ledger validates the limit, not the value: a value the grant syntax refuses can only
		// arrive by a write outside extend, and extend must then fail rather than build on it.
		if _, err := openLedger(t, f).Extended("demo", "ports", "8080", "not-a-port", time.Now()); err != nil {
			t.Fatal(err)
		}
		code, out, errs := f.run("extend", "demo", "budget", "2.00 USD")
		if code != exitFailure || out != "" || !strings.Contains(errs, `extend demo ports "not-a-port"`) {
			t.Errorf("code %d, stdout %q, stderr %q", code, out, errs)
		}
	})
}

// insertRows records one row of each outcome through the ledger package.
func insertRows(t *testing.T, f *fixture) time.Time {
	t.Helper()
	led := openLedger(t, f)
	at := time.Date(2026, 10, 2, 12, 0, 0, 0, time.UTC)
	cost, quote := int64(25), int64(30)
	expires := at.Add(time.Hour)
	if _, err := led.Performed(ledger.Row{At: at, Grant: "demo", Session: "s-1", Capability: "standin.box",
		Action: "create", Resource: "box-a", CostCents: &cost, ExpiresAt: &expires,
		Undo: `{"capability":"standin.box","action":"delete","params":{"name":"box-a"}}`}); err != nil {
		t.Fatal(err)
	}
	if _, err := led.Refused(ledger.Row{At: at.Add(time.Minute), Grant: "demo", Session: "s-1",
		Capability: "standin.box", Action: "create", Resource: "box-b", CostCents: &quote,
		LimitName: "budget", Allowed: "0.75 USD", Needed: "0.30 USD"}); err != nil {
		t.Fatal(err)
	}
	if _, err := led.Extended("demo", "budget", "1.00 USD", "2.00 USD", at.Add(2*time.Minute)); err != nil {
		t.Fatal(err)
	}
	if _, err := led.Extended("demo", "ports", "8080", "22", at.Add(3*time.Minute)); err != nil {
		t.Fatal(err)
	}
	return at
}

func TestLedgerText(t *testing.T) {
	f := newFixture(t)
	code, out, errs := f.run("ledger")
	if code != exitOK || out != "0 rows\n" || errs != "" {
		t.Errorf("empty: code %d, stdout %q, stderr %q", code, out, errs)
	}

	insertRows(t, f)
	code, out, _ = f.run("ledger")
	lines := strings.Split(strings.TrimSuffix(out, "\n"), "\n")
	if code != exitOK || len(lines) != 5 || lines[4] != "4 rows" {
		t.Fatalf("code %d, stdout %q", code, out)
	}
	want := [][]string{
		{"#1 2026-10-02T12:00:00Z performed grant=demo session=s-1", "standin.box.create", "resource=box-a",
			"cost=0.25 USD", "expires=2026-10-02T13:00:00Z", `undo={"capability":"standin.box","action":"delete","params":{"name":"box-a"}}`},
		{"#2 2026-10-02T12:01:00Z refused grant=demo session=s-1", "standin.box.create resource=box-b",
			"limit=budget", `allowed="0.75 USD"`, `needed="0.30 USD"`},
		{"#3 2026-10-02T12:02:00Z extended grant=demo session=operator", `limit=budget was "1.00 USD", set to "2.00 USD"`},
		{"#4 ", `limit=ports was "8080", added "22"`},
	}
	for i, frags := range want {
		for _, frag := range frags {
			if !strings.Contains(lines[i], frag) {
				t.Errorf("line %d %q lacks %q", i+1, lines[i], frag)
			}
		}
	}
}

func TestLedgerJSON(t *testing.T) {
	f := newFixture(t)
	code, out, _ := f.run("ledger", "--json")
	if code != exitOK || strings.TrimSpace(out) != "[]" {
		t.Errorf("empty: code %d, stdout %q", code, out)
	}

	insertRows(t, f)
	code, out, errs := f.run("ledger", "--json")
	if code != exitOK || errs != "" {
		t.Fatalf("code %d, stderr %q", code, errs)
	}
	var rows []map[string]any
	if err := json.Unmarshal([]byte(out), &rows); err != nil {
		t.Fatalf("not a JSON array: %v\n%s", err, out)
	}
	if len(rows) != 4 {
		t.Fatalf("%d rows", len(rows))
	}
	keys := []string{"action", "allowed", "at", "capability", "cost_cents", "expires_at", "grant", "id",
		"limit_name", "needed", "outcome", "resource", "session", "undo"}
	for i, r := range rows {
		var got []string
		for k := range r {
			got = append(got, k)
		}
		sort.Strings(got)
		if !reflect.DeepEqual(got, keys) {
			t.Errorf("row %d keys %v", i, got)
		}
	}
	p, ref, ext := rows[0], rows[1], rows[2]
	undo, ok := p["undo"].(map[string]any)
	if p["outcome"] != "performed" || p["id"] != 1.0 || p["at"] != "2026-10-02T12:00:00Z" || p["cost_cents"] != 25.0 ||
		p["expires_at"] != "2026-10-02T13:00:00Z" || !ok || undo["action"] != "delete" || p["resource"] != "box-a" {
		t.Errorf("performed: %v", p)
	}
	if ref["outcome"] != "refused" || ref["undo"] != nil || ref["expires_at"] != nil || ref["cost_cents"] != 30.0 ||
		ref["limit_name"] != "budget" || ref["allowed"] != "0.75 USD" || ref["needed"] != "0.30 USD" {
		t.Errorf("refused: %v", ref)
	}
	if ext["outcome"] != "extended" || ext["undo"] != nil || ext["cost_cents"] != nil || ext["session"] != "operator" ||
		ext["allowed"] != "1.00 USD" || ext["needed"] != "2.00 USD" {
		t.Errorf("extended: %v", ext)
	}
}

func TestLedgerFailures(t *testing.T) {
	f := newFixture(t)
	code, _, errs := f.run("ledger", "--yaml")
	if code != exitUsage || !strings.Contains(errs, "flag provided but not defined") {
		t.Errorf("bad flag: code %d, stderr %q", code, errs)
	}
	f.vars["ADELE_DB"] = filepath.Join(f.dir, "no", "dir", "adele.db")
	code, _, errs = f.run("ledger")
	if code != exitFailure || !strings.Contains(errs, "adeled: ledger ") {
		t.Errorf("unopenable: code %d, stderr %q", code, errs)
	}
}

func TestDeref(t *testing.T) {
	n := int64(7)
	if deref(nil) != 0 || deref(&n) != 7 {
		t.Error("deref")
	}
}
