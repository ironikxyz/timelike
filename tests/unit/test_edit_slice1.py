"""edit slice 1 (feature 008, Cycle 2) against contracts/edit-cli.md § Slice 1, spec FR-13 to FR-28 and
research R9 to R15: anchors (`--at`), the syntax check, `--skip-syntax-check`, and the checker child.

Written from the contract alone, before the tool. Every expected anchor is the test's own SHA-256 prefix of
the bytes it wrote, never one read from `view` (P005), and every byte claim is checked against a hash the
test computes, never against the tool's message (P004).

Points the contract leaves open, and how this file settles them:
- A one-line anchored edit's verdict: only its start (`edited `) and `(addressed by anchors` are asserted.
- The column of a checker's error, and the message text, are not asserted (they are the checker's); the
  line is, where the language's own parser fixes it (measured for the tree-sitter fixtures).
- The no-op (`--old` equal to `--new`) "checks nothing and says nothing" (FR-26): its verdict is slice 0's
  exactly, no child is started, and a `syntax` key, if present, is null or `not checked`.
- A dry run that would be refused: its scope is not asserted, only its exit, verdict and lines.
- The checker-failure cases run an installed copy of `edit` and `view` beside a fake `libexec/syntax-check`
  (the contract resolves the checker from `edit`'s real path). The time-limit case takes ~10 s (slow).
"""

from __future__ import annotations

import difflib
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import platform
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Any

import pytest
from conftest import TOOLS_DIR, events
from test_edit import check_untouched, file_sha, outcome, sha, shown, view_lines
from test_snapshot import said, stderr_error, text_of, write
from test_view import Lab, Proc, call, make_lab

EDIT = TOOLS_DIR / "edit"
VIEW = TOOLS_DIR / "view"
SESSION = "edit-slice1"
CONTEXT = 3
SKIP_FLAG = "skip-syntax-check"

PY_CHECKER = f"python {platform.python_version()} compile"  # the checker's interpreter is the tools' own
SH_CHECKER = "bash -n"

pytestmark = pytest.mark.skipif(not EDIT.exists(), reason="tools/bin/edit is not written yet")


def _has(module: str) -> bool:
    return importlib.util.find_spec(module) is not None


HAS_TS = _has("tree_sitter") and _has("tree_sitter_typescript")
HAS_GO = _has("tree_sitter") and _has("tree_sitter_go")
HAS_RUST = _has("tree_sitter") and _has("tree_sitter_rust")
needs_ts = pytest.mark.skipif(not HAS_TS, reason="tree_sitter_typescript is not installed here")
needs_go = pytest.mark.skipif(not HAS_GO, reason="tree_sitter_go is not installed here")
needs_rust = pytest.mark.skipif(not HAS_RUST, reason="tree_sitter_rust is not installed here")


def grammar(dist: str) -> str:
    """`tree-sitter-x V`: V is the installed grammar's version (contract § Languages and checkers)."""
    try:
        return f"{dist} {importlib.metadata.version(dist)}"
    except importlib.metadata.PackageNotFoundError:
        return f"{dist} (not installed)"


TS_CHECKER = grammar("tree-sitter-typescript")
TSX_CHECKER = f"{TS_CHECKER} (tsx)"
GO_CHECKER = grammar("tree-sitter-go")
RUST_CHECKER = grammar("tree-sitter-rust")


@pytest.fixture
def lab(tmp_path: Path) -> Lab:
    return make_lab(tmp_path, SESSION)


def edit(lab: Lab, *args: str, **kw: Any) -> Proc:
    return call(EDIT, lab, *args, **kw)


def anchor(raw: bytes) -> str:
    """view's anchor (006 FR-33): sha256 of the line without its `\\n` and one `\\r`, first 6 hex chars."""
    if raw.endswith(b"\n"):
        raw = raw[:-1]
    if raw.endswith(b"\r"):
        raw = raw[:-1]
    return hashlib.sha256(raw).hexdigest()[:6]


def anchors_of(data: bytes) -> list[str]:
    """One anchor per line, the file split on `\\n` as `view` splits it."""
    pieces = data.split(b"\n")
    raws = [p + b"\n" for p in pieces[:-1]] + ([pieces[-1]] if pieces[-1] else [])
    return [anchor(x) for x in raws]


def at(hashes: list[str], a: int, b: int | None = None) -> str:
    return f"{a}:{hashes[a - 1]}" if b is None else f"{a}:{hashes[a - 1]}..{b}:{hashes[b - 1]}"


def body_lines(d: dict[str, Any]) -> list[str]:
    """The JSON `lines` without the `do instead:` line (its place is agentio's)."""
    return [x for x in d["lines"] if not x.startswith("do instead: ")]


def anchored_view(data: bytes, start: int, end: int, marked: set[int]) -> list[str]:
    """`view --anchors`'s layout, `{n:>W}{m}{anchor} {text}`, for lines start..end (clipped)."""
    texts = view_lines(data)
    hashes = anchors_of(data)
    total = len(texts)
    w = len(str(total))
    return [
        f"{n:>{w}}{'>' if n in marked else ' '}{hashes[n - 1]} {texts[n - 1]}"
        for n in range(max(1, start), min(total, end) + 1)
    ]


def ten() -> bytes:
    return b"".join(f"line {i}: value = {i * 11}\n".encode() for i in range(1, 11))


