# Audit log — Feature 004

> Append-only. One row per cycle that changed `audited_against` or decided not to. `/mentor:status` reads
> `audited_against` itself; this log says how each entry was established, for when one is disputed.

| When | Command | Mode | Appended | Basis |
|---|---|---|---|---|
| 2026-10-16T10:36:08Z | modify | scoped | 16 | revision 16 **amended** the slice-1 criterion this cycle's § Slice 1 described (struck and split: status over Adele's refusals stays in slice 1, the denied-connection message moves to slice 2); § Slice 1 corrected in place, declared, as send `bridge/sends/12-rev16-20261016-102708.md` directs, and the code checked against the new criterion. Removals visible: the rev-2 and rev-16 sends diffed (one criterion struck, one slice-1 and one slice-2 added, the Feature text). Revisions 3 to 15 did not change prompt 12 (it stayed at revision 2), so nothing of theirs is claimed |
