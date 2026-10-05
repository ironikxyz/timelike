"""edit (feature 008, slice 0, T004) against contracts/edit-cli.md, spec FR-1 to FR-12, data-model.md and
research R2 to R5, R7 and R8.

Written from the contract alone, before the tool. The tool runs as a real subprocess (test_view's lab: a
workspace under tmp_path, HOME a sibling of it, the scratch root outside both). Every byte claim is checked
against the file's own bytes or a SHA-256 the test computes, never against the tool's message (P004), and
every expected file is built by the test from the bytes it wrote, never by `edit` (P005).

Points the contract leaves open, and how this file settles them:
- The edited outcome's `scope` (`lines S-E of T`): the contract's two examples disagree on S-E (the edited
  example's header names neither the edited lines nor the region shown), so only its shape and T are
  asserted.
- A one-line edit's verdict (`edited lines 4-4` or `edited line 4`): verdicts are asserted exactly only on
  edits of two or more lines.
- Similarity is compared with the test's own `SequenceMatcher` ratio on the `\\n`-joined lines, within 0.01
  (the tool may round).
- `searched_lines` on a search that was not time-limited is read as the file's line count.
- Not tested: a file changed between the read and the write (the contract gives no hook to force it), the
  5 s deadline itself (only the fields' shape), and an owner that cannot be kept (it needs a second uid).
"""

from __future__ import annotations

import difflib
import hashlib
import itertools
import os
import re
import stat
from pathlib import Path
from typing import Any

import pytest
import schema
from conftest import TOOLS_DIR, events
from test_snapshot import doc_of, human, said, stderr_error, text_of, write
from test_view import Lab, Proc, call, make_lab

EDIT = TOOLS_DIR / "edit"
SESSION = "edit-t004"
CONTEXT = 3
LEVEL_PHRASE = {
    "exact": "matched exactly",
    "line_endings": "matched ignoring line endings",
}

pytestmark = pytest.mark.skipif(not EDIT.exists(), reason="tools/bin/edit is not written yet")


@pytest.fixture
def lab(tmp_path: Path) -> Lab:
    return make_lab(tmp_path, SESSION)


def edit(lab: Lab, *args: str, **kw: Any) -> Proc:
    return call(EDIT, lab, *args, **kw)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha(p: Path) -> str:
    return sha(p.read_bytes())


def outcome(r: Proc, code: int, scope: str | None = None) -> dict[str, Any]:
    """A result (not a usage error): the JSON object on stdout with the rule-12 keys first, nothing on
    stderr, and the exit code in the object and the process."""
    assert r.returncode == code, said(r)
    assert r.stderr == "", r.stderr
    d = doc_of(r)
    assert list(d)[:3] == ["tool", "target", "scope"], d
    assert d["tool"] == "edit"
    assert d["exit"] == code
    if scope is not None:
        assert d["scope"] == scope, d
    return d


def view_lines(raw: bytes) -> list[str]:
    """The file's lines as `view` shows them: split after each CRLF, LF or lone CR, endings not shown."""
    text = raw.decode("utf-8", errors="replace")  # a BOM shows, as `view` shows it
    return re.split(r"\r\n|\n|\r", text.removesuffix("\r\n").removesuffix("\n").removesuffix("\r"))


def numbered(texts: list[str], start: int, end: int, total: int, marked: range | None = None) -> list[str]:
    """`{n:>W}{m} {text}`, W = len(str(total)), m `>` on the marked lines and a space otherwise."""
    w = len(str(total))
    marked = marked or range(0)
    return [f"{n:>{w}}{'>' if n in marked else ' '} {texts[n - 1]}" for n in range(start, end + 1)]


def shown(after: bytes, start: int, end: int) -> list[str]:
    """The edited outcome's `lines`: the new text's lines marked, 3 lines of context each side, clipped."""
    texts = view_lines(after)
    total = len(texts)
    return numbered(texts, max(1, start - CONTEXT), min(total, end + CONTEXT), total, range(start, end + 1))


def check_edited(
    lab: Lab,
    r: Proc,
    p: Path,
    before: bytes,
    expected: bytes,
    *,
    level: str,
    start: int,
    end: int,
    endings_changed: bool = False,
) -> dict[str, Any]:
    """The edited outcome (exit 0), with the file's bytes compared against the test's own expectation."""
    d = outcome(r, 0)
    assert p.read_bytes() == expected, (p.read_bytes(), expected)
    total = len(view_lines(expected))
    assert re.fullmatch(rf"lines \d+-\d+ of {total}", d["scope"]), d["scope"]
    assert d["level"] == level
    assert (d["start"], d["end"], d["total"]) == (start, end, total)
    assert d["changed"] is True
    assert d["sha256_before"] == sha(before)
    assert d["sha256_after"] == sha(expected) == file_sha(p)
    assert d["lines"] == shown(expected, start, end)
    assert d["verdict"].startswith("edited ")
    if level != "indentation":
        assert d["mapping"] is None
        assert f"({LEVEL_PHRASE[level]})" in d["verdict"]
    if end > start:
        assert d["verdict"].startswith(f"edited lines {start}-{end} of {total} (")
    # A change of line endings in the region is never silent (contract § Verdict additions); it can happen
    # only at level 1, where --new is inserted as given.
    if endings_changed:
        assert re.search(r"; line endings: .+ → .+", d["verdict"]), d["verdict"]
    else:
        assert "line endings:" not in d["verdict"], d["verdict"]
    leftovers = [x.name for x in p.parent.iterdir() if ".edit-" in x.name]
    assert leftovers == [], leftovers  # the temp file beside the target is gone (R5)
    return d


