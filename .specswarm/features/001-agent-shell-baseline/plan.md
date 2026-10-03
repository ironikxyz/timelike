# Implementation Plan: 001 agent shell baseline & output contract (slice 0)

**Branch:** `001-agent-shell-baseline` | **Spec:** [spec.md](spec.md) | **Send:**
`bridge/sends/01-rev2-20260928-063549.md` | **Date:** 2026-09-28

## Summary

This feature builds four things:
1. **The agent image.** Debian trixie-slim, pinned. Non-interactive defaults carried in the process
   environment and `/etc/gitconfig`. An unprivileged `agent` user with no route to root.
2. **`agentio`.** The shared Python module that implements output-contract rules 1–16.
3. **Two contract-bound tools:** `timelike` (environment info, carrying the build revision) and
   `timelike-conform` (the conformance check).
4. **The test and gate harness.** bats-core end-to-end tests driven from **outside** the image; pytest
   units; the project-owned supply-chain scan gate carried by the send.

The central technical finding (research R1) is that Debian's `/etc/profile` resets PATH. So every
default except PATH lives in `ENV`, and PATH lives in both `ENV` and `/etc/profile.d`. Each invocation
style is tested separately, with and without a TTY.

## Technical Context

| Item | Value |
|---|---|
| **Languages** | Bash 5.x (environment layer, tests); Python 3.12 (`agentio`, tools), stdlib only |
| **Base image** | Debian trixie-slim, pinned by digest (R9) |
| **Interpreter** | uv-managed CPython 3.12.14 at `/opt/timelike/python` (R6). Tools run `#!/opt/timelike/python/bin/python3 -I` |
| **Build tooling** | uv (pinned), Docker, Docker Compose v2 |
| **Testing** | bats-core end to end, driven from a runner image that uses the Docker CLI (R8); pytest for units; shellcheck, ruff, `mypy --strict` |
| **Supply-chain gate** | Syft + Grype (image), pip-audit (Python), gitleaks (repository); all pinned (H9) |
| **Storage** | Files only: per-session scratch and `events.jsonl` (data-model.md) |
| **Target platform** | linux/amd64 container. Nothing installed on the host |
| **Performance goals** | Tool start-up < 100 ms p95 (quality-standards). Each git criterion under 20 s (SC-1) |
| **Constraints** | No sudo, no setuid, no capabilities, no daemons, no network needed at runtime for slice 0 |
| **Scale / scope** | 2 tools, 1 module, 6 automated criteria and 1 manual |

No `NEEDS CLARIFICATION` remains. research.md R1–R10 resolved every unknown.

## Constitution Check

*Gate: must pass before Phase 0; re-checked after Phase 1 design.*

