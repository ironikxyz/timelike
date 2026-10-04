# Tasks: 005 Recover — snapshots and undo (prompt 07, slice 0)

<!-- Tech Stack Validation: PASSED -->
<!-- Validated against: .specswarm/tech-stack.md (no **Version** line) via lib/tech-stack-parser.sh -->
<!-- No prohibited technologies found -->
<!-- 0 unapproved technologies require runtime validation -->

**Input:** `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/recover-cli.md`.
**Tests are required** (constitution H7): each criterion is one e2e file named after its text, plus units.
Tests are written from the CLI contract **before** the tools exist (the 003 practice), by delegates
working on their own files. The tools are written here.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: US1 take (SC-1) · US2 restore (SC-2) · US3 git state (SC-3) · US4 caps (SC-4) ·
  US5 refusals and names (FR-2, R7)

## Phase 1: Setup

- [X] T001 [P] Fixture `tests/e2e/fixtures/recover-repo.sh`: builds a real repository **with git**
  inside the container as the agent (P005, R9). It has commits, a `.gitignore` with ignored files
  (`build/out.bin`, `*.log`), untracked files, a staged change, a `git stash`, a repository hook
  (`.git/hooks/pre-commit`), a nested repository (`vendor/lib` with its own `.git` and a file), a
  `0600` file, an executable script, a symlink, and a script `rmsrc.sh` that deletes `src/`.
  `sh`-compatible, with arguments `DIR`.
- [X] T002 [P] `pyproject.toml`: ruff `extend-include` and mypy `files` gain `tools/bin/snapshot` and
  `tools/bin/undo`. `Makefile` `SHELLCHECK_FILES` gains the fixture and the five bats files of
  T003–T007.

## Phase 2: Tests first (from `contracts/recover-cli.md`; delegated)

- [X] T003 [P] [US1] E2E `tests/e2e/snapshot-records-tracked-untracked-and-ignored-files.bats` (SC-1):
  in the fixture repository, `snapshot` exits 0. Its verdict names `snapshot 1`, a file count equal to
  `find` of the regular files outside any `.git`, and a size. After deleting one tracked, one untracked
  and one ignored file, `undo 1 --yes` brings each back byte-identical (`sha256sum`). `bash -c` and
  `bash -lc`, `notty`.
- [X] T004 [P] [US2] E2E `tests/e2e/restore-returns-captured-content-and-removes-files-created-after.bats`
  (SC-2):
  - after `rmsrc.sh` (a directory removed by a script), an edit, a `chmod`, a new file and a new
    directory, `undo --dry-run` lists exactly those changes (compared as a set with the test's own
    list) and changes nothing;
  - `undo` alone exits 4 with a `confirmation_required` envelope whose `confirm` ends in `--yes`;
  - `undo --yes` leaves a manifest (path, kind, mode, sha256 or link target, from `find` and
    `sha256sum` and `stat`) identical to the one taken before the changes;
  - a second `undo --yes` changes nothing and says so;
  - `undo 2 --yes` (the safety snapshot) brings the changed state back.
