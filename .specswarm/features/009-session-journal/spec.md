---
parent_branch: master
feature_number: "009"
status: In Progress
created_at: 2026-10-05T06:02:57+00:00
source_prompt: plan/.discover/prompts/08-session-journal.md
source_send: bridge/sends/08-rev1-20261004-183704.md
prompt_revision: 1
discovery_revision: 12
audited_against: [1]
slice: 1
---

# Feature: Session journal (prompt 08, slice 1: natural)

## Overview

A session leaves traces in three places, and today nobody reads them together:
- the session event log every timelike tool appends to (001's rule 16);
- the shell commands an agent runs outside timelike tools, which nothing records;
- Adele's ledger of grant uses (004), which only the operator can read.

The journal is the **reader** that turns these into one timeline per session and per agent:
- the agent gets the recent tail of its own session, to resume after a context compaction (P1);
- the operator gets the whole session, with grant uses, to review it (P4, P5).

It adds one writer of its own, the shell-command capture. It writes nothing into another feature's
records (prompt constraint).

**Built under discovery revision 13's rulings** (code-track § Resume after pause-06). 08 is not
confirmed under rule 9 at all: it changes nothing.

**07 slice 1 is not built** (automatic snapshots, guarded commands, the per-workspace state root). The
journal shows what exists today: `run`, `snapshot`, `undo`, `view`, `search`, `edit`, `adele`, `timelike`,
and shell commands.

## The three seams (send), decided

1. **"Adds no new writer to other features" against shell capture.**
   - **Where it hooks:** shell capture is 08's own writer, through 001's shell hook
     (`/etc/timelike/shell-env.bash`). That hook is reached by `bash -c` (BASH_ENV) and by `bash -lc`
     (profile.d, then BASH_ENV).
   - **How:** the hook sets an `EXIT` trap that appends one line to the session's own **shell record**,
     a file separate from the tool event log. It shadows no command, defines no function named after a
     command, and does not wrap or alias anything.
   - **Nothing is written twice.** A timelike tool's event is written only by `agentio`, as now.
     A shell entry is written only by the hook, and it records the command line, not the tool. The
     journal **links** the two: a tool event records its parent process, and when that parent is a
     shell that ran exactly that tool, the journal shows one entry, not two (FR-9).
   - **The change to 001's writer** is additive and optional: three fields, `agent`, `ppid` and `ref`,
     plus a millisecond time (FR-6). That is a change to the existing writer, not a new writer for
     other features, and it goes in `changed_other_features`.
2. **Where the journal lives.** Rule 10 (revision 11) says the per-session scratch is disposable. The
   per-workspace state root is not built (07 slice 1 is held). So the journal **reads the records where
   they are now**, `${TIMELIKE_SCRATCH_ROOT:-/tmp/timelike}/<session>/`, and keeps no store of its own.
   It **does not create the state root**. When the scratch has been cleared, the journal says the
   session has no records, rather than reporting an empty session as complete.
3. **Grant uses** are read, never written:
   - **In the agent's container:** every `adele` client call is a tool event (the request, the grant,
     its exit: 0 performed, 4 beyond the grant). The journal shows them as grant uses.
   - **The ledger** (004) is Adele's, reachable only by the operator
     (`docker exec timelike-adele adeled ledger --json`). The operator's command pipes it into the
     journal (`--ledger -`). The journal merges its rows by session and time, opening nothing of
     Adele's and writing nothing anywhere.

## User Scenarios

### Actors
- **Agent** (primary): reads the tail of its own session to resume.
- **Operator** (administrative): reads a whole session, every session, with grant uses.

### Scenario 1: the agent resumes (SC-3)
After a compaction, the agent runs `journal`. It sees the last 20 entries of its session, oldest first.
Each entry has its time, its kind (tool or shell), the command, its exit and its pointer. The closing
lines name the command for the rest (`journal --all`).

### Scenario 2: a session's tool calls in order (SC-1)
Inside one session the agent runs `snapshot`, `run make test`, `edit …` and `undo --dry-run`.
`journal --all` lists the four in the order they started. Each has its time, tool, arguments, exit and
pointer: `run`'s log path, `snapshot`'s id, `undo`'s snapshot id. Entries without a pointer say so (`—`).

### Scenario 3: shell commands (SC-2)
The agent runs `bash -c 'make lint'` (exit 2) and `bash -lc 'ls'` (exit 0). Both appear with their exit
codes, in order among the tool entries.

### Scenario 4: two agents at once (SC-4)
Two agents work concurrently in one container:
- agent `a1` in session `s1`;
- agent `a2` in session `s2`, then also in `s1`.

`journal --session s1 --agent a1` shows only a1's entries in s1. `journal --all-sessions` labels every
entry with its agent and session.

