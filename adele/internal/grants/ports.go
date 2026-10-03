package grants

import (
	"fmt"
	"strconv"
	"strings"
)

// PortRange is an inclusive range; a single port has Lo == Hi.
type PortRange struct{ Lo, Hi int }

func (r PortRange) String() string {
	if r.Lo == r.Hi {
		return strconv.Itoa(r.Lo)
	}
	return fmt.Sprintf("%d-%d", r.Lo, r.Hi)
}

// PortSet is the ports a resource may expose, in the order written. The empty
// set is written `none`.
type PortSet []PortRange

// Contains reports whether port p is in the set.
func (s PortSet) Contains(p int) bool {
	for _, r := range s {
		if p >= r.Lo && p <= r.Hi {
			return true
		}
	}
	return false
}

// covers reports whether every port of r is already in the set.
func (s PortSet) covers(r PortRange) bool {
	for _, have := range s {
		if r.Lo >= have.Lo && r.Hi <= have.Hi {
			return true
		}
	}
	return false
}

// String is the canonical grant-file form: "8080, 9000-9010" or "none".
func (s PortSet) String() string {
	if len(s) == 0 {
		return "none"
	}
	parts := make([]string, len(s))
	for i, r := range s {
		parts[i] = r.String()
	}
	return strings.Join(parts, ", ")
}

// ParsePorts parses "8080, 9000-9010" or "none".
func ParsePorts(s string) (PortSet, error) {
	ps, ve := parsePorts(s)
	if ve != nil {
		return nil, ve
	}
	return ps, nil
}

func parsePorts(s string) (PortSet, *valueError) {
	s = strings.TrimSpace(s)
	if s == "none" {
		return PortSet{}, nil
	}
	var out PortSet
	for _, item := range strings.Split(s, ",") {
		r, ve := parsePortRange(strings.TrimSpace(item))
		if ve != nil {
			return nil, ve
		}
		out = append(out, r)
	}
	return out, nil
}

func parsePortRange(item string) (PortRange, *valueError) {
	if item == "" || item == "none" {
		return PortRange{}, badValue(fmt.Sprintf("unparsable port item %q", item),
			"write ports or ranges separated by commas, e.g. 8080, 9000-9010, or none alone")
	}
	lo, hi, isRange := strings.Cut(item, "-")
	a, ve := parsePort(strings.TrimSpace(lo))
	if ve != nil {
		return PortRange{}, ve
	}
	if !isRange {
		return PortRange{Lo: a, Hi: a}, nil
	}
	b, ve := parsePort(strings.TrimSpace(hi))
	if ve != nil {
		return PortRange{}, ve
	}
	if b < a {
		return PortRange{}, badValue(fmt.Sprintf("reversed port range %q", item),
			fmt.Sprintf("write the low port first: %d-%d", b, a))
	}
	return PortRange{Lo: a, Hi: b}, nil
}

func parsePort(s string) (int, *valueError) {
	if !intRE.MatchString(s) {
		return 0, badValue(fmt.Sprintf("unparsable port %q", s), "a port is a whole number from 1 to 65535")
	}
	n, err := strconv.Atoi(s)
	if err != nil || n < 1 || n > MaxPort {
		return 0, badValue(fmt.Sprintf("port %s is out of range", s), "a port is from 1 to 65535")
	}
	return n, nil
}
