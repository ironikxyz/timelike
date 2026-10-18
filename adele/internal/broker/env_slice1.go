package broker

// Feature 13 slice 1 (014 plan § Slice 1): builds from the sandbox's context archive, a devcontainer's lifecycle
// commands, and exec in an environment's container. Up's own flow stays in env.go; what it calls is here.

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"

	"timelike/adele/internal/buildctx"
	"timelike/adele/internal/compose"
	"timelike/adele/internal/engine"
	"timelike/adele/internal/grants"
	"timelike/adele/internal/ledger"
)

// Slice 1's bounds (R13, R16, R17).
const (
	BuildTimeout     = 5 * time.Minute
	LifecycleTimeout = 2 * time.Minute
	ExecDefault      = 100 * time.Second // feature 03's run's default
	ExecMax          = 600 * time.Second
	ExecOutput       = 1 << 20 // bytes kept of each of an exec's stdout and stderr
	lifecycleOutput  = 64 << 10
)

// built is one build's account in up's answer.
type built struct {
	Service string  `json:"service"`
	Image   string  `json:"image"`
	Reused  bool    `json:"reused"`
	Seconds float64 `json:"seconds"`
	made    bool    // this request built it (so a later refusal removes it)
}

// requester is the agent container that asked, read from the daemon by the request's peer address (R18).
func (e *Envs) requester(ctx context.Context, peer string) (id string, answer map[string]string) {
	agents, err := e.Engine.Agents(ctx)
	if err != nil {
		return "unknown", map[string]string{"unknown": "the daemon's list of agent containers failed: " + err.Error()}
	}
	if id, ok := engine.RequesterOf(agents, peer); ok {
		return id, map[string]string{"container": id}
	}
	return "unknown", map[string]string{"unknown": "no timelike agent container has the address " + peer}
}

// bases refuses the first base image a build names that is not on the daemon: a build pulls nothing (R15).
func (b *Broker) bases(ctx context.Context, req Request, grant string, scans []compose.BuildScan) (Outcome, bool) {
	for _, s := range scans {
		for _, ref := range s.Bases {
			has, err := b.Envs.Engine.ImageExists(ctx, ref)
			if err != nil {
				return daemonFailed(err), false
			}
			if !has {
				return b.refuseEnv(req, grant, &compose.Refusal{Kind: compose.KindImage, Service: s.Service, Setting: "FROM",
					Value: ref, Remedy: MissingImageRemedy(ref) + " (a build pulls nothing)"}), false
			}
		}
	}
	return Outcome{}, true
}

// buildAll builds each scanned build, or reuses the image an unchanged one made (R16). It returns each service's image
// tag for Inject, the account for up's answer, and either nothing or the outcome that ends the request.
func (b *Broker) buildAll(ctx context.Context, req Request, grant, requester string, scans []compose.BuildScan) (
	map[string]string, []built, Outcome, bool) {
	e, name := b.Envs, req.Params.Name
	tags := map[string]string{}
	var out []built
	for _, s := range scans {
		tag := buildctx.Tag(name, s.Service, s.Key)
		tags[s.Service] = tag
		labels, has, err := e.Engine.ImageLabels(ctx, tag)
		if err != nil {
			return nil, out, daemonFailed(err), false
		}
		if has && labels[engine.LabelBuildKey] == s.Key && labels[engine.LabelEnv] == name {
			out = append(out, built{Service: s.Service, Image: tag, Reused: true})
			continue
		}
		began := time.Now()
		if outcome, ok := b.buildOne(ctx, req, grant, requester, s, tag); !ok {
			e.removeBuilt(out)
			return nil, out, outcome, false
		}
		out = append(out, built{Service: s.Service, Image: tag, Seconds: time.Since(began).Round(100 * time.Millisecond).Seconds(),
			made: true})
	}
	return tags, out, Outcome{}, true
}

