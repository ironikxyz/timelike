# Impact Analysis: Modification to Feature 002

**Feature**: Speedup bench (slice 0)
**Modification**: The report explains itself (D2 findings), carried by `bridge/sends/02-rev1-20260929-080659.md`
**Analysis Date**: 2026-09-29
**Provenance**: prompt revision 1, already in `audited_against [1]` (modify row 4), so nothing is reconciled and `audit-log.md` gets a `none` row

---

## Section 1 — D2 report findings (send `…-080659`)

### Proposed changes

The operator read `bench/out/20260929T022053Z/report.txt` for D2 and misread 2 of 5 questions:
- **The first line's caveat did not land.** The operator: "humans read statements, lawyers read
  caveats."
- **The one loss was read backwards.** The report showed `failed (check failed: exit 1)` and never said
  what the task tests.

Three changes, whose outcomes the send fixes and whose design is ours:
1. **The first line** of a fake-agent report becomes the operator's text, verbatim.
2. **Every task section explains itself:**
   - the capability tested
   - what differs between the images for that task
   - what happened in each arm, call by call
   - how each arm ended, and why
   - why the verdict is what it is
3. **What was read correctly is kept:** losing cases first, the identity line, the reproduce command,
   and tokens only in the appendix.

### Affected components

| Component | Change | Impact |
|---|---|---|
| `bench/benchlib/report.py` | `render(…, tasks=…)` replaces `goals=`. New per-task explanation block. New first line | Medium: every report line after the header changes. The verdict rule and the section order are unchanged |
| `bench/benchlib/catalog.py` | New fields `difference` and `notes`. Every check prints a plain reason when it fails. Task versions bumped to 2 | Low: setup and policy are unchanged. A trace records `task_version: 2` |
| `bench/bin/timelike-bench` | Passes the catalog's texts to the report. The `FAKE_SCOPE` wording changes | Low: the header scope changes |
| `tests/e2e/fixtures/validate_bench.py`, `speedup-bench.bats` | The new first line; each task section must carry its explanation | Low |
| Units: report, cli, validator, catalog | Updated to the new wording and parameters | Low |
| README, `contracts/bench-cli.md`, quickstart, spec FR-9 | Wording, and the new report block | Documentation |

### Breaking changes

**None outside this feature.** The trace schema (v1) is unchanged, so traces from `8ce6173` still
load, and `timelike-bench report` over them renders with the new wording. `render`'s keyword changes
from `goals` to `tasks`; its only caller is the CLI.

### Risks

| Risk | Mitigation |
|---|---|
| Explanations written with the task could describe an outcome that did not happen (cross-stack P005) | A note is keyed by `environment:ending` and printed only when the run actually ended that way. Everything else is derived from the trace: the calls, exit codes, stderr lines and the check's own reason |
| A longer report buries the verdict | Each task opens with the capability tested and one "Verdict:" line in words, before the metrics table |
| "token" leaks above the appendix through new free text | The existing unit over the real catalog, and the validator, both catch it |

**Proceed:** yes. Risk is low.

---

# Cycle 2: revision 8 recorded (send `bridge/sends/02-rev8-20261008-095251.md`, discovery revision 13)

**Analysis date:** 2026-10-08T09:56Z. specswarm **4.0.1-botbaubble.2.37.0** loaded: the modify text expanded
`PLUGIN_DIR` to the 2.37.0 cache path, and this session's pid is in 2.37.0's `.in_use` (lore specswarm Q002).

**Provenance:** modify row 7, computed by executing the command's `provenance-inputs` and `provenance-row`
blocks. `source_prompt` and the send's `> Source:` agree (`plan/.discover/prompts/02-speedup-bench.md`); the
prompt is at revision 8, `prompt_revision` is 1, `audited_against` is `[1]`.

**Classifying revisions 2–8 (lore P004: what was compared).** The prompt bodies of the three archived sends
for prompt 02 were diffed, from the `# Speedup bench` heading to the end:
- `02-rev1-20260929-000641.md` and `02-rev1-20260929-080659.md`: identical.
- `02-rev1-20260929-080659.md` against `02-rev8-20261008-095251.md`: **three additions and nothing else** —
  the revision note, one constraint under *From Principles*, one slice-1 Automated criterion. No line removed
  or reworded, so removals and rewordings are visible and none occurred. Revisions 2–7 did not change prompt
  02 (its `revision` field is 8 and the body is otherwise byte-identical to revision 1's).
- **Revision 8: INCOMPLETE (added), not SUPERSEDED.** The spec body was read for any statement of a verdict
  order, a tiebreak or how a hung call is counted:

| Body line | What it says | Against revision 8 |
|---|---|---|
| `spec.md:20` (Overview) | the report gives completions, turns, tool calls, failed commands, hangs, wall-clock | true; the constraint keeps all six reported |
| `spec.md:75–77` (Scenario 3) | the report compares in completion, turns and failed commands, with hangs, tool calls and wall-clock beside them, and says why the verdict is what it is | true; names no order |
| `spec.md:160–166` (FR-9 headline figures) | completion, turns, failed commands (non-zero exits), hangs, tool calls, wall-clock | true; a hung call is non-zero (T016), which matches *"a hung call is one failed command and one hang"* |
| `spec.md:171–176` (FR-9a) | the verdict in words, naming what decided it | true; states no order |
| `spec.md:216–218` (Success Criteria preface) | slice-1 and slice-2 criteria are **not** in this spec | true; the spec keeps no later-slice criterion list, so the new slice-1 criterion is not copied |
| `spec.md:258–264` (Out of Scope) | all slice-1 and slice-2 criteria are out of scope | true; the new slice-1 criterion is among them |

  **No body line is false. Do not regenerate.** The body states no tiebreak order at all.

**The constraint is unmet by slice 0's code, by plan's ruling (b) carried to 02 s1** (`bridge/feedback/02-20260930-060406-hang-counted-twice.md`, § What code/ changes). The four places, read, not edited:

| Place | What it says now | Against the constraint |
|---|---|---|
| `bench/benchlib/report.py:119` | the third tiebreak is `_sign(v.nonzero_exits + v.hangs, t.nonzero_exits + t.hangs)` | unmet: hangs are not compared on their own before failed commands, and a hung call counts twice |
| `bench/benchlib/report.py:227` | the verdict sentence prints `vf, tf = v.nonzero_exits + v.hangs, …` as "failed or hung commands" | unmet: quotes a sum that is not a count in the report's table |
| `data-model.md:125` (§ Comparison and report, step 3) | "compare `nonzero_exits + hangs` (fewer wins)" | unmet: the design states the old order |
| `decisions.md` T016, the fourth ASSUMED line | the sum "counts a hung call twice … as data-model reads literally" (confidence: medium) | the origin; superseded by revision 8 |

**Proposed change:** the spec only, plus the T016 annotation. No code, test, contract or data-model change, so
nothing outside `.specswarm/features/002-speedup-bench/` changes and no Docker lane is needed (send § How this
cycle runs).

| Component | Change | Impact |
|---|---|---|
| `spec.md` § Reporting | revision 8's constraint copied in, declared, with a note that slice 0 does not meet it and where it is carried | none on behaviour |
| `spec.md` frontmatter `audited_against` | 8 appended (Step 9) | provenance only |
| `decisions.md` T016 | an annotation: superseded by discovery revision 8 (ruling (b)), code change carried to 02 s1 | record only |
| `audit-log.md` | one row | provenance only |
| `bench/`, `data-model.md` | **none** (the send forbids it) | — |

**Breaking changes:** none. **Risk:** low; documentation only. **Proceed:** yes.
