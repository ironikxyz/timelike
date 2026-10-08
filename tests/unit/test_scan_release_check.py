"""The gate's release check for bundled-class baseline entries (discovery revision 15; 007 FR-32 to FR-34).

Host-runnable, no Docker, no network. Every registry here is written by the test (cross-stack P005): a
packument and release tarballs the test packs itself, with integrities it computes, served from files
through `file://` URLs. The code under test chooses none of the versions it is judged on.
"""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import importlib.util
import io
import json
import sys
import tarfile
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[2]
TODAY = dt.date(2026, 10, 8)
NODE = "24.21.0"
IMAGE = "timelike-agent:local"
DIGEST = "sha256:" + "a9" * 32
LABEL = "scan/baseline/timelike-agent.json"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("scan_evaluate_release", REPO / "scan" / "evaluate.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ev = _load()


# --- a registry the test writes ----------------------------------------------------------------------


def _tarball(libs: dict[str, str | list[str]]) -> bytes:
    """An npm-shaped release tarball: package/package.json and one package.json per bundled copy.

    A list of versions puts the second and later copies under a nested node_modules, as npm does when two
    versions of one library are bundled.
    """
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:

        def add(name: str, doc: dict[str, Any]) -> None:
            data = json.dumps(doc).encode()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))

        add("package/package.json", {"name": "npm"})
        for lib, versions in libs.items():
            listed = [versions] if isinstance(versions, str) else versions
            add(f"package/node_modules/{lib}/package.json", {"name": lib, "version": listed[0]})
            for n, extra in enumerate(listed[1:]):
                add(
                    f"package/node_modules/holder{n}/node_modules/{lib}/package.json",
                    {"name": lib, "version": extra},
                )
    return buf.getvalue()


def registry(tmp_path: Path, releases: list[dict[str, Any]]) -> str:
    """Writes registry/npm (the packument) and one tarball per release; returns the registry's URL.

    Each release: version, time (YYYY-MM-DD), libs, and optionally engines (default admits any Node),
    deprecated, and tamper (the tarball's bytes change after its integrity is computed).
    """
    root = tmp_path / "registry"
    (root / "tarballs").mkdir(parents=True)
    versions: dict[str, Any] = {}
    times: dict[str, str] = {"created": "2010-01-01T00:00:00.000Z"}
    for r in releases:
        data = _tarball(r.get("libs", {}))
        integrity = "sha512-" + base64.b64encode(hashlib.sha512(data).digest()).decode()
        path = root / "tarballs" / f"npm-{r['version']}.tgz"
        path.write_bytes(data + (b"tampered" if r.get("tamper") else b""))
        doc: dict[str, Any] = {
            "name": "npm",
            "version": r["version"],
            "dist": {"tarball": path.as_uri(), "integrity": integrity},
        }
        if "engines" in r:
            doc["engines"] = {"node": r["engines"]}
        if r.get("deprecated"):
            doc["deprecated"] = "do not use"
        versions[r["version"]] = doc
        times[r["version"]] = f"{r['time']}T12:00:00.000Z"
    (root / "npm").write_text(json.dumps({"name": "npm", "versions": versions, "time": times}))
    return root.as_uri()


def entry(
    ident: str = "GHSA-qhr7-859c-m2p7",
    lib: str = "brace-expansion",
    lib_version: str = "5.0.9",
    fixed: str = "5.0.11",
    fixed_date: str = "2026-09-14",
    component: str = "npm",
    reviewed: str = "2026-10-08",
    review_by: str = "2026-11-07",
) -> dict[str, Any]:
    return {
        "id": ident,
        "package": lib,
        "severity": "high",
        "origin": "files under /opt/agent",
        "reason": "bundled in npm; no npm release ships the fix",
        "bundled": {
            "component": component,
            "component_version": "11.21.0",
            "library_version": lib_version,
            "fixed_version": fixed,
            "fixed_date": fixed_date,
        },
        "reviewed": reviewed,
        "review_by": review_by,
    }


