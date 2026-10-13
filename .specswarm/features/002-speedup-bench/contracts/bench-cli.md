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
commands; a tie says all three are equal. *(Slice 0's rule. Superseded in Cycle 4 by revision 8's order; see the
Slice 1 section below.)* For a live run (not in slice 0), the first line is instead
`LIVE RUN — <harness> <version>, model <id>; a single repetition, no spread (slice 2)`.

---

# Slice 1 (Cycle 4, send `bridge/sends/02-rev8-20261013-064725.md`), declared

Everything above holds except where this section says otherwise. Above, "vanilla, then timelike" becomes "each arm",
and the verdict line's "failed or hung commands" is replaced by the order below (revision 8).

## `timelike-bench`

```
timelike-bench run [--harness fake|opencode|codex ...] [--arm vanilla|not-told|told ...] [--task ID ...]
                   [--out DIR] [--call-limit S] [--run-limit S] [--turn-cap N] [--spend-cap USD]
                   [--dry-run] [--standin]
timelike-bench report DIR
timelike-bench catalog
timelike-bench categories [--probe]
```

- **`run`**, in order:
  1. Refuses an API-key-shaped variable in its own environment, as before (exit 4), for every harness: the key is
     never in the environment, only in a file.
  2. With the fake agent only (the default): refuses a set `BENCH_KEY_FILE` (exit 4, FR-32).
  3. With a live harness: refuses an undated `BENCH_MODEL` (exit 2); unless `--standin`, reads `BENCH_KEY_FILE` (a
     regular file, mode `0600`, owned by this user, one line; otherwise exit 4, naming the path and the property).
  4. **Prints the plan** (FR-34). `--dry-run` stops here, exit 0, with no Docker and no key.
  5. Checks the images' identity, as before, plus `timelike-bench-harness:local` for a live run.
  6. Reads the timelike tool list once (`timelike tools --json` in a throwaway container of the agent image).
  7. Live: creates the network, connects itself, starts the relay (and the stand-in, with `--standin`), creates the
     harness container.
  8. Runs each task × harness × arm, vanilla first, then not-told, then told; writes each trace as it ends; for a
     live run, also `transcripts/<task>--<harness>--<arm>.{jsonl,rollout.jsonl,stderr.txt}`.
  9. Writes `report.txt`; removes the harness container and the network.

  Exit 0 when every trace was written, whatever the endings (as before), `stopped` rows included. Exit 1 when the
  write gate refuses a file (FR-31), naming it.
- **`--arm`** defaults to all three; **`--harness`** defaults to `fake`. Live and fake harnesses are not mixed in
  one invocation (exit 2): a report is either a pipeline demo or a live run, never both.
- **`--standin`** runs the live harnesses against `benchlib.standin`, in the driver, with no key. The report's
  first line then says so: `STAND-IN MODEL RUN -- live harnesses drove a scripted model stand-in, not a model; this
  tests the bench's live path, not timelike.`
- **`categories`** lists the categories and their rules (no Docker). **`categories --probe`** starts one task
  container of each image (`--network none`, `--memory 64m`), runs one real failing command per category, prints
  `<image> · <category expected> · <category given> · <command> · <evidence>`, and exits 1 if any differ.
- **Environment, added:** `BENCH_KEY_FILE`, `BENCH_MODEL` (default `deepseek/deepseek-v4-pro-0813`),
  `BENCH_UPSTREAM` (default `https://openrouter.ai`), `BENCH_TURN_CAP` (30), `BENCH_SPEND_CAP_USD` (10.00),
  `BENCH_MODEL_PRICE_IN` and `BENCH_MODEL_PRICE_OUT` (USD per million tokens), `BENCH_OPENCODE_VERSION` and
  `BENCH_CODEX_VERSION` (the pins). All are passed by `bench/run.sh` from `pins.env` or the operator's shell.
- **First line** (rule 12) scope: `FAKE-AGENT BENCH PIPELINE DEMO RUN -- not a test of timelike`, `STAND-IN MODEL
  RUN -- not a test of timelike`, or `LIVE RUN n=1`.

## `bench/run.sh`, added

```
bench/run.sh [--out DIR] [--task ID ...] [--harness H ...] [--arm A ...] [--dry-run] [--standin]
             [--turn-cap N] [--spend-cap USD]
```

