package grants

import (
	"errors"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"
	"testing/iotest"
	"time"
)

const validGrant = `[grant demo]
capabilities = standin.box
budget = 2.00 USD
ttl = 1h
instances = 2
ports = 8080, 9000-9010
`

// with returns validGrant with key's line replaced by line (or removed when line is "").
func with(key, line string) string {
	var out []string
	for _, l := range strings.Split(strings.TrimSuffix(validGrant, "\n"), "\n") {
		if strings.HasPrefix(l, key+" =") {
			if line == "" {
				continue
			}
			l = line
		}
		out = append(out, l)
	}
	return strings.Join(out, "\n") + "\n"
}

func TestParseMalformed(t *testing.T) {
	cases := []struct {
		name, src string
		line      int
		want      string // a substring naming the problem
	}{
		{"pair outside section", "# hi\nbudget = 2.00 USD\n" + validGrant, 2, "outside any [grant NAME] section"},
		{"neither section nor pair", validGrant + "just words\n", 7, "neither a [grant NAME] section nor a key = value"},
		{"empty key", "[grant demo]\n = 3\n", 2, "neither a [grant NAME] section"},
		{"section not closed", "[grant demo\n", 1, "not a section header"},
		{"section not grant", "[server demo]\n", 1, "not a section header"},
		{"bad grant name upper", "[grant Demo]\n", 1, `bad grant name "Demo"`},
		{"bad grant name spaces", "[grant my demo]\n", 1, `bad grant name "my demo"`},
		{"bad grant name empty", "[grant]\n", 1, `bad grant name ""`},
		{"bad grant name too long", "[grant a" + strings.Repeat("b", 63) + "]\n", 1, "bad grant name"},
		{"duplicate grant", validGrant + "\n" + validGrant, 8, `duplicate grant "demo" (first defined at line 1)`},
		{"duplicate key", validGrant + "ttl = 2h\n", 7, `duplicate key "ttl" in grant "demo" (first set at line 4)`},
		{"unknown key", validGrant + "region = eu\n", 7, `unknown key "region"`},
		{"empty value", with("ttl", "ttl ="), 4, `empty value for "ttl"`},
		{"unparsable ttl", with("ttl", "ttl = soon"), 4, `unparsable ttl "soon"`},
		{"unparsable budget", with("budget", "budget = two dollars"), 3, "unparsable amount"},
		{"budget without currency", with("budget", "budget = 2.00"), 3, "unparsable amount"},
		{"unparsable instances", with("instances", "instances = 2.5"), 5, "unparsable instances"},
		{"negative instances", with("instances", "instances = -1"), 5, "negative instances"},
		{"unparsable port", with("ports", "ports = http"), 6, `unparsable port "http"`},
		{"empty port item", with("ports", "ports = 80,,81"), 6, "unparsable port item"},
		{"none among ports", with("ports", "ports = 80, none"), 6, "unparsable port item"},
		{"empty capability item", with("capabilities", "capabilities = standin.box,"), 2, "an empty item"},
		{"unknown capability", with("capabilities", "capabilities = standin.box, cloud.vm"), 2, `unknown capability "cloud.vm"`},
		{"negative budget", with("budget", "budget = -1.00 USD"), 3, "negative amount"},
		{"three decimals", with("budget", "budget = 2.001 USD"), 3, "more than 2 decimal places"},
		{"non-USD", with("budget", "budget = 2.00 EUR"), 3, `currency "EUR" is not USD`},
		{"huge budget", with("budget", "budget = 99999999999999999999 USD"), 3, "too large"},
		{"ttl below 1m", with("ttl", "ttl = 59s"), 4, "out of range"},
		{"ttl above 720h", with("ttl", "ttl = 720h1s"), 4, "out of range"},
		{"port 0", with("ports", "ports = 0"), 6, "port 0 is out of range"},
		{"port 65536", with("ports", "ports = 8080, 65536"), 6, "port 65536 is out of range"},
		{"range end out of range", with("ports", "ports = 9000-70000"), 6, "port 70000 is out of range"},
		{"bad range end", with("ports", "ports = 9000-x"), 6, `unparsable port "x"`},
		{"reversed range", with("ports", "ports = 9010-9000"), 6, `reversed port range "9010-9000"`},
		{"missing key", "# c\n\n" + with("instances", "") + "[grant other]\n", 3, `grant "demo" is missing the required key "instances"`},
		{"missing key at EOF", "\n" + with("ports", ""), 2, `missing the required key "ports"`},
		{"no grant", "# only a comment\n\n", 1, "defines no grant"},
		{"empty file", "", 1, "defines no grant"},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			f, err := Parse("g.conf", strings.NewReader(c.src))
			if f != nil {
				t.Fatalf("got a file %+v, want nothing", f)
			}
			var pe *ParseError
			if !errors.As(err, &pe) {
				t.Fatalf("err = %v, want *ParseError", err)
			}
			if pe.Line != c.line || pe.File != "g.conf" {
				t.Errorf("at %s:%d, want g.conf:%d (%v)", pe.File, pe.Line, c.line, err)
			}
			if !strings.Contains(pe.What, c.want) {
				t.Errorf("what = %q, want it to contain %q", pe.What, c.want)
			}
			if pe.Fix == "" {
				t.Error("no fix given")
			}
			if !strings.HasPrefix(err.Error(), "g.conf:") || !strings.Contains(err.Error(), " — ") {
				t.Errorf("Error() = %q, want <file>:<line>: <what> — <fix>", err.Error())
			}
		})
	}
}

