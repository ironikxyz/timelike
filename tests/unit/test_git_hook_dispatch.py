"""The git-hook dispatcher (cycle 5, discovery revision 7; research R11; SC-12, SC-13) — host lane.

Real git, with the image's mechanism replayed: GIT_CONFIG_* points core.hooksPath at the repository's
own image/rootfs/opt/timelike/git-hooks, exactly as the image's ENV does, and GIT_CONFIG_NOSYSTEM keeps
this host's /etc/gitconfig out. What this cannot show is the image itself (001 R10): the Docker lane's
bats files are authoritative for SC-12 and SC-13.

Every git call runs with stdin at /dev/null, in its own session, under a timeout, so a dispatcher
defect is a failing test, never a hung suite. Whether a hook's background child survived is read from
an artefact it would write, not from the process table.
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

import pytest
from conftest import REPO

DISPATCH_DIR = REPO / "image" / "rootfs" / "opt" / "timelike" / "git-hooks"
SKIP_WORDS = ("--no-verify", " -n ", "hooksPath", "skip", "bypass", "disable")


def env_for(home: Path, **extra: str) -> dict[str, str]:
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(home),
        "LC_ALL": "C.UTF-8",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "core.hooksPath",
        "GIT_CONFIG_VALUE_0": str(DISPATCH_DIR),
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.invalid",
    }
    env.update(extra)
    return env


def git(repo: Path, env: dict[str, str], *args: str, timeout: float = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=timeout,
        start_new_session=True,
    )


def hook(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\n" + body + "\n")
    path.chmod(0o755)
    return path


@pytest.fixture
def repo(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    home = tmp_path / "home"
    home.mkdir()
    env = env_for(home)
    r = tmp_path / "r"
    subprocess.run(["git", "init", "-q", "-b", "main", str(r)], env=env, check=True, stdin=subprocess.DEVNULL)
    (r / "f").write_text("base\n")
    assert git(r, env, "add", "f").returncode == 0
    assert git(r, env, "commit", "-qm", "base").returncode == 0
    return r, env


def head(r: Path, env: dict[str, str]) -> str:
    return git(r, env, "rev-parse", "HEAD").stdout.strip()


def stage(r: Path, env: dict[str, str], text: str) -> None:
    (r / "f").write_text(text)
    assert git(r, env, "add", "f").returncode == 0


# --- SC-12: the hooks a repository configures run --------------------------------------------------


def test_default_location_hook_rejects_with_its_own_output(repo: tuple[Path, dict[str, str]]) -> None:
    r, env = repo
    hook(r / ".git/hooks/pre-commit", 'echo "pre-commit: TODO found" >&2; exit 1')
    stage(r, env, "TODO\n")
    before = head(r, env)
    p = git(r, env, "commit", "-qm", "x")
    assert p.returncode == 1
    assert "pre-commit: TODO found" in p.stderr
    assert head(r, env) == before


def test_husky_local_hooks_path_runs_despite_the_command_scope(repo: tuple[Path, dict[str, str]]) -> None:
    r, env = repo
    hook(r / ".husky/pre-commit", ": > .git/husky-ran; echo husky >&2; exit 3")
    assert git(r, env, "config", "core.hooksPath", ".husky").returncode == 0
    stage(r, env, "change\n")
    p = git(r, env, "commit", "-qm", "x")
    assert (r / ".git/husky-ran").exists()
    assert p.returncode == 1 and "husky" in p.stderr


def test_a_passing_hook_lets_the_commit_through(repo: tuple[Path, dict[str, str]]) -> None:
    r, env = repo
    hook(r / ".git/hooks/pre-commit", ": > .git/ran; exit 0")
    stage(r, env, "change\n")
    assert git(r, env, "commit", "-qm", "x").returncode == 0
    assert (r / ".git/ran").exists()


def test_hook_arguments_pass_through(repo: tuple[Path, dict[str, str]]) -> None:
    r, env = repo
    hook(
        r / ".git/hooks/commit-msg", 'grep -q "^fix:" "$1" || { echo "commit-msg: needs fix:" >&2; exit 1; }'
    )
    stage(r, env, "change\n")
    assert git(r, env, "commit", "-qm", "wip").returncode == 1
    assert git(r, env, "commit", "-qm", "fix: ok").returncode == 0


def test_pre_push_receives_gits_stdin(repo: tuple[Path, dict[str, str]], tmp_path: Path) -> None:
    r, env = repo
    remote = tmp_path / "remote.git"
    subprocess.run(
        ["git", "init", "-q", "--bare", str(remote)], env=env, check=True, stdin=subprocess.DEVNULL
    )
    assert git(r, env, "remote", "add", "o", str(remote)).returncode == 0
    hook(r / ".git/hooks/pre-push", 'n=0; while read -r l; do n=$((n+1)); done; echo "lines=$n" >&2')
    p = git(r, env, "push", "-q", "o", "HEAD:refs/heads/main")
    assert p.returncode == 0 and "lines=1" in p.stderr


def test_a_linked_worktree_runs_the_common_hooks(repo: tuple[Path, dict[str, str]], tmp_path: Path) -> None:
    r, env = repo
    hook(r / ".git/hooks/pre-commit", 'echo "wt-hook" >&2; exit 1')
    wt = tmp_path / "wt"
    assert git(r, env, "worktree", "add", "-q", str(wt)).returncode == 0
    (wt / "g").write_text("x\n")
    assert git(wt, env, "add", "g").returncode == 0
    p = git(wt, env, "commit", "-qm", "x")
    assert p.returncode == 1 and "wt-hook" in p.stderr


def test_a_non_executable_hook_is_ignored_with_gits_own_hint(repo: tuple[Path, dict[str, str]]) -> None:
    r, env = repo
    h = hook(r / ".git/hooks/pre-commit", "exit 1")
    h.chmod(0o644)
    stage(r, env, "change\n")
    p = git(r, env, "commit", "-qm", "x")
    assert p.returncode == 0
    assert "hook was ignored because it's not set as executable" in p.stderr


def test_no_recursion_when_the_repository_points_at_the_dispatchers(
    repo: tuple[Path, dict[str, str]],
) -> None:
    # The fallback that once made the dispatcher call itself (R11): a path that resolves to the
    # dispatcher directory is never a repository's hook directory.
    r, env = repo
    assert git(r, env, "config", "core.hooksPath", str(DISPATCH_DIR)).returncode == 0
    stage(r, env, "change\n")
    started = time.monotonic()
    p = git(r, env, "commit", "-qm", "x", timeout=20)
    assert p.returncode == 0, p.stderr
    assert time.monotonic() - started < 10


def test_outside_a_repository_the_dispatcher_does_nothing(tmp_path: Path) -> None:
    p = subprocess.run(
        [str(DISPATCH_DIR / "pre-commit")],
        cwd=tmp_path,
        env=env_for(tmp_path),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert (p.returncode, p.stderr) == (0, "")


def test_every_link_points_at_dispatch() -> None:
    links = sorted(p for p in DISPATCH_DIR.iterdir() if p.is_symlink())
    assert len(links) == 25
    assert all(os.readlink(p) == "dispatch" for p in links)
    names = {p.name for p in links}
    assert {"pre-commit", "commit-msg", "pre-push", "post-checkout", "reference-transaction"} <= names
    assert not {"push-to-checkout", "proc-receive", "fsmonitor-watchman"} & names  # R11: named, not linked


# --- SC-13: a hook past its limit is killed, with a verdict --------------------------------------


def hanging(r: Path) -> None:
    # A child that would leave .git/survived behind if the group kill missed it.
    hook(r / ".git/hooks/pre-commit", "(sleep 3; : > .git/survived) &\nsleep 60")


def assert_verdict(stderr: str, limit: str, source: str) -> None:
    line = next(x for x in stderr.splitlines() if x.startswith("error: git hook pre-commit"))
    assert f"did not finish within {limit} s and was stopped (code 124)" in line
    assert f"the limit is {limit} s ({source})" in line
    assert "TIMELIKE_HOOK_TIMEOUT=<seconds>" in line
    assert "git config timelike.hookTimeout <seconds>" in line
    lowered = line.lower()
    assert not [w for w in SKIP_WORDS if w.lower() in lowered], line


def test_a_hang_is_stopped_within_the_limit_with_a_verdict(repo: tuple[Path, dict[str, str]]) -> None:
    r, env = repo
    hanging(r)
    stage(r, env, "change\n")
    before = head(r, env)
    started = time.monotonic()
    p = git(r, {**env, "TIMELIKE_HOOK_TIMEOUT": "1"}, "commit", "-qm", "x")
    elapsed = time.monotonic() - started
    assert p.returncode != 0
    assert elapsed < 1 + 5
    assert_verdict(p.stderr, "1", "TIMELIKE_HOOK_TIMEOUT")
    assert head(r, env) == before
    time.sleep(3.5)
    assert not (r / ".git/survived").exists(), "the hook's background child outlived the limit"


def test_the_repository_setting_sets_the_limit(repo: tuple[Path, dict[str, str]]) -> None:
    r, env = repo
    hanging(r)
    assert git(r, env, "config", "timelike.hookTimeout", "1").returncode == 0
    stage(r, env, "change\n")
    p = git(r, env, "commit", "-qm", "x")
    assert p.returncode != 0
    assert_verdict(p.stderr, "1", "git config timelike.hookTimeout")


def test_the_environment_beats_the_repository_setting(repo: tuple[Path, dict[str, str]]) -> None:
    r, env = repo
    hanging(r)
    assert git(r, env, "config", "timelike.hookTimeout", "30").returncode == 0
    stage(r, env, "change\n")
    started = time.monotonic()
    p = git(r, {**env, "TIMELIKE_HOOK_TIMEOUT": "1"}, "commit", "-qm", "x")
    assert time.monotonic() - started < 1 + 5
    assert_verdict(p.stderr, "1", "TIMELIKE_HOOK_TIMEOUT")


@pytest.mark.parametrize("value", ["abc", "0", "-5", "1.5"])
def test_a_bad_limit_is_reported_and_the_default_used(repo: tuple[Path, dict[str, str]], value: str) -> None:
    r, env = repo
    hook(r / ".git/hooks/pre-commit", "exit 0")
    stage(r, env, f"change {value}\n")
    p = git(r, {**env, "TIMELIKE_HOOK_TIMEOUT": value}, "commit", "-qm", "x")
    assert p.returncode == 0
    assert (
        f"hook limit {value} from TIMELIKE_HOOK_TIMEOUT is not a positive number of seconds; using 60"
        in p.stderr
    )


def test_the_default_limit_is_60_seconds() -> None:
    text = (DISPATCH_DIR / "dispatch").read_text()
    assert "default_limit=60\n" in text
