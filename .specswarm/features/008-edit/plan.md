# Implementation Plan: 008 Edit — `edit` (prompt 06, slice 0)

**Branch:** `008-edit` (cut from `007-announcements-discovery`; rebased onto `449cb29` after lane batch-a) ·
**Send:** `bridge/sends/06-rev1-20261004-183704.md` (prompt revision 1, discovery revision 12; dispatch 4 of 8),
built under revision 13's rulings (code-track § Resume after pause-06) · **Date:** 2026-10-05 ·
**specswarm:** 4.0.1-botbaubble.2.35.0 (`4ff8dcb`), the expanded command's cache path

## Summary

One new single-file agent tool on `agentio`: **`tools/bin/edit`** (spec FR-1 to FR-12).
- It replaces text that occurs exactly once. Matching runs at three levels: exact, then line endings,
  then indentation (R2).
- The new text takes the file's endings and indentation (R3).
- A failed match shows up to three nearest candidates (R4).
- The write is atomic and hash-checked (R5).
- A dry run prints the unified diff.

It is stdlib only, with no image change: `COPY tools/bin/` ships it, and `timelike` and the announcement
list it automatically.

**Rule 9 (revision 13), outside 008** (R1, spec FR-12):
- `agentio` gains `confirm_protocol`, and honours `--yes` only when it is true.
- 001's `agent-info.schema.json` gains `confirm_protocol` and `dry_run`.
- `timelike-conform` C2 gains the confirmation-scope checks, each shown failing.
- 001's output contract gains the clarifying sentence.
- `undo` declares `confirm_protocol=True`.

## Technical Context

| Item | Value |
|---|---|
| **Language** | Python 3.12+ (3.14.x in the image), stdlib only: `difflib`, `hashlib`, `tempfile`, `os`, `re`, `math`, `shlex`, `stat`, `time` |
| **Contract module** | `tools/agentio` (`Tool`, `Result`, `Cut`, `run`): `Tool.confirm_protocol` is new |
| **Testing** | pytest units (`tests/unit/test_edit.py`, new; `test_agentio.py` and the conform tests, extended); bats-core e2e in the image (`bash -c`, `bash -lc`), one file per criterion named after its text; fixtures built by `printf` in the test (P005) |
| **Performance** | Matching is linear in the file. Candidates: 240 ms on 20,000 lines, measured (R4), with a 5 s deadline. Start-up as `view` (`difflib` is imported only on a failed match or a dry run) |
| **Constraints** | P1 (one call), P2 (bounded, always a verdict, atomic), P3 (the name `edit`), P5 (the file is whole or unchanged), rule 8 (`--dry-run`), rule 9 as revision 13 reads it |
| **Unknowns** | none: R1–R8 |

## Constitution Check

| Principle | Check | Result |
|---|---|---|
| P1 Unaided completion | One call per edit, no envelope (revision 13). A failed match names the candidates and the next command | ✅ |
| P2 Every call concludes | Bounded candidate search (5 s, R4), a 16 MiB cap, and a verdict for every refusal | ✅ |
| P3 Found where agents look | `edit`, the habit of every harness's edit tool, checked by `type -a`; announced by 007's generator | ✅ |
| P4 Reach only by grant | Nothing reaches beyond the environment | n/a |
| P5 Wrong turns are recoverable | Atomic: whole or byte-identical; a dry run first; `snapshot` and `undo` around a series | ✅ |
| P6 Claims are measured | Hash checks in every e2e (P004), not the tool's message | ✅ |
| P7 Harness-agnostic | A shell command | ✅ |
| H2 One output contract | On `agentio`; `confirm_protocol` is a contract field, checked by conform C2 | ✅ |
| H3 Verify artifacts, not messages | `sha256sum` in the container against expected bytes the test builds | ✅ |
| H4 Non-interactive | Flags, not stdin; no prompt | ✅ |
| H5 Stdlib-first | `difflib`, `tempfile`, `hashlib` | ✅ |
| H7 Every acceptance criterion is a test | SC-1 to SC-5, one e2e file each; SC-6 Manual (D6) | ✅ |

**quality-standards § Output contract (H2), the revision-13 bullet** (audited on `master` at `27600de`,
not merged into the stack): C2 checks it, and a unit shows it failing. Gates: pass.

## Project Structure (this feature)

