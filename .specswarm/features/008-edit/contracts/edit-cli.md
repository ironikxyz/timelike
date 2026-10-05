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
