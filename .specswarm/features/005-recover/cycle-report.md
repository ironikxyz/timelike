# Cycle report — 005 recover (prompt 07)

> Append-only. One `## Cycle N — <send>` section per send built to acceptance; later verification goes in
> `### … addendum` sections. The mentor reads this file and never writes into it.

## Cycle 1 — bridge/sends/07-rev1-20261003-013915.md

**Written:** 2026-10-03. Not in dispatch mode. Built with `/specswarm:specify --from-send`, then
`/specswarm:plan`, `/specswarm:tasks` and `/specswarm:implement`, on `005-recover` from `master` at
`9522f55` (the public lineage), under **specswarm 4.0.1-botbaubble.2.27.0**: the version this session
loaded, which the expanded commands name (lore Q002; the session was reloaded with `/reload-plugins`
after Cycle 7 of 001). **Pushed nothing; not merged:** the Docker lane has not run, and the merge waits
for the mentor's sign-off (CLAUDE.md rule 5).

**Status in one line:** two new commands, `snapshot` (take, list) and `undo` (dry run, confirmation
envelope, verified restore with a safety snapshot). The units, conform and the host lane pass. Nothing
has run in the image yet.

### Group A — cited from `.implement-complete`

Group A: not applicable — no marker on this path

### Group B — copied from the send

| Field | Value |
|---|---|
| source_send | bridge/sends/07-rev1-20261003-013915.md |
| source_prompt | plan/.discover/prompts/07-recover.md |
| prompt_revision | 1 |
| discovery_revision | 10 |
| slice | 0 |

### Group C — written by the code instance

**delegations:** four general-purpose or Explore subagents, each with its own files and the brief "do not
commit; do not touch `../bridge`, `../plan`, `.specswarm/` or `tools/`; report decisions as INHERITED /
ASSUMED / FLAGGED / ABSENT".
1. **Explore (read-only): agentio's conventions.** The `Tool` fields, how `--dry-run`/`--yes` are wired,
   `confirm_required`, `Cut`, events, conform's probes, how a tool reaches `PATH`. Its key facts were
   re-read before use (R4, R5).
2. **Explore (read-only): the image, the git layer, the e2e harness, measured sizes** (R3, R6, R7, R9).
3. **The e2e fixture and five bats files (T001, T003–T007)**, written from the CLI contract before the
   tools existed. It was told the contract amendment mid-task. Two test bugs were found by the T013 host
   stand-in and fixed in review (T004, T006); one test was strengthened for the amended default.
4. **The units (T008)**, written from the contract alone: 70 of 71 passed against the tools on first run.
   The one failure was the tool's wording against the contract, and the tool was changed. One unit was
   added in review.

**criteria_reestablished**

Nothing has run in the image (no Docker here, R10), so every automated criterion is `unconfirmed` until
the Docker lane. The host lane and the host stand-in below are advisory.

- `07 · "of the workspace and prints its identifier, file count and size"` — **unconfirmed** (Docker lane
  pending; `tests/e2e/snapshot-records-tracked-untracked-and-ignored-files.bats`)
- `07 · "removes files created after it, and a dry run lists exactly those changes first"` —
  **unconfirmed** (Docker lane pending;
  `tests/e2e/restore-returns-captured-content-and-removes-files-created-after.bats`)
- `07 · "are unchanged by taking or restoring a snapshot"` — **unconfirmed** (Docker lane pending;
  `tests/e2e/version-control-history-index-and-stash-unchanged-by-snapshot-and-restore.bats`)
- `07 · "is refused or partial, and the verdict names what was excluded and why"` — **unconfirmed**
  (Docker lane pending; `tests/e2e/snapshot-over-the-size-cap-is-partial-and-names-what-was-excluded.bats`)
- `07 · "restores it with one undo command _(traces to: D7)_"` — **unconfirmed**. Manual (D7): the mentor
  interviews the operator on the real exchange after the Docker lane.

Each citation matches exactly one line of the send (`grep -cF` = 1 for all five). The D7 citation
includes its trace marker, because the bare sentence is also on the send's line 39.

**reconcile_mode:** `full`. This is a new spec generated from prompt revision 1 in whole, and
`audited_against` is seeded `[1]`. The slice 1 and 2 criteria are out of scope, and are neither
built nor claimed.

**The seams the send named, as built** (spec § Decisions; FOR-MENTOR Item 17, open, not blocking):
1. **Rule 9 and "one undo command" (D-1):** the envelope reading. `undo` alone exits 4; `undo --yes` is the one
   command.