def check_untouched(p: Path, before: bytes) -> None:
    assert file_sha(p) == sha(before)
    leftovers = [x.name for x in p.parent.iterdir() if ".edit-" in x.name]
    assert leftovers == [], leftovers


def ten_lines() -> list[str]:
    return [f"line {i}: value = {i * 11}" for i in range(1, 11)]


# ── SC-1, FR-3 level 1: an exact, unique match ────────────────────────────────────────────────


def test_exact_unique_match_replaces_only_that_text(lab: Lab) -> None:
    texts = ten_lines()
    before = ("\n".join(texts) + "\n").encode()
    p = write(lab.ws / "app.py", before)
    old = f"{texts[4]}\n{texts[5]}"
    new = "line 5: replaced\nline 6: replaced"
    r = edit(lab, "--json", "app.py", "--old", old, "--new", new)
    expected = before.replace(old.encode(), new.encode())
    d = check_edited(lab, r, p, before, expected, level="exact", start=5, end=6)
    assert d["verdict"] == "edited lines 5-6 of 10 (matched exactly)"
    assert (d["match_start"], d["match_end"]) == (5, 6)
    assert d["target"] == "app.py" and d["path"] == "app.py"
    assert d["abs_path"] == os.path.realpath(p)
    assert d["line_ending"] == "LF"


def test_text_mode_shows_header_verdict_and_numbered_region(lab: Lab) -> None:
    texts = ten_lines()
    before = ("\n".join(texts) + "\n").encode()
    p = write(lab.ws / "app.py", before)
    old = f"{texts[4]}\n{texts[5]}"
    new = "line 5: replaced\nline 6: replaced"
    r = edit(lab, "--text", "app.py", "--old", old, "--new", new)
    assert r.returncode == 0 and r.stderr == "", said(r)
    expected = before.replace(old.encode(), new.encode())
    assert p.read_bytes() == expected
    out = text_of(r)
    assert re.fullmatch(r"edit: app\.py \[lines \d+-\d+ of 10\]", out[0]), out[0]
    assert out[1] == "verdict: edited lines 5-6 of 10 (matched exactly)"
    assert out[2:] == numbered(view_lines(expected), 2, 9, 10, range(5, 7))


def test_a_fragment_within_a_line_matches_exactly(lab: Lab) -> None:
    before = b"def f(x):\n    return x\n\nprint(f(1))\n"
    p = write(lab.ws / "f.py", before)
    r = edit(lab, "--json", "f.py", "--old", "return x", "--new", "return x + 1")
    expected = b"def f(x):\n    return x + 1\n\nprint(f(1))\n"
    check_edited(lab, r, p, before, expected, level="exact", start=2, end=2)


def test_removing_whole_lines_names_the_line_it_collapsed_to(lab: Lab) -> None:
    before = b"a\nb\nc\nd\n"
    p = write(lab.ws / "f.txt", before)
    r = edit(lab, "--json", "f.txt", "--old", "b\nc\n", "--new", "")
    d = outcome(r, 0)
    assert p.read_bytes() == b"a\nd\n"
    assert re.match(r"^edited at line \d+ \(2 lines removed\)", d["verdict"]), d["verdict"]


# ── FR-4: unique at the deciding level ────────────────────────────────────────────────────────


def test_several_exact_matches_are_refused_with_every_line(lab: Lab) -> None:
    texts = [f"x{i} = 0" for i in range(1, 10)]
    texts[1] = texts[4] = texts[7] = "retry()"
    before = ("\n".join(texts) + "\n").encode()
    p = write(lab.ws / "app.py", before)
    r = edit(lab, "--json", "app.py", "--old", "retry()", "--new", "retry(3)")
    d = outcome(r, 3, "ambiguous")
    check_untouched(p, before)
    assert d["level"] == "exact"
    assert [(m["start"], m["end"]) for m in d["matches"]] == [(2, 2), (5, 5), (8, 8)]
    assert d["verdict"] == ("--old matches 3 times (matched exactly), at lines 2, 5, 8; nothing written")
    assert "context" in d["remedy"] and "view app.py:2" in d["remedy"]


def test_ambiguous_text_mode_carries_do_instead(lab: Lab) -> None:
    before = b"go()\nstop()\ngo()\n"
    p = write(lab.ws / "app.py", before)
    r = edit(lab, "--text", "app.py", "--old", "go()", "--new", "run()")
    assert r.returncode == 3 and r.stderr == "", said(r)
    check_untouched(p, before)
    out = text_of(r)
    assert out[0] == "edit: app.py [ambiguous]"
    assert out[1] == "verdict: --old matches 2 times (matched exactly), at lines 1, 3; nothing written"
    assert any(x.startswith("do instead: ") and "view app.py:1" in x for x in out[2:]), out


