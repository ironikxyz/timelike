"""bench/run.sh, the host side of `make bench` — the argv it hands the driver (Cycle 1 fix).

The Docker lane at 8ce6173 found run.sh passing `--out DIR` to the driver only as BENCH_OUT, which
timelike-bench treats as a base and stamps beneath, so traces landed in DIR/<stamp>/ while the e2e
test read DIR/. The host lane had exercised the tool directly and never this wrapper. Here a stand-in
`docker` records its arguments and a real unix socket stands in for the daemon's, so the layout rule
is checked where the wrapper builds it: `--out DIR` is passed through exactly, and without it the
tool gets the bench/out base to stamp under.
"""

from __future__ import annotations

import socket
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest
from conftest import REPO

RUN_SH = REPO / "bench" / "run.sh"


@pytest.fixture
def harness(tmp_path: Path) -> Iterator[dict[str, object]]:
    fakebin = tmp_path / "fakebin"
    fakebin.mkdir()
    argv_file = tmp_path / "docker.argv"
    (fakebin / "docker").write_text(f'#!/bin/sh\nprintf "%s\\n" "$@" > {argv_file}\n')
    (fakebin / "docker").chmod(0o755)
    sock_path = tmp_path / "docker.sock"
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.bind(str(sock_path))
    env = {
        "PATH": f"{fakebin}:/usr/bin:/bin",
        "HOME": str(tmp_path),
        "GIT_SHA": "a" * 40,
        "DEBIAN_IMAGE": "debian:trixie-slim@sha256:" + "b" * 64,
        "BENCH_DOCKER_SOCKET": str(sock_path),
    }
    yield {"env": env, "argv": argv_file, "sock": sock_path, "tmp": tmp_path}
    sock.close()


def run_sh(h: dict[str, object], *args: str) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    env = h["env"]
    assert isinstance(env, dict)
    p = subprocess.run(
        [str(RUN_SH), *args], env=env, capture_output=True, text=True, timeout=20, stdin=subprocess.DEVNULL
    )
    argv_file = h["argv"]
    assert isinstance(argv_file, Path)
    return p, argv_file.read_text().splitlines() if argv_file.exists() else []


def after(argv: list[str], flag: str) -> list[str]:
    return [argv[i + 1] for i, a in enumerate(argv) if a == flag]


def test_out_dir_is_passed_through_exactly_and_mounted_at_its_own_path(harness: dict[str, object]) -> None:
    tmp = harness["tmp"]
    assert isinstance(tmp, Path)
    out = tmp / "runs" / "one"
    p, argv = run_sh(harness, "--out", str(out), "--task", "git-inspect")
    assert p.returncode == 0, p.stderr
    real = str(out.resolve())
    driver_args = argv[argv.index("timelike-bench-driver:local") + 1 :]
    assert driver_args == ["run", "--out", real, "--task", "git-inspect"]
    assert f"{real}:{real}" in after(argv, "-v")
    assert f"{harness['sock']}:/var/run/docker.sock" in after(argv, "-v")
    assert "BENCH_REPRODUCE=make bench TASKS='git-inspect'" in after(argv, "-e")


def test_without_out_the_tool_gets_the_bench_out_base_to_stamp_under(harness: dict[str, object]) -> None:
    p, argv = run_sh(harness)
    assert p.returncode == 0, p.stderr
    base = str((REPO / "bench" / "out").resolve())
    assert argv[argv.index("timelike-bench-driver:local") + 1 :] == ["run"]
    assert f"BENCH_OUT={base}" in after(argv, "-e")
    assert f"{base}:{base}" in after(argv, "-v")


def test_no_host_environment_is_forwarded(harness: dict[str, object]) -> None:
    env = harness["env"]
    assert isinstance(env, dict)
    env["ANTHROPIC_API_KEY"] = "must-not-travel"
    p, argv = run_sh(harness)
    assert p.returncode == 0, p.stderr
    assert sorted(a.split("=", 1)[0] for a in after(argv, "-e")) == [
        "BENCH_BASE_DIGEST", "BENCH_GIT_SHA", "BENCH_OUT", "BENCH_REPRODUCE",
    ]  # fmt: skip
    assert not any("must-not-travel" in a for a in argv)


@pytest.mark.parametrize(
    ("args", "extra", "code", "text"),
    [
        (["--bogus"], {}, 2, "unknown argument"),
        (["--out"], {}, 2, "--out needs a directory"),
        ([], {"GIT_SHA": ""}, 1, "GIT_SHA is empty"),
        ([], {"DOCKER_HOST": "tcp://elsewhere:2375"}, 1, "not the local socket"),
        ([], {"BENCH_DOCKER_SOCKET": "/nonexistent.sock"}, 1, "no Docker socket"),
    ],
)
def test_refusals(
    harness: dict[str, object], args: list[str], extra: dict[str, str], code: int, text: str
) -> None:
    env = harness["env"]
    assert isinstance(env, dict)
    env.update(extra)
    p, argv = run_sh(harness, *args)
    assert p.returncode == code and text in p.stderr
    assert argv == []
