# Decisions Log — Feature 005
> Generated at 2026-10-03T01:59:45+00:00
> Spec: .specswarm/features/005-recover/spec.md

## Decision Key

| Tag | Meaning |
|-----|---------|
| ASSUMED | Assumption made without explicit spec guidance (confidence: high/medium/low) |
| DEFERRED | Decision postponed — noted for later resolution |
| FLAGGED | Judgment call between alternatives — requires review |
| ABSENT | What was NOT done and why — forced reflection on gaps |
| INHERITED | Assumption carried forward from a prior task's output |

---

### T001: fixture tests/e2e/fixtures/recover-repo.sh — a real repository built by git (delegate A)
**Started:** 2026-10-03T02:00+00:00 (delegated) | **Completed:** 2026-10-03T02:12:44+00:00

INHERITED: (none — first task)
ASSUMED: written by a general-purpose delegate from the contract and tasks.md alone, never seeing the tools; reviewed here (confidence: high)
ASSUMED: rmsrc.sh is tracked, mode 0755; the pre-commit hook is installed after the last commit and writes DIR/../hook-ran, so a marker can only come from something else running it (delegate's choice, kept) (confidence: high)
FLAGGED: none
ABSENT: no hand-written .git content anywhere (P005); no socket or device files (units cover the FIFO; the agent cannot make devices)
Verification: bash -n and dash -n pass; run on the host inside the T013 stand-in: builds the expected tree; two .git manifests in a row byte-identical; shellcheck 0.11.0 clean after one intentional SC2016 (the script's own text) was marked with its reason
SCOPE: in (1 changed files)

### T003: e2e SC-1 — snapshot-records-tracked-untracked-and-ignored-files.bats (delegate A)
**Started:** 2026-10-03T02:00+00:00 (delegated) | **Completed:** 2026-10-03T02:12:44+00:00

INHERITED: T001's fixture; the contract's JSON fields and verdict form (confidence: high)
ASSUMED: counts compared with find over the workspace with every .git pruned; restore of one tracked, one untracked and one ignored file checked by sha256 and the full manifest, never by the tool's message (P004) (confidence: high)
FLAGGED: none
ABSENT: not run in the image here (no Docker, R10): the Docker lane decides; the host stand-in (T013) is advisory
Verification: host stand-in (T013): 4/4
SCOPE: in (1 changed files)

### T004: e2e SC-2 — restore-returns-captured-content-and-removes-files-created-after.bats (delegate A)
**Started:** 2026-10-03T02:00+00:00 (delegated) | **Completed:** 2026-10-03T02:12:44+00:00

INHERITED: T001's fixture; data-model's plan rows (confidence: high)
ASSUMED: the dry-run plan must equal the test's own list of the five changes it made, as a sequence (sorted by path, remove before restore) (confidence: high)
FLAGGED: review fix — check_envelope read the envelope's confirm through $JPY after a later jpy call had replaced it, so it ran "<absent>"; re-reads it first (a test bug, found by the T013 host stand-in) (confidence: high)
FLAGGED: review change — after a restore, a bare repeated "undo --yes" must change nothing (was "undo 1 --yes"), pinning the amended default (FR-14; T012) (confidence: high)
ABSENT: the verification-failure path (exit 1, "left N differences") is not reachable without a fault hook; not tested end to end
Verification: host stand-in (T013): 10/10 after the fixes
SCOPE: in (1 changed files)

### T005: e2e SC-3 — version-control-history-index-and-stash-unchanged-by-snapshot-and-restore.bats (delegate A)
**Started:** 2026-10-03T02:00+00:00 (delegated) | **Completed:** 2026-10-03T02:12:44+00:00

INHERITED: T001's fixture (commits, staged change, stash, repository hook, nested repository) (confidence: high)
ASSUMED: the .git manifest covers every entry under every .git (path, mode, sha256) plus git log, stash list and diff --cached, read with GIT_OPTIONAL_LOCKS=0 so the reading itself cannot touch the index (confidence: high)
FLAGGED: none
ABSENT: on the host the image's hook dispatcher and /etc/gitconfig are absent; the hook-never-ran assertion is only meaningful in the image
Verification: host stand-in (T013): 4/4
SCOPE: in (1 changed files)

### T006: e2e SC-4 — snapshot-over-the-size-cap-is-partial-and-names-what-was-excluded.bats (delegate A)
**Started:** 2026-10-03T02:00+00:00 (delegated) | **Completed:** 2026-10-03T02:12:44+00:00

INHERITED: T001's fixture plus two large files the test writes (confidence: high)
ASSUMED: the size-cap raise value is the total of all files (what would have captured everything); the per-file raise value is the largest file (confidence: medium)
FLAGGED: review fix — size_matches runs its own =~, which clobbered BASH_REMATCH before the second size was read; the groups are kept in locals first (a test bug, found by the T013 host stand-in) (confidence: high)
ABSENT: unreadable-file and special-file exclusions are covered by units only (the agent cannot make devices; a 000 file is a unit)
Verification: host stand-in (T013): 10/10 after the fix
SCOPE: in (1 changed files)

### T007: e2e FR-2 and R7 — snapshot-refuses-home-root-and-their-ancestors.bats (delegate A)
**Started:** 2026-10-03T02:00+00:00 (delegated) | **Completed:** 2026-10-03T02:12:44+00:00

INHERITED: the amended contract: refusals are verdicts on stdout with "do instead:" (T012) (confidence: high)
ASSUMED: nothing is stored on a refusal, checked by listing the store directory (confidence: high)
FLAGGED: none
ABSENT: the type -a cells can only pass in the image (they pin /opt/timelike/bin); on the host stand-in they fail by construction
Verification: host stand-in (T013): 12/16, the 4 failures being exactly the type -a cells; shellcheck clean after an unused local was removed
SCOPE: in (1 changed files)

### T008: units tests/unit/test_snapshot.py and tests/unit/test_undo.py (delegate B)
**Started:** 2026-10-03T02:00+00:00 (delegated) | **Completed:** 2026-10-03T02:12:44+00:00

INHERITED: conftest's subprocess conventions; test_conform.install for the conform run (both tools in one bindir); test_adele_cli's load_conform pattern (confidence: high)
ASSUMED: written from the contract alone by a general-purpose delegate, then run against the tools: 70 of 71 passed first time; the one failure was the tool's wording against the contract, and the tool was changed (T012) (confidence: high)
FLAGGED: review addition — test_a_repeated_undo_yes_changes_nothing_the_default_skips_safety_snapshots pins the amended default (FR-14; T012) (confidence: high)
ABSENT: no slow marker on the two 10 s lock tests (none is registered in pyproject; adding one is outside these files); the verification-failure path needs a fault hook and is not tested
Verification: 72 passed (test_snapshot.py + test_undo.py, venv pytest 8.4.2, Python 3.12.3); ruff and ruff format clean after line-length and B904 fixes
SCOPE: in (2 changed files)

### T009 and T010: tools/bin/snapshot — workspace, store, walk, exclusions, take and list; planner, apply, verify
**Started:** 2026-10-03T02:05+00:00 | **Completed:** 2026-10-03T02:12:44+00:00

INHERITED: spec D-1 to D-10, research R1–R8, data-model, contracts/recover-cli.md (confidence: high)
ASSUMED: T009 and T010 are one file and were written as one; they are committed together and both ticked by this commit (confidence: high)
FLAGGED: refusals, a missing snapshot and a failed verification are verdicts on stdout (an Outcome result, exit 1 or 3), not stderr errors — chose this over the contract's first wording because timelike-conform's probes run in conform's own directory (the home directory in the image), and C3/C4 need a header on stdout; adele status is the precedent. Contract amended (T012) (confidence: high)
FLAGGED: the default restore target skips safety snapshots ("before undo …") — chose this over "the newest of all" because a second bare undo --yes would otherwise undo the first (rule 7, idempotent). Spec FR-14 and the contract amended (T012) (confidence: high)
ASSUMED: dir modes are set after everything inside them is written, deepest first, so a 0500 directory cannot block its own restore (confidence: high)
ABSENT: no restore of file times or owners (spec assumption 3); no fsync (a crash mid-restore is covered by the safety snapshot, not by durability); a directory whose mode forbids writing at restore time (changed after the snapshot) can still fail the restore, naming the path and the safety snapshot
Verification: ruff, ruff format, mypy strict clean; timelike-conform passes on both tools from a project directory and from the home directory; smoke and edge runs on the host (planted symlink at a parent path, planted .git, type changes, FIFO, unreadable file, size cap largest-first, per-file limit, entry cap, bad env value, unknown id); 72 units pass
SCOPE: in (1 changed files)

### T011: tools/bin/undo — loads snapshot from its own real directory and runs the undo command
**Started:** 2026-10-03T02:20+00:00 | **Completed:** 2026-10-03T02:12:44+00:00

INHERITED: T009–T010's UNDO_TOOL, undo_main and undo_configure (confidence: high)
ASSUMED: SourceFileLoader on the realpath of __file__, registered in sys.modules before exec (research R8) (confidence: high)
FLAGGED: none
ABSENT: no second copy of any logic in undo; nothing undo does is reachable except through snapshot's code
Verification: conform passes with both installed together (unit and host); a first conform attempt failed because the shebang rewrite kept -I (my install's error, not the tool's), recorded in the cycle report
SCOPE: in (1 changed files)

### T002: lint lists — pyproject.toml (ruff extend-include, mypy files) and Makefile SHELLCHECK_FILES
**Started:** 2026-10-03T02:05+00:00 | **Completed:** 2026-10-03T02:12:44+00:00

INHERITED: the two tool files (T009–T011) and the six e2e files (T001, T003–T007) the lists name (confidence: high)
ASSUMED: committed after the files exist, so no list names a missing file at any commit (confidence: high)
FLAGGED: none
ABSENT: no other Makefile change: e2e discovery is by directory, so make test runs the new bats files without being told
Verification: ruff check and ruff format --check clean over tools tests scan bench (54 files); mypy 2.4.0 strict "no issues found in 19 source files" (corrected in T015: first written as 2.3.1, the version an earlier venv had); shellcheck 0.11.0 clean over the extended SHELLCHECK_FILES
SCOPE: in (2 changed files)

### T012: reconcile the delegates' tests and the tools against the contract
**Started:** 2026-10-03T02:30+00:00 | **Completed:** 2026-10-03T02:12:44+00:00

INHERITED: T003–T011 (confidence: high)
ASSUMED: disagreements are decided by the contract; where the contract was wrong or silent, the contract is amended and the amendment is recorded in it (confidence: high)
FLAGGED: contract amended — "Outcomes are verdicts, errors are errors" (conform's probes); both delegates were told mid-task and wrote to it (confidence: high)
FLAGGED: spec FR-14 and contract amended — undo's default skips safety snapshots (rule 7); spec FR-7 and SC-4 amended — the entry-cap verdict names the cap, not a count, because the walk stops at the cap (confidence: high)
ASSUMED: the tool's store-refusal remedy changed to the contract's exact words (the one unit that failed) (confidence: high)
ABSENT: no change to any criterion text; spec D-1 to D-10 unchanged
Verification: 72 units pass; host stand-in 40/44 (the 4 being the image-only type -a cells)
SCOPE: none — no files outside the feature's artifacts changed

### T013: e2e on the host through a docker stand-in (advisory)
**Started:** 2026-10-03T02:35+00:00 | **Completed:** 2026-10-03T02:12:44+00:00

INHERITED: T001, T003–T007 and the tools (confidence: high)
ASSUMED: a scratchpad stand-in for docker (exec runs the command here with the test's -e variables, a stand-in HOME and the two tools on PATH; inspect answers stamp_check; run serves pyq with the host python) plus bats-core v1.14.0 (the pinned version) is a fair advisory check of the bats logic, not of the image (confidence: high)
FLAGGED: COLUMNS=1000 in the stand-in — chose it over leaving the six FR-2 cells failing because the host's scratchpad home path is long enough that the remedy line was cut at 200 columns; the image's /home/agent is not (confidence: medium)
ABSENT: nothing here is image evidence: no /etc/gitconfig layer, no hook dispatcher, host git 2.43 and Python 3.12; the stand-in is not committed (it lives in the scratchpad)
Verification: 44 tests: 40 ok; the 4 not-ok are the type -a cells, which pin /opt/timelike/bin; two test bugs found and fixed (T004, T006)
SCOPE: none — no files outside the feature's artifacts changed

### T014: README — "snapshot and undo — wrong turns are recoverable"
**Started:** 2026-10-03T02:25+00:00 | **Completed:** 2026-10-03T02:12:44+00:00

INHERITED: the contract as amended (default target, outcomes) (confidence: high)
ASSUMED: the README is where this project announces tools (003's decision, kept); timelike's tool list lists both automatically (confidence: high)
FLAGGED: none
ABSENT: no harness context file inside the image announces them (003's precedent: none exists yet)
Verification: the section's statements checked against the tool (defaults, variables, the default target, where snapshots live)
SCOPE: in (1 changed files)

### T015: host lane, coverage, implement step 10, cycle report § Cycle 1, metrics entry
**Started:** 2026-10-03T02:40+00:00 | **Completed:** 2026-10-03T02:16:55+00:00

INHERITED: T001–T014 and their verification (confidence: high)
ASSUMED: every criterion is unconfirmed until the Docker lane runs on this branch; the host lane and the host stand-in are advisory (as in 001 and 003) (confidence: high)
FLAGGED: none
ASSUMED: corrected two of my own records in place, each saying so: T002's mypy version (2.3.1 → 2.4.0, the venv's) and the recorded run_coverage exit (rc 0 → 1, re-measured) (confidence: high)
ABSENT: no Docker lane (R10); no ship or merge (they wait for the mentor's sign-off, and ship's D85 is its own field run); no demo_points_reached; no Group A (no marker on this path)
Verification: make test-host 889 passed, 60/60, 29/29; coverage 93% for the two tools; ruff, mypy, shellcheck clean; implement step 10 run from the installed 2.27.0 blocks (unknown, warned); all five criterion citations match one send line each
SCOPE: out — .specswarm/metrics.json (1 of 1 changed files) (task has FLAGGED: no)

### T016: the size cap counts bytes new to the store; "taken" after a restorability check (Cycle 2)
**Started:** 2026-10-04T03:09+00:00 | **Completed:** 2026-10-04T03:20+00:00

INHERITED: plan's conditions 3 and 4 (resolution Q1; `stack.md` note 12) via send 07-rev11-20261004-030207; conditions 1 and 2 checked as met by the existing code and units (confidence: high)
FLAGGED: the size cap's unit is now the content a snapshot adds to the store, so an over-the-cap snapshot is less partial when part of the workspace is already stored, and the raise line names the new content, not the workspace's whole size; contract, data model and spec FR-6 amended to say so, declared (confidence: high)
FLAGGED: files sharing one content are left out together, largest content first, ties by smallest path; leaving out one copy alone saves nothing (confidence: high)
FLAGGED: verification re-hashes every object a snapshot names (one read of its distinct content), not only the objects it wrote, because `put` trusts an object it finds in place; a damaged object is removed so the next snapshot stores it again (confidence: medium — the cost is one extra read per snapshot; measured in T019)
ASSUMED: the verdict lines stay byte-identical (the lane established them); `stored_bytes` and `verified` are JSON additions only (confidence: high)
ASSUMED: a failed verification is an Outcome (exit 1, `do instead:`), as the contract treats a failed restore verification; the record is deleted and its id stays used (FR-11) (confidence: high)
ASSUMED: undo's safety snapshot goes through the same check, and a failure there applies nothing — D-10's "an undo is undoable" depends on it (confidence: high)
ABSENT: no change to the walk, the plan, apply or the lock; no record version bump (readers require neither new field)
Verification: units 78 passed (72 + 6 new; 1 changed for the cap's unit); ruff, ruff format, mypy clean; the five 005 e2e files through the host stand-in 40/44 (the 4 being the image-only type -a cells, as in Cycle 1), SC-4's raise value 300000 included
SCOPE: in (5 changed files)

### T017: spec § Revision 11, D-5 and D-7 confirmed, Item 17 closed (Cycle 2)
**Started:** 2026-10-04T03:20+00:00 | **Completed:** 2026-10-04T03:22+00:00

INHERITED: the prompt diff between the rev-1 and rev-11 sends (additions only); plan's resolution in ../bridge/feedback/07-20261003-022613-snapshot-store-and-persistence.md (confidence: high)
ASSUMED: the constraint's slice-0 part is "outside the workspace, never inside it or its .git", which holds as built; the rest is slice 1's (the send's reading, confirmed by plan's "Slice 0 stays as built") (confidence: high)
ASSUMED: "carried" means recorded in the spec with their slice marker and not built (confidence: high)
FLAGGED: Item 17's decisions 1, 2, 3 and 6 had no separate ruling; the item closes on the send's instruction with those standing as built, said in the item (confidence: medium)
ABSENT: no criterion text of slice 0 changed; SC-1 to SC-5 untouched
Verification: the constraint and both criteria are quoted from the send word for word (checked by substring match with whitespace normalised, since the spec wraps lines)
SCOPE: out — FOR-MENTOR.md (1 of 1 changed files) (task has FLAGGED: yes)

### T018: provenance — revision 11 deferred until the lane (Cycle 2)
**Started:** 2026-10-04T03:22+00:00 | **Completed:** 2026-10-04T03:23+00:00

INHERITED: modify Step 2 row 7 (computed by the installed provenance-inputs and provenance-row blocks: N 11, prompt_revision 1, audited_against [1]) (confidence: high)
ASSUMED: the mode will be `full` (2–11): removals are visible (the archived rev-1 send), none occurred, revisions 2–10 did not change prompt 07, and the slice-1 criteria are outside a slice-0 spec rather than unaddressed criteria of it (the mentor's 3c skips another slice's criteria) (confidence: medium)
FLAGGED: nothing is appended now — this cycle changed code that slice 0's criteria rest on, so the append waits for the mentor's Docker lane, as in 001 cycles 5 and 6 (confidence: high)
ABSENT: prompt_revision, discovery_revision and source_prompt untouched; spec frontmatter unchanged
Verification: audit-log.md created with the plugin's header and one `none (deferred)` row
SCOPE: none — no files outside the feature's artifacts changed

### T019: host lane, coverage, implement step 10, cycle report § Cycle 2, metrics entry
**Started:** 2026-10-04T03:23+00:00 | **Completed:** 2026-10-04T03:45+00:00

INHERITED: T016–T018 and their verification; Cycle 1's recipes (stand-in, coverage rc, step-10 blocks) (confidence: high)
ASSUMED: every automated criterion is unconfirmed until the mentor's Docker lane on this cycle's commit, since T016 changed the code under SC-1, SC-2 and SC-4 (confidence: high)
ASSUMED: the snapshot-time comparison (f83e984 vs now, on the host) is advisory and recorded beside the plugin's result, never scored (confidence: high)
FLAGGED: none
ABSENT: no Docker lane (R10); no ship or merge; no demo_points_reached; no Group A (no marker on this path); audited_against unchanged (T018)
Verification: make test-host 895 passed, 60/60, 29/29; coverage 92% for the two tools; ruff, mypy, shellcheck clean; stand-in 40/44; implement step 10 from the installed 2.32.0 blocks (unknown, warned); all five criterion citations match one send line each (grep -cF)
SCOPE: out — .specswarm/metrics.json (1 of 1 changed files) (task has FLAGGED: no)

---

## Cycle 3 — 07 slice 1 (send `bridge/sends/07-rev11-20261010-050829.md`), specswarm 2.44.0

Guards and the trash's feed are held for FOR-MENTOR Item 22 (`e488657`, raised 2026-10-10T05:15:03Z).

### T020: agentio's state root
**Started:** 2026-10-10T05:21:06Z | **Completed:** 2026-10-10T05:22:15Z

INHERITED: (none — first task of the cycle); spec FR-25–FR-28, research R10
FLAGGED: persistence decided by `st_dev` differing from `/`'s, chose it over `os.path.ismount` because the e2e cells use a subdirectory of the volume as their state root, which ismount calls not mounted though it persists (confidence: high)
ASSUMED: an unreadable root is "not persistent" — unknown is never reported as the good answer (confidence: high)
ASSUMED: unit tests get a state root beside the scratch root (`<scratch>-state`) in conftest's base_env, so no test writes /var/lib/timelike (confidence: high)
ABSENT: any caller yet — snapshot moves in T021; no cache-wide layout migration (VERSION 1 is the first layout)
Verification: test_agentio_state.py 6 passed; test_agentio.py and test_agentio_startup.py unchanged (83 passed with them, 3.14.8 venv)
SCOPE: out — tests/unit/test_agentio_state.py (1 of 3 changed files) (task has FLAGGED: yes)

### T021: snapshot's store in the state root; persistence line; attribution; other workspaces; lock holder
**Started:** 2026-10-10T05:22:21Z (T020's commit time, from git; a composed time was written here first and corrected) | **Completed:** 2026-10-10T05:34:08Z

INHERITED: agentio.state_root / ensure_state_root / state_persistent / not_persistent_line — from T020 (confidence: high)
FLAGGED: the not-persistent line is set aside by slice 0's unit helpers (text_of, doc_of) and asserted by test_snapshot_slice1.py on raw stdout, chose that over pointing unit state roots at a device unlike `/`, because the image's unit lane has no such device and the line's presence must follow the filesystem, not the test (confidence: high)
FLAGGED: the line was shortened to fit rule 13's 200 columns (it was 217 at the default root and was cut); spec FR-27 and the contract changed with it, declared (confidence: high)
FLAGGED: the lock file is emptied on release, so a later wait never names a holder that has gone; a holder only ever names itself while it holds the flock (confidence: high)
ASSUMED: slice-0 records lack session/agent; JSON shows them as null (confidence: high)
ASSUMED: one slice-0 unit relied on "another session = an empty store"; since slice 1 sessions share a store (FR-23 as amended), it now uses another state root (confidence: high)
ABSENT: import (T022), stat cache (T023), purge (T025); e2e not run (no Docker here)
Verification: test_snapshot.py, test_undo.py, test_snapshot_slice1.py — 84 passed (3.14.8 venv); the lock unit names its holder
SCOPE: out — tests/unit/test_agentio_state.py, tests/unit/test_snapshot_slice1.py (2 of 5 changed files) (task has FLAGGED: yes)

### T022: import of slice-0 stores (FR-30)
**Started:** 2026-10-10T05:34:14Z (T021's commit time, from git; a composed time was written here first and corrected) | **Completed:** 2026-10-10T05:35:12Z

INHERITED: Store in the state root, NOTES/finish — from T021 (confidence: high)
FLAGGED: import runs on any use (take, list, undo) and under the store's lock, re-scanning under the lock so two processes never import twice; chose import over leaving or ignoring (D-14) (confidence: high)
ASSUMED: every session directory under the scratch root this user can read is in scope; another user's are unreadable and skipped (confidence: high)
ASSUMED: a record that fails verification is named once and not retried: the old store is marked imported either way, and stays in place for a person to read (confidence: medium)
ABSENT: deleting the old stores (the scratch is disposable, and nothing a user took is removed by timelike)
Verification: 3 new units (in order and restorable; ids after an import; a damaged record named, not imported)
SCOPE: out — tests/unit/test_snapshot_slice1.py (1 of 2 changed files) (task has FLAGGED: yes)

### T023: the stat cache (FR-35)
**Started:** 2026-10-10T05:35:48Z | **Completed:** 2026-10-10T05:36:32Z

INHERITED: the store and record layout — from T021 (confidence: high)
FLAGGED: a file is trusted unchanged when size, mtime_ns, ctime_ns and inode all match the last take and its object is still stored, chose that over content hashing every file (slice 0) because P2 bounds the scheduled snapshot; ctime cannot be set back by an unprivileged writer, so a rewrite always misses the cache (confidence: high)
ASSUMED: a write landing in the same nanosecond as the cached stat is not a case to design for (git's "racily clean" case is about second-granular mtimes) (confidence: medium)
ASSUMED: verification still re-hashes every object the record names (stack note 12 as written; Item 22 asks the mentor whether to narrow it) (confidence: high)
ABSENT: caching directories or links (they are read from the walk, never from content)
Measured (host, 3.14.8, take of an unchanged workspace, ms; first figure = first take into an empty state root):
- this repository's tree (464 files, 6.7 MB): 545, then 164, 167, 176, 152 (slice 0: 270–320)
- synthetic (657 files, 51 MB): 1543, then 298, 318, 295, 328 (slice 0: 620–700)
- what remains is the interpreter and agentio (about 100 ms, `snapshot list` alone), the walk, and verification re-reading every stored object (the larger share at 51 MB)
Verification: 2 units (an unchanged file is not opened, per an audit hook; a changed one is, and is what a restore brings back; a cached file whose object is gone is read again)
SCOPE: out — tests/unit/test_snapshot_slice1.py (1 of 2 changed files) (task has FLAGGED: yes)

### T024: the scheduled snapshot — helper and the shell-start due check (FR-32–FR-34)
**Started:** 2026-10-10T05:37:19Z | **Completed:** 2026-10-10T05:43:10Z

INHERITED: Store, import, LockBusy, take_locked — from T021–T023 (confidence: high)
FLAGGED: the due check lives in 001's /etc/timelike/shell-env.bash, builtins only, forking once only when due; chose that file (already reached by bash -c, -lc and interactive shells) over a new sourced file, which would cost a file read on every shell start for nothing (confidence: high)
FLAGGED: the helper's stderr line reaches the shell's stderr through fd 3 (the block's original stderr), while everything else stays silent; chose that over a line on every snapshot because a scheduled one that is complete says nothing (FR-33) (confidence: high)
FLAGGED: default interval 300 s, from the measurements in research R11 (confidence: medium — the mentor may prefer another figure)
FLAGGED: not taken when the command line starts with `snapshot` or `undo`: a scheduled snapshot of the damaged state would become the newest and hide the one the agent needs (confidence: high)
ASSUMED: a bash the helper starts must never re-enter the hook: the helper runs with TIMELIKE_SNAPSHOT_SCHEDULING=1, and the block skips under it (confidence: high)
ABSENT: a stamp for a workspace path whose encoded name passes 255 bytes (no scheduled snapshot there; spec FR-32 says so); purge after a scheduled take (T025)
Measured: research R11 — not due +0.5 ms per shell start, no fork; due 120–300 ms on the two workspaces above
Verification: host test K1–K13 (57 of 57); test_scheduled_snapshot.py 5 passed (complete is silent and restores a directory a script removed; partial and refused say so in one line; a busy workspace is skipped; a bad interval is named)
**Process failures recorded:**
- The first run of the K cases used a bash fake helper, which inherited BASH_ENV, re-entered the hook and recursed until it was killed (about 3 minutes, a few hundred processes, in a temporary directory). That's why the re-entry guard exists, and K1 now counts exactly one call.
- Cleaning up after it, `pkill -f` on a pattern matched my own command line and killed that shell, which my own notes say never to do. Nothing else was affected; the test's trap removed its directory.
SCOPE: out — tests/unit/test_scheduled_snapshot.py (1 of 4 changed files) (task has FLAGGED: yes)

### T025: purge on write, by age then size (FR-36, FR-37)
**Started:** 2026-10-10T05:44:04Z | **Completed:** 2026-10-10T05:49:11Z

INHERITED: the store layout, NOTES, the lock — from T021–T024 (confidence: high)
FLAGGED: a snapshot's age is its record file's mtime (written once at take time; an imported record's is set to its own taken_at), chose that over parsing every record, whose entries can be tens of thousands of lines (confidence: high)
FLAGGED: TIMELIKE_STATE_MAX_BYTES counts the snapshot content of every workspace (their objects), not the trash, which has its own cap (FR-41); spec FR-36 and the contract say so, declared (confidence: high)
FLAGGED: the purge runs after a take (on demand, scheduled) and after a verified restore, never between undo's safety snapshot and its apply, so it can never remove the snapshot being restored (confidence: high)
ASSUMED: another workspace's store is purged only while its lock is free at that moment; a busy one is named and skipped (no wait, P2) (confidence: high)
ASSUMED: a store whose records cannot all be read is not swept (a record that cannot be read may name anything) (confidence: high)
ABSENT: a test of the time bound itself (TIMELIKE_PURGE_SECONDS is whole seconds and the host purges in milliseconds); the bound is in the loop, and the line it prints shares the "stopped" path the newest-only case exercises
Verification: 4 units (age; size with the newest kept and the stop named; another workspace purged when free, skipped and named when busy; a bad limit is a usage error before anything is written); all recover units 104 passed
**Process failure recorded:** an edit to undo's verification dropped its `if left:` guard, so every restore reported a failure; 16 units caught it before the commit.
SCOPE: out — tests/unit/test_snapshot_slice1.py (1 of 3 changed files) (task has FLAGGED: yes)

### T026: the trash — store, purge, `undo --trash`, and `guard trash-put` (FR-39–FR-41)
**Started:** 2026-10-10T05:49:39Z | **Completed:** 2026-10-10T05:51:47Z

INHERITED: Store's mechanics (objects, ids, atomic writes, the lock), NOTES, the record-mtime age rule — from T021–T025 (confidence: high)
FLAGGED: "moved to a trash" is met by copy-then-delete: the guard keeps the content, then the real command deletes, so its behaviour, output and exit code are unchanged (seam 4); a hard link would be instant but the state root is a volume, another filesystem, so it cannot (confidence: high)
FLAGGED: the trash is not per workspace — any path the agent deletes is kept, the criterion says "deleted files" (Item 22 Q3 asks the mentor to confirm) (confidence: medium)
FLAGGED: a put-back never overwrites: an existing path, or a missing parent, refuses the whole item, named (confidence: high)
ASSUMED: a file that would take the trash past its cap is named "not kept" by the guard's line, not silently dropped (T2) (confidence: high)
DEFERRED: what calls `guard trash-put` in the agent's shell — FOR-MENTOR Item 22 (Q1, Q3)
ABSENT: an e2e cell (T028); a restored item stays in the trash, so a second put-back is refused as "exists" (not removed on restore)
Verification: test_trash.py 5 passed (kept and put back verified by the test's walk, modes and links included; never overwrites; unknown id exit 3; purge by size and age, named; over the cap named); undo units unchanged (help within 40 lines)
SCOPE: out — tests/unit/test_trash.py (1 of 3 changed files) (task has FLAGGED: yes)

### T027: the image's state root and compose's named volume (FR-25, FR-26)
**Started:** 2026-10-10T05:51:57Z | **Completed:** 2026-10-10T05:53:16Z

INHERITED: TIMELIKE_STATE_ROOT and its default — from T020 (confidence: high)
FLAGGED: 004's e2e cell "nothing of Adele's is mounted into the agent: no mounts at all" now requires exactly one mount, the volume timelike-state at /var/lib/timelike; chose to change its assertion, declared in the cell and here, over leaving it to fail, because revision 11 asks for the volume and the send says it does not cross H1; the cell's intent (nothing of Adele's) is kept and still checked (confidence: high) — another feature's test, so it goes in changed_other_features
ASSUMED: the build's root-run steps must leave /var/lib/timelike empty (a root-owned VERSION would lock the agent out); checked in the announce RUN, as /tmp/timelike already is (confidence: high)
ABSENT: any change to the vanilla image (P6); a build (no Docker here: the Dockerfile parses, 58 instructions, 0 unknown, by BuildKit's parser through the PyPI dockerfile package)
Verification: test_state_root_image.py 6 passed; test_agent_runtimes.py unchanged (97 with it); the cell's regex checked in bash: matches the one volume, rejects a second mount
SCOPE: out — tests/e2e/adele-isolation-grant-file-and-extend-unreachable-from-agent.bats, tests/unit/test_state_root_image.py (2 of 4 changed files) (task has FLAGGED: yes)

### T028: e2e — SC-7, SC-8 (new session; recreate; persistence), SC-9, SC-10's restore and purge; slice 0's cells on per-test state roots
**Started:** 2026-10-10T05:53:22Z (T027's commit time, from git; 06:53:16Z was written here first, composed, and corrected) | **Completed:** 2026-10-10T05:57:59Z

INHERITED: the state root, the hook, the trash helper, the volume — from T020–T027 (confidence: high)
FLAGGED: the e2e harness (exec_in) runs every cell with TIMELIKE_SNAPSHOT_INTERVAL=off unless the cell sets it; chose that over leaving scheduled snapshots on in every feature's cells, because they shift snapshot ids in slice 0's cells and add up to 300 ms, and possibly a stderr line, to timed cells of features that don't test recovery. The scheduled snapshot's own cells set it, the default interval included. Stated in the cycle report as a gap: other features' cells don't run with it on (confidence: medium)
FLAGGED: per-test state roots live on the agent's state volume (/var/lib/timelike/e2e-*), so slice 0's cells see the configuration compose gives the agent (no not-persistent line) and are isolated from each other; the slice-0 files change only their setup, env and teardown (and the refusal file's "nothing stored" check also reads the state root) (confidence: high)
FLAGGED: SC-8's recreate is a throwaway container from the verified image on two FRESH named volumes (state root and /home/agent), removed and started again, never a simulation inside one container; the fresh state volume also shows the image's ownership reaching it (lore Q003) (confidence: high)
ASSUMED: python3 is on the agent's PATH (007 Cycle 4, D-12) for SC-7's script (confidence: high)
DEFERRED: SC-6 (the guards) and SC-10's feed — Item 22. The SC-10 file says in its header that it is partial
ABSENT: running any cell (no Docker here); a "command starting with undo takes none" cell (it could not set the shell's working directory without a leading cd, so it would have passed vacuously; host test K6/K7 covers the rule)
Verification: bats 1.14.0 --count parses all (new: 4, 4, 2, 4; slice 0's and the adele file unchanged: 10, 4, 16, 10, 4, 5); shellcheck clean over every changed shell file, the new ones added to Makefile's SHELLCHECK_FILES; host hook test 57 of 57
SCOPE: out — tests/e2e/helpers.bash (1 of 12 changed files) (task has FLAGGED: yes)

### T029: carried — symbols' index to the state root (Item 20); 001's rule 10 text
**Started:** 2026-10-10T05:58:20Z | **Completed:** 2026-10-10T05:59:59Z

INHERITED: agentio.state_root / ensure_state_root, the workspace key — from T020, T021 (confidence: high)
FLAGGED: the index moves to `<state root>/workspaces/<key>/symbols.json`, keyed with snapshot's 16 hex (was 12, in the session scratch), so one workspace has one directory in the state root; chose sharing the directory over a separate `cache/` tree (confidence: high)
FLAGGED: a state root that cannot be used leaves the answer standing and says "cache not saved (…)", as a save failure always did; chose that over failing `symbols` (confidence: high)
ASSUMED: 011's contract line `index` changes with it — another feature's contract, declared in its file and in changed_other_features (confidence: high)
ASSUMED: 001's output-contract § Session event gains a State root bullet (the send's carried item), declared in place (confidence: high)
ABSENT: the README's prose about the index and the scratch (T030); the symbols e2e cells need no change (each cell has its own workspace, so its own key)
Verification: test_symbols.py 56 passed (a second session finds the index warm; the index in the state root, rebuilt when removed); test_conform.py and test_announce.py unchanged (128 with symbols)
FOR-MENTOR Item 20 closed in the register.
SCOPE: out — .specswarm/features/011-code-intelligence/contracts/symbols-cli.md, FOR-MENTOR.md, tests/unit/test_symbols.py (3 of 5 changed files) (task has FLAGGED: yes)

### T030: README — the generated command reference only; prose and Status held (Item 22)
**Started:** 2026-10-10T06:00:11Z | **Completed:** 2026-10-10T06:00:53Z

INHERITED: the help of `undo` (--trash) and `symbols` (the index line) — from T026, T029 (confidence: high)
FLAGGED: regenerated ONLY the generated command reference (scripts/readme_reference.py --write: undo's --trash line and option, symbols' index line), and left every prose line and the Status untouched; chose that because the send says "If an Item 22 leaves a criterion unbuilt, leave README.md untouched and say why" while CLAUDE.md's standing README rule says the reference is regenerated in the same cycle as any help change, and test_readme_reference.py fails the lane otherwise. The generated block is the script's output, not a reading. **For the mentor:** if "untouched" includes the generated block, revert this one commit's README hunk and the unit fails until T032 (confidence: medium)
ABSENT, held for T032 after Item 22: the README status block (row 07, 18 of 38, the Status paragraph), and the snapshot/undo and scratch prose. That prose now says the store is in the session scratch, which this cycle made false; it is corrected with the block
Verification: readme_reference --check current, 13 tools; test_readme_reference.py 21 passed
SCOPE: in (2 changed files)

### T031: host lane, lint, the cycle report § Cycle 3
**Started:** 2026-10-10T06:01:04Z | **Completed:** 2026-10-10T06:09:00Z

INHERITED: everything from T020–T030 (confidence: high)
ASSUMED: ruff format's rewrites are layout only; the units ran after them (confidence: high)
FLAGGED: reconcile_mode `scoped`, not `full`: the guards criterion is not built (Item 22); an addendum corrects it if the ruling lets this cycle build them (confidence: high)
ABSENT: the Docker lane (the mentor's); the README status block and prose (Item 22); T032
Verification: make test-host exit 0 (1987 passed, 13 skipped; hook 57/57); ruff, mypy --strict, shellcheck clean; step 10 as the installed 2.44.0 blocks report it (unknown)
