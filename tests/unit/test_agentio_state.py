"""agentio's state root (feature 005 slice 1, T020; spec FR-25 to FR-28; data-model § State root).

The state root is read from TIMELIKE_STATE_ROOT by agentio, never from PATH or the workspace (P002), and
carries a layout version (P003). Persistence is a fact about the filesystem, compared here with the test's
own stat of `/`, never with what agentio says.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

import agentio
import pytest


def test_state_root_default_and_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("TIMELIKE_STATE_ROOT", raising=False)
    assert agentio.state_root() == Path("/var/lib/timelike")
    monkeypatch.setenv("TIMELIKE_STATE_ROOT", str(tmp_path / "s"))
    assert agentio.state_root() == tmp_path / "s"
    monkeypatch.setenv("TIMELIKE_STATE_ROOT", "")
    assert agentio.state_root() == Path("/var/lib/timelike")


def test_ensure_creates_private_root_with_layout_version(tmp_path: Path) -> None:
    root = tmp_path / "a" / "state"
    assert agentio.ensure_state_root(root) == root
    assert stat.S_IMODE(root.stat().st_mode) == 0o700
    assert (root / "VERSION").read_text() == "timelike-state 1\n"
    agentio.ensure_state_root(root)  # idempotent
    assert sorted(p.name for p in root.iterdir()) == ["VERSION"]


def test_ensure_refuses_another_layout(tmp_path: Path) -> None:
    root = tmp_path / "state"
    root.mkdir()
    (root / "VERSION").write_text("timelike-state 2\n")
    with pytest.raises(agentio.ToolError) as e:
        agentio.ensure_state_root(root)
    assert e.value.code == agentio.EXIT_FAILURE
    assert "timelike-state 2" in e.value.what and str(root) in e.value.what


@pytest.mark.skipif(os.geteuid() == 0, reason="root writes through any mode")
def test_ensure_names_the_path_and_variable_when_unwritable(tmp_path: Path) -> None:
    parent = tmp_path / "ro"
    parent.mkdir()
    parent.chmod(0o500)
    try:
        with pytest.raises(agentio.ToolError) as e:
            agentio.ensure_state_root(parent / "state")
    finally:
        parent.chmod(0o700)
    assert "TIMELIKE_STATE_ROOT" in e.value.what and str(parent / "state") in e.value.what
    assert "TIMELIKE_STATE_ROOT" in e.value.remediation


def test_persistence_is_the_filesystem_comparison(tmp_path: Path) -> None:
    expected = os.stat(tmp_path).st_dev != os.stat("/").st_dev
    assert agentio.state_persistent(tmp_path) is expected
    assert agentio.state_persistent(Path("/")) is False
    assert agentio.state_persistent(tmp_path / "missing") is False  # unknown is never "persistent"


def test_not_persistent_line_names_root_and_remedy() -> None:
    line = agentio.not_persistent_line(Path("/var/lib/timelike"))
    assert line.startswith("not persistent: /var/lib/timelike is on the container's own filesystem")
    assert "mount a volume at /var/lib/timelike" in line and "timelike-state" in line