def has_run(seq: list[str], run: list[str]) -> bool:
    """`run` occurs in `seq` as a contiguous block."""
    return any(seq[i : i + len(run)] == run for i in range(len(seq) - len(run) + 1))


# ── FR-13, FR-17: anchored edits applied ───────────────────────────────────────────────────────


def test_a_single_anchored_line_is_replaced(lab: Lab) -> None:
    before = ten()
    p = write(lab.ws / "f.txt", before)
    h = anchors_of(before)
    r = edit(lab, "--json", "f.txt", "--at", at(h, 4), "--new", "line 4: replaced")
    d = outcome(r, 0)
    expected = before.replace(b"line 4: value = 44\n", b"line 4: replaced\n")
    assert p.read_bytes() == expected
    assert d["sha256_before"] == sha(before) and d["sha256_after"] == sha(expected) == file_sha(p)
    assert d["verdict"].startswith("edited ") and "(addressed by anchors" in d["verdict"], d["verdict"]
    assert d["level"] == "anchors" and d["mapping"] is None
    assert d["anchors"] == {"start": at(h, 4), "end": at(h, 4)}
    assert d["changed"] is True


def test_an_anchored_range_is_replaced_and_shown(lab: Lab) -> None:
    before = ten()
    p = write(lab.ws / "f.txt", before)
    h = anchors_of(before)
    r = edit(lab, "--json", "f.txt", "--at", at(h, 3, 5), "--new", "X\nY")
    d = outcome(r, 0)
    lines = before.splitlines(keepends=True)
    expected = b"".join(lines[:2]) + b"X\nY\n" + b"".join(lines[5:])
    assert file_sha(p) == sha(expected)
    assert d["sha256_after"] == sha(expected)
    assert d["verdict"].startswith("edited lines 3-4 of 9 (addressed by anchors"), d["verdict"]
    assert d["verdict"].endswith("; syntax: not checked (language unknown)"), d["verdict"]
    assert d["level"] == "anchors" and d["mapping"] is None
    assert d["anchors"] == {"start": at(h, 3), "end": at(h, 5)}
    assert (d["start"], d["end"], d["total"]) == (3, 4, 9)
    assert d["lines"] == shown(expected, 3, 4)


def test_one_trailing_newline_in_new_is_dropped(lab: Lab) -> None:
    before = ten()
    p = write(lab.ws / "f.txt", before)
    h = anchors_of(before)
    outcome(edit(lab, "--json", "f.txt", "--at", at(h, 3, 5), "--new", "X\nY\n"), 0)
    lines = before.splitlines(keepends=True)
    assert p.read_bytes() == b"".join(lines[:2]) + b"X\nY\n" + b"".join(lines[5:])


def test_a_crlf_file_keeps_crlf_on_the_replaced_lines(lab: Lab) -> None:
    before = b"l1\r\nl2\r\nl3\r\nl4\r\n"
    p = write(lab.ws / "f.txt", before)
    h = anchors_of(before)
    assert h[1] == hashlib.sha256(b"l2").hexdigest()[:6]  # the anchor is taken without the CR
    d = outcome(edit(lab, "--json", "f.txt", "--at", at(h, 2, 3), "--new", "X\nY\nZ"), 0)
    expected = b"l1\r\nX\r\nY\r\nZ\r\nl4\r\n"
    assert p.read_bytes() == expected
    assert d["line_ending"] == "CRLF"


def test_an_empty_new_deletes_the_anchored_lines(lab: Lab) -> None:
    before = ten()
    p = write(lab.ws / "f.txt", before)
    h = anchors_of(before)
    d = outcome(edit(lab, "--json", "f.txt", "--at", at(h, 3, 5), "--new", ""), 0)
    lines = before.splitlines(keepends=True)
    assert p.read_bytes() == b"".join(lines[:2] + lines[5:])
    assert d["verdict"].startswith("edited at line 3 (3 lines removed)"), d["verdict"]


# ── FR-15, FR-16: stale anchors ────────────────────────────────────────────────────────────────


def test_a_changed_end_is_stale_and_names_both_anchors(lab: Lab) -> None:
    before = ten()
    h = anchors_of(before)
    now = before.replace(b"line 6: value = 66\n", b"line 6: changed\n")
    p = write(lab.ws / "f.txt", now)
    hn = anchors_of(now)
    r = edit(lab, "--json", "f.txt", "--at", at(h, 4, 6), "--new", "X")
    d = outcome(r, 3, "anchors stale")
    check_untouched(p, now)
    assert d["verdict"].startswith("anchored lines changed: "), d["verdict"]
    assert f"line 6 (anchor {h[5]}, now {hn[5]})" in d["verdict"]
    assert d["verdict"].endswith("; nothing written")
    assert d["changed"] == [{"line": 6, "expected": h[5], "now": hn[5]}]
    assert d["moved_to"] is None
    assert body_lines(d) == anchored_view(now, 1, 9, {4, 6})
    assert d["anchors_now"] == [f"{n}:{hn[n - 1]}" for n in range(1, 10)]
    assert "view --anchors" in d["remedy"] and "f.txt:4-6" in d["remedy"], d["remedy"]


