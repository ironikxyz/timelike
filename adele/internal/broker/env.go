package broker

// The docker.compose capability (feature 13, slice 0; .specswarm/features/014-nested-dev-env/, research R2-R7,
// contracts/adele-env.md). Adele resolves the agent's project in a sandbox, checks the resolved model, brings it up
// from the checked bytes on the host's daemon, labelled as timelike's, and records it in the ledger. `down`
// removes everything carrying the environment's label and records the ending only when the daemon, read back,
// has none of it (cross-stack P004).
//
// Locking (Cycle 2, lane 13s0a item A): the sandbox and the setting check take no lock, so requests resolve side by
// side and a refusal never waits behind another environment's bring-up. Envs' own lock is held from the live
// check to the ledger write, so two ups never race on one name or one instance count, and a down of a name waits
// for an up of it in progress. The broker's lock is taken only around the grant and ledger calls, never across
// the sandbox, compose or the daemon, so a stand-in request never waits out a bring-up.
//
// A request given up by its client (the agent's --wait passed) stops while nothing is created: during the
// sandbox, or while waiting for the lock. Once Adele starts creating, she finishes and records it, so an
// environment is either absent or recorded live, never half-made and unrecorded.

import (
	"bytes"
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"

	"timelike/adele/internal/compose"
	"timelike/adele/internal/engine"
	"timelike/adele/internal/grants"
	"timelike/adele/internal/ledger"
)

// EnvHost is what an environment's refusal records as where it would have reached (004 FR-35).
const EnvHost = "docker:local"

// Bounds on one bring-up's own calls. The agent's client bounds the whole of it.
const (
	SandboxTimeout = 90 * time.Second
	// SandboxSweep is how often serve removes sandboxes older than SandboxLeftover (lane 13s0b, item A).
	SandboxSweep   = 5 * time.Minute
	ComposeTimeout = 5 * time.Minute
	MaxListed      = 8 // files or profiles in one request
)

// SandboxLeftover is the age past which a sandbox is left behind: its bound, then engine.Run's own late removal.
var SandboxLeftover = SandboxTimeout + engine.LateRemoval + time.Minute

// Envs is what the docker.compose capability needs: the daemon, the workspace, the sandbox image and compose.
type Envs struct {
	Engine       *engine.Client
	Workspace    string // TIMELIKE_WORKSPACE: "" when the launch mounted none
	HostGit      string // TIMELIKE_HOST_GIT, shown in up's answer
	SandboxImage string
	ComposeBin   string
	ScratchDir   string // where a bring-up's empty project directory is made: Adele's own state directory
	// RunCompose runs compose with stdin; nil is the real one (tests replace it).
	RunCompose func(ctx context.Context, args []string, stdin []byte) (stdout, stderr []byte, err error)
	mu         sync.Mutex
	// holder is what holds mu ("up NAME" or "down NAME"), for a waiter's timings (lane 13s0b, item A: a 20.6 s
	// lock wait with nothing to say what held it). Guarded by hmu, never by mu.
	hmu    sync.Mutex
	holder string
}

// lock takes mu for what ("up NAME" or "down NAME") and returns what held it when the wait began ("" for no one).
func (e *Envs) lock(what string) (heldBy string) {
	e.hmu.Lock()
	heldBy = e.holder
	e.hmu.Unlock()
	e.mu.Lock()
	e.hmu.Lock()
	e.holder = what
	e.hmu.Unlock()
	return heldBy
}

func (e *Envs) unlock() {
	e.hmu.Lock()
	e.holder = ""
	e.hmu.Unlock()
	e.mu.Unlock()
}

// Service is one service of an environment as the daemon reports it, read back.
type Service struct {
	Service  string `json:"service"`
	State    string `json:"state"`
	Health   string `json:"health"`
	ExitCode int    `json:"exit_code"`
	Alias    string `json:"alias"`
	Ports    []int  `json:"ports"`
}

