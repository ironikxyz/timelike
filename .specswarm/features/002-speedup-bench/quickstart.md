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
