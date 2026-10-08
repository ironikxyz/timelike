# Research — 011 Code intelligence (prompt 10, slice 1)

Each entry gives the decision, the rationale and the alternatives. Everything was measured on the host
(Python 3.12) unless it says otherwise; the image (3.14.x) decides in the lane.

## R1 · Speed: an index in the session scratch, refreshed per file (SC-2, FR-1, FR-2)

**Measured:** a generated repository of 1,000 Python files in 20 packages, each with 3 classes of 4 methods
and 5 functions (about 60 KB of index per 100 files).
- **Cold build** (walk, `stat`, `ast.parse`, definitions): **0.95 s**.
- **Warm call** (load the 0.6 MB JSON index, walk and `stat` every file, compare, look up a name across
  3,000 definitions): **21–23 ms**.

The criterion's bound is 2 s warm, so there is roughly two orders of magnitude of headroom. That is kept
for imports and call sites in the real index.

**Decision:**
- **The index:** one JSON file per workspace, at `<scratch>/<session>/symbols/<key>.json`, where `key` is
  the first 12 hex of the SHA-256 of the workspace's real path.
- **Freshness, on every call:** a walk with `search`'s ignore rules, and (size, mtime_ns) per file. A
  changed file is re-parsed, a new one parsed, a missing one dropped. The index is rewritten (temp, then
  rename) only when something changed.
- **Bounds:** 100,000 files, files over 1 MiB skipped, and a 30 s walk limit. Past it, exit 124, naming
  what was indexed.

**Alternatives:**
- No index at all: a 1,000-file re-parse costs about 1 s per call, which is within 2 s, but it grows with
  the repository.
- An in-workspace cache: struck by revision 11.
- SQLite: not needed at this size.

## R2 · Python: the syntax tree (SC-1, FR-4, FR-5, FR-7)

**Definitions** come from `ast` (`ClassDef`, `FunctionDef`, `AsyncFunctionDef`), walked with their nesting:
- kind `class`, `function`, `method` (a function directly in a class), `nested`;
- the start is the first decorator's line, and the end is `end_lineno`;
- the qualified name is `Outer.inner`.

**The signature is regenerated from the node, not copied from the source:**
- `def name(args) -> ret` uses `ast.unparse` of the arguments and the return annotation, with
  `async def` and `class Name(bases)` as their own forms;
- so no body line can leak in, and a signature spanning several lines becomes one line.

**Imports:** `Import` and `ImportFrom`, with relative levels resolved against the file's package. A module
is resolved to a workspace file `a/b.py` or `a/b/__init__.py`, tried from the workspace root and from each
top-level directory that holds packages (the `src/` layout).

**Call sites** (for `callers`): `ast.Call` whose function is `Name(id)` or `Attribute(attr)`, with their line
and column. A text-based match on Python is therefore free of comments and strings. It is still a name
match, not resolved, and the header says so.

## R3 · Other languages: line patterns, labelled text-based

| Language | Definitions | Imports |
|---|---|---|
| JS/TS (`.js .mjs .cjs .jsx .ts .tsx`) | `function NAME(`, `class NAME`, `(export )?(const\|let) NAME = (async )?(…) =>`, methods `NAME(…) {` inside a class | `import … from './x'`, `require('./x')` (relative only) |
| Go (`.go`) | `func NAME(`, `func (r T) NAME(`, `type NAME struct\|interface` | `import "path"` and grouped imports; the last segments are matched to a directory |
| Rust (`.rs`) | `fn NAME`, `struct\|enum\|trait NAME`, `impl … for … {` | `mod x;`, `use crate::x::…` |
| shell (`.sh .bash`, and shebangs) | `NAME() {`, `function NAME` | `source x`, `. x` |

- **End lines** come from indentation and braces: the line before the next definition at the same or a
  shallower depth, or the end of the file.
- **Calls:** `\bNAME\s*\(` on lines that are not the definition.
- **Precision:** `text-based`.

**Alternatives:**
- **universal-ctags** gives definitions, but no ends for all languages, no calls and no imports.
- **tree-sitter** needs grammars per language in the image.

Both are approved, but they change the image (scan, bench), and slice 1 does not need them (spec seam 2).

## R4 · Ranking (FR-5, FR-7)

**`def`, ranked by:**
1. precision (exact before text-based);
2. kind (class and function before method, method before nested);
3. NAME in the file's path;
4. qualified-name equality (`Order.save` asked, `Order.save` found);
5. path, then line.

**`dependents`, ranked by:**
1. direct before indirect (depth 2);
2. the count of imported names, or references to the module, descending;
3. then path.

The send's "ranked" is satisfied by a stated order, which the contract prints in the verdict.

## R5 · Reuse

- **`search`'s walk and ignore rules:** loaded from the file beside `symbols`, as `view DIR` does (006 R7).
  One implementation of `.gitignore`.
- **Rule 15's redaction:** not applied. `symbols` prints only names, signatures and paths from the agent's
  own code, never log or command output.

## R6 · Name, probe, image

- **`tools/bin/symbols`:** no image change beyond the file. The announcement lists it.
- **The probe:** `outline` of its own file (`/opt/timelike/bin/symbols`), a Python file that is always
  there. Conformance then runs it with `--json` and `--text`.
- **The `type -a` cell** guards the name.

## R7 · Tests

**Units:** `tests/unit/test_symbols.py`. Fixtures are files the test writes. Counts come from the test's
own list (P005), never from `symbols`. They cover:
- a Python fixture of exactly 14 classes and functions (nested, decorated, async, multi-line signatures);
  no body line in the output;
- `def`: ranking, qualified names, exit 3;
- `callers`: 3 call sites in 2 functions plus the top level, a comment and a string that must not count,
  and the text-based header;
- `dependents`: direct and indirect, ranked;
- a stale cache: change a file, then the next call says stale and answers from the new content;
- each text-based language: one definition and one import each;
- a parse failure falling back to text; a binary file skipped;
- a 1,000-file warm timing (generated by the test).

**e2e:** one bats file per criterion, `bash -c` and `bash -lc`, each with its own workspace and session.
Plus the `type -a` and manifest cells.
