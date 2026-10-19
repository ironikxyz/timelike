package broker

import (
	"bytes"
	"context"
	"encoding/binary"
	"encoding/json"
	"io"
	"net"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"testing"
	"time"

	"timelike/adele/internal/engine"
	"timelike/adele/internal/grants"
	"timelike/adele/internal/ledger"
)

// A small stateful daemon for slice 2's order of acts (014 plan R26-R30): containers with mounts and states,
// volumes with labels, and the volume helper's runs answered from a script by operation. Every call is recorded,
// so a test asserts what happened before what. The daemon's own answers are the lane's (cross-stack P005).

type fakeContainer struct {
	id, service, state string
	mounts             []engine.Mount
}

type fakeDaemon struct {
	mu      sync.Mutex
	env     string
	cs      []*fakeContainer
	vols    map[string]map[string]string // name → labels
	events  []string
	helper  map[string]func(cmd []string) (exit int, stdout, stderr string)
	runs    map[string][]string // sandbox id → cmd, until it is removed
	made    int
	pauseOK bool
}

func (d *fakeDaemon) event(s string) {
	d.events = append(d.events, s)
}

func matches(labels map[string]string, filters []string) bool {
	for _, f := range filters {
		k, v, hasV := strings.Cut(f, "=")
		got, ok := labels[k]
		if !ok || hasV && got != v {
			return false
		}
	}
	return true
}

func (d *fakeDaemon) labelsOf(c *fakeContainer) map[string]string {
	return map[string]string{engine.LabelEnv: d.env, engine.ComposeService: c.service, engine.LabelRequester: "agent-1"}
}

func (d *fakeDaemon) find(id string) *fakeContainer {
	for _, c := range d.cs {
		if c.id == id {
			return c
		}
	}
	return nil
}

func frame(stream byte, s string) []byte {
	if s == "" {
		return nil
	}
	h := make([]byte, 8)
	h[0] = stream
	binary.BigEndian.PutUint32(h[4:], uint32(len(s)))
	return append(h, s...)
}

