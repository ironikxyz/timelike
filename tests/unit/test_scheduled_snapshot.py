"""tools/libexec/scheduled-snapshot (feature 005 slice 1, T024; spec FR-33, FR-34; contracts § The scheduled snapshot).

Run as the hook runs it: a subprocess, given the workspace, with the lab's environment. The store and the
stamp are read by the test itself (P004). The hook's own due check is tests/host/test_shell_env_hook.sh K.
"""

from __future__ import annotations

import fcntl
import json
import subprocess
import sys
import time
from pathlib import Path

from conftest import REPO
from test_snapshot import Lab, make_repo, snap, tree, undo, write
from test_snapshot import lab as lab  # the fixture

HELPER = REPO / "tools" / "libexec" / "scheduled-snapshot"


def run_helper(lab: Lab, ws: Path | None = None, **env: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HELPER), str(ws or lab.ws)],
        cwd=str(lab.tmp), env=lab.env(**env), stdin=subprocess.DEVNULL,
        capture_output=True, text=True, timeout=30,
    )


def stamp(lab: Lab, ws: Path | None = None) -> Path:
    name = str(ws or lab.ws).replace("%", "%25").replace("/", "%2F")
    return lab.state / "stamps" / name


def records(lab: Lab) -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted((lab.store() / "snaps").glob("*.json"))]


def test_a_complete_scheduled_snapshot_is_silent_stamped_and_restorable(lab: Lab) -> None:
    make_repo(lab.ws, lab.home)
    before = time.time()
    r = run_helper(lab)
    assert (r.returncode, r.stdout, r.stderr) == (0, "", "")
    assert int(stamp(lab).read_text()) >= int(before)
    [rec] = records(lab)
    assert rec["reason"] == "scheduled" and rec["partial"] is False

    # a script removes a directory (no guard sees it): the scheduled snapshot brings it back (criterion 2)
    src = tree(lab.ws / "src")
    subprocess.run([sys.executable, "-c", "import shutil; shutil.rmtree('src')"], cwd=lab.ws, check=True)
    assert not (lab.ws / "src").exists()
    u = undo(lab, str(rec["id"]), "--yes", "--json")
    assert u.returncode == 0, u.stdout
    assert tree(lab.ws / "src") == src  # compared by the test (P004)


def test_a_partial_scheduled_snapshot_says_so_in_one_stderr_line(lab: Lab) -> None:
    write(lab.ws / "small.txt", "s\n")
    write(lab.ws / "big.bin", b"x" * 5000)
    r = run_helper(lab, TIMELIKE_SNAPSHOT_MAX_FILE_BYTES="1000")
    assert r.returncode == 0 and r.stdout == ""
    assert r.stderr == (
        f"timelike: scheduled snapshot 1 of {lab.ws} is partial: excluded 1 files"
        " (snapshot list; undo 1 --dry-run)\n"
    )


def test_a_refused_scheduled_snapshot_says_why_and_is_still_stamped(lab: Lab) -> None:
    for i in range(5):
        write(lab.ws / f"f{i}.txt", "x\n")
    r = run_helper(lab, TIMELIKE_SNAPSHOT_MAX_ENTRIES="2")
    assert r.returncode == 0 and r.stdout == ""
    assert r.stderr.startswith(f"timelike: scheduled snapshot of {lab.ws} refused: {lab.ws} has more than 2 entries")
    assert stamp(lab).is_file()  # retried per interval, never per shell
    assert not (lab.store() / "snaps").exists() or records(lab) == []


def test_a_busy_workspace_is_skipped_silently(lab: Lab) -> None:
    write(lab.ws / "f.txt", "x\n")
    assert snap(lab, "--json").returncode == 0
    with (lab.store() / "lock").open("a") as held:
        fcntl.flock(held.fileno(), fcntl.LOCK_EX)
        t0 = time.monotonic()
        r = run_helper(lab)
        waited = time.monotonic() - t0
    assert (r.returncode, r.stdout, r.stderr) == (0, "", "")
    assert waited < 5  # at most 1 s for the lock, plus the interpreter
    assert [x["reason"] for x in records(lab)] == ["on demand"]


def test_a_bad_interval_is_named(lab: Lab) -> None:
    write(lab.ws / "f.txt", "x\n")
    r = run_helper(lab, TIMELIKE_SNAPSHOT_INTERVAL="soon")
    assert r.stderr.startswith("timelike: TIMELIKE_SNAPSHOT_INTERVAL='soon' is not a number of seconds or 'off'")
    assert [x["reason"] for x in records(lab)] == ["scheduled"]
