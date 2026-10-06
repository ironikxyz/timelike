# Decisions Log — Feature 012
> Generated at 2026-10-06T17:58:18+00:00
> Spec: .specswarm/features/012-verify-changed/spec.md

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
Pause file path (step 1e): `<repo>/../bridge/dispatch/pause-012.md` (the checkout path quoted as `<repo>/`, P2).

### T003: tools/bin/verify — test (through run's JSON and log; pytest, jest, vitest, go, cargo; exit passed through) and changed (git change set, symbols dependents per file, lint/type-check of changed files, not-run fails the call)
**Started:** 2026-10-06T17:58:24Z | **Completed:** 2026-10-06T18:10:54Z

INHERITED: research R1–R6 and the recordings committed at plan (6ba52b8); run's JSON result (log, verdict, cause, command_exit, redaction) from 003; symbols' `dependents` JSON (path, depth, via) from 011 at 6d523d4 (confidence: high)
FLAGGED: the subcommand is read from the command, not by argparse — agentio ends a pass-through tool's options at the first plain word (and conform's C6 probe runs `verify --json sh -c 'exit N'`), so `verify CMD` is the same as `verify test -- CMD`, and a command named test or changed goes through `verify test -- …`; contract amended and both delegates told before they finished (confidence: high)
FLAGGED: the probe is `["true"]`, not `["changed", "--dry-run"]` — conformance probes outside a repository, where `changed` is a usage error on stderr, which fails C3/C4; manifest `dry_run` is false because agentio's field is rule 8's for destructive tools, and `--dry-run` belongs to `changed` (confidence: high)
FLAGGED: run's line count and its plain `(command exited N)` are dropped from verify's verdict (every other part kept as run words it), so the log path survives rule 13's line cut; unknown format keeps run's verdict whole, as FR-4 says (confidence: medium)
FLAGGED: a deleted Python file's importers are found by text (absolute imports), because 011 resolves imports only to files that exist; other languages say so in `untested` (confidence: medium)
ASSUMED: untracked paths under __pycache__/.pytest_cache/.mypy_cache/.ruff_cache are not changes — verify's own runs create them in a workspace that does not ignore them (confidence: high)
ASSUMED: go counts are top-level tests and the leaf subtest is the reported failure; cargo sums every `test result:` line; jest/vitest "rejects text" is located at the test file's frame, not math.js (R3) (confidence: high)
ABSENT: relative Python imports for deleted files; selecting by symbol; JUnit/JSON reporters; flaky detection (slice 2)
Verification: host smoke run — every one of the 14 recordings read through `verify test -- cat`, counts and locations as the generator wrote them; a script exiting 37 passed through (cause command); changed on a committed pytest project after an edit to app/models.py: tests/test_models.py (imports app/models.py) and tests/test_orders.py (imports app/orders.py, which imports app/models.py), pytest on those two only (3 failed, 9 passed), ruff and mypy on app/models.py only; no change → exit 0 nothing selected; tools off PATH → three `not run`, exit 1; outside a repository and an unknown --since → exit 2 on stderr. T001's tests (written from the contract) then found 9 deviations, fixed before T001's commit (listed there). ruff, format and mypy strict clean.
SCOPE: in (1 changed files)

### T001: tests/unit/test_verify.py (delegated) — every recording against the generator's counts and locations, identification, run's failures, redaction unavailable, the change set and selection on real git repositories, not-run, the manifest
**Started:** 2026-10-06T17:58:24Z | **Completed:** 2026-10-06T18:11:15Z