| Principle | How this plan complies | Status |
|---|---|---|
| P1 Unaided completion | Nothing waits on a person. A credential need fails fast with a message. R10's missing daemon is escalated, not worked around | ✅ |
| P2 Every call concludes | Editor, pager and prompt neutralised (R2). Every tool concludes with a verdict and a vocabulary exit code. The conformance check limits each probe to 10 s | ✅ |
| P3 Found where agents look | One contract across all tools. `timelike` lists the tools on PATH. Announcement files are feature 02+ | ✅ (slice 0) |
| P4 Reach only by grant | No sudo or setuid, `cap_drop: ALL`, `no-new-privileges`. Adele's data is unreadable (R7) | ✅ |
| P5 Wrong turns are recoverable | Not engaged: slice 0 tools do not mutate | n/a |
| P6 Claims are measured | No value claims | n/a |
| P7 Harness-agnostic | Defaults in the process environment and system git config, not harness hooks. Tested per invocation style (R1) | ✅ |
| H1 Two components, one boundary | Agent side only. Adele is represented by a uid and an unreadable directory | ✅ |
| H2 One output contract | `agentio` built **before** the tools. The conformance check ships in the same feature | ✅ |
| H3 Verify artifacts, not messages | Tests read `/proc/self/status`, file modes and exit codes, never success strings. The negative fixture proves the check can fail | ✅ |
| H4 Non-interactive by construction | R1–R5. Every style is tested with and without a TTY (R8) | ✅ |
| H5 Stdlib-first, pinned interpreter | No third-party runtime dependency. Pinned uv interpreter, `-I` | ✅ |
| H6 No hidden machinery | No MCP, LLM or daemon | ✅ |
| H7 Every criterion is a test | SC-1 to SC-6 each map to a bats file named after the criterion's distinguishing text. SC-7 is Manual | ✅ |
| H8 Stamped and typed | `GIT_SHA` build argument. The build fails on an empty value. Label plus `--agent-info`. `mypy --strict`, ruff, shellcheck | ✅ |
| H9 Sound supply chain | Project-owned scan gate built in this feature (the send's carried item) | ✅ |

**Gate result: PASS.** No violations, and no complexity tracking needed.

**Post-design re-check:** PASS. The contracts in `contracts/` add no principle exposure.
`timelike-conform`'s 10 s per-probe limit keeps P2 true for the checker itself.

## Project Structure

### Documentation (this feature)

```
.specswarm/features/001-agent-shell-baseline/
├── spec.md, plan.md, research.md, data-model.md, quickstart.md
├── contracts/  output-contract.md · conformance.md · event / agent-info / error / confirm-envelope schemas
├── checklists/requirements.md
└── cycle-report.md          ← appended when the cycle completes
```

### Source code (repository root)

```
image/
├── Dockerfile                    # agent image: FROM debian@sha256…, uv, CPython, users, setuid strip, ENV
├── rootfs/etc/gitconfig          # fallback git defaults (R2–R4)
├── rootfs/etc/profile.d/00-timelike-path.sh   # PATH for login shells (R1)
└── rootfs/var/lib/adele/fixture.secret        # Adele-owned placeholder (0600, adele:adele)
compose.yaml                      # agent service: cap_drop ALL, no-new-privileges, GIT_SHA build arg
tools/
├── agentio/agentio.py            # contract rules 1–16 (installed into the interpreter's site-packages)
└── bin/
    ├── timelike                  # env info; --agent-info carries the revision
    └── timelike-conform          # conformance check (contracts/conformance.md)
tests/
├── unit/                         # pytest: agentio rules, conform checks against fixture tools
├── e2e/                          # bats, one file per criterion, driven from outside via docker exec
│   ├── helpers.bash              # run_in(style, tty, cmd) → bash -c | bash -lc | bash -ic, with/without -t
│   ├── git-log-diff-commit-rebase-exit-within-20-seconds.bats            # SC-1
│   ├── bash-c-and-bash-lc-defaults-in-effect.bats                        # SC-2
│   ├── credentials-fail-fast-and-hooks-off.bats                          # SC-3
│   ├── agent-cannot-run-as-root-change-firewall-or-read-adele.bats       # SC-4
│   ├── conformance-check-over-every-timelike-tool-on-path.bats           # SC-5
│   └── peer-agents-write-to-own-scratch-space.bats                       # SC-6
├── fixtures/bad-tool/timelike-bad   # deliberately non-conforming; never on the shipped PATH
├── host/                         # advisory host lane (R10): env-layer check via env -i + GIT_CONFIG_SYSTEM
├── runner/Dockerfile             # FROM bats/bats@sha… + docker CLI (R8)
└── run.sh                        # builds with --build-arg GIT_SHA, starts compose, runs e2e + unit (Docker lane)
scan/
└── scan.sh                       # supply-chain gate: syft→grype, pip-audit, gitleaks (pinned images); exemptions table
Makefile                          # build · test · test-host · lint · scan · demo
```

**Structure decision:** a single repository with two tool languages. Only the agent side exists in
this feature. `adele/` arrives in feature 12, and nothing here reaches into its future location.

## Phase 0: Research

Done. See `research.md` R1–R10. Two research agents verified shell and git behaviour by experiment,
and pins and privilege from primary sources.

## Phase 1: Design

Done:
- `data-model.md`
- `contracts/output-contract.md`, `contracts/conformance.md`, and four JSON schemas
- `quickstart.md`

**Agent context update:** skipped. This repository has no `.claude/` context file. `CLAUDE.md` is the
instance's own instructions and is not generated.

## Phase 2: Task approach (for /specswarm:tasks)

The order follows constitution H2: **the contract before any tool**.
1. **Setup:** repository skeleton, Makefile, pins, the runner image, lint configuration.
2. **Foundation:** `agentio` with pytest (rules 1–16). This blocks every tool.
3. **Image:** Dockerfile, rootfs files, users, setuid strip, `ENV`, build stamp, compose hardening.
4. **Tools:** `timelike`, then `timelike-conform`, then the bad fixture.
5. **Criteria:** one bats file per SC (SC-1 to SC-6), each in both TTY modes and every invocation
   style.
6. **Host lane:** the environment-layer check (R10).
7. **Gate:** `scan/scan.sh` and exemptions (H9).
8. **Polish:** lint clean, the demo script for SC-7, and the cycle report.

Tests are written next to each implementation step, never after all of them. The negative
conformance fixture comes before the check is declared working.

## Verification lanes (R10)

| Lane | Needs | Authoritative for | Runs here? |
|---|---|---|---|
| Docker (`make test`) | a Docker daemon (host socket, remote `DOCKER_HOST`, or CI) | SC-1 to SC-6, H8 stamp, H9 scan | **No.** No daemon in this dev container |
| Host (`make test-host`) | Python 3.12 (present) | `agentio` and `timelike-conform` units; the environment-layer **files** | Yes, advisory |

A criterion is reported `executed` in the cycle report **only** if the Docker lane ran it. Host-lane
evidence is reported as evidence about files, never as a criterion pass.

## Complexity Tracking

No constitution violations. One quality-standards exemption, added during implement:

| Item | Standard | Justification |
|---|---|---|
| `scan/evaluate.py`, 650 lines (cycle 2; 525 in cycle 1) | `max_file_lines: 300` ("single-file tools may exceed this with a justification in the feature plan") | It runs under `python3 -I`, which drops the script's directory from `sys.path`, so splitting it into modules would need a `sys.path` workaround. It holds three parsers (Grype, pip-audit, gitleaks), the baseline parser and validator, the H9 rule of discovery revision 5 (baseline per base digest, 90-day cap, never hiding a new or newly fixable finding), origins from the SBOM, the proposed baseline, and the escalation text. Each piece is small and unit-tested (76 tests in `tests/unit/test_scan_*.py`, 99% line+branch) |

## Tech Stack Compliance Report
<!-- Auto-generated by SpecSwarm tech stack validation -->

Checked with `lib/tech-stack-parser.sh` (specswarm 2.11.0) against `tech-stack.md` 1.2.0. No
unparsed prohibitions.

### ✅ Approved Technologies (already in stack)
Debian, Docker, Docker Compose, Bash, Python, uv, git, pytest, bats-core, ruff, mypy, shellcheck, Syft,
Grype, gitleaks, pip-audit

### ➕ New Technologies (auto-added)
None. The Docker CLI in the test runner is part of Docker. `setsid` and `setpriv` are part of the
Debian base image. `tech-stack.md` version unchanged (1.2.0).

### ⚠️ Conflicting Technologies (require approval)
None.

### ❌ Prohibited Technologies (cannot use)
None used.

---

# Cycle 6 plan: rule 5's scope recorded; T4's `env -i` limit stated and pinned

**Branch:** `modify/001-rev9-scope-and-t4` | **Send:** `bridge/sends/01-rev9-20261001-191224.md` (prompt
revision 9, discovery revision 9) | **Date:** 2026-10-01 | **specswarm:** 2.22.0

## Summary

Three items, no criterion change and no behaviour change (`modify.md` § Cycle 6):
1. Spec contract rule 5: revision 9's clarification, appended in place, declared.
2. README: T4's limit under `env -i`, pointing at `run`.
3. A watchdog-bounded e2e test pinning both `env -i` cases (research R12).

## Technical Context

| Item | Value |
|---|---|
| **Languages** | Bash (the e2e test); Markdown (spec, README) |
| **Testing** | bats-core in the image, through `run_in` (the image's real `bash -c` / `bash -lc`, `notty`); shellcheck |
| **Mechanism under test** | git 2.47.3 in the image; `/etc/gitconfig` (system scope); the dispatcher (R11) |
| **Unknowns** | None. R12 measured both cases on the host |

## Constitution Check

- **H2 (output contract):** unchanged. The spec now quotes rule 5's scope as the contract states it.
- **H3 (verify artifacts, not messages):** the test decides from artefacts. The unbounded case is
  decided by the hook's own self-written timestamps, not by git's message.
- **T4:** the README states the limit honestly, and the test keeps it from widening silently.
- **Process safety (cycle 5):** the unbounded case is bounded by the test, and processes are found
  only through files they wrote.

Gates: pass.

## Phase 0: Research

R12 (in `research.md`).

## Phase 1: Design

- **data-model.md, contracts/:** no change. The contract was amended by 003 at `58b7d11`.
- **quickstart.md:** no change. The new test runs in `make test` like every e2e file.
- **The test's design** (`tests/e2e/hooks-under-env-i-default-bounded-local-unbounded.bats`):
  - **fixture:** one repository per case, with `timelike.hookTimeout 2`, a user identity in local
    config (`env -i` drops `HOME`), and a staged file. The `pre-commit` hook writes its pid once and
    an epoch second every 0.2 s, forever.
  - **default case:** `.git/hooks/pre-commit`. `env -i git commit` inside `run_in` exits non-zero
    within 2 + 5 s; stderr has the verdict naming the 2 s limit from `git config
    timelike.hookTimeout`; no commit; the hook stopped beating.
  - **local case:** `core.hooksPath .hooks`. `timeout -k 1 9 env -i git commit` exits 124 from the
    **test's** watchdog; stderr has no `error: git hook` line; the hook's last beat is at least
    2 + 5 s after git started, so it outlived the limit plus the dispatcher's grace.
  - **cells:** `bash -c` and `bash -lc`, in `notty`. After `env -i` the style cannot matter, and two
    styles show it does not.
  - **teardown:** kill by the hook's pid file.

## Tech Stack Compliance Report

### ✅ Approved Technologies (already in stack)
bats-core, git, Bash.

### ➕ New Technologies (auto-added)
None. GNU coreutils `timeout` and `env` are in the Debian base image (the dispatcher already relies on
`timeout`). The parser reads "GNU coreutils" as unlisted, as it read `ctypes` for 003: base-image
utilities are not listed one by one. `tech-stack.md` is unchanged.

### ⚠️ Conflicting Technologies (require approval)
None.

### ❌ Prohibited Technologies (cannot use)
None used.
