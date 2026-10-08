"""view and search, feature 006 slice 1 (T017), against contracts/view-search-cli.md § Slice 1, spec FR-24 to
FR-36, SC-6 and SC-7, research R7 to R9.

Written from the contract alone, before the tool. Every tree and file is written by the test, and every
expected figure (counts, sizes, the breadth-first fit, sha256 anchors) is computed by the test from what it
wrote, never read back from the tool (P004, P005).

The test's own model of the overview (`model`) covers regular files and directories. Where the contract
leaves a figure open (whether the verdict's totals include ignored files, where a symlink sorts, what JSON's
`collapsed.path` is relative to), a fixture avoids the question or the test asserts only what the contract
fixes; each such point is named where it is met.
"""

from __future__ import annotations

import hashlib
import os
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from conftest import TOOLS_DIR
from test_snapshot import git, said, stderr_error, text_of, write
from test_view import (
    VIEW,
    Lab,
    Proc,
    big_texts,
    call,
    cut_line,
    make_lab,
    numbered,
    ok_json,
    result_outcome,
    write_lines,
)

SEARCH = TOOLS_DIR / "search"
SESSION = "bounded-t017"
BUDGET = 200
SLOW = 90.0  # seconds: the 10,000-file fixture is walked by the tool; a hang is a failure, never a wait

VCS = {".git", ".hg", ".svn"}
DEPENDENCY = {
    "node_modules",
    "bower_components",
    "jspm_packages",
    "vendor",
    ".venv",
    "venv",
    "site-packages",
    "Pods",
    ".bundle",
    "elm-stuff",
}
BUILD = {
    "build",
    "dist",
    "target",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".nox",
    ".gradle",
    ".next",
    ".nuxt",
    ".cache",
    "coverage",
    ".terraform",
}
PRECEDENCE = ["vcs", "dependency", "build", "ignored", "budget"]


@pytest.fixture
def lab(tmp_path: Path) -> Lab:
    return make_lab(tmp_path, SESSION)


def view(lab: Lab, *args: str, **kw: Any) -> Proc:
    return call(VIEW, lab, *args, **kw)


def search(lab: Lab, *args: str, **kw: Any) -> Proc:
    return call(SEARCH, lab, *args, **kw)


def rerun(lab: Lab, command: str, *, cwd: Path | None = None, mode: str = "--json") -> Proc:
    """Run a printed `view …` command as the agent would, in the given output mode."""
    words = shlex.split(command)
    assert words[0] == "view", command
    rest = [w for w in words[1:] if w not in ("--json", "--text")]
    return view(lab, mode, *rest, cwd=cwd, timeout=SLOW)


# ── the test's own figures ────────────────────────────────────────────────────────────────────


def size(n: int) -> str:
    """003's size(): an integer `B` below 1 KiB, else one decimal in KiB/MiB/GiB/TiB."""
    if n < 1024:
        return f"{n} B"
    value = float(n)
    unit = "KiB"
    for unit in ("KiB", "MiB", "GiB", "TiB"):
        value /= 1024
        if value < 1024 or unit == "TiB":
            break
    return f"{value:.1f} {unit}"


def plural(n: int, noun: str) -> str:
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


@dataclass
class Tally:
    files: int = 0
    dirs: int = 0
    bytes: int = 0


def tally(d: Path) -> Tally:
    """Everything below d, recursively, links never followed: regular files, directories, their bytes."""
    t = Tally()
    stack = [d]
    while stack:
        with os.scandir(stack.pop()) as it:
            for e in it:
                if e.is_symlink():
                    continue
                if e.is_dir(follow_symlinks=False):
                    t.dirs += 1
                    stack.append(Path(e.path))
                elif e.is_file(follow_symlinks=False):
                    t.files += 1
                    t.bytes += e.stat(follow_symlinks=False).st_size
    return t


def counts(t: Tally) -> str:
    return f"{plural(t.files, 'file')}, {plural(t.dirs, 'dir')}, {size(t.bytes)}"


def kind_by_name(name: str) -> str | None:
    if name in VCS:
        return "vcs"
    if name in DEPENDENCY:
        return "dependency"
    if name in BUILD or name.endswith(".egg-info"):
        return "build"
    return None


@dataclass
class Model:
    lines: list[str]
    collapsed: list[dict[str, Any]]  # path (DIR-relative), kind, files, dirs, bytes, expand

    def kinds(self) -> list[str]:
        return [c["kind"] for c in self.collapsed]


def model(
    root: Path,
    *,
    prefix: str = "",
    budget: int = BUDGET,
    ignored_files: frozenset[str] = frozenset(),
    ignored_dirs: frozenset[str] = frozenset(),
) -> Model:
    """The overview as the contract describes it (FR-26 to FR-29), for trees of files and directories.

    `prefix` is DIR's path as the expand command types it (`""` when DIR is the current directory). The
    ignored sets are DIR-relative paths the test wrote as ignored."""

    def kids(rel: str) -> tuple[list[str], list[str]]:
        d = root / rel if rel else root
        dirs, files = [], []
        for e in os.scandir(d):
            r = f"{rel}/{e.name}" if rel else e.name
            assert not e.is_symlink(), f"the model has no symlinks: {r}"
            if e.is_dir(follow_symlinks=False):
                dirs.append(e.name)
            elif r not in ignored_files:
                files.append(e.name)
        return sorted(dirs), sorted(files)

    def join(rel: str, name: str) -> str:
        return f"{rel}/{name}" if rel else name

    kind: dict[str, str] = {}
    expanded = {""}
    top_dirs, top_files = kids("")
    used = len(top_dirs) + len(top_files)
    level = list(top_dirs)
    while level:  # breadth-first: shallower first, then by path
        nxt: list[str] = []
        for rel in sorted(level):
            k = kind_by_name(rel.rsplit("/", 1)[-1]) or ("ignored" if rel in ignored_dirs else None)
            if k:
                kind[rel] = k
                continue
            d, f = kids(rel)
            if budget == 0 or used + len(d) + len(f) <= budget:
                expanded.add(rel)
                used += len(d) + len(f)
                nxt += [join(rel, x) for x in d]
            else:
                kind[rel] = "budget"
        level = nxt

    lines: list[str] = []
    collapsed: list[dict[str, Any]] = []

    def render(rel: str, depth: int) -> None:
        ind = "  " * depth
        d, f = kids(rel)
        for name in d:
            r = join(rel, name)
            if r in expanded:
                lines.append(f"{ind}{name}/")
                render(r, depth + 1)
                continue
            t = tally(root / r)
            cmd = shlex.join(["view", f"{prefix}{r}/"])
            lines.append(f"{ind}{name}/  {counts(t)}; {kind[r]} — expand: {cmd}")
            collapsed.append(
                {
                    "path": r,
                    "kind": kind[r],
                    "files": t.files,
                    "dirs": t.dirs,
                    "bytes": t.bytes,
                    "expand": cmd,
                }
            )
        for name in f:
            lines.append(f"{ind}{name}  {size((root / join(rel, name)).stat().st_size)}")

    render("", 0)
    return Model(lines, collapsed)


