# Tasks: 001 agent shell baseline & output contract (slice 0)

<!-- Tech Stack Validation: PASSED -->
<!-- Validated against: .specswarm/tech-stack.md v1.2.0 -->
<!-- No prohibited technologies found -->
<!-- 0 unapproved technologies require runtime validation -->

**Input:** `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`
**Tests:** required (constitution H7: every acceptance criterion is a test, named after its
distinguishing text). Within each story, tests come before implementation.

## Format: `[ID] [P?] [Story] [Lane] Description`

- **[P]** — can run in parallel: a different file with no dependency on an incomplete task
- **[Story]** — US1–US6 map to SC-1–SC-6. US1 also carries SC-7, the demo
- **[Lane]:**
  - **H**: completable and verifiable on this host (Python 3.12, no Docker)
  - **D**: **needs a Docker daemon** to verify (research R10). Code can still be *written* here; it
    counts as verified only once the Docker lane runs it

All paths are relative to the repository root, `code/`.

## User stories (from spec.md scenarios)

| Story | Priority | Criterion | Spec scenario |
|---|---|---|---|
| US1 | P1 | SC-1 + SC-7 DEMO | Git never waits on a person |
| US2 | P1 | SC-2 | Defaults hold however the shell is started |
| US3 | P1 | SC-3 | Credentials fail fast; hooks off |
| US4 | P1 | SC-4 | The agent cannot escalate |
| US5 | P2 | SC-5 | Every tool speaks the same contract |
| US6 | P2 | SC-6 | Peer agents do not collide |

---

## Phase 1: Setup (shared infrastructure)

- [X] T001 [H] Create the repository skeleton per plan.md § Source code: `image/`, `image/rootfs/etc/profile.d/`, `tools/agentio/`, `tools/bin/`, `tests/{unit,e2e,fixtures/bad-tool,host,runner}/`, `scan/`. Add `.gitignore` entries for `.pytest_cache/`, `__pycache__/`, `scan/out/`
- [X] T002 [H] Create `pins.env` at the repository root. It is the single source of every pinned digest and version from research.md R9: debian, uv, CPython, bats, docker-cli, shellcheck, syft, grype, gitleaks, pip-audit, ruff, mypy. The Makefile passes each one as a build argument or image reference
- [X] T003 [H] Create a `Makefile` with the targets `build up down test test-host lint scan demo`
  - It reads `pins.env`
  - `build` passes `--build-arg GIT_SHA=$(git rev-parse HEAD)` and **fails before building** if the value is empty or the working tree is dirty and `ALLOW_DIRTY` is not set (H8; lore cross-stack P003)
  - Every target that needs Docker checks `docker info` first. When it fails, it exits 1 with `error: no Docker daemon reachable (code 1) — mount the host socket or set DOCKER_HOST; see research.md R10`. It never hangs
- [X] T004 [P] [H] Add lint configuration:
  - `pyproject.toml` with ruff settings and `[tool.mypy] strict = true`, python 3.12, files `tools/`
  - `.shellcheckrc`

  `make lint` runs ruff, mypy and shellcheck in pinned containers (lane D). Also add a `lint-host` fallback that uses the host's `ruff` if present
- [X] T005 [P] [D] Create `tests/runner/Dockerfile`: `FROM bats/bats:1.14.0@sha256:5322b877…`, then `COPY --from=docker:29.8.1-cli@sha256:018edbc9… /usr/local/bin/docker /usr/local/bin/docker` (research R8)

## Phase 2: Foundational (blocks every story)

**Purpose:** the contract module (H2: it comes before any tool) and the agent image that every
criterion runs in.

### agentio — contract rules 1–16

- [X] T006 [H] Write the failing pytest suite `tests/unit/test_agentio.py`, covering `contracts/output-contract.md` rule by rule:
  - Mode selection (1): `--json`/`--text` override, and a pipe means JSON
  - Cap and omission line (2): `--limit` and `TIMELIKE_OUTPUT_LIMIT`
  - Truncation order (3)
  - No tty access (4): monkeypatch `open` to fail on `/dev/tty`
  - Exit vocabulary (5): an uncaught exception gives exit 1 with a structured error
  - `--help` of at most 40 lines, and `--agent-info` valid against `agent-info.schema.json` (6)
  - The confirm envelope with exit 4 (9)
  - Scratch path and mode 0700 (10)
  - Sorted output and no timestamps without `--verbose` (11)
  - The header regex (12)
  - ANSI strip and `COLUMNS` cut with the byte count (13)
  - Error on stderr, in both forms (14)
  - `[REDACTED:<type>]` (15)
  - Events (16): exactly one line per invocation, valid against `event.schema.json`, written after the result
  - FR-11: event-write failure, e.g. an unwritable scratch directory, leaves the exit code unchanged
  - Session id validation: an invalid id exits 2

  Validate against the schemas with a small stdlib-only checker in `tests/unit/schema.py`. There are no third-party runtime dependencies (H5)
