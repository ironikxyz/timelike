"""snapshot (feature 005, slice 0, T008) against contracts/recover-cli.md, spec FR-1 to FR-13, data-model.md.

Written from the contract alone, before the tool. The tool runs as a real subprocess with its working
directory in a workspace built by git itself under tmp_path; HOME points at a sibling of the workspace,
never an ancestor of it, and the scratch root is outside both. State is compared by the test walking the
tree itself (kind, permission bits, sha256 or link text), never by trusting the tool's message (P004).

The helpers at the top are shared with test_undo.py, which imports them from here.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import shlex
import stat
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
import schema
from conftest import TOOLS_DIR, base_env, events

SNAPSHOT = TOOLS_DIR / "snapshot"
UNDO = TOOLS_DIR / "undo"
SESSION = "recover-t008"
Proc = subprocess.CompletedProcess[str]
# data-model § Lock gives the whole text; FR-24 also asks it to name the holder, so the tool may add the
# lock's path before the closing parenthesis. The test pins the contract's words up to there.
LOCK_VERDICT = "another snapshot or undo is running on this workspace (lock held for 10 s"
CAP_VARS = (
    "TIMELIKE_SNAPSHOT_MAX_BYTES",
    "TIMELIKE_SNAPSHOT_MAX_FILE_BYTES",
    "TIMELIKE_SNAPSHOT_MAX_ENTRIES",
)
GIT_ID = ["-c", "user.name=Timelike Test", "-c", "user.email=t008@example.invalid"]
GIT_CFG = [*GIT_ID, "-c", "init.defaultBranch=main", "-c", "commit.gpgsign=false"]


# ── the lab: a home, a workspace and a scratch root, as siblings in tmp_path ──────────────────


@dataclass
class Lab:
    tmp: Path
    home: Path  # HOME: a sibling of every workspace, never an ancestor
    ws: Path  # the default workspace
    scratch: Path  # TIMELIKE_SCRATCH_ROOT, outside the workspace

    def env(self, **extra: str) -> dict[str, str]:
        return base_env(self.scratch, SESSION, HOME=str(self.home), **extra)

    def store(self, ws: Path | None = None) -> Path:
        """data-model: <scratch root>/<session>/snapshots/<first 16 hex of sha256(realpath ws)>/"""
        real = os.path.realpath(ws or self.ws)
        key = hashlib.sha256(real.encode()).hexdigest()[:16]
        return self.scratch / SESSION / "snapshots" / key


@pytest.fixture
def lab(tmp_path: Path) -> Lab:
    home = tmp_path / "home"
    home.mkdir()
    ws = tmp_path / "ws"
    ws.mkdir()
    return Lab(tmp_path, home, ws, tmp_path / "scratch")


def call(tool: Path, lab: Lab, *args: str, cwd: Path | None = None, timeout: float = 20, **env: str) -> Proc:
    """conftest.run's conventions (stdin /dev/null, no controlling terminal, a timeout), plus a cwd."""
    return subprocess.run(
        [sys.executable, str(tool), *args],
        cwd=str(cwd or lab.ws),
        env=lab.env(**env),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=timeout,
        start_new_session=True,
    )


def snap(lab: Lab, *args: str, **kw: Any) -> Proc:
    return call(SNAPSHOT, lab, *args, **kw)


def undo(lab: Lab, *args: str, **kw: Any) -> Proc:
    return call(UNDO, lab, *args, **kw)


def doc_of(r: Proc) -> dict[str, Any]:
    try:
        d: dict[str, Any] = json.loads(r.stdout)
    except ValueError:
        why = f"stdout is not one JSON object (exit {r.returncode}):\n{r.stdout}\n{r.stderr}"
        raise AssertionError(why) from None
    return d


def text_of(r: Proc) -> list[str]:
    return r.stdout.splitlines()


def said(r: Proc) -> str:
    """Both streams, for failure messages only: no assertion relies on which stream carries the words."""
    return r.stdout + "\n" + r.stderr


def outcome(r: Proc, code: int, scope: str) -> dict[str, Any]:
    """Contract § "Outcomes are verdicts, errors are errors": a refusal, a missing snapshot and a failed
    verification are RESULTS — the header and the verdict on stdout, `do instead: <remedy>` as the first
    line, `data.remedy`, and the exit code. Nothing on stderr. Run with --json."""
    assert r.returncode == code, said(r)
    assert r.stderr == "", r.stderr
    d = doc_of(r)
    assert list(d)[:3] == ["tool", "target", "scope"] and d["scope"] == scope, d
    assert d["exit"] == code
    assert d["lines"][0] == f"do instead: {d['remedy']}", d
    return d


def outcome_text(r: Proc, code: int, header: str) -> list[str]:
    """The same outcome in text: header, verdict, then the `do instead:` line."""
    assert r.returncode == code, said(r)
    assert r.stderr == "", r.stderr
    out = text_of(r)
    assert out[0] == header, out
    assert out[1].startswith("verdict: ") and out[2].startswith("do instead: "), out
    return out


