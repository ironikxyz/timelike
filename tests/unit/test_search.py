"""search (feature 006, slice 0, T009) against contracts/view-search-cli.md, data-model.md § Hit,
§ Search result data and § Narrowing, spec FR-12 to FR-23, research R2 (ignore rules), R3 (binary) and
R6 (saved list).

Written from the contract alone, before the tool. Every tree is written by the test, and every expected count,
order, narrowing choice and byte figure is computed from what the test wrote (P004, P005). Ignore rules are
checked against git's gitignore(5) semantics as the test reads them, without asking git.

Long hit lines follow discovery revision 12 (contract § Long lines, both modes).
"""

from __future__ import annotations

import os
import re
import shlex
from collections import Counter
from pathlib import Path
from typing import Any

import pytest
import schema
from conftest import TOOLS_DIR, events
from test_snapshot import doc_of, said, stderr_error, text_of, write
from test_view import VIEW, Lab, Proc, call, cut_line, make_lab, ok_json, result_outcome, run_sed

SEARCH = TOOLS_DIR / "search"
SESSION = "bounded-t009"
CAP = 50
MIB16 = 16 * 1024 * 1024
LABEL_RE = re.compile(r"^── (.+) \((\d+)(?: of (\d+))?\) ──$")
HIT_RE = re.compile(r"^(\d+): (.*)$")
NARROW_RE = re.compile(r"^narrow: (.+)  \((\d+) of the (\d+)\)$")
Hit = tuple[str, int, str]  # path as printed, line, text


@pytest.fixture
def lab(tmp_path: Path) -> Lab:
    return make_lab(tmp_path, SESSION)


def search(lab: Lab, *args: str, **kw: Any) -> Proc:
    return call(SEARCH, lab, *args, **kw)


def plant(root: Path, files: dict[str, str | bytes]) -> None:
    for rel, data in files.items():
        write(root / rel, data)


def hits_in(root: Path, files: dict[str, str], needle: str, display_root: str = "") -> list[Hit]:
    """The test's own hits, in the contract's order: files by printed path (byte order), hits by line."""
    out: list[Hit] = []
    for rel in sorted(files, key=lambda p: (display_root + p).encode()):
        for i, text in enumerate(files[rel].split("\n")[: files[rel].count("\n")], 1):
            if needle in text:
                out.append((display_root + rel, i, text))
    return out


def counted(n: int, tag: str, needle: str = "needle_fn") -> str:
    """n hits, each on an even line between filler lines."""
    return "".join(f"x = {tag}{i}\n{needle}({tag}{i})\n" for i in range(n))


def groups(out: list[str]) -> list[tuple[str, int, int | None, list[str]]]:
    """File sections of text output: (path, shown, in file or None, hit lines). Other labels are skipped."""
    found: list[tuple[str, int, int | None, list[str]]] = []
    for line in out[2:]:
        m = LABEL_RE.match(line)
        if m:
            found.append((m[1], int(m[2]), int(m[3]) if m[3] else None, []))
        elif found and HIT_RE.match(line):
            found[-1][3].append(line)
    return found


def hit_paths(lab: Lab, *args: str, cwd: Path | None = None) -> set[str]:
    r = search(lab, "--text", "-m", "0", *args, cwd=cwd)
    assert r.returncode == 0, said(r)
    return {g[0] for g in groups(text_of(r))}


def expected_groups(
    hits: list[Hit], all_hits: list[Hit] | None = None
) -> list[tuple[str, int, int | None, list[str]]]:
    """Sections for the shown `hits`; a file's total comes from `all_hits` (every hit, shown or not)."""
    per = Counter(h[0] for h in (all_hits if all_hits is not None else hits))
    out: list[tuple[str, int, int | None, list[str]]] = []
    for path, line, text in hits:
        if not out or out[-1][0] != path:
            out.append((path, 0, None, []))
        out[-1][3].append(f"{line}: {text}")
    return [(p, len(ls), None, ls) if len(ls) == per[p] else (p, len(ls), per[p], ls) for p, _, _, ls in out]


def expected_narrow(hits: list[Hit]) -> tuple[str, int] | None:
    """data-model § Narrowing: below the root, the directory or file with the most hits that holds fewer
    than all of them, the shallowest on ties. None when every hit is in one file. The fixture must make
    the choice unique (asserted), since the contract names no tie-break beyond depth."""
    total = len(hits)
    cand: Counter[str] = Counter()
    for path, _, _ in hits:
        parts = path.split("/")
        for i in range(1, len(parts) + 1):
            cand["/".join(parts[:i])] += 1
    eligible = [(n, -p.count("/"), p) for p, n in cand.items() if n < total]
    if not eligible:
        return None
    eligible.sort(reverse=True)
    if len(eligible) > 1:
        assert eligible[0][:2] != eligible[1][:2], f"fixture has a narrowing tie: {eligible[:2]}"
    return eligible[0][2], eligible[0][0]


