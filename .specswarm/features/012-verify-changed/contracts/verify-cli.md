# CLI contract — `verify` (012, slice 1)

`verify` follows 001's output contract:
- the header `verify: <target> [<scope>]`, then `verdict: …`;
- JSON when stdout is not a terminal;
- `--json`, `--text`, `--limit`, `--verbose`, `--help` (≤ 40 lines), `--agent-info`;
- one session event per call, whose `ref` is `run`'s log (`test`) or the first step's log (`changed`).

```
verify test [--timeout S] -- CMD [ARG…]
verify CMD [ARG…]                         the same as verify test -- CMD (CMD is not test or changed)
verify changed [--since REF] [--timeout S] [--dry-run]
```

**Amended at implement:** agentio ends a pass-through tool's own options at the first plain word, so
`verify` reads its subcommand from that command itself.
- **Global flags** (`--json`, `--text`, `--limit`, `--verbose`) come before it.
- **A first word that is neither `test` nor `changed`** is the command. A command literally named `test`
  or `changed` is run as `verify test -- test …`.
- **`verify test`** with options and no `--` is a usage error.
- **`verify changed` outside a git repository** is a usage error: on stderr, exit 2 (rule 14).

## Manifest

| Field | Value |
|---|---|
| `mutating` | `false` |
| `reads_stdin` | `false` |
| `passes_exit` | `true` (`verify test`, and the bare `verify CMD`) |
| `dry_run` | `false`: agentio's `dry_run` is rule 8's for a destructive tool; `--dry-run` is an option of `changed` |
| `probe` | `["true"]`: `true` through `run`, format unknown, exit 0. It needs no repository, which conformance runs outside of |
| `exit_codes` | `0` passed / nothing selected · `1` failures, a check not run, or `run` failed · `2` usage or not a repository · `124` a limit fired · any other: the command's own (`verify test`) |
| extra | `formats: ["pytest", "jest", "vitest", "go", "cargo"]`, `assertion_lines: 5`, `batch_dependents_over: 50` |

## test

| Outcome | Exit | Scope | Verdict |
|---|---|---|---|
| failures | the command's | `pytest` | `3 failed, 409 passed (pytest) · exit 1 · 0.6 s · log /…/run/….log` |
| all passed | 0 | `pytest` | `400 passed (pytest) · exit 0 · 0.6 s · log …` |
| go without `-v` | the command's | `go` | `3 failed, passes not reported (go test without -v) · exit 1 · …` |
| unknown format | the command's | `format unknown` | `format unknown: no pytest, jest, vitest, go test or cargo test summary · <run's verdict>` (clause first: amended at implement) |
| timeout | 124 | the format, or `format unknown` | `… · timeout after 100 s (default); raise with --timeout or TIMELIKE_RUN_TIMEOUT · 2 failed so far` |
| `run` failed | 1 | `internal` | `run could not be started: /opt/timelike/bin/run: …`, or `run's result could not be read: /opt/timelike/bin/run exited 1: …` |

`run`'s further parts are appended as `run` words them: detached, memory, disk, redacted, and output
withheld.

**Body:** one block per failure. Past `--limit` lines, only whole blocks are kept, and rule 3's
omission line names `run`'s log as the full output. `more:` is the same `verify` call with `--limit 0`.

**Amended at implement:** `run`'s line count is dropped from the verdict, and so is its
`(command exited N)` when the command simply exited. Every other part is kept as `run` words it.
- **Redaction unavailable:** a failure's `lines` are empty in JSON as well as in text.

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
verdict: 1 changed file · 2 test files importing a change, directly or through one file: a superset · pytest: 1 failed, 11 passed · ruff: 1 diagnostic · mypy: passed (amended at implement: shorter, so rule 13 does not cut the steps; `(text-based outside Python)` is added only when a non-Python file changed)
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
  - **A step's state:** `passed`, `N failed, M passed`, `N diagnostic(s)`,
    `not run: TOOL not found (looked in …)`, `run failed: …`, or `timed out: <run's verdict>`.
  - **In the verdict,** a passed test step adds its counts: `pytest: passed (9 passed)`.
  - **tsc's diagnostics** are filtered to the changed files, and its state says how many were dropped.

**JSON data:**
- `against`;
- `changed: [{path, status}]`;
- `selected: {tests: [{path, reason, runner}], lint: [path], typecheck: [path], untested: [{path, reason}],
  batched}`. `untested` was amended from `[path]` at implement, because the reason is the point;
- `steps: [{kind (test | lint | type), tool, command, files, state, exit, log, report}]`, where `report`
  has the shape of `test`'s data.
  - **Lint and type steps** carry `diagnostics: [{file, line, col, message, code}]` and `dropped`.
  - Each diagnostic is also a `report.failures` entry: `{test: code, file, line, lines: [message]}`.

**Settled at implement:**
- **A deleted Python file:** 011's lookup resolves imports only to files that exist. So its importers are
  found by text (absolute imports: `import a.b`, `from a.b import`, `from a import b`), and theirs through
  `symbols`. A deleted file in another language is listed in `untested` with that reason.
- **The runners' caches:** an untracked path under `__pycache__`, `.pytest_cache`, `.mypy_cache` or
  `.ruff_cache` is not a change. A workspace that does not ignore them would otherwise list `verify`'s
  own leftovers on the next call.