def stderr_error(r: Proc, code: int) -> str:
    """A structured error (rule 14) in text form: one line on stderr, nothing on stdout."""
    assert r.returncode == code, said(r)
    assert r.stdout == "", r.stdout
    lines = r.stderr.strip().splitlines()
    assert len(lines) == 1 and re.match(rf"^error: .* \(code {code}\) — ", lines[0]), r.stderr
    return lines[0]


def human(n: int) -> str:
    """The contract's <size>: `512 B`, `2.1 KiB`, `3.4 MiB`, `1.2 GiB`, one decimal."""
    if n < 1024:
        return f"{n} B"
    value = float(n)
    for unit in ("KiB", "MiB", "GiB"):
        value /= 1024
        if value < 1024 or unit == "GiB":
            return f"{value:.1f} {unit}"
    raise AssertionError("unreachable")


def ws_id(r: Proc) -> int:
    d = doc_of(r)
    assert r.returncode == 0, (r.stdout, r.stderr)
    ident: int = d["id"]
    return ident


# ── the test's own view of a tree ─────────────────────────────────────────────────────────────


def tree(root: Path, *, skip_git: bool = True) -> dict[str, tuple[Any, ...]]:
    """Every entry below root: path -> (kind, mode, sha256 | link text). Never follows a symlink.

    With skip_git, any entry named `.git` (directory, file or link) is skipped with everything under it,
    as the tool's walk does. Without it, the result includes every byte of every `.git`.
    """
    out: dict[str, tuple[Any, ...]] = {}

    def walk(d: str, rel: str) -> None:
        for e in sorted(os.scandir(d), key=lambda x: x.name):
            if skip_git and e.name == ".git":
                continue
            p = f"{rel}/{e.name}" if rel else e.name
            st = os.lstat(e.path)
            mode = st.st_mode & 0o7777
            if stat.S_ISLNK(st.st_mode):
                out[p] = ("link", os.readlink(e.path))
            elif stat.S_ISDIR(st.st_mode):
                out[p] = ("dir", mode)
                walk(e.path, p)
            elif stat.S_ISREG(st.st_mode):
                try:
                    digest = hashlib.sha256(Path(e.path).read_bytes()).hexdigest()
                except PermissionError:
                    digest = "unreadable"
                out[p] = ("file", mode, digest, st.st_size)
            else:
                out[p] = ("special", stat.S_IFMT(st.st_mode))

    walk(str(root), "")
    return out


def git_state(root: Path) -> dict[str, tuple[Any, ...]]:
    """Every `.git` below root (top level and nested, directory or file), byte for byte, with modes."""
    return {p: v for p, v in tree(root, skip_git=False).items() if ".git" in p.split("/")}


def counts(t: dict[str, tuple[Any, ...]]) -> tuple[int, int, int, int]:
    files = [v for v in t.values() if v[0] == "file"]
    return (
        len(files),
        sum(1 for v in t.values() if v[0] == "link"),
        sum(1 for v in t.values() if v[0] == "dir"),
        sum(v[3] for v in files),
    )


def write(p: Path, data: bytes | str, mode: int | None = None) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        data = data.encode()
    p.write_bytes(data)
    if mode is not None:
        p.chmod(mode)
    return p


# ── real repositories, built by git ───────────────────────────────────────────────────────────


