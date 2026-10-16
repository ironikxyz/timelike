package ledger

import (
	"database/sql"
	"errors"
	"fmt"
	"strconv"
)

// SchemaVersion is the ledger schema this package writes and reads. Schema 2 (slice 1) adds the reaper's
// outcomes and the columns ref, agent, cause, attempts and host (spec FR-30).
const SchemaVersion = 2

// ledgerTable is the ledger's table at schema 2, created under the name given. "grant" is an SQL keyword,
// so it is quoted.
const ledgerTable = `
CREATE TABLE %s (
	id          INTEGER PRIMARY KEY AUTOINCREMENT,
	at          TEXT    NOT NULL,
	outcome     TEXT    NOT NULL CHECK (outcome IN
	                ('performed', 'refused', 'extended', 'reaped', 'gone', 'reap-failed')),
	"grant"     TEXT    NOT NULL,
	session     TEXT    NOT NULL,
	capability  TEXT,
	action      TEXT,
	resource    TEXT,
	cost_cents  INTEGER,
	expires_at  TEXT,
	undo        TEXT,
	limit_name  TEXT,
	allowed     TEXT,
	needed      TEXT,
	ref         INTEGER,
	agent       TEXT,
	cause       TEXT,
	attempts    INTEGER,
	host        TEXT,
	extend      TEXT
);`

const schemaRest = `
CREATE INDEX IF NOT EXISTS ledger_grant_outcome ON ledger ("grant", outcome);
CREATE INDEX IF NOT EXISTS ledger_ref ON ledger (ref);
CREATE TABLE IF NOT EXISTS extensions (
	id          INTEGER PRIMARY KEY AUTOINCREMENT,
	"grant"     TEXT NOT NULL,
	limit_name  TEXT NOT NULL,
	value       TEXT NOT NULL,
	at          TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS meta (
	key   TEXT PRIMARY KEY,
	value TEXT NOT NULL
);
`

// v1Columns are the columns schema 1 had, copied row for row (and id for id) into schema 2.
const v1Columns = `id, at, outcome, "grant", session, capability, action, resource, cost_cents,
	expires_at, undo, limit_name, allowed, needed`

// ErrNewerSchema is returned by Open for a ledger written by a newer Adele.
var ErrNewerSchema = errors.New("ledger: schema is newer than this Adele understands")

// migrate checks the stored schema version, creates schema 2 when the file is new and upgrades a schema-1
// file in place. It runs in one (immediate) transaction, so two processes opening a file at once cannot
// both create or upgrade it half-way, and a reader never sees half an upgrade (spec D-13).
func migrate(db *sql.DB) error {
	tx, err := db.Begin()
	if err != nil {
		return fmt.Errorf("ledger: begin schema transaction: %w", err)
	}
	defer tx.Rollback() //nolint:errcheck // a no-op after Commit

	version, err := storedVersion(tx)
	if err != nil {
		return err
	}
	if version > SchemaVersion {
		return fmt.Errorf("%w: file has schema_version %d, this build reads %d — run a newer adeled",
			ErrNewerSchema, version, SchemaVersion)
	}
	switch version {
	case 0:
		if err := createFresh(tx); err != nil {
			return err
		}
	case 1:
		if err := upgradeV1(tx); err != nil {
			return err
		}
	}
	if _, err := tx.Exec(schemaRest); err != nil {
		return fmt.Errorf("ledger: create schema: %w", err)
	}
	if version != SchemaVersion {
		if _, err := tx.Exec(`INSERT INTO meta (key, value) VALUES ('schema_version', ?)
			ON CONFLICT (key) DO UPDATE SET value = excluded.value`, strconv.Itoa(SchemaVersion)); err != nil {
			return fmt.Errorf("ledger: record schema version: %w", err)
		}
	}
	if err := tx.Commit(); err != nil {
		return fmt.Errorf("ledger: commit schema: %w", err)
	}
	return nil
}

// createFresh makes schema 2's ledger table, unless a table of that name exists already: a file whose meta
// table lost its version (adopted at version 0) keeps its rows, and is upgraded if it has schema 1's shape.
func createFresh(tx *sql.Tx) error {
	exists, err := tableExists(tx, "ledger")
	if err != nil {
		return err
	}
	if !exists {
		if _, err := tx.Exec(fmt.Sprintf(ledgerTable, "ledger")); err != nil {
			return fmt.Errorf("ledger: create schema: %w", err)
		}
		return nil
	}
	hasRef, err := columnExists(tx, "ledger", "ref")
	if err != nil {
		return err
	}
	if hasRef {
		return nil
	}
	return upgradeV1(tx)
}

// upgradeV1 rebuilds the ledger table at schema 2: SQLite cannot change a CHECK constraint in place. Every
// row is copied with its id, then the old table is dropped and the new one takes its name (and its
// AUTOINCREMENT sequence, which RENAME carries).
func upgradeV1(tx *sql.Tx) error {
	steps := []string{
		fmt.Sprintf(ledgerTable, "ledger_v2"),
		`INSERT INTO ledger_v2 (` + v1Columns + `) SELECT ` + v1Columns + ` FROM ledger ORDER BY id`,
		`DROP INDEX IF EXISTS ledger_grant_outcome`,
		`DROP TABLE ledger`,
		`ALTER TABLE ledger_v2 RENAME TO ledger`,
	}
	for _, s := range steps {
		if _, err := tx.Exec(s); err != nil {
			return fmt.Errorf("ledger: upgrade schema 1 to 2: %w", err)
		}
	}
	return nil
}

func tableExists(tx *sql.Tx, name string) (bool, error) {
	var n int
	if err := tx.QueryRow(`SELECT count(*) FROM sqlite_master WHERE type = 'table' AND name = ?`, name).
		Scan(&n); err != nil {
		return false, fmt.Errorf("ledger: read schema: %w", err)
	}
	return n > 0, nil
}

func columnExists(tx *sql.Tx, table, column string) (bool, error) {
	var n int
	if err := tx.QueryRow(`SELECT count(*) FROM pragma_table_info(?) WHERE name = ?`, table, column).
		Scan(&n); err != nil {
		return false, fmt.Errorf("ledger: read schema: %w", err)
	}
	return n > 0, nil
}

// storedVersion returns the file's schema_version, or 0 for a file with no
// meta table or no recorded version (a new file).
func storedVersion(tx *sql.Tx) (int, error) {
	n, err := tableExists(tx, "meta")
	if err != nil {
		return 0, err
	}
	if !n {
		return 0, nil
	}
	var v string
	err = tx.QueryRow(`SELECT value FROM meta WHERE key = 'schema_version'`).Scan(&v)
	if errors.Is(err, sql.ErrNoRows) {
		return 0, nil
	}
	if err != nil {
		return 0, fmt.Errorf("ledger: read schema_version: %w", err)
	}
	version, err := strconv.Atoi(v)
	if err != nil || version < 1 {
		return 0, fmt.Errorf("ledger: schema_version %q is not a positive integer", v)
	}
	return version, nil
}
