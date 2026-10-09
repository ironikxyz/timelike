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

## Cycle 3 — bridge/sends/04-rev13-20261008-161802.md

Slice 1 of prompt 04, as a modify cycle of 007 on `modify/007-slice-1` from `master` `f6faf01`. Written
2026-10-08T17:04:49Z (from the clock). specswarm **4.0.1-botbaubble.2.37.0** ran: every expanded command's `PLUGIN_DIR` is 2.37.0's
cache path (lore specswarm Q002). **Not merged, not pushed.** This cycle changes `image/`, `tools/` and `tests/`,
so the mentor's Docker lane comes before sign-off, and this instance makes no commit until the mentor says the lane
has ended.

**One criterion is not built.** The install criterion (SC-6) is held on **FOR-MENTOR Item 21** (send seam 1: the
image has no agent-facing Python or Node). Everything else in the slice is built (spec D-11).

### Group A — cited from `.implement-complete`

Group A: not applicable — no marker on this path.

### Group B — copied from the send

| Field | Value |
|---|---|
| source_send | bridge/sends/04-rev13-20261008-161802.md |
| source_prompt | plan/.discover/prompts/04-announcements-discovery.md |
| prompt_revision | 13 |
| discovery_revision | 13 |
| slice | 1 of [0, 1] (intensity: natural) |

### Group C — written by the code instance

**delegations:** `[]`. No sibling feature was used. Two general-purpose subagents wrote the tests from the contract
before the code: T014 (both e2e files) and T015 (the two unit files and the host handler test). Their decisions are in
`decisions.md`, marked `(delegate)`. The coordinator reviewed both, ran T015's suites, and committed each delegate's
files. T015's host test found two handler defects, fixed in T018's follow-up.

**criteria_reestablished.** All eight of prompt 04's criteria: slice 0's four, because this cycle changed the
announcement and SC-1's cells, and slice 1's four. **No image lane has run on this branch yet**, so every Automated
criterion is `unconfirmed`. The host-lane results are listed beside each, labelled advisory; they are not image
evidence.
- `04 · "a timelike announcement of at most 60 lines is present in each supported harness's user-level context location"` —
  **unconfirmed** (image lane pending). The cells
  (`tests/e2e/announcement-at-most-60-lines-in-each-harness-user-level-context-on-start.bats`) were renamed to revision
  13's text, and the 1 s bound became an ordering (T019, declared in spec § Slice 1 carried items).
- `04 · "and a test fails if any installed timelike tool is missing from it _(traces to: P3)_"` — **unconfirmed** (image
  lane pending). Host advisory: `tests/unit/test_announce.py` passed with the two new rule lines (T017, T020).
- `04 · "with fields for JSON support, interactivity risk and safer alternative _(traces to: P3)_"` — **unconfirmed**
  (image lane pending). Host advisory: test_announce passed. `timelike tools` is unchanged.
- `04 · "exits 127 and prints the install command for the package that provides it"` — **unconfirmed** (image lane
  pending: `tests/e2e/command-not-installed-exits-127-and-prints-the-install-command.bats`, 17 cells). Host advisory:
  `tests/host/test_command_not_found.sh` 33/33 (nine invocation styles, byte for byte against bash) and
  `tests/unit/test_missing_commands.py` 13/13.
- `04 · "persist across new shells _(traces to: P1)_"` (the bare Python and Node installs) — **unconfirmed: NOT BUILT**,
  held on FOR-MENTOR Item 21 (T022). Nothing in the image or the tests addresses it.
- `04 · "free space on the workspace and scratch filesystems _(traces to: P2)_"` — **unconfirmed** (image lane pending:
  `tests/e2e/one-command-prints-the-agents-resource-budget.bats`, 10 cells). Host advisory: `tests/unit/test_budget.py`
  73/73, including the CPU rule against the bash hook on the same files.
- `04 · "uses a timelike tool it learned about from the environment's announcement _(traces to: D4)_"` — **observed by the
  operator**, the mode Cycle 1's Addendum 2 recorded (2026-10-07, on slice 0's announcement). This cycle added two rule
  lines to that announcement and observed nothing new.
- `04 · "is told the install command or the equivalent timelike tool _(traces to: D13)_"` — **unconfirmed**. The mentor
  captures D13 after the lane, as the send says.

Each citation matches exactly one line of the send (`grep -cF` = 1 for all eight). Three were lengthened to their
`_(traces to: …)_` endings because the send's "In scope" list repeats their opening words.

**reconcile_mode:** `scoped`. Modify **row 4**: revision 13 was already in `audited_against` `[1, 13]`, so Step 9
appended nothing and the frontmatter is unchanged. This cycle examined slice 1's four criteria. Slice 0's are carried
from Cycle 2's audit.

**not_verified:**
- **Anything in the image.** No Docker daemon here: all 27 new e2e cells and SC-1's six changed cells are written and
  shellcheck-clean, but have not been run.
- **Two premises of T014's cells:**
  - the direct-exec cell asserts non-zero, not 127; docker's status for a missing exec binary was not verified;
  - the limited throwaway needs a host with at least 2 CPUs, for `--cpus 1.5`.
