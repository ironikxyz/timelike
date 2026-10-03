---
parent_branch: master
feature_number: "003"
status: In Progress
created_at: 2026-10-01T04:45:29+00:00
source_prompt: plan/.discover/prompts/03-concluding-run.md
source_send: bridge/sends/03-rev1-20261001-043339.md
prompt_revision: 1
discovery_revision: 9
audited_against: [1]
slice: 0
---

# Feature: Concluding run (slice 0)

## Overview

`run` is a command wrapper. The agent puts it in front of any command whose output may be long or whose
behaviour may hang: `run make test`, `run npm install`, `run ./script.sh`. Whatever the command does,
`run` **concludes**. It returns within its time limit with a verdict that names the outcome and its
cause, followed by the part of the output worth reading. The full output is kept in a log the agent's
next command can open. That is P2, *every call concludes*, made into one tool.

What it fixes:
- **A hang caused by a backgrounded child.** `npm run dev &` inside a wrapped call keeps the output
  pipe open, and the call blocks until the harness kills it (G3: opencode #47350 hung for 1 h 44 m).
  `run` returns as soon as the command itself exits, and names the child still running.
- **A hang caused by the command itself.** At the time limit `run` stops the command's **whole**
  process tree, grandchildren included, and the verdict says *timeout*.
- **A silently cut middle.** Harnesses cut long output to its head or tail, which hides the first
  error. `run` shows the head, the **first error lines with their line numbers**, the tail, and the
  exact command that prints the rest of the log.
- **A lost exit code.** `$?` after `run cmd` is what it would have been after `cmd` (discovery
  revision 9), so `run make && next` keeps its meaning.

Discovery revision 8 (T4's clarification) already depends on this feature: when an agent discards
timelike's environment, *"P2 then rests on feature 03's concluding run and the harness's own
timeout."*

**Slices:**
- **Slice 0 (this spec, skeletal):** the verdict, head / first errors / tail, the detached child, the
  timeout over the whole tree, and exit pass-through.
- Slice 1 (not built here): memory and disk causes, and secret redaction in what is shown and stored.
- Slice 2 (not built here): log garbage collection, and detection of a repeated command.

The verdict's **cause** is an open field, so slice 1 can add `memory` and `disk` without changing its
shape.

**This cycle also changes feature 001's output contract** (plan's ruling on Item 9, discovery
revision 9: *"03's cycle may carry it, declared in 03's spec as touching 001's contract"*). See
**FR-20 to FR-24**. 001's spec is not edited, and its `audited_against` does not change here. It
records revision 9 through 001's own next modify cycle.

## User Scenarios

### Actors

- **Agent** (primary). Runs commands through a harness, from `bash -c` or `bash -lc`, and reads
  `$?` and the printed output. The agent is not watching a terminal.
- **Harness** (autonomous intermediary). Runs each agent call with its own time limit (Claude Code:
  120 s) and kills the call when that limit expires.
- **Operator** (administrative). Reads the output in the D3 demo and judges whether the agent could
  act on it.

### Scenario 1: A command with long output (SC-1, SC-2)

1. The agent runs `run make test`. The tests print 5,000 lines, and three of them are errors.
2. `run` prints its header, then one verdict line: the exit code, the duration, the line count and
   the log path.
3. Then come the first lines, the first error lines (each with its line number in the log), the last
   lines, and the exact command that prints the lines not shown.
4. The agent reads the first error and fixes it without running the tests again just to find it.
5. If the whole output fits within the head and tail, `run` prints all of it, with no section markers.

### Scenario 2: A command that backgrounds a child (SC-3, DEMO → D3, SC-6)

1. The agent runs `run ./start-server.sh`. The script starts a server in the background and exits 0.
   The server keeps the inherited stdout open.
2. Within 2 seconds `run` returns the verdict: exit 0, and the server's process ID, named as a
   detached child still running.
3. The agent gets its turn back, and the server stays up. `run` does not kill a child the command
   deliberately left running.

### Scenario 3: A command that hangs (SC-4)

1. The agent runs `run ./hangs.sh`, under a 5-second limit. The script starts children, and one of
   them starts its own `timeout` (which leads a new process group).
2. At the limit, `run` stops every process in the command's tree, grandchildren and nested process
   groups included.
3. `run` exits 124. The verdict says *timeout*, names the limit and says how to raise it.
4. No process from that tree is left behind.

### Scenario 4: Exit pass-through (SC-5)

1. The agent runs `run sh -c 'exit 42'`, and then `run no-such-command`.
2. `$?` is 42 for the first and 127 for the second: what the shell would have reported without `run`.
   A command killed by signal *n* gives 128+*n*.
3. The verdict names the cause in words (*"command exited 42"*, *"command not found: no-such-command"*),
   and the JSON carries `cause: "command"` and `command_exit`.

### Edge cases

- **The command cannot be executed** (not found, or not executable): exit 127 or 126, cause
  `command`, and `command_exit` set to the same code. It is not a failure of the tool itself.
- **The command's own exit collides with one of the tool's codes** (it exits 2 or 124 by itself).
  `$?` alone cannot tell them apart; the verdict and `cause` can. A real timeout is `cause: timeout`.
  A usage error happens before anything runs, so it arrives as rule 14's stderr error with no verdict.
- **No command given:** a usage error (exit 2), and nothing runs.
- **The command reads stdin.** It gets end-of-file immediately, so a prompt ends instead of waiting for
  an answer nobody will type (rule 4, P2).
- **The command writes no output:** the verdict says 0 lines, and nothing else follows.
- **The command never ends a line, or writes a very long one:** each line is cut at `COLUMNS` as in
  every timelike tool. The log keeps it whole.
- **A detached child is still writing when `run` returns.** Its output keeps going to the same log, and
  the verdict says so. The line count is as of the moment the verdict was written.
- **A child escapes the command's process group** (it calls `setsid`, or a nested `timeout` starts its
  own group). On timeout it is still stopped, because the whole tree is tracked, not one group. On
  normal exit it is named as a detached child if it is still running.
