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
