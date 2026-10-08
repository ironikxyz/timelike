# timelike

A containerised shell environment for coding agents. Everything the agent runs behaves
non-interactively however the harness starts the shell, the agent holds no privilege, and every
timelike tool speaks one output contract.

This repository holds the environment. Its governance is in `.specswarm/`: the constitution, the tech
stack and the quality standards. Each feature has its specification, plan, contracts and decision log
under `.specswarm/features/`.

## Status

**Feature 001, slice 0: agent shell baseline and output contract.**
- The image: Debian trixie-slim with a pinned interpreter, an unprivileged `agent` user, no sudo or
  setuid binaries, and non-interactive defaults in the process environment.
- `agentio`: the output-contract module.
- `timelike`: environment info and build revision.
- `timelike-conform`: the conformance check.
- A supply-chain scan gate.

**Feature 002, slice 0: speedup bench (skeletal).** One command runs catalog tasks in a vanilla
image and in the timelike image, under a deterministic fake agent, and writes a trace per run and a
report. See "Speedup bench" below.

**Feature 003, slice 0: concluding run (skeletal).** `run COMMAND` always ends with a verdict:
- it returns when the command exits, even if something the command backgrounded still holds the
  output
- at its limit it stops the command's whole process tree
- it shows the head, the first errors and the tail of long output, with the exact command for the
  rest
- `$?` is the command's own exit

**Slice 1 (natural, built on `modify/003-slice-1`):** the verdict names a memory kill (limit and
peak) and a full filesystem (which one, and its free space), and secrets are shown and stored as
`[REDACTED:<type>]`. See "run" below.

**Feature 004 (prompt 12), slice 0: Adele and grants (skeletal).** Adele is the one authority,
outside the agent's privilege, that holds credentials and enforces the operator's grants. In slice 0
she brokers one capability, an in-compose **stand-in** that is not a provider, with a synthetic
credential the agent never sees. See "Adele" below.

This README makes no claims about timelike's value. Those are made only from reproducible bench
results (constitution P6).

## Needs

- **A Docker daemon** (Docker Engine with Compose v2) for building, testing and scanning. Nothing
  else is installed on the host: every tool runs in a pinned container (`pins.env`).
- Python 3.12 or later and pytest, only for the advisory host lane below. The image pins its own
  interpreter (3.14.x, `pins.env`).

## Build, test, scan

```bash
make build        # stamps the image with `git rev-parse HEAD`; refuses an empty stamp or a dirty tree
make test         # Docker lane (authoritative): bats end-to-end from outside the container + unit tests
make test-host    # host lane (advisory): agentio/conform unit tests + a check of the env-layer files
make lint         # shellcheck, ruff, mypy --strict; gofmt, go vet, staticcheck (Adele)
make up          # agent + Adele + the stand-in, on the operator's adele/grants.conf
make scan         # supply-chain gate: Syft+Grype, pip-audit, govulncheck (Adele), gitleaks
make demo         # the manual demo: git commit / rebase --continue / log return in seconds
make bench        # the speedup bench (feature 002): vanilla vs timelike; traces and report in bench/out/
```

`make test` writes its results to `tests/out/`: `summary.json`, the bats TAP and JUnit output, and
the full log.

### Two verification lanes

| Lane | Proves | Authoritative for |
|---|---|---|
| **Docker** (`make test`) | the built image, driven from outside the way a harness drives it | the acceptance criteria, the build stamp, the scan gate |
| **Host** (`make test-host`) | `agentio` and `timelike-conform` behaviour; the env-layer *files* | nothing on its own: file evidence, not image evidence |

A host-lane pass never counts as an acceptance-criterion pass.

## Environment defaults

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

## The output contract

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

## run — the concluding run

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

## snapshot and undo — wrong turns are recoverable

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

## Announcements — the environment says what it offers

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

## view and search — bounded reads, each ending with the next command

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

## edit — one exact change, in one call

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

## journal — what happened in a session, in order

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

## services — start it, know when it is ready, stop all of it

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

## symbols — where it is defined, who calls it, what imports it

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

## verify — failures only, and only what a change affects

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

## Speedup bench

```bash
make bench                              # every catalog task, in the vanilla image and the timelike image
make bench TASKS=git-rebase-continue    # one task (space-separated for several)
less bench/out/<run-id>/report.txt      # the report
```

`make bench` builds three images from the pinned base, all stamped with the checkout's revision:
- the agent image
- a **vanilla** baseline: the same base, the same unprivileged user and git, without any of
  timelike's layers
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

## Adele — reaching actions, by grant

Anything that reaches beyond the environment goes through Adele, her own container
(`timelike-adele`). She holds every credential, checks each request against a grant the operator
wrote, performs what the grant allows, refuses what it does not before anything happens, and records
everything in her ledger. The agent asks with `adele`:

```bash
adele status                                            # reachable from here? her build revision
adele grants                                            # the grants she applies: limits, spent, live
adele request standin.box create --name tl-1 --ttl 1h --port 8080
```

Beyond its grant, a request exits **4** and nothing is performed. The refusal names the grant, the
limit, what it allows, what the request needed, and the operator's exact command to extend it:

```
error: beyond grant demo: limit ports allows 8080, this request needs 22; nothing was performed (code 4) — the operator extends it: docker exec timelike-adele adeled extend demo ports 22
```

(Slice 0 prints this refusal on stderr. Its envelope on stdout waits on a decision about 001's exit-4
contract.)

**The operator** writes `adele/grants.conf` (`make up` copies `adele/grants.example.conf` there if it
is absent; the format is documented in that file). Adele reads it once, at start, read-only. A
malformed file stops her, naming the line at fault, in `docker logs timelike-adele`. While she runs:

```bash
docker exec timelike-adele adeled extend demo budget 2.00 USD   # budget, ttl, instances: set; ports, capabilities: add
docker exec timelike-adele adeled ledger                        # every request, refusal and extension
```

Nothing of Adele's is mounted into the agent's container: her ledger, her grant file and her
credential live in her container only. She has no outside network in slice 0.

**The stand-in** (`timelike-adele-standin`, compose profile `standin`) is a test and demo service.
It proves the grant path and that the credential never reaches the agent. It proves nothing about any
real provider: those arrive with the features that use them (the Docker socket at 13, fly.io at 14).
Its credential is a canary, generated inside Docker into a volume, never on the host's disk.

`make test` starts Adele on the lane's own grant file and clears her volumes first, so every run
starts from an empty ledger. Run `make up` afterwards for the operator's own grants.

## Layout

```
image/        Dockerfile and the fallback config layer (/etc/gitconfig, /etc/profile.d)
tools/        agentio (the contract) and the tools on PATH in the image
tests/        unit (pytest), e2e (bats, driven from outside), host (advisory), fixtures, runner
adele/        Adele (Go, FROM scratch): adeled, the test-only stand-in, grants.example.conf
scan/         the supply-chain gate (the agent, Adele, vanilla and driver images)
bench/        the speedup bench: benchlib, timelike-bench, the vanilla and driver images, run.sh
compose.yaml  the agent (no capabilities, no-new-privileges, no Docker socket), Adele, the stand-in
pins.env      every pinned image and version
```

## Licence

MIT.
