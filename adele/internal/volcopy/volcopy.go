//go:build linux

package volcopy

import (
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"hash"
	"io"
	"io/fs"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"syscall"
)

// kinds of entry, as the digest names them.
const (
	kindDir     = "dir"
	kindFile    = "file"
	kindSymlink = "symlink"
	kindFIFO    = "fifo"
	kindSocket  = "socket"
)

// meta is the part of an Lstat the digest and the copy use. Times are nanoseconds since the epoch.
type meta struct {
	mode     uint32 // the full st_mode: type and permission bits, setuid, setgid and sticky included
	uid, gid uint32
	atime    int64
	mtime    int64
	size     int64
	dev, ino uint64
	nlink    uint64
}

// entry is one path in a walked tree.
type entry struct {
	rel  string // slash-separated, "." for the root
	abs  string
	kind string
	m    meta
	link string // a symlink's target, as Readlink returns it
	same string // a hard link: the rel of the earlier regular file it shares an inode with
}

// kindOf names an entry's type from its st_mode, or refuses a device.
func kindOf(rel string, mode uint32) (string, error) {
	switch mode & syscall.S_IFMT {
	case syscall.S_IFDIR:
		return kindDir, nil
	case syscall.S_IFREG:
		return kindFile, nil
	case syscall.S_IFLNK:
		return kindSymlink, nil
	case syscall.S_IFIFO:
		return kindFIFO, nil
	case syscall.S_IFSOCK:
		return kindSocket, nil
	case syscall.S_IFCHR:
		return "", &UnsupportedError{Path: rel, Kind: "character device"}
	case syscall.S_IFBLK:
		return "", &UnsupportedError{Path: rel, Kind: "block device"}
	}
	return "", &UnsupportedError{Path: rel, Kind: fmt.Sprintf("file of type %#o", mode&syscall.S_IFMT)}
}

// walk lists root's tree in lexical path order, root first, without following a link and without reading a file's
// contents. Sockets are counted and left out. Each later name of a regular file's inode is marked as a hard link to
// the first, in the same order, so the copy creates the first before linking to it. A parent's path is a prefix of
// its children's, so it always sorts before them: walking the list forwards creates parents first, and backwards
// sets each directory's times after its children.
func walk(root string) ([]entry, Stats, error) {
	var st Stats
	fi, err := os.Lstat(root)
	if err != nil {
		return nil, st, err
	}
	if !fi.IsDir() {
		return nil, st, fmt.Errorf("%s is not a directory", strconv.Quote(root))
	}
	var out []entry
	err = filepath.WalkDir(root, func(p string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		r, _ := filepath.Rel(root, p)
		rel := filepath.ToSlash(r)
		info, err := d.Info() // Lstat: WalkDir follows no link
		if err != nil {
			return err
		}
		m, err := metaOf(info)
		if err != nil {
			return err
		}
		kind, err := kindOf(rel, m.mode)
		if err != nil {
			return err
		}
		if kind == kindSocket {
			st.Sockets++
			return nil
		}
		e := entry{rel: rel, abs: p, kind: kind, m: m}
		if kind == kindSymlink {
			if e.link, err = os.Readlink(p); err != nil {
				return err
			}
		}
		out = append(out, e)
		return nil
	})
	if err != nil {
		return nil, st, err
	}
	// WalkDir sorts each directory's names, which is not the order of whole paths ("a/x" after "a-b"): sort the paths,
	// keeping the root first ("." sorts after a name that starts with a space or a dash).
	rest := out[1:]
	sort.Slice(rest, func(i, j int) bool { return rest[i].rel < rest[j].rel })
	type inode struct{ dev, ino uint64 }
	first := map[inode]string{}
	for i := range out {
		e := &out[i]
		if e.rel != "." {
			st.Files++
		}
		if e.kind != kindFile {
			continue
		}
		if e.m.nlink > 1 {
			k := inode{e.m.dev, e.m.ino}
			if f, ok := first[k]; ok {
				e.same = f
				continue
			}
			first[k] = e.rel
		}
		st.Bytes += e.m.size
	}
	return out, st, nil
}

