> Redacted for publication, 2026-10-02 (`bridge/sends/maint-publish-redaction-20261002-183624.md`): internal host names, absolute paths and a personal name replaced. No other change.

# Cycle report — 001 agent shell baseline

Append-only. One section per cycle, where a cycle is one archived send built to acceptance. Written by
the code instance; the mentor reads this file and never writes into it.

## Cycle 1 — bridge/sends/01-rev2-20260928-063549.md

**Written:** 2026-09-28, at the end of `/specswarm:implement`, not in dispatch mode. **Branch:**
`001-agent-shell-baseline`, not merged (quality gate FAIL, see `not_verified`).

**Status in one line:** everything in slice 0 is written, and the host lane passes. **No acceptance
criterion has been re-established in the image**, because this development environment has no
Docker daemon. The operator runs the Docker lane (`make test`) on the host, where the repository
lives on a bind mount.

### Group A — cited from `.implement-complete`

Group A: not applicable — no marker on this path

### Group B — copied from the send

| Field | Value |
|---|---|
| source_send | bridge/sends/01-rev2-20260928-063549.md |
| source_prompt | plan/.discover/prompts/01-agent-shell-baseline.md |
| prompt_revision | 2 |
| discovery_revision | 3 |
| slice | 0 |

### Group C — written by the code instance

**delegations**

The coordinator (this instance) wrote `agentio`, `timelike`, `timelike-conform` and their unit tests,
and reviewed and committed every delegated task.

| # | Delegate | Scope | Tasks |
|---|---|---|---|
| 1 | research subagent | bash startup files per invocation style; git non-interactive config, verified by experiment on bash 5.2.21 / git 2.43.0 and against Debian trixie's actual base-files and bash packages | Phase 0 → research.md R1–R5 |
| 2 | research subagent | pins read from registry APIs; uv/CPython layout; Docker seccomp, capabilities and setuid; bats from outside the container | Phase 0 → research.md R6–R9 |
| 3 | image subagent | Dockerfile, rootfs config, compose, host env-layer check | T009–T012, T020; content for T016, T019, T022, T025 |
| 4 | e2e subagent | bats suite (118 tests), Docker-lane driver, demo, netfilter probe | T013–T015, T017, T018, T021, T023, T024, T030, T032 |
| 5 | scan subagent | supply-chain gate and its evaluator; later, report-path tests (two evaluator bugs found and fixed) | T034, T035 and addendum |

**criteria_reestablished**

| Criterion | Mode |
|---|---|
| 01 · "`git log`, `git diff`, `git commit` without a message, and `git rebase --continue` each exit within 20 seconds" | unconfirmed |
| 01 · "non-interactive `bash -c` or `bash -lc` and the environment's pager, editor, prompt and colour defaults are all in effect" | unconfirmed |
| 01 · "A git operation that would need credentials fails fast with a non-zero exit instead of prompting" | unconfirmed |
| 01 · "The agent's user cannot run any command as root, cannot change firewall rules, and cannot read files owned by Adele" | unconfirmed |
| 01 · "A conformance check runs against every timelike tool on PATH and fails when any tool lacks" | unconfirmed |
| 01 · "Two Peer agents running concurrently each write to their own scratch space" | unconfirmed |
| 01 · "DEMO: the Agent runs `git commit`, `git rebase --continue` and `git log` in the container" | unconfirmed |

Every criterion is `unconfirmed` because none has been executed in the image; that is the only place
these criteria live. The host lane produced **evidence, not criterion passes**. It is listed under
`not_verified` so it is not mistaken for either.

**reconcile_mode:** full. This is the first build. Every slice-0 criterion in the send was specified,
planned, tasked and written. Slice-1 criteria are out of scope by the send.

**not_verified**

1. **All six automated criteria in the image.** 118 bats tests were written, but none was run against the image.
   - The Docker lane was never run, because this environment has no daemon (research R10).
   - A fake-`docker` smoke run exercised the test code with the image's environment on the host. A negative control (editor, pager and prompt defaults broken on purpose) failed every git pty case with rc 124, without hanging.
   - **Next step:** the operator runs `make test` on the host, and results land in `tests/out/`.
2. **SC-7 (demo → D1).** No person has watched it. `make demo` is ready.
3. **The build itself:**
   - The image has never been built.
   - Unconfirmed: that uv 0.12.19 offers CPython 3.12.14, and the exact interpreter directory name (research R6/R9 caveats). The Dockerfile fails loudly if either is wrong.
   - The pinned digests are unverified until the first pull.
4. **H8 stamp end to end** (T039): that the image label, `timelike --agent-info` and HEAD agree. Only the Makefile's refusals were verified here.
5. **Start-up budget in the image** (T042; quality-standards C2). Host p95 is 56.7 ms, which is advisory.
6. **Supply-chain gate** (T036). No scanner has run. The gate's logic has 54 host tests, all on synthetic scanner JSON.
7. **`make lint`**, the pinned-container form. Its host equivalents are clean: shellcheck 0.11.0, ruff, `mypy --strict`.
8. **Host-lane evidence**, advisory and file-level only:
   - 150 unit tests pass, and 1 start-up test is skipped under tracing.
   - Coverage is 94% line+branch (agentio 92%, timelike 96%, timelike-conform 93%, scan/evaluate.py 96%).
   - The env-layer check is 32/32, with self-checks showing it fails when a default is removed.
   - The netfilter probe printed `EPERM` **from this development container**, not from the image.
9. **Quality gate:** scaled 43/100 against a minimum of 90, so **FAIL**, and the branch is not merged.
   - Integration is 0/15 because it was unmeasured.
   - Browser, bundle and visual (0/50) do not apply to this project.
   - Host-lane units and coverage scored full marks.
   - Detail in `.specswarm/metrics.json`.
10. **No LICENSE file.** The README says MIT; adding the licence text is the maintainer's act.

**changed_other_features:** none. No other feature exists. Governance work the send carried in:

- **Supply-chain scan gate** built (`scan/`, `make scan`), as the send directed (FOR-MENTOR 5.1; H9). It is governance, not an acceptance criterion of prompt 01, and **not verified**: see `not_verified` 6.
- **Shared infrastructure** later features inherit:
  - `pins.env`, the Makefile, `compose.yaml`
  - `agentio`, the contract module every future tool builds on
  - the two-lane test layout
- **No governance file changed** in this cycle. `.specswarm/metrics.json` was created.

**process_failures_recorded**

1. **The development environment cannot run the product.** This session runs in a container with no daemon and no `CAP_SYS_ADMIN`; passwordless sudo doesn't change that.
   - This is P1's own violation example, met while building timelike.
   - It was escalated to the user, who decided the operator runs the Docker lane on the host.
   - Consequence for dispatch: an unattended code-track run here **cannot verify any image-level criterion**.
2. **Plugin: `lib/test-framework-detector.sh` is not installed** in specswarm 2.11.0. `implement` step 10 depends on it; tests were run and parsed by hand, and scoring was recorded as the plugin prescribes.
3. **Plugin: the quality score formula is web-oriented.** 50 of its 115 points (browser, bundle, visual) can never be earned by a CLI/infra project. So a Strict project with every test green scores at most 56/100 and always fails a 90 gate. This needs a governance or plugin decision, not a workaround.
4. **`make lint` as first written could never run.** It used `sh -c` in the uv image, which is distroless. Caught in review and fixed in T038.
5. **My per-task commit helper mis-recorded FLAGGED** on one addendum section, whose heading was `### T008 (addendum)`. Corrected in decisions.md by recomputing from the section's own FLAGGED line.
6. **Stale lore in the send.** Lore `specswarm` Q001 says `/specswarm:ship` needs `quality_threshold:` at column 0, and that this project "already" carries it.
   - Both are out of date: specswarm 2.11.0's `ship` reads `min_quality_score:`.
   - This project removed the `quality_threshold` key in `04cca40`.
   - The lore entry needs an update, not the project.
7. **Scope records:** from the plugin's own `scope-tally` block:
   `planned=42 recorded=37 unplanned=0 unrecorded=5 in=29 out=7 none=4 unknown=0 flagged=19 flagged_out=4 other=21 other_out=3`.
   - The 7 `out` records are all infrastructure or register files that tasks.md never names: `.gitignore`, `.dockerignore`, `.shellcheckrc`, `Makefile` (×3), and `metrics.json` + `FOR-MENTOR.md` (T041).
   - Unrecorded: T016, T019 and T022 were logged together under T025's section; T036 and T042 need the Docker lane.
   - It is a record, as the plugin intends.
   - No decision was labelled `confidence: low` (0 of 31 FLAGGED).

**retired_prompts_seen:** none.

### Cycle 1 — verification addendum (2026-09-28, after the Docker lane and the demo)

Appended, not rewritten: the section above records the state when implement ended. This records what
the operator's runs established afterwards.

**Runs.**
- **Docker lane:** `make test` on the host, 2026-09-28T12:08:54Z → 12:13:40Z, exit 0.
  - The image was stamped with commit `b235f39`, the commit under test.
  - Results in `tests/out/`: `summary.json`, `e2e.tap` and `report.xml`. All six steps passed: preflight, build, up, runner, e2e, unit.
- **Demo:** `make demo`, watched by the operator.
- **Scan:** `make scan`. Output in `scan/out/`.

**criteria_reestablished** (supersedes the modes above)

| Criterion | Mode |
|---|---|
| 01 · "`git log`, `git diff`, `git commit` without a message, and `git rebase --continue` each exit within 20 seconds" | executed [tests/e2e/git-log-diff-commit-rebase-exit-within-20-seconds.bats, 36/36] |
| 01 · "non-interactive `bash -c` or `bash -lc` and the environment's pager, editor, prompt and colour defaults are all in effect" | executed [tests/e2e/bash-c-and-bash-lc-defaults-in-effect.bats, 12/12] |
| 01 · "A git operation that would need credentials fails fast with a non-zero exit instead of prompting" | executed [tests/e2e/credentials-fail-fast-and-hooks-off.bats, 40/40] |
| 01 · "The agent's user cannot run any command as root, cannot change firewall rules, and cannot read files owned by Adele" | executed [tests/e2e/agent-cannot-run-as-root-change-firewall-or-read-adele.bats, 18/18] |
| 01 · "A conformance check runs against every timelike tool on PATH and fails when any tool lacks" | executed [tests/e2e/conformance-check-over-every-timelike-tool-on-path.bats, 10/10] |
| 01 · "Two Peer agents running concurrently each write to their own scratch space" | executed [tests/e2e/peer-agents-write-to-own-scratch-space.bats, 2/2] |
| 01 · "DEMO: the Agent runs `git commit`, `git rebase --continue` and `git log` in the container" | observed by the operator, 2026-09-28 |

**Demo, as the operator watched it.** Nine runs, three commands in each of three terminal modes, each
returning in 0.094–0.133 s:
- `git commit`: rc 1 (empty message aborted)
- `git rebase --continue`: rc 0
- `git log`: rc 0

No editor, pager or prompt appeared. The operator confirmed sub-second responses.

**Also established:**
- 151 unit tests passed on the image's own interpreter (`/opt/timelike/python/bin/python3 -I`),
  including the start-up budget. That discharges quality-standards C2; the figure was not printed.
- The H8 stamp matches end to end: `stamp_check` ran in every bats file's setup, and the SC-5
  revision test passed.

**Supply-chain gate: FAIL**, the gate working as designed. This is governance, not a prompt-01
criterion.
- **Passed:** the SBOM (640 packages), pip-audit (1 distribution, 0 matches) and gitleaks (0
  findings across history).
