# Cycle report — 007 announcements and discovery (prompt 04)

> Append-only. One `## Cycle N — <send>` section per send built to acceptance; later verification goes in
> `### … addendum` sections. The mentor reads this file and never writes into it.

## Cycle 1 — bridge/sends/04-rev1-20261004-183704.md

**Written:** 2026-10-04. **Dispatch mode**, batch `20261004-183704`, prompt 3 of 8. **specswarm
4.0.1-botbaubble.2.35.0** (`4ff8dcb`), the version this session loaded: the expanded `/specswarm:specify`
and `/specswarm:implement` named that cache path (lore Q002). The path is the one the send names, so
there is no second report.

**Sequence:**
1. `git checkout -b 007-announcements-discovery modify/006-slice-1` (at `eb5c8e2`).
2. `/specswarm:specify "04 announcements & discovery" --from-send bridge/sends/04-rev1-20261004-183704.md --dispatch`,
   invoked. Its blocks were run from the installed file (below).
3. `/specswarm:plan` and `/specswarm:tasks` were **not re-invoked**. Their 2.35.0 text, loaded earlier in
   this session, was followed, as for 006.
4. `/specswarm:implement --dispatch`.

Not `/specswarm:build`. **Pushed nothing; merged nothing.**

**specify's allocation:**
- the directory is `007-announcements-discovery`, from the branch: **D84 held**. The description's slug
  would have been `04-announcements-discovery`, and specify said it took the branch's.
- **PARENT_ROUTE: `default`** (`master`), as the code track predicted. The batch's real parent is
  `modify/006-slice-1`. The batch merges nothing, so the recorded `parent_branch: master` is what a
  `/specswarm:complete` would use, and the mentor merges by hand.

**The `$ARGUMENTS` expansion — the send's question, and its first real occurrence.** The exact argument
string was `"04 announcements & discovery" --from-send bridge/sends/04-rev1-20261004-183704.md --dispatch`.
- **The stray quotes were in the description, not in a path.** The code track itself prescribes the
  quoted short name.
- The expansion pasted that string into double-quoted shell strings:
  `DESCRIPTION=""04 announcements & discovery" --from-send …"`. That breaks the quoting, and leaves
  the `&` unquoted, which would send the rest of the line to the background.
- The blocks (`prompt-source`, `dispatch-flag`, `dispatch-parent`) were run from the installed file
  with `ARGUMENTS` as a variable. They parsed correctly: `PROMPT_VIA=from-send`,
  `DESCRIPTION="04 announcements & discovery"` (quotes kept, slug unaffected), `DISPATCH_MODE=true`.

**Status in one line:** the announcement is generated from every tool's `--agent-info` at build, checked
at build, and placed on container start in the user-level files of Claude Code, Codex CLI and OpenCode.
`timelike tools` prints the manifest. Units, lint and the host lane pass. Nothing has run in the image.

### Group A — cited from `.implement-complete`

The marker is `.specswarm/features/007-announcements-discovery/.implement-complete`, written at the end
of this run, after this section's commit. No measured number is copied here.

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
| source_send | bridge/sends/04-rev1-20261004-183704.md |
| source_prompt | plan/.discover/prompts/04-announcements-discovery.md |
| prompt_revision | 1 |
| discovery_revision | 12 |
| slice | 0 |

The spec's frontmatter carries the same five values, written from the send's header lines, with
`audited_against: [1]`.

### Group C — written by the code instance

**delegations:** `[]`. No sibling feature was used. Two general-purpose subagents wrote the tests (T002,
T003). They are subagents, not delegations.

**criteria_reestablished**

Nothing has run in the image. Each citation carries its trace marker and matches exactly one line of
the send (`grep -cF` = 1 for all four).

- `04 · "and in the workspace's agent context file when none exists, without overwriting an existing one _(traces to: P3)_"` —
  **unconfirmed** (Docker lane pending;
  `tests/e2e/announcement-at-most-60-lines-in-each-harness-user-level-context-on-start.bats`, 6 cells).
  **Built for its user-level part only.** The workspace part is not built: spec D-1, the send's seam 1,
  FOR-MENTOR Item 19, routed to plan. The cells assert the workspace stays untouched.
