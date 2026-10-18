package buildctx

import (
	"bufio"
	"bytes"
	"fmt"
	"path"
	"path/filepath"
	"strings"
)

// Ignore is a parsed .dockerignore, read with the Docker CLI's semantics (moby/patternmatcher), so a context the
// agent trimmed for `docker build` is trimmed the same way here (014 research R14):
//   - one pattern per line; '#' starts a comment line; blank lines are skipped;
//   - each pattern is cleaned with filepath.Clean, and a leading '/' (or './') is dropped;
//   - a '!' prefix is an exception, which re-includes what an earlier pattern excluded;
//   - '*', '?' and character classes match within one path segment, as filepath.Match does;
//   - '**' matches any number of segments, zero included;
//   - the last matching pattern wins, and a pattern that matches a directory matches everything under it.
type Ignore struct {
	patterns []pattern
	except   bool // some pattern is an exception
}

type pattern struct {
	text      string
	segs      []string
	exception bool
}

// ParseIgnore parses the text of a .dockerignore. A pattern filepath.Match cannot read is an error, as it is to
// the CLI, rather than a pattern that silently matches nothing.
func ParseIgnore(data []byte) (*Ignore, error) {
	ig := &Ignore{}
	sc := bufio.NewScanner(bytes.NewReader(data))
	sc.Buffer(make([]byte, 64<<10), 1<<20)
	for n := 1; sc.Scan(); n++ {
		line := sc.Text()
		if n == 1 {
			line = strings.TrimPrefix(line, "\ufeff") // a byte-order mark, as the CLI strips it
		}
		if strings.HasPrefix(line, "#") {
			continue
		}
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		exc := false
		if line[0] == '!' {
			exc = true
			line = strings.TrimSpace(line[1:])
			if line == "" {
				return nil, fmt.Errorf(".dockerignore line %d: an exception ('!') names no pattern", n)
			}
		}
		p := filepath.ToSlash(filepath.Clean(line))
		p = strings.TrimPrefix(p, "/")
		if p == "" {
			p = "."
		}
		segs := strings.Split(p, "/")
		for _, s := range segs {
			if s == "**" {
				continue
			}
			if _, err := path.Match(s, "x"); err != nil {
				return nil, fmt.Errorf(".dockerignore line %d: pattern %q: %v", n, line, err)
			}
		}
		ig.patterns = append(ig.patterns, pattern{text: p, segs: segs, exception: exc})
		if exc {
			ig.except = true
		}
	}
	if err := sc.Err(); err != nil {
		return nil, fmt.Errorf(".dockerignore: %w", err)
	}
	return ig, nil
}

// Excluded reports whether rel (slash-separated, relative to the context root, no leading "./") is excluded: the
// last pattern that matches rel or one of its parent directories decides.
func (ig *Ignore) Excluded(rel string) bool {
	if ig == nil || len(ig.patterns) == 0 {
		return false
	}
	segs := strings.Split(strings.TrimPrefix(path.Clean(rel), "./"), "/")
	excluded := false
	for _, p := range ig.patterns {
		if p.exception && !excluded {
			continue // nothing to re-include
		}
		if matchesOrParent(p.segs, segs) {
			excluded = !p.exception
		}
	}
	return excluded
}

// mayReinclude reports whether an exception could re-include something under the directory rel, which is what
// decides whether the walk may skip an excluded directory whole. It errs towards walking.
func (ig *Ignore) mayReinclude(rel string) bool {
	if ig == nil || !ig.except {
		return false
	}
	segs := strings.Split(rel, "/")
	for _, p := range ig.patterns {
		if p.exception && prefixMayMatch(p.segs, segs) {
			return true
		}
	}
	return false
}

// matchesOrParent reports whether the pattern matches the path or any of its parent directories.
func matchesOrParent(pat, segs []string) bool {
	for i := len(segs); i >= 1; i-- {
		if matchSegs(pat, segs[:i]) {
			return true
		}
	}
	return false
}

// matchSegs matches whole paths segment by segment; "**" absorbs any number of segments.
func matchSegs(pat, segs []string) bool {
	if len(pat) == 0 {
		return len(segs) == 0
	}
	if pat[0] == "**" {
		for i := 0; i <= len(segs); i++ {
			if matchSegs(pat[1:], segs[i:]) {
				return true
			}
		}
		return false
	}
	if len(segs) == 0 {
		return false
	}
	ok, _ := path.Match(pat[0], segs[0])
	return ok && matchSegs(pat[1:], segs[1:])
}

// prefixMayMatch reports whether some path under segs (or segs itself) could match pat.
func prefixMayMatch(pat, segs []string) bool {
	if len(segs) == 0 {
		return true
	}
	if len(pat) == 0 {
		return false
	}
	if pat[0] == "**" {
		return true
	}
	ok, _ := path.Match(pat[0], segs[0])
	return ok && prefixMayMatch(pat[1:], segs[1:])
}