def test_an_exact_match_is_not_made_ambiguous_by_an_indentation_twin(lab: Lab) -> None:
    before = b"if a:\n\tfoo()\nif b:\n    foo()\n"
    p = write(lab.ws / "f.py", before)
    r = edit(lab, "--json", "f.py", "--old", "    foo()", "--new", "    bar()")
    expected = b"if a:\n\tfoo()\nif b:\n    bar()\n"
    check_edited(lab, r, p, before, expected, level="exact", start=4, end=4)


def test_a_line_endings_match_is_not_made_ambiguous_by_an_indentation_twin(lab: Lab) -> None:
    before = b"if a:\r\n    go()\r\nif a:\r\n\tgo()\r\n"
    p = write(lab.ws / "f.py", before)
    r = edit(lab, "--json", "f.py", "--old", "if a:\n    go()", "--new", "if a:\n    stop()")
    expected = b"if a:\r\n    stop()\r\nif a:\r\n\tgo()\r\n"
    d = check_edited(lab, r, p, before, expected, level="line_endings", start=1, end=2)
    assert d["line_ending"] == "CRLF"


def test_two_indentation_matches_are_ambiguous_at_level_3(lab: Lab) -> None:
    before = b"def f():\n\tgo()\n\tx = 1\n\tgo()\n"
    p = write(lab.ws / "f.py", before)
    r = edit(lab, "--json", "f.py", "--old", "    go()", "--new", "    run()")
    d = outcome(r, 3, "ambiguous")
    check_untouched(p, before)
    assert d["level"] == "indentation"
    assert [(m["start"], m["end"]) for m in d["matches"]] == [(2, 2), (4, 4)]


# ── FR-3 level 2 and FR-6: line endings ───────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("eol", "name"),
    [(b"\r\n", "CRLF"), (b"\r", "CR")],
)
def test_level_2_gives_the_new_text_the_regions_ending(lab: Lab, eol: bytes, name: str) -> None:
    before = eol.join([b"one", b"two", b"three", b""])
    p = write(lab.ws / "f.txt", before)
    r = edit(lab, "--json", "f.txt", "--old", "one\ntwo", "--new", "uno\ndos\ntres")
    expected = eol.join([b"uno", b"dos", b"tres", b"three", b""])
    d = check_edited(lab, r, p, before, expected, level="line_endings", start=1, end=3)
    assert d["verdict"] == "edited lines 1-3 of 4 (matched ignoring line endings)"
    assert d["line_ending"] == name
    assert (d["match_start"], d["match_end"]) == (1, 2)


def test_level_2_takes_the_ending_of_the_regions_first_line(lab: Lab) -> None:
    before = b"a\r\nb\nc\r\n"
    p = write(lab.ws / "f.txt", before)
    r = edit(lab, "--json", "f.txt", "--old", "a\nb", "--new", "x\ny")
    expected = b"x\r\ny\nc\r\n"
    d = check_edited(lab, r, p, before, expected, level="line_endings", start=1, end=2)
    assert d["line_ending"] == "CRLF"


def test_level_1_inserts_the_new_text_as_given_in_a_crlf_file(lab: Lab) -> None:
    before = b"one\r\ntwo\r\nthree\r\n"
    p = write(lab.ws / "f.txt", before)
    r = edit(lab, "--json", "f.txt", "--old", "two", "--new", "2\n2")
    expected = b"one\r\n2\n2\r\nthree\r\n"
    check_edited(lab, r, p, before, expected, level="exact", start=2, end=3, endings_changed=True)


def test_level_1_inserts_crlf_as_given_in_an_lf_file(lab: Lab) -> None:
    before = b"one\ntwo\nthree\n"
    p = write(lab.ws / "f.txt", before)
    r = edit(lab, "--json", "f.txt", "--old", "two", "--new", "2a\r\n2b")
    expected = b"one\n2a\r\n2b\nthree\n"
    check_edited(lab, r, p, before, expected, level="exact", start=2, end=3, endings_changed=True)


@pytest.mark.parametrize(
    ("before", "old"),
    [
        (b"a = 1   \nb = 2\nc = 3\n", "a = 1\nb = 2"),  # trailing spaces in the file
        (b"a = 1\t\nb = 2\nc = 3\n", "a = 1\nb = 2"),  # a trailing tab in the file
        (b"a = 1\nb = 2\nc = 3\n", "a = 1  \nb = 2"),  # trailing spaces in --old
    ],
)
def test_trailing_whitespace_is_ignored_at_level_2(lab: Lab, before: bytes, old: str) -> None:
    p = write(lab.ws / "f.txt", before)
    r = edit(lab, "--json", "f.txt", "--old", old, "--new", "a = 10\nb = 20")
    expected = b"a = 10\nb = 20\nc = 3\n"  # the replaced region's trailing whitespace goes with it (R3)
    check_edited(lab, r, p, before, expected, level="line_endings", start=1, end=2)


def test_trailing_whitespace_is_ignored_at_level_3(lab: Lab) -> None:
    before = b"def f():\n\tif x:   \n\t\treturn x\n\treturn 0\n"
    p = write(lab.ws / "f.py", before)
    r = edit(
        lab, "--json", "f.py", "--old", "    if x:\n        return x", "--new", "    if y:\n        return y"
    )
    expected = b"def f():\n\tif y:\n\t\treturn y\n\treturn 0\n"
    check_edited(lab, r, p, before, expected, level="indentation", start=2, end=3)


