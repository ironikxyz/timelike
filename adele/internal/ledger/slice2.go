package ledger

// Feature 13 slice 2 (014 plan § Slice 2, R24, R28, R30): snapshots of an environment's volumes, and the holds a
// snapshot or a restore puts on its services. A snapshot is a performed row whose undo is its removal; a pause or a
// stop is a performed row written before the act, whose undo is the unpause or the start; each hold is ended by a
// row referring to it. None of them has an expiry, so no live count, instance limit or due list ever sees them.

import (
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"strings"
	"time"
)

// Slice 2's actions on docker.compose.
const (
	ActionSnapshot   = "snapshot"
	ActionSnapshotRm = "snapshot-rm"
	ActionRestore    = "restore"
	ActionPause      = "pause"
	ActionUnpause    = "unpause"
	ActionStop       = "stop"
	ActionStart      = "start"
)

// Kept appends a performed row with an undo and no expiry: a snapshot, or a pause or stop a snapshot or restore
// holds (slice 2). Grant, Session, Capability, Action, Resource and Undo (valid JSON) are required. At defaults to
// now.
func (l *Ledger) Kept(r Row) (int64, error) {
	if err := required(map[string]string{"grant": r.Grant, "session": r.Session,
		"capability": r.Capability, "action": r.Action, "resource": r.Resource, "undo": r.Undo}); err != nil {
		return 0, err
	}
	if !json.Valid([]byte(r.Undo)) {
		return 0, fmt.Errorf("%w: undo is not valid JSON", ErrInvalid)
	}
	if r.CostCents != nil && *r.CostCents < 0 {
		return 0, fmt.Errorf("%w: cost_cents is negative", ErrInvalid)
	}
	r.Outcome = OutcomePerformed
	r.ExpiresAt, r.Ref, r.Attempts, r.Host, r.Extend = nil, nil, nil, "", ""
	return l.append(r)
}

// Ended appends the row that ends the hold ref (an unpause or a start, read back), with action and cause. Grant,
// session, agent, capability and resource are copied from ref. It writes only while ref has no ending, checked in
// the same transaction, so a request and the recovery pass end a hold once; wrote is false when it already had one.
func (l *Ledger) Ended(ref int64, action, cause string, at time.Time) (id int64, wrote bool, err error) {
	if strings.TrimSpace(action) == "" || strings.TrimSpace(cause) == "" {
		return 0, false, fmt.Errorf("%w: an ending needs an action and a cause", ErrInvalid)
	}
	if at.IsZero() {
		at = time.Now()
	}
	err = l.write("ending", func(tx *sql.Tx) error {
		id, wrote = 0, false
		var (
			grant, session, outcome     string
			agent, capability, resource sql.NullString
			ended                       int
		)
		err := tx.QueryRow(`SELECT outcome, "grant", session, agent, capability, resource FROM ledger WHERE id = ?`,
			ref).Scan(&outcome, &grant, &session, &agent, &capability, &resource)
		if errors.Is(err, sql.ErrNoRows) {
			return fmt.Errorf("%w: no ledger row %d", ErrInvalid, ref)
		}
		if err != nil {
			return fmt.Errorf("ledger: read row %d: %w", ref, err)
		}
		if outcome != OutcomePerformed {
			return fmt.Errorf("%w: row %d is %s, not performed", ErrInvalid, ref, outcome)
		}
		if err := tx.QueryRow(`SELECT count(*) FROM ledger WHERE ref = ?`, ref).Scan(&ended); err != nil {
			return fmt.Errorf("ledger: read endings of %d: %w", ref, err)
		}
		if ended > 0 {
			return nil
		}
		id, err = l.insert(tx, Row{At: at, Outcome: OutcomePerformed, Grant: grant, Session: session,
			Agent: agent.String, Capability: capability.String, Action: action, Resource: resource.String, Ref: &ref,
			Cause: cause})
		wrote = err == nil
		return err
	})
	if err != nil {
		return 0, false, err
	}
	return id, wrote, nil
}

// noEnding is a row with no row referring to it: an open hold, or a snapshot not yet removed.
const noEnding = `p.expires_at IS NULL AND NOT EXISTS (SELECT 1 FROM ledger e WHERE e.ref = p.id)`

// OpenHolds returns every pause and stop row of capability with no ending, oldest first (R28).
func (l *Ledger) OpenHolds(capability string) ([]Row, error) {
	return l.query(`SELECT `+prefixed("p")+` FROM ledger p WHERE p.outcome = ? AND p.capability = ? AND
		p.action IN (?, ?) AND `+noEnding+` ORDER BY p.id`, OutcomePerformed, capability, ActionPause, ActionStop)
}

// Snapshots returns the snapshot rows of environment env (resource "ENV/ID") that no removal has ended, newest
// first. env "" returns every environment's.
func (l *Ledger) Snapshots(capability, env string) ([]Row, error) {
	q := `SELECT ` + prefixed("p") + ` FROM ledger p WHERE p.outcome = ? AND p.capability = ? AND p.action = ? AND ` +
		noEnding
	args := []any{OutcomePerformed, capability, ActionSnapshot}
	if env != "" {
		q += ` AND substr(p.resource, 1, ?) = ?`
		args = append(args, len(env)+1, env+"/")
	}
	return l.query(q+` ORDER BY p.id DESC`, args...)
}

// SnapshotRow returns the snapshot row of resource ("ENV/ID") that no removal has ended, and whether there is one.
func (l *Ledger) SnapshotRow(capability, resource string) (Row, bool, error) {
	rows, err := l.query(`SELECT `+prefixed("p")+` FROM ledger p WHERE p.outcome = ? AND p.capability = ? AND
		p.action = ? AND p.resource = ? AND `+noEnding+` ORDER BY p.id DESC LIMIT 1`,
		OutcomePerformed, capability, ActionSnapshot, resource)
	if err != nil || len(rows) == 0 {
		return Row{}, false, err
	}
	return rows[0], true, nil
}
