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

### Cycle 2 ship — `/specswarm:ship` under specswarm 2.32.0 (`19829a6`), 2026-10-04

Run on `005-recover` at **`61356ea`**, the commit the mentor signed off (`../bridge/history.md`
2026-10-04T05:06:58Z), with a clean tree. The session loaded **4.0.1-botbaubble.2.32.0**: the expanded
commands name `…/specswarm/4.0.1-botbaubble.2.32.0`, and the marketplace checkout is at **`19829a6`**
("docs: REBOOT at 2.32.0 …"), which is `installed_plugins.json`'s `gitCommitSha`. **This is the first
field run of D85.**

How it ran: ship Step 1 was run from the installed file. Step 2's `/specswarm:analyze-quality` blocks
(`analysis-context`, `component-applicability`, `tests-agnostic-score`, `unknown-resolvability`,
`module-score`, `overall-score`, `quality-report`) were run from the installed file with `MODULES` =
001's eight, as in the 003 and 004 recipe. Then ship's `quality-source`, `quality-threshold`, the
threshold echo lines and `quality-gate` were run with `CLAUDE_PLUGIN_ROOT` set to that cache path.
`FEATURE_DIR` was **unset** before `quality-source`, so D77's own resolution found the feature. **Step 4
(`/specswarm:complete`) was not run.** The mentor merges `--no-ff` by hand, and complete needs stdin.
Step 5's summary therefore did not run either. The output below is verbatim apart from two lines of mine marked `==`, the
`AQ_TESTS_*` and `components:` echoes I added to show the inputs, and the checkout's absolute path,
written `<repo>/` because it matches publish deny-list entry P2.

```
🚢 SpecSwarm Ship - Quality-Gated Merge
══════════════════════════════════════════

This command enforces quality standards before merge:
  1. Runs comprehensive quality analysis
  2. Checks quality score meets threshold
  3. If passing: merges to parent branch
  4. If failing: reports issues and blocks merge

📍 Current branch: 005-recover


== analyze-quality (specswarm 2.32.0) ==
🔤 Language: Python
AQ_TESTS_LINE=tests|25|?|measured:pytest
AQ_TESTS_SCORE=unavailable:pytest is declared but could not be run on this machine
components:
tests|25|-|unavailable:pytest is declared but could not be run on this machine
docs|15|-|unavailable:sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector
architecture|20|-|unavailable:sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector
security|20|-|unavailable:sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector
bundle|7|-|unavailable:lib/bundle-size-monitor.sh is not in this install
lazy-loading|7|-|unavailable:sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector
images|6|-|unavailable:sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector
tools/agentio|unknown
tools/bin|unknown
scan|unknown
image|unknown
scripts|unknown
bench/benchlib|unknown
bench/bin|unknown
bench/images+run.sh|unknown
excluded: tools/agentio: tests — unavailable: pytest is declared but could not be run on this machine (25 points not counted either way)
docs — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (15 points not counted either way)
architecture — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
security — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
bundle — unavailable: lib/bundle-size-monitor.sh is not in this install (7 points not counted either way)
lazy-loading — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (7 points not counted either way)
images — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (6 points not counted either way)
tools/bin: tests — unavailable: pytest is declared but could not be run on this machine (25 points not counted either way)
docs — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (15 points not counted either way)
architecture — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
security — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
bundle — unavailable: lib/bundle-size-monitor.sh is not in this install (7 points not counted either way)
lazy-loading — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (7 points not counted either way)
images — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (6 points not counted either way)
scan: tests — unavailable: pytest is declared but could not be run on this machine (25 points not counted either way)
docs — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (15 points not counted either way)
architecture — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
security — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
bundle — unavailable: lib/bundle-size-monitor.sh is not in this install (7 points not counted either way)
lazy-loading — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (7 points not counted either way)
images — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (6 points not counted either way)
image: tests — unavailable: pytest is declared but could not be run on this machine (25 points not counted either way)
docs — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (15 points not counted either way)
architecture — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
security — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
bundle — unavailable: lib/bundle-size-monitor.sh is not in this install (7 points not counted either way)
lazy-loading — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (7 points not counted either way)
images — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (6 points not counted either way)
scripts: tests — unavailable: pytest is declared but could not be run on this machine (25 points not counted either way)
docs — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (15 points not counted either way)
architecture — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
security — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
bundle — unavailable: lib/bundle-size-monitor.sh is not in this install (7 points not counted either way)
lazy-loading — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (7 points not counted either way)
images — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (6 points not counted either way)
bench/benchlib: tests — unavailable: pytest is declared but could not be run on this machine (25 points not counted either way)
docs — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (15 points not counted either way)
architecture — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
security — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
bundle — unavailable: lib/bundle-size-monitor.sh is not in this install (7 points not counted either way)
lazy-loading — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (7 points not counted either way)
images — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (6 points not counted either way)
bench/bin: tests — unavailable: pytest is declared but could not be run on this machine (25 points not counted either way)
docs — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (15 points not counted either way)
architecture — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
security — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
bundle — unavailable: lib/bundle-size-monitor.sh is not in this install (7 points not counted either way)
lazy-loading — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (7 points not counted either way)
images — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (6 points not counted either way)
bench/images+run.sh: tests — unavailable: pytest is declared but could not be run on this machine (25 points not counted either way)
docs — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (15 points not counted either way)
architecture — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
security — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
bundle — unavailable: lib/bundle-size-monitor.sh is not in this install (7 points not counted either way)
lazy-loading — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (7 points not counted either way)
images — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (6 points not counted either way)

Overall Quality: unknown (no module could be scored (8 unscored))
📄 Wrote <repo>/.specswarm/features/005-recover/quality-report.json (overall_state: unknown, written by 4.0.1-botbaubble.2.32.0)

== ship Step 2: quality-source ==
NOTE: <repo>/.specswarm/features/005-recover/quality-report.json reports overall_state='unknown' - the score is not a measurement
== ship Step 3 ==
📋 Using project quality threshold: 0% (from min_quality_score)
ℹ️  enforce_gates: false — a failing gate will WARN, not block

🎯 Quality Threshold: 0%
📊 Actual Quality Score: unknown — nothing was measured

❔ Quality gate UNKNOWN — the analysis reported no number
   <repo>/.specswarm/features/005-recover/quality-report.json says overall_state='unknown'
   (no module could be scored (8 unscored))

   Nothing was measured. This is NOT a 0% failure and NOT a pass.


🔧 What would change this:
  - no component of this Python project could be measured: pytest is declared but could not be run on this machine
  - re-running /specswarm:analyze-quality will NOT change this result

⚠️  enforce_gates: false — this gate WARNS and does not block the merge.
   Shipping with quality state 'unknown' is the project's recorded choice, not an oversight.

QUALITY_STATE=unknown
```

