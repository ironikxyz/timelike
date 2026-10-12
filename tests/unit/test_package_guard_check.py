"""package-guard's checks against the registry stand-in (feature 013, T005 to T008; FR-14 to FR-28).

Every registry answer here comes from tests/fixtures/registry-standin.py, whose shapes are PyPI's and npm's
(research R2), and every "no request was made" is read from the stand-in's own log (lore P004). Lockfiles are
written by the host's real npm and pnpm where the host has them; uv.lock and pylock.toml are written in their
documented formats (no uv here; the image's uv writes a real one in the e2e cells).
"""

from __future__ import annotations

import datetime as dt
import json
import shutil
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from pgmod import PG
from standin import CATALOG, Standin

NOW = dt.datetime.now(dt.UTC)


@pytest.fixture(scope="module")
def reg(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Standin]:
    with Standin(tmp_path_factory.mktemp("reg"), CATALOG) as s:
        yield s


@pytest.fixture(scope="module")
def html_reg(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Standin]:
    with Standin(tmp_path_factory.mktemp("html"), {**CATALOG, "html_only": True}) as s:
        yield s


def env_for(reg: Standin, home: Path, **extra: str) -> dict[str, str]:
    return {
        "HOME": str(home),
        "PATH": "/usr/bin:/bin",
        "PIP_INDEX_URL": reg.simple,
        "npm_config_registry": reg.npm,
        "UV_DEFAULT_INDEX": reg.simple,
        **extra,
    }


def plan(reg: Standin, cmd: list[str], cwd: Path, **extra: str) -> Any:
    env = env_for(reg, cwd, **extra)
    resolve = PG.resolver(env)
    inst = PG.classify(cmd, cwd, env, resolve)
    return PG.build_plan(inst, cwd, env, resolve, dt.datetime.now(dt.UTC))


def results(p: Any) -> dict[str, str]:
    return {c.req.name: c.result for c in p.checks}


def by_name(p: Any, name: str) -> Any:
    return next(c for c in p.checks if c.req.name == name)


# ── lookups (T005) ─────────────────────────────────────────────────────────────────────────────


def test_absent_is_refused_naming_the_registry_and_the_answer(reg: Standin, tmp_path: Path) -> None:
    p = plan(reg, ["pip", "install", "tl-surely-absent", "tl-old"], tmp_path)
    c = by_name(p, "tl-surely-absent")
    assert c.result == "absent" and reg.simple in c.registry and "HTTP 404" in c.detail
    assert by_name(p, "tl-old").result == "ok"
    p = plan(reg, ["npm", "install", "tl-surely-absent"], tmp_path)
    assert by_name(p, "tl-surely-absent").result == "absent"


@pytest.mark.parametrize(
    ("name", "how"),
    [("tl-broken", "HTTP 503"), ("tl-denied", "denied: HTTP 403"), ("tl-drop", "closed without an answer")],
)
def test_unreachable_is_never_absent(reg: Standin, tmp_path: Path, name: str, how: str) -> None:
    c = by_name(plan(reg, ["pip", "install", name], tmp_path), name)
    assert c.result == "unreachable"
    assert how in c.detail and "unreachable from this container" in c.detail


def test_refused_connection_and_unresolvable_host(tmp_path: Path, reg: Standin) -> None:
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]  # bound, never listening: refused
    c = by_name(plan(reg, ["pip", "install", "-i", f"http://127.0.0.1:{port}/simple", "x"], tmp_path), "x")
    assert c.result == "unreachable" and "refused" in c.detail
    c = by_name(plan(reg, ["npm", "install", "--registry", "http://registry.invalid/", "x"], tmp_path), "x")
    assert c.result == "unreachable" and "not resolved" in c.detail


def test_a_hung_registry_is_bounded_by_one_time_limit(reg: Standin, tmp_path: Path) -> None:
    start = time.monotonic()
    p = plan(reg, ["pip", "install", "tl-slow", "tl-old"], tmp_path, TIMELIKE_PACKAGE_TIMEOUT="1")
    took = time.monotonic() - start
    c = by_name(p, "tl-slow")
    assert c.result == "unreachable" and "timed out after 1 s (TIMELIKE_PACKAGE_TIMEOUT)" in c.detail
    assert by_name(p, "tl-old").result == "ok"
    assert took < 4, took


