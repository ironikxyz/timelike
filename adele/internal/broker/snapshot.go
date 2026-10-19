package broker

// Feature 13 slice 2 (014 plan § Slice 2, R23-R30; contracts/adele-env.md § Slice 2): snapshots of an environment's
// named volumes, and their restore. A snapshot is a volume on the daemon that Adele creates and labels like the rest
// of the environment, filled by a helper from her own image: she never opens volume contents. Its record (digest,
// bytes, files) is its ledger row, written once the copy's digest reads back equal to the source's.
//
// Order is what makes it hardened. A pause or a stop is recorded before it is made and ended once its undo reads
// back, so a crash in between is found by the next recovery pass (R28). A failed copy removes its partial snapshot
// and unpauses, whatever failed. Every one runs under Envs' lock, so no up, down or other snapshot interleaves.

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"sort"
	"strconv"
	"strings"
	"time"

	"timelike/adele/internal/engine"
	"timelike/adele/internal/grants"
	"timelike/adele/internal/ledger"
)

// Bounds on a snapshot's and a restore's own calls (R25, R27).
const (
	SnapshotTimeout = 5 * time.Minute  // a copy, either way
	HelperTimeout   = 2 * time.Minute  // a measure or a digest
	StopWait        = 10 * time.Second // a service stopped for a restore
	ReadyWait       = 60 * time.Second // how long Adele reads a restored service's healthcheck back
	MaxNote         = 200
)

// composeVolume is compose's own label naming a volume's key in the project.
const composeVolume = "com.docker.compose.volume"

// The helper's own exits (R25).
const (
	helperOverBudget  = 10
	helperNoSpace     = 11
	helperUnsupported = 12
)

// snapRecord is a snapshot's record, kept in its row's undo beside the removal it names (data-model § Slice 2).
type snapRecord struct {
	Volume     string `json:"volume"`
	VolumeName string `json:"volume_name"`
	Digest     string `json:"digest"`
	Bytes      int64  `json:"bytes"`
	Files      int    `json:"files"`
	Sockets    int    `json:"sockets"`
	TakenAt    string `json:"taken_at"`
	Note       string `json:"note"`
	Store      string `json:"store"`
}

type snapUndo struct {
	Capability string            `json:"capability"`
	Action     string            `json:"action"`
	Params     map[string]string `json:"params"`
	Record     snapRecord        `json:"record"`
}

// holdUndo is a pause's or a stop's undo: the action that ends it, and the containers it holds.
type holdUndo struct {
	Capability string            `json:"capability"`
	Action     string            `json:"action"`
	Params     map[string]string `json:"params"`
	Containers []string          `json:"containers"`
	Services   []string          `json:"services"`
}

// helperOut is the helper's one JSON line.
type helperOut struct {
	Digest     string `json:"digest"`
	Bytes      int64  `json:"bytes"`
	Files      int    `json:"files"`
	Sockets    int    `json:"sockets"`
	CopyDigest string `json:"copy_digest"`
}

func snapshotID() string {
	b := make([]byte, 4)
	_, _ = rand.Read(b)
	return "s-" + hex.EncodeToString(b)
}

// snapshotVolume is the daemon name of snapshot id's volume: <env>-snap-<hex>.
func snapshotVolume(env, id string) string { return env + "-snap-" + strings.TrimPrefix(id, "s-") }

func (b *Broker) handleSnapshot(ctx context.Context, req Request) Outcome {
	switch req.Action {
	case ledger.ActionSnapshot:
		return b.snapshot(ctx, req)
	case "snapshots":
		return b.snapshots(ctx, req)
	case ledger.ActionRestore:
		return b.restore(ctx, req)
	}
	return b.snapshotRm(ctx, req)
}

// liveEnv returns the environment's up row and containers, or the answer naming the live ones.
func (b *Broker) liveEnv(ctx context.Context, name string) (ledger.Row, []engine.Container, Outcome, bool) {
	b.mu.Lock()
	row, live, err := b.Ledger.LiveResource(grants.CapDockerCompose, name)
	var rows []ledger.Row
	if err == nil && !live {
		rows, err = b.Ledger.LiveRows(grants.CapDockerCompose)
	}
	b.mu.Unlock()
	if err != nil {
		return row, nil, ledgerFailed(err), false
	}
	if !live {
		names := []string{}
		for _, r := range rows {
			names = append(names, r.Resource)
		}
		return row, nil, Outcome{http.StatusNotFound, map[string]any{"error": "no environment named " + name, "envs": names,
			"remediation": "list them with adele env status"}}, false
	}
	cs, err := b.Envs.Engine.Containers(ctx, engine.LabelEnv+"="+name)
	if err != nil {
		return row, nil, daemonFailed(err), false
	}
	if len(cs) == 0 {
		return row, nil, Outcome{http.StatusNotFound, map[string]any{"error": "environment " + name +
			" has no containers on the daemon", "envs": []string{}, "remediation": "bring it up again: adele env up"}}, false
	}
	return row, cs, Outcome{}, true
}

