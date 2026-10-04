"""view (feature 006, slice 0, T008) against contracts/view-search-cli.md, data-model.md § Window, spec
FR-1 to FR-11 and FR-21, research R3 and R4.

Written from the contract alone, before the tool. The tool runs as a real subprocess, with its working
directory in a workspace under tmp_path, HOME a sibling of it, and the scratch root outside both. Every
expected figure (line numbers, omitted lines and bytes, sizes, replaced bytes) is computed by the test from
the bytes it wrote, never read back from the tool (P004, P005).

Long lines (FR-7) follow discovery revision 12 as relayed by the coordinator: rule 13's cut applies in both
modes, JSON carries `cut_lines`, `view --columns N` (0 = no cut) reads long lines whole, and a window with
cut lines ends its body with `long lines cut: K; read them whole with: view FILE:S-E --columns 0`.

The helpers at the top are shared with test_search.py, which imports them from here.
"""

from __future__ import annotations

import errno
import os
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
import schema
from conftest import TOOLS_DIR, base_env, events
from test_snapshot import doc_of, human, said, stderr_error, text_of, write

VIEW = TOOLS_DIR / "view"
SESSION = "bounded-t008"
WINDOW = 120
CONTEXT = 10
Proc = subprocess.CompletedProcess[str]


# ── the lab: a home, a workspace and a scratch root, as siblings in tmp_path ──────────────────


@dataclass
class Lab:
    tmp: Path
    home: Path
    ws: Path  # the working directory of every call unless a test says otherwise
    scratch: Path
    session: str

    def env(self, **extra: str) -> dict[str, str]:
        return base_env(self.scratch, self.session, HOME=str(self.home), **extra)


def make_lab(tmp_path: Path, session: str) -> Lab:
    tmp = Path(os.path.realpath(tmp_path))  # real paths, so `abs_path` and `full output` compare exactly
    home = tmp / "home"
    home.mkdir()
    ws = tmp / "ws"
    ws.mkdir()
    return Lab(tmp, home, ws, tmp / "scratch", session)


@pytest.fixture
def lab(tmp_path: Path) -> Lab:
    return make_lab(tmp_path, SESSION)


def call(tool: Path, lab: Lab, *args: str, cwd: Path | None = None, timeout: float = 30, **env: str) -> Proc:
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


def view(lab: Lab, *args: str, **kw: Any) -> Proc:
    return call(VIEW, lab, *args, **kw)


def ok_json(r: Proc) -> dict[str, Any]:
    assert r.returncode == 0, said(r)
    d = doc_of(r)
    assert list(d)[:3] == ["tool", "target", "scope"], d
    assert d["exit"] == 0
    return d


def result_outcome(r: Proc, code: int) -> dict[str, Any]:
    """Contract § "Outcomes are verdicts": a result on stdout (header keys, verdict, exit), nothing on
    stderr; where there is a remedy, `do instead: <remedy>` is the first line and `data.remedy` holds it."""
    assert r.returncode == code, said(r)
    assert r.stderr == "", r.stderr
    d = doc_of(r)
    assert list(d)[:3] == ["tool", "target", "scope"], d
    assert d["exit"] == code
    if "remedy" in d:
        assert d["lines"][0] == f"do instead: {d['remedy']}", d
    return d


def cut_line(line: str, columns: int) -> str:
    """Rule 13: COLUMNS characters, then ` …[cut N bytes]`, N the UTF-8 bytes removed."""
    if columns == 0 or len(line) <= columns:
        return line
    return f"{line[:columns]} …[cut {len(line[columns:].encode())} bytes]"


def run_sed(more: str) -> list[str]:
    """A `more:` that is a `sed -n A,Bp FILE`: run it and return what it prints."""
    words = shlex.split(more)
    assert words[:2] == ["sed", "-n"], more
    r = subprocess.run(words, capture_output=True, text=True, timeout=10, stdin=subprocess.DEVNULL)
    assert r.returncode == 0, r.stderr
    return r.stdout.splitlines()


# ── the test's own model of a file ────────────────────────────────────────────────────────────


def write_lines(p: Path, texts: list[str], *, final_newline: bool = True, eol: str = "\n") -> Path:
    data = eol.join(texts) + (eol if final_newline and texts else "")
    return write(p, data.encode())