- [X] T007 [H] Implement `tools/agentio/agentio.py`, stdlib only and `mypy --strict` clean, until T006 passes. Provide:
  - a `Tool` class (name, target, scope, summary, usage, flags, exit codes, `mutating`/`destructive`/`reads_stdin`, probe)
  - a `run(main)` entry point that owns argument parsing for the common flags, mode selection, capping, truncation, error rendering, exit mapping and the event write
  - `redact(value, type)`
  - `session()` and `scratch_dir()`
- [X] T008 [H] Add `tests/unit/test_agentio_startup.py`: importing `agentio` and running a trivial tool under `python3 -I` takes < 100 ms p95 over 50 runs on this host. It records the host figure as advisory (quality-standards C2 says re-measure in the image; T042 does that)

### Agent image

- [X] T009 [D] Write `image/Dockerfile`. **R2 cross-check:** before writing it, confirm uv 0.12.19 offers CPython 3.12.14 (`uv python list`, run in the uv image); if not, pin the newest 3.12 it offers and update `pins.env` and research.md R9. Build steps:
  1. `FROM debian:trixie-slim@sha256:a99cfc51…` (from `pins.env` via `ARG`)
  2. Install only `git`, `ca-certificates`, `openssh-client`, `util-linux` (setsid, setpriv) and `procps`, with `--no-install-recommends`. **Do not** install sudo, nft or iptables
  3. uv, `uv python install 3.12.14 --install-dir /opt/uv-python --no-bin`, then the symlink `/opt/timelike/python` (R6). Fail the build if an `EXTERNALLY-MANAGED` marker would block the `agentio` install
  4. Copy `tools/agentio/agentio.py` into the interpreter's site-packages. Copy `tools/bin/*` to `/opt/timelike/bin/` (0755)
  5. Create the users. `adele` is uid/gid 10001 with no login shell; `/var/lib/adele` is 0700 `adele:adele`, and `fixture.secret` is 0600. `agent` is uid/gid 1000, in no supplementary privileged group
  6. `RUN find / -xdev -perm /6000 -type f -exec chmod a-s {} +`, then `RUN test -z "$(find / -xdev -perm /6000 -type f)"` (R7)
  7. `ARG GIT_SHA` then `RUN test -n "$GIT_SHA"`. Write `/opt/timelike/REVISION` (0444) and `LABEL org.opencontainers.image.revision=$GIT_SHA` (H8)
  8. The `ENV` block exactly as in research R1–R5, with PATH starting `/opt/timelike/bin` and `TIMELIKE_BIN_DIRS=/opt/timelike/bin`
  9. `COPY image/rootfs/ /`
  10. `USER agent`, `WORKDIR /home/agent`
- [X] T010 [P] [H] Write `image/rootfs/etc/gitconfig`: `core.editor=true`, `core.pager=cat`, `core.hooksPath=/dev/null`, `sequence.editor=true`, `color.ui=never`, an empty `credential.helper` (R2–R4, fallback layer)
- [X] T011 [P] [H] Write `image/rootfs/etc/profile.d/00-timelike-path.sh`, which prepends `/opt/timelike/bin` to PATH idempotently (R1). It must be shellcheck clean
- [X] T012 [D] Write `compose.yaml`. Service `agent`:
  - `container_name: timelike-agent`
  - built from `image/Dockerfile` with the `GIT_SHA` build argument
  - `cap_drop: [ALL]`, `security_opt: [no-new-privileges:true]`, default seccomp
  - `init: true`, `read_only: false`
  - `command: sleep infinity`
  - no socket mounts
- [X] T013 [D] Write `tests/e2e/helpers.bash`. `run_in STYLE TTY CMD` runs CMD through `docker exec [-t] timelike-agent` as `bash -c`, `bash -lc` or `bash -ic`, wrapped in `timeout 30` (a hang becomes rc 124 and a failure) and with stdin at `/dev/null` when there is no tty. Also provide `stamp_check`: the image's revision label equals `git rev-parse HEAD`, so bats never runs against a stale image (lore docker-compose Q004; cross-stack P004)
- [X] T014 [D] Write `tests/run.sh`, the Docker lane. It checks `docker info`, runs `make build`, runs `docker compose up -d --build --force-recreate`, builds the runner, runs `bats tests/e2e` from the runner with the socket and `code/` mounted, then runs `pytest tests/unit` in the agent image's interpreter. Exit status: the failure of any of these steps. It is shellcheck clean

**Checkpoint:** `agentio` passes its unit tests (H). The image builds with a non-empty stamp and no
setuid binaries (D).

---

## Phase 3: US1 — Git never waits on a person (P1) · SC-1, SC-7

