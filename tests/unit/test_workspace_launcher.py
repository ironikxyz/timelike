"""scripts/workspace.sh (feature 13 slice 0; 014 research R9; FOR-MENTOR Item 27 Q2): the launch's workspace
and the host-git boundary, against a real git (the host's own, which the boundary is about; never a reading of
the agent's config back, cross-stack P004).

- enforced (the default) refuses a workspace inside a git work tree, so the agent's repositories are never the
  operator's checkout; lifted permits it and says what that means;
- a new workspace is a directory per launch under the parent, setgid and group-writable, and the output is
  what compose reads (TIMELIKE_WORKSPACE, TIMELIKE_HOST_GIT, TIMELIKE_WORKSPACE_GID);
- no parent is a refusal naming the variable; local.env is read, and the environment wins over it.
The script is copied into a scratch tree so that its local.env is the test's, never the repository's.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest
from conftest import REPO

SCRIPT = REPO / "scripts" / "workspace.sh"


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    t = tmp_path / "repo"
    (t / "scripts").mkdir(parents=True)
    shutil.copy(SCRIPT, t / "scripts" / "workspace.sh")
    return t


def launch(tree: Path, mode: str = "env", **env: str) -> subprocess.CompletedProcess[str]:
    base = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(tree.parent), "LC_ALL": "C.UTF-8"}
    return subprocess.run(
        ["bash", str(tree / "scripts" / "workspace.sh"), mode],
        env={**base, **env},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def values(out: str) -> dict[str, str]:
    return dict(line.split("=", 1) for line in out.splitlines())


def git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, timeout=30)


@pytest.fixture
def parent(tmp_path: Path) -> Path:
    p = tmp_path / "workspaces"
    p.mkdir()
    os.chmod(p, 0o2775)  # noqa: S103 — the parent's mode Item 27 Q6 asks the operator for
    return p


def test_a_new_workspace_per_launch_under_the_parent(tree: Path, parent: Path) -> None:
    a = launch(tree, TIMELIKE_WORKSPACES=str(parent))
    b = launch(tree, TIMELIKE_WORKSPACES=str(parent))
    assert a.returncode == 0 and b.returncode == 0, a.stderr
    va, vb = values(a.stdout), values(b.stdout)
    assert va["TIMELIKE_WORKSPACE"] != vb["TIMELIKE_WORKSPACE"]
    ws = Path(va["TIMELIKE_WORKSPACE"])
    assert ws.parent == parent.resolve() and ws.is_dir()
    assert stat.S_IMODE(ws.stat().st_mode) & 0o2070 == 0o2070, oct(ws.stat().st_mode)
    assert va["TIMELIKE_HOST_GIT"] == "enforced" and va["TIMELIKE_WORKSPACE_GID"] == str(parent.stat().st_gid)
    assert f"workspace: {ws} (host git enforced)" in a.stderr


def test_check_creates_nothing(tree: Path, parent: Path) -> None:
    r = launch(tree, "check", TIMELIKE_WORKSPACES=str(parent))
    assert r.returncode == 0 and list(parent.iterdir()) == []


def test_enforced_refuses_a_workspace_inside_a_git_work_tree(
    tree: Path, parent: Path, tmp_path: Path
) -> None:
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    git("init", "-q", ".", cwd=checkout)
    r = launch(tree, TIMELIKE_WORKSPACES=str(parent), TIMELIKE_WORKSPACE=str(checkout))
    assert r.returncode == 2 and r.stdout == ""
    assert "is inside a git work tree, and the host-git boundary is enforced (code 2)" in r.stderr
    assert "TIMELIKE_HOST_GIT=lifted" in r.stderr
    sub = checkout / "deep"
    sub.mkdir()
    assert launch(tree, TIMELIKE_WORKSPACES=str(parent), TIMELIKE_WORKSPACE=str(sub)).returncode == 2


def test_enforced_refuses_a_parent_inside_a_git_work_tree(tree: Path, tmp_path: Path) -> None:
    checkout = tmp_path / "checkout"
    (checkout / "ws").mkdir(parents=True)
    git("init", "-q", ".", cwd=checkout)
    r = launch(tree, TIMELIKE_WORKSPACES=str(checkout / "ws"))
    assert r.returncode == 2 and "inside a git work tree" in r.stderr
    assert list((checkout / "ws").iterdir()) == []


def test_lifted_permits_it_and_says_what_that_means(tree: Path, parent: Path, tmp_path: Path) -> None:
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    git("init", "-q", ".", cwd=checkout)
    r = launch(
        tree, TIMELIKE_WORKSPACES=str(parent), TIMELIKE_WORKSPACE=str(checkout), TIMELIKE_HOST_GIT="lifted"
    )
    assert r.returncode == 0, r.stderr
    assert values(r.stdout)["TIMELIKE_HOST_GIT"] == "lifted"
    assert "the operator's git there runs the agent's hooks and executing config" in r.stderr


def test_no_parent_is_a_refusal_naming_the_variable(tree: Path) -> None:
    r = launch(tree)
    assert (
        r.returncode == 2
        and "TIMELIKE_WORKSPACES is not set (code 2)" in r.stderr
        and "local.env" in r.stderr
    )


@pytest.mark.parametrize("bad", ["relative/path", "/no/such/parent"])
def test_a_bad_parent_is_refused(tree: Path, bad: str) -> None:
    assert launch(tree, TIMELIKE_WORKSPACES=bad).returncode == 2


def test_an_unknown_setting_is_refused(tree: Path, parent: Path) -> None:
    r = launch(tree, TIMELIKE_WORKSPACES=str(parent), TIMELIKE_HOST_GIT="off")
    assert r.returncode == 2 and "enforced (the default) or lifted" in r.stderr


def test_local_env_is_read_and_the_environment_wins(tree: Path, parent: Path, tmp_path: Path) -> None:
    other = tmp_path / "other"
    other.mkdir()
    (tree / "local.env").write_text(f"TIMELIKE_WORKSPACES={parent}\nTIMELIKE_HOST_GIT=lifted\n")
    r = launch(tree, "check")
    assert r.returncode == 0 and values(r.stdout)["TIMELIKE_HOST_GIT"] == "lifted"
    assert Path(values(r.stdout)["TIMELIKE_WORKSPACE"]).parent == parent.resolve()
    r = launch(tree, "check", TIMELIKE_WORKSPACES=str(other), TIMELIKE_HOST_GIT="enforced")
    assert Path(values(r.stdout)["TIMELIKE_WORKSPACE"]).parent == other.resolve()
    assert values(r.stdout)["TIMELIKE_HOST_GIT"] == "enforced"


def test_a_path_with_a_space_survives_eval(tree: Path, tmp_path: Path) -> None:
    p = tmp_path / "with space"
    p.mkdir()
    out = launch(tree, "check", TIMELIKE_WORKSPACES=str(p)).stdout
    r = subprocess.run(
        ["bash", "-c", 'eval "$1"; printf "%s" "$TIMELIKE_WORKSPACE"', "x", out],
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )
    assert Path(r.stdout).parent == p.resolve()
