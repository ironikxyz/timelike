package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"os"
	"os/signal"
	"path/filepath"
	"strings"
	"sync"
	"syscall"
	"testing"
	"time"
)

func TestServeStartupFailures(t *testing.T) {
	cases := []struct {
		name    string
		rev     string
		arrange func(f *fixture)
		code    int
		want    string
	}{
		{"unstamped", "", nil, exitFailure, "carries no revision stamp"},
		{"malformed grants", "abc123", func(f *fixture) {
			f.write("grants.conf", "[grant demo]\ncapabilities = standin.box\nbogus = 1\n")
		}, exitUsage, "grants.conf:3: unknown key \"bogus\""},
		{"canary missing", "abc123", func(f *fixture) {
			f.vars["ADELE_CANARY_FILE"] = filepath.Join(f.dir, "no-canary")
		}, exitUsage, "credential: "},
		{"canary invalid", "abc123", func(f *fixture) {
			f.write("canary", "SECRET-VALUE-DO-NOT-ECHO\n")
		}, exitUsage, "is not tlcanary- and 32 lowercase hex characters"},
		{"canary empty", "abc123", func(f *fixture) { f.write("canary", "  \n") }, exitUsage, "is empty"},
		{"db unopenable", "abc123", func(f *fixture) {
			f.vars["ADELE_DB"] = filepath.Join(f.dir, "no", "such", "dir", "adele.db")
		}, exitFailure, "adeled: ledger "},
		{"port in use", "abc123", func(f *fixture) { f.vars["ADELE_LISTEN"] = busyAddr(t) }, exitFailure, "adeled: listen "},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			f := newFixture(t)
			withRevision(t, tc.rev)
			if tc.arrange != nil {
				tc.arrange(f)
			}
			// Through run, as the entrypoint calls it; every one of these returns before serving.
			code, out, errs := f.run("serve")
			if code != tc.code || !strings.Contains(errs, tc.want) || out != "" {
				t.Errorf("code %d (want %d), stdout %q, stderr %q (want %q)", code, tc.code, out, errs, tc.want)
			}
			if strings.Contains(errs, "SECRET-VALUE") || strings.Contains(errs, testCanary) {
				t.Errorf("stderr echoes the canary file's content: %q", errs)
			}
		})
	}
}

// TestSetupHandler is the happy path without the process signal: setup's broker serves health
// with the revision, the grants and the request routes.
func TestSetupHandler(t *testing.T) {
	f := newFixture(t)
	withRevision(t, "feedface")
	var errb bytes.Buffer
	b, led, code := setup(f.env(), &errb)
	if code != exitOK {
		t.Fatalf("setup: code %d, stderr %q", code, errb.String())
	}
	defer led.Close()
	if b.Revision != "feedface" || b.Container != "timelike-adele" || b.Upstream == nil {
		t.Errorf("broker: %+v", b)
	}
	srv := httptest.NewServer(b.Handler())
	defer srv.Close()

	var health struct {
		Service, Revision string
		Grants            []string
	}
	getJSON(t, srv.URL+"/v1/health", http.StatusOK, &health)
	if health.Service != "adele" || health.Revision != "feedface" || strings.Join(health.Grants, ",") != "demo,other" {
		t.Errorf("health: %+v", health)
	}
	var gl struct {
		Grants []map[string]any `json:"grants"`
	}
	getJSON(t, srv.URL+"/v1/grants", http.StatusOK, &gl)
	if len(gl.Grants) != 2 || gl.Grants[0]["name"] != "demo" {
		t.Errorf("grants: %+v", gl)
	}
	resp, err := http.Get(srv.URL + "/v1/requests")
	if err != nil {
		t.Fatal(err)
	}
	resp.Body.Close()
	if resp.StatusCode != http.StatusMethodNotAllowed {
		t.Errorf("GET /v1/requests: %d", resp.StatusCode)
	}
}

func getJSON(t *testing.T, url string, want int, out any) {
	t.Helper()
	resp, err := http.Get(url)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	data, _ := io.ReadAll(resp.Body)
	if resp.StatusCode != want {
		t.Fatalf("GET %s: %d %s", url, resp.StatusCode, data)
	}
	if err := json.Unmarshal(data, out); err != nil {
		t.Fatalf("GET %s: %v in %s", url, err, data)
	}
}

