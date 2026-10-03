// Command adele-standin is the STAND-IN capability (feature 004, slice 0): a test and demo service that
// lives inside the compose project, under the `standin` profile, and is plainly not a provider. It
// refuses every request without Adele's canary credential. It proves the grant path and credential
// isolation; it proves nothing about any real provider (spec, "What the stand-in proves").
//
//	adele-standin serve   the container's entrypoint
//	adele-standin list    print its own record (tests read it: "performed" / "nothing performed")
//	adele-standin health  exit 0 if this container's stand-in answers (the healthcheck)
package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"syscall"
	"time"

	"timelike/adele/internal/standin"
)

const (
	exitOK      = 0
	exitFailure = 1
	exitUsage   = 2
)

type env func(string) string

func (e env) get(key string) string {
	if v := e(key); v != "" {
		return v
	}
	return map[string]string{
		"ADELE_CANARY_FILE": "/run/adele-secret/canary",
		"STANDIN_RECORD":    "/var/lib/standin/boxes.json",
		"STANDIN_LISTEN":    ":8481",
	}[key]
}

func main() {
	os.Exit(run(os.Args[1:], os.Getenv, os.Stdout, os.Stderr, nil))
}

func run(args []string, getenv func(string) string, stdout, stderr io.Writer, ready chan<- string) int {
	e := env(getenv)
	cmd := ""
	if len(args) > 0 {
		cmd = args[0]
	}
	switch cmd {
	case "serve":
		return serve(e, stderr, ready)
	case "list":
		return list(e, stdout, stderr)
	case "health":
		return health(e, stdout, stderr)
	}
	fmt.Fprintln(stderr, "usage: adele-standin serve | list | health  (a stand-in for tests and the demo; not a provider)")
	return exitUsage
}

func serve(e env, stderr io.Writer, ready chan<- string) int {
	canary, err := standin.ReadCanary(e.get("ADELE_CANARY_FILE"))
	if err != nil {
		fmt.Fprintf(stderr, "adele-standin: credential: %v\n", err)
		return exitUsage
	}
	store, err := standin.NewStore(e.get("STANDIN_RECORD"))
	if err != nil {
		fmt.Fprintf(stderr, "adele-standin: record: %v\n", err)
		return exitFailure
	}
	if err := writable(filepath.Dir(e.get("STANDIN_RECORD"))); err != nil {
		fmt.Fprintf(stderr, "adele-standin: record directory is not writable: %v\n", err)
		return exitFailure
	}
	ln, err := net.Listen("tcp", e.get("STANDIN_LISTEN"))
	if err != nil {
		fmt.Fprintf(stderr, "adele-standin: listen: %v\n", err)
		return exitFailure
	}
	srv := &http.Server{
		Handler: standin.Handler(canary, store, nil), ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout: 10 * time.Second, WriteTimeout: 30 * time.Second,
	}
	fmt.Fprintf(stderr, "adele-standin: STAND-IN, not a provider · serving on %s · %d boxes on record\n",
		ln.Addr(), len(store.List()))
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGTERM, os.Interrupt)
	defer stop()
	if ready != nil { // after NotifyContext: a signal sent on ready is handled, never fatal
		ready <- ln.Addr().String()
	}
	errc := make(chan error, 1)
	go func() { errc <- srv.Serve(ln) }()
	select {
	case err := <-errc:
		fmt.Fprintf(stderr, "adele-standin: %v\n", err)
		return exitFailure
	case <-ctx.Done():
	}
	shut, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if err := srv.Shutdown(shut); err != nil && !errors.Is(err, http.ErrServerClosed) {
		fmt.Fprintf(stderr, "adele-standin: shutdown: %v\n", err)
	}
	return exitOK
}

// list reads the record file directly, not through HTTP: it is the stand-in's own account (P004).
func list(e env, stdout, stderr io.Writer) int {
	store, err := standin.NewStore(e.get("STANDIN_RECORD"))
	if err != nil {
		fmt.Fprintf(stderr, "adele-standin: record: %v\n", err)
		return exitFailure
	}
	enc := json.NewEncoder(stdout)
	enc.SetIndent("", "  ")
	_ = enc.Encode(store.List())
	return exitOK
}

// health only connects: every HTTP request needs the canary, and the healthcheck must not hold it.
func health(e env, stdout, stderr io.Writer) int {
	_, port, err := net.SplitHostPort(e.get("STANDIN_LISTEN"))
	if err != nil {
		fmt.Fprintf(stderr, "adele-standin: STANDIN_LISTEN: %v\n", err)
		return exitFailure
	}
	conn, err := net.DialTimeout("tcp", "127.0.0.1:"+port, 2*time.Second)
	if err != nil {
		fmt.Fprintf(stderr, "adele-standin: unhealthy: %v\n", err)
		return exitFailure
	}
	_ = conn.Close()
	fmt.Fprintln(stdout, "healthy")
	return exitOK
}

// writable proves at start that the record can be written, so a misconfigured volume fails here
// rather than on the first create (found by T008's units).
func writable(dir string) error {
	f, err := os.CreateTemp(dir, ".writable-*")
	if err != nil {
		return err
	}
	name := f.Name()
	_ = f.Close()
	return os.Remove(name)
}
