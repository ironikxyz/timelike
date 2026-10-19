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
slice: 2
---

# Feature: Nested dev environments (prompt 13, slices 0–2: skeletal, natural, then hardened)

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

**Slice 1 (natural; send `bridge/sends/13-rev17-20261018-120700.md`)** adds:
- the project's own devcontainer, through slice 0's checked path;
- builds, brokered the way the operator decided (`../bridge/feedback/13-20261018-120700-item-28-builds-and-session-end.md`);
- a command run inside an environment (`adele env exec`);
- session and grant labels on everything an environment creates;
- an explicit session end (`adele session end`), and collection of the environments whose session has ended;
- the one-shot readiness correction (the operator's decision C at slice 0's sign-off).

Natural intensity means the common failures too, each with a verdict naming its cause (§ Scenarios 9–12).

**Slice 2 (hardened; send `bridge/sends/13-rev17-20261019-034239.md`)** adds:
- snapshots of an environment's named volumes, and their restore, the way the operator decided (D-15, D-16);
- the two D22 observations the operator carried here (D-20).

Hardened intensity means edge cases, scale and recovery. Here that is three promises: a snapshot is never silently
partial, a paused service is never left paused, and nothing a snapshot creates outlives its environment
(§ Scenarios 13–15). This is prompt 13's last slice.

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

### Scenario 7: a devcontainer, then a command in it (Agent) — D22 (slice 1)

The agent is in a project with a `.devcontainer/devcontainer.json` and runs `adele env up`. Adele parses it in the
sandbox, translates it into a compose model, checks that model exactly as she checks a compose project, builds its
image if it has one, and brings it up with the workspace at the same absolute path. The lifecycle commands run inside
the container, each named in the verdict. The agent then runs `adele env exec -- CMD`. The command runs in the
devcontainer as its `remoteUser`, its output is bounded, and its exit status is passed through.

### Scenario 8: a build (Agent) (slice 1)

A service has a `build:`. The sandbox archives its context (links as links), resolves its Dockerfile and reports each
stage's base image. Adele streams the archive to the daemon's build API without opening it. Every base image must
already be on the daemon. The image is labelled and tagged under the environment, and `down` removes it. A second
`up` of the unchanged project builds nothing, and a changed Dockerfile builds again.

### Scenario 9: the common failures of a devcontainer or a build (Agent) (slice 1)

- A `devcontainer.json` that does not parse: exit 2, with the line at fault.
- A setting no grant allows (`initializeCommand`, a `runArgs` entry with no checked mapping, `privileged`, `capAdd`,
  `securityOpt`, `features`, build secrets, SSH forwarding, a non-default build network, entitlements, an additional
  context outside the workspace): exit 2 and rule 14's error, naming it.
- A base image not on the daemon: exit 3, naming the operator's `docker pull`.
- A build step that fails: exit 1, naming the step, with its last lines. A build past its bound: exit 124, naming
  the step.
- A lifecycle command that fails: exit 1, naming the command. The environment stays up, and the verdict gives
  `down`.

### Scenario 10: a command in an environment (Agent) (slice 1)

`adele env exec [NAME] [--service S] -- CMD` runs CMD in a running container of a live environment, never privileged.
The output is bounded, the exit status is passed through, and the call is a ledger row. Past its bound it exits 124.
An environment or service that does not exist exits 3.

### Scenario 11: ending a session, and collection (Agent, Adele) (slice 1)

A session has ended when the agent container that made the request no longer exists, or when it was ended with
`adele session end`. `adele env collect` runs a collection pass now, and Adele's reaper runs the same pass on its
interval. Each environment of an ended session is removed, read back from the daemon, and recorded with its cause.
`collect` with nothing to collect says "0 collected" and exits 0. A second `session end` says the session was already
ended, and exits 0.

### Scenario 12: a one-shot is never ready while it runs (Agent) (slice 1; decision C)

A service with no healthcheck and no port gives no readiness signal. `up` reports it as running with no readiness
check, never "ready". If it exits while `up` waits, its exit decides: 0 is completed, and non-zero fails `up` with
exit 1, naming the service and its last lines. A service another depends on with `condition:
service_completed_successfully` is a one-shot for certain, and `up` waits for its exit.

