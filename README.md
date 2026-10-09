# timelike

A containerised shell for AI coding agents: tools built for a user with no terminal, a limited context
window and nobody watching, behind one output contract.

## Why

Coding agents work in a shell made for people. They hand-build pipelines to keep output small, retry
commands that don't exist, wait on processes that never return, and stop at anything that needs
infrastructure. Then a person steps in to unstick, clean up or bring something up.

timelike aims for the agent to finish a task without that help (tests passing, a running app, a reachable
deployment), and, when it can't, to say exactly why and who can unblock it.

Seven principles govern it:
- **Unaided completion.**
- **Every call concludes**: no hangs, and a verdict first.
- **Found where agents look.**
- **Reach only by grant**: credentials stay with Adele, never with the agent.
- **Wrong turns are recoverable.**
- **Claims are measured.**
- **Harness-agnostic.**

Whether it works is a measured claim: see Status.

## What

| # | Feature | What it does | Status |
|---|---|---|---|
| 01 | Shell baseline & output contract | The container, an unprivileged `agent` user, non-interactive defaults, and one contract every tool speaks: verdict first, bounded output, JSON when piped, and `timelike-conform` to check it | complete (0, 1) |
| 02 | Speedup bench | Runs the same tasks in a vanilla and a timelike container and reports turns, failed commands and hangs, losing cases first | slice 0 of 0–2 |
| 03 | `run` | Every command ends with a verdict: the whole process tree is stopped at its limit, memory kills and full disks are named, and secrets are redacted | slices 0, 1 of 0–2 |
| 04 | Announcements & discovery | Tells each harness (Claude Code, Codex CLI, OpenCode) which tools exist, generated from their manifests; `timelike` lists them all; a missing command names how to get it, package installs need no privilege, and `timelike budget` shows the resource budget | complete (0, 1) |
| 05 | `view`, `search` | Bounded reads and searches, each ending with the next command; a directory overview within a budget | complete (0, 1) |
| 06 | `edit` | One exact replacement per call, tolerant of CRLF and tab/space indentation; the nearest candidates on a miss | slice 0 of 0–1 |
| 07 | `snapshot`, `undo` | Snapshot the workspace, git-ignored files too, and restore it | slice 0 of 0–2 |
| 08 | `journal` | A session's timeline: tool calls, shell commands and grant uses, by agent and session | slice 1 of 1–2 |
| 09 | `services` | Start long-running processes, return when ready or dead, and stop the whole process tree | slice 1 of 1–2 |
| 10 | `symbols` | Outlines, definitions, callers and dependents: exact for Python, text-based (and saying so) for others | slice 1 of 1–2 |
| 11 | `verify` | Failures only, and only for what a change affects: tests, lint and type-check | slice 1 of 1–2 |
| 12 | Adele & `adele` | The one authority outside the agent that holds credentials and performs reaching actions within the operator's grants | slice 0 of 0–2 |
| 13 | Nested dev environments | Bring up the project's own compose or devcontainer environment from inside the container, under a grant | not started |
| 14 | Provider compute | One request for compute or an endpoint; Adele quotes, provisions within the grant, and tears down | not started |
| 15 | Package guard | Package installs checked first: does the package exist, is it old enough, is it already in the lockfile | not started |
| 16 | Model-assisted filters | A grep, or a sed's addresses, chosen by description; off by default, and costed per call | not started |
| 17 | Web verification | Load a URL headless and return a bounded verdict: screenshot path, console errors, failed requests | not started |

## Status

**16 of 38 planned slices are built.** Each feature is built in slices: 0 is skeletal (one working path end
to end), 1 natural (the common failures), and 2 hardened (incident replays, enforcement, publication).
Features 01, 04 and 05 are complete. Features 02, 03 and 06–12 have their first slice or slices. Features
13–17 are not started.

**Next:** 07 slice 1 (a persistent state root), 15 slice 1, 06 slice 1.

**Measured results:** none are claimed yet. The speedup bench (02) runs today; published comparisons
wait for its catalog and its losing-cases-first report (P6).

This README makes no claims about timelike's value. Those are made only from reproducible bench
results (constitution P6).

