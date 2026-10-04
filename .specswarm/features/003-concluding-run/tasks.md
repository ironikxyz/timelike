<!-- Tech Stack Validation: PASSED -->
<!-- Validated against: .specswarm/tech-stack.md v1.3.0 -->
<!-- No prohibited technologies found -->
<!-- 0 unapproved technologies require runtime validation (ctypes is Python stdlib; plan § Tech Stack Compliance) -->

# Tasks: 003 concluding run (slice 0)

**Input:** [plan.md](plan.md), [spec.md](spec.md), [data-model.md](data-model.md),
[contracts/](contracts/), [research.md](research.md), [quickstart.md](quickstart.md)

**Tests are required.** Constitution H7 makes every acceptance criterion a test, and the merge bar is
90% coverage. Units come before or beside each module.

**Conventions (from features 001 and 002):**
- One commit per task, `[003] Tnnn: …`.
- Each task gets a `decisions.md` section: INHERITED, FLAGGED, ASSUMED and ABSENT lines, a Verification
  line, and a hand-written `SCOPE:` line.
- Tick the task here.
- Delegates own disjoint files, don't commit, and don't touch `../bridge`, `../plan` or `.specswarm/`.
- **Process safety (cycle 5):**
  - Any host experiment or test that forks or hangs runs under `setsid --wait timeout -k 5 N … </dev/null`.
  - Never `pgrep -f` or `pkill -f`. Survivors are detected by marker files they write.

**Stories.** The spec's scenarios map to stories as follows:
- **US1** = SC-5: exit pass-through. It is the core run path, and every other story builds on it
- **US2** = SC-3 and SC-6: the detached child, D3
- **US3** = SC-4: timeout over the whole tree
- **US4** = SC-1 and SC-2: the display

## Phase 1: Setup

- [X] T001 Register the new tool with the toolchain:
  - `pyproject.toml`: add `tools/bin/run` to ruff `extend-include` and to mypy `files`
  - `tools/bin/run`: a stub. It has the `#!/opt/timelike/python/bin/python3 -I` shebang, a `Tool` with
    `name="run"`, and an `agentio.run` call that exits 1 with "not implemented". Mode 0755
  - Confirm the Dockerfile's `COPY tools/bin/` already ships it, with no edit

## Phase 2: Foundational — 001's contract amendment (FR-20 to FR-24; blocks every story)

- [X] T002 [P] Contract text and schemas (`.specswarm/features/001-agent-shell-baseline/contracts/`),
  per `contracts/output-contract-amendment.md`:
  - `output-contract.md`: § Exit codes gains the scope, the pass-through rule, `cause` and
    `command_exit`. Line 83 is reworded. Add a "Changed in feature 003 (discovery revision 9)" note
  - `agent-info.schema.json`: optional `passes_exit`
  - `event.schema.json`: `exit` becomes an integer from 0 to 255, with a description
  - `conformance.md`: C6 gains the pass-through exercise, and C7 notes the passed-through exit
- [X] T003 `tools/agentio/agentio.py`, with units in `tests/unit/test_agentio.py`:
  1. **Pass-through:**
     - `Tool(passes_exit=False, …)`; the manifest carries `"passes_exit": true` when it is set
     - `Result(cause=None, command_exit=None)`; `cause` and `command_exit` are added to `RESERVED_KEYS`
       and are emitted in JSON whenever they are set
     - `_emit_result` admits an exit outside the vocabulary **only** when `tool.passes_exit`,
       `cause == "command"` and `exit == command_exit`. Otherwise it raises, as today
  2. **The argv split** (research R6), for pass-through tools:
     - Split at the first word that is not one of the tool's options, using the parser's option table
       for options that take a value, or at `--`
     - The rest goes to `args.command`
     - `--json` and `--verbose` are detected in the prefix only
  3. **Tool-supplied cut:**
     - `Result(cut=Cut(sections, omitted_lines, omitted_bytes, full_output, more))`
     - When `cut` is set, `agentio` does not re-cap. It prints the sections with their marker lines,
       then the exit line, the full-output line and the omission line (contract order). In JSON it
       carries `sections`, plus `truncated` with the tool's `more` and `full_output`
  4. **Units:**
     - A pass-through tool returning 42 is allowed
     - A non-pass-through tool returning 42 raises, and so does a pass-through tool returning 42
       with `cause="timeout"`
     - The split handles `run grep --json x`, `run --limit 5 -- --weird`, `run --timeout 3 sh -c …`,
       and an unknown run option, which gives exit 2
     - Cut rendering, text and JSON; the uncapped path is unchanged
     - Every existing `test_agentio` case still passes
