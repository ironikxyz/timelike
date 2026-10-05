# Data model — 010 Services (prompt 09, slice 1)

## Registry (`<scratch>/<session>/services/registry.json`, 0600; written under flock, temp and rename)

```json
{"v": 1, "services": {"web": {
  "name": "web", "session": "s", "instance": "4f0c2a91", "command": ["python3", "-m", "http.server", "8000"],
  "cwd": "/work", "port": 8000, "ready": "port", "ready_log": null, "pid": 1234, "pgid": 1234,
  "log": "/tmp/timelike/s/services/web.log", "started_at": 1791190000.123, "ready_s": 0.8,
  "exit": null, "signal": null}}}
```

| Field | Meaning |
|---|---|
| `instance` | random hex, unique per start; part of the marker |
| `ready` | `port` · `log` · `none` |
| `exit` / `signal` | set when `start` saw the death; otherwise null (the death is then unknown) |

## Marker

`TIMELIKE_SERVICE=<session>/<name>/<instance>`, in the environment of the service's first process and
every process that inherits it. It is matched as an exact `NAME=VALUE` entry of `/proc/<pid>/environ`.

## State (`list`)

| State | When |
|---|---|
| `running` | a process with the marker (or holding the log for writing, or in the pgid) is alive and not a zombie |
| `died` | none is |
| `unlisted` | a marker process whose session/name/instance has no entry in its session's registry |

## Tree (stop)

The tree is the marker processes ∪ the log's writers ∪ the members of `pgid`, minus `services` itself and
zombies. It is re-scanned between signals.
