# Contract: `adele env` and Adele's environment interface (slice 0)

## HTTP (Adele, on `adele-request`)

`POST /v1/requests` with `capability: docker.compose`:

```json
{"session": "s", "agent": "a", "grant": "g", "capability": "docker.compose", "action": "up",
 "params": {"name": "tl-x-1a2b3c", "dir": "/…/ws/proj", "files": ["compose.yaml"], "profiles": [], "ttl": "1h"}}
```

**`up`**
- **200:** `{"outcome": "performed" | "unchanged", "grant", "resource", "expires_at", "ledger_id" (performed only),
  "undo", "cost_cents": 0, "unset": [VAR…], "host_git": "enforced" | "lifted" | "", "services": [Service…]}`.
- **403:** a grant envelope (12's shape), for a grant limit only (capabilities, ttl, ports, instances). `host` is
  `docker:local`, with `performed: false`.
- **422:** `{"outcome": "refused", "refusal": "setting" | "image" | "file", "setting", "service", "value",
  "remediation", "performed": false, "ledger_id"}`. A setting or an outside file: no grant allows it (revision 17).
  An image: the operator's `docker pull` (Item 29).
- **409:** the environment is up with a different model (`remediation: adele env down NAME`).
- **400** usage, **404** no grant, **502** compose or the daemon failed, with the cause and what is left, read back.

**`down`** with `params.name`:
- **200:** `{"outcome": "ended", "resource", "removed": {"containers": n, "networks": n, "volumes": n}, "left": 0,
  "ledger_id"}`;
- **404:** no environment by that name;
- **502:** objects are left. They are listed, and nothing is recorded.

`GET /v1/envs` returns `{"envs": [{"name", "expires_at", "services": [Service…]}]}` for live rows.
`GET /v1/envs/NAME` returns `{"name", "expires_at", "services": [Service…]}`, or 404.

`Service` is `{"service", "state", "health", "exit_code", "alias", "ports": [int…]}`. `state` and `health` are read
from the daemon. `health` is `""` when the service has no healthcheck.

## CLI (agent side, `tools/bin/adele`)

```
adele env up [DIR] [-f FILE]... [--profile P]... [--project NAME] [--wait S] [--ttl D] [--grant G]
adele env status [NAME]
adele env down [NAME | DIR]
```

**Exit codes:**
- **0:** every service is ready, or down left 0 objects;
- **1:** a service failed, or Adele, compose or the daemon failed;
- **2:** usage (outside the workspace, no workspace mounted, a bad name);
- **3:** no such environment or grant;
- **2:** also a forbidden setting (rule 14's error; no envelope; revision 17);
- **3:** also a missing image (provisional, Item 29);
- **4:** a grant envelope (a grant limit), with nothing created;
- **124:** not ready within the bound. The environment stays up, and the verdict names `adele env down NAME`.

**The `up` verdict:**

```
up tl-proj-1a2b3c: 2 services ready (read back from the daemon, ports probed from the agent container) in 3.1 s of 120 s · grant e2e · local: no cost · host git enforced
db  ready (healthy)  db.tl-proj-1a2b3c:5432
job completed (exit 0)
```

An unset variable adds a line: `unset in the workspace: FOO — put it in the project's .env (the agent's environment
is not read)`.

## Slice 1

### HTTP

**`up`** takes `params.devcontainer: true` for a devcontainer project. Its 200 answer gains:
- `kind`: `compose` | `devcontainer`;
- `requester`: `{"container": ID}` or `{"unknown": "no timelike agent container has the address A"}`;
- `built`: one entry per build, `{"service", "image", "reused": bool, "seconds"}`;
- `lifecycle`: one entry per command, `{"name", "exit_code", "last_lines", "timed_out"}`;
- `not_run`: `["postAttachCommand (no attach)"]` when present.

Its `Service` gains `one_shot` and, for an exited non-zero container, `last_lines`.

**New refusals and failures on `up`:**
- **422 `refusal: setting`** for a devcontainer key or a build setting no grant allows, or `devcontainer.json` that
  does not parse (`setting: devcontainer.json`, `value: "line N: …"`).
- **422 `refusal: image`** for a base image (`setting: FROM`), named with the operator's `docker pull`.
- **502** with `build: {service, step, position, instruction, last_lines, message}` for a failed step.
- **504** with `timed_out: true` and `build: {service, step, position, instruction, last_lines}` for a build past its
  bound.
- **`step`** says where, in the Dockerfile's terms: `instruction N of the Dockerfile, <instruction>`, or `the labels
  Adele adds after the Dockerfile's last instruction`. `position` is N, counted among the Dockerfile's own
  instructions from 1 (0 before the first). `last_lines` are that step's own output, and `message` is the daemon's
  error. The daemon's `Step N/M` is never passed on: its classic builder appends one `LABEL` step per label in the
  request, so M counts Adele's six labels too (lane 13s1a; Cycle 7).

**`exec`**: `params: {name, service, cmd: [..], timeout_s}`.
- **200:** `{"outcome": "performed", "exit_code", "stdout", "stderr", "dropped": {"stdout": n, "stderr": n}, "service",
  "user", "ledger_id"}`.
- **504:** `{"timed_out": true, …the same…}` (the process may still run).
- **404:** no live environment, or no container for the service. 409 lists the services when none was named and there
  is more than one. 502 is a container that is not running (its state).

**`POST /v1/sessions/end`** `{"session", "agent"}`: 200 `{"outcome": "ended" | "already ended", "session",
"ended_at", "ledger_id"}`.

**`POST /v1/envs/collect`** `{"session", "agent"}`: 200 `{"collected": [{"name", "cause", "removed", "ledger_id"}],
"failed": [{"name", "cause", "left"}], "count": n}`.

### CLI

```
adele env up [DIR] [--devcontainer] [-f FILE]... [--profile P]... [--project NAME] [--wait S] [--ttl D] [--grant G]
adele env exec [NAME] [--service S] [--timeout S] -- CMD [ARG]...
adele env collect
adele session end
```

**Exit codes added:**
- **`exec`:** the command's own status (passed through, as 03's `run`); 3 for no such environment or service; 124
  past `--timeout` (default 100 s).
- **`up`:** 1 for a failed build step, a failed lifecycle command, or a service that exited non-zero; 124 for a build
  or a lifecycle command past its bound.
- **`collect`:** 0, including "0 collected".
- **`session end`:** 0, including "already ended".

**Verdicts (examples):**

```
up tl-app-1a2b3c: devcontainer, 1 ready, 1 running with no readiness check in 21.4 s of 300 s · …
devcontainer  running, no readiness check  devcontainer.tl-app-1a2b3c:8000
built devcontainer: tl-app-1a2b3c-devcontainer:4f1e… in 6.2 s (nothing pulled)
postCreateCommand  exit 0
exec tl-app-1a2b3c devcontainer as vscode: exit 0 in 0.4 s
collect: 1 collected (tl-app-1a2b3c: session s1 ended at 2026-10-18T12:00:00Z) · 0 failed · read back from the daemon
session s1 ended at 2026-10-18T12:00:00Z (ledger #140)
```

## Slice 2 (send `bridge/sends/13-rev17-20261019-034239.md`; plan § Slice 2)

All four are `POST /v1/requests`, capability `docker.compose`, under the environment's own grant (the one its `up`
row names) unless `grant` is given. Validation is slice 0's: `name` is the environment.

