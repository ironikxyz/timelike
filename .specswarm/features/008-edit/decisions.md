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