- `04 · "and a test fails if any installed timelike tool is missing from it _(traces to: P3)_"` —
  **unconfirmed** (Docker lane pending; `tests/e2e/announcement-generated-from-manifests-missing-tool-fails.bats`, 6 cells)
- `04 · "with fields for JSON support, interactivity risk and safer alternative _(traces to: P3)_"` —
  **unconfirmed** (Docker lane pending;
  `tests/e2e/timelike-tools-manifest-json-interactivity-risk-safer-alternative.bats`, 6 cells)
- `04 · "uses a timelike tool it learned about from the environment's announcement _(traces to: D4)_"` —
  **unconfirmed**. Manual (D4): the mentor captures it after the lane.

**reconcile_mode:** `full`. A new spec, generated from prompt revision 1 in whole, with `audited_against`
seeded `[1]`. Slice 1's three automated criteria and its one Manual criterion are out of scope.

**not_verified**
- **Everything in the image:**
  - the image build's announcement step (simulated on the host);
  - the ENTRYPOINT on container start;
  - the 18 e2e cells;
  - P6 on the vanilla image.
- **Whether each harness reads its file.** The locations come from each harness's own documentation
  (research R1). No harness runs in this container. D4 is where reading is observed.
- **The 1 s placement bound:** measured in the e2e cell from the daemon's start time (delegate's FLAGGED).
- **SC-1's workspace part:** not built (Item 19).
- **D4.**

**changed_other_features**
- **`tools/bin/timelike` (001):** `announce` and `tools` subcommands. Plain `timelike` is unchanged.
- **`image/Dockerfile`:**
  - `ENTRYPOINT`: the agent container, every e2e throwaway and the bench's timelike arm now run it on
    start;
  - the announcement build step;
  - two COPYs.

  `make scan`'s agent image changes.
- **`tools/bin/view` and `tools/bin/search` (006):** mode `0755`. They were committed `100644` in 006
  Cycle 1. The image's `COPY --chmod=0755` hid it, and the generator's executable test found it. This
  is a **process failure of 006 Cycle 1**, now fixed.
- **`Makefile`** (shellcheck list) and **`README.md`** (an announcements section).
- **The bench:** its timelike arm now sees the announcement, and the vanilla arm does not (P6, D-5). The
  told/untold comparison is now the environment's own.

**process_failures_recorded**
1. **006's tools were not executable in git** (above). It was found by this feature, not by 006's lane.
2. **The coverage rc did not map the new tests' `tl/` copies.** The first figure (51%) was not a
   measurement of the code; it was corrected to 95%.
3. **A build-step simulation was blocked by Claude Code's removal safety check** (`rm -rf` of a variable
   inside `sh -c`). It was re-run without any removal. The blocked command was also where T006's
   decision file was written, so T006's first commit attempt failed; T002 then committed a stray blank
   line the helper had begun to append.
4. **The test delegates' contract findings** (rules conditional on installed tools, `current` meaning
   byte-identical, the status line format, the manifest's text) were settled in the contract as built.
   One unit (`current`) was revised to the settled contract: the code was kept, not the first wording.
5. **R3 first said 9 tools.** It was 8, counted.

**retired_prompts_seen:** none.

### Implement step 10 — quality validation (specswarm 2.35.0), as the library reported it

