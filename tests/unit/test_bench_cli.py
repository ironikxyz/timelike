"""timelike-bench, the CLI (T009): contract conformance, run, report, catalog, and every refusal.

The tool runs as a real subprocess (the contract is about what a process does on its streams). Docker
is replaced by tests/unit/fakedocker.py, which runs each "container" as a local directory under the
vanilla / timelike emulations of test_bench_catalog.py — so a full `run` over the real catalog, the
real runner and the real wrapper happens here, and only the docker leg is left to the Docker lane.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import pytest
import test_bench_catalog as cat_t
from conftest import AGENTIO_DIR, REPO, run
from test_conform import install

SHA = "0123456789abcdef0123456789abcdef01234567"
DIGEST = "debian:trixie-slim@sha256:" + "d" * 64
BENCH_BIN = REPO / "bench" / "bin" / "timelike-bench"
FAKE_DOCKER = Path(__file__).with_name("fakedocker.py")
IDS = {"vanilla": "sha256:" + "a" * 64, "timelike": "sha256:" + "b" * 64, "driver": "sha256:" + "c" * 64}


def exec_env(kind: str) -> dict[str, str]:
    return {k: v for k, v in cat_t._env(kind, Path("@HOME@")).items()}


def docker_config(root: Path, **over: Any) -> Path:
    def img(key: str, exec_env_: dict[str, str]) -> dict[str, Any]:
        return {"id": IDS[key], "revision": SHA, "env": ["PATH=/usr/bin"], "exec_env": exec_env_}

    images = {
        "timelike-vanilla:local": img("vanilla", exec_env("vanilla")),
        "timelike-agent:local": img("timelike", exec_env("timelike")),
        "timelike-bench-driver:local": img("driver", {}),
    }
    for ref, changes in over.items():
        images[ref.replace("_", "-") + ":local"].update(changes)
    cfg = root / "fakedocker.json"
    cfg.write_text(json.dumps({"root": str(root / "containers"), "images": images}))
    return cfg


@pytest.fixture
def bench(tmp_path: Path) -> dict[str, Any]:
    bindir = tmp_path / "bin"
    tool = install(BENCH_BIN, bindir)
    fakebin = tmp_path / "fakebin"  # apart from bin/, so conformance never checks the stand-in
    fakebin.mkdir()
    docker = fakebin / "docker"
    docker.write_text(f'#!/bin/sh\nexec {sys.executable} {FAKE_DOCKER} "$@"\n')
    docker.chmod(0o755)
    scratch = tmp_path / "scratch"
    env = {
        "PATH": f"{bindir}:/usr/bin:/bin",
        "PYTHONPATH": f"{AGENTIO_DIR}:{REPO / 'bench'}",
        "HOME": str(tmp_path),
        "TIMELIKE_SCRATCH_ROOT": str(scratch),
        "TIMELIKE_SESSION": "test",
        "LC_ALL": "C.UTF-8",
        "BENCH_GIT_SHA": SHA,
        "BENCH_BASE_DIGEST": DIGEST,
        "BENCH_REPRODUCE": "make bench",
        "TIMELIKE_BENCH_DOCKER": str(docker),
        "FAKE_DOCKER_CONFIG": str(docker_config(tmp_path)),
    }
    if "COVERAGE_PROCESS_START" in os.environ:  # measure the tool as a subprocess (reboot.md recipe)
        env["COVERAGE_PROCESS_START"] = os.environ["COVERAGE_PROCESS_START"]
    return {"tool": tool, "env": env, "tmp": tmp_path, "out": tmp_path / "out"}


def bench_run(b: dict[str, Any], *args: str, timeout: float = 120, **env: str) -> Any:
    return run([str(b["tool"]), *args], {**b["env"], **env}, timeout=timeout)


def test_catalog_text_and_json(bench: dict[str, Any]) -> None:
    p = bench_run(bench, "catalog", "--text")
    assert p.returncode == 0, p.stderr
    assert p.stdout.splitlines()[0] == "timelike-bench: catalog [slice 0]"
    assert "task git-commit-hook-rejects" in p.stdout
    doc = json.loads(bench_run(bench, "catalog", "--json").stdout)
    assert [t["id"] for t in doc["tasks"]][:1] == ["git-inspect"]
    assert len(doc["not_benchable"]) == 6


def test_timelike_conform_passes_over_the_bench_tool(bench: dict[str, Any], tmp_path: Path) -> None:
    conform_dir = tmp_path / "conform"
    install(REPO / "tools" / "bin" / "timelike-conform", conform_dir)
    env = {**bench["env"], "PATH": f"{bench['tool'].parent}:{conform_dir}:/usr/bin:/bin"}
    env["TIMELIKE_BIN_DIRS"] = str(bench["tool"].parent)
    env["TIMELIKE_CONFORM_TIMEOUT"] = "10"
    p = run([str(conform_dir / "timelike-conform"), "--json"], env, timeout=120)
    doc = json.loads(p.stdout)
    assert p.returncode == 0, doc
    assert "timelike-bench" in json.dumps(doc)


@pytest.fixture
def full_run(bench: dict[str, Any]) -> tuple[dict[str, Any], Any]:
    p = bench_run(bench, "run", "--out", str(bench["out"]), "--call-limit", "2", "--text", "--limit", "0")
    return bench, p


def test_run_writes_eight_traces_and_the_report(full_run: tuple[dict[str, Any], Any]) -> None:
    b, p = full_run
    assert p.returncode == 0, p.stderr
    lines = p.stdout.splitlines()
    assert (
        lines[0]
        == f"timelike-bench: {b['out']} [FAKE-AGENT BENCH PIPELINE DEMO RUN -- not a test of timelike]"
    )
    assert lines[-1] == f"report: {b['out'] / 'report.txt'}"
    assert len(list((b["out"] / "traces").glob("*.json"))) == 8
    report = (b["out"] / "report.txt").read_text().splitlines()
    assert report[0].startswith("FAKE-AGENT BENCH PIPELINE DEMO RUN -- This is not a test of timelike")
    appendix = report.index("## Appendix: tokens")
    assert not any("token" in line.lower() for line in report[:appendix])  # the REAL catalog's text too
    # 001 cycle 5 (discovery revision 7): hooks run, bounded, so the hooks-off loss became a tie.
    assert "## Timelike loses (0)" in report
    assert "## Ties (2)" in report and "## Timelike wins (2)" in report


def test_the_hook_tasks_explain_themselves_from_the_report_alone(
    full_run: tuple[dict[str, Any], Any],
) -> None:
    """Send …-080659's acceptance (the report explains itself), held against 001 cycle 5's new default:
    the rejects section says both images ran the hook and both kept the policy; the hangs section says
    timelike's limit stopped the hook with a verdict. The real test is a person reading it (SC-3)."""
    b, _ = full_run
    report = (b["out"] / "report.txt").read_text()
    rejects = report[report.index("### git-commit-hook-rejects") :]
    rejects = rejects[: rejects.index("\n### ") if "\n### " in rejects else len(rejects)]
    assert "Tests: Hooks run (a repository's own policy). Both images run the repository's hooks" in rejects
    assert "Verdict: Tie — both completed" in rejects
    for arm in ("vanilla", "timelike"):
        assert (
            f"What happened in {arm}:\n  1. `git commit -m 'bench: update f'` → exit 1: "
            "pre-commit: TODO found" in rejects
        )
    hangs = report[report.index("### git-commit-hook-hangs") :]
    hangs = hangs[: hangs.index("\n### ") if "\n### " in hangs else len(hangs)]
    assert "Tests: Hooks run, bounded (a hook that never finishes)." in hangs
    assert (
        "What happened in timelike:\n  1. `git commit -m 'bench: update f'` → exit 1: "
        "error: git hook pre-commit" in hangs
    )
    assert "Why: The pre-commit hook ran under timelike's limit and was stopped with a verdict" in hangs