// line is an entry's digest line, newline-terminated: `path type mode uid gid mtime_sec.mtime_nsec`, then for a
// regular file `size sha256`, for a symlink its target, for a hard link `link <path>`. Paths and link targets are
// written with strconv.Quote, so a name holding a space, a newline or a byte that is not UTF-8 has exactly one
// encoding and cannot be mistaken for a field boundary or another line. The mode is the permission bits with
// setuid, setgid and sticky, in octal; the access time is not in it.
func line(e *entry, sum []byte) string {
	var b strings.Builder
	fmt.Fprintf(&b, "%s %s %04o %d %d %d.%09d", strconv.Quote(e.rel), e.kind, e.m.mode&0o7777, e.m.uid, e.m.gid,
		e.m.mtime/1e9, e.m.mtime%1e9)
	switch {
	case e.same != "":
		b.WriteString(" link " + strconv.Quote(e.same))
	case e.kind == kindFile:
		fmt.Fprintf(&b, " %d %s", e.m.size, hex.EncodeToString(sum))
	case e.kind == kindSymlink:
		b.WriteString(" " + strconv.Quote(e.link))
	}
	b.WriteByte('\n')
	return b.String()
}

func sumOf(h hash.Hash) string { return "sha256:" + hex.EncodeToString(h.Sum(nil)) }

// Measure counts root's tree without reading any file's contents. A device in it is an *UnsupportedError.
func Measure(root string) (Stats, error) {
	_, st, err := walk(root)
	return st, err
}

// Digest is root's digest (014 data-model § Slice 2, "The digest"): `sha256:` and the hex SHA-256 over one line per
// entry, root first, in lexical path order. Each regular file's contents are read once.
func Digest(root string) (Stats, string, error) {
	es, st, err := walk(root)
	if err != nil {
		return st, "", err
	}
	h := sha256.New()
	for i := range es {
		e := &es[i]
		var sum []byte
		if e.kind == kindFile && e.same == "" {
			if sum, err = hashFile(e.abs); err != nil {
				return st, "", err
			}
		}
		io.WriteString(h, line(e, sum))
	}
	return st, sumOf(h), nil
}

func hashFile(p string) ([]byte, error) {
	f, err := openRead(p)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	h := sha256.New()
	if _, err := io.Copy(h, f); err != nil {
		return nil, err
	}
	return h.Sum(nil), nil
}

// Copy copies src's tree into dst, which must be an existing empty directory: the snapshot. It measures src first,
// and with maxBytes >= 0 a source past it is ErrOverBudget with nothing written; a device is an *UnsupportedError,
// also with nothing written. Each entry keeps its owner, group, mode bits and access and modification times, and
// dst's root takes src root's. The source digest is taken from the bytes as they are copied; the copy digest is dst
// read back. Out of space is ErrNoSpace, naming the path.
func Copy(src, dst string, maxBytes int64) (Result, error) {
	es, st, err := walk(src)
	if err != nil {
		return Result{Stats: st}, err
	}
	if maxBytes >= 0 && st.Bytes > maxBytes {
		return Result{Stats: st}, fmt.Errorf("%w: %d bytes in the source, %d allowed", ErrOverBudget, st.Bytes, maxBytes)
	}
	if err := emptyDir(dst); err != nil {
		return Result{Stats: st}, err
	}
	return copyTree(es, st, dst)
}

// Restore empties dst (everything inside it, never dst itself) and copies src's tree into it as Copy does, with no
// budget. src is walked before anything is removed, so a device in it removes nothing.
func Restore(src, dst string) (Result, error) {
	es, st, err := walk(src)
	if err != nil {
		return Result{Stats: st}, err
	}
	fi, err := os.Lstat(dst)
	if err != nil {
		return Result{Stats: st}, err
	}
	if !fi.IsDir() {
		return Result{Stats: st}, fmt.Errorf("the target %s is not a directory", strconv.Quote(dst))
	}
	names, err := os.ReadDir(dst)
	if err != nil {
		return Result{Stats: st}, err
	}
	for _, n := range names {
		// RemoveAll removes a link, never what it points to.
		if err := os.RemoveAll(filepath.Join(dst, n.Name())); err != nil {
			return Result{Stats: st}, fmt.Errorf("emptying the target: %w", err)
		}
	}
	return copyTree(es, st, dst)
}

func emptyDir(dst string) error {
	fi, err := os.Lstat(dst)
	if err != nil {
		return err
	}
	if !fi.IsDir() {
		return fmt.Errorf("the target %s is not a directory", strconv.Quote(dst))
	}
	names, err := os.ReadDir(dst)
	if err != nil {
		return err
	}
	if len(names) > 0 {
		return fmt.Errorf("the target %s is not empty", strconv.Quote(dst))
	}
	return nil
}

// copyContent streams one regular file's bytes. It is a seam, and the only one: a test replaces it to make the
// target run out of space, which a temporary directory cannot be made to do.
var copyContent = io.Copy

