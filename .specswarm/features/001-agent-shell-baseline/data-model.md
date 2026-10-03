# Data model — 001 agent shell baseline (slice 0)

No database. The entities are files, environment variables and process identities in the image.

## Agent environment (image)

| Field | Where | Rule |
|---|---|---|
| revision | Image label `org.opencontainers.image.revision`. Also `/opt/timelike/REVISION` (mode 0444), which `timelike --agent-info` reads | Non-empty. The build fails if the build arg is empty (H8, lore cross-stack P003) |
| base | Debian trixie-slim, pinned by digest | Digest in the Dockerfile `FROM` line |
| interpreter | `/opt/timelike/python/bin/python3` (uv-managed CPython 3.12) | Tools run with `-I` |

## Agent user

| Field | Value | Rule |
|---|---|---|
| name / uid / gid | `agent` / 1000 / 1000 | Not in `sudo`, `docker`, `adm` or `adele`. No sudo binary in the image |
| capabilities | none (CapEff = CapPrm = 0) | Compose drops ALL and sets `no-new-privileges` |
| setuid binaries | none in the image | Stripped at build time. The test asserts the find returns an empty list |
| home | `/home/agent` | Holds no defaults that matter: defaults live in the process environment and `/etc/gitconfig` (P7) |

## Adele identity (placeholder until feature 12)

| Field | Value | Rule |
|---|---|---|
| name / uid / gid | `adele` / 10001 / 10001 | Reserved system user with no login shell |
| data directory | `/var/lib/adele`, owner `adele`, mode 0700 | Holds `fixture.secret` (mode 0600) so SC-4 can show the agent cannot read Adele's files |

## Session

| Field | Source | Validation |
|---|---|---|
| id | `TIMELIKE_SESSION`, default `default` | `^[A-Za-z0-9._-]{1,64}$`. Invalid → exit 2 |
| scratch | `${TIMELIKE_SCRATCH_ROOT:-/tmp/timelike}/<id>/` | Created on first use with mode 0700. The root is mode 1777 |
| event log | `<scratch>/events.jsonl` | Append-only JSON lines (`contracts/event.schema.json`) |

**Isolation (SC-6):** two sessions never share a scratch path or an event log, because the path is a
pure function of the id. `O_APPEND` single-write lines keep concurrent writers inside **one** session
from interleaving. That is a robustness property, not SC-6 itself.

## Session event

One per tool invocation. The fields are in `contracts/event.schema.json`: `v`, `tool`, `args`, `cwd`,
`exit`, `duration_ms`, `session`, and optionally `ts` and `pid`.

## Tool manifest

Printed by `--agent-info`. The fields are in `contracts/agent-info.schema.json`.

## Timelike tools in slice 0

| Tool | Purpose | Mutating | Probe |
|---|---|---|---|
| `timelike` | Environment info. `--agent-info` carries the build `revision`. Its default output lists the timelike tools on PATH and the contract version | no | `[]` |
| `timelike-conform` | Conformance check (`contracts/conformance.md`) | no | `["--list"]` (lists the tools it would check, without running them) |

## Test fixture (never on the shipped PATH)

- `tests/fixtures/bad-tool/timelike-bad`. It violates C1 (help longer than 40 lines), C5 (exits 1 on
  an unknown flag) and C7 (writes no event). The negative conformance test puts its directory on PATH
  and in `TIMELIKE_BIN_DIRS`, and expects `timelike-conform` to exit 1 naming all three.
