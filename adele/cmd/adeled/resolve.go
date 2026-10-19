package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strings"
	"time"

	"timelike/adele/internal/buildctx"
	"timelike/adele/internal/compose"
	"timelike/adele/internal/devcontainer"
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
//
// Slice 1 (014 research R12, R14-R16): with --devcontainer it first translates the project's devcontainer.json into
// compose files in its own /tmp and resolves those, so Adele checks the result exactly as a compose project's; and
// for every build it walks the context (links as links, never followed), digests it, scans the Dockerfile for its
// base images and what no grant allows, and reports each build's key.
func resolve(e env, args []string, stdout, stderr io.Writer) int {
	fs := flag.NewFlagSet("resolve", flag.ContinueOnError)
	fs.SetOutput(stderr)
	ws := fs.String("workspace", "", "the workspace")
	dir := fs.String("dir", "", "the project directory")
	project := fs.String("project", "", "the environment name")
	var files, profiles multi
	fs.Var(&files, "file", "a compose file, relative to --dir (repeatable)")
	fs.Var(&profiles, "profile", "a profile (repeatable)")
	dev := fs.Bool("devcontainer", false, "translate the project's devcontainer.json first")
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
	var dc *devcontainer.Result
	if *dev {
		var doc compose.Resolved
		dc, doc = translate(*dir, *ws, *project)
		if dc == nil {
			return printDoc(stdout, doc)
		}
		cargs = []string{"-p", *project, "--project-directory", dc.ProjectDir}
		for _, f := range dc.Files {
			cargs = append(cargs, "-f", f)
		}
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
		raw := out.Bytes()
		if dc != nil {
			if dc.Keep != nil {
				keep(model, dc.Keep)
				raw, _ = json.Marshal(model)
			}
			doc.Dev = devOf(dc)
			doc.Unset = append(doc.Unset, dc.Unset...)
		}
		doc.OK, doc.Model, doc.Real = true, raw, map[string]string{}
		for _, src := range compose.BindSources(model) {
			real, rerr := filepath.EvalSymlinks(src)
			if rerr != nil {
				real = ""
			}
			doc.Real[src] = real
		}
		doc.Builds, doc.Refusal, doc.Error = scanBuilds(model, *ws)
		if doc.Refusal != nil || doc.Error != "" {
			doc.OK = false
		}
	}
	return printDoc(stdout, doc)
}

func printDoc(stdout io.Writer, doc compose.Resolved) int {
	raw, _ := json.Marshal(doc)
	fmt.Fprintln(stdout, string(raw))
	return exitOK
}

// translate finds and translates the project's devcontainer.json (R12). A nil result means doc says why: a refusal
// for a missing or unparseable file or a setting no grant allows, or an error.
func translate(dir, ws, project string) (*devcontainer.Result, compose.Resolved) {
	var doc compose.Resolved
	path, ok := devcontainer.Find(dir)
	if !ok {
		doc.Refusal = &compose.Refusal{Kind: compose.KindSetting, Setting: "devcontainer.json", Value: "none in " + dir,
			Remedy: "add .devcontainer/devcontainer.json, or bring up a compose file with -f"}
		return nil, doc
	}
	tmp, err := os.MkdirTemp("", "tl-devcontainer-")
	if err != nil {
		doc.Error = "the resolution sandbox cannot make a scratch directory: " + err.Error()
		return nil, doc
	}
	res, err := devcontainer.Translate(path, dir, ws, project, tmp)
	var re *devcontainer.RefusalError
	var se *devcontainer.SyntaxError
	switch {
	case errors.As(err, &re):
		doc.Refusal = re.Refusal
	case errors.As(err, &se):
		doc.Refusal = &compose.Refusal{Kind: compose.KindSetting, Setting: "devcontainer.json",
			Value:  fmt.Sprintf("line %d: %s", se.Line, se.Msg),
			Remedy: "fix devcontainer.json at that line (JSONC: comments and trailing commas are fine)"}
	case err != nil:
		doc.Error = "cannot translate devcontainer.json: " + err.Error()
	default:
		return res, doc
	}
	return nil, doc
}

// keep drops every service not in names or their depends_on closure (a devcontainer's service and runServices).
func keep(model compose.Model, names []string) {
	services, _ := model["services"].(map[string]any)
	want := map[string]bool{}
	var add func(string)
	add = func(n string) {
		if want[n] {
			return
		}
		want[n] = true
		s, _ := services[n].(map[string]any)
		deps, _ := s["depends_on"].(map[string]any)
		for d := range deps {
			add(d)
		}
	}
	for _, n := range names {
		add(n)
	}
	for n := range services {
		if !want[n] {
			delete(services, n)
		}
	}
}

