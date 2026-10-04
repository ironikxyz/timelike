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
