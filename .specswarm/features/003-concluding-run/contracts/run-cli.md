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
`/sys/fs/cgroup` joined with `/proc/self/cgroup`'s `0::` path; for tests), `TIMELIKE_RUN_DISK_FULL_BYTES`
(default 1048576: a filesystem with fewer free bytes is full; a non-negative integer, else usage exit 2).

**Detail the tests rely on:**
- `memory.events` is `key value` lines, and only `oom_kill` is read. `memory.max` is an integer or
  `max`, and `memory.peak` is an integer. A file that is absent or unreadable is named in `reason` as
  `<absolute path>: <strerror>`.
- `data.memory` is filled whenever a memory reading was attempted. It is attempted when the command
  did not exit 0, or when it was killed by SIGKILL. `state: "not looked at"` means the command exited
  0 and no OOM kill was counted. In that case the before and after readings were still taken, so an OOM
  kill under exit 0 is seen (FR-27).
- `data.disk` is checked only when the command did not exit 0. Otherwise it is `[]`.
- Sizes: `B`, `KiB`, `MiB`, `GiB`, `TiB`. Below 1 KiB they are written as an integer (`0 B`, `512 B`),
  otherwise with one decimal (`96.0 MiB`).
- Redaction counts the secrets replaced. A multi-line private key counts once.
- The verdict's `redacted` list is ordered by type name: `redacted 3 (credential 1, key 1, token 1)`.
- **Settled at implementation** (gaps the test delegates found):
  - **Two rules matching overlapping text:** the match starting first wins, and on a tie the longer one.
    The other is skipped, so one value is one secret.
  - **`event_args`:** the session event records `run`'s arguments redacted with the rule set, and
    agentio's flag-style redaction (`--token=…`) still applies on top.
  - **A rule whose allowlists hold only `paths`** loads with an empty allowlist. Output has no path.
  - **Rules unavailable** withholds the command line too. The header, JSON `target` and the event's
    arguments become `(withheld: redaction rules unavailable)`.
  - **A filesystem holding both the workspace and the scratch** is named once in the disk words.
  - **A malformed `memory.max` or `memory.peak`** gives `reason` `<path>: not a number of bytes: '<text>'`,
    and the words say `limit unknown`.
  - **An OOM kill under exit 0 with no limit** reads `OOM kill during the command (no limit set, peak <P>)`.
  - **"`data.…`"** in this section names the result's data fields. In JSON they are top-level keys, as
    in slice 0 (`memory`, `disk`, `redaction`, `log`).
  - **The header** is redacted after the command is joined (`shlex.join`). A secret, being one shell
    word of letters and digits, is unquoted, so the marker appears bare: `run: printf %s [REDACTED:token] [run]`.
  - **`redacted N` counts the log's secrets only.** A secret in the command line is redacted in the
    header and the event but not counted.
  - **Sizes at a unit boundary** follow the arithmetic: one decimal of the quotient in the first unit
    under 1024, so 1023.96 KiB prints as `1024.0 KiB`.
  - **A scratch filesystem smaller than the threshold** counts as full whenever a command fails. That
    is true of it: it has less than 1 MiB free.

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
Cause words: `out of memory: limit <L>, peak <P>` (with no limit: `out of memory: no limit set, peak <P>`); `disk full: <mount> has
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
