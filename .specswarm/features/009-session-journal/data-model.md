# Data model — 009 Session journal (prompt 08, slice 1)

## Tool event (001's `events.jsonl`, written by `agentio`; FR-6)

These are 001's fields:

| Field | Type | |
|---|---|---|
| `v` | 1 | |
| `tool` | string | |
| `args` | string[] | redacted (rule 15 key=value) |
| `cwd` | string | |
| `exit` | int | |
| `duration_ms` | int | |
| `session` | string | |
| `ts` | date-time | the end, seconds |
| `pid` | int | |

This feature adds these, all optional:

| Field | Type | |
|---|---|---|
| `t_ms` | int | the end, epoch ms |
| `ppid` | int | the tool's parent process |
| `agent` | string | `TIMELIKE_AGENT`, when valid |
| `ref` | object | one key: `log` (path) or `snapshot` (id) |

`Tool(event_ref=(kind, data_key))` declares the pointer. When `data[data_key]` is a non-empty string or
int, the event carries `ref: {kind: value}`.

| Tool | event_ref |
|---|---|
| `run` | `("log", "log")` |
| `snapshot`, `undo` | `("snapshot", "id")` |
| `adele` | none: the ledger row is its pointer |
| others | none |

## Shell entry (08's `shell.jsonl`, written by `/etc/timelike/journal-exit.bash`; FR-7)

| Field | Type | |
|---|---|---|
| `v` | 1 | |
| `kind` | `"shell"` | |
| `cmd` | string | `BASH_EXECUTION_STRING`, first 4096 characters, JSON-escaped (control bytes other than \n \t \r become `?`) |
| `cut_bytes` | int | characters cut (0 when whole) |
| `exit` | int | the shell's exit status |
| `start_us`, `end_us` | int | epoch µs (`EPOCHREALTIME`) at the hook and at exit |
| `pid`, `ppid` | int | `$$`, `$PPID` |
| `session` | string | |
| `agent` | string | `""` when unset or invalid |
| `cwd` | string | `$PWD` at exit |
| `style` | `"bash -c"` \| `"bash -lc"` | |

## Ledger row (004's `adeled ledger --json`; read only)

`id`, `at` (RFC 3339, s), `outcome` (`performed` | `refused` | `extended`), `grant`, `session`,
`capability`, `action`, `resource`, `cost_cents`, `expires_at`, `undo`, `limit_name`, `allowed`, `needed`.

## Entry (the journal's view)

| Field | From |
|---|---|
| `start`, `end` | tool: `t_ms - duration_ms`, `t_ms` (or `ts`); shell: `start_us`, `end_us`; ledger: `at` |
| `kind` | `tool`; `shell`; `grant` (an `adele` tool event, or a ledger row) |
| `style` | the shell entry's style, for a tool collapsed into it or nested under it |
| `agent`, `session` | the record's |
| `command` | tool: `tool` + `args`, shell-quoted; shell: `cmd`; ledger alone: `capability.action resource` |
| `exit` | the record's; a ledger-only row: its outcome |
| `ref` | the event's `ref`; a ledger row's `{ledger, outcome, grant}` |
| `children`, `collapsed` | linking (research R3) |

**Order:** `start`, then `end`, then record order (FR-3).