- [X] T004 `tools/bin/timelike-conform`, with units in `tests/unit/test_conform.py` and
  `test_conform_violations.py`:
  - When the manifest says `passes_exit`, run `--json sh -c 'exit 42'` and require:
    - the exit is 42
    - `command_exit` is 42
    - `cause` is `command`
    - the verdict contains `42`
  - Exclude that probe's exit from the six-code C6 set
  - C7 matches the event's `exit` against 42
  - Fixtures, in `tests/fixtures/bad-tool/` or temp files:
    - a pass-through tool that exits 1 instead of 42 → `FAIL … C6`
    - a pass-through tool whose `command_exit` is missing → `FAIL … C6`
    - a tool that is **not** pass-through and exits 42 on its probe → `FAIL … C6`, as before

**Checkpoint:** 001's units all pass. `timelike-conform` over the stub `run` still fails, and it fails
on the right checks.

## Phase 3: US1 — run, conclude, pass the exit through (SC-5) 🎯 MVP

- [X] T005 [US1] `tools/bin/run`, its core, with units in `tests/unit/test_run.py`:
  - **Options:** `--timeout`, and `TIMELIKE_RUN_TIMEOUT` resolution with its source (R10). An invalid
    value is a usage error naming its source
  - **No command:** a usage error
  - **The log:** created `O_EXCL`, 0600, under `<scratch>/<session>/run/` (R12). If it cannot be
    created, exit 1 with an error naming the path, and run nothing
  - **The subreaper**, set through `ctypes`, at start (R3)
  - **Popen:** stdin `/dev/null`, stdout and stderr both on the log, `start_new_session=True`
  - **Exit mapping (R1):**
    - `-n` → 128+n
    - `FileNotFoundError` → 127
    - `PermissionError`, `IsADirectoryError` or ENOEXEC → 126
  - **The verdict line** (`contracts/run-cli.md`), with `cause` and `command_exit`
  - **Units:** exit 0, 1, 42, 127, 126 (a non-executable file), 137 (`sh -c 'kill -9 $$'`), the
    verdict's words, an empty command, a bad `--timeout`, a bad environment value, and an unwritable
    scratch space
- [X] T006 [US1] [P] `tests/e2e/run-exit-equals-the-wrapped-commands-exit-code.bats` (SC-5), under
  `bash -c` and `bash -lc`:
  - `$?` is 0, 1, 42, 127, 126 and 137
  - `--json` gives `cause` `command` and `command_exit` equal to the exit
  - also: `type -a run` resolves to exactly `/opt/timelike/bin/run` (R7, never shadow)

**Checkpoint:** `run sh -c 'exit 42'; echo $?` prints 42.

## Phase 4: US2 — the detached child (SC-3, D3)

- [X] T007 [US2] `tools/bin/run`, the detached-child detection (R5):
  - After the exit, reap, wait the 100 ms settle, then parent-walk the tree (skipping zombies) and add
    the write-holders of the log from `/proc/*/fd` + `fdinfo`
  - The verdict names each process as `detached: <pid> <comm>`, and JSON carries `detached`
  - Units, in a sandbox: a command that does `sh -c 'sleep 30 & echo $! > marker; exit 0'`. The test
    asserts the pid in the verdict equals the marker, that `run` returned in under 2 s, and then kills
    that pid
  - Also: a pure-`/proc` helper that is tested on synthetic stat lines
- [X] T008 [US2] [P] `tests/e2e/run-backgrounded-child-holding-stdout-verdict-within-2-seconds.bats`
  (SC-3):
  - The child holds stdout, for example `sh -c '(sleep 30; echo late) & echo $! > m; echo hi'`
  - The verdict arrives in under 2 s, measured with `date +%s%N` around the call
  - The pid in the verdict equals `m`
  - Cleanup kills the pid read from `m`

## Phase 5: US3 — timeout over the whole tree (SC-4)

- [X] T009 [US3] `tools/bin/run`, the stop sequence (R4):
  - SIGTERM to the tree, then a 2 s grace with reaping, then freeze rounds with SIGSTOP and re-scan,
    then SIGKILL + SIGCONT, then reap and re-scan until empty or 3 s pass
  - Exit 124, `cause` `timeout`, and the verdict names the limit, its source and both ways to raise it
  - Survivors are named under `not_stopped`
  - Units, in a sandbox:
    - a tree with a nested `timeout 50 …` and a `setsid sleep`, where each descendant touches a
      marker on a loop
    - after `run --timeout 1`, no marker changes for 1.5 s
    - SIGTERM-ignoring children (`trap '' TERM`) are still stopped
    - a fork loop is stopped
