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
