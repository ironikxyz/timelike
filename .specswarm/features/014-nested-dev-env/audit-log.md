# Audit log — Feature 014

> Append-only. One row per cycle that changed `audited_against` or decided not to. `/mentor:status` reads
> `audited_against` itself; this log says how each entry was established, for when one is disputed.

| When | Command | Mode | Appended | Basis |
|---|---|---|---|---|
| 2026-10-17T04:04:44Z | modify | scoped | 17 | revision 17's only change to prompt 13 (the forbidden-settings criterion: exit 4 struck, exit 2 added) applied to spec.md FR-8, Scenario 2, criterion 3, D-1, D-7. SUPERSEDED by modify's table, corrected in place as the re-send declares (`bridge/sends/13-rev17-20261017-035606.md`: "do not regenerate"). Scoped, not full: no revisions between 8 and 17 changed prompt 13 (its `revision` moved 8 → 17), but the archived send at revision 8 is the only baseline diffed, which is enough for this prompt and was the whole check |
| 2026-10-18T12:17:01Z | modify | none | — | row 4: revision 17 is already listed and neither prompt 13 nor discovery moved since slice 0's send (`bridge/sends/13-rev17-20261018-120700.md`). Slice 1's criteria were in the prompt from generation, so the cycle brings them into scope (`slice: 1`) without a revision to reconcile; nothing appended |