def baseline(tmp_path: Path, *entries: dict[str, Any]) -> Path:
    doc = {
        "image": "timelike-agent",
        "base_digest": DIGEST,
        "reviewed": "2026-10-01",
        "review_by": "2026-12-27",
        "origins": {"files under /opt/agent": "the agent runtimes"},
        "findings": list(entries),
    }
    path = tmp_path / "timelike-agent.json"
    path.write_text(json.dumps(doc))
    return path


def check(tmp_path: Path, url: str, *entries: dict[str, Any]) -> dict[str, Any]:
    """Runs the release check as scan.sh does (the `releases` subcommand) and returns the one result."""
    out = tmp_path / "release-check.json"
    path = baseline(tmp_path, *entries)
    argv = ["releases", "--baseline", str(path), "--node-version", NODE, "--registry", url, "--out", str(out)]
    assert ev.main(argv) == 0
    results: list[dict[str, Any]] = json.loads(out.read_text())["results"]
    assert len(results) == len(entries)
    return results[0]


def finding(
    ident: str = "GHSA-qhr7-859c-m2p7", component: str = "brace-expansion 5.0.9", fix: str = "5.0.11"
) -> Any:
    return ev.Vuln("grype", ident, (), component, "high", (fix,), "art-1")


def judge(tmp_path: Path, result: dict[str, Any] | None, *entries: dict[str, Any], vuln: Any = None) -> Any:
    b = ev.load_baseline(baseline(tmp_path, *entries), LABEL)
    releases = {} if result is None else {(result["id"].lower(), result["package"].lower()): result}
    return ev.judge([vuln or finding()], b, DIGEST, TODAY, IMAGE, releases)


PIN = {
    "version": "11.21.0",
    "time": "2026-09-30",
    "libs": {"brace-expansion": "5.0.9"},
    "engines": ">=22.9.0",
}


# --- the four outcomes the ruling names --------------------------------------------------------------


def test_a_release_that_ships_the_fix_blocks_and_names_the_release(tmp_path: Path) -> None:
    url = registry(
        tmp_path,
        [
            PIN,
            {
                "version": "12.3.0",
                "time": "2026-10-05",
                "libs": {"brace-expansion": "5.0.11"},
                "engines": ">=24",
            },
        ],
    )
    result = check(tmp_path, url, entry())
    assert (result["state"], result["release"]) == ("fix-released", "12.3.0")
    v = judge(tmp_path, result, entry())
    (block,) = v.blocking
    assert (block.identifier, block.component) == ("GHSA-qhr7-859c-m2p7", "brace-expansion 5.0.9")
    assert "npm 12.3.0" in block.message and "brace-expansion 5.0.11" in block.message
    assert "pins.env" in block.update and "NPM_VERSION" in block.update
    assert v.allowed == []


def test_no_release_ships_the_fix_so_the_entry_lets_the_finding_through(tmp_path: Path) -> None:
    url = registry(
        tmp_path,
        [
            PIN,
            {
                "version": "12.2.0",
                "time": "2026-09-30",
                "libs": {"brace-expansion": "5.0.9"},
                "engines": ">=24",
            },
        ],
    )
    result = check(tmp_path, url, entry())
    assert result["state"] == "no-release"
    assert result["examined"] == ["11.21.0", "12.2.0"]  # what was checked is said, in version order
    v = judge(tmp_path, result, entry())
    assert v.blocking == []
    (allowed,) = v.allowed
    assert "no npm release ships brace-expansion 5.0.11" in allowed.message
    assert allowed.date == "2026-11-07"  # the entry's own review date, not the baseline's


def test_registry_unreachable_blocks_with_the_escalation(tmp_path: Path) -> None:
    result = check(tmp_path, (tmp_path / "no-registry").as_uri(), entry())
    assert result["state"] == "unknown"
    assert "could not read npm's packument" in result["reason"]
    v = judge(tmp_path, result, entry())
    (block,) = v.blocking
    assert "release check could not run" in block.message
    assert "npm" in block.message and "brace-expansion" in block.message
    assert "registry" in block.update  # what to do


