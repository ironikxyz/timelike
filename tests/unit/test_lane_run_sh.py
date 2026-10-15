"""tests/run.sh, the Docker lane's driver: scope, parallelism and order (maint-lane-speed).

No Docker here, so the lane runs in a scratch copy of the repository with a stand-in `docker` and `make`
that log their arguments and answer as a healthy stack would. That checks what run.sh decides and hands
on: the first line and summary.json's scope, the refusals, the e2e command (serial: exactly `bats
tests/e2e`; parallel: --jobs, the lock, lane.conf's order), the unit step's two parts, and gounit beside
e2e. Whether the cells pass side by side is the Docker lane's to show (the mentor's proof lanes).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from conftest import REPO

FILES = ("a.bats", "b-long.bats", "c.bats", "d-timed.bats", "e.bats")
LANE_CONF = """# test lane.conf
first   b-long.bats  # the longest
serial  d-timed.bats  # measures the machine
"""

FAKE_DOCKER = r"""#!/bin/sh
printf '%s\037' "$@" >> "$LOG/docker.log"; printf '\n' >> "$LOG/docker.log"
case "$1" in
  info|build|compose|rm) exit 0 ;;
  inspect) echo healthy ;;
  ps) printf '%s\n' "$FAKE_STALE" ;;
  create) echo cid-1 ;;
  cp) : > "$3" ;;
  run)
    for a in "$@"; do
      case "$a" in
        timelike-test-runner:local) printf '1..1\nok 1 cell # in 1 ms\n'; exit 0 ;;
        timelike-agent:local) echo "1 passed"; exit 0 ;;
      esac
    done ;;
