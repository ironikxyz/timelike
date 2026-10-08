# Data model — 012 Verify changed

Nothing is stored. Every entity lives for one call, and only `run`'s logs outlive it, in the session
scratch.

| Entity | Fields | From |
|---|---|---|
| **RunResult** | exit, command_exit, cause, seconds, log, verdict, lines, withheld (redaction unavailable) | `run --json` |
| **Report** | format (`pytest` \| `jest` \| `vitest` \| `go` \| `cargo` \| `unknown`), counts {failed, passed, skipped, errors} (each int or null), failures [Failure] | the log, by R3 |
| **Failure** | test, file (or null), line (or null), lines (≤ 5) | the log |
| **Diagnostic** | file, line, col (or null), message, code (or null) | a linter's log |
| **Change** | path, status (`modified`, `added`, `deleted`, `renamed`, `untracked`) | git |
| **Selected test** | path, reason, runner | `symbols dependents`, the test-file rules |
| **Step** | kind (`test` \| `lint` \| `type`), tool, command, state, exit, log, report or diagnostics | R5 |

**State of a step:** `passed` · `failed` (N) · `diagnostics` (N) · `not run` (with the reason) ·
`timed out`.