2. **The workspace (D-2):** the nearest ancestor holding `.git`, else the current directory, found
   without running git. `/`, the home directory and their ancestors are refused with
   `do instead: change into the project directory …`.
3. **"Excluded" (D-3):** the per-file limit, the size cap's largest-first cut, non-regular and unreadable
   files. No built-in cache list. Ignored files are captured.
4. **The git-state boundary (D-4):** every `.git` is out of scope at any depth. The write and remove
   helpers refuse it themselves, and every parent is checked with `lstat`, so a planted symlink is replaced,
   never written through (unit and host-checked).
5. **The store (D-5):** a stdlib content-addressed copy store, not git. This **departs from
   `tech-stack.md`'s note** for three stated reasons (modes, nested repositories, the dispatcher). Raised
   in Item 17.

**Decided in implement, recorded as amendments** (both FLAGGED in `decisions.md`, T009 and T012):
- **Outcomes are verdicts.** A refusal, "no snapshot" and a failed verification are results on stdout
  (header, verdict, `do instead:`, exit 1 or 3), not stderr errors. `timelike-conform` forced it: its
  probes run in conform's own directory, which in the image is the home directory, and C3/C4 need a
  header. `adele status` is the precedent.
- **`undo`'s default skips safety snapshots** (spec FR-14 amended). Otherwise a second `undo --yes` would
  undo the first, and `undo` would not be idempotent (rule 7).
- **The entry-cap verdict names the cap, not a count** (FR-7 and SC-4 amended): the walk stops at the cap.

**not_verified**
- **Everything in the image:**
  - the five e2e files (44 cells);
  - conform over every tool on `PATH` (the count test includes the two new tools);
  - `type -a` for both names;
  - Python 3.14.7 (the host is 3.12.3);
  - the real `/etc/gitconfig` and the hook dispatcher next to a repository being snapshotted.
- **The host stand-in (T013) is not image evidence.** A scratchpad `docker` stand-in ran each bats file's
  commands here, with the test's variables, a stand-in home and the two tools on `PATH`, under bats-core
  1.14.0:
  - 40 of 44 ok; the 4 not-ok are the `type -a` cells, which pin `/opt/timelike/bin`;
  - `COLUMNS=1000` was set because the host's scratchpad home path is long enough to cut the remedy line
    at 200 columns. The image's `/home/agent` is not.
- **Filesystem behaviour on the container's overlay layer** (rename over a symlink, `O_NOFOLLOW`, modes).
  Measured on the host's ext4 only.
- **Snapshot latency in the image** at the default caps. R1 measured it on the host only.
- **The verification-failure path** (`left N differences`) is reachable only by a fault: it is untested.
- **D7 (the demo)**: unconfirmed until the operator is interviewed.

**changed_other_features:** none in behaviour. Shared files gained entries for this feature only:
- `pyproject.toml`: ruff and mypy lists;
- `Makefile`: `SHELLCHECK_FILES`;
- `README.md`: a new section.

`timelike` lists the two tools automatically.

**process_failures_recorded**
1. **My conform check first failed for my own install's reason.** The rewritten shebang kept `-I`, which
   ignores `PYTHONPATH`, so `undo` could not import agentio. Re-run the way `test_conform.install`
   does it (no `-I`). Not a tool defect.
2. **A version copied from memory.** T002's decision and the metrics entry first said mypy 2.3.1 (from
   `reboot.md`); this venv has 2.4.0. Corrected in place and noted in T015.
3. **A wrong exit code in my own step-10 script.** It echoed `run_coverage`'s exit after a pipeline and
   printed `rc 0`. Re-measured separately: `unknown`, rc 1. The recorded output below is marked
   corrected.
4. **Two contract gaps found during the build**, not in the plan: the conform probe location (outcomes)
   and idempotency (the default target). Both were amended in the contract and spec, and both delegates
   were told before they finished.
5. **Plugin observations, for the mentor to relay** (the first `specify` under 2.26.0+, as the send
   asked):
   - **D84 holds:** reusing branch `005-recover`, specify named the directory from the branch
     (`005-recover`), not from the description (`07-recover`), and said so on stdout.
   - **D81: no positional parameters remain in specify's blocks (checked: 0 `$1` outside comments).
     But a different workaround was needed:** the expansion pastes the arguments into double-quoted
     strings (`DESCRIPTION=""07 recover" --from-send …"`), so an argument holding a double quote
     breaks the shell. The blocks were run from the installed file with `ARGUMENTS` as a variable.
   - **D82 not exercised:** no task changed a dotfile. D75's bare-name match worked: T002's `Makefile`
     scored `SCOPE: in`.
   - **`lib/features-location.sh` wrote nothing to stderr** in specify, plan, tasks or implement.
   - **`lib/quality-gates.sh` is still absent** (2.27.0), as relayed after 001's Cycle 7.
   - **D85** (which unknown the gate names) is a ship result; ship has not run.

