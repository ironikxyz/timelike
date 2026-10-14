> Redacted for publication, 2026-10-02 (`bridge/sends/maint-publish-redaction-20261002-183624.md`): internal host names, absolute paths and a personal name replaced. No other change.

# Cycle report — 002 speedup bench

Append-only. One section per cycle, where a cycle is one archived send built to acceptance. Written by
the code instance; the mentor reads this file and never writes into it.

The send's cycle-report path, `.specswarm/features/[NNN]-[slug]/cycle-report.md`, is the same path this
project's CLAUDE.md names, so there is only this one file.

## Cycle 1 — bridge/sends/02-rev1-20260929-000641.md

**Written:** 2026-09-29, at the end of `/specswarm:implement`, not in dispatch mode. The sequence was
`/specswarm:specify --from-send`, then plan, tasks and implement. **Branch:** `002-speedup-bench`, from
`master` at `a265964`. **Not merged**; see `not_verified`.

**Status in one line:** slice 0 is written (T001–T020), and the host lane passes. **No acceptance
criterion has been re-established in an image**, because this workspace has no Docker daemon (001
research R10). The operator runs `make test`, `make bench` and `make scan` on the host.

### Group A — cited from `.implement-complete`

Group A: not applicable — no marker on this path

### Group B — copied from the send

| Field | Value |
|---|---|
| source_send | bridge/sends/02-rev1-20260929-000641.md |
| source_prompt | plan/.discover/prompts/02-speedup-bench.md |
| prompt_revision | 1 |
| discovery_revision | 6 |
| slice | 0 |

### Group C — written by the code instance

**delegations**

Each delegate had disjoint file ownership. None committed, and none touched `../bridge`, `../plan` or
`.specswarm/`. This instance reviewed every delegated file and committed each as its own task.

| # | Delegate | Scope | Tasks |
|---|---|---|---|
| 1 | research subagent | What vanilla trixie-slim contains; how git behaves with no TTY and no TERM, vanilla vs timelike (host `env -i` experiments); the slice-0 catalog; the fake agent's limits (P005) | research RB1–RB4, RB11 |
| 2 | research subagent | The driver container; killing a hung `docker exec`; trace paths; the staleness check; the key refusal; lane integration; the scan over three images | research RB5–RB10 |
| 3 | general-purpose subagent | `bench/benchlib/trace.py` and its units | T002 |
| 4 | general-purpose subagent | `bench/benchlib/keys.py` and its units; cross-checked against the real shell-env hook on 77 names | T003 |
| 5 | general-purpose subagent | `fakeagent.py` and `catalog.py` and their units; ran every task for real under vanilla and timelike emulation | T004, T005 |
| 6 | general-purpose subagent | `bench/vanilla/Dockerfile` and `bench/driver/Dockerfile` | T010, T011 |
| 7 | general-purpose subagent | `bench/benchlib/report.py` and its units | T016 |

This instance wrote the spec, the plan artifacts, and T001, T006–T009, T012–T015 and T017–T020. It also
corrected three things that delegates found (see `process_failures_recorded`).

**criteria_reestablished**

- `02 · "One command runs a task in both a vanilla image and the timelike image"` — **unconfirmed**.
  - The Docker lane has not run.
  - Test: `tests/e2e/speedup-bench.bats` "SC-1 one command runs a task in both a vanilla image and
    the timelike image and writes a per-run trace". It runs `bench/run.sh`, the operator's own command,
    and then the independent validator.
  - Host-lane evidence, which is advisory and not image evidence: `test_bench_cli` runs the real
    catalog, runner and wrapper through a stand-in docker; 8 traces are written and valid.
    `test_bench_runner` gets RB4's outcomes for all 8 task × environment pairs.
- `02 · "The bench runs end to end in CI against a deterministic fake agent without any API key"` —
  **unconfirmed**.
  - Same reason: the Docker lane has not run.
  - Test: `speedup-bench.bats` "SC-2 the bench runs end to end in CI…" (report, and no key-shaped
    variable in the driver or either image), plus "SC-2 a planted API key refuses the run before any
    trace is written".
  - "CI" here is the project's Docker lane (spec Assumption 2). No hosted CI or remote exists.
- `02 · "DEMO: the Adopting developer reads a bench report comparing a vanilla container with timelike on one task"` —
  **unconfirmed**. Nobody has read a report, because none has been produced in an image yet.
  - **Which report will be shown:** a fake-agent report from `make bench` (spec Assumption 8). No
    live run was built in this cycle.
  - Its first line says it proves the pipeline, not timelike's value.

**reconcile_mode:** full. This is a new spec, generated from this send: `prompt_revision: 1`,
`discovery_revision: 6`, `audited_against: [1]`. Governance was already audited through discovery
revision 6, and the send cites revision 6, so no governance audit was needed.

**not_verified**

1. **The Docker lane.**
   - None of the three images has been built: the agent image is rebuilt, and the vanilla and driver
     images are new.
   - `speedup-bench.bats` has not run.
   - SC-1 and SC-2 stay unconfirmed until the operator's `make test`. That run also exercises four
     things this workspace cannot check:
     - the busybox `realpath`, `stat -c` and `tr` that `bench/run.sh` uses when the runner calls it
     - the docker CLI's behaviour with `HOME=/tmp` under an arbitrary uid
     - the driver's `import agentio, benchlib` smoke line
     - the vanilla image's "no recommends slipped in" assertion
2. **`make scan` will block 002's merge until a person acts.**
   - `scan/scan.sh` now gates the agent, vanilla and driver images (FR-16).
   - The two new images have **no reviewed baseline**. This instance never writes a baseline, because
     a baseline is a person's review. So the gate will accept none of their unfixable base-image
     findings.
   - To unblock, the operator reviews `scan/out/timelike-vanilla/baseline.proposed.json` and
     `scan/out/timelike-bench-driver/baseline.proposed.json`, then commits them as
     `scan/baseline/<image>.json`.
   - Separately, the driver carries the docker CLI, a Go binary. Grype may report fixable Go-stdlib
     Highs in it, which block until `DOCKER_CLI_IMAGE` is bumped (RB10). Not measured.
3. **The environment emulation.** The tasks' outcomes are from host emulation, with git 2.43 (the image
   has 2.47.3) and timelike's ENV and gitconfig replayed. BASH_ENV and `/opt/timelike/bin` are not
   replayed, and no task uses them.