### Scenario 13: snapshot, corrupt, restore (Agent) — D31 (slice 2)

The agent snapshots its environment's database volume with `adele env snapshot db-data`. Adele pauses the services
that mount it, copies it, unpauses them, and answers with the snapshot's id, its size, the services paused and for
how long. The agent then corrupts the data, and restores it with `adele env restore SNAPSHOT --yes`: Adele checks the
snapshot is whole, stops the services that mount the volume, replaces its contents, starts them again, and the
answer is the readiness verdict `up` gives. The data is the snapshotted data, read back by its digest.

### Scenario 14: the failures a snapshot or a restore can meet (Agent) (slice 2)

Each concludes with a verdict naming its cause, and nothing is left half-done:
- **over the grant's snapshot cap:** exit 4 with the grant envelope, and nothing is written;
- **the store fills, or the copy helper fails, partway:** exit 1 naming the cause; the partial snapshot is removed
  and read back gone; the paused services are unpaused and read back running;
- **a snapshot whose content no longer matches its record:** exit 1 before anything is stopped;
- **a service that does not come back ready after a restore:** exit 1 with the readiness verdict; the restored data
  stays restored, and the verdict gives `adele env status` and `down`;
- **an unknown environment, volume or snapshot:** exit 3, naming what does exist (a bind mount, or a volume of
  another environment, is "no such volume in this environment");
- **restore without `--yes`:** exit 4 `confirmation_required`, naming what will be replaced and which services will
  be stopped; nothing is stopped. `--dry-run` shows the same and changes nothing.

### Scenario 15: nothing is left behind (Adele) (slice 2)