def saved_list(hits: list[Hit]) -> list[str]:
    return [f"{p}:{n}:{t}" for p, n, t in hits]


def check_narrow_runs(
    lab: Lab, line: str, *, pattern: str, flags: list[str], path: str, n: int, total: int
) -> None:
    m = NARROW_RE.match(line)
    assert m, line
    assert (int(m[2]), int(m[3])) == (n, total), line
    words = shlex.split(m[1])
    assert words[0] == "search" and words[-1] == path and pattern in words, words
    for f in flags:
        assert f in words, (f, words)
    d = ok_json(search(lab, *words[1:], "--json"))
    assert d["count"] == n < total


# ── the cap: 262 hits, 50 shown (SC-3 in miniature) ───────────────────────────────────────────

CAP_FILES = {
    "docs/guide.md": counted(30, "d"),
    "src/cli.py": counted(40, "c"),
    "src/engine/a.py": counted(50, "a"),
    "src/engine/run.py": counted(41, "r"),
    "src/engine/z.py": counted(57, "z"),
    "tests/test_x.py": counted(44, "t"),
}
CAP_IGNORED = {"app.log": counted(5, "l"), "out.gen": counted(25, "g")}


@pytest.fixture
def capped(lab: Lab) -> list[Hit]:
    plant(lab.ws, {**CAP_FILES, **CAP_IGNORED, ".gitignore": "*.log\n*.gen\n"})
    hits = hits_in(lab.ws, CAP_FILES, "needle_fn")
    assert len(hits) == 262
    return hits


def test_262_hits_show_50_with_the_cut_footer(lab: Lab, capped: list[Hit]) -> None:
    r = search(lab, "--text", "needle_fn")
    assert r.returncode == 0 and r.stderr == "", said(r)
    out = text_of(r)
    assert (
        out[1]
        == "verdict: 262 matches in 6 files; 50 shown, 212 omitted (searched 7 files; skipped 2 ignored)"
    )
    assert groups(out) == expected_groups(capped[:CAP], capped)
    assert [g[:3] for g in groups(out)] == [("docs/guide.md", 30, None), ("src/cli.py", 20, 40)]
    narrow = expected_narrow(capped)
    assert narrow == ("src", 188)
    full = re.escape(str(lab.scratch / SESSION / "search")) + r"/hits-[0-9a-f]{12}\.txt"
    m = re.match(rf"^full output: ({full})$", out[-2])
    assert m, out[-2]
    path = m[1]
    more = f"sed -n 51,262p {path}"
    omitted = sum(len(x.encode()) + 1 for x in saved_list(capped)[CAP:])
    assert out[-5] == "narrow: search needle_fn src  (188 of the 262)"
    assert out[-4:] == [
        f"more: {more}",
        "exit: 0",
        f"full output: {path}",
        f"… omitted 212 lines ({omitted} bytes) — full output: {path}; more: {more}",
    ]


def test_262_hits_in_json(lab: Lab, capped: list[Hit]) -> None:
    d = ok_json(search(lab, "--json", "needle_fn"))
    assert d["target"] == "."
    assert (d["count"], d["shown"], d["files_matched"], d["files_searched"]) == (262, 50, 6, 7)
    assert d["skipped"] == {"ignored": 2, "binary": 0, "large": 0, "unreadable": 0}
    assert (d["strict"], d["timed_out"]) == (False, False)
    assert d["pattern"] == "needle_fn"
    narrow_line = "narrow: search needle_fn src  (188 of the 262)"
    assert d["lines"] == [f"{n}: {t}" for _, n, t in capped[:CAP]] + [narrow_line]
    assert isinstance(d["narrow"], str) and d["narrow"] in narrow_line
    t = d["truncated"]
    assert t["omitted_lines"] == d["count"] - d["shown"] == 212
    assert t["omitted_bytes"] == sum(len(x.encode()) + 1 for x in saved_list(capped)[CAP:])
    assert t["more"] == f"sed -n 51,262p {t['full_output']}"


def test_the_saved_list_holds_every_hit_and_more_prints_exactly_the_omitted(
    lab: Lab, capped: list[Hit]
) -> None:
    d = ok_json(search(lab, "--json", "needle_fn"))
    saved = Path(d["truncated"]["full_output"]).read_text().splitlines()
    assert saved == saved_list(capped)
    assert run_sed(d["truncated"]["more"]) == saved_list(capped)[CAP:]


