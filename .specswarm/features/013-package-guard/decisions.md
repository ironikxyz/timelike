# Decisions Log — Feature 013
> Generated at 2026-10-12T00:27:30Z (read from the clock)
> Spec: .specswarm/features/013-package-guard/spec.md
> specswarm: 4.0.1-botbaubble.2.44.0 (the expanded PLUGIN_DIR); an attended run, no --dispatch

## Decision Key

| Tag | Meaning |
|-----|---------|
| ASSUMED | Assumption made without explicit spec guidance (confidence: high/medium/low) |
| DEFERRED | Decision postponed — noted for later resolution |
| FLAGGED | Judgment call between alternatives — requires review |
| ABSENT | What was NOT done and why — forced reflection on gaps |
| INHERITED | Assumption carried forward from a prior task's output |

---

### T001: The registry stand-in and its shape units
**Started:** 2026-10-12T00:27:30Z | **Completed:** 2026-10-12T00:29:49Z

INHERITED: (none — first task)
ASSUMED: one loopback server for both registries, PyPI under /simple/ and /files/, npm under /npm/ (the npm registry URL carries the path, which npm, pnpm and uv-free installs accept) — keeps one process per cell (confidence: high)
ASSUMED: upload times as offsets from the stand-in's start, so "one day old" holds when the installer asks; the formats are R2's (PyPI microseconds Z, npm milliseconds Z) (confidence: high)
FLAGGED: the stand-in writes its own pid file and the tests stop it by that pid — chose that over any process-name match after I broke the standing rule while smoke-testing: a pkill -f whose pattern matched my own command killed my shell (exit 144). No stand-in was left running (checked through /proc) (confidence: high)
ABSENT: an uv check against the stand-in on the host (no uv here; the image's uv meets it in the e2e cells); the HTML-only index mode has no unit of its own yet (T005 uses it)
Verification: tests/unit/test_registry_standin.py 7 passed (3.14.8 venv), including the host's real pip 24.0 installing tl-old 1.2.0 into --target and npm 10.9.7 installing tl-left and @tl/scoped; pnpm 11.5.1 installed from it by hand and wrote a v9 pnpm-lock.yaml
PROCESS: T001's commit 1fa2714 was made before the deny-list ran; it was run on HEAD at once (PASS, 495 files, P1–P7 0/0). Every later commit goes through a helper that runs the deny-list on the staged tree first and refuses on anything but PASS

### T002, T003: versions (PEP 440, npm semver) and reading the command
**Started:** 2026-10-12T00:32:53Z | **Completed:** 2026-10-12T00:42:21Z

INHERITED: the stand-in and its catalog (T001); the spec's forms FR-5 to FR-9 (confidence: high)
FLAGGED: the whole tool was written as one file in this step (tools/bin/package-guard): versions, the parse, and the code T004 to T010 test next. The per-task boundary is the tests, not the file; chose one coherent first draft over stubbing functions to commit task by task (confidence: medium)
FLAGGED: an option the guard does not know, followed by a word that could be its value or a package, makes the command unreadable (refused with the confirm), never guessed — FR-9. The option tables are pip 24/25's, uv's and npm/pnpm's common ones; a missing switch shows up as a refusal the confirm passes, not as a silent pass (confidence: medium)
ASSUMED: a requirement's environment marker is not evaluated: the name is checked whatever the marker says. A name for another platform is checked though pip would skip it; the cost is a lookup, and an absent name refused that pip would not have installed (confidence: medium)
ASSUMED: a bare npm/pnpm install reads dependencies, optionalDependencies, peerDependencies and devDependencies (not with --omit=dev/--production); uv sync reads [project] dependencies and every [dependency-groups] group (confidence: medium)
ASSUMED: pip's "directory named like the package" case: a word is a local project only when it looks like a path, is an archive, or names a directory holding pyproject.toml or setup.py; npm reads a bare word as a registry name always, as npm-package-arg does (confidence: high)
ABSENT: environment markers; pip's --group with a path prefix is read but untested; yarn and bun (out of scope)
Verification: test_package_guard_versions.py 74 passed (PEP 440's ordering list and specifier examples; node-semver README's desugarings and pre-release rule, verbatim); test_package_guard_parse.py 62 passed. Two defects the units found: a direct reference ending in .whl read as a local archive (fixed: direct references first), and a test assuming no package.json above /tmp (a stray /tmp/package.json on this host, not mine; the test asks from / instead)

### T004: which registry the installer would use
**Started:** 2026-10-12T00:46:00Z (approximate: not read at the start; the previous commit's time) | **Completed:** 2026-10-12T00:43:16Z

INHERITED: Install from T003 (index flags, interpreter, scoped registries) (confidence: high)
ASSUMED: pip's order as read from pip 24.0's own configuration.py (global, user unless PIP_CONFIG_FILE exists, site, PIP_CONFIG_FILE, PIP_* env, CLI; [install] over [global]) (confidence: high)
ASSUMED: uv's order — --index, UV_INDEX, extra index URLs, the project's and uv.toml's [[index]] entries, then the default (--default-index, UV_DEFAULT_INDEX, UV_INDEX_URL, a default=true index, PyPI) — is read from uv's documentation, not measured: there is no uv on this host. The image's uv meets the stand-in in the e2e cells, which use one index (confidence: medium)
ASSUMED: npm's global npmrc is <realpath(node)>/../../etc/npmrc unless PREFIX or npm_config_globalconfig says otherwise (007 D-12's measurement); the builtin npmrc sits in npm's own package directory; pnpm also reads $XDG_CONFIG_HOME/pnpm/rc (confidence: medium)
ABSENT: npm workspaces' per-workspace .npmrc; a pip.conf [download] or [wheel] section (not an install); uv's index-strategy unsafe-best-match (the guard keeps first-index's order)
Verification: test_package_guard_registry.py 10 passed: pip user < site < PIP_CONFIG_FILE < env < CLI with a real venv layout and a plain prefix; uv's order and a user uv.toml; npm builtin < global < user < project (with ${VAR}) < env (any case) < CLI, and a scope's registry over --registry; credentials redacted for display and dropped from the request
