# Contract — `run` command line and output (slice 0)

## Synopsis
```
run [--timeout SECONDS] [--json|--text] [--limit N] [--verbose] [--] COMMAND [ARGS...]
run --help | --agent-info
```
`run`'s options end at the first word that is not one of its options, or at `--`. Everything after
is the command's argv, executed directly (no shell). Environment: `TIMELIKE_RUN_TIMEOUT` (seconds,
default 100), plus the contract's `TIMELIKE_SESSION`, `TIMELIKE_SCRATCH_ROOT`, `TIMELIKE_OUTPUT_LIMIT`,
`COLUMNS`.

## Exit
| Exit | When | cause | command_exit |
|---|---|---|---|
| the command's code (0–255) | the command ran and exited | `command` | same |
| 126 / 127 | the command could not be executed / was not found | `command` | same |
| 128+n | the command was killed by signal n (not by `run`) | `command` | same |
| 124 | `run`'s own limit fired | `timeout` | null |
| 2 | usage error, before anything runs (rule 14 stderr; no verdict) | — | — |
| 1 | `run` itself failed (rule 14 stderr if before the command; verdict `internal` after) | `internal` | null |

## Text output
```
run: <shell-quoted command> [run]
verdict: exit <E> (<cause words>) · <D> s · <N> lines · log <path>[ · detached: <pid> <name>, …][ · limit <T> s (<source>)]
<body>
```
Cause words: `command exited <c>`, `command killed by signal <n> (<NAME>)`, `command not found: <x>`,
`command not executable: <x>`, `timeout after <T> s (<source>); raise with --timeout or TIMELIKE_RUN_TIMEOUT`.

Uncapped body: the log's lines, nothing after. Capped body:
```
── lines 1–50 of 5000 ──
…
── first errors (lines 51–4900) ──
L123: error: …
── lines 4901–5000 of 5000 ──
…
more: sed -n 51,4900p <log>
exit: <E>
full output: <log>
… omitted <k> lines (<b> bytes) — full output: <log>; more: sed -n 51,4900p <log>
```
`<k>` and `<b>` count the gap's lines that were not printed (the shown error lines excluded). The more
command is one range over the whole gap, so it also re-prints those error lines (research R8).
At most five detached children are named in the verdict, then `(+N more)`; JSON `detached` has all.

## Manifest additions
`"passes_exit": true`, `"exit_codes": {"0": "…", "1": "…", "2": "usage", "124": "timeout"}`,
`"error_patterns": [...]`, `"probe": ["true"]`.
