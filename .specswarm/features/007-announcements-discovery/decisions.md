
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

### T011: spec D-1 — resolution appended, reasoning kept
**Started:** 2026-10-08T10:10:45Z | **Completed:** 2026-10-08T10:10:45Z | **Coordinator**

INHERITED: T010 (same file; SC-1 and FR-7 already name D-1 as resolved) — (confidence: high)
ASSUMED: the resolution is a paragraph after D-1, not an edit inside it, so D-1's original FLAGGED reasoning reads as it did — (confidence: high)
ABSENT: research.md's seam reasoning is unchanged (still true); FOR-MENTOR.md is not touched (Item 19 already closed; outside the feature directory)
SCOPE: none — no files outside the feature's artifacts changed

### T012: provenance — audited_against [1] → [1, 13] (scoped); audit-log.md created
**Started:** 2026-10-08T10:11:12Z | **Completed:** 2026-10-08T10:11:12Z | **Coordinator**

INHERITED: T010, T011 — (confidence: high)
FLAGGED: scoped, not full — revision 13 rewords a criterion, so the installed block in full mode, given UNVERIFIED=13, appends 2–12 and leaves 13 out (verified); scoped appends 13 alone, which is what this cycle checked and what the send asks — (confidence: high)
ASSUMED: the new audit-log.md opens with a seed row for specify's [1], dated by the spec's created_at and marked as written now, as 002's log did — (confidence: high)
ABSENT: prompt_revision (1), discovery_revision (12) and source_prompt untouched; revisions 2–12 not appended
SCOPE: none — no files outside the feature's artifacts changed

### T013: cycle report § Cycle 2; implement steps 10 and 9b recorded
**Started:** 2026-10-08T10:12:16Z | **Completed:** 2026-10-08T10:12:16Z | **Coordinator**

INHERITED: T010–T012; lane readme-c from bridge/history.md and its log (ok 41–52, 426–431) — (confidence: high)
FLAGGED: SC-1 cited by text outside the strike, not by Cycle 1's text — Cycle 1's quoted the struck clause and matches no line of this send; the new text matches exactly one — (confidence: high)
ASSUMED: D4 keeps "observed by the operator" (Cycle 1 Addendum 2) — (confidence: high)
ABSENT: the stale e2e cell names are reported, not renamed (tests/ is outside the feature directory); no demo_points_reached; no .implement-complete; metrics.json not written
SCOPE: none — no files outside the feature's artifacts changed

### T016: agentio gains cgroup_dir, cgroup_value, cpu_figure, workspace; run and snapshot use them
**Started:** 2026-10-08T16:28:58Z | **Completed:** 2026-10-08T16:31:57Z | **Coordinator**

INHERITED: (none from this cycle's tasks; T014/T015 are delegated test files, landing separately) — the moved code is `run`'s cgroup_dir/_read_bytes (003 R16) and `snapshot`'s find_workspace (005 FR-1), read before the move (confidence: high)
ASSUMED: `cgroup_value` keeps `_read_bytes`'s contract exactly (int, None for `max`, OSError/ValueError raised), so `run`'s memory_reading is unchanged; the ValueError message says "not a number" (was "not a number of bytes"), which only reaches `run`'s data.reason on a garbage memory file — (confidence: high)
ASSUMED: `cpu_figure` reads cpu.max at TIMELIKE_CGROUP_CPU_MAX, else `cgroup_dir()/cpu.max`; the hook's default is /sys/fs/cgroup/cpu.max. In a container with a private cgroup namespace (Docker's default on v2) `/proc/self/cgroup` is `0::/`, so both read the same file; the e2e agreement cell (T014) checks it in the image — (confidence: medium)
FLAGGED: snapshot keeps a one-line `find_workspace` that calls agentio, rather than replacing its two call sites — chose the thin shim over editing call sites because it keeps 005's names and diff minimal, and its refusal logic (check_workspace) stays in snapshot — (confidence: high)
ABSENT: no direct unit tests for the new agentio functions in this task (test_budget.py, T015, covers them through `timelike budget`, and run/snapshot suites cover the moved paths); `undo` unchanged (it loads snapshot); the hook's bash copy of the CPU rule is not touched
Verification: host, venv python 3.12 + pytest 8.4.2: tests/unit/test_run.py, test_run_slice1.py, test_snapshot.py, test_undo.py, test_agentio.py — 232 passed, unchanged suites; ruff check + format --check over tools: clean; mypy (pyproject config): no issues in 27 source files. Advisory: host, not the image
SCOPE: in (3 changed files)

### T017: `timelike budget`; the announcement's two rule lines; README reference regenerated
**Started:** 2026-10-08T16:32:16Z | **Completed:** 2026-10-08T16:34:17Z | **Coordinator**

INHERITED: T016's agentio readers (cgroup_dir, cgroup_value, cpu_figure, workspace) — (confidence: high)
FLAGGED: `run`'s `size()` moved into agentio (`run` keeps the name as `size = agentio.size`) rather than a fourth copy in `timelike` — the contract names run's format, and edit/snapshot/view keep their own `human()`, which this cycle does not unify — (confidence: high)
FLAGGED: README's generated command reference regenerated here (`scripts/readme_reference.py --write`, one line), not in T021 — CLAUDE.md's standing rule says "in the same cycle" and test_readme_reference.py fails the moment the help moves, so T017 keeps the tree green; T021 keeps the README status decision — (confidence: high)
ASSUMED: the processes line reads "limit no limit" when pids.max is `max`, the contract's literal wording; awkward but exact — (confidence: medium)
ASSUMED: contract wording "JSON `data`" amended to say agentio puts the keys at the top level (no `data` key): found running it, relayed to both test delegates by message — (confidence: high)
ABSENT: no budget for a cgroup v1 host beyond "unknown, file named" (natural intensity); no inode figures (the criterion names free space only); no cut of long paths beyond agentio's column cap
Verification (host, advisory): fake cgroup (300 MiB, 150000/100000, pids max, no memory.peak, affinity 0-3,8,10-11) → 300.0 MiB, 1.50 CPUs, job count 2 agrees with TIMELIKE_CPUS=2, "no limit", peak unknown naming the file, scratch "does not exist yet", verdict "; 1 unknown", exit 0; real host cgroup → no limit / 56 / 154457. pytest: test_announce, test_run, test_run_slice1, test_conform, test_readme_reference — 162 passed after the reference --write; ruff clean; mypy no issues (27 files)
SCOPE: in (4 changed files)

