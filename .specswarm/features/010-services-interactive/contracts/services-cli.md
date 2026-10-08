# CLI contract — `services` (010, slice 1)

`services` follows 001's output contract:
- the header `services: <target> [<scope>]`, then `verdict: …`;
- JSON when stdout is not a terminal;
- `--json`, `--text`, `--limit`, `--verbose`, `--help` (≤ 40 lines), `--agent-info`, `--dry-run`, `--yes`;
- one session event per call, whose `ref` is the log path when there is one;
- rule 13 on lines, and rule 15 on log lines.

```
services start NAME [--port N] [--ready-log REGEX] [--timeout S] [--keep] [--cwd DIR] -- CMD [ARG…]
services stop NAME [--dry-run]                    this session's service (not confirmed)
services stop NAME --session S [--yes]            another session's (confirmed)
services stop --all [--yes]                       every service of this session (confirmed)
services list [--all-sessions]
services logs NAME [-n N] [--session S]
```

## Manifest

| Field | Value |
|---|---|
| `mutating` | `true` |
| `confirm_protocol` | `true` (`stop --session`, `stop --all`) |
| `destructive` | `true` |
| `dry_run` | `true` |
| `reads_stdin` | `false` |
| `envelopes` | `["confirmation_required"]` |
| `probe` | `["list"]` |
| `exit_codes` | `0` ok · `1` died, refused or survivors · `2` usage · `3` no such service · `4` confirmation required · `124` not ready in time |
| extra | `ready_timeout_s: 60`, `log_tail: 20`, `registry: "<scratch>/<session>/services/registry.json"`, `marker: "TIMELIKE_SERVICE"` |

## start

| Outcome | Exit | Scope | Verdict |
|---|---|---|---|
| ready (port) | 0 | `ready` | `web ready: pid 1234, port 8000 accepting, log /tmp/timelike/s/services/web.log (0.8 s)` |
| ready (log line) | 0 | `ready` | `web ready: pid 1234, log line matched /listening/, log … (1.2 s)` |
| ready (none) | 0 | `started` | `web started: pid 1234, readiness not checked (no --port or --ready-log), log …` |
| died | 1 | `died` | `web died before ready (exit 3) after 0.1 s; last 2 log lines below` |
| not ready | 124 | `not ready` | `web not ready after 60 s: port 8000 not accepting; stopped (use --keep to leave it running); last 20 log lines below` |
| port held | 1 | `refused` | `port 8000 is held by service web in session s, pid 1234; nothing started` |
| port held, unregistered | 1 | `refused` | `port 8000 is held by pid 999 (python3 -m http.server); nothing started` (or `by a process the agent cannot see`) |
| name live | 1 | `refused` | `web is already running in session s (pid 1234); stop it first or use another name` |
| command not found / not executable | 1 | `refused` | `cannot start web: CMD not found` / `not executable` |

- **Ready verdicts** add `; registered in session s (the scratch is disposable: rule 10)`.
- **The died and not-ready bodies** are the log's tail (redacted), with `do instead:` naming
  `services logs NAME`.
- **JSON data:** `name`, `session`, `pid`, `pgid`, `port`, `ready` (`port` | `log` | `none` | null), `log`,
  `seconds`, `exit_status` / `signal` (died; `exit` is agentio's own key), `tail` (died or not ready), `holder` (refused: `{name, session, pid}`
  or `{pid, command}`).

## stop

| Outcome | Exit | Scope | Verdict |
|---|---|---|---|
| stopped | 0 | `stopped` | `web stopped: 4 processes (1234, 1235, 1240, 1241), none remains; start again: services start web --port 8000 -- python3 -m http.server 8000` |
| already gone | 0 | `stopped` | `web had already ended (exit 3); entry removed` |
| survivors | 1 | `survivors` | `web: 1 process remains after SIGKILL: 1240 (sleep)` |
| dry run | 0 | `dry run` | `would stop web: 4 processes (…); nothing signalled` |
| confirm | 4 | — | the confirmation envelope (`plan`: one line per service and its pids) |
| no such service | 3 | `not found` | `no service web in session s`, with `do instead: services list` |

The JSON data carries `name`, `session`, `pids` (stopped), `survivors`, `restart` (the command), and
`removed`.

## list

```
services: s [3 services]
verdict: 3 services in session s: 1 running, 1 died, 1 unlisted
web     running   port 8000   pid 1234   up 2m14s   python3 -m http.server 8000
bad     died      port 8001   exit 3     ran 0.1s   sh -c 'echo boom >&2; exit 3'
old     unlisted  —           pid 2222   —          (a marker process with no registry entry: its records were cleared)
```

- **Uptime:** `up 2m14s` for a running service. A died one shows how long it ran when that is known,
  otherwise `—`.
- **JSON:** `services: [{name, session, state, port, pid, uptime_s, exit, command, log}]`.

## logs

`services logs NAME -n N`: the last N lines (default 50) of the log, redacted. Rule 3 applies when the log
is longer, and the full output is the log itself. A missing service is exit 3.
