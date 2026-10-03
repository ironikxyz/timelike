# Audit log — Feature 002

> Append-only. One row per cycle that changed `audited_against` or decided not to. `/mentor:status` reads
> `audited_against` itself; this log says how each entry was established, for when one is disputed.

| When | Command | Mode | Appended | Basis |
|---|---|---|---|---|
| 2026-09-29T00:10Z | specify --from-send `…-000641` | seed | 1 | body generated from prompt revision 1 |
| 2026-09-29T09:15Z | modify --from-send `…-080659` | none | — | modify row 4: revision 1 already in `audited_against [1]`; the send re-sends revision 1 with D2 findings, which changed the report's required content (FR-9 amended, FR-9a added), not the prompt's criteria |
