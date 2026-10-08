# Decisions Log — Feature 001
> Generated at 2026-09-28T06:54:47+00:00
> Spec: .specswarm/features/001-agent-shell-baseline/spec.md

## Decision Key

| Tag | Meaning |
|-----|---------|
| ASSUMED | Assumption made without explicit spec guidance (confidence: high/medium/low) |
| DEFERRED | Decision postponed — noted for later resolution |
| FLAGGED | Judgment call between alternatives — requires review |
| ABSENT | What was NOT done and why — forced reflection on gaps |
| INHERITED | Assumption carried forward from a prior task's output |

---
### T001: Repository skeleton, ignore files
**Started:** 2026-09-28T06:55:11+00:00 | **Completed:** 2026-09-28T06:55:11+00:00

INHERITED: (none — first task)
ASSUMED: tests/out/ holds Docker-lane results the operator produces on the host and the code instance reads (user decision 2026-09-28: operator runs the Docker lane on the host) — ignored except .gitkeep so results are never committed by accident (confidence: high)
ASSUMED: .dockerignore excludes .specswarm/ and .git/ — the image needs neither; the revision reaches it via the GIT_SHA build arg, not .git (confidence: high)
ABSENT: no pyproject packaging for tools — tools are single files copied into the image (H5), not an installable package
SCOPE: out — .dockerignore .gitignore (2 of 3 changed files) (task has FLAGGED: no)

### T002: pins.env — single source of pins
**Started:** 2026-09-28T06:56:00+00:00 | **Completed:** 2026-09-28T06:56:00+00:00

INHERITED: pinned digests and versions from research.md R9 — from Phase 0 research agent (confidence: high; read from registry APIs 2026-09-28, not re-verified here — no registry access from a shell without Docker)
ASSUMED: PYTEST_VERSION pinned to 8.4.2, the version installed in the host-lane scratch venv — pytest was not in R9 (confidence: medium)
ABSENT: digest verification of each image — impossible without a registry client here; the Docker lane's first pull verifies it (a wrong digest fails the pull, it cannot pass silently)
SCOPE: in (1 changed files)

### T003: Makefile with docker-check and stamp-check
**Started:** 2026-09-28T06:56:00+00:00 | **Completed:** 2026-09-28T06:56:00+00:00

INHERITED: pins.env — from T002 (confidence: high)
FLAGGED: stamp-check refuses a dirty tree unless ALLOW_DIRTY=1 — chose refusal over stamping HEAD for a tree that differs from it, because a stamp that names the wrong revision is the failure cross-stack P003 describes; cost: every build needs a commit first (confidence: high)
ASSUMED: untracked files under tests/out/ do not count as dirty — they are the Docker lane's own output (confidence: high)
ASSUMED: docker-check message names research R10 as the remediation, so an agent hitting it is told why and who can unblock it (P1) (confidence: high)
ABSENT: no 'test' fallback to the host lane when Docker is missing — make test fails loudly instead, so a host-lane pass is never mistaken for the authoritative lane (plan § Verification lanes)
SCOPE: out — Makefile (1 of 1 changed files) (task has FLAGGED: yes)

### T004: Lint configuration
**Started:** 2026-09-28T06:56:00+00:00 | **Completed:** 2026-09-28T06:56:00+00:00

INHERITED: tools/ layout from plan.md — from T001 (confidence: high)
ASSUMED: ruff S603/S607 ignored project-wide — the conformance check executes tools on PATH by design (confidence: high)
ASSUMED: mypy checks the extensionless tools via scripts_are_modules and an explicit files list (confidence: medium — confirmed when T007/T028 run mypy)
ABSENT: no ruff/mypy for tests/ under strict typing — tests are held to ruff only; strict typing applies to shipped code (quality-standards: mypy --strict for tools)
SCOPE: out — .shellcheckrc (1 of 2 changed files) (task has FLAGGED: no)

### T005: Test runner image
**Started:** 2026-09-28T06:56:00+00:00 | **Completed:** 2026-09-28T06:56:00+00:00

INHERITED: BATS_IMAGE and DOCKER_CLI_IMAGE pins — from T002 (confidence: high)
ASSUMED: the docker CLI binary lives at /usr/local/bin/docker in docker:*-cli images — from research R8 (confidence: medium; verified only when the Docker lane builds the runner)
ABSENT: not built — no Docker daemon here (research R10); lane D
SCOPE: in (1 changed files)

### T006: Failing unit tests for agentio, rule by rule
**Started:** 2026-09-28T07:00:31+00:00 | **Completed:** 2026-09-28T07:00:31+00:00

INHERITED: contracts/output-contract.md and the four JSON schemas — from /specswarm:plan Phase 1 (confidence: high)
ASSUMED: tools are exercised as subprocesses (stdin /dev/null, setsid, timeout) rather than in-process — the contract is about streams and exit codes of a process (confidence: high)
ASSUMED: rule 14 read literally — JSON error on stderr only with an explicit --json, text line otherwise even when piped; conformance C5 depends on this reading (confidence: medium)
ASSUMED: an explicitly empty TIMELIKE_SESSION is invalid (exit 2), unset means "default" (confidence: medium)
ASSUMED: session ids "." and ".." are rejected although they match ^[A-Za-z0-9._-]{1,64}$ — they would traverse out of the scratch root; the contract regex alone is insufficient (confidence: high)
FLAGGED: agentio refuses to print help longer than 40 lines (exit 1) instead of truncating it — chose refusal because a silently truncated help hides the violation from the author; the conformance check still exists for tools that bypass agentio (confidence: medium)
ABSENT: no test for rule 7 (idempotence) or rule 10's "no daemons" — neither is observable for a generic tool; mutating tools will carry their own idempotence tests
ABSENT: no JSON Schema library — tests/unit/schema.py implements the keyword subset the contract schemas use, guarded by test_schema_keywords_are_supported
Verification: 43 failed, 1 passed before agentio exists (expected: TDD red)
SCOPE: in (3 changed files)

### T007: agentio — the contract module
**Started:** 2026-09-28T06:58:00+00:00 | **Completed:** 2026-09-28T07:03:09+00:00

