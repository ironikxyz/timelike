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
