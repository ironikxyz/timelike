package ledger

import (
	"database/sql"
	"fmt"
	"time"
)

const rowColumns = `id, at, outcome, "grant", session, capability, action, resource,
	cost_cents, expires_at, undo, limit_name, allowed, needed, ref, agent, cause, attempts, host`

const selectRows = `SELECT ` + rowColumns + ` FROM ledger ORDER BY id`

// Rows returns every ledger row in id order.
func (l *Ledger) Rows() ([]Row, error) {
	return l.query(selectRows)
}

func (l *Ledger) query(q string, args ...any) ([]Row, error) {
	rows, err := l.db.Query(q, args...)
	if err != nil {
		return nil, fmt.Errorf("ledger: read rows: %w", err)
	}
	defer rows.Close()
	var out []Row
	for rows.Next() {
		r, err := scanRow(rows)
		if err != nil {
			return nil, err
		}
		out = append(out, r)
	}
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("ledger: read rows: %w", err)
	}
	return out, nil
}

func scanRow(rows *sql.Rows) (Row, error) {
	var (
		r                                   Row
		at                                  string
		capability, action, resource, undo  sql.NullString
		limitName, allowed, needed, expires sql.NullString
		agent, cause, host                  sql.NullString
		cost, ref, attempts                 sql.NullInt64
	)
	if err := rows.Scan(&r.ID, &at, &r.Outcome, &r.Grant, &r.Session, &capability, &action,
		&resource, &cost, &expires, &undo, &limitName, &allowed, &needed,
		&ref, &agent, &cause, &attempts, &host); err != nil {
		return Row{}, fmt.Errorf("ledger: scan row: %w", err)
	}
	var err error
	if r.At, err = parseTime(at); err != nil {
		return Row{}, fmt.Errorf("ledger: row %d at: %w", r.ID, err)
	}
	if expires.Valid {
		t, err := parseTime(expires.String)
		if err != nil {
			return Row{}, fmt.Errorf("ledger: row %d expires_at: %w", r.ID, err)
		}
		r.ExpiresAt = &t
	}
	if cost.Valid {
		c := cost.Int64
		r.CostCents = &c
	}
	r.Capability, r.Action, r.Resource, r.Undo = capability.String, action.String, resource.String, undo.String
	r.LimitName, r.Allowed, r.Needed = limitName.String, allowed.String, needed.String
	if ref.Valid {
		v := ref.Int64
		r.Ref = &v
	}
	if attempts.Valid {
		v := int(attempts.Int64)
		r.Attempts = &v
	}
	r.Agent, r.Cause, r.Host = agent.String, cause.String, host.String
	return r, nil
}

// Spent returns the sum of cost_cents over grant's performed rows.
func (l *Ledger) Spent(grant string) (int64, error) {
	var n int64
	err := l.db.QueryRow(`SELECT COALESCE(SUM(cost_cents), 0) FROM ledger
		WHERE "grant" = ? AND outcome = ?`, grant, OutcomePerformed).Scan(&n)
	if err != nil {
		return 0, fmt.Errorf("ledger: spent %s: %w", grant, err)
	}
	return n, nil
}

// unended is the condition that a performed row p has no reaped or gone row: its resource may still exist.
const unended = `NOT EXISTS (SELECT 1 FROM ledger e WHERE e.ref = p.id AND e.outcome IN ('reaped', 'gone'))`

// Live returns the count of grant's performed rows whose resource has not been reaped or found gone
// (FR-34). Spent is unchanged by a reap: money spent stays spent.
func (l *Ledger) Live(grant string) (int, error) {
	var n int
	err := l.db.QueryRow(`SELECT count(*) FROM ledger p WHERE p."grant" = ? AND p.outcome = ? AND `+unended,
		grant, OutcomePerformed).Scan(&n)
	if err != nil {
		return 0, fmt.Errorf("ledger: live %s: %w", grant, err)
	}
	return n, nil
}