def test_the_narrow_command_runs_and_returns_fewer(lab: Lab, capped: list[Hit]) -> None:
    d = ok_json(search(lab, "--json", "needle_fn"))
    check_narrow_runs(lab, d["lines"][-1], pattern="needle_fn", flags=[], path="src", n=188, total=262)


def test_the_narrow_command_reuses_flags(lab: Lab, capped: list[Hit]) -> None:
    d = ok_json(search(lab, "--json", "-i", "NEEDLE_FN"))
    assert d["count"] == 262
    check_narrow_runs(lab, d["lines"][-1], pattern="NEEDLE_FN", flags=["-i"], path="src", n=188, total=262)


def test_m_changes_the_cap(lab: Lab, capped: list[Hit]) -> None:
    d = ok_json(search(lab, "--json", "-m", "10", "needle_fn"))
    assert (d["count"], d["shown"]) == (262, 10)
    assert d["lines"][:10] == [f"{n}: {t}" for _, n, t in capped[:10]]
    assert d["truncated"]["omitted_lines"] == 252
    assert d["truncated"]["more"] == f"sed -n 11,262p {d['truncated']['full_output']}"
    assert run_sed(d["truncated"]["more"]) == saved_list(capped)[10:]
    out = text_of(search(lab, "--text", "-m", "10", "needle_fn"))
    assert [g[:3] for g in groups(out)] == [("docs/guide.md", 10, 30)]


def test_writes_nothing_to_the_workspace(lab: Lab, capped: list[Hit]) -> None:
    before = sorted(str(p) for p in lab.ws.rglob("*"))
    search(lab, "--json", "needle_fn")
    search(lab, "--text", "needle_fn")
    assert sorted(str(p) for p in lab.ws.rglob("*")) == before


# ── narrowing choices ─────────────────────────────────────────────────────────────────────────


def test_narrowing_skips_a_directory_that_holds_every_hit(lab: Lab) -> None:
    files = {
        "pkg/engine/a.py": counted(60, "a"),
        "pkg/engine/b.py": counted(30, "b"),
        "pkg/cli.py": counted(20, "c"),
    }
    plant(lab.ws, dict(files))
    hits = hits_in(lab.ws, files, "needle_fn")
    assert expected_narrow(hits) == ("pkg/engine", 90)
    d = ok_json(search(lab, "--json", "needle_fn"))
    assert d["lines"][-1] == "narrow: search needle_fn pkg/engine  (90 of the 110)"
    check_narrow_runs(lab, d["lines"][-1], pattern="needle_fn", flags=[], path="pkg/engine", n=90, total=110)


def test_narrowing_prefers_the_shallowest_on_ties(lab: Lab) -> None:
    files = {"a/x/f.txt": counted(60, "f"), "b.txt": counted(10, "b")}
    plant(lab.ws, dict(files))
    assert expected_narrow(hits_in(lab.ws, files, "needle_fn")) == ("a", 60)
    d = ok_json(search(lab, "--json", "-m", "5", "needle_fn"))
    check_narrow_runs(lab, d["lines"][-1], pattern="needle_fn", flags=[], path="a", n=60, total=70)


def test_when_every_hit_is_in_one_file_the_narrow_line_says_so(lab: Lab) -> None:
    plant(lab.ws, {"sub/f.txt": counted(60, "f"), "other.txt": "nothing here\n"})
    d = ok_json(search(lab, "--json", "needle_fn"))
    line = "narrow: all 60 are in sub/f.txt; narrow the pattern, or view sub/f.txt:2"
    assert d["lines"][-1] == line
    assert isinstance(d["narrow"], str)
    out = text_of(search(lab, "--text", "needle_fn"))
    assert out[-5] == line


def test_no_narrow_when_nothing_was_omitted(lab: Lab) -> None:
    plant(lab.ws, {"a.txt": counted(3, "a"), "b/c.txt": counted(4, "c")})
    d = ok_json(search(lab, "--json", "needle_fn"))
    assert d["narrow"] is None and "truncated" not in d
    assert not any(x.startswith("narrow:") for x in d["lines"])
    assert (d["count"], d["shown"]) == (7, 7)


# ── grouping and order (FR-15), -m 0 (FR-16) ──────────────────────────────────────────────────