def numbered(texts: list[str], start: int, end: int, total: int, target: int | None = None) -> list[str]:
    """`{n:>W}{m} {text}`, W = len(str(total)), m `>` on the target and a space otherwise."""
    w = len(str(total))
    return [f"{n:>{w}}{'>' if n == target else ' '} {texts[n - 1]}" for n in range(start, end + 1)]


def omitted_bytes(raw: bytes, start: int, end: int) -> int:
    """The bytes of every file line outside start..end, as stored (newlines included)."""
    pieces = raw.split(b"\n")
    lines = [p + b"\n" for p in pieces[:-1]] + ([pieces[-1]] if pieces[-1] else [])
    return sum(len(x) for i, x in enumerate(lines, 1) if not start <= i <= end)


def big_texts(n: int = 412) -> list[str]:
    return [f"line {i:03d}: alpha beta {i * 7}" for i in range(1, n + 1)]


def cut_text(
    target: str,
    abs_path: str,
    body: list[str],
    start: int,
    end: int,
    total: int,
    verdict: str,
    more: str,
    raw: bytes,
) -> list[str]:
    """The whole text output of a partial window (contract § Partial window: a cut)."""
    scope = f"lines {start}-{end} of {total}"
    omitted = total - (end - start + 1)
    return [
        f"view: {target} [{scope}]",
        f"verdict: {verdict}",
        f"── {scope} ──",
        *body,
        f"more: {more}",
        "exit: 0",
        f"full output: {abs_path}",
        f"… omitted {omitted} lines ({omitted_bytes(raw, start, end)} bytes)"
        f" — full output: {abs_path}; more: {more}",
    ]


def check_cut_json(
    d: dict[str, Any],
    *,
    target: str,
    abs_path: str,
    raw: bytes,
    start: int,
    end: int,
    total: int,
    more: str,
    next_: str | None,
) -> None:
    assert d["scope"] == f"lines {start}-{end} of {total}"
    assert (d["start"], d["end"], d["total"]) == (start, end, total)
    assert (d["path"], d["abs_path"]) == (target, abs_path)
    assert d["truncated"] == {
        "omitted_lines": total - (end - start + 1),
        "omitted_bytes": omitted_bytes(raw, start, end),
        "full_output": abs_path,
        "more": more,
    }
    assert d["next"] == next_


@pytest.fixture
def big(lab: Lab) -> tuple[list[str], bytes, str]:
    texts = big_texts()
    p = write_lines(lab.ws / "big.txt", texts)
    return texts, p.read_bytes(), os.path.realpath(p)


# ── FR-1, FR-4, FR-5: the first window of a large file is a cut ───────────────────────────────


def test_no_range_shows_lines_1_to_120_of_412_as_a_cut(lab: Lab, big: tuple[list[str], bytes, str]) -> None:
    texts, raw, real = big
    d = ok_json(view(lab, "--json", "big.txt"))
    assert (d["tool"], d["target"]) == ("view", "big.txt")
    assert d["verdict"] == "lines 1-120 of 412"
    assert d["lines"] == numbered(texts, 1, 120, 412)
    assert d["lines"][0] == "  1  line 001: alpha beta 7"  # W = 3: right-aligned to the last number's width
    more = "view big.txt:121-240"
    check_cut_json(
        d, target="big.txt", abs_path=real, raw=raw, start=1, end=120, total=412, more=more, next_=more
    )
    assert d["next"] == d["truncated"]["more"]
    assert d["target"] == "big.txt"  # rule 12's target is FILE; see test_the_target_key_is_file
    assert (d["clipped"], d["replaced_bytes"], d["escape_lines"]) == (False, 0, 0)
    assert "cut_lines" not in d


def test_the_target_key_is_file_and_the_marker_carries_the_line(lab: Lab, big: Any) -> None:
    """Rule 12 puts FILE in the top-level `target`, and agentio reserves that key, so data-model's window
    field `target` (N) cannot also be a top-level key. The line N is pinned by its `>` marker instead."""
    d = ok_json(view(lab, "--json", "big.txt:40"))
    assert d["target"] == "big.txt"
    assert (d["start"], d["end"]) == (30, 50)
    assert [x[:4] for x in d["lines"] if x[3] == ">"] == [" 40>"]