// ownVolumes returns the environment's own named volumes, key → daemon name, never its snapshots (FR-32).
func (e *Envs) ownVolumes(ctx context.Context, name string) (map[string]string, error) {
	vs, err := e.Engine.Volumes(ctx, engine.LabelEnv+"="+name)
	if err != nil {
		return nil, err
	}
	out := map[string]string{}
	for _, v := range vs {
		if v.Labels[engine.LabelSnapshot] != "" {
			continue
		}
		key := v.Labels[composeVolume]
		if key == "" {
			key = strings.TrimPrefix(v.Name, name+"_")
		}
		out[key] = v.Name
	}
	return out, nil
}

func keys(m map[string]string) []string {
	out := make([]string, 0, len(m))
	for k := range m {
		out = append(out, k)
	}
	sort.Strings(out)
	return out
}

// volumeOf resolves what the agent named (a key or a daemon name) to one of the environment's own volumes.
func volumeOf(own map[string]string, asked string) (key, daemonName string, ok bool) {
	if n, ok := own[asked]; ok {
		return asked, n, true
	}
	for k, n := range own {
		if n == asked {
			return k, n, true
		}
	}
	return "", "", false
}

// noSuchVolume is FR-32's refusal: a refused row, and exit 3 naming the environment's own volumes.
func (b *Broker) noSuchVolume(req Request, grant, asked string, own map[string]string) Outcome {
	names := keys(own)
	allowed := "the environment's own named volumes: " + strings.Join(names, ", ")
	if len(names) == 0 {
		allowed = "the environment's own named volumes: none"
	}
	b.mu.Lock()
	id, err := b.Ledger.Refused(ledger.Row{At: b.now(), Grant: grant, Session: req.Session, Agent: req.Agent,
		Capability: req.Capability, Action: req.Action, Resource: req.Params.Name, LimitName: "volume",
		Allowed: allowed, Needed: asked, Host: EnvHost})
	b.mu.Unlock()
	if err != nil {
		return ledgerFailed(err)
	}
	return Outcome{http.StatusNotFound, map[string]any{"error": fmt.Sprintf("no such volume in this environment: %s", asked),
		"volumes": names, "performed": false, "ledger_id": id,
		"remediation": "a snapshot is of one of " + req.Params.Name + "'s own named volumes; a bind mount or another environment's volume is not"}}
}

// capOf is the grant's cap for environment name, what its snapshots use, and its store.
func (b *Broker) capOf(grant, name string) (grants.Grant, int64, []ledger.Row, error) {
	b.mu.Lock()
	defer b.mu.Unlock()
	base, ok := b.Grants.Get(grant)
	if !ok {
		return grants.Grant{}, 0, nil, fmt.Errorf("the environment's grant %s is not in the grant file", grant)
	}
	g, err := b.effective(base)
	if err != nil {
		return g, 0, nil, err
	}
	rows, err := b.Ledger.Snapshots(grants.CapDockerCompose, name)
	if err != nil {
		return g, 0, nil, err
	}
	var used int64
	for _, r := range rows {
		if rec, ok := recordOf(r); ok {
			used += rec.Bytes
		}
	}
	return g, used, rows, nil
}

func recordOf(r ledger.Row) (snapRecord, bool) {
	var u snapUndo
	if json.Unmarshal([]byte(r.Undo), &u) != nil || u.Record.Digest == "" {
		return snapRecord{}, false
	}
	return u.Record, true
}

func capBody(g grants.Grant, used int64) map[string]any {
	return map[string]any{"bytes": g.SnapshotBytes, "used": used, "left": max(g.SnapshotBytes-used, 0),
		"store": g.SnapshotStore}
}

// roundMiB rounds n up to a whole MiB, for the size an extension names.
func roundMiB(n int64) int64 { return (n + 1<<20 - 1) / (1 << 20) * (1 << 20) }

// helper runs `adeled volume op` in a sandbox from Adele's image (R25): src read-only at /src, dst (if any) at /dst.
// Reading needs DAC_READ_SEARCH only; writing needs the copy's five.
func (e *Envs) helper(ctx context.Context, env, op, src, dst string, maxBytes int64, timeout time.Duration) (helperOut, int, string, error) {
	suffix := make([]byte, 3)
	_, _ = rand.Read(suffix)
	cmd := []string{"volume", op, "--src", "/src"}
	binds := []string{src + ":/src:ro"}
	caps := []string{"DAC_READ_SEARCH"}
	if dst != "" {
		cmd = append(cmd, "--dst", "/dst")
		binds = append(binds, dst+":/dst")
		caps = engine.HelperCaps
	}
	if maxBytes >= 0 {
		cmd = append(cmd, "--max-bytes", strconv.FormatInt(maxBytes, 10))
	}
	stdout, stderr, exit, err := e.Engine.Run(ctx, engine.Sandbox{
		Image: e.SandboxImage, Entrypoint: []string{"/usr/local/bin/adeled"}, Cmd: cmd, User: "0:0", Env: []string{"HOME=/tmp"},
		WorkingDir: "/", Binds: binds, Name: "tl-sandbox-" + env + "-vol-" + hex.EncodeToString(suffix),
		Timeout: timeout, CapAdd: caps, Kind: engine.SandboxVolume,
	})
	var out helperOut
	if err == nil && exit == 0 {
		lines := strings.Split(strings.TrimSpace(string(stdout)), "\n")
		if json.Unmarshal([]byte(lines[len(lines)-1]), &out) != nil {
			return out, exit, "", fmt.Errorf("the volume helper's answer is not readable JSON: %q", lastLines(string(stdout), 1))
		}
	}
	return out, exit, lastLines(string(stderr), 2), err
}

