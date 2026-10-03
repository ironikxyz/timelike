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
	"syscall"
	"time"

	"timelike/adele/internal/broker"
	"timelike/adele/internal/grants"
	"timelike/adele/internal/ledger"
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
	}
	return b, led, exitOK
}

// serve runs until SIGTERM or SIGINT. ready, when non-nil, receives the bound address (tests).
func serve(e env, stderr io.Writer, ready chan<- string) int {
	b, led, code := setup(e, stderr)
	if code != exitOK {
		return code
	}
	defer led.Close()
	ln, err := net.Listen("tcp", e.get("ADELE_LISTEN"))
	if err != nil {
		fmt.Fprintf(stderr, "adeled: listen %s: %v\n", e.get("ADELE_LISTEN"), err)
		return exitFailure
	}
	srv := &http.Server{
		Handler: b.Handler(), ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout: 10 * time.Second, WriteTimeout: 30 * time.Second,
	}
	fmt.Fprintf(stderr, "adeled: serving on %s · %d grants (%v) · revision %s\n",
		ln.Addr(), len(b.Grants.Grants), b.Grants.Names(), revision)
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGTERM, os.Interrupt)
	defer stop()
	if ready != nil { // after NotifyContext: a signal sent on ready is handled, never fatal
		ready <- ln.Addr().String()
	}
	errc := make(chan error, 1)
	go func() { errc <- srv.Serve(ln) }()
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