esac
exit 0
"""


@pytest.fixture
def lane(tmp_path: Path) -> dict[str, object]:
    root = tmp_path / "repo"
    (root / "tests" / "e2e").mkdir(parents=True)
    shutil.copy(REPO / "tests" / "run.sh", root / "tests" / "run.sh")
    shutil.copy(REPO / "pins.env", root / "pins.env")
    for f in FILES:
        (root / "tests" / "e2e" / f).write_text("@test x { :; }\n")
    (root / "tests" / "e2e" / "lane.conf").write_text(LANE_CONF)
    git = ["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@example.invalid"]
    subprocess.run([*git, "init", "-q"], check=True)
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run([*git, "commit", "-q", "-m", "x"], check=True)
    fakebin = tmp_path / "fakebin"
    fakebin.mkdir()
    (fakebin / "docker").write_text(FAKE_DOCKER)
    (fakebin / "make").write_text('#!/bin/sh\necho "$@" >> "$LOG/make.log"\n')
    for f in ("docker", "make"):
        (fakebin / f).chmod(0o755)
    logs = tmp_path / "logs"
    logs.mkdir()
    env = {
        "PATH": f"{fakebin}:/usr/bin:/bin",
        "HOME": str(tmp_path),
        "LOG": str(logs),
        "DOCKER_HOST": "tcp://stand-in:2375",
        "FAKE_STALE": "",
    }
    return {"root": root, "env": env, "logs": logs}


def run_lane(
    lane: dict[str, object], **env: str
) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
    root = lane["root"]
    assert isinstance(root, Path)
    base = lane["env"]
    assert isinstance(base, dict)
    p = subprocess.run(
        [str(root / "tests" / "run.sh")], env={**base, **env}, capture_output=True, text=True, timeout=60,
        stdin=subprocess.DEVNULL,
    )  # fmt: skip
    summary = root / "tests" / "out" / "summary.json"
    return p, json.loads(summary.read_text()) if summary.exists() else {}


def docker_calls(lane: dict[str, object]) -> list[list[str]]:
    logs = lane["logs"]
    assert isinstance(logs, Path)
    log = logs / "docker.log"
    if not log.exists():
        return []
    return [line.rstrip("\x1f").split("\x1f") for line in log.read_text().splitlines() if line]


def runner_call(lane: dict[str, object]) -> list[str]:
    (call,) = [c for c in docker_calls(lane) if c[0] == "run" and "timelike-test-runner:local" in c]
    return call


def unit_calls(lane: dict[str, object]) -> list[list[str]]:
    return [c for c in docker_calls(lane) if c[0] == "run" and "timelike-agent:local" in c]


def pin(name: str) -> str:
    for line in (REPO / "pins.env").read_text().splitlines():
        if line.startswith(f"{name}="):
            return line.split("=", 1)[1]
    raise AssertionError(f"pins.env has no {name}")


def after_image(call: list[str], image: str) -> list[str]:
    return call[call.index(image) + 1 :]


def test_a_serial_lane_is_the_old_command_exactly(lane: dict[str, object]) -> None:
    p, summary = run_lane(lane, E2E_JOBS="1", UNIT_JOBS="1")
    assert p.returncode == 0, p.stdout + p.stderr
    assert p.stdout.splitlines()[0] == "scope: full"
    runner = runner_call(lane)
    assert after_image(runner, "timelike-test-runner:local") == [
        "--formatter", "tap", "--report-formatter", "junit", "--output", "/out", "--timing", "tests/e2e",
    ]  # fmt: skip
    assert not any(a.startswith("TL_E2E_") for a in runner)
    (unit,) = unit_calls(lane)
    assert after_image(unit, "timelike-agent:local") == [
        "uv", "run", "--no-project", "--python", "/opt/timelike/python/bin/python3",
        "--with", f"pytest=={pin('PYTEST_VERSION')}",
        "python", "-m", "pytest", "-q", "-rP", "-p", "no:cacheprovider", "tests/unit",
    ]  # fmt: skip
    assert summary["scope"] == "full" and summary["e2e_files"] == []
    assert [s["name"] for s in summary["steps"]][-3:] == ["e2e", "unit", "gounit"]
    assert summary["exit"] == 0


def test_a_parallel_lane_runs_files_side_by_side_in_lane_conf_s_order(lane: dict[str, object]) -> None:
    p, summary = run_lane(lane, FAKE_STALE="stale-1")
    assert p.returncode == 0, p.stdout + p.stderr
    runner = runner_call(lane)
    tail = after_image(runner, "timelike-test-runner:local")
    assert tail[:3] == ["--jobs", "8", "--no-parallelize-within-files"]
    files = [a for a in tail if a.startswith("tests/e2e/")]
    assert files == [f"tests/e2e/{n}" for n in ("b-long.bats", "a.bats", "c.bats", "e.bats", "d-timed.bats")]
    assert "TL_E2E_LOCK=/out/.e2e-lane.lock" in runner
    assert "TL_E2E_SERIAL_FILES=d-timed.bats" in runner
    # The sweep six files did in setup_file is done once, before the lane.
    assert ["rm", "-f", "stale-1"] in docker_calls(lane)
    spread, timed = unit_calls(lane)
    assert spread[-5:] == ["-n", "8", "-m", "not timed", "tests/unit"]
    assert timed[-3:] == ["-m", "timed", "tests/unit"]
    assert f"pytest-xdist=={pin('PYTEST_XDIST_VERSION')}" in spread
    assert f"execnet=={pin('EXECNET_VERSION')}" in spread
    assert summary["e2e_jobs"] == "8" and summary["unit_jobs"] == "8"
    steps = {s["name"]: s for s in summary["steps"]}
    assert all(steps[n]["status"] == "pass" for n in ("e2e", "unit", "gounit"))
    assert summary["exit"] == 0


def test_gounit_runs_beside_e2e_and_every_step_keeps_its_rc_line(lane: dict[str, object]) -> None:
    if shutil.which("flock") is None:
        pytest.skip("no flock on this host: the lane runs its steps one after another, and says so")
    p, summary = run_lane(lane)
    assert p.returncode == 0, p.stdout + p.stderr
    assert summary["steps_together"] == "gounit ran beside e2e"
    out = p.stdout
    assert "════ step gounit: run_go_unit — started beside e2e" in out
    for name in ("e2e", "unit", "gounit"):
        assert f"════ step {name}: rc=0 (" in out
    # unit after e2e, never beside it; gounit's output is printed when it is collected
    assert out.index("════ step e2e: rc=0") < out.index("════ step unit: run_unit")
    assert [s["name"] for s in summary["steps"]][-3:] == ["e2e", "unit", "gounit"]
    p, summary = run_lane(lane, LANE_STEPS_TOGETHER="0")
    assert p.returncode == 0 and summary["steps_together"] == "no"
    assert "started beside e2e" not in p.stdout


def test_a_partial_lane_says_so_first_and_runs_only_its_files(lane: dict[str, object]) -> None:
    p, summary = run_lane(lane, LANE_SCOPE="partial", E2E_FILES="d-timed.bats tests/e2e/a.bats")
    assert p.returncode == 0, p.stdout + p.stderr
    assert p.stdout.splitlines()[0] == "scope: partial — e2e files: d-timed.bats tests/e2e/a.bats"
    files = [a for a in runner_call(lane) if a.startswith("tests/e2e/")]
    assert files == ["tests/e2e/a.bats", "tests/e2e/d-timed.bats"]  # lane.conf's rule, over the subset
    assert summary["scope"] == "partial"
    assert summary["e2e_files"] == ["d-timed.bats", "tests/e2e/a.bats"]
    assert len(unit_calls(lane)) == 2  # all of unit


def test_a_serial_partial_lane_runs_the_files_as_given(lane: dict[str, object]) -> None:
    p, _ = run_lane(lane, LANE_SCOPE="partial", E2E_FILES="e.bats a.bats", E2E_JOBS="1")
    assert p.returncode == 0, p.stdout + p.stderr
    tail = after_image(runner_call(lane), "timelike-test-runner:local")
    assert tail[-2:] == ["tests/e2e/e.bats", "tests/e2e/a.bats"] and "--jobs" not in tail


@pytest.mark.parametrize(
    ("env", "why"),
    [
        ({"LANE_SCOPE": "partial"}, "a partial lane needs E2E_FILES"),
        ({"LANE_SCOPE": "partial", "E2E_FILES": "a.bats nosuch.bats"}, "E2E_FILES names nosuch.bats"),
        ({"LANE_SCOPE": "partial", "E2E_FILES": "a.bats a.bats"}, "names a.bats twice"),
        ({"LANE_SCOPE": "partial", "E2E_FILES": "lane.conf"}, "E2E_FILES names lane.conf"),
        ({"E2E_FILES": "a.bats"}, "E2E_FILES is set (a.bats) for a full lane"),
        ({"E2E_JOBS": "0"}, "E2E_JOBS is '0', not a positive integer"),
        ({"UNIT_JOBS": "x"}, "UNIT_JOBS is 'x', not a positive integer"),
        ({"LANE_SCOPE": "some"}, "LANE_SCOPE is 'some'"),
    ],
)
def test_a_lane_that_would_not_be_what_it_says_is_refused_before_anything_runs(
    lane: dict[str, object], env: dict[str, str], why: str
) -> None:
    p, summary = run_lane(lane, **env)
    assert p.returncode == 2, p.stdout + p.stderr
    assert p.stdout.splitlines()[0].startswith("scope: ")
    assert why in p.stdout + p.stderr
    assert summary["exit"] == 2
    logs = lane["logs"]
    assert isinstance(logs, Path)
    assert not (logs / "make.log").exists() and docker_calls(lane) == []


def test_a_lane_conf_naming_a_missing_file_fails_the_e2e_step(lane: dict[str, object]) -> None:
    root = lane["root"]
    assert isinstance(root, Path)
    (root / "tests" / "e2e" / "lane.conf").write_text("serial gone.bats  # renamed\n")
    p, summary = run_lane(lane)
    assert p.returncode == 1
    assert "tests/e2e/lane.conf names gone.bats, which is not a file in tests/e2e" in p.stdout + p.stderr
    assert {s["name"]: s["status"] for s in summary["steps"]}["e2e"] == "fail"


# ── The repository's own lane.conf and e2e files ────────────────────────────────────────────────────────


def test_lane_conf_names_real_files_and_gives_every_serial_file_a_reason() -> None:
    e2e = REPO / "tests" / "e2e"
    kinds: dict[str, list[str]] = {"first": [], "serial": []}
    for line in (e2e / "lane.conf").read_text().splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        kind, name, *rest = line.split()
        assert kind in kinds, line
        assert (e2e / name).is_file(), f"lane.conf names {name}, not a file in tests/e2e"
        assert rest[:1] == ["#"] and len(rest) > 2, f"{name}: no reason given"
        kinds[kind].append(name)
    assert not set(kinds["first"]) & set(kinds["serial"])
    assert len(set(kinds["serial"])) == len(kinds["serial"])


def test_every_e2e_file_takes_the_lane_lock() -> None:
    # A file that took no lock would run beside a serial file, which is the one thing a serial file forbids.
    for f in sorted((REPO / "tests" / "e2e").glob("*.bats")):
        lines = f.read_text().splitlines()
        assert "load helpers" in lines or "load lane" in lines, f"{f.name} loads neither helpers nor lane"