```
🧪 Running Quality Validation
=============================
- Detector:
{
  "frameworks": ["pytest"],
  "primary": "pytest",
  "count": 1
}
- run_tests pytest: rc=2
/usr/bin/python3: No module named pytest
run_tests: pytest is declared by this project but not installed here
- parse_test_results: total=unknown passed=unknown failed=unknown skipped=unknown
- run_coverage pytest: unknown (rc 1)
- step 10e: browser test framework: none (no package.json)
- quality-components: QC_BROWSER_STATE=not-applicable:no web project detected, so there is nothing to drive a browser over
                      QC_BUNDLE_STATE=unavailable:lib/bundle-size-monitor.sh is not present in this install
- components:
unit-tests|25|-|unavailable:pytest could not be run on this machine (run_tests returned 2: declared by this project, not installed for /usr/bin/python3)
coverage|25|-|unavailable:pytest could not be run on this machine, so run_coverage printed unknown (rc 1)
integration-tests|15|-|not-applicable:no integration suite is detected by the plugin; the bats e2e run only in the Docker lane
browser-tests|15|-|not-applicable:no web project detected, so there is nothing to drive a browser over
bundle-size|20|-|unavailable:lib/bundle-size-monitor.sh is not present in this install
visual-alignment|15|-|unavailable:screenshot analysis is not implemented

Quality Score: unknown — no component could be measured, so there is no score to compare


ℹ️  Why there is no score, and whose gap it is
   Every component was excluded. Each line below says which:
     - unit-tests — unavailable: pytest could not be run on this machine (run_tests returned 2: declared by this project, not installed for /usr/bin/python3) (25 points not counted either way)
     - coverage — unavailable: pytest could not be run on this machine, so run_coverage printed unknown (rc 1) (25 points not counted either way)
     - integration-tests — not-applicable: no integration suite is detected by the plugin; the bats e2e run only in the Docker lane (15 points not counted either way)
     - browser-tests — not-applicable: no web project detected, so there is nothing to drive a browser over (15 points not counted either way)
     - bundle-size — unavailable: lib/bundle-size-monitor.sh is not present in this install (20 points not counted either way)
     - visual-alignment — unavailable: screenshot analysis is not implemented (15 points not counted either way)

   2 component(s) could not be measured because something this plugin ships is
   absent from this install — that is SpecSwarm's gap, not this project's.
   2 component(s) could not be measured because something this project
   declares could not be run on this machine — that is neither a defect in SpecSwarm
   nor in the project: install it here, or run where it is installed.
   2 component(s) do not apply to a project of this kind, which is not a defect.
block_merge_on_failure=false
```

The gate is **UNKNOWN**. It warns and does not halt, and dispatch never asks. Nothing was filled in by
hand. The project's figures are **beside** it in `.specswarm/metrics.json` →
`007.project_measurements_not_scored`. The output is verbatim.

**Host lane** (advisory; scratch venv, Python 3.12.3):
- **Units:** 1309 passed, 1 skipped. This feature's units: 50.
- **Coverage:** Python **95%**, `timelike` 92%.
- **Lint:** ruff (63 files), mypy strict (21 files) and shellcheck: clean.
- **`make test-host`:** passed.
- **Timings p95:** `timelike --help` 76 ms, `announce --status` 72 ms, `tools` 688 ms, `announce` 675 ms.

**Implement step 9b: decision log** (installed `scope-tally` and `decision-tally`, after T008):

```
scope: planned=9 recorded=8 unplanned=0 unrecorded=1 in=7 out=0 none=1 unknown=0 flagged=7 flagged_out=0 other=1 other_out=0
decisions: sections=8 flagged_sections=7 non_flagged_sections=1 sections_without_absent=0 flagged=17 assumed=7 deferred=0 absent=8 inherited=7 low_confidence=0 flagged_low_confidence=0
```

- `unrecorded=1` is T009, this report. The marker's tallies are taken after it.
- There is no low-confidence entry, so no pause file was written **for this feature**.

### Addendum 1 — lane batch-a's failed cell, fixed (2026-10-05T04:43:04Z, read from the clock)

- **Finding** (mentor, `../bridge/history.md` 2026-10-05T00:06:27Z, lane batch-a at `8b8c61c`): not ok 50,
  SC-2 [bash -lc, notty], `timelike announce --check exits 0 … on an unmodified copy`: the fixture's
  `cp` into the file's temp dir failed with Permission denied.
- **Cause: cell order, not the login shell.** `/etc/timelike/announcement.md` is 0444 (Dockerfile § 8b),
  and `cp` gives a new file the source's mode. Both cells copied to the same `${SC2_DIR}/copy.md` (one
  dir per file, from `setup_file`). Cell 49 (bash -c) runs first and creates it 0444. Cell 50's `cp`,
  as `agent` (`USER agent`), then cannot open it for writing. Reproduced on the host as a non-root
  user: the first `cp` succeeds, the second fails with the same message.
- **Fix:** `check_check_passes` copies to `copy-<style>-<tty>.md`, one per cell. Test-side only; the tool
  and the image are unchanged. `check_missing_tool_fails` writes its copy with Python's `open(…, "w")`
  (mode from umask, owner-writable), so it does not have this defect.
