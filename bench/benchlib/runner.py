"""runner — one task, in one arm, under one harness → one trace; and the bench over the catalog.

**Cells** (slice 1, FR-17): a task runs once per harness in each arm, in this order: `vanilla` (the vanilla
image), `not-told` (the timelike image, no announcement placed) and `told` (the same image, the announcement
placed by `timelike announce --install` after setup and before the agent starts, FR-18). Every run opens a
fresh session (a task container, or a temp dir on the host lane), runs the task's setup, drives the agent,
runs the task's check, and closes the session. Setup, placement and check belong to the bench, not to the
agent, so they are outside the trace's calls and its wall-clock.

**The fake agent** (slice 0's path) walks its policy one tool call per turn through the bench's own wrapper.
Endings (trace-schema rule 3):
- the walk reaches DONE and the check exits 0          → completed
- the walk reaches DONE and the check fails            → failed, "check failed: …"
- GIVE_UP:<reason> (including the loop guard)           → failed, <reason>
- ESCALATE:<reason>                                     → escalated, <reason>
- the run limit passes, or the driver's backstop fires → hung. A hung CALL followed by recovery is not a
  hung run: it ends however the walk ends, with the hang counted
- setup fails                                           → failed, "setup failed: …", no calls

**A live harness** (FR-24 to FR-37) runs in the task container under the run limit, talking to the model only
through the relay, which counts its turns and spend and enforces the caps. Its calls come from its own
transcript (benchlib.transcripts), and its ending from what was observed (`live_ending`): a cap, an unreadable
transcript, the run limit, the provider's last answer, the harness's exit, then the check. An infrastructure
cause ends the run `stopped` (FR-36), which the report never counts as a loss.

Every call gets its category (FR-40) and, in the timelike arms, the timelike tools its command words name and
what it ran through timelike (FR-19). Every session is closed in a `finally`, so a failed run never leaves a
container behind. Every file is written through the key gate (FR-31).

The fake harness passes at most HARNESS_PASS_BYTES of each stream on to the agent (a documented stand-in for
real harness caps); what it cut is recorded per call, so plan's byte-cap question is answerable from traces.
"""

from __future__ import annotations

import dataclasses
import os
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from benchlib import adoption
from benchlib import fakeagent as fa
from benchlib import harness as hz
from benchlib.catalog import Task
from benchlib.categories import categorize
from benchlib.executor import CallResult, Executor
from benchlib.keyfile import Gate
from benchlib.relay import Accounting, Relay, generation_cost
from benchlib.standin import StandIn
from benchlib.trace import (
    NO_SPEND,
    Ending,
    Identity,
    Spend,
    Tokens,
    ToolCall,
    Trace,
    derive_totals,
    write_trace,
)
from benchlib.transcripts import Parsed, TranscriptUnreadable

HARNESS_PASS_BYTES = 30000  # per stream
STDERR_HEAD_KEEP = 2048
OBS_HEAD_KEEP = 2048
INVOCATION = "bash -c"
NO_TOKENS = Tokens(recorded=False, reason="the fake agent uses no model")
ARMS = ("vanilla", "not-told", "told")
FAKE_KEY = "fake"
KEY_PLACEHOLDER = (
    "stand-in-placeholder-not-a-key"  # what a harness gets for its key variable against the stand-in
)
PLACED_STATES = ("placed", "replaced", "current")


@dataclass(frozen=True)
class Limits:
    # Claude Code's default call timeout, the harness 001's hook limit (60 s) is sized for: a hook's own
    # verdict arrives inside a call, as it would under that harness (001 cycle 5, discovery revision 7).
    # It was 30 s, above 001's 20 s git bound, until then.
    call_s: int = 120
    run_s: int = 300


LIVE_RUN_S = 900  # FR-33: a live run's wall-clock limit; the fake agent's stays Limits.run_s


@dataclass(frozen=True)
class RunContext:
    bench_revision: str
    base_digest: str
    reproduce: str
    limits: Limits = Limits()
    timelike_tools: tuple[str, ...] = ()  # read once per invocation from the timelike image (FR-19)


