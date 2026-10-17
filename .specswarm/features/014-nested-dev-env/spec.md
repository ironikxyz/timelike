---
parent_branch: master
feature_number: "014"
status: In Progress
created_at: 2026-10-17T01:36:45+00:00
source_prompt: plan/.discover/prompts/13-nested-dev-env.md
source_send: bridge/sends/13-rev8-20261017-012727.md
prompt_revision: 8
discovery_revision: 16
audited_against: [8, 17]
slice: 0
---

# Feature: Nested dev environments (prompt 13, slice 0: skeletal)

## Overview

The agent brings up a project's own development environment, a compose file in slice 0, from inside its container.
It runs its tests against the environment's services and tears it down. All of this happens without the operator
starting anything (P1).

The agent never holds a daemon socket. **Adele** reaches the local Docker daemon under a grant the operator wrote,
and she refuses every container setting that escapes a container, with exit 2 and rule 14's error naming the
setting and stating that no grant allows it (P4; prompt revision 17). What Adele
checks is what would be run: the project after interpolation, `extends`, profiles and override files, never the
text the agent wrote (cross-stack P002, P004).

The operator's two decisions for this feature are fixed by the send:
- **The daemon is reached through the host's socket, mounted into Adele's container only.**
- **The workspace is a directory on the host, one per launch,** mounted into the agent at the same absolute path
  (the same-absolute-path rule; lore docker-compose P001 item 1).

Up is idempotent, and down removes everything the environment created (P5). Bring-up always concludes with a
verdict (P2, feature 003).

**Out of scope (later slices):** devcontainers, session and grant labels with a collect command (slice 1), and
volume snapshots (slice 2).

**Seams, decided.** Five design points touch compose, other features' contracts, the constitution or the socket. They
were raised in FOR-MENTOR **Item 27** and answered in `../bridge/feedback/13-20261017-034920-item-27-seams-answered.md` (2026-10-17T03:49:20Z). Each appears below as a decided
decision citing that answer. One narrowing found while planning (D-7, builds) is raised as FOR-MENTOR Item 28 and
does not block a criterion.

## User Scenarios

### Scenario 1: bring up, use, tear down (Agent) — D9

The agent is in a project with a `compose.yaml` and runs `adele env up` from its workspace. The command:
1. resolves and checks the project;
2. brings its services up;
3. waits until each is ready;
4. prints a verdict listing each service with an address the agent's container can reach.

The agent then runs its tests against those addresses, and `adele env down` removes everything the environment
created. The verdict says that this was read back from the daemon.

### Scenario 2: a dangerous setting (Agent, Hostile content)

A project, or text the agent was given, asks for a privileged container, host networking, the host's PID or IPC
namespace, an added capability, a device, or a mount from outside the workspace (the socket included). Adele
refuses before anything is created. The command exits 2 with rule 14's error naming the service and the setting,
stating that no grant allows it and how to change the request, with no operator's command. Nothing is created on the
daemon.

### Scenario 3: up twice, then down (Agent)

A second `up` of a live, unchanged project creates nothing and says so. `down` removes every container, network and
volume the environment created, and the daemon no longer has any of them.

### Scenario 4: a service never becomes ready (Agent)

Bring-up ends at its bound with exit 124. The verdict lists each service's state and names the command that removes
the environment.

### Scenario 5: the operator's git (Operator)

The agent writes a `pre-commit` hook and a `core.hooksPath` or `core.fsmonitor` setting in its workspace. The
operator's own git on the host, in their own checkout, runs none of them, unless the operator lifted this at launch.
The launch configuration shows which of the two it is.

### Scenario 6: beyond the grant (Agent, then Operator)

A bring-up past the grant's `instances` is refused with 12's grant envelope (exit 4), naming the grant, the limit
and the operator's extend command.

## Functional Requirements

### The command (agent side)

- **FR-1** The agent brings up, inspects and tears down a project's compose environment with one tool, announced
  like every timelike tool (feature 04): `adele env up|status|down` (D-3). It follows 001's output
  contract and 003's concluding run.
- **FR-2** `up` names the project from its workspace directory, or from `--project`. The project name Adele gives the
  environment is unique per workspace project, so two projects, or two cells, never share one.