def test_both_ends_changed_are_both_named(lab: Lab) -> None:
    before = ten()
    h = anchors_of(before)
    now = before.replace(b"value = 44", b"v44").replace(b"value = 66", b"v66")
    p = write(lab.ws / "f.txt", now)
    hn = anchors_of(now)
    d = outcome(edit(lab, "--json", "f.txt", "--at", at(h, 4, 6), "--new", "X"), 3, "anchors stale")
    check_untouched(p, now)
    assert f"line 4 (anchor {h[3]}, now {hn[3]})" in d["verdict"], d["verdict"]
    assert f"line 6 (anchor {h[5]}, now {hn[5]})" in d["verdict"], d["verdict"]
    assert [c["line"] for c in d["changed"]] == [4, 6]


def test_an_end_past_the_end_of_the_file_is_stale(lab: Lab) -> None:
    before = ten()
    p = write(lab.ws / "f.txt", before)
    d = outcome(edit(lab, "--json", "f.txt", "--at", "12:abcdef", "--new", "X"), 3, "anchors stale")
    check_untouched(p, before)
    assert "line 12 is past the end (10 lines)" in d["verdict"], d["verdict"]
    assert d["changed"] == [{"line": 12, "expected": "abcdef", "now": None}]
    assert d["moved_to"] is None


def test_a_pure_move_is_refused_naming_where_the_lines_went(lab: Lab) -> None:
    before = ten()
    h = anchors_of(before)
    now = b"new a\nnew b\nnew c\n" + before
    p = write(lab.ws / "f.txt", now)
    r = edit(lab, "--json", "f.txt", "--at", at(h, 5, 7), "--new", "X")
    d = outcome(r, 3, "anchors stale")
    check_untouched(p, now)
    assert d["verdict"] == "anchored lines moved: lines 5-7 are now lines 8-10; nothing written"
    assert d["moved_to"] == {"start": 8, "end": 10}
    assert f"--at 8:{h[4]}..10:{h[6]}" in d["remedy"], d["remedy"]
    assert d["remedy"].startswith(f"rerun with --at 8:{h[4]}..10:{h[6]}"), d["remedy"]
    assert "view --anchors f.txt:8-10" in d["remedy"]
    assert body_lines(d) == anchored_view(now, 5, 13, {8, 10})


def test_an_ambiguous_move_is_reported_as_changed(lab: Lab) -> None:
    before = b"a {\n}\nb {\n}\nc {\n}\n"
    h = anchors_of(before)
    now = b"x\n" + before  # line 4 (`}`) is now `b {`, and `}` occurs three times
    p = write(lab.ws / "f.txt", now)
    hn = anchors_of(now)
    d = outcome(edit(lab, "--json", "f.txt", "--at", at(h, 4), "--new", "]"), 3, "anchors stale")
    check_untouched(p, now)
    assert d["verdict"].startswith("anchored lines changed: "), d["verdict"]
    assert f"line 4 (anchor {h[3]}, now {hn[3]})" in d["verdict"]
    assert d["moved_to"] is None


def test_stale_text_mode_shows_header_and_the_anchored_lines(lab: Lab) -> None:
    before = ten()
    h = anchors_of(before)
    now = before.replace(b"value = 55", b"v55")
    p = write(lab.ws / "f.txt", now)
    r = edit(lab, "--text", "f.txt", "--at", at(h, 5), "--new", "X")
    assert r.returncode == 3 and r.stderr == "", said(r)
    check_untouched(p, now)
    out = text_of(r)
    assert out[0] == "edit: f.txt [anchors stale]"
    assert out[1].startswith("verdict: anchored lines changed: line 5 (anchor "), out[1]
    assert has_run(out, anchored_view(now, 2, 8, {5})), out
    assert any(x.startswith("do instead: ") and "view --anchors" in x for x in out), out


# ── FR-13: usage errors ────────────────────────────────────────────────────────────────────────


def test_at_with_old_is_a_usage_error(lab: Lab) -> None:
    before = ten()
    p = write(lab.ws / "f.txt", before)
    h = anchors_of(before)
    stderr_error(edit(lab, "f.txt", "--at", at(h, 2), "--old", "line 2", "--new", "x"), 2)
    check_untouched(p, before)


def test_at_without_new_is_a_usage_error(lab: Lab) -> None:
    before = ten()
    p = write(lab.ws / "f.txt", before)
    h = anchors_of(before)
    stderr_error(edit(lab, "f.txt", "--at", at(h, 2)), 2)
    check_untouched(p, before)


@pytest.mark.parametrize(
    "spec",
    ["42", "42:xyz", "5:abcdef..3:abcdef", "0:abcdef", "4:ABCDEF", "4:abcde", "4:abcdef..", "a:abcdef"],
)
def test_a_malformed_at_is_a_usage_error_naming_the_form(lab: Lab, spec: str) -> None:
    before = ten()
    p = write(lab.ws / "f.txt", before)
    line = stderr_error(edit(lab, "f.txt", "--at", spec, "--new", "x"), 2)
    assert "N:hhhhhh" in line, line
    check_untouched(p, before)


# ── FR-18 to FR-22: the syntax check, per language ─────────────────────────────────────────────

PY_SRC = b"def f(x):\n    return x\n\n\nprint(f(1))\n"
SH_SRC = b"#!/bin/bash\nif true; then\n  echo hi\nfi\necho done\n"
TS_SRC = b"function f(x: number): number {\n  return x + 1;\n}\n\nconst y = f(2);\n"
TSX_SRC = b'const a = <div className="x">hi</div>;\n\nexport default a;\n'
GO_SRC = b"package main\n\nfunc f(x int) int {\n\treturn x + 1\n}\n"
RS_SRC = b"fn f(x: i32) -> i32 {\n    x + 1\n}\n\nfn main() {}\n"