class Session(Protocol):
    """A run's container (or host directory). Two optional methods are looked up when used: `place()`, the
    told placement's result per harness file, and `oom_kills()`, the container's OOM count or None."""

    executor: Executor

    def close(self) -> None: ...


class LiveSession(Session, Protocol):
    def read(self, argv: Sequence[str]) -> tuple[int, str]: ...

    def harness_executor(self, exec_env: dict[str, str], key: str) -> Executor: ...


class PlacementFailed(Exception):
    """The told placement did not place the announcement for the harness that is about to run."""


class HarnessMismatch(Exception):
    """The harness in the image is not the pinned one (FR-23): every run of the invocation is refused."""


@dataclass(frozen=True)
class Environment:
    name: str  # vanilla | timelike
    image_id: str
    image_revision: str
    open_session: Callable[[], Session]


@dataclass(frozen=True)
class Cell:
    arm: str
    env: Environment


def cells(vanilla: Environment, timelike: Environment, arms: Sequence[str] = ARMS) -> list[Cell]:
    """The cells for one task under one harness, in ARMS order whatever order `arms` names them."""
    return [Cell(arm, vanilla if arm == "vanilla" else timelike) for arm in ARMS if arm in arms]


@dataclass
class Live:
    """A live harness's configuration for an invocation."""

    spec: hz.HarnessSpec
    relay: Relay
    relay_url: str  # the relay as a task container reaches it
    model: str
    turn_cap: int
    run_limit_s: int
    gate: Gate
    key: str | None = None  # None: the stand-in, which gets a placeholder
    upstream: str = "https://openrouter.ai"
    standin: StandIn | None = None
    stopped_for_all: str = ""  # "key-rejected" once OpenRouter has refused the key (FR-37)
    checked_version: str = ""


# --- shared -------------------------------------------------------------------------------------


def _first_line(data: bytes | str, fallback: str) -> str:
    text = data.decode("utf-8", "replace") if isinstance(data, bytes) else data
    for line in text.splitlines():
        if line.strip():
            return line.strip()[:200]
    return fallback


def _adopt(arm: str, command: str, tools: Sequence[str]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if arm == "vanilla":
        return (), ()
    return tuple(adoption.timelike_tools_in(command, tools)), tuple(adoption.through_timelike(command))


def _trace(
    ident: Identity,
    calls: Sequence[ToolCall],
    ending: Ending,
    wall_ms: int,
    tokens: Tokens = NO_TOKENS,
    spend: Spend = NO_SPEND,
    extensions: dict[str, object] | None = None,
) -> Trace:
    return Trace(
        identity=ident,
        calls=tuple(calls),
        totals=derive_totals(calls, wall_ms),
        ending=ending,
        tokens=tokens,
        spend=spend,
        extensions=dict(extensions or {}),
    )


def _oom(session: Session) -> int | None:
    reader = getattr(session, "oom_kills", None)
    return reader() if callable(reader) else None


def _place(session: Session, harness_files: Sequence[str]) -> str:
    """The placement's summary, or PlacementFailed when none of `harness_files` was placed (FR-18)."""
    place = getattr(session, "place", None)
    if not callable(place):
        raise PlacementFailed("this session cannot place the announcement")
    result = str(place())
    states = dict(part.split(": ", 1) for part in result.split("; ") if ": " in part)
    if not any(states.get(h, "").split(" ")[0] in PLACED_STATES for h in harness_files):
        raise PlacementFailed(f"the announcement was not placed for {' or '.join(harness_files)}: {result}")
    return result


def _check(ex: Executor, task: Task, ctx: RunContext) -> tuple[bool, str]:
    check = ex.run(task.check, ctx.limits.call_s)
    if check.exit_code == 0 and not check.hung:
        return True, "check passed"
    why = "hung" if check.hung else _first_line(check.stderr_head, f"exit {check.exit_code}")
    return False, f"check failed: {why}"


# --- the fake agent -----------------------------------------------------------------------------


def _passed(r: CallResult) -> int:
    return min(r.stdout_bytes, HARNESS_PASS_BYTES) + min(r.stderr_bytes, HARNESS_PASS_BYTES)


def _call(
    seq: int, command: str, r: CallResult, arm: str, ctx: RunContext, oom_rose: bool = False
) -> ToolCall:
    passed = _passed(r)
    output = (r.stdout_head + b"\n" + r.stderr_head).decode("utf-8", "replace")
    tools, through = _adopt(arm, command, ctx.timelike_tools)
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
        category=categorize(r.exit_code, r.hung, output, oom_rose),
        timelike_tools=tools,
        through_timelike=through,
    )


