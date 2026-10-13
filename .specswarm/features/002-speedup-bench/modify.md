# Modification: Feature 002 — Speedup bench

**Status**: Active
**Created**: 2026-09-29
**Send**: `bridge/sends/02-rev1-20260929-080659.md`. It continues cycle 1, with the same prompt revision
(1) and the same slice (0)
**Impact Analysis**: [impact-analysis.md](impact-analysis.md)

## Modification summary

**What:** the report explains itself. The first line now states what the run is. Each task section
says, in plain words, what it tests, what happened in each arm, and why the verdict is what it is.

**Why:** SC-3 (D2). The operator read the report as the Adopting developer and misread it twice:
- they took the fake-agent report as evidence
- they read timelike's one loss backwards

The operator chose to hold the merge until the report explains itself. SC-3's text is unchanged. What
changes is what the report must contain for SC-3 to be met.

## Functional changes

**F001 — First line.**
- **Current:** `FAKE-AGENT RUN — this report proves the bench pipeline, not timelike's value. The
  agent's policy was written by timelike's own builders.`
- **Proposed:** the operator's text, verbatim:
  `FAKE-AGENT BENCH PIPELINE DEMO RUN -- This is not a test of timelike, rather a test of the bench
  test itself (its presentation and usefulness to the human user). The agent's policy was written by
  timelike's own builders.`
  It applies to any report touched by a fake-agent run. The tool's header scope follows it:
  `[FAKE-AGENT BENCH PIPELINE DEMO RUN -- not a test of timelike]`.
- **Breaking:** no.

**F002 — Every task section explains its outcome, from the report alone.** Under the task heading:
- `Tests:` the catalog's capability, and what differs between the two images for this task. That is a
  fact about the environments, not a claim about the outcome.
- `Verdict:` the verdict in words, derived from the traces: which ending ranked higher, or which turn
  or failure count decided, or why it is a tie.
- The metrics table (unchanged). The failure row now says hung calls are included.
- For each arm, `What happened in <arm>:`
  - each call with its exit and the first line of stderr for a failed call; a hung call says it was
    killed at the limit
  - then how the run ended, and why: the check's own plain reason when the check failed
  - then a note written with the task, **printed only when the run ended the way the note describes**
    (keyed `environment:ending`)
- **Breaking:** no. The trace schema is unchanged; `render` takes `tasks=` instead of `goals=`.

**F003 — Checks say why they failed.** Every catalog check prints a one-line reason to stderr when it
fails. For example: "the commit contains a TODO line, which this repository's pre-commit hook
forbids". Before, it exited 1 silently. Task versions go to 2, because the check text changed.

**Kept:** losing cases first, the identity line, the reproduce command, tokens only under the appendix,
and the not-benchable section.

## Acceptance

Written for the reader, not the test: **a reader who sees only the report can say correctly why
timelike lost `git-commit-hook-rejects`.** The mentor re-interviews the operator on the new report.
Until then SC-3 stays `unconfirmed`.

## Tech stack compliance

No new technology. Stdlib Python and bash, as before.

---

# Cycle 2: revision 8 recorded (send `bridge/sends/02-rev8-20261008-095251.md`)

**Status:** Active. **Created:** 2026-10-08. **Impact analysis:** `impact-analysis.md` § Cycle 2.

## Modification summary

**What:** record discovery revision 8 against 002's spec. No behaviour changes.

**Why:** revision 8 (plan `7ce212b`, ruling (b) on `bridge/feedback/02-20260930-060406-hang-counted-twice.md`)
added one constraint (the verdict order: ending, turns, hangs, failed commands, each call counted once) and one
slice-1 criterion. It amended nothing, so the body stays true; the spec was UNAUDITED against it.

## Proposed changes

- **F001 · The constraint in the spec, declared.**
  - **Current:** the spec states no verdict order.
  - **Proposed:** revision 8's constraint, verbatim and marked *(Added revision 8.)*, under § Reporting, with
    a note that slice 0's code does not meet it (`report.py:119`, `:227`; `data-model.md:125`) and that plan's
    ruling carries the change to 02 slice 1.
  - **Breaking:** no.
- **F002 · T016's assumption marked superseded.** An annotation on `decisions.md` T016, the ASSUMED line kept.
- **Not copied:** the slice-1 criterion. The spec keeps no list of later-slice criteria (`spec.md:216–218`);
  § Out of Scope already excludes all slice-1 criteria.

