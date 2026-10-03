"""Units for benchlib.catalog (T005): the four slice-0 tasks, their policies and their scripts.

The scripts are run for real. Each task's setup runs in a temporary directory, its policy is walked by
the fake agent through a small local runner that uses the executor's own in-container wrapper (RB5),
and its check judges the result — under two emulations of the environments:

- **vanilla**: `env -i` style, only PATH, a scratch HOME and GIT_CONFIG_NOSYSTEM=1; no TERM, no EDITOR.
- **timelike**: the same, plus image/Dockerfile's ENV block replayed from the file itself, and
  GIT_CONFIG_SYSTEM pointing at image/rootfs/etc/gitconfig.

The observed outcome is compared with research RB4's prediction. A disagreement is reported by the
test, never absorbed into it: the prediction table below is RB4's, not what was observed.
"""

from __future__ import annotations

import functools
import os
import re
import signal
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

import pytest
from benchlib import catalog
from benchlib.fakeagent import (
    Observation,
    Walker,
    is_terminal,
    reachable_terminals,
    terminal_kind,
)

REPO = Path(__file__).resolve().parents[2]
DOCKERFILE = REPO / "image" / "Dockerfile"
GITCONFIG = REPO / "image" / "rootfs" / "etc" / "gitconfig"
# 001 cycle 5: the image points core.hooksPath at its hook dispatchers. Here they run from the
# repository, and their limit sits below this unit's call limit, so a hanging hook ends on the
# dispatcher's verdict inside one call, as it does under the bench's real limits (60 s < 120 s).
IMAGE_HOOKS = "/opt/timelike/git-hooks"
DISPATCH_DIR = REPO / "image" / "rootfs" / "opt" / "timelike" / "git-hooks"
HOOK_LIMIT_S = "1"

# The executor's wrapper (RB5), so a hung hook is killed by group exactly as in a container: TERM
# first, which lets git remove its index.lock, then KILL.
WRAPPER = (
    'timeout -s TERM -k 2 "$0" bash -c "$1" & t=$!; wait $t; rc=$?; kill -KILL -$t 2>/dev/null; exit $rc'
)
CALL_LIMIT_S = 2  # short, so the vanilla hang costs two seconds, not the bench's real limit
BACKSTOP_S = CALL_LIMIT_S + 10
SCRIPT_TIMEOUT_S = 15

FORBIDDEN = re.compile(r"\bpython3?\b|\bmake\b|\bps\b|curl|wget|http", re.IGNORECASE)


@dataclass(frozen=True)
class Outcome:
    calls: int
    nonzero: int  # non-zero exits that are not hangs
    hangs: int
    ending: str  # completed | failed | escalated


# Research RB4, "Predicted: vanilla / timelike".
PREDICTED: dict[tuple[str, str], Outcome] = {
    ("git-inspect", "vanilla"): Outcome(2, 0, 0, "completed"),
    ("git-inspect", "timelike"): Outcome(2, 0, 0, "completed"),
    ("git-rebase-continue", "vanilla"): Outcome(5, 2, 0, "completed"),
    ("git-rebase-continue", "timelike"): Outcome(4, 1, 0, "completed"),
    ("git-commit-hook-hangs", "vanilla"): Outcome(2, 0, 1, "completed"),
    ("git-commit-hook-hangs", "timelike"): Outcome(2, 1, 0, "completed"),  # the dispatcher's verdict
    ("git-commit-hook-rejects", "vanilla"): Outcome(4, 1, 0, "completed"),
    ("git-commit-hook-rejects", "timelike"): Outcome(4, 1, 0, "completed"),  # hooks run (001 cycle 5)
}
ENVIRONMENTS = ("vanilla", "timelike")


# --- static properties -----------------------------------------------------------------------------


def test_the_four_rb4_tasks() -> None:
    assert [t.id for t in catalog.CATALOG] == [
        "git-inspect",
        "git-rebase-continue",
        "git-commit-hook-hangs",
        "git-commit-hook-rejects",
    ]


