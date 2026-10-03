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