func (d *fakeDaemon) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	d.mu.Lock()
	defer d.mu.Unlock()
	var filters struct {
		Label []string `json:"label"`
	}
	_ = json.Unmarshal([]byte(r.URL.Query().Get("filters")), &filters)
	path := r.URL.Path
	write := func(code int, v any) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(code)
		_ = json.NewEncoder(w).Encode(v)
	}
	parts := strings.Split(strings.Trim(path, "/"), "/")
	switch {
	case r.Method == http.MethodGet && path == "/containers/json":
		out := []map[string]any{}
		for _, c := range d.cs {
			if matches(d.labelsOf(c), filters.Label) {
				out = append(out, map[string]any{"Id": c.id, "Labels": d.labelsOf(c), "State": c.state})
			}
		}
		for id := range d.runs {
			if l := map[string]string{engine.LabelSandbox: engine.SandboxVolume}; matches(l, filters.Label) {
				out = append(out, map[string]any{"Id": id, "Labels": l, "State": "running"})
			}
		}
		write(http.StatusOK, out)
	case r.Method == http.MethodGet && len(parts) == 3 && parts[0] == "containers" && parts[2] == "json":
		c := d.find(parts[1])
		if c == nil {
			write(http.StatusNotFound, map[string]string{"message": "no such container"})
			return
		}
		write(http.StatusOK, map[string]any{"State": map[string]any{"Status": c.state}, "Mounts": c.mounts})
	case r.Method == http.MethodPost && path == "/containers/create":
		var spec struct{ Cmd []string }
		_ = json.NewDecoder(r.Body).Decode(&spec)
		d.made++
		id := "h" + strconv.Itoa(d.made)
		d.runs[id] = spec.Cmd
		d.event("helper " + spec.Cmd[1])
		write(http.StatusCreated, map[string]string{"Id": id})
	case r.Method == http.MethodPost && len(parts) == 3 && parts[0] == "containers" && d.runs[parts[1]] != nil:
		switch parts[2] {
		case "start":
			w.WriteHeader(http.StatusNoContent)
		case "wait":
			exit, _, _ := d.helper[d.runs[parts[1]][1]](d.runs[parts[1]])
			write(http.StatusOK, map[string]int{"StatusCode": exit})
		}
	case r.Method == http.MethodGet && len(parts) == 3 && parts[2] == "logs":
		_, out, errs := d.helper[d.runs[parts[1]][1]](d.runs[parts[1]])
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write(append(frame(1, out), frame(2, errs)...))
	case r.Method == http.MethodDelete && len(parts) == 2 && parts[0] == "containers":
		delete(d.runs, parts[1]) // a helper's run is removed once its answer is read, as engine.Run does
		w.WriteHeader(http.StatusNoContent)
	case r.Method == http.MethodPost && len(parts) == 3 && parts[0] == "containers":
		c := d.find(parts[1])
		if c == nil {
			write(http.StatusNotFound, map[string]string{"message": "no such container"})
			return
		}
		d.event(parts[2] + " " + c.service)
		switch parts[2] {
		case "pause":
			if d.pauseOK {
				c.state = "paused"
			}
		case "unpause", "start":
			c.state = "running"
		case "stop":
			c.state = "exited"
		}
		w.WriteHeader(http.StatusNoContent)
	case r.Method == http.MethodGet && path == "/volumes":
		out := []map[string]any{}
		for n, l := range d.vols {
			if matches(l, filters.Label) {
				out = append(out, map[string]any{"Name": n, "Labels": l})
			}
		}
		write(http.StatusOK, map[string]any{"Volumes": out})
	case r.Method == http.MethodPost && path == "/volumes/create":
		var spec struct {
			Name   string
			Labels map[string]string
		}
		_ = json.NewDecoder(r.Body).Decode(&spec)
		d.vols[spec.Name] = spec.Labels
		d.event("create " + spec.Name)
		write(http.StatusCreated, map[string]string{})
	case len(parts) == 2 && parts[0] == "volumes":
		name, _ := url.PathUnescape(parts[1])
		l, ok := d.vols[name]
		switch {
		case !ok:
			write(http.StatusNotFound, map[string]string{"message": "no such volume"})
		case r.Method == http.MethodDelete:
			delete(d.vols, name)
			d.event("remove " + name)
			w.WriteHeader(http.StatusNoContent)
		default:
			write(http.StatusOK, map[string]any{"Name": name, "Labels": l})
		}
	default:
		_, _ = io.Copy(io.Discard, r.Body)
		write(http.StatusTeapot, map[string]string{"message": "unexpected " + r.Method + " " + path})
	}
}

const snapEnv = "tl-p-1"

// snapFixture is a broker with one live environment, snapEnv, whose db service mounts its volume db-data.
func snapFixture(t *testing.T, grantExtra string) (*fixture, *fakeDaemon) {
	t.Helper()
	f := newFixture(t, envGrants+grantExtra)
	d := &fakeDaemon{env: snapEnv, pauseOK: true, runs: map[string][]string{},
		vols: map[string]map[string]string{snapEnv + "_db-data": {engine.LabelEnv: snapEnv, composeVolume: "db-data"}},
		cs: []*fakeContainer{{id: "c-db", service: "db", state: "running",
			mounts: []engine.Mount{{Type: "volume", Name: snapEnv + "_db-data", Destination: "/data"}}},
			{id: "c-web", service: "web", state: "running"}},
		helper: map[string]func([]string) (int, string, string){
			"measure": func([]string) (int, string, string) { return 0, `{"bytes":4096,"files":3,"sockets":0}`, "" },
			"copy": func([]string) (int, string, string) {
				return 0, `{"digest":"sha256:aa","copy_digest":"sha256:aa","bytes":4096,"files":3,"sockets":0}`, ""
			},
			"digest": func([]string) (int, string, string) { return 0, `{"digest":"sha256:aa","bytes":4096,"files":3}`, "" },
			"restore": func([]string) (int, string, string) {
				return 0, `{"digest":"sha256:aa","copy_digest":"sha256:aa","bytes":4096,"files":3}`, ""
			},
		}}
	dir, err := os.MkdirTemp("", "snap")
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { os.RemoveAll(dir) })
	sock := filepath.Join(dir, "d.sock")
	ln, err := net.Listen("unix", sock)
	if err != nil {
		t.Fatal(err)
	}
	srv := &http.Server{Handler: d}
	go srv.Serve(ln) //nolint:errcheck // ends with Close
	t.Cleanup(func() { srv.Close() })
	f.b.Envs = &Envs{Engine: engine.New(sock), Workspace: "/w", SandboxImage: "timelike-adele:local"}
	expires := fixedNow.Add(time.Hour)
	zero := int64(0)
	if _, err := f.led.Performed(ledger.Row{At: fixedNow, Grant: "env", Session: "s1", Capability: grants.CapDockerCompose,
		Action: "up", Resource: snapEnv, CostCents: &zero, ExpiresAt: &expires, Undo: `{}`}); err != nil {
		t.Fatal(err)
	}
	return f, d
}

