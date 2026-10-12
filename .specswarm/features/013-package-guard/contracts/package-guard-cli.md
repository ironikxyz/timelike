# Contract — `package-guard` (013, slice 1)

```
package-guard [--yes] [--dry-run] [--timeout S] [--json|--text] [--limit N] -- CMD [ARG…]
package-guard CMD [ARG…]          the same (CMD's own options never reach the guard)
package-guard --help | --agent-info
```

001's output contract, rules 1–16. Manifest:
- `mutating: true`, `confirm_protocol: true`, `passes_exit: true`;
- `envelopes: ["confirmation_required"]`;
- probe `["true"]`;
- `event_ref` `log`.

## Exits

| Exit | When |
|---|---|
| CMD's own | Every check passed, or `--yes`, or CMD installs nothing (FR-9's unlisted forms). `cause: command`, `command_exit` is CMD's |
| 0 | `--dry-run`, whatever the checks say (the verdict says what would happen) |
| 4 | A check refused: the `confirmation_required` envelope, and CMD never started |
| 124 | `run`'s limit ended CMD (`--timeout`, or `TIMELIKE_RUN_TIMEOUT`) |
| 2 | Usage: no CMD, or an unknown option of the tool's own |
| 1 | Internal: `run` could not be started, or its result could not be read |

## The envelope (exit 4; `confirm-envelope.schema.json`)

```json
{
  "tool": "package-guard",
  "target": "/home/agent/proj",
  "scope": "install pypi",
  "status": "confirmation_required",
  "plan": [
    "refused: tl-absent-pkg — not in http://127.0.0.1:41733/simple (HTTP 404)",
    "ok: six 1.17.0, released 2024-12-04 (676 days) — http://127.0.0.1:41733/simple",
    "nothing was downloaded: pip install tl-absent-pkg six was not run",
    "proceeding runs: pip install tl-absent-pkg six; the override is recorded in this session"
  ],
  "confirm": "package-guard --yes -- pip install tl-absent-pkg six"
}
```

**One plan line per package.** Each begins with its result word:
- `ok`;
- `pinned` (and in which lockfile);
- `refused`, followed by:
  - `not in REGISTRY (HTTP 404)`;
  - `newest release V was released DATE (N days ago); the minimum age is M days (TIMELIKE_PACKAGE_MIN_AGE_DAYS); the newest release old enough is V2: pip install 'NAME==V2'`;
  - `REGISTRY unreachable from this container: timed out after 10 s (TIMELIKE_PACKAGE_TIMEOUT)`;
  - `REGISTRY gives no release dates (no upload-time): age unknown`;
  - `unchecked source: a URL or VCS reference, which no registry vouches for`;
  - `could not read: …`;
- `unchecked`, for a local path.

**Then two closing lines:** what was not run, and what proceeding runs.

## Verdicts

| Case | Verdict |
|---|---|
| Passed | `N packages checked (P pinned, no lookup) against REGISTRY…; CMD exited E` (and run's own parts: duration, lines, log) |
| Installs nothing | `not an install: ran CMD unchecked; CMD exited E` |
| Proceeded with `--yes` over a refusal | `proceeded over K refusals (recorded: PATH); CMD exited E` |
| `--dry-run`, would pass | `would proceed: N packages checked` |
| `--dry-run`, would refuse | `would be refused: K of N packages` |

## Data (`--json`)

- `ecosystem`, `registries`, `project`, `lockfile`;
- `packages`: a list of `{name, requested, source, result, registry, release, released, reason}`;
- `lookups` (count);
- `override_record`, when overriding;
- `log` (run's), `command_exit`, `cause`.

## Environment

| Variable | Default | Meaning |
|---|---|---|
| `TIMELIKE_PACKAGE_MIN_AGE_DAYS` | `2` | Minimum age of the release checked; decimals allowed; `0` is off |
| `TIMELIKE_PACKAGE_TIMEOUT` | `10` | Seconds per lookup, and for the whole check |
| `TIMELIKE_BIN_DIRS` | `/opt/timelike/bin` | Removed from PATH when CMD is resolved (no recursion) |

## The override record (`<session scratch>/package-guard/override-<UTC>-<pid>.json`)

```json
{"v": 1, "time": "…Z", "session": "…", "agent": "…", "cwd": "…", "command": ["pip", "install", "x"],
 "overridden": [{"package": "x", "ecosystem": "pypi", "registry": "…", "reason": "absent", "detail": "…"}],
 "command_exit": 0}
```

Written before CMD runs (`command_exit: null`), then rewritten with the exit. The tool's event has
`ref: {"log": <this path>}`.