def test_text_of_the_first_window_is_the_contract_example(
    lab: Lab, big: tuple[list[str], bytes, str]
) -> None:
    texts, raw, real = big
    r = view(lab, "--text", "big.txt")
    assert r.returncode == 0 and r.stderr == "", said(r)
    more = "view big.txt:121-240"
    expected = cut_text(
        "big.txt", real, numbered(texts, 1, 120, 412), 1, 120, 412, "lines 1-120 of 412", more, raw
    )
    assert text_of(r) == expected


def test_more_runs_and_shows_the_next_window(lab: Lab, big: tuple[list[str], bytes, str]) -> None:
    texts, _, _ = big
    d = ok_json(view(lab, "--json", "big.txt"))
    words = shlex.split(d["truncated"]["more"])
    assert words[0] == "view"
    d2 = ok_json(view(lab, "--json", *words[1:]))
    assert d2["lines"] == numbered(texts, 121, 240, 412)
    assert d2["next"] == "view big.txt:241-360"


@pytest.mark.parametrize("n", [1, 100, 120])
def test_a_file_of_120_lines_or_fewer_is_shown_whole(lab: Lab, n: int) -> None:
    texts = big_texts(n)
    write_lines(lab.ws / "small.txt", texts)
    d = ok_json(view(lab, "--json", "small.txt"))
    assert d["scope"] == f"lines 1-{n} of {n}"
    assert d["verdict"] == f"lines 1-{n} of {n} (whole file)"
    assert d["lines"] == numbered(texts, 1, n, n)
    assert "truncated" not in d and d["next"] is None
    r = view(lab, "--text", "small.txt")
    out = text_of(r)
    assert out[0] == f"view: small.txt [lines 1-{n} of {n}]"
    assert out[1] == f"verdict: lines 1-{n} of {n} (whole file)"
    assert out[-n:] == numbered(texts, 1, n, n)  # text ends on the file's last line
    assert not any(x.startswith(("… omitted", "more: ", "full output: ")) for x in out), out


def test_121_lines_is_a_cut_of_one_line(lab: Lab) -> None:
    texts = big_texts(121)
    p = write_lines(lab.ws / "f.txt", texts)
    d = ok_json(view(lab, "--json", "f.txt"))
    raw = p.read_bytes()
    assert d["truncated"]["omitted_lines"] == 1
    assert d["truncated"]["omitted_bytes"] == len(texts[120]) + 1 == omitted_bytes(raw, 1, 120)


# ── FR-2: ranges, context, clipping ───────────────────────────────────────────────────────────


def test_range_shows_exactly_lines_40_to_80(lab: Lab, big: tuple[list[str], bytes, str]) -> None:
    texts, raw, real = big
    d = ok_json(view(lab, "--json", "big.txt:40-80"))
    assert d["lines"] == numbered(texts, 40, 80, 412)
    assert d["verdict"] == "lines 40-80 of 412"
    more = "view big.txt:81-200"
    check_cut_json(
        d, target="big.txt", abs_path=real, raw=raw, start=40, end=80, total=412, more=more, next_=more
    )
    assert d["clipped"] is False


def test_line_with_context_marks_only_that_line(lab: Lab, big: tuple[list[str], bytes, str]) -> None:
    texts, raw, real = big
    d = ok_json(view(lab, "--json", "big.txt:40"))
    assert d["lines"] == numbered(texts, 30, 50, 412, target=40)
    assert d["lines"][10] == " 40> line 040: alpha beta 280"
    assert [x for x in d["lines"] if x[3] == ">"] == [d["lines"][10]]
    more = "view big.txt:51-170"
    check_cut_json(
        d, target="big.txt", abs_path=real, raw=raw, start=30, end=50, total=412, more=more, next_=more
    )


def test_line_near_the_start_is_clipped_to_line_1(lab: Lab, big: tuple[list[str], bytes, str]) -> None:
    texts, _, _ = big
    d = ok_json(view(lab, "--json", "big.txt:3"))
    assert (d["start"], d["end"]) == (1, 13)
    assert d["lines"] == numbered(texts, 1, 13, 412, target=3)
    assert d["next"] == "view big.txt:14-133"


