# Cycle report — 012 verify changed (prompt 11)

> Append-only. One `## Cycle N — <send>` section per send built to acceptance; later verification goes in
> `### … addendum` sections. The mentor reads this file and never writes into it.

## Cycle 1 — bridge/sends/11-rev1-20261004-183704.md

**Written:** 2026-10-06. **Dispatch mode**, batch `20261004-183704`, prompt 8 of 8, the batch's last.
**specswarm 4.0.1-botbaubble.2.35.0** (`4ff8dcb`), the version this session loaded: the expanded commands
named that cache path (lore Q002). The path is the one the send names, so there is no second report.

**Built under discovery revision 13's rulings** (code-track § Resume after pause-06). Nothing here
mutates the workspace. Group B copies the send's `discovery_revision: 12`.

**Sequence:**
1. `git checkout -b 012-verify-changed 011-code-intelligence` (at `473be4a`).
2. `/specswarm:specify "11 verify changed" --from-send bridge/sends/11-rev1-20261004-183704.md --dispatch`
   (`d5c8e46`).
3. `/specswarm:plan` (`6ba52b8`): the fixtures were recorded here, because the research measured them.
4. `/specswarm:tasks` (`0f2d31e`).
5. `/specswarm:implement --dispatch`: T003 `d3befbc`, T001 `6680d51`, T002 `da0e940`, T004 `37b2489`,
   T005 `84f84e2`, T006 (this report, then the marker).

Each command was invoked, and its blocks were run from the installed file. Not `/specswarm:build`.
**Pushed nothing; merged nothing.**

**specify's allocation:**
- `FEATURE_DIR` = `.specswarm/features/012-verify-changed`;
- D84 held;
- PARENT_ROUTE `default` (`master`).

**The `$ARGUMENTS` expansion:** the argument string was
`"11 verify changed" --from-send bridge/sends/11-rev1-20261004-183704.md --dispatch`.
- The expansion pasted it into double quotes.
- **The stray quotes were in the description, not a path.**
- Run from the installed file, it parsed correctly.

**The seams, as decided in the spec:**
1. **Real recorded output.**
   - **Tests use real output only:** the parsers are tested against output recorded from the real
     runners: pytest 8.4.2, jest 30.5.2, vitest 5.0.3, go1.27.1, cargo 1.99.0, ruff 0.16.7, mypy 2.4.0,
     tsc 7.0.2 and eslint 10.12.0.
   - **Where it came from:** 14 recordings, each with a `.source` sidecar naming the runner, command,
     exit, generator, time and host. They were made by `tests/fixtures/verify/record.sh` on projects
     written by `make-project.sh`, which knows nothing of the parsers.
   - **The send's premise "pytest runs in the image" is false:** the image has no pytest, ruff or mypy.
     The e2e cells run the real ones through the image's uv at the `pins.env` versions, as the lane's
     unit and lint steps already do.
   - **Not added:** no tool was added to the image, so `make scan`'s inputs and the bench images are
     unchanged.
2. **Through 03's `run`:** every command goes through `run --json`, and `verify` reads `run`'s log.
   `verify test`'s exit is the command's (the pass-through gate).
3. **The affected set:** `symbols dependents`, **built against 011 at `6d523d4`** (its marker commit; the
   branch tip `473be4a` only adds reboot.md). It is called once per changed file, so each test's reason
   names the file it imports.

**Status in one line:**
- `verify test -- CMD` reports `N failed, M passed (format)`, with each failure's file, line, test name
  and first assertion lines, for pytest, jest, vitest, go test and cargo test. Anything else is
  `format unknown`, and the exit passes through.
- `verify changed` selects the tests importing a change, and lints and type-checks the changed files
  only, saying why. A check it cannot run fails the call.
- **Nothing has run in the image.**

### Group A — cited from `.implement-complete`

The marker is `.specswarm/features/012-verify-changed/.implement-complete`, written at the end of this run,
after this section's commit. No measured number is copied here.

| Field | In the marker |
|---|---|
| feature | present |
| completed_at | present |
| mode | present |
| tasks | present |
| tests | present |
| coverage | present |
| lint | present |
| decisions | present |
| scope | present |
| pause_file_written | present |

### Group B — copied from the send

| Field | Value |
|---|---|
| source_send | bridge/sends/11-rev1-20261004-183704.md |
| source_prompt | plan/.discover/prompts/11-verify-changed.md |
| prompt_revision | 1 |
| discovery_revision | 12 |
| slice | 1 |

