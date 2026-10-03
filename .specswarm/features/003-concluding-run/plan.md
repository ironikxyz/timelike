# Implementation Plan: 003 Concluding run (slice 0)

**Branch:** `003-concluding-run` (from `master` at `702ba59`) · **Spec:** `spec.md` · **Send:**
`../bridge/sends/03-rev1-20261001-043339.md` (prompt revision 1, discovery revision 9) · **specswarm:**
2.21.0 (the send asked for ≥ 2.20.0)

## Summary

`run` is a new single-file tool, `tools/bin/run`, built on `agentio`. It runs a command with its output
going to a log file, not a pipe, so a backgrounded child holding stdout cannot block it. It waits on the
process. On timeout it freezes and kills the whole process tree, which it tracks by parent link as a
child subreaper. It prints the contract's header, then a verdict, then head / first errors / tail and a
`sed -n` command that reads the rest of the log. It exits with the command's own code (discovery
revision 9).

The cycle also carries 001's contract amendment: the contract text, the manifest and event schemas,
`agentio`, and conformance C6 (spec FR-20 to FR-24). Without the amendment, `run` cannot be conformant.

## Technical Context

| Item | Value |
|---|---|
| Language | Python 3.14.x (image, `/opt/timelike/python`, `-I`); host lane 3.12 |
| Dependencies | stdlib only. Added stdlib modules: `ctypes` (prctl), `subprocess`, `collections.deque` |
| Process control | `PR_SET_CHILD_SUBREAPER`; `/proc/<pid>/stat`, `/proc/<pid>/fd`, `/proc/<pid>/fdinfo`; SIGTERM → SIGSTOP sweep → SIGKILL + SIGCONT (research R3, R4) |
| Storage | One log per call under `<scratch>/<session>/run/`. No garbage collection in slice 0 |
| Testing | pytest units (`tests/unit/test_run.py`, plus additions to `test_agentio.py` and `test_conform*.py`); bats e2e in the image, one file per criterion, each run under `bash -c` and `bash -lc` |
| Lint and types | ruff, ruff format, `mypy --strict`, shellcheck (bats) |
| Performance | Start-up < 100 ms p95 (quality-standards); `ctypes` adds about 3 ms (R3). The detached-child verdict comes within 2 s of the command's exit (SC-3) |
| Unknowns | none left (research R1–R14) |

## Constitution Check

| Principle | Check | Result |
|---|---|---|
| P1 Unaided completion | The timeout verdict names both ways to raise the limit, and the more command is exact | ✅ |
| P2 Every call concludes | This is the P2 feature: no pipe wait, a whole-tree stop, a verdict on every path, and a 100 s default below the harness's 120 s | ✅ |
| P3 Found where agents look | The name is `run`, with `timeout(1)`-style argv and `$?` pass-through. Announcement in harness files is another feature's (README / `timelike` lists the tool) | ✅ |
| P4 Reach only by grant | Nothing reaches beyond the environment. It signals only processes in its own tree, or holders of its own log (same uid) | ✅ |
| P5 Wrong turns are recoverable | Not touched | n/a |
| P6 Claims are measured | No value claim is made. 002's bench may later wrap calls in `run` (not here) | n/a |
| P7 Harness-agnostic | A shell command; no harness hook | ✅ |
| T4 | `run` is where P2 rests when an agent discards the environment (`env -i`). `run` itself needs only `/proc` and its own interpreter | ✅ |
| H1 Two components | Agent-side Python, inside the environment | ✅ |
| H2 One output contract | Built on `agentio`. The contract is amended **as plan ruled** (revision 9), not bypassed | ✅ |
| H3 Verify artifacts | The verdict's "no survivors" claim comes from a re-scan. Tests detect survivors by marker files | ✅ |
| H4 Non-interactive | stdin is `/dev/null`; no tty, no prompt | ✅ |
| H5 Stdlib, pinned interpreter | Stdlib only, `#!/opt/timelike/python/bin/python3 -I` | ✅ |
| H6 No hidden machinery | Nothing persists past the call: detached children are the command's, not `run`'s | ✅ |
| H7 Criterion = test | SC-1 to SC-5 and SC-7 are e2e and unit tests named after their text. SC-6 is Manual | ✅ |
| H8 Stamped and typed | `mypy --strict`, ruff, shellcheck | ✅ |
| H9 Supply chain | No new package. The image's tool set changes, so `make scan` re-runs | ✅ |

