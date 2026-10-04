# Data model — 006 Bounded read and search (slice 0)

No state is kept between calls except `search`'s saved hit lists in the session scratch directory
(rule 10). Nothing is written to the workspace.

## Window (`view`)

| Field | Type | Meaning |
|---|---|---|
| `path` | string | FILE as given (relative paths stay relative; the printed commands use it) |
| `abs_path` | string | its real path: the omission line's full output |
| `total` | int | lines in the file (`\n` count, plus one for a final line without `\n`; 0 for empty) |
| `start`, `end` | int | the range shown, 1-based, inclusive (0, 0 for an empty file) |
| `target_line` | int or null | N for `FILE:N` (not `target`: rule 12 reserves it for FILE) |
| `next` | string or null | the next window's command when lines remain after `end`, else null |
| `clipped` | bool | a requested end past the file was clipped to `total` |
| `replaced_bytes` | int | undecodable bytes shown as U+FFFD |
| `escape_lines` | int | lines whose terminal escapes were stripped (rule 13) |

**Binary result:** `path`, `abs_path`, `binary: true`, `type` (R3), `size` (bytes). No lines.

**Line layout:** `{number right-aligned to len(str(total))}{marker} {text}`, marker `>` on `target`, else a
space. Slice 1's anchor goes between the marker and the text (spec D-9).

**Window rules:**
- no range: `1 .. min(total, 120)`, or the whole file with `--limit 0` (spec FR-6; corrected in
  implement: this line first said 1..120 for `--limit 0` too, against FR-6 and the quickstart);
- `A-B`: `A .. min(B, total)`; `A > total`, `A < 1` or `A > B` is a usage error;
- `N`: `max(1, N-10) .. min(total, N+10)`; `N > total` or `N < 1` is a usage error;
- then, when `limit > 0` and the range is longer than `limit`: `start .. start+limit-1`;
- the window is a **cut** when `(start, end) != (1, total)`. Then `next` is `FILE:{end+1}-{end+120}` when
  `end < total`; when `end == total` (a window at the end of the file) the cut's `more:` is the window
  before it, `FILE:{max(1, start-120)}-{start-1}`. The omitted figures count every file line outside
  the window and its bytes (as read, with newlines).

## Hit (`search`)

| Field | Type | Meaning |
|---|---|---|
| `path` | string | relative to the current directory when under it, else absolute |
| `line` | int | 1-based |
| `text` | string | the line, decoded as in R4 |

## Search result data

| Field | Type | Meaning |
|---|---|---|
| `pattern` | string | as given |
| `roots` | list | the PATHs searched |
| `count` | int | total hits |
| `shown` | int | hits printed (≤ the cap) |
| `files_matched` | int | files with ≥ 1 hit |
| `files_searched` | int | text files read |
| `skipped` | object | `{ignored, binary, large, unreadable}` counts |
| `narrow` | string or null | the narrowing command (spec D-3), when hits were omitted |
| `strict` | bool | `--strict` was given |
| `timed_out` | bool | the time limit fired (exit 124), with `not_reached` naming the first path not read |

**Order:** files by path (byte order of the printed path), hits by line. The first `cap` hits in that order
are shown.

**Narrowing (spec FR-17):** among the directories and files below the search root, take the one with the
most hits that holds **fewer than all** of them, preferring the shallowest on ties. Write it as
`search <same pattern and flags> <that path>`, with `(N of the T)`. When every hit is in one file, there is
no smaller place to search, and the line says so (`narrow: all T are in FILE; narrow the pattern, or view
FILE:<first hit>`).
