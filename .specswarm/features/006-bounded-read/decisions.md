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

### T009: tests/unit/test_search.py, from the contract (delegate B)
**Started:** 2026-10-04T07:12+00:00 | **Completed:** 2026-10-04T09:10+00:00

INHERITED: test_view.py's and test_snapshot.py's helpers; the narrowing rule from data-model.md (confidence: high)
FLAGGED: the narrowing follows the rule (src, 188) over the contract's example (src/engine, 148); the example was wrong and is corrected in T012 (confidence: high)
FLAGGED: --timeout 0.001 over 3000 files, not --timeout 0, because the contract gave 0 no meaning; T012 now makes 0 = no limit (confidence: medium)
FLAGGED: the 262-hit test compared its section labels with `expected_groups(capped[:CAP])`, which counts a file's hits from the shown 50 only and so contradicted the test's own next assertion `(20 of 40)`; corrected in T012 (as written: a test bug)
ASSUMED: .gitignore files count in files_searched (hidden files are searched); a pruned directory counts as one ignored entry; symlinked files are not followed (confidence: medium)
ABSENT: the exact zero-match verdict tail; whether a root .gitignore above a searched subdirectory applies (T011 applies it, as git does)
Verification: 92 collected; ruff, format and mypy strict clean
SCOPE: in (1 changed files)

### T015: FR-7 under discovery revision 12 — rule 13's line cut in JSON, in agentio
**Started:** 2026-10-04T09:00+00:00 | **Completed:** 2026-10-04T09:40+00:00

INHERITED: discovery revision 12 (Q3 (a)) and the re-send `05-rev1-20261004-085517` ("the fix belongs in agentio"); T008/T009 written against it after the coordinator's message (confidence: high)
FLAGGED: JSON carries the cut as `cut_lines: [{index, cut_bytes}]` beside `lines`, over a per-string object, because `lines` stays a list of strings for every existing consumer; `cut_lines` is a reserved key (confidence: high)
FLAGGED: added `Result.footer` (a count of trailing body lines that are the tool's own closing commands) so those lines are never cut in either mode; without it the `long lines cut:` and `narrow:` commands are cut themselves when COLUMNS is small or a path is long, and a cut command cannot be run (found by T008's COLUMNS=40 case) (confidence: high)
FLAGGED: changed another feature's test: 005's outcome helper (`tests/unit/test_snapshot.py`) asserted JSON `lines[0]` equals the full `do instead:` remedy; under pytest's long temp paths that line exceeds 200 characters and is now cut in JSON as text already cut it, while `data.remedy` carries it whole; the helper now expects the cut form (confidence: high)
ASSUMED: verdicts, errors and data fields are not content and are not cut (revision 12 names file lines, hits and log lines) (confidence: high)
ABSENT: no total byte bound per call (revision 6's bench question); 001's spec is not modified (the re-send: UNAUDITED at 11 and 12, the next 01 modify records both)
Verification: all units 895 + the new ones; only the two 005 cases changed, both through the helper; the 005 and 003 e2e through the host stand-in show no new failure (the 4 type -a and 4 run cells need the image)
SCOPE: in (3 changed files)

### T010: tools/bin/view
**Started:** 2026-10-04T07:15+00:00 | **Completed:** 2026-10-04T09:45+00:00

INHERITED: the contract § view (Q1 (a)); T015's agentio `columns` and `footer`; T008's units (confidence: high)
FLAGGED: a window that ends at the file's end has nothing after it, so its `more:` is the window before (`FILE:{S-120}-{S-1}`); Q1 answered `more:` for a window with lines after it, and is silent on this case (confidence: medium)
FLAGGED: `--limit 0` with no range shows the whole file (spec FR-6, quickstart), where data-model.md first said 1-120; the data model is corrected in T012 (confidence: high)
ASSUMED: the file is streamed once (line count, bytes and the window's lines), so a large file is never held whole; stray ESC bytes the rule-13 pattern leaves are removed too, or conform's C8 would fail (confidence: high)
ABSENT: no anchor column (slice 1); the layout leaves its place between the marker and the text (D-9)
Verification: 68 units pass; ruff, format, mypy strict clean; the view e2e files through the host stand-in pass
SCOPE: in (1 changed files)

### T011: tools/bin/search
**Started:** 2026-10-04T09:45+00:00 | **Completed:** 2026-10-04T10:05+00:00

INHERITED: the contract § search (Q2 (a)), research R1, R2, R6; T015's footer; T009's units (confidence: high)
FLAGGED: the ignore rules include every `.gitignore` from the enclosing repository's root down to the search root, as git applies them, over only the files met in the walk (the contract said "in the walk"); amended in T012 (confidence: high)
FLAGGED: the body is kept within --limit by search itself (fewer hits shown, still a hit-list cut); otherwise agentio's generic cap would cut it with a re-run as `more:`, which the contract forbids (confidence: high)
FLAGGED: uncapped output shows file labels as lines in text only; JSON `lines` stay the hit lines, matching T009 (confidence: medium)
ASSUMED: symlinks met in the walk are skipped (neither followed nor counted); a pruned ignored directory counts as one ignored entry; --timeout takes decimals, 0 = no limit (confidence: medium)
ABSENT: no ripgrep (D-8); no context lines around hits; no -w
Verification: 92 units pass; ruff, format, mypy strict clean; the search e2e files through the host stand-in pass
SCOPE: in (1 changed files)