**retired_prompts_seen:** none.

### Implement step 10 — quality validation (specswarm 2.27.0), as the library reported it

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
- run_coverage pytest: unknown (rc 1)   [corrected: the first capture echoed the wrong $?; re-measured separately: out=unknown rc=1]
- step 10e: lib/quality-gates.sh is not installed under <plugin cache>/4.0.1-botbaubble.2.27.0; unavailable, recorded as unmeasured
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

The gate is **UNKNOWN**. With `block_merge_on_failure: false` and `min_quality_score: 0` it warns and
does not halt. No component was filled in by hand. The project's own host-lane figures are recorded
**beside** it in `.specswarm/metrics.json` → `005.project_measurements_not_scored`. The output is
verbatim except the plugin cache path (`<plugin cache>`) and the one corrected `run_coverage` line.

**Host lane** (advisory; scratch venv, Python 3.12.3):
- `make test-host`: **889 passed** (174 s); env layer 60/60; hook logic 29/29.
- This feature's units: 72 passed.
- Coverage of the two tools (line + branch, subprocesses included): `snapshot` 93%, `undo` 88% (20
  statements), together **93%**.
- ruff 0.16.7 clean (54 files formatted); mypy 2.4.0 strict: no issues in 19 files; shellcheck 0.11.0
  clean over `SHELLCHECK_FILES`, with the six new files added.
- The publish deny-list read `pass` with the list read before every commit (7 entries, P1–P7 0/0).

