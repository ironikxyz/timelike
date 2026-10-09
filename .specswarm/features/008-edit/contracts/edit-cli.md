# CLI contract — `edit` (008, slice 0)

`edit` follows 001's output contract (`.specswarm/features/001-agent-shell-baseline/contracts/output-contract.md`):
- the header line `edit: <FILE> [<scope>]`, then `verdict: …`;
- JSON when stdout is not a terminal, text on a terminal (rule 1);
- `--json`, `--text`, `--limit N`, `--verbose`, `--help` (≤ 40 lines), `--agent-info`;
- structured errors on stderr (rule 14);
- one session event per call;
- rule 13's line cut, in both modes, on the lines it shows.

```
edit FILE --old TEXT --new TEXT             replace TEXT where it occurs exactly once
edit FILE --old TEXT --new TEXT --dry-run   print the unified diff; write nothing
```

## Manifest

| Field | Value |
|---|---|
| `mutating` | `true` |
| `confirm_protocol` | `false` (discovery revision 13; spec FR-12). No `--yes`, never exit 4 |
| `destructive` | `true` (it overwrites), so the parser adds `--dry-run` |
| `dry_run` | `true` |
| `reads_stdin` | `false` (rule 4: TEXT is an argument) |
| `envelopes` | `[]` |
| `probe` | `["/etc/os-release", "--old", "PRETTY_NAME=", "--new", "PRETTY_NAME=", "--dry-run"]` (no change; R7) |
| `exit_codes` | `0` edited, or nothing to do · `1` refused: binary, unwritable, too large, changed since read, owner cannot be kept · `2` usage · `3` no such file, no match, or more than one match |
| extra | `levels: ["exact", "line endings", "indentation"]`, `context: 3`, `candidates: 3`, `candidate_floor: 0.5` |

`--yes` is not a flag. Passing it is a usage error (exit 2: unknown flag), as for any tool that does not
confirm.

## Target, scope and lines

- **Target:** FILE as given. Relative paths resolve from the current directory, and printed commands reuse
  FILE as given.
