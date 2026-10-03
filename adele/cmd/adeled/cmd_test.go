package main

import (
	"bytes"
	"net"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// testCanary is a well-formed canary: tlcanary- and 32 lowercase hex characters.
const testCanary = "tlcanary-0123456789abcdef0123456789abcdef"

const testGrants = `# two grants, file order demo then other
[grant demo]
capabilities = standin.box
budget = 1.00 USD
ttl = 1h
instances = 2
ports = 8080

[grant other]
capabilities = standin.box
budget = 0.50 USD
ttl = 30m
instances = 1
ports = none
`

// fixture is one test's environment: every path in its own temp dir, nothing from the process env.
type fixture struct {
	t    *testing.T
	dir  string
	vars map[string]string
}

func newFixture(t *testing.T) *fixture {
	t.Helper()
	dir := t.TempDir()
	f := &fixture{t: t, dir: dir, vars: map[string]string{
		"ADELE_GRANTS":      filepath.Join(dir, "grants.conf"),
		"ADELE_DB":          filepath.Join(dir, "adele.db"),
		"ADELE_CANARY_FILE": filepath.Join(dir, "canary"),
		"ADELE_LISTEN":      "127.0.0.1:0",
		"ADELE_STANDIN_URL": "http://127.0.0.1:1",
		"ADELE_CONTAINER":   "timelike-adele",
	}}
	f.write("grants.conf", testGrants)
	f.write("canary", testCanary+"\n")
	return f
}

func (f *fixture) write(name, content string) string {
	f.t.Helper()
	p := filepath.Join(f.dir, name)
	if err := os.WriteFile(p, []byte(content), 0o600); err != nil {
		f.t.Fatal(err)
	}
	return p
}

func (f *fixture) getenv(k string) string { return f.vars[k] }

func (f *fixture) env() env { return env(f.getenv) }

func (f *fixture) run(args ...string) (int, string, string) {
	var out, errb bytes.Buffer
	code := run(args, f.getenv, &out, &errb)
	return code, out.String(), errb.String()
}

// withRevision sets the package's build stamp for one test.
func withRevision(t *testing.T, rev string) {
	t.Helper()
	saved := revision
	revision = rev
	t.Cleanup(func() { revision = saved })
}

// busyAddr holds a port for the rest of the test.
func busyAddr(t *testing.T) string {
	t.Helper()
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { ln.Close() })
	return ln.Addr().String()
}

// freeAddr returns an address nothing listens on (a port bound, then released).
func freeAddr(t *testing.T) string {
	t.Helper()
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	addr := ln.Addr().String()
	ln.Close()
	return addr
}

func TestRunDispatch(t *testing.T) {
	f := newFixture(t)
	code, out, errs := f.run()
	if code != exitUsage || !strings.Contains(errs, "usage:") || out != "" {
		t.Errorf("no args: code %d, stdout %q, stderr %q", code, out, errs)
	}
	code, _, errs = f.run("frobnicate")
	if code != exitUsage || !strings.Contains(errs, `unknown command "frobnicate"`) || !strings.Contains(errs, "usage:") {
		t.Errorf("unknown: code %d, stderr %q", code, errs)
	}
	for _, h := range []string{"help", "-h", "--help"} {
		code, out, _ = f.run(h)
		if code != exitOK || !strings.Contains(out, "adeled extend GRANT LIMIT VALUE") {
			t.Errorf("%s: code %d, stdout %q", h, code, out)
		}
	}
}

func TestEnvDefaults(t *testing.T) {
	e := env(func(string) string { return "" })
	want := map[string]string{
		"ADELE_GRANTS": "/etc/adele/grants.conf", "ADELE_DB": "/var/lib/adele/adele.db",
		"ADELE_CANARY_FILE": "/run/adele-secret/canary", "ADELE_LISTEN": ":8480",
		"ADELE_STANDIN_URL": "http://adele-standin:8481", "ADELE_CONTAINER": "timelike-adele", "OTHER": "",
	}
	for k, v := range want {
		if got := e.get(k); got != v {
			t.Errorf("default %s = %q, want %q", k, got, v)
		}
	}
	set := env(func(k string) string { return map[string]string{"ADELE_LISTEN": ":9"}[k] })
	if got := set.get("ADELE_LISTEN"); got != ":9" {
		t.Errorf("a set value is not used: %q", got)
	}
}

func TestVersion(t *testing.T) {
	f := newFixture(t)
	withRevision(t, "")
	code, out, errs := f.run("version")
	if code != exitFailure || out != "" || !strings.Contains(errs, "carries no revision stamp") || !strings.Contains(errs, "(H8)") {
		t.Errorf("unstamped: code %d, stdout %q, stderr %q", code, out, errs)
	}
	withRevision(t, "0123abcd")
	code, out, errs = f.run("version")
	if code != exitOK || out != "0123abcd\n" || errs != "" {
		t.Errorf("stamped: code %d, stdout %q, stderr %q", code, out, errs)
	}
}

func TestCheck(t *testing.T) {
	f := newFixture(t)
	code, out, errs := f.run("check")
	if code != exitOK || out != "ok: 2 grants (demo, other)\n" || errs != "" {
		t.Errorf("valid: code %d, stdout %q, stderr %q", code, out, errs)
	}

	// The malformation is on line 4: the error names the file and that line.
	bad := f.write("bad.conf", "[grant demo]\ncapabilities = standin.box\nbudget = 1.00 USD\nttl = forever\ninstances = 1\nports = none\n")
	f.vars["ADELE_GRANTS"] = bad
	code, out, errs = f.run("check")
	if code != exitUsage || out != "" || !strings.HasPrefix(errs, "adeled: "+bad+":4: ") || !strings.Contains(errs, "ttl") {
		t.Errorf("malformed: code %d, stdout %q, stderr %q", code, out, errs)
	}

	// --grants overrides ADELE_GRANTS (which still names the bad file).
	good := f.write("one.conf", "[grant solo]\ncapabilities = standin.box\nbudget = 1.00 USD\nttl = 1h\ninstances = 1\nports = none\n")
	code, out, _ = f.run("check", "--grants", good)
	if code != exitOK || out != "ok: 1 grants (solo)\n" {
		t.Errorf("--grants: code %d, stdout %q", code, out)
	}

	code, _, errs = f.run("check", "--nope")
	if code != exitUsage || !strings.Contains(errs, "flag provided but not defined") {
		t.Errorf("bad flag: code %d, stderr %q", code, errs)
	}

	f.vars["ADELE_GRANTS"] = filepath.Join(f.dir, "absent.conf")
	code, _, errs = f.run("check")
	if code != exitUsage || !strings.Contains(errs, "absent.conf:0: cannot read the grant file") {
		t.Errorf("absent: code %d, stderr %q", code, errs)
	}
}
