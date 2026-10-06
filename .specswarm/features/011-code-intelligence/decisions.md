# Decisions Log — Feature 011
> Generated at 2026-10-06T17:16:27+00:00
> Spec: .specswarm/features/011-code-intelligence/spec.md

## Decision Key

| Tag | Meaning |
|-----|---------|
| ASSUMED | Assumption made without explicit spec guidance (confidence: high/medium/low) |
| DEFERRED | Decision postponed — noted for later resolution |
| FLAGGED | Judgment call between alternatives — requires review |
| ABSENT | What was NOT done and why — forced reflection on gaps |
| INHERITED | Assumption carried forward from a prior task's output |

---

Run: `/specswarm:implement --dispatch`, specswarm 4.0.1-botbaubble.2.35.0 (`4ff8dcb`). Blocks are run from
the installed `commands/implement.md` (the expansion again replaces awk's `$0` with `--dispatch`), with
`CLAUDE_PLUGIN_ROOT` set to the cache path. Checklists: requirements.md 16/16.
Pause file path (step 1e): `<repo>/../bridge/dispatch/pause-011.md` (the checkout path quoted as `<repo>/`, P2).



### T003: tools/bin/symbols — the index in the session scratch (fresh per call), Python by ast, JS/TS/Go/Rust/shell by line patterns, outline/def/callers/dependents
**Started:** 2026-10-06T17:17:10Z | **Completed:** 2026-10-06T17:20:38Z

INHERITED: research R1–R4's design and measurements; search's walk and ignore rules (loaded from tools/bin/search, as view does) (confidence: high)
FLAGGED: Python signatures are regenerated from the syntax tree (`ast.unparse` of the arguments and return), not copied from the source — a body line can never leak into an outline, and a multi-line signature becomes one line; the cost is spacing normalised (`force: bool=False`) (confidence: high)
FLAGGED: call sites for Python come from `ast.Call` (so comments and strings never count) but are still name matches, and the header says `text-based` for every callers answer, Python included — the criterion asks for it and a name match is not a resolved call (confidence: high)
FLAGGED: other file types are not indexed in slice 1 (spec amended from "def by a name match, low precision"); def's not-found remedy names `search -w` (confidence: medium)
FLAGGED: dependency and build directories (node_modules, vendor, .venv, build, dist, target, caches) are not indexed, on top of .gitignore — they are not the agent's code, and indexing them would cost the 2 s bound in a JS repository (confidence: medium)
ASSUMED: a workspace is the nearest ancestor holding .git (a file or a directory, so worktrees count), else the current directory, said in the verdict (confidence: high)
ABSENT: a cache that survives sessions (the state root, 07 slice 1; FOR-MENTOR Item 20 in T004); resolved calls; languages beyond the five
Verification: host smoke run on a 3-file Python fixture (outline 6 definitions with nested/async/decorated ranges; def ranked, exit 3 with `search -w`; callers 3 sites in 2 groups, the comment and the string not counted; dependents direct then indirect; a change reported `cache stale: 1 file changed` and answered from the new content). On a generated 1,000-file repository: cold 1882 ms, warm 259 and 284 ms (bound 2 s warm). ruff, format, mypy strict clean; host conformance: 12 tools pass
SCOPE: in (1 changed files)

### T004: FOR-MENTOR.md Item 20 — the symbols index lives in the session scratch until the state root exists (seam 1)
**Started:** 2026-10-06T17:20:49Z | **Completed:** 2026-10-06T17:20:59Z

INHERITED: the index location and the measured cold/warm cost — from T003 (confidence: high)
FLAGGED: raised as an item, not a pause, as the send's seam 1 asks — nothing in slice 1 waits on it (confidence: high)
ABSENT: moving the index (the state root does not exist yet)
Verification: the item names what was built, its measured cost, and the one-path change that would move it
SCOPE: in (1 changed files)

**Fixes from the T001 delegate's findings (2026-10-06T17:23:49Z, read from the clock)**, made in tools/bin/symbols before T001's commit. The delegate's tests (written from the contract) ran 38/42 against T003; the 4 failures were 3 tool deviations:
1. **Notes after the cache clause:** the contract says every verdict ends with the cache state. The notes (workspace without .git, skipped files, unsaved cache, incomplete index) now come before it.
2. **A Python shebang was not recognised** (only shell's), so `outline /opt/timelike/bin/symbols` (the manifest's probe) was refused, and conformance would have failed in the image.
3. **Go import resolution was inverted:** it required the whole import path to be a suffix of the directory. Now the import path's last segments name the directory (research R3).

One contract amendment: an outline of a file outside the index ends with `cache: not used (outside the index: parsed directly)`, a fourth state. Claiming `fresh` for a file the index never saw would be false; the test's pattern gained exactly that state. 42/42 now.

### T001: tests/unit/test_symbols.py (delegated, from the contract): 42 tests on fixtures the tests write and count
**Started:** delegated,_written_after_8bac3b4_(its_start_was_not_read_from_a_clock) | **Completed:** 2026-10-06T17:23:54Z

INHERITED: the contract and research R7; `symbols` as committed at T003 and fixed after this file's first run (confidence: high)
FLAGGED: expected values come from the fixtures' own definitions (14 definitions listed by hand, 3 planted call sites, 2+1 importers), never from the tool (P005); a comment and a string carrying `save(` must not count (confidence: high)
FLAGGED: its first run found 3 tool deviations (4 failures), fixed in the tool before this commit; one test pattern widened by exactly the fourth cache state the contract now names (confidence: high)
ASSUMED: the delegate's settlements: signatures compared without whitespace (ast.unparse prints `bool=False`), a class inside a class left unpinned, JS imports with the `.js` extension (confidence: medium)
ABSENT: exit 1 (index unreadable) and exit 124 (walk limit); shell `source` relative to the importer vs the root (both readings agree in the fixture) — named by the delegate as not tested
Verification: 42 passed (6.5 s), the 1,000-file warm timing under 2 s included; ruff clean
SCOPE: in (1 changed files)

### T002: e2e (delegated) — SC-1 to SC-5 and the name and manifest, 28 cells
**Started:** delegated,_written_after_8bac3b4_(its_start_was_not_read_from_a_clock) | **Completed:** 2026-10-06T17:25:42Z

INHERITED: the contract (as amended at fbf6d71: the cache state ends every verdict); helpers.bash; 010's files as the model (confidence: high)
FLAGGED: each cell its own workspace (a fresh directory holding .git) and session, checked empty first; fixtures by printf or the image's Python; expected values written by hand (14 definitions, 4 ranked `persist`, 3 planted `save(` calls among decoys in a docstring, a string and comments, 3+1 importers with 3/2/1 names) (confidence: high)
FLAGGED: SC-2's 2 s bound is measured inside the container around the warm command alone, after a cold call that must report `cache: built (1000 files)` (confidence: high)
FLAGGED: the contract's example signature now reads `bool=False`, as ast.unparse prints it (the delegate found the example and R2 disagreeing; aligned here in the contract, spec and data model) (confidence: high)
ASSUMED: the delegate's settlements: `1 file(s) changed` both accepted, depth compared relative to the top level, paths compared relative to the workspace, the `search -w` hint on stdout or stderr (confidence: medium)
ABSENT: the fourth cache state (an outline outside the index) — no criterion needs it; units cover it
Verification: shellcheck -x clean over the six files. Host stand-in (advisory): 26 of 28 ok; not ok only the 2 type -a cells (image-only); the warm def on 1,000 files took 168–175 ms there
SCOPE: in (6 changed files)

### T005: pyproject (ruff, mypy lists), Makefile (shellcheck list: the six e2e files), README (a symbols section)
**Started:** 2026-10-06T17:25:58Z | **Completed:** 2026-10-06T17:26:14Z

INHERITED: tools/bin/symbols — from T003 and its fixes; the e2e files — from T002 (confidence: high)
FLAGGED: committed only after `ruff check` printed "All checks passed!" over tools tests scan bench (010's T004 lesson) (confidence: high)
ABSENT: a Status bullet (the README's Status lists 001–004 only)
Verification: ruff check clean, format clean (71 files); mypy strict (25 files); shellcheck over the Makefile's 68 files, every file present
SCOPE: in (3 changed files)
