<!-- Tech Stack Validation: PASSED — plan § Tech Stack Compliance Report: Python stdlib, Bash, pytest, bats-core; none added -->

# Tasks: 009 Session journal (prompt 08, slice 1)

**Input:** spec.md, plan.md, research.md, data-model.md, contracts/journal-cli.md. **Tests are required**
(H7). Conventions are as in 003–008:
- one commit per task, `[009] Tnnn: …`;
- a `decisions.md` section per task, with a SCOPE line from the installed `scope-check` block;
- delegates own disjoint files, don't commit, and stay out of `tools/`, `image/`, `.specswarm/`,
  `../bridge` and `../plan`.

**Story map:**
- US1: tool invocations in order with pointers (SC-1)
- US2: shell commands (SC-2)
- US3: the tail of 20 (SC-3)
- US4: agents and sessions (SC-4)
- US5: the operator's view with grant uses (SC-5, D17)
- US0: shared (the event extension)

## Phase 1: Foundational — the writers

- [X] T001 [US0] [US1] [US4] `tools/agentio/agentio.py`: the event's `agent`, `ppid`, `t_ms`, and `ref`
  from `Tool(event_ref=(kind, key))` (data-model § Tool event). Declare `event_ref` in `tools/bin/run`
  (`log`) and `tools/bin/snapshot` (`snapshot`, `id`, for both `snapshot` and `undo`). Update 001's
  `contracts/event.schema.json` (optional fields) and `contracts/output-contract.md` § Session event.
  Extend `tests/unit/test_agentio.py`: new and old lines validate, `ref` present only for a declared
  key, and `agent` only when valid.
- [X] T002 [US2] [US4] `image/rootfs/etc/timelike/journal-exit.bash` (new) and the guarded step in
  `image/rootfs/etc/timelike/shell-env.bash` (research R1). Add the `COPY` in `image/Dockerfile`. Extend
  `tests/host/test_shell_env_hook.sh`:
  - F1 holds;
  - Q2 lists `__timelike_journal_t0`;
  - exit status is preserved for each R1 case;
  - `bash -lc` gives one entry;
  - root 1777 and session 0700;
  - a hostile command line gives one valid JSON line.

## Phase 2: Tests first (from the contract; delegated)

- [X] T003 [P] [US1] [US2] [US3] [US4] [US5] `tests/unit/test_journal.py`. Fixtures come from running
  the real tools and `bash -c` with the hook under a temporary scratch root (P005). Cover:
  - order and linking (collapse, nesting);
  - the tail and its cut;
  - sessions and agents;
  - the ledger merge (a JSON array as `adeled ledger --json` prints it);
  - redaction;
  - unreadable lines and records;
  - stdin only with `--ledger -`;
  - the manifest.
- [X] T004 [P] [US1] [US2] [US3] [US4] e2e, each under `bash -c` and `bash -lc`, with the test's own
  `TIMELIKE_SESSION` and `TIMELIKE_AGENT`:
  - `tests/e2e/journal-lists-every-tool-invocation-in-order-with-pointer.bats` (SC-1)
  - `tests/e2e/journal-shell-commands-outside-tools-with-exit-codes.bats` (SC-2)
  - `tests/e2e/journal-last-20-entries-of-current-session-bounded.bats` (SC-3)
  - `tests/e2e/journal-concurrent-agents-separable-by-agent-and-session.bats` (SC-4)
  - `tests/e2e/journal-name-and-manifest.bats`: `type -a journal` exactly `/opt/timelike/bin/journal`,
    and the manifest

## Phase 3: Implementation

- [X] T005 [US1] [US2] [US3] [US4] [US5] `tools/bin/journal`, per `contracts/journal-cli.md`:
  - reading the records;
  - order and linking (R3);
  - the entries;
  - the tail, `--all`, `--session`, `--all-sessions`, `--agent`;
  - `--ledger` (R4);
  - redaction (R5);
  - the refusals.
- [X] T006 `pyproject.toml` (ruff and mypy lists), `Makefile` (`SHELLCHECK_FILES`: `journal-exit.bash`
  and the e2e files), `README.md` (a journal section).

## Phase 4: Polish

- [ ] T007 Host lane: lint, units with coverage, `make test-host`, host conformance, the e2e host
  stand-in, and start-up timings. Results in `decisions.md`.
- [ ] T008 `cycle-report.md` § Cycle 1, implement step 10, `.specswarm/metrics.json`, the marker.

## Dependencies

- T001 → T005 (the fields it reads). T002 → T005 (the record it reads). T005 → T006 → T007 → T008.
- T003 and T004 depend only on the contract and run beside T001, T002 and T005.

## Strategy

The MVP is US1 + US3: tool events, and the tail. US2 needs T002's trap. US4 needs T001's `agent`. US5 is
the `--ledger` merge.