def test_line_near_the_end_ends_at_the_file_and_more_is_the_window_before(
    lab: Lab, big: tuple[list[str], bytes, str]
) -> None:
    texts, raw, real = big
    d = ok_json(view(lab, "--json", "big.txt:410"))
    assert d["lines"] == numbered(texts, 400, 412, 412, target=410)
    more = "view big.txt:280-399"  # FILE:{max(1, S-120)}-{S-1}
    check_cut_json(
        d, target="big.txt", abs_path=real, raw=raw, start=400, end=412, total=412, more=more, next_=None
    )
    r = view(lab, "--text", "big.txt:410")
    assert text_of(r)[-4] == f"more: {more}"


def test_window_ending_at_the_end_near_the_top_starts_its_more_at_1(lab: Lab) -> None:
    texts = big_texts(130)
    write_lines(lab.ws / "f.txt", texts)
    d = ok_json(view(lab, "--json", "f.txt:60-130"))
    assert d["truncated"]["more"] == "view f.txt:1-59"
    assert d["next"] is None


def test_a_range_past_the_end_is_clipped_and_says_so(lab: Lab, big: tuple[list[str], bytes, str]) -> None:
    texts, raw, real = big
    d = ok_json(view(lab, "--json", "big.txt:400-500"))
    assert d["lines"] == numbered(texts, 400, 412, 412)
    assert d["verdict"] == "lines 400-412 of 412; clipped to 412"
    assert d["clipped"] is True
    more = "view big.txt:280-399"
    check_cut_json(
        d, target="big.txt", abs_path=real, raw=raw, start=400, end=412, total=412, more=more, next_=None
    )


def test_a_clipped_range_covering_the_file_is_whole_and_clipped(lab: Lab) -> None:
    texts = big_texts(100)
    write_lines(lab.ws / "small.txt", texts)
    d = ok_json(view(lab, "--json", "small.txt:1-500"))
    assert d["verdict"] == "lines 1-100 of 100 (whole file); clipped to 100"
    assert d["clipped"] is True and "truncated" not in d
    assert d["lines"] == numbered(texts, 1, 100, 100)


def test_line_form_on_a_small_file_can_be_the_whole_file(lab: Lab) -> None:
    texts = big_texts(15)
    write_lines(lab.ws / "f.txt", texts)
    d = ok_json(view(lab, "--json", "f.txt:5"))
    assert d["lines"] == numbered(texts, 1, 15, 15, target=5)
    assert d["verdict"] == "lines 1-15 of 15 (whole file)"
    assert "truncated" not in d and d["next"] is None


@pytest.mark.parametrize("spec", ["413", "500", "413-420", "0-5", "50-40", "0"])
def test_impossible_ranges_are_usage_errors_naming_the_length(lab: Lab, big: Any, spec: str) -> None:
    r = view(lab, f"big.txt:{spec}")
    line = stderr_error(r, 2)
    assert "412" in line, line


# ── FILE resolution ───────────────────────────────────────────────────────────────────────────


def test_a_file_literally_named_with_a_colon_is_used_whole(lab: Lab) -> None:
    write_lines(lab.ws / "notes", big_texts(412))
    colon = big_texts(30)
    write_lines(lab.ws / "notes:5", colon)
    d = ok_json(view(lab, "--json", "notes:5"))
    assert not any(x[2] == ">" for x in d["lines"])
    assert d["lines"] == numbered(colon, 1, 30, 30)
    assert d["verdict"] == "lines 1-30 of 30 (whole file)"


def test_otherwise_the_trailing_line_is_split_off(lab: Lab) -> None:
    texts = big_texts(412)
    write_lines(lab.ws / "notes", texts)
    d = ok_json(view(lab, "--json", "notes:5"))
    assert d["lines"] == numbered(texts, 1, 15, 412, target=5)
    assert d["path"] == "notes"


def test_a_non_digit_suffix_is_part_of_the_name(lab: Lab) -> None:
    write_lines(lab.ws / "notes", big_texts(10))
    result_outcome(view(lab, "--json", "notes:abc"), 3)