The spec's frontmatter carries the same five values, with `audited_against: [1]`.

### Group C — written by the code instance

**delegations:** `[]`. Two general-purpose subagents wrote the tests (T001 units, T002 e2e) from the
contract. They are subagents, not delegations.

**criteria_reestablished**

Nothing has run in the image. Each citation matches exactly one line of the send (`grep -cF` = 1 for all
five).

- `11 · "and, for each failure, its file, line, test name and first assertion lines _(traces to: P2)_"`
  — **unconfirmed**. Docker lane pending;
  `tests/e2e/verify-pytest-3-failed-409-passed-file-line-name-assertion-lines.bats`, 4 cells, real
  pytest.
- `11 · "an unrecognised format falls back to the concluding-run verdict marked format unknown _(traces to: P2)_"`
  — **unconfirmed**. Docker lane pending;
  `tests/e2e/verify-parses-pytest-jest-vitest-go-cargo-unknown-format-falls-back.bats`, 18 cells.
  - **pytest** runs for real.
  - **jest, vitest, go and cargo** are not in the image, so their recorded output is replayed through
    `verify test -- cat FILE`.
- `11 · "lints and type-checks only changed files, and states which were selected and why _(traces to: P1)_"`
  — **unconfirmed**. Docker lane pending;
  `tests/e2e/verify-changed-one-source-file-runs-importing-tests-lints-changed-states-why.bats`, 4 cells,
  real pytest, ruff and mypy.
- `11 · "the changed-only check exits 0 and says nothing was selected _(traces to: P2)_"` —
  **unconfirmed**. Docker lane pending;
  `tests/e2e/verify-changed-no-changes-exits-0-nothing-selected.bats`, 6 cells.
- `11 · "receives failures with locations _(traces to: D20)_"` — **unconfirmed**. Manual (D20), after the
  lane. **For the demo:** the image has no pytest, so the operator brings one, either in the workspace's
  `.venv`, which `verify` looks in first, or as the e2e's uv wrappers do.

**On the host stand-in, 36 of 38 cells passed.**
- **The stand-in** is a scratchpad copy whose wrapper helper links this host's pytest, ruff and mypy
  instead of uv.
- **The other two** are the `type -a` cells, which only the image can pass.
- **What it shows:** evidence for the files' logic. It changes no mode above.

**reconcile_mode:** `full`. A new spec, from prompt revision 1 in whole, with `audited_against` seeded
`[1]`. Slice 2's flaky detection is out of scope.

**not_verified**
- **Everything in the image:**
  - the 38 e2e cells;
  - conformance over the image's tools (the probe is `verify true`);
  - the announcement's line for `verify`.
- **PyPI from inside the agent container,** which the wrappers need. The lane has proved PyPI access only
  for a throwaway container of the same image (the unit step).
- **jest, vitest, go, cargo, tsc and eslint run live by `verify`:** only their recorded output is parsed
  in tests. `changed`'s runner commands for them (`vitest run FILES`, `jest FILES`, `go test ./PKG`,
  `cargo test`, `eslint FILES`, `tsc --noEmit -p .`) are not exercised against real projects.
- **A deleted Python file's importers found by text:** units only, and absolute imports only.
- **The >50-file batched dependents path:** not tested.
- **D20.**

**changed_other_features**
- **None in code.** `run` (003) and `symbols` (011) are called as commands from the files beside
  `verify`. Their JSON results (`run`: `log`, `verdict`, `cause`, `command_exit`, `redaction`; `symbols
  dependents`: `path`, `depth`, `via`) are now interfaces `verify` depends on.
- **`tests/e2e/helpers.bash`:** one function appended, `install_uv_tool_wrappers`. Nothing existing was
  changed.
- **`Makefile`**, **`pyproject.toml`**, **`README.md`** (a verify section).
- **The announcement (007):** lists `verify` automatically.

**process_failures_recorded**
1. **T003 shipped nine deviations from the contract, which T001's delegate tests caught** before T001's
   commit:
   - no "failed so far" on a timeout;
   - the omission line named the wrong file;
   - assertion lines left in JSON when redaction was unavailable;
   - three ways `run` can fail that were not reported as `internal` results;
   - a deleted file not used;
   - a passing step's state.

   The `untested` shape was the ninth, and was settled by amending the contract. All are listed in T001's
   decisions.
