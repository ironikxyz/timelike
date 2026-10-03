# Quality Analysis Report — 2026-09-29, specswarm 4.0.1-botbaubble.2.18.0 (verification run)

**Overall Quality: unknown** — no module could be scored (8 unscored).

Run on `master` at `37db570`, after the plugin update, as a verification of 2.18.0.

## What 2.18.0 decided, and why it is right for this project

- `lib/language-detector.sh` reports **Python** (unit test: pytest; framework: none).
- Every check in sections 2–6 is a JavaScript/TypeScript grep: `*.tsx`, React patterns, `*.test.ts`,
  `app/routes/`. On this project those checks can match nothing.
- So `component-applicability` marks tests, docs, architecture, security, lazy loading and images as
  `unavailable` ("there is no Python detector"), and bundle size as `unavailable` (the monitor is not
  in this install). No component is scored, so the score is `unknown`: not 0, and not 100.
- No `tsconfig.json`, so LSP analysis does not apply.

| Module | Score |
|---|---|
| tools/agentio, tools/bin, scan, image, scripts | unknown |
| bench/benchlib, bench/bin, bench images + run.sh | unknown |

## Correction to earlier scores

**The earlier scores were judgments, not measurements.** Both earlier scores were computed with 2.15.0
logic:
- 001's 89% (`001-agent-shell-baseline/quality-report.json`)
- 002's 90% (`002-speedup-bench/quality-report.json`,
  `.specswarm/quality-analysis-20260929-092346.md`)

Their component values were **filled in by this instance's judgment**. For example, "the module has
pytest units, so 25/25", or "43 of 75 public items documented, so 10/15". They were not produced by the
rubric's checks, which cannot run on Python. `lib/quality-scale.sh` did the arithmetic, but the inputs
were substitutes. 2.18.0 names exactly that defect ("a null result from a grep that could never match
read as clean").

Both scores were informational (`enforce_gates: false`, `min_quality_score: 0`), so neither decided a
merge. The merge bar is quality-standards § Quality Gates, which rests on the project's own lanes:
- 002: Docker lane 176/176 e2e, unit 593, scan PASS on three images, coverage 97%, SC-3 observed
- 001: its Docker lane, scan and coverage as recorded in its cycle report

Those stand.

## Consequences to watch (not acted on here)

1. **`/specswarm:ship` under 2.18.0** will read `overall_state: unknown`. With `enforce_gates: false` it
   warns and does not block (its three-state gate).
2. **`/specswarm:implement` step 10i** halts on an unknown score when `block_merge_on_failure: true`
   (reboot.md). Check quality-standards before the next implement.
3. The project's real quality evidence remains its own lanes: `make test`, `make test-host` with
   coverage by language, and `make scan`. That is what plan's ruling
   (`../bridge/feedback/01-20260928-130206-quality-score.md`) already made the merge bar.

## Findings the rubric cannot see (carried from the 002 ship, not re-scored)

- Driver hardening: `--cap-drop ALL` and `no-new-privileges` (the mentor's note).
- Docstrings: `benchlib` 32 public items and `timelike-bench` 6 undocumented; `timelike-conform` (the 001
  leftover).
- `scripts/demo.sh` has no automated test (the operator watches it).

**`quality-report.json` not written.** This run is on `master`, with no feature context. `§9` would
write `${FEATURE_DIR}/quality-report.json` with `FEATURE_DIR` unset, and overwriting a shipped feature's
report with a re-run was not wanted.
