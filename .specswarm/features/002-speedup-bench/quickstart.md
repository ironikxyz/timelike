# Quickstart — speedup bench (slice 0)

**Operator, on the Docker host**, from a clean checkout of `code/`:

```bash
make bench                              # builds agent, vanilla and driver images; runs all 4 tasks
make bench TASKS=git-rebase-continue    # one task
less bench/out/<run-id>/report.txt      # the D2 report
```

`make test` runs the same bench inside the e2e step (`tests/e2e/speedup-bench.bats`), checks the traces
and report with an independent validator, and shows that a blanked stamp and a planted key both fail.
`make scan` now scans three images.

**Reading the report (D2).**
- **Line 1:** what produced it. A fake-agent run opens with "FAKE-AGENT BENCH PIPELINE DEMO RUN -- This
  is not a test of timelike, rather a test of the bench test itself…".
- **Line 3:** exactly what was compared: the revisions, the vanilla definition, the harness and the
  model.
- **The sections:** losing tasks first, then ties, then wins. Each task says what it tests and what
  differs between the images, gives the verdict in words, compares completion, turns and failed
  commands (with hangs, tool calls and wall-clock time), then tells what happened in each arm, call by
  call, and why it ended as it did.

**Expected slice-0 shape** (research RB4 predictions, not results; the hook tasks moved with feature 001's
cycle 5, discovery revision 7, when repository hooks began to run, bounded):
- `git-inspect` and `git-commit-hook-rejects`: ties (until 001's cycle 5, timelike lost the rejects task)
- `git-rebase-continue` and `git-commit-hook-hangs`: timelike wins (on the hangs task, timelike's
  60 s hook limit ends the commit with a verdict inside the 120 s call; vanilla hangs to the call limit)

A report that disagrees with this shape is information, not an error.

**Host lane** (no Docker): `make test-host PYTHON=<venv python>` runs the bench units, including the
real wrapper against local hangs and detached children.

---

# Quickstart — slice 1 (Cycle 4)

**CI and the Docker lane** stay key-free. `make bench` runs the fake agent in three arms (vanilla, timelike not told,
timelike told). `make test` also runs the live path against the model stand-in (`--standin`), with both live harnesses
and no key, and the category probe in both images.

## The live run (the mentor's)

One command, from `code/` on the Docker host, after `make bench-images` at the revision under test:

```bash
BENCH_KEY_FILE=/path/outside/code/openrouter.key make bench-live DRY_RUN=1   # the plan only: no request, no spend
BENCH_KEY_FILE=/path/outside/code/openrouter.key make bench-live             # the whole catalog, live
```

It runs all 5 tasks under both live harnesses (OpenCode 1.19.0, Codex CLI 0.162.1), in all three arms, once each
(n = 1, labelled so): 30 runs.

**What it needs:**
- `BENCH_KEY_FILE`: the OpenRouter key, one line, in a file **outside** the repository, mode `0600`, owned by you.
  It is refused otherwise; the refusal names the path and the property, never the value.
- Optional caps, with their defaults:
  - `BENCH_TURN_CAP=30`: turns per run;
  - `BENCH_SPEND_CAP_USD=10.00`: per invocation. When it is reached, the remaining cells are recorded `stopped`
    without a request;
  - 900 s per run (`bench/run.sh --run-limit S`).
- `BENCH_MODEL` defaults to `deepseek/deepseek-v4-pro-0813`. An undated id is refused.

**Spend estimate** (printed by the plan; research RB18): about $0.03 per turn, so about $7 for the catalog at a
typical 8 turns per run, and $27 at the turn cap. The default spend cap of $10 therefore binds. The figures recorded
are OpenRouter's own, read from each response.

**Where it lands:** `bench/out/<UTC stamp>/` on the host:
- `report.txt`: one section per harness, with the adoption table (told against not-told), categories, verdicts,
  then the infrastructure rows, and spend only in the appendix;
- `traces/<task>--<harness>--<arm>.json`;
- `transcripts/`: each harness's own output.

Every file was checked for the key's value before it was written.

`timelike-bench report bench/out/<stamp>` re-reports from the traces alone.