ORDER_FILES = {
    "ab.txt": "needle 1\n",
    "a/b.txt": "x\nneedle 2\n",
    "a-c.txt": "needle 3\nneedle 3b\n",
    "a/a.txt": "needle 4\nx\nneedle needle 4b\n",  # two hits on one line count once
    "a.txt": "x\nx\nneedle 5\n",
    "B.txt": "needle 6\nnope\nneedle 6b\n",
}


def test_hits_are_grouped_by_file_in_path_byte_order(lab: Lab) -> None:
    for rel in reversed(list(ORDER_FILES)):  # creation order is not the expected order
        write(lab.ws / rel, ORDER_FILES[rel])
    hits = hits_in(lab.ws, ORDER_FILES, "needle")
    assert [h[0] for h in hits][:3] == ["B.txt", "B.txt", "a-c.txt"]
    r = search(lab, "--text", "needle")
    assert r.returncode == 0, said(r)
    out = text_of(r)
    body: list[str] = []
    for path, _, _, lines in expected_groups(hits):
        body += [f"── {path} ({len(lines)}) ──", *lines]
    assert out[2:] == body
    assert out[1].startswith(f"verdict: {len(hits)} matches in 6 files (searched 6 files")
    d = ok_json(search(lab, "--json", "needle"))
    assert (d["count"], d["shown"], d["files_matched"], d["files_searched"]) == (len(hits), len(hits), 6, 6)


def test_m_0_shows_every_hit(lab: Lab) -> None:
    files = {f"d{i}/f.txt": counted(30, f"f{i}") for i in range(4)}
    plant(lab.ws, dict(files))
    hits = hits_in(lab.ws, files, "needle_fn")
    r = search(lab, "--text", "-m", "0", "needle_fn")
    assert groups(text_of(r)) == expected_groups(hits)
    d = ok_json(search(lab, "--json", "-m", "0", "needle_fn"))
    assert (d["count"], d["shown"]) == (120, 120)
    assert "truncated" not in d and d["narrow"] is None


def test_several_paths_are_one_ordered_search(lab: Lab) -> None:
    plant(lab.ws, {"src/b.txt": "needle\n", "docs/a.txt": "needle\n", "other/c.txt": "needle\n"})
    d = ok_json(search(lab, "--json", "needle", "src", "docs"))
    assert d["target"] == "src docs"
    r = search(lab, "--text", "needle", "src", "docs")
    assert [g[0] for g in groups(text_of(r))] == ["docs/a.txt", "src/b.txt"]


def test_paths_outside_the_cwd_are_printed_absolute(lab: Lab) -> None:
    write(lab.tmp / "other" / "f.txt", "needle\n")
    r = search(lab, "--text", "needle", "../other")
    assert [g[0] for g in groups(text_of(r))] == [os.path.realpath(lab.tmp / "other" / "f.txt")]


def test_the_scope_is_the_pattern_shlex_quoted(lab: Lab) -> None:
    write(lab.ws / "f.txt", "a needle fn here\n")
    d = ok_json(search(lab, "--json", "needle fn"))
    assert d["scope"] == shlex.quote("needle fn") == "'needle fn'"
    assert d["count"] == 1


# ── what is searched: ignore rules (FR-14, D-5, research R2) ──────────────────────────────────

