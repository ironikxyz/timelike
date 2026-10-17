package main

import (
	"bytes"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"timelike/adele/internal/compose"
)

// fakeCompose writes a script standing in for docker-compose: it prints stdout and stderr as given and exits code.
func fakeCompose(t *testing.T, stdout, stderr string, code int) string {
	t.Helper()
	dir := t.TempDir()
	p := filepath.Join(dir, "docker-compose")
	o, e := filepath.Join(dir, "out"), filepath.Join(dir, "err")
	if err := os.WriteFile(o, []byte(stdout), 0o600); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(e, []byte(stderr), 0o600); err != nil {
		t.Fatal(err)
	}
	script := "#!/bin/sh\necho \"$@\" > " + filepath.Join(dir, "args") + "\ncat " + o + "\ncat " + e + " >&2\nexit " +
		string(rune('0'+code)) + "\n"
	if err := os.WriteFile(p, []byte(script), 0o700); err != nil {
		t.Fatal(err)
	}
	return p
}

func runResolve(t *testing.T, bin string, args ...string) compose.Resolved {
	t.Helper()
	var out, errb bytes.Buffer
	e := env(func(k string) string {
		if k == "ADELE_COMPOSE_BIN" {
			return bin
		}
		return ""
	})
	if code := resolve(e, args, &out, &errb); code != exitOK {
		t.Fatalf("resolve exit %d: %s", code, errb.String())
	}
	var doc compose.Resolved
	if err := json.Unmarshal(out.Bytes(), &doc); err != nil {
		t.Fatalf("not one JSON document: %q", out.String())
	}
	return doc
}

func TestResolveReportsTheModelRealPathsAndUnsetVariables(t *testing.T) {
	ws := t.TempDir()
	p := filepath.Join(ws, "p")
	if err := os.MkdirAll(filepath.Join(p, "data"), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink("/etc", filepath.Join(p, "link")); err != nil {
		t.Fatal(err)
	}
	model := `{"name": "tl-p-1", "services": {"db": {"image": "debian:x", "volumes": [
	  {"type": "bind", "source": "` + p + `/data", "target": "/d"},
	  {"type": "bind", "source": "` + p + `/link", "target": "/l"},
	  {"type": "bind", "source": "` + p + `/missing", "target": "/m"}]}}}`
	bin := fakeCompose(t, model, `level=warning msg="The \"DB_PASSWORD\" variable is not set. Defaulting to a blank string."`, 0)
	doc := runResolve(t, bin, "--workspace", ws, "--dir", p, "--project", "tl-p-1", "--file", "compose.yaml", "--profile", "test")
	if !doc.OK || len(doc.Unset) != 1 || doc.Unset[0] != "DB_PASSWORD" {
		t.Fatalf("doc %+v", doc)
	}
	real := doc.Real
	if real[p+"/data"] == "" || !compose.Within(real[p+"/data"], ws) {
		t.Fatalf("data resolved to %q", real[p+"/data"])
	}
	if real[p+"/link"] != "/etc" || real[p+"/missing"] != "" {
		t.Fatalf("real %v", real)
	}
	args, _ := os.ReadFile(filepath.Join(filepath.Dir(bin), "args"))
	if !strings.Contains(string(args), "-p tl-p-1 --project-directory "+p+" -f "+p+"/compose.yaml --profile test config --format json") {
		t.Fatalf("compose ran with %q", args)
	}
}

func TestResolveTurnsAFileOutsideTheWorkspaceIntoARefusal(t *testing.T) {
	ws := t.TempDir()
	p := filepath.Join(ws, "p")
	if err := os.MkdirAll(p, 0o755); err != nil {
		t.Fatal(err)
	}
	bin := fakeCompose(t, "", "env file /run/adele-secret/canary not found: stat /run/adele-secret/canary: no such file or directory", 1)
	doc := runResolve(t, bin, "--workspace", ws, "--dir", p, "--project", "tl-p-1")
	if doc.OK || doc.Refusal == nil || doc.Refusal.Setting != "env_file" || doc.Refusal.Value != "/run/adele-secret/canary" {
		t.Fatalf("doc %+v", doc)
	}
	bin = fakeCompose(t, "", "services.db.image must be a string", 1)
	if doc := runResolve(t, bin, "--workspace", ws, "--dir", p, "--project", "tl-p-1"); doc.OK || doc.Refusal != nil || doc.Error == "" {
		t.Fatalf("a project's own error: %+v", doc)
	}
}

func TestResolveRefusesADirOutsideTheWorkspace(t *testing.T) {
	var out, errb bytes.Buffer
	if code := resolve(env(func(string) string { return "" }), []string{"--workspace", "/w", "--dir", "/etc", "--project", "tl-p-1"}, &out, &errb); code != exitUsage {
		t.Fatalf("exit %d", code)
	}
}