def identity_for(task: Task, cell: Cell, ctx: RunContext, placement: str = "") -> Identity:
    env = cell.env
    return Identity(
        bench_revision=ctx.bench_revision,
        environment=env.name,
        arm=cell.arm,
        image_id=env.image_id,
        image_revision=env.image_revision,
        base_digest=ctx.base_digest,
        harness_name=fa.FAKE_AGENT_NAME,
        harness_version=fa.FAKE_AGENT_VERSION,
        harness_reported_version=fa.FAKE_AGENT_VERSION,
        model_id=fa.MODEL_ID,
        models_answered=(),
        invocation=INVOCATION,
        output_streams="separate",
        placement=placement,
        task_id=task.id,
        task_version=task.version,
        call_limit_s=ctx.limits.call_s,
        run_limit_s=ctx.limits.run_s,
        turn_cap=0,
        timelike_tools=ctx.timelike_tools,
        reproduce=ctx.reproduce,
    )


def _walk(
    task: Task, ex: Executor, limits: Limits, clock: Callable[[], float], arm: str, ctx: RunContext
) -> tuple[list[ToolCall], Ending]:
    walker = fa.Walker(task.policy)
    calls: list[ToolCall] = []
    started = clock()
    while not walker.finished:
        if clock() - started >= limits.run_s:
            return calls, Ending("hung", f"run limit of {limits.run_s} s exceeded")
        command = walker.command
        r = ex.run(command, limits.call_s)
        calls.append(_call(len(calls) + 1, command, r, arm, ctx))
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


def _with_oom(calls: list[ToolCall], arm: str, ctx: RunContext) -> list[ToolCall]:
    """Re-categorise the 137s once the container's OOM count is known to have risen during the run."""
    out = []
    for c in calls:
        if c.exit_code == 137 and not c.hung:
            c = dataclasses.replace(c, category=categorize(c.exit_code, c.hung, c.stderr_head, True))
        out.append(c)
    return out


def run_task(
    task: Task, cell: Cell | Environment, ctx: RunContext, clock: Callable[[], float] = time.monotonic
) -> Trace:
    """The fake agent through one task in one cell; an Environment alone means its default arm (slice 0)."""
    if isinstance(cell, Environment):
        cell = Cell("vanilla" if cell.name == "vanilla" else "not-told", cell)
    ident = identity_for(task, cell, ctx)
    session = cell.env.open_session()
    try:
        ex = session.executor
        setup = ex.run(task.setup, ctx.limits.call_s)
        if setup.exit_code != 0 or setup.hung:
            why = "hung" if setup.hung else _first_line(setup.stderr_head, f"exit {setup.exit_code}")
            return _trace(ident, [], Ending("failed", f"setup failed: {why}"), 0)
        if cell.arm == "told":
            try:
                ident = identity_for(task, cell, ctx, _place(session, ("codex", "opencode", "claude-code")))
            except PlacementFailed as e:
                ident = identity_for(task, cell, ctx, "not placed")
                return _trace(ident, [], Ending("stopped", str(e).splitlines()[0], "placement"), 0)
        before = _oom(session)
        started = clock()
        calls, ending = _walk(task, ex, ctx.limits, clock, cell.arm, ctx)
        wall_ms = int((clock() - started) * 1000)
        after = _oom(session)
        if before is not None and after is not None and after > before:
            calls = _with_oom(calls, cell.arm, ctx)
        if ending.kind == "completed":
            ok, why = _check(ex, task, ctx)
            ending = Ending("completed" if ok else "failed", why)
        return _trace(ident, calls, ending, wall_ms)
    finally:
        session.close()


