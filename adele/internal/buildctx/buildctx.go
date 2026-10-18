// Package buildctx is what the context sandbox does with a service's `build:` (feature 13, slice 1; 014 research
// R14-R16): it resolves the context and the Dockerfile inside the workspace, walks the context as `docker build`
// would send it, digests it, writes it as a tar, and scans the Dockerfile for what it asks of the daemon.
//
// It runs in a network-less sandbox that sees the workspace read-only. Adele never runs it on the host and never
// parses the tar it writes: she copies the bytes into the daemon's build request (cross-stack P002). So nothing
// here may follow a link out of the context, and nothing here trusts a file to stay as it was read.
package buildctx

import (
	"archive/tar"
	"bytes"
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
)

// Limits bound one context archive. A zero field takes DefaultLimits' value.
type Limits struct {
	MaxBytes   int64 // the sum of regular files' sizes
	MaxEntries int   // archived paths, directories and links included
}

// DefaultLimits are the bounds of 014 research R14: 256 MiB of content and 100 000 entries.
var DefaultLimits = Limits{MaxBytes: 256 << 20, MaxEntries: 100000}

// Entry is one archived path.
type Entry struct {
	Rel  string      // slash-separated path inside the archive
	Abs  string      // its path on disk; for an injected Dockerfile, the Dockerfile's real path
	Mode fs.FileMode // type bits and permission bits as Lstat reports them
	Link string      // a symlink's target, as Readlink returns it (never followed)
	Size int64       // regular files only

	sum [sha256.Size]byte // a regular file's content, so WriteTar can tell it changed
}

// Context is a walked build context.
type Context struct {
	Dir            string  // the context directory (absolute, real path)
	Dockerfile     string  // the Dockerfile's real absolute path
	DockerfileName string  // its path inside the archive
	Entries        []Entry // in walk order
	Digest         string  // hex SHA-256 over each entry's path, type, mode, link and content; never times or owners
}

// Refusal is a path that may not be built. Setting names it ("build.context", "build.dockerfile"), Value is the
// path, and Remedy says how to change the request.
type Refusal struct {
	Setting string `json:"setting"`
	Value   string `json:"value"`
	Remedy  string `json:"remediation"`
}

func (r *Refusal) Error() string {
	return fmt.Sprintf("%s %q is refused: %s", r.Setting, r.Value, r.Remedy)
}

// TooBig is a context past one of its Limits. What is "bytes" or "entries".
type TooBig struct {
	What  string
	Limit int64
}

func (e *TooBig) Error() string {
	hint := "exclude what the image does not need with a .dockerignore at the context's root"
	if e.What == "entries" {
		return fmt.Sprintf("the build context has more than %d entries; %s", e.Limit, hint)
	}
	return fmt.Sprintf("the build context is over %s; %s", size(e.Limit), hint)
}

func size(n int64) string {
	if n >= 1<<20 && n%(1<<20) == 0 {
		return strconv.FormatInt(n>>20, 10) + " MiB"
	}
	return strconv.FormatInt(n, 10) + " bytes"
}

// within reports whether path is ws or lies under it, lexically.
func within(path, ws string) bool {
	return path == ws || strings.HasPrefix(path, ws+"/") || ws == "/"
}

// resolve gives the real path of p, refused when it does not exist or resolves outside the workspace.
func resolve(setting, p, ws string) (string, error) {
	if !filepath.IsAbs(p) {
		return "", &Refusal{Setting: setting, Value: p, Remedy: "give an absolute path (compose's config makes it one)"}
	}
	real, err := filepath.EvalSymlinks(p)
	if err != nil {
		return "", &Refusal{Setting: setting, Value: p,
			Remedy: "it does not exist in the workspace the sandbox sees; create it, or name a path inside the workspace"}
	}
	if !within(real, ws) {
		return "", &Refusal{Setting: setting, Value: p,
			Remedy: "it resolves outside the workspace, which is all the sandbox may read; move it inside the workspace"}
	}
	return real, nil
}