def test_html_index_shows_existence_but_not_age(html_reg: Standin, tmp_path: Path) -> None:
    c = by_name(plan(html_reg, ["pip", "install", "tl-old"], tmp_path), "tl-old")
    assert c.result == "age-unknown" and "no upload-time" in c.detail
    assert by_name(plan(html_reg, ["pip", "install", "tl-old"], tmp_path, TIMELIKE_PACKAGE_MIN_AGE_DAYS="0"), "tl-old").result == "ok"
    assert by_name(plan(html_reg, ["pip", "install", "tl-nope"], tmp_path), "tl-nope").result == "absent"


def test_no_dates_on_either_registry(reg: Standin, tmp_path: Path) -> None:
    assert by_name(plan(reg, ["pip", "install", "tl-nodates"], tmp_path), "tl-nodates").result == "age-unknown"
    c = by_name(plan(reg, ["npm", "install", "tl-notime"], tmp_path), "tl-notime")
    assert c.result == "age-unknown" and "no time" in c.detail


def test_the_guards_requests_name_it(reg: Standin, tmp_path: Path) -> None:
    reg.clear()
    plan(reg, ["npm", "install", "@tl/scoped"], tmp_path)
    (r,) = reg.requests()
    assert r["path"] == "/npm/@tl%2fscoped" and r["user_agent"].startswith("timelike-package-guard/")
    assert r["accept"] == "application/json"


# ── age (T006) ─────────────────────────────────────────────────────────────────────────────────


def test_newest_release_too_new_names_its_date_and_the_release_to_pin(reg: Standin, tmp_path: Path) -> None:
    for cmd in (["pip", "install", "tl-fresh"], ["npm", "install", "tl-fresh"], ["uv", "pip", "install", "tl-fresh"]):
        c = by_name(plan(reg, cmd, tmp_path), "tl-fresh")
        assert c.result == "too-new", cmd
        assert c.release == "1.1.0" and c.released is not None
        assert (NOW - c.released).days == 1 or (NOW - c.released).total_seconds() < 2 * 86400
        assert c.released.strftime("%Y-%m-%d") in c.detail and "minimum age is 2 days" in c.detail
        assert c.suggestion.startswith("1.0.0, released ")
    assert "tl-fresh==1.0.0" in by_name(plan(reg, ["pip", "install", "tl-fresh"], tmp_path), "tl-fresh").suggestion
    assert "tl-fresh@1.0.0" in by_name(plan(reg, ["npm", "install", "tl-fresh"], tmp_path), "tl-fresh").suggestion


def test_a_named_release_is_checked_for_its_own_age(reg: Standin, tmp_path: Path) -> None:
    assert by_name(plan(reg, ["pip", "install", "tl-fresh==1.0.0"], tmp_path), "tl-fresh").result == "ok"
    assert by_name(plan(reg, ["pip", "install", "tl-fresh<1.1"], tmp_path), "tl-fresh").result == "ok"
    assert by_name(plan(reg, ["npm", "install", "tl-fresh@1.0.0"], tmp_path), "tl-fresh").result == "ok"
    assert by_name(plan(reg, ["npm", "install", "tl-fresh@~1.0.0"], tmp_path), "tl-fresh").result == "ok"
    assert by_name(plan(reg, ["npm", "install", "tl-fresh@^1.0.0"], tmp_path), "tl-fresh").result == "too-new"


def test_minimum_age_variable(reg: Standin, tmp_path: Path) -> None:
    assert by_name(plan(reg, ["pip", "install", "tl-fresh"], tmp_path, TIMELIKE_PACKAGE_MIN_AGE_DAYS="0"), "tl-fresh").result == "ok"
    assert by_name(plan(reg, ["pip", "install", "tl-fresh"], tmp_path, TIMELIKE_PACKAGE_MIN_AGE_DAYS="0.5"), "tl-fresh").result == "ok"
    c = by_name(plan(reg, ["pip", "install", "tl-old"], tmp_path, TIMELIKE_PACKAGE_MIN_AGE_DAYS="365"), "tl-old")
    assert c.result == "too-new" and "minimum age is 365 days" in c.detail
    with pytest.raises(PG.agentio.UsageError):
        plan(reg, ["pip", "install", "x"], tmp_path, TIMELIKE_PACKAGE_MIN_AGE_DAYS="soon")


