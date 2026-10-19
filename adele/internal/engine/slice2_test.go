package engine

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"strings"
	"sync"
	"testing"
	"time"
)

// recorder is a fake daemon that records each call and answers from a table by "METHOD path".
type recorder struct {
	mu    sync.Mutex
	calls []string
	body  map[string]string
}

func (rec *recorder) serve(t *testing.T, answers map[string]func(w http.ResponseWriter)) *Client {
	rec.body = map[string]string{}
	return fakeDaemon(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		key := r.Method + " " + r.URL.Path
		raw, _ := io.ReadAll(r.Body)
		rec.mu.Lock()
		rec.calls = append(rec.calls, key+"?"+r.URL.RawQuery)
		rec.body[key] = string(raw)
		rec.mu.Unlock()
		if a, ok := answers[key]; ok {
			a(w)
			return
		}
		http.Error(w, "unexpected "+key, http.StatusTeapot)
	}))
}

func status(code int, body string) func(w http.ResponseWriter) {
	return func(w http.ResponseWriter) {
		w.WriteHeader(code)
		_, _ = io.WriteString(w, body)
	}
}

func TestSnapshotVolumesAreCreatedLabelledAndRemoved(t *testing.T) {
	var rec recorder
	c := rec.serve(t, map[string]func(http.ResponseWriter){
		"POST /volumes/create":           status(http.StatusCreated, `{}`),
		"DELETE /volumes/tl-a-snap-1":    status(http.StatusNoContent, ``),
		"GET /volumes/tl-a-snap-1":       status(http.StatusOK, `{"Name":"tl-a-snap-1","Labels":{"`+LabelSnapshot+`":"s-1"}}`),
		"GET /volumes/tl-a-snap-gone":    status(http.StatusNotFound, `{"message":"no such volume"}`),
		"DELETE /volumes/tl-a-snap-gone": status(http.StatusNotFound, `{}`),
	})
	ctx := context.Background()
	if err := c.CreateVolume(ctx, "tl-a-snap-1", map[string]string{LabelEnv: "tl-a", LabelSnapshot: "s-1"},
		map[string]string{"type": "tmpfs", "device": "tmpfs", "o": "size=1048576"}); err != nil {
		t.Fatal(err)
	}
	var spec struct {
		Name       string
		Driver     string
		DriverOpts map[string]string
		Labels     map[string]string
	}
	if err := json.Unmarshal([]byte(rec.body["POST /volumes/create"]), &spec); err != nil {
		t.Fatal(err)
	}
	if spec.Name != "tl-a-snap-1" || spec.Driver != "local" || spec.DriverOpts["type"] != "tmpfs" ||
		spec.Labels[LabelEnv] != "tl-a" {
		t.Fatalf("create %+v", spec)
	}
	labels, ok, err := c.VolumeExists(ctx, "tl-a-snap-1")
	if err != nil || !ok || labels[LabelSnapshot] != "s-1" {
		t.Fatalf("VolumeExists = %v %v %v", labels, ok, err)
	}
	if _, ok, err := c.VolumeExists(ctx, "tl-a-snap-gone"); err != nil || ok {
		t.Fatalf("a gone volume exists: %v %v", ok, err)
	}
	if err := c.RemoveVolume(ctx, "tl-a-snap-1"); err != nil {
		t.Fatal(err)
	}
	if err := c.RemoveVolume(ctx, "tl-a-snap-gone"); err != nil {
		t.Fatalf("removing a gone volume: %v", err)
	}
}

