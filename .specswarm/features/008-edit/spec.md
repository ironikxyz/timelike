---
parent_branch: master
feature_number: "008"
status: In Progress
created_at: 2026-10-04T20:25:19+00:00
source_prompt: plan/.discover/prompts/06-edit.md
source_send: bridge/sends/06-rev1-20261004-183704.md
prompt_revision: 1
discovery_revision: 12
audited_against: [1]
slice: 0
---

# Feature: Edit (prompt 06, slice 0: skeletal)

## Overview

Agents change files through their harness's own edit tool, or, without one, through `sed -i` and scripted
rewrites. Most edit failures are match failures: CRLF line endings, tabs the agent sees as spaces,
text that occurs twice, a stale view (prompt 06; SWE-agent's edit+lint at 18.0% against 10.3%
bash-only). `edit` is the harness-independent write half of the loop (P1, P7):

- the agent names a file, the exact text to replace and the new text;
- the edit applies **only if the match is unique**, tolerating the line-ending and tab/space differences
  the agent cannot see, and it keeps the file's own line endings and indentation;
- a failed match says why: several matches with their line numbers, or none, with up to three nearest
  candidate regions;
- after a change it shows the edited region, numbered as `view` numbers lines;
- an edit never partially applies.

Slice 1 (not built here) accepts `view --anchors`'s `N:hhhhhh` and refuses edits that break a file's syntax.

**Rule 9 was not decided here, by instruction** (send seam 1): the choice was plan's, so this instance
wrote `../bridge/dispatch/pause-06.md` naming both readings. Plan answered with discovery revision 13:
`edit` is not confirmed (FR-12). Every seam in this spec is now decided.

## User Scenarios

### Actors
- **Agent** (primary): edits files from bash, through any harness.
- **Operator**: in the D6 demo, watches an agent edit a CRLF, tab-indented file.

### Scenario 1: a unique replacement (SC-1)
1. The agent runs `edit src/app.py --old 'return x' --new 'return x + 1'`.
2. The text occurs once. The file now has the new text and nothing else changed.
3. The output shows the edited region with line numbers, for example lines 40–46 with the changed line
   marked.

### Scenario 2: CRLF and tabs (SC-2, D6)
1. The file uses CRLF endings and tab indentation. The agent copies the text as it saw it, with LF endings
   and four spaces per level.
2. The edit applies. The new text is written with CRLF endings, and its indentation is translated to tabs
   at the same levels.

### Scenario 3: ambiguous, or missing (SC-3, SC-4)
1. The text occurs three times: exit 3, listing the three line numbers and how to make it unique (more
   context).
2. The text occurs nowhere: exit 3, showing up to three nearest candidate regions with line numbers, and
   saying what differed when that is detectable.

### Scenario 4: a dry run (SC-5)
`edit … --dry-run` prints the unified diff the edit would make and leaves the file byte-identical.

### Edge cases
- **A missing file:** exit 3, with `do instead:`. Creating a file is not `edit`'s job in slice 0, and the
  verdict says how to create one.
- **A binary file** (a NUL byte in the first 8 KiB, as `view` decides): refused (exit 1), unchanged.
- **Bytes that are not UTF-8:** kept byte for byte. Matching works on the decodable text around them.
- **A byte-order mark:** kept.
- **`--old` equal to `--new`:** nothing to do. Exit 0 with a verdict saying no change was made, and the
  file untouched.
- **An empty `--old`:** a usage error (exit 2). Inserting needs context to anchor on.
- **A file changed between the read and the write** (another process): the write is refused (exit 1), and
  nothing is written (the hash read before is compared before renaming).
- **Mode and owner** are kept. A file the agent cannot write is refused (exit 1) before anything happens.

## Functional Requirements

### Invocation
- **FR-1** `edit FILE --old TEXT --new TEXT [--dry-run]`. TEXT is passed as an argument. Rule 4 forbids
  reading stdin unless declared, and slice 0 declares none. Multi-line text is passed the way the agent's
  shell allows (`$'…'`, a quoted newline).
- **FR-2** **The name is `edit`**: the habit of every harness's edit tool (P3). A test checks that the
  image has no other `edit` on `PATH`. Debian's `mailcap` package installs `/usr/bin/edit`, and the image
  does not install it; the `type -a` cell decides.

### Matching
- **FR-3** **Levels, tried in order; the first level that finds any match decides:**
  1. **exact:** the bytes as given;
  2. **line endings:** `--old`'s LF matched against the file's CRLF (or CR);
  3. **indentation:** each line's leading whitespace compared by level, not by characters. One
     consistent mapping is required between the agent's indentation unit and the file's (four spaces ↔
     one tab, for example), and the rest of each line must be equal.

  Trailing whitespace is ignored at levels 2 and 3. The verdict names the level used (`matched exactly`,
  `matched ignoring line endings`, `matched ignoring line endings and indentation (4 spaces = 1 tab)`).
- **FR-4** **Unique or refused:** more than one match at the deciding level is exit 3, with every match's
  line number and `do instead:` (add lines of context to `--old`). Nothing is written.
- **FR-5** **No match:** exit 3, showing up to three **nearest candidate regions**: windows of the file the
  same length as `--old`, ranked by similarity, each numbered as `view` numbers lines (no window below a
  similarity floor of 0.5). Where detectable, it names the difference: line endings, indentation, or which
  line differs.

### Applying
- **FR-6** **The new text takes the file's conventions:** its line ending (CRLF if the matched region used
  CRLF), and its indentation, translated with the mapping the match used (level 3). Exact matches insert
  `--new` as given.
