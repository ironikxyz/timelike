# CLI contract — `view` and `search` (006, slice 0)

Both follow 001's output contract (`.specswarm/features/001-agent-shell-baseline/contracts/output-contract.md`):
- the header line `<tool>: <target> [<scope>]`, then `verdict: …`;
- JSON when stdout is not a terminal, text on a terminal (rule 1); `--json`, `--text`, `--limit N`
  (default 200, `0` = none), `--verbose`, `--help` (≤ 40 lines), `--agent-info`;
- structured errors on stderr (rule 14); one session event per call.

**Outcomes are verdicts** (as 005): "no such file or path" (exit 3) and a strict no-match (exit 1) are
results on stdout, with the header, the verdict, `do instead: <remedy>` as the first line where there is a
remedy, and `data.remedy`. Usage errors are exit 2 on stderr.

**Not yet settled:** a line longer than `COLUMNS` in **JSON** (spec FR-7, FOR-MENTOR Item 18 Q3, with
plan). Until it is answered, JSON carries lines as agentio does today (whole), and no test pins that
behaviour. Text mode cuts at `COLUMNS` with `…[cut N bytes]` (rule 13), as for every tool.

## `view`

```
view FILE            the first window (lines 1-120), or the whole file if it has 120 lines or fewer
view FILE:A-B        lines A to B
view FILE:N          line N with 10 lines of context each side, N marked with >
```

Manifest: `mutating: false`, `destructive: false`, `probe: ["/etc/os-release"]`. Exit codes: `0` ok,
`1` the file could not be read, `2` usage, `3` no such file.

**FILE resolution.** When FILE itself exists, it is the file, colon and all. Otherwise a trailing `:N` or
`:A-B` (digits) is split off. Relative paths resolve from the current directory, and the printed commands
reuse FILE as given, so they work pasted into the same shell.

**Target and scope.** `<target>` is FILE as given. The scope is `lines S-E of T` (`empty` for an empty
file; `binary` for a binary file).

**Lines.** Each shown line is `{n:>W}{m} {text}`: n right-aligned to `W = len(str(T))`, m `>` on the target
line of `FILE:N` and a space otherwise, then one space and the text. JSON `lines` are the same strings.

**Whole file shown** (`S == 1` and `E == T`): no omission line. The verdict is `lines 1-T of T (whole
file)`. Text ends on the file's last line.

**Partial window: a cut** (rule 3, spec D-2, answered (a)):
- text:
  ```
  view: src/engine.py [lines 1-120 of 412]
  verdict: lines 1-120 of 412
  ── lines 1-120 of 412 ──
    1  …
  …
  120  …
  more: view src/engine.py:121-240
  exit: 0
  full output: /abs/path/src/engine.py
  … omitted 292 lines (N bytes) — full output: /abs/path/src/engine.py; more: view src/engine.py:121-240
  ```
- `more:` is **the next window**, `FILE:{E+1}-{E+120}` (its end may pass T; the next call clips it).
  When `E == T`, nothing follows, and `more:` is the window before: `FILE:{max(1,S-120)}-{S-1}`;
- the omitted figures count every line of the file outside the window, and their bytes as stored
  (newlines included);
- `full output:` is the file's real path (the file itself, not a copy);
- JSON: `truncated = {omitted_lines, omitted_bytes, full_output, more}`, and `data.next` equals
  `truncated.more` when lines remain after E.

**Verdict additions**, appended with `; `:
- `clipped to T` when a requested end passed the file;
- `N undecodable bytes shown as U+FFFD`;
- `N lines had terminal escapes stripped`.

**JSON data:** `path`, `abs_path`, `total`, `start`, `end`, `target`, `next`, `clipped`,
`replaced_bytes`, `escape_lines`.

**Binary** (a NUL in the first 8 KiB): exit 0, scope `binary`, verdict
`binary file: <TYPE>, <human size> (<bytes> bytes); content not shown`. No lines. JSON: `binary: true`,
`type`, `size`.

**Empty file:** exit 0, scope `empty`, verdict `empty file (0 lines)`.

