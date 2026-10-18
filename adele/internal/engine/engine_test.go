package engine

import (
	"bytes"
	"context"
	"encoding/binary"
	"encoding/json"
	"errors"
	"fmt"
	"net"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"
)

func frame(stream byte, s string) []byte {
	h := make([]byte, 8)
	h[0] = stream
	binary.BigEndian.PutUint32(h[4:], uint32(len(s)))
	return append(h, s...)
}

func TestDemuxSplitsTheDaemonsLogStream(t *testing.T) {
	var b bytes.Buffer
	b.Write(frame(1, `{"ok":`))
	b.Write(frame(2, "warning\n"))
	b.Write(frame(1, `true}`))
	o, e, err := Demux(&b)
	if err != nil || string(o) != `{"ok":true}` || string(e) != "warning\n" {
		t.Fatalf("Demux = %q %q %v", o, e, err)
	}
	cut := frame(1, "abc")[:9]
	if _, _, err := Demux(bytes.NewReader(cut)); err == nil {
		t.Fatal("a cut frame read as complete")
	}
}

func TestCountsTotal(t *testing.T) {
	if (Counts{Containers: 1, Networks: 2, Volumes: 3, Images: 4}).Total() != 10 {
		t.Fatal("Total")
	}
}

// A sandbox's error names its phase, and only its own bound passing is a timeout (lane 13s0a, item A).
func TestASandboxErrorNamesItsPhaseAndWhetherItsBoundPassed(t *testing.T) {
	c := New("/nonexistent/docker.sock")
	var took Phases
	_, _, _, err := c.Run(context.Background(), Sandbox{Image: "x", Timeout: time.Second, Took: &took})
	var se *SandboxError
	if !errors.As(err, &se) || se.Phase != "create" || se.TimedOut || se.ImageMissing() {
		t.Fatalf("no daemon: %#v", err)
	}
	if !strings.Contains(err.Error(), "failed at create after") {
		t.Errorf("text: %v", err)
	}
	gone := &SandboxError{Phase: "create", Err: &APIError{Status: 404, Message: "No such image: x"}}
	if !gone.ImageMissing() {
		t.Error("a 404 at create is a missing image")
	}
	slow := &SandboxError{Phase: "wait", Bound: 90 * time.Second, TimedOut: true}
	if slow.ImageMissing() || slow.Error() != "the resolution sandbox did not finish within 1m30s (the daemon was still at wait)" {
		t.Errorf("slow: %v", slow)
	}
	if m := (Phases{Create: 1500 * time.Millisecond}).Millis(); m["create"] != 1500 || len(m) != 4 {
		t.Errorf("millis: %v", m)
	}
}

// A request given up by its client is not the sandbox's own bound passing.
func TestAGivenUpRequestIsNotATimeout(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	_, _, _, err := New("/nonexistent/docker.sock").Run(ctx, Sandbox{Image: "x", Timeout: time.Minute})
	var se *SandboxError
	if !errors.As(err, &se) || se.TimedOut {
		t.Fatalf("%#v", err)
	}
}

// fakeDaemon serves h on a unix socket and returns a client for it.
func fakeDaemon(t *testing.T, h http.Handler) *Client {
	t.Helper()
	dir, err := os.MkdirTemp("", "eng")
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { os.RemoveAll(dir) })
	sock := filepath.Join(dir, "d.sock")
	ln, err := net.Listen("unix", sock)
	if err != nil {
		t.Fatal(err)
	}
	srv := &http.Server{Handler: h}
	go srv.Serve(ln) //nolint:errcheck // ends with Close
	t.Cleanup(func() { srv.Close() })
	return New(sock)
}

// A create the daemon finishes after the sandbox's bound is removed once it lands, and a sandbox carries none of
// the compose labels Adele's image has (lane 13s0b, item A).
func TestASandboxCreatedAfterItsBoundIsRemovedWhenItLands(t *testing.T) {
	defer func(r time.Duration) { LateRetry = r }(LateRetry)
	LateRetry = 20 * time.Millisecond
	var mu sync.Mutex
	made, removed := false, make(chan struct{})
	var labels map[string]string
	c := fakeDaemon(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch {
		case r.Method == http.MethodPost && r.URL.Path == "/containers/create":
			var spec struct{ Labels map[string]string }
			_ = json.NewDecoder(r.Body).Decode(&spec)
			time.Sleep(300 * time.Millisecond) // the daemon at create, past the bound
			mu.Lock()
			made, labels = true, spec.Labels
			mu.Unlock()
			w.WriteHeader(http.StatusCreated)
			_, _ = w.Write([]byte(`{"Id":"abc"}`))
		case r.Method == http.MethodDelete && r.URL.Path == "/containers/tl-sandbox-x":
			mu.Lock()
			defer mu.Unlock()
			if !made {
				http.Error(w, `{"message":"No such container"}`, http.StatusNotFound)
				return
			}
			w.WriteHeader(http.StatusNoContent)
			close(removed)
		default:
			http.Error(w, "unexpected "+r.Method+" "+r.URL.Path, http.StatusTeapot)
		}
	}))
	_, _, _, err := c.Run(context.Background(), Sandbox{Image: "x", Name: "tl-sandbox-x", Timeout: 100 * time.Millisecond})
	var se *SandboxError
	if !errors.As(err, &se) || !se.TimedOut || se.Phase != "create" {
		t.Fatalf("%#v", err)
	}
	select {
	case <-removed:
	case <-time.After(5 * time.Second):
		t.Fatal("the sandbox made after the bound was never removed")
	}
	mu.Lock()
	defer mu.Unlock()
	if labels[LabelSandbox] != "resolve" {
		t.Errorf("labels %v", labels)
	}
	for _, k := range composeImageLabels {
		if v, ok := labels[k]; !ok || v != "" {
			t.Errorf("label %s = %q, %v; want it overridden empty", k, v, ok)
		}
	}
}

// The sweep removes only sandboxes older than its age, found by the sandbox label.
func TestTheSweepRemovesOnlyLeftBehindSandboxes(t *testing.T) {
	var mu sync.Mutex
	var gone []string
	var filter string
	now := time.Now().Unix()
	c := fakeDaemon(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch {
		case r.Method == http.MethodGet && r.URL.Path == "/containers/json":
			mu.Lock()
			filter = r.URL.Query().Get("filters")
			mu.Unlock()
			fmt.Fprintf(w, `[{"Id":"old","Created":%d},{"Id":"new","Created":%d}]`, now-3600, now-5)
		case r.Method == http.MethodDelete:
			mu.Lock()
			gone = append(gone, strings.TrimPrefix(r.URL.Path, "/containers/"))
			mu.Unlock()
			w.WriteHeader(http.StatusNoContent)
		default:
			http.Error(w, "unexpected", http.StatusTeapot)
		}
	}))
	n, err := c.SweepSandboxes(context.Background(), 15*time.Minute)
	mu.Lock()
	defer mu.Unlock()
	if err != nil || n != 1 || len(gone) != 1 || gone[0] != "old" {
		t.Fatalf("removed %d %v, %v", n, gone, err)
	}
	if !strings.Contains(filter, LabelSandbox+"=resolve") {
		t.Errorf("filter %q", filter)
	}
}
