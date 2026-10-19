//go:build linux

package volcopy

import (
	"errors"
	"fmt"
	"io"
	"net"
	"os"
	"path/filepath"
	"strings"
	"syscall"
	"testing"
	"time"
)

// tree builds a source with every kind of entry the helper copies, a socket it does not, and links that point out
// of the tree. It returns the source and a directory beside it, outside it, holding what those links point at.
func tree(t *testing.T) (src, outside string) {
	t.Helper()
	base := t.TempDir()
	src, outside = filepath.Join(base, "src"), filepath.Join(base, "out")
	for _, d := range []string{src, outside, filepath.Join(src, "a", "b"), filepath.Join(src, "a-b"), filepath.Join(src, "g")} {
		must(t, os.MkdirAll(d, 0o755))
	}
	write(t, filepath.Join(outside, "secret"), "outside the tree")
	write(t, filepath.Join(src, "a", "b", "data"), "rows")
	write(t, filepath.Join(src, "a-b", "x"), "dash")
	write(t, filepath.Join(src, "empty"), "")
	write(t, filepath.Join(src, "with space\nand newline"), "odd name")
	write(t, filepath.Join(src, "suid"), "s")
	must(t, syscall.Chmod(filepath.Join(src, "suid"), 0o4755))
	must(t, syscall.Chmod(filepath.Join(src, "g"), 0o2775|0o1000)) // setgid and sticky on a directory
	must(t, os.Chmod(filepath.Join(src, "a", "b"), 0o700))
	must(t, os.Link(filepath.Join(src, "a", "b", "data"), filepath.Join(src, "hard")))
	must(t, os.Symlink("a/b/data", filepath.Join(src, "rel")))
	must(t, os.Symlink(filepath.Join(outside, "secret"), filepath.Join(src, "abs-out")))
	must(t, os.Symlink("../out", filepath.Join(src, "dir-out")))
	must(t, os.Symlink("nowhere", filepath.Join(src, "dangling")))
	must(t, syscall.Mkfifo(filepath.Join(src, "fifo"), 0o640))
	l, err := net.Listen("unix", filepath.Join(src, "s.sock"))
	if err != nil {
		t.Fatalf("a socket in the tree: %v", err)
	}
	t.Cleanup(func() { l.Close() })
	old := time.Date(2020, 1, 2, 3, 4, 5, 123456789, time.UTC)
	must(t, os.Chtimes(filepath.Join(src, "a", "b", "data"), old, old))
	must(t, os.Chtimes(filepath.Join(src, "a", "b"), old, old))
	return src, outside
}

func must(t *testing.T, err error) {
	t.Helper()
	if err != nil {
		t.Fatal(err)
	}
}

func write(t *testing.T, p, s string) {
	t.Helper()
	must(t, os.WriteFile(p, []byte(s), 0o644))
}

func emptyTarget(t *testing.T) string {
	t.Helper()
	d := filepath.Join(t.TempDir(), "dst")
	must(t, os.Mkdir(d, 0o755))
	return d
}

func TestMeasure(t *testing.T) {
	src, _ := tree(t)
	st, err := Measure(src)
	must(t, err)
	// rows + dash + "" + odd name + s, the hard link counted once.
	if want := int64(len("rows") + len("dash") + len("odd name") + len("s")); st.Bytes != want {
		t.Errorf("bytes %d, want %d", st.Bytes, want)
	}
	// a, a/b, a/b/data, a-b, a-b/x, g, empty, odd name, suid, hard, rel, abs-out, dir-out, dangling, fifo.
	if st.Files != 15 || st.Sockets != 1 {
		t.Errorf("files %d sockets %d, want 15 and 1", st.Files, st.Sockets)
	}
}

