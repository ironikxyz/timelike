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

- [ ] T008 [US1] Broker: `docker.compose` up and down, `/v1/envs` (`adele/internal/broker/env.go`, `broker.go`, `http.go`); `adeled serve` wires the engine and sandbox image (`adele/cmd/adeled/serve.go`); units `adele/internal/broker/env_test.go`
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
- [ ] T020 Host lanes (`make test-host` serial and `-n 8`), Go units and vet; the cycle report; `reboot.md`; the deny-list on the staged tree; commit

## Dependencies

T001–T002 → T003–T007 → US1 (T008–T012) → US2, US3, US5, US4/6 (each independent after US1) → Polish.