- **Scope:** one of
  - `lines S-E of T` (edited, or the dry run's region);
  - `no change`;
  - `ambiguous`;
  - `no match`;
  - `not found`;
  - `refused`.
- **Numbered lines** are `view`'s: `{n:>W}{m} {text}`, where `W = len(str(T))`. The marker `m` is `>` on a
  line the edit changed or added, and a space otherwise. CR is not shown, and the text is shown as `view`
  shows it (U+FFFD for undecodable bytes, escapes stripped).

## Outcomes

### Edited (exit 0)

```
edit: src/app.py [lines 41-43 of 121]
verdict: edited lines 42-43 of 121 (matched ignoring line endings and indentation (4 spaces = 1 tab))
 39      def run(self):
 40          x = self.load()
 41          if x:
 42>             return x + 1
 43>         log("none")
 44          return None
 45
```

- **The region shown:** the edited lines, with 3 lines of context each side, clipped to the file. The
  verdict's range is the new text's lines in the file after the edit (`T` is the new total). An edit that
  removes every line of its region names the line it collapsed to: `edited at line N (2 lines removed)`.
- **The level phrase:**
  - `matched exactly`;
  - `matched ignoring line endings`;
  - `matched ignoring line endings and indentation (A = F)`, where A and F are units such as
    `4 spaces` and `1 tab`.
- **Verdict additions**, appended with `; `:
  - `via symlink to <real path>`;
  - `hard link broken (N links)`;
  - `N undecodable bytes kept`;
  - `line endings: N CRLF → N LF` (or the like), when the edit changes endings in the region (possible
    only at level 1, where `--new` is inserted as given).
- **JSON data:**
  - `path`, `abs_path`;
  - `level` (`exact` | `line_endings` | `indentation`), and `mapping` (`{"agent": "4 spaces", "file":
    "1 tab"}` at level 3, else null);
  - `start`, `end`, `total`, `match_start`, `match_end` (the old region's lines, before);
  - `line_ending` (`CRLF` | `LF` | `CR`), the ending given to the new text;
  - `sha256_before`, `sha256_after`;
  - `changed: true`.
  `lines` holds the numbered lines.

### No change (exit 0)

`--old` equal to `--new`: verdict `no change: --old and --new are the same`, with the file untouched
(`changed: false`, the hash once). The match is still checked, so a no-op on text that is absent is exit 3.

### Dry run (exit 0)

```
edit: src/app.py [lines 42-43 of 121]
verdict: dry run: would edit lines 42-43 of 121 (matched exactly); nothing written
--- a/src/app.py
+++ b/src/app.py
@@ -39,6 +39,6 @@
 …
```

- **The diff:** a unified diff (`difflib.unified_diff` over the lines' text without their endings, 3
  lines of context, `lineterm=""`, labels `a/FILE` and `b/FILE`). Line endings are not shown in the diff.
  When the edit changes any line ending in the region, the verdict adds `line endings: N CRLF → N LF`
  (or the like), so an ending-only change is never silent.
- **JSON:** the diff is `lines` (the body; not repeated in `data`). `data` carries `dry_run: true`,
  `sha256_before`, `sha256_after: null` and `changed: false`, with the edited outcome's other fields
  (`level`, `mapping`, `start`, `end`, `total`, `match_start`, `match_end`, `line_ending`).
- **Bound:** the diff is body output, cut by rule 3 at `--limit` by agentio, which saves the whole output
  as an artefact in the session scratch dir and names it as the full output.

### More than one match (exit 3)

```
edit: src/app.py [ambiguous]
verdict: --old matches 3 times (matched exactly), at lines 12, 48, 97; nothing written
do instead: add lines of context to --old until it matches once; view src/app.py:12 shows the first
```

JSON: `matches: [{"start": 12, "end": 13}, …]`, `level`, `remedy`.

### No match (exit 3)

```
edit: src/app.py [no match]
verdict: --old matches nowhere (tried exact, line endings, indentation); 2 nearest candidates; nothing written
── candidate 1: lines 40-42, similarity 0.93: indentation ──
 40      if x:
 41          return x
 42      log("none")
── candidate 2: lines 88-90, similarity 0.61: line 2 differs ──
 …
do instead: copy the text from a candidate (view src/app.py:40-42), or search for it: search -F 'return x' src/app.py
```

- **No candidate ≥ 0.5:** the verdict says `no candidate above 0.5 similarity`. `do instead:` names
  `search`.
- **JSON:** `candidates: [{"start", "end", "similarity", "difference", "lines"}]`, `searched_lines`,
  `time_limited`.
- **Past the 5 s candidate deadline:** the verdict adds `; candidates searched in lines 1-N of T (time
  limit)`.

### Refusals

| Case | Exit | Scope | Verdict |
|---|---|---|---|
| no such file | 3 | `not found` | `no such file: FILE`, with `do instead:` naming how to create one (`printf … > FILE`) and `search -F` |
| a directory | 2 | — | usage error: `FILE is a directory` |
| binary (NUL in first 8 KiB) | 1 | `refused` | `binary file: <TYPE>, <size>; edit changes text files` |
| over 16 MiB | 1 | `refused` | `too large to edit: <size> (limit 16 MiB)` |
| not writable | 1 | `refused` | `cannot write FILE: permission denied; nothing written` |
| owner cannot be kept | 1 | `refused` | `cannot keep FILE's owner (uid U); nothing written` |
| changed since read | 1 | `refused` | `FILE changed while editing; nothing written`, `do instead:` rerun |
| empty `--old` | 2 | — | usage error: `--old is empty`; remedy: include a line of context to anchor the insertion |
| `--old`/`--new` missing | 2 | — | usage error |

Every refusal leaves the file byte-identical. The tests check that with `sha256sum`, not with the verdict.

---

## Slice 1 (Cycle 2, send `bridge/sends/06-rev1-20261009-102433.md`)

Additive. Every slice-0 outcome above stands, plus a `syntax` part in each verdict that writes or would
write (FR-26). Spec FR-13 to FR-28; research R9 to R16.

```
edit FILE --at N:hhhhhh --new TEXT                 replace line N, if its anchor is unchanged
edit FILE --at A:aaaaaa..B:bbbbbb --new TEXT       replace lines A-B, if both anchors are unchanged
edit FILE … --skip-syntax-check                    apply without the syntax check (shown in the verdict)
```

### Flags

| Flag | Meaning | Errors (exit 2, usage) |
|---|---|---|
| `--at SPEC` | `N:hhhhhh` or `A:aaaaaa..B:bbbbbb`: N, A, B ≥ 1, A ≤ B, six lowercase hex characters each | malformed (the message names the form); `--at` with `--old`; `--at` without `--new` |
| `--skip-syntax-check` | No check runs, and no child is started | — |

### Anchored edit applied (exit 0)

```
edit: src/app.py [lines 42-44 of 121]
verdict: edited lines 42-44 of 121 (addressed by anchors; checked at lines 42 and 48); syntax: ok (python 3.14.7 compile)
 39      def run(self):
 …
```

- **The region** is lines A to B, from the first byte of A to the end of B's content. B's line ending
  stays.
- **`--new`:**
  - its line endings become the ending of line A (or the file's most common one, for a last line
    without an ending), and one trailing newline in `--new` is dropped;
  - an empty `--new` deletes lines A to B, endings included (`edited at line A (7 lines removed)`).
- **JSON:** as an edit above, with `level: "anchors"`, `mapping: null`,
  `anchors: {"start": "A:aaaaaa", "end": "B:bbbbbb"}` (one `N:hhhhhh` for both ends when A = B).

### Anchors stale (exit 3, nothing written)

```
edit: src/app.py [anchors stale]
verdict: anchored lines changed: line 42 (anchor a3f9c1, now 7d01be); nothing written
 39 0c1d2e      def run(self):
 40 9a8b7c          x = self.load()
 41 51e0aa          if x:
 42>7d01be              return y
 …
do instead: view --anchors src/app.py:42-48, then rerun with the anchors it shows
```

- **Each changed end is named:**
  - `line N (anchor h, now h′)`;
  - `line N is past the end (T lines)`;
  - with both ends changed: `lines 42 and 48`, listing each.
- **A move** is recognised when each end's anchor occurs exactly once in the file, both at the same shift
  `d ≠ 0`:
  - the verdict is `anchored lines moved: lines 42-48 are now lines 45-51; nothing written`;
  - `do instead:` is `rerun with --at 45:a3f9c1..51:0b11e2 (view --anchors src/app.py:45-51 shows them)`;
  - the lines shown are the moved region's.
- **The lines shown** are the addressed region (or the moved one) with 3 lines of context, clipped to the
  file. They use `view --anchors`'s layout, `{n:>W}{m}{anchor} {text}`, with `>` on the anchored ends.
- **JSON:**
  - `changed: [{"line": 42, "expected": "a3f9c1", "now": "7d01be" | null}]` (`now` is null past the end);
  - `moved_to: {"start": 45, "end": 51}` or null;
  - `anchors_now: ["N:hhhhhh", …]` for the lines shown;
  - `remedy`.

### The syntax check

**Languages and checkers** (manifest `syntax_checkers`):

| Language | Files | Checker named in the verdict |
|---|---|---|
| `python` | `.py`, `.pyi`; shebang `python`, `python3`, `python3.N` | `python X.Y.Z compile` (the checker's interpreter) |
| `shell` | `.sh`, `.bash`; shebang `bash`, `sh` | `bash -n` |
| `typescript` | `.ts`, `.mts`, `.cts` | `tree-sitter-typescript V` |
| `tsx` | `.tsx` | `tree-sitter-typescript V (tsx)` |
| `go` | `.go` | `tree-sitter-go V` |
| `rust` | `.rs` | `tree-sitter-rust V` |

V is the installed grammar's version, read by the checker.

**The verdict's `syntax:` part, appended with `; `:**

| Outcome | Text | JSON `syntax.status` |
|---|---|---|
| passes | `syntax: ok (CHECKER)` | `ok` |
| an unknown language | `syntax: not checked (language unknown)` | `not checked` |
| the checker failed | `syntax: not checked (checker failed: REASON)` | `not checked` |
| skipped | `syntax: skipped (--skip-syntax-check)` | `skipped` |
| already failing, nothing new | `syntax: FILE already failed its check before this edit (line N: MESSAGE); no new error in lines S-E` | `already failed` |
| refused | (below) | `refused` |

REASON is one of these:
- `checker not installed at PATH`;
- `no tree-sitter grammar for LANGUAGE (NAME is not installed)`;
- `time limit 10 s`;
- `exit N: <the last stderr line>`;
- `unreadable output`.

**JSON `syntax`** is `{"status", "language" (null when unknown), "checker" (null when none ran), "errors":
[{"line", "column" (null for bash), "message"}], "reason" (null unless not checked or skipped),
"original_errors": […] (only when the original was checked)}`.

### Refused by the syntax check (exit 1, nothing written)

```
edit: app.py [refused]
verdict: refused: the edit would make app.py fail its syntax check (python 3.14.7 compile): line 12, column 9: expected ':'; nothing written
── syntax error 1: line 12, column 9: expected ':' ──
 10      x = 1
 11
 12> def f(x)
 13      return x
 14
do instead: correct --new and rerun (add --dry-run to see the diff first)
```

- **Which errors refuse:**
  - the original passes and the result does not: every result error is listed;
  - the original already fails: only the result errors inside the written lines S to E that the original
    lacks (identity: message plus the stripped text of the line) refuse, and only those are listed.
- **Bounds:** up to 3 errors are shown, each with the would-be result's lines L−2 to L+2. Their
  numbering is `edit`'s (`{n:>W}{m} {text}`), with `>` on line L. More than 3: `… and N more` (JSON
  carries all, up to 20).
- **No suggestion to skip:** neither `do instead:` nor any line names `--skip-syntax-check` (T4).
- **A dry run that would be refused** prints the diff, then the error sections, and exits 1. Its verdict
  is `dry run: would be refused: the edit would make … ; nothing written`.

### Manifest (additions)

| Field | Value |
|---|---|
| `anchor_form` | `"N:hhhhhh[..M:hhhhhh]"` |
| `syntax_checkers` | `{"python": "python compile", "shell": "bash -n", "typescript": "tree-sitter-typescript", "tsx": "tree-sitter-typescript (tsx)", "go": "tree-sitter-go", "rust": "tree-sitter-rust"}` |
| `syntax_time_limit_s` | `10` |
| `exit_codes` | `1`: refused: binary, unwritable, too large, changed meanwhile, **or the edit would break the file's syntax**; nothing written · `3`: no such file, no match, more than one match, **or stale anchors**; nothing written |
| `probe` | unchanged (`/etc/os-release` is an unknown language: no child) |

### The checker child (`libexec/syntax-check`; internal, not a tool)

- **Resolved** as `<dirname(realpath(edit))>/../libexec/syntax-check`, and run as
  `[sys.executable, "-I", CHECKER, LANGUAGE, str(len(result))]`. It is started in its own session, and
  its group is killed at 10 s.
- **stdin** is the result's bytes, then the original's bytes.
- **stdout** is one JSON object: `{"checker": "...", "result": [errors], "original": [errors] | null}`.
  The original is checked only when the result has errors.
- **Exit 0** means it ran. Any other exit, or unreadable output, is the checker's failure (FR-24).
- **Errors:** at most 20 per text, in file order. Tree-sitter reports the outermost `ERROR` and `MISSING`
  nodes only:
  - `ERROR` reads `unexpected 'TEXT'`, the node's text up to 20 characters of its first line;
  - `MISSING` reads `missing 'TOKEN'`.
- **Imports:** tree-sitter is imported from the checker's own interpreter's site-packages; under a venv
  interpreter (the image's unit lane), the base interpreter's. `-I` keeps `PYTHONPATH` and the user site
  out.
