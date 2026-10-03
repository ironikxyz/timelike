"""runner — one task in one environment → one trace; the bench over the catalog (FR-1, FR-4, FR-6..8).

A run is: open a fresh session (a task container, or a temp dir on the host lane), run the task's
setup, walk the fake agent's policy one tool call per turn, run the task's check, close the session.
Only the policy's calls are counted and timed; setup and check belong to the bench, not to the agent,
so they are outside the trace's calls and its wall-clock.

Endings (trace-schema rule 3):
- the walk reaches DONE and the check exits 0          → completed
- the walk reaches DONE and the check fails            → failed, "check failed: …"
- GIVE_UP:<reason> (including the loop guard)           → failed, <reason>
- ESCALATE:<reason>                                     → escalated, <reason>
- the run limit passes, or the driver's backstop fires → hung. A hung CALL followed by recovery is
  not a hung run: it ends however the walk ends, with the hang counted
- setup fails                                           → failed, "setup failed: …", no calls

Every session is closed in a `finally`, so a failed run never leaves a container behind.

The harness passes at most HARNESS_PASS_BYTES of each stream on to the agent (a documented stand-in
for real harness caps); what it cut is recorded per call, so plan's byte-cap question becomes
answerable from traces later (send, "flagged by plan").
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from benchlib import fakeagent as fa
from benchlib.catalog import Task
from benchlib.executor import CallResult, Executor
from benchlib.trace import Ending, Identity, Tokens, ToolCall, Trace, derive_totals, write_trace

HARNESS_PASS_BYTES = 30000  # per stream
STDERR_HEAD_KEEP = 2048
OBS_HEAD_KEEP = 2048
INVOCATION = "bash -c"
NO_TOKENS = Tokens(recorded=False, reason="the fake agent uses no model")


@dataclass(frozen=True)
class Limits:
    # Claude Code's default call timeout, the harness 001's hook limit (60 s) is sized for: a hook's own
    # verdict arrives inside a call, as it would under that harness (001 cycle 5, discovery revision 7).
    # It was 30 s, above 001's 20 s git bound, until then.
    call_s: int = 120
    run_s: int = 300


@dataclass(frozen=True)
class RunContext:
    bench_revision: str
    base_digest: str
    reproduce: str
    limits: Limits = Limits()


class Session(Protocol):
    executor: Executor

    def close(self) -> None: ...


@dataclass(frozen=True)
class Environment:
    name: str  # vanilla | timelike
    image_id: str
    image_revision: str
    open_session: Callable[[], Session]


def _first_line(data: bytes, fallback: str) -> str:
    for line in data.decode("utf-8", "replace").splitlines():
        if line.strip():
            return line.strip()[:200]
    return fallback


def _passed(r: CallResult) -> int:
    return min(r.stdout_bytes, HARNESS_PASS_BYTES) + min(r.stderr_bytes, HARNESS_PASS_BYTES)


def _call(seq: int, command: str, r: CallResult) -> ToolCall:
    passed = _passed(r)
    return ToolCall(
        seq=seq,
        turn=seq,  # the fake agent takes one tool call per turn (data-model)
        command=command,
        exit_code=r.exit_code,
        duration_ms=r.duration_ms,
        hung=r.hung,
        stdout_bytes=r.stdout_bytes,
        stderr_bytes=r.stderr_bytes,
        passed_bytes=passed,
        harness_cut=passed < r.stdout_bytes + r.stderr_bytes,
        stderr_head=r.stderr_head[:STDERR_HEAD_KEEP].decode("utf-8", "replace"),
    )


def identity_for(task: Task, env: Environment, ctx: RunContext) -> Identity:
    return Identity(
        bench_revision=ctx.bench_revision,
        environment=env.name,
        image_id=env.image_id,
        image_revision=env.image_revision,
        base_digest=ctx.base_digest,
        harness_name=fa.FAKE_AGENT_NAME,
        harness_version=fa.FAKE_AGENT_VERSION,
        model_id=fa.MODEL_ID,
        invocation=INVOCATION,
        task_id=task.id,
        task_version=task.version,
        call_limit_s=ctx.limits.call_s,
        run_limit_s=ctx.limits.run_s,
        reproduce=ctx.reproduce,
    )


def _walk(
    task: Task, ex: Executor, limits: Limits, clock: Callable[[], float]
) -> tuple[list[ToolCall], Ending]:
    walker = fa.Walker(task.policy)
    calls: list[ToolCall] = []
    started = clock()
    while not walker.finished:
        if clock() - started >= limits.run_s:
            return calls, Ending("hung", f"run limit of {limits.run_s} s exceeded")
        command = walker.command
        r = ex.run(command, limits.call_s)
        calls.append(_call(len(calls) + 1, command, r))
        if r.backstop:
            return calls, Ending(
                "hung", f"the environment did not conclude call {len(calls)} (driver backstop)"
            )
        walker.advance(
            fa.Observation(
                exit_code=r.exit_code,
                hung=r.hung,
                stdout_head=r.stdout_head[:OBS_HEAD_KEEP].decode("utf-8", "replace"),
                stderr_head=r.stderr_head[:OBS_HEAD_KEEP].decode("utf-8", "replace"),
            )
        )
    kind = fa.terminal_kind(walker.current)
    if kind == "give_up":
        return calls, Ending("failed", fa.terminal_reason(walker.current))
    if kind == "escalate":
        return calls, Ending("escalated", fa.terminal_reason(walker.current))
    return calls, Ending("completed", "check pending")  # DONE: the caller runs the check


def run_task(
    task: Task, env: Environment, ctx: RunContext, clock: Callable[[], float] = time.monotonic
) -> Trace:
    ident = identity_for(task, env, ctx)
    session = env.open_session()
    try:
        ex = session.executor
        setup = ex.run(task.setup, ctx.limits.call_s)
        if setup.exit_code != 0 or setup.hung:
            why = "hung" if setup.hung else _first_line(setup.stderr_head, f"exit {setup.exit_code}")
            return _trace(ident, [], Ending("failed", f"setup failed: {why}"), 0)
        started = clock()
        calls, ending = _walk(task, ex, ctx.limits, clock)
        wall_ms = int((clock() - started) * 1000)
        if ending.kind == "completed":
            check = ex.run(task.check, ctx.limits.call_s)
            if check.exit_code == 0 and not check.hung:
                ending = Ending("completed", "check passed")
            else:
                why = "hung" if check.hung else _first_line(check.stderr_head, f"exit {check.exit_code}")
                ending = Ending("failed", f"check failed: {why}")
        return _trace(ident, calls, ending, wall_ms)
    finally:
        session.close()


def _trace(ident: Identity, calls: Sequence[ToolCall], ending: Ending, wall_ms: int) -> Trace:
    return Trace(
        identity=ident,
        calls=tuple(calls),
        totals=derive_totals(calls, wall_ms),
        ending=ending,
        tokens=NO_TOKENS,
    )


def trace_path(out: Path, task_id: str, env_name: str) -> Path:
    return out / "traces" / f"{task_id}--{env_name}.json"


def run_bench(
    tasks: Iterable[Task],
    environments: Sequence[Environment],
    ctx: RunContext,
    out: Path,
    clock: Callable[[], float] = time.monotonic,
) -> list[Trace]:
    """Each task in each environment, in the order given (vanilla first), writing each trace as it ends."""
    traces: list[Trace] = []
    for task in tasks:
        for env in environments:
            t = run_task(task, env, ctx, clock)
            write_trace(t, trace_path(out, task.id, env.name))
            traces.append(t)
    return traces
