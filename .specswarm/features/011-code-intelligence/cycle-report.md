# Cycle report — 011 code intelligence (prompt 10)

> Append-only. One `## Cycle N — <send>` section per send built to acceptance; later verification goes in
> `### … addendum` sections. The mentor reads this file and never writes into it.

## Cycle 1 — bridge/sends/10-rev1-20261004-183704.md

**Written:** 2026-10-06. **Dispatch mode**, batch `20261004-183704`, prompt 7 of 8. **specswarm
4.0.1-botbaubble.2.35.0** (`4ff8dcb`), the version this session loaded: the expanded commands named that
cache path (lore Q002). The path is the one the send names, so there is no second report. Built under
discovery revision 13's rulings (code-track § Resume after pause-06); nothing here mutates. Group B copies
the send's `discovery_revision: 12`.

**Sequence:**
1. `git checkout -b 011-code-intelligence 010-services-interactive` (at `39b4224`).
2. `/specswarm:specify "10 code intelligence" --from-send bridge/sends/10-rev1-20261004-183704.md --dispatch`
   (`aaa9a42`).
3. `/specswarm:plan` (`67a52a8`).
4. `/specswarm:tasks` (`5978dd9`).
5. `/specswarm:implement --dispatch`:
   - T003 `0b192eb`, T004 `d1c494a`;
   - the deviations T001's tests found, fixed (`fbf6d71`);
   - T001 `c84356a`, T002 `c9bbe52`, T005 `341369f`, T006 `5bd3c08`.

Each command was invoked; blocks run from the installed file. Not `/specswarm:build`.
**Pushed nothing; merged nothing.**

**specify's allocation:**
- `FEATURE_DIR` = `.specswarm/features/011-code-intelligence`;
- D84 held;
- PARENT_ROUTE `default` (`master`).

**The `$ARGUMENTS` expansion:** the argument string was
`"10 code intelligence" --from-send bridge/sends/10-rev1-20261004-183704.md --dispatch`. The quotes went
into double quotes, and the stray quotes were in the description, not a path. Run from the installed file,
it parsed correctly.

**Status in one line:**
- `symbols outline | def | callers | dependents` work on an index in the session scratch, refreshed file
  by file on every call.
- Python is exact; JS/TS, Go, Rust and shell are text-based, and say so.
- A warm `def` on 1,000 files takes about 0.3 s on the host.
- **Nothing has run in the image.**

### Group A — cited from `.implement-complete`

The marker is `.specswarm/features/011-code-intelligence/.implement-complete`, written at the end of this run,
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
| source_send | bridge/sends/10-rev1-20261004-183704.md |
| source_prompt | plan/.discover/prompts/10-code-intelligence.md |
| prompt_revision | 1 |
| discovery_revision | 12 |
| slice | 1 |

The spec's frontmatter carries the same five values, with `audited_against: [1]`.

### Group C — written by the code instance

**delegations:** `[]`. Two general-purpose subagents wrote the tests (T001 units, T002 e2e) from the
contract. They are subagents, not delegations.

**criteria_reestablished**

Nothing has run in the image. Each citation matches exactly one line of the send (`grep -cF` = 1 for all
six).

- `10 · "lists exactly its 14 classes and functions with line ranges and no function bodies _(traces to: P1)_"`
  — **unconfirmed**. Docker lane pending; `tests/e2e/symbols-outline-fixture-14-definitions-line-ranges-no-bodies.bats`,
  4 cells.
- `10 · "answers in under 2 seconds warm on a 1,000-file repository _(traces to: P1)_"` —
  **unconfirmed**. Docker lane pending; `tests/e2e/symbols-def-file-and-line-first-exit-3-not-found-under-2s-warm.bats`,
  8 cells, with the bound timed inside the container.
- `10 · "grouped by enclosing function, with a header stating it is text-based _(traces to: P3)_"` —
  **unconfirmed**. Docker lane pending; `tests/e2e/symbols-callers-3-call-sites-grouped-text-based-header.bats`,
  4 cells.
- `10 · "returns the files that import it, ranked _(traces to: P1)_"` — **unconfirmed**. Docker lane
  pending; `tests/e2e/symbols-dependents-of-changed-file-ranked.bats`, 4 cells.
- `10 · "reports the cache as stale, rebuilds it, and answers from the new content _(traces to: P1)_"` —
  **unconfirmed**. Docker lane pending; `tests/e2e/symbols-stale-cache-rebuilt-answers-from-new-content.bats`,
  4 cells.
