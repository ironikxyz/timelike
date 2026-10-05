# Research — 009 Session journal (prompt 08, slice 1)

Each entry gives the decision, the rationale and the alternatives. Everything was measured on the host
(bash 5.2.21, Python 3.12) unless it says otherwise. The image decides in the lane.

## R1 · Capturing shell commands: an EXIT trap from 001's hook (spec seam 1, FR-7, FR-8)

**Decision.** 001's hook (`/etc/timelike/shell-env.bash`) gains one guarded step that runs when bash is
non-interactive and has an execution string. The guard is `BASH_EXECUTION_STRING` set and `$-` without
`i`, which covers `bash -c` and `bash -lc`. The step does two things:
- it records the start time in one non-exported variable, `__timelike_journal_t0`
  (`${EPOCHREALTIME/./}`, microseconds);
- it sets `trap '. /etc/timelike/journal-exit.bash' EXIT`.

The trap's work lives in its own file, so that file is linted and tested like any other, and no
function is defined.

**Measured, in order:**
- **bash forks for a single command when an EXIT trap is set.** The child's `$PPID` is the shell's
  `$$`. Without a trap, `bash -c 'cmd'` execs `cmd` in place. So a timelike tool run as
  `bash -c 'edit …'` is the shell's child, its event's `ppid` is the shell's `pid`, and FR-9's link holds.
- **The trap leaves the shell's exit status unchanged:**
  - `false` → 1, `exit 7` → 7, `ls /nonexist` → 2, `sh -c "exit 3"` → 3;
  - under `set -e`, a failing command → 1;
  - every entry recorded the same exit as the shell returned.
- **Cost:** 3.23 ms per `bash -c ':'` against 2.11 ms with an empty hook, over 200 runs each. That is
  about 1.1 ms per shell command. It is spent at exit, after the command's output.
- **JSON:** `\`, `"`, newline, tab and CR are escaped by parameter expansion. Any other control byte
  becomes `?`. All eight test lines parsed with `json.loads`, quotes and backslashes intact.
- **`bash -lc`** sources the hook twice (profile.d, then BASH_ENV). The `t0` guard sets the trap once,
  and one entry was written, with `style: "bash -lc"` from `shopt -q login_shell`.

**001's hook rules, kept:**
- **No fork at shell start.** F1's `ulimit -u 1` probe sources the hook at start. The trap file forks at
  most twice, at exit, and only the first time a session directory is missing: `mkdir` for the root
  (mode 1777, as `agentio` makes it) and for the session (0700).
