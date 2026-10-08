"""symbols (feature 011, slice 1, T001) against contracts/symbols-cli.md, data-model.md, research R1-R4, R7.

Written from the contract alone, before the tool. Every fixture is a source file the test writes into a
temporary workspace (a directory holding `.git`, so the workspace root is defined, FR-1). Every expected
name, kind, line range, count and order comes from the test's own fixture tables (P005): a line number is
found by locating a needle in the text the test wrote, never read from `symbols`' output (P004).

Ambiguities settled here (the contract is the authority; the report lists them):
- Global flags (`--json`, `--text`) are placed before the subcommand.
- A signature is compared with whitespace removed: research R2 regenerates it with `ast.unparse`, which
  prints `force: bool=False`, while the contract's example prints `force: bool = False`.
- The nesting indentation in `outline`'s text sits between the range and the kind (the contract example:
  ` 12-48   class` against ` 30-41     method`); it is checked as "kind column - 2 x depth is constant".
- The kind of a Python method is `method` and of a function inside a function `nested` (data-model); the
  fixtures avoid classes inside classes or functions, whose kind is not pinned.
- `cache stale: N file(s) changed`: the plural is not pinned (the contract writes `files`, SC-5 `file`).
- JS imports name the file with its extension (`./util.js`), and shell `source` and the sourced file sit
  side by side at the workspace root, so resolution relative to the importer and to the root agree.
- Files skipped as binary or over 1 MiB: the spec says they are "counted in the verdict"; only the word
  `skipped` in the building call's verdict is checked, not the wording of the count.
- `def`'s ranking key "class and function before method" (R4) and "top level before method" (FR-5) agree
  on the fixture, which has no class named like a function.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
import schema
from conftest import TOOLS_DIR, base_env, events

SYMBOLS = TOOLS_DIR / "symbols"
SESSION = "symbols-t001"
Proc = subprocess.CompletedProcess[str]

pytestmark = pytest.mark.skipif(not SYMBOLS.exists(), reason="tools/bin/symbols is not written yet (T003)")

CACHE_TAIL = re.compile(
    r"; (cache: fresh|cache: not used \(outside the index: parsed directly\)|cache: built \((\d+) files?\)"
    r"|cache stale: (\d+) files? changed, (\d+) removed; rebuilt)$"
)
OUTLINE_LINE = re.compile(r"^\s*(\d+)-(\d+)\s+(class|function|method|nested|type)\s+(.+?)\s*$")
DEF_LINE = re.compile(r"^(\S+?):(\d+)\s+(\S+)\s+(\S+)\s+(.+?)\s*$")
GROUP_FN = re.compile(r"^── (\S+) \((\S+):(\d+)-(\d+)\) ──$")
GROUP_TOP = re.compile(r"^── \(top level\) (\S+) ──$")
SITE_LINE = re.compile(r"^(\S+?):(\d+)\s+(.*?)\s*$")
DEP_LINE = re.compile(r"^(\S+)\s+(direct|indirect)\s+(.*?)\s*$")


# ── the lab: a home, a workspace (with .git) and a scratch root, as siblings in tmp_path ─────────


@dataclass
class Lab:
    tmp: Path
    home: Path
    ws: Path
    scratch: Path

    def env(self) -> dict[str, str]:
        return base_env(self.scratch, SESSION, HOME=str(self.home), COLUMNS="1000")


def make_lab(tmp_path: Path, git: bool = True) -> Lab:
    tmp = Path(os.path.realpath(tmp_path))
    lab = Lab(tmp, tmp / "home", tmp / "ws", tmp / "scratch")
    lab.home.mkdir()
    lab.ws.mkdir()
    if git:
        (lab.ws / ".git").mkdir()
        (lab.ws / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
    return lab


@pytest.fixture
def lab(tmp_path: Path) -> Lab:
    return make_lab(tmp_path)


def symbols(lab: Lab, *args: str, cwd: Path | None = None, timeout: float = 30) -> Proc:
    """conftest.run's conventions (stdin /dev/null, no controlling terminal, a timeout), plus a cwd."""
    return subprocess.run(
        [sys.executable, str(SYMBOLS), *args],
        cwd=str(cwd or lab.ws),
        env=lab.env(),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=timeout,
        start_new_session=True,
    )


def said(r: Proc) -> str:
    return f"exit {r.returncode}\n{r.stdout}\n{r.stderr}"


def doc_of(r: Proc) -> dict[str, Any]:
    try:
        d: dict[str, Any] = json.loads(r.stdout)
    except ValueError:
        raise AssertionError(f"stdout is not one JSON object:\n{said(r)}") from None
    assert list(d)[:3] == ["tool", "target", "scope"], d
    assert d["tool"] == "symbols"
    assert d["exit"] == r.returncode
    return d


def as_json(lab: Lab, *args: str, code: int = 0, **kw: Any) -> dict[str, Any]:
    r = symbols(lab, "--json", *args, **kw)
    assert r.returncode == code, said(r)
    d = doc_of(r)
    assert CACHE_TAIL.search(d["verdict"]), d["verdict"]  # every verdict ends with the cache state
    return d