**Implement step 9b: decision log** (plugin `scope-tally` and `decision-tally` over 005's `tasks.md` and `decisions.md`, after T015):

```
scope: planned=15 recorded=14 unplanned=0 unrecorded=1 in=11 out=1 none=2 unknown=0 flagged=6 flagged_out=0 other=8 other_out=1
decisions: sections=14 flagged_sections=6 non_flagged_sections=8 sections_without_absent=0 flagged=9 assumed=18 deferred=0 absent=14 inherited=13 low_confidence=0 flagged_low_confidence=0
```

- `unrecorded=1` is T010: it is one file with T009, written as one, committed together, and recorded in
  T009's section.
- `out=1` is T015's `.specswarm/metrics.json`: implement step 10 writes it, and `tasks.md` does not name it
  (the same as 001's T078).
- 6 FLAGGED sections and 0 low-confidence entries, so this run gives the promotion bar nothing.

## Cycle 2 — bridge/sends/07-rev11-20261004-030207.md

**Written:** 2026-10-04. Not in dispatch mode. **specswarm 4.0.1-botbaubble.2.32.0** (`19829a6`), the
version this session loaded: the expanded commands name the cache path `…/4.0.1-botbaubble.2.32.0`
(lore Q002). The sequence was `/specswarm:constitution` (governance, on `master`), then
`/specswarm:modify 005 --from-send bridge/sends/07-rev11-20261004-030207.md` on `005-recover`, then the
plan, tasks and implement records for the cycle (Phase 6, T016–T019). The send's `005-recover` was kept;
`modify` did not ask for a new branch. **Nothing was pushed or merged.** The lane, the D7 interview and
the mentor's sign-off come first (CLAUDE.md rule 5).

This cycle's path is named here, as the send asks: `.specswarm/features/005-recover/cycle-report.md`.
CLAUDE.md names the same file, so there is no second report.

**Status in one line:** governance is audited to revision 11, and the CVE-2026-95619 baselines are on
`master` and merged in. Plan's four store conditions: two held as built, and two were built (the size cap
after dedup; "taken" only after a restorability check). Revision 11 is recorded in the spec, Item 17 is
closed, and the host lane passes. Nothing has run in the image yet.

### Group A — cited from `.implement-complete`

Group A: not applicable — no marker on this path

### Group B — copied from the send

| Field | Value |
|---|---|
| source_send | bridge/sends/07-rev11-20261004-030207.md |
| source_prompt | plan/.discover/prompts/07-recover.md |
| prompt_revision | 11 |
| discovery_revision | 11 |
| slice | 0 |

These are the send's own values. The spec's frontmatter keeps `prompt_revision: 1` and
`discovery_revision: 10`, the revisions its body was generated from. Only `audited_against` may move, and
it waits for the lane (*Provenance* below).

### Before the modify: on `master`, then merged into `005-recover`

**Governance audit, discovery revision 10 → 11** (`586e298`). Source: `../bridge/governance-context.md`
(`/mentor:regovern` 2026-10-04T00:24:17Z), § "What Changed In Those Revisions". This was three edits, as
the send said:

| File | How | Result |
|---|---|---|
| `constitution.md` | `/specswarm:constitution` (2.32.0) | **No change needed.** No article restates rule 10's state locations or the project cache; H2 points at the contract rather than restating its rules; P5 and T2 name no store technology. 1.4.2 stands. Sync Impact Report entry, `governance_audited_against` += 11 |
| `tech-stack.md` | by hand | **Amended.** The git line said "snapshots, shadow store outside the workspace". It now reads as the agent's own version control, "not the snapshot store (discovery revision 11)", and the stdlib content-addressed store is noted under Python. 1.3.0 → 1.3.1. `lib/tech-stack-parser.sh` reads the same 41 technologies before and after. Prose note, += 11 |
| `quality-standards.md` | by hand | **No change needed.** No gate restates rule 10; the *Snapshots (T2)* budget and the *Snapshot restore round-trip (P5)* gate name no store technology. Prose note, += 11 |

All three now read `governance_audited_against: [2, 3, 4, 5, 6, 7, 8, 9, 10, 11]`.

**CVE-2026-95619 baselines** (`f33c806`; send `bridge/sends/maint-baseline-cve-2026-95619-20261004-024309.md`).
In each image, three entries were added (`gcc-14-base`, `libgcc-s1`, `libstdc++6`; High; origin `base
layer`). They were taken from that image's own `baseline.proposed.json` of the 2026-10-04 lane and placed
after CVE-2026-102010's:

| Baseline | Entries | Review note |
|---|---|---|
| `scan/baseline/timelike-agent.json` | 80 → 83 | one, attributed to `ironik.xyz` |
| `scan/baseline/timelike-vanilla.json` | 79 → 82 | one, attributed to `ironik.xyz` |
| `scan/baseline/timelike-bench-driver.json` | 51 → 54 | one, attributed to `ironik.xyz` |

Nothing else changed in the baselines: `review_by` stays 2026-12-27, and so do `reviewed` and the
origins. As an advisory check only, `scan/evaluate.py report` was re-run on the host over copies of that
lane's own scan output with these baselines: **PASS** for agent, vanilla and bench-driver (83, 82 and 54
baselined). The scan units passed (112). The deny-list read `pass` with the list read.

**Merge:** `master` → `005-recover` at `fc5b97d`, with no conflict.

### Provenance (modify Step 2 and Step 9)

The installed `provenance-inputs` and `provenance-row` blocks gave **row 7**: the same prompt, `N 11`,
`prompt_revision 1`, `audited_against [1]`. `modify` took the feature number from the standalone `005`
argument. The branch is not `modify/NNN`, so without the argument it would have asked on stdin, as the
send said.

The classification compares the prompt copy in `bridge/sends/07-rev1-20261003-013915.md` with this send's.
Only additions differ: the revision note, one constraint and two *(slice 1)* criteria. **Nothing was
removed or reworded**, so removals are visible and none occurred. Revisions 2–10 did not change prompt 07.
**Not superseded.** The constraint's slice-0 part ("outside the workspace") holds as built; the two
criteria are carried, not built (spec § Revision 11).

**`audited_against` is not appended yet**: `audit-log.md` has one `none (deferred)` row. This cycle
changed `tools/bin/snapshot`, which slice 0's criteria rest on, so the expected **`full`** append of
2–11 waits for the mentor's Docker lane on this cycle's commit, as in 001 cycles 5 and 6. A `### Cycle 2
addendum` will record it.

### Plan's four conditions on the store (resolution Q1), checked against `005-recover` at `f83e984`