// serveUntilSignalled runs start, waits for its address, calls probe and then stops it with a
// SIGINT to this process. It is safe only because:
//   - the test registers its own SIGINT channel first, so the process never takes SIGINT's default
//     action (termination), even if serve had not yet registered its handler;
//   - probe must get an HTTP answer before the signal is sent. serve calls signal.NotifyContext
//     before it starts srv.Serve, so an answered request proves serve's handler is registered (the
//     ready channel alone does not: serve sends on it before NotifyContext);
//   - no other test in this package uses signals or t.Parallel, and the signal goes to this test
//     binary only (getpid), never to another package's process.
func serveUntilSignalled(t *testing.T, start func(ready chan<- string) int, probe func(addr string) error) int {
	t.Helper()
	guard := make(chan os.Signal, 1)
	signal.Notify(guard, os.Interrupt)
	defer signal.Stop(guard)

	ready := make(chan string, 1)
	done := make(chan int, 1)
	go func() { done <- start(ready) }()
	var addr string
	select {
	case addr = <-ready:
	case code := <-done:
		t.Fatalf("serve returned %d before it was ready", code)
	case <-time.After(10 * time.Second):
		t.Fatal("serve never became ready")
	}
	probeErr := probe(addr)
	if err := syscall.Kill(os.Getpid(), syscall.SIGINT); err != nil {
		t.Fatalf("signal self: %v", err)
	}
	select {
	case code := <-done:
		if probeErr != nil {
			t.Error(probeErr)
		}
		return code
	case <-time.After(10 * time.Second):
		t.Fatalf("serve did not stop on SIGINT (probe: %v)", probeErr)
	}
	return -1
}

func TestServeLifecycle(t *testing.T) {
	f := newFixture(t)
	withRevision(t, "c0ffee42")
	var errb syncBuffer
	code := serveUntilSignalled(t, func(ready chan<- string) int {
		return serve(f.env(), &errb, ready)
	}, func(addr string) error {
		c := &http.Client{Timeout: 5 * time.Second}
		var resp *http.Response
		var err error
		for i := 0; i < 50; i++ { // the listener is bound; Serve starts a moment later
			if resp, err = c.Get("http://" + addr + "/v1/health"); err == nil {
				break
			}
			time.Sleep(20 * time.Millisecond)
		}
		if err != nil {
			return err
		}
		defer resp.Body.Close()
		var h struct{ Revision string }
		if err := json.NewDecoder(resp.Body).Decode(&h); err != nil {
			return err
		}
		if resp.StatusCode != http.StatusOK || h.Revision != "c0ffee42" {
			return fmt.Errorf("health: %d %+v", resp.StatusCode, h)
		}
		// The healthcheck command against the live server.
		f.vars["ADELE_LISTEN"] = addr
		if code, out, errs := f.run("health"); code != exitOK || out != "healthy\n" {
			return fmt.Errorf("health command: %d %q %q", code, out, errs)
		}
		return nil
	})
	if code != exitOK {
		t.Errorf("serve exit %d, stderr %q", code, errb.String())
	}
	log := errb.String()
	if !strings.Contains(log, "serving on 127.0.0.1:") || !strings.Contains(log, "2 grants ([demo other])") ||
		!strings.Contains(log, "revision c0ffee42") || strings.Contains(log, testCanary) {
		t.Errorf("startup line: %q", log)
	}
}

// syncBuffer is a bytes.Buffer safe for serve's goroutine and the test to share.
type syncBuffer struct {
	mu sync.Mutex
	b  bytes.Buffer
}

func (s *syncBuffer) Write(p []byte) (int, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.b.Write(p)
}

func (s *syncBuffer) String() string {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.b.String()
}

func TestHealth(t *testing.T) {
	f := newFixture(t)

	f.vars["ADELE_LISTEN"] = ":" + port(t, freeAddr(t))
	code, out, errs := f.run("health")
	if code != exitFailure || out != "" || !strings.Contains(errs, "adeled: unhealthy: ") {
		t.Errorf("nothing listening: code %d, stdout %q, stderr %q", code, out, errs)
	}

	status := http.StatusOK
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/v1/health" {
			http.NotFound(w, r)
			return
		}
		w.WriteHeader(status)
	}))
	defer srv.Close()
	f.vars["ADELE_LISTEN"] = ":" + port(t, srv.Listener.Addr().String())
	code, out, _ = f.run("health")
	if code != exitOK || out != "healthy\n" {
		t.Errorf("200: code %d, stdout %q", code, out)
	}
	status = http.StatusInternalServerError
	code, _, errs = f.run("health")
	if code != exitFailure || !strings.Contains(errs, "unhealthy: HTTP 500") {
		t.Errorf("500: code %d, stderr %q", code, errs)
	}

	f.vars["ADELE_LISTEN"] = "no-port-here"
	code, _, errs = f.run("health")
	if code != exitFailure || !strings.Contains(errs, `ADELE_LISTEN "no-port-here"`) {
		t.Errorf("bad listen: code %d, stderr %q", code, errs)
	}
}

func port(t *testing.T, addr string) string {
	t.Helper()
	_, p, err := net.SplitHostPort(addr)
	if err != nil {
		t.Fatal(err)
	}
	return p
}
