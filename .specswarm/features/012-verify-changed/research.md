# Research — 012 Verify changed (prompt 11, slice 1)

Each entry gives the decision, the rationale and the alternatives. Everything was measured on the host
(Python 3.12) unless it says otherwise; the image (3.14.x) decides in the lane.

## R1 · Real recorded output, with each fixture's source named (seam 1, SC-1, SC-2)

**Two files, and neither knows how `verify` parses:**
- **`tests/fixtures/verify/make-project.sh KIND DIR`** writes a small project with a known number of tests
  and failures:
  - **pytest:** 412 tests, 3 failing;
  - **jest and vitest:** 12 each, 3 failing;
  - **go:** 12, 3 failing, one of them a subtest;
  - **cargo:** 12 unit tests (3 failing) and 2 integration tests;
  - **lint:** a ruff, a mypy, a tsc and an eslint finding.
- **`tests/fixtures/verify/record.sh OUTDIR`** (host only) runs the real runner on each project and keeps
  its output as `recorded/NAME.out`, with a `recorded/NAME.source` sidecar.
  - **The sidecar holds:** the runner and version, the command, the exit, the generator, the time from the
    clock, and the host.
  - **The output** is stdout and stderr together, as `run`'s log holds them, with `NO_COLOR=1` and no
    terminal.

**Recorded on 2026-10-06, the times in each sidecar:**

| Recording | Runner | Exit |
|---|---|---|
| `pytest-default`, `pytest-q`, `pytest-tb-short` | pytest 8.4.2 (Python 3.12.3, scratch venv) | 1 |
| `pytest-pass-one` | pytest 8.4.2, `tests/test_cli.py` only | 0 |
| `jest` | jest 30.5.2 (node 22.22.2) | 1 |
| `vitest` | vitest 5.0.3 | 1 |
| `go-test`, `go-test-v` | go1.27.1 | 1 |
| `cargo-test`, `cargo-test-no-fail-fast` | cargo 1.99.0 | 101 |
| `ruff` | ruff 0.16.7 | 1 |
| `mypy` | mypy 2.4.0 | 1 |
| `tsc` | tsc 7.0.2 | 1 |
| `eslint` | eslint 10.12.0 (default `stylish` format) | 1 |

**Paths.** Absolute paths are replaced before writing:
- the project directory becomes `<PROJECT>`;
- tool directories become `<TOOLS>`;
- the home directory becomes `<HOME>`.

`record.sh` then refuses to keep any recording that still names this host. The first vitest run did name
it, in a relative path through the `node_modules` link; that project now uses ES modules, as vitest
requires, and its recording names nothing.

**The send's premise "pytest runs in the image" is false.** The image has no pytest, ruff or mypy. The
lane's own steps fetch them with the pinned uv:
- the unit step uses `uv run --with pytest==PYTEST_VERSION`;
- the lint step uses `uv tool run ruff@… mypy@…`.

**So the e2e cells** put three wrappers on PATH in their own temporary directory. Each runs
`uv tool run --python /opt/timelike/python/bin/python3 TOOL@VERSION "$@"`, with the versions from
`pins.env`, which the runner container reads from the mounted repository. That is the real pytest, ruff
and mypy, in the image. It needs PyPI, as the unit step does.

**Not added to the image.** Adding pytest would change `make scan`'s inputs and the bench images. It would
also put a test runner in the agent's environment that the agent's own projects do not use (they bring
their own, in `.venv` or `node_modules`, which R5 looks in first).

**Alternatives:**
- **Hand-written fixtures:** P005 forbids them.
- **Replaying a recording in the e2e** (`verify test -- cat file`): the criterion says "running a pytest
  suite".
- **Skipping without pytest:** a skipped criterion is reported as passed by nobody, and as unknown by
  everyone.

## R2 · Through `run` (seam 2, FR-1, FR-5)

