"""package-guard as a process (feature 013, T009, T010; FR-1 to FR-4, FR-28 to FR-32, FR-35).

The tool is copied with the host interpreter's shebang beside `run` (verify's lab pattern). The installer is
the host's real pip against the registry stand-in, and what happened is read from the stand-in's log, the
target directory and the session's event log, never from the tool's message (lore P004). Envelopes and
events are checked against 001's own schemas.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO, TOOLS_DIR, base_env
from schema import errors, load
from standin import CATALOG, Standin

SESSION = "pg"
pytestmark = pytest.mark.skipif(shutil.which("pip") is None, reason="the host has no pip")


def install(dest: Path, names: tuple[str, ...]) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    for name in names:
        lines = (TOOLS_DIR / name).read_text().splitlines(keepends=True)
        assert lines[0].startswith("#!/opt/timelike/python/bin/python3"), name
        (dest / name).write_text(f"#!{sys.executable}\n" + "".join(lines[1:]))
        (dest / name).chmod(0o755)
    return dest


@dataclass
class Lab:
    tmp: Path
    bin: Path
    ws: Path
    scratch: Path
    reg: Standin
    extra: dict[str, str] | None = None

    def env(self, **extra: str) -> dict[str, str]:
        e = base_env(self.scratch, SESSION, HOME=str(self.tmp / "home"), COLUMNS="1000")
        e.update(
            PATH=f"{self.bin}:{os.environ.get('PATH', '/usr/bin:/bin')}",
            TIMELIKE_BIN_DIRS=str(self.bin),
            PIP_INDEX_URL=self.reg.simple,
            PIP_NO_CACHE_DIR="1",
            PIP_DISABLE_PIP_VERSION_CHECK="1",
            npm_config_registry=self.reg.npm,
            pnpm_config_registry=self.reg.npm,  # pnpm 11 reads its own prefix, not npm_config_* (research R3)
            npm_config_cache=str(self.tmp / "npm-cache"),
            npm_config_update_notifier="false",
            npm_config_audit="false",
            npm_config_fund="false",
        )
        e.update(self.extra or {})
        e.update(extra)
        return e

    def run(self, *args: str, timeout: float = 120, **extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(self.bin / "package-guard"), *args],
            cwd=self.ws,
            env=self.env(**extra),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=timeout,
            start_new_session=True,
        )

    def events(self) -> list[dict[str, Any]]:
        p = self.scratch / SESSION / "events.jsonl"
        return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []


@pytest.fixture(scope="module")
def reg(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Standin]:
    with Standin(tmp_path_factory.mktemp("reg"), CATALOG) as s:
        yield s


def make_lab(tmp_path: Path, reg: Standin) -> Lab:
    tmp = Path(os.path.realpath(tmp_path))
    (tmp / "home").mkdir()
    (tmp / "ws").mkdir()
    reg.clear()
    return Lab(tmp, install(tmp / "bin", ("package-guard", "run")), tmp / "ws", tmp / "scratch", reg)


@pytest.fixture
def lab(tmp_path: Path, reg: Standin) -> Lab:
    return make_lab(tmp_path, reg)


def said(r: subprocess.CompletedProcess[str]) -> str:
    return f"exit {r.returncode}\nstdout:\n{r.stdout}\nstderr:\n{r.stderr}"


def test_refusal_is_the_confirm_envelope_and_nothing_runs(lab: Lab) -> None:
    r = lab.run("--", "pip", "install", "--target", "t", "tl-surely-absent", "tl-old")
    assert r.returncode == 4, said(r)
    env = json.loads(r.stdout)
    assert errors(env, load("confirm-envelope.schema.json")) == []
    assert list(env)[:4] == ["tool", "target", "scope", "status"]
    assert env["scope"] == "install pypi" and env["status"] == "confirmation_required"
    assert env["plan"][0] == f"refused: tl-surely-absent — not found: not in {lab.reg.simple} (HTTP 404)"
    assert env["confirm"] == "package-guard --yes -- pip install --target t tl-surely-absent tl-old"
    assert not (lab.ws / "t").exists()
    assert lab.reg.file_requests() == []
    assert all(x["user_agent"].startswith("timelike-package-guard/") for x in lab.reg.requests())
    (ev,) = lab.events()
    assert ev["tool"] == "package-guard" and ev["exit"] == 4
    assert errors(ev, load("event.schema.json")) == []


def test_running_the_confirm_proceeds_and_records_the_override(lab: Lab) -> None:
    r = lab.run("--", "pip", "install", "--target", "t", "tl-fresh")
    assert r.returncode == 4, said(r)
    confirm = shlex.split(json.loads(r.stdout)["confirm"])
    assert confirm[:3] == ["package-guard", "--yes", "--"]
    r = lab.run("--json", *confirm[1:])  # a global flag goes before --, or CMD receives it
    assert r.returncode == 0, said(r)
    assert (lab.ws / "t" / "tl_fresh" / "__init__.py").read_text() == 'NAME = "tl-fresh"\nVERSION = "1.1.0"\n'
    doc = json.loads(r.stdout)
    assert doc["exit"] == 0 and doc["command_exit"] == 0 and doc["cause"] == "command"
    record_path = doc["override_record"]
    rec = json.loads(Path(record_path).read_text())
    assert rec["session"] == SESSION and rec["command_exit"] == 0
    assert rec["command"] == ["pip", "install", "--target", "t", "tl-fresh"]
    (o,) = rec["overridden"]
    assert (o["package"], o["ecosystem"], o["registry"], o["reason"]) == (
        "tl-fresh",
        "pypi",
        lab.reg.simple,
        "too-new",
    )
    assert "minimum age is 2 days" in o["detail"]
    evs = lab.events()
    assert [e["exit"] for e in evs] == [4, 0]  # one event per call (rule 16): run's own stays in its scratch
    assert evs[1]["ref"] == {"log": record_path}
    assert evs[1]["args"][:3] == ["--json", "--yes", "--"]
    assert all(errors(e, load("event.schema.json")) == [] for e in evs)


def test_a_passing_install_runs_and_records_nothing(lab: Lab) -> None:
    r = lab.run("--json", "--yes", "--", "pip", "install", "--target", "t", "tl-old")
    assert r.returncode == 0, said(r)
    doc = json.loads(r.stdout)
    assert "override_record" not in doc
    assert doc["verdict"].startswith(
        f"1 package checked (0 pinned, no lookup) against {lab.reg.simple}; pip exited 0"
    )
    assert (lab.ws / "t" / "tl_old").is_dir()
    assert list((lab.scratch / SESSION / "package-guard").glob("override-*.json")) == []
    assert lab.events()[-1]["ref"] == {"log": doc["log"]}


def test_the_installers_failure_is_the_tools_exit(lab: Lab) -> None:
    r = lab.run("--json", "--", "pip", "install", "--target", "t", "--no-index", "tl-old")
    assert r.returncode == 1, said(r)  # pip's own: no index, no files
    doc = json.loads(r.stdout)
    assert doc["command_exit"] == 1 and doc["cause"] == "command" and "pip exited 1" in doc["verdict"]


def test_dry_run_checks_and_runs_nothing(lab: Lab) -> None:
    r = lab.run("--json", "--dry-run", "--", "pip", "install", "--target", "t", "tl-fresh", "tl-old")
    assert r.returncode == 0, said(r)
    doc = json.loads(r.stdout)
    assert doc["verdict"] == "would be refused: 1 of 2"
    assert [p["result"] for p in doc["packages"]] == ["too-new", "ok"]
    assert not (lab.ws / "t").exists() and lab.reg.file_requests() == []


def test_not_an_install_runs_unchanged(lab: Lab) -> None:
    r = lab.run("--json", "sh", "-c", "echo hi; exit 42")
    assert r.returncode == 42, said(r)
    doc = json.loads(r.stdout)
    assert doc["cause"] == "command" and doc["command_exit"] == 42 and doc["lines"] == ["hi"]
    assert doc["verdict"] == "not an install: ran sh unchecked; sh exited 42"
    assert lab.reg.requests() == []


def test_usage(lab: Lab) -> None:
    assert lab.run().returncode == 2
    assert lab.run("--", "package-guard", "--", "pip", "install", "x").returncode == 2


def test_never_runs_itself_or_a_decoy_in_its_own_directory(lab: Lab, tmp_path: Path) -> None:
    """FR-2, FR-35 (lore P002): a `pip` in timelike's own directory is skipped, and a python3 or run earlier
    on PATH is never what the tool runs itself with."""
    decoy = tmp_path / "decoy"
    decoy.mkdir()
    for name in ("python3", "run", "package-guard"):
        (decoy / name).write_text("#!/bin/sh\necho DECOY >&2\nexit 99\n")
        (decoy / name).chmod(0o755)
    (lab.bin / "pip").write_text("#!/bin/sh\necho RECURSION >&2\nexit 98\n")
    (lab.bin / "pip").chmod(0o755)
    r = lab.run("--json", "--", "pip", "install", "--target", "t", "tl-old",
                PATH=f"{decoy}:{lab.bin}:{os.environ.get('PATH', '/usr/bin:/bin')}")  # fmt: skip
    assert r.returncode == 0, said(r)
    assert "DECOY" not in r.stderr + r.stdout and "RECURSION" not in r.stderr + r.stdout
    assert (lab.ws / "t" / "tl_old").is_dir()


def test_agent_info_names_the_settings(lab: Lab) -> None:
    r = lab.run("--agent-info", TIMELIKE_PACKAGE_MIN_AGE_DAYS="7")
    m = json.loads(r.stdout)
    assert m["tool"] == "package-guard" and m["mutating"] is True and m["passes_exit"] is True
    assert m["dry_run"] is True and "--dry-run" in m["flags"] and "--yes" in m["flags"]
    assert m["envelopes"] == ["confirmation_required"]
    assert m["min_age_days"] == {"env": "TIMELIKE_PACKAGE_MIN_AGE_DAYS", "default": 2.0, "value": 7.0}
    assert m["lookup_timeout_s"]["env"] == "TIMELIKE_PACKAGE_TIMEOUT"
    assert "uv.lock" in m["lockfiles"] and "pnpm-lock.yaml" in m["lockfiles"]
    assert "not yet a grant under Adele" in m["adele"]


def test_help_fits_the_contract(lab: Lab) -> None:
    r = lab.run("--help")
    assert r.returncode == 0 and len(r.stdout.splitlines()) <= 40


def test_conform_passes_over_the_tool(lab: Lab) -> None:
    install(lab.bin, ("timelike-conform",))
    env = lab.env(TIMELIKE_CONFORM_TIMEOUT="30", TIMELIKE_REVISION="0" * 40)
    r = subprocess.run(
        [str(lab.bin / "timelike-conform"), "--json"], cwd=lab.ws, env=env, stdin=subprocess.DEVNULL,
        capture_output=True, text=True, timeout=300, start_new_session=True,
    )  # fmt: skip
    doc = json.loads(r.stdout)
    assert r.returncode == 0, doc.get("failures")
    assert "package-guard" in doc["tools"]


def test_contract_file_names_the_same_variables() -> None:
    text = (REPO / ".specswarm/features/013-package-guard/contracts/package-guard-cli.md").read_text()
    for var in ("TIMELIKE_PACKAGE_MIN_AGE_DAYS", "TIMELIKE_PACKAGE_TIMEOUT", "TIMELIKE_BIN_DIRS"):
        assert var in text
