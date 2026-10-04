# Tasks: 006 Bounded read and search — `view` and `search` (prompt 05, slice 0)

<!-- Tech Stack Validation: PASSED -->
<!-- Validated against: .specswarm/tech-stack.md v1.3.1 via lib/tech-stack-parser.sh (2.35.0) -->
<!-- No prohibited technologies found -->
<!-- 0 unapproved technologies require runtime validation -->

**Input:** `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/view-search-cli.md`.
**Tests are required** (constitution H7). Each criterion is one e2e file named after its text, plus units.
Delegates working on their own files write the tests from the CLI contract **before** the tools exist
(the 003 and 005 practice). The tools are written here.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: US1 window (SC-1) · US2 range, context, missing, binary (SC-2) · US3 the search cap
  (SC-3) · US4 zero and strict (SC-4) · US5 names, conform, announcement (FR-23)

## Phase 1: Setup

- [X] T001 [P] Fixture `tests/e2e/fixtures/bounded-read.sh DIR`. It is `sh`-compatible and builds its
  content with `seq`, `printf` and `awk` only, never with the tools (P005):
  - `DIR/big.txt`: exactly 412 lines, each distinct (`line NNN: …`);
  - `DIR/small.txt`: 100 lines;
  - `DIR/long.txt`: one line of 5000 bytes between two short lines;
  - `DIR/app.bin`: an ELF header, then NULs; `DIR/pic.png`: a PNG header, then NULs;
  - `DIR/latin1.txt`: invalid UTF-8; `DIR/escapes.txt`: two lines carrying terminal escapes;
  - `DIR/repo/`: a real git repository made **with git**: `.gitignore` ignoring `build/` and `*.log`,
    and the token `needle_fn` exactly 262 times outside ignored paths (`src/engine/` 148,
    `src/cli.py` 40, `tests/` 44, `docs/` 30), plus 25 in `build/out.txt` and 5 in `app.log` (ignored);
    a committed and an untracked file each carrying some; a file in `.git/` carrying it (never searched).
  The counts are asserted inside the script with `grep -c`, so a fixture that drifts fails at build time.
- [X] T002 [P] `pyproject.toml`: ruff `extend-include` and mypy `files` gain `tools/bin/view` and
  `tools/bin/search`. `Makefile` `SHELLCHECK_FILES` gains the fixture and the e2e files of T003–T007.

## Phase 2: Tests from the contract (delegated, before the tools)

- [X] T003 [P] [US1] `tests/e2e/view-412-line-file-shows-lines-1-120-with-header-and-next-range.bats`
  (SC-1): exact lines 1–120 against the fixture, right alignment, the header scope, `more:` and its
  result (lines 121–240), the omission line's counts computed by the test, and a whole-file view (no
  omission line). `bash -c` and `bash -lc`.
- [X] T004 [P] [US2] `tests/e2e/view-range-context-missing-file-and-binary.bats` (SC-2): `:40-80`, `:40`
  (30–50, `>` on 40), missing (exit 3, `do instead:`), ELF and PNG (type and size, no content bytes).
- [X] T005 [P] [US3] `tests/e2e/search-262-matches-shows-50-grouped-with-212-omitted-and-narrowing.bats`
  (SC-3): 50 hits grouped by file, 262 and 212 stated, ignored matches not counted, `.git` never
  searched, the `narrow:` command returning fewer matches when run, and `more:` printing exactly the
  212 omitted hits.
- [X] T006 [P] [US4] `tests/e2e/search-zero-matches-exits-0-and-1-only-in-strict-mode.bats` (SC-4).
- [X] T007 [P] [US5] `tests/e2e/view-and-search-resolve-once-and-pass-conform.bats`: `type -a view` and
  `type -a search` each give exactly `/opt/timelike/bin/…`; `timelike-conform` passes on both; `timelike`'s
  tool list names both.
- [X] T008 [P] [US1, US2] `tests/unit/test_view.py`, from the contract: window rules, the colon split,
  clipping and usage errors, the cut's figures and `more:` (including a window ending at the file's end),
  JSON `next == truncated.more`, binary types, an empty file, decoding and escape counts, the event.
- [X] T009 [P] [US3, US4] `tests/unit/test_search.py`, from the contract: the gitignore matcher's rules
  (negation, anchoring, `**`, directory-only, nested files, `info/exclude`, `--no-ignore`), grouping and
  order, the cap and `-m`, the narrowing choice, the saved list and `more:`, zero and strict, the time
  limit (exit 124), large and binary skips, `-i` and `-F`, a bad pattern, a missing path.

## Phase 3: User Stories 1 and 2 — `view`

