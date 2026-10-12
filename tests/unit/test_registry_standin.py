"""The registry stand-in's own answers (feature 013, FR-33; research R2, R6; lore P005).

Its shapes are checked against the field names and date formats PyPI and npm returned on 2026-10-12 (R2), and
the host's real pip and npm fetch and install from it, so the stand-in is what the installers accept, not what
the guard expects.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from standin import CATALOG, Standin

PEP691 = "application/vnd.pypi.simple.v1+json"
PYPI_TIME = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{6}Z$")
NPM_TIME = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z$")


@pytest.fixture(scope="module")
def reg(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Standin]:
    with Standin(tmp_path_factory.mktemp("reg"), CATALOG) as s:
        yield s


def get(url: str, accept: str = "*/*") -> tuple[int, str, bytes]:
    req = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": "test"})  # noqa: S310
    try:
        with urllib.request.urlopen(req, timeout=10) as r:  # noqa: S310 — loopback stand-in
            return r.status, r.headers.get("Content-Type", ""), r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type", ""), e.read()


def test_simple_json_has_pypis_fields_and_formats(reg: Standin) -> None:
    status, ctype, body = get(f"{reg.simple}/tl_old/", PEP691)
    assert status == 200 and ctype == PEP691
    doc = json.loads(body)
    assert sorted(doc) == ["files", "meta", "name", "project-status", "versions"]
    assert doc["meta"]["api-version"] == "1.4" and doc["name"] == "tl-old"
    assert doc["versions"] == ["1.0.0", "1.2.0"]
    f = doc["files"][0]
    for key in (
        "core-metadata",
        "filename",
        "hashes",
        "requires-python",
        "size",
        "upload-time",
        "url",
        "yanked",
    ):
        assert key in f
    assert PYPI_TIME.match(f["upload-time"])
    assert set(f["hashes"]) == {"sha256"}


def test_simple_html_and_absent(reg: Standin) -> None:
    status, ctype, body = get(f"{reg.simple}/tl-yanked/")
    assert status == 200 and ctype == "text/html"
    text = body.decode()
    assert "tl_yanked-1.0.0-py3-none-any.whl</a>" in text
    assert 'data-yanked=""' in text and "#sha256=" in text
    assert get(f"{reg.simple}/tl-surely-absent/", PEP691)[0] == 404


def test_npm_document_has_npms_fields_and_formats(reg: Standin) -> None:
    status, ctype, body = get(f"{reg.npm}tl-left", "application/json")
    assert status == 200 and ctype == "application/json"
    doc = json.loads(body)
    assert doc["name"] == doc["_id"] == "tl-left"
    assert doc["dist-tags"] == {"latest": "1.3.0"}
    assert {"created", "modified", "1.0.0", "1.3.0"} == set(doc["time"])
    assert all(NPM_TIME.match(v) for v in doc["time"].values())
    dist = doc["versions"]["1.3.0"]["dist"]
    assert dist["integrity"].startswith("sha512-") and dist["tarball"].endswith(
        "/tl-left/-/tl-left-1.3.0.tgz"
    )


def test_npm_scoped_absent_and_faults(reg: Standin) -> None:
    assert get(f"{reg.npm}@tl%2fscoped", "application/json")[0] == 200
    status, _, body = get(f"{reg.npm}tl-surely-absent", "application/json")
    assert status == 404 and json.loads(body) == {"error": "Not found"}
    assert get(f"{reg.npm}tl-broken")[0] == 502
    assert get(f"{reg.simple}/tl-denied/", PEP691)[0] == 403


def test_every_request_is_logged(reg: Standin) -> None:
    get(f"{reg.npm}tl-left", "application/json")
    last = reg.requests()[-1]
    assert last["path"] == "/npm/tl-left" and last["user_agent"] == "test" and last["status"] == 200


@pytest.mark.skipif(shutil.which("pip") is None, reason="the host has no pip")
def test_real_pip_installs_from_it(reg: Standin, tmp_path: Path) -> None:
    p = subprocess.run(
        [
            "pip",
            "install",
            "--no-cache-dir",
            "--target",
            str(tmp_path / "t"),
            "--index-url",
            reg.simple,
            "tl-old",
        ],
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )
    assert p.returncode == 0, p.stderr
    assert (tmp_path / "t" / "tl_old" / "__init__.py").read_text() == 'NAME = "tl-old"\nVERSION = "1.2.0"\n'


@pytest.mark.skipif(shutil.which("npm") is None, reason="the host has no npm")
def test_real_npm_installs_from_it(reg: Standin, tmp_path: Path) -> None:
    proj = tmp_path / "p"
    proj.mkdir()
    (proj / "package.json").write_text('{"name": "p", "version": "1.0.0"}')
    p = subprocess.run(
        ["npm", "install", "--registry", reg.npm, "--cache", str(tmp_path / "c"), "--no-audit", "--no-fund",
         "tl-left", "@tl/scoped"],
        cwd=proj,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )  # fmt: skip
    assert p.returncode == 0, p.stderr
    pkg: dict[str, Any] = json.loads((proj / "node_modules" / "@tl" / "scoped" / "package.json").read_text())
    assert pkg["version"] == "2.0.0"
    assert (
        proj / "node_modules" / "tl-left" / "index.js"
    ).read_text() == 'module.exports = "tl-left@1.3.0";\n'
