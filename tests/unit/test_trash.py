"""The trash (feature 005 slice 1, T026; spec FR-39 to FR-41; contracts/recover-cli.md § `undo --trash`).

Fed here through `guard trash-put`, the entry point every guard design uses; what calls it in the agent's
shell is FOR-MENTOR Item 22's. The deleting command is the real `rm` (cross-stack P005), and what is put
back is compared by the test's own walk (P004).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from conftest import REPO
from test_snapshot import Lab, doc_of, tree, undo, write
from test_snapshot import lab as lab  # the fixture

GUARD = REPO / "tools" / "libexec" / "guard"


def guard_rm(lab: Lab, *paths: str, cwd: Path | None = None, **env: str) -> subprocess.CompletedProcess[str]:
    """What a guarded `rm -rf PATH...` does: keep them in the trash, then the real rm deletes them."""
    g = subprocess.run(
        [sys.executable, str(GUARD), "trash-put", "--command", "rm -rf " + " ".join(paths), "--", *paths],
        cwd=str(cwd or lab.ws), env=lab.env(**env), stdin=subprocess.DEVNULL,
        capture_output=True, text=True, timeout=30,
    )
    subprocess.run(["rm", "-rf", "--", *paths], cwd=str(cwd or lab.ws), check=True)
    return g


def test_deleted_files_are_kept_and_put_back_verified(lab: Lab) -> None:
    write(lab.ws / "build" / "a.txt", "a\n", 0o640)
    write(lab.ws / "build" / "deep" / "b.bin", os.urandom(300))
    os.symlink("a.txt", lab.ws / "build" / "link")
    write(lab.ws / "notes.txt", "n\n")
    before = tree(lab.ws)
    g = guard_rm(lab, "build", "notes.txt")
    assert g.returncode == 0, g.stderr
    assert g.stderr.startswith("timelike: trash item 1 keeps 3 files (")
    assert g.stderr.rstrip().endswith("undo --trash 1 --yes puts them back")
    assert not (lab.ws / "build").exists() and not (lab.ws / "notes.txt").exists()

    listed = doc_of(undo(lab, "--trash", "--json"))
    assert listed["verdict"] == "1 items in the trash"
    assert listed["lines"] == [f"1  3 files  304 B  {lab.ws / 'build'} and 1 more"]
    item = json.loads((lab.state / "trash" / "items" / "1.json").read_text())
    assert item["command"] == ["rm", "-rf", "build", "notes.txt"] and item["session"]

    dry = doc_of(undo(lab, "--trash", "1", "--dry-run", "--json"))
    assert dry["verdict"] == "dry run: trash item 1 — 6 to put back; nothing changed"
    assert not (lab.ws / "build").exists()

    r = undo(lab, "--trash", "1", "--json")
    assert r.returncode == 4  # rule 9: the envelope first
    r = undo(lab, "--trash", "1", "--yes", "--json")
    assert r.returncode == 0, r.stdout
    assert doc_of(r)["verdict"] == "put back trash item 1: 6 paths; verified"
    assert tree(lab.ws) == before  # content, modes and the link, by the test's own walk


def test_a_put_back_never_overwrites(lab: Lab) -> None:
    write(lab.ws / "f.txt", "old\n")
    guard_rm(lab, "f.txt")
    write(lab.ws / "f.txt", "new\n")
    dry = doc_of(undo(lab, "--trash", "1", "--dry-run", "--json"))
    assert dry["verdict"].endswith("; 1 blocked") and f"refused: {lab.ws / 'f.txt'} exists" in dry["lines"]
    r = undo(lab, "--trash", "1", "--yes", "--json")
    assert r.returncode == 1
    assert doc_of(r)["verdict"].startswith("refused: trash item 1 would overwrite or has no place:")
    assert (lab.ws / "f.txt").read_text() == "new\n"


def test_an_unknown_item_is_exit_3(lab: Lab) -> None:
    r = undo(lab, "--trash", "9", "--dry-run", "--json")
    assert r.returncode == 3
    assert doc_of(r)["verdict"] == "no trash item 9"


def test_the_trash_is_purged_by_size_and_age_naming_what_it_dropped(lab: Lab) -> None:
    for i in range(3):
        write(lab.ws / f"f{i}.bin", os.urandom(1000))
        assert guard_rm(lab, f"f{i}.bin", TIMELIKE_TRASH_MAX_BYTES="2500").returncode == 0
    g = guard_rm(lab, "missing-is-fine")  # nothing to keep: no item, no line
    assert g.stderr == ""
    items = sorted(p.stem for p in (lab.state / "trash" / "items").glob("*.json"))
    assert items == ["2", "3"]  # 1 was dropped when 3 was written

    write(lab.ws / "g.bin", os.urandom(10))
    p2 = lab.state / "trash" / "items" / "2.json"
    t = p2.stat().st_mtime - 40 * 86400
    os.utime(p2, (t, t))
    g = guard_rm(lab, "g.bin")
    assert "timelike: purged: trash item 2 (older than 30 days)" in g.stderr.splitlines()
    objs = [p for p in (lab.state / "trash" / "objects").rglob("*") if p.is_file()]
    assert len(objs) == 2  # 3's and 4's content; 1's and 2's are gone


def test_a_file_over_the_cap_is_named_not_kept(lab: Lab) -> None:
    write(lab.ws / "big.bin", os.urandom(5000))
    g = guard_rm(lab, "big.bin", TIMELIKE_TRASH_MAX_BYTES="1000")
    assert f"timelike: not kept: {lab.ws / 'big.bin'} (over TIMELIKE_TRASH_MAX_BYTES)" in g.stderr.splitlines()
