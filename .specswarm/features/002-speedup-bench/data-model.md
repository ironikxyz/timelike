# Data model — 002 speedup bench (slice 0)

All types are stdlib `dataclasses` (frozen where possible) in `bench/benchlib/`. JSON forms are in
[contracts/trace-schema.md](contracts/trace-schema.md).

## Task (`catalog.py`)

| Field | Type | Notes |
|---|---|---|
| `id` | str | kebab-case, unique. Part of each trace's file name |
| `version` | int | Bumped whenever the setup, policy or check changes. Recorded in every trace |
| `capability` | str | The feature-001 capability it exercises |
| `goal` | str | One line, shown in the report |
| `prerequisites` | tuple[str, ...] | OS packages. **Each must be present in both images** (RB1). Slice 0: `("git",)` |
| `setup` | str | Bash, run through the executor before the run. Not counted. A non-zero exit fails the run as `failed`, with reason `setup failed` |
| `policy` | Policy | See below |
| `check` | str | Bash, run through the executor after the policy ends. Exit 0 means the goal holds. Not counted |
| `expected` | str | The research RB4 prediction, shown only in `--verbose`. It is never used for scoring |

`NOT_BENCHABLE`: a tuple of `(capability, reason)`. It is printed in the report's scope note (RB4).

## Policy and Step (`fakeagent.py`)

A policy is an ordered tuple of `Step`s and a start id. It is **data**, interpreted by one pure
function:

```
next_step(policy: Policy, current: str, obs: Observation) -> str
```

The function takes **no environment argument**, which is how the fake agent is environment-blind by
construction (FR-11, spec Assumption 6).

| Step field | Type | Notes |
|---|---|---|
| `id` | str | Unique within the policy |
| `command` | str | Run as `bash -c` |
| `on_ok` | str | The next step id, or a terminal |
| `on_fail` | str | Taken on a non-zero exit that is not a hang |
| `on_hang` | str | Taken on a hang |

**Terminals:**
- `DONE`: run the check
- `GIVE_UP:<reason>`: ending `failed`
- `ESCALATE:<reason>`: ending `escalated`

**Observation:** `exit_code: int`, `hung: bool`, plus `stdout_head: str` and `stderr_head: str`, which
are passed on but not branched on in slice 0 (RB11 item 3).

**Turn accounting.** The fake agent takes one tool call per turn, so `turns == tool_calls` for the
fake agent. The trace keeps both, because a real harness can make several calls in one turn.

**Loop guard.** A policy may revisit a step at most 3 times. A 4th visit ends the run `failed`, with
reason `policy loop`. This is a P2 guard against a badly written policy.

## ToolCall (`trace.py`)

| Field | Type | Notes |
|---|---|---|
| `seq` | int | 1-based |
| `turn` | int | |
| `command` | str | |
| `exit_code` | int | The wrapper's exit code |
| `duration_ms` | int | Driver monotonic time, around `docker exec` |
| `hung` | bool | `exit_code ∈ {124, 137}` **and** the duration is at least the limit, or the driver backstop fired |
| `stdout_bytes`, `stderr_bytes` | int | Every byte emitted |
| `passed_bytes` | int | Bytes the harness passed on to the agent |
| `harness_cut` | bool | True if `passed_bytes` is less than the total |
| `stderr_head` | str | The first 2 KB of stderr, kept for slice-1 categorisation (FR-14) |

The fake harness passes at most `HARNESS_PASS_BYTES = 30000` bytes per stream, a documented stand-in
for common harness caps. The field exists so plan's byte-cap question becomes answerable (send, flagged
by plan).

## Identity (`trace.py`)

Every field is required and non-empty (FR-8):
- `bench_revision`
- `environment`: `vanilla` or `timelike`
- `image_id`
- `image_revision`: the label; must equal `bench_revision`
- `base_digest`
- `harness_name`, `harness_version`
- `model_id`
- `invocation`: `bash -c`
- `task_id`, `task_version`
- `call_limit_s`, `run_limit_s`
- `reproduce`: the command

The fake agent is:
- `harness_name = "timelike-fake-agent"`
- `harness_version = FAKE_AGENT_VERSION`, a constant bumped whenever the interpreter changes
- `model_id = "none (deterministic fake agent)"`

## Trace (`trace.py`)

The fields are `schema_version`, `identity`, `calls: list[ToolCall]`, `totals`, `ending`, `tokens` and
`extensions`.

- **`totals`**: `turns`, `tool_calls`, `nonzero_exits`, `hangs` and `wall_clock_ms`. Always **derived
  from `calls`** (and the run's own clock), never counted separately, so they cannot disagree.
- **`ending`**: `{kind, reason}`, where `kind` is one of `completed`, `escalated`, `failed`, `hung`.
  `hung` is used only when the **run** limit is exceeded. A hung *call* followed by recovery can still
  end `completed`.
- **`tokens`**: `{"recorded": false, "reason": "..."}` or `{"recorded": true, "input": n, "output": n}`.
  Zero is never written for an absent count (FR-7).
- **`extensions`**: an object, empty in slice 0. It is where slice 1 adds `arm`, per-call `category`
  and similar fields, without changing existing fields (FR-14).

**Validation** (`trace.validate`) rejects:
- any empty identity field
- an unknown ending kind
- totals that disagree with `calls`
- a `schema_version` it doesn't know

The writer calls `validate` before writing, so an invalid trace is never written.

## Comparison and report (`report.py`)

For each task, the report pairs the vanilla and timelike traces.

**The verdict is from timelike's side:**
1. Compare the endings, ranked `completed` > `escalated` > `failed` > `hung`.
2. If they are equal, compare turns (fewer wins).
3. If still equal, compare `nonzero_exits + hangs` (fewer wins).
4. If still equal, the task is a **tie**.

Wall-clock time is shown but never decides a verdict: it is noise in a single run, and slice 2 brings
repetitions.

**Sections, in order:**
1. first line
2. preamble
3. **Timelike loses**
4. **Ties**
5. **Timelike wins**
6. scope note: the not-benchable capabilities
7. `## Appendix: tokens`

A missing pair (only one trace for a task) is listed under the losing section as `incomplete`, never
dropped.