# name, source, breaking old/new, the error's line (measured with each parser), language, checker
BREAKS = [
    pytest.param("app.py", PY_SRC, "def f(x):", "def f(x)", 1, "python", PY_CHECKER, id="python"),
    pytest.param("app.sh", SH_SRC, "echo done", "echo (done", 5, "shell", SH_CHECKER, id="shell"),
    pytest.param("app.ts", TS_SRC, "f(2);", "f(2;", 5, "typescript", TS_CHECKER, id="ts", marks=needs_ts),
    pytest.param("app.tsx", TSX_SRC, "</div>;", "</div;", 1, "tsx", TSX_CHECKER, id="tsx", marks=needs_ts),
    pytest.param(
        "app.go", GO_SRC, "return x + 1", "return x + )", 4, "go", GO_CHECKER, id="go", marks=needs_go
    ),
    pytest.param("app.rs", RS_SRC, "x + 1", "x + )", 2, "rust", RUST_CHECKER, id="rust", marks=needs_rust),
]

# name, source, valid old/new, language, checker
VALID = [
    pytest.param("app.py", PY_SRC, "return x", "return x + 1", "python", PY_CHECKER, id="python"),
    pytest.param("app.sh", SH_SRC, "echo hi", "echo hello", "shell", SH_CHECKER, id="shell"),
    pytest.param("app.ts", TS_SRC, "x + 1", "x + 2", "typescript", TS_CHECKER, id="ts", marks=needs_ts),
    pytest.param("app.tsx", TSX_SRC, ">hi<", ">hello<", "tsx", TSX_CHECKER, id="tsx", marks=needs_ts),
    pytest.param("app.go", GO_SRC, "x + 1", "x + 2", "go", GO_CHECKER, id="go", marks=needs_go),
    pytest.param("app.rs", RS_SRC, "x + 1", "x + 2", "rust", RUST_CHECKER, id="rust", marks=needs_rust),
]


def check_syntax_keys(syn: dict[str, Any]) -> None:
    assert {"status", "language", "checker", "errors", "reason"} <= set(syn), syn


def check_refused(
    r: Proc, p: Path, before: bytes, name: str, line: int, language: str, checker: str, result: bytes
) -> dict[str, Any]:
    d = outcome(r, 1, "refused")
    check_untouched(p, before)
    v = d["verdict"]
    head = f"refused: the edit would make {name} fail its syntax check ({checker}): line {line}"
    assert v.startswith(head) and v[len(head)] in ",:", v
    assert v.endswith("; nothing written"), v
    syn = d["syntax"]
    check_syntax_keys(syn)
    assert syn["status"] == "refused"
    assert (syn["language"], syn["checker"]) == (language, checker)
    assert syn["errors"] and syn["errors"][0]["line"] == line, syn
    for e in syn["errors"]:
        assert isinstance(e["line"], int) and e["message"], e
        if language == "shell":
            assert e["column"] is None, e
    assert any(x.startswith(f"── syntax error 1: line {line}") for x in d["lines"]), d["lines"]
    texts = view_lines(result)
    w = len(str(len(texts)))
    assert f"{line:>{w}}> {texts[line - 1]}" in d["lines"], d["lines"]
    assert "--new" in d["remedy"], d["remedy"]
    assert SKIP_FLAG not in r.stdout + r.stderr  # T4: the refusal never suggests the skip
    return d


@pytest.mark.parametrize(("name", "src", "old", "new", "line", "language", "checker"), BREAKS)
def test_an_edit_that_breaks_the_syntax_is_refused(
    lab: Lab, name: str, src: bytes, old: str, new: str, line: int, language: str, checker: str
) -> None:
    p = write(lab.ws / name, src)
    r = edit(lab, "--json", name, "--old", old, "--new", new)
    check_refused(r, p, src, name, line, language, checker, src.replace(old.encode(), new.encode()))


@pytest.mark.parametrize(("name", "src", "old", "new", "language", "checker"), VALID)
def test_a_valid_edit_applies_with_syntax_ok(
    lab: Lab, name: str, src: bytes, old: str, new: str, language: str, checker: str
) -> None:
    p = write(lab.ws / name, src)
    d = outcome(edit(lab, "--json", name, "--old", old, "--new", new), 0)
    expected = src.replace(old.encode(), new.encode())
    assert file_sha(p) == sha(expected)
    assert d["verdict"].endswith(f"; syntax: ok ({checker})"), d["verdict"]
    syn = d["syntax"]
    check_syntax_keys(syn)
    assert (syn["status"], syn["language"], syn["checker"]) == ("ok", language, checker)
    assert syn["errors"] == [] and syn["reason"] is None
    assert "original_errors" not in syn  # the original is checked only when the result fails


def test_the_python_checker_is_the_tools_own_interpreter(lab: Lab) -> None:
    p = write(lab.ws / "app.py", PY_SRC)
    d = outcome(edit(lab, "--json", "app.py", "--old", "return x", "--new", "return 2 * x"), 0)
    assert d["syntax"]["checker"].startswith("python 3.")
    assert d["syntax"]["checker"] == PY_CHECKER
    assert file_sha(p) == sha(PY_SRC.replace(b"return x", b"return 2 * x"))