# --- a live harness -----------------------------------------------------------------------------


@dataclass(frozen=True)
class Observed:
    """What a live run showed, from which its ending is decided (data-model § Live run result)."""

    acct: Accounting
    harness_exit: int
    hit_run_limit: bool
    parsed: Parsed | None
    parse_error: str
    check_ok: bool
    check_why: str
    harness_said: str = ""  # the harness's last reported error, or its stderr's first line
    errors: tuple[str, ...] = field(default_factory=tuple)


def live_ending(o: Observed, run_limit_s: int, harness: str) -> Ending:
    """The run's ending, in the order data-model gives. Pure: units drive it with every combination."""
    a = o.acct
    if a.stopped_by:
        cap = "the turn cap" if a.stopped_by == "turn-cap" else "the spend cap"
        return Ending("stopped", f"{cap} was reached; the relay refused the next request", a.stopped_by)
    if o.hit_run_limit:
        if a.waiting > 0:
            return Ending(
                "stopped",
                f"run limit of {run_limit_s} s reached while waiting on the provider",
                "api-unreachable",
            )
        if a.last_asked_tools:
            return Ending("hung", f"run limit of {run_limit_s} s reached with a call in flight")
        return Ending(
            "stopped", f"run limit of {run_limit_s} s reached with no call in flight", "harness-unresponsive"
        )
    if o.parse_error:
        return Ending(
            "stopped", f"{harness}'s transcript could not be read: {o.parse_error}", "transcript-unreadable"
        )
    if o.check_ok:
        return Ending("completed", o.check_why)
    last = a.last_status
    if last in ("401", "403"):
        return Ending("stopped", f"the provider refused the key (HTTP {last})", "key-rejected")
    if last == "429":
        return Ending(
            "stopped", "the provider answered 429 (rate limit) to the last request", "api-rate-limit"
        )
    if last == "unreachable":
        return Ending("stopped", "the provider did not answer the last request", "api-unreachable")
    if last and not last.startswith("2") and last != "400 cap":
        return Ending("stopped", f"the provider answered HTTP {last} to the last request", "api-error")
    if o.harness_exit != 0:
        said = f": {o.harness_said}" if o.harness_said else ""
        return Ending("stopped", f"{harness} exited {o.harness_exit}{said}", "harness-exit")
    return Ending("failed", o.check_why)


def _live_identity(
    task: Task, cell: Cell, ctx: RunContext, live: Live, reported: str, placement: str, models: Sequence[str]
) -> Identity:
    spec = live.spec
    return Identity(
        bench_revision=ctx.bench_revision,
        environment=cell.env.name,
        arm=cell.arm,
        image_id=cell.env.image_id,
        image_revision=cell.env.image_revision,
        base_digest=ctx.base_digest,
        harness_name=spec.name,
        harness_version=spec.version,
        harness_reported_version=reported,
        model_id=live.model,
        models_answered=tuple(models),
        invocation=spec.invocation,
        output_streams="merged",
        placement=placement,
        task_id=task.id,
        task_version=task.version,
        call_limit_s=spec.call_limit_s or live.run_limit_s,
        run_limit_s=live.run_limit_s,
        turn_cap=live.turn_cap,
        timelike_tools=ctx.timelike_tools,
        reproduce=ctx.reproduce,
    )


