# Impact Analysis: Modification to Feature 007 — Announcements and discovery

> One section per modify cycle. Feature 007's first modify, so this file starts here.

# Cycle 2: revision 13 recorded; the workspace clause struck (send `bridge/sends/04-rev13-20261008-095251.md`, discovery revision 13)

**Analysis date:** 2026-10-08T10:09Z. specswarm **4.0.1-botbaubble.2.37.0** loaded (the expanded `PLUGIN_DIR`; the session's pid in
2.37.0's `.in_use`; lore specswarm Q002). Built on `modify/007-rev13` from `master` at `c79facc`.

**Provenance:** modify row 7, computed by the command's `provenance-inputs` and `provenance-row` blocks:
`source_prompt` agrees with the send's `> Source:` (`plan/.discover/prompts/04-announcements-discovery.md`); the
prompt is at revision 13, `prompt_revision` is 1, `audited_against` is `[1]`.

**What changed (lore P004: what was compared).** The prompt bodies of `04-rev1-20261004-183704.md` and this send,
diffed from `# Announcements and discovery` to the end, differ in two places only: revision 13's note is added, and
the slice-0 Automated criterion's clause *"and in the workspace's agent context file when none exists"* is **struck**
(kept visible, with "user level only; a committed workspace announcement would announce tools that exist only in
timelike"). No other criterion, constraint or line changed. Revisions 2–12 did not change prompt 04.

**Classification: one criterion reworded by a strike, toward what was built.** The body describes the feature
correctly (FR-5–FR-7, user level only, never inside the workspace; SC-1's cells assert the workspace stays untouched),
so the **design is not false and is not regenerated**. What is now false is the body's **quotation and account** of
the old criterion:

| Body line | What it says | Against revision 13 |
|---|---|---|
| `spec.md:113–116` FR-7 | "Never inside the workspace … *This narrows the criterion's 'and in the workspace's agent context file when none exists'*: see D-1 and FOR-MENTOR Item 19" | design true; the "narrows" note is now false (the criterion no longer asks for it) |
| `spec.md:161–163` SC-1 | quotes the criterion with the workspace clause, "copied exactly" | **false as a quote**: the clause is struck |
| `spec.md:170–171` | "The workspace part is not built (D-1). The test asserts the workspace is left untouched, so the narrowing is visible" | the build is right; there is no longer a narrowing, nothing to build |
| `spec.md:200–210` D-1 | the seam and the criterion "disagree"; FLAGGED, medium; raised as Item 19 "for plan to amend the criterion or overrule the seam" | **resolved**: plan amended the criterion (revision 13, Q3 option (b), plan `394c33e`). The reasoning is kept |
| `spec.md:232` Out of scope | "The workspace context file (D-1, raised)" | no longer raised: struck at revision 13 |

**Other artifacts, read and left as they are:** `decisions.md:65` (T003's FLAGGED cell sense, "the cells change if plan
amends the criterion"). Plan amended it in the direction already built, so the cells do not change, and the line stays
as written. `cycle-report.md:86–90` (Cycle 1's SC-1 citation) is append-only. `plan.md:38` ("no workspace write;
D-1") is true. FOR-MENTOR Item 19 has been **closed since 2026-10-05** (`FOR-MENTOR.md:858`), so nothing outside
this feature's directory changes.

**Code against revision 13:** the build placed the announcement at the user level only and never in the workspace
(FR-7), and SC-1's cells assert that the workspace stays untouched. Lane readme-c ran them at `10ddd3a`, a tree
identical to `master`'s, and they passed. **The code already matches. Nothing to build.**

**Proposed change:** the spec only. SC-1 quotes revision 13's criterion with the strike kept; FR-7's note, SC-1's note,
D-1 (resolution appended, reasoning kept) and Out of scope follow it. `audited_against` gains 13, and `audit-log.md` is
created. No code, test or contract change, so no Docker lane is needed.

**Breaking changes:** none. **Risk:** low; documentation only. **Proceed:** yes.