func TestCopyKeepsEverythingAndFollowsNoLink(t *testing.T) {
	src, outside := tree(t)
	dst := emptyTarget(t)
	srcAtime := time.Date(2019, 5, 6, 7, 8, 9, 0, time.UTC)
	mtime := time.Date(2020, 1, 2, 3, 4, 5, 123456789, time.UTC)
	must(t, os.Chtimes(filepath.Join(src, "a", "b", "data"), srcAtime, mtime))
	must(t, os.Chtimes(src, mtime, mtime))

	r, err := Copy(src, dst, -1)
	must(t, err)
	if r.SourceDigest != r.CopyDigest || !strings.HasPrefix(r.SourceDigest, "sha256:") || len(r.SourceDigest) != 71 {
		t.Fatalf("digests %q and %q", r.SourceDigest, r.CopyDigest)
	}
	_, d, err := Digest(src)
	must(t, err)
	if d != r.SourceDigest {
		t.Errorf("the digest during the copy %s is not the source's read again %s", r.SourceDigest, d)
	}
	if r.Files != 15 || r.Sockets != 1 {
		t.Errorf("files %d sockets %d", r.Files, r.Sockets)
	}

	if _, err := os.Lstat(filepath.Join(dst, "s.sock")); !errors.Is(err, os.ErrNotExist) {
		t.Errorf("the socket was copied: %v", err)
	}
	for name, target := range map[string]string{"abs-out": filepath.Join(outside, "secret"), "dir-out": "../out", "rel": "a/b/data", "dangling": "nowhere"} {
		fi, err := os.Lstat(filepath.Join(dst, name))
		must(t, err)
		if fi.Mode()&os.ModeSymlink == 0 {
			t.Errorf("%s is %v in the copy, not a link: it was followed", name, fi.Mode())
		}
		if got, _ := os.Readlink(filepath.Join(dst, name)); got != target {
			t.Errorf("%s points at %q, want %q", name, got, target)
		}
	}
	if fi, _ := os.Lstat(filepath.Join(dst, "fifo")); fi == nil || fi.Mode()&os.ModeNamedPipe == 0 {
		t.Errorf("the fifo is not a fifo in the copy")
	}
	a, _ := os.Lstat(filepath.Join(dst, "a", "b", "data"))
	h, _ := os.Lstat(filepath.Join(dst, "hard"))
	if !os.SameFile(a, h) {
		t.Errorf("the hard link is two files in the copy")
	}
	if fi, _ := os.Lstat(filepath.Join(dst, "g")); fi.Mode()&(os.ModeSetgid|os.ModeSticky) != os.ModeSetgid|os.ModeSticky {
		t.Errorf("the directory's setgid and sticky bits were lost: %v", fi.Mode())
	}
	if fi, _ := os.Lstat(filepath.Join(dst, "suid")); fi.Mode()&os.ModeSetuid == 0 {
		t.Errorf("the file's setuid bit was lost: %v", fi.Mode())
	}
	if fi, _ := os.Lstat(dst); !fi.ModTime().Equal(mtime) {
		t.Errorf("the target's root has mtime %v, want the source root's %v", fi.ModTime(), mtime)
	}
	if fi, _ := os.Lstat(filepath.Join(dst, "a", "b")); !fi.ModTime().Equal(mtime) || fi.Mode().Perm() != 0o700 {
		t.Errorf("a/b has %v %v: a directory's times are set after its children", fi.ModTime(), fi.Mode())
	}
	var at syscall.Stat_t
	must(t, syscall.Lstat(filepath.Join(dst, "a", "b", "data"), &at))
	if got := time.Unix(at.Atim.Unix()); !got.Equal(srcAtime) {
		t.Errorf("the access time %v, want %v", got, srcAtime)
	}
	if b, _ := os.ReadFile(filepath.Join(dst, "with space\nand newline")); string(b) != "odd name" {
		t.Errorf("the odd name's content %q", b)
	}
}

func TestOwnership(t *testing.T) {
	if os.Geteuid() != 0 {
		t.Skip("giving an entry another owner needs root (CHOWN); this test runs as uid", os.Geteuid())
	}
	src, _ := tree(t)
	must(t, os.Lchown(filepath.Join(src, "a", "b", "data"), 999, 998))
	must(t, os.Lchown(filepath.Join(src, "rel"), 997, 996))
	must(t, os.Lchown(filepath.Join(src, "a", "b"), 999, 999))
	must(t, os.Chmod(filepath.Join(src, "a", "b"), 0o700))
	must(t, os.Lchown(filepath.Join(src, "g"), 1001, 1002))
	must(t, syscall.Chmod(filepath.Join(src, "g"), 0o2775))
	dst := emptyTarget(t)
	r, err := Copy(src, dst, -1)
	must(t, err)
	if r.SourceDigest != r.CopyDigest {
		t.Fatalf("digests differ")
	}
	for name, want := range map[string][2]uint32{"a/b/data": {999, 998}, "rel": {997, 996}, "a/b": {999, 999}, "g": {1001, 1002}} {
		var s syscall.Stat_t
		must(t, syscall.Lstat(filepath.Join(dst, name), &s))
		if s.Uid != want[0] || s.Gid != want[1] {
			t.Errorf("%s is %d:%d, want %d:%d", name, s.Uid, s.Gid, want[0], want[1])
		}
	}
	if fi, _ := os.Lstat(filepath.Join(dst, "g")); fi.Mode()&os.ModeSetgid == 0 {
		t.Errorf("setgid lost after the owner changed")
	}
}

