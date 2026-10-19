package buildctx

import (
	"archive/tar"
	"bytes"
	"errors"
	"io"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"
	"time"
)

func TestIgnore(t *testing.T) {
	cases := []struct {
		name, ignore string
		excluded     []string
		included     []string
	}{
		{"glob", "*.log", []string{"a.log", "x.log"}, []string{"dir/a.log", "a.txt", "log"}},
		{"double star", "**/node_modules", []string{"node_modules", "node_modules/x", "a/b/node_modules/c"}, []string{"a/node_modulesx"}},
		{"exception after", "*.log\n!keep.log", []string{"a.log"}, []string{"keep.log"}},
		{"exception before loses", "!keep.log\n*.log", []string{"keep.log"}, nil},
		{"directory", "build", []string{"build", "build/out/x.o"}, []string{"src/build", "builder"}},
		{"leading slash and dot", "/secret\n./tmp/", []string{"secret", "secret/k", "tmp/x"}, []string{"a/secret"}},
		{"comments and blanks", "# *.go\n\n   \nvendor", []string{"vendor/a"}, []string{"main.go"}},
		{"question and class", "?.txt\nfile[0-9]", []string{"a.txt", "file7"}, []string{"ab.txt", "filex"}},
		{"star in segment", "docs/*.md", []string{"docs/a.md"}, []string{"docs/sub/a.md", "a.md"}},
		{"middle double star", "a/**/z", []string{"a/z", "a/b/c/z", "a/b/z/q"}, []string{"b/z"}},
		{"reinclude under dir", "dir\n!dir/keep", []string{"dir", "dir/other"}, []string{"dir/keep", "dir/keep/x"}},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			ig, err := ParseIgnore([]byte(c.ignore))
			if err != nil {
				t.Fatal(err)
			}
			for _, p := range c.excluded {
				if !ig.Excluded(p) {
					t.Errorf("%q not excluded", p)
				}
			}
			for _, p := range c.included {
				if ig.Excluded(p) {
					t.Errorf("%q excluded", p)
				}
			}
		})
	}
	if _, err := ParseIgnore([]byte("a[")); err == nil {
		t.Error("a bad pattern parsed")
	}
	if _, err := ParseIgnore([]byte("!")); err == nil {
		t.Error("a bare ! parsed")
	}
	var nilIg *Ignore
	if nilIg.Excluded("x") {
		t.Error("nil Ignore excludes")
	}
}

func TestMayReinclude(t *testing.T) {
	ig, _ := ParseIgnore([]byte("dir\nother\n!dir/keep\n!**/x"))
	if !ig.mayReinclude("dir") {
		t.Error("dir/keep could be re-included")
	}
	ig2, _ := ParseIgnore([]byte("dir\n!src/keep"))
	if ig2.mayReinclude("dir") {
		t.Error("nothing under dir can be re-included")
	}
	if !ig.mayReinclude("other") {
		t.Error("**/x could match under other")
	}
}

type tree struct{ ws, ctx string }