# ── FR-3 level 3 and FR-6: indentation ────────────────────────────────────────────────────────


def test_sc2_crlf_and_tabs_given_lf_and_four_spaces(lab: Lab) -> None:
    before = b"def f():\r\n\tif x:\r\n\t\treturn x\r\n\treturn None\r\n"
    p = write(lab.ws / "f.py", before)
    old = "    if x:\n        return x"
    new = "    if x:\n        return x + 1\n    log(1)"
    r = edit(lab, "--json", "f.py", "--old", old, "--new", new)
    expected = b"def f():\r\n\tif x:\r\n\t\treturn x + 1\r\n\tlog(1)\r\n\treturn None\r\n"
    d = check_edited(lab, r, p, before, expected, level="indentation", start=2, end=4)
    assert d["mapping"] == {"agent": "4 spaces", "file": "1 tab"}
    assert d["line_ending"] == "CRLF"
    assert d["verdict"] == (
        "edited lines 2-4 of 5 (matched ignoring line endings and indentation (4 spaces = 1 tab))"
    )
    assert (d["match_start"], d["match_end"]) == (2, 3)


def test_two_spaces_in_the_file_four_from_the_agent(lab: Lab) -> None:
    before = b"def f():\n  if x:\n    return x\n  y = 2\n"
    p = write(lab.ws / "f.py", before)
    old = "    if x:\n        return x"
    new = "    if x:\n        return 1\n    z = 3"
    r = edit(lab, "--json", "f.py", "--old", old, "--new", new)
    expected = b"def f():\n  if x:\n    return 1\n  z = 3\n  y = 2\n"
    d = check_edited(lab, r, p, before, expected, level="indentation", start=2, end=4)
    assert d["mapping"] == {"agent": "4 spaces", "file": "2 spaces"}
    assert "(4 spaces = 2 spaces)" in d["verdict"]


def test_tabs_from_the_agent_four_spaces_in_the_file(lab: Lab) -> None:
    before = b"class A:\n    def f(self):\n        return 1\n"
    p = write(lab.ws / "a.py", before)
    old = "\tdef f(self):\n\t\treturn 1"
    new = "\tdef f(self):\n\t\treturn 2"
    r = edit(lab, "--json", "a.py", "--old", old, "--new", new)
    expected = b"class A:\n    def f(self):\n        return 2\n"
    d = check_edited(lab, r, p, before, expected, level="indentation", start=2, end=3)
    assert d["mapping"] == {"agent": "1 tab", "file": "4 spaces"}


def test_an_alignment_remainder_is_kept_as_given(lab: Lab) -> None:
    before = b"def f():\n\tif x:\n\t\treturn g(a)\n"
    p = write(lab.ws / "f.py", before)
    old = "    if x:\n        return g(a)"
    new = "    if x:\n        return g(a,\n" + " " * 15 + "b)"  # 15 = 3 levels of 4, and 3 for alignment
    r = edit(lab, "--json", "f.py", "--old", old, "--new", new)
    expected = b"def f():\n\tif x:\n\t\treturn g(a,\n\t\t\t   b)\n"
    check_edited(lab, r, p, before, expected, level="indentation", start=2, end=4)


def test_a_mixed_indent_line_identical_on_both_sides_maps(lab: Lab) -> None:
    before = b"def f():\n\tcall(a,\n\t  b)\n\treturn 1\n"
    p = write(lab.ws / "f.py", before)
    old = "    call(a,\n\t  b)"
    new = (
        "    call(a,\n\t  c)"  # a line indented with tabs, when the agent's unit is spaces, is kept as given
    )
    r = edit(lab, "--json", "f.py", "--old", old, "--new", new)
    expected = b"def f():\n\tcall(a,\n\t  c)\n\treturn 1\n"
    d = check_edited(lab, r, p, before, expected, level="indentation", start=2, end=3)
    assert d["mapping"] == {"agent": "4 spaces", "file": "1 tab"}


def test_a_mixed_indent_line_that_differs_does_not_map(lab: Lab) -> None:
    before = b"def f():\n\tcall(a,\n\t  b)\n\treturn 1\n"
    p = write(lab.ws / "f.py", before)
    r = edit(lab, "--json", "f.py", "--old", "    call(a,\n      b)", "--new", "    call(a,\n      c)")
    outcome(r, 3, "no match")
    check_untouched(p, before)


def test_no_single_mapping_is_no_match_with_an_indentation_candidate(lab: Lab) -> None:
    before = b"# head one\n# head two\ndef f():\n\tif x:\n\t\treturn x\n# tail one\n# tail two\n"
    p = write(lab.ws / "f.py", before)
    old = "    if x:\n      return x"  # 4 spaces = 1 tab on one line, 3 spaces = 1 tab on the next
    r = edit(lab, "--json", "f.py", "--old", old, "--new", "    if x:\n      return 0")
    d = outcome(r, 3, "no match")
    check_untouched(p, before)
    first = d["candidates"][0]
    assert (first["start"], first["end"]) == (4, 5)
    assert first["difference"] == "indentation"