| # | Condition | As built at `f83e984` | Now | Evidence (test or code line → result) |
|---|---|---|---|---|
| 1 | Blobs deduplicated by content across snapshots | **Met.** `Store.put` stores by sha256 and drops the copy when the object exists (`tools/bin/snapshot:389`) | unchanged | `test_content_is_stored_by_hash_outside_the_workspace` (two snapshots: one object on disk) → pass. New, measured on disk: `test_a_repeated_snapshot_of_an_unchanged_workspace_adds_no_stored_bytes`: the second snapshot adds **0** bytes to `objects/` and reports `stored_bytes 0`; a 123-byte change adds exactly 123 → pass |
| 2 | Symlinks stored as links, never followed out of the workspace | **Met.** The walk records `os.readlink` (`:276`), never descends a link, and restore writes `os.symlink` (`:835`) | unchanged | `test_take_records_tracked_untracked_ignored_files_links_and_dirs_with_modes`: `src-link` recorded as `("link", "src")` with no `src-link/app.py`, `dangling`, and `outside-link` with nothing from outside captured → pass. `test_yes_restores_every_kind_byte_identical_and_names_the_safety_snapshot` restores links byte-identical → pass |
| 3 | The size cap counts stored bytes after dedup | **Not met.** The cap was compared with the sum of every candidate's plain size, so content already stored or repeated counted again | **Built (T016).** `_fit_size_cap` (`:558`, called at `:498`): content already stored costs nothing (`:580`), repeated content counts once, the largest new content is left out first, files sharing content are left out together; the raise line names the new content | `test_the_size_cap_counts_bytes_already_stored_as_nothing` (1900 bytes of files, 300 new, cap 500 → complete, `stored_bytes 300`); `test_the_size_cap_counts_content_repeated_within_a_snapshot_once` (750 bytes, 450 distinct, cap 450 → complete; 450 on disk); `test_over_the_cap_files_sharing_content_are_left_out_together_largest_first`; the changed `test_per_file_limit_and_size_cap_exclude_largest_first_with_reasons` (a second snapshot adds only a.bin); SC-4's e2e raise value 300000 → all pass. **What a capped snapshot left out** is still named per file with its reason (FR-6) |
| 4 | "Taken" only after checking that the snapshot is restorable | **Not met.** "Taken" followed the record write | **Built (T016).** `Store.verify` (`:409`, called at `:545`) is **a hash check**: the record is read back and compared, every entry path is checked as one a restore may write, and every object it names must be a regular file of the recorded size whose sha256 is its name. On failure no record stays (the id stays used), the damaged object is removed so the next snapshot stores it again, and the verdict is `snapshot <id> not taken: …` (exit 1). The same check guards `undo --yes`'s safety snapshot: if it fails, nothing is applied | `test_taken_follows_a_check_that_every_stored_object_reads_back_by_its_hash` (a damaged object planted where `put` trusts it → not taken, not listed, object removed; the next snapshot is id 3 and stores the content again) → pass. `test_a_safety_snapshot_that_fails_verification_stops_the_restore_before_any_change` (the workspace tree is identical after the refused undo) → pass |

**The cost of condition 4, measured on the host (advisory):** a 53 MB, 391-file workspace, page cache
warm, three runs each of first and repeat snapshot. At `f83e984`: 364–407 ms. Now: 554–594 ms. That is
about +180 ms, one re-read of the snapshot's distinct content. Under the size cap, the plain sizes decide
first, so nothing is hashed twice unless the cap is in play.

**Contract changes (declared, in `contracts/recover-cli.md`, `data-model.md`, spec FR-6, FR-9, FR-23,
README):** the verdict lines are byte-identical. JSON `data` gains `stored_bytes` and `verified`. There
are two new outcomes (exit 1): `snapshot <id> not taken: it could not be verified restorable: <what>`,
and `restore of snapshot <id> not started: …`. The record gains `stored_bytes` and `size_cap_needed`, and
`v` stays 1.

### Group C — written by the code instance

**delegations:** `[]`. Every task was done by this instance; no subagent was used.

**criteria_reestablished**

Nothing has run in the image this cycle (no Docker here, R10). Cycle 2 changed the code under SC-1, SC-2
and SC-4, so the image results from Cycle 1's lane at `f83e984` no longer cover this tree. Every automated
criterion is `unconfirmed` until the mentor's lane on this cycle's commit.

- `07 · "of the workspace and prints its identifier, file count and size"` — **unconfirmed** (Docker lane
  pending; `tests/e2e/snapshot-records-tracked-untracked-and-ignored-files.bats`; the verdict format is
  unchanged)
- `07 · "removes files created after it, and a dry run lists exactly those changes first"` —
  **unconfirmed** (Docker lane pending;
  `tests/e2e/restore-returns-captured-content-and-removes-files-created-after.bats`)
