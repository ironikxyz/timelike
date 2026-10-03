package grants

import (
	"fmt"
	"strings"
)

// Extension is one operator extension: limit set to value on grant
// (`adeled extend <grant> <limit> <value>`).
type Extension struct {
	Grant, Limit, Value string
}

// ValidateExtension checks value in grant-file syntax for limit, so that the
// extend command can refuse a bad value before storing it. budget is a new
// total; ports is one port or range; capabilities is one capability.
func ValidateExtension(limit, value string) error {
	var scratch Grant
	return extend(&scratch, limit, strings.TrimSpace(value))
}

// Effective overlays exts on g, in order. budget, ttl and instances replace
// the value; ports and capabilities add one item. Extensions naming another
// grant are skipped (an empty Grant field applies to any grant). g is not
// modified.
func Effective(g Grant, exts []Extension) (Grant, error) {
	out := g
	out.Capabilities = append([]string(nil), g.Capabilities...)
	out.Ports = append(PortSet(nil), g.Ports...)
	for _, e := range exts {
		if e.Grant != "" && e.Grant != g.Name {
			continue
		}
		if err := extend(&out, e.Limit, strings.TrimSpace(e.Value)); err != nil {
			return g, fmt.Errorf("extend %s %s %q: %w", g.Name, e.Limit, e.Value, err)
		}
	}
	return out, nil
}

func extend(g *Grant, limit, value string) error {
	if value == "" {
		return badValue("empty value", "give a value, e.g. "+example(limit))
	}
	switch limit {
	case LimitCapabilities:
		if ve := checkCapability(value); ve != nil {
			return ve
		}
		if !contains(g.Capabilities, value) {
			g.Capabilities = append(g.Capabilities, value)
		}
		return nil
	case LimitPorts:
		if strings.Contains(value, ",") || value == "none" {
			return badValue(fmt.Sprintf("ports extension %q is not one port or range", value),
				"extend one port or range at a time, e.g. 8080 or 9000-9010")
		}
		r, ve := parsePortRange(value)
		if ve != nil {
			return ve
		}
		if !g.Ports.covers(r) {
			g.Ports = append(g.Ports, r)
		}
		return nil
	case LimitBudget, LimitTTL, LimitInstances:
		if ve := setLimit(g, limit, value); ve != nil {
			return ve
		}
		return nil
	}
	return badValue(fmt.Sprintf("unknown limit %q", limit),
		"the limits are capabilities, budget, ttl, instances and ports")
}

// FormatLimit returns g's value for limit in grant-file syntax, or "" for an
// unknown limit.
func FormatLimit(g Grant, limit string) string {
	switch limit {
	case LimitCapabilities:
		return strings.Join(g.Capabilities, ", ")
	case LimitBudget:
		return FormatMoney(g.BudgetCents)
	case LimitTTL:
		return FormatDuration(g.TTL)
	case LimitInstances:
		return fmt.Sprint(g.Instances)
	case LimitPorts:
		return g.Ports.String()
	}
	return ""
}