def test_an_anchored_edit_is_checked_too(lab: Lab) -> None:
    p = write(lab.ws / "app.py", PY_SRC)
    h = anchors_of(PY_SRC)
    d = outcome(edit(lab, "--json", "app.py", "--at", at(h, 1), "--new", "def f(x)"), 1, "refused")
    check_untouched(p, PY_SRC)
    assert d["syntax"]["status"] == "refused"


def test_a_refusal_in_text_mode(lab: Lab) -> None:
    p = write(lab.ws / "app.py", PY_SRC)
    r = edit(lab, "--text", "app.py", "--old", "def f(x):", "--new", "def f(x)")
    assert r.returncode == 1 and r.stderr == "", said(r)
    check_untouched(p, PY_SRC)
    out = text_of(r)
    assert out[0] == "edit: app.py [refused]"
    assert out[1].startswith(
        f"verdict: refused: the edit would make app.py fail its syntax check ({PY_CHECKER})"
    )
    assert any(x.startswith("── syntax error 1: line 1") for x in out), out
    assert any(x.startswith("do instead: ") for x in out), out
    assert SKIP_FLAG not in r.stdout


# ── FR-18, R15: language detection ─────────────────────────────────────────────────────────────

SHEBANG_PY = b"#!/usr/bin/env python3\nx = 1\nprint(x)\n"
SHEBANG_SH = b"#!/bin/bash\nx=1\necho $x\n"


@pytest.mark.parametrize(
    ("name", "src", "old", "new", "language", "checker"),
    [
        pytest.param(
            "stub.pyi", b"def f(x: int) -> int: ...\n", "x: int", "y: int", "python", PY_CHECKER, id="pyi"
        ),
        pytest.param("m.mts", TS_SRC, "x + 1", "x + 3", "typescript", TS_CHECKER, id="mts", marks=needs_ts),
        pytest.param("m.cts", TS_SRC, "x + 1", "x + 3", "typescript", TS_CHECKER, id="cts", marks=needs_ts),
        pytest.param("s.bash", SH_SRC, "echo hi", "echo ho", "shell", SH_CHECKER, id="bash"),
        pytest.param("tool", SHEBANG_PY, "x = 1", "x = 2", "python", PY_CHECKER, id="env-python3"),
        pytest.param("script", SHEBANG_SH, "x=1", "x=2", "shell", SH_CHECKER, id="bin-bash"),
        pytest.param(
            "odd.py", b"#!/bin/bash\nx = 1\n", "x = 1", "x = 2", "python", PY_CHECKER, id="ext-wins"
        ),
    ],
)
def test_the_language_is_detected_and_checked(
    lab: Lab, name: str, src: bytes, old: str, new: str, language: str, checker: str
) -> None:
    p = write(lab.ws / name, src)
    d = outcome(edit(lab, "--json", name, "--old", old, "--new", new), 0)
    assert file_sha(p) == sha(src.replace(old.encode(), new.encode()))
    assert d["verdict"].endswith(f"; syntax: ok ({checker})"), d["verdict"]
    assert (d["syntax"]["status"], d["syntax"]["language"]) == ("ok", language)


@pytest.mark.parametrize(
    ("name", "src", "old", "new"),
    [
        pytest.param("tool", SHEBANG_PY, "x = 1", "x = = 1", id="env-python3"),
        pytest.param("script", SHEBANG_SH, "x=1", "if (", id="bin-bash"),
    ],
)
def test_a_shebang_file_that_breaks_is_refused(lab: Lab, name: str, src: bytes, old: str, new: str) -> None:
    p = write(lab.ws / name, src)
    d = outcome(edit(lab, "--json", name, "--old", old, "--new", new), 1, "refused")
    check_untouched(p, src)
    assert d["syntax"]["status"] == "refused"


@pytest.mark.parametrize("name", ["notes.txt", "app.js"])
def test_an_unknown_language_is_not_checked(lab: Lab, name: str) -> None:
    before = b"function f( {\nbroken here\n"
    p = write(lab.ws / name, before)
    d = outcome(edit(lab, "--json", name, "--old", "broken here", "--new", "still ) broken"), 0)
    assert file_sha(p) == sha(before.replace(b"broken here", b"still ) broken"))
    assert d["verdict"].endswith("; syntax: not checked (language unknown)"), d["verdict"]
    syn = d["syntax"]
    check_syntax_keys(syn)
    assert syn["status"] == "not checked"
    assert syn["language"] is None and syn["checker"] is None
    assert syn["reason"] == "language unknown"


# ── FR-21, R12: an already-broken file ─────────────────────────────────────────────────────────

BROKEN_PY = b"a = 1\nb = = 2\nc = 3\nd = 4\ne = 5\n"


def test_an_edit_adding_no_error_to_a_broken_file_applies_and_says_so(lab: Lab) -> None:
    p = write(lab.ws / "f.py", BROKEN_PY)
    d = outcome(edit(lab, "--json", "f.py", "--old", "d = 4\ne = 5", "--new", "d = 40\ne = 50"), 0)
    assert file_sha(p) == sha(BROKEN_PY.replace(b"d = 4\ne = 5", b"d = 40\ne = 50"))
    assert re.search(
        r"; syntax: f\.py already failed its check before this edit \(line 2: .+\); "
        r"no new error in lines 4-5$",
        d["verdict"],
    ), d["verdict"]
    syn = d["syntax"]
    check_syntax_keys(syn)
    assert syn["status"] == "already failed"
    assert syn["original_errors"] and syn["original_errors"][0]["line"] == 2, syn


