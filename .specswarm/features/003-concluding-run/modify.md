# Modification: Feature 003 — Concluding run (`run`)

Append-only: one section per modify cycle.

---

## Cycle 2 — `bridge/sends/03-rev1-20261004-183704.md`

**Status:** Active | **Created:** 2026-10-04 | **Impact analysis:** `impact-analysis.md` § Cycle 2 |
**Spec:** `spec.md` § Slice 1 | **Contract:** `contracts/run-cli.md` § Slice 1

### Summary

Build slice 1 (natural): `run` names a memory kill and a full disk as causes, and redacts known secret
formats from what it shows and what it stores. The rule set is one file shared with `make scan`'s
gitleaks. The slice-1 criteria were in prompt revision 1 from the start (row 4: nothing to audit), so this
is added work, not a superseded body.

### Functional changes

**F001: the memory cause** (spec FR-25 to FR-28)
- **Current:** a command killed by the OOM killer reads `exit 137 (command killed by signal 9 (SIGKILL))`
  or `command exited 137`.
- **Proposed:** `run` reads its cgroup's `memory.events` `oom_kill` count before and after the command.
  When it rose and the command did not succeed, the cause is `memory`, and the verdict names the limit
  (`memory.max`) and the peak (`memory.peak`). Unreadable files make the memory part `unknown`, named.
- **Breaking:** no. The exit code still passes through (137).

**F002: the disk cause** (FR-29 to FR-32)
- **Current:** a write failing on a full filesystem reads as the command's own exit.
- **Proposed:** when the command did not succeed, `run` checks the scratch and workspace filesystems
  (`statvfs`) and the log's text for the ENOSPC message. Then the cause is `disk`, and the verdict names
  the filesystem (its mount point) and its free space. A log on a full scratch filesystem is said to be
  possibly incomplete. The log-creation error names the free space too.
- **Breaking:** no.

**F003: redaction** (FR-33 to FR-40)
- **Current:** the log, the shown lines and the header hold what the command printed and was given.
- **Proposed:** the rule set in `/etc/timelike/redaction.toml` (gitleaks' format, 18 provider rules
  from its defaults, each tagged with a rule-15 type) is applied after the command ends. The log is
  replaced by its redacted copy when anything matched. The shown lines come from it, and the header and
  the event's arguments are redacted too. The verdict counts what was redacted. A missing or broken rule
  file withholds the output and says why.
- **Breaking:** no. One slice-0 edge case changes (a detached child's later output, when the log was
  rewritten), declared in the spec.

### Data model changes

**D001:** JSON `data` gains `memory` (`state`, `limit_bytes`, `peak_bytes`, `oom_kills`,
`command_max_rss_bytes`, `reason`), `disk` (per filesystem: `role`, `path`, `mount`, `free_bytes`,
`full`) and `redaction` (`state`, `counts`, `rules`, `log_rewritten`). No stored format changes.

### API/contract changes

**A001 (`run`):** `cause` gains `memory` and `disk`. The verdict gains the cause words and
` · redacted N (type n, …)`. The manifest gains `redaction_rules` and `disk_full_bytes`.
**A002 (agentio, 001's contract):**
- `redact_text()` and `load_redaction_rules()`, rule 15's rule set;
- a pass-through exit is admitted for any `cause` when `command_exit` equals the exit;
- `Context.event_args` lets a tool record its arguments redacted.

Existing tools are unchanged in behaviour.

### Testing strategy

- **Regression:** `test_run.py`, the agentio units, `make test-host`; the e2e suite in the mentor's lane.
- **New units:** listed in `impact-analysis.md` § Cycle 2, written from the contract by a delegate, before
  the code.
- **New e2e:** one file per automated criterion. Memory and disk use throwaway containers with `--memory`
  and `--tmpfs`. Every secret-shaped value is generated at run time.

### Tech stack compliance

Compliant. cgroup v2 and gitleaks are approved, and gitleaks' note names this sharing. `tomllib` is stdlib.

### Steps 7–8 of `/specswarm:modify`

They are not run here. The dispatch sequence prescribes `/specswarm:plan`, `/specswarm:tasks` and
`/specswarm:implement --dispatch` next, and `tasks.md` gains a Phase for Cycle 2 there, appended, not
overwritten.
