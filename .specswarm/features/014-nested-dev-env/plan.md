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

---

# Slice 1 (natural) — `bridge/sends/13-rev17-20261018-120700.md`

**Branch:** `modify/014-slice-1` (from `master` at `08df8e2`, v0.22.0) · **Decisions:**
`../bridge/feedback/13-20261018-120700-item-28-builds-and-session-end.md` (FOR-MENTOR Item 28 closed, `cf768d8`) and
the mentor's rulings in the send · **specswarm:** 4.0.1-botbaubble.2.44.0

## Summary

`adele env up` gains two kinds of project input and one capability:
- **a devcontainer**, which the sandbox parses and translates into a compose model (R12);
- **builds**, from a context archive the sandbox makes and Adele streams, unopened, to the daemon's classic builder,
  with nothing pulled (R14–R16);
- **lifecycle commands**, run in the devcontainer after it starts (R13).

New verbs:
- `adele env exec` runs a command in an environment (R17);
- `adele session end` ends the caller's session;
- `adele env collect` removes the environments of ended sessions. Adele's reaper runs the same pass on its tick
  (R19).

Every object an environment creates carries session, grant and requester labels (R21). The requester is the agent
container Adele finds on the daemon by the request's peer address (R18). Readiness follows decision C (R20).

## Technical Context (slice 1)

| Item | Value |
|---|---|
| Languages | unchanged: Go 1.27.2 (Adele), Python 3.14.x (the client), Bash (the lane) |
| Dependencies | **none new.** Go stdlib only: `archive/tar`, `crypto/sha256`, `path/filepath`, and a JSONC reader written here (comments and trailing commas blanked, then `encoding/json`). The Engine API's build, exec and attach endpoints over the existing unix-socket client |
| Builder | the daemon's **classic builder** (`POST /build`, `version=1`): the one the build API offers without a BuildKit session, which would need a gRPC session Adele does not run (R15) |
| Storage | 12's ledger: no schema change; one new writer (a performed row with no undo and no expiry) and the live queries narrowed to rows with an expiry. Labels on the daemon's objects carry session, grant and requester |
| Testing | go test (JSONC and translation, `.dockerignore`, the archive and its digest, the Dockerfile scan, build-key reuse, the refusals, exec and collection against the fake daemon, the ledger's new writer); pytest (the client's exec, collect, session end and readiness verdicts); bats e2e, one file per slice-1 criterion, plus one for the failures and one for decision C |
| Bounds | sandbox 90 s (slice 0's); a build `BuildTimeout` 5 min; a lifecycle command 120 s; exec feature 03's 100 s default (`--timeout`); the context archive at most 256 MiB and 100 000 entries |
| Unknowns | not verifiable here (no Docker): the host engine still offers the classic builder; its progress messages' exact text; the attach stream over the unix socket |

## Constitution Check (slice 1)

| Principle | Check | Result |
|---|---|---|
| P1 | The project's own devcontainer and builds, with no operator; a missing base image names the operator's `docker pull` | ✅ |
| P2 | Every build, lifecycle command and exec has a bound and a verdict naming its step, command or service; collect and session end always answer | ✅ |
| P3 | `adele env exec|collect`, `adele session end` follow the `<tool> <verb>` habit; in the usage lines, the README section and the reference | ✅ |
| P4 | Every new path reaches the daemon only through Adele, under a grant; the devcontainer and build refusals are slice 0's check applied to the translated model; Adele's process never opens a workspace file or the archive (R14) | ✅ |
| P5 | Session and grant labels on every object; ended sessions collected, read back, each a ledger row with its cause; `down` removes built images | ✅ |
| P6 | No claim of value | n/a |
| P7 | Shell commands; `session end` may be called from a harness hook and works without one (T3) | ✅ |
| H1 | The agent still has no socket; the context sandbox is slice 0's sandbox (workspace read-only, no network, no socket, no secret) | ✅ |
| H2 | agentio's codes: 2 a setting or a bad devcontainer.json, 3 not found or a missing base, 4 a grant limit, 1 a failed build step, lifecycle command or one-shot, 124 a bound; exec passes the command's status through as 03's `run` does | ✅ |
| H3 | "Collected", "ended", "removed" and labels are read back from the daemon or the ledger; nothing is reported from a request's success alone (cross-stack P004) | ✅ |
| H5 | stdlib only | ✅ |
| H7 | One file per criterion, named after its text; D22 Manual | ✅ |
| H9 | Adele's image is unchanged in its binaries (`adeled`, `docker-compose`); the scan is the lane's | ✅ (lane) |

## Research (slice 1): R12–R22

### R12 · Devcontainers, in the sandbox (`adeled resolve --devcontainer`)

- **Which file.** The client chooses the devcontainer when `--devcontainer` is given, or when no `-f` is given, the
  project has no root compose file (`compose.yaml`, `compose.yml`, `docker-compose.yaml`, `docker-compose.yml`), and it
  has `.devcontainer/devcontainer.json` or `.devcontainer.json`. So slice 0's projects behave as before. The sandbox
  checks the file exists again: the client's choice is a request, not a fact.
- **Parsing.** JSONC: `//` and `/* */` comments and trailing commas are blanked (same length, newlines kept), then
  `encoding/json` decodes. A syntax error's offset maps to the same line in the original, so the refusal is exit 2,
  `devcontainer.json line N: …`.
- **Variables** (string values, every key): `${localWorkspaceFolder}` and `${containerWorkspaceFolder}` are the
  project directory (the folder holding `.devcontainer` or `.devcontainer.json`); their `…Basename` forms; and
  `${devcontainerId}`, which is the environment's name. `${localEnv:X}` and `${localEnv:X:default}` read **nothing**
  of the agent's environment: the default, or empty, with X reported as unset (slice 0's rule). `${containerEnv:X}`
  is kept literally in `remoteEnv`, and exec resolves it from the container's own environment, read back.