def test_an_edit_adding_a_new_error_in_its_lines_to_a_broken_file_is_refused(lab: Lab) -> None:
    p = write(lab.ws / "f.py", BROKEN_PY)
    r = edit(lab, "--json", "f.py", "--old", "a = 1", "--new", "a = 1 +")
    d = outcome(r, 1, "refused")
    check_untouched(p, BROKEN_PY)
    syn = d["syntax"]
    assert syn["status"] == "refused"
    assert [e["line"] for e in syn["errors"]] == [1], syn  # only the new error is listed
    assert d["verdict"].startswith(
        f"refused: the edit would make f.py fail its syntax check ({PY_CHECKER}): line 1"
    )
    assert SKIP_FLAG not in r.stdout + r.stderr


# ── FR-23: a dry run that would be refused ─────────────────────────────────────────────────────


def test_a_dry_run_that_would_be_refused_prints_the_diff_and_exits_1(lab: Lab) -> None:
    p = write(lab.ws / "app.py", PY_SRC)
    st = p.stat()
    r = edit(lab, "--json", "app.py", "--old", "def f(x):", "--new", "def f(x)", "--dry-run")
    assert r.returncode == 1 and r.stderr == "", said(r)
    d = json.loads(r.stdout)
    check_untouched(p, PY_SRC)
    assert p.stat().st_mtime_ns == st.st_mtime_ns
    assert d["verdict"].startswith(
        "dry run: would be refused: the edit would make app.py fail its syntax check"
    )
    assert d["verdict"].endswith("; nothing written"), d["verdict"]
    after = PY_SRC.replace(b"def f(x):", b"def f(x)").decode()
    diff = list(
        difflib.unified_diff(
            PY_SRC.decode().splitlines(), after.splitlines(), "a/app.py", "b/app.py", n=3, lineterm=""
        )
    )
    assert has_run(d["lines"], diff), d["lines"]
    first_error = next(i for i, x in enumerate(d["lines"]) if x.startswith("── syntax error 1: "))
    assert d["lines"].index(diff[0]) < first_error  # the diff, then the error sections
    assert d["syntax"]["status"] == "refused"
    assert SKIP_FLAG not in r.stdout


def test_a_valid_dry_run_carries_the_syntax_outcome(lab: Lab) -> None:
    p = write(lab.ws / "app.py", PY_SRC)
    d = outcome(edit(lab, "--json", "app.py", "--old", "return x", "--new", "return -x", "--dry-run"), 0)
    check_untouched(p, PY_SRC)
    assert f"; syntax: ok ({PY_CHECKER})" in d["verdict"], d["verdict"]
    check_syntax_keys(d["syntax"])
    assert d["syntax"]["status"] == "ok"


# ── FR-25, R14: --skip-syntax-check ────────────────────────────────────────────────────────────


def test_skip_applies_a_breaking_edit_and_says_so(lab: Lab) -> None:
    p = write(lab.ws / "app.py", PY_SRC)
    r = edit(lab, "--json", "app.py", "--old", "def f(x):", "--new", "def f(x)", "--skip-syntax-check")
    d = outcome(r, 0)
    assert file_sha(p) == sha(PY_SRC.replace(b"def f(x):", b"def f(x)"))
    assert d["verdict"].endswith("; syntax: skipped (--skip-syntax-check)"), d["verdict"]
    syn = d["syntax"]
    check_syntax_keys(syn)
    assert syn["status"] == "skipped" and syn["checker"] is None
    assert "--skip-syntax-check" in events(lab.scratch, SESSION)[-1]["args"]


@pytest.mark.parametrize("mode", ["--json", "--text"])
def test_no_refusal_names_the_skip(lab: Lab, mode: str) -> None:
    write(lab.ws / "app.py", PY_SRC)
    write(lab.ws / "app.sh", SH_SRC)
    write(lab.ws / "f.py", BROKEN_PY)
    runs = [
        edit(lab, mode, "app.py", "--old", "def f(x):", "--new", "def f(x)"),
        edit(lab, mode, "app.py", "--old", "def f(x):", "--new", "def f(x)", "--dry-run"),
        edit(lab, mode, "app.sh", "--old", "echo done", "--new", "echo (done"),
        edit(lab, mode, "f.py", "--old", "a = 1", "--new", "a = 1 +"),
    ]
    for r in runs:
        assert r.returncode == 1, said(r)
        assert SKIP_FLAG not in r.stdout + r.stderr, said(r)


# ── FR-24, R13: the checker child and its failure (fail open) ─────────────────────────────────


def install(tmp_path: Path, checker: str | None) -> Path:
    """A copy of edit and view in <tmp>/inst/bin, and the checker (a Python script) in <tmp>/inst/libexec."""
    root = tmp_path / "inst"
    (root / "bin").mkdir(parents=True)
    for tool in (EDIT, VIEW):
        shutil.copy2(tool, root / "bin" / tool.name)
    if checker is not None:
        (root / "libexec").mkdir()
        c = root / "libexec" / "syntax-check"
        c.write_text(checker)
        c.chmod(0o755)
    return root / "bin" / "edit"


def fake(body: str) -> str:
    return "import json, os, subprocess, sys, time\n" + body