def as_text(lab: Lab, *args: str, code: int = 0, **kw: Any) -> list[str]:
    r = symbols(lab, "--text", *args, **kw)
    assert r.returncode == code, said(r)
    out = r.stdout.splitlines()
    assert out[0].startswith("symbols: ") and out[1].startswith("verdict: "), out[:2]
    assert CACHE_TAIL.search(out[1]), out[1]
    return out


def plant(root: Path, files: dict[str, str | bytes]) -> None:
    for rel, data in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, str):
            p.write_text(data)
        else:
            p.write_bytes(data)


def line_of(src: str, needle: str) -> int:
    """The 1-based line of the one line of the test's own text holding `needle`."""
    hits = [i for i, text in enumerate(src.splitlines(), 1) if needle in text]
    assert len(hits) == 1, (needle, hits)
    return hits[0]


def squash(sig: str) -> str:
    return re.sub(r"\s+", "", sig).rstrip(":")


# ── SC-1 · outline: a Python file of exactly 14 classes and functions ────────────────────────────

MODELS = '''\
"""Fixture: exactly fourteen classes and functions."""
import functools


class Base(dict):
    def __init__(self, ident):
        self.ident = ident
        return MARK_BODY_01


class Order(Base):
    def save(self, force: bool = False) -> None:
        return MARK_BODY_02

    @property
    def total(self) -> int:
        return MARK_BODY_03

    async def refresh(self):
        return MARK_BODY_04

    def checkout(self):
        def validate(item):
            return MARK_BODY_05

        return validate(MARK_BODY_06)


def helper(x):
    """DOCSTRING_MARK"""
    return MARK_BODY_07


@functools.lru_cache(maxsize=None)
@functools.cache
def decorated(y):
    return MARK_BODY_08


async def fetch(url: str) -> bytes:
    return MARK_BODY_09


def build(
    name: str,
    *,
    size: int = 3,
) -> dict:
    return MARK_BODY_10


def outer():
    def middle():
        return MARK_BODY_11

    return MARK_BODY_12
'''

# (name, qual, kind, depth, start needle, end needle, signature)
MODELS_DEFS: list[tuple[str, str, str, int, str, str, str]] = [
    ("Base", "Base", "class", 0, "class Base(dict):", "MARK_BODY_01", "class Base(dict)"),
    ("__init__", "Base.__init__", "method", 1, "def __init__", "MARK_BODY_01", "def __init__(self, ident)"),
    ("Order", "Order", "class", 0, "class Order(Base):", "MARK_BODY_06", "class Order(Base)"),
    ("save", "Order.save", "method", 1, "def save", "MARK_BODY_02",
     "def save(self, force: bool = False) -> None"),
    ("total", "Order.total", "method", 1, "@property", "MARK_BODY_03", "def total(self) -> int"),
    ("refresh", "Order.refresh", "method", 1, "async def refresh", "MARK_BODY_04", "async def refresh(self)"),
    ("checkout", "Order.checkout", "method", 1, "def checkout", "MARK_BODY_06", "def checkout(self)"),
    ("validate", "Order.checkout.validate", "nested", 2, "def validate", "MARK_BODY_05",
     "def validate(item)"),
    ("helper", "helper", "function", 0, "def helper", "MARK_BODY_07", "def helper(x)"),
    ("decorated", "decorated", "function", 0, "@functools.lru_cache", "MARK_BODY_08", "def decorated(y)"),
    ("fetch", "fetch", "function", 0, "async def fetch", "MARK_BODY_09",
     "async def fetch(url: str) -> bytes"),
    ("build", "build", "function", 0, "def build(", "MARK_BODY_10",
     "def build(name: str, *, size: int = 3) -> dict"),
    ("outer", "outer", "function", 0, "def outer", "MARK_BODY_12", "def outer()"),
    ("middle", "outer.middle", "nested", 1, "def middle", "MARK_BODY_11", "def middle()"),
]  # fmt: skip

# Distinctive lines that are not definitions (bodies, the docstring, the import) and must never be shown.
NOT_SHOWN = ["MARK_BODY", "DOCSTRING_MARK", "self.ident = ident", "import functools", "size: int = 3,"]


def expected_models() -> list[dict[str, Any]]:
    out = []
    for name, qual, kind, depth, start, end, sig in MODELS_DEFS:
        out.append(
            {"name": name, "qual": qual, "kind": kind, "depth": depth, "sig": sig,
             "start": line_of(MODELS, start), "end": line_of(MODELS, end)}
        )  # fmt: skip
    return sorted(out, key=lambda e: e["start"])  # source order (FR-4); starts are distinct here


def test_the_fixture_has_14_definitions() -> None:
    assert len(MODELS_DEFS) == 14
    starts = [e["start"] for e in expected_models()]
    assert len(set(starts)) == 14


@pytest.fixture
def models(lab: Lab) -> Lab:
    plant(lab.ws, {"app/models.py": MODELS})
    return lab


def test_outline_json_lists_exactly_the_14_definitions(models: Lab) -> None:
    r = symbols(models, "--json", "outline", "app/models.py")
    assert r.returncode == 0, said(r)
    d = doc_of(r)
    assert d["target"] == "app/models.py"
    assert d["scope"] == "14 definitions, exact (python)"
    assert d["verdict"].startswith("14 definitions in app/models.py (exact: python syntax tree); ")
    assert d["path"] == "app/models.py"
    assert d["precision"] == "exact"
    got = [
        {k: e[k] for k in ("name", "qual", "kind", "depth", "start", "end")} | {"sig": squash(e["sig"])}
        for e in d["definitions"]
    ]
    want = [e | {"sig": squash(e["sig"])} for e in expected_models()]
    assert got == want