- [X] T010 [US1, US2] `tools/bin/view` on agentio (contract § view): resolution, the window rules,
  the line layout with the marker column (room for slice 1's anchor), the `Cut` with the file as full
  output and the next window as `more:`, binary by NUL plus magic type, decoding counts, verdicts as
  outcomes.

## Phase 4: User Stories 3 and 4 — `search`

- [X] T011 [US3, US4] `tools/bin/search` on agentio (contract § search): the walk (`.git` never,
  symlinks not followed), the stdlib gitignore matcher (research R2), `re` with `-i`, `-F` and a compile
  error as usage, grouping, the cap with a `Cut`, the `narrow:` line, the saved hit list and its `sed`
  `more:`, zero and `--strict`, the time limit, large and binary skips.

## Phase 5: Integration

- [X] T012 Units T008 and T009 against the tools. A disagreement is decided by the contract; where the
  contract is wrong or silent, the contract is amended and the amendment recorded.
- [X] T013 The e2e files through the host docker stand-in (advisory), and each fixture command run through
  the real tools on the host.

## Phase 6: Polish

- [X] T014 [P] `README.md`: a "view and search" section next to `snapshot and undo` (P3).
- [X] T015 FR-7, answered by **discovery revision 12** (re-send `05-rev1-20261004-085517`; this line was
  "HELD for Q3" until then): rule 13's line cut in JSON, in `tools/agentio/agentio.py` (`cut_lines`, and
  `Result.footer` so a tool's closing commands are never cut); 001's
  `contracts/output-contract.md` gains the both-modes sentence; spec FR-7 amended and D-12; the contract's
  long-lines section; 005's `tests/unit/test_snapshot.py` outcome helper expects the cut remedy line.
- [X] T016 Host lane: ruff, mypy, shellcheck, `make test-host`, coverage for the two tools. The cycle
  report § Cycle 1 (the send's block), implement step 10 as the plugin reports it, metrics entry.

## Dependencies

- T001 and T002 first (both [P]).
- T003–T009 need only the contract and T001, and run in parallel (delegated).
- T010 and T011 are independent (different files).
- T012 needs T008–T011. T013 needs T003–T007, T010 and T011. T014 any time after T011. T015 waits for Q3.
  T016 is last.

## Parallel opportunities

- **Delegate A:** T001, T003–T007 (the fixture and the e2e files).
- **Delegate B:** T008 and T009 (the units).
- **This instance:** T002, then T010 and T011, at the same time as both delegates.

## Implementation strategy

The tests come first, from the contract, written by delegates who do not see the code. The tools are
written against the contract alone. T012 and T013 reconcile the two, and the contract decides every
disagreement. MVP is US1 (`view`'s window); each later story is its own increment.

---

## Phase 6: Cycle 2 — slice 1: the overview, anchors, carried items (send `bridge/sends/05-rev1-20261004-183704.md`, via `/specswarm:modify`, `--dispatch`)

<!-- Tech Stack Validation (Cycle 2): PASSED — plan § Tech Stack Compliance Report (Cycle 2): stdlib only, none added -->

**Input:** spec § Slice 1, plan § Cycle 2, contracts/view-search-cli.md § Slice 1, research R7–R10.
**Tests are required** (H7). Same conventions as Cycle 1, with these additions: `implement --dispatch`
commits per task, and the scope is the files each task names.

**Story map:** US6 overview (SC-6, SC-8 D14) · US7 anchors (SC-7) · US8 carried (FR-36 to FR-38).

### Tests first (from the contract; delegated, disjoint files)

- [ ] T017 [P] [US6] [US7] [US8] `tests/unit/test_view_slice1.py`:
  - the overview: order, indentation, sizes, symlinks, ignore rules, the five collapse kinds, the
    breadth-first fit, the 100,000 cap (patched lower), the verdict clauses, JSON, `--no-ignore`,
    `--limit 0`, the over-budget cut, a missing directory;
  - anchors: equal to the test's own sha256 prefixes, stable, unchanged by insertions above, changed by
    an edit, CRLF and LF agree, JSON `anchors`, `--anchors` kept in `next`/`more`, refused on a
    directory;
  - the search plurals.
- [ ] T018 [P] [US6] [US7] [US8] e2e, each under `bash -c` and `bash -lc`:
  - `tests/e2e/view-directory-overview-dependency-directory-collapsed-within-budget.bats` (SC-6);
  - `tests/e2e/view-anchor-mode-short-stable-anchor-changes-with-content.bats` (SC-7);
  - `tests/e2e/view-and-search-slice-1-carried-items.bats` (a window ending at the end, the plural,
    search speed measured).

### Implementation

- [X] T019 [US6] `tools/bin/view`: `view DIR`, the overview (FR-24 to FR-31); the slice-0 units or e2e
  cells that asserted the directory refusal are updated in `tests/unit/test_view.py` and
  `tests/e2e/view-range-context-missing-file-and-binary.bats` if they assert it.
- [X] T020 [US7] `tools/bin/view`: `--anchors` (FR-32 to FR-35).
- [X] T021 [US8] `tools/bin/search`: the verdict's plurals (FR-36); `tests/unit/test_search.py` where an
  expectation names a plural.
- [X] T022 `README.md`: the `view` section gains the overview and anchors.

### Polish

- [ ] T023 Host lane: lint, units with coverage, `make test-host`, `view --help` start-up. Results in
  `decisions.md`.
- [ ] T024 `cycle-report.md` § Cycle 2, implement step 10, `.specswarm/metrics.json`, the marker.

### Dependencies (Cycle 2)

- T019 → T020 (one file) → T021 → T022 → T023 → T024.
- T017 and T018 depend only on the contract, and run beside T019–T021.
