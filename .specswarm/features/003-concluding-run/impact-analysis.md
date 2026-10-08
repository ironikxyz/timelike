# Impact Analysis: Modification to Feature 003 (concluding run)

Append-only: one section per modify cycle. Cycle 1 was built by `/specswarm:specify` and needs none.

---

## Cycle 2 — `bridge/sends/03-rev1-20261004-183704.md` (prompt 03 revision 1, discovery revision 12; slice 1)

**Feature:** Concluding run (`run`) | **Analysis date:** 2026-10-04 |
**Command:** `/specswarm:modify 003 --from-send bridge/sends/03-rev1-20261004-183704.md --dispatch` on
`modify/003-slice-1` (cut from `master` `aa8127d`), specswarm **4.0.1-botbaubble.2.35.0** (`4ff8dcb`)
loaded: the expanded command named that cache path. Dispatch batch `20261004-183704`, prompt 1 of 8.

### Provenance (modify Step 2)

The installed `provenance-inputs` and `provenance-row` blocks, run from the 2.35.0 file with `ARGUMENTS`
as a variable: `FEATURE_NUM 003` (from the branch `modify/003-slice-1`), `PROMPT_VIA from-send`,
`SOURCE_SEND bridge/sends/03-rev1-20261004-183704.md`, `OLD_SOURCE` = `NEW_SOURCE` =
`plan/.discover/prompts/03-concluding-run.md`, `PROMPT_REV 1`, `AUDITED [1]`, `N 1` → **row 4**: revision
1 is already audited. Nothing is appended in Step 9.

The slice-1 criteria are not a revision's additions. They were in prompt revision 1 from the start, marked
*(slice 1)*, and the slice-0 spec carried them as out of scope. The send asks to record them as added work
(INCOMPLETE, not SUPERSEDED), and that is what this cycle does: nothing the slice-0 body says becomes
false, except one edge case this cycle's own design changes (below, declared).

### What this cycle changes

The send's slice-1 scope, 4 criteria (3 automated, 1 Manual):
1. A command killed by the container's memory limit gets a verdict naming the limit and peak usage.
2. A command that fails because the scratch or workspace filesystem is full gets a verdict naming the
   filesystem and its free space.
3. Values matching known secret formats are shown and stored as `[REDACTED:<type>]`, in the displayed
   output and in the saved log.
4. DEMO D12 (Manual): the memory verdict instead of a bare exit 137.

And the send's three seams:
1. **Why a command died:** the cause is read from cgroup v2 (`memory.events` `oom_kill`, `memory.max`,
   `memory.peak`) and from the filesystems themselves (`statvfs`). Unreadable means `unknown`, named,
   never a guessed cause.
2. **Redaction meets rule 15:** agentio's `redact()` is reused. What counts as a secret is the **pattern
   set**, kept in one file in gitleaks' own config format and read by both `run` (through agentio) and
   `make scan`'s gitleaks step. A rule set in `run` alone would diverge.
3. **The JSON line cut** (revision 12) already applies to `run`'s lines through agentio. Not
   re-implemented.

### Affected components

