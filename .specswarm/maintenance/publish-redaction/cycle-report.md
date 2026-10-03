# Cycle report — maintenance: publish redaction

> Append-only. One section per cycle, headed by the send it built. A maintenance send has no prompt and
> no feature directory (`/specswarm:specify` is not run), so this report lives under
> `.specswarm/maintenance/publish-redaction/`. The send's own report is `FOR-MENTOR.md` Item 15.

## Cycle 1 — bridge/sends/maint-publish-redaction-20261002-183624.md

**Written:** 2026-10-02. Built by hand on `maint/publish-redaction`, branched from `master` at `3c10d11`.
No specswarm command was run. **Not merged:** the mentor's lane and sign-off are next.

**Commits:**
- `8f2d72d`: the redaction, 10 tracked files
- `26dc987`: the check (`scan/denylist.py`, wired into `make scan`) and its tests
- this commit: `FOR-MENTOR.md` Item 15 and this report

### Group A — cited from `.implement-complete`

Group A: not applicable — no marker on this path

### Group B — copied from the send

| Field | Value |
|---|---|
| source_send | bridge/sends/maint-publish-redaction-20261002-183624.md |
| source_prompt | none (maintenance; the source is the operator's decision, `bridge/state.json` `carry_forward.publish-cutover`) |
| prompt_revision | none |
| discovery_revision | 10 |
| slice | none |

### Group C — written by the code instance

**delegations:** `[]`.

**criteria_reestablished.** The send has no criterion lines. Its requirements, with their modes:
- *Replace, string for string* — **executed** (`git grep -E -i` per id over the tree at `8f2d72d`:
  0 for every id; the "before" counts at `3c10d11` equal the send's table). The word-level diff
  changes only matched strings and adds one note line per file.
- *Scan baselines keep their ids, packages, review dates and `review_by`* — **executed** (field by
  field, before and after, in the edit script). The baselined counts and `make scan` passing on all
  four images are **unconfirmed** until the mentor's lane.
- *A check that keeps the tree clean, by id and file:line, unknown without a list, never PASS on a list
  it did not read* — **executed** on the host: the real list against `3c10d11` and against HEAD; a
  scratch clone with seven generated plants through `scan.sh`'s own section (seven FAIL lines, exit 1);
  41 units; `scan.sh` end to end through its unit fake. Its run under real Docker in `make scan` is
  **unconfirmed** until the mentor's lane.
- *Show it failing, without committing a matching string* — **executed**: every plant is built at run
  time, from the real list or from synthetic entries, and no tracked file holds a pattern or a match
  (the check passes its own HEAD, 245 files).
- *Step 3, read-only* — **executed** for history (counts in Item 15); for the built images,
  **unconfirmed**: read from the source only, with a read-only command for the lane in Item 15.

**reconcile_mode:** `full`: every tracked file was searched for every entry, not just the files the
mentor counted.

**not_verified**
- nothing ran in Docker: the deny-list step inside `make scan`, its read-only mount, the agent image's
  GNU grep, and the baselines' unchanged counts;
- the built images' labels, history and filesystem (Item 15 has the command);
- the check on a host whose `grep` is not GNU grep: an entry it rejects is an error there, never a pass.

**changed_other_features**
- **records of 001, 002, 003 and 004**: the matched strings in their cycle reports only, and 001-era
  `.specswarm/quality-analysis-20260930-052430.md`;
- **the scan gate shared by every feature**: a new step in `scan/scan.sh`, a new `scan/denylist.py`, the
  three baselines' attribution and one note, and `tests/unit/test_scan_report.py`'s docker fake (it
  learns `-i`, and its fixture tree is a real git repository);
- `pyproject.toml`: mypy also checks `scan/denylist.py`.

**Host lane:** 817 passed (untraced). Coverage, from the traced run before the last fixture fix:
`scan/denylist.py` 95%, scan overall 99%, all 97%. ruff, ruff format, mypy (17 files) and shellcheck
are clean.

**process_failures_recorded**
1. The check's first run errored on every tree: my `_grep` put `-e PATTERN` after `--`, so grep read
   the pattern as a file name. It reported **error**, not pass, which is the design working, and was
   fixed before commit.
2. The plant generator wrapped plants in other text, so anchored entries could not match. The self-test
   now writes the plant as its own line.
3. With no list, the check returned before reading stdin, so `git archive` died of SIGPIPE under
   `pipefail` (exit 141). Found by dry-running `scan.sh`'s section through a shim, fixed by draining
   stdin on every path, and pinned by a test.
4. A `git stash` round-trip during testing left a stash entry. I confirmed it was identical to the
   working tree and dropped it.
5. Correction to 004's ship section (append-only there): *"8 beside 8 unscored"* was 003's 2.22.0
   ship, not 001's cycle 6, which was already `0/8` (the mentor's discharge note, 18:10:53Z).

**retired_prompts_seen:** none.

### What the mentor needs to do next

1. `make test` and `make scan` on this branch's HEAD. Expect the scan's new line
   `publish deny-list [tracked tree]: PASS — 7 entries, …`, the baselined counts unchanged, and
   `scan/out/denylist.json` with every count at 0.
2. Optionally, the read-only image check in Item 15.
3. Sign-off. I then merge `--no-ff` by hand.

### Cycle 1 lane addendum — the mentor's lane on `f73ac79` (2026-10-02T20:03:52Z)

**Written:** 2026-10-03, after the sign-off. Sources: the mentor's `lane` and `sign-off` entries in
`../bridge/history.md` (20:03:52Z), and this checkout's `tests/out/summary.json` (`git_sha`
`f73ac794f55f…`, every step `pass`) and `scan/out/denylist.json` (state `pass`, 246 files, every id 0).
Cycle 1 above is not edited.

- **make test: passed.** e2e 239/239; Python units 816 passed and 1 skipped; Go units pass.
- **make scan, first run:** PASS on all four images with unchanged baselined counts (agent 80, vanilla
  79, bench-driver 51, Adele none). The deny-list step reported **`unknown — no deny-list available`**,
  because the lane mounted only `code/`. That is the specified behaviour: there was no list, so nothing
  was checked and nothing was claimed. The mentor then mounted `bridge/` read-only at its host path.
- **make scan, re-run:** PASS on all four images, and **the deny-list step PASS: 7 entries, 246 tracked
  files, P1–P7 all 0/0.** The mentor's own count over `git ls-tree` at `f73ac79` also gives 0.
- **Image check** (Item 15's read-only command, run by the mentor on the host, by id): agent, adele,
  adele-standin, vanilla, bench-driver and test-runner are all 0 for P1–P7, in metadata, history and the
  exported filesystem. The mentor also ran positive controls, to show the matcher can find hits: one
  file of its own matched P6, and a temporary copy of a host note matched P1–P5 (it was deleted
  afterwards). P7 has no positive control outside the check's own per-entry self-test.

**Modes, updated from Cycle 1:**
- the baselines' unchanged counts, and `make scan` passing on all four images — **executed** (the lane);
- the check under real Docker in `make scan` — **executed** (the re-run), and its no-list behaviour was
  **executed** too, unplanned, in the first run;
- step 3's built images — **executed** (the mentor's image check).

**Merge:** by hand, `--no-ff`, into `master`. The commits after `f73ac79` are bookkeeping only: this
addendum and `FOR-MENTOR.md` Item 15's closure.