func TestParseErrorFormat(t *testing.T) {
	e := &ParseError{File: "a.conf", Line: 7, What: "bad", Fix: "fix it"}
	if got, want := e.Error(), "a.conf:7: bad — fix it"; got != want {
		t.Errorf("got %q, want %q", got, want)
	}
}

func TestLoadUnreadable(t *testing.T) {
	path := filepath.Join(t.TempDir(), "missing.conf")
	_, err := Load(path)
	var pe *ParseError
	if !errors.As(err, &pe) || pe.Line != 0 || pe.File != path {
		t.Fatalf("err = %#v, want line 0 of %s", err, path)
	}
	if !strings.Contains(pe.What, "no such file or directory") {
		t.Errorf("what = %q, want the OS error", pe.What)
	}
}

func TestParseReadError(t *testing.T) {
	_, err := Parse("g.conf", iotest.ErrReader(errors.New("disk on fire")))
	var pe *ParseError
	if !errors.As(err, &pe) || pe.Line != 0 || !strings.Contains(pe.What, "disk on fire") {
		t.Fatalf("err = %v, want line 0 naming the read error", err)
	}
}

func TestLoadValid(t *testing.T) {
	path := filepath.Join(t.TempDir(), "grants.conf")
	if err := os.WriteFile(path, []byte(validGrant), 0o600); err != nil {
		t.Fatal(err)
	}
	f, err := Load(path)
	if err != nil {
		t.Fatal(err)
	}
	want := Grant{Name: "demo", Capabilities: []string{CapStandinBox}, BudgetCents: 200, TTL: time.Hour,
		Instances: 2, Ports: PortSet{{8080, 8080}, {9000, 9010}}, Line: 1}
	if f.Name != path || len(f.Grants) != 1 || !reflect.DeepEqual(f.Grants[0], want) {
		t.Errorf("got %+v, want %+v", f, want)
	}
}

func TestParseValidVariants(t *testing.T) {
	src := "\uFEFF# Adele's grants\r\n" +
		"   # indented comment\r\n" +
		"\r\n" +
		"[grant demo]\r\n" +
		"capabilities=standin.box , standin.box\r\n" +
		"\tbudget   =   0.5 USD\r\n" +
		"ttl = 90m\n" +
		"instances = 0\n" +
		"ports = none\n" +
		"\n" +
		"  [ grant  ci-2 ]  \n" +
		"ports = 22,8000 - 8010\n" +
		"instances = 10\n" +
		"ttl = 720h\n" +
		"budget = 7 USD\n" +
		"capabilities = standin.box" // no final newline
	f, err := Parse("v.conf", strings.NewReader(src))
	if err != nil {
		t.Fatal(err)
	}
	if got := f.Names(); !reflect.DeepEqual(got, []string{"demo", "ci-2"}) {
		t.Fatalf("names = %v", got)
	}
	demo, _ := f.Get("demo")
	if demo.BudgetCents != 50 || demo.TTL != 90*time.Minute || demo.Instances != 0 ||
		len(demo.Ports) != 0 || demo.Line != 4 || !reflect.DeepEqual(demo.Capabilities, []string{CapStandinBox}) {
		t.Errorf("demo = %+v", demo)
	}
	ci, ok := f.Get("ci-2")
	if !ok || ci.BudgetCents != 700 || ci.TTL != 720*time.Hour || ci.Instances != 10 || ci.Line != 11 ||
		ci.Ports.String() != "22, 8000-8010" || !ci.Allows(CapStandinBox) || ci.Allows("cloud.vm") {
		t.Errorf("ci-2 = %+v", ci)
	}
	if _, ok := f.Get("nope"); ok {
		t.Error("Get(nope) found a grant")
	}
}