- **FR-3** `up` returns only once every service is ready, or the bound is reached (FR-12). Its verdict lists each
  service, its state, and each address reachable **from the agent's container** (cross-stack P001).
- **FR-4** `down` returns only once the daemon no longer has anything the environment created, read back (P004). Its
  verdict lists what was removed.
- **FR-5** A repeat `up` of a live, unchanged environment creates nothing, records nothing new, and says so.

### Adele's check (the daemon side)

- **FR-6** Adele alone reaches the daemon. The agent has no socket, no Docker group and no Docker endpoint
  (constitution H1). Adele's container gets the socket's group from a compose variable, never a literal.
- **FR-7** Adele checks the project's **resolved** model, after interpolation, `extends`, `include`, profiles and
  override files, and runs exactly what she checked. Which process resolves which path is stated in the plan
  (P002). Resolution runs in a throwaway sandbox that can read only the workspace (D-1).
- **FR-8** Adele refuses, with exit 2 and rule 14's structured error naming the service and the setting, and before
  anything is created:
  - a privileged container, or host networking;
  - the host's PID, IPC, UTS, user or cgroup namespace;
  - any added capability, and any device;
  - a security option that unconfines;
  - a mount or a volume whose source is outside the workspace, including the Docker socket and a volume's driver
    options that bind a host path;
  - a file-backed secret, config or env file from outside the workspace;
  - any `build:` in slice 0 (D-7).

  The full list is in Item 27 Q1, accepted as complete for slice 0. **A setting refusal is exit 2, with no envelope on
  stdout** (prompt revision 17): in text mode rule 14's line,
  `error: <setting> is not allowed (code 2) — no grant allows it; <how to change the request>`; with `--json` one
  JSON object on stderr naming the setting. Its remediation says how to change the request, never an operator's
  command. It is Adele's refusal and a `refused` ledger row like the others, and 12's `status` shows it with
  "operator's command: none".
- **FR-9** Adele creates nothing that lacks timelike's labels, and lists, inspects, stops or removes nothing that
  lacks them. This is the host's standing rule: timelike creates and removes only its own containers and images.
