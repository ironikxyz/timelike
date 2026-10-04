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

---

## Slice 1 (Cycle 2, send `bridge/sends/03-rev1-20261004-183704.md`)

### Environment
`TIMELIKE_REDACTION_RULES` (default `/etc/timelike/redaction.toml`), `TIMELIKE_CGROUP_ROOT` (default:
`/sys/fs/cgroup` joined with `/proc/self/cgroup`'s `0::` path; for tests).

### Exit and cause
| Exit | When | cause | command_exit |
|---|---|---|---|
| the command's code (not 0) | an OOM kill in the container during the command | `memory` | same |
| the command's code (not 0) | a full scratch or workspace filesystem, or the ENOSPC message in the output | `disk` | same |

Memory is tested before disk. Every other row is slice 0's.

### Verdict additions (in this order, after slice 0's parts)
```
… · OOM kill during the command (limit <L>, peak <P>)     only when cause is command and the command exited 0
… · memory: unknown (<file>: <reason>)                     only when killed by SIGKILL / exit 137 and unreadable
… · log may be incomplete                                  when the scratch filesystem is full
… · redacted <n> (<type> <n>, …)                           when anything was redacted
… · detached output after this is not kept                 when the log was rewritten while held
… · output withheld: redaction rules unavailable (<reason>); the log is unredacted
```
Cause words: `out of memory: limit <L>, peak <P>` (`<L>` may be `no limit`); `disk full: <mount> has
<free> free[, <mount> has <free> free]`; `disk full: "<message>" in the output; <mount> has <free> free,
<mount> has <free> free` (workspace, then scratch). Sizes are binary units with one decimal (`96.0 MiB`,
`0 B`).

### JSON `data` additions
```
"memory":    {"state": "read"|"unknown"|"not looked at", "limit_bytes": int|null, "peak_bytes": int|null,
              "oom_kills": int|null, "command_max_rss_bytes": int|null, "reason": str|null}
"disk":      [{"role": "workspace"|"scratch", "path": str, "mount": str|null, "free_bytes": int|null,
               "free_inodes": int|null, "full": bool}]          (empty when the command exited 0)
"redaction": {"state": "applied"|"unavailable", "counts": {"<type>": n}, "rules": str,
              "log_rewritten": bool, "reason": str|null}
```

### Manifest additions
`"redaction_rules": {"path": "/etc/timelike/redaction.toml", "ids": [...]}`, `"disk_full_bytes": 1048576`.

### agentio (001's module) additions
- `load_redaction_rules(path) -> RuleSet`. It raises `RulesUnavailable(reason)`.
- `redact_text(text, rules) -> (text, counts)`.
- `Context.event_args`: when a tool sets it, the session event records these arguments instead of argv.
- The pass-through gate: `exit == command_exit` with `command_exit` not null, for any `cause`.
