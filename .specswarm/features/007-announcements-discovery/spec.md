---
parent_branch: master
feature_number: "007"
status: In Progress
created_at: 2026-10-04T19:47:32+00:00
source_prompt: plan/.discover/prompts/04-announcements-discovery.md
source_send: bridge/sends/04-rev1-20261004-183704.md
prompt_revision: 1
discovery_revision: 12
audited_against: [1]
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

- **FR-13** The **vanilla** bench image (`bench/vanilla/Dockerfile`) is not changed. A unit test checks
  it references none of this feature's paths, and an e2e cell checks the vanilla image's home holds no
  announcement. The timelike arm of the bench uses the agent image, so its agents now see the
  announcement. That is the *told by the environment* condition this feature creates.

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

Command-not-found guidance, unprivileged `pip`/`npm` installs, the resource-budget command (slice 1).
~~The workspace context file (D-1, raised).~~ *(Revised, revision 13: not out of scope but struck from the
criterion; D-1 resolved.)*

## Assumptions

- Each harness reads its user-level file when a session starts (their documentation, research R1). This
  is not verified against each harness here, because no harness runs in this container. The D4 demo is
  where it is observed.
- The agent's `$HOME` is `/home/agent`, writable by the agent, unless an operator mounts something else
  (FR-8 covers that).
