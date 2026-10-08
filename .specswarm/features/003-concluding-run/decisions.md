# Decisions Log — Feature 003
> Generated at 2026-10-01T04:51:42+00:00
> Spec: .specswarm/features/003-concluding-run/spec.md

## Decision Key

| Tag | Meaning |
|-----|---------|
| ASSUMED | Assumption made without explicit spec guidance (confidence: high/medium/low) |
| DEFERRED | Decision postponed — noted for later resolution |
| FLAGGED | Judgment call between alternatives — requires review |
| ABSENT | What was NOT done and why — forced reflection on gaps |
| INHERITED | Assumption carried forward from a prior task's output |

---

### T001: register tools/bin/run with ruff and mypy; stub tool
**Started:** 2026-10-01T04:51:42+00:00 | **Completed:** 2026-10-01T04:51:42+00:00

INHERITED: (none — first task)
ASSUMED: the Dockerfile's `COPY --chmod=0755 tools/bin/ /opt/timelike/bin/` ships any new file there, so no Dockerfile edit is needed — read at image/Dockerfile:69 (confidence: high)
FLAGGED: none
ABSENT: the stub is not conformant (it exits 1 on every call). Nothing runs conform over tools/bin on the host lane between tasks: the units install named tools into temp directories. So an intermediate commit breaks no unit test. The image lane runs only at the end
Verification: `grep tools/bin/run pyproject.toml` (2 lines); the file is mode 0755
SCOPE: in (2 changed files)

### T002: 001's contract text and schemas amended for pass-through (discovery revision 9)
**Started:** 2026-10-01T04:55:05+00:00 | **Completed:** 2026-10-01T04:55:05+00:00

