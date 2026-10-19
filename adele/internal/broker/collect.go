package broker

// Feature 13 slice 1 (the operator's decision 2; 014 research R19): a session ends when it is ended explicitly
// (`adele session end`) or when the agent container that made its requests no longer exists. A collection pass
// removes every environment whose session has ended, read back from the daemon, and records each removal with its
// cause. The agent's `adele env collect` runs one now; Adele's reaper runs the same pass on its tick.

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"time"

	"timelike/adele/internal/engine"
	"timelike/adele/internal/grants"
	"timelike/adele/internal/ledger"
)

// Collected is one environment a pass removed, or failed to.
type Collected struct {
	Name     string         `json:"name"`
	Session  string         `json:"session"`
	Cause    string         `json:"cause"`
	Removed  engine.Counts  `json:"removed"`
	Left     *engine.Counts `json:"left,omitempty"`
	LedgerID int64          `json:"ledger_id,omitempty"`
}

// sessionBody is what session end and collect read from the agent: who asks, nothing else.
type sessionBody struct {
	Session string `json:"session"`
	Agent   string `json:"agent,omitempty"`
}

func readSessionBody(w http.ResponseWriter, r *http.Request) (sessionBody, bool) {
	var body sessionBody
	dec := json.NewDecoder(http.MaxBytesReader(w, r.Body, MaxBodyBytes))
	dec.DisallowUnknownFields()
	if err := dec.Decode(&body); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]any{"error": "the request is not valid JSON: " + err.Error()})
		return body, false
	}
	if !sessionRe.MatchString(body.Session) {
		writeJSON(w, http.StatusBadRequest, map[string]any{"error": fmt.Sprintf("bad session id %q", body.Session),
			"remediation": "TIMELIKE_SESSION must match ^[A-Za-z0-9._-]{1,64}$"})
		return body, false
	}
	if body.Agent != "" && !agentRe.MatchString(body.Agent) {
		writeJSON(w, http.StatusBadRequest, map[string]any{"error": fmt.Sprintf("bad agent name %q", body.Agent)})
		return body, false
	}
	return body, true
}

func (b *Broker) sessionEnd(w http.ResponseWriter, r *http.Request) {
	body, ok := readSessionBody(w, r)
	if !ok {
		return
	}
	out := b.EndSession(body.Session, body.Agent)
	writeJSON(w, out.Status, out.Body)
}

// EndSession ends session with a ledger row, once; a second end says it was already ended (FR-28). "Ended" is read
// back from the ledger, never taken from the write's success (cross-stack P004).
func (b *Broker) EndSession(session, agent string) Outcome {
	b.mu.Lock()
	defer b.mu.Unlock()
	row, ended, err := b.Ledger.SessionEnded(session)
	if err != nil {
		return ledgerFailed(err)
	}
	outcome := "already ended"
	if !ended {
		if _, err := b.Ledger.Recorded(ledger.Row{At: b.now(), Grant: ledger.NoGrant, Session: session, Agent: agent,
			Capability: ledger.CapabilitySession, Action: ledger.ActionEnd, Resource: session,
			Cause: "ended with adele session end; its environments are collected"}); err != nil {
			return ledgerFailed(err)
		}
		if row, ended, err = b.Ledger.SessionEnded(session); err != nil || !ended {
			return ledgerFailed(errors.Join(err, errors.New("the end was written but does not read back")))
		}
		outcome = "ended"
	}
	return Outcome{http.StatusOK, map[string]any{"outcome": outcome, "session": session,
		"ended_at": row.At.UTC().Format(time.RFC3339), "ledger_id": row.ID}}
}