- [X] T010 [US3] [P] `tests/e2e/run-exceeding-its-timeout-exits-124-no-process-survives.bats` (SC-4):
  - Covers the nested `timeout` group, `setsid`, and `trap '' TERM`
  - Exit 124, and the verdict says `timeout`
  - Survival is checked by heartbeat markers: none advances after the call returns
  - The test's own runner limit is longer than the call's

## Phase 6: US4 — the display (SC-1, SC-2)

- [X] T011 [US4] `tools/bin/run`, the sections (R8, R9, R14):
  - Stream the log once: the count, head ⌊L/4⌋, the first errors ⌊L/10⌋ from the gap (numbered
    `L<n>:`), and the tail ⌊L/2⌋
  - The `sed -n` more command over the omitted ranges
  - Build `agentio.Cut` for capped output, and plain lines when the output fits
  - The error pattern set goes in the manifest (`error_patterns`) and is summarized in the help, which
    stays ≤ 40 lines
  - Units:
    - 5,000 lines with three errors: the order of the sections, the line numbers, and that running
      the more command prints exactly the omitted lines
    - 120 lines: printed whole, with no markers
    - `--limit 10` and `--limit 0`
    - CRLF and a final line with no newline
    - a 300 KB single line, cut at `COLUMNS`
    - an empty output
- [X] T012 [US4] [P] `tests/e2e/run-5000-lines-verdict-first-head-first-errors-tail-more-command.bats`
  (SC-1):
  - Line 2 is the verdict, and the head, the numbered errors, the tail and the more line appear in
    order
  - Running the printed more command reproduces the omitted lines, compared byte-for-byte with
    `sed` over the log
- [X] T013 [US4] [P] `tests/e2e/run-output-within-head-and-tail-printed-in-full.bats` (SC-2):
  - The output is the header, the verdict and every line, with no `── ` marker and no omission line

## Phase 7: Polish & cross-cutting

- [X] T014 Update the existing 001 e2e tests that enumerate tools:
  - `conformance-check-over-every-timelike-tool-on-path.bats` now counts 3 tools, including the
    pass-through probe
  - the guards test's checksum list (`agent-cannot-run-as-root-…bats:162`) gains `run`
  - also grep for any other place that hard-codes the tool set
  - List each one under `changed_other_features`
- [X] T015 `README.md`: a `run` section (P3, the place agents read):
  - what it is for, the synopsis, pass-through, the default limit and how to raise it, the detached
    child, and the more command
  - The `timelike` overview lists `run`, if it lists tools
- [X] T016 Host lane:
  - ruff, ruff format, mypy, shellcheck
  - units with coverage ≥ 90%, using reboot's covrc plus `/tmp/pytest-of-*/**/run`
  - `make test-host`
  - start-up of `run --help`, measured (budget < 100 ms p95)
  - Record the results in decisions
- [X] T017 `cycle-report.md` § Cycle 1 — `bridge/sends/03-rev1-20261001-043339.md`:
  - Group A: not applicable
  - Group B: copied from the send
  - The seven written fields, with SC-6 `unconfirmed`
  - `changed_other_features`: 001's contract, schemas, `agentio`, conform, and its e2e tool lists
  - The specswarm version: 2.21.0
  - Then hand the Docker lane to the mentor or operator

## Dependencies

- T001 → T002, T003, T004. T003 → T004 (conform uses the new manifest key)
- Phase 2 → US1 (T005) → US2 (T007) → US3 (T009) → US4 (T011). These tasks share `tools/bin/run`, so
  they run one after another
- The e2e tasks T006, T008, T010, T012 and T013 [P] depend only on `contracts/run-cli.md`. Each is a
  separate file, so they can be written alongside the implementation, by a delegate
- T014 and T015 come after T011, and T016 → T017

## Parallel execution

- **Delegate A:** T002 (contract text and schemas), while the main session does T003 and T004
- **Delegate B:** T006, T008, T010, T012 and T013 (the e2e files), from the CLI contract, while the
  main session does T005, T007, T009 and T011

## Implementation strategy

- **MVP:** Phase 2 + US1 (`run` passes the exit through and is conformant)
- Then US2 and US3, the P2 core, and then the display
- The image lane runs once, at the end (the mentor or operator)

---

## Phase 6: Cycle 2 — slice 1: memory, disk, redaction (send `bridge/sends/03-rev1-20261004-183704.md`, via `/specswarm:modify`, `--dispatch`)