- With `BENCH_KEY_FILE` set: refuses it on the host unless it is a regular file outside the repository, mode
  `0600`, owned by the user running the script (exit 4, naming the path and the property, never the value). Mounts
  it read-only at `/run/timelike-bench/key` and passes `-e BENCH_KEY_FILE=/run/timelike-bench/key`.
- Passes, by name and value from its own environment, only: `BENCH_MODEL`, `BENCH_UPSTREAM`, `BENCH_TURN_CAP`,
  `BENCH_SPEND_CAP_USD`, `BENCH_MODEL_PRICE_IN`, `BENCH_MODEL_PRICE_OUT`, `BENCH_OPENCODE_VERSION`,
  `BENCH_CODEX_VERSION`. None is key-shaped, and nothing else is forwarded (RB9).
- `make bench-live` = `bench/run.sh --harness opencode --harness codex`; `make bench-live DRY_RUN=1` adds `--dry-run`.

## The live exec (`harness.py`), identical for every arm

```
docker exec -u agent -w /home/agent/task -e OPENROUTER_API_KEY -e HOME=/home/agent -e CODEX_HOME=/home/agent/.codex \
  [-e OPENCODE_CONFIG_CONTENT -e OPENCODE_DISABLE_…] <container> \
  sh -c '<the wrapper>' <run limit> '<harness argv, quoted> > ~/.bench/stdout.jsonl 2> ~/.bench/stderr.txt'
```

The value of each `-e NAME` without `=` comes from the docker CLI's own environment, which the driver sets for that
one exec. Only the harness exec carries `OPENROUTER_API_KEY`.

## Report layout, schema 2

```
<first line>
Measured by the project's own maintainer. Reproduce: <command>
Timelike <revision> · vanilla <image_id> (base <digest>; same base, user and git, without timelike's layers) · model <pin> · arms: vanilla, timelike not told, timelike told

# Harness: <name> <version> (reported <version>) · answered by <model ids> · invocation <…>

## Adoption: timelike tool calls per arm
arm                  runs   tool calls   timelike tool calls   tools used         through timelike
vanilla              5      31           —                     —                  —
timelike, not told   5      29           1                     run 1              2
timelike, told       5      24           7                     run 4, view 3      2

## Failure categories per arm (where the failed call ran: the task container)
category            vanilla   timelike, not told   timelike, told
command not found   0         0                    0
…
other               1         0                    0

## Timelike loses (N)
### <task-id> — <goal>
Tests: <capability>. <difference>.
Not told vs vanilla: Verdict: Timelike loses — both completed in 4 turns; timelike, not told had 1 hang to vanilla's 0.
Told vs vanilla: Verdict: Tie — both completed, in 4 turns, with 0 hangs and 1 failed command.
metric                            vanilla     timelike, not told   timelike, told
ending                            completed   completed            completed
turns                             4           4                    4
hangs                             0           1                    0
failed commands (hung included)   1           1                    1
tool calls                        4           4                    4
wall-clock                        3.1 s       9.4 s                3.0 s

What happened in vanilla:
  1. `<command>` → exit 127 [command not found]: <first output line>
  …
## Ties (N)
## Timelike wins (N)
## Not compared: infrastructure (N)
- <task-id> · timelike, told: stopped (api-rate-limit) — OpenRouter answered 429 to the last request

# Not benchable on this path
- <capability>: <reason>

# Appendix: tokens and spend
- <harness> · <task> · <arm>: input 81234, output 2210; spend $0.1159 (openrouter usage)
Total spend: $<sum> over <n> runs (OpenRouter's figures; <k> generations not reported)
```

- **The verdict order (revision 8, FR-48):** ending, turns, hangs, failed commands. The sentence names what decided it
  and quotes only counts in the table. A tie quotes the turns, hangs and failed commands. The table's rows run in
  that order.
- **Placement in sections:** a task goes under the worse of its two verdicts (`incomplete` counts as a loss). A
  comparison with a `stopped` side is not made, and that run is listed under "Not compared".
- **Fake agent:** the adoption table carries one more line: `The fake agent cannot read a placement: its told and
  not-told arms run the same policy.`
- Token and spend figures appear only under the appendix heading.
