package engine

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"strings"
	"sync"
	"testing"
	"time"
)

// upgrade answers r by hijacking the connection, as the daemon does for attach and exec start, and writes frames.
func upgrade(t *testing.T, w http.ResponseWriter, frames ...[]byte) {
	t.Helper()
	conn, buf, err := w.(http.Hijacker).Hijack()
	if err != nil {
		t.Error(err)
		return
	}
	defer conn.Close()
	_, _ = buf.WriteString("HTTP/1.1 101 UPGRADED\r\nContent-Type: application/vnd.docker.raw-stream\r\nConnection: Upgrade\r\nUpgrade: tcp\r\n\r\n")
	for _, f := range frames {
		_, _ = buf.Write(f)
	}
	_ = buf.Flush()
}

func TestExecPassesTheExitCodeAndKeepsTheLastOfTheOutput(t *testing.T) {
	var spec map[string]any
	c := fakeDaemon(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch {
		case r.Method == http.MethodPost && r.URL.Path == "/containers/box/exec":
			_ = json.NewDecoder(r.Body).Decode(&spec)
			w.WriteHeader(http.StatusCreated)
			_, _ = w.Write([]byte(`{"Id":"e1"}`))
		case r.Method == http.MethodPost && r.URL.Path == "/exec/e1/start":
			upgrade(t, w, frame(1, "0123456789"), frame(2, "oops\n"))
		case r.Method == http.MethodGet && r.URL.Path == "/exec/e1/json":
			_, _ = w.Write([]byte(`{"ExitCode":7,"Running":false}`))
		default:
			http.Error(w, "unexpected "+r.Method+" "+r.URL.Path, http.StatusTeapot)
		}
	}))
	res, err := c.Exec(context.Background(), "box", ExecSpec{Cmd: []string{"sh", "-c", "x"}, User: "dev", WorkingDir: "/w",
		Env: []string{"A=1"}, MaxOutput: 4})
	if err != nil || res.ExitCode != 7 || string(res.Stdout) != "6789" || res.Dropped[0] != 6 || string(res.Stderr) != "ops\n" {
		t.Fatalf("Exec = %+v, %v", res, err)
	}
	if spec["Privileged"] != false || spec["Tty"] != false || spec["User"] != "dev" || spec["WorkingDir"] != "/w" {
		t.Errorf("exec spec %v", spec)
	}
}

func TestAnExecPastItsBoundIsATimeoutNotAnError(t *testing.T) {
	c := fakeDaemon(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/containers/box/exec":
			w.WriteHeader(http.StatusCreated)
			_, _ = w.Write([]byte(`{"Id":"e1"}`))
		case "/exec/e1/start":
			conn, buf, _ := w.(http.Hijacker).Hijack()
			_, _ = buf.WriteString("HTTP/1.1 101 UPGRADED\r\nConnection: Upgrade\r\nUpgrade: tcp\r\n\r\n")
			_, _ = buf.Write(frame(1, "started\n"))
			_ = buf.Flush()
			time.Sleep(time.Second) // still running
			conn.Close()
		default:
			http.Error(w, "unexpected", http.StatusTeapot)
		}
	}))
	res, err := c.Exec(context.Background(), "box", ExecSpec{Cmd: []string{"sleep", "9"}, Timeout: 100 * time.Millisecond})
	if err != nil || !res.TimedOut || string(res.Stdout) != "started\n" {
		t.Fatalf("Exec = %+v, %v", res, err)
	}
}