def test_outline_text_lines_carry_range_kind_and_signature(models: Lab) -> None:
    out = as_text(models, "outline", "app/models.py")
    assert out[0] == "symbols: app/models.py [14 definitions, exact (python)]"
    body = out[2:]
    assert len(body) == 14, body
    want = expected_models()
    columns = []
    for line, e in zip(body, want, strict=True):
        m = OUTLINE_LINE.match(line)
        assert m, line
        assert (int(m[1]), int(m[2]), m[3]) == (e["start"], e["end"], e["kind"]), (line, e)
        assert squash(m[4]) == squash(e["sig"]), (line, e)
        columns.append(m.start(3) - 2 * e["depth"])
    assert len(set(columns)) == 1, f"kind column is not indented two spaces per level: {body}"


@pytest.mark.parametrize("mode", ["--json", "--text"])
def test_outline_shows_no_body_line(models: Lab, mode: str) -> None:
    r = symbols(models, mode, "outline", "app/models.py")
    assert r.returncode == 0, said(r)
    for needle in NOT_SHOWN:
        assert needle not in r.stdout, needle


def test_outline_of_a_missing_file_is_exit_3(models: Lab) -> None:
    r = symbols(models, "--json", "outline", "app/nope.py")
    assert r.returncode == 3, said(r)
    doc_of(r)


def test_outline_of_a_file_outside_the_workspace_is_answered(models: Lab) -> None:
    """Spec edge case, and the probe's shape: its own source, a Python file outside the workspace."""
    d = as_json(models, "outline", str(SYMBOLS))
    assert d["precision"] == "exact"
    assert len(d["definitions"]) >= 1


# ── SC-2 · def: ranked, qualified, not found ────────────────────────────────────────────────────

RANKED = {
    "lib/a.py": "X = 1\n\n\ndef save():\n    return X\n",
    "lib/b.py": "Y = 2\n\n\ndef save():\n    return Y\n",
    "lib/save_ops.py": "def save(target):\n    return target\n",
    "app/orders.py": (
        "class Order:\n    def save(self):\n        return 1\n\n\n"
        "class Cart:\n    def save(self, quick=False):\n        return 2\n"
    ),
    "app/zz.py": "def outer():\n    def save():\n        return 3\n\n    return save\n",
    "web/save.js": "function save(record) {\n  return record;\n}\n",
}
# R4 applied by hand to the table above: exact before text-based; function before method before nested;
# NAME in the path; then path, then line.
RANKED_ORDER = [
    ("lib/save_ops.py", "def save(target)", "function", "save", "exact"),
    ("lib/a.py", "def save():", "function", "save", "exact"),
    ("lib/b.py", "def save():", "function", "save", "exact"),
    ("app/orders.py", "def save(self):", "method", "Order.save", "exact"),
    ("app/orders.py", "def save(self, quick", "method", "Cart.save", "exact"),
    ("app/zz.py", "def save():", "nested", "outer.save", "exact"),
    ("web/save.js", "function save(", "function", None, "text-based"),
]


def ranked_expect() -> list[tuple[str, int]]:
    return [(p, line_of(RANKED[p], needle)) for p, needle, *_ in RANKED_ORDER]


@pytest.fixture
def ranked(lab: Lab) -> Lab:
    plant(lab.ws, RANKED)
    return lab


def test_def_ranks_best_first_json(ranked: Lab) -> None:
    d = as_json(ranked, "def", "save")
    assert d["scope"] == f"{len(RANKED_ORDER)} definitions, mixed"
    defs = d["definitions"]
    assert [(e["path"], e["line"]) for e in defs] == ranked_expect()
    for e, (_, _, kind, qual, precision) in zip(defs, RANKED_ORDER, strict=True):
        assert e["precision"] == precision, e
        if precision == "exact":
            assert (e["kind"], e["qual"]) == (kind, qual), e
    assert d["ranking"], "the stated order is part of the data"
    best_path, best_line = ranked_expect()[0]
    assert d["verdict"].startswith(
        f"save is defined in {len(RANKED_ORDER)} places; best first: {best_path}:{best_line}"
    )


def test_def_text_first_body_line_is_the_best_definition(ranked: Lab) -> None:
    out = as_text(ranked, "def", "save")
    assert out[0] == f"symbols: save [{len(RANKED_ORDER)} definitions, mixed]"
    rows = [DEF_LINE.match(x) for x in out[2:]]
    assert all(rows), out
    assert [(m[1], int(m[2])) for m in rows if m] == ranked_expect()
    first = rows[0]
    assert first and first[3] == "function" and squash(first[5]) == squash("def save(target)")


def test_def_by_qualified_name_finds_only_that_definition(ranked: Lab) -> None:
    d = as_json(ranked, "def", "Cart.save")
    assert d["scope"].startswith("1 definition") and d["scope"].endswith(", exact (python)"), d["scope"]
    assert [(e["path"], e["line"], e["qual"]) for e in d["definitions"]] == [
        ("app/orders.py", line_of(RANKED["app/orders.py"], "def save(self, quick"), "Cart.save")
    ]