### T018: the command-not-found handler in the hook; missing-commands.tsv; the Dockerfile COPY
**Started:** 2026-10-08T16:35:11Z | **Completed:** 2026-10-08T16:40:02Z | **Coordinator**

INHERITED: research R5's prolog rule (BASH_SOURCE[1] else $0, BASH_LINENO[0], none when interactive) and the contract's line formats — from plan/contract (confidence: high)
FLAGGED: errexit/nounset/xtrace are switched off inside `{ local -; set +o …; } 2>/dev/null`, so a caller's `set -x` does not trace even that first line (the caller's own `+ NAME` trace remains, as without timelike) — chose this over the defaults function's bare `local -; set +o …`, which would leak two trace lines into every typo under -x — (confidence: high)
FLAGGED: the data set (64 rows, 63 names over 75 lines with the header) is limited to names I am confident trixie-slim plus this image's packages do not install; uncertain ones (xz, bzip2, which, ssh, sudo, docker) are left out — ssh and sudo because their answer is policy (stack note 15, R7), not a package the operator should add. The e2e absence cell (T014) is the check — (confidence: medium)
ASSUMED: `fd` and `bat` get `instead` rows only, because Debian ships their binaries as `fdfind` and `batcat` (those names carry the package rows) — (confidence: high)
ASSUMED: the hook's header rule "leaves nothing behind" is amended rather than kept literal: command_not_found_handle is the feature; tests/host/test_shell_env_hook.sh Q2 now allows exactly that function and asserts it is defined — (confidence: high)
ABSENT: no `user` rows (Item 21 open); no handling for a PATH set to the empty string — bash then searches the current directory and never calls the handler (observed on the host); no override of an operator's own handler (none exists in this image)
Measurement (host bash 5.2.21, load ~1.6, 1000 calls in one shell, 3 runs each): with the handler, a listed name with one row (javac) 2843–2886 µs/call, an unknown name (all 64 rows read) 2734–2865 µs/call, tree (two rows) 2694–2846 µs/call; bash alone (no handler) 865–867 µs/call. So about 1.9 ms more per missing command. The subshell is bash's own (it forks for a not-found command either way); the handler adds none (the hook's no-fork probe F1 passes)
Verification (host, advisory): byte-for-byte equal to bash for an unknown name in `bash -c` (line 2), a script with the name inside a function (`d/t.sh: line 3`), interactive `bash -i`; tree and jq print the contract's lines; `set -eux` caller: no handler trace, exit 127. tests/host/test_shell_env_hook.sh 44/44, tests/host/test_env_layer.sh 60/60; shellcheck clean on the hook and the test
SCOPE: in (4 changed files)

### T018 (follow-up): two handler defects the T015 delegate's host test found
**Started:** 2026-10-08T16:40:31Z | **Completed:** 2026-10-08T16:41:15Z | **Coordinator**

INHERITED: T018's handler; the delegate's report on tests/host/test_command_not_found.sh (30 of 33 at first) — (confidence: high)
ASSUMED: interactive bash prints argv0's base name (`/usr/bin/bash` → `bash:`; `-bash` stays `-bash:`), confirmed here on host bash before the fix; the handler now prints `${0##*/}` when interactive. Non-interactive keeps $0 as given (bash prints `/bin/bash: line 1:` for an absolute argv0, observed in T018) — (confidence: high)
ASSUMED: a directory at the data path is "unreadable" (line 1 alone), not an error; `-f` is tested beside `-r`, so bash's `read: read error … Is a directory` no longer leaks — (confidence: high)
ABSENT: the contract's two rows are corrected (interactive base name; a directory means line 1 alone) — no other format changed
Verification (host, advisory): tests/host/test_command_not_found.sh 33/33 (A interactive-path ×2 and D2 now pass), tests/host/test_shell_env_hook.sh 44/44
SCOPE: in (1 changed files)

### T015: units (test_budget.py, test_missing_commands.py) and the host handler test, from the contract
**Started:** 2026-10-08T16:27Z (delegate launched, before T016) | **Completed:** 2026-10-08T16:42:44Z | **Delegate (general-purpose), reviewed and committed by the coordinator**

INHERITED: the contract § Slice 1 and research R5; the coordinator's message that agentio puts `data` at the top level — (confidence: high)
FLAGGED (delegate): line 1 is never written into the host test; it is captured from the same bash with no handler (P005), so the comparison is against bash itself — (confidence: high)
FLAGGED (delegate): the absolute-path interactive case is a real failure, not a TODO, because FR-15 says byte for byte — it found that interactive bash prints argv0's base name; fixed in T018 (follow-up) — (confidence: medium)
FLAGGED (delegate): interactive cases use --noediting, PS1/PS2 set by the launcher, and filter bash's two job-control lines and the closing `exit` — (confidence: high)
ASSUMED (delegate): free space may differ by up to 256 MiB between the tool's statvfs and the test's; total bytes must match exactly — (confidence: medium)
ASSUMED (delegate): COLUMNS=4000 keeps rule 13 from cutting long temp paths, as test_run_slice1 does — (confidence: high)
FLAGGED: the coordinator added the host test's step to tests/host/run.sh (the delegate was not allowed to edit it), so `make test-host` runs it; run.sh is not named in tasks.md, so the scope record may read out — (confidence: high)
ASSUMED: the delegate's two handler findings (interactive base name; a directory at the data path) were checked on host bash before the fix (T018 follow-up) — (confidence: high)
ABSENT (delegate): `bash -lc` on the host (reads the host's /etc/profile; the e2e covers it); a statvfs failure case (cannot be caused on the host); sh -c and direct exec (e2e only)
ABSENT: the delegate's contract findings settled: no `data` key (contract amended in T017); interactive base name and directory-as-unreadable (contract amended in T018 follow-up); quota/period absent when the CPU limit is not a value (as built: absent); PATH empty never reaches the handler (bash's own behaviour, recorded in T018)
Verification (host, advisory): test_budget.py 73 + test_missing_commands.py 13 = 86 passed against the implementation; tests/host/test_command_not_found.sh 33/33; ruff check/format clean; shellcheck clean (run.sh too)
SCOPE: in (4 changed files)

