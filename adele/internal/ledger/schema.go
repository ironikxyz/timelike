package ledger

import (
	"database/sql"
	"errors"
	"fmt"
	"strconv"
)

// SchemaVersion is the ledger schema this package writes and reads.
const SchemaVersion = 1

// schemaV1 is created when absent. "grant" is an SQL keyword, so it is quoted.
const schemaV1 = `
CREATE TABLE IF NOT EXISTS ledger (
	id          INTEGER PRIMARY KEY AUTOINCREMENT,
	at          TEXT    NOT NULL,
	outcome     TEXT    NOT NULL CHECK (outcome IN ('performed', 'refused', 'extended')),
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
	needed      TEXT
);
CREATE INDEX IF NOT EXISTS ledger_grant_outcome ON ledger ("grant", outcome);
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

// ErrNewerSchema is returned by Open for a ledger written by a newer Adele.
var ErrNewerSchema = errors.New("ledger: schema is newer than this Adele understands")

// migrate checks the stored schema version and creates schema v1 when the
// file is new. It runs in one (immediate) transaction so that two processes
// opening a fresh file at once cannot both create it half-way.
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
	if _, err := tx.Exec(schemaV1); err != nil {
		return fmt.Errorf("ledger: create schema: %w", err)
	}
	if version == 0 {
		if _, err := tx.Exec(`INSERT INTO meta (key, value) VALUES ('schema_version', ?)`,
			strconv.Itoa(SchemaVersion)); err != nil {
			return fmt.Errorf("ledger: record schema version: %w", err)
		}
	}
	if err := tx.Commit(); err != nil {
		return fmt.Errorf("ledger: commit schema: %w", err)
	}
	return nil
}

// storedVersion returns the file's schema_version, or 0 for a file with no
// meta table or no recorded version (a new file).
func storedVersion(tx *sql.Tx) (int, error) {
	var n int
	err := tx.QueryRow(`SELECT count(*) FROM sqlite_master WHERE type = 'table' AND name = 'meta'`).Scan(&n)
	if err != nil {
		return 0, fmt.Errorf("ledger: read schema: %w", err)
	}
	if n == 0 {
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
