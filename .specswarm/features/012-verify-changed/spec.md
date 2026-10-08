---
parent_branch: master
feature_number: "012"
status: In Progress
created_at: 2026-10-06T17:50:23+00:00
source_prompt: plan/.discover/prompts/11-verify-changed.md
source_send: bridge/sends/11-rev1-20261004-183704.md
prompt_revision: 1
discovery_revision: 12
audited_against: [1]
slice: 1
---

# Feature: Verify changed (prompt 11, slice 1: natural)

## Overview

Agents do run tests. The weakness is in what they read afterwards: a scroll of passing lines with the one
failure somewhere inside, or a full suite that takes long enough that the next edit lands first. `verify`
provides two commands, and both end in failures with locations (P2):

- **`verify test -- CMD [ARG…]`** runs a test command through 03's concluding run (`run`) and reports only
  the counts and the failures. Each failure comes with its file, line, test name and first assertion lines.
  Four runner formats are read: pytest, jest or vitest, go test and cargo test. Any other output falls back
  to `run`'s own verdict, marked `format unknown`. The command's exit passes through.
- **`verify changed`** takes the working changes and works out what they could have broken (P1):
  - the tests that import a changed file, found with 011's `symbols dependents`;
  - lint and type-check of the changed files only.

  It runs those, reports their failures the same way, and says what it selected and why. With no
  changes, it selects nothing and exits 0.

**Built under discovery revision 13's rulings** (code-track § Resume after pause-06). Nothing in this
feature mutates the workspace, so rule 9 does not apply.

**Flaky detection** (a failure that passes on repeat) is slice 2, and is not built here.

## The three seams (send), decided

1. **Runners not in the image: real recorded output.**
   - **Every parser is tested against output recorded from the real runner,** never written by hand.
   - **Where each was recorded:** on this host, from scratch toolchains:
     - pytest from a Python 3.12 venv;
     - jest and vitest from npm packages;
     - `go test` from the Go toolchain;
     - `cargo test` from rustup's stable toolchain;
     - ruff, mypy, tsc and eslint where they are reachable.
   - **Provenance:** each fixture has a sidecar naming the runner, its version, the command, the date
     (read from the clock) and the generator script that wrote the test project. Absolute paths in a
     capture are replaced by a documented placeholder (P2 of the deny-list).
   - **In the image:** the image has no pytest, ruff or mypy, which the send's "pytest runs in the image"
     assumed. The lane's own unit and lint steps fetch them with the pinned `uv` (`PYTEST_VERSION`,
     `RUFF_VERSION`, `MYPY_VERSION` in `pins.env`). The e2e cells do the same: they put small wrappers on
     PATH that call `uv tool run` with those pins. So the criteria run **real** pytest, ruff and mypy in
     the image, and need PyPI as the unit step already does.
   - **Nothing is added to the image**, so `make scan`'s inputs and the bench images do not change.
2. **Through 03's `run`.**
   - **Every command** is executed as `run --json [--timeout S] -- CMD…`, from the file beside `verify`.
     `verify` then reads the log `run` wrote, which is already redacted (rule 15).
   - **`verify test` passes the exit through:** `exit == command_exit`, 001's pass-through gate.
   - **Not re-implemented:** the concluding behaviour (time limit, detached children, memory and disk
     causes). Its verdict parts are carried into `verify`'s verdict.
3. **The affected set: 011's dependents lookup**, called as `symbols dependents --json FILE…` from the file
   beside `verify`.
   - **Built against 011 at `6d523d4`** (its marker commit). The branch tip, `473be4a`, only adds
     reboot.md on top.
   - **Direct and indirect dependents** (depth 2) both count, as 011 ranks them.
   - **The verdict says the set is a superset heuristic:** "tests importing a changed file, directly or
     through one other file (text-based for non-Python)".

## User Scenarios

### Actors
- **Agent** (primary): after an edit, checks exactly what the edit could have broken, and reads only the
  failures.

### Scenario 1: a suite with three failures (SC-1)
`verify test -- pytest` on a suite of 412 tests, 3 of which fail:
- **The verdict:** `3 failed, 409 passed (pytest)`, then `run`'s exit, duration and log path.
- **Below it:** one block per failure, `tests/test_orders.py:41  test_total_rounds` with its first
  assertion lines indented under it.
- **Passing tests:** not one line of passing output is shown.
- **Exit:** pytest's own exit (1).

### Scenario 2: other runners, and an unknown format (SC-2)
The same report comes from jest, vitest, go test and cargo test output, each read in its own format.
- **A command whose output matches none of them** (say, `make check`): the verdict is `run`'s verdict with
  `format unknown`, and the body is `run`'s bounded output.
- **Its exit:** passed through.

