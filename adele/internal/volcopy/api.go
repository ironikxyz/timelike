// Package volcopy is what the volume helper does with a named volume (feature 13, slice 2; 014 plan R24, R25): it
// measures a tree, digests it, copies it into an empty snapshot volume, and restores a snapshot into a volume it
// first empties. Adele never opens a volume's contents herself: she runs `adeled volume …` as a sandbox from her own
// image, the source read-only at /src and the target at /dst, as uid 0 with CHOWN, DAC_READ_SEARCH, DAC_OVERRIDE,
// FOWNER and FSETID only.
//
// Nothing here follows a symbolic link: entries are read with Lstat, a link is copied as its target string, and a
// regular file is opened with O_NOFOLLOW. A link pointing outside the tree is therefore copied as a link and never
// read through, and the copy only ever creates entries below the target it was given.
package volcopy

import (
	"errors"
	"fmt"
	"strconv"
)

// ErrOverBudget is a source whose bytes are past the copy's budget; nothing was written (the helper's exit 10).
var ErrOverBudget = errors.New("the source is past the byte budget")

// ErrNoSpace is a target that ran out of space during a copy (the helper's exit 11). It wraps the ENOSPC it came from.
var ErrNoSpace = errors.New("no space left in the target")

// UnsupportedError is an entry the helper will not copy: a character or block device, which needs MKNOD, a
// capability the helper does not get (the helper's exit 12). Path is the entry's slash-separated path in its tree.
type UnsupportedError struct {
	Path string
	Kind string // "character device" or "block device"
}

func (e *UnsupportedError) Error() string {
	return fmt.Sprintf("%s is a %s, which the helper will not copy (making one needs MKNOD)", strconv.Quote(e.Path), e.Kind)
}

// Stats counts a tree. Bytes is the sum of regular files' sizes, a hard-linked file counted once; Files is the
// entries other than the root that the digest has a line for (sockets are not among them); Sockets is the sockets
// found, which are never copied.
type Stats struct {
	Bytes   int64
	Files   int
	Sockets int
}

// Result is a copy or a restore: the source's stats, the source's digest (taken while copying, from the bytes
// copied), and the target's digest read back after the copy.
type Result struct {
	Stats
	SourceDigest string
	CopyDigest   string
}