def test_which_release_pip_and_npm_would_take(reg: Standin, tmp_path: Path) -> None:
    assert by_name(plan(reg, ["pip", "install", "tl-pre"], tmp_path), "tl-pre").release == "1.0.0"
    assert by_name(plan(reg, ["pip", "install", "--pre", "tl-pre"], tmp_path), "tl-pre").result == "too-new"
    assert by_name(plan(reg, ["pip", "install", "tl-yanked"], tmp_path), "tl-yanked").release == "1.0.0"
    assert by_name(plan(reg, ["npm", "install", "tl-tagged"], tmp_path), "tl-tagged").release == "1.0.0"
    c = by_name(plan(reg, ["npm", "install", "tl-tagged@next"], tmp_path), "tl-tagged")
    assert c.release == "2.0.0-beta.1" and c.result == "too-new"
    c = by_name(plan(reg, ["pip", "install", "tl-brandnew"], tmp_path), "tl-brandnew")
    assert c.result == "too-new" and c.suggestion == ""
    c = by_name(plan(reg, ["pip", "install", "tl-old==9.9"], tmp_path), "tl-old")
    assert c.result == "no-match" and "no release matches ==9.9" in c.detail


def test_an_extra_index_is_asked_and_named(reg: Standin, html_reg: Standin, tmp_path: Path) -> None:
    p = plan(reg, ["pip", "install", "--extra-index-url", html_reg.simple, "tl-old"], tmp_path)
    c = by_name(p, "tl-old")
    assert c.result == "ok" and c.also_on == [html_reg.simple]
    p = plan(reg, ["pip", "install", "-i", f"{reg.url}/simple-none", "--extra-index-url", reg.simple, "tl-old"], tmp_path)
    assert by_name(p, "tl-old").result == "ok"


# ── lockfiles (T007) ───────────────────────────────────────────────────────────────────────────


def npm_project(reg: Standin, tmp: Path, *pkgs: str) -> Path:
    proj = tmp / "np"
    proj.mkdir()
    (proj / "package.json").write_text('{"name": "p", "version": "1.0.0"}')
    p = subprocess.run(
        ["npm", "install", "--registry", reg.npm, "--cache", str(tmp / "cache"), "--no-audit", "--no-fund", *pkgs],
        cwd=proj, capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL, check=False,
    )  # fmt: skip
    assert p.returncode == 0, p.stderr
    return proj


@pytest.mark.skipif(shutil.which("npm") is None, reason="the host has no npm")
def test_package_lock_written_by_npm_pins_without_a_request(reg: Standin, tmp_path: Path) -> None:
    proj = npm_project(reg, tmp_path, "tl-left@1.3.0", "@tl/scoped")
    lock = PG.read_package_lock(proj / "package-lock.json")
    assert lock.readable and lock.pins["tl-left"] == {"1.3.0"} and lock.pins["@tl/scoped"] == {"2.0.0"}
    reg.clear()
    p = plan(reg, ["npm", "install", "tl-left", "@tl/scoped@^2"], proj)
    assert results(p) == {"tl-left": "pinned", "@tl/scoped": "pinned"}
    assert reg.guard_requests() == [] and p.lookups == 0
    # a different version is not pinned: that name is checked
    p = plan(reg, ["npm", "install", "tl-left@1.0.0"], proj)
    assert results(p) == {"tl-left": "ok"} and len(reg.guard_requests()) == 1
    # a bare install: the manifest's names, all pinned by the lockfile npm just wrote
    reg.clear()
    p = plan(reg, ["npm", "install"], proj)
    assert set(results(p).values()) == {"pinned"} and reg.guard_requests() == []
    reg.clear()
    p = plan(reg, ["npm", "ci"], proj)
    assert p.inst.lockfile_only and p.checks == [] and reg.guard_requests() == []


@pytest.mark.skipif(shutil.which("pnpm") is None, reason="the host has no pnpm")
def test_pnpm_lock_written_by_pnpm(reg: Standin, tmp_path: Path) -> None:
    proj = tmp_path / "pp"
    proj.mkdir()
    (proj / "package.json").write_text('{"name": "p", "version": "1.0.0"}')
    r = subprocess.run(
        ["pnpm", "add", "--registry", reg.npm, "--store-dir", str(tmp_path / "store"), "tl-left@1.0.0", "@tl/scoped"],
        cwd=proj, capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL, check=False,
    )  # fmt: skip
    assert r.returncode == 0, r.stdout + r.stderr
    lock = PG.read_pnpm_lock(proj / "pnpm-lock.yaml")
    assert lock.readable and lock.pins == {"tl-left": {"1.0.0"}, "@tl/scoped": {"2.0.0"}}
    reg.clear()
    p = plan(reg, ["pnpm", "add", "tl-left", "@tl/scoped"], proj)
    assert set(results(p).values()) == {"pinned"} and reg.guard_requests() == []
    p = plan(reg, ["pnpm", "install", "--frozen-lockfile"], proj)
    assert p.inst.lockfile_only and reg.guard_requests() == []