### Scenario 3: one changed source file (SC-3)
After editing `app/models.py`, `verify changed`:
- **finds the change** with git;
- **selects** the two test files that import it, one directly and one through `app/orders.py`;
- **runs** pytest on those two files only;
- **lints and type-checks** `app/models.py` only (ruff, mypy).

The verdict states the selection and the reason for each entry:
- `tests/test_models.py (imports app/models.py)`;
- `tests/test_orders.py (imports app/orders.py, which imports app/models.py)`;
- `lint: 1 changed file (ruff)`, `type-check: 1 changed file (mypy)`.

Then each step's failures, as in scenario 1.

### Scenario 4: nothing changed (SC-4)
`verify changed` on a clean tree: exit 0, `no changes against HEAD: nothing selected, nothing run`.

### Edge cases
- **Not inside a git repository:** `verify changed` exits 2 (usage), saying it needs one and naming
  `verify test -- CMD` as the alternative.
- **A changed test file** is itself selected (reason: `changed`).
- **A deleted file:** still used to find dependents, and not linted.
- **A changed file with no importing tests:** said per file (`app/cli.py: no test imports it`).
- **A runner, linter or type checker that cannot be found:**
  - the step is `not run: pytest not found (looked in .venv/bin and PATH)`;
  - `verify changed` exits 1, because a selected check that did not run is not a pass;
  - with no other failure, the verdict says only that.
- **Go and Rust:** selection is by package or crate, because neither runner selects tests by file.
  - **Go:** `go test` runs the packages of the changed files and of their dependents.
  - **Rust:** `cargo test` runs the crate.
  - The verdict says which, and why.
- **`--since REF`:** compare against a commit instead of HEAD. Untracked files still count.
- **`--dry-run`:** print the selection and run nothing.
- **More failures than `--limit`:** the first N blocks, then rule 3's omission line naming the log.
- **A runner killed by `run`'s limit:** exit 124, `run`'s timeout words, and the failures parsed so far.

## Functional Requirements

### verify test
- **FR-1** `verify test [--timeout S] -- CMD [ARG…]` runs `run --json [--timeout S] -- CMD…`, reads
  `run`'s result and log, and identifies the format.
  - **Identification** is by each format's concluding summary:
    - **pytest:** the `== … in Ns ==` line;
    - **jest:** `Tests:`;
    - **vitest:** `Tests  … (N)`;
    - **go test:** `ok`/`FAIL` package lines, or `--- FAIL`/`--- PASS`;
    - **cargo:** `test result:`.
  - **A first match wins,** in that order.
- **FR-2** **Counts:** failed, passed, and skipped where the format reports them.
  - **go test** without `-v` does not report passes. The verdict then says `passes not reported (go test
    without -v)`, and never `0 passed`.
  - **cargo** sums its per-binary `test result:` lines.
- **FR-3** **Each failure:**
  - **Its fields:**
    - `test`: the runner's own name, such as a pytest node id or a jest title path;
    - `file`, `line`: where the failure was raised in the test file, if the output says so, else where
      the test is defined;
    - `lines`: the first assertion lines, up to 5.
  - **No location in the output:** `file` and `line` are `null`, and the block says `location not in the
    output`.
- **FR-4** **Unknown format:**
  - **The verdict:** `format unknown: no pytest, jest, vitest, go test or cargo test summary`, then
    `run`'s verdict. *Amended at implement:* the clause was moved first, so rule 13's cut at 200 columns
    never takes it; `run`'s line count is dropped, as for every format.
  - **The body:** the log's head and tail, bounded by rule 3.
  - **Not a parse failure:** the counts are `null`, never zero.
- **FR-5** **Exit:** `run`'s exit, unchanged, which is the command's for any cause (the pass-through gate).
  `verify`'s own exits are only:
  - `2`: usage;
  - `1`: `run` could not be started or its result could not be read.

### verify changed
- **FR-6** **The change set:** `git -c core.fsmonitor=false status --porcelain -z --untracked-files=all`
  in the workspace (the git top level), against HEAD. With `--since REF`, it is
  `git diff --name-only -z REF` plus the untracked files.
  - **Renamed files** count under their new path.
  - **Ignored files** are not changes.
- **FR-7** **Tests selected:**
  - **Which files:** changed test files, and the test files among the dependents of the changed files.
    The dependents come from `symbols dependents --json` (direct and indirect).
  - **What is a test file:**
    - Python: `test_*.py`, `*_test.py`, or anything under a `tests/` or `test/` directory;
    - JS/TS: `*.test.*` and `*.spec.*`;
    - Go: `*_test.go`;
    - Rust: under `tests/`.
  - **Each selected file carries its reason:** `changed`, `imports X`, or `imports Y, which imports X`.