4. **API keys (the send's P4 instruction).** This cycle puts **no key into any container**: no live
   harness was built.
   - A fake-agent run refuses to start (exit 4) if a key-shaped name is found in any of three places:
     - the driver's own environment
     - either image's ENV
     - a task container's environment
   - `bench/run.sh` forwards no host environment, only a fixed `-e` list.
   - A future live run needs the key in the harness process only, which runs outside the environment
     under test. Nothing here decides how it gets there or who can read it; under P4 that is Adele's
     (feature 12).
5. **A remote `DOCKER_HOST` is refused** by `bench/run.sh`. The output bind mount would resolve on the
   remote daemon's host (RB7). The Docker lane's tcp/ssh support therefore does not extend to the bench
   tests.
6. **No value claim.** The fake agent's policy, the task selection and its recoveries were all written
   by timelike's builders (RB11). The expected shape is:
   - `git-commit-hook-rejects`: timelike loses
   - `git-inspect`: a tie
   - `git-rebase-continue` and `git-commit-hook-hangs`: timelike wins

   That is a prediction about the pipeline, not a finding.
7. **Workspace figures** (host lane, advisory):
   - 565 unit tests passed, 1 skipped
   - Python coverage 97% overall; `bench/` 96–100% per module
   - ruff, `mypy --strict` and shellcheck clean
   - `timelike-conform` passes over `bench/bin`
   - `make test-host` passed

**changed_other_features:** 001's code and image are untouched: `git diff master --name-only -- tools
image compose.yaml pins.env` is empty. Shared ground changed:
- `scan/scan.sh`: loops over three images. The agent's paths are unchanged, including
  `scan/out/verdict.json`. A missing bench image is reported, not failed.
- `tests/run.sh`: a `benchimg` step, and the e2e runner now mounts `bench/out/e2e` at its host path
  and gets `DEBIAN_IMAGE`, `REPO_HOST` and `BENCH_E2E_OUT`. e2e does not wait on `benchimg`, so 001's
  suite still runs if the bench images fail.
- `Makefile`: `bench` and `bench-images` targets; `bench` added to the lint paths and
  `SHELLCHECK_FILES`.
- `pyproject.toml`: bench files added to mypy and ruff.
- `tests/unit/conftest.py`: `bench/` added to `sys.path`.
- `README.md`: a "Speedup bench" section.

**process_failures_recorded**

1. **Research RB5's wrapper was wrong for dash.** `kill -KILL -- -$t` fails in dash with "Illegal
   number: -", so the group kill never ran, and a detached child held the call open until the
   backstop. T006's unit caught it. Changed to `kill -KILL -$t`, and RB5 and the contract were
   corrected.
2. **Research RB4 miscounted `git-commit-hook-rejects`** as 3 vanilla calls, where its own policy takes
   4. The T005 delegate caught it and kept it visible as a strict xfail rather than bend the test. The
   count was corrected to 4, and the policy was not changed to fit.
3. **Spec Assumption 5's example was wrong.** "git opening an editor with no terminal" is not a vanilla
   hang on this path; it fails fast. Research RB3 caught it, and the spec was corrected at plan time
   with a note.
4. **A catalog reason said "token-shaped"**, which put "token" in the report before the appendix
   (FR-9). The T016 delegate caught it; now "key-shaped".
5. **`timelike-bench --help` exited 2**, because a required positional was checked before `--help`.
   The conformance check (C1) caught it.
6. **The CLI tests did not forward `COVERAGE_PROCESS_START`**, so the tool's coverage was silently
   lost. Caught at T018.
7. **Plugin (specswarm 2.15.0):** the expanded text of `specify` again substituted argument words
   inside shell functions. Its `regenerate-identity` `fm()` and `source-send` `norm()` came out as
   `grep -E "^--from-send:"` and `sed … "--from-send"`. Neither ran on this path, because there was no
   `--regenerate` and `--from-send` needs no matching. The blocks were run as the installed
   `commands/specify.md` has them. This is the same defect reboot.md records for `ship` and `complete`.

**retired_prompts_seen:** none.

### Carried from feature 001 — watch items and leftovers (reported at the operator's request)

These are not criteria of this send. They are listed so that they stay in view.

**Watch items (the mentor tracks them):**

| Item | State after this cycle |
|---|---|
| `scan/baseline/timelike-agent.json` `review_by` **2026-12-27**; after that the scan blocks every merge until a person re-reviews it | Unchanged. This cycle did not touch the agent's baseline |
| Credential-class Criticals CVE-2026-11856, -19931, -8926, accepted for slice 0 only; re-reviewed at feature 12 (Adele) | Unchanged. Their premise still holds: this cycle gives the agent no credential, netrc or proxy, and puts no key into any container |
| Uncapped output can reach about 40 KB (200 lines × 200 columns), above common harness limits. Plan flagged it and did not rule; it is the operator's to raise | **Now answerable later.** Every trace records bytes emitted per call, bytes passed on, and whether the harness cut them (FR-6). Slice 0 builds no analysis and rules nothing |
| **New:** reviewed baselines for `timelike-vanilla` and `timelike-bench-driver` | Needed before 002 can merge (`not_verified` 2) |
| **New:** the Go-stdlib findings in the driver's docker CLI | Possible blocker at the first `make scan` (RB10) |

**Low leftovers from 001:**

| Item | State after this cycle |
|---|---|
| Docstrings for `timelike-conform`'s public functions (1 of 15) | **Still open.** Out of scope for this send; `tools/` was not touched |
| Measure start-up on the tools' own path (`/opt/timelike/python/bin/python3 -I` with the precompiled `agentio`, not uv's ephemeral environment) | **Still open.** Out of scope; needs the Docker lane. quality-standards C2 still carries the 88.1 ms figure with its conditions |

### Cycle 1 — Docker lane addendum (2026-09-29)

**Source:** `../bridge/history.md`, 2026-09-29T02:21:41Z. At the operator's request, the mentor ran
`make test`, `make scan` and `make bench` on the host at `8ce6173`, with a clean tree. The mentor's note
to this instance: *"timelike-bench --out X writes to X/<UTC stamp>/, but the test validates X/traces
and X/report.txt. Pick one layout, then record it in the cycle report."*

**What the lane showed at `8ce6173`:**

| Run | Result |
|---|---|
| `make test` | FAILED at e2e: 173/176. The unit step passed, and every other step passed |
| `speedup-bench.bats` | 3 tests failed: SC-1 trace, SC-1 hang, SC-2 report. 2 passed: the mismatched-stamp refusal and the planted-key refusal |
| `make scan` | agent PASS (77 baselined). `timelike-vanilla`: 76 blocking (8 Critical, 68 High). `timelike-bench-driver`: 48 High. Every finding has no stable fix, and every (id, package) pair is already in the agent's reviewed baseline. Vanilla carries the three credential-class Criticals (CVE-2026-11856, -19931, -8926). The driver has no fixable Go-stdlib finding, so RB10's risk did not materialise |
| `make bench` | exit 0. `bench/out/20260929T022053Z/report.txt`, with the fake-agent line first. Verdicts: git-inspect tie; git-rebase-continue and git-commit-hook-hangs timelike wins; git-commit-hook-rejects timelike loses. **This matches research RB4's prediction, and it is still a fake-agent result: it proves the pipeline, not the value** |

**The cause** (confirmed in `bench/out/e2e/run-8ce61739468f-32279/20260929T020334Z/`):
`bench/run.sh --out X` passed X to the driver only as `BENCH_OUT`. The tool treats that as a base and
writes a UTC-stamped run directory beneath it, while the e2e test validated `X/traces`. Both
refusal tests passed because they stop before writing anything. **The host lane missed it** because
`test_bench_cli` called the tool with `--out` directly, and nothing on the host ran `bench/run.sh`.

**The layout, picked and recorded** (T021; `contracts/bench-cli.md` § `run` and `bench/run.sh`):
- **`--out DIR` means exactly DIR:** `DIR/traces/<task>--<environment>.json` and `DIR/report.txt`.
  This holds for both `timelike-bench run` and `bench/run.sh`, which now passes `--out` on.
- **A DIR that already holds traces is refused** (exit 1), so two runs never mix in one report.
- **Without `--out`**, the run writes `$BENCH_OUT/<UTC stamp>/`. `make bench` writes
  `bench/out/<stamp>/`, so repeated runs never overwrite each other.

`speedup-bench.bats` already expected this layout and is unchanged. New host evidence:
- `tests/unit/test_bench_run_sh.py` checks the argv the wrapper hands the driver. Run against the old
  `run.sh`, its `--out` test fails, so it would have caught this.
- `test_bench_cli` now asserts that `--out` is exact and that a used directory is refused.

**criteria_reestablished, updated:**
- `02 · "One command runs a task in both a vanilla image and the timelike image"` — **unconfirmed**.
  It failed in the Docker lane at `8ce6173`, for the layout reason above. It needs a re-run at the fix
  commit.
- `02 · "The bench runs end to end in CI against a deterministic fake agent without any API key"` —
  **unconfirmed**. The same failure and the same re-run apply. Its planted-key refusal passed in the
  lane.
- `02 · "DEMO: the Adopting developer reads a bench report comparing a vanilla container with timelike on one task"` —
  **unconfirmed**. A fake-agent report now exists (`bench/out/20260929T022053Z/report.txt`), but
  nobody has read it yet. The report that will be shown is the fake-agent one.

**not_verified, updated:**
- Item 2 (scan) is now measured: **both bench images block**. Their findings are the agent baseline's
  own (id, package) pairs, but a baseline is one person's review of one image. So the fix is still a
  person reviewing `scan/out/timelike-vanilla/baseline.proposed.json` and
  `scan/out/timelike-bench-driver/baseline.proposed.json` into `scan/baseline/`. This instance does
  not copy the agent's review onto them.
- The watch item on the three credential-class Criticals now covers the vanilla image too. The
  vanilla image is a comparison baseline that never holds a credential, and the driver holds only the
  socket. The Criticals' premise is unchanged for both.

**process_failures_recorded (addendum):**
- **A wrapper was built without a test of the wrapper.** The contract defined `run.sh`'s `DIR`
  ambiguously ("default `bench/out`"), and the tool read `BENCH_OUT` as a base. Each was tested alone,
  never together, until the Docker lane. Fixed by one written rule and a host test of `run.sh`.

## Cycle 1 (continued) — bridge/sends/02-rev1-20260929-080659.md

**Written:** 2026-09-29. Not in dispatch mode. This send continues cycle 1 with the same prompt
revision (1) and slice (0). Built with `/specswarm:modify --from-send` on `002-speedup-bench`, from
`64270f7`. **Not merged**: the mentor holds the merge until the report explains itself.

**Status in one line:** the report now opens with the operator's statement of what the run is, and every
task explains its outcome in plain words. The host lane passes. The Docker lane at `64270f7` executed
SC-1 and SC-2; since then only the report's text, the checks' messages and their tests changed. SC-3
waits for the mentor's re-interview of the operator.

### Group A — cited from `.implement-complete`

Group A: not applicable — no marker on this path

### Group B — copied from the send

| Field | Value |
|---|---|
| source_send | bridge/sends/02-rev1-20260929-080659.md |
| source_prompt | plan/.discover/prompts/02-speedup-bench.md |
| prompt_revision | 1 |
| discovery_revision | 6 |
| slice | 0 |

### Group C — written by the code instance

**delegations:** empty. This instance did T022–T027 itself.

**criteria_reestablished**

- `02 · "One command runs a task in both a vanilla image and the timelike image"` — **executed
  [`tests/e2e/speedup-bench.bats`: "SC-1 one command runs a task in both a vanilla image and the
  timelike image and writes a per-run trace", and "SC-1 a hanging call ends within its limit and is
  recorded"]**.
  - Where: the Docker lane at `64270f7`, run by the mentor at the operator's request. It passed:
    `make test` e2e 176/176, all 5 bench tests, unit 575. Source: this send.
  - Changed since: the report text, the checks' failure messages (task version 2), the validator and
    their units. The runner, executor, images and wrapper are unchanged. The mentor re-runs the lane
    after this fix.
- `02 · "The bench runs end to end in CI against a deterministic fake agent without any API key"` —
  **executed [`speedup-bench.bats`: "SC-2 the bench runs end to end in CI…" and "SC-2 a planted API key
  refuses the run before any trace is written"]**, same run, same caveat. The validator's report check
  is now stricter:
  - the first line must equal the operator's text whole
  - every task section must carry `Tests:`, `Verdict:` and a "What happened" for both arms

  The re-run will exercise both.
- `02 · "DEMO: the Adopting developer reads a bench report comparing a vanilla container with timelike on one task"` —
  **unconfirmed**.
  - **Shown:** a fake-agent report, `bench/out/20260929T022053Z/report.txt`, from `8ce6173`. It was
    read by the operator, by interview with the mentor, and misled on 2 of 5 questions: it was taken
    as evidence, and the one loss was read backwards (this send).
  - **Now:** the new layout, previewed from those same traces at
    `bench/out/20260929T022053Z-preview/report.txt`. The report the operator read is left untouched
    beside it.
  - **What remains:** a fresh `make bench` report at the fix commit carries the checks' new reasons.
    It stays unconfirmed until the mentor re-interviews the operator.

**reconcile_mode:** full. The whole send was checked against the spec: the prompt, slice and criteria
are unchanged. Its three demands were done as F001–F003 in `modify.md`, and recorded in the spec as
FR-9 (amended) and FR-9a (added). Provenance is modify row 4: revision 1 is already in
`audited_against [1]`, so nothing is appended. `audit-log.md` records a `none` row.

**Where the first line lives now** (the send asked for this to be stated):

| Place | Form |
|---|---|
| `bench/benchlib/report.py` `FAKE_LINE` | The operator's text, verbatim: line 1 of every report touched by a fake-agent run |
| `bench/bin/timelike-bench` `FAKE_SCOPE` | Shortened for the rule-12 header: `[FAKE-AGENT BENCH PIPELINE DEMO RUN -- not a test of timelike]` |
| `tests/e2e/fixtures/validate_bench.py` `FAKE_FIRST` | Verbatim, and compared whole |
| `tests/e2e/speedup-bench.bats` | The header scope, via `grep -F` |
| Units: `test_bench_report`, `test_bench_cli`, `test_validate_bench` | Verbatim / scope |
| README, `contracts/bench-cli.md`, quickstart, spec FR-9 and Scenario 3 | Verbatim, or quoted |

**What each task section now carries** (FR-9a; `contracts/bench-cli.md`, Report layout):
- `Tests:` — the capability and what differs between the images for this task. This is a fact about
  the environments, from the catalog's new `difference` field.
- `Verdict:` in words, naming what decided it. When the endings differ it quotes the losing arm's
  reason.
- The metrics table. The ending cell now shows the kind alone, and the failure row reads "failed
  commands (hung included)".
- For each arm, `What happened in <arm>:` — each call with its exit and the first line of stderr, or
  "hung: killed at the N s limit"; then `Ended:` with the reason. A failing check now states its own
  reason (F003).
- A `Why:` note, written with the task and printed **only when that arm ended the way the note
  describes** (keyed `environment:ending`). For `git-commit-hook-rejects`, timelike's note reads:
  "Timelike's default skipped the repository's pre-commit hook, so the commit went through carrying
  the TODO line and broke the policy the goal names."

**not_verified**

1. **SC-3.** Nobody has read the new layout. The acceptance test is a person, the operator
   re-interviewed by the mentor.
2. **The Docker lane at the fix commit.** Last run at `64270f7`, which passed. The new first line, the
   stricter validator and the checks' messages have not run in an image.
3. **Hardening noted by the mentor, not required, not done.** The driver runs without `--cap-drop ALL`
   or `no-new-privileges`, and keeps Debian's setuid binaries. It is carried as a follow-up, not
   silently dropped.
4. **API keys:** unchanged. This cycle puts no key into any container, and no live harness exists.
5. **Host lane:** 592 passed, 1 skipped (under coverage). Coverage is 97% overall, and `bench/` 96–100%
   per module, with `report.py` at 100%. ruff, `mypy --strict` and shellcheck are clean.

**changed_other_features:** none. Only `bench/`, the bench's tests, README and feature 002's artifacts
changed.

**process_failures_recorded**

1. **The first report was written for a test, not for a reader.** Every automated check passed a
   report that a person misread twice. The only honest test for FR-9a is a person, which is why SC-3
   stays unconfirmed until the re-interview. The validator's new presence checks guard the shape, not
   the understanding.
2. **tasks.md T026 said to re-render the operator's report in place.** Done as written, that would have
   overwritten the artifact the D2 reading was checked against. The preview was written beside it
   instead (decisions T026).
3. **A check's own reason could be hidden behind git's stderr.** A unit caught it. Checks now send
   their commands' stderr to `/dev/null`, and print only their reason.

**retired_prompts_seen:** `bridge/sends/02-rev1-20260929-000641.md` is superseded by this send, as
cycle 1's instruction, and was continued, not abandoned.

### Carried watch items and leftovers (updated)

| Item | State |
|---|---|
| `scan/baseline/timelike-agent.json` `review_by` 2026-12-27 | Unchanged |
| **New baselines** `timelike-vanilla` and `timelike-bench-driver` (`64270f7`, reviewed by a person 2026-09-29), `review_by` **2026-12-27** | `make scan` PASS on all three images at `64270f7`. Vanilla's 8 libcurl Criticals must be re-reviewed if a bench task container gets a network or credentials, and at feature 12. Today every task container runs `--network none` with no credential |
| Credential-class Criticals (CVE-2026-11856, -19931, -8926) at feature 12 | Now also in vanilla (baseline above). Premise unchanged |
| Uncapped output about 40 KB; plan's byte-cap question | Traces record bytes per call and whether the harness cut them. No analysis yet |
| Driver hardening (`--cap-drop ALL`, `no-new-privileges`, setuid binaries) | **New**, noted by the mentor, not required. Open |
| Low leftovers from 001: `timelike-conform` docstrings (1 of 15); start-up on the tools' own path | Still open, out of scope |

### Cycle 1 — sign-off addendum (2026-09-29)

**Source:** `../bridge/history.md`, 2026-09-29T08:53:35Z (host-run) and 09:22:04Z (observation and
sign-off). This section records what others observed; this instance ran none of it.

**The Docker lane at `57a0942`** (the fix for send `…-080659`), run by the mentor at the operator's
request, with specswarm 2.17.0 installed:
- **`make test` PASSED:** e2e 176/176, including all 5 bench tests under the stricter validator (the
  whole first line, and every task section explaining itself). Unit 593.
- **`make scan` PASS** on all three images.
- **`make bench` exit 0:** `bench/out/20260929T085248Z/report.txt`.

**criteria_reestablished (final for slice 0):**
- `02 · "One command runs a task in both a vanilla image and the timelike image"` — **executed
  [`tests/e2e/speedup-bench.bats` "SC-1 one command runs a task in both a vanilla image and the
  timelike image and writes a per-run trace", "SC-1 a hanging call ends within its limit and is
  recorded"]**, Docker lane at `57a0942`.
- `02 · "The bench runs end to end in CI against a deterministic fake agent without any API key"` —
  **executed [`speedup-bench.bats` "SC-2 the bench runs end to end in CI…", "SC-2 a planted API key
  refuses the run before any trace is written"]**, Docker lane at `57a0942`.
- `02 · "DEMO: the Adopting developer reads a bench report comparing a vanilla container with timelike on one task"` —
  **observed by the operator (ironik.xyz)**, by re-interview with the mentor on
  `bench/out/20260929T085248Z/report.txt`.
  - **Which report:** the fake-agent report from `make bench` at `57a0942`. No live run exists.
  - **Fresh questions**, because the operator already knew the hook-rejects answer from the first
    interview. All 5 were answered correctly:
    1. the run is a test of the bench itself
    2. rebase-continue: vanilla had no editor, so the agent retried with `-c core.editor=true`
    3. `core.hooksPath=/dev/null` decides both hook tasks: a "dubious win for speed, not
       reliability" in hangs (vanilla also ended on `--no-verify`), and a policy violation in rejects
    4. git-inspect is the expected-tie control
    5. no adoption conclusion can be drawn from a fake-agent run, and the bench is robust
  - The first reading, on `bench/out/20260929T022053Z/report.txt` at `8ce6173`, misled on 2 of 5. It is
    kept, unchanged, as the evidence that FR-9a answered.

**Operator's reading worth carrying:** the hook-hangs "win" is a speed win and a reliability question.
Both arms ended by skipping the hook: vanilla through `--no-verify`, timelike by default. That is data
for slice 1's failure categories and for how wins are worded in the report. It is not a defect in
slice 0.

**Mentor sign-off:** merge 002 slice 0 via `/specswarm:ship` (the score is informational;
`enforce_gates: false`).

### Cycle 1 — merge addendum (2026-09-29)

**Merged** `002-speedup-bench` into `master` at `47cbc26` (no-ff), after the mentor's sign-off
(`../bridge/history.md` 09:22:04Z) and the operator's instruction. The tree equals the branch tip
`f350671`. There was no push, because there is no remote. The branch is kept.

**The ship gate:**
- `/specswarm:analyze-quality` wrote `quality-report.json` (`overall_state: scored`, 90%, the average
  of 8 modules, including three new `bench/` ones). The full report is
  `.specswarm/quality-analysis-20260929-*.md`.
- The score passed against `min_quality_score: 0`, and is informational under `enforce_gates: false`.
- **The merge bar** (quality-standards § Quality Gates) was met at `57a0942`: the Docker lane passed,
  the scan passed on three images, coverage is 97%, SC-1 and SC-2 were executed, and SC-3 was
  observed.
- **Since `57a0942`, only documentation and ship artifacts changed:** the cycle report, the quality
  report and the analysis. `git diff --name-only 57a0942 f350671` lists only `.specswarm/`.

**process_failures_recorded (addendum):**
- The ship and analyze-quality text expanded from specswarm 2.15.0's cache path, although the mentor
  reports 2.17.0 installed; 2.16.1–2.18.0 are all in the plugin cache. The 2.15.0 logic was followed:
  `lib/quality-scale.sh`, `quality-report.json`, then the gate.
- `/specswarm:complete` was not run, because its prompts need stdin and its expanded text garbles
  shell-function arguments (reboot.md). The merge was done by hand, exactly as for 001.

### Cycle 1 — quality-score addendum (2026-09-29, after merge)

**The ship score was a judgment, not a measurement.** After specswarm was updated to 2.18.0,
`/specswarm:analyze-quality` was re-run on `master` (`.specswarm/quality-analysis-20260929-093335.md`). It
detects Python and reports **`Overall Quality: unknown`**, because every rubric check is a
JavaScript/TypeScript grep.

The **90%** recorded at ship (`quality-report.json`, the merge addendum above) was computed under
2.15.0 with component values this instance **filled in by judgment**. It was not a measurement. It was
informational (`enforce_gates: false`) and decided nothing. The merge bar (Docker lane, scan, coverage
97%, SC-3 observed) is unaffected.

`quality-report.json` is left as shipped. This note is the correction.

## Cycle 2 — bridge/sends/02-rev8-20261008-095251.md

**Written:** 2026-10-08T10:01:46Z (read from the clock). Not in dispatch mode. Built with `/specswarm:modify 002 --from-send
bridge/sends/02-rev8-20261008-095251.md`, then `/specswarm:plan`, `/specswarm:tasks` and `/specswarm:implement`,
on `modify/002-rev8` from `master` at `c79facc` (= `public/main`). **Pushed nothing; not merged.**

**specswarm version (lore specswarm Q002):** this session ran **4.0.1-botbaubble.2.37.0**. Every expanded command
named `PLUGIN_DIR=…/4.0.1-botbaubble.2.37.0`, and the session's pid is in that version's `.in_use` (2.36.0's is
empty). This is the first `modify` under 2.37.0; see process_failures_recorded for what it showed.

**Status in one line:** record only, `.specswarm/features/002-speedup-bench/` only. Revision 8 added a constraint and a
slice-1 criterion and amended nothing; the constraint is copied into the spec, declared, with slice 0's four unmet
places named; `audited_against` gains 8.

### Group A — cited from `.implement-complete`

Group A: not applicable — no marker on this path

### Group B — copied from the send

| Field | Value |
|---|---|
| source_send | bridge/sends/02-rev8-20261008-095251.md |
| source_prompt | plan/.discover/prompts/02-speedup-bench.md |
| prompt_revision | 8 |
| discovery_revision | 13 |
| slice | 0 of [0, 1, 2] (merged) (no new slice; an audit of what is merged) |

### Group C — written by the code instance

**delegations:** `[]`.

**criteria_reestablished.** Slice 0's three criteria. This cycle changed only files under
`.specswarm/features/002-speedup-bench/` (`git diff master HEAD -- . ':!.specswarm/features/002-speedup-bench'` is
empty), and `master`'s tree at `c79facc` is `725b7a1f…`, identical to `10ddd3a`'s. So, as the send directs, the
two Automated criteria cite **the mentor's lane readme-c at `10ddd3a`, a lane on an identical tree** (history
2026-10-08T08:28:00Z: `make test` PASSED, e2e 537/537; log `bridge/.make-test-readme-c.log`, TAP 393, 394, 396, 397).
No lane ran for this cycle.
- `02 · "One command runs a task in both a vanilla image and the timelike image"` — **executed [mentor's lane readme-c
  at 10ddd3a: `tests/e2e/speedup-bench.bats` "SC-1 one command runs a task in both a vanilla image and the timelike
  image and writes a per-run trace" (ok 393), "SC-1 a hanging call ends within its limit and is recorded" (ok 394)]**
  (cited, not re-run; identical tree)
- `02 · "The bench runs end to end in CI against a deterministic fake agent without any API key"` — **executed [mentor's
  lane readme-c at 10ddd3a: `speedup-bench.bats` "SC-2 the bench runs end to end in CI against a deterministic fake
  agent without any API key" (ok 396), "SC-2 a planted API key refuses the run before any trace is written" (ok 397)]**
  (cited, not re-run; identical tree)
- `02 · "DEMO: the Adopting developer reads a bench report comparing a vanilla container with timelike on one task"` —
  **observed by the operator**, the mode the Cycle 1 sign-off addendum recorded (re-interview with the mentor on
  `bench/out/20260929T085248Z/report.txt`, a fake-agent report). This cycle observed nothing new.

Each citation matches exactly one line of the send (`grep -cF` = 1 for all three). The slice-1 criterion revision 8
added is not cited: it is not in scope for slice 0.

**reconcile_mode:** `scoped`. `audited_against` is now `[1, 8]` (T030, computed by the installed `audit-append`
block: `MODE=scoped`, `OUT_OF_SCOPE` empty, `REMOVALS_VISIBLE=yes` → `MODE_USED=scoped`, `APPENDED=8`, no note).
- **What revision 8 changed (lore P004: what was compared).** The prompt bodies of the archived sends
  `02-rev1-20260929-000641`, `02-rev1-20260929-080659` and this one were diffed from `# Speedup bench` to the end:
  the two revision-1 sends are identical, and this one adds three lines (the revision note, the constraint, the
  slice-1 criterion) and removes or rewords none. Revisions 2–7 did not change prompt 02.
- **Not SUPERSEDED; not regenerated.** Body lines read for a verdict order, a tiebreak or how a hung call counts
  (numbers as before T028): `spec.md:20` (Overview), `:75–77` (Scenario 3), FR-9 `:160–166`, FR-9a `:171–176`,
  `:216–218` (Success Criteria preface), `:258–264` (Out of Scope). None states an order, so none is false. FR-9's
  "failed commands (non-zero exits)" already counts a hung call as one failed command, which revision 8 confirms.
- **Why `scoped`, and the one place I read the rule differently from the command (FLAGGED in T030, medium).** The
  command appends nothing for a revision whose added criteria a cycle leaves unaddressed. Passing revision 8 as
  out of scope makes the block return `none`, verified. Revision 8's slice-1 criterion is out of slice 0 by the
  spec's own slice rule and by the mentor's 3c, and its constraint is now in the body. So 8 is appended in the
  sense `audited_against` carries on the mentor's side, *checked and needs no regeneration*, as the send instructs.
  It is **not** a claim that slice 0's code meets revision 8, which it does not (not_verified). `full` was not used:
  it would also append 2–7.

**The send's items:**
1. **The constraint, declared** (T028, `8096f77`): under § Reporting after FR-9a, verbatim and marked *(Added revision
   8)*, with a sub-bullet naming the four unmet places and plan's ruling (b). The slice-1 criterion is not copied: the
   spec keeps no later-slice criterion list.
2. **T016 marked superseded** (T029, `e284679`): an annotation under its fourth ASSUMED line, which is kept as written.
3. **`report.py` and `data-model.md` not edited.** I agree the change can wait for 02 s1: every slice-0 report is
   labelled a fake-agent run (FR-9), the README makes no bench claim, and slice 1 brings the live runs where the
   order first decides something real.

**not_verified**
- **Slice 0's code does not meet revision 8's constraint**, by plan's ruling (b), carried to 02 s1. All four places
  were read, none edited:
  - `bench/benchlib/report.py:119`: the third tiebreak is `_sign(v.nonzero_exits + v.hangs, t.nonzero_exits + t.hangs)`.
    Hangs are not compared on their own before failed commands, and a hung call counts twice.
  - `bench/benchlib/report.py:227`: the verdict sentence quotes that sum as "failed or hung commands", which is not
    a count in the report's table.
  - `data-model.md:125` (§ Comparison and report, step 3): "compare `nonzero_exits + hangs` (fewer wins)".
  - `decisions.md` T016: the origin, now annotated.
- **No test ran in this cycle**, on the host or in the image. The two Automated criteria are cited from lane
  readme-c, not re-executed. The citation holds only because nothing outside this feature's directory changed.

**changed_other_features:** none. Only `.specswarm/features/002-speedup-bench/` changed. Implement step 10j's
`.specswarm/metrics.json` entry was **not** written, because the send confines this cycle to the feature directory;
step 10's output is recorded below instead.

**process_failures_recorded**
1. **A commit before its deny-list check.** The modify-step commit `4f634c6` was made before the publish deny-list
   ran. It ran straight after over the branch's objects, path names and message (P1–P7 0) and the tree (pass,
   452 files). Every later commit ran the check first.
