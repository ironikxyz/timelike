package engine

import (
	"bytes"
	"context"
	"encoding/binary"
	"errors"
	"strings"
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
	if (Counts{1, 2, 3}).Total() != 6 {
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
