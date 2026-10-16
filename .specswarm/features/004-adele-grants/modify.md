# Modification: Feature 004 — Adele & grants

Append-only: one section per modify cycle.

---

## Cycle 3 — `bridge/sends/12-rev2-20261016-091249.md` (slice 1, natural)

**Status:** Active | **Created:** 2026-10-16 | **Impact analysis:** `impact-analysis.md` § Cycle 3

### Summary

Slice 1 of prompt 12: Adele's reaper and its record, the denial record and `status` (its source waits on
FOR-MENTOR Item 26), the agent's name on ledger rows, Item 14 (b)'s human line on stderr (plan: a
clarification), and agentio's guard. The requirements are spec § Slice 1, FR-24 to FR-42.

### Functional changes
- **F001 the reaper** (FR-24–FR-29): a pass at start and every interval; same-box check; read-back outcome;
  bounded retries and give-up; `adeled reap`.
- **F002 status** (FR-35–FR-37): `adele status [HOST]`, `adeled status [HOST]`, `GET /v1/denials`.
- **F003 attribution** (FR-32, FR-33).
- **F004 the human line** (FR-38–FR-40).
- **F005 the guard** (FR-41).
- **F006 stand-in faults** (FR-42).

### Data model changes
- **D001 ledger schema 2** (FR-30): outcomes `reaped`, `gone`, `reap-failed`; columns `ref`, `agent`, `cause`,
  `attempts`, `host`. Migration on open, by rebuild, id-preserving.

### API/contract changes
- **A001** `POST /v1/requests` accepts optional `agent`. **A002** `GET /v1/denials[?host=H]`. **A003** `adeled
  ledger --json` adds five keys. **A004** agentio exit 4 in text mode writes one stderr line (001's contract,
  one sentence). **A005** `adele status` gains `denials` in its data; existing keys unchanged.

### Backward compatibility
All additive. A schema-1 ledger is migrated; the agent's default (piped, JSON) output is byte-identical.

### Testing strategy
Go units per outcome and for the migration; pytest for agentio's line, the guard, the client and the journal;
bats: one file per criterion (reap: spread; restart and unreachable: serial), named after its text.