2. **A line-number slip, corrected in the cycle.** T030's audit-log row cited spec line numbers measured before
   T028 inserted 14 lines. Fixed in `248d090`, which states the offset. The row was not otherwise rewritten.
3. **Plugin observations under 2.37.0, for the mentor to relay** (first `modify` under it):
   - **D105 holds in the field.** The expanded `implement` text sources `lib/tally.sh` for `scope-tally` and
     `decision-tally` and carries no awk record sigil. Both functions ran with **0 bytes on stderr**, and
     `decision_tally` prints the new `flagged_delegate` and `assumed_delegate` counts (D107).
   - **Cosmetic:** `scope_tally` and `decision_tally` print no trailing newline, so two consecutive calls run
     together on one line ("…other_out=0decisions: …"). Inside `$(…)`, as the blocks use them, this is harmless.
   - **`modify` row 7 is now mechanised end to end.** The `provenance-inputs` block (D89) sets every input
     `provenance-row` branches on, and it gave row 7 (`N=8`, `prompt_revision 1`, `audited_against [1]`) with
     nothing read by hand. This closes the gap Cycle 7 of 001 reported.
   - **`fnum_resolve`** resolved `modify/002-rev8` to 002 in plan, tasks and implement, writing nothing to stderr.
   - **Workaround, as before:** the command blocks were run from scratch scripts holding the installed blocks'
     logic, rather than as expanded text, because the expansion substitutes the command's arguments into
     `$ARGUMENTS` and positional sigils. No block needed a logic change.
   - **The `audit-append` rule versus the send:** see reconcile_mode. The command has no mode for "revision N's
     own change is recorded but carried to a later slice". Whether it should is the mentor's question to relay.

