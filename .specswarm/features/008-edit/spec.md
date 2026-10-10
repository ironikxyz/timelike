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

---

## Slice 1 (Cycle 2, send `bridge/sends/06-rev1-20261009-102433.md`; natural)

Built by `/specswarm:modify 008` on `modify/008-slice-1`, cut from `master` `ce1eaf2`. Prompt 06 is still at
revision 1, and `audited_against [1]` is current (modify row 4). The slice-1 criteria were in revision 1
from the start, so this is **added work** on a body that stays true. FR-1's invocation gains two flags
(FR-13, FR-25), declared. The exit codes stay 0, 1, 2 and 3 (FR-10). The `Out of scope (slice 0)` list
above is history. The reasoning for each decision is in `research.md` R9 to R15.

### Scenarios

**Scenario 5: an edit addressed by anchors.**
1. The agent runs `view --anchors src/app.py:40-48` and sees ` 42 a3f9c1 return x` … ` 48 0b11e2 }`.
2. It runs `edit src/app.py --at 42:a3f9c1..48:0b11e2 --new $'…'`. Both anchored lines are unchanged, so
   lines 42–48 are replaced, and the edited region is shown as in FR-8.
3. If line 42 changed in the meantime, the edit exits 3 with
   `line 42 changed (anchor a3f9c1, now 7d01be)`. It shows lines 39–51 as they are now, with their anchors,
   so the next call can use them.

**Scenario 6: a line that moved.** Three lines were inserted above line 42, so its bytes are now line 45.
The edit exits 3, naming the move (`lines 42-48 are now lines 45-51`). `do instead:` gives the exact
`--at 45:a3f9c1..51:0b11e2` to rerun with.

**Scenario 7: an edit that would break the syntax (D15).**
1. The agent replaces `def f(x):` with `def f(x)` in a clean Python file.
2. Exit 1:
   `refused: the edit would make app.py fail its syntax check (python 3.14.8 compile): line 12, column 9: expected ':'; nothing written`.
3. The lines around line 12 of the would-be result are shown numbered, with the error line marked. The
   file's SHA-256 is unchanged.

**Scenario 8: a file that was already broken.** The agent is midway through a repair: the file fails its
check before the edit. An edit that adds no new error in the lines it writes applies, and the verdict
says the file still fails, and where. An edit that adds a new error in the lines it writes is refused.

### Functional requirements

**Anchors** (send seam 7)
- **FR-13** `edit FILE --at N:hhhhhh --new TEXT` replaces line N whole. `--at A:aaaaaa..B:bbbbbb`
  replaces lines A to B inclusive (A ≤ B). The form is 006 FR-34's.
  - `--at` with `--old` is a usage error (exit 2): one way of addressing per call.
  - `--at` without `--new` is a usage error.
  - A malformed `--at` is a usage error naming the form.