### T014: e2e for SC-5 and SC-7, from the contract
**Started:** 2026-10-08T16:27Z (delegate launched, before T016) | **Completed:** 2026-10-08T16:43:10Z | **Delegate (general-purpose), reviewed and committed by the coordinator**

INHERITED (delegate): the SC-1 file's test-name shape and setup_file/throwaway pattern, run_in/value_of/assert_*, cpu_list_count, container_tmpdir; the image's python3 -I for JSON; the coordinator's top-level-keys message — (confidence: high)
FLAGGED (delegate): line 1 is checked against bash itself: each cell runs the same string twice in the same style, once with SC5_UNSET=1 (`unset -f command_not_found_handle` on the same line), so the control is bash's own line and interactive job-control notices pass through both — (confidence: high)
FLAGGED (delegate): the direct-exec cell asserts non-zero and docker's not-found text, not 127 — docker's status for a missing exec binary was not verified here (no daemon) — (confidence: medium)
FLAGGED (delegate): the limited throwaway uses --cpus 1.5 as specified; on a 1-CPU host docker refuses it and the cells fail with that reason (never skip) — (confidence: medium)
ASSUMED (delegate): the throwaway's WORKDIR (/home/agent) has no .git at or above it, so its workspace is pwd — (confidence: medium)
ASSUMED (delegate): the omitted note drops the two spaces with the parentheses — matches the implementation and the host test — (confidence: high)
ASSUMED: review found the file's JSON and text runs use separate not-yet-existing scratch roots because agentio's event creates the root after the first run (delegate finding, true by design: rule 10's scratch is created on first use) — (confidence: high)
FLAGGED: one shellcheck warning (SC2034, ELAPSED_S read by helpers' asserts) annotated by the coordinator — (confidence: high)
ABSENT (delegate): not run — no Docker daemon or bats here; bash -n on @test-stripped copies only. The image lane is the evidence. ABSENT: spec FR-14 says a direct exec "exits 127 as before"; the cell asserts non-zero, which is what the lane can establish without a docker-version assumption
Verification: shellcheck -x -P tests/e2e:tests/host clean on both files (coordinator, venv shellcheck-py); read in full by the coordinator against the contract and helpers.bash (exec_in/_shell_argv support ic; start_throwaway passes the limits; paths stay under the 200-column cut)
SCOPE: in (2 changed files)

### T019: SC-1 carried items — cell names to revision 13's text; the 1 s bound becomes an ordering
**Started:** 2026-10-08T16:43:27Z | **Completed:** 2026-10-08T16:44:02Z | **Coordinator**

INHERITED: spec § Slice 1 carried items (declared in Cycle 3's spec commit); the send's "Carried into this cycle" — (confidence: high)
FLAGGED: the 1 s bound is replaced, not re-measured another way — host load decided it (readme-b 11225 ms fail, readme-c pass); the ordering it stood for is already established by the file's process-table wait (every read happens after the entrypoint exec'd `sleep infinity`), so the cell keeps that, keeps "placed by this start" (first file ≥ StartedAt − 1000 ms clock tolerance, and the image itself holds none), and prints the time to fd 3 as a measurement — (confidence: high)
ASSUMED: the six cell names take revision 13's criterion text exactly (the struck clause removed from the name, the strike explained in the header), and the two workspace cells say "the workspace is left untouched: no CLAUDE.md or AGENTS.md is created there"; their assertions are unchanged — (confidence: high)
ABSENT: no change to what the cells assert beyond the removed `last >= 1000` failure; the header's struck-criterion account replaces the "NOT BUILT (D-1)" paragraph; no other 007 e2e file changes
Verification: shellcheck clean; @test names counted (6 renamed, 2 workspace names replaced). Not run: no Docker here; the mentor's lane runs it
SCOPE: in (1 changed files)

### T021: README — the generated reference is current; the README status block is NOT applied (SC-6 held)
**Started:** 2026-10-08T17:01:13Z | **Completed:** 2026-10-08T17:01:13Z | **Coordinator**

INHERITED: T017 regenerated the command reference (`timelike budget`'s usage line); `scripts/readme_reference.py --check` passes now — (confidence: high)
FLAGGED: the send's `## README status` block (row 04 `complete (0, 1)`, "16 of 38") is **not applied**: the send says to apply it "only if all four slice-1 criteria are met", and SC-6 (installs) is held on FOR-MENTOR Item 21 (spec D-11). README.md's What and Status stay as they are — (confidence: high)
ABSENT: no hand edit of the generated block; no value claim (P6); if Item 21 is answered and SC-6 is built in this cycle, the block is applied then
Verification: `python3 scripts/readme_reference.py --check` exit 0; tests/unit/test_readme_reference.py passed in T020's host lane
SCOPE: none — no files outside the feature's artifacts changed

### T020: host verification (advisory); implement step 10 recorded in metrics.json
**Started:** 2026-10-08T16:44:26Z | **Completed:** 2026-10-08T17:03:35Z | **Coordinator**

INHERITED: T014-T019 and T021 (T021 was committed before this record: it changes no README content, only records the status-block decision) — (confidence: high)
ASSUMED: `make test-host` with the scratch venv (python 3.12.3, pytest 8.4.2) is the host lane of record; it now runs tests/host/test_command_not_found.sh (T015) — (confidence: high)
FLAGGED: the coverage TOTAL (59%) is not recorded as a project figure — this cycle's rc mapped the bench's temp `bin/` copies under the `bin` alias, not reboot.md's separate `benchbin`, so `timelike-bench` copies were counted unmapped; the per-file figures for the four changed files are unaffected and are what is recorded — (confidence: high)
ABSENT: no host e2e stand-in run (SC-7 needs throwaway containers with limits, which a stand-in cannot give; SC-5's cells read /etc/timelike from the container) — the mentor's Docker lane is the evidence; no host conformance sweep over every tool (test_conform.py covers timelike, whose help changed; run and snapshot gained no flag)
Verification (host, advisory): make test-host passed — 1747 units, 60/60 env layer, 44/44 hook, 33/33 handler; traced coverage run 1746 passed + 1 skipped, agentio 95%, run 93%, snapshot 92%, timelike 93%; ruff check/format, mypy (27 files), shellcheck over all shell files: clean. Implement step 10 (2.37.0 blocks): run_tests rc 2, run_coverage unknown, Quality Score unknown, 2 this install / 2 this machine / 2 not applicable, gate UNKNOWN warned; recorded as metrics.json "007-cycle-3", project figures beside it, unscored
SCOPE: in (1 changed files)

### T023: cycle-report.md § Cycle 3; implement steps 10 and 9b recorded
**Started:** 2026-10-08T17:04:49Z | **Completed:** 2026-10-08T17:04:49Z | **Coordinator**

INHERITED: T014–T021; the step-10 output (T020) and the tallies from lib/tally.sh (2.37.0) — (confidence: high)
FLAGGED: every Automated criterion is cited `unconfirmed` with host results beside it as advisory, not `executed` — no image lane has run on this branch, and host evidence is never image evidence (reboot.md § Environment) — (confidence: high)
ASSUMED: SC-6 is cited `unconfirmed: NOT BUILT` rather than omitted, so the mentor's derivation sees it — (confidence: high)
ABSENT: no demo_points_reached; no .implement-complete (not dispatch); T022 stays open (Item 21)
SCOPE: none — no files outside the feature's artifacts changed

### T026: Node pins in pins.env; the agent build args in compose.yaml; the vanilla build args in the Makefile
**Started:** 2026-10-08T17:54:47Z | **Completed:** 2026-10-08T17:54:56Z | **Coordinator**

INHERITED: research R9 (Node 24.21.0 is the newest LTS on nodejs.org/dist/index.json read 2026-10-08; its SHA-256 from SHASUMS256.txt equals the downloaded tarball's) — (confidence: high)
FLAGGED: 24.21.0 over v26.11.1 — 26 is the newest release but `lts: false` on 2026-10-08; the ruling says "current Active LTS" — (confidence: high)
ASSUMED: the Makefile's `include pins.env` + `export` makes NODE_VERSION and NODE_SHA256 reach compose's ${NODE_VERSION:-} interpolation and tests/run.sh (which runs make), as for PYTHON_VERSION — (confidence: high)
ABSENT: no signature check of SHASUMS256.txt (GPG release keys) — the ruling asks for a pinned version and SHA-256, which is what the build checks; bench/driver/Dockerfile unchanged (the driver runs no task)
Verification: grep of pins.env, compose.yaml args, Makefile bench-images (four args added); built in T027/T028
SCOPE: in (3 changed files)

### T027: the agent image's runtimes stage, configuration and PATH; profile.d
**Started:** 2026-10-08T17:55:59Z | **Completed:** 2026-10-08T17:59:28Z | **Coordinator**

INHERITED: T026's pins; research R9's measurements (npmrc in <node>/etc, pip.conf as the prefix's site config, the relocatable pip script) — (confidence: high)
FLAGGED: a separate `runtimes` build stage (pinned base + uv) rather than steps in the final stage — so bench/vanilla/Dockerfile (T028) can run byte-identical steps and the two arms carry the same binaries (D-15); the final stage copies only /opt/agent — (confidence: high)
FLAGGED: the marker is removed in the agent's final stage, not the shared stage, and the stage fails loudly if no marker is found (a uv change would otherwise silently skip the Q3 step) — (confidence: high)
ASSUMED: `ADD <url>` with ARG expansion in the source works in the lane's builder (Docker 29, BuildKit); the checksum is enforced by `sha256sum -c` in the RUN after it, so a builder that ignored anything would still fail on a mismatch — (confidence: medium)
ASSUMED: npm finds /opt/agent/node/etc/npmrc through the /usr/local/bin/npm link because node's execPath is its real path (R9 measured npm through the prefix's own bin; the link path is checked in the lane by T024's cells) — (confidence: medium)
ABSENT: no image build here (no Docker daemon); the stage's shell was replayed on the host under a scratch root with the pinned uv and the verified tarball: checksum OK, node v24.21.0, CPython 3.14.7, prefix left with cpython-…, node and python only, marker removed, pip 26.2.1 and npm 11.19.0 run, npmrc written literally. A tests/unit/test_bench_catalog.py failure seen now (12 setup timeouts at 15 s) also fails at e0fb5a3 under the same load (~9, delegates running): environmental, re-run in T031
Verification: host replay as above; tests/host/test_env_layer.sh 60/60; profile.d sourced under sh from three starting PATHs puts /opt/timelike/bin first and /home/agent/.local/bin second; shellcheck clean
SCOPE: in (2 changed files)

### T028: bench/vanilla/Dockerfile — the same runtimes stage, stock behaviour (002's file)
**Started:** 2026-10-08T17:59:57Z | **Completed:** 2026-10-08T18:00:42Z | **Coordinator**

INHERITED: T027's `runtimes` stage, copied byte for byte (a unit test now compares the two stages); T026's Makefile args — (confidence: high)
FLAGGED: vanilla links the same seven names into /usr/local/bin — chose identical command names in both arms over leaving the prefixes off PATH, because "the same runtime binaries" with different names would make a task find `python3` in one arm only (RB1) — (confidence: medium)
ASSUMED: Debian's default PATH (no ENV in vanilla) includes /usr/local/bin, so the links are found; no ~/.local/bin, so a user install's command would not be — that is stock behaviour — (confidence: high)
ASSUMED: the RUN asserts the marker is present but does not name pip.conf or npmrc: the unit test reads any non-comment mention as configuration, and the e2e cell (T024) checks their absence in the built image — (confidence: high)
ABSENT: no bench catalog change (its "only what both images contain" rule is about tasks' prerequisites; no task uses the runtimes in this slice); 002's spec not modified (02 s1 records it); the driver image unchanged
Verification: tests/unit/test_agent_runtimes.py and test_announce.py 124 passed (with T025's delegate tests, uncommitted at this point); not built here (no Docker)
SCOPE: in (1 changed files)

### T029: missing-commands.tsv — runtime rows out, user rows in; standard-tools.json checked
**Started:** 2026-10-08T18:01:10Z | **Completed:** 2026-10-08T18:01:21Z | **Coordinator**

INHERITED: T027 (the image now ships python3, python, pip, pip3, node, npm, npx); FR-29 — (confidence: high)
FLAGGED: a name the agent can install itself gets the `user` row only, not also its Debian package (pytest's `python3-pytest` row removed) — the answer the agent can act on first (P1); the operator route stays for OS-only tools — (confidence: medium)
ASSUMED: 14 `user` rows (8 pip, 6 npm), each the prefix plus one package token (T025's unit rule); `http` → `pip install httpie`, `tsc` → `npm install -g typescript` (command name differs from the package); none of the names is in the image (the SC-5 e2e absence cell checks it) — (confidence: high)
ABSENT: no change to standard-tools.json — python3 and node keep their REPL risk and `instead`, and `installed` is computed (true now); `uv` not listed (it is on PATH at /bin/uv); no network-dependent check that each package exists on PyPI or npm
Verification: tests/unit/test_missing_commands.py 16 passed, 1 skipped (the pre-ruling "no user rows" check, off by flag)
SCOPE: in (1 changed files)

### T030: scan/scan.sh — its comments say timelike's interpreter, and where the agent runtimes are scanned
**Started:** 2026-10-08T18:01:42Z | **Completed:** 2026-10-08T18:02:02Z | **Coordinator**

INHERITED: FR-30; quality-standards.md's revised scan gate (governance audit, e58dd36) — (confidence: high)
FLAGGED: the pip-audit "no interpreter in image" record is left as written — it already names the exact path it probed (`has no /opt/timelike/python/bin/python3`), so it is true for vanilla, and tests/unit/test_scan_report.py pins its wording; only the comments change — (confidence: high)
ASSUMED: Grype over Syft's SBOM catalogs the CPython and Node binaries, pip in the agent prefix and npm's bundled packages, so no scanner step is added; the lane's scan shows what it finds — (confidence: medium)
ABSENT: no pip-audit over the agent interpreter (its only distribution is pip, which Grype sees); no baseline change (findings unknown until the lane; a no-fix finding is raised, never exempted silently)
Verification: bash -n and shellcheck clean; tests/unit/test_scan_report.py passed
SCOPE: in (1 changed files)

### T025: units for the runtimes, the vanilla Dockerfile and the data (delegate, from the spec)
**Started:** 2026-10-08T17:56Z (delegate launched) | **Completed:** 2026-10-08T18:03:10Z | **Delegate (general-purpose), reviewed and committed by the coordinator**

INHERITED: spec FR-13 (revised), FR-25–FR-29, D-12, D-13; test_env_layer.sh's ENV parse — (confidence: high)
FLAGGED (delegate): the PIP_BREAK_SYSTEM_PACKAGES scan skips full-line `#` comments, so image/Dockerfile's "Never PIP_BREAK_SYSTEM_PACKAGES" note does not fail it; a comment sets nothing, and test_break_system_scan_can_fail proves the pattern matches — (confidence: medium)
ASSUMED (delegate): vanilla links the same seven names; vanilla needle checks skip comments and are case-insensitive — (confidence: medium)
ASSUMED (delegate): a `user` value is the prefix plus one package token; at least one pip and one npm row — (confidence: medium)
ASSUMED (delegate): the npmrc's ${HOME} must reach the file literally (single-quoted in the RUN) — (confidence: high)
FLAGGED: the coordinator added test_the_two_runtimes_stages_are_identical (D-15: the agent and vanilla `runtimes` stages byte-identical), which the vanilla Dockerfile's header claims — (confidence: high)
ABSENT (delegate): root ownership of /opt/agent (e2e territory); the stage name `runtimes` beyond the identity test; the vanilla header's wording
Verification: 141 passed, 1 skipped (tests/unit/test_agent_runtimes.py, test_announce.py, test_missing_commands.py) against T026–T029's files; ruff check and format clean. The delegate checked the tests fail on mutated Dockerfiles (npmrc double-quoted, corepack linked, marker kept, the pre-cycle file)
SCOPE: in (3 changed files)

### T024: e2e for SC-6, and the P6 vanilla cells revised to FR-13 (delegate, from the spec)
**Started:** 2026-10-08T17:56Z (delegate launched) | **Completed:** 2026-10-08T18:03:23Z | **Delegate (general-purpose), reviewed and committed by the coordinator**

INHERITED (delegate): run_in/notty styles, stamp_check, container_tmpdir, the KEY=value + value_of pattern, the vanilla docker run invocation; unique names and versions per cell (nodejs Q001, P004) — (confidence: high)
FLAGGED (delegate): the Python cell fails if pip says "Defaulting to user installation" — without pip.conf pip would still fall back to ~/.local (site-packages unwritable), so location alone cannot prove FR-26's configuration — (confidence: high)
FLAGGED (delegate): the runtime paths must resolve inside the resolved /opt/agent prefixes and never inside the resolved /opt/timelike/python (both are links to uv directories) — (confidence: high)
ASSUMED (delegate): teardown uninstalls the probes (pip uninstall, npm uninstall -g) so cells do not leak onto the shared container's PATH; install calls get RUN_TIMEOUT=120 — (confidence: medium)
ASSUMED (delegate): the "only home changed" find prints any changed path and allow-lists nothing — (confidence: medium)
FLAGGED: the coordinator changed both `npm prefix -g` reads from `2>&1` to `2>/dev/null` (the delegate's flag: an update notice on stderr would break the exact match; the prefix is on stdout, and an error still fails the cell by an empty value); `npm prefix -g` through the /usr/local/bin link was confirmed on the host to report $HOME/.local — (confidence: high)
ABSENT (delegate): no Docker run of either file (no daemon); the host trial ran the in-container scripts with other pip/npm versions
ABSENT (delegate): the vanilla `pip config list` is not checked
Verification: shellcheck -x -P tests/e2e:tests/host clean on both files; read by the coordinator (installs, the home-only find, teardown, the purelib listing)
SCOPE: in (2 changed files)

### T031: host verification (advisory) for Cycle 4
**Started:** 2026-10-08T18:03:41Z | **Completed:** 2026-10-08T18:09:51Z | **Coordinator**

INHERITED: T024–T030; T027's host replay of the runtimes stage (checksum, Node 24.21.0, CPython 3.14.7, prefix contents, marker removed, pip 26.2.1, npm 11.19.0) — (confidence: high)
ASSUMED: the 12 tests/unit/test_bench_catalog.py setup timeouts seen in T027 were host load (about 9, two delegates running): at load about 2–3 they pass in this full run, as they did at e0fb5a3 in Cycle 3's lane — (confidence: high)
ABSENT: no image build or image test (no Docker daemon): every SC-6 and P6 cell, and the scan over the two new runtimes, wait for the mentor's lane. No coverage run this cycle: no Python source under tools/ changed in Cycle 4
Verification (host, advisory): make test-host passed — 1825 passed and 1 skipped units (load 2.0–2.6), env layer 60/60, hook 44/44, handler 33/33; ruff check/format (77 files), mypy (27 files), shellcheck over every shell file: clean; README reference current; npm prefix -g through a /usr/local/bin link reports $HOME/.local
SCOPE: none — no files outside the feature's artifacts changed

### T032: README — the send's README status block; the vanilla description
**Started:** 2026-10-08T18:10:09Z | **Completed:** 2026-10-08T18:10:30Z | **Coordinator**

INHERITED: all four slice-1 criteria built (SC-5, SC-7 in Cycle 3; SC-6 in T024–T029); the send applies the block "only if all four slice-1 criteria are met (the Manual one may be unconfirmed)" — (confidence: medium)
FLAGGED: applied now, on built-and-host-verified, before the image lane — the README's Status counts built slices, and the lane decides the merge; if a lane failure leaves a criterion unmet, these rows revert in that fix's cycle — (confidence: medium)
ASSUMED: row 04's "What it does" names `timelike budget` by its real name; the Status paragraph is the send's text verbatim; the vanilla bullet becomes "the same agent runtimes (Python and Node) with their stock behaviour"; "The vanilla bench image gets none of this (P6)" (§ announcements) stays true and is unchanged — (confidence: high)
ABSENT: no value claim (P6); no other README change; the generated reference unchanged (no help moved this cycle)
Verification: scripts/readme_reference.py --check current; tests/unit/test_readme_reference.py passed
SCOPE: in (1 changed files)

### T033: provenance (audited_against [1, 13, 14], scoped); cycle-report § Cycle 4; steps 10 and 9b; reboot.md for a clear
**Started:** 2026-10-08T18:10:53Z | **Completed:** 2026-10-08T18:12:51Z | **Coordinator**

INHERITED: T024–T032; the installed audit-append block; lib/tally.sh (2.37.0) — (confidence: high)
FLAGGED: scoped, not full — revision 14 rewords a constraint and the Feature text, so full (UNVERIFIED=13 14) appends 2–12 and leaves out 14 (verified); scoped appends 14 alone, which this cycle checked and built — (confidence: high)
FLAGGED: T022 closed here, not ticked — superseded by Phase 7 (T024–T033), which built what it held; scope_tally counts it unrecorded, as the cycle report says — (confidence: high)
ASSUMED: every Automated criterion cited unconfirmed with host results labelled advisory; D4 kept "observed by the operator"; D13 unconfirmed — (confidence: high)
ABSENT: no demo_points_reached; no .implement-complete (not dispatch); prompt_revision, discovery_revision and source_prompt untouched; no commit after the cycle is reported done (send rule)
SCOPE: in (2 changed files)

### T034: SC-5 direct-exec cell reads both streams (lane 007s1-a, item 1)
**Started:** 2026-10-08T20:00:22Z | **Completed:** 2026-10-08T20:00:49Z | **Coordinator**

INHERITED: the mentor's measurement on the lane host (Docker 29.4.2): `docker exec <agent> tree </dev/null` exits 127, 0 bytes on stderr, the OCI not-found message on stdout; Cycle 3's not_verified named this premise — (confidence: high)
ASSUMED: docker's choice of stream is not the criterion's subject, so the cell reads stdout and stderr together; non-zero, `tree`, "not found" and no timelike line (on either stream, as before) are kept — (confidence: high)
ABSENT: no change to FR-14 or the handler; exit code still asserted non-zero, not 127 (126 on older releases)
Verification (host, advisory): the cell's three functions, run under bats 1.14.0 against a stub docker — message on stdout: ok; on stderr: ok; a timelike line: not ok; exit 0: not ok; an unrelated daemon error: not ok
SCOPE: in (1 changed files)

### T035: 001's broken-interpreter conformance cell, its premise restored (lane 007s1-a, item 2)
**Started:** 2026-10-08T20:01:54Z | **Completed:** 2026-10-08T20:02:24Z | **Coordinator**

INHERITED: lane 007s1-a not ok 108/109 — revision 14 put the agent's python3 on PATH (/usr/local/bin), so the `#!/usr/bin/env python3` fixture ran and C6 had nothing to find; the other 12 findings were correct — (confidence: high)
FLAGGED: the PATH route, not a renamed interpreter — the fixture stays the everyday `#!/usr/bin/env python3` it was written as; the cell drops every PATH entry holding an executable python3 and fails with "premise:" (exit 3) if python3 still resolves. Applied in the shared check, so the two timelike-nointerp cells (absolute interpreter path) run the same way, unaffected. 001's test, so changed_other_features — (confidence: high)
ASSUMED: timelike-conform and the shipped tools need nothing from /usr/local/bin or ~/.local/bin (they name /opt/timelike/python, H5; /opt/timelike/bin, /usr/bin and /bin stay) — (confidence: high)
ABSENT: the cell is not deleted, C1 and C6 are still asserted, and the shipped tools are still judged and must pass
Verification (host, advisory): the generated command run under env -i in a scratch layout — a PATH dir holding python3 is dropped, `/usr/bin/env python3` then exits 127; the stub conform sees no python3
SCOPE: in (2 changed files)

### T036: two reviewed baseline entries for the findings with no fix (lane 007s1-a, item 3, second half)
**Started:** 2026-10-08T20:03:15Z | **Completed:** 2026-10-08T20:04:02Z | **Coordinator**

INHERITED: the mentor's ruling under quality-standards' baseline rule — GHSA-ch52-4w7c-c8xp (npm's bundled http-cache-semantics 4.2.0) and CVE-2026-77214 (libexpat1 2.8.3-1~deb13u1, via git) into both baselines, with reason, layer and the neighbours' review date — (confidence: high)
ASSUMED: the gate files the npm finding under a new origin, "files under /opt/agent" (evaluate.py names non-deb artifacts by their first two path parts), so that origin gets a reason in each baseline; CVE-2026-77214 sits under the existing "git" origin, whose reason already names expat's WebDAV-only use. Each entry also carries its own reason, since both are new and individually reviewed — (confidence: high)
ASSUMED: reviewed 2026-10-01 and review_by 2026-12-27 left unchanged ("the same review date as their neighbours"); a review note records who added them and on whose ruling — (confidence: high)
ABSENT: none of the seven fixable findings is baselined (the gate would block them anyway: a baselined finding with a fix still blocks)
Verification (host, advisory): evaluate.py report over lane 007s1-a's own scan output with the new baselines — agent: 85 baselined, 7 blocking; vanilla: 84 baselined, 7 blocking; the 7 are exactly the fixable npm findings. tests/unit/test_scan_baseline.py and test_scan_report.py: 112 passed
SCOPE: in (2 changed files)

### T037: pip-audit over the agent interpreter, a result line of its own (lane 007s1-a, item 4)
**Started:** 2026-10-08T20:05:44Z | **Completed:** 2026-10-08T20:09:36Z | **Coordinator**

INHERITED: the mentor's reading of lane 007s1-a's scan — pip-audit ran over /opt/timelike/python only, and recorded "no interpreter" for vanilla, which now carries /opt/agent/python; quality-standards (13 → 14) says the scan covers the runtimes — (confidence: high)
FLAGGED: extended pip-audit rather than judging Grype sufficient — pip-audit reads PyPI's advisory service (PYSEC/OSV) for the exact versions, which Grype's database may lag; the cost is one more network step per image that carries the runtime — (confidence: high)
FLAGGED: the audit runs over a pinned list, not --path — the scanned image's own agent interpreter lists its distributions (evaluate.py dists --requirements, no network), and the AGENT image's uv runs pip-audit -r that list with --no-deps --disable-pip (nothing resolved or installed), because vanilla has no /bin/uv. The same pattern as the verdict, which already runs on the agent image. pip-audit 2.10.1 checked on the host: the flags exist and the JSON has the same shape — (confidence: high)
ASSUMED: step name pip-audit-agent, its own row in steps.tsv and verdict.json, its findings attributed to it (pip_audit_vulns takes the step name); the report's step column widened from 13 to 17 so the name fits — (confidence: high)
ASSUMED: quality-standards amended (dated note, not a discovery revision; governance_audited_against unchanged) and the scan.sh header and image list say what each pip-audit covers — (confidence: high)
ABSENT: no change to the gate rule, the baselines, or step 3 (timelike's interpreter)
Verification (host, advisory): tests/unit/test_scan_report.py and test_scan_baseline.py 116 passed (new: the agent finding blocks on its own row while pip-audit passes, its skip note, a missing record fails, dists --requirements writes exact pins, and the four-image scan under the fake docker: agent and vanilla audited from the agent image with -r/--no-deps/--disable-pip, Adele and the bench driver none); ruff check and format, mypy (27 files), shellcheck scan/scan.sh: clean. The real run is lane 007s1-b's
SCOPE: in (4 changed files)

### T038: npm pinned at 11.21.0 in both runtimes stages (lane 007s1-a, item 3, first half)
**Started:** 2026-10-08T20:13:29Z | **Completed:** 2026-10-08T20:22:29Z | **Coordinator**

INHERITED: the mentor's ruling — fix, never baseline; a newer Node if one carries the fixes, else npm itself pinned by version and registry integrity in both images; never patch inside npm's tree — (confidence: high)
FLAGGED: no route fixes all seven. No Node 24.x newer than 24.21.0 (nodejs.org index, 20:10Z); npm 11.20.0, 11.21.0 and 12.2.0 all bundle brace-expansion 5.0.9 and undici 6.28.0. Put to the operator; the mentor chose option 1 (npm 11.21.0) and routed the other three (GHSA-6j4f-fj2g-mc7p, GHSA-qhr7-859c-m2p7, GHSA-rfgv-xxqx-mfg5) to plan as bridge/feedback/04-20261008-201205-fix-available-for-npm-bundled-libraries.md — (confidence: high)
ASSUMED: NPM_SHA512 is the registry's dist.integrity re-encoded as hex, so the build checks it with sha512sum -c as it checks Node with sha256sum -c; the npm directory is removed and the package unpacked whole; the build checks npm --version. The two runtimes stages stay byte-identical — (confidence: high)
ABSENT: no package inside npm's tree is touched; no baseline entry for any fixable finding; the three remaining findings are not raised on FOR-MENTOR (the mentor routed them)
Verification (host, advisory): the integrity (sha512-Zov8…) decodes to the tarball's sha512sum; the RUN's Node and npm lines replayed verbatim under a scratch root with the real Node 24.21.0 tarball: checksum OK, npm 11.21.0, npm and npx links resolve, tarballs removed; a tampered tarball is refused. npm's tree then holds brace-expansion 5.0.9, ip-address 10.5.0, tar 7.5.22, undici 6.28.0, http-cache-semantics 4.2.0, with no nested copies — GHSA-mwp4, GHSA-r292, GHSA-mh99 and GHSA-rgw5 should clear, and three should remain. make test-host: 1838 passed, 1 skipped; env 60/60, hook 44/44, handler 33/33; ruff, mypy, shellcheck clean
SCOPE: in (6 changed files)

### T039: governance audit, discovery 14 → 15 (constitution 1.4.3, tech-stack 1.5.0, quality-standards)
**Started:** 2026-10-08T20:26:34Z | **Completed:** 2026-10-08T20:27:27Z | **Coordinator**

INHERITED: ../bridge/governance-context.md at revision 15 (regovern 2026-10-08T20:17:29Z), its "What Changed In Those Revisions" (one clarification paragraph under "Fix available"; stack.md's Agent runtimes row), and plan's ruling in bridge/feedback/04-20261008-201205-fix-available-for-npm-bundled-libraries.md § Resolution — (confidence: high)
FLAGGED: constitution amended, not a no-change audit — H9 restates revision 5's "fix available" word for word, so it gains the clarification (PATCH 1.4.2 → 1.4.3, a clarification under the versioning rule), with a Sync Impact Report — (confidence: high)
ASSUMED: tech-stack 1.4.0 → 1.5.0 (MINOR: an addition, npm's own pin and constraint, and an npm line so the parser reads it as approved, which the plan's classification asked for); quality-standards states the bundled class, the 30-day entry review, the release check (fails closed) and npm/pip's constraints, with a dated audit note — (confidence: high)
ABSENT: no threshold moved; the 90-day review for the rest of the baseline is unchanged; P1–P7, T1–T4 and H1–H8 checked, unchanged; no governance file is touched outside these three
Verification: tech-stack-parser loads 1.5.0 with nothing unparsed and classifies npm APPROVED; each file's governance_audited_against reads [2..15]
SCOPE: in (3 changed files)

### T040: tests first for the release check (FR-34; cross-stack P005)
**Started:** 2026-10-08T20:27:33Z | **Completed:** 2026-10-08T20:29:33Z | **Coordinator**

INHERITED: T039's quality-standards text (the bundled class, the 30-day entry review, the release check that fails closed); plan § Cycle 5 and research R10 (candidates bounded by the fix date; tarballs checked by integrity) — (confidence: high)
FLAGGED: written by the coordinator, not a delegate — the API they pin (releases subcommand, judge's releases argument, engines_admit, the entry's bundled object) is new in this cycle and the tests are its specification; P005 holds because every registry, tarball, version and integrity is built by the test, never chosen by the code under test — (confidence: high)
ASSUMED: file:// URLs stand in for the registry (urllib reads them; no server, no network); the unreachable case is a registry directory that does not exist — (confidence: high)
ABSENT: no test reaches the real registry (T044 runs that from the host, advisory); 38 tests fail until T041 (expected: tests first)
Verification: ruff check and format clean; pytest: 38 failed, as expected before T041
SCOPE: in (1 changed files)

### T041: evaluate.py — bundled-class entries, the releases subcommand, and the verdict's use of it (FR-32, FR-33)
**Started:** 2026-10-08T20:30:00Z | **Completed:** 2026-10-08T20:33:58Z | **Coordinator**

INHERITED: T040's tests (the API they pin); T039's quality-standards text; research R10 (candidates bounded by the fix date, tarballs checked by integrity, every copy of the library counted) — (confidence: high)
FLAGGED: a bundled-class entry is judged before the "stable fix blocks" rule, because under revision 15 the scanner's upstream fix is not "fix available" for it — but only that entry's finding, and only on the release check's no-release answer for the same fixed version; a missing, stale or unknown answer blocks (fails closed) — (confidence: high)
FLAGGED: the entry is held to the image and the scanner: a library version other than the one recorded, or a fixed version other than the scanner's lowest stable fix, blocks with "re-review the entry", so an npm bump or a new advisory cannot ride an old review — (confidence: high)
FLAGGED: generic over the component by a table — npm is read; pip answers unknown with what its reader would need (PyPI JSON for releases admitting the agent interpreter, each wheel's pip/_vendor/vendor.txt), so a pip entry blocks until then — (confidence: high)
ASSUMED: the engines reader handles ||, comparators, ^, ~, x-ranges and hyphen ranges, and raises on anything else (pre-release tags included), which makes the check unknown; deprecated and pre-release npm versions never count; a release that no longer bundles the library counts as shipping the fix; urllib reads https:// and file:// only — (confidence: high)
ASSUMED: release-check joins STEPS as its own row (between pip-audit-agent and govulncheck); propose() carries a bundled entry whole (its review is a person's) — (confidence: high)
ABSENT: no assert (S101): types narrowed by passing the Bundled explicitly; single file kept (scan.sh runs it with -I); the network is used only by releases, never by report; tests/unit/test_scan_report.py's scan.sh cells fail until T042 adds the step to scan.sh
Verification (host, advisory): test_scan_release_check.py 38 passed; ruff check and format, mypy (27 files) clean
SCOPE: in (1 changed files)

### T042: scan.sh — the release-check step per image; test_scan_report.py follows
**Started:** 2026-10-08T20:34:04Z | **Completed:** 2026-10-08T20:34:14Z | **Coordinator**

INHERITED: T041's releases subcommand (prints "<n> <summary>", writes release-check.json) and the release-check row in STEPS — (confidence: high)
FLAGGED: the check runs from the AGENT image's timelike interpreter, like the verdict, with network on (the registry is the point), against the scanned image's baseline read from /scan; no baseline or no bundled entries is "none"; a run that fails is "error", never "nothing to check" (H3), and the verdict then blocks every bundled entry — (confidence: high)
ASSUMED: the step's detail is the subcommand's summary, so the scan's output says what was checked (entries, Node, releases examined, states), as the send asks — (confidence: high)
ABSENT: scan.sh passes no --registry (the default, https://registry.npmjs.org); the fake docker runs the real subcommand, so the scan cell uses a pip-component entry that answers without a registry; npm's path is tested against the file-served registry (T040)
Verification (host, advisory): test_scan_report.py, test_scan_release_check.py, test_scan_baseline.py 153 passed (new: the four images' release-check rows, and a scan.sh run with a bundled entry: from the agent image, no --network flag, NODE_VERSION passed, "1 bundled-class entries checked … 1 unknown"); shellcheck scan/scan.sh clean
SCOPE: in (2 changed files)

### T043: three bundled-class entries in both baselines (revision 15)
**Started:** 2026-10-08T20:34:20Z | **Completed:** 2026-10-08T20:35:29Z | **Coordinator**

INHERITED: T041's entry shape (bundled object; its own reviewed/review_by, 30 days at most); T038's npm 11.21.0, whose tree holds brace-expansion 5.0.9 and undici 6.28.0 (host replay); T036's "files under /opt/agent" origin reason — (confidence: high)
FLAGGED: each entry records the fixed version the scanner gives for THAT advisory (GHSA-6j4f-fj2g-mc7p 5.0.10, GHSA-qhr7-859c-m2p7 5.0.11, GHSA-rfgv-xxqx-mfg5 6.28.1, from lane 007s1-a's grype), not one version per library: the send's summary gave brace-expansion 5.0.11 for both, and the gate holds each entry to the scanner's lowest stable fix. Dates read from the registry (brace-expansion 5.0.10 and 5.0.11 both 2026-09-14; undici 6.28.1 2026-09-04) — (confidence: high)
ASSUMED: reviewed 2026-10-08 (the day plan ratified revision 15), review_by 2026-11-07 (30 days); the baseline's own dates unchanged; a review note says who added them, on whose ruling, and that the mentor reviews them at sign-off — (confidence: high)
ABSENT: none of these is an ordinary entry (they would block: the scanner reports a fix); no other entry changed
Verification (host, advisory): both baselines load with no problems and 3 bundled entries each; evaluate.py releases against the real registry from the host, with these baselines: 3 no-release per image, releases examined 11.20.0, 11.21.0, 12.1.0, 12.2.0, about 3 s each; a live negative (a fixed version npm already ships) answers fix-released 11.19.1