- **Not verified here:** the cell itself (no Docker in this instance). It is `unconfirmed` until the
  full lane at the batch's end.

### Addendum 2 — D4 observed by the operator (2026-10-07T20:38:33Z, read from the clock)

From the mentor's observation entry in `../bridge/history.md` (2026-10-07T20:37:02Z) and the transcript
it cites, `bridge/.d4-demo-20261007T185100Z.txt` (with the harness's stream-json beside it,
`.d4-demo-20261007T185100Z.jsonl`; bridge `a4b5567`). This instance read the `.txt`.

- `04 · "uses a timelike tool it learned about from the environment's announcement _(traces to: D4)_"` —
  **observed by the operator**, by interview with the mentor instance on a real harness session.
  - **The environment:** a throwaway from the image lane batch-d passed (revision `244c4a8`,
    `sha256:d0dd2058…`). Node 20 and Claude Code 2.1.292 were added for the demo only. It ran with
    `--cap-drop ALL`, `no-new-privileges` and `--init`, as user `agent`.
  - **The session:** one `claude -p` with HOME `/home/agent`, so it loaded `~/.claude/CLAUDE.md`, the
    announcement the entrypoint placed at start (`announce --status`: claude-code, codex and opencode all
    `current`; 28 lines). Its built-in file tools were disallowed, so it worked through its shell tool.
  - **The prompt** (verbatim in the transcript) names neither timelike nor any tool.
  - **What the agent did:**
    1. `view mailparse/_header_value_parser.py:1404-1437`;
    2. `symbols get_word`, a usage error (exit 2) whose message lists the four actions;
    3. `symbols callers get_word`.
  - **Its answer** gave `get_word`'s role and its callers: 4 call sites in 3 functions (`get_phrase` at
    1452 and 1465, `get_local_part` at 1501, `get_obs_local_part` at 1551), which it said were text-based.
    The mentor checked the four lines by grep in the image.
  - **Interview:** answers 1–3 matched; one was corrected (the entrypoint placed the file, and `announce
    --status` only reports it). Answer 4 first said "4 functions"; when challenged, the operator
    corrected it to 3 (a mistype). The operator accepts D4 as observed.
  - **Credential**, from the mentor's entry: the operator's subscription token reached the harness
    process only. timelike's shell-env strips token-shaped variables from every bash, so the agent's
    shell never held it. The token is absent from both transcript files.
  - The criterion still resolves to exactly one line of the send (`grep -cF` = 1).
- **What this settles from § Cycle 1's not_verified:** "whether each harness reads its file", for
  **Claude Code** only. Codex and opencode reading their files is still not observed.
- **Noted by this instance, not a defect:** the agent's first guess, `symbols NAME`, cost one turn, and the
  usage message's list of actions recovered it. The announcement's `symbols` line is the manifest summary
  (`tools/bin/symbols:68`: "where a name is defined, who calls it, what imports a file, a file's outline;
  never bodies"). It names what the tool answers but no action word, so a first guess like this is
  expected. A summary naming the actions would avoid the extra turn; that is a question for a later
  cycle, not a change here.
- **Where this record lives:** on `012-verify-changed`, the stack's tip, as with the D12 and D14 addenda
  (`d932c1c`, `631a29e`), so that `244c4a8..` stays records only and lane batch-d's evidence holds.

§ Cycle 1's automated criteria are still recorded `unconfirmed` above. Lane batch-d (2026-10-07T03:26:28Z,
e2e 537/537) ran their cells, but this addendum records D4 only.

## Cycle 2 — bridge/sends/04-rev13-20261008-095251.md

**Written:** 2026-10-08T10:12:16Z (read from the clock). Not in dispatch mode. Built with `/specswarm:modify 007 --from-send
bridge/sends/04-rev13-20261008-095251.md`, then `/specswarm:plan`, `/specswarm:tasks` and `/specswarm:implement`,
on `modify/007-rev13` from `master` at `c79facc` (= `public/main`). **Pushed nothing; not merged.** This is
007's first modify cycle, so it creates `impact-analysis.md`, `modify.md` and `audit-log.md`.