def test_def_of_an_unknown_name_is_exit_3_with_the_search_remedy(ranked: Lab) -> None:
    r = symbols(ranked, "--json", "def", "no_such_name_xyz")
    assert r.returncode == 3, said(r)
    d = doc_of(r)
    assert d["scope"] == "not found"
    assert re.match(rf"no definition of no_such_name_xyz in {len(RANKED)} indexed files?\b", d["verdict"]), d
    assert "do instead: search -w no_such_name_xyz" in d["lines"], d["lines"]
    t = symbols(ranked, "--text", "def", "no_such_name_xyz")
    assert t.returncode == 3
    assert "do instead: search -w no_such_name_xyz" in t.stdout.splitlines()


# ── SC-3 · callers: exactly 3 call sites, grouped, text-based ───────────────────────────────────

CALLERS = {
    "app/orders.py": (
        "class Order:\n"
        "    def save(self):\n"
        "        return 1\n"
        "\n"
        "    def checkout(self):\n"
        "        # self.save() in a comment must not count\n"
        '        note = "call save() later"\n'
        "        self.save()\n"
        "        if note:\n"
        "            self.save(force=True)\n"
        "        return note\n"
        "\n"
        "\n"
        "def helper():\n"
        "    return 0\n"
    ),
    "app/cli.py": "from app.orders import Order\n\norder = Order()\norder.save()\n",
}


def callers_expect() -> set[tuple[str, int, str, tuple[str, int, int] | None]]:
    src = CALLERS["app/orders.py"]
    enc = ("Order.checkout", line_of(src, "def checkout"), line_of(src, "return note"))
    return {
        ("app/orders.py", line_of(src, "        self.save()"), "self.save()", enc),
        ("app/orders.py", line_of(src, "self.save(force=True)"), "self.save(force=True)", enc),
        ("app/cli.py", line_of(CALLERS["app/cli.py"], "order.save()"), "order.save()", None),
    }


@pytest.fixture
def callers(lab: Lab) -> Lab:
    plant(lab.ws, CALLERS)
    return lab


def test_callers_json_returns_the_3_call_sites_grouped(callers: Lab) -> None:
    d = as_json(callers, "callers", "save")
    assert "text-based" in d["scope"] and d["scope"].startswith("3 call sites"), d["scope"]
    assert d["verdict"].startswith("3 call sites of save "), d["verdict"]
    assert "text-based" in d["verdict"]
    assert d["precision"] == "text-based"
    assert d["groups"] == 2
    got = set()
    for s in d["call_sites"]:
        enc = s["enclosing"]
        got.add(
            (
                s["path"],
                s["line"],
                s["text"],
                None if enc is None else (enc["qual"], enc["start"], enc["end"]),
            )
        )
    assert got == callers_expect()


def test_callers_text_groups_by_enclosing_function(callers: Lab) -> None:
    out = as_text(callers, "callers", "save")
    assert out[0].startswith("symbols: save [3 call sites") and "text-based" in out[0], out[0]
    groups: dict[str, list[tuple[str, int, str]]] = {}
    current = None
    for line in out[2:]:
        if (m := GROUP_FN.match(line)) is not None:
            current = f"{m[1]} {m[2]}:{m[3]}-{m[4]}"
        elif (m := GROUP_TOP.match(line)) is not None:
            current = f"(top level) {m[1]}"
        else:
            m = SITE_LINE.match(line)
            assert m and current is not None, line
            groups.setdefault(current, []).append((m[1], int(m[2]), m[3]))
    want: dict[str, set[tuple[str, int, str]]] = {}
    for path, line, text, enc in callers_expect():
        key = f"(top level) {path}" if enc is None else f"{enc[0]} {path}:{enc[1]}-{enc[2]}"
        want.setdefault(key, set()).add((path, line, text))
    assert {k: set(v) for k, v in groups.items()} == want
    assert sum(len(v) for v in groups.values()) == 3


def test_callers_with_no_call_site_is_exit_0(callers: Lab) -> None:
    d = as_json(callers, "callers", "helper")
    assert d["verdict"].startswith("0 call sites of helper"), d["verdict"]
    assert d["call_sites"] == []
    assert "text-based" in d["scope"]


# ── SC-4 · dependents: direct by names, then indirect ───────────────────────────────────────────

DEPENDENTS = {
    "app/__init__.py": "",
    "app/models.py": (
        "class Order:\n    pass\n\n\nclass Customer:\n    pass\n\n\ndef make():\n    return Order()\n"
    ),
    "app/orders.py": (
        "from app.models import Order, Customer\n\n\ndef place():\n    return Order(), Customer()\n"
    ),
    "app/report.py": "from .models import make\n\n\ndef report():\n    return make()\n",
    "main.py": "from app.orders import place\n\nplace()\n",
    "app/lonely.py": "def alone():\n    return 1\n",
}
# (path, depth, names or None, via needle): orders imports 2 names, report 1 (relative), main via orders.
DEPENDENTS_ORDER = [
    ("app/orders.py", 1, 2, "app.models"),
    ("app/report.py", 1, 1, ".models"),
    ("main.py", 2, None, "app/orders.py"),
]


@pytest.fixture
def deps(lab: Lab) -> Lab:
    plant(lab.ws, DEPENDENTS)
    return lab