def test_a_pre_release_or_a_deprecated_release_that_ships_the_fix_does_not_count(tmp_path: Path) -> None:
    fixed = {"brace-expansion": "5.0.11"}
    url = registry(
        tmp_path,
        [
            PIN,
            {"version": "12.3.0-pre.1", "time": "2026-10-01", "libs": fixed, "engines": ">=24"},
            {"version": "12.3.1", "time": "2026-10-02", "libs": fixed, "engines": ">=24", "deprecated": True},
        ],
    )
    result = check(tmp_path, url, entry())
    assert result["state"] == "no-release"
    assert result["examined"] == ["11.21.0"]
    assert judge(tmp_path, result, entry()).blocking == []


# --- what counts as "inside the constraint" and "ships the fix" --------------------------------------


def test_a_release_whose_engines_exclude_the_pinned_node_does_not_count(tmp_path: Path) -> None:
    url = registry(
        tmp_path,
        [
            PIN,
            {
                "version": "13.0.0",
                "time": "2026-10-05",
                "libs": {"brace-expansion": "5.0.11"},
                "engines": ">=26",
            },
        ],
    )
    result = check(tmp_path, url, entry())
    assert result["state"] == "no-release"
    assert "13.0.0" not in result["examined"]


def test_releases_published_before_the_fix_are_not_downloaded(tmp_path: Path) -> None:
    old = {"version": "11.19.0", "time": "2026-07-29", "libs": {"brace-expansion": "5.0.7"}, "tamper": True}
    result = check(tmp_path, registry(tmp_path, [old, PIN]), entry())
    # A tampered tarball would make the check unknown if it were read; it predates the fix, so it is not.
    assert (result["state"], result["examined"]) == ("no-release", ["11.21.0"])


def test_a_release_that_still_bundles_an_old_nested_copy_does_not_ship_the_fix(tmp_path: Path) -> None:
    both = {"brace-expansion": ["5.0.11", "5.0.9"]}
    url = registry(tmp_path, [PIN, {"version": "12.3.0", "time": "2026-10-05", "libs": both}])
    assert check(tmp_path, url, entry())["state"] == "no-release"


def test_a_release_that_no_longer_bundles_the_library_ships_the_fix(tmp_path: Path) -> None:
    url = registry(tmp_path, [PIN, {"version": "12.3.0", "time": "2026-10-05", "libs": {}}])
    result = check(tmp_path, url, entry())
    assert (result["state"], result["release"]) == ("fix-released", "12.3.0")
    assert "does not bundle brace-expansion" in result["reason"]


def test_a_tarball_that_does_not_match_its_integrity_makes_the_check_unknown(tmp_path: Path) -> None:
    bad = {"version": "12.3.0", "time": "2026-10-05", "libs": {"brace-expansion": "5.0.11"}, "tamper": True}
    result = check(tmp_path, registry(tmp_path, [PIN, bad]), entry())
    assert result["state"] == "unknown"
    assert "integrity" in result["reason"]
    assert len(judge(tmp_path, result, entry()).blocking) == 1


def test_an_engines_range_the_reader_cannot_parse_makes_the_check_unknown(tmp_path: Path) -> None:
    odd = {
        "version": "12.3.0",
        "time": "2026-10-05",
        "libs": {"brace-expansion": "5.0.9"},
        "engines": "node-lts",
    }
    result = check(tmp_path, registry(tmp_path, [PIN, odd]), entry())
    assert result["state"] == "unknown"
    assert "engines" in result["reason"]


def test_a_component_the_check_does_not_read_yet_is_unknown_and_says_what_it_needs(tmp_path: Path) -> None:
    pip_entry = entry(
        ident="PYSEC-2026-9", lib="urllib3", lib_version="2.5.0", fixed="2.6.0", component="pip"
    )
    result = check(tmp_path, registry(tmp_path, [PIN]), pip_entry)
    assert result["state"] == "unknown"
    assert "vendor.txt" in result["reason"]  # what pip's reader would need
    v = judge(tmp_path, result, pip_entry, vuln=finding("PYSEC-2026-9", "urllib3 2.5.0", "2.6.0"))
    assert len(v.blocking) == 1