func TestPauseUnpauseStopStartAndState(t *testing.T) {
	var rec recorder
	c := rec.serve(t, map[string]func(http.ResponseWriter){
		"POST /containers/c1/pause":   status(http.StatusNoContent, ``),
		"POST /containers/c1/unpause": status(http.StatusConflict, `{"message":"not paused"}`),
		"POST /containers/c1/stop":    status(http.StatusNotModified, ``),
		"POST /containers/c1/start":   status(http.StatusNoContent, ``),
		"GET /containers/c1/json":     status(http.StatusOK, `{"State":{"Status":"paused"}}`),
		"GET /containers/c2/json":     status(http.StatusNotFound, `{}`),
		"POST /containers/c3/pause":   status(http.StatusInternalServerError, `{"message":"freezer"}`),
	})
	ctx := context.Background()
	for name, err := range map[string]error{"pause": c.Pause(ctx, "c1"), "unpause": c.Unpause(ctx, "c1"),
		"stop": c.Stop(ctx, "c1", 10*time.Second), "start": c.Start(ctx, "c1")} {
		if err != nil {
			t.Errorf("%s: %v", name, err)
		}
	}
	if err := c.Pause(ctx, "c3"); err == nil || !strings.Contains(err.Error(), "freezer") {
		t.Errorf("a failed pause: %v", err)
	}
	if s, err := c.State(ctx, "c1"); err != nil || s != "paused" {
		t.Errorf("State = %q, %v", s, err)
	}
	if s, err := c.State(ctx, "c2"); err != nil || s != "removed" {
		t.Errorf("a gone container's State = %q, %v", s, err)
	}
	rec.mu.Lock()
	defer rec.mu.Unlock()
	if !strings.Contains(strings.Join(rec.calls, " "), "/containers/c1/stop?t=10") {
		t.Errorf("calls %v", rec.calls)
	}
}

// Snapshot volumes are counted apart from an environment's own volumes, in Count and in Down.
func TestSnapshotsAreCountedApart(t *testing.T) {
	vols := `{"Volumes":[{"Name":"tl-a_db","Labels":{"` + LabelEnv + `":"tl-a"}},` +
		`{"Name":"tl-a-snap-1","Labels":{"` + LabelEnv + `":"tl-a","` + LabelSnapshot + `":"s-1"}}]}`
	var rec recorder
	removed := false
	c := rec.serve(t, map[string]func(http.ResponseWriter){
		"GET /containers/json": status(http.StatusOK, `[]`),
		"GET /networks":        status(http.StatusOK, `[]`),
		"GET /images/json":     status(http.StatusOK, `[]`),
		"GET /volumes": func(w http.ResponseWriter) {
			if removed {
				_, _ = io.WriteString(w, `{"Volumes":[]}`)
				return
			}
			_, _ = io.WriteString(w, vols)
		},
		"DELETE /volumes/tl-a_db": status(http.StatusNoContent, ``),
		"DELETE /volumes/tl-a-snap-1": func(w http.ResponseWriter) {
			removed = true
			w.WriteHeader(http.StatusNoContent)
		},
	})
	n, err := c.Count(context.Background(), "tl-a")
	if err != nil || n.Volumes != 1 || n.Snapshots != 1 || n.Total() != 2 {
		t.Fatalf("Count = %+v, %v", n, err)
	}
	gone, left, err := c.Down(context.Background(), "tl-a")
	if err != nil || gone.Volumes != 1 || gone.Snapshots != 1 || left.Total() != 0 {
		t.Fatalf("Down = %+v left %+v, %v", gone, left, err)
	}
}

// The volume helper is a sandbox with named capabilities back and its own kind.
func TestASandboxGetsItsCapabilitiesAndKind(t *testing.T) {
	var rec recorder
	c := rec.serve(t, map[string]func(http.ResponseWriter){
		"POST /containers/create":   status(http.StatusCreated, `{"Id":"h1"}`),
		"POST /containers/h1/start": status(http.StatusNoContent, ``),
		"POST /containers/h1/wait":  status(http.StatusOK, `{"StatusCode":0}`),
		"GET /containers/h1/logs":   status(http.StatusOK, ``),
		"DELETE /containers/h1":     status(http.StatusNoContent, ``),
	})
	_, _, code, err := c.Run(context.Background(), Sandbox{Image: "adele", User: "0:0", CapAdd: HelperCaps,
		Kind: SandboxVolume, Binds: []string{"tl-a_db:/src:ro"}})
	if err != nil || code != 0 {
		t.Fatalf("Run = %d, %v", code, err)
	}
	var spec struct {
		User       string
		Labels     map[string]string
		HostConfig struct {
			CapDrop, CapAdd []string
			NetworkMode     string
		}
	}
	rec.mu.Lock()
	raw := rec.body["POST /containers/create"]
	rec.mu.Unlock()
	if err := json.Unmarshal([]byte(raw), &spec); err != nil {
		t.Fatal(err)
	}
	if spec.User != "0:0" || spec.Labels[LabelSandbox] != SandboxVolume || spec.HostConfig.NetworkMode != "none" ||
		strings.Join(spec.HostConfig.CapDrop, ",") != "ALL" || len(spec.HostConfig.CapAdd) != 5 {
		t.Fatalf("spec %+v", spec)
	}
}