// mk writes files under root: a map of relative path to content; a trailing "/" makes a directory.
func mk(t *testing.T, root string, files map[string]string) {
	t.Helper()
	for p, content := range files {
		full := filepath.Join(root, p)
		if strings.HasSuffix(p, "/") {
			if err := os.MkdirAll(full, 0o755); err != nil {
				t.Fatal(err)
			}
			continue
		}
		if err := os.MkdirAll(filepath.Dir(full), 0o755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(full, []byte(content), 0o644); err != nil {
			t.Fatal(err)
		}
	}
}

func newTree(t *testing.T, files map[string]string) tree {
	t.Helper()
	ws, err := filepath.EvalSymlinks(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	ctx := filepath.Join(ws, "app")
	mk(t, ctx, files)
	return tree{ws, ctx}
}

func rels(c *Context) []string {
	var out []string
	for _, e := range c.Entries {
		out = append(out, e.Rel)
	}
	return out
}

func readTar(t *testing.T, c *Context) map[string]*tar.Header {
	t.Helper()
	var buf bytes.Buffer
	if err := c.WriteTar(&buf); err != nil {
		t.Fatal(err)
	}
	out := map[string]*tar.Header{}
	tr := tar.NewReader(&buf)
	for {
		h, err := tr.Next()
		if err == io.EOF {
			break
		}
		if err != nil {
			t.Fatal(err)
		}
		body, _ := io.ReadAll(tr)
		h.PAXRecords = map[string]string{"body": string(body)}
		out[h.Name] = h
	}
	return out
}

func TestWalkIgnoreAndTar(t *testing.T) {
	tr := newTree(t, map[string]string{
		"Dockerfile":         "FROM alpine\n",
		".dockerignore":      "*.log\n!keep.log\nnode_modules\nDockerfile\n.dockerignore\n",
		"a.log":              "x",
		"keep.log":           "kept",
		"src/main.go":        "package main",
		"node_modules/x/y":   "big",
		"empty/":             "",
		"bin/run.sh":         "#!/bin/sh",
		"node_modules/x/z/q": "q",
	})
	if err := os.Chmod(filepath.Join(tr.ctx, "bin/run.sh"), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink("../../etc/passwd", filepath.Join(tr.ctx, "out")); err != nil {
		t.Fatal(err)
	}
	c, err := Walk(tr.ctx, filepath.Join(tr.ctx, "Dockerfile"), tr.ws, DefaultLimits)
	if err != nil {
		t.Fatal(err)
	}
	want := []string{".dockerignore", "Dockerfile", "bin", "bin/run.sh", "empty", "keep.log", "out", "src", "src/main.go"}
	if got := rels(c); !reflect.DeepEqual(got, want) {
		t.Fatalf("entries %v, want %v", got, want)
	}
	if c.DockerfileName != "Dockerfile" || c.Dir != tr.ctx {
		t.Errorf("name %q dir %q", c.DockerfileName, c.Dir)
	}
	hs := readTar(t, c)
	if len(hs) != len(want) {
		t.Fatalf("%d headers", len(hs))
	}
	for name, h := range hs {
		if h.Uid != 0 || h.Gid != 0 || h.Uname != "" || h.Gname != "" {
			t.Errorf("%s owner %d:%d %q:%q", name, h.Uid, h.Gid, h.Uname, h.Gname)
		}
	}
	if h := hs["out"]; h == nil || h.Typeflag != tar.TypeSymlink || h.Linkname != "../../etc/passwd" || h.PAXRecords["body"] != "" {
		t.Errorf("symlink header %+v", h)
	}
	if h := hs["bin/"]; h == nil || h.Typeflag != tar.TypeDir {
		t.Errorf("dir header %+v", h)
	}
	if h := hs["bin/run.sh"]; h == nil || h.Typeflag != tar.TypeReg || h.Mode != 0o755 || h.PAXRecords["body"] != "#!/bin/sh" {
		t.Errorf("file header %+v", h)
	}
	if h := hs["keep.log"]; h == nil || h.Mode != 0o644 || h.PAXRecords["body"] != "kept" {
		t.Errorf("keep.log header %+v", h)
	}
}

func TestWalkLinkOutsideWorkspaceNotFollowed(t *testing.T) {
	outside := t.TempDir()
	secret := filepath.Join(outside, "secret")
	if err := os.WriteFile(secret, []byte("TOPSECRETCONTENT"), 0o600); err != nil {
		t.Fatal(err)
	}
	tr := newTree(t, map[string]string{"Dockerfile": "FROM alpine\n"})
	if err := os.Symlink(secret, filepath.Join(tr.ctx, "s")); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink(outside, filepath.Join(tr.ctx, "d")); err != nil {
		t.Fatal(err)
	}
	c, err := Walk(tr.ctx, filepath.Join(tr.ctx, "Dockerfile"), tr.ws, DefaultLimits)
	if err != nil {
		t.Fatal(err)
	}
	var buf bytes.Buffer
	if err := c.WriteTar(&buf); err != nil {
		t.Fatal(err)
	}
	if bytes.Contains(buf.Bytes(), []byte("TOPSECRETCONTENT")) {
		t.Fatal("the link's target is in the archive")
	}
	hs := readTar(t, c)
	if h := hs["s"]; h == nil || h.Typeflag != tar.TypeSymlink || h.Linkname != secret {
		t.Errorf("s: %+v", h)
	}
	if h := hs["d"]; h == nil || h.Typeflag != tar.TypeSymlink {
		t.Errorf("d: %+v", h)
	}
	if _, ok := hs["d/secret"]; ok {
		t.Error("walked through a directory link")
	}
}

func TestWalkRefusals(t *testing.T) {
	tr := newTree(t, map[string]string{"Dockerfile": "FROM alpine\n"})
	outside := t.TempDir()
	mk(t, outside, map[string]string{"Dockerfile": "FROM alpine\n"})
	linkCtx := filepath.Join(tr.ws, "linkctx")
	if err := os.Symlink(outside, linkCtx); err != nil {
		t.Fatal(err)
	}
	linkDf := filepath.Join(tr.ctx, "Df")
	if err := os.Symlink(filepath.Join(outside, "Dockerfile"), linkDf); err != nil {
		t.Fatal(err)
	}
	cases := []struct {
		name, dir, df, setting string
	}{
		{"context outside", outside, filepath.Join(outside, "Dockerfile"), "build.context"},
		{"context link outside", linkCtx, filepath.Join(tr.ctx, "Dockerfile"), "build.context"},
		{"dockerfile outside", tr.ctx, filepath.Join(outside, "Dockerfile"), "build.dockerfile"},
		{"dockerfile link outside", tr.ctx, linkDf, "build.dockerfile"},
		{"context missing", filepath.Join(tr.ws, "nope"), filepath.Join(tr.ctx, "Dockerfile"), "build.context"},
		{"dockerfile missing", tr.ctx, filepath.Join(tr.ctx, "nope"), "build.dockerfile"},
		{"context relative", "app", filepath.Join(tr.ctx, "Dockerfile"), "build.context"},
		{"context a file", filepath.Join(tr.ctx, "Dockerfile"), filepath.Join(tr.ctx, "Dockerfile"), "build.context"},
		{"dockerfile a dir", tr.ctx, tr.ctx, "build.dockerfile"},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			_, err := Walk(c.dir, c.df, tr.ws, DefaultLimits)
			var r *Refusal
			if !errors.As(err, &r) {
				t.Fatalf("err %v, want a refusal", err)
			}
			if r.Setting != c.setting || r.Remedy == "" || !strings.Contains(r.Error(), r.Setting) {
				t.Errorf("refusal %+v", r)
			}
		})
	}
	if _, err := Walk(tr.ctx, filepath.Join(tr.ctx, "Dockerfile"), filepath.Join(tr.ws, "none"), DefaultLimits); err == nil {
		t.Error("a missing workspace walked")
	}
}

func TestWalkDockerfileOutsideContext(t *testing.T) {
	tr := newTree(t, map[string]string{"main.go": "x"})
	df := filepath.Join(tr.ws, "docker", "Dockerfile.app")
	mk(t, tr.ws, map[string]string{"docker/Dockerfile.app": "FROM alpine\n"})
	c, err := Walk(tr.ctx, df, tr.ws, DefaultLimits)
	if err != nil {
		t.Fatal(err)
	}
	if !strings.HasPrefix(c.DockerfileName, ".timelike-dockerfile-") || len(c.DockerfileName) != len(".timelike-dockerfile-")+6 {
		t.Fatalf("name %q", c.DockerfileName)
	}
	last := c.Entries[len(c.Entries)-1]
	if last.Rel != c.DockerfileName || last.Abs != df {
		t.Errorf("last entry %+v", last)
	}
	hs := readTar(t, c)
	if h := hs[c.DockerfileName]; h == nil || h.PAXRecords["body"] != "FROM alpine\n" {
		t.Errorf("injected %+v", h)
	}
	// A Dockerfile in an ignored, skipped directory is still sent.
	tr2 := newTree(t, map[string]string{"build/Dockerfile": "FROM alpine\n", "build/junk": "j", ".dockerignore": "build\n"})
	c2, err := Walk(tr2.ctx, filepath.Join(tr2.ctx, "build/Dockerfile"), tr2.ws, DefaultLimits)
	if err != nil {
		t.Fatal(err)
	}
	if got := rels(c2); !reflect.DeepEqual(got, []string{".dockerignore", "build/Dockerfile"}) || c2.DockerfileName != "build/Dockerfile" {
		t.Errorf("entries %v name %q", got, c2.DockerfileName)
	}
}

func TestWalkReincludeUnderExcludedDir(t *testing.T) {
	tr := newTree(t, map[string]string{"Dockerfile": "FROM a\n", "dir/keep": "k", "dir/drop": "d", ".dockerignore": "dir\n!dir/keep\n"})
	c, err := Walk(tr.ctx, filepath.Join(tr.ctx, "Dockerfile"), tr.ws, DefaultLimits)
	if err != nil {
		t.Fatal(err)
	}
	if got := rels(c); !reflect.DeepEqual(got, []string{".dockerignore", "Dockerfile", "dir/keep"}) {
		t.Errorf("entries %v", got)
	}
}

func TestWalkSkipsSpecial(t *testing.T) {
	tr := newTree(t, map[string]string{"Dockerfile": "FROM a\n"})
	if err := mkfifo(filepath.Join(tr.ctx, "pipe")); err != nil {
		t.Skip("no fifo:", err)
	}
	c, err := Walk(tr.ctx, filepath.Join(tr.ctx, "Dockerfile"), tr.ws, DefaultLimits)
	if err != nil {
		t.Fatal(err)
	}
	if got := rels(c); !reflect.DeepEqual(got, []string{"Dockerfile"}) {
		t.Errorf("entries %v", got)
	}
}

func digestOf(t *testing.T, tr tree) string {
	t.Helper()
	c, err := Walk(tr.ctx, filepath.Join(tr.ctx, "Dockerfile"), tr.ws, DefaultLimits)
	if err != nil {
		t.Fatal(err)
	}
	return c.Digest
}

func TestDigest(t *testing.T) {
	tr := newTree(t, map[string]string{"Dockerfile": "FROM a\n", "f": "one", "d/g": "two"})
	d0 := digestOf(t, tr)
	old := time.Now().Add(-48 * time.Hour)
	for _, p := range []string{"f", "d/g", "d"} {
		if err := os.Chtimes(filepath.Join(tr.ctx, p), old, old); err != nil {
			t.Fatal(err)
		}
	}
	if d := digestOf(t, tr); d != d0 {
		t.Fatal("digest moved with mtimes only")
	}
	if err := os.WriteFile(filepath.Join(tr.ctx, "f"), []byte("ONE"), 0o644); err != nil {
		t.Fatal(err)
	}
	d1 := digestOf(t, tr)
	if d1 == d0 {
		t.Fatal("digest did not move with content")
	}
	if err := os.Chmod(filepath.Join(tr.ctx, "f"), 0o600); err != nil {
		t.Fatal(err)
	}
	d2 := digestOf(t, tr)
	if d2 == d1 {
		t.Fatal("digest did not move with a mode")
	}
	if err := os.Symlink("f", filepath.Join(tr.ctx, "l")); err != nil {
		t.Fatal(err)
	}
	d3 := digestOf(t, tr)
	if d3 == d2 {
		t.Fatal("digest did not move with a link")
	}
	os.Remove(filepath.Join(tr.ctx, "l"))
	if err := os.Symlink("d", filepath.Join(tr.ctx, "l")); err != nil {
		t.Fatal(err)
	}
	if d := digestOf(t, tr); d == d3 {
		t.Fatal("digest did not move with a link's target")
	}
}

func TestWriteTarRefusesChange(t *testing.T) {
	tr := newTree(t, map[string]string{"Dockerfile": "FROM a\n", "f": "one"})
	walk := func() *Context {
		c, err := Walk(tr.ctx, filepath.Join(tr.ctx, "Dockerfile"), tr.ws, DefaultLimits)
		if err != nil {
			t.Fatal(err)
		}
		return c
	}
	f := filepath.Join(tr.ctx, "f")
	for _, change := range []func(){
		func() { os.WriteFile(f, []byte("longer"), 0o644) },
		func() { os.WriteFile(f, []byte("two"), 0o644) }, // same size, other content
		func() { os.Chmod(f, 0o700) },
		func() { os.Remove(f); os.Symlink("Dockerfile", f) },
		func() { os.Remove(f) },
	} {
		os.Remove(f)
		os.WriteFile(f, []byte("one"), 0o644)
		c := walk()
		change()
		if err := c.WriteTar(io.Discard); err == nil {
			t.Error("a change since Walk was written")
		}
	}
	os.Remove(f)
	os.Symlink("a", f)
	c := walk()
	os.Remove(f)
	os.Symlink("b", f)
	if err := c.WriteTar(io.Discard); err == nil {
		t.Error("a retargeted link was written")
	}
}

func TestTooBig(t *testing.T) {
	tr := newTree(t, map[string]string{"Dockerfile": "FROM a\n", "a": strings.Repeat("x", 100), "b": "y", "c": "z"})
	df := filepath.Join(tr.ctx, "Dockerfile")
	_, err := Walk(tr.ctx, df, tr.ws, Limits{MaxBytes: 50})
	var tb *TooBig
	if !errors.As(err, &tb) || tb.What != "bytes" || tb.Limit != 50 || !strings.Contains(tb.Error(), ".dockerignore") {
		t.Fatalf("bytes: %v", err)
	}
	_, err = Walk(tr.ctx, df, tr.ws, Limits{MaxEntries: 3})
	if !errors.As(err, &tb) || tb.What != "entries" || tb.Limit != 3 || !strings.Contains(tb.Error(), "3 entries") {
		t.Fatalf("entries: %v", err)
	}
	if got := (&TooBig{What: "bytes", Limit: 256 << 20}).Error(); !strings.Contains(got, "over 256 MiB") {
		t.Errorf("%q", got)
	}
	// The injected Dockerfile counts too.
	mk(t, tr.ws, map[string]string{"Df": "FROM a\n"})
	if _, err = Walk(tr.ctx, filepath.Join(tr.ws, "Df"), tr.ws, Limits{MaxEntries: 4}); !errors.As(err, &tb) {
		t.Fatalf("injected: %v", err)
	}
	if _, err = Walk(tr.ctx, df, tr.ws, Limits{MaxEntries: 4, MaxBytes: 109}); err != nil {
		t.Fatalf("at the bounds: %v", err)
	}
}

func TestScanDockerfile(t *testing.T) {
	cases := []struct {
		name, text string
		args       map[string]string
		target     string
		bases      []string
		stages     []string
		refusal    string
		err        string
	}{
		{name: "simple", text: "FROM alpine:3.20\nRUN echo hi\n", bases: []string{"alpine:3.20"}, stages: []string{""}},
		{name: "arg default", text: "ARG BASE=debian\nARG TAG=12\nFROM ${BASE}:$TAG\n", bases: []string{"debian:12"}, stages: []string{""}},
		{name: "arg overridden", text: "ARG BASE=debian\nARG TAG=12\nFROM ${BASE}:$TAG\n", args: map[string]string{"TAG": "13"},
			bases: []string{"debian:13"}, stages: []string{""}},
		{name: "arg fallback", text: "ARG V\nFROM node:${V:-20}\n", bases: []string{"node:20"}, stages: []string{""}},
		{name: "undeclared arg ignored", text: "FROM node:${V:-20}\n", args: map[string]string{"V": "22"}, bases: []string{"node:20"}, stages: []string{""}},
		{name: "multi stage", text: "FROM golang:1.27 AS Build\nRUN go build\nFROM build AS test\nFROM scratch\nCOPY --from=build /x /x\nCOPY --from=0 /y /y\nCOPY --from=busybox:1 /bin/sh /sh\nCOPY --from=golang:1.27 /a /a\n",
			bases: []string{"golang:1.27", "busybox:1"}, stages: []string{"build", "test", ""}},
		{name: "platform and case", text: "from --platform=$BUILDPLATFORM python:3 as base\ncopy --from=BASE / /\n",
			bases: []string{"python:3"}, stages: []string{"base"}},
		{name: "continuation and comments", text: "# a comment\nFROM \\\n  # inside\n\n  alpine \\\n  AS a\nRUN apk add \\\n  curl\n",
			bases: []string{"alpine"}, stages: []string{"a"}},
		{name: "escape directive", text: "# escape=`\nFROM `\n  alpine\nRUN dir c:\\\n", bases: []string{"alpine"}, stages: []string{""}},
		{name: "stage arg in copy from", text: "ARG IMG=redis:7\nFROM alpine\nARG IMG\nCOPY --from=$IMG /a /a\n",
			bases: []string{"alpine", "redis:7"}, stages: []string{""}},
		{name: "mount from image", text: "FROM alpine\nRUN --mount=type=bind,from=tools:1,target=/t true\n",
			bases: []string{"alpine", "tools:1"}, stages: []string{""}},
		{name: "target", text: "FROM a AS one\nFROM b AS two\n", target: "TWO", bases: []string{"a", "b"}, stages: []string{"one", "two"}},
		{name: "secret", text: "FROM a\nRUN --mount=type=secret,id=k cat /run/secrets/k\n", refusal: "build secrets"},
		{name: "ssh", text: "FROM a\nRUN --mount=type=ssh git clone x\n", refusal: "build ssh"},
		{name: "network", text: "FROM a\nRUN --network=host curl x\n", refusal: "build network"},
		{name: "network default", text: "FROM a\nRUN --network=default curl x\n", bases: []string{"a"}, stages: []string{""}},
		{name: "insecure", text: "FROM a\nRUN --security=insecure x\n", refusal: "build entitlements"},
		{name: "first refusal", text: "FROM a\nRUN --network=none x\nRUN --mount=type=secret,id=k x\n", refusal: "build network"},
		{name: "flag after command", text: "FROM a\nRUN echo --network=host\n", bases: []string{"a"}, stages: []string{""}},
		{name: "unknown target", text: "FROM a AS one\n", target: "two", err: "names no stage"},
		{name: "no from", text: "ARG X=1\n", err: "no FROM"},
		{name: "before from", text: "RUN x\nFROM a\n", err: "before the first FROM"},
		{name: "empty from", text: "ARG B\nFROM $B\n", err: "empty"},
		{name: "bad index", text: "FROM a\nCOPY --from=3 /a /a\n", err: "earlier stage"},
		{name: "bad escape", text: "# escape=x\nFROM a\n", err: "escape"},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			sc, err := ScanDockerfile([]byte(c.text), c.args, c.target)
			if c.err != "" {
				if err == nil || !strings.Contains(err.Error(), c.err) {
					t.Fatalf("err %v, want %q", err, c.err)
				}
				return
			}
			if err != nil {
				t.Fatal(err)
			}
			if c.refusal != "" {
				if sc.Refusal == nil || sc.Refusal.Setting != c.refusal || sc.Refusal.Remedy == "" {
					t.Fatalf("refusal %+v, want %s", sc.Refusal, c.refusal)
				}
				return
			}
			if sc.Refusal != nil {
				t.Fatalf("refusal %+v", sc.Refusal)
			}
			if !reflect.DeepEqual(sc.Bases, c.bases) || !reflect.DeepEqual(sc.Stages, c.stages) {
				t.Errorf("bases %q stages %q, want %q %q", sc.Bases, sc.Stages, c.bases, c.stages)
			}
		})
	}
}

