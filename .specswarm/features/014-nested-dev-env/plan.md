# Implementation Plan: 014 nested dev environments (prompt 13, slice 0)

**Branch:** `014-nested-dev-env` (from `master` at `15a5213`) · **Spec:** `spec.md` · **Send:**
`../bridge/sends/13-rev8-20261017-012727.md` (prompt revision 8, discovery revision 16) · **Seams:**
`../bridge/feedback/13-20261017-034920-item-27-seams-answered.md` · **specswarm:** 4.0.1-botbaubble.2.44.0

## Summary

The agent runs `adele env up` in a project in its workspace. Adele then:
1. resolves the project with the Compose CLI in a sandbox that can read only the workspace;
2. checks the resolved model against her refusal list and the `docker.compose` grant;
3. brings it up from the checked bytes on the host's daemon, labelled as timelike's, joined to the internal network
   `timelike-nested` that the agent shares;
4. records a performed ledger row.

The client waits until every service is ready, probing ports from the agent's container, and concludes within its
bound. `adele env down` removes everything labelled with the environment, read back. 12's reaper reaps an expired
environment through a second provider.

The workspace is a host directory per launch, mounted into the agent at the same path. A launcher refuses one inside
a git work tree unless the operator sets `TIMELIKE_HOST_GIT=lifted`.

## Technical Context

| Item | Value |
|---|---|
| Languages | Go 1.27.2 (`adele/`); Python 3.14.x (`tools/bin/adele`, agentio, stdlib); Bash (`scripts/workspace.sh`) |
| Dependencies | **Compose CLI** from the pinned `DOCKER_CLI_IMAGE` (approved: Docker Compose v2; checked static, R1). The Engine API is reached over the unix socket with Go's stdlib `net/http`. No new Go module and no new Python package |
| Storage | 12's ledger (no schema change). Labels on the daemon's objects are the environment's record |
| Transport | agent ↔ Adele as in 12. Adele ↔ daemon over `/var/run/docker.sock` (group from `TIMELIKE_DOCKER_GID`). agent ↔ nested services on `timelike-nested` (internal) |
| Testing | go test (model checks, injection, resolve output, the reaper's provider routing); pytest (the client's readiness loop and verdicts against a fake Adele; the launcher with a real git); bats e2e, one file per criterion plus one for the grant, never-ready and reap cells |
| Performance | Bring-up is bounded at 120 s by default, at most 600 s. Adele's request lock is held for checks and ledger writes, never across a wait |
| Unknowns | none blocking. Not verifiable here (no Docker): whether the compose binary is static (the build checks it), and compose's exact error and warning texts (R2) |

## Constitution Check

| Principle | Check | Result |
|---|---|---|
| P1 | One command brings up the project's own environment, without the operator. Beyond the grant: exit 4 with the operator's command | ✅ |
| P2 | The client's bound gives 124 with each state. The sandbox and compose calls have their own limits. Every path ends in a verdict | ✅ |
| P3 | `adele env up` follows the `<tool> <verb>` habit; listed by `timelike`; in the README section and the generated reference | ✅ |
| P4 | Only Adele holds the socket; refusal before creation; under a grant; labels limit what she acts on | ✅ |
| P5 | Up is idempotent; down removes everything labelled, read back; the performed row's undo is `down` | ✅ |
| P6 | No claim of value | n/a |
| P7 | A shell command | ✅ |
| T1 | A grant limit names the operator's command; a forbidden setting is exit 2 and says no grant allows it, with no command (revision 17) | ✅ |
| H1 | The agent has no socket, group or endpoint (the isolation tests are updated, not loosened). Adele's process never reads the workspace: resolution runs in the sandbox, and builds are refused (R10) | ✅ |
| H2 | Through agentio; exit 4 only for a grant limit; a forbidden setting is agentio's exit-2 error. A missing image's code waits on Item 29 | ✅ |
| H3 | Up's "ready" and down's "removed" are read back from the daemon; ports probed, named "from the agent container" | ✅ |
| H4 | Non-interactive; e2e under `bash -c` and `bash -lc` | ✅ |
| H5 | stdlib Python and Go; the compose binary is a pinned component, static (R1) | ✅ |
| H7 | One file per criterion, named after its text; D9 Manual | ✅ |
| H8 | Adele stays stamped; the sandbox runs her own stamped image | ✅ |
| H9 | The compose binary joins Adele's image scan; its findings are reviewed like any other | ✅ (lane) |

**Post-design re-check:** unchanged. R10 narrows the feature and is raised as FOR-MENTOR Item 28. It does not block
a criterion.

## Project Structure (changed or new)

```
adele/Dockerfile                          + compose binary (static check), DOCKER_CLI_IMAGE arg
adele/internal/compose/                   new: model checks (R3), injection (R5), resolve output, names
adele/internal/engine/                    new: Engine API client over the unix socket (sandbox, images, list, down)
adele/internal/broker/env.go              new: docker.compose up/down/status; the setting and image refusals (one place each)
adele/internal/broker/{broker,http}.go    route docker.compose; /v1/envs
adele/internal/grants/grants.go           KnownCapabilities + docker.compose
adele/internal/ledger/query.go            LiveOf(grant, capability)
adele/internal/reaper/reaper.go           Providers by capability; record wording per provider
adele/cmd/adeled/{main,serve,resolve}.go  `adeled resolve`; the compose provider and engine in serve
compose.yaml                              socket and group for Adele; workspace, group, label, env and network for the agent
scripts/workspace.sh                      new launcher (R9)
Makefile, tests/run.sh                    the launcher before up; DOCKER_GID; runner env and workspace mount
tools/bin/adele                           `adele env up|status|down`
tests/e2e/…                               five criterion files + one; the 004 isolation and network assertions updated
tests/e2e/fixtures/adele/grants.conf      nested grants
tests/e2e/fixtures/nested/                fixture compose projects
tests/unit/test_adele_env_cli.py, test_workspace_launcher.py
README.md                                 the README status block; a section; the generated reference
```

## Tech Stack Compliance Report

### ✅ Approved Technologies (already in stack)
Go, Python, Bash, Docker, Docker Compose v2, bats-core, pytest, go test, modernc.org/sqlite (unchanged).

### ➕ New Technologies (auto-added)
None. The Compose CLI is the approved Docker Compose v2, now also inside Adele's image.

### ⚠️ Conflicting Technologies (require approval)
None.

### ❌ Prohibited Technologies (cannot use)
None used (no cgo, no mattn/go-sqlite3, no MCP, no pyright).

## Complexity Tracking

| Addition | Why | Simpler alternative rejected |
|---|---|---|
| A sandbox per resolution | The resolved model hides what `include` and `env_file` read (Item 27 Q1) | Resolving in Adele's process, which can read her credential |
| The Engine API client in Go | Read-back, label-scoped down and the sandbox need it; compose's own `down` acts on its project label, not timelike's | The docker CLI in her image too: a second large binary for the same calls |
