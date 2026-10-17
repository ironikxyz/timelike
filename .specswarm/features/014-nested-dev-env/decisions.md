# Decisions Log — Feature 014
> Generated at 2026-10-17T04:02:13Z (read from the clock)
> Spec: .specswarm/features/014-nested-dev-env/spec.md

## Decision Key

| Tag | Meaning |
|-----|---------|
| ASSUMED | Assumption made without explicit spec guidance (confidence: high/medium/low) |
| DEFERRED | Decision postponed — noted for later resolution |
| FLAGGED | Judgment call between alternatives — requires review |
| ABSENT | What was NOT done and why — forced reflection on gaps |
| INHERITED | Assumption carried forward from a prior task's output |

---

### T001: Adele's image gains the Compose CLI, refused unless static
**Started:** 2026-10-17T04:02:13Z | **Completed:** 2026-10-17T04:06:16Z

INHERITED: (none — first task)
ASSUMED: the plugin binary sits at /usr/local/libexec/docker/cli-plugins/docker-compose in docker:29.9.0-cli, and `go version -m` reads its build info though it is stripped — not checked here (no Docker); a wrong path fails the build loudly at COPY (confidence: medium)
ASSUMED: the binary runs standalone as docker-compose (compose v2's standalone mode), so neither the docker CLI nor buildx is copied (confidence: medium)
FLAGGED: DOCKER_CLI_IMAGE is passed to the stand-in's build too, though its stage does not use the binary — an unused FROM with an empty ARG can fail the whole Dockerfile's parse; chose passing it over a second Dockerfile (confidence: high)
ABSENT: whether the binary is static is not known until the lane builds it; the cycle report's not_verified carries it (Item 27's answer)
ABSENT: the scan's view of the binary's Go modules (it joins Adele's image scan) is the lane's, not this session's
SCOPE: in (2 changed files)

### T002: The launcher scripts/workspace.sh
**Started:** 2026-10-17T04:03:30Z | **Completed:** 2026-10-17T04:06:16Z

INHERITED: none
ASSUMED: the workspace parent is never written into the repository (deny-list P3 matches its absolute path); it comes from TIMELIKE_WORKSPACES in the environment or the git-ignored local.env, and its absence is a refusal naming the variable (confidence: high)
FLAGGED: "enforced" is checked as "the workspace (or its parent) is not inside a git work tree", read with the host's own git, rather than by scanning for .git directories — git's own answer is the one the boundary is about (confidence: high)
FLAGGED: a launch with no git on the host proceeds and says the check was not made, rather than refusing — nothing on such a host runs the agent's hooks (confidence: medium)
ABSENT: old per-launch workspaces are not pruned; each make up makes a new one. Removing them is the operator's
ABSENT: shellcheck did not run here (not installed on this host); make lint runs it in the lane
SCOPE: in (3 changed files)

### T003: docker.compose in the known capabilities; LiveOf, LiveResource, LiveRows
**Started:** 2026-10-17T04:07:10Z | **Completed:** 2026-10-17T04:14:01Z

INHERITED: 12's ledger schema and its "unended" condition (performed with no reaped or gone row) — from 004 (confidence: high)
FLAGGED: instances counts per grant AND capability (LiveOf), not per grant as 12's Live does — a stand-in box and an environment are different resources, and a grant allowing both would otherwise share one count; Live is left as it is, so 12's status and grants are unchanged (confidence: medium)
ASSUMED: "Adele knows: standin.box, docker.compose" replaces "slice 0 knows one: standin.box" in two messages; no test pins either text (grep) (confidence: high)
ABSENT: no new ledger outcome: down's ending is a "reaped" row with its cause, so 12's Live, Due and status read it unchanged
SCOPE: in

### T004: the Engine API client
**Started:** 2026-10-17T04:14:01Z | **Completed:** 2026-10-17T04:14:01Z

INHERITED: none
ASSUMED: the unversioned API path (the daemon's current version) — the pin is the operator's daemon, not a client SDK (confidence: medium)
FLAGGED: down is Adele's own, over the API, by timelike's label, not compose's `down`: compose's down acts on com.docker.compose.project, which an object timelike did not create could carry; the label is the host's rule (confidence: high)
ABSENT: no unit drives the client against a daemon (tech-stack: Adele's Docker calls are never mocked to reach coverage); only Demux is unit-tested, and the lane's e2e cells are its test
SCOPE: in

### T005: the compose model package
**Started:** 2026-10-17T04:14:01Z | **Completed:** 2026-10-17T04:14:01Z

INHERITED: Item 27 Q1's refusal list, accepted for slice 0
FLAGGED: container_name is refused (a name outside the project's could collide with, or be confused for, a container that is not timelike's); not on Item 27's list, a neighbour of it (confidence: medium)
FLAGGED: any security_opt but no-new-privileges is refused, not only the unconfined forms — a label=disable or an apparmor profile name is a choice Adele cannot judge (confidence: medium)
ASSUMED: compose config's JSON shapes (long-form volumes, ports with target/published, expose as strings, top-level env_file kept per service) as compose-go v2 prints them; not checked against the pinned binary here (no Docker). A shape that differs fails a cell, not open (confidence: medium)
ABSENT: sysctls, ulimits, extra_hosts, dns and user are allowed: none reaches outside the container without the refused settings
SCOPE: in

### T006: adeled resolve, the sandbox's entrypoint
**Started:** 2026-10-17T04:14:01Z | **Completed:** 2026-10-17T04:14:01Z

INHERITED: T005's BindSources, Unset, Outside
ASSUMED: compose's error for an absent env_file, include or extends names the absolute path (R2); the setting is read from the error's words. A wording that names none falls to exit 1 with compose's text, never to a pass (confidence: medium)
ABSENT: the resolve command never runs in Adele's own container, but nothing stops the operator running it there; it reads only what it is given
SCOPE: in

### T007: compose.yaml and make up
**Started:** 2026-10-17T04:15:25Z | **Completed:** 2026-10-17T04:15:25Z

INHERITED: T002's launcher output (now printf %q, so a path with a space survives eval)
FLAGGED: without TIMELIKE_WORKSPACE the agent's second mount is an empty named volume at /opt/timelike/no-workspace, not a failure — every compose command (exec, down) interpolates the whole file, so a strict ${VAR:?} would break them (lore docker-compose Q002); the named volume keeps a valid file and creates nothing on the host (a bind of a missing path would be created as root) (confidence: medium)
ASSUMED: the socket's group is read by make from the socket (stat), as tests/run.sh already does for the runner; the default 10001 is Adele's own gid and grants nothing (confidence: high)
ABSENT: timelike-nested's name is fixed (Adele joins services to it by name); two stacks on one daemon would share it — there is one stack per host (container names are fixed already)
ABSENT: files a nested container writes as root into the workspace are root's on the host; the operator removes them with sudo or from a container. Not addressed in slice 0
SCOPE: in