- **Every listed command is absent from the image.** The TSV rows were chosen as names trixie-slim plus this image's
  packages do not install. The e2e cell `… every listed name is absent in the image …` is the check, and a failure
  there means removing a row.
- **The handler in the image's bash 5.2.37.** It was measured and compared on host bash 5.2.21.
- **SC-6**, in full (held).

**changed_other_features:**
- **003 `run`:** `cgroup_dir`, the byte reader and `size()` moved into agentio, and `run` uses them. Behaviour is unchanged;
  test_run and test_run_slice1 pass unchanged.
- **005 `snapshot`:** `find_workspace` calls `agentio.workspace()`. Unchanged; test_snapshot and test_undo pass.
- **001's hook** `image/rootfs/etc/timelike/shell-env.bash`: it defines `command_not_found_handle`, and its "leaves
  nothing behind" rule is amended. `tests/host/test_shell_env_hook.sh` Q2 now allows exactly that function.
- **001's agentio:** new shared readers.
- **`image/Dockerfile`:** one COPY.
- **`README.md`:** the generated command reference only (one line).
- **`tests/host/run.sh`:** runs the new host test.
- **FOR-MENTOR.md:** Item 21.
- **reboot.md:** the operator's staged note folded in.
- **`bench/vanilla/Dockerfile`:** untouched (FR-13).

**process_failures_recorded:**
1. T021 was committed before T020's record. T021 changes no README content; T020's record says so.
2. T014's `decisions.md` section puts its plain `ABSENT:` mid-line after `ABSENT (delegate):`, so the plugin's
   `decision_tally` reports `sections_without_absent=1` for it. The section does carry an ABSENT, and records are
   append-only, so it is left as written.
3. The traced coverage run's TOTAL (59%) used a wrong `[paths]` alias for the bench's temp copies, so it is not
   reported. The four changed files' figures are unaffected: agentio 95%, run 93%, snapshot 92%, timelike 93%.
4. A timing command was refused by the harness's removal check (an inline `bash -c` script); it was re-run from a
   script file. No removal was involved.

**retired_prompts_seen:** none.