2. **The verdicts could be cut by rule 13 at 200 columns,** taking a step's result or the
   `format unknown` clause with them. Found on the host stand-in, and fixed before T002's commit: the
   clause now comes first, and the lead is shorter. Spec FR-4 and the contract were amended.
3. **Two e2e header assertions assumed `verify: test …`;** the target is the command. Amended.
4. **The first vitest recording named this host's path** through the `node_modules` link (relative, so
   the scrub missed it). It was caught by reading it before commit. That project now uses ES modules, and
   `record.sh` refuses any recording that still names the host.
5. **T001, T002 and T003 recorded their start together** (the delegates ran beside T003), so T001's
   scope range includes T003's commit. Each start was read from git HEAD at the time, never composed.
   The record is true, and wider than the task.
6. **The host lane (T005) found three more tool defects:**
   - **Two events per call.** Each call appended two session events, failing conformance C7 (rule 16):
     `verify`'s, and the nested `run`'s. `symbols` adds one per changed file. Fixed by giving the
     children a scratch root inside the session's own scratch, without touching 001's `agentio`. A unit
     now guards it.
   - **A `conftest.py` under `tests/`** was handed to pytest as a test file. Fixed.
   - **`verify --help` was at p95 114 ms** against the 100 ms budget. It is 93 ms after replacing
     `dataclasses`.
7. **The traced unit run had one failure outside this feature:** `test_bench_runner.py` showed "setup
   failed: hung" under coverage tracing. It passes untraced 3 of 3, and bench is untouched. Recorded, not
   hidden, as 011 recorded `adele`'s.

**retired_prompts_seen:** none.

### Implement step 10 — quality validation (specswarm 2.35.0), as the library reported it

The output matches 011 § Cycle 1's apart from its timestamps (`diff` with timestamps masked: no
difference). Every component was excluded, `Quality Score: unknown — no component could be measured, so
there is no score to compare`, and `block_merge_on_failure=false`.

The gate is **UNKNOWN**. It warns and does not halt; dispatch never asks; nothing was filled in by hand.
The project's figures are beside it in `.specswarm/metrics.json` → `012.project_measurements_not_scored`.

