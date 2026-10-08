---
parent_branch: master
feature_number: "001"
status: In Progress
created_at: 2026-09-28T06:37:29+00:00
source_prompt: plan/.discover/prompts/01-agent-shell-baseline.md
source_send: bridge/sends/01-rev7-20260929-094055.md
prompt_revision: 2
discovery_revision: 3
audited_against: [2, 3, 4, 5, 6, 7, 8, 9, 10]
slice: 1
---

# Feature: Agent shell baseline & output contract (slices 0–1)

## Overview

The environment a coding agent lives in, and the contract every timelike tool obeys.

Coding agents work through a harness that starts shell commands with no person at the keyboard. In an
ordinary shell those commands stall on editors, pagers, credential prompts and terminal reads, or they
bury their result in colour codes and unbounded output. This feature provides an environment where any
command the agent runs behaves non-interactively, however the harness starts the shell. The agent runs
unprivileged, with no route to root and no way to alter what guards it.

It also defines one **output contract** that every timelike tool follows, in this feature and every
later one. Learning one tool teaches all of them. A conformance check makes the contract enforceable,
and every tool invocation is recorded to a per-session event log that later features read.

**This spec covers slices 0 and 1.**
- **Slice 0 (skeletal):** the thinnest end-to-end path, built from
  `bridge/sends/01-rev2-20260928-063549.md`, re-sent as `…-131708.md`, merged at `39d3b74`.
- **Slice 1 (natural):** added by `/specswarm:modify` from `bridge/sends/01-rev2-20260928-214635.md`.
  It brings SC-8 to SC-11 and FR-15 to FR-18, and the common failures beside each slice-0 criterion.

The full output contract is binding in every slice. Slice 0 builds the contract and its conformance
check, and slice 1 does not redefine them.

**Principles served:** P2 (every call concludes), P4 (reach only by grant), P7 (harness-agnostic),
P3 (found where agents look).

## User Scenarios

### Actors

- **Agent** (primary). Runs commands in the environment and reads tool output.
- **Harness** (autonomous intermediary). Starts each command non-interactively, as `bash -c` or
  `bash -lc` without a terminal, and captures the output.
- **Peer agents** (primary, concurrent). Other agents working in the same environment at the same time.
- **Operator**. Builds and starts the environment. Takes part in the manual demo.

### Scenario 1: Git never waits on a person (DEMO, D1)

1. The agent runs `git commit` without a message, `git rebase --continue`, `git log` and `git diff`
   through the harness.
2. Each returns within seconds: no editor opens, no pager holds the output, no prompt waits.
3. A commit without a message fails with an explanation instead of opening an editor. `git log` and
   `git diff` print directly.

### Scenario 2: Defaults hold however the shell is started

1. The harness runs the same command as `bash -c`, as `bash -lc`, and in an interactive shell.
2. In all three, the pager, editor, prompt and colour defaults are the same. None depends on a startup
   file that only some of those shells read.

### Scenario 3: Credentials fail fast

1. The agent runs a git operation against a remote that would ask for credentials.
2. It fails quickly with a non-zero exit and a message, instead of waiting for a username or password.
3. ~~A repository's own hooks do not run unless they have been explicitly enabled.~~ *(Struck at
   discovery revision 7, cycle 5: see Scenario 7.)*

### Scenario 7: A repository's own checks run, and conclude (cycle 5, discovery revision 7; T4)

1. The agent commits in a repository whose pre-commit hook rejects the change (for example, a husky
   hook, or one in `.git/hooks`).
2. The commit fails with the hook's own output, as it would without timelike.
3. In a repository whose hook never finishes, the commit fails within the time limit plus a few
   seconds. It fails with a verdict naming the hook, the limit and how to raise it. It never suggests
   skipping the hook: skipping stays the agent's own, visible choice.

### Scenario 4: The agent cannot escalate

