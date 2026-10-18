# Tasks: 014 nested dev environments (prompt 13, slice 0)

<!-- Tech Stack Validation: PASSED -->
<!-- Validated against: .specswarm/tech-stack.md v1.7.0 -->
<!-- No prohibited technologies found -->
<!-- 0 unapproved technologies require runtime validation -->

**Input:** `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/adele-env.md`. Tests are requested (H7:
every criterion is a test). Paths are relative to the repository root.

## Phase 1: Setup

- [X] T001 Adele's image gains the Compose CLI from `DOCKER_CLI_IMAGE`, refused unless static (`adele/Dockerfile`; `compose.yaml` build arg; R1)
- [X] T002 [P] The launcher `scripts/workspace.sh` (R9): parent from `TIMELIKE_WORKSPACES` or `local.env`, a new directory per launch, `TIMELIKE_HOST_GIT` enforced or lifted, the work-tree refusal; `local.env` git-ignored

## Phase 2: Foundational (blocks every story)

- [X] T003 `docker.compose` in `grants.KnownCapabilities`; `Ledger.LiveOf(grant, capability)` (`adele/internal/grants/grants.go`, `adele/internal/ledger/query.go`)
- [X] T004 The Engine API client over the unix socket (`adele/internal/engine/engine.go`): sandbox run, image inspect, labelled list, label-scoped down, network inspect
- [X] T005 The compose model package (`adele/internal/compose/`): names, the refusal list (R3), the bind sources, label and network injection (R5), the resolve document; units in `adele/internal/compose/*_test.go`
- [X] T006 `adeled resolve` (`adele/cmd/adeled/resolve.go`), the sandbox's entrypoint (R2)
- [X] T007 `compose.yaml`: Adele's socket, group and workspace env; the agent's workspace mount at the same path, group, labels, env and `timelike-nested`; the network; `Makefile` `up` through the launcher, with `TIMELIKE_DOCKER_GID`

## Phase 3: US1, bring up, use, tear down (criteria 1 and 2; D9)

- [X] T008 [US1] Broker: `docker.compose` up and down, `/v1/envs` (`adele/internal/broker/env.go`, `broker.go`, `http.go`); `adeled serve` wires the engine and sandbox image (`adele/cmd/adeled/serve.go`); units `adele/internal/broker/env_test.go`
- [X] T009 [US1] The client: `adele env up|status|down` with the readiness loop and port probes (`tools/bin/adele`); status's "operator's command: none" for an empty extend; units `tests/unit/test_adele_env_cli.py`
- [X] T010 [US1] Lane: the launcher before `up`, the runner's workspace mount and env (`tests/run.sh`); nested grants (`tests/e2e/fixtures/adele/grants.conf`); fixtures (`tests/e2e/fixtures/nested/`); helpers (`tests/e2e/helpers.bash`)
- [X] T011 [US1] e2e `tests/e2e/bringing-up-a-fixture-projects-compose-file-starts-its-services-and-returns-once-ready-listing-each-service-and-address.bats`
- [X] T012 [US1] e2e `tests/e2e/nested-containers-run-with-the-agents-workspace-mounted-at-the-same-absolute-path.bats`

## Phase 4: US2, dangerous settings (criterion 3)

- [X] T013 [US2] e2e `tests/e2e/privileged-host-network-or-namespace-added-capabilities-or-mount-outside-the-workspace-refused-by-adele-with-exit-2-naming-the-setting.bats`

## Phase 5: US3, idempotent up and complete down (criterion 5)

- [X] T014 [US3] e2e `tests/e2e/bringing-up-twice-is-a-no-op-and-tearing-down-removes-every-container-network-and-volume-it-created.bats`

## Phase 6: US5, the operator's git (criterion 4)

- [X] T015 [US5] e2e `tests/e2e/agent-written-hooks-and-executing-git-config-do-not-run-in-the-operators-own-checkout-unless-lifted.bats`; units `tests/unit/test_workspace_launcher.py` (real git: enforced refuses, lifted allows)

## Phase 7: US4 and US6, never ready, beyond the grant, expiry

- [X] T016 [US4] Reaper: providers by capability, the compose provider (`adele/internal/reaper/reaper.go`, `adele/cmd/adeled/serve.go`, `ops.go`); units
- [X] T017 [US4] e2e `tests/e2e/nested-environment-beyond-the-grant-refused-never-ready-exits-124-and-expired-reaped.bats`

## Phase 8: Polish

- [X] T018 Feature 004's isolation and network assertions follow the new topology (agent: state volume plus workspace bind; networks plus `timelike-nested`; Adele: plus the socket); `tests/e2e/lane.conf` lines; `Makefile` `SHELLCHECK_FILES`
- [X] T019 README: the status block (if all five Automated criteria are built), the section, the regenerated reference (`scripts/readme_reference.py --write`); `adele/grants.example.conf`
- [X] T020 Host lanes (`make test-host` serial and `-n 8`), Go units and vet; the cycle report; `reboot.md`; the deny-list on the staged tree; commit

## Phase 9: Cycle 2, lane 13s0a's findings (`../bridge/feedback/13-20261017-063803-lane-13s0a-fails.md`)

