// Package ledger is Adele's append-only account of every request: performed,
// refused and extended (spec FR-14..FR-17, data-model § Ledger).
//
// The file is SQLite through modernc.org/sqlite (pure Go; no cgo). `adeled
// serve` and the operator's `adeled extend` open the same file at once, so
// every connection runs WAL with a busy timeout, and transactions begin
// IMMEDIATE so that a writer waits for the lock instead of failing on upgrade.
package ledger

import (
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"net/url"
	"sort"
	"strings"
	"time"

	_ "modernc.org/sqlite" // registers the "sqlite" driver
)

// Outcomes recorded in the ledger's outcome column.
const (
	OutcomePerformed = "performed"
	OutcomeRefused   = "refused"
	OutcomeExtended  = "extended"
)

// OperatorSession is the session recorded on an extended row.
const OperatorSession = "operator"

// Limits names the limits an extension may change (contracts/adele-http.md).
var Limits = []string{"capabilities", "ttl", "ports", "instances", "budget"}

// ErrInvalid wraps every input-validation error; nothing is written.
var ErrInvalid = errors.New("ledger: invalid row")

// Row is one ledger row. Empty strings, a nil CostCents and a nil ExpiresAt
// are stored as NULL in the columns that are nullable.
type Row struct {
	ID         int64
	At         time.Time
	Outcome    string
	Grant      string
	Session    string
	Capability string
	Action     string
	Resource   string
	CostCents  *int64
	ExpiresAt  *time.Time
	Undo       string // JSON
	LimitName  string
	Allowed    string
	Needed     string
}

// Extension is one operator extension: the overlay on a grant's limit.
type Extension struct {
	Grant string
	Limit string
	Value string
	At    time.Time
}

// Ledger is an open ledger file.
type Ledger struct {
	db *sql.DB
}

// Open opens or creates the ledger at path and creates schema v1 when absent.
// It refuses a file whose schema_version is newer than SchemaVersion.
func Open(path string) (*Ledger, error) {
	if path == "" || strings.ContainsAny(path, "?#") {
		return nil, fmt.Errorf("ledger: unusable path %q", path)
	}
	q := url.Values{}
	q.Add("_pragma", "busy_timeout(5000)")
	q.Add("_pragma", "journal_mode(WAL)")
	q.Add("_pragma", "foreign_keys(on)")
	q.Set("_txlock", "immediate")
	db, err := sql.Open("sqlite", path+"?"+q.Encode())
	if err != nil {
		return nil, fmt.Errorf("ledger: open %s: %w", path, err)
	}
	if err := migrate(db); err != nil {
		db.Close()
		return nil, fmt.Errorf("ledger: %s: %w", path, err)
	}
	return &Ledger{db: db}, nil
}

// Close closes the ledger. Every later call returns an error.
func (l *Ledger) Close() error { return l.db.Close() }

const insertRow = `INSERT INTO ledger (at, outcome, "grant", session, capability, action,
	resource, cost_cents, expires_at, undo, limit_name, allowed, needed)
	VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`

// Performed appends a performed row. Grant, Session, Capability, Action,
// Resource, CostCents, ExpiresAt and Undo (valid JSON) are required; At
// defaults to now. ID and Outcome are ignored.
func (l *Ledger) Performed(r Row) (int64, error) {
	if err := required(map[string]string{"grant": r.Grant, "session": r.Session,
		"capability": r.Capability, "action": r.Action, "resource": r.Resource, "undo": r.Undo}); err != nil {
		return 0, err
	}
	if r.CostCents == nil || *r.CostCents < 0 {
		return 0, fmt.Errorf("%w: performed row needs a cost_cents of 0 or more", ErrInvalid)
	}
	if r.ExpiresAt == nil || r.ExpiresAt.IsZero() {
		return 0, fmt.Errorf("%w: performed row needs expires_at", ErrInvalid)
	}
	if !json.Valid([]byte(r.Undo)) {
		return 0, fmt.Errorf("%w: undo is not valid JSON", ErrInvalid)
	}
	r.Outcome = OutcomePerformed
	return l.insert(l.db, r)
}

