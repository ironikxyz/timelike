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

---

## Cycle 4 — `bridge/sends/12-rev16-20261016-102708.md` (prompt 12 revision 16, discovery revision 16; slice 1, re-sent)

**Command:** `/specswarm:modify 004 --from-send bridge/sends/12-rev16-20261016-102708.md` on `modify/004-slice-1`,
continuing Cycle 3's work (nothing withdrawn), specswarm 4.0.1-botbaubble.2.44.0.

### Provenance (modify Step 2)

Row 7: same `source_prompt`, `N = 16`, `prompt_revision 2`, `audited_against [2]`. Classified by diffing the rev-2 send
(`bridge/sends/12-rev2-20261016-091249.md`) against this one:

| Revision | What it did | Finding |
|---|---|---|
| 3 to 15 | Nothing in prompt 12 (it stayed at revision 2 through them) | Not claimed |
| 16 | **Struck** the slice-1 criterion "A denied outbound connection returns a plain message …"; **added** a slice-1 criterion (a status command over Adele's refusals, naming where the record lives) and a slice-2 one (the denied-connection message); adjusted the Feature text | **Amended** what § Slice 1 (written in Cycle 3) described — SUPERSEDED in the skill's word, for that section only. Slice 0's body stays true |

**Not regenerated, on the send's instruction.** The skill says to stop and regenerate on a superseded body; the
send says to correct in place via modify, declared, because the correction makes the spec ask for less and the only
false text is this cycle's own slice-1 section. § Slice 1 is corrected in place with a declaration at its head.

### Affected components (delta)

| Component | Change |
|---|---|
| `spec.md` § Slice 1 | the criterion, FR-35 to FR-37, SC-8 (declared, *(revision 16)*); `audited_against` gains 16 (`audit-log.md`) |
| `tests/e2e/…status…bats` | renamed after SC-8's new text; the exit-4 line's cell moved to its own file (Item 14 (b)) |
| `.specswarm/{constitution,tech-stack,quality-standards}.md` | the governance audit 15 → 16 (`bridge/governance-context.md`) |
| `README.md` | the send's status block (both live slice-1 Automated criteria now built), Adele's section |
| `FOR-MENTOR.md` | Item 26 closed |

No code change: the status command, its record and the reaper are what revision 16's slice 1 asks for.
