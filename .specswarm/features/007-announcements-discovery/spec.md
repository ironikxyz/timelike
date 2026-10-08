---
parent_branch: master
feature_number: "007"
status: In Progress
created_at: 2026-10-04T19:47:32+00:00
source_prompt: plan/.discover/prompts/04-announcements-discovery.md
source_send: bridge/sends/04-rev1-20261004-183704.md
prompt_revision: 1
discovery_revision: 12
audited_against: [1, 13, 14]
slice: 0
---

# Feature: Announcements and discovery (prompt 04, slice 0: skeletal)

## Overview

An agent cannot use a tool it does not know about (P3). Today an agent dropped into timelike learns
about `run`, `view`, `search` or `snapshot` only if the operator tells it, and the comparison the
bench makes (P6) is between a *told* and an *untold* agent. This feature makes the environment
announce itself, by default, in the places agents already read at start-up:

- **An announcement** of at most 60 lines: what timelike is, each installed timelike tool with its one-line
  purpose, and the few rules that change how an agent works here. It is generated at image build from the
  installed tools' own manifests (`--agent-info`), so it cannot drift from them, and it names the build
  revision it describes (cross-stack P003).
- **On container start** it is placed in each supported harness's **user-level** context file (Claude
  Code, Codex CLI; OpenCode as well), never overwriting a file that is not timelike's.
- **One command, `timelike tools`,** prints a manifest of every timelike tool and of curated standard
  tools: whether it speaks JSON, whether it can hang or wait for a person (interactivity risk), and what to
  use instead.

**Slices:** slice 0 (this spec, skeletal) is the announcement, its placement and the manifest command.
Slice 1 (not built here) adds command-not-found guidance, unprivileged package installs and the
resource-budget command.
*(Revised, modify cycle 3, send `…-161802`: slice 1 is now specified in § Slice 1 below, declared. Slice 0's
text above is kept as built.)*

**Harness-agnostic (P7, T3):** the announcement only *announces*. Every tool works the same whether or
not a harness reads it.

## User Scenarios

### Actors

- **Agent** (primary): starts in the container through a harness, and reads its context files at start-up.
- **Operator** (administrative): starts the container, and in the D4 demo says nothing about timelike.
- **Harness** (autonomous intermediary): Claude Code, Codex CLI or OpenCode, which load their user-level
  context files when a session starts.

### Scenario 1: an agent told nothing (D4)

1. The operator starts `timelike-agent` and starts an agent session with a task. The operator says nothing
   about timelike.
2. The harness loads its user-level context file, which holds timelike's announcement.
3. Asked to read part of a large file, the agent runs `view FILE:A-B` rather than `sed -n … | nl`,
   because the announcement told it `view` exists.

### Scenario 2: the manifest

1. The agent runs `timelike tools`.
2. It gets one entry per timelike tool (from the tool's own manifest) and per curated standard tool, each
   with `json`, `interactive_risk` and `instead`. For example, `less` is a pager, so its risk is that it
   waits for a key and `instead` is `view FILE`.

### Edge cases

- **The user-level file already exists and is not timelike's** (the operator mounted their own
  `~/.claude/CLAUDE.md`): it is left untouched, and `timelike announce --status` names it as *not
  placed: a file that is not timelike's is there*.
- **The file is timelike's own, from an older image** (it carries timelike's marker line): it is replaced
  by the current announcement, so a rebuilt image never leaves a stale announcement behind.