func (e *Envs) runCompose(ctx context.Context, home string, args []string, stdin []byte) ([]byte, []byte, error) {
	if e.RunCompose != nil {
		return e.RunCompose(ctx, args, stdin)
	}
	ctx, cancel := context.WithTimeout(ctx, ComposeTimeout)
	defer cancel()
	cmd := exec.CommandContext(ctx, e.ComposeBin, args...)
	// Nothing of Adele's own environment: a second interpolation of the checked bytes reads nothing (R5).
	// HOME is the bring-up's own directory, under Adele's state: /tmp is not hers to rely on (lane 13s0a, item B).
	cmd.Env = []string{"HOME=" + home, "PATH=", "DOCKER_HOST=unix://" + e.Engine.Socket}
	cmd.Stdin = bytes.NewReader(stdin)
	var out, errb bytes.Buffer
	cmd.Stdout, cmd.Stderr = &out, &errb
	err := cmd.Run()
	if ctx.Err() != nil {
		err = fmt.Errorf("compose did not finish within %s", ComposeTimeout)
	}
	return out.Bytes(), errb.Bytes(), err
}

// Services reads an environment's services back from the daemon, by its label only.
func (e *Envs) Services(ctx context.Context, name string) ([]Service, error) {
	cs, err := e.Engine.Containers(ctx, engine.LabelEnv+"="+name)
	if err != nil {
		return nil, err
	}
	out := make([]Service, 0, len(cs))
	for _, c := range cs {
		svc := c.Labels[engine.ComposeService]
		var ports []int
		for _, p := range strings.Split(c.Labels[engine.LabelPorts], ",") {
			if n, err := strconv.Atoi(p); err == nil {
				ports = append(ports, n)
			}
		}
		if ports == nil {
			ports = []int{}
		}
		out = append(out, Service{Service: svc, State: c.State, Health: c.Health, ExitCode: c.ExitCode,
			Alias: compose.Alias(svc, name), Ports: ports})
	}
	sort.Slice(out, func(i, j int) bool { return out[i].Service < out[j].Service })
	return out, nil
}

func envFail(status int, what, remedy string) Outcome { return fail(status, what, remedy, nil) }

func (b *Broker) handleEnv(ctx context.Context, req Request) Outcome {
	e := b.Envs
	if e == nil {
		return envFail(http.StatusServiceUnavailable, "this Adele has no Docker daemon to bring environments up on",
			"the operator starts her with the socket: make up")
	}
	if e.Workspace == "" {
		return envFail(http.StatusBadRequest, "no workspace was mounted at launch, so there is no project Adele can resolve",
			"the operator launches with a workspace: make up (TIMELIKE_WORKSPACES set)")
	}
	if !compose.ValidName(req.Params.Name) {
		return envFail(http.StatusBadRequest, fmt.Sprintf("bad environment name %q", req.Params.Name),
			"a name is tl-, then a lowercase letter or digit, then up to 59 of a-z, 0-9 and -")
	}
	if req.Action == "down" {
		return b.envDown(ctx, req)
	}
	return b.envUp(ctx, req)
}