**Host lane** (advisory; scratch venv, Python 3.12.3):
- **Units:**
  - 1639 passed (`make test-host`, before T005's 12 cases);
  - `test_verify.py` 73 passed after them;
  - traced: 1626 passed, 1 skipped, and 1 failed outside the feature (above).
- **Coverage:** Python **94%** (the traced run); `verify` 90% from its own tests, after the 12 cases.
- **Lint:** ruff, mypy strict (26 files) and shellcheck (the Makefile's 75 files): clean.
- **Conformance on the host:** 13 tools, pass.
- **Timings:** `verify --help` p95 93 ms; the probe `verify --json true` (through `run`) p95 191 ms.

**Implement step 9b: decision log** (installed `scope-tally` and `decision-tally`, after T005):

```
scope: planned=6 recorded=5 unplanned=0 unrecorded=1 in=5 out=0 none=0 unknown=0 flagged=4 flagged_out=0 other=1 other_out=0
decisions: sections=5 flagged_sections=4 non_flagged_sections=1 sections_without_absent=0 flagged=10 assumed=6 deferred=0 absent=5 inherited=5 low_confidence=0 flagged_low_confidence=0
```

- `unrecorded=1` is T006, this report. The marker's tallies are taken after it.
- There is no low-confidence entry, and no pause.

**For the batch:** this was prompt 8 of 8. The batch's final report goes to the mentor through the
operator, not into this file.


### Addendum 1 — lane batch-b's two 012 failures, and the cascade (2026-10-07T00:09:09Z, read from the clock)

- **Finding** (mentor, `../bridge/history.md` 2026-10-06T20:03:07Z, lane batch-b at `1dfc6b7`; log
  `bridge/.make-test-batch-b.log`). **Routed** by `bridge/feedback/batch-20261006-234535-lane-b-three-failures.md`,
  with its rulings (§ 2 and § 3 here; § 1 is on 009).
- **Unit `test_verify.py::test_not_found_steps_are_not_run_exit_1`** (log 2364–2559): its probe ran
  `python3` on `PATH=/usr/bin:/bin`. The image has none there, so it raised `FileNotFoundError` before
  reaching its claim. It passed on this instance's host, which has one. **Fix** (`2a0ca75`): guard the probe
  with `shutil.which("python3", path=bare)`. No `python3` there means verify's `python3 -m pytest` fallback
  (`find_pytest`) is unavailable too, so the precondition holds. Checked on the host, and under a "bare"
  PATH holding only `git`: **passes, not skipped** (`-rs` lists no skip), and the old probe reproduces the
  lane's `FileNotFoundError` there. The ruling's condition (it must run, not skip, in the image) is for the
  re-run's log to show.
- **not ok 432**, SC-4 `[bash -c]` JSON clean tree (log 2193–2203): verify's JSON was complete and correct
  with exit 0, and `jpy` failed after 33.7 s with no stderr. **Diagnosability only, as ruled** (`f6cf7da`):
  the five `verify-*.bats` files' `jpy` keep `pyq`'s exit status and stderr, and name exit 124 as the
  timeout, in the `flunk` message. No assertion and no timeout changed; the shared `pyq` in `helpers.bash`
  is untouched. The new `jpy` was run outside bats against a stubbed `pyq`: parsed, a parse error (exit 1
  with its traceback), exit 124 with stderr, and a hang killed by a real `timeout` (named). If the re-run
  passes, 432 goes down as **load-sensitive**, citing both lanes; if it fails, the message says how.
- **The cascade** (009's fix `2e3f483`): `010-services-interactive`, `011-code-intelligence` and this branch
  were rebased in that order, with no conflicts. 010 and 011 each gained an Addendum 1 naming their new
  hashes. This branch's 12 commits kept their subjects; the marker `d075404` is now **`4772706`**.
  Tips after the cascade, before this addendum: 009 `2e3f483`, 010 `dbe1959`, 011 `eb9d004`, 012 `f6cf7da`.
  This branch's tip is the commit that adds this addendum.
- **Process slip:** `2a0ca75` and `f6cf7da` were committed before the deny-list check ran. It ran over
  `f6cf7da` right after, before anything else: PASS (7 entries, 449 files, P1–P7 0/0).
- **Not verified here:** the six cells and the unit test in the image. They stay `unconfirmed` until the
  lane re-runs.

### Addendum 2 — the parser's bound: lane batch-b's 432 and lane batch-c's 448, one finding (2026-10-07T02:02:36Z, read from the clock)

- **Finding** (mentor, `../bridge/history.md` 2026-10-07T01:31:30Z, lane batch-c at `7aafbbb`; log
  `bridge/.make-test-batch-c.log` lines 2113–2124). **Routed** by
  `bridge/feedback/batch-20261006-234535-lane-b-three-failures.md` § Lane batch-c, Failure 4, with its ruling.
  Lane batch-c otherwise confirmed Addendum 1's fixes: ok 249 and 250, ok 432, and the unit test ran
  (1638 passed, 2 skipped, as before).
- **One finding, not two flakes:** not ok 432 in lane batch-b (`bridge/.make-test-batch-b.log` 2193, 33.7 s)
  and not ok 448 in lane batch-c (32.3 s). In both, verify's JSON was complete and correct, and `pyq`'s
  throwaway `docker run` was killed at `RUN_TIMEOUT` (30 s), the bound meant for the tools under test. The
  failure moves between 012's heavy cells (448's neighbours took 69 s and 81 s).
- **Why 143, and a defect in Addendum 1:** the runner image is `bats/bats` (Alpine), whose `timeout` is
  BusyBox's. It execs the command in its own process and has a grandchild send the signal
  (`coreutils/timeout.c`: `BB_EXECVP_or_die`, `kill(parent, signo)`), so a killed command reports **143**,
  never GNU's 124. Addendum 1's `jpy` named a timeout only on 124, so in the real runner it never could:
  448's message said "exited 143" and no more. The mentor read the 143 correctly from the source of the
  signal.
- **Fix, as ruled (the first option):**
  - `tests/e2e/helpers.bash` gains `PYQ_TIMEOUT="${PYQ_TIMEOUT:-120}"`, and `pyq` alone uses it.
  - `RUN_TIMEOUT`, every bound on a command under test, and every assertion are unchanged.
  - The five `verify-*.bats` `jpy` decide "timed out" by elapsed time against `PYQ_TIMEOUT` (as the Adele
    helper above `pyq` does with `SECONDS`), and print the exit and the elapsed milliseconds either way.
  - A timeout still fails the cell, and the message says so.
  - The parser stays in a throwaway container with no network; the ruling's alternative (parse inside the
    session container) was not taken.
- **Checked here** (no Docker): the new `jpy` outside bats against stubbed `pyq` with `PYQ_TIMEOUT=2`:
  - parsed;
  - a parse error (exit 1, 36 ms, not a timeout);
  - a BusyBox-shaped SIGTERM at the bound (143 after 2011 ms, named a timeout);
  - a GNU `timeout` (124 after 2008 ms, named);
  - a fast 143 (5 ms, not named).
  shellcheck is clean, and no bats per-test timeout caps the new bound.
- **Not verified here:** 432, 448 and their neighbours in the image. If they pass in the re-run, this finding
  is closed by the bound; if one fails, its message now gives its exit and time.

**changed_other_features (this addendum):** 001's `tests/e2e/helpers.bash`: `PYQ_TIMEOUT` (default 120 s) for
`pyq`, which 43 e2e files use. Only the parser's bound moves; no criterion's bound changes.

### Addendum 3 — D20 observed by the operator (2026-10-08T05:37:26Z, read from the clock)

From the mentor's observation entry in `../bridge/history.md` (2026-10-08T05:28:17Z) and the transcript
it cites, `bridge/.d20-demo-20261007T235014Z.txt` (bridge `d6c6e65`), which this instance read.

- `11 · "receives failures with locations _(traces to: D20)_"` — **observed by the operator**, by
  interview with the mentor instance on `verify`'s real output. The image was the one lane batch-d passed
  (revision `244c4a8`, `sha256:d0dd2058…`), run as a throwaway with `--cap-drop ALL`,
  `no-new-privileges` and `--init`. Each agent command was its own `docker exec … bash -lc`, as user
  `agent`.
  - **The project:** `~/shop`, committed: `app/models.py`, `app/orders.py` (which imports it), an
    unrelated `app/report.py`, and a test file for each. The project's `.venv` held real pytest 8.4.2,
    ruff 0.16.9 and mypy 2.3.1, the versions `pins.env` gives at `244c4a8`.
  - **The changes:** two `edit` calls on `app/models.py` introduced an off-by-one, an unused import and
    a wrong return type.
  - **`verify --text changed`:** `1 changed file · 2 test files importing a change … · pytest: 3 failed,
    0 passed · ruff: 1 diagnostic · mypy: 1 diagnostic`.
    - The selection came with its reasons: `tests/test_models.py` and `tests/test_orders.py` because each
      `imports app/models.py`; lint and type-check on `app/models.py` only.
    - Each failure has its file:line, test name and assertion lines (e.g. `tests/test_models.py:5
      test_total`, `assert 1001 == 1000`).
    - ruff gave `app/models.py:1:8 F401`, and mypy gave `app/models.py:16 return-value`.
    - Exit 1. The JSON form is recorded too.
  - **The mentor's direct run:** the whole suite gave 3 failed, 1 passed (`test_report`, which was
    correctly not selected); ruff and mypy found the same two diagnostics.
  - **Interview:** answers 3 and 4 matched. Answer 1 first read "left out" as verify's options, and answer
    2 first gave the transcript's own line numbers (56 and 57). The mentor challenged both, and the
    operator corrected both from the transcript (models and orders tested, report not; lint at line 1,
    type-check at line 16 of `app/models.py`). The operator accepts D20 as observed.
  - The criterion still resolves to exactly one line of the send (`grep -cF` = 1).
- **The transcript header also discloses** a discarded first capture (23:49:47Z): the mentor placed
  `--text` after the subcommand, and verify refused it with exit 2, as its help says global flags go
  first. That capture's project also lacked pytest's `pythonpath`.
- **With this, all eight demo points of batch `20261004-183704` are observed:** D12 (003), D14 (006),
  D4 (007), D6 (008), D17 (009), D18 (010), D19 (011) and D20 (012).
- **Where this record lives:** on `012-verify-changed`, the stack's tip, as with the D12, D14 and D4 addenda
  (`d932c1c`, `631a29e`, `eafd930`), so that `244c4a8..` stays records only and lane batch-d's evidence holds.
  The mentor's instruction allowed this placement provided it is stated (a branch per addendum was its
  first option). A revert of 012 by branch topology would carry this addendum with it.
