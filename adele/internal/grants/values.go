package grants

import (
	"fmt"
	"math"
	"regexp"
	"strconv"
	"strings"
	"time"
)

// Bounds on a ttl, inclusive.
const (
	MinTTL = time.Minute
	MaxTTL = 720 * time.Hour
)

// MaxPort is the highest valid port.
const MaxPort = 65535

// valueError is a bad value: what is wrong and how to fix it.
type valueError struct{ what, fix string }

func (e *valueError) Error() string { return e.what + " — " + e.fix }

func badValue(what, fix string) *valueError { return &valueError{what: what, fix: fix} }

func example(key string) string {
	switch key {
	case LimitCapabilities:
		return CapStandinBox
	case LimitBudget:
		return "2.00 USD"
	case LimitTTL:
		return "1h"
	case LimitInstances:
		return "2"
	}
	return "8080, 9000-9010"
}

// setLimit parses value as key's syntax and stores it in g.
func setLimit(g *Grant, key, value string) *valueError {
	var ve *valueError
	switch key {
	case LimitCapabilities:
		g.Capabilities, ve = parseCapabilities(value)
	case LimitBudget:
		g.BudgetCents, ve = parseMoney(value)
	case LimitTTL:
		g.TTL, ve = parseTTL(value)
	case LimitInstances:
		g.Instances, ve = parseInstances(value)
	case LimitPorts:
		g.Ports, ve = parsePorts(value)
	default:
		ve = badValue(fmt.Sprintf("unknown limit %q", key),
			"the limits are capabilities, budget, ttl, instances and ports")
	}
	return ve
}

func parseCapabilities(value string) ([]string, *valueError) {
	var out []string
	for _, c := range strings.Split(value, ",") {
		c = strings.TrimSpace(c)
		if c == "" {
			return nil, badValue(fmt.Sprintf("unparsable capabilities %q: an empty item", value),
				"separate capability names with single commas, e.g. "+CapStandinBox)
		}
		if ve := checkCapability(c); ve != nil {
			return nil, ve
		}
		if !contains(out, c) {
			out = append(out, c)
		}
	}
	return out, nil
}

func checkCapability(c string) *valueError {
	if !KnownCapabilities[c] {
		return badValue(fmt.Sprintf("unknown capability %q", c), "Adele knows: "+CapStandinBox)
	}
	return nil
}

func contains(list []string, s string) bool {
	for _, x := range list {
		if x == s {
			return true
		}
	}
	return false
}

var moneyRE = regexp.MustCompile(`^([+-]?)(\d+)(?:\.(\d+))?\s+(\S+)$`)

// ParseMoney parses an amount in grant-file syntax ("2.00 USD") into cents.
func ParseMoney(s string) (int64, error) {
	c, ve := parseMoney(s)
	if ve != nil {
		return 0, ve
	}
	return c, nil
}

func parseMoney(s string) (int64, *valueError) {
	m := moneyRE.FindStringSubmatch(strings.TrimSpace(s))
	if m == nil {
		return 0, badValue(fmt.Sprintf("unparsable amount %q", s), "write a decimal then USD, e.g. 2.00 USD")
	}
	sign, whole, frac, cur := m[1], m[2], m[3], m[4]
	if sign == "-" {
		return 0, badValue(fmt.Sprintf("negative amount %q", s), "an amount is 0.00 USD or more")
	}
	if len(frac) > 2 {
		return 0, badValue(fmt.Sprintf("amount %q has more than 2 decimal places", s),
			"round it to the cent, e.g. 2.00 USD")
	}
	if cur != "USD" {
		return 0, badValue(fmt.Sprintf("currency %q is not USD", cur), "write the amount in USD, e.g. 2.00 USD")
	}
	w, err := strconv.ParseInt(whole, 10, 64)
	if err != nil || w > math.MaxInt64/100-1 {
		return 0, badValue(fmt.Sprintf("amount %q is too large", s), "write a smaller amount")
	}
	frac = (frac + "00")[:2]
	f, _ := strconv.ParseInt(frac, 10, 64)
	return w*100 + f, nil
}

// FormatMoney formats cents in grant-file syntax: 40 → "0.40 USD".
func FormatMoney(cents int64) string {
	sign := ""
	if cents < 0 {
		sign, cents = "-", -cents
	}
	return fmt.Sprintf("%s%d.%02d USD", sign, cents/100, cents%100)
}

// ParseTTL parses a Go-style duration between MinTTL and MaxTTL inclusive.
func ParseTTL(s string) (time.Duration, error) {
	d, ve := parseTTL(s)
	if ve != nil {
		return 0, ve
	}
	return d, nil
}

func parseTTL(s string) (time.Duration, *valueError) {
	d, err := time.ParseDuration(strings.TrimSpace(s))
	if err != nil {
		return 0, badValue(fmt.Sprintf("unparsable ttl %q", s), "write a duration such as 1h, 90m or 1h30m")
	}
	if d < MinTTL || d > MaxTTL {
		return 0, badValue(fmt.Sprintf("ttl %q is out of range", s), "a ttl is between 1m and 720h")
	}
	return d, nil
}

// FormatDuration formats d compactly so that time.ParseDuration round-trips
// it: 1h, 90m → "1h30m", 45m, 30s. Sub-second durations use d.String().
func FormatDuration(d time.Duration) string {
	if d <= 0 || d%time.Second != 0 {
		return d.String()
	}
	h, m, s := d/time.Hour, (d%time.Hour)/time.Minute, (d%time.Minute)/time.Second
	var b strings.Builder
	if h > 0 {
		fmt.Fprintf(&b, "%dh", h)
	}
	if m > 0 {
		fmt.Fprintf(&b, "%dm", m)
	}
	if s > 0 {
		fmt.Fprintf(&b, "%ds", s)
	}
	return b.String()
}

var intRE = regexp.MustCompile(`^\d+$`)

func parseInstances(s string) (int, *valueError) {
	if strings.HasPrefix(s, "-") {
		return 0, badValue(fmt.Sprintf("negative instances %q", s), "instances is 0 or more")
	}
	n, err := strconv.Atoi(s)
	if !intRE.MatchString(s) || err != nil {
		return 0, badValue(fmt.Sprintf("unparsable instances %q", s), "write a whole number, 0 or more")
	}
	return n, nil
}