### `snapshot`: `params: {name, volume, note}`

- `volume` is the compose key (`db-data`) or the daemon's name (`tl-app-1a2b3c_db-data`). `note` at most 200
  characters.
- **200:** `{"outcome": "performed", "grant", "resource": name, "snapshot": {"id", "volume", "volume_name", "bytes",
  "files", "sockets", "digest", "taken_at", "note"}, "paused": [{"service", "container"}], "paused_ms", "took_ms",
  "cap": {"bytes", "used", "left", "store"}, "ledger_id", "undo", "revision"}`. `paused` is empty when no running
  service mounts the volume.
- **404:** `{"error": "no environment named NAME", "envs": [...]}` or `{"error": "no such volume in this environment:
  V", "volumes": [keys], "remediation"}` (a refused row).
- **403:** the grant envelope (slice 0's shape): `limit: {"name": "snapshots", "allowed": "1 GiB (300 MiB used)",
  "needed": "volume db-data: 900 MiB"}`, `extend`.
- **502:** `{"error": the cause, "performed": false, "partial_removed": true, "unpaused": [services],
  "still_paused": [services], "remediation"}`. The cause is the full store, the helper's exit, an entry it will not
  copy, or the digests differing.
- **504:** `{"error", "timed_out": true, "partial_removed", "unpaused", "still_paused"}`.

### `snapshots`: `params: {name}`

- **200:** `{"resource": name, "snapshots": [{"id", "volume", "bytes", "files", "digest", "taken_at", "note",
  "ledger_id"}], "cap": {"bytes", "used", "left", "store"}, "volumes": [keys]}`, newest first. Nothing written.
- **404:** no environment.

### `restore`: `params: {name, snapshot, dry_run}`

- **`dry_run: true`, 200:** `{"outcome": "plan", "snapshot": {...}, "volume": key, "stop": [services], "replace":
  "volume V"}`. Nothing is stopped or written; the client prints it for `--dry-run`, and as the confirmation's plan
  without `--yes`.
- **200:** `{"outcome": "performed", "snapshot": {...}, "volume": key, "stopped": [services], "stopped_ms", "digest",
  "services": [Service], "adele_readiness": {service: "healthy" | "running" | "exited N" | "starting"}, "ledger_id",
  "took_ms"}`. The client then waits for readiness as `up` does.
- **404:** no environment, or `{"error": "no snapshot S in NAME", "snapshots": [ids]}`.
- **502, before anything is stopped:** `{"error": "snapshot S does not match its record: …", "stopped": []}`.
- **502, after:** `{"error", "partial": true, "started": [services], "remediation"}`.

### `snapshot-rm`: `params: {name, snapshot}`

- **200:** `{"outcome": "removed", "snapshot": id, "bytes", "cap": {...}, "ledger_id"}`, read back gone.
- **404:** as restore's.

### `down`, `collect`

`removed` and `left` gain `snapshots`.

### CLI

```
adele env snapshot [NAME] VOLUME [--note TEXT]
adele env snapshots [NAME]
adele env restore [NAME] SNAPSHOT [--yes] [--dry-run] [--wait S]
adele env snapshot-rm [NAME] SNAPSHOT [--yes]
```

`NAME` defaults as for `down` (the project directory's environment). **Exit codes:** 3 no such environment, volume or
snapshot; 4 the grant envelope (the cap) or `confirmation_required` (restore, snapshot-rm without `--yes`); 1 the
capability failed, or a service not ready after a restore; 124 a bound.

**Verdicts (examples):**

```
snapshot tl-app-1a2b3c db-data: s-3f2a91c0, 48.0 KiB, 12 files · paused db for 0.4 s · cap 1 GiB, 1023.9 MiB left
snapshots tl-app-1a2b3c: 2 · 96.0 KiB of 1 GiB used
restore tl-app-1a2b3c db-data from s-3f2a91c0: digest read back · stopped db for 3.1 s · 1 ready in 4.2 s of 120 s
snapshot-rm tl-app-1a2b3c s-3f2a91c0: removed, read back · 48.0 KiB freed
```