func TestDigestMoves(t *testing.T) {
	src, _ := tree(t)
	_, base, err := Digest(src)
	must(t, err)
	p := filepath.Join(src, "a-b", "x")
	for name, change := range map[string]func(){
		"content": func() { write(t, p, "DASH") },
		"mode":    func() { must(t, os.Chmod(p, 0o600)) },
		"mtime":   func() { tm := time.Unix(1, 1); must(t, os.Chtimes(p, tm, tm)) },
		"link": func() {
			must(t, os.Remove(filepath.Join(src, "rel")))
			must(t, os.Symlink("a", filepath.Join(src, "rel")))
		},
		"name": func() { must(t, os.Rename(filepath.Join(src, "empty"), filepath.Join(src, "empty2"))) },
	} {
		before := base
		change()
		_, d, err := Digest(src)
		must(t, err)
		if d == before {
			t.Errorf("a change of %s left the digest as it was", name)
		}
		base = d
	}
	// atime is not in it, and a socket is not.
	fi, err := os.Lstat(p)
	must(t, err)
	must(t, os.Chtimes(p, time.Unix(5, 0), fi.ModTime()))
	root, err := os.Lstat(src)
	must(t, err)
	l, err := net.Listen("unix", filepath.Join(src, "t.sock"))
	must(t, err)
	defer l.Close()
	must(t, os.Chtimes(src, root.ModTime(), root.ModTime())) // making the socket moved its directory's mtime
	if _, d, _ := Digest(src); d != base {
		t.Errorf("an access time or a socket moved the digest")
	}
}

func TestLineQuotesNames(t *testing.T) {
	e := entry{rel: "a b\nc", kind: kindSymlink, link: "x y", m: meta{mode: syscall.S_IFLNK | 0o777, mtime: 1_000000002}}
	if got, want := line(&e, nil), `"a b\nc" symlink 0777 0 0 1.000000002 "x y"`+"\n"; got != want {
		t.Errorf("line %q, want %q", got, want)
	}
	f := entry{rel: "h", kind: kindFile, same: "a b", m: meta{mode: syscall.S_IFREG | 0o4644}}
	if got, want := line(&f, nil), `"h" file 4644 0 0 0.000000000 link "a b"`+"\n"; got != want {
		t.Errorf("line %q, want %q", got, want)
	}
}

func TestOverBudgetWritesNothing(t *testing.T) {
	src, _ := tree(t)
	st, _ := Measure(src)
	dst := emptyTarget(t)
	r, err := Copy(src, dst, st.Bytes-1)
	if !errors.Is(err, ErrOverBudget) || r.Bytes != st.Bytes {
		t.Fatalf("err %v, bytes %d", err, r.Bytes)
	}
	if !strings.Contains(err.Error(), fmt.Sprint(st.Bytes)) {
		t.Errorf("the error does not name the bytes: %v", err)
	}
	if names, _ := os.ReadDir(dst); len(names) != 0 {
		t.Errorf("an over-budget copy wrote %d entries", len(names))
	}
	if _, err := Copy(src, dst, st.Bytes); err != nil {
		t.Errorf("a source of exactly the budget: %v", err)
	}
}

func TestCopyRefusesATarget(t *testing.T) {
	src, _ := tree(t)
	dst := emptyTarget(t)
	write(t, filepath.Join(dst, "already"), "x")
	if _, err := Copy(src, dst, -1); err == nil || !strings.Contains(err.Error(), "not empty") {
		t.Errorf("a target that is not empty: %v", err)
	}
	if _, err := Copy(src, filepath.Join(dst, "already"), -1); err == nil || !strings.Contains(err.Error(), "not a directory") {
		t.Errorf("a target that is a file: %v", err)
	}
	if _, err := Copy(src, filepath.Join(dst, "missing"), -1); !errors.Is(err, os.ErrNotExist) {
		t.Errorf("a missing target: %v", err)
	}
	if _, err := Copy(filepath.Join(dst, "already"), emptyTarget(t), -1); err == nil {
		t.Errorf("a source that is a file was copied")
	}
	if _, _, err := Digest(filepath.Join(dst, "missing")); err == nil {
		t.Errorf("a missing source was digested")
	}
	link := filepath.Join(t.TempDir(), "link")
	must(t, os.Symlink(src, link))
	if _, err := Measure(link); err == nil {
		t.Errorf("a root that is a link was followed")
	}
}

