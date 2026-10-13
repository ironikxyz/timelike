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


# --- slice 1: the live run's flags, the key file, the forwarded configuration (FR-29, FR-50) --------


def test_live_flags_pass_through_and_reproduce_names_bench_live(harness: dict[str, object]) -> None:
    p, argv = run_sh(
        harness, "--harness", "opencode", "--harness", "codex", "--arm", "told", "--dry-run", "--standin"
    )
    assert p.returncode == 0, p.stderr
    driver_args = argv[argv.index("timelike-bench-driver:local") + 1 :]
    assert driver_args == [
        "run",
        "--harness",
        "opencode",
        "--harness",
        "codex",
        "--arm",
        "told",
        "--dry-run",
        "--standin",
    ]
    assert "BENCH_REPRODUCE=make bench-live" in after(argv, "-e")


def test_the_bench_configuration_is_forwarded_by_name_and_value(harness: dict[str, object]) -> None:
    env = harness["env"]
    assert isinstance(env, dict)
    env.update(
        BENCH_MODEL="deepseek/deepseek-v4-pro-0813",
        BENCH_TURN_CAP="12",
        BENCH_SPEND_CAP_USD="2.50",
        OPENCODE_VERSION="1.19.0",
        CODEX_VERSION="0.162.1",
    )
    p, argv = run_sh(harness, "--harness", "opencode")
    assert p.returncode == 0, p.stderr
    e = after(argv, "-e")
    for want in (
        "BENCH_MODEL=deepseek/deepseek-v4-pro-0813",
        "BENCH_TURN_CAP=12",
        "BENCH_SPEND_CAP_USD=2.50",
        "BENCH_OPENCODE_VERSION=1.19.0",
        "BENCH_CODEX_VERSION=0.162.1",
    ):
        assert want in e


def test_a_good_key_file_is_mounted_read_only_and_its_value_never_travels(harness: dict[str, object]) -> None:
    tmp = harness["tmp"]
    env = harness["env"]
    assert isinstance(tmp, Path) and isinstance(env, dict)
    key = tmp / "secrets" / "or.key"
    key.parent.mkdir()
    key.write_text("value-that-must-not-travel\n")
    key.chmod(0o600)
    env["BENCH_KEY_FILE"] = str(key)
    p, argv = run_sh(harness, "--harness", "opencode")
    assert p.returncode == 0, p.stderr
    assert f"{key.resolve()}:/run/timelike-bench/key:ro" in after(argv, "-v")
    assert "BENCH_KEY_FILE=/run/timelike-bench/key" in after(argv, "-e")
    assert not any("value-that-must-not-travel" in a for a in argv)


@pytest.mark.parametrize(
    ("setup", "text"),
    [
        ("mode", "mode is 0644, must be 0600"),
        ("link", "is a symbolic link"),
        ("missing", "is not a regular file"),
        ("relative", "is not an absolute path"),
        ("inside", "is inside the repository"),
    ],
)
def test_a_bad_key_file_is_refused_on_the_host(harness: dict[str, object], setup: str, text: str) -> None:
    tmp = harness["tmp"]
    env = harness["env"]
    assert isinstance(tmp, Path) and isinstance(env, dict)
    key = tmp / "or.key"
    key.write_text("x\n")
    key.chmod(0o644 if setup == "mode" else 0o600)
    path = str(key)
    if setup == "link":
        (tmp / "link").symlink_to(key)
        path = str(tmp / "link")
    elif setup == "missing":
        path = str(tmp / "absent")
    elif setup == "relative":
        path = "or.key"
    elif setup == "inside":
        inside = REPO / "bench" / "out" / ".unit-key-file"
        inside.parent.mkdir(exist_ok=True)
        inside.write_text("x\n")
        inside.chmod(0o600)
        path = str(inside)
    env["BENCH_KEY_FILE"] = path
    try:
        p, argv = run_sh(harness, "--harness", "opencode")
    finally:
        if setup == "inside":
            Path(path).unlink()
    assert p.returncode == 4 and text in p.stderr, p.stderr
    assert argv == []