// buildOne pipes the context sandbox's archive into the daemon's build (R14, R15). Adele copies the bytes and never
// opens them. An archive whose digest is not the one resolve keyed keeps no image: the project changed in between.
func (b *Broker) buildOne(ctx context.Context, req Request, grant, requester string, s compose.BuildScan, tag string) (Outcome, bool) {
	e := b.Envs
	suffix := make([]byte, 3)
	_, _ = rand.Read(suffix)
	pr, pw := io.Pipe()
	type ended struct {
		stderr []byte
		exit   int
		err    error
	}
	done := make(chan ended, 1)
	go func() {
		stderr, exit, err := e.Engine.RunStream(ctx, engine.Sandbox{
			Image: e.SandboxImage, Entrypoint: []string{"/usr/local/bin/adeled"}, User: "10001:10001", Env: []string{"HOME=/tmp"},
			Cmd:        []string{"context", "--workspace", e.Workspace, "--context", s.Context, "--dockerfile", s.Dockerfile},
			WorkingDir: s.Context, Binds: []string{e.Workspace + ":" + e.Workspace + ":ro"},
			Name: "tl-sandbox-" + req.Params.Name + "-ctx-" + hex.EncodeToString(suffix), Timeout: BuildTimeout,
		}, pw)
		switch {
		case err != nil:
			pw.CloseWithError(err)
		case exit != 0:
			pw.CloseWithError(fmt.Errorf("the context sandbox exited %d: %s", exit, lastLines(string(stderr), 2)))
		default:
			pw.Close()
		}
		done <- ended{stderr, exit, err}
	}()
	labels := map[string]string{engine.LabelEnv: req.Params.Name, engine.LabelSession: req.Session, engine.LabelGrant: grant,
		engine.LabelRequester: requester, engine.LabelBuildKey: s.Key, engine.LabelCreated: b.now().Format(time.RFC3339)}
	_, berr := e.Engine.Build(ctx, engine.BuildSpec{Tag: tag, Dockerfile: s.DockerfileName, Target: s.Target, Args: s.Args,
		Labels: labels, Timeout: BuildTimeout}, pr)
	pr.CloseWithError(errors.New("the build ended"))
	sb := <-done
	where := map[string]any{"service": s.Service}
	if berr != nil {
		_ = e.Engine.RemoveImage(context.WithoutCancel(ctx), tag)
		var be *engine.BuildError
		if !errors.As(berr, &be) {
			return daemonFailed(berr), false
		}
		where["step"] = be.Step
		switch be.Kind {
		case "pull":
			return b.refuseEnv(req, grant, &compose.Refusal{Kind: compose.KindImage, Service: s.Service, Setting: "FROM",
				Value: be.Image, Remedy: MissingImageRemedy(be.Image) + " (the daemon began to pull it, so the build was stopped: a build pulls nothing)"}), false
		case "timeout":
			where["last_lines"] = be.Last
			return Outcome{http.StatusGatewayTimeout, map[string]any{"error": be.Error(), "timed_out": true, "build": where,
				"performed": false, "remediation": "nothing was created; make the step quicker, or the operator raises Adele's build bound"}}, false
		case "step":
			where["last_lines"] = be.Last
			return Outcome{http.StatusBadGateway, map[string]any{"error": "the build of " + s.Service + " failed: " + be.Error(), "build": where,
				"performed": false, "remediation": "nothing was created; fix the Dockerfile or the context and bring it up again"}}, false
		}
		if sb.err != nil || sb.exit != 0 {
			return envFail(http.StatusBadGateway, "the build of "+s.Service+" got no context: "+contextFailure(sb.stderr, sb.exit, sb.err),
				"nothing was created; retry, and if it persists the operator checks the daemon on the host"), false
		}
		return daemonFailed(berr), false
	}
	if digest := contextDigest(sb.stderr); sb.err != nil || sb.exit != 0 || digest != s.Digest {
		_ = e.Engine.RemoveImage(context.WithoutCancel(ctx), tag)
		why := contextFailure(sb.stderr, sb.exit, sb.err)
		if sb.err == nil && sb.exit == 0 {
			why = "the context changed between resolving the project and building it"
		}
		return envFail(http.StatusConflict, "the build of "+s.Service+" was not kept: "+why, "nothing was created; bring it up again"), false
	}
	return Outcome{}, true
}

func contextDigest(stderr []byte) string {
	lines := strings.Split(strings.TrimSpace(string(stderr)), "\n")
	var sum struct {
		Digest string `json:"digest"`
	}
	_ = json.Unmarshal([]byte(lines[len(lines)-1]), &sum)
	return sum.Digest
}

func contextFailure(stderr []byte, exit int, err error) string {
	if err != nil {
		return err.Error()
	}
	return fmt.Sprintf("the context sandbox exited %d: %s", exit, lastLines(string(stderr), 2))
}

// removeBuilt removes the images this request built, when it is refused after building: they belong to an
// environment that was not created.
func (e *Envs) removeBuilt(bs []built) {
	for _, x := range bs {
		if x.made {
			_ = e.Engine.RemoveImage(context.Background(), x.Image)
		}
	}
}