- **FR-8** **Runners per language**, the first found in the workspace's own tools and then on PATH:
  - **Python:** `.venv/bin/pytest`, then `pytest`, then `python3 -m pytest` only when importable. Run as
    `pytest FILES`.
  - **JS/TS:** `node_modules/.bin/vitest run FILES`, then `node_modules/.bin/jest FILES`.
  - **Go:** `go test` on the packages (directories) of the changed `.go` files and their dependents.
  - **Rust:** `cargo test` in the crate holding the changed `.rs` files.
- **FR-9** **Lint and type-check, changed files only** (not deleted ones):
  - **Python:** `ruff check --output-format concise FILES` and `mypy FILES`.
  - **JS/TS:** `eslint --format unix FILES`, and `tsc --noEmit -p .` (tsc checks a project, not files).
    tsc's diagnostics are filtered to the changed files, and the verdict says so.
  - **Lookup:** each tool is looked up as the runners are.
- **FR-10** **Every step runs through `run`**, one after another: tests, then lint, then type-check.
  - **Each step is reported:** its command, its result (`passed`, `N failed`, `N diagnostics`,
    `not run: …`, `timed out`), and its failures or diagnostics, each with `file:line`.
- **FR-11** **Exit:**
  - `0`: every selected step ran and passed, or nothing was selected;
  - `1`: a step failed, or a selected step could not run;
  - `124`: a step hit `run`'s limit;
  - `2`: usage, or not a git repository.

  **Why not pass through:** several commands cannot pass through one exit. Each step's own exit is in its
  report and in JSON.
- **FR-12** **`--dry-run`** prints the selection with its reasons and the commands it would run. It runs
  nothing, and exits 0.

### Contract
- **FR-13** **The name is `verify`.** A `type -a` cell checks that the image has no other `verify`.
  - **Manifest:** `mutating: false`, `reads_stdin: false`, `takes_command: true`, `passes_exit: true`
    (`verify test`), `dry_run: true`.
  - **Probe:** `["changed", "--dry-run"]`. It is read-only, and needs only git.
- **FR-14** **001's output contract applies:**
  - the header `verify: <target> [<format or scope>]`, then `verdict: …`;
  - JSON when stdout is not a terminal;
  - rule 3's bound;
  - one session event per call, whose `ref` is `run`'s log (or, for `changed`, the first step's log).

## Success Criteria

The criterion text is the send's, copied exactly.
- **Automated criteria:** one e2e file each in the image, under `bash -c` and `bash -lc`, against a
  project the test writes (P005). Each test checks with its own count, not the tool's.
- **Parsers:** units against the recorded fixtures.

- **SC-1** "Running a pytest suite with 3 failing and 409 passing tests reports "3 failed, 409 passed" and,
  for each failure, its file, line, test name and first assertion lines".
- **SC-2** "Failures are parsed for pytest, jest or vitest, go test and cargo test; an unrecognised format
  falls back to the concluding-run verdict marked format unknown".
- **SC-3** "With one changed source file, the changed-only check runs the tests that import it and lints
  and type-checks only changed files, and states which were selected and why".
- **SC-4** "With no changes, the changed-only check exits 0 and says nothing was selected".
- **SC-5** "DEMO: the Agent, after an edit, runs only the tests and lint affected by the change and
  receives failures with locations" (D20). Manual, after the lane.

## Key Entities

- **Run result:** command, exit, cause, seconds, log, and `run`'s verdict, all read from `run --json`.
- **Report:** format (`pytest` | `jest` | `vitest` | `go` | `cargo` | `unknown`), counts {failed, passed,
  skipped}, failures [Failure].
- **Failure:** test, file, line, lines.
- **Selection:** changed [path, status], tests [path, reason], lint [path], typecheck [path], steps
  [{kind, tool, command, state, report}].

## Decisions

| Point | Decision |
|---|---|
| Seam 1 | Parsers tested on real recorded runner output, each fixture's source named; in the image, real pytest/ruff/mypy via the pinned uv, as the lane's unit and lint steps do; nothing added to the image |
| Seam 2 | `run --json` for every command; the log is read after; `verify test` passes the exit through |
| Seam 3 | `symbols dependents --json`, 011 at `6d523d4`; direct and indirect; the verdict calls the set a superset heuristic |
| Name | `verify`, with `test` and `changed` |
| Not run | A selected check that cannot run makes `changed` exit 1: not running is not passing |

## Out of scope (slice 1)

- Flaky detection by repeats (slice 2).
- Selecting tests by symbol rather than by file.
- Any tool added to the image.
- Watch mode, and parallel steps.

## Assumptions

- **Readable output:** the runners' default text output, or output with the common flags (`-q`, `-v`,
  `--tb=short`). JUnit and JSON reporters are not needed in slice 1.
- **Git:** git is in the image (it is: features 005 and 011 use it).