Post-design re-check: no violations, and no complexity tracking needed.

## Project Structure

### Documentation (this feature)
```
.specswarm/features/003-concluding-run/
  spec.md  plan.md  research.md  data-model.md  quickstart.md
  contracts/run-cli.md  contracts/output-contract-amendment.md
  checklists/requirements.md
  tasks.md  decisions.md  cycle-report.md        (tasks / implement)
```

### Source code
```
tools/agentio/agentio.py           passes_exit, cause/command_exit, argv split, tool-supplied cut
tools/bin/run                      NEW: the tool
tools/bin/timelike-conform         C6 pass-through exercise; C7 accepts the passed-through exit
.specswarm/features/001-agent-shell-baseline/contracts/
  output-contract.md  agent-info.schema.json  event.schema.json  conformance.md   (amendment)
tests/unit/test_run.py             NEW
tests/unit/test_agentio.py         + pass-through, split, tool-supplied cut
tests/unit/test_conform*.py        + C6 pass-through (a lying pass-through tool fails)
tests/e2e/run-*.bats               NEW, one per criterion (SC-1–SC-5, SC-7 shape, the name)
tests/e2e/<existing 001 tests>     tool counts and lists that now include run
README.md                          the run section (P3 announcement in the place agents read)
```

## Phase 0: Research
`research.md` R1–R14. Two host experiments: an output file plus a subreaper finding nested-group and
`setsid` descendants, and the cost of the `ctypes` import.

## Phase 1: Design
`data-model.md`, `contracts/run-cli.md`, `contracts/output-contract-amendment.md`, `quickstart.md`.

## Phase 2: Task approach (for /specswarm:tasks)

1. **Contract first** (001-side, FR-20 to FR-24): contract text, schemas, `agentio`, conformance, and
   their unit tests. Every later task depends on it.
2. **`run`'s core:** argv, the limit, the log, execution and exit mapping (SC-5).
3. **Concluding:** detached-child detection (SC-3) and the tree stop (SC-4).
4. **Display:** sections, error patterns and the more command (SC-1, SC-2).
5. **e2e in the image,** one bats file per criterion, plus updates to existing 001 tests that count tools.
6. **README and help** (P3), then lint, coverage and the host lane.
7. **Cycle report.** The Docker lane is then run by the mentor on the host.

Disjoint file ownership allows delegation: the contract and `agentio` (1) are one owner; `run` and its
units (2–4) are another; the e2e tests (5) are a third, written against `contracts/run-cli.md`.

## Verification lanes (001 R10)

- **Host (this workspace):**
  - `make test-host`
  - units with coverage of at least 90% (reboot's covrc, plus `/tmp/pytest-of-*/**/run`)
  - lint
  - process experiments under `setsid --wait` + `timeout`
- **Image (operator or mentor, on the host):** `make build test scan`. Never report an image criterion
  passed from host evidence.

## Complexity Tracking

None.

## Tech Stack Compliance Report
<!-- Auto-generated by SpecSwarm tech stack validation (lib/tech-stack-parser.sh, specswarm 2.21.0) -->

### ✅ Approved Technologies (already in stack)
Python, Bash, bats-core, pytest, mypy, ruff, shellcheck.

### ➕ New Technologies (auto-added)
None. `ctypes` was reported `unlisted` by the parser, but it is a module of Python's standard library.
tech-stack.md approves Python as "stdlib only" (§ line 189), so it is covered, and nothing was added to
tech-stack.md.

### ⚠️ Conflicting Technologies (require approval)
None.

### ❌ Prohibited Technologies (cannot use)
None.