// The context sandbox's stdout reaches the writer from the attached stream, and it writes nothing to the log.
func TestRunStreamCopiesStdoutFromTheAttachedStream(t *testing.T) {
	var mu sync.Mutex
	var order []string
	var logType string
	c := fakeDaemon(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		order = append(order, r.Method+" "+r.URL.Path)
		mu.Unlock()
		switch {
		case r.URL.Path == "/containers/create":
			var spec struct {
				HostConfig struct {
					LogConfig struct{ Type string }
				}
			}
			_ = json.NewDecoder(r.Body).Decode(&spec)
			logType = spec.HostConfig.LogConfig.Type
			w.WriteHeader(http.StatusCreated)
			_, _ = w.Write([]byte(`{"Id":"s1"}`))
		case r.URL.Path == "/containers/s1/attach":
			upgrade(t, w, frame(1, "tar-bytes-"), frame(2, "summary"), frame(1, "more"))
		case r.URL.Path == "/containers/s1/start":
			w.WriteHeader(http.StatusNoContent)
		case r.URL.Path == "/containers/s1/wait":
			_, _ = w.Write([]byte(`{"StatusCode":0}`))
		case r.Method == http.MethodDelete && r.URL.Path == "/containers/s1":
			w.WriteHeader(http.StatusNoContent)
		default:
			http.Error(w, "unexpected "+r.URL.Path, http.StatusTeapot)
		}
	}))
	var out bytes.Buffer
	stderr, exit, err := c.RunStream(context.Background(), Sandbox{Image: "adele", Timeout: 5 * time.Second}, &out)
	if err != nil || exit != 0 || out.String() != "tar-bytes-more" || string(stderr) != "summary" {
		t.Fatalf("RunStream = %q %q %d %v", out.String(), stderr, exit, err)
	}
	if logType != "none" {
		t.Errorf("log driver %q, want none", logType)
	}
	mu.Lock()
	defer mu.Unlock()
	if strings.Join(order, ",") != "POST /containers/create,POST /containers/s1/attach,POST /containers/s1/start,POST /containers/s1/wait,DELETE /containers/s1" {
		t.Errorf("order %v: attach must come before start, and the sandbox is removed", order)
	}
}

func buildDaemon(t *testing.T, lines ...string) (*Client, *http.Request, *[]byte) {
	t.Helper()
	var got http.Request
	body := new([]byte)
	c := fakeDaemon(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/build" {
			http.Error(w, "unexpected", http.StatusTeapot)
			return
		}
		got = *r
		*body, _ = io.ReadAll(r.Body)
		for _, l := range lines {
			_, _ = io.WriteString(w, l+"\r\n")
			w.(http.Flusher).Flush()
		}
	}))
	return c, &got, body
}

func TestABuildStreamsTheArchiveUnopenedAndReturnsTheImage(t *testing.T) {
	c, req, body := buildDaemon(t, `{"stream":"Step 1/2 : FROM base\n"}`, `{"stream":" ---> abc\n"}`,
		`{"stream":"Step 2/2 : RUN true\n"}`, `{"aux":{"ID":"sha256:feed"}}`, `{"stream":"Successfully built feed\n"}`)
	id, err := c.Build(context.Background(), BuildSpec{Tag: "tl-x-svc:0123", Dockerfile: "Dockerfile", Target: "dev",
		Args: map[string]string{"BASE": "b"}, Labels: map[string]string{LabelEnv: "tl-x"}}, strings.NewReader("TARBYTES"))
	if err != nil || id != "sha256:feed" {
		t.Fatalf("Build = %q, %v", id, err)
	}
	q := req.URL.Query()
	if q.Get("version") != "1" || q.Get("pull") != "0" || q.Get("networkmode") != "default" || q.Get("t") != "tl-x-svc:0123" ||
		q.Get("target") != "dev" || !strings.Contains(q.Get("labels"), LabelEnv) {
		t.Errorf("query %v", q)
	}
	if string(*body) != "TARBYTES" || req.Header.Get("Content-Type") != "application/x-tar" {
		t.Errorf("body %q", *body)
	}
}

func TestAFailedStepIsNamedWithTheLastLines(t *testing.T) {
	c, _, _ := buildDaemon(t, `{"stream":"Step 1/2 : FROM base\n"}`, `{"stream":"Step 2/2 : RUN false\n"}`,
		`{"stream":"some output\n"}`, `{"errorDetail":{"message":"The command '/bin/sh -c false' returned a non-zero code: 1"},"error":"x"}`)
	_, err := c.Build(context.Background(), BuildSpec{Tag: "t"}, strings.NewReader(""))
	var be *BuildError
	if !errors.As(err, &be) || be.Kind != "step" || be.Step != "Step 2/2 : RUN false" || !strings.Contains(be.Msg, "non-zero code: 1") ||
		be.Last[len(be.Last)-1] != "some output" {
		t.Fatalf("%#v", err)
	}
}

