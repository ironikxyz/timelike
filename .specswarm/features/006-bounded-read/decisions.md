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

### T012: units against the tools; the contract corrected where the units found it wrong
**Started:** 2026-10-04T09:10+00:00 | **Completed:** 2026-10-04T10:10+00:00

INHERITED: T008–T011, T015 (confidence: high)
FLAGGED: contract amended where it was wrong or silent, each marked in place: JSON `target_line` (rule 12 reserves `target`); the scope is `shlex.quote(pattern)` (the example's `['parse_args']` was not); the narrowing example now follows the rule (`src`, 188); `--timeout` takes decimals and 0 = no limit; ignore rules include the `.gitignore` files above the search root; data-model's `--limit 0` reads the whole file (FR-6) (confidence: high)
FLAGGED: one test corrected: `expected_groups` counted a file's hits from the shown 50 only, contradicting the test's own `(20 of 40)` assertion and the contract; it now takes every hit for the totals (confidence: high)
ABSENT: no tool behaviour changed in this task; every disagreement was decided by the contract
Verification: 160 units pass (68 view, 92 search); ruff, format, mypy strict clean
SCOPE: in (1 changed files)

### T013: e2e through the host docker stand-in (advisory)
**Started:** 2026-10-04T10:00+00:00 | **Completed:** 2026-10-04T10:15+00:00

INHERITED: the 005 stand-in recipe (exec runs the command here with the test's -e variables, a stand-in home, the tools on PATH with the shebang rewritten, no -I), bats-core v1.14.0 (confidence: high)
ASSUMED: the stand-in also exports TIMELIKE_BIN_DIRS at its tool directory, so the conform cells can find the tools; that is a stand-in setting, not the image's (confidence: high)
FLAGGED: one e2e expectation corrected: SC-2's missing-file JSON expected `lines == []`, where D-10 (as in 005) puts the `do instead:` line in `lines` in both modes and the units pin it so for `search --strict` (confidence: high)
ABSENT: nothing here is image evidence: no /opt/timelike/bin, no REVISION stamp, no /opt/timelike/python, host Python 3.12
Verification: 006's 60 cells: 52 ok; the 8 not ok are image-only (4 `type -a` cells pin /opt/timelike/bin; 4 `timelike` list cells need /opt/timelike/REVISION). 005 and 003 after T015's agentio change: 60 of 70 ok; the 10 not ok are image-only (6 `type -a`, 4 `run` cells whose fixture calls /opt/timelike/python directly), none from the change
SCOPE: in (1 changed files)

### T014: README — "view and search — bounded reads, each ending with the next command"
**Started:** 2026-10-04T10:15+00:00 | **Completed:** 2026-10-04T10:18+00:00

INHERITED: the contract as amended (T012, T015) (confidence: high)
ASSUMED: the README is where this project announces tools (003's and 005's decision, kept); `timelike` lists both automatically (confidence: high)
FLAGGED: none
ABSENT: no harness context file inside the image announces them (none exists yet, as for 005)
Verification: each example's output text checked against the contract and the units (the binary line's size format, the narrow line, the strict exit)
SCOPE: in (1 changed files)

### T016: host lane, coverage, implement step 10, cycle report § Cycle 1, metrics entry
**Started:** 2026-10-04T10:20+00:00 | **Completed:** 2026-10-04T10:45+00:00

INHERITED: T001–T015 and their verification (confidence: high)
ASSUMED: every criterion is unconfirmed until the Docker lane runs on this branch; the host lane and the stand-in are advisory (as in 001, 003 and 005) (confidence: high)
FLAGGED: none
ABSENT: no Docker lane (R10); no ship or merge (they wait for the lane, the D5 demo and the mentor's sign-off); no demo_points_reached; no Group A (no marker on this path)
Verification: make test-host 1055 passed, 60/60, 29/29; coverage view 96%, search 93%, agentio 95%; ruff, mypy, shellcheck clean; implement step 10 run from the installed 2.35.0 blocks (unknown, warned); all five criterion citations match one send line each
SCOPE: out — .specswarm/metrics.json (1 of 1 changed files) (task has FLAGGED: no)

### T019: view DIR — the overview (FR-24 to FR-31)
**Started:** 2026-10-04T19:19:30Z | **Completed:** 2026-10-04T19:21:33Z

INHERITED: search's ignore rules (D-5) and display() (P002) — loaded from tools/bin/search, as undo loads snapshot (005 R8) (confidence: high)
FLAGGED: the overview is `view DIR`, replacing slice 0's directory refusal (FR-8, exit 2) — chose one name over a new tool, because discovery's own example is `view`, vim's `view .` lists a directory, and a new name must be discovered (P3); declared in spec § Slice 1 and impact-analysis (confidence: high)
FLAGGED: the budget is rule 3's output cap in lines — chose the unit the contract already has (send seam 1), over bytes (revision 6 leaves a total byte bound to the bench) and entries (a third unit) (confidence: high)
FLAGGED: breadth-first fit is greedy: a directory too large for the lines left is collapsed as `budget`, and later, smaller ones may still expand — the contract's "each one only if its entries fit the lines left" (confidence: medium)
FLAGGED: singular forms everywhere in the overview (`1 dir`), changing the contract's own example — the carried plural fix applies from the start; both test delegates told (confidence: high)
ASSUMED: a dependency directory is recognised by name (FR-28's list), not by content (R8) (confidence: medium)
ABSENT: the 100,000 count cap is not reached by any fixture here — a unit would need a patched constant
ABSENT: --no-ignore keeps .git collapsed, as specified; nothing lists inside .git
Verification: ruff, format, mypy clean; a fixture repository (10,000-file node_modules, .git, build, an ignored file, a symlink): node_modules one line with its counts and expand command, symlink shown not followed, 1 ignored file counted; view node_modules/ expands breadth-first within 200 lines; tests/unit/test_view.py 2 expectations updated for FR-24 (declared), 160 passed with test_search.py
SCOPE: in (2 changed files)

### T020: view --anchors (FR-32 to FR-35)
**Started:** 2026-10-04T19:21:53Z | **Completed:** 2026-10-04T19:22:04Z

INHERITED: the window code and the overview's flags — from T019 (confidence: high)
FLAGGED: the anchor hashes the line's raw bytes (before decoding, escape stripping and the COLUMNS cut), line ending removed — chose raw bytes over the shown text, because the shown text depends on COLUMNS and on replacement, which would make the anchor unstable across views; removing \r\n makes CRLF and LF copies agree, which 06 needs (R9) (confidence: high)
FLAGGED: 6 hex characters (24 bits) — chose them over 4 (16 bits, 1 in 65,536 per changed line) as short enough for a column and unlikely to collide over a session of edits; 06 also checks the line number (R9) (confidence: medium)
ASSUMED: hashlib is imported only under --anchors, so the file mode's start-up is unchanged (confidence: high)
ABSENT: anchors in the overview — a directory has no lines of a file; --anchors on a directory is a usage error (T019)
Verification: ruff, format, mypy clean; a 4-line file with a CRLF line, an escape sequence and an invalid byte: each anchor equals sha256(raw line)[:6] computed separately; view --anchors FILE:2 marks line 2
SCOPE: in (1 changed files)

### T021: search's (and view's) verdict plurals (FR-36)
**Started:** 2026-10-04T19:22:11Z | **Completed:** 2026-10-04T19:22:51Z

INHERITED: the D5 transcript's defect `44 matches in 1 files (searched 1 files)` (mentor, history 2026-10-04T18:27:32Z) — from 006 Cycle 1 (confidence: high)
FLAGGED: view's own verdict notes had the same defect (`1 undecodable bytes`, `1 lines had terminal escapes stripped`), seen in T020's check — fixed here too, beyond the task's wording, because the carried item is the plural and leaving one tool's would carry it again (confidence: high)
ASSUMED: "skipped N kind" stays as written (`skipped 1 ignored`): the kind is an adjective there, with no plural to fix (confidence: high)
ABSENT: plurals in other tools' verdicts (run, snapshot, adele) — not this feature's; none was reported
Verification: ruff and format clean; tests/unit/test_view.py and test_search.py: 160 passed (their expectations use counts above 1); the singular cases are in T017's units
SCOPE: in (2 changed files)
