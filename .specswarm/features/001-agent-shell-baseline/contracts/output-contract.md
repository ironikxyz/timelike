# Output contract — agentio v1

The contract every timelike tool obeys: rules 1–16 from the send, in every feature. `agentio` (the
shared Python module) implements it; `timelike-conform` verifies it. This file fixes the concrete
formats that the rules leave open, so the implementation and the conformance check read one source.

**Contract version:** `1`. A tool declares it in `--agent-info` as `"contract": 1`.

## Invocation surface (rules 1, 6, 8, 9, 11)

| Flag | Meaning | Required on |
|---|---|---|
| `--help` | Usage on stdout, **at most 40 lines**, exit 0. The first line is the header (rule 12) | every tool |
| `--json` | Force structured output, even on a terminal | every tool |
| `--text` | Force text output, even when piped | every tool |
| `--agent-info` | Print the manifest (`agent-info.schema.json`) as JSON, exit 0 | every tool |
| `--limit N` | Override the output cap, in lines. `0` means no cap | every tool |
| `--verbose` | May add timestamps, and a tool's timing of its own work. Nothing else may add them (rule 11). A duration a tool measures as its result (a wrapped command's run time) is not a timestamp | every tool |
| `--dry-run` | Print the plan and change nothing | tools whose manifest says `"destructive": true` |
| `--yes` | Confirm a mutation | tools whose manifest says `"mutating": true` |

**Mode selection (rule 1):** `--json` or `--text` if given. Otherwise JSON when stdout is not a
terminal, text when it is. Under a harness, stdout is always a pipe, so the default there is JSON.

## Exit codes (rule 5)

| Code | Name | Meaning |
|---|---|---|
| 0 | `ok` | Success. **Zero search results is 0**, with `"count": 0` |
| 1 | `failure` | The operation ran and failed |
| 2 | `usage` | Bad flags or arguments. stderr carries a structured error |
| 3 | `not_found` | Target not found, or the tool cannot decide |
| 4 | `confirm` | Confirmation or a grant is required. stdout carries one envelope, told apart by `status`: `confirmation_required` (`confirm-envelope.schema.json`, rule 9) or `grant_required` (`grant-envelope.schema.json`; discovery revision 10, changed in feature 004) |
| 124 | `timeout` | The tool's own time limit expired |

No other exit code is permitted from a timelike tool's own logic. An uncaught exception becomes exit 1
with a structured error. It is never a traceback on its own.

**Scope, and pass-through (discovery revision 9; changed in feature 003).** The vocabulary above covers
a tool's **own** outcomes. A tool that runs a command the agent named passes that command's exit
through, as `timeout(1)` and `env(1)` do. It returns the code the shell would have reported, including
126 (cannot execute), 127 (not found) and 128+n (killed by signal n), and 124 only when the tool's own
limit fired. Such a tool:
- declares it in its manifest, `"passes_exit": true` (`agent-info.schema.json`). `exit_codes` still
  lists only its own outcomes, from the vocabulary
- carries the difference in its output. The verdict names the cause in words, and the JSON object
  carries `cause` and `command_exit`:
  - `cause` is `command`, `timeout`, `usage` or `internal`. It is an open string, and later causes
    (for example `memory`, `disk`) are added without changing its shape
  - `command_exit` is the command's own code, or `null` when the command never ran or was stopped by
    the tool's limit
- returns a code outside the vocabulary only as the command's: `cause: command`, with the exit equal
  to `command_exit`

A usage error happens before anything runs, so it arrives as rule 14's error on stderr, with exit 2 and
no verdict. No 125 is added: the verdict and `cause` already carry what an extra code would.

## Header — first line (rule 12)

- **Text:** `<tool>: <target> [<scope>]`. The regex is `^[a-z][a-z0-9-]*: .+ \[[^]]+\]$`, for
  example `timelike: environment [agent-info]`.
- **JSON:** the top-level object's first three keys are `"tool"`, `"target"` and `"scope"`, in that
  order. For JSON, "first line" means these keys.

## Body and truncation (rules 2, 3, 13)

**Cut or not cut (discovery revision 6).** Rule 3's order is the shape of output a tool **cuts**. It
binds every tool that cuts, not a category of tool. Output that is not cut is printed whole after the
rule-12 header.

- The default cap is **200 lines** (`--limit N` overrides, and so does `TIMELIKE_OUTPUT_LIMIT`). Lines
  are cut at `COLUMNS` (default 200) with the marker ` …[cut N bytes]`.