### Scenario 5: the operator's review (SC-5, D17)
The operator pipes the ledger into the journal:
`docker exec timelike-adele adeled ledger --json | docker exec -i timelike-agent journal --all-sessions --ledger -`
and sees every run, snapshot and grant use in order, each with its session.

### Edge cases
- **No records for the session:** exit 0. The verdict says no records were found, names where it looked,
  and says the scratch is disposable (rule 10).
- **A malformed or foreign line** in a record: skipped and counted in the verdict
  (`2 unreadable lines skipped`). It is never silently dropped.
- **A record the agent cannot read** (another user's scratch): named, with the reason. The journal does
  not fail.
- **A shell command whose own script replaces the EXIT trap:** that command is not captured. This is
  stated in the docs and the manifest, not hidden.
- **`sh -c` (dash) and a direct `docker exec` of a binary:** not captured. 001's hook does not reach them
  either. Timelike tools run that way still write their tool events.
- **Interactive shells:** not captured in slice 1. Harnesses run `bash -c` and `bash -lc`.
- **A long command line:** stored and shown cut at 4096 characters with the cut byte count. Display
  lines are cut at `COLUMNS` (rule 13).
- **A secret in a command line:** see FR-12.
- **Clock ties:** entries are ordered to the millisecond. A tool started from a shell command sorts after
  that command's start.

## Functional Requirements

### Reading
- **FR-1** The journal reads, for a session:
  - the tool event log `<scratch>/<session>/events.jsonl` (001's format, extended by FR-6);
  - the shell record `<scratch>/<session>/shell.jsonl` (FR-7);
  - in the operator's mode, ledger rows on stdin (FR-11).

  It writes nothing, except its own session event as every timelike tool does.
- **FR-2** **The current session** is `TIMELIKE_SESSION` (default `default`), as `agentio` resolves it.
  `--session S` names another. `--all-sessions` reads every session directory under the scratch root that
  the caller can read.
- **FR-3** **Order:** entries are ordered by start time, to the millisecond. Ties are broken by end
  time, then by record order. A tool event's start is its end minus its duration.

### Output
- **FR-4** `journal` prints the **last 20 entries** of the current session, oldest first, through the
  output contract:
  - a header, a verdict naming the session, the count shown and the total;
  - `--json`;
  - rule 3's cut, whose `more:` is `journal --all` (or the window before);
  - one session event.

  `journal --all` prints the whole session. `-n N` sets the tail length.
- **FR-5** **Each entry** shows:
  - its start time (UTC, `HH:MM:SS.mmm`; the date when it differs from the previous entry's);
  - its agent and session (only in `--all-sessions`, or when more than one agent appears);
  - its kind: `tool`, `shell` or `grant`;
  - the command (tool and arguments, or the shell's command line);
  - its exit, its duration;
  - **its pointer:** a log path, a snapshot id, a ledger row id, or `—`.

  JSON entries carry the same fields, named.

### Writing (the extension to 001, and 08's own writer)
- **FR-6** **001's tool event** gains optional fields, written by `agentio`:
  - `agent`: `TIMELIKE_AGENT`, when set and valid (`^[A-Za-z0-9._-]{1,64}$`);
  - `ppid`: the tool's parent process;
  - `ref`: a tool's pointer, `{"log": path}` or `{"snapshot": id}`, taken from the result's own data by a
    key the tool declares (`run`: `log`; `snapshot` and `undo`: the snapshot id);
  - `ts` keeps its form and gains milliseconds.

  `event.schema.json` gains them as optional. Old events without them stay valid and are read.
- **FR-7** **The shell record:**
  - one JSON line per `bash -c` / `bash -lc` invocation, appended by the hook's `EXIT` trap;
  - fields: `v`, `kind: "shell"`, `cmd` (the command line, cut at 4096 characters with `cut_bytes`),
    `exit`, `start_ms` and `end_ms` (epoch milliseconds), `pid`, `ppid`, `session`, `agent`, `cwd`, `style`
    (`bash -c`, `bash -lc`);
  - mode `0600`, in the session's `0700` directory, appended on an `O_APPEND` descriptor in one write.
  - The hook keeps 001's hook rules: bash builtins only (no fork), silent, never fails the shell,
    idempotent, nothing left behind but the trap. **The trap never changes the shell's exit status.**
- **FR-8** **No double capture:** under `bash -lc` the hook runs twice (001's note). The trap is set once.
  A shell started by a timelike tool's own subprocess is a shell like any other: it is captured, and the
  journal shows it beside the tool that started it.
- **FR-9** **Linking:** a tool event whose `ppid` is a shell entry's `pid` belongs to that command. When
  the shell's command line is exactly one invocation of that tool (its first word names the tool), the
  journal shows the tool entry alone, marked with the shell style. Otherwise both are shown, and the
  tool entries are indented under the shell entry.

### Agents and sessions
- **FR-10** **Separable by agent and session:**
  - the session comes from every record's `session`;
  - the agent comes from `agent` when the harness or operator sets `TIMELIKE_AGENT`.

  `--agent A` filters to one agent. Records without an agent are shown as agent `-`, with the pid. Two
  agents that set neither variable share session `default` and agent `-`. That is stated, because no
  record can tell them apart. The announcement (007) is not changed in this slice.

### The operator's view and grant uses
- **FR-11** `--ledger FILE` (or `-` for stdin, the only time the journal reads stdin; declared in the
  manifest) merges the rows of `adeled ledger --json`:
  - performed, refused and extended rows become `grant` entries in their session, with the grant, the
    capability, the action, the outcome and the row id;
  - an `adele` tool event and the ledger row it produced are linked by session and time (within the
    call's duration), and shown as one entry with both pointers.

  Without `--ledger`, `adele` tool events are the grant entries.

### Secrets
- **FR-12** The journal never prints a raw secret (P4):
  - the hook applies `agentio`'s argument redaction (a `KEY=value` or `--flag=value` whose key names a
    secret) before writing;
  - the journal applies rule 15's full rule set (the shared redaction rules) to every command line and
    path it prints.

  A secret that only the full rule set catches is stored in the agent's own `0700` scratch, as the
  agent's shell history would hold it. It is redacted on every read. The tests check the output, never
  the stored bytes alone.

### Contract
- **FR-13** The name is **`journal`**, the habit of `journalctl` and the systemd journal (P3). `history`
  is a shell builtin, and a file on PATH cannot shadow it. A `type -a` cell checks that the image has no
  other `journal`.
- **FR-14** Exit codes:
  - `0`: entries shown, or none found (an empty session is a result);
  - `1`: a record unreadable as a whole;
  - `2`: usage;
  - `3`: `--session S` names no session directory.

  The manifest: `mutating: false`, `reads_stdin: true` (only with `--ledger -`), `probe: []` (the current
  session).

## Success Criteria

The criterion text is the send's, copied exactly. Each automated criterion is one e2e file in the image,
under `bash -c` and `bash -lc`, with its fixtures made by running the real tools and shells in the
container (P005), never by writing records by hand.

- **SC-1** "The journal lists, in order, every timelike tool invocation of a session with time, tool,
  arguments, exit and a pointer to its log or snapshot". Checked against the invocations the test made,
  in the order it made them.
- **SC-2** "Shell commands run outside timelike tools in the same session appear in the journal with their
  exit codes". Checked with commands of known exit codes (0, 1, 2, 7).
- **SC-3** "One command prints the last 20 journal entries of the current session in the bounded output
  format". 30 invocations; exactly the last 20 shown, oldest first, with the cut and its `more:`.
- **SC-4** "Entries from concurrent agents are separable by agent and session". Two concurrent agents,
  each with its own `TIMELIKE_AGENT` (and sessions as in Scenario 4).
- **SC-5** "DEMO: the Operator reads the session journal and sees every run, snapshot and grant use in
  order, each with its session" (D17). Manual, after the lane, with the ledger piped in.

## Key Entities

- **Entry:** start, end, kind (tool, shell, grant), agent, session, command, exit, duration, pointer, links.
- **Tool event:** 001's record, plus `agent`, `ppid`, `ref`, `ts` to the millisecond.
- **Shell entry:** 08's record (FR-7).
- **Ledger row:** 004's `adeled ledger --json` row, read only.

## Decisions

| Point | Decision |
|---|---|
| Seam 1 (writer) | 08's own shell record, through 001's hook's `EXIT` trap; additive optional fields in 001's event; linked, never written twice (FR-6 to FR-9) |
| Seam 2 (location) | Read the session scratch where records are now; no store, no state root (FR-1, FR-2) |
| Seam 3 (grants) | `adele` events always; ledger rows only when the operator pipes them in; nothing written (FR-11) |
| Agent identity | `TIMELIKE_AGENT`, optional; without it, not separable within a session, and said so (FR-10) |
| Name | `journal` (FR-13) |
| Tail | 20 entries, oldest first; `--all`, `-n N` (FR-4) |
| Order | Start time to the millisecond (FR-3) |
| Secrets | Hook-side argument redaction, read-side full rule set (FR-12) |

## Out of scope (slice 1)

- Tamper evidence (slice 2).
- Interactive shells, `sh -c`.
- Guarded commands and automatic snapshots (07 slice 1).
- A persistent store (the state root, 07 slice 1).
- Services (09, later in this batch: its tool events are journalled like any other).

## Assumptions

- Harnesses run commands as `bash -c` or `bash -lc` (001's invocation matrix), so the hook reaches them.
- `EPOCHREALTIME` (bash ≥ 5.0) gives the shell entry's times without a fork. The image's bash is 5.2.
- A harness or operator that runs several agents in one container sets `TIMELIKE_AGENT` or
  `TIMELIKE_SESSION` per agent. Without either, separation is impossible from the records, and the journal
  says so.