```
tools/bin/edit                                   # new: the tool
tools/agentio/agentio.py                         # confirm_protocol; --yes, codes(), envelopes() follow it; manifest dry_run
tools/bin/snapshot                               # UNDO_TOOL: confirm_protocol=True (explicit)
tools/bin/timelike-conform                       # C2: the confirmation-scope checks
.specswarm/features/001-agent-shell-baseline/contracts/agent-info.schema.json   # confirm_protocol, dry_run
.specswarm/features/001-agent-shell-baseline/contracts/output-contract.md       # rule 9's sentence (revision 13)
tests/unit/test_edit.py                          # new
tests/unit/test_agentio.py, tests/unit/test_conform.py, test_conform_violations.py   # extended
tests/e2e/edit-*.bats                            # new: SC-1..SC-5, plus a contract file (type -a, manifest)
pyproject.toml, Makefile                         # edit added to the lint and mypy lists
README.md                                        # an "edit" section
```

## Phase 0: Research

`research.md` covers:
- R1: rule 9 and `confirm_protocol`;
- R2: the three levels;
- R3: the file's conventions;
- R4: candidates, measured;
- R5: the atomic write;
- R6: the name and the image;
- R7: the conform probe;
- R8: tests.

## Phase 1: Design

- **`data-model.md`:** the source, match, candidate and result, and the manifest fields with their
  invariants.
- **`contracts/edit-cli.md`:** the exact text and JSON for every outcome, and the refusals.
- **`quickstart.md`:** usage and host checks.

There is no agent context file in this repository, so the agent-context step does not apply.

## Tech Stack Compliance Report
<!-- Auto-generated by SpecSwarm tech stack validation: the installed tech-stack-classify block (lib/tech-stack-parser.sh, 2.35.0) classifies Python, pytest and bats-core APPROVED; none prohibited; nothing unparsed -->

### ✅ Approved Technologies (already in stack)
- Python (stdlib only: `difflib`, `hashlib`, `tempfile`)
- bats-core, pytest (testing)

### ➕ New Technologies (auto-added)
None.

### ⚠️ Conflicting Technologies (require approval)
None.

### ❌ Prohibited Technologies (cannot use)
None used.

---

# Cycle 2 — slice 1 (send `bridge/sends/06-rev1-20261009-102433.md`)

**Branch:** `modify/008-slice-1`, from `master` `ce1eaf2` (`bbb2c46` plus one `reboot.md` commit) · **Date:**
2026-10-09 · **specswarm:** 4.0.1-botbaubble.2.40.0, the expanded command's cache path · **Modify:** row 4
(`impact-analysis.md`, `modify.md` § Cycle 2) · **Spec:** § Slice 1 (FR-13 to FR-28, SC-7 to SC-9)

## Summary

- **Anchors** (FR-13 to FR-17, R11): `edit FILE --at N:h[..M:h] --new TEXT`. The ends are checked with
  `view`'s own `anchor_of` and `line_body`. Stale or moved anchors exit 3, naming the lines.
- **The syntax check** (FR-18 to FR-26, R9 to R15): an edit that would introduce a syntax error into a
  Python, TypeScript/TSX, Go, Rust or shell file is refused (exit 1) with the checker's error, and the
  file is byte-identical.
  - The checker is a child process (`tools/libexec/syntax-check`) with a 10 s limit. It fails open, and
    says so.
  - `--skip-syntax-check` is visible in the command and never suggested.
- **The image** gains four pinned wheels in timelike's interpreter and `/opt/timelike/libexec/syntax-check`.
- **Carried** (FR-28): `bash -lc` cells, `type -a` under `bash -lc`, and the owner branch under a second
  uid.

## Technical Context

| Item | Value |
|---|---|
| **Language** | Python 3.12+ (3.14.7 in the image). `edit` stays stdlib; the checker child imports `tree_sitter` only for TS/TSX/Go/Rust |
| **New dependencies** | `tree-sitter` 0.26.0 (binding), `tree-sitter-typescript` 0.23.2, `tree-sitter-go` 0.25.0, `tree-sitter-rust` 0.24.2, all prebuilt wheels pinned by SHA-256 in `pins.env`, in timelike's interpreter only (R9). Python and shell use the interpreter's compiler and `/bin/bash -n`: nothing new |
| **Contract module** | `agentio`, unchanged |
| **Other features' code** | `tools/bin/view`: `line_body()` factored out of `window()`, with identical output (R11). Declared in `changed_other_features` |
| **Testing** | pytest units (`tests/unit/test_edit_slice1.py`, new, written from the contract by a delegate; grammar-dependent units skip where the wheels are absent); bats e2e in the image, one file per criterion, `bash -c` and `bash -lc`, fixtures written by the test, anchors computed with `hashlib` (P005), hashes read by the test (P004), and a decoy `python3`/`bash` on the agent's PATH (P002) |
| **Performance** | One child per checked edit: interpreter start, tree-sitter import (TS/Go/Rust only), parse. 200k-line Python parses in 1.07 s with tree-sitter (R13); `compile()` is faster. Limit 10 s |
| **Constraints** | P2 (bounded, a verdict always, atomic), T4 (no silent skip, never suggested), P002 (nothing from PATH), RB1 (agent runtimes and vanilla untouched) |
| **Unknowns** | none (R9 to R16). Two are measured only in the lane: the cp314 binding's import, and `docker exec -u 0` for the owner cell (R16) |