def test_ids_unique_and_kebab() -> None:
    ids = [t.id for t in catalog.CATALOG]
    assert len(ids) == len(set(ids))
    assert all(re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", i) for i in ids)


def test_versions_and_prerequisites() -> None:
    for task in catalog.CATALOG:
        assert task.version == 2  # 2: checks print their reason (send …-080659, F003)
        assert task.prerequisites == ("git",)
        assert task.capability and task.goal and task.expected


def test_every_step_reaches_a_terminal() -> None:
    for task in catalog.CATALOG:
        for step in task.policy.steps:
            assert reachable_terminals(task.policy, step.id), f"{task.id}:{step.id} can only cycle"
        assert "DONE" in reachable_terminals(task.policy), task.id


def test_every_step_is_reachable_from_start() -> None:
    for task in catalog.CATALOG:
        seen = {task.policy.start}
        todo = [task.policy.start]
        while todo:
            for target in task.policy.step(todo.pop()).targets():
                if not is_terminal(target) and target not in seen:
                    seen.add(target)
                    todo.append(target)
        assert seen == {s.id for s in task.policy.steps}, task.id


def test_no_forbidden_tools_or_network() -> None:
    for task in catalog.CATALOG:
        texts = [task.setup, task.check, *(s.command for s in task.policy.steps)]
        for text in texts:
            assert not FORBIDDEN.search(text), f"{task.id}: {FORBIDDEN.search(text)!r} in {text!r}"


def test_policies_are_environment_blind_text() -> None:
    for task in catalog.CATALOG:
        for text in [task.setup, task.check, *(s.command for s in task.policy.steps)]:
            assert not re.search(r"timelike|vanilla|/opt/|GIT_CONFIG_(COUNT|KEY|VALUE)", text), task.id


def test_hooks_are_sh_and_executable() -> None:
    for task in catalog.CATALOG:
        if ".git/hooks/pre-commit" in task.setup:
            assert "#!/bin/sh" in task.setup
            assert "chmod +x .git/hooks/pre-commit" in task.setup


def test_by_id() -> None:
    assert catalog.by_id("git-inspect") is catalog.CATALOG[0]
    with pytest.raises(KeyError, match="known: git-inspect"):
        catalog.by_id("nope")


def test_not_benchable_matches_rb4() -> None:
    names = [c for c, _ in catalog.NOT_BENCHABLE]
    assert len(names) == 6
    assert all(reason for _, reason in catalog.NOT_BENCHABLE)
    assert any("cpu.max" in n for n in names) and any("TZ" in n for n in names)


# --- real execution --------------------------------------------------------------------------------


def _image_env() -> dict[str, str]:
    """The Dockerfile's single static ENV block, parsed as tests/host/test_env_layer.sh does."""
    text = DOCKERFILE.read_text()
    start = text.index('\nENV PATH="')
    block: list[str] = []
    for line in text[start + 1 :].splitlines():
        block.append(line)
        if not line.rstrip().endswith("\\"):
            break
    env = dict(re.findall(r'([A-Za-z_][A-Za-z0-9_]*)="([^"]*)"', "\n".join(block)))
    assert env["GIT_CONFIG_KEY_0"] == "core.hooksPath"  # the parse found the block it meant to
    # PATH: the image's own dirs do not exist here. BASH_ENV: its hook file does not exist here, and
    # it only adds job counts and strips secret-shaped names, which no task exercises.
    del env["PATH"], env["BASH_ENV"]
    env = {k: str(DISPATCH_DIR) if v == IMAGE_HOOKS else v for k, v in env.items()}
    env["TIMELIKE_HOOK_TIMEOUT"] = HOOK_LIMIT_S
    return env


@functools.cache
def _system_gitconfig() -> str:
    """The image's /etc/gitconfig with its hooksPath fallback mapped to the repository's dispatchers."""
    path = Path(tempfile.mkdtemp(prefix="bench-gitconfig-")) / "gitconfig"
    path.write_text(GITCONFIG.read_text().replace(IMAGE_HOOKS, str(DISPATCH_DIR)))
    return str(path)


def _env(kind: str, home: Path) -> dict[str, str]:
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(home)}
    if kind == "vanilla":
        env["GIT_CONFIG_NOSYSTEM"] = "1"
    else:
        env.update(_image_env())
        env["GIT_CONFIG_SYSTEM"] = _system_gitconfig()
    return env


