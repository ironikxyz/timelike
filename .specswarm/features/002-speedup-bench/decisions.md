# Decisions Log — Feature 002
> Generated at 2026-09-29T00:23:02+00:00
> Spec: .specswarm/features/002-speedup-bench/spec.md

## Decision Key

| Tag | Meaning |
|-----|---------|
| ASSUMED | Assumption made without explicit spec guidance (confidence: high/medium/low) |
| DEFERRED | Decision postponed — noted for later resolution |
| FLAGGED | Judgment call between alternatives — requires review |
| ABSENT | What was NOT done and why — forced reflection on gaps |
| INHERITED | Assumption carried forward from a prior task's output |

---

### T001: bench/ skeleton, ignore, lint and type-check paths
**Started:** 2026-09-29T00:23:02+00:00 | **Completed:** 2026-09-29T00:23:02+00:00

INHERITED: (none — first task)
ASSUMED: benchlib is imported on the host lane by a sys.path entry in tests/unit/conftest.py, mirroring how agentio is imported there; in the driver image it sits in site-packages (RB6) — (confidence: high)
FLAGGED: mypy_path gains `bench`, and `bench/benchlib` joins mypy `files` now; `bench/bin/timelike-bench` joins at T009, because mypy fails on a listed file that does not exist yet — chose incremental over listing it early (confidence: high)
ABSENT: no .dockerignore — the Dockerfiles COPY named paths only, as image/Dockerfile does; a context-wide ignore is not needed for correctness
Verification: the diff only; nothing to run yet
SCOPE: in (5 changed files)

### T002: benchlib/trace.py — trace v1 dataclasses, derive, validate, write, load
**Started:** 2026-09-29T00:40Z | **Completed:** 2026-09-29T00:27:22+00:00 | **Delegate:** subagent (reviewed by coordinator)