def verdict(total: Tally, dir_text: str, kinds: list[str], ignored: int = 0) -> str:
    v = f"{plural(total.files, 'file')}, {plural(total.dirs, 'dir')}, {size(total.bytes)} under {dir_text}"
    if kinds:
        each = ", ".join(f"{k} {kinds.count(k)}" for k in PRECEDENCE if k in kinds)
        v += f"; collapsed {len(kinds)} ({each})"
    if ignored:
        v += f"; {plural(ignored, 'ignored file')} not listed"
    return v


def overview_json(r: Proc) -> dict[str, Any]:
    d = ok_json(r)
    assert d["scope"] == "overview", d
    assert d["overview"] is True
    return d


def check_collapsed(d: dict[str, Any], m: Model, prefix: str = "") -> None:
    """JSON `collapsed`, in line order. `path` is checked against the two readings the contract allows
    (DIR-relative, or as the expand command types it; with or without the trailing slash)."""
    got = d["collapsed"]
    assert [c["kind"] for c in got] == m.kinds(), got
    for g, e in zip(got, m.collapsed, strict=True):
        assert (g["files"], g["dirs"], g["bytes"]) == (e["files"], e["dirs"], e["bytes"]), (g, e)
        assert g["complete"] is True, g
        assert g["expand"] == e["expand"], (g, e)
        p = e["path"]
        assert g["path"] in {p, f"{p}/", f"{prefix}{p}", f"{prefix}{p}/"}, (g, e)


def fill(d: Path, n: int, stem: str = "f", data: bytes = b"x\n") -> None:
    d.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        (d / f"{stem}{i:05d}.txt").write_bytes(data)


def kind_dir(d: Path) -> None:
    """A directory to collapse: 5 files and 2 directories below it, sizes all different."""
    write(d / "a.txt", b"a" * 10)
    write(d / "b.txt", b"b" * 20)
    write(d / "c.txt", b"c" * 2000)
    write(d / "one" / "x.txt", b"x" * 30)
    write(d / "two" / "y.txt", b"y" * 40)


# ── the overview: order, indentation, sizes (FR-24, FR-26) ────────────────────────────────────


@pytest.fixture
def small(lab: Lab) -> Path:
    root = lab.ws / "proj"
    write(root / "a" / "z.txt", b"hello")
    write(root / "a" / "inner" / "q.txt", b"q" * 2000)
    (root / "b").mkdir()
    write(root / "Z.txt", b"zzz")
    write(root / "m.txt", b"m")
    return root


SMALL_LINES = [
    "a/",
    "  inner/",
    "    q.txt  2.0 KiB",
    "  z.txt  5 B",
    "b/",
    "Z.txt  3 B",  # Python's str order: upper case before lower
    "m.txt  1 B",
]


def test_view_dot_is_an_overview_with_dirs_first_sorted_and_indented(lab: Lab, small: Path) -> None:
    d = overview_json(view(lab, "--json", ".", cwd=small))
    assert (d["tool"], d["target"]) == ("view", ".")
    assert d["lines"] == SMALL_LINES
    assert d["lines"] == model(small).lines  # the model agrees with the hand-written lines
    assert "truncated" not in d


def test_view_dir_from_its_parent(lab: Lab, small: Path) -> None:
    d = overview_json(view(lab, "--json", "proj"))
    assert d["target"] == "proj"
    assert d["lines"] == SMALL_LINES
    assert (d["path"], d["abs_path"]) == ("proj", str(small))


def test_the_text_output_is_header_verdict_and_the_lines(lab: Lab, small: Path) -> None:
    r = view(lab, "--text", ".", cwd=small)
    assert r.returncode == 0 and r.stderr == "", said(r)
    v = "4 files, 3 dirs, 2.0 KiB under ."  # 5 + 2000 + 3 + 1 = 2009 bytes
    assert verdict(tally(small), ".", []) == v
    assert text_of(r) == ["view: . [overview]", f"verdict: {v}", *SMALL_LINES]


def test_json_lines_equal_the_text_lines(lab: Lab, small: Path) -> None:
    d = overview_json(view(lab, "--json", ".", cwd=small))
    assert text_of(view(lab, "--text", ".", cwd=small))[2:] == d["lines"]


