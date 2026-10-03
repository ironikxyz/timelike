// Package grants parses Adele's grant file and computes effective grants.
//
// The grammar is line-based so that every error names the exact line at
// fault (data-model § Grant file; spec FR-5, FR-6, D-3).
package grants

import (
	"bufio"
	"errors"
	"fmt"
	"io"
	"os"
	"regexp"
	"strings"
	"time"
)

// Limit names: the grant-file keys, and the `limit.name` values of a refusal.
const (
	LimitCapabilities = "capabilities"
	LimitBudget       = "budget"
	LimitTTL          = "ttl"
	LimitInstances    = "instances"
	LimitPorts        = "ports"
)

// Limits lists every limit name in grant-file order.
var Limits = []string{LimitCapabilities, LimitBudget, LimitTTL, LimitInstances, LimitPorts}

// CapStandinBox is the one capability slice 0 knows.
const CapStandinBox = "standin.box"

// KnownCapabilities is the set of capability names a grant may contain.
var KnownCapabilities = map[string]bool{CapStandinBox: true}

// Grant is one `[grant NAME]` section, with every required key present.
type Grant struct {
	Name         string
	Capabilities []string
	BudgetCents  int64
	TTL          time.Duration
	Instances    int
	Ports        PortSet
	Line         int // the line of the section header
}

// Allows reports whether the grant contains capability c.
func (g Grant) Allows(c string) bool {
	for _, have := range g.Capabilities {
		if have == c {
			return true
		}
	}
	return false
}

// File is a fully parsed grant file. Grants are in file order.
type File struct {
	Name   string
	Grants []Grant
}

// Get returns the grant named name.
func (f *File) Get(name string) (Grant, bool) {
	for _, g := range f.Grants {
		if g.Name == name {
			return g, true
		}
	}
	return Grant{}, false
}

// Names returns the grant names in file order.
func (f *File) Names() []string {
	out := make([]string, len(f.Grants))
	for i, g := range f.Grants {
		out[i] = g.Name
	}
	return out
}

// ParseError is a malformed grant file: the file, the line at fault (0 when
// the file could not be read), what is wrong, and how to fix it.
type ParseError struct {
	File string
	Line int
	What string
	Fix  string
}

func (e *ParseError) Error() string {
	return fmt.Sprintf("%s:%d: %s — %s", e.File, e.Line, e.What, e.Fix)
}

// Load reads and parses the grant file at path.
func Load(path string) (*File, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, &ParseError{File: path, Line: 0, What: "cannot read the grant file: " + osReason(err),
			Fix: "check the path (ADELE_GRANTS) and that the file is readable"}
	}
	defer f.Close()
	return Parse(path, f)
}

func osReason(err error) string {
	var pe *os.PathError
	if errors.As(err, &pe) {
		return pe.Err.Error()
	}
	return err.Error()
}

var (
	nameRE = regexp.MustCompile(`^[a-z][a-z0-9-]{0,62}$`)
	keyRE  = regexp.MustCompile(`^[A-Za-z0-9_.-]+$`)
)

// parser holds the state of one parse.
type parser struct {
	file    string
	grants  []Grant
	cur     *Grant
	seen    map[string]int // keys of the current section → their line
	names   map[string]int // grant names → their section line
	lineNum int
}

// Parse parses a grant file read from r. name is used in error messages.
// The first error stops the parse; nothing is returned on error.
func Parse(name string, r io.Reader) (*File, error) {
	p := &parser{file: name, names: map[string]int{}}
	br := bufio.NewReader(r)
	for {
		raw, err := br.ReadString('\n')
		if len(raw) > 0 {
			p.lineNum++
			if perr := p.line(raw); perr != nil {
				return nil, perr
			}
		}
		if err == io.EOF {
			break
		}
		if err != nil {
			return nil, &ParseError{File: name, Line: 0, What: "cannot read the grant file: " + err.Error(),
				Fix: "check that the file is readable"}
		}
	}
	if err := p.closeSection(); err != nil {
		return nil, err
	}
	if len(p.grants) == 0 {
		return nil, p.errAt(1, "the file defines no grant",
			"add a [grant NAME] section with capabilities, budget, ttl, instances and ports")
	}
	return &File{Name: name, Grants: p.grants}, nil
}