**retired_prompts_seen:** none.

### Implement step 10 — quality validation (specswarm 2.37.0 blocks), as the library reported it

```
== b detect
{"frameworks": ["pytest"], "primary": "pytest", "count": 1}   rc=0
== c run_tests
rc=2
/usr/bin/python3: No module named pytest
run_tests: pytest is declared by this project but not installed here
== parse
total=unknown passed=unknown failed=unknown skipped=unknown
== d coverage
detect rc=0; run_coverage rc=1 out=unknown
== e browser
browser test framework: none (declared in package.json; not a check that it runs)
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
block_merge_on_failure: false (quality-standards.md:295)
```

The gate is **UNKNOWN**. With `block_merge_on_failure: false` and `min_quality_score: 0`, it warns and does not halt.
No component was filled in by hand. Step 10e in 2.37.0 reads `package.json` (D88), so the missing
`lib/quality-gates.sh` error that 001's Cycle 7 recorded no longer occurs. 2.37.0 needed no rewording of reasons:
all four `unavailable` reasons were attributed.

**Implement step 9b: decision log** (plugin `scope_tally` and `decision_tally` over the whole of 002's `tasks.md` and `decisions.md`, all cycles, before T031's own records):

```
scope: planned=31 recorded=30 unplanned=0 unrecorded=1 in=25 out=0 none=5 unknown=0 flagged=27 flagged_out=0 other=3 other_out=0
decisions: sections=30 flagged_sections=27 non_flagged_sections=3 sections_without_absent=0 flagged=45 assumed=42 deferred=2 absent=37 inherited=28 low_confidence=0 flagged_low_confidence=0 flagged_delegate=0 assumed_delegate=0
```

Cycle 2 alone (T028–T030 at that point): 3 sections, 2 FLAGGED entries (T028's placement; T030's mode), 0
low-confidence. `SCOPE:` none 3.

## Cycle 3 — bridge/sends/02-rev8-20261009-043302.md

**Written:** 2026-10-09T04:42:14Z (read from the clock). Not in dispatch mode. Built with `/specswarm:modify 002 --from-send
bridge/sends/02-rev8-20261009-043302.md`, then plan, tasks and `/specswarm:implement` (T032, T033), on
`modify/002-rev8-carried` from `master` at `ec71f3d` (= `public/main`). **Nothing pushed; not merged.**

**specswarm version (lore specswarm Q002):** this session ran **4.0.1-botbaubble.2.40.0**.
- The plugins were updated during the operator's pause, and the session resumed after it. Both commands, on
  expansion, set `PLUGIN_DIR=…/4.0.1-botbaubble.2.40.0`.
- The `audit-append` block accepted `MODE=carried`: it returned `MODE_USED=carried`, not `none`, and logged no
  "is not one of" note.
- The `.in_use` files of both 2.37.0 and 2.40.0 are empty this time, so that signal (which Cycle 2 cited) reads
  nothing.

**Status in one line:** records only. Revision 8 is re-recorded as **`carried` to 02 slice 1**, one new
`audit-log.md` row. `audited_against` stays `[1, 8]`, and `spec.md` is unchanged.

### Group A — cited from `.implement-complete`

Group A: not applicable — no marker on this path

### Group B — copied from the send

| Field | Value |
|---|---|
| source_send | bridge/sends/02-rev8-20261009-043302.md |
| source_prompt | plan/.discover/prompts/02-speedup-bench.md |
| prompt_revision | 8 |
| discovery_revision | 15 |
| slice | 0 of [0, 1, 2] (merged) (no new slice; a record of what is merged) |

### Group C — written by the code instance

**delegations:** `[]`.

**criteria_reestablished.** Slice 0's three criteria. This cycle changed only
`.specswarm/features/002-speedup-bench/` and `reboot.md`. The lane's tree differs from `master`'s only in four
documentation files: `git diff --name-only 3eba335 ec71f3d` lists 007's `cycle-report.md`,
`.specswarm/maintenance/readme/cycle-report.md`, `README.md` (the closing section, outside the reference markers)
and `reboot.md`, none of them code or tests. So the two Automated criteria cite **the mentor's lane 007s1-c at
`3eba335`** (history 2026-10-09T03:16:00Z: `make test` exit 0, e2e 576/576 ok; log `bridge/.make-test-007s1-c.log`).
No lane ran for this cycle.
- `02 · "One command runs a task in both a vanilla image and the timelike image"` — **executed [mentor's lane 007s1-c
  at 3eba335: `tests/e2e/speedup-bench.bats` "SC-1 one command runs a task in both a vanilla image and the timelike
  image and writes a per-run trace" (ok 432), "SC-1 a hanging call ends within its limit and is recorded" (ok 433)]**
  (cited, not re-run)
- `02 · "The bench runs end to end in CI against a deterministic fake agent without any API key"` — **executed [mentor's
  lane 007s1-c at 3eba335: `speedup-bench.bats` "SC-2 the bench runs end to end in CI against a deterministic fake
  agent without any API key" (ok 435), "SC-2 a planted API key refuses the run before any trace is written" (ok 436)]**
  (cited, not re-run)
- `02 · "DEMO: the Adopting developer reads a bench report comparing a vanilla container with timelike on one task"` —
  **observed by the operator**, the mode Cycle 2 recorded (from the Cycle 1 sign-off addendum: the re-interview on
  `bench/out/20260929T085248Z/report.txt`). Nothing new was observed this cycle.

Each citation matches exactly one line of this send (`grep -cF` = 1 for all three). The slice-1 criterion revision 8 added (`Two arms that end the same way…`) is not cited: it is not in scope for slice 0,
and it is the work `carried` points at.

**reconcile_mode:** `carried`, to **02 slice 1**. `audited_against` is unchanged at `[1, 8]`.
- **The block's own output (lore P004).** The installed 2.40.0 `audit-append` block took `PROMPT_REV=1`,
  `AUDITED=[1, 8]`, `N=8`, `MODE=carried`, `OUT_OF_SCOPE` empty, `CARRIES_TO="02 slice 1"`. It also took
  `UNVERIFIED` empty and `REMOVALS_VISIBLE=yes`, which carried does not read. It returned `MODE_USED=carried`,
  `APPENDED` empty, `NEW_AUDITED=[1, 8]` and `AUDIT_NOTE=02 slice 1`, which are the values the send expected. The
  empty append is the expected no-op, because 8 was already listed. It is not a failure.
- **Library row 4.** Modify's provenance row is 4 (`N=8` is already in `audited_against`), and on that row the library
  alone skips Step 9. The block ran on the send's instruction. The audit-log row and T032's FLAGGED entry both say so.
- **Basis:** plan's ruling (b) in `bridge/feedback/02-20260930-060406-hang-counted-twice.md`. Revision 8 was examined,
  and the code change rides 02 slice 1. The new row supersedes Cycle 2's `scoped` for revision 8, and Cycle 2's row
  is kept as written.
- **What was compared.** This send's prompt body is byte-identical to Cycle 2's send's (`diff` from `# Speedup bench`
  to the end is empty). Prompt 02 is still at revision 8.

**not_verified**
- **Slice 0's code does not meet revision 8**, and that is why `carried` is true. All four places were re-read on
  `ec71f3d`, and none was edited:
  - `bench/benchlib/report.py:119`: the summed tiebreak `_sign(v.nonzero_exits + v.hangs, t.nonzero_exits + t.hangs)`.
  - `bench/benchlib/report.py:227`: the same sum, quoted at `:231` as "failed or hung commands". Cycle 2 cited `:227`
    only, where the sum is computed; the phrase is four lines down.
  - `data-model.md:125`, step 3.
  - `decisions.md` T016, annotated in Cycle 2.
- **No test ran in this cycle**, on the host or in the image. The two Automated criteria are cited from lane 007s1-c,
  not re-executed. `bench/` changed since Cycle 2's lane only in `bench/vanilla/Dockerfile` (007 slice 1's runtimes
  parity), and lane 007s1-c ran the bench cells over it.
