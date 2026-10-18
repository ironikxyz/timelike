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


## Cycle 3 — bridge/sends/13-rev17-20261017-035606.md

**Written:** 2026-10-18T00:58:44Z (read from the clock). Attended, not in dispatch mode. The same send as Cycles 1 and 2, built
again to acceptance after **lane 13s0b** on `22c4777` failed. The lane's feedback is
`../bridge/feedback/13-20261017-153646-lane-13s0b-fails.md`: 2 of 733 e2e cells not ok, one `setup_file` in place of
its file's 8 cells, gounit's `internal/ledger` and one shellcheck finding. Every cell 13s0a failed passes, and the scan
passes. This cycle fixes A, C, D and E, answers B and the questions the feedback asks, and handles the six SC-8
volumes. It is on `014-nested-dev-env`, in one commit after `22c4777`, with this report. No `/specswarm` command ran:
no revision moved, so the spec, plan and `audited_against [8, 17]` stand. tasks.md gains T027–T032, and decisions.md
gains § Cycle 3.

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

**reconcile_mode:** `scoped`. No prompt or discovery revision moved since Cycle 2.

**What changed, by the feedback's items:**
- **A · cell 151 and the container it left:**
  - **How it leaked.** `engine.Run` removed a sandbox only once its create had answered. Here the create ran past the
    sandbox's 90 s bound, so Run gave up without an id; the daemon finished it at 14:42:36Z, and nothing knew the
    container was there. The reaper works from the ledger, and a sandbox is not a ledger resource.
  - **Found and removed now, two ways:**
    - **Run itself.** A create that got no answer from the daemon (its bound passed, the request was given up, or the
      socket failed) starts a removal by the sandbox's name. It tries until the daemon removes it, for up to 10
      minutes, because until a create finishes the daemon answers 404 for the name. A create answered with an error
      status made nothing and starts none. A removal of a made sandbox that does not answer is handed to the same
      removal.
    - **A sweep in `adeled serve`.** At start and every 5 minutes, she removes every container labelled
      `xyz.ironik.timelike.sandbox=resolve` created more than the bound plus that 10 minutes ago, about 12.5 minutes,
      and logs a line when she removed any. That finds one left by an Adele that stopped while a sandbox ran.
    - The lane's start sweep already removed sandbox-labelled containers, so the next lane would have removed this one;
      the sweep in serve covers the time between lanes, and the operator's host.
  - **Why it carried Adele's Compose labels.** The sandbox is made from Adele's own image, `timelike-adele:local`,
    and `compose up --build` builds that image. Compose labels the images it builds with its project, service and
    version, and a container inherits its image's labels. The daemon cannot drop an inherited label, so a sandbox now
    sets each of the three to an empty value: it then matches no project and no service, and compose no longer counts
    it as a container of the `timelike` project's `adele` service. **Not inspected here**:
    `docker image inspect timelike-adele:local --format '{{json .Config.Labels}}'` shows the image's labels.
  - **"Nothing was created" is now "no environment was created".** On a timeout the remediation also says that if the
    daemon makes the sandbox after all, Adele removes it.
  - **What held the lock for 20.6 s.** Envs' lock is held from the live check through `compose up` to the ledger
    write, for every name, so that two ups never race on one instance count. Cell 153's own sandbox took 359 ms; it then
    waited for another bring-up or down already holding the lock, whose `compose up` takes about 20 s under the lane's
    load. Which request it was is not in the lane's output, so `up`'s timings now carry `lock_held_by` (`up NAME` or
    `down NAME`, what held the lock when the wait began), and the JSON cell prints it, **measured and not asserted**.
    No lock change: what to narrow, if anything, waits for the next lane to name the holder.
- **B · cell 88's `setup_file`:** a `docker run` of the reap file's throwaway printed nothing for 300 s. That is the
  daemon at create under the same load as A. No code of this feature is on that path, and nothing changes for it: its
  bound is not raised.
- **C · SC-1's first cell:** the 60-commit history is now made once, in the file's `setup_file`, under exec_plain's
  `PLUMBING_TIMEOUT` and outside every cell's bound. Each cell copies it into its own directory and sets its state
  there (`fixtures/sc1-repo.sh DIR STATE FROM`; it refuses a FROM that is not a clean 60-commit history). The command
  each cell measures and its 20 s are unchanged. The two-argument form the demo uses is unchanged. All seven states were
  built from a copy on this host and checked.