func (b *Broker) envUp(ctx context.Context, req Request) Outcome {
	e, p := b.Envs, req.Params
	if !filepath.IsAbs(p.Dir) || filepath.Clean(p.Dir) != p.Dir || !compose.Within(p.Dir, e.Workspace) {
		return envFail(http.StatusBadRequest, fmt.Sprintf("the project directory %q is not inside the workspace %s", p.Dir, e.Workspace),
			"bring up a project inside the workspace: cd into it, or name it with an absolute path")
	}
	if len(p.Files) > MaxListed || len(p.Profiles) > MaxListed {
		return envFail(http.StatusBadRequest, "too many files or profiles", fmt.Sprintf("at most %d of each", MaxListed))
	}
	for _, f := range p.Files {
		if f == "" || filepath.IsAbs(f) || strings.HasPrefix(filepath.Clean(f), "..") {
			return envFail(http.StatusBadRequest, fmt.Sprintf("compose file %q is not a path inside the project", f),
				"name it relative to the project directory")
		}
	}
	for _, pr := range p.Profiles {
		if !nameRe.MatchString(pr) {
			return envFail(http.StatusBadRequest, fmt.Sprintf("bad profile %q", pr), "a profile is lowercase letters, digits and -")
		}
	}

	b.mu.Lock()
	g, out, ok := b.choose(req)
	if ok {
		var err error
		if g, err = b.effective(g); err != nil {
			out, ok = fail(http.StatusInternalServerError, "the grant's extensions do not apply: "+err.Error(), "", nil), false
		}
	}
	b.mu.Unlock()
	if !ok {
		return out
	}
	ttl := g.TTL
	if p.TTL != "" {
		ttl, _ = grants.ParseTTL(p.TTL)
	}

	began := time.Now()
	var phases engine.Phases
	doc, out, ok := e.resolve(ctx, p.Dir, p.Name, p.Files, p.Profiles, &phases)
	if !ok {
		return out
	}
	timings := map[string]any{"resolve_ms": time.Since(began).Milliseconds(), "sandbox_ms": phases.Millis()}
	if doc.Refusal != nil {
		return b.refuseEnv(req, g.Name, doc.Refusal)
	}
	var model compose.Model
	if err := json.Unmarshal(doc.Model, &model); err != nil {
		return envFail(http.StatusBadGateway, "the sandbox's model is not readable JSON: "+err.Error(), "")
	}
	hash := compose.Hash(model)
	if r := compose.Check(model, e.Workspace, doc.Real); r != nil {
		return b.refuseEnv(req, g.Name, r)
	}

	queued := time.Now()
	heldBy := e.lock("up " + p.Name)
	defer e.unlock()
	timings["lock_wait_ms"] = time.Since(queued).Milliseconds()
	if heldBy != "" {
		timings["lock_held_by"] = heldBy
	}
	if ctx.Err() != nil {
		return envFail(http.StatusServiceUnavailable, "the request was given up before Adele started creating "+p.Name,
			"nothing was created; bring it up again")
	}
	ctx = context.WithoutCancel(ctx)

	// A live environment of this name: unchanged is a no-op, read back; changed is refused (FR-5).
	b.mu.Lock()
	row, live, err := b.Ledger.LiveResource(grants.CapDockerCompose, p.Name)
	b.mu.Unlock()
	if err != nil {
		return ledgerFailed(err)
	}
	if live {
		cs, err := e.Engine.Containers(ctx, engine.LabelEnv+"="+p.Name)
		if err != nil {
			return daemonFailed(err)
		}
		if len(cs) > 0 {
			for _, c := range cs {
				if c.Labels[engine.LabelModel] != hash {
					return Outcome{http.StatusConflict, map[string]any{
						"error":       fmt.Sprintf("environment %s is up with a different model; nothing was changed", p.Name),
						"remediation": "take it down first: adele env down " + p.Name, "performed": false}}
				}
			}
			svcs, err := e.Services(ctx, p.Name)
			if err != nil {
				return daemonFailed(err)
			}
			body := b.upBody("unchanged", g.Name, p.Name, row.ExpiresAt, 0, doc.Unset, svcs)
			body["timings"] = timings
			return Outcome{http.StatusOK, body}
		}
		// The ledger says live and the daemon has nothing: record that, then bring it up again.
		b.mu.Lock()
		_, _, err = b.Ledger.Reap(row.ID, ledger.OutcomeGone, "already gone: the daemon had nothing labelled "+p.Name+
			" when it was brought up again", 0, b.now())
		b.mu.Unlock()
		if err != nil {
			return ledgerFailed(err)
		}
	}

	check := req
	check.Params.Ports = compose.Published(model)
	if r := checkStatic(check, g, ttl); r != nil {
		return b.refuseAt(req, g.Name, *r, EnvHost)
	}
	b.mu.Lock()
	n, err := b.Ledger.LiveOf(g.Name, grants.CapDockerCompose)
	var spent int64
	if err == nil {
		spent, err = b.Ledger.Spent(g.Name)
	}
	b.mu.Unlock()
	if err != nil {
		return ledgerFailed(err)
	}
	if n+1 > g.Instances {
		s := strconv.Itoa(n + 1)
		return b.refuseAt(req, g.Name, refusal{grants.LimitInstances, strconv.Itoa(g.Instances), s, s, nil}, EnvHost)
	}
	if spent > g.BudgetCents { // an environment quotes 0.00 (local: no cost); an exhausted budget still refuses
		zero := int64(0)
		return b.refuseAt(req, g.Name, refusal{grants.LimitBudget, grants.FormatMoney(0), grants.FormatMoney(0),
			grants.FormatMoney(spent), &zero}, EnvHost)
	}
	images := compose.Images(model)
	for _, svc := range compose.Services(model) {
		has, err := e.Engine.ImageExists(ctx, images[svc])
		if err != nil {
			return daemonFailed(err)
		}
		if !has {
			return b.refuseEnv(req, g.Name, &compose.Refusal{Kind: compose.KindImage, Service: svc, Setting: "image",
				Value: images[svc], Remedy: MissingImageRemedy(images[svc])})
		}
	}
	if labels, err := e.Engine.NetworkLabels(ctx, compose.Network); err != nil || labels[engine.LabelNetwork] != "nested" {
		why := "it carries no timelike label"
		if err != nil {
			why = err.Error()
		}
		return envFail(http.StatusBadGateway, "the shared network "+compose.Network+" is not timelike's ("+why+"); nothing was created",
			"the operator recreates the stack: make up")
	}

	created := b.now().Truncate(time.Second)
	bytesUp, err := compose.Inject(model, p.Name, created, ttl, hash)
	if err != nil {
		return envFail(http.StatusInternalServerError, "cannot write the checked model: "+err.Error(), "")
	}
	scratch, err := os.MkdirTemp(e.ScratchDir, "tl-up-")
	if err != nil {
		return envFail(http.StatusInternalServerError, "cannot make an empty project directory: "+err.Error(),
			"nothing was created; the operator checks Adele's state directory "+e.ScratchDir+" is hers and writable")
	}
	defer os.RemoveAll(scratch)
	empty, home := filepath.Join(scratch, "project"), filepath.Join(scratch, "home")
	if err := errors.Join(os.Mkdir(empty, 0o700), os.Mkdir(home, 0o700)); err != nil {
		return envFail(http.StatusInternalServerError, "cannot make an empty project directory: "+err.Error(), "nothing was created")
	}
	composing := time.Now()
	_, stderr, err := e.runCompose(ctx, home, []string{"-p", p.Name, "--project-directory", empty, "-f", "-", "up", "-d",
		"--pull", "never", "--no-build", "--remove-orphans"}, bytesUp)
	timings["compose_ms"] = time.Since(composing).Milliseconds()
	if err != nil {
		_, left, derr := e.Engine.Down(context.WithoutCancel(ctx), p.Name)
		what := fmt.Sprintf("compose up failed: %s", lastLines(string(stderr), 6))
		if what == "compose up failed: " {
			what += err.Error()
		}
		remedy := fmt.Sprintf("what it created was removed; the daemon, read back, has %d objects labelled %s left", left.Total(), p.Name)
		if derr != nil {
			remedy = "removing what it created failed: " + derr.Error() + "; the operator checks: docker ps -a --filter label=" + engine.LabelEnv + "=" + p.Name
		}
		return Outcome{http.StatusBadGateway, map[string]any{"error": what, "remediation": remedy, "performed": false,
			"left": left}}
	}
	expires := created.Add(ttl).Truncate(time.Second)
	zero := int64(0)
	undoRaw, _ := json.Marshal(map[string]any{"capability": grants.CapDockerCompose, "action": "down",
		"params": map[string]string{"name": p.Name}})
	undo := string(undoRaw)
	b.mu.Lock()
	id, err := b.Ledger.Performed(ledger.Row{At: b.now(), Grant: g.Name, Session: req.Session, Agent: req.Agent,
		Capability: grants.CapDockerCompose, Action: "up", Resource: p.Name, CostCents: &zero, ExpiresAt: &expires, Undo: undo})
	b.mu.Unlock()
	if err != nil {
		return Outcome{http.StatusInternalServerError, map[string]any{
			"error":     fmt.Sprintf("environment %s was brought up but the ledger write failed: %v", p.Name, err),
			"performed": true, "remediation": "the operator records or removes it: docker exec " + b.container() + " adeled ledger",
		}}
	}
	svcs, err := e.Services(ctx, p.Name)
	if err != nil {
		return daemonFailed(err)
	}
	body := b.upBody(ledger.OutcomePerformed, g.Name, p.Name, &expires, id, doc.Unset, svcs)
	body["undo"] = undo
	timings["adele_ms"] = time.Since(began).Milliseconds()
	body["timings"] = timings
	return Outcome{http.StatusOK, body}
}