# (id, ignore files, searched, ignored): every listed file holds "needle"; the ignore files do not.
IGNORE_CASES: list[tuple[str, dict[str, str], list[str], list[str]]] = [
    ("blank-and-comment", {".gitignore": "\n# a.txt\n   \nb.txt\n"}, ["a.txt"], ["b.txt"]),
    ("escaped-hash", {".gitignore": "\\#c.txt\n"}, ["c.txt"], ["#c.txt"]),
    ("trailing-space-trimmed", {".gitignore": "d.txt   \n"}, ["dd.txt"], ["d.txt"]),
    ("escaped-trailing-space", {".gitignore": "e.txt\\ \n"}, ["e.txt"], ["e.txt "]),
    ("negation", {".gitignore": "*.log\n!keep.log\n"}, ["keep.log", "sub/keep.log"], ["x.log", "sub/y.log"]),
    ("last-match-wins", {".gitignore": "!a.txt\n*.txt\n"}, ["c.md"], ["a.txt", "b.txt"]),
    (
        "no-reinclude-below-excluded-dir",
        {".gitignore": "build/\n!build/keep.txt\n"},
        ["src/x.txt"],
        ["build/keep.txt", "build/x.txt"],
    ),
    (
        "reinclude-when-dir-not-excluded",
        {".gitignore": "build/*\n!build/keep.txt\n"},
        ["build/keep.txt"],
        ["build/x.txt"],
    ),
    ("leading-slash-anchors", {".gitignore": "/top.txt\n"}, ["sub/top.txt"], ["top.txt"]),
    (
        "leading-slash-in-nested-file",
        {"sub/.gitignore": "/x.txt\n"},
        ["x.txt", "sub/deeper/x.txt"],
        ["sub/x.txt"],
    ),
    ("middle-slash-anchors", {".gitignore": "doc/frotz\n"}, ["a/doc/frotz"], ["doc/frotz"]),
    (
        "no-slash-any-depth",
        {".gitignore": "frotz\n"},
        ["frotzz", "a/xfrotz"],
        ["frotz", "a/frotz", "a/b/frotz", "c/frotz/f.txt"],
    ),
    ("trailing-slash-dirs-only", {".gitignore": "logs/\n"}, ["other/logs"], ["logs/a.txt", "sub/logs/b.txt"]),
    ("star-does-not-cross-slash", {".gitignore": "src/*.py\n"}, ["src/sub/b.py", "a.py"], ["src/a.py"]),
    (
        "question-does-not-cross-slash",
        {".gitignore": "x/a?b.txt\n"},
        ["x/a/b.txt", "x/ab.txt"],
        ["x/aab.txt"],
    ),
    (
        "leading-double-star",
        {".gitignore": "**/foo/bar\n"},
        ["bar", "a/bar", "foo/baz"],
        ["foo/bar", "a/foo/bar", "a/b/foo/bar"],
    ),
    (
        "trailing-double-star",
        {".gitignore": "abc/**\n"},
        ["xabc/x.txt", "sub/abc/z.txt"],
        ["abc/x.txt", "abc/d/y.txt"],
    ),
    ("middle-double-star", {".gitignore": "a/**/b\n"}, ["a/bc", "c/a/b"], ["a/b", "a/x/b", "a/x/y/b"]),
    ("class", {".gitignore": "f[0-9].txt\n"}, ["fa.txt", "f10.txt"], ["f1.txt", "sub/f7.txt"]),
    ("negated-class", {".gitignore": "g[!0-9].txt\n"}, ["g1.txt"], ["ga.txt"]),
    (
        "nested-file-own-subtree",
        {"sub/.gitignore": "*.tmp\n"},
        ["c.tmp", "other/d.tmp"],
        ["sub/a.tmp", "sub/d/b.tmp"],
    ),
    (
        "nested-file-overrides-parent",
        {".gitignore": "*.tmp\n", "sub/.gitignore": "!keep.tmp\n"},
        ["sub/keep.tmp"],
        ["a.tmp", "sub/b.tmp"],
    ),
]


@pytest.mark.parametrize(
    ("ignores", "searched", "ignored"), [c[1:] for c in IGNORE_CASES], ids=[c[0] for c in IGNORE_CASES]
)
def test_ignore_rules(lab: Lab, ignores: dict[str, str], searched: list[str], ignored: list[str]) -> None:
    plant(lab.ws, {**ignores, **{p: "needle\n" for p in searched + ignored}})
    assert hit_paths(lab, "needle") == set(searched)


@pytest.mark.parametrize(
    ("ignores", "searched", "ignored"), [c[1:] for c in IGNORE_CASES], ids=[c[0] for c in IGNORE_CASES]
)
def test_no_ignore_searches_everything(
    lab: Lab, ignores: dict[str, str], searched: list[str], ignored: list[str]
) -> None:
    plant(lab.ws, {**ignores, **{p: "needle\n" for p in searched + ignored}})
    assert hit_paths(lab, "--no-ignore", "needle") == set(searched + ignored)


def test_ignored_files_are_counted(lab: Lab) -> None:
    plant(lab.ws, {".gitignore": "*.log\n", "a.log": "needle\n", "b.log": "needle\n", "c.txt": "needle\n"})
    d = ok_json(search(lab, "--json", "needle"))
    assert d["skipped"]["ignored"] == 2 and d["count"] == 1
    assert d["files_searched"] == 2  # c.txt and .gitignore: hidden files are searched


def test_an_ignored_directory_counts_as_skipped(lab: Lab) -> None:
    plant(
        lab.ws,
        {".gitignore": "build/\n", "build/a.txt": "needle\n", "build/b.txt": "needle\n", "c.txt": "needle\n"},
    )
    d = ok_json(search(lab, "--json", "needle"))
    assert d["count"] == 1 and d["skipped"]["ignored"] >= 1


