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