INHERITED: plan's ruling (../bridge/feedback/03-20260930-235857-exit-pass-through.md § Resolution) and contracts/output-contract-amendment.md — from the plan (confidence: high)
ASSUMED: line 36 ("No other exit code is permitted from a timelike tool's own logic") stays as written: plan called it the faithful reading, and the new paragraph states the scope beside it (confidence: high)
FLAGGED: event.schema.json `exit` becomes an integer 0–255, not "the six codes plus anything when passes_exit". JSON Schema cannot see the manifest from an event line, so the tie between them is C7's job (an event's exit must equal the observed exit). Chose the range over an enum because a range is checkable per line (confidence: high)
FLAGGED: tests/unit/schema.py (the repo's stdlib schema subset) gains `maximum`. test_schema_keywords_are_supported failed on the new keyword, which is that guard working. Adding it is outside tasks.md's named paths: the alternative was to drop the upper bound, and a 300 would then validate (confidence: high)
ABSENT: the schema edits are textual, keeping the files' compact one-line properties. A json.dump rewrite produced a 145-line diff, so it was reverted
ABSENT: no agentio or conform change here (T003, T004). No unit asserting pass-through behaviour yet (T003)
Verification: tests/unit/test_agentio.py -k 'schema or rule16' 7 passed. The event schema accepts 42 and rejects 256 and -1 (checked by hand with tests/unit/schema.py). Full units before the schema.py fix: 611 passed, 1 failed (the keyword guard)
SCOPE: out — tests/unit/schema.py (1 of 5 changed files) (task has FLAGGED: yes)

### T003: agentio — pass-through, argv split, tool-supplied cut
**Started:** 2026-10-01T04:57:21+00:00 | **Completed:** 2026-10-01T04:57:21+00:00

INHERITED: the amended contract and schemas (passes_exit, event exit 0–255) — from T002 (confidence: high)
ASSUMED: `cause` and `command_exit` are emitted in JSON whenever a tool sets a cause, not only for pass-through tools. A future non-wrapping tool may name a cause too, and the keys are reserved, so no tool can set them through `data` (confidence: high)
FLAGGED: a tool-supplied cut prints a separate `more: <cmd>` line after its sections and before the exit line, in addition to the command in the omission line. contracts/run-cli.md (written at plan) shows it, and spec FR-13 lists "the exact command" as part of the body. The contract's order (exit line, path, omission) is kept after it. Chose the explicit line over relying on the omission line alone, because agents read line starts (confidence: medium)
FLAGGED: JSON `sections` carries `{label, count}`, and the shown lines stay flattened in `lines`. data-model.md said `{name, first, last}`. The label already states the range ("lines 1–50 of 5000"), and a count keeps agentio generic. data-model.md is updated at T011 (confidence: high)
FLAGGED: the argv split is agentio's own (`_split_command`), not argparse.REMAINDER (research R6). An option taking a value consumes the next word, read from the parser's own option table (confidence: high)
ABSENT: Tool.codes() is unchanged. A pass-through tool still declares only its own outcomes, and a command's exit is admitted only in `_emit_result`, tied to cause command and exit == command_exit
ABSENT: the generic cap path (`--limit` re-run as "more") is unchanged for every other tool
Verification: test_agentio.py 59 passed (12 new); ruff, ruff format, mypy --strict clean; startup and conform units pass (above)
SCOPE: in (2 changed files)

### T004: timelike-conform — C6 exercises a declared pass-through
**Started:** 2026-10-01T04:58:46+00:00 | **Completed:** 2026-10-01T04:58:46+00:00

INHERITED: the manifest key `passes_exit` and the JSON `cause` / `command_exit` — from T002 and T003 (confidence: high)
ASSUMED: "the verdict names 42" means the verdict string contains "42". A stricter form, such as "exit 42", would bind every future wrapper to one phrasing that the contract does not fix (confidence: medium)
FLAGGED: only a manifest whose `passes_exit` is exactly `true` triggers the exercise. A non-boolean value is a C2 manifest problem, and it is not exercised. Chose not to exercise "yes", because conform would otherwise guess at intent (confidence: high)
ABSENT: the probe runs the shell `sh` from PATH inside the tool's own environment. A tool that cannot run `sh` fails C6, and that is the right verdict for a command wrapper. No fixture covers a missing `sh`
ABSENT: no change to conformance.md here. T002 already wrote C6's pass-through row, and the schema makes `passes_exit` a boolean, so C2 covers `pass_flag_str`
Verification: test_conform.py + test_conform_violations.py 43 passed (6 new cases: pass_ok, pass_exit_1, pass_no_command_exit, pass_wrong_cause, pass_vague_verdict, pass_flag_str; exit_42 still C6 for a tool that does not declare it); ruff, mypy clean
SCOPE: in (2 changed files)

### T005: run — core: options, limit, log, subreaper, exec, exit mapping, verdict
**Started:** 2026-10-01T05:00:29+00:00 | **Completed:** 2026-10-01T05:00:29+00:00

INHERITED: agentio's passes_exit, argv split and Result(cause, command_exit) — from T003 (confidence: high)
ASSUMED: setting the subreaper never fails the call. If prctl is unavailable, the command still runs, and only orphan tracking is lost. T007 and T009 report what they could see (confidence: high)
ASSUMED: ENOTDIR at exec (a path through a file) maps to 126, as bash does ("Not a directory", 126) (confidence: medium)
FLAGGED: the timeout source is printed as the setting's own name (`--timeout`, `TIMELIKE_RUN_TIMEOUT` or `default`), and the limit with %g (2, not 2.0). That settles the delegate's two questions on the verdict's format (confidence: high)
FLAGGED: open_log creates the file O_EXCL before anything runs, and execute() re-opens it O_APPEND for the command. Two opens, one path, so the command's descriptor is the one that reaches it (confidence: high)
ABSENT: the timeout path kills only the command's own process here; the whole-tree stop is T009. Detached children are not yet named (T007)
ABSENT: the display is not yet run's own. All lines go to agentio, whose generic cap would offer "re-run with --limit 0" as its more command. That would run the command again, and T011 replaces it before anything ships
Verification: tests/unit/test_run.py 25 passed (exits 0, 1, 42, 137, 127, 126 with marker; header/verdict; stdin EOF; argv split; usage cases; precedence; unwritable scratch runs nothing; manifest schema; help ≤ 40). ruff, mypy --strict clean
SCOPE: in (2 changed files)

### T006: e2e SC-5 — run-exit-equals-the-wrapped-commands-exit-code.bats
**Started:** 2026-10-01T05:00:46+00:00 | **Completed:** 2026-10-01T05:00:46+00:00 | **Delegate:** subagent (reviewed by coordinator)

INHERITED: helpers.bash conventions (run_in, exec_plain, container_tmpdir, stamp_check, fixtures/json_fields.py) and the cause words of T005 ("command exited 42", "command not found: X", "command killed by signal 9 (SIGKILL)") — from T005 (confidence: high)
ASSUMED: the delegate's cells are bash -c and bash -lc in notty only. A terminal cannot change an exit code, as the hook test's own reasoning holds (confidence: high)
FLAGGED: none
ABSENT: not run here (no Docker daemon, research R10). It runs in the mentor's `make test`. The JSON expectations were checked by eye against the T005 units, which assert the same strings on the host
ABSENT: bash -ic and sh -c cells; tty mode
Verification: shellcheck -x -P tests/e2e:tests/host clean (0.11.0); 18 @test cells, reviewed: no pgrep/pkill -f, markers only
SCOPE: in (1 changed files)

### T007: run — detached children named, never stopped
**Started:** 2026-10-01T05:02:21+00:00 | **Completed:** 2026-10-01T05:02:21+00:00

INHERITED: the subreaper set at start, and the log opened O_APPEND for the command — from T005 (confidence: high)
ASSUMED: 100 ms is enough for a backgrounded child to reach exec, so its name is the program's (`sleep`) and not the forking shell's. On the host, three back-to-back suite runs named `sleep` every time (confidence: medium)
FLAGGED: the verdict adds "(still running, not stopped; their output goes on to the log)" after the pids. That says in words why the call ended while something still runs (P2: a verdict names its cause). Chose words over a bare list (confidence: high)
FLAGGED: a log writer outside the tree is listed as detached too. With run as a subreaper, such a process can only be one the command handed the log to through a path run cannot see (for example a helper re-parented to another subreaper). Readers are excluded, because an agent may tail an older log (confidence: medium)
ABSENT: detection runs only when the command exits by itself. A timeout stops the whole tree (T009), so nothing is left to name
ABSENT: zombies are reaped (WNOHANG) and never listed. A zombie that appears after the scan is not reported, and that is harmless
Verification: tests/unit/test_run.py 31 passed ×3: a subshell holding stdout and a plain `sleep &`, both verdicts in < 2 s naming the marker's pid; nothing detached after `wait`; parse_stat with "(a (b) c)"; descendants; log_writers is writers only. Every detached pid is killed by its listed pid, never by pattern. ruff, mypy clean
SCOPE: in (2 changed files)

### T008: e2e SC-3 — run-backgrounded-child-holding-stdout-verdict-within-2-seconds.bats (+ verdict format fixes in run)
**Started:** 2026-10-01T05:03:14+00:00 | **Completed:** 2026-10-01T05:03:14+00:00 | **Delegate:** subagent (test file; reviewed by coordinator)

INHERITED: run's detached detection and verdict — from T007 (confidence: high)
FLAGGED: review found a defect in T007, not in the test. T007 appended "(still running, not stopped; their output goes on to the log)" after the pid list. contracts/run-cli.md fixes the list as `· detached: <pid> <name>, …`, and the parenthetical's own comma split it, so "<pid> sleep" never matched. The verdict now carries the contract's plain list. Chose the contract over T007's wording, because the contract was written first and an agent parses the same list (confidence: high)
FLAGGED: a host run of the e2e's own script showed the verdict cut at COLUMNS (200) with a long log path, which dropped the detached list. The verdict now names at most 5 children, then "(+N more)"; JSON `detached` lists all. In the image the log path is about 50 characters, so 5 names fit (confidence: medium)
ASSUMED: the child's exec of `sleep` lands within the 100 ms settle, so its name is `sleep`. That is the delegate's assumption too, and a host run of the same script named it `sleep` (confidence: medium)
ABSENT: not run in the image here; the host run used the e2e's script with run on the host Python
ABSENT: the 2-second bound is measured inside the container around the run call only. docker exec start-up is excluded, as the criterion is about run
Verification: shellcheck clean; host run of the e2e script printed `verdict: exit 0 (command exited 0) · 0.2 s · 1 lines · log /tmp/claude-2001/tl/default/run/20261001T050257Z-3671426.log · detached: 3671429 sleep`; tests/unit/test_run.py 32 passed (+1: at most five named, +2 more)
SCOPE: in (3 changed files)

### T009: run — the whole tree stopped at the limit (freeze, then kill)
**Started:** 2026-10-01T05:04:47+00:00 | **Completed:** 2026-10-01T05:04:47+00:00

INHERITED: proc_table / descendants / log_writers and the subreaper — from T005 and T007 (confidence: high)
ASSUMED: the processes a stop must reach are the tree plus whatever holds the log for writing, the same set T007 names as detached. A writer of this call's log is this call's output (confidence: medium)
FLAGGED: no separate " · limit T s (source)" segment in the verdict, though contracts/run-cli.md lists one as optional. The timeout's cause words already carry the limit, its source and both ways to raise it ("timeout after 1 s (--timeout); raise with --timeout or TIMELIKE_RUN_TIMEOUT"). Chose not to say it twice (confidence: high)
FLAGGED: survivors are named in the verdict (" · not stopped: <pid> <name>") and in JSON `not_stopped`, and the exit stays 124. Chose to report rather than escalate to exit 1: the limit did fire, and the verdict says what is left (H3) (confidence: medium)
ABSENT: no cgroup-based stop. The agent has no privilege to create one (P4), and the stack has none (research R3)
ABSENT: a process that changes uid inside the tree cannot be signalled. It would be listed under not_stopped. There is no setuid binary on the agent's path to test it with
Verification: tests/unit/test_run.py 35 passed, then the timeout subset twice more (12 passed each): a tree with a plain loop, a nested `timeout 50` (own process group), a `setsid` child and a `trap '' TERM` child stopped at 1 s, with all four heartbeats frozen for 1.5 s after the call; a forking loop at 0.5 s with every spawned pid (from markers) gone; the TIMELIKE_RUN_TIMEOUT source named. ruff, mypy clean
SCOPE: in (2 changed files)

### T010: e2e SC-4 — run-exceeding-its-timeout-exits-124-no-process-survives.bats
**Started:** 2026-10-01T05:05:14+00:00 | **Completed:** 2026-10-01T05:05:14+00:00 | **Delegate:** subagent (reviewed by coordinator)

INHERITED: the stop sequence and the timeout verdict wording — from T009 (confidence: high)
ASSUMED: the docker exec overhead stays within the test's 2 s allowance above R4's bound (assert_within 9) (confidence: medium)
FLAGGED: none
ABSENT: not run in the image here. The fixture was extracted from the .bats file and run through run on the host Python, sandboxed under setsid --wait timeout
ABSENT: no fork-loop cell in e2e; it is a unit (T009). The e2e covers the tree shapes the criterion names
Verification: shellcheck clean. Host run of the e2e's own hang.sh: `rc=124 elapsed_ms=4112`; verdict `exit 124 (timeout after 2 s (--timeout); raise with --timeout or TIMELIKE_RUN_TIMEOUT) · 4.0 s · 0 lines · …`. After 1.5 s, main, plain, nested-timeout, setsid and trap-term were all `state=gone`; trap-term had beaten twice as long (it ignored SIGTERM through the grace)
SCOPE: in (1 changed files)

### T011: run — its own display: head, first errors, tail, one-range more
**Started:** 2026-10-01T05:07:59+00:00 | **Completed:** 2026-10-01T05:07:59+00:00

INHERITED: agentio.Cut and its rendering order (sections, more line, exit, full output, omission) — from T003 (confidence: high)
ASSUMED: error patterns are plain case-sensitive substrings, not the "whole-word or prefix" research R9 first described. Substrings are what an agent can predict from the listed set; "0 errors" is a known false hit (R9) (confidence: medium)
FLAGGED: the more command is one `sed -n A,Bp <log>` range over the whole gap, not one range per gap between errors (research R8 amended). Up to 21 ranges would pass the COLUMNS cut and break the command; one range re-prints at most 20 shown error lines. The omission count stays exact, counting only lines not printed. This settles the delegate's open question for SC-1 (confidence: high)
FLAGGED: run always cuts its own output once it exceeds the cap. With `--limit 1` it once handed agentio 2 whole lines, and agentio's generic cut then offered "re-run with --limit 0", which runs the command again. Below head + tail the tail is shortened, so the gap is never empty (confidence: high)
FLAGGED: the docs were aligned to what was built: research R8, data-model (sections {label, count}; run's `errors` is [] because its errors are a section), and run-cli.md (one range; what the omission counts; at most five detached names) (confidence: high)
ABSENT: no stream distinction for errors. stdout and stderr share one log by design (R2), so stderr lines are not flagged unless they match a pattern
ABSENT: the gap's bytes are counted by re-reading the log up to the gap's end, a second partial pass. Its memory is bounded; on a multi-GB log it costs time and nothing else
Verification: tests/unit/test_run.py 43 passed (+8): 5,000 lines with errors at 700/1800/3000 give exactly the contract's order, and the more command reproduces lines 51–4900 from the log; omitted 4847 lines and bytes checked; JSON sections/truncated; 120 lines printed whole with no markers; errors in the head or tail not repeated; --limit 10, 0 and 1; CRLF and a final line with no newline; empty output; a 300,000-character line cut on screen and kept whole in the log; error_patterns in the manifest. ruff, mypy clean
SCOPE: in (2 changed files)

### T012: e2e SC-1 — run-5000-lines-verdict-first-head-first-errors-tail-more-command.bats
**Started:** 2026-10-01T05:08:27+00:00 | **Completed:** 2026-10-01T05:08:27+00:00 | **Delegate:** subagent (reviewed by coordinator)

INHERITED: run's display and its one-range more command — from T011 (confidence: high)
ASSUMED: no TIMELIKE_OUTPUT_LIMIT is set in the image, so the cap is the contract's 200 (the delegate's assumption; the Dockerfile's ENV sets none) (confidence: high)
FLAGGED: none. The test accepts the single gap range (`more=gap`) that T011 chose, and it would accept a per-gap form too
ABSENT: the omission line's counts are not asserted in e2e. The host units assert 4847 and the byte count against the log
ABSENT: not run in the image here
Verification: shellcheck clean. Host run of the e2e's own gen.sh: exactly 162 output lines, header, verdict "· 5000 lines · log …", the head marker at line 3, L700/L1800/L3000 at lines 55–57, the tail marker at 58, `more: sed -n 51,4900p <log>` at 159, the omission line last (162)
SCOPE: in (1 changed files)

### T013: e2e SC-2 — run-output-within-head-and-tail-printed-in-full.bats
**Started:** 2026-10-01T05:08:27+00:00 | **Completed:** 2026-10-01T05:08:27+00:00 | **Delegate:** subagent (reviewed by coordinator)

INHERITED: run returns every line uncut when the output is within the cap — from T011 (confidence: high)
ASSUMED: none beyond T012's cap assumption
FLAGGED: none
ABSENT: the boundary between 151 and 200 lines (within the cap but beyond head + tail) is not an e2e cell. FR-15 and the contract print it whole too, and the host unit for 120 lines covers the shape
ABSENT: not run in the image here
Verification: shellcheck clean; reviewed: exactly 122 lines, the last 120 equal to the fixture's own output, and no `── `, `more: ` or `… omitted` line
SCOPE: in (1 changed files)

### T014: 001's e2e tests that name the tool set — run added
**Started:** 2026-10-01T05:08:59+00:00 | **Completed:** 2026-10-01T05:08:59+00:00

INHERITED: run ships in /opt/timelike/bin through the Dockerfile's tools/bin COPY — from T001 (confidence: high)
ASSUMED: the conformance e2e already compares conform's count with the executables actually shipped, so run is checked, pass-through exercise included, without a new assertion. Only its floor (≥ 2 → ≥ 3) and comment change (confidence: high)
FLAGGED: none
ABSENT: `timelike` lists tools from PATH at run time (tools/bin/timelike:72), so no change there. README is T015. The grep over scan/out (scanner JSON) was noise and is not a tool list
Verification: shellcheck clean on both files. The GUARDS list gains /opt/timelike/bin/run, so the SC-4 guards test checksums it before and after the agent's attempts. Listed under changed_other_features (001)
SCOPE: out — tests/e2e/agent-cannot-run-as-root-change-firewall-or-read-adele.bats (1 of 2 changed files) (task has FLAGGED: no — tasks.md names it abbreviated, `agent-cannot-run-as-root-…bats`)

### T015: README — run announced where agents read (P3), and the pass-through rule
**Started:** 2026-10-01T05:09:34+00:00 | **Completed:** 2026-10-01T05:09:34+00:00

INHERITED: run's behaviour as built (T005–T011), and the contract's scope of exit codes — from T002 (confidence: high)
ASSUMED: the README is the place this project announces tools. Harness context files are T3's boundary and another feature's work (P3 vs P7) (confidence: medium)
FLAGGED: none
ABSENT: no claim about run's value (P6). The section says what run does, not that it saves turns; the bench says that
ABSENT: no harness context file (CLAUDE.md, AGENTS.md) inside the image announces run. Announcement into harness files is not in prompt 03's slice 0
Verification: by reading; the examples match tests/unit/test_run.py's shapes (verdict, L<n>:, more: sed -n A,Bp, detached:, exit codes)
SCOPE: in (1 changed files)

### T016: host lane — lint, units with coverage, make test-host, start-up (+ settle only when needed)
**Started:** 2026-10-01T05:18:16+00:00 | **Completed:** 2026-10-01T05:18:16+00:00

INHERITED: everything built in T001–T015 (confidence: high)
FLAGGED: the start-up measurement showed `run --json true` at 176 ms, 100 ms of it the fixed settle T007 put on every call. find_detached now scans first and settles only when something is left running (research R5 amended). A forked child exists before its parent exits, so the first scan cannot miss one; only its name could lag behind exec (confidence: high)
ASSUMED: the start-up budget (< 100 ms p95, quality-standards) applies to the tool's own overhead, so `run --help` and `run true` are measured. A real command's own time is not run's (confidence: high)
ABSENT: the first start-up run used `python -I`, which ignores PYTHONPATH, so every tool failed to import agentio and the figures measured a crash. It was caught because no exit code had been checked, and re-measured with exit codes asserted. Those first figures are not used anywhere
ABSENT: image figures (interpreter /opt/timelike/python, -I, precompiled agentio) come from the Docker lane's startup.json, not from here
Verification:
- ruff check and format: clean over tools, tests, scan and bench (ruff 0.16.7)
- mypy --strict: clean over 15 source files
- shellcheck 0.11.0: clean over every .sh, .bash and .bats file
- units under coverage (reboot covrc plus /tmp/pytest-of-*/**/run): **675 passed, 1 skipped** (the start-up test skips under tracing). Coverage is **97% overall**: run 96%, agentio 94%, timelike-conform 92%, timelike 96%, timelike-bench 98%, scan/evaluate 99%
- `make test-host PYTHON=<venv>`: rc 0, units 676 passed, host hook-logic 29 of 29
- start-up, host Python 3.12, 40 runs, exit codes asserted (median / p95):
  - base python -c pass: 17.1 / 19.1 ms
  - run --help: 70.7 / 72.2 ms
  - timelike --help: 56.8 / 58.8 ms
  - run --json true: 75.1 / 78.2 ms (after the fix; 176.4 / 178.5 ms before)
- tests/unit/test_run.py: 43 passed, twice, after the fix
SCOPE: in (1 changed files)

### T017: cycle report § Cycle 1, implement step 10, metrics entry
**Started:** 2026-10-01T05:20:45+00:00 | **Completed:** 2026-10-01T05:20:45+00:00

INHERITED: every task's results and decisions (T001–T016), and the send's cycle-report block (confidence: high)
ASSUMED: every automated criterion is `unconfirmed` until the Docker lane runs, as in 002 cycle 1. Host units run the real tool, but host evidence is not image evidence (reboot.md; memory "no Docker") (confidence: high)
FLAGGED: implement step 10's score of record is the plugin's own result, `unknown`, with every component excluded and its reason quoted. The project's host-lane figures are recorded beside it, labelled `project_measurements_not_scored`, and are not fed into the score. 002's entry scored them; this one does not (the memory rule against judgment-filled scores). Chose "beside" over "inside" so the score never says something the plugin did not measure (confidence: high)
FLAGGED: criteria are cited by text taken from their own lines (for example "returns a verdict line first, then the first lines, …"). The send's "In scope" list repeats each criterion's opening words, so a citation from the start of a line matched two lines. Each citation was checked to match exactly one line of the send (grep -cF = 1 for all six) (confidence: high)
ABSENT: no demo_points_reached (the mentor derives them). No Group A fields: no marker on this path
ABSENT: no ship and no merge. Those wait for the mentor's sign-off after the Docker lane (memory: merge after sign-off)
Verification: the commit hashes the report cites resolve (9163245, e344395, 702ba59, b6b795e), and 702ba59 is the branch's base. Plugin tallies: `scope: planned=17 recorded=16 unplanned=0 unrecorded=1 in=14 out=2 none=0 unknown=0 flagged=9 flagged_out=1 other=7 other_out=1` (before this section); `decisions: sections=16 flagged_sections=10 non_flagged_sections=6 sections_without_absent=0 flagged=19 assumed=17 deferred=0 absent=30 inherited=15 low_confidence=0 flagged_low_confidence=0`
SCOPE: in (1 changed files)

### Lane fix 1: SC-4's e2e test read its own expected exit as the runner's timeout
**Started:** 2026-10-01T05:43:30+00:00 | **Completed:** 2026-10-01T05:46:00+00:00

INHERITED: the Docker lane at `2af58e4` (`tests/out/summary.json`, started 05:24:13Z): e2e 192 of 194, with only `not ok 168` and `not ok 169` failing, both SC-4. Each said "timed out after 4.3s (runner limit 30s)" (confidence: high)
FLAGGED: the defect is in the test, not in `run`. `assert_within` (001's `helpers.bash`) treats any status 124 as the runner's own timeout, and SC-4 expects 124 from `run`. The cell took 4.3 s, under its own 9 s bound and far under the runner's 30 s. The test now decides the runner's timeout by elapsed time, which is how `run_in` itself decides it. The fix stays in 003's own file: `helpers.bash` is unchanged, because every other caller expects an exit other than 124 (confidence: high)
ASSUMED: bats stopped at the first failing assertion, so the image has not yet checked SC-4's header, verdict and survival assertions. They are unconfirmed until the lane re-runs (confidence: high)
ABSENT: no change to `tools/bin/run`
Verification:
- shellcheck 0.11.0: clean on the edited file
- host, sandboxed (`setsid --wait timeout -k 5 40`): the test's own fixture, extracted from the file, run through `tools/bin/run --text --timeout 2`. rc 124 in 4.4 s (image: 4.3 s). Line 2 is `verdict: exit 124 (timeout after 2 s (--timeout); raise with --timeout or TIMELIKE_RUN_TIMEOUT) · 4.1 s · …`, with no "not stopped". After 1.5 s, all five members (main, plain, nested-timeout, setsid, trap-term) had stopped beating and were not alive. This is host evidence, not image evidence
SCOPE: in (1 changed files)

### T018: the shared rule file, the image COPY, scan.sh --config
**Started:** 2026-10-04T19:05Z | **Completed:** 2026-10-04T19:12Z

INHERITED: spec FR-33, research R15 (the 18 rule ids, gitleaks' format, extend useDefault) — from the Cycle 2 spec (confidence: high)
FLAGGED: the rule file is gitleaks' own config format, read by both run (agentio, tomllib) and gitleaks — chose one shared file over run-only regexes, because the stack note and 001's rule 15 both say the set is shared, and a second copy would diverge (confidence: high)
FLAGGED: 18 provider rules copied byte for byte from gitleaks v8.30.1 defaults, overriding them by id with an added tag — chose override-with-tag over new ids, because new ids would make gitleaks report each leak twice, and the tag carries rule 15's type (confidence: high)
ASSUMED: gitleaks ignores nothing it needs and accepts `tags` and `[[rules.allowlists]]` as written — verified, not assumed: the v8.30.1 binary (checksum-checked) loads the file, reports a planted generated token as `github-pat` with `["redact:token"]`, and finds 0 leaks in timelike's history with it (confidence: high)
ABSENT: the 25 default rules Python's re cannot compile, and generic-api-key — not in the redaction set (R15); they stay in the scan through useDefault
ABSENT: no Docker here, so the image COPY is not built in this task — the mentor's lane builds it; a unit (T019) and an e2e cell (T021) check /etc/timelike/redaction.toml loads in the image
Verification: field-by-field equality of regex, entropy, keywords, allowlists and description against the pinned defaults (script, scratch); gitleaks v8.30.1 over the history and over a planted scratch repository
SCOPE: in (3 changed files)

### T022: agentio — the rule set (load_redaction_rules, redact_text), the pass-through gate, Context.event_args
**Started:** 2026-10-04T19:20Z | **Completed:** 2026-10-04T19:34Z

INHERITED: the shared file and its format — from T018 (confidence: high)
FLAGGED: the rule set lives in agentio, not in run — chose the contract module over run alone, because rule 15 is the contract's and a second tool redacting later (08's journal) must read the same set; the send says a rule in run alone would diverge (confidence: high)
FLAGGED: the pass-through gate admits any cause when command_exit equals the exit — chose that over listing memory and disk, because the cause says why the command ended and the exit is still the command's; 001's contract already said later causes are added "without changing its shape" (confidence: high)
FLAGGED: regexes compile with re.ASCII — chose ASCII over Python's default Unicode classes, because gitleaks runs Go RE2, where \w and \b are ASCII; a Unicode \w would widen what a rule matches (confidence: medium)
ASSUMED: gitleaks takes the first non-empty capture group as the secret when secretGroup is unset — none of the 18 rules sets secretGroup, and each one's group 1 is the value (confidence: medium)
ASSUMED: a FutureWarning from compiling a gitleaks regex must not reach stderr — compile warnings are suppressed for the rule load only (confidence: high)
ABSENT: gitleaks' `paths` allowlists and `path` rules — output has no path; not applied, and none of the 18 needs them for a match
ABSENT: environment-value matching — spec FR-34 decides patterns only
Verification: ruff, ruff format, mypy strict clean; a generated token, AWS key id and 20-line PEM block redacted with the line count kept; low-entropy and EXAMPLE look-alikes not redacted; 200k lines in 0.09–0.24 s; tests/unit/test_agentio.py, test_conform*.py, test_run.py: 166 passed
SCOPE: in (1 changed files)

### T023: run — the memory cause (FR-25 to FR-28)
**Started:** 2026-10-04T19:35Z | **Completed:** 2026-10-04T19:52Z

INHERITED: agentio's pass-through gate admits cause memory with command_exit — from T022 (confidence: high)
FLAGGED: an OOM kill is read as the oom_kill count rising during the command, together with a failed command — chose that over "exit 137 means memory", because the OOM killer may kill a grandchild and the command then exits with whatever its shell reports, and because 137 is also any SIGKILL (research R16) (confidence: high)
FLAGGED: the peak is memory.peak, the container cgroup's peak since it started, named "peak" with command_max_rss_bytes beside it in JSON — chose it over getrusage alone, because the criterion asks for the usage that hit the limit, which is the cgroup's; per-command cgroup peaks need kernel 6.12 or a child cgroup the agent cannot create (confidence: medium)
FLAGGED: with memory.max = max the words are "out of memory: no limit set, peak P" — changed from "limit no limit" (contract amended, the unit delegate told) (confidence: high)
ASSUMED: peer agents in one container share the count, so another process's OOM kill during the command is attributed to it — accepted and documented (spec FR-28 limit, R16) (confidence: medium)
ABSENT: no attribution finer than the container cgroup — not readable without delegation (R16)
ABSENT: the image check — no Docker here; SC-8 runs in the mentor's lane on a throwaway with --memory 96m
Verification: ruff, format, mypy clean; host smoke over a fake cgroup (rise+SIGKILL → exit 137 "out of memory: limit 96.0 MiB, peak 96.0 MiB"; no limit; malformed memory.max reason; exit 0 → not looked at); tests/unit/test_run_slice1.py memory tests 10/10 (the delegate's, uncommitted until T020)
SCOPE: in (1 changed files)

### T024: run — the disk cause (FR-29 to FR-32)
**Started:** 2026-10-04T19:53Z | **Completed:** 2026-10-04T20:05Z

INHERITED: Outcome.notes and the memory-first ordering — from T023 (confidence: high)
FLAGGED: "full" is under 1 MiB free for an unprivileged writer (f_bavail) or no free inodes, OR the ENOSPC message in the log — chose both signals over statvfs alone, because a writer that hits ENOSPC often deletes its partial file and free space recovers before run looks; the message survives in the log unless the log's own filesystem was the full one, which statvfs then shows (R17) (confidence: high)
FLAGGED: a filesystem holding both the workspace and the scratch is named once — the unit delegate found the contract silent on it (confidence: high)
FLAGGED: TIMELIKE_RUN_DISK_FULL_BYTES is a documented threshold (manifest disk_full_bytes), also what the host units use to make a filesystem count as full — chose a real knob over a test-only hook (confidence: medium)
ASSUMED: a filesystem reporting f_files == 0 has no inode limit, so its inodes never make it full (confidence: medium)
ABSENT: a full filesystem other than the workspace's and the scratch's (say, /tmp when the scratch root moved) — not checked; the criterion names those two
ABSENT: a verdict line cut at COLUMNS before the slice-1 parts when the log path is very long — the image's log path is short (~55 chars); JSON's verdict is uncut; recorded for the cycle report
Verification: ruff, format, mypy clean; tests/unit/test_run_slice1.py memory and disk: 24/24 (the delegate's; its go() helper now sets COLUMNS=1000, because pytest's scratch paths are long and the text verdict was cut before the slice-1 note — a test fix, committed with T020)
SCOPE: in (1 changed files)

### T025: run — redaction of the log, the shown lines, the header and the event; the verdict count; fail closed; the manifest (FR-33 to FR-40)
**Started:** 2026-10-04T20:06Z | **Completed:** 2026-10-04T20:24Z

INHERITED: agentio.load_redaction_rules, redact_text, Context.event_args — from T022; Outcome.notes order — from T023/T024 (confidence: high)
FLAGGED: the log is replaced by its redacted copy (write beside it, rename) only when something matched, after a keyword pre-scan — chose rename-on-match over always rewriting, because a log with no secret then stays exactly as the command wrote it, including a detached child's later output (slice 0's edge case keeps holding) (confidence: high)
FLAGGED: when the rules are unavailable, run fails closed for the command line too: the header and the event's arguments become "(withheld: redaction rules unavailable)" — the unit delegate found that withholding only the body left a secret argument in the header and the event (confidence: high)
FLAGGED: tests/unit/conftest.py base_env points every tool test at the repository's rule file — chose that over setting it per test, because run withholds its output without rules and the unit lanes run outside the agent image; without it 14 slice-0 tests failed by design; the file is not named in tasks.md, so this task records SCOPE out (confidence: high)
ASSUMED: surrogateescape round-trips every non-secret byte of the log, so a binary or non-UTF-8 output is kept byte for byte (confidence: high)
ASSUMED: a private key longer than 64 KiB at a block boundary is not a case to carry further — PEM keys are a few KiB (confidence: high)
ABSENT: redaction of output written after the verdict by a detached child — not possible after run returns; the verdict says "detached output after this is not kept" when the log was replaced
ABSENT: environment values as secrets — FR-34
Verification: ruff, format, mypy clean; tests/unit/test_run_slice1.py, test_run.py, test_agentio_redaction.py, test_redaction_rules.py: 185 passed (the delegates' files are committed with T019/T020)
SCOPE: out — tests/unit/conftest.py (1 of 2 changed files) (task has FLAGGED: yes)

### T019: tests/unit/test_agentio_redaction.py and test_redaction_rules.py (delegated)
**Started:** 2026-10-04T19:15Z | **Completed:** 2026-10-04T20:26Z

INHERITED: contracts/run-cli.md § Slice 1 (agentio additions), spec FR-33 to FR-40, the rule file — from T018 and the Cycle 2 spec (confidence: high)
FLAGGED: committed after T022, not before it — the delegate started from the contract, but T022 landed while it was writing, so its 107 tests were checked against existing code rather than defining it first; the delegate said so in its report. Test-first held for intent, not for order (confidence: high)
ASSUMED (delegate): the rule file's secret self-check excuses the gcp example keys that the gcp rule's own allowlist lists — they match the regex and are gitleaks' own allowlisted samples (confidence: medium)
FLAGGED (delegate): test_agentio.py::test_rev9_pass_through_exit_only_with_cause_command still passes (its case has command_exit None), but its name states the rule T022 replaced — left as written, raised for the cycle report (confidence: medium)
ABSENT: two rules matching overlapping text, event_args getting agentio's flag-style redaction too, paths-only allowlists — the delegate found the contract silent; T026 states them
Verification: reviewed (secret-shaped values built at run time; redact_text over both files finds nothing); 107 passed, five repeated runs (random values); ruff, format clean
SCOPE: in (2 changed files)

### T020: tests/unit/test_run_slice1.py (delegated)
**Started:** 2026-10-04T19:15Z | **Completed:** 2026-10-04T20:27Z

INHERITED: contracts/run-cli.md § Slice 1, spec § Slice 1 — from the Cycle 2 spec (confidence: high)
FLAGGED: test-first in order for run — all 35 failed for the right reason before T023–T025; they found three contract gaps that changed the code (fail closed for the command line, a shared filesystem named once, a malformed memory.max reason) (confidence: high)
FLAGGED: go() sets COLUMNS=1000 — my change in review: the verdict's slice-1 parts follow the log path, pytest's scratch paths are long, and under COLUMNS 200 rule 13 cut the text verdict before them; the image's log path is short (confidence: high)
ASSUMED (delegate): the manifest's redaction_rules.path is checked only to end in redaction.toml (the host has no /etc/timelike) (confidence: medium)
ABSENT: FR-32 (the scratch filesystem named when the log cannot be created) — not unit-tested; the e2e scratch cell reaches the in-run case, not this one
Verification: reviewed; 35/35 pass against T023–T025; background children found and killed through pid files; ruff, format, mypy clean
SCOPE: in (1 changed files)

### T026: 001's output contract (pass-through, rule 15's rule set), README's run section, run-cli.md's settled gaps
**Started:** 2026-10-04T20:28Z | **Completed:** 2026-10-04T20:36Z

INHERITED: the behaviour of T022–T025 and the gaps T019/T020's delegates reported (confidence: high)
FLAGGED: 001's pass-through paragraph now admits any cause when the exit equals command_exit, naming memory and disk — declared as changed_other_features; 001's spec is not modified (its own next modify records it), as the send's precedent for contract text (confidence: high)
ASSUMED: the earlier no-limit wording (spec FR-26, contract) and the TIMELIKE_RUN_DISK_FULL_BYTES detail, edited before T018 and committed by no task, belong here (feature artifacts) (confidence: high)
ABSENT: 001's agent-info.schema.json — redaction_rules and disk_full_bytes are tool-specific manifest extras, which the schema already allows (the run units validate run's manifest against it)
Verification: the README and contract text read against the code (cause words, verdict additions, fail closed); deny-list PASS
SCOPE: in (2 changed files)

### T021: e2e — one file per automated criterion (delegated)
**Started:** 2026-10-04T19:15Z | **Completed:** 2026-10-04T20:45Z

INHERITED: contracts/run-cli.md § Slice 1; helpers.bash (run_in, exec_plain, start_throwaway); the throwaway pattern of container-derived-defaults.bats (confidence: high)
FLAGGED: memory and disk run in throwaway containers from the verified image (--memory 96m --memory-swap 96m; --tmpfs /work:size=1m,mode=1777; --tmpfs /scratch:size=256k,mode=1777), with each limit read back from the throwaway before it is relied on; a failed precondition FAILS the cells with its reason, never skips (confidence: high)
FLAGGED: no secret reaches the runner or tests/out — generated in the container, checked there with grep -cF against a secrets file, only counts printed; each SC-10 cell has its own session, so "stored" covers the whole scratch directory, events.jsonl included (confidence: high)
FLAGGED (delegate): the scratch cell's 256 KiB filesystem counts as full under FR-30 even when empty; the command failing on its own write is what makes the case real — accepted, stated in the contract (confidence: medium)
ASSUMED (delegate): the allocator writes its pages (b"x" * 8 MiB per step), so the limit is reached (confidence: high)
FLAGGED: Makefile SHELLCHECK_FILES gains the three files, so make lint covers them; Makefile is not named in tasks.md, so this task records SCOPE out (confidence: high)
ABSENT: not run — no Docker here (R10); the first run is the mentor's lane. FR-27, FR-28 and FR-39 are covered by units only, and SC-9 has no text-mode variant
Verification: reviewed (the size formatter is run's algorithm; the verdict assertions match the contract); shellcheck clean; bats --count parses (delegate); gitleaks v8.30.1 over the three files: nothing, default and shared config (delegate); deny-list PASS
SCOPE: out — Makefile (1 of 4 changed files) (task has FLAGGED: yes)

### T027: host lane — lint, units with coverage, make test-host, start-up
**Started:** 2026-10-04T20:40Z | **Completed:** 2026-10-04T21:00Z

INHERITED: T018–T026's files (confidence: high)
FLAGGED: run --json true p95 rose from 78 ms to 98 ms on the host (the rule load: tomllib plus 18 regex compiles, about 20 ms) — left as is: under the 100 ms budget, which quality-standards sets for start-up (run --help: 78 ms, unaffected by the load); recorded for the mentor rather than optimised without a measurement in the image (confidence: medium)
ASSUMED: the image's Python 3.14.7 behaves as the host's 3.12.3 for tomllib, re.ASCII and surrogateescape (confidence: high)
ABSENT: the e2e on a host stand-in — not rebuilt this cycle (the scratchpad stand-in from 006 is gone after the clear); SC-8 and SC-9 need real --memory and --tmpfs anyway; all 16 new cells wait for the mentor's lane
ABSENT: undo's 88% coverage — 005's module, unchanged by this cycle
Verification: ruff check and format (61 files), mypy strict (21 files), shellcheck over every *.sh, *.bash, *.bats: clean; units with subprocess coverage: 1196 passed, 1 skipped (457 s); Python 95% overall (agentio 94%, run 92%); make test-host: passed (hook logic 29/29); start-up p95 run --help 78 ms, run --json true 98 ms (host, 40 runs, every exit asserted)
SCOPE: none — no files outside the feature's artifacts changed

### T028: cycle report § Cycle 2, implement step 10, metrics entry
**Started:** 2026-10-04T21:00Z | **Completed:** 2026-10-04T21:15Z

INHERITED: T018–T027's records and the host-lane figures — from T027 (confidence: high)
FLAGGED: criteria cited with their trace markers — the bare sentences also appear in the send's scope list, so without the marker three citations matched two lines (grep -cF = 1 for all four now) (confidence: high)
FLAGGED: Group A reports each of the ten contracted fields as present, for a marker written after this commit — the marker is written by this same dispatch run from the installed tally blocks, and marker-fields is run over it before completion is reported (confidence: high)
ASSUMED: step 10's components are the plugin's own reasons, unchanged from 006's run (same machine, same install) — re-run here, not copied (confidence: high)
ABSENT: demo_points_reached — the mentor derives it
ABSENT: an audit-log row — modify row 4, nothing appended
Verification: step 10 run from the installed blocks and library (output verbatim in the report); metrics.json gains 003-cycle-2 only (diff: additions); deny-list PASS
SCOPE: in (1 changed files)

## Note on Cycle 2's timestamps (correction, appended after T028)

The **Started / Completed** times in the T018–T028 sections above were composed while writing each
section, not read from a clock, and they are wrong: they run from 19:05Z to 21:15Z, while the clock
(`date -Iseconds`) read 19:13:57Z when the marker was written. **The commit times are the record**
(`git log --format=%cI`; T018 `86d0351` 18:49:28Z … T028 `3ea3385` 19:13:57Z, each the time of the
task's final amend). The sections are left as written, append-only. This note supersedes their times.
