# Impact Analysis: Modification to Feature 007 — Announcements and discovery

> One section per modify cycle. Feature 007's first modify, so this file starts here.

# Cycle 2: revision 13 recorded; the workspace clause struck (send `bridge/sends/04-rev13-20261008-095251.md`, discovery revision 13)

**Analysis date:** 2026-10-08T10:09Z. specswarm **4.0.1-botbaubble.2.37.0** loaded (the expanded `PLUGIN_DIR`; the session's pid in
2.37.0's `.in_use`; lore specswarm Q002). Built on `modify/007-rev13` from `master` at `c79facc`.

**Provenance:** modify row 7, computed by the command's `provenance-inputs` and `provenance-row` blocks:
`source_prompt` agrees with the send's `> Source:` (`plan/.discover/prompts/04-announcements-discovery.md`); the
prompt is at revision 13, `prompt_revision` is 1, `audited_against` is `[1]`.

**What changed (lore P004: what was compared).** The prompt bodies of `04-rev1-20261004-183704.md` and this send,
diffed from `# Announcements and discovery` to the end, differ in two places only: revision 13's note is added, and
the slice-0 Automated criterion's clause *"and in the workspace's agent context file when none exists"* is **struck**
(kept visible, with "user level only; a committed workspace announcement would announce tools that exist only in
timelike"). No other criterion, constraint or line changed. Revisions 2–12 did not change prompt 04.

**Classification: one criterion reworded by a strike, toward what was built.** The body describes the feature
correctly (FR-5–FR-7, user level only, never inside the workspace; SC-1's cells assert the workspace stays untouched),
so the **design is not false and is not regenerated**. What is now false is the body's **quotation and account** of
the old criterion:

| Body line | What it says | Against revision 13 |
|---|---|---|
| `spec.md:113–116` FR-7 | "Never inside the workspace … *This narrows the criterion's 'and in the workspace's agent context file when none exists'*: see D-1 and FOR-MENTOR Item 19" | design true; the "narrows" note is now false (the criterion no longer asks for it) |
| `spec.md:161–163` SC-1 | quotes the criterion with the workspace clause, "copied exactly" | **false as a quote**: the clause is struck |
| `spec.md:170–171` | "The workspace part is not built (D-1). The test asserts the workspace is left untouched, so the narrowing is visible" | the build is right; there is no longer a narrowing, nothing to build |
| `spec.md:200–210` D-1 | the seam and the criterion "disagree"; FLAGGED, medium; raised as Item 19 "for plan to amend the criterion or overrule the seam" | **resolved**: plan amended the criterion (revision 13, Q3 option (b), plan `394c33e`). The reasoning is kept |
| `spec.md:232` Out of scope | "The workspace context file (D-1, raised)" | no longer raised: struck at revision 13 |

**Other artifacts, read and left as they are:** `decisions.md:65` (T003's FLAGGED cell sense, "the cells change if plan
amends the criterion"). Plan amended it in the direction already built, so the cells do not change, and the line stays
as written. `cycle-report.md:86–90` (Cycle 1's SC-1 citation) is append-only. `plan.md:38` ("no workspace write;
D-1") is true. FOR-MENTOR Item 19 has been **closed since 2026-10-05** (`FOR-MENTOR.md:858`), so nothing outside
this feature's directory changes.

**Code against revision 13:** the build placed the announcement at the user level only and never in the workspace
(FR-7), and SC-1's cells assert that the workspace stays untouched. Lane readme-c ran them at `10ddd3a`, a tree
identical to `master`'s, and they passed. **The code already matches. Nothing to build.**

**Proposed change:** the spec only. SC-1 quotes revision 13's criterion with the strike kept; FR-7's note, SC-1's note,
D-1 (resolution appended, reasoning kept) and Out of scope follow it. `audited_against` gains 13, and `audit-log.md` is
created. No code, test or contract change, so no Docker lane is needed.

**Breaking changes:** none. **Risk:** low; documentation only. **Proceed:** yes.

# Cycle 3: slice 1 (natural) — command-not-found, unprivileged installs, the resource budget (send `bridge/sends/04-rev13-20261008-161802.md`, discovery revision 13)

**Analysis date:** 2026-10-08T16:24Z. specswarm **4.0.1-botbaubble.2.37.0** loaded: the expanded command's `PLUGIN_DIR` is
2.37.0's cache path (lore specswarm Q002). Built on `modify/007-slice-1` from `master` at `f6faf01`. An attended send.

**Provenance:** modify **row 4**, computed by the command's `provenance-inputs` and `provenance-row` blocks:
`source_prompt` agrees with the send's `> Source:`; the prompt is at revision 13, already in `audited_against`
`[1, 13]`. Nothing new to reconcile, and Step 9 appends nothing. The cycle adds the prompt's slice-1 criteria,
which have been in the prompt since revision 1 and out of scope until now. That is an addition, not supersession:
the slice-0 body stays true.

**Proposed changes** (spec § Slice 1):
- **The command-not-found answer.** A bash `command_not_found_handle` in 001's hook (`image/rootfs/etc/timelike/shell-env.bash`)
  and a data file `image/rootfs/etc/timelike/missing-commands.tsv`, copied by `image/Dockerfile`.
- **The budget.** `timelike budget` in `tools/bin/timelike`. The readers move into `tools/agentio/agentio.py`:
  `cgroup_dir`, the integer-or-`max` reader, the CPU figure, and 005's workspace finder.
- **The announcement** gains two rule lines (FR-24).
- **Carried:** SC-1's cell names; the 1 s bound becomes an ordering assertion.
- **Held:** the install criterion (FOR-MENTOR Item 21).

## Affected components

| Component | Feature | Change | Impact |
|---|---|---|---|
| `image/rootfs/etc/timelike/shell-env.bash` | 001 | defines `command_not_found_handle` (builtins only), and its header rule "leaves nothing behind" changes to "one function left on purpose" | **High reach:** every bash in the image reads it. Covered by `tests/host/test_shell_env_hook.sh` (no fork, PATH empty, idempotence) and `test_env_layer.sh` |
| `image/Dockerfile` | 001/007 | one `COPY` for the data file | low. The ENV block is unchanged unless Item 21 rules (b) |
| `tools/agentio/agentio.py` | 001 | gains the readers and the workspace finder | medium: every tool imports agentio. New functions only, nothing existing changes |
| `tools/bin/run` | 003 | imports `cgroup_dir` and the byte reader from agentio and drops its own | medium. Behaviour is unchanged, checked by `test_run*.py` unchanged and passing |
| `tools/bin/snapshot` | 005 | `find_workspace` calls agentio's | low. Behaviour unchanged, checked by `test_snapshot.py` |
| `tools/bin/timelike` | 007 | `budget`, two announcement lines | the README command reference regenerates |
| `tests/e2e/announcement-…-on-start.bats` | 007 | cell names; the bound becomes an ordering | test-only |
| `bench/vanilla/Dockerfile` | 002 | **none** (FR-13 holds; P6) | — |

## Breaking changes

None to any contract.
- A missing command still exits 127, and its first stderr line is bash's own.
- `run` and `snapshot` keep their outputs.
- The announcement grows by two lines, inside the bound.

## Risks

| Risk | Mitigation |
|---|---|
| The handler slows or breaks every shell | builtins only, defined without a fork; the hook tests (no fork, empty PATH, `set -eu` callers) are extended to cover it; its cost is measured |
| An answer that lies (a listed command is installed, or an `instead` names no tool) | an e2e cell for absence in the image; a unit test that every `instead` names a timelike tool |
| The budget's CPU figure disagrees with `TIMELIKE_CPUS` | one rule in agentio, tested against the bash hook on the same files, and in the container against the shell's value |
| Moving the readers changes `run` or `snapshot` | their existing unit and e2e suites run unchanged |

**Testing:** units for agentio's readers, `budget` and the data file; a host test of the handler (each style
simulated, byte-for-byte against bash). e2e in the image: SC-5's file (per style), SC-7's file (a throwaway with
known limits, and the agent container), and SC-1's renamed cells. The mentor's Docker lane is the merge bar.

**Risk level:** medium (the shell hook's reach). **Proceed:** yes, with SC-6 held.

# Cycle 4: discovery revision 14 — the agent runtimes (send `bridge/sends/04-rev14-20261008-174220.md`)

**Analysis date:** 2026-10-08T17:52Z. specswarm **4.0.1-botbaubble.2.37.0**, the same session as Cycle 3: the expanded `PLUGIN_DIR`
is 2.37.0's cache. 2.38.0 is published but not installed, and is not reloaded, as the send says. Continued on
`modify/007-slice-1` from `e0fb5a3`; Item 21 closed in `9b90a74`. The governance audit to 14 is on this branch:
`e58dd36` (tech-stack 1.4.0, quality-standards) and `07b914d` (constitution, no change).

**Provenance:** modify **row 7**, computed by the installed blocks: `source_prompt` agrees; the prompt is at
revision 14; `prompt_revision` is 1; `audited_against` is `[1, 13]`.

**What changed (lore P004: what was compared).** The prompt bodies of `04-rev13-20261008-161802` and this send,
diffed from `# Announcements & discovery` to the end, differ in three places:
- revision 14's note;
- the Feature text: "work in their default locations without privilege" becomes "work without privilege in user
  locations made the default, so the bare command needs no flag";
- the Environment constraint on PEP 668 is struck, and a new one added (the image ships an agent Python and
  Node, no marker, runtime-scoped configuration, never `PIP_BREAK_SYSTEM_PACKAGES`).

**No criterion changed**, and the Acceptance Criteria are byte-identical. Revisions 2–12 did not touch prompt 04;
13 was audited in Cycle 2.

**Classification: amended (a constraint struck and replaced, a feature sentence clarified), corrected by declared
copy as the send directs; no regeneration.** The slice-0 design is untrue in one place, and the held parts of
Cycle 3's slice-1 text now state a decision that has been made:

| Body lines (before this cycle) | What it said | Against revision 14 |
|---|---|---|
| `spec.md:152–155` FR-13 | the vanilla image is not changed | **false**: it gains the same runtimes with stock behaviour |
| `spec.md:294` FR-15 | no `user` rows until Item 21 | false: answered |
| `spec.md:310–320` FR-18 | held; recommendation (b), configured "through the environment" | false: ruled (a); configuration scoped to each runtime |
| `spec.md:322–335` FR-19 | recovery facts | true; seam 5's choice added (no exclusion: none reachable) |
| `spec.md:384–385` SC-6 | held | false: built |
| `spec.md:409–411` python3 carried | `installed: false` | false after this cycle |
| `spec.md:433–436` D-11 | held | resolved |

**Proposed changes** (spec § Slice 1, cycle 4: FR-25 to FR-31, D-12 to D-15):
- `image/Dockerfile`: a runtime build stage; the two prefixes; `pip.conf`, `npmrc`, links; `ENV` PATH.
- `image/rootfs/etc/profile.d/00-timelike-path.sh`: `~/.local/bin`.
- `pins.env`: `NODE_VERSION`, `NODE_SHA256`.
- `compose.yaml`, `Makefile`, `tests/run.sh`: pass the new build arguments.
- `bench/vanilla/Dockerfile`: the same runtimes, stock (002).
- `image/rootfs/etc/timelike/missing-commands.tsv`: runtime rows out, `user` rows in.
- `scan/scan.sh`: comments and the pip-audit record.
- `README.md`: the status block (all four slice-1 criteria built) and the vanilla description.
- Tests: SC-6 e2e (new), the P6 vanilla cell and unit test (revised), test_missing_commands (user rows),
  test_env_layer if its PATH checks move.

## Affected components

| Component | Feature | Change | Impact |
|---|---|---|---|
| `image/Dockerfile`, `pins.env`, `compose.yaml` | 001 | two runtimes, two pins, `PATH` | **High:** the image's contents and scan surface |
| `bench/vanilla/Dockerfile`, `Makefile` | 002 | same binaries, stock | medium: both bench arms change together (RB1) |
| `profile.d/00-timelike-path.sh` | 001 | one more `PATH` entry | low. `test_env_layer.sh` is checked |
| `scan/scan.sh` | 001/002 | comments, one record message | low |
| 007's data and tests | 007 | as above | — |

**Breaking changes:** none to any contract. The agent now *finds* `python3`, `pip`, `node` and `npm` where it
used to get the 127 answer.

**Risks:**
- **Scan findings in Node's npm tree or CPython** with no fix: they surface in the lane and are raised, never
  silently exempted.
- **Image size:** about 100 MB more for Node, and about 80 MB for Python.
- **The vanilla image grows the same way.**
- **Network at build:** uv's Python download and the Node tarball, both pinned.

**Risk level:** medium. **Proceed:** yes.