`quality-report.json` as written (`.specswarm/features/005-recover/quality-report.json`, committed with
this section):

```
{
  "overall_score": null,
  "overall_state": "unknown",
  "unknown_is": "unresolvable",
  "unknown_why": "no component of this Python project could be measured: pytest is declared but could not be run on this machine",
  "set": "no module could be scored (8 unscored)",
  "modules_scored": 0,
  "modules_total": 8,
  "generated_at": "2026-10-04T05:14:26+00:00",
  "generated_by": "/specswarm:analyze-quality",
  "generated_by_version": "4.0.1-botbaubble.2.32.0"
}
```

**Field results:**
- **D85 held.** The report was read (`QR_READ=yes`), so the gate took the branch that says *the analysis
  reported no number*, and it named the report's `overall_state='unknown'` and its set. It did **not**
  say "nothing reported a score", and it did not repeat the old "was not produced" headline.
- **D77 held** without a hand-set `FEATURE_DIR`: `quality-source` resolved
  `.specswarm/features/005-recover/quality-report.json` from the branch `005-recover`.
- **D72 held:** "What would change this" printed the report's `unknown_why`, and that re-running
  analyze-quality will **not** change the result (`unknown_is: unresolvable`). No re-run was offered as
  the remedy.
- **D71 held:** `modules_scored: 0` beside `modules_total: 8` and "no module could be scored (8
  unscored)". The false `modules_scored: 8` line relayed from 003's ship is gone.
- **The gate is UNKNOWN and warns.** `min_quality_score: 0` (canonical form), `enforce_gates: false`.
  Under this project's recorded choice the merge is not blocked. No number was produced, and none was
  filled in by hand.
- Not exercised: Step 5's `ship-summary-state` line (Step 4 was not run here).

## Cycle 3 — bridge/sends/07-rev11-20261010-050829.md

**Written:** 2026-10-10T06:09:00Z (read from the clock). Not in dispatch mode. **specswarm 4.0.1-botbaubble.2.44.0**:
the expanded `modify`, `plan`, `tasks` and `implement` commands name the cache path
`…/specswarm/4.0.1-botbaubble.2.44.0` (lore `specswarm` Q002; the operator ran `/plugin` in this session after
the install). The sequence was `/specswarm:modify 005 --from-send bridge/sends/07-rev11-20261010-050829.md` on
`modify/005-slice-1` (from `master` `97641da`), then `/specswarm:plan`, `/specswarm:tasks` and
`/specswarm:implement` (Phase 7, T020–T031; T032 held). **Nothing was pushed or merged.**

This path is the send's, `code/.specswarm/features/005-recover/cycle-report.md`; CLAUDE.md names the same file.

**Status in one line:** the state root, its volume, the scheduled snapshot, purge, the lock, import, the trash's
store and restore, and the two revision-11 criteria are built and pass on the host. **The guards (`rm`,
`git reset --hard`, `git push --force`, `git clean`) and what feeds the trash are not built: FOR-MENTOR Item 22
(`e488657`) asks how they reach `rm` and `git`, and is unanswered.** So two of slice 1's five Automated criteria
cannot be met yet, and the README status block is not applied. Nothing has run in the image.

### Group A — cited from `.implement-complete`

Group A: not applicable — no marker on this path

### Group B — copied from the send

| Field | Value |
|---|---|
| source_send | bridge/sends/07-rev11-20261010-050829.md |
| source_prompt | plan/.discover/prompts/07-recover.md |
| prompt_revision | 11 |
| discovery_revision | 15 |
| slice | 1 |

The spec's frontmatter is unchanged (`prompt_revision: 1`, `discovery_revision: 10`,
`audited_against: [1, …, 11]`).

### Provenance (modify Step 2 and Step 9)

