# Modification: Feature 014 — nested dev environments (declared by the re-send)

**Status:** Active · **Created:** 2026-10-17T04:04:44Z (read from the clock) · **Send:** `bridge/sends/13-rev17-20261017-035606.md`
(prompt revision 17, discovery revision 17) · **Original spec:** `spec.md`, written from
`bridge/sends/13-rev8-20261017-012727.md` (prompt revision 8) · **Impact analysis:** `impact-analysis.md`

## Why this cycle corrects in place

Revision 17 **amended** one slice-0 criterion. The forbidden-settings refusal was exit 4 naming the setting; it is
now exit 2 with rule 14's error, naming the setting and stating that no grant allows it, with no operator's
command. By modify's own table that is SUPERSEDED, which would mean regenerating the body. **The re-send declares
otherwise:** "Correct it in place with this modify cycle, declared … Do not regenerate." Only the spec existed when
it was written (plus, since then, plan and tasks, which this cycle updates), so nothing built rests on the false
sentence. The correction follows the re-send.

## Changes

- **F001, the forbidden-settings criterion and FR-8:** exit 4 with a grant envelope becomes exit 2 with rule 14's
  error, with no envelope on stdout and no operator's command. The struck criterion stays visible, struck, beside
  its replacement.
- **F002, the seams:** each proposed decision becomes decided, citing
  `../bridge/feedback/13-20261017-034920-item-27-seams-answered.md` (done before the re-send arrived; checked
  against it).
- **F003, a missing image:** the re-send asks for plan's test. It fails three of the four fields, so FOR-MENTOR
  Item 29 is raised, and exit 3 is built provisionally.
- **Provenance:** revision 17 is appended to `audited_against` (scoped: revision 17's change, the only change to
  prompt 13 since revision 8). `prompt_revision` stays 8.

**Breaking changes:** none to any built feature. Nothing past the spec existed when revision 17 landed.
