# Research — 010 Services (prompt 09, slice 1)

Each entry gives the decision, the rationale and the alternatives. Everything was measured on the host
(Python 3.12, bash 5.2) unless it says otherwise. The image decides in the lane.

## R1 · Finding a service's tree after the starter has exited (spec FR-5; SC-4)

**The problem.** `run` keeps its command's tree visible by staying alive as a child subreaper (003, R3).
`services start` returns once the service is ready, so the tree outlives it. Orphans are re-parented to
the container's pid 1, and parentage no longer leads back.

**Decision: three nets, merged:**
1. **An inherited environment marker,** `TIMELIKE_SERVICE=<session>/<name>/<instance>`, matched as an
   exact `KEY=VALUE` entry of `/proc/<pid>/environ`.
2. **The log's writers.** The processes holding `<name>.log` open for writing, found with `run`'s own
   `log_writers`.
3. **The process group** recorded at start.

**Measured:** a tree of `sh -c "setsid sh -c 'sleep 300' & python3 -m http.server … & wait"`.
- The marker found all four processes: the shell, the server, and the `setsid` escapee with its child,
  in their own session and group.
- One scan took 1.0 ms over the namespace's 33 processes.
- The port answered within a second.

**Limits, stated:** a process that clears its environment, closes the log and leaves the group cannot be
found by any net. Stop reports what it could not prove gone (spec edge cases).

**Alternatives considered:**
- **A cgroup per service:** the agent cannot create cgroups in the image (no delegation).
- **Staying alive as a subreaper:** that is a supervisor daemon, which discovery's Assumed Constraints
  exclude.

## R2 · Stopping (FR-5): `run`'s sweep, with the services member set

**Decision.** The sweep is `run`'s (003, R4):
- SIGTERM;
- a 2 s grace;
- then freeze (SIGSTOP the newcomers until a scan finds none), SIGKILL and SIGCONT;
- then re-scan for 3 s.

Its member function is R1's union. `run`'s low-level helpers (`proc_table`, `parse_stat`, `log_writers`,
`signal_all`, `reap`) are loaded from the file beside `services`, as `undo` loads `snapshot` and `view`
loads `search`. One implementation; `run` is unchanged.

Zombies (state `Z`) count as gone.

## R3 · Readiness (FR-2)

- **Port:** `socket.create_connection(("127.0.0.1", N), 0.2)`, then `::1` when the first is refused,
  polled every 50 ms.
- **Log:** the log's new bytes since start, scanned for the regex as lines complete.
- **Neither:** alive after 0.5 s.
- **Death:** `Popen.poll()` between polls. The starter is still the parent while it waits, so the exit
  status is known: `exit N` or `signal NAME`.
- **The last log lines:** the tail of the log (20 lines), with rule 15's redaction applied, as `run`
  applies it.
- **Time limit:** `--timeout S`, default 60 s. Past it, exit 124, the condition named, the tail shown,
  and the service stopped by R2 unless `--keep`.

## R4 · Port holders (FR-3)

**Two sources, both read-only:**
1. **Every registry under the scratch root the caller can read.** An entry holds the port when its
   marker processes are alive.
2. **`/proc/net/tcp` and `tcp6`** for a socket in state `0A` (LISTEN) on port N. Its inode is matched to
   a pid through `/proc/<pid>/fd` (own processes only), and the holder is named by pid and command when
   found, otherwise as "a process the agent cannot see".

**A registered holder is named as `service <name> in session <s>, pid <p>`.** That is the criterion's
"naming the holder".

## R5 · The registry (FR-8; seam 2)

- **Path:** `<scratch>/<session>/services/registry.json` (0600), with the logs beside it.
- **Writes:** read-modify-write under `fcntl.flock` on a lock file beside it, then a temp-and-rename, so
  concurrent starts in one session never lose an entry.
- **A died entry** stays until it is stopped (removed) or started again under the same name (replaced),
  so `list` can mark it.
- **Unlisted:** `list` also scans for marker processes whose `<session>/<name>/<instance>` matches no
  entry, and names them as unlisted. That is the seam-2 case, a scratch cleared under a running
  service.

## R6 · Name and image

- **The name:** `tools/bin/services`, copied by `COPY tools/bin/`. Debian's `service` (init-system-helpers)
  manages the init system's services, not the agent's.
- **The `type -a` cell** checks that `services` names only `/opt/timelike/bin/services`.
- **The image:** no package added, so `make scan`'s inputs change only by the file. The announcement
  (007) lists it automatically.

## R7 · Contract shape (revision 13)

The manifest is `mutating: true`, `confirm_protocol: true`, `destructive: true` (so `dry_run: true`) and
`envelopes: ["confirmation_required"]`.

**Which calls are confirmed:**
- **Not confirmed:** `start`, and `stop` of this session's service.
- **Confirmed:** `stop --session S` and `stop --all`. Without `--yes`, they exit 4 with
  `agentio.confirm_required` (the plan lists the services and pids).

**Probe:** `list`, which is read-only and has an empty registry by default.

## R8 · Tests

**Units:** `tests/unit/test_services.py`. Every fixture is a real process: `python3 -m http.server` on a
free port, `sh -c` trees with a `setsid` grandchild, and commands that exit early. They cover:
- start and ready by port, by log line, and by neither;
- died before ready;
- the timeout, with and without `--keep`;
- port holders, both registered and unregistered;
- a duplicate name;
- stop: the whole tree gone, checked in `/proc` by the test itself;
- `--dry-run`;
- confirmation for another session and for `--all`;
- list: running, died, unlisted, and uptime;
- logs;
- the registry under concurrent starts;
- the manifest.

**e2e:** one bats file per criterion, `bash -c` and `bash -lc`, each cell with its own session and its own
free port. Every claim is checked against `/proc` and the port in the container, never against the
verdict alone. Plus the `type -a` and manifest cells.