**`verify` runs** `run --json [--timeout S] -- CMD…`, with `run` from the file beside `verify` (resolved
through `__file__`, as `services` loads `run`'s helpers). Its JSON result carries:
- `exit`, `command_exit`, `cause`, `duration_s`, `timeout_s`;
- `log`;
- `verdict`, `lines`, `detached`;
- `redaction: {state, counts, reason}`.

**Measured on the host:** a 3-line command costs about 90 ms through `run`.

**Decision:**
- **The log is the input.** It holds stdout and stderr in order and, with the rules available, is
  already redacted (rule 15).
- **The exit** is `run`'s, unchanged. That makes the pass-through gate (`exit == command_exit`) hold for
  `verify test`, and a timeout stays 124 with `run`'s words.
- **Redaction unavailable:** `run` withholds output and leaves the log unredacted.
  - `verify` then prints the counts, test names and locations, which are the runner's own structure, not
    the program's data.
  - The assertion lines are withheld, and the verdict carries `run`'s withheld clause.
- **`run`'s verdict parts are carried:** detached children, memory, disk and timeout are appended as
  `run` words them.
- **`run` cannot be started, or its JSON cannot be read:** exit 1, `internal`, naming the path.

**Alternatives:**
- **Calling `run`'s functions in-process:** `run` is a script, not a module. Loading it, as `services`
  does for its process helpers, would make its whole main path an interface.
- **Running the command directly:** seam 2 forbids it.

## R3 · Identifying and reading each format (FR-1 to FR-4)

**Identification is by a format's concluding summary, never by the command's name.** `npm test` may run
jest, and `make test` may run pytest. A first match wins, in this order:

| Format | Summary | Failures | Location |
|---|---|---|---|
| pytest | `^=+ (.*) in [\d.]+s` or, with `-q`, `^\d+ (failed\|passed).* in [\d.]+s$`; counts are each `N word` | the `FAILED nodeid - msg` lines of the short summary; blocks under `_____ name _____` | the last `path:line:` in the block whose path is the node id's file (the test file's frame, not `app/orders.py:6`); `E ` lines are the assertion lines; with `--tb=short` the `path:line: in name` line |
| jest | `^Tests:\s+…\d+ total` | `● title › path` blocks | the first `at … (FILE:L:C)` whose file is the `FAIL` file; else the `> N \|` frame line |
| vitest | `^\s+Tests\s+.*\(\d+\)` | ` FAIL  file > title path` | the ` ❯ FILE:L:C` line whose file is the test file |
| go test | `^(ok\|FAIL)\s+\S+\s+[\d.]+s` or `^--- (FAIL\|PASS):` | `--- FAIL: Name` at any depth; a leaf failure is reported, and a parent failing only through its subtests is not | the `    file_test.go:N: msg` lines under (non-`-v`) or before (`-v`) the `--- FAIL` |
| cargo | `^test result: (ok\|FAILED)\. N passed; N failed; N ignored` | `---- name stdout ----` blocks | `panicked at FILE:L:C:` |

**Counts:**
- **pytest:** every `N word` of the summary (failed, passed, skipped, error/errors, xfailed, xpassed).
- **jest and vitest:** their `Tests` line.
- **go:** top-level `--- FAIL` and, with `-v`, top-level `--- PASS`. Without `-v`, passes are not reported,
  so `passed` is `null` and the verdict says so.
- **cargo:** the sum of every `test result:` line. `--no-fail-fast` gives three; a plain run stops after
  the failing binary, and gives one.

**Assertion lines:** up to 5, with surrounding blanks stripped.
- **pytest:** its `E ` lines.
- **jest:** the block's text before the code frame.
- **vitest:** the error line and its diff.
- **go:** the message lines.
- **cargo:** the lines after `panicked at`, up to the `note:` line.

**Measured on the recordings:** every recording is read in under 5 ms.

**Linter diagnostics** (R5's steps) are read the same way: `path:line[:col]: message` (ruff `concise`,
mypy), `path(line,col): error …` (tsc), and eslint's default `stylish` (a path line, then
`  L:C  error  message  rule`).

## R4 · The affected set (seam 3, FR-6, FR-7)

**The change set:**
- `git -c core.fsmonitor=false status --porcelain=v1 -z --untracked-files=all`. Renames are read as
  their new path; ignored files are not listed.