func (b *Broker) upBody(outcome, grant, name string, expires *time.Time, id int64, unset []string, svcs []Service) map[string]any {
	if unset == nil {
		unset = []string{}
	}
	body := map[string]any{"outcome": outcome, "grant": grant, "resource": name, "cost_cents": 0, "unset": unset,
		"host_git": b.Envs.HostGit, "services": svcs, "revision": b.Revision}
	if expires != nil {
		body["expires_at"] = expires.UTC().Format(time.RFC3339)
	}
	if id != 0 {
		body["ledger_id"] = id
	}
	return body
}

// MissingImageRemedy is a missing image's remediation, in one place: exit 3 with rule 14's error, no grant
// envelope (FOR-MENTOR Item 29, ratified by plan eab79e9).
func MissingImageRemedy(ref string) string {
	return "the operator pulls it on the host: docker pull " + ref + "; the agent cannot"
}

// NoGrantAllows is the start of a forbidden setting's remediation, in one place (prompt 13 revision 17: exit 2,
// rule 14's error, no operator's command).
const NoGrantAllows = "no grant allows it; "

// refuseEnv records and answers a refusal no grant limit describes: a forbidden setting or an outside file (no
// grant allows either, revision 17) or a missing image (the operator's docker pull, Item 29's ruling).
func (b *Broker) refuseEnv(req Request, grant string, r *compose.Refusal) Outcome {
	needed := r.Value
	if r.Service != "" {
		needed = "service " + r.Service + ": " + r.Value
	}
	allowed, extend, remedy := "no grant allows it", "", NoGrantAllows+r.Remedy
	if r.Kind == compose.KindImage {
		allowed, extend, remedy = "images on the daemon (Adele never pulls)", "docker pull "+r.Value, r.Remedy
	}
	b.mu.Lock()
	id, err := b.Ledger.Refused(ledger.Row{At: b.now(), Grant: grant, Session: req.Session, Agent: req.Agent,
		Capability: req.Capability, Action: req.Action, Resource: req.Params.Name, LimitName: r.Setting,
		Allowed: allowed, Needed: needed, Host: EnvHost, Extend: extend})
	b.mu.Unlock()
	if err != nil {
		return ledgerFailed(err)
	}
	return Outcome{http.StatusUnprocessableEntity, map[string]any{
		"outcome": ledger.OutcomeRefused, "refusal": r.Kind, "setting": r.Setting, "service": r.Service, "value": r.Value,
		"remediation": remedy, "operator_command": extend, "performed": false, "ledger_id": id, "host": EnvHost,
		"grant": grant,
	}}
}

