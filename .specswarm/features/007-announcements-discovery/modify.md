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

# Cycle 4: discovery revision 14, the agent runtimes (send `bridge/sends/04-rev14-20261008-174220.md`)

**Status:** Active. **Created:** 2026-10-08. **Impact analysis:** `impact-analysis.md` § Cycle 4. **Spec:** § Slice 1, cycle 4.

## Modification summary

**What:** build SC-6 under plan's ruling.
- The agent image ships an agent Python (uv, its own prefix, no marker, its own `pip.conf`) and Node (the
  pinned Active LTS tarball, its own `npmrc`). Bare installs land in `~/.local`.
- The vanilla bench image carries the same binaries with stock behaviour.
- Record revision 14.

**Why:** G6, the largest measured failure class: command not found, then module not found and installs that do
not persist. P1. And Item 21, answered as Q1 (a), Q2 (ii) and Q3.

## Proposed changes

- **F006 · The runtimes** (FR-25 to FR-28).
- **F007 · The data and isolation** (FR-29).
- **F008 · Bench parity and the scan** (FR-30, FR-13 revised).
- **F009 · The SC-6 tests** (FR-31).
- **F010 · Corrections by declared copy:** FR-13, FR-15, FR-18, FR-19, SC-6, the `python3` item, D-11.
- **F011 · Provenance:** append 14, scoped, with its `audit-log.md` row.

## Backward compatibility

Additive. A missing `python3`, `pip`, `node` or `npm` now resolves instead of answering 127. Every other tool
behaves as before.

---

# Cycle 5: lane 007s1-a's fixes and discovery revision 15, the bundled-library rule (send `bridge/sends/04-rev14-20261008-201729.md`)

**Status:** Active. **Created:** 2026-10-08. **Impact analysis:** `impact-analysis.md` § Cycle 5. **Spec:** § Slice 1, cycle 5.

## Modification summary

**What:**
- Lane 007s1-a's four items, as ruled in `../bridge/feedback/04-20261008-193851-lane-007s1-a-three-cells-and-the-scan.md`
  (built before this send arrived, T034–T038): the direct-exec cell's stream, 001's C6 premise, the two no-fix
  baseline entries, pip-audit over `/opt/agent/python`, and npm 11.21.0 pinned by version and registry integrity.
- Revision 15: the three findings npm's bundled tree still carries become **bundled-class** baseline entries,
  each with its own 30-day review, and the gate gains a **release check** that voids them as soon as any stable
  npm inside the constraint ships the fix, and blocks when it cannot tell.
- The governance audit 14 → 15. Record 15 in `audited_against`.

**Why:** the lane failed on three cells and nine scan findings; plan's ruling at revision 15
(`../bridge/feedback/04-20261008-201205-fix-available-for-npm-bundled-libraries.md` § Resolution) defines "fix
available" for a library bundled inside a component as the component's release.

## Proposed changes

- **F012 · The lane fixes** (T034–T038): built.
- **F013 · Bundled-class baseline entries** (FR-32): three per image, in both the agent and vanilla baselines.
- **F014 · The release check** (FR-33): `evaluate.py releases` reads the component's released manifests on every
  scan; `report` lets a bundled-class entry through only on its answer; fails closed.
- **F015 · Its tests** (FR-34), with fixtures the tests write (cross-stack P005).
- **F016 · Governance 14 → 15**, and provenance: append 15, with its `audit-log.md` row.

## Backward compatibility

Additive to the gate. A baseline without bundled-class entries is judged exactly as before; the release-check step
records `none` for it. A bundled-class entry is stricter than an ordinary one: it passes only while its own review
date holds and the release check answers that no release ships the fix.