def make_repo_dir(ws: Path) -> None:
    """A repository as the tool finds one (the nearest ancestor with a `.git` directory, by lstat)."""
    plant(
        ws,
        {
            ".git/info/exclude": "# git's own comment\n*.bak\n/sub/hidden.txt\n",
            ".git/HEAD": "ref: refs/heads/needle\n",
            ".git/objects/needle.txt": "needle\n",
            "sub/hidden.txt": "needle\n",
            "sub/a.bak": "needle\n",
            "sub/ok.txt": "needle\n",
            "hidden.txt": "needle\n",
        },
    )


def test_info_exclude_of_the_enclosing_repository(lab: Lab) -> None:
    make_repo_dir(lab.ws)
    assert hit_paths(lab, "needle") == {"sub/ok.txt", "hidden.txt"}
    assert hit_paths(lab, "needle", cwd=lab.ws / "sub") == {"ok.txt"}  # the repo is above the search root


def test_no_ignore_turns_off_info_exclude_but_never_enters_git(lab: Lab) -> None:
    make_repo_dir(lab.ws)
    assert hit_paths(lab, "--no-ignore", "needle") == {
        "sub/ok.txt",
        "sub/hidden.txt",
        "sub/a.bak",
        "hidden.txt",
    }


@pytest.mark.parametrize("flags", [[], ["--no-ignore"]])
def test_git_directories_are_never_entered(lab: Lab, flags: list[str]) -> None:
    plant(
        lab.ws,
        {
            ".git/config": "needle\n",
            "vendor/inner/.git/objects/x": "needle\n",
            "vendor/inner/lib.txt": "needle\n",
        },
    )
    assert hit_paths(lab, *flags, "needle") == {"vendor/inner/lib.txt"}


@pytest.mark.parametrize("flags", [[], ["--no-ignore"]])
def test_symlinks_met_during_the_walk_are_not_followed(lab: Lab, flags: list[str]) -> None:
    write(lab.ws / "real" / "a.txt", "needle\n")
    write(lab.tmp / "outside" / "o.txt", "needle\n")
    os.symlink("real", lab.ws / "link-dir")
    os.symlink("real/a.txt", lab.ws / "link-file")
    os.symlink(str(lab.tmp / "outside"), lab.ws / "link-out")
    assert hit_paths(lab, *flags, "needle") == {"real/a.txt"}


def test_hidden_files_are_searched(lab: Lab) -> None:
    plant(lab.ws, {".hidden.txt": "needle\n", ".config/x.txt": "needle\n", "v.txt": "needle\n"})
    assert hit_paths(lab, "needle") == {".hidden.txt", ".config/x.txt", "v.txt"}


def test_a_path_that_is_a_file_is_searched_whatever_the_ignore_rules(lab: Lab) -> None:
    plant(lab.ws, {".gitignore": "*.log\n", "x.log": "a\nneedle\n"})
    d = ok_json(search(lab, "--json", "needle", "x.log"))
    assert (d["count"], d["files_searched"]) == (1, 1)
    assert d["target"] == "x.log"
    assert hit_paths(lab, "needle", "x.log") == {"x.log"}


# ── skipped and counted: binary, large, unreadable ────────────────────────────────────────────


def test_binary_files_are_skipped_and_counted(lab: Lab) -> None:
    plant(lab.ws, {"t.txt": "needle\n", "b.bin": b"needle\n\x00\x00\x01"})
    d = ok_json(search(lab, "--json", "needle"))
    assert d["count"] == 1 and d["skipped"]["binary"] == 1
    assert hit_paths(lab, "needle") == {"t.txt"}


def sparse(p: Path, size: int) -> None:
    """Text for the first 8 KiB and more (so it is not binary by R3), then a sparse tail to `size`."""
    write(p, "needle in a large file\n" + "filler line\n" * 800)
    os.truncate(p, size)


def test_a_file_over_16_mib_is_skipped_and_counted(lab: Lab) -> None:
    sparse(lab.ws / "huge.dat", MIB16 + 1)
    write(lab.ws / "t.txt", "needle\n")
    d = ok_json(search(lab, "--json", "needle"))
    assert d["skipped"]["large"] == 1 and d["skipped"]["binary"] == 0
    assert d["count"] == 1


