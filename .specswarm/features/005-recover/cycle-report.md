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
