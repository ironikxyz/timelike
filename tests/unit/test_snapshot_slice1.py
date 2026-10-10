"""snapshot and undo, slice 1 (feature 005 Cycle 3; spec FR-25 to FR-41; contracts/recover-cli.md § Slice 1).

The same lab as slice 0's tests (test_snapshot.py), whose helpers this file imports. State is judged by
the test walking the tree and the store itself, never by the tool's message (P004).
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from test_snapshot import (
    SESSION,
    Lab,
    doc_of,
    make_repo,
    snap,
    take,
    text_of,
    tree,
    undo,
    write,
)
from test_snapshot import lab as lab  # the fixture, re-exported as test_undo.py does

NOT_PERSISTENT = "not persistent: "


# ── FR-23 as amended, FR-25: the store lives in the state root ───────────────────────────────


def test_the_store_is_in_the_state_root_not_the_session_scratch(lab: Lab) -> None:
    write(lab.ws / "f.txt", "x\n")
    d = take(lab)
    assert d["store"] == str(lab.store())
    assert str(lab.store()).startswith(str(lab.state / "workspaces") + "/")
    assert (lab.state / "VERSION").read_text() == "timelike-state 1\n"
    assert (lab.store() / "snaps" / "1.json").is_file()
    assert not (lab.scratch / SESSION / "snapshots").exists()


# ── FR-27: persistence is stated, never implied ──────────────────────────────────────────────


def test_not_persistent_line_follows_the_filesystem_the_test_measures(lab: Lab) -> None:
    write(lab.ws / "f.txt", "x\n")
    take(lab)
    persistent = os.stat(lab.state).st_dev != os.stat("/").st_dev
    for args in (["--json"], ["--json", "list"]):
        r = snap(lab, *args)
        raw = json.loads(r.stdout)
        assert raw["state"] == {"root": str(lab.state), "persistent": persistent}
        lines = [x for x in raw["lines"] if x.startswith(NOT_PERSISTENT)]
        assert len(lines) == (0 if persistent else 1), raw["lines"]
        if lines:
            assert lines[0].startswith(f"not persistent: {lab.state} is not a mounted volume")
    t = undo(lab, "--text", "--dry-run")
    assert any(x.startswith(NOT_PERSISTENT) for x in t.stdout.splitlines()) is (not persistent)


def test_a_refusal_carries_the_line_after_its_remedy(lab: Lab) -> None:
    r = snap(lab, "--json", cwd=lab.home)
    raw = json.loads(r.stdout)
    assert raw["lines"][0].startswith("do instead: ")
    if os.stat(lab.tmp).st_dev == os.stat("/").st_dev:
        assert raw["lines"][1].startswith(NOT_PERSISTENT), raw["lines"]


# ── FR-31: attribution; one store for every session (revision 11) ───────────────────────────


def test_two_sessions_share_one_store_and_each_record_names_who_took_it(lab: Lab) -> None:
    write(lab.ws / "f.txt", "one\n")
    take(lab, TIMELIKE_SESSION="s1", TIMELIKE_AGENT="agent-a")
    write(lab.ws / "f.txt", "two\n")
    take(lab, TIMELIKE_SESSION="s2", TIMELIKE_AGENT="agent-b")
    take(lab, TIMELIKE_SESSION="s3", TIMELIKE_AGENT="not valid!")

    d = doc_of(snap(lab, "--json", "list", TIMELIKE_SESSION="s9"))
    who = [(s["id"], s["session"], s["agent"]) for s in d["snapshots"]]
    assert who == [(3, "s3", None), (2, "s2", "agent-b"), (1, "s1", "agent-a")]
    rec = json.loads((lab.store() / "snaps" / "1.json").read_text())
    assert (rec["session"], rec["agent"]) == ("s1", "agent-a")

    v = [x for x in text_of(snap(lab, "--text", "list", "--verbose")) if x[:1].isdigit()]
    assert v[1].endswith("session s2  agent agent-b") and v[0].endswith("session s3  agent -"), v

    # A new session restores another session's snapshot (criterion 3, first half, on the host).
    write(lab.ws / "f.txt", "three\n")
    r = undo(lab, "1", "--yes", "--json", TIMELIKE_SESSION="s-new")
    assert r.returncode == 0, r.stdout
    assert (lab.ws / "f.txt").read_text() == "one\n"


# ── FR-29: a workspace moved elsewhere is told where its history is ──────────────────────────


def test_a_moved_workspace_sees_none_and_is_told_where_snapshots_are(lab: Lab) -> None:
    make_repo(lab.ws, lab.home)
    take(lab)
    take(lab)
    moved = lab.tmp / "moved"
    shutil.copytree(lab.ws, moved, symlinks=True)

    d = doc_of(snap(lab, "--json", "list", cwd=moved))
    assert d["verdict"] == "0 snapshots"
    real = os.path.realpath(lab.ws)
    assert d["lines"] == [f"other workspace with snapshots: {real} (2)"]
    assert d["other_workspaces"] == [{"workspace": real, "snapshots": 2}]

    r = undo(lab, "--json", "--dry-run", cwd=moved)
    assert r.returncode == 3
    u = doc_of(r)
    assert u["lines"] == ["do instead: take one with: snapshot", f"other workspace with snapshots: {real} (2)"]


# ── criterion 4 (revision 11): a restore first snapshots the workspace, and can itself be undone ──


def test_a_restore_names_its_safety_snapshot_and_undoing_it_returns_the_replaced_state(lab: Lab) -> None:
    make_repo(lab.ws, lab.home)
    take(lab)
    write(lab.ws / "src" / "app.py", "print('changed')\n")
    write(lab.ws / "new.txt", "new\n")
    replaced = tree(lab.ws)

    r = undo(lab, "--yes", "--json")
    assert r.returncode == 0, r.stdout
    d = doc_of(r)
    s = d["before"]
    assert d["verdict"].endswith(f"verified; the state before is snapshot {s}")
    assert tree(lab.ws) != replaced

    r2 = undo(lab, str(s), "--yes", "--json")
    assert r2.returncode == 0, r2.stdout
    assert tree(lab.ws) == replaced  # compared by the test, never by the message (P004)


# ── FR-30: slice 0's stores in the session scratch are imported once, nothing lost ──────────


def _make_slice0_store(lab: Lab, session: str) -> Path:
    """A slice-0 store has the same layout as a state-root store; move one to the old place."""
    old = lab.scratch / session / "snapshots" / lab.store().name
    old.parent.mkdir(parents=True)
    shutil.move(str(lab.store()), str(old))
    return old


def test_a_slice0_store_is_imported_once_in_order_and_restorable(lab: Lab) -> None:
    write(lab.ws / "f.txt", "first\n")
    take(lab, "-m", "one")
    write(lab.ws / "f.txt", "second\n")
    take(lab)
    old = _make_slice0_store(lab, "old-session")
    write(lab.ws / "f.txt", "now\n")

    r = snap(lab, "--json", "list")
    raw = json.loads(r.stdout)
    assert "imported 2 snapshots from session old-session (were 1–2, now 1–2)" in raw["lines"]
    assert raw["imported"] == [{"session": "old-session", "was": [1, 2], "now": [1, 2]}]
    rows = [(s["id"], s["label"], s["session"]) for s in raw["snapshots"]]
    assert rows == [(2, None, SESSION), (1, "one", SESSION)]  # slice-0 records gain their session
    rec = json.loads((lab.store() / "snaps" / "1.json").read_text())
    assert rec["imported"] == {"session": "old-session", "id": 1}
    assert (old / "imported").read_text() == "1 1\n2 2\n"
    assert (old / "snaps" / "1.json").is_file()  # the old store is left in place

    again = json.loads(snap(lab, "--json", "list").stdout)
    assert not any(x.startswith("imported ") for x in again["lines"])  # once
    assert [s["id"] for s in again["snapshots"]] == [2, 1]

    assert undo(lab, "1", "--yes", "--json").returncode == 0
    assert (lab.ws / "f.txt").read_text() == "first\n"


def test_an_imported_record_follows_the_state_roots_own(lab: Lab) -> None:
    write(lab.ws / "f.txt", "old\n")
    take(lab)
    _make_slice0_store(lab, "s0")
    write(lab.ws / "f.txt", "new\n")
    d = take(lab)  # a take imports first, then takes: the import gets 1, the new snapshot 2
    assert d["id"] == 2 and d["imported"][0]["now"] == [1]


def test_a_damaged_slice0_record_is_named_not_imported(lab: Lab) -> None:
    write(lab.ws / "f.txt", "a\n")
    take(lab)
    write(lab.ws / "g.txt", "b\n")
    take(lab)
    old = _make_slice0_store(lab, "s0")
    objs = sorted(p for p in (old / "objects").rglob("*") if p.is_file())
    rec2 = json.loads((old / "snaps" / "2.json").read_text())
    only2 = {e["sha256"] for e in rec2["entries"] if e["kind"] == "file"} - {
        e["sha256"] for e in json.loads((old / "snaps" / "1.json").read_text())["entries"] if e["kind"] == "file"
    }
    bad = next(p for p in objs if p.name in only2)
    bad.chmod(0o600)
    bad.write_text("damaged\n")

    raw = json.loads(snap(lab, "--json", "list").stdout)
    assert "imported 1 snapshots from session s0 (were 1, now 1)" in raw["lines"], raw["lines"]
    assert any(x.startswith("not imported: s0 snapshot 2: object ") for x in raw["lines"]), raw["lines"]
    assert [s["id"] for s in raw["snapshots"]] == [1]


# ── FR-35: unchanged files are not re-read ──────────────────────────────────────────────────

_AUDIT = """
import os, runpy, sys
ws, log, tool = sys.argv[1], sys.argv[2], sys.argv[3]
seen = []
def hook(event, args):
    if event == "open" and isinstance(args[0], str) and args[0].startswith(ws + "/"):
        seen.append(os.path.relpath(args[0], ws))
