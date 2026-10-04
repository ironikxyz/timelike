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

---

## Slice 1 (Cycle 2, send `bridge/sends/03-rev1-20261004-183704.md`; natural)

Built by `/specswarm:modify 003` on `modify/003-slice-1`, dispatch batch `20261004-183704`. Prompt 03 is
still at revision 1, and `audited_against [1]` is current (modify row 4). The slice-1 criteria were in
revision 1 from the start, marked *(slice 1)*. They are **added work** on a body that stays true. The
`Out of Scope (slice 0)` list above is history: memory, disk and redaction are this section's.

### Scenarios

**Scenario 5: a command killed for memory (SC-8, DEMO → D12).**
1. The container has a 96 MiB limit. The agent runs `run python3 build.py`, and the build allocates past
   it.
2. The kernel's OOM killer stops the process. `run`'s verdict reads, for example:
   `verdict: exit 137 (out of memory: limit 96.0 MiB, peak 96.0 MiB) · 3.1 s · 12 lines · log …`.
3. `$?` is 137, as it would have been. The agent knows to reduce the build's memory, or to ask for a
   larger limit, instead of retrying unchanged (P2's violation example).

**Scenario 6: a full filesystem (SC-9).**
1. The workspace filesystem fills while the command writes, and the command fails.
2. The verdict reads, for example: `verdict: exit 1 (disk full: /work has 0 B free) · …`. When the
   scratch filesystem is the full one, the verdict also says the log may be incomplete, because the
   command's output could not be written to it.

**Scenario 7: a secret in the output (SC-10).**
1. A command prints a GitHub token, an AWS access key ID and a private key.
2. The shown lines, the saved log and the header carry `[REDACTED:token]`, `[REDACTED:credential]` and
   `[REDACTED:key]` in their place. The log has the same number of lines as before. The verdict ends
   ` · redacted 3 (credential 1, key 1, token 1)`.

### Functional requirements

**The memory cause**
- **FR-25:** `run` reads its own cgroup v2 directory: `/proc/self/cgroup`'s `0::<path>` under
  `/sys/fs/cgroup`. `TIMELIKE_CGROUP_ROOT` overrides the directory, for tests on hosts. It reads
  `memory.events`' `oom_kill` count before starting the command and after it ends.
- **FR-26:** When the count rose and the command did not exit 0, the cause is **`memory`**. The words
  are `out of memory: limit <L>, peak <P>`, where `<L>` is `memory.max` (or `no limit` for `max`) and
  `<P>` is `memory.peak`, both in binary units with one decimal. The exit code still passes through:
  137 when the command itself was killed, or what its parent reported.
- **FR-27:** When the count rose and the command exited 0 anyway (a child was killed, and the command
  survived it), the cause stays `command`. The verdict adds ` · OOM kill during the command (limit <L>,
  peak <P>)`.
- **FR-28:** When the command was killed by SIGKILL (or exited 137) and the cgroup files cannot be read,
  the verdict adds ` · memory: unknown (<file>: <reason>)`. The cause stays `command`. A cause is never
  guessed (send seam 1). JSON `data.memory.state` is `read`, `unknown` or `not looked at` (when
  nothing pointed at memory), with `limit_bytes`, `peak_bytes`, `oom_kills` (the rise) and
  `command_max_rss_bytes` (the largest resident set among the command's waited-for processes,
  `getrusage(RUSAGE_CHILDREN)`).
- **Limit of the reading:** the cgroup is the container's. An OOM kill of another process in the same
  container during the command is counted too (peer agents share it), and `memory.peak` is the
  container's peak since it started. The JSON names both, and research R16 records why nothing finer is
  readable.

**The disk cause**
- **FR-29:** When the command did not exit 0, `run` checks two filesystems: the **scratch** one (the
  session scratch directory, which holds the log) and the **workspace** one (the current directory).
  For each it reads `statvfs` (free bytes for an unprivileged writer, and free inodes) and resolves the
  mount point from `/proc/self/mountinfo`.
- **FR-30:** A filesystem is **full** when its free bytes are below `disk_full_bytes` (1 MiB) or it has
  no free inodes. The cause is **`disk`** when one is full, or when a line of the log carries the
  ENOSPC message (`No space left on device`, `Disk quota exceeded`). The words are `disk full: <mount>
  has <free> free`, for each full filesystem (`, ` between them). With only the message, the words are
  `disk full: "No space left on device" in the output; <mount> has <free> free` for the workspace and
  the scratch filesystem.
- **FR-31:** When the scratch filesystem is full, the verdict adds ` · log may be incomplete`, because
  the command's output could not all be written to it.
- **FR-32:** When the log cannot be created before the command runs, the error (exit 1, the command not
  run, unchanged from slice 0) names the scratch filesystem and its free space.

**Redaction (G9, rule 15)**
- **FR-33:** The rule set is one file in **gitleaks' own config format**:
  `image/rootfs/etc/timelike/redaction.toml`, installed at `/etc/timelike/redaction.toml`.
  `TIMELIKE_REDACTION_RULES` overrides the path. It extends gitleaks' defaults (`[extend] useDefault =
  true`). Its rules are 18 provider rules copied byte for byte from the pinned gitleaks v8.30.1
  defaults, with a `tags = ["redact:<type>"]` added to each, where `<type>` is one of rule 15's five.
  `make scan`'s gitleaks step reads the same file (`--config`), so the set cannot diverge. The rules
  are named, never paraphrased: `anthropic-admin-api-key`, `anthropic-api-key`, `aws-access-token`,
  `gcp-api-key`, `github-app-token`, `github-fine-grained-pat`, `github-oauth`, `github-pat`,
  `github-refresh-token`, `gitlab-pat`, `jwt`, `npm-access-token`, `openai-api-key`, `private-key`,
  `pypi-upload-token`, `slack-bot-token`, `slack-user-token`, `stripe-access-token`.
- **FR-34:** What counts as a secret is **the patterns** (send seam 2). Environment values are not
  matched: feature 001's environment layer already strips secret-shaped variables, and a value the
  operator allowed through `TIMELIKE_ENV_ALLOW` was allowed on purpose. Generic, entropy-only rules
  (`generic-api-key`) are excluded, because they redact ordinary output.
- **FR-35:** A rule is applied as gitleaks applies it. Its keywords (case-insensitive) must occur, then
  its regex matches, and the secret is the first non-empty capture group (the whole match when there is
  none). The secret's Shannon entropy must reach the rule's `entropy`, and it must match none of the
  rule's `allowlists` regexes. Only the secret is replaced, by `agentio.redact(secret, type)`.
- **FR-36:** The rules are applied to the **saved log** after the command ends, in one streaming pass,
  in blocks of whole lines. A match spanning lines (a private key) is replaced line by line, so the log
  keeps its line count, and every line number the verdict or the more command names stays true. The log
  is replaced (a redacted copy, then a rename) **only when something matched**. Otherwise it is left as
  the command wrote it.
- **FR-37:** The **shown output** is read from the redacted log, so it is redacted in both modes. The
  **header's command** (`run: <command>`, JSON `target`) and the **session event's arguments** are
  redacted with the same rules.
- **FR-38:** When anything was redacted, the verdict adds ` · redacted <n> (<type> <n>, …)`, types in
  alphabetical order. JSON `data.redaction` has `state` (`applied` or `unavailable`), `counts` per type,
  `rules` (the file) and `log_rewritten`. When the log was rewritten while a detached child held it
  open, the verdict also says `detached output after this is not kept`: the child keeps writing to the
  file the redacted copy replaced. **This amends slice 0's edge case** *"Its output keeps going to the
  same log"*, which still holds whenever nothing was redacted.
- **FR-39:** When the rule file is missing, unparsable or invalid (a rule with no `redact:<type>` tag, a
  type outside rule 15's five, or a regex that does not compile), `run` **fails closed** for what it
  shows. The verdict adds ` · output withheld: redaction rules unavailable (<reason>); the log is
  unredacted`, and no lines are shown. The exit code is still the command's.
- **FR-40:** The manifest names `redaction_rules` (the path and the rule ids). `--help` has one usage
  line on redaction.

### Success criteria (slice 1)

The criterion text is the send's, copied exactly.

**Automated**
- **SC-8:** "A command killed by the container's memory limit produces a verdict naming the memory limit
  and peak usage". The test runs in a throwaway container from the agent's image with `--memory 96m
  --memory-swap 96m`. It checks the exit code (137), the words, `cause: memory` and
  `data.memory.limit_bytes` equal to 96 MiB.
- **SC-9:** "A command that fails because the scratch or workspace filesystem is full produces a verdict
  naming the full filesystem and its free space". Both cases are tested, each on a small `--tmpfs` in a
  throwaway container: the workspace (`/work`) and the scratch (`TIMELIKE_SCRATCH_ROOT`).
- **SC-10:** "Values matching known secret formats are shown and stored as `[REDACTED:<type>]` in both the
  displayed output and the saved log". The values are generated at run time, and none is a literal in a
  tracked file. That keeps `make scan`'s gitleaks step at 0 findings, and GitHub's push protection quiet.
  The test checks the shown lines, the log (read in the container), the header and the line count.

Every automated criterion runs end to end in the image, under `bash -c` and `bash -lc`.

**Manual**
- **SC-11:** "DEMO: the Agent whose command is killed for exceeding memory receives a verdict naming the
  memory cap and peak use instead of a bare exit 137" (D12). The mentor captures it after the lane; it is
  `unconfirmed` until then.

### Decisions (the send's seams; reasoning in `research.md` R15–R19)

| Point | Decision |
|---|---|
| Where the memory cause is read | cgroup v2 `memory.events` `oom_kill` (before and after), `memory.max`, `memory.peak`; the container's cgroup, named as such (FR-25 to FR-28) |
| Unreadable cgroup files | `unknown`, naming the file and the reason; cause stays `command` (FR-28) |
| Which filesystems | Scratch (the log's) and workspace (the current directory) (FR-29) |
| "Full" | Under 1 MiB free for an unprivileged writer, or no free inodes; or the ENOSPC message in the output (FR-30) |
| What counts as a secret | The pattern set only, not environment values (FR-34) |
| Where the rule set lives | One gitleaks-format file read by `run` (agentio) and gitleaks (FR-33) |
| Which rules | 18 provider rules from gitleaks' pinned defaults; not the generic entropy rule (FR-33, FR-34) |
| Redacting the log | After the command, a streaming pass, and a rename only when something matched; line count kept (FR-36) |
| Rule file unavailable | Fail closed: the output is withheld, and the verdict says why (FR-39) |
| A detached child holding a rewritten log | Its later output is not kept, and the verdict says so (FR-38) |
| agentio's pass-through gate | Admits any `cause` with `command_exit` equal to the exit, as 001's contract already foresaw (A002) |