# --- the entry itself ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("reviewed", "review_by", "said"),
    [
        ("2026-09-01", "2026-10-01", "overdue since 2026-10-01"),
        ("2026-10-08", "2026-11-08", "exceeds the 30-day cap"),
    ],
)
def test_an_entry_past_its_own_date_or_over_the_30_day_cap_blocks(
    tmp_path: Path, reviewed: str, review_by: str, said: str
) -> None:
    e = entry(reviewed=reviewed, review_by=review_by)
    result = {"id": e["id"], "package": e["package"], "state": "no-release", "fixed_version": "5.0.11"}
    result |= {"component": "npm", "release": "", "reason": "", "examined": ["11.21.0"]}
    (block,) = judge(tmp_path, result, e).blocking
    assert said in block.message
    assert block.date == review_by


def test_no_release_check_result_blocks(tmp_path: Path) -> None:
    (block,) = judge(tmp_path, None, entry()).blocking
    assert "release check could not run" in block.message
    assert "no result" in block.message


def test_an_entry_that_no_longer_matches_the_image_blocks(tmp_path: Path) -> None:
    e = entry()
    result = {"id": e["id"], "package": e["package"], "state": "no-release", "fixed_version": "5.0.11"}
    result |= {"component": "npm", "release": "", "reason": "", "examined": ["11.21.0"]}
    v = judge(tmp_path, result, e, vuln=finding(component="brace-expansion 5.0.10"))
    (block,) = v.blocking
    assert "records brace-expansion 5.0.9" in block.message


def test_an_entry_whose_fixed_version_disagrees_with_the_scanner_blocks(tmp_path: Path) -> None:
    e = entry()
    result = {"id": e["id"], "package": e["package"], "state": "no-release", "fixed_version": "5.0.11"}
    result |= {"component": "npm", "release": "", "reason": "", "examined": ["11.21.0"]}
    (block,) = judge(tmp_path, result, e, vuln=finding(fix="5.0.12")).blocking
    assert "the scanner says 5.0.12" in block.message


def test_a_bundled_entry_missing_a_field_voids_the_baseline(tmp_path: Path) -> None:
    e = entry()
    del e["bundled"]["fixed_date"]
    b = ev.load_baseline(baseline(tmp_path, e), LABEL)
    assert any("fixed_date" in message for message, _ in b.problems)


def test_the_proposed_baseline_carries_bundled_entries(tmp_path: Path) -> None:
    b = ev.load_baseline(baseline(tmp_path, entry()), LABEL)
    proposal = ev.propose([finding()], b, {}, DIGEST, IMAGE)
    (item,) = proposal["findings"]
    assert item["bundled"]["component"] == "npm"
    assert (item["reviewed"], item["review_by"]) == ("2026-10-08", "2026-11-07")


def test_releases_with_no_bundled_entries_says_so(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "release-check.json"
    path = baseline(tmp_path)
    argv = ["releases", "--baseline", str(path), "--node-version", NODE, "--out", str(out)]
    assert ev.main(argv) == 0
    assert capsys.readouterr().out.startswith("0 ")
    assert json.loads(out.read_text())["results"] == []


# --- the engines reader --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("spec", "node", "admits"),
    [
        ("^20.17.0 || >=22.9.0", "24.21.0", True),
        ("^20.17.0 || >=22.9.0", "22.8.0", False),
        ("^22.22.2 || ^24.15.0 || >=26.0.0", "24.21.0", True),
        ("^22.22.2 || ^24.15.0 || >=26.0.0", "24.14.0", False),
        ("^22.22.2 || ^24.15.0 || >=26.0.0", "25.0.0", False),
        (">=18 <20", "19.9.9", True),
        (">=18 <20", "20.0.0", False),
        ("~24.21", "24.21.5", True),
        ("~24.21", "24.22.0", False),
        ("24.x", "24.0.1", True),
        ("1.2.3 - 2.3", "2.3.9", True),
        (">24.21", "24.21.9", False),
        ("<=24.21", "24.21.9", True),
        ("*", "24.21.0", True),
        ("", "24.21.0", True),
    ],
)
def test_the_engines_reader(spec: str, node: str, admits: bool) -> None:
    assert ev.engines_admit(spec, node) is admits


@pytest.mark.parametrize("spec", ["node-lts", ">=22.0.0-rc.1", "^^24", ">= abc"])
def test_the_engines_reader_refuses_what_it_cannot_parse(spec: str) -> None:
    with pytest.raises(ValueError):
        ev.engines_admit(spec, NODE)