# ── FR-5: candidates ──────────────────────────────────────────────────────────────────────────

OLD3 = ["alpha = compute(one)", "beta = compute(two)", "gamma = compute(three)"]


def candidate_file() -> list[str]:
    texts = [f"# filler {i:02d} ......" for i in range(1, 31)]
    texts[4:7] = ["alpha = compute(one)", "beta = compute(twx)", "gamma = compute(three)"]  # 5-7
    texts[14:17] = ["alpha = compute(one)", "beta = compute(tw0)", "gamma = compute(thr33)"]  # 15-17
    texts[24:27] = ["alpha = compite(onx)", "beta = cmpute(txo)", "gamma = compute(three)"]  # 25-27
    return texts


def ratio(a: list[str], b: list[str]) -> float:
    return difflib.SequenceMatcher(None, "\n".join(a), "\n".join(b), autojunk=False).ratio()


def test_candidates_are_ranked_floored_and_do_not_overlap(lab: Lab) -> None:
    texts = candidate_file()
    before = ("\n".join(texts) + "\n").encode()
    p = write(lab.ws / "cand.py", before)
    r = edit(lab, "--json", "cand.py", "--old", "\n".join(OLD3), "--new", "x = 1")
    d = outcome(r, 3, "no match")
    check_untouched(p, before)
    cands = d["candidates"]
    regions = [(5, 7), (15, 17), (25, 27)]
    mine = [ratio(OLD3, texts[s - 1 : e]) for s, e in regions]
    assert mine == sorted(mine, reverse=True) and mine[-1] >= 0.5  # the fixture's own ranking
    assert [(c["start"], c["end"]) for c in cands] == regions
    for c, m, (s, e) in zip(cands, mine, regions, strict=True):
        assert abs(c["similarity"] - m) <= 0.01, (c, m)
        assert c["lines"] == numbered(texts, s, e, len(texts))
    assert [c["difference"] for c in cands] == ["line 2 differs", "line 2 differs", "line 1 differs"]
    assert d["verdict"].startswith("--old matches nowhere (tried exact, line endings, indentation); ")
    assert "3 nearest candidates" in d["verdict"] and d["verdict"].endswith("nothing written")
    assert "view cand.py:5-7" in d["remedy"]
    assert d["time_limited"] is False and d["searched_lines"] == len(texts)


def test_at_most_three_candidates(lab: Lab) -> None:
    texts = candidate_file()
    texts[9:12] = ["alpha = compute(one)", "beta = compute(twz)", "gamma = compute(three)"]  # 10-12
    before = ("\n".join(texts) + "\n").encode()
    p = write(lab.ws / "cand.py", before)
    d = outcome(edit(lab, "--json", "cand.py", "--old", "\n".join(OLD3), "--new", "x = 1"), 3, "no match")
    check_untouched(p, before)
    cands = d["candidates"]
    assert len(cands) == 3
    sims = [c["similarity"] for c in cands]
    assert sims == sorted(sims, reverse=True) and min(sims) >= 0.5
    spans = sorted((c["start"], c["end"]) for c in cands)
    assert all(a[1] < b[0] for a, b in itertools.pairwise(spans)), spans


def test_no_candidate_above_the_floor(lab: Lab) -> None:
    texts = [f"# filler {i:02d} ......" for i in range(1, 21)]
    before = ("\n".join(texts) + "\n").encode()
    p = write(lab.ws / "f.py", before)
    old = ["zzzz qqqq", "xxxx yyyy"]
    assert max(ratio(old, texts[i : i + 2]) for i in range(len(texts) - 1)) < 0.5
    d = outcome(edit(lab, "--json", "f.py", "--old", "\n".join(old), "--new", "k"), 3, "no match")
    check_untouched(p, before)
    assert d["candidates"] == []
    assert "no candidate above 0.5 similarity" in d["verdict"]
    assert "search" in d["remedy"]
    assert isinstance(d["searched_lines"], int) and isinstance(d["time_limited"], bool)


def test_no_match_text_mode_numbers_the_candidates(lab: Lab) -> None:
    texts = candidate_file()
    before = ("\n".join(texts) + "\n").encode()
    p = write(lab.ws / "cand.py", before)
    r = edit(lab, "--text", "cand.py", "--old", "\n".join(OLD3), "--new", "x = 1")
    assert r.returncode == 3 and r.stderr == "", said(r)
    check_untouched(p, before)
    out = text_of(r)
    assert out[0] == "edit: cand.py [no match]"
    assert out[1].startswith("verdict: --old matches nowhere")
    head = [x for x in out if x.startswith("── candidate 1: lines 5-7, similarity ")]
    assert len(head) == 1 and head[0].endswith(": line 2 differs ──"), out
    i = out.index(head[0])
    assert out[i + 1 : i + 4] == numbered(texts, 5, 7, len(texts))
    assert out[-1].startswith("do instead: ")


# ── FR-7, R5: the write ───────────────────────────────────────────────────────────────────────