func TestExpand(t *testing.T) {
	v := map[string]string{"A": "a", "E": ""}
	cases := map[string]string{
		"$A":         "a",
		"${A}x":      "ax",
		"${B:-b}":    "b",
		"${E:-e}":    "e",
		"${E-e}":     "",
		"${B-b}":     "b",
		"${A:+p}":    "p",
		"${B:+p}":    "",
		"${A+p}":     "p",
		"${E+p}":     "p",
		"\\$A":       "$A",
		"$":          "$",
		"$-":         "$-",
		"${A":        "${A",
		`"$A"`:       "a",
		"${B:-${A}}": "a",
	}
	for in, want := range cases {
		if got := expand(in, v, '\\'); got != want {
			t.Errorf("expand(%q) = %q, want %q", in, got, want)
		}
	}
}

func TestKeyAndTag(t *testing.T) {
	k := Key("d", "Dockerfile", map[string]string{"B": "2", "A": "1"}, "t")
	if len(k) != 64 || k != Key("d", "Dockerfile", map[string]string{"A": "1", "B": "2"}, "t") {
		t.Fatalf("key %q", k)
	}
	for _, other := range []string{
		Key("e", "Dockerfile", map[string]string{"A": "1", "B": "2"}, "t"),
		Key("d", "Df", map[string]string{"A": "1", "B": "2"}, "t"),
		Key("d", "Dockerfile", map[string]string{"A": "1", "B": "3"}, "t"),
		Key("d", "Dockerfile", map[string]string{"A": "1"}, "t"),
		Key("d", "Dockerfile", map[string]string{"A": "1", "B": "2"}, ""),
	} {
		if other == k {
			t.Error("key did not move")
		}
	}
	if got := Tag("tl-App-1a2b3c", "Web Server", k); got != "tl-app-1a2b3c-web-server:"+k[:12] {
		t.Errorf("tag %q", got)
	}
	if got := Tag("tl-x", "db_1.2", "ABC"); got != "tl-x-db_1.2:abc" {
		t.Errorf("tag %q", got)
	}
}