// helperFailed words a helper that did not finish, by its exit (R25).
func helperFailed(op string, exit int, stderr string, err error) (int, string) {
	var se *engine.SandboxError
	switch {
	case errors.As(err, &se) && se.TimedOut:
		return http.StatusGatewayTimeout, fmt.Sprintf("the %s did not finish within its bound (%s)", op, se.Bound)
	case err != nil:
		return http.StatusBadGateway, fmt.Sprintf("the %s helper failed: %v", op, err)
	case exit == helperOverBudget:
		return http.StatusBadGateway, "the volume grew past the cap between its measure and its copy: " + stderr
	case exit == helperNoSpace:
		return http.StatusBadGateway, "the snapshot store is full: " + stderr
	case exit == helperUnsupported:
		return http.StatusBadGateway, "the volume holds an entry a snapshot does not copy: " + stderr
	case exit == 137:
		return http.StatusBadGateway, fmt.Sprintf("the %s helper ended without finishing (exit 137: it was killed)", op)
	}
	why := fmt.Sprintf("the %s helper ended without finishing (exit %d)", op, exit)
	if stderr != "" {
		why += ": " + stderr
	}
	return http.StatusBadGateway, why
}

// users returns the environment's containers in state that mount the volume daemonName, and their services.
func users(cs []engine.Container, daemonName string, states ...string) (ids, services []string) {
	for _, c := range cs {
		in := false
		for _, s := range states {
			in = in || c.State == s
		}
		if !in {
			continue
		}
		for _, m := range c.Mounts {
			if m.Type == "volume" && m.Name == daemonName {
				ids = append(ids, c.ID)
				services = append(services, c.Labels[engine.ComposeService])
				break
			}
		}
	}
	sort.Strings(services)
	return ids, services
}

// hold records a pause or a stop of containers BEFORE it is made (R28), and returns its row.
func (b *Broker) hold(req Request, grant, action, end string, ids, services []string) (int64, error) {
	undo, _ := json.Marshal(holdUndo{Capability: grants.CapDockerCompose, Action: end,
		Params: map[string]string{"name": req.Params.Name}, Containers: ids, Services: services})
	b.mu.Lock()
	defer b.mu.Unlock()
	return b.Ledger.Kept(ledger.Row{At: b.now(), Grant: grant, Session: req.Session, Agent: req.Agent,
		Capability: grants.CapDockerCompose, Action: action, Resource: req.Params.Name, Undo: string(undo),
		Cause: fmt.Sprintf("%s %s for a %s, recorded before the %s", action, strings.Join(services, ", "), req.Action, action)})
}

// release undoes a hold on ids (unpause, or start), reads each back, and ends the hold's row when every one is back.
// It returns the containers still held.
func (b *Broker) release(ctx context.Context, holdID int64, action string, ids []string, cause string) []string {
	e := b.Envs
	var still []string
	for _, id := range ids {
		var err error
		if action == ledger.ActionUnpause {
			err = e.Engine.Unpause(ctx, id)
		} else {
			err = e.Engine.Start(ctx, id)
		}
		state, rerr := e.Engine.State(ctx, id)
		if err != nil && rerr == nil && state != "running" || rerr != nil || (state != "running" && state != "removed") {
			still = append(still, id)
		}
	}
	if len(still) == 0 && holdID != 0 {
		b.mu.Lock()
		_, _, _ = b.Ledger.Ended(holdID, action, cause, b.now())
		b.mu.Unlock()
	}
	return still
}

func servicesOf(cs []engine.Container, ids []string) []string {
	out := []string{}
	for _, c := range cs {
		for _, id := range ids {
			if c.ID == id {
				out = append(out, c.Labels[engine.ComposeService])
			}
		}
	}
	sort.Strings(out)
	return out
}