- **Discovery revisions 14 and 15.** Revision 14's vanilla-image parity rule (RB1, P6) touches the bench's vanilla
  arm. It was built and tested in 007 slice 1 (e2e P6 cells 469 and 470 in lane 007s1-c), not here, and nothing in it
  changes a criterion 002 carries. I found nothing in revision 15 (bundled-library fixes) that bears on the bench.

**changed_other_features:** none. Only `.specswarm/features/002-speedup-bench/` and `reboot.md` changed. Implement
step 10j's `.specswarm/metrics.json` entry was **not** written, as in Cycle 2, because the send confines this cycle
to the feature's directory; step 10's output is below instead.

**process_failures_recorded:** none this cycle.

**retired_prompts_seen:** Cycle 2's send `02-rev8-20261008-095251` stands as written. This send re-records its mode
and does not replace its content.

### Implement step 10 — quality validation (specswarm 2.40.0 blocks), as the library reported it

- The detector found `pytest` (`{"frameworks": ["pytest"], "primary": "pytest", "count": 1}`).
  - `run_tests` rc=2: "pytest is declared by this project but not installed here".
  - `run_coverage` rc=1, printing `unknown`.
  - Neither web project nor browser suite was detected.
- `Quality Score: unknown — no component could be measured, so there is no score to compare`.
- **The exclusions, by `unmeasured-explains-itself`:** 2 attributed to this install (bundle size, visual alignment),
  2 to this machine (unit tests, coverage), 2 not applicable (integration, browser), and 0 unattributed.
  - Coverage's reason is written "on this machine" as in 007's Cycle 4. The library's own `unknown` names neither.
- The gate is **UNKNOWN**: warned, not halted (`min_quality_score: 0`, `block_merge_on_failure: false`).