func (e *Envs) resolve(ctx context.Context, dir, name string, files, profiles []string, took *engine.Phases) (compose.Resolved, Outcome, bool) {
	cmd := []string{"resolve", "--workspace", e.Workspace, "--dir", dir, "--project", name}
	for _, f := range files {
		cmd = append(cmd, "--file", f)
	}
	for _, pr := range profiles {
		cmd = append(cmd, "--profile", pr)
	}
	suffix := make([]byte, 3)
	_, _ = rand.Read(suffix)
	stdout, stderr, exit, err := e.Engine.Run(ctx, engine.Sandbox{
		Image: e.SandboxImage, Entrypoint: []string{"/usr/local/bin/adeled"}, Cmd: cmd, User: "10001:10001",
		Env: []string{"HOME=/tmp"}, WorkingDir: dir, Binds: []string{e.Workspace + ":" + e.Workspace + ":ro"},
		Name: "tl-sandbox-" + name + "-" + hex.EncodeToString(suffix), Timeout: SandboxTimeout, Took: took,
	})
	var doc compose.Resolved
	if err != nil {
		return doc, envFail(http.StatusBadGateway, err.Error(), SandboxRemedy(err, e.SandboxImage)), false
	}
	if exit != 0 || json.Unmarshal(stdout, &doc) != nil {
		return doc, envFail(http.StatusBadGateway, fmt.Sprintf("the resolution sandbox exited %d: %s", exit, lastLines(string(stderr), 4)),
			"nothing was created"), false
	}
	if !doc.OK && doc.Refusal == nil {
		return doc, envFail(http.StatusBadRequest, "compose could not resolve the project: "+doc.Error,
			"fix the project's compose file; it was resolved with the workspace's files only, and the agent's environment is not read (put values in the project's .env)"), false
	}
	return doc, Outcome{}, true
}