def test_dependents_json_ranks_direct_by_names_then_indirect(deps: Lab) -> None:
    d = as_json(deps, "dependents", "app/models.py")
    assert d["scope"] == "3 dependents"
    assert d["verdict"].startswith("3 files import app/models.py: 2 directly, 1 through them"), d["verdict"]
    assert d["targets"] == ["app/models.py"]
    got = d["dependents"]
    assert [(e["path"], e["depth"]) for e in got] == [(p, n) for p, n, _, _ in DEPENDENTS_ORDER]
    for e, (_, _, names, via) in zip(got, DEPENDENTS_ORDER, strict=True):
        if names is not None:
            assert e["names"] == names, e
        assert via in e["via"], e


def test_dependents_text_marks_direct_and_indirect(deps: Lab) -> None:
    out = as_text(deps, "dependents", "app/models.py")
    assert out[0] == "symbols: app/models.py [3 dependents]"
    rows = [DEP_LINE.match(x) for x in out[2:]]
    assert all(rows), out
    assert [(m[1], m[2]) for m in rows if m] == [
        (p, "direct" if n == 1 else "indirect") for p, n, _, _ in DEPENDENTS_ORDER
    ]
    assert "(2 names)" in out[2] and "(1 name)" in out[3], out
    assert "via app/orders.py" in out[4], out


def test_dependents_of_a_file_nothing_imports_is_exit_0(deps: Lab) -> None:
    d = as_json(deps, "dependents", "app/lonely.py")
    assert "0 dependents" in d["scope"] + " " + d["verdict"], d
    assert d["dependents"] == []


def test_dependents_of_a_file_outside_the_index_is_exit_3(deps: Lab) -> None:
    r = symbols(deps, "--json", "dependents", "app/missing.py")
    assert r.returncode == 3, said(r)
    doc_of(r)


# ── SC-5 · the cache: built, fresh, stale; in the session scratch ───────────────────────────────

CACHED = {
    "pkg/one.py": "def helper():\n    return 1\n",
    "pkg/two.py": "def other():\n    return 2\n",
    "pkg/three.py": "def third():\n    return 3\n",
}


def bump(p: Path, text: str) -> None:
    """Rewrite p and move its mtime forward, so (size, mtime_ns) differs however coarse the clock."""
    st = p.stat()
    p.write_text(text)
    os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))


def cache_of(d: dict[str, Any]) -> dict[str, Any]:
    c: dict[str, Any] = d["cache"]
    return c


def ws_files(lab: Lab) -> set[str]:
    return {str(p.relative_to(lab.ws)) for p in lab.ws.rglob("*") if p.is_file()}


def test_cache_built_then_fresh_then_stale_answers_from_new_content(lab: Lab) -> None:
    plant(lab.ws, CACHED)
    before = ws_files(lab)
    d = as_json(lab, "def", "helper")
    assert d["verdict"].endswith(f"; cache: built ({len(CACHED)} files)"), d["verdict"]
    assert cache_of(d)["state"] == "built" and cache_of(d)["files"] == len(CACHED)
    assert [(e["path"], e["line"]) for e in d["definitions"]] == [("pkg/one.py", 1)]

    d = as_json(lab, "def", "helper")
    assert d["verdict"].endswith("; cache: fresh"), d["verdict"]
    assert cache_of(d)["state"] == "fresh"

    moved = "# a comment\n# another\n\ndef helper():\n    return 10\n"
    bump(lab.ws / "pkg/one.py", moved)
    d = as_json(lab, "def", "helper")
    assert re.search(r"; cache stale: 1 files? changed, 0 removed; rebuilt$", d["verdict"]), d["verdict"]
    assert (cache_of(d)["changed"], cache_of(d)["removed"]) == (1, 0)
    assert [(e["path"], e["line"]) for e in d["definitions"]] == [
        ("pkg/one.py", line_of(moved, "def helper"))
    ]

    renamed = "def renamed_helper():\n    return 11\n"
    bump(lab.ws / "pkg/one.py", renamed)
    r = symbols(lab, "--json", "def", "helper")
    assert r.returncode == 3, said(r)
    assert re.search(r"cache stale: 1 files? changed", doc_of(r)["verdict"]), doc_of(r)["verdict"]
    d = as_json(lab, "def", "renamed_helper")
    assert d["verdict"].endswith("; cache: fresh"), d["verdict"]
    assert [(e["path"], e["line"]) for e in d["definitions"]] == [("pkg/one.py", 1)]

    (lab.ws / "pkg/two.py").unlink()
    d = as_json(lab, "def", "third")
    assert re.search(r"; cache stale: 0 files? changed, 1 removed; rebuilt$", d["verdict"]), d["verdict"]
    assert (cache_of(d)["changed"], cache_of(d)["removed"]) == (0, 1)
    assert symbols(lab, "--json", "def", "other").returncode == 3

    assert ws_files(lab) == before - {"pkg/two.py"}, "the index must not be written into the workspace"


