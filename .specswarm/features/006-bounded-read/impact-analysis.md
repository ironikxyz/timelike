# Impact Analysis: Modification to Feature 006 (bounded read and search)

Append-only: one section per modify cycle. Cycle 1 was built by `/specswarm:specify` and needs none.

---

## Cycle 2 — `bridge/sends/05-rev1-20261004-183704.md` (prompt 05 revision 1, discovery revision 12; slice 1)

**Feature:** Bounded read and search (`view`, `search`). **Command:** `/specswarm:modify 006 --from-send
bridge/sends/05-rev1-20261004-183704.md --dispatch`, run on `modify/006-slice-1`. That branch was cut from
`modify/003-slice-1` at `4857215`, the batch's stack. specswarm **4.0.1-botbaubble.2.35.0** (`4ff8dcb`)
was loaded: the expanded command named that cache path. Dispatch batch `20261004-183704`, prompt 2 of 8.

### Provenance (modify Step 2)

The installed `provenance-inputs` and `provenance-row` blocks ran with `ARGUMENTS` as a variable:
- `FEATURE_NUM 006`, from the branch;
- `PROMPT_VIA from-send`;
- `OLD_SOURCE` = `NEW_SOURCE` = `plan/.discover/prompts/05-bounded-read.md`;
- `PROMPT_REV 1`, `AUDITED [1]`, `N 1`.

That is **row 4**: revision 1 is already audited, and Step 9 appends nothing. The slice-1 criteria were
in revision 1 from the start, marked *(slice 1)*. They are added work, not a superseded body.

### What this cycle changes

The send's slice-1 scope is three criteria (two automated, one Manual):
1. A directory overview of a repository with a 10,000-file dependency directory fits its default budget,
   collapses that directory to one line with counts, and names how to expand it.
2. The viewer's anchor mode shows a short, stable anchor per line, which changes when the line's content
   changes.
3. DEMO D14 (Manual): the Agent orients in an unfamiliar repository with one budgeted overview.

The send's seams:
1. **The budget** is rule 3's output cap, in lines: 200 by default, `--limit N`, and `--limit 0` lifts it.
   Each line is cut at `COLUMNS` (revision 12). This is a budget the contract already has.
2. **The anchor:** 6 lowercase hex characters of SHA-256 over the line's raw bytes, without its line
   ending. It goes in the column D-9 reserved. 06 slice 1 accepts `N:hhhhhh`.
3. **Carried from slice 0:**
   - the verdict's plural (`1 files`);
   - search speed in the image (measured by an e2e cell over a generated corpus);
   - a window ending at the file's end (an e2e cell, now not units only).

### Affected components

| Component | Impact | Notes |
|---|---|---|
| `tools/bin/view` | High | `view DIR` becomes the overview (amends FR-8's "a directory exits 2", declared); `--anchors`; the next and more commands keep `--anchors` |
| `tools/bin/search` | Low | The verdict's plurals (`1 file`, `1 match`). Its ignore functions are now also read by `view`, loaded from `view`'s own directory as `undo` loads `snapshot` (005 R8). No behaviour change |
| `contracts/view-search-cli.md`, `spec.md`, `research.md`, `data-model.md` | Low | Appended slice-1 sections, declared |
| `tests/unit/test_view.py`, `tests/unit/test_search.py` | Low | One expectation each, if any asserted the old directory refusal or the plural |
| `tests/e2e/` | Low | New files, one per criterion, plus one for the carried items. `view-range-context-missing-file-and-binary.bats` if a cell asserts the directory refusal |
| Other features | None | No other tool uses `view` or `search`. 08 (edit, later in this batch) is slice 0 and does not take anchors yet |

### Breaking changes: one, declared

`view DIR` exited 2 with a usage error suggesting `search` or `ls`. It now shows the overview and exits
0. Nothing depends on the refusal except a test, if one asserts it. Everything else is additive:
`--anchors`, JSON `anchors`, and the overview's JSON fields.

### Risk: low

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| A walk of a huge tree takes long | Low | Medium | Each collapsed directory is counted up to 100,000 entries and then reported as `100000+`. The walk never follows symlinks. A unit measures 10,000 files |
| The anchor collides | Very low (1 in 16.7 M per changed line) | Low | Documented. 06 verifies the anchor at its line number, so a collision needs the same line changed to a same-hash content |
| `view` breaks if `search` is not beside it | Low | Medium | A missing `search` is a structured error naming the path. The image installs both; the tests use the repository's `tools/bin` |

### Tech stack compliance

Compliant: stdlib only (`hashlib`, `os.scandir`). No new tool. ripgrep stays the stated fallback (D-8).
The image measurement below does not trigger it yet.
