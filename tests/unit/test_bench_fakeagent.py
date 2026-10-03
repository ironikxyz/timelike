"""Units for benchlib.fakeagent (T004): the deterministic, environment-blind fake agent (FR-11)."""

from __future__ import annotations

import inspect

import pytest
from benchlib import fakeagent as fa
from benchlib.fakeagent import DONE, Observation, Policy, Step, Walker, next_step

OK = Observation(exit_code=0, hung=False)
FAIL = Observation(exit_code=1, hung=False)
HANG = Observation(exit_code=124, hung=True)


def _policy() -> Policy:
    return Policy(
        start="a",
        steps=(
            Step("a", "true", on_ok="b", on_fail="c", on_hang=fa.escalate("a hung")),
            Step("b", "true", on_ok=DONE, on_fail=fa.give_up("b failed"), on_hang="c"),
            Step("c", "true", on_ok=DONE, on_fail=fa.give_up("c failed"), on_hang=fa.give_up("c hung")),
        ),
    )


def _walk(policy: Policy, observations: list[Observation]) -> list[str]:
    walker = Walker(policy)
    path = [walker.current]
    for obs in observations:
        if walker.finished:
            break
        path.append(walker.advance(obs))
    return path


def test_identity_constants() -> None:
    assert fa.FAKE_AGENT_NAME == "timelike-fake-agent"
    assert fa.FAKE_AGENT_VERSION == "1"
    assert fa.MODEL_ID == "none (deterministic fake agent)"


def test_next_step_signature_takes_no_environment() -> None:
    # FR-11: environment-blindness is the signature. Widening it must fail here.
    assert list(inspect.signature(next_step).parameters) == ["policy", "current", "obs"]


def test_branches() -> None:
    p = _policy()
    assert next_step(p, "a", OK) == "b"
    assert next_step(p, "a", FAIL) == "c"
    assert next_step(p, "a", HANG) == "ESCALATE:a hung"


def test_hang_wins_over_exit_code() -> None:
    p = _policy()
    assert next_step(p, "b", Observation(exit_code=0, hung=True)) == "c"
    assert next_step(p, "b", Observation(exit_code=137, hung=True)) == "c"
    # 124 without the hang flag is an ordinary failure: the executor decides what a hang is.
    assert next_step(p, "b", Observation(exit_code=124, hung=False)) == "GIVE_UP:b failed"


def test_output_is_not_branched_on() -> None:
    p = _policy()
    noisy = Observation(exit_code=0, hung=False, stdout_head="error!", stderr_head="fatal: x")
    assert next_step(p, "a", noisy) == next_step(p, "a", OK)


def test_determinism() -> None:
    seq = [FAIL, FAIL, OK, HANG]
    runs = [_walk(_policy(), seq) for _ in range(5)]
    assert all(r == runs[0] for r in runs)
    assert runs[0] == ["a", "c", "GIVE_UP:c failed"]


@pytest.mark.parametrize(
    ("observations", "end", "kind", "reason"),
    [
        ([OK, OK], DONE, "done", ""),
        ([FAIL, FAIL], "GIVE_UP:c failed", "give_up", "c failed"),
        ([HANG], "ESCALATE:a hung", "escalate", "a hung"),
    ],
)
def test_each_terminal(observations: list[Observation], end: str, kind: str, reason: str) -> None:
    path = _walk(_policy(), observations)
    assert path[-1] == end
    assert fa.is_terminal(end)
    assert fa.terminal_kind(end) == kind
    assert fa.terminal_reason(end) == reason


@pytest.mark.parametrize("target", ["a", "", "GIVE_UP:", "ESCALATE:  ", "done", "GIVEUP:x"])
def test_non_terminals(target: str) -> None:
    assert not fa.is_terminal(target)
    with pytest.raises(ValueError, match="not a terminal"):
        fa.terminal_kind(target)


def test_loop_guard_gives_up_on_fourth_visit() -> None:
    p = Policy(start="x", steps=(Step("x", "false", on_ok=DONE, on_fail="x", on_hang="x"),))
    walker = Walker(p)
    path = [walker.current]
    while not walker.finished:
        path.append(walker.advance(FAIL))
    # Visits 1, 2, 3 run; the 4th entry becomes the terminal instead.
    assert path == ["x", "x", "x", "GIVE_UP:policy loop"]
    assert fa.terminal_kind(walker.current) == "give_up"


def test_loop_guard_counts_per_step() -> None:
    p = Policy(
        start="x",
        steps=(
            Step("x", "true", on_ok="y", on_fail=DONE, on_hang=DONE),
            Step("y", "true", on_ok="x", on_fail=DONE, on_hang=DONE),
        ),
    )
    path = _walk(p, [OK] * 10)
    assert path == ["x", "y", "x", "y", "x", "y", "GIVE_UP:policy loop"]


def test_walker_refuses_to_advance_after_end() -> None:
    walker = Walker(_policy())
    walker.advance(HANG)
    assert walker.finished
    with pytest.raises(RuntimeError, match="already ended"):
        walker.advance(OK)
    with pytest.raises(KeyError):
        _ = walker.command


def test_walker_command_follows_current() -> None:
    walker = Walker(_policy())
    assert walker.command == "true"
    walker.advance(OK)
    assert walker.current == "b"


@pytest.mark.parametrize(
    ("start", "steps", "message"),
    [
        ("a", (), "at least one step"),
        ("a", (Step("a", "true", DONE, DONE, DONE), Step("a", "true", DONE, DONE, DONE)), "duplicate"),
        ("z", (Step("a", "true", DONE, DONE, DONE),), "start 'z'"),
        ("a", (Step("a", "true", "nowhere", DONE, DONE),), "neither a step id nor a terminal"),
        ("a", (Step("a", "true", DONE, "GIVE_UP:", DONE),), "neither a step id nor a terminal"),
        ("a", (Step("a", "true", DONE, DONE, "ESCALATE:"),), "neither a step id nor a terminal"),
        ("DONE", (Step("DONE", "true", DONE, DONE, DONE),), "terminal-shaped"),
        ("a:b", (Step("a:b", "true", DONE, DONE, DONE),), "terminal-shaped"),
        ("a", (Step("a", "  ", DONE, DONE, DONE),), "empty command"),
    ],
)
def test_policy_construction_errors(start: str, steps: tuple[Step, ...], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        Policy(start=start, steps=steps)


def test_frozen() -> None:
    p = _policy()
    with pytest.raises(AttributeError):
        p.start = "b"  # type: ignore[misc]
    with pytest.raises(AttributeError):
        OK.exit_code = 1  # type: ignore[misc]


def test_reachable_terminals() -> None:
    p = _policy()
    assert fa.reachable_terminals(p) == {
        DONE,
        "ESCALATE:a hung",
        "GIVE_UP:b failed",
        "GIVE_UP:c failed",
        "GIVE_UP:c hung",
    }
    assert fa.reachable_terminals(p, "c") == {DONE, "GIVE_UP:c failed", "GIVE_UP:c hung"}
    cyclic = Policy(start="x", steps=(Step("x", "true", "x", "x", "x"),))
    assert fa.reachable_terminals(cyclic) == frozenset()
