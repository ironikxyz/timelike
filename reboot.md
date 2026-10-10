> Redacted for publication, 2026-10-02 (`bridge/sends/maint-publish-redaction-20261002-183624.md`): internal host names, absolute paths and a personal name replaced. No other change.

# reboot.md — resume point for the code instance

Read this first after a context clear. It is a snapshot. The artifacts it points to are the truth:
`cycle-report.md`, `FOR-MENTOR.md`, `tasks.md`, the bridge.

**Snapshot:** 2026-10-08T20:45:32Z (read from the clock), written at the end of 007 Cycle 5; lane 007s1-b's outcome added 2026-10-09T01:23:57Z; sign-off and merges added 2026-10-09T03:54:48Z; 002 Cycle 3's merge added 2026-10-09T10:22:06Z; 008 Cycle 2 added 2026-10-09T11:02:21Z; its sign-off and merge added 2026-10-10T04:01:41Z. **This repository is public**:
push only on a discharge and the operator's OK (CLAUDE.md rule 5).

## State at 2026-10-08T20:45:32Z

- **Pushed 2026-10-09** (operator OK, mentor discharge 04:10Z): `public/main` = `ec71f3d`, tag **`v0.16.0`** (object
  `5f3b94f`). Deny-list over the tag message and every object pushed: 0 on P1–P7, control positive.
- **Plugins:** specswarm **2.40.0** and ccmentor 1.50.2, installed during the operator's pause (04:21Z). This session
  runs 2.40.0, which the expanded `PLUGIN_DIR` shows.
- **`modify/008-slice-1`** (from `master` `ce1eaf2`): **008 Cycle 2 = 06 slice 1**, send
  `bridge/sends/06-rev1-20261009-102433.md` (row 4: `audited_against [1]` unchanged). Built: `edit --at` (view's anchors,
  checked with view's own `anchor_of`/`line_body`), the syntax check (Python by the interpreter's compiler, shell by
  `bash -n`, TS/TSX/Go/Rust by tree-sitter wheels pinned in `pins.env`, child `tools/libexec/syntax-check`, 10 s limit,
  fail open), `--skip-syntax-check`, the README status block (17 of 38). **Lane 008s1-a failed** (feedback
  `06-20261009-162833`): the Dockerfile did not parse (fixed `765190a`), and the mentor ruled CPython 3.14.8 (uv 0.12.22)
  and CVE-2026-107161 baselined, origin git (`e275c26`); Cycle 2 addendum 1. **Lane 008s1-b**: slice 1 green; ten slice-0 cells pinned the old
  verdict (feedback `06-20261009-192053`), fixed `5f5c246`, Cycle 2 addendum 2. **Lane 008s1-c** green (its 8 SC-8
  failures were a slow `--cpus` container start on the host; the file alone passed 19 of 19 with `RUN_TIMEOUT=180`).
  D15 observed by the operator. **Signed off at `965844d`** (2026-10-10T03:58:31Z). Cycle 2 addendum 3 corrects
  spec.md FR-19 and Scenario 7 (3.14.7 was stale). **Merged `--no-ff` into `master`. Not pushed**: the mentor
  discharges on the merge; push only on the discharge plus the operator's OK. The README Status is now 17 of 38, so
  that push's tag is `v0.17.0`.
  - **Feedback closed** (resolved by the mentor beside each question): `06-20261009-162833-…` (lane 008s1-a) and
    `06-20261009-192053-…` (lane 008s1-b).
- **`modify/002-rev8-carried`** (from `ec71f3d`): 002 Cycle 3, send `bridge/sends/02-rev8-20261009-043302.md`. Records
  only: revision 8 is re-recorded as `carried` to 02 slice 1, and `audited_against` stays `[1, 8]`. **Signed off at
  `28da1d0`** (records only, no lane) and **merged `--no-ff` into `master` as `bbb2c46`**. No tag (the slice count is
  unchanged). **Not pushed**: it rides the next germane push.
