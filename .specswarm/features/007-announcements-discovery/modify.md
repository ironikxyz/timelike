# Modification: Feature 007 — Announcements and discovery

> One section per modify cycle. Feature 007's first modify, so this file starts here.

# Cycle 2: revision 13 recorded (send `bridge/sends/04-rev13-20261008-095251.md`)

**Status:** Active. **Created:** 2026-10-08. **Impact analysis:** `impact-analysis.md` § Cycle 2.

## Modification summary

**What:** record discovery revision 13 against 007's spec. The spec's quotation of SC-1 and its account of D-1 catch
up with the criterion as revised. No behaviour changes.

**Why:** revision 13 (plan `394c33e`, Q3 option (b) of
`bridge/feedback/batch-20261004-232148-rule9-scope-and-workspace-context-file.md`) struck the criterion's workspace
clause: user level only. That is what D-1 built. The body still quotes the old criterion and calls D-1 a raised
deviation.

## Proposed changes

- **F001 · SC-1's quotation.** Revision 13's criterion text, verbatim, with the struck clause kept struck and marked.
  SC-1's note becomes "struck at revision 13, nothing to build".
- **F002 · D-1 resolved.** D-1's reasoning is kept as written. The resolution is appended: *resolved by discovery
  revision 13 (Q3, option (b)), plan `394c33e`. The FLAGGED decision is now the rule, not a deviation from it.*
- **F003 · FR-7 and Out of scope follow.** FR-7's "narrows the criterion" note and Out of scope's "(D-1, raised)" say
  that the clause is struck at revision 13.

## Contract and code changes

None.

# Cycle 3: slice 1 (send `bridge/sends/04-rev13-20261008-161802.md`)

**Status:** Active. **Created:** 2026-10-08. **Impact analysis:** `impact-analysis.md` § Cycle 3. **Spec:** § Slice 1.

## Modification summary

**What:** build prompt 04's slice-1 criteria:
- a missing command answers with the way to get it;
- unprivileged package installs (**held on FOR-MENTOR Item 21**);
- one command for the resource budget.

**Why:** P1 ("a missing command becomes a next step instead of a dead end"; command not found is the largest measured
failure class, 24.1% in Terminal-Bench 2.0) and P2 (the budget names the limits a call can hit).

## Proposed changes

- **F001 · The command-not-found answer** (FR-14–FR-17): `command_not_found_handle` in the hook, and the TSV data. Not
  breaking: the first line is bash's own.
- **F002 · `timelike budget`** (FR-20–FR-23), on readers moved into agentio (FR-21). Additive.
- **F003 · The announcement's two rule lines** (FR-24).
- **F004 · Carried:** SC-1's cell names, and the bound changed to an ordering (declared).
- **F005 · Installs (FR-18, FR-19): held.** Nothing is built until Item 21 is answered.

## Backward compatibility

Additive, with no breaking change. A missing command still exits 127, with bash's own line first. `run` and
`snapshot` behave as before, and their suites run unchanged.