func (b *Broker) snapshot(ctx context.Context, req Request) Outcome {
	e, p := b.Envs, req.Params
	if len(p.Note) > MaxNote {
		return envFail(http.StatusBadRequest, fmt.Sprintf("the note is %d characters; at most %d", len(p.Note), MaxNote), "shorten it")
	}
	if p.Volume == "" {
		return envFail(http.StatusBadRequest, "name the volume to snapshot", "adele env snapshots NAME lists the environment's volumes")
	}
	began := time.Now()
	e.lock("snapshot " + p.Name)
	defer e.unlock()
	ctx = context.WithoutCancel(ctx)
	row, cs, out, ok := b.liveEnv(ctx, p.Name)
	if !ok {
		return out
	}
	own, err := e.ownVolumes(ctx, p.Name)
	if err != nil {
		return daemonFailed(err)
	}
	key, vol, ok := volumeOf(own, p.Volume)
	if !ok {
		return b.noSuchVolume(req, row.Grant, p.Volume, own)
	}
	g, used, _, err := b.capOf(row.Grant, p.Name)
	if err != nil {
		return ledgerFailed(err)
	}

	// The cap, before anything is written (FR-34): the helper measures the volume, unpaused and read-only.
	measured, exit, stderr, err := e.helper(ctx, p.Name, "measure", vol, "", -1, HelperTimeout)
	if err != nil || exit != 0 {
		status, why := helperFailed("measure", exit, stderr, err)
		return envFail(status, "the snapshot of "+key+" could not measure it: "+why, "nothing was written; retry")
	}
	if used+measured.Bytes > g.SnapshotBytes {
		return b.refuseAt(req, g.Name, refusal{grants.LimitSnapshots,
			fmt.Sprintf("%s (%s used)", grants.HumanSize(g.SnapshotBytes), grants.HumanSize(used)),
			fmt.Sprintf("volume %s: %s", key, grants.HumanSize(measured.Bytes)),
			grants.FormatSize(roundMiB(used + measured.Bytes)), nil}, EnvHost)
	}

	// Its users paused, recorded first (FR-35, R28).
	ids, services := users(cs, vol, "running")
	var holdID int64
	paused := []string{}
	var pausedAt time.Time
	if len(ids) > 0 {
		if holdID, err = b.hold(req, g.Name, ledger.ActionPause, ledger.ActionUnpause, ids, services); err != nil {
			return ledgerFailed(err)
		}
		pausedAt = time.Now()
		for _, id := range ids {
			perr := e.Engine.Pause(ctx, id)
			state, serr := e.Engine.State(ctx, id)
			if perr != nil || serr != nil || state != "paused" {
				still := b.release(ctx, holdID, ledger.ActionUnpause, ids, "a pause did not take, so every service was unpaused, read back running")
				why := fmt.Sprintf("pausing %s did not read back paused (%s)", strings.Join(servicesOf(cs, []string{id}), ", "), state)
				if perr != nil {
					why = "pausing failed: " + perr.Error()
				}
				return Outcome{http.StatusBadGateway, map[string]any{"error": "the snapshot of " + key + " was not taken: " + why,
					"performed": false, "partial_removed": false, "unpaused": servicesOf(cs, ids), "still_paused": servicesOf(cs, still),
					"remediation": "nothing was written; retry"}}
			}
			paused = append(paused, id)
		}
	}

	id := snapshotID()
	snapVol := snapshotVolume(p.Name, id)
	labels := map[string]string{engine.LabelEnv: p.Name, engine.LabelSnapshot: id, engine.LabelSnapshotOf: vol,
		engine.LabelSession: req.Session, engine.LabelGrant: g.Name, engine.LabelRequester: requesterOf(cs),
		engine.LabelCreated: b.now().Format(time.RFC3339)}
	var opts map[string]string
	if g.SnapshotStore == grants.StoreTmpfs {
		opts = map[string]string{"type": "tmpfs", "device": "tmpfs", "o": "size=" + strconv.FormatInt(g.SnapshotBytes, 10)}
	}
	var copied helperOut
	var cerr error
	var cexit int
	var cstderr string
	if cerr = e.Engine.CreateVolume(ctx, snapVol, labels, opts); cerr == nil {
		copied, cexit, cstderr, cerr = e.helper(ctx, p.Name, "copy", vol, snapVol, g.SnapshotBytes-used, SnapshotTimeout)
	}

	// Unpaused whatever happened, read back running (FR-35, FR-39).
	still := []string{}
	pausedFor := time.Duration(0)
	if len(paused) > 0 {
		still = b.release(ctx, holdID, ledger.ActionUnpause, paused, "the copy ended; unpaused, read back running")
		pausedFor = time.Since(pausedAt)
	}
	failure := func(status int, why string) Outcome {
		_ = e.Engine.RemoveVolume(ctx, snapVol)
		_, there, rerr := e.Engine.VolumeExists(ctx, snapVol)
		remedy := "the partial snapshot was removed, read back gone; retry"
		if there || rerr != nil {
			remedy = "removing the partial snapshot " + snapVol + " did not read back gone; Adele's recovery pass removes it"
		}
		if len(still) > 0 {
			remedy += "; " + strings.Join(servicesOf(cs, still), ", ") + " did not read back running, and Adele's recovery pass unpauses it"
		}
		return Outcome{status, map[string]any{"error": "the snapshot of " + key + " was not taken: " + why, "performed": false,
			"partial_removed": !there && rerr == nil, "unpaused": servicesOf(cs, minus(paused, still)),
			"still_paused": servicesOf(cs, still), "timed_out": status == http.StatusGatewayTimeout, "remediation": remedy}}
	}
	if cerr != nil || cexit != 0 {
		status, why := helperFailed("copy", cexit, cstderr, cerr)
		if cerr != nil && !isSandboxErr(cerr) {
			status, why = http.StatusBadGateway, "the snapshot volume could not be made: "+cerr.Error()
		}
		return failure(status, why)
	}
	if copied.Digest == "" || copied.Digest != copied.CopyDigest {
		return failure(http.StatusBadGateway, fmt.Sprintf("the copy read back as %s, not its source's %s", copied.CopyDigest, copied.Digest))
	}

	// Taken, read back: the record, then the answer (FR-37, FR-42).
	takenAt := b.now()
	rec := snapRecord{Volume: key, VolumeName: vol, Digest: copied.Digest, Bytes: copied.Bytes, Files: copied.Files,
		Sockets: copied.Sockets, TakenAt: takenAt.Format(time.RFC3339), Note: p.Note, Store: g.SnapshotStore}
	undo, _ := json.Marshal(snapUndo{Capability: grants.CapDockerCompose, Action: ledger.ActionSnapshotRm,
		Params: map[string]string{"name": p.Name, "snapshot": id}, Record: rec})
	cause := fmt.Sprintf("snapshot %s of volume %s: %d bytes, %d files, %s, read back", id, key, rec.Bytes, rec.Files, rec.Digest)
	if len(paused) > 0 {
		cause += fmt.Sprintf("; paused %s for %.1f s", strings.Join(servicesOf(cs, paused), ", "), pausedFor.Seconds())
	}
	b.mu.Lock()
	lid, err := b.Ledger.Kept(ledger.Row{At: takenAt, Grant: g.Name, Session: req.Session, Agent: req.Agent,
		Capability: grants.CapDockerCompose, Action: ledger.ActionSnapshot, Resource: p.Name + "/" + id, Undo: string(undo),
		Cause: cause})
	b.mu.Unlock()
	if err != nil {
		return Outcome{http.StatusInternalServerError, map[string]any{"error": fmt.Sprintf("snapshot %s was taken but the ledger write failed: %v", id, err),
			"performed": true, "remediation": "it has no record, so Adele's recovery pass removes it as partial; take it again"}}
	}
	pausedList := []map[string]string{}
	for _, c := range cs {
		for _, pid := range paused {
			if c.ID == pid {
				pausedList = append(pausedList, map[string]string{"service": c.Labels[engine.ComposeService], "container": c.ID})
			}
		}
	}
	body := map[string]any{"outcome": ledger.OutcomePerformed, "grant": g.Name, "resource": p.Name,
		"snapshot": snapshotDoc(id, rec, lid), "paused": pausedList, "paused_ms": pausedFor.Milliseconds(),
		"took_ms": time.Since(began).Milliseconds(), "cap": capBody(g, used+rec.Bytes), "ledger_id": lid,
		"undo": string(undo), "revision": b.Revision}
	if len(still) > 0 {
		body["still_paused"] = servicesOf(cs, still)
	}
	return Outcome{http.StatusOK, body}
}

