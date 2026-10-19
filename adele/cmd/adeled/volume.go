package main

import (
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"strings"

	"timelike/adele/internal/volcopy"
)

// The volume helper's own exits (014 plan R25), beside 0 done, 1 anything else and 2 usage.
const (
	exitOverBudget  = 10 // the source is past --max-bytes; nothing was written
	exitNoSpace     = 11 // the target ran out of space
	exitUnsupported = 12 // an entry the helper will not copy (a device)
)

// volCopy is the copy the helper runs. It is a seam for one test, which makes the target run out of space.
var volCopy = volcopy.Copy

// volumeAnswer is the helper's one JSON line. For a copy or a restore, Digest is the source's, taken during the copy,
// and CopyDigest the target's read back; measure has no digest.
type volumeAnswer struct {
	Digest     string `json:"digest,omitempty"`
	Bytes      int64  `json:"bytes"`
	Files      int    `json:"files"`
	Sockets    int    `json:"sockets"`
	CopyDigest string `json:"copy_digest,omitempty"`
}

// volume is the volume helper's entrypoint, `adeled volume measure|copy|digest|restore` (feature 13, slice 2; 014
// plan R24, R25): never run in Adele's own container. Adele runs it as a sandbox from her own image with the source
// read-only at /src and the target at /dst. It prints one JSON line on stdout (volumeAnswer) and exits 0; or exits
// 10, 11 or 12 (above) or 1 with one line on stderr naming the cause. Past --max-bytes the line is still printed,
// with what was measured, so Adele can say how much was needed.
func volume(args []string, stdout, stderr io.Writer) int {
	const use = "usage: adeled volume measure|digest --src DIR | copy --src DIR --dst DIR [--max-bytes N] | restore --src DIR --dst DIR"
	if len(args) == 0 {
		fmt.Fprintln(stderr, use)
		return exitUsage
	}
	op := args[0]
	fs := flag.NewFlagSet("volume "+op, flag.ContinueOnError)
	fs.SetOutput(stderr)
	src := fs.String("src", "", "the source tree")
	dst := fs.String("dst", "", "the target tree (copy, restore)")
	maxBytes := fs.Int64("max-bytes", -1, "copy only: refuse, writing nothing, a source of more bytes (-1: no limit)")
	if err := fs.Parse(args[1:]); err != nil {
		return exitUsage
	}
	needDst := op == "copy" || op == "restore"
	switch {
	case op != "measure" && op != "digest" && !needDst:
		fmt.Fprintf(stderr, "adeled volume: unknown operation %q\n%s\n", op, use)
		return exitUsage
	case *src == "" || needDst != (*dst != "") || fs.NArg() > 0 || (op != "copy" && *maxBytes != -1):
		fmt.Fprintln(stderr, use)
		return exitUsage
	}

	var a volumeAnswer
	var err error
	switch op {
	case "measure":
		var st volcopy.Stats
		st, err = volcopy.Measure(*src)
		a = volumeAnswer{Bytes: st.Bytes, Files: st.Files, Sockets: st.Sockets}
	case "digest":
		var st volcopy.Stats
		st, a.Digest, err = volcopy.Digest(*src)
		a.Bytes, a.Files, a.Sockets = st.Bytes, st.Files, st.Sockets
	default:
		var r volcopy.Result
		if op == "copy" {
			r, err = volCopy(*src, *dst, *maxBytes)
		} else {
			r, err = volcopy.Restore(*src, *dst)
		}
		a = volumeAnswer{Digest: r.SourceDigest, Bytes: r.Bytes, Files: r.Files, Sockets: r.Sockets,
			CopyDigest: r.CopyDigest}
	}
	code := exitOK
	var ue *volcopy.UnsupportedError
	switch {
	case err == nil:
	case errors.Is(err, volcopy.ErrOverBudget):
		code = exitOverBudget
	case errors.Is(err, volcopy.ErrNoSpace):
		code = exitNoSpace
	case errors.As(err, &ue):
		code = exitUnsupported
	default:
		code = exitFailure
	}
	if err != nil {
		// One line: a path in an error from the os package is not quoted and may hold a newline.
		fmt.Fprintln(stderr, "adeled volume "+op+": "+strings.ReplaceAll(err.Error(), "\n", `\n`))
	}
	if code == exitOK || code == exitOverBudget {
		raw, _ := json.Marshal(a)
		fmt.Fprintln(stdout, string(raw))
	}
	return code
}
