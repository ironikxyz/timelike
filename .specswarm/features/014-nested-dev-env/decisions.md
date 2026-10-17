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
