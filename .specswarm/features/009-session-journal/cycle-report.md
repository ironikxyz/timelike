# Cycle report — 009 session journal (prompt 08)

> Append-only. One `## Cycle N — <send>` section per send built to acceptance; later verification goes in
> `### … addendum` sections. The mentor reads this file and never writes into it.

## Cycle 1 — bridge/sends/08-rev1-20261004-183704.md

**Written:** 2026-10-05. **Dispatch mode**, batch `20261004-183704`, prompt 5 of 8. **specswarm
4.0.1-botbaubble.2.35.0** (`4ff8dcb`), the version this session loaded: the expanded `/specswarm:specify`,
`/specswarm:plan`, `/specswarm:tasks` and `/specswarm:implement` named that cache path (lore Q002). The path
is the one the send names, so there is no second report.

**Built under discovery revision 13's rulings** (code-track § Resume after pause-06). Group B copies the
send's `discovery_revision: 12`. Nothing in 08 is confirmed under rule 9, since the journal changes nothing.

**Sequence:**
1. `git checkout -b 009-session-journal 008-edit` (at `2bf0818`).
2. `/specswarm:specify "08 session journal" --from-send bridge/sends/08-rev1-20261004-183704.md --dispatch`
   (`f225ef6`).
3. `/specswarm:plan` (`51195b1`).
4. `/specswarm:tasks` (`5be2885`).
5. `/specswarm:implement --dispatch`.

Each command was invoked, and each block was run from the installed file. Not `/specswarm:build`.
**Pushed nothing; merged nothing.**

**specify's allocation:**
- **Directory:** `009-session-journal`, from the branch. **D84 held**: specify said it took the branch's
  slug over the description's (`08-session-journal`).
- **PARENT_ROUTE:** `default` (`master`). The batch's real parent is `008-edit`; the batch merges nothing.
- **`FEATURE_DIR`:** `.specswarm/features/009-session-journal` for plan, tasks and implement
  (`fnum_resolve`, `find_feature_dir`).

**The `$ARGUMENTS` expansion:**
- **specify's argument string** was `"08 session journal" --from-send bridge/sends/08-rev1-20261004-183704.md --dispatch`.
  The expansion pasted it into double quotes: `DESCRIPTION=""08 session journal" --from-send …"`. **The stray
  quotes were in the description, not a path.** Run from the installed file with `ARGUMENTS` as a variable,
  the blocks gave `PROMPT_VIA=from-send`, `DISPATCH_MODE=true`, and `DESCRIPTION="08 session journal"` with
  the quotes kept.
- **implement's** expansion again replaced awk's `$0` with `--dispatch`.

**Status in one line:** `journal` prints a session's timeline:
- tool calls with their pointers;
- `bash -c` / `bash -lc` commands with their exits, captured by an EXIT trap from 001's hook;
- grant uses, with Adele's ledger merged when the operator pipes it in.

It is ordered, linked, bounded to the last 20, separable by agent and session, and redacted. Units, lint,
the host lane and the host stand-in pass, apart from the stand-in's known gaps. **Nothing has run in the
image.**

### Group A — cited from `.implement-complete`

The marker is `.specswarm/features/009-session-journal/.implement-complete`, written at the end of this run,
after this section's commit. No measured number is copied here.

| Field | In the marker |
|---|---|
| feature | present |
| completed_at | present |
| mode | present |
| tasks | present |
| tests | present |
| coverage | present |
| lint | present |
| decisions | present |
| scope | present |
| pause_file_written | present |

### Group B — copied from the send

| Field | Value |
|---|---|
| source_send | bridge/sends/08-rev1-20261004-183704.md |
| source_prompt | plan/.discover/prompts/08-session-journal.md |
| prompt_revision | 1 |
| discovery_revision | 12 |
| slice | 1 |

The spec's frontmatter carries the same five values, with `audited_against: [1]`.

### Group C — written by the code instance

**delegations:** `[]`. No sibling feature was used. Two general-purpose subagents wrote the tests (T003
units, T004 e2e) from the contract. They are subagents, not delegations.

**criteria_reestablished**

Nothing has run in the image. Each citation carries its trace marker and matches exactly one line of the
send (`grep -cF` = 1 for all five).