func devOf(r *devcontainer.Result) *compose.Dev {
	d := &compose.Dev{Primary: r.Primary, RemoteUser: r.RemoteUser, RemoteEnv: r.RemoteEnv,
		WorkspaceFolder: r.WorkspaceFolder, NotRun: r.NotRun, Lifecycle: []compose.Command{}}
	if d.RemoteEnv == nil {
		d.RemoteEnv = map[string]string{}
	}
	for _, c := range r.Lifecycle {
		d.Lifecycle = append(d.Lifecycle, compose.Command{Name: c.Name, Shell: c.Shell, Argv: c.Argv})
	}
	return d
}

// scanBuilds walks each build's context and scans its Dockerfile, in the sandbox (R14-R16). It returns the scans,
// or the first refusal, or an error the agent can act on (a context over its bound, a Dockerfile that cannot be read).
func scanBuilds(model compose.Model, ws string) ([]compose.BuildScan, *compose.Refusal, string) {
	var out []compose.BuildScan
	for _, b := range compose.Builds(model) {
		c, err := buildctx.Walk(b.Context, b.Dockerfile, ws, buildctx.DefaultLimits)
		var br *buildctx.Refusal
		if errors.As(err, &br) {
			return nil, &compose.Refusal{Kind: compose.KindSetting, Service: b.Service, Setting: br.Setting, Value: br.Value,
				Remedy: br.Remedy}, ""
		}
		if err != nil {
			return nil, nil, "the build of " + b.Service + " cannot be archived: " + err.Error()
		}
		data, err := os.ReadFile(c.Dockerfile)
		if err != nil {
			return nil, nil, "the build of " + b.Service + ": cannot read its Dockerfile: " + err.Error()
		}
		sc, err := buildctx.ScanDockerfile(data, b.Args, b.Target)
		if err != nil {
			return nil, nil, "the build of " + b.Service + ": its Dockerfile: " + err.Error()
		}
		if sc.Refusal != nil {
			return nil, &compose.Refusal{Kind: compose.KindSetting, Service: b.Service, Setting: sc.Refusal.Setting,
				Value: sc.Refusal.Value, Remedy: sc.Refusal.Remedy}, ""
		}
		bases := sc.Bases
		if bases == nil {
			bases = []string{}
		}
		out = append(out, compose.BuildScan{Service: b.Service, Context: c.Dir, Dockerfile: c.Dockerfile,
			DockerfileName: c.DockerfileName, Digest: c.Digest, Key: buildctx.Key(c.Digest, c.DockerfileName, b.Args, b.Target),
			Bases: bases, Args: b.Args, Target: b.Target})
	}
	sort.Slice(out, func(i, j int) bool { return out[i].Service < out[j].Service })
	return out, nil, ""
}

// contextArchive is the context sandbox's entrypoint, `adeled context` (R14): never run in Adele's own container. It
// writes the build context's archive to stdout and nothing else there, then one JSON line to stderr with its digest,
// so Adele can tell an archive that is not the one resolve keyed. Exit 2 for a refusal, 1 for anything else.
func contextArchive(args []string, stdout, stderr io.Writer) int {
	fs := flag.NewFlagSet("context", flag.ContinueOnError)
	fs.SetOutput(stderr)
	ws := fs.String("workspace", "", "the workspace")
	dir := fs.String("context", "", "the build context")
	df := fs.String("dockerfile", "", "the Dockerfile")
	if err := fs.Parse(args); err != nil {
		return exitUsage
	}
	if *ws == "" || *dir == "" || *df == "" {
		fmt.Fprintln(stderr, `{"error": "adeled context: --workspace, --context and --dockerfile are required"}`)
		return exitUsage
	}
	c, err := buildctx.Walk(*dir, *df, *ws, buildctx.DefaultLimits)
	if err != nil {
		raw, _ := json.Marshal(map[string]string{"error": err.Error()})
		fmt.Fprintln(stderr, string(raw))
		var br *buildctx.Refusal
		if errors.As(err, &br) {
			return exitUsage
		}
		return 1
	}
	if err := c.WriteTar(stdout); err != nil {
		raw, _ := json.Marshal(map[string]string{"error": "the archive was not finished: " + err.Error()})
		fmt.Fprintln(stderr, string(raw))
		return 1
	}
	raw, _ := json.Marshal(map[string]any{"digest": c.Digest, "entries": len(c.Entries)})
	fmt.Fprintln(stderr, string(raw))
	return exitOK
}

func lastLines(s string, n int) string {
	lines := strings.Split(strings.TrimSpace(s), "\n")
	if len(lines) > n {
		lines = lines[len(lines)-n:]
	}
	return strings.Join(lines, "\n")
}
