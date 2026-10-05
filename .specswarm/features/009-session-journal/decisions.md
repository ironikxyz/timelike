# Decisions Log — Feature 009
> Generated at 2026-10-05T06:08:02+00:00
> Spec: .specswarm/features/009-session-journal/spec.md

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
Pause file path (step 1e): `<repo>/../bridge/dispatch/pause-009.md` (the checkout path quoted as `<repo>/`, P2).

### T001: agentio's event gains agent, ppid, t_ms and ref (Tool.event_ref); run, snapshot and undo declare their pointers; 001's event schema and contract
**Started:** 2026-10-05T06:08:50Z | **Completed:** 2026-10-05T06:13:58Z

INHERITED: none — first task of this feature; the plan's R2 and the data-model's tool event (confidence: high)
FLAGGED: `t_ms` beside `ts`, not a millisecond `ts` — 001's tests and conform C7 read `ts`; a second field changes nothing that already reads the first (confidence: high)
FLAGGED: `ref` comes from the result's own data by a key the tool declares (`Tool(event_ref=(kind, key))`) — the pointer is what the tool reported; no second derivation that could disagree. A tool that failed (ToolError) has no result and so no `ref` (confidence: high)
FLAGGED: the schema's `ref` lists `log` (string) and `snapshot` (integer) with additionalProperties false — the repo's test schema checker (tests/unit/schema.py) supports neither type lists nor min/maxProperties, so "exactly one key" is stated in the description and enforced by agentio's construction, not by the schema (confidence: medium)
ASSUMED: `agent` is written only when TIMELIKE_AGENT matches the session id's character set; an invalid value is dropped silently rather than refused — a tool must not fail on a journal label (confidence: high)
ABSENT: an `agent` on other records (Adele's ledger, 004) — the ledger is read, never written (seam 3)
Verification: 3 new units in tests/unit/test_agentio.py (fields and agent validity, ref from data for str/int and absent for None/""/True/a failure, old lines valid and a foreign ref key invalid); the whole unit suite 1409 passed; ruff, format, mypy clean; host conformance over all 9 tools: pass
SCOPE: in (6 changed files)

### T002: the shell record — journal-exit.bash (new), the guarded step in 001's hook, the Dockerfile COPY; host tests J1–J6
**Started:** 2026-10-05T06:14:07Z | **Completed:** 2026-10-05T06:17:12Z

INHERITED: research R1's measured design (EXIT trap, builtins at start, exit status kept) (confidence: high)
FLAGGED: the trap sources a separate file (`. '/etc/timelike/journal-exit.bash'`) instead of an inline trap string — readable, lintable and testable on its own, and it defines no function (001's Q2) (confidence: high)
FLAGGED: the exit file is COPYed after the image's last RUN — the hook sets its trap only when the file is readable, so no build step (SHELL is bash -c, BASH_ENV set) writes /tmp/timelike, which 007's build step asserts absent (confidence: high)
FLAGGED: root (EUID 0) is not captured — root's commands are the operator's, and a root-owned /tmp/timelike/<session> would lock the agent out of its own events (agentio refuses a session dir it does not own) (confidence: high)
FLAGGED: at exit, a missing root is made 1777 and the session 0700, as agentio makes them (`mkdir`, `chmod`: forks at exit only, the first time) — the first prototype made the root 0775 with `mkdir -p`, which would have locked other users' sessions out of a shared root (confidence: high)
ASSUMED: existing e2e tests are unaffected: every run_in `bash -c` now appends to its session's shell.jsonl; the one test that inspects session directories (001's peer-agents SC-6) checks other sessions' names and content and root strays, none of which the record adds (read: tests/e2e/fixtures/sc6_check.py) (confidence: medium)
ABSENT: a hook-side redaction (research R5: read-side only); capture of `sh -c`, interactive shells and a command with its own EXIT trap (J5 asserts the last two as stated limits)
Verification: tests/host/test_shell_env_hook.sh 44 of 44 — J1 six exit cases (status kept, one entry each), J2 the double source gives one entry with agent and session, J3 modes 1777/0700/0600, J4 a hostile 5 KiB line with quotes, backslashes, a control byte, tab and newline is one valid JSON line cut at 4096 with its count, J5 the stated limits, J6 the hook and exit file with forking impossible (the probe can fail here: X2 caught the forking variant). A first run failed J1 on a test-helper bug (a counter inside a command substitution), fixed with mktemp. shellcheck clean on both files and the test
SCOPE: in (4 changed files)
