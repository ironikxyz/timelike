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

### Addendum 1 — rebased after lane batch-b's fix on 009 (2026-10-07T00:08:24Z, read from the clock)

- **Why:** the cascade ordered by `bridge/feedback/batch-20261006-234535-lane-b-three-failures.md`. The fix
  for lane batch-b's SC-6 default-session cells (`../bridge/history.md` 2026-10-06T20:03:07Z) went on
  `009-session-journal` (`2e3f483`). 010 was rebased onto it and gained its Addendum 1 (`dbe1959`), and this
  branch was rebased onto that.
- **The rebase:** `git rebase --onto dbe1959 7c9a5bd 011-code-intelligence`. No conflicts. The same 14
  commits; the tree differs from the old tip `473be4a` by 009's fix and 010's addendum only. **Nothing of
  011 changed.**
- **New hashes:** the marker `6d523d4` is now **`14cd5a3`**; the code tip `473be4a` is now `5cce652`. The
  branch's tip is the commit that adds this addendum.
- **Not verified here:** 011's cells in the image. They passed in lane batch-b (symbols 28/28) and stay as
  recorded until the lane re-runs at the new tip.

### Addendum 2 — D19 observed by the operator (2026-10-08T05:37:19Z, read from the clock)

From the mentor's observation entry in `../bridge/history.md` (2026-10-07T23:48:48Z) and the transcript
it cites, `bridge/.d19-demo-20261007T233617Z.txt` (bridge `5ab9058`), which this instance read.

- `10 · "receives ranked locations with signatures _(traces to: D19)_"` — **observed by the operator**,
  by interview with the mentor instance on `symbols`'s real output. The image was the one lane batch-d
  passed (revision `244c4a8`, `sha256:d0dd2058…`), run as a throwaway with `--cap-drop ALL`,
  `no-new-privileges` and `--init`. Each agent command was its own `docker exec … bash -lc`, as user
  `agent`, in a git repository holding a copy of the stdlib email package as `mailparse/` (29 files).
  - **`symbols def --text get_content`:** `2 definitions, exact (python)`. Best first came
    `mailparse/contentmanager.py:17` `ContentManager.get_content` with `def get_content(self, msg, *args,
    **kw)`, then `mailparse/message.py:1137` `MIMEPart.get_content` with its signature.
  - **`symbols callers --text get_content`:** 1 call site, in `MIMEPart.get_content`
    (`mailparse/message.py:1140`), under the header `text-based: name matches followed by "(", not
    resolved calls`.
  - **A missing name:** `symbols def get_contents_v2` gave not found, exit 3, `do instead: search -w
    get_contents_v2`. The JSON form is shown too.
  - **The mentor's independent grep** over the same files agrees: two definitions (`message.py:1137`,
    `contentmanager.py:17`) and one call site (`message.py:1140`).
  - **Interview:** all four answers matched the transcript. The operator accepts D19 as observed.
  - The criterion still resolves to exactly one line of the send (`grep -cF` = 1).
- **Where this record lives:** on `012-verify-changed`, the stack's tip, as with the D12, D14 and D4 addenda
  (`d932c1c`, `631a29e`, `eafd930`), so that `244c4a8..` stays records only and lane batch-d's evidence holds.
  The mentor's instruction allowed this placement provided it is stated (a branch per addendum was its
  first option). A revert of 012 by branch topology would carry this addendum with it.