// written names a failed write; out of space becomes ErrNoSpace, still wrapping the ENOSPC.
func written(rel string, err error) error {
	if errors.Is(err, syscall.ENOSPC) {
		return fmt.Errorf("%w: writing %s: %w", ErrNoSpace, strconv.Quote(rel), err)
	}
	return fmt.Errorf("writing %s: %w", strconv.Quote(rel), err)
}

// copyTree creates es below dst in order, then sets each directory's owner, mode and times backwards (children
// first), so creating an entry neither moves a directory's mtime nor meets a directory it may not yet write into.
func copyTree(es []entry, st Stats, dst string) (Result, error) {
	res := Result{Stats: st}
	h := sha256.New()
	target := func(rel string) string { return filepath.Join(dst, filepath.FromSlash(rel)) }
	for i := range es {
		e := &es[i]
		to := target(e.rel)
		var sum []byte
		var err error
		switch {
		case e.rel == ".":
			// dst itself: its attributes are set with the other directories', below.
		case e.same != "":
			err = os.Link(target(e.same), to)
		case e.kind == kindDir:
			err = os.Mkdir(to, 0o700)
		case e.kind == kindFile:
			sum, err = copyFile(e.abs, to)
		case e.kind == kindSymlink:
			err = os.Symlink(e.link, to)
		case e.kind == kindFIFO:
			err = syscall.Mkfifo(to, 0o600)
		}
		if err == nil && e.kind != kindDir && e.same == "" {
			err = setMeta(to, e)
		}
		if err != nil {
			return res, written(e.rel, err)
		}
		io.WriteString(h, line(e, sum))
	}
	for i := len(es) - 1; i >= 0; i-- {
		if e := &es[i]; e.kind == kindDir {
			if err := setMeta(target(e.rel), e); err != nil {
				return res, written(e.rel, err)
			}
		}
	}
	res.SourceDigest = sumOf(h)
	_, d, err := Digest(dst)
	if err != nil {
		return res, fmt.Errorf("reading the copy back: %w", err)
	}
	res.CopyDigest = d
	// Listing a directory to read it back may move its access time (which the digest does not hold); give it back.
	for i := len(es) - 1; i >= 0; i-- {
		if e := &es[i]; e.kind == kindDir {
			if err := lutimes(target(e.rel), e.m.atime, e.m.mtime); err != nil {
				return res, written(e.rel, err)
			}
		}
	}
	return res, nil
}

// openRead opens a regular file for reading, never through a link, and without moving its access time (O_NOATIME,
// which the helper may use on any file because it has FOWNER), so reading the copy back leaves the times the copy
// gave it. Without FOWNER, on a file it does not own, O_NOATIME is EPERM, and the file is opened without it.
func openRead(p string) (*os.File, error) {
	f, err := os.OpenFile(p, os.O_RDONLY|syscall.O_NOFOLLOW|syscall.O_NOATIME, 0)
	if errors.Is(err, syscall.EPERM) {
		f, err = os.OpenFile(p, os.O_RDONLY|syscall.O_NOFOLLOW, 0)
	}
	return f, err
}

// copyFile copies one regular file's bytes, hashing them as they are read, into a file it creates (never one that
// exists, never through a link).
func copyFile(from, to string) ([]byte, error) {
	in, err := openRead(from)
	if err != nil {
		return nil, err
	}
	defer in.Close()
	out, err := os.OpenFile(to, os.O_WRONLY|os.O_CREATE|os.O_EXCL|syscall.O_NOFOLLOW, 0o600)
	if err != nil {
		return nil, err
	}
	h := sha256.New()
	if _, err := copyContent(out, io.TeeReader(in, h)); err != nil {
		out.Close()
		return nil, err
	}
	if err := out.Close(); err != nil {
		return nil, err
	}
	return h.Sum(nil), nil
}

// setMeta gives p e's owner and group, then its mode (after the owner: changing the owner clears setuid and setgid),
// then its access and modification times. A symlink gets its owner and times, not a mode: Linux has none for one, and
// chmod would follow it.
func setMeta(p string, e *entry) error {
	if err := os.Lchown(p, int(e.m.uid), int(e.m.gid)); err != nil {
		return err
	}
	if e.kind != kindSymlink {
		if err := syscall.Chmod(p, e.m.mode&0o7777); err != nil {
			return &os.PathError{Op: "chmod", Path: p, Err: err}
		}
	}
	return lutimes(p, e.m.atime, e.m.mtime)
}
