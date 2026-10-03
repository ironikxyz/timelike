"""Units for bench/benchlib/executor.py (T006) — the REAL wrapper, run locally (research RB5).

The wrapper string is the one DockerExecutor sends through `docker exec`; LocalExecutor runs the same
argv on this machine, so hangs, detached children and byte counts are exercised for real here. What
cannot be exercised here is the docker leg itself (no daemon, research R10): that is the Docker lane.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest
from benchlib import executor as ex


def local(tmp_path: Path) -> ex.LocalExecutor:
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(tmp_path)}
    return ex.LocalExecutor(str(tmp_path), env)


def test_success_counts_bytes_exactly_and_keeps_streams_apart(tmp_path: Path) -> None:
    r = local(tmp_path).run("head -c 100000 /dev/zero; printf 'err' >&2", 10)
    assert r.exit_code == 0
    assert r.hung is False
    assert r.stdout_bytes == 100000
    assert r.stderr_bytes == 3
    assert len(r.stdout_head) == ex.HEAD_CAP
    assert r.stderr_head == b"err"


def test_nonzero_exit_is_reported_and_is_not_a_hang(tmp_path: Path) -> None:
    r = local(tmp_path).run("exit 3", 10)
    assert (r.exit_code, r.hung) == (3, False)


def test_fast_exit_124_is_not_a_hang(tmp_path: Path) -> None:
    r = local(tmp_path).run("exit 124", 5)
    assert r.exit_code == 124
    assert r.hung is False


def test_sleep_past_the_limit_is_hung_and_ends_near_the_limit(tmp_path: Path) -> None:
    started = time.monotonic()
    r = local(tmp_path).run("sleep 60", 1)
    elapsed = time.monotonic() - started
    assert r.hung is True
    assert r.exit_code in ex.HANG_EXIT_CODES
    assert r.backstop is False
    assert elapsed < 1 + 3


def test_term_ignoring_command_is_killed_after_grace(tmp_path: Path) -> None:
    started = time.monotonic()
    r = local(tmp_path).run("trap '' TERM; sleep 60", 1)
    assert r.hung is True
    assert r.exit_code == 137
    assert time.monotonic() - started < 1 + 2 + 3


def test_background_child_holding_stdout_does_not_block_the_return(tmp_path: Path) -> None:
    started = time.monotonic()
    r = local(tmp_path).run("sleep 60 & echo started", 10)
    assert r.exit_code == 0
    assert r.stdout_head == b"started\n"
    assert time.monotonic() - started < 5


def test_stdin_is_at_eof(tmp_path: Path) -> None:
    r = local(tmp_path).run("if read -r line; then echo got; else echo eof; fi", 5)
    assert r.stdout_head == b"eof\n"


def test_backstop_fires_when_the_process_ignores_its_limit(tmp_path: Path) -> None:
    # Not the wrapper: a bare command with no inner limit, so only the driver's deadline can end it.
    r = ex.capture(["sleep", "60"], 1, cwd=str(tmp_path), backstop_s=0.5)
    assert r.backstop is True
    assert r.hung is True


def test_limit_must_be_positive() -> None:
    with pytest.raises(ValueError, match="positive"):
        ex.wrapper_argv("true", 0)


def test_docker_argv_has_no_tty_and_no_stdin_and_ends_in_the_same_wrapper() -> None:
    d = ex.DockerExecutor("abc123")
    argv = d.argv("git log", 30)
    assert argv[:7] == ["docker", "exec", "-u", "agent", "-w", "/home/agent/task", "abc123"]
    assert "-t" not in argv and "-i" not in argv and "-it" not in argv
    assert argv[7:] == ex.wrapper_argv("git log", 30)
    assert argv[7:] == ex.LocalExecutor("/", {}).argv("git log", 30)


def test_docker_run_goes_through_capture(tmp_path: Path) -> None:
    # A stand-in "docker" that drops the exec prefix and runs the rest, proving run() wires argv.
    fake = tmp_path / "docker"
    fake.write_text('#!/bin/sh\nshift 6\nexec "$@"\n')
    fake.chmod(0o755)
    d = ex.DockerExecutor("cid", docker=str(fake), env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")})
    r = d.run("echo hi", 5)
    assert (r.exit_code, r.stdout_head) == (0, b"hi\n")


@pytest.mark.parametrize(
    ("code", "ms", "limit", "hung"),
    [(124, 30000, 30, True), (137, 31000, 30, True), (124, 100, 30, False), (1, 30000, 30, False)],
)
def test_is_hang(code: int, ms: int, limit: int, hung: bool) -> None:
    assert ex.is_hang(code, ms, limit) is hung
