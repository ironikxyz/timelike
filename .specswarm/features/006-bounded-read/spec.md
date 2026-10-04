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
- **FR-7** A line longer than the terminal width is cut in text mode at `COLUMNS` with
  `…[cut N bytes]` (rule 13, as every timelike tool does). JSON carries the line whole.

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
before this part is built** (D-11).

**D-3 · Search: hits against lines.** The cap counts **hits** (50). Each hit prints as one line, so
for search the omitted *lines* in rule 3's omission line equal the omitted hits, and its bytes are those
lines' bytes. File-group labels are section labels, not counted lines. JSON's `truncated` carries
`omitted_lines` (= omitted hits), `omitted_bytes`, `full_output` (the saved hit list) and `more` (`sed -n
A,Bp <hit list>`, never a re-run). `count` and `shown` carry the hit totals. **The narrowing command is the
last line before the omission line**, written `narrow: search … <dir>  (N of the 262)`, so the footer
both states the 212 and narrows. **Raised with D-2** (where the narrowing sits relative to rule 3's order).

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
