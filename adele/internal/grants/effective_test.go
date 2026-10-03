package grants

import (
	"reflect"
	"strings"
	"testing"
	"time"
)

func baseGrant() Grant {
	return Grant{Name: "demo", Capabilities: []string{CapStandinBox}, BudgetCents: 200, TTL: time.Hour,
		Instances: 2, Ports: PortSet{{8080, 8080}, {9000, 9010}}, Line: 1}
}

func TestEffective(t *testing.T) {
	g := baseGrant()
	exts := []Extension{
		{"demo", LimitBudget, "1.25 USD"},
		{"demo", LimitTTL, "2h"},
		{"demo", LimitInstances, "3"},
		{"demo", LimitPorts, "22"},
		{"demo", LimitPorts, "9005"},      // already covered: no change
		{"demo", LimitPorts, "7000-7001"}, // a range
		{"other", LimitInstances, "99"},   // another grant: skipped
		{"demo", LimitCapabilities, CapStandinBox},
		{"demo", LimitBudget, "3.00 USD"}, // latest wins
	}
	eff, err := Effective(g, exts)
	if err != nil {
		t.Fatal(err)
	}
	if eff.BudgetCents != 300 || eff.TTL != 2*time.Hour || eff.Instances != 3 {
		t.Errorf("eff = %+v", eff)
	}
	if got := eff.Ports.String(); got != "8080, 9000-9010, 22, 7000-7001" {
		t.Errorf("ports = %q", got)
	}
	if !reflect.DeepEqual(eff.Capabilities, []string{CapStandinBox}) {
		t.Errorf("capabilities = %v", eff.Capabilities)
	}
	if !reflect.DeepEqual(g, baseGrant()) {
		t.Errorf("Effective modified its input: %+v", g)
	}
}

func TestEffectiveAddsCapability(t *testing.T) {
	g := baseGrant()
	g.Capabilities = nil
	eff, err := Effective(g, []Extension{{"", LimitCapabilities, CapStandinBox}})
	if err != nil || !eff.Allows(CapStandinBox) {
		t.Errorf("eff = %+v, %v", eff, err)
	}
	g.Ports = nil
	eff, _ = Effective(g, []Extension{{"demo", LimitPorts, "8080"}})
	if eff.Ports.String() != "8080" {
		t.Errorf("ports = %q", eff.Ports)
	}
}

func TestEffectiveErrors(t *testing.T) {
	g := baseGrant()
	for _, e := range []Extension{
		{"demo", "region", "eu"},
		{"demo", LimitBudget, "1.001 USD"},
		{"demo", LimitTTL, "721h"},
		{"demo", LimitPorts, "8080, 8081"},
	} {
		got, err := Effective(g, []Extension{e})
		if err == nil {
			t.Errorf("Effective(%v) succeeded", e)
			continue
		}
		if !strings.Contains(err.Error(), "extend demo "+e.Limit) {
			t.Errorf("err = %v, want it to name the extension", err)
		}
		if !reflect.DeepEqual(got, g) {
			t.Errorf("on error got %+v, want the unextended grant", got)
		}
	}
}

func TestValidateExtension(t *testing.T) {
	cases := []struct {
		limit, value string
		ok           bool
		want         string
	}{
		{LimitBudget, "1.25 USD", true, ""},
		{LimitBudget, "1.25 EUR", false, "not USD"},
		{LimitBudget, "-1 USD", false, "negative"},
		{LimitTTL, "90m", true, ""},
		{LimitTTL, "30s", false, "out of range"},
		{LimitInstances, "0", true, ""},
		{LimitInstances, "three", false, "unparsable instances"},
		{LimitPorts, "22", true, ""},
		{LimitPorts, "9000-9010", true, ""},
		{LimitPorts, "0", false, "out of range"},
		{LimitPorts, "9010-9000", false, "reversed"},
		{LimitPorts, "none", false, "not one port or range"},
		{LimitPorts, "22,80", false, "not one port or range"},
		{LimitCapabilities, CapStandinBox, true, ""},
		{LimitCapabilities, "cloud.vm", false, "unknown capability"},
		{LimitCapabilities, "", false, "empty value"},
		{"region", "eu", false, "unknown limit"},
	}
	for _, c := range cases {
		err := ValidateExtension(c.limit, c.value)
		if (err == nil) != c.ok {
			t.Errorf("ValidateExtension(%q, %q) = %v, want ok=%v", c.limit, c.value, err, c.ok)
			continue
		}
		if err != nil && !strings.Contains(err.Error(), c.want) {
			t.Errorf("ValidateExtension(%q, %q) = %v, want %q", c.limit, c.value, err, c.want)
		}
	}
}

func TestFormatLimit(t *testing.T) {
	g := baseGrant()
	want := map[string]string{
		LimitCapabilities: "standin.box",
		LimitBudget:       "2.00 USD",
		LimitTTL:          "1h",
		LimitInstances:    "2",
		LimitPorts:        "8080, 9000-9010",
		"region":          "",
	}
	for limit, w := range want {
		if got := FormatLimit(g, limit); got != w {
			t.Errorf("FormatLimit(%s) = %q, want %q", limit, got, w)
		}
		if w != "" {
			if err := ValidateExtension(limit, w); err != nil && limit != LimitPorts {
				t.Errorf("formatted %s %q does not validate: %v", limit, w, err)
			}
		}
	}
}
