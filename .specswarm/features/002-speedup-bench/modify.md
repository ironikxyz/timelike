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