If Adele or her helper dies while a service is paused, Adele's next start and her reaper's next pass find what she
paused and unpause it, with a ledger row naming the cause. An environment taken down or collected (an ended session,
a gone requester, a ttl) takes its snapshots with it. A snapshot volume whose environment is gone, or that never got a
record because the copy was cut short, is removed as an orphan, with a ledger row. The lane's start removes leftover
snapshot volumes, by timelike's labels only.

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

  The definition is D-3. **Corrected in slice 1 (decision C, the operator, slice 0's sign-off):** a service with no
  healthcheck and no port is never "ready" while it runs. `up` reports it as running with no readiness check. If it
  exits while `up` waits, 0 is completed and non-zero fails `up` with exit 1, naming the service and its last lines.
  A service another service depends on with `condition: service_completed_successfully` is a one-shot for certain:
  `up` waits for its exit (D-13).
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

### Slice 1: devcontainers (D-9)

- **FR-16** `adele env up` brings up a project's devcontainer when the project has `.devcontainer/devcontainer.json`
  or `.devcontainer.json` and no compose file was named. The file is parsed **in the sandbox** as JSONC (comments,
  trailing commas). A file that does not parse is exit 2, naming the line at fault.
- **FR-17** The sandbox translates it into a compose model, and Adele checks and brings up that model exactly as a
  compose project, so every slice-0 refusal applies identically. Supported: `image`; `build` (`dockerfile`,
  `context`, `args`, `target`); `dockerComposeFile` with `service` and `runServices`; `containerEnv`, `remoteEnv`
  (for exec), `containerUser` and `remoteUser`; `workspaceFolder`, and `workspaceMount`, which must keep the
  workspace at the same absolute path; `mounts`, checked like volumes; `forwardPorts`, as addresses on
  `timelike-nested` (nothing is published on the host); `overrideCommand`, which keeps the container alive by
  default; and the lifecycle commands.
- **FR-18** Refused with exit 2 and rule 14's error: `initializeCommand` (it runs on the host); `runArgs` that do not
  map to a checked setting, the setting named; `privileged`, `capAdd`, `securityOpt` and the rest of slice 0's list;
  `features`, which slice 1 does not broker; `appPort`, which publishes on the host.
- **FR-19** The lifecycle commands (`onCreateCommand`, `updateContentCommand`, `postCreateCommand` on creation;
  `postStartCommand` on every start) run inside the container as its `remoteUser`, each bounded and named in the
  verdict. One that fails is exit 1, naming the command; the environment stays up, and the verdict gives `down`.
  Past its bound it is exit 124, naming it.

### Slice 1: builds (D-8, the operator's decision 1)

- **FR-20** A service's `build:` is built by the daemon from a context archive the sandbox makes. The sandbox has the
  workspace read-only, no socket, no network, no secret and none of the agent's environment. It archives the context
  with symlinks as links, never followed, honours `.dockerignore`, resolves the Dockerfile (one outside the workspace
  is refused) and reports each stage's base image. Adele streams the archive to the build API without opening or
  parsing it. Which process resolves each path is stated in the plan (cross-stack P002).
- **FR-21** **A build pulls nothing.** Every base image must be on the daemon before the build starts: a missing one
  is exit 3, naming the operator's `docker pull`. The plan says how the builder is kept from pulling (R15).
- **FR-22** Refused with exit 2 and rule 14's error, before any build: build secrets, SSH forwarding, a build network
  other than the default, entitlements, privileged builds, and additional contexts. A Dockerfile `RUN` asking for a
  secret or SSH mount, another network, or the insecure security mode is refused the same way.
- **FR-23** A built image is labelled with the environment, session and grant, and tagged under the environment's
  name. `down` and collection remove it, read back. An unchanged project builds nothing again; a changed context or
  Dockerfile builds again (D-12, cross-stack P003).
- **FR-24** A build has a bound. Past it, it is exit 124, naming the step it was in. A failed step is exit 1, naming
  the step, with the build's last lines.

### Slice 1: exec

- **FR-25** `adele env exec [NAME] [--service S] -- CMD …` runs CMD in a running container of a live environment, as
  its `remoteUser` (devcontainer) or its image's user (compose), never privileged. The output is bounded per 001's
  contract, and the exit status is passed through. Past its bound (feature 03's default) it is exit 124. Each exec is
  a `performed` ledger row with no undo. An environment or service that does not exist is exit 3.

### Slice 1: labels, session end and collection (D-10, D-11; the operator's decision 2)

- **FR-26** Everything an environment creates carries timelike's session and grant labels beside its environment
  label: containers, networks, volumes and built images.
- **FR-27** Adele records the requesting agent container when an environment comes up. She reads it from the daemon
  (the peer's address on `adele-request`, matched to a timelike-labelled container), never from what the client says.
- **FR-28** A session has ended when (a) the agent container that made the request no longer exists, or (b) it was
  ended with `adele session end`. `session end` ends the caller's own session with a ledger row; a second one says it
  was already ended and exits 0.
- **FR-29** A collection pass removes every environment whose session has ended, read back from the daemon, and
  records each removal with its cause ("container gone" or "ended at T"). `adele env collect` runs one now, and
  Adele's reaper runs the same pass on its interval. Nothing to collect is exit 0, "0 collected". A grant's ttl still
  reaps whatever outlives it.
- **FR-30** The exit codes stay slice 0's: 2, a setting no grant allows (or a devcontainer that does not parse); 3, no
  grant, environment or service by that name, or an image or base image not on the daemon; 4, beyond a grant's
  limits, with the envelope; 1, the capability failed (a build step, a lifecycle command, a one-shot); 124, a bound.

### Slice 2: volume snapshots and restore (D-15–D-20)

- **FR-31** `adele env snapshot [NAME] VOLUME [--note TEXT]` snapshots one named volume of a running environment and
  prints the snapshot's id, its size, the services paused and the time taken. `adele env snapshots [NAME]` lists them
  (id, volume, size, time, note) with the cap used and left. `adele env restore [NAME] SNAPSHOT` restores one.
  `adele env snapshot-rm [NAME] SNAPSHOT` removes one, freeing cap space.
- **FR-32** Only named volumes the environment created can be snapshotted. A bind mount, a volume the environment did
  not create, or another environment's volume is exit 3, "no such volume in this environment", naming the
  environment's own volumes. Restore checks that the snapshot was taken from this volume of this environment.
- **FR-33** A snapshot is held in a volume on the daemon that Adele creates, labelled with the environment, session,
  grant and requester. Nothing about it lives in the workspace, on a host path, or past its environment.
- **FR-34** The grant caps the bytes of snapshots an environment may hold (the grant file's `snapshots`, default
  **1 GiB** when the grant does not set it). A snapshot that would pass the cap is refused before anything is written:
  exit 4 with the grant envelope, naming the volume, its size, the cap, and the operator's command to raise it.
- **FR-35** A volume in use is snapshotted with its users paused: Adele pauses the running services that mount it,
  copies it, and unpauses them, read back running. The copy is one moment in time, the state a power cut would leave.
  The verdict says which services were paused and for how long.
- **FR-36** The copy runs in a throwaway helper container from Adele's own image: no network, no socket, no secret,
  the source mounted read-only, and only the capabilities keeping ownership needs. Owners, groups, modes, times and
  symbolic links are kept, and links are never followed. Adele never opens volume contents.
- **FR-37** A snapshot records its content digest, byte count and file count when it is taken, and "taken" is read
  back: the copy's digest equals the source's. Restore checks the snapshot's digest against that record before it
  stops anything; a mismatch is exit 1, and nothing is stopped. "Restored" is read back: the volume's digest after the
  restore equals the snapshot's.
- **FR-38** Restore is destructive, so it uses feature 01's confirm protocol: without `--yes` it exits 4
  `confirmation_required`, naming what will be replaced and which services will be stopped, and `--dry-run` shows the
  same and changes nothing. With `--yes` it stops the services that mount the volume, replaces its contents, starts
  them again, and waits for readiness under slice 0's rules and decision C. Its verdict is `up`'s readiness verdict.
- **FR-39** A snapshot that cannot be finished (the store full, the helper failed or killed) is exit 1 naming the
  cause. The partial snapshot is removed and read back gone, and the paused services are unpaused, read back running.
- **FR-40** A paused service is never left paused. Adele records what she pauses before she pauses it; her next start
  and her reaper's pass unpause whatever a record says is still paused, with a ledger row naming the cause. The same
  holds for services a restore stopped.
- **FR-41** `down`, collection and the reaper remove an environment's snapshots with the rest of it, read back, and
  count them in the verdict. A snapshot volume whose environment is gone, or that has no record, is removed as an
  orphan with a ledger row.
- **FR-42** The ledger: a snapshot is a performed row whose undo is its removal; a restore is a performed row naming
  the snapshot, the services stopped and the readiness Adele read back; a refusal (the cap, an unknown volume) is a
  refused row.
- **FR-43** The exit codes stay slice 0's: 2, a setting no grant allows; 3, no such environment, volume or snapshot;
  4, beyond a grant's limits with its envelope, or confirmation required; 1, the capability failed; 124, a bound.
- **FR-44** Every `up`, `restore` and `snapshot` verdict fits agentio's 200 columns at a realistic name length, and
  each clause of a verdict says only what was done: "ports probed" appears only when a port was probed (D-20).

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

Prompt 13's slice-1 criteria, verbatim (slice 1's send):

7. A project's devcontainer definition is brought up and a command is executed inside it.
8. Everything created carries session and grant labels, and a collect command removes environments whose session has
   ended.
9. DEMO (D22, Manual): the Agent brings up a project's devcontainer from inside its container and runs a command in
   it.

Prompt 13's slice-2 criteria, verbatim (slice 2's send):

10. A named volume of a running nested environment is snapshotted and later restored to its snapshotted content.
11. DEMO (D31, Manual): the Agent snapshots a nested environment's database volume, corrupts the data, and restores
    it.

**Measures:**
- Every addressed service is reachable from the agent's container when `up` returns 0.
- After `down`, the daemon holds 0 objects labelled with the environment's project.
- Each refused setting creates 0 objects.
- The operator-side git runs 0 agent-written hooks or config commands while enforced.
- Slice 1: every container, network, volume and built image of an environment carries its session and grant labels,
  read back; after a collection, the daemon holds 0 objects of an ended session's environments, and the ledger has one
  row per environment collected, with its cause.
- Slice 2: after a restore, the volume's digest equals the snapshot's; after a failed snapshot, the daemon holds 0
  partial snapshot volumes and 0 paused services of the environment; after `down` or a collection, 0 snapshot volumes
  of the environment.

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
- **D-7 (plan, FOR-MENTOR Item 28; superseded in slice 1 by D-8)** `build:` is refused in slice 0, as a forbidden setting (exit 2, naming `build`). Compose builds on the
  client side, so a build would run in Adele's process, which can read her credential: a Dockerfile or build secret
  that is a symlink would be read by her. No slice-0 criterion needs a build; the fixture uses images the lane has.

### Slice 1 (send `bridge/sends/13-rev17-20261018-120700.md`; the operator's decisions in
`../bridge/feedback/13-20261018-120700-item-28-builds-and-session-end.md`; FOR-MENTOR Item 28 closed)

