
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

### T003: e2e — SC-1 (on start, user level, workspace untouched), SC-2 (from manifests; a missing tool fails), SC-3 (the manifest) and P6 (delegated)
**Started:** after 8b45fc2 (the delegate's own start was not read from a clock) | **Completed:** 2026-10-04T20:00:14Z

INHERITED: the contract and spec D-1; helpers.bash and the throwaway pattern (confidence: high)
FLAGGED: SC-1 runs on fresh throwaway containers, so "on container start" is the image's real entrypoint; the existing-file case starts its own container whose first process writes a non-timelike ~/.claude/CLAUDE.md and then execs the image's ENTRYPOINT (read from the image) (confidence: high)
FLAGGED: SC-1's workspace clause is asserted in the opposite sense (no CLAUDE.md/AGENTS.md created in the WORKDIR or a git repository, which stays clean) — spec D-1, FOR-MENTOR Item 19; the cells change if plan amends the criterion (confidence: medium)
FLAGGED (delegate): the 1 s placement bound is measured from the daemon's container start time to the files' mtimes — assumes one clock (confidence: medium)
ASSUMED: pgrep exists in the image (procps, Dockerfile line 31) and the command is PID 1's child under --init (confidence: high)
ABSENT: --check's `extra:` and Codex's override end to end — units cover them
Verification: reviewed; shellcheck clean; bats --count 6, 6, 6 (delegate); in-container scripts dry-run on the host with stand-ins, failure cases included (delegate); four contract gaps settled as built
SCOPE: in (3 changed files)

### T007: README — announcements section; Makefile SHELLCHECK_FILES
**Started:** 2026-10-04T19:57:29Z | **Completed:** 2026-10-04T20:00:19Z

INHERITED: the behaviour of T004–T006 (confidence: high)
ASSUMED: the README is a place agents and operators read (P3); the announcement itself is the place harnesses read (confidence: high)
ABSENT: the README's Status paragraph — it lists features by slice; 007 is added when the batch is reconciled
Verification: shellcheck clean over the four new files; the README text matches the paths and commands as built
SCOPE: in (2 changed files)

### T008: host lane — lint, units with coverage, make test-host, timings
**Started:** 2026-10-04T20:00:28Z | **Completed:** 2026-10-04T20:22:56Z

INHERITED: T001–T007's files (confidence: high)
FLAGGED: the first coverage run read 51% overall — not a measurement of the code: the new units install timelike into pytest `tl/` directories, which the scratch coverage rc did not map back to tools/bin, so each copy counted as its own partly covered file. Added the mapping and re-ran: 95% (an rc defect of this instance's, recorded in reboot.md's coverage recipe at the next reboot rewrite) (confidence: high)
FLAGGED: `timelike tools` and `timelike announce` take about 680 ms p95 on the host, because each runs every tool's --agent-info (8 subprocesses) — acceptable for a manifest command; the entrypoint's `announce --install` reads one file (status p95 72 ms), so container start is not delayed by the generation (confidence: high)
ASSUMED: the image's Python 3.14.7 behaves as the host's for subprocess and os.replace (confidence: high)
ABSENT: the e2e — the delegate dry-ran its in-container scripts with stand-ins; the image and the entrypoint run only in the mentor's lane
Verification: ruff check and format (63 files), mypy strict (21 files), shellcheck over every *.sh/*.bash/*.bats and the entrypoint: clean; units with subprocess coverage: 1309 passed, 1 skipped (530 s); Python 95% overall, timelike 92%; make test-host: passed; p95 (host, 20 runs, exits asserted): timelike --help 76 ms, --json 69 ms, announce --status 72 ms, tools 688 ms, announce 675 ms
SCOPE: none — no files outside the feature's artifacts changed

### T009: cycle report § Cycle 1, implement step 10, metrics entry
**Started:** 2026-10-04T20:23:08Z | **Completed:** 2026-10-04T20:23:47Z

INHERITED: T001–T008's records (confidence: high)
FLAGGED: SC-1 cited as built for its user-level part only, with Item 19 named beside the citation — the citation is the criterion's, the narrowing is stated next to it rather than in it (confidence: high)
ABSENT: demo_points_reached — the mentor derives it
Verification: four citations, grep -cF = 1 each against the send; step 10 run from the installed blocks (identical to 003's); metrics.json gains 007 only; deny-list PASS
SCOPE: in (1 changed files)

## Cycle 2 — send `bridge/sends/04-rev13-20261008-095251.md` (specswarm 4.0.1-botbaubble.2.37.0)

### T010: spec SC-1 quotes revision 13's criterion; SC-1's note, FR-7's note and Out of scope follow
**Started:** 2026-10-08T10:10:29Z | **Completed:** 2026-10-08T10:10:29Z | **Coordinator**

INHERITED: (none — first task of the cycle); the classification in impact-analysis.md § Cycle 2 — (confidence: high)
FLAGGED: the superseded notes are struck through and kept, each followed by a declared *(Revised, revision 13 …)* note — chose that over deleting them, so the record of the narrowing stays readable (the send: "declared copies, never silent edits") — (confidence: high)
ASSUMED: SC-1's "Tested for the user-level part" becomes "Tested", because the criterion is now user-level only and the cells test all of it — (confidence: high)
ABSENT: no other body line changes; decisions.md T003's cell sense and Cycle 1's citation are left as written (append-only records)
SCOPE: none — no files outside the feature's artifacts changed