// Walk resolves dir and dockerfile, each inside workspace after filepath.EvalSymlinks, or a *Refusal. It applies
// the context root's .dockerignore, walks dir without following any link, and digests what it found. The
// Dockerfile and .dockerignore are always sent, as the CLI sends them; a Dockerfile outside dir is added at the
// archive's root as DockerfileName. Sockets, pipes, devices and irregular files are skipped. Past lim it returns
// a *TooBig.
func Walk(dir, dockerfile, workspace string, lim Limits) (*Context, error) {
	if lim.MaxBytes <= 0 {
		lim.MaxBytes = DefaultLimits.MaxBytes
	}
	if lim.MaxEntries <= 0 {
		lim.MaxEntries = DefaultLimits.MaxEntries
	}
	ws, err := filepath.EvalSymlinks(workspace)
	if err != nil {
		return nil, fmt.Errorf("the workspace %q: %w", workspace, err)
	}
	ws = filepath.Clean(ws)
	rdir, err := resolve("build.context", dir, ws)
	if err != nil {
		return nil, err
	}
	if fi, err := os.Stat(rdir); err != nil || !fi.IsDir() {
		return nil, &Refusal{Setting: "build.context", Value: dir, Remedy: "name a directory"}
	}
	rdf, err := resolve("build.dockerfile", dockerfile, ws)
	if err != nil {
		return nil, err
	}
	if fi, err := os.Stat(rdf); err != nil || !fi.Mode().IsRegular() {
		return nil, &Refusal{Setting: "build.dockerfile", Value: dockerfile, Remedy: "name a regular file"}
	}

	c := &Context{Dir: rdir, Dockerfile: rdf}
	dfRel := ""
	if within(rdf, rdir) && rdf != rdir {
		r, _ := filepath.Rel(rdir, rdf)
		dfRel = filepath.ToSlash(r)
		c.DockerfileName = dfRel
	} else {
		sum := sha256.Sum256([]byte(rdf))
		c.DockerfileName = ".timelike-dockerfile-" + hex.EncodeToString(sum[:])[:6]
	}

	var ig *Ignore
	if data, err := os.ReadFile(filepath.Join(rdir, ".dockerignore")); err == nil {
		if ig, err = ParseIgnore(data); err != nil {
			return nil, err
		}
	} else if !errors.Is(err, fs.ErrNotExist) {
		return nil, fmt.Errorf("reading .dockerignore: %w", err)
	}
	always := func(rel string) bool { return rel == dfRel || rel == ".dockerignore" }
	holdsAlways := func(rel string) bool { return dfRel != "" && strings.HasPrefix(dfRel, rel+"/") }

	var total int64
	add := func(e Entry) error {
		if len(c.Entries) >= lim.MaxEntries {
			return &TooBig{What: "entries", Limit: int64(lim.MaxEntries)}
		}
		if e.Mode.IsRegular() {
			total += e.Size
			if total > lim.MaxBytes {
				return &TooBig{What: "bytes", Limit: lim.MaxBytes}
			}
		}
		c.Entries = append(c.Entries, e)
		return nil
	}

	err = filepath.WalkDir(rdir, func(p string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if p == rdir {
			return nil
		}
		r, _ := filepath.Rel(rdir, p)
		rel := filepath.ToSlash(r)
		if ig.Excluded(rel) && !always(rel) {
			if d.IsDir() && !ig.mayReinclude(rel) && !holdsAlways(rel) {
				return filepath.SkipDir
			}
			return nil
		}
		fi, err := d.Info() // Lstat: WalkDir follows no link
		if err != nil {
			return err
		}
		e := Entry{Rel: rel, Abs: p, Mode: fi.Mode()}
		switch t := fi.Mode().Type(); {
		case t == fs.ModeDir:
		case t == fs.ModeSymlink:
			if e.Link, err = os.Readlink(p); err != nil {
				return err
			}
		case t == 0:
			e.Size = fi.Size()
		default:
			return nil // a socket, pipe, device or irregular file: nothing a build can use
		}
		return add(e)
	})
	if err != nil {
		return nil, err
	}
	if dfRel == "" {
		fi, err := os.Lstat(rdf)
		if err != nil {
			return nil, err
		}
		if err := add(Entry{Rel: c.DockerfileName, Abs: rdf, Mode: fi.Mode(), Size: fi.Size()}); err != nil {
			return nil, err
		}
	}

	h := sha256.New()
	for i := range c.Entries {
		e := &c.Entries[i]
		if e.Mode.IsRegular() {
			if e.sum, err = fileSum(e.Abs, e.Size); err != nil {
				return nil, err
			}
		}
		digestEntry(h, e)
	}
	c.Digest = hex.EncodeToString(h.Sum(nil))
	return c, nil
}

// fileSum hashes a regular file's content, which must be exactly the size the walk saw.
func fileSum(p string, want int64) (sum [sha256.Size]byte, err error) {
	f, err := os.Open(p)
	if err != nil {
		return sum, err
	}
	defer f.Close()
	h := sha256.New()
	n, err := io.Copy(h, f)
	if err != nil {
		return sum, err
	}
	if n != want {
		return sum, fmt.Errorf("%s changed while the context was read (%d bytes, then %d); build again", p, want, n)
	}
	copy(sum[:], h.Sum(nil))
	return sum, nil
}