// The classic builder pulls a missing base whatever pull says; its first pull message stops the build (R15).
func TestTheFirstPullStopsTheBuild(t *testing.T) {
	c, _, _ := buildDaemon(t, `{"stream":"Step 1/1 : FROM gone:1\n"}`, `{"status":"Pulling from library/gone","id":"1"}`,
		`{"aux":{"ID":"sha256:never"}}`)
	_, err := c.Build(context.Background(), BuildSpec{Tag: "t"}, strings.NewReader(""))
	var be *BuildError
	if !errors.As(err, &be) || be.Kind != "pull" || be.Image != "library/gone" || !strings.Contains(err.Error(), "a build pulls nothing") {
		t.Fatalf("%#v", err)
	}
}

func TestABuildPastItsBoundNamesItsStep(t *testing.T) {
	c := fakeDaemon(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = io.ReadAll(r.Body)
		_, _ = io.WriteString(w, `{"stream":"Step 1/1 : RUN sleep 9\n"}`+"\r\n")
		w.(http.Flusher).Flush()
		<-r.Context().Done()
	}))
	_, err := c.Build(context.Background(), BuildSpec{Tag: "t", Timeout: 200 * time.Millisecond}, strings.NewReader(""))
	var be *BuildError
	if !errors.As(err, &be) || be.Kind != "timeout" || be.Step != "Step 1/1 : RUN sleep 9" {
		t.Fatalf("%#v", err)
	}
}

func TestTheRequesterIsTheAgentWithThePeersAddressOnTheRequestNetwork(t *testing.T) {
	agents := []AgentContainer{
		{ID: "other", Addresses: map[string]string{"timelike_default": "172.18.0.5"}},
		{ID: "agent", Addresses: map[string]string{"timelike_default": "172.18.0.2", "timelike_adele-request": "172.19.0.3"}},
	}
	if id, ok := RequesterOf(agents, "172.19.0.3"); !ok || id != "agent" {
		t.Fatalf("RequesterOf = %q %v", id, ok)
	}
	if _, ok := RequesterOf(agents, "172.18.0.5"); ok {
		t.Fatal("an address on another network named a requester")
	}
	if _, ok := RequesterOf(agents, ""); ok {
		t.Fatal("no address named a requester")
	}
}

func TestAgentsAreListedByTheAgentsLaunchLabel(t *testing.T) {
	var filter string
	c := fakeDaemon(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		filter = r.URL.Query().Get("filters")
		_, _ = w.Write([]byte(`[{"Id":"a1","NetworkSettings":{"Networks":{"timelike_adele-request":{"IPAddress":"10.0.0.2"}}}}]`))
	}))
	as, err := c.Agents(context.Background())
	if err != nil || len(as) != 1 || as[0].Addresses["timelike_adele-request"] != "10.0.0.2" || !strings.Contains(filter, LabelAgent) {
		t.Fatalf("Agents = %+v, %v (filter %q)", as, err, filter)
	}
}

// Down removes an environment's built images too, after its containers, by its label only.
func TestDownRemovesTheImagesAnEnvironmentBuilt(t *testing.T) {
	var mu sync.Mutex
	images := []string{"sha256:i1"}
	var deleted []string
	c := fakeDaemon(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		defer mu.Unlock()
		switch {
		case r.Method == http.MethodGet && r.URL.Path == "/images/json":
			if !strings.Contains(r.URL.Query().Get("filters"), LabelEnv+"=tl-x") {
				http.Error(w, "unfiltered", http.StatusTeapot)
				return
			}
			out := []map[string]string{}
			for _, i := range images {
				out = append(out, map[string]string{"Id": i})
			}
			_ = json.NewEncoder(w).Encode(out)
		case r.Method == http.MethodDelete && strings.HasPrefix(r.URL.Path, "/images/"):
			deleted = append(deleted, strings.TrimPrefix(r.URL.Path, "/images/"))
			images = nil
			_, _ = w.Write([]byte(`[]`))
		case r.Method == http.MethodGet && r.URL.Path == "/volumes":
			_, _ = w.Write([]byte(`{"Volumes":[]}`))
		case r.Method == http.MethodGet:
			_, _ = w.Write([]byte(`[]`))
		default:
			http.Error(w, fmt.Sprintf("unexpected %s %s", r.Method, r.URL.Path), http.StatusTeapot)
		}
	}))
	removed, left, err := c.Down(context.Background(), "tl-x")
	if err != nil || removed.Images != 1 || left.Total() != 0 || len(deleted) != 1 || deleted[0] != "sha256:i1" {
		t.Fatalf("Down = %+v %+v %v (deleted %v)", removed, left, err, deleted)
	}
}
