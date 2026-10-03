# Contract: bench trace, schema v1

One JSON file per run, at `<out>/traces/<task-id>--<environment>.json`. The file is UTF-8, uses
sorted keys and 2-space indentation, and ends with a newline. Only the driver writes it.

```json
{
  "schema_version": 1,
  "identity": {
    "bench_revision": "<40-hex>",
    "environment": "vanilla | timelike",
    "image_id": "sha256:<64-hex>",
    "image_revision": "<40-hex, equal to bench_revision>",
    "base_digest": "debian:trixie-slim@sha256:<64-hex>",
    "harness_name": "timelike-fake-agent",
    "harness_version": "1",
    "model_id": "none (deterministic fake agent)",
    "invocation": "bash -c",
    "task_id": "git-rebase-continue",
    "task_version": 1,
    "call_limit_s": 120,
    "run_limit_s": 300,
    "reproduce": "make bench TASKS=git-rebase-continue"
  },
  "calls": [
    {"seq": 1, "turn": 1, "command": "git rebase main", "exit_code": 1, "duration_ms": 212,
     "hung": false, "stdout_bytes": 310, "stderr_bytes": 96, "passed_bytes": 406,
     "harness_cut": false, "stderr_head": "..."}
  ],
  "totals": {"turns": 5, "tool_calls": 5, "nonzero_exits": 2, "hangs": 0, "wall_clock_ms": 1840},
  "ending": {"kind": "completed", "reason": "check passed"},
  "tokens": {"recorded": false, "reason": "the fake agent uses no model"},
  "extensions": {}
}
```

## Rules

1. **Stamps (FR-8).** Every `identity` value is non-empty.
   - `image_revision` must equal `bench_revision`, or the run was refused and no trace exists.
   - `base_digest` must contain `@sha256:`.
2. **Totals are derived.** `totals.tool_calls == len(calls)`. `nonzero_exits` counts calls with
   `exit_code != 0`, including hung calls. `hangs` counts calls with `hung == true`. `turns` is the
   largest `turn` value, or 0 when there are no calls.
3. **Endings.**
   - `kind` ∈ {`completed`, `escalated`, `failed`, `hung`}.
   - `reason` is a single line, and is non-empty.
   - `completed` requires the task check to have exited 0.
4. **Tokens (FR-7).** A count is present only when `recorded` is true. There is never a zero stand-in.
5. **Extension (FR-14).**
   - A new field goes under `extensions` (a run-level field) or into a new key on a call.
   - An existing key never changes meaning.
   - A change that breaks either of those bumps `schema_version`.
   - Readers ignore unknown keys **under `extensions` only**.
6. **A task's failed setup** produces a trace with `calls: []` and the ending `failed` / `setup failed:
   <stderr first line>`, so a broken task is visible and never silently skipped.