def test_index_lives_in_the_session_scratch_and_rebuilds_when_cleared(lab: Lab) -> None:
    plant(lab.ws, CACHED)
    as_json(lab, "def", "helper")
    key = hashlib.sha256(os.path.realpath(lab.ws).encode()).hexdigest()[:12]
    index = lab.scratch / SESSION / "symbols" / f"{key}.json"
    assert index.is_file(), sorted(str(p) for p in lab.scratch.rglob("*"))
    data = json.loads(index.read_text())
    assert data["v"] == 1
    assert set(data["files"]) == set(CACHED)
    shutil.rmtree(lab.scratch / SESSION / "symbols")
    d = as_json(lab, "def", "helper")
    assert d["verdict"].endswith(f"; cache: built ({len(CACHED)} files)"), d["verdict"]


def test_ignored_files_are_not_indexed(lab: Lab) -> None:
    plant(
        lab.ws,
        {
            ".gitignore": "generated/\n",
            "generated/gen.py": "def only_here():\n    return 1\n",
            ".git/hooks/hook.py": "def only_here():\n    return 2\n",
            "src/real.py": "def only_here():\n    return 3\n",
        },
    )
    d = as_json(lab, "def", "only_here")
    assert [(e["path"], e["line"]) for e in d["definitions"]] == [("src/real.py", 1)]


# ── text-based languages (R3): one definition and one import each ───────────────────────────────

LANGS = {
    "web/util.js": "// helpers\nexport function formatDate(d) {\n  return d.toISOString();\n}\n",
    "web/app.js": "import { formatDate } from './util.js';\n\nconsole.log(formatDate(new Date()));\n",
    "web/widget.ts": 'export class Widget {\n  render(): string {\n    return "w";\n  }\n}\n',
    "pkg/store/store.go": (
        "package store\n\ntype Handle struct {\n\tpath string\n}\n\n"
        "func OpenStore(path string) (*Handle, error) {\n\treturn &Handle{path: path}, nil\n}\n"
    ),
    "cmd/app/main.go": (
        'package main\n\nimport (\n\t"fmt"\n\n\t"example.com/proj/pkg/store"\n)\n\n'
        'func main() {\n\th, _ := store.OpenStore("x")\n\tfmt.Println(h)\n}\n'
    ),
    "src/parser.rs": (
        "pub struct Token {\n    pub text: String,\n}\n\n"
        "pub fn parse_input(s: &str) -> usize {\n    s.len()\n}\n"
    ),
    "src/main.rs": 'mod parser;\n\nfn main() {\n    println!("{}", parser::parse_input("abc"));\n}\n',
    "lib.sh": '#!/bin/sh\nlog_line() {\n  echo "$1"\n}\n',
    "run.sh": "#!/bin/sh\nsource lib.sh\nlog_line hello\n",
    "scripts/deploy": "#!/bin/bash\nfunction deploy_now {\n  echo go\n}\n",
}
# (name, file, needle of the defining line)
LANG_DEFS = [
    ("formatDate", "web/util.js", "export function formatDate"),
    ("Widget", "web/widget.ts", "export class Widget"),
    ("OpenStore", "pkg/store/store.go", "func OpenStore"),
    ("parse_input", "src/parser.rs", "pub fn parse_input"),
    ("log_line", "lib.sh", "log_line() {"),
    ("deploy_now", "scripts/deploy", "function deploy_now"),
]
# (target, importer)
LANG_IMPORTS = [
    ("web/util.js", "web/app.js"),
    ("pkg/store/store.go", "cmd/app/main.go"),
    ("src/parser.rs", "src/main.rs"),
    ("lib.sh", "run.sh"),
]


@pytest.fixture
def langs(lab: Lab) -> Lab:
    plant(lab.ws, LANGS)
    return lab


@pytest.mark.parametrize(("name", "path", "needle"), LANG_DEFS, ids=[x[0] for x in LANG_DEFS])
def test_text_based_definition(langs: Lab, name: str, path: str, needle: str) -> None:
    d = as_json(langs, "def", name)
    assert "text-based" in d["scope"], d["scope"]
    assert [(e["path"], e["line"], e["precision"]) for e in d["definitions"]] == [
        (path, line_of(LANGS[path], needle), "text-based")
    ]


@pytest.mark.parametrize(("target", "importer"), LANG_IMPORTS, ids=[x[0] for x in LANG_IMPORTS])
def test_text_based_import(langs: Lab, target: str, importer: str) -> None:
    d = as_json(langs, "dependents", target)
    assert [(e["path"], e["depth"]) for e in d["dependents"]] == [(importer, 1)]


# ── fallbacks and skips ─────────────────────────────────────────────────────────────────────────

BROKEN = "def good_one(a):\n    return a\n\n\ndef broken(:\n    pass\n"


def test_a_python_file_that_does_not_parse_falls_back_to_text(lab: Lab) -> None:
    plant(lab.ws, {"pkg/broken.py": BROKEN, "pkg/fine.py": "def fine():\n    return 1\n"})
    d = as_json(lab, "def", "good_one")
    assert [(e["path"], e["line"], e["precision"]) for e in d["definitions"]] == [
        ("pkg/broken.py", line_of(BROKEN, "def good_one"), "text-based")
    ]
    assert "text-based" in d["scope"]
    d = as_json(lab, "outline", "pkg/broken.py")
    assert d["precision"] == "text-based"
    assert ("good_one", line_of(BROKEN, "def good_one")) in [
        (e["name"], e["start"]) for e in d["definitions"]
    ]
    d = as_json(lab, "def", "fine")
    assert d["definitions"][0]["precision"] == "exact"