- **Grype:** 258 matches, of which **81 block**.
  - **80 are unfixable** High/Critical findings in Debian trixie OS packages. They are **38 distinct
    CVEs**: one CVE counts once per package that carries it.
  - By image layer, **49 come from Debian's own base layer** (ncurses, util-linux, login, libc,
    perl-base, acl). **31 come from this image's package install**: libcurl (18, including 8
    Critical), expat and perl via `git`, and openssh-client (3, including 1 Critical).
  - **1 is fixable under the rule as written:** CVE-2026-82049 (`tarfile`, "CPython 3.13 and
    earlier") against the pinned python 3.12.14. Grype gives the fix as `3.14.0b1`, meaning the fix
    exists only on the 3.14 line.
- **No exemptions were written.** Plan must decide how to handle 80 unfixable findings before anyone
  writes rows; see FOR-MENTOR Item 7. The branch stays unmerged.

**Governance moved during the cycle.**
- Discovery went to revision 4 at 06:40, five minutes after this send (revision 3 at send time), so
  the send is **stale on the discovery axis** and not on the prompt axis. Prompt 01 is unchanged; all
  17 prompts were reviewed.
- Revision 4 changes only the supply-chain exemption rule. It is applied: governance commit
  `224858e` (all three files `[2, 3, 4]`, constitution 1.1.1) and the gate (`9d17f32`: enforced
  review date, 90-day cap, escalation output naming the exact edit).
- The spec needs no change for revision 4. Its criteria don't mention the gate.

**Quality score after the Docker lane.**
- Integration rose to 15/15, giving a raw score of 65/115, **scaled 57/100**. That is still FAIL
  against 90, as FOR-MENTOR Item 6 predicted: browser, bundle and visual (50 points) can't be
  earned by this project.
- The score is not the reason the branch is held. The supply-chain gate is.

**not_verified, updated.** Items 1–7 of the original list are now verified, and items 8 and 10 stand.
Open:
- a LICENSE file
- the in-image start-up figure (passed, not printed)
- the supply-chain gate decision (FOR-MENTOR Item 7)

## Cycle 2 — bridge/sends/01-rev2-20260928-131708.md

**Written:** 2026-09-28, after the code changes for this send and before the operator's Docker-lane
runs, not in dispatch mode. **Branch:** `001-agent-shell-baseline`, not merged.

**Status in one line:** everything this send moved is applied and passes the host lane. The image has
not been rebuilt, and the new baseline waits on a person's review, so no criterion is re-established
yet and `make scan` will FAIL until that review.

**What this cycle is.** The same prompt (revision 2), re-sent because discovery moved to revision 5
underneath it. The spec and its criteria are unchanged, and the spec was not regenerated or modified,
as the send directs. Tasks T043–T048 were added to `tasks.md` (Phase 11).

### Group A — cited from `.implement-complete`

Group A: not applicable — no marker on this path

### Group B — copied from the send

| Field | Value |
|---|---|
| source_send | bridge/sends/01-rev2-20260928-131708.md |
| source_prompt | plan/.discover/prompts/01-agent-shell-baseline.md |
| prompt_revision | 2 |
| discovery_revision | 5 |
| slice | 0 |

### Group C — written by the code instance

**delegations:** none. This instance did every task in the cycle itself.

**criteria_reestablished**

| Criterion | Mode |
|---|---|
| 01 · "`git log`, `git diff`, `git commit` without a message, and `git rebase --continue` each exit within 20 seconds" | unconfirmed |
| 01 · "non-interactive `bash -c` or `bash -lc` and the environment's pager, editor, prompt and colour defaults are all in effect" | unconfirmed |
| 01 · "A git operation that would need credentials fails fast with a non-zero exit instead of prompting" | unconfirmed |
| 01 · "The agent's user cannot run any command as root, cannot change firewall rules, and cannot read files owned by Adele" | unconfirmed |
| 01 · "A conformance check runs against every timelike tool on PATH and fails when any tool lacks" | unconfirmed |
| 01 · "Two Peer agents running concurrently each write to their own scratch space" | unconfirmed |
| 01 · "DEMO: the Agent runs `git commit`, `git rebase --continue` and `git log` in the container" | unconfirmed |

Cycle 1 executed all six automated criteria and the operator observed the demo, but on an image this
cycle changes: a new interpreter (3.14.7) and no `openssh-client`. Those results do not carry over.
The SC-3 ssh cells are rewritten, and nothing has run them yet.

**reconcile_mode:** scoped. Examined:
- what moved under the unchanged prompt: discovery revision 5, `stack.md` at plan `d606ed1`, and the
  governance-only score ruling
- where each of those touches this feature: the interpreter pin, the image's package set, the SC-3 ssh
  tests, and the supply-chain gate

Not re-examined: criteria and code this send left unmoved.

**not_verified**

1. **The image build**, with Python 3.14.7 and without `openssh-client`. The Dockerfile's interpreter
   checks and its new "no ssh on PATH" check run at build time.
2. **All six automated criteria and the unit suite on the image's interpreter** (`make test`). The SC-3
   ssh cells now assert that git reports `cannot run ssh`. That exact string is an assumption until
   the run (decisions T044).
3. **The supply-chain gate on the new image** (`make scan`). The committed baseline has
   `reviewed` / `review_by` unset **on purpose**: a person reviews the reasons and sets the dates
   (decisions T046). Until then the gate FAILs, with one escalation naming both fields. With the dates
   filled in (a scratch copy only), the evaluator over the cycle-1 scan baselines 77 findings and
   blocks exactly the 4 that T043 and T044 remove.
4. **SC-7 (demo)** on the new image. No person has watched it.
5. **The baseline's reasons** are a code instance's draft. Each Critical names what would void it
   (credentials or an egress proxy arriving with Adele, feature 12).
6. **Host-lane evidence**, advisory:
   - 174 unit tests pass (Python 3.12 venv)
   - `scan/evaluate.py` 99% line+branch
   - env-layer check 32/32
   - ruff, `mypy --strict` and shellcheck clean across the repo
7. Open from cycle 1: a LICENSE file, and the in-image start-up figure (passed, not printed).

**changed_other_features:** none by feature, since no other feature exists. Shared ground every later
feature inherits:
- **Governance** (`d980e4d`): constitution 1.2.0 (H9 rewritten for the baseline rule), tech-stack 1.3.0
  (Python 3.14.x, notes 6–7), and quality-standards. All three are `governance_audited_against:
  [2, 3, 4, 5]`.
- **The score is informational:** `min_quality_score: 0`, with the merge bar listed under Quality
  Gates.
- **The supply-chain gate's semantics** (`scan/`): a baseline per image in `scan/baseline/`, keyed to
  the pinned base digest. Adele's image (feature 12) gets its own file.
- **The interpreter**, `pins.env` `PYTHON_VERSION=3.14.7`, for every agent-side tool.

**process_failures_recorded**

1. **Plugin: `/specswarm:ship` never reads `enforce_gates`.** `ship.md` says "If `enforce_gates:
   false`, ship will warn but not block merge", but its code compares only the score against
   `min_quality_score`. Checked in 2.12.0, answering the mentor's unverified flag in the quality-score
   feedback. So the ruling's fallback was applied: `min_quality_score: 0`, with the reason under
   Exemptions.
2. **Plugin: `/specswarm:constitution` assumes a template.** It expects placeholder tokens and gives no
   path for an audit of an already-ratified constitution against a new discovery revision. The audit
   followed its Governance provenance section (Append N) and its propagation checklist. The
   fill-the-template steps had nothing to do.
3. **Scope records written by hand.** Cycle 1's scope-check helper lived in a scratchpad lost at the
   context clear. Each `SCOPE:` line in decisions T043–T046 lists the task's changed files against its
   own text, not the plugin's `scope-check` block.

**retired_prompts_seen:** none.

### Cycle 2 — verification addendum (2026-09-28, after the Docker lane, the scan and the demo)

Appended, not rewritten. The section above records the state before the operator's runs. This records
what those runs established. The mentor's history also records them
(`../bridge/history.md`, 21:01:31Z, 21:09:57Z, 21:12:35Z).

**Runs**, all against image `sha256:727b8c49c28c`, stamped `3690e76`:
- **Baseline review:** the operator reviewed `scan/baseline/timelike-agent.json`, by interview with the
  mentor instance. The 8 Criticals were reviewed one by one, and the 69 Highs were accepted on their
  origin reasons.
  - `reviewed 2026-09-28`, `review_by 2026-12-27`, committed `3690e76`.
  - The credential-class Criticals (CVE-2026-11856, -19931, -8926) are accepted **for slice 0 only**.
    Feature 12 must re-review them.
  - Written by the mentor at the operator's request, outside this cycle's tasks. So it has no
    decisions.md section, which is correct: the review is the person's, not the code instance's.
- **Docker lane:** `make test`, 21:03:17Z → 21:06:13Z. Results in `tests/out/` (`summary.json`,
  `e2e.tap`, `report.xml`, `unit.txt`).
  - preflight, build, up, runner and e2e passed.
  - The unit step failed on one test (below).
- **Scan:** `make scan` **PASS**. Results in `scan/out/` (`verdict.json`, `steps.tsv`,
  `baseline.proposed.json`).
- **Demo:** `make demo`, watched by the operator.

**criteria_reestablished** (supersedes the modes above)

| Criterion | Mode |
|---|---|
| 01 · "`git log`, `git diff`, `git commit` without a message, and `git rebase --continue` each exit within 20 seconds" | executed [tests/e2e/git-log-diff-commit-rebase-exit-within-20-seconds.bats, 36/36] |
| 01 · "non-interactive `bash -c` or `bash -lc` and the environment's pager, editor, prompt and colour defaults are all in effect" | executed [tests/e2e/bash-c-and-bash-lc-defaults-in-effect.bats, 12/12] |
| 01 · "A git operation that would need credentials fails fast with a non-zero exit instead of prompting" | executed [tests/e2e/credentials-fail-fast-and-hooks-off.bats, 40/40] |
| 01 · "The agent's user cannot run any command as root, cannot change firewall rules, and cannot read files owned by Adele" | executed [tests/e2e/agent-cannot-run-as-root-change-firewall-or-read-adele.bats, 18/18] |
| 01 · "A conformance check runs against every timelike tool on PATH and fails when any tool lacks" | executed [tests/e2e/conformance-check-over-every-timelike-tool-on-path.bats, 10/10] |
| 01 · "Two Peer agents running concurrently each write to their own scratch space" | executed [tests/e2e/peer-agents-write-to-own-scratch-space.bats, 2/2] |
| 01 · "DEMO: the Agent runs `git commit`, `git rebase --continue` and `git log` in the container" | observed by the operator, 2026-09-28 (demo container from image `sha256:727b8c49c28c`, revision `3690e76`) |

**The operator on the demo:** "fast and sufficient". The mentor recorded the same observation at
21:12:35Z: "SC-7 looks good".

**Also established:**
- **SC-3's rewritten ssh cells:** all 13 pass (TAP 50–62, 225–314 ms). This confirms T044's
  assumption that git reports `cannot run ssh` when there is no client.
- **The build checks passed:** the interpreter is 3.14.7 at the expected path, and there is no ssh on
  PATH.
- **The H8 stamp matches end to end:** `stamp_check` passed in every bats file's setup, and the SC-5
  revision test passed.

**Supply-chain gate: PASS.**
- **SBOM:** 635 packages. **pip-audit:** 1 distribution (Python 3.14.7 site-packages), 0 matches.
  **gitleaks:** 0 findings across history.
- **Grype:** 232 matches.
  - **0 blocking.**
  - **77 baselined** (8 Critical, 69 High), exactly the drafted set.
  - 155 are below High.
- CVE-2026-82049 (Python) and the 3 openssh-client findings are gone, as T043 and T044 intended. No
  new High or Critical appeared.
- The summary line: `baseline: scan/baseline/timelike-agent.json — accepts 8 Critical, 69 High;
  base digest sha256:a99cfc517144; reviewed 2026-09-28, review by 2026-12-27`.

**Unit step: 173/174, one test defect, fixed in `3cf8a28`, re-run pending.**
- `test_dists_counts_what_the_interpreter_sees[names1]` failed on 3.14.7 with `ModuleNotFoundError:
  quopri`. The test replaced `sys.path` with only a fake site-packages, and on 3.14,
  `importlib.metadata` reads METADATA through `email`, which imports `quopri` lazily.
- It is a test defect, not a product one. `evaluate.py dists` ran correctly inside the real scan.
- Fixed by keeping the stdlib directories after the fake site (decisions T047 (fix)). The mentor's
  sign-off suggested prepending the fake site to the whole `sys.path`, but that would also count the
  interpreter's own site-packages.
- Reproduced and verified on the host. **The Docker lane's unit step needs the operator's re-run of
  `make test`** before merge.

**not_verified, updated.** Items 1–5 of the list above are now verified. Still open:
- the unit step on 3.14.7 after `3cf8a28` (the operator's re-run)
- a LICENSE file
- the in-image start-up figure (passed, not printed)

**Merge bar** (quality-standards § Quality Gates):
- Boundary and Safety gates: pass
- supply-chain scan: pass
- one test per criterion per invocation style: pass
- Manual criterion observed: pass
- Python coverage of 90% or more: **pending** the unit re-run. The host lane is at 94% or more, and
  there is no Go in this feature.

**Re-run, 2026-09-28 21:22–21:25Z, at `12b7f9c`** (this addendum's `a3dd456` plus the maintainer's MIT
LICENSE): `make test` **PASS**, e2e 118/118 and unit 174/174 on Python 3.14.7 (`tests/out/summary.json`,
exit 0). The unit fix `3cf8a28` holds in the image.

**Coverage, 90% per language:** confirmed on the host lane at `12b7f9c`, line+branch, tools measured as
the subprocesses they are. The Docker lane's unit step does not measure coverage.

| File | Coverage |
|---|---|
| `scan/evaluate.py` | 99% |
| `tools/agentio/agentio.py` | 92% |
| `tools/bin/timelike` | 96% |
| `tools/bin/timelike-conform` | 93% |
| **Python total** | **95%** |

There is no Go in this feature.

**The merge bar holds**, and the LICENSE leftover is closed. Still open: the in-image start-up figure
(passed, not printed).

**Before merge, governance-only** (the same ruling, no audit entry): specswarm 2.13.0's `ship` reads
`enforce_gates`, so `quality-standards.md` now records `enforce_gates: false` and its Exemptions row is
corrected (`../bridge/feedback/01-20260928-130206-quality-score.md` § Correction after closure).

## Cycle 3 — bridge/sends/01-rev2-20260928-214635.md

**Written:** 2026-09-28, after the code changes for this send and before the operator's Docker-lane runs,
not in dispatch mode. Built with `/specswarm:modify --from-send` on feature 001, as the send directs.
**Branch:** `modify/001-slice-1` off `master` (`dca60ff`), not merged.

**Status in one line:** slice 1 is written, and so is natural-intensity coverage of slice 0. The host
lane passes. No criterion is re-established yet, because the image has not been rebuilt (research R10).

### Group A — cited from `.implement-complete`

Group A: not applicable — no marker on this path

### Group B — copied from the send

| Field | Value |
|---|---|
| source_send | bridge/sends/01-rev2-20260928-214635.md |
| source_prompt | plan/.discover/prompts/01-agent-shell-baseline.md |
| prompt_revision | 2 |
| discovery_revision | 5 |
| slice | 1 |

### Group C — written by the code instance

**delegations**

This instance wrote the modify artifacts, T054–T056, and the T059 fix. It reviewed, amended and
committed every delegated task.

| # | Delegate | Scope | Tasks |
|---|---|---|---|
| 1 | general-purpose subagent | the slice-1 environment: `shell-env.bash` and its wiring, TZ and REPL in ENV, the SC-8/9/10 bats file, host-lane checks | T050, T051, T052 |
| 2 | general-purpose subagent | natural intensity: common-failure tests in the six slice-0 bats files. It found the product gap fixed in T059 | T053 |

**Review amendment (coordinator):** delegate 1's whole-component secret rule missed `PGPASSWORD`. The
password, token and secret families now also match a component ending in the word. See decisions T050.

**criteria_reestablished**

| Criterion | Mode |
|---|---|
| 01 · "`git log`, `git diff`, `git commit` without a message, and `git rebase --continue` each exit within 20 seconds" | unconfirmed |
| 01 · "non-interactive `bash -c` or `bash -lc` and the environment's pager, editor, prompt and colour defaults are all in effect" | unconfirmed |
| 01 · "A git operation that would need credentials fails fast with a non-zero exit instead of prompting" | unconfirmed |
| 01 · "The agent's user cannot run any command as root, cannot change firewall rules, and cannot read files owned by Adele" | unconfirmed |
| 01 · "A conformance check runs against every timelike tool on PATH and fails when any tool lacks" | unconfirmed |
| 01 · "Two Peer agents running concurrently each write to their own scratch space" | unconfirmed |
| 01 · "Build parallelism defaults (make jobs, test-runner workers, compiler jobs) are derived from the container's CPU limit" | unconfirmed |
| 01 · "Secret-shaped environment variables (names matching key, token, secret, password patterns) are absent" | unconfirmed |
| 01 · "The timezone defaults to UTC and interactive language REPLs default to their basic, scriptable prompt mode" | unconfirmed |
| 01 · "DEMO: the Agent runs `git commit`, `git rebase --continue` and `git log` in the container" | unconfirmed |
| 01 · "A person reading the output contract can predict, for a tool they have not seen" | unconfirmed |

Cycle 2's executed results were for an image this cycle changes: a new hook, three new ENV keys and
a changed `timelike-conform`. They do not carry over. The e2e suite is now 171 tests:
- 118 carried from slice 0
- 34 common-failure tests
- 19 for SC-8, SC-9 and SC-10

**reconcile_mode:** full.
- All eleven criteria in the send were examined. The seven slice-0 criteria were each tested against
  their common failure, and the four slice-1 criteria were added to the spec and built.
- **Provenance:** row 4. Prompt revision 2 is already in `audited_against: [2]`, so nothing was
  appended; `modify` Step 9 was skipped by its own rule.
- `source_send` in `spec.md` moved to this send, and the body's generating send is recorded in
  modify.md.

**not_verified**

1. **The image build** with the hook, the `bash.bashrc` line and the Dockerfile's own smoke run.
2. **All 171 e2e tests and the unit suite on 3.14.7** (`make test`). SC-8 needs a host with at least 2
   usable CPUs and cgroup v2; otherwise its tests FAIL with the reason, by design.
3. **The in-image start-up p95.** `tests/out/startup.json` is new (T054). Its figure then goes into
   quality-standards C2 (T057, governance-only).
4. **`make scan`.** No package was added, so no new finding is expected. gitleaks has not yet seen the
   new test files, whose fake secret values are short and low-entropy on purpose.
5. **SC-7 on the new image** (the demo) and **SC-11** (a person reading the contract). Both are Manual.
6. **The FR-15/FR-16 limits** (spec Out of Scope):
   - plain `sh -c` and direct execs of non-shell binaries get neither the job counts nor the strip
   - `/proc/1/environ` keeps whatever the container was started with
   - names that are not shell identifiers pass through
   - `SSHPASS`, `MYSQL_PWD` and `GITHUB_PAT` match none of the criterion's patterns and are kept
7. **The credential-class Criticals' premise** (CVE-2026-11856, -19931, -8926; the send's watch item).
   Nothing in this cycle gives the agent a credential, a netrc or a proxy. The secret strip
   strengthens the premise. The baseline is unchanged.
8. **Host-lane evidence**, advisory:
   - 176 unit tests
   - env layer 60/60, hook logic 29/29
   - Python coverage 95% (evaluate 99%, agentio 92%, timelike 96%, timelike-conform 93%)
   - ruff, mypy `--strict` and shellcheck clean

**changed_other_features:** none by feature. Shared ground later features inherit:
- **Every bash shell** now sources `/etc/timelike/shell-env.bash`. It adds the job-count defaults and
  strips secret-shaped names. The image's own `RUN` shells after the ENV block read it too.
- **`timelike-conform`** now judges a tool that cannot execute (127 or 126) instead of crashing (T059).
- **The Docker lane writes `tests/out/startup.json`.**
- **No governance file changed.** The C2 figure is pending T057, and there is no audit entry (it is
  governance-only).

**process_failures_recorded**

1. **Plugin: `modify` Step 7 says to create `tasks.md`.** On a feature with history, that overwrites
   48 completed tasks. This cycle appended Phase 12 instead.
2. **The design missed two things, and review caught them:**
   - the image's own `GIT_CONFIG_KEY_0` would have been stripped (caught by delegate 1)
   - whole-component matching missed `PGPASSWORD` (caught by the coordinator)

   Both are recorded in modify.md F002.
3. **A contract gap met while building SC-11:** an uncapped text output has no fixed last line. Raised
   as FOR-MENTOR Item 8, and not changed unilaterally.
4. **A product gap found by the natural-intensity pass:** `timelike-conform` crashed on a tool whose
   interpreter cannot be executed. Fixed in T059, with unit and e2e tests.

**retired_prompts_seen:** none.

### Cycle 3 — verification addendum (2026-09-28, after the Docker lane, the scan and the demo)

Appended, not rewritten. These runs were at `01ee1ce`, the end of Cycle 3. The mentor ran them at the
operator's request (`../bridge/history.md`, 22:49:44Z), and the operator watched the demo (22:52:26Z).

**Runs**, all against image `sha256:7a1266f0e85d`, stamped `01ee1ce`:
- **`make build`:** PASS, including the Dockerfile's own smoke run of the hook.
- **`make test`:** PASS. e2e **171/171** and unit **176/176** on Python 3.14.7 (`tests/out/summary.json`,
  22:39:34Z → 22:43:40Z, exit 0).
  - SC-8 ran for real, on a 56-CPU cgroup-v2 host.
  - The two SC-5 cells for a tool whose interpreter path does not exist pass, so T059's fix holds in
    the image.
- **`make scan`:** PASS. 0 blocking, 77 baselined, no new High or Critical (`scan/out/verdict.json`).
  gitleaks raised nothing on the new test files.
- **Start-up:** p95 88.1 ms over 50 runs (`tests/out/startup.json`). The conditions are recorded in
  quality-standards C2 (T064).
- **Demo:** watched by the operator, "fine". git commit rc=1, git rebase --continue rc=0, git log rc=0,
  in no-tty, tty and pty. Every call took 0.090–0.141 s, with no editor, pager or prompt.

**criteria_reestablished** (supersedes Cycle 3's modes)

| Criterion | Mode |
|---|---|
| 01 · "`git log`, `git diff`, `git commit` without a message, and `git rebase --continue` each exit within 20 seconds" | executed [tests/e2e/git-log-diff-commit-rebase-exit-within-20-seconds.bats] |
| 01 · "non-interactive `bash -c` or `bash -lc` and the environment's pager, editor, prompt and colour defaults are all in effect" | executed [tests/e2e/bash-c-and-bash-lc-defaults-in-effect.bats] |
| 01 · "A git operation that would need credentials fails fast with a non-zero exit instead of prompting" | executed [tests/e2e/credentials-fail-fast-and-hooks-off.bats] |
| 01 · "The agent's user cannot run any command as root, cannot change firewall rules, and cannot read files owned by Adele" | executed [tests/e2e/agent-cannot-run-as-root-change-firewall-or-read-adele.bats] |
| 01 · "A conformance check runs against every timelike tool on PATH and fails when any tool lacks" | executed [tests/e2e/conformance-check-over-every-timelike-tool-on-path.bats] |
| 01 · "Two Peer agents running concurrently each write to their own scratch space" | executed [tests/e2e/peer-agents-write-to-own-scratch-space.bats] |
| 01 · "Build parallelism defaults (make jobs, test-runner workers, compiler jobs) are derived from the container's CPU limit" | executed [tests/e2e/container-derived-defaults.bats, SC-8 cells] |
| 01 · "Secret-shaped environment variables (names matching key, token, secret, password patterns) are absent" | executed [tests/e2e/container-derived-defaults.bats, SC-9 cells] |
| 01 · "The timezone defaults to UTC and interactive language REPLs default to their basic, scriptable prompt mode" | executed [tests/e2e/container-derived-defaults.bats, SC-10 cells] |
| 01 · "DEMO: the Agent runs `git commit`, `git rebase --continue` and `git log` in the container" | observed by the operator, 2026-09-28 (image `sha256:7a1266f0e85d`, `01ee1ce`) |
| 01 · "A person reading the output contract can predict, for a tool they have not seen" | unconfirmed |

All 171 e2e tests passed. The totals per file are in `tests/out/e2e.tap`.

## Cycle 4 — bridge/sends/01-rev6-20260928-231531.md

**Written:** 2026-09-29. Not in dispatch mode. This continues the slice-1 cycle on `modify/001-slice-1`
("continue that cycle; don't restart it"). It was built with `/specswarm:constitution` and then
`/specswarm:modify --from-send`.

**Status in one line:** revision 6 is a clarification. It is recorded in governance and on the spec, and
plan's wording changes are made. **No code, test or image file changed since `01ee1ce`**
(`git diff --name-only 01ee1ce HEAD` lists only `.specswarm/`, README and FOR-MENTOR), so the
verification addendum above stands for this cycle.

### Group A — cited from `.implement-complete`

Group A: not applicable — no marker on this path

### Group B — copied from the send

| Field | Value |
|---|---|
| source_send | bridge/sends/01-rev6-20260928-231531.md |
| source_prompt | plan/.discover/prompts/01-agent-shell-baseline.md |
| prompt_revision | 6 |
| discovery_revision | 6 |
| slice | 1 |

### Group C — written by the code instance

**delegations**

| # | Delegate | Scope | Tasks |
|---|---|---|---|
| 1 | general-purpose subagent | host experiment: do the start-up test's conditions make its figure slower than real tool use? It used the same CPython 3.14.7 build, the test's own program, and 8 conditions × 3 × 50 runs, repeated twice. It edited nothing | evidence for T064 |

This instance wrote everything else.

**criteria_reestablished:** as in the Cycle 3 verification addendum above. The same commit's results
stand, because this cycle changed no code, test or image. SC-11 stays `unconfirmed` until a person reads
the contract, which now states the uncapped case (T061).

**reconcile_mode:** full.
- **Governance:** all three files audited against revision 6 (`938a0d2`), now `[2, 3, 4, 5, 6]`.
  - Constitution: no amendment.
  - tech-stack: no change.
  - quality-standards: the Output contract gate now says what verifies the cut shape: `agentio`'s unit
    tests, not the conformance check.
- **Spec:** `audited_against` is `[2, 3, 4, 5, 6]` by modify Step 9 in full mode. The basis is a diff
  against the archived revision-2 send: no criterion was added, removed or reworded, and revisions 3–5
  never touched prompt 01. See audit-log.md.
  - **This appends 3–6, where the send said "append 6".** modify's rule for full mode is recorded in
    decisions T063.
- **`discovery_revision` stays `3`** and `prompt_revision` stays `2` in the spec's frontmatter. Only
  `/specswarm:specify` writes them, and modify Step 9 forbids touching them. So the frontmatter now
  pairs `discovery_revision: 3` with a `source_send` at revision 6. Those fields record the body's
  generation, while `audited_against` records what has been checked since. Nothing was hand-stamped.

**not_verified**

1. **SC-11**, a Manual criterion: no person has read the contract yet.
2. **The start-up figure on the tools' own path.** The recorded 88.1 ms ran through uv's ephemeral
   environment, and `agentio` was compiled from source on each run. A host experiment puts the
   real-tool path about 11 ms lower. That is host evidence, not an in-image figure (quality-standards
   C2).
3. **The FR-15/FR-16 limits**, unchanged from Cycle 3:
   - `sh -c` and direct execs
   - `/proc/1/environ`
   - names that are not shell identifiers
   - SSHPASS, MYSQL_PWD and GITHUB_PAT
4. **The credential-class Criticals' premise:** nothing in this cycle gives the agent a credential, a
   netrc or a proxy. The baseline is unchanged.
5. **Plan's flagged item, not ruled:** uncapped output can reach about 40 KB (200 lines × 200 columns),
   above the harness limits, so a harness can cut output timelike did not cut. It is left to the
   operator.
6. **Workspace re-check:** unit 176 and Python coverage 95% were measured at Cycle 3. Since then only
   documentation changed.

**changed_other_features:** none. Shared ground:
- the three governance files now record revision 6
- the contract document states the uncapped case (plan's table)
- quality-standards C2 carries the in-image figure and its conditions

**process_failures_recorded**

1. **A commit briefly claimed a README change it did not contain.** In T061/T062, the README edit failed
   an exact-match check after the contract edit had applied, and the commit ran anyway. It was caught
   at once and amended before anything else (`fc95cdf`). The commit was local and never pushed.
2. **Plugin: `modify` Steps 5–7 again say to create `impact-analysis.md`, `modify.md` and `tasks.md`.**
   On a feature with prior cycles, that overwrites their records. Cycle 4 appended sections instead.

**retired_prompts_seen:** none.

### Cycle 4 — merge addendum (2026-09-29)

**Merged** `modify/001-slice-1` into `master` at `7361366` (no-ff), after the operator approved. There
was no push, because there is no remote. The branch is kept. The existing `feature-001-complete` tag,
from slice 0, is unchanged.

**The ship gate:** `/specswarm:analyze-quality` (specswarm 2.15.0) wrote `quality-report.json`
(`overall_state: scored`, 89%, the average of 5 modules). Performance is excluded, not zeroed: bundle
size is unavailable, and lazy loading and images are not applicable. The score passed against
`min_quality_score: 0` and is informational under `enforce_gates: false`.

**process_failures_recorded (addendum):** in the expanded command text of `ship` and `complete`
(2.15.0), positional parameters inside shell functions were replaced by the command's argument words.
- `ship`'s `qr_get` looked up key `"modify/001-slice-1"` instead of `$1`.
- `complete`'s `confirm()` had its locals set to argument words.

The installed `commands/*.md` files have `$1`/`$2`/`$3`. So this is argument substitution being applied
to function bodies, not a defect in the source files. Both blocks were run as installed, and the merge
was done by hand with your answers.

### Cycle 4 — SC-11 addendum (2026-09-29)

**SC-11 observed by the operator** (`../bridge/history.md`, 2026-09-28T23:58:38Z).
- **Method.** By interview with the mentor, the operator read `contracts/output-contract.md` (as
  clarified in cycle 4, T061). They then predicted the first line, last line and exit code of
  `timelike-conform`, a tool they had not seen, in 4 cases:
  - plain `--text`
  - capped `--text --limit 2`
  - an unknown flag, `--text --bogus`
  - piped output (JSON)
- **Check.** The mentor ran each case in `timelike-agent` at `/opt/timelike/REVISION` `01ee1ce`.
- **All 4 predictions matched:**
  - a header first line
  - uncapped output ending on its own result line
  - capped output ending on the omission line, exit 0
  - `--bogus` exiting 2, with a one-line error on stderr and empty stdout
  - piped JSON with `tool`, `target` and `scope` first, an `exit` key, and no `truncated` key

**criteria_reestablished** (supersedes SC-11's mode in the Cycle 3 verification addendum; the other ten
rows stand)

| Criterion | Mode |
|---|---|
| 01 · "A person reading the output contract can predict, for a tool they have not seen" | observed by the operator, 2026-09-28 (4 of 4 predictions matched; `timelike-agent` at `01ee1ce`) |

**All eleven criteria of slice 1 are now re-established:** nine executed, and two observed by the
operator (SC-7, SC-11).

**On the order of events:** `modify/001-slice-1` was first merged at `7361366`, before this observation
and the mentor's approval note arrived. This addendum is merged by a second `/specswarm:ship`. Nothing
else changed between the two merges.

## Cycle 5 — bridge/sends/01-rev7-20260929-094055.md

**Written:** 2026-09-30. Not in dispatch mode. Built with `/specswarm:constitution` (the governance audit,
on `master` at `9688118`) and then `/specswarm:modify --from-send`, on `modify/001-hooks-bounded` from
`9688118`. **Not merged**: the Docker lane has not run, and the merge waits for the mentor's sign-off.

**Status in one line:** repository hooks now run, each under a 60 s limit with a verdict, instead of
being switched off (discovery revision 7, tension T4). The host lane passes. SC-12 and SC-13 are written
and not yet re-established in the image.

### Group A — cited from `.implement-complete`

Group A: not applicable — no marker on this path

### Group B — copied from the send

| Field | Value |
|---|---|
| source_send | bridge/sends/01-rev7-20260929-094055.md |
| source_prompt | plan/.discover/prompts/01-agent-shell-baseline.md |
| prompt_revision | 7 |
| discovery_revision | 7 |
| slice | 1 |

### Group C — written by the code instance

**delegations:** empty. This instance did T066–T073 itself. The mechanism needed host experiments
whose failures (below) were cheaper to see than to delegate.

**criteria_reestablished**

- `01 · "The hooks a repository configures (its core.hooksPath, or .git/hooks) run under git commands"` —
  **unconfirmed**. It has not run in the image. Test:
  `tests/e2e/hooks-a-repository-configures-run.bats`, 7 tests: a local core.hooksPath (husky's shape)
  that rejects, per style c/lc/ic; five default-location hook types across a commit and a checkout, per
  style; a passing hook. Host evidence (advisory): `tests/unit/test_git_hook_dispatch.py`, 18 passed.
- `01 · "A hook that runs past its time limit is killed and the git command exits non-zero within the limit plus a few seconds"` —
  **unconfirmed**. It has not run in the image. Test: `tests/e2e/hook-past-its-time-limit-is-killed.bats`,
  5 tests:
  - the repository limit (3 s), per style
  - the environment limit (2 s)
  - the 60 s default
  - in each: the verdict names the hook, the limit, its source and both ways to raise it, and has no
    skip word; the commit is absent; the hook's background child did not survive

  Host evidence: the same unit file.
- `01 · "A git operation that would need credentials fails fast with a non-zero exit instead of prompting"` —
  **unconfirmed** in this cycle. Its credentials half is unchanged, and its hooks clause is struck. The
  file is renamed `tests/e2e/credentials-fail-fast.bats` and keeps its 26 credentials tests; its 20
  hooks tests are removed (their subject is now SC-12/SC-13). Last executed at `01ee1ce`.
- Every other 001 criterion: last executed at `01ee1ce` and observed as recorded in Cycles 3 and 4. This
  cycle changes the image's ENV value, `/etc/gitconfig`, and adds `/opt/timelike/git-hooks`. The SC-2
  matrix and `container-derived-defaults.bats` now expect the new `core.hooksPath` value. The next
  Docker lane re-runs them all: e2e **168** tests (176 − 20 + 12).

**reconcile_mode:** full, **with the append deferred**.
- The spec was checked against revision 7's full criteria set (13).
  - SUPERSEDED: the struck clause (FR-4, SC-3, Scenario 3, R3), **corrected in place through this
    modify, declared**, as the send says. The plugin's row-7 rule says to stop and regenerate; that was
    not followed, because the send says not to (the correction needs the work, and R3's reasoning is
    reused).
  - INCOMPLETE: the two added criteria, built as FR-19/FR-20 and SC-12/SC-13, with Scenario 7.
- **`audited_against` stays `[2, 3, 4, 5, 6]`.** The send: "append revision 7 only when the cycle has
  re-established what it claims". SC-12 and SC-13 have not run in the image. `audit-log.md` records a
  `none` row naming the condition. A later addendum appends 7 when the Docker lane passes them.
- `source_send` in the spec's frontmatter now names this send. `prompt_revision` (2),
  `discovery_revision` (3) and `source_prompt` are untouched.

**Decisions the send left to code** (research R11):
1. **The limit is 60 s**, below Claude Code's 120 s call timeout. It can be raised with
   `TIMELIKE_HOOK_TIMEOUT` (this shell) or with `git config timelike.hookTimeout` (this repository);
   the environment wins. Both appear in the verdict.
2. **The mechanism is a dispatcher directory.**
   - `GIT_CONFIG_*` (command scope, R3) points `core.hooksPath` at `/opt/timelike/git-hooks`: one
     `dispatch` script and 25 hook-name links.
   - Each runs the hook git would have run without timelike: the last non-command `core.hooksPath`,
     else `<git-common-dir>/hooks`. It passes arguments, stdin and environment through, under GNU
     `timeout`, which stops the whole process group.
   - **Precedence relied on:** command > worktree > local > global > system.
   - It works where the repository sets `core.hooksPath` locally (husky) [V, host].
   - **Stdin:** git's stdin is forwarded, not replaced with `/dev/null` as the ruling's example said.
     pre-push reads from it, and git never hands a hook a terminal.
3. The hooks test is inverted, with one test per new criterion per invocation style.
4. Feature 002 moves too: see `changed_other_features`.

**not_verified**

1. **The Docker lane:** the image is not built, and SC-12, SC-13 and the whole 168-test e2e suite have
   not run. That includes the build-time check that COPY kept the 25 links.
2. **Three hook names are not linked:** `push-to-checkout` and `proc-receive` (git changes behaviour
   when they merely exist) and `fsmonitor-watchman` (not reached through `core.hooksPath`). They matter
   only when this environment receives a push. They are named in R11, not silent.
3. **The `/etc/gitconfig` fallback:** if the agent unsets `GIT_CONFIG_*`, a repository's local
   `core.hooksPath` wins, and its hooks run **unbounded**, as without timelike. Not tested.
4. **Bind-mounted workspaces (flagged by plan, not ruled):** the dispatcher runs a repository's hooks
   inside the container. A hook the agent writes into a bind-mounted `.git/hooks` also runs on the
   **host** the next time the operator commits there. This cycle neither widens nor closes that
   boundary.
5. **Cost:** about 5.5 ms per dispatch when no hook exists, and about eight dispatches per commit, so
   about 30–40 ms per commit on a noisy host. Measured, and not optimised further (P6 measures turns
   and failures).
6. **Host git 2.43, image git 2.47.3:** hook resolution and stdin were verified on 2.43 only.
7. **API keys:** none; this cycle touches no credential. The credential-class Criticals' premise is
   unchanged.

**changed_other_features:** **002 (merged)**, as the send's item 4 asks.
- `bench/benchlib/catalog.py`: both hook tasks' capability, difference, notes and expected texts.
  `git-commit-hook-rejects` becomes a tie. `git-commit-hook-hangs` now ends on timelike's hook verdict
  inside the call.
- `bench/benchlib/runner.py`: the default call limit goes from 30 s to 120 s (Claude Code's default,
  which the 60 s hook limit is sized for). A full bench run takes about 3 minutes longer.
- 002's units: the timelike emulation maps the dispatchers.
- 002's quickstart, plan and contracts: the new shape and the 120 s limit.

Host: 002's units pass, and a full stand-in run reports 0 losses, 2 ties and 2 wins. The bench has not
run in the image with the new default. Plan's resolution keeps both hook tasks for the live-harness
bench (slice 1), to measure the bound's cost in turns.

**process_failures_recorded**

1. **A recursive dispatcher reached the host.** The first fallback, `git rev-parse --git-path hooks`,
   honours `core.hooksPath` and returned the dispatcher's own directory. Each nested `timeout` leads its
   own process group, so no outer limit stopped the chain: about 1,000 processes were reaped by hand.
   - **Fixed:** `<git-common-dir>/hooks`, plus a self-directory check. A unit asserts it.
   - **The experiments ran unsandboxed until then.** Every later one ran under `setsid --wait` and a
     watchdog `timeout`.
2. **A no-hook stdin drain blocked** (post-index-change inherits the caller's stdin), and **dash ignores
   `<&0`** on an asynchronous command (pre-push got 0 lines). Both were found by host experiment, fixed,
   and covered by units.
3. **`pgrep -f` / `pkill -f` matched this session's own tool shell**, whose command line contained the
   pattern. That produced false "leftover child" readings and killed the shell three times (exit 144).
   The units detect a surviving child by an artefact it writes instead.
4. **A mis-invoked dry run created a stray repository at `tests/e2e/sc13-hang/`.** It was caught by
   `git add` and removed before any commit.
5. **Five tests still asserted `core.hooksPath=/dev/null`.** They were found by grep after T070, not by
   a run, and fixed in the T070 follow-up. They would have failed in the Docker lane.
6. **Plugin (specswarm 2.18.0):** `modify`'s expanded `provenance-row` and `audit-append` blocks again
   substitute argument words into shell functions (`grep -qxF "--from-send"`), the defect reboot.md
   records. They were not relied on; the row (7) was decided by reading the frontmatter.

**retired_prompts_seen:** none.

### Cycle 5 — Docker lane addendum (2026-09-30)

**Source:** the mentor's report of the Docker lane, relayed by the operator: `make test` **PASSED at
`7416c49`**, 168/168 e2e and 612 host. `make bench` at `13e7d10` showed `git-commit-hook-rejects` as a
tie, and `git-commit-hook-hangs` ending on the bounded verdict. `make scan` at `13e7d10` passed on all
three images. `13e7d10..7416c49` touches no `image/` path, so the images the bench and the scan ran
against are the images at `7416c49`.

That lane also carried the SC-4 guard fix, `1bcb7a7`. The earlier lane at `13e7d10` was 166/168: SC-4's
`check_cannot_alter_guards` still expected the system `core.hooksPath` to be `/dev/null`.

**criteria_reestablished (update to Cycle 5 above):**
- `01 · "The hooks a repository configures (its `core.hooksPath`, or `.git/hooks`) run under git commands"` —
  **observed by the mentor, in the Docker lane at `7416c49`, run at the operator's request**, through
  [`tests/e2e/hooks-a-repository-configures-run.bats`], 7 tests passed.
- `01 · "A hook that runs past its time limit is killed and the git command exits non-zero within the limit plus a few seconds"` —
  **observed by the mentor, in the Docker lane at `7416c49`**, through
  [`tests/e2e/hook-past-its-time-limit-is-killed.bats`], 5 tests passed, including the 60 s default.
- `01 · "A git operation that would need credentials fails fast with a non-zero exit instead of prompting"` —
  observed in the same lane, through [`tests/e2e/credentials-fail-fast.bats`] (the hooks clause is
  struck).
- Every other 001 criterion: re-run in the same lane (168/168), including the SC-2 matrix and
  `container-derived-defaults.bats` with the new `core.hooksPath` value.

**A citation correction:** Cycle 5 above cited SC-12 as `01 · "The hooks a repository configures (its
core.hooksPath, or .git/hooks) run under git commands"`, without the backticks the send has around
`core.hooksPath` and `.git/hooks`. That text matches 0 lines of the send. The citation above is exact:
it matches 1 line. Cycle 5's section is left as written, because this file is append-only.

**reconcile_mode, completed:** revision 7 is appended. `audited_against` is now `[2, 3, 4, 5, 6, 7]`,
with a `full` row in `audit-log.md` completing the deferred one. The send's condition is met: the cycle
re-established what it claims.

**changed_other_features, confirmed:** feature 002's bench at `13e7d10` gave the shape Cycle 5
predicted: `git-commit-hook-rejects` a tie, and `git-commit-hook-hangs` ending on timelike's bounded
verdict.

**Not merged.** The merge waits for the mentor's sign-off. At `/specswarm:ship`, its full output and
analyze-quality's output go into this report verbatim.

### Cycle 5 — ship addendum (2026-09-30, specswarm 2.19.0)

**Merged** `modify/001-hooks-bounded` into `master` at **`948ef84`** (no-ff) after the mentor's sign-off
at `b8cdf09` (`../bridge/history.md` 2026-09-30T05:22:20Z). The merge's tree equals `b8cdf09`'s. There
was no push, because there is no remote. The branch is kept.

**How ship ran:** these are 2.19.0's blocks, as the reloaded session expands them (`PLUGIN_DIR=…/4.0.1-botbaubble.2.19.0`), run as
written and quoted verbatim below. Two points to state plainly:
- **`quality-report.json` was not written, to any feature directory.** analyze-quality's
  `quality-report` block resolves the feature from a branch named `NNN-*`. This branch,
  `modify/001-hooks-bounded`, gives it no number (`QR_NUM=''`), so, by the block's own rule, it wrote no
  report and said why. Ship's `quality-source` then looked for `./quality-report.json` (its
  `FEATURE_DIR` is unset), found none, and fell back to the analysis output, which has no numeric
  "Overall Quality" line. So the score reached the gate empty, and the gate reported **unknown**.
- **Step 4 (`/specswarm:complete`) was not run**: its prompts need stdin, and its expanded text garbles
  shell-function arguments (reboot.md). The merge was done by hand with `git merge --no-ff`, as for
  001's earlier cycles and 002. Its output is quoted below.

#### analyze-quality output (verbatim; also saved as `.specswarm/quality-analysis-20260930-052430.md`)

```
📊 Codebase Quality Analysis
============================

Analyzing: .
Started: 2026-09-30T05:23:32+00:00

🔤 Language: Python
Measurable (sections 2-6): no
LSP analysis: false (no tsconfig.json)

Sections 2-6 (tests, architecture, documentation, performance, security): skipped — AQ_MEASURABLE=no; each component is recorded unavailable by component-applicability, not scored

📊 Module Quality Scores
========================
tools/agentio: unknown
tools/bin: unknown
scan: unknown
image: unknown
scripts: unknown
bench/benchlib: unknown
bench/bin: unknown
bench/images+run.sh: unknown

Excluded (not scored, and not scored as 0):
tools/agentio: tests — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (25 points not counted either way)
docs — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (15 points not counted either way)
architecture — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
security — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
bundle — unavailable: lib/bundle-size-monitor.sh is not in this install (7 points not counted either way)
lazy-loading — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (7 points not counted either way)
images — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (6 points not counted either way)
tools/bin: tests — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (25 points not counted either way)
docs — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (15 points not counted either way)
architecture — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
security — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
bundle — unavailable: lib/bundle-size-monitor.sh is not in this install (7 points not counted either way)
lazy-loading — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (7 points not counted either way)
images — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (6 points not counted either way)
scan: tests — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (25 points not counted either way)
docs — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (15 points not counted either way)
architecture — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
security — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
bundle — unavailable: lib/bundle-size-monitor.sh is not in this install (7 points not counted either way)
lazy-loading — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (7 points not counted either way)
images — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (6 points not counted either way)
image: tests — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (25 points not counted either way)
docs — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (15 points not counted either way)
architecture — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
security — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
bundle — unavailable: lib/bundle-size-monitor.sh is not in this install (7 points not counted either way)
lazy-loading — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (7 points not counted either way)
images — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (6 points not counted either way)
scripts: tests — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (25 points not counted either way)
docs — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (15 points not counted either way)
architecture — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
security — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
bundle — unavailable: lib/bundle-size-monitor.sh is not in this install (7 points not counted either way)
lazy-loading — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (7 points not counted either way)
images — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (6 points not counted either way)
bench/benchlib: tests — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (25 points not counted either way)
docs — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (15 points not counted either way)
architecture — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
security — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
bundle — unavailable: lib/bundle-size-monitor.sh is not in this install (7 points not counted either way)
lazy-loading — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (7 points not counted either way)
images — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (6 points not counted either way)
bench/bin: tests — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (25 points not counted either way)
docs — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (15 points not counted either way)
architecture — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
security — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
bundle — unavailable: lib/bundle-size-monitor.sh is not in this install (7 points not counted either way)
lazy-loading — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (7 points not counted either way)
images — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (6 points not counted either way)
bench/images+run.sh: tests — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (25 points not counted either way)
docs — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (15 points not counted either way)
architecture — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
security — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
bundle — unavailable: lib/bundle-size-monitor.sh is not in this install (7 points not counted either way)
lazy-loading — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (7 points not counted either way)
images — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (6 points not counted either way)


Overall Quality: unknown (no module could be scored (8 unscored))

(branch: modify/001-hooks-bounded; feature number read from it: ''; FEATURE_DIR: '')
ℹ️  No feature directory — quality-report.json was NOT written.
   hooks/stop-hook.sh gates a build loop per feature and reads it at
   <feature>/quality-report.json, so there is nowhere for this run's report to go.
   This is a repo-wide analysis; the score above stands on its own.
   Run this from a feature branch (NNN-*) to produce the report the build loop reads.
```

#### ship output, steps 1–3 (verbatim; the threshold lines and the gate)

```
🚢 SpecSwarm Ship - Quality-Gated Merge
══════════════════════════════════════════

This command enforces quality standards before merge:
  1. Runs comprehensive quality analysis
  2. Checks quality score meets threshold
  3. If passing: merges to parent branch
  4. If failing: reports issues and blocks merge

📍 Current branch: modify/001-hooks-bounded

[Step 2: /specswarm:analyze-quality — its output is quoted separately]

📋 Using project quality threshold: 0% (from min_quality_score)
ℹ️  enforce_gates: false — a failing gate will WARN, not block

🎯 Quality Threshold: 0%
📊 Actual Quality Score: %

❌ Quality gate UNKNOWN — no "Overall Quality: NN%" line was produced

   Nothing was measured. This is NOT a 0% failure and NOT a pass:
   the analysis did not run, did not report a score, or could not measure this project.


🔧 Recommended Actions:
  1. Review the quality analysis output above
  2. Address critical and high-priority issues
  3. Run /specswarm:analyze-quality again to verify improvements
  4. Run /specswarm:ship again when quality improves

⚠️  enforce_gates: false — this gate WARNS and does not block the merge.
   Shipping a unknown quality result is the project's recorded choice, not an oversight.

GATE_STATE=unknown
```

#### merge (step 4, by hand; verbatim)

```
Switched to branch 'master'
Merge made by the 'ort' strategy.
 .../features/001-agent-shell-baseline/audit-log.md |   2 +
 .../001-agent-shell-baseline/cycle-report.md       | 182 ++++++++++++++
 .../features/001-agent-shell-baseline/decisions.md |  99 ++++++++
 .../001-agent-shell-baseline/impact-analysis.md    |  36 +++
 .../features/001-agent-shell-baseline/modify.md    |  39 +++
 .../features/001-agent-shell-baseline/research.md  |  91 +++++++
 .../features/001-agent-shell-baseline/spec.md      |  41 +++-
 .../features/001-agent-shell-baseline/tasks.md     |  30 +++
 .../002-speedup-bench/contracts/bench-cli.md       |   2 +-
 .../002-speedup-bench/contracts/trace-schema.md    |   2 +-
 .specswarm/features/002-speedup-bench/plan.md      |   2 +-
 .../features/002-speedup-bench/quickstart.md       |   9 +-
 Makefile                                           |   1 +
 README.md                                          |  11 +-
 bench/benchlib/catalog.py                          |  46 ++--
 bench/benchlib/runner.py                           |   5 +-
 image/Dockerfile                                   |  14 +-
 image/rootfs/etc/gitconfig                         |   5 +-
 image/rootfs/etc/timelike/shell-env.bash           |   4 +-
 image/rootfs/opt/timelike/git-hooks/applypatch-msg |   1 +
 image/rootfs/opt/timelike/git-hooks/commit-msg     |   1 +
 image/rootfs/opt/timelike/git-hooks/dispatch       | 117 +++++++++
 image/rootfs/opt/timelike/git-hooks/p4-changelist  |   1 +
 .../opt/timelike/git-hooks/p4-post-changelist      |   1 +
 image/rootfs/opt/timelike/git-hooks/p4-pre-submit  |   1 +
 .../opt/timelike/git-hooks/p4-prepare-changelist   |   1 +
 .../rootfs/opt/timelike/git-hooks/post-applypatch  |   1 +
 image/rootfs/opt/timelike/git-hooks/post-checkout  |   1 +
 image/rootfs/opt/timelike/git-hooks/post-commit    |   1 +
 .../opt/timelike/git-hooks/post-index-change       |   1 +
 image/rootfs/opt/timelike/git-hooks/post-merge     |   1 +
 image/rootfs/opt/timelike/git-hooks/post-receive   |   1 +
 image/rootfs/opt/timelike/git-hooks/post-rewrite   |   1 +
 image/rootfs/opt/timelike/git-hooks/post-update    |   1 +
 image/rootfs/opt/timelike/git-hooks/pre-applypatch |   1 +
 image/rootfs/opt/timelike/git-hooks/pre-auto-gc    |   1 +
 image/rootfs/opt/timelike/git-hooks/pre-commit     |   1 +
 .../rootfs/opt/timelike/git-hooks/pre-merge-commit |   1 +
 image/rootfs/opt/timelike/git-hooks/pre-push       |   1 +
 image/rootfs/opt/timelike/git-hooks/pre-rebase     |   1 +
 image/rootfs/opt/timelike/git-hooks/pre-receive    |   1 +
 .../opt/timelike/git-hooks/prepare-commit-msg      |   1 +
 .../opt/timelike/git-hooks/reference-transaction   |   1 +
 .../opt/timelike/git-hooks/sendemail-validate      |   1 +
 image/rootfs/opt/timelike/git-hooks/update         |   1 +
 reboot.md                                          |  21 +-
 ...-run-as-root-change-firewall-or-read-adele.bats |  12 +-
 .../e2e/bash-c-and-bash-lc-defaults-in-effect.bats |   6 +-
 tests/e2e/container-derived-defaults.bats          |   2 +-
 ...d-hooks-off.bats => credentials-fail-fast.bats} | 129 +---------
 tests/e2e/hook-past-its-time-limit-is-killed.bats  | 102 ++++++++
 tests/e2e/hooks-a-repository-configures-run.bats   | 105 ++++++++
 tests/host/test_env_layer.sh                       |   2 +-
 tests/host/test_shell_env_hook.sh                  |   4 +-
 tests/unit/test_bench_catalog.py                   |  44 +++-
 tests/unit/test_bench_cli.py                       |  48 ++--
 tests/unit/test_bench_runner.py                    |  19 +-
 tests/unit/test_git_hook_dispatch.py               | 268 +++++++++++++++++++++
 58 files changed, 1319 insertions(+), 206 deletions(-)
 create mode 120000 image/rootfs/opt/timelike/git-hooks/applypatch-msg
 create mode 120000 image/rootfs/opt/timelike/git-hooks/commit-msg
 create mode 100755 image/rootfs/opt/timelike/git-hooks/dispatch
 create mode 120000 image/rootfs/opt/timelike/git-hooks/p4-changelist
 create mode 120000 image/rootfs/opt/timelike/git-hooks/p4-post-changelist
 create mode 120000 image/rootfs/opt/timelike/git-hooks/p4-pre-submit
 create mode 120000 image/rootfs/opt/timelike/git-hooks/p4-prepare-changelist
 create mode 120000 image/rootfs/opt/timelike/git-hooks/post-applypatch
 create mode 120000 image/rootfs/opt/timelike/git-hooks/post-checkout
 create mode 120000 image/rootfs/opt/timelike/git-hooks/post-commit
 create mode 120000 image/rootfs/opt/timelike/git-hooks/post-index-change
 create mode 120000 image/rootfs/opt/timelike/git-hooks/post-merge
 create mode 120000 image/rootfs/opt/timelike/git-hooks/post-receive
 create mode 120000 image/rootfs/opt/timelike/git-hooks/post-rewrite
 create mode 120000 image/rootfs/opt/timelike/git-hooks/post-update
 create mode 120000 image/rootfs/opt/timelike/git-hooks/pre-applypatch
 create mode 120000 image/rootfs/opt/timelike/git-hooks/pre-auto-gc
 create mode 120000 image/rootfs/opt/timelike/git-hooks/pre-commit
 create mode 120000 image/rootfs/opt/timelike/git-hooks/pre-merge-commit
 create mode 120000 image/rootfs/opt/timelike/git-hooks/pre-push
 create mode 120000 image/rootfs/opt/timelike/git-hooks/pre-rebase
 create mode 120000 image/rootfs/opt/timelike/git-hooks/pre-receive
 create mode 120000 image/rootfs/opt/timelike/git-hooks/prepare-commit-msg
 create mode 120000 image/rootfs/opt/timelike/git-hooks/reference-transaction
 create mode 120000 image/rootfs/opt/timelike/git-hooks/sendemail-validate
 create mode 120000 image/rootfs/opt/timelike/git-hooks/update
 rename tests/e2e/{credentials-fail-fast-and-hooks-off.bats => credentials-fail-fast.bats} (57%)
 create mode 100644 tests/e2e/hook-past-its-time-limit-is-killed.bats
 create mode 100644 tests/e2e/hooks-a-repository-configures-run.bats
 create mode 100644 tests/unit/test_git_hook_dispatch.py
```

#### ship output, step 5 (verbatim)

```

══════════════════════════════════════════
🎉 SHIP SUCCESSFUL
══════════════════════════════════════════

✅ Quality gate passed (%)
✅ Merged to parent branch
✅ Feature/bugfix complete

📝 Next Steps:
  - Pull latest changes in other branches
  - Consider creating a release tag if ready
  - Update project documentation if needed

```

**Two lines above are not true, and are quoted as printed:**
- `📊 Actual Quality Score: %` prints an empty score, because the score is unknown.
- `✅ Quality gate passed (%)`: **the gate did not pass.** Its state was `unknown`, and it warned without
  blocking because `enforce_gates: false`. Step 5 prints "passed" unconditionally. That is a defect report
  about the plugin: its step 5 does not read `QUALITY_STATE`. The merge bar here is quality-standards
  § Quality Gates, and it was met by the project's own lanes (Docker lane at `7416c49`, scan and bench at
  `13e7d10`), not by this score.

**A defect report about specswarm 2.19.0:** analyze-quality's feature resolution reads only branches
named `NNN-*`. It does not read the `modify/NNN-*` branches that `/specswarm:modify`'s own step 1
reads, so no modify cycle ever gets a `quality-report.json`.

## Cycle 6 — bridge/sends/01-rev9-20261001-191224.md

**Written:** 2026-10-01. Not in dispatch mode. Built with `/specswarm:modify --from-send`, then
`/specswarm:plan`, `/specswarm:tasks` and `/specswarm:implement`, on `modify/001-rev9-scope-and-t4` from
`master` at `a6fa2e9`, under **specswarm 4.0.1-botbaubble.2.22.0**: the version this session loaded,
which the expanded commands name (lore Q002). **Not merged:** the Docker lane has not run, and the merge
waits for the mentor's sign-off.

**Status in one line:** no behaviour change. Spec rule 5 now carries revision 9's scope sentence. The
README states T4's limit under `env -i`. A new e2e file pins both `env -i` cases. The host lane passes;
nothing is yet re-established in the image.

### Group A — cited from `.implement-complete`

Group A: not applicable — no marker on this path

### Group B — copied from the send

| Field | Value |
|---|---|
| source_send | bridge/sends/01-rev9-20261001-191224.md |
| source_prompt | plan/.discover/prompts/01-agent-shell-baseline.md |
| prompt_revision | 9 |
| discovery_revision | 9 |
| slice | 1 |

### Group C — written by the code instance

**delegations:** empty. This instance did T074–T078 itself.

**criteria_reestablished**

No criterion changed at revision 9 (the Acceptance Criteria of `01-rev7-20260929-094055.md` and this send
are byte-identical). This cycle changed no behaviour, so it re-establishes the criteria only by the
Docker lane re-running 001's e2e files against the image built from this branch. Until that runs, every
criterion is `unconfirmed`. The lane addendum gives each its mode.

- `01 · "each exit within 20 seconds without opening a pager or editor"` — **unconfirmed** (Docker lane
  pending)
- `01 · "the environment's pager, editor, prompt and colour defaults are all in effect, verified by one test per invocation style"` —
  **unconfirmed** (Docker lane pending)
- `01 · "fails fast with a non-zero exit instead of prompting"` — **unconfirmed** (Docker lane pending)
- `01 · "a commit a pre-commit hook rejects fails with the hook's output, as it would without timelike"` —
  **unconfirmed** (Docker lane pending)
- `01 · "is killed and the git command exits non-zero within the limit plus a few seconds, with a verdict naming the hook"` —
  **unconfirmed** (Docker lane pending)
- `01 · "cannot run any command as root, cannot change firewall rules, and cannot read files owned by Adele"` —
  **unconfirmed** (Docker lane pending)
- `` 01 · "fails when any tool lacks `--help` within 40 lines" `` — **unconfirmed** (Docker lane pending)
- `01 · "each write to their own scratch space, and neither's output files or event log entries appear in the other's"` —
  **unconfirmed** (Docker lane pending)
- `01 · "are derived from the container's CPU limit rather than the host's CPU count"` — **unconfirmed**
  (Docker lane pending)
- `01 · "are absent from the agent's environment unless explicitly allow-listed"` — **unconfirmed**
  (Docker lane pending)
- `01 · "The timezone defaults to UTC and interactive language REPLs default to their basic, scriptable prompt mode"` —
  **unconfirmed** (Docker lane pending)
- `01 · "each returns within seconds instead of waiting on an editor, pager or prompt"` — **unconfirmed**.
  Manual (D1); this cycle changes nothing it observes.
- `01 · "can predict, for a tool they have not seen, what its first line, last line and exit codes will be"` —
  **unconfirmed**. Manual. Rule 5's new sentence is part of what such a reader predicts from.

Each citation was checked to match exactly one line of the send (`grep -cF` = 1 for all 13).

**reconcile_mode:** `full` is available, and it is **deferred**. Revisions 8 and 9 are unaudited.
- Revision 8 did not change prompt 01.
- Revision 9 changed no criterion. The criteria diff against the rev-7 send is empty, so removals and
  rewordings are visible, and none occurred.
- Revision 9's one change, rule 5's scope, needs no body change. It is copied into the spec, declared
  (T074): line 171 of `spec.md`. No body line stated the unconditional "always one of" reading, so
  nothing was corrected, only annotated.
- By the bookkeeping convention, 8 and 9 are appended only after the Docker lane re-establishes the
  cycle: `audit-log.md` has a `none (deferred)` row, and a `full` row follows with the lane addendum.
  `audited_against` stays `[2, 3, 4, 5, 6, 7]` for now.

**The send's three items:**
1. **Rule 5's scope recorded** (T074, `5ff8860`). The annotation's text equals the send's rule-5
   clarification (a whitespace-normalised comparison).
2. **README states T4's limit** (T075, `9744e1c`), under "Environment defaults", right after the hook
   paragraph. It names both cases, because "git's own behaviour" alone would read as unbounded for
   `.git/hooks` too, which the measurement contradicts. It points at `run --timeout N`.
3. **A test pins the limit** (T076, `60647c9`):
   `tests/e2e/hooks-under-env-i-default-bounded-local-unbounded.bats`, with four cells (two cases ×
   `bash -c`/`bash -lc`, `notty`). git runs under `env -i` through the image's real shells and its
   real `/etc/gitconfig` (lore P005).
   - **Default `.git/hooks`:** non-zero within 2 + 5 s, the verdict naming the repository's 2 s limit,
     no commit, and the hook stopped and not alive.
   - **Local `core.hooksPath`:** the test's own `timeout -k 1 10` ends git (rc 124), with no
     `error: git hook` line and no commit. The hook's own last-beat second is at least 7 s after git
     started.
   - The tests carry no SC number, because they pin a ruling rather than a criterion. Titled
     "T4 under env -i: …".

**not_verified**
- **Nothing ran in the image** (no Docker here, R10). The new test's four cells, and every criterion
  above, wait for the Docker lane.
- **The host evidence for the new test.** Both fixtures were generated from the file's own `sh -c`
  text and run through the test's own command lines on the host (git 2.43.0), sandboxed. The one
  difference: `env -i GIT_CONFIG_SYSTEM=<stand-in>` replaced the image's real `/etc/gitconfig`.
  - default: rc 1 at 2.0 s with the verdict, no commit, hook stopped
  - local: rc 124 from the watchdog, no verdict, no commit, last beat 10 s after git started
  - The image has git 2.47.3, and `env -i git` there resolves git through glibc's default path. Both
    are unverified until the lane.
- **Coverage** was not re-measured: no Python changed (`git diff --stat 95e4128 HEAD -- bench tests/unit
  tools` is empty).

**changed_other_features:** none. `run` (003) is named in the README only. The flaky unit reported below
is in 002's code, and was not changed.

**process_failures_recorded**
1. **A flaky unit in 002's bench runner.** The first `make test-host` failed one test:
   `tests/unit/test_bench_runner.py::test_totals_and_endings_match_rb4[git-inspect-vanilla]`, with
   `Ending(kind='failed', reason='setup failed: hung')`.
   - The file passed 21/21 three times in isolation. The full host lane then passed: 676 units, env
     layer 60/60, hook logic 29/29.
   - The task's setup runs under the same call limit as the agent's calls (`runner.py:161`, `ex.run(task.setup,
     ctx.limits.call_s)`), so a loaded host can time setup out.
   - Not this cycle's code. Noted for 002 slice 1's bench-driver hardening (a watch item).
2. **Plugin blocks run as a script without `CLAUDE_PLUGIN_ROOT`.** Implement step 10's
   `quality-scale` block reads `PLUGIN_DIR="${CLAUDE_PLUGIN_ROOT}"`. The session fills that in when it
   expands the command; a script does not. The first run reported `lib/quality-scale.sh is not in this
   install`. It was discarded and re-run with the variable set to the 2.22.0 path. This was this
   instance's extraction error, the same one 003's ship hit, and is now in `reboot.md`.
3. **Plugin defects, for the mentor to relay** (decided from the files, not worked around in code):
   - `/specswarm:plan`, `/specswarm:tasks` and `/specswarm:implement` read the feature number with
     `grep -oE '^[0-9]{3}'`. On `modify/001-…` that finds nothing, and they fall back to the
     **newest** feature (003). 2.22.0 fixed this class in analyze-quality's `quality-report` block
     (`^([a-z]+/)?[0-9]{3}`), but not here.
   - `/specswarm:modify`'s expanded text again clobbered the shell functions' positional parameters
     (`in_list` and `has` grep for the send path instead of `$1`).
   - implement's scope matcher cannot match a bare file name with no `/` and no extension, so T077's
     `Makefile`, named in `tasks.md`, computed as `SCOPE: out — Makefile`. The record is left as
     computed.
   - Step 10's "Why there is no score" counts unit tests among "SpecSwarm's gap". Here, unit tests are
     unavailable because pytest is not installed for this machine's system Python. That is the
     machine's gap, not the plugin's.

**retired_prompts_seen:** none.

### Implement step 10 — quality validation (specswarm 2.22.0), as the library reported it

```
🧪 Running Quality Validation
=============================
- Detector:
{
  "frameworks": ["pytest"],
  "primary": "pytest",
  "count": 1
}

- run_tests pytest: rc=2
/usr/bin/python3: No module named pytest
run_tests: pytest is declared by this project but not installed here
- parse_test_results: total=unknown passed=unknown failed=unknown skipped=unknown
- run_coverage pytest: unknown (rc 1)
- components:
unit-tests|25|-|unavailable:run_tests returned 2 — pytest is declared but not installed for /usr/bin/python3 (the suite runs in the image and a scratch venv)
coverage|25|-|unavailable:run_coverage printed unknown (rc 1)
integration-tests|15|-|not-applicable:no integration suite is detected by the plugin (e2e bats run in the Docker lane)
browser-tests|15|-|not-applicable:no web project detected, so there is nothing to drive a browser over
bundle-size|20|-|unavailable:lib/bundle-size-monitor.sh is not present in this install
visual-alignment|15|-|unavailable:screenshot analysis is not implemented

Quality Score: unknown — no component could be measured, so there is no score to compare
Excluded:
unit-tests — unavailable: run_tests returned 2 — pytest is declared but not installed for /usr/bin/python3 (the suite runs in the image and a scratch venv) (25 points not counted either way)
coverage — unavailable: run_coverage printed unknown (rc 1) (25 points not counted either way)
integration-tests — not-applicable: no integration suite is detected by the plugin (e2e bats run in the Docker lane) (15 points not counted either way)
browser-tests — not-applicable: no web project detected, so there is nothing to drive a browser over (15 points not counted either way)
bundle-size — unavailable: lib/bundle-size-monitor.sh is not present in this install (20 points not counted either way)
visual-alignment — unavailable: screenshot analysis is not implemented (15 points not counted either way)


ℹ️  Why there is no score, and whose gap it is
   Every component was excluded. Each line below says which:
     - unit-tests — unavailable: run_tests returned 2 — pytest is declared but not installed for /usr/bin/python3 (the suite runs in the image and a scratch venv) (25 points not counted either way)
     - coverage — unavailable: run_coverage printed unknown (rc 1) (25 points not counted either way)
     - integration-tests — not-applicable: no integration suite is detected by the plugin (e2e bats run in the Docker lane) (15 points not counted either way)
     - browser-tests — not-applicable: no web project detected, so there is nothing to drive a browser over (15 points not counted either way)
     - bundle-size — unavailable: lib/bundle-size-monitor.sh is not present in this install (20 points not counted either way)
     - visual-alignment — unavailable: screenshot analysis is not implemented (15 points not counted either way)

   4 component(s) could not be measured because something this plugin ships is
   absent — that is SpecSwarm's gap, not this project's.
   2 component(s) do not apply to a project of this kind, which is not a defect.
block_merge_on_failure=false
```

The gate is **UNKNOWN**, and with `block_merge_on_failure: false` it warns and does not halt. No
component was filled in by hand. The project's own host-lane figures are recorded **beside** the score
in `.specswarm/metrics.json` → `001-cycle-6.project_measurements_not_scored`.

**Host lane** (advisory; scratch venv):
- ruff 0.16.7: "All checks passed!", "46 files already formatted"
- mypy 2.3.1: "Success: no issues found in 15 source files"
- shellcheck 0.11.0: clean over 28 files
- `make test-host`: passed on the second run (676 units; env layer 60/60; hook logic 29/29). The first
  run failed one 002 unit (process failure 1).

**Implement step 9b: decision log** (plugin `scope-tally` and `decision-tally` over the whole of 001's `tasks.md` and `decisions.md`, all cycles, after T078):

```
scope: planned=78 recorded=71 unplanned=0 unrecorded=7 in=54 out=12 none=13 unknown=0 flagged=47 flagged_out=8 other=32 other_out=4
decisions: sections=82 flagged_sections=47 non_flagged_sections=35 sections_without_absent=8 flagged=83 assumed=107 deferred=6 absent=93 inherited=84 low_confidence=0 flagged_low_confidence=0
```

Cycle 6 alone (T074–T078): 5 sections, 6 FLAGGED entries, 0 low-confidence. `SCOPE:` none 1 (T074), in 2 (T075, T076), out 2 (T077 `Makefile`, the matcher defect above; T078 `.specswarm/metrics.json`, written by implement step 10 and not named in `tasks.md`).

### Cycle 6 — Docker lane addendum 1 (tests passed; scan blocked by the base layer)

Written 2026-10-01 from `tests/out/`, `scan/out/` and the mentor's lane entry in `../bridge/history.md`
(2026-10-01T21:05:37Z).

**`make test` at `474a48b`** (`tests/out/summary.json`, 20:33:57Z–20:48:31Z): `exit 0`, every step
passed.
- e2e: **198 of 198**
- units: 676 passed
- start-up: p95 87.7 ms over 50 runs (budget 100 ms, Python 3.14.7)

The four new cells passed in the image (git 2.47.3), as on the host:
- TAP 160 and 161: `.git/hooks` bounded under `env -i`, 4.4 s each (the 2 s limit, the verdict, no
  commit, the hook stopped)
- TAP 162 and 163: a local `core.hooksPath` unbounded under `env -i`, 12.3 s each (ended by the test's
  10 s watchdog, no verdict, the hook's last beat at least 7 s after git started)

**`make scan` at `474a48b`: FAIL** on all three images (agent 4 blocking, vanilla 12, bench-driver 12).
None of it comes from this cycle's changes:
- Debian fixed OpenSSL (CVE-2026-54873, -72897, -84782, -84784 → 3.5.7-1~deb13u3) and PCRE2
  (CVE-2026-103111 → 10.46-1~deb13u3). The gate never lets a baseline hide a finding that gained a fix.
- CVE-2026-102010 (gcc-14 runtime, no fix) is new.

FOR-MENTOR Item 12 records it. The operator decided (21:05:37Z): accept CVE-2026-102010, and refresh
the base layer first as separate maintenance; then this branch merges `master` in and the lane
re-runs.

**Criteria:** not given modes here. The image the merge will carry changes with the base refresh, so
the modes, and the `full` audit-log row appending 8 and 9, wait for the lane re-run on this branch
after `master` is merged in.

### Cycle 6 — Docker lane addendum 2 (the re-run on `f2eaf82`: tests and scan passed)

Written 2026-10-02 from `tests/out/`, `scan/out/`, the lane logs `../bridge/.make-test-001-rev9-b.log`
and `../bridge/.make-scan-001-rev9-b.log`, and the mentor's sign-off in `../bridge/history.md`
(2026-10-02T01:21:07Z). Under specswarm **4.0.1-botbaubble.2.24.0**, which this session loaded.

**What ran:** `modify/001-rev9-scope-and-t4` at **`f2eaf82`**. That is Cycle 6 with `master` at `4b2b5b1`
(the base-layer maintenance, FOR-MENTOR Item 12) merged in. Both logs record `HEAD=f2eaf82…` with
`status=[]` before and after the run.

**`make test` at `f2eaf82`** (`tests/out/summary.json`: `git_sha` `f2eaf82f2f1d…`,
00:44:30Z–01:04:09Z, `exit 0`):
- e2e: **198 of 198** (`tests/out/e2e.tap`, no `not ok`)
- units: 676 passed (`tests/out/unit.txt`)
- start-up: p95 94.1 ms over 50 runs (budget 100 ms, Python 3.14.7; `tests/out/startup.json`)
- The four T4 `env -i` cells passed again: TAP 160 and 161 (`.git/hooks`, bounded) at 4.4 s each, and
  TAP 162 and 163 (local `core.hooksPath`, unbounded, ended by the test's watchdog) at 12.3 s each.

**`make scan` at `f2eaf82`: PASS on all three images**, 0 blocking each (`exit=0`, 01:20:45Z). The
images keep base digest `a99cfc517144`:
- agent `9dbaab11d1d1…`: 80 baselined (`scan/out/verdict.json`)
- vanilla `f876c0c67d0d…`: 79 baselined (`scan/out/timelike-vanilla/verdict.json`)
- bench-driver `041a4708e8cc…`: 51 baselined (`scan/out/timelike-bench-driver/verdict.json`)

The first scan attempt (00:44Z) exited 125 before scanning, because `timelike-hostrunner:local` was not
built yet. It gave no verdict, and the log above replaced it.

**How TAP lines were attributed.** SC numbers repeat across features 001, 002 and 003, so each TAP line
was matched to an e2e file by its title against the files' `@test` titles. All 198 matched exactly one
file, and each file's lines are contiguous. 001's files are TAP 1–167; 003's `run` files are 168–193;
002's bench is 194–198.

**criteria_reestablished (update to Cycle 6 above).** Each citation is § Cycle 6's, unchanged, and
matches one line of the send (`grep -cF` = 1 for all 13).
- `01 · "each exit within 20 seconds without opening a pager or editor"` —
  **executed [`tests/e2e/git-log-diff-commit-rebase-exit-within-20-seconds.bats`]**, TAP 98–147, 50 of
  50 ok
- `01 · "the environment's pager, editor, prompt and colour defaults are all in effect, verified by one test per invocation style"` —
  **executed [`tests/e2e/bash-c-and-bash-lc-defaults-in-effect.bats`]**, TAP 23–38, 16 of 16 ok
- `01 · "fails fast with a non-zero exit instead of prompting"` —
  **executed [`tests/e2e/credentials-fail-fast.bats`]**, TAP 72–97, 26 of 26 ok
- `01 · "a commit a pre-commit hook rejects fails with the hook's output, as it would without timelike"` —
  **executed [`tests/e2e/hooks-a-repository-configures-run.bats`]**, TAP 153–159, 7 of 7 ok
- `01 · "is killed and the git command exits non-zero within the limit plus a few seconds, with a verdict naming the hook"` —
  **executed [`tests/e2e/hook-past-its-time-limit-is-killed.bats`]**, TAP 148–152, 5 of 5 ok
- `01 · "cannot run any command as root, cannot change firewall rules, and cannot read files owned by Adele"` —
  **executed [`tests/e2e/agent-cannot-run-as-root-change-firewall-or-read-adele.bats`]**, TAP 1–22, 22
  of 22 ok
- `` 01 · "fails when any tool lacks `--help` within 40 lines" `` —
  **executed [`tests/e2e/conformance-check-over-every-timelike-tool-on-path.bats`]**, TAP 39–52, 14 of
  14 ok
- `01 · "each write to their own scratch space, and neither's output files or event log entries appear in the other's"` —
  **executed [`tests/e2e/peer-agents-write-to-own-scratch-space.bats`]**, TAP 164–167, 4 of 4 ok
- `01 · "are derived from the container's CPU limit rather than the host's CPU count"` —
  **executed [`tests/e2e/container-derived-defaults.bats`, SC-8 cells]**, TAP 53–60, 8 of 8 ok
- `01 · "are absent from the agent's environment unless explicitly allow-listed"` —
  **executed [`tests/e2e/container-derived-defaults.bats`, SC-9 cells]**, TAP 61–64, 4 of 4 ok
- `01 · "The timezone defaults to UTC and interactive language REPLs default to their basic, scriptable prompt mode"` —
  **executed [`tests/e2e/container-derived-defaults.bats`, SC-10 cells]**, TAP 65–71, 7 of 7 ok
- `01 · "each returns within seconds instead of waiting on an editor, pager or prompt"` —
  **unconfirmed**. Manual (D1). Nobody observed it this cycle, and the cycle changes nothing it
  observes. SC-1's 50 cells (above) exercise the same commands, but they are not the demo.
- `01 · "can predict, for a tool they have not seen, what its first line, last line and exit codes will be"` —
  **unconfirmed**. Manual (SC-11). Nobody observed it this cycle.

**reconcile_mode, completed:** `full`. Revisions 8 and 9 are appended: `audited_against` is now
`[2, 3, 4, 5, 6, 7, 8, 9]`, and a `full` row in `audit-log.md` completes the deferred one. The basis is
unchanged from § Cycle 6: revision 8 did not change prompt 01, revision 9 changed no criterion, and rule
5's scope sentence is copied into the spec as declared. The lane has now re-established the cycle in the
image.

**not_verified, updated:** the image-level gaps listed in § Cycle 6 are closed by this lane. The two
Manual criteria stay unconfirmed. Coverage was not re-measured, because the merge of `master` brought in
no Python (`fe385c8..f2eaf82` adds only the six maintenance files: Dockerfiles and baselines).

**FOR-MENTOR Item 12:** closed (the scan passes at `f2eaf82`, with `4b2b5b1` merged in).

**Not merged yet.** The mentor signed off at `f2eaf82` (2026-10-02T01:21:07Z), on condition that later
commits are bookkeeping only. Ship's output and analyze-quality's output follow in a ship addendum.

### Cycle 6 — ship (specswarm 2.24.0), as the plugin reported it

Run 2026-10-02 at `eac4342` on `modify/001-rev9-scope-and-t4`, after the mentor's sign-off at `f2eaf82`
(2026-10-02T01:21:07Z). `eac4342` adds only the bookkeeping: lane addendum 2, the audit-log row,
`audited_against`, and FOR-MENTOR Item 12's closure.
- **Version:** this session loaded **specswarm 4.0.1-botbaubble.2.24.0**. The expanded `/specswarm:ship`
  named the 2.24.0 cache directory, and `quality-report.json` records it as `generated_by_version`.
- **How the blocks were run:** analyze-quality's and ship's blocks were run as installed, extracted from
  the 2.24.0 command files, with `CLAUDE_PLUGIN_ROOT` set to the 2.24.0 cache path.
  - analyze-quality: `analysis-context`, `component-applicability`, `tests-agnostic-score`,
    `unknown-resolvability`, `module-score`, `overall-score` and `quality-report`. The modules are
    001's 8. Substituting `AQ_TESTS_SCORE` into the tests component, which the command describes in
    prose, was done by the script. The `KEY=value` and list lines are the script's own echoes of
    the blocks' variables, as at 003's ship.
  - ship: every `bash` block from Pre-Flight to the end of Step 3. `FEATURE_DIR` was set to this
    feature's directory for `quality-source`, because ship assigns it nowhere.
- **What 2.24.0 changed, as seen here** (compare 003's ship under 2.22.0):
  - `quality-report.json` was written on a `modify/001-…` branch. 2.19.0 resolved no feature on this
    branch shape.
  - It reads `modules_scored: 0` with `modules_total: 8`, instead of 2.22.0's false
    `modules_scored: 8` beside "8 unscored" (D71).
  - Step 3's advice under an unknown gate states `unknown_why`, and says a re-run will not change it,
    instead of the improve-and-retry list (D72).
- `.specswarm/features/001-agent-shell-baseline/quality-report.json` was rewritten by analyze-quality
  (below). It replaces cycle 5's report.

#### analyze-quality output (verbatim)

```
📊 Codebase Quality Analysis
============================

Analyzing: .
Started: 2026-10-02T04:23:47+00:00

🔤 Language: Python
AQ_MEASURABLE=no
AQ_TESTS_LINE=tests|25|?|measured:pytest
run_tests rc=2
/usr/bin/python3: No module named pytest
run_tests: pytest is declared by this project but not installed here
AQ_TESTS_SCORE=unavailable:pytest is declared but could not be run on this machine
AQ_UNKNOWN_IS=unresolvable
AQ_UNKNOWN_WHY=no component of this Python project could be measured: pytest is declared but could not be run on this machine
MODULE_COMPONENTS:
tests|25|-|unavailable:pytest is declared but could not be run on this machine
docs|15|-|unavailable:sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector
architecture|20|-|unavailable:sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector
security|20|-|unavailable:sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector
bundle|7|-|unavailable:lib/bundle-size-monitor.sh is not in this install
lazy-loading|7|-|unavailable:sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector
images|6|-|unavailable:sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector
MODULE_SCORES:
tools/agentio|unknown
tools/bin|unknown
scan|unknown
image|unknown
scripts|unknown
bench/benchlib|unknown
bench/bin|unknown
bench/images+run.sh|unknown
MODULE_EXCLUDED_NOTES:
tools/agentio: tests — unavailable: pytest is declared but could not be run on this machine (25 points not counted either way)
docs — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (15 points not counted either way)
architecture — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
security — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
bundle — unavailable: lib/bundle-size-monitor.sh is not in this install (7 points not counted either way)
lazy-loading — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (7 points not counted either way)
images — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (6 points not counted either way)
tools/bin: tests — unavailable: pytest is declared but could not be run on this machine (25 points not counted either way)
docs — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (15 points not counted either way)
architecture — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
security — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
bundle — unavailable: lib/bundle-size-monitor.sh is not in this install (7 points not counted either way)
lazy-loading — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (7 points not counted either way)
images — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (6 points not counted either way)
scan: tests — unavailable: pytest is declared but could not be run on this machine (25 points not counted either way)
docs — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (15 points not counted either way)
architecture — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
security — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
bundle — unavailable: lib/bundle-size-monitor.sh is not in this install (7 points not counted either way)
lazy-loading — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (7 points not counted either way)
images — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (6 points not counted either way)
image: tests — unavailable: pytest is declared but could not be run on this machine (25 points not counted either way)
docs — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (15 points not counted either way)
architecture — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
security — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
bundle — unavailable: lib/bundle-size-monitor.sh is not in this install (7 points not counted either way)
lazy-loading — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (7 points not counted either way)
images — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (6 points not counted either way)
scripts: tests — unavailable: pytest is declared but could not be run on this machine (25 points not counted either way)
docs — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (15 points not counted either way)
architecture — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
security — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
bundle — unavailable: lib/bundle-size-monitor.sh is not in this install (7 points not counted either way)
lazy-loading — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (7 points not counted either way)
images — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (6 points not counted either way)
bench/benchlib: tests — unavailable: pytest is declared but could not be run on this machine (25 points not counted either way)
docs — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (15 points not counted either way)
architecture — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
security — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
bundle — unavailable: lib/bundle-size-monitor.sh is not in this install (7 points not counted either way)
lazy-loading — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (7 points not counted either way)
images — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (6 points not counted either way)
bench/bin: tests — unavailable: pytest is declared but could not be run on this machine (25 points not counted either way)
docs — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (15 points not counted either way)
architecture — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
security — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
bundle — unavailable: lib/bundle-size-monitor.sh is not in this install (7 points not counted either way)
lazy-loading — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (7 points not counted either way)
images — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (6 points not counted either way)
bench/images+run.sh: tests — unavailable: pytest is declared but could not be run on this machine (25 points not counted either way)
docs — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (15 points not counted either way)
architecture — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
security — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
bundle — unavailable: lib/bundle-size-monitor.sh is not in this install (7 points not counted either way)
lazy-loading — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (7 points not counted either way)
images — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (6 points not counted either way)

Overall Quality: unknown (no module could be scored (8 unscored))
📄 Wrote .specswarm/features/001-agent-shell-baseline/quality-report.json (overall_state: unknown, written by 4.0.1-botbaubble.2.24.0)
QUALITY_SCORE=unknown
```

#### ship output, steps 1–3 (verbatim; the threshold lines and the gate)

```
🚢 SpecSwarm Ship - Quality-Gated Merge
══════════════════════════════════════════

This command enforces quality standards before merge:
  1. Runs comprehensive quality analysis
  2. Checks quality score meets threshold
  3. If passing: merges to parent branch
  4. If failing: reports issues and blocks merge

📍 Current branch: modify/001-rev9-scope-and-t4

NOTE: .specswarm/features/001-agent-shell-baseline/quality-report.json reports overall_state='unknown' - the score is not a measurement
📋 Using project quality threshold: 0% (from min_quality_score)
ℹ️  enforce_gates: false — a failing gate will WARN, not block

🎯 Quality Threshold: 0%
📊 Actual Quality Score: unknown — nothing was measured

❌ Quality gate UNKNOWN — no "Overall Quality: NN%" line was produced

   Nothing was measured. This is NOT a 0% failure and NOT a pass:
   the analysis did not run, did not report a score, or could not measure this project.


🔧 What would change this:
  - no component of this Python project could be measured: pytest is declared but could not be run on this machine
  - re-running /specswarm:analyze-quality will NOT change this result

⚠️  enforce_gates: false — this gate WARNS and does not block the merge.
   Shipping a unknown quality result is the project's recorded choice, not an oversight.

```

**Step 4 (`/specswarm:complete`)** needs stdin, so the merge is done by hand:
`git checkout master && git merge --no-ff modify/001-rev9-scope-and-t4`. The merge commit is reported to
the mentor. Its tree is checked to equal `f2eaf82`'s plus only this cycle's bookkeeping and ship files:
this report, `audit-log.md`, `spec.md`'s `audited_against`, `quality-report.json`, and `FOR-MENTOR.md`.

## Cycle 7 — bridge/sends/01-rev10-20261003-003933.md

**Written:** 2026-10-03. Not in dispatch mode. Built with `/specswarm:modify --from-send`, then
`/specswarm:plan`, `/specswarm:tasks` and `/specswarm:implement`, on `modify/001-rev10-rule9-grant-envelope`
from `master` at `36a5be1` (the public lineage). **Pushed nothing; not merged** (CLAUDE.md rule 5: the
merge and any push wait for the mentor's discharge and the operator's OK).

**specswarm version (lore Q002):** this session loaded **4.0.1-botbaubble.2.26.1**, which the expanded
commands name (`PLUGIN_DIR=…/4.0.1-botbaubble.2.26.1`), not the 2.27.0 the send asked for (installed
2026-10-02T18:33Z, `713ec86`; the session started before it). Checked before going on:
`diff -rq` of the two cache directories shows **only `commands/ship.md` and `plugin.json` differ**.
`modify.md`, `plan.md`, `tasks.md`, `implement.md` and every `lib/` file are byte-identical, so every
command this cycle ran is 2.27.0's code. Ship (D85's first field run) is not part of this cycle; it
needs a session that has loaded 2.27.0.

**Status in one line:** no behaviour change, `.specswarm/` only. Spec rule 9 carries revision 10's
sentence, declared; 001's contract already agreed with it clause by clause; `audited_against` gains 10.

### Group A — cited from `.implement-complete`

Group A: not applicable — no marker on this path

### Group B — copied from the send

| Field | Value |
|---|---|
| source_send | bridge/sends/01-rev10-20261003-003933.md |
| source_prompt | plan/.discover/prompts/01-agent-shell-baseline.md |
| prompt_revision | 10 |
| discovery_revision | 10 |
| slice | 1 |

### Group C — written by the code instance

**delegations:** one.
- A general-purpose subagent, read-only (no edits, no commits, nothing under `../bridge`, `../plan` or
  `.specswarm/` written): read 001's contract files against revision 10's sentence, clause by clause,
  and reported each file's statement with line numbers. It found no disagreement. Its key citations
  were re-read here before use (`output-contract.md:33` and `:112–125`, `conformance.md:34` and `:53`,
  both schemas' properties, `b7a6ea6` as T018's commit). Its table is condensed into
  `impact-analysis.md` § Cycle 7.

**criteria_reestablished**

No criterion changed at revision 10 (the Acceptance Criteria of `01-rev9-20261001-191224.md` and this
send are byte-identical). This cycle changed only files under `.specswarm/`, so, as the send directs, the
11 automated criteria are cited from **an earlier lane on an identical non-bookkeeping tree**: the
mentor's Docker lane at `f73ac79` (2026-10-02, 20:01Z; `make test` e2e 239/239 with 001's files at TAP
1–167 and units passing; `make scan` PASS on four images, deny-list PASS). Outside `.specswarm/`, this
branch equals `master` (`git diff master HEAD -- . ':!.specswarm'` is empty), and `master` differs from
`f73ac79` only in `CLAUDE.md` (rule 5), `FOR-MENTOR.md` and `reboot.md`. No lane ran for this cycle.

- `01 · "each exit within 20 seconds without opening a pager or editor"` — **executed [`make test` at `f73ac79`, mentor's lane: 001's e2e files]** (cited, not re-run; tree identical outside `.specswarm/` and bookkeeping)
- `01 · "the environment's pager, editor, prompt and colour defaults are all in effect, verified by one test per invocation style"` — **executed [`make test` at `f73ac79`, mentor's lane: 001's e2e files]** (cited, not re-run; tree identical outside `.specswarm/` and bookkeeping)
- `01 · "fails fast with a non-zero exit instead of prompting"` — **executed [`make test` at `f73ac79`, mentor's lane: 001's e2e files]** (cited, not re-run; tree identical outside `.specswarm/` and bookkeeping)
- `01 · "a commit a pre-commit hook rejects fails with the hook's output, as it would without timelike"` — **executed [`make test` at `f73ac79`, mentor's lane: 001's e2e files]** (cited, not re-run; tree identical outside `.specswarm/` and bookkeeping)
- `01 · "is killed and the git command exits non-zero within the limit plus a few seconds, with a verdict naming the hook"` — **executed [`make test` at `f73ac79`, mentor's lane: 001's e2e files]** (cited, not re-run; tree identical outside `.specswarm/` and bookkeeping)
- `01 · "cannot run any command as root, cannot change firewall rules, and cannot read files owned by Adele"` — **executed [`make test` at `f73ac79`, mentor's lane: 001's e2e files]** (cited, not re-run; tree identical outside `.specswarm/` and bookkeeping)
- `` 01 · "fails when any tool lacks `--help` within 40 lines" `` — **executed [`make test` at `f73ac79`, mentor's lane: 001's e2e files]** (cited, not re-run; tree identical outside `.specswarm/` and bookkeeping)
- `01 · "each write to their own scratch space, and neither's output files or event log entries appear in the other's"` — **executed [`make test` at `f73ac79`, mentor's lane: 001's e2e files]** (cited, not re-run; tree identical outside `.specswarm/` and bookkeeping)
- `01 · "are derived from the container's CPU limit rather than the host's CPU count"` — **executed [`make test` at `f73ac79`, mentor's lane: 001's e2e files]** (cited, not re-run; tree identical outside `.specswarm/` and bookkeeping)
- `01 · "are absent from the agent's environment unless explicitly allow-listed"` — **executed [`make test` at `f73ac79`, mentor's lane: 001's e2e files]** (cited, not re-run; tree identical outside `.specswarm/` and bookkeeping)
- `01 · "The timezone defaults to UTC and interactive language REPLs default to their basic, scriptable prompt mode"` — **executed [`make test` at `f73ac79`, mentor's lane: 001's e2e files]** (cited, not re-run; tree identical outside `.specswarm/` and bookkeeping)
- `01 · "each returns within seconds instead of waiting on an editor, pager or prompt"` — **unconfirmed**.
  Manual (D1); unchanged by this cycle.
- `01 · "can predict, for a tool they have not seen, what its first line, last line and exit codes will be"` —
  **unconfirmed**. Manual (SC-11); unchanged by this cycle. Rule 9's new sentence is part of what such a
  reader predicts from.

Each citation was checked to match exactly one line of the send (`grep -cF` = 1 for all 13).

**reconcile_mode:** `full`. Revision 10 is appended: `audited_against` is now `[2, 3, 4, 5, 6, 7, 8, 9, 10]`
(T080, computed by the installed `audit-append` block: `MODE_USED=full`, `APPENDED=10`, no note).
- Revision 10 changed no criterion. The criteria diff against the rev-9 send is empty (sha256
  `7d42021a…` for both sections), so removals and rewordings are visible, and none occurred.
- Revision 10's one change, rule 9's clarification, needs no body change. Spec line 181 is the body's
  only statement about exit 4's envelope, and it stays true: revision 10 adds a second envelope and
  contradicts nothing. The spec never mentioned the confirm envelope's `grant` field that T018 removed.
  **Not SUPERSEDED; not regenerated.**
- Appended in this cycle rather than deferred to a lane addendum (this instance's usual convention),
  because the send directs it for a `.specswarm/`-only cycle and names the lane to cite. Recorded as a
  FLAGGED decision in T080.

**The send's items:**
1. **Rule 9's clarification recorded** (T079, `1f7a563`). The annotation's sentence equals the send's
   rule-9 clarification after whitespace normalisation, with a provenance note in the shape of rule 5's
   (T074).
2. **001's contract checked against it (lore P004: what was compared).** Each file read, and what it
   says:
   - `contracts/output-contract.md:33`: exit 4 "carries one envelope, told apart by `status`:
     `confirmation_required` … or `grant_required`". **Agrees.**
   - `contracts/output-contract.md:112–125` (§ Confirmation): the confirmation envelope, then "A missing
     grant is the other exit-4 envelope": the grant, `limit {name, allowed, needed}`, `extend`,
     `extend_by: "operator"`, `performed: false`; the operator's command "never in `confirm`"; not
     `--yes`-confirmed, "the grant is the confirmation"; "Rule 8 still binds it". **Agrees, every clause.**
   - `contracts/grant-envelope.schema.json`: requires `grant`, `limit`, `extend`, `extend_by` (const
     `operator`), `performed` (const `false`), `status` const `grant_required`; its description says it
     has no `confirm` key, checked by C9 and the agentio units. **Agrees.**
   - `contracts/confirm-envelope.schema.json`: properties `tool, target, scope, status, plan, confirm`,
     `status` const `confirmation_required`, **no `grant`**. **Agrees**; silent on an operator command in
     `confirm` (no `additionalProperties: false`), which C9 enforces.
   - `tools/agentio/agentio.py` `grant_required()` (:276–312): only for `Tool(grant_envelope=True)`; emits
     the grant envelope with `extend_by="operator"`, `performed=False`, exit 4. `confirm_required()`
     builds `confirm` from the tool's own argv plus `--yes`. **Agrees.**
   - Conformance C9 (`contracts/conformance.md:34`; `tools/bin/timelike-conform` `check_envelope`):
     every exit 4 prints one envelope of a declared `status`; a grant envelope has `limit`,
     `extend_by: "operator"`, `performed: false` and no `confirm`; no `confirm` names a command outside
     the tool's own. **Agrees.**

   **Disagreements: none.** All six files were last changed by 004's T018 (`b7a6ea6`, on
   `archive/pre-publish`), and `git diff archive/pre-publish HEAD` is empty for them.
3. **No Docker lane:** only `.specswarm/` changed, so the `f73ac79` lane is cited (above).

**not_verified**
- **No test ran in this cycle**, on the host or in the image. The 11 automated criteria are cited from
  the `f73ac79` lane, not re-executed. The citation holds because the tree outside `.specswarm/` is
  unchanged apart from bookkeeping; it would not survive a change to code, tests or the image.
- **Two observations from the contract read, not acted on** (for the mentor):
  - Revision 10's "rule 8 still applies" is stated only in `output-contract.md:123–124`. The schemas,
    C9 and agentio say nothing about it. agentio ties `--dry-run` to `destructive` for every tool, which
    is rule 8 itself, so nothing is missing; but nothing checks a grant client specifically.
  - Nothing forbids declaring a tool both `mutating=True` and `grant_envelope=True`, which would give a
    grant client `--yes`, against revision 10. No tool does (`adele` leaves `mutating` False). In that
    combination `Tool.codes()` would describe exit 4 as confirmation only. A guard belongs to the cycle
    that adds a second grant client.
- The two Manual criteria (D1, SC-11) stay `unconfirmed`.

**changed_other_features:** none. Nothing outside 001's own feature directory and `.specswarm/metrics.json`
changed.

**process_failures_recorded**
1. **The session's plugin version.** The send asked for a session that had loaded 2.27.0; this one had
   loaded 2.26.1. Found from the first expanded command, checked by `diff -rq` (above), and carried on
   because the commands this cycle runs are identical. Ship needs a fresh session.
2. **Step-10 reasons reworded once.** The first run of the `quality-scale` block named unit tests and
   coverage as `unavailable: run_tests returned 2 …` and `… printed unknown`, which carry neither of the
   plugin's attribution literals, so "Why there is no score" put them in the unattributed bucket. They
   were re-run as "could not be run on this machine", which is the same fact in the plugin's own words
   (`reboot.md` already said so). The second run is recorded below; no score changed (unknown both times).
3. **Plugin observations, for the mentor to relay** (first `modify` under 2.26.0+, as the send asked):
   - `lib/features-location.sh` wrote **nothing to stderr** in modify, plan, tasks or implement.
     `fnum_resolve` resolved `modify/001-rev10-…` to 001 with no fallback, so 2.24.0's fix holds in the field.
   - **modify's helpers (D81, named variables) needed no workaround.** `provenance-row` and
     `audit-append` ran as installed, and gave row 7 and `full`/`10`. The expansion still substitutes `$1`
     inside a **comment** of both blocks (the D76 comment now reads "`bridge/sends/01-rev10-…` stops
     meaning …"); cosmetic, no code affected.
   - `modify.md` Step 2 tells the reader to "read the provenance frontmatter" but ships no block that
     extracts `source_prompt`, `prompt_revision`, `audited_against` or the prompt's `N`, so
     `provenance-row`'s inputs are read by hand. Worked, but it is the one unmechanised step left in the row.
   - **`lib/quality-gates.sh` is absent** from both 2.26.1 and 2.27.0. Implement step 10e sources it
     (`detect_browser_test_framework`), behind a guard that says "record it as unmeasured". This
     instance's script skipped the guard and got `No such file or directory`. Browser applicability came
     from the `quality-components` block (`not-applicable: no web project detected`), so the score is
     unaffected. Not reported before (no hit in `.specswarm/`, FOR-MENTOR or `bridge/history.md`).

**retired_prompts_seen:** none.

### Implement step 10 — quality validation (specswarm 2.26.1 blocks, identical in 2.27.0), as the library reported it

```
🧪 Running Quality Validation
=============================
== b detect
{
  "frameworks": ["pytest"],
  "primary": "pytest",
  "count": 1
}
rc=0
PRIMARY=pytest
== c run_tests
rc=2
/usr/bin/python3: No module named pytest
run_tests: pytest is declared by this project but not installed here
== parse
total=unknown passed=unknown failed=unknown skipped=unknown
== d coverage
rc=0
rc=1 out=unknown
== e browser
<scratchpad>/step10.sh: line 9: <plugin cache>/4.0.1-botbaubble.2.26.1/lib/quality-gates.sh: No such file or directory
rc=1
- components (second run; see process failure 2):
Quality Score: unknown — no component could be measured, so there is no score to compare

ℹ️  Why there is no score, and whose gap it is
   Every component was excluded. Each line below says which:
     - unit_tests — unavailable: pytest could not be run on this machine (run_tests returned 2: declared by this project, not installed for /usr/bin/python3) (25 points not counted either way)
     - coverage — unavailable: pytest could not be run on this machine, so run_coverage printed unknown (rc 1) (25 points not counted either way)
     - integration_tests — not-applicable: no integration suite detected by the plugin; the bats e2e run only in the Docker lane (15 points not counted either way)
     - browser_tests — not-applicable: no web project detected, so there is nothing to drive a browser over (15 points not counted either way)
     - bundle_size — unavailable: lib/bundle-size-monitor.sh is not present in this install (20 points not counted either way)
     - visual_alignment — unavailable: screenshot analysis is not implemented (15 points not counted either way)

   2 component(s) could not be measured because something this plugin ships is
   absent from this install — that is SpecSwarm's gap, not this project's.
   2 component(s) could not be measured because something this project
   declares could not be run on this machine — that is neither a defect in SpecSwarm
   nor in the project: install it here, or run where it is installed.
   2 component(s) do not apply to a project of this kind, which is not a defect.
block_merge_on_failure=false
```

The gate is **UNKNOWN**, and with `block_merge_on_failure: false` (and `min_quality_score: 0`) it warns
and does not halt. No component was filled in by hand. The output is verbatim except two absolute paths
in the `quality-gates.sh` error line, replaced by `<scratchpad>` and `<plugin cache>` (no local paths in
tracked files). `.specswarm/metrics.json` → `001-cycle-7`
records the same, with `lib/quality-gates.sh`'s absence under `plugin_tooling`.

**Host lane:** not run. Nothing outside `.specswarm/` changed (no code, test, lint target or image
input). The publish deny-list over the tree read `pass` with the list read before every commit
(7 entries, 247 files, P1–P7 0/0).

**Implement step 9b: decision log** (plugin `scope-tally` and `decision-tally` over the whole of 001's `tasks.md` and `decisions.md`, all cycles, after T081):

```
scope: planned=81 recorded=74 unplanned=0 unrecorded=7 in=55 out=12 none=15 unknown=0 flagged=49 flagged_out=8 other=33 other_out=4
decisions: sections=85 flagged_sections=49 non_flagged_sections=36 sections_without_absent=8 flagged=86 assumed=110 deferred=6 absent=98 inherited=87 low_confidence=0 flagged_low_confidence=0
```

Cycle 7 alone (T079–T081): 3 sections, 3 FLAGGED entries (T080's in-cycle append; T081's version and
reworded-reasons calls), 0 low-confidence. `SCOPE:` none 2 (T079, T080: `.specswarm/features/001-…`
only), in 1 (T081: `.specswarm/metrics.json`).