def test_a_file_of_exactly_16_mib_is_searched(lab: Lab) -> None:
    sparse(lab.ws / "edge.dat", MIB16)
    d = ok_json(search(lab, "--json", "needle"))
    assert d["skipped"]["large"] == 0 and d["count"] == 1


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads a 000 file")
def test_an_unreadable_file_is_skipped_and_counted(lab: Lab) -> None:
    write(lab.ws / "locked.txt", "needle\n", 0o000)
    write(lab.ws / "t.txt", "needle\n")
    d = ok_json(search(lab, "--json", "needle"))
    assert d["skipped"]["unreadable"] == 1 and d["count"] == 1


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads a 000 directory")
def test_an_unreadable_root_is_a_failure_not_a_no_match(lab: Lab) -> None:
    locked = lab.ws / "locked"
    write(locked / "f.txt", "needle\n")
    locked.chmod(0o000)
    try:
        r = search(lab, "--json", "needle", "locked")
    finally:
        locked.chmod(0o755)
    assert r.returncode == 1, said(r)
    assert "no match (strict)" not in r.stdout + r.stderr


# ── zero and strict (FR-18, SC-4) ─────────────────────────────────────────────────────────────


def test_zero_matches_exits_0_with_count_0(lab: Lab) -> None:
    plant(lab.ws, {"a.txt": "nothing\n", "b.txt": "here\n"})
    d = ok_json(search(lab, "--json", "no_such_symbol"))
    assert d["count"] == 0 and d["lines"] == [] and "truncated" not in d
    assert d["verdict"].startswith("0 matches (searched 2 files"), d["verdict"]
    assert d["strict"] is False


def test_strict_zero_matches_exits_1_as_a_result(lab: Lab) -> None:
    plant(lab.ws, {"a.txt": "nothing\n", "b.txt": "here\n"})
    d = result_outcome(search(lab, "--json", "--strict", "no_such_symbol"), 1)
    assert d["verdict"].startswith("no match (strict): 0 matches (searched 2 files"), d["verdict"]
    assert d["remedy"] == "drop --strict to treat no match as a result"
    assert d["lines"][0] == "do instead: drop --strict to treat no match as a result"
    assert d["count"] == 0 and d["strict"] is True


def test_strict_with_matches_exits_0(lab: Lab) -> None:
    write(lab.ws / "a.txt", "needle\n")
    d = ok_json(search(lab, "--json", "--strict", "needle"))
    assert d["count"] == 1 and d["strict"] is True


# ── the pattern (FR-13) ───────────────────────────────────────────────────────────────────────


def test_case_sensitive_by_default_and_i_ignores_case(lab: Lab) -> None:
    write(lab.ws / "a.txt", "Needle\nneedle\nNEEDLE\nother\n")
    assert ok_json(search(lab, "--json", "needle"))["count"] == 1
    assert ok_json(search(lab, "--json", "-i", "needle"))["count"] == 3


def test_patterns_are_extended_regular_expressions(lab: Lab) -> None:
    write(lab.ws / "a.txt", "def parse_args(argv):\ndef run():\nx = parse_args\n")
    d = ok_json(search(lab, "--json", r"def [a-z_]+\("))
    assert d["count"] == 2


METAS = "a.b*(c)[d]+?{2}"


def test_f_takes_the_pattern_as_a_fixed_string(lab: Lab) -> None:
    write(lab.ws / "a.txt", f"price {METAS} here\naXbbb(c)d\nabcd\n")
    d = ok_json(search(lab, "--json", "-F", METAS))
    assert d["count"] == 1
    assert d["lines"] == [f"1: price {METAS} here"]


def test_the_same_metacharacters_without_f_are_a_bad_pattern(lab: Lab) -> None:
    write(lab.ws / "a.txt", f"price {METAS} here\n")
    stderr_error(search(lab, METAS), 2)


def test_a_pattern_that_does_not_compile_is_usage_naming_the_position(lab: Lab) -> None:
    write(lab.ws / "a.txt", "foo\n")
    line = stderr_error(search(lab, "foo("), 2)
    assert "position 3" in line, line


def test_a_bad_flag_is_usage(lab: Lab) -> None:
    stderr_error(search(lab, "--no-such-flag", "x"), 2)


def test_a_missing_path_exits_3_as_a_result(lab: Lab) -> None:
    d = result_outcome(search(lab, "--json", "needle", "nope"), 3)
    assert d["verdict"] == "no such path: nope"


# ── FR-19: the time limit ─────────────────────────────────────────────────────────────────────


