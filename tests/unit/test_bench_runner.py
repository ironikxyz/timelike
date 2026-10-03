"""Units for bench/benchlib/runner.py (T008).

The four catalog tasks run through the REAL runner and the REAL wrapper (LocalExecutor) under the
vanilla and timelike emulations that test_bench_catalog.py defines, so the runner's endings and totals
are checked against research RB4 end to end on the host. The docker leg is the Docker lane's (R10).
Edge endings (backstop, run limit, escalation, harness cut) use a scripted executor.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import ClassVar

import pytest
import test_bench_catalog as cat_t
from benchlib import catalog, runner, trace
from benchlib import fakeagent as fa
from benchlib.executor import CallResult, Executor, LocalExecutor

SHA = "c" * 40
DIGEST = "debian:trixie-slim@sha256:" + "d" * 64
CTX = runner.RunContext(SHA, DIGEST, "make bench", runner.Limits(call_s=2, run_s=60))


class LocalSession:
    closed: ClassVar[list[str]] = []

    def __init__(self, root: Path, kind: str) -> None:
        self.dir = tempfile.mkdtemp(dir=root)
        home = Path(self.dir) / "home"
        home.mkdir()
        self.executor: Executor = LocalExecutor(self.dir, cat_t._env(kind, home))

    def close(self) -> None:
        LocalSession.closed.append(self.dir)


def local_env(kind: str, root: Path) -> runner.Environment:
    return runner.Environment(kind, "sha256:" + kind[0] * 64, SHA, lambda: LocalSession(root, kind))


# Research RB4 (hook-rejects corrected to 4 at T005; both hook tasks moved with 001 cycle 5, discovery
# revision 7): calls, non-zero exits, hangs, ending.
EXPECTED = {
    ("git-inspect", "vanilla"): (2, 0, 0, "completed"),
    ("git-inspect", "timelike"): (2, 0, 0, "completed"),
    ("git-rebase-continue", "vanilla"): (5, 2, 0, "completed"),
    ("git-rebase-continue", "timelike"): (4, 1, 0, "completed"),
    ("git-commit-hook-hangs", "vanilla"): (2, 1, 1, "completed"),  # the hung call is also non-zero
    ("git-commit-hook-hangs", "timelike"): (2, 1, 0, "completed"),  # the hook dispatcher's verdict
    ("git-commit-hook-rejects", "vanilla"): (4, 1, 0, "completed"),
    ("git-commit-hook-rejects", "timelike"): (4, 1, 0, "completed"),  # hooks run (001 cycle 5)
}


@pytest.fixture(scope="module")
def bench_run(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, list[trace.Trace]]:
    root = tmp_path_factory.mktemp("bench")
    out = root / "out"
    envs = [local_env("vanilla", root), local_env("timelike", root)]
    return out, runner.run_bench(catalog.CATALOG, envs, CTX, out)


def test_run_bench_writes_two_valid_traces_per_task_in_order(
    bench_run: tuple[Path, list[trace.Trace]],
) -> None:
    out, traces = bench_run
    assert [(t.identity.task_id, t.identity.environment) for t in traces] == [
        (task.id, env) for task in catalog.CATALOG for env in ("vanilla", "timelike")
    ]
    files = sorted(p.name for p in (out / "traces").iterdir())
    assert len(files) == 8
    assert trace.load_traces(out) == sorted(
        traces, key=lambda t: f"{t.identity.task_id}--{t.identity.environment}.json"
    )


@pytest.mark.parametrize(("task_id", "env"), sorted(EXPECTED))
def test_totals_and_endings_match_rb4(
    bench_run: tuple[Path, list[trace.Trace]], task_id: str, env: str
) -> None:
    t = next(x for x in bench_run[1] if (x.identity.task_id, x.identity.environment) == (task_id, env))
    got = (t.totals.tool_calls, t.totals.nonzero_exits, t.totals.hangs, t.ending.kind)
    assert got == EXPECTED[(task_id, env)], (t.ending, [c.command for c in t.calls])
    assert t.totals.turns == t.totals.tool_calls


def test_identity_is_fully_stamped(bench_run: tuple[Path, list[trace.Trace]]) -> None:
    for t in bench_run[1]:
        assert trace.validate(t) == []
        assert t.identity.harness_name == fa.FAKE_AGENT_NAME
        assert t.identity.model_id == fa.MODEL_ID
        assert t.identity.invocation == "bash -c"
        assert t.tokens.recorded is False


def test_timelike_hang_ends_on_the_hook_dispatchers_verdict(
    bench_run: tuple[Path, list[trace.Trace]],
) -> None:
    # 001 cycle 5: the hook's own limit (1 s here) stops it inside the call, with a verdict; the call is
    # a failed command, not a hang. (A failed check is covered by the scripted units below.)
    t = next(
        x
        for x in bench_run[1]
        if (x.identity.task_id, x.identity.environment) == ("git-commit-hook-hangs", "timelike")
    )
    first = t.calls[0]
    assert (first.hung, first.exit_code != 0) == (False, True)
    assert "did not finish within 1 s and was stopped" in first.stderr_head


def test_every_session_is_closed(bench_run: tuple[Path, list[trace.Trace]]) -> None:
    assert len(LocalSession.closed) >= 8


# --- scripted edges --------------------------------------------------------------------------------


def result(
    code: int = 0, *, hung: bool = False, backstop: bool = False, out: int = 0, err: bytes = b""
) -> CallResult:
    return CallResult(code, 5, hung, out, len(err), b"", err, backstop)


class Scripted:
    def __init__(self, results: list[CallResult]) -> None:
        self.results = results
        self.commands: list[str] = []
        self.closed = False
        self.executor: Executor = self

    def run(self, command: str, limit_s: int) -> CallResult:
        self.commands.append(command)
        return self.results.pop(0)

    def close(self) -> None:
        self.closed = True


def scripted_env(s: Scripted) -> runner.Environment:
    return runner.Environment("vanilla", "sha256:" + "e" * 64, SHA, lambda: s)


def task_with(policy: fa.Policy) -> catalog.Task:
    return catalog.Task("t", 1, "cap", "goal", ("git",), "setup", policy, "check", "expected")


ONE = fa.Policy("a", (fa.Step("a", "cmd", fa.DONE, fa.escalate("needs a grant"), fa.give_up("a hung")),))


def test_setup_failure_gives_a_trace_with_no_calls_and_closes() -> None:
    s = Scripted([result(3, err=b"\nfatal: no\n")])
    t = runner.run_task(task_with(ONE), scripted_env(s), CTX)
    assert (t.calls, t.ending) == ((), trace.Ending("failed", "setup failed: fatal: no"))
    assert trace.validate(t) == [] and s.closed


def test_setup_hang_and_check_hang() -> None:
    t = runner.run_task(task_with(ONE), scripted_env(Scripted([result(124, hung=True)])), CTX)
    assert t.ending.reason == "setup failed: hung"
    t = runner.run_task(
        task_with(ONE), scripted_env(Scripted([result(), result(), result(137, hung=True)])), CTX
    )
    assert t.ending == trace.Ending("failed", "check failed: hung")


def test_check_failure_without_stderr_names_the_exit() -> None:
    t = runner.run_task(task_with(ONE), scripted_env(Scripted([result(), result(), result(1)])), CTX)
    assert t.ending == trace.Ending("failed", "check failed: exit 1")


def test_escalation_and_give_up() -> None:
    t = runner.run_task(task_with(ONE), scripted_env(Scripted([result(), result(4)])), CTX)
    assert t.ending == trace.Ending("escalated", "needs a grant")
    t = runner.run_task(task_with(ONE), scripted_env(Scripted([result(), result(124, hung=True)])), CTX)
    assert t.ending == trace.Ending("failed", "a hung")
    assert t.totals.hangs == 1


def test_backstop_ends_the_run_hung() -> None:
    s = Scripted([result(), result(137, hung=True, backstop=True)])
    t = runner.run_task(task_with(ONE), scripted_env(s), CTX)
    assert t.ending.kind == "hung" and "backstop" in t.ending.reason
    assert s.closed


def test_run_limit_ends_the_run_hung() -> None:
    # run_task's start, the walk's start, the check before call 1, the check before call 2, the end
    ticks = iter([0.0, 0.0, 0.0, 1000.0, 1000.0])
    clock: Callable[[], float] = lambda: next(ticks)  # noqa: E731
    loop = fa.Policy(
        "a", (fa.Step("a", "cmd", "b", "b", "b"), fa.Step("b", "cmd", fa.DONE, fa.DONE, fa.DONE))
    )
    t = runner.run_task(task_with(loop), scripted_env(Scripted([result(), result()])), CTX, clock)
    assert t.ending == trace.Ending("hung", "run limit of 60 s exceeded")
    assert len(t.calls) == 1


def test_harness_cut_is_recorded() -> None:
    s = Scripted([result(), result(out=50000, err=b"x" * 10), result()])
    t = runner.run_task(task_with(ONE), scripted_env(s), CTX)
    call = t.calls[0]
    assert (call.passed_bytes, call.harness_cut) == (30010, True)
    assert trace.validate(t) == []


def test_session_closes_when_the_executor_raises() -> None:
    class Boom(Scripted):
        def run(self, command: str, limit_s: int) -> CallResult:
            raise OSError("docker went away")

    s = Boom([])
    with pytest.raises(OSError, match="docker went away"):
        runner.run_task(task_with(ONE), scripted_env(s), CTX)
    assert s.closed


def test_trace_path() -> None:
    assert runner.trace_path(Path("/o"), "t", "vanilla") == Path("/o/traces/t--vanilla.json")
    assert os.sep == "/"
