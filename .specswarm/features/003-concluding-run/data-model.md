# Data model — 003 Concluding run (slice 0)

No persistent state beyond the log file and the session event. Shapes below are what `run` holds in
memory and prints.

## Invocation
| Field | Type | Source | Rule |
|---|---|---|---|
| `command` | list[str], ≥ 1 | argv after `run`'s own options | Empty → usage error (exit 2) |
| `timeout_s` | float > 0 | `--timeout` > `TIMELIKE_RUN_TIMEOUT` > 100 | Invalid → usage error naming the source |
| `timeout_source` | `flag` \| `env` \| `default` | as above | Printed in the timeout verdict |
| `log_path` | absolute path | `<scratch>/<session>/run/<stamp>-<pid>.log` | Created `O_EXCL`, 0600 before the command starts |
| `started`, `ended` | monotonic float | `time.monotonic()` | `duration_s = ended - started` |

## Outcome
| Field | Type | Meaning |
|---|---|---|
| `cause` | `command` \| `timeout` \| `internal` (open string; slice 1 adds `memory`, `disk`) | Who decided the outcome |
| `command_exit` | int 0–255 \| null | The command's own code (126/127 for exec failures, 128+n for signal n); null on `timeout` and `internal` |
| `exit` | int | `command_exit` when cause is `command`; 124 for `timeout`; 1 for `internal` |
| `detached` | list[{pid:int, name:str}] sorted by pid | Tree members / write-holders of the log still alive after the command exited (cause `command` only) |
| `not_stopped` | list[{pid, name}] | After a timeout: anything still alive after the stop sequence (expected empty) |
| `lines` | int | Lines in the log at verdict time |

State transitions: `started → command` (process exited) → verdict; `started → timeout` (limit) → stop
sequence → verdict; exec failure → `command` with 126/127 immediately; failure inside `run` after the
log exists → `internal`.

## Display (capped case)
| Section | Lines | Content |
|---|---|---|
| head | ⌊L/4⌋ | log lines 1..h |
| first errors | ≤ ⌊L/10⌋ | first matches in (h, n−t], each `L<n>: <text>` |
| tail | ⌊L/2⌋ | log lines n−t+1..n |
| more | 1 | `sed -n A,Bp <log>`, one range over the gap (it re-prints the shown error lines) |

Uncapped (n ≤ L): the n lines, no markers.

## JSON result (`run --json`, after `tool`, `target`, `scope`)
`verdict` (str), `exit` (int), `cause` (str), `command_exit` (int|null), `duration_s` (float, 1 dp),
`line_count` (int), `log` (str), `timeout_s` (float), `detached` (list), `not_stopped` (list),
`lines` (shown lines, flattened across sections), `errors` (always `[]` for run: its error lines are
a section), `sections` (capped only: `[{"label","count"}]`, where the label states the range, e.g.
`lines 1–50 of 5000`; amended at T003), `truncated` (capped only, contract shape, with `more` = the sed
command and `full_output` = the log).

## Session event (unchanged shape)
One line per invocation; `exit` = the real exit code (may be outside the six for `run` — schema
amended, FR-22).
