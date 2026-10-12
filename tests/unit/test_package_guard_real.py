"""The host's real npm and pnpm through package-guard, against the stand-in (feature 013, T011; FR-34;
P004, P005).

pip's path is test_package_guard_tool.py's. Here the Node installers write real node_modules and real
lockfiles; "nothing downloaded" is the stand-in's log holding no tarball request, and "no registry check" is
its log holding no request with the guard's user agent. pnpm is not in the agent image (Item 24), so this is
where its forms meet a real pnpm.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
from standin import CATALOG, Standin
from test_package_guard_tool import Lab, make_lab, said


@pytest.fixture(scope="module")
def reg(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Standin]:
    with Standin(tmp_path_factory.mktemp("reg"), CATALOG) as s:
        yield s


@pytest.fixture
def lab(tmp_path: Path, reg: Standin) -> Lab:
    return make_lab(tmp_path, reg)


NODE = pytest.mark.skipif(shutil.which("npm") is None, reason="the host has no npm")
PNPM = pytest.mark.skipif(shutil.which("pnpm") is None, reason="the host has no pnpm")


def project(lab: Lab) -> Path:
    (lab.ws / "package.json").write_text('{"name": "p", "version": "1.0.0"}')
    return lab.ws


def installed(lab: Lab, name: str) -> str | None:
    pkg = lab.ws / "node_modules" / name / "package.json"
    return json.loads(pkg.read_text())["version"] if pkg.exists() else None


@NODE
def test_npm_absent_name_refused_before_anything_downloads(lab: Lab) -> None:
    project(lab)
    r = lab.run("--", "npm", "install", "tl-left", "tl-surely-absent")
    assert r.returncode == 4, said(r)
    plan = json.loads(r.stdout)["plan"]
    assert plan[1] == f"refused: tl-surely-absent — not found: not in {lab.reg.npm} (HTTP 404)"
    assert not (lab.ws / "node_modules").exists() and lab.reg.file_requests() == []


@NODE
def test_npm_too_new_refused_named_release_installs_and_confirm_records(lab: Lab) -> None:
    project(lab)
    r = lab.run("--", "npm", "install", "tl-fresh")
    assert r.returncode == 4, said(r)
    assert "too new: newest release 1.1.0 was released " in json.loads(r.stdout)["plan"][0]
    r = lab.run("--json", "--", "npm", "install", "tl-fresh@1.0.0")
    assert r.returncode == 0, said(r)
    assert installed(lab, "tl-fresh") == "1.0.0"
    r = lab.run("--", "npm", "install", "tl-fresh@latest")
    confirm = shlex.split(json.loads(r.stdout)["confirm"])
    r = lab.run("--json", *confirm[1:])
    assert r.returncode == 0, said(r)
    assert installed(lab, "tl-fresh") == "1.1.0"
    rec = json.loads(Path(json.loads(r.stdout)["override_record"]).read_text())
    assert rec["overridden"][0]["reason"] == "too-new" and rec["overridden"][0]["ecosystem"] == "npm"


@NODE
def test_npm_pinned_names_make_no_request(lab: Lab) -> None:
    project(lab)
    assert lab.run("--", "npm", "install", "tl-left@1.3.0").returncode == 0
    assert (
        json.loads((lab.ws / "package-lock.json").read_text())["packages"]["node_modules/tl-left"]["version"]
        == "1.3.0"
    )
    lab.reg.clear()
    r = lab.run("--json", "--", "npm", "install", "tl-left")
    assert r.returncode == 0, said(r)
    assert lab.reg.guard_requests() == []
    assert json.loads(r.stdout)["packages"][0]["result"] == "pinned"
    lab.reg.clear()
    r = lab.run("--json", "--", "npm", "ci")
    assert r.returncode == 0, said(r)
    assert lab.reg.guard_requests() == [] and installed(lab, "tl-left") == "1.3.0"


@NODE
def test_npx_and_npm_init_are_checked(lab: Lab) -> None:
    project(lab)
    r = lab.run("--", "npx", "--yes", "tl-surely-absent")
    assert r.returncode == 4, said(r)  # npx's own --yes is not the guard's
    assert "tl-surely-absent" in json.loads(r.stdout)["plan"][0]
    r = lab.run("--json", "--dry-run", "--", "npm", "init", "tl-app")
    assert r.returncode == 0, said(r)
    assert [p["name"] for p in json.loads(r.stdout)["packages"]] == ["create-tl-app"]


# The host's pnpm runs through corepack, which keeps the pnpm it fetched under the user's own cache. With the
# lab's HOME it would look for a pnpm to download from the stand-in; it is pointed at that cache instead, with
# its network off, so the pnpm that runs is the one already on this host.
COREPACK = {
    "COREPACK_HOME": os.path.join(os.path.expanduser("~"), ".cache", "node", "corepack"),
    "COREPACK_ENABLE_NETWORK": "0",
    "COREPACK_ENABLE_DOWNLOAD_PROMPT": "0",
}


@PNPM
def test_pnpm_add_refused_and_passed(lab: Lab) -> None:
    project(lab)
    store = str(lab.tmp / "pnpm-store")
    lab.extra = COREPACK
    r = lab.run("--", "pnpm", "add", "--store-dir", store, "tl-surely-absent")
    assert r.returncode == 4, said(r)
    assert not (lab.ws / "node_modules").exists() and lab.reg.file_requests() == []
    r = lab.run("--json", "--", "pnpm", "add", "--store-dir", store, "tl-left")
    assert r.returncode == 0, said(r)
    assert installed(lab, "tl-left") == "1.3.0"
    lab.reg.clear()
    r = lab.run("--json", "--", "pnpm", "add", "--store-dir", store, "tl-left")
    assert r.returncode == 0, said(r)
    assert lab.reg.guard_requests() == []  # pnpm-lock.yaml pins it now


@PNPM
def test_pnpm_registry_is_pnpms_own_answer(tmp_path: Path) -> None:
    """Research R3: pnpm 11 ignores npm_config_registry. The guard asks pnpm, so it names the registry pnpm
    would use, not the one npm would (P001). Called as a function: nothing is looked up, so nothing public
    is reached."""
    from pgmod import PG

    (tmp_path / "package.json").write_text('{"name": "p"}')
    env = {**os.environ, **COREPACK, "npm_config_registry": "http://npm-only.example/"}
    env.pop("pnpm_config_registry", None)
    env.pop("PNPM_CONFIG_REGISTRY", None)
    resolve = PG.resolver(env)
    inst = PG.classify(["pnpm", "add", "x"], tmp_path, env, resolve)
    reg, src = PG.pnpm_registry_for(inst, None, env, tmp_path, resolve, [], 30)
    assert (reg, src) == ("https://registry.npmjs.org/", "pnpm config get")
    env["pnpm_config_registry"] = "http://pnpm.example/"
    assert PG.pnpm_registry_for(inst, None, env, tmp_path, resolve, [], 30)[0] == "http://pnpm.example/"