def _live_calls(parsed: Parsed, arm: str, ctx: RunContext, oom_rose: bool) -> list[ToolCall]:
    calls = []
    for i, pc in enumerate(parsed.calls, start=1):
        tools, through = _adopt(arm, pc.command, ctx.timelike_tools)
        calls.append(
            ToolCall(
                seq=i,
                turn=max(1, pc.turn),
                command=pc.command,
                exit_code=pc.exit_code,
                duration_ms=pc.duration_ms,
                hung=pc.hung,
                stdout_bytes=0,  # both harnesses merge the streams (Assumption 11)
                stderr_bytes=pc.output_bytes,
                passed_bytes=pc.passed_bytes,
                harness_cut=pc.passed_bytes < pc.output_bytes,
                stderr_head=pc.output[:STDERR_HEAD_KEEP],
                category=categorize(pc.exit_code, pc.hung, pc.output, oom_rose),
                timelike_tools=tools,
                through_timelike=through,
            )
        )
    return calls


def _spend(acct: Accounting, live: Live) -> tuple[Tokens, Spend]:
    if not acct.generations:
        why = "no answer reached the relay" if acct.requests else "no request reached the relay"
        return Tokens(recorded=False, reason=why), Spend(recorded=False, reason=why)
    cost, unknown, looked = acct.cost_usd, list(acct.cost_unknown), False
    if live.key and unknown:
        still = []
        for gen in unknown:
            found = generation_cost(live.upstream, gen, live.key)
            if found is None:
                still.append(gen)
            else:
                cost, looked = cost + found, True
                live.relay.spent_usd += found
        unknown = still
    if live.standin is not None:
        source = "the model stand-in's usage (synthetic)"
    else:
        source = "openrouter usage" + (" and generation stats" if looked else "")
    tokens = Tokens(recorded=True, input=acct.tokens_in, output=acct.tokens_out)
    return tokens, Spend(recorded=True, usd=round(cost, 6), source=source, unknown_generations=len(unknown))


def _not_started(task: Task, cell: Cell, ctx: RunContext, live: Live, cause: str) -> Trace:
    ident = _live_identity(task, cell, ctx, live, "not run", "not placed" if cell.arm == "told" else "", ())
    why = {
        "spend-cap": f"not started: earlier runs reached the spend cap (${live.relay.spend_cap_usd:.2f})",
        "key-rejected": "not started: the provider refused the key on an earlier run",
    }[cause]
    no = "the run was not started"
    return _trace(ident, [], Ending("stopped", why, cause), 0, Tokens(False, no), Spend(False, no))