- `08 · "with time, tool, arguments, exit and a pointer to its log or snapshot _(traces to: P5)_"` —
  **unconfirmed**. Docker lane pending;
  `tests/e2e/journal-lists-every-tool-invocation-in-order-with-pointer.bats`, 4 cells.
- `08 · "appear in the journal with their exit codes _(traces to: P5)_"` — **unconfirmed**. Docker lane
  pending; `tests/e2e/journal-shell-commands-outside-tools-with-exit-codes.bats`, 4 cells.
- `08 · "One command prints the last 20 journal entries of the current session in the bounded output format _(traces to: P1)_"`
  — **unconfirmed**. Docker lane pending; `tests/e2e/journal-last-20-entries-of-current-session-bounded.bats`,
  2 cells.
- `08 · "Entries from concurrent agents are separable by agent and session _(traces to: P4)_"` —
  **unconfirmed**. Docker lane pending;
  `tests/e2e/journal-concurrent-agents-separable-by-agent-and-session.bats`, 2 cells. **Separable when each
  agent has its own `TIMELIKE_AGENT` (or session).** Two agents that set neither share session `default`
  and agent `-`. The records cannot tell them apart, and the spec says so (FR-10).
- `08 · "sees every run, snapshot and grant use in order, each with its session _(traces to: D17)_"` —
  **unconfirmed**. Manual (D17): the mentor captures it after the lane, with the ledger piped in.

The host stand-in run is not a mode. On the scratchpad-only stub, with the rules file and the hook given
to `exec`:
- SC-1 4/4, SC-3 2/2, the manifest 2/2 and SC-4 `bash -c` passed;
- every `bash -lc` style check failed, because the stub runs `-lc` as `-c`;
- `type -a` failed, because it found the stand-in's own path.

**reconcile_mode:** `full`. A new spec, generated from prompt revision 1 in whole, with `audited_against`
seeded `[1]`. Slice 2's tamper-evidence criterion is out of scope.

**not_verified**
- **Everything in the image:**
  - the 16 e2e cells;
  - the hook and trap as installed (`/etc/timelike`);
  - `bash -lc` capture through profile.d;
  - the COPY after the last RUN (the build's `test ! -e /tmp/timelike` must still hold);
  - conformance over the image's tools;
  - the announcement's line for `journal`.
- **Every earlier e2e cell under the new trap.** Each `bash -c` the suite runs now appends a line to its
  session's `shell.jsonl`. I read the one test that inspects session directories (001's peer agents, SC-6),
  and nothing it checks changes. The lane decides.
- **A real `adele` call against the broker, linked to its ledger row.** The units link a slow `adele grants`
  call to a row placed inside it, and the operator's pipe is D17.
- **Root's shells:** not captured, by design.
- **D17.**

**changed_other_features**
- **001, the event (`agentio`):**
  - every tool's event gains `t_ms`, `ppid` and `agent` (when `TIMELIKE_AGENT` is valid);
  - `Tool(event_ref=…)` adds `ref` from the result's data;
  - 001's `event.schema.json` (optional fields) and `output-contract.md` § Session event.
- **001, the shell layer:**
  - `image/rootfs/etc/timelike/shell-env.bash` gains a guarded step that sets an EXIT trap in
    non-interactive `bash -c` / `bash -lc`. It leaves one non-exported variable and the trap.
    **Every agent shell in the image now writes one line at exit**, about 1.1 ms per command (measured).
  - `tests/host/test_shell_env_hook.sh` gains J1–J6.
  - `image/Dockerfile` gains a COPY after the last RUN, so `make scan`'s agent image changes.
- **003 (`run`):** declares `event_ref=("log", "log")`.
- **005 (`snapshot`, `undo`):** declare `event_ref=("snapshot", "id")`.
- **`Makefile`**, **`pyproject.toml`** and **`README.md`** (a journal section).
- **The announcement (007):** lists `journal` automatically.

**process_failures_recorded**
1. **A test helper's counter inside a command substitution** made J1's cases share one scratch root. It
   failed five cases on the first run and was fixed with `mktemp` before the commit (decisions.md T002).
