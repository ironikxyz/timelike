# Contract: `timelike-bench`, `bench/run.sh` and the report

## `timelike-bench` (in the driver image, `/opt/timelike-bench/bin`)

This tool is bound by the feature-001 output contract (rules 1–16). It is built on `agentio`, and it
passes `timelike-conform` (FR-15).

```
timelike-bench run    [--task ID ...] [--out DIR] [--call-limit S] [--run-limit S] [--json|--text] [--limit N] [--verbose]
timelike-bench report DIR [--json|--text] [--limit N] [--verbose]
timelike-bench catalog [--json|--text]
timelike-bench --help | --agent-info
```

- **`run`**
  1. Refuses if a key-shaped variable is present (RB9). Exit 4 (a grant is required) with remediation
     "unset <NAME>; live runs are not part of slice 0".
  2. Checks the identity of all three images against `BENCH_GIT_SHA` (RB8). On a stale or empty stamp
     it exits 1, naming both values.
  3. Runs every selected task in `vanilla`, then `timelike`.
  4. Writes the traces and `<DIR>/report.txt`.
  5. Prints a capped summary.

  **Output layout** (one rule for the tool and `bench/run.sh`; fixed at Cycle 1, after the Docker
  lane at `8ce6173` found the two disagreeing):
  - `--out DIR` writes exactly `DIR/traces/` and `DIR/report.txt`. A `DIR` that already holds traces
    is refused (exit 1), so two runs never mix in one report.
  - Without `--out`, the run writes `$BENCH_OUT/<UTC stamp>/`, so repeated runs never overwrite.

  Exit 0 when every trace was written, **whatever the tasks' endings**, because a timelike loss is
  data, not a failure.
- **`report DIR`** rebuilds `report.txt` from the traces alone (FR-10). Exit 3 if `DIR` holds no
  traces.
- **`catalog`** lists the tasks and the not-benchable capabilities. It is read-only and needs no
  Docker, so it is the tool's conformance probe (`--agent-info` `probe: ["catalog"]`). *(Added at
  T009.)*
- **Environment read by `run`:** `BENCH_GIT_SHA` and `BENCH_BASE_DIGEST` (both required; an empty
  value exits 1), `BENCH_OUT` and `BENCH_REPRODUCE` (optional). `TIMELIKE_BENCH_DOCKER` names the
  docker binary; it exists only so that host units can put a stand-in in its place.
- **First line** (rule 12): `timelike-bench: <run|report> <DIR> [FAKE-AGENT BENCH PIPELINE DEMO RUN
  -- not a test of timelike]`. The bracketed scope carries this whenever any trace's `harness_name` is
  `timelike-fake-agent`; the report's own first line carries the full text. *(Amended, send `…-080659`.)*
- **Full artefact** (rule 3): the summary ends with `report: <DIR>/report.txt`.

## The wrapper (`executor.WRAPPER`, identical for both images)

```
sh -c 'timeout -s TERM -k 2 "$0" bash -c "$1" & t=$!; wait $t; rc=$?; kill -KILL -$t 2>/dev/null; exit $rc' <limit> <command>
```

`DockerExecutor` runs this as `docker exec -u agent -w /home/agent/task <container-id> …` with no `-t`
and no `-i`. `LocalExecutor` (host units) runs the same argv without the `docker exec` prefix.

## `bench/run.sh` (on the host, `make bench`)

```
bench/run.sh [--out DIR] [--task ID ...]
```

1. Requires `GIT_SHA` and the pins in the environment (the Makefile exports them).
2. Resolves the output directory with `realpath` and creates it. With `--out DIR`, it passes
   `--out DIR` on to the tool (exactly DIR). Without it, it passes `bench/out` as `BENCH_OUT` only, and
   the tool stamps a run directory beneath it.
3. Runs `docker run --rm` on `timelike-bench-driver:local` with:
   - `-u $(id -u):$(id -g) --group-add <socket gid>`
   - `-v /var/run/docker.sock:/var/run/docker.sock`
   - `-v DIR:DIR` (the same absolute path; `DIR` is `--out`'s directory, or the `bench/out` base)
   - `-e BENCH_GIT_SHA -e BENCH_OUT=DIR -e BENCH_BASE_DIGEST=$DEBIAN_IMAGE -e BENCH_REPRODUCE`

   Then it passes the arguments on to `timelike-bench run`. **No other environment is forwarded** (RB9).

## Report layout (`report.txt`)

*(Amended by modify, send `…-080659`, after the operator's D2 reading: the first line is the operator's
text, and every task section explains itself — FR-9a.)*

```
FAKE-AGENT BENCH PIPELINE DEMO RUN -- This is not a test of timelike, rather a test of the bench test itself (its presentation and usefulness to the human user). The agent's policy was written by timelike's own builders.
Measured by the project's own maintainer. Reproduce: make bench
Timelike <revision> · vanilla <image_id> (base <base_digest>; same base, user and git, without timelike's layers) · harness timelike-fake-agent 1 · model none (deterministic fake agent) · invocation bash -c, no TTY

## Timelike loses (N)
### <task-id> — <goal>
Tests: <capability>. <what differs between the two images for this task>.
Verdict: Timelike loses — vanilla completed; timelike failed: check failed: <the check's reason>. A run that ends failed ranks below one that ends completed, whatever the turns.
metric                            vanilla     timelike
ending                            completed   failed
turns                             4           1
failed commands (hung included)   1           0
hangs                             0           0
tool calls                        4           1
wall-clock                        0.4 s       0.1 s

What happened in vanilla:
  1. `<command>` → exit 1: <first line of stderr>
  2. `<command>` → hung: killed at the 120 s limit
  3. `<command>` → exit 0
  Ended: completed — the check confirmed the goal.
  Why: <a note written with the task, printed only when this arm ended this way>.

What happened in timelike:
  1. `<command>` → exit 0
  Ended: failed — check failed: <the check's reason>.
  Why: <note, if one matches "timelike:failed">.

## Ties (N)
...
## Timelike wins (N)
...
## Not benchable on this path
- <capability>: <reason>

## Appendix: tokens
- <task> · <environment>: not recorded — the fake agent uses no model
```

The verdict line names what decided it: the endings when they differ, else turns, else failed or hung
commands; a tie says all three are equal. For a live run (not in slice 0), the first line is instead
`LIVE RUN — <harness> <version>, model <id>; a single repetition, no spread (slice 2)`.