def test_run_removes_every_container(full_run: tuple[dict[str, Any], Any]) -> None:
    b, _ = full_run
    root = b["tmp"] / "containers"
    started = [d.name for d in root.iterdir() if d.is_dir()]
    removed = (root / "removed.log").read_text().split()
    assert len(started) == 8 and sorted(started) == sorted(removed)


def test_report_rebuilds_from_traces_alone(full_run: tuple[dict[str, Any], Any]) -> None:
    b, _ = full_run
    before = (b["out"] / "report.txt").read_text()
    (b["out"] / "report.txt").unlink()
    p = bench_run(b, "report", str(b["out"]), "--text", "--limit", "0")
    assert p.returncode == 0, p.stderr
    assert (b["out"] / "report.txt").read_text() == before
    assert p.stdout.splitlines()[2].startswith("FAKE-AGENT BENCH PIPELINE DEMO RUN")


def test_out_is_exactly_the_directory_and_a_used_one_is_refused(full_run: tuple[dict[str, Any], Any]) -> None:
    b, _ = full_run
    assert (b["out"] / "traces").is_dir() and not any(p.is_dir() for p in (b["out"] / "traces").iterdir())
    p = bench_run(b, "run", "--out", str(b["out"]), "--task", "git-inspect")
    assert p.returncode == 1
    assert "already holds traces" in p.stderr
    assert len(list((b["out"] / "traces").glob("*.json"))) == 8  # nothing was added or mixed in


def test_planted_api_key_refuses_before_anything(bench: dict[str, Any]) -> None:
    p = bench_run(bench, "run", "--out", str(bench["out"]), ANTHROPIC_API_KEY="x")
    assert p.returncode == 4
    assert "ANTHROPIC_API_KEY" in p.stderr
    assert not bench["out"].exists()
    assert not (bench["tmp"] / "containers").exists()  # docker was never called


