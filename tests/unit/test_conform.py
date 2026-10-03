"""timelike-conform (SC-5; contracts/conformance.md) and the timelike tool itself.

The shipped tools and the fixtures carry the image's shebang. On the host lane they are installed
into temporary bin directories with the shebang rewritten to this interpreter, which is the only
difference from the image (where agentio is importable under -I from site-packages).
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import pytest
from conftest import AGENTIO_DIR, FIXTURES, TOOLS_DIR, events, run

REVISION = "0123456789abcdef0123456789abcdef01234567"


def install(src: Path, bindir: Path) -> Path:
    bindir.mkdir(parents=True, exist_ok=True)
    lines = src.read_text().splitlines(keepends=True)
    assert lines[0].startswith("#!/opt/timelike/python/bin/python3"), f"{src} has an unexpected shebang"
    dst = bindir / src.name
    dst.write_text(f"#!{sys.executable}\n" + "".join(lines[1:]))
    dst.chmod(0o755)
    return dst


@pytest.fixture
def good(tmp_path: Path) -> Path:
    d = tmp_path / "good"
    install(TOOLS_DIR / "timelike", d)
    install(TOOLS_DIR / "timelike-conform", d)
    return d


def env_for(
    scratch: Path, dirs: list[Path], on_path: list[Path] | None = None, **extra: str
) -> dict[str, str]:
    path_dirs = dirs if on_path is None else on_path
    env = {
        "PATH": ":".join([*(str(d) for d in path_dirs), "/usr/bin", "/bin"]),
        "PYTHONPATH": str(AGENTIO_DIR),
        "HOME": str(scratch.parent),
        "TIMELIKE_SCRATCH_ROOT": str(scratch),
        "TIMELIKE_SESSION": "test",
        "TIMELIKE_BIN_DIRS": ":".join(str(d) for d in dirs),
        "TIMELIKE_REVISION": REVISION,
        "TIMELIKE_CONFORM_TIMEOUT": "5",
        "LC_ALL": "C.UTF-8",
    }
    if "COVERAGE_PROCESS_START" in os.environ:
        env["COVERAGE_PROCESS_START"] = os.environ["COVERAGE_PROCESS_START"]
    env.update(extra)
    return env


def conform(env: dict[str, str], *args: str, timeout: float = 60) -> Any:
    return run(["timelike-conform", *args], env, timeout=timeout)


def checks_for(doc: dict[str, Any], tool: str) -> set[str]:
    return {f["check"] for f in doc["failures"] if f["tool"] == tool}


# ── conformance: positive ──────────────────────────────────────────────────────────────────────


def test_conform_passes_over_the_shipped_tools(good: Path, scratch: Path) -> None:
    r = conform(env_for(scratch, [good]), "--json")
    doc = json.loads(r.stdout)
    assert r.returncode == 0, doc["failures"]
    assert doc["verdict"] == "pass"
    assert doc["checked"] == 2
    assert doc["tools"] == ["timelike", "timelike-conform"]


def test_conform_list_probe(good: Path, scratch: Path) -> None:
    r = conform(env_for(scratch, [good]), "--text", "--list")
    assert r.returncode == 0
    lines = r.stdout.splitlines()
    assert lines[0].startswith("timelike-conform: ")
    assert any(x.endswith("/timelike") for x in lines)


# ── conformance: negative (the check must be able to fail) ─────────────────────────────────────


def test_conform_names_every_violation_of_the_bad_tool(good: Path, tmp_path: Path, scratch: Path) -> None:
    bad = tmp_path / "bad"
    install(FIXTURES / "bad-tool" / "timelike-bad", bad)
    r = conform(env_for(scratch, [good, bad]), "--json")
    assert r.returncode == 1
    doc = json.loads(r.stdout)
    assert doc["verdict"] == "fail"
    assert checks_for(doc, "timelike-bad") == {"C1", "C5", "C7"}
    assert checks_for(doc, "timelike") == set()
    keys = [(f["tool"], f["check"]) for f in doc["failures"]]
    assert keys == sorted(keys)
    text = conform(env_for(scratch, [good, bad]), "--text", "--limit", "0").stdout
    for c in ("C1", "C5", "C7"):
        assert any(line.startswith(f"FAIL timelike-bad {c} ") for line in text.splitlines()), text


def test_conform_bounds_a_tool_that_never_concludes(tmp_path: Path, scratch: Path) -> None:
    hang = tmp_path / "hang"
    install(FIXTURES / "bad-tool" / "timelike-hang", hang)
    conf = tmp_path / "conf"
    install(TOOLS_DIR / "timelike-conform", conf)
    env = env_for(scratch, [hang], on_path=[hang, conf], TIMELIKE_CONFORM_TIMEOUT="2")
    t0 = time.monotonic()
    r = conform(env, "--json", timeout=30)
    elapsed = time.monotonic() - t0
    assert r.returncode == 1
    doc = json.loads(r.stdout)
    details = [f["detail"] for f in doc["failures"] if f["tool"] == "timelike-hang"]
    assert any("did not conclude" in d for d in details), details
    assert elapsed < 15, (
        f"conform took {elapsed:.1f}s; a hanging tool must cost one probe limit, not sixty seconds"
    )


def test_conform_with_zero_tools_fails(tmp_path: Path, scratch: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    conf = tmp_path / "conf"
    install(TOOLS_DIR / "timelike-conform", conf)
    r = conform(env_for(scratch, [empty], on_path=[empty, conf]), "--json")
    assert r.returncode == 1
    assert json.loads(r.stdout)["checked"] == 0


def test_conform_reports_a_bin_dir_not_on_path(good: Path, tmp_path: Path, scratch: Path) -> None:
    hidden = tmp_path / "hidden"
    install(TOOLS_DIR / "timelike", hidden)
    r = conform(env_for(scratch, [good, hidden], on_path=[good]), "--json")
    assert r.returncode == 1
    doc = json.loads(r.stdout)
    assert any("not on PATH" in f["detail"] for f in doc["failures"])


def test_conform_writes_nothing_outside_scratch(good: Path, tmp_path: Path, scratch: Path) -> None:
    before = set(os.listdir(tmp_path))
    conform(env_for(scratch, [good]), "--json")
    assert set(os.listdir(tmp_path)) - before <= {"scratch"}


# ── timelike itself ────────────────────────────────────────────────────────────────────────────


def test_timelike_agent_info_carries_the_revision(good: Path, scratch: Path) -> None:
    r = run(["timelike", "--agent-info"], env_for(scratch, [good]))
    assert r.returncode == 0
    assert json.loads(r.stdout)["revision"] == REVISION


def test_timelike_reads_the_revision_file(good: Path, tmp_path: Path, scratch: Path) -> None:
    f = tmp_path / "REVISION"
    f.write_text(REVISION)  # the image writes it without a trailing newline
    env = env_for(scratch, [good], TIMELIKE_REVISION_FILE=str(f))
    del env["TIMELIKE_REVISION"]
    assert json.loads(run(["timelike", "--agent-info"], env).stdout)["revision"] == REVISION


@pytest.mark.parametrize("content", [None, "", "\n"])
def test_timelike_empty_or_missing_stamp_is_a_failure(
    good: Path, tmp_path: Path, scratch: Path, content: str | None
) -> None:
    f = tmp_path / "REVISION"
    if content is not None:
        f.write_text(content)
    env = env_for(scratch, [good], TIMELIKE_REVISION_FILE=str(f))
    del env["TIMELIKE_REVISION"]
    r = run(["timelike", "--agent-info", "--json"], env)
    assert r.returncode == 1
    assert "revision" in json.loads(r.stderr)["error"]


def test_timelike_lists_tools_on_path_sorted(good: Path, scratch: Path) -> None:
    r = run(["timelike", "--json"], env_for(scratch, [good]))
    doc = json.loads(r.stdout)
    assert r.returncode == 0
    assert doc["tools"] == ["timelike", "timelike-conform"]
    assert doc["contract"] == 1
    assert doc["revision"] == REVISION
    assert events(scratch)[-1]["tool"] == "timelike"