- `10 · "receives ranked locations with signatures _(traces to: D19)_"` — **unconfirmed**. Manual (D19),
  after the lane.

On the host stand-in, 26 of 28 cells passed. The two that fail are the `type -a` cells, which only the image
can pass. On the stand-in, a warm `def` over 1,000 files took 168–175 ms. That is evidence for the files'
logic, and changes no mode above.

**reconcile_mode:** `full`. A new spec, from prompt revision 1 in whole, with `audited_against` seeded
`[1]`. Slice 2's repository orientation is out of scope.

**not_verified**
- **Everything in the image:**
  - the 28 e2e cells;
  - the 2 s bound on the image's Python 3.14;
  - conformance over the image's tools (the probe is `outline /opt/timelike/bin/symbols`);
  - the announcement's line for `symbols`.
- **Exit 1 (index unreadable) and exit 124 (walk limit)** end to end. A unit covers the walk limit in
  process.
- **Text-based precision on real JS/TS, Go and Rust projects:** the patterns are tested on small
  fixtures.
- **D19.**

**changed_other_features**
- **None in code.** `search`'s walk and ignore rules are **loaded** from `tools/bin/search` (006), as
  `view` loads them, so `search`'s internal `walk` is now an interface `symbols` depends on.
- **`FOR-MENTOR.md` Item 20:** the index lives in the session scratch until 07 slice 1's state root exists.
  This is the send's seam 1, raised and not a pause.
- **`Makefile`**, **`pyproject.toml`**, **`README.md`** (a symbols section).
- **The announcement (007):** lists `symbols` automatically.

**process_failures_recorded**
1. **Three tool deviations shipped in T003 and were caught by the delegate's tests** before T001's commit:
   - notes after the cache clause;
   - a Python shebang not recognised, so the manifest's probe would have failed conformance in the image;
   - Go import matching inverted.

   They were fixed in `fbf6d71`, recorded in decisions.md.
2. **The contract's example signature** (`bool = False`) disagreed with what `ast.unparse` prints
   (`bool=False`). The e2e delegate found it; the contract, spec and data model were aligned.
3. **The traced unit run had one failure outside this feature:** `test_adele_cli.py` conform under tracing
   missed its 5 s probe limit. It passes untraced 3 of 3, and `adele` is untouched. Recorded, not hidden.

**retired_prompts_seen:** none.

**For 11 (the send's seam 3):** the dependents lookup 12 builds on is 011 at the commit of this report and
its marker, recorded in the batch's final report.

### Implement step 10 — quality validation (specswarm 2.35.0), as the library reported it

The output is byte-identical to 008 § Cycle 1's (`diff` of the two runs: no difference): every component
excluded, `Quality Score: unknown — no component could be measured, so there is no score to compare`, and
`block_merge_on_failure=false`.

The gate is **UNKNOWN**. It warns and does not halt; dispatch never asks; nothing was filled in by hand. The
project's figures are beside it in `.specswarm/metrics.json` → `011.project_measurements_not_scored`.

**Host lane** (advisory; scratch venv, Python 3.12.3):
- **Units:** 1567 passed (make test-host). This feature adds 55 in `test_symbols.py`.
- **Coverage:** Python **95%**; `symbols` 94% from its tests.
- **Lint:** ruff, mypy strict (25 files), shellcheck (the Makefile's 68 files): clean.
- **`make test-host`:** passed.
- **Timings:**
  - `symbols --help` p95 83 ms, after deferring `ast` (87 ms before);
  - the probe (`outline` of a 900-line file) p95 130 ms;
  - `def` on 1,000 files: 1.9 s cold, about 0.27 s warm.

**Implement step 9b: decision log** (installed `scope-tally` and `decision-tally`, after T006):

```
scope: planned=7 recorded=6 unplanned=0 unrecorded=1 in=6 out=0 none=0 unknown=0 flagged=6 flagged_out=0 other=0 other_out=0
decisions: sections=6 flagged_sections=6 non_flagged_sections=0 sections_without_absent=0 flagged=14 assumed=4 deferred=0 absent=6 inherited=6 low_confidence=0 flagged_low_confidence=0
```

- `unrecorded=1` is T007, this report. The marker's tallies are taken after it.
- There is no low-confidence entry, and no pause.
