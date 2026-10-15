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

# Cycle 3: revision 8 re-recorded as `carried` (send `bridge/sends/02-rev8-20261009-043302.md`, discovery revision 15)

**Analysis date:** 2026-10-09T04:39Z. specswarm **4.0.1-botbaubble.2.40.0** loaded. The modify text expanded `PLUGIN_DIR`
to the 2.40.0 cache path, and its `audit-append` block accepts `MODE=carried`: run with the send's inputs, it returned
`MODE_USED=carried`, not `none`. Both versions' `.in_use` files are empty this time, so that signal reads nothing.

**Provenance:** modify **row 4**, computed by executing `provenance-inputs` and `provenance-row`. `source_prompt` and
the send's `> Source:` agree (`plan/.discover/prompts/02-speedup-bench.md`). N=8, `prompt_revision` 1,
`audited_against` `[1, 8]`. Revision 8 is listed, so on its own the library finds nothing new and skips Step 9.
**The send asks for the `carried` record anyway**, so the block runs on its instruction, and `audit-log.md` says so.

**What was compared (lore P004).** This send's prompt body is byte-identical to Cycle 2's send
(`02-rev8-20261008-095251`), from `# Speedup bench` to the end (`diff` empty). Revisions 14 and 15 did not revise
prompt 02, which is still at revision 8.

**The four places, re-read on `master` `ec71f3d`.** All four still contradict revision 8, so `carried` stands:
- `bench/benchlib/report.py:119`: `_sign(v.nonzero_exits + v.hangs, t.nonzero_exits + t.hangs)`, the summed tiebreak.
- `bench/benchlib/report.py:227`: the same sum, with `:231` quoting it as "failed or hung commands". (Cycle 2 cited
  `:227`, where the sum is computed; the phrase is on `:231`.)
- `data-model.md:125`, step 3: "compare `nonzero_exits + hangs` (fewer wins)".
- `decisions.md` T016: the origin, annotated in Cycle 2 and still in place.

`report.py` is unchanged since `4662060`, and `bench/` changed since Cycle 2's lane only in `bench/vanilla/Dockerfile`
(007 slice 1's runtimes parity), which is none of the four.

**Impact:** none on code, contracts or other features. Records only: one `audit-log.md` row, the cycle report and
this feature's cycle artifacts. `spec.md` is unchanged, including `audited_against`. Risk: low.

# Cycle 4: 02 slice 1 (send `bridge/sends/02-rev8-20261013-064725.md`, discovery revision 15)

**Analysis date:** 2026-10-13T07:08:58Z. specswarm **4.0.1-botbaubble.2.44.0** loaded (`claude plugin list`, and the
`PLUGIN_DIR` the modify text expanded). Branch `modify/002-slice-1` from `master` `8dbddc7`.

**Provenance:** modify **row 4**, computed by executing `provenance-inputs` and `provenance-row`. `source_prompt` and
the send's `> Source:` agree (`plan/.discover/prompts/02-speedup-bench.md`). N=8, `prompt_revision` 1,
`audited_against` `[1, 8]`. Nothing is new upstream: prompt 02 is still at revision 8. This cycle is **added work on
a body that stays true** (the send: do not re-specify, do not regenerate), and it does revision 8's code work, which
Cycle 3 recorded as `carried` here.

## Proposed changes

Slice 1 of prompt 02: four Automated criteria and D11 (Manual), plus revision 8's four places.
- **Functional:** told and not-told timelike arms beside vanilla; a live harness path (OpenCode and a second
  harness) beside the fake agent; failure categories per failed call; timelike tool invocations counted per arm;
  the verdict order of revision 8; caps, a dry-run plan and spend accounting for live runs; a key file read by the
  bench and passed to the harness process only.
- **Data:** trace schema **2** (an arm, per-call category and tool names, a `stopped` ending for infrastructure
  causes, spend). Schema 1 traces are refused by the new reader, naming the revision that can re-report them.
- **Contracts:** `contracts/trace-schema.md` and `contracts/bench-cli.md` (this feature's own). No other feature's
  contract changes: the told arm runs `timelike announce --install` exactly as the agent image's entrypoint does
  (007's placement, unchanged).
- **Images:** a new bench image, `timelike-bench-harness:local`, holding the pinned harness binaries and mounted
  read-only into task containers at run time. **Neither the agent image nor the vanilla image changes.**

## Affected components

| Component | Type | Impact | Notes |
|---|---|---|---|
| `bench/benchlib/report.py` | report | High | verdict order (revision 8), arms, harnesses, categories, adoption, `stopped` rows |
| `bench/benchlib/trace.py` | schema | High | schema 2; list and float fields; derived adoption and category totals |
| `bench/benchlib/runner.py` | runs | High | arms; the told placement; live runs through a harness adapter |
| `bench/bin/timelike-bench` | CLI | High | `--harness`, `--arm`, `--dry-run`, caps, the key file, `categories --probe` |
| `bench/run.sh` | host side | Medium | `BENCH_KEY_FILE` (checked on the host, mounted read-only), the harness image, the network |
| `bench/benchlib/catalog.py` | catalog | Medium | one task added (`python-missing-module`); goals as plain words for a live agent |
| new: `categories.py`, `harness.py`, `relay.py`, `secrets.py`, `standin.py`, `transcripts.py` | bench | New | categories, adapters, the model relay, the write gate, the stand-in, the parsers |
| `bench/harness/Dockerfile`, `pins.env`, `Makefile` | images | Medium | the harness image, pinned by version and npm integrity |
| `tests/e2e/speedup-bench.bats`, `tests/e2e/fixtures/validate_bench.py` | tests | Medium | schema 2; arms; the live path against the stand-in; categories in both images |
| `README.md` | docs | Low | the send's README block, if all four Automated criteria are met |

**Other features:** none changed. 001's `agentio` and output contract are used as they are; 003's `run` verdict, 004's
Adele denial, 007's command-not-found handler and 013's guard and shims are **read** (their texts are matched by the
categories), never changed.

## Breaking changes

- **Trace schema 1 → 2.** A slice-0 trace set is not re-reported by this build; the refusal names the reason and
  that slice 0's revision re-reports it (FR-10 holds per revision). Nothing outside the bench reads traces.
- **`timelike-bench run`'s default** still runs the fake agent, now in three arms instead of two. CI keeps its key-free
  path (FR-12 unchanged, and widened: a set `BENCH_KEY_FILE` also refuses a fake-agent run).

## Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| OpenRouter rejects a request shape a harness sends (Codex's `namespace` tool) | Medium | A harness's live cells end `stopped` | named per row; the first live run is its own test tier (llm-apis Q001) |
| The scan gate flags the harness binaries | Medium | `make scan` fails | the image is scanned like every bench image; findings go through the operator's baseline rule |
| The `--volumes-from` copy of ~480 MB slows a run | Low | minutes per invocation | one harness container per invocation, not per run |
| The model stand-in proves only the harness parses what timelike wrote (P005) | Certain | parser trusted too far | transcripts are the harnesses' own output; the live run is a tier of its own |

**Proceed:** yes, with one item raised as FOR-MENTOR Item 25 (the key's route), not built.