func TestRestoreReplaces(t *testing.T) {
	src, _ := tree(t)
	dst := emptyTarget(t)
	must(t, os.MkdirAll(filepath.Join(dst, "stale", "deep"), 0o755))
	write(t, filepath.Join(dst, "stale", "deep", "f"), "old")
	write(t, filepath.Join(dst, "a"), "a file where the source has a directory")
	outside := filepath.Join(t.TempDir(), "keep")
	write(t, outside, "kept")
	must(t, os.Symlink(filepath.Dir(outside), filepath.Join(dst, "to-outside")))

	r, err := Restore(src, dst)
	must(t, err)
	if r.SourceDigest != r.CopyDigest {
		t.Fatalf("digests differ")
	}
	if _, err := os.Lstat(filepath.Join(dst, "stale")); !errors.Is(err, os.ErrNotExist) {
		t.Errorf("the stale directory survived: %v", err)
	}
	if b, err := os.ReadFile(outside); err != nil || string(b) != "kept" {
		t.Errorf("emptying the target reached through a link: %q %v", b, err)
	}
	_, d, _ := Digest(src)
	if d != r.CopyDigest {
		t.Errorf("the restored target is not the source")
	}
	if _, err := Restore(src, filepath.Join(dst, "missing")); err == nil {
		t.Errorf("a missing target")
	}
	if _, err := Restore(src, filepath.Join(dst, "empty")); err == nil {
		t.Errorf("a target that is a file")
	}
	if _, err := Restore(filepath.Join(dst, "missing"), dst); err == nil {
		t.Errorf("a missing source")
	}
}

func TestNoSpace(t *testing.T) {
	src, _ := tree(t)
	dst := emptyTarget(t)
	defer func(c func(io.Writer, io.Reader) (int64, error)) { copyContent = c }(copyContent)
	copyContent = func(io.Writer, io.Reader) (int64, error) {
		return 0, &os.PathError{Op: "write", Path: "x", Err: syscall.ENOSPC}
	}
	_, err := Copy(src, dst, -1)
	if !errors.Is(err, ErrNoSpace) || !errors.Is(err, syscall.ENOSPC) {
		t.Fatalf("err %v", err)
	}
	if !strings.Contains(err.Error(), `"a-b/x"`) { // the first regular file in lexical order: "-" sorts before "/"
		t.Errorf("the error does not name the path: %v", err)
	}
	if err := written("p", os.ErrPermission); errors.Is(err, ErrNoSpace) {
		t.Errorf("a permission error became no space")
	}
}

func TestDevice(t *testing.T) {
	for _, c := range []struct {
		mode uint32
		kind string
	}{{syscall.S_IFCHR, "character device"}, {syscall.S_IFBLK, "block device"}, {0o170000, "file of type"}} {
		_, err := kindOf("dev/x", c.mode|0o600)
		var ue *UnsupportedError
		if !errors.As(err, &ue) || ue.Path != "dev/x" || !strings.Contains(ue.Error(), c.kind) {
			t.Errorf("mode %o: %v", c.mode, err)
		}
	}
	src, _ := tree(t)
	// makedev(1, 3), the null device.
	if err := syscall.Mknod(filepath.Join(src, "a", "null"), syscall.S_IFCHR|0o666, 1<<8|3); err != nil {
		t.Skipf("cannot make a device node here (needs MKNOD, uid %d): %v; kindOf is tested above", os.Geteuid(), err)
	}
	dst := emptyTarget(t)
	_, err := Copy(src, dst, -1)
	var ue *UnsupportedError
	if !errors.As(err, &ue) || ue.Path != "a/null" {
		t.Fatalf("err %v", err)
	}
	if names, _ := os.ReadDir(dst); len(names) != 0 {
		t.Errorf("a refused copy wrote %d entries", len(names))
	}
}