def git(cwd: Path, *args: str, home: Path) -> str:
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(home),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "LC_ALL": "C.UTF-8",
    }
    r = subprocess.run(
        ["git", *GIT_CFG, *args],
        cwd=str(cwd),
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert r.returncode == 0, f"git {' '.join(args)}: {r.stderr}"
    return r.stdout


def make_repo(ws: Path, home: Path, outside: Path | None = None) -> None:
    """A repository with commits, a staged index, a stash, ignored and untracked files, a nested
    repository, a 0600 file, an executable, symlinks (file, directory, dangling, pointing outside)."""
    git(ws, "init", "-q", home=home)
    write(ws / ".gitignore", "build/\n*.log\n")
    write(ws / "README.md", "# demo\n")
    write(ws / "src" / "app.py", "print('app')\n")
    write(ws / "src" / "lib" / "util.py", "X = 1\n")
    write(ws / "run.sh", "#!/bin/sh\necho run\n", 0o755)
    git(ws, "add", "-A", home=home)
    git(ws, "commit", "-q", "-m", "first", home=home)
    write(ws / "README.md", "# demo\nstashed edit\n")
    git(ws, "stash", "-q", home=home)
    write(ws / "src" / "app.py", "print('app, staged')\n")
    git(ws, "add", "src/app.py", home=home)
    write(ws / "build" / "out.bin", bytes(range(256)) * 4)  # ignored
    write(ws / "debug.log", "ignored log\n")  # ignored
    write(ws / "notes" / "todo.txt", "untracked\n")  # untracked
    write(ws / "secret.txt", "private\n", 0o600)  # untracked, 0600
    (ws / "empty-dir").mkdir()
    os.symlink("README.md", ws / "readme-link")
    os.symlink("src", ws / "src-link")  # a link to a directory: a link, never descended
    os.symlink("no/such/target", ws / "dangling")
    if outside is not None:
        os.symlink(str(outside), ws / "outside-link")
    inner = ws / "vendor" / "inner"
    inner.mkdir(parents=True)
    git(inner, "init", "-q", home=home)
    write(inner / "lib.txt", "nested project\n")
    git(inner, "add", "-A", home=home)
    git(inner, "commit", "-q", "-m", "inner", home=home)


def take(lab: Lab, *args: str, cwd: Path | None = None, **env: str) -> dict[str, Any]:
    r = snap(lab, "--json", *args, cwd=cwd, **env)
    assert r.returncode == 0, (r.stdout, r.stderr)
    return doc_of(r)


def record(lab: Lab, ident: int, ws: Path | None = None) -> dict[str, Any]:
    rec: dict[str, Any] = json.loads((lab.store(ws) / "snaps" / f"{ident}.json").read_text())
    return rec


def snapshot_ids(lab: Lab, cwd: Path | None = None) -> list[int]:
    r = snap(lab, "--json", "list", cwd=cwd)
    assert r.returncode == 0, (r.stdout, r.stderr)
    return [s["id"] for s in doc_of(r)["snapshots"]]


def no_store_written(lab: Lab, ws: Path) -> bool:
    s = lab.store(ws)
    return not (s / "snaps").exists() or not any((s / "snaps").iterdir())


def check_cut_more(more: str, *, tool: str) -> list[str]:
    """`more` is a `sed -n` over an artefact; it never names the tool, so it never re-runs a mutation.
    Runs it, and returns what it prints."""
    words = shlex.split(more)
    assert words[:2] == ["sed", "-n"], more
    assert tool not in words and not any(os.path.basename(w) == tool for w in words), more
    assert "--yes" not in words and "--limit" not in words, more
    r = subprocess.run(words, capture_output=True, text=True, timeout=10, stdin=subprocess.DEVNULL)
    assert r.returncode == 0, r.stderr
    return r.stdout.splitlines()


# ── FR-1: the workspace is the nearest `.git` ancestor, else the current directory ────────────


def test_workspace_is_the_nearest_ancestor_holding_git(lab: Lab) -> None:
    make_repo(lab.ws, lab.home)
    d = take(lab, cwd=lab.ws / "src" / "lib")
    assert (d["tool"], d["scope"]) == ("snapshot", "take")
    assert d["target"] == os.path.realpath(lab.ws)
    files, links, dirs, size = counts(tree(lab.ws))
    assert (d["files"], d["links"], d["dirs"], d["bytes"]) == (files, links, dirs, size)


def test_workspace_found_through_a_git_file(lab: Lab) -> None:
    """A `.git` that is a file (a worktree's, made by git) marks a workspace too."""
    make_repo(lab.ws, lab.home)
    wt = lab.tmp / "wt"
    git(lab.ws, "worktree", "add", "-q", "-b", "side", str(wt), home=lab.home)
    assert (wt / ".git").is_file()
    d = take(lab, cwd=wt / "src")
    assert d["target"] == os.path.realpath(wt)
    files, links, dirs, size = counts(tree(wt))
    assert (d["files"], d["links"], d["dirs"], d["bytes"]) == (files, links, dirs, size)


def test_workspace_falls_back_to_the_current_directory(lab: Lab) -> None:
    plain = lab.ws / "a" / "b"
    write(plain / "f.txt", "x\n")
    write(lab.ws / "sibling.txt", "not in the workspace\n")
    d = take(lab, cwd=plain)
    assert d["target"] == os.path.realpath(plain)
    assert (d["files"], d["bytes"]) == (1, 2)


def test_workspace_is_resolved_to_its_real_path(lab: Lab) -> None:
    make_repo(lab.ws, lab.home)
    alias = lab.tmp / "alias"
    os.symlink(lab.ws, alias)
    d = take(lab, cwd=alias / "src")
    assert d["target"] == os.path.realpath(lab.ws)


# ── FR-2, FR-3: refused workspaces (exit 1, nothing written) ──────────────────────────────────


HOME_REMEDY = "change into the project directory (a directory below {home}) and run snapshot again"


def test_home_directory_is_refused_with_what_to_do(lab: Lab) -> None:
    write(lab.home / "dotfile", "x\n")
    home = os.path.realpath(lab.home)
    d = outcome(snap(lab, "--json", cwd=lab.home), 1, "take")
    assert d["target"] == home
    assert d["verdict"] == f"refused: {home} is your home directory"
    assert d["remedy"] == HOME_REMEDY.format(home=home)
    out = outcome_text(snap(lab, "--text", cwd=lab.home), 1, f"snapshot: {home} [take]")
    assert out[1:3] == [f"verdict: refused: {home} is your home directory", f"do instead: {d['remedy']}"]
    assert no_store_written(lab, lab.home)


def test_list_from_a_refused_workspace_is_refused_too(lab: Lab) -> None:
    """snapshot's conform probe is `list`, run in conform's own directory: the home directory."""
    home = os.path.realpath(lab.home)
    d = outcome(snap(lab, "--json", "list", cwd=lab.home), 1, "list")
    assert d["verdict"] == f"refused: {home} is your home directory"


def test_home_that_is_a_git_top_level_is_refused(lab: Lab) -> None:
    """D-2: a dotfiles repository at HOME is still the home directory."""
    git(lab.home, "init", "-q", home=lab.home)
    d = outcome(snap(lab, "--json", cwd=lab.home), 1, "take")
    assert d["verdict"] == f"refused: {os.path.realpath(lab.home)} is your home directory"


def test_ancestor_of_home_is_refused(lab: Lab) -> None:
    parent = lab.tmp / "h"
    home = parent / "agent"
    home.mkdir(parents=True)
    write(parent / "x.txt", "x\n")
    lab.home = home
    d = outcome(snap(lab, "--json", cwd=parent), 1, "take")
    assert d["target"] == os.path.realpath(parent)
    assert d["verdict"] == f"refused: {os.path.realpath(parent)} is an ancestor of your home directory"
    assert d["remedy"] == HOME_REMEDY.format(home=os.path.realpath(home))
    assert no_store_written(lab, parent)


def test_filesystem_root_is_refused(lab: Lab) -> None:
    d = outcome(snap(lab, "--json", cwd=Path("/")), 1, "take")
    assert (d["target"], d["verdict"]) == ("/", "refused: / is the filesystem root")
    assert d["remedy"] == HOME_REMEDY.format(home=os.path.realpath(lab.home))


def test_workspace_containing_the_store_is_refused(lab: Lab) -> None:
    make_repo(lab.ws, lab.home)
    inner_scratch = lab.ws / "scratch-here"
    lab.scratch = inner_scratch
    before = tree(lab.ws)
    d = outcome(snap(lab, "--json"), 1, "take")
    assert d["verdict"].startswith(f"refused: {os.path.realpath(lab.ws)} contains the snapshot store (")
    assert os.path.realpath(lab.ws) in d["verdict"].split("(", 1)[1], d["verdict"]  # the store path
    assert d["remedy"] == "set TIMELIKE_SCRATCH_ROOT outside the workspace"
    assert not (inner_scratch / SESSION / "snapshots").exists() or no_store_written(lab, lab.ws)
    after = {p: v for p, v in tree(lab.ws).items() if not p.startswith("scratch-here")}
    assert after == before


# ── FR-4, FR-5: what a snapshot holds ─────────────────────────────────────────────────────────


def test_take_records_tracked_untracked_ignored_files_links_and_dirs_with_modes(lab: Lab) -> None:
    outside = lab.tmp / "outside"
    write(outside / "not-mine.txt", "outside the workspace\n")
    make_repo(lab.ws, lab.home, outside=outside)
    expected = tree(lab.ws)
    files, links, dirs, size = counts(expected)

    r = snap(lab, "--json")
    assert r.returncode == 0, r.stderr
    d = doc_of(r)
    assert list(d)[:3] == ["tool", "target", "scope"]
    assert d["verdict"] == f"snapshot 1 taken: {files} files, {human(size)} (complete)"
    assert (d["id"], d["reason"], d["label"]) == (1, "on demand", None)
    assert (d["files"], d["links"], d["dirs"], d["bytes"]) == (files, links, dirs, size)
    assert (d["partial"], d["excluded"], d["excluded_bytes"]) == (False, [], 0)
    assert os.path.realpath(d["store"]) == os.path.realpath(lab.store())

    rec = record(lab, 1)
    assert rec["v"] == 1 and rec["id"] == 1 and rec["reason"] == "on demand"
    assert rec["workspace"] == os.path.realpath(lab.ws)
    assert rec["partial"] is False and rec["excluded"] == []
    paths = [e["path"] for e in rec["entries"]]
    assert paths == sorted(paths)
    got: dict[str, tuple[Any, ...]] = {}
    for e in rec["entries"]:
        p = e["path"]
        assert p and not p.startswith("/") and not {".", "..", ".git"} & set(p.split("/")), p
        if e["kind"] == "file":
            got[p] = ("file", e["mode"], e["sha256"], e["size"])
        elif e["kind"] == "link":
            got[p] = ("link", e["target"])
        else:
            assert e["kind"] == "dir", e
            got[p] = ("dir", e["mode"])
    assert got == expected
    # the three version-control statuses, the modes, and links never followed
    assert got["build/out.bin"][0] == "file" and got["debug.log"][0] == "file"  # ignored
    assert got["notes/todo.txt"][0] == "file"  # untracked
    assert got["secret.txt"][1] == 0o600 and got["run.sh"][1] == 0o755
    assert got["src-link"] == ("link", "src") and "src-link/app.py" not in got
    assert got["dangling"] == ("link", "no/such/target")
    assert got["outside-link"] == ("link", str(outside)) and not any("not-mine" in p for p in got)
    assert got["vendor/inner/lib.txt"][0] == "file"  # a nested project's files are captured...
    assert not any(".git" in p.split("/") for p in got)  # ...its .git is not, at any depth


def test_content_is_stored_by_hash_outside_the_workspace(lab: Lab) -> None:
    write(lab.ws / "a.txt", "same\n")
    write(lab.ws / "b.txt", "same\n")
    take(lab)
    digest = hashlib.sha256(b"same\n").hexdigest()
    obj = lab.store() / "objects" / digest[:2] / digest
    assert obj.read_bytes() == b"same\n"
    assert len(list((lab.store() / "objects").rglob("*"))) == 2  # one shard dir, one object
    take(lab)
    assert len(list((lab.store() / "objects").rglob("*"))) == 2  # stored once across snapshots


def test_taking_and_listing_change_neither_the_workspace_nor_git(lab: Lab) -> None:
    make_repo(lab.ws, lab.home)
    before, git_before = tree(lab.ws), git_state(lab.ws)
    take(lab)
    take(lab, "-m", "second")
    assert snap(lab, "--json", "list").returncode == 0
    assert snap(lab, "--text", "list", "--verbose").returncode == 0
    assert tree(lab.ws) == before
    assert git_state(lab.ws) == git_before
    assert (lab.ws / ".git").is_dir() and (lab.ws / "vendor" / "inner" / ".git").is_dir()


# ── FR-6: exclusions and their reasons ────────────────────────────────────────────────────────


def test_per_file_limit_and_size_cap_exclude_largest_first_with_reasons(lab: Lab) -> None:
    write(lab.ws / "big.bin", b"B" * 5000)  # over the per-file limit
    write(lab.ws / "a.bin", b"a" * 300)  # a tie with b.bin: the path decides, a.bin goes first
    write(lab.ws / "b.bin", b"b" * 300)
    write(lab.ws / "c.bin", b"c" * 200)
    write(lab.ws / "small.txt", b"s" * 10)
    caps = {"TIMELIKE_SNAPSHOT_MAX_FILE_BYTES": "1000", "TIMELIKE_SNAPSHOT_MAX_BYTES": "520"}

    d = take(lab, **caps)
    assert d["partial"] is True
    per_file = "over the per-file limit (1000 bytes)"
    size_cap = "over the size cap: largest files left out first (520 bytes)"
    excluded = sorted(d["excluded"], key=lambda x: x["path"])
    assert excluded == [
        {"path": "a.bin", "size": 300, "reason": size_cap},
        {"path": "big.bin", "size": 5000, "reason": per_file},
    ]
    assert (d["files"], d["bytes"], d["excluded_bytes"]) == (3, 510, 5300)
    assert d["verdict"] == (
        f"snapshot 1 taken (partial): 3 files, {human(510)}; excluded 2 files, {human(5300)} — see below"
    )
    rec = record(lab, 1)
    assert [e["path"] for e in rec["excluded"]] == ["a.bin", "big.bin"]  # the record sorts by path
    assert {e["path"] for e in rec["entries"]} == {"b.bin", "c.bin", "small.txt"}
    assert rec["caps"] == {"max_bytes": 520, "max_file_bytes": 1000, "max_entries": 50000}
    assert (d["stored_bytes"], d["verified"]) == (510, True)

    # Revision 11 (condition 3): the cap counts bytes NEW to the store. b, c and small are stored now,
    # so a second snapshot adds only a.bin (300 <= 520) and leaves out only what the per-file limit does.
    d2 = take(lab, **caps)
    assert [(x["path"], x["reason"]) for x in d2["excluded"]] == [("big.bin", per_file)]
    assert (d2["files"], d2["bytes"], d2["stored_bytes"]) == (4, 810, 300)

    # The text form, from an empty store (another session), where the size cap bites as in the JSON run.
    t = snap(lab, "--text", TIMELIKE_SESSION=f"{SESSION}-text", **caps)
    assert t.returncode == 0
    out = text_of(t)
    assert out[0] == f"snapshot: {os.path.realpath(lab.ws)} [take]"
    assert out[1].startswith("verdict: snapshot 1 taken (partial): ")
    ex = [x for x in out if x.startswith("excluded: ")]
    assert ex == [  # largest first, then by path
        f"excluded: big.bin ({human(5000)}) — {per_file}",
        f"excluded: a.bin ({human(300)}) — {size_cap}",
    ]
    # "A last line ... and/or": one line naming both, or one line per cap, at the end (see the report)
    raise_lines = [x for x in out if x.startswith("raise with ")]
    assert raise_lines and out[-len(raise_lines) :] == raise_lines, out
    named = " ".join(raise_lines)
    assert "TIMELIKE_SNAPSHOT_MAX_FILE_BYTES=5000" in named
    # the value that would have captured everything: all content new to that store, big.bin included
    assert "TIMELIKE_SNAPSHOT_MAX_BYTES=5810" in named


# ── revision 11, plan's conditions on the store (send 07-rev11-20261004-030207) ───────────────


def object_bytes(lab: Lab) -> int:
    """What the store holds, measured by the test on disk (P004), not by the tool's account of it."""
    return sum(p.stat().st_size for p in (lab.store() / "objects").rglob("*") if p.is_file())


def test_a_repeated_snapshot_of_an_unchanged_workspace_adds_no_stored_bytes(lab: Lab) -> None:
    make_repo(lab.ws, lab.home)
    first = take(lab)
    held = object_bytes(lab)
    assert first["stored_bytes"] == held > 0
    second = take(lab)
    assert object_bytes(lab) == held  # condition 1: nothing new on disk
    assert second["stored_bytes"] == 0 and second["bytes"] == first["bytes"]
    write(lab.ws / "notes" / "new.txt", b"n" * 123)
    third = take(lab)
    assert third["stored_bytes"] == 123 and object_bytes(lab) == held + 123  # only what changed


def test_the_size_cap_counts_bytes_already_stored_as_nothing(lab: Lab) -> None:
    for i in range(4):
        write(lab.ws / f"f{i}.bin", bytes([65 + i]) * 400)
    take(lab)  # no cap: 1600 bytes stored
    write(lab.ws / "g.bin", b"g" * 300)
    d = take(lab, TIMELIKE_SNAPSHOT_MAX_BYTES="500")  # 1900 bytes of files, 300 of them new
    assert d["partial"] is False and d["excluded"] == [], d["excluded"]
    assert (d["files"], d["bytes"], d["stored_bytes"]) == (5, 1900, 300)


def test_the_size_cap_counts_content_repeated_within_a_snapshot_once(lab: Lab) -> None:
    write(lab.ws / "a.bin", b"x" * 300)
    write(lab.ws / "copy" / "a.bin", b"x" * 300)
    write(lab.ws / "b.bin", b"y" * 150)
    d = take(lab, TIMELIKE_SNAPSHOT_MAX_BYTES="450")  # 750 bytes of files, 450 of distinct content
    assert d["partial"] is False, d["excluded"]
    assert (d["files"], d["bytes"], d["stored_bytes"]) == (3, 750, 450)
    assert object_bytes(lab) == 450


def test_over_the_cap_files_sharing_content_are_left_out_together_largest_first(lab: Lab) -> None:
    write(lab.ws / "a.bin", b"x" * 300)
    write(lab.ws / "dup.bin", b"x" * 300)
    write(lab.ws / "b.bin", b"y" * 200)
    write(lab.ws / "c.txt", b"z" * 10)
    t = snap(lab, "--text", TIMELIKE_SNAPSHOT_MAX_BYTES="250")  # new content 510 > 250
    assert t.returncode == 0, t.stderr
    reason = "over the size cap: largest files left out first (250 bytes)"
    out = text_of(t)
    assert [x for x in out if x.startswith("excluded: ")] == [
        f"excluded: a.bin ({human(300)}) — {reason}",
        f"excluded: dup.bin ({human(300)}) — {reason}",
    ]
    assert out[-1] == "raise with TIMELIKE_SNAPSHOT_MAX_BYTES=510"  # distinct new content, counted once
    rec = record(lab, 1)
    assert {e["path"] for e in rec["entries"]} == {"b.bin", "c.txt"}
    assert (rec["bytes"], rec["stored_bytes"]) == (210, 210)


def test_taken_follows_a_check_that_every_stored_object_reads_back_by_its_hash(lab: Lab) -> None:
    """Condition 4: plant a damaged object where `put` will find it and trust it. The re-hash catches
    it: no snapshot is taken or listed, the damaged object is removed, and the next snapshot succeeds."""
    write(lab.ws / "a.txt", b"real content\n")
    digest = hashlib.sha256(b"real content\n").hexdigest()
    take(lab)  # creates the store; snapshot 1 is sound
    obj = lab.store() / "objects" / digest[:2] / digest
    obj.chmod(0o600)
    obj.write_bytes(b"real contenX\n")  # same size, wrong bytes

    d = outcome(snap(lab, "--json"), 1, "take")
    assert d["verdict"].startswith("snapshot 2 not taken: it could not be verified restorable: object ")
    assert not d["verdict"].startswith("snapshot 2 taken") and "run snapshot again" in d["remedy"]
    assert not (lab.store() / "snaps" / "2.json").exists() and not obj.exists()
    assert snapshot_ids(lab) == [1]

    d3 = take(lab)
    assert d3["id"] == 3 and d3["verified"] is True  # ids are never reused (FR-11)
    assert obj.read_bytes() == b"real content\n"


def test_only_the_per_file_limit_bit_names_only_its_variable(lab: Lab) -> None:
    write(lab.ws / "big.bin", b"B" * 3000)
    write(lab.ws / "small.txt", b"s" * 10)
    t = snap(lab, "--text", TIMELIKE_SNAPSHOT_MAX_FILE_BYTES="1000")
    assert t.returncode == 0
    raise_line = [x for x in text_of(t) if x.startswith("raise with ")]
    assert raise_line == ["raise with TIMELIKE_SNAPSHOT_MAX_FILE_BYTES=3000"], text_of(t)


def test_a_fifo_is_excluded_as_not_a_regular_file_and_never_read(lab: Lab) -> None:
    write(lab.ws / "f.txt", "x\n")
    os.mkfifo(lab.ws / "pipe")
    d = take(lab)  # a read of the fifo would block until the subprocess timeout
    assert d["partial"] is True
    assert [(e["path"], e["reason"]) for e in d["excluded"]] == [
        ("pipe", "not a regular file, symlink or directory (fifo)")
    ]
    assert d["files"] == 1


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads a 000 file; the case does not arise")
def test_an_unreadable_file_is_excluded_with_its_error(lab: Lab) -> None:
    write(lab.ws / "f.txt", "x\n")
    locked = write(lab.ws / "locked.txt", "secret\n", 0o000)
    try:
        d = take(lab)
    finally:
        locked.chmod(0o600)
    assert d["partial"] is True
    assert d["excluded"] == [{"path": "locked.txt", "size": 7, "reason": "unreadable: Permission denied"}]
    assert d["files"] == 1


def test_a_cap_of_zero_means_no_limit(lab: Lab) -> None:
    write(lab.ws / "big.bin", b"B" * 5000)
    for i in range(5):
        write(lab.ws / f"f{i}.txt", "x\n")
    d = take(lab, **{v: "0" for v in CAP_VARS})
    assert d["partial"] is False and d["files"] == 6


# ── FR-7: the entry cap refuses ───────────────────────────────────────────────────────────────


def test_over_the_entry_cap_is_refused_and_nothing_is_stored(lab: Lab) -> None:
    for i in range(10):
        write(lab.ws / f"f{i}.txt", "x\n")
    d = outcome(snap(lab, "--json", TIMELIKE_SNAPSHOT_MAX_ENTRIES="5"), 1, "take")
    assert d["verdict"].startswith(
        f"refused: {os.path.realpath(lab.ws)} has more than 5 entries (TIMELIKE_SNAPSHOT_MAX_ENTRIES)"
    ), d["verdict"]
    assert d["remedy"] == "snapshot a smaller directory, or raise TIMELIKE_SNAPSHOT_MAX_ENTRIES"
    assert no_store_written(lab, lab.ws)
    assert snapshot_ids(lab) == []


def test_the_entry_cap_does_not_count_git(lab: Lab) -> None:
    make_repo(lab.ws, lab.home)
    n = len(tree(lab.ws))  # every entry outside any .git (exclusions would count too; there are none)
    assert len(tree(lab.ws, skip_git=False)) > n
    assert snap(lab, "--json", TIMELIKE_SNAPSHOT_MAX_ENTRIES=str(n)).returncode == 0
    outcome(snap(lab, "--json", TIMELIKE_SNAPSHOT_MAX_ENTRIES=str(n - 1)), 1, "take")


# ── FR-8: an invalid cap value is a usage error naming the variable ───────────────────────────


@pytest.mark.parametrize("var", CAP_VARS)
@pytest.mark.parametrize("value", ["abc", "-1", "1.5", "1e3"])
def test_an_invalid_cap_value_is_exit_2_naming_the_variable(lab: Lab, var: str, value: str) -> None:
    write(lab.ws / "f.txt", "x\n")
    r = snap(lab, "--json", **{var: value})
    assert r.returncode == 2
    err = json.loads(r.stderr)
    assert err["code"] == 2 and err["tool"] == "snapshot"
    assert var in err["error"] + " " + err["remediation"], err
    assert no_store_written(lab, lab.ws)
    assert r.stdout == ""
    assert var in stderr_error(snap(lab, "--text", **{var: value}), 2)


# ── FR-9 to FR-12: identifiers, labels and the list ───────────────────────────────────────────


def test_identifiers_are_1_2_3_in_the_order_taken(lab: Lab) -> None:
    write(lab.ws / "f.txt", "x\n")
    assert [take(lab)["id"] for _ in range(3)] == [1, 2, 3]
    assert (lab.store() / "workspace").read_text().strip() == os.path.realpath(lab.ws)
    assert (lab.store() / "next").read_text().strip() == "4"


def test_list_is_newest_first_with_labels_and_no_times_unless_verbose(lab: Lab) -> None:
    write(lab.ws / "f.txt", "hello\n")
    take(lab, "-m", "first try")
    write(lab.ws / "g.txt", "world!\n")
    take(lab)
    take(lab, "-m", "third")

    r = snap(lab, "--json", "list")
    assert r.returncode == 0
    d = doc_of(r)
    assert (d["scope"], d["verdict"]) == ("list", "3 snapshots")
    assert d["target"] == os.path.realpath(lab.ws)
    rows = d["snapshots"]
    assert [s["id"] for s in rows] == [3, 2, 1]
    assert rows[2] == {
        "id": 1,
        "reason": "on demand",
        "label": "first try",
        "files": 1,
        "bytes": 6,
        "partial": False,
    }
    assert rows[1]["label"] is None and rows[1]["files"] == 2
    assert all("taken_at" not in s for s in rows)

    t = snap(lab, "--text", "list")
    out = text_of(t)
    assert out[:2] == [f"snapshot: {os.path.realpath(lab.ws)} [list]", "verdict: 3 snapshots"]
    assert out[2:] == [  # the label is the line's last column, after the same two-space separator
        f'3  on demand  2 files  {human(13)}  complete  "third"',
        f"2  on demand  2 files  {human(13)}  complete",
        f'1  on demand  1 files  {human(6)}  complete  "first try"',
    ]
    assert not any("taken" in x for x in out)

    v = doc_of(snap(lab, "--json", "list", "--verbose"))
    stamps = [s["taken_at"] for s in v["snapshots"]]
    assert all(re.match(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d", x) for x in stamps), stamps
    vt = [x for x in text_of(snap(lab, "--text", "list", "--verbose")) if re.match(r"^\d+  ", x)]
    assert len(vt) == 3 and all("taken " in x for x in vt), vt


def test_list_with_no_snapshots_is_zero_and_exit_0(lab: Lab) -> None:
    write(lab.ws / "f.txt", "x\n")
    r = snap(lab, "--json", "list")
    assert r.returncode == 0
    d = doc_of(r)
    assert (d["verdict"], d["snapshots"]) == ("0 snapshots", [])
    assert text_of(snap(lab, "--text", "list"))[1] == "verdict: 0 snapshots"


def test_a_partial_snapshot_says_so_in_the_list(lab: Lab) -> None:
    write(lab.ws / "big.bin", b"B" * 3000)
    write(lab.ws / "f.txt", "x\n")
    take(lab, TIMELIKE_SNAPSHOT_MAX_FILE_BYTES="1000")
    out = text_of(snap(lab, "--text", "list"))
    assert out[2] == f"1  on demand  1 files  {human(2)}  partial"
    assert doc_of(snap(lab, "--json", "list"))["snapshots"][0]["partial"] is True


# ── the output cap on take: Cut, `more` is sed over the artefact, never a re-run ──────────────


@pytest.mark.parametrize("mode", ["--json", "--text"])
def test_take_over_the_limit_cuts_with_a_sed_more_never_a_rerun(lab: Lab, mode: str) -> None:
    for i in range(30):
        write(lab.ws / f"x{i:02d}.bin", b"x" * (100 + i))
    write(lab.ws / "keep.txt", "x\n")
    r = snap(lab, mode, "--limit", "4", TIMELIKE_SNAPSHOT_MAX_FILE_BYTES="50")
    assert r.returncode == 0, r.stderr
    excluded_lines = [
        f"excluded: x{i:02d}.bin ({human(100 + i)}) — over the per-file limit (50 bytes)" for i in range(30)
    ]
    if mode == "--json":
        d = doc_of(r)
        assert d["verdict"].startswith("snapshot 1 taken (partial): 1 files")
        assert len(d["excluded"]) == 30  # JSON lists the exclusions in full
        more = d["truncated"]["more"]
        shown = d["lines"]
    else:
        out = text_of(r)
        assert out[1].startswith("verdict: snapshot 1 taken (partial): 1 files")
        mores = [x for x in out if x.startswith("more: ")]
        assert len(mores) == 1, out
        more = mores[0].removeprefix("more: ")
        shown = out
    assert len([x for x in shown if x.startswith("excluded: ")]) < 30
    printed = check_cut_more(more, tool="snapshot")
    omitted = [x for x in excluded_lines if x not in shown]
    assert omitted and all(x in printed for x in omitted), (omitted, printed)
    assert snapshot_ids(lab) == [1]  # reading `more` took no second snapshot


# ── FR-24: the lock ───────────────────────────────────────────────────────────────────────────


def test_take_waits_for_the_lock_then_exits_1_naming_the_holder(lab: Lab) -> None:
    """Slow by design (the contract's 10 s wait)."""
    write(lab.ws / "f.txt", "x\n")
    take(lab)  # creates the store and its lock file
    lock = lab.store() / "lock"
    assert lock.exists()
    with lock.open("a") as held:
        fcntl.flock(held.fileno(), fcntl.LOCK_EX)
        t0 = time.monotonic()
        r = snap(lab, "--text", timeout=30)
        elapsed = time.monotonic() - t0
    assert LOCK_VERDICT in stderr_error(r, 1)  # the lock timeout stays a structured error
    assert 9 <= elapsed < 15, elapsed
    assert snapshot_ids(lab) == [1]


# ── FR-21: the contract ───────────────────────────────────────────────────────────────────────


def test_manifest_is_neither_mutating_nor_destructive(lab: Lab) -> None:
    r = snap(lab, "--agent-info")
    assert r.returncode == 0
    info = doc_of(r)
    assert schema.errors(info, schema.load("agent-info.schema.json")) == []
    assert info["tool"] == "snapshot"
    assert (info["mutating"], info["destructive"]) == (False, False)
    assert info["probe"] == ["list"]
    assert "--yes" not in info["flags"] and "--dry-run" not in info["flags"]
    assert info["envelopes"] == []
    assert set(info["exit_codes"]) == {"0", "1", "2"}


def test_help_is_within_40_lines(lab: Lab) -> None:
    r = snap(lab, "--help")
    assert r.returncode == 0
    lines = r.stdout.splitlines()
    assert 0 < len(lines) <= 40 and lines[0].startswith("snapshot: ")


def test_one_event_per_invocation(lab: Lab) -> None:
    write(lab.ws / "f.txt", "x\n")
    expected: list[int] = []

    def go(*args: str, cwd: Path | None = None, **env: str) -> None:
        r = snap(lab, *args, cwd=cwd, **env)
        expected.append(r.returncode)
        assert len(events(lab.scratch, SESSION)) == len(expected), args

    go("--json")
    go("--json", "list")
    go("--json", "list", "--verbose")
    go("--json", TIMELIKE_SNAPSHOT_MAX_BYTES="x")
    go("--json", cwd=lab.home)
    go("--json", "--no-such-flag")
    assert expected == [0, 0, 0, 2, 1, 2]
    evs = events(lab.scratch, SESSION)
    assert [e["exit"] for e in evs] == expected
    event_schema = schema.load("event.schema.json")
    for ev in evs:
        assert (ev["tool"], ev["session"]) == ("snapshot", SESSION)
        assert schema.errors(ev, event_schema) == []
