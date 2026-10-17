# Cycle report — 014-nested-dev-env (prompt 13, nested dev environments)

## Cycle 1 — bridge/sends/13-rev17-20261017-035606.md

**Written:** 2026-10-17T05:02:39Z (read from the clock). Attended, not in dispatch mode. A first build of prompt 13,
**slice 0 (skeletal)**, on `014-nested-dev-env` from `master` `15a5213`. This path is the one the send names, and this
project's CLAUDE.md names the same one.

**The spec was first written from `bridge/sends/13-rev8-20261017-012727.md`** (prompt revision 8, discovery 16), as
`1e0c224`, before FOR-MENTOR Item 27 was answered. That send was superseded by this one (prompt revision 17,
discovery 17) after Item 27's answer was folded into the spec and plan, and while T001–T002 were being written. This
send's sequence was then followed:
1. Item 27 was closed, citing both answers (`dc33bd9`).
2. `/specswarm:modify 014 --from-send bridge/sends/13-rev17-20261017-035606.md` corrected the spec in place, declared
   (`f33472c`).
3. The governance audit of revision 17 (`f83b3de`, one commit).
4. Implement continued from the plan and tasks, which this cycle wrote in full and which follow revision 17.

**Plugin:** specswarm **4.0.1-botbaubble.2.44.0**, the version this session loaded (lore `specswarm` Q002).

**Commits** (`master..HEAD`, all under the ironik.xyz identity):
- **The spec and its revision:**
  - `1e0c224` the spec (rev-8 send) and FOR-MENTOR Item 27;
  - `206d243` the plan, research, data model, contract, quickstart and tasks, with Item 27 closed and Item 28;
  - `dc33bd9` Item 27's closure cites the refusal-code answer;
  - `f83b3de` the governance audit;
  - `f33472c` the modify cycle (spec corrected, `audited_against [8, 17]`, `audit-log.md`, Item 29).
- **Tasks:**
  - `1349850` T001–T002;
  - `21e4f19` T003–T006;
  - `134bf03` T007;
  - `3295874` T008 (Adele) and T016;
  - `5af0d84` T009;
  - `eb60aff` T010–T015, T017, T018;
  - `e003066` T019;
  - `6bfc6ee` the host-lane fixes.
- **This report** and `reboot.md`, in the last commit.

### Group A — cited from `.implement-complete`

Group A: not applicable — no marker on this path

### Group B — copied from the send

| Field | Value |
|---|---|
| source_send | bridge/sends/13-rev17-20261017-035606.md |
| source_prompt | plan/.discover/prompts/13-nested-dev-env.md |
| prompt_revision | 17 |
| discovery_revision | 17 |
| slice | 0 |

`spec.md`'s own `prompt_revision` stays **8**: the body was generated from revision 8, and a modify cycle never moves
that field. Revision 17 is recorded in its `audited_against`.

### Group C — written by the code instance

**delegations:** `[]`. No subagent was used in this cycle.

**reconcile_mode:** `scoped`.
- **Classification:** revision 17 is the only revision since 8 that changed prompt 13; its `revision` field moved
  8 → 17. It **amended** the forbidden-settings criterion, from exit 4 to exit 2 with rule 14's error. By modify's
  table that is SUPERSEDED.
- **Corrected in place, not regenerated,** as the send directs. Only the spec existed when revision 17 landed, so
  no built code rested on the struck sentence.
- **What changed in the spec:** FR-8, Scenario 2, criterion 3 (the old line kept, struck, beside the new one), D-1 and
  D-7.
- **Records:** `audited_against [8, 17]`; `audit-log.md` has the row, and `modify.md` and `impact-analysis.md`
  record it.

**What was built** (spec FR-1 to FR-15; research R1–R11; contract `contracts/adele-env.md`):
- **Adele's image** carries the Compose CLI, copied from the pinned `DOCKER_CLI_IMAGE`. The build refuses it unless
  `go version -m` reports `CGO_ENABLED=0`; the final stage is still `FROM scratch`.
