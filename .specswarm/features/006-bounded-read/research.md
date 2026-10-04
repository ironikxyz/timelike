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