// SandboxRemedy names what a failed sandbox needs, by its cause (lane 13s0a, item A: "make build" was named
// when the image was there and the daemon slow). It says no environment was created, not that nothing was: a
// create the daemon finishes after the bound leaves a sandbox, which engine.Run removes when it lands (lane 13s0b,
// item A).
func SandboxRemedy(err error, image string) string {
	var se *engine.SandboxError
	switch {
	case errors.As(err, &se) && se.ImageMissing():
		return "nothing was created; the operator builds " + image + " on the host: make build"
	case errors.As(err, &se) && se.TimedOut:
		return "no environment was created; the daemon was slow to create, start or run the sandbox, as a busy host is, " +
			"and if it makes the sandbox after all Adele removes it: retry"
	}
	return "no environment was created; retry, and if it persists the operator checks the daemon on the host"
}

// envDown waits for an up of the same name in progress (Envs' lock), then removes everything labelled with it.
func (b *Broker) envDown(ctx context.Context, req Request) Outcome {
	e, name := b.Envs, req.Params.Name
	e.lock("down " + name)
	defer e.unlock()
	b.mu.Lock()
	row, live, err := b.Ledger.LiveResource(grants.CapDockerCompose, name)
	b.mu.Unlock()
	if err != nil {
		return ledgerFailed(err)
	}
	before, err := e.Engine.Count(ctx, name)
	if err != nil {
		return daemonFailed(err)
	}
	if !live && before.Total() == 0 {
		return envFail(http.StatusNotFound, "no environment named "+name, "list them with adele env status")
	}
	removed, left, err := e.Engine.Down(ctx, name)
	if left.Total() > 0 || err != nil {
		why := ""
		if err != nil {
			why = ": " + err.Error()
		}
		return Outcome{http.StatusBadGateway, map[string]any{
			"error":   fmt.Sprintf("down did not remove everything labelled %s; the daemon, read back, still has %d%s", name, left.Total(), why),
			"removed": removed, "left": left, "remediation": "retry adele env down " + name + "; nothing was recorded"}}
	}
	body := map[string]any{"outcome": "ended", "resource": name, "removed": removed, "left": 0}
	if live {
		cause := fmt.Sprintf("taken down by session %s (adele env down): %d containers, %d networks, %d volumes removed; 0 left, read back from the daemon",
			req.Session, removed.Containers, removed.Networks, removed.Volumes)
		b.mu.Lock()
		id, wrote, err := b.Ledger.Reap(row.ID, ledger.OutcomeReaped, cause, 1, b.now())
		b.mu.Unlock()
		if err != nil {
			return ledgerFailed(err)
		}
		if wrote {
			body["ledger_id"] = id
		}
	}
	return Outcome{http.StatusOK, body}
}