func snapReq(action string, p Params) Request {
	p.Name = snapEnv
	return Request{Session: "s1", Capability: grants.CapDockerCompose, Action: action, Params: p}
}

func (d *fakeDaemon) log() string {
	d.mu.Lock()
	defer d.mu.Unlock()
	return strings.Join(d.events, " | ")
}

func rowsOf(t *testing.T, f *fixture, action string) []ledger.Row {
	var out []ledger.Row
	for _, r := range f.rows(t) {
		if r.Action == action {
			out = append(out, r)
		}
	}
	return out
}

func TestASnapshotPausesItsUsersCopiesThenUnpausesAndRecords(t *testing.T) {
	f, d := snapFixture(t, "")
	out := f.handle(snapReq("snapshot", Params{Volume: "db-data", Note: "before the migration"}))
	if out.Status != http.StatusOK {
		t.Fatalf("snapshot: %d %v", out.Status, out.Body)
	}
	snap := out.Body["snapshot"].(map[string]any)
	id := snap["id"].(string)
	if !snapshotRe.MatchString(id) || snap["digest"] != "sha256:aa" || snap["bytes"] != int64(4096) || snap["volume"] != "db-data" {
		t.Fatalf("snapshot %v", snap)
	}
	// Measured unpaused, then paused, created, copied, unpaused: in that order, and web (no mount) untouched.
	want := "helper measure | pause db | create " + snapshotVolume(snapEnv, id) + " | helper copy | unpause db"
	if got := d.log(); got != want {
		t.Fatalf("events\n got %s\nwant %s", got, want)
	}
	if paused := out.Body["paused"].([]map[string]string); len(paused) != 1 || paused[0]["service"] != "db" {
		t.Fatalf("paused %v", out.Body["paused"])
	}
	labels := d.vols[snapshotVolume(snapEnv, id)]
	if labels[engine.LabelEnv] != snapEnv || labels[engine.LabelSnapshot] != id || labels[engine.LabelSnapshotOf] != snapEnv+"_db-data" ||
		labels[engine.LabelSession] != "s1" || labels[engine.LabelGrant] != "env" || labels[engine.LabelRequester] != "agent-1" {
		t.Fatalf("labels %v", labels)
	}
	// The pause was recorded, and ended once the unpause read back; the snapshot row carries its record.
	pauses, unpauses := rowsOf(t, f, ledger.ActionPause), rowsOf(t, f, ledger.ActionUnpause)
	if len(pauses) != 1 || len(unpauses) != 1 || unpauses[0].Ref == nil || *unpauses[0].Ref != pauses[0].ID || pauses[0].ID > unpauses[0].ID {
		t.Fatalf("pause %+v unpause %+v", pauses, unpauses)
	}
	snaps := rowsOf(t, f, ledger.ActionSnapshot)
	if len(snaps) != 1 || snaps[0].Resource != snapEnv+"/"+id || snaps[0].ExpiresAt != nil {
		t.Fatalf("snapshot rows %+v", snaps)
	}
	if rec, ok := recordOf(snaps[0]); !ok || rec.Digest != "sha256:aa" || rec.Note != "before the migration" || rec.Store != "volume" {
		t.Fatalf("record %+v", rec)
	}
	if n, _ := f.led.LiveOf("env", grants.CapDockerCompose); n != 1 {
		t.Fatalf("live environments %d: a snapshot or a pause counted as one", n)
	}
	// Listed, with the cap used.
	list := f.handle(snapReq("snapshots", Params{}))
	if list.Status != http.StatusOK || len(list.Body["snapshots"].([]map[string]any)) != 1 ||
		list.Body["cap"].(map[string]any)["used"] != int64(4096) {
		t.Fatalf("snapshots: %d %v", list.Status, list.Body)
	}
}

