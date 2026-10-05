---
parent_branch: master
feature_number: "010"
status: In Progress
created_at: 2026-10-05T08:57:05+00:00
source_prompt: plan/.discover/prompts/09-services-interactive.md
source_send: bridge/sends/09-rev1-20261004-183704.md
prompt_revision: 1
discovery_revision: 12
audited_against: [1]
slice: 1
---

# Feature: Services (prompt 09, slice 1: natural)

## Overview

An agent that starts a dev server today runs `npm run dev &` and then:
- guesses when it is ready;
- reads "exit 0" from a server that crashed (gemini-cli #17900, "hallucinated success");
- leaves orphans behind it (claude-code #43944, #80885).

`services` gives the agent's own long-running processes a lifecycle that always concludes (P2):
- `services start NAME --port N -- CMD…` returns **once the port accepts connections**, or once the
  process has died (with its last log lines), or at its time limit;
- `services stop NAME` ends **every process of its tree** and checks that none remains;
- `services list` shows each one's state, port and uptime, and marks the dead;
- `services logs NAME` shows the tail of its log.

There is no daemon. A file registry records what was started (discovery's Assumed Constraints).

**Built under discovery revision 13's rulings** (code-track § Resume after pause-06). The send's seam 1 is
answered there, so this cycle does not pause on it.

**Interactive sessions and the slot allocator are slice 2**, and are not built here.

## The three seams (send), decided

1. **Rules 8 and 9 for services** (revision 13, Q2):
   - **`start` is not confirmed.** It is scoped to the named service, creates a process inside the
     container, and `stop` reverses it.
   - **`stop` of one of this session's services is not confirmed.** It carries `--dry-run`: rule 8,
     since it kills processes, and the dry run lists them. Its verdict names the command that starts the
     service again, so it is reversible from what the tool shows.
   - **`stop` of another session's service, or `stop --all`, is confirmed** (cases 2 and 1). Without
     `--yes` it exits 4 with the confirmation envelope.
   - So the tool declares `mutating: true`, `confirm_protocol: true` (some of its changes honour `--yes`)
     and `destructive: true` (`--dry-run`). That shape passes conform's C2 checks.
2. **The registry is a file** in the session scratch: `<scratch>/<session>/services/registry.json`, with
   one log per service beside it. The per-workspace state root is 07 slice 1's, and it is held.
   - **A service outliving its session's records is unlisted.** That is said, not silent: `start`'s
     verdict says where the service is registered, and that the scratch is disposable.
   - `list` names every running process that carries a service marker but has no registry entry, as
     **unlisted**, with its pid and the name it was started under.
3. **Ports and P4:** a service listening inside the container is confined and needs no grant. Readiness
   connects to the loopback address. Anything reaching outside is out of scope here.

## User Scenarios

### Actors
- **Agent** (primary): starts, checks, reads and stops its own services.
- **Peer agents** (concurrent): each sees the port holders of the others, and cannot stop another's
  service without confirming.

### Scenario 1: a dev server comes up (SC-1, D18)
`services start web --port 8000 -- python3 -m http.server 8000` returns when 127.0.0.1:8000 accepts a
connection. The verdict names the name, the process id, the port and the log path. Exit 0.

### Scenario 2: it dies first (SC-2)
`services start bad --port 8001 -- sh -c 'echo boom >&2; exit 3'` returns non-zero, with a verdict saying
the service died (exit 3) before it was ready, followed by the last log lines (`boom`).

### Scenario 3: the port is taken (SC-3)
- **By a registered service:** with `web` running on 8000, `services start web2 --port 8000 -- …` is
  refused before anything starts. The verdict names the holder: service `web` in session S, pid P.
- **By an unregistered process:** refused too, naming that process when it can be found.

### Scenario 4: stop (SC-4, D18)
`services stop web` ends the service's tree, the server and anything it spawned, and checks that none of
it remains. Exit 0. The verdict lists what was stopped and the command that starts it again.

### Scenario 5: list (SC-5)
`services list` shows `web running 8000 up 2m14s pid 1234` and `bad died … exit 3`. A service whose
processes have all gone since it was started is marked **died**.

### Edge cases
- **The name is already running:** refused, naming its pid. Stop it first, or use another name.
- **No `--port`:** started, and ready as soon as the process is alive after a settle (`--ready none`).
  The verdict says readiness was not checked. A log-pattern condition, `--ready-log REGEX`, waits for that
  line in the log.
- **Not ready within `--timeout` (default 60 s):** exit 124. The verdict names the condition that was not
  met and the last log lines. **The service is stopped**, because a start that does not conclude in
  readiness leaves nothing running; `--keep` leaves it running and registered.
- **A command that is not found, or not executable:** refused (exit 1), with the cause named (`not
  found`, `not executable`) and nothing registered. `services` is not a pass-through tool: its exits are
  its own outcomes.
- **A process that escapes its group** (`setsid`, daemonising): found by its inherited marker and by its
  hold on the log, as `run` finds its tree (003).
- **A process that clears its environment and closes the log:** cannot be found. Stop names any
  survivor it can still see, and says how many it could not prove gone.
- **Stopping a service that already died:** exit 0. The verdict says it had already ended, and the entry
  is removed.
- **`--dry-run` on stop:** lists the processes that would be signalled, and changes nothing.

## Functional Requirements

### Start
- **FR-1** `services start NAME [--port N] [--ready-log REGEX] [--timeout S] [--keep] [--cwd DIR] -- CMD…`
  starts CMD:
  - in a new session (process group), with stdin closed (`/dev/null`);
  - with stdout and stderr appended to `<scratch>/<session>/services/NAME.log`;
  - with an inherited marker variable `TIMELIKE_SERVICE=<session>/<NAME>/<instance>`, where `instance` is
    a random id unique to this start.
- **FR-2** It then waits for readiness:
  - **`--port N`:** a TCP connect to 127.0.0.1:N (and ::1 when 127.0.0.1 refuses) succeeds;
  - **`--ready-log REGEX`:** a line of the log matches;
  - **neither:** the process is alive after 0.5 s.

  It concludes with one of:
  - **ready**: exit 0;
  - **died**: exit 1, with the exit status (or signal) and the last 20 log lines;
  - **not ready in time**: exit 124, with the last 20 log lines, the service stopped unless `--keep`;
  - **refused**: exit 1, with nothing started.

  It never reports success for a process that has exited (P2).
- **FR-3** **Port holders:** before starting, `--port N` is checked against every registry the caller can
  read under the scratch root, and against a listening socket on N:
  - held by a registered, live service: refused, naming its name, session and pid;
  - held by another process: refused, naming its pid and command when `/proc` shows them.
- **FR-4** **Names:** `^[A-Za-z0-9._-]{1,64}$`. A name already registered as live in this session is
  refused, naming its pid.

### Stop
- **FR-5** `services stop NAME` (this session) stops the service's tree:
  - **the tree** is every process carrying its marker, plus every process holding its log open for
    writing, plus its process group;
  - **SIGTERM**, then a 2 s grace, then a freeze-and-SIGKILL sweep, as `run` stops its tree (003, R4);
  - **then it re-scans.** It exits 0 only when nothing remains; otherwise exit 1, naming the survivors.

  The verdict lists the pids stopped and the command that starts the service again. The registry entry
  is removed.
- **FR-6** `--dry-run` lists the processes that would be signalled, and changes nothing.
- **FR-7** **Confirmation (rule 9, revision 13).** These need `--yes`; without it, exit 4 and the
  confirmation envelope, whose `confirm` is the same command plus `--yes`:
  - `services stop NAME --session S` (another session's service);
  - `services stop --all` (every service of this session).

### List and logs
- **FR-8** `services list` shows, for each registered service of this session (`--all-sessions`: every
  readable session):
  - its name, state, port, pid and uptime;
  - its command and its log path.

  **States:**
  - `running`: a marker process is alive;
  - `died`: none is; the exit status when known, otherwise `exit unknown`;
  - **`unlisted`** entries: marker processes whose registry entry is absent (seam 2).

  JSON carries the same as data.
- **FR-9** `services logs NAME [-n N]` prints the last N lines of the log (default 50), bounded by rule 3,
  with the full log as the full output.

### Contract
- **FR-10** **The name is `services`.** It does not shadow the init system's `service`, which is not the
  agent's. A `type -a` cell checks that the image has no other `services`. The manifest:
  `mutating: true`, `confirm_protocol: true`, `destructive: true`, `dry_run: true`, `reads_stdin: false`,
  `probe: ["list"]`.
- **FR-11** Exit codes:
  - `0`: ok;
  - `1`: died, refused, or survivors;
  - `2`: usage;
  - `3`: no such service;
  - `4`: confirmation required;
  - `124`: not ready in time.

  A command that cannot start is exit 1, with the cause named.

  One session event per call, and the event's `ref` is the log path (009's `event_ref`).

## Success Criteria

The criterion text is the send's, copied exactly. Each automated criterion is one e2e file in the image,
under `bash -c` and `bash -lc`. A claim is checked against the state it claims (P004): the port answering,
the process tree gone in `/proc`, never the verdict alone.

- **SC-1** "Starting a service with a port readiness condition returns only after the port accepts
  connections, with a verdict naming the name, process ID, port and log path".
- **SC-2** "Starting a service that exits before becoming ready returns non-zero with a verdict saying it
  died and its last log lines".
- **SC-3** "Starting a service on a port already in use by another registered service is refused, naming
  the holder".
- **SC-4** "Stopping a service terminates every process in its tree, and no process from it remains
  afterwards". The tree includes a grandchild that daemonised (`setsid`).
- **SC-5** "Listing services shows each registered service's state, port and uptime, and marks ones whose
  process has died".
- **SC-6** "DEMO: the Agent starts a dev server, receives a ready verdict naming its port, stops it, and no
  process from it remains" (D18). Manual, after the lane.

## Key Entities

- **Service entry:** name, session, instance, command, cwd, port, ready condition, pid, pgid, log,
  started_at, and the exit status when known.
- **Registry:** this session's entries, one JSON file, written atomically.
- **Marker:** `TIMELIKE_SERVICE=<session>/<name>/<instance>`, inherited by every process of the service.

## Decisions

| Point | Decision |
|---|---|
| Seam 1 | `start` and own `stop` not confirmed; another session's or `--all` confirmed; `--dry-run` on stop (revision 13) |
| Seam 2 | Registry and logs in the session scratch; unlisted marker processes named by `list` |
| Seam 3 | Loopback readiness only; nothing reaches outside |
| Tree | Marker ∪ log writers ∪ process group; `run`'s stop sweep, shared |
| Not ready | Exit 124 and the service stopped, unless `--keep` |
| Name | `services` |

## Out of scope (slice 1)

- Interactive sessions and the slot allocator (slice 2).
- URL readiness (a port and a log line cover slice 1).
- Restarts and supervision (no daemon).
- A registry that outlives the scratch (07 slice 1's state root).

## Assumptions

- `/proc` is readable for the agent's own processes, which is the image's normal case.
- A service's processes keep the inherited environment, or hold its log, or stay in its process group.
  Each is enough for them to be found.
