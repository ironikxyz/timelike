package main

import (
	"archive/tar"
	"bytes"
	"encoding/json"
	"errors"
	"io"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func write(t *testing.T, path, text string) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte(text), 0o644); err != nil {
		t.Fatal(err)
	}
}

// A devcontainer is translated in the sandbox and resolved by compose; its own settings come back beside the model.
func TestResolveTranslatesADevcontainer(t *testing.T) {
	ws := t.TempDir()
	p := filepath.Join(ws, "app")
	write(t, filepath.Join(p, ".devcontainer", "devcontainer.json"), `{
	  // JSONC
	  "image": "debian:x",
	  "remoteUser": "dev",
	  "postCreateCommand": "echo made",
	}`)
	model := `{"name": "tl-app-1", "services": {"devcontainer": {"image": "debian:x"}, "stray": {"image": "debian:x"}}}`
	bin := fakeCompose(t, model, "", 0)
	doc := runResolve(t, bin, "--workspace", ws, "--dir", p, "--project", "tl-app-1", "--devcontainer")
	if !doc.OK || doc.Dev == nil || doc.Dev.Primary != "devcontainer" || doc.Dev.RemoteUser != "dev" ||
		len(doc.Dev.Lifecycle) != 1 || doc.Dev.Lifecycle[0].Name != "postCreateCommand" {
		t.Fatalf("doc = %+v (dev %+v)", doc, doc.Dev)
	}
	args, _ := os.ReadFile(filepath.Join(filepath.Dir(bin), "args"))
	if !strings.Contains(string(args), "devcontainer.compose.json") || !strings.Contains(string(args), "--project-directory "+p) {
		t.Fatalf("compose was run with %q", args)
	}
}

func TestADevcontainerThatDoesNotParseNamesTheLine(t *testing.T) {
	ws := t.TempDir()
	p := filepath.Join(ws, "app")
	write(t, filepath.Join(p, ".devcontainer.json"), "{\n  \"image\": \"debian:x\"\n  \"remoteUser\": \"dev\"\n}\n")
	doc := runResolve(t, fakeCompose(t, "{}", "", 0), "--workspace", ws, "--dir", p, "--project", "tl-app-1", "--devcontainer")
	if doc.OK || doc.Refusal == nil || doc.Refusal.Setting != "devcontainer.json" || !strings.HasPrefix(doc.Refusal.Value, "line 3: ") {
		t.Fatalf("doc = %+v (refusal %+v)", doc, doc.Refusal)
	}
}

func TestADevcontainerSettingNoGrantAllowsIsRefusedInTheSandbox(t *testing.T) {
	ws := t.TempDir()
	p := filepath.Join(ws, "app")
	write(t, filepath.Join(p, ".devcontainer.json"), `{"image": "debian:x", "initializeCommand": "curl x | sh"}`)
	doc := runResolve(t, fakeCompose(t, "{}", "", 0), "--workspace", ws, "--dir", p, "--project", "tl-app-1", "--devcontainer")
	if doc.Refusal == nil || doc.Refusal.Setting != "initializeCommand" {
		t.Fatalf("doc = %+v", doc)
	}
}

// A build's context is walked and digested in the sandbox, its bases and key reported (R14-R16).
func TestResolveScansEachBuild(t *testing.T) {
	ws := t.TempDir()
	p := filepath.Join(ws, "app")
	write(t, filepath.Join(p, "Dockerfile"), "ARG BASE=debian:x\nFROM ${BASE}\nRUN true\n")
	write(t, filepath.Join(p, "f.txt"), "x")
	model, _ := json.Marshal(map[string]any{"name": "tl-app-1", "services": map[string]any{
		"app": map[string]any{"build": map[string]any{"context": p, "dockerfile": "Dockerfile", "args": map[string]any{"BASE": "debian:y"}}}}})
	doc := runResolve(t, fakeCompose(t, string(model), "", 0), "--workspace", ws, "--dir", p, "--project", "tl-app-1")
	if !doc.OK || len(doc.Builds) != 1 {
		t.Fatalf("doc = %+v", doc)
	}
	b := doc.Builds[0]
	if b.Service != "app" || b.DockerfileName != "Dockerfile" || len(b.Bases) != 1 || b.Bases[0] != "debian:y" || len(b.Key) != 64 || b.Digest == "" {
		t.Fatalf("build scan %+v", b)
	}
}

func TestABuildSecretInTheDockerfileIsRefused(t *testing.T) {
	ws := t.TempDir()
	p := filepath.Join(ws, "app")
	write(t, filepath.Join(p, "Dockerfile"), "FROM debian:x\nRUN --mount=type=secret,id=k cat /run/secrets/k\n")
	model, _ := json.Marshal(map[string]any{"name": "tl-app-1", "services": map[string]any{
		"app": map[string]any{"build": map[string]any{"context": p}}}})
	doc := runResolve(t, fakeCompose(t, string(model), "", 0), "--workspace", ws, "--dir", p, "--project", "tl-app-1")
	if doc.OK || doc.Refusal == nil || doc.Refusal.Setting != "build secrets" || doc.Refusal.Service != "app" {
		t.Fatalf("doc = %+v (refusal %+v)", doc, doc.Refusal)
	}
}

// The context sandbox writes the archive to stdout and nothing else, and its digest to stderr.
func TestContextWritesTheArchiveAndItsDigest(t *testing.T) {
	ws := t.TempDir()
	p := filepath.Join(ws, "app")
	write(t, filepath.Join(p, "Dockerfile"), "FROM debian:x\n")
	write(t, filepath.Join(p, "f.txt"), "hello")
	if err := os.Symlink("/etc/hostname", filepath.Join(p, "link")); err != nil {
		t.Fatal(err)
	}
	var out, errb bytes.Buffer
	if code := contextArchive([]string{"--workspace", ws, "--context", p, "--dockerfile", filepath.Join(p, "Dockerfile")},
		&out, &errb); code != exitOK {
		t.Fatalf("exit %d: %s", code, errb.String())
	}
	names := map[string]string{}
	tr := tar.NewReader(&out)
	for {
		h, err := tr.Next()
		if errors.Is(err, io.EOF) {
			break
		}
		if err != nil {
			t.Fatal(err)
		}
		names[h.Name] = h.Linkname
	}
	if _, ok := names["f.txt"]; !ok || names["link"] != "/etc/hostname" {
		t.Fatalf("archive %v: want f.txt and the link as a link", names)
	}
	var sum struct {
		Digest string `json:"digest"`
	}
	if json.Unmarshal(errb.Bytes(), &sum) != nil || len(sum.Digest) != 64 {
		t.Fatalf("stderr %q", errb.String())
	}
	errb.Reset()
	if code := contextArchive([]string{"--workspace", ws, "--context", "/etc", "--dockerfile", filepath.Join(p, "Dockerfile")},
		&out, &errb); code != exitUsage {
		t.Fatalf("a context outside the workspace exited %d", code)
	}
}