func TestASnapshotPastTheCapIsRefusedBeforeAnythingIsWritten(t *testing.T) {
	f, d := snapFixture(t, "")
	d.helper["measure"] = func([]string) (int, string, string) { return 0, `{"bytes":2147483648,"files":1}`, "" }
	out := f.handle(snapReq("snapshot", Params{Volume: "db-data"}))
	if out.Status != http.StatusForbidden {
		t.Fatalf("over the cap: %d %v", out.Status, out.Body)
	}
	limit := out.Body["limit"].(map[string]string)
	if limit["name"] != "snapshots" || limit["allowed"] != "1 GiB (0 B used)" || limit["needed"] != "volume db-data: 2 GiB" ||
		!strings.HasSuffix(out.Body["extend"].(string), "adeled extend env snapshots 2GiB") {
		t.Fatalf("envelope %v", out.Body)
	}
	if got := d.log(); got != "helper measure" {
		t.Fatalf("something was paused or written: %s", got)
	}
	if r := rowsOf(t, f, "snapshot"); len(r) != 1 || r[0].Outcome != ledger.OutcomeRefused || r[0].LimitName != "snapshots" {
		t.Fatalf("rows %+v", r)
	}
}

func TestAFailedCopyRemovesItsPartialSnapshotAndUnpauses(t *testing.T) {
	for exit, want := range map[int]string{11: "the snapshot store is full", 137: "it was killed", 10: "grew past the cap"} {
		f, d := snapFixture(t, "")
		d.helper["copy"] = func([]string) (int, string, string) { return exit, "", "adeled volume copy: no space left on device" }
		out := f.handle(snapReq("snapshot", Params{Volume: "db-data"}))
		if out.Status != http.StatusBadGateway || !strings.Contains(out.Body["error"].(string), want) ||
			out.Body["partial_removed"] != true || len(out.Body["still_paused"].([]string)) != 0 {
			t.Fatalf("exit %d: %d %v", exit, out.Status, out.Body)
		}
		if !strings.HasSuffix(d.log(), "| helper copy | unpause db | remove "+strings.Split(d.log(), "create ")[1][:len(snapEnv)+14]) {
			t.Fatalf("exit %d: events %s", exit, d.log())
		}
		for n, l := range d.vols {
			if l[engine.LabelSnapshot] != "" {
				t.Fatalf("exit %d: partial snapshot %s left", exit, n)
			}
		}
		if len(rowsOf(t, f, ledger.ActionSnapshot)) != 0 || len(rowsOf(t, f, ledger.ActionUnpause)) != 1 {
			t.Fatalf("exit %d: rows %+v", exit, f.rows(t))
		}
		if d.find("c-db").state != "running" {
			t.Fatalf("exit %d: db %s", exit, d.find("c-db").state)
		}
	}
}

