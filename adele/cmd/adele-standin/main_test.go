package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"strings"
	"sync"
	"syscall"
	"testing"
	"time"

	"timelike/adele/internal/standin"
)

const testCanary = "tlcanary-0123456789abcdef0123456789abcdef"

type fixture struct {
	t    *testing.T
	dir  string
	vars map[string]string
}

func newFixture(t *testing.T) *fixture {
	t.Helper()
	dir := t.TempDir()
	f := &fixture{t: t, dir: dir, vars: map[string]string{
		"ADELE_CANARY_FILE": filepath.Join(dir, "canary"),
		"STANDIN_RECORD":    filepath.Join(dir, "boxes.json"),
		"STANDIN_LISTEN":    "127.0.0.1:0",
	}}
	f.write("canary", testCanary+"\n")
	return f
}

func (f *fixture) write(name, content string) {
	f.t.Helper()
	if err := os.WriteFile(filepath.Join(f.dir, name), []byte(content), 0o600); err != nil {
		f.t.Fatal(err)
	}
}

func (f *fixture) getenv(k string) string { return f.vars[k] }

func (f *fixture) run(args ...string) (int, string, string) {
	var out, errb bytes.Buffer
	code := run(args, f.getenv, &out, &errb, nil)
	return code, out.String(), errb.String()
}

func TestUsage(t *testing.T) {
	f := newFixture(t)
	for _, args := range [][]string{nil, {"frobnicate"}, {"help"}} {
		code, out, errs := f.run(args...)
		if code != exitUsage || out != "" || !strings.Contains(errs, "usage: adele-standin serve | list | health") ||
			!strings.Contains(errs, "stand-in") || !strings.Contains(errs, "not a provider") {
			t.Errorf("%v: code %d, stdout %q, stderr %q", args, code, out, errs)
		}
	}
}

func TestEnvDefaults(t *testing.T) {
	e := env(func(string) string { return "" })
	want := map[string]string{
		"ADELE_CANARY_FILE": "/run/adele-secret/canary", "STANDIN_RECORD": "/var/lib/standin/boxes.json",
		"STANDIN_LISTEN": ":8481", "OTHER": "",
	}
	for k, v := range want {
		if got := e.get(k); got != v {
			t.Errorf("default %s = %q, want %q", k, got, v)
		}
	}
}

func TestServeStartupFailures(t *testing.T) {
	busy, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	defer busy.Close()
	cases := []struct {
		name    string
		arrange func(f *fixture)
		code    int
		want    string
	}{
		{"canary missing", func(f *fixture) { f.vars["ADELE_CANARY_FILE"] = filepath.Join(f.dir, "none") }, exitUsage, "credential: "},
		{"canary invalid", func(f *fixture) { f.write("canary", "SECRET-VALUE-DO-NOT-ECHO") }, exitUsage,
			"is not tlcanary- and 32 lowercase hex characters"},
		{"record unreadable", func(f *fixture) {
			// A directory where the record file should be: reading it fails.
			if err := os.Mkdir(filepath.Join(f.dir, "boxes.json"), 0o700); err != nil {
				f.t.Fatal(err)
			}
		}, exitFailure, "adele-standin: record: "},
		{"record corrupt", func(f *fixture) { f.write("boxes.json", "{not json") }, exitFailure, "adele-standin: record: "},
		{"port in use", func(f *fixture) { f.vars["STANDIN_LISTEN"] = busy.Addr().String() }, exitFailure, "adele-standin: listen: "},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			f := newFixture(t)
			tc.arrange(f)
			code, out, errs := f.run("serve")
			if code != tc.code || out != "" || !strings.Contains(errs, tc.want) {
				t.Errorf("code %d (want %d), stdout %q, stderr %q (want %q)", code, tc.code, out, errs, tc.want)
			}
			if strings.Contains(errs, "SECRET-VALUE") || strings.Contains(errs, testCanary) {
				t.Errorf("stderr echoes the canary file's content: %q", errs)
			}
		})
	}
}