2. **A host-only false alarm.** A smoke run through this instance's own Bash tool, whose stdin is a socket,
   showed no shell entries. Debian bash takes its remote-shell path there and skips `BASH_ENV`. It was
   diagnosed in about ten steps; every later host run uses stdin from `/dev/null`, as 001's host test
   always did.
3. **Three contract inconsistencies** found by the T003 delegate (exit 1 vs 0 for an unreadable record,
   `start_ms` vs `start_us`, what the verdict counts) and **two wrong assertions** of its own (rule 2's
   uncut ending, rule 3's section label). All were settled in the contract or the tests, not by bending the
   tool.
4. **The first prototype of the trap file** made the scratch root 0775 with `mkdir -p`. It was caught
   before any commit; the root is now made 1777, as `agentio` makes it.

**retired_prompts_seen:** none.

### Implement step 10 — quality validation (specswarm 2.35.0), as the library reported it

The output is byte-identical to 008 § Cycle 1's (`diff` of the two runs: no difference): every component
excluded, `Quality Score: unknown — no component could be measured, so there is no score to compare`, and
`block_merge_on_failure=false`. The full text is in 008's cycle report and is not repeated here.

The gate is **UNKNOWN**. It warns and does not halt, and dispatch never asks. Nothing was filled in by
hand. The project's figures are **beside** it in `.specswarm/metrics.json` →
`009.project_measurements_not_scored`.

**Host lane** (advisory; scratch venv, Python 3.12.3):
- **Units:** 1467 passed (make test-host). This feature adds 58 in `test_journal.py`, 3 in `test_agentio.py`
  and J1–J6 (15 host cases).
- **Coverage:** Python **95%**; `journal` 99% (from its tests), agentio 94%.
- **Lint:** ruff (67 files), mypy strict (23 files) and shellcheck (the Makefile's 56 files): clean.
- **`make test-host`:** passed (60/60 files, 44/44 hook).
- **Timings p95:** `journal --help` 67 ms; `journal --json` 86 ms; the trap about 1.1 ms per shell command.

**Implement step 9b: decision log** (installed `scope-tally` and `decision-tally`, after T007):

```
scope: planned=8 recorded=7 unplanned=0 unrecorded=1 in=7 out=0 none=0 unknown=0 flagged=7 flagged_out=0 other=0 other_out=0
decisions: sections=7 flagged_sections=7 non_flagged_sections=0 sections_without_absent=0 flagged=20 assumed=7 deferred=0 absent=7 inherited=6 low_confidence=0 flagged_low_confidence=0
```

- `unrecorded=1` is T008, this report. The marker's tallies are taken after it.
- There is no low-confidence entry, so no pause file was written.

### Addendum 1 — lane batch-b's SC-6 cells, fixed (2026-10-07T00:05:37Z, read from the clock)

- **Finding** (mentor, `../bridge/history.md` 2026-10-06T20:03:07Z, lane batch-b at `1dfc6b7`; log
  `bridge/.make-test-batch-b.log` lines 1948–2010): not ok 249 and 250, 001's SC-6
  `peer-agents-write-to-own-scratch-space.bats`, the default-session cells `[bash -c]` and `[bash -lc]`:
  `b_holds_other_content=1`, `b_foreign=…/peer-b-…/shell.jsonl`. Every other isolation count was clean.
- **Routed** by `bridge/feedback/batch-20261006-234535-lane-b-three-failures.md` § Failure 1, with its ruling.
- **Cause: not a leak.** `fixtures/sc6_check.py` searched each peer's files for the other's session id as
  bytes. In the default cells that id is the word `default`, which the test's `PEER_SCRIPT` holds
  (`${TIMELIKE_SESSION:-default}`). This feature's shell record writes the command text as `"cmd"`, so the
  named peer's `shell.jsonl` held the word with nothing leaked. The named-peer cells passed because random
  ids never occur in the script.
- **Fix, as ruled:** `PEER_SCRIPT` unchanged. `sc6_check.py` leaves `ROOT/X/shell.jsonl` out of the byte
  search and nothing else. In its place it reports `X_shell_records` and `X_shell_own_session`, and the
  test asserts that each peer has at least one record and that every record carries that peer's own
  session. So SC-6 now checks this feature's record for isolation instead of tripping on it.
- **Checked on the host** (no Docker here): the fixture over synthetic trees. The lane's shape gives
  `b_holds_other_content=0` (the old fixture gives 1 on `shell.jsonl`, as in the lane). Three controls trip:
  a session id in another file, a record carrying the other session (`records 2`, `own 1`), and no record
  (`records 0`). The new bats assertion was run in isolation over the same four outputs. ruff, mypy and
  shellcheck are clean.
- **Not verified here:** the four SC-6 cells themselves. They stay `unconfirmed` until the lane re-runs.

**changed_other_features (this addendum):** 001's SC-6 test,
`tests/e2e/peer-agents-write-to-own-scratch-space.bats`, and its fixture `tests/e2e/fixtures/sc6_check.py`.
Test-side only; no tool and no image file changed.

### Addendum 2 — D17 observed by the operator (2026-10-08T05:37:07Z, read from the clock)

From the mentor's observation entry in `../bridge/history.md` (2026-10-07T23:17:25Z) and the transcript
it cites, `bridge/.d17-demo-20261007T224040Z.txt` (bridge `9833168`), which this instance read.

- `08 · "sees every run, snapshot and grant use in order, each with its session _(traces to: D17)_"` —
  **observed by the operator**, by interview with the mentor instance on the live stack from lane batch-d
  (`timelike-agent` `sha256:d0dd2058…` and `timelike-adele` `sha256:8d299c50…`, revision `244c4a8`).
  Each agent command was its own `docker exec … bash -lc`, as user `agent`, with `TIMELIKE_SESSION` and
  `TIMELIKE_AGENT` set per command.
  - **What the agents did:** agent-a, in session `d17-review`, took a snapshot, made two `run` calls
    (exit 0 and exit 2) and two `adele request standin.box create --grant e2e` calls. Port 8080 was
    performed (ledger #45, exit 0); port 22 was refused (ledger #46, exit 4, with an envelope naming
    `adeled extend e2e ports 22`). It also ran plain shell commands. At the same time, agent-b worked in
    session `d17-side`.
  - **The operator's review**, using the spec's Scenario 5 pipe (`adeled ledger --json | journal --session
    d17-review --all --ledger -`): 12 of 12 entries (3 tools, 7 shell, 2 grants) in time order, each with
    its pointer (snapshot 1, the run logs, ledger #45 performed e2e, #46 refused e2e).
    `--all-sessions --agent agent-b` showed agent-b's entries labelled `[agent-b/d17-side]`.
  - **Ledger cross-check:** rows 45 and 46, session `d17-review`, outcomes performed and refused. They
    agree with the journal.
  - **Interview:** answers 1 and 4 matched. Answer 2 first reversed the outcomes, and answer 3 first
    pointed at the ledger. The mentor challenged both, and the operator corrected both from the
    transcript. The operator accepts D17 as observed.
  - The criterion still resolves to exactly one line of the send (`grep -cF` = 1).
- **Noted by the mentor, a finding for 08 and 12, not D17:** Adele's ledger rows carry `agent: None`
  although `TIMELIKE_AGENT` was set, so the ledger alone cannot attribute a grant use to an agent. The
  journal places it by session and time. That is for a later cycle.
- **Read by this instance, not a defect:** agent-b's `run uname -s` appears as one row in the
  `--all-sessions` view, while agent-a's calls appear as a shell row with an indented tool row. That is
  FR-9's rule (`tools/bin/journal`, `link`): a shell whose command is exactly one tool call is shown once.
  agent-a's commands began with `cd … &&`.
- **The transcript header also discloses** a discarded first attempt at 22:40:15Z (its requests named no
  grant). Its sessions `d17-demo` and `d17-other` remain in the live container's scratch, which is why
  agent-b's view lists `d17-other`'s two entries.
- **Where this record lives:** on `012-verify-changed`, the stack's tip, as with the D12, D14 and D4 addenda
  (`d932c1c`, `631a29e`, `eafd930`), so that `244c4a8..` stays records only and lane batch-d's evidence holds.
  The mentor's instruction allowed this placement provided it is stated (a branch per addendum was its
  first option). A revert of 012 by branch topology would carry this addendum with it.