func isSandboxErr(err error) bool {
	var se *engine.SandboxError
	return errors.As(err, &se)
}

func minus(all, some []string) []string {
	out := []string{}
	for _, a := range all {
		found := false
		for _, s := range some {
			found = found || a == s
		}
		if !found {
			out = append(out, a)
		}
	}
	return out
}

// requesterOf is the environment's requester, as its containers' labels have it.
func requesterOf(cs []engine.Container) string {
	for _, c := range cs {
		if r := c.Labels[engine.LabelRequester]; r != "" {
			return r
		}
	}
	return "unknown"
}

func snapshotDoc(id string, rec snapRecord, ledgerID int64) map[string]any {
	return map[string]any{"id": id, "volume": rec.Volume, "volume_name": rec.VolumeName, "bytes": rec.Bytes,
		"files": rec.Files, "sockets": rec.Sockets, "digest": rec.Digest, "taken_at": rec.TakenAt, "note": rec.Note,
		"ledger_id": ledgerID}
}

func (b *Broker) snapshots(ctx context.Context, req Request) Outcome {
	row, _, out, ok := b.liveEnv(ctx, req.Params.Name)
	if !ok {
		return out
	}
	own, err := b.Envs.ownVolumes(ctx, req.Params.Name)
	if err != nil {
		return daemonFailed(err)
	}
	g, used, rows, err := b.capOf(row.Grant, req.Params.Name)
	if err != nil {
		return ledgerFailed(err)
	}
	list := []map[string]any{}
	for _, r := range rows {
		if rec, ok := recordOf(r); ok {
			list = append(list, snapshotDoc(strings.TrimPrefix(r.Resource, req.Params.Name+"/"), rec, r.ID))
		}
	}
	return Outcome{http.StatusOK, map[string]any{"resource": req.Params.Name, "snapshots": list, "cap": capBody(g, used),
		"volumes": keys(own), "revision": b.Revision}}
}

// theSnapshot finds snapshot id of environment name, or the answer naming the ones there are.
func (b *Broker) theSnapshot(name, id string) (ledger.Row, snapRecord, Outcome, bool) {
	b.mu.Lock()
	row, ok, err := b.Ledger.SnapshotRow(grants.CapDockerCompose, name+"/"+id)
	var rows []ledger.Row
	if err == nil && !ok {
		rows, err = b.Ledger.Snapshots(grants.CapDockerCompose, name)
	}
	b.mu.Unlock()
	if err != nil {
		return row, snapRecord{}, ledgerFailed(err), false
	}
	rec, good := recordOf(row)
	if !ok || !good {
		ids := []string{}
		for _, r := range rows {
			ids = append(ids, strings.TrimPrefix(r.Resource, name+"/"))
		}
		return row, rec, Outcome{http.StatusNotFound, map[string]any{"error": fmt.Sprintf("no snapshot %s in %s", id, name),
			"snapshots": ids, "remediation": "list them with adele env snapshots " + name}}, false
	}
	return row, rec, Outcome{}, true
}