def test_binary_and_large_files_are_skipped(lab: Lab) -> None:
    big = "def big_fn():\n    return 1\n" + "# padding padding padding padding padding padding\n" * 25_000
    assert len(big.encode()) > 1024 * 1024
    plant(
        lab.ws,
        {
            "ok.py": "def ok_fn():\n    return 1\n",
            "big.py": big,
            "weird.py": b"\x00\x01\x02def binary_fn():\n    return 1\n\x00",
        },
    )
    d = as_json(lab, "def", "ok_fn")
    assert d["verdict"].endswith("; cache: built (1 files)") or d["verdict"].endswith(
        "; cache: built (1 file)"
    )
    assert "skipped" in d["verdict"], d["verdict"]
    for name in ("big_fn", "binary_fn"):
        r = symbols(lab, "--json", "def", name)
        assert r.returncode == 3, said(r)
        assert re.match(rf"no definition of {name} in 1 indexed files?\b", doc_of(r)["verdict"])


def test_outside_a_repository_the_workspace_is_the_current_directory(tmp_path: Path) -> None:
    lab = make_lab(tmp_path, git=False)
    plant(lab.ws, {"m.py": "def here():\n    return 1\n"})
    d = as_json(lab, "def", "here")
    assert [(e["path"], e["line"]) for e in d["definitions"]] == [("m.py", 1)]


# ── SC-2's bound: a warm def on 1,000 files under 2 s ────────────────────────────────────────────


def generated_module(p: int, f: int) -> str:
    out = ["import os\n\n"]
    for c in range(2):
        out.append(f"\nclass Cls_{p}_{f}_{c}:\n")
        for m in range(2):
            out.append(f"    def meth_{m}(self, x):\n        return x + {m}\n\n")
    for k in range(3):
        out.append(f"\ndef fn_{p}_{f}_{k}(a, b=1):\n    return os.sep, a, b\n\n")
    return "".join(out)


def test_def_is_under_2_seconds_warm_on_1000_files(lab: Lab) -> None:
    files = {f"pkg{p:02d}/mod{f:02d}.py": generated_module(p, f) for p in range(20) for f in range(50)}
    assert len(files) == 1000
    plant(lab.ws, files)
    cold = as_json(lab, "def", "fn_0_0_0", timeout=120)
    assert cold["verdict"].endswith("; cache: built (1000 files)"), cold["verdict"]

    target = "pkg07/mod33.py"
    t0 = time.monotonic()
    r = symbols(lab, "--json", "def", "fn_7_33_1", timeout=60)
    elapsed = time.monotonic() - t0
    assert r.returncode == 0, said(r)
    d = doc_of(r)
    assert d["verdict"].endswith("; cache: fresh"), d["verdict"]
    assert [(e["path"], e["line"]) for e in d["definitions"]] == [
        (target, line_of(files[target], "def fn_7_33_1"))
    ]
    assert elapsed < 2.0, f"warm def took {elapsed:.2f} s"


# ── the contract: manifest, help, usage, one event per call ─────────────────────────────────────

LANGUAGES = {
    "python": "exact",
    "javascript": "text-based",
    "typescript": "text-based",
    "go": "text-based",
    "rust": "text-based",
    "shell": "text-based",
}


def test_manifest(lab: Lab) -> None:
    r = symbols(lab, "--agent-info")
    assert r.returncode == 0, said(r)
    info = json.loads(r.stdout)
    assert schema.errors(info, schema.load("agent-info.schema.json")) == []
    assert info["tool"] == "symbols"
    assert info["mutating"] is False
    assert info["confirm_protocol"] is False
    assert info["destructive"] is False
    assert info["reads_stdin"] is False
    assert info["probe"] == ["outline", "/opt/timelike/bin/symbols"]
    assert set(info["exit_codes"]) == {"0", "1", "2", "3", "124"}
    assert info["languages"] == LANGUAGES
    assert "symbols" in info["index"] and info["index"].endswith(".json")


def test_help_is_within_40_lines(lab: Lab) -> None:
    r = symbols(lab, "--help")
    assert r.returncode == 0, said(r)
    lines = r.stdout.splitlines()
    assert 0 < len(lines) <= 40 and lines[0].startswith("symbols: ")


@pytest.mark.parametrize(
    "args", [[], ["bogus", "x"], ["outline"], ["def"]], ids=["none", "bogus", "outline", "def"]
)
def test_usage_errors_are_exit_2(lab: Lab, args: list[str]) -> None:
    assert symbols(lab, *args).returncode == 2


def test_one_event_per_call(lab: Lab) -> None:
    plant(lab.ws, CACHED)
    codes = []
    for args in (
        ["def", "helper"],
        ["def", "nothing_here"],
        ["callers", "helper"],
        ["outline", "pkg/one.py"],
    ):
        codes.append(symbols(lab, "--json", *args).returncode)
        assert len(events(lab.scratch, SESSION)) == len(codes), args
    assert codes == [0, 3, 0, 0]


# ── T006: paths the delegate's set did not reach (coverage), each on a fixture the test writes ───


def _sm() -> Any:
    import importlib.machinery
    import importlib.util

    loader = importlib.machinery.SourceFileLoader("timelike_symbols_under_test", str(SYMBOLS))
    spec = importlib.util.spec_from_loader("timelike_symbols_under_test", loader)
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