// lifecycleRun is one lifecycle command's account in up's answer.
type lifecycleRun struct {
	Name      string   `json:"name"`
	ExitCode  int      `json:"exit_code"`
	LastLines []string `json:"last_lines"`
	TimedOut  bool     `json:"timed_out"`
}

// lifecycle runs a new devcontainer's lifecycle commands in its primary container, in order, stopping at the first
// that fails or passes its bound (R13). The environment is recorded and stays up whatever they do.
func (e *Envs) lifecycle(ctx context.Context, name string, dev *compose.Dev) ([]lifecycleRun, error) {
	runs := []lifecycleRun{}
	if dev == nil || len(dev.Lifecycle) == 0 {
		return runs, nil
	}
	c, err := e.primary(ctx, name, dev.Primary)
	if err != nil {
		return runs, err
	}
	env, err := e.remoteEnv(ctx, c)
	if err != nil {
		return runs, err
	}
	for _, cmd := range dev.Lifecycle {
		argv := cmd.Argv
		if cmd.Shell != "" {
			argv = []string{"/bin/sh", "-c", cmd.Shell}
		}
		res, err := e.Engine.Exec(ctx, c.ID, engine.ExecSpec{Cmd: argv, User: c.Labels[engine.LabelRemoteUser],
			WorkingDir: c.Labels[engine.LabelWorkdir], Env: env, Timeout: LifecycleTimeout, MaxOutput: lifecycleOutput})
		if err != nil {
			return runs, fmt.Errorf("%s could not be run: %w", cmd.Name, err)
		}
		run := lifecycleRun{Name: cmd.Name, ExitCode: res.ExitCode, TimedOut: res.TimedOut,
			LastLines: tailLines(string(res.Stdout)+string(res.Stderr), 6)}
		runs = append(runs, run)
		if res.TimedOut || res.ExitCode != 0 {
			break
		}
	}
	return runs, nil
}

func tailLines(s string, n int) []string {
	out := []string{}
	for _, l := range strings.Split(strings.TrimRight(s, "\n"), "\n") {
		if l = strings.TrimRight(l, "\r"); l != "" {
			out = append(out, l)
		}
	}
	if len(out) > n {
		out = out[len(out)-n:]
	}
	return out
}

// primary returns the container of service in the environment, read back by its labels.
func (e *Envs) primary(ctx context.Context, name, service string) (engine.Container, error) {
	cs, err := e.Engine.Containers(ctx, engine.LabelEnv+"="+name, engine.ComposeService+"="+service)
	if err != nil {
		return engine.Container{}, err
	}
	if len(cs) == 0 {
		return engine.Container{}, fmt.Errorf("the daemon has no container for service %s of %s", service, name)
	}
	return cs[0], nil
}

// remoteEnv is the container's remoteEnv label as KEY=VALUE, its ${containerEnv:X} read from the container's own
// environment on the daemon (R12).
func (e *Envs) remoteEnv(ctx context.Context, c engine.Container) ([]string, error) {
	raw := c.Labels[engine.LabelRemoteEnv]
	if raw == "" {
		return nil, nil
	}
	var vars map[string]string
	if err := json.Unmarshal([]byte(raw), &vars); err != nil {
		return nil, fmt.Errorf("the container's remote-env label is not JSON: %w", err)
	}
	have := map[string]string{}
	if strings.Contains(raw, "${containerEnv:") {
		env, err := e.Engine.ContainerEnv(ctx, c.ID)
		if err != nil {
			return nil, err
		}
		for _, kv := range env {
			if k, v, ok := strings.Cut(kv, "="); ok {
				have[k] = v
			}
		}
	}
	out := make([]string, 0, len(vars))
	for _, k := range sortedNames(vars) {
		v := vars[k]
		for {
			i := strings.Index(v, "${containerEnv:")
			if i < 0 {
				break
			}
			j := strings.Index(v[i:], "}")
			if j < 0 {
				break
			}
			ref := v[i+len("${containerEnv:") : i+j]
			key, def, _ := strings.Cut(ref, ":")
			val, ok := have[key]
			if !ok {
				val = def
			}
			v = v[:i] + val + v[i+j+1:]
		}
		out = append(out, k+"="+v)
	}
	return out, nil
}

func sortedNames(m map[string]string) []string {
	out := make([]string, 0, len(m))
	for k := range m {
		out = append(out, k)
	}
	for i := 1; i < len(out); i++ {
		for j := i; j > 0 && out[j] < out[j-1]; j-- {
			out[j], out[j-1] = out[j-1], out[j]
		}
	}
	return out
}