def test_relative_paths_resolve_from_the_cwd_and_commands_reuse_file_as_given(
    lab: Lab, big: tuple[list[str], bytes, str]
) -> None:
    texts, _, real = big
    sub = lab.ws / "sub"
    sub.mkdir()
    d = ok_json(view(lab, "--json", "../big.txt", cwd=sub))
    assert d["target"] == "../big.txt"
    assert d["path"] == "../big.txt" and d["abs_path"] == real
    assert d["next"] == "view ../big.txt:121-240"
    assert d["lines"] == numbered(texts, 1, 120, 412)


# ── FR-3: the line layout ─────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("n", [9, 10, 99, 100, 1000])
def test_numbers_are_right_aligned_to_the_width_of_the_total(lab: Lab, n: int) -> None:
    texts = big_texts(n)
    write_lines(lab.ws / "f.txt", texts)
    d = ok_json(view(lab, "--json", f"f.txt:{n}"))
    start = max(1, n - CONTEXT)
    assert d["lines"] == numbered(texts, start, n, n, target=n)
    assert d["lines"][-1] == f"{n}> {texts[-1]}"


def test_a_blank_line_keeps_the_layout(lab: Lab) -> None:
    write(lab.ws / "f.txt", b"a\n\nc\n")
    d = ok_json(view(lab, "--json", "f.txt"))
    assert d["lines"] == ["1  a", "2  ", "3  c"]


def test_crlf_lines_are_shown_without_the_cr(lab: Lab) -> None:
    write(lab.ws / "f.txt", b"one\r\ntwo\r\n")
    d = ok_json(view(lab, "--json", "f.txt"))
    assert d["lines"] == ["1  one", "2  two"] and d["total"] == 2
    r = view(lab, "--text", "f.txt")
    assert "\r" not in r.stdout


def test_a_final_line_without_a_newline_counts(lab: Lab) -> None:
    write(lab.ws / "f.txt", b"a\nb\nc")
    d = ok_json(view(lab, "--json", "f.txt"))
    assert d["total"] == 3 and d["lines"] == ["1  a", "2  b", "3  c"]
    write(lab.ws / "g.txt", b"a\nb\n")
    assert ok_json(view(lab, "--json", "g.txt"))["total"] == 2


def test_omitted_bytes_count_a_final_line_without_a_newline(lab: Lab) -> None:
    texts = big_texts(130)
    p = write_lines(lab.ws / "f.txt", texts, final_newline=False)
    raw = p.read_bytes()
    d = ok_json(view(lab, "--json", "f.txt"))
    expected = sum(len(t) + 1 for t in texts[120:129]) + len(texts[129])
    assert d["truncated"]["omitted_bytes"] == expected == omitted_bytes(raw, 1, 120)
    assert d["truncated"]["omitted_lines"] == 10


# ── FR-6: --limit bounds a window ─────────────────────────────────────────────────────────────


def test_limit_bounds_a_long_explicit_range_as_a_cut(lab: Lab, big: tuple[list[str], bytes, str]) -> None:
    texts, raw, real = big
    d = ok_json(view(lab, "--json", "--limit", "50", "big.txt:1-300"))
    assert d["lines"] == numbered(texts, 1, 50, 412)
    more = "view big.txt:51-170"
    check_cut_json(
        d, target="big.txt", abs_path=real, raw=raw, start=1, end=50, total=412, more=more, next_=more
    )


def test_the_default_limit_of_200_bounds_a_long_range(lab: Lab, big: tuple[list[str], bytes, str]) -> None:
    texts, _, _ = big
    d = ok_json(view(lab, "--json", "big.txt:1-300"))
    assert d["lines"] == numbered(texts, 1, 200, 412)
    assert d["next"] == "view big.txt:201-320"


def test_limit_below_the_window_cuts_a_small_file(lab: Lab) -> None:
    texts = big_texts(120)
    write_lines(lab.ws / "f.txt", texts)
    d = ok_json(view(lab, "--json", "--limit", "100", "f.txt"))
    assert d["lines"] == numbered(texts, 1, 100, 120)
    assert d["next"] == "view f.txt:101-220"
    assert d["truncated"]["omitted_lines"] == 20