**Goal:** `git log`, `git diff`, `git commit` without a message and `git rebase --continue` each
conclude within 20 s without a pager or editor.
**Independent test:** `tests/e2e/git-log-diff-commit-rebase-exit-within-20-seconds.bats` passes in
every invocation style, both with and without a TTY.

- [X] T015 [US1] [D] Write the bats file `tests/e2e/git-log-diff-commit-rebase-exit-within-20-seconds.bats`
  - **Setup** (via `run_in`, in a temp directory in the container): a repository with more than one screen of history, and a branch with a conflict to rebase
  - **For each style × TTY**, assert that each of the following finishes in < 20 s (measured), does not exit 124, and produces no pager or editor process (`pgrep -f 'less|vi|nano|editor'` is empty during and after):
    - `git log` and `git diff` exit 0 and print directly
    - `git commit` with no `-m` exits 1, and its output contains "Aborting commit due to empty commit message"
    - `git rebase --continue`, after the conflict is resolved and staged, exits 0 and completes with the existing message
- [X] T016 [US1] [D] Ensure T009's `ENV` block carries `GIT_EDITOR=true`, `GIT_SEQUENCE_EDITOR=true`, `GIT_MERGE_AUTOEDIT=no`, `GIT_PAGER=cat` and `PAGER=cat` (R2), and that T010 carries the fallbacks. Make T015 pass
- [X] T017 [P] [US1] [D] Write `scripts/demo.sh`, invoked by `make demo` for SC-7. Inside the container, with and without a TTY, it runs `git commit`, `git rebase --continue` and `git log`, and prints each command's rc and elapsed seconds. It is for a person to **watch**; it is not asserted

**Checkpoint:** SC-1 green in the Docker lane. SC-7 ready to be observed.

## Phase 4: US2 — Defaults hold however the shell is started (P1) · SC-2

**Goal:** the pager, editor, prompt and colour defaults are in effect in `bash -c`, `bash -lc` and
interactive shells.
**Independent test:** `tests/e2e/bash-c-and-bash-lc-defaults-in-effect.bats`, with one test per
invocation style.

- [X] T018 [US2] [D] Write the bats file `tests/e2e/bash-c-and-bash-lc-defaults-in-effect.bats`, with **one `@test` per style**: `bash -c`, `bash -lc`, `bash -ic`, and also `sh -c`
  - Each asserts `command -v timelike` resolves to `/opt/timelike/bin/timelike`. This catches the PATH reset by `/etc/profile`
  - Each asserts these values: `git var GIT_EDITOR` = `true`, `git var GIT_PAGER` = `cat`, `$PAGER` = `cat`, `git config --get color.ui` = `never`, `$NO_COLOR` = `1`, `$GIT_TERMINAL_PROMPT` = `0`, `$DEBIAN_FRONTEND` = `noninteractive`
  - Each test's name contains its style