**specswarm version (lore specswarm Q002):** **4.0.1-botbaubble.2.37.0**. The expanded commands named its cache path,
and the session's pid is in its `.in_use`.

**Status in one line:** record only, `.specswarm/features/007-announcements-discovery/` only. Revision 13 struck
SC-1's workspace clause, and the code already matches it. The spec's quotation of SC-1, its notes and D-1 are
corrected by declared copy, and D-1 is resolved. `audited_against` gains 13.

### Group A — cited from `.implement-complete`

Group A: not applicable — no marker on this path

### Group B — copied from the send

| Field | Value |
|---|---|
| source_send | bridge/sends/04-rev13-20261008-095251.md |
| source_prompt | plan/.discover/prompts/04-announcements-discovery.md |
| prompt_revision | 13 |
| discovery_revision | 13 |
| slice | 0 of [0, 1] (merged) (no new slice; an audit of what is merged) |

### Group C — written by the code instance

**delegations:** `[]`.

**criteria_reestablished.** Slice 0's four criteria. This cycle changed only files under
`.specswarm/features/007-announcements-discovery/` (`git diff master HEAD -- . ':!.specswarm/features/007-announcements-discovery'`
is empty), and `master`'s tree at `c79facc` is `725b7a1f…`, identical to `10ddd3a`'s. So the three Automated
criteria cite **the mentor's lane readme-c at `10ddd3a`, a lane on an identical tree** (history 2026-10-08T08:28:00Z:
`make test` PASSED, e2e 537/537; log `bridge/.make-test-readme-c.log`). No lane ran for this cycle.
- `04 · "a timelike announcement of at most 60 lines is present in each supported harness's user-level context location"` —
  **executed [mentor's lane readme-c at 10ddd3a:
  `tests/e2e/announcement-at-most-60-lines-in-each-harness-user-level-context-on-start.bats`, ok 41–46]** (cited,
  not re-run; identical tree). Under revision 13 the criterion is user level only, and its cells test all of it,
  including that no `CLAUDE.md` or `AGENTS.md` is created in the workspace (ok 45, 46). The cited text lies
  outside the strike: Cycle 1's citation quoted the now-struck clause and no longer matches the send.
- `04 · "and a test fails if any installed timelike tool is missing from it _(traces to: P3)_"` — **executed [mentor's
  lane readme-c at 10ddd3a: `tests/e2e/announcement-generated-from-manifests-missing-tool-fails.bats`, ok 47–52]**
  (cited, not re-run; identical tree)
- `04 · "with fields for JSON support, interactivity risk and safer alternative _(traces to: P3)_"` — **executed
  [mentor's lane readme-c at 10ddd3a: `tests/e2e/timelike-tools-manifest-json-interactivity-risk-safer-alternative.bats`,
  ok 426–429, and its P6 cells ok 430–431]** (cited, not re-run; identical tree)
- `04 · "uses a timelike tool it learned about from the environment's announcement _(traces to: D4)_"` — **observed by
  the operator**, the mode Cycle 1's Addendum 2 recorded (the mentor's observation entry 2026-10-07T20:37:02Z; transcript
  `bridge/.d4-demo-20261007T185100Z.txt`). This cycle observed nothing new.

Each citation matches exactly one line of the send (`grep -cF` = 1 for all four).

**reconcile_mode:** `scoped`. `audited_against` is now `[1, 13]` (T012, computed by the installed `audit-append`
block: `MODE=scoped`, `UNVERIFIED=13`, `OUT_OF_SCOPE` empty → `MODE_USED=scoped`, `APPENDED=13`, no note).
- **What revision 13 changed (lore P004: what was compared).** The prompt bodies of `04-rev1-20261004-183704` and
  this send differ by revision 13's note and by one strike in the slice-0 criterion, "and in the workspace's agent
  context file when none exists". Nothing else moved, and revisions 2–12 did not change prompt 04.
