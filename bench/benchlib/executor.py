"""executor — runs one tool call the way a harness does, and measures it (FR-3, FR-4, FR-6).

Every call, in either environment, goes through the same wrapper (research RB5):

    sh -c '<WRAPPER_SCRIPT>' <limit> <command>

The limit lives INSIDE the environment, because `docker exec` has no timeout and killing the docker
client leaves the process running in the container (moby #35703). GNU `timeout` makes itself a
process-group leader and signals the group when the limit expires; the unconditional
`kill -KILL -$t` after `wait` also kills a background child that outlived a normal exit and would
otherwise hold stdout open, so the call could never reach EOF. The wrapper is dash (`sh`), which reads
no startup file; the command itself runs as `bash -c`, so an environment's BASH_ENV applies exactly as
it does under a real harness.

The same argv runs locally (LocalExecutor: host units) or behind `docker exec` (DockerExecutor) with no
`-t` and no `-i`: no TTY, stdin at EOF (RB2). Neither environment gets a path the other does not
(cross-stack P005).

Output is drained from two pipes by a selector. Every byte is counted; only a capped head is kept, so a
command that prints without end cannot exhaust the driver. A driver-side backstop (limit + 10 s) covers
a wrapper that itself fails to conclude: the call is recorded hung and `backstop` is set, and the caller
(runner) removes the container.
"""

from __future__ import annotations

import contextlib
import os
import selectors
import signal
import subprocess
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import IO, Protocol

# `kill -KILL -$t`, not `kill -KILL -- -$t`: dash's kill builtin rejects `--` ("Illegal number: -"), and
# the group kill then silently never happens (found by T006's unit; research RB5 had the bash form).
WRAPPER_SCRIPT = (
    'timeout -s TERM -k 2 "$0" bash -c "$1" & t=$!; wait $t; rc=$?; kill -KILL -$t 2>/dev/null; exit $rc'
)
HANG_EXIT_CODES = frozenset({124, 137})  # timeout's TERM verdict, and the KILL that follows it
BACKSTOP_GRACE_S = 10.0
HEAD_CAP = 4096  # bytes kept per stream; everything is still counted
TASK_DIR = "/home/agent/task"
TASK_USER = "agent"


@dataclass(frozen=True)
class CallResult:
    exit_code: int
    duration_ms: int
    hung: bool
    stdout_bytes: int
    stderr_bytes: int
    stdout_head: bytes
    stderr_head: bytes
    backstop: bool = False  # the driver's own deadline fired; the environment may still hold the call


class Executor(Protocol):
    def run(self, command: str, limit_s: int) -> CallResult: ...


def wrapper_argv(command: str, limit_s: int) -> list[str]:
    if limit_s <= 0:
        raise ValueError(f"limit must be positive, got {limit_s}")
    return ["sh", "-c", WRAPPER_SCRIPT, str(limit_s), command]


def is_hang(exit_code: int, duration_ms: int, limit_s: int) -> bool:
    """A hang is timeout's verdict AND the limit's worth of time: a command may exit 124 by itself."""
    return exit_code in HANG_EXIT_CODES and duration_ms >= limit_s * 1000


def capture(
    argv: Sequence[str],
    limit_s: int,
    *,
    cwd: str | None = None,
    env: Mapping[str, str] | None = None,
    head_cap: int = HEAD_CAP,
    backstop_s: float | None = None,
) -> CallResult:
    """Run argv with stdin at EOF, drain both pipes, and time it with the driver's monotonic clock."""
    deadline_s = limit_s + BACKSTOP_GRACE_S if backstop_s is None else backstop_s
    started = time.monotonic()
    proc = subprocess.Popen(
        list(argv),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=cwd,
        env=dict(env) if env is not None else None,
        start_new_session=True,  # no controlling terminal; lets the backstop kill the whole group
    )
    assert proc.stdout is not None and proc.stderr is not None  # noqa: S101 — PIPE was requested
    counts = {"out": 0, "err": 0}
    heads = {"out": bytearray(), "err": bytearray()}
    sel = selectors.DefaultSelector()
    sel.register(proc.stdout, selectors.EVENT_READ, "out")
    sel.register(proc.stderr, selectors.EVENT_READ, "err")
    backstop = False
    while sel.get_map():
        remaining = deadline_s - (time.monotonic() - started)
        if remaining <= 0:
            backstop = True
            break
        for key, _ in sel.select(timeout=remaining):
            name = str(key.data)
            stream: IO[bytes] = key.fileobj  # type: ignore[assignment]
            chunk = os.read(stream.fileno(), 65536)
            if not chunk:
                sel.unregister(stream)
                continue
            counts[name] += len(chunk)
            room = head_cap - len(heads[name])
            if room > 0:
                heads[name] += chunk[:room]
    sel.close()
    if backstop:
        _kill_group(proc)
        exit_code = proc.wait()
    else:
        try:
            exit_code = proc.wait(timeout=max(0.1, deadline_s - (time.monotonic() - started)))
        except subprocess.TimeoutExpired:
            backstop = True
            _kill_group(proc)
            exit_code = proc.wait()
    proc.stdout.close()
    proc.stderr.close()
    duration_ms = int((time.monotonic() - started) * 1000)
    return CallResult(
        exit_code=exit_code,
        duration_ms=duration_ms,
        hung=backstop or is_hang(exit_code, duration_ms, limit_s),
        stdout_bytes=counts["out"],
        stderr_bytes=counts["err"],
        stdout_head=bytes(heads["out"]),
        stderr_head=bytes(heads["err"]),
        backstop=backstop,
    )


def _kill_group(proc: subprocess.Popen[bytes]) -> None:
    with contextlib.suppress(ProcessLookupError):
        os.killpg(proc.pid, signal.SIGKILL)


class LocalExecutor:
    """The wrapper on this machine. Host units use it to exercise the real wrapper without Docker."""

    def __init__(self, cwd: str, env: Mapping[str, str]) -> None:
        self.cwd = cwd
        self.env = dict(env)

    def argv(self, command: str, limit_s: int) -> list[str]:
        return wrapper_argv(command, limit_s)

    def run(self, command: str, limit_s: int) -> CallResult:
        return capture(self.argv(command, limit_s), limit_s, cwd=self.cwd, env=self.env)


class DockerExecutor:
    """The wrapper inside a task container: `docker exec` with no -t and no -i (RB2)."""

    def __init__(
        self,
        container_id: str,
        *,
        docker: str = "docker",
        user: str = TASK_USER,
        workdir: str = TASK_DIR,
        env: Mapping[str, str] | None = None,
    ) -> None:
        self.container_id = container_id
        self.docker = docker
        self.user = user
        self.workdir = workdir
        self.env = dict(env) if env is not None else None  # the docker CLI's own env; never forwarded

    def argv(self, command: str, limit_s: int) -> list[str]:
        prefix = [self.docker, "exec", "-u", self.user, "-w", self.workdir, self.container_id]
        return prefix + wrapper_argv(command, limit_s)

    def run(self, command: str, limit_s: int) -> CallResult:
        return capture(self.argv(command, limit_s), limit_s, env=self.env)
