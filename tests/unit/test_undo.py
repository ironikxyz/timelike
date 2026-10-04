"""undo (feature 005, slice 0, T008) against contracts/recover-cli.md, spec FR-14 to FR-21 and data-model.md.

Written from the contract alone, before the tool. Every restore is checked by the test walking the
workspace and every `.git` itself and comparing with what it recorded before (P004): the tool's verdict
is asserted as well, never instead. Helpers come from test_snapshot.py.
"""

from __future__ import annotations

import fcntl
import hashlib
import importlib.machinery
import importlib.util
import json
import os
import re
import shlex
import subprocess
import time
from pathlib import Path
from typing import Any

import pytest
import schema
from conftest import TOOLS_DIR, events
from test_conform import env_for, install
from test_snapshot import (
    LOCK_VERDICT,
    SESSION,
    Lab,
    check_cut_more,
    doc_of,
    git,
    git_state,
    make_repo,
    outcome,
    outcome_text,
    record,
    snap,
    snapshot_ids,
    stderr_error,
    take,
    text_of,
    tree,
    undo,
    write,
)
from test_snapshot import lab as lab

Row = tuple[str, str, str]  # (change, kind, path)


def load_conform() -> Any:
    loader = importlib.machinery.SourceFileLoader("timelike_conform", str(TOOLS_DIR / "timelike-conform"))
    spec = importlib.util.spec_from_loader("timelike_conform", loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def line_of(row: Row) -> str:
    change, kind, path = row
    return f"{change} {kind} {path}"


def plan_rows(d: dict[str, Any]) -> list[Row]:
    return [(p["change"], p["kind"], p["path"]) for p in d["plan"]]


def dry(lab: Lab, *args: str, **env: str) -> dict[str, Any]:
    r = undo(lab, "--json", "--dry-run", *args, **env)
    assert r.returncode == 0, (r.stdout, r.stderr)
    return doc_of(r)


# ── a workspace that exercises every row of the plan (data-model § Plan) ──────────────────────


def build_every_row(lab: Lab) -> None:
    """Snapshot 1 of a small repository, then one change per plan row."""
    ws, home = lab.ws, lab.home
    git(ws, "init", "-q", home=home)
    write(ws / "a.txt", "a\n")
    write(ws / "b.txt", "b\n")
    write(ws / "m.txt", "m\n", 0o644)
    write(ws / "same.txt", "same\n")
    write(ws / "touched.txt", "touched\n")
    write(ws / "kind.txt", "a file\n")
    write(ws / "d2" / "k.txt", "k\n")
    (ws / "d2").chmod(0o755)
    write(ws / "gone" / "f.txt", "f\n")
    os.symlink("a.txt", ws / "link1")
    os.symlink("a.txt", ws / "link2")
    os.symlink("a.txt", ws / "lnk3")
    take(lab)

    write(ws / "a.txt", "a, edited\n")  # content differs
    (ws / "b.txt").unlink()  # file missing
    (ws / "m.txt").chmod(0o600)  # mode differs
    write(ws / "touched.txt", "touched\n")  # rewritten, same content: no change
    (ws / "kind.txt").unlink()
    write(ws / "kind.txt" / "inner", "now a dir\n")  # kind differs: file -> dir
    (ws / "d2").chmod(0o700)  # dir mode differs
    (ws / "gone" / "f.txt").unlink()
    (ws / "gone").rmdir()  # a directory removed by a script
    (ws / "link1").unlink()  # link missing
    (ws / "link2").unlink()
    os.symlink("b.txt", ws / "link2")  # target differs
    (ws / "lnk3").unlink()
    write(ws / "lnk3", "now a file\n")  # kind differs: link -> file
    write(ws / "notes.txt", "new\n")  # new file
    os.symlink("a.txt", ws / "newlink")  # new link
    write(ws / "newdir" / "n.txt", "n\n")  # new dir with a file
    (ws / "newrepo").mkdir()
    git(ws / "newrepo", "init", "-q", home=home)  # a .git planted after the snapshot
    write(ws / "newrepo" / "f.txt", "f\n")


EVERY_ROW: list[Row] = [
    ("restore", "file", "a.txt"),
    ("restore", "file", "b.txt"),
    ("restore", "dir", "d2"),
    ("restore", "dir", "gone"),
    ("restore", "file", "gone/f.txt"),
    ("remove", "dir", "kind.txt"),
    ("restore", "file", "kind.txt"),
    ("remove", "file", "kind.txt/inner"),
    ("restore", "link", "link1"),
    ("restore", "link", "link2"),
    ("remove", "file", "lnk3"),
    ("restore", "link", "lnk3"),
    ("restore", "file", "m.txt"),
    ("remove", "dir", "newdir"),
    ("remove", "file", "newdir/n.txt"),
    ("remove", "link", "newlink"),
    ("keep", "dir", "newrepo"),
    ("remove", "file", "newrepo/f.txt"),
    ("remove", "file", "notes.txt"),
]
RESTORES = sum(1 for c, _, _ in EVERY_ROW if c == "restore")  # 10
REMOVES = sum(1 for c, _, _ in EVERY_ROW if c == "remove")  # 8


def assert_every_row_lines(lines: list[str]) -> None:
    assert len(lines) == len(EVERY_ROW), lines
    for got, row in zip(lines, EVERY_ROW, strict=True):
        if row[0] == "keep":
            assert got.startswith("keep dir newrepo (holds ") and ".git" in got and got.endswith(")"), got
        else:
            assert got == line_of(row), (got, row)


# ── FR-14: which snapshot ─────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("args", [("--dry-run",), ("--yes",), ()])
def test_no_snapshots_is_exit_3_saying_how_to_take_one(lab: Lab, args: tuple[str, ...]) -> None:
    write(lab.ws / "f.txt", "x\n")
    before = tree(lab.ws)
    ws = os.path.realpath(lab.ws)
    d = outcome(undo(lab, "--json", *args), 3, "restore newest")
    assert d["target"] == ws
    assert (d["verdict"], d["remedy"]) == (f"no snapshot for {ws}", "take one with: snapshot")
    out = outcome_text(undo(lab, "--text", *args), 3, f"undo: {ws} [restore newest]")
    assert out[1:3] == [f"verdict: no snapshot for {ws}", "do instead: take one with: snapshot"]
    assert tree(lab.ws) == before


def test_unknown_id_is_exit_3_naming_the_snapshots_newest_first(lab: Lab) -> None:
    write(lab.ws / "f.txt", "x\n")
    take(lab)
    take(lab)
    d = outcome(undo(lab, "--json", "7", "--dry-run"), 3, "restore 7")
    assert d["verdict"] == f"no snapshot 7 for {os.path.realpath(lab.ws)}"
    assert re.match(r"^snapshots here: 2\D+1$", d["remedy"]), d["remedy"]  # newest first
    outcome(undo(lab, "--json", "7", "--yes"), 3, "restore 7")
    assert snapshot_ids(lab) == [2, 1]  # an unknown id took no safety snapshot


def test_default_is_the_newest_snapshot(lab: Lab) -> None:
    write(lab.ws / "f.txt", "one\n")
    take(lab)
    write(lab.ws / "f.txt", "two\n")
    take(lab)
    write(lab.ws / "f.txt", "three\n")
    d = dry(lab)
    assert (d["id"], d["scope"]) == (2, "restore 2")
    assert plan_rows(d) == [("restore", "file", "f.txt")]
    d1 = dry(lab, "1")
    assert (d1["id"], d1["scope"]) == (1, "restore 1")


def test_a_repeated_undo_yes_changes_nothing_the_default_skips_safety_snapshots(lab: Lab) -> None:
    """Rule 7: the default is the newest snapshot that is not a safety snapshot (FR-14, amended)."""
    write(lab.ws / "f.txt", "one\n")
    take(lab)
    write(lab.ws / "f.txt", "two\n")
    first = undo(lab, "--json", "--yes")
    assert first.returncode == 0, (first.stdout, first.stderr)
    assert (doc_of(first)["id"], doc_of(first)["before"]) == (1, 2)
    after_first = tree(lab.ws)
    second = undo(lab, "--json", "--yes")
    assert second.returncode == 0, (second.stdout, second.stderr)
    d = doc_of(second)
    assert (d["scope"], d["verdict"]) == ("restore 1", "nothing to restore: the workspace matches snapshot 1")
    assert tree(lab.ws) == after_first
    assert snapshot_ids(lab) == [2, 1]  # no further safety snapshot
    back = undo(lab, "--json", "--yes", "2")  # a safety snapshot by id undoes the undo
    assert back.returncode == 0, (back.stdout, back.stderr)
    assert (lab.ws / "f.txt").read_text() == "two\n"


# ── FR-15, FR-16: the plan, every row, and a dry run that changes nothing ─────────────────────


def test_dry_run_lists_every_plan_row_sorted_with_counts_and_changes_nothing(lab: Lab) -> None:
    build_every_row(lab)
    before, git_before = tree(lab.ws), git_state(lab.ws)

    d = dry(lab)
    assert (d["tool"], d["target"], d["scope"]) == ("undo", os.path.realpath(lab.ws), "restore 1")
    assert (d["id"], d["restore"], d["remove"]) == (1, RESTORES, REMOVES)
    assert plan_rows(d) == EVERY_ROW
    assert (
        d["verdict"] == f"dry run: snapshot 1 — {RESTORES} to restore, {REMOVES} to remove; nothing changed"
    )

    t = undo(lab, "--text", "--dry-run", "--limit", "0")
    assert t.returncode == 0
    out = text_of(t)
    assert out[0] == f"undo: {os.path.realpath(lab.ws)} [restore 1]"
    assert out[1] == f"verdict: {d['verdict']}"
    assert_every_row_lines(out[2:])

    assert tree(lab.ws) == before
    assert git_state(lab.ws) == git_before
    assert snapshot_ids(lab) == [1]


def test_an_empty_plan_needs_no_confirmation_and_takes_no_safety_snapshot(lab: Lab) -> None:
    make_repo(lab.ws, lab.home)
    take(lab)
    write(lab.ws / "README.md", "# demo\n")  # rewritten with the same bytes: still no change
    before = tree(lab.ws)

    d = dry(lab)
    assert d["verdict"] == "dry run: snapshot 1 — nothing to change"
    assert (d["restore"], d["remove"], d["plan"]) == (0, 0, [])
    for args in ((), ("--yes",)):
        r = undo(lab, "--json", *args)
        assert r.returncode == 0, (args, r.stdout, r.stderr)
        assert doc_of(r)["verdict"] == "nothing to restore: the workspace matches snapshot 1"
    assert tree(lab.ws) == before
    assert snapshot_ids(lab) == [1]


# ── FR-17: no flag is the confirmation envelope (rule 9) ──────────────────────────────────────


@pytest.mark.parametrize("mode", ["--json", "--text"])
def test_without_yes_exit_4_with_the_confirm_envelope_and_nothing_changes(lab: Lab, mode: str) -> None:
    build_every_row(lab)
    before, git_before = tree(lab.ws), git_state(lab.ws)
    r = undo(lab, mode)
    assert r.returncode == 4
    assert r.stderr == ""
    env = json.loads(r.stdout)  # JSON in every mode
    assert schema.errors(env, schema.load("confirm-envelope.schema.json")) == []
    assert list(env)[:4] == ["tool", "target", "scope", "status"]
    assert (env["tool"], env["target"], env["scope"]) == ("undo", os.path.realpath(lab.ws), "restore 1")
    assert env["status"] == "confirmation_required"
    assert_every_row_lines(env["plan"])  # the dry run's lines
    assert env["confirm"] == shlex.join(["undo", mode, "--yes"])
    c = load_conform()
    assert c.check_envelope("undo", r.stdout, {"confirmation_required"}) == []
    assert c.check_envelope("undo", r.stdout, set()) != []  # the check can fail
    assert tree(lab.ws) == before
    assert git_state(lab.ws) == git_before
    assert snapshot_ids(lab) == [1]  # no safety snapshot either


def test_running_the_envelopes_confirm_is_the_one_undo_command(lab: Lab) -> None:
    write(lab.ws / "src" / "main.py", "main\n")
    take(lab)
    pre = tree(lab.ws)
    for p in sorted((lab.ws / "src").iterdir()):
        p.unlink()
    (lab.ws / "src").rmdir()
    write(lab.ws / "notes.txt", "wrong turn\n")
    r = undo(lab, "1")
    assert r.returncode == 4
    words = shlex.split(json.loads(r.stdout)["confirm"])
    assert words[0] == "undo" and words[-1] == "--yes", words
    done = undo(lab, *words[1:])
    assert done.returncode == 0, (done.stdout, done.stderr)
    assert tree(lab.ws) == pre


def test_the_envelope_plan_is_bounded_with_a_dry_run_for_the_rest(lab: Lab) -> None:
    write(lab.ws / "keep.txt", "x\n")
    take(lab)
    for i in range(30):
        write(lab.ws / f"n{i:02d}.txt", "x\n")
    r = undo(lab, "--json", "--limit", "5")
    assert r.returncode == 4
    plan = json.loads(r.stdout)["plan"]
    shown, last = plan[:-1], plan[-1]
    assert 0 < len(shown) <= 5, plan
    assert all(x.startswith("remove file n") for x in shown), plan
    m = re.match(r"^… and (\d+) more: undo 1 --dry-run --limit 0$", last)
    assert m, last
    assert int(m.group(1)) + len(shown) == 30


# ── FR-18, FR-19: --yes restores, verifies, and keeps the state before as a snapshot ──────────


def test_yes_restores_every_kind_byte_identical_and_names_the_safety_snapshot(lab: Lab) -> None:
    """Scenario 1 and SC-1/SC-2/SC-3: tracked, untracked and ignored files, modes, links, a directory
    removed by a script, a nested project's file; `.git` byte-identical throughout."""
    outside = lab.tmp / "outside"
    write(outside / "theirs.txt", "not ours\n")
    make_repo(lab.ws, lab.home, outside=outside)
    pre, git_pre = tree(lab.ws), git_state(lab.ws)
    take(lab)
    assert git_state(lab.ws) == git_pre

    script = "import shutil, sys; shutil.rmtree(sys.argv[1])"
    subprocess.run(["python3", "-c", script, str(lab.ws / "src")], check=True, timeout=10)  # tracked
    (lab.ws / "notes" / "todo.txt").unlink()  # untracked
    write(lab.ws / "build" / "out.bin", b"rebuilt")  # ignored, content changed
    (lab.ws / "debug.log").unlink()  # ignored, removed
    (lab.ws / "secret.txt").chmod(0o644)
    (lab.ws / "run.sh").chmod(0o644)
    (lab.ws / "readme-link").unlink()
    write(lab.ws / "vendor" / "inner" / "lib.txt", "edited nested\n")
    write(lab.ws / "notes.txt", "a new file\n")
    write(lab.ws / "fresh" / "deep" / "x.txt", "new tree\n")
    changed, git_changed = tree(lab.ws), git_state(lab.ws)
    outside_before = tree(outside)

    d = dry(lab)
    r = undo(lab, "--json", "--yes")
    assert r.returncode == 0, (r.stdout, r.stderr)
    y = doc_of(r)
    assert (y["id"], y["restored"], y["removed"]) == (1, d["restore"], d["remove"])
    assert (y["verified"], y["before"], y["before_partial"]) == (True, 2, False)
    assert y["verdict"] == (
        f"restored to snapshot 1: {d['restore']} restored, {d['remove']} removed; verified;"
        " the state before is snapshot 2"
    )
    assert tree(lab.ws) == pre  # the test's own comparison, not the verdict's
    assert git_state(lab.ws) == git_changed == git_pre
    assert tree(outside) == outside_before

    rec2 = record(lab, 2)
    assert (rec2["reason"], rec2["label"]) == ("before undo 1", None)
    listed = doc_of(snap(lab, "--json", "list"))["snapshots"]
    assert [(s["id"], s["reason"]) for s in listed] == [(2, "before undo 1"), (1, "on demand")]

    # an undo is undoable: back to the state the restore replaced
    back = undo(lab, "--json", "2", "--yes")
    assert back.returncode == 0, (back.stdout, back.stderr)
    assert doc_of(back)["before"] == 3
    assert tree(lab.ws) == changed
    assert git_state(lab.ws) == git_pre
    assert record(lab, 3)["reason"] == "before undo 2"


def test_yes_applies_every_plan_row_and_keeps_a_planted_git(lab: Lab) -> None:
    build_every_row(lab)
    git_before = git_state(lab.ws)
    newrepo_mode = tree(lab.ws)["newrepo"]
    t = undo(lab, "--text", "--yes", "--limit", "0")
    assert t.returncode == 0, (t.stdout, t.stderr)
    out = text_of(t)
    assert out[0] == f"undo: {os.path.realpath(lab.ws)} [restore 1]"
    assert out[1] == (
        f"verdict: restored to snapshot 1: {RESTORES} restored, {REMOVES} removed; verified;"
        " the state before is snapshot 2"
    )
    for row in EVERY_ROW:
        if row[0] != "keep":
            assert line_of(row) in out[2:], (row, out)

    after = tree(lab.ws)
    # the planted repository's directory and its .git stay; its other file went
    assert after.pop("newrepo") == newrepo_mode
    assert git_state(lab.ws) == git_before
    assert (lab.ws / "newrepo" / ".git").is_dir()
    lab_ws_snapshot = record(lab, 1)
    want: dict[str, tuple[Any, ...]] = {}
    for e in lab_ws_snapshot["entries"]:
        if e["kind"] == "file":
            want[e["path"]] = ("file", e["mode"], e["sha256"], e["size"])
        elif e["kind"] == "link":
            want[e["path"]] = ("link", e["target"])
        else:
            want[e["path"]] = ("dir", e["mode"])
    assert after == want
    assert (lab.ws / "kind.txt").read_text() == "a file\n" and os.readlink(lab.ws / "lnk3") == "a.txt"
    assert (lab.ws / "d2").stat().st_mode & 0o7777 == 0o755
    assert (lab.ws / "m.txt").stat().st_mode & 0o7777 == 0o644


def test_dry_run_with_yes_is_a_dry_run(lab: Lab) -> None:
    write(lab.ws / "f.txt", "x\n")
    take(lab)
    write(lab.ws / "notes.txt", "new\n")
    before = tree(lab.ws)
    for args in (("--dry-run", "--yes"), ("--yes", "--dry-run")):
        r = undo(lab, "--json", *args)
        assert r.returncode == 0, (args, r.stderr)
        assert doc_of(r)["verdict"] == "dry run: snapshot 1 — 0 to restore, 1 to remove; nothing changed"
    assert tree(lab.ws) == before
    assert snapshot_ids(lab) == [1]


# ── FR-20: never through a symlink, never into or out of a `.git` ─────────────────────────────


def test_a_symlink_planted_at_a_parent_path_is_replaced_never_written_through(lab: Lab) -> None:
    write(lab.ws / "a" / "f", "inside\n")
    write(lab.ws / "top.txt", "x\n")
    take(lab)
    pre = tree(lab.ws)
    outside = lab.tmp / "outside"
    write(outside / "sentinel.txt", "theirs\n")
    outside_before = tree(outside)
    for p in (lab.ws / "a" / "f", lab.ws / "a"):
        p.unlink() if p.is_file() else p.rmdir()
    os.symlink(str(outside), lab.ws / "a")

    d = dry(lab)
    assert plan_rows(d) == [("remove", "link", "a"), ("restore", "dir", "a"), ("restore", "file", "a/f")]
    r = undo(lab, "--json", "--yes")
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert not (lab.ws / "a").is_symlink() and (lab.ws / "a").is_dir()
    assert (lab.ws / "a" / "f").read_text() == "inside\n"
    assert tree(lab.ws) == pre
    assert tree(outside) == outside_before  # nothing was written where the link pointed


def test_a_git_planted_after_the_snapshot_is_never_removed(lab: Lab) -> None:
    make_repo(lab.ws, lab.home)
    take(lab)
    proj = lab.ws / "later" / "proj"
    proj.mkdir(parents=True)
    git(proj, "init", "-q", home=lab.home)
    write(proj / "work.txt", "x\n")
    git(proj, "add", "-A", home=lab.home)
    git(proj, "commit", "-q", "-m", "later", home=lab.home)
    git_before = git_state(lab.ws)

    d = dry(lab)
    keeps = [p for p in d["plan"] if p["change"] == "keep"]
    assert {(k["kind"], k["path"]) for k in keeps} >= {("dir", "later/proj")}, d["plan"]
    assert ("remove", "file", "later/proj/work.txt") in plan_rows(d)
    assert not any(".git" in p["path"].split("/") for p in d["plan"])
    r = undo(lab, "--json", "--yes")
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert git_state(lab.ws) == git_before
    assert (proj / ".git").is_dir() and not (proj / "work.txt").exists()


# ── FR-6 at restore: excluded files are neither restored nor removed ──────────────────────────


def test_excluded_files_are_left_alone_and_a_partial_safety_snapshot_says_so(lab: Lab) -> None:
    caps = {"TIMELIKE_SNAPSHOT_MAX_FILE_BYTES": "100"}
    write(lab.ws / "big.bin", b"B" * 500)
    write(lab.ws / "src.txt", "source\n")
    d = take(lab, **caps)
    assert [e["path"] for e in d["excluded"]] == ["big.bin"]
    write(lab.ws / "big.bin", b"C" * 600)  # changed since, still excluded by name
    write(lab.ws / "src.txt", "edited\n")
    write(lab.ws / "notes.txt", "new\n")

    plan = dry(lab, **caps)
    assert not any(p["path"] == "big.bin" for p in plan["plan"]), plan["plan"]
    r = undo(lab, "--json", "--yes", **caps)
    assert r.returncode == 0, (r.stdout, r.stderr)
    y = doc_of(r)
    assert y["before_partial"] is True
    assert y["verdict"].endswith(f"the state before is snapshot {y['before']} (partial)"), y["verdict"]
    assert (lab.ws / "big.bin").read_bytes() == b"C" * 600
    assert (lab.ws / "src.txt").read_text() == "source\n"
    assert not (lab.ws / "notes.txt").exists()


def test_a_safety_snapshot_that_fails_verification_stops_the_restore_before_any_change(lab: Lab) -> None:
    """Revision 11, condition 4, on undo's own snapshot (D-10): with the state it would replace not shown
    restorable, the restore never starts. A damaged object is planted for the new file's content."""
    write(lab.ws / "a.txt", "kept\n")
    take(lab)
    write(lab.ws / "new.txt", "made after\n")
    write(lab.ws / "a.txt", "edited\n")
    digest = hashlib.sha256(b"made after\n").hexdigest()
    obj = lab.store() / "objects" / digest[:2] / digest
    write(obj, "made aftex\n")
    before = tree(lab.ws)

    d = outcome(undo(lab, "--json", "--yes"), 1, "restore newest")
    assert d["verdict"].startswith("restore of snapshot 1 not started: the snapshot of the state it would")
    assert "could not be verified restorable" in d["verdict"]
    assert d["remedy"].startswith("nothing was changed; run undo 1 --yes again"), d["remedy"]
    assert tree(lab.ws) == before  # nothing applied
    assert snapshot_ids(lab) == [1] and not obj.exists()
    y = doc_of(undo(lab, "--json", "--yes"))  # the damaged object is gone, so the next attempt succeeds
    assert y["verified"] is True and (lab.ws / "a.txt").read_text() == "kept\n"
    assert not (lab.ws / "new.txt").exists()


# ── refusals and usage ────────────────────────────────────────────────────────────────────────


def test_a_refused_workspace_is_refused_by_undo_too(lab: Lab) -> None:
    write(lab.home / "dotfile", "x\n")
    before = tree(lab.home)
    home = os.path.realpath(lab.home)
    r = undo(lab, "--json", "--yes", cwd=lab.home)
    d = outcome(r, 1, doc_of(r).get("scope", "?"))
    assert d["scope"] in ("restore newest", "take"), d["scope"]  # FLAGGED in the report: not pinned
    assert (d["target"], d["verdict"]) == (home, f"refused: {home} is your home directory")
    assert d["remedy"].startswith("change into the project directory"), d["remedy"]
    assert tree(lab.home) == before


def test_a_non_numeric_id_is_a_usage_error(lab: Lab) -> None:
    write(lab.ws / "f.txt", "x\n")
    take(lab)
    stderr_error(undo(lab, "--text", "newest", "--dry-run"), 2)
    r = undo(lab, "--json", "abc", "--yes")
    assert r.returncode == 2 and r.stdout == ""
    assert json.loads(r.stderr)["code"] == 2
    assert snapshot_ids(lab) == [1]


@pytest.mark.parametrize("var", ["TIMELIKE_SNAPSHOT_MAX_BYTES", "TIMELIKE_SNAPSHOT_MAX_ENTRIES"])
def test_an_invalid_cap_value_is_exit_2_for_undo(lab: Lab, var: str) -> None:
    write(lab.ws / "f.txt", "x\n")
    take(lab)
    write(lab.ws / "notes.txt", "new\n")
    r = undo(lab, "--json", "--yes", **{var: "ten"})
    assert r.returncode == 2 and r.stdout == ""
    err = json.loads(r.stderr)
    assert err["code"] == 2 and var in err["error"] + " " + err["remediation"], err
    assert (lab.ws / "notes.txt").exists()
    assert snapshot_ids(lab) == [1]


# ── FR-24: the lock covers undo --yes ─────────────────────────────────────────────────────────


def test_undo_yes_waits_for_the_lock_then_exits_1_and_changes_nothing(lab: Lab) -> None:
    """Slow by design (the contract's 10 s wait)."""
    write(lab.ws / "f.txt", "x\n")
    take(lab)
    write(lab.ws / "notes.txt", "new\n")
    before = tree(lab.ws)
    with (lab.store() / "lock").open("a") as held:
        fcntl.flock(held.fileno(), fcntl.LOCK_EX)
        t0 = time.monotonic()
        r = undo(lab, "--text", "--yes", timeout=30)
        elapsed = time.monotonic() - t0
    assert LOCK_VERDICT in stderr_error(r, 1)  # the lock timeout stays a structured error
    assert 9 <= elapsed < 15, elapsed
    assert tree(lab.ws) == before
    assert snapshot_ids(lab) == [1]


# ── the Cut on --yes: `more` reads the artefact, never restores again ─────────────────────────


@pytest.mark.parametrize("mode", ["--json", "--text"])
def test_yes_over_the_limit_cuts_with_a_sed_more_never_a_rerun(lab: Lab, mode: str) -> None:
    write(lab.ws / "keep.txt", "x\n")
    take(lab)
    pre = tree(lab.ws)
    for i in range(25):
        write(lab.ws / f"n{i:02d}.txt", "x\n")
    planned = [line_of((p["change"], p["kind"], p["path"])) for p in dry(lab)["plan"]]
    assert len(planned) == 25

    r = undo(lab, mode, "--yes", "--limit", "3")
    assert r.returncode == 0, (r.stdout, r.stderr)
    if mode == "--json":
        d = doc_of(r)
        assert d["verdict"].startswith("restored to snapshot 1: 0 restored, 25 removed; verified;")
        more, shown = d["truncated"]["more"], d["lines"]
    else:
        out = text_of(r)
        assert out[1].startswith("verdict: restored to snapshot 1: 0 restored, 25 removed; verified;")
        mores = [x for x in out if x.startswith("more: ")]
        assert len(mores) == 1, out
        more, shown = mores[0].removeprefix("more: "), out
    assert tree(lab.ws) == pre
    printed = check_cut_more(more, tool="undo")
    omitted = [x for x in planned if x not in shown]
    assert omitted and all(x in printed for x in omitted), (omitted, printed)
    assert tree(lab.ws) == pre and snapshot_ids(lab) == [2, 1]  # reading `more` restored nothing


# ── FR-21: manifest, conformance, events ──────────────────────────────────────────────────────


def test_manifest_is_mutating_and_destructive_with_the_confirm_envelope(lab: Lab) -> None:
    r = undo(lab, "--agent-info")
    assert r.returncode == 0
    info = doc_of(r)
    assert schema.errors(info, schema.load("agent-info.schema.json")) == []
    assert info["tool"] == "undo"
    assert (info["mutating"], info["destructive"]) == (True, True)
    assert "--yes" in info["flags"] and "--dry-run" in info["flags"]
    assert info["envelopes"] == ["confirmation_required"]
    assert info["probe"] == ["--dry-run"]
    assert set(info["exit_codes"]) == {"0", "1", "2", "3", "4"}


def test_help_is_within_40_lines(lab: Lab) -> None:
    r = undo(lab, "--help")
    assert r.returncode == 0
    lines = r.stdout.splitlines()
    assert 0 < len(lines) <= 40 and lines[0].startswith("undo: ")


@pytest.mark.parametrize("where", ["workspace", "home"])
def test_conform_passes_on_snapshot_and_undo_installed_together(lab: Lab, where: str) -> None:
    """undo loads snapshot from its own real directory (R8), so both are installed into one bindir.
    Conform probes in its own working directory: a fresh workspace (no snapshots: undo exits 3) and the
    home directory (refused: both exit 1). R5 says both conform."""
    bindir = lab.tmp / "bin"
    install(TOOLS_DIR / "snapshot", bindir)
    install(TOOLS_DIR / "undo", bindir)
    conf = lab.tmp / "conf"
    install(TOOLS_DIR / "timelike-conform", conf)
    write(lab.ws / "f.txt", "x\n")
    env = env_for(lab.scratch, [bindir], on_path=[bindir, conf], HOME=str(lab.home))
    cwd = lab.ws if where == "workspace" else lab.home
    before = tree(lab.ws)
    r = subprocess.run(
        ["timelike-conform", "--json"],
        cwd=str(cwd),
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=90,
        start_new_session=True,
    )
    doc = json.loads(r.stdout)
    assert r.returncode == 0, doc["failures"]
    assert (doc["verdict"], doc["checked"], doc["tools"]) == ("pass", 2, ["snapshot", "undo"])
    assert tree(lab.ws) == before


def test_one_event_per_invocation(lab: Lab) -> None:
    write(lab.ws / "f.txt", "x\n")
    expected: list[int] = []

    def go(*args: str, cwd: Path | None = None, **env: str) -> None:
        r = undo(lab, *args, cwd=cwd, **env)
        expected.append(r.returncode)
        assert len([e for e in events(lab.scratch, SESSION) if e["tool"] == "undo"]) == len(expected), args

    go("--json", "--dry-run")  # no snapshots
    take(lab)
    write(lab.ws / "notes.txt", "new\n")
    go("--json", "--dry-run")
    go("--json")  # the envelope
    go("--json", "9", "--yes")  # unknown id
    go("--json", "--yes", cwd=lab.home)  # refused
    go("--json", "--no-such-flag")
    go("--json", "--yes")  # restores, and its safety snapshot is not a second event
    assert expected == [3, 0, 4, 3, 1, 2, 0]
    evs = events(lab.scratch, SESSION)
    assert [e["tool"] for e in evs] == ["undo", "snapshot", *["undo"] * 6]
    undo_evs = [e for e in evs if e["tool"] == "undo"]
    assert [e["exit"] for e in undo_evs] == expected
    event_schema = schema.load("event.schema.json")
    for ev in undo_evs:
        assert ev["session"] == SESSION
        assert schema.errors(ev, event_schema) == []