Row 4: the same prompt, `N = 11`, already in `audited_against`. Step 9 did not run and nothing was appended, as
the send said. No `audit-log.md` row: no mode was recorded or corrected.

### What was built (Phase 7)

| Task | Commit | What |
|---|---|---|
| — | `e488657` | FOR-MENTOR Item 22, raised before any guard was built |
| — | `19f151f`, `36a03de` | modify, impact analysis, spec slice 1, plan, research R10–R16, data model, contract, tasks |
| T020 | `fd3c423` | agentio: `TIMELIKE_STATE_ROOT` (default `/var/lib/timelike`), `VERSION` (P003), persistence by `st_dev` |
| T021 | `4c97c1c` | the store in `<state>/workspaces/<key>/`; the not-persistent line (FR-27); `session`/`agent` (FR-31); other workspaces named (FR-29); the lock names its holder (FR-38) |
| T022 | `294ffbd` | slice-0 stores imported once, in order, verified (FR-30) |
| T023 | `c01767b` | the stat cache (FR-35) |
| T024 | `d888a46` | the scheduled snapshot: the builtins-only due check in `shell-env.bash`, `libexec/scheduled-snapshot`, default interval 300 s (FR-32–FR-34) |
| T025 | `d54925f` | purge on write: age, then size, never a workspace's newest, time-bounded, named (FR-36, FR-37) |
| T026 | `18eec08` | the trash: `libexec/guard trash-put`, `undo --trash`, its purge (FR-39–FR-41) |
| T027 | `5d8857b` | `/var/lib/timelike` in the image (agent, 0700), the ENV, compose's named volume `timelike-state` |
| T028 | `519385f` | e2e cells (below) |
| T029 | `2811c2b` | carried: `symbols`' index in the state root (Item 20, closed); rule 10's contract text |
| T030 | `bddd93a` | README: the generated command reference only |
| T031 | this commit | the host lane, lint fixes, this report |

### The seams, as decided (spec § Slice 1, D-11 to D-18; research R10 to R16)

1. **State root:** `/var/lib/timelike`, outside every workspace and the home; `TIMELIKE_STATE_ROOT`, read by
   timelike (P002); created in the image owned by `agent`, 0700, so a fresh named volume takes it (Q003).
   **Without a volume, every `snapshot` and `undo` result carries one line** (FR-27):
   `not persistent: /var/lib/timelike is not a mounted volume, so this recovery state dies with the container;
   mount one at /var/lib/timelike (compose.yaml: timelike-state)`. Every result, not the first per session: a
   "first per session" needs a record kept where the line says nothing persists. Vanilla gets nothing.
2. **Keying:** by real path (as slice 0). A workspace moved elsewhere sees `0 snapshots`, and `snapshot list`
   and `undo` name every other workspace in the state root with snapshots, with its path and count.
3. **Slice 0's stores:** imported on first use, in order, verified, marked `imported` in place, each import
   and each failure named.
4. **Guards:** Item 22 (Q1, Q2). Not built.
5. **Force push:** Item 22 Q2 (git's own `pre-push` input, through 001's dispatcher). Not built.
6. **Scripts:** a scheduled snapshot at the shell's start when the last one is older than
   `TIMELIKE_SNAPSHOT_INTERVAL` (default 300 s; `0`, `off`). Measured (R11): **not due, +0.5 ms per shell
   start and no fork; due, 120–145 ms (464 files, 6.7 MB) and 270–300 ms (657 files, 51 MB) on an unchanged
   workspace**. Not taken when the command starts with `snapshot` or `undo`.
7. **Trash:** the store, `undo --trash [ID] [--dry-run] [--yes]`, purge by `TIMELIKE_TRASH_MAX_AGE_DAYS` (30)
   and `TIMELIKE_TRASH_MAX_BYTES` (1 GiB). What feeds it: Item 22 Q3.
8. **Purge:** on write (after a take and after a verified restore), `TIMELIKE_SNAPSHOT_MAX_AGE_DAYS` (30),
   `TIMELIKE_STATE_MAX_BYTES` (4 GiB) over every workspace's content, `TIMELIKE_PURGE_SECONDS` (2); never a
   workspace's newest; a busy workspace skipped and named.
9. **Concurrency:** one `flock` per workspace store, shared by every session and agent; the kernel releases a
   dead holder's lock, so there is no stale-lock state; a live holder is named.

### Group C — written by the code instance

**delegations:** `[]`. No sibling feature was used and no subagent ran.

**criteria_reestablished** (each citation matches exactly one line of the send, `grep -cF` = 1 for all eleven).
Nothing has run in the image, so every mode is `unconfirmed`; host evidence is listed and changes no mode.

- `07 · "records tracked, untracked and ignored-but-not-excluded files of the workspace and prints its identifier, file count and size _(traces to: P5)_"` —
  **unconfirmed** (slice 0; `snapshot-records-tracked-untracked-and-ignored-files.bats`, now on a per-test state
  root; host: test_snapshot.py).
- `07 · "removes files created after it, and a dry run lists exactly those changes first _(traces to: P5)_"` —
  **unconfirmed** (slice 0; `restore-returns-captured-content-and-removes-files-created-after.bats`).
- `07 · "history, index and stash are unchanged by taking or restoring a snapshot _(traces to: P5)_"` —
  **unconfirmed** (slice 0; `version-control-history-index-and-stash-unchanged-by-snapshot-and-restore.bats`).
