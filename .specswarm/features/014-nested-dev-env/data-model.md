# Data model: 014 nested dev environments (slice 0)

## Environment (a compose project Adele brought up)

| Field | Where it lives | Rule |
|---|---|---|
| name | `-p` project name; label `xyz.ironik.timelike.env` | `^tl-[a-z0-9][a-z0-9-]{0,59}$`. Default: `tl-<basename slug, ≤40>-<sha256(dir)[:6]>` |
| dir | request param | absolute, clean, under `TIMELIKE_WORKSPACE` |
| files, profiles | request params | at most 8 each. A file is relative to `dir`, with no `..` |
| model | checked JSON (not stored) | its SHA-256 is the label `xyz.ironik.timelike.model` |
| created, ttl | container labels `…created`, `…ttl-seconds` | `expires_at = created + ttl`, truncated to the second, as 12 records it |
| services | read back from the daemon | per service: state, health, exit code, the container ports from label `…ports`, alias `<service>.<name>` |

**State as the client sees it:** `up` (performed) → `ready` | `not ready` (124) | `failed` (exit 1) → `down` (ended,
0 left).

## Ledger rows (12's ledger, unchanged schema)

| Event | outcome | capability | action | resource | Notes |
|---|---|---|---|---|---|
| up created it | performed | docker.compose | up | name | `cost_cents` 0; `expires_at`; undo `{"capability":"docker.compose","action":"down","params":{"name":…}}` |
| up refused | refused | docker.compose | up | name | `limit_name` is a grant limit (with its extend command), a setting (empty `extend`: no grant allows it), or `image` (`extend` is the operator's `docker pull`); `host` is `docker:local` |
| repeat up, unchanged | none | | | | nothing is recorded |
| down | reaped | docker.compose | delete | name | `ref` is the performed row; the cause says `adele env down` by session S, with 0 objects left (read back) |
| reaper | reaped or gone or reap-failed | docker.compose | delete | name | 12's reaper, through the compose provider |

`instances` counts the grant's live `docker.compose` rows (`Ledger.LiveOf`). A stand-in box and an environment never
share a count.

## Grant capability `docker.compose`

Grants keep 12's five keys:
- `instances`: environments live at once;
- `ttl`: an environment's longest life;
- `ports`: host-published ports (`none` by default; a `ports:` publish is checked against it);
- `budget`: required, and slice 0 quotes 0.00 ("local: no cost").
- `capabilities`: may now include `docker.compose`.

## Launch configuration

| Variable | Set by | Shown as |
|---|---|---|
| `TIMELIKE_WORKSPACES` | the operator (environment or git-ignored `local.env`) | — |
| `TIMELIKE_WORKSPACE` | `scripts/workspace.sh` | agent and Adele env; agent label `xyz.ironik.timelike.workspace`; the bind mount at the same path |
| `TIMELIKE_HOST_GIT` | the operator, `enforced` by default | agent label `xyz.ironik.timelike.host-git`, agent env, `adele env up` verdict |
| `TIMELIKE_WORKSPACE_GID` | `scripts/workspace.sh` (the parent's group) | agent `group_add` |
| `TIMELIKE_DOCKER_GID` | Makefile / lane (`stat` of the socket) | Adele `group_add` |

## Slice 1

### Labels (every object an environment creates: containers, networks, volumes, built images)

| Label | Value | On |
|---|---|---|
| `xyz.ironik.timelike.env` | the environment's name | all (slice 0) |
| `xyz.ironik.timelike.session` | the requesting session (self-declared, validated as in 12) | all |
| `xyz.ironik.timelike.grant` | the grant it came up under | all |
| `xyz.ironik.timelike.requester` | the requesting agent container's id, read from the daemon, or `unknown` | all |
| `xyz.ironik.timelike.one-shot` | `1` on a service another depends on with `service_completed_successfully` | containers |
| `xyz.ironik.timelike.devcontainer` | `1` on a devcontainer's primary service | containers |
| `xyz.ironik.timelike.remote-user`, `…workdir`, `…remote-env` | the devcontainer's `remoteUser`, workspace folder and `remoteEnv` (JSON) | the primary container |
| `xyz.ironik.timelike.build-key` | the build's key (R16) | images |
| `xyz.ironik.timelike.created` | RFC 3339 | containers (slice 0), images |

### A build

| Field | Rule |
|---|---|
| context | absolute, inside the workspace after `EvalSymlinks` (the sandbox) |
| dockerfile | inside the workspace; its path inside the archive, or `.timelike-dockerfile-<6 hex>` |
| bases | every `FROM` and `COPY --from` image, after the args; each must be on the daemon |
| digest | SHA-256 over each archived entry's path, type, mode, link and content, in walk order |
| key | SHA-256 of digest, dockerfile path, sorted args and target |
| tag | `<env>-<service>:<key[:12]>` (lowercase; non-`[a-z0-9._-]` characters become `-`) |

### Ledger rows (12's ledger, no schema change)

| Event | outcome | capability | action | resource | Notes |
|---|---|---|---|---|---|
| exec | performed | docker.compose | exec | name | no undo, no `expires_at`; `cause` holds the service, the command (≤ 200 characters) and its exit status; never counted live |
| session end | performed | adele.session | end | the session | grant `(none)`; no undo, no `expires_at`; never counted live |
| collection | reaped | docker.compose | delete | name | `ref` is the up row; the cause is "session S ended at T (adele session end, ledger #N)" or "session S's agent container ID no longer exists"; 0 left, read back |
| collection, objects left | reap-failed | docker.compose | delete | name | tried again on the next pass |

`Live`, `LiveOf`, `LiveResource`, `LiveRows` and `Due` count only performed rows with an `expires_at`.

### Readiness (decision C), per service read back

`one_shot` (bool) and, for a container that exited non-zero, `last_lines` (its last 10 log lines). The client's words:
`ready (healthy)`, `ready (running, ports accept)`, `completed (exit 0)`, `exited N`, `running, no readiness check`, or
`running (one-shot: waiting for its exit)`.