- [X] T019 [US2] [D] Make T018 pass. Put every default except PATH only in `ENV`, and put PATH in both `ENV` and `00-timelike-path.sh`. Do not add rc-file or `PROMPT_COMMAND` defaults. Adding one to make a test pass is a violation of FR-1
- [X] T020 [P] [US2] [H] Write the host lane `tests/host/test_env_layer.sh`. It extracts the `ENV` block from `image/Dockerfile` and runs `env -i` with those variables, with `GIT_CONFIG_SYSTEM=image/rootfs/etc/gitconfig` and `GIT_CONFIG_GLOBAL=/dev/null`, in `bash -c`, `bash -lc` (with a temporary `/etc/profile` stand-in that resets PATH as Debian's does) and `bash -ic`, asserting T018's values
  - **Advisory:** it proves the files, not the image
  - The script's output says so in its first line

**Checkpoint:** SC-2 green in the Docker lane. The host lane is green as file evidence.

## Phase 5: US3 — Credentials fail fast; hooks off (P1) · SC-3

**Goal:** credential needs fail non-zero quickly, and repository hooks don't run unless explicitly
enabled.
**Independent test:** `tests/e2e/credentials-fail-fast-and-hooks-off.bats`

- [X] T021 [US3] [D] Write the bats file `tests/e2e/credentials-fail-fast-and-hooks-off.bats`
  - **Credentials:** `git ls-remote` against an https URL that needs auth, and against an ssh URL. Each is run under both TTY modes and must exit non-zero in < 10 s and not 124. Use a local credential-demanding fixture if there is no network: `git -c http.extraHeader=` against an unreachable host is not enough, because a network failure is not a credential prompt. Record which was used, and if the network is absent, mark the https case `skip` with the reason rather than passing it
  - **Hooks:** a repository with a failing `pre-commit` hook **and** a local `core.hooksPath=.git/hooks`. `git commit -m x` succeeds, so the hook did not run
  - **Explicit enable:** `git -c core.hooksPath=.git/hooks commit -m y` fails, so the hook ran
- [X] T022 [US3] [D] Make T021 pass through the `ENV` block:
  - `GIT_TERMINAL_PROMPT=0`, `GIT_ASKPASS=`, `SSH_ASKPASS=`, `GCM_INTERACTIVE=never`
  - `GIT_SSH_COMMAND="ssh -o BatchMode=yes -o ConnectTimeout=15"`
  - `GIT_CONFIG_COUNT=1`, `GIT_CONFIG_KEY_0=core.hooksPath`, `GIT_CONFIG_VALUE_0=/dev/null` (R2, R3)

**Checkpoint:** SC-3 green in the Docker lane.

## Phase 6: US4 — The agent cannot escalate (P1) · SC-4

**Goal:** no root, no firewall change, no reading of Adele's files.
**Independent test:** `tests/e2e/agent-cannot-run-as-root-change-firewall-or-read-adele.bats`

- [X] T023 [US4] [D] Write the bats file `tests/e2e/agent-cannot-run-as-root-change-firewall-or-read-adele.bats`. It reads the controls directly (lore cross-stack P001):
  - `/proc/self/status`: CapEff, CapPrm, CapBnd and CapAmb are all `0000000000000000`; `NoNewPrivs` is `1`; `Seccomp` is `2`
  - `id -u` is 1000, and `id -G` contains none of 0, 27 (sudo) or 10001
  - `find / -xdev -perm /6000 -type f` is empty
  - `command -v sudo` is absent
  - `su -c true root` fails
  - `unshare -r true` fails
  - Firewall: a netfilter probe `tests/fixtures/nfprobe.py`, run with the image's Python, opens `AF_NETLINK/NETLINK_NETFILTER`, sends one nfnetlink get, and expects `EPERM`
  - `cat /var/lib/adele/fixture.secret` fails with "Permission denied", and `ls /var/lib/adele` fails
  - Every assertion runs under `bash -c` and `bash -lc`
- [X] T024 [P] [US4] [H] Write `tests/fixtures/nfprobe.py`, stdlib only (`socket.AF_NETLINK`, protocol 12). It prints `EPERM`, `OK` or `<errno name>` and exits 0 on EPERM, 1 otherwise. Unit-test its message building on the host in `tests/unit/test_nfprobe.py`
- [X] T025 [US4] [D] Make T023 pass using T009 steps 2, 5 and 6 and T012's hardening. Nothing in the agent image may be added to satisfy the test other than removing privilege

**Checkpoint:** SC-4 green in the Docker lane.

## Phase 7: US5 — Every tool speaks the same contract (P2) · SC-5

**Goal:** `timelike-conform` checks every timelike tool on PATH and fails naming the tool and the rule.
**Independent test:** `tests/e2e/conformance-check-over-every-timelike-tool-on-path.bats`, plus the
unit tests.

- [X] T026 [P] [US5] [H] Write `tests/fixtures/bad-tool/timelike-bad`. It uses `agentio` but deliberately violates C1 (help of 45 lines), C5 (exits 1 on an unknown flag) and C7 (skips the event write). A second fixture, `timelike-hang`, sleeps 60 s on `--help`, and exists to prove the 10 s probe limit
- [X] T027 [US5] [H] Write the unit tests `tests/unit/test_conform.py`:
  - conform passes over a temporary bin directory holding only good tools
  - it exits 1 naming `timelike-bad` with C1, C5 and C7 when the bad directory is on PATH and in `TIMELIKE_BIN_DIRS`
  - `timelike-hang` gives the failure "did not conclude" within about 10 s, not 60
  - zero tools found exits 1
  - a directory in `TIMELIKE_BIN_DIRS` that is not on PATH is reported
  - the JSON output validates, and failures are sorted by tool and then check
- [X] T028 [US5] [H] Implement `tools/bin/timelike` (shebang `#!/opt/timelike/python/bin/python3 -I`; host tests invoke it with the host interpreter explicitly):
  - its default output is the header plus the contract version and the sorted list of timelike tools found on `TIMELIKE_BIN_DIRS` ∩ PATH
  - `--agent-info` adds `revision`, read from `/opt/timelike/REVISION` or `TIMELIKE_REVISION` in tests. An empty or missing revision exits 1 with a structured error (H8)
- [X] T029 [US5] [H] Implement `tools/bin/timelike-conform` per `contracts/conformance.md`, with checks C1–C8:
  - each probe is `setsid`, has stdin at `/dev/null`, uses a fresh session under a temporary scratch root, and has a 10 s limit
  - a `--list` probe
  - Make T027 pass
- [X] T030 [US5] [D] Write the bats file `tests/e2e/conformance-check-over-every-timelike-tool-on-path.bats`. In the image:
  - `timelike-conform` exits 0 over the shipped PATH, and checks at least 2 tools (`timelike` and itself)
  - `docker cp` the bad fixture into `/tmp/badbin`; with `PATH=/tmp/badbin:$PATH TIMELIKE_BIN_DIRS=/opt/timelike/bin:/tmp/badbin`, it exits 1 and names `timelike-bad` C1, C5 and C7
  - `timelike --agent-info | …revision` equals `git rev-parse HEAD`

**Checkpoint:** SC-5 green in both lanes. The host lane runs the units; the Docker lane runs the image
test.

## Phase 8: US6 — Peer agents do not collide (P2) · SC-6

**Goal:** concurrent sessions write only to their own scratch space and event log.
**Independent test:** `tests/e2e/peer-agents-write-to-own-scratch-space.bats`

- [X] T031 [US6] [H] Unit-test in `tests/unit/test_sessions.py`:
  - two concurrent sessions, `A` and `B`, run as parallel processes of 50 invocations each; each events file holds exactly its own 50 lines, and every line parses
  - session A's scratch directory has mode 0700
  - no file of A's appears under B's
  - an invalid session id (`../x`) exits 2
- [X] T032 [US6] [D] Write the bats file `tests/e2e/peer-agents-write-to-own-scratch-space.bats`. Two concurrent `docker exec` processes with `TIMELIKE_SESSION=peer-a` and `peer-b` each run `timelike` 20 times and write an output artefact. Assert:
  - each session's `events.jsonl` has exactly 20 lines, all with its own session id
  - each output file lives only under its own scratch directory
  - neither scratch tree contains the other's files
- [X] T033 [US6] [H] Make T031 and T032 pass in `agentio`: path purity, `O_APPEND` single-write lines, and 0700 creation

**Checkpoint:** SC-6 green in the Docker lane.

---

## Phase 9: Governance — supply-chain scan gate (the send's carried item; H9, not a criterion)

- [X] T034 [D] Write `scan/scan.sh`, invoked by `make scan`, using the pinned images from `pins.env`:
  1. Syft SBOM of the agent image → Grype, failing on a High or Critical **with a fix available** (`--only-fixed --fail-on high`)
  2. pip-audit over the image interpreter's installed packages, run via `uvx pip-audit==2.10.1` in a throwaway container. There are none beyond the stdlib today, which makes this a no-op pass that says so
  3. gitleaks over the repository (`detect --source /repo`), failing on any finding
  4. An unfixable High or Critical is allowed only if listed in `quality-standards.md` § Exemptions with its identifier, reason and review date. An overdue review date fails, pending plan's answer to FOR-MENTOR 5.2; the script says which rule applied

  Output goes to `scan/out/`, which is git-ignored. It follows H3: it parses Grype's JSON result and never trusts an exit message alone
- [X] T035 [P] [H] Unit-test the exemption parser: `tests/unit/test_scan_exemptions.py` over sample tables (valid, missing a field, overdue)
- [X] T036 [D] Run `make scan` against the built image and record the result in the cycle report (`changed_other_features` / `not_verified`, as the send directs)

## Phase 10: Polish & cross-cutting

- [X] T037 [P] [H] shellcheck-clean every `.sh`, `.bash` and `.bats` file via `lint-host` where possible; `make lint` is authoritative
- [X] T038 [P] [H] `ruff check` and `ruff format --check` are clean. `mypy --strict tools/` is clean (host `mypy`, if absent, only in the Docker lane: say so)
- [X] T039 [H] Verify the H8 stamp end to end: the Makefile refuses an empty `GIT_SHA`. In the Docker lane, the label equals `timelike --agent-info` revision equals `HEAD`
- [X] T040 [H] Document in a short `README.md` how to build and test, the two verification lanes, the Docker prerequisite, and that the contract lives in `contracts/output-contract.md`. It makes **no** value claims (P6)
- [X] T041 [H] Append the cycle report to `.specswarm/features/001-agent-shell-baseline/cycle-report.md`, in the send's format:
  - Group A: not applicable — no marker on this path
  - the five copied fields
  - the seven written fields
  - `criteria_reestablished` cites each SC by distinguishing text, with mode `executed [test]` **only if the Docker lane ran it**, otherwise `unconfirmed`, and SC-7 as `unconfirmed` unless someone watched it
  - `not_verified` names everything that needs the Docker lane
- [X] T042 [D] Re-measure tool start-up inside the image with `/opt/timelike/python/bin/python3 -I` (quality-standards C2), and record where it was measured in `quality-standards.md` Performance Budgets, preserving its frontmatter verbatim

---

## Phase 11: Cycle 2 — re-send `bridge/sends/01-rev2-20260928-131708.md` (discovery revision 5)

The prompt is unchanged at revision 2, and so are the spec and its criteria. This phase applies what moved
underneath it: discovery revision 5, `stack.md` at plan `d606ed1`, and the governance-only score ruling.
Governance itself was re-audited first (`d980e4d`: constitution 1.2.0, tech-stack 1.3.0).

- [X] T043 [P] [H] Pin Python to the current stable 3.14.x in `pins.env` (3.14.7: python.org and uv 0.12.19's download metadata both carry it). Update research.md R9 and the README's host-lane note. The Dockerfile's interpreter checks verify it in the Docker lane
- [X] T044 [P] [D] Remove `openssh-client` from the agent image (stack note 15), together with `GIT_SSH_COMMAND`, which has nothing left to configure. Rewrite the SC-3 ssh tests: git over ssh still concludes fast with no prompt, now because there is no ssh client, and no `ssh` is on PATH under any invocation style. The https credential tests stay unchanged
- [X] T045 [H] Revision 5 in the supply-chain gate: `scan/evaluate.py` replaces the exemptions table with a reviewed baseline per image (`scan/baseline/<image>.json`): a reason per origin group, a reason per Critical, one review date at most 90 days out, tied to the pinned base digest. New or newly fixable findings block. One summary line on every scan. A proposal is written to `scan/out/baseline.proposed.json`. `scan/scan.sh` passes the baseline and the base digest. Unit tests replace `tests/unit/test_scan_exemptions.py`
- [X] T046 [H] Draft `scan/baseline/timelike-agent.json` from the last real scan, less what T043 and T044 remove: the reasons per origin group and per Critical. `reviewed` stays unset for a person to fill in, because the baseline passes only once a person has reviewed it
- [X] T047 [D] Operator: `make build`, `make test` and `make scan` against the new image. Record the results in cycle-report.md, Cycle 2
- [X] T048 [H] Close `FOR-MENTOR.md` Item 6 finding 1 (the score ruling, applied in `d980e4d`) and Item 7 (once T045–T047 land). Update reboot.md

## Phase 12: Cycle 3 — slice 1 (natural), `bridge/sends/01-rev2-20260928-214635.md`, via `/specswarm:modify`

Branch `modify/001-slice-1` off `master`. Design: `modify.md` (F001–F007). Risks and limits:
`impact-analysis.md`. The spec gains SC-8–SC-11 and FR-15–FR-18.

- [X] T049 [H] Modify artifacts: `impact-analysis.md`, `modify.md`, and the slice-1 rows in `spec.md` (SC-8–SC-11, FR-15–FR-18, Assumptions 7–8, Out of Scope updated)
- [X] T050 [P] [D] SC-8/SC-9/SC-10 environment:
  - `image/rootfs/etc/timelike/shell-env.bash`: job counts from cgroup `cpu.max` and affinity, set only when unset; the secret strip with `TIMELIKE_ENV_ALLOW`; bash builtins only, idempotent
  - its wiring through `BASH_ENV` (ENV), `/etc/profile.d/10-timelike-shell-env.sh` and `/etc/bash.bashrc`
  - `TZ="UTC"` and `PYTHON_BASIC_REPL="1"` in the ENV block
- [X] T051 [P] [D] e2e `tests/e2e/container-derived-defaults.bats`:
  - SC-8 in a container started with a CPU limit below the host's count, including explicit-wins
  - SC-9 with an allow-listed name and a non-secret look-alike
  - SC-10: `date` and Python's REPL in a pty
  - each under `bash -c`, `bash -lc` and `bash -ic`
- [X] T052 [P] [H] `tests/host/test_env_layer.sh`: the new ENV keys and the hook's wiring. The hook's logic is unit-tested on the host against fake cgroup and status files
- [X] T053 [P] [D] Natural intensity: the common failure next to each happy path in the six slice-0 bats files (SC-1–SC-6). Report any product gap found; do not fix it silently
- [X] T054 [P] [H] In-image start-up figure (operator decision 1):
  - `test_agentio_startup.py` prints `TIMELIKE_STARTUP p95_ms=… runs=… python=… interpreter=…`
  - `tests/run.sh` runs the unit step with `-rP` and writes `tests/out/startup.json`
- [X] T055 [P] [H] SC-11 support: make the output contract findable for a person who has not seen a tool (README link, and `timelike --help` pointing to it if the contract allows). The criterion itself stays `unconfirmed` until a person looks
- [X] T056 [H] Close `FOR-MENTOR.md` Items 1–3 (operator decision 3)
- [X] T059 [H] Fix the product gap T053 found: `timelike-conform` crashed, naming no tool, on a tool whose interpreter cannot be executed (`run_probe`'s Popen was unguarded). An exec failure is now that tool's probe result (127 or 126), judged by the rules. Unit test for ENOENT and EACCES
- [X] T057 [D] Operator: `make test` and `make scan`. Then record the 3.14.7 start-up figure under quality-standards Performance Budgets (governance-only)
- [X] T058 [H] Cycle 3 report (`cycle-report.md`) and reboot.md

## Phase 13: Cycle 4 — revision 6, a clarification (send `bridge/sends/01-rev6-20260928-231531.md`)

The re-send continues Phase 12's cycle on `modify/001-slice-1`. T057 (the operator's run) happened at
`01ee1ce`; its figure is recorded by T064. Governance was audited against revision 6 first (`938a0d2`).

- [X] T060 [H] Modify artifacts for revision 6: impact-analysis and modify.md Cycle 4 sections. The criteria diff against the revision-2 send shows only rules 2–3 annotated
- [X] T061 [P] [H] `contracts/output-contract.md` states the uncapped case (F101)
- [X] T062 [P] [H] README: remove "does not fix that line yet"; describe the last line by its kind (F102)
- [X] T063 [H] spec.md: the two rule clarifications, and revision 6 recorded by modify Step 9 (audit-log.md) (F103)
- [X] T064 [H] quality-standards C2: the in-image start-up figure with its conditions, and evidence on whether the conditions make it slower (F105). Governance-only
- [X] T065 [H] Close FOR-MENTOR Item 8 (F104); Cycle 3 verification addendum and Cycle 4 report; reboot.md

## Dependencies

```
Setup (T001–T005)
  └─► Foundational: agentio T006→T007→T008 [H]   image T009–T014 [D]
        ├─► US1 (T015–T017)  ─┐
        ├─► US2 (T018–T020)   │ all four use the image and are independent of each other
        ├─► US3 (T021–T022)   │
        ├─► US4 (T023–T025)  ─┘
        ├─► US5 (T026–T030)  needs agentio (T007); its image test needs T009
        └─► US6 (T031–T033)  needs agentio (T007); its image test needs T009
  └─► Governance (T034–T036) needs the built image
  └─► Polish (T037–T041, T042) last
```

## Parallel opportunities

- Setup: T004 and T005 can run together.
- Foundational: T010 and T011 can run together, and alongside T006–T007 (different files).
- US5 and US6 (lane H) can run in parallel with image work: T026, T027, T031, T024 and T035.
- Once the image exists, the bats files T015, T018, T021, T023, T030 and T032 are all separate files.

**Example batch, lane H now:** T006 → T007, then run T024, T026, T027, T031 and T035 in parallel,
then T028 and T029.

## Implementation strategy

1. **MVP = Foundational + US1.** The contract module, the image, and git never waiting (the D1 demo).
2. Then US2–US4, all P1: invocation styles, credentials and hooks, privilege.
3. Then US5 and US6 (P2), then governance and polish.

**Given research R10 (no Docker daemon here):** all lane H tasks can be completed and verified now,
and lane D tasks can be written. Nothing lane D is reported as verified until the Docker lane runs.
That is 19 of 42 tasks: T005, T009, T012–T019, T021–T023, T025, T030, T032, T034, T036 and T042.

## Summary

| Phase | Tasks | Lane H | Lane D |
|---|---|---|---|
| Setup | 5 | 4 | 1 |
| Foundational | 9 | 5 | 4 |
| US1 | 3 | 0 | 3 |
| US2 | 3 | 1 | 2 |
| US3 | 2 | 0 | 2 |
| US4 | 3 | 1 | 2 |
| US5 | 5 | 4 | 1 |
| US6 | 3 | 2 | 1 |
| Governance | 3 | 1 | 2 |
| Polish | 6 | 5 | 1 |
| **Total** | **42** | **23** | **19** |


## Phase 14: Cycle 5 — repository hooks run, bounded (send `bridge/sends/01-rev7-20260929-094055.md`, via `/specswarm:modify`)

- [X] T066 Governance audited against discovery revision 7 (done before this branch, on `master` at
  `9688118`: constitution 1.3.0 adds T4; tech-stack and quality-standards no change). Recorded here.
- [X] T067 `image/rootfs/opt/timelike/git-hooks/dispatch` and its 25 links (research R11).
- [X] T068 `image/Dockerfile`: `GIT_CONFIG_VALUE_0=/opt/timelike/git-hooks`, and COPY the directory
  keeping the links (root-owned, 0755). `image/rootfs/etc/gitconfig`: hooksPath points at the same
  directory. Comments updated.
- [X] T069 Host units, `tests/unit/test_git_hook_dispatch.py`, with real git and the dispatcher in
  place:
  - a default-location rejecting hook; husky's local path
  - a hang stopped within limit + a few seconds, and its verdict (no skip suggestion)
  - both limit sources, and a bad value
  - a non-executable hook's hint; pre-push stdin
  - a linked worktree; no recursion; not in a repository
- [X] T070 E2E: `tests/e2e/credentials-fail-fast-and-hooks-off.bats` keeps its credentials half, and
  its hooks half is removed. New `tests/e2e/hooks-a-repository-configures-run.bats` (SC-12) and
  `tests/e2e/hook-past-its-time-limit-is-killed.bats` (SC-13), per style c/lc/ic in `notty`. Add both
  to `SHELLCHECK_FILES` where the Makefile lists bats files.
- [X] T071 Feature 002:
  - `bench/benchlib/catalog.py`: difference texts, notes and expected verdicts for both hook tasks
  - `runner.Limits.call_s` goes from 30 to 120
  - the timelike emulation in `test_bench_catalog.py` points at the dispatcher and sets
    `TIMELIKE_HOOK_TIMEOUT` below the unit's call limit
  - 002's expected shape in its quickstart and README
- [X] T072 Docs: README (environment defaults), and `contracts/` if any contract names hooks.
- [X] T073 Host lane: ruff, mypy, shellcheck, units, coverage and conformance. Cycle report: Cycle 5.
  `audited_against` and audit-log (modify Step 9).

## Phase 15: Cycle 6 — rule 5's scope recorded; T4's `env -i` limit stated and pinned (send `bridge/sends/01-rev9-20261001-191224.md`, via `/specswarm:modify`)

<!-- Tech Stack Validation (cycle 6): PASSED — plan.md § Cycle 6 compliance report has no conflict or
prohibition; every technology named below (bats-core, git, Bash) is approved; GNU coreutils is base-image -->

Governance is current at `[2..9]` (`e344395`), so there is no audit task. No criterion changes.

- [X] T074 [P] Spec contract rule 5 (`spec.md`, lines 170–171): append revision 9's clarification in
  place, declared, as revision 6's were appended to rules 2 and 3. No other spec line states the
  unconditional reading (impact analysis § Cycle 6), so nothing else in the body changes.
- [X] T075 [P] `README.md`, where it describes the hook limit: T4's limit holds in the environment
  timelike provides. Under `env -i` (or anything that discards it), `.git/hooks` stays bounded through
  `/etc/gitconfig`, and a local `core.hooksPath` runs unbounded, as without timelike. Point at `run
  --timeout N` as the bounded way to run git when in doubt (research R12).
- [X] T076 [P] E2E `tests/e2e/hooks-under-env-i-default-bounded-local-unbounded.bats` (plan § Cycle 6
  design; research R12): both cases under `env -i`, in `bash -c` and `bash -lc` `notty`. The local
  case is bounded by the test's own `timeout`. Teardown kills by the hook's own pid file; never
  `pgrep -f`. Run each fixture through git on the host, sandboxed, before committing.
- [X] T077 `Makefile` `SHELLCHECK_FILES`: add the new bats file (depends on T076).
- [X] T078 Host lane: shellcheck, ruff and `make test-host`. Cycle report § Cycle 6 (send's block). An
  audit-log row `none (deferred)`: 8 and 9 are appended in `full` mode only after the Docker lane
  re-establishes the cycle (bookkeeping convention). Implement step 10 recorded as the plugin reports
  it.

**Parallel:** T074, T075 and T076 touch different files. T077 follows T076, and T078 comes last.

## Phase 16: Cycle 7 — rule 9's clarification recorded (send `bridge/sends/01-rev10-20261003-003933.md`, via `/specswarm:modify`)

<!-- Tech Stack Validation (cycle 7): PASSED — plan.md § Tech Stack Compliance Report (Cycle 7) has no
conflict or prohibition; the task scan (lib/tech-stack-parser.sh, ts_mentions) found no technology in
the task text below. The tasks change Markdown only -->

Governance is current at `[2..10]` (`cb943d3`), so there is no audit task. No criterion changes, and
nothing outside `.specswarm/` changes, so there is no Docker lane (send § 2).

- [X] T079 Spec contract rule 9 (`spec.md`, lines 181–182): append revision 10's clarification in place,
  declared, as revision 9's was appended to rule 5 (T074). No other spec line states exit 4's envelope
  (impact analysis § Cycle 7), so nothing else in the body changes.
- [X] T080 Provenance (modify Step 9): compute the append with the installed `audit-append` block in
  `full` mode (revision 10's criteria byte-identical to revision 9's, so removals are visible); write
  `audited_against` in `spec.md` frontmatter and one `full` row in `audit-log.md`. Never touch
  `prompt_revision`, `discovery_revision` or `source_prompt`.
- [X] T081 Cycle report § Cycle 7 (the send's block), citing the mentor's lane at `f73ac79` for the 11
  automated criteria; the deny-list over the tree reads `pass` with the list read. Implement step 10
  recorded as the plugin reports it.

**Parallel:** none. T080 follows T079, and T081 comes last.