func (b *Broker) snapshotRm(ctx context.Context, req Request) Outcome {
	e, p := b.Envs, req.Params
	e.lock("snapshot-rm " + p.Name)
	defer e.unlock()
	ctx = context.WithoutCancel(ctx)
	envRow, _, out, ok := b.liveEnv(ctx, p.Name)
	if !ok {
		return out
	}
	row, rec, out, ok := b.theSnapshot(p.Name, p.Snapshot)
	if !ok {
		return out
	}
	vol := snapshotVolume(p.Name, p.Snapshot)
	if err := e.Engine.RemoveVolume(ctx, vol); err != nil {
		return daemonFailed(err)
	}
	if _, there, err := e.Engine.VolumeExists(ctx, vol); err != nil || there {
		return envFail(http.StatusBadGateway, "snapshot "+p.Snapshot+"'s volume did not read back gone", "retry adele env snapshot-rm")
	}
	b.mu.Lock()
	id, _, err := b.Ledger.Reap(row.ID, ledger.OutcomeReaped, fmt.Sprintf("removed with adele env snapshot-rm by session %s; %d bytes freed; read back gone",
		req.Session, rec.Bytes), 1, b.now())
	b.mu.Unlock()
	if err != nil {
		return ledgerFailed(err)
	}
	g, used, _, err := b.capOf(envRow.Grant, p.Name)
	if err != nil {
		return ledgerFailed(err)
	}
	return Outcome{http.StatusOK, map[string]any{"outcome": "removed", "resource": p.Name, "snapshot": p.Snapshot,
		"bytes": rec.Bytes, "cap": capBody(g, used), "ledger_id": id, "revision": b.Revision}}
}

func (b *Broker) restore(ctx context.Context, req Request) Outcome {
	e, p := b.Envs, req.Params
	began := time.Now()
	e.lock("restore " + p.Name)
	defer e.unlock()
	ctx = context.WithoutCancel(ctx)
	envRow, cs, out, ok := b.liveEnv(ctx, p.Name)
	if !ok {
		return out
	}
	snapRow, rec, out, ok := b.theSnapshot(p.Name, p.Snapshot)
	if !ok {
		return out
	}
	// This snapshot, of this volume, of this environment (FR-32).
	snapVol := snapshotVolume(p.Name, p.Snapshot)
	labels, there, err := e.Engine.VolumeExists(ctx, snapVol)
	if err != nil {
		return daemonFailed(err)
	}
	if !there || labels[engine.LabelEnv] != p.Name || labels[engine.LabelSnapshot] != p.Snapshot {
		return Outcome{http.StatusBadGateway, map[string]any{"error": fmt.Sprintf("snapshot %s's volume %s is not on the daemon as %s's", p.Snapshot, snapVol, p.Name),
			"stopped": []string{}, "remediation": "nothing was stopped; take a new snapshot"}}
	}
	own, err := e.ownVolumes(ctx, p.Name)
	if err != nil {
		return daemonFailed(err)
	}
	if n, ok := own[rec.Volume]; !ok || n != rec.VolumeName || labels[engine.LabelSnapshotOf] != rec.VolumeName {
		return Outcome{http.StatusConflict, map[string]any{"error": fmt.Sprintf("snapshot %s was taken from volume %s, which %s no longer has as it was",
			p.Snapshot, rec.Volume, p.Name), "volumes": keys(own), "stopped": []string{},
			"remediation": "nothing was stopped; a snapshot restores only the volume it was taken from"}}
	}
	ids, services := users(cs, rec.VolumeName, "running", "paused", "restarting")
	snap := snapshotDoc(p.Snapshot, rec, snapRow.ID)
	if p.DryRun {
		return Outcome{http.StatusOK, map[string]any{"outcome": "plan", "resource": p.Name, "snapshot": snap,
			"volume": rec.Volume, "stop": nonNilStrings(services), "replace": "volume " + rec.Volume, "revision": b.Revision}}
	}

	// Whole, before anything is stopped (FR-37).
	check, exit, stderr, err := e.helper(ctx, p.Name, "digest", snapVol, "", -1, HelperTimeout)
	if err != nil || exit != 0 {
		status, why := helperFailed("digest", exit, stderr, err)
		return Outcome{status, map[string]any{"error": "snapshot " + p.Snapshot + " could not be checked: " + why,
			"stopped": []string{}, "remediation": "nothing was stopped; retry"}}
	}
	if check.Digest != rec.Digest {
		return Outcome{http.StatusBadGateway, map[string]any{"error": fmt.Sprintf("snapshot %s does not match its record: its content reads as %s, recorded %s",
			p.Snapshot, check.Digest, rec.Digest), "stopped": []string{},
			"remediation": "nothing was stopped; this snapshot cannot be restored: remove it with adele env snapshot-rm"}}
	}

	// Its users stopped, recorded first (R27, R28).
	var holdID int64
	stoppedAt := time.Now()
	if len(ids) > 0 {
		if holdID, err = b.hold(req, envRow.Grant, ledger.ActionStop, ledger.ActionStart, ids, services); err != nil {
			return ledgerFailed(err)
		}
		for _, id := range ids {
			_ = e.Engine.Unpause(ctx, id) // a paused container stops only once thawed
			_ = e.Engine.Stop(ctx, id, StopWait)
		}
	}
	notStopped := []string{}
	for _, id := range ids {
		if state, err := e.Engine.State(ctx, id); err != nil || state == "running" || state == "paused" {
			notStopped = append(notStopped, id)
		}
	}
	var restored helperOut
	var rerr error
	var rexit int
	var rstderr string
	if len(notStopped) == 0 {
		restored, rexit, rstderr, rerr = e.helper(ctx, p.Name, "restore", snapVol, rec.VolumeName, -1, SnapshotTimeout)
	}
	// Started again whatever happened (R27 step 5).
	still := []string{}
	if len(ids) > 0 {
		still = b.release(ctx, holdID, ledger.ActionStart, ids, "the restore ended; started, read back running")
	}
	stoppedFor := time.Since(stoppedAt)
	if len(notStopped) > 0 {
		return Outcome{http.StatusBadGateway, map[string]any{"error": fmt.Sprintf("%s did not stop, so volume %s was not touched",
			strings.Join(servicesOf(cs, notStopped), ", "), rec.Volume), "partial": false, "started": servicesOf(cs, minus(ids, still)),
			"remediation": "retry the restore"}}
	}
	if rerr != nil || rexit != 0 || restored.CopyDigest != rec.Digest {
		_, why := helperFailed("restore", rexit, rstderr, rerr)
		if rerr == nil && rexit == 0 {
			why = fmt.Sprintf("the volume read back as %s, not the snapshot's %s", restored.CopyDigest, rec.Digest)
		}
		return Outcome{http.StatusBadGateway, map[string]any{"error": "the restore of " + rec.Volume + " from " + p.Snapshot + " did not finish: " + why,
			"partial": true, "started": servicesOf(cs, minus(ids, still)), "still_stopped": servicesOf(cs, still),
			"remediation": "volume " + rec.Volume + "'s contents are partial; restore again, or take the environment down: adele env down " + p.Name}}
	}

	// Readiness as Adele reads it from the daemon (R27 step 6); the client probes ports from the agent's container.
	readiness := e.readBack(ctx, p.Name, services)
	svcs, err := e.Services(ctx, p.Name)
	if err != nil {
		return daemonFailed(err)
	}
	words := []string{}
	for _, s := range services {
		words = append(words, s+" "+readiness[s])
	}
	cause := fmt.Sprintf("restored volume %s from snapshot %s (ledger #%d), %s read back; stopped %s for %.1f s; Adele read: %s",
		rec.Volume, p.Snapshot, snapRow.ID, rec.Digest, strings.Join(services, ", "), stoppedFor.Seconds(), strings.Join(words, ", "))
	b.mu.Lock()
	lid, err := b.Ledger.Recorded(ledger.Row{At: b.now(), Grant: envRow.Grant, Session: req.Session, Agent: req.Agent,
		Capability: grants.CapDockerCompose, Action: ledger.ActionRestore, Resource: p.Name, Cause: cause})
	b.mu.Unlock()
	if err != nil {
		return Outcome{http.StatusInternalServerError, map[string]any{"error": "the volume was restored but the ledger write failed: " + err.Error(),
			"performed": true, "remediation": "the operator checks Adele's log: docker logs " + DefaultContainer}}
	}
	return Outcome{http.StatusOK, map[string]any{"outcome": ledger.OutcomePerformed, "resource": p.Name, "snapshot": snap,
		"volume": rec.Volume, "stopped": nonNilStrings(services), "stopped_ms": stoppedFor.Milliseconds(), "digest": rec.Digest,
		"services": svcs, "adele_readiness": readiness, "still_stopped": servicesOf(cs, still), "ledger_id": lid,
		"took_ms": time.Since(began).Milliseconds(), "revision": b.Revision}}
}

