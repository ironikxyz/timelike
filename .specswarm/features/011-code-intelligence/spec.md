---
parent_branch: master
feature_number: "011"
status: In Progress
created_at: 2026-10-06T17:13:35+00:00
source_prompt: plan/.discover/prompts/10-code-intelligence.md
source_send: bridge/sends/10-rev1-20261004-183704.md
prompt_revision: 1
discovery_revision: 12
audited_against: [1]
slice: 1
---

# Feature: Code intelligence (prompt 10, slice 1: natural)

## Overview

An agent looking for one location reads ten files: `grep` for the name, `cat` each hit, scroll past the
bodies. `symbols` answers the structural questions directly, offline and deterministically. It never
returns a function body or a generated summary (P1):

- **`symbols outline FILE`:** a file's classes and functions with line ranges and signatures, no bodies;
- **`symbols def NAME`:** where NAME is defined, ranked, the best first; exit 3 when it is not found;
- **`symbols callers NAME`:** the call sites of NAME, grouped by the function that encloses each one. The
  header states that the answer is text-based (P3);
- **`symbols dependents FILE…`:** the files that import the given files, ranked.

An index of the workspace backs every answer. It is checked for freshness on every call and refreshed
before answering, so there is no build step to remember. When something changed, the verdict says the
cache was stale and what it rebuilt.

**Built under discovery revision 13's rulings** (code-track § Resume after pause-06). Nothing in this
feature mutates, so rule 9 does not apply.

**The repository orientation** (budgeted, 120 lines) is slice 2, and is not built here.

## The three seams (send), decided

1. **The cache location against revision 11.**
   - **Here:** the index lives in the **per-session scratch**:
     `<scratch>/<session>/symbols/<workspace key>.json`. That is outside the workspace and outside version
     control (rule 10, revision 11). It is rebuilt once per session, and refreshed per file after that.
   - **Not here:** prompt 10 (revision 1) says "excluded from version control", which assumed an
     in-workspace cache. Revision 11 struck that.
   - **What would make it survive** sessions is the per-workspace state root (07 slice 1, held). That is
     raised in `FOR-MENTOR.md` as an item, not a pause, as the send asks.
2. **Parsers.** **No tool is added to the image.**
   - **Python:** read with the interpreter's own syntax tree, so definitions, signatures, line ranges,
     enclosing functions and imports are exact for Python.
   - **TypeScript/JavaScript, Go, Rust and shell:** read by line patterns for their definition and import
     forms. Their answers say so ("text-based").
   - **Other files:** not indexed in slice 1, and `def`'s not-found answer names `search -w NAME` for them.
     This was amended at implement, from "a name match with a low-precision note": a second, weaker `def`
     path for unknown languages would blur the precision the header states.
   - **Why not ctags or tree-sitter now:** universal-ctags and the tree-sitter CLI are approved in
     `tech-stack.md`, but adding them changes `make scan`'s inputs and the bench images. Slice 1's criteria
     are met without them: the 14-entry outline and the 1,000-file timing are Python fixtures, and callers
     are text-based by the criterion's own wording. Adding them is left to a later slice, which would say
     so.
3. **Stated precision (P3).** Every answer carries its precision:
   - in the header's scope: `exact (python)`, `text-based`, or `mixed`;
   - in the verdict, with what that means: "text-based: name matches followed by `(`, not resolved calls".

## User Scenarios

### Actors
- **Agent** (primary): asks where things are and who uses them, then reads only those lines.

### Scenario 1: a file's shape (SC-1)
`symbols outline app/models.py` lists the file's 14 classes and functions, nested as they are, each with its
line range (`12-48`) and its signature (`def save(self, force: bool=False) -> None`). No line of any body is
shown.

### Scenario 2: where is it defined (SC-2)
`symbols def save` lists the definitions of `save`, best first: an exact top-level or method definition, in
the file that matches the name best. Each comes with its file, line and signature. An unknown name is exit 3,
with `do instead: search NAME`. On a 1,000-file repository, a warm call answers in under 2 seconds.

### Scenario 3: who calls it (SC-3)
`symbols callers save` returns the 3 call sites in a fixture that has exactly 3, grouped by the function
enclosing each one (`Order.checkout (app/orders.py:40-71): line 55`). The header says the answer is
text-based.

### Scenario 4: what depends on this file (SC-4)
After changing `app/models.py`, `symbols dependents app/models.py` lists the files that import it:
- direct importers first, ranked by how many of its names they import;
- then the files that import those, marked as indirect.

### Scenario 5: the cache follows the files (SC-5)
After `app/models.py` changes, the next `symbols def save` reports `cache stale: 1 file changed; rebuilt`
and answers from the new content: the new line, or the new definition.

### Edge cases
- **Not inside a repository:** the workspace is the current directory, and the verdict says so.
- **Ignored files** (`.gitignore`, `.git`, dependency and build directories) are not indexed: `search`'s
  rules, loaded from the file beside `symbols`, as `view` loads them.
- **A Python file that does not parse:** indexed by text patterns instead, and marked as such in its answers.
- **Files over 1 MiB, and binary files:** skipped and counted in the verdict.
- **A huge repository:** the index walk is bounded (100,000 files, then 30 s). The verdict says what was not
  indexed.
- **The scratch is cleared:** the next call rebuilds the whole index and says so.
- **`outline` of a file outside the index** (an ignored file, a path outside the workspace): parsed directly
  and answered. It is not cached.
- **`def` with several equally ranked definitions:** all of them are listed, in a stable order (path, line).

## Functional Requirements

### Index and freshness
- **FR-1** **The workspace:** the nearest ancestor of the current directory that holds `.git`, or the current
  directory. **The index file:** `<scratch>/<session>/symbols/<key>.json`, where `key` is a short hash of the
  workspace's real path.