func (p *parser) errAt(line int, what, fix string) *ParseError {
	return &ParseError{File: p.file, Line: line, What: what, Fix: fix}
}

func (p *parser) err(what, fix string) *ParseError { return p.errAt(p.lineNum, what, fix) }

// line handles one raw line, including its terminator.
func (p *parser) line(raw string) *ParseError {
	s := strings.TrimRight(raw, "\r\n")
	if p.lineNum == 1 {
		s = strings.TrimPrefix(s, "\uFEFF")
	}
	s = strings.TrimSpace(s)
	switch {
	case s == "" || strings.HasPrefix(s, "#"):
		return nil
	case strings.HasPrefix(s, "["):
		return p.section(s)
	}
	key, value, ok := strings.Cut(s, "=")
	key, value = strings.TrimSpace(key), strings.TrimSpace(value)
	if !ok || !keyRE.MatchString(key) {
		return p.err(fmt.Sprintf("%q is neither a [grant NAME] section nor a key = value line", s),
			"write [grant NAME], key = value, or a # comment")
	}
	return p.pair(key, value)
}

func (p *parser) section(s string) *ParseError {
	if !strings.HasSuffix(s, "]") {
		return p.err(fmt.Sprintf("%q is not a section header", s), "write [grant NAME]")
	}
	fields := strings.Fields(s[1 : len(s)-1])
	if len(fields) == 0 || fields[0] != "grant" {
		return p.err(fmt.Sprintf("%q is not a section header", s), "write [grant NAME]")
	}
	if err := p.closeSection(); err != nil {
		return err
	}
	name := strings.Join(fields[1:], " ")
	if len(fields) != 2 || !nameRE.MatchString(name) {
		return p.err(fmt.Sprintf("bad grant name %q", name),
			"a name is a lowercase letter, then up to 62 lowercase letters, digits or hyphens")
	}
	if first, dup := p.names[name]; dup {
		return p.err(fmt.Sprintf("duplicate grant %q (first defined at line %d)", name, first),
			"rename one of the two grants, or merge them")
	}
	p.names[name] = p.lineNum
	p.cur = &Grant{Name: name, Line: p.lineNum}
	p.seen = map[string]int{}
	return nil
}

// closeSection checks that the current section has every required key, and
// reports a missing one at the section's own line.
func (p *parser) closeSection() *ParseError {
	if p.cur == nil {
		return nil
	}
	for _, k := range Limits {
		if _, ok := p.seen[k]; !ok {
			return p.errAt(p.cur.Line, fmt.Sprintf("grant %q is missing the required key %q", p.cur.Name, k),
				fmt.Sprintf("add a line %q under [grant %s]", k+" = …", p.cur.Name))
		}
	}
	p.grants = append(p.grants, *p.cur)
	p.cur = nil
	return nil
}

func (p *parser) pair(key, value string) *ParseError {
	if p.cur == nil {
		return p.err(fmt.Sprintf("%q is outside any [grant NAME] section", key),
			"put it under a [grant NAME] line")
	}
	if !isLimit(key) {
		return p.err(fmt.Sprintf("unknown key %q", key),
			"the keys are capabilities, budget, ttl, instances and ports")
	}
	if first, dup := p.seen[key]; dup {
		return p.err(fmt.Sprintf("duplicate key %q in grant %q (first set at line %d)", key, p.cur.Name, first),
			"keep one of the two lines")
	}
	p.seen[key] = p.lineNum
	if value == "" {
		return p.err(fmt.Sprintf("empty value for %q", key), "give it a value, e.g. "+example(key))
	}
	if ve := setLimit(p.cur, key, value); ve != nil {
		return p.err(ve.what, ve.fix)
	}
	return nil
}

func isLimit(key string) bool {
	for _, l := range Limits {
		if l == key {
			return true
		}
	}
	return false
}
