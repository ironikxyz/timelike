# Modification: Feature 006 — Bounded read and search (`view`, `search`)

Append-only: one section per modify cycle.

---

## Cycle 2 — `bridge/sends/05-rev1-20261004-183704.md`

**Status:** Active | **Created:** 2026-10-04 | **Impact analysis:** `impact-analysis.md` § Cycle 2 |
**Spec:** `spec.md` § Slice 1 | **Contract:** `contracts/view-search-cli.md` § Slice 1

### Summary

Build slice 1 (natural): the budgeted directory overview (`view DIR`), the viewer's anchor mode
(`view --anchors`), and the three items carried from slice 0. Row 4: nothing to audit.

### Functional changes

- **F001: the overview** (spec FR-24 to FR-31). `view DIR` lists the tree within rule 3's line budget,
  directories first. Ignore files are respected, through `search`'s rules. It collapses version-control,
  dependency, build, ignored and over-budget directories, each to one line with counts and
  `expand: view DIR/`. **Breaking:** the slice-0 refusal of a directory (exit 2) is gone. Declared.
- **F002: anchors** (FR-32 to FR-35). `view --anchors` puts a 6-hex SHA-256 anchor of each line's raw
  bytes between the marker and the text. JSON carries `anchors: ["N:hhhhhh"]`. **Breaking:** no.
- **F003: carried** (FR-36 to FR-38). `search`'s verdict plurals; a measured search speed in the image;
  e2e for a window ending at the file's end. **Breaking:** no; the plural is a verdict wording.

### Data model changes

The overview's JSON fields (data-model § Slice 1). `anchors` is in a window's JSON. Nothing is stored.

### API/contract changes

`view DIR` (a new mode); `--anchors` (a new flag); search verdict wording (`1 file`, `1 match`).

### Testing strategy

- **Regression:** `test_view.py`, `test_search.py`, the five slice-0 e2e files.
- **New units:** written from the contract by a delegate.
- **New e2e:**
  - `view-directory-overview-dependency-directory-collapsed-within-budget.bats`;
  - `view-anchor-mode-short-stable-anchor-changes-with-content.bats`;
  - `view-and-search-slice-1-carried-items.bats`.

### Tech stack compliance

Compliant: stdlib only.

### Steps 7–8 of `/specswarm:modify`

These steps are not run here. `/specswarm:plan`, `/specswarm:tasks` and `/specswarm:implement
--dispatch` follow, as the dispatch sequence prescribes. `tasks.md` gains an appended phase.
