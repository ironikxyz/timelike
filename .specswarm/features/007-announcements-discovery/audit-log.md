# Audit log — Feature 007

> Append-only. One row per cycle that changed `audited_against` or decided not to. `/mentor:status` reads
> `audited_against` itself; this log says how each entry was established, for when one is disputed.

| When | Command | Mode | Appended | Basis |
|---|---|---|---|---|
| 2026-10-04T19:47Z (written 2026-10-08T10:11Z) | specify --from-send `04-rev1-20261004-183704` | seed | 1 | body generated from prompt revision 1 (the spec's `created_at`); recorded now, when this log is created |
| 2026-10-08T10:11Z | modify | scoped | 13 | send `04-rev13-20261008-095251` (prompt revision 13), computed with the installed `audit-append` block (MODE=scoped, OUT_OF_SCOPE empty, UNVERIFIED=13, REMOVALS_VISIBLE=yes → APPENDED 13). **What revision 13 changed:** it struck one clause of the slice-0 criterion, "and in the workspace's agent context file when none exists" (user level only); nothing else in prompt 04 moved (the prompt bodies of `04-rev1-20261004-183704` and this send differ by that strike and the revision note). **Amended (struck clause), corrected in place**, toward what was built: the body's quotation and account of the old criterion were false, the design was not. **Body lines compared:** `spec.md:113–116` (FR-7's "narrows the criterion" note), `:161–163` (SC-1's quotation), `:170–171` (SC-1's note), `:200–210` (D-1), `:232` (Out of scope) — all corrected by declared copy (T010, T011), not regenerated; numbers before T010. **Why scoped:** revision 13 rewords a criterion, so `full` lists it as unverified and would append 2–12 and not 13 (verified); this cycle addresses revision 13's own change and no more. Revisions 2–12 did not change prompt 04, which was generated at discovery revision 12 |