def fail_open(lab: Lab, tool: Path, timeout: float = 30) -> tuple[dict[str, Any], Path, float]:
    p = write(lab.ws / "app.py", PY_SRC)
    t0 = time.monotonic()
    r = call(tool, lab, "--json", "app.py", "--old", "return x", "--new", "return x + 1", timeout=timeout)
    took = time.monotonic() - t0
    d = outcome(r, 0)
    assert file_sha(p) == sha(PY_SRC.replace(b"return x", b"return x + 1"))  # applied: fail open
    syn = d["syntax"]
    check_syntax_keys(syn)
    assert syn["status"] == "not checked" and syn["reason"], syn
    return d, p, took


def test_the_checker_protocol_argv_and_stdin(lab: Lab, tmp_path: Path) -> None:
    mark = tmp_path / "seen.json"
    tool = install(
        tmp_path,
        fake(
            "data = sys.stdin.buffer.read()\n"
            f"open({str(mark)!r}, 'w').write(json.dumps({{'argv': sys.argv[1:], 'stdin': data.hex()}}))\n"
            "print(json.dumps({'checker': 'fake checker 1.0', 'result': [], 'original': None}))\n"
        ),
    )
    p = write(lab.ws / "app.py", PY_SRC)
    d = outcome(call(tool, lab, "--json", "app.py", "--old", "return x", "--new", "return x + 1"), 0)
    result = PY_SRC.replace(b"return x", b"return x + 1")
    assert file_sha(p) == sha(result)
    assert d["verdict"].endswith("; syntax: ok (fake checker 1.0)"), d["verdict"]
    seen = json.loads(mark.read_text())
    assert seen["argv"] == ["python", str(len(result))]
    assert bytes.fromhex(seen["stdin"]) == result + PY_SRC  # the result's bytes, then the original's


@pytest.mark.parametrize(
    "args",
    [
        pytest.param(["notes.txt", "--old", "a", "--new", "b"], id="unknown-language"),
        pytest.param(["app.py", "--old", "return x", "--new", "return y", "--skip-syntax-check"], id="skip"),
        pytest.param(["app.py", "--old", "return x", "--new", "return x"], id="no-op"),
    ],
)
def test_no_child_is_started(lab: Lab, tmp_path: Path, args: list[str]) -> None:
    mark = tmp_path / "started"
    tool = install(
        tmp_path,
        fake(
            f"open({str(mark)!r}, 'w').write('x')\n"
            "print(json.dumps({'checker': 'c', 'result': [], 'original': None}))\n"
        ),
    )
    write(lab.ws / "app.py", PY_SRC)
    write(lab.ws / "notes.txt", b"a\n")
    r = call(tool, lab, "--json", *args)
    assert r.returncode == 0, said(r)
    assert not mark.exists()


def test_the_no_op_checks_nothing_and_says_nothing(lab: Lab) -> None:
    p = write(lab.ws / "app.py", PY_SRC)
    d = outcome(edit(lab, "--json", "app.py", "--old", "return x", "--new", "return x"), 0, "no change")
    check_untouched(p, PY_SRC)
    assert d["verdict"] == "no change: --old and --new are the same"
    syn = d.get("syntax")
    assert syn is None or syn.get("status") == "not checked", syn


def test_a_missing_checker_fails_open(lab: Lab, tmp_path: Path) -> None:
    d, _, _ = fail_open(lab, install(tmp_path, None))
    assert "; syntax: not checked (checker failed: checker not installed at " in d["verdict"], d["verdict"]
    assert d["syntax"]["checker"] is None


def test_a_checker_exiting_nonzero_fails_open_with_its_last_stderr_line(lab: Lab, tmp_path: Path) -> None:
    tool = install(
        tmp_path, fake("sys.stdin.buffer.read()\nsys.stderr.write('first\\nboom happened\\n')\nsys.exit(3)\n")
    )
    d, _, _ = fail_open(lab, tool)
    assert d["verdict"].endswith("; syntax: not checked (checker failed: exit 3: boom happened)"), d[
        "verdict"
    ]


def test_a_checker_printing_garbage_fails_open(lab: Lab, tmp_path: Path) -> None:
    tool = install(tmp_path, fake("sys.stdin.buffer.read()\nprint('this is { not json')\n"))
    d, _, _ = fail_open(lab, tool)
    assert d["verdict"].endswith("; syntax: not checked (checker failed: unreadable output)"), d["verdict"]


def _gone(pid: int) -> bool:
    try:
        state = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
    except (FileNotFoundError, ProcessLookupError, IndexError):
        return True
    return state in ("Z", "X")


def test_a_checker_past_the_time_limit_is_killed_with_its_group(lab: Lab, tmp_path: Path) -> None:
    # Slow: ~10 s, the contract's limit.
    pidfile = tmp_path / "grandchild.pid"
    tool = install(
        tmp_path,
        fake(
            "sys.stdin.buffer.read()\n"
            "g = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
            f"open({str(pidfile)!r}, 'w').write(str(g.pid))\n"
            "time.sleep(60)\n"
        ),
    )
    d, _, took = fail_open(lab, tool, timeout=40)
    assert d["verdict"].endswith("; syntax: not checked (checker failed: time limit 10 s)"), d["verdict"]
    assert took < 20, took
    pid = int(pidfile.read_text())
    deadline = time.monotonic() + 3
    while not _gone(pid) and time.monotonic() < deadline:
        time.sleep(0.1)
    if not _gone(pid):
        os.kill(pid, 9)
        pytest.fail(f"the checker's group outlived the limit (pid {pid})")


