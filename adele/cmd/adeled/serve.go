package main

import (
	"context"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"sync"
	"syscall"
	"time"

	"timelike/adele/internal/broker"
	"timelike/adele/internal/engine"
	"timelike/adele/internal/grants"
	"timelike/adele/internal/ledger"
	"timelike/adele/internal/reaper"
	"timelike/adele/internal/standin"
)

// setup is everything serve needs, built before anything listens: a malformed grant file, an
// unreadable canary or an unstamped build stops Adele at start (FR-6, H8).
func setup(e env, stderr io.Writer) (*broker.Broker, *ledger.Ledger, int) {
	if revision == "" {
		fmt.Fprintln(stderr, "adeled: this build carries no revision stamp — rebuild with make build (H8)")
		return nil, nil, exitFailure
	}
	file, err := grants.Load(e.get("ADELE_GRANTS"))
	if err != nil {
		fmt.Fprintf(stderr, "adeled: %v\n", err)
		return nil, nil, exitUsage
	}
	canary, err := standin.ReadCanary(e.get("ADELE_CANARY_FILE"))
	if err != nil {
		fmt.Fprintf(stderr, "adeled: credential: %v — the operator runs make canary, then make up\n", err)
		return nil, nil, exitUsage
	}
	led, err := ledger.Open(e.get("ADELE_DB"))
	if err != nil {
		fmt.Fprintf(stderr, "adeled: ledger %s: %v\n", e.get("ADELE_DB"), err)
		return nil, nil, exitFailure
	}
	b := &broker.Broker{
		Grants: file, Ledger: led, Container: e.get("ADELE_CONTAINER"), Revision: revision,
		Upstream: broker.NewStandinClient(e.get("ADELE_STANDIN_URL"), canary),
		Envs:     envs(e),
	}
	return b, led, exitOK
}

// envs is the docker.compose capability when the socket is mounted (feature 13), else nil: then an environment
// request is answered "no Docker daemon", and nothing else changes.
func envs(e env) *broker.Envs {
	sock := e.get("ADELE_DOCKER_SOCKET")
	if fi, err := os.Stat(sock); err != nil || fi.Mode()&os.ModeSocket == 0 {
		return nil
	}
	return &broker.Envs{Engine: engine.New(sock), Workspace: e.get("TIMELIKE_WORKSPACE"), HostGit: e.get("TIMELIKE_HOST_GIT"),
		SandboxImage: e.get("ADELE_SANDBOX_IMAGE"), ComposeBin: e.get("ADELE_COMPOSE_BIN")}
}

// newReaper is the reaper over this Adele's ledger and capability (spec FR-24, D-12). lock is the
// broker's request lock in serve, nil in the operator's own process.
func newReaper(e env, led *ledger.Ledger, up *broker.StandinClient, lock sync.Locker, envs *broker.Envs) (*reaper.Reaper, error) {
	r := &reaper.Reaper{Ledger: led, Provider: up, Lock: lock, Container: e.get("ADELE_CONTAINER")}
	if envs != nil { // feature 13: expired environments are reaped too (the operator's decision, Item 27 Q4)
		r.Providers = map[string]reaper.Provider{grants.CapDockerCompose: &broker.EnvProvider{Engine: envs.Engine}}
	}
	if v := e.get("ADELE_REAP_INTERVAL"); v != "" {
		d, err := time.ParseDuration(v)
		if err != nil || d < 100*time.Millisecond || d > time.Hour {
			return nil, fmt.Errorf("ADELE_REAP_INTERVAL %q is not a duration between 100ms and 1h", v)
		}
		r.Interval = d
	}
	if v := e.get("ADELE_REAP_PASSES"); v != "" {
		n, err := strconv.Atoi(v)
		if err != nil || n < 1 || n > 100 {
			return nil, fmt.Errorf("ADELE_REAP_PASSES %q is not a whole number from 1 to 100", v)
		}
		r.Passes = n
	}
	return r, nil
}

// serve runs until SIGTERM or SIGINT. ready, when non-nil, receives the bound address (tests).
func serve(e env, stderr io.Writer, ready chan<- string) int {
	b, led, code := setup(e, stderr)
	if code != exitOK {
		return code
	}
	defer led.Close()
	reap, err := newReaper(e, led, b.Upstream.(*broker.StandinClient), b.Locker(), b.Envs)
	if err != nil {
		fmt.Fprintf(stderr, "adeled: %v\n", err)
		return exitUsage
	}
	ln, err := net.Listen("tcp", e.get("ADELE_LISTEN"))
	if err != nil {
		fmt.Fprintf(stderr, "adeled: listen %s: %v\n", e.get("ADELE_LISTEN"), err)
		return exitFailure
	}
	srv := &http.Server{
		Handler: b.Handler(), ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout: 10 * time.Second, WriteTimeout: 30 * time.Second,
	}
	fmt.Fprintf(stderr, "adeled: serving on %s · %d grants (%v) · revision %s · reaping every %s · %s\n",
		ln.Addr(), len(b.Grants.Grants), b.Grants.Names(), revision, reapEvery(reap), envsLine(b.Envs))
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGTERM, os.Interrupt)
	defer stop()
	if ready != nil { // after NotifyContext: a signal sent on ready is handled, never fatal
		ready <- ln.Addr().String()
	}
	errc := make(chan error, 1)
	go func() { errc <- srv.Serve(ln) }()
	// The reaper runs beside the request interface for as long as Adele serves, whatever the agent does
	// (spec FR-24). Its first pass is at once, so a restart reaps what expired while she was down.
	reapCtx, stopReaper := context.WithCancel(ctx)
	reaped := make(chan struct{})
	go func() { reap.Run(reapCtx, stderr); close(reaped) }()
	defer func() { stopReaper(); <-reaped }()
	select {
	case err := <-errc:
		fmt.Fprintf(stderr, "adeled: %v\n", err)
		return exitFailure
	case <-ctx.Done():
	}
	shut, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if err := srv.Shutdown(shut); err != nil && !errors.Is(err, http.ErrServerClosed) {
		fmt.Fprintf(stderr, "adeled: shutdown: %v\n", err)
	}
	return exitOK
}

// health is the container's healthcheck: scratch has no shell or curl, so Adele checks herself.
func health(e env, stdout, stderr io.Writer) int {
	_, port, err := net.SplitHostPort(e.get("ADELE_LISTEN"))
	if err != nil {
		fmt.Fprintf(stderr, "adeled: ADELE_LISTEN %q: %v\n", e.get("ADELE_LISTEN"), err)
		return exitFailure
	}
	c := &http.Client{Timeout: 2 * time.Second}
	resp, err := c.Get("http://127.0.0.1:" + port + "/v1/health")
	if err != nil {
		fmt.Fprintf(stderr, "adeled: unhealthy: %v\n", err)
		return exitFailure
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		fmt.Fprintf(stderr, "adeled: unhealthy: HTTP %d\n", resp.StatusCode)
		return exitFailure
	}
	fmt.Fprintln(stdout, "healthy")
	return exitOK
}

func reapEvery(r *reaper.Reaper) string {
	if r.Interval > 0 {
		return r.Interval.String()
	}
	return reaper.DefaultInterval.String()
}

func envsLine(e *broker.Envs) string {
	switch {
	case e == nil:
		return "docker.compose: no socket, so no environments"
	case e.Workspace == "":
		return "docker.compose: the socket, but no workspace mounted"
	}
	return "docker.compose: workspace " + e.Workspace + ", host git " + e.HostGit
}