- **FR-7** **Atomic** (send seam 2, P2): the new content is written to a temporary file beside the target,
  flushed, given the target's mode (and owner, where the agent may set it), and renamed over the target.
  The file is either fully changed or byte-identical. A failure at any step leaves the target untouched,
  and the temporary file is removed.
- **FR-8** **Shown after:** the edited region with 3 lines of context each side, numbered and right-aligned
  as `view` prints them, changed lines marked. The verdict says which lines changed
  (`edited lines 42-43 of 120 (matched exactly)`). JSON carries `path`, `start`, `end`, `total`, `level`,
  `lines`, and the SHA-256 of the file before and after.

### Dry run
- **FR-9** `--dry-run` (rule 8) prints the unified diff (`--- a/FILE`, `+++ b/FILE`, 3 lines of context) and
  writes nothing. JSON carries `diff` (the lines) and the file's SHA-256, unchanged.

### Contract
- **FR-10** `edit` follows the output contract: header, verdict, `--json`, exit codes 0, 1, 2, 3 (never
  4: FR-12), and one session event per call.
- **FR-11** Outcomes are verdicts on stdout (as 005 and 006): no match, several matches, a missing file.
  Usage errors go to stderr.

### Rule 9 — decided by plan: not confirmed (discovery revision 13; pause-06 answered)
- **FR-12** `edit` is **not confirmed** under rule 9. It declares `mutating: true` and
  **`confirm_protocol: false`**: an edit applies in one call, never exits 4 with a confirmation envelope,
  and does not accept `--yes`. Rule 8 still binds it, since it overwrites: `--dry-run` (FR-9) is the look
  before.
  - **The ruling:** discovery **revision 13** (plan `394c33e`), a clarification, answer (b) to pause-06's
    question. Rule 9 binds a change whose scope the arguments do not name exactly, that touches another
    agent's or session's work, or that cannot be reversed from what the tool shows. A change to a target
    named exactly, applied whole or not at all, that shows what it changed, is not confirmed. `edit` is
    that case: the agent names the file and the text (FR-3, FR-4), the write is atomic (FR-7), and the
    after-view shows the edited region (FR-8).
  - **Where the answer is:** `../bridge/feedback/batch-20261004-232148-rule9-scope-and-workspace-context-file.md`
    § Resolution (Q1), delivered through `../bridge/dispatch/code-track.md` § Resume after pause-06. The
    question was `../bridge/dispatch/pause-06.md`, written by this instance at 2026-10-04T20:25:38Z and
    deleted by the mentor beside its answer.
  - **What this cycle also builds, outside 008 (code-track § Resume after pause-06):** 001's
    `agent-info.schema.json` gains `confirm_protocol` (restored, report 03 Appendix B); `agentio`
    honours `--yes` only when `confirm_protocol` is true; `timelike-conform` adds a check that
    `confirm_protocol: false` with an overwriting or removing tool requires `dry_run: true`; 001's
    output contract gains rule 9's clarifying sentence. `undo` (005) stays confirmed (its scope is
    "everything since"), so it declares `confirm_protocol: true`. All of it goes in the cycle report's
    `changed_other_features`.
  - **D6's "on the first attempt"** is the first call: no envelope comes between the agent and the edit.

## Success Criteria

The criterion text is the send's, copied exactly. Each automated criterion is one e2e file in the image,
under `bash -c` and `bash -lc`, with every byte-identical claim checked by a hash (send seam 2).

- **SC-1** "Replacing text that appears exactly once changes only that text and prints the edited region
  with line numbers". The file's SHA-256 differs from the original only by the replacement, which the test
  applies itself and compares.
- **SC-2** "Replacing text in a CRLF file whose indentation is tabs, given the text with LF endings and
  spaces, succeeds and preserves CRLF endings and tabs".
- **SC-3** "Text that matches more than once is refused with exit 3, listing each match's line number".
  The file's hash is unchanged.
- **SC-4** "Text that matches nowhere is refused with exit 3, showing up to three nearest candidate regions
  with line numbers". The hash is unchanged.
- **SC-5** "A dry run prints the unified diff and leaves the file byte-identical". The hash is unchanged,
  and the diff equals one the test computes itself.
- **SC-6** "DEMO: the Agent edits a CRLF, tab-indented file on the first attempt, and on a failed match is
  shown the nearest candidates" (D6). Manual, after the lane.

## Key Entities

- **Match:** the level, the region (start and end line) and, at level 3, the indentation mapping.
- **Candidate:** a region and its similarity, plus the detectable difference.
- **Edit result:** the region shown, and the hash before and after.

## Decisions

| Point | Decision |
|---|---|
| Rule 9 | **Not confirmed**: `mutating: true`, `confirm_protocol: false`; `--dry-run` binds (FR-12, revision 13) |
| Atomicity | Temp file beside, mode and owner kept, rename; hash-checked against a concurrent change (FR-7) |
| Tolerance | Three levels, first that matches decides; uniqueness at that level (FR-3, FR-4) |
| Candidates | Same-length windows by similarity, top 3, floor 0.5, with the difference named (FR-5) |
| Name | `edit` (FR-2), checked by `type -a` |
| Input | Flags, not stdin (rule 4) |

## Out of scope (slice 0)

Anchors, syntax checks (slice 1). Creating files. Several edits in one call.

## Assumptions

- Python's `difflib` is the similarity and diff engine (stdlib, H5).
- The image installs no other `edit` (verified by the `type -a` cell).
