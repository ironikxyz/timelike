# Research: 014 nested dev environments (prompt 13, slice 0)

The seams were decided in `../bridge/feedback/13-20261017-034920-item-27-seams-answered.md` (FOR-MENTOR Item 27).
This file records how each decision is built, and the choices plan made inside them.

## R1 · The Compose CLI in Adele's image, checked static

- **Decision:** the build stage copies `/usr/local/libexec/docker/cli-plugins/docker-compose` from the pinned
  `DOCKER_CLI_IMAGE` and refuses to continue unless `go version -m` reports `CGO_ENABLED=0` for it. The final stage
  stays `FROM scratch`, with the binary at `/usr/local/bin/docker-compose`. It runs standalone (compose v2's
  `docker-compose` mode); no `docker` CLI and no buildx are copied.
- **Rationale:** the check must be made on the resolved model, and only compose resolves compose's model (Item 27
  Q1). If the binary is not static, the build fails with a message that says to raise it, and no base is chosen
  (the mentor's rule).
- **Alternatives:** the Engine API subset (Item 27's (b)), rejected by the mentor; a third container holding the
  socket, which breaks H1.

## R2 · Resolution in a sandbox, `adeled resolve`

- **Decision:** Adele creates one throwaway container per resolution through the Engine API. It uses her own image
  (`ADELE_SANDBOX_IMAGE`) with the entrypoint `adeled resolve`, and is set up as follows:
  - the workspace bound read-only at its own path, and nothing else mounted;
  - network `none`, an environment of `HOME=/tmp` only, uid 10001, a read-only root, a `/tmp` tmpfs;
  - all capabilities dropped, `no-new-privileges`, memory and pid limits;
  - the label `xyz.ironik.timelike.sandbox`.

  Inside, `adeled resolve` runs `docker-compose … config --format json` and resolves every bind source it finds in
  the model with `filepath.EvalSymlinks`. It also collects compose's "variable is not set" warnings, and prints one
  JSON document. Adele reads its logs, then removes the container.
- **Rationale:** `include`, `extends` and an inlined `env_file` leave no trace in the resolved model. In the sandbox a
  file outside the workspace is simply absent, and Adele's secret and environment are not there to read (Item 27
  Q1). The realpath step closes the symlink route to a bind mount, because the daemon resolves a bind source on the
  host (lore docker-compose P001 item 1). A link pointing outside the workspace either resolves outside it or does not
  resolve at all, and both are refused. The race between this check and the daemon's mount stays open; it is slice
  2's (`not_verified`).
- **Compose's failure on an absent file** is turned into a refusal. Any absolute path outside the workspace that
  compose's error names is reported with the setting the error's words name (`env_file`, `include`, `extends`, or
  "a file"), as exit 4. Any other compose error is the project's own and is exit 1, with compose's text.

## R3 · What Adele refuses (the list Item 27 Q1 accepted)

Each check reads the resolved model. A refusal names the service and the setting, and nothing is created before it.
- **Privilege:** `privileged`; any `cap_add`; `devices`, `device_cgroup_rules`, `gpus` and device reservations;
  `security_opt` other than `no-new-privileges`; `runtime`; `cgroup_parent`.
- **Namespaces:** `network_mode` host or `container:`; `pid`, `ipc`, `uts`, `userns_mode` or `cgroup` set to host;
  `pid` or `ipc` set to `container:`.
- **Other containers:** `external_links`; `volumes_from` a `container:`; `container_name` (a name outside the
  project's).
- **Mounts:**
  - a bind source outside the workspace, or one that does not resolve, the Docker socket included;
  - a volume with a `driver` other than `local`, or with `driver_opts`;
  - an `external` volume or network;
  - a network with a `driver` other than `bridge`, or with `driver_opts`.
- **Files:** a secret or config whose `file` lies outside the workspace.
- **Builds:** any `build:` (R10, FOR-MENTOR Item 28).
- **Labels:** any service, network or volume label under `xyz.ironik.timelike.`, which is Adele's own.
- **Top-level keys:** any top-level key other than `name`, `services`, `networks`, `volumes`, `secrets`, `configs`
  and `x-*`.

**The refusal (prompt revision 17, replacing Item 27's proposed `extend: none: …`).** Adele answers HTTP 422,
`{"outcome": "refused", "refusal": "setting", "setting", "service", "value", "remediation", "performed": false,
"ledger_id"}`. Her ledger records a `refused` row with `limit_name` set to the setting and an empty `extend`, so 12's
`status` prints "operator's command: none". The client exits 2 through agentio's usage error, with no envelope on
stdout:

    error: <setting> is not allowed (code 2) — no grant allows it; <how to change the request> (service S)

With `--json`, the same is one JSON object on stderr. The remediation says how to change the request (for example
"run it without privileged", "use a path inside the workspace"), never an operator's command.

## R4 · Never pull; a missing image

Before `up`, Adele inspects each service's image (`GET /images/{ref}/json`). If an image is missing, she refuses
with HTTP 422 `refusal: image`, and records a `refused` row with `limit_name: image` and `extend: docker pull <ref>`.
The client exits 3 with rule 14's error, naming the operator's command as the operator's. This is provisional:
plan's test showed the grant envelope is false of it, so it is raised as FOR-MENTOR Item 29, and the code and text
are in one place. `up` runs with `--pull never --no-build`.

## R5 · `up` from the checked bytes

Adele adds her labels and the shared network to the checked model, marshals it, and runs
`docker-compose -p NAME --project-directory /tmp/tl-empty -f - up -d --pull never --no-build --remove-orphans`. The
process environment holds only `HOME`, `DOCKER_HOST` and `PATH=`, so a second interpolation reads nothing of hers.
The project directory is an empty one, so no `.env` is read. The model's SHA-256 is the label
`xyz.ironik.timelike.model`, and a repeat `up` compares against it.

**Labels on everything Adele creates:**
- `xyz.ironik.timelike.env=NAME` on every service, network and volume;
- on containers, also `…created` (RFC 3339), `…ttl-seconds`, `…model` and `…ports` (the container ports the agent is
  told about).

## R6 · `down` and the reaper over the Engine API, read back

`down` and the reaper's delete use the Engine API directly:
1. list containers labelled `xyz.ironik.timelike.env=NAME`, stop each, and remove it with its anonymous volumes;
2. remove the networks, then the volumes, carrying that label;
3. list all three again. The environment's ending is recorded only when 0 objects are left (cross-stack P004).

Nothing without the label is listed, inspected or removed (the host's standing rule). The reaper gains a provider
per capability (`Reaper.Providers`), and the compose provider's `List` returns one entry per labelled environment,
with `CreatedAt` and `TTLSeconds` read from its labels. 12's same-box check therefore holds for a reused name.

## R7 · Readiness: Adele reports, the agent probes

`up` answers once compose has created the containers. The agent's client then polls `GET /v1/envs/NAME`, Adele's
read back from the daemon, every 0.5 s. For each service it applies the readiness rule:
- **healthcheck:** `healthy`;
- **no healthcheck:** `running`, and each of its ports accepts a TCP connection at `<service>.<project>:<port>`,
  probed from the agent's container (cross-stack P001);
- **one-shot:** exited 0 counts as completed.

**When it concludes:**
- **A service exits non-zero:** the client concludes at once with exit 1, naming the service and its code.
- **Not ready within the bound:** exit 124. The bound is 120 s by default, `--wait` at most 600 s. The verdict lists
  each service's state and names `adele env down`.
- **Why the client waits:** Adele's request lock is never held across the wait, and the tool that concludes is the
  one the agent ran (P2).

## R8 · The shared network

`compose.yaml` declares `timelike-nested` (`name: timelike-nested`, `internal: true`, labelled
`xyz.ironik.timelike.network=nested`). The agent joins it. Adele joins every nested service to it as an external
network, with the alias `<service>.<project>`, after checking its label. Its only route is container to container.

## R9 · The workspace and the git boundary: `scripts/workspace.sh`

`make up` and the lane run `scripts/workspace.sh env`, which prints the variables compose reads. **Inputs:**
- `TIMELIKE_WORKSPACES` (the parent, from the environment or the git-ignored `local.env`; never written in the
  repository, P3);
- `TIMELIKE_HOST_GIT` (`enforced` by default, or `lifted`);
- optionally `TIMELIKE_WORKSPACE`. Without it, a new directory `<UTC stamp>-<6 hex>` is made under the parent.

**Its outputs:** `TIMELIKE_WORKSPACE`, `TIMELIKE_HOST_GIT` and `TIMELIKE_WORKSPACE_GID` (the parent's group).

**Enforced** refuses a workspace inside a git work tree, read with the host's own git. So the agent's repositories
are never the operator's checkout: the operator clones or fetches from them. **Lifted** allows it, and says so. A
host without git is told the check was not made. The setting is shown three ways:
- the agent's label `xyz.ironik.timelike.host-git`;
- its environment value `TIMELIKE_HOST_GIT`;
- `adele env up`'s verdict.

## R10 · Builds refused in slice 0 (FOR-MENTOR Item 28)

Compose builds on the client side: it reads the Dockerfile and any build secret itself, and tars the context.
Run inside Adele, a symlinked Dockerfile or build secret would be read by the one process that can read her
credential, and a build error can echo what it read. The fixture needs no build, and no slice-0 criterion names one.
So `build:` is refused (R3). Item 28 asks how slice 1 should build: in a sandbox that exports an image, or with the
workspace mounted into Adele and the Dockerfile path resolved in the sandbox.

## R11 · The lane

- **Projects:** each is named `tl-<file-hash6>-<cell>`. Each cell's teardown asks the daemon, from the runner, for
  anything labelled with its project and requires 0.
- **Fixtures:** projects are written by the agent into the lane's own workspace, using `DEBIAN_IMAGE` (present after
  the lane's `up`, which runs `adele-secret` from it) and `timelike-agent:local`. Nothing is pulled.
- **The operator's git:** a throwaway of `DOCKER_CLI_IMAGE` (alpine, with git), run as the runner's uid. It is the
  operator's stand-in, outside the agent.
- **Lane classes and waits:** the git-boundary file and the file measuring the never-ready bound are `serial`.
  Bring-ups use `PLUMBING_TIMEOUT`.