INHERITED: rule-by-rule tests — from T006 (confidence: high)
ASSUMED: capped text keeps up to 3 first errors between head and tail; head = (limit - errors)//2 (confidence: medium — the contract fixes the order, not the split)
ASSUMED: the full artefact is named by a content hash (<scratch>/artefacts/<tool>-<sha12>.txt) so the omission line stays deterministic (rule 11) (confidence: high)
ASSUMED: the event log's own ts field is exempt from rule 11 — rule 11 governs tool output, not the event log (event.schema.json says so) (confidence: high)
ASSUMED: nested JSON dict keys are sorted; list order is the tool's responsibility (confidence: high)
FLAGGED: a scratch session directory owned by another uid is refused (event not written, result unchanged) rather than written into — chose refusal because writing into another user's directory would breach SC-6's isolation; cost: a mis-owned directory silently loses events unless --verbose (confidence: high)
FLAGGED: an uncaught exception's traceback goes to <scratch>/<tool>-traceback.txt and only its path is shown — chose that over printing the traceback because rule 14 allows exactly one error object/line (confidence: high)
ASSUMED: ruff RUF001-RUF003 disabled project-wide in pyproject.toml (T004's file) — "…" and "—" are mandated by the contract's output formats (confidence: high)
ABSENT: no support yet for reads_stdin tools (no stdin reading helper) — no slice-0 tool reads stdin, and rule 4 forbids reading it otherwise
ABSENT: rule 8 (--dry-run) only provides the flag; the plan output for dry runs is each destructive tool's own responsibility — none exists in slice 0
Verification: pytest tests/unit/test_agentio.py → 44 passed (host lane, host Python 3.12.3); mypy --strict → no issues; ruff check/format → clean
SCOPE: in (5 changed files)

### T008: Start-up budget test; agentio import trimmed
**Started:** 2026-09-28T07:06:00+00:00 | **Completed:** 2026-09-28T07:04:25+00:00

INHERITED: agentio from T007 (confidence: high)
FLAGGED: agentio's dataclasses replaced with plain __slots__ classes and hashlib/traceback imports deferred, event ts via time.strftime — chose to trim now over shipping at 83.4 ms p95 against a 100 ms budget, because python-build-standalone in the image may start slower than the host's Python and the margin was 17 %; result: import 50 ms → 29 ms, host p95 83.4 → 58.4 ms (confidence: high)
ASSUMED: second-precision UTC timestamps are enough for the event log's ts; duration_ms carries the precise timing (confidence: high)
ABSENT: the authoritative in-image measurement (quality-standards C2) — needs the Docker lane; task T042
ABSENT: argparse (~12 ms) kept — replacing it with a hand parser trades a measured cost for an unmeasured correctness risk
Verification: host lane p95 58.4 ms over 50 runs (advisory); 45 unit tests pass; mypy --strict clean
SCOPE: in (2 changed files)

### T010: Fallback /etc/gitconfig
**Started:** 2026-09-28T06:59:00Z | **Completed:** 2026-09-28T06:59:00Z

INHERITED: keys and values from research R2–R4 and tasks.md T010 (confidence: high)
ASSUMED: an empty `helper =` resets the credential helper list (git semantics) (confidence: high)
ABSENT: no other git defaults (init.defaultBranch, advice.*) — they produce noise, not hangs, and are not in R2–R4
Implemented by the image subagent; reviewed by the coordinator. Verified as GIT_CONFIG_SYSTEM in the host env-layer test (color.ui=never in all three styles; self-check N3 shows the value is absent without this file)
SCOPE: in (1 changed files)

### T011: profile.d PATH restore
**Started:** 2026-09-28T06:59:00Z | **Completed:** 2026-09-28T06:59:00Z

INHERITED: Debian's /etc/profile resets PATH for login shells — research R1 (confidence: high)
FLAGGED: prepend only when absent, rather than move to front when present elsewhere — after Debian's reset it is always absent, and the simple form has no parsing to get wrong (confidence: medium)
ABSENT: not exercised under the image's real /etc/profile — the host lane simulates it
Verified: bash -n, sh -n, shellcheck 0.11.0 (default and -s sh) clean; host test shows simulated bash -lc gets /opt/timelike/bin first; emptying the file fails test 10 (mutation run)
SCOPE: in (1 changed files)

### T009: Agent image Dockerfile
**Started:** 2026-09-28T06:57:00Z | **Completed:** 2026-09-28T07:03:00Z

INHERITED: build steps and ordering from tasks.md T009; uv/CPython install and symlink from research R6; privilege steps from R7; pins as build args from pins.env (T002) (confidence: high)
ASSUMED: `uv python install --compile-bytecode` exists in uv 0.12.19 — R6 lists it; if not, the build fails loudly, not silently (confidence: medium)
ASSUMED: uv names the directory cpython-${PYTHON_VERSION}-linux-x86_64-gnu; the build fails with the directory listing and a remediation if not (confidence: medium)
ASSUMED: agentio.py is byte-compiled at build (compileall) because the agent cannot write __pycache__ into root-owned site-packages, and quality-standards C2 sets a 100 ms start-up budget (confidence: high)
ASSUMED: build RUNs use SHELL bash with errexit/nounset/pipefail; ARGs are read as ${X:-} so an unset arg reaches our own error message (confidence: high)
FLAGGED: agent home created empty (no /etc/skel) — chose an empty home over useradd -m because skel's .profile prepends ~/bin and ~/.local/bin under login shells and skel's .bashrc would give rc-file defaults tests could come to depend on (FR-1) (confidence: medium)
FLAGGED: rootfs copied file by file with COPY --chmod=0644 instead of `COPY image/rootfs/ /` — the build context carries host umask modes (0664 here), and --chmod on a directory COPY would also chmod the directories (confidence: high)
FLAGGED: EXTERNALLY-MANAGED marker is reported, not fatal — agentio is installed by a direct file copy, which the marker cannot block, so T009 step 3's failure condition can never trigger (confidence: high)
FLAGGED: the Adele fixture is created by RUN (install -d, chown, chmod), not shipped under image/rootfs/var — exact ownership and modes; plan.md § Source code still lists rootfs/var/lib/adele/fixture.secret (confidence: high)
ASSUMED: ENV is placed before ARG GIT_SHA, so the per-commit stamp is the last layer (confidence: high)
ASSUMED: /bin/uv stays in the runtime image — the stack makes uv the default for the agent's own installs, and tests/run.sh uses it to run the unit suite on the image's interpreter (confidence: medium)
DEFERRED: R2 cross-check `uv python list` in the uv image — needs Docker; the build's missing-directory check is the fail-safe
ABSENT: image never built — no Docker daemon (research R10); every build-time assertion is unexecuted
ABSENT: apt package versions not pinned (no snapshot.debian.org) — only the base image is pinned by digest
Implemented by the image subagent; reviewed by the coordinator (each RUN asserts its own outcome, H3)
SCOPE: in (1 changed files)

### T012: compose.yaml agent service
**Started:** 2026-09-28T06:59:00Z | **Completed:** 2026-09-28T06:59:00Z

INHERITED: service shape from tasks.md T012; hardening from research R7; lore docker-compose Q002 and Q005 (confidence: high)
FLAGGED: ${VAR:-} for every build arg, not ${VAR:?} for pins — compose interpolates the whole file on exec/down too, so :? would break `docker compose exec` whenever pins.env is not exported; the Dockerfile refuses empty values instead (confidence: high)
ASSUMED: the pins reach compose through the Makefile's `include pins.env` + `export`; tests/run.sh must export pins.env and GIT_SHA the same way (confidence: high)
DEFERRED: `platform: linux/amd64` not set — the interpreter-directory check fails loudly on other architectures
ABSENT: `docker compose config` / up not run — no daemon. Parsed with PyYAML only
SCOPE: in (1 changed files)

### T020: Host-lane env-layer test and host lane driver
**Started:** 2026-09-28T06:59:00Z | **Completed:** 2026-09-28T07:03:00Z

INHERITED: ENV block from T009, gitconfig from T010, profile.d script from T011; host-lane design from research R10 (confidence: high)
ASSUMED: the stand-in profile reproduces trixie base-files 13.8's PATH reset and profile.d loop as research R1 describes; the file itself was not read here (confidence: medium)
FLAGGED: login case simulated with `bash -c` sourcing a temporary stand-in profile, not a real `bash -lc` — the host's Ubuntu /etc/profile does not reset PATH and cannot be edited; the first output line and header say so (confidence: high)
FLAGGED: PATH asserted as "first entry is /opt/timelike/bin" rather than `command -v timelike` — the directory does not exist on this host (confidence: high)
FLAGGED: run.sh counts pytest exit 5 (no tests collected) as a failure — an empty suite proves nothing (H3, cross-stack P004) (confidence: high)
DEFERRED: `sh -c` style (in T018) not added to the host lane — T020 names three styles
ABSENT: proves the files only, not the image: host bash 5.2.21 and git 2.43.0 stand in for the image's
Verified: tests/host/test_env_layer.sh → 32/32 (27 assertions, 5 self-checks incl. N1 all-fail without ENV); mutations (GIT_PAGER=less, emptied profile.d, second ENV, backslash) each fail; shellcheck 0.11.0 clean
SCOPE: in (2 changed files)

### T016: Git editor/pager defaults (SC-1) — written, pending Docker lane
**Started:** 2026-09-28T06:57:00Z | **Completed:** (pending verification)

INHERITED: GIT_EDITOR/GIT_SEQUENCE_EDITOR=true, GIT_MERGE_AUTOEDIT=no, GIT_PAGER/PAGER=cat in ENV and fallbacks in gitconfig — from T009/T010, research R2 (confidence: high)
ABSENT: T015 not run — Docker lane; SC-1 unconfirmed. Task left unticked until the Docker lane passes it

### T019: Defaults in every invocation style (SC-2) — written, pending Docker lane
**Started:** 2026-09-28T06:57:00Z | **Completed:** (pending verification)

INHERITED: every non-PATH default only in ENV; PATH in ENV and profile.d — from T009/T011, research R1 (confidence: high)
ABSENT: no rc-file, BASH_ENV or PROMPT_COMMAND default added (FR-1); T018 not run — Docker lane; SC-2 unconfirmed (host lane is file evidence only). Task left unticked

### T022: Credentials fail fast, hooks off (SC-3) — written, pending Docker lane
**Started:** 2026-09-28T06:57:00Z | **Completed:** (pending verification)

INHERITED: GIT_TERMINAL_PROMPT=0, empty GIT_ASKPASS/SSH_ASKPASS, GCM_INTERACTIVE=never, GIT_SSH_COMMAND BatchMode, GIT_CONFIG_* hooksPath=/dev/null — from T009, research R2/R3 (confidence: high)
ASSUMED: Dockerfile `KEY=""` yields an empty, set variable (confidence: high)
ABSENT: T021 not run — Docker lane; SC-3 unconfirmed. Task left unticked

### T025: No escalation (SC-4) — written, pending Docker lane
**Started:** 2026-09-28T06:57:00Z | **Completed:** (pending verification)

INHERITED: no sudo/nft/iptables, setuid/setgid strip with an empty-find assertion, agent uid 1000 with no supplementary groups, adele 10001 with /var/lib/adele 0700 and fixture 0600 — from T009; cap_drop ALL, no-new-privileges, default seccomp — from T012; research R7 (confidence: high)
ABSENT: T023 not run — Docker lane; /proc/self/status, su, unshare and nfprobe results unobserved; SC-4 unconfirmed. Task left unticked
SCOPE: none — no files outside the feature's artifacts changed

### T026: Non-conforming fixtures for the negative conformance test
**Started:** 2026-09-28T07:06:10+00:00 | **Completed:** 2026-09-28T07:06:10+00:00

INHERITED: check list C1–C8 from contracts/conformance.md (confidence: high)
FLAGGED: timelike-bad hand-rolls its output instead of using agentio (tasks.md said "uses agentio") — agentio refuses a >40-line help and always writes events, so a fixture built on it cannot violate C1 or C7; chose a hand-written fixture that breaks exactly C1, C5, C7 and conforms otherwise, so the negative test can match findings exactly (confidence: high)
ASSUMED: fixtures carry the image's shebang (/opt/timelike/python/bin/python3 -I) so T030 can run them in the container; host unit tests rewrite the shebang when installing them into a temp bin (confidence: high)
ABSENT: no fixture for C2/C3/C4/C8 violations — the unit tests build those cases from temp tools where needed; the send's criterion names the six properties, and C1/C5/C7 plus the hang cover three plus P2
Verified: timelike-bad --help prints 45 lines; an unknown flag exits 1
SCOPE: in (2 changed files)

### T027: Unit tests for timelike-conform and timelike
**Started:** 2026-09-28T07:06:49+00:00 | **Completed:** 2026-09-28T07:06:49+00:00

INHERITED: contracts/conformance.md C1–C8; fixtures from T026 (confidence: high)
ASSUMED: TIMELIKE_CONFORM_TIMEOUT overrides the 10 s probe limit so tests stay fast; the contract's 10 s stays the default (confidence: high)
ASSUMED: TIMELIKE_REVISION and TIMELIKE_REVISION_FILE override /opt/timelike/REVISION for tests; the image sets neither (confidence: high)
ASSUMED: timelike tests live here rather than in a separate file — tasks.md T028 names no test file, and both tools are checked together by SC-5 (confidence: medium)
ABSENT: no test that conform checks mutating tools' --yes/--dry-run behaviour — contracts/conformance.md leaves that to per-tool tests, and slice 0 has no mutating tool
Verification: TDD red before implementation — all tests fail (tools/bin is empty)
SCOPE: in (1 changed files)

### T028: timelike — environment info carrying the build revision
**Started:** 2026-09-28T07:12:00+00:00 | **Completed:** 2026-09-28T07:08:38+00:00

INHERITED: agentio (T007); /opt/timelike/REVISION written without a trailing newline by the image (T009) — read and stripped (confidence: high)
ASSUMED: the default output fails (exit 1) when the stamp is missing, not only --agent-info — an environment that cannot say what it is has failed H8 either way (confidence: medium)
ASSUMED: "tools on PATH" means executables in TIMELIKE_BIN_DIRS whose directory is on PATH, compared by realpath — P3: a tool the agent cannot find does not exist (confidence: high)
ABSENT: no announcement of tools into harness context files — that is P3's feature 02+ work, not slice 0
Verification: tests/unit/test_conform.py timelike_* (6 tests) pass on the host lane; mypy --strict clean
SCOPE: in (1 changed files)

### T029: timelike-conform — the conformance check
**Started:** 2026-09-28T07:14:00+00:00 | **Completed:** 2026-09-28T07:08:38+00:00

INHERITED: C1–C8 from contracts/conformance.md; fixtures from T026; tests from T027 (confidence: high)
FLAGGED: after a probe that does not conclude, the remaining probes for that tool are skipped — chose one limit per hanging tool over checking the rest, because five more hanging probes would cost 50 s and prove nothing new (P2); the finding names the probe that hung (confidence: high)
FLAGGED: the result's verdict is the single word pass|fail and the human summary is the first body line and data.summary — verdict is a reserved agentio key and callers (tests, bats) match on it (confidence: medium)
ASSUMED: a TIMELIKE_BIN_DIRS entry that is missing or off PATH is a C0 finding that fails the run, not a warning — the contract says "reported, not silently skipped"; failing is the stronger reading (confidence: medium)
ASSUMED: manifest validity is checked inline (keys, tool, contract, exit_codes, flags, probe) rather than by a JSON Schema library — shipped code stays stdlib-only (H5) (confidence: high)
ABSENT: rules 2, 3, 7–10, 15 are not probed by conform — contracts/conformance.md assigns them to agentio's unit tests or to per-tool tests for mutating tools
Verification: 13 conform/timelike tests pass on the host lane (incl. bad tool → exactly C1, C5, C7; hang bounded to one 2 s limit; zero tools and dir-off-PATH fail); mypy --strict clean; ruff clean
SCOPE: in (2 changed files)

### T031: Unit tests for peer-session isolation
**Started:** 2026-09-28T07:20:00+00:00 | **Completed:** 2026-09-28T07:09:09+00:00

INHERITED: session model from data-model.md; agentio's session handling from T007 (confidence: high)
ASSUMED: "concurrent" is exercised by two threads each spawning 50 sequential tool processes, so both sessions' processes overlap in time (confidence: medium — it proves overlap, not a worst-case schedule)
ASSUMED: an extra same-session test (4 × 50 writers, every line parses) is worth adding — it is the O_APPEND single-write property T033 names (confidence: high)
ABSENT: no test of hostile peers (same uid reading the other's 0700 dir is possible) — spec Assumption 4: separation, not security
Verification: 3 passed on the host lane
SCOPE: in (1 changed files)

### T033: agentio session isolation (path purity, O_APPEND lines, 0700)
**Started:** 2026-09-28T07:09:09+00:00 | **Completed:** 2026-09-28T07:09:09+00:00

INHERITED: the implementation already in agentio (T007): scratch path is a pure function of the session id, each event is one os.write on an O_APPEND fd, directories are created 0700 and refused when owned by another uid (confidence: high)
ABSENT: no code change — T031 passes against T007's implementation; T032 (the image-level test) is still pending the Docker lane
Verification: tests/unit/test_sessions.py 3 passed; tests/unit/test_agentio.py rule-10 test passes
SCOPE: none — no files outside the feature's artifacts changed

### T034: supply-chain scan gate (scan/scan.sh, scan/evaluate.py)
**Started:** 2026-09-28T06:58:04+00:00 | **Completed:** 2026-09-28T07:06:15+00:00

INHERITED: pinned images and PIP_AUDIT_VERSION from pins.env; interpreter at /opt/timelike/python and uv at /bin/uv (research R6); exemption table format and the overdue-blocks reading from quality-standards.md § Exemptions and FOR-MENTOR 5.2 (confidence: high)
INHERITED: gitleaks `git` subcommand — `detect` became a deprecated alias in v8.19; `git` scans history, so a secret committed then deleted is caught, where `dir` would miss it (confidence: medium — from knowledge of v8.19+, not run against v8.30.1)
ASSUMED: gitleaks with `--exit-code 0` exits non-zero only on its own failure, and writes `[]` when it finds nothing — findings are read from the JSON (confidence: medium)
ASSUMED: grype JSON shape (matches[].vulnerability.{id,severity,fix.state,fix.versions}, relatedVulnerabilities[].id, artifact.{name,version}) and syft-json source.metadata.imageID for a docker-archive source (confidence: medium — a wrong guess fails the gate loudly and never passes)
ASSUMED: exemptions match by identifier or any grype-related alias, not by component (confidence: medium)
ASSUMED: an overdue exemption blocks even when no current finding matches it, following quality-standards' "fails the gate until someone reviews it" (confidence: medium)
FLAGGED: SBOM source — chose `docker save` + syft `docker-archive:` over mounting /var/run/docker.sock into Syft, because the socket is root on the host (P4) and the archive also works under a remote DOCKER_HOST (confidence: high)
FLAGGED: pip-audit reports no severity — chose to treat each of its findings as High ("unrated": fixable blocks, unfixable needs an exemption) over ignoring them, because H9 cannot be applied without severity and the conservative side is to block. Grype's "Unknown" severity does NOT block (confidence: medium)
FLAGGED: kept evaluate.py as one 405-line file over splitting it, because `python3 -I` drops the script directory from sys.path — justified in plan.md Complexity Tracking (added by the coordinator) against max_file_lines 300 (confidence: medium)
FLAGGED: invalid exemption rows (missing field, bad id, bad date, duplicate) block the gate whether or not they match anything, over being ignored, because a defective governance table should not pass silently (confidence: high)
ASSUMED: the coordinator added scan/evaluate.py to pyproject mypy files and scan/ to make lint / lint-host (the subagent could not edit those files) (confidence: high)
ABSENT: no scanner was run — no Docker daemon here (R10). Syft, Grype, pip-audit and gitleaks invocations and their output formats are unverified until T036 runs `make scan` in the Docker lane; fake-docker runs checked only the script's plumbing
ABSENT: Adele's image and govulncheck are not scanned — no Adele image exists in feature 001
Implemented by the scan subagent; reviewed by the coordinator. Verified: mypy --strict clean, ruff clean, shellcheck 0.11.0 clean, fake-docker scenarios (pass, fixable High + unfixable Critical + leak, grype db failure, wrong SBOM image, malformed JSON, missing image)
SCOPE: out — Makefile (1 of 4 changed files) (task has FLAGGED: yes)

### T035: unit tests for the exemption parser and the H9 rule
**Started:** 2026-09-28T07:02:00+00:00 | **Completed:** 2026-09-28T07:06:15+00:00

INHERITED: cases from the task (valid, missing field, overdue, fixable-exempted void, Medium, `*(none)*`, the real quality-standards.md) (confidence: high)
ASSUMED: evaluate.py is loaded by file path and registered in sys.modules, since scan/ is not a package (confidence: high)
ABSENT: the tests run only on the host lane (host Python 3.12 via the scratch venv), not inside the image — the Docker lane has not run them
ABSENT: no test feeds real scanner output — all Grype, pip-audit and gitleaks JSON is synthetic
Verification: 28 passed on the host lane (coordinator re-ran); the real quality-standards.md parses to zero exemptions
SCOPE: in (1 changed files)

### T040: README
**Started:** 2026-09-28T07:10:03+00:00 | **Completed:** 2026-09-28T07:10:03+00:00

INHERITED: two verification lanes from research R10; contract summary from contracts/output-contract.md (confidence: high)
ASSUMED: the README says "MIT" without a LICENSE file — the stack names the licence; adding the licence text is a maintainer act, not part of this criterion set (confidence: medium)
ABSENT: no value claims, benchmarks or comparisons — P6: claims only from reproducible bench results, and none exist yet
ABSENT: no LICENSE file added — flagged in the cycle report's not_verified list for the maintainer
SCOPE: in (1 changed files)

### T013: e2e helpers (run_in, stamp_check, timing, pager/editor checks)
**Started:** 2026-09-28T06:57:42Z | **Completed:** 2026-09-28T07:23:14Z

INHERITED: container name timelike-agent, label org.opencontainers.image.revision, /opt/timelike/REVISION, interpreter path — from plan.md and image/Dockerfile (confidence: high)
FLAGGED: three terminal modes (notty, tty = docker exec -t, pty = script inside the container) — kept docker exec -t alongside script because -t alone should work from a non-interactive runner (docker/cli refuses only -i with -t, In.CheckTty — from source, not verified) and it is the only mode where a canonical-mode prompt blocks forever; script feeds EOF to canonical reads (confidence: medium)
FLAGGED: copy_into_container streams through `docker exec -i ... sh -c 'cat > f; chmod'` instead of docker cp — agent-owned files with explicit modes over root-owned ones the agent cannot chmod or delete from sticky /tmp (confidence: high)
ASSUMED: runner has bash 5 (EPOCHREALTIME) and busybox timeout, since bats/bats is FROM bash — timeouts judged by elapsed time because busybox may report 143 not 124 (confidence: medium)
ASSUMED: pager/editor detection by exact process name (pgrep -x) (confidence: high)
ABSENT: nothing has run against the image — no Docker daemon here (R10); verified by shellcheck 0.11.0, bats --count and a fake-docker smoke run only
ABSENT: no "during the run" pager sampling — a pager on a tty with more than one screen cannot exit by itself, so it surfaces as a timeout; the process table is read after each run
Implemented by the e2e subagent; reviewed by the coordinator
SCOPE: in (1 changed files)

### T014: Docker lane driver tests/run.sh
**Started:** 2026-09-28T07:05:00Z | **Completed:** 2026-09-28T07:12:00Z

INHERITED: pins.env keys, Makefile build/stamp-check, compose.yaml — from T002/T003/T012 (confidence: high)
INHERITED: results in tests/out/ (summary.json, e2e.tap, report.xml, unit.txt, run-<UTC>.log, latest.log) for the code instance to read — user decision 2026-09-28: the operator runs the Docker lane on the host (confidence: high)
FLAGGED: build via `make build` rather than a second copy of the compose build — one definition of the build and its stamp/dirty checks (confidence: high)
FLAGGED: unit tests use a uv binary copied out of the pinned UV_IMAGE, run against the image's interpreter — independence from whether the agent image keeps uv (confidence: medium)
ASSUMED: run on the Docker host, so bind-mount paths are host paths (confidence: medium)
ASSUMED: every step runs unless a step it depends on failed (recorded skipped with the reason), so one report is complete (confidence: high)
ABSENT: not executed — no Docker daemon here (R10); shellcheck-clean and bash -n only
ABSENT: unit step is not offline — pytest comes from PyPI at run time
Implemented by the e2e subagent; reviewed by the coordinator
SCOPE: in (1 changed files)

### T015: SC-1 bats (git log/diff/commit/rebase exit within 20 s)
**Started:** 2026-09-28T07:02:00Z | **Completed:** 2026-09-28T07:14:00Z

INHERITED: expected rc, "Aborting commit due to empty commit message", rebase --continue rc 0 keeping the message — from research R2 (confidence: high)
ASSUMED: git log/diff with a TTY and more than one screen of output is what exposes a pager; notty alone proves little (the negative smoke confirmed notty passes with a broken pager) (confidence: high)
FLAGGED: SC-1 line matching strips ANSI colour — keeps colour out of SC-1 so one regression fails exactly one criterion (SC-2 owns colour) (confidence: high)
ABSENT: unrun against the image (R10). 36 tests: 4 commands × 3 styles × 3 terminal modes; fake-docker smoke passed with the image's env; the broken-env control failed all 12 pty cases (rc 124) without hanging
Implemented by the e2e subagent; reviewed by the coordinator
SCOPE: in (2 changed files)

### T017: manual demo script for SC-7
**Started:** 2026-09-28T07:12:00Z | **Completed:** 2026-09-28T07:23:00Z

INHERITED: repository fixture from T015 (sc1-repo.sh), reused so demo and test show the same thing (confidence: high)
ASSUMED: host has bash 5 and GNU timeout; falls back and says so (confidence: medium)
ABSENT: not watched by anyone — SC-7 stays `unconfirmed` until a person runs `make demo` and records it
Implemented by the e2e subagent; reviewed by the coordinator
SCOPE: in (1 changed files)

### T018: SC-2 bats (defaults in effect per invocation style)
**Started:** 2026-09-28T07:06:00Z | **Completed:** 2026-09-28T07:10:00Z

INHERITED: expected values and which layer carries them — from research R1–R4 and image/Dockerfile ENV (confidence: high)
ASSUMED: tested in all three terminal modes, not only notty, per R8 (confidence: high)
ABSENT: unrun against the image (R10). 12 tests: bash -c, bash -lc, bash -ic, sh -c × 3 modes, each name carrying its style
Implemented by the e2e subagent; reviewed by the coordinator
SCOPE: in (1 changed files)

### T021: SC-3 bats (credentials fail fast, hooks off)
**Started:** 2026-09-28T07:06:00Z | **Completed:** 2026-09-28T07:12:00Z

INHERITED: GIT_TERMINAL_PROMPT/GIT_ASKPASS/GIT_SSH_COMMAND/GIT_CONFIG_* design and "-c is explicit enablement" — from research R2, R3 (confidence: high)
FLAGGED: the https case is a local plain-http 401 server whose request log proves git reached the credential challenge, never skipped — chose a proven challenge over a real https remote that needs the internet and cannot tell a prompt refusal from a network error; git's credential path is the same for both schemes (confidence: medium)
ASSUMED: prompt detection by text (Username for, Password for, passphrase, yes/no) as well as by timeout, because pty mode feeds EOF to canonical reads (confidence: high)
ABSENT: no real ssh credential challenge — no sshd in the image; ssh cases show an unreachable host fails fast plus a direct read of BatchMode (ssh -G)
ABSENT: unrun against the image (R10). 40 tests
Implemented by the e2e subagent; reviewed by the coordinator
SCOPE: in (2 changed files)

### T024: netfilter probe and its unit tests
**Started:** 2026-09-28T06:58:00Z | **Completed:** 2026-09-28T07:01:00Z

INHERITED: AF_NETLINK/NETLINK_NETFILTER probe expecting EPERM — from research R7 (confidence: high)
ASSUMED: nftables GETTABLE dump (type 0x0A01, NLM_F_REQUEST|NLM_F_DUMP) as the one message; the kernel checks CAP_NET_ADMIN in nfnetlink_rcv before any subsystem (confidence: high; observed: -EPERM NLMSG_ERROR)
ABSENT: never observed printing OK — no environment here holds CAP_NET_ADMIN; the OK path is covered only by unit tests on synthetic replies
Verification: 14 unit tests pass; the probe run in THIS dev container (uid 2001, CapEff 0) printed EPERM from an NLMSG_ERROR with error -1 — vantage point: the development container, not the agent image (lore cross-stack P001)
SCOPE: in (2 changed files)

### T023: SC-4 bats (no root, no firewall change, no Adele reads)
**Started:** 2026-09-28T07:08:00Z | **Completed:** 2026-09-28T07:22:00Z

INHERITED: control list and expected values — from research R7 and data-model.md; nfprobe from T024 (confidence: high)
ASSUMED: `su -c true root` failing is weak evidence on its own; the direct reads (NoNewPrivs 1, no setuid files) carry the claim (confidence: high)
ASSUMED: Adele's directory ownership is read first, so a failed read counts only as a permission refusal, never a missing file (confidence: high)
ABSENT: CapInh not asserted — not in tasks.md
ABSENT: unrun against the image (R10). 18 tests under bash -c and bash -lc; on this host the smoke fails exactly where it should (host CapBnd, uid 2001 in sudo, setuid files present)
Implemented by the e2e subagent; reviewed by the coordinator
SCOPE: in (1 changed files)

### T030: SC-5 bats (conformance check over every tool on PATH)
**Started:** 2026-09-28T07:12:00Z | **Completed:** 2026-09-28T07:22:00Z

INHERITED: output formats (text FAIL line, JSON verdict/checked/failures) — from contracts/conformance.md; tools from T028/T029 (confidence: high)
ASSUMED: the conform runs get a 60 s runner limit (confidence: medium)
ABSENT: timelike-hang is not exercised here — unit-tested in T027
ABSENT: unrun against the image (R10). 10 tests: pass over the shipped PATH with checked == executables in /opt/timelike/bin; bad fixture → FAIL C1/C5/C7 and nothing for shipped tools; timelike --agent-info revision == GIT_SHA
Implemented by the e2e subagent; reviewed by the coordinator
SCOPE: in (2 changed files)

### T032: SC-6 bats (peer agents write to own scratch space)
**Started:** 2026-09-28T07:12:00Z | **Completed:** 2026-09-28T07:20:00Z

INHERITED: scratch path = ${TIMELIKE_SCRATCH_ROOT}/<session>, 0700, events.jsonl — from data-model.md (confidence: high)
FLAGGED: explicit per-test TIMELIKE_SCRATCH_ROOT instead of the default /tmp/timelike — isolation from earlier runs (stale events cannot satisfy a count) over exercising the default root (confidence: medium)
ASSUMED: overlap of the two peers is measured, not assumed; artefacts carry the session id in their names (confidence: high)
ABSENT: unrun against the image (R10). Smoke passes against a session-honouring fake and fails when peers share a session
Implemented by the e2e subagent; reviewed by the coordinator
SCOPE: in (2 changed files)

### T037: shellcheck clean
**Started:** 2026-09-28T07:26:12+00:00 | **Completed:** 2026-09-28T07:26:12+00:00

INHERITED: shell files from T011, T013–T017, T020, T034 (confidence: high)
ASSUMED: shellcheck 0.11.0 from the scratch venv (shellcheck-py) is the same version pinned in pins.env for make lint (confidence: high)
ABSENT: make lint (authoritative, pinned container) not run — Docker lane
Verification: shellcheck 0.11.0 clean on profile.d, tests/run.sh, tests/host/*.sh, tests/e2e/helpers.bash, all six .bats files, fixtures/*.sh, scan/scan.sh, scripts/demo.sh
SCOPE: none — no files outside the feature's artifacts changed

### T038: ruff and mypy --strict clean; make lint runnable
**Started:** 2026-09-28T07:26:12+00:00 | **Completed:** 2026-09-28T07:26:12+00:00

INHERITED: pyproject ruff/mypy configuration from T004, extended in T007 and T034 (confidence: high)
FLAGGED: make lint runs ruff and mypy through the uv inside the built agent image instead of the uv image — the uv image is distroless with no shell (research R6), so the original 'sh -c' target could never have run; chose the agent image because it has bash, the pinned uv and the image's own interpreter (confidence: high)
ASSUMED: lint builds the image first when it is absent (confidence: high)
ABSENT: make lint itself not run — Docker lane; host-lane equivalents only
Verification: ruff check + format --check clean (tools, tests, scan); mypy --strict clean on 4 source files (host venv mypy 2.3.1 = pinned MYPY_VERSION)
SCOPE: out — Makefile (1 of 1 changed files) (task has FLAGGED: yes)

### T039: H8 stamp end to end — host half verified, Docker half pending
**Started:** 2026-09-28T07:26:12+00:00 | **Completed:** (pending Docker lane)

INHERITED: stamp-check (T003), Dockerfile GIT_SHA refusal (T009), timelike revision (T028), stamp_check and SC-5 revision test (T013, T030) (confidence: high)
ABSENT: label == timelike --agent-info revision == HEAD not observed — Docker lane (checked there by tests/e2e/helpers.bash stamp_check and the SC-5 bats); task left unticked
Verification (host): make stamp-check refuses a dirty tree (rc 2, named remediation), passes with ALLOW_DIRTY=1, refuses an empty GIT_SHA (rc 2); timelike exits 1 on a missing, empty or newline-only stamp (T027 tests)
SCOPE: none — no files outside the feature's artifacts changed

### T035 (addendum): report-path tests; two evaluator fixes
**Started:** 2026-09-28T07:12:00+00:00 | **Completed:** 2026-09-28T07:30:25+00:00

INHERITED: the 90% line+branch coverage floor for Python from quality-standards.md; the case list from the coordinator (confidence: high)
ASSUMED: `dists` is tested against a fake site-packages directory standing in for the image interpreter — checks counting and recording, not the real image's contents (confidence: high)
FLAGGED: changed scan/evaluate.py although asked to touch only tests — minimal fixes for two real bugs: (1) the exemptions row failed on "no exemption listed", misattributing a Grype finding to the table; (2) an uncaught crash exited 1, which scan.sh reads as a verdict with no verdict line printed — now exits 2, which scan.sh already treats as "no verdict reached" (confidence: high)
DEFERRED: 8 uncovered lines (parse-error edge paths, the __main__ guard) — 96% clears the floor
ABSENT: no scanner was run and no test uses real scanner output — no Docker daemon (R10)
Verification: 54 scan tests pass; evaluate.py 96% line+branch; each fix has a test that failed before it; ruff, mypy --strict clean
SCOPE: in (2 changed files)

### T029 (addendum): every conformance check shown able to fail
**Started:** 2026-09-28T07:31:00+00:00 | **Completed:** 2026-09-28T07:36:00+00:00

INHERITED: timelike-conform (T029); the negative fixture covered only C1, C5, C7 (T026) (confidence: high)
ASSUMED: one hand-written conforming probe tool with 17 single-point mutations is the smallest way to show C2, C3, C4, C6, C7 and C8 fail when they should — lore cross-stack P004: a check never seen failing proves nothing (confidence: high)
ASSUMED: an out-of-vocabulary exit (42) on the probe runs also trips C3/C4, since those checks require a vocabulary exit; the test allows C6 alongside any case (confidence: high)
ABSENT: no mutation for C1 or C0 beyond the existing fixtures and tests — already covered by T027
Verification: 22 tests pass (17 mutations incl. a fully conforming control, missing bin dir, invalid probe-limit values); timelike-conform coverage 81% → 93%
SCOPE: in (2 changed files)

### T008 (addendum): coverage measurement across subprocesses
**Started:** 2026-09-28T07:30:00+00:00 | **Completed:** 2026-09-28T07:40:00+00:00

INHERITED: quality-standards: coverage.py line+branch, 90% minimum for Python (confidence: high)
FLAGGED: test environments now pass COVERAGE_PROCESS_START through, and the start-up budget test skips itself under tracing — chose to measure tools as the subprocesses they are (the contract is about processes) over in-process coverage that would miss the real entry points; the skip exists because a coverage .pth import inflated start-up to 148.7 ms, which is a measurement artefact, not a regression (confidence: high)
ASSUMED: .coverage data files are git-ignored (confidence: high)
ABSENT: no `make coverage` target — the measurement uses a scratch-venv .pth hook that the Docker lane would need its own form of; recorded in the cycle report instead
Verification (host lane): 150 passed, 1 skipped; coverage 94% total — agentio 92%, timelike 96%, timelike-conform 93%, scan/evaluate.py 96%; start-up p95 56.7 ms without tracing
SCOPE: out — .gitignore (1 of 3 changed files) (task has FLAGGED: yes)

### T041: Cycle report, cycle 1
**Started:** 2026-09-28T07:34:05+00:00 | **Completed:** 2026-09-28T07:34:05+00:00

INHERITED: format from the send's ## Cycle report block; decisions and verification results from T001–T040 (confidence: high)
ASSUMED: every criterion is `unconfirmed` — none ran in the image; host-lane evidence is listed under not_verified, never as a criterion mode (confidence: high)
ASSUMED: reconcile_mode full — first build, every slice-0 criterion examined (confidence: high)
ABSENT: demo_points_reached not written — the mentor derives it (send instruction)
ABSENT: Group A — no .implement-complete marker on a non-dispatch run
Verification: each of the 7 criterion citations matches exactly one line of bridge/sends/01-rev2-20260928-063549.md; SCOPE: out count (6) matches decisions.md
SCOPE: out — .specswarm/metrics.json FOR-MENTOR.md (2 of 2 changed files) (task has FLAGGED: no)

### T016: verified in the Docker lane (SC-1)
**Started:** 2026-09-28T12:08:54Z | **Completed:** 2026-09-28T12:13:40Z

INHERITED: content from T009–T012 (image, gitconfig, profile.d, compose) and the bats file git-log-diff-commit-rebase-exit-within-20-seconds.bats (confidence: high)
ABSENT: nothing changed in code — this entry records the verification the task was waiting on
Verification: Docker lane run 2026-09-28T12:08:54Z by the operator on the host, image stamped b235f39 (tests/out/summary.json exit 0); git-log-diff-commit-rebase-exit-within-20-seconds.bats → 36 tests, 0 failed, 0 skipped (tests/out/report.xml)
SCOPE: none — no files outside the feature's artifacts changed

### T019: verified in the Docker lane (SC-2)
**Started:** 2026-09-28T12:08:54Z | **Completed:** 2026-09-28T12:13:40Z

INHERITED: content from T009–T012 (image, gitconfig, profile.d, compose) and the bats file bash-c-and-bash-lc-defaults-in-effect.bats (confidence: high)
ABSENT: nothing changed in code — this entry records the verification the task was waiting on
Verification: Docker lane run 2026-09-28T12:08:54Z by the operator on the host, image stamped b235f39 (tests/out/summary.json exit 0); bash-c-and-bash-lc-defaults-in-effect.bats → 12 tests, 0 failed, 0 skipped (tests/out/report.xml)
SCOPE: none — no files outside the feature's artifacts changed

### T022: verified in the Docker lane (SC-3)
**Started:** 2026-09-28T12:08:54Z | **Completed:** 2026-09-28T12:13:40Z

INHERITED: content from T009–T012 (image, gitconfig, profile.d, compose) and the bats file credentials-fail-fast-and-hooks-off.bats (confidence: high)
ABSENT: nothing changed in code — this entry records the verification the task was waiting on
Verification: Docker lane run 2026-09-28T12:08:54Z by the operator on the host, image stamped b235f39 (tests/out/summary.json exit 0); credentials-fail-fast-and-hooks-off.bats → 40 tests, 0 failed, 0 skipped (tests/out/report.xml)
SCOPE: none — no files outside the feature's artifacts changed

### T025: verified in the Docker lane (SC-4)
**Started:** 2026-09-28T12:08:54Z | **Completed:** 2026-09-28T12:13:40Z

INHERITED: content from T009–T012 (image, gitconfig, profile.d, compose) and the bats file agent-cannot-run-as-root-change-firewall-or-read-adele.bats (confidence: high)
ABSENT: nothing changed in code — this entry records the verification the task was waiting on
Verification: Docker lane run 2026-09-28T12:08:54Z by the operator on the host, image stamped b235f39 (tests/out/summary.json exit 0); agent-cannot-run-as-root-change-firewall-or-read-adele.bats → 18 tests, 0 failed, 0 skipped (tests/out/report.xml)
SCOPE: none — no files outside the feature's artifacts changed

### T039: H8 stamp verified end to end
**Started:** 2026-09-28T12:08:54Z | **Completed:** 2026-09-28T12:13:40Z

INHERITED: stamp_check (T013) runs in every bats file's setup_file; the SC-5 bats asserts timelike --agent-info revision == GIT_SHA (T030) (confidence: high)
ABSENT: no separate label-inspection test beyond stamp_check — it already compares GIT_SHA, the running container's image label and /opt/timelike/REVISION
Verification: Docker lane run 2026-09-28T12:08:54Z by the operator on the host, image stamped b235f39 (tests/out/summary.json exit 0); all 118 bats tests ran after stamp_check passed; conformance bats (10/10) includes the revision == GIT_SHA test; build log shows REVISION written from b235f39
SCOPE: none — no files outside the feature's artifacts changed

### T042: start-up measured in the image (quality-standards C2)
**Started:** 2026-09-28T12:12:00Z | **Completed:** 2026-09-28T12:42:23+00:00

INHERITED: tests/unit/test_agentio_startup.py (T008), run by the Docker lane's unit step on /opt/timelike/python/bin/python3 -I (T014) (confidence: high)
ASSUMED: the < 100 ms p95 assertion passing in the image satisfies C2's "re-measure"; the figure itself was not printed (pytest -q) (confidence: medium)
DEFERRED: printing the in-image figure — the next Docker-lane run can add -s for that test; recorded in quality-standards Performance Budgets as "passed, figure not printed"
ABSENT: no in-image figure to compare with the host's 56.7 ms
Verification: Docker lane run 2026-09-28T12:08:54Z by the operator on the host, image stamped b235f39 (tests/out/summary.json exit 0); unit step 151 passed on the image's interpreter (tests/out/unit.txt), including the start-up budget test
SCOPE: none — no files outside the feature's artifacts changed

### T034 (addendum, R4-scan): discovery revision 4 in the supply-chain gate — enforced overdue, 90-day cap, T1 escalation
**Started:** 2026-09-28T12:25:00+00:00 (approximate) | **Completed:** 2026-09-28T12:45:54+00:00

INHERITED: enforced overdue rule, 90-day cap and the four escalation fields, from discovery revision 4 via bridge/feedback/gov-20260928-063634.md § Resolution and bridge/governance-context.md "What Changed" (confidence: high)
INHERITED: the 5-column exemptions header from the coordinator's revision-4 governance audit (confidence: high)
ASSUMED: "more than 90 days" means Review by − Reviewed > 90 days: exactly 90 passes, 91 fails; Reviewed equal to today is not in the future (confidence: high)
ASSUMED: the affected image in each escalation is the scanned image (--image), not the free text of the row's "Component / image" cell (confidence: medium)
FLAGGED: kept verdict.json's `component` and added `image`, `date`, `update`, over renaming it to `package` — existing readers of verdict.json would break (confidence: medium)
FLAGGED: the escalation for an unexempted unfixable finding suggests one row per identifier naming every affected package, dated today and today+90 — a repeated identifier is itself invalid, so a row per package would produce an invalid table (confidence: high)
FLAGGED: overdue and capped rows point at column "Review by", with "Reviewed" to update after a person re-reviews — re-arming needs both dates and only a person can set Reviewed (confidence: medium)
DEFERRED: CVE-2026-82049 (python 3.12.14, "fixed" in 3.14.0b1) blocks as fixable — whether a fix only in another minor line counts as "fixed" for H9 is a policy call, raised in FOR-MENTOR Item 7
ABSENT: scan.sh unchanged and not re-run; the real-data check ran the evaluator on the host against a scratch copy of scan/out, not inside the image
ABSENT: no exemption rows written — the 80 unfixable findings need a person's review, which is what the gate exists to require
Implemented by the scan subagent; reviewed and committed by the coordinator. Verification: 70 scan tests pass, evaluate.py 99% line+branch; host lane 167 passed + env layer 32/32; ruff, mypy --strict clean. plan.md Complexity Tracking updated to 525 lines
SCOPE: in (3 changed files) (corrected by hand: the helper's start point preceded the separate governance commit 224858e, so its first record counted that commit's files)

### T036: supply-chain scan run and recorded
**Started:** 2026-09-28T12:13:00Z | **Completed:** 2026-09-28T12:18:00Z

INHERITED: scan/scan.sh and evaluate.py (T034, T035); the operator's `make scan` on the host (confidence: high)
FLAGGED: no exemptions written for the 80 unfixable findings, and the pin not bumped for the one fixable finding — chose to put both to plan (FOR-MENTOR Item 7) over writing 38 reviewed rows now, because the mentor asked for the policy to be settled first and because "fixed only in another minor line" is a reading of H9, not a fact (confidence: high)
ASSUMED: the 49/31/1 layer split is read from the SBOM's layer locations (earliest layer that holds the package) (confidence: medium)
ABSENT: no second scan with revision 4's evaluator inside the image — the evaluator was re-run on the host against a copy of the real scan/out; the next `make scan` runs it in the image
Verification: scan/out/steps.tsv — sbom, grype, pip-audit, gitleaks all ran; verdict FAIL, 81 blocking (80 unfixable, 38 distinct CVEs, 1 fixable); recorded in cycle-report.md verification addendum and FOR-MENTOR Item 7
SCOPE: out — .specswarm/metrics.json FOR-MENTOR.md (2 of 2 changed files) (task has FLAGGED: yes)


### T043: Python pinned to 3.14.7 (discovery revision 5, stack.md at plan d606ed1)
**Started:** 2026-09-28T13:40:00Z | **Completed:** 2026-09-28T13:48:00Z

INHERITED: "pin the current stable 3.14.x" — stack.md Python row via ../bridge/governance-context.md; tech-stack.md 1.3.0 (confidence: high)
ASSUMED: 3.14.7 is the current stable 3.14 — python.org/ftp lists 3.14.7 as its newest 3.14 directory, and uv 0.12.19's download metadata carries `cpython-3.14.7-linux-x86_64-gnu` with no prerelease tag, from python-build-standalone 20260924, the same release as the old pin (confidence: high)
ASSUMED: uv installs the baseline `x86_64-gnu` build, not an `x86_64_v3` variant, so the Dockerfile's `cpython-${PYTHON_VERSION}-linux-x86_64-gnu` path holds — it held for 3.12.14 on the same uv; the Dockerfile fails the build loudly and lists what it found if not (confidence: medium)
ASSUMED: no code needs changing for 3.14 — grep found none of the modules or APIs removed in 3.13/3.14 in tools/, scan/ or tests/ (confidence: medium; the Docker lane's unit step runs the suite on 3.14.7)
ABSENT: not built here (no Docker daemon, research R10). The Dockerfile's two interpreter checks (path exists; `platform.python_version()` equals the pin) verify it at build time
Verification: pending T047 (`make build`, then `make test`'s unit step on /opt/timelike/python/bin/python3 -I)
SCOPE: in — pins.env .specswarm/features/001-agent-shell-baseline/research.md README.md (3 of 3 changed files named by T043)

### T044: openssh-client removed; SC-3 ssh tests rewritten
**Started:** 2026-09-28T13:48:00Z | **Completed:** 2026-09-28T14:02:00Z

INHERITED: remove `openssh-client` unless an acceptance criterion needs it (stack note 15; supply-chain resolution § Question 1, item 6); keep the https credential fail-fast tests (the send, "What changed", item 3) (confidence: high)
FLAGGED: `GIT_SSH_COMMAND` removed with the client, over keeping it as a dormant safe default — chose removal because nothing can test a setting for a binary that is absent, and an untested default reads as a guarantee. A later feature that installs ssh for a criterion must bring the default and its test back (confidence: medium)
ASSUMED: git reports a missing ssh as "cannot run ssh: No such file or directory" (run-command's `cannot run %s`), which the rewritten test asserts so that a fast failure is shown to have the right cause (confidence: medium; the Docker lane confirms or corrects the string)
ASSUMED: no criterion needs ssh — prompt 01's SC-3 says "a git operation that would need credentials fails fast", which the http-401 cells show over git's shared credential path (confidence: high)
Verification: shellcheck clean on the bats file; 118 tests still (9 "no ssh client" cells replace 9 "unreachable host" cells, 4 "no ssh on PATH" replace 4 BatchMode checks). The Dockerfile now fails the build if any ssh is on PATH. Docker-lane run pending T047
SCOPE: in — image/Dockerfile tests/e2e/credentials-fail-fast-and-hooks-off.bats .specswarm/features/001-agent-shell-baseline/research.md (3 of 3 changed files named by T044 or its research note)

### T045: discovery revision 5 in the supply-chain gate — a reviewed baseline per base digest
**Started:** 2026-09-28T14:02:00Z | **Completed:** 2026-09-28T15:05:00Z

INHERITED: the baseline rule, "fix available", severity from the scanner's source — supply-chain resolution § Question 1–2, constitution H9 1.2.0, quality-standards § Exemptions (confidence: high)
FLAGGED: "per image digest" is read as the **pinned base digest** (`DEBIAN_IMAGE` in pins.env), not the built image's id — chose it because the built image changes on every commit (the GIT_SHA stamp, H8), so keying the review to it would demand a re-review per commit, while the resolution's trigger is "when the pinned digest moves" (confidence: medium)
FLAGGED: a fix listed **only as a pre-release** (e.g. Grype's `3.14.0b1` for CVE-2026-82049) does not block as fixable and may be baselined, and every line saying so tells the reviewer to upgrade instead if a stable release has it — chose this because H9 says a pre-release never counts and the evaluator cannot see which stable releases exist; the person reviewing the baseline is the control. Today's case needs no baseline: T043 moves to 3.14.7 (confidence: medium)
FLAGGED: an unusable baseline (malformed, unreviewed, overdue, past the cap, other digest or image) yields **one blocking line per defect** with a count of the findings it lists, not one line per finding — chose it so an overdue date reads as one edit and not 77 (confidence: high)
ASSUMED: origins come from the SBOM alone: layer 0 is the base layer; a package added later traces up `dependency-of` links to the top-level added packages (on the last real scan: 49 base layer, 28 git, 3 openssh-client, 1 files under /opt/uv-python). All 258 Grype matches carried Syft's artifact id, so the join is exact (confidence: high)
ASSUMED: an entry matches by identifier (or an alias) **and** package name, not version: apt fetches current security updates at build time without the digest moving, and a version-only change is not a new finding (confidence: medium)
ASSUMED: an origin without an entry in the SBOM falls back to "<scanner> package" in the proposal; origins never fail a step, since they only feed the proposal (confidence: high)
ABSENT: not run in the image. Smoke-tested on the host against a copy of the operator's real scan/out (12:1xZ run): FAIL, 81 blocking, a proposal of 81 entries in 4 origin groups
Verification: tests/unit 173 passed (host venv, Python 3.12); test_scan_baseline.py 46 and test_scan_report.py 30 tests; evaluate.py 99% line+branch; ruff, mypy --strict, shellcheck clean
SCOPE: in — scan/evaluate.py scan/scan.sh tests/unit/test_scan_baseline.py tests/unit/test_scan_report.py tests/unit/test_scan_exemptions.py (deleted) .specswarm/features/001-agent-shell-baseline/plan.md (6 of 6 changed files named by T045 or its complexity-tracking row)

### T046: baseline drafted for timelike-agent; awaiting a person's review
**Started:** 2026-09-28T15:05:00Z | **Completed:** 2026-09-28T15:30:00Z

INHERITED: the 77 findings and their origins, from the evaluator's proposal over the operator's real scan (image sha256:c3a3370b7ea6), less the 4 removed by T043 and T044 (confidence: high)
FLAGGED: `reviewed` and `review_by` are left as placeholders, over dating the file today — chose it because H9 says a person reviews the baseline; a code instance writing its own review date would be the stamped-audit failure the governance rules forbid. Until a person sets them, the gate accepts nothing from this file and `make scan` fails with one escalation naming both fields (confidence: high)
ASSUMED: the Critical reasons rest on how git's http transport uses libcurl (no cookie file, no proxy, no .netrc, no HTTP/2 stream dependencies, no server-push callback, no Negotiate credentials) and on P4 (the agent holds no credentials in slice 0). Each names what would make it void: credentials or an egress proxy arriving with Adele (feature 12) (confidence: medium; for a person to confirm at review)
ASSUMED: the base-layer reason rests on research R7 and SC-4 (no capabilities, no-new-privileges, no setuid or setgid file), which removes the privileged process the util-linux and acl escalation findings need (confidence: high)
ABSENT: the new image (3.14.7, no openssh-client) is not scanned yet, so its exact set is unconfirmed. Any finding it has that this file lacks blocks and appears in scan/out/baseline.proposed.json
Verification: with the two dates filled in (scratch copy, not committed), the evaluator over the real scan/out gives 77 baselined (8 Critical, 69 High) and 4 blocking: exactly the openssh-client and Python 3.12 findings this cycle removes. test_scan_baseline.py pins that the committed file has no defect other than the two review fields
SCOPE: in — scan/baseline/timelike-agent.json tests/unit/test_scan_baseline.py (2 of 2 changed files named by T046)

### T047 (fix): unit test hid the stdlib from importlib.metadata on Python 3.14
**Started:** 2026-09-28T21:20:00Z | **Completed:** 2026-09-28T21:35:00Z

INHERITED: the operator's Docker lane at 3690e76 (run 2026-09-28T21:03:17Z): unit 173/174, `test_dists_counts_what_the_interpreter_sees[names1]` failed with `ModuleNotFoundError: quopri` on /opt/timelike/python/bin/python3 -I (3.14.7); the mentor's history line of 21:09:57Z and its sign-off list (confidence: high)
FLAGGED: the test's `sys.path` is now the fake site followed by the stdlib directories only, not the fake site prepended to the whole `sys.path` as the sign-off suggested. Prepending would expose the interpreter's own site-packages, and the exact count `len(names)` would then include pip, pytest and so on, so the test would fail differently. Keeping only the stdlib fixes the cause (reading METADATA imports email, which from 3.14 imports quopri lazily) and keeps the assertion exact (confidence: high)
ASSUMED: a test-only defect, not a product one. `evaluate.py dists` runs with the interpreter's normal `sys.path` in scan.sh, and the operator's scan at 3690e76 ran it: pip-audit PASS, 1 distribution (confidence: high)
Verification: reproduced on the host by evicting email and quopri from sys.modules. The old sys.path gives ModuleNotFoundError; the new one lists only the fake distribution. tests/unit 174 passed (3.12 venv), ruff and mypy clean. The Docker lane's unit step on 3.14.7 needs the operator's re-run of `make test`
SCOPE: in — tests/unit/test_scan_report.py (1 of 1 changed file; T045 owns the scan tests)

### T054: in-image start-up figure surfaced into tests/out/ (operator decision 1)
**Started:** 2026-09-28T22:05:00Z | **Completed:** 2026-09-28T22:20:00Z

INHERITED: "make the in-image run write its p95 (and the sample count) into tests/out/" — the send, operator decision 1; quality-standards C2 (confidence: high)
FLAGGED: the figure goes from the test's stdout through pytest `-rP` into unit.txt, and run.sh (host side) writes tests/out/startup.json, over mounting tests/out into the unit container for the test to write a file — chose it because the unit container runs as the agent user (uid 1000) while tests/out/ belongs to the runner's uid, so a mount would need a permission change for one file, and `-rP` adds output only for passing tests that print (confidence: high)
ASSUMED: a missing line is recorded as `{"measured": false, "reason": …}`, never omitted — a failed or skipped start-up test must not leave a stale figure that reads as current (confidence: high)
ASSUMED: run_unit keeps pytest's exit code (PIPESTATUS[0]) after write_startup runs (confidence: high)
Verification: host run of the test with -rP printed `TIMELIKE_STARTUP p95_ms=57.5 runs=50 python=3.12.3 …`; write_startup exercised on a synthetic unit.txt with and without the line: both outputs valid JSON; shellcheck and ruff clean. The 3.14.7 figure needs the operator's `make test` (T057)
SCOPE: in — tests/unit/test_agentio_startup.py tests/run.sh (2 of 2 changed files named by T054)

### T055: SC-11 support — the README states what a reader can predict
**Started:** 2026-09-28T22:20:00Z | **Completed:** 2026-09-28T22:35:00Z

INHERITED: SC-11 (Manual): "A person reading the output contract can predict, for a tool they have not seen, what its first line, last line and exit codes will be"; contract rules 2, 3, 5, 12 (confidence: high)
FLAGGED: the README now states the first line, last line and exit codes exactly as agentio implements them, and says plainly that an uncapped text output's last line is not fixed; raised as FOR-MENTOR Item 8, over changing agentio to always end text output with `exit: <code>` — chose not to change the contract's behaviour for every tool without the mentor/plan, because the contract comes from the prompt and the spec says slice 1 does not redefine it (confidence: high)
ABSENT: no change to `timelike --help` or the image: the README already linked the contract, and adding a document path to the image would touch the Dockerfile owned by T050 for no criterion gain
Verification: the three statements were checked against tools/agentio/agentio.py (the text and JSON branches, lines ~400–450) and contracts/output-contract.md. SC-11 stays `unconfirmed` until a person reads it
SCOPE: in — README.md FOR-MENTOR.md (2 of 2 changed files; T055 names the README, and Item 8 is where the gap is raised)

### T056: FOR-MENTOR Items 1–3 closed
**Started:** 2026-09-28T22:35:00Z | **Completed:** 2026-09-28T22:38:00Z

INHERITED: operator decision 3 in send `…-214635`: the mentor reconciled Items 1–3; Item 1's text is out of date ([2, 3] vs [2, 3, 4, 5]) (confidence: high)
ASSUMED: closing keeps each item's history and prepends the closure with its evidence, rather than deleting it; Item 1 states the current audit list so its old table does not mislead (confidence: high)
Verification: FOR-MENTOR.md Items 1–3 read "closed 2026-09-28" with evidence; open items are now Item 8 only
SCOPE: in — FOR-MENTOR.md (1 of 1 changed file named by T056)

### T053: natural intensity — common failures beside the slice-0 happy paths (delegated to a subagent)
**Started:** 2026-09-28T21:58:00Z | **Completed:** 2026-09-28T22:10:00Z

INHERITED: the check-function + one-line-@test pattern, run_in/assert_within bounds, artefact reads via exec_plain, the 401 fixture with request-count proof (confidence: high)
FLAGGED: SC-1 and SC-3 failure cells run under bash -c and bash -lc in the mode that exposes the trap, over the full 3×3 matrix — the happy paths and SC-2 already prove the defaults reach every style and mode; these prove the defaults also cover another code path (confidence: medium)
FLAGGED: `git add -p` only in notty — it reads stdin, not the terminal, so under `docker exec -t` it would block whatever the defaults are, as `cat` would; R5 leaves stdin readers to the harness's /dev/null (confidence: high)
FLAGGED: the two SC-5 cells for a tool whose interpreter path does not exist assert the criterion and were expected to fail until the product gap was fixed, over skipping them — a skip would hide the gap. The gap is fixed in T059 (confidence: high)
FLAGGED: `git log --help` asserts whichever case the image has (no man viewer: rc 128; else rc 0), read in the same run, over hard-coding rc 128 (confidence: medium)
ASSUMED: no man and no python3 on PATH in the image (slim base, --no-install-recommends, uv --no-bin); both tests hold either way (confidence: high)
ASSUMED: SC-4's no-write test checksums T050's /etc/timelike/shell-env.bash and profile.d file, so those ship in the same merge (confidence: high)
ABSENT: GIT_TERMINAL_PROMPT has no gitconfig fallback, so an agent that unsets it re-enables terminal prompts; with `env -i` the system hooksPath loses to a repo-local one (R3 caveat). Neither is tested or claimed. Not added: `tag -a` without -m (same editor path as commit), repo-local credential helper (a clone never carries config), setpriv/chmod on Adele's files (covered by capability reads), conformance hang/off-PATH/C1–C8 (unit-tested)
Verification (subagent, host): each git scenario reproduced with the image's ENV block and /etc/gitconfig (git 2.43, bash 5.2, pty via script): amend rc 0 message kept; diverged merge rc 0 two parents; conflict rc 1 MERGE_HEAD present; mid-merge commit rc 0; rebase -i rc 0; add -p rc 0 nothing staged; log --help rc 128; user@ URL rc 128 terminal prompts disabled; clone vs 401 rc 128 directory removed; .git/hooks 0 markers (3 with the env layer removed). Negative control: with the defaults removed, amend, merge, mid-merge commit and rebase -i hung (rc 124). `git config --system` as non-root: rc 255. shellcheck clean. 118 → 152 tests in the six files. Docker lane pending (T057)
Product gap found: timelike-conform crashes on a tool whose interpreter path does not exist (Popen unguarded in run_probe): "error: internal error: FileNotFoundError …", no tool or rule named, every other verdict lost. Fixed in T059
SCOPE: in — tests/e2e/git-log-diff-commit-rebase-exit-within-20-seconds.bats tests/e2e/bash-c-and-bash-lc-defaults-in-effect.bats tests/e2e/credentials-fail-fast-and-hooks-off.bats tests/e2e/agent-cannot-run-as-root-change-firewall-or-read-adele.bats tests/e2e/conformance-check-over-every-timelike-tool-on-path.bats tests/e2e/peer-agents-write-to-own-scratch-space.bats tests/e2e/fixtures/sc1-repo.sh tests/e2e/fixtures/timelike-envpython tests/e2e/fixtures/timelike-nointerp (9 of 9 changed files named by T053)

### T059: timelike-conform judges a tool that cannot execute instead of crashing (gap found by T053)
**Started:** 2026-09-28T22:40:00Z | **Completed:** 2026-09-28T22:55:00Z

INHERITED: SC-5 "fails when any tool lacks … naming the tool and the rule"; T053's reproduction ("error: internal error: FileNotFoundError", no tool named, other verdicts lost) (confidence: high)
FLAGGED: fixed in this cycle, over only reporting it — natural intensity exists to surface the common failure, and this breaks a slice-0 criterion in this feature's own code; the fix is 8 lines at the one call site (confidence: high)
ASSUMED: an exec failure maps to the shell's codes, 127 (ENOENT) and 126 (EACCES), so the existing checks name it (C1 help, C6 exit vocabulary, C7 events, …) with no special rule — the same verdict a `#!/usr/bin/env python3` tool already gets from /usr/bin/env's 127 (confidence: high)
ASSUMED: a non-executable file stays outside discovery (discover() takes X_OK files only): it is not a command on PATH, so it is not a tool. The EACCES case tested is an executable tool whose interpreter is not executable (confidence: high)
Verification: unit test test_a_tool_that_cannot_execute_is_named_and_the_others_still_judged[missing, not-executable] passes with the fix and fails without it (stash check); host reproduction names timelike-nointerp under C1–C7 with exit 127 and no internal error; test_conform_violations.py 24/24; ruff, mypy --strict clean. The e2e cells (T053) run in the Docker lane (T057)
SCOPE: in — tools/bin/timelike-conform tests/unit/test_conform_violations.py tests/e2e/conformance-check-over-every-timelike-tool-on-path.bats (3 of 3 changed files named by T059, the last only its comments)

### T050: container-derived shell defaults — the hook, its wiring, TZ and PYTHON_BASIC_REPL (delegated; reviewed and amended)
**Started:** 2026-09-28T21:58:00Z | **Completed:** 2026-09-28T23:10:00Z

INHERITED: modify.md F001–F004: BASH_ENV for bash -c, profile.d for bash -lc, a line appended to /etc/bash.bashrc for interactive bash; TZ and PYTHON_BASIC_REPL as static ENV (confidence: high)
ASSUMED: bash -lc reads BASH_ENV after the profile files, so the hook runs twice there — confirmed with env -i (R1 agrees); the hook is idempotent, pinned by a test (confidence: high)
FLAGGED: variables enumerated with ${!A@}…${!_@} and ${!name@a}, over `compgen -e` — capturing compgen's output needs a fork, and the hook forbids forks at every shell start (confidence: high)
FLAGGED: GIT_CONFIG_KEY_<n> always kept, over the design's pure component rule — GIT_CONFIG_KEY_0 contains the component KEY; stripping it while GIT_CONFIG_COUNT=1 makes every git command fail ("missing config key"), verified (confidence: high)
FLAGGED (coordinator, in review): password/token/secret matched when a component ENDS with the word (PGPASSWORD, GHTOKEN, OAUTH_CLIENTSECRET), over whole components only — the delegate's rule missed PGPASSWORD, which plainly matches SC-9's "password pattern"; the key family stays whole-component, because a suffix match would take MONKEY and HOTKEY. modify.md F002 amended (confidence: high)
FLAGGED: strip on every bash start, over once per exec with a marker — a marker the environment can carry is a bypass, and the rule is "absent from the agent's shells". Cost: an agent that exports FOO_TOKEN and runs `bash script.sh` loses it there unless allow-listed (confidence: medium)
FLAGGED: "explicit wins" means set and non-empty; TIMELIKE_CPUS is always recomputed; a value inherited from a parent's hook is explicit and the same figure (confidence: high)
FLAGGED: neither cpu.max nor /proc/self/status readable → TIMELIKE_CPUS=1; cgroup v1 falls back to the affinity count (confidence: medium)
FLAGGED: the hook discards its own stderr and switches errexit/nounset/xtrace off locally, so it stays silent and harmless under bash -eux (confidence: high)
ASSUMED: TZ="UTC" suffices without /etc/localtime (glibc reads it as a POSIX TZ string; checked with TZDIR=/nonexistent) (confidence: high)
ABSENT: sh -c and direct execs of non-shell binaries get neither job counts nor the strip (spec Out of Scope); /proc/1/environ is untouched; names that are not shell identifiers (MY-TOKEN) pass through, since bash cannot unset them; SSHPASS, MYSQL_PWD and GITHUB_PAT match none of the criterion's patterns and are kept (documented in the hook)
ABSENT: the TIMELIKE_ENV_ALLOW note the impact analysis promised for the README — added by the coordinator in T058's README pass
Verification: the Dockerfile's own build-time smoke run (env -i, bash -c: GITHUB_TOKEN stripped, TIMELIKE_CPUS ≥ 1); host lane 60/60 env layer, 29/29 hook logic after the amendment; direct spot-check: PGPASSWORD and MY_SECRETS stripped, allow-listed GHTOKEN, TOKENIZERS_PARALLELISM, MONKEY, HOTKEY, GIT_ASKPASS, PASSAGE_COUNT, GIT_CONFIG_KEY_0 kept; shellcheck clean. The image build is the Docker lane's (T057)
SCOPE: in — image/Dockerfile image/rootfs/etc/timelike/shell-env.bash image/rootfs/etc/profile.d/10-timelike-shell-env.sh .specswarm/features/001-agent-shell-baseline/modify.md (4 of 4 changed files named by T050 or its design)

### T051: e2e for SC-8, SC-9, SC-10 — tests/e2e/container-derived-defaults.bats (delegated; reviewed)
**Started:** 2026-09-28T21:58:00Z | **Completed:** 2026-09-28T23:12:00Z

INHERITED: the bats conventions (stamp_check, run_in styles c/lc/ic, one test per criterion per style, names after the distinguishing text, driven from outside the image) (confidence: high)
FLAGGED: SC-8 runs in throwaway containers from the running container's image id, with compose's cap_drop, no-new-privileges and init: one with `--cpus (L-1).5` (L = 2 on a host with ≥ 3 CPUs, else 1; expects L, which also tests rounding up), one with `--cpuset-cpus <one CPU>` and no quota (expects 1). The host count is the smaller of docker info NCPU and the agent container's affinity; both limits are read back from cpu.max and status before asserting (confidence: medium)
FLAGGED: FAIL, over skip, on a host with fewer than 2 usable CPUs or on cgroup v1 — a bats skip leaves the lane green with the criterion never run; only SC-8 fails, with the reason (confidence: medium)
FLAGGED: the REPL test sets TERM=xterm (what `docker exec -t` announces) and feeds input with delays through docker exec -i and script; a control with PYTHON_BASIC_REPL empty must show escape sequences, so the test can fail (confidence: medium)
ASSUMED: python-build-standalone 3.14.7 uses libedit, which prints no escape sequences in basic mode (checked by the delegate on that exact build) (confidence: medium)
ABSENT: the value of every SC-9 secret is a marker searched for in the full `env` dump, so a secret surviving under any name is caught; fake values are short and low-entropy so gitleaks' generic-api-key rule does not fire on the test file (unverified until `make scan`)
Verification (delegate, host): 19/19 with bats 1.14.0 against a fake docker that runs commands locally with the real hook, the parsed ENV and the pinned CPython 3.14.7; with an empty hook all SC-8 and SC-9 tests fail; with 1 CPU the SC-8 tests fail with the stated reason. Coordinator: SC-9 lists extended with PGPASSWORD and GHTOKEN (T050 amendment); shellcheck clean. The real run is the Docker lane's (T057)
SCOPE: in — tests/e2e/container-derived-defaults.bats tests/e2e/helpers.bash (2 of 2 changed files named by T051; helpers additions only: start_throwaway, remove_throwaway, remove_stale_throwaways, cpu_list_count)

### T052: host lane for the env layer and the hook's logic (delegated; reviewed)
**Started:** 2026-09-28T21:58:00Z | **Completed:** 2026-09-28T23:14:00Z

INHERITED: test_env_layer.sh's ENV parser, stand-in profile and self-check style (confidence: high)
FLAGGED: bash -ic simulated with --rcfile holding the Dockerfile's exact appended line (path rewritten), over reading the host's /etc/bash.bashrc; new checks: static wiring, W1 (profile.d alone reaches the hook under bash -lc), N4 (all three wirings removed: the hook's values fail in every style, TZ still holds) (confidence: high)
FLAGGED: host tests redirect stdin from /dev/null — this dev container's bash reads /etc/bash.bashrc under -c when stdin is a socket; an environment quirk, not a product one (confidence: high)
ASSUMED: tests/host/test_shell_env_hook.sh feeds fake cpu.max and status files through the hook's test-only overrides; C1–C10 CPU figures, E1–E4 explicit wins, S1–S6 strip, Q1–Q4 idempotent/silent/clean, N1–N2 non-bash no-op; X1 empty-hook control, X2/F1 fork detection (`ulimit -u 1`, empty PATH) (confidence: high)
Verification: make test-host — 176 unit, env layer 60/60, hook logic 29/29 (after T050's amendment, with PGPASSWORD, GHTOKEN, OAUTH_CLIENTSECRET added to the strip cases); the delegate's mutation runs (no GIT_CONFIG_KEY exemption, no `local -`, an echo, substring ASKPASS) each turned the right tests red; Makefile lint list extended; shellcheck clean
SCOPE: in — tests/host/test_env_layer.sh tests/host/test_shell_env_hook.sh tests/host/run.sh Makefile (4 of 4 changed files named by T052; Makefile only its SHELLCHECK_FILES list)

### T061, T062: the contract states the uncapped case; README aligned (discovery revision 6)
**Started:** 2026-09-28T23:40:00Z | **Completed:** 2026-09-28T23:48:00Z

INHERITED: plan's ruling (feedback 01-20260928-225646 § Resolution, § 3): "last line" means a predictable kind; the SC-11 table (capped / uncapped / JSON); state the uncapped case in the contract itself; remove the README's "does not fix that line yet" (confidence: high)
ASSUMED: the contract gains a paragraph on cut vs not cut, the omission line's only-when-capped sentence, and plan's table — words only; agentio already behaves this way (text branch ends on the body when uncapped; the capped branch ends on the omission line; JSON carries exit and truncated) (confidence: high)
Verification: grep finds no "does not fix" left; statements checked against tools/agentio/agentio.py (text and JSON branches) and tests/unit/test_agentio.py (rule 2 cases)
SCOPE: in — .specswarm/features/001-agent-shell-baseline/contracts/output-contract.md README.md (2 of 2 changed files named by T061 and T062)

### T063: revision 6 recorded on the spec (modify Step 9, full); rule clarifications copied
**Started:** 2026-09-28T23:48:00Z | **Completed:** 2026-09-28T23:58:00Z

INHERITED: modify's provenance table (row 7: prompt revision 6 > prompt_revision 2, not in [2]); the send: "Append 6 … Not a regeneration" (confidence: high)
FLAGGED: full mode, appending 3, 4, 5, 6, over appending 6 alone as the send worded it — modify's Step 9 rule: full applies when the spec was checked against revision N's whole criteria set and removals are visible; the diff against the archived revision-2 send shows none, and revisions 3–5 never touched prompt 01, so claiming them is accurate, not padding. The audit-log row states the basis (confidence: medium — the mentor may prefer 6 alone; the log makes the choice disputable)
FLAGGED: the spec's rule list gains plan's two clarifying sentences, over leaving the body untouched — the body is not false (not SUPERSEDED), but a spec whose rule text lags its prompt is what SC-11's reader would trip on; `prompt_revision` stays 2 and `discovery_revision` stays 3, because only /specswarm:specify writes those and modify Step 9 forbids touching them. The mentor asked that this be said in the cycle report, not hand-stamped (confidence: high)
ASSUMED: `source_send` moves to this send, as in cycle 3 (the mentor's earlier note allows it); the generating send is recorded in modify.md (confidence: medium)
Verification: spec frontmatter audited_against [2, 3, 4, 5, 6]; audit-log.md created with both cycles' rows (cycle 3's marked as written in cycle 4)
SCOPE: in — .specswarm/features/001-agent-shell-baseline/spec.md .specswarm/features/001-agent-shell-baseline/audit-log.md (2 of 2 changed files named by T063)

### T064: C2 start-up figure recorded with its conditions (operator decision; governance-only)
**Started:** 2026-09-28T23:30:00Z | **Completed:** 2026-09-29T00:10:00Z

INHERITED: tests/out/startup.json at 01ee1ce: p95 88.1 ms, 50 runs, 3.14.7; the send's step 4: record the figure *and* its conditions, and if the conditions make it slower than real use, say why without assuming (confidence: high)
FLAGGED: the "slower than real use" claim rests on a host experiment by a subagent, over reasoning from the conditions alone — the send asked for evidence. Same CPython 3.14.7 build, the test's own PROGRAM and p95 method, 8 conditions × 3 × 50 spawns, repeated twice: test conditions 88.5 ms, real-tool path 77.2 ms; ~8 ms from compiling agentio from the read-only source each run (C1−B, A−C5, C3−C4 agree), ~3 ms from uv's ephemeral env (its overlay .pth survives -I); plain venv, sys.path insert, shebang vs -c ≤ 1 ms (confidence: medium — host, not image)
FLAGGED: the test is not changed now to measure the tools' own path, over changing it in this cycle — a test change voids the host results the send says stand, and the recorded figure errs on the safe side; quality-standards names the change that would make it authoritative (confidence: high)
ABSENT: no in-image measurement of the real-tool path; the host experiment's absolute numbers are not calibrated to the Docker lane's CPU; EROFS (a real :ro mount) vs EACCES (chmod) not distinguished
Verification: quality-standards Performance Budgets rewritten; the 3.12-era "did not print the figure" wording is gone. The experiment's scripts and results are in the session scratchpad (startup-exp/), not in the repository
SCOPE: in — .specswarm/quality-standards.md (1 of 1 changed file named by T064; governance-only, no audit entry)

### T066: governance audited against discovery revision 7 (cycle 5)
**Started:** 2026-09-30T03:40Z | **Completed:** 2026-09-30T03:50Z | **Coordinator** (on master, 9688118, before this branch)

INHERITED: ../bridge/governance-context.md (/mentor:regovern 2026-09-29T09:40:34Z) § What Changed — (confidence: high)
FLAGGED: the constitution restates the tension table, so T4 is added (MINOR, 1.2.0 → 1.3.0), and P1 and P2 name it as P1 names T1 — chose restating over a pointer, to keep the table whole (confidence: high)
ASSUMED: tech-stack and quality-standards derive from stack.md and Constraints, which revision 7 did not touch, and neither states the old hooks default; both audited with no change — (confidence: high)
ABSENT: no governance gate for "hooks run"; it arrives as acceptance criteria SC-12 and SC-13, not as a quality gate
Verification: all three files read [2, 3, 4, 5, 6, 7]; specswarm 2.18.0's quality-standards and tech-stack parsers read every key as before
SCOPE: none — governance files only, committed on master

### T067: the git-hook dispatcher and its 25 links (research R11)
**Started:** 2026-09-30T03:55Z | **Completed:** 2026-09-30T04:06:53+00:00 | **Coordinator**

INHERITED: R3's precedence finding (command scope beats local); the bench wrapper's group-kill lesson (002 RB5) — (confidence: high)
FLAGGED: git's stdin is forwarded to the hook, not replaced with /dev/null as the ruling's example said, because pre-push and post-rewrite read their input from it and git never hands a hook a terminal — (confidence: high)
FLAGGED: the limit is 60 s, below Claude Code's 120 s call timeout; the environment variable beats the repository setting, which beats the default — (confidence: medium: 60 s may be short for a heavy test-suite hook, and raising it is one variable)
FLAGGED: push-to-checkout, proc-receive and fsmonitor-watchman are not linked: git changes behaviour when the first two merely exist, and git does not reach the third through core.hooksPath. Receive-side only, and named in R11 — (confidence: medium)
ASSUMED: dash is /bin/sh in the image (Debian); GNU timeout from coreutils — (confidence: high)
ABSENT: no caching of the core.hooksPath lookup across dispatches; about 30–40 ms per commit, measured, accepted (R11)
Verification: shellcheck -s sh clean. Host experiments, each in its own session under a watchdog: default-location reject (rc 1 with the hook's message); husky local path runs; a hang stopped at 2 s with a verdict and no leftover child; the limit from git config; a bad value reported; a non-executable hint; pre-push stdin (1 line through the dispatcher, 1 without). Three defects found and fixed on the way: recursion through --git-path hooks, a blocking stdin drain, and dash ignoring <&0 (R11)
SCOPE: in (26 changed files)

### T068: the image points core.hooksPath at the dispatchers (ENV and /etc/gitconfig)
**Started:** 2026-09-30T04:07:24+00:00 | **Completed:** 2026-09-30T04:07:24+00:00 | **Coordinator**

INHERITED: T067's directory; R3's ENV mechanism (GIT_CONFIG_COUNT/KEY_0/VALUE_0), unchanged except the value — (confidence: high)
FLAGGED: the directory is COPYed without --chmod (it would apply to the links too), and modes, ownership and the 25 links are checked in the same RUN, which fails the build if a link was flattened — (confidence: medium: COPY keeping links is Docker's documented behaviour, not built here)
ASSUMED: /etc/gitconfig's fallback hooksPath points at the same directory; when the agent unsets GIT_CONFIG_*, a local core.hooksPath wins and runs unbounded, as without timelike (R11) — (confidence: high)
ABSENT: not built (no daemon here, 001 R10); the Docker lane builds it
SCOPE: in (3 changed files)

### T069: host units for the dispatcher (tests/unit/test_git_hook_dispatch.py)
**Started:** 2026-09-30T04:08:29+00:00 | **Completed:** 2026-09-30T04:08:29+00:00 | **Coordinator**

INHERITED: T067 dispatcher; the image mechanism replayed exactly (GIT_CONFIG_* → the repository's own dispatcher directory, GIT_CONFIG_NOSYSTEM) — (confidence: high)
FLAGGED: a surviving background child is detected by an artefact it would write (.git/survived), not by the process table: pgrep matched the calling shell's own command line three times in this cycle's experiments — (confidence: high)
ASSUMED: host git 2.43 behaves as the image's 2.47.3 for hook resolution and stdin; the Docker lane checks the image — (confidence: medium)
ABSENT: the tests do not cover a global (~/.gitconfig) core.hooksPath, or the /etc/gitconfig fallback with GIT_CONFIG_* unset; the dispatcher reads every non-command scope, and the fallback is recorded in R11
Verification: 18 passed in 8 s: default-location reject with the hook's output, husky local path, passing hook, commit-msg arguments, pre-push stdin, linked worktree, non-executable hint, no recursion, outside a repository, the 25 links, a hang stopped in under 6 s with a verdict naming hook, limit, source and both ways to raise it and no skip word, no surviving child, repository limit, environment beats repository, four bad values, 60 s default
SCOPE: in (1 changed file)

### T070: e2e — SC-3's hooks half removed; SC-12 and SC-13 tests added
**Started:** 2026-09-30T04:10:17+00:00 | **Completed:** 2026-09-30T04:10:17+00:00 | **Coordinator**

INHERITED: the old hooks fixtures (husky-style local path; five default-location hook types), reused and inverted; helpers.bash run_in/exec_plain/assert_within — (confidence: high)
FLAGGED: SC-3's file is renamed to credentials-fail-fast.bats; its 20 hooks tests go and its 26 credentials tests stay. New files: hooks-a-repository-configures-run.bats (SC-12: 7 tests) and hook-past-its-time-limit-is-killed.bats (SC-13: 5 tests). The e2e count goes from 176 to 168 — chose one file per criterion, named after its distinguishing text (H7), over editing the old file in place (confidence: high)
FLAGGED: SC-13's limit is tested from all three sources the verdict names: the repository (3 s, per style c/lc/ic), the environment (2 s) and the 60 s default (bash -c only, with the runner's per-command limit raised locally to 90 s) — chose one default-limit test over three, because each costs over 60 s (confidence: high)
ASSUMED: notty only, because a terminal does not change whether git runs a hook or how timeout stops it — (confidence: high)
ABSENT: no tty/pty cells for hooks (the old file had them for "hooks off"); no test for the /etc/gitconfig fallback with GIT_CONFIG_* unset (R11 records its unbounded behaviour)
Verification: shellcheck clean on all three files; the SC-13 fixture script was dry-run locally (the background child fires at limit + 3 s: 63 s default, 6 s for a 3 s limit). Not run: no daemon here (001 R10). A fixture bug was caught at review: the child's delay was escaped into the hook file, where it would always be 3 s, so the default case would have failed falsely
SCOPE: in (4 changed files)

### T070 (follow-up): tests that read the hooks value expect the dispatcher directory
**Started:** 2026-09-30T04:14:13+00:00 | **Completed:** 2026-09-30T04:14:13+00:00 | **Coordinator**

INHERITED: T068's value (/opt/timelike/git-hooks in ENV and /etc/gitconfig) — (confidence: high)
FLAGGED: found by grep after T070, not by a failing run. The SC-2 matrix (bash-c-and-bash-lc-defaults-in-effect.bats: the ENV layer and the /etc/gitconfig fallback), container-derived-defaults.bats, host test_env_layer.sh and test_shell_env_hook.sh S5 all asserted core.hooksPath=/dev/null, and would have failed in the Docker lane. All now expect /opt/timelike/git-hooks — (confidence: high)
ABSENT: the e2e changes have not run (no daemon here)
Verification: shellcheck over every sh/bash/bats file clean; host test_env_layer.sh 60/60, test_shell_env_hook.sh 29/29
SCOPE: out — tests/e2e/bash-c-and-bash-lc-defaults-in-effect.bats, tests/e2e/container-derived-defaults.bats, tests/host/test_env_layer.sh, tests/host/test_shell_env_hook.sh (4 of 4 changed files; tasks.md T070 named only the SC-3/12/13 files) (task has FLAGGED: yes)

### T071: feature 002 moves with the new default (changed_other_features)
**Started:** 2026-09-30T04:14:13+00:00 | **Completed:** 2026-09-30T04:14:13+00:00 | **Coordinator**

INHERITED: the send's item 4 (rejects → tie; hangs → timelike's bounded verdict); 002's catalog, runner and report — (confidence: high)
FLAGGED: the bench's default call limit goes from 30 s to 120 s (Claude Code's default, which the 60 s hook limit is sized for), so the hook's own verdict arrives inside a call as it would under that harness. With 30 s the bench would kill the call first, and both arms would hang alike. Cost: a full bench run takes about 3 minutes longer (vanilla's hang is now 120 s, and timelike's hook stops at 60 s) — (confidence: medium)
FLAGGED: task versions stay at 2 — setup, policy and check are unchanged; the environment moved, and traces record its revision. capability, difference, notes and expected are rewritten; the old timelike:failed note is removed, because it described the hooks-off cause — (confidence: high)
ASSUMED: the catalog's timelike emulation maps /opt/timelike/git-hooks to the repository's dispatchers, in ENV and in a rewritten copy of /etc/gitconfig, with TIMELIKE_HOOK_TIMEOUT=1 below the unit's 2 s call limit — (confidence: high)
ABSENT: the bench has not run in the image with the new default; a live-harness bench (slice 1) keeps both hook tasks, per plan's resolution
Verification: 002 units: catalog + runner 49 passed; cli + validator + report 105 passed. The full run through the stand-in docker gives 0 losses, 2 ties, 2 wins, and hook sections that explain the new default. Also fixed: the unit's copy of the executor wrapper still had dash's broken `kill -- -$t`
SCOPE: in (9 changed files)

### T072: README — hooks run, bounded
**Started:** 2026-09-30T04:14:22+00:00 | **Completed:** 2026-09-30T04:14:22+00:00 | **Coordinator**

INHERITED: R11's limit and ways to raise it — (confidence: high)
ASSUMED: 001's contracts name no hooks behaviour (grep finds none), so only the README changes — (confidence: high)
ABSENT: the README does not describe the dispatcher's internals; research R11 does
SCOPE: in (1 changed file)

### T073: host lane, cycle report (Cycle 5), audit-log
**Started:** 2026-09-30T04:19:21+00:00 | **Completed:** 2026-09-30T04:19:21+00:00 | **Coordinator**

INHERITED: T066–T072 — (confidence: high)
FLAGGED: audited_against is not appended: the send makes revision 7 conditional on the cycle re-establishing what it claims, and SC-12/13 have not run in the image. audit-log records "none (deferred)" with the condition — chose deferring over appending on host evidence, because host evidence never counts as an image-level pass (R10) (confidence: high)
ABSENT: no Docker lane run (no daemon here); the dispatcher is shell, so Python coverage does not measure it; its 18 behavioural host units stand for it
Verification: ruff, format, mypy --strict clean; shellcheck clean over every sh/bash/bats file and `-s sh` on dispatch; unit suite 611 passed, 1 skipped (under coverage); Python coverage 97%; host env-layer 60/60 and shell-env hook 29/29
SCOPE: none — no files outside the feature's artifacts changed

### T070 (second follow-up): SC-4's guard test expects the dispatcher as the system hooksPath (Docker lane at 13e7d10)
**Started:** 2026-09-30T04:47:40+00:00 | **Completed:** 2026-09-30T04:47:40+00:00 | **Coordinator**

INHERITED: the mentor's Docker-lane note, 13e7d10: 166/168; SC-4 check_cannot_alter_guards (bats line 185) still asserted system core.hooksPath == /dev/null — (confidence: high)
FLAGGED: the assertion now expects /opt/timelike/git-hooks, keeping the test's point: the agent's `git config --system` write was refused, so the image's own value is unchanged. The first follow-up's grep missed it because the command and the expected value sit on different lines; a context grep (-B3/-A3) over tests and scripts finds no other /dev/null hooksPath expectation — (confidence: high)
FLAGGED: beyond the requested fix, /opt/timelike/git-hooks/dispatch joins SC-4's checksummed GUARDS, and /opt/timelike/git-hooks joins the directories the agent tries to plant a file in, because the dispatcher now enforces T4's limit and must not be alterable by the agent. Not yet run — (confidence: medium: it widens a passing test; the directory is root-owned 0755 and the file root-owned, so it should hold)
ABSENT: not re-run (no daemon here); the mentor's next lane run shows it
Verification: shellcheck clean
SCOPE: out — tests/e2e/agent-cannot-run-as-root-change-firewall-or-read-adele.bats (1 of 1 changed file; tasks.md T070 did not name it) (task has FLAGGED: yes)

### T074: spec contract rule 5 — revision 9's clarification appended in place, declared (cycle 6)
**Started:** 2026-10-01T19:17:37+00:00 | **Completed:** 2026-10-01T19:17:37+00:00

INHERITED: the impact analysis § Cycle 6 classification (revision 9 needs no body change; criteria identical to rev 7's) and 003's contract amendment at `58b7d11` (confidence: high)
ASSUMED: the right form is revision 6's precedent: the prompt's *(Clarified, revision N: …)* sentence copied into the spec's rule list, plus a note that cycle 6 annotated it and where the contract matches (confidence: high)
FLAGGED: no line of the body states the unconditional "always one of" reading the send asks about, so nothing was corrected, only annotated. Chose "annotate rule 5" over "leave the spec untouched" because the spec would otherwise quote a rule narrower in scope than the contract it governs (confidence: high)
ABSENT: FR-9 and SC-5 ("the exit-code vocabulary") are not reworded: conformance C6/C7 (003) already check a pass-through tool against its declared exits, so they stay true as written
ABSENT: `prompt_revision`, `discovery_revision`, `source_prompt` and `audited_against` untouched (the last waits for the Docker lane, T078)
Verification: the annotation's text equals the send's rule-5 clarification (whitespace-normalised comparison: True)
SCOPE: none — no files outside the feature's artifacts changed

### T075: README states T4's limit under env -i and points at run (cycle 6)
**Started:** 2026-10-01T19:17:56+00:00 | **Completed:** 2026-10-01T19:17:56+00:00

INHERITED: the revision-8 ruling (`../bridge/feedback/01-20260930-060721-unbounded-if-env-unset.md` § Resolution, option (c)) and research R12's host measurement (confidence: high)
ASSUMED: the paragraph goes directly after the hook paragraph in "Environment defaults", where the README describes the limit, as the send says (confidence: high)
FLAGGED: the README names both cases (`.git/hooks` bounded, local `core.hooksPath` unbounded) rather than the ruling's single sentence ("gets git's own behaviour"). Chose the precise statement, because "git's own behaviour" alone would read as "unbounded" for the default case too, which R12 measured as false (confidence: high)
ABSENT: the claim rests on a host measurement (git 2.43.0) until T076's test runs in the image (git 2.47.3); the README cites the test so the two move together
ABSENT: no change to `/etc/gitconfig` or the dispatcher comments: they already say so (R11)
Verification: the link target `#run--the-concluding-run` is the anchor GitHub generates for "## run — the concluding run"
SCOPE: in (1 changed files)

### T076: e2e test pinning T4's limit under env -i, both cases (cycle 6)
**Started:** 2026-10-01T19:19:41+00:00 | **Completed:** 2026-10-01T19:19:41+00:00

INHERITED: research R12 (both cases measured on the host), plan § Cycle 6's test design, SC-13's fixture and verdict shapes (confidence: high)
ASSUMED: "bounded" for the default case means what SC-13 asserts (non-zero within limit + the dispatcher's 5 s grace, the verdict naming the limit and its source, no commit, the hook stopped). "Unbounded" for the local case means the hook outlived limit + grace with no verdict, read from the hook's own last-beat second, not from git's message (H3) (confidence: high)
FLAGGED: the unbounded case is ended by the TEST's `timeout -k 1 10` (GNU timeout signals git's process group, so the hook goes with it), and teardown kills by the hook's self-written pid. Chose this over running the local case through `run` (003): `run` would also bound it, but then the test would depend on a second feature's mechanism to stay safe, and P005 asks for git through the image's real shells with nothing in between (confidence: high)
FLAGGED: the tests carry no SC number: they pin a ruling (discovery revision 8), not a criterion, so they are titled "T4 under env -i: …". The cycle report lists them under not_verified/process, not criteria_reestablished (confidence: high)
ASSUMED: `env -i git` resolves git through glibc's default search path (PATH is unset); the dispatcher's `git` and `timeout` resolve through dash's default path. Both held on the host; the image decides (confidence: medium)
ABSENT: no `bash -ic` cell. After `env -i` the style cannot matter, and the c/lc pair shows it does not
ABSENT: not run in the image here (no Docker; R10). Host evidence only, labelled so
Verification:
- shellcheck 0.11.0: clean
- fixture generated on the host from the file's own `sh -c` text: the hook reads `echo $$ > <abs>/hook.pid`, `date +%s > …/hook.start`, a 0.2 s heartbeat loop
- both cases run on the host through the test's own command lines, sandboxed (`setsid --wait timeout -k 5 60`), with `GIT_CONFIG_SYSTEM` standing in for the image's /etc/gitconfig: default rc 1 at 2.0 s with the verdict, no commit, hook stopped and not alive; local rc 124 from the watchdog, no verdict, no commit, last beat 10 s after git started (≥ 7 s required), hook not alive afterwards
SCOPE: in (1 changed files)

### T077: Makefile SHELLCHECK_FILES lists the new bats file (cycle 6)
**Started:** 2026-10-01T19:19:53+00:00 | **Completed:** 2026-10-01T19:19:53+00:00

INHERITED: T076's file (confidence: high)
ASSUMED: the list is where both lint lanes (`make lint` in the pinned shellcheck image, `make lint-host`) take their shell files from, as cycle 5's T070 assumed (confidence: high)
ABSENT: no other Makefile change; e2e discovery is by directory, so `make test` runs the new file without being told
Verification: `make lint-host` (venv shellcheck on PATH): ruff "All checks passed!", "46 files already formatted", shellcheck silent over the extended list; mypy reported "not available" for the system python3 (run from the venv in T078)
SCOPE: out — Makefile (1 of 1 changed files) (task has FLAGGED: no)

### T078: host lane, implement step 10, Cycle 6 report, deferred audit-log row (cycle 6)
**Started:** 2026-10-01T19:27:24+00:00 | **Completed:** 2026-10-01T19:27:24+00:00

INHERITED: T074–T077 and their verification; the send's cycle-report block (confidence: high)
ASSUMED: every criterion is `unconfirmed` until the Docker lane runs on this branch, as in cycles 5 and 003's cycle 1. This cycle changed no behaviour, so the criteria are re-established only by the lane re-running 001's e2e files (confidence: high)
FLAGGED: `full` reconcile mode is available (criteria identical to the rev-7 send's, revision 8 no prompt change) but deferred. 8 and 9 are not appended until the lane passes (bookkeeping convention), so audit-log gets a `none (deferred)` row now and a `full` row with the lane addendum (confidence: high)
FLAGGED: the first `make test-host` failed one 002 bench unit (setup hung under load). Chose to record it as a flake and not fix 002's runner in a 001 cycle: it passed 21/21 three times in isolation, and the full lane passed on the second run. Noted for 002 slice 1's driver hardening (confidence: medium)
ABSENT: coverage not re-measured (no Python changed); no Docker lane (R10); no ship or merge (they wait for the mentor's sign-off)
ABSENT: no demo_points_reached (the mentor derives them); no Group A fields (no marker on this path)
Verification:
- ruff 0.16.7 clean; mypy 2.3.1 "no issues found in 15 source files"; shellcheck 0.11.0 clean over 28 files
- `make test-host`: second run passed (676 units, 60/60, 29/29)
- implement step 10 run from the installed 2.22.0 blocks with `CLAUDE_PLUGIN_ROOT` set: Quality Score unknown, all six components excluded with reasons, gate warned
- all 13 citations in § Cycle 6 match exactly one line of the send (grep -cF = 1)
SCOPE: out — .specswarm/metrics.json (1 of 1 changed files) (task has FLAGGED: yes)

### T079: spec rule 9 — revision 10's clarification appended in place, declared (cycle 7)
**Started:** 2026-10-03T00:45:27+00:00 | **Completed:** 2026-10-03T00:45:40+00:00

INHERITED: impact-analysis § Cycle 7 — spec line 181 is the body's only statement about exit 4's envelope, still true; 001's contract agrees with revision 10 clause by clause (T018, `b7a6ea6`) (confidence: high)
ASSUMED: the annotation copies the prompt's sentence verbatim and closes with a provenance note, in the shape cycle 6 used for rule 5 (T074) (confidence: high)
FLAGGED: none
ABSENT: no other spec line changed: FR-9 and SC-5 name the exit-code vocabulary, not the envelope; the confirm envelope's removed `grant` field was never in the spec, so nothing to strike
ABSENT: no contract, code or test change — the contract already says the same; the two observations in impact-analysis § Cycle 7 (rule 8 stated only in output-contract.md; nothing forbids `mutating` with `grant_envelope`) are noted for the mentor, not built
Verification: the annotation's sentence equals the send's (`bridge/sends/01-rev10-20261003-003933.md`, rule 9) after whitespace normalisation (VERBATIM)
SCOPE: none — no files outside the feature's artifacts changed

### T080: provenance — audited_against += 10 (full), audit-log row (cycle 7)
**Started:** 2026-10-03T00:45:49+00:00 | **Completed:** 2026-10-03T00:46:08+00:00

INHERITED: T079's annotation; the criteria diff (identical to rev 9's, 13 criteria) (confidence: high)
ASSUMED: computed with the installed `audit-append` block (2.26.1, byte-identical to 2.27.0's), inputs PROMPT_REV=2, AUDITED=[2..9], N=10, MODE=full, OUT_OF_SCOPE and UNVERIFIED empty, REMOVALS_VISIBLE=yes; it returned MODE_USED=full, APPENDED=10, NEW_AUDITED=[2, 3, 4, 5, 6, 7, 8, 9, 10], no note (confidence: high)
FLAGGED: 10 is appended in this cycle rather than deferred to a lane addendum, against this instance's usual convention (append only after the Docker lane re-establishes) — chose to append now because the send instructs it for a `.specswarm/`-only cycle and names the lane to cite (`f73ac79`); the tree outside `.specswarm/` is unchanged from master (confidence: high)
ABSENT: `prompt_revision`, `discovery_revision`, `source_prompt` and `source_send` untouched; no spec body change in this task
Verification: `git diff` touches only spec.md's `audited_against` line and one appended audit-log row
SCOPE: none — no files outside the feature's artifacts changed

### T081: implement step 10, Cycle 7 report, metrics entry (cycle 7)
**Started:** 2026-10-03T00:46:28+00:00 | **Completed:** 2026-10-03T00:48:18+00:00

INHERITED: T079 and T080; the send's cycle-report block; the f73ac79 lane as the send states it (confidence: high)
ASSUMED: the 11 automated criteria are `executed` by citation of the f73ac79 lane, as the send directs, because nothing outside `.specswarm/` changed (verified: `git diff master HEAD -- . ':!.specswarm'` empty) (confidence: high)
FLAGGED: carried on under the session's 2.26.1 rather than stopping for a 2.27.0 session — chose to proceed because `diff -rq` shows only ship.md and plugin.json differ, so every command this cycle ran is 2.27.0's code; recorded as process failure 1 so the mentor can disagree (confidence: high)
FLAGGED: step-10 unit-test and coverage reasons re-run in the plugin's "on this machine" wording after the first run left them unattributed — same fact, same unknown score; both runs disclosed (confidence: high)
ABSENT: no host lane, lint or coverage (nothing outside `.specswarm/` changed); no Docker lane (send § 2); no demo_points_reached; no Group A fields (no marker on this path); no ship or merge (they wait for sign-off, and ship for a 2.27.0 session)
ABSENT: the two contract observations (rule 8 unchecked for grant clients; `mutating` with `grant_envelope` not forbidden) are reported, not built
Verification: all 13 citations in § Cycle 7 match exactly one line of the send (`grep -cF` = 1); no local path in the added text; deny-list pass before commit
SCOPE: in (1 changed files)

## Cycle 8 — send `bridge/sends/01-rev13-20261008-095251.md` (specswarm 4.0.1-botbaubble.2.37.0)

### T082: spec rule 10 — revision 11's struck clause corrected in place, declared
**Started:** 2026-10-08T10:06:09Z | **Completed:** 2026-10-08T10:06:09Z | **Coordinator**

INHERITED: (none — first task of the cycle); the classification in impact-analysis.md § Cycle 8 (diff of the rev-10 and rev-13 sends) — (confidence: high)
FLAGGED: corrected in place rather than stopping for regeneration — the command's row 7 says to stop on an amended, false body line; chose the send's instruction ("one copied constraint line, not a criterion and not the body's design: correct it in place … do not regenerate"), which is how revision 7's struck hooks clause was handled in cycle 5 — (confidence: high)
ASSUMED: the revision's words are copied as the prompt has them, with the strike kept visible as ~~…~~ and the revision note verbatim; the closing note on what 001 builds is this cycle's, marked as such — (confidence: high)
ABSENT: no other body line changes (the scratch-space lines 97, 201, 287, 330 stay true); no contract change (the contract's missing state root is reported for 07 s1)
SCOPE: none — no files outside the feature's artifacts changed

### T083: spec rules 9 and 13 — revisions 13 and 12 appended in place, declared
**Started:** 2026-10-08T10:06:28Z | **Completed:** 2026-10-08T10:06:28Z | **Coordinator**

INHERITED: T082 (same file); revision 10's annotation pattern on rule 9 (T079) — (confidence: high)
ASSUMED: each clarification is copied verbatim from the send's prompt bytes, then a provenance note naming where the contract already carries it (re-read at output-contract.md:20, :81–83, :131–140, conformance.md:27) — (confidence: high)
ABSENT: neither rule's existing text is changed (both stay true); no contract change
SCOPE: none — no files outside the feature's artifacts changed

### T084: provenance — audited_against gains 11, 12, 13 (full); three audit-log rows
**Started:** 2026-10-08T10:06:53Z | **Completed:** 2026-10-08T10:06:53Z | **Coordinator**

INHERITED: T082, T083; the criteria comparison (byte-identical to rev 10's) from impact-analysis.md § Cycle 8 — (confidence: high)
ASSUMED: one row per revision, as the send asks, each repeating the shared basis so a row read alone stands — (confidence: high)
ABSENT: prompt_revision (2), discovery_revision (3) and source_prompt untouched; no earlier row rewritten
SCOPE: none — no files outside the feature's artifacts changed
