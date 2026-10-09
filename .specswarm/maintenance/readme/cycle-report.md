# Cycle report — maintenance: the README

> Append-only. One section per cycle, headed by the send it built. A maintenance send has no prompt and
> no feature directory.

## Cycle 1 — bridge/sends/maint-readme-20261008-060811.md

**Written:** 2026-10-08T06:25:03Z (read from the clock). Built by hand on `maint/readme`, from `master` at
`b10f32c` (`0a02771` plus this instance's reboot.md commit, as the send allows). No specswarm command was
run. The session runs specswarm **2.36.0**: its pid is in the 2.36.0 cache's `.in_use`, and 2.35.0 has
none. **Pushed nothing; merged nothing.**

### Group A — cited from `.implement-complete`

Group A: not applicable — no marker on this path

### Group B — copied from the send

| Field | Value |
|---|---|
| source_send | bridge/sends/maint-readme-20261008-060811.md |
| source_prompt | none (maintenance; the source is the operator's request, 2026-10-08) |
| prompt_revision | none |
| discovery_revision | 13 |
| slice | none |

### Group C — written by the code instance

**delegations:** `[]`.

**The commits** (`master..maint/readme`):
- `97c25b0`: the README reorganised; the generator `scripts/readme_reference.py`; its test
  `tests/unit/test_readme_reference.py`; `scripts` added to ruff's paths (`Makefile`, both lint targets)
  and the generator to mypy's files (`pyproject.toml`).
- `5cdee2c`: `CLAUDE.md` gains the README's standing rule (§ Keeping it current, as the send asks).
- `e670f6c`: `CLAUDE.md` rule 5 gains **status tags until 1.0**. This is an instruction from the
  operator during this cycle, not part of the send. See "For the mentor" below.
- This report.

**The README's new outline** (977 lines, from 510):

| Part | Lines | Source |
|---|---|---|
| Title and one line | 1–5 | the send, verbatim |
| Why | 6–25 (20) | the send, verbatim |
| What (17 rows) | 26–47 (22) | the send, verbatim; tool names checked against `tools/bin` and each tool's `--help` |
| Status | 48–65 (18) | the send, verbatim, with the kept P6 sentence and a contents line |
| How it works | 66–183 (118) | the container (from the old Status), Environment defaults, The output contract, Adele and grants (her concept and the stand-in), and the session scratch (new, from the tool sections) |
| Install (typical) | 184–221 (38) | Needs (moved), build and `make up`, bringing the project in, attaching a harness, and the `python3` gap |
| Using it | 222–546 (325) | What an agent sees (the announcement, one flow from the demo transcripts, `more:`/`narrow:`/`expand:`/`do instead:`); the tools, one by one (the existing sections, moved); What the operator does (grants, extend, the ledger into the journal, the scan) |
| Command reference | 547–888 (342) | prose, then the generated block (328 lines, 13 tools) |
| Development | 889–977 (89) | build, test and scan; the two lanes; the speedup bench; the layout; governance; the licence |

The intro (title to Status) is 65 lines, more than one screen. The 17-row table is most of it, and its
rows are the send's.

**Content moved, not rewritten,** with these exceptions:
- **One correction:** the old Adele section said the exit-4 refusal is printed on stderr and that "its
  envelope on stdout waits on a decision". That has been false since 004 T018 (discovery revision 10):
  `tools/bin/adele:7` and `:228` return the grant envelope on stdout. D17's transcript shows it. The
  README now describes the envelope from that output.
- The old per-feature Status section is replaced by the send's table and paragraph. Its description of the
  image moved to How it works.
- New prose, all of it read from the code or the transcripts:
  - the session scratch;
  - Install's steps: the agent service mounts nothing (`compose.yaml`), runs as `USER agent` in
    `/home/agent`, and has `/opt/timelike/bin` first on PATH (`image/Dockerfile`);
  - the example flow, whose lines come from the D14, D5, D6 and D20 transcripts;
  - the line types that point to the next step;
  - What the operator does.
- **The `python3` gap** is stated as it is: `python3` is not on the agent's PATH; use
  `/opt/timelike/python/bin/python3` or the project's own Python. No `FOR-MENTOR.md` item was raised,
  because this instance has no reason to believe it should change.
- No claim of value was added. The P6 sentence is kept.

**The generator and its test:**
- **`scripts/readme_reference.py --write | --check`.** The tools are every executable in `tools/bin/`,
  the set the image installs (`image/Dockerfile:74`). Each section is the tool's own `--help`, verbatim:
  summary, synopsis, every flag with its meaning, and exit codes, all written by agentio's
  `_emit_help` from the tool's definition.
  - **Determinism, measured:** `--help` is cut at `COLUMNS` (rule 13), so the generator fixes
    `COLUMNS=1000`, with a temporary HOME, cwd and scratch root. Under that, all 13 tools' help is
    byte-identical across HOME, cwd, session and `LANG` (sha256 per tool). agentio formats the help
    itself, not argparse, so it does not vary between Python 3.12 (host) and 3.14 (image).
  - **`--agent-info` is not read:** `timelike --agent-info` exits 1 without the image's build stamp
    (`/opt/timelike/REVISION`), and `--help` already carries the summary.
- **The test** (21 cases):
  - the README's block equals what the generator produces now;
  - every installed tool has a section;
  - each section is a tool's own help, with no line cut;
  - `--check` passes on the README;
  - **controls**: a removed section, for each of the 13 tools; a changed flag line; a tool that is not
    installed; a README without the block.
- **The control at full scale:** with `verify`'s section removed from the real README, 4 tests failed
  and `--check` exited 1 with `verify: missing from the README's reference`. After the README was
  restored, `--check` reported `current, 13 tools`.
- **In the Docker lane:** the unit step mounts the repository read-only at `/src` and runs pytest on the
  image's interpreter, through uv. The test only reads the repository and runs each `--help` in a
  temporary directory. **Not run here** (no Docker): the mentor's lane is the first run on 3.14.

**criteria_reestablished.** The send has no criterion lines. Its asks, with their modes:
- intro, body order, generated reference with its test, the standing rule in `CLAUDE.md`, and this
  report: **executed** here (above).
- the reference test in the image: **unconfirmed** until the mentor's Docker lane.

**reconcile_mode:** `full`. The whole send was read and every section built.

**not_verified:**
- the new test under Python 3.14 in the image (lane pending);
- the README as rendered on the forge: anchors were written by GitHub's rule (lowercase, punctuation
  dropped, spaces to hyphens), not clicked.

**changed_other_features:**
- `Makefile` (ruff's paths gain `scripts`; both lint targets) and `pyproject.toml` (mypy's files gain the
  generator). No tool's behaviour changed.

**Deny-list, per id, over the branch** (`master..maint/readme` before this report: 16 new objects, 10 path
names, and the 3 commits' messages): P1–P7 **0** each. **Control** (`archive/pre-publish`): P1, P2, P6
and P7 fire. The tree check passed before each commit (451 files).

**`make test-host`** (at `97c25b0`'s tree; the later commits change only `CLAUDE.md`): **passed**.
Units 1661 passed (1640 before, plus this test's 21), files 60/60, hook 44/44. ruff, ruff format and
mypy strict (27 files) are clean, and shellcheck has no new file.

**process_failures_recorded:** none.

**retired_prompts_seen:** none.

### For the mentor

1. **A change to the publishing rule, from the operator during this cycle** (`e670f6c`).
   - Until 1.0, each germane push carries one annotated tag on the pushed commit, `v0.<slices built>.<n>`,
     with the message `N of 38 slices built; this push: …`. The operator chose this scheme and the
     backfill.
   - **`v0.15.0` exists locally on `0a02771`** (tagger ironik.xyz, message deny-listed), unpushed.
   - At this branch's push the operator expects `v0.15.0` and `v0.15.1` (README maintenance; this send
     changes no slice count).
   - Rule 5 named `master` as the only pushed ref. The tag is now the one other ref, on the same discharge
     and OK, so the pre-push checks should cover its message.
2. **The Docker lane is needed** before sign-off: the change adds a unit test.

## Cycle 2 — bridge/sends/maint-readme-godel-20261008-180140.md

**Written:** 2026-10-08T18:22:10Z (read from the clock). Built by hand on `maint/readme-godel`, from `master` at `f6faf01`, in a
temporary git worktree outside the project (in the session's scratchpad), so `modify/007-slice-1` and its working
tree were not touched. No specswarm command was run (session: specswarm 2.37.0). **One commit** (this one): `README.md`
and this section. **Pushed nothing; merged nothing.** No lane on 04 slice 1 had started when this was committed: there
was no lane row in `bridge/history.md` after the send at 18:01:40Z, and no new `bridge/.make-test-*.log`.

### Group A — cited from `.implement-complete`

Group A: not applicable — no marker on this path

### Group B — copied from the send

| Field | Value |
|---|---|
| source_send | bridge/sends/maint-readme-godel-20261008-180140.md |
| source_prompt | none (maintenance; the operator's text, 2026-10-08, verbatim) |
| prompt_revision | none |
| discovery_revision | none (the send names none) |
| slice | none |

### Group C — written by the code instance

**delegations:** `[]`.

**What changed.**
- **`README.md`:** one blank line, then the section `## Thank You Mr Gödel`, after the last line (`MIT.` under
  `### Licence`). The 8 lines were copied byte for byte from the send's fenced block, extracted with `awk`, not
  retyped. The curly apostrophe (U+2019) and the five `ö` characters were checked. Diff stat:
  `README.md | 9 +++++++++` (9 lines added, nothing removed).
- **Nothing else changed:** the Contents line, the What and Status sections, and the generated command reference are
  untouched.

**criteria_reestablished** (the send's checks, not prompt criteria):
- `python3 scripts/readme_reference.py --check`: **executed**, `readme reference: current, 13 tools`, exit 0. The
  section is outside the reference markers.
- `make test-host` (venv python 3.12.3, pytest 8.4.2, run in the worktree): **executed, FAILED 2 of 1661**:
  1658 passed, 1 skipped, 2 failed; env layer 60/60; hook 44/44. The two failures are not this change's (see
  not_verified).
- **What reads the README:** only `scripts/readme_reference.py` and its test (between the markers), and the deny-list
  gate (the whole tracked tree). Every other mention of "README" in `tests/`, `image/` and `bench/` is a fixture that
  writes its own file. Nothing in the image or its tests reads past the markers.
- **The deny-list per id** over this commit's diff and message: in the final paragraph of this section.

**reconcile_mode:** not applicable (no prompt).

**not_verified / the two host failures, reported, not fixed** (the send confines this cycle to `README.md`):
- **The failures:** `tests/unit/test_run_slice1.py::test_the_enospc_message_in_the_output_is_the_disk_cause`
  [both parameters].
- **What the test expects:** `run`'s verdict to name two filesystems ("<workspace mount> has … free, <scratch mount>
  has … free").
- **What `run` does:** it names a filesystem once when the workspace and scratch share it (`tools/bin/run`,
  `named()`: "one filesystem holding both is named once").
- **Why it failed here:** in this worktree, under `/tmp` like pytest's scratch, both are `/`, so the verdict reads
  "`/` has … free" once. In the project checkout the workspace is on another filesystem, and the same tests passed
  (007 Cycle 4, T031: 1825 passed).
- So it is **a test that assumes two filesystems**, unrelated to the README. It is for a later 003 cycle: assert one
  name when both mounts agree.

**changed_other_features:** none.

**process_failures_recorded:** none.

**retired_prompts_seen:** none.

**For the mentor:**
- Merge `--no-ff` after sign-off, in either order with 04 slice 1. They touch different parts of the README, and 04
  s1's status block sits in `## What` / `## Status`.
- It rides the next germane push and shares its tag.
- No Docker lane is needed: only `README.md` changes. The two host failures are environmental, as above.

**The deny-list per id**, over this commit's staged diff (`README.md` and this report) and its message, computed
with `scan/denylist.py`'s parser before committing:
- diff: P1 0, P2 0, P3 0, P4 0, P5 0, P6 0, P7 0;
- message: P1 0, P2 0, P3 0, P4 0, P5 0, P6 0, P7 0;
- tracked tree: `publish deny-list [tracked tree]: PASS — 7 entries, 455 tracked files: no match`.

Identity: ironik.xyz.

## Cycle 3 — bridge/sends/maint-readme-godel-2-20261008-190924.md

**Written:** 2026-10-08T19:57:19Z (read from the clock). Built by hand on `maint/readme-godel`, on top of `866b49b`, in a temporary git
worktree outside the project (in the session's scratchpad), after the mentor said lane `007s1-a` had ended
(`bridge/feedback/04-20261008-193851-lane-007s1-a-three-cells-and-the-scan.md`, "Also"). `modify/007-slice-1` and its
working tree were not touched. No specswarm command was run. **One commit** (this one): `README.md` and this section.
**Pushed nothing; merged nothing.** The send as read carries its 19:10:30Z amendment (no comma after "his").

### Group A — cited from `.implement-complete`

Group A: not applicable — no marker on this path

### Group B — copied from the send

| Field | Value |
|---|---|
| source_send | bridge/sends/maint-readme-godel-2-20261008-190924.md |
| source_prompt | none (maintenance; the operator's text, 2026-10-08, verbatim) |
| prompt_revision | none |
| discovery_revision | none (the send names none) |
| slice | none |

### Group C — written by the code instance

**delegations:** `[]`.

**What changed.**
- **`README.md`:** the whole section, from `## Thank You Mr Gödel` (line 979) to the end of the file, replaced with the
  send's fenced block. The block was extracted from the send with `awk` (the lines between ````markdown` and the
  closing fence), not retyped, and the README was rebuilt as its first 978 lines followed by that block. Diff stat:
  `README.md | 8 +++++++-` (7 insertions, 1 deletion: the Wolchover link line, which now continues the paragraph).
- **Nothing else changed:** lines 1–978 are untouched, including the blank line after `MIT.`.

**criteria_reestablished** (the send's checks, not prompt criteria):
- **Byte comparison**, executed: `tail -n +979 README.md | cmp - <block>` reports no difference. Both are 14 lines and
  1256 bytes, SHA-256 `3049085e01442467b79d820ba477317d9a7702e4a840d7d779ff1c73e49d51d9`. The straight quotes and the
  apostrophe in "Marks'", the one curly apostrophe (U+2019) in "Gödel’s", the `ö`s and the three dots come across as sent.
- `python3 scripts/readme_reference.py --check`: **executed**, `readme reference: current, 13 tools`, exit 0.
- `make test-host` was not asked for by this send and was not run.

**reconcile_mode:** not applicable (no prompt).

**not_verified:** that the three new links resolve (no network check was asked for or made).

**changed_other_features:** none.

**process_failures_recorded:** none.

**retired_prompts_seen:** none.

**For the mentor:** `maint/readme-godel` now carries two commits (`866b49b` and this one). Merge `--no-ff` with 04 slice 1
after sign-off; no tag of its own.

**The deny-list per id**, over this commit's staged diff (`README.md` and this report) and its message, computed with
`scan/denylist.py`'s parser before committing:
- diff: P1 0, P2 0, P3 0, P4 0, P5 0, P6 0, P7 0;
- message: P1 0, P2 0, P3 0, P4 0, P5 0, P6 0, P7 0;
- tracked tree: `publish deny-list [tracked tree]: PASS — 7 entries, 455 tracked files: no match`; per id: P1 0/0, P2 0/0, P3 0/0, P4 0/0, P5 0/0, P6 0/0, P7 0/0.

Identity: ironik.xyz.
