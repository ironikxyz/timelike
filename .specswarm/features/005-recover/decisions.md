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