- **`$HOME` is not writable** (an operator's read-only mount): the container still starts. Placement is
  best effort, and `timelike announce --status` names what could not be placed and why.
- **Codex's `AGENTS.override.md`** exists in its home: Codex reads that file instead of `AGENTS.md`, so
  the announcement is not read there, and `--status` says so.
- **A tool's `--agent-info` fails at build:** the build fails and names the tool. An announcement missing
  a tool is the drift this feature exists to prevent.

## Functional Requirements

### The announcement

- **FR-1** The announcement is generated at image build by `timelike announce` from the `--agent-info`
  manifest of every executable in `/opt/timelike/bin`. It is stored at
  `/etc/timelike/announcement.md`, read-only, after the build stamp, and it names that revision on its
  first lines.
- **FR-2** It is **at most 60 lines** (the prompt's bound), Markdown, and holds:
  - a first line that marks it as timelike's: `<!-- timelike announcement: revision <sha>; generated
    from the tools' manifests; do not edit -->`;
  - one line naming the environment and the revision;
  - one line per installed timelike tool: `- \`name\` — summary`, with the summary from its
    manifest;
  - **the rules that change how an agent works here:**
    - outputs are bounded and end with the exact next command;
    - `--json` is everywhere;
    - long or hanging commands go through `run`;
    - `timelike tools` prints the full manifest;
  - a closing line saying it changes nothing about how the tools work (P7).
- **FR-3** **Every installed timelike tool is in it.** `timelike announce --check` exits 1 and names each
  missing tool when the announcement and `/opt/timelike/bin` disagree. The image build runs the check, so
  an image whose announcement misses a tool is never built. A test (unit and e2e) fails on the same
  condition (the criterion's "a test fails").
- **FR-4** `timelike announce` prints it (stdout); `--json` gives the same lines and the tool list.

### Placement on container start (send seam 1)

- **FR-5** The image's entrypoint runs `timelike announce --install`, then `exec`s the container's
  command. It places the announcement in each supported harness's **user-level** context file:
  - **Claude Code:** `~/.claude/CLAUDE.md`;
  - **Codex CLI:** `${CODEX_HOME:-~/.codex}/AGENTS.md`;
  - **OpenCode:** `~/.config/opencode/AGENTS.md`. OpenCode also falls back to `~/.claude/CLAUDE.md`.
- **FR-6** **Never overwrite what is not timelike's.** An absent file is written. A file whose first line is
  timelike's marker is replaced with the current announcement. Any other file is left byte for byte.
- **FR-7** **Never inside the workspace.** The workspace's own `CLAUDE.md` / `AGENTS.md` are not created
  or changed, whether or not they exist (rule 10, revision 11; send seam 1). ~~*This narrows the
  criterion's "and in the workspace's agent context file when none exists"*: see Decisions D-1 and
  FOR-MENTOR Item 19.~~ *(Revised, revision 13: the criterion no longer asks for the workspace file; its
  clause is struck, so FR-7 narrows nothing. D-1 resolved; Item 19 closed 2026-10-05.)*
- **FR-8** **Never blocks the container.** A placement that fails (unwritable home, a directory where a
  file should be) is skipped, the reason is recorded, and the entrypoint still `exec`s the command.
  `timelike announce --status` reports each location: `placed`, `current` (already timelike's, at this
  revision), `not placed: <why>`, or `shadowed: <file> is read instead` (Codex's override).

### The manifest command

- **FR-9** `timelike tools` prints one entry per timelike tool and per curated standard tool:
  - `name`;
  - `kind` (`timelike` or `standard`);
  - `installed` (the name resolves on `PATH`);
  - `summary`;
  - `json` (`yes`, `partial: <how>`, or `no`);
  - `interactive_risk` (`none`, or what it can do: `pager`, `editor`, `prompt`, `repl`, `waits`, `unbounded output`);
  - `instead` (a safer command, or empty).
- **FR-10** **Timelike entries come from the tools' manifests**: `summary` from `--agent-info`, `json`
  `yes` (contract rule 1), and `interactive_risk` `none` (rule 4), unless a manifest declares otherwise.
- **FR-11** **Curated entries** come from a file shipped in the image,
  `/etc/timelike/standard-tools.json` (`TIMELIKE_STANDARD_TOOLS` overrides it for tests). Each entry
  states its `json`, `interactive_risk` and `instead`. The set covers the traps agents hit:
  - pagers and editors (`less`, `more`, `vi`, `nano`);
  - unbounded readers (`cat`, `grep -r`, `find`, `ls -R`, `tree`);
  - REPLs (`python3`, `node` with no script);
  - prompting commands (`ssh`, `sudo`, `npm init`);
  - long or hanging runs (`make`, `pytest`, `npm test`, `curl`);
  - `git` (pager and editor pinned by 001's layer).
- **FR-12** Text output is one line per entry, sorted timelike first and then by name, and within the
  output contract's 200-line cap. JSON carries `tools: [...]` with every field. It follows the output
  contract (header, verdict, `--json`).

### P6 and the bench (send seam 2)

- **FR-13** ~~The **vanilla** bench image (`bench/vanilla/Dockerfile`) is not changed. A unit test checks
  it references none of this feature's paths, and an e2e cell checks the vanilla image's home holds no
  announcement.~~ The timelike arm of the bench uses the agent image, so its agents now see the
  announcement. That is the *told by the environment* condition this feature creates.
  *(Revised, discovery revision 14, modify cycle 4, declared: the vanilla image is no longer untouched. It
  gains **the same agent runtime binaries** as the agent image (FR-25), **with stock behaviour**: its agent
  interpreter keeps the `EXTERNALLY-MANAGED` marker, npm keeps its default prefix, and none of timelike's
  configuration goes in (no `pip.conf`, no `npmrc`, no `~/.local/bin` on `PATH`, no announcement, no
  missing-commands data, no entrypoint). RB1 ("a prerequisite goes into both images or neither") stays whole.
  The unit test checks the vanilla Dockerfile references none of timelike's configuration paths and does
  carry the runtime pins; the e2e cell checks the same runtimes are present at the same versions, with stock
  behaviour, and still no announcement.)*

## Success Criteria

The criterion text is the send's, copied exactly. Each automated criterion is one e2e file in the
image, under `bash -c` and `bash -lc`.

### Automated

- **SC-1:** "On container start, a timelike announcement of at most 60 lines is present in each supported
  harness's user-level context location~~ and in the workspace's agent context file when none exists~~
  _(struck, revision 13: user level only; a committed workspace announcement would announce tools that exist
  only in timelike)_, without overwriting an existing one". *(Revised, revision 13: the quotation is the
  criterion as revision 13 states it, copied by modify cycle 2, declared; the clause it struck is kept struck.)*
  **Tested**, against a freshly started throwaway container from the verified image:
  - the files exist at FR-5's paths, are at most 60 lines, and are byte-identical to
    `/etc/timelike/announcement.md`;
  - a pre-existing non-timelike file at one location (a throwaway started with that file placed) is
    unchanged.

  ~~The workspace part is not built (D-1). The test asserts the workspace is left untouched, so the
  narrowing is visible in the result rather than silent.~~ *(Revised, revision 13: the workspace part is
  struck from the criterion, so there is nothing to build. The test still asserts the workspace is left
  untouched, which is now the criterion's own reading (D-1, resolved).)*
- **SC-2:** "The announcement is generated from the installed tools' manifests, and a test fails if any
  installed timelike tool is missing from it". Every executable in `/opt/timelike/bin` appears with the
  summary its own `--agent-info` gives, and `timelike announce --check` exits 0. A copy of the
  announcement with one tool's line removed makes `--check` exit 1 and name that tool.
- **SC-3:** "One command prints a manifest of every timelike tool and curated standard tools with fields
  for JSON support, interactivity risk and safer alternative". `timelike tools --json` lists every tool in
  `/opt/timelike/bin` and every curated entry, each with `json`, `interactive_risk` and `instead`.

### Manual

- **SC-4:** "DEMO: the Agent, told nothing about timelike by the Operator, uses a timelike tool it learned
  about from the environment's announcement" (D4). The mentor captures it after the lane; it stays
  `unconfirmed` until then.

### Measurable outcomes

- The announcement is never longer than 60 lines and never names a tool that is not installed, or misses
  one that is (FR-3, checked at build).
- Starting the container is not delayed by more than 1 second by placement (measured in the e2e cell).

## Key Entities

- **Announcement:** the generated Markdown, its marker line and its revision.
- **Placement:** a harness, its user-level path, and a state (`placed` | `current` | `not placed` | `shadowed`).
- **Manifest entry:** `name`, `kind`, `installed`, `summary`, `json`, `interactive_risk`, `instead`.

## Decisions (the send's seams, decided here; reasoning in `research.md`)

**D-1 · Where the announcement is written: user level only.** The send: *"Write at the user level in the
image, and say which file each supported harness reads. Writing into a project's files would be a tracked
change the operator never asked for."* Rule 10 (revision 11) keeps state out of the workspace, and a
context file created in a repository is exactly such an unasked-for change. **The criterion also says
"and in the workspace's agent context file when none exists".** The send's seam and the criterion's text
disagree. This spec follows the seam and does not build the workspace part, and SC-1 asserts the
workspace is untouched. **FLAGGED, medium confidence, not a pause:** the seam is the mentor's explicit
instruction for this batch, and the narrowing is visible. Raised as **FOR-MENTOR Item 19**, for plan to
amend the criterion or overrule the seam. No pause file, because the decision has an informed basis: the
send names it.

**D-1 resolved by discovery revision 13 (Q3, option (b)), plan `394c33e`** *(appended by modify cycle 2,
send `…-095251`, declared; the reasoning above is kept as written)*. Plan amended the criterion: its workspace clause
is struck ("user level only; a committed workspace announcement would announce tools that exist only in timelike").
The FLAGGED decision is now the rule, not a deviation from it. Nothing was built differently, and nothing is built
now. FOR-MENTOR Item 19 has been closed since 2026-10-05.

**D-2 · On container start, from an entrypoint.** Generating at build and placing at start (not at build
into `/home/agent`) covers a home that is a volume or a mount, and a harness that recreates its
directory. The entrypoint is best effort and always `exec`s the command (FR-8).

**D-3 · Which harnesses.** The prompt asks for Claude Code and one of Codex CLI or OpenCode. All three are
placed, because each is one file and OpenCode's fallback already reads Claude Code's. Each location is
from the harness's own documentation (research R1).

**D-4 · The command's name.** `timelike tools` and `timelike announce`: subcommands of the environment's
own command, which `timelike` already is (its revision and tool list). They add no new name on `PATH`.

**D-5 · P6 (send seam 2).** The vanilla Dockerfile is untouched, checked by a unit test and an e2e cell.
The agent image's ENTRYPOINT changes, so the bench's timelike arm and `make scan`'s agent image change
(declared).

**D-6 · No drift (send seam 3).** Generated at build from `--agent-info`, after the stamp, and checked
at build (FR-3). The marker line carries the revision.

## Out of scope (slice 0)

Command-not-found guidance, unprivileged `pip`/`npm` installs, the resource-budget command (slice 1). *(Revised, modify cycle 3: specified in § Slice 1.)*
~~The workspace context file (D-1, raised).~~ *(Revised, revision 13: not out of scope but struck from the
criterion; D-1 resolved.)*

## Assumptions

- Each harness reads its user-level file when a session starts (their documentation, research R1). This
  is not verified against each harness here, because no harness runs in this container. The D4 demo is
  where it is observed.
- The agent's `$HOME` is `/home/agent`, writable by the agent, unless an operator mounts something else
  (FR-8 covers that).

---

## Slice 1 (natural) — added by modify cycle 3 (send `bridge/sends/04-rev13-20261008-161802.md`), declared

> Added by `/specswarm:modify 007` from the send above, at prompt revision 13. Nothing above this line changes
> meaning, apart from the annotated SC-1 notes (§ Slice 1 carried items). `prompt_revision`, `discovery_revision`
> and `source_prompt` are untouched. Revision 13 was already in `audited_against` (modify row 4), so this cycle
> appends nothing. It adds the criteria marked `_(slice 1)_`, which were in the prompt from revision 1 and out
> of scope until now.

**Intensity: natural.** The common failures are included: an unknown command with no known source, a
runtime that is absent, a cgroup file that cannot be read. Edge-case hardening is not.

### The command-not-found answer (criterion 4; send seams 2 and 3)

- **FR-14 · Where it is reached.** A bash `command_not_found_handle`, defined by 001's hook
  `/etc/timelike/shell-env.bash`, so it is reached exactly where that hook is:
  - `bash -c` (through `BASH_ENV`);
  - `bash -lc` (profile.d, then `BASH_ENV`);
  - interactive bash (the `/etc/bash.bashrc` line);
  - a bash script run by any of them (each bash reads `BASH_ENV`).

  **Not reached, and said:** `sh -c` (dash, which has no such hook) prints `sh: 1: NAME: not found`. A
  harness that `execve`s a missing binary directly gets `ENOENT` from the kernel, and the harness's own
  message. Both exit 127 as before. Nothing works only through a harness's hook (P7, T3). Each claimed
  style has its own e2e cell, and so does each unclaimed one, asserting what it gets (stack note 4).
- **FR-15 · What it prints.** On stderr, then exit 127. The handler never installs anything, never asks and
  never reads stdin (P2, P4).
  1. **First, bash's own line, byte for byte:** `bash: line N: NAME: command not found` from `bash -c`,
     `SCRIPT: line N: NAME: command not found` from a script, and `bash: NAME: command not found`
     interactively. The handler rebuilds it from `$0`, `BASH_LINENO[0]` and `$-`, so an agent, or a harness
     matching that text, sees exactly what it would see without timelike.
  2. **Then, only when the name is known, one line per answer,** each starting `timelike: `, in the data
     file's order:
     - a timelike equivalent: `timelike: instead: <command>  (<what it is>)`, with the command first;
     - an OS package: `timelike: NAME is in the Debian package PKG, which is not installed. The agent
       cannot install OS packages (no root): the operator adds PKG to the image.`;
     - a user-level install the agent can run itself: `timelike: install it yourself: <command>  (<note>)`.
       ~~**None ships until Item 21 is answered** (FR-18).~~ *(Revised, discovery revision 14: Item 21 is
       answered; `user` rows ship for Python and Node CLIs (FR-29).)*
  3. **An unknown name gets line 1 alone:** exactly the shell's usual line, with nothing invented.
- **FR-16 · The data.** `/etc/timelike/missing-commands.tsv`, shipped in the image: one answer per line,
  `name<TAB>kind<TAB>value<TAB>note`, with `kind` one of `instead`, `debian` or `user`, `-` for an empty note,
  and `#` comments. A name can have several lines (`tree`: `view DIR`, and the Debian package `tree`).
  `TIMELIKE_MISSING_COMMANDS` replaces the path for tests only, like the hook's other overrides.
  **How it grows:** one line per answer. Checks in the tests:
  - every `instead` names a command whose first word is an installed timelike tool;
  - no listed name is installed in the image (e2e), or its answer could never be reached.
- **FR-17 · Cost.** The handler uses bash builtins only (`read`, `printf`), so a typo costs no fork. Its cost
  per call is measured (plan § Measurements). It is defined once per bash start, like the hook's other parts.
  Defining a function forks nothing, which keeps the hook's rule of no fork at shell start.
- **FR-17a · A harness that parses JSON.** The hook is the shell's and not a timelike tool, so rule 14's
  JSON error shape does not apply. A harness sees exit 127 and the stderr lines above, as it would see
  bash's line alone.

### Unprivileged package installs (criterion 5; send seams 1, 4 and 5) — ~~HELD on FOR-MENTOR Item 21~~ *(Revised, discovery revision 14: ruled; built in cycle 4, FR-25 to FR-31)*

- **FR-18 · Not built until Item 21 is answered.** The image ships no agent-facing Python or Node (only
  timelike's own interpreter, run with `-I`, and `uv`). Every reading changes the image's contents or reads
  the criterion as conditional, so the send says to raise it first. The options and the facts measured with
  the pinned `uv` are in Item 21. The recommendation is (b): the configuration, not the runtimes. Whichever
  reading is chosen, these hold:
  - installs go through the standard commands (`pip install`, `npm install -g`), configured through the
    environment, never through a wrapper that shadows `pip` or `npm`, so feature 15 can sit in front of them;
  - package registries are reached under P4's standing grant;
  - "succeeded" means the package imports, or is on PATH, in a **new** shell, from the user location, with
    nothing under a root-owned path changed (P004); never the installer's exit code.

  *(Revised, discovery revision 14, modify cycle 4, declared: Item 21 is answered — Q1 option (a), Q2
  reading (ii), Q3 no `PIP_BREAK_SYSTEM_PACKAGES`. The three bullets above still hold, with one correction:
  the configuration is **scoped to each runtime** (its own `pip.conf`, its own `npmrc`), never the
  environment (Q3). What is built is FR-25 to FR-31.)*
- **FR-19 · Installs under `$HOME`, and recovery (seam 5), as built today.** User-level installs live under
  `~/.local`, and the image sets `WORKDIR /home/agent`:
  - with no repository in `~`, the workspace is `~` itself (005 FR-1). `snapshot` and `undo` refuse it
    (005 D-2: the home directory is refused), and `verify changed` needs a git repository, so neither covers
    installed packages there;
  - inside a repository below `~`, `~/.local` is outside the workspace, so neither covers them either;
  - so an install is undone by the installer's own uninstall (`pip uninstall`, `npm uninstall -g`). Nothing
    in this slice promises otherwise.

  The home is not a volume, so installs end with the container. 07 slice 1's state root is for timelike's
  state, not for packages. Neither the announcement nor the budget says anything about persistence beyond
  new shells.

  *(Confirmed, discovery revision 14, modify cycle 4: plan noted that excluding `~/.local` from the snapshot
  scope would fit T2's capped scope. **Chosen: no exclusion, because none is reachable.** A workspace that
  could contain `~/.local` is `~` itself or an ancestor of it, and 005 refuses both. A workspace below `~`
  never contains it. So no snapshot captures installed packages, and no contract changes. `verify changed`
  sees `~/.local` only in a git repository rooted at `~`, an agent's own unusual choice; it then lists
  installed files as untracked, as git would.)*

### The resource budget (criterion 6; send seam 6)

- **FR-20 · The command: `timelike budget`.** A subcommand of the environment's own command, as D-4 chose
  for `tools` and `announce`: no new name on PATH, nothing shadowed. It is announced by its own line in the
  announcement (FR-24). It follows the output contract (header, verdict, `--json`, exit 0 for a report,
  whatever it could read).
- **FR-21 · One reader, not three.** The cgroup readers move into `agentio`:
  - `cgroup_dir()`, `/proc/self/cgroup`'s `0::` path under `/sys/fs/cgroup`, with `TIMELIKE_CGROUP_ROOT`
    overriding it;
  - the integer-or-`max` file reader;
  - the CPU figure.

  `run` (003) imports them in place of its own, unchanged in behaviour (recorded as
  `changed_other_features`). 005's workspace finder (FR-1) moves into `agentio` too, so `budget` and
  `snapshot` name the same workspace (005 is recorded as changed as well).
- **FR-22 · The figures, from cgroup v2** (stack note 6; never `ps` RSS or `os.cpu_count()`):
  - **memory:** limit (`memory.max`), in use (`memory.current`), peak (`memory.peak`, where the kernel has it);
  - **CPU:** limit as CPUs (`cpu.max` quota ÷ period, two decimals), plus the job-count figure
    `TIMELIKE_CPUS` the hook computes. That is ⌈quota ÷ period⌉ capped by the affinity count, never below 1,
    computed by **the same rule in `agentio`**. A test feeds the same files to both and asserts they agree. The
    output also names the shell's `$TIMELIKE_CPUS`, when set, and whether it agrees;
  - **processes:** limit (`pids.max`), running (`pids.current`);
  - **disk:** free and total bytes (`statvfs`) on the **workspace** (005 FR-1: the nearest ancestor holding
    `.git`, else the current directory) and on the **scratch root** (`TIMELIKE_SCRATCH_ROOT`, default
    `/tmp/timelike`). When the scratch root does not exist yet, the figure is for its nearest existing
    ancestor. Both paths are named in the output, and so is the measured path when it differs.
- **FR-23 · Results that are not numbers.** `max` prints as **no limit**, never as a number. An unreadable
  file, a missing one (a cgroup v1 host, or a kernel without `memory.peak`) or an unparseable one is
  **unknown**, with the file and the reason named, never 0. Each figure carries `state` (`value`, `none` or
  `unknown`), `value`, `source` (the file or path read) and `reason`.

### The announcement (FR-2, extended)

- **FR-24** Two rule lines are added, inside the 60-line bound (28 lines at slice 0, 30 now):
  - `` `timelike budget`: this container's memory, CPU, process and disk limits, and what is in use. ``
  - "In bash, a command that is not installed says what to use instead, or who can install it." It says
    "in bash" because `sh -c` and direct execs do not get the answer (FR-14).

### Slice 1 success criteria (the send's text, copied exactly)

- **SC-5:** "Typing a command that is not installed exits 127 and prints the install command for the package
  that provides it or the equivalent timelike tool, when either is known". One e2e file in the image:
  - one cell per claimed style (`bash -c`, `bash -lc`, interactive bash, a script), each for a known name with
    an equivalent (`tree`), a known name with a package only (`jq`), and an unknown, guaranteed-absent name;
  - one cell each for `sh -c` and a direct exec, asserting exit 127 and the shell's or harness's own message,
    with no `timelike:` line;
  - one cell that every listed name is absent in the image;
  - the unknown cell compares the handler's stderr byte for byte with the same command run with the handler
    unset.
- **SC-6:** "A bare Python package install and a global Node package install each succeed as the agent's user
  without privilege and persist across new shells". ~~**HELD on Item 21 (FR-18).**~~ *(Revised, discovery
  revision 14: built in cycle 4; tested as FR-31 says.)*
- **SC-7:** "One command prints the agent's resource budget: memory limit and use, CPU limit, process limit,
  and free space on the workspace and scratch filesystems". Tested:
  - by units against cgroup files the test writes under `TIMELIKE_CGROUP_ROOT`, with values chosen apart from
    the reader, including `max`, an unreadable file and a missing file (P005);
  - by e2e against a throwaway container started with a known `--memory`, `--cpus` and `--pids-limit`, and
    against the running agent container; the CPU figure equals that shell's `$TIMELIKE_CPUS`.
- **SC-8 (Manual):** "DEMO: the Agent types a command that is not installed and is told the install command or
  the equivalent timelike tool" (D13). The mentor captures it after the lane. It stays `unconfirmed` until
  then.

### Slice 1 carried items (007's own; send § Carried)

- **SC-1's e2e cell names** take revision 13's text: the struck clause is gone, and the two workspace cells
  say "the workspace is left untouched". The assertions do not change.
- **SC-1's placement bound (Measurable outcomes, "not delayed by more than 1 second") is replaced, declared.**
  It failed in lane readme-b at 11225 ms under host I/O load and passed in readme-c, so host load decided it,
  not the feature. The criterion says "on container start". The cell now asserts the **ordering**:
  - every file is present and current when the container's command first runs (the entrypoint places them,
    then `exec`s the command);
  - none predates the container's start by more than the existing 1 s clock tolerance (placed on this
    start, not baked into the image).

  The placement time is still printed in the cell's output, as a measurement, not a bound.
- **`python3` in `standard-tools.json`:** it stays a curated entry (its REPL trap is real wherever a Python
  exists). It is `installed: false` in the image today, computed and not curated. Item 21 settles whether
  that changes. *(Revised, discovery revision 14: the image now ships `python3` and `node`, so both entries
  read `installed: true`, computed; their REPL risk and `instead` stay.)*

### Slice 1 decisions

**D-7 · The answer lives in the shell hook, reached by every bash style 001's hook reaches (seam 2).** A
wrapper around the harness, or a harness hook, would work in one harness only (P7). `sh -c` cannot be
reached without replacing `/bin/sh`, which changes every system script. So it is named, and tested, as not
reached.

**D-8 · The data is a tab-separated file, not `standard-tools.json` (seam 3).** The handler runs on every
typo, in bash, with no fork (FR-17), and bash cannot read JSON without a process. One file is read by the
handler and validated by the tests. Debian's `command-not-found` index is not used: it needs `apt-file` data
fetched from the network and an index rebuilt as root, which suits neither an agent without root nor an image
that does not change after build.

**D-9 · OS packages are named with who can install them (seam 3, P1).** The agent has no root (R7), so
`apt-get install X` is a command it cannot follow. The answer names the package and the operator, not a
command that fails.

**D-10 · `timelike budget`, a subcommand (seam 6).** It follows D-4: no new name on PATH. A new name such
as `budget` would also need conformance and its own announcement line, for no gain.

**D-11 · SC-6 is held, not narrowed (seam 1).** FOR-MENTOR Item 21 is raised. The parts of the cycle it does
not block (FR-14–FR-17, FR-20–FR-24) are built meanwhile. If it is still open when everything else is done,
the cycle report says SC-6 is not built, and `README.md` is left untouched, as the send's README block
instructs. *(Resolved, discovery revision 14 (plan `e800ef3`): Item 21 closed; SC-6 built in cycle 4.)*

---

## Slice 1, cycle 4 — the agent runtimes (discovery revision 14; send `bridge/sends/04-rev14-20261008-174220.md`), declared

> Added by `/specswarm:modify 007` from the send above. Revision 14 (plan `e800ef3`) changed prompt 04's Feature
> text ("work without privilege in user locations made the default, so the bare command needs no flag") and
> struck its PEP 668 constraint, replacing it. **No criterion changed.** The ruling is
> `../bridge/feedback/04-20261008-173021-agent-runtimes-for-package-installs.md` § Resolution (Q1–Q3). FR-13,
> FR-15, FR-18, FR-19, SC-6, the `python3` carried item and D-11 are corrected above by declared copy.

### The runtimes (FR-25 to FR-28)

- **FR-25 · Two runtimes for the agent, never for timelike's tools.**
  - **Agent Python:** uv-managed CPython at the pinned `PYTHON_VERSION` (the same 3.14.x as timelike's), in
    its **own prefix** `/opt/agent/python` (a link to the uv install directory), not `/opt/timelike/python`.
  - **Node:** the official `node-v<NODE_VERSION>-linux-x64.tar.gz`, the current Active LTS (24.x "Krypton" on
    2026-10-08; 26 is not LTS yet), unpacked to `/opt/agent/node`. `NODE_VERSION` and `NODE_SHA256` are pinned
    in `pins.env`. The build checks the tarball against `NODE_SHA256` with `sha256sum -c`, and a mismatch fails
    the build.
  - On the agent's `PATH`, as links in `/usr/local/bin`: `python3`, `python`, `pip`, `pip3` (to the agent
    prefix) and `node`, `npm`, `npx` (to Node's). `corepack` is not linked.
  - Root owns both prefixes: the agent cannot change them.
- **FR-26 · Python's user location is the default, by the interpreter's own configuration.**
  - The agent prefix ships **without** its `EXTERNALLY-MANAGED` marker. No external manager owns it (Q3).
  - Its own `pip.conf` (`/opt/agent/python/pip.conf`, pip's *site* configuration for that prefix) sets
    `[install]` `user = true`.
  - So a bare `pip install X` goes to `~/.local`, scripts to `~/.local/bin`. A venv the agent makes has its
    own prefix and does not read this file.
- **FR-27 · Node's global prefix is the agent's, by Node's own configuration.** `/opt/agent/node/etc/npmrc`
  (npm's global config file for that Node, which npm finds from the real path of `node`) sets
  `prefix=${HOME}/.local`. So `npm install -g X` goes to `~/.local/lib/node_modules`, binaries to
  `~/.local/bin`. This was measured on the host with the pinned tarball and a locally packed package.
- **FR-28 · `~/.local/bin` on `PATH`.**
  - In the image's `ENV` block, as the literal `/home/agent/.local/bin`, since the block takes no `$`.
  - In `/etc/profile.d/00-timelike-path.sh`, for login shells.
  - It goes after `/opt/timelike/bin`, so an install never shadows a timelike tool, and before `/usr/local/bin`,
    so a package the agent upgrades for itself (`pip install -U pip`) wins over the image's.
  - **Never `PIP_BREAK_SYSTEM_PACKAGES`**, anywhere. **No wrapper** around `pip` or `npm`: the links are to
    the runtimes' own executables (seam 4; feature 15 sits in front later).

### Isolation, the data, the bench and the scan (FR-29 to FR-30)

- **FR-29 · timelike's interpreter is untouched (stack note 3), and the data follows the image.**
  - User installs land in `~/.local/lib/python3.14/site-packages`. timelike's tools run their interpreter with
    `-I`, which never reads the user site, so an agent install cannot reach them.
  - Nothing installs into `/opt/timelike/python`'s site-packages: it stays root-owned, and the agent's pip is
    another interpreter.
  - `missing-commands.tsv` drops the rows for names the image now ships (`python3`, `python`, `pip`, `pip3`,
    `node`, `npm`, `npx`).
  - It gains `user` rows for common Python and Node CLIs (`pip install X`, `npm install -g X`), each a command
    the agent can run as itself. The unit test now requires every `user` value to start with `pip install `
    or `npm install -g `.
- **FR-30 · Bench parity and the scan.**
  - **The vanilla image** gains the same runtime binaries from the same pins (FR-13, revised), with stock
    behaviour. That changes **002's** `bench/vanilla/Dockerfile` and its header (recorded in
    `changed_other_features`). 002's spec is not modified here; 02 s1 records it. The bench catalog's
    "only what both images contain" rule is about the tasks' prerequisites, not the images' contents, so it
    stands as written. No package-install bench task is part of this slice.
  - **`make scan`** already scans the agent and vanilla images. Grype over Syft's SBOM sees the CPython and
    Node binaries, pip, and npm's bundled packages, under the same baseline rule. A new finding with no fix is
    a baseline change, raised for review after the lane, never exempted silently. `scan.sh`'s comments and the
    pip-audit "no interpreter" record are corrected: vanilla has an interpreter, but not timelike's.

### How SC-6 is tested (FR-31; cross-stack P004, P005; nodejs Q001)

- **FR-31** An e2e file in the image, as `agent`, one cell per style (`bash -c`, `bash -lc`):
  - **Python:** a wheel built by the test (stdlib `zipfile`, no network, a version unique per run), installed
    with a bare `pip install --no-index <wheel>`. In a **new** `docker exec` shell, from a directory that does
    not hold the source, it must import and its console script must run from `~/.local/bin`.
  - **Node:** a package packed by the test (`npm pack`, a unique version per run, nodejs Q001), installed with
    a bare `npm install -g --offline <tgz>`. In a new shell its binary must run.
  - **Only the agent's home changed:** no file outside `/home/agent` (with `/proc`, `/sys`, `/dev`, `/run` and
    `/tmp` excluded) is newer than a marker written before the installs.
  - **timelike's interpreter is unchanged:** a listing of `/opt/timelike/python`'s site-packages is equal
    before and after, and `/opt/timelike/python/bin/python3 -I` cannot import the installed module.
  - **No `PIP_BREAK_SYSTEM_PACKAGES`:** not in the environment of any style, not in `pip config list`, and
    not in any `pip.conf`, profile.d file, the hook or the `npmrc`.
  - **The runtimes:** `python3`, `pip`, `node` and `npm` resolve to the agent prefixes, never to
    `/opt/timelike`. The agent prefix has no `EXTERNALLY-MANAGED` marker.

  The vanilla cell (FR-13, revised) checks:
  - the same `python3 --version` and `node --version` as the agent image;
  - the marker present;
  - `npm prefix -g` is `/opt/agent/node`;
  - a bare `pip install` of the same kind of wheel is refused;
  - no announcement.

### Cycle 4 decisions

**D-12 · Links in `/usr/local/bin`, not the prefixes' `bin` on `PATH`.** Only the seven names the ruling lists
appear on `PATH`, so the prefixes' other executables (`idle3`, `pydoc3`, `python3-config`, `corepack`) don't.
npm finds its global config from Node's real path, which a link keeps (measured).

**D-13 · `${HOME}/.local` in the `npmrc`, the literal `/home/agent/.local/bin` in `ENV`.** npm expands
`${HOME}`, and pip's user base is `~/.local` too, so both follow an operator's different `HOME`. The `ENV`
block cannot expand variables (001's `test_env_layer.sh` forbids `$`). So `PATH` names the image's home, and
profile.d names the same literal path, to stay one value.

**D-14 · The checksum is checked by `sha256sum -c` in a `RUN`, not only `ADD --checksum`.** It works in any
builder, and the failure names the file. The tarball is fetched with `ADD`, because the slim image has no
`curl`, and `.tar.gz` because it has no `xz`.

**D-15 · The vanilla image gets its Python from a build stage.** It has no `uv` of its own and must not gain
one (stock behaviour). A builder stage from the same pinned base and `uv` image installs the interpreter, and
only `/opt/agent` is copied. The agent image does the same, so the two prefixes come from identical steps.