def test_json_fields_of_an_overview(lab: Lab, small: Path) -> None:
    """ASSUMED: the verdict's and JSON's totals count everything below DIR (a fixture with no ignored
    or collapsed entries, so either reading gives the same figures)."""
    d = overview_json(view(lab, "--json", "proj"))
    t = tally(small)
    assert (d["files"], d["dirs"], d["bytes"]) == (t.files, t.dirs, t.bytes) == (4, 3, 2009)
    assert d["ignored_files"] == 0
    assert d["budget_lines"] == BUDGET
    assert d["collapsed"] == []
    assert d["verdict"] == "4 files, 3 dirs, 2.0 KiB under proj"
    assert ok_json(view(lab, "--json", "--limit", "50", "proj"))["budget_lines"] == 50
    assert ok_json(view(lab, "--json", "--limit", "0", "proj"))["budget_lines"] == 0


def test_singulars_in_the_verdict(lab: Lab) -> None:
    root = lab.ws / "one"
    write(root / "d" / "f.txt", b"seven!\n")
    d = overview_json(view(lab, "--json", "one"))
    assert d["verdict"] == "1 file, 1 dir, 7 B under one"
    assert d["lines"] == ["d/", "  f.txt  7 B"]


def test_an_empty_directory(lab: Lab) -> None:
    (lab.ws / "void").mkdir()
    d = overview_json(view(lab, "--json", "void"))
    assert d["verdict"] == "0 files, 0 dirs, 0 B under void"
    assert d["lines"] == [] and d["collapsed"] == []


def test_a_name_longer_than_columns_is_cut(lab: Lab) -> None:
    root = lab.ws / "long"
    name = "n" * 230
    write(root / name, b"abc")
    d = overview_json(view(lab, "--json", "long"))
    assert d["lines"] == [cut_line(f"{name}  3 B", 200)]


def test_sizes_follow_the_size_rule(lab: Lab) -> None:
    root = lab.ws / "sizes"
    figures = {"a0": 0, "a1": 1023, "a2": 1024, "a3": 1536, "a4": 5 * 1024 * 1024 + 300_000}
    for name, n in figures.items():
        write(root / name, b"s" * n)
    d = overview_json(view(lab, "--json", "sizes"))
    assert d["lines"] == [f"{name}  {size(n)}" for name, n in figures.items()]
    assert [size(n) for n in figures.values()] == ["0 B", "1023 B", "1.0 KiB", "1.5 KiB", "5.3 MiB"]


# ── symlinks are shown and never followed (FR-26) ─────────────────────────────────────────────


def test_symlinks_are_shown_with_their_target_and_never_followed(lab: Lab) -> None:
    """Where a link sorts among directories and files is not fixed by the contract; its line is."""
    outside = lab.ws / "outside_big"
    fill(outside, 500, data=b"y" * 100)
    root = lab.ws / "proj"
    write(root / "a.txt", b"abc")
    os.symlink("../outside_big", root / "big-link")
    os.symlink("a.txt", root / "file-link")
    os.symlink("no/such/target", root / "dangling")
    deps = root / "node_modules"
    write(deps / "pkg" / "index.js", b"1;\n")
    os.symlink("../../outside_big", deps / "pkg" / "loop")
    d = overview_json(view(lab, "--json", "proj", timeout=SLOW))
    lines = d["lines"]
    for text in ("big-link -> ../outside_big", "file-link -> a.txt", "dangling -> no/such/target"):
        assert text in lines, lines
    assert "a.txt  3 B" in lines
    assert not any(x.startswith(" ") for x in lines), lines  # nothing below a link, nothing expanded
    assert d["bytes"] == 3 + 3  # regular files only: a.txt and node_modules/pkg/index.js
    assert d["files"] < 500
    nm = [c for c in d["collapsed"] if c["kind"] == "dependency"]
    assert len(nm) == 1 and nm[0]["bytes"] == 3 and nm[0]["files"] < 500, d["collapsed"]


# ── ignore rules (FR-27) ──────────────────────────────────────────────────────────────────────