**For the mentor:**
- **Item 21** is open and holds SC-6 and the README status block.
- **The handler's cost:** about 1.9 ms more per missing command than bash alone (host).
- **The README status block is not applied** (send: "only if all four slice-1 criteria are met").
- **Delegate contract findings,** settled in the contract:
  - JSON keys are at the top level;
  - the interactive line uses argv0's base name;
  - a directory at the data path means line 1 alone;
  - an empty `PATH` never reaches the handler (bash's own behaviour).

### Implement step 10 — quality validation (specswarm 2.37.0 blocks), as the library reported it

- `run_tests` rc=2 (pytest declared, not installed for `/usr/bin/python3`). `run_coverage` printed `unknown` (rc 1).
  Browser framework: `none`.
- `Quality Score: unknown — no component could be measured, so there is no score to compare`.
- The six exclusions: 2 attributed to this install, 2 to this machine, 2 not applicable.
- The gate is **UNKNOWN**: warned, not halted.
- Recorded as `.specswarm/metrics.json` → `007-cycle-3`, with the project's host figures beside it, unscored (T020).
  No component was filled in by hand.

**Implement step 9b: decision log** (the plugin's `scope_tally` and `decision_tally` over all of 007's `tasks.md` and
`decisions.md`, every cycle, before T023's own records):

```
scope: planned=23 recorded=21 unplanned=0 unrecorded=2 in=16 out=0 none=6 unknown=0 flagged=19 flagged_out=0 other=3 other_out=0
decisions: sections=22 flagged_sections=19 non_flagged_sections=3 sections_without_absent=1 flagged=31 assumed=23 deferred=0 absent=21 inherited=19 low_confidence=0 flagged_low_confidence=0 flagged_delegate=7 assumed_delegate=4
```

`unrecorded=2` is T022 (held) and T023 (this record). There are no low-confidence decisions. Every `SCOPE:` record in
Cycle 3 is `in` or `none`.

## Cycle 4 — bridge/sends/04-rev14-20261008-174220.md

Slice 1 of prompt 04, re-sent at discovery revision 14, continued on `modify/007-slice-1` from `e0fb5a3` (Cycle 3
stands, as the send says). Written 2026-10-08T18:12:08Z (from the clock). specswarm **4.0.1-botbaubble.2.37.0**, the same session
(2.38.0 is published but not installed, and was not reloaded). **Not merged, not pushed.** This cycle changes
`image/`, `bench/`, `scan/`, `tests/`, `pins.env`, `compose.yaml`, `Makefile` and `README.md`, so the mentor's
Docker lane (`make test`, `make scan` with the deny-list read) comes before sign-off. This instance makes no
commit until the mentor says the lane has ended.

**The governance audit (13 → 14) is on this branch**, as its own commits, so the lane sees one branch:
- `e58dd36`: `tech-stack.md` 1.3.1 → 1.4.0 (the Agent runtimes entry; the PEP 668 and uv notes corrected; a
  parseable `Node` line) and `quality-standards.md` (the scan gate names the four images and the runtimes in their
  SBOMs);
- `07b914d`: `constitution.md` through `/specswarm:constitution`, no change, 1.4.2 stands (no article restates the
  base-image constraint; H5 already keeps timelike's tools off any agent interpreter).

All three now record `[2..14]`, each with a prose note naming revision 14, what was checked, and the governance
context's *What Changed In Those Revisions* (relied on). **FOR-MENTOR Item 21 is closed** (`9b90a74`).

### Group A — cited from `.implement-complete`

Group A: not applicable — no marker on this path.

### Group B — copied from the send

| Field | Value |
|---|---|
| source_send | bridge/sends/04-rev14-20261008-174220.md |
| source_prompt | plan/.discover/prompts/04-announcements-discovery.md |
| prompt_revision | 14 |
| discovery_revision | 14 |
| slice | 1 of [0, 1] (intensity: natural) |

### Group C — written by the code instance

**delegations:** `[]`. No sibling feature was used. Two general-purpose subagents wrote the tests from the spec
before the images changed:
- T024: the SC-6 e2e file and the revised P6 vanilla cells;
- T025: the runtime units, the vanilla unit test and the user-row checks.

Their decisions are in `decisions.md`, marked `(delegate)`. The coordinator reviewed and committed both, and
changed two lines of T024 (`npm prefix -g` reads stdout only) and added one test to T025 (the two `runtimes` stages
byte-identical).

**criteria_reestablished.** All eight of prompt 04's criteria. **No image lane has run on this branch** (Cycle 3's
and this cycle's changes together), so every Automated criterion is `unconfirmed`, with host results beside it,
labelled advisory.
- `04 · "a timelike announcement of at most 60 lines is present in each supported harness's user-level context location"` —
  **unconfirmed** (image lane pending; the cells were renamed and the bound became an ordering in Cycle 3).
- `04 · "and a test fails if any installed timelike tool is missing from it _(traces to: P3)_"` — **unconfirmed** (image
  lane pending). Host advisory: `tests/unit/test_announce.py` passed.
- `04 · "with fields for JSON support, interactivity risk and safer alternative _(traces to: P3)_"` — **unconfirmed**
  (image lane pending). Host advisory: test_announce passed; python3 and node now read `installed: true`, computed.
- `04 · "when either is known _(traces to: P1)_"` (the command-not-found answer) — **unconfirmed** (image lane pending).
  Host advisory: `tests/host/test_command_not_found.sh` 33/33; `tests/unit/test_missing_commands.py` 16 passed,
  1 skipped. The data now carries 14 `user` rows, and no runtime name.
- `04 · "persist across new shells _(traces to: P1)_"` (the bare installs) — **unconfirmed** (image lane pending:
  `tests/e2e/a-bare-python-package-install-and-a-global-node-package-install-succeed-without-privilege.bats`, 12
  cells). Host advisory:
  - the runtimes stage replayed under a scratch root: checksum OK, Node 24.21.0, CPython 3.14.7, marker removed;
  - a bare `pip install --no-index` of a test-built wheel went to `~/.local` through the prefix's `pip.conf`, and
    `python3 -I` could not import it;
  - `npm install -g --offline` of a packed package went to `~/.local` through the Node prefix's `npmrc`;
  - `tests/unit/test_agent_runtimes.py` passed.
- `04 · "free space on the workspace and scratch filesystems _(traces to: P2)_"` — **unconfirmed** (image lane pending).
  Host advisory: `tests/unit/test_budget.py` 73 passed.
- `04 · "uses a timelike tool it learned about from the environment's announcement _(traces to: D4)_"` — **observed by the
  operator**, the mode Cycle 1's Addendum 2 recorded (2026-10-07). Nothing new was observed this cycle.
- `04 · "is told the install command or the equivalent timelike tool _(traces to: D13)_"` — **unconfirmed**. The mentor
  captures D13 after the lane.

Each citation matches exactly one line of this send (`grep -cF` = 1 for all eight).

**reconcile_mode:** `scoped`. `audited_against` is now `[1, 13, 14]` (T033, the installed `audit-append` block:
`MODE=scoped`, `UNVERIFIED=14`, `REMOVALS_VISIBLE=yes` → `APPENDED=14`).
- **What revision 14 changed:** Feature text and one Environment constraint (struck and replaced). The Acceptance
  Criteria are byte-identical to revision 13's.
- **Amended, corrected by declared copy, not regenerated.** The body lines compared are in `audit-log.md`:
  FR-13, FR-15, FR-18, FR-19, SC-6, the python3 item and D-11. FR-25 to FR-31 and D-12 to D-15 are added.
- `full` would have appended 2–12 and left out 14 (verified).

**not_verified:**
- **Every image-level fact.** No Docker daemon here, so neither image was built.
  - The `runtimes` stage has not run under the real builder. Unverified: `ADD <url>` with ARG expansion, and the
    uv download.
  - The 12 SC-6 cells, the 2 P6 vanilla cells and Cycle 3's 27 new cells.
  - SC-1's six renamed cells.
- **The scan over the new runtimes.** Grype will see CPython, Node and npm's bundled packages in the agent and
  vanilla SBOMs. A finding with no fix is a baseline change, to raise after the lane, never to exempt silently.
- **Image size** (about +180 MB per image, estimated, not measured).
- **The handler and pip/npm at the image's exact versions:** they were tried with host or other versions.
- **The vanilla `npm prefix -g` with no network:** the update notifier is now outside the value read.

**changed_other_features:**
- **002 (bench):**
  - `bench/vanilla/Dockerfile` gains the same runtimes stage and the seven links, with stock behaviour, and its
    header and label say so;
  - the `Makefile`'s `bench-images` passes the four pins;
  - 002's spec is not modified here (02 s1 records it);
  - the catalog's "only what both images contain" rule is about tasks' prerequisites and stands.
- **001 (image and environment layer):**
  - `image/Dockerfile` (the runtimes stage, `/opt/agent`, the `PATH` in `ENV`);
  - `image/rootfs/etc/profile.d/00-timelike-path.sh`;
  - `pins.env`, `compose.yaml`.
- **The scan:** `scan/scan.sh` comments only.
- **Governance:** `tech-stack.md` 1.4.0, `quality-standards.md`, `constitution.md` (audit note).
- **README.md:** the status block (16 of 38; row 04 `complete (0, 1)`) and the vanilla bullet.
- **FOR-MENTOR.md:** Item 21 closed.
- **reboot.md:** brought up to date for a clear.

**process_failures_recorded:**
1. The plugin's `decision_tally` reports `sections_without_absent=3`, but every section has an ABSENT. T014's plain
   `ABSENT:` is mid-line (Cycle 3's slip). T024's and T025's are written `ABSENT (delegate):`, which the tally does
   not count. D107 taught it `FLAGGED (delegate)` and `ASSUMED (delegate)`, but not ABSENT. That last part is an
   upstream observation for the mentor to relay.
2. During T027, `tests/unit/test_bench_catalog.py` failed 12 setup steps at a 15 s timeout, under host load of
   about 9 (two delegates running). It failed the same way at `e0fb5a3`, and passed at load 2–3 in T031's full run.
   It's environmental, but noted: the suite is load-sensitive.
3. T022 is not ticked. It was superseded by Phase 7, and its closure is in T033's record, so `scope_tally` counts
   it as unrecorded.

**retired_prompts_seen:** `bridge/sends/04-rev13-20261008-161802.md` (replaced by this send, stale on both axes; Cycle
3 names it and stands as written).

**Seam 5 (`$HOME`), as the send asks:** `~/.local` now holds installed packages.
- **Chosen: no snapshot exclusion, because none is reachable** (spec FR-19, confirmed). The only workspaces that
  could contain `~/.local` are `~` and its ancestors, which 005 refuses; a workspace below `~` never contains it.
  No contract changes.
- `verify changed` sees `~/.local` only in a git repository rooted at `~`, where it lists installed files as untracked,
  as git would.

### Implement step 10 — quality validation (specswarm 2.37.0 blocks), as the library reported it

- `run_tests` rc=2 (pytest declared, not installed for `/usr/bin/python3`). `run_coverage` printed `unknown` (rc 1).
  Browser framework: `none`.
- `Quality Score: unknown — no component could be measured, so there is no score to compare`.
- The six exclusions: 2 attributed to this install, 2 to this machine, 2 not applicable.
- The gate is **UNKNOWN**: warned, not halted.
- Recorded as `.specswarm/metrics.json` → `007-cycle-4`, with the host figures beside it, unscored.

**Implement step 9b: decision log** (the plugin's `scope_tally` and `decision_tally` over all of 007, every cycle,
before T033's own records):

```
scope: planned=33 recorded=31 unplanned=0 unrecorded=2 in=24 out=0 none=8 unknown=0 flagged=28 flagged_out=0 other=4 other_out=0
decisions: sections=32 flagged_sections=28 non_flagged_sections=4 sections_without_absent=3 flagged=41 assumed=33 deferred=0 absent=29 inherited=28 low_confidence=0 flagged_low_confidence=0 flagged_delegate=10 assumed_delegate=9
```

There are no low-confidence decisions. Every `SCOPE:` record in Cycle 4 is `in` or `none`.

## Cycle 5 — bridge/sends/04-rev14-20261008-201729.md

Slice 1 of prompt 04, re-sent at prompt revision 14 / **discovery revision 15**, continued on `modify/007-slice-1`
(Cycles 3 and 4 stand, as the send says). Written 2026-10-08T20:44:52Z (from the clock). specswarm **4.0.1-botbaubble.2.37.0**, the
same session (2.38.0 and later are published, not installed; the send said not to reload). **Not merged, not pushed.**
This cycle covers **lane 007s1-a's fixes** (`bridge/feedback/04-20261008-193851-lane-007s1-a-three-cells-and-the-scan.md`)
and **revision 15** (`bridge/feedback/04-20261008-201205-fix-available-for-npm-bundled-libraries.md` § Resolution). It
changes `image/`, `bench/`, `scan/`, `tests/`, `pins.env`, `compose.yaml` and `Makefile`, so lane **007s1-b** comes
before sign-off. **This instance makes no commit until the mentor says that lane has ended.**

**How the cycle ran.** The lane fixes T034–T038 were built from the feedback file before this send arrived, as a by-hand
addendum to Cycle 4's tasks; the send folded them into this cycle, and `tasks.md`'s Phase 8 heading says so. Then
`/specswarm:modify 007 --from-send …` → plan → tasks → implement built revision 15 (T039–T045).

**The governance audit (14 → 15) is on this branch**, in T039 (`eff83ca`):
- `constitution.md` **1.4.2 → 1.4.3** (PATCH): H9 restates revision 5's "fix available", so it gains the clarification,
  with a Sync Impact Report;
- `tech-stack.md` **1.4.0 → 1.5.0**: npm's own pin and constraint, and an `npm` line the parser reads as approved;
- `quality-standards.md`: the bundled-component reading, the bundled class with its 30-day review, and the release
  check that fails closed.

All three record `[2..15]`, each with a prose note naming revision 15 and its source.

### Group A — cited from `.implement-complete`

Group A: not applicable — no marker on this path.

### Group B — copied from the send

| Field | Value |
|---|---|
| source_send | bridge/sends/04-rev14-20261008-201729.md |
| source_prompt | plan/.discover/prompts/04-announcements-discovery.md |
| prompt_revision | 14 |
| discovery_revision | 15 |
| slice | 1 of [0, 1] (intensity: natural) |

### Group C — written by the code instance

**delegations:** `[]`. No subagent and no sibling feature was used; the coordinator wrote every test this cycle.

**What was built.**
- **Lane item 1** (T034, `b3e29a6`): the SC-5 direct-exec cell reads docker's not-found message on either stream (measured
  on Docker 29.4.2 by the mentor: stdout), keeping non-zero, `tree`, "not found" and no timelike line.
- **Lane item 2** (T035, `a32641e`): 001's broken-interpreter cell drops every `PATH` entry that holds a `python3` and
  checks that premise first ("premise:", exit 3); C1 and C6 stay asserted. 001's test.
- **Lane item 3, no fix** (T036, `b7bcf5f`): GHSA-ch52-4w7c-c8xp (npm's bundled http-cache-semantics 4.2.0, origin "files
  under /opt/agent", with a new origin reason) and **CVE-2026-77214** (libexpat1, origin git) in **both** baselines,
  `timelike-agent.json` and `timelike-vanilla.json`, with the neighbours' review dates. **CVE-2026-77214 is not caused by
  this slice:** it is in the base layer's git and would block `master` too.
- **Lane item 3, fixable** (T038, `72825e7`): no Node 24.x newer than 24.21.0 exists, so **npm 11.21.0** is pinned
  (`NPM_VERSION`, `NPM_SHA512` = the registry's integrity as hex), checked with `sha512sum -c`, and replaces Node's bundled
  npm whole, in the `runtimes` stage of both images (still byte-identical). It fixes 4 of the 7: ip-address
  GHSA-mwp4-54f8-5fhr, tar GHSA-r292-9mhp-454m, brace-expansion GHSA-mh99-v99m-4gvg and GHSA-rgw5-rvv9-x895. **Route:**
  the second the ruling allows, because no Node release carries the fixes; nothing inside npm's tree is touched.
- **Lane item 4** (T037, `cd170e2`): a `pip-audit-agent` step in every image that carries `/opt/agent/python`, on its
  own line. The scanned image's agent interpreter lists its distributions as exact pins; the agent image's uv runs
  `pip-audit -r … --no-deps --disable-pip` over them (vanilla has no uv). quality-standards amended to match.
- **Revision 15, bundled-class entries** (T043, `b07f24f`): GHSA-6j4f-fj2g-mc7p (brace-expansion 5.0.9, fixed 5.0.10)
  and GHSA-qhr7-859c-m2p7 (fixed 5.0.11), both 2026-09-14, and GHSA-rfgv-xxqx-mfg5 (undici 6.28.0, fixed 6.28.1,
  2026-09-04), each naming **npm 11.21.0**, with its own `reviewed` 2026-10-08 and `review_by` 2026-11-07, in both
  baselines. Each records the scanner's fixed version for **that** advisory, so brace-expansion's two entries differ
  (5.0.10, 5.0.11), where the send's summary gave 5.0.11 for both; the gate holds each entry to the scanner's figure.
- **Revision 15, the release check** (T040 tests, T041 `ad90c36`, T042 `d5c3ba8`):
  - `evaluate.py releases` reads npm's packument from the registry and, for each stable, non-deprecated release published
    on or after the fix date whose `engines` admit Node 24.21.0, downloads the tarball, checks its sha512 integrity, and
    reads every bundled copy of the library. It writes `release-check.json`.
  - `report` lets a bundled-class finding through **only** on that check's `no-release` answer for the same fixed version.
    A release that ships the fix blocks, naming it and the `pins.env` edit. No answer, a stale answer or `unknown` blocks,
    with the escalation (component, library, why, what to do). **It fails closed.**
  - The entry is held to the image and the scanner: a different library version, or a fixed version other than the
    scanner's lowest stable fix, blocks with "re-review the entry". An entry past its own date, or over 30 days, blocks.
  - `scan.sh` runs it per image, from the agent image, **with network**, after pip-audit-agent; the step's detail is its
    summary, so the scan says what it checked (entries, Node, releases examined, states).
  - **Generic over the component by a table; npm is implemented.** pip answers `unknown` (so it blocks) and says what its
    reader needs: PyPI's JSON for stable pip releases whose `requires_python` admits the agent interpreter, and each
    candidate wheel's `pip/_vendor/vendor.txt`.

**criteria_reestablished.** All eight of prompt 04's criteria. **No image lane has run on this cycle's tip**, so every
Automated criterion is `unconfirmed`, with lane 007s1-a's result and host results beside it, labelled.
- `04 · "a timelike announcement of at most 60 lines is present in each supported harness's user-level context location"` —
  **unconfirmed** (lane 007s1-b pending). Lane 007s1-a passed these cells at `41d4b5f`; this cycle did not touch them.
- `04 · "and a test fails if any installed timelike tool is missing from it _(traces to: P3)_"` — **unconfirmed** (lane
  pending). 007s1-a passed; host advisory: `tests/unit/test_announce.py` passed.
- `04 · "with fields for JSON support, interactivity risk and safer alternative _(traces to: P3)_"` — **unconfirmed** (lane
  pending). 007s1-a passed; untouched here.
- `04 · "when either is known _(traces to: P1)_"` (the command-not-found answer) — **unconfirmed** (lane pending). 007s1-a
  failed one cell here (not ok 94, the direct-exec stream), fixed in T034; host advisory: the cell's functions under
  bats 1.14.0 against a stub docker (stdout ok, stderr ok; a timelike line, exit 0 and a daemon error each fail).
- `04 · "persist across new shells _(traces to: P1)_"` (the bare installs) — **unconfirmed** (lane pending). 007s1-a passed
  every SC-6 cell with npm 11.19.0; this cycle changes npm to 11.21.0 (host replay: checksum OK, `npm --version` 11.21.0,
  links resolve).
- `04 · "free space on the workspace and scratch filesystems _(traces to: P2)_"` — **unconfirmed** (lane pending). 007s1-a
  passed the budget cells; untouched here.
- `04 · "uses a timelike tool it learned about from the environment's announcement _(traces to: D4)_"` — **observed by the
  operator**, as Cycle 1's Addendum 2 recorded (2026-10-07). Nothing new was observed this cycle.
- `04 · "is told the install command or the equivalent timelike tool _(traces to: D13)_"` — **unconfirmed**. The mentor
  captures D13 after a passing lane.

Each citation matches exactly one line of this send (`grep -cF` = 1 for all eight).

**reconcile_mode:** `scoped`. `audited_against` is now `[1, 13, 14, 15]` (T045, the installed `audit-append` block:
`MODE=scoped`, `N=15`, `UNVERIFIED` empty, `REMOVALS_VISIBLE=yes` → `APPENDED=15`).
- **The library's provenance row is 4**: the prompt is still at revision 14, which was already audited, so the library
  finds nothing new. **15 is appended on the send's instruction**, and `audit-log.md` says so.
- **What revision 15 changed:** a clarification of revision 5's "fix available", and npm's constraint in stack.md. No
  prompt and no criterion changed (the Acceptance Criteria of `04-rev14-20261008-174220` and this send are byte-identical).
- **Needs no body change.** The spec was checked for the scan's fixable rule: FR-30 describes the scan and stays true; it
  gains a declared addition, and FR-32 to FR-34 are added (§ Slice 1, cycle 5). Nothing regenerated.

**not_verified:**
- **Every image-level fact for this cycle's tip.** No Docker daemon here:
  - npm 11.21.0 under the real builder (`ADD` of the registry URL with ARG expansion; the RUN's npm lines were replayed
    on the host only);
  - the three e2e cell fixes (T034, T035) against the real container;
  - `pip-audit-agent` in the real scan (`-r --no-deps --disable-pip` was tried on the host with pip-audit 2.10.1);
  - **the release check from inside the scan container**: whether the image's timelike interpreter reaches
    registry.npmjs.org over TLS. If it cannot, the three findings block, by design, and the escalation says why.
- **Grype's view of npm 11.21.0's tree.** The host replay shows brace-expansion 5.0.9, ip-address 10.5.0, tar 7.5.22,
  undici 6.28.0, with no nested copies; which advisories grype then reports is the lane's. Any new finding in the rest of
  npm 11.21.0's tree is unknown until then.
- **The verdict end to end** was run only over lane 007s1-a's scan output **edited** to npm 11.21.0's versions (synthetic,
  labelled in T044): both images PASS, 0 blocking.
- **SC-7's limited throwaway** still needs a lane host with at least 2 CPUs.

**changed_other_features:**
- **001 (image and environment layer):** `image/Dockerfile` (npm in the runtimes stage); `pins.env`, `compose.yaml`;
  **001's test** `tests/e2e/conformance-check-over-every-timelike-tool-on-path.bats` and its fixture
  `tests/e2e/fixtures/timelike-envpython` (T035: the premise restored, C1 and C6 kept).
- **002 (bench):** `bench/vanilla/Dockerfile` (the same npm step; the stages stay identical) and the `Makefile`'s
  `bench-images` (the npm pins).
- **The scan gate** (shared by every feature): `scan/scan.sh` (pip-audit-agent, release-check), `scan/evaluate.py`
  (bundled class, release check, the step column widened to 17), both baselines, `tests/unit/test_scan_report.py`.
- **Governance:** `constitution.md` 1.4.3, `tech-stack.md` 1.5.0, `quality-standards.md`.
- **README.md:** unchanged. The send's README block (16 of 38; row 04 `complete (0, 1)`) was applied in Cycle 4 (T032) and
  matches word for word; the generated reference is current (no help moved).
- **reboot.md:** brought up to date for a clear.

**process_failures_recorded:**
1. **A helper failed after committing, and its re-run committed twice.** The rebuilt `ct.sh` (reboot.md's recipe) sourced
   the installed scope-check block under `set -e`, where a `grep` with no match ends the script. T034's first run had
   committed (`b3e29a6`) before failing; reading the failure as "nothing committed", I re-ran it, which added
   `ad93ac9` (a duplicate decision entry only). It was dropped with `git reset --keep b3e29a6` within the minute (local,
   unpushed, no lane running), and the helper now sources the block under `set +eu`. Lesson: read `git log` before
   re-running anything that commits.
2. **A stray `git stash`** in the Gödel worktree (a command left at the end of a script) stashed the staged change; it was
   restored with `git stash pop --index` and checked byte for byte before the commit. The Gödel commit was then amended
   once (local, unpushed) to quote the tracked-tree PASS line, which a `tail -1` had replaced with the per-id line.
3. **T037's decision said "116 passed"; the run said 114.** Corrected in place in T045, with the correction named in the
   line.
4. **One red commit window:** between T041 (`ad90c36`) and T042 (`d5c3ba8`), `test_scan_report.py`'s scan.sh cells fail
   (the evaluator expects a `release-check` row that scan.sh did not yet write). T040 (`71fc5cc`) is red by design
   (tests first).
5. The plugin's `decision_tally` still reports `sections_without_absent=3`, as in Cycle 4 (T014's mid-line ABSENT; two
   `ABSENT (delegate):` lines it does not count). No new case this cycle.

**retired_prompts_seen:** `bridge/sends/04-rev14-20261008-174220.md` (replaced by this send, stale on the discovery axis;
Cycle 4 names it and stands as written).

**For the mentor (lane 007s1-b):**
- Expect the three bundled entries to pass through the baseline **with the release check having run**: the
  `release-check` row should read "3 bundled-class entries checked against npm's released tarballs (Node 24.21.0;
  releases examined: 11.20.0, 11.21.0, 12.1.0, 12.2.0): 3 no-release" for the agent and vanilla images, and none for Adele
  and the bench driver.
- If the scan container cannot reach the registry, those three block with "release check could not run …; it fails
  closed". That is the ruling working, not a defect in the entries.
- The five new baseline entries (two ordinary, three bundled) are for your review at sign-off.

### Implement step 10 — quality validation (specswarm 2.37.0 blocks), as the library reported it

- The detector found `pytest`. `run_tests` rc=2 (declared, not installed for `/usr/bin/python3`). `run_coverage` printed
  `unknown` (rc 1). Browser framework: `none`.
- `Quality Score: unknown — no component could be measured, so there is no score to compare`.
- The six exclusions, by the `unmeasured-explains-itself` rule: 2 attributed to this install (bundle size, visual
  alignment), 1 to this machine (unit tests), 2 not applicable (integration, browser), and 1 unattributed (coverage,
  whose reason as written here, "run_coverage printed unknown", names neither; Cycle 4 wrote it with "on this machine").
- The gate is **UNKNOWN**: warned, not halted.
- Recorded as `.specswarm/metrics.json` → `007-cycle-5`, with the project's figures beside it, unscored (host lane 1877
  passed + 1 skipped; `scan/evaluate.py` 97% from its three test files).

**Implement step 9b: decision log** (the plugin's `scope_tally` and `decision_tally` over all of 007, every cycle, before
T045's own records):

```
scope: planned=45 recorded=43 unplanned=0 unrecorded=2 in=35 out=0 none=9 unknown=0 flagged=37 flagged_out=0 other=7 other_out=0
decisions: sections=44 flagged_sections=37 non_flagged_sections=7 sections_without_absent=3 flagged=54 assumed=48 deferred=0 absent=41 inherited=40 low_confidence=0 flagged_low_confidence=0 flagged_delegate=10 assumed_delegate=9
```

There are no low-confidence decisions. Every `SCOPE:` record in Cycle 5 is `in` or `none`.

**Git workflow (implement step 11):** option 2, stay on `modify/007-slice-1`. The merge is `--no-ff` after the mentor's
sign-off, with `maint/readme-godel` (`866b49b`, `ad4d63f`).

### Addendum — lane 007s1-b: Go 1.27.2 (2026-10-09T01:16:28Z, read from the clock)

- **Finding** (mentor, `bridge/feedback/04-20261009-010500-lane-007s1-b-go-1.27.2-and-a-host-event.md`, lane 007s1-b at
  `3d0b9f9`): item 1, `timelike-adele` FAIL. govulncheck v1.8.0 over `adele/` on `golang:1.27.1-trixie` found 9
  reachable stdlib advisories, all high, all fixed in Go 1.27.2. Lane 007s1-a, five hours earlier on the same pin, read 0.
  Not caused by this slice.
- **Fix (`a7e1f2f`):** `pins.env` `GO_IMAGE` → `golang:1.27.2-trixie@sha256:e58d6f83b3416618d8bcac2b3dde1b7f7e3c4a77d25e88637f8bbae81536c48d`.
  This is revision 5's fix-available rule, so there are no baseline entries.
  - I re-read the index digest from Docker Hub's registry API on 2026-10-09. It matches the mentor's reading, and the
    index carries linux/amd64.
  - go.dev's release list gives go1.27.2 as current.
  - Nothing else pins the Go patch version: `adele/go.mod` says `go 1.27` (no `toolchain` line); govulncheck and lint
    run in `GO_IMAGE`; `tech-stack.md` says `Go 1.23+`. Citations of 1.27.1 in earlier cycles' records and in test
    fixtures are history or synthetic input, and stay.
  - In passing: the `1.27.1-trixie` tag now resolves to a different index (`sha256:8f58fd67…`) from the one pinned.
    The tag was rebuilt upstream, and the digest pin is why the lane did not follow it.
- **Host check (advisory; scratch Go 1.27.2, tarball SHA-256 checked against go.dev):** in `adele/`, `go test
  -count=1 -cover ./...` passes for all 6 packages. `gofmt -l` is empty and `go vet` is clean. **govulncheck v1.8.0:
  "No vulnerabilities found."**
- **Found, not fixed: staticcheck v0.8.1 cannot read Go 1.27.2's standard library.** It fails with `internal error in
  importing "internal/cpu" (cannot decode …, export data version 5 is greater than maximum supported version 4)`, exit 1.
  - It runs clean under Go 1.27.1, and the failure is the same with a fresh cache.
  - v0.8.1 is the newest staticcheck release (module proxy, 2026-10-09).
  - Rebuilding v0.8.1 against `golang.org/x/tools` v0.50.0 makes it clean on 1.27.2 (a scratch build, not committed).
  - Only `make lint` runs staticcheck. `make test`, `bench-images` and `scan` don't, so lane 007s1-c is unaffected,
    but `make lint` will fail on this pin. Raised to the mentor in the report, not changed here: the remedy is a choice
    between pins, not a lane fix.
- **Host lane:** `make test-host` failed once with a cause I didn't capture (I kept only the tail, which showed the
  env, hook and handler suites passing). It then passed: 1877 passed, 1 skipped; env 60/60, hook 44/44, handler 33/33.
  A third run also passed with the same counts (417.9 s, against 310.1 s for the second). Item 2 (the vanilla image missing, and the stalled Go and pytest
  stage) needs no change, per the feedback; lane 007s1-c shows whether it recurs.
- **Not verified here:** the adele image build and the scan on 1.27.2 (no Docker in this instance). They are
  `unconfirmed` until lane 007s1-c.

### Addendum — staticcheck in a lint-only Go image (2026-10-09T02:04:01Z, read from the clock)

- **Ruling** (mentor, `bridge/feedback/04-20261009-010500-…` § Amendment 2026-10-09T01:40Z): staticcheck runs in a
  lint-only Go image at the previous pin until a staticcheck release reads Go 1.27.2. gofmt and `go vet` stay on
  `GO_IMAGE`. The ruling turned down two alternatives: the x/tools rebuild (not a released tool) and leaving lint red.
- **Fix (`de5aebe`):**
  - `pins.env` gains `GO_LINT_IMAGE=golang:1.27.1-trixie@sha256:3b77fc618ec235a1ab412de7737f120dd507c57e8d87de4cbb7994fb94275ed5`,
    with a comment giving the reason and the removal condition.
  - `make lint`'s Go step is split in two:
    - gofmt and `go vet` run in `GO_IMAGE` and print `go version` first;
    - staticcheck runs alone in `GO_LINT_IMAGE` and prints `staticcheck on <go version>`.
  - `lint-host` uses the host's Go, runs no staticcheck and pins nothing, so it is unchanged.
  - `quality-standards.md` records the removal item under its lint rule. `reboot.md` § Open items records it with the
    command that checks for a new release. `tech-stack.md` is unchanged (`Go 1.23+`), as the ruling says.
- **Checks (host, advisory; no Docker in this instance):** each command of `make lint`, run with the pinned versions.
  - **Go:**
    - gofmt and `go vet` on `go1.27.2 linux/amd64`: clean.
    - `go run honnef.co/go/tools/cmd/staticcheck@v0.8.1 ./...` on `go1.27.1 linux/amd64`: clean.
  - **Python:** ruff 0.16.9 check and format, clean (79 files formatted); `mypy --strict`, no issues (27 files).
  - **Shell:** shellcheck 0.11.0 over `SHELLCHECK_FILES` (75 files), clean.
  - **Units:** the four pin-related files, 230 passed.
  - **Unconfirmed:** `make lint` itself, run in the images, until someone with Docker runs it.
