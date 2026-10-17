package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	"timelike/adele/internal/compose"
)

// ResolveTimeout bounds compose's own `config` inside the sandbox; the sandbox has a longer limit of its own.
const ResolveTimeout = 45 * time.Second

type multi []string

func (m *multi) String() string     { return strings.Join(*m, ",") }
func (m *multi) Set(v string) error { *m = append(*m, v); return nil }

// resolve is the sandbox's entrypoint (feature 13, slice 0; 014 research R2): never run in Adele's own container.
// The sandbox has the workspace read-only at its own path and nothing else: no network, no socket, no secret, an
// environment of HOME only. It runs compose's `config` on the project, resolves every bind source with
// EvalSymlinks (the same path the daemon will resolve on the host, because the workspace is mounted at the same
// path), and prints one JSON document (compose.Resolved). Exit 0 whenever that document is printed.
func resolve(e env, args []string, stdout, stderr io.Writer) int {
	fs := flag.NewFlagSet("resolve", flag.ContinueOnError)
	fs.SetOutput(stderr)
	ws := fs.String("workspace", "", "the workspace")
	dir := fs.String("dir", "", "the project directory")
	project := fs.String("project", "", "the environment name")
	var files, profiles multi
	fs.Var(&files, "file", "a compose file, relative to --dir (repeatable)")
	fs.Var(&profiles, "profile", "a profile (repeatable)")
	if err := fs.Parse(args); err != nil {
		return exitUsage
	}
	if *ws == "" || *dir == "" || !compose.ValidName(*project) || !compose.Within(*dir, *ws) {
		fmt.Fprintln(stderr, "adeled resolve: --workspace, --dir inside it and a valid --project are required")
		return exitUsage
	}
	bin := e.get("ADELE_COMPOSE_BIN")
	cargs := []string{"-p", *project, "--project-directory", *dir}
	for _, f := range files {
		cargs = append(cargs, "-f", filepath.Join(*dir, f))
	}
	for _, p := range profiles {
		cargs = append(cargs, "--profile", p)
	}
	cargs = append(cargs, "config", "--format", "json")
	ctx, cancel := context.WithTimeout(context.Background(), ResolveTimeout)
	defer cancel()
	cmd := exec.CommandContext(ctx, bin, cargs...)
	cmd.Dir = *dir
	cmd.Env = []string{"HOME=/tmp"}
	var out, errb bytes.Buffer
	cmd.Stdout, cmd.Stderr = &out, &errb
	err := cmd.Run()
	doc := compose.Resolved{Unset: compose.Unset(errb.String())}
	switch {
	case ctx.Err() != nil:
		doc.Error = fmt.Sprintf("compose config did not finish within %s in the resolution sandbox", ResolveTimeout)
	case err != nil:
		msg := strings.TrimSpace(errb.String())
		var ee *exec.ExitError
		if !errors.As(err, &ee) {
			msg = err.Error()
		}
		if r := compose.Outside(msg, *ws); r != nil {
			doc.Refusal = r
		} else {
			doc.Error = lastLines(msg, 8)
		}
	default:
		var model compose.Model
		if jerr := json.Unmarshal(out.Bytes(), &model); jerr != nil {
			doc.Error = "compose config printed something that is not a JSON model: " + jerr.Error()
			break
		}
		doc.OK, doc.Model, doc.Real = true, out.Bytes(), map[string]string{}
		for _, src := range compose.BindSources(model) {
			real, rerr := filepath.EvalSymlinks(src)
			if rerr != nil {
				real = ""
			}
			doc.Real[src] = real
		}
	}
	raw, _ := json.Marshal(doc)
	fmt.Fprintln(stdout, string(raw))
	return exitOK
}

func lastLines(s string, n int) string {
	lines := strings.Split(strings.TrimSpace(s), "\n")
	if len(lines) > n {
		lines = lines[len(lines)-n:]
	}
	return strings.Join(lines, "\n")
}
