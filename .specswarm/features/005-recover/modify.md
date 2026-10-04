# Modification: Feature 005 — Recover (snapshots and undo)

Append-only: one section per modify cycle.

---

## Cycle 2 — `bridge/sends/07-rev11-20261004-030207.md`

**Status:** Active | **Created:** 2026-10-04 | **Impact analysis:** `impact-analysis.md` § Cycle 2

### Summary

Record discovery revision 11 against slice 0 (UNAUDITED, not superseded), and meet plan's four
conditions on the store. Two hold as built; two are built here. Governance was audited to revision 11
on `master` (`586e298`) and merged in (`fc5b97d`), with the operator-accepted CVE-2026-95619 baselines
(`f33c806`).

### Functional changes

**F001: the size cap counts bytes new to the store** (condition 3; FR-6)
- **Current:** the cap is compared with the sum of every candidate file's size.
- **Proposed:** the cap is compared with the bytes this snapshot would add to the store. Content already
  stored costs nothing, and content repeated within the snapshot counts once. When even the plain sizes
  fit, nothing is hashed twice. Over the cap, the largest new content is left out first (ties by path),
  and files sharing one content are left out together. The raise line names the content new to the store.
- **Breaking:** no.

**F002: "taken" only after a restorability check** (condition 4; FR-9; stack note 12)
- **Current:** "taken" follows the record write.
- **Proposed:** after the write, the record is read back and compared. Every entry path must be one a
  restore may write, and every object it names must be a regular file of the recorded size whose sha256
  is its name. On failure, no record stays, a damaged object is removed (so the next snapshot stores it
  again rather than trusting it), and the verdict says `not taken` and why (exit 1). The same check
  guards `undo --yes`'s safety snapshot: if it fails, nothing is applied.
- **Breaking:** no (a new outcome, within the existing exit codes).

**F003: revision 11 recorded** (spec § Revision 11, D-5, D-7)
- The constraint is recorded verbatim, with its slice-0 part shown true as built. The two slice-1
  criteria are carried, not built. D-5 and D-7 are "confirmed by discovery revision 11". FOR-MENTOR
  Item 17 is closed.

### Data model changes

**D001:** the record gains `stored_bytes` (int) and, when the size cap was applied, `size_cap_needed`
(int). `v` stays 1, and readers require neither field. No migration.

### API/contract changes

**A001:** `snapshot --json` `data` gains `stored_bytes` and `verified` (true). There is a new outcome:
`snapshot <id> not taken: it could not be verified restorable: <what>` (exit 1). `undo --yes` gains
`restore of snapshot <id> not started: …` (exit 1). The verdict lines are unchanged.

### Testing strategy

- **Regression:** `tests/unit/test_snapshot.py`, `test_undo.py`, the five 005 e2e files, `make test-host`.
- **New units (6):** a repeated snapshot adds no stored bytes (measured on disk); the cap ignores
  already-stored content; content repeated within a snapshot counts once; shared content is left out
  together, largest first; a planted damaged object is caught (not taken, removed, the next snapshot
  succeeds); a damaged object under undo's safety snapshot stops the restore before any change.
- **The mentor's Docker lane** re-establishes slice 0's criteria in the image (`make test`, `make scan`
  on all four images with the new baselines).

### Tech stack compliance

Compliant: stdlib Python only. No change to `tech-stack.md` from this modification (the git note was
amended at the governance audit).
