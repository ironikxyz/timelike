// Package ledger is Adele's append-only account of every request: performed,
// refused and extended (spec FR-14..FR-17, data-model § Ledger), and from slice 1
// of every reap: reaped, gone or reap-failed (FR-24..FR-31).
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
	// The reaper's outcomes (slice 1, FR-26). Reaped and gone end a resource's life in the
	// ledger; a reap-failed row records one failed pass and the resource stays due.
	OutcomeReaped     = "reaped"
	OutcomeGone       = "gone"
	OutcomeReapFailed = "reap-failed"
)

// ActionDelete is the action recorded on reap rows: the undo the performed row names (D-7).
const ActionDelete = "delete"

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
	// Slice 1 (schema 2). Ref is the performed row a reap concerns; Agent is self-declared attribution,
	// like Session (D-14); Cause and Attempts describe a reap; Host is where a refused request would have
	// reached (FR-35).
	Ref      *int64
	Agent    string
	Cause    string
	Attempts *int
	Host     string
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
	resource, cost_cents, expires_at, undo, limit_name, allowed, needed, ref, agent, cause, attempts, host)
	VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`

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
	r.Ref, r.Cause, r.Attempts, r.Host = nil, "", nil, ""
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
	r.ExpiresAt, r.Undo, r.Ref, r.Cause, r.Attempts = nil, "", nil, "", nil
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

// Reap records one reap of the performed row ref: its outcome (reaped, gone or reap-failed), the cause in
// words and the delete attempts made. The grant, session, agent, capability and resource are copied from
// the performed row, so a reap row says whose resource it was (FR-27).
//
// It writes only while ref is still unreaped, checked in the same immediate transaction, so the serving
// reaper and the operator's `adeled reap` can run at once and a resource gets one ending (FR-28). wrote
// is false, with a nil error, when ref already had one.
func (l *Ledger) Reap(ref int64, outcome, cause string, attempts int, at time.Time) (id int64, wrote bool, err error) {
	switch outcome {
	case OutcomeReaped, OutcomeGone, OutcomeReapFailed:
	default:
		return 0, false, fmt.Errorf("%w: %q is not a reap outcome", ErrInvalid, outcome)
	}
	if strings.TrimSpace(cause) == "" {
		return 0, false, fmt.Errorf("%w: missing cause", ErrInvalid)
	}
	if attempts < 0 {
		return 0, false, fmt.Errorf("%w: attempts is negative", ErrInvalid)
	}
	if at.IsZero() {
		at = time.Now()
	}
	tx, err := l.db.Begin()
	if err != nil {
		return 0, false, fmt.Errorf("ledger: begin: %w", err)
	}
	defer tx.Rollback() //nolint:errcheck // a no-op after Commit
	var (
		grant, session, outcomeWas  string
		agent, capability, resource sql.NullString
		ended                       int
	)
	err = tx.QueryRow(`SELECT outcome, "grant", session, agent, capability, resource FROM ledger WHERE id = ?`,
		ref).Scan(&outcomeWas, &grant, &session, &agent, &capability, &resource)
	if errors.Is(err, sql.ErrNoRows) {
		return 0, false, fmt.Errorf("%w: no ledger row %d", ErrInvalid, ref)
	}
	if err != nil {
		return 0, false, fmt.Errorf("ledger: read row %d: %w", ref, err)
	}
	if outcomeWas != OutcomePerformed {
		return 0, false, fmt.Errorf("%w: row %d is %s, not performed", ErrInvalid, ref, outcomeWas)
	}
	if err := tx.QueryRow(`SELECT count(*) FROM ledger WHERE ref = ? AND outcome IN (?, ?)`,
		ref, OutcomeReaped, OutcomeGone).Scan(&ended); err != nil {
		return 0, false, fmt.Errorf("ledger: read reaps of %d: %w", ref, err)
	}
	if ended > 0 {
		return 0, false, nil
	}
	n := attempts
	id, err = l.insert(tx, Row{At: at, Outcome: outcome, Grant: grant, Session: session, Agent: agent.String,
		Capability: capability.String, Action: ActionDelete, Resource: resource.String, Ref: &ref,
		Cause: cause, Attempts: &n})
	if err != nil {
		return 0, false, err
	}
	if err := tx.Commit(); err != nil {
		return 0, false, fmt.Errorf("ledger: commit reap: %w", err)
	}
	return id, true, nil
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
	var cost, ref, attempts any
	if r.CostCents != nil {
		cost = *r.CostCents
	}
	if r.Ref != nil {
		ref = *r.Ref
	}
	if r.Attempts != nil {
		attempts = *r.Attempts
	}
	res, err := e.Exec(insertRow, formatTime(r.At), r.Outcome, r.Grant, r.Session,
		nullable(r.Capability), nullable(r.Action), nullable(r.Resource), cost, expires,
		nullable(r.Undo), nullable(r.LimitName), nullable(r.Allowed), nullable(r.Needed),
		ref, nullable(r.Agent), nullable(r.Cause), attempts, nullable(r.Host))
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