SM = _sm()


@pytest.mark.parametrize(
    ("args", "words"),
    [
        ([], "needs an action"),
        (["where", "x"], "unknown action"),
        (["def"], "takes one NAME"),
        (["outline", "a", "b"], "takes one FILE"),
        (["dependents"], "dependents needs FILE"),
    ],
)
def test_usage_errors_exit_2(lab: Lab, args: list[str], words: str) -> None:
    r = symbols(lab, "--json", *args)
    assert r.returncode == 2, said(r)
    assert words in r.stderr, said(r)


def test_rust_use_and_mod_resolve_to_files(lab: Lab) -> None:
    plant(
        lab.ws,
        {
            "src/lib.rs": "mod store;\npub fn run() {}\n",
            "src/store.rs": "pub fn keep() {}\n",
            "src/app/mod.rs": "pub fn start() {}\n",
            "src/main.rs": "use crate::app::start;\nfn main() { start(); }\n",
        },
    )
    d = as_json(lab, "--json", "dependents", "src/store.rs")
    assert [x["path"] for x in d["dependents"]] == ["src/lib.rs"]
    d = as_json(lab, "--json", "dependents", "src/app/mod.rs")
    assert [x["path"] for x in d["dependents"]] == ["src/main.rs"]


def test_shell_source_resolves_relative_to_the_importer(lab: Lab) -> None:
    plant(
        lab.ws,
        {"bin/lib/common.sh": "say() { echo hi; }\n", "bin/run.sh": "#!/bin/sh\n. lib/common.sh\nsay\n"},
    )
    d = as_json(lab, "--json", "dependents", "bin/lib/common.sh")
    assert [x["path"] for x in d["dependents"]] == ["bin/run.sh"]


def test_js_index_file_and_unresolved_imports(lab: Lab) -> None:
    plant(
        lab.ws,
        {
            "web/util/index.ts": "export function pad(s: string) { return s; }\n",
            "web/main.ts": "import { pad } from './util';\nimport x from 'react';\npad('a');\n",
        },
    )
    d = as_json(lab, "--json", "dependents", "web/util/index.ts")
    assert [x["path"] for x in d["dependents"]] == ["web/main.ts"]


def test_dependents_of_a_non_source_file_is_exit_3(lab: Lab) -> None:
    plant(lab.ws, {"a.py": "x = 1\n", "notes.txt": "hello\n"})
    r = symbols(lab, "--json", "dependents", "notes.txt")
    assert r.returncode == 3, said(r)


def test_outline_of_a_non_source_file_is_refused(lab: Lab) -> None:
    plant(lab.ws, {"a.py": "x = 1\n", "notes.txt": "hello\n"})
    r = symbols(lab, "--json", "outline", "notes.txt")
    assert r.returncode == 1, said(r)
    assert "not a source file" in doc_of(r)["verdict"]


def test_an_index_that_cannot_be_saved_still_answers(lab: Lab) -> None:
    plant(lab.ws, {"a.py": "def f():\n    return 1\n"})
    blocker = lab.tmp / "blocked"
    blocker.write_text("a file where the scratch root should be a directory")
    env = lab.env()
    env["TIMELIKE_SCRATCH_ROOT"] = str(blocker)
    r = subprocess.run(
        [sys.executable, str(SYMBOLS), "--json", "def", "f"],
        cwd=str(lab.ws), env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30,
    )  # fmt: skip
    assert r.returncode in (0, 1), said(r)


def test_the_walk_limit_is_exit_124_and_named(lab: Lab, monkeypatch: pytest.MonkeyPatch) -> None:
    plant(lab.ws, {f"m{i}.py": f"def f{i}():\n    return {i}\n" for i in range(5)})

    class Ctx:
        def scratch(self) -> Path:
            d = lab.tmp / "ctx-scratch"
            d.mkdir(exist_ok=True)
            return d

    monkeypatch.setattr(SM, "MAX_FILES", 2)
    index = SM.Index(Ctx(), str(lab.ws))
    index.refresh()
    assert index.limited
    assert "index incomplete" in index.clause()
    assert index.clause().rsplit("; ", 1)[-1].startswith("cache: built")


def test_text_patterns_edge_cases() -> None:
    js = SM.parse_text(
        "class A {\n  run(x) {\n    return go(x);\n  }\n}\nconst f = (a) => a;\n", "javascript"
    )
    kinds = {d["qual"]: d["kind"] for d in js["defs"]}
    assert kinds == {"A": "class", "A.run": "method", "f": "function"}
    go = SM.parse_text(
        'package p\nimport (\n  "fmt"\n  s "example.com/p/store"\n)\nfunc (r *T) M() {\n}\n', "go"
    )
    assert [i["path"] for i in go["imports"]] == ["fmt", "example.com/p/store"]
    assert go["defs"][0]["kind"] == "method"
    sh = SM.parse_text("function a {\n  b\n}\nb() {\n  :\n}\n", "shell")
    assert [d["name"] for d in sh["defs"]] == ["a", "b"]
    assert SM.language_of("x", b"#!/usr/bin/env python3\n") == "python"
    assert SM.language_of("x", b"#!/bin/bash\n") == "shell"
    assert SM.language_of("x.txt", b"hello") is None
