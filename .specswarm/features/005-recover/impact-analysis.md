# Impact Analysis: Modification to Feature 005 (recover)

Append-only: one section per modify cycle. Cycle 1 was built by `/specswarm:specify` and needs none.

---

## Cycle 2 — `bridge/sends/07-rev11-20261004-030207.md` (prompt 07 revision 11, discovery revision 11)

**Feature:** Recover — snapshots and undo (slice 0) | **Analysis date:** 2026-10-04 |
**Command:** `/specswarm:modify 005 --from-send bridge/sends/07-rev11-20261004-030207.md` on
`005-recover`, specswarm 2.32.0 (`19829a6`) loaded. The feature number came from the standalone `005`
argument (the branch is not `modify/NNN`, and the provenance-inputs block resolved `005-recover`).
The branch stays `005-recover`, as the send asks.

### Provenance (modify Step 2)

Row 7: the source is the same prompt (`plan/.discover/prompts/07-recover.md`), `N = 11`,
`prompt_revision 1`, `audited_against [1]`. Revisions 2 to 10 did not change prompt 07 (the rev-1 send
was at prompt revision 1 and discovery revision 10). Revision 11 is classified by diffing the prompt
copy in `bridge/sends/07-rev1-20261003-013915.md` against this send's:

| Revision | What it did | Finding |
|---|---|---|
| 11 | **Added** one constraint (recovery state per workspace, in rule 10's state root) | Needs no body change for slice 0: the slice-0 part ("outside the workspace") holds as built. Recorded, declared (spec § Revision 11) |
| 11 | **Added** two criteria, both *(slice 1)* | Out of slice 0. Carried in the spec, not built (the send: "do not build them") |
| 11 | Removed or reworded nothing | Removals are visible (the diff above), and none occurred |

Not SUPERSEDED: nothing the body says became false.

### What else this cycle changes, and why (the send, not the revision)

Plan's four conditions on the store (resolution Q1, `stack.md` note 12) were checked against
`005-recover` at `f83e984`:

| # | Condition | As built | Change |
|---|---|---|---|
| 1 | Blobs deduplicated by content across snapshots | `Store.put` stores by sha256 and drops the copy when the object exists | None. Evidence: units |
| 2 | Symlinks stored as links, never followed | `walk` records `os.readlink`; `_restore` writes `os.symlink`; nothing is followed | None. Evidence: units |
| 3 | The size cap counts stored bytes after deduplication | **Not met.** The cap summed every candidate's plain size (`take_locked`, `total = sum(...)`), so content already stored, or repeated, counted again | Built: the cap counts bytes new to the store |
| 4 | "Taken" only after a restorability check | **Not met.** The verdict followed the record write | Built: the record is read back and every object re-hashed before "taken" |

### Affected components

| Component | Impact | Notes |
|---|---|---|
| `tools/bin/snapshot` (`Store.put`, `take_locked`, `raise_lines`, `cmd_take`, `_undo`) | Medium | Behaviour change only over the size cap, and on a verification failure |
| `tools/bin/undo` | None | Loads `snapshot`; the safety snapshot is verified through `take_locked` |
| `contracts/recover-cli.md`, `data-model.md`, `spec.md` FR-6 and FR-9, README | Low | Declared amendments |
| `tests/unit/test_snapshot.py`, `test_undo.py`, the SC-4 e2e file | Low | One unit and one e2e expectation change with the cap's meaning; 6 new units |
| Other features | None | Nothing else uses the store |

### Breaking changes: no

The verdict lines are unchanged. JSON gains `stored_bytes` and `verified` (additions). Over the size cap,
a snapshot of content that is already stored now captures more than before (it is less partial),
and the raise value names the content new to the store. A verification failure is a new outcome (exit 1),
inside the manifest's existing exit codes. No record migration: `v` stays 1, and older records lack the
new fields, which no reader requires.

### Risk: low

| Risk | Mitigation |
|---|---|
| The cap pass hashes files twice | Only when the plain sizes exceed the cap. Under it, nothing is hashed twice |
| Verification re-reads every object a snapshot names (one read of its distinct content) | Bounded by the workspace's distinct content. Measured in the host lane; stated in the cycle report |
| A file changes between the cap pass and the copy | Assumption 4 (recorded as read). `stored_bytes` reports what was actually added |

**Tech stack compliance:** stdlib only (`hashlib`, `os`, `stat`, `json`); no new technology.

**Proceed:** yes.