- **The time limit is raised past the harness's own limit.** That is allowed, and the help says what it
  risks: the harness then kills the call before `run` can conclude it.
- **Invalid time limit** (not a positive number): a usage error naming the value.
- **The scratch space cannot be written** (the log cannot be created): the command does not run. The
  tool fails with exit 1 and a structured error naming the path. It never runs a command whose output
  it cannot keep.

## Functional Requirements

### Invocation

- **FR-1:** The tool is named `run`, is on the agent's `PATH` in `/opt/timelike/bin`, and is the only
  `run` on that `PATH`. It shadows no existing command (discovery, Assumed Constraints: "new names,
  never shadow"). It is named after a habit agents were trained on (P3): the research bundle's own
  specification calls it `run`, and so does discovery revision 6.
- **FR-2:** `run [run-options] COMMAND [ARGS...]`. `run`'s own options come before the command, and
  everything from the first non-option word on is the command, passed as an argument vector, as
  `timeout(1)` and `env(1)` do. A command needing shell syntax is written `run bash -c '...'`. `--`
  ends `run`'s options explicitly.
- **FR-3:** Every contract flag applies to `run` itself: `--help`, `--json`, `--text`, `--agent-info`,
  `--limit N`, `--verbose`. A flag after the command belongs to the command: `run grep --json x` passes
  `--json` to `grep`.
- **FR-4:** The command's stdin is empty (end-of-file at once). Its stdout and stderr both go, in order,
  to one log.

### Time limit

- **FR-5:** The default limit is **100 seconds**. That is below the harness's 120 s call limit, with
  room to stop the tree and print the verdict (P2). It is set by `TIMELIKE_RUN_TIMEOUT` (seconds) and
  overridden by `--timeout SECONDS`. Fractions are allowed.
- **FR-6:** At the limit, `run` stops **every process descended from the command**: its process group,
  any nested process group or session a descendant started, and any orphan re-parented while the
  command ran. It asks politely first and then forces, within a short grace period. It then confirms
  that none of those processes remain before writing the verdict.
- **FR-7:** On timeout, `run` exits **124**. The verdict says `timeout`, names the limit, and names both
  ways to raise it. It never suggests skipping the work (the T4 precedent).

### Concluding

- **FR-8:** `run` returns when the command's own process exits. It never waits for end-of-file on the
  command's output.
- **FR-9:** When the command has exited but processes it started are still running, `run` names each by
  process ID and command name as a **detached child**. Its verdict comes within 2 seconds of the
  command's exit. `run` does not stop these processes: the agent may have meant to leave them running.
- **FR-10:** Detached children are found by looking at the processes themselves (what is still running
  in the command's tree, and which processes hold the log open), never by matching command lines
  (cycle 5 process failure 2).

### Output

- **FR-11:** Line 1 is the contract's header, `run: <command> [run]`. Line 2 is the verdict. "A verdict
  line first" in the prompt means first after the header: the header is the contract's own first line
  (rule 12, § Body and truncation order 1–2). In JSON, `tool`, `target` and `scope` come first, then
  `verdict`.
- **FR-12:** The verdict line gives the exit code, the cause, the duration, the number of lines and the
  log path. Detached children and the time limit are added when they apply. For example:
  `verdict: exit 1 (command exited 1) · 4.2 s · 5000 lines · log /tmp/timelike/default/run/…/output.log`.
- **FR-13:** When the output exceeds the cap (the contract's 200 lines, or `--limit`), the body is, in
  order:
  - the **head**: the first 50 lines
  - the **first errors**: up to 20 lines from beyond the head that look like errors, each prefixed
    with its line number in the log
  - the **tail**: the last 100 lines
  - the exact command that prints the lines that were not shown, which reads the log; it never runs
    the command again
  - then the contract's exit line, full-artefact line and omission line

  Each section is labelled with its line range.
- **FR-14:** "Looks like an error" is a fixed, documented, case-sensitive pattern set (for example
  `error`, `Error`, `ERROR`, `FAIL`, `fatal`, `Traceback`, `panic`, `Exception`, `not found`,
  `denied`). The command's stdout and stderr share one log, so stream is not the test. The pattern set
  is listed in `--help` and in `--agent-info`.
- **FR-15:** When the whole output fits within the cap, it is printed in full, with no section markers,
  no omission line, and nothing after its last line (the contract's uncapped case, discovery revision
  6).
- **FR-16:** The log holds the command's complete output, unchanged except for its line endings. It is
  written under the session scratch space, `${TIMELIKE_SCRATCH_ROOT:-/tmp/timelike}/<session>/run/`.
  The path in the verdict is absolute, and it is the same path the agent's next command opens
  (cross-stack P002). Slice 0 does not remove old logs; slice 2 does.

### Exit and cause (discovery revision 9)

- **FR-17:** `run`'s exit code is the command's: what `$?` would have been had the agent run the
  command directly. That includes 126 (cannot execute), 127 (not found) and 128+*n* (killed by
  signal *n*). It is **124** only when `run`'s own limit fired. `run`'s own outcomes keep the contract
  vocabulary: 2 for usage, 1 for its own failure.
- **FR-18:** Every verdict carries a **cause**: `command` (the command ran and exited, whatever its
  code), `timeout` (`run`'s own limit), or `internal` (`run` itself failed after starting). In JSON:
  `cause`, and `command_exit` (the command's own code, or `null` when it never ran or was stopped at
  the limit). `usage` is a cause in the contract's sense too, but it is reported only as rule 14's
  error, because no verdict exists. Slice 1 adds `memory` and `disk`. The field is a string, open to
  new values.
- **FR-19:** `run`'s manifest declares the pass-through (FR-21) and lists its own codes (0, 1, 2, 124)
  under `exit_codes`. `--help` says that the command's exit passes through.

### Changes to feature 001's contract (carried by this cycle)

These come from plan's ruling on Item 9, and each is listed under `changed_other_features` in the cycle
report.

- **FR-20 — `output-contract.md`:** § Exit codes states the scope: the vocabulary covers a tool's
  **own** outcomes. It adds the pass-through rule and `cause` / `command_exit`. Line 83's "always one of
  those listed" is reworded to the tool's own outcomes, and to the command's exit for a tool that
  declares pass-through.
- **FR-21 — `agent-info.schema.json`:** a manifest may carry `"passes_exit": true`. `exit_codes` stays
  an enum of the six codes, for the tool's own outcomes.
- **FR-22 — `event.schema.json`:** an event's `exit` stays the real exit code (rule 16). For a
  pass-through tool that may be any code from 0 to 255. Without this, every `run` that passes a 42
  through would write an event that fails C7.
- **FR-23 — `agentio`:** a tool that declares pass-through may return a command's exit code outside the
  vocabulary, and only as that command's exit (`command_exit`, with `cause: command`). `Tool.codes()`
  still rejects a non-vocabulary code among a tool's own. A tool that does not declare pass-through
  cannot return one.
- **FR-24 — Conformance (C6, `timelike-conform`):** a tool whose manifest declares pass-through is also
  run wrapping a command that exits outside the vocabulary, `sh -c 'exit 42'`. Its exit must be 42, its
  JSON `command_exit` 42 and `cause` `command`, and its verdict must name 42. A probe that only ever
  exits 0 cannot pass a pass-through tool (the blind spot found in Item 9). Tools that do not declare
  pass-through are checked as before.

## Success Criteria

Each criterion of the send's slice 0 maps to one test, named after its distinguishing text (stack:
"one test per acceptance criterion"). The criterion text is the send's, copied exactly.

### Automated

- **SC-1:** "Running a command that prints 5,000 lines returns a verdict line first, then the first
  lines, the first error lines with their line numbers, the last lines, and the exact command to view
  the rest". Running that command prints exactly the lines it names.
- **SC-2:** "When the whole output fits within the head and tail, it is printed in full with no section
  markers".
- **SC-3:** "A command that backgrounds a child holding stdout and then exits returns its verdict within
  2 seconds and names the detached child's process ID". The ID named is the child's. That is checked
  against a file the child itself wrote, not by matching command lines.
- **SC-4:** "A command exceeding its timeout exits 124, the verdict says timeout, and no process from its
  process group survives". The nested case is included: a descendant that leads its own process group
  (a nested `timeout`). Survival is checked by a marker each descendant would write if still alive.
- **SC-5:** "The tool's exit code equals the wrapped command's exit code". This covers 0, 1, 42, 127
  (not found), 126 (not executable) and 137 (killed by SIGKILL).
- **SC-7 (contract, FR-20 to FR-24):** `timelike-conform` passes `run`, including the pass-through
  exercise, and still passes every existing tool. A pass-through tool that returned 1 instead of 42 is
  reported as failing C6. The unit tests show that a tool which does not declare pass-through cannot
  return 42.

Every automated criterion runs end-to-end in the image, under `bash -c` and `bash -lc` (the stack's
invocation styles).

### Manual

- **SC-6:** "DEMO: the Agent runs a command that backgrounds a child process and immediately receives a
  verdict with exit code and log path" (D3). The mentor interviews the operator on `run`'s real output
  after the Docker lane, as for 002's D2. The criterion stays `unconfirmed` until then.

### Measurable outcomes

- A backgrounded child holding the output adds at most 2 seconds to a call. Without `run`, it adds the
  harness's whole time limit.
- A hang ends at the configured limit (100 s by default) plus a grace period of at most 5 seconds, and
  no process from the tree remains.
- The first error in a 5,000-line output is on screen, with its line number, in the first call.

## Key Entities

- **Invocation:** the command vector, the time limit, the session, and the start and end time.
- **Log:** the command's whole output, one per invocation, at an absolute path in the session scratch
  space.
- **Verdict:** the exit code, cause, duration, line count, log path and detached children (pid and name),
  plus the limit when it fired.
- **Sections (capped output):** head, first errors (each with its log line number), tail, and the more
  command.
- **Detached child:** a process from the command's tree that was still running when the command exited.

## Out of Scope (slice 0)

- **Memory and disk causes, and redaction** (slice 1). Redaction has a helper in `agentio`, but its
  rule set is slice 1's. In slice 0 the log holds what the command printed, so it is no more of a leak
  surface than the command's own output in the harness (G9 is slice 1's criterion).
- **Log garbage collection and repeat detection** (slice 2).
- **Running a shell string.** `run` takes an argument vector. A shell is `run bash -c '…'`.
- **Stopping detached children on normal exit.** They are named, not stopped.
- **Feature 001's `audited_against`.** It records revision 9 through 001's own next modify, not here.

## Decisions on the points the send left open (reasoning in `research.md`)

| Point | Decision |
|---|---|
| Name | `run` (FR-1). It is the bundle's name and discovery revision 6's, and it shadows nothing on the image's `PATH`. A test asserts it is the only one |
| Verdict vs header | The header is line 1, and the verdict is line 2, before the body (FR-11) |
| Head, errors, tail | 50, up to 20, 100 within the 200-line cap. Errors are found by a pattern set over the combined log (FR-13, FR-14) |
| Default timeout and variable | 100 s, `TIMELIKE_RUN_TIMEOUT`, and `--timeout` (FR-5) |
| Detached child | Found from the command's process tree and from the processes holding the log open, then named by pid and command name (FR-9, FR-10) |
| Log location | `<scratch>/<session>/run/` (FR-16) |
| Exit codes | Pass-through, as ruled at discovery revision 9 (FR-17 to FR-24) |
| Duration in the verdict | Shown always. Rule 11 (prompt 01) forbids **timestamps** except behind `--verbose`. A duration is the result being reported, not a timestamp. `output-contract.md` line 18 says "timestamps and timing", which is wider than the rule, the same pattern as line 83. This reading is raised as FOR-MENTOR Item 10, non-blocking |

## Assumptions

- The image's `PATH` has no other `run` (checked by a test, not assumed).
- `/proc` is mounted and readable for the agent's own processes, as in every container on the stack.
- The 120 s figure is Claude Code's default call limit, the one the 60 s hook limit was sized against
  (001 cycle 5). Other harnesses with shorter limits are served by `TIMELIKE_RUN_TIMEOUT`.
- A process tree that escapes the command's descent entirely, by being re-parented to a process outside
  `run` before `run` could see it, is not stopped. `run` claims only the tree it can observe; the
  research records how far that reaches.
