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