- **`--since REF`:** `git diff --name-status -z REF`, plus the untracked files.
- **`core.fsmonitor=false`:** a workspace's fsmonitor hook is not run by a read-only command (feature 005
  did the same).

**Dependents:** `symbols --json dependents FILE` from the file beside `verify`, **once per changed file**.
- **Why once per file:** 011's answer to several files does not say which file each dependent imports,
  and the reason must.
- **Cost:** with the index warm, one call is about 100 ms on the host, so 20 changed files cost about 2 s.
- **Past 50 changed files:** one call for all of them, with the reason `imports a changed file`. The
  verdict says so.
- **Built against 011 at `6d523d4`**, its marker commit.
- **Depth:** depth 1 is `imports X`; depth 2 is `imports Y, which imports X`, where `via` names Y.

**Test files:**
- Python: `test_*.py`, `*_test.py`, `conftest.py`, or anything under a `tests/` or `test/` directory;
- JS/TS: `*.test.*` and `*.spec.*`, or anything under `__tests__/`;
- Go: `*_test.go`;
- Rust: anything under `tests/`.

## R5 · Runners and linters, and "not run" (FR-8 to FR-11)

**Lookup, the first that exists:** the workspace's own tools (`.venv/bin/`, `node_modules/.bin/`), then
PATH. For pytest, `python3 -m pytest` is tried last, and only when `python3 -c 'import pytest'` succeeds.
- **Tests:** the selected files, grouped by language, one step per runner.
  - pytest: `pytest FILES`;
  - vitest: `vitest run FILES`;
  - jest: `jest FILES`;
  - go: `go test ./DIR…`;
  - cargo: `cargo test`.
- **Lint:** ruff `check --output-format concise`, eslint (default format).
- **Type-check:**
  - **mypy:** `mypy FILES`.
  - **tsc:** `tsc --noEmit -p .`. tsc checks a project, not files, so its diagnostics are filtered to the
    changed files, and the step says how many were dropped.

**A selected step whose tool is not found** is `not run: TOOL not found (looked in WHERE)`, and `changed`
exits 1. Not running a check is not passing it. This is the false "done" the prompt's WHY names.

**Alternatives:** exit 0 with a note. Rejected, because an agent reads exit 0 as verified.

## R6 · Name, probe and exits (FR-13, FR-11)

- **`verify`:** an agent "verifies" a change, and the word is free in the image. Debian's
  `trixie-slim` has no `verify` (a `type -a` cell checks).
- **The rejected names:**
  - `test`: a shell builtin;
  - `check`: too generic, and used by make targets;
  - `ci`: promises a pipeline.
- **The subcommands:** `test` (an agent's habit: "run the tests") and `changed`.
- **The probe:** `["changed", "--dry-run"]`. It is read-only, needs only git, and exits 2 outside a
  repository, which the conformance probe accepts as a usage answer.
- **The exits:**
  - **`verify test`:** `run`'s exit, with 2 for usage and 1 when `run` itself fails.
  - **`verify changed`:**
    - `0`: everything passed, or nothing was selected;
    - `1`: a failure, or a check not run;
    - `124`: a step hit its limit;
    - `2`: usage, or not a repository.

## R7 · Tests

- **Units (`tests/unit/test_verify.py`):**
  - every parser against every recording. The expected counts and names are written from the
    **projects**: "412 tests, 3 failing", the generator's own counts. Never from what the parser
    returned;
  - the change set and selection on git repositories the tests build;
  - `run` replaced by a stub only where the test is about `verify`'s handling of a `run` result (exit 1,
    unreadable JSON, redaction unavailable).
- **e2e:** one file per criterion, in the image, under `bash -c` and `bash -lc`, each cell with its own
  workspace and session:
  - **SC-1:** the real pytest on make-project.sh's pytest project;
  - **SC-2:** two parts. The real pytest in the image, with the other runners' recorded output passed
    through `verify test -- cat FILE`: real output, though not run in the image (named in
    `not_verified`). Then an unknown format, from a command the image has;
  - **SC-3:** an edit to `app/models.py` in a committed project, with pytest, ruff and mypy from the
    wrappers;
  - **SC-4:** a clean repository;
  - **the name and manifest.**
