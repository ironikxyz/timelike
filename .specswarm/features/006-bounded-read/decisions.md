# Decisions Log — Feature 006
> Generated at 2026-10-04T07:05:00+00:00
> Spec: .specswarm/features/006-bounded-read/spec.md

## Decision Key

| Tag | Meaning |
|-----|---------|
| ASSUMED | Assumption made without explicit spec guidance (confidence: high/medium/low) |
| DEFERRED | Decision postponed — noted for later resolution |
| FLAGGED | Judgment call between alternatives — requires review |
| ABSENT | What was NOT done and why — forced reflection on gaps |
| INHERITED | Assumption carried forward from a prior task's output |

---

### T002: lint lists gain view, search, the fixture and the five e2e files
**Started:** 2026-10-04T07:08+00:00 | **Completed:** 2026-10-04T07:10+00:00

INHERITED: (none — first task) the file names fixed in tasks.md T001, T003–T007 (confidence: high)
ASSUMED: the lists name files that T001, T003–T007, T010 and T011 create; until they exist, `make lint` and mypy would report them missing (as 005's T002 did before its tools) (confidence: high)
FLAGGED: none
ABSENT: no new lint rule or tool version; nothing else in pyproject or the Makefile changed
Verification: `git diff` shows only the six SHELLCHECK_FILES lines and the two Python list entries
SCOPE: in (2 changed files)

### T001: fixture tests/e2e/fixtures/bounded-read.sh (delegate A)
**Started:** 2026-10-04T07:12+00:00 | **Completed:** 2026-10-04T09:25+00:00

INHERITED: T001's content list and the contract (confidence: high)
ASSUMED: content is built with seq, printf, awk and git only; the self-checks also use grep, od, tr, sort, wc and `git grep --untracked`, which judge the fixture, not the tools (confidence: high)
FLAGGED: none
ABSENT: no long hit line in the repo, so search's `long lines cut:` path is covered by the units only (T009), not by e2e
Verification: run under dash on the host: big.txt 412 lines (16276 bytes), repo 262 hits in 10 files (12 searched), 25 + 5 ignored, 9 inside .git; the narrowing rule picks src (188 of 262) with no tie; a changed count makes the script exit 1 (delegate's check)
SCOPE: in (1 changed files)

### T003: e2e for SC-1, written from the contract before the tools (delegate A)
**Started:** 2026-10-04T07:12+00:00 | **Completed:** 2026-10-04T09:25+00:00

INHERITED: the contract, the T001 fixture, helpers.bash; the coordinator's mid-task corrections (revision 12's JSON cut, target_line, the narrowing rule, the shlex scope) (confidence: high)
ASSUMED: expected values come from the fixture inside the container (awk, sed, wc, git ls-files as the search oracle), never from the tool (P004) (confidence: high)
FLAGGED: none
ABSENT: no image run here (no Docker, R10); the Docker lane decides
Verification: shellcheck clean; the delegate ran every check against a scratch stand-in of the contract and broke it 17 ways, each caught by its target check; host docker stand-in (T013) run separately
SCOPE: in (1 changed files)

### T004: e2e for SC-2, written from the contract before the tools (delegate A)
**Started:** 2026-10-04T07:12+00:00 | **Completed:** 2026-10-04T09:25+00:00

INHERITED: the contract, the T001 fixture, helpers.bash; the coordinator's mid-task corrections (revision 12's JSON cut, target_line, the narrowing rule, the shlex scope) (confidence: high)
ASSUMED: expected values come from the fixture inside the container (awk, sed, wc, git ls-files as the search oracle), never from the tool (P004) (confidence: high)
FLAGGED: JSON `lines` of a missing file expected `[]`, where D-10 puts the `do instead:` line in `lines` in both modes; corrected in T013 (confidence: medium, as written)
ABSENT: no image run here (no Docker, R10); the Docker lane decides
Verification: shellcheck clean; the delegate ran every check against a scratch stand-in of the contract and broke it 17 ways, each caught by its target check; host docker stand-in (T013) run separately
SCOPE: in (1 changed files)

### T005: e2e for SC-3, written from the contract before the tools (delegate A)
**Started:** 2026-10-04T07:12+00:00 | **Completed:** 2026-10-04T09:25+00:00

INHERITED: the contract, the T001 fixture, helpers.bash; the coordinator's mid-task corrections (revision 12's JSON cut, target_line, the narrowing rule, the shlex scope) (confidence: high)
ASSUMED: expected values come from the fixture inside the container (awk, sed, wc, git ls-files as the search oracle), never from the tool (P004) (confidence: high)
FLAGGED: none
ABSENT: no image run here (no Docker, R10); the Docker lane decides
Verification: shellcheck clean; the delegate ran every check against a scratch stand-in of the contract and broke it 17 ways, each caught by its target check; host docker stand-in (T013) run separately
SCOPE: in (1 changed files)

### T006: e2e for SC-4, written from the contract before the tools (delegate A)
**Started:** 2026-10-04T07:12+00:00 | **Completed:** 2026-10-04T09:25+00:00

INHERITED: the contract, the T001 fixture, helpers.bash; the coordinator's mid-task corrections (revision 12's JSON cut, target_line, the narrowing rule, the shlex scope) (confidence: high)
ASSUMED: expected values come from the fixture inside the container (awk, sed, wc, git ls-files as the search oracle), never from the tool (P004) (confidence: high)
FLAGGED: none
ABSENT: no image run here (no Docker, R10); the Docker lane decides
Verification: shellcheck clean; the delegate ran every check against a scratch stand-in of the contract and broke it 17 ways, each caught by its target check; host docker stand-in (T013) run separately
SCOPE: in (1 changed files)

### T007: e2e for FR-23, written from the contract before the tools (delegate A)
**Started:** 2026-10-04T07:12+00:00 | **Completed:** 2026-10-04T09:25+00:00

INHERITED: the contract, the T001 fixture, helpers.bash; the coordinator's mid-task corrections (revision 12's JSON cut, target_line, the narrowing rule, the shlex scope) (confidence: high)
ASSUMED: expected values come from the fixture inside the container (awk, sed, wc, git ls-files as the search oracle), never from the tool (P004) (confidence: high)
FLAGGED: the conform cells check only view's and search's own lines, not conform's overall exit, so another tool's finding cannot fail this file; the brief named a conform cell in snapshot-refuses-…, which has none, so it was modelled on 001's conformance file (confidence: high)
ABSENT: no image run here (no Docker, R10); the Docker lane decides
Verification: shellcheck clean; the delegate ran every check against a scratch stand-in of the contract and broke it 17 ways, each caught by its target check; host docker stand-in (T013) run separately
SCOPE: in (1 changed files)

### T008: tests/unit/test_view.py, from the contract (delegate B)
**Started:** 2026-10-04T07:12+00:00 | **Completed:** 2026-10-04T09:10+00:00

INHERITED: test_snapshot.py's helpers (doc_of, text_of, said, stderr_error, human, write); agentio's Cut rendering for the footer order (confidence: high)
FLAGGED: read the top-level `target` as FILE over the data model's window `target` (N), because agentio reserves `target`; this found the contract defect fixed in T012 (`target_line`) (confidence: high)
ASSUMED: the long-lines line is the last of JSON `lines`; the cut applies to the whole formatted line, number prefix included; sizes use 005's human format (confidence: medium)
ABSENT: none of the verdict variants the contract writes as `…`; no singular wording
Verification: 68 collected; ruff, format and mypy strict clean; all pass against T010 and T015
SCOPE: in (1 changed files)