- **FR-10** Every `up` that creates an environment is a `performed` ledger row, and every refused `up` is a
  `refused` row (12's ledger). `down` records the environment's ending. Adele's verdicts on her own policy name her
  stamped revision (P003).

### Readiness

- **FR-11** A service is ready when:
  - it has a healthcheck, and the daemon reports it healthy;
  - it has none, and it is running and its exposed ports accept a connection from the agent's container;
  - it is a one-shot service, and it exited 0.

  The definition is D-3.
- **FR-12** Bring-up has a bound, a default of 120 s with an at-most value, both printed. Past it, the command exits
  124. The verdict lists each service's state, and the environment stays until `down` (D-3; at most 600 s).

### The workspace and the operator's git

- **FR-13** The launch mounts a host directory, one per launch under the workspace parent the operator set, into the
  agent at the same absolute path, so bind-mount sources resolve on the host to what the agent sees.
- **FR-14** Nothing the agent writes reaches the git state the operator's host git executes in their checkout
  (`.git/hooks/`, executing `.git/config` keys), unless the operator lifted it at launch. The launch configuration
  shows whether it was lifted. Decided: a private clone the operator fetches from, with the lift switch
  `TIMELIKE_HOST_GIT` (D-2). Tested with a real git on the host side, never by reading the agent's config
  back.

### The grant

- **FR-15** A new capability, `docker.compose`, takes 12's five keys (D-4):
  - `instances` is the number of environments live at once;
  - `ttl` is an environment's longest lifetime;
  - `ports` limits host-published ports;
  - `budget` is required, and slice 0 quotes 0.00.

## Success Criteria

Prompt 13's slice-0 criteria, verbatim (each gets one test named after its distinguishing text):

1. Bringing up a fixture project's compose file from inside the agent container starts its services and returns once
   they are ready, with a verdict listing each service and its address.
2. The Infra provider (the local Docker daemon) runs the nested environment's containers with the agent's workspace
   mounted at the same absolute path.
3. ~~A request for a privileged container, host networking or process namespace, added capabilities, or a mount
   outside the workspace is refused by Adele with exit 4 naming the setting.~~ *(Struck at prompt revision 17.)*
   A request for a privileged container, host networking or process namespace, added capabilities, or a mount
   outside the workspace is refused by Adele with exit 2 and rule 14's structured error, naming the setting and
   stating that no grant allows it, without an operator's command; nothing is created. *(Added revision 17.)*
4. A pre-commit hook and a `core.hooksPath` or `core.fsmonitor` setting written by the Agent in its workspace do not
   run when the Operator runs git in their own checkout on the host, unless the Operator lifted this at launch, and
   the launch configuration shows whether it was lifted.
5. Bringing the environment up twice is a no-op the second time, and tearing it down removes every container,
   network and volume it created.
6. DEMO (D9, Manual): the Agent brings up a compose test environment from inside its container, runs tests against
   it, and tears it down.

**Measures:**
- Every addressed service is reachable from the agent's container when `up` returns 0.
- After `down`, the daemon holds 0 objects labelled with the environment's project.
- Each refused setting creates 0 objects.
- The operator-side git runs 0 agent-written hooks or config commands while enforced.

## Key Entities

- **Environment:** a project brought up by Adele. It has a name unique per workspace project, its services, the
  addresses the agent can reach, a ledger row, an expiry, and labels.
- **Workspace:** the per-launch host directory, mounted into the agent, and read-only into Adele's resolver, at the
  same absolute path.
- **Resolved model:** the compose project after resolution. It is the only thing Adele checks and the only thing
  she runs.
- **Grant capability `docker.compose`:** the limits an environment is checked against.
- **Launch boundary setting:** whether the host-git boundary is enforced or lifted, shown on the agent's container.

## Decisions (decided: `../bridge/feedback/13-20261017-034920-item-27-seams-answered.md`)

- **D-1 (Q1)** The Compose CLI in Adele's image, from the pinned `DOCKER_CLI_IMAGE`. Resolution runs in a throwaway
  sandbox, with only the workspace read-only, no network, no socket, no secret and an empty environment. `up` runs
  from the checked bytes. Adele never pulls (the operator's decision); a missing image names the operator's
  `docker pull`. Its exit code waits on FOR-MENTOR Item 29: no field of the grant envelope but `extend_by` is true of
  it (the re-send's test).
- **D-2 (Q2)** A private clone the operator fetches from, with `TIMELIKE_HOST_GIT=enforced|lifted` at launch, shown as
  a container label, an agent environment value and a verdict line.
- **D-3 (Q3)** Readiness as FR-11 and FR-12. The shared network is `timelike-nested`, internal, and every nested
  service joins it with the alias `<service>.<project>`.
- **D-4 (Q4)** `docker.compose` with 12's five keys. 12's reaper reaps an expired environment through a second
  provider; collection by ended session waits for slice 1.
- **D-5 (Q5)** Per-cell project names. The fixture project uses images the lane already has. `lane.conf` classes
  are given per file in the plan.
- **D-6 (Q6)** The workspace parent is 2001:2001, mode 2775, created by the operator (read back 2026-10-17T03:53:19Z).
  The agent (uid 1000) writes through `group_add` of the parent's group.
- **D-7 (plan, FOR-MENTOR Item 28)** `build:` is refused in slice 0, as a forbidden setting (exit 2, naming `build`). Compose builds on the
  client side, so a build would run in Adele's process, which can read her credential: a Dockerfile or build secret
  that is a symlink would be read by her. No slice-0 criterion needs a build; the fixture uses images the lane has.

## Assumptions

- The socket's owner, group and mode are as the mentor read them. Nothing in this project verifies that they stay so
  (the send's external prerequisites).
- The images the fixture project uses are already on the daemon; slice 0 pulls nothing (D-1).
- A project's `${VAR}` resolves from the workspace's `.env` only, never the agent's environment; an unset variable is
  named in the verdict (D-1).
- The agent's existing egress through compose's default network is unchanged until 12 slice 2. The new network
  routes nowhere (D-3).
- This session has no Docker. Every e2e cell is first run in the mentor's lane.