- **Translation.** The sandbox writes a compose file into its `/tmp` and runs `docker-compose config` on it, so the
  model Adele checks is normalised exactly as a compose project's is.
  - `image` or `build`: one service, `devcontainer`. It gets:
    - `image`, or `build: {context, dockerfile, args, target}`, both relative to the json's folder;
    - `environment` from `containerEnv`, and `user` from `containerUser`;
    - `volumes`: the `workspaceMount` (default: the project directory bound at its own path), then `mounts`;
    - `working_dir` from `workspaceFolder`, and `expose` from `forwardPorts`;
    - `init` and the mapped `runArgs`.

    With `overrideCommand` true (the default here), the entrypoint becomes a `/bin/sh` loop that ends on SIGTERM.
  - `dockerComposeFile`: those files, relative to the json's folder, plus an override for `service` with
    `containerEnv`, `containerUser`, `workspaceMount`, `mounts`, `forwardPorts` and, when `overrideCommand` is true
    (default false here), the loop. The project directory is the first file's folder (compose's own default). The
    model is filtered to `service`, `runServices` (default all) and their `depends_on` closure.
  - **`workspaceMount`** must be `type=bind` with `target` equal to `source`, or it is exit 2 (the same-path rule).
    **`workspaceFolder`** must lie inside the workspace; otherwise it is exit 2 naming it, with the remedy
    `${localWorkspaceFolder}`.
  - **`runArgs`** that map to a checked setting become compose keys, which slice 0's check then accepts or refuses
    exactly as for a compose project:
    - `-e/--env`, `-l/--label`, `-u/--user` and `-w/--workdir`;
    - `-h/--hostname`, `--init`, `--shm-size`, `-m/--memory` and `--cpus`;
    - `--add-host`, `-v/--volume` and `--mount`;
    - `--cap-add`, `--privileged`, `--security-opt` and `--device`;
    - `--network/--net`, `--pid`, `--ipc`, `--uts` and `--userns`;
    - `--name`.

    Any other is exit 2, naming the argument. `privileged`, `capAdd` and `securityOpt` map the same way, so their
    refusal is slice 0's own.
  - **Refused at translation** (exit 2): `initializeCommand` (it runs on the host); `features` (not brokered in slice
    1); `appPort` (it publishes on the host); and any key not on the list. Listed keys that need nothing (`name`,
    `customizations`, `hostRequirements`, `portsAttributes`, `otherPortsAttributes`, `shutdownAction`, `waitFor`,
    `userEnvProbe`, `updateRemoteUserUID`, `$schema`) are ignored. `postAttachCommand` is ignored and named in the
    verdict ("no attach").
- **What the sandbox returns** beside the model:
  - the devcontainer's primary service and its `remoteUser` (default `containerUser`, else the image's user);
  - its `remoteEnv`, its workspace folder, and its lifecycle commands.

  Adele puts the user, the folder and the environment on the primary service as labels (`…devcontainer=1`,
  `…remote-user`, `…workdir`, `…remote-env`), so exec reads them back from the container.

### R13 · Lifecycle commands

After compose has created a **new** environment and recorded it, Adele runs `onCreateCommand`,
`updateContentCommand`, `postCreateCommand` and then `postStartCommand` in the primary container.
- **How:** an exec as the remote user, in the workspace folder, with `remoteEnv`. A string is run with
  `/bin/sh -c`, an array as is, and an object as each of its commands in key order, named `<key>.<name>`.
- **Bound:** each has `LifecycleTimeout` (120 s).
- **Answer:** up's answer lists each command with its exit code and last lines.
  - **A failure** is still a performed environment. The client exits 1, naming the command; the environment stays
    up, and the verdict gives `down`.
  - **Past the bound** the client exits 124, naming the command.
- **No repeat:** an unchanged repeat `up` runs none.
- **Locking:** Envs' lock is released before the first command, so a long one does not hold other bring-ups.

### R14 · The context archive (`adeled context`, a second sandbox)