## Contract and code changes

None. `report.py` and `data-model.md` are not edited (the send's § 1).

# Cycle 3: revision 8 re-recorded as `carried` (send `bridge/sends/02-rev8-20261009-043302.md`)

**Status:** Active. **Created:** 2026-10-09. **Impact analysis:** `impact-analysis.md` § Cycle 3.

## Modification summary

**What:** re-record revision 8 against 002 as `carried` to 02 slice 1. No behaviour changes and no spec change.

**Why:** Cycle 2 recorded revision 8 as `scoped`, which says the modification brought the feature into line with
revision 8. It did not, by design. Plan's ruling (b) (`bridge/feedback/02-20260930-060406-hang-counted-twice.md`)
carries the code change to 02 slice 1, and Cycle 2's `not_verified` names the four unmet places. specswarm 2.37.0
had no mode for "examined, work outstanding". 2.40.0 has `carried`.

## Proposed changes

- **F001 · One `audit-log.md` row**: mode `carried`, revision 8, destination 02 slice 1, the ruling as its basis,
  and the block's inputs and outputs quoted. It supersedes Cycle 2's mode for revision 8. Cycle 2's row stays as
  written, because the log is append-only.
- **F002 · `audited_against` unchanged** at `[1, 8]`: 8 is already listed, so the append adds nothing.
- **Not changed:** the spec body, `prompt_revision`, `report.py`, `data-model.md`, `decisions.md` T016. The fix is
  02 slice 1's work.

## Contract and code changes

None.

# Cycle 4: 02 slice 1 (send `bridge/sends/02-rev8-20261013-064725.md`)

**Status:** Active. **Created:** 2026-10-13. **Impact analysis:** `impact-analysis.md` § Cycle 4.

## Modification summary

**What:** slice 1 of prompt 02. Told and not-told arms, two live harnesses beside the fake agent, failure categories,
timelike tool invocations per arm, and revision 8's verdict order, which slice 0 did not meet.

**Why:** the send (natural intensity). Revision 8's code work was carried here by Cycle 3.

## Proposed changes

- **F001 · Verdict order (revision 8):** ending, turns, hangs, failed commands; one count per call per row; the
  sentence quotes table counts only (FR-48). The four places: `report.py`'s tiebreak and sentence, `data-model.md`
  step 3, and decisions T016 (annotated).
- **F002 · Arms (SC-4):** `vanilla`, `not-told`, `told` (FR-17 to FR-20).
- **F003 · Live harnesses (SC-5):** OpenCode 1.19.0 and Codex CLI 0.162.1, pinned, mounted read-only into task
  containers; a relay in the driver; caps and a plan; the key file and the write gate (FR-21 to FR-37, FR-50).
- **F004 · Categories (SC-7):** one per failed call; a probe that produces each category in both images (FR-40 to
  FR-43).
- **F005 · Parsers and the stand-in:** per-harness parsers tested on recorded transcripts; the model stand-in
  (FR-44 to FR-47).
- **F006 · Catalog:** goals as live prompts; one task added (FR-38, FR-39).
- **F007 · Report:** per harness, three arms, two verdicts per task, adoption and category tables, a `stopped`
  section, spend only in the appendix (FR-36, FR-42, FR-49).

## Data model and contract changes

- **D001 · Trace schema 2** (`contracts/trace-schema.md`): `identity.arm`, `identity.timelike_tools`,
  `identity.harness_reported_version`, `identity.models_answered`, `identity.output_streams`; per call `category`,
  `timelike_tools` and `through_timelike`; totals by category and adoption counts, both derived; `ending.cause`; a
  top-level `spend`. Not backward compatible: the schema-2 reader refuses schema 1 and says so.
- **A001 · `timelike-bench` CLI** (`contracts/bench-cli.md`): `--harness`, `--arm`, `--dry-run`, `--standin`,
  `--turn-cap`, `--spend-cap`, `categories [--probe]`. `run` with no `--harness` is the fake agent, as before.

## Backward compatibility

Fake-agent CI keeps its key-free path, with three arms instead of two. Schema-1 traces are re-reported by slice 0's
revision only. No other feature is touched.

## Tech stack compliance

Python stdlib only for the bench (H5). The harnesses are third-party binaries, pinned by version and npm integrity,
never installed into either image under test. No new library.