def test_limit_0_shows_a_whole_large_file_with_no_omission_line(
    lab: Lab, big: tuple[list[str], bytes, str]
) -> None:
    texts, _, _ = big
    d = ok_json(view(lab, "--json", "--limit", "0", "big.txt:1-412"))
    assert d["lines"] == numbered(texts, 1, 412, 412)
    assert d["verdict"] == "lines 1-412 of 412 (whole file)"
    assert "truncated" not in d and d["next"] is None
    d0 = ok_json(view(lab, "--json", "--limit", "0", "big.txt"))  # data-model, as amended: no range too
    assert d0["lines"] == numbered(texts, 1, 412, 412)
    assert "truncated" not in d0 and d0["verdict"] == "lines 1-412 of 412 (whole file)"
    out = text_of(view(lab, "--text", "--limit", "0", "big.txt:1-412"))
    assert out[-412:] == numbered(texts, 1, 412, 412)
    assert not any(x.startswith("… omitted") for x in out)


# ── FR-7 (discovery revision 12): long lines are cut in both modes ────────────────────────────


def long_file(lab: Lab) -> tuple[list[str], str]:
    long = "x" * 4990 + "ééééé"  # the removed part holds multibyte characters: N counts bytes
    texts = ["short one", long, "short two"]
    write_lines(lab.ws / "long.txt", texts)
    return texts, long


def test_a_long_line_is_cut_at_columns_in_json_with_cut_lines(lab: Lab) -> None:
    texts, _ = long_file(lab)
    full = numbered(texts, 1, 3, 3)
    d = ok_json(view(lab, "--json", "long.txt"))
    assert d["lines"][:3] == [full[0], cut_line(full[1], 200), full[2]]
    assert d["lines"][1].endswith(f" …[cut {len(full[1][200:].encode())} bytes]")
    assert d["cut_lines"] == [{"index": 1, "cut_bytes": len(full[1][200:].encode())}]
    assert d["lines"][3:] == ["long lines cut: 1; read them whole with: view long.txt:1-3 --columns 0"]


def test_columns_env_sets_the_cut_in_both_modes(lab: Lab) -> None:
    texts, _ = long_file(lab)
    full = numbered(texts, 1, 3, 3)
    d = ok_json(view(lab, "--json", "long.txt", COLUMNS="40"))
    assert d["lines"][1] == cut_line(full[1], 40)
    assert d["cut_lines"] == [{"index": 1, "cut_bytes": len(full[1][40:].encode())}]
    out = text_of(view(lab, "--text", "long.txt", COLUMNS="40"))
    assert out[-4:] == [
        full[0],
        cut_line(full[1], 40),
        full[2],
        "long lines cut: 1; read them whole with: view long.txt:1-3 --columns 0",
    ]


def test_columns_0_reads_long_lines_whole(lab: Lab) -> None:
    texts, _ = long_file(lab)
    d = ok_json(view(lab, "--json", "--columns", "0", "long.txt"))
    assert d["lines"] == numbered(texts, 1, 3, 3)
    assert "cut_lines" not in d
    out = text_of(view(lab, "--text", "--columns", "0", "long.txt"))
    assert out[-3:] == numbered(texts, 1, 3, 3)


def test_the_long_lines_line_precedes_the_cut_footer(lab: Lab) -> None:
    texts = big_texts(200)
    texts[4] = "y" * 300
    write_lines(lab.ws / "f.txt", texts)
    out = text_of(view(lab, "--text", "f.txt"))
    assert out[-5] == "long lines cut: 1; read them whole with: view f.txt:1-120 --columns 0"
    assert out[-4] == "more: view f.txt:121-240"


def test_no_cut_lines_key_when_nothing_was_cut(lab: Lab, big: Any) -> None:
    d = ok_json(view(lab, "--json", "big.txt:1-10"))
    assert "cut_lines" not in d
    assert not any(x.startswith("long lines cut:") for x in d["lines"])


# ── FR-9: binary files ────────────────────────────────────────────────────────────────────────


def tar_bytes() -> bytes:
    b = bytearray(1024)
    b[0:5] = b"a.txt"
    b[257:263] = b"ustar\x00"
    return bytes(b)


