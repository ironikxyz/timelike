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
**Started:** 2026-10-12T00:42:28Z (not read at the start: f3f7f8a's commit time, the previous commit) | **Completed:** 2026-10-12T00:43:16Z

INHERITED: Install from T003 (index flags, interpreter, scoped registries) (confidence: high)
ASSUMED: pip's order as read from pip 24.0's own configuration.py (global, user unless PIP_CONFIG_FILE exists, site, PIP_CONFIG_FILE, PIP_* env, CLI; [install] over [global]) (confidence: high)
ASSUMED: uv's order — --index, UV_INDEX, extra index URLs, the project's and uv.toml's [[index]] entries, then the default (--default-index, UV_DEFAULT_INDEX, UV_INDEX_URL, a default=true index, PyPI) — is read from uv's documentation, not measured: there is no uv on this host. The image's uv meets the stand-in in the e2e cells, which use one index (confidence: medium)
ASSUMED: npm's global npmrc is <realpath(node)>/../../etc/npmrc unless PREFIX or npm_config_globalconfig says otherwise (007 D-12's measurement); the builtin npmrc sits in npm's own package directory; pnpm also reads $XDG_CONFIG_HOME/pnpm/rc (confidence: medium)
ABSENT: npm workspaces' per-workspace .npmrc; a pip.conf [download] or [wheel] section (not an install); uv's index-strategy unsafe-best-match (the guard keeps first-index's order)
Verification: test_package_guard_registry.py 10 passed: pip user < site < PIP_CONFIG_FILE < env < CLI with a real venv layout and a plain prefix; uv's order and a user uv.toml; npm builtin < global < user < project (with ${VAR}) < env (any case) < CLI, and a scope's registry over --registry; credentials redacted for display and dropped from the request

### T005 to T008: lookups, age, lockfiles and the plan, against the stand-in
**Started:** 2026-10-12T00:43:23Z (not read at the start: 6c266de's commit time, the previous commit) | **Completed:** 2026-10-12T00:45:20Z

INHERITED: the stand-in (T001), the parse (T003), the registries (T004) (confidence: high)
FLAGGED: lookups run on daemon threads under one deadline (the limit plus 1 s), not a ThreadPoolExecutor, whose threads are joined at interpreter exit: a registry that drips bytes under the socket timeout would otherwise hold the call past its limit (P2) (confidence: high)
FLAGGED: across several pip indexes, the release checked for age is the best across all of them (what pip would take); for uv and npm it is the first index that has the name. A name on more than one index is named in its line ("also on …") and not refused (spec D-6) (confidence: medium)
FLAGGED: a request no release satisfies (pip install x==9.9; npm's x@^9) is refused as "no matching release", not passed to fail inside the installer — chose refusing because the installer would only fail after asking the registry itself, and a hallucinated version is the same shape as a hallucinated name (confidence: medium)
ASSUMED: npm escapes a scope's slash as %2f, lowercase: read from the stand-in's log of the host's real npm 10.9.7 (T001), and now matched (confidence: high)
ASSUMED: a pip.conf, npmrc or lockfile that cannot be read is not a pin; its names are checked and a line says the file could not be read (FR-27) (confidence: high)
ABSENT: a registry dripping bytes slowly has no test of its own (the deadline is tested with a 30 s delay against a 1 s limit); npm documents above 64 MiB are untested (no such fixture)
Verification: test_package_guard_check.py 22 passed (3.8 s): absent vs 503/403/dropped/refused/unresolvable (never absent, "from this container"); a hung registry bounded at 1 s with the other name still checked; HTML-only and dateless registries give "age unknown"; newest release too new with its date and the release to pin, through pip, uv and npm; named and ranged releases checked for their own age; the age variable, including 0 and a bad value; pip's pre/yanked rules, npm's dist-tags; extra index; package-lock.json written by the host's npm 10.9.7 and pnpm-lock.yaml by pnpm 11.5.1, each pinning with zero guard requests in the stand-in's log; npm ci and pnpm --frozen-lockfile with none; uv.lock and pylock.toml in their documented formats; hashed requirements; an unreadable lockfile; the root found upward; plan lines in the command's order; no "did you mean". Three defects found and fixed: an npm range starting ~ read as a home path, the scope escape's case, and the plan's order

### T009 to T011: the tool as a process, the override record, the host's real installers
**Started:** 2026-10-12T00:45:27Z (not read at the start: f2d9b64's commit time, the previous commit) | **Completed:** 2026-10-12T00:53:00Z

INHERITED: the checks and the plan (T005 to T008); verify's lab pattern and its run-through-run (012) (confidence: high)
FLAGGED: pnpm's registry is asked of pnpm itself (pnpm config get), not read from npm's files. Measured on the host: pnpm 11.5.1 ignores npm_config_registry (in any case) and reads pnpm_config_registry and the project's .npmrc; older pnpm read npm_config_*. The first real-pnpm test caught the guard checking the stand-in while pnpm installed from registry.npmjs.org — the exact P001 failure. Asking pnpm costs a Node start per scope per call; if pnpm cannot answer, the npmrc chain is read with pnpm_config_* first, and the source names that it is a fallback (confidence: high)
FLAGGED: a lookup URL must be http or https; any other scheme (file:, ftp:) is "unreadable" and refuses. A registry URL comes from configuration the agent can write, and urlopen would read a local file (ruff S310 raised it) (confidence: high)
ASSUMED: one session event per call (rule 16): run's own event goes to a scratch root inside the session's scratch (package-guard/run), as verify does; the tool's ref.log is the override record when it overrides, else run's log (confidence: high)
ASSUMED: a command not found on PATH is handed to run unchanged, so its exit is what the shell's would be; the tool refuses only to guard itself (confidence: medium)
ABSENT: uv in these units (not on the host; the image's e2e); measured overhead (T017); the bare-command route (Item 24)
Verification: test_package_guard_tool.py 12 passed (the envelope valid against 001's confirm-envelope.schema.json; running its confirm string installs the too-new package and writes the record named by the event's ref.log; events valid against event.schema.json, one per call; a passing --yes records nothing; pip's own failure is the tool's exit; --dry-run runs nothing; a non-install passes its exit 42 through; a pip in the guard's own directory and a decoy python3/run/package-guard earlier on PATH are never run; --agent-info; --help within 40 lines; timelike-conform passes over package-guard and run on the host). test_package_guard_real.py 6 passed (the host's npm 10.9.7 and pnpm 11.5.1: absent refused with no tarball request and no node_modules; too new refused, the named old release installed, the confirm installing the newest and recording it; pinned with zero guard requests, then npm ci; npx --yes is not the guard's; npm init's create- package; pnpm add refused, passed, then pinned by its own lockfile). All 193 of the guard's units pass. ruff check and format clean over tools, tests, scan, bench, scripts; mypy --strict clean over 31 files (package-guard added to pyproject's list)
SCOPE-NOTE: pyproject.toml (mypy's file list) is outside tasks.md's named paths

PROCESS: the start times of T004, T005–T008 and T009–T011 were first written as composed values (00:46, 00:53, 00:59), each later than its own completion read from the clock — a record nobody measured. Corrected at 2026-10-12T00:54:20Z (read from the clock) to the previous commit's time, which is what the entries claimed to be. From T012 on, each start is read with date -u when the task starts

### T012 to T017: the e2e helpers and the four criterion files, the shellcheck list, the command reference, the measurement
**Started:** 2026-10-12T00:54:20Z (read from the clock) | **Completed:** 2026-10-12T01:00:24Z

INHERITED: the tool and its units (T001 to T011); the lane helpers (exec_in -e/-w, copy_into_container, container_tmpdir) (confidence: high)
FLAGGED: the stand-in runs inside the agent container on its loopback, started in the background by each cell with timelike's interpreter and stopped by its own pid (spec D-10): no compose service, no image change. The send says "a registry stand-in in the test profile"; this is a stand-in from timelike's own files, in the lane, without a compose profile — recorded in Item 24's not-blocking list (confidence: medium)
FLAGGED: the cells name package-guard in the command (as the envelope's confirm does). The bare pip install is Item 24's, so the criteria's "installing a package" is shown through the tool; the cells for the bare command are written after the ruling (confidence: medium)
ASSUMED: the registry reaches the installers by each one's ordinary configuration — pip by PIP_INDEX_URL, uv by UV_DEFAULT_INDEX, npm by the project's .npmrc — so the guard's own reading of those is part of what the cells test (confidence: high)
ASSUMED: the README's generated command reference is rewritten in this cycle (scripts/readme_reference.py --write: package-guard's section). Its drift test would fail otherwise, and CLAUDE.md's README rule says the same cycle. The intro's What and Status are NOT applied: their condition, all four slice-1 Automated criteria met, waits for Item 24's route (confidence: high)
FLAGGED: the tool's summary names the minimum age and its variable, so the announcement (generated from manifests) shows them with no change to 007's generator. The announcement's rule lines for package installs wait for Item 24: they would describe the bare-command route (confidence: medium)
ABSENT: running any cell in the image (no Docker here); uv on the host (its cells meet uv only in the lane); a bash -ic cell (the job-control lines are handled by drop_ic_notty_lines, and these criteria are not about the shell style); pnpm in the image (Item 24 Q3)
Verification: each cell's command and asserted string rehearsed on the host with bash -c against the stand-in (pip and npm; all matched, including running the npm refusal's confirm and reading the override back from events.jsonl); the in-container python snippets run on the host; shellcheck 0.11.0 clean over the Makefile's 88 files (four added); bats --count 5, 5, 4, 3 (17 cells); readme_reference --check current (14 tools); 215 units pass (the guard's, the stand-in's and the README reference's); ruff clean; mypy --strict clean (31 files). Measured: the guard adds about 300 to 350 ms to a passing pip or npm install of 1 or 5 packages on the host (research Measurements)

### T018: the cycle report, reboot.md, the contract's wording
**Started:** 2026-10-12T01:00:31Z (not read at the start: 71a1454's commit time, the previous commit; a composed time first written here was replaced before the report) | **Completed:** 2026-10-12T01:10:19Z

INHERITED: everything above (confidence: high)
ASSUMED: the README status block is not applied: its condition (all four Automated criteria met) waits for Item 24's route; only the generated command reference changed, which carries no <mark> (the operator's rule is for hand-written passages) (confidence: high)
ASSUMED: the contract's example envelope and plan words were brought in line with what the tool prints (they predated the final wording) (confidence: high)
ABSENT: implement step 10's score (unknown here); any cell run in the image
Verification: make test-host exit 0 (2208 passed, 13 skipped; 60/60, 57/57, 33/33)

### T019 to T026: Item 24's ruling built; lane 013s1-a2's items 1 and 2 (Cycle 1 addendum)
**Started:** 2026-10-12T17:23:03Z (read from the clock, when the findings were first read) | **Completed:** 2026-10-12T18:01:36Z (read from the clock)

INHERITED: the tool, its units and its 17 cells (T001 to T018); the ruling (bridge/feedback/15-20261012-015246-…, 01:52:46Z) and lane 013s1-a2's findings (bridge/feedback/15-20261012-034908-…, with the operator's acceptance of CVE-2026-88647 at 16:44:10Z) (confidence: high)
FLAGGED: the shim is POSIX sh (dash), not bash as Item 24's text proposed — chose sh because a bash script reads BASH_ENV, whose secret strip would change the real installer's environment (an exported NPM_TOKEN would be unset before npm runs), against condition 2; dash reads no startup file. Builtins only before the exec, as proposed. Measured: a BASH_ENV that unsets FOO leaves FOO for the real command (confidence: high)
FLAGGED: the gate's output is captured by the shim (command substitution: one fork, only for a call that may be an install) rather than a quiet mode added to agentio — chose capture because a tool that prints nothing would break the output contract's rule that every call ends with a verdict; on a pass the shim drops it, on anything else prints it (confidence: high)
FLAGGED: the shim sends a call to the guard when ANY argument is one of its installer's install words (npx: any non-option word), not only the subcommand position — chose the superset because parsing each installer's global options in sh would duplicate the guard's parser; a word in another position costs one guard call that answers "not an install". A unit reads the guard's own word sets and checks the shim names every one (confidence: high)
FLAGGED: with no real installer on PATH (pnpm before the agent installs it), the shim execs bash with 007's command-not-found handler rather than printing its own message — chose the handler so the answer, including "npm install -g pnpm", is the one bash gives without the shim; its first line names the shim's path and line 1, where bash would name the caller's (confidence: medium)
FLAGGED: Q3's in-image pnpm cell installs the stand-in's own `pnpm` package (a script that says it ran and answers no `pnpm config`), not pnpm — chose it because pnpm itself is not in the stand-in and the cell may not reach the public registry; what it shows is the shim reaching a pnpm the agent installed into ~/.local/bin, ahead of it on PATH, and pnpm never running on a refusal. pnpm's own forms stay the host's units with pnpm 11.5.1, named as such (confidence: medium)
ASSUMED: 00-timelike-path.sh now adds /opt/timelike/bin when it is absent anywhere in PATH, not only when it is not first: with the shims first, the old "first" test would prepend it again on a second sourcing. 007's idempotency unit passes (confidence: high)
ASSUMED: the README's status block applies now: its condition was "all four slice-1 Automated criteria met", and the send said to hold it only while Item 24 left a criterion unbuilt. Every criterion now has bare-name cells; whether they pass is lane 013s1-b's to say, and if one fails the block is wrong and is reverted (confidence: medium)
ASSUMED: the README sentence "the tools are on PATH at /opt/timelike/bin, ahead of everything else" became false with the shims, so it is corrected in the same cycle (the standing README rule), marked; nothing else outside the send's block changed (confidence: high)
ASSUMED: 007's units (test_agent_runtimes.py: the ENV PATH order and the login PATH after Debian's reset), 007's SC-6 runtimes cell and the agent-cannot-alter list are the declared changes to other features' tests; each now expects the shims first (confidence: high)
ABSENT: anything in the image (no Docker here): the shims, the 28 cells of the four criterion files, the pnpm cell, the PATH in the built image, the added time in the image; uvx (not in the image, so not shimmed); `-r /dev/stdin` (the installer reads it, the guard does not: the guard's stdin is closed); python -m pip, a venv's own pip, /usr/local/bin/pip (named gaps, slice 2's proxy)
Verification: make test-host exit 0 on the final tree (2239 passed, 13 skipped; env 60/60, hook 57/57, command-not-found 33/33); an earlier run failed only 007's two PATH-order units, updated as declared. Units: test_package_guard_shim.py 24 (pass-through with no guard call for eight non-install commands; environment, stdin and exit kept, a BASH_ENV that unsets a variable not read; a passing install is the installer's own output; refusals for pip, pip3, npm, npx and uv with the tool-form confirm and the decoy never run; a terminal caller; a decoy alias of the shims and a second link never run; not found → 127 with the handler's hint; a missing guard fails closed; the host's real pip through the shim; the guard's install words all in the shim); the tool's gate, override and shim-skip units; the announcement's. Rehearsed on the host with a pip whose pip.conf says user = true: each new cell's refusal, the user install into the cell's HOME, the confirm, the event readers' exact strings, the npm pinned cell's gate count, npx, and the pnpm cell (type -a -P, --version reaching the stand-in pnpm, pnpm add refused). Measured (research R11): about 0.9 to 1.05 ms added to a non-install call, about 233 ms to a passing install, on the host. ruff and mypy --strict clean; shellcheck clean over 89 files; scan units 192 passed. Commits 3542eb3 (T019–T022), f1814fa (T023–T025), and the records' commit
