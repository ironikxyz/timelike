# CLI contract — `verify` (012, slice 1)

`verify` follows 001's output contract:
- the header `verify: <target> [<scope>]`, then `verdict: …`;
- JSON when stdout is not a terminal;
- `--json`, `--text`, `--limit`, `--verbose`, `--help` (≤ 40 lines), `--agent-info`;
- one session event per call, whose `ref` is `run`'s log (`test`) or the first step's log (`changed`).

```
verify test [--timeout S] -- CMD [ARG…]
verify changed [--since REF] [--timeout S] [--dry-run]
```

## Manifest

| Field | Value |
|---|---|
| `mutating` | `false` |
| `reads_stdin` | `false` |
| `takes_command` | `true` (`verify test`; argv split at the first `--`) |
| `passes_exit` | `true` (`verify test`) |
| `dry_run` | `true` (`verify changed --dry-run`) |
| `probe` | `["changed", "--dry-run"]` |
| `exit_codes` | `0` passed / nothing selected · `1` failures, a check not run, or `run` failed · `2` usage or not a repository · `124` a limit fired · any other: the command's own (`verify test`) |
| extra | `formats: ["pytest", "jest", "vitest", "go", "cargo"]`, `assertion_lines: 5`, `batch_dependents_over: 50` |

## test

| Outcome | Exit | Scope | Verdict |
|---|---|---|---|
| failures | the command's | `pytest` | `3 failed, 409 passed (pytest) · exit 1 · 0.6 s · log /…/run/….log` |
| all passed | 0 | `pytest` | `400 passed (pytest) · exit 0 · 0.6 s · log …` |
| go without `-v` | the command's | `go` | `3 failed, passes not reported (go test without -v) · exit 1 · …` |
| unknown format | the command's | `format unknown` | `<run's verdict> · format unknown: no pytest, jest, vitest, go test or cargo test summary` |
| timeout | 124 | the format, or `format unknown` | `… · timeout after 100 s (default); raise with --timeout or TIMELIKE_RUN_TIMEOUT · 2 failed so far` |
| `run` failed | 1 | `internal` | `run could not be started: /opt/timelike/bin/run: …` |

`run`'s further parts are appended as `run` words them: detached, memory, disk, redacted, and output
withheld.

**Body:** one block per failure, up to `--limit` blocks, then rule 3's omission line naming the log.

```
tests/test_models.py:26  tests/test_models.py::test_total_rounds
    AssertionError: 1 + 2 should round to 4
    assert 3 == 4
```

- **No location:** `(location not in the output)  NAME`.
- **Unknown format:** the body is `run`'s bounded lines.

**JSON data:**
- `format`, `counts: {failed, passed, skipped, errors}`, where a count the format does not report is
  `null`;
- `failures: [{test, file, line, lines}]`;
- `run: {exit, command_exit, cause, seconds, log, verdict}`;
- `withheld: bool`.

## changed

```
verify: changed against HEAD [2 tests, 1 lint, 1 type-check]
verdict: 1 changed file; selected tests importing a changed file directly or through one other file (a superset; text-based outside Python): 2 test files · pytest: 1 failed, 11 passed · ruff: 1 diagnostic · mypy: passed
changed   app/models.py (modified)
test      tests/test_models.py   imports app/models.py
test      tests/test_orders.py   imports app/orders.py, which imports app/models.py
lint      app/models.py          ruff
type      app/models.py          mypy
── pytest tests/test_models.py tests/test_orders.py · exit 1 · 0.4 s · log …
tests/test_models.py:26  tests/test_models.py::test_total_rounds
    assert 3 == 4
── ruff check --output-format concise app/models.py · exit 1 · log …
app/models.py:1:8  F401 `os` imported but unused
── mypy app/models.py · exit 0 · passed
```

| Outcome | Exit | Scope |
|---|---|---|
| no changes | 0 | `nothing selected` — verdict `no changes against HEAD: nothing selected, nothing run` |
| all passed | 0 | the selection |
| a failure, or a step not run | 1 | the selection |
| a step timed out | 124 | the selection |
| dry run | 0 | `dry run` — the selection and the commands, nothing run |
| not a git repository | 2 | — (usage error: `verify changed needs a git repository; use verify test -- CMD`) |
| `--since REF` unknown | 2 | — (usage error naming REF) |

- **The reason column:** `changed`, `imports X`, `imports Y, which imports X`, or `imports a changed file`
  (batched, more than 50 changed files).
- **A changed file with no importing test** is listed as `none      app/cli.py   no test imports it`.
- **Steps:** tests per runner (pytest, vitest or jest, go, cargo), then lint (ruff, eslint), then
  type-check (mypy, tsc).
  - **A step's state:** `passed`, `N failed`, `N diagnostics`, `not run: TOOL not found (looked in …)`,
    or `timed out`.
  - **tsc's diagnostics** are filtered to the changed files, and its state says how many were dropped.

**JSON data:**
- `against`;
- `changed: [{path, status}]`;
- `selected: {tests: [{path, reason, runner}], lint: [path], typecheck: [path], untested: [path]}`;
- `steps: [{kind, tool, command, state, exit, log, report}]`, where `report` has the shape of `test`'s
  data.