def test_key_baked_into_an_image_refuses(bench: dict[str, Any]) -> None:
    cfg = docker_config(bench["tmp"], timelike_agent={"env": ["PATH=/usr/bin", "OPENAI_API_KEY=x"]})
    p = bench_run(bench, "run", "--out", str(bench["out"]), FAKE_DOCKER_CONFIG=str(cfg))
    assert p.returncode == 4 and "OPENAI_API_KEY" in p.stderr
    assert not (bench["out"] / "traces").exists()


def test_key_in_a_task_container_refuses_and_removes_it(bench: dict[str, Any]) -> None:
    cfg = docker_config(bench["tmp"], timelike_vanilla={"container_env": ["GH_TOKEN=x"]})
    p = bench_run(bench, "run", "--out", str(bench["out"]), FAKE_DOCKER_CONFIG=str(cfg))
    assert p.returncode == 4 and "GH_TOKEN" in p.stderr
    removed = (bench["tmp"] / "containers" / "removed.log").read_text().split()
    assert len(removed) == 1


def test_stale_image_refuses_naming_both_revisions(bench: dict[str, Any]) -> None:
    cfg = docker_config(bench["tmp"], timelike_agent={"revision": "f" * 40})
    p = bench_run(bench, "run", "--out", str(bench["out"]), FAKE_DOCKER_CONFIG=str(cfg))
    assert p.returncode == 1
    assert "f" * 40 in p.stderr and SHA in p.stderr and "stale" in p.stderr
    assert not (bench["out"] / "traces").exists()


def test_blank_stamp_refuses(bench: dict[str, Any]) -> None:
    cfg = docker_config(bench["tmp"], timelike_vanilla={"revision": ""})
    p = bench_run(bench, "run", "--out", str(bench["out"]), FAKE_DOCKER_CONFIG=str(cfg))
    assert p.returncode == 1 and "unstamped" in p.stderr


def test_missing_image_is_a_named_failure(bench: dict[str, Any]) -> None:
    cfg = json.loads(Path(bench["env"]["FAKE_DOCKER_CONFIG"]).read_text())
    del cfg["images"]["timelike-bench-driver:local"]
    path = bench["tmp"] / "missing.json"
    path.write_text(json.dumps(cfg))
    p = bench_run(bench, "run", FAKE_DOCKER_CONFIG=str(path))
    assert p.returncode == 1 and "No such image" in p.stderr and "make bench-images" in p.stderr


def test_term_inside_a_task_container_refuses(bench: dict[str, Any]) -> None:
    env = {**exec_env("vanilla"), "TERM": "xterm"}
    cfg = docker_config(bench["tmp"], timelike_vanilla={"exec_env": env})
    p = bench_run(bench, "run", "--out", str(bench["out"]), FAKE_DOCKER_CONFIG=str(cfg))
    assert p.returncode == 1 and "TERM=xterm" in p.stderr


@pytest.mark.parametrize(
    ("args", "env", "code", "text"),
    [
        (["run", "--task", "no-such-task"], {}, 3, "unknown task"),
        (["run", "somedir"], {}, 2, "no directory argument"),
        (["run", "--call-limit", "0"], {}, 2, "must be positive"),
        (["run"], {"BENCH_GIT_SHA": ""}, 1, "BENCH_GIT_SHA is empty"),
        (["run"], {"BENCH_BASE_DIGEST": ""}, 1, "BENCH_BASE_DIGEST is empty"),
        (["report"], {}, 2, "needs a run directory"),
        ([], {}, 2, "no action given"),
    ],
)
def test_usage_and_refusals(
    bench: dict[str, Any], args: list[str], env: dict[str, str], code: int, text: str
) -> None:
    p = bench_run(bench, *args, **env)
    assert p.returncode == code, (p.stdout, p.stderr)
    assert text in p.stderr


def test_report_over_an_empty_directory_is_not_found(bench: dict[str, Any], tmp_path: Path) -> None:
    p = bench_run(bench, "report", str(tmp_path / "nothing"))
    assert p.returncode == 3 and "no traces" in p.stderr


def test_report_over_a_corrupt_trace_fails(bench: dict[str, Any], tmp_path: Path) -> None:
    (tmp_path / "bad" / "traces").mkdir(parents=True)
    (tmp_path / "bad" / "traces" / "x--vanilla.json").write_text("{}")
    p = bench_run(bench, "report", str(tmp_path / "bad"))
    assert p.returncode == 1 and "invalid trace" in p.stderr


def test_one_task_with_default_out_under_bench_out(bench: dict[str, Any], tmp_path: Path) -> None:
    p = bench_run(bench, "run", "--task", "git-inspect", "--json", BENCH_OUT=str(tmp_path / "o"))
    doc = json.loads(p.stdout)
    assert p.returncode == 0, p.stderr
    assert doc["verdicts"] == {"git-inspect": "tie"}
    assert Path(doc["out"]).parent == tmp_path / "o"
    assert len(list(Path(doc["out"], "traces").glob("*.json"))) == 2
