"""package-guard's version orderings and ranges (feature 013, T002; research R4).

The tables come from the two specifications' own examples: PEP 440's ordering and specifier sections, and
node-semver's README (its "Advanced Range Syntax" desugarings and its pre-release rule). The tool's
implementation is not consulted for an expected value.
"""

from __future__ import annotations

import pytest
from pgmod import PG

# PEP 440 § Summary of permitted suffixes and relative ordering — this exact sequence, ascending.
PEP440_ORDER = [
    "1.dev0", "1.0.dev456", "1.0a1", "1.0a2.dev456", "1.0a12.dev456", "1.0a12", "1.0b1.dev456", "1.0b2",
    "1.0b2.post345.dev456", "1.0b2.post345", "1.0rc1.dev456", "1.0rc1", "1.0", "1.0+abc.5", "1.0+abc.7",
    "1.0+5", "1.0.post456.dev34", "1.0.post456", "1.0.15", "1.1.dev1",
]  # fmt: skip


def test_pep440_order_is_the_specifications() -> None:
    parsed = [PG.py_version(v) for v in PEP440_ORDER]
    assert all(p is not None for p in parsed)
    keys = [p.key() for p in parsed]
    assert keys == sorted(keys)
    assert len(set(keys)) == len(keys)


@pytest.mark.parametrize(
    ("a", "b"),
    [("1.0", "1.0.0"), ("1.0", "1"), ("v1.0", "1.0"), ("1.0-1", "1.0.post1"), ("1.0alpha1", "1.0a1"),
     ("1.0.preview2", "1.0rc2"), ("1!1.0", "1!1.0.0")],
)  # fmt: skip
def test_pep440_equal_spellings(a: str, b: str) -> None:
    assert PG.py_version(a).key() == PG.py_version(b).key()


def admits(spec: str, version: str) -> bool:
    v = PG.py_version(version)
    return all(s.admits(v) for s in PG.py_specifier(spec))


@pytest.mark.parametrize(
    ("spec", "version", "want"),
    [
        ("==1.1.*", "1.1.post1", True),  # PEP 440 § Version matching
        ("==1.1", "1.1.0", True),
        ("==1.1", "1.1.dev1", False),
        ("==1.1", "1.1a1", False),
        ("==1.1.*", "1.1a1", True),
        ("==1.1.*", "1.2", False),
        ("!=1.1.*", "1.2", True),
        ("~=2.2", "2.3", True),  # >= 2.2, == 2.*
        ("~=2.2", "3.0", False),
        ("~=1.4.5", "1.4.9", True),  # >= 1.4.5, == 1.4.*
        ("~=1.4.5", "1.5.0", False),
        (">1.7", "1.7.1", True),  # PEP 440 § Exclusive ordered comparison
        (">1.7", "1.7.0.post1", False),
        (">1.7.post2", "1.7.1", True),
        ("<1.7", "1.7.0rc1", False),
        ("<1.7rc2", "1.7.0rc1", True),
        (">=1.0, <2", "1.5", True),
        (">=1.0, <2", "2.0", False),
        ("", "9.9", True),
        ("===1.0+local", "1.0+LOCAL", True),
    ],
)
def test_pep440_specifiers(spec: str, version: str, want: bool) -> None:
    assert admits(spec, version) is want


@pytest.mark.parametrize("bad", ["==1..2", ">=", "~=1", "<=1.*", "@@1"])
def test_pep440_unreadable_specifier(bad: str) -> None:
    with pytest.raises(PG.SpecError):
        PG.py_specifier(bad)


def rel(uploaded: object = None, yanked: bool = False) -> object:
    return PG.Release(uploaded, yanked)


def test_pip_picks_the_newest_final_skipping_yanked_and_pre() -> None:
    versions = {"1.0": rel(), "1.1": rel(yanked=True), "2.0rc1": rel(), "0.9": rel()}
    ranked, pre = PG.py_select(versions, [], False)
    assert [v.text for v, _ in ranked] == ["1.0", "0.9"] and pre is False
    ranked, _ = PG.py_select(versions, PG.py_specifier("==1.1"), False)  # PEP 592: a yanked release, pinned
    assert [v.text for v, _ in ranked] == ["1.1"]
    ranked, _ = PG.py_select(versions, [], True)  # --pre
    assert ranked[0][0].text == "2.0rc1"
    ranked, _ = PG.py_select({"2.0rc1": rel()}, [], False)  # only a pre-release exists
    assert [v.text for v, _ in ranked] == ["2.0rc1"]
    ranked, _ = PG.py_select(versions, PG.py_specifier(">=2.0rc1"), False)  # the specifier names one
    assert ranked[0][0].text == "2.0rc1"