- [X] T021 A: the sandbox and the setting check take no lock; Envs' lock covers the live check to the ledger write, and a down of a name waits for an up of it; a request given up before creating stops, one that has started creating is finished and recorded; the sandbox's errors name their phase and say whether its own bound passed, and the remedy names make build only for a missing image; Adele's timings in up's answer and the client's data (`adele/internal/broker/env.go`, `adele/internal/engine/engine.go`, `tools/bin/adele`); units; the bring-up JSON cell prints them, measured and not asserted
- [X] T022 B: a bring-up's empty project directory and compose's HOME under Adele's state directory, not /tmp (`adele/cmd/adeled/serve.go`, `env.go`); unit
- [X] T023 C: the operator's git is `timelike-operator-git:local`, built by the runner step from the pinned CLI image (`tests/runner/Dockerfile`, `tests/run.sh`); safe.directory names the repository's work tree and its `.git`; hooks say on stderr that they ran; project directories are 2775 so the lifted operator can write; the cells assert the git operations happened (`tests/e2e/agent-written-…bats`, `tests/e2e/nested.bash`); README's safe.directory sentence; lane unit
- [X] T024 E: Compose built from source at v5.6.0 with x/net v0.60.0 by GO_IMAGE's Go, sum-checked, refused unless static and carrying the pinned x/net (`adele/Dockerfile`, `pins.env`, `compose.yaml`); FOR-MENTOR Item 30
- [X] T025 Item 29 closed against plan `eab79e9`; D answered in the cycle report
- [X] T026 Host lanes (serial and `-n 8`), Go units and vet; Cycle 2's report; `reboot.md`; the deny-list on the staged tree; commit

## Phase 10: Cycle 3, lane 13s0b's findings (`../bridge/feedback/13-20261017-153646-lane-13s0b-fails.md`)

- [X] T027 A: a sandbox whose create the daemon finishes after the bound is removed by name when it lands, and one whose remove did not answer is tried again (`adele/internal/engine/engine.go`); serve sweeps sandboxes older than their bound and that removal at start and every 5 minutes (`adele/cmd/adeled/serve.go`); a sandbox overrides the compose labels it inherits from Adele's image with empty values; the remediation says no environment was created, not that nothing was; up's timings name what held Envs' lock (`lock_held_by`), and the bring-up JSON cell prints it, measured and not asserted; units
- [X] T028 D: every ledger write is one IMMEDIATE transaction, tried again while the file stays busy past the busy timeout, up to `WriteWait` (60 s) (`adele/internal/ledger/ledger.go`); unit
- [X] T029 C: SC-1's 60-commit history is made once in setup_file and copied by each cell (`tests/e2e/fixtures/sc1-repo.sh`, `tests/e2e/git-log-diff-commit-rebase-exit-within-20-seconds.bats`)
- [X] T030 E: `build_runner` carries the SC2329 directive the other step functions carry (`tests/run.sh`)
- [X] T031 SC-8's volumes are created labelled as throwaways; the parallel lane's start removes labelled throwaway volumes and SC-8's unlabelled ones by their exact name shape (`tests/run.sh`, the SC-8 snapshot bats)
- [X] T032 Host lanes (serial and `-n 8`), Go units with -race and vet; Cycle 3's report; `reboot.md`; the deny-list on the staged tree; commit

## Phase 11: Cycle 4, lanes 13s0c and 13s0d stopped at the build (`../bridge/feedback/13-20261018-030300-build-disk-bound-uv-compile-timeout.md`)

- [X] T033 Every `--compile-bytecode` carries `UV_COMPILE_BYTECODE_TIMEOUT=300`, refused at build time by a uv that does not read it (`image/Dockerfile` twice, `bench/vanilla/Dockerfile`, `bench/driver/Dockerfile`); the agent image's second compile waits for its first through a bind mount of the runtimes stage
- [X] T034 `make build` builds the compose images one at a time, `BUILD_SERVICES` (`Makefile`; `tests/run.sh`'s header); unit `tests/unit/test_build_one_image_at_a_time.py`
- [X] T035 Host lanes (serial and `-n 8`); Cycle 4's report, with the answer on `E2E_JOBS`; `reboot.md`; the deny-list on the staged tree; commit

## Phase 12: Cycle 5, lane 13s0e's findings (`../bridge/feedback/13-20261018-051500-lane-13s0e-e2e-green-lint-e501.md`)

- [X] T036 A: the four E501 lines in `tests/unit/test_build_one_image_at_a_time.py` wrapped; ruff check and format over the lint's paths
- [X] T037 B: `E2E_JOBS`' default 4, on the mentor's ruling (`tests/run.sh`); `tests/unit/test_lane_run_sh.py`'s parallel lane expects 4
- [X] T038 Host lanes (serial and `-n 8`); Cycle 5's report, with C read from the lane's log; `reboot.md`; the deny-list on the staged tree; commit

## Dependencies

T001–T002 → T003–T007 → US1 (T008–T012) → US2, US3, US5, US4/6 (each independent after US1) → Polish.