- **The line cut applies in both modes** *(discovery revision 12, clarification; written into this
  contract by feature 006's cycle, declared)*. In JSON, each content string a tool emits in `lines` (a
  file line, a hit, a log line) is cut at `COLUMNS` with the same marker, and the object carries the
  bytes cut as data: `"cut_lines": [{"index": i, "cut_bytes": N}, …]`, indexes into `lines`, present only
  when something was cut. The serialised JSON stays valid. Verdicts, errors and data fields are not
  content and are not cut. Reading a long line whole is an explicit request: a tool may offer it per
  call (`view --columns 0`). Whether a call should also be bounded in total bytes stays a bench question
  (revision 6).
- Order when capped:
  1. header
  2. verdict line
  3. head
  4. first error(s)
  5. tail
  6. exit line
  7. the full-artefact path
  8. the omission line

  Nothing is cut out of the middle unannounced.
- **Omission line** (always the last line when capped):
  `… omitted <N> lines (<B> bytes) — full output: <path>; more: <exact command>`. It appears **only**
  when output was capped, so its absence means nothing was omitted.
- **JSON when capped:** the object carries
  `"truncated": {"omitted_lines": N, "omitted_bytes": B, "full_output": "<path>", "more": "<cmd>"}`.
  The JSON itself stays valid.
- ANSI escape sequences are stripped from everything a tool prints (rule 13).
- The full artefact is written under the session scratch space (rule 10).

**Predicting the last line (SC-11).** "Last line" means a predictable *kind* of line:

| Output | Last line |
|---|---|
| Capped text | the omission line |
| Uncapped text | the result's own last line. Nothing trails it, and there is no omission line |
| JSON | not a line. The object carries `exit`, and `truncated` when capped |

The first line is always the rule-12 header (text), or the `tool`, `target` and `scope` keys (JSON). The
exit code is one of those listed under *Exit codes*, or, for a tool whose manifest declares
`"passes_exit": true`, the command's own exit, with `cause: command` (discovery revision 9).

## Errors (rule 14)

- **With `--json`:** exactly one JSON object on stderr (`error.schema.json`).
- **Otherwise:** one line on stderr, `error: <what> (code N) — <remediation>`.

## Confirmation (rule 9)

A mutating tool run without `--yes` exits 4 and prints the envelope (`confirm-envelope.schema.json`)
on stdout. It names the plan and the exact command that confirms it. It never prompts, and it never
falls back to the terminal (rule 4).

**A missing grant is the other exit-4 envelope (discovery revision 10; changed in feature 004).** A
request beyond its grant prints `grant-envelope.schema.json` on stdout (`status: grant_required`):
`tool`, `target` and `scope` first (rule 12), then the grant, the exceeded `limit {name, allowed,
needed}`, `extend`, `extend_by: "operator"`, `performed: false` and the refused `request`. Its command
is the **operator's**, never the agent's: it is in `extend`, never in `confirm` or in any other field
the agent's habit runs, so rule 9's promise — the command in `confirm` is the agent's to run — holds
for every envelope. A tool that prints it declares `"envelopes": ["grant_required"]` in its manifest
and is not `--yes`-confirmed by the agent, because the grant is the confirmation (P4). Rule 8 still
binds it: anything destructive it exposes supports `--dry-run`. Each envelope keeps its own key order
on stdout; neither is sorted.

## Redaction (rule 15)

A redacted value is replaced with `[REDACTED:<type>]`, where `<type>` is one of `token`, `password`,
`key`, `secret` or `credential`. A value is never silently dropped. (Slice 0 ships the helper. Feature
03 supplies the rule set, shared with gitleaks.)

## Session event (rules 10, 16)

- **Session:** `TIMELIKE_SESSION` (default `default`), validated against `^[A-Za-z0-9._-]{1,64}$`.
  An invalid id is a usage error (exit 2).
- **Scratch space:** `${TIMELIKE_SCRATCH_ROOT:-/tmp/timelike}/<session>/`, created with mode `0700`.
- **Event log:** `<scratch>/events.jsonl`. Each invocation appends one line
  (`event.schema.json`) in a single `write()` on an `O_APPEND` descriptor, so concurrent writers within
  a session never interleave inside a line.
- **Failure to write the event is swallowed.** The tool's result and exit code are unchanged (FR-11).
  With `--verbose`, a warning goes to stderr.
- The event is written **after** the result, and it records the real exit code.

## Never (rule 4)

A tool never:
- reads stdin unless its manifest declares `"reads_stdin": true` and data is piped
- opens `/dev/tty`
- calls `isatty` to decide whether to prompt
- spawns a pager or an editor
- prompts
