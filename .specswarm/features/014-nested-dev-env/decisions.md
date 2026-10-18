# Decisions Log — Feature 014
> Generated at 2026-10-17T04:02:13Z (read from the clock)
> Spec: .specswarm/features/014-nested-dev-env/spec.md

## Decision Key

| Tag | Meaning |
|-----|---------|
| ASSUMED | Assumption made without explicit spec guidance (confidence: high/medium/low) |
| DEFERRED | Decision postponed — noted for later resolution |
| FLAGGED | Judgment call between alternatives — requires review |
| ABSENT | What was NOT done and why — forced reflection on gaps |
| INHERITED | Assumption carried forward from a prior task's output |

---

### T001: Adele's image gains the Compose CLI, refused unless static
**Started:** 2026-10-17T04:02:13Z | **Completed:** 2026-10-17T04:06:16Z

INHERITED: (none — first task)
ASSUMED: the plugin binary sits at /usr/local/libexec/docker/cli-plugins/docker-compose in docker:29.9.0-cli, and `go version -m` reads its build info though it is stripped — not checked here (no Docker); a wrong path fails the build loudly at COPY (confidence: medium)
ASSUMED: the binary runs standalone as docker-compose (compose v2's standalone mode), so neither the docker CLI nor buildx is copied (confidence: medium)
FLAGGED: DOCKER_CLI_IMAGE is passed to the stand-in's build too, though its stage does not use the binary — an unused FROM with an empty ARG can fail the whole Dockerfile's parse; chose passing it over a second Dockerfile (confidence: high)
ABSENT: whether the binary is static is not known until the lane builds it; the cycle report's not_verified carries it (Item 27's answer)
ABSENT: the scan's view of the binary's Go modules (it joins Adele's image scan) is the lane's, not this session's
SCOPE: in (2 changed files)

### T002: The launcher scripts/workspace.sh
**Started:** 2026-10-17T04:03:30Z | **Completed:** 2026-10-17T04:06:16Z

INHERITED: none
ASSUMED: the workspace parent is never written into the repository (deny-list P3 matches its absolute path); it comes from TIMELIKE_WORKSPACES in the environment or the git-ignored local.env, and its absence is a refusal naming the variable (confidence: high)
FLAGGED: "enforced" is checked as "the workspace (or its parent) is not inside a git work tree", read with the host's own git, rather than by scanning for .git directories — git's own answer is the one the boundary is about (confidence: high)
FLAGGED: a launch with no git on the host proceeds and says the check was not made, rather than refusing — nothing on such a host runs the agent's hooks (confidence: medium)
ABSENT: old per-launch workspaces are not pruned; each make up makes a new one. Removing them is the operator's
ABSENT: shellcheck did not run here (not installed on this host); make lint runs it in the lane
SCOPE: in (3 changed files)

### T003: docker.compose in the known capabilities; LiveOf, LiveResource, LiveRows
**Started:** 2026-10-17T04:07:10Z | **Completed:** 2026-10-17T04:14:01Z

INHERITED: 12's ledger schema and its "unended" condition (performed with no reaped or gone row) — from 004 (confidence: high)
FLAGGED: instances counts per grant AND capability (LiveOf), not per grant as 12's Live does — a stand-in box and an environment are different resources, and a grant allowing both would otherwise share one count; Live is left as it is, so 12's status and grants are unchanged (confidence: medium)
ASSUMED: "Adele knows: standin.box, docker.compose" replaces "slice 0 knows one: standin.box" in two messages; no test pins either text (grep) (confidence: high)
ABSENT: no new ledger outcome: down's ending is a "reaped" row with its cause, so 12's Live, Due and status read it unchanged
SCOPE: in

### T004: the Engine API client
**Started:** 2026-10-17T04:14:01Z | **Completed:** 2026-10-17T04:14:01Z

INHERITED: none
ASSUMED: the unversioned API path (the daemon's current version) — the pin is the operator's daemon, not a client SDK (confidence: medium)
FLAGGED: down is Adele's own, over the API, by timelike's label, not compose's `down`: compose's down acts on com.docker.compose.project, which an object timelike did not create could carry; the label is the host's rule (confidence: high)
ABSENT: no unit drives the client against a daemon (tech-stack: Adele's Docker calls are never mocked to reach coverage); only Demux is unit-tested, and the lane's e2e cells are its test
SCOPE: in

### T005: the compose model package
**Started:** 2026-10-17T04:14:01Z | **Completed:** 2026-10-17T04:14:01Z

INHERITED: Item 27 Q1's refusal list, accepted for slice 0
FLAGGED: container_name is refused (a name outside the project's could collide with, or be confused for, a container that is not timelike's); not on Item 27's list, a neighbour of it (confidence: medium)
FLAGGED: any security_opt but no-new-privileges is refused, not only the unconfined forms — a label=disable or an apparmor profile name is a choice Adele cannot judge (confidence: medium)
ASSUMED: compose config's JSON shapes (long-form volumes, ports with target/published, expose as strings, top-level env_file kept per service) as compose-go v2 prints them; not checked against the pinned binary here (no Docker). A shape that differs fails a cell, not open (confidence: medium)
ABSENT: sysctls, ulimits, extra_hosts, dns and user are allowed: none reaches outside the container without the refused settings
SCOPE: in

### T006: adeled resolve, the sandbox's entrypoint
**Started:** 2026-10-17T04:14:01Z | **Completed:** 2026-10-17T04:14:01Z

INHERITED: T005's BindSources, Unset, Outside
ASSUMED: compose's error for an absent env_file, include or extends names the absolute path (R2); the setting is read from the error's words. A wording that names none falls to exit 1 with compose's text, never to a pass (confidence: medium)
ABSENT: the resolve command never runs in Adele's own container, but nothing stops the operator running it there; it reads only what it is given
SCOPE: in

### T007: compose.yaml and make up
**Started:** 2026-10-17T04:15:25Z | **Completed:** 2026-10-17T04:15:25Z

INHERITED: T002's launcher output (now printf %q, so a path with a space survives eval)
FLAGGED: without TIMELIKE_WORKSPACE the agent's second mount is an empty named volume at /opt/timelike/no-workspace, not a failure — every compose command (exec, down) interpolates the whole file, so a strict ${VAR:?} would break them (lore docker-compose Q002); the named volume keeps a valid file and creates nothing on the host (a bind of a missing path would be created as root) (confidence: medium)
ASSUMED: the socket's group is read by make from the socket (stat), as tests/run.sh already does for the runner; the default 10001 is Adele's own gid and grants nothing (confidence: high)
ABSENT: timelike-nested's name is fixed (Adele joins services to it by name); two stacks on one daemon would share it — there is one stack per host (container names are fixed already)
ABSENT: files a nested container writes as root into the workspace are root's on the host; the operator removes them with sudo or from a container. Not addressed in slice 0
SCOPE: in

### T008 (Adele's side): docker.compose up, down and /v1/envs
**Started:** 2026-10-17T04:12:40Z | **Completed:** 2026-10-17T04:20:23Z

INHERITED: T004's client, T005's checks and injection, T006's resolve document; 12's choose, effective, refuse and ledger (confidence: high)
FLAGGED: an environment request takes its own lock (Envs.mu) for its whole length and the broker's lock only around grant and ledger calls — holding the broker's lock across a sandbox and a compose up would make every stand-in request wait out a bring-up (12's addendum 1, E, found the reaper doing that) (confidence: high)
FLAGGED: a forbidden setting, an outside file and a missing image answer HTTP 422 with a refusal document, not 403's grant envelope: revision 17 for the first two; Item 29 for the third. Each is a refused ledger row; a setting's extend is empty, an image's is the operator's docker pull (confidence: high for settings, provisional for images)
FLAGGED: up's order is resolve, then the live-row check (unchanged is a no-op read back; changed is 409), then the refusal list, the grant (capability, ttl, ports, instances, budget), the images, the shared network's label, compose up, the ledger row. Nothing is created before the last check; a compose failure is cleaned up by label and the count left is said (confidence: medium)
ASSUMED: the ledger says live and the daemon has nothing labelled: the old row gets a "gone" ending and the up proceeds (an environment removed outside Adele, e.g. by the operator) (confidence: medium)
ASSUMED: up answers once compose's up -d returns; readiness is the client's (R7), so the HTTP write deadline is raised for environment requests only (confidence: high)
ABSENT: a project error (compose cannot resolve it) is HTTP 400, so exit 2 with compose's last lines; it is not recorded in the ledger (nothing was refused by policy)
ABSENT: two containers of one service (scale) are listed as two services of the same name; scale is not considered in slice 0
SCOPE: in

### T016: the reaper's providers by capability
**Started:** 2026-10-17T04:20:23Z | **Completed:** 2026-10-17T04:20:23Z

INHERITED: 12's reaper (same-box check, read-back before and after, lock for the ledger write only)
FLAGGED: the provider names its record, noun and holder (described), so an environment's reap cause says "the daemon's labelled objects"; the stand-in's words are unchanged byte for byte (its unit pins one) (confidence: high)
ASSUMED: an environment's "box" for the same-box check is its labels: created + ttl-seconds equal the performed row's expires_at, both truncated to the second (confidence: high)
ABSENT: collection of environments of ended sessions (slice 1's criterion) is not built
SCOPE: in

### T009: the client, adele env up|status|down
**Started:** 2026-10-17T04:27:14Z | **Completed:** 2026-10-17T04:27:14Z

INHERITED: T008's HTTP answers (200 with services read back, 403 grant envelope, 422 refusal, 409, 404); 12's client (call, unreachable, answered_error, grant_required)
FLAGGED: readiness is the client's: it polls Adele's read-back every 0.5 s and probes each service's ports itself, so "ready" is reached from the agent's container (cross-stack P001) and the bound is the tool the agent ran (P2); a service that exits non-zero concludes at once with exit 1 rather than waiting out the bound (confidence: high)
FLAGGED: the verdict is "up NAME: N ready in T s of W s · read back, ports probed from the agent container · local: no cost · host git X", with the grant and expiry on the first body line, so a lane's names fit rule 13's 200 columns (the first draft was cut) (confidence: high)
FLAGGED: a forbidden setting raises agentio's usage error: "error: <setting> is not allowed (code 2) — no grant allows it; <change> (service S: value)", with nothing on stdout, as revision 17 words it; a missing image raises exit 3 naming the operator's docker pull (Item 29, provisional) (confidence: high; medium for the image)
ASSUMED: the default name is computed by the client from the project's realpath (tl-<slug>-<sha6>), and Adele's Go DefaultName is pinned to the same value by both units (confidence: high)
ABSENT: `adele env exec` (running a command in a service) is not built: the agent reaches services by address; slice 1's devcontainer criterion is where a command inside one is asked for
ABSENT: status's denial line now prints "operator's command: none" for a refusal without one (both 12's client and adeled status); no existing test pinned the empty case
SCOPE: in

### T010-T015, T017, T018: the lane, the criterion files, the launcher's units, 004's assertions
**Started:** 2026-10-17T04:34:19Z | **Completed:** 2026-10-17T04:34:19Z

INHERITED: T007's compose variables; T009's verdict and error texts, which the cells pin
FLAGGED: the lane's up step runs the launcher, so a lane without TIMELIKE_WORKSPACES fails at up, naming the variable, rather than skipping feature 13's cells — a skipped cell would read as a pass. The mentor's lane must set it (environment or local.env) (confidence: high)
FLAGGED: the lane sweeps leftover nested environments and sandboxes by timelike's labels before compose down, because a container still joined to timelike-nested would stop compose removing the network; it removes nothing unlabelled (confidence: high)
FLAGGED: the operator's git is a throwaway of DOCKER_CLI_IMAGE (alpine, carries git, already pinned and pulled for the runner's build), run as the runner's uid with the workspace at the same path — the runner image itself has no git known to this session; the first cell fails naming it if git is absent (confidence: medium)
FLAGGED: 004's isolation test now allows exactly two agent mounts, the state volume and the workspace bind at the same path, and still refuses anything of Adele's or the socket; the network test adds timelike-nested and requires it internal. Loosened only by what feature 13 adds (confidence: high)
ASSUMED: compose's default health with one failed check and retries 1 reads "unhealthy" while the container runs; the never-ready cell pins "stuck  running (unhealthy)" (confidence: medium)
ASSUMED: alpine's git (2.45.1 or later) needs safe.directory for a repository owned by uid 1000; the cells pass it per command, as the README tells the operator (confidence: high)
ABSENT: no cell builds an image (builds are refused, Item 28) and no cell publishes a host port (ports = none in every lane grant); a ports refusal is 12's tested path, through checkStatic
ABSENT: the e2e files were not run here (no Docker); shellcheck passes on each, and every helper they call exists
SCOPE: in

### T019: README, the example grants, where agents look
**Started:** 2026-10-17T04:38:07Z | **Completed:** 2026-10-17T04:38:07Z

INHERITED: the send's README status block (applied: all five slice-0 Automated criteria are built, as e2e files not yet run in a lane)
FLAGGED: the previous update's marks are cleared (it was pushed, v0.21.0) except the Next line's, which the send says to leave as it is; that mark is the mentor's to move at sign-off (confidence: medium)
FLAGGED: two passages the build made false are corrected in the same cycle, marked: Install's "the agent container mounts nothing" (now its workspace, with TIMELIKE_WORKSPACES) and Adele's paragraph (she now holds the socket) (confidence: high)
FLAGGED: P3 — a `docker` and `docker-compose` answer in missing-commands.tsv points at `adele env up`, and the announcement gains one line, because the agent's habit is `docker compose up` and there is no docker here (confidence: medium; beyond the send's list, inside 04's mechanism, each tested by 04's own units)
ASSUMED: the help stays within 40 lines with the env options (31 lines in the regenerated reference) (confidence: high)
ABSENT: the What row's "What it does" is unchanged, as the send allows
SCOPE: out — image/rootfs/etc/timelike/missing-commands.tsv, tools/bin/timelike (2 of 6 changed files) (task has FLAGGED: yes)

### T020 (part): the host lanes, two units of other features, the lane's non-unix daemon
**Started:** 2026-10-17T04:38:38Z | **Completed:** 2026-10-17T05:02:21Z

INHERITED: every earlier task's code
FLAGGED: the first serial host lane failed 11 units: 10 of maint-lane-speed's test_lane_run_sh (its scratch lane had no scripts/workspace.sh and no workspace parent) and 005's test_state_root_image (it pinned the agent's one mount). The harness now copies the launcher and sets TIMELIKE_WORKSPACES; 005's unit allows exactly the workspace's second mount and still refuses Adele's and the socket. Two new lane units: the runner gets the workspace at the same path and DOCKER_CLI_IMAGE, the sweep runs before compose down, and a lane without the parent fails at up naming it (confidence: high)
FLAGGED: a DOCKER_HOST that is not a unix socket gives Adele no socket and says so, rather than failing the up step at stat — the lane's units run that way; on such a daemon feature 13's cells would fail naming "no Docker daemon" (confidence: medium)
ASSUMED: pytest-xdist 3.8.0 and execnet 2.1.2, as pins.env names them, were installed into this session's scratch venv for the -n 8 run; nothing in the repository changed for it (confidence: high)
ABSENT: the Docker lane, the scan and make lint did not run (no Docker in this session); the e2e cells have never run
SCOPE: in

## Cycle 2 — lane 13s0a (`../bridge/feedback/13-20261017-063803-lane-13s0a-fails.md`)

### T021–T025: lane 13s0a's findings A, B, C and E; Item 29
**Started:** not read from the clock; the cycle's first reading was 2026-10-17T10:06:50Z, after A–E's code was written | **Completed:** 2026-10-17T10:08:13Z

INHERITED: Cycle 1's code at `e5a58af`; the lane's logs under `../bridge/`
FLAGGED: A — Envs' lock was held for a whole request, the sandbox included, so in a parallel lane every bring-up and every one of the 26 forbidden-setting cells queued behind each other; the agent's 120 s counted that queue. The sandbox and the setting check now take no lock. Chose this over moving the bring-up files into lane.conf's serial class, because the product must answer concurrent requests and a class would hide the queue rather than remove it (confidence: medium — not run against a daemon here)
FLAGGED: A — the bound stays counted from the agent's side: it is what the agent waits for. A request given up before Adele creates anything stops; once she creates, she finishes and records it (the context is detached), so an environment is never half-made and unrecorded; the client's remediation says so. Chose this over cancelling compose midway, which can leave objects the daemon finishes creating after compose is killed (the likeliest cause of "left 3 0 1") (confidence: medium)
FLAGGED: A — why the sandbox was slow is not established. compose config inside it is bounded at 45 s and would have printed its own error, so cell 155's 90 s was spent in the daemon's create, start, wait or logs, under the lane's load. The sandbox's phases are now measured and reported in up's data, and the bring-up JSON cell prints them, measured and not asserted, so the next lane says which (confidence: high for the 45 s argument; the phase is unknown)
FLAGGED: B — the cause is not established. 153 reached compose up through the same MkdirTemp in the parallel phase; 701–703 failed in the serial phase after 595 stops and starts Adele. Rather than depend on /tmp's state after a restart, the scratch is under her state directory, which the ledger writes (confidence: high for the fix, low for the cause)
FLAGGED: C — the stand-in models a current git (2.54, from the pinned CLI image), not the host's 2.43: it is the git the README tells the operator to expect, and the stricter one. safe.directory names exactly the agent's repository, its work tree and its .git (what git 2.54 asked for). 605's failure was the operator's own write into a 0755 directory the agent made, not the hook's marker; both are addressed: the directory is 2775 and the hooks announce themselves on stderr (confidence: high)
FLAGGED: C — the operator's git image is built by the runner step (`--target operator-git`), not pulled by a cell (confidence: high)
FLAGGED: E — no newer Compose release exists (v5.6.0 is the newest, its binary go1.26.8 and x/net v0.58.0), so option (b): built from source in Adele's build stage, sum-checked, x/net raised; the build on this host is static and govulncheck finds no x/net advisory (confidence: medium — the image build and scan are the lane's)
ASSUMED: D — by the parallel plan's order and the cells' durations, 005's cell 69 ran in the lane's first three minutes, before the bring-up files (11th and 12th in the plan) could have started; an estimate from durations, not start times (confidence: low)
ABSENT: no lane.conf class is added for 005's file or for this feature's files; no e2e cell was run here (no Docker); the image's build, the scan and lint did not run here
SCOPE: out — tests/runner/Dockerfile, tests/run.sh, pins.env, README.md (feature-scope files of the lane and the README, named by the feedback) (task has FLAGGED: yes)


## Cycle 3 — lane 13s0b (`../bridge/feedback/13-20261017-153646-lane-13s0b-fails.md`)

### T027–T031: lane 13s0b's findings A–E and the SC-8 volumes
**Started:** 2026-10-18T00:35:03Z (the cycle's first clock reading) | **Completed:** 2026-10-18T00:46:57Z (the code; records and host lanes after)

INHERITED: Cycle 2's code at `22c4777`; the lane's logs under `../bridge/`
FLAGGED: A — a create that outlives the sandbox's bound is the daemon's to finish, and Run cannot know whether it will. Run now removes the sandbox by its name once the daemon makes it, trying for `LateRemoval` (10 min), because until a create finishes the daemon answers 404 for the name; an answer with an error status made nothing and starts no removal. serve also sweeps sandboxes older than their bound plus that removal, at start and every 5 minutes, so one left by an Adele that stopped is found. Chose the sweep by the sandbox label over adding sandboxes to the ledger, which records requests, not Adele's own working containers (confidence: medium — not run against a daemon here)
FLAGGED: A — the sandbox is made from Adele's image, `timelike-adele:local`, which `compose up --build` builds; compose labels the images it builds with its project, service and version, and a container inherits its image's labels. The daemon cannot drop an inherited label, so the sandbox overrides each with an empty value, which matches no project and no service. Not inspected here: the mentor can read the image's labels (confidence: medium for the source, high for the override)
FLAGGED: A — the two engine units drive Run and the sweep against a fake daemon on a unix socket. tech-stack.md forbids mocking Adele's Docker calls to reach coverage; these units exist because a create that finishes after its bound cannot be produced on demand from a real daemon, and they cover the order of calls, not the filter. The real path stays the lane's (confidence: medium)
FLAGGED: A — the 20.6 s lock wait: Envs' lock is held from the live check through compose up to the ledger write, for every name, so a bring-up waits for any other bring-up or down in progress, and compose up took about 20 s under the lane's load. The cell's own sandbox took 359 ms. That is the design Cycle 2 kept (two ups never race on one instance count), so no lock change: `lock_held_by` now names the holder, so the next lane says which request it was, rather than an inference (confidence: medium)
FLAGGED: D — modernc's busy_timeout was set (5 s) and transactions began IMMEDIATE, but performed and refused rows were plain autocommit inserts, and under the lane's load one writer can lose the lock to a busier one for longer than the timeout. Every write is now one IMMEDIATE transaction, tried again while busy up to `WriteWait` (60 s). The test that failed was not reproduced here under a CPU load (15 runs passed); the new unit holds the lock for 12 busy timeouts and fails without the retry (confidence: medium for the cause, high for the fix's effect)
FLAGGED: C — SC-1's history moves to setup_file, under exec_plain's PLUMBING_TIMEOUT and outside every cell; each cell copies it. Chose this over a faster fixture (fast-import), which would change how the history is made (confidence: high)
ASSUMED: B — the reap file's setup_file throwaway printed nothing for 300 s: the daemon at create under the same load as A. Nothing in this feature's code is on that path (confidence: medium)
ABSENT: no bound moved, no cell's assertion changed, no lane.conf class added, and `LANE_STEPS_TOGETHER`'s default is unchanged (the mentor can run the next lane with it 0; see the report); no e2e cell ran here (no Docker); shellcheck is not on this host
SCOPE: out — tests/run.sh, the SC-1 and SC-8 bats and the SC-1 fixture (other features' lane files, named by the feedback) (task has FLAGGED: yes)


## Cycle 4 — lanes 13s0c and 13s0d (`../bridge/feedback/13-20261018-030300-build-disk-bound-uv-compile-timeout.md`)

### T033–T034: the build on a disk-bound host
**Started:** 2026-10-18T03:20:45Z (the cycle's first clock reading) | **Completed:** 2026-10-18T03:24:19Z (the code; records and host lanes after)

INHERITED: Cycle 3's code at `a8b0d7b`; the mentor's reading of the host's disk in the feedback
FLAGGED: both levers. uv's compile bound goes from its 60 s default to 300 s at all four compile sites, the bench's two included: benchimg runs beside e2e, on the same disk. 300 s is five times the default; the failure is a worker that did not answer within 60 s while the disk's average wait was 65–138 ms, and a broken interpreter fails at once rather than at the bound, so only a compile that stops answering waits it out. Chose a fixed value inline over a pin or a build arg: it is plumbing, not a version (confidence: medium — the value is a judgment, not a measurement)
FLAGGED: uv ignores a variable it does not read, so a raised bound the pinned uv does not know would change nothing and say nothing. Each compile first checks that the uv binary carries the variable's name, and the build stops with a remedy if it does not. Not run here: the check's first run is the lane's build (confidence: medium)
FLAGGED: the agent image's two standard-library compiles ran at once because BuildKit builds the runtimes stage beside the final stage. The final stage's compile now bind-mounts the runtimes stage's /opt, which makes it wait for that stage; nothing is copied, so the image is unchanged. The cost: a change to the runtimes stage now also rebuilds the final stage's interpreter layer (confidence: high)
FLAGGED: `make build` builds `agent`, `adele` and `adele-standin` one after another instead of one `compose build` of all three. The list is checked against compose.yaml's services with a build section by a unit, and adele-standin follows adele so their shared Go stage is a cache hit. The lane's `up --build` still names all of them, after `build` has made each one, so it is a cache hit (confidence: high)
ASSUMED: E2E_JOBS — the default stays 8 (the lane-speed send set it); 13s0e with E2E_JOBS=4 is the recommendation, see the report (confidence: medium)
ABSENT: no image was built here (no Docker), so neither the raised bound, the guard, the mount nor the build's time is measured; no criterion's bound moved; E2E_JOBS' default is unchanged
SCOPE: out — image/Dockerfile, bench/vanilla/Dockerfile, bench/driver/Dockerfile, Makefile, tests/run.sh (the build's files, named by the feedback) (task has FLAGGED: yes)


## Cycle 5 — lane 13s0e (`../bridge/feedback/13-20261018-051500-lane-13s0e-e2e-green-lint-e501.md`)

### T036–T037: lint's E501 and E2E_JOBS' default
**Started:** 2026-10-18T05:14:44Z (the cycle's first clock reading) | **Completed:** 2026-10-18T05:16:03Z (the code; records and host lanes after)

INHERITED: Cycle 4's code at `367bc31`; lane 13s0e's logs under `../bridge/`
ASSUMED: A — the four messages wrapped, no assertion changed; ruff 0.16.7 on this host passes check and format over the lint's paths (the lane pins 0.16.9) (confidence: high)
FLAGGED: B — the default is 4 on the mentor's ruling. The 8 was chosen in the lane-speed maintenance cycle from a schedule estimate (about 752 s at 8 or more, 953 s at 4), not from runs on the Docker host, and that report said the default should move if 8 was flaky. UNIT_JOBS and LANE_STEPS_TOGETHER's defaults are unchanged: the ruling names only E2E_JOBS (confidence: high)
ASSUMED: C — 004's Cycle 4 report named the cause of the same failure in lane 12s1: the fake run's `--call-limit 2`, a hooked commit past 2 s under load counted as a hang, then `--no-verify`. 13s0e's two failures are consistent with it; the log truncates the report, so it does not show the ending (confidence: medium)
ABSENT: C not fixed (the mentor carries it as open item 1); no e2e cell ran here; the lane's pinned ruff 0.16.9 did not run here
SCOPE: out — tests/run.sh, tests/unit/test_lane_run_sh.py (the lane's files, named by the feedback) (task has FLAGGED: yes)


## Cycle 6 — slice 1 (`bridge/sends/13-rev17-20261018-120700.md`; branch `modify/014-slice-1`)

### T039: the ledger's Recorded writer, SessionEnded, live queries need an expiry
**Started:** 2026-10-18T12:23:47Z | **Completed:** 2026-10-18T12:25:00Z

INHERITED: slice 0's ledger at `08df8e2` (schema 2), and the plan's R17 and R19
FLAGGED: an exec and a session end are performed rows (the send: "performed, no undo") with no expiry, so the one condition every live query shares, `unended`, now also requires `expires_at IS NOT NULL`. Chose that over a new outcome (a schema change) or filtering by action in each query (four places to keep in step). Every performed row before slice 1 has an expiry, because Performed requires one (confidence: high)
ASSUMED: a session end is under no grant, and the grant column is NOT NULL, so it records grant `(none)`, which no grant can be named (grant names are lowercase letters, digits and -) (confidence: high)
ABSENT: no schema change and no migration; `adeled ledger` prints a performed row with no expiry by its cause, not with a cost or undo; the JSON form already prints null expiry and undo
SCOPE: out — adele/internal/ledger/recorded_test.go (1 of 4 changed files) (task has FLAGGED: yes)

### T040: the engine's builds, exec, attach, images and agents
**Started:** 2026-10-18T12:25:37Z | **Completed:** 2026-10-18T12:28:54Z

INHERITED: slice 0's engine client (unix socket, label-filtered lists, Run, removeLate) — from T004 and Cycle 3
FLAGGED: the context sandbox's stdout is read from an attached, upgraded stream with the container's log driver set to none, not from its logs as `Run` reads the resolve sandbox's. The json-file driver re-encodes output as JSON strings (binary is mangled) and writes it to the host's disk, which this host can least afford (cross-stack P006) (confidence: high for the reason; the attach over the unix socket is untried against a real daemon)
FLAGGED: builds use the classic builder (`version=1`), the only one the build API offers with a plain tar body and no BuildKit session. It pulls a missing base whatever `pull=0` says, so `Build` cancels the request at the first progress message that is a pull (R15's second guard). The message prefixes are the classic builder's as remembered, not read from a daemon here (confidence: medium)
FLAGGED: the Engine API has no call to stop an exec'd process. Exec's bound ends the call (`TimedOut`), and the caller says the process may still run and that `down` removes the container (confidence: high)
ASSUMED: the requester is the agent-labelled container whose address on a network named `adele-request` (or `*_adele-request`, compose's project prefix) equals the request's peer (confidence: high)
ABSENT: no image is pulled, tagged or removed outside an environment's label; the classic builder's own intermediate containers are left to forcerm; no exec kill; units against the fake daemon only (no Docker here)

### T041: `adele/internal/buildctx/` (delegated)
**Started:** 2026-10-18T12:23:00Z | **Completed:** 2026-10-18T12:28:54Z

INHERITED: plan R14–R16 and data-model § A build, given to a delegate with the exported API fixed
FLAGGED (delegate): mode bits in the header and the digest keep setuid, setgid and sticky as well as the permissions, as the CLI does (confidence: high)
FLAGGED (delegate): WriteTar re-checks each entry's type, mode, link, size and content hash against the walk, so an archive never carries a digest that does not describe it; a file changed between resolve and build fails the build (confidence: high)
FLAGGED (delegate): RUN --mount=from=IMAGE also counts as a base, and Bases lists every stage's images, those after the target included (conservative: a missing one is refused even when the classic builder would not reach it) (confidence: medium)
ASSUMED (delegate): an excluded directory is skipped whole only when no exception could reach below it; otherwise walked, its own entry left out (confidence: medium)
ABSENT: heredocs are not parsed (the classic builder has none); the injected Dockerfile's name is not checked for a collision with a real file; .dockerignore beside a Dockerfile (Dockerfile.dockerignore) is not read
SCOPE (T040–T041, one commit 7739f1a): out — adele/internal/engine/engine_test.go, adele/internal/engine/slice1.go, adele/internal/engine/slice1_test.go (3 of 10 changed files) (task has FLAGGED: yes)

### T042: `adele/internal/devcontainer/` (delegated)
**Started:** 2026-10-18T12:23:00Z | **Completed:** 2026-10-18T12:29:20Z

INHERITED: plan R12–R13, given to a delegate with the exported API fixed
FLAGGED (delegate): Translate returns a refusal as `*RefusalError` wrapping `*compose.Refusal` (which is not an error), rather than a third return value (confidence: high)
FLAGGED (delegate): more than one of image, build and dockerComposeFile is refused, naming the second; a build key other than dockerfile, context, args and target is refused as `build.<key>`; a value of the wrong JSON type is refused, naming its key (confidence: high)
ASSUMED (delegate): `-v NAME:/x` is a named volume, declared at the top level; `-v ./rel:/x` is refused; a relative source in `mounts` is left to compose, which makes it absolute against the project directory, and slice 0's check then judges it (confidence: medium)
ABSENT: the legacy top-level `dockerFile` and `context` keys are refused as unknown, not translated; a compose-form forwardPorts naming a service not in the files is left to compose config's own error
SCOPE: in (3 changed files)

### T043: compose — builds checked, slice 1's labels, one-shots, build keys in the hash
**Started:** 2026-10-18T12:29:44Z | **Completed:** 2026-10-18T12:31:15Z

INHERITED: slice 0's refusal list and Inject (T005, Cycle 1); R16's allowed and refused build keys
FLAGGED: slice 0's `build` refusal (D-7) is lifted. A build is checked by key: context, dockerfile, args, target and labels are brokered; secrets, ssh, entitlements, privileged and additional_contexts are refused under the names the operator's decision gives them ("build secrets", …); a network other than default is "build network"; any other key is refused as `build.<key>`. Chose an allow-list over the decision's refuse-list alone, so a build key compose adds later is refused until someone looks at it (confidence: high)
ASSUMED: compose's config makes a build's context absolute and leaves a relative dockerfile relative to it; Builds joins them (confidence: medium — compose's normalised output is not read here)
ASSUMED: a one-shot for certain is exactly a service another names in depends_on with condition service_completed_successfully, in the resolved model's map form (confidence: high)
ABSENT: Inject's requester is "unknown" until T045/T049 pass the real one; slice 0's broker call keeps compiling with session and grant
SCOPE: in (4 changed files)

### T044: `adeled resolve --devcontainer`, the build scan, `adeled context`
**Started:** 2026-10-18T12:31:38Z | **Completed:** 2026-10-18T12:36:02Z

INHERITED: devcontainer.Translate (T042), buildctx (T041), compose.Builds (T043)
FLAGGED: an oversize context or an unreadable Dockerfile is the resolve document's error (Adele's 400, the client's exit 2 with the remedy), not plan R14's exit 1: it is the request that must change (a .dockerignore), not the capability that failed (confidence: medium)
FLAGGED: the context sandbox writes only the archive to stdout and one JSON line with its digest to stderr, so Adele can tell an archive that is not the one resolve keyed (a file changed between the two sandboxes) and keep no image built from it (confidence: high)
ASSUMED: the devcontainer's generated compose files go in the sandbox's own /tmp (its tmpfs), which compose reads with the project directory the translation names (confidence: high)
ABSENT: the resolve sandbox does not check that a build's bases exist (Adele does, on the daemon); runServices' filter keeps the depends_on closure only
SCOPE: out — adele/cmd/adeled/resolve_slice1_test.go (1 of 4 changed files) (task has FLAGGED: yes)

### T045–T046: the broker's builds, lifecycle commands and exec
**Started:** 2026-10-18T12:36:30Z | **Completed:** 2026-10-18T12:39:45Z

INHERITED: the engine's Build, RunStream, Exec and Agents (T040); the resolve document's builds and devcontainer (T044); Inject's Meta (T043)
FLAGGED: everything a build could be refused for is checked before it builds: the grant's static limits, a live environment of the name with another model (409), and every base image (exit 3). The builds then run before Envs' lock, because they can take minutes and the lock serialises every bring-up; the lock's own checks run again after, and a refusal there (instances, budget, a missing image, the network) removes what this request built (confidence: medium — two ups of one name can both build, and the second is then refused or found unchanged)
FLAGGED: an unchanged build is the image tagged `<env>-<service>:<key[:12]>` carrying that key and the environment's label, which is reused with no build. A context archive whose digest is not the one resolve keyed keeps no image, and the answer is a 409 to bring it up again (confidence: high)
FLAGGED: lifecycle commands run after the environment is recorded and Envs' lock is released, in the primary container, as its remote user, in its workspace folder, with remoteEnv; they stop at the first that fails or passes its 120 s bound. A command that cannot be run at all is reported as exit 126 under the name "lifecycle" (confidence: medium)
FLAGGED: exec picks the named service, else the devcontainer's primary, else the only service, else answers 409 listing the services; a container that is not running is a 502 naming its state; the row records service, user, command (≤ 200 characters) and its end, with the environment's grant (confidence: high)
ASSUMED: the requester is read before the lock, once per up, from the daemon's list of agent-labelled containers by the request's peer address (http.go sets Request.Peer from RemoteAddr; it is `json:"-"`, so the body cannot set it) (confidence: high)
ABSENT: no unit drives the daemon side of a build, a lifecycle command or an exec (tech-stack: Adele's Docker calls are not mocked to reach coverage; the lane's cells do); EnvWriteTimeout is 30 min so the server never cuts a long build, and the agent's --wait concludes it first
SCOPE: out — adele/internal/engine/slice1.go (1 of 6 changed files) (task has FLAGGED: yes)

### T047, T050, T052 (client half): the client's devcontainer choice, exec, collect, session end, readiness per decision C (delegated)
**Started:** 2026-10-18T12:23:00Z | **Completed:** 2026-10-18T12:40:31Z

INHERITED: the contract § Slice 1 and plan R12, R13, R17, R19, R20, given to a delegate
FLAGGED (delegate): exec passes its command's exit status through by setting the tool's `passes_exit` for that verb only, after parsing, which agentio reads in one place (the exit-vocabulary check); declaring it Tool-wide would split every verb's arguments at its first word and make conform wrap a command adele does not run. The tool is declared `takes_command` instead, so `--` splits the command, and `--` on any other verb is a usage error. The manifest therefore understates exec (no passes_exit declared) rather than overstate the tool (confidence: medium)
FLAGGED (delegate): `--timeout` resolves per verb: 100 s for exec (feature 03's run default), 30 s for every other verb, unchanged (confidence: high)
ASSUMED (delegate): "N ready" counts ready and completed services; "running, no readiness check" never counts, and the verdict is slice 0's exactly when nothing is unchecked (confidence: high)
FLAGGED: down's verdict and collect's lines name built images only when there were any, so slice 0's pinned verdict is unchanged (confidence: high)
ABSENT: the README's generated reference is stale until T055 (test_readme_reference fails until then); an up verdict with a long name, "devcontainer," and the unchecked clause can pass 200 columns, and agentio cuts it with its marker
SCOPE: out — tests/unit/test_adele_env_slice1_cli.py (1 of 2 changed files) (task has FLAGGED: yes)

### T049: the requester, session end, the collection pass and the reaper's tick
**Started:** 2026-10-18T12:40:45Z | **Completed:** 2026-10-18T12:42:21Z

INHERITED: Request.Peer and the requester label (T045); the ledger's Recorded and SessionEnded (T039); the engine's Agents and Down with images (T040)
FLAGGED: a pass collects an environment when its ledger session has an end row (b), or when its containers' requester label names an agent container the daemon's list no longer has (a); an environment whose requester is unknown, or that has none (slice 0's), is left to session end and the ttl. Chose the ledger's session over the session label as the authority, because the ledger is what records who asked and the label is read back only to find the requester (confidence: high)
FLAGGED: a collected environment is a reaped row with the cause and the counts removed, read back with 0 left; anything left is a reap-failed row, tried again on the next pass, so the reaper's own given-up logic is not involved (confidence: medium)
ASSUMED: the reaper's After hook runs on its existing tick (5 s by default) and lists the daemon only while there are live environments (confidence: high)
ABSENT: no unit drives the daemon side of a collection (the lane's cells do); no unit runs the reaper's After hook through Run; collect needs no grant, since it only removes what an ended session left
SCOPE: in (5 changed files)

### T055: README
**Started:** 2026-10-18T12:43:45Z | **Completed:** 2026-10-18T12:44:50Z

INHERITED: the send's README status block; the client's verbs and verdicts (T047, T050, T052); the operator's mark rule (clear the last update's marks first)
FLAGGED: the status block is applied now, on both slice-1 criteria being built with their cells written, as slice 0's T019 applied its block before its lane ran; the lane is what shows they are met (confidence: medium)
ASSUMED: the Status paragraph's other sentences stay true ("Features 02, 03, 07–13 and 15 have their first slice or slices") and the Next line is left as it is, as the send says (confidence: high)
ABSENT: the two changed command examples sit in code blocks, which cannot be marked; slice 0's 13 marks were removed first, per the operator's rule
SCOPE: out — README.md (1 of 1 changed files) (task has FLAGGED: yes)

### T048, T051, T053, T054, T052 (e2e half): the slice-1 cells, fixtures and lane (delegated), and the label fix they found
**Started:** 2026-10-18T12:43:00Z | **Completed:** 2026-10-18T13:02:42Z

INHERITED: every verdict, error and ledger cause from tools/bin/adele and the broker (T045–T049), read from the code by the delegate
FLAGGED: a defect the cells were written to find, confirmed with the pinned docker-compose v5.6.0's config here: compose interpolates the bytes Adele runs once more, so a remote-env label holding ${containerEnv:X} made compose refuse the model. Inject now escapes $ as $$ in Adele's own label values, and the escaped label round-trips through compose's config (confidence: high)
FLAGGED (delegate): the reaper runs the same collection pass every 5 s and can win the race with a cell's `adele env collect`; the cells assert the ledger row and the daemon either way, and say on fd 3 which pass collected (confidence: high)
FLAGGED (delegate): rule (a)'s cell starts a throwaway agent container labelled as the agent is, on the agent's own adele-request network and timelike-nested, so Adele finds it by its address; its removal is what ends the session (confidence: medium — that a non-compose container can join those networks and resolve adele is the lane's)
FLAGGED (delegate): oneshot-fail accepts either path (compose up refusing a failed service_completed_successfully dependency, or the client's rule) and checks each on its own terms, naming on fd 3 which answered (confidence: medium)
ASSUMED (delegate): the image nobody exists in timelike-agent:local and can run its Python; the classic builder prints "Step 2/2 : RUN false" (confidence: medium)
ABSENT: no cell runs a build or a lifecycle command past its bound (5 min, 120 s: minutes of timing on a disk-bound host); no new lane.conf serial entry; the lane-start sweep removes built images in nested_sweep, at every lane start
SCOPE: in (16 changed files)

### T056: host lanes, the cycle report, reboot.md, commit
**Completed:** 2026-10-18T13:16:41Z

INHERITED: every task above
ASSUMED: the README status block stands on both criteria being built; the lane shows whether they are met (confidence: medium)
ABSENT: the Docker lane, scan and lint in their containers; mypy, staticcheck and govulncheck

## Cycle 7 — lane 13s1a (`../bridge/feedback/13-20261018-173253-lane-13s1a-build-step-verdict-and-mypy.md`; branch `modify/014-slice-1`)

### T057–T058: mypy's union-attr, and the failed build step in the Dockerfile's terms
**Started:** 2026-10-18T17:47:10Z (the cycle's first clock reading) | **Completed:** 2026-10-18T17:53:26Z (the code; records and host lanes after)

INHERITED: Cycle 6's code at `b209824`; lane 13s1a's logs under `../bridge/` (196's verdict read from `.make-test-13s1a.log`)
ASSUMED: A — `dropped` read once into a local and narrowed by `isinstance`; mypy 2.3.1 (the version `pins.env` gives the lint) on this host over `pyproject.toml`'s files then also flagged the new `last_lines` line, narrowed the same way; it reports no issues in 39 files (confidence: high)
ASSUMED: the six steps are Adele's six labels. Read in moby v28.5.1's source (`builder/dockerfile/builder.go`, `buildLabelOptions`): one `LABEL` command per `labels` entry, appended to the last stage, counted in "Step N/M" (`totalCommands`). The lane's daemon version is not in its logs; 2 + 6 = 8 matches (confidence: high)
FLAGGED: B — the step is named by its position N among the Dockerfile's own instructions and its text, never the daemon's M; chose to compute nothing from M (no M minus the label count) over deriving the Dockerfile's total, because steps are numbered in the Dockerfile's order with label steps last, so N is right on any daemon, while a total would depend on how a daemon version adds labels. A label step is recognised as `LABEL <a request key>=` (buildkit v0.25.1's `NewLabelCommand` text) and said as "the labels Adele adds after the Dockerfile's last instruction" (confidence: high)
FLAGGED: the lines kept are the failing step's own, with the daemon's `--->` and `Removing intermediate container` lines dropped; the daemon's error (`message`, e.g. "The command '…' returned a non-zero code: 1") follows them in the client's one line, because a step that prints nothing (`RUN false`) otherwise says nothing of why (confidence: high)
ASSUMED: 196's cell asserts the instruction and its position, the daemon's message with the command left as a wildcard, and that no `Step ` or `--->` is in the line (confidence: high)
ABSENT: no Docker here, so 196 has not run against a daemon; no broker unit drives a failed build (the engine units and 196 cover the mapping); C (002's bench probe) not touched, as ruled; the spec's FR-24 ("naming the step") left as it stands, since it is still true
SCOPE: in (6 changed files) (task has FLAGGED: yes)