| Component | Impact | Notes |
|---|---|---|
| `tools/bin/run` | High | The cause (memory, disk), the redaction pass over the log, the redacted header and event arguments, the verdict additions, manifest fields |
| `tools/agentio/agentio.py` (001's module) | Medium | The shared rule loader and `redact_text` (rule 15's rule set); a pass-through exit admitted for any cause with `command_exit` equal to the exit; the event's arguments may be supplied redacted by the tool |
| `image/rootfs/etc/timelike/redaction.toml` (new) | Medium | The shared rule set: gitleaks config format, `[extend] useDefault = true`, 18 provider rules copied byte for byte from the pinned gitleaks v8.30.1 defaults, each tagged `redact:<type>` |
| `image/Dockerfile` | Low | One `COPY` of the rule file to `/etc/timelike/redaction.toml`. Changes the agent image, so `make scan`'s inputs |
| `scan/scan.sh` | Low | gitleaks reads the same file (`--config`). Checked with the pinned binary on this host: the same leak is found with the same rule id, now carrying its tag, and timelike's history still has 0 findings under both configs |
| 001's `contracts/output-contract.md` | Low | Rule 15 names the rule file. The pass-through paragraph admits an exit outside the vocabulary for any `cause` when `command_exit` equals it, which the paragraph's own "later causes (for example `memory`, `disk`) are added without changing its shape" already foresaw |
| `contracts/run-cli.md`, `spec.md`, `research.md`, `data-model.md` | Low | Declared, appended slice-1 sections |
| `tests/unit/test_run.py`, `tests/unit/test_agentio*.py` | Low | New units. No existing expectation changes |
| `tests/e2e/` | Low | Three new files, one per automated criterion. The memory and disk cells use throwaway containers (`--memory`, `--tmpfs`), the established pattern of 001's SC-8 |
| `timelike-conform` | None | C6 still checks `sh -c 'exit 42'`, which is `cause: command` |
| Other features' tools | None in behaviour | They gain nothing unless they call the new helpers. Their exit validation is unchanged for `cause: command` |

### Breaking changes: no

- The verdict gains optional parts (` · redacted N (…)`, the memory and disk cause words). The line's
  shape is the slice-0 shape: `exit E (cause words) · D s · N lines · log P`.
- `cause` gains `memory` and `disk`, as the slice-0 spec (FR-18) and 001's contract promised.
- JSON `data` gains `memory`, `disk` and `redaction`.
- **One slice-0 edge case changes, declared:** *"A detached child is still writing when `run` returns.
  Its output keeps going to the same log."* That still holds when nothing was redacted, which is when
  the log is left as written. When something was redacted, the log is replaced by its redacted copy,
  and a detached child's later output goes to the replaced file, which is no longer on disk. The verdict
  says so. Storing a secret to keep a background process's later output is the worse trade (P4, G9).

### Risk: medium

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| A redaction rule misses a secret, or redacts a non-secret | Medium | Medium | The rules are gitleaks' own, with its entropy floors and allowlists applied the same way. Units test each rule on generated values. The set is named in `--agent-info` |
| An OOM kill of another process in the same container is read as this command's | Low | Low | The verdict says "an OOM kill in this container during the command". Peer agents in one container share one cgroup, and nothing finer is readable without delegation |
| `memory.peak` is the container's peak since it started, not the command's | Certain | Low | Named "container peak". The command tree's largest resident set (`getrusage`) is in JSON beside it |
| Rewriting a large log costs time | Low | Low | One streaming pass, only when a rule's keyword occurs. Measured in the units |
| The rule file is missing or broken in the image | Low | High | Fail closed: the output is withheld and the verdict names why. A unit and an e2e cell check the image's file loads |
| Adding the file changes gitleaks' findings in `make scan` | Low | High | Measured above with the pinned binary: 0 findings before and after. Test fixtures build secret-shaped values at run time, never as literals in a tracked file |

### Testing requirements

- **Regression:** `tests/unit/test_run.py` and `test_agentio*.py` unchanged and passing; `make test-host`;
  every earlier e2e file in the mentor's lane.
- **New units:** the cgroup reader (limit, peak, `oom_kill` before and after, unreadable files); the disk
  check (statvfs, mount resolution, the ENOSPC text); the rule loader (valid, missing, broken, a bad tag);
  `redact_text` per rule (generated values), entropy floors, allowlists, multi-line private keys keeping
  the line count; the log rewrite (only when needed); the redacted header and event arguments.
- **New e2e** (one file per criterion, named after its distinguishing text, `bash -c` and `bash -lc`).

### Tech stack compliance

Compliant. cgroup v2 is approved for budget verdicts (`tech-stack.md`: "`memory.max`, `memory.events` …
are the source of truth"). gitleaks is approved, and its note says it "shares its rule set with `run`'s
output redaction (feature 03)": this cycle builds exactly that. `tomllib` is Python stdlib. No new tool.

### Recommendation

Proceed.
