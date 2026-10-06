<!-- Tech Stack Validation: PASSED — plan § Tech Stack Compliance Report: Python stdlib, pytest, ruff, mypy, uv, bats-core, git; none added; the host-recorded runners are not project technologies -->

# Tasks: 012 Verify changed (prompt 11, slice 1)

**Input:** spec.md, plan.md, research.md, data-model.md, contracts/verify-cli.md. **Tests are required**
(H7). Conventions are as in 003–011:
- one commit per task, `[012] Tnnn: …`;
- a `decisions.md` section per task, with a SCOPE line from the installed `scope-check` block;
- delegates own disjoint files, don't commit, and stay out of `tools/`, `image/`, `.specswarm/`,
  `../bridge` and `../plan`.

The fixtures (`tests/fixtures/verify/make-project.sh`, `record.sh`, `recorded/`) were recorded and
committed at plan (`6ba52b8`), because the research measured them. A task that changes them re-records
them with `record.sh`, and never edits a recording by hand.

**Story map:**
- US1: `verify test` on pytest (SC-1)
- US2: the other formats, and unknown (SC-2)
- US3: `verify changed` with one changed file (SC-3)
- US4: no changes (SC-4)
- D20: the demo

## Phase 1: Tests first (from the contract; delegated)

- [X] T001 [P] [US1] [US2] [US3] [US4] `tests/unit/test_verify.py`, per research R7.
  - **Every recording** in `tests/fixtures/verify/recorded/`, with the expected counts, names and
    locations taken from `make-project.sh`'s projects (what the generator wrote), never from the parser's
    answer.
  - **Formats:** identification order, and the unknown fallback.
  - **`run` results:** `run` replaced by a stub only for exit 1, unreadable JSON, and redaction
    unavailable.
  - **The change set:** on git repositories the test builds (modified, added, deleted, renamed,
    untracked, `--since`).
  - **Selection reasons**, using the real `symbols` beside `verify`.
  - **Not-run steps**, exit codes, `--dry-run`, and the manifest.
- [X] T002 [P] [US1] [US2] [US3] [US4] e2e, each under `bash -c` and `bash -lc`, with its own workspace
  and session. Projects come from `make-project.sh` copied into the container; pytest, ruff and mypy are
  uv-backed wrappers from a `tests/e2e/helpers.bash` function (R1):
  - `tests/e2e/verify-pytest-3-failed-409-passed-file-line-name-assertion-lines.bats` (SC-1)
  - `tests/e2e/verify-parses-pytest-jest-vitest-go-cargo-unknown-format-falls-back.bats` (SC-2)
  - `tests/e2e/verify-changed-one-source-file-runs-importing-tests-lints-changed-states-why.bats` (SC-3)
  - `tests/e2e/verify-changed-no-changes-exits-0-nothing-selected.bats` (SC-4)
  - `tests/e2e/verify-name-and-manifest.bats`: `type -a verify`, and the manifest

## Phase 2: Implementation

- [X] T003 [US1] [US2] [US3] [US4] `tools/bin/verify`, per `contracts/verify-cli.md`:
  - `run --json` and the log (R2);
  - the five parsers and the linter diagnostics (R3);
  - the change set, and selection through `symbols dependents` (R4);
  - runner lookup and "not run" (R5);
  - `test`, `changed` and `--dry-run`, with the exits (R6).
- [X] T004 `pyproject.toml` (ruff and mypy lists), `Makefile` (`SHELLCHECK_FILES`: the e2e files and
  `tests/fixtures/verify/*.sh`), `README.md` (a verify section).

## Phase 3: Polish

- [X] T005 Host lane: lint, units with coverage, `make test-host`, host conformance, the e2e host stand-in,
  start-up. Results in `decisions.md`.
- [ ] T006 `cycle-report.md` § Cycle 1, implement step 10, `.specswarm/metrics.json`, the marker.

## Dependencies

- T003 → T004 → T005 → T006.
- T001 and T002 depend only on the contract and the fixtures, and run beside T003.
