//go:build linux

package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"syscall"
	"testing"

	"timelike/adele/internal/volcopy"
)

func volumeTree(t *testing.T) (src, dst string) {
	t.Helper()
	base := t.TempDir()
	src, dst = filepath.Join(base, "src"), filepath.Join(base, "dst")
	for _, d := range []string{filepath.Join(src, "pg", "base"), dst} {
		if err := os.MkdirAll(d, 0o755); err != nil {
			t.Fatal(err)
		}
	}
	if err := os.WriteFile(filepath.Join(src, "pg", "base", "1"), []byte("0123456789"), 0o600); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink("../../elsewhere", filepath.Join(src, "pg", "link")); err != nil {
		t.Fatal(err)
	}
	return src, dst
}

func runVolume(t *testing.T, args ...string) (int, map[string]any, string) {
	t.Helper()
	var out, errb bytes.Buffer
	code := run(append([]string{"volume"}, args...), func(string) string { return "" }, &out, &errb)
	var a map[string]any
	if out.Len() > 0 {
		if strings.Count(out.String(), "\n") != 1 {
			t.Fatalf("stdout is not one line: %q", out.String())
		}
		if err := json.Unmarshal(out.Bytes(), &a); err != nil {
			t.Fatalf("stdout is not JSON: %q", out.String())
		}
	}
	if strings.Count(strings.TrimSuffix(errb.String(), "\n"), "\n") > 0 && code != exitUsage {
		t.Errorf("stderr is more than one line: %q", errb.String())
	}
	return code, a, errb.String()
}

func TestVolumeCopyAndDigest(t *testing.T) {
	src, dst := volumeTree(t)
	code, a, stderr := runVolume(t, "measure", "--src", src)
	if code != exitOK || a["bytes"] != 10.0 || a["files"] != 4.0 || a["sockets"] != 0.0 || a["digest"] != nil {
		t.Fatalf("measure: %d %v %s", code, a, stderr)
	}
	code, d, _ := runVolume(t, "digest", "--src", src)
	if code != exitOK || !strings.HasPrefix(fmt.Sprint(d["digest"]), "sha256:") || d["copy_digest"] != nil {
		t.Fatalf("digest: %d %v", code, d)
	}
	code, c, stderr := runVolume(t, "copy", "--src", src, "--dst", dst, "--max-bytes", "10")
	if code != exitOK || c["digest"] != d["digest"] || c["copy_digest"] != d["digest"] || c["bytes"] != 10.0 {
		t.Fatalf("copy: %d %v %s", code, c, stderr)
	}
	if err := os.WriteFile(filepath.Join(dst, "stale"), []byte("x"), 0o644); err != nil {
		t.Fatal(err)
	}
	code, r, stderr := runVolume(t, "restore", "--src", src, "--dst", dst)
	if code != exitOK || r["copy_digest"] != d["digest"] {
		t.Fatalf("restore: %d %v %s", code, r, stderr)
	}
}

func TestVolumeExits(t *testing.T) {
	src, dst := volumeTree(t)

	code, a, stderr := runVolume(t, "copy", "--src", src, "--dst", dst, "--max-bytes", "9")
	if code != exitOverBudget || a["bytes"] != 10.0 || !strings.Contains(stderr, "past the byte budget") {
		t.Errorf("over budget: %d %v %q", code, a, stderr)
	}
	if names, _ := os.ReadDir(dst); len(names) != 0 {
		t.Errorf("an over-budget copy wrote %d entries", len(names))
	}

	code, a, stderr = runVolume(t, "digest", "--src", filepath.Join(src, "missing\nname"))
	if code != exitFailure || a != nil || !strings.Contains(stderr, `missing\nname`) {
		t.Errorf("a missing source: %d %v %q", code, a, stderr)
	}

	defer func(c func(string, string, int64) (volcopy.Result, error)) { volCopy = c }(volCopy)
	volCopy = func(string, string, int64) (volcopy.Result, error) {
		return volcopy.Result{}, fmt.Errorf("%w: writing \"pg/base/1\": %w", volcopy.ErrNoSpace, syscall.ENOSPC)
	}
	if code, a, stderr := runVolume(t, "copy", "--src", src, "--dst", dst); code != exitNoSpace || a != nil ||
		!strings.Contains(stderr, "no space left in the target") {
		t.Errorf("no space: %d %v %q", code, a, stderr)
	}
	volCopy = func(string, string, int64) (volcopy.Result, error) {
		return volcopy.Result{}, &volcopy.UnsupportedError{Path: "dev/null", Kind: "character device"}
	}
	if code, _, stderr := runVolume(t, "copy", "--src", src, "--dst", dst); code != exitUnsupported ||
		!strings.Contains(stderr, `"dev/null" is a character device`) {
		t.Errorf("a device: %d %q", code, stderr)
	}

	for _, args := range [][]string{
		{},
		{"rename", "--src", src},
		{"measure"},
		{"copy", "--src", src},
		{"digest", "--src", src, "--dst", dst},
		{"restore", "--src", src, "--dst", dst, "--max-bytes", "1"},
		{"measure", "--src", src, "extra"},
		{"measure", "--bogus"},
	} {
		if code, a, _ := runVolume(t, args...); code != exitUsage || a != nil {
			t.Errorf("%q: %d %v, want usage", args, code, a)
		}
	}
}