- `07 · "would exceed the size cap is refused or partial, and the verdict names what was excluded and why _(traces to: P2)_"` —
  **unconfirmed** (slice 0; `snapshot-over-the-size-cap-is-partial-and-names-what-was-excluded.bats`).
- `07 · "a force push, and a clean of untracked files each take an automatic snapshot before running, and the verdict names it _(traces to: P5)_"` —
  **unconfirmed: not built.** Held for FOR-MENTOR Item 22; no e2e file yet.
- `07 · "is restorable from the most recent automatic or scheduled snapshot _(traces to: P5)_"` — **unconfirmed**
  (`a-directory-removed-by-a-script-is-restorable-from-the-most-recent-scheduled-snapshot.bats`, 4 cells;
  host: test_scheduled_snapshot.py restores a directory a Python script removed).
- `07 · "is listed and restorable from a new session, and after the agent's container is recreated _(traces to: P5)_"` —
  **unconfirmed** (`a-snapshot-taken-in-one-session-is-listed-and-restorable-from-a-new-session-and-after-recreate.bats`,
  4 cells: two new-session cells, the recreate on fresh named volumes, and the no-volume line; host: the
  new-session half in test_snapshot_slice1.py).
- `07 · "so the restore itself can be undone, and its verdict names that snapshot _(traces to: P5)_"` —
  **unconfirmed** (`a-restore-first-snapshots-the-workspace-so-the-restore-can-be-undone.bats`, 2 cells; host:
  test_snapshot_slice1.py). FR-19 already did this; nothing in it had to change against the new store.
- `07 · "Deleted files are moved to a restorable trash that is purged by age and size limits _(traces to: P5)_"` —
  **unconfirmed: partly built.** The trash's store, put-back and purge are built and have cells
  (`deleted-files-trash-restorable-and-purged-by-age-and-size.bats`, 4 cells, fed through `guard trash-put`);
  what moves the agent's deletes into it is held for Item 22. The file's header says it is partial.