def test_uv_lock_and_pylock_in_their_documented_formats(reg: Standin, tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "p"\nversion = "0"\ndependencies = ["tl-fresh"]\n')
    (tmp_path / "uv.lock").write_text(
        'version = 1\nrequires-python = ">=3.12"\n\n[[package]]\nname = "p"\nversion = "0"\nsource = { virtual = "." }\n\n'
        '[[package]]\nname = "tl-fresh"\nversion = "1.0.0"\nsource = { registry = "https://pypi.org/simple" }\n'
    )
    reg.clear()
    p = plan(reg, ["uv", "add", "tl-fresh"], tmp_path)
    assert results(p) == {"tl-fresh": "pinned"} and reg.guard_requests() == []
    p = plan(reg, ["uv", "sync"], tmp_path)
    assert results(p) == {"tl-fresh": "pinned"} and reg.guard_requests() == []
    assert results(plan(reg, ["uv", "add", "tl-fresh==1.1.0"], tmp_path)) == {"tl-fresh": "too-new"}
    (tmp_path / "pylock.toml").write_text('lock-version = "1.0"\n[[packages]]\nname = "tl-old"\nversion = "1.0.0"\n')
    assert results(plan(reg, ["pip", "install", "tl-old"], tmp_path))["tl-old"] == "pinned"


def test_hashed_requirements_pin_only_their_own_names(reg: Standin, tmp_path: Path) -> None:
    (tmp_path / "req.txt").write_text("tl-fresh==1.1.0 --hash=sha256:00\n")
    reg.clear()
    p = plan(reg, ["pip", "install", "-r", "req.txt", "tl-surely-absent"], tmp_path)
    assert results(p) == {"tl-fresh": "pinned", "tl-surely-absent": "absent"}
    assert [r["path"] for r in reg.guard_requests()] == ["/simple/tl-surely-absent/"]
    reg.clear()
    p = plan(reg, ["uv", "pip", "sync", "req.txt"], tmp_path)
    assert results(p) == {"tl-fresh": "pinned"} and reg.guard_requests() == []


def test_an_unreadable_lockfile_is_not_a_pin(reg: Standin, tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text('{"name": "p"}')
    (tmp_path / "package-lock.json").write_text("{broken")
    p = plan(reg, ["npm", "install", "tl-left"], tmp_path)
    assert results(p)["tl-left"] == "ok"
    note = next(c for c in p.checks if c.req.origin == "lockfile")
    assert note.result == "unchecked" and "could not be read" in note.detail


def test_project_root_is_found_upward(reg: Standin, tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text('{"name": "p"}')
    (tmp_path / "package-lock.json").write_text(
        json.dumps({"lockfileVersion": 3, "packages": {"": {}, "node_modules/tl-left": {"version": "1.3.0"},
                                                        "node_modules/x/node_modules/tl-fresh": {"version": "1.1.0"}}})
    )  # fmt: skip
    sub = tmp_path / "src" / "deep"
    sub.mkdir(parents=True)
    p = plan(reg, ["npm", "install", "tl-left", "tl-fresh"], sub)
    assert results(p) == {"tl-left": "pinned", "tl-fresh": "too-new"}  # a nested copy is a dependency's, not a pin
    assert p.root == tmp_path


# ── the plan (T008) ────────────────────────────────────────────────────────────────────────────


def test_plan_lines_name_every_package_and_its_registry(reg: Standin, tmp_path: Path) -> None:
    p = plan(reg, ["pip", "install", "tl-old", "tl-surely-absent", "tl-fresh", "./local.whl", "git+https://e.example/r"], tmp_path)
    lines = [PG.plan_line(c, "pypi") for c in p.checks]
    assert lines[0].startswith("ok: tl-old 1.2.0, released ") and reg.simple in lines[0]
    assert lines[1] == f"refused: tl-surely-absent — not found: not in {reg.simple} (HTTP 404)"
    assert lines[2].startswith("refused: tl-fresh — too new: newest release 1.1.0 was released ")
    assert "the newest release old enough is 1.0.0" in lines[2]
    assert lines[3].startswith("unchecked: ./local.whl — a local path")
    assert lines[4].startswith("refused: git+https://e.example/r — unchecked source")
    assert {c.req.name for c in p.refused} == {"tl-surely-absent", "tl-fresh", "git+https://e.example/r"}


def test_no_did_you_mean(reg: Standin, tmp_path: Path) -> None:
    c = by_name(plan(reg, ["pip", "install", "tl-olf"], tmp_path), "tl-olf")
    assert c.result == "absent" and "tl-old" not in PG.plan_line(c, "pypi")
