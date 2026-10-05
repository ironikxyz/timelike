# Decisions Log — Feature 009
> Generated at 2026-10-05T06:08:02+00:00
> Spec: .specswarm/features/009-session-journal/spec.md

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
the installed `commands/implement.md` (the expansion again replaces awk's `$0` with `--dispatch`), with
`CLAUDE_PLUGIN_ROOT` set to the cache path. Checklists: requirements.md 16/16.
Pause file path (step 1e): `<repo>/../bridge/dispatch/pause-009.md` (the checkout path quoted as `<repo>/`, P2).

### T001: agentio's event gains agent, ppid, t_ms and ref (Tool.event_ref); run, snapshot and undo declare their pointers; 001's event schema and contract
**Started:** 2026-10-05T06:08:50Z | **Completed:** 2026-10-05T06:13:58Z

INHERITED: none — first task of this feature; the plan's R2 and the data-model's tool event (confidence: high)
FLAGGED: `t_ms` beside `ts`, not a millisecond `ts` — 001's tests and conform C7 read `ts`; a second field changes nothing that already reads the first (confidence: high)
FLAGGED: `ref` comes from the result's own data by a key the tool declares (`Tool(event_ref=(kind, key))`) — the pointer is what the tool reported; no second derivation that could disagree. A tool that failed (ToolError) has no result and so no `ref` (confidence: high)
FLAGGED: the schema's `ref` lists `log` (string) and `snapshot` (integer) with additionalProperties false — the repo's test schema checker (tests/unit/schema.py) supports neither type lists nor min/maxProperties, so "exactly one key" is stated in the description and enforced by agentio's construction, not by the schema (confidence: medium)
ASSUMED: `agent` is written only when TIMELIKE_AGENT matches the session id's character set; an invalid value is dropped silently rather than refused — a tool must not fail on a journal label (confidence: high)
ABSENT: an `agent` on other records (Adele's ledger, 004) — the ledger is read, never written (seam 3)
Verification: 3 new units in tests/unit/test_agentio.py (fields and agent validity, ref from data for str/int and absent for None/""/True/a failure, old lines valid and a foreign ref key invalid); the whole unit suite 1409 passed; ruff, format, mypy clean; host conformance over all 9 tools: pass
SCOPE: in (6 changed files)