- `07 · "are unchanged by taking or restoring a snapshot"` — **unconfirmed** (Docker lane pending;
  `tests/e2e/version-control-history-index-and-stash-unchanged-by-snapshot-and-restore.bats`)
- `07 · "is refused or partial, and the verdict names what was excluded and why"` — **unconfirmed**
  (Docker lane pending; `tests/e2e/snapshot-over-the-size-cap-is-partial-and-names-what-was-excluded.bats`,
  whose second-run raise value changed to 300000)
- `07 · "restores it with one undo command _(traces to: D7)_"` — **unconfirmed**. Manual (D7): the mentor
  interviews the operator on the real exchange after the Docker lane.

Each citation matches exactly one line of this send (`grep -cF` = 1 for all five). The two revision-11
criteria are *(slice 1)* and are neither built nor cited.

**reconcile_mode:** `full` is expected (2–11: removals visible, none occurred, revisions 2–10 did not
touch the prompt, and the slice-1 criteria are outside a slice-0 spec). **It is not applied yet.** It is
deferred to the lane, recorded as `none (deferred)` in `audit-log.md`. If the mentor reads the two
slice-1 criteria as unaddressed criteria of this spec, the mode is `scoped` (11 alone) or `none`. I have
not assumed that reading.

**not_verified**
- **Everything in the image:** the five e2e files on this tree; conform over `snapshot` and `undo` after
  the change; Python 3.14.7 (the host is 3.12.3); the overlay filesystem.
- **`make scan` with the new baselines.** The host re-evaluation used the lane's own scan output from
  2026-10-04; a fresh scan may carry newer scanner data.
- **The host stand-in is not image evidence:** 40 of 44 ok, the 4 not-ok being the `type -a` cells (as
  in Cycle 1).
- **Verification's cost at the default caps in the image:** measured on the host only (above).
- **A file changing between the cap pass and the copy:** handled by Assumption 4 (recorded as read), and
  untested.
- **Two of `verify`'s defensive branches** are uncovered: a record that cannot be read back or reads back
  different, and an object that cannot be opened.
- **D7 (the demo):** unconfirmed until the operator interview.