<!-- Tech Stack Validation (Cycle 2): PASSED — plan § Tech Stack Compliance Report (Cycle 2): all approved, none added; tomllib, math, resource are stdlib -->

**Input:** spec § Slice 1, plan § Cycle 2, contracts/run-cli.md § Slice 1, research R15–R19,
data-model § Slice 1. **Tests are required** (H7). Same conventions as Cycle 1, with these additions:
- `implement --dispatch` commits per task.
- The scope is the files each task names.
- Every secret-shaped test value is generated at run time, never written as a literal.

**Story map:** US5 memory cause (SC-8, SC-11 D12) · US6 disk cause (SC-9) · US7 redaction (SC-10).

### Setup

- [ ] T018 The shared rule file and its two readers' wiring:
  - `image/rootfs/etc/timelike/redaction.toml`: `[extend] useDefault = true`, plus the 18 rules of spec
    FR-33, copied from gitleaks v8.30.1's `config/gitleaks.toml` and checked field by field, each with
    `tags = ["redact:<type>"]`;
  - `image/Dockerfile`: one `COPY --chmod=0644` to `/etc/timelike/redaction.toml`;
  - `scan/scan.sh`: the gitleaks step gains `--config /repo/image/rootfs/etc/timelike/redaction.toml`.

  Verify with the pinned binary (scratch): the config loads, and timelike's history has 0 findings.

### Tests first (from `contracts/run-cli.md` § Slice 1; delegated, disjoint files)

- [ ] T019 [P] [US7] `tests/unit/test_agentio_redaction.py` and `tests/unit/test_redaction_rules.py`:
  - the loader: valid, missing, unparsable, a bad tag or type, a non-compiling regex → `RulesUnavailable`;
  - the repository's file: 18 rules, unique ids, one redact tag each, `useDefault`;
  - `redact_text` per rule on generated values, entropy floors, allowlists, a multi-line private key
    keeping its line count;
  - the pass-through gate for `memory` and `disk`;
  - `Context.event_args` in the event.
- [ ] T020 [P] [US5] [US6] [US7] `tests/unit/test_run_slice1.py`:
  - memory over a fake cgroup directory (`TIMELIKE_CGROUP_ROOT`): rise and failure, rise and success,
    no rise, `max`, unreadable;
  - disk over fake statvfs and mountinfo, and the ENOSPC text;
  - redaction of the log, the header, the event, the verdict count, `log_rewritten`, a detached holder,
    and fail closed.
- [ ] T021 [P] [US5] [US6] [US7] The e2e files, one per criterion, each under `bash -c` and `bash -lc`:
  - `tests/e2e/run-killed-by-memory-limit-names-limit-and-peak.bats`: a throwaway with `--memory 96m
    --memory-swap 96m`;
  - `tests/e2e/run-full-scratch-or-workspace-names-filesystem-and-free-space.bats`: throwaways with
    `--tmpfs`, workspace and scratch;
  - `tests/e2e/run-secrets-redacted-in-shown-output-and-saved-log.bats`.

### Implementation

- [ ] T022 [US7] `tools/agentio/agentio.py`:
  - `RulesUnavailable`, `load_redaction_rules`, `RuleSet`, `redact_text`;
  - the pass-through gate (any `cause`, `command_exit == exit`);
  - `Context.event_args`.
- [ ] T023 [US5] `tools/bin/run`: the memory cause (FR-25 to FR-28).
- [ ] T024 [US6] `tools/bin/run`: the disk cause (FR-29 to FR-32).
- [ ] T025 [US7] `tools/bin/run`: redaction of the log, the shown lines, the header and the event
  arguments; the verdict count; fail closed; the manifest (FR-33 to FR-40).
- [ ] T026 The declared contract text and the place agents read:
  - `.specswarm/features/001-agent-shell-baseline/contracts/output-contract.md`: the pass-through
    paragraph and § Redaction;
  - `README.md`: the `run` section gains the causes and redaction.

### Polish

- [ ] T027 Host lane: ruff, ruff format, mypy, shellcheck; units with coverage (90% bar); `make test-host`;
  the new e2e on the host stand-in (advisory); `run --help` start-up. Results in `decisions.md`.
- [ ] T028 `cycle-report.md` § Cycle 2, implement step 10, and `.specswarm/metrics.json`.

### Dependencies (Cycle 2)

- T018 → T019, T022. T022 → T023 → T024 → T025 (one file, `tools/bin/run`) → T026 → T027 → T028.
- T019, T020 and T021 depend only on the contract, and run beside T022–T025 (delegates).