# node-semver README § Advanced Range Syntax: each range and the comparators it desugars to.
NODE_DESUGAR = [
    ("1.2.3 - 2.3.4", ">=1.2.3 <=2.3.4"),
    ("1.2 - 2.3.4", ">=1.2.0 <=2.3.4"),
    ("1.2.3 - 2.3", ">=1.2.3 <2.4.0-0"),
    ("1.2.3 - 2", ">=1.2.3 <3.0.0-0"),
    ("*", ""),
    ("1.x", ">=1.0.0 <2.0.0-0"),
    ("1.2.x", ">=1.2.0 <1.3.0-0"),
    ("1", ">=1.0.0 <2.0.0-0"),
    ("1.2", ">=1.2.0 <1.3.0-0"),
    ("~1.2.3", ">=1.2.3 <1.3.0-0"),
    ("~1.2", ">=1.2.0 <1.3.0-0"),
    ("~1", ">=1.0.0 <2.0.0-0"),
    ("~0.2.3", ">=0.2.3 <0.3.0-0"),
    ("~1.2.3-beta.2", ">=1.2.3-beta.2 <1.3.0-0"),
    ("^1.2.3", ">=1.2.3 <2.0.0-0"),
    ("^0.2.3", ">=0.2.3 <0.3.0-0"),
    ("^0.0.3", ">=0.0.3 <0.0.4-0"),
    ("^1.2.3-beta.2", ">=1.2.3-beta.2 <2.0.0-0"),
    ("^0.0.3-beta", ">=0.0.3-beta <0.0.4-0"),
    ("^1.2.x", ">=1.2.0 <2.0.0-0"),
    ("^0.0.x", ">=0.0.0 <0.1.0-0"),
    ("^0.0", ">=0.0.0 <0.1.0-0"),
    ("^1.x", ">=1.0.0 <2.0.0-0"),
    ("^0.x", ">=0.0.0 <1.0.0-0"),
]


@pytest.mark.parametrize(("rng", "want"), NODE_DESUGAR)
def test_npm_ranges_desugar_as_node_semver_documents(rng: str, want: str) -> None:
    (comps,) = PG.npm_range(rng)
    assert " ".join(f"{op}{v}" for op, v in comps) == want


def sat(version: str, rng: str) -> bool:
    return PG.npm_satisfies(PG.npm_version(version), PG.npm_range(rng))


@pytest.mark.parametrize(
    ("version", "rng", "want"),
    [
        ("3.4.0-beta.2", ">1.2.3-alpha.3", False),  # README § Prerelease Tags: another tuple's pre-release
        ("1.2.3-alpha.7", ">1.2.3-alpha.3", True),
        ("1.2.3-alpha.1", ">1.2.3-alpha.3", False),
        ("3.4.5", ">1.2.3-alpha.3", True),
        ("1.2.4", "^1.2.3", True),
        ("2.0.0", "^1.2.3", False),
        ("2.0.0-beta", "^1.2.3", False),
        ("1.3.0", "1.2.x || >=1.3.0 <1.4.0", True),
        ("1.4.0", "1.2.x || >=1.3.0 <1.4.0", False),
        ("1.2.3", "=1.2.3", True),
        ("1.2.3", ">= 1.2.0 < 1.3", True),
        ("0.0.1", "", True),
    ],
)
def test_npm_satisfies(version: str, rng: str, want: bool) -> None:
    assert sat(version, rng) is want


def test_npm_version_order() -> None:
    order = [
        "1.0.0-alpha",
        "1.0.0-alpha.1",
        "1.0.0-alpha.beta",
        "1.0.0-beta",
        "1.0.0-beta.2",
        "1.0.0-beta.11",
        "1.0.0-rc.1",
        "1.0.0",
    ]  # semver.org § 11, ascending
    keys = [PG.npm_version(v).key() for v in order]
    assert keys == sorted(keys) and len(set(keys)) == len(keys)


@pytest.mark.parametrize("bad", ["^a.b", ">=1.2.3.4", "1.2.3 - x.y.z.w"])
def test_npm_unreadable_range(bad: str) -> None:
    with pytest.raises(PG.SpecError):
        PG.npm_range(bad)
