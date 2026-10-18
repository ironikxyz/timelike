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
