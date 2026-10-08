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

- [X] T002 [P] [US1] [US2] [US3] `tests/unit/test_announce.py`:
  - generation from fake tools' manifests (a temporary bin directory), the 60-line bound, a failing
    `--agent-info`;
  - `--check` (missing, extra, equal);
  - `--install` and `--status` over a temporary HOME (absent, current, replaced, someone else's, a
    directory in the way, unwritable, Codex's override);
  - `tools` (timelike and curated fields, `installed`, a malformed file);
  - the vanilla Dockerfile untouched.
- [X] T003 [P] [US1] [US2] [US3] e2e, each under `bash -c` and `bash -lc`:
  - `tests/e2e/announcement-at-most-60-lines-in-each-harness-user-level-context-on-start.bats` (SC-1,
    throwaways);
  - `tests/e2e/announcement-generated-from-manifests-missing-tool-fails.bats` (SC-2);
  - `tests/e2e/timelike-tools-manifest-json-interactivity-risk-safer-alternative.bats` (SC-3, and the
    vanilla image's home).

## Phase 3: Implementation

- [X] T004 [US1] [US3] `tools/bin/timelike`: `announce` (`--write`, `--check`) and `tools`.
- [X] T005 [US2] `tools/bin/timelike`: `announce --install` and `--status`; `image/rootfs/opt/timelike/libexec/entrypoint`.
- [X] T006 `image/Dockerfile`: COPY the curated file and the entrypoint; generate and check after the
  stamp; `ENTRYPOINT`. Update `tests/unit/test_timelike*.py` and the 001 e2e cells if one asserts the
  old usage.
- [X] T007 `README.md`: an announcements section; `Makefile` `SHELLCHECK_FILES` gains the entrypoint
  and the e2e files.

## Phase 4: Polish

- [X] T008 Host lane: lint, units with coverage, `make test-host`, start-up. Results in `decisions.md`.
- [X] T009 `cycle-report.md` § Cycle 1, implement step 10, `.specswarm/metrics.json`, the marker.

## Phase 5: Cycle 2 — revision 13 recorded; the workspace clause struck (send `bridge/sends/04-rev13-20261008-095251.md`, via `/specswarm:modify`)

<!-- Tech Stack Validation (cycle 2): PASSED — plan.md § Tech Stack Compliance Report (Cycle 2) has no
conflict or prohibition; the task scan (lib/tech-stack-parser.sh, ts_mentions) found no prohibited
technology in the task text below. The tasks change Markdown only -->

Governance is current at `[2..13]`, so there is no audit task. Nothing outside
`.specswarm/features/007-announcements-discovery/` changes, so there is no Docker lane.

- [X] T010 `spec.md` SC-1 (`:161–163`) and its note (`:170–171`): quote revision 13's criterion verbatim, the workspace
  clause kept struck with its marker; the note becomes "struck at revision 13, nothing to build". FR-7's
  "narrows the criterion" note (`:113–116`) and Out of scope (`:232`) say the clause is struck at revision 13.
- [X] T011 `spec.md` D-1 (`:200–210`): keep the reasoning as written; append *resolved by discovery revision 13 (Q3,
  option (b)), plan `394c33e` — the FLAGGED decision is now the rule, not a deviation from it*.
- [X] T012 Provenance (modify Step 9): compute the append with the installed `audit-append` block, mode `scoped`
  (revision 13 rewords one criterion by a strike, so `full` would list it as unverified; its own change is what this
  cycle addresses), expecting 13 alone; write `audited_against` in `spec.md` frontmatter; create `audit-log.md` with
  its header, a seed row for specify's `[1]` and this cycle's row. Never touch `prompt_revision`,
  `discovery_revision` or `source_prompt`.
- [X] T013 `cycle-report.md` § Cycle 2 (the send's block): Group A not applicable; Group B from the send; the three
  slice-0 Automated criteria cited from the mentor's lane readme-c at `10ddd3a` (an identical tree); D4 observed by the
  operator (Addendum 2); implement steps 10 and 9b.

**Parallel:** T010 and T011 touch the same file, so they run in order. T012 follows them, and T013 comes last.

## Dependencies

- T001 → T004. T004 → T005 → T006 → T007 → T008 → T009.
- T002 and T003 depend only on the contract, and run beside T004–T006.

## Phase 6: Cycle 3 — slice 1 (send `bridge/sends/04-rev13-20261008-161802.md`, via `/specswarm:modify` → plan → tasks)

<!-- Tech Stack Validation (cycle 3): PASSED — plan.md § Tech Stack Compliance Report (Cycle 3) has no conflict or
prohibition; the installed tech-stack-taskscan block (lib/tech-stack-parser.sh, ts_mentions) scanned the 10 task
lines below and found no prohibited technology -->

Spec § Slice 1, contract § Slice 1, plan § Cycle 3. Governance is current at `[2..13]`, so there is no audit task.
This cycle changes `image/`, `tools/` and `tests/`, so **the mentor's Docker lane is the merge bar**.

**Stories:** US5 = SC-5 (the command-not-found answer), US7 = SC-7 (the budget), US6 = SC-6 (installs, **held**),
C = carried items. Tests are written from the contract **before** the code (the 003/005 pattern), by delegates.

- [X] T014 [P] [US5, US7] e2e from the contract, written by a delegate before the code:
  `tests/e2e/command-not-installed-exits-127-and-prints-the-install-command.bats` (SC-5: per style `bash -c`,
  `bash -lc`, interactive, a script; `sh -c` and direct exec unreached; the unknown name byte for byte against bash
  with the handler unset; every listed name absent) and
  `tests/e2e/one-command-prints-the-agents-resource-budget.bats` (SC-7: a throwaway with known `--memory`, `--cpus`,
  `--pids-limit`; the agent container; the CPU figure equals the shell's `$TIMELIKE_CPUS`).
- [X] T015 [P] [US5, US7] Units and the host test from the contract, written by a delegate before the code:
  `tests/unit/test_budget.py` (figures from files the test writes under `TIMELIKE_CGROUP_ROOT`: values, `max`,
  unreadable, missing; disks; text and JSON; the CPU rule against the bash hook on the same files),
  `tests/unit/test_missing_commands.py` (the shipped TSV's validity), and `tests/host/test_command_not_found.sh`
  (the handler per style, byte for byte against bash, under `set -eux` callers, with an empty PATH).
- [X] T016 [US7] `tools/agentio/agentio.py`: `cgroup_dir`, `cgroup_value`, `cpu_figure` and `workspace`. `tools/bin/run`
  and `tools/bin/snapshot` use them, and their own copies go. Their existing suites (`tests/unit/test_run*.py`,
  `tests/unit/test_snapshot.py`, `tests/unit/test_undo.py`) pass unchanged.
- [X] T017 [US7] `tools/bin/timelike`: `timelike budget` (contract § `timelike budget`) and the announcement's two
  rule lines (FR-24). `tests/unit/test_announce.py` is updated only where it counts lines.
- [X] T018 [US5] `image/rootfs/etc/timelike/shell-env.bash`: `command_not_found_handle` (contract § The
  command-not-found answer), with the header rules updated. `image/rootfs/etc/timelike/missing-commands.tsv` (R6).
  `image/Dockerfile`: one COPY. Measure the handler's cost per call and record it. `tests/host/test_shell_env_hook.sh`
  and `tests/host/test_env_layer.sh` still pass.
- [X] T019 [C] `tests/e2e/announcement-at-most-60-lines-in-each-harness-user-level-context-on-start.bats`: the cell
  names take revision 13's criterion text, and the workspace cells say "the workspace is left untouched". The
  1 s bound becomes the ordering assertion (spec § Slice 1 carried items), and the time is printed, not asserted.
- [X] T020 Host verification: units, lint (ruff, mypy, shellcheck), the host e2e stand-in over the new and changed
  files, conformance, coverage. Results go in `decisions.md`, labelled advisory (no image).
- [X] T021 `README.md`: `python3 scripts/readme_reference.py --write` (the timelike help moved). The README status
  block is applied **only if** SC-6 is built too (the send's condition); otherwise untouched, with the reason
  recorded.
- [ ] T022 [US6] ~~**HELD on FOR-MENTOR Item 21** (FR-18): installs per the ruling. Tasks are written when it is
  answered.~~ *(Superseded by Phase 7, Cycle 4: Item 21 answered by discovery revision 14; the installs are
  T024–T033. T022 itself is closed there, in T033's record.)*
- [X] T023 `cycle-report.md` § Cycle 3 (the send's block), and implement steps 10 and 9b.

**Parallel:** T014 and T015 (delegates, test files only) run beside T016–T019. T016 comes before T017. T020 follows
T016–T019 and T021 follows T020. T023 comes last.

## Phase 7: Cycle 4 — the agent runtimes (send `bridge/sends/04-rev14-20261008-174220.md`, via `/specswarm:modify` → plan → tasks)

<!-- Tech Stack Validation (cycle 4): PASSED — plan.md § Tech Stack Compliance Report (Cycle 4) has no conflict or
prohibition; the installed tech-stack-taskscan block scanned the 10 task lines below and found no prohibited
technology -->

Spec § Slice 1, cycle 4 (FR-25 to FR-31, D-12 to D-15), plan § Cycle 4, research R9. Governance was audited to
14 on this branch (`e58dd36`, `07b914d`), so there is no audit task here. **The mentor's Docker lane is the merge
bar.** US6 = SC-6.

- [X] T024 [P] [US6] e2e from the spec, by a delegate, before the images change:
  `tests/e2e/a-bare-python-package-install-and-a-global-node-package-install-succeed-without-privilege.bats`
  (FR-31: per style; a test-built wheel and npm package, unique versions; new shell; only `/home/agent` changed;
  timelike's interpreter unchanged; no `PIP_BREAK_SYSTEM_PACKAGES`; the runtimes resolve to `/opt/agent`), and the
  P6 vanilla cell in `tests/e2e/timelike-tools-manifest-json-interactivity-risk-safer-alternative.bats` revised to
  FR-13 (same versions, marker kept, `npm prefix -g` default, bare pip refused, no announcement).
- [X] T025 [P] [US6] Units by a delegate: `tests/unit/test_announce.py`'s vanilla test (FR-13 revised: no timelike
  configuration path; the runtime pins present), `tests/unit/test_agent_runtimes.py` (new: `pins.env` carries
  `NODE_VERSION` and a 64-hex `NODE_SHA256`; both Dockerfiles verify it with `sha256sum -c`; `pip.conf` and
  `npmrc` only in the agent Dockerfile; no `PIP_BREAK_SYSTEM_PACKAGES` in `image/`, `bench/`, `compose.yaml`,
  `Makefile`; the `ENV` PATH order), `tests/unit/test_missing_commands.py` (user rows allowed; each starts
  `pip install ` or `npm install -g `; none of the seven runtime names listed).
- [X] T026 [US6] `pins.env` (`NODE_VERSION`, `NODE_SHA256`), `compose.yaml` (agent build args), `Makefile`
  (`bench-images` passes `UV_IMAGE`, `PYTHON_VERSION` and the Node pins to the vanilla build).
- [X] T027 [US6] `image/Dockerfile`: the `runtimes` stage, `/opt/agent`, marker removed, `pip.conf`, `npmrc`, seven
  links, the `ENV` PATH with `/home/agent/.local/bin`. `image/rootfs/etc/profile.d/00-timelike-path.sh`: the
  same entry. `tests/host/test_env_layer.sh` still passes, or its PATH checks move with the declared order.
- [X] T028 [US6] `bench/vanilla/Dockerfile`: the same stage and binaries, stock behaviour; its header comment says
  so (002's file; `changed_other_features`).
- [X] T029 [US6] `image/rootfs/etc/timelike/missing-commands.tsv`: the seven runtime rows out; `user` rows for common
  Python and Node CLIs. `image/rootfs/etc/timelike/standard-tools.json` checked (python3 and node keep their risk
  and `instead`).
- [X] T030 `scan/scan.sh`: its comments and the pip-audit "no interpreter" record say timelike's interpreter, not
  any interpreter.
- [X] T031 Host verification: the units, the host lane, lint, and an advisory host build check of the runtime
  steps (the uv prefix and Node tarball, as in R9). Results go in `decisions.md`.
- [X] T032 `README.md`: the send's `## README status` block (all four slice-1 criteria are now built); the vanilla
  description (Debian + git + the agent runtimes, stock); the reference regenerated if any help moved.
- [X] T033 Provenance (modify Step 9): append 14 with the installed `audit-append` block, scoped, and its
  `audit-log.md` row. Then `cycle-report.md` § Cycle 4, implement steps 10 and 9b, and `reboot.md` brought up
  to date for a clear.

**Parallel:** T024 and T025 (delegates, test files only) run beside T026–T030. T026 comes before T027 and T028.
T031 follows them, then T032, then T033.


## Phase 8: Lane 007s1-a fixes (feedback `bridge/feedback/04-20261008-193851-lane-007s1-a-three-cells-and-the-scan.md`, by hand on Cycle 4's tasks)

- [X] T034 [US5] `tests/e2e/command-not-installed-exits-127-and-prints-the-install-command.bats`: the direct-exec
  SC-5 cell looks for docker's not-found message on either stream (measured on Docker 29.4.2: stdout), and keeps
  non-zero, `tree`, "not found" and no timelike line.
- [X] T035 `tests/e2e/conformance-check-over-every-timelike-tool-on-path.bats` and
  `tests/e2e/fixtures/timelike-envpython`: 001's broken-interpreter cell runs with a PATH that excludes the agent
  runtimes, so its premise (no python3 on PATH) holds again; C1 and C6 stay asserted (001's test:
  `changed_other_features`).
- [X] T036 `scan/baseline/timelike-agent.json`, `scan/baseline/timelike-vanilla.json`: reviewed entries for the two
  findings with no fix (GHSA-ch52-4w7c-c8xp in npm's bundled http-cache-semantics; CVE-2026-77214 in the base
  layer's libexpat1, via git), with reason, layer and the neighbours' review date.
- [X] T037 `scan/scan.sh`, `scan/evaluate.py`: pip-audit also over the agent interpreter (`/opt/agent/python`)
  in every image that carries it, as a second result line; `tests/unit/test_scan_report.py` and
  `.specswarm/quality-standards.md` follow.
- [X] T038 `pins.env`, `image/Dockerfile`, `bench/vanilla/Dockerfile`: the seven fixable npm findings, by the route
  the mentor's ruling allows (no Node 24.x release newer than 24.21.0 exists; see decisions).
- [ ] T039 `cycle-report.md` § Cycle 4, `### Lane 007s1-a fixes`; `reboot.md` brought up to date.