INHERITED: the contract (amended for the bare `verify CMD` form and the manifest before the delegate finished), make-project.sh and the 14 recordings (confidence: high)
FLAGGED: expected values come from the generated projects (counts from the generator's header, lines by locating needles in the generated text), never from verify's answers (P005); the recordings are replayed through the real `run` with the recorded exit (confidence: high)
ASSUMED: run's own failure is tested with verify copied beside a stub `run`; every other case uses the real run, symbols and search, copied with a host interpreter shebang as test_conform does (confidence: high)
ABSENT: real jest, vitest, go and cargo runs (not on the lane's unit step; their real output is replayed); tsc and eslint under `changed` are replayed by stub linters on PATH printing the recordings
Verification: the delegate's tests ran 52 passed / 9 failed against T003's first version, and all 9 were tool deviations from the contract, fixed in tools/bin/verify (in T003's commit `d3befbc`, made after these findings, 2026-10-06):
1. no "N failed so far" on a timeout (contract § test, timeout row);
2. the --limit omission named agentio's artefact, not run's log (now a Cut over whole blocks with run's log as the full output);
3. assertion lines were still in JSON when redaction was unavailable (R2);
4. three: run missing, failing or unreadable was a stderr error, not an `internal` result (contract § test);
5. a deleted file was not used to find dependents (spec edge case; now by text for Python);
6. a passing test step's state was `400 passed`, not `passed` (FR-10);
7. `selected.untested` shape — here the CONTRACT was amended to `[{path, reason}]` and the test's assertion changed to compare paths (the reason is the point).
One more assertion amended: the SC-1 text verdict's regex required a part between the duration and the log path; verify now drops run's line count (T003, FLAGGED), which the contract's example already showed (`exit 1 · 0.6 s · log …`).
After the fixes: 61 passed (scratch venv, Python 3.12.3). ruff and format clean.
SCOPE: in (2 changed files)

### T002: e2e (delegated) — SC-1 to SC-4 and the name and manifest, bash -c and bash -lc, each cell its own workspace and session; real pytest, ruff and mypy in the image through uv wrappers at the pins.env versions
**Started:** 2026-10-06T17:58:24Z | **Completed:** 2026-10-06T18:18:31Z

INHERITED: the contract as amended at T003 (bare `verify CMD`, the manifest, changed outside a repository), make-project.sh and the recordings (confidence: high)
FLAGGED: `install_uv_tool_wrappers DIR` (tests/e2e/helpers.bash) writes pytest, ruff and mypy wrappers that run the REAL tools via the image's uv at PYTEST_VERSION, RUFF_VERSION and MYPY_VERSION read from pins.env on the runner side — the image has none of them (the send's "pytest runs in the image" is false, R1); needs PyPI from inside the agent container, which the lane has proved only for a throwaway container of the same image (confidence: medium)
FLAGGED: jest, vitest, go and cargo are not in the image, so SC-2 replays their recorded output through `verify test -- cat FILE` (real output, recorded on the host, sources in the .source sidecars); pytest runs for real (confidence: high)
ASSUMED: each wrapper-using file warms the tools once in setup_file under a 300 s bound, so timed cells start warm (confidence: medium)
ABSENT: any run in the image (no Docker here); the two `type -a` cells can only pass there
Verification: shellcheck -x clean over the five files, helpers.bash and tests/fixtures/verify/*.sh. Host stand-in (advisory; a scratchpad copy whose install_uv_tool_wrappers links this host's pytest 8.4.2, mypy 2.4.0 and ruff 0.16.7 instead of uv): first run 30 of 38; the delegate's findings and mine, fixed before this commit (2026-10-06):
1. two header assertions assumed `verify: test …`; the target is the command, shell-quoted, as run's is (contract amended; the cells now expect `verify: pytest [pytest]` and `verify: sh -c … [format unknown]`);
2. SC-3's edit left one blank line after `import os`, so a ruff selecting isort (the host's did) adds I001; the edit now leaves two, so the only finding is the unused import whatever ruff selects;
3. the changed verdict and the unknown-format verdict could be cut by rule 13 at 200 columns, taking step results or the `format unknown` clause with them. Fixed in tools/bin/verify: the changed lead is shorter ("N changed files · M test files importing a change, directly or through one file: a superset", "(text-based outside Python)" only when a non-Python file changed), and the unknown clause comes FIRST, then run's verdict with its line count dropped. Spec FR-4 and the contract amended; one unit assertion and one e2e check of the old order amended with them.
After the fixes: stand-in 36 of 38, only the 2 type -a cells not ok (image-only); units 61 passed.
SCOPE: in (8 changed files)

### T004: pyproject.toml (verify in the ruff and mypy lists), Makefile (SHELLCHECK_FILES: the five e2e files and tests/fixtures/verify/*.sh), README.md (a verify section)
**Started:** 2026-10-06T18:18:41Z | **Completed:** 2026-10-06T18:19:13Z

INHERITED: tools/bin/verify, its e2e files and the fixture scripts — from T001–T003 (confidence: high)
ASSUMED: the fixture generator and recorder go in the shellcheck list like any repository shell script; record.sh is host-only and never run by the lane (confidence: high)
ABSENT: the e2e files are NOT added to any per-feature run list beyond SHELLCHECK_FILES — tests/run.sh runs every tests/e2e/*.bats, as for 008–011
Verification: ruff check and format clean over the repository (host ruff 0.16.7; the lane pins 0.16.9); mypy strict: 26 files, no issues; shellcheck over the Makefile's 75 files: clean
SCOPE: in (3 changed files)

### T005: host lane — lint, units with coverage, make test-host, conformance, the e2e stand-in, start-up; three tool fixes it found (one event per call, conftest, start-up), 12 unit cases added
**Started:** 2026-10-06T18:19:48Z | **Completed:** 2026-10-06T18:46:30Z

INHERITED: every earlier task's files (confidence: high)
FLAGGED: host conformance failed verify on C7 — each call appended 2 events (verify's, and the nested run's; symbols adds one per changed file). Fixed without touching 001's agentio: run and symbols get TIMELIKE_SCRATCH_ROOT=<scratch>/<session>/verify, so their logs, index and events stay inside the session's scratch and the journal holds verify's one event (ref: run's log). A unit now asserts one event per call whatever verify runs. The cost: symbols' index for verify is separate from the agent's own, built once per session (confidence: medium)
FLAGGED: `verify --help` measured p95 114 ms against quality-standards' 100 ms; dataclasses (12 ms of import, through inspect) replaced by slotted classes and shutil deferred: p50 89 / p95 93 ms. The rest is compiling the 1,460-line script (~20 ms, as every tool here pays) (confidence: high)
FLAGGED: the traced run had 1 failure outside this feature: tests/unit/test_bench_runner.py::test_totals_and_endings_match_rb4[git-inspect-timelike] ("setup failed: hung" under coverage tracing). Untraced, the whole test passed 8/8 three times (4.5 s); bench is untouched by 012. Recorded as a tracing/load timing artefact, as 011 recorded adele's, not hidden (confidence: medium)
ASSUMED: runners not on this host (vitest, jest, go, cargo) are exercised in changed mode by stubs printing their REAL recordings, as T001's lint stubs do: what those cases test is the selection, the command and the step state, not the parser (confidence: high)
ABSENT: the Docker lane (the mentor's); a go build-failure recording (the parser's `[build failed]` branch is untested — no real recording was made, and a written one would prove nothing, P005); the >50-file batched dependents path
Verification:
- traced units (before the 12 cases and the fixes): 1626 passed, 1 skipped, 1 failed (the bench timing above), 739 s; coverage TOTAL 94%, verify 85%
- 12 cases added (vitest and jest steps with the workspace's runner, go test on the package, cargo test in the crate, a missing JS runner, a changed conftest, a step past its limit → 124, --timeout validation ×3 forms, real pytest skipped and error counts, one event per call); the conftest case found a real defect (conftest.py under tests/ was handed to pytest as a test file) — fixed. verify 90% from its own tests (traced); units 73 passed
- make test-host (before the final fixes): passed — units 1639 untraced, files 60/60, hook 44/44
- lint: ruff check and format clean (host ruff 0.16.7), mypy strict 26 files, shellcheck over the Makefile's 75 files
- conformance on the host, all 13 tools: pass (after the C7 fix)
- e2e host stand-in (advisory): 36 of 38, the 2 type -a cells image-only
- start-up on the host, 20 runs each, every exit asserted 0: `verify --help` p50 89 / p95 93 ms (114 before); the probe `verify --json true` (through run) p50 186 / p95 191 ms
SCOPE: in (2 changed files)