func daemonFailed(err error) Outcome {
	return envFail(http.StatusBadGateway, "the Docker daemon failed: "+err.Error(),
		"retry; if it persists, the operator checks the daemon on the host")
}

func lastLines(s string, n int) string {
	lines := strings.Split(strings.TrimSpace(s), "\n")
	if len(lines) > n {
		lines = lines[len(lines)-n:]
	}
	return strings.Join(lines, " · ")
}

// EnvList is GET /v1/envs: every live environment in the ledger, with its services read back.
func (b *Broker) EnvList(ctx context.Context) (map[string]any, error) {
	if b.Envs == nil {
		return nil, errors.New("this Adele has no Docker daemon")
	}
	b.mu.Lock()
	rows, err := b.Ledger.LiveRows(grants.CapDockerCompose)
	b.mu.Unlock()
	if err != nil {
		return nil, err
	}
	envs := make([]map[string]any, 0, len(rows))
	for _, r := range rows {
		svcs, err := b.Envs.Services(ctx, r.Resource)
		if err != nil {
			return nil, err
		}
		envs = append(envs, envDoc(r, svcs))
	}
	return map[string]any{"envs": envs, "revision": b.Revision, "host_git": b.Envs.HostGit}, nil
}

// EnvGet is GET /v1/envs/NAME, or found false.
func (b *Broker) EnvGet(ctx context.Context, name string) (map[string]any, bool, error) {
	if b.Envs == nil {
		return nil, false, errors.New("this Adele has no Docker daemon")
	}
	b.mu.Lock()
	r, live, err := b.Ledger.LiveResource(grants.CapDockerCompose, name)
	b.mu.Unlock()
	if err != nil || !live {
		return nil, false, err
	}
	svcs, err := b.Envs.Services(ctx, name)
	if err != nil {
		return nil, false, err
	}
	return envDoc(r, svcs), true, nil
}

func envDoc(r ledger.Row, svcs []Service) map[string]any {
	doc := map[string]any{"name": r.Resource, "grant": r.Grant, "session": r.Session, "services": svcs, "ledger_id": r.ID}
	if r.ExpiresAt != nil {
		doc["expires_at"] = r.ExpiresAt.UTC().Format(time.RFC3339)
	}
	return doc
}

// EnvProvider is the reaper's provider for docker.compose (014 D-4; the operator's decision: reap in slice 0).
// List reads environments from the daemon's labels; Delete is Down, read back.
type EnvProvider struct {
	Engine *engine.Client
}

// List returns one Box per labelled environment, with its creation and lifetime from its labels.
func (p *EnvProvider) List(ctx context.Context) ([]Box, error) {
	cs, err := p.Engine.Containers(ctx, engine.LabelEnv)
	if err != nil {
		return nil, err
	}
	seen := map[string]bool{}
	var out []Box
	for _, c := range cs {
		name := c.Labels[engine.LabelEnv]
		if seen[name] {
			continue
		}
		seen[name] = true
		created, _ := time.Parse(time.RFC3339, c.Labels[engine.LabelCreated])
		ttl, _ := strconv.ParseInt(c.Labels[engine.LabelTTL], 10, 64)
		out = append(out, Box{Name: name, CreatedAt: created, TTLSeconds: ttl})
	}
	return out, nil
}

// Delete removes everything labelled with the environment. No such environment is ErrNoSuchResource.
func (p *EnvProvider) Delete(ctx context.Context, name string) error {
	removed, left, err := p.Engine.Down(ctx, name)
	if err != nil {
		return err
	}
	if left.Total() > 0 {
		return fmt.Errorf("%d objects labelled %s are left, read back", left.Total(), name)
	}
	if removed.Total() == 0 {
		return fmt.Errorf("%w: %s", ErrNoSuchResource, name)
	}
	return nil
}

// Record, Noun and Holder name the provider's record in the reaper's causes.
func (p *EnvProvider) Record() string { return "the daemon's labelled objects" }

// Noun is what the record holds.
func (p *EnvProvider) Noun() string { return "environment" }

// Holder is who keeps the record.
func (p *EnvProvider) Holder() string { return "the daemon" }