- **`modify/007-slice-1`** holds **04 slice 1**: Cycles 3 and 4 (built), lane 007s1-a's fixes and revision 15 (Cycle 5).
  It started from `master` `f6faf01`. **Signed off on `3eba335`** (2026-10-09T03:55Z; lane 007s1-c green; D13 observed
  by the operator, transcript `bridge/.d13-demo-20261009T034838Z.txt`). **Merged `--no-ff` into `master`**, then
  `maint/readme-godel` the same way (the merge commits are the two at `master`'s tip). **Not pushed, no tag.** The
  mentor discharges on the merge; push only on the discharge plus the operator's OK.
  - **Feedback closed** (resolved by the mentor 2026-10-09T03:55Z, beside each question):
    `04-20261008-193851-…` (lane 007s1-a: fixed in Cycle 5) and `04-20261009-010500-…` (lane 007s1-b: `a7e1f2f`
    GO_IMAGE 1.27.2, `de5aebe` GO_LINT_IMAGE). Only the `GO_LINT_IMAGE` removal item stays open (Open items).
  - The tag at that push: **`v0.16.0`** (README Status is 16 of 38). It carries the three audit merges (`225a55c`,
    `39c8ae2`, `f6faf01`) and the Gödel commits too.
- **`maint/readme-godel`**: `866b49b` (the section) and `ad4d63f` (the section extended, send
  `maint-readme-godel-2-20261008-190924`). Reported in `.specswarm/maintenance/readme/cycle-report.md` Cycles 2 and 3.
  Merge `--no-ff` after sign-off; no tag of its own.
- **Sends:** Cycle 3 = `04-rev13-20261008-161802`, Cycle 4 = `04-rev14-20261008-174220` (both stand, both retired),
  **Cycle 5 = `bridge/sends/04-rev14-20261008-201729.md`** (the active prompt: prompt 14, discovery 15).
- **Cycle 5 built** (T034–T045; full account in `cycle-report.md` § Cycle 5):
  - lane fixes: the direct-exec cell reads both streams; 001's C6 cell drops python3-bearing PATH entries; two no-fix
    baseline entries (GHSA-ch52-4w7c-c8xp, CVE-2026-77214); `pip-audit-agent`; **npm 11.21.0** (`NPM_VERSION`,
    `NPM_SHA512`) replacing Node's bundled npm in both runtimes stages;
  - revision 15: three **bundled-class** baseline entries (brace-expansion ×2, undici; npm 11.21.0; review by
    2026-11-07) and the **release check** (`evaluate.py releases`, a `release-check` scan step, fails closed);
  - governance `[2..15]`: constitution 1.4.3, tech-stack 1.5.0, quality-standards.
- **007's spec** records `audited_against: [1, 13, 14, 15]`; `prompt_revision` is 1. 15 was appended on the send's
  instruction (the library's row was 4), as `audit-log.md` says.
- **FOR-MENTOR:** Item 20 still open. The three npm-bundled findings went to plan as
  `bridge/feedback/04-20261008-201205-fix-available-for-npm-bundled-libraries.md` (resolved: revision 15).
- **specswarm 2.37.0** ran every cycle. Later versions are published, not installed; the send said not to reload.

## Expect from lane 007s1-b (watch for these)

- **The release check from inside the scan container:** the `release-check` row should say 3 bundled entries, 4
  releases examined (11.20.0, 11.21.0, 12.1.0, 12.2.0), 3 no-release, for agent and vanilla. If the image's interpreter
  cannot reach registry.npmjs.org over TLS, the three findings block with "release check could not run" (by design).
- **Grype over npm 11.21.0's tree:** any new finding in the rest of that tree. A finding with a fix in no npm release is
  a bundled-class entry under revision 15; one with no fix at all is an ordinary entry. Raise both; never exempt silently.
- **`pip-audit-agent`** in the real scan (`-r … --no-deps --disable-pip` from the agent image's uv).
- **The npm step under the real builder** (`ADD` of the registry URL; `sha512sum -c`).
- **T034's and T035's cells** against the real container.
- **SC-7's limited throwaway** needs a lane host with at least 2 CPUs. `tests/unit/test_bench_catalog.py` is
  load-sensitive (15 s setup timeouts at host load of about 9).

## Recipes this session used (the scratchpad is gone after a clear; rebuild)

- **`ct.sh TASK MSGFILE DECFILE FILES…`** (one task): append DECFILE to `decisions.md`; tick the task; stage FILES with
  both; run the deny-list per id over the staged diff and the message (refuse on any hit) and over the tracked tree
  (`git write-tree` + `git archive`; capture the output first, `head` under `pipefail` kills it); commit; then compute
  SCOPE from `ts-TASK` with the installed `scope-check` block, **sourced under `set +eu`** (it is not `set -e` safe:
  a `grep` with no match ends the script after the commit), append it, and commit "scope record, task ticked".
  **Read `git log` before re-running anything that commits.**
- **`dlids.py`** (per-id counts): `sys.path.insert(0, scan)`, `import denylist`, `parse_list`, `match_lines` per entry
  over each file; prints ids and numbers only.
- **A venv** with pytest 8.4.2, ruff 0.16.9, mypy 2.3.1, shellcheck-py, coverage 7.10.7. `make test-host
  PYTHON=<venv python>` with the venv's bin on PATH; `make lint-host` the same.
- **bats 1.14.0** from the bats-core tag tarball, for stub-docker trials of single cells (there is no bats on the host).
- **The live release check from the host:** `python3 -I scan/evaluate.py releases --baseline scan/baseline/<img>.json
  --node-version 24.21.0 --out <file>` (about 3 s; it reads npm's 25 MB packument and 4 tarballs).
- **Temporary worktrees** (the Gödel sends): `git worktree add <scratch>/wt maint/readme-godel`, then remove it.

## What happened since b10f32c (2026-10-08)

1. **README maintenance** (send `maint-readme-20261008-060811`): built on `maint/readme`.
   - The README was reorganised, with a generated command reference (`scripts/readme_reference.py --check|--write`)
     and its test (`tests/unit/test_readme_reference.py`).
   - CLAUDE.md gained the README rule and the status-tag rule.
   - Lane readme-c passed. Merged as `c79facc`. Pushed with `v0.15.0` and `v0.15.1`.
2. **Audit send** (`maint-audit-rev8-13-20261008-095251`): three record-only modify cycles, each touching only its
   feature directory:
   - **002, Cycle 2 (rev 8).** The verdict-order constraint is in the spec, declared. Slice 0's code doesn't meet it
     (`report.py:119`, `:227`, `data-model` step 3, T016), and plan's ruling (b) carries it to **02 s1**. Scoped
     reconcile, `[1, 8]`.
   - **001, Cycle 8 (revs 11–13).** Rule 10's struck project-cache clause is corrected in place; rules 9 and 13 are
     annotated. Full reconcile, `[2..13]`.
   - **007, Cycle 2 (rev 13).** SC-1's workspace clause is struck and D-1 resolved. Scoped reconcile, `[1, 13]`.
   - The mentor reconciled all three and signed off; they merged to master (above).

3. **README Gödel sends** (`maint-readme-godel-20261008-180140`, `…-godel-2-20261008-190924`): `866b49b`, `ad4d63f` on
   `maint/readme-godel`, each in a temporary worktree; README only; not merged.
4. **Lane 007s1-a** (18:24–19:37Z) on `41d4b5f`: 573/576 e2e (the direct-exec stream; 001's C6 premise ×2), units and Go
   passed, scan 9 blocking per runtime image. Feedback `04-20261008-193851-…`; fixes T034–T038.
5. **Revision 15** (plan `300fdf3`): the npm-bundled question, ruled; built as 007 **Cycle 5** (T039–T045).

## Open items (none blocks)

- **Removal item, `GO_LINT_IMAGE`** (2026-10-09): delete it once a staticcheck release whose x/tools reads Go
  1.27.2's export data exists, and move staticcheck back to `GO_IMAGE`. Check with `curl
  https://proxy.golang.org/honnef.co/go/tools/@latest` (v0.8.1 at 2026-10-09). Recorded in `quality-standards.md`
  and `pins.env`.
- **The mentor's carried findings** (history 12:58:18Z):
  - (a) `verify` runs `git status` without `--no-optional-locks` (`tools/bin/verify:878`). Cheap hardening for
    012's next cycle. Runner caches stay in the workspace, which 012's contract admits.
  - (b) `output-contract.md` doesn't name the per-workspace state root. For 07 s1.
  - (c) 007's SC-1 e2e cell names (`announcement-…-on-start.bats:400–405`) still quote the struck clause. For a later
    007 cycle, together with SC-1's 1 s timing bound, which trips under host I/O load (lane readme-b).
  - (d) `announce --install` writes under `$HOME`, which is also the image's WORKDIR.
- **Still open from the batch** (see `reboot.md` § Open items): the singular/plural defects; `view` `more:` not
  clamped; Adele ledger `agent: None`; `python3` not on the agent's PATH; FOR-MENTOR **Item 20** (the symbols index
  in the scratch until 07 s1).
- **Slices to come:** 07 s1 (state root) and 15 s1 (Adele's standing grant), both held for attended sends; 02 s1
  (carries the rev-8 verdict order); 04 s1; 06 s1.
- **A rule question I raised, not ruled on:** the specswarm `audit-append` rule has no mode for "revision N's change
  recorded, but carried to a later slice". 002 appended 8 per the send's reading.

## How the audit cycles were run (recipes; the scripts lived in the memory staging folder, removed once folded here: rebuild them from this text)

- **Per cycle:**
  - branch `modify/NNN-revM` from master;
  - `Skill specswarm:modify` with `NNN --from-send bridge/sends/…`, which loads the text;
  - run its blocks from `modify_s12.sh "<args>"`, which gives the row;
  - classify by diffing the prompt bodies of the archived sends;
  - append `# Cycle N` sections to `impact-analysis.md` and `modify.md` (create them on a first modify), and commit;
  - `Skill specswarm:plan`: append the Cycle plan section and commit;
  - `Skill specswarm:tasks`: add a Phase with tasks, run the `ts_mentions` scan, and commit;
  - `Skill specswarm:implement`, per task: `git rev-parse HEAD > ts`, edit, append to `decisions.md`, tick the
    task, then `precommit.sh msgfile && git commit -F msgfile`, then `scope.sh FEATURE_DIR $(cat ts)` appended to
    `decisions.md` and a "scope record, task ticked" commit.
- **Provenance:** run `audit_append.sh` with the env vars `PROMPT_REV`, `AUDITED`, `N`, `MODE`, `OUT_OF_SCOPE`,
  `UNVERIFIED` and `REMOVALS_VISIBLE`. **A revision that rewords a criterion gets `scoped`**; `full` would skip it.
- **Step 10:** `step10.sh` then `step10g.sh`. The result is always unknown, warned (pytest is not installed for
  `/usr/bin/python3`). **Do not write `.specswarm/metrics.json`** when a send confines the cycle to the feature
  directory.
- **The 9b tallies:** `source lib/tally.sh; scope_tally tasks decisions; decision_tally decisions`. Wrap each in
  `echo "$(…)"`, because they print no trailing newline.
- **Deny-list:**
  - `precommit.sh [msgfile]` checks the staged tree and the message, by id;
  - `objscan.py "<range>" <outdir> ../bridge/publish-denylist.txt` checks objects, path names and messages. Run it
    from `code/`;
  - the control is the range `archive/pre-publish`, which fires P1, P2, P6 and P7.
  - **Run the check before every commit.** I slipped once this session (`4f634c6`; scanned clean straight after).
- **Push recipe** (`reboot.md` § Publishing recipes): a throwaway `GIT_ASKPASS` script in the scratchpad (mode 700).
  It answers `Username*` with `x-access-token`, and anything else with `GITHUB_IRONICXYZ_PAT` read from
  `~/projects/ironik.xyz/.env`. Run `GIT_ASKPASS=… GIT_TERMINAL_PROMPT=0 git -c credential.helper= push public
  master:main`, then the tags. Delete the script afterwards, check the output holds no token, and verify with
  `git ls-remote`.
- **Subagents:** a read-only general-purpose agent did 001's rule-10 code search well. Brief it: no edits, nothing
  under bridge/ or plan/, cite file:line. Re-read its key citations before using them.

## specswarm 2.37.0 observations (already relayed to the mentor)

- D105: the tallies live in `lib/tally.sh`, with 0 bytes on stderr. D107: `flagged_delegate` counts work.
- `provenance-inputs` (D89) mechanises modify row 7.
- `fnum_resolve` handles `modify/NNN-*` silently.
- Step 10e reads `package.json` (no more `quality-gates.sh` error).
- Cosmetic: the tallies print no trailing newline.

## How the batch closed (2026-10-06 to 10-08)

- **Lane batch-b** at `1dfc6b7`: 3 failures, all test-side, routed by
  `bridge/feedback/batch-20261006-234535-lane-b-three-failures.md` (closed):
  1. 001's SC-6 default cells: 009's shell record holds the command text, so the byte grep matched
     `default`. Fixed on 009 (`2e3f483`): `shell.jsonl` out of the byte grep, its `session` field asserted.
     Cascade 010 → 011 → 012.
  2. 012's `test_verify` probe assumed `python3` on `/usr/bin:/bin` (`2a0ca75`).
  3. 432 / 448 (lanes b and c) were one finding: `pyq`'s throwaway `docker run` killed at the 30 s
     `RUN_TIMEOUT`. Fixed with `PYQ_TIMEOUT` (120 s, `pyq` only), and `jpy` decides a timeout by elapsed time
     (`f6cf7da`, `244c4a8`). **The runner's `timeout` is BusyBox's** (bats/bats is Alpine): a killed command
     reports 143, never 124. Decide timeouts by elapsed time, never by exit code.
- **Lane batch-d** at `244c4a8`: PASS (e2e 537/537, units 1638 + 2 skipped, scan PASS ×4, deny-list PASS).
- **Demos**, all observed by the operator: D12 (003), D14 (006), D4 (007), D6 (008), D17 (009), D18 (010),
  D19 (011), D20 (012). Each is in its feature's cycle report, committed on 012's tip as records only
  (`d932c1c` … `5684391`), placement stated in each.
- **Sign-off** 2026-10-08T05:39:01Z (its `{exp}` placeholder corrected at 05:40:49Z, after this instance
  raised it before merging). Eight `--no-ff` merges in stack order: `b1cfb49` … `0a02771`, tree
  `d177c142839b…` as expected.
- **Pre-push checks that worked:**
  - the cleared list diffed against `git rev-list aa8127d..0a02771` (137 = 137);
  - the object scan of the new objects, path names and messages (P1–P7 0), with the control on
    `archive/pre-publish` firing P1, P2, P6 and P7 (the recipe in § Publishing recipes);
  - the askpass push.
- **The feature branches stay local and are fully merged.** The old scratch worktree of `master` is
  removed.

## Open items after the batch (for the next sends; none blocks)

- **Records:** each feature's automated slice criteria are still recorded `unconfirmed` in its cycle
  report, although lane batch-d ran their cells. Recording them `executed` is a records-only pass, and only
  if the mentor asks.
- **Mentor findings for later cycles:**
  - the singular/plural defects `1 lines` (003 run), `1 files` (006 search) and `[1 services]` (010's list
    header);
  - `view …:10-14` on a 21-line file offers `more: …:15-134` (not clamped) and prints the full-output path
    twice (05);
  - Adele's ledger rows carry `agent: None` with `TIMELIKE_AGENT` set (08/12);
  - `python3` is not on the agent's PATH in the image (the announcement, or a decision).
- **The mentor's reconcile (2026-10-07T05:04:07Z):**
  - 010, 011 and 012 cite pre-rebase SHAs; the mapping is in that row;
  - 008 T007's stale TASK_START (self-reported);
  - 007 is UNAUDITED at 13; 001 at 11–13.
- **Slices still to come:** 07 s1 (state-root volume) and 15 s1 (Adele's standing grant) were held for
  attended sends; 04 s1 and 06 s1 wait. FOR-MENTOR Item 20 (the symbols index in the scratch until 07 s1)
  is open.

## Next actions

1. **Check the bridge** (memory: check-bridge-before-building): `../bridge/history.md`'s newest rows,
   `../bridge/active-prompt.md`'s Status line, `../bridge/feedback/`, and `../bridge/dispatch/`.
2. Build only from a new send. Start each feature branch from `master` (`0a02771`), unless the send says
   otherwise.
3. **This file has uncommitted updates** (2026-10-08). Commit them with the next code work, as the
   operator said.

**Batch recipes (scratchpad, gone after a clear; rebuild them):**
- **Expanded command text is not safe to run.** 2.35.0's implement expansion turns awk's `$0` into
  the argument. specify's pastes a quoted description into double quotes. Run every block from the
  installed file (awk the `# >>> name` … `# <<< name` range), with `ARGUMENTS` as a variable.
- **`FEATURE=NNN-slug commit-task.sh TASK DECFILE MSG FILES…`:** appends DECFILE (`@START@`/`@END@` from
  `start-TASK`, written by `start.sh TASK`: the clock and HEAD) to decisions.md, gates on the deny-list
  (refuses to commit unless PASS), commits only the named FILES plus decisions.md, computes SCOPE with the
  installed `scope-check` block (under `set +euo pipefail`), ticks the task, and amends. A delegated
  task's start file is written by hand (one token, then HEAD), so its range is its own files only.
- **Every block needs `CLAUDE_PLUGIN_ROOT`** set to the cache path when run outside the expansion
  (`tech-stack-classify`, `tech-stack-taskscan`, `quality-scale`); without it they report their library
  absent, which is false.
- **The marker:** write the ten fields by hand with the tallies from the installed `scope-tally` and
  `decision-tally` blocks (after T009's section), then the `marker-fields` block (MARKER-CLEAN).
- **Host e2e stand-in** (advisory, never image evidence): bats-core v1.11.1 cloned into the scratchpad,
  and `stub/docker` running `exec` locally against `cbin/` (tools/bin with the venv shebang, made by
  `conform-all.sh`), mapping the image's interpreter to the venv's and `bash -lc` to `bash -c`. Run:
  `PATH=$S/stub:$PATH GIT_SHA=host $S/bats/bin/bats tests/e2e/<files>`. `type -a` cells fail by design.
- **Host conformance:** `conform-all.sh` installs every tools/bin tool with the venv interpreter and runs
  timelike-conform over them (test_conform.py covers only timelike and timelike-conform).
- **Step 10:** `step10.sh` runs the installed `quality-components`, `quality-scale` and
  `unmeasured-explains-itself` blocks. Its output so far is identical each time (unknown, warned).
- **Coverage rc:** add `/tmp/pytest-of-*/*/*/tl/` to `[paths] bin` (007's announce tests install
  `timelike` there; without it the total read 51%).
- **Delegates** wrote every cycle's units and e2e from the contract. Brief each with its files, the
  no-literal-secrets rule and the deny-list rule. Review their contract findings and settle them in the
  contract as built.
- **Never compose a time:** read it with `date` (memory: read-times-from-clock).

**06 is done** (`008-edit` § Cycle 1). Its leftovers for the batch's final report: the D6 observation
(a uniform dedent is not tolerated; the candidate says "indentation"), and the process failures in its
§ Cycle 1 (one ungated commit amended locally, the probe, CLAUDE_PLUGIN_ROOT).

**Open items from this batch, for the batch's final report:**
- **012:** the send's premise "pytest runs in the image" was false (the image has no pytest, ruff or
  mypy); the e2e fetch them via the image's uv at the pins, so they need PyPI from inside the agent
  container (proved by lanes batch-b, c and d). `verify`'s children run with a scratch root inside the session's
  scratch so a call writes one event (C7). The D104 note: T001–T003 shared one start read from HEAD, so
  T001's scope range includes T003's commit (true, and wider than the task).
- **Traced-run timing failures outside the features:** 011's adele conform, 012's bench runner; both pass
  untraced 3/3.
- **FOR-MENTOR Item 19:** closed (revision 13, user level only). Item 18 Q3 closed (revision 12).
- **Plugin observations to relay (2.35.0):** implement's expansion clobbers awk's `$0`; specify's
  expansion breaks on a quoted description (the stray quote is in the description; an unquoted `&`
  would background part of the line). That is the send's `$ARGUMENTS` question, answered with a real case.
- **A 006 Cycle 1 defect, fixed on 007:** `tools/bin/view` and `search` were committed `100644`. The
  image's `COPY --chmod=0755` hid it.
- **A process slip:** composed timestamps in 003 Cycle 2's decisions, corrected by an appended note.
  Rule now: read times from the clock.
- **plan and tasks were not re-invoked** for 006 and 007. Their 2.35.0 text from 003 was followed, and
  the cycle reports say so. Invoke them for each remaining feature.

**Per-feature paths in this batch:**

| Feature | Report | New tests |
|---|---|---|
| 003 s1 | `003-concluding-run/cycle-report.md` § Cycle 2 | `tests/unit/test_run_slice1.py`, `test_agentio_redaction.py`, `test_redaction_rules.py`; e2e `run-killed-by-memory-…`, `run-full-scratch-…`, `run-secrets-redacted-…` |
| 006 s1 | `006-bounded-read/cycle-report.md` § Cycle 2 | `tests/unit/test_view_slice1.py`; e2e `view-directory-overview-…`, `view-anchor-mode-…`, `view-and-search-slice-1-carried-items.bats` + `fixtures/bounded-read-slice1.sh` |
| 007 | `007-announcements-discovery/cycle-report.md` § Cycle 1 | `tests/unit/test_announce.py`; e2e `announcement-at-most-60-…`, `announcement-generated-…`, `timelike-tools-manifest-…` |

Shared files this batch touched:
- `image/rootfs/etc/timelike/redaction.toml` (shared with `scan/scan.sh`'s gitleaks `--config`) and
  `standard-tools.json`;
- `image/rootfs/opt/timelike/libexec/entrypoint` (the image's ENTRYPOINT);
- `tests/unit/conftest.py` (`TIMELIKE_REDACTION_RULES`).

**006 helpers** (scratchpad, gone after a clear): `commit-006.sh` / `scope-tick-006.sh` (one task commit,
then a "scope record, task ticked" commit; the scope-check block from 2.35.0, unchanged since 2.32.0);
`tally006.sh`; the docker stand-in in `stub/` (exports TIMELIKE_BIN_DIRS) with tools in `tb/`; bats in
`bats/`. **Work on `master` from a worktree** (`git worktree add <scratch>/master-wt master`) when
delegates are reading the feature branch.

**Ship recipe under 2.32.0 (worked, 005):** extract analyze-quality's blocks (`analysis-context`,
`component-applicability`, `tests-agnostic-score`, `unknown-resolvability`, `module-score`,
`overall-score`, `quality-report`) and ship's (`quality-source`, `quality-threshold`, the threshold
lines, `quality-gate`) with `textwrap.dedent` into one script, `MODULES` = 001's eight; **unset
`FEATURE_DIR`** before `quality-source`. Quote the checkout path as `<repo>/` (P2). Merge by hand.

## Publishing recipes (2026-10-03)

- **The deny-list rule:** never write a pattern or a matched string into a tracked file, a commit
  message or a test. Refer to entries as P1–P7.
- **The tree check:**
  `git archive HEAD | python3 -I scan/denylist.py --list ../bridge/publish-denylist.txt --expect-files $(git ls-tree -r HEAD --name-only | wc -l)`.
  Never put two `git write-tree` calls on either side of one pipe: they race for `index.lock`.
- **The interactive `grep` here is a ugrep wrapper**, which rejects P2's syntax. In scripts, use
  `/usr/bin/grep` (GNU). `scan/denylist.py` calls `grep` from PATH, which is GNU here and in the image.
- **The object scan before a push** (every object, not only files). For each `sha` in
  `git rev-list --objects <rev>`, write `git cat-file -p <sha>` to a scratch dir. Also write the path
  names, the second field of `git rev-list --objects`. Then, per id,
  `{ /usr/bin/grep -rlaiE -e "$re" DIR || [ $? -eq 1 ]; } | wc -l`. The `|| [ $? -eq 1 ]` matters:
  under `pipefail`, grep's "no match" exit 1 otherwise stops the script silently. End by naming the
  ids checked. For a control, the same over `archive/pre-publish` finds P1, P2, P6 and P7.
- **The push:** a throwaway `GIT_ASKPASS` script in the scratchpad (mode 700) answers `Username*` with
  `x-access-token`, and anything else with `GITHUB_IRONICXYZ_PAT` read from `~/projects/ironik.xyz/.env`.
  Run `GIT_ASKPASS=<script> GIT_TERMINAL_PROMPT=0 git -c credential.helper= push …`, then delete the
  script, and check the output holds no token before showing it. Never put the token in a URL, an
  argument or printed output.

## Watch items (the mentor tracks them)

- the base upgrade lines come out when a trixie-slim newer than `a99cfc517144` ships the fixes (check
  with the registry recipe below)
- the load-dependent bench units: 7 `setup failed: hung` in the 004 lane (host load ~5) and 2 in this
  instance's traced run (then 24/24 ×3 alone). The mentor wants it re-established in the post-T018
  lane before it is read as a regression
- the publishing maintenance cycle after 12 s0 merges: internal hostname and home paths out of
  tracked files, plus a gitleaks rule (operator 2026-10-02T04:46Z). Add no new ones meanwhile
- the load-dependent unit timing: `test_agentio_startup` p95 and the `test_bench_runner` rb4 setup under
  `call_s=2` (`tests/unit/test_bench_runner.py:25`). Don't change them now; they belong to 002 slice
  1's driver hardening
- the baselines' `review_by` 2026-12-27; vanilla's libcurl Criticals; feature 12's credential-class
  Criticals
- the 40 KB uncapped-output question (002 slice 1); bench driver hardening (02 slice 1)
- 2.24.0 observations for the mentor to relay (004 § Cycle 1): specify's expanded text clobbering
  `$1` (gone: `specify.md` has had no `$1` since 2.32.0 at the latest); the scope matcher misses dotfiles; specify's reuse path takes the slug from the description; D74
  counts visual-alignment's own literal as unattributed
- plugin defects relayed upstream:
  - the four from Cycle 6 are fixed in 2.24.0: the modify-branch fallback (now `lib/features-location.sh`,
    which says so on stderr), positional parameters, the scope matcher, and gap attribution. Verify
    them in the field on 12's cycle.
  - `ship.md` never assigned `FEATURE_DIR` (relayed 2026-10-02): **fixed as D77**. Its `quality-source`
    block derives it from the branch when unset (`lib/features-location.sh`). `ship.md` is byte-identical
    from 2.32.0 to 2.36.0.

## How work is done here (facts that aren't obvious)

### Environment

- **No Docker daemon in this container, and none can run here** (research R10).
  - The operator (or the mentor, at the operator's request) runs `make build`, `make test`,
    `make scan` and `make demo` on the host, from the same checkout. The operator's home directory is a bind mount.
  - Read the results in `tests/out/` (`summary.json`, `e2e.tap`, `unit.txt`, `startup.json`) and in
    `scan/out/verdict.json`.
  - Never report an image-level criterion as passed from host-lane evidence.
- **Host lane:** `make test-host PYTHON=<venv python>`. The scratch venv is gone after a clear.
  Recreate it:
  `python3 -m venv <scratchpad>/venv && <scratchpad>/venv/bin/pip install pytest==8.4.2 mypy coverage shellcheck-py`.
  ruff is on PATH; shellcheck comes from the venv.
- **Lint, all of it:**
  - `ruff check tools tests scan bench && ruff format --check tools tests scan bench`
  - `<venv>/bin/python -m mypy` (configured in pyproject; `tools/bin/run` is listed there)
  - `find . -path ./.git -prune -o \( -name '*.sh' -o -name '*.bash' -o -name '*.bats' \) -print | xargs <venv>/bin/shellcheck -x -P tests/e2e:tests/host`
- **Don't grep the whole tree for test strings.** `scan/out/` holds megabytes of scanner JSON.
  Restrict the search to `tests/`, `tools/`, `bench/` and `image/`.

### Coverage (the merge bar: 90% per language, measured in the workspace)

The tests copy `timelike` and `timelike-conform` into pytest temp directories and run them as
subprocesses. So coverage needs both an `include` for those copies and a `[paths]` map back to
`tools/bin/`. `run`'s units run `tools/bin/run` in place, which `$PWD/tools/*` already covers. Write
this rc to `<scratchpad>/covrc`, with `$PWD` = `code/` and `$S` = the scratchpad:

```
[run]
branch = True
parallel = True
data_file = $S/cov/.coverage
include =
    $PWD/tools/*
    $PWD/scan/*
    $PWD/bench/*
    /tmp/pytest-of-*/**/timelike
    /tmp/pytest-of-*/**/timelike-conform
    /tmp/pytest-of-*/**/timelike-bench
    /tmp/pytest-of-*/**/run
[paths]
bin =
    $PWD/tools/bin/
    /tmp/pytest-of-*/*/*/good/
    /tmp/pytest-of-*/*/*/conf/
    /tmp/pytest-of-*/*/*/hidden/
    /tmp/pytest-of-*/*/*/probe/
    /tmp/pytest-of-*/*/*/conform/
benchbin =
    $PWD/bench/bin/
    /tmp/pytest-of-*/*/*/bin/
[report]
show_missing = True
```

Then run:

```
rm -rf $S/cov && mkdir -p $S/cov
setsid --wait timeout -k 10 900 env COVERAGE_PROCESS_START=$S/covrc $S/venv/bin/python -m coverage run --rcfile=$S/covrc -m pytest -q tests/unit </dev/null
$S/venv/bin/python -m coverage combine --rcfile=$S/covrc -q
$S/venv/bin/python -m coverage report --rcfile=$S/covrc
```

Notes:
- coverage 7.x installs its own `a1_coverage.pth`, which acts only when `COVERAGE_PROCESS_START` is
  set, so no extra `.pth` is needed.
- The start-up test skips itself under tracing.
- `[paths]` patterns must not end in a wildcard. A bad rc silences every process, the parent included.
- The full traced run takes about 4.5 minutes.
- Last result (003 T016, 2026-10-01): **675 passed, 1 skipped; 97% overall**:
  - `run` 96%, agentio 94%, conform 92%, timelike 96%
  - bench 98%, scan 99%
- The dispatcher is shell, so Python coverage does not measure it.

### Measuring start-up

Run each tool with the venv's Python **without `-I`**, because `-I` ignores PYTHONPATH and so agentio
fails to import. **Assert every exit code.** Cycle 1's first measurement timed a crash.

Last result (host, 3.12, p95):
- `run --help`: 72 ms
- `run --json true`: 78 ms
- `timelike --help`: 59 ms
- the bare interpreter: 19 ms

### Workflow conventions

- **Per-task commits:** `[NNN] Tnnn: …`.
  - Each task gets a `decisions.md` section: INHERITED, FLAGGED, ASSUMED and ABSENT lines, a
    Verification line, and a `SCOPE:` line.
  - Compute the SCOPE line with implement's `scope-check` block, not by hand. Cycle 1 used a helper
    script in the scratchpad, gone after a clear, so rebuild it from `implement.md` § 6f. Pass the
    task's real FLAGGED yes or no: a helper default once wrote "yes" for a task that had none.
  - Tick the task in `tasks.md`.
  - **Commit** your own finished work without being asked, and never push.
- **Tallies for the cycle report:** use implement's `scope-tally` and `decision-tally` blocks
  (`awk` the `# >>> … # <<<` ranges out of `commands/implement.md`), never counts by hand.
- **`/specswarm:modify` on a feature with history:** Steps 5–7 say to *create* `impact-analysis.md`,
  `modify.md` and `tasks.md`. **Append a new section or phase instead**, or you overwrite earlier
  cycles. Provenance:
  - row 4 (N already audited): append nothing
  - row 7: classify each revision, then Step 9 in full or scoped mode, with a row in `audit-log.md`
  - never touch `prompt_revision`, `discovery_revision` or `source_prompt`
- **`cycle-report.md` is append-only.** One `## Cycle N — <send path>` per send, plus `### … addendum`
  sections for later verification. Group A is "not applicable — no marker on this path" (not
  dispatch). The mentor derives demo points, so never write `demo_points_reached`.
- **Implement step 10:**
  - The score of record is the plugin's own (`unknown` here: `run_tests` returns 2 because the system
    python3 has no pytest).
  - Record the project's host-lane figures **beside** it, labelled, in `.specswarm/metrics.json` →
    `NNN.project_measurements_not_scored`. Never score them (memory: no judgment-filled scores).
- **Delegation to subagents works.**
  - Give each delegate its own files. Tell it not to commit and not to touch `../bridge`, `../plan`,
    `.specswarm/` or `tools/`. Have it report decisions in the INHERITED / FLAGGED form.
  - Review its work, then commit it yourself, one task per commit.
  - Writing e2e tests from the CLI contract **before** the tool exists paid off. Review against them
    caught a contract departure in this instance's own code (003 T008).
  - Then **run each fixture script the test drops into the container through the real tool on the
    host**, sandboxed: that is how the COLUMNS cut of the verdict was found.
- **Raising questions:** a FOR-MENTOR item with a stable heading. If an item conflicts with the send's
  instructions ("stop and raise it"), stop: don't specify on a reading plan has not confirmed (Item 9).

### Feature 005 (recover, prompt 07): what later work inherits, and how it was built

**The design** (spec D-1 to D-10; the contract is `contracts/recover-cli.md`):
- **Files.** `tools/bin/snapshot` holds everything: the workspace rules, the store, the walk, the
  planner, apply and verify, and both commands' entry points (`main`, `undo_main`, `UNDO_TOOL`).
  `tools/bin/undo` is about 20 lines: it loads `snapshot` from its own realpath with `SourceFileLoader`
  (R8). Tests and conform must install **both** into one bin dir.
- **Workspace.** The nearest ancestor holding a `.git` entry (found with `lstat`, never git), else the
  current directory. Refused at `/`, `$HOME` (and the passwd home), their ancestors, and when it would
  contain the store.
- **Store.** `<scratch root>/<session>/snapshots/<sha256(ws)[:16]>/`, holding `workspace`, `lock`
  (flock, 10 s wait), `next`, `snaps/<id>.json` and `objects/<aa>/<sha256>` (0400, temp then rename).
  `artefacts/` holds `Cut` lists.
- **`.git` at any depth** is out of scope: never captured, removed or followed. `check_rel` refuses it,
  and `_parent_checked` (lstat on every component) refuses to write through a symlink.
- **Exclusions:** the per-file limit; the size cap, cutting the largest files first (ties by path);
  non-regular files; unreadable files. The entry cap refuses (`more than <cap>`).
  The variables are `TIMELIKE_SNAPSHOT_MAX_{BYTES,FILE_BYTES,ENTRIES}` (256 MiB / 64 MiB / 50,000;
  `0` = none).
- **Outcomes are verdicts:** a refusal, "no snapshot" and a failed verification are a `Result` on
  stdout (`do instead:` line, `data.remedy`, exit 1 or 3), because conform's probes run in the home
  directory in the image. Usage, lock and I/O stay stderr errors.
- **`undo`:**
  - With no ID it restores the newest snapshot that is **not** a safety snapshot (`before undo …`),
    so it is idempotent (rule 7).
  - `--yes` takes a safety snapshot, applies, then re-plans to verify.
  - Without `--yes` it exits 4 with the envelope (plan bounded at the limit).
  - Over the output limit, `--yes` and take output a `Cut` whose `more` is `sed -n` over an artefact,
    never a re-run.

**Recipes that worked:**
- **e2e on the host with no Docker:** a scratchpad `docker` stand-in, and bats-core v1.14.0 cloned
  into the scratchpad.
  - `exec`: parse `-i`, `-t` and `-e K=V`, drop the container name, answer
    `cat /opt/timelike/REVISION` with `$GIT_SHA`, then
    `exec env COLUMNS=1000 HOME=<stand-in home> PATH=<tools with the shebang rewritten, no -I>:/usr/bin:/bin PYTHONPATH=tools/agentio …`.
  - `inspect` and `image`: echo a name, or `$GIT_SHA`.
  - `run` (used by `pyq`): skip the flags and the image, then `python3 "$@"`.
  - Run as `PATH=<stub>:$PATH GIT_SHA=x AGENT_CONTAINER=x bats --tap <files>`, under
    `setsid --wait timeout`. It found two real test bugs.
  - It is advisory: no `/etc/gitconfig` layer, no dispatcher, host git and Python.
- **Per-task commits:** a scratchpad `commit-task.sh TASK FLAGGED DECFILE MSG FILES…`. It appends the
  decisions section, runs the deny-list check, commits, computes the SCOPE line with the installed
  `scope-check` block, ticks the task, and amends. Write each task's decisions section to a file first.
- **Delegates writing tests from the contract** before the tool exists, as in 003: 70 of 71 units passed
  first time against the tool. A contract change made mid-task reached them by `SendMessage` to their
  agent IDs.
- **Coverage of tools run as subprocesses:** an rc with `include` for `tools/bin/<tool>` plus
  `/tmp/pytest-of-*/**/<tool>`, and `COVERAGE_PROCESS_START` (the 001 recipe below). Result: 93%.
- **specify's expansion pastes the arguments into double-quoted strings,** so a quoted argument such as
  `"07 recover"` breaks the shell. Run its blocks from the installed file with `ARGUMENTS` as a
  variable.

### Feature 004 (Adele): what later work inherits, and how it is built here

**The design** (spec D-1 to D-9):
- The client is `tools/bin/adele` (agentio; `status` always returns a Result).
- Adele is `adele/` (Go module `timelike/adele`):
  - `cmd/adeled`: `serve`, `check`, `extend`, `ledger [--json]`, `version`, `health`
  - `cmd/adele-standin`: `serve`, `list`, `health`
  - `internal/{grants,ledger,broker,standin}`
- The image is `adele/Dockerfile`, with stages `adele` and `standin`, FROM scratch, uid 10001, stamped
  through `-X main.revision`.
- compose:
  - `adele` and `adele-standin` (profile `standin`)
  - the one-shot `adele-secret`, which writes the canary into the volume `adele-secret`, `root:10001`
    0440 (D-8 revised)
  - the internal networks `adele-request` and `adele-standin`
- Adele's HTTP interface is on `:8480`: `/v1/health`, `/v1/grants`, `/v1/requests`. The check order is
  capability, ttl, ports, instances, budget. A 403 body carries `limit {name, allowed, needed}`,
  `extend`, `performed: false` and `ledger_id`.
- The extend command is `docker exec timelike-adele adeled extend <grant> <limit> <value…>`. The value
  is unquoted, and its words are joined.
- `make test` resets Adele's volumes and runs on `tests/e2e/fixtures/adele/grants.conf` (one grant per
  refusal cell). helpers: `stamp_check_adele`, `adeled`, `standin_list`/`standin_names`, `canary_bytes`,
  `adele_run_with_grants`, `pyq`.
- SC-4's no-leak search never passes the canary into the agent: it streams the agent's data out and
  greps on the runner.

**Host Go toolchain** (gone after a clear; nothing is installed on the host):
```
S=<scratchpad>; cd $S && curl -sSL -o go.tgz https://go.dev/dl/go1.27.2.linux-amd64.tar.gz
# verify sha256 against https://go.dev/dl/?mode=json, then: tar xzf go.tgz
cat > $S/goenv.sh <<X
export PATH=$S/go/bin:\$PATH GOPATH=$S/gopath GOCACHE=$S/gocache GOMODCACHE=$S/gomod GOFLAGS=-modcacherw GOTOOLCHAIN=local
X
. $S/goenv.sh; go install honnef.co/go/tools/cmd/staticcheck@v0.8.1; go install golang.org/x/vuln/cmd/govulncheck@v1.8.0
# (two installs: different modules. staticcheck v0.8.1 fails on Go 1.27.2; see Cycle 5's lane addendum)
cd adele && CGO_ENABLED=0 go test -count=1 -cover ./... && gofmt -l . && go vet ./... && $GOPATH/bin/staticcheck ./... && $GOPATH/bin/govulncheck ./...
```

**Host integration** (no Docker):
- Build both binaries with the Dockerfile's flags.
- Run them on loopback, Adele with `ADELE_LISTEN=127.0.0.1:18480` and the stand-in with
  `STANDIN_LISTEN=127.0.0.1:18481`. Set `ADELE_GRANTS`, `ADELE_DB`, `ADELE_CANARY_FILE`,
  `STANDIN_RECORD` and `ADELE_STANDIN_URL` to temp paths.
- Drive them with `PYTHONPATH=tools/agentio TIMELIKE_ADELE_URL=http://127.0.0.1:18480 <venv>/bin/python
  tools/bin/adele …`.
- Background each server, and kill it by pid file.

**Helpers this session used** (rebuild them in the scratchpad after a clear):
- `scope.sh TASK_START FLAGGED`: the installed `scope-check` block from `implement.md`, extracted with
  awk (`# >>> scope-check` … `# <<<`).
- `commit-task.sh TASK FLAGGED MSG FILES…`: commit, compute the SCOPE line, append it to
  `decisions.md`, tick the task, and `git commit --amend`. One commit per task.
- Step 10 and 9b: extract `quality-components`, `quality-scale`, `unmeasured-explains-itself`,
  `scope-tally` and `decision-tally`, and set `CLAUDE_PLUGIN_ROOT`.
  - Write unit-test and coverage reasons as "could not be run on this machine", so D74 attributes them.

**Delegation that worked:**
- Give each general-purpose subagent its own files, and the brief "don't commit; report bugs, don't fix
  non-owned files; t.Skip("BUG: …") so the suite stays green".
- Review each delegate's work, re-run its checks, then commit it yourself.
- The delegates found 7 real bugs. Briefs that named the real counterpart ("test against the REAL
  stand-in via httptest") kept the tests honest.

**Plugin 2.24.0 observations** (relay):
- specify's expanded text still substitutes `$1` with the first argument. Run the blocks from the
  installed file with `ARGUMENTS` as a variable.
- The scope matcher misses dotfiles (`.gitignore`, `.dockerignore`).
- On the reuse-branch path, specify slugs the directory from the description. Name the directory after
  the branch.
- D74 counts visual-alignment's own literal as unattributed.
- `ship.md` never assigns `FEATURE_DIR`.

### `run` (feature 003): what later features inherit

- **Pass-through** (discovery revision 9): a tool that runs a command the agent named returns that
  command's exit (126, 127 and 128+n included), and 124 only for its own limit.
  - It declares `Tool(passes_exit=True)`, and its result carries `cause` and `command_exit`.
  - agentio admits an exit outside the vocabulary only with `cause == "command"` and
    `exit == command_exit`.
  - conform's C6 runs such a tool as `<tool> --json sh -c 'exit 42'`.
  - Features 09 and 11 inherit this.
- **agentio's argv split for pass-through tools** (`_split_command`): the tool's options end at the
  first plain word or at `--`. It does not use argparse.REMAINDER, which differs between 3.12 and 3.14.
- **A tool-supplied `agentio.Cut`:** a tool that cuts its own output passes its sections and its own
  more command. agentio's generic cut offers "re-run with `--limit 0`", **which re-executes a wrapped
  command**. So a wrapper must always cut its own output once it is over the cap.
- **How `run` works:**
  - The output goes to one log file descriptor, never a pipe, and `run` waits on the process.
  - It is a child subreaper (`prctl` through `ctypes`, about 3 ms), and walks the tree by parent link
    in `/proc`. It does not use process groups, which nested `timeout` and `setsid` escape.
  - Log writers are found through `/proc/*/fd` plus `fdinfo` flags, writers only.
  - On timeout: SIGTERM, a 2 s grace, freeze rounds (SIGSTOP until no newcomer), SIGKILL + SIGCONT,
    then a re-scan for at most 3 s. Survivors are named, never claimed stopped.
  - On a normal exit: scan first, and settle 100 ms only if something is left running.
- **The verdict is line 2:** `verdict: exit E (cause words) · D s · N lines · log <abs path>`, then
  ` · detached: pid name, …` (at most five names, then ` (+N more)`), then ` · not stopped: …`.
- **Lines over the cap:** head ⌊L/4⌋, then up to ⌊L/10⌋ error lines from the gap (`L<n>:`), then
  tail ⌊L/2⌋. Then `more: sed -n A,Bp <log>`, one range over the whole gap.
- **Duration in the verdict is a result, not a timestamp** (plan, Item 10). The contract's line 18 now
  says so.

### Checking for a newer Debian base (Item 12)

The pin is the **index** digest. To compare it with Docker Hub without Docker:

```
T=$(curl -sS "https://auth.docker.io/token?service=registry.docker.io&scope=repository:library/debian:pull" | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')
curl -sSI -H "Authorization: Bearer $T" -H 'Accept: application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.list.v2+json' https://registry-1.docker.io/v2/library/debian/manifests/trixie-slim | grep -i docker-content-digest
```

The dated builds are `trixie-YYYYMMDD-slim` (list with `/v2/library/debian/tags/list?n=10000`) and come
about every 3–4 weeks. On 2026-10-01 the newest (`20260918`) was the pinned `a99cfc517144`. **Check a
premise like "bump to a current base" before acting on it**, and raise it if it fails, as Item 12's
follow-up did.

### e2e helper gotcha (003 lane fix 1)

- `assert_within` (`tests/e2e/helpers.bash`) reads **any** status 124 as the runner's own timeout. A
  test that **expects** 124 must instead decide the runner's timeout by elapsed time
  (`ELAPSED_MS < RUN_TIMEOUT*1000`), as `run_in` does. See SC-4's `run-exceeding-…bats`.

### Process safety (cycles 5 and 003)

- Run anything that forks or hangs as `setsid --wait timeout -k 5 N bash script.sh </dev/null`, with
  the pattern in a script file.
- Never `pgrep -f` or `pkill -f` a pattern that appears in your own command line: that killed the
  session's shell three times (exit 144).
- Find processes **only** through marker files they write (pid files, heartbeats). Kill them by those
  pids.
- An unsandboxed recursive dispatcher once left about 1,000 processes. A nested `timeout` leads its
  own process group.

### Bench facts (feature 002) that aren't obvious

- **dash's `kill` rejects `--`:** the wrapper's group kill is `kill -KILL -$t`.
- **On the bench's path (no TTY, no TERM), vanilla git's editor and pager traps fail fast.** The only
  guaranteed vanilla hang is a hook that never returns (research RB3).
- **Since 001 cycle 5,** `git-commit-hook-rejects` is a tie, and `git-commit-hook-hangs` ends on
  timelike's 60 s hook verdict. The bench's call limit is 120 s.
- **The report explains itself** (FR-9a). The first line is the operator's verbatim text.
- **Prompt 02 revision 8 (slice 1):** the verdict order is ending, turns, hangs, failed commands, with
  each call counted once. Today, `report.py:119` counts a hung call twice.

### Git hooks (001 cycle 5, research R11): what every later feature inherits

- `GIT_CONFIG_*` (command scope) points `core.hooksPath` at `/opt/timelike/git-hooks`: `dispatch` plus
  25 links. Each runs the hook git would have run, under GNU `timeout`.
- **Limit:** 60 s by default. Raise it with `TIMELIKE_HOOK_TIMEOUT` or `git config
  timelike.hookTimeout`.
- **Not linked:** push-to-checkout, proc-receive, fsmonitor-watchman. Under `env -i`, hooks run
  unbounded (T4, revision 8). P2 then rests on `run` and the harness's timeout.

### Plugin: specswarm (2.37.0 `d523530` loaded since the audit cycles, 2026-10-08; 2.36.0 notes below)

- **2.36.0** (`40d7149`, `4.0.1-botbaubble.2.36.0`) differs from 2.35.0 in `implement.md` and `specify.md`
  only, and only for D104 (values that were composed, now read from the clock):
  - implement 6a's `TASK_START=$(git rev-parse HEAD)` is now an executed fence, no longer prose. This
    instance's `start.sh` already read it.
  - specify gains the named block `spec-created-at` (`CREATED_AT` from the clock) and reads
    `REGENERATED_AT` in `regenerate-keep`. **Run both from the installed file**, as with every block.
- **Unchanged in 2.36.0, so these recipes still hold:**
  - implement's blocks still use awk `$0` and `$1` (`scope-tally`, `decision-tally`), which the
    expansion clobbers;
  - specify still pastes the description into `DESCRIPTION="$ARGUMENTS"`, so a quoted description breaks
    the expanded text (the 007 occurrence);
  - `scope-check` is identical to 2.32.0's;
  - `ship.md`, `analyze-quality.md`, `lib/quality-standards-parser.sh` and `lib/tech-stack-parser.sh` are
    identical to 2.32.0's, so the ship recipe and step 10 hold;
  - every named block they use exists (`tech-stack-classify` and `tech-stack-taskscan` are in
    `plan.md` and `tasks.md`).
- **Upstream, still open** (bridge/history 2026-10-06T17:17:44Z): `$ARGUMENTS` (the 007 occurrence is
  owed), and `complete` (D102) has not been asked.
- The notes below date from 2.21–2.27, as written then.

- The session loaded 2.21.0, which the send called 2.20.0. Say which version ran in the cycle report
  (lore Q002: a session keeps the version it loaded). 2.21.0 fixes build's Stop hook, but build is
  still never run here.
- **The expanded command text clobbers positional parameters inside shell functions** (`grep -qxF
  "--from-send"`, `qr_get`). Decide from the files. Specify's provenance fields were written by hand
  from the send's header lines.
- **`analyze-quality` and implement step 10 report `unknown` for timelike.** **Never fill components
  by judgment.**
- **`ship`** (2.20.0 and later): the summary follows the gate state, and `NNN-*`, `modify/` and
  `bugfix/` branches get a `quality-report.json`. The threshold is 0 and `enforce_gates: false`, so an
  unknown gate warns. **Step 4 (`complete`) needs stdin**, so merge by hand.
- **Parsers:** `lib/quality-standards-parser.sh` and `lib/tech-stack-parser.sh`. `ctypes` reads as
  `unlisted` there; it is Python stdlib, covered by "stdlib only".
- **Running a command's blocks as a script:** the installed command files say
  `PLUGIN_DIR="${CLAUDE_PLUGIN_ROOT}"`. The session fills that in when it expands the command; a
  script does not. Set `CLAUDE_PLUGIN_ROOT` to the cache path the session expanded, or the libs read
  as missing. 003's first ship attempt hit this and fell back to an enforcing 80% gate (discarded).
- **Ship recipe that worked (003, 2.22.0):**
  - extract analyze-quality's `analysis-context` … `quality-report` blocks with awk, using `MODULES` =
    001's 8 (`tools/agentio tools/bin scan image scripts bench/benchlib bench/bin bench/images+run.sh`)
  - extract ship's `quality-source`, `quality-threshold`, the threshold echo lines and
    `quality-gate`
  - record both outputs verbatim; step 4 needs stdin, so merge by hand
  - known false line: `quality-report.json` `modules_scored: 8` beside "8 unscored" (the mentor
    relayed it upstream)
- Upstream defects are noted for the mentor to relay. This instance writes nothing in
  `~/projects/block24-mentor/`.

### Environment layer (feature 001 slice 1): what future features inherit

- **Every bash shell** sources `/etc/timelike/shell-env.bash`: through `BASH_ENV`, `/etc/profile.d/10-…`
  and `/etc/bash.bashrc`.
  - It sets job counts from cgroup `cpu.max` and affinity, each only when unset.
  - It strips secret-shaped variables, except names in `TIMELIKE_ENV_ALLOW` and `GIT_CONFIG_KEY_n`.
- **Static ENV:** `TZ=UTC` and `PYTHON_BASIC_REPL=1`. `sh -c` and direct execs get neither the job
  counts nor the strip.
- **`timelike-conform`** judges a tool that cannot execute (127/126) instead of crashing.

## Key paths

| What | Where |
|---|---|
| Sends for 01 | `../bridge/sends/01-rev2-…` (cycles 1–3), `01-rev6-20260928-231531.md` (cycle 4), `01-rev7-20260929-094055.md` (cycle 5), `01-rev9-20261001-191224.md` (cycle 6, merged at `3d891ae`) |
| Sends for 12 | `../bridge/sends/12-rev2-20261002-042951.md` (discovery 9; Cycle 1, built as feature **004**, superseded) · **`12-rev2-20261002-055142.md` (discovery 10; ACTIVE — Cycle 2: T018 + audit)** |
| Sends for 02 | `../bridge/sends/02-rev1-20260929-000641.md` and `02-rev1-20260929-080659.md` (cycle 1) |
| Sends for 03 | `../bridge/sends/03-rev1-20261001-043339.md` (cycle 1). The earlier `03-rev1-20260930-223345.md` was superseded and never built |
| Feature 003 | `.specswarm/features/003-concluding-run/`: spec, research (R1–R14), plan, data-model, quickstart, contracts (`run-cli.md`, `output-contract-amendment.md`), tasks, decisions, cycle-report |
| `run` | `tools/bin/run`; units `tests/unit/test_run.py` (43); e2e `tests/e2e/run-*.bats` (5 files, one per criterion) |
| Contract module, tools | `tools/agentio/agentio.py` (passes_exit, Cut, `_split_command`), `tools/bin/timelike`, `tools/bin/timelike-conform` (C6 pass-through) |
| Output contract | `.specswarm/features/001-agent-shell-baseline/contracts/` (`output-contract.md` § Exit codes scope and line 18; `agent-info.schema.json` passes_exit; `event.schema.json` exit 0–255; `conformance.md`) |
| Hook dispatcher | `image/rootfs/opt/timelike/git-hooks/dispatch` (+25 links) |
| Feature 001 | `.specswarm/features/001-agent-shell-baseline/` (spec UNAUDITED at discovery 10 until its next modify; its contracts change in 004 T018) |
| Feature 004 | `.specswarm/features/004-adele-grants/` (spec D-1..D-9, research R1–R8, contracts adele-http/adele-cli, tasks T001–T023 with T018 held, decisions, cycle-report § Cycle 1); code `adele/`, `tools/bin/adele`, e2e `tests/e2e/adele-*.bats` and 4 others, fixtures `tests/e2e/fixtures/adele/` |
| Feature 002 | `.specswarm/features/002-speedup-bench/`; bench in `bench/` |
| Image, env hook | `image/Dockerfile` (its `COPY tools/bin/` ships `run`), `image/rootfs/etc/timelike/shell-env.bash`, `compose.yaml`, `pins.env` |
| Tests | `tests/unit` (pytest; `schema.py` is a stdlib schema subset that now has `maximum`), `tests/e2e` (bats), `tests/host`, `tests/run.sh` |
| Scan gate | `scan/scan.sh`, `scan/evaluate.py`, `scan/baseline/*.json` |
| Governance | `.specswarm/constitution.md` (1.4.2), `tech-stack.md` (1.3.1), `quality-standards.md`, all `[2..11]` (revision 11 audited at `586e298`) |
| Metrics | `.specswarm/metrics.json` (`003`: plugin score unknown; project figures beside it). Scan baselines `scan/baseline/timelike-{agent,vanilla,bench-driver}.json`, all reviewed 2026-10-01 (80/79/51 entries after `09e2c0b`) |
| Sends for 07 | `../bridge/sends/07-rev1-20261003-013915.md` (Cycle 1, built as **005**) · `07-rev11-20261004-002459.md` (superseded, never built) · **`07-rev11-20261004-030207.md` (ACTIVE: revision 11, corrected; Cycle 2)** |
| Feature 005 | `.specswarm/features/005-recover/`: spec (D-1..D-10), research R1–R9, data-model, `contracts/recover-cli.md`, tasks T001–T015, decisions, cycle-report § Cycle 1; code `tools/bin/snapshot`, `tools/bin/undo`; units `tests/unit/test_snapshot.py`, `test_undo.py`; e2e `tests/e2e/snapshot-*.bats`, `restore-*.bats`, `version-control-*.bats`, fixture `tests/e2e/fixtures/recover-repo.sh` |
| Register to mentor | `FOR-MENTOR.md` (Items 1–17 closed) |