**Contents:** [How it works](#how-it-works) · [Install](#install-typical) · [Using it](#using-it) ·
[Command reference](#command-reference) · [Development](#development)

## How it works

### The container and the `agent` user

The image is Debian trixie-slim with a pinned interpreter, an unprivileged `agent` user, no sudo or
setuid binaries, and non-interactive defaults in the process environment. Its container
(`timelike-agent`) runs with no capabilities and `no-new-privileges`, and mounts no volumes, no ports and
no Docker socket. The tools are on PATH at `/opt/timelike/bin`, ahead of everything else. Governance is in
`.specswarm/` (the constitution, the tech stack and the quality standards), and each feature has its
specification, plan, contracts and decision log under `.specswarm/features/`.

### Environment defaults

Every shell the harness starts (`bash -c`, `bash -lc`, interactive) is non-interactive by default:
no pager, editor or prompt, and no colour.

**A repository's own git hooks run, each under a time limit.** Hooks in `.git/hooks`, or in the
repository's own `core.hooksPath` (husky, for example), run as they would without timelike. A hook
that has not finished after **60 s** is stopped, and the git command fails with a verdict naming the
hook and the limit. To raise the limit, set `TIMELIKE_HOOK_TIMEOUT=<seconds>` for a shell, or run
`git config timelike.hookTimeout <seconds>` for a repository. timelike never switches a project's
checks off. The dispatchers are in `image/rootfs/opt/timelike/git-hooks/`.

**The limit holds in the environment timelike provides.** An agent or tool that discards that
environment, for example with `env -i`, gets git's own behaviour, as without timelike. The hooks still
run. Hooks in `.git/hooks` stay bounded, through `/etc/gitconfig`. Hooks in a repository's own
`core.hooksPath` run **unbounded**, because that setting then outranks timelike's. When in doubt, run
git through [`run`](#run--the-concluding-run), which stops the whole process tree at its own limit:
`run --timeout 300 git commit -m "…"`. (Discovery revision 8, tension T4. Pinned by
`tests/e2e/hooks-under-env-i-default-bounded-local-unbounded.bats`.)

From slice 1, it also gets these:

- **Job counts from the container's CPU limit.** `TIMELIKE_CPUS` is taken from cgroup `cpu.max`,
  capped by the CPU affinity. From it come `MAKEFLAGS=-jN`, `CMAKE_BUILD_PARALLEL_LEVEL`,
  `CARGO_BUILD_JOBS`, `GOMAXPROCS`, `PYTEST_XDIST_AUTO_NUM_WORKERS` and `PYTHON_CPU_COUNT`. Each is set
  only if it is not already set, so an explicit value wins.
- **No secret-shaped variables.**
  - A variable whose name has a component `KEY`, `PASS`, `CREDENTIAL(S)` or similar is removed.
  - So is one whose name has a component ending in `PASSWORD`, `TOKEN` or `SECRET`.
  - To let one through, list its exact name in `TIMELIKE_ENV_ALLOW`, e.g.
    `docker exec -e TIMELIKE_ENV_ALLOW=NPM_TOKEN -e NPM_TOKEN=... timelike-agent bash -c '...'`.
  - The strip applies to the agent's shells. It cannot remove what the container itself was started
    with, so don't pass secrets to the agent container (P4).
- **`TZ=UTC`**, and Python's REPL in its basic, scriptable mode (`PYTHON_BASIC_REPL=1`).

Plain `sh -c` and a direct exec of a non-shell binary get the static defaults (including `TZ`), but not
the job counts or the strip. The details are in `image/rootfs/etc/timelike/shell-env.bash`.

### The output contract

Every timelike tool follows rules 1–16 in
`.specswarm/features/001-agent-shell-baseline/contracts/output-contract.md`. In brief:
- JSON when piped, text on a terminal
- a self-labelling first line
- capped output that says what was left out and how to get it
- one exit-code vocabulary (0, 1, 2, 3, 4, 124) for a tool's own outcomes; a tool that runs a
  command you named passes that command's exit through (discovery revision 9)
- structured errors
- never a prompt, pager, editor or terminal read
- one session event per invocation

`timelike-conform` checks every timelike tool on PATH against it.

**Predicting a tool you have not seen.** Three things hold for every timelike tool:

- **First line.** On a terminal or with `--text`: `<tool>: <target> [<scope>]`, then
  `verdict: <verdict>`. With JSON (the default under a harness, where stdout is a pipe): an object whose
  first keys are `tool`, `target`, `scope`, then `verdict` and `exit`.
- **Last line**, predicted by its kind:
  - **Capped text:** always
    `… omitted <N> lines (<B> bytes) — full output: <path>; more: <command>`. It appears only when
    output was cut, so its absence means nothing was omitted.
  - **Uncapped text:** the result's own last line. Nothing trails it.
  - **JSON:** the object carries `exit` (and `truncated` when capped).
  - The contract document gives the full rules (discovery revision 6).
- **Exit codes:**

  | Code | Meaning |
  |---|---|
  | 0 | success (zero search results is 0, with a count of zero) |
  | 1 | failure |
  | 2 | usage |
  | 3 | not found, or unsure |
  | 4 | confirmation or a grant is required |
  | 124 | timeout |

  These are a tool's **own** outcomes. A tool that runs a command you named, such as `run`, passes that
  command's exit through instead, as `timeout` and `env` do: 126, 127 and 128+n included, and 124
  only when the tool's own limit fired. Its manifest says `"passes_exit": true`, and its JSON carries
  `cause` (`command`, `timeout`, …) and `command_exit`, which tell the two apart.

  Errors go to stderr as `error: <what> (code N) — <remediation>`, or as one JSON object with `--json`.

### Adele and grants

Anything that reaches beyond the environment goes through Adele, her own container
(`timelike-adele`). She holds every credential, checks each request against a grant the operator
wrote, performs what the grant allows, refuses what it does not before anything happens, and records
everything in her ledger. The agent asks with `adele` (see [What the operator does](#what-the-operator-does)
for the other side).

Nothing of Adele's is mounted into the agent's container: her ledger, her grant file and her
credential live in her container only. She has no outside network in slice 0.

**The stand-in** (`timelike-adele-standin`, compose profile `standin`) is a test and demo service.
It proves the grant path and that the credential never reaches the agent. It proves nothing about any
real provider: those arrive with the features that use them (the Docker socket at 13, fly.io at 14).
Its credential is a canary, generated inside Docker into a volume, never on the host's disk.

### The session scratch

Every tool writes its records and saved output under one scratch directory per session:
`/tmp/timelike/<session>/` (`TIMELIKE_SCRATCH_ROOT`, `TIMELIKE_SESSION`; the session is `default` when
none is set). That is where `run`'s logs, the session events, snapshots, `search`'s saved hit lists,
the `symbols` index and the `services` registry live. The scratch is disposable (contract rule 10): it
survives a container restart, not a recreate. A persistent state root is 07 slice 1, not yet built.

## Install (typical)

**A host needs:**
- **A Docker daemon** (Docker Engine with Compose v2) for building, testing and scanning. Nothing
  else is installed on the host: every tool runs in a pinned container (`pins.env`).
- Python 3.12 or later and pytest, only for the advisory host lane (see [Development](#development)).
  The image pins its own interpreter (3.14.x, `pins.env`).

**Build and bring it up:**

```bash
make build    # the agent, Adele and the stand-in; stamped with `git rev-parse HEAD`; refuses a dirty tree
make up       # the agent, Adele and the stand-in, on the operator's adele/grants.conf
              # (copied from adele/grants.example.conf if it is absent; edit it, then make up again)
```

**Give the agent its work.** The agent container mounts nothing, so bring the project in, as `agent`:

```bash
docker exec timelike-agent git clone <repository> /home/agent/project     # it has egress until slice 2
docker cp ./project timelike-agent:/home/agent/project                     # or copy a local checkout
```

**Attach a harness.** The image ships no harness. A harness's shell commands run in the container as
`agent`, one `docker exec` per command, the way the bench and the demos drive it:

```bash
docker exec timelike-agent bash -lc 'cd ~/project && view .'
```

Or install a harness into an image built `FROM timelike-agent:local` and run it there as `agent`. Either
way, on container start the entrypoint places the [announcement](#announcements--the-environment-says-what-it-offers)
in each harness's user-level context file, so the harness learns the tools without being told.

**One gap to know:** `python3` is not on the agent's PATH. The image's interpreter is
`/opt/timelike/python/bin/python3`; call it by that path, or bring the project's own Python
(a `.venv`, for example).

## Using it

### What an agent sees

**The announcement.** At most 60 lines in the harness's own context file: the tools, one line each, and
the contract's rules in brief. `timelike` lists them all, and `timelike tools` adds curated standard tools
with what can make them wait for a person.

**One session, as the demos ran it** (each line one call; outputs abridged from the recorded transcripts):

```text
view .                                  # 10104 files, 451 dirs …; collapsed 3 (vcs 1, dependency 1, build 1)
search "def get_"                       # 68 matches in 4 files, 50 shown; narrow: search … (44 of the 68)
edit legacy/Invoice.cs --old … --new …  # edited lines 10-16 of 23 (matched ignoring line endings and indentation)
verify changed                          # 1 changed file · 2 test files … · pytest: 3 failed, 0 passed · ruff: 1 diagnostic
run make test                           # verdict: exit 1 (command exited 1) · 4.2 s · 5000 lines · log …
```

**The last line tells the next step.** A result that left something out ends with the exact command that
continues it, never a re-run:
- `more:` the next window, or the rest of a saved output;
- `narrow:` a smaller query that still finds what was shown;
- `expand:` one collapsed directory;
- `do instead:` what to run when this call could not do what was asked (a near match to copy, a
  `search` for a missing definition).

A refusal beyond a grant names the operator's command to extend it, marked as the operator's (`adele`, below).

### The tools

#### Announcements — the environment says what it offers

An agent cannot use a tool it does not know about (P3), so timelike tells it, by default:

- **The announcement** (`/etc/timelike/announcement.md`, at most 60 lines) is generated at image build
  from every installed tool's own `--agent-info`. It names the build revision, and the build fails if it
  misses a tool (`timelike announce --check`).
- **On container start** the entrypoint places it in each harness's user-level context file:
  `~/.claude/CLAUDE.md` (Claude Code), `${CODEX_HOME:-~/.codex}/AGENTS.md` (Codex CLI) and
  `~/.config/opencode/AGENTS.md` (OpenCode). A file there that is not timelike's is never touched.
  `timelike announce --status` says what was placed and why not. Nothing is written inside the
  workspace.
- **`timelike tools`** prints the manifest: every timelike tool, plus curated standard tools, each with
  whether it speaks JSON, what can make it wait for a person (pager, editor, prompt, REPL), and what to
  use instead.

The announcement only announces: every tool works the same whether or not a harness reads it (P7).
The vanilla bench image gets none of this (P6).

#### run — the concluding run

Put `run` in front of any command whose output may be long or which may hang:

```bash
run make test                        # verdict, then head / first errors / tail; $? is make's
run --timeout 300 ./slow-job.sh      # or TIMELIKE_RUN_TIMEOUT=300; the default is 100 s
run sh -c 'make 2>&1 | grep -v noise'  # shell syntax goes through a shell: run takes argv, like timeout(1)
```

- **The verdict comes first,** on the line after the header. It gives the exit code and its cause in
  words, the duration, the line count and the log path:
  `verdict: exit 1 (command exited 1) · 4.2 s · 5000 lines · log /tmp/timelike/default/run/….log`.
- **Long output is never cut in the middle without saying so.** Over the cap (200 lines, or
  `--limit N`), `run` shows:
  - the first 50 lines
  - up to 20 later lines that look like errors, each prefixed with its line number in the log (`L700:`)
  - the last 100 lines
  - `more: sed -n A,Bp <log>`, the exact command that prints the rest. It reads the log; it never
    runs the command again.

  The full output is always in the log.
- **A backgrounded child cannot hold the call.** `run` returns as soon as the command exits, and the
  verdict names anything the command left running (`detached: 1234 node`). It does not stop those
  processes.
- **At the limit, the whole tree stops.** That includes grandchildren, nested `timeout`s and `setsid`
  children. The exit is 124, and the verdict says `timeout` and how to raise the limit. Keep the limit
  below your harness's own call limit (Claude Code: 120 s). Otherwise the harness kills the call before
  `run` can conclude it.
- **`$?` is the command's own:** 0, 1, 42, 126 (cannot execute), 127 (not found), 137 (SIGKILL), and
  so on. `run`'s own outcomes are 2 (usage, before anything runs), 1 (`run` itself failed) and 124 (its
  limit).
- **The command gets no stdin.** A prompt fails fast instead of waiting. `cat x | run grep y` does not
  feed `grep`; write `run sh -c 'cat x | grep y'`.
- **It says why a command died** (slice 1). If the container's memory limit killed it, the verdict says
  `out of memory: limit 96.0 MiB, peak 96.0 MiB` instead of a bare 137. If a filesystem filled up, it
  says `disk full: /work has 0 B free` (the workspace, or the scratch space that holds the log). The
  exit still passes through. When the memory files cannot be read, the verdict says
  `memory: unknown (…)`; it never guesses.
- **Secrets are shown and stored as `[REDACTED:<type>]`** (slice 1): in the shown lines, in the saved
  log (which keeps its line count, so line numbers stay true), in the header and in the session event.
  The verdict counts them (`redacted 2 (key 1, token 1)`). The rules are 18 known provider formats from
  gitleaks, in `/etc/timelike/redaction.toml`. `make scan`'s gitleaks reads the same file, and
  `run --agent-info` lists the rules. If the rules cannot be read, the output is withheld and the
  verdict says why.
- Slice 2 adds log garbage collection and repeat detection.

#### view and search — bounded reads, each ending with the next command

`view` shows a numbered window of a file. `search` finds a pattern and groups the hits by file. Both say
what they left out, and how to get it:

```
view src/engine.py              # lines 1-120 of 412; ends with: more: view src/engine.py:121-240
view src/engine.py:40           # lines 30-50, line 40 marked >
view build/app.o                # binary file: ELF, 18.2 KiB (18640 bytes); content not shown
search parse_args               # 50 hits grouped by file; ends with narrow: search parse_args src  (188 of the 262)
search no_such_thing --strict   # exit 1, as grep does; without --strict, 0 matches exits 0
view .                          # overview in 200 lines; node_modules/ is one line: counts, expand: view node_modules/
view --anchors src/app.py:40-60 # each line with a 6-hex anchor of its content: " 42 a3f9c1 return x"
```

- **Bounded:** a window is 120 lines (`view FILE:A-B` for a range, `--limit 0` for a whole file when you
  mean it), and a search shows 50 hits (`-m N`). Long lines are cut at `COLUMNS` in text and JSON alike,
  and the output names the exact command that reads them whole (`view FILE:N --columns 0`).
- **The rest is never a re-run:** a window's `more:` is the next window; a search's `more:` reads every
  hit from a list saved in the session scratch directory.
- **Ignore rules without git:** `search` skips `.git`, what `.gitignore` and `.git/info/exclude` exclude,
  binary files and files over 16 MiB, and counts each. It reads the ignore files itself, so a
  repository's git configuration runs nothing. `--no-ignore` searches everything but `.git`.
- **Always ends:** a search stops at 30 seconds (`--timeout S`) with exit 124 and names what it reached.
- **An overview to orient** (slice 1): `view DIR` lists the tree within the same 200-line budget,
  directories first and files with their sizes. It respects the ignore files, and collapses `.git`,
  dependency and build directories (and, to fit, deeper ones) into one line each, with counts and the
  `expand:` command.
- **Anchors** (slice 1): `view --anchors` shows each line's anchor, the first 6 hex characters of the
  SHA-256 of its raw bytes. The same content keeps its anchor wherever the line moves; changed content
  gets a new one. `N:anchor` is the form the edit tool (feature 06) is to accept from its slice 1.

#### edit — one exact change, in one call

`edit` replaces text that occurs exactly once in a file, and shows the edited lines numbered as `view`
numbers them (feature 008, prompt 06 slice 0):

```
edit src/app.py --old 'return x' --new 'return x + 1'                 # edited lines 42-42 of 120 (matched exactly)
edit win.c --old $'    if (x) {\n        y();' --new $'    if (x) {\n        y(1);'
                                  # a CRLF, tab-indented file: CRLF and tabs kept (4 spaces = 1 tab)
edit src/app.py --old 'return x' --new 'return x + 1' --dry-run       # the unified diff; nothing written
```

- **Unique or refused:** matching tries the exact bytes, then line endings and trailing whitespace, then
  (over whole lines) indentation under one consistent mapping, and the first level with any match
  decides. Several matches: exit 3 with their line numbers. None: exit 3 with up to three nearest
  candidate regions, numbered, saying what differs. Nothing is written in either case.
- **The file's conventions:** the new text takes the region's line ending and, when the match was by
  indentation, the file's indentation unit.
- **Atomic:** a temporary file beside the target, the target's mode and owner, a check that the file did
  not change meanwhile, then a rename. The file is either fully changed or byte-identical. A hard link
  is broken by the rename, as with `sed -i`, and the verdict says so.
- **No `--yes`:** an edit names its target exactly, applies whole or not at all, and shows what it
  changed, so rule 9 does not confirm it (discovery revision 13). `--dry-run` is the look first;
  `snapshot` and `undo` cover a series.

#### snapshot and undo — wrong turns are recoverable

Take a snapshot before a risky change; `undo` takes the workspace back to it:

```bash
snapshot -m "before the refactor"   # snapshot 3 taken: 245 files, 2.1 MiB (complete)
undo --dry-run                      # exactly what a restore would change; changes nothing
undo --yes                          # restore the newest snapshot (undo 3 --yes for a chosen one)
snapshot list                       # this workspace's snapshots, newest first
```

- **`undo --yes` is the one undo command.** Without `--yes`, `undo` changes nothing and exits 4 with the
  confirmation envelope; its `confirm` is your own command plus `--yes` (contract rule 9).
- **Restored means verified.** After restoring, `undo` reads the workspace again and says "restored"
  only when nothing differs from the snapshot. Before it changes anything it snapshots the state it is
  about to replace, and names that snapshot, so an undo can itself be undone.
- **The workspace** is the nearest directory upward that holds `.git`, else the current directory.
  Your home directory, `/` and their ancestors are refused: change into the project directory first.
- **What a snapshot holds:** every file, symlink and directory, whether git tracks it, ignores it or has
  never seen it, with its permission bits. **Never anything inside a `.git`**, at any depth: history,
  index, stash and hooks are the project's, and neither `snapshot` nor `undo` reads or writes them.
- **Stored once.** Content is stored by its hash, so a repeated snapshot costs only what changed
  (`stored_bytes` in `snapshot --json`). "Taken" is said only after the record and every stored file
  it names are read back and re-hashed; otherwise the snapshot is not taken, and says why.
- **Caps, stated rather than implied.** A snapshot adds at most 256 MiB of new content to the store
  (`TIMELIKE_SNAPSHOT_MAX_BYTES`; content already stored counts as nothing), files up to 64 MiB each
  (`TIMELIKE_SNAPSHOT_MAX_FILE_BYTES`), in a workspace of at most 50,000 entries
  (`TIMELIKE_SNAPSHOT_MAX_ENTRIES`); `0` lifts a cap. Over the size cap the snapshot is **partial**: it
  leaves out the largest new files first and names each one and why. `undo` leaves files that were
  left out alone. Over the entry cap it is refused.
- **Where they live:** in the session scratch directory (`/tmp/timelike/<session>/snapshots/`). They
  survive a container restart, not a recreate, and each `TIMELIKE_SESSION` has its own.
- Slice 1 adds automatic snapshots before destructive commands and a restorable trash.

#### journal — what happened in a session, in order

`journal` reads a session's records and prints one timeline (feature 009, prompt 08 slice 1):

```
journal                          # the last 20 entries of this session, oldest first; ends with: more: journal --all
journal --all-sessions --agent a1
docker exec timelike-adele adeled ledger --json | docker exec -i timelike-agent journal --all-sessions --ledger -
```

- **What it shows:**
  - every timelike tool call, with its arguments, exit and pointer (`run`'s log, a snapshot's id);
  - every `bash -c` and `bash -lc` command, with its exit code;
  - grant uses: the `adele` calls and, for the operator, Adele's ledger rows.

  A shell line that only ran one tool is shown once, as that tool. The tools of a longer command line
  are nested under it.
- **Where the records live:** the session scratch (`/tmp/timelike/<session>/`). `events.jsonl` is written
  by every tool (001). `shell.jsonl` is written by an EXIT trap that `/etc/timelike/shell-env.bash` sets in
  `bash -c` / `bash -lc`. It shadows no command, and the shell's exit status is unchanged. The scratch is
  disposable (rule 10).
- **Not captured:** `sh -c`, interactive shells, direct execs, root's shells, and a command that sets its own
  EXIT trap.
- **Agents and sessions:** a harness running several agents gives each one `TIMELIKE_AGENT` and
  `TIMELIKE_SESSION`. Without them, agents share session `default` and cannot be told apart.
- **Secrets:** every printed command and path goes through rule 15's redaction rules. If the rules cannot
  be loaded, commands are withheld, never printed raw.

#### services — start it, know when it is ready, stop all of it

`services` runs the agent's own long-running processes (feature 010, prompt 09 slice 1):

```
services start web --port 8000 -- /opt/timelike/python/bin/python3 -m http.server 8000
                                # returns when 127.0.0.1:8000 accepts, or it died (exit 1, its log's tail)
services list                   # state, port, uptime; died ones marked
services logs web -n 20
services stop web               # every process of its tree; checks that none remains
```

- **Every start concludes:**
  - ready (exit 0);
  - died before ready (exit 1, with the last log lines);
  - not ready within `--timeout` (60 s): exit 124, and the service is stopped unless `--keep`.

  It never reports success for a process that has exited.
- **The whole tree:** a service's processes carry an inherited marker (`TIMELIKE_SERVICE`). `stop` finds
  them by it, by their hold on the service's log, and by the process group, so a child that called
  `setsid` is still stopped. `stop` re-scans and names anything left.
- **Ports:** a start on a port another registered service holds is refused, naming the holder.
  Readiness checks the loopback address only.
- **No daemon:** the registry is a file in the session scratch, which is disposable. A service whose
  records were cleared shows in `list` as unlisted.
- **Rule 9:** your own `start` and `stop` need no `--yes` (`stop --dry-run` lists the processes).
  Stopping another session's service (`--session S`), or `--all`, asks for `--yes`.

#### symbols — where it is defined, who calls it, what imports it

`symbols` answers structural questions offline, from an index of the workspace (feature 011, prompt 10
slice 1):

```
symbols outline app/models.py      # classes and functions with line ranges and signatures; never bodies
symbols def save                   # where save is defined, best first; exit 3 if nowhere
symbols callers save               # call sites grouped by enclosing function (text-based)
symbols dependents app/models.py   # the files that import it, direct first, ranked
```

- **Precision is stated:** Python is exact (its syntax tree). JS/TS, Go, Rust and shell are read by line
  patterns, and their answers say `text-based`. `callers` is always text-based: name matches, not
  resolved calls.
- **No build step:** every call checks the index file by file, re-reads what changed, and ends its
  verdict with the cache state (`fresh`, `stale: N changed; rebuilt`, `built`).
- **The index lives in the session scratch,** outside the workspace (rule 10), and is rebuilt once per
  session. On 1,000 files that took 1.9 s cold and about 0.3 s warm, measured on the host.

#### verify — failures only, and only what a change affects

`verify` runs tests through `run` and reports the failures, each with its file, line, test name and first
assertion lines (feature 012, prompt 11 slice 1):

```
verify test -- pytest -q        # or: verify pytest -q — "3 failed, 409 passed (pytest)", then each failure
verify npm test                 # the format is read from the output: pytest, jest, vitest, go test, cargo test
verify changed --dry-run        # what an edit could break, and why each test was selected; nothing run
verify changed                  # tests importing the changed files; lint and type-check of those files only
```

- **The exit is the command's** (`verify test`). Any other output falls back to `run`'s verdict, marked
  `format unknown`.
- **`changed` selects by imports:** tests importing a changed file, directly or through one other file,
  from `symbols dependents`. That is a superset, and text-based outside Python; the verdict says so.
  Lint (ruff, eslint) and type-check (mypy, tsc) run on the changed files only.
- **Runners come from the workspace first** (`.venv/bin`, `node_modules/.bin`), then PATH. A selected
  check whose tool is missing is `not run`, and the call exits 1: not running a check is not passing it.
- **The parsers are tested on real runners' output,** recorded by `tests/fixtures/verify/record.sh`, with
  each recording's source beside it.

#### adele — reaching actions, by grant

```bash
adele status                                            # reachable from here? her build revision
adele grants                                            # the grants she applies: limits, spent, live
adele request standin.box create --name tl-1 --ttl 1h --port 8080
```

Beyond its grant, a request exits **4** and nothing is performed. Its output is the grant envelope: the
grant, the limit with what it allows and what the request needed, `performed: false`, and the operator's
exact command to extend it, marked as the operator's (`extend_by: operator`). As JSON, abridged:

```
{"tool": "adele", …, "status": "grant_required", "grant": "e2e", "limit": {"allowed": "8080, 9000-9010", "name": "ports", "needed": "22"}, "extend": "docker exec timelike-adele adeled extend e2e ports 22", "extend_by": "operator", "performed": false, …}
```

### What the operator does

**Grants.** The operator writes `adele/grants.conf` (`make up` copies `adele/grants.example.conf` there
if it is absent; the format is documented in that file). Adele reads it once, at start, read-only. A
malformed file stops her, naming the line at fault, in `docker logs timelike-adele`.

**Extending a grant**, and reading the ledger, while she runs:

```bash
docker exec timelike-adele adeled extend demo budget 2.00 USD   # budget, ttl, instances: set; ports, capabilities: add
docker exec timelike-adele adeled ledger                        # every request, refusal and extension
```

**Reading a session with its grant uses.** Adele's ledger, piped into the journal, places each grant use
in the session's timeline, by session and time:

```bash
docker exec timelike-adele adeled ledger --json | docker exec -i timelike-agent journal --session <s> --all --ledger -
```

**The scan.** `make scan` is the supply-chain gate over the agent, Adele, vanilla and bench-driver
images: Syft and Grype, pip-audit, govulncheck (Adele) and gitleaks. Each image is judged against a
reviewed baseline in `scan/baseline/`; its verdict is in `scan/out/verdict.json`.

## Command reference

Every installed tool, as its own `--help` describes it: what it does, its synopsis, every flag and its
exit codes. This section is generated from the tools themselves by `scripts/readme_reference.py`, and a
unit test (`tests/unit/test_readme_reference.py`) fails when a tool is missing from it or its section
differs from what the tool prints now. After changing a tool, regenerate it:

```bash
python3 scripts/readme_reference.py --write
```

Every tool also answers `--agent-info` with its manifest (JSON), and `timelike tools` lists them all.

<!-- BEGIN command reference: generated by scripts/readme_reference.py --write; do not edit -->

### `adele`

```text
adele: adele [help]
ask Adele to perform a reaching action within the operator's grant; never see a credential
usage:
  adele status                  # is Adele reachable from here; her build revision
  adele grants                  # the grants she applies: limits, spent, live
  adele request standin.box create --name NAME [--ttl 1h] [--port 8080 ...] [--grant G]
  exit 4: beyond the grant; nothing performed; stdout is the grant envelope (operator's command)
options:
  --help  this help (at most 40 lines)
  --json  structured output (default when piped)
  --text  terse text output (default on a terminal)
  --agent-info  machine-readable manifest
  --limit  output cap in lines; 0 = no cap
  --verbose  add timing; warn about event-log failures
  --name  the resource's name
  --ttl  its lifetime, e.g. 30m or 1h (default: the grant's ttl)
  --port  a port it exposes
  --grant  the grant to use (default: the one that allows it)
  --timeout  give up after S seconds
exit codes: 0 ok, 1 unreachable, or the capability failed, 2 usage; or name one with --grant, 3 no grant by that name, 4 beyond the grant, nothing performed, 124 own limit fired
```

### `edit`

```text
edit: file [help]
replace text that occurs exactly once in a file; tolerates CRLF and tab/space indentation
usage:
  edit FILE --old TEXT --new TEXT            # applies only if TEXT matches exactly once
  edit FILE --old TEXT --new TEXT --dry-run  # the unified diff; nothing written
  multi-line TEXT: --old $'line 1\nline 2'; TEXT starting with '-': --old=TEXT
  matching: exact, then ignoring line endings, then indentation (4 spaces = 1 tab, one mapping)
  the new text takes the file's line endings and indentation; the edited lines are shown after
  no match: exit 3 with up to 3 nearest candidates; several: exit 3 with their line numbers
  atomic: the file is fully changed or byte-identical; no --yes (one call; rule 9, revision 13)
options:
  --help  this help (at most 40 lines)
  --json  structured output (default when piped)
  --text  terse text output (default on a terminal)
  --agent-info  machine-readable manifest
  --limit  output cap in lines; 0 = no cap
  --verbose  add timing; warn about event-log failures
  --dry-run  show the plan, change nothing
  --old  the text to replace (must match exactly once)
  --new  the replacement
exit codes: 0 edited, or nothing to change, 1 refused: binary, unwritable, too large, or changed meanwhile; nothing written, 2 usage, 3 no such file, no match, or more than one match; nothing written
```

### `journal`

```text
journal: session [help]
a session's timeline: tool calls, shell commands and grant uses, in order, by agent and session
usage:
  journal                     # the last 20 entries of this session, oldest first
  journal -n N | --all        # the last N entries, or the whole session
  journal --session S         # another session; --all-sessions: every one you can read
  journal --agent A           # only agent A's entries (agents set TIMELIKE_AGENT)
  journal --ledger FILE|-     # merge `adeled ledger --json` rows as grant entries (the operator)
  captured: timelike tools, and bash -c / bash -lc commands (not sh -c or interactive shells)
  records live in the session scratch (/tmp/timelike/<session>/) and are disposable (rule 10)
options:
  --help  this help (at most 40 lines)
  --json  structured output (default when piped)
  --text  terse text output (default on a terminal)
  --agent-info  machine-readable manifest
  --limit  output cap in lines; 0 = no cap
  --verbose  add timing; warn about event-log failures
  -n  the last N entries (default 20)
  --all  the whole session
  --session  another session
  --all-sessions  every readable session
  --agent  only agent A's entries
  --ledger  merge `adeled ledger --json` rows; - = stdin
exit codes: 0 entries shown, or none found, 1 the ledger could not be read, or is not a JSON array, 2 usage, 3 no such session
```

### `run`

```text
run: command [help]
run a command; the call always ends with a verdict, and $? is the command's own exit
usage:
  run [--timeout SECONDS] [--] COMMAND [ARGS...]
  run make test            # verdict, then the output; $? is make's
  run sh -c 'a | b'        # shell syntax goes through a shell
  long output: head, first error lines (error, FAIL, Traceback, … see --agent-info), tail
  secrets in the output are shown and stored as [REDACTED:<type>] (rules: see --agent-info)
options:
  --help  this help (at most 40 lines)
  --json  structured output (default when piped)
  --text  terse text output (default on a terminal)
  --agent-info  machine-readable manifest
  --limit  output cap in lines; 0 = no cap
  --verbose  add timing; warn about event-log failures
  --timeout  stop the whole tree after SECONDS (default 100, or $TIMELIKE_RUN_TIMEOUT)
exit codes: 0 ok, 1 run itself failed, 2 usage, 124 timeout: run's own limit fired, and the command's whole tree was stopped; otherwise the command's own exit
```

### `search`

```text
search: paths [help]
find a pattern in files, hits grouped by file, 50 shown, with how to narrow and see the rest
usage:
  search PATTERN [PATH...]     # recursively, from . by default; Python regex, case-sensitive
    -i ignore case, -F fixed string, -m N show N hits (0 = all), --no-ignore, --strict
    --timeout S (default 30; 0 = none): the search always ends, with 124 if the limit fires
  skips .git, files .gitignore excludes, binary files and files over 16 MiB (all counted)
  zero matches exits 0; with --strict it exits 1, as grep does
  a hit's whole line: view FILE:LINE
options:
  --help  this help (at most 40 lines)
  --json  structured output (default when piped)
  --text  terse text output (default on a terminal)
  --agent-info  machine-readable manifest
  --limit  output cap in lines; 0 = no cap
  --verbose  add timing; warn about event-log failures
  -i  ignore case
  -F  PATTERN is a fixed string
  -m  show at most N hits (0 = all)
  --strict  zero matches exits 1, as grep does
  --no-ignore  also search ignored files
  --timeout  seconds (0 = no limit)
exit codes: 0 ok (zero matches is 0, with count 0), 1 failed; with --strict, also: no match, 2 usage, 3 no such path, 124 the time limit fired
```

### `services`

```text
services: session [help]
start, list, read and stop your long-running processes; start returns when ready or dead
usage:
  services start NAME --port N -- CMD ARG…  # returns when 127.0.0.1:N accepts, or it died
  services start NAME --ready-log REGEX -- CMD  # ready when a log line matches
  services list                             # state, port, uptime; died ones marked
  services logs NAME [-n N]                 # the log's last lines
  services stop NAME [--dry-run]            # every process of its tree; checks none remains
  services stop NAME --session S --yes      # another session's service (confirmed)
  services stop --all --yes                 # every service of this session (confirmed)
  not ready within --timeout (60 s): exit 124 and stopped, unless --keep
options:
  --help  this help (at most 40 lines)
  --json  structured output (default when piped)
  --text  terse text output (default on a terminal)
  --agent-info  machine-readable manifest
  --limit  output cap in lines; 0 = no cap
  --verbose  add timing; warn about event-log failures
  --dry-run  show the plan, change nothing
  --yes  confirm the mutation
  --port  start: ready when 127.0.0.1:N accepts
  --ready-log  start: ready when a log line matches
  --timeout  start: readiness limit (default 60 s)
  --keep  start: leave it running when not ready in time
  --cwd  start: working directory
  --session  stop/logs: another session's service
  --all  stop: every service of this session
  --all-sessions  list: every session
  -n  logs: last N lines (default 50)
exit codes: 0 ok, 1 died, refused, or processes survived a stop, 2 usage, 3 no such service, 4 confirmation required: rerun with --yes, 124 not ready in time
```

### `snapshot`

```text
snapshot: workspace [help]
take a snapshot of the workspace (every file, git-ignored ones too) so undo can restore it
usage:
  snapshot [-m TEXT]       # take one: prints its id, file count and size, and what was left out
  snapshot list            # this workspace's snapshots, newest first
  undo [ID] --yes          # restore one (the newest by default); undo --dry-run shows the changes
  workspace: the nearest directory upward holding .git, else here; never ~ or /
  caps: TIMELIKE_SNAPSHOT_MAX_BYTES, TIMELIKE_SNAPSHOT_MAX_FILE_BYTES, TIMELIKE_SNAPSHOT_MAX_ENTRIES (0 = none)
options:
  --help  this help (at most 40 lines)
  --json  structured output (default when piped)
  --text  terse text output (default on a terminal)
  --agent-info  machine-readable manifest
  --limit  output cap in lines; 0 = no cap
  --verbose  add timing; warn about event-log failures
  -m  a short label for the snapshot
exit codes: 0 ok, 1 refused (home, root, over the entry cap) or failed, 2 usage, or a cap variable that is not a number
```

### `symbols`

```text
symbols: query [help]
where a name is defined, who calls it, what imports a file, a file's outline; never bodies
usage:
  symbols outline FILE          # classes and functions with line ranges and signatures
  symbols def NAME              # where NAME (or Outer.NAME) is defined, best first; 3 if nowhere
  symbols callers NAME          # call sites grouped by enclosing function (text-based)
  symbols dependents FILE…      # the files that import these, ranked
  python is exact (its syntax tree); JS/TS, Go, Rust and shell are text-based, and say so
  the index lives in the session scratch and is refreshed per file on every call
options:
  --help  this help (at most 40 lines)
  --json  structured output (default when piped)
  --text  terse text output (default on a terminal)
  --agent-info  machine-readable manifest
  --limit  output cap in lines; 0 = no cap
  --verbose  add timing; warn about event-log failures
exit codes: 0 answered, 1 the workspace could not be read, 2 usage, 3 not found, 124 the index walk hit its limit before the answer could be complete
```

### `timelike`

```text
timelike: environment [help]
The agent environment: build revision, output contract version, timelike tools on PATH
usage:
  timelike [--json|--text]
  timelike tools             timelike and standard tools: JSON support, interactivity risk, instead
  timelike announce          the announcement placed for harnesses; --check, --status, --install
  timelike budget            memory, CPU, process and disk limits, and what is in use
  timelike --agent-info      manifest, including the build revision
options:
  --help  this help (at most 40 lines)
  --json  structured output (default when piped)
  --text  terse text output (default on a terminal)
  --agent-info  machine-readable manifest
  --limit  output cap in lines; 0 = no cap
  --verbose  add timing; warn about event-log failures
  --write  announce: write the announcement to PATH
  --check  announce: exit 1 naming tools missing from it
  --install  announce: place it for each harness
  --status  announce: report each placement
exit codes: 0 ok, 1 failure, 2 usage
```

### `timelike-conform`

```text
timelike-conform: timelike tools on PATH [help]
Check every timelike tool on PATH against the output contract (C1-C9)
usage:
  timelike-conform [--json|--text]   check every tool in TIMELIKE_BIN_DIRS that is on PATH
  timelike-conform --list            list the tools it would check, without running them
options:
  --help  this help (at most 40 lines)
  --json  structured output (default when piped)
  --text  terse text output (default on a terminal)
  --agent-info  machine-readable manifest
  --limit  output cap in lines; 0 = no cap
  --verbose  add timing; warn about event-log failures
  --list  list the tools to check; run nothing
exit codes: 0 every tool conforms, 1 a tool fails a check, or none was found, 2 usage
```

### `undo`

```text
undo: workspace [help]
restore the workspace to a snapshot (the newest by default); dry run first, verified after
usage:
  undo --dry-run           # list exactly what a restore would change; change nothing
  undo --yes               # restore the newest snapshot, verify it, keep the replaced state
  undo ID --yes            # restore snapshot ID (see: snapshot list)
  without --yes: exit 4 and the confirmation envelope (its confirm is undo … --yes)
  never touches any .git; files left out of the snapshot are left alone
options:
  --help  this help (at most 40 lines)
  --json  structured output (default when piped)
  --text  terse text output (default on a terminal)
  --agent-info  machine-readable manifest
  --limit  output cap in lines; 0 = no cap
  --verbose  add timing; warn about event-log failures
  --dry-run  show the plan, change nothing
  --yes  confirm the mutation
exit codes: 0 ok (restored and verified, or nothing to change), 1 refused, or the restore could not be verified, 2 usage, 3 no such snapshot, 4 confirmation required: rerun with --yes
```

### `verify`

```text
verify: tests [help]
run tests and see only the failures, with file and line; or check only what a change affects
usage:
  verify test [--timeout S] -- CMD [ARG...]   failures only; $? is CMD's
  verify CMD [ARG...]                         the same (CMD is not test or changed)
  verify changed [--since REF] [--timeout S] [--dry-run]
    tests importing the changed files, lint and type-check of the changed files only
  formats: pytest, jest, vitest, go test, cargo test; others: run's verdict, format unknown
  lint: ruff, eslint; type-check: mypy, tsc; looked up in .venv/bin, node_modules/.bin, PATH
  global flags (--json, --text, --limit) go before test, changed or CMD
options:
  --help  this help (at most 40 lines)
  --json  structured output (default when piped)
  --text  terse text output (default on a terminal)
  --agent-info  machine-readable manifest
  --limit  output cap in lines; 0 = no cap
  --verbose  add timing; warn about event-log failures
exit codes: 0 passed, or nothing selected, 1 failures, a selected check not run, or run itself failed, 2 usage, or changed outside a git repository, 124 a command hit run's time limit; otherwise the command's own exit
```

### `view`

```text
view: file [help]
show a numbered window of a file (120 lines); ends with the command for the next window
usage:
  view FILE              # lines 1-120, or the whole file if it is shorter
  view FILE:A-B          # lines A to B
  view FILE:N            # line N with 10 lines of context each side, N marked >
  view FILE --limit 0    # the whole file, when you mean it
  view DIR               # overview in 200 lines; dependency, build and .git dirs collapsed
  view --anchors FILE    # each line with a 6-hex anchor of its content (edit accepts N:anchor)
  a binary file prints its type and size, not its bytes; search finds text across files
  note: where vim is installed, its `view` is shadowed (/opt/timelike/bin is first on PATH)
options:
  --help  this help (at most 40 lines)
  --json  structured output (default when piped)
  --text  terse text output (default on a terminal)
  --agent-info  machine-readable manifest
  --limit  output cap in lines; 0 = no cap
  --verbose  add timing; warn about event-log failures
  --anchors  show each line's anchor (6 hex of its sha256)
  --no-ignore  overview: list ignored entries
  --columns  cut lines at N characters for this call (default COLUMNS; 0 = whole lines)
exit codes: 0 ok, 1 the file could not be read, 2 usage, 3 no such file
```

<!-- END command reference -->

## Development

### Build, test, scan

```bash
make build        # stamps the image with `git rev-parse HEAD`; refuses an empty stamp or a dirty tree
make test         # Docker lane (authoritative): bats end-to-end from outside the container + unit tests
make test-host    # host lane (advisory): agentio/conform unit tests + a check of the env-layer files
make lint         # shellcheck, ruff, mypy --strict; gofmt, go vet, staticcheck (Adele)
make up           # agent + Adele + the stand-in, on the operator's adele/grants.conf
make scan         # supply-chain gate: Syft+Grype, pip-audit, govulncheck (Adele), gitleaks
make demo         # the manual demo: git commit / rebase --continue / log return in seconds
make bench        # the speedup bench (feature 002): vanilla vs timelike; traces and report in bench/out/
```

`make test` writes its results to `tests/out/`: `summary.json`, the bats TAP and JUnit output, and
the full log. `make test` starts Adele on the lane's own grant file and clears her volumes first, so
every run starts from an empty ledger. Run `make up` afterwards for the operator's own grants.

### Two verification lanes

| Lane | Proves | Authoritative for |
|---|---|---|
| **Docker** (`make test`) | the built image, driven from outside the way a harness drives it | the acceptance criteria, the build stamp, the scan gate |
| **Host** (`make test-host`) | `agentio` and `timelike-conform` behaviour; the env-layer *files* | nothing on its own: file evidence, not image evidence |

A host-lane pass never counts as an acceptance-criterion pass.

### Speedup bench

```bash
make bench                              # every catalog task, in the vanilla image and the timelike image
make bench TASKS=git-rebase-continue    # one task (space-separated for several)
less bench/out/<run-id>/report.txt      # the report
```

`make bench` builds three images from the pinned base, all stamped with the checkout's revision:
- the agent image
- a **vanilla** baseline: the same base, the same unprivileged user and git, and the same agent
  runtimes (Python and Node) with their stock behaviour, without any of timelike's layers
- the bench **driver**, the only container that holds the Docker socket

The driver refuses any image whose revision label differs from the checkout, and refuses to start if
an API-key-shaped variable is present. It runs each task in a fresh container for each environment, with
every tool call a non-interactive `bash -c` with no terminal. It writes one trace per run to
`bench/out/<run-id>/traces/` and a report to `bench/out/<run-id>/report.txt`. `timelike-bench report
<dir>` rebuilds the report from the traces alone.

**Read the report's first line.** Slice 0 drives the tasks with a deterministic fake agent, and every
report it produces begins:

> FAKE-AGENT BENCH PIPELINE DEMO RUN -- This is not a test of timelike, rather a test of the bench test
> itself (its presentation and usefulness to the human user). The agent's policy was written by
> timelike's own builders.

The fake agent's policy, the task selection and the recoveries it takes were all chosen by the people
who built timelike, so a fake-agent report shows that the bench runs, traces and reports. It is not
evidence that timelike helps.

After the maintainer statement, the reproduce command and the exact revisions, harness and model
compared, the report lists the tasks where timelike **loses** first, then the ties and the wins. Each
task says what it tests and what differs between the two images, gives the verdict in words, shows the
metrics, and then tells what happened in each image call by call and why the run ended as it did.
Tokens appear only in an appendix.

### Layout

```
image/        Dockerfile and the fallback config layer (/etc/gitconfig, /etc/profile.d)
tools/        agentio (the contract) and the tools on PATH in the image
tests/        unit (pytest), e2e (bats, driven from outside), host (advisory), fixtures, runner
adele/        Adele (Go, FROM scratch): adeled, the test-only stand-in, grants.example.conf
scan/         the supply-chain gate (the agent, Adele, vanilla and driver images)
bench/        the speedup bench: benchlib, timelike-bench, the vanilla and driver images, run.sh
scripts/      the manual demo, and the README's command-reference generator
compose.yaml  the agent (no capabilities, no-new-privileges, no Docker socket), Adele, the stand-in
pins.env      every pinned image and version
```

### Governance

`.specswarm/` holds the constitution, the tech stack and the quality standards, each recording the
discovery revisions it was audited against. Each feature's specification, plan, contracts, tasks,
decision log and cycle reports are under `.specswarm/features/`; maintenance cycles are under
`.specswarm/maintenance/`.

### Licence

MIT.

## Thank You Mr Gödel

Thanks to Kurt Gödel for everything he was and everything he did for philosophy, reasoning and a truly human sense of
reality. Mr. Gödel, we used a lot of your terms in this project primarily because you were so good at naming things, but
also because we love you for your creativity and deep capacity for observation. We hope our use of your terminology is
praise, not simple appropriation. For anyone who needs to know more about Kurt Gödel (that would be you, dear reader),
please start with this short article by Natalie Wolchover,
[How Gödel’s Proof Works](https://www.quantamagazine.org/how-godels-proof-works-20200714/). After that, check out Sam
Marks' great book review of Gödel, Escher, Bach at
[Less Wrong](https://www.lesswrong.com/posts/wwNnzaPnB5a48K86N/book-review-goedel-escher-bach-an-in-depth-explainer),
then dive into the wonderful deep end with Michael Graziano and his
[Theory of Subjective Experience](https://www.goodreads.com/book/show/43726566). Or maybe simply sit back in your chair
and think back about that one scene from Garden State... Largeman, "Hey Albert? Good luck exploring the infinite
abyss." Albert, "Thanks. Hey, you too." Rest in peace, Kurt Gödel. Peace to you as well. Yeah, you.
