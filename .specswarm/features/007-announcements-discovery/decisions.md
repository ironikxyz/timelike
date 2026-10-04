
### T001: image/rootfs/etc/timelike/standard-tools.json — the curated entries
**Started:** 2026-10-04T19:49:57Z | **Completed:** 2026-10-04T19:49:58Z

INHERITED: (none — first task)
FLAGGED: 20 entries over the classes research R4 names (pagers and editors, unbounded readers, REPLs, prompting commands, long or hanging runs, git) — chose data in the image over code, so an entry is a one-line change and the manifest's test reads the same file (confidence: high)
ASSUMED: `instead` for an editor is a non-interactive edit (sed -i or a heredoc); 06's edit tool is built later in this batch (008) and can be named here once it exists (confidence: medium)
ABSENT: entries for tools the image does not install — `installed` is computed at run time, so an entry for an absent tool still warns an agent that brings it
Verification: valid JSON, 20 entries, every field present
SCOPE: in (1 changed files)

### T004: timelike announce (generate, --write, --check) and timelike tools
**Started:** 2026-10-04T19:50:20Z | **Completed:** 2026-10-04T19:52:29Z

INHERITED: the curated file — from T001; 001's timelike (revision, bin dirs, TIMELIKE_REVISION hook) (confidence: high)
FLAGGED: subcommands of `timelike` (announce, tools), not new names on PATH — spec D-4 (confidence: high)
FLAGGED: a rule line in the announcement is written only when the tools it names are installed — chose that over static rules, so the announcement never names a tool that is not there (the drift FR-3 forbids, in the rules as well as the list) (confidence: high)
FLAGGED: tools/bin/view and tools/bin/search were committed as mode 100644 (006 Cycle 1); the image's COPY --chmod=0755 hid it, so the lane passed. The generator skips non-executables (correct), which is how it showed: 6 tools announced instead of 8. Fixed here (mode 0755), declared as changed_other_features (006) (confidence: high)
ASSUMED: a summary's whitespace is collapsed to one line (`" ".join(split())`), so a multi-line summary cannot break the one-line-per-tool layout (confidence: high)
ABSENT: placement (--install, --status) — T005; a placeholder refuses it with a usage error until then
Verification: ruff, format, mypy clean; on a fake bin dir with the 8 real tools: 23 lines, 8 tools, marker with the revision; --check equal → 0, a removed line → 1 "missing: undo"; tools: 8 timelike + 20 standard entries; plain `timelike` unchanged; test_conform*, test_view*, test_search: passed
SCOPE: in (3 changed files)

### T005: timelike announce --install / --status; the entrypoint
**Started:** 2026-10-04T19:52:51Z | **Completed:** 2026-10-04T19:53:17Z

INHERITED: the announcement file and the marker line — from T004 (confidence: high)
FLAGGED: placement replaces a file only when its first line is timelike's marker; any other file is left byte for byte ("not placed") — chose the marker over a content or name test, because only a file timelike wrote carries it, and an older timelike announcement must be replaced so a rebuilt image is never stale (confidence: high)
FLAGGED: Codex's non-empty AGENTS.override.md is reported as "shadowed" after placing AGENTS.md, rather than writing into the override — the override is the operator's or the user's (confidence: high)
FLAGGED: the entrypoint discards install's output and ignores its exit, then execs the command — a placement must never stop a container (FR-8); --status is how a person or a test sees what happened (confidence: high)
ASSUMED: a directory created for a harness file gets mode 0700 and the file 0644, written beside the target and renamed (confidence: high)
ABSENT: the image wiring (COPY, ENTRYPOINT) — T006
Verification: ruff, format, mypy, shellcheck clean; temp HOME: 3 placed, byte-identical; again 3 current; someone else's codex file kept ("mine"), a stale timelike file replaced; a non-empty AGENTS.override.md → codex shadowed; a missing source → 3 not placed with the reason, exit 0
SCOPE: in (2 changed files)


### T002: tests/unit/test_announce.py (delegated); four deviations it found
**Started:** after 8b45fc2 (the delegate's own start was not read from a clock) | **Completed:** 2026-10-04T19:56:54Z

INHERITED: the contract (with TIMELIKE_ANNOUNCEMENT, added while it worked) and test_conform.py's harness (confidence: high)
FLAGGED: committed after T004–T006 landed; its 49 tests ran against the code and 4 failed on real deviations, three fixed in tools/bin/timelike here: name order across bin dirs (sorted globally, first directory wins), every created directory 0700 (not only the last), a curated file with v != 1 rejected (confidence: high)
FLAGGED: the fourth, `current` for a same-revision file with another body — kept the code (restore it: the marker says do not edit) and changed the contract and the test, split into an identical-is-current test and a hand-edited-is-replaced test (confidence: medium)
FLAGGED: four contract gaps settled as built (conditional rules, the tools text and verdict, the status line format, v 1) (confidence: high)
ABSENT: a second bin directory in the image — the order fix matters on hosts and in tests only
Verification: 50 passed; ruff, format and mypy clean
SCOPE: in (2 changed files)

### T006: image/Dockerfile — the curated file and the entrypoint copied; the announcement generated and checked after the stamp; ENTRYPOINT
**Started:** 2026-10-04T19:53:39Z | **Completed:** 2026-10-04T19:57:13Z

INHERITED: the subcommands and the entrypoint — from T004 and T005 (confidence: high)
FLAGGED: generation runs as root during the build with its own throwaway scratch root, removed after, and the step asserts /tmp/timelike does not exist — the tools write their session events into the scratch root, and a root-owned /tmp/timelike in the image would lock the agent out of its scratch space (rule 10) (confidence: high)
FLAGGED: the step runs after the build stamp, so the announcement names this revision (P003), and only this layer and the stamp's change per commit (confidence: high)
FLAGGED: ENTRYPOINT changes the agent image for every consumer: compose's agent, the e2e throwaways (start_throwaway runs IMAGE sleep infinity, so the entrypoint runs) and the bench's timelike arm — declared; docker exec does not run it (confidence: medium)
ASSUMED: no e2e test asserts the agent's home is empty or lists it (a grep over tests/e2e and tests/host found none) (confidence: medium)
ABSENT: an image build — no Docker here; the mentor's lane builds it
Verification: the build step simulated on the host (fake /etc, the real tools, a scratch root of its own): write "23 lines, 8 tools"; check "all 8 installed tools are announced", exit 0; the scratch root received the tools' session directory (so the separate root is needed); 23 ≤ 60. A first attempt was blocked by Claude Code's removal safety check (an rm -rf of a variable inside sh -c); re-run without any removal, the scratch directory left in the scratchpad. That blocked attempt also cost a blank line in decisions.md (the helper had begun appending)
SCOPE: in (1 changed files)