// envExec runs a command in a running container of a live environment (R17): as its remoteUser or its image's user,
// never privileged, bounded, and recorded as a performed row with no undo.
func (b *Broker) envExec(ctx context.Context, req Request) Outcome {
	e, p := b.Envs, req.Params
	if len(p.Cmd) == 0 {
		return envFail(http.StatusBadRequest, "exec needs a command", "e.g. adele env exec -- pytest -q")
	}
	timeout := ExecDefault
	if p.TimeoutS > 0 {
		timeout = time.Duration(p.TimeoutS * float64(time.Second))
	}
	if timeout > ExecMax {
		return envFail(http.StatusBadRequest, fmt.Sprintf("an exec's bound is at most %s", ExecMax), "use a smaller --timeout")
	}
	b.mu.Lock()
	row, live, err := b.Ledger.LiveResource(grants.CapDockerCompose, p.Name)
	b.mu.Unlock()
	if err != nil {
		return ledgerFailed(err)
	}
	if !live {
		return envFail(http.StatusNotFound, "no live environment named "+p.Name, "list them with adele env status")
	}
	cs, err := e.Engine.Containers(ctx, engine.LabelEnv+"="+p.Name)
	if err != nil {
		return daemonFailed(err)
	}
	var target *engine.Container
	services := []string{}
	for i, c := range cs {
		svc := c.Labels[engine.ComposeService]
		services = append(services, svc)
		switch {
		case p.Service != "" && svc == p.Service:
			target = &cs[i]
		case p.Service == "" && c.Labels[engine.LabelDevcontainer] == "1":
			target = &cs[i]
		}
	}
	if p.Service == "" && target == nil && len(cs) == 1 {
		target = &cs[0]
	}
	switch {
	case target == nil && p.Service != "":
		return envFail(http.StatusNotFound, fmt.Sprintf("%s has no service %s", p.Name, p.Service), "its services: "+strings.Join(services, ", "))
	case target == nil:
		return Outcome{http.StatusConflict, map[string]any{"error": p.Name + " has more than one service; name one",
			"services": services, "remediation": "add --service S"}}
	case target.State != "running":
		return envFail(http.StatusBadGateway, fmt.Sprintf("service %s of %s is %s, not running", target.Labels[engine.ComposeService], p.Name, target.State),
			"bring it up again: adele env up, or look at it: adele env status "+p.Name)
	}
	env, err := e.remoteEnv(ctx, *target)
	if err != nil {
		return envFail(http.StatusBadGateway, err.Error(), "")
	}
	user := target.Labels[engine.LabelRemoteUser]
	res, err := e.Engine.Exec(ctx, target.ID, engine.ExecSpec{Cmd: p.Cmd, User: user, WorkingDir: target.Labels[engine.LabelWorkdir],
		Env: env, Timeout: timeout, MaxOutput: ExecOutput})
	if err != nil {
		return daemonFailed(err)
	}
	svc := target.Labels[engine.ComposeService]
	ended := fmt.Sprintf("exit %d", res.ExitCode)
	if res.TimedOut {
		ended = "past its bound of " + timeout.String()
	}
	argv := strings.Join(p.Cmd, " ")
	if len(argv) > 200 {
		argv = argv[:197] + "..."
	}
	b.mu.Lock()
	id, err := b.Ledger.Recorded(ledger.Row{At: b.now(), Grant: row.Grant, Session: req.Session, Agent: req.Agent,
		Capability: grants.CapDockerCompose, Action: "exec", Resource: p.Name,
		Cause: fmt.Sprintf("exec in service %s as %s: %s: %s", svc, userWords(user), argv, ended)})
	b.mu.Unlock()
	if err != nil {
		return ledgerFailed(err)
	}
	body := map[string]any{"outcome": ledger.OutcomePerformed, "exit_code": res.ExitCode, "stdout": string(res.Stdout),
		"stderr": string(res.Stderr), "dropped": map[string]int64{"stdout": res.Dropped[0], "stderr": res.Dropped[1]},
		"service": svc, "user": user, "seconds": res.Took.Seconds(), "ledger_id": id, "resource": p.Name}
	if res.TimedOut {
		body["timed_out"] = true
		body["error"] = fmt.Sprintf("the command did not finish within %s; the Engine API cannot stop an exec'd process, so it may still be running in the container", timeout)
		body["remediation"] = "adele env down " + p.Name + " removes the container"
		return Outcome{http.StatusGatewayTimeout, body}
	}
	return Outcome{http.StatusOK, body}
}

func userWords(user string) string {
	if user == "" {
		return "the image's user"
	}
	return user
}
