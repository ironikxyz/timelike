# Decisions Log — Feature 010
> Generated at 2026-10-05T09:00:21+00:00
> Spec: .specswarm/features/010-services-interactive/spec.md

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
Pause file path (step 1e): `<repo>/../bridge/dispatch/pause-010.md` (the checkout path quoted as `<repo>/`, P2).


### T003: tools/bin/services — start (marker, readiness, died, not ready, holders), stop (tree, run's sweep, confirmation), list (unlisted), logs; agentio Tool(takes_command)
**Started:** 2026-10-05T09:01:22Z | **Completed:** 2026-10-05T09:05:15Z

INHERITED: research R1's measured tree discovery; run's helpers (proc_table, log_writers, signal_all, reap and its sweep constants), loaded from tools/bin/run; revision 13's rule 9 for services (code-track § Resume) (confidence: high)
FLAGGED: agentio gains `Tool(takes_command=True)`: argv is split at the first `--` before argparse — Python 3.12's argparse rejects options followed by `--` and a command on a positional (tried: "unrecognized arguments"), and agentio already avoids REMAINDER because its `--` handling differs between 3.12 and 3.14. A change to 001's module, additive, with a unit; not a pass-through (services' exits are its own) (confidence: high)
FLAGGED: "died" means the first process has exited AND no process of the tree remains — a wrapper that backgrounds the server and exits 0 is not reported dead while its server runs (P2: never report a state the tree does not have) (confidence: high)
FLAGGED: not ready in time stops the service (unless --keep) and removes its entry; a died service keeps its entry (with its exit) so `list` can mark it, until `stop` removes it (confidence: high)
FLAGGED: a command not found or not executable is a refusal (exit 1, cause named), not 126/127 — declaring pass-through would make conform's C6 run `services` wrapping `sh -c 'exit 42'` (spec amended at specify) (confidence: high)
FLAGGED: the died/not-ready result data uses `exit_status`, not `exit` — `exit` is agentio's reserved key (found by the first smoke run's internal error; contract amended) (confidence: high)
ASSUMED: readiness by port connects to 127.0.0.1, then ::1 (loopback only: seam 3) (confidence: high)
ABSENT: URL readiness and restarts (spec out of scope); the slot allocator and interactive sessions (slice 2)
Verification: host smoke runs with real processes — a server with a setsid grandchild ready by port (the port accepted), a second start on the held port refused naming `service web in session s1, pid P`, an early exit `died before ready (exit 3)` with its log line, a 1 s timeout exit 124 and stopped, `stop --all` exit 4 with the confirmation envelope then exit 0 with --yes, `stop --dry-run` naming the 3 processes (the setsid escapee included), `stop` leaving no marker process in /proc; test_agentio (1 new unit for takes_command), test_conform and test_conform_violations pass; ruff, format, mypy strict clean; host conformance: 11 tools pass
SCOPE: out — tests/unit/test_agentio.py (1 of 3 changed files) (task has FLAGGED: yes)

**Paused at 2026-10-05T09:06:07Z** (read from the clock): T003's SCOPE record is `out` (tests/unit/test_agentio.py) on a task with a FLAGGED decision (the agentio `takes_command` change). That is code-track's pause cause 4, which takes no confidence judgment. Pause file: `<repo>/../bridge/dispatch/pause-09.md`, naming readings (a) accept, (b) revert and put options before NAME, (c) another route. tasks.md was not amended after the fact to make the record read `in`. The T001/T002 delegates' files are left uncommitted until the answer.

**Resumed at 2026-10-06T16:52:34Z** (read from the clock): pause-09 answered (a) by the mentor (`../bridge/feedback/09-20261006-162949-takes-command-in-agentio.md`), pause file deleted. Its three conditions:
1. **Declared** in the cycle report's `changed_other_features` (T006): `tools/agentio/agentio.py` (`takes_command`) and `tests/unit/test_agentio.py`.
2. **Written into 001's contract text** (this commit): `output-contract.md` § Invocation surface, one paragraph: a tool may take a command after the first `--` without passing its exit through (`takes_command`), distinct from `passes_exit`.
3. **The died verdict fixed** to the contract's `last N log lines below` (this commit), and the not-ready verdict to the same form. The T001 delegate's test was right; it passes now (28/28).

### T001: tests/unit/test_services.py (delegated, from the contract): 28 tests with real processes
**Started:** delegated,_written_after_b3ac307_(its_start_was_not_read_from_a_clock) | **Completed:** 2026-10-06T16:53:35Z

INHERITED: the contract and research; `services` as committed at T003 and fixed at the resume (confidence: high)
FLAGGED: every fixture is a real process (http.server on a free port, sh trees with a setsid grandchild, early exits, a never-ready sleep), and every claim is checked in /proc, on the port and in the registry file — a teardown SIGKILLs every process carrying the test's own session marker, and none was left after the runs (confidence: high)
FLAGGED: its one failure on the tool as committed (the died verdict's `last N of M` against the contract's `last N`) was a tool deviation; fixed at the resume (`ae4bb5e`, the mentor's condition 3) and now 28/28 (confidence: high)
ASSUMED: the delegate's settlements: global flags before the subcommand, the data model's registry shape, `exit_status` for a died start's status (agentio reserves `exit`), stop's `pids`/`survivors` keyed by service name (confidence: medium)
ABSENT: the survivors outcome (needs a process that hides from all three nets), a holder another user owns, the ::1 fallback, rule 3's cut in `logs` — named by the delegate as not tested
Verification: 28 passed (14 s); ruff clean
SCOPE: in (1 changed files)
