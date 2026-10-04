# Research — 006 Bounded read and search (prompt 05, slice 0)

Each entry: decision, rationale, alternatives. Measured on the host unless it says otherwise; the image
decides (R10).

## R1 · Search engine: stdlib `re` over a stdlib walk (spec D-8)

- **Decision:** `os.scandir` walk + `re` over each file's bytes, read once (up to 16 MiB). A file is only
  split into lines when the pattern matches somewhere in it.
- **Measured (2026-10-04, host, Python 3.12, warm cache, `def [a-z_]+\(`):** `tools/` 0.1 MB 2 ms;
  `tests/` 2.9 MB 34 ms; the whole checkout 21.9 MB in 570 text files 86 ms (255 MB/s);
  `/usr/lib/python3.12` 10.9 MB 213 ms (51 MB/s). At ≥ 50 MB/s, the 30 s limit covers about 1.5 GB of
  text before it fires.
- **Alternatives:** ripgrep (in `tech-stack.md` as "invoked and wrapped", absent from the image).
  Adding it changes `make scan`'s inputs and the bench images, and nothing measured needs it. It stays
  the stated fallback if a bench repository makes stdlib search miss its limit. `git grep` was rejected
  by D-5 (it reads `.git/config`).

## R2 · Ignore rules without git (spec D-5)

- **Decision:** a stdlib gitignore matcher. Patterns are compiled to regexes per git's
  `gitignore(5)`: blank lines and `#` comments skipped, `\` escapes, trailing spaces trimmed unless
  escaped; `!` negates; a trailing `/` matches directories only; a `/` at the start or in the middle
  anchors to the `.gitignore`'s directory, otherwise the pattern matches at any depth; `*` and `?` do not
  cross `/`; `**/`, `/**` and `/**/` per the man page; `[…]` classes. The last matching pattern wins,
  and a file below an excluded directory is never re-included (the walk prunes the directory).
- **Sources:** `.gitignore` in every directory walked, applying to its subtree; `<repo>/.git/info/exclude`
  for the repository the search root is in (the nearest ancestor with a `.git` directory, found with
  `lstat`, as 005 finds the workspace).
- **Not read:** `core.excludesFile` (git config); the index (so a tracked file matching a pattern is
  skipped, where git would search it).
- **Why not git:** 001 pins `core.hooksPath` (`GIT_CONFIG_*`) and the pager and editor, but not
  `core.fsmonitor`, which `git status` and `git ls-files` can run. 005 runs no git command either.

## R3 · Binary detection and type (spec FR-9)

- **Decision:** binary iff the first 8 KiB holds a NUL byte (git's and grep's test). Type from magic bytes:
  `\x7fELF` ELF, `\x89PNG` PNG, `\xff\xd8\xff` JPEG, `GIF8` GIF, `\x1f\x8b` gzip, `PK\x03\x04` zip,
  `%PDF` PDF, `SQLite format 3\0` SQLite, `ustar` at offset 257 tar; otherwise `data`. A PDF or zip
  without a NUL in its first 8 KiB is text by this test, which is grep's answer too.
- **Alternative:** `file(1)`/libmagic: not in the image, and a new package.

## R4 · Decoding (spec FR-10, FR-11)

- **Decision:** read bytes, split on `\n`, strip one trailing `\r`, decode UTF-8 with `errors="replace"`,
  and count the replaced bytes by decoding once strictly per line that fails. Lines carrying an escape
  (`\x1b`) are counted before agentio's rule-13 clean strips them. Both counts go in the verdict and as
  data (`replaced_bytes`, `escape_lines`).

## R5 · Conform probes

- **Decision:** `view` probes `/etc/os-release`; `search` probes `-m 1 ID /etc/os-release`. Both files exist
  on the host and in the image (Debian), and conform runs probes from its own directory (in the image,
  the home directory), so the probes take absolute paths.

## R6 · Where "the rest" of a search lives

- **Decision:** the saved hit list is `<session scratch>/search/hits-<sha256[:12]>.txt`, one hit per line
  as `path:line:text` (grep `-n` form), in display order. `more:` is `sed -n 51,262p <file>`, which prints
  exactly the omitted hits. Never a re-run (rule 3; a re-run could differ).

---

# Slice 1 (Cycle 2, send `bridge/sends/05-rev1-20261004-183704.md`)

## R7 · The overview's name and budget

- **The name.** `ls -R`, `tree` and `find . -type f` are the habits. None may be shadowed (prompt 05's
  constraint), and a new name has to be discovered (P3). `view` is already timelike's (D-6). Viewing a
  directory is what vim's `view .` does: it opens a directory listing. So `view DIR` costs the agent no
  new name, and it removes slice 0's refusal, which only told the agent to go elsewhere.
- **The budget's unit.** Lines, bytes and entries were the options (send seam 1). The contract already
  has lines: rule 3's cap, 200, `--limit`. Revision 12 bounds each line at `COLUMNS`, and revision 6
  leaves a total byte bound to the bench. An entries budget would be a third unit. Lines are what the
  agent's context pays for, line by line.

## R8 · Collapse and fit

- A dependency directory is named by convention, not detected by content. The kinds list
  (spec FR-28) covers npm, bower, jspm, Go and PHP vendoring, Python virtual environments, CocoaPods,
  Bundler, Elm, and the common build and cache directories. `out` and `env` are left out: they are too
  often source directories.
- Breadth-first expansion fills the budget with the shallow structure first. That is the orientation
  D14 asks for: what is at the top, and what is in each directory, before any one subtree in depth.
- Counting stops at 100,000 entries per collapsed directory. This keeps the call bounded for a pathological
  `node_modules`. `os.scandir` counts 10,000 entries in about 20 ms on this host.

## R9 · The anchor

- **Hash input:** the raw bytes, with the line ending removed. Hashing the shown text would make the
  anchor depend on `COLUMNS`, on escape stripping and on the U+FFFD replacement, so it would not be
  stable across views. Dropping the line ending makes a CRLF file and its LF copy agree line by line,
  which 06 needs, since it preserves line endings.
- **Length:** 6 hex characters is 24 bits. For one changed line, the chance that its anchor is unchanged
  is 1 in 16.7 M. 06 checks the anchor at its line number, so a stale edit is refused unless both the
  number and the anchor still match. 4 hex characters (1 in 65,536) was the shorter option, and it was
  judged too likely across a long session of edits.
- **Line number outside the hash:** inserting lines above does not change an anchor. 06 can then say
  "the anchored line moved to N" rather than "changed".

## R10 · Search speed in the image (carried)

The host measurement was 51–255 MB/s, depending on the pattern (R1). The image's Python 3.14.7 is
measured by the lane's e2e cell over a generated corpus. D-8's ripgrep fallback is decided from that
figure, not this cycle.