- `07 · "deletes the wrong directory and restores it with one undo command _(traces to: D7)_"` — **unconfirmed**
  in this cycle (Manual; observed by the operator in Cycle 2, transcript `bridge/.d7-demo-20261004T044030Z.txt`;
  nobody has looked again on this cycle's code).
- `07 · "a snapshot is taken automatically, and the Agent restores from it _(traces to: D16)_"` — **unconfirmed**
  (Manual; the mentor captures it after the lane; it needs a guarded destructive command, so Item 22 first).

**reconcile_mode:** `scoped`. Slice 0's four criteria and four of slice 1's five Automated ones have cells on
this cycle's code; the guards criterion is not built. If Item 22's ruling lets the guards be built in this
cycle, an addendum says so and corrects the mode.

**not_verified**
- **Everything in the image:** every e2e cell above; the hook in the image's three bash styles; the helpers'
  shebang interpreter; the named volume's first-mount ownership (the recreate cell checks it).
- **The scheduled snapshot under other features' cells:** the e2e harness turns it off unless a cell sets
  `TIMELIKE_SNAPSHOT_INTERVAL` (`helpers.bash` `exec_in`), so no other feature's cell runs with it on. Its own
  cells run it at `0` and at the default.
- **Latency in the image:** R11's figures are the host's (3.14.8 venv), not the container's.
- **Note 12's cost on a large store:** verification re-hashes every object a snapshot names, so a scheduled
  snapshot of a workspace with much stored content costs more than R11 shows. Item 22 asks the mentor whether
  to narrow it.
- **Two containers on one volume** (two agents in two containers): `flock` works across containers on one
  host, but no cell runs two containers at once.
- **The purge's time bound** has no test of its own (R14; decisions.md T025).
- **D7 and D16.**

**changed_other_features**
- **001:** `image/rootfs/etc/timelike/shell-env.bash` gains the scheduled-snapshot block (builtins only; forks
  once only when due; never re-entered); `image/Dockerfile` creates `/var/lib/timelike` and sets
  `TIMELIKE_STATE_ROOT`; `compose.yaml` mounts `timelike-state` on the agent, and its "Deliberately no volumes"
  comment now names the one volume; `contracts/output-contract.md` § Session event gains the State root (rule
  10, declared, the send's carried item); `tests/e2e/helpers.bash` gains `state_root_dir`/`state_root_rm` and
  turns scheduled snapshots off by default in `exec_in`.
- **004 (Adele, feature 12's cells):** `adele-isolation-grant-file-and-extend-unreachable-from-agent.bats`'s first
  cell read "no mounts at all"; it now requires exactly one mount, `timelike-state` at `/var/lib/timelike`, and
  still that nothing of Adele's is mounted.
- **011 (`symbols`):** the index moves to `<state root>/workspaces/<key>/symbols.json` (Item 20); its usage line,
  its manifest's `index` and `contracts/symbols-cli.md`'s `index` line change with it, declared.
- **README:** only the generated command reference (`undo --trash`; `symbols`' index line). The prose that says
  snapshots and the index live in the session scratch is now false and is corrected with the README status
  block, after Item 22.
- `pyproject.toml`: the two new helpers are linted and type-checked.

**process_failures_recorded**
- The first run of the hook's K cases used a bash fake helper, which inherited `BASH_ENV`, re-entered the hook
  and recursed until it was killed; the hook now has a re-entry guard and K1 counts exactly one call.
- Cleaning up after it, `pkill -f` on a pattern matched my own command line and killed that shell (against my
  own standing notes).
- An edit to undo's verification dropped its `if left:` guard; 16 units caught it before the commit.
- Three task start times were written composed, not read (T021, T022, T028); each is corrected in
  `decisions.md` from git's commit times, with the correction stated.
- The tasks commit `36a03de` was made before the deny-list ran; it passed when run straight after.
- The not-persistent line was first 217 characters, over rule 13's 200, and was cut; shortened, with the spec
  and contract, before any commit of the tool.

**retired_prompts_seen:** none.

### Host lane

Advisory: files, units and the hooks' logic on the host, never the image. Python 3.14.8 (a scratch venv).
- `make test-host`: **1987 passed, 13 skipped** (pytest tests/unit, 364 s); `test_env_layer.sh` 60 of 60;
  `test_shell_env_hook.sh` **57 of 57** (K1–K13 new: the due check, the re-entry guard, and K13, the no-fork
  probe from inside a workspace with a fresh stamp, which ran rather than skipped); `test_command_not_found.sh`
  33 of 33. Exit 0.
- New units: test_agentio_state.py 6, test_snapshot_slice1.py 15, test_scheduled_snapshot.py 5,
  test_trash.py 5, test_state_root_image.py 6, test_symbols.py +1 (and one moved).
- ruff 0.16.9 (`check` and `format --check`, the Makefile's paths): clean. mypy 2.3.1 `--strict` (pyproject's
  files, the two helpers added): no issues in 30 files.
- shellcheck (scratch shellcheck-py 0.11.0.1) over every changed shell file and the four new e2e files: clean;
  the new files are in Makefile's `SHELLCHECK_FILES`.
- bats 1.14.0 `--count` parses every new and changed e2e file; the slice-0 files' counts are unchanged.
- BuildKit's Dockerfile parser (PyPI `dockerfile` 3.4.0): 58 instructions, 0 unknown.
- Deny-list: PASS before every commit of this cycle (7 entries, P1–P7 0/0), except the tasks commit `36a03de`,
  checked straight after (above).

### Implement step 10 — quality validation (specswarm 2.44.0), as the installed blocks reported it

Run from a scratch script executing the installed blocks (detector, `run_tests`, `run_coverage`, `quality-components`, `quality-scale` with its 2.44.0 rubric-coverage fields, `unmeasured-explains-itself`). Verbatim from the components on:

```
- components:
unit-tests|25|-|unavailable:pytest could not be run on this machine (run_tests returned 2: declared by this project, not installed for /usr/bin/python3)
coverage|25|-|unavailable:pytest could not be run on this machine, so run_coverage printed unknown (rc 1)
integration-tests|15|-|not-applicable:no integration suite is detected by the plugin; the bats e2e run only in the Docker lane
browser-tests|15|-|not-applicable:no web project detected, so there is nothing to drive a browser over
bundle-size|20|-|unavailable:lib/bundle-size-monitor.sh is not present in this install
visual-alignment|15|-|unavailable:screenshot analysis is not implemented
QS_POINTS_TOTAL=115.0000 QS_COVERAGE=0

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

The score is `unknown`, not a number: the merge bar is the mentor's Docker lane, as the send says.

### Then

Done for what Item 22 does not block. **No commit until the mentor says the lane has ended.** After Item 22 is
answered: T032 (the guards, the force-push record, the trash's feed, SC-6's cells), the README status block,
and an addendum here.

### Addendum 1 — after lane 005s1-a and FOR-MENTOR Item 22's ruling

**Written:** 2026-10-10T09:34:47Z (read from the clock), on `modify/005-slice-1`. Same send, same cycle: lane 005s1-a's
fixes, the guards on Item 22's ruling, and the README status block. Instructed by the operator, relaying
`../bridge/feedback/07-20261010-081905-lane-005s1-a-sc7-loop-status-and-new-cves.md` (the lane) and
`../bridge/feedback/07-20261010-064701-item-22-guards-reach-rm-and-git.md` (Item 22), in that file's order.
**Nothing was pushed or merged.** Nothing has run in the image since lane 005s1-a.

**Status in one line:** every slice-1 criterion is now built and has cells; the README block is applied.
None of this addendum's work has run in the image: lane 005s1-b decides it.

| Task | Commit | What |
|---|---|---|
| T033 | `6e9c60b` | lane item 1: SC-7's `scheduled_ids` returned its loop's last match status; SC-7's shells now start in the repository (`exec_in -w`) |
| T034 | `93725e5` | lane item 3: eight `git`-layer entries in both baselines; `DOCKER_CLI_IMAGE` to `docker:29.9.0-cli` (Go 1.26.9) |
| T032 | `c2da532` | the guards, the pre-push record, the trash's feed, note 12, SC-6's cells; FOR-MENTOR Item 22 closed |
| T035 | this commit | the README status block; this addendum |

#### Lane 005s1-a, item 1 (SC-7)

- **The defect the lane found:** `scheduled_ids` ended in `for … do [[ … ]] && …; done`, so it returned the last
  line's non-match. It now matches with `if` and ends `return 0`. No assertion changed.
- **The same shape elsewhere in this cycle's e2e files:** SC-8's two loops (`… && found=yes`, `… && n=…`) were
  not a function's last statement, so they could not fail a cell; they are `if` now too. `helpers.bash`'s new
  loops end in `|| true`. Nothing else matched.
- **A second defect behind it, which the lane could not reach:** SC-7's `in_repo` started the shell in
  `/home/agent` (the image's WORKDIR) and `cd`'d in the command, after the hook had run. The hook snapshots the
  workspace a shell **starts** in, and skips `$HOME`, so the count after line 81 would have been 0. The cells
  now start the shell in the repository (`exec_in -w DIR`, `docker exec -w`), as a harness starts the agent's
  shell in its workspace. This is a test-setup fix, not a change to the feature. **None of SC-7's assertions
  after the helper has run in the image yet.**

#### Lane 005s1-a, item 3 (the scan)

- **(a) Baselined** in `timelike-agent` and `timelike-vanilla`, origin `git`, the files' `review_by`
  (2026-12-27) unchanged:
  - CVE-2026-107778 in `libgssapi-krb5-2`, `libk5crypto3`, `libkrb5-3` and `libkrb5support0`;
  - CVE-2026-67693, CVE-2026-95184 and CVE-2026-95209 (High), and CVE-2026-95210 (Critical, its own reason), in
    `libgnutls30t64`.

  The layer was checked: the pinned base's dpkg status (78 packages) holds none of them, and Debian trixie's
  Depends lead `git` → `libcurl3t64-gnutls` → `libgnutls30t64` and `libgssapi-krb5-2` → the krb5 libraries.
  `evaluate.py report` over the lane's own grype output with the new files gives grype PASS and 0 blocking in
  both images. **A person re-reviews both files, as the scan asks.**
- **(b) The Docker CLI:** `DOCKER_CLI_IMAGE=docker:29.9.0-cli@sha256:1a4c7cb6…` (29.9.0, 2026-10-09, the newest
  release), confirmed by the registry's `Docker-Content-Digest`. The Go build info of its linux/amd64
  `/usr/local/bin/docker` reads `go1.26.9`; 29.8.2 and 29.8.1 read `go1.26.8`. The bench driver and the e2e
  runner both build from this one pin. **Neither was rebuilt here** (no Docker): lane 005s1-b rebuilds both, and
  `docker version --format '{{.Client.GoVersion}}'` is the mentor's check.

#### Item 22's ruling, built (T032; spec FR-35a, FR-42 to FR-47, D-19; research R17)

- **The guards:** functions `rm` and `git` in `shell-env.bash`. They call `/opt/timelike/libexec/guard` by its
  absolute path, then run the real command last, so its output and exit code are its own. The caller's
  `set -e` can't stop the real command, and nothing is blocked. Any command line that isn't guarded runs with
  no fork.
- **The depth bound:** the guards are defined only in a `-c` or interactive shell, never in a script run from a
  file.
  - A guarded `-c` shell exports `TIMELIKE_GUARD_SHELL=$$`. A bash that inherits it walks its ancestors
    through `/proc/<pid>/stat`, with builtin reads, and defines nothing when that shell is one of them.
  - A stale marker doesn't disarm a new top-level `bash -c`.
  - An interactive shell sets no marker, so a harness a person starts from one gets guarded shells.
  - A bash the guarded shell exec'd in its own place (bash execs a `-c` string's last simple command) is told
    from the `bash -lc` double source by a non-exported variable. A unit found this case.
- **What is snapshotted:**
  - `rm -r`, or an `rm` whose options the guard can't read: the workspace of each operand, once each.
  - `git reset --hard`: only with uncommitted tracked changes, or when `git status` can't say.
  - `git clean`: unless `-n`, and unless `clean.requireForce` makes git refuse.
  - A git option before the subcommand that the guard can't read: the shell's workspace.
- **The trash's feed:** every file a guarded `rm` deletes, recursive or not, and every path `git clean -n` lists,
  copied before the real command runs.
  - Never kept, and named: `/`, `$HOME` and its ancestors, and the state root.
  - A file the trash can't take is still deleted and named: up to 5 lines, then a count.
- **The force push:** the `pre-push` step in 001's dispatcher (declared).
  - It buffers git's lines, records each non-fast-forward or deleted ref, then hands the same lines to the
    repository's own hook. It never fails the push.
  - `--no-verify` with a force is caught by the `git` function instead, from the remote-tracking ref, and its
    line says that ref may be stale.
  - A remote given as a URL is recorded without a user or password.
  - A forced push without `--no-verify` makes exactly one snapshot (a unit and an e2e cell check this).
- **Note 12, as ruled:**
  - `taken` re-hashes the objects new to the snapshot, and checks presence, type and size for objects the last
    verified take proved. The stat cache is now written only after a take verifies.
  - A restore (`undo ID --yes`, `undo --trash ID --yes`) re-hashes every object it will write before writing
    any. A mismatch refuses, names the object and path, removes the object, and writes nothing.
  - Slice 0's condition-4 unit was rewritten to the ruling (a damaged object new to a snapshot is still caught
    at take). A new unit covers a rotted proven object caught by the restore.
- **The measured cost on the host (R17):**
  - a guarded single-file `rm`: 74–77 ms, against 1 ms for `command rm`;
  - a guarded `rm -r` in a 400-file workspace (snapshot and trash): 115–136 ms;
  - `git status` through the function: 3 ms, the same as `command git`.

#### The README (T035)

The send's `## README status` block is applied, because every slice-1 Automated criterion is now built:
- row 07 reads `slices 0, 1 of 0–2`, with its new "What it does";
- the Status paragraph is verbatim (18 of 38; Next: 15 slice 1, 02 slice 1);
- the `snapshot`/`undo` section now covers the state root, the named volume, what a plain `docker run` means,
  purge, the guards, the trash, and the scheduled snapshot for scripts;
- its "Taken" sentence follows note 12's ruling;
- the `symbols` line names the state root;
- the command reference is current (`readme_reference --check`, 13 tools).

No value claims (P6).

**Held, for the mentor:** README § "The session scratch" still says snapshots and the `symbols` index live in
the session scratch, and that "a persistent state root is 07 slice 1, not yet built". Both are now false. The
block says "Nothing else in the README changes", so it is untouched. Correcting it is one paragraph, and needs
your word.

#### Group C, as it now stands (supersedes § Cycle 3's where it differs)

**delegations:** `[]`.

**criteria_reestablished.** The citations are § Cycle 3's eleven. Nothing in this addendum has run in the image,
so every mode is still `unconfirmed`. Only these change:
- `07 · "a force push, and a clean of untracked files each take an automatic snapshot before running, and the verdict names it _(traces to: P5)_"` —
  **unconfirmed: built.**
  - Cells: `a-recursive-delete-hard-reset-force-push-and-clean-each-take-an-automatic-snapshot.bats`, 12 of them:
    - `rm -rf` in three styles;
    - a hard reset, a clean, and forced pushes with and without `--no-verify`, against a bare remote;
    - a script that isn't guarded, keeps its exit code and is restored from the scheduled snapshot;
    - a decoy on PATH;
    - `type -a` in three styles.
  - Host: test_guard.py, 26 units, on the real chain.
- `07 · "is restorable from the most recent automatic or scheduled snapshot _(traces to: P5)_"` —
  **unconfirmed.** Lane 005s1-a failed all 4 cells on the test's defect. Its fix (T033) has not run in the
  image.
- `07 · "Deleted files are moved to a restorable trash that is purged by age and size limits _(traces to: P5)_"` —
  **unconfirmed: built.** The cells now feed the trash through the agent's own `rm`; they no longer call
  `guard trash-put`.
- `07 · "a snapshot is taken automatically, and the Agent restores from it _(traces to: D16)_"` — **unconfirmed**
  (Manual). It can now be captured after lane 005s1-b.

**reconcile_mode:** `full` (corrected from `scoped`). Every criterion of the send is built and has cells on
this cycle's code. Slice 0's four keep theirs, on per-test state roots.

**not_verified**
- **Everything in the image:** every cell, the guards in the three styles, the pre-push step under the image's
  `GIT_CONFIG_*`, the new Docker CLI pin's Go version, and the scan with the new baselines.
- **Other features' cells with the guards on:** the harness leaves the guards on, and no switch exists.
  - Six other e2e files `rm` a temp file inside their container scripts (`a-bare-python-package-install-…`,
    `command-not-installed-…`, `announcement-generated-…`, `announcement-at-most-60-lines-…`,
    `one-command-prints-the-agents-resource-budget`, `timelike-tools-manifest-json-…`). Each reads its output
    by key, and a `timelike:` trash line doesn't match a key, so I expect no change. Not run.
  - SC-8's recreate cell uses `command rm`.
  - The bench's catalog runs no `rm`, `git reset`, `git clean` or `git push`.
- **git aliases** (`git rh` for `reset --hard`) are not resolved. That would cost a fork per git command.
- **A harness started from inside a guarded `-c` shell** gives its own shells no guards (the marker's
  ancestor). A person's interactive shell sets no marker, so the common case is guarded.
- **One measurement session ran its loops unguarded.** It was discarded and the cause was not found (R17);
  three reruns, one in a fresh directory, were guarded. The units cover every path that defines or skips the
  functions.
- **The arm64 Docker CLI's Go version** (amd64 read only). Two containers on one volume. The purge's time bound
  has no test of its own. D7 and D16.

**changed_other_features** (in addition to § Cycle 3's)
- **001:**
  - `shell-env.bash` defines the guards. The spec gains FR-18a, declared.
  - The hook dispatcher gains the `pre-push` step. The spec gains FR-20a, declared.
  - `tests/host/test_shell_env_hook.sh`'s Q2 (the functions kept on purpose) and Q4 (the marker's pid) are
    updated, with nothing loosened.
  - `tests/e2e/helpers.bash`: `exec_in -w DIR`.
  - `Makefile`: the dispatcher and the new bats file are in `SHELLCHECK_FILES`.
- **007:** the announcement gains two lines after `snapshot`/`undo` (what is guarded, `type -a`,
  `command rm`, scripts), in `tools/bin/timelike` and `contracts/timelike-announce-tools.md`, declared.
- **002 and the e2e runner:** `DOCKER_CLI_IMAGE` (`pins.env`).
- **The scan baselines** of `timelike-agent` and `timelike-vanilla`.
- **README:** the status block, as instructed.

**process_failures_recorded**
- **SC-7's cells went to the lane with two defects:** the helper's return status, and a shell started outside
  the workspace. The first was mine, and it was reachable by running the helper's loop under `set -e` on the
  host, which I did not do before the lane. The second was found only by reading on past line 81.
- **T034's start time was not read** (`decisions.md` says so); T033 and T034 were edited before either was
  committed.
- **The unexplained unguarded measurement session above.** It was caught because its numbers were implausible,
  and was not used.

**retired_prompts_seen:** none.

#### Host lane (this addendum's tree)

- `make test-host` (Python 3.14.8, scratch venv): **2014 passed, 13 skipped** (pytest tests/unit, 450 s); `test_env_layer.sh` 60 of 60; `test_shell_env_hook.sh` 57 of 57 (Q2 and Q4 updated for the guards); `test_command_not_found.sh` 33 of 33. Exit 0.
- New: test_guard.py 26 units (real bash with the hook, the real rm and git, a bare remote, the dispatcher); test_snapshot.py +1 (a rotted proven object caught by the restore), its condition-4 test rewritten to the ruling.
- ruff (check, format --check) clean; mypy --strict: no issues in 30 files; shellcheck 0.11.0 over the Makefile's 84 `SHELLCHECK_FILES` (the dispatcher and the SC-6 file added): clean; bats --count: SC-6 12, SC-7 4, SC-8 4, SC-10 4.
- Deny-list: PASS before every commit of this addendum (7 entries, P1–P7 0/0).

Implement step 10 was not rerun. The installed blocks can't run pytest here, so the score is `unknown`, as in
§ Cycle 3.

#### Then

Done. **No commit until lane 005s1-b has ended.** Lane 005s1-b is the full lane (`test`, `bench-images`,
`scan`, `lint`): T032 reaches the image, and the pins moved. D16 is the mentor's, after the lane.

### Addendum 2 — README § "The session scratch" corrected, on the operator's word

**Written:** 2026-10-10T13:58:04Z (read from the clock), on `modify/005-slice-1`, after `0be6679`. **Not yet
committed:** no commit until lane 005s1-b has ended.

- **Addendum 1's held item is resolved.** The operator said to correct the paragraph, and to keep the README
  current with each build from now on. § "The session scratch" no longer lists snapshots or the `symbols` index
  in the scratch, and no longer says the state root is not yet built. A new paragraph names what lives in the
  state root (`/var/lib/timelike`, `TIMELIKE_STATE_ROOT`): snapshots, the trash and the `symbols` index, on the
  `timelike-state` volume. The intro's What and Status are untouched.
- **changed_other_features** gains: README § "The session scratch" (001's scratch description).
- **The findings reported to the operator at addendum 1's close are all in addendum 1:** the guards on in
  other features' e2e cells with no switch (`not_verified`); git aliases and a harness under a guarded `-c`
  shell (`not_verified`); the unexplained unguarded measurement session (`not_verified`,
  `process_failures_recorded`); SC-7's two defects and my missed `set -e` check (`process_failures_recorded`);
  the Docker CLI not rebuilt here and the baselines awaiting a person's review (lane item 3). Nothing else
  was found after it.

### Addendum 3 — lane 005s1-c: the `bash -ic` cells read output by line position

**Written:** 2026-10-11T07:29:16Z (read from the clock), on `modify/005-slice-1`. Committed with T036.

- **Addendum 2's "Not yet committed" line is stale:** it went in as it stood in `7306473`, on the operator's
  instruction, after lane 005s1-b was void (the stamp-check refused the dirty tree).
- **Lane 005s1-c** (`7306473`; rerun c2): unit 2024 passed, 3 skipped; e2e 646 of 649; bench-images, scan and
  lint pass. The Docker CLI reports `29.9.0 go1.26.9`. Lane 005s1-a's items are fixed in the image.
- **The three failures were this cycle's test defect,** not the feature's: SC-7 `[bash -ic]`, and SC-6
  `[bash -ic]`'s recursive delete and `type -a`. An interactive bash with no terminal prints two job-control lines
  first, and the cells read by position.
- **T036:** `drop_ic_notty_lines` (`tests/e2e/helpers.bash`) drops exactly those two lines in the ic style.
  - Each line is matched whole, at most once, in bash's order, and only at the start. Only the process group may
    vary: `-1` here, a pid on a host.
  - Both files' `in_repo` call it, so every positional assertion stays as written, unloosened.
  - `:191`'s id read (a `bash -c` cell the ic lines can't reach) now finds the newest row by its form and
    requires it to be `scheduled`.
  - No other file of this cycle has an ic cell.
- **criteria_reestablished:** unchanged from addendum 1. Every mode stays `unconfirmed` until lane 005s1-d runs
  SC-6 and SC-7 in the image.
- **not_verified:** the cells in the image. On the host, the helper was exercised under a real `bash -ic` with no
  terminal. shellcheck is clean over the 84 files.
- **changed_other_features:** `tests/e2e/helpers.bash` gains the helper. It is called only from this cycle's two
  files.
- **process_failures_recorded:** the ic cells went to the lane unrun. T036's start time was not read.
- **Then:** lane 005s1-d is `test` only. Bench-images, scan and lint at `7306473` stand. D16 is captured, and
  the mentor holds it for the operator's interview.
