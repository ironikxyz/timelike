# Implementation Plan: 002 speedup bench (slice 0)

**Branch:** `002-speedup-bench` | **Spec:** [spec.md](spec.md) | **Send:**
`bridge/sends/02-rev1-20260929-000641.md` | **Date:** 2026-09-29

## Summary

Slice 0 builds:
- a bench driver that runs in its own container
- a vanilla image
- a four-task git catalog, driven by a deterministic fake agent
- a versioned per-run trace
- a report built from traces alone
- a Docker-lane test that checks the artifacts, not the exit message

One command runs it all: `make bench`, which calls `bench/run.sh`, which runs `timelike-bench run`
inside the driver.

**Central findings** (research RB3 and RB4):
- On the invocation path the bench uses (`docker exec`, no TTY, no TERM), vanilla git's editor and
  pager traps **fail fast rather than hang**. The only guaranteed vanilla hang is a repository hook
  that doesn't return.
- The catalog includes a task where timelike **loses**: its hooks-off default commits content the
  repository's own hook would reject.

Neither finding is a value claim. The fake agent's policy was written by timelike's own builders
(RB11), and every report says so on its first line.

## Technical Context

| Item | Value |
|---|---|
| **Languages** | Python (stdlib only) for the driver, library and tool; Bash for `bench/run.sh` and the Dockerfiles |
| **Driver interpreter** | uv-managed CPython `PYTHON_VERSION` (3.14.7) at `/opt/timelike/python`, **inside the driver image** (RB6). The tool shebang is `#!/opt/timelike/python/bin/python3 -I`. Nothing is installed on the host |
| **Images** | `timelike-agent:local` (001, unchanged); `timelike-vanilla:local` (new, RB1); `timelike-bench-driver:local` (new, RB6). All three are built from `DEBIAN_IMAGE` and stamped with `GIT_SHA` |
| **Build tooling** | Docker (`docker build`, with build args from `pins.env`) and uv. No new compose service |
| **Invocation path** | `docker exec -u agent -w /home/agent/task <id> sh -c <wrapper> <limit> <cmd>`, with an in-container `timeout` and a process-group kill (RB2, RB5) |
| **Storage** | Files only: `bench/out/<run-id>/traces/*.json` and `report.txt` (RB7) |
| **Testing** | pytest units on the host lane (trace, report, policy, keys, and the executor wrapper run locally); bats e2e in the Docker lane (`tests/e2e/speedup-bench.bats`); `timelike-conform` over `timelike-bench` |
| **Lint** | ruff, `mypy --strict` (`pyproject.toml` `files` extended), shellcheck |
| **Supply chain** | `scan/scan.sh` extended to three images (RB10) |
| **Time limits** | Per call: 30 s (above 001's 20 s git bound); **120 s from 001's cycle 5** (Claude Code's default call timeout, which 001's 60 s hook limit is sized for). Per run: 300 s. Driver backstop: limit + 10 s. All are overridable per run |
| **Scale / scope** | 4 tasks, 2 environments, 8 runs per bench, 2 automated criteria and 1 manual |

No `NEEDS CLARIFICATION` remains. research.md RB1–RB11 resolve every unknown.

## Constitution Check

*Gate: must pass before Phase 0; re-checked after Phase 1 design.*

| Principle | How this plan complies | Status |
|---|---|---|
| P1 Unaided completion | Every run ends `completed`, `escalated`, `failed` or `hung`, with a reason. This keeps P1's test answerable | ✅ |
| P2 Every call concludes | Per-call and per-run limits inside the container, a process-group kill, and a driver backstop (RB5). A hang is a result, not a crash | ✅ |
| P3 Found where agents look | The told/not-told arm is slice 1. The trace keeps room for it (FR-14) | n/a (slice 0) |
| P4 Reach only by grant | No key in either image under test, in CI, or in the repository. A fake-agent run refuses to start if a key-shaped variable is present (RB9). The socket is held only by the driver | ✅ |
| P5 Wrong turns are recoverable | Each run gets a fresh container, removed afterwards. Incident replays are slice 2 | n/a |
| P6 Claims are measured | Vanilla and timelike are compared under an identical path, task and policy. The fake-agent statement is the first line of every report. Losing tasks come first. Tokens go only in an appendix. The maintainer line and reproduce command are always present | ✅ |
| P7 Harness-agnostic | The harness sits outside the environment and reaches it only through `bash -c`. Harness identity is a trace field | ✅ |
| H1 Two components, one boundary | The driver is a third container, and the only one holding the socket. The agent and vanilla images never do | ✅ |
| H2 One output contract | `timelike-bench` is built on `agentio` and checked by `timelike-conform` | ✅ |
| H3 Verify artifacts, not messages | The e2e validator is separate from the trace writer, and parses traces and the report. The completion check reads git state, not the policy's opinion | ✅ |
| H4 Non-interactive by construction | No `-t`, no `-i`, TERM asserted empty, and stdin at EOF | ✅ |
| H5 Stdlib-first, pinned interpreter | Stdlib only; the pinned uv CPython, run with `-I` | ✅ |
| H6 No hidden machinery | No MCP and no LLM in slice 0 | ✅ |
| H7 Every criterion is a test | SC-1 and SC-2 each map to a bats test named after the criterion's distinguishing text. SC-3 is Manual | ✅ |
| H8 Stamped and typed | Three images are stamped and checked against `GIT_SHA`. An empty stamp fails the run (FR-8). `mypy --strict` | ✅ |
| H9 Sound supply chain | Both new images go through the scan gate (FR-16). The Docker CLI's Go stdlib is a named risk (RB10) | ✅ (risk named) |

**Gate result: PASS.** No violations.

**Post-design re-check: PASS.** The fake agent's limits (RB11) are disclosed, not claimed away.

## Project Structure

### Documentation (this feature)

```
.specswarm/features/002-speedup-bench/
├── spec.md  plan.md  research.md  data-model.md  quickstart.md
├── contracts/
│   ├── trace-schema.md        trace v1: fields, stamps, endings, FR-14 extension rules
│   └── bench-cli.md           timelike-bench run / report; bench/run.sh; report layout
├── checklists/requirements.md
├── tasks.md  decisions.md  cycle-report.md   (later phases)
```

### Source code (repository root)

```
bench/
├── run.sh                 host wrapper: realpath, socket gid, explicit -e list, docker run of the driver
├── driver/Dockerfile      DEBIAN_IMAGE + uv CPython + docker CLI + agentio + benchlib + tools (RB6)
├── vanilla/Dockerfile     DEBIAN_IMAGE + git (no recommends) + agent uid 1000 + label (RB1)
├── bin/timelike-bench     contract-bound CLI (agentio): run, report
└── benchlib/
    ├── __init__.py
    ├── trace.py           Trace/ToolCall/Identity dataclasses, to/from JSON, validate (FR-6..8, FR-14)
    ├── catalog.py         Task definitions (setup, policy, check), NOT_BENCHABLE list (RB4)
    ├── fakeagent.py       pure policy interpreter: next_step(policy, step, observation) (FR-11)
    ├── executor.py        the wrapper string; Executor protocol; LocalExecutor and DockerExecutor (RB5)
    ├── docker.py          image identity, stale check, container lifecycle, env inspection (RB8)
    ├── keys.py            key-shaped name matcher, a port of shell-env F002 (RB9)
    ├── runner.py          one run: setup → policy loop → check → Trace; the bench over the catalog
    └── report.py          traces → report text; ordering; appendix (FR-9, FR-10)
tests/unit/test_bench_*.py host-lane units (trace, report, fakeagent, keys, executor, catalog, cli)
tests/e2e/speedup-bench.bats     SC-1, SC-2 and failure-can-fail tests (Docker lane)
tests/e2e/fixtures/validate_bench.py   independent trace/report validator (H3, P005)
```

**Changed files:**
- `Makefile`: `bench` and `bench-images` targets; `SHELLCHECK_FILES`
- `tests/run.sh`: vanilla and driver build steps before e2e
- `scan/scan.sh`: loop over three images
- `pyproject.toml`: mypy `files`
- `.gitignore`: `bench/out/`

## Phase 0: Research

Done: research.md RB1–RB11.

## Phase 1: Design

- [data-model.md](data-model.md): Task, Policy, Step, Observation, ToolCall, Trace, Identity, Ending,
  Report, and the win/lose/tie rule.
- [contracts/trace-schema.md](contracts/trace-schema.md): trace v1.
- [contracts/bench-cli.md](contracts/bench-cli.md): the CLI, the wrapper, and the report layout.
- [quickstart.md](quickstart.md): how the operator runs the bench and reads the report (D2).

The agent context update is skipped: there is no `.claude/context.md` or equivalent in `code/`.

## Phase 2: Task approach (for /specswarm:tasks)

Build order:
1. `benchlib` pure modules first: `trace`, `keys`, `fakeagent`, `catalog`, `report`, each with its
   host units. These need no Docker, and give the coverage base.
2. Then `executor` (LocalExecutor units exercise the real wrapper: hangs, a detached child, byte
   counts), then `docker` and `runner`.
3. Then the CLI on `agentio`, with conformance.
4. Then the images and `bench/run.sh`, the Makefile, `tests/run.sh` and `scan.sh`.
5. Then the e2e bats and the validator.

Delegation: the pure modules and their units split cleanly by file, so they can go to subagents with
disjoint ownership. The coordinator writes `runner`, the CLI, the images and the lane wiring, and
reviews and commits everything, one task per commit.

## Verification lanes (001 R10)

- **Host lane** (this workspace): ruff, mypy, shellcheck, the pytest units, coverage (≥ 90%, with
  `bench/` added to the coverage rc), and `timelike-conform` over `bench/bin`.
- **Docker lane** (the operator, on the host): `make test` builds all three images and runs
  `speedup-bench.bats`. `make scan` scans three images. `make bench` produces the D2 report.
- SC-1 and SC-2 are **not** claimed from host-lane evidence.

## Complexity Tracking

None. A third image is the smallest arrangement that keeps the socket out of both environments under
test (H1).

## Tech Stack Compliance Report

<!-- Auto-generated by SpecSwarm tech stack validation -->

### ✅ Approved Technologies (already in stack)

Python, Bash, Docker, Debian, uv, git, pytest, bats-core, ruff, mypy, shellcheck, Syft, Grype, gitleaks,
pip-audit. Each was checked with `lib/tech-stack-parser.sh`.

### ➕ New Technologies (auto-added)

None. `tech-stack.md` is unchanged, and its version was not bumped.

### ⚠️ Conflicting Technologies (require approval)

None.

### ❌ Prohibited Technologies (cannot use)

None.

---

# Cycle 2 plan: revision 8 recorded

**Branch:** `modify/002-rev8` | **Send:** `bridge/sends/02-rev8-20261008-095251.md` (prompt revision 8,
discovery revision 13) | **Date:** 2026-10-08 | **specswarm:** 4.0.1-botbaubble.2.37.0 loaded by the session

## Summary

A record-only cycle (`modify.md` § Cycle 2): revision 8's constraint is copied into the spec, declared, with a
note that slice 0's code does not meet it and that plan's ruling (b) carries the change to 02 slice 1. T016's
assumption is annotated as superseded. Nothing outside `.specswarm/features/002-speedup-bench/` changes.

## Technical Context

| Item | Value |
|---|---|
| **Languages** | Markdown (spec and records) |
| **Testing** | None new. The two Automated criteria are cited from the mentor's lane readme-c at `10ddd3a`, whose tree (`725b7a1f…`) equals `master`'s at `c79facc`, from which this branch differs only in `.specswarm/features/002-speedup-bench/` |
| **Unknowns** | None |

## Constitution Check

- **P6 (claims are measured):** the constraint is P6's; slice 0's reports remain labelled fake-agent runs
  (FR-9), which is why plan let the code change wait. No report is re-rendered here.
- **H3 (verify artifacts, not messages):** the four unmet places were read in the files (`report.py:119`,
  `:227`; `data-model.md:125`; `decisions.md` T016), not taken from the send.
- **Provenance:** `prompt_revision` (1), `discovery_revision` (6) and `source_prompt` are untouched; only
  `audited_against` gains 8.

Gates: pass.

## Phase 0: Research

None needed.

## Phase 1: Design

- **data-model.md, contracts/, quickstart.md:** no change. `data-model.md:125` states the old order and is
  left as it is by the send's instruction; it is named in the spec's note and in `not_verified`.

## Tech Stack Compliance Report (Cycle 2)
<!-- Auto-generated by SpecSwarm tech stack validation -->

### ✅ Approved Technologies (already in stack)
None named: the cycle changes Markdown only.

### ➕ New Technologies (auto-added)
None. `tech-stack.md` is unchanged.

### ⚠️ Conflicting Technologies (require approval)
None.

### ❌ Prohibited Technologies (cannot use)
None.
