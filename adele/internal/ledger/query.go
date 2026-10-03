package ledger

import (
	"database/sql"
	"fmt"
	"time"
)

const selectRows = `SELECT id, at, outcome, "grant", session, capability, action, resource,
	cost_cents, expires_at, undo, limit_name, allowed, needed FROM ledger ORDER BY id`

// Rows returns every ledger row in id order.
func (l *Ledger) Rows() ([]Row, error) {
	rows, err := l.db.Query(selectRows)
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
		cost                                sql.NullInt64
	)
	if err := rows.Scan(&r.ID, &at, &r.Outcome, &r.Grant, &r.Session, &capability, &action,
		&resource, &cost, &expires, &undo, &limitName, &allowed, &needed); err != nil {
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

// Live returns the count of grant's performed rows. Slice 0 has no reaper or
// delete, so every creation is live.
func (l *Ledger) Live(grant string) (int, error) {
	var n int
	err := l.db.QueryRow(`SELECT count(*) FROM ledger WHERE "grant" = ? AND outcome = ?`,
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
