# Decisions Log — Feature 008
> Generated at 2026-10-05T04:51:40+00:00
> Spec: .specswarm/features/008-edit/spec.md

## Decision Key

| Tag | Meaning |
|-----|---------|
| ASSUMED | Assumption made without explicit spec guidance (confidence: high/medium/low) |
| DEFERRED | Decision postponed — noted for later resolution |
| FLAGGED | Judgment call between alternatives — requires review |
| ABSENT | What was NOT done and why — forced reflection on gaps |
| INHERITED | Assumption carried forward from a prior task's output |

---

Run: `/specswarm:implement --dispatch`, specswarm 4.0.1-botbaubble.2.35.0 (`4ff8dcb`). Blocks are run from
the installed `commands/implement.md`, not from the expanded text: this expansion again replaced awk's
`$0` with the command's argument (`--dispatch`) in `scope-tally` and `decision-tally`.
Checklists: requirements.md 16/16 after its FR-12 item was ticked (decided by discovery revision 13).
Pause file path (step 1e): `<repo>/../bridge/dispatch/pause-008.md` (the checkout path quoted as `<repo>/`, P2).
Process slip, corrected before any further commit: this initialising commit was first made without the
deny-list gate and carried the absolute pause path (P2, line 21). It was amended locally (never pushed).
Every later commit goes through the gate in the commit helper.

### T001: agentio confirm_protocol (revision 13); undo declares it; manifest confirm_protocol and dry_run
**Started:** 2026-10-05T04:52:03Z | **Completed:** 2026-10-05T04:56:52Z

INHERITED: discovery revision 13's ruling, via code-track § Resume after pause-06 and spec FR-12; research R1 (confidence: high)
FLAGGED: `Tool(confirm_protocol=None)` with None meaning "the same as mutating" — chose a default that keeps rule 9 whole for every tool written before revision 13 over a default of False, which would have silently dropped `undo`'s confirmation had its declaration been missed (confidence: high)
FLAGGED: `--yes`, exit 4's "confirmation required" and `confirmation_required` in `envelopes()` now follow `confirm_protocol`, not `mutating` — a `--yes` that does nothing is refused as an unknown flag (exit 2), so the reflex the ruling warns about has nothing to land on (confidence: high)
FLAGGED: the manifest gains `dry_run`, equal to `destructive` (the parser adds `--dry-run` exactly then) — chose stating the ruling's own field over leaving a reader to infer it from `destructive` (confidence: medium)
ASSUMED: `confirm_required()` needs no new guard: `_emit_result` already refuses an envelope whose status is not in `tool.envelopes()` (internal error, exit 1), and `envelopes()` now follows `confirm_protocol` — a unit shows it (confidence: high)
ABSENT: the schema and conform changes — T002/T003; tasks.md's "confirm_required() raises" is met by that existing refusal rather than a raise inside it
Verification: 5 new units in tests/unit/test_agentio.py (default, edit's shape, the undeclared envelope, the ValueError, dry_run); test_agentio.py 72 passed; whole unit suite on the host 1315 passed; ruff, format, mypy clean
SCOPE: in (3 changed files)

### T002: timelike-conform C2 — the confirmation-scope checks (revision 13), each shown failing
**Started:** 2026-10-05T04:57:40Z | **Completed:** 2026-10-05T04:59:28Z

INHERITED: `confirm_protocol` and `dry_run` in the manifest, absent meaning `mutating` and "--dry-run in flags" — from T001 (confidence: high)
FLAGGED: the checks live in C2 (the manifest), not in a new C10 — they are properties of the manifest, beside the flags and envelopes checks that already were there; C9 still checks every exit-4 output, and `declared_envelopes` now defaults by `confirms()` (confidence: high)
FLAGGED: every mutating tool that does not confirm must declare `dry_run: true` with `--dry-run` — the ruling binds "when it overwrites or removes", and a manifest cannot say which; a tool that only creates declares mutating false (snapshot's shape) (confidence: medium)
FLAGGED: `--yes` offered by a tool that does not confirm is a C2 failure — chose refusing it over tolerating it, so a `--yes` never appears where it would do nothing (confidence: high)
ABSENT: a separate C-number and its catalogue entries (C2 keeps its rule list "5, 6"; the C2 finding names rule 8 and revision 13 in its text)
Verification: 7 new cases in tests/unit/test_conform_violations.py (edit's shape passes; no dry run, --yes without confirming, confirm without mutating, dry_run disagreeing with the flags, an envelope from a non-confirming tool, a non-boolean — each C2 and only C2); test_conform.py and test_conform_violations.py 63 passed; ruff, format, mypy clean
SCOPE: in (2 changed files)

### T003: 001's contracts — schema (confirm_protocol, dry_run), output contract § Confirmation (revision 13), conformance C2
**Started:** 2026-10-05T04:59:56Z | **Completed:** 2026-10-05T05:00:31Z

INHERITED: the manifest fields and their "absent means" defaults — from T001; C2's five checks — from T002 (confidence: high)
FLAGGED: both new schema properties are optional, with "absent means" in their descriptions — chose that over required, following `envelopes` (revision 10), so a manifest printed before revision 13 still validates (confidence: high)
FLAGGED: `conformance.md`'s C2 row also changes (not named in tasks.md's T003, which lists the schema and output-contract.md) — its text described the old "--yes if mutating" rule and would have been false after T002 (confidence: high)
ASSUMED: 001's spec.md is not modified: it is UNAUDITED at 11–13 with no criterion changed, and routing it is the mentor's (research R1) (confidence: high)
ABSENT: a change to `confirm-envelope.schema.json` — the envelope itself is unchanged; only which tools may print it
Verification: the schema parses as JSON; test_agentio.py (which validates manifests against it, the new edit-shaped one included) 72 passed. Host conformance over all 8 shipped tools (installed with the venv interpreter, scratchpad conform-all.sh): pass — undo with confirm_protocol true, the others false
SCOPE: in (3 changed files)
