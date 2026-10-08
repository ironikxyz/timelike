---
parent_branch: master
feature_number: "006"
status: In Progress
created_at: 2026-10-04T06:40:00+00:00
source_prompt: plan/.discover/prompts/05-bounded-read.md
source_send: bridge/sends/05-rev1-20261004-061518.md
prompt_revision: 1
discovery_revision: 11
audited_against: [1]
slice: 0
---

# Feature: Bounded read and search — `view` and `search` (prompt 05, slice 0: skeletal)

## Overview

Agents read files and search code dozens of times per task, and today they do it with pipelines built
to bound the output: `sed -n '40,80p' file | nl`, `grep -rn pat . | head -50`. Each pipeline is several
executables, and none says what it left out (P2). This feature gives the agent one call for each, shaped
like the habits it already has (P3):

- **`view`** shows a numbered window of a file. The default window is 120 lines. The output names the
  file, the range out of the file's total, and the exact command for the next window.
- **`search`** finds a pattern under a directory and groups the hits by file. At most 50 hits are shown,
  and the output says how many were left out and gives a concrete way to narrow.

Both are bounded. Both end with a verdict, including when a search runs out of time. Both say what
they did not show. Neither dumps a whole file unless the file fits the window or the agent asked.

Slice 1 (not built here) adds a budgeted directory overview, and a viewer anchor mode that feature 06
(edit) accepts. This slice keeps room in the viewer's line layout for that anchor column.

## User Scenarios

### Scenario 1: read a window of a large file (Agent) — D5

The agent runs `view src/engine.py`. The file has 412 lines. It sees lines 1–120, numbered and
right-aligned. The header names `src/engine.py` and `lines 1-120 of 412`. The output ends with the
command for the next window, `view src/engine.py:121-240`, which works pasted into the same shell.

### Scenario 2: jump to a line, or a range (Agent)

A traceback names line 40. `view src/engine.py:40` shows lines 30–50, with line 40 marked.
`view src/engine.py:40-80` shows exactly lines 40–80. A typo in the name (`view src/engnie.py`) exits 3
and says no such file, with what to do instead.

### Scenario 3: a binary file (Agent)

`view build/app.o` does not print bytes. It prints the file's type and size and exits 0.

### Scenario 4: search a repository (Agent) — D5

`search parse_args` in a repository with 262 matches shows the first 50, grouped by file. The verdict
says 262 matches, 50 shown and 212 omitted. The output ends with a concrete narrowing (the directory
holding most of the matches) and with how to get the rest. Files the repository's ignore rules exclude,
such as build output, are not searched unless the agent asks.

### Scenario 5: nothing found (Agent)

`search no_such_symbol` exits 0. The verdict says 0 matches and names what was searched, because finding
nothing is a result, not a failure (rule 5). With `--strict` the same search exits 1, as grep does, and
the verdict says *no match (strict)*, so it cannot be mistaken for a failure.

## Functional Requirements

### `view`: what it shows

- **FR-1** `view FILE` shows the first window of FILE: lines 1 to 120, or the whole file when it has 120
  lines or fewer.
- **FR-2** `view FILE:A-B` shows lines A to B. `view FILE:N` shows line N with 10 lines of context on each
  side, clipped to the file, and marks line N. A range past the end is clipped to the file and says so.
  A start beyond the last line, or A > B, is a usage error (exit 2) naming the file's length.
- **FR-3** Each shown line is the line number, right-aligned to the width of the file's last line
  number, then a marker column (`>` on the target line of `FILE:N`, a space otherwise), then the line's
  text. The layout leaves the position after the number for slice 1's anchor column (D-9).