INHERITED: benchlib import path and mypy_path from T001 — (confidence: high)
ASSUMED: calls is a tuple on the frozen Trace; the JSON form is a list — (confidence: high)
ASSUMED: seq runs 1..n, turn ≥ 1, byte counts ≥ 0, and harness_cut == (passed_bytes < stdout_bytes + stderr_bytes), because data-model defines harness_cut as derived — (confidence: medium)
ASSUMED: a recorded token count may be a genuine 0; an unrecorded one carries a reason and no counts — (confidence: medium)
FLAGGED: unknown keys are rejected in every object except under `extensions`, per trace-schema rule 5. A slice-1 key added on a call therefore bumps schema_version or moves under extensions — chose the strict reader over a lenient one because rule 5 says "under extensions only" (confidence: medium)
FLAGGED: from_json/load_traces fully validate and raise on a malformed file, naming it, so a report is never built over a bad trace; the cost is one bad file stops the load — (confidence: medium)
ABSENT: "completed requires the check to have exited 0" is not checkable from the trace (it carries no check exit code); the runner enforces it (T008)
ABSENT: 40-hex revision and sha256 image-id formats are not validated, only non-emptiness and the @sha256: mark
Verification: 101 passed; trace.py 100% line+branch; ruff, format, mypy --strict clean (delegate's run, re-run by coordinator at T018)
SCOPE: in (2 changed files)

### T003: benchlib/keys.py — key-shaped variable matcher (FR-12, RB9)
**Started:** 2026-09-29T00:40Z | **Completed:** 2026-09-29T00:27:22+00:00 | **Delegate:** subagent (reviewed by coordinator)

INHERITED: the F002 part/suffix lists and the GIT_CONFIG_KEY_<n> exemption from image/rootfs/etc/timelike/shell-env.bash — (confidence: high)
ASSUMED: names that are not shell identifiers are judged too (MY-TOKEN is key-shaped), erring toward refusal — (confidence: high)
ASSUMED: uppercasing by str.upper() matches bash ${name^^} for ASCII names; may refuse more for non-ASCII — (confidence: medium)
FLAGGED: no TIMELIKE_ENV_ALLOW bypass: a fake-agent run cannot be talked out of the refusal — chose strict over matching the hook's allow-list because FR-12 is a refusal, not a strip (confidence: high)
ABSENT: SSHPASS, MYSQL_PWD and GITHUB_PAT are not key-shaped, same as the hook's documented limits; the rule is not widened here
Verification: 95 passed; keys.py 100%; all 77 identifier-shaped table names cross-checked against the real hook via BASH_ENV (no disagreement, one-off script)
SCOPE: in (2 changed files)

### T006: benchlib/executor.py — the wrapper, capture, Local/Docker executors (RB2, RB5)
**Started:** 2026-09-29T00:45Z | **Completed:** 2026-09-29T00:27:22+00:00 | **Coordinator**

INHERITED: RB5's wrapper and hang rule (exit 124/137 and duration ≥ limit) — (confidence: medium, see FLAGGED)
FLAGGED: RB5's wrapper was wrong for dash: `kill -KILL -- -$t` fails with "Illegal number: -", so the group kill never ran and a detached child held the call open to the backstop. Changed to `kill -KILL -$t` (verified: the orphaned sleep is found in the group and killed; the call returns in 13 ms). research.md RB5 and contracts/bench-cli.md corrected — chose the dash-valid form over switching the wrapper to bash, because dash reads no startup file (confidence: high)
ASSUMED: the image's /bin/sh is dash, as on this host and Debian — (confidence: high)
ASSUMED: HEAD_CAP 4096 bytes kept per stream; everything counted — (confidence: high)
DEFERRED: creating /home/agent/task before the first `docker exec -w` — the runner (T008) does it
ABSENT: DockerExecutor has not run against a daemon (research R10); its argv is unit-tested, and a stand-in docker proves run() wires it through capture
Verification: 15 passed (hang near the limit, TERM-ignoring command killed at 137, detached child returns under 5 s, stdin at EOF, exact byte counts, backstop); ruff, format, mypy --strict clean
SCOPE: in (2 changed files; research.md and contracts/bench-cli.md are feature artifacts, exempt)

### T010: bench/vanilla/Dockerfile (RB1)
**Started:** 2026-09-29T00:40Z | **Completed:** 2026-09-29T00:27:22+00:00 | **Delegate:** subagent (reviewed by coordinator)

INHERITED: SHELL line, apt pattern, uid collision guard and useradd flags, GIT_SHA refusal — from image/Dockerfile — (confidence: high)
FLAGGED: label-only stamp (no REVISION file), because RB8 reads only the label and a file is one more non-Debian thing in the baseline (confidence: medium)
FLAGGED: image/Dockerfile's setuid sweep left out — it is timelike hardening, so it belongs to timelike's layers, not the baseline (confidence: medium)
FLAGGED: the build asserts git's recommends (ca-certificates, less, patch, openssh-client) and procps stayed out, so the baseline cannot drift silently (confidence: high)
ABSENT: no ENV, gitconfig, profile.d, shell-env hook, interpreter, tools or adele user — by definition (spec Assumption 1)
ABSENT: not built — no daemon here (R10); the Docker lane builds it
SCOPE: in (1 changed file)

### T011: bench/driver/Dockerfile (RB6)
**Started:** 2026-09-29T00:40Z | **Completed:** 2026-09-29T00:27:22+00:00 | **Delegate:** subagent (reviewed by coordinator)

INHERITED: interpreter block (image/Dockerfile §2), purelib copy (§3), docker CLI copy (tests/runner/Dockerfile), GIT_SHA refusal — (confidence: high)
FLAGGED: ENV HOME=/tmp rather than an extra -e HOME from run.sh, because the contract's -e list is closed; docker keeps an image-level HOME under -u — (confidence: medium)
FLAGGED: no USER (run.sh supplies -u uid:gid --group-add), absolute ENTRYPOINT, PATH written in full, no apt packages at all — (confidence: high/medium)
ASSUMED: the docker CLI needs no writable $HOME/.docker for run, exec, inspect and rm — (confidence: medium)
ABSENT: not built — no daemon here; it also COPYs bench/bin/timelike-bench, which T009 writes, so it cannot build before T009
ABSENT: the RB10 risk (Go stdlib CVEs in the docker CLI under grype) is recorded in a comment, not mitigated
SCOPE: in (1 changed file)

### T007: benchlib/docker.py — identity, staleness check, container lifecycle (RB5, RB8)
**Started:** 2026-09-29T01:00Z | **Completed:** 2026-09-29T00:28:45+00:00 | **Coordinator**

INHERITED: env_list_to_mapping from T003; the RB5 container flags — (confidence: high)
ASSUMED: every docker call goes through an injectable Runner, the real one time-limited at 120 s with stdin at EOF (P2) — (confidence: high)
ASSUMED: prepare_task_dir runs `mkdir -p task` as agent in /home/agent, which both images create with agent ownership (vanilla T010; timelike 001) — (confidence: medium: timelike's /home/agent ownership read from 001, not re-verified in an image)
FLAGGED: remove_container ignores docker's result — chose best-effort over raising, because it runs in a finally and must not mask the run's own failure; a leftover container is visible in `docker ps -a` (confidence: high)
ABSENT: no check that the three images share the same base digest — the vanilla and driver Dockerfiles take DEBIAN_IMAGE from pins.env, and the trace records base_digest from the same pins; an image built from another base would carry a different ID, recorded, not refused
ABSENT: no daemon here, so no real inspect output has been parsed; fixtures follow docker's documented inspect shape
Verification: 15 passed; ruff, format, mypy --strict clean
SCOPE: in (2 changed files)

### T004: benchlib/fakeagent.py — policy data, pure next_step, Walker loop guard (FR-11)
**Started:** 2026-09-29T00:40Z | **Completed:** 2026-09-29T00:29:44+00:00 | **Delegate:** subagent (reviewed by coordinator)

INHERITED: benchlib import path from T001 — (confidence: high)
ASSUMED: a 4th visit to a step gives up (`GIVE_UP:policy loop`), counting the start as the first visit — (confidence: high)
ASSUMED: next_step trusts the executor's hung flag and checks it before the exit code; exit 124 without hung is an ordinary failure — (confidence: high)
FLAGGED: the loop guard lives in a separate Walker, so next_step keeps the pure (policy, current, obs) signature that is FR-11's guarantee, asserted by an inspect.signature unit — (confidence: high)
ABSENT: Policy does not check every step is reachable from start; the catalog unit does
ABSENT: terminal kinds (done/give_up/escalate) are not mapped to trace endings here; the runner (T008) does, and "done" becomes completed only if the check passes
Verification: part of 51 passed (with T005); ruff, format, mypy --strict clean
SCOPE: in (2 changed files)

### T005: benchlib/catalog.py — four tasks and NOT_BENCHABLE (RB4)
**Started:** 2026-09-29T00:40Z | **Completed:** 2026-09-29T00:29:44+00:00 | **Delegate:** subagent (reviewed and amended by coordinator)

INHERITED: the fake-agent API from T004; RB5's wrapper, copied into the unit's local runner — (confidence: high)
ASSUMED: sed and grep (Debian Essential, in both images) are allowed beyond coreutils+git+bash — (confidence: medium)
ASSUMED: where RB4 names no hang recovery, the hang branch gives up naming the step — (confidence: medium)
ASSUMED: the timelike emulation replays image/Dockerfile's ENV block parsed at test time and points GIT_CONFIG_SYSTEM at image/rootfs/etc/gitconfig; BASH_ENV and /opt/timelike/bin are not replayed (no task uses them) — (confidence: high)
FLAGGED: RB4 predicted 3 vanilla calls for git-commit-hook-rejects; its own policy (commit, strip, add, recommit) is 4 at one command per step, as git-rebase-continue counts steps. The delegate kept RB4's 3 under a strict xfail and reported it; the coordinator ruled the policy stands and the count was wrong, corrected RB4, the task's `expected`, and the unit to 4, and removed the xfail — chose correcting the prediction over merging strip+add into one compound call, because a compound call would be a shortcut shaped to fit a prediction (confidence: high)
FLAGGED: setup identity bench@example.invalid, so the environment-blindness scan can reject the word "timelike" in any script — (confidence: high)
ABSENT: the tasks have not run in either real image (no daemon); the outcomes are from host emulation with git 2.43 (image: 2.47.3)
Verification: 51 passed (fakeagent + catalog), including every task's setup, policy and check run for real under vanilla and timelike emulation: inspect 2/0/0 tie; rebase 5/2/0 vs 4/1/0; hook-hangs 2/0/1 vs 1/0/0; hook-rejects 4/1/0 completed vs 1/0/0 failed. Both emulations give the same commit id (deterministic setup)
SCOPE: in (2 changed files; research.md is a feature artifact, exempt)

### T008: benchlib/runner.py — one task in one environment → one trace; the bench over the catalog
**Started:** 2026-09-29T01:15Z | **Completed:** 2026-09-29T00:31:34+00:00 | **Coordinator**

INHERITED: trace (T002), executor (T006), docker session shape (T007), Walker/terminals (T004), Task (T005) — (confidence: high)
ASSUMED: only the policy's calls are counted and timed; setup and check belong to the bench and sit outside calls and wall-clock — (confidence: high)
ASSUMED: a hung CALL followed by recovery is not a hung RUN; `hung` is the run limit or the driver backstop only (data-model) — (confidence: high)
ASSUMED: harness pass cap 30 000 bytes per stream; passed/cut recorded per call — (confidence: medium: a stand-in, documented)
FLAGGED: the run limit is checked between calls, so a run can exceed run_s by up to one call limit — chose between-call checks over interrupting a call mid-way, because a call already has its own limit and killing it twice would blur which limit ended it (confidence: high)
ABSENT: no retry of a failed setup: a broken task shows as `setup failed`, never silently skipped (trace-schema rule 6)
ABSENT: the docker Session (container per run) is not in runner.py; the CLI (T009) builds it from docker.py, keeping runner testable without a daemon
Verification: 21 passed — all four catalog tasks through the real runner and wrapper under vanilla and timelike emulation match RB4 (8 of 8), 8 valid stamped traces written and reloaded, every session closed, plus setup/check failure and hang, escalation, give-up, backstop, run limit, harness cut, and close-on-exception; ruff, format, mypy --strict clean
SCOPE: in (2 changed files)

### T016: benchlib/report.py — pairing, verdict, render, build_report (FR-9, FR-10)
**Started:** 2026-09-29T01:05Z | **Completed:** 2026-09-29T00:31:34+00:00 | **Delegate:** subagent (reviewed by coordinator)

INHERITED: verdict order and section order from data-model; first line and vanilla definition verbatim from contracts/bench-cli.md — (confidence: high)
ASSUMED: with no traces, line 1 is "NO TRACES — nothing was measured"; neither the fake nor the live line is true of an empty run — (confidence: high)
ASSUMED: one fake-agent trace anywhere makes line 1 the fake-agent line (FR-9 "any fake-agent run") — (confidence: high)
ASSUMED: nonzero_exits + hangs as the failure tiebreak counts a hung call twice (it is also non-zero), as data-model reads literally — (confidence: medium)
  ↳ *Superseded by discovery revision 8 (ruling (b), `bridge/feedback/02-20260930-060406-hang-counted-twice.md`): hangs are compared on their own after turns and before failed commands, each call counted once. Code change carried to 02 s1; slice 0's `report.py:119`, `:227` and `data-model.md` step 3 are unchanged. Annotated 2026-10-08 by modify Cycle 2 (T029); the line above is kept as written.*
  ↳ *Done in 02 slice 1 (Cycle 4, T034, 2026-10-13): `report.verdict` compares ending, turns, hangs, failed commands; the sentence quotes only table counts; `data-model.md` step 3 corrected at plan. Both lines above are kept as written.*
FLAGGED: catalog.NOT_BENCHABLE said "token-shaped", which put "token" before the appendix against FR-9; the delegate reported it rather than rewriting text in render; the coordinator changed it to "key-shaped" (FR-12's term) in catalog.py — (confidence: high)
FLAGGED: the appendix lists one line per trace, not the contract sample's single collapsed line — chose per-trace so a mixed live/fake set can't hide a recorded count (confidence: medium)
FLAGGED: pair() raises on two traces for one task and environment, rather than letting file order decide a verdict; slice 2's repetitions will change this — (confidence: medium)
ABSENT: free text from traces (ending reasons, goals) is not scanned for "token"; T009 adds a unit rendering the REAL catalog's text
Verification: 39 passed; report.py 100% line+branch; ruff, format, mypy --strict clean
SCOPE: in (3 changed files)

### T009: bench/bin/timelike-bench — the contract-bound CLI: run, report, catalog
**Started:** 2026-09-29T01:25Z | **Completed:** 2026-09-29T00:35:25+00:00 | **Coordinator**

INHERITED: runner (T008), report (T016), docker (T007), keys (T003), catalog (T005); agentio's Tool/Result/run — (confidence: high)
FLAGGED: a third subcommand, `catalog`, added as the conformance probe — `run` needs Docker and `report` needs traces, so neither is a probe that works anywhere; chose a read-only listing over a probe-only hidden flag because it is also what a reader asks first (P3). contracts/bench-cli.md amended (confidence: high)
FLAGGED: `action` is optional to argparse and required by main, because a required positional turned `--help` into a usage error (conformance C1 caught it) — (confidence: high)
FLAGGED: key refusal is exit 4 (grant required) for the driver's env, an image's ENV, or a task container's env; exit 1 when a stale stamp and a key occur together — chose 4 only when every problem is a key, so a stale image is never reported as a grant question (confidence: medium)
ASSUMED: TIMELIKE_BENCH_DOCKER names the docker binary, a test seam only; the driver image leaves it unset — (confidence: high)
ASSUMED: a task container with TERM set refuses the run (RB2) rather than recording it — (confidence: medium)
ABSENT: the docker leg itself is not exercised on the host lane: tests/unit/fakedocker.py runs each "container" as a local directory under the vanilla/timelike emulations, proving the wiring, not Docker
ABSENT: the command-line text summary names verdicts per task but not the report's loses-first ordering; the report file carries that
Verification: 22 passed — conformance (timelike-conform over bench/bin passes), a full `run` over the real catalog through the fake docker (8 traces, report first line, 1 loss / 1 tie / 2 wins, "token" nowhere before the appendix in the REAL catalog's text, 8 containers started and 8 removed), `report` rebuilds report.txt byte-identically from traces alone (FR-10), and refusals: planted key (exit 4, docker never called), key in image ENV, key in a container (removed), stale label naming both revisions, blank stamp, missing image, TERM in a container, unknown task, bad limits, empty env; ruff and mypy --strict clean repo-wide
SCOPE: in (5 changed files; contracts/bench-cli.md is a feature artifact, exempt)

### T012: bench/run.sh and the make bench / bench-images targets
**Started:** 2026-09-29T01:05Z | **Completed:** 2026-09-29T00:35:43+00:00 | **Coordinator**

INHERITED: the contract's run.sh (bench-cli.md), RB7 path rule, RB9 closed -e list; `build`'s docker-check and stamp-check — (confidence: high)
ASSUMED: bench-images depends on `build`, so the agent image is always rebuilt at the same GIT_SHA first (docker-compose Q004) — (confidence: high)
FLAGGED: a non-local DOCKER_HOST is refused rather than supported — the output bind mount would resolve on the remote daemon's host (P001, P002); chose refusal with a named reason over a copy-back step (confidence: high)
FLAGGED: BENCH_REPRODUCE is added to the -e list (make bench, or make bench TASKS='…'), so the report's reproduce line is the command the operator actually ran — contract amended at T009 (confidence: high)
ABSENT: nothing here has run against a daemon; verified: shellcheck clean, `make -n bench TASKS=…` expands as intended, and run.sh's refusals (no socket, empty GIT_SHA, unknown argument) print contract-shaped errors with codes 1 and 2
SCOPE: in (2 changed files)

### T013: tests/e2e/fixtures/validate_bench.py — the independent validator (H3, P004, P005)
**Started:** 2026-09-29T01:40Z | **Completed:** 2026-09-29T00:37:22+00:00 | **Coordinator**

INHERITED: the rules of contracts/trace-schema.md and bench-cli.md — re-derived, not imported — (confidence: high)
FLAGGED: the validator shares no code with benchlib, including its own key-shaped rule, so it cannot agree with the writer by construction; its unit's GOOD fixture is written by benchlib's writer, so the two are proven to agree on the real format, and every BAD case is a hand mutation — (confidence: high)
FLAGGED: two subcommands beyond T013's text: `env` (key-shaped names in env output, for SC-2's "without any API key") and `hang` (a vanilla hung call ended within limit + 10 s), because the bats runner has no Python or jq to read JSON — (confidence: high)
ASSUMED: it runs on the driver image's interpreter from the read-only repository mount in the Docker lane — (confidence: high)
ABSENT: the validator does not re-check the verdict arithmetic (win/lose/tie); the report's section order and first lines are checked, the verdicts are report.py's units' job
Verification: 31 passed; ruff clean
SCOPE: in (2 changed files)

### T014: tests/e2e/speedup-bench.bats — SC-1 and SC-2 in the Docker lane
**Started:** 2026-09-29T01:50Z | **Completed:** 2026-09-29T00:38:23+00:00 | **Coordinator**

INHERITED: the independent validator (T013); bench/run.sh as the one command (T012); the runner's socket and uid arrangement (001 R8) — (confidence: high)
FLAGGED: the test runs bench/run.sh itself (the operator's command) rather than a hand-built `docker run` of the driver, so SC-1's "one command" is the real one; refusals that run.sh deliberately cannot trigger (a planted key, a wrong expected revision) use a direct `docker run` of the driver with one extra -e — (confidence: high)
FLAGGED: "a blanked stamp fails the run" is tested as a mismatched expected revision (BENCH_GIT_SHA ≠ every label), not by rebuilding an image with a wrong label — both exercise check_identity's refusal, and the rebuild would cost a full image build per lane run; the blank-label branch itself is unit-tested (test_bench_cli, test_bench_docker) — (confidence: medium)
ASSUMED: the bats image's busybox provides realpath, stat -c and tr, as bench/run.sh needs when the runner calls it — (confidence: medium: not run here)
ABSENT: not run: no daemon in this workspace. Shellcheck clean. The five tests are unconfirmed until the operator's `make test`
SCOPE: in (1 changed file)

### T015: tests/run.sh — bench images step and the e2e mounts
**Started:** 2026-09-29T01:55Z | **Completed:** 2026-09-29T00:38:23+00:00 | **Coordinator**

INHERITED: run.sh's step/skip/record structure — (confidence: high)
FLAGGED: e2e does NOT depend on the new `benchimg` step, against tasks.md T015's "make e2e depend on them" — chose independence because a bench image failure would otherwise skip all of feature 001's e2e results; speedup-bench.bats fails loudly by itself when the images are missing (confidence: high)
ASSUMED: bench/out/e2e is mounted into the runner at its host path, and DEBIAN_IMAGE, REPO_HOST and BENCH_E2E_OUT are passed — (confidence: high)
ABSENT: a remote DOCKER_HOST (tcp/ssh), which run_e2e supports, will fail the bench tests: bench/run.sh refuses a non-local daemon by design (RB7). Named, not fixed
SCOPE: in (1 changed file)

### T017: scan/scan.sh — the gate over three images (FR-16, RB10)
**Started:** 2026-09-29T02:05Z | **Completed:** 2026-09-29T00:39:47+00:00 | **Coordinator**

INHERITED: scan.sh's four steps and evaluate.py's per-image baseline rule (discovery revision 5) — (confidence: high)
ASSUMED: the agent keeps its paths (scan/out/, scan/out/verdict.json), so feature 001's readers and reboot.md stay right; the bench images write scan/out/<image>/ — (confidence: high)
ASSUMED: evaluate.py's report runs on the AGENT image's interpreter for every image (vanilla has none), and pip-audit records `none` for an image with no interpreter — (confidence: high)
FLAGGED: gitleaks runs once (it scans the repository, not an image) and its record and report are shared into each image's directory — (confidence: high)
FLAGGED: a bench image that is absent is reported "not present; not scanned" and does not fail a scan of the agent alone — chose this so `make scan` after only `make build` still gates the shipped image; `make test` builds the bench images before any scan is read (confidence: medium)
DEFERRED: **scan/baseline/timelike-vanilla.json and scan/baseline/timelike-bench-driver.json do not exist, and must not be written by this instance.** A baseline is a person's review (review_by, reasons per origin). Until the operator reviews scan/out/<image>/baseline.proposed.json and commits them, the gate accepts nothing for those images, so their unfixable base-image findings will BLOCK `make scan`. Copying the agent's reviewed baseline onto images nobody reviewed was rejected. This is a merge-bar item for 002 (quality-standards: the scan must pass) — carried to the cycle report
ABSENT: not run against a daemon; verified by shellcheck and a scratch fake docker driving the flow: three images → per-image dirs, vanilla "no Python interpreter", shared gitleaks, exit 1 when one image fails, exit 0 when bench images are absent and the agent passes
SCOPE: in (1 changed file)

### T018: host-lane verification
**Started:** 2026-09-29T02:15Z | **Completed:** 2026-09-29T00:44:36+00:00 | **Coordinator**

INHERITED: every module and test from T001–T017 — (confidence: high)
ASSUMED: the coverage rc from reboot.md, extended with bench/* and the pytest copies of timelike-bench (a `benchbin` [paths] group) — (confidence: high)
FLAGGED: test_bench_cli's environment did not forward COVERAGE_PROCESS_START, so the tool's subprocess coverage was silently lost; fixed, following conftest.base_env — (confidence: high)
ABSENT: none of this is image evidence (001 R10): the host lane proves files, units and logic only
Verification (this workspace, host lane, advisory):
- ruff check + format --check over tools tests scan bench: clean (42 files)
- mypy --strict (pyproject files, 14 source files incl. bench): no issues
- shellcheck -x over every *.sh/*.bash/*.bats: clean
- pytest tests/unit under coverage: 565 passed, 1 skipped (the start-up test skips under tracing)
- coverage (line + branch, combined across subprocesses): **97% overall**; bench/benchlib 96–100% per module (executor 96%: the backstop's TimeoutExpired branch); bench/bin/timelike-bench 98%
- timelike-conform over bench/bin: passes (test_bench_cli); over tools/bin: passes (test_conform)
- make test-host: passed (units + env-layer files + shell-env hook, 29/29)
SCOPE: in (1 changed file)

### T019: README "Speedup bench" and reboot.md for 002
**Started:** 2026-09-29T02:25Z | **Completed:** 2026-09-29T00:44:36+00:00 | **Coordinator**

INHERITED: quickstart.md's reading guide; the fake-agent first line verbatim from contracts/bench-cli.md — (confidence: high)
ASSUMED: the README states the fake-agent caveat verbatim and makes no value claim, as its existing P6 sentence requires — (confidence: high)
ABSENT: no results are quoted in the README: nothing has run in an image yet, and a fake-agent result is not a value claim anyway
SCOPE: in (2 changed files)

### T020: cycle-report.md, Cycle 1
**Started:** 2026-09-29T02:35Z | **Completed:** 2026-09-29T00:45:38+00:00 | **Coordinator**

INHERITED: the send's `## Cycle report` block; T001–T019's decisions and verification — (confidence: high)
ASSUMED: criteria are cited as `02 · "…"` with enough text to match one line of the send — (confidence: high)
FLAGGED: all three criteria are `unconfirmed`, including SC-1 and SC-2, which have host-lane evidence: host evidence is never reported as an image-level pass (001 R10) — (confidence: high)
ABSENT: no demo_points_reached (the mentor derives them); no .implement-complete (not a dispatch run)
SCOPE: none — no files outside the feature's artifacts changed

### T021: one output layout for bench/run.sh and timelike-bench run --out (Docker lane feedback)
**Started:** 2026-09-29T02:40Z | **Completed:** 2026-09-29T02:41:05+00:00 | **Coordinator**

INHERITED: the mentor's Docker-lane run at 8ce6173 (../bridge/history.md 02:21:41Z) and note: "Pick one layout, then record it in the cycle report" — (confidence: high)
FLAGGED: `--out DIR` is exactly DIR, for both the tool and run.sh; without it, $BENCH_OUT/<UTC stamp>/ — chose "exact when named, stamped when not" over always stamping (which would have made the test compute a path it cannot know) or never stamping (which would let `make bench` overwrite the last run). speedup-bench.bats already assumed this rule and is unchanged (confidence: high)
FLAGGED: a DIR already holding traces is refused (exit 1), because an exact directory reused would mix two runs' traces in one report — (confidence: high)
ASSUMED: BENCH_DOCKER_SOCKET overrides the socket path for the host unit only; the driver-side mount is now `SOCKET:/var/run/docker.sock`, so the driver's CLI always finds the default path — (confidence: high)
ABSENT: the three failing bats tests have not been re-run at the fix commit; that is the operator's Docker lane. No scan baseline was written (a person's review)
Verification: tests/unit/test_bench_run_sh.py (8 tests) fails its --out test against the old run.sh and passes against the new; test_bench_cli adds an exact-dir and reused-dir test; full unit suite 575 passed; ruff, format, mypy --strict and shellcheck clean
SCOPE: in (4 changed files; contracts/bench-cli.md, tasks.md and cycle-report.md are feature artifacts, exempt)

### T022: catalog — what differs, notes per arm and ending, checks that say why (send …-080659, F002/F003)
**Started:** 2026-09-29T08:20Z | **Completed:** 2026-09-29T08:12:22+00:00 | **Coordinator**

INHERITED: the send's D2 findings (the loss read backwards; "check failed: exit 1" said nothing); the four tasks' setups and policies, unchanged — (confidence: high)
FLAGGED: two kinds of explanatory text, kept apart: `difference` states what differs between the images for the task (an environment fact, printed always); `notes` interpret an outcome and are keyed "environment:ending", so the report prints one only when that arm ended that way — chose conditional notes over always-printed explanations, because text written with the task must not describe a run that did not happen (cross-stack P005) (confidence: high)
FLAGGED: every check sends its commands' stderr to /dev/null and writes only its own one-line reason (fd 3), because the runner uses the check's first stderr line as the ending reason, and git's own "fatal: …" came first in a unit — (confidence: high)
ASSUMED: task versions go to 2: the check text changed, and a trace records task_version — (confidence: high)
ABSENT: setups and policies are untouched, so the fake agent's behaviour and RB4's predicted counts are unchanged
Verification: 48 passed (catalog + runner): every task says what differs; notes are keyed by a real arm and ending; each check, run where nothing holds, fails with exactly one reason line; timelike's git-commit-hook-rejects fails with "the commit contains a TODO line, which this repository's pre-commit hook forbids"
SCOPE: in (2 changed files)

### T023: report — the operator's first line, and every task explains its outcome (send …-080659, F001/F002)
**Started:** 2026-09-29T08:35Z | **Completed:** 2026-09-29T08:15:22+00:00 | **Coordinator**

INHERITED: T022's difference/notes and check reasons; the verdict rule and section order, unchanged — (confidence: high)
FLAGGED: per task, in this order: heading; `Tests:` (capability + what differs); `Verdict:` in words, naming what decided it; the table; then each arm's calls, its ending and reason, and a note when one matches — chose the verdict in words ABOVE the table, because the operator read the table's "failed (check failed: exit 1)" and reversed the meaning (confidence: high)
FLAGGED: the table's ending cell is now the kind alone ("failed"), with the reason told in the arm's "Ended:" line and the verdict; the failure row reads "failed commands (hung included)", because a hung call is also a non-zero exit and the report now says so rather than leaving the reader to reconcile 1 and 1 — (confidence: medium)
ASSUMED: render takes `tasks: Mapping[str, TaskText]` instead of `goals`; its only caller is the CLI; the trace schema is unchanged, so traces from 8ce6173 still render — (confidence: high)
ABSENT: no wording is generated from the timelike/vanilla difference automatically; the only causal claims are the catalog's notes, printed only when the arm ended as described
Verification: 46 passed (report units); report.py 100% line+branch; the report re-rendered from the traces the operator read (bench/out/20260929T022053Z) shows the new layout
SCOPE: in (2 changed files)

### T024: timelike-bench passes the catalog's texts; header scope follows the first line
**Started:** 2026-09-29T08:45Z | **Completed:** 2026-09-29T08:15:23+00:00 | **Coordinator**

INHERITED: report.TaskText (T023); catalog difference/notes (T022) — (confidence: high)
ASSUMED: the rule-12 header scope is a shortened form, "FAKE-AGENT BENCH PIPELINE DEMO RUN -- not a test of timelike"; the full verbatim text is the report's first line — (confidence: medium: the send asks for the old wording to be updated wherever asserted, and a 200-character scope would be cut at COLUMNS)
ABSENT: the CLI's own summary lines still give verdicts in one line per task; the explanation lives in report.txt, which the summary names
Verification: 24 passed (CLI units), including a full run over the REAL catalog through the stand-in docker whose git-commit-hook-rejects section names what is tested, the verdict with the hook-policy reason, vanilla's rejected commit, timelike's successful one, and the note
SCOPE: in (2 changed files)

### T025: validator and bats follow the new first line; every task section must explain itself
**Started:** 2026-09-29T08:55Z | **Completed:** 2026-09-29T08:15:47+00:00 | **Coordinator**

INHERITED: the verbatim first line (T023); the validator's independence from benchlib (T013) — (confidence: high)
FLAGGED: the validator compares line 1 WHOLE to the operator's text (it used a prefix), so a reworded first line fails the Docker lane — (confidence: high)
FLAGGED: the validator requires each task section to carry "Tests:", "Verdict:" and a "What happened" for both arms — a presence check, not a reading test; whether a person understands it is SC-3's re-interview — (confidence: high)
ABSENT: the bats file asserts only the header scope; the report's content is the validator's job
Verification: 35 passed (validator units, including a reworded first line and each missing explanation line); the validator passes the report re-rendered from the operator's traces; shellcheck clean
SCOPE: in (3 changed files)

### T026: docs, preview, host-lane verification
**Started:** 2026-09-29T09:05Z | **Completed:** 2026-09-29T08:19:38+00:00 | **Coordinator**

INHERITED: T022–T025 — (confidence: high)
FLAGGED: spec FR-9's first-line bullet is amended in place with a note naming the send, and FR-9a is added; Scenario 3 follows — the send leaves the spec change to us, and SC-3's text is unchanged (confidence: high)
FLAGGED: the preview is written BESIDE the report the operator read (bench/out/20260929T022053Z-preview/, from a copy of its traces) and never over it, so the artifact the D2 reading was checked against stays as it was — tasks.md T026 said "re-render bench/out/20260929T022053Z/", and that would have destroyed the evidence (confidence: high)
ASSUMED: the preview is built from 8ce6173's traces, so the checks' new reasons (T022) do not appear in it ("check failed: exit 1"); a fresh `make bench` shows them — (confidence: high)
ABSENT: nothing has run in an image since 64270f7; the mentor re-runs the lane
Verification: 592 passed, 1 skipped (under coverage); coverage 97% overall, bench 96–100% per module (report.py 100%); ruff, format, mypy --strict and shellcheck clean; the validator passes the preview
SCOPE: in (2 changed files; spec, contract and quickstart are feature artifacts, exempt)

### T027: cycle report section for send …-080659; audit-log
**Started:** 2026-09-29T09:10Z | **Completed:** 2026-09-29T08:20:15+00:00 | **Coordinator**

INHERITED: the send's host results (64270f7: make test 176/176 e2e, 575 unit; make scan PASS on three images) — (confidence: high: cited from the send, not re-run here)
FLAGGED: SC-1 and SC-2 cited as `executed` at 64270f7, with the caveat that the report text, check messages and validator changed since; SC-3 stays `unconfirmed` — (confidence: high)
ASSUMED: audit-log.md is created now with a seed row for specify's audited_against [1] and this cycle's `none` row — (confidence: high)
ABSENT: no demo_points_reached (the mentor derives them); no .implement-complete (not dispatch)
SCOPE: none — no files outside the feature's artifacts changed

## Cycle 2 — send `bridge/sends/02-rev8-20261008-095251.md` (specswarm 4.0.1-botbaubble.2.37.0)

### T028: spec § Reporting — revision 8's constraint copied in, declared
**Started:** 2026-10-08T09:58:33Z | **Completed:** 2026-10-08T09:58:44Z | **Coordinator**

INHERITED: (none — first task of the cycle); the classification is impact-analysis.md § Cycle 2 (additions only, by diff of the archived sends) — (confidence: high)
FLAGGED: the constraint is placed under § Reporting after FR-9a as a declared bullet, not as a new numbered FR — chose that over an FR-9b because slice 0 does not meet it and an FR reads as a requirement this slice claims; the bullet says so in its own text — (confidence: high)
ASSUMED: the constraint's text is copied verbatim from the send's prompt bytes (the *From Principles* list), quoted, with the revision marker moved into the bullet's lead — (confidence: high)
ABSENT: report.py and data-model.md are not edited (send § 1); no other spec line changes, because none states a verdict order (impact analysis table); the slice-1 criterion is not copied (the spec carries no later-slice criteria)
SCOPE: none — no files outside the feature's artifacts changed

### T029: decisions.md T016 — the double-counting assumption annotated as superseded
**Started:** 2026-10-08T09:59:01Z | **Completed:** 2026-10-08T09:59:01Z | **Coordinator**

INHERITED: T028's spec note names T016 as the origin — (confidence: high)
ASSUMED: an indented annotation under the ASSUMED line, rather than an edit to it, keeps the record of what was assumed at build time (append-only spirit of this log) — (confidence: high)
ABSENT: T016's other lines are untouched; the code it describes is unchanged
SCOPE: none — no files outside the feature's artifacts changed

### T030: provenance — audited_against [1] → [1, 8], one audit-log row
**Started:** 2026-10-08T09:59:49Z | **Completed:** 2026-10-08T09:59:49Z | **Coordinator**

INHERITED: T028 (the constraint now in the body, its unmet places named); the send's instruction "append 8" — (confidence: high)
FLAGGED: mode scoped with OUT_OF_SCOPE empty, appending 8 — chose that over mode none, which the installed block returns when revision 8 is listed as out of scope (verified: it yields NEW_AUDITED [1]). The command reserves an append for a revision this modification "brought into line" or that "needed no body change"; revision 8's constraint is neither in the code, by plan's ruling. Chose the send's reading (audited_against = checked and needs no regeneration, the mentor's definition; the slice-1 criterion is another slice's), and recorded the code gap in the spec, the audit-log row and not_verified so the entry cannot be read as "slice 0 meets revision 8". Raised in the report — (confidence: medium)
ASSUMED: the audit-log row's date is the clock's at writing — (confidence: high)
ABSENT: prompt_revision (1), discovery_revision (6) and source_prompt untouched; revisions 2–7 not appended (they did not change prompt 02, so they leave no hole)
SCOPE: none — no files outside the feature's artifacts changed

### T031: cycle report § Cycle 2; implement steps 10 and 9b recorded
**Started:** 2026-10-08T10:03Z | **Completed:** 2026-10-08T10:01:56Z | **Coordinator**

INHERITED: T028–T030; lane readme-c's results from `bridge/history.md` 2026-10-08T08:28:00Z and its log (TAP 393–397) — (confidence: high: read, not re-run)
FLAGGED: implement step 10j's `.specswarm/metrics.json` entry is not written — chose the send's "only .specswarm/features/<that feature>/ changes" over the command's step; step 10's output is in the cycle report instead — (confidence: high)
ASSUMED: D2's mode stays "observed by the operator", as the send says (Cycle 1 sign-off addendum) — (confidence: high)
ABSENT: no demo_points_reached (the mentor derives them); no .implement-complete (not dispatch); no host or Docker lane (only this feature's directory changed)
SCOPE: none — no files outside the feature's artifacts changed

### T032: provenance — revision 8 re-recorded as carried to 02 slice 1; audited_against unchanged [1, 8]
**Started:** 2026-10-09T04:40:57Z | **Completed:** 2026-10-09T04:40:57Z | **Coordinator** (specswarm 4.0.1-botbaubble.2.40.0)

INHERITED: Cycle 2's `scoped` row and its not_verified list of four unmet places; plan's ruling (b) — from T030/T031 (confidence: high)
FLAGGED: ran audit-append although modify's provenance row is 4 (the library skips Step 9 there) — chose the send's explicit instruction over the row's skip, because the record the send exists to make (examined, work outstanding) is only made by a row; the row's number is recorded beside it (confidence: high)
ASSUMED: the four places still contradict revision 8, re-read on `ec71f3d` (report.py unchanged since 4662060) — so carried, not scoped or full, is true (confidence: high)
ABSENT: spec.md untouched (audited_against stays [1, 8]; prompt_revision, discovery_revision and source_prompt unchanged); Cycle 2's audit-log row not edited (append-only); report.py, data-model.md and T016 not edited (02 slice 1's work)
SCOPE: none — no files outside the feature's artifacts changed

### T033: cycle report § Cycle 3; implement steps 10 and 9b recorded; reboot.md
**Started:** 2026-10-09T04:42:14Z | **Completed:** 2026-10-09T04:42:40Z | **Coordinator** (specswarm 4.0.1-botbaubble.2.40.0)

INHERITED: T032's block outputs; lane 007s1-c's results from `bridge/history.md` 2026-10-09T03:16:00Z and its log (ok 432, 433, 435, 436) — (confidence: high: read, not re-run)
FLAGGED: the Automated criteria cite lane 007s1-c at 3eba335, not re-run — chose the send's citation over a fresh lane, because 3eba335..ec71f3d changes four documentation files only (verified with git diff --name-only) and this cycle changes no code (confidence: high)
ASSUMED: D2's mode stays "observed by the operator", as Cycle 2 recorded and the send says — (confidence: high)
ABSENT: no demo_points_reached (the mentor derives them); no .implement-complete (not dispatch); no .specswarm/metrics.json entry (outside the feature directory, as in Cycle 2); no host or Docker lane
SCOPE: in (1 changed files)

---

## Cycle 4 — 02 slice 1 (send `bridge/sends/02-rev8-20261013-064725.md`), attended, specswarm 4.0.1-botbaubble.2.44.0

### T034: revision 8's verdict order in report.py (SC-6)
**Started:** 2026-10-13T07:18:36Z | **Completed:** 2026-10-13T07:20:44Z

INHERITED: (none — first task of the cycle; the order is the spec's FR-48 and data-model step 3 as corrected at plan) — (confidence: high)
FLAGGED: the order goes into slice 0's renderer now, in its own commit, before T046 rewrites the renderer for schema 2 — chose a separate revision-8 commit over folding it into the rewrite, so the carried fix is reviewable on its own (confidence: high)
ASSUMED: "failed commands" in the sentence and the table means non-zero exits, a hung call included (the table's label says so), so a hung call is one hang and one failed command, never two of either — (confidence: high)
ABSENT: the arms, harness sections and `stopped` rows (T046); the contract's slice-0 sample table keeps the old row order, under its slice-0 heading, and the slice-1 section shows the new one
Verification: tests/unit/test_bench_report.py 52 passed (rows differing in one column at a time, the pair on which the summed tiebreak and the new order disagree, the sentence quoting only table counts); ruff clean
SCOPE: in (2 changed files)

### T035: benchlib/categories.py — one category per failed call (SC-7, FR-40)
**Started:** 2026-10-13T07:20:44Z | **Completed:** 2026-10-13T07:22:21Z

INHERITED: research RB16's texts and order; the trace's exit code, hang flag and output head as the inputs — from plan (confidence: high)
FLAGGED: Adele's denial is matched by agentio's grant-envelope verdict ("nothing performed; the operator extends it"), not a word from adele's own file — chose the text the agent actually sees (the envelope agentio prints for every grant refusal) over adele's malformed-reply message, which only appears when her answer is broken (confidence: medium: this envelope is shared with any future grant-checked tool, which would also be read as network denial)
ASSUMED: exit 124 is a timeout even when it ran quickly — GNU timeout and 003's run both use 124 for their own limit, and a command exiting 124 by itself is rare — (confidence: medium)
ASSUMED: a 137 without OOM evidence is "other", not "timeout": the bench's hang flag already covers its own kill, so a bare 137 is someone else's kill -9 — (confidence: high)
ABSENT: no live-harness wording for a harness's own call timeout yet (OpenCode, Codex): added when T041's recordings show it, so the pattern is the harness's real text, not a guess
Verification: tests/unit/test_bench_categories.py 21 passed — command not found, module not found (python3, node), timeout (GNU timeout), refused and DNS failure (bash /dev/tcp, git on .invalid), a kill -9, an ls error, all produced on this host; 003's, 007's, 013's and agentio's texts read from their files; ruff clean
SCOPE: in (2 changed files)

### T036: benchlib/adoption.py — command words, timelike tools, through timelike (SC-4, FR-19)
**Started:** 2026-10-13T07:22:21Z | **Completed:** 2026-10-13T07:23:36Z

INHERITED: FR-19's rule; the shimmed names from 013 (/opt/timelike/shims) and the guarded forms from 005 — from spec and plan (confidence: high)
FLAGGED: a command inside a string (`bash -c 'run x'`) is not looked into — chose command words only, as the spec says, over parsing nested shells, because a nested string can be anything (a heredoc, a python -c) and a guess there would count calls nobody made; the report says counts come from command words (confidence: medium)
ASSUMED: `git push --force-with-lease` counts as the guarded force push — 005's guard reads any --force* (confidence: medium)
ASSUMED: `python3 -m pip` is not through timelike: it is the escape 013's announcement names, which the shim does not see — (confidence: high)
ABSENT: no detection of a tool run through `xargs`, `find -exec` or a variable (`$TOOL x`); each would need a guess
Verification: tests/unit/test_bench_adoption.py 37 passed; ruff clean; mypy --strict clean (33 files)
SCOPE: in (2 changed files)

### T037: benchlib/keyfile.py — the key file's rule and the write gate (FR-29, FR-31)
**Started:** 2026-10-13T07:23:36Z | **Completed:** 2026-10-13T07:24:35Z

INHERITED: FR-29's properties (regular, 0600, the bench user's, outside the repository, one line) and FR-31's gate — from spec (confidence: high)
FLAGGED: mode must be exactly 0600 (0400 is refused too) — chose the send's literal "mode 0600" over "no group or other bits", so the rule is one a person can check by eye (confidence: medium: 0400 is as safe, and an operator who uses it is told exactly what to change)
ASSUMED: an absolute BENCH_KEY_FILE only — a relative path would resolve against whichever process reads it (cross-stack P002), and run.sh and the driver are two processes — (confidence: high)
ASSUMED: the gate matches the raw value only; JSON escaping cannot change an OpenRouter key (letters, digits, '-' and '_') — (confidence: medium)
ABSENT: no check of the value's shape (sk-or-…): a key OpenRouter rejects ends its run stopped (key-rejected, FR-37), which is the provider's answer and not a guess
Verification: tests/unit/test_bench_keyfile.py 20 passed (every refusal checked for the value); ruff clean; mypy --strict clean (34 files)
SCOPE: in (2 changed files)

### T043: benchlib/plan.py — the plan before any request, the estimate, the dated-model rule (FR-27, FR-34)
**Started:** 2026-10-13T07:24:35Z | **Completed:** 2026-10-13T07:25:18Z

INHERITED: RB18's per-turn figures (20 000 in, 1 000 out) and the base prices OpenRouter lists (.32, .96) — from research (confidence: medium: the figures are an assumption about two harnesses' prompts, stated as one in the plan)
FLAGGED: the estimate uses the base price, not the cheaper listed UTC hours — chose the higher, so the printed figure is an upper bound on price (confidence: high)
ASSUMED: a dated id ends in 4 or 8 digits after its last '-'; OpenRouter's own ids use both (`-0813`, the canonical `-20260813`) — (confidence: medium)
ABSENT: no live price lookup — the plan needs neither the network nor a key (--dry-run), so the price comes from pins.env
Verification: tests/unit/test_bench_plan.py 11 passed; ruff clean; mypy --strict clean (35 files)
SCOPE: in (2 changed files)

### T038: trace schema 2 (contracts/trace-schema.md) and the validators
**Started:** 2026-10-13T07:25:18Z | **Completed:** 2026-10-13T07:33:06Z

INHERITED: categories (T035) and the gate (T037) are used by the trace module itself: category values are checked against categories.CATEGORIES, and write_trace writes through a Gate — (confidence: high)
FLAGGED: schema 1 is refused, not read — chose a refusal naming the revision that re-reports it over a v1 reader, because a v1 trace has no arm and no categories and a report that guessed them would present a guess as measured (confidence: medium: an operator with an old bench/out run must check out slice 0 to re-report it)
FLAGGED: field kinds are explicit tables per object, replacing slice 0's derivation from dataclass annotations — that derivation knew str/int/bool only, and lists, a float and an int map would each have needed a special case in it (confidence: high)
ASSUMED: models_answered may be empty (a run that ended before any answer, and every fake run) while every other identity string stays non-empty — (confidence: high)
ASSUMED: the runner's fake path writes arm "not-told" for the timelike environment until T044 adds the told arm; nothing has been placed for it, so "not told" is the truth of those runs — (confidence: high)
DEFERRED: the e2e validator's file naming (<task>--<harness>--<arm>.json) and its three-arm count — moved with the runner's naming in T044, so the validator never expects files the runner does not yet write
ABSENT: the report does not yet show categories, arms or spend (T046); the runner's live path is T044
Verification: tests/unit -k bench 550 passed (trace 135: every schema-2 rule one violation at a time, spend recorded or absent, the gate on write; the validator's new mutations: schema 1, arm vs environment, a category on a success, a stopped ending without a cause); ruff clean; mypy --strict clean (35 files)
SCOPE: in (6 changed files)

### T039: benchlib/standin.py — the model stand-in (FR-47); fakeagent.happy_path; categories.PROBES
**Started:** 2026-10-13T07:33:06Z | **Completed:** 2026-10-13T07:35:26Z

INHERITED: the protocol shapes each harness was seen to send in research RB12/RB17 (chat completions for OpenCode, Responses for Codex; OpenCode's title request offers no tools) — (confidence: high: observed, not documented)
FLAGGED: progress through the script is read from the request (the count of tool results it carries), not kept per connection — chose stateless over a session table, because both harnesses resend the whole conversation and a retry then lands on the same step (confidence: high)
FLAGGED: the stand-in's script is the task's happy path (fakeagent.happy_path), not a walk that branches on outcomes — OpenCode sends the model a call's output but not its exit code (RB17), so branching would work under one harness and not the other (confidence: high)
ASSUMED: every answer reports usage.cost, as OpenRouter's always does (its usage-accounting page), defaulting to 0.0 so a stand-in run's spend is a real zero, labelled as the stand-in's — (confidence: high)
ABSENT: no Anthropic messages route: no harness the bench runs speaks it (Claude Code is excluded, FR-21)
ABSENT: the probe commands (categories.PROBES) are data here; they run in T045's `categories --probe` and in e2e
Verification: tests/unit/test_bench_standin.py 8 passed (each protocol, streamed and not, over real HTTP on loopback; faults; the happy path of every catalog task); fakeagent and categories units still pass (59 with the stand-in's); ruff clean; mypy --strict clean (36 files)
SCOPE: out — bench/benchlib/fakeagent.py (1 of 4 changed files) (task has FLAGGED: yes)

### T040: benchlib/relay.py — forwarding, streaming, accounting, caps (FR-25, FR-26, FR-33, FR-36)
**Started:** 2026-10-13T07:35:26Z | **Completed:** 2026-10-13T07:37:47Z

INHERITED: the stand-in (T039) as the upstream in every unit; OpenRouter's usage shape (always present, cost in it) from research RB15 — (confidence: high)
FLAGGED: Authorization is forwarded unchanged and never recorded (the send's route); the alternative, the relay adding it, is FOR-MENTOR Item 25 and not built — (confidence: high)
FLAGGED: a cap answers 400 and keeps answering 400 for the rest of the run without reaching upstream — chose a hard stop over relying on how each harness reacts to the 400, which is not yet verified against the real binaries (recorded as T041's check) (confidence: medium)
ASSUMED: a cost that is missing, negative or not a number is named as unknown (cost_unknown) and never counted as 0 or estimated — (confidence: high)
ASSUMED: one run at a time per relay (runs are sequential, FR-1's order); accounting for a request still in flight when a run ends stays with that run's object — (confidence: high)
ABSENT: the generation-stats lookup is a function (generation_cost) the driver calls after a run; its live behaviour is not testable without a key (not_verified)
ABSENT: no TLS between harness and relay: the internal network has no other member (FR-25)
Verification: tests/unit/test_bench_relay.py 15 passed (stream and plain, chat and Responses; turns only for requests offering tools; the turn cap and the spend cap across runs; 429/500/401 passed through and counted; an unreachable upstream as 502 'unreachable'; a missing cost named; the key's header reaches upstream and appears in no accounting); ruff clean; mypy --strict clean (37 files)
SCOPE: in (2 changed files)

### T041: transcripts recorded from the pinned harnesses (tests/fixtures/transcripts/)
**Started:** 2026-10-13T07:37:47Z | **Completed:** 2026-10-13T07:42:27Z

INHERITED: the stand-in (T039) and the relay (T040) as the path the harness talked to; the harness binaries from research RB12, checked against npm's sha512 — (confidence: high)
FLAGGED: the recordings' scratch paths were rewritten to /home/agent/task and /home/agent, and the README says so — chose a stated, single rewrite over committing the host's paths, which name the host user and would also have been checked against the deny-list (confidence: high)
FLAGGED: two texts added to the categories from what the harnesses really printed: OpenCode's own call timeout ("shell tool terminated command after exceeding timeout") and git's "Failed to connect to … Couldn't connect to server" — chose to match the recorded text over guessing harness wording earlier (T035's ABSENT) (confidence: high)
ASSUMED: Codex stopping at the first 429 is Codex's own behaviour, measured as it is; no retry setting is added for it (each harness runs with its defaults, so the two arms of a harness see the same retries) — (confidence: medium: live, Codex rows may stop on a 429 more often than OpenCode's; each is named)
ABSENT: no recording against OpenRouter itself (no key on this side); the mentor's first live run is that tier (llm-apis Q001)
ABSENT: no memory-kill recording: the host run has no memory limit; the probe produces it in the lane
Verification: record.py ran both harnesses through four scenarios (exits: pass 0/0, failures 0/0, turn-cap 1/1, rate-limit 0/1); deny-list PASS over the 29 files (P1–P7 0/0); no host path left; categories 23 passed with the two recorded texts
SCOPE: in (32 changed files)

### T042: benchlib/transcripts.py — the OpenCode and Codex parsers (FR-44)
**Started:** 2026-10-13T07:42:27Z | **Completed:** 2026-10-13T07:44:07Z

INHERITED: T041's recordings, and research RB17's reading of each harness's output — (confidence: high: the tests run on the harnesses' own files)
FLAGGED: Codex is read from its rollout file, not from exec --json — chose the file with model-response boundaries (token_usage_record) so a Codex turn is a model response, as OpenCode's step is; stdout is read only for the errors Codex printed (confidence: high)
FLAGGED: a non-shell tool call (an edit, a read, Codex's update_goal) is a call in the trace, with command "[tool] …" — chose to count every tool call the harness made, as the "tool calls" row says, over counting only shell commands; adoption still counts command words only (confidence: medium)
ASSUMED: an exit code the harness did not report is -1 (NO_EXIT), never 0, and the call is failed; OpenCode's own-timeout text marks the call hung — (confidence: high)
ASSUMED: both harnesses merge stdout and stderr; the merged size goes in stderr_bytes beside the merged head, and stdout_bytes is 0 (Assumption 11, output_streams: merged) — applied in T044 — (confidence: medium)
ABSENT: no parser for Claude Code (excluded, FR-21)
Verification: tests/unit/test_bench_transcripts.py 17 passed on the recorded transcripts (pass, failures with exits and categories per call, OpenCode's own timeout, both harnesses' cap error, Codex's 429, turns from response records) and on empty, non-JSON, truncated and foreign input; ruff clean; mypy --strict clean (38 files) — after a fix: the first commit of this task went in before mypy's result was read, with 31 narrowing errors; amended before anything else was built on it
SCOPE: in (2 changed files)

### T044–T046: the runner's cells and live path, the CLI, the report for schema 2 (one integration)
**Started:** 2026-10-13T07:44:23Z | **Completed:** 2026-10-13T08:08:30Z

INHERITED: the parsers (T042), relay and stand-in (T039–T040), categories, adoption and the gate (T035–T037), trace schema 2 (T038) — (confidence: high)
FLAGGED: T044, T045 and T046 are built and committed together — chose one integration over three commits because the told and not-told traces share an environment, so the runner's cells broke slice 0's report pairing and the CLI's call at once; three separate commits would each have left the suite red (confidence: high)
FLAGGED: BENCH_KEY_FILE is itself key-shaped under FR-12's rule (it has a KEY part), so every live run refused itself; a live run now accepts exactly that one name, and a fake run refuses it with its own message — recorded in spec FR-32 and the CLI contract, declared (confidence: high)
FLAGGED: the tool is declared destructive, so agentio adds --dry-run ("show the plan, change nothing") and conform's C2 holds; it starts and removes containers and, live, spends money (confidence: high)
FLAGGED: the plan printed before any request goes to stderr — stdout carries the output contract, and a plan line there would break --json; the same lines head the final result (confidence: high)
FLAGGED: a live run's ending follows data-model § Live run result in that order, with one deliberate exception: a passing check makes the run completed even if the harness exited non-zero or the provider's last answer was an error, because the goal was reached (confidence: medium)
ASSUMED: Codex's own per-call limit is not known (none was observed), so its traces record the run limit as the call limit; OpenCode's is 120 s, as its transcript reported — (confidence: medium)
ASSUMED: the relay's port is fixed (8417) inside the per-invocation network; nothing else listens there — (confidence: high)
DEFERRED: the CLI's live path end to end (network, harness container, relay, real harness binaries) runs only in the Docker lane (T050); on the host it is driven at the runner level with the real relay and stand-in and a recorded transcript (tests/unit/test_bench_live.py)
ABSENT: no unit for `categories --probe` on the host: the fake docker runs commands locally, where the memory probe would allocate 512 MiB for real; the probe is T051's, in the lane
ABSENT: the e2e validator gained `verdicts` (revision 8's ranking recomputed independently) and `adoption` (recounted per arm) here rather than in T049, because its unit fixture broke with the file naming
Verification: tests/unit -k bench 612 passed (runner 26, live 19, report 33, CLI 34 incl. conform, validator 43); ruff and format clean; mypy --strict clean (39 files)
SCOPE: out — bench/benchlib/executor.py, tests/unit/fakedocker.py, tests/unit/test_bench_runner.py, tests/unit/test_bench_live.py (4 of 13 changed files) (task has FLAGGED: yes)
