"""fakeagent — the deterministic fake agent that drives every catalog task (FR-11).

A policy is data: a start id and a tuple of `Step`s, each naming one command and where to go on
success, on a non-zero exit and on a hang. One pure function, `next_step`, interprets it. That
function takes the policy, the current step and what was observed, and **nothing else** — no
environment name, no image id, no clock. Environment-blindness is therefore a property of the
signature, not a promise about the policies (FR-11, spec Assumption 6), and a unit test pins the
signature so that a later edit cannot quietly widen it.

What the fake agent cannot reveal is listed in research RB11: its recoveries are written by the people
who built timelike, the tasks were selected where timelike differs, and it reads exit codes and hangs
only — `stdout_head` and `stderr_head` are carried so slice 1 can branch on them, and slice 0 does not.

Stdlib only (H5). Nothing here runs inside an environment under test.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Literal

FAKE_AGENT_NAME = "timelike-fake-agent"
FAKE_AGENT_VERSION = "1"  # bumped whenever next_step, Walker or the terminal grammar changes meaning
MODEL_ID = "none (deterministic fake agent)"

DONE = "DONE"
GIVE_UP_PREFIX = "GIVE_UP:"
ESCALATE_PREFIX = "ESCALATE:"

# data-model.md: a step may be visited at most 3 times; the 4th visit ends the run `failed`.
MAX_VISITS = 3
LOOP_REASON = "policy loop"

TerminalKind = Literal["done", "give_up", "escalate"]


def give_up(reason: str) -> str:
    """The terminal that ends a run `failed` with `reason`."""
    return GIVE_UP_PREFIX + reason


def escalate(reason: str) -> str:
    """The terminal that ends a run `escalated` with `reason`."""
    return ESCALATE_PREFIX + reason


def is_terminal(target: str) -> bool:
    """True for DONE, and for GIVE_UP:/ESCALATE: with a non-empty reason.

    A bare prefix is not a terminal: an ending with no reason is what FR-8's non-empty rule exists to
    prevent, so it is rejected when the policy is built rather than written into a trace.
    """
    if target == DONE:
        return True
    for prefix in (GIVE_UP_PREFIX, ESCALATE_PREFIX):
        if target.startswith(prefix):
            return bool(target[len(prefix) :].strip())
    return False


def terminal_kind(target: str) -> TerminalKind:
    """`done`, `give_up` or `escalate`; ValueError for anything that is not a terminal."""
    if not is_terminal(target):
        raise ValueError(f"not a terminal: {target!r}")
    if target == DONE:
        return "done"
    return "give_up" if target.startswith(GIVE_UP_PREFIX) else "escalate"


def terminal_reason(target: str) -> str:
    """The reason after the prefix; empty for DONE. ValueError for a non-terminal."""
    kind = terminal_kind(target)
    if kind == "done":
        return ""
    return target.split(":", 1)[1]


@dataclass(frozen=True)
class Step:
    """One tool call and its three exits. `command` runs as `bash -c` in the task directory."""

    id: str
    command: str
    on_ok: str
    on_fail: str
    on_hang: str

    def targets(self) -> tuple[str, str, str]:
        return (self.on_ok, self.on_fail, self.on_hang)


@dataclass(frozen=True)
class Policy:
    """A start id and its steps, validated when built so a bad policy fails in units, not mid-run."""

    start: str
    steps: tuple[Step, ...]

    def __post_init__(self) -> None:
        if not self.steps:
            raise ValueError("a policy needs at least one step")
        ids = [s.id for s in self.steps]
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        if dupes:
            raise ValueError(f"duplicate step ids: {', '.join(dupes)}")
        for step_id in ids:
            # A step named like a terminal would make next_step's result ambiguous.
            if not step_id or step_id == DONE or ":" in step_id:
                raise ValueError(f"step id {step_id!r} is empty or terminal-shaped")
        if self.start not in ids:
            raise ValueError(f"start {self.start!r} is not a step id")
        known = set(ids)
        for step in self.steps:
            if not step.command.strip():
                raise ValueError(f"step {step.id!r} has an empty command")
            for target in step.targets():
                if target not in known and not is_terminal(target):
                    raise ValueError(f"step {step.id!r} targets {target!r}, neither a step id nor a terminal")

    def step(self, step_id: str) -> Step:
        for s in self.steps:
            if s.id == step_id:
                return s
        raise KeyError(step_id)


@dataclass(frozen=True)
class Observation:
    """What one tool call showed. Only `exit_code` and `hung` are branched on in slice 0 (RB11 item 3)."""

    exit_code: int
    hung: bool
    stdout_head: str = ""
    stderr_head: str = ""


def next_step(policy: Policy, current: str, obs: Observation) -> str:
    """The step id or terminal that follows `current`, given what its call showed.

    A hang wins over the exit code: a killed call exits 124 or 137, and reading that as an ordinary
    failure would route a hang down the failure branch. Pure — same arguments, same answer.
    """
    step = policy.step(current)
    if obs.hung:
        return step.on_hang
    if obs.exit_code != 0:
        return step.on_fail
    return step.on_ok


class Walker:
    """Walks a policy one observation at a time, adding the loop guard next_step cannot hold.

    The guard needs memory (how often each step was entered), so it lives here rather than in the pure
    function. A step entered a 4th time turns into `GIVE_UP:policy loop` instead of running (P2: a
    badly written policy ends, it never spins).
    """

    def __init__(self, policy: Policy) -> None:
        self.policy = policy
        self._visits: Counter[str] = Counter({policy.start: 1})
        self.current = policy.start

    @property
    def finished(self) -> bool:
        return is_terminal(self.current)

    @property
    def command(self) -> str:
        """The command of the current step; an error once the walk has ended."""
        return self.policy.step(self.current).command

    def advance(self, obs: Observation) -> str:
        """Record `obs` for the current step and move on; returns the new position."""
        if self.finished:
            raise RuntimeError(f"walk already ended at {self.current!r}")
        target = next_step(self.policy, self.current, obs)
        if not is_terminal(target):
            self._visits[target] += 1
            if self._visits[target] > MAX_VISITS:
                target = give_up(LOOP_REASON)
        self.current = target
        return target


def reachable_terminals(policy: Policy, start: str | None = None) -> frozenset[str]:
    """Every terminal reachable from `start` (default: the policy's start) along any branch.

    Empty means the walk from there can only cycle — the loop guard would end it, but as a bug.
    """
    seen: set[str] = set()
    found: set[str] = set()
    todo = [policy.start if start is None else start]
    while todo:
        node = todo.pop()
        if node in seen:
            continue
        seen.add(node)
        for target in policy.step(node).targets():
            if is_terminal(target):
                found.add(target)
            else:
                todo.append(target)
    return frozenset(found)