def run_live(
    task: Task,
    cell: Cell,
    ctx: RunContext,
    live: Live,
    out: Path,
    clock: Callable[[], float] = time.monotonic,
) -> Trace:
    if live.stopped_for_all:
        return _not_started(task, cell, ctx, live, live.stopped_for_all)
    if live.relay.spend_cap_reached:
        return _not_started(task, cell, ctx, live, "spend-cap")
    spec = live.spec
    session = cell.env.open_session()
    assert hasattr(session, "read") and hasattr(session, "harness_executor")  # noqa: S101 — a LiveSession
    lsession: LiveSession = session  # type: ignore[assignment]
    placement = ""
    try:
        ex = session.executor
        setup = ex.run(task.setup, ctx.limits.call_s)
        if setup.exit_code != 0 or setup.hung:
            why = "hung" if setup.hung else _first_line(setup.stderr_head, f"exit {setup.exit_code}")
            ident = _live_identity(
                task, cell, ctx, live, spec.version, "not placed" if cell.arm == "told" else "", ()
            )
            return _trace(ident, [], Ending("failed", f"setup failed: {why}"), 0)
        if cell.arm == "told":
            try:
                placement = _place(session, (spec.name,))
            except PlacementFailed as e:
                ident = _live_identity(task, cell, ctx, live, spec.version, "not placed", ())
                return _trace(ident, [], Ending("stopped", str(e).splitlines()[0], "placement"), 0)
        code, printed = lsession.read(spec.version_argv)
        reported = spec.reported(printed) if code == 0 else ""
        if reported != spec.version:
            raise HarnessMismatch(
                f"{spec.name} in the harness image reports {reported or 'nothing'!r}, the pin is "
                f"{spec.version} — rebuild with make bench-images"
            )
        if live.standin is not None:
            live.standin.set_script(fa.every_command(task.policy))
        before = _oom(session)
        live.relay.begin_run()
        hx = lsession.harness_executor(spec.exec_env(live.relay_url, live.model), live.key or KEY_PLACEHOLDER)
        prompt = hz.prompt_for(task.goal, "/home/agent/task")
        started = clock()
        r = hx.run(spec.command(live.relay_url, live.model, prompt), live.run_limit_s)
        wall_ms = int((clock() - started) * 1000)
        acct = live.relay.end_run()
        after = _oom(session)
        files = {
            "stdout": lsession.read(("cat", hz.STDOUT))[1],
            "stderr": lsession.read(("cat", hz.STDERR))[1],
        }
        if spec.name == "codex":
            files["rollout"] = lsession.read(hz.ROLLOUT_CMD)[1]
        stem = out / "transcripts" / f"{task.id}--{spec.name}--{cell.arm}"
        for kind, text in files.items():
            suffix = {"stdout": "stdout.jsonl", "stderr": "stderr.txt", "rollout": "rollout.jsonl"}[kind]
            live.gate.write_text(Path(f"{stem}.{suffix}"), text)
        check_ok, check_why = _check(ex, task, ctx)
        parsed: Parsed | None = None
        parse_error = ""
        try:
            parsed = spec.parse(files)
        except TranscriptUnreadable as e:
            parse_error = str(e)
        errors = parsed.errors if parsed else ()
        said = errors[-1] if errors else _first_line(files["stderr"], "")
        observed = Observed(
            acct=acct,
            harness_exit=r.exit_code,
            hit_run_limit=r.hung or r.backstop,
            parsed=parsed,
            parse_error=parse_error,
            check_ok=check_ok,
            check_why=check_why,
            harness_said=said[:200],
            errors=errors,
        )
        ending = live_ending(observed, live.run_limit_s, spec.name)
        if ending.cause == "key-rejected":
            live.stopped_for_all = "key-rejected"
        oom_rose = before is not None and after is not None and after > before
        calls = _live_calls(parsed, cell.arm, ctx, oom_rose) if parsed else []
        tokens, spend = _spend(acct, live)
        ident = _live_identity(task, cell, ctx, live, reported, placement, acct.models)
        ext: dict[str, object] = {
            "relay": acct.summary(),
            "harness_exit": r.exit_code,
            "transcripts": str(stem.relative_to(out)),
        }
        if live.standin is not None:
            ext["standin"] = True
        return _trace(ident, calls, ending, wall_ms, tokens, spend, ext)
    finally:
        session.close()


# --- the bench ----------------------------------------------------------------------------------


def trace_path(out: Path, task_id: str, harness: str, arm: str) -> Path:
    return out / "traces" / f"{task_id}--{harness}--{arm}.json"


def run_bench(
    tasks: Iterable[Task],
    cells_: Sequence[Cell],
    ctx: RunContext,
    out: Path,
    *,
    lives: Sequence[Live] = (),
    gate: Gate | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> list[Trace]:
    """Each task, under each harness (the fake agent when `lives` is empty), in each cell, writing each trace
    as it ends."""
    gate = gate or Gate()
    traces: list[Trace] = []
    for task in tasks:
        runs: list[Live | None] = list(lives) or [None]
        for live in runs:
            for cell in cells_:
                if live is None:
                    t = run_task(task, cell, ctx, clock)
                    key = FAKE_KEY
                else:
                    t = run_live(task, cell, ctx, live, out, clock)
                    key = live.spec.name
                write_trace(t, trace_path(out, task.id, key, cell.arm), gate)
                traces.append(t)
    return traces


def environ_with(name: str, value: str) -> dict[str, str]:
    """The docker CLI's own environment plus one variable, for a `-e NAME` exec (FR-30)."""
    env = dict(os.environ)
    env[name] = value
    return env