1. The agent tries to run a command as root, change a firewall rule, or read a file belonging to the
   authority that guards its grants (Adele).
2. Each attempt is refused. Nothing the agent holds allows any of them.

### Scenario 5: Every tool speaks the same contract

1. A new timelike tool is placed on PATH.
2. The conformance check runs against every timelike tool on PATH and fails if any tool breaks the
   contract, naming the tool and the rule it broke.

### Scenario 6: Peer agents do not collide

1. Two agents run concurrently, each in its own session.
2. Each agent's output files and event-log entries land in its own scratch space. Neither appears in
   the other's.

### Edge cases

- A command started with no terminal attached must not try to open one.
- A git command that already has an explicit editor or pager argument keeps it. The environment
  changes defaults, not explicit choices.
- A failure to write a session event never changes the tool's own result or exit code.
- A timelike tool run with no session identity still works, and its event goes to a default session.
- Output that exceeds the cap says how much was left out and the exact command to see more.

## Functional Requirements

### Non-interactive environment

- **FR-1** Pager, editor, prompt and colour defaults MUST be in effect for non-interactive `bash -c`,
  login `bash -lc` and interactive shells alike. They MUST NOT depend only on startup files or hooks
  that some of those shells skip.
- **FR-2** `git log`, `git diff`, `git commit` without a message and `git rebase --continue` MUST each
  exit within 20 seconds without opening a pager or editor, under the harness's non-interactive
  invocation.
- **FR-3** A git operation that needs credentials MUST fail fast with a non-zero exit instead of
  prompting.
- **FR-4** ~~Repository hooks MUST NOT run unless explicitly enabled.~~ *(Superseded at discovery
  revision 7, cycle 5, corrected in place through `/specswarm:modify` as the send declares, not
  regenerated. The environment never silently removes a project's own checks (T4). See FR-19 and FR-20,
  and research R11.)*
