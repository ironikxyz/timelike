<!-- Tech Stack Validation: PASSED -->
<!-- Validated against: .specswarm/tech-stack.md v1.3.0 -->
<!-- No prohibited technologies found -->
<!-- 0 unapproved technologies require runtime validation -->

# Tasks: 002 speedup bench (slice 0)

**Input:** [plan.md](plan.md), [spec.md](spec.md), [data-model.md](data-model.md),
[contracts/](contracts/), [research.md](research.md), [quickstart.md](quickstart.md)

**Tests are required** (constitution H7: every acceptance criterion is a test; merge bar: 90%
coverage). Units come before or beside each module.

**Conventions (from feature 001):**
- One commit per task, `[002] Tnnn: …`.
- Each task gets a `decisions.md` section: INHERITED, FLAGGED, ASSUMED and ABSENT lines, a Verification
  line, and a hand-written `SCOPE:` line.
- Tick the task here.
- Delegates own disjoint files, don't commit, and don't touch `../bridge`, `../plan` or `.specswarm/`.

**Stories.** The spec's scenarios map to stories as follows:
- **US1** = SC-1: one command, two environments
- **US2** = SC-2: CI with a fake agent and no key
- **US3** = SC-3: the D2 report

## Phase 1: Setup

- [X] T001 Create the `bench/` skeleton:
  - `bench/benchlib/__init__.py` (a version constant)
  - add `bench/out/` to `.gitignore`
  - `pyproject.toml`: add the bench modules and `bench/bin/timelike-bench` to mypy `files`, and add
    `bench` to `mypy_path`; ruff already covers the new paths once `bench` is added to the lint
    commands
  - `Makefile`: add `bench` to the `lint-host` and `lint` ruff paths

## Phase 2: Foundational (pure modules; no Docker)

- [X] T002 [P] `bench/benchlib/trace.py`: `ToolCall`, `Identity`, `Ending`, `Tokens`, `Trace`
  dataclasses; `derive_totals`; `to_json` and `from_json`; `validate` (contract rules 1–6); and
  `write_trace`, which validates first. Units in `tests/unit/test_bench_trace.py`:
  - an empty stamp is rejected, field by field
  - totals are derived
  - a revision mismatch is rejected
  - tokens are never written as zero
  - unknown keys are allowed only under `extensions`
  - a round trip gives the same trace