**Refusals and errors:**
- no such file: exit 3, verdict `no such file: FILE`, `do instead: check the name; search for it with:
  search -F <basename> .`;
- a directory: exit 2 (stderr) `FILE is a directory`, remedy `view a file in it, or: search PATTERN FILE`;
- a start past the end (`A > T` or `N > T`), `A < 1`, or `A > B`: exit 2 naming T;
- an unreadable file: exit 1, verdict `cannot read FILE: <strerror>`.

## `search`

```
search PATTERN [PATH...]    hits grouped by file, at most 50 shown
  -i            ignore case
  -F            PATTERN is a fixed string
  -m N          show at most N hits (default 50; 0 = all)
  --strict      zero matches exits 1, as grep does
  --no-ignore   also search what .gitignore and .git/info/exclude exclude
  --timeout S   end the search after S seconds (default 30) with exit 124
```

Manifest: `mutating: false`, `destructive: false`, `probe: ["-m", "1", "ID", "/etc/os-release"]`. Exit
codes: `0` ok (zero matches is 0, with `count: 0`), `1` failed; **with --strict, also: no match**, `2`
usage, `3` no such path, `124` the time limit fired.

**Target and scope.** `<target>` is the PATHs joined by a space (`.` by default). The scope is the
pattern, `shlex`-quoted.

**What is searched.**
- Each PATH recursively; a PATH that is a file is searched itself, whatever the ignore rules say.
- Directories named `.git` are never entered. Symbolic links met during the walk are not followed.
  Hidden files are searched (grep's habit).
- Ignore rules (spec D-5): every `.gitignore` in the walk, applying to its own subtree, and the enclosing
  repository's `.git/info/exclude`. `--no-ignore` turns both off.
- Skipped and counted: binary files (NUL in the first 8 KiB), files over 16 MiB, unreadable files.

**Pattern.** Python `re` (extended syntax, close to `grep -E`), case-sensitive; `-i`, `-F`. A pattern
that does not compile is exit 2, naming the error's position.

**Output, all hits shown** (`count ≤ cap`):
```
search: . ['parse_args']
verdict: 12 matches in 3 files (searched 41 files; skipped 5 ignored)
── src/cli.py (5) ──
14: def parse_args(argv):
…
```
Each section label is `<path> (<hits in that file>)`. Each hit line is `<line>: <text>`.

**Output, hits omitted** (`count > cap`): a cut.
```
search: . ['parse_args']
verdict: 262 matches in 9 files; 50 shown, 212 omitted (searched 120 files; skipped 30 ignored)
── src/a.py (12) ──
…
── src/engine/run.py (8 of 41) ──
…
narrow: search parse_args src/engine  (148 of the 262)
more: sed -n 51,262p /tmp/timelike/<session>/search/hits-0123456789ab.txt
exit: 0
full output: /tmp/timelike/<session>/search/hits-0123456789ab.txt
… omitted 212 lines (N bytes) — full output: …/hits-0123456789ab.txt; more: sed -n 51,262p …/hits-0123456789ab.txt
```
- The `narrow:` line is the last body line (spec D-3, answered (a)). It reuses the pattern and flags, and
  names the directory or file below the root holding the most hits but not all of them.
- A file whose hits were cut part-way is labelled `(<shown> of <in file>)`.
- The omission line counts **hits** as lines (one line per hit) and their bytes in the saved list.
- The saved list holds every hit as `path:line:text`, in display order.
- JSON: `count`, `shown`, `truncated.omitted_lines == count - shown`, `narrow`; `lines` are the hit lines
  plus the `narrow:` line.

**Zero matches:** exit 0, verdict `0 matches (searched N files; …)`, `count: 0`, no lines.
**With `--strict`:** exit 1, verdict `no match (strict): 0 matches (searched N files; …)`, `do instead:
drop --strict to treat no match as a result`.

**Time limit:** exit 124, verdict `time limit 30 s reached: searched N files, H matches so far; not reached:
<first path not read>`. The hits found so far are shown under the same cap.

**Errors:** a PATH that does not exist exits 3 (verdict `no such path: PATH`). Bad flags or a bad pattern
exit 2.

## Session events

One per invocation, written by agentio, as for every tool.