// perm is the mode a header carries: permission bits, with setuid, setgid and sticky.
func perm(m fs.FileMode) int64 {
	v := int64(m.Perm())
	if m&fs.ModeSetuid != 0 {
		v |= 0o4000
	}
	if m&fs.ModeSetgid != 0 {
		v |= 0o2000
	}
	if m&fs.ModeSticky != 0 {
		v |= 0o1000
	}
	return v
}

func kind(m fs.FileMode) string {
	switch {
	case m.IsDir():
		return "d"
	case m&fs.ModeSymlink != 0:
		return "l"
	}
	return "f"
}

// digestEntry writes one entry, NUL-separated, so no two different entries hash the same fields.
func digestEntry(h hash.Hash, e *Entry) {
	fmt.Fprintf(h, "%s\x00%s\x00%o\x00%s\x00", e.Rel, kind(e.Mode), perm(e.Mode), e.Link)
	if e.Mode.IsRegular() {
		fmt.Fprintf(h, "%d\x00%x\x00", e.Size, e.sum)
	}
}

// WriteTar writes the archive: one header per entry in order, with uid and gid 0 and no owner names, as the CLI
// sends, and each file's mtime read now. It fails if a file changed type, link, size or content since Walk, so the
// digest never names a context other than the one sent.
func (c *Context) WriteTar(w io.Writer) error {
	tw := tar.NewWriter(w)
	for i := range c.Entries {
		e := &c.Entries[i]
		fi, err := os.Lstat(e.Abs)
		if err != nil {
			return err
		}
		if fi.Mode().Type() != e.Mode.Type() || perm(fi.Mode()) != perm(e.Mode) {
			return changed(e.Abs)
		}
		hdr := &tar.Header{Name: e.Rel, Mode: perm(e.Mode), ModTime: fi.ModTime().Truncate(1e9)}
		switch kind(e.Mode) {
		case "d":
			hdr.Typeflag, hdr.Name = tar.TypeDir, e.Rel+"/"
		case "l":
			link, err := os.Readlink(e.Abs)
			if err != nil {
				return err
			}
			if link != e.Link {
				return changed(e.Abs)
			}
			hdr.Typeflag, hdr.Linkname = tar.TypeSymlink, e.Link
		default:
			if fi.Size() != e.Size {
				return changed(e.Abs)
			}
			hdr.Typeflag, hdr.Size = tar.TypeReg, e.Size
		}
		if err := tw.WriteHeader(hdr); err != nil {
			return err
		}
		if hdr.Typeflag == tar.TypeReg {
			if err := copyFile(tw, e); err != nil {
				return err
			}
		}
	}
	return tw.Close()
}

func changed(p string) error {
	return fmt.Errorf("%s changed after the context was digested; build again", p)
}

// copyFile streams a file's content into the archive, checking it is the content Walk digested.
func copyFile(w io.Writer, e *Entry) error {
	f, err := os.Open(e.Abs)
	if err != nil {
		return err
	}
	defer f.Close()
	h := sha256.New()
	n, err := io.Copy(io.MultiWriter(w, h), io.LimitReader(f, e.Size))
	if err != nil {
		return err
	}
	var extra [1]byte
	if m, _ := f.Read(extra[:]); n != e.Size || m != 0 || !bytes.Equal(h.Sum(nil), e.sum[:]) {
		return changed(e.Abs)
	}
	return nil
}

// Key is the build's key (014 research R16): SHA-256 over the context digest, the Dockerfile's path in the
// archive, the args sorted by name and the target. An unchanged project has an unchanged key, so nothing builds.
func Key(digest, dockerfileName string, args map[string]string, target string) string {
	h := sha256.New()
	fmt.Fprintf(h, "%s\x00%s\x00", digest, dockerfileName)
	names := make([]string, 0, len(args))
	for k := range args {
		names = append(names, k)
	}
	sort.Strings(names)
	for _, k := range names {
		fmt.Fprintf(h, "%s=%s\x00", k, args[k])
	}
	fmt.Fprintf(h, "\x00%s", target)
	return hex.EncodeToString(h.Sum(nil))
}

// Tag is the image's tag: "<env>-<service>:<key[:12]>", lowercased, with any character of env-service outside
// [a-z0-9._-] replaced by '-', since a repository name takes no other.
func Tag(env, service, key string) string {
	var b strings.Builder
	for _, r := range strings.ToLower(env + "-" + service) {
		if r >= 'a' && r <= 'z' || r >= '0' && r <= '9' || r == '.' || r == '_' || r == '-' {
			b.WriteRune(r)
		} else {
			b.WriteByte('-')
		}
	}
	k := strings.ToLower(key)
	if len(k) > 12 {
		k = k[:12]
	}
	return b.String() + ":" + k
}