- **Silent:** both files discard their stderr.
- **Never fails the shell:** the trap ends without `exit`, so the status stands.
- **Idempotent:** the env (`declare -px`) is unchanged, because `__timelike_journal_t0` is not exported.
- **No function left** (Q2's `declare -F`).

The new variable and the trap are this feature's residue. Q2's list of names it checks is extended
by name.

**Limits, stated:**
- **A command that sets its own EXIT trap replaces ours.** That command is not captured. The journal
  cannot know, and the docs say so.
- **`sh -c`, direct execs and interactive shells are not captured** (spec).
- **A shell killed by a signal it cannot trap (`SIGKILL`) leaves no entry.** The tools it ran still
  have theirs.

**Alternatives considered:**
- `PROMPT_COMMAND`: interactive only.
- A `DEBUG` trap: one write per simple command, so a pipeline becomes several entries, and it costs a
  trap per command.
- Wrapping `bash` on PATH: that shadows a command, which seam 1 forbids.
- Writing into `events.jsonl`: that is another feature's record, and its schema is
  `additionalProperties: false`.

## R2 · The tool event's new fields (FR-6), in 001's writer

**Decision.** `agentio._write_event` adds four fields:
- `agent` (when `TIMELIKE_AGENT` is valid);
- `ppid` (`os.getppid()`);
- `ref`, a tool's pointer: `Tool(event_ref=…)` names a key of the result's `data`, and the event carries
  `{"<kind>": value}`. `run` uses `("log", "log")`; `snapshot` and `undo` use `("snapshot", "id")`;
- `t_ms`, the end in epoch milliseconds, beside `ts`, which keeps its form.

`event.schema.json` adds them as optional properties. Old lines stay valid and are read.

**Why `t_ms` beside `ts`, not a new `ts` format:** 001's tests and conform C7 read `ts`. A second field
changes nothing that already reads the first.

**Why the result's own data:** the pointer is what the tool already reported. A second path to the same
value could disagree with it. `agentio` writes the event after the result, so the data exists.

**Alternatives:** the journal re-deriving pointers from arguments. A `run` log path is not in its
arguments, so that cannot work.

## R3 · Order and linking (FR-3, FR-9)

**Order: start time, to the millisecond.**
- A tool event's start is `t_ms - duration_ms`. An old event without `t_ms` uses `ts` (seconds) as its
  end, so its order is good to the second.
- A shell entry's start is `start_us` (when its hook ran), and its end is `end_us`.
- A tool started by a shell therefore sorts after the shell's start.
- Ties are broken by end time, then by record order.

**Linking:**
- **A child of a shell:** a tool event whose `ppid` equals a shell entry's `pid`, and whose start lies
  within that shell's start and end, is that shell's child. The time window guards against pid reuse.
- **Collapsed:** when the shell's command line's first word (after `exec`, `env A=B …` and redirections)
  is the tool's name, and the tool is its only child, the journal shows the tool entry alone, styled with
  the shell (`bash -c`).
- **Nested:** otherwise the shell entry is shown and its children are indented under it.

## R4 · The ledger (FR-11, seam 3)

**The input:** `adeled ledger --json` prints one JSON array of rows (004's `jsonRow`, `adele/cmd/adeled/ops.go`):
- `id`, `at` (RFC 3339, seconds), `outcome` (`performed` | `refused` | `extended`);
- `grant`, `session`, `capability`, `action`, `resource`, `cost_cents`, `expires_at`, `undo`;
- `limit_name`, `allowed`, `needed`.

An `extended` row's session is `operator`.

**Decision.** `journal --ledger -|FILE` parses that array. Each row becomes a `grant` entry in its
session, at its second. When an `adele` tool event in the same session spans that second, the row is
linked to it, and the entry carries both pointers (`ledger #id`). With `--all-sessions`, operator
extensions are shown as session `operator`.

Stdin is read only with `--ledger -` (rule 4), and the manifest declares `reads_stdin: true`.

**Bound:** at most 16 MiB of ledger JSON. More than that is exit 1, `ledger too large`.

## R5 · Secrets (FR-12)

**The hook:** builtins only, so it cannot run rule 15's regular expressions. Two consequences:
- The stored command line is the agent's own, in its `0700` scratch, as its history file would hold it.
- **Every line the journal prints** goes through `agentio`'s rule-15 redaction (the shared gitleaks rule
  file, feature 003 slice 1), command lines and paths both. The units feed command lines with fake
  credentials of each tagged type and assert the printed output.

The hook-side argument redaction the spec mentions is **not done in the hook**, for this reason. It is
done by the reader, with the full rule set. The spec's FR-12 is amended to say so.

**Alternative:** a bash `[[ =~ ]]` copy of `_redact_arg`. That would be a second implementation of the
redaction that could drift from the first, which is exactly what the shared rule file exists to prevent.

## R6 · Name and image

**Decision:** `tools/bin/journal`, copied by `COPY tools/bin/`. `image/rootfs/etc/timelike/journal-exit.bash`
is new, and 001's hook file gains the guarded step.
- `make scan`'s agent image changes: two files, no package.
- The `type -a journal` cell guards the name. Debian's `systemd` would not install a `journal` binary,
  but the cell decides.
- The announcement (007) lists `journal` automatically.

## R7 · Tests

**Units:** `tests/unit/test_journal.py`. Fixtures are made by running real tools and real `bash -c`
under a temporary scratch root (P005), never by writing records by hand. The exception is the
malformed-line and foreign-format cases, which must be written. The units cover:
- order, linking, collapse and nesting;
- the tail of 20 and the cut;
- sessions and agents;
- the ledger merge;
- redaction;
- unreadable records.

**agentio:** units for the new event fields, `event_ref`, and schema validation of new and old lines.

**Host:** `tests/host/test_shell_env_hook.sh` extended:
- F1 still holds with the trap;
- Q2 lists the new variable;
- the exit status is preserved for each case in R1;
- `bash -lc` gives one entry;
- the root is created 1777 and the session 0700;
- a hostile command line (quotes, backslashes, control bytes, 10 KiB) gives one valid JSON line.

**e2e:** one bats file per criterion, `bash -c` and `bash -lc`, under a test's own `TIMELIKE_SESSION`
and `TIMELIKE_AGENT`. Plus the `type -a` and manifest cells.