BINARIES: list[tuple[str, bytes, str]] = [
    ("app.o", b"\x7fELF\x02\x01\x01" + b"\x00" * 2993, "ELF"),
    ("pic.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 92, "PNG"),
    ("pic.jpg", b"\xff\xd8\xff\xe0" + b"\x00" * 2044, "JPEG"),
    ("pic.gif", b"GIF89a" + b"\x00" * 30, "GIF"),
    ("a.gz", b"\x1f\x8b\x08" + b"\x00" * 5000, "gzip"),
    ("a.zip", b"PK\x03\x04" + b"\x00" * 1500, "zip"),
    ("a.pdf", b"%PDF-1.7\n" + b"\x00" * 64, "PDF"),
    ("a.db", b"SQLite format 3\x00" + b"\x00" * 4080, "SQLite"),
    ("a.tar", tar_bytes(), "tar"),
    ("blob", b"\x00\x01\x02hello" + b"\x00" * 1024 * 1024 * 2, "data"),
]


@pytest.mark.parametrize(("name", "data", "kind"), BINARIES, ids=[b[2] for b in BINARIES])
def test_binary_shows_type_and_size_and_no_content(lab: Lab, name: str, data: bytes, kind: str) -> None:
    write(lab.ws / name, data)
    n = len(data)
    verdict = f"binary file: {kind}, {human(n)} ({n} bytes); content not shown"
    d = ok_json(view(lab, "--json", name))
    assert d["scope"] == "binary" and d["verdict"] == verdict
    assert (d["binary"], d["type"], d["size"]) == (True, kind, n)
    assert d["lines"] == [] and "truncated" not in d
    assert (d["path"], d["abs_path"]) == (name, os.path.realpath(lab.ws / name))
    r = view(lab, "--text", name)
    assert text_of(r) == [f"view: {name} [binary]", f"verdict: {verdict}"]


def test_a_nul_in_the_first_8_kib_makes_a_file_binary(lab: Lab) -> None:
    write(lab.ws / "f", b"a" * 8191 + b"\x00" + b"\n")
    d = ok_json(view(lab, "--json", "f"))
    assert d.get("binary") is True and d["type"] == "data"


def test_a_nul_after_8_kib_leaves_a_file_text(lab: Lab) -> None:
    texts = [f"t{i:04d}" for i in range(2000)]  # 12000 bytes, then a NUL
    write(lab.ws / "f", ("\n".join(texts) + "\n").encode() + b"\x00\n")
    d = ok_json(view(lab, "--json", "f"))
    assert not d.get("binary") and d["scope"] == "lines 1-120 of 2001"


# ── an empty file, decoding, escapes (FR-10, FR-11) ───────────────────────────────────────────


def test_an_empty_file(lab: Lab) -> None:
    write(lab.ws / "empty.txt", b"")
    d = ok_json(view(lab, "--json", "empty.txt"))
    assert d["scope"] == "empty" and d["verdict"] == "empty file (0 lines)"
    assert (d["total"], d["start"], d["end"]) == (0, 0, 0)
    assert d["lines"] == [] and "truncated" not in d
    assert text_of(view(lab, "--text", "empty.txt")) == [
        "view: empty.txt [empty]",
        "verdict: empty file (0 lines)",
    ]


def test_invalid_utf8_is_replaced_and_counted(lab: Lab) -> None:
    write(
        lab.ws / "latin1.txt", b"caf\xff ok\nplain\n\xfe\x80 end\n"
    )  # three invalid start/continuation bytes
    d = ok_json(view(lab, "--json", "latin1.txt"))
    assert d["replaced_bytes"] == 3
    assert d["verdict"] == "lines 1-3 of 3 (whole file); 3 undecodable bytes shown as U+FFFD"
    assert d["lines"] == ["1  caf� ok", "2  plain", "3  �� end"]


def test_terminal_escapes_are_stripped_and_counted(lab: Lab) -> None:
    write(lab.ws / "esc.txt", b"plain\n\x1b[31mred\x1b[0m text\n\x1b]0;title\x07after\n")
    d = ok_json(view(lab, "--json", "esc.txt"))
    assert d["escape_lines"] == 2
    assert d["verdict"] == "lines 1-3 of 3 (whole file); 2 lines had terminal escapes stripped"
    assert d["lines"][:2] == ["1  plain", "2  red text"]
    assert d["lines"][2].endswith("after")
    assert not any("\x1b" in x for x in d["lines"])
    for mode in ("--json", "--text"):
        r = view(lab, mode, "esc.txt")
        assert "\x1b" not in r.stdout and "\\u001b" not in r.stdout, mode


# ── FR-8 and the refusals ─────────────────────────────────────────────────────────────────────


def test_a_missing_file_exits_3_with_do_instead(lab: Lab) -> None:
    d = result_outcome(view(lab, "--json", "nope.txt"), 3)
    assert d["verdict"] == "no such file: nope.txt"
    assert d["remedy"] == "check the name; search for it with: search -F nope.txt ."
    assert d["lines"][0] == "do instead: check the name; search for it with: search -F nope.txt ."
    r = view(lab, "--text", "nope.txt")
    out = text_of(r)
    assert r.returncode == 3 and r.stderr == ""
    assert out[0].startswith("view: nope.txt [") and out[1] == "verdict: no such file: nope.txt"
    assert out[2] == "do instead: check the name; search for it with: search -F nope.txt ."


def test_a_directory_is_a_usage_error(lab: Lab) -> None:
    (lab.ws / "adir").mkdir()
    line = stderr_error(view(lab, "adir"), 2)
    assert line.startswith("error: adir is a directory (code 2) — "), line
    assert "search PATTERN adir" in line


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads a 000 file")
def test_an_unreadable_file_exits_1_with_strerror(lab: Lab) -> None:
    write(lab.ws / "locked.txt", b"secret\n", 0o000)
    r = view(lab, "--json", "locked.txt")
    assert r.returncode == 1, said(r)
    d = doc_of(r)
    assert d["verdict"] == f"cannot read locked.txt: {os.strerror(errno.EACCES)}"


def test_view_writes_nothing_to_the_workspace(lab: Lab, big: Any) -> None:
    before = sorted(str(p) for p in lab.ws.rglob("*"))
    view(lab, "--json", "big.txt")
    view(lab, "--text", "big.txt:400")
    assert sorted(str(p) for p in lab.ws.rglob("*")) == before


# ── FR-21: the contract ───────────────────────────────────────────────────────────────────────


def test_manifest(lab: Lab) -> None:
    r = view(lab, "--agent-info")
    assert r.returncode == 0, said(r)
    info = doc_of(r)
    assert schema.errors(info, schema.load("agent-info.schema.json")) == []
    assert info["tool"] == "view"
    assert (info["mutating"], info["destructive"]) == (False, False)
    assert info["probe"] == ["/etc/os-release"]
    assert set(info["exit_codes"]) == {"0", "1", "2", "3"}
    assert info["envelopes"] == []
    assert "--columns" in info["flags"]


def test_the_probe_runs(lab: Lab) -> None:
    d = ok_json(view(lab, "--json", "/etc/os-release"))
    assert d["target"] == "/etc/os-release"


def test_help_is_within_40_lines(lab: Lab) -> None:
    r = view(lab, "--help")
    assert r.returncode == 0
    lines = r.stdout.splitlines()
    assert 0 < len(lines) <= 40 and lines[0].startswith("view: ")


def test_one_event_per_invocation(lab: Lab, big: Any) -> None:
    write(lab.ws / "app.o", BINARIES[0][1])
    (lab.ws / "adir").mkdir()
    expected: list[int] = []
    for args in (
        ["--json", "big.txt"],
        ["--text", "big.txt:40"],
        ["--json", "nope.txt"],
        ["big.txt:500"],
        ["adir"],
        ["--json", "app.o"],
        [],
        ["--no-such-flag", "big.txt"],
    ):
        r = view(lab, *args)
        expected.append(r.returncode)
        assert len(events(lab.scratch, SESSION)) == len(expected), args
    assert expected == [0, 0, 3, 2, 2, 0, 2, 2]
    evs = events(lab.scratch, SESSION)
    assert [e["exit"] for e in evs] == expected
    event_schema = schema.load("event.schema.json")
    for ev in evs:
        assert (ev["tool"], ev["session"]) == ("view", SESSION)
        assert schema.errors(ev, event_schema) == []


def test_header_in_text_mode_matches_rule_12(lab: Lab, big: Any) -> None:
    out = text_of(view(lab, "--text", "big.txt:40-80"))
    assert re.match(r"^[a-z][a-z0-9-]*: .+ \[[^]]+\]$", out[0])
    assert out[0] == "view: big.txt [lines 40-80 of 412]"
