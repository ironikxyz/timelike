# Contract — `package-guard` (013, slice 1)

```
package-guard [--yes] [--dry-run] [--timeout S] [--json|--text] [--limit N] -- CMD [ARG…]
package-guard CMD [ARG…]          the same (CMD's own options never reach the guard)
package-guard --gate [--json|--text] -- CMD [ARG…]   the shims' question: check only, run nothing
package-guard --help | --agent-info
```

## How the bare commands reach it (FOR-MENTOR Item 24, Q1 (b′); built in Cycle 1's addendum)

`/opt/timelike/shims` is first on PATH (the image's `ENV` and `/etc/profile.d/00-timelike-path.sh`). In it,
`pip`, `pip3`, `uv`, `npm`, `npx` and `pnpm` are links to one POSIX sh wrapper,
`/opt/timelike/libexec/install-shim`:
1. it finds the real command: the first of its name on PATH that is not the shim itself (no recursion, P002);
   none → bash's command-not-found handler answers, exit 127, as without the shim;
2. a command that cannot be an install (no install word: `pip --version`, `npm run x`, `uv lock`) is `exec`'d at
   once — no fork, no Python;
3. one that may be an install asks `package-guard --gate -- NAME ARG…` with stdin closed. Exit 0: the guard's
   output is dropped and the real command is `exec`'d, so its output, stdin, environment and exit are its own.
   Anything else: the guard's output (exit 4: the envelope) is printed and its exit is the shim's.

`--gate` takes neither `--yes` nor `--dry-run` (exit 2). A refusal's `confirm` is the tool form exactly,
`package-guard --yes -- <the original command>` (Q2), without the shim's own `--gate` and format option.

**Not reached** (named in the announcement, `--agent-info`'s `shims.not_reached`, and the cycle report):
`python -m pip`; an activated venv's own `pip`, `uv` or `npm` (its `bin` is ahead of the shims);
`/usr/local/bin/pip` or any installer called by its full path (the visible escape). Slice 2's checking proxy
closes them. `type -a pip` shows `/opt/timelike/shims/pip` first.

**A name resolves when its installer is absent** (`--agent-info`'s `shims.resolves_when_absent`, and one line of
the announcement): the six links exist whether or not the installer does, so `command -v pnpm` succeeds in an
image with no pnpm. `type -a pnpm` lists a real one after the shim; run with none, the shim exits 127 with the
command-not-found handler's hint. The guard's own lookups (`pnpm config get registry`, npm's and node's paths,
a `#!/usr/bin/env` interpreter) skip the shims, as CMD's does.

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
    "refused: tl-absent-pkg — not found: not in http://127.0.0.1:41733/simple (HTTP 404)",
    "ok: six 1.17.0, released 2024-12-04 17:35 UTC — http://127.0.0.1:41733/simple",
    "nothing was downloaded: pip install tl-absent-pkg six was not run",
    "proceeding runs: pip install tl-absent-pkg six; the override is recorded in this session"
  ],
  "confirm": "package-guard --yes -- pip install tl-absent-pkg six"
}
```

**One plan line per package, in the command's order.** Each begins with its result word:
- `ok: NAME VERSION, released DATE — REGISTRY` (plus `(also on …)` when another index has it);
- `pinned: NAME — pinned in LOCKFILE; no registry was asked`;
- `unchecked: NAME — …`, for a local path, `--no-index`, or a project bin already installed;
- `refused: NAME — WORD: DETAIL`, where WORD and DETAIL are one of:
  - `not found: not in REGISTRY (HTTP 404)`;
  - `too new: newest release V was released DATE (N days ago); the minimum age is M days
    (TIMELIKE_PACKAGE_MIN_AGE_DAYS); the newest release old enough is V2, released DATE2: pin it as NAME==V2`;
  - `registry unreachable: REGISTRY unreachable from this container: timed out after 10 s
    (TIMELIKE_PACKAGE_TIMEOUT)` (or `HTTP 503`, `connection refused`, `denied: HTTP 403 …`, …);
  - `age unknown: REGISTRY gives no release date for V (no upload-time): age unknown`;
  - `no matching release: no release matches SPEC in REGISTRY`;
  - `unchecked source: a URL or VCS reference, which no registry vouches for`;
  - `unreadable: …` (the command, a requirements file, a manifest, or a version that does not parse).

**Then two closing lines:** what was not run, and what proceeding runs.

## Verdicts

| Case | Verdict |
|---|---|
| Passed | `N packages checked (P pinned, no lookup) against REGISTRY…; CMD exited E`; when `run` ended CMD (a timeout, memory, disk), `— run: <run's own verdict>` follows |
| Installs nothing | `not an install: ran CMD unchecked; CMD exited E` |
| Proceeded with `--yes` over a refusal | `proceeded over K refusals (recorded: PATH); CMD exited E` |
| `--dry-run`, would pass | `would proceed: N packages checked` |
| `--dry-run`, would refuse | `would be refused: K of N packages` |
| `--gate`, passes | `gate passed: N packages checked …; NAME runs next` (exit 0; the shim drops it) |
| `--gate`, installs nothing | `gate passed: NAME runs unchecked` (exit 0) |

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
| `TIMELIKE_SHIMS` | `/opt/timelike/shims` | The shims' directory, also removed from PATH when CMD is resolved |

## The override record (`<session scratch>/package-guard/override-<UTC>-<pid>.json`)

```json
{"v": 1, "time": "…Z", "session": "…", "agent": "…", "cwd": "…", "command": ["pip", "install", "x"],
 "overridden": [{"package": "x", "ecosystem": "pypi", "registry": "…", "reason": "absent", "detail": "…"}],
 "command_exit": 0}
```

Written before CMD runs (`command_exit: null`), then rewritten with the exit. The tool's event has
`ref: {"log": <this path>}`.

## The override in the session event line (Item 24 Q4; 001's `event.schema.json`, optional `override`)

```json
{"v": 1, "tool": "package-guard", "args": ["--yes", "--", "pip", "install", "x"], "exit": 0, …,
 "ref": {"log": "<the record above>"},
 "override": {"ecosystem": "pypi", "command": ["pip", "install", "x"],
              "packages": [{"name": "x", "registry": "https://pypi.org/simple", "reason": "too-new",
                            "released": "2026-10-11T09:12:00Z", "detail": "newest release 1.1.0 was released …"}]}}
```

`packages[].version` is the version or range the command named, when it named one. `reason` is the refusal's word
(`absent`, `too-new`, `unreachable`, `age-unknown`, `no-match`, `unchecked-source`, `unreadable`); `released` is
present for a dated release. Credentials in a URL are redacted. Only a call that proceeded over a refusal carries
it.