**changed_other_features:** none in behaviour. The shared files changed are `README.md` (the snapshot
section's caps paragraph and a "Stored once" bullet), `FOR-MENTOR.md` (Item 17 closed), the three
governance files and the three scan baselines (on `master`, for every image).

**process_failures_recorded**
1. **The code came before the task list.** T016's code and tests were written and passing before the
   modify, plan and tasks records existed. Those records were then written and committed first, and the
   code was committed under T016. The order of record is right; the order of work was not.
2. **My scope helper failed after T016's commit.** The installed `scope-check` block, sourced under
   `set -euo pipefail`, stopped on a `grep` exit 1. The commit had landed; the scope record was then
   written by the fixed helper (`eb6a46d`). That is a defect of my wrapper, not of the block.
3. **Two bugs in my own new tests**, caught on the first run: `"taken:" not in …` also matched `not
   taken:`, and undo's outcome scope is `restore newest`, not `restore 1`. While fixing the second, undo's
   remedy was changed from "run snapshot again" to "run undo <id> --yes again".
4. **One verification wording corrected before commit:** T017 first said the quotes were checked "by
   grep". They were checked by substring match with whitespace normalised, since the spec wraps lines.
5. **T017 scored `SCOPE: out`** (`FOR-MENTOR.md`; `tasks.md` names it without an extension, which the
   extractor does not read). It is recorded as computed, with FLAGGED yes.
6. **Plugin observations, for the mentor to relay** (2.32.0, first session):
   - **`modify`'s number fallback works:** with `005` as a standalone argument, it resolved `005-recover`
     on a non-`modify/` branch without reading stdin. `printf %03d` on `005` gives 005. The send's octal
     note (`008` and `009` give 000) was not exercised.
   - **`modify`'s provenance blocks now set their own inputs** (D89): row 7 came from the blocks, not by
     hand.
   - **Step 10e no longer consults the absent quality-gates library** (D88). It reads `package.json`,
     and there is none here: `none`.
   - **`/specswarm:constitution`, followed as expanded, needed no input for a no-change audit.** Its
     provenance section names the operation used (append N).

**retired_prompts_seen:** `bridge/sends/07-rev11-20261004-002459.md`, superseded by this send and never
built from. Nothing was built from it.

### Implement step 10 — quality validation (specswarm 2.32.0), as the library reported it

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

The gate is **UNKNOWN**. With `block_merge_on_failure: false` and `min_quality_score: 0`, it warns and
does not halt. No component was filled in by hand. The project's own figures are recorded **beside** it
in `.specswarm/metrics.json` → `005-cycle-2.project_measurements_not_scored`. The output is verbatim.

**Host lane** (advisory; scratch venv, Python 3.12.3):
- `make test-host`: **895 passed** (175.5 s); env layer 60/60; hook logic 29/29.
- This feature's units: 78 passed (6 new).
- Coverage of the two tools (line and branch, subprocesses included): `snapshot` 92%, `undo` 88% (20
  statements), together **92%**.
- ruff clean (54 files formatted); mypy strict: no issues in 19 files; shellcheck clean over every
  `*.sh`, `*.bash` and `*.bats`.
- The five 005 e2e files through the host stand-in: 40/44 (the 4 `type -a` cells).
- The publish deny-list read `pass` with the list read before every commit (7 entries, P1–P7 0/0).

**Implement step 9b: decision log** (plugin `scope-tally` and `decision-tally`, 2.32.0, over 005's
`tasks.md` and `decisions.md` after T019; cumulative over Cycles 1 and 2):

```
scope: planned=19 recorded=18 unplanned=0 unrecorded=1 in=12 out=3 none=3 unknown=0 flagged=9 flagged_out=1 other=9 other_out=2
decisions: sections=18 flagged_sections=9 non_flagged_sections=9 sections_without_absent=0 flagged=14 assumed=26 deferred=0 absent=18 inherited=17 low_confidence=0 flagged_low_confidence=0
```

- **Cycle 2 alone** (the differences from Cycle 1's tallies): 4 tasks planned and 4 recorded. T016 `in`,
  T017 `out` (`FOR-MENTOR.md`), T018 `none`, T019 `out` (`.specswarm/metrics.json`, as for T015).
  3 FLAGGED sections with 5 FLAGGED entries; 0 low-confidence (two FLAGGED entries say `medium`).
- `unrecorded=1` is still Cycle 1's T010 (recorded in T009's section).

### Cycle 2 addendum — the mentor's Docker lane at `e50a82f` (2026-10-04)

Source: `../bridge/history.md` 2026-10-04T04:32:39Z (lanes 005-c and 005-d), and the lane's own outputs
in `tests/out/` (`summary.json`: `lane docker`, `git_sha e50a82f…`, exit 0) and `scan/out/`.
`e50a82f` is `810b2c0` plus `reboot.md` only, and the tested HEAD is unchanged.

- **`make test` (005-d): PASSED.** e2e 283/283 (0 not ok). All 44 cells of the five 005 files are `ok`,
  matched by test name in `tests/out/e2e.tap`: records 4/4, restore 10/10, version control 4/4, size
  cap 10/10, refusals 16/16 (the four `type -a` cells included). Units 894 passed + 1 skipped; Go pass.
- **`make scan` (005-c, at `e50a82f`): PASS ×4** (agent, vanilla, bench-driver, adele), with CVE-2026-95619
  baselined in the three Debian images. Deny-list PASS (7 entries, 270 files).

**criteria_reestablished** (superseding Cycle 2's `unconfirmed` for the automated four; the Cycle 2
section itself is unchanged):

- `07 · "of the workspace and prints its identifier, file count and size"` — **executed
  [`tests/e2e/snapshot-records-tracked-untracked-and-ignored-files.bats`, 4/4, lane 005-d at `e50a82f`]**
- `07 · "removes files created after it, and a dry run lists exactly those changes first"` — **executed
  [`tests/e2e/restore-returns-captured-content-and-removes-files-created-after.bats`, 10/10, lane 005-d]**
- `07 · "are unchanged by taking or restoring a snapshot"` — **executed
  [`tests/e2e/version-control-history-index-and-stash-unchanged-by-snapshot-and-restore.bats`, 4/4, lane 005-d]**
- `07 · "is refused or partial, and the verdict names what was excluded and why"` — **executed
  [`tests/e2e/snapshot-over-the-size-cap-is-partial-and-names-what-was-excluded.bats`, 10/10, lane 005-d;
  the second run's raise value of 300000, the bytes new to the store, held in the image]**
- `07 · "restores it with one undo command _(traces to: D7)_"` — **unconfirmed**. Manual (D7): the
  mentor's interview with the operator is next.

Each citation still matches exactly one line of the send.

**Provenance:** `audited_against` is now **`[1, 11]`**, computed by the installed `audit-append` block in
**`scoped`** mode (appended `11`), with a row in `audit-log.md` completing the `none (deferred)` row.
`prompt_revision`, `discovery_revision` and `source_prompt` are untouched.

**reconcile_mode: `scoped`.** This differs from the `full` (2–11) that Cycle 2 said to expect. The
operator asked for 11 to be appended. Revisions 2–10 did not change prompt 07, so they moved no
criterion, and a membership test over criteria-changing revisions finds no hole there.

**process_failures_recorded** (added by this addendum)
- **I committed during the mentor's lane.** `e50a82f` (`reboot.md`) landed while lane 005-c's
  `make test` was running at `810b2c0`. The agent images were stamped `810b2c0` and the bench images
  `e50a82f`, so `bench/run.sh` refused the mixed stamps, and `speedup-bench.bats` setup failed (4 not
  run). The mentor had to re-run it as 005-d. I had reported the cycle done and did not check for a
  starting lane before that last commit. That breaks this instance's own rule: no commits during lane
  runs.

**not_verified** (still open): D7, the operator's demo.

### Cycle 2 addendum 2 — reconcile mode `full`, and D7 observed (2026-10-04)

At the operator's instruction, this addendum supersedes two statements of the addendum above:
`reconcile_mode` and D7's mode. That addendum is left as written (append-only). Its lane evidence
stands, and is not repeated except where cited.

**criteria_reestablished** (final for Cycle 2; supersedes both earlier lists):

- `07 · "of the workspace and prints its identifier, file count and size"` — **executed
  [`tests/e2e/snapshot-records-tracked-untracked-and-ignored-files.bats`, 4/4, in the image: lane 005-d
  at `e50a82f`, `../bridge/history.md` 2026-10-04T04:32:39Z]**
- `07 · "removes files created after it, and a dry run lists exactly those changes first"` — **executed
  [`tests/e2e/restore-returns-captured-content-and-removes-files-created-after.bats`, 10/10, in the image:
  lane 005-d at `e50a82f`]**
- `07 · "are unchanged by taking or restoring a snapshot"` — **executed
  [`tests/e2e/version-control-history-index-and-stash-unchanged-by-snapshot-and-restore.bats`, 4/4, in the
  image: lane 005-d at `e50a82f`]**
- `07 · "is refused or partial, and the verdict names what was excluded and why"` — **executed
  [`tests/e2e/snapshot-over-the-size-cap-is-partial-and-names-what-was-excluded.bats`, 10/10, in the image:
  lane 005-d at `e50a82f`]**
- `07 · "restores it with one undo command _(traces to: D7)_"` — **observed by the operator**
  (`../bridge/history.md` 2026-10-04T04:59:15Z; transcript `bridge/.d7-demo-20261004T044030Z.txt`).
  This was on the live stack from lane 005-d: `timelike-agent` at revision `e50a82f`, image
  `sha256:d4c49415…`, as the agent user under `bash -lc`. The sequence was `snapshot` (verified, 3 files),
  then `rm -rf docs` (the wrong directory), then `undo` (exit 4, the confirmation envelope, nothing
  changed), then `undo --yes` (exit 0, verified, the state before is snapshot 2). The three files' sha256
  are identical before the delete and after the undo. The operator accepted it as one undo command with
  rule 9's confirmation step. The transcript was read by this instance; its hashes and verdicts are as
  stated.

There are **five slice-0 criteria: four automated and one Manual (D7)**. The automated four are executed
in the image, and D7 is observed by a person, not run by a test. Each citation matches exactly one line
of the send. The two revision-11 criteria are *(slice 1)* and are not cited.

**reconcile_mode: `full`.** `audited_against` is now **`[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]`**, computed by
the installed `audit-append` block in `full` mode (appended 2–10 beside 11). `full` appends every
revision in (`prompt_revision`, N]. Its conditions hold:
- revision 11's criteria were checked in full (above);
- removals are visible (the rev-1 send's prompt copy) and none occurred;
- no added criterion of this slice was left unaddressed.

Revisions 2–10 did not change prompt 07. The `audit-log.md` row records the basis and supersedes the
`scoped` row. `prompt_revision`, `discovery_revision` and `source_prompt` are untouched.

**not_verified:** nothing remains open for slice 0's criteria. The earlier `not_verified` items about the
host (stand-in, timing, two defensive branches of `verify`, a file changing mid-snapshot) still stand as
written.
