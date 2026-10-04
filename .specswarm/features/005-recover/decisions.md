# Decisions Log — Feature 005
> Generated at 2026-10-03T01:59:45+00:00
> Spec: .specswarm/features/005-recover/spec.md

## Decision Key

| Tag | Meaning |
|-----|---------|
| ASSUMED | Assumption made without explicit spec guidance (confidence: high/medium/low) |
| DEFERRED | Decision postponed — noted for later resolution |
| FLAGGED | Judgment call between alternatives — requires review |
| ABSENT | What was NOT done and why — forced reflection on gaps |
| INHERITED | Assumption carried forward from a prior task's output |

---

### T001: fixture tests/e2e/fixtures/recover-repo.sh — a real repository built by git (delegate A)
**Started:** 2026-10-03T02:00+00:00 (delegated) | **Completed:** 2026-10-03T02:12:44+00:00

INHERITED: (none — first task)
ASSUMED: written by a general-purpose delegate from the contract and tasks.md alone, never seeing the tools; reviewed here (confidence: high)
ASSUMED: rmsrc.sh is tracked, mode 0755; the pre-commit hook is installed after the last commit and writes DIR/../hook-ran, so a marker can only come from something else running it (delegate's choice, kept) (confidence: high)
FLAGGED: none
ABSENT: no hand-written .git content anywhere (P005); no socket or device files (units cover the FIFO; the agent cannot make devices)
Verification: bash -n and dash -n pass; run on the host inside the T013 stand-in: builds the expected tree; two .git manifests in a row byte-identical; shellcheck 0.11.0 clean after one intentional SC2016 (the script's own text) was marked with its reason
SCOPE: in (1 changed files)

### T003: e2e SC-1 — snapshot-records-tracked-untracked-and-ignored-files.bats (delegate A)
**Started:** 2026-10-03T02:00+00:00 (delegated) | **Completed:** 2026-10-03T02:12:44+00:00

INHERITED: T001's fixture; the contract's JSON fields and verdict form (confidence: high)
ASSUMED: counts compared with find over the workspace with every .git pruned; restore of one tracked, one untracked and one ignored file checked by sha256 and the full manifest, never by the tool's message (P004) (confidence: high)
FLAGGED: none
ABSENT: not run in the image here (no Docker, R10): the Docker lane decides; the host stand-in (T013) is advisory
Verification: host stand-in (T013): 4/4
SCOPE: in (1 changed files)

### T004: e2e SC-2 — restore-returns-captured-content-and-removes-files-created-after.bats (delegate A)
**Started:** 2026-10-03T02:00+00:00 (delegated) | **Completed:** 2026-10-03T02:12:44+00:00

INHERITED: T001's fixture; data-model's plan rows (confidence: high)
ASSUMED: the dry-run plan must equal the test's own list of the five changes it made, as a sequence (sorted by path, remove before restore) (confidence: high)
FLAGGED: review fix — check_envelope read the envelope's confirm through $JPY after a later jpy call had replaced it, so it ran "<absent>"; re-reads it first (a test bug, found by the T013 host stand-in) (confidence: high)
FLAGGED: review change — after a restore, a bare repeated "undo --yes" must change nothing (was "undo 1 --yes"), pinning the amended default (FR-14; T012) (confidence: high)
ABSENT: the verification-failure path (exit 1, "left N differences") is not reachable without a fault hook; not tested end to end
Verification: host stand-in (T013): 10/10 after the fixes
SCOPE: in (1 changed files)

### T005: e2e SC-3 — version-control-history-index-and-stash-unchanged-by-snapshot-and-restore.bats (delegate A)
**Started:** 2026-10-03T02:00+00:00 (delegated) | **Completed:** 2026-10-03T02:12:44+00:00

INHERITED: T001's fixture (commits, staged change, stash, repository hook, nested repository) (confidence: high)
ASSUMED: the .git manifest covers every entry under every .git (path, mode, sha256) plus git log, stash list and diff --cached, read with GIT_OPTIONAL_LOCKS=0 so the reading itself cannot touch the index (confidence: high)
FLAGGED: none
ABSENT: on the host the image's hook dispatcher and /etc/gitconfig are absent; the hook-never-ran assertion is only meaningful in the image
Verification: host stand-in (T013): 4/4
SCOPE: in (1 changed files)

### T006: e2e SC-4 — snapshot-over-the-size-cap-is-partial-and-names-what-was-excluded.bats (delegate A)
**Started:** 2026-10-03T02:00+00:00 (delegated) | **Completed:** 2026-10-03T02:12:44+00:00

INHERITED: T001's fixture plus two large files the test writes (confidence: high)
ASSUMED: the size-cap raise value is the total of all files (what would have captured everything); the per-file raise value is the largest file (confidence: medium)
FLAGGED: review fix — size_matches runs its own =~, which clobbered BASH_REMATCH before the second size was read; the groups are kept in locals first (a test bug, found by the T013 host stand-in) (confidence: high)
ABSENT: unreadable-file and special-file exclusions are covered by units only (the agent cannot make devices; a 000 file is a unit)
Verification: host stand-in (T013): 10/10 after the fix
SCOPE: in (1 changed files)

### T007: e2e FR-2 and R7 — snapshot-refuses-home-root-and-their-ancestors.bats (delegate A)
**Started:** 2026-10-03T02:00+00:00 (delegated) | **Completed:** 2026-10-03T02:12:44+00:00

INHERITED: the amended contract: refusals are verdicts on stdout with "do instead:" (T012) (confidence: high)
ASSUMED: nothing is stored on a refusal, checked by listing the store directory (confidence: high)
FLAGGED: none
ABSENT: the type -a cells can only pass in the image (they pin /opt/timelike/bin); on the host stand-in they fail by construction
Verification: host stand-in (T013): 12/16, the 4 failures being exactly the type -a cells; shellcheck clean after an unused local was removed
SCOPE: in (1 changed files)

### T008: units tests/unit/test_snapshot.py and tests/unit/test_undo.py (delegate B)
**Started:** 2026-10-03T02:00+00:00 (delegated) | **Completed:** 2026-10-03T02:12:44+00:00

INHERITED: conftest's subprocess conventions; test_conform.install for the conform run (both tools in one bindir); test_adele_cli's load_conform pattern (confidence: high)
ASSUMED: written from the contract alone by a general-purpose delegate, then run against the tools: 70 of 71 passed first time; the one failure was the tool's wording against the contract, and the tool was changed (T012) (confidence: high)
FLAGGED: review addition — test_a_repeated_undo_yes_changes_nothing_the_default_skips_safety_snapshots pins the amended default (FR-14; T012) (confidence: high)
ABSENT: no slow marker on the two 10 s lock tests (none is registered in pyproject; adding one is outside these files); the verification-failure path needs a fault hook and is not tested
Verification: 72 passed (test_snapshot.py + test_undo.py, venv pytest 8.4.2, Python 3.12.3); ruff and ruff format clean after line-length and B904 fixes
SCOPE: in (2 changed files)

### T009 and T010: tools/bin/snapshot — workspace, store, walk, exclusions, take and list; planner, apply, verify
**Started:** 2026-10-03T02:05+00:00 | **Completed:** 2026-10-03T02:12:44+00:00

INHERITED: spec D-1 to D-10, research R1–R8, data-model, contracts/recover-cli.md (confidence: high)
ASSUMED: T009 and T010 are one file and were written as one; they are committed together and both ticked by this commit (confidence: high)
FLAGGED: refusals, a missing snapshot and a failed verification are verdicts on stdout (an Outcome result, exit 1 or 3), not stderr errors — chose this over the contract's first wording because timelike-conform's probes run in conform's own directory (the home directory in the image), and C3/C4 need a header on stdout; adele status is the precedent. Contract amended (T012) (confidence: high)
FLAGGED: the default restore target skips safety snapshots ("before undo …") — chose this over "the newest of all" because a second bare undo --yes would otherwise undo the first (rule 7, idempotent). Spec FR-14 and the contract amended (T012) (confidence: high)
ASSUMED: dir modes are set after everything inside them is written, deepest first, so a 0500 directory cannot block its own restore (confidence: high)
ABSENT: no restore of file times or owners (spec assumption 3); no fsync (a crash mid-restore is covered by the safety snapshot, not by durability); a directory whose mode forbids writing at restore time (changed after the snapshot) can still fail the restore, naming the path and the safety snapshot
Verification: ruff, ruff format, mypy strict clean; timelike-conform passes on both tools from a project directory and from the home directory; smoke and edge runs on the host (planted symlink at a parent path, planted .git, type changes, FIFO, unreadable file, size cap largest-first, per-file limit, entry cap, bad env value, unknown id); 72 units pass
SCOPE: in (1 changed files)

### T011: tools/bin/undo — loads snapshot from its own real directory and runs the undo command
**Started:** 2026-10-03T02:20+00:00 | **Completed:** 2026-10-03T02:12:44+00:00

INHERITED: T009–T010's UNDO_TOOL, undo_main and undo_configure (confidence: high)
ASSUMED: SourceFileLoader on the realpath of __file__, registered in sys.modules before exec (research R8) (confidence: high)
FLAGGED: none
ABSENT: no second copy of any logic in undo; nothing undo does is reachable except through snapshot's code
Verification: conform passes with both installed together (unit and host); a first conform attempt failed because the shebang rewrite kept -I (my install's error, not the tool's), recorded in the cycle report
SCOPE: in (1 changed files)

### T002: lint lists — pyproject.toml (ruff extend-include, mypy files) and Makefile SHELLCHECK_FILES
**Started:** 2026-10-03T02:05+00:00 | **Completed:** 2026-10-03T02:12:44+00:00

INHERITED: the two tool files (T009–T011) and the six e2e files (T001, T003–T007) the lists name (confidence: high)
ASSUMED: committed after the files exist, so no list names a missing file at any commit (confidence: high)
FLAGGED: none
ABSENT: no other Makefile change: e2e discovery is by directory, so make test runs the new bats files without being told
Verification: ruff check and ruff format --check clean over tools tests scan bench (54 files); mypy 2.4.0 strict "no issues found in 19 source files" (corrected in T015: first written as 2.3.1, the version an earlier venv had); shellcheck 0.11.0 clean over the extended SHELLCHECK_FILES
SCOPE: in (2 changed files)

### T012: reconcile the delegates' tests and the tools against the contract
**Started:** 2026-10-03T02:30+00:00 | **Completed:** 2026-10-03T02:12:44+00:00

INHERITED: T003–T011 (confidence: high)
ASSUMED: disagreements are decided by the contract; where the contract was wrong or silent, the contract is amended and the amendment is recorded in it (confidence: high)
FLAGGED: contract amended — "Outcomes are verdicts, errors are errors" (conform's probes); both delegates were told mid-task and wrote to it (confidence: high)
FLAGGED: spec FR-14 and contract amended — undo's default skips safety snapshots (rule 7); spec FR-7 and SC-4 amended — the entry-cap verdict names the cap, not a count, because the walk stops at the cap (confidence: high)
ASSUMED: the tool's store-refusal remedy changed to the contract's exact words (the one unit that failed) (confidence: high)
ABSENT: no change to any criterion text; spec D-1 to D-10 unchanged
Verification: 72 units pass; host stand-in 40/44 (the 4 being the image-only type -a cells)
SCOPE: none — no files outside the feature's artifacts changed

### T013: e2e on the host through a docker stand-in (advisory)
**Started:** 2026-10-03T02:35+00:00 | **Completed:** 2026-10-03T02:12:44+00:00

INHERITED: T001, T003–T007 and the tools (confidence: high)
ASSUMED: a scratchpad stand-in for docker (exec runs the command here with the test's -e variables, a stand-in HOME and the two tools on PATH; inspect answers stamp_check; run serves pyq with the host python) plus bats-core v1.14.0 (the pinned version) is a fair advisory check of the bats logic, not of the image (confidence: high)
FLAGGED: COLUMNS=1000 in the stand-in — chose it over leaving the six FR-2 cells failing because the host's scratchpad home path is long enough that the remedy line was cut at 200 columns; the image's /home/agent is not (confidence: medium)
ABSENT: nothing here is image evidence: no /etc/gitconfig layer, no hook dispatcher, host git 2.43 and Python 3.12; the stand-in is not committed (it lives in the scratchpad)
Verification: 44 tests: 40 ok; the 4 not-ok are the type -a cells, which pin /opt/timelike/bin; two test bugs found and fixed (T004, T006)
SCOPE: none — no files outside the feature's artifacts changed

### T014: README — "snapshot and undo — wrong turns are recoverable"
**Started:** 2026-10-03T02:25+00:00 | **Completed:** 2026-10-03T02:12:44+00:00

INHERITED: the contract as amended (default target, outcomes) (confidence: high)
ASSUMED: the README is where this project announces tools (003's decision, kept); timelike's tool list lists both automatically (confidence: high)
FLAGGED: none
ABSENT: no harness context file inside the image announces them (003's precedent: none exists yet)
Verification: the section's statements checked against the tool (defaults, variables, the default target, where snapshots live)
SCOPE: in (1 changed files)

### T015: host lane, coverage, implement step 10, cycle report § Cycle 1, metrics entry
**Started:** 2026-10-03T02:40+00:00 | **Completed:** 2026-10-03T02:16:55+00:00

INHERITED: T001–T014 and their verification (confidence: high)
ASSUMED: every criterion is unconfirmed until the Docker lane runs on this branch; the host lane and the host stand-in are advisory (as in 001 and 003) (confidence: high)
FLAGGED: none
ASSUMED: corrected two of my own records in place, each saying so: T002's mypy version (2.3.1 → 2.4.0, the venv's) and the recorded run_coverage exit (rc 0 → 1, re-measured) (confidence: high)
ABSENT: no Docker lane (R10); no ship or merge (they wait for the mentor's sign-off, and ship's D85 is its own field run); no demo_points_reached; no Group A (no marker on this path)
Verification: make test-host 889 passed, 60/60, 29/29; coverage 93% for the two tools; ruff, mypy, shellcheck clean; implement step 10 run from the installed 2.27.0 blocks (unknown, warned); all five criterion citations match one send line each
SCOPE: out — .specswarm/metrics.json (1 of 1 changed files) (task has FLAGGED: no)

### T016: the size cap counts bytes new to the store; "taken" after a restorability check (Cycle 2)
**Started:** 2026-10-04T03:09+00:00 | **Completed:** 2026-10-04T03:20+00:00

INHERITED: plan's conditions 3 and 4 (resolution Q1; `stack.md` note 12) via send 07-rev11-20261004-030207; conditions 1 and 2 checked as met by the existing code and units (confidence: high)
FLAGGED: the size cap's unit is now the content a snapshot adds to the store, so an over-the-cap snapshot is less partial when part of the workspace is already stored, and the raise line names the new content, not the workspace's whole size; contract, data model and spec FR-6 amended to say so, declared (confidence: high)
FLAGGED: files sharing one content are left out together, largest content first, ties by smallest path; leaving out one copy alone saves nothing (confidence: high)
FLAGGED: verification re-hashes every object a snapshot names (one read of its distinct content), not only the objects it wrote, because `put` trusts an object it finds in place; a damaged object is removed so the next snapshot stores it again (confidence: medium — the cost is one extra read per snapshot; measured in T019)
ASSUMED: the verdict lines stay byte-identical (the lane established them); `stored_bytes` and `verified` are JSON additions only (confidence: high)
ASSUMED: a failed verification is an Outcome (exit 1, `do instead:`), as the contract treats a failed restore verification; the record is deleted and its id stays used (FR-11) (confidence: high)
ASSUMED: undo's safety snapshot goes through the same check, and a failure there applies nothing — D-10's "an undo is undoable" depends on it (confidence: high)
ABSENT: no change to the walk, the plan, apply or the lock; no record version bump (readers require neither new field)
Verification: units 78 passed (72 + 6 new; 1 changed for the cap's unit); ruff, ruff format, mypy clean; the five 005 e2e files through the host stand-in 40/44 (the 4 being the image-only type -a cells, as in Cycle 1), SC-4's raise value 300000 included
SCOPE: in (5 changed files)