- **FR-4** The output names the file and the range shown out of the file's total, for example `lines
  1-120 of 412`, in the header's scope (rule 12).
- **FR-5** **When the window shows less than the whole file, the output is a cut** (rule 3, D-2): it ends
  with the omission line, which counts the file's lines and bytes that were not shown, names the file
  itself as the full output, and gives the command for the next window. **When the window shows the
  whole file, there is no omission line**, so its absence means nothing was left out.
- **FR-6** `--limit N` (rule 3's output cap, in lines; default 200) bounds any window: a range longer than
  the cap shows the first N lines of it, as a cut. `--limit 0` lifts the cap, which is how the agent asks
  for a whole large file.
- **FR-7** A line longer than the terminal width (`COLUMNS`, default 200) is cut at `COLUMNS` with
  `…[cut N bytes]` **in both modes** (rule 13). In JSON the cut byte count is carried as data
  (`cut_lines`). `--columns N` changes the width for one call, and `--columns 0` reads lines whole: the
  explicit request. When a window has cut lines, the last body line gives that exact command. *(Amended
  in place, declared: discovery revision 12, D-12. As first written, JSON carried the line whole.)*

### `view`: what it refuses or reports instead of content

- **FR-8** A missing FILE exits 3 with a verdict naming it and `do instead:` (D-10). A directory exits 2
  and suggests `search` or `ls`.
- **FR-9** **Binary** is decided by a NUL byte in the first 8 KiB, the habit of git and grep. A binary file
  prints its type and size instead of content and exits 0. The type comes from the file's leading magic
  bytes for common formats (ELF, PNG, JPEG, GIF, gzip, zip, PDF, SQLite, tar), else `data`.
- **FR-10** **Text that is not valid UTF-8** is shown with each undecodable byte replaced, and the verdict
  says how many bytes were replaced.
- **FR-11** **Terminal escape sequences** in the file are stripped from what is printed (rule 13). When
  that happens, the verdict says how many lines were altered, so the agent is never shown changed text
  silently.

### `search`: what it finds

- **FR-12** `search PATTERN [PATH…]` searches PATTERN in the files under each PATH, recursively. The
  default PATH is the current directory, as `grep -r` does. Printed paths are relative to the current
  directory when they are under it, so a printed command works pasted into the same shell.
- **FR-13** PATTERN is an extended regular expression (close to `grep -E`), case-sensitive.
  `-i` ignores case, and `-F` takes PATTERN as a fixed string. A pattern that does not compile is a usage
  error naming the position.
- **FR-14** **Ignore rules are respected by default** (D-5): every `.gitignore` in the searched tree, and
  the repository's `.git/info/exclude`. Directories named `.git` are never searched. `--no-ignore`
  searches everything except `.git`. Binary files (FR-9's test) are skipped and counted.
- **FR-15** Hits are grouped by file, files in path order, hits in line order. Each hit is one line:
  the line number, then the matched line's text.

### `search`: the cap and the footer

- **FR-16** **At most 50 hits are shown** (D-3). `-m N` changes the cap, as grep's `-m` does, and `-m 0`
  shows every hit.
- **FR-17** When hits were left out, the verdict states the total, the number shown and the number
  omitted, all in hits. The output ends with **a concrete way to narrow** (D-3): the directory or file
  holding the most matches, written as a full `search` command with its share of the total. It also
  gives how to see the rest, from a saved list of every hit (never by re-running the search).
- **FR-18** **Zero matches exits 0**, with a verdict that says `0 matches` and how many files were
  searched, and JSON `count: 0` (rule 5). **`--strict` makes zero matches exit 1** (D-4). The verdict
  then says `no match (strict)`, and the manifest declares that meaning of 1.
- **FR-19** **A search always ends** (P2). A time limit (default 30 seconds, `--timeout S`) ends a search
  with exit 124 and a verdict naming how many files were searched, how many hits were found, and the first
  path not reached. Files larger than 16 MiB are skipped and counted, never read whole.
- **FR-20** A PATH that does not exist exits 3 with a verdict naming it.

### Both

- **FR-21** Both commands follow the agent output contract of feature 001: the header, JSON when stdout is
  not a terminal and text on a terminal (rule 1, D-1), `--json`, `--text`, `--limit`, `--help` within 40
  lines, `--agent-info`, structured errors, and one session event per call.
- **FR-22** Both are read-only. They never write to the workspace. `search`'s saved list of hits goes in
  the session scratch directory (rule 10).
- **FR-23** Both are announced where agents look, as every timelike tool is (`timelike`'s tool list),
  and pass `timelike-conform`. Each name resolves to exactly one command on PATH (`type -a`, checked
  by this feature's own e2e cells).

## Success Criteria

Each is one test, named after its distinguishing text, in the image (bats e2e per invocation style) and
on the host (pytest). Fixtures are generated independently of the code that counts them (cross-stack
P005): the 412-line file and the 262 matches are written by the test, and their counts are checked
against the test's own arithmetic, never the tool's (P004).

- **SC-1** *"Viewing a 412-line file with no range shows lines 1–120 with right-aligned line numbers, a
  header naming the file and range out of 412, and a footer naming the next range command"*: `view` of a
  412-line file shows lines 1 to 120 exactly, numbered and right-aligned to 3 digits. The header scope is
  `lines 1-120 of 412`. The output ends with the next range command (`…:121-240`), which, when run, shows
  lines 121 to 240. A file of 120 lines or fewer is shown whole, with no omission line. *(slice 0)*
- **SC-2** *"Viewing `file:40-80`, `file:40` with surrounding context, and a missing file (exit 3) each
  behave as specified; a binary file prints its type and size instead of content"*: `file:40-80` shows
  exactly lines 40 to 80. `file:40` shows lines 30 to 50 with line 40 marked. A missing file exits 3 with
  `do instead:`. A binary file (ELF and PNG fixtures) prints its type and size and no content bytes.
  *(slice 0)*
- **SC-3** *"A search with 262 matches shows 50, grouped by file, with a footer stating the 212 omitted and
  a concrete way to narrow"*: a search over a real git repository with 262 matches (some in an ignored
  directory that is not counted) shows exactly 50 hits, grouped by file. The output states 262 total and
  212 omitted, and gives a narrowing command which, when run, returns fewer matches. *(slice 0)*
- **SC-4** *"A search with zero matches exits 0 with a zero-count header, and exits 1 only in strict
  mode"*: zero matches exits 0 with `0 matches` in the verdict and `count: 0`. The same search with
  `--strict` exits 1 with `no match (strict)`. A failure (an unreadable root) is distinguishable from
  both. *(slice 0)*
- **SC-5** *DEMO: "the Agent reads a window of a large file and searches a repository, each result
  ending with the exact command to narrow or continue"* (D5): Manual. The mentor captures the real
  exchange in `timelike-agent` as the agent user and interviews the operator. *(slice 0)*

Further, from the contract and the decisions below (not criteria of the prompt):
- `timelike-conform` passes on `view` and `search` in the image;
- `type -a view` and `type -a search` each resolve to exactly one command, timelike's;
- a search that hits its time limit exits 124 with a verdict naming what was searched.

## Key Entities

- **Window**: a contiguous range of a file's lines, `start..end` of `total`, with an optional target line.
- **Hit**: one matching line: path, line number, text.
- **Hit list**: every hit of one search, saved in the session scratch directory, which the "see the rest"
  command reads.
- **Ignore rules**: the patterns from `.gitignore` files and `.git/info/exclude` that decide what a
  search skips.

## Decisions (the seams the send named, decided here on purpose)

**D-1 · Rule 1 under a harness: JSON stays the default.** Under a harness stdout is a pipe, so both tools
print JSON unless `--text` is given, as every timelike tool does. The window is in the JSON as data:
`path`, `start`, `end`, `total`, `target`, `next` (the next range command), and `lines`. **`lines` holds
the same numbered lines that text mode prints**, so the D5 demo's agent sees numbered lines by default,
inside the JSON object. This keeps rule 1 whole: no tool gets a different default. It also keeps P3,
since the lines look like `cat -n` either way.

**D-2 · Rule 3 and a window: a partial view is a cut.** A window that shows less than the whole file
leaves lines out, and rule 3 says the omission line appears only when output was capped. So a partial
window **is** cut output: it ends with the omission line, and a whole-file view has none. That way a
window never reads as complete when it is not. The omission line's figures count the **file's** lines and
bytes not shown. Its full output is **the file itself**, by its absolute path; a copy in scratch would add
nothing. **Its `more:` is the next window's command** (`view FILE:121-240`). That is the prompt's
"footer naming the next range command". It is a narrower reading of `more` than "prints everything
omitted", which an earlier tool's `sed -n` over its artefact satisfies. **Raised in FOR-MENTOR Item 18
before this part is built** (D-11). *(Answered (a), mentor, 2026-10-04,
`../bridge/feedback/05-20261004-062732-view-search-rule3-and-byte-bound.md`: the next window is D5's
"continue", and the bundle's own `view` footer is a continuation. JSON's `truncated.more` equals the
text's `more:`.)*

**D-3 · Search: hits against lines.** The cap counts **hits** (50). Each hit prints as one line, so
for search the omitted *lines* in rule 3's omission line equal the omitted hits, and its bytes are those
lines' bytes. File-group labels are section labels, not counted lines. JSON's `truncated` carries
`omitted_lines` (= omitted hits), `omitted_bytes`, `full_output` (the saved hit list) and `more` (`sed -n
A,Bp <hit list>`, never a re-run). `count` and `shown` carry the hit totals. **The narrowing command is the
last line before the omission line**, written `narrow: search … <dir>  (N of the 262)`, so the footer
both states the 212 and narrows. **Raised with D-2** (where the narrowing sits relative to rule 3's order). *(Answered (a), same file: a
body line before the closing lines is content, and the order does not forbid it.)*

**D-4 · Strict mode's exit 1.** Discovery's constraint asks for it (grep compatibility). It is opt-in
(`--strict`), and the manifest's `exit_codes` declares 1 as *"failed; with --strict, also: no match"*.
The verdict tells the two apart: `no match (strict)` or the failure's own words. Zero results without
`--strict` stays exit 0 with `count: 0` (rule 5).

**D-5 · Ignore files: read in the standard library, with no git command.** Asking git (`git check-ignore`,
`git ls-files`) would be exact, but git reads the repository's `.git/config`, and some keys there
execute. 001's layer pins `core.hooksPath` (`GIT_CONFIG_*`), and the pager and editor (`GIT_PAGER`,
`GIT_EDITOR`, `/etc/gitconfig`). **It does not pin `core.fsmonitor`.** So, as 005's store does, this runs no
git command, and executes nothing from a repository's configuration. The stdlib reading implements git's
pattern rules: `*`, `?`, `[…]`, `**`, a leading `/` anchors, a trailing `/` matches directories only, and
`!` re-includes (except below an excluded directory, as git does). It applies each `.gitignore` to its own
subtree, plus `.git/info/exclude`. **Its limits, named:** it does not read `core.excludesFile` (the
user's global ignore, set in git config), or git's per-attribute rules, and it does not know which files
are *tracked* (git searches a tracked file even when a pattern matches it). `--no-ignore` searches
everything except `.git`.

**D-6 · Names (P3): `view` and `search`.** Neither shadows `cat`, `grep`, `ls`, `find` or `tree`. `read` is a
bash builtin. **`view` is discovery's own example of this tool** (P3's violation example names it). It is
also vim's read-only alias wherever vim is installed. The image has no vim, and the agent cannot install
packages (no root). In a derived image that adds vim, `/opt/timelike/bin` comes first on PATH, so `view`
would be timelike's. That is stated in the help text. The image installs no `search` command; the
`type -a` cells check both names in the image. **Those cells are e2e tests in this feature's own bats
files, as 005's R7 cells were, not part of `timelike-conform`** (the send says conform's; conform checks
the contract, C0–C9). Announcement is automatic: `timelike` lists every tool in `/opt/timelike/bin`
(`TIMELIKE_BIN_DIRS`, `tools/bin/timelike:45`), the path 005's tools took with no change to `image/` or
`tools/agentio`.

**D-7 · The window size and the cap.** Fixed defaults, matching the criteria exactly: 120 lines and
50 hits, with no environment variables. The flags are the habits: a range for the window, `--limit` for
the output cap (rule 3), and `-m` for the hit cap (grep). Context for `FILE:N` is 10 lines each side.

**D-8 · Stdlib first.** Search is Python's `re` over a stdlib walk, so FR-13's dialect is `re`'s:
`grep -E` syntax plus `\d`, `\w` and lookarounds, without POSIX classes such as `[[:space:]]`. No search binary is added: adding
ripgrep would change `make scan`'s inputs and the bench images. The measured cost decides later. If a
repository the bench uses makes stdlib search miss its time limit, ripgrep is the stated fallback (it is
in `tech-stack.md` as "invoked and wrapped").

**D-9 · Room for slice 1's anchors.** A line's layout is number, marker, text. Slice 1 puts the anchor
between the marker and the text. Then 06 (edit) can accept `FILE` plus an anchor without the viewer's
layout changing for anyone who does not ask for anchors.

**D-10 · Outcomes are verdicts**, as in 005: a missing file or path (exit 3) and a strict no-match (exit 1)
are results on stdout, with a header, a verdict, `do instead:` where there is something to do, and
`data.remedy`. `timelike-conform`'s probes run wherever conform runs, and C3 and C4 need a header. Usage
errors stay structured errors on stderr (rule 14).

**D-11 · What is raised before building.** D-2's `more` (the next window rather than everything omitted)
and D-3's narrowing line sit closest to rule 3's wording, so they are raised in FOR-MENTOR Item 18 with
the reading recommended here. The parts of 05 that do not depend on them are built first. D-1, D-4, D-5 and
D-6 change no contract and read no criterion more narrowly. They are listed in the same item for the
mentor to see, not to wait on.

**D-12 · Long lines in both modes (discovery revision 12, Q3 answered (a)).** Rule 13's cut applies to
JSON's content strings too, so a window is bounded at about 120 × 200 characters in either mode. The
fix is in `agentio`, so every tool inherits it: in JSON each string in `lines` longer than `COLUMNS` is
cut with the same marker, and the object carries `cut_lines: [{index, cut_bytes}]`. Verdicts, errors
and data fields (paths, ids, counts) are not content and are not cut. A tool may set the width for one
call: `view --columns N` (0 = whole lines), which is the explicit request revision 12 names. The closing
lines name it: `view` adds `long lines cut: K; read them whole with: view FILE:S-E --columns 0` as its
last body line, and `search` adds `long lines cut: K; read one whole with: view FILE:LINE --columns 0`
just before its `narrow:` line. This narrows no criterion. Other tools' JSON changes with it
(`changed_other_features`).

## Out of scope (slice 0)

The budgeted directory overview (D14) and the viewer's anchor mode, which are slice 1's two criteria.
Editing. Searching inside archives or binaries. Syntax highlighting. A file's encoding beyond UTF-8 with
replacement.

## Assumptions

1. The agent reads files it can open. An unreadable file is a verdict (`view`) or a counted skip
   (`search`), not a crash.
2. Files are read as they are when read. A file changing during a search is searched as read.
3. Line numbers count `\n`. A final line without a newline is still a line. `\r\n` files show their text
   without the `\r`.
4. The search's time limit is wall-clock time in this process. It bounds the walk and the reads, not the
   machine's load.

---

## Slice 1 (Cycle 2, send `bridge/sends/05-rev1-20261004-183704.md`; natural)

Built by `/specswarm:modify 006` on `modify/006-slice-1`, dispatch batch `20261004-183704`. Prompt 05 is
still at revision 1, and `audited_against [1]` is current (modify row 4). The slice-1 criteria were in
revision 1 from the start, so this is **added work** on a body that stays true. Two exceptions are
declared below: FR-8's directory refusal is replaced by the overview (FR-24), and FR-3's layout gains
its reserved anchor column (FR-32). The `Out of scope (slice 0)` list above is history.

### Scenarios

**Scenario 6: orient in an unfamiliar repository (Agent) — D14.**
1. The agent runs `view .` in a repository it has never seen. Its `node_modules/` holds 10,000 files.
2. One call shows the tree within 200 lines: directories first, then files with their sizes.
   `node_modules/` is one line with its counts, its kind and `expand: view node_modules/`, and `.git/`
   is another.
3. The verdict counts files, directories and bytes, and names how many directories were collapsed and why.

**Scenario 7: lines the edit tool can address (Agent).**
1. The agent runs `view --anchors src/app.py:40-60`.
2. Each line shows its number, its marker and a 6-character anchor, for example `  42 a3f9c1 return x`.
3. The same line shows the same anchor in any later view. After the line changes, its anchor changes.
   06 (edit) accepts `42:a3f9c1`.

### Functional requirements

**The overview (`view DIR`)**
- **FR-24** `view DIR`, where DIR is a directory (`.` included), shows an **overview** instead of
  refusing. *This replaces FR-8's "A directory exits 2 and suggests `search` or `ls`", declared.* The
  header's scope is `overview`, and the exit is 0.
- **FR-25** **The budget** is rule 3's output cap, in lines: 200 by default, `--limit N`, and `--limit 0`
  for no budget, which is how the agent asks for the whole tree. Each line is cut at `COLUMNS`, as in
  every mode (revision 12). This is the budget the contract already has (send seam 1). A total byte
  bound stays the bench's question (revision 6).
- **FR-26** **Lines:** DIR's entries, indented two spaces per level, directories first and then files,
  each group sorted by name. A directory ends with `/`. A file shows its size, for example
  `README.md  2.1 KiB`. A symbolic link shows `name -> target` and is never followed.
- **FR-27** **Ignore files are respected,** with `search`'s rules (D-5): `.gitignore` at every level and
  `.git/info/exclude`. An ignored file is not listed, and the verdict counts ignored files. An ignored
  directory is listed collapsed (FR-28). `--no-ignore` lists everything, except that `.git` stays
  collapsed.
- **FR-28** **Collapsed directories:** one line each, `name/  F files, D dirs, S; KIND — expand: view
  PATH/`. PATH is the directory's path as the agent's next command would type it, relative to the
  current directory when below it (cross-stack P002). The kinds, in precedence order:
  - `vcs`: `.git`, `.hg`, `.svn`;
  - `dependency`: `node_modules`, `bower_components`, `jspm_packages`, `vendor`, `.venv`, `venv`,
    `site-packages`, `Pods`, `.bundle`, `elm-stuff`;
  - `build`: `build`, `dist`, `target`, `__pycache__`, `.mypy_cache`, `.pytest_cache`, `.ruff_cache`,
    `.tox`, `.nox`, `.gradle`, `.next`, `.nuxt`, `.cache`, `coverage`, `.terraform`, and names ending
    in `.egg-info`;
  - `ignored`: a directory the ignore files exclude;
  - `budget`: a directory left unexpanded so the overview fits its budget (FR-29).

  DIR itself is never collapsed, so `view node_modules/` shows its contents, which is the expand
  command's meaning.
- **FR-29** **Fitting the budget:** DIR's own entries are always listed. Then directories are expanded
  breadth-first (shallower first, then by path), each one only if its entries fit the lines left.
  Directories that do not fit are collapsed as `budget`. When DIR's own entries alone exceed the budget,
  the output is a cut (rule 3): the generic omission line, whose `more` re-runs with `--limit 0`. That is
  harmless for a read-only tool.
- **FR-30** **Counts in a collapsed directory** stop at 100,000 entries per directory. Beyond that the
  line says `100000+ files`, and JSON says `complete: false`, so the overview always concludes (P2).
- **FR-31** **Verdict:** `F files, D dirs, S under DIR; collapsed N (KIND n, …); I ignored files not
  listed`, with the clauses that apply. JSON carries `overview: true`, `path`, `abs_path`, `files`,
  `dirs`, `bytes`, `ignored_files`, `budget_lines`, `collapsed: [{path, kind, files, dirs, bytes,
  complete, expand}]`, and `lines`: the same lines the text prints (D-1).

**Anchors (`view --anchors`)**
- **FR-32** `--anchors` adds an **anchor** to each shown line, in the column D-9 reserved: number,
  marker, anchor, a space, text. For example ` 42 a3f9c1 return x`, and `>` in the marker on `FILE:N`'s
  target line. *This extends FR-3's layout; without `--anchors` the layout is unchanged.*
- **FR-33** **The anchor** (send seam 2) is the first 6 lowercase hex characters of the SHA-256 of the
  line's raw bytes: as stored in the file, before decoding, before escape stripping, before the
  `COLUMNS` cut, with its line ending removed (`\n`, and a `\r` before it). So:
  - **stable:** the same bytes give the same anchor at any line number, in any file, view or mode;
  - **changes with content:** any changed byte changes it, except with probability 1 in 16,777,216;
  - **short:** 6 characters.
- **FR-34** JSON carries `anchors: ["N:hhhhhh", …]`, one per shown line in order. That is the form 06
  (edit) slice 1 accepts, so 06 can take it without the viewer changing (D-9's promise).
- **FR-35** The `next` and `more` commands, and the long-lines command, keep `--anchors` when it was
  given, so continuing keeps the mode.

**Carried from slice 0** (send seam 3)
- **FR-36** **Plurals:** `search`'s verdict says `1 file`, `1 match` and `searched 1 file`, never
  `1 files`. This was the D5 transcript's defect (mentor, history 2026-10-04T18:27:32Z).
- **FR-37** **Search speed in the image** is measured by an e2e cell over a generated corpus (about
  40 MiB of text). The cell asserts the search concludes within 30 s and prints the measured MB/s into
  the TAP output for the lane's record. It is a measurement, not a criterion. D-8's fallback (ripgrep)
  is decided from it.
- **FR-38** **A window ending at the file's end** (`view FILE:400-412` of a 412-line file) is a cut
  whose `more` is the window before it (`view FILE:280-399`). It is now also checked end to end, not by
  the units alone.

### Success criteria (slice 1)

The criterion text is the send's, copied exactly.

- **SC-6** *"A directory overview of a repository with a dependency directory of 10,000 files fits its
  default budget, collapses that directory to one line with counts, and names how to expand it"*. The
  fixture is a real git repository with a `node_modules/` of 10,000 files, written by the test, which
  counts them itself (P005). `view .` prints at most 200 body lines. `node_modules/` is exactly one line
  with `10000 files` and `expand: view node_modules/`. Running that expand command shows
  `node_modules/`'s own entries. *(slice 1)*
- **SC-7** *"The viewer's anchor mode shows a short, stable anchor per line that changes when the line's
  content changes"*. `view --anchors` shows a 6-hex anchor per line. The anchors equal SHA-256 prefixes
  the test computes itself (P005). They are unchanged by a second view and by inserting lines above.
  Changing one line changes that line's anchor only. *(slice 1)*
- **SC-8** *DEMO: "the Agent orients in an unfamiliar repository with one budgeted directory overview"*
  (D14). Manual: the mentor captures it after the lane. *(slice 1)*

### Decisions (the slice-1 seams; reasoning in `research.md` R7–R10)

| Point | Decision |
|---|---|
| The overview's name | `view DIR`: one name, discovery's own example; vim's `view .` lists a directory, so the habit exists. Replaces FR-8's refusal |
| The budget | Rule 3's output cap, in lines (200, `--limit`); lines cut at COLUMNS |
| Collapsing | By kind (vcs, dependency, build, ignored), then breadth-first to fit the budget (`budget`) |
| Counting | Capped at 100,000 entries per collapsed directory (`100000+`, `complete: false`) |
| Ignore rules | `search`'s, loaded from `view`'s own directory as `undo` loads `snapshot` (005 R8): one implementation |
| The anchor | SHA-256 of the line's raw bytes without its line ending, first 6 hex; the edit form is `N:hhhhhh` |
| Plural | `1 file`, `1 match` |
