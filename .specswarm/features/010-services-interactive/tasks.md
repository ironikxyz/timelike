<!-- Tech Stack Validation: PASSED — plan § Tech Stack Compliance Report: Python stdlib, pytest, bats-core; none added -->

# Tasks: 010 Services (prompt 09, slice 1)

**Input:** spec.md, plan.md, research.md, data-model.md, contracts/services-cli.md. **Tests are required**
(H7). Conventions are as in 003–009:
- one commit per task, `[010] Tnnn: …`;
- a `decisions.md` section per task, with a SCOPE line from the installed `scope-check` block;
- delegates own disjoint files, don't commit, and stay out of `tools/`, `image/`, `.specswarm/`,
  `../bridge` and `../plan`.

**Story map:**
- US1: start, ready by port (SC-1)
- US2: died before ready (SC-2)
- US3: port held (SC-3)
- US4: stop, whole tree (SC-4)
- US5: list (SC-5)
- D18: the demo

## Phase 1: Tests first (from the contract; delegated)

- [X] T001 [P] [US1] [US2] [US3] [US4] [US5] `tests/unit/test_services.py`, per research R8. Real
  processes only:
  - `python3 -m http.server` on a free port;
  - `sh -c` trees with a `setsid` grandchild;
  - commands that exit early.

  Every claim is checked in `/proc` and on the port. Cover:
  - readiness by port, by log line and by neither;
  - died before ready;
  - the timeout, with and without `--keep`;
  - port holders, registered and unregistered;
  - a duplicate name;
  - stop with the whole tree gone, and `--dry-run`;
  - confirmation for `--session` and `--all`;
  - list: running, died, unlisted, uptime;
  - logs and their redaction;
  - concurrent starts in one session;
  - the manifest.
- [X] T002 [P] [US1] [US2] [US3] [US4] [US5] e2e, each under `bash -c` and `bash -lc`, with its own session
  and free port:
  - `tests/e2e/services-start-with-port-readiness-returns-after-port-accepts.bats` (SC-1)
  - `tests/e2e/services-start-exits-before-ready-non-zero-died-last-log-lines.bats` (SC-2)
  - `tests/e2e/services-start-port-held-by-registered-service-refused-naming-holder.bats` (SC-3)
  - `tests/e2e/services-stop-terminates-every-process-in-its-tree.bats` (SC-4)
  - `tests/e2e/services-list-state-port-uptime-marks-died.bats` (SC-5)
  - `tests/e2e/services-name-and-manifest.bats`: `type -a services`, and the manifest

## Phase 2: Implementation

- [X] T003 [US1] [US2] [US3] [US4] [US5] `tools/bin/services`, per `contracts/services-cli.md`:
  - `start`: marker, new session, log, readiness, died and not ready, holders, names;
  - `stop`: tree by marker ∪ log writers ∪ group, with `run`'s sweep loaded from `tools/bin/run` (R2),
    `--dry-run`, and confirmation for `--session` and `--all`;
  - `list`, including unlisted marker processes;
  - `logs`;
  - the registry under flock.
- [ ] T004 `pyproject.toml` (ruff and mypy lists), `Makefile` (`SHELLCHECK_FILES`: the e2e files),
  `README.md` (a services section).

## Phase 3: Polish

- [ ] T005 Host lane: lint, units with coverage, `make test-host`, host conformance, the e2e host
  stand-in, start-up. Results in `decisions.md`.
- [ ] T006 `cycle-report.md` § Cycle 1, implement step 10, `.specswarm/metrics.json`, the marker.

## Dependencies

- T003 → T004 → T005 → T006.
- T001 and T002 depend only on the contract and run beside T003.