- [X] T005 [P] [US3] E2E
  `tests/e2e/version-control-history-index-and-stash-unchanged-by-snapshot-and-restore.bats` (SC-3):
  a manifest of `.git` (every path, mode and sha256, the nested repository's `.git` included) before
  `snapshot`, after it, and after `undo --yes`, all identical. `git stash list`, `git log` and
  `git diff --cached` are unchanged too. The repository's `pre-commit` hook writes a marker if it ever
  runs: there must be no marker.
- [X] T006 [P] [US4] E2E `tests/e2e/snapshot-over-the-size-cap-is-partial-and-names-what-was-excluded.bats`
  (SC-4):
  - with `TIMELIKE_SNAPSHOT_MAX_BYTES` below the workspace's size, `snapshot` says `(partial)` and
    names each excluded file with `over the size cap`, largest first, plus the raise line;
  - `TIMELIKE_SNAPSHOT_MAX_FILE_BYTES` names `over the per-file limit`;
  - after deleting a captured file, `undo --yes` restores it and leaves the excluded files untouched
    (same sha256);
  - `TIMELIKE_SNAPSHOT_MAX_ENTRIES=5` is refused, naming the count and the variable;
  - a non-integer value is exit 2.
- [X] T007 [P] [US5] E2E `tests/e2e/snapshot-refuses-home-root-and-their-ancestors.bats`:
  - `snapshot` from `~`, `/` and `/home` is refused (exit 1, the reason, "change into the project
    directory"), and nothing is written to the store;
  - `undo` there is refused the same way;
  - `type -a snapshot` and `type -a undo` each print exactly one line, under `/opt/timelike/bin`.
- [X] T008 [P] Units `tests/unit/test_snapshot.py` and `tests/unit/test_undo.py`, every FR of the spec
  against real repositories built by git in `tmp_path`, with tools run as subprocesses (`conftest.run`):
  - the workspace rules (FR-1 to FR-3, with `HOME` pointed into `tmp_path`);
  - capture of every kind, `.git` out of scope at any depth, the exclusions and their reasons, entry-cap
    refusal, identifiers, `list` (with `--verbose` times and without);
  - the plan's every row (data-model), dry-run, the envelope against the schema and C9's
    `check_envelope`, `--yes` with verification and the safety snapshot, the empty plan;
  - a symlink planted after the snapshot at a parent path (the restore must not write through it);
  - a `.git` planted after the snapshot (never removed);
  - the lock: the test holds it with `fcntl.flock` and expects exit 1 with the lock verdict after the
    10 s wait;
  - the Cut on `--yes` and on `take` (`more` is `sed`, never the tool);
  - the manifest flags (C2), `timelike-conform` passing on both (installed with `test_conform.install`),
    and one event per invocation.

## Phase 3: The tools

- [X] T009 [US1][US4][US5] `tools/bin/snapshot`: workspace resolution and refusals; the store (layout,
  key, lock, `next`, objects written by temp and rename, records); the walk (`.git` skipped, the entry
  cap); exclusions (per-file, special files, unreadable, the size cap's largest-first cut); `snapshot`
  and `snapshot list` per the contract, with `Cut` over the limit on `take`.
- [X] T010 [US2][US3] `tools/bin/snapshot`, continued: the planner, the apply (removals deepest first,
  directories, files and links by temp and rename with `O_NOFOLLOW`, every parent checked with `lstat`,
  `.git` refused by the helpers themselves), and the verify (re-walk, re-plan).
- [X] T011 [US2] `tools/bin/undo`: loads `snapshot` from its own real directory (R8); `undo [ID]`,
  `--dry-run`, the envelope (bounded plan), `--yes` with the safety snapshot, apply, verify, and `Cut`.

## Phase 4: Make the tests pass

- [X] T012 Run the units (T008) against T009–T011, and fix the tools until they pass. Review the
  delegates' tests against the contract: a test that disagrees with the contract is fixed in the test,
  and a contract gap is fixed in the contract and recorded.
- [X] T013 Run each e2e fixture and each bats file's container commands on the host, sandboxed
  (`setsid --wait timeout`), with `HOME` pointed at a temporary home and the tools on `PATH`, to catch
  what the image would.

## Phase 5: Polish

- [X] T014 [P] `README.md`: a "Snapshots and undo" section next to `run` and Adele: the two commands,
  `undo --yes` as the one undo command, the workspace rule, the caps and their variables, what survives
  a restart (P3).
- [X] T015 Host lane: ruff, mypy, shellcheck, `make test-host`, coverage for the two tools. The cycle
  report § Cycle 1 (the send's block), and implement step 10 as the plugin reports it.

## Dependencies

- T001 and T002 first (both [P]).
- T003–T008 need only the contract and T001, and run in parallel (delegated).
- T009 → T010 → T011 (one file, then the file that loads it).
- T012 needs T008–T011. T013 needs T003–T007 and T011. T014 can run any time after T011. T015 is last.

## Parallel opportunities

- **Delegate A:** T001, T003–T007 (the fixture and the e2e files).
- **Delegate B:** T008 (the units).
- **This instance:** T002, then T009–T011, at the same time as both delegates.

## Implementation strategy

The tests come first, from the contract, by delegates who do not see the code. The tools are written
against the contract alone. T012 and T013 reconcile the two, and any disagreement is decided by the
contract, not by whichever was written last. MVP is US1 + US2 (take and undo); US3–US5 are properties of
the same code, pinned by their own tests.

## Phase 6: Cycle 2 — revision 11 recorded; plan's store conditions (send `bridge/sends/07-rev11-20261004-030207.md`, via `/specswarm:modify`)

<!-- Tech Stack Validation (cycle 2): PASSED — plan.md § Tech Stack Compliance Report (Cycle 2) has no
conflict or prohibition; stdlib Python only -->

The governance audit to revision 11 and the CVE-2026-95619 baselines were done on `master` before this
phase (`586e298`, `f33c806`) and merged in (`fc5b97d`), as the send orders. They are recorded in the cycle
report, not as tasks here.

- [X] T016 [US4] `tools/bin/snapshot`: the size cap counts bytes new to the store, after deduplication
  (F001, FR-6), and "taken" follows a restorability check, applied to undo's safety snapshot too (F002,
  FR-9). Contract, data model, spec FR-6, FR-9 and FR-23 annotations, README. Units: 6 new, 1 changed;
  SC-4's e2e raise value.
- [X] T017 Spec § Revision 11 (the constraint, declared; two slice-1 criteria carried, not built), D-5
  and D-7 "confirmed by discovery revision 11", out-of-scope line. FOR-MENTOR Item 17 closed.
- [X] T018 Provenance (modify Step 9): a `none (deferred)` row in `audit-log.md`. The `full` append
  (2–11) waits for the mentor's Docker lane to re-establish slice 0 on this cycle's commit, as in 001
  cycles 5 and 6.
- [X] T019 Host lane (ruff, mypy, shellcheck, `make test-host`, coverage for `snapshot`), the e2e stand-in,
  and the cycle report § Cycle 2 (the send's block). Implement step 10 as the plugin reports it.

**Order:** T016 → T017 → T018 → T019.