def repo(lab: Lab, root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    git(root, "init", "-q", home=lab.home)


def add_exclude(root: Path, text: str) -> None:
    p = root / ".git" / "info" / "exclude"
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as f:
        f.write(text)


@pytest.fixture
def ignoring(lab: Lab) -> Path:
    """Ignored files at three levels (root .gitignore, a nested .gitignore, .git/info/exclude); no
    ignored directory, so the ignored-file count has one reading."""
    root = lab.ws / "proj"
    repo(lab, root)
    write(root / ".gitignore", "*.log\n")
    add_exclude(root, "local.tmp\n")
    write(root / "a.txt", b"aaaa")
    write(root / "x.log", b"ignored")
    write(root / "local.tmp", b"ignored")
    write(root / "sub" / ".gitignore", "secret.txt\n")
    write(root / "sub" / "b.txt", b"bb")
    write(root / "sub" / "secret.txt", b"ignored")
    write(root / "sub" / "deep" / "y.log", b"ignored")
    write(root / "sub" / "deep" / "c.txt", b"c")
    return root


IGNORED_FILES = frozenset({"x.log", "local.tmp", "sub/secret.txt", "sub/deep/y.log"})


def test_ignored_files_are_not_listed_and_are_counted(lab: Lab, ignoring: Path) -> None:
    d = overview_json(view(lab, "--json", ".", cwd=ignoring))
    m = model(ignoring, ignored_files=IGNORED_FILES)
    assert d["lines"] == m.lines
    assert m.kinds() == ["vcs"]
    assert not any(n in x for x in d["lines"] for n in ("x.log", "local.tmp", "secret.txt", "y.log"))
    assert d["ignored_files"] == 4
    assert d["verdict"].endswith("; collapsed 1 (vcs 1); 4 ignored files not listed"), d["verdict"]
    check_collapsed(d, m)


def test_one_ignored_file_is_singular(lab: Lab) -> None:
    root = lab.ws / "proj"
    repo(lab, root)
    write(root / ".gitignore", "*.log\n")
    write(root / "x.log", b"ignored")
    d = overview_json(view(lab, "--json", ".", cwd=root))
    assert d["ignored_files"] == 1
    assert d["verdict"].endswith("; 1 ignored file not listed"), d["verdict"]


def test_no_ignored_clause_when_nothing_is_ignored(lab: Lab, small: Path) -> None:
    d = overview_json(view(lab, "--json", "proj"))
    assert "ignored" not in d["verdict"] and "collapsed" not in d["verdict"]


def test_an_ignored_directory_is_collapsed_as_ignored(lab: Lab) -> None:
    root = lab.ws / "proj"
    repo(lab, root)
    write(root / ".gitignore", "out/\n")
    kind_dir(root / "out")
    write(root / "keep.txt", b"k")
    d = overview_json(view(lab, "--json", ".", cwd=root))
    m = model(root, ignored_dirs=frozenset({"out"}))
    assert m.kinds() == ["vcs", "ignored"]
    assert d["lines"] == m.lines
    assert "out/  5 files, 2 dirs, 2.1 KiB; ignored — expand: view out/" in d["lines"]
    assert "; collapsed 2 (vcs 1, ignored 1)" in d["verdict"], d["verdict"]
    check_collapsed(d, m)


def test_no_ignore_lists_everything_but_git_stays_collapsed(lab: Lab, ignoring: Path) -> None:
    write(ignoring / ".gitignore", "*.log\nout/\n")
    kind_dir(ignoring / "out")
    d = overview_json(view(lab, "--json", "--no-ignore", ".", cwd=ignoring))
    m = model(ignoring)
    assert m.kinds() == ["vcs"]
    assert d["lines"] == m.lines
    for listed in ("x.log  7 B", "local.tmp  7 B", "  secret.txt  7 B", "    y.log  7 B", "out/"):
        assert listed in d["lines"], listed
    assert d["ignored_files"] == 0 and "ignored file" not in d["verdict"]
    assert [c["kind"] for c in d["collapsed"]] == ["vcs"]


# ── collapsed kinds (FR-28) ───────────────────────────────────────────────────────────────────


KIND_CASES = [
    (".git", "vcs"),
    (".hg", "vcs"),
    (".svn", "vcs"),
    ("node_modules", "dependency"),
    (".venv", "dependency"),
    ("vendor", "dependency"),
    ("__pycache__", "build"),
    ("dist", "build"),
    ("pkg.egg-info", "build"),
]


@pytest.mark.parametrize(("name", "kind"), KIND_CASES, ids=[c[0] for c in KIND_CASES])
def test_each_kind_is_collapsed_to_one_line_with_its_counts(lab: Lab, name: str, kind: str) -> None:
    root = lab.ws / "proj"
    kind_dir(root / name)
    write(root / "keep.txt", b"keep")
    d = overview_json(view(lab, "--json", ".", cwd=root))
    m = model(root)
    assert m.kinds() == [kind]
    line = f"{name}/  5 files, 2 dirs, 2.1 KiB; {kind} — expand: view {name}/"
    assert m.lines == [line, "keep.txt  4 B"]
    assert d["lines"] == m.lines
    assert d["verdict"].endswith(f"; collapsed 1 ({kind} 1)"), d["verdict"]
    check_collapsed(d, m)


def test_singulars_in_a_collapsed_line(lab: Lab) -> None:
    root = lab.ws / "proj"
    write(root / "node_modules" / "pkg" / "i.js", b"1;\n")
    d = overview_json(view(lab, "--json", ".", cwd=root))
    assert d["lines"] == ["node_modules/  1 file, 1 dir, 3 B; dependency — expand: view node_modules/"]


def test_an_empty_kind_directory_counts_zero(lab: Lab) -> None:
    root = lab.ws / "proj"
    (root / "dist").mkdir(parents=True)
    d = overview_json(view(lab, "--json", ".", cwd=root))
    assert d["lines"] == ["dist/  0 files, 0 dirs, 0 B; build — expand: view dist/"]


def test_kinds_take_precedence_over_ignored_and_the_verdict_names_them_in_order(lab: Lab) -> None:
    root = lab.ws / "proj"
    repo(lab, root)
    write(root / ".gitignore", "node_modules/\ndist/\nlogs/\n")
    for name in ("node_modules", "dist", "logs"):
        kind_dir(root / name)
    d = overview_json(view(lab, "--json", ".", cwd=root))
    m = model(root, ignored_dirs=frozenset({"node_modules", "dist", "logs"}))
    assert m.kinds() == ["vcs", "build", "ignored", "dependency"]  # line order: .git, dist, logs, node_m…
    assert d["lines"] == m.lines
    assert "; collapsed 4 (vcs 1, dependency 1, build 1, ignored 1)" in d["verdict"], d["verdict"]
    check_collapsed(d, m)


def test_a_nested_kind_directory_expands_by_its_path(lab: Lab) -> None:
    root = lab.ws / "proj"
    kind_dir(root / "web" / "node_modules")
    write(root / "web" / "app.js", b"app();\n")
    d = overview_json(view(lab, "--json", ".", cwd=root))
    m = model(root)
    assert d["lines"] == m.lines
    assert "  node_modules/  5 files, 2 dirs, 2.1 KiB; dependency — expand: view web/node_modules/" in m.lines
    check_collapsed(d, m)


# ── the expand path (FR-28, cross-stack P002) ─────────────────────────────────────────────────


def test_expand_is_relative_to_the_cwd_when_below_it(lab: Lab) -> None:
    root = lab.ws / "proj"
    kind_dir(root / "node_modules")
    d = overview_json(view(lab, "--json", "proj"))
    m = model(root, prefix="proj/")
    assert (
        d["lines"]
        == m.lines
        == ["node_modules/  5 files, 2 dirs, 2.1 KiB; dependency — expand: view proj/node_modules/"]
    )
    check_collapsed(d, m, prefix="proj/")


def test_expand_is_absolute_when_not_below_the_cwd(lab: Lab) -> None:
    root = lab.ws / "proj"
    kind_dir(root / "node_modules")
    elsewhere = lab.ws / "elsewhere"
    elsewhere.mkdir()
    d = overview_json(view(lab, "--json", "../proj", cwd=elsewhere))
    expand = shlex.join(["view", f"{root}/node_modules/"])
    assert d["lines"] == [f"node_modules/  5 files, 2 dirs, 2.1 KiB; dependency — expand: {expand}"]
    assert d["collapsed"][0]["expand"] == expand


def test_expand_is_shell_quoted_when_needed(lab: Lab) -> None:
    root = lab.ws / "my app"
    kind_dir(root / "node_modules")
    d = overview_json(view(lab, "--json", "my app"))
    expand = "view 'my app/node_modules/'"
    assert shlex.join(["view", "my app/node_modules/"]) == expand
    assert d["lines"] == [f"node_modules/  5 files, 2 dirs, 2.1 KiB; dependency — expand: {expand}"]
    r = rerun(lab, expand)
    e = overview_json(r)
    assert e["lines"] == model(root / "node_modules", prefix="my app/node_modules/").lines


def test_the_expand_command_shows_the_directory_itself_not_collapsed(lab: Lab) -> None:
    root = lab.ws / "proj"
    kind_dir(root / "node_modules")
    d = overview_json(view(lab, "--json", ".", cwd=root))
    e = overview_json(rerun(lab, d["collapsed"][0]["expand"], cwd=root))
    assert e["target"] == "node_modules/"
    assert e["lines"] == model(root / "node_modules", prefix="node_modules/").lines
    assert e["lines"] == [
        "one/",
        "  x.txt  30 B",
        "two/",
        "  y.txt  40 B",
        "a.txt  10 B",
        "b.txt  20 B",
        "c.txt  2.0 KiB",
    ]
    assert e["collapsed"] == []


# ── SC-6: a 10,000-file dependency directory in a real repository ─────────────────────────────


SC6_PACKAGES = 40
SC6_LIB = 248  # 40 packages x (index.js + package.json + 248 in lib/) = 10,000 files


@pytest.fixture(scope="module")
def sc6(tmp_path_factory: pytest.TempPathFactory) -> tuple[Lab, Path]:
    lab = make_lab(tmp_path_factory.mktemp("sc6"), SESSION)
    root = lab.ws / "repo"
    repo(lab, root)
    write(root / "README.md", b"# demo\n")
    write(root / "src" / "main.py", b"print('main')\n" * 30)
    write(root / "src" / "util" / "io.py", b"x = 1\n")
    nm = root / "node_modules"
    for p in range(SC6_PACKAGES):
        pkg = nm / f"pkg{p:02d}"
        write(pkg / "index.js", f"module.exports = {p};\n")
        write(pkg / "package.json", f'{{"name": "pkg{p:02d}"}}\n')
        fill(pkg / "lib", SC6_LIB, data=b"export {};\n")
    assert tally(nm).files == 10_000  # the test counts them itself
    return lab, root


def test_sc6_a_10000_file_dependency_directory_is_one_line_within_200(sc6: tuple[Lab, Path]) -> None:
    lab, root = sc6
    nm = tally(root / "node_modules")
    assert (nm.files, nm.dirs) == (10_000, 2 * SC6_PACKAGES)
    r = view(lab, "--text", ".", cwd=root, timeout=SLOW)
    assert r.returncode == 0 and r.stderr == "", said(r)
    out = text_of(r)
    assert out[0] == "view: . [overview]"
    body = out[2:]
    assert len(body) <= BUDGET
    mine = [x for x in body if x.startswith("node_modules/")]
    assert mine == [
        f"node_modules/  10000 files, 80 dirs, {size(nm.bytes)}; dependency — expand: view node_modules/"
    ]
    assert not any("pkg" in x for x in body if not x.startswith("node_modules/"))
    assert any(x.startswith(".git/  ") and x.endswith("; vcs — expand: view .git/") for x in body), body


def test_sc6_the_whole_overview_matches_the_model(sc6: tuple[Lab, Path]) -> None:
    lab, root = sc6
    d = overview_json(view(lab, "--json", ".", cwd=root, timeout=SLOW))
    m = model(root)
    assert m.kinds() == ["vcs", "dependency"]
    assert d["lines"] == m.lines
    check_collapsed(d, m)
    assert "truncated" not in d


def test_sc6_the_verdict_counts_everything_below(sc6: tuple[Lab, Path]) -> None:
    """ASSUMED (medium): F, D and S count everything below DIR, collapsed contents included (the
    contract's `100000+` "past the cap" applies to counts generally; nothing here is ignored)."""
    lab, root = sc6
    d = overview_json(view(lab, "--json", ".", cwd=root, timeout=SLOW))
    t = tally(root)
    assert (d["files"], d["dirs"], d["bytes"]) == (t.files, t.dirs, t.bytes)
    assert d["verdict"] == verdict(t, ".", ["vcs", "dependency"])


def test_sc6_running_the_expand_command_shows_node_modules_entries(sc6: tuple[Lab, Path]) -> None:
    lab, root = sc6
    r = rerun(lab, "view node_modules/", cwd=root)
    d = overview_json(r)
    m = model(root / "node_modules", prefix="node_modules/")
    assert d["lines"] == m.lines
    assert d["lines"][0] == "pkg00/"  # its own entries, not one collapsed line
    assert len(d["lines"]) == SC6_PACKAGES * 4 <= BUDGET
    assert m.kinds() == ["budget"] * SC6_PACKAGES  # each lib/ (248 entries) is left unexpanded
    assert d["lines"][1] == (
        f"  lib/  {SC6_LIB} files, 0 dirs, {size(SC6_LIB * 11)}; budget"
        " — expand: view node_modules/pkg00/lib/"
    )
    check_collapsed(d, m, prefix="node_modules/")


# ── the breadth-first fit (FR-29) ─────────────────────────────────────────────────────────────


@pytest.fixture
def layered(lab: Lab) -> Path:
    """Shallow levels that fit any budget here, deep levels that do not.

    root: a/ b/ c/ + 2 files (5 lines); each X/: deep/ + 5 files (6); each X/deep: deeper/ + 30 files
    (31); each X/deep/deeper: 30 files. 5 + 18 = 23 lines for two levels, 206 for all four."""
    root = lab.ws / "tree"
    for x in "abc":
        fill(root / x, 5, stem=f"{x}")
        fill(root / x / "deep", 30, stem=f"{x}d")
        fill(root / x / "deep" / "deeper", 30, stem=f"{x}e")
    write(root / "r1.txt", b"1")
    write(root / "r2.txt", b"22")
    return root


@pytest.mark.parametrize(
    ("limit", "budgeted"),
    [
        (40, ["a/deep", "b/deep", "c/deep"]),  # 23 + 31 > 40: no deep level fits
        (60, ["a/deep/deeper", "b/deep", "c/deep"]),  # a/deep fits (54), b/deep would be 85
        (BUDGET, ["c/deep/deeper"]),  # 23 + 93 = 116; deeper: 146, 176, then 206 > 200
    ],
)
def test_deeper_levels_that_do_not_fit_are_collapsed_as_budget(
    lab: Lab, layered: Path, limit: int, budgeted: list[str]
) -> None:
    args = ["--json", "."] if limit == BUDGET else ["--json", "--limit", str(limit), "."]
    d = overview_json(view(lab, *args, cwd=layered))
    m = model(layered, budget=limit)
    assert [c["path"] for c in m.collapsed] == budgeted  # the fixture does what its comment says
    assert d["lines"] == m.lines
    assert len(d["lines"]) <= limit
    assert d["budget_lines"] == limit
    assert "truncated" not in d
    n = len(budgeted)
    assert d["verdict"] == verdict(tally(layered), ".", ["budget"] * n)
    assert d["verdict"].endswith(f"; collapsed {n} (budget {n})")
    check_collapsed(d, m)


def test_limit_0_expands_everything(lab: Lab, layered: Path) -> None:
    d = overview_json(view(lab, "--json", "--limit", "0", ".", cwd=layered))
    m = model(layered, budget=0)
    assert m.collapsed == []
    assert len(m.lines) == 206 > BUDGET
    assert d["lines"] == m.lines
    assert d["collapsed"] == [] and "truncated" not in d and "collapsed" not in d["verdict"]
    assert d["budget_lines"] == 0


def test_a_budget_collapsed_line_expands_with_its_command(lab: Lab, layered: Path) -> None:
    d = overview_json(view(lab, "--json", "--limit", "40", ".", cwd=layered))
    first = d["collapsed"][0]
    assert first["kind"] == "budget" and first["expand"] == "view a/deep/"
    e = overview_json(rerun(lab, first["expand"], cwd=layered))
    assert e["lines"] == model(layered / "a" / "deep", prefix="a/deep/").lines
    assert e["lines"][0] == "deeper/"


# ── DIR's own entries over the budget: the generic cut (FR-29, rule 3) ────────────────────────


def test_own_entries_over_the_budget_are_a_cut_whose_more_is_limit_0(lab: Lab) -> None:
    root = lab.ws / "wide"
    fill(root, 250)
    full = model(root, budget=0).lines
    assert len(full) == 250
    d = overview_json(view(lab, "--json", "wide"))
    head, tail = BUDGET // 2, BUDGET - BUDGET // 2  # rule 3's generic cut: head and tail of the body
    assert d["lines"] == full[:head] + full[-tail:]
    omitted = full[head:-tail]
    t = d["truncated"]
    assert t["omitted_lines"] == len(omitted) == 50
    assert t["omitted_bytes"] == sum(len(x.encode()) + 1 for x in omitted)
    words = shlex.split(t["more"])
    assert words[0] == "view" and "wide" in words
    assert words[words.index("--limit") + 1] == "0"
    e = overview_json(rerun(lab, t["more"]))
    assert e["lines"] == full and "truncated" not in e


def test_the_cut_in_text_ends_with_the_omission_line(lab: Lab) -> None:
    fill(lab.ws / "wide", 250)
    r = view(lab, "--text", "wide")
    assert r.returncode == 0 and r.stderr == "", said(r)
    out = text_of(r)
    assert out[0] == "view: wide [overview]"
    assert out[-1].startswith("… omitted 50 lines (") and "; more: view " in out[-1], out[-1]
    assert out[-1].endswith("--limit 0"), out[-1]


# ── a missing directory, an unreadable one (FR-31 contract) ───────────────────────────────────


def test_a_missing_directory_exits_3_with_do_instead(lab: Lab) -> None:
    d = result_outcome(view(lab, "--json", "nodir"), 3)
    assert d["verdict"] == "no such file: nodir"
    assert d["lines"][0].startswith("do instead: ")
    out = text_of(view(lab, "--text", "nodir"))
    assert out[1] == "verdict: no such file: nodir" and out[2].startswith("do instead: ")


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads a 000 directory")
def test_an_unreadable_subdirectory_is_listed_and_counted(lab: Lab) -> None:
    root = lab.ws / "proj"
    write(root / "locked" / "inside.txt", b"hidden")
    write(root / "ok.txt", b"ok")
    (root / "locked").chmod(0o000)
    try:
        d = overview_json(view(lab, "--json", ".", cwd=root))
    finally:
        (root / "locked").chmod(0o755)
    assert d["lines"] == ["locked/  unreadable", "ok.txt  2 B"]
    assert "1 unreadable" in d["verdict"], d["verdict"]
    assert "inside" not in "\n".join(d["lines"])


# ── anchors (FR-32 to FR-35, SC-7) ────────────────────────────────────────────────────────────


def raw_lines(data: bytes) -> list[bytes]:
    """The file's lines as stored, each with its line ending."""
    pieces = data.split(b"\n")
    return [p + b"\n" for p in pieces[:-1]] + ([pieces[-1]] if pieces[-1] else [])


def anchor(raw: bytes) -> str:
    """FR-33: sha256 of the raw bytes without the line ending (a trailing \\n, then a trailing \\r)."""
    if raw.endswith(b"\n"):
        raw = raw[:-1]
        if raw.endswith(b"\r"):
            raw = raw[:-1]
    return hashlib.sha256(raw).hexdigest()[:6]


def anchors_of(data: bytes) -> list[str]:
    return [anchor(x) for x in raw_lines(data)]


def anchored(
    texts: list[str],
    hashes: list[str],
    start: int,
    end: int,
    total: int,
    target: int | None = None,
    columns: int = 200,
) -> list[str]:
    """`{n:>width}{marker}{anchor} {text}`, then rule 13's cut at COLUMNS (0 = none)."""
    w = len(str(total))
    return [
        cut_line(f"{n:>{w}}{'>' if n == target else ' '}{hashes[n - 1]} {texts[n - 1]}", columns)
        for n in range(start, end + 1)
    ]


def edit_form(hashes: list[str], start: int, end: int) -> list[str]:
    return [f"{n}:{hashes[n - 1]}" for n in range(start, end + 1)]


@pytest.fixture
def big(lab: Lab) -> tuple[list[str], list[str]]:
    texts = big_texts()
    p = write_lines(lab.ws / "big.txt", texts)
    return texts, anchors_of(p.read_bytes())


def test_anchors_are_the_tests_own_sha256_prefixes(lab: Lab, big: tuple[list[str], list[str]]) -> None:
    texts, hashes = big
    assert hashes[0] == hashlib.sha256(texts[0].encode()).hexdigest()[:6]
    d = ok_json(view(lab, "--json", "--anchors", "big.txt:40-80"))
    assert d["lines"] == anchored(texts, hashes, 40, 80, 412)
    assert d["anchors"] == edit_form(hashes, 40, 80)
    assert len(d["anchors"]) == len(d["lines"])
    assert all(len(a.split(":")[1]) == 6 for a in d["anchors"])
    assert d["lines"][0] == f" 40 {hashes[39]} {texts[39]}"


def test_anchors_in_text_mode(lab: Lab) -> None:
    texts = ["def f(x):", "    return x", ""]
    p = write_lines(lab.ws / "app.py", texts)
    hashes = anchors_of(p.read_bytes())
    r = view(lab, "--text", "--anchors", "app.py")
    assert r.returncode == 0 and r.stderr == "", said(r)
    v = "lines 1-3 of 3 (whole file)"
    assert text_of(r) == ["view: app.py [lines 1-3 of 3]", f"verdict: {v}", *anchored(texts, hashes, 1, 3, 3)]


def test_the_marker_on_file_n_precedes_the_anchor(lab: Lab, big: tuple[list[str], list[str]]) -> None:
    texts, hashes = big
    d = ok_json(view(lab, "--json", "--anchors", "big.txt:40"))
    assert d["lines"] == anchored(texts, hashes, 30, 50, 412, target=40)
    assert d["lines"][10] == f" 40>{hashes[39]} {texts[39]}"
    assert d["anchors"] == edit_form(hashes, 30, 50)


def test_anchors_hash_raw_bytes_not_the_shown_text(lab: Lab) -> None:
    """A non-UTF-8 line, a line with terminal escapes and a line longer than COLUMNS: each anchor is the
    hash of the bytes as stored, so the replacement, the stripping and the cut do not move it."""
    long = "z" * 300
    data = b"caf\xff ok\n\x1b[31mred\x1b[0m text\n" + long.encode() + b"\nplain\n"
    write(lab.ws / "mixed.txt", data)
    hashes = anchors_of(data)
    assert hashes[0] == hashlib.sha256(b"caf\xff ok").hexdigest()[:6]
    assert hashes[1] == hashlib.sha256(b"\x1b[31mred\x1b[0m text").hexdigest()[:6]
    assert hashes[2] == hashlib.sha256(long.encode()).hexdigest()[:6]
    shown = ["caf� ok", "red text", long, "plain"]
    d = ok_json(view(lab, "--json", "--anchors", "mixed.txt"))
    assert d["lines"][:4] == anchored(shown, hashes, 1, 4, 4)
    assert d["anchors"] == edit_form(hashes, 1, 4)
    w = ok_json(view(lab, "--json", "--anchors", "--columns", "0", "mixed.txt"))
    assert w["lines"] == anchored(shown, hashes, 1, 4, 4, columns=0)
    assert w["anchors"] == d["anchors"]


def test_the_long_lines_command_keeps_anchors(lab: Lab) -> None:
    texts = ["short", "y" * 300, "tail"]
    p = write_lines(lab.ws / "long.txt", texts)
    hashes = anchors_of(p.read_bytes())
    d = ok_json(view(lab, "--json", "--anchors", "long.txt"))
    assert d["lines"][:3] == anchored(texts, hashes, 1, 3, 3)
    last = d["lines"][3]
    lead = "long lines cut: 1; read them whole with: "
    assert last.startswith(lead), last
    words = shlex.split(last[len(lead) :])
    assert "--anchors" in words and "long.txt:1-3" in words, words
    w = ok_json(rerun(lab, last[len(lead) :]))
    assert w["lines"] == anchored(texts, hashes, 1, 3, 3, columns=0)
    assert w["anchors"] == edit_form(hashes, 1, 3)


def test_next_and_more_keep_anchors(lab: Lab, big: tuple[list[str], list[str]]) -> None:
    texts, hashes = big
    d = ok_json(view(lab, "--json", "--anchors", "big.txt"))
    assert d["lines"] == anchored(texts, hashes, 1, 120, 412)
    assert d["next"] == d["truncated"]["more"]
    words = shlex.split(d["next"])
    assert words[0] == "view" and "--anchors" in words and "big.txt:121-240" in words, words
    n = ok_json(rerun(lab, d["next"]))
    assert n["lines"] == anchored(texts, hashes, 121, 240, 412)
    assert n["anchors"] == edit_form(hashes, 121, 240)
    out = text_of(view(lab, "--text", "--anchors", "big.txt"))
    assert out[-4] == f"more: {d['next']}"


def test_more_before_a_window_at_the_end_keeps_anchors(lab: Lab, big: tuple[list[str], list[str]]) -> None:
    _, hashes = big
    d = ok_json(view(lab, "--json", "--anchors", "big.txt:400-412"))
    assert d["next"] is None
    words = shlex.split(d["truncated"]["more"])
    assert "--anchors" in words and "big.txt:280-399" in words, words
    b = ok_json(rerun(lab, d["truncated"]["more"]))
    assert b["anchors"] == edit_form(hashes, 280, 399)


def test_anchors_are_stable_across_views(lab: Lab, big: tuple[list[str], list[str]]) -> None:
    first = ok_json(view(lab, "--json", "--anchors", "big.txt:1-50"))
    second = ok_json(view(lab, "--json", "--anchors", "big.txt:1-50"))
    assert first["anchors"] == second["anchors"]
    other = ok_json(view(lab, "--json", "--anchors", "big.txt:25"))
    assert set(other["anchors"]) <= set(first["anchors"])


def test_inserting_lines_above_keeps_each_moved_lines_anchor(lab: Lab) -> None:
    texts = [f"row {i}: value {i * 3}" for i in range(1, 31)]
    write_lines(lab.ws / "f.txt", texts)
    before = ok_json(view(lab, "--json", "--anchors", "f.txt"))["anchors"]
    write_lines(lab.ws / "f.txt", ["new 1", "new 2", "new 3", *texts])
    after = ok_json(view(lab, "--json", "--anchors", "f.txt"))["anchors"]
    assert len(after) == 33
    moved = [f"{int(a.split(':')[0]) + 3}:{a.split(':')[1]}" for a in before]
    assert after[3:] == moved
    assert after[:3] == [f"{i}:{anchor(f'new {i}'.encode())}" for i in (1, 2, 3)]


def test_changing_one_line_changes_only_its_anchor(lab: Lab) -> None:
    texts = [f"row {i}" for i in range(1, 21)]
    write_lines(lab.ws / "f.txt", texts)
    before = ok_json(view(lab, "--json", "--anchors", "f.txt"))["anchors"]
    edited = list(texts)
    edited[9] = "row 10 changed"
    write_lines(lab.ws / "f.txt", edited)
    after = ok_json(view(lab, "--json", "--anchors", "f.txt"))["anchors"]
    differ = [i for i, (a, b) in enumerate(zip(before, after, strict=True)) if a != b]
    assert differ == [9]
    assert after[9] == f"10:{anchor(b'row 10 changed')}"


def test_a_crlf_file_and_its_lf_copy_give_equal_anchors(lab: Lab) -> None:
    texts = ["alpha", "beta", "", "gamma delta"]
    write_lines(lab.ws / "lf.txt", texts)
    write_lines(lab.ws / "crlf.txt", texts, eol="\r\n")
    lf = ok_json(view(lab, "--json", "--anchors", "lf.txt"))
    crlf = ok_json(view(lab, "--json", "--anchors", "crlf.txt"))
    expected = edit_form([anchor(t.encode()) for t in texts], 1, 4)
    assert lf["anchors"] == crlf["anchors"] == expected
    assert lf["lines"] == crlf["lines"]


def test_without_anchors_the_slice_0_layout_is_unchanged(lab: Lab, big: tuple[list[str], list[str]]) -> None:
    texts, _ = big
    d = ok_json(view(lab, "--json", "big.txt:40-80"))
    assert d["lines"] == numbered(texts, 40, 80, 412)
    assert "anchors" not in d
    assert "--anchors" not in shlex.split(d["next"])


def test_anchors_on_a_directory_is_a_usage_error(lab: Lab) -> None:
    (lab.ws / "adir").mkdir()
    line = stderr_error(view(lab, "--anchors", "adir"), 2)
    assert "adir" in line, line


# ── search plurals (FR-36) ────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("files", "verdict_text"),
    [
        ({"one.txt": "needle\n"}, "1 match in 1 file (searched 1 file)"),
        ({"one.txt": "needle\nneedle\n"}, "2 matches in 1 file (searched 1 file)"),
        ({"one.txt": "needle\n", "two.txt": "other\n"}, "1 match in 1 file (searched 2 files)"),
        ({"one.txt": "needle\n", "two.txt": "needle\n"}, "2 matches in 2 files (searched 2 files)"),
    ],
    ids=["1-1-1", "2-1-1", "1-1-2", "2-2-2"],
)
def test_search_verdict_singulars_and_plurals(lab: Lab, files: dict[str, str], verdict_text: str) -> None:
    for name, text in files.items():
        write(lab.ws / name, text)
    d = ok_json(search(lab, "--json", "needle"))
    assert d["verdict"] == verdict_text
    r = search(lab, "--text", "needle")
    assert text_of(r)[1] == f"verdict: {verdict_text}"


def test_search_zero_matches_in_one_file_is_singular(lab: Lab) -> None:
    """ASSUMED (medium): FR-36's `searched 1 file` reaches the zero-match form too."""
    write(lab.ws / "one.txt", "hay\n")
    d = ok_json(search(lab, "--json", "needle"))
    assert d["verdict"] == "0 matches (searched 1 file)"