// Refused appends a refused row. Session, Capability, Action, LimitName,
// Allowed and Needed are required; Grant may be empty (no grant resolved);
// CostCents is set only when a quote was obtained. At defaults to now.
func (l *Ledger) Refused(r Row) (int64, error) {
	if err := required(map[string]string{"session": r.Session, "capability": r.Capability,
		"action": r.Action, "limit_name": r.LimitName, "allowed": r.Allowed, "needed": r.Needed}); err != nil {
		return 0, err
	}
	if r.CostCents != nil && *r.CostCents < 0 {
		return 0, fmt.Errorf("%w: cost_cents is negative", ErrInvalid)
	}
	r.Outcome = OutcomeRefused
	r.ExpiresAt, r.Undo = nil, ""
	return l.insert(l.db, r)
}

// Extended records an operator extension: one extensions row and its matching
// extended ledger row, in one transaction. It returns the ledger row's id.
func (l *Ledger) Extended(grant, limit, oldValue, newValue string, at time.Time) (int64, error) {
	if err := required(map[string]string{"grant": grant, "limit": limit,
		"old value": oldValue, "new value": newValue}); err != nil {
		return 0, err
	}
	if !knownLimit(limit) {
		return 0, fmt.Errorf("%w: unknown limit %q (one of %s)", ErrInvalid, limit, strings.Join(Limits, ", "))
	}
	if at.IsZero() {
		at = time.Now()
	}
	tx, err := l.db.Begin()
	if err != nil {
		return 0, fmt.Errorf("ledger: begin: %w", err)
	}
	defer tx.Rollback() //nolint:errcheck // a no-op after Commit
	if _, err := tx.Exec(`INSERT INTO extensions ("grant", limit_name, value, at) VALUES (?, ?, ?, ?)`,
		grant, limit, newValue, formatTime(at)); err != nil {
		return 0, fmt.Errorf("ledger: insert extension: %w", err)
	}
	id, err := l.insert(tx, Row{At: at, Outcome: OutcomeExtended, Grant: grant, Session: OperatorSession,
		LimitName: limit, Allowed: oldValue, Needed: newValue})
	if err != nil {
		return 0, err
	}
	if err := tx.Commit(); err != nil {
		return 0, fmt.Errorf("ledger: commit extension: %w", err)
	}
	return id, nil
}

type execer interface {
	Exec(query string, args ...any) (sql.Result, error)
}

func (l *Ledger) insert(e execer, r Row) (int64, error) {
	if r.At.IsZero() {
		r.At = time.Now()
	}
	var expires any
	if r.ExpiresAt != nil {
		expires = formatTime(*r.ExpiresAt)
	}
	var cost any
	if r.CostCents != nil {
		cost = *r.CostCents
	}
	res, err := e.Exec(insertRow, formatTime(r.At), r.Outcome, r.Grant, r.Session,
		nullable(r.Capability), nullable(r.Action), nullable(r.Resource), cost, expires,
		nullable(r.Undo), nullable(r.LimitName), nullable(r.Allowed), nullable(r.Needed))
	if err != nil {
		return 0, fmt.Errorf("ledger: append %s row: %w", r.Outcome, err)
	}
	return res.LastInsertId()
}

// required reports the first empty field, in sorted order for a stable message.
func required(fields map[string]string) error {
	var missing []string
	for name, v := range fields {
		if strings.TrimSpace(v) == "" {
			missing = append(missing, name)
		}
	}
	if len(missing) == 0 {
		return nil
	}
	sort.Strings(missing)
	return fmt.Errorf("%w: missing %s", ErrInvalid, strings.Join(missing, ", "))
}

func knownLimit(limit string) bool {
	for _, l := range Limits {
		if l == limit {
			return true
		}
	}
	return false
}

func nullable(s string) any {
	if s == "" {
		return nil
	}
	return s
}

func formatTime(t time.Time) string { return t.UTC().Format(time.RFC3339) }