- **D · the ledger's `SQLITE_BUSY`:**
  - **The connection had:** WAL, `busy_timeout(5000)`, and transactions begun IMMEDIATE. But performed and refused
    rows were single autocommit inserts outside any transaction, and nothing tried a write again once the 5 s passed.
    Under the lane's load one writer can lose the lock to a busier one for longer than that.
  - **What `adeled` did when the performed-row append failed after the resource exists:** it answered 500 with
    `performed: true`, the resource's name and "the operator records or removes it", for a box and for an environment.
    So it was not silent, but the resource was unrecorded, against 004 SC-5, and the reaper, which reads the ledger,
    would not have reaped it.
  - **The fix:** every ledger write is one IMMEDIATE transaction, and a write still refused busy (SQLITE_BUSY or
    SQLITE_LOCKED, extended codes included) is tried again, whole, until `WriteWait` (60 s) has passed. The 500 above
    stays for a write that fails past that.
  - **Evidence:** a new unit holds the write lock for 12 busy timeouts and the performed row lands once it is let go;
    with the retry removed it fails. `TestConcurrentHandles` was not reproduced failing here: 15 runs with -race under
    a CPU load on every core passed.
- **E · SC2329:** `build_runner` carries the directive every other step function in `tests/run.sh` carries ("invoked
  indirectly, by step"). Cycle 2 made it a function, called only through `step`.
- **The six `timelike-sc8-{home,state}-*` volumes:** they are SC-8's recreate cell's, whose teardown removes them with
  `|| true` under the plumbing bound; the 2026-10-15 run's log shows the daemon printing nothing for 30 s in that
  file, the likeliest way a removal failed. **Yes, a lane should remove them:** the cell now creates its two volumes
  labelled as throwaways, and the parallel lane's start removes labelled throwaway volumes and SC-8's unlabelled
  ones by their exact name shape (`timelike-sc8-{state,home}-N-N`). One still in use is left, and the lane says so.

**The questions in the feedback's common thread:**
- **Should gounit stay beside e2e? My recommendation: no, for the next lane.** In 13s0b every long gounit package took
  about 340 s against 132 s in 13s0a, and A, B and C all fell in e2e's start window beside it. `LANE_STEPS_TOGETHER=0`
  already runs gounit after e2e with no code change, so the mentor can run 13s0c with it and compare. I have not changed
  its default: the default came from the lane-speed maintenance send's measurements, and that is the mentor's call.
- **If a cell's failure is load, does its bound or its lane class move?** Neither bound moves: the bounds are the
  criteria's, or the plumbing's, and raising one hides the load. A lane class is the lever that changes what runs at
  once, and the steps' order is a lighter one. My order: gounit after e2e first; a class for the nested-environment
  files only if 13s0c still shows creates stuck behind the load.

**criteria_reestablished:** none of this cycle's code has run against a daemon, because there is no Docker here. So
each criterion is `unconfirmed` for this commit, and the lane-13s0b evidence about Cycle 2's code is given beside it.

| Criterion | Mode | Evidence |
|---|---|---|
| 13 · "Bringing up a fixture project's compose file from inside the agent container starts its services" | **unconfirmed** | Test: `tests/e2e/bringing-up-a-fixture-projects-compose-file-starts-its-services-and-returns-once-ready-listing-each-service-and-address.bats`. In 13s0b, 151 was not ok (A); 152 and 153 were ok |
| 13 · "runs the nested environment's containers with the agent's workspace mounted at the same absolute path" | **unconfirmed** | Test: `tests/e2e/nested-containers-run-with-the-agents-workspace-mounted-at-the-same-absolute-path.bats`. Ok in 13s0b on `22c4777` |
| 13 · "A request for a privileged container, host networking or process namespace, added capabilities, or a mount outside the workspace is refused by Adele with exit 2" | **unconfirmed** | Test: `tests/e2e/privileged-host-network-or-namespace-added-capabilities-or-mount-outside-the-workspace-refused-by-adele-with-exit-2-naming-the-setting.bats`. Ok in 13s0b on `22c4777` |
| 13 · "A pre-commit hook and a `core.hooksPath` or `core.fsmonitor` setting written by the Agent" | **unconfirmed** | Test: `tests/e2e/agent-written-hooks-and-executing-git-config-do-not-run-in-the-operators-own-checkout-unless-lifted.bats`. Ok in 13s0b on `22c4777` (603–606) |
| 13 · "Bringing the environment up twice is a no-op the second time" | **unconfirmed** | Test: `tests/e2e/bringing-up-twice-is-a-no-op-and-tearing-down-removes-every-container-network-and-volume-it-created.bats`. Ok in 13s0b on `22c4777` (154, 155) |
| 13 · "DEMO: the Agent brings up a compose test environment from inside its container" (D9, Manual) | **unconfirmed** | Nobody has looked; the demo is the mentor's with the operator |

**The host lanes, run before this report** (this cycle's code, uncommitted at the time; the commit is the same tree):
- **`make test-host`, serially:** passed, ending 00:55:36Z (the log's time); 2580 passed, 12 skipped, in 515.00 s;
  env-layer 60/60, hook 57/57, handler 33/33.
- **The same with `-n 8`:** passed, ending 00:58:32Z; 2580 passed, 12 skipped, in 140.22 s.
- **Go** (the session's 1.27.1): `go test -race -count=1 ./...` passed in every package; gofmt and `go vet` are clean.
  Coverage of the changed packages: ledger 88.1 %, engine 48.5 %, broker 49.2 %, adeled 89.3 % (no gate; the Docker
  paths are the lane's).
- **Syntax:** `bash -n` on `tests/run.sh` and the three changed bats files; `sh -n` on the SC-1 fixture.
- **Not run:**
  - shellcheck, because it is not on this host (the lane's `make lint` runs it);
  - mypy, staticcheck and govulncheck over Adele's code;
  - the Docker lane, `make scan` and `make lint`.

**One test choice to flag:** the two new engine units drive `Run` and the sweep against a fake daemon on a unix socket.
tech-stack.md says Adele's Docker calls are never mocked to reach coverage. These exist because a create that finishes
after its bound cannot be produced on demand from a real daemon; they check the order of calls and the labels sent,
not the filter. The real path is the lane's. If the mentor reads the rule as covering them, they come out and the late
removal is left to the lane alone.

**not_verified:**
- **Every e2e cell, and the late removal and the sweep against a real daemon:** no Docker here.
- **That the image carries the three compose labels**, and that an empty override takes the sandbox out of compose's
  view of the `timelike` project: read from how compose builds, not inspected.
- **What held Envs' lock in 13s0b:** the next lane's `lock_held_by` names it.
- **D's cause:** the retry's effect is shown by the new unit; the 13s0b failure was not reproduced.
- **Whether the lane's start sweep finds the six volumes unused:** the lane's.
- Cycle 2's list stands otherwise.

**changed_other_features:**
- **001 (SC-1):** `tests/e2e/fixtures/sc1-repo.sh` takes an optional FROM, and SC-1's file makes the history in
  `setup_file`. The demo's two-argument call is unchanged.
- **005 (SC-8):** its recreate cell creates its two volumes, labelled as throwaways, before starting the throwaway.
- **004 (12):** the ledger's writes are transactions retried while busy (performed, refused, extended and reap rows).
- **maint-lane-speed:** `tests/run.sh`'s parallel e2e start removes throwaway volumes; `build_runner`'s directive.
- **Others:** none.

**process_failures_recorded:**
- **Lane 13s0b failed** on Cycle 2's code. A and B are the daemon not finishing a create under load; the host lanes
  cannot reach either.
- **A composed time.** reboot.md's snapshot line was written with a time before the clock was read, then replaced with
  the reading before commit.

**retired_prompts_seen:** none.

**After this report:** no commits until the mentor says the next lane has ended. Merge `--no-ff` only after sign-off.

## Cycle 4 — bridge/sends/13-rev17-20261017-035606.md

**Written:** 2026-10-18T03:51:57Z (read from the clock). Attended, not in dispatch mode. The same send as Cycles 1–3, built again
after **lanes 13s0c and 13s0d** on `a8b0d7b` stopped at the build step. The feedback is
`../bridge/feedback/13-20261018-030300-build-disk-bound-uv-compile-timeout.md`: both lanes failed in the agent image's
`uv python install … --compile-bytecode` with "Python startup timed out (60s)", on a host whose one disk was saturated.
This cycle makes the build survive a slow disk and answers the question on `E2E_JOBS`. It is on `014-nested-dev-env`,
in one commit after `a8b0d7b`, with this report. No `/specswarm` command ran: no revision moved, so the spec, plan and
`audited_against [8, 17]` stand. tasks.md gains T033–T035, and decisions.md gains § Cycle 4.

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

**reconcile_mode:** `scoped`. No prompt or discovery revision moved since Cycle 3.

**What changed: both levers.**
- **uv's own bound, 60 s → 300 s, at every bytecode compile.** There are four: the agent image's runtimes stage
  (`/opt/agent`) and final stage (`/opt/uv-python`), and the bench's vanilla and driver images, because benchimg
  runs beside e2e on the same disk.
  - **Why 300.** It is five times the default. What failed was a compile worker that did not answer within 60 s
    while the disk's average wait was 65–138 ms. A broken interpreter fails at once, not at the bound, so only a
    compile that stops answering waits the 300 s out. It is a build-time plumbing bound, like `PLUMBING_TIMEOUT`;
    no criterion's bound moved. It is a judgment, not a measurement: no build ran here.
  - **A guard, so the raise cannot be silent.** uv ignores a variable it does not read. Before each compile the build
    checks that the pinned uv binary carries the name `UV_COMPILE_BYTECODE_TIMEOUT`, and stops with a remedy if it
    does not. The lane's build is the first run of that check.
- **Fewer concurrent writers.**
  - **`make build` builds one image at a time**: `agent`, then `adele`, then `adele-standin`, which reuses adele's Go
    stage from the cache. Before, one `compose build` built all three at once, so the agent image's two compiles
    overlapped Adele's Go build of Compose. A unit checks the list against compose.yaml's services with a build
    section. The lane's `up --build` is unchanged, and is a cache hit after `build`.
  - **The agent image's two compiles no longer overlap.** BuildKit built the runtimes stage beside the final stage.
    The final stage's compile now bind-mounts the runtimes stage's `/opt`, so it starts only after that stage is
    done. Nothing is copied by the mount, so the image's content is unchanged. The cost: a change to the runtimes
    stage now also rebuilds the final stage's interpreter layer.
- **The cost in time:** a cold build is now sequential where it was concurrent, so it may take longer on a fast disk.
  Not measured here.

**The mentor's question: should `E2E_JOBS` be smaller on a disk-bound host?** Yes for 13s0e: I recommend
`E2E_JOBS=4`, with `LANE_STEPS_TOGETHER=0` as in 13s0c and 13s0d.
- **Why.** Each e2e file starts containers and writes to the same disk. 13s0b's failures (151 at create, 88's silent
  `docker run`) fell in its e2e start window, when 8 files began at once and the disk's average wait sat at 67–85 ms
  with 16 tasks blocked. The CPU count does not see that.
- **Why the default stays 8 for now.** It came from the lane-speed maintenance send's measurements, and one lane at 4
  is the evidence for or against moving it. If 13s0e at 4 is clean where 13s0b at 8 was not, the default is the
  mentor's to move: a send, or I can change it on the mentor's word. A default read from the disk would need a
  measure of the disk the lane can trust, and I have none to offer.

**criteria_reestablished:** none of this cycle's code has run against a daemon, because there is no Docker here. So
each criterion is `unconfirmed` for this commit. 13s0c and 13s0d ran no e2e cell.

| Criterion | Mode | Evidence |
|---|---|---|
| 13 · "Bringing up a fixture project's compose file from inside the agent container starts its services" | **unconfirmed** | Test: `tests/e2e/bringing-up-a-fixture-projects-compose-file-starts-its-services-and-returns-once-ready-listing-each-service-and-address.bats`. Not run since 13s0b |
| 13 · "runs the nested environment's containers with the agent's workspace mounted at the same absolute path" | **unconfirmed** | Test: `tests/e2e/nested-containers-run-with-the-agents-workspace-mounted-at-the-same-absolute-path.bats`. Not run since 13s0b |
| 13 · "A request for a privileged container, host networking or process namespace, added capabilities, or a mount outside the workspace is refused by Adele with exit 2" | **unconfirmed** | Test: `tests/e2e/privileged-host-network-or-namespace-added-capabilities-or-mount-outside-the-workspace-refused-by-adele-with-exit-2-naming-the-setting.bats`. Not run since 13s0b |
| 13 · "A pre-commit hook and a `core.hooksPath` or `core.fsmonitor` setting written by the Agent" | **unconfirmed** | Test: `tests/e2e/agent-written-hooks-and-executing-git-config-do-not-run-in-the-operators-own-checkout-unless-lifted.bats`. Not run since 13s0b |
| 13 · "Bringing the environment up twice is a no-op the second time" | **unconfirmed** | Test: `tests/e2e/bringing-up-twice-is-a-no-op-and-tearing-down-removes-every-container-network-and-volume-it-created.bats`. Not run since 13s0b |
| 13 · "DEMO: the Agent brings up a compose test environment from inside its container" (D9, Manual) | **unconfirmed** | Nobody has looked; the demo is the mentor's with the operator |

**E is verified** by the mentor's lint on `a8b0d7b` (exit 0), as the feedback says. The scan's exit 0 is of
`22c4777`'s images and is not evidence for `a8b0d7b` or this commit.

**The host lanes, run before this report** (this cycle's code, uncommitted at the time; the commit is the same tree):
- **`make test-host`, serially:** passed, 03:24:12Z–03:35:16Z; 2584 passed, 13 skipped, in 571.65 s; env-layer 60/60,
  hook 57/57, handler 33/33.
- **The same with `-n 8`:**
  - **The first run failed,** 03:35:16Z–03:39:12Z: 1 failed and 18 errors, all in `test_bench_catalog.py` and
    `test_bench_runner.py`. Every one was a `subprocess.TimeoutExpired` in the bench fixtures' git setup, not an
    assertion. The host's `/proc/pressure/io` "full" avg300 read 14.67 % just after it. That is the disk the
    feedback describes, reaching the host lane too.
  - **The two files alone with `-n 8`** passed, 70 of 70.
  - **The whole run again** passed, 03:40:33Z–03:42:50Z: 2568 passed, 13 skipped, in 136.68 s. The 16 `timed` tests
    passed, run alone.
- **One more skip than Cycle 3** (13, not 12): `test_verify.py`'s `test_sc3_real_steps` skips because mypy is not on
  this host's PATH. It does not touch this cycle's files. Cycle 3's skip list was not kept, so I cannot confirm this is
  the one that changed. 2584 passed is Cycle 3's 2580, plus this cycle's 5, minus that one.
- **New unit:** `tests/unit/test_build_one_image_at_a_time.py`, 5 tests. Each of its three checks failed when its
  change was undone (the raised bound on one site, the bind mount, adele-standin in `BUILD_SERVICES`).
- **Not run:**
  - any image build, so the raised bound, the guard, the mount and the build's time are unmeasured;
  - the Docker lane, `make scan` and `make lint`; shellcheck, which is not on this host. No Go code changed.

**not_verified:**
- **That uv 0.12.22 reads `UV_COMPILE_BYTECODE_TIMEOUT`:** the mentor says uv takes it; the build's guard checks the
  binary for the name, and stops if it is missing. Not run here.
- **That 300 s is enough on this disk,** and that the sequential build stays within the lane's budget for the step.
- **That BuildKit orders the final stage's compile after the runtimes stage** because of the bind mount: how BuildKit
  resolves a mount's stage, not observed here.
- **Everything Cycle 3 listed as not verified** still stands, because no e2e cell has run on its code.

**changed_other_features:**
- **001 (the agent image):** both of its bytecode compiles carry the raised bound and its guard, and its final stage's
  compile waits for the runtimes stage.
- **002 (the bench):** the vanilla image's runtimes stage carries the same change as the agent image's, so the two
  stages stay byte-identical (D-15, RB1); the driver image's compile carries the raised bound.
- **The Makefile's `build`:** one image at a time.
- **Others:** none.

**process_failures_recorded:**
- **Lanes 13s0c and 13s0d stopped at the build** on Cycle 3's code, on the host's disk. The host lanes cannot reach a
  build.
- **The host lane's first `-n 8` run failed on timeouts under the same disk,** and passed when run again (above).

**retired_prompts_seen:** none.

**After this report:** no commits until the mentor says the next lane has ended. Merge `--no-ff` only after sign-off.

## Cycle 5 — bridge/sends/13-rev17-20261017-035606.md

**Written:** 2026-10-18T05:28:53Z (read from the clock). Attended, not in dispatch mode. The same send as Cycles 1–4, after
**lane 13s0e** on `367bc31` (`E2E_JOBS=4 LANE_STEPS_TOGETHER=0`). The feedback is
`../bridge/feedback/13-20261018-051500-lane-13s0e-e2e-green-lint-e501.md`: e2e 733 of 733 ok, the build and the scan
pass, lint fails on Cycle 4's new unit (E501), and 002's bench unit fails again. This cycle fixes A, applies B, and
reads C from the log. It is on `014-nested-dev-env`, in one commit after `367bc31`, with this report. No `/specswarm`
command ran: no revision moved, so the spec, plan and `audited_against [8, 17]` stand. tasks.md gains T036–T038, and
decisions.md gains § Cycle 5.

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

**reconcile_mode:** `scoped`. No prompt or discovery revision moved since Cycle 4.

**What changed, by the feedback's items:**
- **A · E501 in `tests/unit/test_build_one_image_at_a_time.py`:** the four assertion messages are wrapped, and no
  assertion changed. ruff 0.16.7, on this host, passes `check` and `format --check` over the lint's paths (`tools
  tests scan bench scripts`). The lane pins 0.16.9.
- **B · `E2E_JOBS`' default is 4, on the mentor's ruling** (`tests/run.sh`, with the reason beside it).
  - **Where the old 8 came from:** the lane-speed maintenance cycle
    (`.specswarm/maintenance/lane/cycle-report.md`). It was chosen from a schedule estimate made from per-file times
    on `c09f94a`: about 752 s at 8 or more, about 953 s at 4. It did not come from runs on the Docker host, and that
    report said the default should move if 8 proved flaky, on the mentor's call.
  - **The evidence for 4:** 13s0e at 4 was clean, with e2e taking 2142 s. 13s0b at 8 had 2 not ok and a `setup_file`,
    all in the start window, on the same disk.
  - **Measure again before raising it,** for example once the disk is replaced, as the comment beside the default
    says.
  - **Unchanged:** `UNIT_JOBS` (8) and `LANE_STEPS_TOGETHER` (1), because the ruling names only `E2E_JOBS`. 13s0e ran
    with `LANE_STEPS_TOGETHER=0`, so 13s0f on the defaults would run gounit beside e2e. Passing
    `LANE_STEPS_TOGETHER=0` again keeps 13s0f the same as 13s0e on everything but the commit.
  - **`tests/unit/test_lane_run_sh.py`**'s parallel-lane test now expects `--jobs 4`. The README names no number,
    so it does not change.
- **C · 002's bench unit (`tests/unit/test_bench_cli.py:137`, `:151`): not fixed, as asked.**
  - **The cause, as far as the log goes.** 004's Cycle 4 report named the cause of the same `:151` failure in lane
    12s1 (`.specswarm/features/004-adele-grants/cycle-report.md`, item F). The fixture's fake run uses
    `--call-limit 2`. A hooked `git commit` in the rejects task went past 2 s under the unit step's load and was
    counted as a hang. The fake agent's policy then took `--no-verify`, which failed, so the report did not say
    "Tie".
  - **This lane's two failures fit that.** Both are on `[gw6]` through the one `full_run` fixture. `:137` (Timelike
    loses not 0) and `:151` (no Tie in the rejects section) are the same changed ending seen from two tests.
  - **Not confirmed:** the log truncates the report, so it does not show this lane's ending.
  - **The fix belongs to 002's unit,** for the maintenance send after 13. Raising its call limit costs every hang
    task that limit's time.

**criteria_reestablished:** 13s0e ran every e2e cell on `367bc31`. This commit changes no code those cells exercise,
only a unit's line breaks and the lane's default file count. So each Automated criterion is observed by the mentor on
`367bc31`, and 13s0f is the run on this commit.

| Criterion | Mode | Evidence |
|---|---|---|
| 13 · "Bringing up a fixture project's compose file from inside the agent container starts its services" | **observed by the mentor** (lane 13s0e, `367bc31`) | Test: `tests/e2e/bringing-up-a-fixture-projects-compose-file-starts-its-services-and-returns-once-ready-listing-each-service-and-address.bats`; 151 ok; 153 printed "lock wait 1116 ms (held by up tl-51bd29-twice-lc)" |
| 13 · "runs the nested environment's containers with the agent's workspace mounted at the same absolute path" | **observed by the mentor** (lane 13s0e, `367bc31`) | Test: `tests/e2e/nested-containers-run-with-the-agents-workspace-mounted-at-the-same-absolute-path.bats` |
| 13 · "A request for a privileged container, host networking or process namespace, added capabilities, or a mount outside the workspace is refused by Adele with exit 2" | **observed by the mentor** (lane 13s0e, `367bc31`) | Test: `tests/e2e/privileged-host-network-or-namespace-added-capabilities-or-mount-outside-the-workspace-refused-by-adele-with-exit-2-naming-the-setting.bats` |
| 13 · "A pre-commit hook and a `core.hooksPath` or `core.fsmonitor` setting written by the Agent" | **observed by the mentor** (lane 13s0e, `367bc31`) | Test: `tests/e2e/agent-written-hooks-and-executing-git-config-do-not-run-in-the-operators-own-checkout-unless-lifted.bats` |
| 13 · "Bringing the environment up twice is a no-op the second time" | **observed by the mentor** (lane 13s0e, `367bc31`) | Test: `tests/e2e/bringing-up-twice-is-a-no-op-and-tearing-down-removes-every-container-network-and-volume-it-created.bats` |
| 13 · "DEMO: the Agent brings up a compose test environment from inside its container" (D9, Manual) | **unconfirmed** | Nobody has looked; the demo is the mentor's with the operator, after sign-off |

**Cycles 3 and 4, as the lane verified them** (from the feedback):
- 151, 88 and SC-1's first cell pass.
- The cold build passes, one image at a time, with uv's raised bound and its check.
- After the lane, there are no sandbox- or environment-labelled containers and no `timelike-sc8-*` volumes.
- The lock's holder is named.

**The host lanes, run before this report** (this cycle's code, uncommitted at the time; the commit is the same tree):
- **`make test-host`, serially:** passed, 05:16:03Z–05:25:38Z; 2584 passed, 13 skipped, in 541.76 s; env-layer 60/60,
  hook 57/57, handler 33/33.
- **The same with `-n 8`:** passed, 05:25:38Z–05:27:55Z; 2568 passed, 13 skipped, in 135.98 s, and the 16 `timed`
  tests passed, run alone.
- **ruff 0.16.7** `check` and `format --check` over `tools tests scan bench scripts`: all checks passed, and 126
  files were already formatted.
- **Not run:** the Docker lane, `make scan`, `make lint` with the pinned ruff 0.16.9, mypy, and shellcheck (which
  is not on this host).

**not_verified:**
- **That the pinned ruff 0.16.9 agrees with 0.16.7** on the four wrapped lines. That is the lint step's to show.
- **Whether `E2E_JOBS=4` stays clean beyond one lane:** 13s0f is the second run.
- **C's ending in 13s0e:** read as consistent with 12s1's cause, not confirmed.
- **D9:** the demo is still to come.

**changed_other_features:**
- **maint-lane-speed:** `E2E_JOBS`' default is 4, and its unit expects 4.
- **Others:** none.

**process_failures_recorded:**
- **Cycle 4 committed a lint failure.** It listed `make lint` as not run, but ruff is on this host (`lint-host`'s
  fallback), and running it would have caught all four lines. From now on, ruff `check` and `format --check` over the
  lint's paths run before each commit here.

**retired_prompts_seen:** none.

**After this report:** no commits until the mentor says the next lane has ended. Merge `--no-ff` only after sign-off.

### Cycle 5 — sign-off addendum

**Written:** 2026-10-18T11:34:48Z (read from the clock), from the mentor's
`../bridge/feedback/13-20261018-113014-slice-0-signed-off.md`. **Feature 13 slice 0 is signed off at `49b5e76`**
(Cycle 5), built from `bridge/sends/13-rev17-20261017-035606.md`. Append-only: nothing above is changed.

**The lane, 13s0f on `49b5e76`:**
- lint exit 0, scan exit 0 (all five images PASS), unit and gounit green;
- e2e 732 of 733. The one not ok was 517, SC-3 `[bash -lc]` (feature 001's, not this slice's): a 0.22 s git call
  took 22.95 s on a stalled host disk. The mentor ruled it environmental: the cell passed in 13s0b and 13s0e, and
  Cycle 5 changed no product or e2e file.
- 13s0e on `367bc31` was 733 of 733 on the same product and e2e code.

**criteria_reestablished, at sign-off** (these supersede Cycle 5's modes for the same criteria):

| Criterion | Mode | Evidence |
|---|---|---|
| `13 · "Bringing up a fixture project's compose file from inside the agent container starts its services and returns once they are ready"` | **executed [lane 13s0f]** | `tests/e2e/bringing-up-a-fixture-projects-compose-file-starts-its-services-and-returns-once-ready-listing-each-service-and-address.bats` |
| `13 · "runs the nested environment's containers with the agent's workspace mounted at the same absolute path"` | **executed [lane 13s0f]** | `tests/e2e/nested-containers-run-with-the-agents-workspace-mounted-at-the-same-absolute-path.bats` |
| `13 · "is refused by Adele with exit 2 and rule 14's structured error, naming the setting and stating that no grant allows it"` | **executed [lane 13s0f]** | `tests/e2e/privileged-host-network-or-namespace-added-capabilities-or-mount-outside-the-workspace-refused-by-adele-with-exit-2-naming-the-setting.bats` |
| `13 · "A pre-commit hook and a `core.hooksPath` or `core.fsmonitor` setting written by the Agent in its workspace do not run"` | **executed [lane 13s0f]** | `tests/e2e/agent-written-hooks-and-executing-git-config-do-not-run-in-the-operators-own-checkout-unless-lifted.bats` |
| `13 · "Bringing the environment up twice is a no-op the second time, and tearing it down removes every container, network and volume it created"` | **executed [lane 13s0f]** | `tests/e2e/bringing-up-twice-is-a-no-op-and-tearing-down-removes-every-container-network-and-volume-it-created.bats` |
| `13 · "DEMO: the Agent brings up a compose test environment from inside its container, runs tests against it, and tears it down"` (D9) | **observed by the operator** | transcript `bridge/.d9-demo-20261018T110127Z.txt` (run 1, which failed on the mentor's own demo project, is kept beside it) |

The cell 13s0f missed (517) belongs to none of these criteria. 13s0e's 733 of 733 on the same product and e2e code
covers it.

**D9, as demonstrated:**
- The agent's own project was brought up through `adele env up`, with no Docker in the agent: a notes API on a named
  volume, a one-shot seed job, and four tests.
- It was tested from the agent's container against `api.tl-notes-347b48:8080` (4 OK), and a second up created nothing.
- It was torn down with 0 containers, networks and volumes left. Adele read that back, and so did the mentor's label
  filters on the host.
- Ledger rows #131 (up) and #132 (down), session d9-demo.
- **The operator's answers**, quoted in the feedback:
  1. "api at api.tl-notes-347b48:8080 and seed, /var/lib/docker/volumes/tl-notes-347b48_notes/_data -> /home/agent".
     The address is right. The mount quoted is the notes volume; the project folder's line is the bind mount above
     it, at the same absolute path in both. D9 does not rest on that half: the same-path criterion is Automated, and
     executed by the lane.
  2. "http://api.tl-notes-347b48:8080, Ran 4 tests in 0.013s OK".
  3. "131, 132, 2 containers, 1 networks, 1 volumes removed; 0 left, read back from the daemon".

**The operator's decisions:**
- **A. The libcurl acceptance holds.**
  - Only Adele has the socket mounted.
  - Her image is `adeled` and `docker-compose`: Go, static, no libcurl. Her scan passes and accepts nothing.
  - `timelike-nested` is internal.
  - The agent's libcurl entries stay baselined until 2026-12-27.
- **B. Item 30 is approved:** Compose v5.6.0 built from source, its sum pinned, x/net raised to v0.60.0, static.
  `FOR-MENTOR.md` closes Item 30 in this commit. Return to a released Compose when one ships with a fixed Go and
  x/net; that is a pin change back.
- **C. Carried to the 13 slice 1 send, not fixed now:** `adele env up` counts a service with no healthcheck and no
  ports as ready while it runs.
  - So a one-shot that is still running is reported "ready (running)", and up exits 0. In the demo's run 1 the seed
    job then exited 1, and only the second up said so.
  - README says a one-shot is ready when it exits 0, which is true only of one that has already exited.
  - The slice 1 send will ask for the rule and the README to agree.
- **D. README's Next line** is now `**Next:** 13 slice 1.` Nothing else in the README changed.

**Still carried, not this feature's:**
- open item 1, 002's bench unit, for the maintenance send after 13;
- Item 28, build brokering, for the 13 slice 1 send.

**Next:** the merge `--no-ff` into `master`, no push and no tag. The push with tag `v0.22.0` waits for the
mentor's discharge and the operator's OK.

**The ship, `/specswarm:ship` under specswarm 4.0.1-botbaubble.2.44.0, at `026727e` before this text was added** (its blocks
extracted from the installed `analyze-quality.md` and `ship.md` and run, as in 002 Cycle 4; the modules are the
ones this feature changed). The output, verbatim, with the checkout path written `<repo>/`:

```
== analyze-quality (2.44.0 blocks) ==
🔤 Language: Python
AQ_TESTS_LINE=tests|25|?|measured:pytest
AQ_TESTS_SCORE=unavailable:pytest is declared but could not be run on this machine
adele/internal/engine|unknown
tools/bin|unknown
adele/internal/broker|unknown
image|unknown
scripts|unknown
adele/internal/ledger|unknown
tests/e2e|unknown
adele/cmd/adeled|unknown
Overall Quality: unknown (no module could be scored (8 unscored))
📄 Wrote <repo>/.specswarm/features/014-nested-dev-env/quality-report.json (overall_state: unknown, coverage_state: unknown, written by 4.0.1-botbaubble.2.44.0)
== ship (2.44.0 blocks) ==
📍 Current branch: 014-nested-dev-env @ 026727e
NOTE: <repo>/.specswarm/features/014-nested-dev-env/quality-report.json reports overall_state='unknown' - the score is not a measurement
📋 Using project quality threshold: 0% (from min_quality_score)
ℹ️  enforce_gates: false — a failing gate will WARN, not block

🎯 Quality Threshold: 0%
📊 Actual Quality Score: unknown — nothing was measured

❔ Quality gate UNKNOWN — the analysis reported no number
   <repo>/.specswarm/features/014-nested-dev-env/quality-report.json says overall_state='unknown'
   (no module could be scored (8 unscored))

   Nothing was measured. This is NOT a 0% failure and NOT a pass.


🔧 What would change this:
  - no component of this Python project could be measured: pytest is declared but could not be run on this machine
  - re-running /specswarm:analyze-quality will NOT change this result

⚠️  enforce_gates: false — this gate WARNS and does not block the merge.
   Shipping with quality state 'unknown' is the project's recorded choice, not an oversight.

== QUALITY_STATE=unknown ==
```

- **The gate is UNKNOWN, and it warns because `enforce_gates: false`.** Nothing was measured: it is neither a pass
  nor a 0% failure. pytest is not beside the interpreter the analysis finds on this host, and the Go modules have no
  detector in it.
- **`quality-report.json`** is written by the analysis into this feature's folder (`overall_state: unknown`) and
  committed here, as 002's was.
- **The merge is by hand,** `--no-ff`, of this commit, which is the signed-off `49b5e76` plus these records.