## Constitution Check (Cycle 2)

| Principle | Check | Result |
|---|---|---|
| P1 Unaided completion | An anchored edit in one call. A stale anchor shows fresh anchors. A false refusal has a visible skip (R14) | ✅ |
| P2 Every call concludes | The checker child is killed at 10 s. Every outcome has a verdict. A checker's failure is named, not the file's (R13) | ✅ |
| P3 Found where agents look | `--at` takes `view --anchors`'s own form. Usage and the announcement name both | ✅ |
| P4 Reach only by grant | Offline: no network at check time; the wheels arrive at build | n/a |
| P5 Wrong turns are recoverable | A refused edit leaves the file byte-identical. The write is atomic as before | ✅ |
| P6 Claims are measured | Hash checks (P004). The grammars' false errors are measured and published (R10) | ✅ |
| P7 Harness-agnostic | Shell command and flags | ✅ |
| T4 | The skip is the agent's own, visible in command, verdict and event, and never suggested | ✅ |
| H2 One output contract | On `agentio`, with extra manifest fields only. Conform must pass | ✅ |
| H3 Verify artifacts | `sha256sum` before and after, in the container | ✅ |
| H4 Non-interactive | No prompt. The child gets stdin from `edit`, never from the agent | ✅ |
| H5 Stdlib-first | **Deviation, justified:** tree-sitter is the stack's named parser, and no stdlib module parses TS, Go or Rust. `edit` itself stays stdlib, and the deviation is confined to the child and to three languages. Python and shell use what is already there (R9) | ✅ justified |
| H7 Every acceptance criterion is a test | SC-7 and SC-8, one e2e file each. SC-9 is Manual (D15) | ✅ |

Gates: pass.

## Project Structure (Cycle 2)

```
tools/bin/edit                        # --at, the syntax check, --skip-syntax-check, manifest extras
tools/libexec/syntax-check            # new: the checker child (not on PATH)
tools/bin/view                        # line_body() factored out of window(); output unchanged
image/Dockerfile                      # wheels into timelike's purelib (hash-checked, import-checked); libexec copy
pins.env, compose.yaml, Makefile      # TREE_SITTER_*_VERSION / _SHA256 pins, as build args
pyproject.toml                        # syntax-check in the ruff and mypy lists; tree_sitter imports untyped
.specswarm/tech-stack.md              # the four packages (1.6.0)
tests/unit/test_edit_slice1.py        # new (delegate, from the contract)
tests/unit/test_edit.py, test_agent_runtimes.py   # manifest assertions; pins and build-arg lists
tests/e2e/edit-anchored-lines-unchanged-applies-changed-lines-refused-naming-them.bats             # SC-7
tests/e2e/edit-would-fail-syntax-check-refused-with-checker-error-file-byte-identical.bats          # SC-8
tests/e2e/edit-slice-0-carried-items.bats                                                          # FR-28
tests/e2e/edit-*.bats (slice 0)       # bash -lc cells
README.md                             # command reference regenerated; the README status block (if all three are met)
```

## Phase 0 and Phase 1

- **Research:** R9 to R16.
- **Design:**
  - `data-model.md` § Slice 1;
  - `contracts/edit-cli.md` § Slice 1 (the exact verdicts, the JSON and the child's protocol);
  - `quickstart.md` § Slice 1.

There is no agent context file in this repository, so the agent-context step does not apply.

## Tech Stack Compliance Report (Cycle 2)
<!-- The installed tech-stack-classify block (lib/tech-stack-parser.sh, 2.40.0) ran on 2026-10-09: tree-sitter, Python, bash, uv APPROVED; the binding and three grammars AUTO_ADD; none prohibited; nothing unparsed -->

### ✅ Approved Technologies (already in stack)
- Python, bash, uv (the wheels are installed with the pinned uv)
- tree-sitter (structural search). This cycle uses its Python binding as the carrier (R9)

### ➕ New Technologies (auto-added)
- **tree-sitter** 0.26.0 (the Python binding), **tree-sitter-typescript** 0.23.2, **tree-sitter-go** 0.25.0,
  **tree-sitter-rust** 0.24.2
  - Purpose: `edit`'s syntax check for TypeScript/TSX, Go and Rust
  - No conflicts detected
  - Added to: Approved Libraries (Python additions), with the justification
  - Version updated: 1.5.0 → 1.6.0

### ⚠️ Conflicting Technologies (require approval)
None.

### ❌ Prohibited Technologies (cannot use)
None used.