- **Amended (struck clause), corrected in place, not regenerated.** The design was already user level only (FR-5–7,
  D-1), and the cells assert that the workspace stays untouched. The body's *quotation* of SC-1 and its account of
  D-1 as a raised deviation became false. The lines compared and corrected (numbers before T010): `spec.md:113–116`
  (FR-7's note), `:161–163` (SC-1's quotation), `:170–171` (SC-1's note), `:200–210` (D-1, resolution appended,
  T011), `:232` (Out of scope). The superseded notes are kept, struck through, each followed by a declared
  *(Revised, revision 13 …)* note.
- **Why `scoped`, not `full`.** Revision 13 rewords a criterion, so `full` lists it as unverified. Verified: it
  would append 2–12 and leave out 13, the revision this cycle actually checked. `scoped` appends 13 alone, as the
  send asks.
- **Left as written** (records, true or append-only): `decisions.md:65`, T003's FLAGGED cell sense, which said
  "the cells change if plan amends the criterion". Plan amended it in the direction already built, so the cells do
  not change. Also left: Cycle 1's SC-1 citation (`cycle-report.md:86–90`) and `plan.md:38`.

**not_verified**
- **No test ran in this cycle**, on the host or in the image. The Automated criteria are cited from lane readme-c,
  not re-executed. The citation holds only because nothing outside this feature's directory changed.
- **SC-1's timing bound under load.** The mentor recorded that SC-1's 1 s placement bound failed in lane readme-b
  (ok 41, 42 not ok: 11225 ms under host I/O load) and passed in readme-c. That is a watch item for a later 007 cycle.
  This cycle does not touch it.

**changed_other_features:** none. Only `.specswarm/features/007-announcements-discovery/` changed. FOR-MENTOR Item 19
was already closed (2026-10-05, `FOR-MENTOR.md:858`), so the register needs nothing. Implement step 10j's
`.specswarm/metrics.json` entry was not written (outside the feature directory, as the send directs).

**process_failures_recorded**
- None in this cycle's steps. **Plugin observations under 2.37.0:** the same as 002's Cycle 2 on this session
  (`lib/tally.sh` with 0 bytes on stderr; the tallies print no trailing newline; `provenance-inputs` mechanises
  row 7; `fnum_resolve` resolved `modify/007-rev13` to 007 with nothing on stderr).

**retired_prompts_seen:** none.

**One finding outside this cycle's scope, for the mentor (not changed: the send confines this cycle to the feature
directory).** SC-1's six e2e cell names in
`tests/e2e/announcement-at-most-60-lines-in-each-harness-user-level-context-on-start.bats` (`:400–405`) still quote
the old criterion, with "and in the workspace's agent context file when none exists". The two workspace cells
(`:404–405`, ok 45 and 46) are named "workspace part NOT built (D-1)". Their assertions are right under revision 13;
only their names quote the struck text. Renaming them changes `tests/`, which needs a lane, so it belongs to a later
007 cycle or a small maintenance send.

### Implement step 10 — quality validation (specswarm 2.37.0 blocks), as the library reported it

This is the same result as 002's Cycle 2 on this session, re-run on this branch: `run_tests` rc=2 (pytest declared,
not installed for `/usr/bin/python3`), `run_coverage` `unknown`, browser `none`. The scale's output is identical
byte for byte: `Quality Score: unknown — no component could be measured`. The six exclusions are attributed 2 to
this install, 2 to this machine and 2 not applicable, with `block_merge_on_failure: false`
(`quality-standards.md:295`). The gate is **UNKNOWN**, so it warns and does not halt. No component was filled in by
hand.

**Implement step 9b: decision log** (plugin `scope_tally` and `decision_tally` over the whole of 007's `tasks.md` and `decisions.md`, all cycles, before T013's own records):

```
scope: planned=13 recorded=12 unplanned=0 unrecorded=1 in=8 out=0 none=4 unknown=0 flagged=10 flagged_out=0 other=2 other_out=0
decisions: sections=12 flagged_sections=10 non_flagged_sections=2 sections_without_absent=0 flagged=20 assumed=10 deferred=0 absent=12 inherited=10 low_confidence=0 flagged_low_confidence=0 flagged_delegate=1 assumed_delegate=0
```

Cycle 2 alone (T010–T012 at that point): 3 sections, 2 FLAGGED entries (T010's struck-and-kept notes; T012's mode),
0 low-confidence. `SCOPE:` none 3.