func TestAPauseThatDoesNotTakeUnpausesAndWritesNothing(t *testing.T) {
	f, d := snapFixture(t, "")
	d.pauseOK = false
	out := f.handle(snapReq("snapshot", Params{Volume: "db-data"}))
	if out.Status != http.StatusBadGateway || !strings.Contains(out.Body["error"].(string), "did not read back paused") {
		t.Fatalf("%d %v", out.Status, out.Body)
	}
	if strings.Contains(d.log(), "create") {
		t.Fatalf("a volume was created: %s", d.log())
	}
}

func TestOnlyTheEnvironmentsOwnVolumesAreSnapshotted(t *testing.T) {
	f, d := snapFixture(t, "")
	d.vols["tl-other-1_db-data"] = map[string]string{engine.LabelEnv: "tl-other-1", composeVolume: "db-data"}
	for _, asked := range []string{"cache", "tl-other-1_db-data", "/w/p/data"} {
		out := f.handle(snapReq("snapshot", Params{Volume: asked}))
		if out.Status != http.StatusNotFound || !strings.Contains(out.Body["error"].(string), "no such volume in this environment") ||
			strings.Join(out.Body["volumes"].([]string), ",") != "db-data" {
			t.Errorf("%s: %d %v", asked, out.Status, out.Body)
		}
	}
	refused := rowsOf(t, f, "snapshot")
	if len(refused) != 3 || refused[0].LimitName != "volume" || refused[0].Outcome != ledger.OutcomeRefused {
		t.Fatalf("rows %+v", refused)
	}
	if strings.Contains(d.log(), "helper") {
		t.Fatalf("a helper ran for a volume not the environment's: %s", d.log())
	}
	if out := f.handle(Request{Session: "s1", Capability: grants.CapDockerCompose, Action: "snapshot",
		Params: Params{Name: "tl-gone-1", Volume: "db-data"}}); out.Status != http.StatusNotFound ||
		strings.Join(out.Body["envs"].([]string), ",") != snapEnv {
		t.Fatalf("no environment: %d %v", out.Status, out.Body)
	}
}

func takeSnapshot(t *testing.T, f *fixture) string {
	t.Helper()
	out := f.handle(snapReq("snapshot", Params{Volume: "db-data"}))
	if out.Status != http.StatusOK {
		t.Fatalf("snapshot: %d %v", out.Status, out.Body)
	}
	return out.Body["snapshot"].(map[string]any)["id"].(string)
}

func TestARestoreChecksTheSnapshotThenStopsReplacesAndStarts(t *testing.T) {
	f, d := snapFixture(t, "")
	id := takeSnapshot(t, f)
	d.events = nil
	plan := f.handle(snapReq("restore", Params{Snapshot: id, DryRun: true}))
	if plan.Status != http.StatusOK || plan.Body["outcome"] != "plan" || strings.Join(plan.Body["stop"].([]string), ",") != "db" ||
		d.log() != "" {
		t.Fatalf("plan: %d %v; events %s", plan.Status, plan.Body, d.log())
	}
	out := f.handle(snapReq("restore", Params{Snapshot: id}))
	if out.Status != http.StatusOK || out.Body["digest"] != "sha256:aa" || strings.Join(out.Body["stopped"].([]string), ",") != "db" {
		t.Fatalf("restore: %d %v", out.Status, out.Body)
	}
	if want := "helper digest | unpause db | stop db | helper restore | start db"; d.log() != want {
		t.Fatalf("events\n got %s\nwant %s", d.log(), want)
	}
	if r := rowsOf(t, f, ledger.ActionRestore); len(r) != 1 || !strings.Contains(r[0].Cause, "from snapshot "+id) ||
		!strings.Contains(r[0].Cause, "Adele read: db running") {
		t.Fatalf("restore row %+v", r)
	}
	if len(rowsOf(t, f, ledger.ActionStop)) != 1 || len(rowsOf(t, f, ledger.ActionStart)) != 1 {
		t.Fatalf("stop and start rows %+v", f.rows(t))
	}
}

