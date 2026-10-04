<!-- Tech Stack Validation: PASSED — plan § Tech Stack Compliance Report: stdlib and POSIX sh, none added -->

# Tasks: 007 Announcements and discovery (prompt 04, slice 0)

**Input:** spec.md, plan.md, research.md, contracts/timelike-announce-tools.md. **Tests are required**
(H7). Conventions are as in 003–006:
- one commit per task, `[007] Tnnn: …`;
- a `decisions.md` section per task, with a SCOPE line from the installed `scope-check` block;
- delegates own disjoint files, don't commit, and stay out of `tools/`, `.specswarm/`, `../bridge` and
  `../plan`.

**Story map:** US1 the announcement and its check (SC-2) · US2 placement on start (SC-1, SC-4 D4) · US3 the
manifest (SC-3).

## Phase 1: Setup

- [X] T001 `image/rootfs/etc/timelike/standard-tools.json`: the curated entries (spec FR-11, research R4).

## Phase 2: Tests first (from the contract; delegated)

- [ ] T002 [P] [US1] [US2] [US3] `tests/unit/test_announce.py`:
  - generation from fake tools' manifests (a temporary bin directory), the 60-line bound, a failing
    `--agent-info`;
  - `--check` (missing, extra, equal);
  - `--install` and `--status` over a temporary HOME (absent, current, replaced, someone else's, a
    directory in the way, unwritable, Codex's override);
  - `tools` (timelike and curated fields, `installed`, a malformed file);
  - the vanilla Dockerfile untouched.
- [ ] T003 [P] [US1] [US2] [US3] e2e, each under `bash -c` and `bash -lc`:
  - `tests/e2e/announcement-at-most-60-lines-in-each-harness-user-level-context-on-start.bats` (SC-1,
    throwaways);
  - `tests/e2e/announcement-generated-from-manifests-missing-tool-fails.bats` (SC-2);
  - `tests/e2e/timelike-tools-manifest-json-interactivity-risk-safer-alternative.bats` (SC-3, and the
    vanilla image's home).

## Phase 3: Implementation

- [ ] T004 [US1] [US3] `tools/bin/timelike`: `announce` (`--write`, `--check`) and `tools`.
- [ ] T005 [US2] `tools/bin/timelike`: `announce --install` and `--status`; `image/rootfs/opt/timelike/libexec/entrypoint`.
- [ ] T006 `image/Dockerfile`: COPY the curated file and the entrypoint; generate and check after the
  stamp; `ENTRYPOINT`. Update `tests/unit/test_timelike*.py` and the 001 e2e cells if one asserts the
  old usage.
- [ ] T007 `README.md`: an announcements section; `Makefile` `SHELLCHECK_FILES` gains the entrypoint
  and the e2e files.

## Phase 4: Polish

- [ ] T008 Host lane: lint, units with coverage, `make test-host`, start-up. Results in `decisions.md`.
- [ ] T009 `cycle-report.md` § Cycle 1, implement step 10, `.specswarm/metrics.json`, the marker.

## Dependencies

- T001 → T004. T004 → T005 → T006 → T007 → T008 → T009.
- T002 and T003 depend only on the contract, and run beside T004–T006.