def _script(script: str, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "-c", script],
        cwd=cwd,
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=SCRIPT_TIMEOUT_S,
        start_new_session=True,
    )


def _call(command: str, cwd: Path, env: dict[str, str]) -> Observation:
    started = time.monotonic()
    proc = subprocess.Popen(
        ["sh", "-c", WRAPPER, str(CALL_LIMIT_S), command],
        cwd=cwd,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        out, err = proc.communicate(timeout=BACKSTOP_S)
    except subprocess.TimeoutExpired:  # the backstop: the wrapper itself failed to conclude
        os.killpg(proc.pid, signal.SIGKILL)
        out, err = proc.communicate()
        return Observation(exit_code=137, hung=True, stdout_head=out[:2048], stderr_head=err[:2048])
    elapsed = time.monotonic() - started
    hung = proc.returncode in (124, 137) and elapsed >= CALL_LIMIT_S
    return Observation(proc.returncode, hung, out[:2048], err[:2048])


@dataclass(frozen=True)
class Run:
    outcome: Outcome
    path: tuple[str, ...]
    stderr: tuple[str, ...]
    check_stderr: str = ""


def _run_task(task: catalog.Task, kind: str, root: Path) -> Run:
    home, work = root / "home", root / "task"
    home.mkdir()
    work.mkdir()
    env = _env(kind, home)
    setup = _script(task.setup, work, env)
    assert setup.returncode == 0, f"{task.id} setup failed under {kind}: {setup.stderr}"

    walker = Walker(task.policy)
    path, stderrs = [walker.current], []
    calls = nonzero = hangs = 0
    while not walker.finished:
        obs = _call(walker.command, work, env)
        calls += 1
        hangs += obs.hung
        nonzero += obs.exit_code != 0 and not obs.hung
        stderrs.append(obs.stderr_head)
        path.append(walker.advance(obs))

    kind_ = terminal_kind(walker.current)
    check_stderr = ""
    if kind_ == "done":
        check = _script(task.check, work, env)
        ending = "completed" if check.returncode == 0 else "failed"
        check_stderr = check.stderr
    else:
        ending = "failed" if kind_ == "give_up" else "escalated"
    return Run(Outcome(calls, nonzero, hangs, ending), tuple(path), tuple(stderrs), check_stderr)


@pytest.fixture(scope="module")
def runs(tmp_path_factory: pytest.TempPathFactory) -> dict[tuple[str, str], Run]:
    """Every task under both emulations, once for the module (the hang costs CALL_LIMIT_S)."""
    result: dict[tuple[str, str], Run] = {}
    for task in catalog.CATALOG:
        for kind in ENVIRONMENTS:
            root = tmp_path_factory.mktemp(f"{task.id}-{kind}")
            result[(task.id, kind)] = _run_task(task, kind, root)
    return result


def test_emulations_differ_where_they_should(tmp_path: Path) -> None:
    """Guard against a vacuous replay: the timelike emulation must actually carry timelike's git layer."""
    for kind, hooks, editor in (("vanilla", "", None), ("timelike", str(DISPATCH_DIR), "true")):
        home = tmp_path / kind
        home.mkdir()
        env = _env(kind, home)
        assert "TERM" not in env and "EDITOR" not in env
        got_hooks = _script("git config --get core.hooksPath || true", tmp_path, env).stdout.strip()
        assert got_hooks == hooks, kind
        var = _script("git var GIT_EDITOR", tmp_path, env)
        if editor is None:  # no TERM, no EDITOR: git has no editor to name and says so (RB3)
            assert var.returncode != 0, var.stdout
        else:
            assert (var.returncode, var.stdout.strip()) == (0, editor), kind


# RB4 first predicted 3 calls for vanilla git-commit-hook-rejects. Its own policy text ("remove the TODO
# lines, git add, and commit again") is 4 calls at one command per step, as in git-rebase-continue; this
# unit found it, and RB4 was corrected to 4 at T005 (coordinator's decision: the policy stands, the count
# was wrong).
def _params() -> list[object]:
    return [
        pytest.param(task.id, kind, id=f"{task.id}-{kind}")
        for task in catalog.CATALOG
        for kind in ENVIRONMENTS
    ]


@pytest.mark.parametrize(("task_id", "kind"), _params())
def test_outcome_matches_rb4(runs: dict[tuple[str, str], Run], task_id: str, kind: str) -> None:
    run = runs[(task_id, kind)]
    assert run.outcome == PREDICTED[(task_id, kind)], (
        f"{task_id} under {kind}: observed {run.outcome}, RB4 predicts {PREDICTED[(task_id, kind)]}; "
        f"path {run.path}; stderr {run.stderr}"
    )


def test_rejects_vanilla_takes_the_repository_policy_path(runs: dict[tuple[str, str], Run]) -> None:
    run = runs[("git-commit-hook-rejects", "vanilla")]
    assert run.path == ("commit", "strip", "add", "recommit", "DONE")
    assert (run.outcome.nonzero, run.outcome.hangs, run.outcome.ending) == (1, 0, "completed")
    assert "pre-commit: TODO found" in run.stderr[0]


def test_hang_is_the_hook_and_leaves_no_lock(runs: dict[tuple[str, str], Run]) -> None:
    run = runs[("git-commit-hook-hangs", "vanilla")]
    assert run.path == ("commit", "no-verify", "DONE")
    assert run.outcome.hangs == 1  # --no-verify succeeding is the proof: a left index.lock fails it


# --- the report's texts (send …-080659: the report explains itself) --------------------------------


def test_every_task_says_what_differs_and_notes_are_keyed_by_an_arm_and_an_ending() -> None:
    for task in catalog.CATALOG:
        assert task.difference.strip(), task.id
        assert "token" not in (task.difference + " ".join(n for _, n in task.notes)).lower()
        for key, note in task.notes:
            env, _, kind = key.partition(":")
            assert env in ("vanilla", "timelike") and kind in ("completed", "escalated", "failed", "hung")
            assert note.strip()


@pytest.mark.parametrize("task", catalog.CATALOG, ids=lambda t: t.id)
def test_a_failing_check_says_why_in_one_line(task: catalog.Task, tmp_path: Path) -> None:
    # Run the check in an empty directory: nothing holds, so it must fail and say why.
    p = _script(task.check, tmp_path, _env("vanilla", tmp_path))
    assert p.returncode != 0
    reason = p.stderr.strip().splitlines()
    assert len(reason) == 1 and len(reason[0]) > 10, p.stderr


def test_hook_rejects_timelike_runs_the_hook_like_vanilla(runs: dict[tuple[str, str], Run]) -> None:
    # 001 cycle 5: hooks run under timelike, so the repository's policy holds there too (a tie).
    run = runs[("git-commit-hook-rejects", "timelike")]
    assert run.path == ("commit", "strip", "add", "recommit", "DONE")
    assert run.outcome.ending == "completed"
    assert "pre-commit: TODO found" in run.stderr[0]


def test_hook_hangs_timelike_ends_on_the_dispatchers_verdict(runs: dict[tuple[str, str], Run]) -> None:
    run = runs[("git-commit-hook-hangs", "timelike")]
    assert run.path == ("commit", "no-verify", "DONE")
    assert (run.outcome.nonzero, run.outcome.hangs) == (1, 0)
    assert f"did not finish within {HOOK_LIMIT_S} s and was stopped" in run.stderr[0]
    assert "--no-verify" not in run.stderr[0]
