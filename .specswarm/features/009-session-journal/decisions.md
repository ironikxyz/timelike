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

### T005: tools/bin/journal — read, order, link, tail, sessions and agents, the ledger, redaction
**Started:** 2026-10-05T06:19:27Z | **Completed:** 2026-10-05T06:24:13Z

INHERITED: the event's agent/ppid/t_ms/ref — from T001; the shell record's shape and limits — from T002; the contract (confidence: high)
FLAGGED: a shell line whose only child is the tool its first word names is folded into that tool's entry (styled bash -c / -lc, `collapsed: true`); any other shell line is shown with its tools nested under it — chosen over always showing both (the "written twice" the seam forbids, as seen) (confidence: high)
FLAGGED: redaction fails closed — when rule 15's rules cannot be loaded, every command and pointer is shown as `[withheld: redaction rules unavailable]` and the verdict says why, rather than printing raw lines (confidence: high)
FLAGGED: a ledger row is linked to an `adele` event of the same session when its second overlaps the call; otherwise it is a grant entry of its own, its outcome in the exit column (contract) (confidence: medium)
FLAGGED: the cut's `more:` is `journal --all …` for the default tail and `journal -n <N+20> …` after `-n N`, with the session/agent/ledger-file flags kept (a piped `--ledger -` cannot be repeated by a pasted command, so it is not) (confidence: medium)
ASSUMED: JSON `lines` are the entry lines without the date line and the label (contract § JSON); text keeps both (confidence: high)
ABSENT: pid-reuse beyond the time window, clock ties within a millisecond (R3 says how they order; no test can force them)
Host observations, not defects:
- A shell whose stdin is a network socket: Debian/Ubuntu bash takes its remote-shell startup path (bashrc, no BASH_ENV), so neither 001's hook nor the journal's trap runs. This instance's own Bash tool has such a stdin; 001's host test already runs every case with stdin from /dev/null. In the image, `docker exec` gives /dev/null or a pipe.
- A fake token of a repeated pattern (low entropy) is not redacted: the gitleaks rule's entropy floor excludes it, as for `run`'s redaction (feature 003); a random one is ([REDACTED:token], smoke run).
Verification: tests/unit/test_journal.py (T003's 43) all pass; 40 passed on the first run, 3 settled (1 tool fix: JSON lines undecorated, per the contract; 2 test errors: rule 2's uncut ending, rule 3's section label before the cut); a host smoke run with real `bash -c` / `bash -lc` and the hook: collapse, nesting, the tail's cut, `more:`, the artefact, the agent filter; mypy strict and ruff clean; host conformance: 10 tools pass
SCOPE: in (1 changed files)

### T003: tests/unit/test_journal.py (delegated, from the contract): 43 cases; 3 first-run failures settled
**Started:** delegated,_written_after_b420e1d_(its_start_was_not_read_from_a_clock) | **Completed:** 2026-10-05T06:24:27Z

INHERITED: the contract, data-model and research; the real writers (T001's event fields, T002's trap) for fixtures (confidence: high)
FLAGGED: fixtures by running the real tools and real `bash -c` / `bash -lc` with the hook; inside shells a tool is reached through a two-line `sh` shim that `exec`s the repository's tool, so the pid the shell forked is the tool's and its event's ppid is the shell's pid, as in the image (confidence: high)
FLAGGED: three contract inconsistencies the delegate found, settled in the contract and spec: an unreadable events/shell record is exit 0 and named (the refusal table over the manifest's wording); FR-7's `start_ms` is `start_us` (the record's real field); verdict counts are of the entries shown (confidence: high)
FLAGGED: two of its assertions were wrong against 001's contract and were corrected here, not in the tool: uncut text ends on its last entry (rule 2, revision 6), and a cut opens with rule 3's section label (confidence: high)
ASSUMED: left unpinned by the delegate, deliberately: a nested child's JSON style, an agentless entry's agent value, the scope when a session holds fewer entries than the tail (confidence: medium)
ABSENT: the `password` type (no rule in redaction.toml carries it), a PEM in a command line, clock ties, pid reuse — named by the delegate as not tested
Verification: 43 passed; ruff and format clean
SCOPE: in (1 changed files)

### T004: e2e (delegated) — SC-1 to SC-4 and the name and manifest, 16 cells; dry-run on the host stand-in
**Started:** delegated,_written_after_b420e1d_(its_start_was_not_read_from_a_clock) | **Completed:** 2026-10-05T08:34:56Z

INHERITED: the contract and the real writers; helpers.bash; 008's files as the model (confidence: high)
FLAGGED: every cell has its own session (`j<N>-<run id>-<check>-<style>`, the run id from the file's container_tmpdir) and first checks it has no records — no cell reads another's, the lesson of lane batch-a (confidence: high)
FLAGGED: SC-4's overlap is made, not hoped for: a runner-side gate puts a2's s1 work inside a1's, and the overlap is asserted (confidence: high)
FLAGGED: SC-3 uses 30 invocations (the spec's SC-3), and the earlier tail is checked field by field against the `more:` command's own output (confidence: high)
ASSUMED: an entry without an agent may carry `agent: null` in JSON; FR-10's `-` is the text display (confidence: medium)
ABSENT: tty and pty cells (journal is a reader for pipes and terminals alike; the criteria name no terminal mode)
Verification: shellcheck -x clean over the five files. Host stand-in (advisory): as committed, only the manifest cells pass — the host has no /etc/timelike/redaction.toml (the journal withholds every command, failing closed), no hook (no shell entries) and the stand-in's own PATH (type -a). In a scratch copy whose helpers.bash supplied the rules file, the hook and the trap file: SC-1 4/4, SC-3 2/2, SC-4 bash -c, the manifest 2/2 pass; what remained failing was only the `bash -lc` style (the stub runs -lc as -c) and the `type -a` path — image-only by design. Nothing of the dry runs was left in /tmp
SCOPE: in (5 changed files)