func nonNilStrings(l []string) []string {
	if l == nil {
		return []string{}
	}
	return l
}

// readBack waits, bounded, for each service's state as the daemon reports it: healthy for one with a healthcheck,
// running for one without. It returns what it last read (healthy, running, starting, unhealthy, exited N).
func (e *Envs) readBack(ctx context.Context, name string, services []string) map[string]string {
	out := map[string]string{}
	until := time.Now().Add(ReadyWait)
	for {
		svcs, err := e.Services(ctx, name)
		done := err == nil
		for _, want := range services {
			word := "gone"
			for _, s := range svcs {
				if s.Service != want {
					continue
				}
				switch {
				case s.State == "exited":
					word = fmt.Sprintf("exited %d", s.ExitCode)
				case s.Health != "":
					word = s.Health
				default:
					word = s.State
				}
			}
			out[want] = word
			done = done && (word == "healthy" || word == "running" || strings.HasPrefix(word, "exited"))
		}
		if done || time.Now().After(until) {
			return out
		}
		time.Sleep(time.Second)
	}
}

// Recover is the pass of R28 and R30, at Adele's start (atStart) and on every reaper tick: it ends every open hold
// (unpausing or starting what it still holds, read back), ends the record of every snapshot whose volume is gone,
// and removes snapshot volumes whose environment is gone (orphans) or that have no record (partial). Each act is a
// ledger row naming its cause. It takes Envs' lock, so it never undoes the hold of a snapshot in progress.
func (b *Broker) Recover(ctx context.Context, atStart bool, log io.Writer) {
	e := b.Envs
	if e == nil {
		return
	}
	e.lock("recovery")
	defer e.unlock()
	when := "found by the reaper's pass"
	if atStart {
		when = "found when Adele started"
		// A volume helper still running is a stopped Adele's copy: removed first, so the partial snapshot it holds
		// open can be removed below.
		if n, err := e.Engine.RemoveSandboxes(ctx, engine.SandboxVolume); err != nil {
			fmt.Fprintf(log, "adeled: recovery: removing a stopped Adele's volume helpers failed: %v\n", err)
		} else if n > 0 {
			fmt.Fprintf(log, "adeled: recovery: removed %d volume helpers a stopped Adele left running\n", n)
		}
	}
	b.mu.Lock()
	holds, err := b.Ledger.OpenHolds(grants.CapDockerCompose)
	b.mu.Unlock()
	if err != nil {
		fmt.Fprintf(log, "adeled: recovery: the ledger failed: %v\n", err)
		return
	}
	for _, h := range holds {
		var u holdUndo
		if json.Unmarshal([]byte(h.Undo), &u) != nil {
			continue
		}
		verb := "unpaused"
		if u.Action == ledger.ActionStart {
			verb = "started"
		}
		still := b.release(ctx, h.ID, u.Action, u.Containers, fmt.Sprintf("%s: %s held by ledger #%d (Adele or her helper stopped before ending it); %s, read back running",
			when, strings.Join(u.Services, ", "), h.ID, verb))
		if len(still) == 0 {
			fmt.Fprintf(log, "adeled: recovery: %s %s of %s (ledger #%d)\n", verb, strings.Join(u.Services, ", "), h.Resource, h.ID)
		} else {
			fmt.Fprintf(log, "adeled: recovery: %d containers of %s did not read back running; tried again on the next pass\n", len(still), h.Resource)
		}
	}

	vols, err := e.Engine.Volumes(ctx, engine.LabelSnapshot)
	if err != nil {
		fmt.Fprintf(log, "adeled: recovery: the daemon failed: %v\n", err)
		return
	}
	have := map[string]engine.Object{}
	for _, v := range vols {
		have[v.Name] = v
	}
	b.mu.Lock()
	rows, err := b.Ledger.Snapshots(grants.CapDockerCompose, "")
	b.mu.Unlock()
	if err != nil {
		fmt.Fprintf(log, "adeled: recovery: the ledger failed: %v\n", err)
		return
	}
	recorded := map[string]ledger.Row{}
	for _, r := range rows {
		env, id, _ := strings.Cut(r.Resource, "/")
		vol := snapshotVolume(env, id)
		if _, ok := have[vol]; !ok {
			b.mu.Lock()
			_, _, _ = b.Ledger.Reap(r.ID, ledger.OutcomeGone, "its volume "+vol+" is gone from the daemon: removed with its environment, or outside Adele", 0, b.now())
			b.mu.Unlock()
			continue
		}
		recorded[vol] = r
	}
	for _, v := range vols {
		env, id := v.Labels[engine.LabelEnv], v.Labels[engine.LabelSnapshot]
		row, hasRecord := recorded[v.Name]
		b.mu.Lock()
		_, live, lerr := b.Ledger.LiveResource(grants.CapDockerCompose, env)
		b.mu.Unlock()
		if lerr != nil {
			continue
		}
		cs, cerr := e.Engine.Containers(ctx, engine.LabelEnv+"="+env)
		if cerr != nil {
			continue
		}
		var why string
		switch {
		case !live && len(cs) == 0:
			why = "orphan: its environment " + env + " is gone"
		case !hasRecord && (atStart || old(v, b.now())):
			why = "partial: the copy was cut short, so it has no record"
		default:
			continue
		}
		if err := e.Engine.RemoveVolume(ctx, v.Name); err != nil {
			fmt.Fprintf(log, "adeled: recovery: removing %s failed: %v\n", v.Name, err)
			continue
		}
		if _, there, err := e.Engine.VolumeExists(ctx, v.Name); err != nil || there {
			continue
		}
		cause := why + "; " + when + "; removed, read back gone"
		b.mu.Lock()
		if hasRecord {
			_, _, err = b.Ledger.Reap(row.ID, ledger.OutcomeReaped, cause, 1, b.now())
		} else {
			grant := v.Labels[engine.LabelGrant]
			if grant == "" {
				grant = ledger.NoGrant
			}
			session := v.Labels[engine.LabelSession]
			if session == "" {
				session = ledger.OperatorSession
			}
			_, err = b.Ledger.Recorded(ledger.Row{At: b.now(), Grant: grant, Session: session, Capability: grants.CapDockerCompose,
				Action: ledger.ActionSnapshotRm, Resource: env + "/" + id, Cause: cause})
		}
		b.mu.Unlock()
		if err != nil {
			fmt.Fprintf(log, "adeled: recovery: the ledger failed: %v\n", err)
			continue
		}
		fmt.Fprintf(log, "adeled: recovery: %s %s\n", v.Name, cause)
	}
}

// old reports whether a snapshot volume was made longer ago than a copy's bound and a minute, so no copy of Adele's
// is still filling it.
func old(v engine.Object, now time.Time) bool {
	made, err := time.Parse(time.RFC3339, v.Labels[engine.LabelCreated])
	return err == nil && now.Sub(made) > SnapshotTimeout+time.Minute
}

// endSnapshots ends the records of environment name's snapshots once its volumes are gone, read back: by down or a
// collection, with cause (R30).
func (b *Broker) endSnapshots(name, cause string) {
	b.mu.Lock()
	defer b.mu.Unlock()
	rows, err := b.Ledger.Snapshots(grants.CapDockerCompose, name)
	if err != nil {
		return
	}
	for _, r := range rows {
		_, _, _ = b.Ledger.Reap(r.ID, ledger.OutcomeReaped, cause, 1, b.now())
	}
}