- **D-8 (decision 1)** Builds: the sandbox makes the context archive; Adele streams it to the daemon's build API
  without opening it; a build pulls nothing; build secrets, SSH, a non-default network, entitlements and outside
  contexts are refused; `down` and collection remove what an environment built; a build has a bound (FR-20–FR-24).
- **D-9 (the mentor's ruling 1)** Devcontainers go through slice 0's checked path: parsed and translated in the
  sandbox, never the devcontainer CLI (it is Node, and it wants a socket); `features` refused in slice 1
  (FR-16–FR-19).
- **D-10 (decision 2)** A session has ended when its requesting container is gone, or when it was ended explicitly;
  the requesting container is read from the daemon (FR-27, FR-28).
- **D-11 (the mentor's ruling 3)** Session and grant labels on everything an environment creates, read back in the
  criterion's test (FR-26).
- **D-12 (cross-stack P003)** "Unchanged" is decided by the checked model's hash, which for a build includes the
  digest of its context archive as the sandbox made it, its Dockerfile, args and target (R16).
- **D-13 (decision C)** The readiness correction in FR-11.
- **D-14 (the mentor's ruling 2)** `adele env exec` as FR-25.

### Slice 2 (send `bridge/sends/13-rev17-20261019-034239.md`; the operator's decisions of 2026-10-19 and the mentor's rulings in it)

- **D-15 (decision 1)** A snapshot lives with its environment: a volume on the daemon, labelled like everything else
  the environment creates, removed with it, and capped by the grant (FR-33, FR-34, FR-41).
- **D-16 (decision 2)** A volume in use is snapshotted with its users paused; restore stops them, replaces the
  contents, starts them and waits for readiness (FR-35, FR-38).
- **D-17 (the mentor's rulings 1, 2)** The four commands and their names; only the environment's own named volumes
  (FR-31, FR-32). They work on a nested environment's **volumes**, where feature 07's `snapshot` and `undo` work on
  the **workspace**, and the announcement says so.
- **D-18 (the mentor's rulings 3, 4)** The copy in a helper from Adele's own image; the digest recorded and checked
  both ways (FR-36, FR-37).
- **D-19 (the mentor's rulings 5, 6)** The ledger rows and the exit codes (FR-42, FR-43).
- **D-20 (the operator's D22 observations A and B)** Verdicts fit 200 columns, and a clause says only what was done
  (FR-44).

## Assumptions

- The socket's owner, group and mode are as the mentor read them. Nothing in this project verifies that they stay so
  (the send's external prerequisites).
- The images the fixture project uses are already on the daemon; slice 0 pulls nothing (D-1).
- A project's `${VAR}` resolves from the workspace's `.env` only, never the agent's environment; an unset variable is
  named in the verdict (D-1).
- The agent's existing egress through compose's default network is unchanged until 12 slice 2. The new network
  routes nowhere (D-3).
- This session has no Docker. Every e2e cell is first run in the mentor's lane.
- Slice 1: the daemon's classic builder (the build API without a BuildKit session) is available on the host's engine
  (R15). The lane is the first run of it.
- Slice 1: the devcontainer fixtures are timelike's own. Real projects' devcontainers are not tried (cross-stack P005;
  named in the cycle report's `not_verified`).
- Slice 2: the database fixture is timelike's own (SQLite on a named volume, on `DEBIAN_IMAGE` or
  `timelike-agent:local`). PostgreSQL, MySQL and Redis were not tried, and the claim that a paused copy is one a
  database recovers from rests on their crash-recovery, not on a test here (cross-stack P005).