sys.addaudithook(hook)
sys.argv = [tool, "--json"]
try:
    runpy.run_path(tool, run_name="__main__")
finally:
    open(log, "w").write("\\n".join(sorted(set(seen))))
"""


def _take_counting_opens(lab: Lab) -> list[str]:
    """Run a take with an audit hook recording every workspace file the tool opens (by name)."""
    import subprocess
    import sys

    from test_snapshot import SNAPSHOT

    log = lab.tmp / "opens.txt"
    real = os.path.realpath(lab.ws)
    r = subprocess.run(
        [sys.executable, "-c", _AUDIT, real, str(log), str(SNAPSHOT)],
        cwd=lab.ws, env=lab.env(), capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL,
    )
    assert r.returncode == 0, (r.stdout, r.stderr)
    return [x for x in log.read_text().splitlines() if x]


def test_an_unchanged_file_is_not_reread_and_a_changed_one_is(lab: Lab) -> None:
    write(lab.ws / "a.txt", "alpha\n")
    write(lab.ws / "sub" / "b.txt", "beta\n")
    assert sorted(_take_counting_opens(lab)) == ["a.txt", "sub/b.txt"]  # the first take reads both
    assert _take_counting_opens(lab) == []  # nothing changed: nothing read (FR-35)

    write(lab.ws / "a.txt", "ALPHA\n")  # same size, new content
    assert _take_counting_opens(lab) == ["a.txt"]
    write(lab.ws / "a.txt", "changed again\n")
    assert undo(lab, "3", "--yes", "--json").returncode == 0
    assert (lab.ws / "a.txt").read_text() == "ALPHA\n"  # the re-read content is what was captured


def test_a_cached_file_whose_object_is_gone_is_read_again(lab: Lab) -> None:
    write(lab.ws / "a.txt", "alpha\n")
    take(lab)
    rec = json.loads((lab.store() / "snaps" / "1.json").read_text())
    sha = next(e["sha256"] for e in rec["entries"] if e["path"] == "a.txt")
    obj = lab.store() / "objects" / sha[:2] / sha
    obj.chmod(0o600)
    obj.unlink()
    assert _take_counting_opens(lab) == ["a.txt"]
    assert obj.is_file()