- **Resolution in a sandbox** (`adeled resolve`). This is a throwaway of Adele's own image with:
  - the workspace read-only at its own path, and nothing else mounted;
  - network `none`, an environment of `HOME` only, uid 10001, a read-only root, all capabilities dropped.

  It runs compose's `config --format json`, resolves each bind source with `EvalSymlinks`, and names unset
  variables. A file it cannot see outside the workspace becomes a refusal.
- **The check.** Item 27 Q1's refusal list, applied to the resolved model. A forbidden setting is HTTP 422 with no
  operator's command, and the client exits **2** with rule 14's line (revision 17). It is recorded as a `refused`
  ledger row with an empty `extend`; 12's `status` prints "operator's command: none".
- **The grant.** `docker.compose` with 12's five keys: capability, ttl, published ports and instances (counted per
  capability), plus a budget at 0.00.
- **Never pull.** A missing image exits **3** and names the operator's `docker pull` (Item 29, provisional).
- **Up.** From the checked bytes, with timelike's labels on every service, network and volume, every service joined
  to `timelike-nested` as `<service>.<name>`, and compose run in an emptied environment from an empty directory.
- **Ledger and repeat up.** A `performed` row records `undo` = down. A repeat `up` of an unchanged model creates
  nothing and records nothing. A changed model is 409.
- **Down and the reaper.** `down` uses the Engine API by label: it removes everything labelled with the environment,
  reads the daemon back, and records a `reaped` ending only when 0 objects are left. 12's reaper reaps expired
  environments through a second provider, chosen by capability.
- **The client** (`adele env up|status|down`). It waits until each service is ready, using Adele's read-back and
  probing ports itself, from the agent's container. The bound is 120 s by default and at most 600 s; past it, exit
  124 with each state, and the environment stays up. A service that exits non-zero is exit 1 at once.
- **The workspace and the boundary** (`scripts/workspace.sh`, `make up`, the lane). The launcher takes
  `TIMELIKE_WORKSPACES` from the environment or the git-ignored `local.env`, makes one directory per launch, and
  mounts it into the agent at the same path with the parent's group. `TIMELIKE_HOST_GIT=enforced` refuses a
  workspace inside a git work tree; `lifted` permits it. The setting is shown as a label, an agent environment value
  and a verdict line.
- **Where agents look** (P3): `docker` and `docker-compose` in the command-not-found table answer with
  `adele env up`, and the announcement has one line.

**criteria_reestablished:** Every e2e cell of this cycle is written and has never run: there is no Docker here. So
each Automated criterion is `unconfirmed` until the mentor's lane runs it, and the test that will execute it is named.

| Criterion | Mode | Evidence |
|---|---|---|
| 13 · "Bringing up a fixture project's compose file from inside the agent container starts its services" | **unconfirmed** | Test: `tests/e2e/bringing-up-a-fixture-projects-compose-file-starts-its-services-and-returns-once-ready-listing-each-service-and-address.bats`, not run. Host-side: `tests/unit/test_adele_env_cli.py`, the readiness loop and verdict against a fake Adele |
| 13 · "runs the nested environment's containers with the agent's workspace mounted at the same absolute path" | **unconfirmed** | Test: `tests/e2e/nested-containers-run-with-the-agents-workspace-mounted-at-the-same-absolute-path.bats`, not run |
| 13 · "A request for a privileged container, host networking or process namespace, added capabilities, or a mount outside the workspace is refused by Adele with exit 2" | **unconfirmed** | Test: `tests/e2e/privileged-host-network-or-namespace-added-capabilities-or-mount-outside-the-workspace-refused-by-adele-with-exit-2-naming-the-setting.bats`, not run. Host-side: the refusal list, executed (`adele/internal/compose` units, 26 settings); the exit-2 line, executed against a fake Adele (`tests/unit/test_adele_env_cli.py`) |
| 13 · "A pre-commit hook and a `core.hooksPath` or `core.fsmonitor` setting written by the Agent" | **unconfirmed** | Test: `tests/e2e/agent-written-hooks-and-executing-git-config-do-not-run-in-the-operators-own-checkout-unless-lifted.bats`, not run. Host-side: the launcher's refusal and lift, executed with a real git (`tests/unit/test_workspace_launcher.py`) |
| 13 · "Bringing the environment up twice is a no-op the second time" | **unconfirmed** | Test: `tests/e2e/bringing-up-twice-is-a-no-op-and-tearing-down-removes-every-container-network-and-volume-it-created.bats`, not run |
| 13 · "DEMO: the Agent brings up a compose test environment from inside its container" (D9, Manual) | **unconfirmed** | Nobody has looked; the demo is the mentor's with the operator |

