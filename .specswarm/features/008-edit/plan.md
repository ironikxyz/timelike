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
