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