- **FR-2** **Every call checks freshness first:** the workspace is walked, and each file's (size, mtime) is
  compared with the index.
  - **New, changed or removed files** are (re)parsed or dropped.
  - **The verdict reports** `cache: fresh`, `cache stale: N files changed, M removed; rebuilt`, or
    `cache: built (N files)`. JSON carries `cache: {state, changed, removed, files, seconds}`.
- **FR-3** **Index contents per file:**
  - its language;
  - its definitions: name, kind (class, function, method), qualified name, start and end line, signature,
    and parent;
  - its imports: the module or path, and the names imported;
  - its call-like name occurrences, for `callers`.

### Outline
- **FR-4** `symbols outline FILE` lists the definitions of FILE in source order, nested, each as
  `START-END  kind  signature`, with no other line of the file.
  - **Python:** exact (the syntax tree). Methods and nested functions are listed, and decorated
    definitions start at the first decorator.
  - **Other languages:** text-based. A definition's end is the line before the next definition at the
    same or a shallower level, or the end of the file.

### Definition
- **FR-5** `symbols def NAME` lists the definitions whose name, or qualified name, is NAME (`Order.save`
  also matches), ranked:
  1. an exact language (Python) before a text-based one;
  2. a top-level definition before a method, and a method before a nested function;
  3. a file whose path contains NAME (`save.py`, `orders/save/`) before others;
  4. path, then line, for stability.

  The first line of the answer is the best definition's `FILE:LINE` and signature. **No definition:**
  exit 3, `no definition of NAME in N indexed files`, with `do instead: search -w NAME`.

### Callers
- **FR-6** `symbols callers NAME` lists the occurrences of `NAME(` (and `.NAME(`) that are not NAME's own
  definitions:
  - grouped by the function enclosing each one, from the index's line ranges, or `(top level)`;
  - with the file and line for each;
  - **the header says `text-based`**, and the verdict says what that means: name matches followed by `(`,
    not resolved calls, so a same-named function elsewhere is included. Comments and string literals are
    excluded for Python, and not for other languages.

  No call site is exit 0 (`0 call sites`), as `search` treats no match.

### Dependents
- **FR-7** `symbols dependents FILE…` lists the indexed files that import any of the given files:
  - **Python:** `import a.b`, `from a.b import x` and relative imports, resolved to files in the workspace;
  - **JS/TS:** relative `import … from './x'` and `require('./x')`;
  - **Go:** an import path whose last segments name the file's directory;
  - **Rust:** `mod x;` and `use crate::x`;
  - **shell:** `source x` and `. x`.

  **Ranked:**
  1. direct importers before indirect ones (importers of importers, depth 2);
  2. then by how many names they import, or how often they reference the module;
  3. then by path.

  Each line names how the file imports it. A file nothing imports is exit 0, `0 dependents`.

### Contract
- **FR-8** **The name is `symbols`.** `code` is VS Code's command, and `ctags`/`tags` would promise ctags'
  format. A `type -a` cell checks that the image has no other `symbols`. The manifest: `mutating: false`,
  `reads_stdin: false`, `probe: ["outline", "/opt/timelike/bin/symbols"]` (its own source, Python).
- **FR-9** Exit codes:
  - `0`: answered;
  - `1`: the index could not be read or written (with its path);
  - `2`: usage;
  - `3`: not found (a `def` with no definition, an `outline` of a missing file);
  - `124`: the index walk hit its time limit before the answer could be complete.

  The output is bounded by rule 3, with one session event per call.

## Success Criteria

The criterion text is the send's, copied exactly. Each automated criterion is one e2e file in the image,
under `bash -c` and `bash -lc`, against fixtures the test writes (P005) and checks with its own count, not
the tool's.

- **SC-1** "A signatures view of a fixture file lists exactly its 14 classes and functions with line ranges
  and no function bodies".
- **SC-2** "A definition lookup returns the defining file and line first, exits 3 when the symbol is not
  found, and answers in under 2 seconds warm on a 1,000-file repository".
- **SC-3** "A callers lookup on a fixture with exactly 3 call sites returns those 3, grouped by enclosing
  function, with a header stating it is text-based".
- **SC-4** "A dependents lookup for a changed file returns the files that import it, ranked".
- **SC-5** "After a file changes, the next lookup reports the cache as stale, rebuilds it, and answers from
  the new content".
- **SC-6** "DEMO: the Agent asks where a symbol is defined and who calls it and receives ranked locations
  with signatures" (D19). Manual, after the lane.

## Key Entities

- **Index:** workspace, files {path: size, mtime, language, precision, definitions, imports, calls},
  built_at.
- **Definition:** name, qualified name, kind, start, end, signature, parent, precision.
- **Import:** target (module or path), names, line.

## Decisions

| Point | Decision |
|---|---|
| Seam 1 | Index in the session scratch, keyed by workspace; fresh on every call; the state root raised in FOR-MENTOR |
| Seam 2 | Python's syntax tree; text patterns for JS/TS, Go, Rust, shell; no tool added to the image |
| Seam 3 | Precision in the header's scope and the verdict |
| Name | `symbols` |
| Ranking | Exact before text-based, top level before method before nested, name in path, then path/line |

## Out of scope (slice 1)

- The repository orientation (slice 2).
- Resolved (semantic) calls.
- Languages beyond the five, except `def` by name.
- A cache that survives sessions (the state root).

## Assumptions

- The image's Python (3.14.x) parses the agent's Python code. A file in a newer syntax falls back to text
  patterns and says so.
- `search`'s ignore rules, loaded from the file beside `symbols`, decide what is indexed, as for `view DIR`.