The struck exit-4 criterion is not cited. Slice 1's and slice 2's criteria are not cited.

**The host lanes, run before this report** (the code as committed in `6bfc6ee`):
- **`make test-host`, serially:** passed; 2577 passed, 12 skipped, in 516.11 s; env-layer 60/60, hook 57/57,
  handler 33/33. The first serial run failed 11 units, all fixed in `6bfc6ee` (decisions.md § T020).
- **The same with `-n 8`:** passed; 2577 passed, 12 skipped, in 138.43 s.
- **Go,** on the session's Go 1.27.1, not the pinned 1.27.2:
  - `go test -race ./...` passed in every package;
  - gofmt, `go vet` and staticcheck v0.8.1 are clean;
  - govulncheck reports nothing the code calls.
- **Lint:** ruff check and format, mypy (39 files) and shellcheck over the Makefile's whole list are clean.
- **Not run:** the Docker lane (`make test`), `make scan` and `make lint`.

**not_verified:**
- **Every e2e cell of this cycle, and the whole Docker lane:** this session has no Docker. No cell has run against a
  daemon.
- **Whether the compose binary in `DOCKER_CLI_IMAGE` is static** (Item 27's answer asks for this): not known. The
  build checks it and refuses otherwise. The binary's path in that image
  (`/usr/local/libexec/docker/cli-plugins/docker-compose`) and its standalone mode are also unchecked.
- **The symlink race** (Item 27's answer): a link swapped between the sandbox's check and the daemon's mount is not
  closed. That is slice 2's.
- **Compose's own texts and shapes, against the pinned binary:** the "variable is not set" warning, an absent file's
  error, `config --format json`'s field shapes, and a second interpolation of the checked JSON (R5). The units use
  the shapes compose-go v2 prints; a difference fails a cell rather than letting a setting through.
- **The Docker lane's prerequisites:**
  - `DOCKER_CLI_IMAGE` carries git (the operator's stand-in in the boundary cells): unchecked, though the first cell
    names it if absent;
  - `DEBIAN_IMAGE` is on the daemon after the lane's up: assumed, because adele-secret runs from it.
- **Real projects' compose files were not tried** (cross-stack P005). The fixture is timelike's own, and each refusal
  is shown with a fixture asking for that one setting.
- **Builds are refused in slice 0** (Item 28), so no cell builds.
- **No cell publishes a host port:** every lane grant has `ports = none`. The ports refusal goes through 12's tested
  check.
- **Scale:** two containers of one service would be listed as two services.
- **The scan:** Adele's image scan now includes the compose binary's Go modules, and its findings are unknown until
  `make scan` runs (H9).
- **Root-owned files:** files a nested container writes as root into the workspace are root's on the host. Not
  handled in slice 0.

**changed_other_features:**
- **004 (12):**
  - Adele's broker routes `docker.compose` under its own lock;
  - `Params` gains `dir`, `files` and `profiles`;
  - `refuse` gains a host argument (`refuseAt`);
  - the reaper takes providers by capability, and the stand-in's reap wording is unchanged byte for byte;
  - `KnownCapabilities` and two messages name `docker.compose`;
  - the ledger gains `LiveOf`, `LiveResource` and `LiveRows`, with no schema change;
  - `/v1/denials` gives `extend_by: none` for a refusal with no command, and both `status` commands print
    "operator's command: none" for it;
  - `adeled serve` wires the socket when it is mounted;
  - `grants.example.conf` gains a `docker.compose` grant;
  - the lane's grant file gains three grants.

  Two of 004's e2e files follow the new topology:
  - the agent's mounts are exactly the state volume and the workspace bind, still with nothing of Adele's and no
    socket;
  - the agent's networks add `timelike-nested`, which must be internal;
  - Adele's mounts add the socket.
- **005:** `tests/unit/test_state_root_image.py` allows exactly the workspace as the agent's second mount.
- **007 (04):**
  - `missing-commands.tsv` gains `docker` and `docker-compose`;
  - the announcement gains one line (under 60 lines; 04's units pass).
- **maint-lane-speed:**
  - `tests/run.sh` runs the launcher and the label sweep in the up step, and gives the runner the workspace and
    `DOCKER_CLI_IMAGE`;
  - a non-unix `DOCKER_HOST` gives Adele no socket;
  - `tests/unit/test_lane_run_sh.py` gets the launcher and two new units.
- **001:** its contract text was not edited. The exit-4 confirmation clause (plan's no-revision ruling) is
  **carried**: no cycle-14 test writes an exit-4 test across modes for a confirmation envelope.
- **Compose and the Makefile:**
  - `compose.yaml`: Adele gets the socket and its group; the agent gets the workspace, its group, the labels and
    environment, and `timelike-nested`;
  - Makefile: `make up` runs the launcher and reads the socket's group; the lint list gains the new files.

**What the mentor's lane needs (new in this cycle):**
- **`TIMELIKE_WORKSPACES` set to the workspace parent**, in the environment or in `local.env`, which code/ cannot
  write for the mentor. Without it, the up step fails naming the variable.
- **The lane's runner writes into its own new directory under the parent.** As uid 2001 in the parent's group it
  can.

**process_failures_recorded:**
- **A send superseded mid-cycle.** The rev-8 send was superseded after the spec, plan and tasks were written and
  T001–T002 were in progress. The work in progress did not touch the amended criterion. The re-send's sequence was
  followed from there, so plan and tasks were updated rather than regenerated.
- **A draft verdict past rule 13.** The first `adele env up` verdict ran past 200 columns, and agentio cut it. Found
  by a unit and shortened before commit.
- **Assumptions found by the first host run.** It failed 11 units of other features: the lane's scratch harness and
  005's mount pin assumed the old topology. Fixed and rerun, with both runs recorded above.
- **The launcher's `local.env` lookup** returned non-zero under `set -e` for a key the file lacked, which would have
  ended a launch silently. Found by its unit and fixed before commit.

**retired_prompts_seen:** none.

**The libcurl re-review: facts for the operator's decision at sign-off** (the send's § Before the merge):
- **What holds or reaches the socket** is Adele's process and the compose CLI it runs, both in her image.
  - **adeled:** Go, `CGO_ENABLED=0`, static. It links no libcurl; its daemon client is Go's stdlib `net/http` over the
    unix socket.
  - **docker-compose:** Go, and the build refuses it unless `CGO_ENABLED=0`, so it links no C library, libcurl
    included.
  - **The image's contents:** `FROM scratch` with those two binaries, so no libcurl is present.
  - **The sandbox** runs her image with no socket and no network.
- **The agent's new network path** is `timelike-nested`, `internal: true`, which reaches only the nested
  environments' containers. It gives the agent no route out.
  - The nested services keep their own project default network, which has the host's egress, as any compose project
    has.
  - Nothing new reaches the socket or Adele from the agent. The agent still reaches Adele only on `adele-request`.
  - The agent holds no socket, Docker group or Docker endpoint.
- **Not changed:** the agent's existing egress through compose's default network, until 12 slice 2.

## Cycle 2 — bridge/sends/13-rev17-20261017-035606.md

**Written:** 2026-10-17T10:25:15Z (read from the clock). Attended, not in dispatch mode. The same send as Cycle 1, built again to
acceptance after **lane 13s0a** on `e5a58af` failed. The lane's feedback is
`../bridge/feedback/13-20261017-063803-lane-13s0a-fails.md`: 10 of 733 e2e cells not ok, and Adele's scan FAIL. This
cycle fixes A, B, C and E, answers D, and closes Item 29, as the feedback asks. It is on `014-nested-dev-env`, in one
commit after `e5a58af`, with this report. No `/specswarm` command ran: no revision moved, so the spec, plan and
`audited_against [8, 17]` stand. tasks.md gains T021–T026, and decisions.md gains § Cycle 2.

### Group A — cited from `.implement-complete`

Group A: not applicable — no marker on this path

### Group B — copied from the send

| Field | Value |
|---|---|
| source_send | bridge/sends/13-rev17-20261017-035606.md |
| source_prompt | plan/.discover/prompts/13-nested-dev-env.md |
| prompt_revision | 17 |
| discovery_revision | 17 |
| slice | 0 |

### Group C — written by the code instance

**delegations:** `[]`.

**reconcile_mode:** `scoped`. No prompt or discovery revision moved since Cycle 1. Item 29's ruling (plan `eab79e9`)
is a clarification with no revision: it confirms exit 3, which Cycle 1 built. **"Provisional" is dropped.** A missing
image is exit 3 with rule 14's error, and no grant envelope.

**What changed, by the feedback's items:**
- **A · the bound** (cells 151, 152, 154, 155):
  - **The cause read from the code.**
    - Adele held one lock (`Envs.mu`) for the whole of every environment request, the sandbox included. So in the
      parallel lane, each bring-up and each of the 26 forbidden-setting cells waited behind the others, and the
      agent's 120 s counted that queue.
    - Cell 155's sandbox ran past its own 90 s, and the time was not compose's. `compose config` inside it is bounded
      at 45 s and would have printed its own error, so the 90 s went to the daemon's create, start, wait or logs,
      under the lane's load.
    - **Which of those four phases is not established here.**
  - **The fix:**
    - The sandbox and the setting check take no lock, and refusals no longer queue.
    - The lock runs from the live check to the ledger write. A `down` of a name takes it, so it waits for an `up` of
      that name in progress, then removes everything labelled with it.
    - A request its client gave up stops if Adele has not started creating. Once she creates, she finishes and records
      it (the context is detached), so an environment is never half-made and unrecorded. Compose is no longer killed
      midway when the agent gives up. Killing it mid-create can leave objects the daemon finishes after compose dies,
      which is the likeliest cause of the teardown's "left 3 0 1".
  - **Measuring it next time:** the sandbox's errors name their phase, and whether its own bound passed or the
    request was given up. `up`'s answer carries Adele's timings: resolve, the sandbox's four phases, the lock wait and
    compose. The client puts them in `adele_timings`, and the bring-up JSON cell prints them, **measured and not
    asserted**, so the next lane says where the time went.
  - **The remediation names the cause:**
    - `make build` is named only when the daemon says the image is missing;
    - a timeout says the daemon was slow, and to retry.
  - **The bound still counts from the agent's side**, because it is what the agent waits for. Past it, the line says
    what is true: if she had started creating she finishes and records it, `adele env status` shows it, and
    `adele env down` removes it once she is done.
- **B · /tmp** (cells 701–703):
  - **The fix:** a bring-up's empty project directory and compose's HOME are made under Adele's state directory, the
    one her ledger writes, and no longer under /tmp.
  - **The cause is not established.** Cell 153 reached compose up through the same call in the parallel phase. 701–703
    failed in the serial phase, after cell 595 stops and starts Adele. /tmp after that restart is the likeliest
    difference, and it is not checked.
- **C · the git boundary** (cells 603, 605):
  - **The stand-in models a current git:** the pinned CLI image's (2.54 at 29.9.0), the git the README tells the
    operator to expect, and the stricter one. The lane's runner step builds it as `timelike-operator-git:local`
    (`--target operator-git` in `tests/runner/Dockerfile`), and the cell runs it with `--pull never`. No cell pulls by
    digest.
  - **603:** git 2.54's local clone asked for `safe.directory` on the repository's `.git`. The operator passes it for
    exactly the agent's repository, both its work tree and its `.git`, on each command that reads it.
  - **603 now also asserts** that the operator's checkout has both commits, its own and the agent's, through clone,
    fetch and pull. No hook of the agent's announced itself, and the marker is empty.
  - **605:** the failure was the operator's own write into a project directory the agent had made 0755, not the
    hook's marker (its path is absolute). Project directories are now made 2775, as the workspace is.
  - **Hooks now say on stderr that they ran**, so "the hook ran" and "the hook could not write" differ. The cell
    asserts the commit and the hook's own line.
  - The README's `safe.directory` sentence now names both paths.
- **E · the scan:**
  - **Option (a) is not available:** Compose v5.6.0 is the newest release, and its binary is go1.26.8 with x/net
    v0.58.0.
  - **Built: option (b),** Compose from source in Adele's build stage:
    - `COMPOSE_VERSION=v5.6.0`, sum-checked against `COMPOSE_SUM`;
    - x/net raised to `COMPOSE_XNET_VERSION=v0.60.0`;
    - built by GO_IMAGE's Go 1.27.2.
  - **The build refuses the binary unless:**
    - it is `CGO_ENABLED=0`, so **the static check still holds**;
    - it carries the pinned x/net;
    - it reports the pinned version.
  - FOR-MENTOR **Item 30** has the recommendation and what was checked.
- **D · 005's SC-7 cell 69:** answered below.

**D, answered:**
- **Load:** yes, this cycle's cells add load. Every `adele env up` runs one sandbox container, each bring-up starts
  three containers, and the forbidden-settings file runs 26 sandboxes in a row.
- **Overlap with cell 69: most likely none.** This is an estimate from the plan's order and the cells' durations; the
  lane records no start times.
  - In the parallel plan, 005's file is the first after the three `first` files, and the two bring-up files are
    11th and 12th.
  - With 8 slots, the bring-up files start only after 6 of the files ahead of them finish, and the snapshot files
    2–5 ran minutes each (cells 72, 86 and 88 took 137 s, 141 s and 297 s).
  - Cell 69 began about 77 s into its file, after cells 66–68.
  - Its neighbours were the three long `first` files and the snapshot files, as in earlier lanes it passed.
- **No class change from this one failure.** If the next lane shows the overlap, the fix is a class for 005's file,
  not its bound.

**criteria_reestablished:** none of this cycle's code has run against a daemon, because there is no Docker here. So
each criterion is `unconfirmed` for this commit, and the lane-13s0a evidence about Cycle 1's code is given beside it.

| Criterion | Mode | Evidence |
|---|---|---|
| 13 · "Bringing up a fixture project's compose file from inside the agent container starts its services" | **unconfirmed** | Test: `tests/e2e/bringing-up-a-fixture-projects-compose-file-starts-its-services-and-returns-once-ready-listing-each-service-and-address.bats`. In 13s0a, 151 and 152 were not ok (A) and 153 was ok |
| 13 · "runs the nested environment's containers with the agent's workspace mounted at the same absolute path" | **unconfirmed** | Test: `tests/e2e/nested-containers-run-with-the-agents-workspace-mounted-at-the-same-absolute-path.bats`. Ok in 13s0a on `e5a58af`; this cycle changed the lock and the image it runs under |
| 13 · "A request for a privileged container, host networking or process namespace, added capabilities, or a mount outside the workspace is refused by Adele with exit 2" | **unconfirmed** | Test: `tests/e2e/privileged-host-network-or-namespace-added-capabilities-or-mount-outside-the-workspace-refused-by-adele-with-exit-2-naming-the-setting.bats`. Ok in 13s0a on `e5a58af` (26 settings); its refusals now run outside the lock |
| 13 · "A pre-commit hook and a `core.hooksPath` or `core.fsmonitor` setting written by the Agent" | **unconfirmed** | Test: `tests/e2e/agent-written-hooks-and-executing-git-config-do-not-run-in-the-operators-own-checkout-unless-lifted.bats`. In 13s0a, 603 and 605 were not ok (C); 604 and 606 were ok |
| 13 · "Bringing the environment up twice is a no-op the second time" | **unconfirmed** | Test: `tests/e2e/bringing-up-twice-is-a-no-op-and-tearing-down-removes-every-container-network-and-volume-it-created.bats`. In 13s0a, 154 and 155 were not ok (A) |
| 13 · "DEMO: the Agent brings up a compose test environment from inside its container" (D9, Manual) | **unconfirmed** | Nobody has looked; the demo is the mentor's with the operator |

**The host lanes, run before this report** (this cycle's code, uncommitted at the time; the commit is the same tree):
- **`make test-host`, serially:** passed, 10:07:45Z–10:20:48Z; 2580 passed, 12 skipped, in 669.40 s; env-layer 60/60,
  hook 57/57, handler 33/33.
- **The same with `-n 8`:** passed, 10:21:08Z–10:24:03Z; 2580 passed, 12 skipped, in 141.14 s.
- **Go** (the session's 1.27.1): `go test -race -count=1 ./...` passed in every package; gofmt and `go vet` are clean.
- **Lint:** ruff check and format are clean on the changed Python. `bash -n` was run on `tests/run.sh`, `nested.bash`
  and the two changed bats files.
- **Not run:**
  - shellcheck, because it is not on this host (the lane's `make lint` runs it);
  - mypy, staticcheck and govulncheck over Adele's code;
  - the Docker lane, `make scan` and `make lint`.
- **The Compose build steps, rehearsed on the host:** a static binary, Docker Compose 5.6.0, with x/net v0.60.0.
  govulncheck on it finds no x/net advisory. It finds the host Go's stdlib advisories, which 1.27.2 fixes, and
  GO-2026-5932 in `x/crypto/openpgp`, which has no fix.

**not_verified:**
- **Every e2e cell, the image build with the source-built Compose, and the scan:** no Docker here.
- **Whether grype blocks GO-2026-5932** (x/crypto openpgp, no fix) in the rebuilt image: the lane's reading.
- **Which sandbox phase was slow (A), and why /tmp failed after the restart (B):** the next lane's timings line answers
  the first. The second is avoided, not explained.
- **D's overlap:** an estimate from durations.
- **The lifted cell's write path** under the real workspace's group: it depends on the runner's uid being in the
  workspace parent's group, as Cycle 1 assumed.
- Cycle 1's list stands otherwise, except two of its entries, now replaced:
  - whether DOCKER_CLI_IMAGE's compose binary is static: the binary is now built here;
  - whether DOCKER_CLI_IMAGE carries git: 13s0a showed git 2.54.

**changed_other_features:**
- **maint-lane-speed:** `tests/run.sh`'s runner step also builds `timelike-operator-git:local` and passes
  `OPERATOR_GIT_IMAGE` to the runner. `tests/runner/Dockerfile` gains the `operator-git` stage, and the runner's own
  default target is unchanged. One lane unit is added.
- **004 (12):**
  - Adele's image no longer takes `DOCKER_CLI_IMAGE`, and its build stage builds Compose;
  - `compose.yaml` passes the three Compose pins to both of Adele's targets;
  - `engine.Run`'s errors are typed.
- **Others:** none.

**process_failures_recorded:**
- **Lane 13s0a failed** on Cycle 1's code, which never ran against a daemon before the lane. The host lanes could not
  reach any of A, B, C or E.
- **A composed time.** A start time was composed in decisions.md while writing, then replaced with the cycle's first
  clock reading before commit.

**retired_prompts_seen:** none.

**The libcurl re-review:** the facts in Cycle 1 stand. Compose is now built here, still Go with `CGO_ENABLED=0`, and
links no C library. Nothing new reaches the socket.

**After this report:** no commits until the mentor says the next lane has ended. Merge `--no-ff` only after sign-off.