def test_the_time_limit_exits_124_with_a_verdict(lab: Lab) -> None:
    """--timeout 0.001 over 3000 files: the walk alone outlasts a millisecond. 0 is not used because the
    contract gives `0` the meaning "none" for --limit and -m, and says nothing about it for --timeout."""
    for k in range(30):
        for f in range(100):
            write(lab.ws / f"d{k:02d}" / f"f{f:03d}.txt", f"needle {k} {f}\n")
    r = search(lab, "--json", "--timeout", "0.001", "needle", timeout=60)
    assert r.returncode == 124, said(r)
    d = doc_of(r)
    m = re.match(
        r"^time limit \S+ s reached: searched (\d+) files, (\d+) matches so far; not reached: (.+)$",
        d["verdict"],
    )
    assert m, d["verdict"]
    assert d["timed_out"] is True and d["exit"] == 124
    assert (d["files_searched"], d["count"]) == (int(m[1]), int(m[2]))
    assert d["not_reached"] == m[3]
    assert int(m[1]) < 3000
    assert d["shown"] <= CAP
    assert (lab.ws / m[3]).exists(), m[3]


# ── FR-7 (discovery revision 12): long hit lines ──────────────────────────────────────────────


def test_a_long_hit_is_cut_and_named_with_a_view_command(lab: Lab) -> None:
    long = "needle " + "y" * 300 + "é"
    write(lab.ws / "long.txt", f"short\n{long}\nneedle short\n")
    d = ok_json(search(lab, "--json", "needle"))
    hit = f"2: {long}"
    i = d["lines"].index(cut_line(hit, 200))
    assert d["cut_lines"] == [{"index": i, "cut_bytes": len(hit[200:].encode())}]
    note = "long lines cut: 1; read one whole with: view long.txt:2 --columns 0"
    assert d["lines"][-1] == note
    out = text_of(search(lab, "--text", "needle"))
    assert out[-1] == note and cut_line(hit, 200) in out
    words = shlex.split(note.split("read one whole with: ", 1)[1])
    assert words[0] == "view"
    v = ok_json(call(VIEW, lab, "--json", *words[1:]))
    assert "cut_lines" not in v
    assert f"2> {long}" in v["lines"]


def test_the_long_lines_line_comes_before_narrow_and_the_saved_list_is_whole(lab: Lab) -> None:
    long = "needle " + "z" * 300
    plant(lab.ws, {"a.txt": f"{long}\n", "b/c.txt": "needle 1\nneedle 2\n"})
    out = text_of(search(lab, "--text", "-m", "1", "needle"))
    assert out[-6] == "long lines cut: 1; read one whole with: view a.txt:1 --columns 0"
    assert NARROW_RE.match(out[-5]), out[-5]
    d = ok_json(search(lab, "--json", "-m", "1", "needle"))
    assert Path(d["truncated"]["full_output"]).read_text().splitlines() == [
        f"a.txt:1:{long}",
        "b/c.txt:1:needle 1",
        "b/c.txt:2:needle 2",
    ]


# ── FR-21: the contract ───────────────────────────────────────────────────────────────────────


def test_manifest(lab: Lab) -> None:
    r = search(lab, "--agent-info")
    assert r.returncode == 0, said(r)
    info = doc_of(r)
    assert schema.errors(info, schema.load("agent-info.schema.json")) == []
    assert info["tool"] == "search"
    assert (info["mutating"], info["destructive"]) == (False, False)
    assert info["probe"] == ["-m", "1", "ID", "/etc/os-release"]
    assert set(info["exit_codes"]) == {"0", "1", "2", "3", "124"}
    assert "strict" in info["exit_codes"]["1"]
    assert info["envelopes"] == []


def test_the_probe_runs(lab: Lab) -> None:
    d = ok_json(search(lab, "--json", "-m", "1", "ID", "/etc/os-release"))
    assert d["count"] >= 1 and d["shown"] == 1


def test_help_is_within_40_lines(lab: Lab) -> None:
    r = search(lab, "--help")
    assert r.returncode == 0
    lines = r.stdout.splitlines()
    assert 0 < len(lines) <= 40 and lines[0].startswith("search: ")


def test_one_event_per_invocation(lab: Lab) -> None:
    write(lab.ws / "a.txt", "needle\n")
    expected: list[int] = []
    for args in (
        ["--json", "needle"],
        ["--text", "nothing_here"],
        ["--json", "--strict", "nothing_here"],
        ["--json", "needle", "nope"],
        ["foo("],
        ["--no-such-flag", "x"],
    ):
        r = search(lab, *args)
        expected.append(r.returncode)
        assert len(events(lab.scratch, SESSION)) == len(expected), args
    assert expected == [0, 0, 1, 3, 2, 2]
    evs = events(lab.scratch, SESSION)
    assert [e["exit"] for e in evs] == expected
    event_schema = schema.load("event.schema.json")
    for ev in evs:
        assert (ev["tool"], ev["session"]) == ("search", SESSION)
        assert schema.errors(ev, event_schema) == []