def test_mode_is_kept(lab: Lab) -> None:
    before = b"#!/bin/sh\necho one\n"
    p = write(lab.ws / "s.sh", before, mode=0o751)
    r = edit(lab, "--json", "s.sh", "--old", "echo one", "--new", "echo two")
    check_edited(lab, r, p, before, b"#!/bin/sh\necho two\n", level="exact", start=2, end=2)
    assert stat.S_IMODE(p.stat().st_mode) == 0o751


@pytest.mark.skipif(os.geteuid() == 0, reason="root can write a read-only file")
def test_an_unwritable_file_is_refused_unchanged(lab: Lab) -> None:
    before = b"one\ntwo\n"
    p = write(lab.ws / "ro.txt", before, mode=0o444)
    d = outcome(edit(lab, "--json", "ro.txt", "--old", "one", "--new", "1"), 1, "refused")
    check_untouched(p, before)
    assert stat.S_IMODE(p.stat().st_mode) == 0o444
    assert d["verdict"] == "cannot write ro.txt: permission denied; nothing written"


def test_a_symlink_edits_its_target_and_stays_a_link(lab: Lab) -> None:
    before = b"one\ntwo\n"
    real = write(lab.ws / "real.txt", before)
    link = lab.ws / "link.txt"
    link.symlink_to("real.txt")
    r = edit(lab, "--json", "link.txt", "--old", "two", "--new", "2")
    d = outcome(r, 0)
    assert link.is_symlink() and os.readlink(link) == "real.txt"
    assert real.read_bytes() == b"one\n2\n"
    assert d["abs_path"] == os.path.realpath(real)
    assert f"via symlink to {os.path.realpath(real)}" in d["verdict"]
    assert d["sha256_after"] == file_sha(real)


def test_a_hard_link_is_broken_and_said(lab: Lab) -> None:
    before = b"one\ntwo\n"
    a = write(lab.ws / "a.txt", before)
    b = lab.ws / "b.txt"
    os.link(a, b)
    d = outcome(edit(lab, "--json", "a.txt", "--old", "two", "--new", "2"), 0)
    assert a.read_bytes() == b"one\n2\n"
    assert b.read_bytes() == before  # the rename makes a new inode; the other name keeps the old bytes
    assert a.stat().st_ino != b.stat().st_ino
    assert "hard link broken (2 links)" in d["verdict"]


def test_too_large_is_refused_unchanged(lab: Lab) -> None:
    size = 16 * 1024 * 1024 + 1
    before = b"x" * (size - 1) + b"\n"
    p = write(lab.ws / "big.txt", before)
    d = outcome(edit(lab, "--json", "big.txt", "--old", "xx", "--new", "y"), 1, "refused")
    check_untouched(p, before)
    assert d["verdict"].startswith(f"too large to edit: {human(size)}")
    assert d["verdict"].endswith("(limit 16 MiB)")


# ── edge cases: BOM, undecodable bytes, binary ────────────────────────────────────────────────


def test_a_bom_is_kept_at_level_1(lab: Lab) -> None:
    before = b"\xef\xbb\xbfone\ntwo\nthree\n"
    p = write(lab.ws / "f.txt", before)
    r = edit(lab, "--json", "f.txt", "--old", "one\ntwo", "--new", "uno\ndos")
    check_edited(lab, r, p, before, b"\xef\xbb\xbfuno\ndos\nthree\n", level="exact", start=1, end=2)


def test_a_bom_is_kept_at_level_2(lab: Lab) -> None:
    before = b"\xef\xbb\xbfone\r\ntwo\r\nthree\r\n"
    p = write(lab.ws / "f.txt", before)
    r = edit(lab, "--json", "f.txt", "--old", "one\ntwo", "--new", "uno\ndos")
    expected = b"\xef\xbb\xbfuno\r\ndos\r\nthree\r\n"
    check_edited(lab, r, p, before, expected, level="line_endings", start=1, end=2)


def test_undecodable_bytes_are_kept_byte_for_byte(lab: Lab) -> None:
    before = b"caf\xe9 = 1\nx = 2\ny = 3\n"
    p = write(lab.ws / "f.txt", before)
    d = outcome(edit(lab, "--json", "f.txt", "--old", "x = 2", "--new", "x = 20"), 0)
    assert p.read_bytes() == b"caf\xe9 = 1\nx = 20\ny = 3\n"
    assert d["sha256_after"] == file_sha(p)
    assert re.search(r"\b1 undecodable bytes? kept\b", d["verdict"]), d["verdict"]


def test_undecodable_bytes_are_kept_at_level_2(lab: Lab) -> None:
    before = b"caf\xe9\xff\r\nx = 2\r\ny\r\n"
    p = write(lab.ws / "f.txt", before)
    d = outcome(edit(lab, "--json", "f.txt", "--old", "x = 2\ny", "--new", "x = 3\ny"), 0)
    assert p.read_bytes() == b"caf\xe9\xff\r\nx = 3\r\ny\r\n"
    assert d["level"] == "line_endings"


def test_a_binary_file_is_refused_unchanged(lab: Lab) -> None:
    before = b"text then\x00binary\n"
    p = write(lab.ws / "app.o", before)
    d = outcome(edit(lab, "--json", "app.o", "--old", "text", "--new", "word"), 1, "refused")
    check_untouched(p, before)
    assert d["verdict"].startswith("binary file: ")
    assert d["verdict"].endswith("; edit changes text files")


