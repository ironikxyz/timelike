# Cycle report — maintenance: the lane (a parallel lane, a partial lane)

> Append-only. One section per cycle, headed by the send it built. A maintenance send has no prompt and
> no feature directory.

## Cycle 1 — bridge/sends/maint-lane-speed-20261015-062546.md

**Written:** 2026-10-15T07:01:41Z (read from the clock). Built by hand on `maint/lane-speed`, from `master` at
`5b9a347` (the send's base; `master` had not moved). No specswarm command was run; the session runs specswarm
**2.44.0**. **Pushed nothing; merged nothing.**

### Group A — cited from `.implement-complete`

Group A: not applicable — no marker on this path

### Group B — copied from the send

| Field | Value |
|---|---|
| source_send | bridge/sends/maint-lane-speed-20261015-062546.md |
| source_prompt | none (maintenance; the source is the operator, 2026-10-14: the Docker lane's time per slice) |
| prompt_revision | none |
| discovery_revision | 15 |
| slice | none |

### Group C — written by the code instance

**delegations:** three read-only survey agents (general-purpose Explore), one per third of the 86 e2e files, each
asked for every way a file could meet another file running beside it, with file:line citations and a verdict.
Their findings are below, re-checked where a verdict rests on them (the `view` process name, the six
`remove_stale_throwaways` callers, the `/tmp/json_fields.py` pair, the `~/.local` writers and readers).

**The commits** (`master..maint/lane-speed`): `d732eda` item 3; `f7521d6` parts 1 and 2 (the lane, its units, pins, the timed marker, README); then this report with reboot.md. Each names the send.

#### Part 1a · e2e in parallel

- **`E2E_JOBS`** (tests/run.sh). `1` is the serial lane exactly: the runner gets `… --timing tests/e2e`, the same
  argv as before, no lock variable is set, and every helper takes its old branch (a unit asserts the argv).
  Above 1: `bats --jobs N --no-parallelize-within-files`, so files run side by side and each file's own cells stay
  in sequence.
- **GNU parallel** is already in the pinned runner base, `bats/bats:1.14.0@sha256:5322b877…`: its amd64 image's
  build history installs `parallel` (`apk add --no-cache parallel ncurses`), and its layer `sha256:1d163999…`
  holds `usr/bin/parallel`, `usr/bin/perl` and an apk record `parallel 20260322-r0`. I read all of this from Docker
  Hub without Docker, by index digest, and fetched the layer by its digest. So it is pinned by that image digest,
  as everything else in the image is, and nothing was added to pins.env or tests/runner/Dockerfile. The runner image
  is unchanged. `make scan` does not scan the runner image (scan/scan.sh names no runner), so "keep its scan green"
  had nothing to keep.
- **The lock** (`tests/e2e/lane.bash`, new): each file holds a lock on `tests/out/.e2e-lane.lock` while it runs.
  The lock is shared, or exclusive for a serial file. A turnstile in front of it gives a waiting exclusive holder
  its turn. It is taken once per file, in `bats-exec-file`, recognised by the bottom of `BASH_SOURCE`. It is not
  taken in `bats-gather-tests`, which sources every file in one process to count tests, nor again in
  `bats-exec-test`. `helpers.bash` sources it, and the three files that load no helpers load it
  (`failed-commands-…`, `speedup-bench`, `the-same-task-catalog-…`). A unit asserts that every e2e file takes it.
  - **Exercised:** with bats-core 1.14.0's own source and the runner image's GNU parallel 20260322 (extracted from
    that layer), on dummy files. Shared files ran together; each exclusive file ran alone after them; the TAP kept
    plan order under one `1..N`; with no lock variable set, nothing was taken.
- **Order** (`tests/e2e/lane.conf`, new): in a parallel lane, the `first` files (longest first, since the
  longest file sets the floor), then the rest by name, then the `serial` files by name. The plan's `1..N` and the
  cell names are the same as in the serial lane; the cells' numbers differ, because the order does. run.sh refuses
  a lane.conf that names a missing file (a unit), so a renamed serial file cannot quietly run beside others.
- **Output:** unchanged in shape. One TAP stream with `1..N` and `ok N` lines in plan order (GNU parallel's
  `--keep-order`, used by bats), the same `step X: rc` lines, `report.xml`, and `summary.json` with five added
  keys (`scope`, `e2e_files`, `e2e_jobs`, `unit_jobs`, `steps_together`).

**Every file marked serial, and why** (lane.conf carries the same reasons):

| File | Why it runs alone |
|---|---|
| `a-bare-python-package-install-…` | installs into the shared `~/.local` by design, and its check runs `find / -xdev` for anything new outside the home directory, so any neighbour's write fails it |
| `adele-rejects-malformed-grant-…` | a 10 s window that includes the throwaway Adele's `docker run`: a malformed file must exit inside it and a valid one still serve at its end |
| `announcement-at-most-60-lines-…` | waits at most 10 s for each throwaway's entrypoint; placement has taken 11 s under host I/O load (the file's own note) |
| `command-not-installed-…` | requires nothing new anywhere under `$HOME` and the listed commands absent from PATH; neighbours' shells and installs write there |
| `failed-commands-are-grouped-…` | each probe has the bench's 5 s call limit, and cold starts in a new 64 MiB container must finish inside it |
| `hook-past-its-time-limit-is-killed` | `assert_within 8` and `7` for 3 s and 2 s hook limits, timed from the runner |
| `hooks-under-env-i-…` | `assert_within 7` for a 2 s limit plus its 5 s grace |
| `installing-a-package-name-absent-…` | `npm install -g` into the shared `~/.local`, and it requires nothing else new there |
| `installing-a-package-whose-newest-release-is-younger-…` | requires nothing new in `~/.local` or the agent's site-packages but its own cell's |
| `no-credential-held-by-adele-appears-in-agent` | tars the whole filesystem under a 120 s cap; under load the cap could cut the search short and pass it without looking |
| `run-backgrounded-child-…-within-2-seconds` | the verdict within 2000 ms |
| `run-exceeding-its-timeout-…` | under 9000 ms for a 2 s timeout plus its 5 s grace |
| `symbols-def-…-under-2s-warm` | a warm `def` under 2 s, CPU-bound |

No budget was raised, and no cell was removed, skipped, weakened or moved.

**Every shared resource found, and what was done with it:**

| Resource | Where | Done |
|---|---|---|
| `kill_strays`: `pkill -KILL -x` by pager/editor name over the whole agent container. It is called by `exec_in` on any timeout and by four teardowns. timelike's `view` tool is a script, so its process is named `view`, which is on the list | `helpers.bash` | in a parallel lane, `exec_in` passes `TL_E2E_FILE=<file>`, and `kill_strays` kills only processes whose `/proc/PID/environ` carries it. A serial lane is unchanged |
| `assert_no_pager_or_editor`: `pgrep -x` over the whole container (`git-log-…`, 11 calls) | `helpers.bash` | the same scoping (`pager_editor_procs`); serial unchanged |
| `remove_stale_throwaways`: removes every container labelled `timelike.test.throwaway`, which includes other files' live `pyq`, canary, Adele and throwaway containers. Six files call it from `setup_file` | `helpers.bash` | a no-op in a parallel lane; run.sh removes the stale ones once, before the first file starts (a unit) |
| `/tmp/json_fields.py`, copied in place (`cat >`) by two files (`conformance-…`, `run-exit-equals-…`), so one could read the other's half-written copy | `copy_into_container` | in a parallel lane, written beside the destination and renamed into place; serial unchanged |
| `~/.local` and `$HOME`: installs and whole-home "nothing new" checks | five files | their files run alone (serial, above) |
| Machine time: tight elapsed-time bounds | seven files | run alone (serial, above) |
| Container, network and volume names; ports; compose | all 86 | none fixed: each cell's are mktemp'd or random (port 0), no file brings compose up or down, and the bench's task containers are unnamed. Nothing to do |
| `bench/out/e2e`, `tests/out` | the bench and categories files | each file writes its own names (`run-<sha12>-$$`, `live-…`, `probe.*`); nothing to do |
| The default session `/tmp/timelike/default` and state root `/var/lib/timelike` | cells that set no session or state root | appends only, and no file reads them; left as is |
| Pids written by fixtures, killed in teardown (usually already dead) | `hooks-under-env-i-…`, `run-exceeding-…`, `run-backgrounded-…` | all three are serial files, so pid reuse cannot reach a neighbour |
| The services cells' `free_port` (port 0, released, then used) | the services files | a neighbour could take the port in between; low odds, left as is and listed under not verified |

#### Part 1b · unit in parallel

- **pytest-xdist 3.8.0** and **execnet 2.1.2** (its runtime dependency), pinned in pins.env like `PYTEST_VERSION`
  and fetched by the pinned uv with it. They are added only when `UNIT_JOBS > 1`. `UNIT_JOBS=1` is today's command
  exactly (a unit asserts the argv).
- **The `timed` marker** (pyproject.toml): 16 tests whose elapsed-time bound is tight enough that neighbours could
  move it. They are the start-up p95 and the tests asserting under 2, 3, 4, 5, 6 or 8 s, or 9–15 s. Above 1, the
  step runs `-n UNIT_JOBS -m "not timed"`, then `-m timed` serially, both into `tests/out/unit.txt`; `startup.json`
  is read from it as before.
- **Measured on this host** (56 cores, the same machine as the Docker host; timelike's CPython 3.14.8 in a scratch
  venv, outside the image, so these are not the lane's figures). The whole suite with xdist (2510 to 2526 tests as
  this cycle added units):

  | Workers | Result | Seconds | Host otherwise |
  |---|---|---|---|
  | 1 (the host lane, Addendum 3) | 2505 passed | 496 | — |
  | 8 | **2 failed**, 2508 passed | 314 | busy: my other runs beside it |
  | 8 | 2526 passed | 120 | quiet |
  | 16 | 2510 passed | 135 | quiet |
  | 16 | 2526 passed | 134 | quiet |
  | 24 | 2510 passed | 100 | quiet |
  | 32 | 2510 passed | 106 | quiet |

  The timed tests alone, serially: 16 passed, 47 s (start-up p95 79.8 ms, with the host busy).
- **The two failures under load** (8 workers, busy host): `test_bench_runner::test_totals_and_endings_match_rb4[git-commit-hook-hangs-timelike]`
  (`git commit --no-verify hung`) and `test_bench_cli::test_run_writes_three_traces_per_task_and_the_report`. Both
  drive real git through the bench under a **2 s call limit** (`runner.Limits(call_s=2, …)`, `--call-limit 2`), and
  a commit through the hook dispatcher took longer than that. They are not marked `timed`: the six `full_run` tests
  alone take about 180 s serially. Instead the unit step never runs beside e2e (1c). Quiet, all four worker counts
  passed. This is the unit step's one known load-sensitivity, and the proof lanes will show whether 16 workers on a
  quiet machine hold.
- **Default `UNIT_JOBS=8`:** quiet, 8 workers took 120 s and 16 took 134–135 s; 24 and 32 took 100–106 s on the
  smaller suite. The differences are within the noise of these few runs, and the suite is bounded by its longest
  tests (the bench CLI's full runs). Of the near-equal counts I chose the lowest, because fewer workers load the 2 s
  bench units less.

#### Part 1c · steps side by side

- **gounit runs beside e2e** (when `E2E_JOBS > 1`, `LANE_STEPS_TOGETHER=1` and the host has `flock`). It holds the
  lane's lock shared, so e2e's serial files still run alone. Its output and its `step gounit: rc` line are printed
  when it is collected, after e2e. Without `flock` it runs after e2e, and `summary.json` says why.
- **unit does not run beside e2e.** Its bench units failed under host load (above). So the unit step always runs
  after e2e, on a quiet machine.
- **I did not try it on the Docker host.** The send's rule is "if running them together makes any of them flaky,
  keep them in sequence and say so". Unit was kept in sequence on the strength of the host measurement, not of a
  lane.

#### Part 2 · the partial lane

- **`make test-partial E2E_FILES="a.bats b.bats"`**, a new target; a variable on `make test` was the other choice.
  It runs build, up, runner and benchimg as a full lane does, only the named e2e files (with that subset's `1..N`;
  in parallel, lane.conf's rule over the subset), and all of unit and gounit.
- **It cannot pass for a full lane:** its first line is `scope: partial — e2e files: …`, and `summary.json` has
  `"scope": "partial"` and `"e2e_files"`. A full lane's first line is `scope: full`. `make test`'s recipe is now
  `@`-prefixed, so make's own echo of the command no longer comes first.
- **Refused before anything is built** (exit 2, naming the problem; a unit for each):
  - an empty list;
  - a name that is not a `.bats` file in tests/e2e (it is named);
  - a name given twice;
  - E2E_FILES set on a full `make test`, which never narrows itself;
  - an unknown `LANE_SCOPE`;
  - a job count that is not a positive integer.

#### Item 3 · `make bench-live` and the environment

- **The fix** (Makefile): the four operator-set values in pins.env (`BENCH_MODEL` and its three price values) are
  noted from the environment before `include pins.env` and put back after it.
  - An empty environment value counts as unset, and a make command-line value still wins.
  - `?=` in pins.env would have done it, but pins.env is also sourced as shell by tests/run.sh and scan/scan.sh,
    where `?=` is a syntax error.
  - The caps (`BENCH_TURN_CAP`, `BENCH_SPEND_CAP_USD`) are not in pins.env, so the environment always reached them.
- **The plan says where each value came from.** make sets `BENCH_<NAME>_SOURCE` (`pins.env`, `the environment`
  or `the make command line`), and bench/run.sh forwards it. The model line now reads `model: <id>, from <source>
  (<prices>)`, and a new `prices from:` line follows it. Run outside make, nothing records a source, and the plan
  says so, or names the bench's own default when BENCH_MODEL is unset.
- **Proved by units:**
  - `tests/unit/test_makefile_bench_values.py` runs the real Makefile through GNU make `--eval` for four cases:
    unset, environment, empty, command line. It needs make on PATH: the host lane has it, the agent image does not,
    and there it is skipped with that reason.
  - a dry-run CLI unit, and plan units, including a check that both lines fit agentio's 200-column cut. A first
    form, with the sources at the end of the model line, was cut there.

#### Expected time, and what caps it

**No lane has been run.** This session has no Docker. I estimated the parallel e2e step from lane 02s1-d's own
per-file times in `tests/out/report.xml` on `c09f94a`: each file's duration is the gap between consecutive JUnit
timestamps. The estimate schedules lane.conf's order onto N slots, with the serial files alone at the end. It is an
estimate, not a measurement:

| E2E_JOBS | e2e, estimated |
|---|---|
| 4 | about 953 s |
| 6 | about 771 s |
| 8 and above | about 752 s |

- **What caps it at about 752 s** is two things that parallelism cannot shorten. One is `git-log-diff-commit-…`
  (362 s), whose 50 cells must stay in sequence: they read the container's pager processes, scoped to the file.
  The other is the serial files, 390 s in all, of which no-credential is 113 s and hook-past 94 s.
- **Unit after it:** about 120 s spread (8 workers) plus about 47 s timed on this host (the lane's own unit step in the image
  took 756 s serially, against 496 s here). So e2e and unit together come to about 15 minutes if the Docker host
  matches the estimate. The send's goal is under about 15.
- **Default `E2E_JOBS=8`:** chosen from that estimate, not from runs on the Docker host. The send asks for runs on
  the Docker host and a record of them, and this session cannot run any. The cheapest measurement is the proof
  lanes themselves, at `E2E_JOBS=4`, `8` and `12`; `summary.json` records each step's seconds. If 8 is flaky or no
  faster than 6, the default should move. That is the mentor's call, on the runs.

#### What was not verified

- **Nothing here has run in Docker.** Not the parallel lane, the lock under busybox `flock`, the scoped process
  checks inside the agent container, gounit beside e2e, or the partial lane. The units drive tests/run.sh with a
  stand-in docker and make, and check what it decides and hands on, not what the cells do side by side.
- **Busybox `flock`** (the runner is Alpine) was not run. The prototype used util-linux `flock`; the runner's
  `/usr/bin/flock` is busybox's, present in the image's base layer, and takes the same `-s`, `-x` and fd forms.
- **The lock across the bind mount:** the host's `flock` (gounit) and the runner's lock the same file through the
  `tests/out` mount. That holds on one Linux kernel, not on a remote `DOCKER_HOST`, where the lane's mounts would
  not work anyway.
- **That every cell passes side by side:** the survey reasons about each file, and the mentor's three parallel
  lanes test it. Known residual risks, none of them marked serial:
  - the services files' port-0 race;
  - `peer-agents-…` running 20 tool calls under the 30 s exec limit;
  - `view-directory-…` creating 10,000 files per cell under a 30 s exec;
  - `install_uv_tool_wrappers`' PyPI fetches, four files at once;
  - Docker daemon latency from many `pyq` containers, counted in every runner-side `assert_within`.
- **That `TL_E2E_FILE` in a parallel lane's command environment changes no cell's result:** no cell compares the
  whole environment (I checked by grep); `a-bare-…` counts one pattern that the name does not match.
- **The unit figures are this host's**, outside the image.
- **README:** the command reference is current (14 tools). The Development section gained `make test-partial` and
  a passage on the lane's parallelism, and the live-run passage gained the model override; they are marked. The 02
  slice 1 marks were cleared, as the standing rule says.

**changed_other_features:** 002's bench, by item 3. These are the plan's model line and a new `prices from:` line;
`bench/run.sh` forwards four more names, none key-shaped; and the Makefile now honours the environment. No
acceptance criterion's text changed. The 002 records (`contracts/bench-cli.md`) do not quote the model line.

**process_failures_recorded:**
1. A dry-run unit failed first: the sources at the end of the model line passed agentio's 200-column cut. The
   sources were moved to their own line, and a unit now checks both lengths.
2. The lane units first failed on `E2E_FILES: unbound variable` under `set -u`, in the partial-lane check; fixed.
3. A first unit measurement at 8 workers ran beside my other runs and failed two load-sensitive tests (above). It
   is kept in the table as the evidence for 1c.

**retired_prompts_seen:** none.

#### Host lane

`make test-host` on timelike's CPython 3.14.8 in a scratch venv, over this tree, 2026-10-15T07:03:38Z–07:13:05Z
(read from the clock): **rc 0**. pytest tests/unit: **2527 passed, 12 skipped** (530 s, serial; the host lane runs
no xdist). `test_env_layer.sh` 60 of 60; `test_shell_env_hook.sh` 57 of 57; `test_command_not_found.sh` 33 of 33.

Other checks:
- ruff check and format: clean (123 files);
- mypy `--strict`: clean (39 files);
- shellcheck over the Makefile's whole list, now with `tests/e2e/lane.bash`: clean;
- `scripts/readme_reference.py --check`: current, 14 tools;
- the deny-list over the working tree (567 files, `tests/out/` aside) and the three commit messages: PASS, P1–P7 0/0.

#### For the mentor

- **The proof lanes, on one unchanged HEAD**, as the send lists them:
  1. `E2E_JOBS=1 UNIT_JOBS=1 make test`, the serial baseline;
  2. `make test` three times, at the defaults;
  3. `make test-partial E2E_FILES="<two files>"`, and one with a misspelt name, which is refused with exit 2
     before anything is built.
- **The default `E2E_JOBS=8` rests on an estimate, not on runs.** If the three parallel lanes are green, their
  times are the first measurement of it. Lanes at 4 and 12 would show whether it should move.
- **Watch first** (the risks listed under not verified): any `not ok` in a serial-tail file, the services files,
  `peer-agents-…`, `view-directory-…`, or the bench units in `unit.txt` (`test_bench_cli`, `test_bench_runner`).

## Cycle 1, Addendum 1 — bridge/feedback/maint-20261015-115635-lane-speed-proof-parallel-lanes-fail.md

The mentor's proof chain on `17efa2f` (2026-10-15T08:46:28Z–11:14:19Z): the serial lane (689 of 689), the two
partial lanes and `make scan`/`make lint` passed, and the three parallel lanes at the defaults failed: 30, 6 and 4
`not ok`, and 681, 676 and 676 TAP lines against `1..689`. This addendum takes the feedback's four items in order.
Read from the logs the feedback names (`bridge/.make-test-ls-*.log`, read only), from `bench/out/e2e/` on this host,
and by two read-only survey agents (below). Nothing here has run in Docker. **No criterion's budget was raised, no
cell was removed or weakened, and no file was added to lane.conf's serial group.**

### Group B — copied from the send

Unchanged from Cycle 1: `source_send` `bridge/sends/maint-lane-speed-20261015-062546.md`; no prompt, no feature,
no discovery revision of its own (a maintenance send); no slice. The instruction for this addendum is the
feedback file named in the heading.

### Item 1 · the bench's output, shared across lanes

**What was shared.** `bench/out/e2e`, one host directory for every lane. Cycle 1's table said "each file writes its
own names" (`run-<sha12>-$$`, `live-…`, `probe.*`). That is true within one lane and false across lanes: `$$` is the
bats process's pid in a fresh runner container, so it repeats, and par2 and par3 made the same names as par1 on the
same commit (`run-17efa2f09b1c-312`, `live-17efa2f09b1c-313`). The bench then refused the non-empty `--out`. The
fixed names `run.stdout`, `run.stderr` and `run.rc` were also one set for every lane, so par2 and par3 overwrote
par1's. Cycle 1's survey reasoned within one lane and never across two on one commit; that is its gap.

**What changed:**
- `tests/run.sh` gives each lane its own directory, `bench/out/e2e/<the lane's stamp>`, the same stamp as
  `tests/out/run-<stamp>.log`. It is mounted at the same path and passed as `BENCH_E2E_OUT`, as before. The serial
  lane gets the same change; nothing else in its command moves.
- `speedup-bench.bats` and `the-same-task-catalog-….bats` record the bench's exit status in `setup_file` instead of
  failing there. Their first cells already judge `run.rc` and `live.rc` and print the bench's stderr, so a failing
  bench now fails those cells, with its reason, and the file's other cells still report.
- **Accounting for skipped cells:** a `setup_file` can still fail for other reasons (`stamp_check`, a fixture copy),
  and bats then prints one `not ok N setup_file failed` in place of the whole file. `run_e2e` now counts the TAP
  stream against its plan when bats ends, prints `e2e: R of PLAN cells reported, F of them not ok; U not reported:
  S setup_file failed, each in place of its file's cells`, and fails e2e when any went unreported. A complete
  stream prints `e2e: N of N cells reported, F not ok`. Answering the feedback's question: yes, the lane should
  account for them, and now it does, in the log line beside e2e's rc.

**par1's own bench failure: the reason is lost.** It came before any collision existed, and its stderr was
overwritten by par2. What remains on this host is `bench/out/e2e/run-17efa2f09b1c-312/traces/`: 9 traces, the first
three tasks in all three arms. The last one is `git-commit-hook-hangs--fake--told.json`, written 09:44:25Z. Its three
runs took 121, 60 and 67 s (vanilla, not told, told): the 120 s call limit and timelike's 60 s hook limit, as in a
serial lane. So the
run stopped at or during the fourth task (`git-commit-hook-rejects`), and no trace or log says why. I kept the
directory. The next failure will print its stderr into the TAP.

### Item 2 · `git-log-diff-commit-rebase-exit-within-20-seconds.bats`

**What it shared:** nothing with a neighbour. It shared the host's load, through a fixture whose bound was the
exec's, and whose failure went unseen.

**The cause:**
- Each cell first builds its repository with `fixtures/sc1-repo.sh`: 60 commits through `exec_plain`, under
  `RUN_TIMEOUT`'s 30 s. In a serial lane that takes about 5 s. Under the parallel lanes' load, a commit took 1–5 s
  (par1's `git log` output shows 12 commits from 09:39:06 to 09:39:31), so the fixture ran past 30 s.
- The runner's busybox `timeout` stopped the docker CLI, which can exit 0 when stopped that way (helpers.bash
  already says so of `exec_in`). `exec_plain` returned that status, and the fixture went on committing inside the
  container, where a stopped CLI does not reach it.
- The cell then ran its command against the part-built repository: `history commit 12` as the newest commit,
  `HEAD moved: 32 commits`, `nothing to commit`, `no rebase in progress`.
- **No cell went over its 20 s.** All 19 failing cells in the three logs failed on content. Their timed commands
  took 0.11–2.16 s (`got 128 after …`). The 30.7–37.1 s in their `# in` lines is the whole cell, the fixture's 30 s
  included.

**What changed:**
- `exec_plain` (helpers.bash) now fails with 124, naming its bound and the command, whenever it reaches that bound,
  whatever status the stopped CLI left. That is `exec_in`'s rule, applied to the setup and control reads, so no
  fixture anywhere can be cut short and pass as finished.
- `prepare` in this file gives the fixture its own bound, 300 s, as `install_uv_tool_wrappers` already does for its
  warm-up. That is test plumbing, timed by no criterion. The criterion's 20 s is `run_in`'s `assert_within 20` on
  the command itself, and it is unchanged.

**Why it stays in the parallel group:** its timed commands used at most 2.2 s of their 20 s under the heaviest load
seen. The failures were the fixture's, not the budget's. It is 362 s of the lane's floor, so moving it to the serial
tail would cost the lane that much.

### Item 3 · par1's four other files

Two read-only survey agents went through these failures against the code and par1's log. Common to all four: par1's
Docker daemon was stalling. Cells that take 2 s in the other lanes took 225–295 s there (446, 462, 487, 495), and the
serial file just before the announcement file took 34 s for its 10 s window, about 24 s of it a `docker rm -f`. No
neighbouring file removes, stops or kills another's container: there is no `docker stop` or `docker kill` in the
suite, the only label sweeps are run.sh's (before the lane) and the no-op `remove_stale_throwaways`, and
`kill_strays` kills only pagers and editors, only the file's own.

- **`container-derived-defaults.bats`, SC-8 (8 cells).** Shared: the Docker daemon. `start_throwaway`'s
  `docker run -d --cpus 1.5` failed with nothing on stderr. Every error docker reports itself goes to stderr (a name
  in use, no CPU quota, a missing image), so an empty reason means the CLI was stopped, most likely at `RUN_TIMEOUT`'s
  30 s against the stalled daemon. Inferred, not proven. **Changed:** `start_throwaway` now says, when docker printed
  nothing, `docker printed nothing: exit RC after S s (bound 30s)`, and removes a container a part-way start left
  behind. The bound is unchanged.
- **`snapshot-over-the-size-cap-….bats`, the entry-cap cell (1 cell, 295 s).** Shared: the Docker daemon, through
  `pyq`. The tool did refuse: both `expect_status 1` and both `assert_within 20` passed (the trace names neither).
  The stdout in the message is `snapshot list`'s correct answer, `0 snapshots`. What failed was the parse of it:
  `jpy` → `pyq`, a throwaway container per parse, against the stalled daemon, reported as "stdout is not the JSON
  expected". **Changed:** `pyq` now says on failure `pyq: the parser exited RC after S s (bound 120s)`, so a cell
  that fails in its own parsing says so. Its bound is unchanged.
- **`timelike-tools-manifest-json-….bats`, P6 vanilla `bash -c` (1 cell).** Exit 143, with no output, after 0.129 s,
  from `timeout 30 docker run --rm … timelike-vanilla:local`. The container has no name. Nothing in the suite sends
  SIGTERM to a runner process or a container, and `docker rm -f` would give 137. In 0.13 s a stalled daemon cannot
  have started the container, so the signal reached the docker CLI itself, in the runner. **I did not find what
  sent it.**
  - One agent's hypothesis is busybox `timeout`'s watcher: it polls its command's pid once a second and signals that
    pid when time is up. Its source warns that this "may kill wrong process" if the pid is reused. That needs the
    runner's pid counter to wrap, and pid_max here is 4194304, so I do not believe it.
  - **Nothing changed for it.** Its `bash -lc` twin passed right after. The message already names the status and
    the time, so a recurrence will be visible.
  - Not marked serial: nothing it does is shared with a neighbour, and marking it would hide an unexplained signal
    rather than explain it.
- **`announcement-at-most-60-lines-….bats` (6 cells), a serial file.** It did run alone:
  - `load helpers` sources lane.bash at load time in bats-exec-file, and the file's name matches
    `TL_E2E_SERIAL_FILES`, so it took the lock exclusive before `setup_file`.
  - gounit holds the lock shared for as long as it runs, so the file could not start beside it either. gounit's Go
    tests took about 3 s after a module download and build.
  - What it met was the stalled daemon. Its prepared container passed its wait and its `StartedAt` read, and two
    cells later was `No such container`. With `--rm`, that means its process had exited, and the evidence went with
    it.
  - The same precondition failed in a serial lane on 2026-10-10 (`tests/out/run-20261010T064626Z.log`), before any
    parallel lane existed.
  - **Changed:** the 10 s wait (`sc1_wait_command`) no longer discards docker's error. On failure the cell's reason
    now carries docker's message and the container's state: status, exit code, OOM-killed and error. The 10 s is
    unchanged.

### Item 4 · gounit's seconds

The `step gounit: rc=0 (N s)` figure was taken when `bg_collect` collected it, after e2e and unit. The background
step now writes its own run time when it ends (`tests/out/.step-gounit.secs`, from taking the lock to its exit).
summary.json's `seconds` for gounit is that, and its note and rc line add when it was collected:
`════ step gounit: rc=0 (S s; collected after W s, beside e2e) ════`. A unit drives it with an e2e step that
sleeps 3 s: own ≤ 1 s, collected ≥ 3 s.

### Group C — written by the code instance

**delegations:**
- two read-only Explore agents, one per pair of par1 files: (a) `container-derived-defaults` and P6, and (b) the
  entry cap and the announcement file.
- They read the code and par1's log and proposed causes and fixes. I checked each claim I relied on against the
  file and log lines they cited. I took their diagnostics and declined their larger changes:
  - GNU `timeout` in the runner image (a new package, so a change to the image);
  - `docker exec -i` into the agent for `pyq` (it changes what the agent container sees);
  - dropping `--rm` from the announcement file's throwaways.
  Those are for the mentor if the next lanes show the same.

**criteria_reestablished:** none. A maintenance send carries no acceptance criteria. Units over tests/run.sh
(`tests/unit/test_lane_run_sh.py`, now 19, `executed`): the per-lane bench directory, the plan accounting (a short
stream fails and says why, a full one passes), and gounit's own seconds.

**reconcile_mode:** scoped (the four items).

**not_verified:**
- **Nothing has run in Docker.** That includes the per-lane bench directory, `exec_plain`'s bound under busybox
  `timeout`, the fixture's 300 s bound, and every new message.
- **What sent par1's SIGTERM** (P6), and **why par1's bench run stopped** after its third task: both unknown.
- **That par1's daemon stall will not recur:** nothing here reduces the load. If it recurs, the cells now say which
  step waited and for how long, rather than failing on content.
- **That no other file was cut short silently** in the three parallel lanes before `exec_plain`'s change. Every
  `not ok` in them is accounted for above, but an `ok` cell on a part-built fixture whose assertions did not notice
  cannot be seen from a log.

**changed_other_features:** none. Test files only (002's two bench e2e files, 007's announcement file, 001's git-log
file, the helpers), and tests/run.sh.

**process_failures_recorded:** Cycle 1's survey reasoned about one lane and missed two lanes on one commit (item 1),
and it did not see that `exec_plain` treats a stopped CLI as success (item 2).

**retired_prompts_seen:** none.

#### Host lane

`make test-host` on timelike's CPython 3.14.8 in a scratch venv, over this tree, 2026-10-15T12:12:25Z–12:21:47Z
(read from the clock): **rc 0**. pytest tests/unit: **2529 passed, 13 skipped** (529 s). That is Cycle 1's 2527 and
12, plus the three new lane units, and one skip more: `test_verify.py:714` (pytest, ruff or mypy not beside this
venv's interpreter), which depends on the venv, not on this change. `test_env_layer.sh` 60 of 60;
`test_shell_env_hook.sh` 57 of 57; `test_command_not_found.sh` 33 of 33.

Other checks: ruff check over `tests/` and `bench/` and ruff format over the changed unit file: clean.
shellcheck 0.11.0 over tests/run.sh, helpers.bash, lane.bash and all 86 e2e files: clean. The deny-list over the
tree and the commit message: below the commit, in the reply.

#### For the mentor

- **The rerun, on one HEAD:** a serial lane, three parallel lanes, and both partial lanes, as the feedback says.
- **What to read in a failing lane:**
  - the new `e2e: … cells reported …` line beside e2e's rc;
  - `exec_plain: stopped at the 30s bound` or `pyq: the parser exited …` in a cell's reason;
  - `docker printed nothing: exit … after … s` from `start_throwaway`;
  - the announcement file's `state: status …`.
  Each of these says that a step waited, not that the behaviour under test was wrong.
- The bench's output for each lane is now `bench/out/e2e/<stamp>/`; earlier lanes' files stay where they were.

## Cycle 1, Addendum 2 — bridge/feedback/maint-20261015-115635-lane-speed-proof-parallel-lanes-fail.md

The mentor's second proof chain, on `7505a57` (2026-10-15T12:33:43Z–15:00:38Z), appended to the same feedback file
("Rerun on `7505a57`"). The serial lane, par3 and both partial lanes passed. Items 1, 2 and 4 held in all four full
lanes. par1 and par2 failed, on two new items (5 and 6), which this addendum takes in order. Read from
`bridge/.make-test-ls2-*.log` (read only). Nothing here has run in Docker. **No criterion's budget was raised, no
cell's assertion changed, no file was added to lane.conf's serial group, and no unit was marked `timed`.**

### Group B — copied from the send

Unchanged from Cycle 1 and Addendum 1: `source_send` `bridge/sends/maint-lane-speed-20261015-062546.md`; no prompt,
no feature, no discovery revision of its own; no slice. The instruction is the feedback file named in the heading.

### Item 5 · `container-derived-defaults.bats`: the throwaway start (par1 and par2)

**What it shared:** the Docker daemon, at its busiest point in the lane. The file is 14th of 86 in the parallel
plan (cells 157–163 in both lanes), so it starts while the four `first` files are still running, the bench and the
catalog among them. Its first `docker run -d` was stopped at RUN_TIMEOUT's 30 s with nothing printed, in two lanes
of three. That timing is inferred from the plan's order: the TAP stream carries no timestamps.

**Not the `--cpus` flag:** SC-7's file (`one-command-prints-the-agents-resource-budget.bats`, 34th in the plan)
starts a throwaway with the same `--cpus 1.5`, and passed in all three parallel lanes. Other files' throwaways
(the snapshot-recreate file, 8th) also passed. I did not find why this one start took longer than its neighbours'.

**What changed:** the start is test plumbing that no criterion times, as the git-log fixture was. `sc8_prepare`
(the setup that starts both throwaways and reads their limits back) now has its own bound, `local RUN_TIMEOUT=300`,
which is the git-log fixture's figure. The cells, and their own bounds, are unchanged. If the start still fails, its
reason now names the 300 s bound. **Not marked serial:** the file changes nothing that a neighbour reads, and its
cells measure no time.

### Item 6 · `test_lane_run_sh.py::test_a_parallel_lane_runs_files_side_by_side_in_lane_conf_s_order` (par1, gw7)

**What it shared:** the fake `docker`'s log, `$LOG/docker.log`, between two processes of *one* lane under test. It
did not share anything between workers. tests/run.sh starts gounit beside e2e before the e2e sweep, so the fake
`docker` runs twice at once. The fake logged each call in two appends: its arguments, then a newline. gounit's `run`
landed between `rm -f stale-1` and its newline, so the line no longer read as `rm -f stale-1`. The fixture's
`'FAKE_STALE': ''` in the failure is the fixture's dict before `run_lane` adds `FAKE_STALE=stale-1`, not the
environment the lane ran with.

**Reproduced on this host:** the one test, 32 runs at a time: 1 failure in 64 runs, then 1 in 128. The kept log of
the second shows `rm|-f|stale-1|run|--rm|-u|…` on one line.

**What changed:** the fake builds the line first and appends it in one write (the longest line it writes is about
1.6 KB). The whole file, 32 runs at a time: **384 of 384 passed, 19 tests each.** The test is not marked `timed` and
still runs in the spread part.

### Group C — written by the code instance

**delegations:** none in this addendum.

**criteria_reestablished:** none (a maintenance send carries no acceptance criteria). `tests/unit/test_lane_run_sh.py`
(19 tests): `executed`, serially and under `-n 8` (Host lane, below), and in the stress runs above.

**reconcile_mode:** scoped (items 5 and 6).

**not_verified:**
- **Nothing has run in Docker,** including SC-8's 300 s setup bound.
- **Why SC-8's start was slower than its neighbours':** inferred from the plan's order, not shown.
- **That 300 s is enough:** no lane has measured the start under that load. It is a bound, not a wait.

**changed_other_features:** none. Test files only: `tests/e2e/container-derived-defaults.bats` (the image's
feature) and the lane unit.

**process_failures_recorded:** Addendum 1 added three lane units, but I did not run them concurrently or under
`-n 8` on this host. The race needed both.

**retired_prompts_seen:** none.

#### Host lane

`make test-host` on timelike's CPython 3.14.8 in a scratch venv (`venv-xdist`, with pytest 8.4.2 and pytest-xdist
3.8.0, the pins), over this tree, 2026-10-15T15:54:16Z–16:06:04Z (read from the clock): **rc 0**. pytest tests/unit,
serially: **2529 passed, 13 skipped** (634 s); `test_env_layer.sh` 60 of 60; `test_shell_env_hook.sh` 57 of 57;
`test_command_not_found.sh` 33 of 33.

Then the Docker lane's two unit parts on the same venv, 16:06:04Z–16:09:04Z: `-n 8 -m "not timed"`: **rc 0, 2513
passed, 13 skipped** (135 s); `-m timed`: **rc 0, 16 passed** (44 s). Together, the serial run's 2529.

Other checks: ruff check and ruff format over the changed unit file, and shellcheck 0.11.0 over the changed e2e
file: clean. The deny-list over the tree and the commit message: below the commit, in the reply.

#### For the mentor

- **The rerun, on one HEAD:** as the feedback says.
- **If SC-8 fails again:** its reason now ends `(bound 300s)`. A start that does not finish inside 300 s is no
  longer load alone, and would be worth a lane that keeps `docker events` for the window.

## Cycle 1, Addendum 3 — bridge/feedback/maint-20261015-115635-lane-speed-proof-parallel-lanes-fail.md

The mentor's third proof chain, on `5c3c84a` (2026-10-15T17:04:02Z–19:52:19Z), appended to the same feedback file
("Rerun on `5c3c84a`"). The serial lane passed (689 of 689). The three parallel lanes failed at many sites, on a
busier host: serial e2e 3335 s against proof 2's 2762 s. Items 5 and 6 held, and so did 1, 2 and 4. This addendum
takes items 7 to 10 and the note about the stack. Read from `bridge/.make-*-ls3*.log` (read only), and by one
read-only survey agent (below). Nothing here has run in Docker. **No criterion's budget was raised, no cell's
assertion changed, no file was added to lane.conf's serial group, no unit was marked, and `E2E_JOBS` is unchanged.**

### Group B — copied from the send

Unchanged: `source_send` `bridge/sends/maint-lane-speed-20261015-062546.md`; no prompt, no feature, no discovery
revision of its own; no slice. The instruction is the feedback file named in the heading.

### Item 7 · the plumbing bound, as a class

**The rule, written once in `tests/e2e/helpers.bash`:** two runner-side bounds.
- **`RUN_TIMEOUT` (30 s, unchanged)** bounds the command a cell measures: `run_in`, `exec_in` and `run_bare`,
  whose elapsed time `assert_within` reads, and the direct calls whose time or timeout a cell asserts.
- **`PLUMBING_TIMEOUT` (300 s, new)** bounds everything else: steps that set a cell up, read evidence back or
  clean up, and whose time no criterion names. `pyq`'s `PYQ_TIMEOUT` now defaults to it (it was 120 s).

**Moved to `PLUMBING_TIMEOUT`, in the helpers:** `exec_plain`, `copy_into_container`, `start_throwaway`,
`remove_throwaway`, `remove_stale_throwaways`, `adeled`, `standin_list`, `canary_bytes`, `pyj`, and so everything
built on them (`container_tmpdir`, `state_root_dir`, `container_rm`, `stamp_check`, the stand-in helpers,
`install_uv_tool_wrappers`).

**Moved, in the .bats files** (51 uses in 13 files):
- the image inspects, throwaway starts and readiness waits of the announcement file;
- the fixture server's start in `credentials-fail-fast.bats`;
- the snapshot-after-recreate file's volume removal, fixture copy, manifest reads and its `in_rc` (no cell times
  these, and one builds the fixture repository);
- `standin_post`'s container in `adele-isolation-…` (cell 106: the request has its own 5 s `urlopen` bound inside
  the container, so a refusal that never answers still fails the cell);
- `exec_root` in `edit-slice-0-…`;
- the gofmt cross-check in `edit-would-fail-…`;
- the process and environment reads in `no-credential-…`, and its `setup_file` request cycle;
- the cgroup read in `one-command-…`;
- SC-8's whole setup in `container-derived-defaults.bats`;
- the P6 image inspects and probe in `timelike-tools-manifest-…` (item 8);
- the two whole-filesystem `find` walks in `agent-cannot-run-as-root-…` (`RUN_TIMEOUT="$PLUMBING_TIMEOUT" run_in`,
  the pattern the file set already uses for `RUN_TIMEOUT=60`): those cells have no `assert_within`.

The `local RUN_TIMEOUT=300` overrides from Addenda 1 and 2 (the git-log fixture's `prepare`, `sc8_prepare`) and
`install_uv_tool_wrappers`' own are gone: they now get the same bound from the helpers.

**The failing sites, mapped:**

| Site | Bound before | Now |
|---|---|---|
| `recover-repo-sc6/7/8.sh` in `setup` (cells 83, 85, 88, 89, 99) | `exec_plain` | plumbing |
| the first container in the after-recreate file (cells 100, 101) | `start_throwaway` | plumbing |
| SC-4's setuid `find` (cell 117) | `run_in`, no `assert_within` | plumbing, per call |
| cell 106, the stand-in without a credential | `standin_post`'s `docker run` | plumbing |

**Kept at `RUN_TIMEOUT`, per step:**
- `run_in`, `exec_in` and `run_bare` everywhere else: the style under test.
- The cells that set it locally around one command (`RUN_TIMEOUT=60 run_in`, the 90 s hook file, the 120 s
  installs).
- `run-exceeding-its-timeout-…`: its local 30 s is read by its own elapsed check.
- `direct_exec` in `command-not-installed-…`: docker's own error is the evidence, and it starts nothing.
- The printed extend command in `request-within-grant-…`: run exactly as printed.
- SC-8's REPL session: its message names `RUN_TIMEOUT`.

None of these failed in the three lanes.

**`E2E_JOBS`:** unchanged at 8. I cannot measure another value without Docker. If the next lanes still fail on
load, `E2E_JOBS=4` is the lever to measure.

### Item 8 · P6 in par1: not a stray TERM

**What happened:** the vanilla probe's `docker run` (line 324) went past its 30 s bound, and BusyBox's `timeout`
exits with the killed command's status, 143, not GNU's 124 (helpers.bash already says so, for `pyq`). Both P6
cells took 30.2 s and 30.3 s in all (TAP's own times). The "after 0.095s" was `ELAPSED_S` from the cell's
earlier `run_in`: the probe is a bare bats `run`, which sets no time, and `assert_status` printed the stale one.
Proof 1's "143 after 0.129 s" was the same: that cell took 30.3 s (30258 ms).

**Nothing shared:** no other file stops, recreates or kills a container this file uses. The probe is a fresh
container of its own (`--rm`). So lane.conf states no dependency.

**What changed:** the probe runs under `PLUMBING_TIMEOUT` (it is a fresh container and a refused pip install, and
P6 names no time), and the cell sets its own `ELAPSED_MS`/`ELAPSED_S` around the run, so a failure reports the
probe's own time.

### Item 9 · the broker tests' stand-in client, beside e2e

**Which:** plumbing. The fixture's client is `NewStandinClient`, whose 10 s is the production bound ("well
inside the agent's 30 s limit"), and no broker test asserts it.
- The stand-in in these tests is an in-process httptest server.
- Its store fsyncs the record file and its directory on every change, and so does the ledger's sqlite.
- So the 10 s ran out on the lane's I/O, not on anything the tests check. That I/O reading is inferred: the
  logs show only the client's deadline.

**What changed:** the fixture sets its own client bound, `fixtureUpstreamTimeout` (120 s), in
`adele/internal/broker/fixture_test.go`. The production 10 s and every test's assertion are unchanged. The two
tests that build their own client (wrong canary, bad host) fail fast and keep 10 s.

### Item 10 · `test_budget_json_shape`

The test runs the tool twice (`json_of`, `text_of`) and compared the lines whole. It now blanks the disk's free
figure (`without_free`) on both sides, and still compares everything else. The free figure itself is checked
against `statvfs` in the disks tests, with their slack. Not marked.

### The stack after a lane

Yes: lanes leave the stack up. That predates this send: `compose_up` takes it down and up at the start of each
lane, and nothing takes it down at the end. It is left running on the lane's own grant file and volumes, and
`compose_up`'s comment says to run `make up` afterwards for the operator's grants. Nothing records a decision to
leave it up rather than stop it. I have not changed it in this addendum; if the lane should stop the stack at the
end, that is one step after the summary, and it is the mentor's or the operator's call.

### Group C — written by the code instance

**delegations:**
- one read-only Explore agent surveyed every `RUN_TIMEOUT` use in tests/e2e: each helper's class, the failing
  sites and the cells that depend on the bound's value.
- I checked each site I moved against the file, and I moved more than it proposed: `in_rc`, the P6 probe and the
  two `find` walks, each with the reason above.

**criteria_reestablished:** none (a maintenance send carries no acceptance criteria). Units: `test_budget.py` 73
`executed`; the Go tests over adele/ `executed` (host, below).

**reconcile_mode:** scoped (items 7 to 10).

**not_verified:**
- **Nothing has run in Docker,** so it is not shown that 300 s is enough under proof 3's load, or that no cell now
  waits long enough to stretch the lane noticeably. A plumbing step that hangs now costs 300 s before it fails,
  not 30.
- **Item 9's cause** (I/O rather than CPU) is inferred.
- **Item 8:** that nothing else contributed to the probe's 30 s.

**changed_other_features:** test code only: the e2e files and helpers named above, which belong to several
features, `tests/unit/test_budget.py`, and Adele's Go test fixture. No production code.

**process_failures_recorded:** items 2 and 5 were fixed one site each. This addendum should have been the first
fix.

**retired_prompts_seen:** none.

## npm 11.21.1 — bridge/feedback/maint-20261015-195341-npm-advisories-scan-blocks.md

Proof 3's scan on `5c3c84a` (2026-10-15T19:50:14Z, `bridge/.make-scan-ls3.log`) blocked the agent and vanilla images
on three Highs bundled in the pinned npm 11.21.0: `GHSA-6j4f-fj2g-mc7p` and `GHSA-qhr7-859c-m2p7` (brace-expansion
5.0.9) and `GHSA-rfgv-xxqx-mfg5` (undici 6.28.0). The gate's release check named npm 11.21.1 as the release that
ships the fixes. Fixed on `maint/lane-speed`, in its own commit, because it blocks this branch's merge.

**The rule applied: H9, not SC-2.**
- **H9 (constitution; quality-standards' *Vulnerability baseline*)** decides what blocks:
  - A High with a fix available blocks.
  - For a bundled library, "fix available" means a stable release of the bundling component inside the
    constraint. For npm, that is any stable npm whose `engines` admits the pinned Node.
  - It sets no release age.
  - The release check blocks "whatever the baseline says" once such a release ships the fix. So a dated baseline
    entry for these three ids is not open to me: the gate would still block them, and H9 keeps the baseline for
    findings with no fix.
- **SC-2's minimum release age** is an acceptance criterion of the package guard: what the *agent's* installs
  refuse. No governance file applies it to timelike's own pins. I found no age rule in the constitution,
  tech-stack.md or quality-standards.md. It does not apply to this bump. If the project wants a cooling-off for
  its own pins, that is a governance change for plan, not a reading I can make here.

**Checked before the bump (host, before 2026-10-15T20:38:00Z, read from the clock):**
- npm 11.21.1, from the registry's metadata: not deprecated, published 2026-10-15T15:45:16Z, `engines` `node:
  ^20.17.0 || >=22.9.0`, which admits Node 24.21.0. It is the newest 11.21.x; `latest` is 12.2.0.
- The tarball's sha512 matches the registry's `dist.integrity` (`sha512sum -c` OK).
- It bundles brace-expansion 5.0.12 (fixed in 5.0.10 and 5.0.11) and undici 6.29.0 (fixed in 6.28.1).
- Its bundled tree against 11.21.0's: those two, and patch or minor moves in arborist, http-cache-semantics, ip-address,
  libnpmdiff, libnpmexec, libnpmfund, libnpmpack and postcss-selector-parser. Nothing added or removed.

**What changed:** `pins.env`: `NPM_VERSION=11.21.1` and `NPM_SHA512` (the integrity as hex), with the comment
updated. Both Dockerfiles take them as build args and check the checksum and `npm --version`, unchanged. Units:
`test_agent_runtimes.py` and `test_scan_release_check.py`, 129 passed.

**Left for the baseline's review:** the three bundled-class entries for these ids in `scan/baseline/timelike-agent.json`
and `timelike-vanilla.json` will match no finding. The gate reports that as "match no finding in this scan (drop
them at the next review)", which does not block. Their reasons ("no stable npm release … ships it") are now
out of date. I did not edit a reviewed baseline outside its review. `GHSA-ch52-4w7c-c8xp` (http-cache-semantics,
now 4.3.0) may also stop matching; the scan will say.

**not_verified:** no image was built and no scan was run. That the images build with 11.21.1, that grype then
finds none of the three, and what the release check prints, are all for the mentor's scan.

#### Host lane (Addendum 3 and npm 11.21.1, one tree)

`make test-host` on timelike's CPython 3.14.8 in a scratch venv (`venv-xdist`: pytest 8.4.2, pytest-xdist 3.8.0, the
pins), over this tree, 2026-10-15T20:37:53Z–20:47:22Z (read from the clock): **rc 0**. pytest tests/unit, serially:
**2529 passed, 13 skipped** (535 s); `test_env_layer.sh` 60 of 60; `test_shell_env_hook.sh` 57 of 57;
`test_command_not_found.sh` 33 of 33. Then the Docker lane's two unit parts, 20:47:22Z–20:50:22Z:
`-n 8 -m "not timed"` **rc 0, 2513 passed, 13 skipped** (135 s); `-m timed` **rc 0, 16 passed** (44 s).

Go: `go vet ./internal/broker/` and `go test -count=1 ./...` over adele/ with the scratch Go 1.27.2 (cold module
cache, so it fetched modules): every package `ok`; `gofmt -l internal/` empty. shellcheck 0.11.0 over helpers.bash,
lane.bash, tests/run.sh and all 86 e2e files, and ruff check and ruff format over `test_budget.py`: clean. The
deny-list over the tree and the commit messages: in the reply.

## Cycle 1, Addendum 4 — bridge/feedback/maint-20261015-115635-lane-speed-proof-parallel-lanes-fail.md

The mentor's fourth proof chain, on `280659f` (2026-10-15T22:08:43Z–2026-10-16T01:21:00Z), appended to the same
feedback file ("Rerun on `280659f`"). Serial, par1 and par2 passed (689 of 689), as did the scan and lint, and the
partial rerun. par3 and the first partial lane were ruined by the host's own scheduled Docker cleanup at 23:50Z (no
action for code/). par3b, on a heavily loaded host, failed twice from load: items 11 and 12. Items 7 to 10 held.
Read from `bridge/.make-*-ls4*.log` (read only). Nothing here has run in Docker. **No criterion's budget was raised,
no cell's assertion changed, no unit was marked, and `E2E_JOBS` is unchanged.** Five files join lane.conf's serial
group (item 11).

### Group B — copied from the send

Unchanged: `source_send` `bridge/sends/maint-lane-speed-20261015-062546.md`; no prompt, no feature, no discovery
revision of its own; no slice. The instruction is the feedback file named in the heading.

### Item 11 · time budgets in the spread part, as a class

**The measurement this needed did not exist.** A cell's time in the TAP stream is mostly its setup: the git-log
cells take up to 101 s in par3b and pass their 20 s budgets, because `prepare` builds a fixture repository first.
The time the budget is about is the one `run_in` records in `ELAPSED_MS`, and no lane printed it for a passing cell.
So:

- **`assert_within` now records it.** With `TL_WITHIN_LOG` set, each call appends one line (file, budget s, measured
  ms, cell) in one write, passing or not, before its verdict, which it does not change. `tests/run.sh` sets
  `TL_WITHIN_LOG=/out/within.tsv` in every lane, serial included (the one addition to the serial lane's command;
  the bats arguments are unchanged), clears the file before the lane, and after it prints the count and the five
  timed commands that used the most of their budgets (`within_account`; it fails nothing). The next proof's
  `tests/out/within.tsv` gives every budget's headroom exactly, in every lane.
- **Until then, a bound.** For each of the 588 `assert_within` cells I matched (by name, all 588 in all four lanes)
  its time in proof 4's serial, par1, par2 and par3b TAP. The quietest of the first three is an upper bound on its
  timed command's use, so `budget − quietest cell` is a lower bound on its headroom. Survey script:
  every `@test`, the `assert_within` calls in its body and in the file's functions it calls.

**The rule (now in lane.conf's header):** a file goes in the serial group when a budget it asserts has less than
15 s of headroom over what its timed command takes on a quiet host. 15 s is what par3b put on one command: cell 176
took 0.5–1.2 s in the other lanes and 15.6 s there (`took 15.220s, limit 10s`). par3b's load was bursty rather
than even: the median cell ran at 0.88 times its serial time, the 90th percentile at 1.70 (cells of 200 ms or more), so a factor would not
describe it; a stall of about 15 s on one command does.

**The spread and `first` files, tightest timed cell each** (the 13 files already serial are not listed; all 469
spread cells and 64 `first` cells are covered):

| File (part in proof 4) | Timed cells | Tightest budget | Its quietest cell | Headroom (bound) | par3b, slowest timed cell | Now |
|---|---|---|---|---|---|---|
| `services-start-exits-before-ready-non-zero-died-last-log-lines.bats` (spread) | 4 | 10 s | 1.9 s | 8.1 s | 1.9 s | **serial** |
| `credentials-fail-fast.bats` (spread) | 26 | 10 s | 0.9 s | 9.1 s | 15.6 s (not ok) | **serial** |
| `journal-last-20-entries-of-current-session-bounded.bats` (spread) | 2 | 20 s | 9.0 s | 11.0 s | 9.4 s | **serial** |
| `git-log-diff-commit-rebase-exit-within-20-seconds.bats` (first) | 50 | 20 s | 6.8 s | 13.2 s | 101.3 s | first; within.tsv decides |
| `journal-concurrent-agents-separable-by-agent-and-session.bats` (spread) | 2 | 20 s | 5.9 s | 14.1 s | 5.8 s | **serial** |
| `timelike-tools-manifest-json-interactivity-risk-safer-alternative.bats` (spread) | 4 | 20 s | 5.7 s | 14.3 s | 5.7 s | **serial** |
| `restore-returns-captured-content-and-removes-files-created-after.bats` (spread) | 10 | 20 s | 4.9 s | 15.1 s | 5.5 s | spread |
| `announcement-generated-from-manifests-missing-tool-fails.bats` (spread) | 6 | 20 s | 4.6 s | 15.4 s | 5.0 s | spread |
| `version-control-history-index-and-stash-unchanged-by-snapshot-and-restore.bats` (spread) | 4 | 20 s | 4.3 s | 15.7 s | 4.5 s | spread |
| `services-list-state-port-uptime-marks-died.bats` (spread) | 4 | 20 s | 4.2 s | 15.8 s | 4.2 s | spread |
| `view-directory-overview-dependency-directory-collapsed-within-budget.bats` (spread) | 6 | 20 s | 3.9 s | 16.1 s | 203.9 s | spread |
| `one-command-prints-the-agents-resource-budget.bats` (spread) | 10 | 20 s | 3.5 s | 16.5 s | 3.5 s | spread |
| `snapshot-over-the-size-cap-is-partial-and-names-what-was-excluded.bats` (spread) | 10 | 20 s | 3.5 s | 16.5 s | 3.4 s | spread |
| `services-start-with-port-readiness-returns-after-port-accepts.bats` (spread) | 4 | 20 s | 3.4 s | 16.6 s | 3.4 s | spread |
| `symbols-stale-cache-rebuilt-answers-from-new-content.bats` (spread) | 4 | 20 s | 3.4 s | 16.6 s | 3.3 s | spread |
| `journal-lists-every-tool-invocation-in-order-with-pointer.bats` (spread) | 4 | 20 s | 3.2 s | 16.8 s | 3.3 s | spread |
| `view-and-search-slice-1-carried-items.bats` (spread) | 10 | 20 s | 2.9 s | 17.1 s | 3.5 s | spread |
| `edit-anchored-lines-unchanged-applies-changed-lines-refused-naming-them.bats` (spread) | 12 | 20 s | 2.8 s | 17.2 s | 217.7 s | spread |
| `search-262-matches-shows-50-grouped-with-212-omitted-and-narrowing.bats` (spread) | 10 | 20 s | 2.7 s | 17.3 s | 2.8 s | spread |
| `snapshot-records-tracked-untracked-and-ignored-files.bats` (spread) | 4 | 20 s | 2.4 s | 17.6 s | 2.4 s | spread |
| `edit-dry-run-prints-unified-diff-file-byte-identical.bats` (spread) | 6 | 20 s | 2.4 s | 17.6 s | 195.9 s | spread |
| `view-range-context-missing-file-and-binary.bats` (spread) | 16 | 20 s | 2.3 s | 17.7 s | 143.2 s | spread |
| `journal-shell-commands-outside-tools-with-exit-codes.bats` (spread) | 4 | 20 s | 2.3 s | 17.7 s | 2.4 s | spread |
| `services-start-port-held-by-registered-service-refused-naming-holder.bats` (spread) | 4 | 20 s | 2.3 s | 17.7 s | 2.3 s | spread |
| `view-412-line-file-shows-lines-1-120-with-header-and-next-range.bats` (spread) | 8 | 20 s | 2.3 s | 17.7 s | 2.3 s | spread |
| `view-anchor-mode-short-stable-anchor-changes-with-content.bats` (spread) | 12 | 20 s | 2.1 s | 17.9 s | 2.6 s | spread |
| `edit-replacing-text-appearing-once-changes-only-that-text-prints-edited-region.bats` (spread) | 4 | 20 s | 2.1 s | 17.9 s | 2.1 s | spread |
| `edit-would-fail-syntax-check-refused-with-checker-error-file-byte-identical.bats` (spread) | 30 | 20 s | 2.0 s | 18.0 s | 2.1 s | spread |
| `edit-matches-nowhere-refused-exit-3-nearest-candidates.bats` (spread) | 4 | 20 s | 2.0 s | 18.0 s | 2.1 s | spread |
| `edit-crlf-tab-indented-file-given-lf-and-spaces-preserves-crlf-and-tabs.bats` (spread) | 4 | 20 s | 1.9 s | 18.1 s | 118.4 s | spread |
| `snapshot-refuses-home-root-and-their-ancestors.bats` (spread) | 16 | 20 s | 1.9 s | 18.1 s | 2.4 s | spread |
| `symbols-dependents-of-changed-file-ranked.bats` (spread) | 4 | 20 s | 1.9 s | 18.1 s | 1.9 s | spread |
| `services-stop-terminates-every-process-in-its-tree.bats` (spread) | 2 | 20 s | 1.7 s | 18.3 s | 1.8 s | spread |
| `search-zero-matches-exits-0-and-1-only-in-strict-mode.bats` (spread) | 14 | 20 s | 1.7 s | 18.3 s | 1.8 s | spread |
| `edit-name-and-manifest.bats` (spread) | 6 | 20 s | 1.6 s | 18.4 s | 1.6 s | spread |
| `edit-matches-more-than-once-refused-exit-3-listing-line-numbers.bats` (spread) | 4 | 20 s | 1.6 s | 18.4 s | 86.9 s | spread |
| `edit-slice-0-carried-items.bats` (spread) | 4 | 20 s | 1.6 s | 18.4 s | 1.7 s | spread |
| `run-secrets-redacted-in-shown-output-and-saved-log.bats` (spread) | 8 | 20 s | 1.5 s | 18.5 s | 1.5 s | spread |
| `run-5000-lines-verdict-first-head-first-errors-tail-more-command.bats` (spread) | 2 | 20 s | 1.3 s | 18.7 s | 1.3 s | spread |
| `agent-cannot-run-as-root-change-firewall-or-read-adele.bats` (spread) | 8 | 20 s | 1.1 s | 18.9 s | 1.1 s | spread |
| `symbols-callers-3-call-sites-grouped-text-based-header.bats` (spread) | 4 | 20 s | 1.1 s | 18.9 s | 1.2 s | spread |
| `services-name-and-manifest.bats` (spread) | 4 | 20 s | 1.0 s | 19.0 s | 1.4 s | spread |
| `symbols-outline-fixture-14-definitions-line-ranges-no-bodies.bats` (spread) | 4 | 20 s | 1.0 s | 19.0 s | 1.0 s | spread |
| `run-output-within-head-and-tail-printed-in-full.bats` (spread) | 2 | 20 s | 1.0 s | 19.0 s | 1.1 s | spread |
| `view-and-search-resolve-once-and-pass-conform.bats` (spread) | 12 | 20 s | 0.9 s | 19.1 s | 127.5 s | spread |
| `symbols-name-and-manifest.bats` (spread) | 4 | 20 s | 0.9 s | 19.1 s | 0.9 s | spread |
| `run-full-scratch-or-workspace-names-filesystem-and-free-space.bats` (spread) | 4 | 20 s | 0.8 s | 19.2 s | 0.8 s | spread |
| `journal-name-and-manifest.bats` (spread) | 4 | 20 s | 0.8 s | 19.2 s | 0.9 s | spread |
| `container-derived-defaults.bats` (spread) | 16 | 20 s | 0.7 s | 19.3 s | 1.0 s | spread |
| `conformance-check-over-every-timelike-tool-on-path.bats` (first) | 14 | 20 s | 0.6 s | 19.4 s | 32.0 s | first |
| `run-killed-by-memory-limit-names-limit-and-peak.bats` (spread) | 4 | 20 s | 0.6 s | 19.4 s | 0.6 s | spread |
| `run-exit-equals-the-wrapped-commands-exit-code.bats` (spread) | 18 | 20 s | 0.6 s | 19.4 s | 0.6 s | spread |
| `hooks-a-repository-configures-run.bats` (spread) | 7 | 20 s | 0.5 s | 19.5 s | 0.6 s | spread |
| `bash-c-and-bash-lc-defaults-in-effect.bats` (spread) | 16 | 20 s | 0.3 s | 19.7 s | 0.7 s | spread |
| `verify-name-and-manifest.bats` (spread) | 6 | 20 s | 0.1 s | 19.9 s | 1.0 s | spread |
| `verify-changed-one-source-file-runs-importing-tests-lints-changed-states-why.bats` (spread) | 4 | 25 s | 3.3 s | 21.7 s | 3.5 s | spread |
| `verify-pytest-3-failed-409-passed-file-line-name-assertion-lines.bats` (spread) | 4 | 25 s | 2.9 s | 22.1 s | 3.0 s | spread |
| `verify-parses-pytest-jest-vitest-go-cargo-unknown-format-falls-back.bats` (spread) | 18 | 25 s | 2.8 s | 22.2 s | 141.7 s | spread |
| `verify-changed-no-changes-exits-0-nothing-selected.bats` (spread) | 6 | 25 s | 1.7 s | 23.3 s | 1.7 s | spread |
| `a-directory-removed-by-a-script-is-restorable-from-the-most-recent-scheduled-snapshot.bats` (spread) | 4 | 30 s | 2.3 s | 27.7 s | 26.5 s | spread |
| `a-restore-first-snapshots-the-workspace-so-the-restore-can-be-undone.bats` (spread) | 2 | 30 s | 2.2 s | 27.8 s | 26.4 s | spread |
| `a-snapshot-taken-in-one-session-is-listed-and-restorable-from-a-new-session-and-after-recreate.bats` (spread) | 2 | 30 s | 2.2 s | 27.8 s | 26.3 s | spread |
| `deleted-files-trash-restorable-and-purged-by-age-and-size.bats` (spread) | 4 | 30 s | 1.6 s | 28.4 s | 7.1 s | spread |
| `re-running-a-refused-install-with-the-confirm-flag-proceeds-and-records-the-override.bats` (spread) | 6 | 60 s | 2.7 s | 57.3 s | 2.9 s | spread |
| `a-recursive-delete-hard-reset-force-push-and-clean-each-take-an-automatic-snapshot.bats` (spread) | 12 | 60 s | 2.6 s | 57.4 s | 26.2 s | spread |
| `installing-packages-already-pinned-in-the-projects-lockfile-proceeds-without-registry-checks.bats` (spread) | 6 | 120 s | 3.1 s | 116.9 s | 3.2 s | spread |

**Moved to serial (five files, each with its reason in lane.conf):** `credentials-fail-fast.bats` (10 s budgets,
par3b's failure), `services-start-exits-before-ready-non-zero-died-last-log-lines.bats` (10 s),
`journal-last-20-entries-of-current-session-bounded.bats`, `journal-concurrent-agents-separable-by-agent-and-session.bats`
and `timelike-tools-manifest-json-interactivity-risk-safer-alternative.bats` (20 s, with 11.0–14.3 s of headroom by
the bound). Their bound overstates what the timed command uses, so some may not need it; within.tsv will say, and a
file can move back on that evidence.

**Stays `first`: `git-log-diff-commit-rebase-exit-within-20-seconds.bats`.** By the bound it has 13.2 s, under the
rule. But its cells' time is mostly `prepare` (a fixture repository, under `PLUMBING_TIMEOUT`), so the git
command's own share is unknown, and the bound is the least informative for this file of any. Moving it costs most:
507 s of cells in proof 4's serial lane, run alone in the serial tail, about 55% on top of par1's and par2's e2e
875–954 s. I left it in place, said so on its lane.conf line, and the next proof's within.tsv decides: if its git
commands use more than 5 s of their 20, it moves.

**Stay spread: every other file.** Each has at least 15.1 s of headroom by the bound (the table), which is more
than par3b's stall. The closest are `restore-returns-…` (15.1 s), `announcement-generated-…` (15.4 s) and
`version-control-…` (15.7 s); within.tsv will show whether the bound or the rule is the tighter.

**The serial group's own files** were not re-examined against this rule; they are serial already. Two of them
assert near their budgets even alone (`hook-past-its-time-limit-is-killed.bats`: 7.7 s quiet cells on an 8 s
budget, `hooks-under-env-i-…`: 4.4 s on 7 s), but that is how those criteria are written (a 3 s or 2 s limit plus
5 s grace, timed from the runner), not a scheduling question.

**What the move costs:** the five files' cells took 77 s in proof 4's serial lane (6.6 s, 11.6 s, 22.0 s, 14.5 s,
22.3 s), plus their `setup_file`s, which the TAP stream does not time. They now run alone, after the rest, instead
of beside it: roughly 1.5 minutes on the parallel lane's e2e, about 8% of par1's and par2's 875–954 s. Not measured.

### Item 12 · the unit fixtures' bounds

`full_run` (`tests/unit/test_bench_cli.py`) is plumbing: the whole fake bench pipeline, run for each of the six
tests that read its output, whose time no test asserts. It took 18.3–18.5 s a time on this host, serially
(`--durations`), so 120 s was about 6.5 times that, and par3b's unit step ran at 2.6 times proof 4's other lanes
(507 s against 197 s), more at its peaks.

- **One bound for unit-side setup:** `PLUMBING_TIMEOUT_S = 300.0` in `tests/unit/conftest.py`, documented as the
  unit side of item 7: a subprocess that only sets a test up, whose time no test asserts. The bound on the command
  a test is about stays where the test sets it.
- **Where it applies:** every pytest fixture's subprocess bound, found by walking each fixture's calls (AST, all
  of tests/unit):
  - `test_bench_cli.py` `full_run`: `bench_run(…, timeout=PLUMBING_TIMEOUT_S)` (was the helper's default 120 s);
  - `test_verify.py` `projects` and `repo`: the project generator (was 60 s), and the module's `git` helper, which
    only builds the repositories the tests read (was 30 s);
  - `test_git_hook_dispatch.py` `repo`: its two `git` calls (were the helper's 30 s), and its `git init`, which
    had no bound at all.
- **Left as they are, with the reason:**
  - two teardown waits: `test_adele_cli.py` `adele` (`thread.join(timeout=5)`) and `test_services.py` `lab`
    (`p.wait(timeout=5)` under `suppress(TimeoutExpired)`, `wait_until(…, timeout=2)` in a three-round kill loop).
    Neither fails when it expires; each is a best-effort wait before the next cleanup step.
  - the bounds inside test bodies (about 70 sites): they bound the command the test is about, or a tool's own
    limit the test checks (exit 124 within a time), or the `timed` tests. They are the unit side of `RUN_TIMEOUT`.
    None failed in any proof-4 lane. A test-body bound that fails under load later is that class's question.
- **Not marked `timed`.** No bench test asserts a time.

Seen and not changed: `full_run` is function-scoped, so the pipeline runs six times (about 110 s of a serial unit
step). A module-scoped run would cut that, but two of its tests change its output directory (one deletes the report, one runs into it again), so that is a change to
the tests' independence, not to a bound.

### Group C — written by the code instance

**delegations:** none. The survey (every `assert_within` cell against proof 4's four TAP streams, and every unit
fixture's bounds) was mine, by script, in scratch.

**criteria_reestablished:** none (a maintenance send carries no acceptance criteria). Units: the host lane below,
`executed`; `test_lane_run_sh.py` 20 `executed` (one new test: the headroom summary; and the serial lane test checks its one new
variable).

**reconcile_mode:** scoped (items 11 and 12).

**not_verified:**
- **Nothing has run in Docker.** That `assert_within` writes within.tsv from inside the runner, that the lane prints
  its summary, and the moves' cost in time, are for the mentor's proof.
- **The headroom figures are bounds**, from cell times; within.tsv replaces them.
- **15 s** is par3b's one observed stall. A host worse than par3b would need more, and no rule here would catch it.

**changed_other_features:** test code only: tests/e2e (helpers.bash, lane.conf), tests/run.sh, and five unit
files. No production code.

**process_failures_recorded:** item 11 was the class lane.conf already named ("cells measure the machine"), applied
one file at a time when the send built lane.conf; the rule should have been stated with a measurement then.

**retired_prompts_seen:** none.

#### Host lane (Addendum 4, one tree)

`make test-host` on timelike's CPython 3.14.8 in the scratch venv (`venv-xdist`: pytest 8.4.2, pytest-xdist 3.8.0,
the pins), over this tree, 2026-10-16T03:59:35Z–04:09:03Z (read from the clock): **rc 0**. pytest tests/unit,
serially: **2530 passed, 13 skipped** (534 s); `test_env_layer.sh` 60 of 60; `test_shell_env_hook.sh` 57 of 57;
`test_command_not_found.sh` 33 of 33. Then the Docker lane's two unit parts, 04:09:03Z–04:12:04Z:
`-n 8 -m "not timed"` **rc 0, 2514 passed, 13 skipped** (136 s); `-m timed` **rc 0, 16 passed** (44 s).
shellcheck 0.11.0 over helpers.bash, lane.bash, tests/run.sh and all 86 e2e files, and ruff check and ruff format
over the five changed unit files: clean. The deny-list over the tree and the commit message: in the reply.
