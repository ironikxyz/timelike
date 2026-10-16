# Impact Analysis: Modification to Feature 004 (Adele & grants)

Append-only: one section per modify cycle. Cycles 1 and 2 were built by `/specswarm:specify` and its sequence,
and need none.

---

## Cycle 3 — `bridge/sends/12-rev2-20261016-091249.md` (prompt 12 revision 2, discovery revision 15; slice 1)

**Analysis date:** 2026-10-16 | **Command:** `/specswarm:modify 004 --from-send
bridge/sends/12-rev2-20261016-091249.md` on `modify/004-slice-1` (from `master` `ba3107b`), specswarm
**4.0.1-botbaubble.2.44.0** loaded (`~/.claude/plugins/cache/specswarm-marketplace/specswarm/4.0.1-botbaubble.2.44.0`).

### Provenance (modify Step 2)

Row 4: same `source_prompt`, `N = 2`, `prompt_revision 2`, `audited_against [2]`. Nothing new; Step 9 is
skipped. Added work on a body that stays true (spec § Slice 1). Not SUPERSEDED.

### Affected components

| Component | Feature | Change | Breaking |
|---|---|---|---|
| `adele/internal/ledger` | 004 | schema 2 (outcomes, columns), migration, reap queries, `live` excludes reaped | No: v1 files migrate on open |
| `adele/internal/reaper` (new) | 004 | the reaper | — |
| `adele/internal/broker` | 004 | `agent`, `host` on rows; `/v1/denials`; the stand-in client's list and delete | No: `agent` optional |
| `adele/cmd/adeled` | 004 | the reaper in serve; `reap`, `status`; help text | No |
| `adele/internal/standin`, `cmd/adele-standin` | 004 | faults; `delete` | No (test fixture) |
| `tools/bin/adele` | 004 | sends `agent`; `status [HOST]` with denials; help | No: `status` keeps its fields |
| `tools/agentio/agentio.py` | **001** | rule 14's stderr line for exit 4 in text mode; the declaration guard | No: stdout byte-identical; no tool declares the pair |
| 001 `contracts/output-contract.md` | **001** | one sentence (FR-39) | No |
| `tools/bin/journal` | **009** | reads `agent` from ledger rows | No: absent → as before |
| `bench/benchlib/categories.py` | **002** | none expected: the verdict text it matches is unchanged | — |
| `README.md` | — | Adele's section; Status/What only if both slice-1 Automated criteria are met | — |

**Confirm-protocol tools inherit the line** (FR-38): every tool with `confirm_protocol: true` (snapshot/undo,
services, package-guard and the rest). Their stdout does not change; e2e cells that read stderr under `--text`
on exit 4 are searched and updated in the same task (memory: grep e2e when output changes).

### Risks

| Risk | Mitigation |
|---|---|
| Deleting a new box that reuses an expired name | the same-box check (FR-26) |
| The serving reaper and `adeled reap` racing | the outcome written only while the row is unreaped, read in one transaction |
| Migration on the operator's live ledger | one transaction, row and id preserving; Go units over a v1 file |
| An e2e cell for a reap that measures the machine | no `assert_within` on reaps; waits on the ledger at `PLUMBING_TIMEOUT` |
| Stopping Adele or the stand-in under neighbours | those cells in one `serial` file |
| A cell that pins stderr text on exit 4 under `--text` | grep the e2e tree before the change lands |

**Proceed:** yes. The denial criterion's source waits on FOR-MENTOR Item 26.