- **FR-14** **One definition.** The anchor is `view`'s own `anchor_of` (006 FR-33), over lines as `view`
  splits them (`line_body`, factored out of `view`'s window). Both are loaded from the `view` beside
  `edit`, as `edit` already loads `view`'s `file_type`. Nothing is copied.
- **FR-15** **Unchanged** means each anchored end, read at its line number now, has the anchor given.
  The interior lines of a range are not checked, because the form carries the ends only. The verdict
  says which lines were checked (`anchors checked at lines 42 and 48`).
- **FR-16** **Stale** means an anchored line is missing or has another anchor. Exit 3, scope
  `anchors stale`, nothing written.
  - The verdict names each changed line: `line 42 changed (anchor a3f9c1, now 7d01be)`, or
    `line 42 is past the end (120 lines)`.
  - **A pure move:** both ends' bytes are found at the same offset elsewhere, and the range between them
    is still a range (`lines 42-48 are now lines 45-51`). This is **refused, naming where they moved**,
    with `do instead:` the exact `--at` that would apply it. The agent's `--new` was written against a
    view that is now stale (P2's verdict names the cause; R11).
  - Otherwise `do instead:` is `view --anchors FILE:A-B`, then rerun with the anchors it shows.
  - The current lines A−3 to B+3 are printed as `view --anchors` prints them (` 42>7d01be text`, with
    `>` on the anchored ends). JSON carries `anchors_now: ["N:hhhhhh", …]` for those lines,
    `changed: [{line, expected, now}]` and, on a move, `moved_to: {start, end}`.
- **FR-17** **The replacement:**
  - `--new`'s line endings become the region's (the ending of its first line, as at level 2), and one
    trailing newline in `--new` is dropped, since the region keeps its last line's ending;
  - an empty `--new` deletes the lines, endings included;
  - indentation is taken as given (the agent saw the lines it is replacing);
  - shown after as in FR-8. The verdict says `(addressed by anchors)`; JSON `level: "anchors"` and
    `anchors: {"start": "A:aaaaaa", "end": "B:bbbbbb"}`.

**The syntax check** (send seams 1 to 6)
- **FR-18** **Language** (seam 4):
  - by extension first: `.py` and `.pyi` are Python; `.ts`, `.mts` and `.cts` are TypeScript; `.tsx` is
    TSX (TypeScript with JSX, its own grammar); `.go` is Go; `.rs` is Rust; `.sh` and `.bash` are shell;
  - an extensionless file is identified by its shebang (`python`, `python3`, `python3.N`, `bash`, `sh`;
    directly or through `/usr/bin/env`);
  - anything else is **unknown**: the edit applies, the verdict says
    `syntax: not checked (language unknown)`, and JSON says the same
    (`syntax.status "not checked"`, `syntax.reason "language unknown"`).
- **FR-19** **Checkers** (seam 1), all timelike's own and never the agent's runtime:
  - **Python:** timelike's interpreter's own compiler (`compile(…, "exec", ast.PyCF_ONLY_AST)`, which
    parses and never runs), CPython at the version `pins.env` pins as `PYTHON_VERSION`, the same as the agent's;
  - **shell:** `/bin/bash -n` (bash's own parser, which reads and never runs), with no startup files and
    no `BASH_ENV`;
  - **TypeScript, TSX, Go, Rust:** tree-sitter, through its Python binding and prebuilt grammar wheels
    pinned by hash in `pins.env` and installed into timelike's interpreter. A parse whose tree holds an
    `ERROR` or `MISSING` node is a syntax error at that node's position.

  The check runs in a **child process**: `libexec/syntax-check`, resolved from `edit`'s own real path and
  run by `edit`'s own interpreter with `-I`. Nothing is resolved from `PATH`, the agent's `PYTHONPATH` or
  `~/.local` (lore P002).
- **FR-20** The check runs on **the bytes that would be written**, with their line endings and encoding.
  The result is checked first; the original is checked only when the result fails (FR-21).
- **FR-21** **What refuses** (seam 3):
  - if the original passes its check and the result fails, the edit is **refused**;
  - if the original already fails, the edit is **refused only when the result has an error inside the
    lines it writes that the original does not have**. An error's identity is its message plus the text
    of its line, so a shifted line is the same error. Otherwise the edit applies, and the verdict says
    `syntax: FILE already failed its check before this edit (line N: message); no new error in lines S-E`.
- **FR-22** **The refusal** (seam: "with the checker's error"):
  - exit 1, scope `refused`;
  - the verdict is `refused: the edit would make FILE fail its syntax check (CHECKER): line L, column C:
    MESSAGE; nothing written`;
  - the lines show up to 3 errors, each with the would-be result's lines L−2 to L+2, numbered and with
    the error line marked, bounded by rule 3;
  - `do instead:` is to correct `--new` and rerun, with `--dry-run` to see the diff first. **It never
    suggests skipping the check** (T4);
  - JSON carries `syntax: {status: "refused", language, checker, errors: [{line, column, message}]}`;
  - the file is byte-identical.
- **FR-23** **`--dry-run`** with a syntax error prints the diff and then the errors, exits 1 as the real edit
  would, and writes nothing.
- **FR-24** **The checker's own failure** (seam 5): a checker that is missing, crashes, has no grammar, or
  exceeds its **10 s** limit does not stop the edit.
  - The child is killed at the limit, and the call concludes.
  - The edit applies, and the verdict says `syntax: not checked (checker failed: REASON)`.
  - **Fail open**, because a check that cannot run says nothing about the file. Refusing would block the
    agent's work on timelike's fault, not the file's (P2: the checker's failure is not the file's).
  - The file is still written whole or not at all (FR-7).
- **FR-25** **The skip** (seam 6): `--skip-syntax-check`, in the agent's own command.
  - The verdict says `syntax: skipped (--skip-syntax-check)`, and JSON `syntax.status "skipped"`.
  - The session event's `args` carry the flag, as they carry every flag.
  - `--help` lists it. No verdict, refusal or `do instead:` suggests it (T4: the environment never
    suggests a skip).
- **FR-26** Every edit's and dry run's verdict carries the check's outcome, and JSON always has `syntax`.
  The outcomes are `syntax: ok (CHECKER)`, `skipped`, `not checked (…)` or `already failed …`. The no-op
  (`--old` equal to `--new`) checks nothing and says nothing.
- **FR-27** **The manifest and the announcement:**
  - usage gains the anchor form and the check;
  - manifest extras gain `anchor_form: "N:hhhhhh[..M:hhhhhh]"`, `syntax_checkers` (language → checker)
    and `syntax_time_limit_s: 10`;
  - exit 1's text gains "would break the file's syntax", and exit 3's gains "stale anchors";
  - the announcement and `timelike tools` regenerate from `--agent-info`;
  - `timelike-conform` passes over the new `edit`.

**Carried from slice 0** (008 Cycle 1's `not_verified`)
- **FR-28** The slice-0 e2e files gain `bash -lc` cells.
  - The `type -a edit` cell also runs under `bash -lc`, where Debian's `/etc/profile` resets `PATH`.
  - The atomic write's owner branch runs under a real second uid: a file owned by another user,
    writable by the agent, is refused with `cannot keep FILE's owner`, and its hash is unchanged.

### Success criteria (slice 1)

The criterion text is the send's, copied exactly. Each automated criterion is one e2e file in the image,
under `bash -c` and `bash -lc`. Each byte-identical claim is checked by a hash the test reads (P004).

- **SC-7** "An edit addressed by viewer anchors applies when the anchored lines are unchanged and is
  refused, naming the changed lines, when they are not". The expected anchors are computed by the test
  with `hashlib` over the raw line bytes, not by calling `view` (P005). Cases: unchanged (applies), a
  changed end (exit 3, named), and a move (exit 3, named, with the rerun command). *(slice 1)*
- **SC-8** "An edit that would make a Python, TypeScript, Go, Rust or shell file fail its syntax check is
  refused with the checker's error, and the file is byte-identical". For each language, a valid fixture
  written by the test is edited into an invalid one, and the edit is refused with the checker's line and
  message, with the hash unchanged. A valid edit applies. A decoy `python3` and `bash` on the agent's
  `PATH` change nothing (P002). *(slice 1)*
- **SC-9** "DEMO: the Agent's edit that would break the file's syntax is rejected with the error and the
  file is left unchanged" (D15). Manual: the mentor captures it after the lane. *(slice 1)*

### Decisions (the slice-1 seams; reasoning in `research.md` R9 to R15)

| Point | Decision |
|---|---|
| Checker carrier (seam 1) | Python: timelike's interpreter's compiler. Shell: `bash -n`. TS/TSX/Go/Rust: tree-sitter's Python binding and prebuilt grammar wheels, pinned by hash, in timelike's interpreter (the CLI would need a compiler) |
| Direction of error (seam 2) | Python and shell are exact (the language's own parser). Tree-sitter errs both ways, measured per grammar in R10; only *introduced* errors refuse, so a grammar's gap costs an edit that adds the construct, never other work |
| An already-broken file (seam 3) | Refuse only a new error inside the lines written. Identity is message plus line text |
| Language (seam 4) | Extension, then shebang; `.tsx` uses the TSX grammar; `.mts`/`.cts` are TypeScript; unknown applies with `not checked (language unknown)` |
| The checker's failure (seam 5) | Fail open, with `not checked (checker failed: …)`; 10 s limit; child killed |
| The skip (seam 6) | `--skip-syntax-check`, visible in the command, verdict and event; never suggested |
| Anchors (seam 7) | `--at N:h[..M:h]` with `--new` only; the ends are checked; a move is refused, naming where it went; view's own `anchor_of` and `line_body` |
| The refusal's code | Syntax: exit 1 (the operation ran and refused, as binary or unwritable does). Stale anchors: exit 3 (the addressed text is not there, as no match) |