**Implement step 9b: decision log** (`scope_tally` and `decision_tally` from 2.40.0's `lib/tally.sh`, over all of 002,
before T033's own records):

```
scope: planned=33 recorded=32 unplanned=0 unrecorded=1 in=25 out=0 none=7 unknown=0 flagged=29 flagged_out=0 other=3 other_out=0 unattributed_scope=0
decisions: sections=32 flagged_sections=29 non_flagged_sections=3 sections_without_absent=0 flagged=47 assumed=44 deferred=2 absent=39 inherited=30 low_confidence=0 flagged_low_confidence=0 flagged_delegate=0 assumed_delegate=0 unattributed=0 deferred_delegate=0 absent_delegate=0 inherited_delegate=0
```

The `unrecorded=1` is T033 itself, recorded right after this section. There are no low-confidence decisions.

**Git workflow (implement step 11):** option 2, stay on `modify/002-rev8-carried`. The merge is `--no-ff` after the
mentor's sign-off, and it rides the next germane push and its tag.

## Cycle 4 — bridge/sends/02-rev8-20261013-064725.md

**Written:** 2026-10-13T08:43:56Z (read from the clock). Not in dispatch mode (attended). Built with `/specswarm:modify 002 --from-send
bridge/sends/02-rev8-20261013-064725.md`, then plan, tasks and `/specswarm:implement` (T034–T052), on `modify/002-slice-1`
from `master` at `8dbddc7` (= `public/main`, `v0.19.0`). **Nothing pushed; not merged.**

**specswarm version (lore specswarm Q002):** this session ran **4.0.1-botbaubble.2.44.0** (`claude plugin list`, and the
`PLUGIN_DIR` every command expanded).

**Status in one line:** slice 1 built and unit-tested on the host. Nothing has run in Docker yet. Every criterion is
`unconfirmed` until the mentor's lane, and D11 until the live run and the operator's reading. FOR-MENTOR Item 25 is
open, and nothing built waits on it.

### Group A — cited from `.implement-complete`

Group A: not applicable — no marker on this path

### Group B — copied from the send

| Field | Value |
|---|---|
| source_send | bridge/sends/02-rev8-20261013-064725.md |
| source_prompt | plan/.discover/prompts/02-speedup-bench.md |
| prompt_revision | 8 |
| discovery_revision | 15 |
| slice | 1 of [0, 1, 2] (intensity: natural) |

### Group C — written by the code instance

**delegations:** `[]`. No subagent wrote code or documents. Every task was done in this session.

**criteria_reestablished.** Each is cited by text that matches exactly one criterion line (`- [ ]`) of the send
(`grep -F` over the send, counting `- [ ]` lines: 1 each). Four of the texts also appear once in the send's "In scope"
list, which is not a criterion line. **No mode below is `executed`.** A host-lane pass never counts as an
acceptance-criterion pass (README, "Two verification lanes"), and no lane has run on this branch. The cells that will
execute each one are named.
- `02 · "One command runs a task in both a vanilla image and the timelike image"` _(slice 0)_ — **unconfirmed**
  (lane: `tests/e2e/speedup-bench.bats` "SC-1 one command runs…", "SC-1 a hanging call…", "SC-1 a stamp that does not
  match…"; schema 2, three arms, five tasks)
- `02 · "The bench runs end to end in CI against a deterministic fake agent without any API key"` _(slice 0)_ —
  **unconfirmed** (lane: `speedup-bench.bats` "SC-2 the bench runs end to end…", "SC-2 a planted API key…", "SC-2 a set
  BENCH_KEY_FILE refuses…")
- `02 · "Each run is labelled told or not-told, and the report counts timelike tool invocations per arm"` _(slice 1)_ —
  **unconfirmed** (lane: `speedup-bench.bats` "SC-4 each run is labelled…"; the validator's `adoption` recount, and the
  same under both live harnesses in the SC-5 file)
- `02 · "The same task catalog runs under two harnesses and the report shows results per harness"` _(slice 1)_ —
  **unconfirmed** (lane: `the-same-task-catalog-runs-under-two-harnesses-and-the-report-shows-results-per-harness.bats`,
  five cells: OpenCode and Codex CLI against the model stand-in, `--standin`, no key)
- `02 · "Two arms that end the same way in the same number of turns are ranked by hangs, then by failed commands"`
  _(slice 1; revision 8)_ — **unconfirmed** (lane: `speedup-bench.bats` "SC-6 …", the validator's independent
  `verdicts` recomputation; host units: `test_bench_report.py` rows differing in one column at a time, and the pair on
  which slice 0's summed tiebreak and revision 8 disagree)
- `02 · "Failed commands are grouped into categories including command not found"` _(slice 1)_ — **unconfirmed**
  (lane: `failed-commands-are-grouped-into-categories-…-network-denial.bats`, `categories --probe` in both images:
  one real failing command per category, memory kill under a 64 MiB limit with the kernel's OOM count; and
  `speedup-bench.bats` "SC-7 …")
- `02 · "DEMO: the Adopting developer compares timelike tool adoption between a told arm and a not-told arm"` _(slice 1;
  D11, Manual)_ — **unconfirmed**. The mentor's live run, then the operator's reading.

Slice 0's D2 is not re-cited (the send). Slice 2's criteria are not built and not cited.

**reconcile_mode:** `scoped`. This cycle examined revision 8's change and did its code work: the verdict order, each call
counted once per row, the sentence quoting only table counts (T034). It checked the spec against the slice-1 criteria it
built, revision 8's among them, and not against slice 2's. The installed `audit-append` block ran with `LOG_ONLY=yes`,
because this is modify row 4 and 8 was already listed. It took `MODE=scoped`, `PROMPT_REV=1`, `AUDITED=[1, 8]`, `N=8`,
`REMOVALS_VISIBLE=yes`, with `OUT_OF_SCOPE` and `UNVERIFIED` empty, and returned `MODE_USED=scoped`, `APPENDED` empty and
`NEW_AUDITED=[1, 8]`. The `audit-log.md` row supersedes Cycle 3's `carried` mode for revision 8, and both earlier rows
are kept. `spec.md`'s `audited_against` is unchanged.

**What was built** (T034–T052; `tasks.md` Phase 11, `decisions.md` § Cycle 4):
- **Arms** (FR-17 to FR-20). The arms are vanilla, timelike not told, and timelike told. The told arm runs 007's own
  `timelike announce --install` after setup, because task containers start with `--entrypoint sleep`, which skips the
  entrypoint that runs it in the product.
- **Adoption** is counted from the commands' words. Calls through the shims or guards are counted apart and are never
  adoption.
- **Two live harnesses**, run inside the task container from a read-only harness volume:
  - OpenCode 1.19.0;
  - Codex CLI 0.162.1, chosen on OpenRouter's own guides and runs against a stand-in. Claude Code is excluded
    (research RB12).
- **The relay** in the driver is a harness's only road to the model. It counts turns, reads spend from each answer's
  `usage.cost`, enforces the caps, and records no header.
- **The key** is read from a 0600 file, passed to the harness exec only, and kept out of every artifact by the write
  gate.
- **Caps and the plan.** The plan is printed before any request; `--dry-run` prints only the plan.
- **A `stopped` ending** with a named cause, never a loss.
- **Failure categories**, and the probe.
- **Parsers**, tested on transcripts the harnesses wrote themselves.
- **Trace schema 2.**
- **The report:** per harness, three arms, two verdicts, adoption and category tables, and spend only in the appendix.
- **A fifth task**, `python-missing-module`.

**The live run (the mentor's).** One command, from `code/` on the Docker host, after `make bench-images` at the
revision under test. The first form prints only the plan:

```bash
BENCH_KEY_FILE=/path/outside/code/openrouter.key make bench-live DRY_RUN=1   # the plan: no request, no spend
BENCH_KEY_FILE=/path/outside/code/openrouter.key make bench-live             # 5 tasks × 2 harnesses × 3 arms = 30 runs, n = 1
```

- **It needs `BENCH_KEY_FILE`**: one line, mode `0600`, yours, outside the repository. `run.sh` checks it on the host,
  and the driver checks it again on its read-only mount.
- **Caps** (defaults):
  - `BENCH_TURN_CAP=30` per run;
  - `BENCH_SPEND_CAP_USD=10.00` per invocation;
  - 900 s per run (`bench/run.sh --run-limit S`).

  `BENCH_MODEL` defaults to `deepseek/deepseek-v4-pro-0813` (`pins.env`).
- **Spend estimate** (research RB18; printed by the plan): about $0.03 per turn, so about $7.29 at 8 turns per run and
  $27.32 at the turn cap. The $10 spend cap therefore binds. The recorded spend is OpenRouter's own figure from each
  answer.
- **Where it lands:** `bench/out/<UTC stamp>/`:
  - `report.txt`;
  - `traces/<task>--<harness>--<arm>.json`;
  - `transcripts/` (each harness's own output, and Codex's rollout).

**What the lane needs:**
- `make test`: the three bench e2e files above, and everything else.
- `make bench-images`: it builds the new harness image, whose build fetches both tarballs from the npm registry and
  checks them against `pins.env`.
- `make scan`: the harness image is scanned when present, and has **no reviewed baseline yet**.
- `make lint`: the two new bats files are on the shellcheck list.

**Host lane** (advisory, `tests/host/run.sh` on CPython 3.14.8 over the working tree this cycle's last commit records, 2026-10-13T08:34:17Z–08:42:59Z): **rc 0. pytest 2452 passed, 12 skipped (the first full run, 08:23:37Z–08:32:17Z, failed 2, both fixed: see process failure 8); env layer 60/60, shell-env hook 57/57, command-not-found 33/33**. Bench
units alone: 628 passed. ruff check and format: clean (120 files). mypy `--strict`: clean (39 files). shellcheck
0.11.0: clean on `bench/run.sh` and the three bench bats files. Publish deny-list over the committed tree: run over the tree before the commit and again at HEAD after it (P1–P7, below in the commit report).

**not_verified**
- **Nothing ran in Docker:**
  - the harness image's build (npm fetch, sha512, each binary's `--version`), its scan, and its `--volumes-from` mount;
  - the per-invocation internal network and the driver joining it by host name;
  - the relay reached as `bench-relay`;
  - every e2e cell above.
- **The scan:** the harness image has no reviewed baseline. If Grype reports an unfixable High or Critical in the Bun
  or Rust binaries, `make scan` fails until the operator reviews one.
- **OpenRouter, without a key:**
  - whether it accepts Codex's `namespace` tool (`multi_agent_v1`) for this model;
  - whether it answers both protocols for this model (OpenCode chat completions, Codex Responses);
  - whether `usage.cost` arrives in the Responses stream's `response.completed`;
  - the generation-stats fallback's field (`data.total_cost`);
  - how often it answers 429.

  The first live run is its own test tier (llm-apis Q001).
- **Codex stops at the first 429** (recorded against the stand-in), so live Codex rows may stop more often than
  OpenCode's. Each is named `stopped (api-rate-limit)`, never a loss.
- **The key, by the send's route:**
  - both harnesses pass `OPENROUTER_API_KEY` to the agent's commands (each printed it present, against the stand-in);
  - in the timelike arms, 001's strip removes it from the agent's bash, which is not checked live;
  - in vanilla nothing strips it, so the provider sees whatever the agent prints. The gate keeps it out of every
    file.

  FOR-MENTOR Item 25 asks whether the relay should hold the key instead.
- **The told placement:** that each harness actually reads the placed file (`~/.config/opencode/AGENTS.md`,
  `$CODEX_HOME/AGENTS.md`) is 007's claim (its research R1), not observed in this cycle's transcripts.
- **Turns are counted per harness** (OpenCode's steps, Codex's response records) and are not comparable across
  harnesses. The report never compares harnesses.
- **Codex's own per-call limit** is unknown, so its traces record the run limit in its place. OpenCode's is 120 s, as
  its transcript showed. OpenCode also waited out its 120 s when a command's shell was killed (`kill -KILL $$`).
- **Codex runs as its native binary, not through its npm launcher**, so its bundled `rg` is not on its PATH.
- **Memory kill has no live task**; only the probe produces it.
- **python-missing-module's install** fails in vanilla as `other` (an externally managed interpreter) and in timelike
  as `network denial` (the guard), by each image's design. A live model may try something else first.
- **The fake agent cannot read a placement**, so its told and not-told arms are equal by construction. The report says
  so.
- **The stand-in's script is every step once.** A task whose steps make sense on one branch only may end failed under
  it. That is a fact about the script, not about timelike.
- **The spend estimate's per-turn figures** (20 000 in, 1 000 out) are assumed.
- **Schema-1 trace sets** (slice 0's `bench/out` runs) are refused by this build's `report`. Slice 0's revision
  re-reports them.
- **The host-lane probe of the harnesses' own network fetches** used a dead proxy, not network isolation, which
  unprivileged namespaces did not allow on this host.

**changed_other_features:**
- No other feature's code or contract. The told arm runs 007's `timelike announce --install` unchanged. The categories
  read 003's, 007's, 013's and agentio's verdict texts and change none of them.
- **Shared files changed:**
  - `README.md`: the send's block (row 02, Status: 20 of 38, Next: 12 slice 1), the bench's section, and the scan and
    layout lines; previous marks cleared, every changed passage in `<mark>`; the command reference unchanged and its
    drift test passing.
  - `.specswarm/tech-stack.md` 1.7.0: two harnesses auto-added by plan, declared, not a discovery audit.
  - `pins.env`: harness pins, `BENCH_MODEL` and its price.
  - `Makefile`: the harness image, `bench-live`, two bats files on the lint list.
  - `scan/scan.sh`: the harness image.
  - `FOR-MENTOR.md`: Item 25.
  - `tests/unit/test_scan_report.py`: five images.
- The `.specswarm/metrics.json` entry was not written (implement step 10j), as in Cycles 2 and 3.

**process_failures_recorded:**
1. **A composed time:** T034's "Completed" was typed, not read. Caught at once, corrected from the clock, and the commit
   amended before the next task.
2. **mypy unread before commit:** T042 was committed before mypy's result was read (31 narrowing errors). Fixed, and the
   commit amended with a true record before anything was built on it.
3. **A scope miscount:** T038's scope line said 7 changed files. It was 6, corrected from git.
4. **An unverified claim, caught:** FOR-MENTOR Item 25's first draft said Codex drops `*KEY*` variables from the
   agent's commands. Tested against the stand-in, neither harness does. Corrected before the commit.
5. **`pkill -f` killed my own shell:** while probing, a `pkill -f` matched its own command line (exit 144), against a
   standing rule. No harm, and later probes tracked the stand-in by its own timeout.
6. **A blocked removal:** a `rm -rf "$HOME"`-shaped cleanup in a probe was stopped by the harness's safety check. Nothing
   was removed, and fresh literal directories were used instead.
7. **An e2e test that could reach the provider** (a key file under `bench/out/e2e`) was written and removed before any
   commit.
8. **The full host lane caught two failures** after the per-task runs had passed:
   - a scan unit still counting four images;
   - `--break-system-packages` in the new task, which 007's FR-28 forbids repo-wide.

   Both were fixed before this report (FR-39 amended, declared).
9. **Two design defects, found by reading before any lane:**
   - the harness would have been started by `bash -c`, whose BASH_ENV strip in the timelike image would take its key;
   - `BENCH_KEY_FILE` is itself key-shaped, so every live run would have refused itself.

   Both were fixed, with units.

**retired_prompts_seen:** none. The mailbox this send replaced held 15 slice 1, discharged at `8dbddc7`.

### Implement step 10 — quality validation (specswarm 2.44.0 blocks), as the library reported it

- The detector found `pytest` (`"primary": "pytest", "count": 1`).
- `run_tests pytest` returned exit 2, "pytest is declared by this project but not installed here": the library runs
  `/usr/bin/python3`, which has no pytest. Unit tests are therefore **unmeasured** by this step (the host lane above
  measured them, on CPython 3.14.8).
- The score is **`unknown`**. `min_quality_score: 0` and `block_merge_on_failure: false` (`quality-standards.md`), so
  it is informational and blocks nothing.

### Addendum 1 — Item 25 ruled (b), built; lane 02s1-a's items 2 to 4

**Written:** 2026-10-13T17:11:10Z (read from the clock), on `modify/002-slice-1`. Same send, same cycle. Instructed by the
operator, relaying `../bridge/feedback/02-20261013-102310-lane-02s1-a-item-25-not-built-told-arm-trace-sbom-empty.md`
(the lane's four items) and `../bridge/feedback/02-20261013-071257-item-25-the-relay-holds-the-key.md` (the ruling,
read in full). Lane 02s1-a had ended (`0d47e3f`); nothing was edited while it ran. **Nothing was pushed or merged.**
None of this addendum's work has run in Docker: lane 02s1-b decides it.

**Status in one line:** the relay in the bench driver now holds the key, under all seven of the ruling's conditions,
each with a test. The told arm's setup-failed trace is valid. The key-file cell writes nothing into the checkout. The
harness image's scan sees both harnesses, and an empty SBOM fails. FOR-MENTOR Item 25 is closed.

| Task | Commit | What |
|---|---|---|
| T057 | `22c9071` | lane item 4: `scan/evaluate.py` (an empty SBOM fails, naming the image; `pinned`), `scan/scan.sh` (`pinned_packages_of`), their units |
| T053 to T056 | `3311da2` | Item 25 (b) in `relay.py`, `harness.py`, `runner.py`, `executor.py`, `trace.py`, `bin/timelike-bench`; the plan's basis; lane items 2 and 3; their units; one e2e cell |
| T058 | this commit | the spec, contracts, data model, plan, research, quickstart; README; FOR-MENTOR Item 25 closed; this addendum; `tasks.md`, `decisions.md`, `reboot.md` |

#### Item 25's ruling, as built (each condition and its test)

1. **The relay replaces any incoming `Authorization`.** It drops `Authorization`, `X-Api-Key`, `Api-Key` and `Cookie`
   from every request, placeholder or not, and adds `Authorization: Bearer <key>` from the key in its memory. Against
   the stand-in there is no key and it adds none.
   *Tests:* `test_c1_the_relay_replaces_the_authorization_a_request_arrives_with` (the placeholder, another bearer,
   and an `X-Api-Key` with a cookie all reach the stand-in as the relay's test key, nothing else);
   `test_c1_with_the_stand_in_no_credential_is_forwarded_at_all`; `test_c7_the_stand_in_path_has_no_key_and_the_relay_adds_none`.
2. **One placeholder,** `placeholder-the-bench-relay-adds-the-key` (`harness.KEY_PLACEHOLDER`, documented there and in
   FR-30). It is lowercase words with no provider prefix, the same for every harness and every run, and it is in each
   harness's exec environment as `OPENROUTER_API_KEY`.
   *Tests:* `test_c2_the_placeholder_is_fixed_documented_and_not_key_shaped` (both harnesses, two sets of pins);
   `test_a_live_harness_is_started_by_dash_so_bash_env_cannot_strip_its_key_variable` (the exec's argv).
3. **The key lives in the driver's memory only,** read from `BENCH_KEY_FILE` at start and handed to the relay (and to
   the driver's own generation-stats lookup, FR-35). `pass_env` is gone from the executor, and `runner.environ_with`
   is removed: no `docker exec -e` carries it, and the docker CLI's environment is the driver's own, unchanged.
   *Tests, with a test key value:* `test_c3_no_harness_exec_and_no_environment_holds_the_key` (the harness exec's
   environment, the driver's `os.environ`, and the argv and environment of the exec that `bin/timelike-bench`'s
   `DockerSession` builds); `test_c3_the_key_appears_in_no_accounting_summary_or_refusal`; the driver's `Config.Env`
   is `run.sh`'s `-e` list, where `test_a_good_key_file_is_mounted_read_only_and_its_value_never_travels` asserts
   only the path travels; each task container's environment is refused when key-shaped, as before.
4. **Only what a harness needs is forwarded:** `POST /api/v1/chat/completions` and `POST /api/v1/responses` for the
   pinned model, and `GET /api/v1/generation`, to the one upstream. Anything else is answered 403 with a named verdict,
   counted under `refused`, and never forwarded: `route-not-allowed` (another method or path, an absolute-form target
   naming another host, `CONNECT`), `no-model`, or `other-model`. `other-model` ends the run `stopped`, cause
   `model-refused`, a new cause in the trace schema.
   *Tests:* `test_c4_screen_forwards_only_the_harness_routes_and_the_pinned_model` (11 cases);
   `test_c4_refusals_are_named_recorded_and_never_forwarded` (the stand-in sees none of four refused requests);
   `test_c4_generation_stats_are_forwarded_with_the_relay_s_key`;
   `test_a_request_for_another_model_ends_the_run_stopped_and_is_never_forwarded`; `live_ending`'s table.
   *Evidence that the routes are enough:* both pinned harness binaries ran on this host through the new relay against
   the stand-in, all four recorded scenarios each (`record.py`'s setup, dead proxy). Nothing was refused, and every
   request, turn and status count equalled the recordings'. A new e2e cell checks the same in the containers.
5. **Every request counts, whoever sent it.** The same turn and spend rules apply to any request. The relay **cannot
   tell** a harness's request from an agent command's: they come from the same container and address, and anything the
   harness carries the agent can read. So each live trace's `extensions.relay.senders` says exactly that.
   *Test:* `test_c5_every_request_counts_whoever_sent_it_and_the_summary_says_senders_are_not_told_apart` (a
   curl-shaped request takes a turn and spends like the harness's, and the cap stops the third).
6. **The write gate stays** (FR-31). *Test:* `test_c6_the_gate_still_refuses_a_file_holding_the_key_should_it_ever_appear`.
7. **Fake-agent runs are unchanged.** They still refuse any key-shaped variable and a set `BENCH_KEY_FILE`, and start
   no relay. *Tests:* the existing refusal units, and `test_c7_a_fake_run_starts_no_relay_network_and_no_harness_holder`
   (no `network` or `create` call in a full fake run).

**The ruling's addition:** the plan's estimate states its basis. A new `basis:` line gives the requests per run (8
typical, or the turn cap), the tokens assumed per request (20 000 input, 1 000 output), and the prices with the date
they were read: `BENCH_MODEL_PRICE_READ=2026-10-13`, a new pin forwarded by `run.sh`.
*Tests:* `test_bench_plan.py`, `test_bench_run_sh.py`.

#### Lane item 2: the told arm's trace

- **The cause:** `run_task`'s setup-failure path built the trace before the placement, so a told run whose setup
  failed had an empty placement, which its own schema refuses. That path is reachable only when setup fails. So in
  the runner container the timelike setup failed, and vanilla's did not.
- **Why setup failed, inferred, not observed** (the runner's traceback file is gone): setup ran under the agent's call
  limit, which the unit sets to 2 s. The timelike setup runs every git hook through the dispatcher. On this host it
  takes 0.31 s for `git-inspect`, against vanilla's 0.06 s.
- **The fix:**
  - the invariant is kept, and the trace is made true: a told run whose setup failed records `not placed`, as the live
    path already did;
  - setup and check are the bench's own steps, so they run under `Limits.step_s` (120 s). The agent's calls keep the
    call limit, and `call_limit_s` in the trace is unchanged.
- **The wording:** a trace that breaks the schema now stops the run with `a run's trace broke the trace schema and was
  refused, so it was not written: <file>: <violation>`. The remediation says it is a bench defect, not a result.
- **Tests:** two CLI cells through the fake docker: a failing setup, and a 2 s setup under `--call-limit 1`. The first
  reproduces the lane's exact error on the old runner and passes on the new one. There are also three runner units.

#### Lane item 3: the key-file cell

The "inside the repository" cell copies `run.sh` into a throwaway repository in its temp directory and puts the key
file there. `run.sh` takes the repository from its own location. Nothing is written into the real checkout, and the
file holds `x`.

#### Lane item 4: the harness image's SBOM

- **An SBOM with no packages fails** its step, for every image, naming it: `the SBOM of <image> catalogues no packages,
  though the image holds software: Grype had nothing to match, so its result says nothing (a pass on nothing cannot
  fail)`.
- **The harness image's SBOM takes both harnesses from their pins,** before Grype reads it:
  - `scan.sh`'s `pinned_packages_of` names them, and `evaluate.py pinned` adds them;
  - they run on the agent image's interpreter with no network;
  - each is marked as found in the pins and located at its binary;
  - the step's detail says how many were added.
- **Which names:** each binary is named by the package its advisories are filed under, at its pin: `opencode-ai@1.19.0`
  and `@openai/codex@0.162.1`. Read from the npm registry, each lists the platform build the image holds
  (`opencode-linux-x64`, `@openai/codex@0.162.1-linux-x64`) among its optionalDependencies, at the same version.
  Keeping each package's `package.json` in the image would have let Syft catalogue the platform packages, which carry
  no advisories, so Grype's 0 would still have said nothing.
- **No baseline entry was written.** If Grype reports an unfixable High or Critical, it goes to the operator.

### Group C — Addendum 1

**delegations:** `[]`.

**criteria_reestablished** (the same seven citations as Cycle 4's report, each still one `- [ ]` line of the send;
nothing has run in Docker since lane 02s1-a, which was not a sign-off lane, so every mode is still **`unconfirmed`**):
- `02 · "One command runs a task in both a vanilla image and the timelike image"` _(slice 0)_ — **unconfirmed**
  (lane: `speedup-bench.bats`, SC-1 cells).
- `02 · "The bench runs end to end in CI against a deterministic fake agent without any API key"` _(slice 0)_ —
  **unconfirmed** (lane: `speedup-bench.bats`, SC-2 cells; host: the five `test_bench_cli.py` units item 2 fixed).
- `02 · "Each run is labelled told or not-told, and the report counts timelike tool invocations per arm"` _(slice 1)_
  — **unconfirmed** (lane: `speedup-bench.bats` SC-4, and the SC-5 file's adoption recounts).
- `02 · "The same task catalog runs under two harnesses and the report shows results per harness"` _(slice 1)_ —
  **unconfirmed** (lane: the SC-5 file, now six cells; the new one checks that no harness request was refused).
- `02 · "Two arms that end the same way in the same number of turns are ranked by hangs, then by failed commands"`
  _(slice 1; revision 8)_ — **unconfirmed** (lane: `speedup-bench.bats` SC-6, the validator's `verdicts`).
- `02 · "Failed commands are grouped into categories including command not found"` _(slice 1)_ — **unconfirmed**
  (lane: the SC-7 probe file).
- `02 · "DEMO: the Adopting developer compares timelike tool adoption between a told arm and a not-told arm"` _(slice 1;
  D11, Manual)_ — **unconfirmed**. The mentor's live run, then the operator's reading.

**reconcile_mode:** `scoped` (unchanged; no revision moved, and `audited_against` stays `[1, 8]`).

**not_verified** (Cycle 4's list stands, with these changes):
- **Removed:** the key-by-the-send's-route lines. No harness and no agent command holds the key now, so the vanilla
  arm's agent cannot print it to the provider.
- **Added, condition 5:** **an agent's command can spend through the relay, within the caps.** It shares the harness's
  network, so it can reach `bench-relay:8417`. The relay forwards its requests by the same rules, so the agent can use
  the key without reading it. The relay cannot tell such a request from the harness's, and the traces say so
  (`senders`) instead of attributing any.
- **Not checked by the relay:** the `Host` header. The relay connects only to its one upstream, and refuses an
  absolute-form target and `CONNECT`, so the header changes nothing it forwards.
- **Everything in Docker:**
  - the relay's refusals in the containers (the new e2e cell);
  - the harness image's scan with its pinned entries, including whether Grype matches entries `pinned` added (syft
    JSON, `type: npm`, a purl) as it matches Syft's own;
  - lane item 2's fix in the runner container. Its cause there is inferred.
- **OpenRouter, without a key** (unchanged): Codex's `namespace` tool for this model, both protocols, `usage.cost` in
  the Responses stream, the generation-stats field, how often it answers 429. Now also: whether it takes the relay's
  `Authorization` as it would a harness's. It should, since only the header's source changed.

**changed_other_features:**
- **The scan gate, every image** (001's agent image, 004's Adele, the bench's three): an SBOM that catalogues nothing
  now fails. All five catalogued packages in lane 02s1-a except the harness image, which now gets its pins.
  `scan/evaluate.py` and `scan/scan.sh` are shared files.
- **Shared files changed:** `pins.env` (`BENCH_MODEL_PRICE_READ`), `README.md` (the bench's key passage, inside the
  mark this cycle already gave it; the cycle's other marks kept, since this addendum is part of the same update),
  `FOR-MENTOR.md` (Item 25 closed), `tests/fixtures/transcripts/record.py` (the Relay's new `model` argument; the
  recordings are unchanged).
- No other feature's contract or code.

**process_failures_recorded:**
1. **A unit called the function it had patched:** the first draft of
   `test_run_bench_names_the_trace_its_schema_refused` monkeypatched `runner.run_task` and called it from inside the
   patch (RecursionError). Fixed by keeping the original first, before any commit.
2. **59 lines over the 110-column limit** in the first ruff run, all this addendum's. They were rewrapped and
   shortened, and ruff was clean before any commit.
3. **To prove item 2's unit,** I swapped the committed `runner.py` and `bin/timelike-bench` into the working tree,
   ran two units, and copied the new files back from the scratchpad. The diff was checked afterwards. No commit was
   involved, but for a moment the working tree held the old code.

**retired_prompts_seen:** none.

#### Host lane

`make test-host`, timelike's CPython 3.14.8 in a scratch venv, over the working tree of `3311da2` plus this commit's
records (no code changed after the run), 2026-10-13T17:01:57Z–17:10:47Z (read from the clock): **rc 0**.
- pytest tests/unit: **2489 passed, 12 skipped** (497 s);
- `test_env_layer.sh` 60 of 60; `test_shell_env_hook.sh` 57 of 57; `test_command_not_found.sh` 33 of 33.

Other checks:
- ruff check and format: clean (285 files);
- mypy `--strict`: clean (39 files);
- shellcheck: clean over the Makefile's 91 files;
- `scripts/readme_reference.py --check`: current, 14 tools;
- the deny-list: PASS over the working tree before the commits (562 files) and over the three commit messages, P1–P7 0/0.

#### Then

Commit everything, and report done. No commit after that until the mentor says lane 02s1-b has ended.
- **The lane:** `make test`, `make bench-images`, `make scan` with the deny-list read, and `make lint`.
- **After it:** the live run (D11), `BENCH_KEY_FILE=… make bench-live DRY_RUN=1`, then without `DRY_RUN`. Its plan now
  prints the estimate's basis.

### Addendum 2 — live run 1: the driver's CA store; what a relay turn is

**Written:** 2026-10-14T03:45:57Z (read from the clock), on `modify/002-slice-1`. Same send, same cycle. Instructed by the
operator, relaying `../bridge/feedback/02-20261014-031353-live-run-1-the-driver-has-no-ca-certificates.md` (read in
full). Lane 02s1-b had passed on `ec6f626` (observed by the mentor, `bridge/history.md` row 2026-10-13T18:57:18Z), and
live run 1 had ended; nothing was edited while either ran. **Nothing was pushed or merged.** None of this addendum's
work has run in Docker: lane 02s1-c decides it.

**Status in one line:** the driver image now carries a CA store, and a no-network cell proves the relay's own HTTPS
client verifies against it and refuses what it cannot verify. A relay turn is now a tool-offering request that was
answered, so a harness retrying an unreachable provider no longer spends the turn cap.

| Task | Commit | What |
|---|---|---|
| T059 to T061 | this commit | item 1 in `bench/driver/Dockerfile`, the SC-5 cell and `tests/e2e/fixtures/relay_tls.py`, a host unit; item 2 in `relay.py` and its units; the spec, contracts, data model, this addendum, `tasks.md`, `decisions.md`, `reboot.md` |

#### Item 1: the relay could not verify OpenRouter's certificate

- **The fix, in the image:** `bench/driver/Dockerfile` §1 installs `ca-certificates` (with the `openssl` it depends
  on), and its comment now says why: since slice 1 the relay is an HTTPS client of OpenRouter that sends it the key.
  The build fails if `/etc/ssl/certs/ca-certificates.crt` is empty or `/etc/ssl/certs` holds no hashed certificate.
  The relay is unchanged: it still verifies with the interpreter's default context, which reads `/etc/ssl/certs`.
  Verification is never turned off, and the relay is given no context of its own.
- **The cell, and which one:** the stronger of the two offered. `SC-5 the relay verifies an HTTPS upstream against the
  driver's system store, and refuses one it cannot verify` runs in the driver image with `--network none`:
  - `store`: `/etc/ssl/certs` holds hashed entries, and the bundle loads a non-zero CA count;
  - `make`: a throwaway CA and a `localhost` certificate it issued, made with `openssl` at test time and never kept;
  - `check refused`: the model stand-in served over TLS with that certificate, and the relay pointed at it as a live run
    is (`https://localhost:<port>`, no context given). The answer is 502 naming `CERTIFICATE_VERIFY_FAILED`, the
    stand-in receives nothing, and the request counts as unanswered. This proves verification is on;
  - `update-ca-certificates` adds the CA to the system store, then `check verified`: 200, forwarded once, one turn.
    This proves the store is the one the relay reads.
- **Why not the minimum alone:** `cert_store_stats()['x509_ca'] > 0` on the default context cannot pass with this
  interpreter. Its default context has no cafile on Debian (it looks for `/etc/ssl/cert.pem`) and reads
  `/etc/ssl/certs` only lazily, at lookup. On this host it reports 0 with 147 hashed entries installed. So the
  `store` step counts the bundle instead, loaded on its own.
- **On the host:** the cell's steps are also a unit,
  `test_live_run_1_item1_the_relay_s_https_client_verifies_its_peer`. It trusts the CA through `SSL_CERT_FILE`, since
  only the image's cell may change a system store. I also ran the `verified` step through a rehashed `SSL_CERT_DIR`
  with no cafile, which is the image's arrangement; it verified.
- **The scan:** `ca-certificates` and `openssl` are new in the driver image. `make scan` reports what they bring; any
  finding with no fix goes to the operator for review, as before. No baseline entry was written.

#### Item 2: failed requests counted as turns — the answer

**An unanswered request does not count toward the turn cap.** The cap bounds model turns. A request the upstream
never answered, or answered with an error status (429, 5xx, 401), produced no model turn. Under the old rule a
harness's retries spent the cap: in `git-commit-hook-hangs · codex · not-told`, 30 retries made 30 "turns" and no
answers.

`stopped_by` was empty there, and that was correct under the old rule too. The cap refuses only a turn beyond it, and
the run made exactly 30.

- **Built:**
  - a relay turn is a tool-offering request answered with HTTP 200. The others are counted under the summary's new
    `unanswered`;
  - the cap refuses the next tool-offering request once the answered turns, with those still waiting on the upstream,
    reach it, so concurrent requests cannot pass it;
  - retries against a dead provider are now bounded by the run limit and the harness's own retry policy. The run ends
    `stopped` (`api-unreachable`), as before.
- **The two figures are labelled as two counts, not made equal.**
  - The relay's `turns` counts answered tool-offering requests, including the final answer.
  - The trace's `totals.turns` is the harness's own last turn that issued a tool call (spec § Assumptions (slice 1),
    item 10).
  - A normal run has one more of the first. Every summary now carries `turns_counted`, a fixed sentence saying so.
  - On live run 1's runs, both would now read 0.
- **Tests:**
  - `test_item2_unanswered_requests_are_not_turns_and_do_not_reach_the_cap`: five 502s with a cap of 3, none refused;
    0 turns, 5 unanswered;
  - `test_item2_answered_turns_reach_the_cap_after_errors`: two 500s, then two answers, then the cap;
  - `test_error_statuses_pass_through_and_are_counted`: 429, 500 and 401 are unanswered;
  - `test_c5_…`: its count is now 2, because the refused third was never answered.
- **Left as recorded:** the relay counts in `tests/fixtures/transcripts/*.meta.json` were recorded under the old rule.
  Nothing reads them.

### Group C — Addendum 2

**delegations:** `[]`.

**criteria_reestablished** (the same seven citations; lane 02s1-b ran every automated one on `ec6f626`, and this
addendum changes the driver image and the relay after it, so lane 02s1-c decides them again):
- `02 · "One command runs a task in both a vanilla image and the timelike image"` _(slice 0)_ — **observed by the
  mentor** on `ec6f626` (lane 02s1-b: `speedup-bench.bats`, SC-1 cells, in e2e 688 of 688); not yet on this commit.
- `02 · "The bench runs end to end in CI against a deterministic fake agent without any API key"` _(slice 0)_ —
  **observed by the mentor** on `ec6f626` (lane 02s1-b: SC-2 cells, and the host units in its unit run); not yet on
  this commit.
- `02 · "Each run is labelled told or not-told, and the report counts timelike tool invocations per arm"` _(slice 1)_
  — **observed by the mentor** on `ec6f626` (lane 02s1-b: SC-4, and the SC-5 file's adoption recounts); not yet on
  this commit.
- `02 · "The same task catalog runs under two harnesses and the report shows results per harness"` _(slice 1)_ —
  **observed by the mentor** on `ec6f626` (lane 02s1-b: the SC-5 file's six cells); this commit adds a seventh, the TLS
  cell, which has not run.
- `02 · "Two arms that end the same way in the same number of turns are ranked by hangs, then by failed commands"`
  _(slice 1; revision 8)_ — **observed by the mentor** on `ec6f626` (lane 02s1-b: SC-6, the validator's `verdicts`);
  not yet on this commit.
- `02 · "Failed commands are grouped into categories including command not found"` _(slice 1)_ — **observed by the
  mentor** on `ec6f626` (lane 02s1-b: the SC-7 probe file); not yet on this commit.
- `02 · "DEMO: the Adopting developer compares timelike tool adoption between a told arm and a not-told arm"` _(slice 1;
  D11, Manual)_ — **unconfirmed**. Live run 1 reached no model: 30 of 30 runs `stopped (api-unreachable)`.

**reconcile_mode:** `scoped` (unchanged; no revision moved, and `audited_against` stays `[1, 8]`).

**not_verified** (Addendum 1's list stands, with these changes):
- **Added, live Codex rows:** Codex prints `Model metadata for <model> not found. Defaulting to fallback metadata` at
  the start of each run (live run 1, with `deepseek/deepseek-v4-flash-0731`). It may change how Codex budgets its
  context. It probably applies to the pinned pro model too. Nothing built for it.
- **Added, item 1:** that Debian trixie's `ca-certificates` brings `openssl`, which the cell uses to make its CA. It
  does on Ubuntu 24.04 here (`apt-cache depends`). The image was not built here, so this is not checked; if the CLI is
  absent the cell fails, naming it.
- **Added, item 1:** what `make scan` reports for `ca-certificates` and `openssl` in the driver image.
- **Added, item 1:** OpenRouter's real certificate chain against the image's store. The cell proves the mechanism with
  a throwaway CA; only the next live run meets the real chain. No cell may use the real network.
- **Updated, from Addendum 1:** lane 02s1-b ran the relay-refusal cell in the containers (none refused), and the
  harness image's scan read its two pinned entries with 0 matches (the mentor's history row). Whether Grype would
  match such entries when an advisory exists is still not shown.
- **Unchanged:** an agent's command can spend through the relay, within the caps; OpenRouter, without a key, as
  listed. Live run 1 got no answer, so none of those were reached.

**changed_other_features:**
- **The bench driver image** gains `ca-certificates` and `openssl`. It is 002's own image; the scan gate covers it.
- No other feature's contract, code or shared file. `pins.env` is unchanged.

**process_failures_recorded:**
1. **Slice 1 made the relay an HTTPS client and left the driver image as slice 0 built it.** Its §1 comment said "no
   TLS, so no ca-certificates", and nothing re-read it when the relay was added. Every lane cell used the stand-in
   over plain HTTP, so nothing could fail. The first live run found it. The new cell exercises the relay's HTTPS
   path, with no network.
2. **The relay counted a turn before it knew whether one happened,** at request time. The count was named as a model
   turn, but it was a count of attempts. Its unit never put an unanswered request against the cap.

**retired_prompts_seen:** none.

#### Host lane

`make test-host`, timelike's CPython 3.14.8 in a scratch venv, over this commit's working tree (code and tests final;
only this addendum's records written after), 2026-10-14T03:36:43Z–03:45:42Z (read from the clock): **rc 0**.
- pytest tests/unit: **2492 passed, 12 skipped** (501 s);
- `test_env_layer.sh` 60 of 60; `test_shell_env_hook.sh` 57 of 57; `test_command_not_found.sh` 33 of 33.

Other checks:
- ruff check and format: clean;
- mypy `--strict`: clean (39 files);
- shellcheck: clean over the Makefile's 91 files;
- `scripts/readme_reference.py --check`: current, 14 tools;
- the deny-list: see the commit's own check (run before it, over the working tree and the commit message).

#### Then

Commit everything, and report done. No commit after that until the mentor says lane 02s1-c has ended.
- **The lane (02s1-c, full, sign-off):** `make test` (it builds the driver image with the new §1; the SC-5 file's
  seventh cell is the TLS one), `make bench-images`, `make scan` with the deny-list read, and `make lint`.
- **After it:** live run 2.