func (b *Broker) collect(w http.ResponseWriter, r *http.Request) {
	if _, ok := readSessionBody(w, r); !ok {
		return
	}
	if b.Envs == nil {
		writeJSON(w, http.StatusServiceUnavailable, map[string]any{"error": "this Adele has no Docker daemon",
			"remediation": "the operator starts her with the socket: make up"})
		return
	}
	collected, failed, err := b.Collect(r.Context())
	if err != nil {
		writeJSON(w, http.StatusBadGateway, map[string]any{"error": "the collection pass failed: " + err.Error(),
			"collected": collected, "failed": failed, "remediation": "retry; Adele's reaper also runs the pass on its interval"})
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"collected": collected, "failed": failed, "count": len(collected),
		"revision": b.Revision})
}

// Collect is one collection pass (R19): every live environment whose session has ended, by (b) the ledger's end row
// or (a) its requester label naming an agent container the daemon no longer has, is taken down and read back. 0
// left is a reaped row with the cause; anything left is a reap-failed row, tried again on the next pass.
func (b *Broker) Collect(ctx context.Context) (collected, failed []Collected, err error) {
	collected, failed = []Collected{}, []Collected{}
	if b.Envs == nil {
		return collected, failed, nil
	}
	e := b.Envs
	b.mu.Lock()
	rows, err := b.Ledger.LiveRows(grants.CapDockerCompose)
	b.mu.Unlock()
	if err != nil || len(rows) == 0 {
		return collected, failed, err
	}
	agents, err := e.Engine.Agents(ctx)
	if err != nil {
		return collected, failed, err
	}
	present := map[string]bool{}
	for _, a := range agents {
		present[a.ID] = true
	}
	for _, row := range rows {
		cause, err := b.endedCause(ctx, row, present)
		if err != nil {
			return collected, failed, err
		}
		if cause == "" {
			continue
		}
		e.lock("collect " + row.Resource)
		removed, left, derr := e.Engine.Down(context.WithoutCancel(ctx), row.Resource)
		e.unlock()
		c := Collected{Name: row.Resource, Session: row.Session, Cause: cause, Removed: removed}
		outcome, words := ledger.OutcomeReaped, fmt.Sprintf("collected: %s; %d containers, %d networks, %d volumes, %d images removed; 0 left, read back from the daemon",
			cause, removed.Containers, removed.Networks, removed.Volumes, removed.Images)
		if derr != nil || left.Total() > 0 {
			l := left
			c.Left = &l
			outcome, words = ledger.OutcomeReapFailed, fmt.Sprintf("collecting it failed: %s; %d objects left, read back from the daemon", cause, left.Total())
			if derr != nil {
				words += ": " + derr.Error()
			}
		}
		b.mu.Lock()
		id, _, rerr := b.Ledger.Reap(row.ID, outcome, words, 1, b.now())
		b.mu.Unlock()
		if rerr != nil {
			return collected, failed, rerr
		}
		c.LedgerID = id
		if outcome == ledger.OutcomeReaped {
			collected = append(collected, c)
		} else {
			failed = append(failed, c)
		}
	}
	return collected, failed, nil
}

// endedCause says why row's session has ended, or "" while it has not.
func (b *Broker) endedCause(ctx context.Context, row ledger.Row, present map[string]bool) (string, error) {
	b.mu.Lock()
	end, ended, err := b.Ledger.SessionEnded(row.Session)
	b.mu.Unlock()
	if err != nil {
		return "", err
	}
	if ended {
		return fmt.Sprintf("session %s ended at %s (adele session end, ledger #%d)", row.Session,
			end.At.UTC().Format(time.RFC3339), end.ID), nil
	}
	cs, err := b.Envs.Engine.Containers(ctx, engine.LabelEnv+"="+row.Resource)
	if err != nil {
		return "", err
	}
	for _, c := range cs {
		r := c.Labels[engine.LabelRequester]
		if r == "" || r == "unknown" {
			continue // a slice-0 environment, or one whose requester was not found: only session end or the ttl
		}
		if !present[r] {
			return fmt.Sprintf("session %s's agent container %s no longer exists", row.Session, short(r)), nil
		}
		return "", nil
	}
	return "", nil
}

func short(id string) string {
	if len(id) > 12 {
		return id[:12]
	}
	return id
}