func TestASnapshotThatDoesNotMatchItsRecordStopsNothing(t *testing.T) {
	f, d := snapFixture(t, "")
	id := takeSnapshot(t, f)
	d.events = nil
	d.helper["digest"] = func([]string) (int, string, string) { return 0, `{"digest":"sha256:bb"}`, "" }
	out := f.handle(snapReq("restore", Params{Snapshot: id}))
	if out.Status != http.StatusBadGateway || !strings.Contains(out.Body["error"].(string), "does not match its record") ||
		len(out.Body["stopped"].([]string)) != 0 {
		t.Fatalf("%d %v", out.Status, out.Body)
	}
	if d.log() != "helper digest" {
		t.Fatalf("something was stopped: %s", d.log())
	}
}

func TestARestoreThatFailsPartwayStartsTheServicesAgainAndSaysPartial(t *testing.T) {
	f, d := snapFixture(t, "")
	id := takeSnapshot(t, f)
	d.helper["restore"] = func([]string) (int, string, string) { return 11, "", "no space" }
	out := f.handle(snapReq("restore", Params{Snapshot: id}))
	if out.Status != http.StatusBadGateway || out.Body["partial"] != true || strings.Join(out.Body["started"].([]string), ",") != "db" {
		t.Fatalf("%d %v", out.Status, out.Body)
	}
	if d.find("c-db").state != "running" {
		t.Fatalf("db left %s", d.find("c-db").state)
	}
	if len(rowsOf(t, f, ledger.ActionRestore)) != 0 {
		t.Fatal("a restore that did not finish was recorded as one")
	}
}

func TestAnUnknownSnapshotNamesTheOnesThereAre(t *testing.T) {
	f, _ := snapFixture(t, "")
	id := takeSnapshot(t, f)
	for _, action := range []string{"restore", "snapshot-rm"} {
		out := f.handle(snapReq(action, Params{Snapshot: "s-00000000"}))
		if out.Status != http.StatusNotFound || strings.Join(out.Body["snapshots"].([]string), ",") != id {
			t.Errorf("%s: %d %v", action, out.Status, out.Body)
		}
	}
	if out := f.handle(snapReq("restore", Params{Snapshot: "latest"})); out.Status != http.StatusBadRequest {
		t.Errorf("a bad id: %d", out.Status)
	}
}

func TestSnapshotRmRemovesItsVolumeAndEndsItsRecord(t *testing.T) {
	f, d := snapFixture(t, "")
	id := takeSnapshot(t, f)
	out := f.handle(snapReq("snapshot-rm", Params{Snapshot: id}))
	if out.Status != http.StatusOK || out.Body["bytes"] != int64(4096) || out.Body["cap"].(map[string]any)["used"] != int64(0) {
		t.Fatalf("%d %v", out.Status, out.Body)
	}
	if _, there := d.vols[snapshotVolume(snapEnv, id)]; there {
		t.Fatal("the volume is still there")
	}
	if rows, _ := f.led.Snapshots(grants.CapDockerCompose, snapEnv); len(rows) != 0 {
		t.Fatalf("still listed %+v", rows)
	}
}

