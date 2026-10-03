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