# ── no change, usage errors, a missing file ───────────────────────────────────────────────────


def test_old_equal_to_new_is_no_change(lab: Lab) -> None:
    before = b"one\ntwo\n"
    p = write(lab.ws / "f.txt", before)
    st = p.stat()
    d = outcome(edit(lab, "--json", "f.txt", "--old", "two", "--new", "two"), 0, "no change")
    check_untouched(p, before)
    assert p.stat().st_ino == st.st_ino and p.stat().st_mtime_ns == st.st_mtime_ns
    assert d["verdict"] == "no change: --old and --new are the same"
    assert d["changed"] is False
    assert d["sha256_before"] == sha(before)
    assert d.get("sha256_after") is None


def test_old_equal_to_new_on_absent_text_is_no_match(lab: Lab) -> None:
    before = b"one\ntwo\n"
    p = write(lab.ws / "f.txt", before)
    outcome(edit(lab, "--json", "f.txt", "--old", "three", "--new", "three"), 3, "no match")
    check_untouched(p, before)


def test_an_empty_old_is_a_usage_error(lab: Lab) -> None:
    before = b"one\n"
    p = write(lab.ws / "f.txt", before)
    line = stderr_error(edit(lab, "f.txt", "--old", "", "--new", "x"), 2)
    assert "--old is empty" in line
    check_untouched(p, before)


@pytest.mark.parametrize("args", [["--old", "one"], ["--new", "x"], []])
def test_old_or_new_missing_is_a_usage_error(lab: Lab, args: list[str]) -> None:
    before = b"one\n"
    p = write(lab.ws / "f.txt", before)
    stderr_error(edit(lab, "f.txt", *args), 2)
    check_untouched(p, before)


def test_yes_is_not_a_flag(lab: Lab) -> None:
    before = b"one\n"
    p = write(lab.ws / "f.txt", before)
    r = edit(lab, "f.txt", "--old", "one", "--new", "1", "--yes")
    stderr_error(r, 2)
    check_untouched(p, before)


def test_a_missing_file_is_not_found_and_not_created(lab: Lab) -> None:
    d = outcome(edit(lab, "--json", "nope.txt", "--old", "a", "--new", "b"), 3, "not found")
    assert not (lab.ws / "nope.txt").exists()
    assert d["verdict"] == "no such file: nope.txt"
    assert "printf" in d["remedy"] and "search -F" in d["remedy"]


def test_a_directory_is_a_usage_error(lab: Lab) -> None:
    (lab.ws / "adir").mkdir()
    line = stderr_error(edit(lab, "adir", "--old", "a", "--new", "b"), 2)
    assert "is a directory" in line


# ── FR-9, SC-5: the dry run ───────────────────────────────────────────────────────────────────


def test_dry_run_writes_nothing_and_prints_the_unified_diff(lab: Lab) -> None:
    texts = [f"row {i} = {i * 3}" for i in range(1, 16)]
    before = ("\n".join(texts) + "\n").encode()
    p = write(lab.ws / "app.py", before)
    st = p.stat()
    old = f"{texts[6]}\n{texts[7]}"
    new = "row 7 = changed\nrow 8 = changed"
    r = edit(lab, "--json", "app.py", "--old", old, "--new", new, "--dry-run")
    d = outcome(r, 0)
    check_untouched(p, before)
    assert p.stat().st_ino == st.st_ino and p.stat().st_mtime_ns == st.st_mtime_ns
    after = before.replace(old.encode(), new.encode()).decode()
    expected_diff = list(
        difflib.unified_diff(
            before.decode().splitlines(), after.splitlines(), "a/app.py", "b/app.py", n=3, lineterm=""
        )
    )
    assert d["lines"] == expected_diff  # the diff is the body (contract § Dry run), not a data key
    assert "diff" not in d
    assert d["dry_run"] is True
    assert d["changed"] is False
    assert d["sha256_before"] == sha(before)
    assert d["sha256_after"] is None
    assert d["level"] == "exact" and d["mapping"] is None
    assert (d["start"], d["end"], d["total"]) == (7, 8, 15)
    assert (d["match_start"], d["match_end"]) == (7, 8)
    assert d["line_ending"] == "LF"
    assert d["verdict"] == "dry run: would edit lines 7-8 of 15 (matched exactly); nothing written"


def test_dry_run_text_mode(lab: Lab) -> None:
    before = b"a\nb\nc\nd\n"
    p = write(lab.ws / "f.txt", before)
    r = edit(lab, "--text", "f.txt", "--old", "b\nc", "--new", "B\nC", "--dry-run")
    assert r.returncode == 0 and r.stderr == "", said(r)
    check_untouched(p, before)
    out = text_of(r)
    expected_diff = list(
        difflib.unified_diff(["a", "b", "c", "d"], ["a", "B", "C", "d"], "a/f.txt", "b/f.txt", lineterm="")
    )
    assert out[1] == "verdict: dry run: would edit lines 2-3 of 4 (matched exactly); nothing written"
    assert out[2:] == expected_diff