- **Paths and who resolves them** (cross-stack P002):
  - **The sandbox** resolves the context directory and the Dockerfile (compose's `config` makes both absolute).
    Each must lie inside the workspace after `EvalSymlinks`, or it is exit 2 like a bind source.
  - **The daemon** reads only the tar.
  - **Adele** reads neither: she copies bytes from the sandbox's attach stream into the build request's body,
    counting them. She never parses them.
- **The archive.** `filepath.WalkDir` walks the context, which follows no link. A symlink is archived as a link
  (`Linkname` from `Readlink`) and resolves nowhere in the context. Sockets, fifos and devices are skipped.
  - **`.dockerignore`** (the context's root) is applied with the CLI's semantics: `*`, `?`, `**`, `!` exceptions,
    and a cleaned leading `/`. The Dockerfile and `.dockerignore` are always sent.
  - **A Dockerfile outside the context** (inside the workspace) is added as `.timelike-dockerfile-<6 hex>` at the
    root and named in the build's `dockerfile` parameter.
  - **Each header** has uid and gid 0, as the CLI sends.
  - **Bounds:** at most `MaxContextBytes` (256 MiB of content) and 100 000 entries, or it is exit 1 naming the bound,
    with the remedy `.dockerignore`.
- **The transport.** Adele creates the context sandbox with `LogConfig: none`, so nothing is written to the host's
  log, attaches to it (`POST /containers/{id}/attach`, upgraded), starts it, and pipes stdout's frames straight into
  `POST /build`. stderr is kept (bounded) for the verdict.
- **The digest.** The digest in the model hash (R16) is computed by the same walk in the resolve sandbox. It covers
  each entry's path, type, mode, link and content, never times, so a touched but unchanged file builds nothing.

### R15 · The builder, and why nothing is pulled

The daemon's classic builder (`version=1`). It needs no session, ignores a `# syntax=` line (no frontend image is
fetched), and has no secret, SSH or entitlement mechanism at all. The request is:
`t=TAG`, `dockerfile`, `target`, `buildargs`, `labels`, `pull=0`, `rm=1`, `forcerm=1`, `networkmode=default`, `q=0`.

**The classic builder does pull a missing base image, whatever `pull` says.** So nothing is pulled because of two
guards:
1. **Before any build**, the sandbox reports every base the Dockerfile names, and Adele inspects each one on the
   daemon. A missing one is refused, exit 3, naming the operator's `docker pull`.
   - The sandbox's Dockerfile scan reads line continuations and the `ARG`s before the first `FROM` (with the build's
     args), then `FROM [--platform] REF [AS NAME]` and `COPY --from=REF`.
   - `scratch` and earlier stages' names are not images.
2. **During the build**, Adele reads the progress stream. At the first message that is a pull (`Pulling from`,
   `Pulling fs layer`, `Downloading`, `Pull complete`), she cancels the request, so the daemon stops the build, and
   refuses with exit 3, naming the image.
   - This covers a base removed between the check and the build, for example by the host's 23:50Z prune (lore dokploy
     Q010).

The test is a cell whose base is absent: exit 3. The daemon then still has no image of that reference, read back.

### R16 · What is refused in a build, and when a build happens

- **The compose `build` keys allowed:** `context`, `dockerfile`, `args`, `target`, and `labels` (none under
  timelike's prefix).
  - **Refused with exit 2:** `secrets` and `ssh`; `network` other than `default`; `entitlements`; `privileged`;
    `additional_contexts`, which the classic builder cannot take, so none is brokered. The rest are refused naming
    the key: `cache_from`, `cache_to`, `platforms`, `tags`, `extra_hosts`, `dockerfile_inline`, `isolation`,
    `shm_size`, `ulimits` and `pull`.
  - **In the Dockerfile**, the scan refuses `RUN --mount=type=secret` (build secrets), `--mount=type=ssh` (SSH), a
    `--network` other than `default`, and `--security=insecure` (entitlements).
- **Unchanged** (cross-stack P003). A build's key is the SHA-256 of the context digest, the Dockerfile's path in the
  archive, the sorted args and the target. The tag is `<env>-<service>:<key[:12]>`, labelled with the key.
  - **The model's hash** covers the key. So a live environment with an unchanged project is a no-op, and one whose
    Dockerfile or context changed is "up with a different model" (409, `down` first), as for any changed model.
  - **An existing image** with that tag and key is reused, with no build. A changed one builds again.
- **The image's labels:** `…env`, `…session`, `…grant`, `…requester`, `…build-key` and `…created`.
- **Down and collection** remove images labelled `…env=NAME` after their containers, then read back.
- **The bound:** `BuildTimeout` (5 min). The step is read from the stream (`Step N/M : …`). Past the bound, the
  request is cancelled and the answer names the step (client exit 124). An `error` in the stream is exit 1, naming
  the step, with the last 6 lines.
  - **Cycle 7 (lane 13s1a):** the step is named by the instruction and its position N in the Dockerfile. M is never
    said: moby's classic builder appends one `LABEL` step per request label to the last stage (`buildLabelOptions`,
    read in moby v28.5.1). Steps are numbered in the Dockerfile's order, with the label steps last, so N is the
    position. A label step is known by being `LABEL <one of the request's keys>=`. The lines kept are that step's own,
    without the daemon's `--->` lines.