# ── FR-19, lore P002: nothing from PATH, BASH_ENV or PYTHONPATH ───────────────────────────────


def decoys(tmp_path: Path) -> tuple[Path, Path]:
    d = tmp_path / "decoy"
    d.mkdir()
    marker = tmp_path / "decoy-ran"
    script = f'#!/bin/sh\necho "$0" >> {marker}\nexit 0\n'
    names = ["python", "python3", f"python3.{sys.version_info.minor}", "bash", "sh"]
    for name in [*names, "bash-env"]:
        f = d / name
        f.write_text(script)
        f.chmod(0o755)
    return d, marker


def test_decoys_on_path_and_bash_env_are_never_run(lab: Lab, tmp_path: Path) -> None:
    d, marker = decoys(tmp_path)
    env = {"PATH": f"{d}:{os.environ.get('PATH', '/usr/bin:/bin')}", "BASH_ENV": str(d / "bash-env")}
    write(lab.ws / "app.py", PY_SRC)
    write(lab.ws / "app.sh", SH_SRC)
    r1 = edit(lab, "--json", "app.py", "--old", "def f(x):", "--new", "def f(x)", **env)
    r2 = edit(lab, "--json", "app.sh", "--old", "echo done", "--new", "echo (done", **env)
    for r in (r1, r2):
        assert r.returncode == 1, said(r)
        assert json.loads(r.stdout)["syntax"]["status"] == "refused"
    assert not marker.exists(), marker.read_text()


@needs_ts
def test_a_decoy_tree_sitter_on_pythonpath_is_never_imported(lab: Lab, tmp_path: Path) -> None:
    d = tmp_path / "pp"
    d.mkdir()
    marker = tmp_path / "pp-ran"
    (d / "tree_sitter.py").write_text(f"open({str(marker)!r}, 'w').write('x')\nraise ImportError('decoy')\n")
    pythonpath = f"{lab.env()['PYTHONPATH']}:{d}"
    p = write(lab.ws / "app.ts", TS_SRC)
    r = edit(lab, "--json", "app.ts", "--old", "f(2);", "--new", "f(2;", PYTHONPATH=pythonpath)
    assert r.returncode == 1, said(r)
    check_untouched(p, TS_SRC)
    assert json.loads(r.stdout)["syntax"]["status"] == "refused"
    assert not marker.exists()


# ── the checker child in process: the branches a subprocess run cannot force (T017, coverage) ─────

CHECKER = TOOLS_DIR.parent / "libexec" / "syntax-check"


def load_checker() -> Any:
    import importlib.machinery

    loader = importlib.machinery.SourceFileLoader("timelike_syntax_check", str(CHECKER))
    spec = importlib.util.spec_from_loader("timelike_syntax_check", loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def test_child_python_nul_byte_is_an_error_not_a_crash() -> None:
    errs = load_checker().python_errors(b"x = 1\x00\n")
    assert len(errs) == 1 and errs[0]["line"] == 1 and errs[0]["column"] is None


def test_child_bash_error_without_a_line_number_is_still_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    sc = load_checker()

    class Done:
        returncode, stderr = 2, b"bash: something odd\n"

    monkeypatch.setattr(sc.subprocess, "run", lambda *a, **k: Done())
    assert sc.shell_errors(b"echo\n") == [{"line": 1, "column": None, "message": "bash: something odd"}]

    class Silent:
        returncode, stderr = 2, b""

    monkeypatch.setattr(sc.subprocess, "run", lambda *a, **k: Silent())
    assert sc.shell_errors(b"echo\n")[0]["message"] == "bash -n exit 2"


def test_child_missing_bash_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    sc = load_checker()
    monkeypatch.setattr(sc.os, "access", lambda *a: False)
    with pytest.raises(sc.Unavailable, match="is not installed"):
        sc.checker("shell")


def test_child_unknown_language_and_bad_usage(capsys: pytest.CaptureFixture[str]) -> None:
    sc = load_checker()
    with pytest.raises(SystemExit, match="unknown language"):
        sc.checker("cobol")
    assert sc.main(["python"]) == 2
    assert sc.main(["python", "x"]) == 2
    assert "usage: syntax-check" in capsys.readouterr().err


def test_child_reports_an_absent_grammar_as_unavailable(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    sc = load_checker()
    import importlib

    real = importlib.import_module

    def no_tree_sitter(name: str, *a: Any) -> Any:
        if name.startswith("tree_sitter"):
            raise ImportError(name)
        return real(name, *a)

    monkeypatch.setattr(importlib, "import_module", no_tree_sitter)
    # a venv over a base interpreter: the base's site-packages is tried once, then the grammar is absent
    monkeypatch.setattr(sc.sys, "base_prefix", "/nonexistent-base")
    monkeypatch.setattr(sc.sys, "path", list(sys.path))
    monkeypatch.setattr(sc.sys, "stdin", type("I", (), {"buffer": __import__("io").BytesIO(b"x")})())
    assert sc.main(["go", "1"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out == {"unavailable": "no tree-sitter grammar for go (tree-sitter-go is not installed)"}
    assert any(p.startswith("/nonexistent-base") for p in sc.sys.path)
