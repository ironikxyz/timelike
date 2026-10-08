"""The README's command reference is generated from the installed tools' own --help, and stays so
(maintenance: README, bridge/sends/maint-readme-20261008-060811.md § 2.4).

The reference test fails when an installed tool is missing from the README's reference, or when its
section differs from what `scripts/readme_reference.py` produces now: a tool change that moves a flag
fails here until the README is regenerated (`python3 scripts/readme_reference.py --write`).

The controls show the test can fail: a section removed, a flag line changed, a tool that is not
installed, and a README without the block are each reported.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO = Path(__file__).resolve().parents[2]


def _load() -> ModuleType:
    path = REPO / "scripts" / "readme_reference.py"
    spec = importlib.util.spec_from_file_location("readme_reference", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rr = _load()


@pytest.fixture(scope="module")
def ref() -> str:
    return str(rr.reference())


@pytest.fixture(scope="module")
def readme() -> str:
    return (REPO / "README.md").read_text(encoding="utf-8")


def test_reference_is_current(readme: str, ref: str) -> None:
    assert rr.differences(readme, ref) == []


def test_every_installed_tool_has_a_section(readme: str) -> None:
    tools = rr.installed_tools()
    assert tools, "no tools found in tools/bin"
    assert sorted(rr.sections_of(rr.split(readme)[1])) == tools


def test_installed_tools_are_tools_bin_executables() -> None:
    tools = rr.installed_tools()
    assert "timelike" in tools and "run" in tools
    assert "__pycache__" not in tools
    assert all((REPO / "tools" / "bin" / t).is_file() for t in tools)


def test_each_section_is_the_tools_own_help(ref: str) -> None:
    secs = rr.sections_of(ref)
    for name, sec in secs.items():
        assert sec.startswith(f"### `{name}`\n\n```text\n{name}: ")
        assert "\nusage:\n" in sec and "\noptions:\n" in sec and "\nexit codes: " in sec
        assert "…[cut" not in sec, f"{name}: a line was cut; the generator's COLUMNS is too small"


@pytest.mark.parametrize("name", rr.installed_tools())
def test_control_a_removed_section_fails(readme: str, ref: str, name: str) -> None:
    sec = rr.sections_of(rr.split(readme)[1])[name]
    broken = readme.replace(sec + "\n", "", 1) if sec + "\n" in readme else readme.replace(sec, "", 1)
    assert broken != readme
    assert f"{name}: missing from the README's reference" in rr.differences(broken, ref)


def test_control_a_changed_flag_line_fails(readme: str, ref: str) -> None:
    name = rr.installed_tools()[0]
    sec = rr.sections_of(rr.split(readme)[1])[name]
    line = next(x for x in sec.splitlines() if x.startswith("  --help"))
    broken = readme.replace(sec, sec.replace(line, line + " (stale)", 1), 1)
    assert f"{name}: differs from `{name} --help`" in rr.differences(broken, ref)


def test_control_a_tool_not_installed_fails(readme: str, ref: str) -> None:
    extra = "### `gone`\n\n```text\ngone: x [help]\n```\n\n"
    before, block, after = rr.split(readme)
    broken = before + block.replace("### `", extra + "### `", 1) + after
    assert "gone: in the reference but not installed" in rr.differences(broken, ref)


def test_control_no_block_is_refused(ref: str) -> None:
    with pytest.raises(SystemExit, match="exactly one block"):
        rr.differences("# a README with no reference\n", ref)


def test_check_command_passes_on_the_readme() -> None:
    r = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "readme_reference.py"), "--check"],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
        stdin=subprocess.DEVNULL,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.startswith("readme reference: current")