- **Where it runs:** after the check and before Envs' lock. A request given up while building stops the build;
  nothing of the environment exists yet. An image it left is labelled with the environment's name, so `down NAME`
  and the lane's sweep find it.

### R17 · `adele env exec`

`POST /v1/requests`, `action: exec`, `params: {name, service, cmd}`.
- **Adele:** the environment must be live (ledger) and the service's container running (daemon), or it is 404 (exit
  3). A container that exists but is not running is exit 1, naming its state.
  - **The exec** runs as the container's `…remote-user` label, or the image's own user, in `…workdir`, with
    `…remote-env` (its `${containerEnv:X}` read from the container). It is never privileged, has no TTY, and stdout
    and stderr are attached.
  - **Output:** the stream is demultiplexed, and each of stdout and stderr is kept to its last 1 MiB, with the bytes
    dropped counted.
  - **Bound:** the client's `--timeout` (default 100 s, feature 03's), passed in. Past it, the answer is a timeout.
    **The Engine API has no call to stop an exec'd process**, so the verdict says it may still be running and that
    `adele env down NAME` removes the container.
  - **The ledger:** a performed row with no undo: capability `docker.compose`, action `exec`, the environment as
    resource, and as cause the service, the command (at most 200 characters) and the exit status.
- **The client:** `exec` passes the command's exit status through as feature 03's `run` does (agentio's `passes_exit`
  for that verb). Output goes through agentio's caps and truncation, and the default target is the devcontainer's
  primary service, or the only service. A project with more than one service and no `--service` is exit 2, naming
  the services.

### R18 · The requesting container, read from the daemon

`http.go` passes the request's peer address (`RemoteAddr`) into the broker. It is never a field the client can set.
Adele lists the containers carrying the agent's launch label (`xyz.ironik.timelike.host-git`) and takes the one whose
endpoint on a network named `…adele-request` has that address.
- **Found:** its id is the environment's `…requester` label and is in up's answer.
- **Not found:** the label is `unknown`. The answer says so, and rule (a) cannot collect it: only `session end` or
  the ttl can.

### R19 · Session end and collection