- [X] T003 [P] `bench/benchlib/keys.py`: `is_key_shaped(name)` and `key_shaped(env)`, a port of the
  shell-env F002 rule (RB9), with no `TIMELIKE_ENV_ALLOW` bypass. Units in
  `tests/unit/test_bench_keys.py`: a table taken from the cases in `tests/host/test_shell_env_hook.sh`,
  plus `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, `CLAUDE_CODE_OAUTH_TOKEN` and `OPENAI_API_KEY`;
  MONKEY and KEYBOARD are kept; `GIT_CONFIG_KEY_0` is exempt.
- [X] T004 [P] `bench/benchlib/fakeagent.py`: `Step`, `Policy`, `Observation`, the terminals, a pure
  `next_step` (it takes no environment argument), the loop guard, and `FAKE_AGENT_VERSION`. Units in
  `tests/unit/test_bench_fakeagent.py`:
  - determinism
  - the ok, fail and hang branches
  - each terminal
  - the loop guard
  - a signature test: `next_step` takes no environment parameter
- [X] T005 `bench/benchlib/catalog.py`: the four tasks from RB4, with setup and check scripts,
  policies, `version = 1` and `expected`, plus `NOT_BENCHABLE`. It depends on T004. Units in
  `tests/unit/test_bench_catalog.py`:
  - ids are unique
  - each policy reaches a terminal from every step
  - prerequisites are all `git`
  - no setup or check uses `python3`, `make`, `ps` or network access (RB1)
  - **the setup and check scripts run for real** against a local git repository in a temporary
    directory, with `env -i`, `GIT_CONFIG_NOSYSTEM=1` and no TERM (vanilla emulation), so a broken
    setup fails here and not only in the Docker lane

## Phase 3: US1 — one command runs a task in both images and writes traces (SC-1) 🎯 MVP

**Independent test:** `make bench TASKS=git-inspect` writes `traces/git-inspect--vanilla.json` and
`traces/git-inspect--timelike.json`, both valid and both stamped.

- [X] T006 `bench/benchlib/executor.py`: the `WRAPPER` string (contract); an `Executor` protocol
  returning `(exit_code, duration_ms, hung, stdout_bytes, stderr_bytes, heads)`; a selector-based
  capture that counts every byte and keeps the heads capped; `LocalExecutor`; `DockerExecutor`
  (`docker exec -u agent -w /home/agent/task`, no `-t` or `-i`); and the backstop (limit + 10 s),
  which returns hung. Units in `tests/unit/test_bench_executor.py`, using `LocalExecutor` and the
  **real wrapper**:
  - a sleep past the limit is hung, and ends within limit + 3 s
  - a command that exits 124 by itself, fast, is not hung
  - a background child holding stdout does not block the return
  - byte counts are exact for a 100 KB output, and the heads are capped
  - stdout and stderr are kept separate
  - `DockerExecutor.argv` has no `-t` or `-i`
- [X] T007 `bench/benchlib/docker.py`: `image_identity(ref)` (`.Id` and the revision label);
  `check_identity(expected_sha, images)`, which refuses on an empty or mismatched label and names both
  values; `start_container(image_id)` (the RB5 flags, started by ID); `remove_container`;
  `env_of(image or container)` from `docker inspect`; and `term_is_empty`, a preflight check. Each
  call takes an injectable `run` function. Units in `tests/unit/test_bench_docker.py`, fed fake
  `inspect` JSON.
- [X] T008 `bench/benchlib/runner.py`: `run_task(task, env_name, image, executor_factory, limits,
  identity)`. It runs setup, then the policy loop through `next_step` (with a harness pass cap of
  30 000 bytes), then the check, and returns a `Trace` with its ending (it depends on T002–T007).
  `run_bench(tasks, ...)` does vanilla then timelike, writes the traces, and always removes the
  containers. Units in `tests/unit/test_bench_runner.py`, using `LocalExecutor` in temporary
  directories, with the environment emulated by env variables. They cover:
  - completed
  - failed check
  - failed setup, which gives a trace with no calls
  - a hung call followed by recovery
  - the run limit, which gives `hung`
  - `rebase-continue` on the host with vanilla emulation and with timelike's ENV replayed, matching
    RB3's rc pattern
- [X] T009 `bench/bin/timelike-bench`: an `agentio`-based CLI with `run` and `report` (contract);
  key refusal before anything else (exit 4); identity check (exit 1); and a first line whose scope
  carries the fake-agent statement. Units in `tests/unit/test_bench_cli.py`: `run` with the Docker
  layer stubbed through an environment hook, and `report` over fixture traces. `timelike-conform`
  passes over `bench/bin`. Add `bench/bin` to the conformance unit, following the
  `TIMELIKE_BIN_DIRS` pattern in `tests/unit/test_conform.py`.
- [X] T010 [P] `bench/vanilla/Dockerfile` (RB1): `DEBIAN_IMAGE`, git with `--no-install-recommends`,
  the `agent` uid 1000 with the collision guard from `image/Dockerfile`, `/home/agent` empty,
  `USER agent`, and the `GIT_SHA` label (refusing an empty value). No ENV beyond the base image.
- [X] T011 [P] `bench/driver/Dockerfile` (RB6): `DEBIAN_IMAGE`, the uv CPython at
  `/opt/timelike/python` (as in `image/Dockerfile` §2), the docker CLI from `DOCKER_CLI_IMAGE`,
  `agentio` and `benchlib` in site-packages, `timelike-bench` and `timelike-conform` in
  `/opt/timelike-bench/bin`, `TIMELIKE_BIN_DIRS`, the `GIT_SHA` label, and a `REVISION` file.
- [X] T012 `bench/run.sh` (the host wrapper, per the contract) and Makefile targets:
  - `bench-images`, which builds agent, vanilla and driver with `GIT_SHA` and the pins
  - `bench`, which runs `docker-check`, `stamp-check` and `bench-images`, then
    `bench/run.sh --task $(TASKS)`

  Add `bench/run.sh` to `SHELLCHECK_FILES`.

**Checkpoint:** SC-1 is ready for the Docker lane.

## Phase 4: US2 — end to end in CI against the fake agent, without any API key (SC-2)

**Independent test:** `make test` runs `speedup-bench.bats` green, and a planted key makes the run
refuse.

- [X] T013 `tests/e2e/fixtures/validate_bench.py`: an **independent** validator that shares no code
  with `benchlib`. It parses the traces with its own rules: stamps are non-empty, `image_revision`
  equals the expected SHA, totals are recomputed from `calls`, and there are two traces per task. It
  also checks the report: the first line holds the fake-agent statement, the maintainer and reproduce
  lines are present, and tokens appear only under the appendix. It runs in the driver image's
  interpreter, from the read-only repository mount. Units in `tests/unit/test_validate_bench.py`, over
  good and bad fixtures.
- [X] T014 `tests/e2e/speedup-bench.bats`, with tests named after the distinguishing text:
  - `one command runs a task in both a vanilla image and the timelike image and writes a per-run
    trace`: runs `bench/run.sh`-equivalent `docker run` of the driver from the runner, then the
    validator
  - `the bench runs end to end in CI against a deterministic fake agent without any API key`: a full
    catalog run and the validator; the report's first line; no key-shaped variable in the driver or
    the containers
  - `a planted API key refuses the run`: exit 4, and no traces written
  - `a blanked stamp fails the run`: an image rebuilt with a mismatched label is refused, naming both
    values
  - `a hanging call ends within its limit and is recorded`: the vanilla trace for
    `git-commit-hook-hangs` has `hangs >= 1`, and the run's wall-clock is under
    `call_limit + run overhead`
- [X] T015 `tests/run.sh`: add `vanilla` and `driver` build steps after `build`, and make e2e depend
  on them, recording skipped steps with a reason as now. Mount a writable `bench/out` for the bats
  runner, at the same absolute path (RB7).

**Checkpoint:** SC-2 is ready for the Docker lane.

## Phase 5: US3 — the D2 report (SC-3)

**Independent test:** `timelike-bench report <dir>` over fixture traces prints the layout in the
contract, with losing tasks first.

- [X] T016 `bench/benchlib/report.py`: pairing, the verdict rule (data-model), the sections in order,
  `incomplete` pairs placed under the losing section, the not-benchable note, the tokens appendix, and
  the fake-agent and live first lines. `render(traces) -> list[str]` is pure. Units in
  `tests/unit/test_bench_report.py`:
  - ordering (loss, tie, win)
  - ties
  - an incomplete pair
  - the first line for a fake-agent run
  - the maintainer and reproduce lines
  - the word "token" appears only under the appendix heading
  - re-rendering from files equals rendering from memory (FR-10)

  This task can start after T002, in parallel with Phase 3. T009 consumes it.

## Phase 6: Polish and cross-cutting

- [X] T017 `scan/scan.sh`: loop over the agent, vanilla and driver images (RB10), with an output
  directory for each image; `evaluate.py` and the dists run in the agent image; pip-audit gives
  `none` for vanilla; and the Docker CLI's Go-stdlib risk goes in a comment. Update the scan units if
  they assert the image list.
- [X] T018 Host-lane verification:
  - ruff, format, mypy and shellcheck (the full commands in reboot.md)
  - the unit suite
  - coverage using the reboot.md recipe, with `$PWD/bench/*` and the pytest copies of
    `timelike-bench` added: ≥ 90% overall for Python
  - `timelike-conform` over `tools/bin` and `bench/bin`

  Record the figures in `decisions.md`.
- [X] T019 Docs: add a README section "Speedup bench", with the command and the reading guide from
  quickstart, and the fake-agent caveat verbatim. Update `reboot.md` for 002.
- [X] T020 `cycle-report.md` (Cycle 1, this send), per the send's `## Cycle report` block:
  - Group A: not applicable
  - Group B: copied from the send
  - Group C: all seven fields
  - the watch items and the low leftovers carried from 001, as the user asked
  - SC-1 and SC-2 `unconfirmed` until the operator's Docker lane runs
  - SC-3 `unconfirmed` until the operator reads a report

## Phase 7: Docker lane feedback (Cycle 1)

- [X] T021 One output layout for `bench/run.sh` and `timelike-bench run --out`. The Docker lane at
  `8ce6173` failed three bench tests: run.sh passed `--out X` only as `BENCH_OUT`, the tool stamped
  `X/<UTC>/` beneath it, and `speedup-bench.bats` validated `X/traces`. Rule: `--out DIR` is exactly
  DIR, and a DIR already holding traces is refused; no `--out` gives `$BENCH_OUT/<UTC stamp>/`. Adds
  `tests/unit/test_bench_run_sh.py`, the host test of the wrapper the lane caught, and records the
  layout in `contracts/bench-cli.md` and the cycle report.

## Phase 8: The report explains itself (send `…-080659`, D2 findings; modify.md F001–F003)

- [X] T022 `bench/benchlib/catalog.py`: add `difference` and `notes` (keyed `environment:ending`) to
  every task; make every check print a plain one-line reason when it fails; bump every task to version
  2. Units in `tests/unit/test_bench_catalog.py`: each failing check's reason is non-empty, and in the
  timelike emulation `git-commit-hook-rejects` fails with the TODO/hook reason.
- [X] T023 `bench/benchlib/report.py`: the new first line (F001) and the per-task explanation block
  (F002): `Tests:`, `Verdict:` in words, the table, what happened in each arm, and the ending and its
  reason; a note printed only when its `environment:ending` matches. `render(…, tasks=…)` replaces
  `goals=`. Units in `tests/unit/test_bench_report.py`.
- [X] T024 `bench/bin/timelike-bench`: pass the catalog texts; the header scope becomes
  `FAKE-AGENT BENCH PIPELINE DEMO RUN -- not a test of timelike`. Units in `tests/unit/test_bench_cli.py`,
  including one that renders the real catalog through a full run and checks that the
  `git-commit-hook-rejects` section names the skipped hook and the broken policy.
- [X] T025 `tests/e2e/fixtures/validate_bench.py` (the new first line; every task section carries
  `Tests:`, `Verdict:` and a "What happened" for both arms) and `tests/e2e/speedup-bench.bats` (scope
  wording), with its units.
- [X] T026 Docs: README, `contracts/bench-cli.md` (report layout), quickstart, and spec FR-9. Re-render
  `bench/out/20260929T022053Z/` with `timelike-bench report`, as a preview built from the traces the
  operator already read, and host-lane verification.
- [X] T027 `cycle-report.md`: a section for this send, recording the Docker lane at `64270f7` (SC-1 and
  SC-2 executed), where the first line lives, and SC-3 still unconfirmed; `audit-log.md`, a `none` row.

## Phase 9: Cycle 2 — revision 8 recorded (send `bridge/sends/02-rev8-20261008-095251.md`, via `/specswarm:modify`)

<!-- Tech Stack Validation (cycle 2): PASSED — plan.md § Tech Stack Compliance Report (Cycle 2) has no
conflict or prohibition; the task scan (lib/tech-stack-parser.sh, ts_mentions) found no prohibited
technology in the task text below. The tasks change Markdown only -->

Governance is current at `[2..13]`, so there is no audit task. Nothing outside
`.specswarm/features/002-speedup-bench/` changes, so there is no Docker lane (send § How this cycle runs).

- [X] T028 `spec.md` § Reporting: copy revision 8's constraint in after FR-9a, verbatim and declared
  *(Added revision 8.)*, with a note that slice 0's code does not meet it (`bench/benchlib/report.py:119`,
  `:227`; `data-model.md:125`; T016) and that plan's ruling (b) carries the change to 02 slice 1. The
  slice-1 criterion is not copied: the spec keeps no later-slice criterion list (`spec.md:216–218`). No other
  body line changes; `report.py` and `data-model.md` are not edited.
- [ ] T029 `decisions.md` T016: below its fourth ASSUMED line (the hung call counted twice), add an
  annotation: *superseded by discovery revision 8 (ruling (b)), code change carried to 02 s1*. The ASSUMED
  line is kept as written.
- [ ] T030 Provenance (modify Step 9): compute the append with the installed `audit-append` block, mode
  `scoped` with `OUT_OF_SCOPE` empty: revision 8's own change (the constraint) is addressed by T028, but its
  added slice-1 criterion is not addressed by this cycle, so `full` is not available (Step 9: "Added criteria
  this modification didn't address"). Expected append: 8 alone, as the send asks; revisions 2–7 did not
  change prompt 02, so they leave no hole for 3c. Write
  `audited_against` in `spec.md` frontmatter and one row in `audit-log.md`. Never touch `prompt_revision`,
  `discovery_revision` or `source_prompt`.
- [ ] T031 Cycle report § Cycle 2 (the send's block): Group A not applicable; Group B copied from the send;
  Group C, the two Automated criteria cited from the mentor's lane readme-c at `10ddd3a` (an identical tree),
  D2 with the mode the Cycle 1 sign-off addendum recorded (observed by the operator); `not_verified` names the
  four unmet places; the plugin version and any stderr under 2.37.0.

**Parallel:** T028 and T029 touch different files. T030 follows T028, and T031 comes last.

## Dependencies

- T001 comes first.
- T002, T003 and T004 can run in parallel. T004 comes before T005.
- T002 comes before T016.
- T002–T007 come before T008. T008 and T016 come before T009.
- T010 and T011 can run in parallel with T006–T009. T009, T010 and T011 come before T012.
- T012 comes before T013, T014 and T015.
- T017 is independent of Phase 4.
- T018 comes after everything else in code. T019 and T020 come last.

## Parallel execution (delegation plan)

**Wave A**, subagents with disjoint files:
- T002 (`trace.py` and its units)
- T003 (`keys.py` and its units)
- T004 → T005 (`fakeagent.py`, `catalog.py` and their units; one delegate)

**Wave B:**
- the coordinator: T006 → T007 → T008
- a subagent: T016 (`report.py` and its units)
- a subagent: T010 and T011 (the two Dockerfiles)

**Then** the coordinator does T009, T012–T015 and T017, and review, T018–T020.

## Implementation strategy

The MVP is US1: two traces per task from one command. US2 wires it into the Docker lane with an
independent validator. US3's report is small, but it is what the D2 demo reads. Nothing in slice 1
(the told/not-told arm, a second harness, failure categories) is built. The trace keeps room for it
under `extensions` and in `stderr_head`.