// serveUntilSignalled: see the same helper in cmd/adeled/serve_test.go for why a SIGINT to this
// process is safe here (own guard channel registered first; an answered request proves serve's
// NotifyContext is registered; no other test in this package uses signals or t.Parallel).
func serveUntilSignalled(t *testing.T, f *fixture, stderr *syncBuffer, probe func(addr string) error) int {
	t.Helper()
	guard := make(chan os.Signal, 1)
	signal.Notify(guard, os.Interrupt)
	defer signal.Stop(guard)

	ready := make(chan string, 1)
	done := make(chan int, 1)
	go func() { done <- run([]string{"serve"}, f.getenv, &bytes.Buffer{}, stderr, ready) }()
	var addr string
	select {
	case addr = <-ready:
	case code := <-done:
		t.Fatalf("serve returned %d before it was ready: %s", code, stderr.String())
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

// getRetry tolerates the moment between the listener's bind and srv.Serve.
func getRetry(url string, header string) (*http.Response, error) {
	c := &http.Client{Timeout: 5 * time.Second}
	var lastErr error
	for i := 0; i < 50; i++ {
		req, _ := http.NewRequest(http.MethodGet, url, nil)
		if header != "" {
			req.Header.Set("Authorization", header)
		}
		resp, err := c.Do(req)
		if err == nil {
			return resp, nil
		}
		lastErr = err
		time.Sleep(20 * time.Millisecond)
	}
	return nil, lastErr
}

func TestServeLifecycle(t *testing.T) {
	f := newFixture(t)
	store, err := standin.NewStore(f.vars["STANDIN_RECORD"])
	if err != nil {
		t.Fatal(err)
	}
	if err := store.Create(standin.Box{Name: "pre", CreatedAt: time.Now().UTC(), TTLSeconds: 3600, CostCents: 25}); err != nil {
		t.Fatal(err)
	}
	var errb syncBuffer
	code := serveUntilSignalled(t, f, &errb, func(addr string) error {
		resp, err := getRetry("http://"+addr+"/v1/boxes", "")
		if err != nil {
			return err
		}
		resp.Body.Close()
		if resp.StatusCode != http.StatusUnauthorized {
			return fmt.Errorf("without the canary: %d, want 401", resp.StatusCode)
		}
		resp, err = getRetry("http://"+addr+"/v1/boxes", "Bearer "+testCanary)
		if err != nil {
			return err
		}
		defer resp.Body.Close()
		var boxes []standin.Box
		if err := json.NewDecoder(resp.Body).Decode(&boxes); err != nil || resp.StatusCode != http.StatusOK ||
			len(boxes) != 1 || boxes[0].Name != "pre" {
			return fmt.Errorf("with the canary: %d %+v %v", resp.StatusCode, boxes, err)
		}
		g := newFixture(t)
		g.vars["STANDIN_LISTEN"] = addr
		if code, out, errs := g.run("health"); code != exitOK || out != "healthy\n" {
			return fmt.Errorf("health against the live server: %d %q %q", code, out, errs)
		}
		return nil
	})
	if code != exitOK {
		t.Errorf("serve exit %d, stderr %q", code, errb.String())
	}
	log := errb.String()
	if !strings.Contains(log, "STAND-IN, not a provider · serving on 127.0.0.1:") ||
		!strings.Contains(log, "1 boxes on record") || strings.Contains(log, testCanary) {
		t.Errorf("startup line: %q", log)
	}
}

// TestServeUnwritableRecordDir: a record directory the stand-in cannot write to. serve only reads
// the record at start (NewStore treats a missing file as empty), so it starts and every create
// then fails with 500. The brief expected exit 1 at start.
func TestServeUnwritableRecordDir(t *testing.T) {
	if os.Geteuid() == 0 {
		t.Skip("root ignores directory permissions")
	}
	f := newFixture(t)
	ro := filepath.Join(f.dir, "ro")
	if err := os.Mkdir(ro, 0o500); err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { os.Chmod(ro, 0o700) })
	f.vars["STANDIN_RECORD"] = filepath.Join(ro, "boxes.json")

	guard := make(chan os.Signal, 1)
	signal.Notify(guard, os.Interrupt)
	defer signal.Stop(guard)
	var errb syncBuffer
	ready := make(chan string, 1)
	done := make(chan int, 1)
	go func() { done <- run([]string{"serve"}, f.getenv, &bytes.Buffer{}, &errb, ready) }()
	select {
	case code := <-done:
		if code != exitFailure || !strings.Contains(errb.String(), "record") {
			t.Errorf("code %d, stderr %q", code, errb.String())
		}
		return
	case addr := <-ready:
		// It started. Stop it the same safe way as TestServeLifecycle, then report.
		if resp, err := getRetry("http://"+addr+"/v1/boxes", ""); err == nil {
			resp.Body.Close()
		}
		if err := syscall.Kill(os.Getpid(), syscall.SIGINT); err != nil {
			t.Fatalf("signal self: %v", err)
		}
		select {
		case <-done:
		case <-time.After(10 * time.Second):
			t.Fatal("serve did not stop on SIGINT")
		}
		t.Fatal("serve started with an unwritable record directory; expected exit 1 at start")
	case <-time.After(10 * time.Second):
		t.Fatal("serve neither failed nor became ready")
	}
}

func TestList(t *testing.T) {
	f := newFixture(t)
	code, out, errs := f.run("list")
	if code != exitOK || strings.TrimSpace(out) != "[]" || errs != "" {
		t.Errorf("empty: code %d, stdout %q, stderr %q", code, out, errs)
	}

	store, err := standin.NewStore(f.vars["STANDIN_RECORD"])
	if err != nil {
		t.Fatal(err)
	}
	at := time.Date(2026, 10, 2, 12, 0, 0, 0, time.UTC)
	for i, name := range []string{"box-a", "box-b"} {
		if err := store.Create(standin.Box{Name: name, CreatedAt: at.Add(time.Duration(i) * time.Minute),
			TTLSeconds: 3600, Ports: []int{8080}, CostCents: 25}); err != nil {
			t.Fatal(err)
		}
	}
	code, out, _ = f.run("list")
	var boxes []map[string]any
	if err := json.Unmarshal([]byte(out), &boxes); err != nil || code != exitOK {
		t.Fatalf("code %d, %v in %q", code, err, out)
	}
	if len(boxes) != 2 || boxes[0]["name"] != "box-a" || boxes[1]["name"] != "box-b" ||
		boxes[0]["ttl_seconds"] != 3600.0 || boxes[0]["cost_cents"] != 25.0 {
		t.Errorf("list: %v", boxes)
	}

	f.write("boxes.json", "{corrupt")
	code, _, errs = f.run("list")
	if code != exitFailure || !strings.Contains(errs, "adele-standin: record: ") {
		t.Errorf("corrupt: code %d, stderr %q", code, errs)
	}
}

func TestHealth(t *testing.T) {
	f := newFixture(t)
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	_, port, _ := net.SplitHostPort(ln.Addr().String())
	f.vars["STANDIN_LISTEN"] = ":" + port
	code, out, _ := f.run("health")
	if code != exitOK || out != "healthy\n" {
		t.Errorf("listening: code %d, stdout %q", code, out)
	}
	ln.Close()
	code, out, errs := f.run("health")
	if code != exitFailure || out != "" || !strings.Contains(errs, "adele-standin: unhealthy: ") {
		t.Errorf("nothing listening: code %d, stdout %q, stderr %q", code, out, errs)
	}
	f.vars["STANDIN_LISTEN"] = "no-port"
	code, _, errs = f.run("health")
	if code != exitFailure || !strings.Contains(errs, "STANDIN_LISTEN") {
		t.Errorf("bad listen: code %d, stderr %q", code, errs)
	}
}

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