- **`POST /v1/sessions/end`** `{session, agent}`. If the ledger has an end row for the session, the answer is
  `already ended`, with its time and row.
  - Otherwise Adele writes a performed row with no undo: capability `adele.session`, action `end`, the session as
    resource, grant `(none)` (not a valid grant name, so never a grant's). Then she reads it back.
- **The pass, `POST /v1/envs/collect`**, is the same function the reaper calls on its tick. For each live
  `docker.compose` row:
  - **Ended (b):** the ledger has an end row for its session. The cause is "session S ended at T (adele session end,
    ledger #N)".
  - **Ended (a):** otherwise, its `…requester` label names a container that the daemon's list of agent containers no
    longer has. The cause is "session S's agent container ID no longer exists".
  - **The removal:** Adele takes Envs' lock for the name, takes everything down (built images too) and reads it back.
    0 left is a `reaped` row with the cause. Anything left is a `reap-failed` row, tried again on the next pass.
- **The answer:** what was collected, each with its cause, removal counts and row, and what failed. Nothing to
  collect is `0 collected`.
- **A slice-0 environment** with no session labels is collected only by the ledger's session end, or reaped by its
  ttl.

### R20 · Readiness, decision C

`Inject` labels each service that another service's `depends_on` names with `condition:
service_completed_successfully` as `…one-shot=1`. Services read back carry `one_shot`, and for an exited non-zero
container its last 10 log lines. The client's rule for each service:

| The service | Its word |
|---|---|
| Exited 0 | completed |
| Exited non-zero | failed: exit 1, naming the service and its last lines |
| Has a healthcheck | as slice 0 |
| Running, with ports | as slice 0 (probed from the agent's container) |
| Running, no healthcheck and no port, `one_shot` | waiting for its exit |
| Running, no healthcheck and no port, otherwise | **running, no readiness check**: it never counts as ready, does not block, and is named in the verdict (`N ready, M running with no readiness check`) |

### R21 · Labels on everything an environment creates

`Inject` adds `…session`, `…grant` and `…requester` beside `…env` on every service, network and volume (the project's
default network and declared volumes included). The build adds them to images (R16). The criterion's test reads all
four kinds back.

### R22 · The lane

- **Fixtures** (`tests/e2e/fixtures/nested/`):
  - `devcontainer/` (image type, lifecycle commands, `remoteUser`, `forwardPorts`);
  - `devcontainer-build/` (a two-line Dockerfile `FROM ${BASE}` with `BASE` passed as an arg);
  - `build/` (a compose `build:`);
  - `oneshot/` (decision C).

  Each base is `DEBIAN_IMAGE` or `timelike-agent:local`, which the lane already has. Nothing is pulled, and each
  build is two or three layers (disk-bound host).
- **The lane's start** (`tests/run.sh`, the parallel e2e start) also removes images labelled `xyz.ironik.timelike.env`
  (`tl-*`), as it removes sandboxes and SC-8's volumes.
- **Rule (a)'s cell** starts a throwaway agent container from `timelike-agent:local`:
  - labelled as the agent is (`host-git`), on `adele-request` and `timelike-nested`, with the workspace at its path;
  - it brings up an environment, is removed, and `adele env collect` from the agent collects it ("container gone").
- **Classes:** no new `serial` file. The collect cells run each pass over every live environment, but collect only
  ended sessions: their own throwaway's, or their own session's after `session end` with a session id of their own
  (`TIMELIKE_SESSION`).

## Data model additions (slice 1)

See `data-model.md` § Slice 1.

## Contract additions (slice 1)

See `contracts/adele-env.md` § Slice 1.

## Tech Stack Compliance Report (slice 1)
<!-- Auto-generated by SpecSwarm tech stack validation -->

### ✅ Approved Technologies (already in stack)
Go (stdlib), Python (stdlib, agentio), Bash, Docker, Docker Compose v2, bats-core, pytest, go test.

### ➕ New Technologies (auto-added)
None. The JSONC reader, `.dockerignore` matcher and tar writer are stdlib code in Adele's module. The devcontainer
CLI is not used (the mentor's ruling: it is Node, and it wants a socket).

### ⚠️ Conflicting Technologies (require approval)
None.

### ❌ Prohibited Technologies (cannot use)
None used.

## Project Structure (slice 1, changed or new)

```
adele/internal/devcontainer/       new: JSONC, variables, translation to a compose file and override, the refusals
adele/internal/buildctx/           new: .dockerignore, the walk, the archive, its digest, the Dockerfile scan
adele/internal/compose/compose.go  build: allowed with R16's checks; labels R20/R21; build keys in the hash
adele/internal/engine/engine.go    Build (streamed, pull watch), Exec, attach for a sandbox, images in Down/Count, ContainerByAddress
adele/internal/broker/env.go       devcontainer and builds in up; lifecycle; exec; collect; session end
adele/internal/broker/{http,broker}.go  peer address; /v1/sessions/end, /v1/envs/collect; actions exec
adele/internal/ledger/             Recorded (performed, no undo, no expiry); SessionEnded; live queries need an expiry
adele/internal/reaper/reaper.go    a pass on its tick (collection)
adele/cmd/adeled/{resolve,context,serve}.go  --devcontainer; `adeled context`; the collection pass wired
tools/bin/adele                    env exec|collect, session end; readiness per decision C
tests/e2e/…                        two criterion files, the failures file, decision C's file; fixtures; nested.bash helpers
tests/run.sh                       the lane-start image sweep
tests/unit/test_adele_env_cli.py   the client's new verbs and readiness
README.md                          the adele env section, the readiness paragraph, the status block, the reference
```

## Complexity Tracking (slice 1)

| Addition | Why | Simpler alternative rejected |
|---|---|---|
| A second sandbox per build, attached | The operator's decision: the archive is made where only the workspace is visible, and Adele never opens it | Adele archiving the workspace herself (reopens the link into her secret volume) |
| Attach instead of logs | The log driver re-encodes stdout as JSON strings (binary is mangled) and writes it to the host's disk | Reading the archive back from the sandbox's logs |
| Watching the build for a pull | The classic builder pulls a missing base whatever `pull` says | Trusting the pre-check alone (a prune between check and build) |
| A translation, not the devcontainer CLI | The mentor's ruling: the CLI is Node and wants a socket | — |

---

# Slice 2 (hardened) — `bridge/sends/13-rev17-20261019-034239.md`

**Branch:** `modify/014-slice-2` (from `master` at `295824e`, v0.23.0) · **Decisions:** the operator's two
(2026-10-19) and the mentor's seven rulings, in the send · **specswarm:** 4.0.1-botbaubble.2.44.0

## Summary

An environment's named volumes can be snapshotted and restored, through Adele, under the grant:
- `adele env snapshot|snapshots|restore|snapshot-rm` on the agent's side (R31);
- on Adele's side, a snapshot is a volume on the daemon that she creates and labels like the rest of the
  environment, filled by a throwaway helper from her own image (R23–R25);
- a volume in use is copied with its users paused (R26). Restore stops them, replaces the contents, starts them and
  waits for readiness (R27);
- every pause and stop is recorded before it is made, so a crash never leaves a service paused or stopped (R28);
- the snapshot's digest is recorded when it is taken and checked both ways (R24);
- the cap comes from the grant (R29), and nothing a snapshot creates outlives its environment (R30).

The two D22 observations (A: verdicts past 200 columns; B: "ports probed" when nothing was) are fixed in the client
(R32).

## Technical Context (slice 2)

| Item | Value |
|---|---|
| Languages | unchanged: Go (Adele), Python (the client), Bash (the lane) |
| Dependencies | **none new.** Go stdlib (`io/fs`, `syscall` for owners, times and links, `crypto/sha256`). The Engine API's volume, pause, unpause, stop and start endpoints over the existing client |
| Storage | 12's ledger: **no schema change.** One new writer (a performed row with an undo and no expiry), one ending writer for a pause or a stop, and queries by action. The snapshot's record (digest, bytes, files) is in its row's undo document, beside the removal it names |
| Testing | go test: the copy, digest and measure package against temp trees (owners and modes where the test runs as root, skipped and said otherwise); the broker's snapshot, restore, refusals, recovery and orphan passes against the fake daemon; grants' new keys; pytest: the four verbs, the confirm protocol, verdict widths; bats e2e: the criterion's file, the failures file, the recovery file |
| Bounds | a snapshot's copy `SnapshotTimeout` 5 min; a restore's copy the same; the measure and digest helpers 2 min; a stop 10 s per container; a restore's readiness the client's `--wait` (120 s default, as `up`) |
| Unknowns | not verifiable here (no Docker): pause and unpause read back on the host's engine; a helper's capabilities enough for a database's owners; tmpfs volumes on the host's engine |

## Constitution Check (slice 2)

| Principle | Check | Result |
|---|---|---|
| P1 | The agent snapshots and restores its environment's data itself; over the cap, the operator's exact command | ✅ |
| P2 | Every snapshot, restore and removal has a bound and a verdict naming its cause: a full store, a killed helper, a mismatched digest, a service not ready | ✅ |
| P3 | `adele env snapshot…` follows the `<tool> <verb>` habit; the announcement and `--agent-info` say these are an environment's volumes, where `snapshot`/`undo` are the workspace's (R31) | ✅ |
| P4 | Only through Adele, under the grant's cap; the helper has no network, no socket and no secret; Adele never opens volume contents | ✅ |
| P5 | The point of the slice: an environment's data back to a prior state, by the agent | ✅ |
| P6 | No claim of value | n/a |
| P7 | Shell commands only | ✅ |
| H1 | No socket in the agent; the helper is a sandbox from Adele's image with named capabilities only (R25) | ✅ |
| H2 | Exit codes as slice 0's (FR-43); restore's exit 4 is the confirm envelope, the cap's is the grant envelope | ✅ |
| H3 | "Taken", "restored", "unpaused" and "removed" are read back: digests, the daemon's state, the daemon's volume list (cross-stack P003, P004) | ✅ |
| H5 | stdlib only | ✅ |
| H7 | One file per criterion (the snapshot criterion), the failures file, the recovery file; D31 Manual | ✅ |

## Research (slice 2): R23–R33

### R23 · Where a snapshot lives

A snapshot is one volume on the daemon, named `<env>-snap-<hex>` for the snapshot `s-<hex>` (8 random hex), created by
Adele:
- **labels:** `…env=<env>` (so slice 0's `down` and every collection remove it with the environment), `…snapshot=<id>`,
  `…snapshot-of=<the source volume's daemon name>`, `…session`, `…grant`, `…requester`, `…created`, and the compose
  project label left empty so compose never counts it as its own;
- **the record** is the snapshot's ledger row (R24), not the volume: a volume's labels are fixed when it is made,
  before its digest is known, and the record must not live where the content it vouches for lives;
- a snapshot volume with no record is **partial** (a copy cut short by Adele's death). It is never listed, and R30
  removes it.

The store is a plain local volume. A grant may set `snapshot-store = tmpfs`: the volume is a tmpfs of the cap's
size, held in memory and lost when the daemon restarts. It exists so a store can be bounded, which is how the
disk-full cell fills a store without touching the host's disk (R33); the README says what it costs.

### R24 · The digest, and what "whole" means

The helper walks a tree in lexical order and hashes one line per entry: its relative path, type, mode bits
(including setuid, setgid, sticky), uid, gid, mtime (seconds and nanoseconds), and for a regular file its size and
the SHA-256 of its content, for a link its target, for a hard link the path it shares an inode with. The root's own
mode, owner and times are its first line. The digest is SHA-256 over the lines. The byte count is the sum of regular
files' sizes; the file count is the entries other than the root.
- **Snapshot:** the helper copies the source to the snapshot volume, then digests the copy. Adele keeps the
  snapshot only when the source's digest during the copy equals the copy's read back.
- **Restore:** before anything is stopped, a helper digests the snapshot volume, and Adele compares it with the
  record. A mismatch is exit 1, nothing stopped. After the copy, the target's digest must equal the record.
- **Not copied, and said:** sockets (they cannot be copied; the count is in the record and the verdict). A device node
  is refused (exit 1 naming it): making one needs `MKNOD`, which the helper does not get. Extended attributes and ACLs
  are not kept (`not_verified`).
- A file that changes during the copy cannot happen to a paused service's files. It can happen to a volume no running
  service mounts but a stopped one does, which nothing writes.

### R25 · The helper

`adeled volume measure|copy|digest|restore`, run by `engine.Run` as a sandbox from Adele's own image:
- network none, no socket, no secret, read-only root, `no-new-privileges`, its `/tmp` a small tmpfs, memory and
  pids bounded, `LogConfig` none;
- the source mounted read-only at `/src`, the target (if any) at `/dst`;
- **user 0, with all capabilities dropped and these added, each for one reason:**
  - `CHOWN`, to give each copied entry its owner and group;
  - `DAC_READ_SEARCH`, to read a database's files and directories whatever their modes (a 0700 directory owned by
    uid 999);
  - `DAC_OVERRIDE`, to write into directories the copy has already given to another owner;
  - `FOWNER`, to set modes and times on entries it does not own;
  - `FSETID`, so setting a mode keeps a setgid or setuid bit after the owner changes;
- labelled `…sandbox=volume`, so the sandbox sweep removes one left behind, and named `tl-sandbox-<env>-vol-<hex>`,
  which is how the lane's kill cell finds it.

Its answer is one JSON line on stdout (`digest`, `bytes`, `files`, `sockets`, and for a copy `copy_digest`). Its exits
are its own: 0 done; 10 the bytes are past `--max-bytes` (nothing written: it measures before it writes); 11 no space
in the target; 12 an entry it will not copy (a device); 1 anything else. Adele reads both.

### R26 · Snapshot, in order

Under Envs' lock (`snapshot NAME`), so no `up`, `down` or restore of any environment interleaves:
1. the environment is live and its volume is one of its own named volumes (FR-32), else exit 3;
2. the cap (R29): the helper measures the source, unpaused and read-only, and a snapshot past the cap is refused, with
   nothing written;
3. the users: the environment's running containers whose mounts include the volume;
4. **a pause row first** (R28), then pause each, read back paused;
5. create the snapshot volume, run the copy (`--max-bytes` the cap left, so a volume that grew since step 2 fails
   rather than passes the cap);
6. **unpause, whatever happened**, read back running; end the pause row;
7. a failed copy: remove the snapshot volume, read back gone, exit 1 naming the cause;
8. the digests equal: the snapshot row, then the answer.

### R27 · Restore, in order

`--dry-run`, and a call without `--yes`, get the plan from Adele (`dry_run: true`): the volume, the snapshot, the
services that would be stopped. Nothing is checked that changes anything, and no row is written. With `--yes`, under
Envs' lock:
1. the snapshot is this environment's, and its source volume is still one of this environment's volumes (FR-32);
2. the snapshot's digest is checked against its record, before anything is stopped;
3. **a stop row first**, then stop the users (10 s each), read back exited;
4. the restore helper empties the target (not its root) and copies the snapshot in; the target's digest must equal
   the record;
5. **start the stopped services, whatever happened**, read back; end the stop row;
6. Adele waits, bounded, for each started service's healthcheck as the daemon reports it, and records what she read:
   the restore row names the snapshot, the services stopped, and that readiness;
7. the answer carries the services, and the client then waits for readiness exactly as `up` does, probing ports from
   the agent's container (cross-stack P001), with `up`'s verdict.

A copy that fails at step 4 leaves the volume partial: the services are started again (step 5), the verdict says the
contents are partial and names `restore` again and `down`. A service that is not ready after a restore is exit 1;
the data stays restored.

### R28 · Never left paused, never left stopped

A pause row and a stop row are performed rows whose undo is the unpause or the start, naming the containers, written
**before** the pause or stop. Each is ended by a row referring to it once the unpause or start reads back. A pass at
Adele's start and on every reaper tick (the slice-1 `After` hook) takes every open pause or stop row, unpauses or
starts whichever of its containers the daemon still has paused or stopped, and ends the row with the cause ("Adele
stopped while it was paused; unpaused, read back running"). The daemon cannot label a running container, so "labelled
when paused" (the send) is kept by the ledger instead, and the cycle report says so.

### R29 · The cap

The grant file gains two optional keys (absent means the default): `snapshots`, a size (`1GiB`, `256MiB`, `64KiB`,
`0`), default **1 GiB**, the bytes of snapshots one environment may hold; and `snapshot-store` (R23). `adeled extend
GRANT snapshots SIZE` raises it. "Used" is the sum of the recorded bytes of the environment's snapshots that still
have a volume. A refusal is the grant envelope: `limit: snapshots`, allowed "1 GiB (300 MiB used)", needed "volume
db-data: 900 MiB", and the operator's command with the size that would allow it.

### R30 · Nothing outlives its environment

- `down` and collection already remove every volume labelled with the environment. They now count snapshot volumes
  apart (`snapshots` in the counts), and end each snapshot's row with the cause.
- The pass of R28 also: ends the row of every snapshot whose volume the daemon no longer has ("gone"); removes a
  snapshot volume whose environment has no live row and no containers, ending its row ("orphan: its environment is
  gone"); removes a snapshot volume with no record, with a row ("partial: the copy was cut short"): at Adele's start
  every such volume, since no copy of hers can be running then; on a tick, only one older than the copy's bound and
  a minute.
- The lane-start sweep removes every volume labelled `…env`, which snapshot volumes are.

### R31 · The client

`adele env snapshot [NAME] VOLUME [--note TEXT]`, `snapshots [NAME]`, `restore [NAME] SNAPSHOT [--yes] [--dry-run]
[--wait S]`, `snapshot-rm [NAME] SNAPSHOT [--yes]`, each on agentio like the rest of `adele env`.
- **Confirm:** restore and snapshot-rm cannot be undone from what the tool shows, so both use rule 9's confirm
  protocol (`confirmation_required`, the agent's own command with `--yes`). The send names it for restore; snapshot-rm
  deletes the only copy of a past state, which is rule 9's own case. `adele` declares the grant envelope too: the
  cap's exit 4 is the grant's, a restore's is the confirmation's, and each says which.
- **The announcement and `--agent-info`** say these work on a nested environment's **volumes** and that the
  workspace's files are `snapshot` and `undo` (feature 07), in both directions (P3).

### R32 · D22's observations

- **A.** The unchanged `up`'s verdict passed 200 columns. Every `up`, `restore` and `snapshot` verdict is built to fit
  at a 30-character environment name (`tl-` and a project name of 20 and its hash), and a unit asserts the longest
  of each at that length.
- **B.** "ports probed from the agent container" only when a port was probed; otherwise the clause is absent.

### R33 · The lane

- **The criterion's fixture** is a small service on `DEBIAN_IMAGE` that keeps its data (a few KB of files) on a named
  volume owned by a non-root uid, so owners are exercised; the cell snapshots it, changes the data, restores and
  reads the data and the owners back.
- **The disk-full cell** uses the lane grant `nested-snapfull` (`snapshot-store = tmpfs`, `snapshots = 1MiB`) and a
  volume of a few hundred one-byte files: under the cap by bytes, past the tmpfs's 1 MiB by pages, so the copy meets
  `ENOSPC` in memory and never touches the host's disk.
- **The kill cell** kills the copy helper from the runner (`docker kill`, by its name), which is the "Adele or her
  helper dies" case; Adele's own death is the serial file's (stop and start Adele, as 12's reaper cells do).
- **The cap cell** uses the lane grant `nested-snapcap` (`snapshots = 64KiB`).
- No new serial file unless Adele must be stopped; the recovery cell that stops Adele goes in the existing serial
  group with its reason.

## Data model additions (slice 2)

See `data-model.md` § Slice 2.

## Contract additions (slice 2)

See `contracts/adele-env.md` § Slice 2.

## Tech Stack Compliance Report (slice 2)
<!-- Auto-generated by SpecSwarm tech stack validation -->

### ✅ Approved Technologies (already in stack)
Go (stdlib), Python (stdlib, agentio), Bash, Docker, bats-core, pytest, go test.

### ➕ New Technologies (auto-added)
None.

### ⚠️ Conflicting Technologies (require approval)
None.

### ❌ Prohibited Technologies (cannot use)
None used.

## Project Structure (slice 2, changed or new)

```
adele/internal/volcopy/            new: measure, copy, digest and restore of a tree (owners, modes, times, links)
adele/cmd/adeled/volume.go         new: `adeled volume measure|copy|digest|restore`, the helper's entrypoint
adele/internal/engine/             volumes created and removed; pause, unpause, stop, start; mounts on inspect; a sandbox's capabilities; snapshots in counts
adele/internal/broker/snapshot.go  new: snapshot, snapshots, restore, snapshot-rm; the recovery and orphan pass
adele/internal/broker/{broker,env,collect}.go  the actions; down and collection end snapshot rows
adele/internal/grants/             `snapshots` and `snapshot-store`, optional; extend snapshots
adele/internal/ledger/             Kept (performed with an undo, no expiry); Ended; queries by action
adele/cmd/adeled/serve.go          the recovery pass at start and on the tick
tools/bin/adele                    env snapshot|snapshots|restore|snapshot-rm; the confirm protocol; D22 A and B
tests/e2e/…                        the criterion's file, the failures file, the recovery file; fixtures; lane grants
README.md                          snapshots and restore, the cap and its default, pausing, and how they differ from the workspace's snapshot and undo
```

## Complexity Tracking (slice 2)

| Addition | Why | Simpler alternative rejected |
|---|---|---|
| A helper container per copy | The ruling: Adele never opens volume contents, and the copy needs capabilities her serving process must not hold | Adele reading the volume through a bind of the daemon's volume directory (a host path, and her own process opening the data) |
| The record in the ledger, not on the volume | Labels are fixed at creation, before the digest exists, and a record beside the content it vouches for proves nothing | A manifest file in the snapshot volume |
| Pause and stop rows before the act | The daemon cannot label a running container, and a crash between pause and unpause must be found | Unpausing every paused timelike container at start (it would unpause what the agent paused itself) |
| `snapshot-store = tmpfs` | A store bounded in memory is the only way the disk-full case is real without filling the host's disk | Simulating ENOSPC in the helper (tests a branch, not a full store) |
