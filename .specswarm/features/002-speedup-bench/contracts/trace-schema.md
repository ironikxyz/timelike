# Contract: bench trace, schema v2 (slice 1)

*(Added in Cycle 4, declared. Schema v1, as slice 0 wrote it, follows unchanged below for the record. This build's
reader accepts schema 2 only: a schema-1 trace set is refused with
`schema_version: 1 is slice 0's trace; re-report it with a slice-0 build of the bench`, and slice 0's revision
re-reports it, which keeps FR-10 true per revision.)*

One JSON file per run, at `<out>/traces/<task-id>--<harness>--<arm>.json` (`<harness>` is `fake`, `opencode` or
`codex`). UTF-8, sorted keys, 2-space indentation, a final newline. Only the driver writes it, through the write gate
(FR-31).

```json
{
  "schema_version": 2,
  "identity": {
    "bench_revision": "<40-hex>",
    "environment": "vanilla | timelike",
    "arm": "vanilla | not-told | told",
    "image_id": "sha256:<64-hex>",
    "image_revision": "<40-hex, equal to bench_revision>",
    "base_digest": "debian:trixie-slim@sha256:<64-hex>",
    "harness_name": "timelike-fake-agent | opencode | codex",
    "harness_version": "<the pin>",
    "harness_reported_version": "<what the harness printed for --version>",
    "model_id": "<the pin>",
    "models_answered": ["<each distinct model id the provider answered with>"],
    "invocation": "bash -c | opencode bash tool | codex exec_command",
    "output_streams": "separate | merged",
    "placement": "<told: the placement's result per harness file; otherwise empty>",
    "task_id": "python-missing-module",
    "task_version": 1,
    "call_limit_s": 120,
    "run_limit_s": 900,
    "turn_cap": 30,
    "timelike_tools": ["edit", "journal", "run", "..."],
    "reproduce": "make bench-live"
  },
  "calls": [
    {"seq": 1, "turn": 1, "command": "python3 report.py > out/totals.txt", "exit_code": 1, "duration_ms": 212,
     "hung": false, "stdout_bytes": 0, "stderr_bytes": 96, "passed_bytes": 96, "harness_cut": false,
     "stderr_head": "Traceback …", "category": "module-not-found", "timelike_tools": [], "through_timelike": []}
  ],
  "totals": {"turns": 5, "tool_calls": 5, "nonzero_exits": 2, "hangs": 0, "wall_clock_ms": 1840,
             "timelike_tool_calls": 0, "through_timelike_calls": 1,
             "by_category": {"module-not-found": 1, "network-denial": 1}},
  "ending": {"kind": "completed", "cause": "", "reason": "check passed"},
  "tokens": {"recorded": true, "input": 81234, "output": 2210},
  "spend": {"recorded": true, "usd": 0.1159, "source": "openrouter usage", "unknown_generations": 0},
  "extensions": {"relay": {"requests": 7, "turns": 6, "statuses": {"200": 7}}}
}
```

## Rules (schema 2)

Schema 1's rules 1 to 6 hold, with these changes and additions.

1. **Stamps.** Every string in `identity` is non-empty except `placement`, which is non-empty exactly when `arm` is
   `told`. `models_answered` may be empty (a run that ended before any answer). Integers are positive, except
   `turn_cap`, where 0 means no cap (the fake agent).
2. **Arms.** `environment` is `vanilla` exactly when `arm` is `vanilla`.
3. **Calls.** `category` is `""` exactly when `exit_code` is 0 and `hung` is false; otherwise it is one of
   `timeout`, `memory-kill`, `command-not-found`, `module-not-found`, `network-denial`, `other`. `timelike_tools` and
   `through_timelike` are lists of strings, and both are empty in the vanilla arm.
4. **Totals are derived** (schema 1's rule 2, and): `timelike_tool_calls` counts calls with a non-empty
   `timelike_tools`; `through_timelike_calls` counts calls with a non-empty `through_timelike`; `by_category` maps each
   category present to its count, and lists no category with a count of 0.
5. **Endings.** `kind` ∈ {`completed`, `escalated`, `failed`, `hung`, `stopped`}. `cause` is non-empty exactly when
   `kind` is `stopped`, and is one of `api-rate-limit`, `api-error`, `api-unreachable`, `key-rejected`,
   `harness-exit`, `harness-unresponsive`, `turn-cap`, `spend-cap`, `placement`, `transcript-unreadable`, and
   *(Cycle 4 addendum, Item 25 (b))* `model-refused`.
6. **Spend** follows the tokens rule: `usd` (a number ≥ 0) and `source` are present only when `recorded` is true;
   otherwise `reason` says why. `unknown_generations` counts generations whose cost OpenRouter did not report; it is
   present when recorded. The fake agent records `{"recorded": false, "reason": "the fake agent uses no model"}`.
7. **Extensions.** `extensions.relay`, on live runs: the relay's own counts for the run (requests, turns, statuses).
   Readers ignore other keys under `extensions`. *(Cycle 4 addendum, Item 25 (b):)* it also carries `refused` (verdict
   → count, for requests the relay did not forward) and `senders`, a fixed sentence saying the relay cannot tell a
   harness's request from an agent command's. A told run whose setup failed records `placement: "not placed"`
   (lane 02s1-a, item 2).

---

# Schema v1 (slice 0, kept for the record)

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
