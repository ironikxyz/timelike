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