def test_dry_run_on_crlf_and_tabs_writes_nothing(lab: Lab) -> None:
    before = b"def f():\r\n\tif x:\r\n\t\treturn x\r\n"
    p = write(lab.ws / "g.py", before)
    old, new = "    if x:\n        return x", "    if y:\n        return y"
    d = outcome(edit(lab, "--json", "g.py", "--old", old, "--new", new, "--dry-run"), 0)
    check_untouched(p, before)
    assert d["level"] == "indentation"
    assert d["mapping"] == {"agent": "4 spaces", "file": "1 tab"}
    assert d["line_ending"] == "CRLF"
    expected_diff = list(
        difflib.unified_diff(
            ["def f():", "\tif x:", "\t\treturn x"],
            ["def f():", "\tif y:", "\t\treturn y"],
            "a/g.py",
            "b/g.py",
            lineterm="",
        )
    )
    assert d["lines"] == expected_diff  # endings are not shown in the diff
    assert "line endings:" not in d["verdict"]


def test_dry_run_names_a_change_of_line_endings_in_the_verdict(lab: Lab) -> None:
    before = b"one\r\ntwo\r\nthree\r\n"
    p = write(lab.ws / "f.txt", before)
    d = outcome(edit(lab, "--json", "f.txt", "--old", "two", "--new", "2\n2", "--dry-run"), 0)
    check_untouched(p, before)
    assert d["level"] == "exact"
    expected_diff = list(
        difflib.unified_diff(
            ["one", "two", "three"], ["one", "2", "2", "three"], "a/f.txt", "b/f.txt", lineterm=""
        )
    )
    assert d["lines"] == expected_diff
    assert all("[CRLF" not in x and "LF]" not in x for x in d["lines"])
    assert d["verdict"].startswith("dry run: would edit lines 2-3 of 4 (matched exactly)")
    assert re.search(r"; line endings: .+ → .+", d["verdict"]), d["verdict"]
    assert d["verdict"].endswith("nothing written")


# ── FR-10, FR-12: the contract ────────────────────────────────────────────────────────────────


def test_manifest(lab: Lab) -> None:
    r = edit(lab, "--agent-info")
    assert r.returncode == 0, said(r)
    info = doc_of(r)
    assert schema.errors(info, schema.load("agent-info.schema.json")) == []
    assert info["tool"] == "edit"
    assert info["mutating"] is True
    assert info["confirm_protocol"] is False
    assert info["destructive"] is True
    assert info["dry_run"] is True
    assert info["reads_stdin"] is False
    assert info["envelopes"] == []
    assert "--dry-run" in info["flags"]
    assert "--yes" not in info["flags"]
    assert set(info["exit_codes"]) == {"0", "1", "2", "3"}
    assert info["probe"] == ["/etc/os-release", "--old", "PRETTY_NAME=", "--new", "PRETTY_NAME=", "--dry-run"]
    assert info["levels"] == ["exact", "line endings", "indentation"]
    assert (info["context"], info["candidates"], info["candidate_floor"]) == (3, 3, 0.5)


def test_the_probe_runs(lab: Lab) -> None:
    """R7: the probe is a no-op. It runs against the real /etc/os-release, as conform runs it."""
    before = file_sha(Path("/etc/os-release"))
    info = doc_of(edit(lab, "--agent-info"))
    d = outcome(edit(lab, "--json", *info["probe"]), 0)
    assert d["target"] == "/etc/os-release"
    assert file_sha(Path("/etc/os-release")) == before


def test_help_is_within_40_lines(lab: Lab) -> None:
    r = edit(lab, "--help")
    assert r.returncode == 0
    lines = r.stdout.splitlines()
    assert 0 < len(lines) <= 40 and lines[0].startswith("edit: ")


def test_json_is_the_default_when_piped(lab: Lab) -> None:
    write(lab.ws / "f.txt", b"one\ntwo\n")
    d = outcome(edit(lab, "f.txt", "--old", "two", "--new", "2"), 0)
    assert d["changed"] is True


def test_one_event_per_invocation(lab: Lab) -> None:
    write(lab.ws / "f.txt", b"one\ntwo\none\n")
    write(lab.ws / "app.o", b"\x00\x01")
    (lab.ws / "adir").mkdir()
    expected: list[int] = []
    for args in (
        ["--json", "f.txt", "--old", "two", "--new", "2"],
        ["--text", "f.txt", "--old", "2", "--new", "2"],
        ["--json", "f.txt", "--old", "one", "--new", "1"],
        ["--json", "f.txt", "--old", "absent", "--new", "x"],
        ["--json", "nope.txt", "--old", "a", "--new", "b"],
        ["--json", "app.o", "--old", "a", "--new", "b"],
        ["adir", "--old", "a", "--new", "b"],
        ["f.txt", "--old", "", "--new", "x"],
        ["f.txt", "--old", "2", "--new", "3", "--dry-run"],
    ):
        r = edit(lab, *args)
        expected.append(r.returncode)
        assert len(events(lab.scratch, SESSION)) == len(expected), args
    assert expected == [0, 0, 3, 3, 3, 1, 2, 2, 0]
    evs = events(lab.scratch, SESSION)
    assert [e["exit"] for e in evs] == expected
    event_schema = schema.load("event.schema.json")
    for ev in evs:
        assert (ev["tool"], ev["session"]) == ("edit", SESSION)
        assert schema.errors(ev, event_schema) == []