- **FR-19** *(cycle 5)* The hooks a repository configures, from its `core.hooksPath` (any scope except
  the environment's own) or git's default hooks directory, MUST run under git commands, with git's
  arguments, stdin and environment. A commit that a pre-commit hook rejects MUST fail with the hook's
  output, as it would without timelike.
- **FR-20** *(cycle 5)* Every repository hook MUST run under a time limit: 60 s by default. It can be
  raised with `TIMELIKE_HOOK_TIMEOUT` (seconds) in the environment, or with `git config
  timelike.hookTimeout` in the repository. A hook past its limit MUST be stopped with its whole
  process group. The git command then MUST exit non-zero within the limit plus a few seconds, with a
  verdict naming the hook, the limit and how to raise it. The verdict MUST NOT suggest any way to skip
  the hook.

### Privilege boundary

- **FR-5** The agent's user MUST NOT be able to run any command as root, by any route.
- **FR-6** The agent's user MUST NOT be able to change firewall rules. This is verified by reading the
  controls themselves (capabilities, rule state), not by inferring from a connection attempt.
- **FR-7** The agent's user MUST NOT be able to read files owned by Adele.

### Output contract

- **FR-8** Every timelike tool MUST follow contract rules 1–16 below.
- **FR-9** A conformance check MUST run against every timelike tool on PATH. It MUST fail when any tool
  lacks any of the following, and name the tool and the rule broken:
  - `--help` within 40 lines
  - `--json`
  - `--agent-info`
  - the exit-code vocabulary
  - a self-labelling first line
  - one session event per invocation
- **FR-10** Every tool invocation MUST append one structured event to the session event log: tool,
  arguments, working directory, exit code, duration, session.
- **FR-11** A failure to write the event MUST NOT change the tool's result or exit code.

The contract (binding on every timelike tool, in every feature):

1. Structured (JSON) output when piped, terse text on a terminal. `--json` and `--text` override.
2. A hard default output cap. When output is capped, the last line states how much was omitted and
   the exact command to get more or to narrow. *(Clarified, revision 6: the omission line appears only
   when output was capped, so its absence means nothing was omitted. Uncapped text ends on its own
   last result line, and JSON carries `exit`.)*
3. Never truncate in the middle. The order is: verdict first, then the head, the first error(s), the
   tail, the exit code, and a path to the full artefact. *(Clarified, revision 6: this order is the
   shape of output a tool cuts, and it binds every tool that cuts. Output that is not cut is printed
   whole after the rule-12 header.)*
4. Never read the terminal, open `/dev/tty`, spawn a pager or editor, or prompt.
5. Exit codes: 0 success, 1 failure, 2 usage, 3 not found or unsure, 4 confirmation or grant
   required, 124 timeout. Zero search results exit 0 with a count of zero. *(Clarified, revision 9:
   these are a tool's own outcomes. A tool that runs a command the agent named passes that command's
   exit through, as the shell would have reported it (126, 127 and 128+n included), and uses 124 only
   when its own limit fired. The verdict and a JSON `cause` tell its own outcomes from the command's,
   and its `--agent-info` declares the pass-through. Annotated in place by cycle 6, declared; the
   contract was amended to match by feature 003 at `58b7d11`.)*
6. `--help` (at most 40 lines), `--json`, and `--agent-info` (a machine-readable manifest) on every
   tool.
7. Idempotent.
8. `--dry-run` for anything destructive.
9. Mutating without `--yes` exits 4 with a JSON envelope naming the plan and the confirm command.
   There is never an interactive fallback. *(Clarified, revision 10: exit 4 carries either this
   confirmation envelope or a grant envelope, told apart by `status`. A grant envelope names the grant,
   the exceeded limit and the operator's extend command, marked as the operator's, and states that
   nothing was performed. An operator's command never appears in `confirm`. A client whose requests
   Adele brokers is not `--yes`-confirmed: the grant is the confirmation, and rule 8 still applies.
   Annotated in place by cycle 7, declared; the contract was amended to match by feature 004 at
   `b7a6ea6`.)*
10. No daemons. State lives only under a scratch directory~~ and an optional git-excluded project cache~~
    *(struck, revision 11)* and a per-workspace state root outside the workspace, never inside the workspace or
    its `.git`. *(Revised, revision 11: the scratch directory is per session and disposable; the state root
    holds recovery state and caches, survives sessions and container recreation, and is bounded by size and
    age. Amended (struck clause), corrected in place by cycle 8, declared: the line before it named the
    project cache as allowed state. 001 builds only the scratch; no tool here writes a project cache, and the
    state root is not built yet (07 slice 1).)*
11. Deterministic, sorted output. No timestamps except behind `--verbose`.
12. The first line is a self-labelling header naming the tool, target and scope.
13. ANSI stripped. Long lines are cut at `COLUMNS` (default 200) with a marker and a byte count.
14. Structured errors on stderr: one JSON object with `--json`, otherwise
    `error: <what> (code N) — <remediation>`.
15. Redacted values appear as `[REDACTED:<type>]` and are never silently removed.
16. Every invocation appends one structured event (tool, arguments, cwd, exit, duration, session) to
    the session event log.

### Peer isolation

- **FR-12** Each concurrent agent session MUST have its own scratch space and its own session event
  log.
- **FR-13** One session's output files and event-log entries MUST NOT appear in another session's.

### Build identity

- **FR-14** The environment MUST carry the revision it was built from, readable both from the built
  artefact's metadata and from `timelike --agent-info`. An empty or missing revision is a failure
  (constitution H8).

### Slice 1: container-derived defaults (added by modify, send `…-214635`)

- **FR-15** Build parallelism defaults MUST be derived from the container's CPU limit rather than the
  host's CPU count, for make jobs, test-runner workers and compiler jobs. An explicit value already in
  the environment MUST win.
- **FR-16** Environment variables with secret-shaped names (matching key, token, secret or password
  patterns) MUST be absent from the agent's shells unless their name is explicitly allow-listed. A
  variable that only resembles such a name MUST NOT be removed.
- **FR-17** The timezone MUST default to UTC. Interactive language REPLs MUST default to their basic,
  scriptable prompt mode.
- **FR-18** FR-15 and FR-16 MUST hold under non-interactive `bash -c`, login `bash -lc` and interactive
  shells alike, as FR-1 requires of every default.

## Success Criteria

Acceptance criteria, cited by distinguishing text as the sends give them. SC-1 to SC-7 are slice 0;
SC-8 to SC-11 are slice 1. From slice 1 (natural intensity), each slice-0 criterion is also tested
against the common failure a real user meets, not only the happy path.

### Automated

- **SC-1** With the harness's non-interactive invocation, `git log`, `git diff`, `git commit` without
  a message, and `git rebase --continue` each exit within 20 seconds without opening a pager or
  editor. *(P2)*
- **SC-2** The Harness invokes a command through non-interactive `bash -c` or `bash -lc`, and the
  environment's pager, editor, prompt and colour defaults are all in effect. This is verified by one
  test per invocation style. *(P7)*
- **SC-3** A git operation that would need credentials fails fast with a non-zero exit instead of
  prompting~~, and repository hooks do not run unless explicitly enabled~~. *(P2; the hooks clause was
  struck at revision 7, cycle 5)*
- **SC-4** The agent's user cannot run any command as root, cannot change firewall rules, and cannot
  read files owned by Adele. *(P4)*
- **SC-5** A conformance check runs against every timelike tool on PATH. It fails when any tool lacks
  any of: `--help` within 40 lines, `--json`, `--agent-info`, the exit-code vocabulary, a
  self-labelling first line, or a session event per invocation. *(P3)*
- **SC-6** Two Peer agents running concurrently each write to their own scratch space, and neither's
  output files or event log entries appear in the other's. *(P2)*

- **SC-12** *(cycle 5, slice 0 criterion at revision 7)* The hooks a repository configures (its
  `core.hooksPath`, or `.git/hooks`) run under git commands, and a commit a pre-commit hook rejects
  fails with the hook's output, as it would without timelike. *(P1)*
- **SC-13** *(cycle 5, slice 0 criterion at revision 7)* A hook that runs past its time limit is killed,
  and the git command exits non-zero within the limit plus a few seconds, with a verdict naming the
  hook, the limit and how to raise it, and never suggesting a way to skip the hook. *(P2)*

- **SC-8** Build parallelism defaults (make jobs, test-runner workers, compiler jobs) are derived from
  the container's CPU limit rather than the host's CPU count. *(P2, slice 1)*
- **SC-9** Secret-shaped environment variables (names matching key, token, secret, password patterns)
  are absent from the agent's environment unless explicitly allow-listed. *(P4, slice 1)*
- **SC-10** The timezone defaults to UTC and interactive language REPLs default to their basic,
  scriptable prompt mode. *(P2, slice 1)*

### Manual

- **SC-7 (DEMO → D1)** The Agent runs `git commit`, `git rebase --continue` and `git log` in the
  container, and each returns within seconds instead of waiting on an editor, pager or prompt.
- **SC-11** A person reading the output contract can predict, for a tool they have not seen, what its
  first line, last line and exit codes will be. *(P3, slice 1)* It stays unconfirmed until a person
  has looked.

### Measurable outcomes

- Zero commands in the acceptance suite wait for input. Each of the listed git commands returns
  within 20 s, and in practice within seconds.
- 100% of timelike tools on PATH pass the conformance check. A deliberately broken tool makes the
  check fail, which shows the check can fail.
- 0 routes to root, firewall change or Adele-owned data from the agent's user.

## Key Entities

- **Agent environment.** The built image the agent runs in. It carries its build revision.
- **Agent user.** The unprivileged identity the agent runs as.
- **Timelike tool.** Any command timelike ships on PATH. Each is bound by the output contract.
- **Output contract.** Rules 1–16. The shared behaviour every tool implements.
- **Conformance check.** Verifies every timelike tool against the contract, and fails naming the tool
  and the rule.
- **Session.** One agent's working context, identified by a session id. It owns a scratch space and an
  event log.
- **Session event.** One record per tool invocation: tool, arguments, cwd, exit, duration, session.
- **Adele-owned data.** Files that belong to the grant authority. Adele itself is feature 12. Here only
  its ownership boundary is represented, so that the agent's lack of access can be verified.

## Out of Scope

- ~~Slice 1 criteria~~: now in scope as SC-8 to SC-11, added by modify from `…-214635`.
- **Plain `sh -c` and direct execs of non-shell binaries** for FR-15 and FR-16. They read no startup
  file, and the harness invocation is `bash -c` / `bash -lc` (Assumption 1). FR-17 is static and
  reaches them.
- **REPLs not present in the image.** FR-17 is claimed for Python, the only language interpreter
  shipped.
- **Adele itself.** Grants, egress policy, the Docker filter (feature 12). This feature only proves the
  agent cannot reach Adele's side.
- Any agent-facing tool beyond what slice 0 needs to exercise the contract: the environment's
  information tool, and the conformance check itself.

## Related work in the same cycle (governance, not acceptance criteria)

The send carries the project's own **supply-chain scan gate**:
- scan the agent image and its dependencies
- block on a High or Critical vulnerability that has a fix
- block on a committed secret

It is required by discovery revision 3 and constitution H9, and it takes effect at this feature's first
merge. It is governance and is deliberately **not** a success criterion here. It is recorded in the
cycle report.

## Assumptions

1. **"The harness's non-interactive invocation"** means a command started as `bash -c` or `bash -lc`
   with no terminal attached, as a harness does through a container exec without a TTY. Tests start
   commands exactly this way, from **outside** the environment (lore cross-stack P005). A test must
   not configure the shell it is testing.
2. **Adele-owned files in slice 0:** Adele does not exist yet. The environment reserves Adele's
   identity and its data location, and holds a fixture file there with owner-only permissions. SC-4
   shows the agent's user cannot read it. Feature 12 replaces the fixture with Adele's real data.
3. **Firewall** means the environment's packet-filtering rules. "Cannot change" is shown by the agent's
   user holding no network-administration capability, and by a rule-change attempt being refused,
   read directly (lore cross-stack P001).
4. **Peer isolation is separation, not security.** Peers may run as the same user. Each session is
   identified by a session id, and its scratch space and event log are keyed by that id and created
   owner-only. The criterion is that output lands in the right place and not in the other session's.
   Protection between mutually hostile peers is not claimed.
5. **Session identity:** a tool run with no session id uses a default session. It never fails for
   lack of one.
6. **Tools in slice 0:**
   - `timelike` (reports environment info, including the build revision via `--agent-info`)
   - the conformance check, which is itself a timelike tool and bound by the contract

   A deliberately non-conforming fixture tool, kept off the shipped PATH, proves the check can fail.
7. **Output cap default** is a documented constant (several KB), overridable per call. Its exact value
   is a planning decision.
8. **The build host** needs a container runtime (the send's external prerequisite). Nothing is
   installed on the host beyond that.
7. **Slice 1, allow-list:** the operator names allowed secret-shaped variables in `TIMELIKE_ENV_ALLOW`
   (exact names, separated by commas or whitespace), through compose or `docker exec -e`. Stripping
   governs what the agent's shells hold. It cannot remove what the operator gave the container itself
   (e.g. PID 1's environment), and the operator should not pass secrets to the agent container at all
   (P4).
8. **Slice 1, CPU limit** means cgroup v2 `cpu.max` (the quota divided by the period, rounded up),
   capped by the process's CPU affinity. Without a quota, the affinity count applies.