// The recovery pass (R28, R30): an open hold is undone and ended; a snapshot whose volume is gone is ended; a volume
// with no record is removed at a start; a snapshot of an environment that is gone is removed as an orphan.
func TestTheRecoveryPassLeavesNothingHeldPartialOrOrphaned(t *testing.T) {
	f, d := snapFixture(t, "")
	id := takeSnapshot(t, f)
	gone := takeSnapshot(t, f)
	delete(d.vols, snapshotVolume(snapEnv, gone))
	// A pause recorded and made, never ended (Adele died in between).
	if _, err := f.b.hold(snapReq("snapshot", Params{}), "env", ledger.ActionPause, ledger.ActionUnpause, []string{"c-db"}, []string{"db"}); err != nil {
		t.Fatal(err)
	}
	d.find("c-db").state = "paused"
	d.vols[snapEnv+"-snap-0000beef"] = map[string]string{engine.LabelEnv: snapEnv, engine.LabelSnapshot: "s-0000beef",
		engine.LabelSession: "s1", engine.LabelGrant: "env", engine.LabelCreated: fixedNow.Format(time.RFC3339)}
	d.vols["tl-old-1-snap-0000cafe"] = map[string]string{engine.LabelEnv: "tl-old-1", engine.LabelSnapshot: "s-0000cafe",
		engine.LabelCreated: fixedNow.Format(time.RFC3339)}
	d.runs["h-left"] = []string{"volume", "copy"} // a stopped Adele's helper, still running
	var log bytes.Buffer
	f.b.Recover(context.Background(), true, &log)
	if !strings.Contains(log.String(), "removed 1 volume helpers") {
		t.Errorf("the stopped Adele's helper was not removed first: %s", log.String())
	}
	if d.find("c-db").state != "running" {
		t.Fatalf("db left %s; log %s", d.find("c-db").state, log.String())
	}
	if holds, _ := f.led.OpenHolds(grants.CapDockerCompose); len(holds) != 0 {
		t.Fatalf("holds still open %+v", holds)
	}
	for _, v := range []string{snapEnv + "-snap-0000beef", "tl-old-1-snap-0000cafe"} {
		if _, there := d.vols[v]; there {
			t.Errorf("%s left; log %s", v, log.String())
		}
	}
	if _, there := d.vols[snapshotVolume(snapEnv, id)]; !there {
		t.Fatal("a recorded snapshot of a live environment was removed")
	}
	rows, _ := f.led.Snapshots(grants.CapDockerCompose, snapEnv)
	if len(rows) != 1 || !strings.HasSuffix(rows[0].Resource, id) {
		t.Fatalf("listed %+v (the one whose volume is gone must be ended)", rows)
	}
	partial := rowsOf(t, f, ledger.ActionSnapshotRm)
	if len(partial) != 2 || !strings.Contains(partial[0].Cause+partial[1].Cause, "partial: the copy was cut short") ||
		!strings.Contains(partial[0].Cause+partial[1].Cause, "orphan: its environment tl-old-1 is gone") {
		t.Fatalf("rows %+v", partial)
	}
	// On a tick, a record-less volume younger than a copy's bound is a copy that may still be running: kept.
	d.vols[snapEnv+"-snap-0000f00d"] = map[string]string{engine.LabelEnv: snapEnv, engine.LabelSnapshot: "s-0000f00d",
		engine.LabelCreated: fixedNow.Format(time.RFC3339)}
	f.b.Recover(context.Background(), false, &log)
	if _, there := d.vols[snapEnv+"-snap-0000f00d"]; !there {
		t.Fatal("a young record-less volume was removed on a tick")
	}
}

func TestDownEndsTheEnvironmentsSnapshots(t *testing.T) {
	f, _ := snapFixture(t, "")
	takeSnapshot(t, f)
	f.b.endSnapshots(snapEnv, "removed with its environment")
	if rows, _ := f.led.Snapshots(grants.CapDockerCompose, snapEnv); len(rows) != 0 {
		t.Fatalf("still listed %+v", rows)
	}
}

func TestTheHelperGetsOnlyWhatItsOperationNeeds(t *testing.T) {
	cases := map[string]struct {
		exit int
		err  error
		want string
	}{
		"full":   {11, nil, "store is full"},
		"device": {12, nil, "does not copy"},
		"killed": {137, nil, "killed"},
		"other":  {3, nil, "exit 3"},
		"bound":  {0, &engine.SandboxError{TimedOut: true, Bound: time.Minute}, "within its bound"},
	}
	for name, c := range cases {
		status, why := helperFailed("copy", c.exit, "x", c.err)
		if !strings.Contains(why, c.want) || (name == "bound") != (status == http.StatusGatewayTimeout) {
			t.Errorf("%s: %d %q", name, status, why)
		}
	}
	if roundMiB(1) != 1<<20 || roundMiB(1<<20) != 1<<20 {
		t.Error("roundMiB")
	}
}