// Extensions returns grant's extensions in insertion order (latest last, so
// a caller overlaying them in order gets "latest wins per limit").
func (l *Ledger) Extensions(grant string) ([]Extension, error) {
	rows, err := l.db.Query(`SELECT "grant", limit_name, value, at FROM extensions
		WHERE "grant" = ? ORDER BY id`, grant)
	if err != nil {
		return nil, fmt.Errorf("ledger: extensions %s: %w", grant, err)
	}
	defer rows.Close()
	var out []Extension
	for rows.Next() {
		var e Extension
		var at string
		if err := rows.Scan(&e.Grant, &e.Limit, &e.Value, &at); err != nil {
			return nil, fmt.Errorf("ledger: scan extension: %w", err)
		}
		if e.At, err = parseTime(at); err != nil {
			return nil, fmt.Errorf("ledger: extension at: %w", err)
		}
		out = append(out, e)
	}
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("ledger: extensions %s: %w", grant, err)
	}
	return out, nil
}

func parseTime(s string) (time.Time, error) { return time.Parse(time.RFC3339, s) }

// Due is a performed row whose resource has expired and has no reaped or gone row, with the failed passes
// recorded against it so far (FR-25).
type Due struct {
	Row         Row
	Failures    int
	LastFailure time.Time // zero when Failures is 0
}

// Due returns every performed row that expired at or before now and has not been reaped or found gone, in
// expiry order. It reads the ledger, never the reaper's memory, so a restarted Adele finds what an earlier
// one left (Scenario 7).
func (l *Ledger) Due(now time.Time) ([]Due, error) {
	rows, err := l.query(`SELECT `+prefixed("p")+` FROM ledger p WHERE p.outcome = ? AND p.expires_at <= ? AND `+
		unended+` ORDER BY p.expires_at, p.id`, OutcomePerformed, formatTime(now))
	if err != nil {
		return nil, err
	}
	out := make([]Due, 0, len(rows))
	for _, r := range rows {
		d := Due{Row: r}
		var last sql.NullString
		if err := l.db.QueryRow(`SELECT count(*), max(at) FROM ledger WHERE ref = ? AND outcome = ?`,
			r.ID, OutcomeReapFailed).Scan(&d.Failures, &last); err != nil {
			return nil, fmt.Errorf("ledger: failures of %d: %w", r.ID, err)
		}
		if last.Valid {
			if d.LastFailure, err = parseTime(last.String); err != nil {
				return nil, fmt.Errorf("ledger: failures of %d: %w", r.ID, err)
			}
		}
		out = append(out, d)
	}
	return out, nil
}

// Denials returns refused rows recorded at or after since, newest first, at most perHost for each host
// (FR-36). With host non-empty, only that host's. A refusal recorded before schema 2 has no host and is
// returned with Host "".
func (l *Ledger) Denials(since time.Time, host string, perHost int) ([]Row, error) {
	q := `SELECT ` + rowColumns + ` FROM ledger WHERE outcome = ? AND at >= ?`
	args := []any{OutcomeRefused, formatTime(since)}
	if host != "" {
		q += ` AND host = ?`
		args = append(args, host)
	}
	rows, err := l.query(q+` ORDER BY at DESC, id DESC`, args...)
	if err != nil {
		return nil, err
	}
	seen := map[string]int{}
	out := rows[:0]
	for _, r := range rows {
		if perHost > 0 && seen[r.Host] >= perHost {
			continue
		}
		seen[r.Host]++
		out = append(out, r)
	}
	return out, nil
}

func prefixed(alias string) string {
	cols := []string{"id", "at", "outcome", `"grant"`, "session", "capability", "action", "resource",
		"cost_cents", "expires_at", "undo", "limit_name", "allowed", "needed", "ref", "agent", "cause",
		"attempts", "host"}
	s := ""
	for i, c := range cols {
		if i > 0 {
			s += ", "
		}
		s += alias + "." + c
	}
	return s
}
