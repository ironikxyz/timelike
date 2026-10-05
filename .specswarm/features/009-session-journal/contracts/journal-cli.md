# CLI contract — `journal` (009, slice 1)

`journal` follows 001's output contract:
- the header line `journal: <session> [<scope>]`, then `verdict: …`;
- JSON when stdout is not a terminal, text on a terminal;
- `--json`, `--text`, `--limit N`, `--verbose`, `--help` (≤ 40 lines), `--agent-info`;
- one session event per call;
- rule 13's line cut and rule 15's redaction on every printed line.

```
journal                         the last 20 entries of the current session, oldest first
journal -n N                    the last N entries
journal --all                   the whole session
journal --session S             another session (with -n / --all)
journal --all-sessions          every session the caller can read, merged, labelled by agent and session
journal --agent A               only agent A's entries (with any of the above)
journal --ledger FILE|-         merge `adeled ledger --json` rows as grant entries (- = stdin)
```

## Manifest

| Field | Value |
|---|---|
| `mutating` | `false` |
| `confirm_protocol` | `false` |
| `destructive` | `false` |
| `reads_stdin` | `true` (only `--ledger -`) |
| `probe` | `[]` (the current session; an empty one is exit 0) |
| `exit_codes` | `0` entries shown, or none found · `1` the ledger (`--ledger`) could not be read or is not a JSON array; an unreadable events or shell record is named in the verdict, exit 0 (§ Refusals) · `2` usage · `3` no such session |
| extra | `tail: 20`, `sources: ["events.jsonl", "shell.jsonl", "ledger (stdin or file)"]`, `captures: ["bash -c", "bash -lc"]`, `not_captured: ["sh -c", "interactive shells", "a command that sets its own EXIT trap", "direct exec"]` |

## Target, scope, verdict

- **Target:**
  - the session name;
  - `all sessions` with `--all-sessions`.
- **Scope:**
  - `last N of T` with `-n` or the default;
  - `all T` with `--all`.
- **Verdict:** `N of T entries in session S (K tools, M shell, G grants)`, plus additions joined with `; `:
  - `agents: a1, a2` when more than one agent appears;
  - `U unreadable lines skipped`;
  - `no agent recorded for X entries: separate agents with TIMELIKE_AGENT`, when the selection mixes
    known agents with entries that have none.
- **No records:** `no records for session S in <scratch>/S (the scratch is disposable: rule 10)`, exit 0,
  scope `none`.

## Text entries

```
journal: s1 [last 20 of 34]
verdict: 20 of 34 entries in session s1 (14 tools, 5 shell, 1 grant)
── last 20 of 34 ──
── 2026-10-05 ──
06:10:01.204  tool   bash -c  snapshot                         exit 0     0.41 s  snapshot 3
06:10:02.880  tool   bash -lc run -- make test                 exit 2    12.07 s  log /tmp/timelike/s1/run/…
06:10:15.002  shell  bash -c  make lint                        exit 2     3.20 s  —
06:10:19.311  shell  bash -c  for f in a b; do edit "$f" …     exit 0     0.30 s  —
06:10:19.320    tool          edit a --old x --new y           exit 0     0.08 s  —
06:10:19.410    tool          edit b --old x --new y           exit 0     0.08 s  —
06:10:22.700  grant  bash -c  adele standin.box create …       exit 0     0.22 s  ledger #4 performed demo
…
more: journal --all
exit: 0
```

- **Columns:** time (UTC, ms), kind, style (`bash -c`, `bash -lc`, or blank), command, exit, duration,
  pointer.
- **Date line:** a `── YYYY-MM-DD ──` line opens the entries and appears again where the date changes.
  A cut tail is preceded by rule 3's section label (`── last N of T ──`), as `agentio` prints every cut.
  Uncut output ends on its last entry (rule 2): the closing `more:`/`exit:` lines come only with a cut.
- **Labels:** with `--all-sessions`, or when more than one agent appears, each line gains `[agent/session]`
  after the time.
- **Pointers:**
  - `log <path>`;
  - `snapshot <id>`;
  - `ledger #<id> <outcome> <grant>`;
  - `—` when there is none.
- **A grant entry from the ledger alone** (no `adele` event matched) shows `—` for the style, the command
  as `<capability>.<action> <resource>`, and its outcome as its exit column (`performed`, `refused`,
  `extended`).
- **The cut (rule 3)** applies to entries:
  - `more:` is `journal --all` (with `--session`/`--agent` as given), or the earlier window
    `journal -n <N+20>`;
  - the omitted figures count entries and their text bytes;
  - the full output is an artefact in the session scratch.

## JSON

- **Data:** `session`, `sessions`, `agents`, `total`, `shown`, `counts {tool, shell, grant}`,
  `unreadable`, `sources {path: lines}`, and `entries`.
- **Each entry:**
  - `start` and `end`, ISO 8601 UTC with ms;
  - `kind`, `style`, `agent`, `session`, `command` (redacted), `exit`, `duration_ms`;
  - `ref`: `{"log": …}`, `{"snapshot": …}`, `{"ledger": id, "outcome", "grant"}`, or null;
  - `pid`, `ppid`;
  - `children` (the indexes of the tool entries nested under a shell entry);
  - `collapsed` (true when the shell line was folded into its tool).
- **`lines`:** the text lines above, without the date and label decoration.

## Refusals and errors

| Case | Exit | |
|---|---|---|
| `--session S`, no such directory | 3 | verdict on stdout, with `do instead: journal --all-sessions` |
| `--session` invalid name | 2 | usage error |
| `--ledger FILE` unreadable or not a JSON array | 1 | verdict naming the file and the reason |
| `--ledger -` and stdin is a terminal | 2 | usage error (rule 4: never wait on a terminal) |
| events.jsonl or shell.jsonl unreadable (permissions) | 0 | named in the verdict, entries from the other sources shown |
| a line that is not JSON, or not a record of either shape | 0 | skipped, counted (`unreadable`) |
