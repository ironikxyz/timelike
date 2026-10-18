"""adele env (feature 13 slice 0; 014 contracts/adele-env.md, research R7) against a fake Adele.

The client runs as a real subprocess against test_adele_cli's in-process fake of Adele's request interface,
and the fake records what it was SENT. Readiness is the client's own: it reads Adele's read-back and probes
each service's ports itself, so a port here is a real listener on 127.0.0.1, standing in for a service's
alias on timelike-nested. What Adele does with the daemon is the e2e lane's (tests/e2e/*compose*, *nested*).
"""

from __future__ import annotations

import hashlib
import json
import socket
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from conftest import base_env, run
from test_adele_cli import (
    ADELE,
    SESSION,
    URL_ENV,
    FakeAdele,
    Proc,
    adele,
    doc_of,
    no_traceback,
    one_error_line,
)

__all__ = ["adele"]  # the fixture, imported for its name

NAME = "tl-proj-0a1b2c"


@pytest.fixture
def ws(tmp_path: Path) -> Path:
    w = tmp_path / "ws"
    (w / "proj").mkdir(parents=True)
    return w


@pytest.fixture
def listener() -> Iterator[int]:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    s.listen(8)
    try:
        yield int(s.getsockname()[1])
    finally:
        s.close()


def closed_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def go(py: str, scratch: Path, fake: FakeAdele, ws: Path | None, *args: str, timeout: float = 30) -> Proc:
    extra = {URL_ENV: fake.url}
    if ws is not None:
        extra["TIMELIKE_WORKSPACE"] = str(ws)
    mode = [] if "--json" in args else ["--text"]
    return run([py, str(ADELE), *mode, *args], base_env(scratch, session=SESSION, **extra), timeout=timeout)


def svc(
    name: str, state: str = "running", health: str = "", code: int = 0, ports: list[int] | None = None
) -> dict[str, Any]:
    alias = "127.0.0.1" if ports else f"{name}.{NAME}"
    return {
        "service": name,
        "state": state,
        "health": health,
        "exit_code": code,
        "alias": alias,
        "ports": ports or [],
    }


def up_body(
    services: list[dict[str, Any]], outcome: str = "performed", unset: list[str] | None = None
) -> dict[str, Any]:
    return {
        "outcome": outcome,
        "grant": "env",
        "resource": NAME,
        "cost_cents": 0,
        "expires_at": "2026-10-17T06:00:00Z",
        "ledger_id": 9,
        "undo": '{"capability":"docker.compose","action":"down","params":{"name":"' + NAME + '"}}',
        "unset": unset or [],
        "host_git": "enforced",
        "services": services,
    }


def up(py: str, scratch: Path, fake: FakeAdele, ws: Path, *extra: str, timeout: float = 30) -> Proc:
    return go(
        py, scratch, fake, ws, "env", "up", str(ws / "proj"), "--project", NAME, *extra, timeout=timeout
    )


def test_default_name_is_the_one_adele_computes() -> None:
    import importlib.machinery
    import importlib.util

    loader = importlib.machinery.SourceFileLoader("adele_tool", str(ADELE))
    spec = importlib.util.spec_from_loader("adele_tool", loader)
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    # adele/internal/compose/compose_test.go pins the same value for compose.DefaultName.
    assert mod.default_name("/w/ws1/My Project_2") == "tl-my-project-2-48c3cb"
    assert hashlib.sha256(b"/w/ws1/My Project_2").hexdigest()[:6] == "48c3cb"


def test_up_returns_once_each_service_is_ready_listing_its_address(
    py: str, scratch: Path, adele: FakeAdele, ws: Path, listener: int
) -> None:
    services = [svc("db", health="healthy"), svc("job", state="exited", code=0), svc("web", ports=[listener])]
    adele.answer("POST", "/v1/requests", 200, up_body(services))
    r = up(py, scratch, adele, ws, "-f", "compose.yaml", "--profile", "test")
    no_traceback(r)
    assert r.returncode == 0, r.stderr
    head = r.stdout.splitlines()[1]
    assert head.startswith(f"verdict: up {NAME}: 3 ready in ") and len(head) <= 200
    assert "read back, ports probed from the agent container" in head
    assert head.endswith("local: no cost · host git enforced")
    assert r.stdout.splitlines()[2].startswith("grant env · expires 2026-10-17T06:00:00Z")
    assert f"127.0.0.1:{listener}" in r.stdout and "completed (exit 0)" in r.stdout
    sent = next(s for s in adele.received() if s.method == "POST").body
    assert sent["capability"] == "docker.compose" and sent["action"] == "up"
    assert sent["params"] == {
        "name": NAME,
        "ttl": "",
        "ports": [],
        "dir": str((ws / "proj").resolve()),
        "files": ["compose.yaml"],
        "profiles": ["test"],
    }


def test_up_waits_on_adeles_read_back_until_healthy(
    py: str, scratch: Path, adele: FakeAdele, ws: Path
) -> None:
    adele.answer("POST", "/v1/requests", 200, up_body([svc("db", health="starting")]))
    adele.answer("GET", f"/v1/envs/{NAME}", 200, {"name": NAME, "services": [svc("db", health="healthy")]})
    r = up(py, scratch, adele, ws)
    assert r.returncode == 0, r.stderr
    assert any(s.path == f"/v1/envs/{NAME}" for s in adele.received())


def test_a_port_that_never_accepts_is_not_ready_and_the_bound_is_124(
    py: str, scratch: Path, adele: FakeAdele, ws: Path
) -> None:
    services = [svc("web", ports=[closed_port()]), svc("db", health="starting")]
    adele.answer("POST", "/v1/requests", 200, up_body(services))
    adele.answer("GET", f"/v1/envs/{NAME}", 200, {"name": NAME, "services": services})
    r = up(py, scratch, adele, ws, "--wait", "2", "--json")
    assert r.returncode == 124, r.stderr
    doc = doc_of(r)
    assert doc["ready"] is False and f"adele env down {NAME}" in doc["verdict"]
    assert "not ready within 2 s" in doc["verdict"]
    states = {s["service"]: s["ready"] for s in doc["services"]}
    assert states == {"web": "waiting", "db": "waiting"}


def test_a_service_that_exits_non_zero_concludes_at_once(
    py: str, scratch: Path, adele: FakeAdele, ws: Path
) -> None:
    adele.answer("POST", "/v1/requests", 200, up_body([svc("migrate", state="exited", code=3)]))
    r = up(py, scratch, adele, ws, "--wait", "60", timeout=20)
    assert r.returncode == 1
    line = one_error_line(r)
    assert "service migrate exited 3" in line and f"adele env down {NAME}" in line


def test_a_repeat_up_says_it_created_nothing(py: str, scratch: Path, adele: FakeAdele, ws: Path) -> None:
    body = up_body([svc("db", health="healthy")], outcome="unchanged")
    del body["ledger_id"]
    adele.answer("POST", "/v1/requests", 200, body)
    r = up(py, scratch, adele, ws)
    head = r.stdout.splitlines()[1]
    assert r.returncode == 0 and "1 ready, unchanged (nothing created or recorded)" in head
    long_name = "tl-" + "a" * 22 + "-cell"
    assert len(head.replace(NAME, long_name)) <= 200


def test_an_unset_variable_is_named(py: str, scratch: Path, adele: FakeAdele, ws: Path) -> None:
    adele.answer("POST", "/v1/requests", 200, up_body([svc("db", health="healthy")], unset=["DB_PASSWORD"]))
    r = up(py, scratch, adele, ws)
    assert "unset in the workspace: DB_PASSWORD" in r.stdout and "project's .env" in r.stdout


SETTING = {
    "outcome": "refused",
    "refusal": "setting",
    "setting": "privileged",
    "service": "db",
    "value": "true",
    "remediation": "no grant allows it; run it without privileged",
    "operator_command": "",
    "performed": False,
    "ledger_id": 11,
    "host": "docker:local",
    "grant": "env",
}


def test_a_forbidden_setting_is_exit_2_with_rule_14s_line_and_no_envelope(
    py: str, scratch: Path, adele: FakeAdele, ws: Path
) -> None:
    adele.answer("POST", "/v1/requests", 422, SETTING)
    r = up(py, scratch, adele, ws)
    assert r.returncode == 2 and r.stdout == ""
    line = one_error_line(r)
    assert line == (
        "error: privileged is not allowed (code 2) — no grant allows it; run it without privileged"
        " (service db: true)"
    )
    assert "docker exec" not in line and "operator" not in line


def test_a_forbidden_setting_in_json_is_one_object_on_stderr_naming_it(
    py: str, scratch: Path, adele: FakeAdele, ws: Path
) -> None:
    adele.answer(
        "POST",
        "/v1/requests",
        422,
        {
            **SETTING,
            "setting": "volumes",
            "value": "/etc:/etc",
            "remediation": "no grant allows it; use a path inside the workspace",
        },
    )
    r = up(py, scratch, adele, ws, "--json")
    assert r.returncode == 2 and r.stdout == ""
    doc = json.loads(one_error_line(r))
    assert (
        doc["code"] == 2
        and doc["error"] == "volumes is not allowed"
        and "no grant allows it" in doc["remediation"]
    )


def test_a_missing_image_names_the_operators_pull(py: str, scratch: Path, adele: FakeAdele, ws: Path) -> None:
    adele.answer(
        "POST",
        "/v1/requests",
        422,
        {
            **SETTING,
            "refusal": "image",
            "setting": "image",
            "value": "debian:x",
            "remediation": "the operator pulls it on the host: docker pull debian:x; the agent cannot",
            "operator_command": "docker pull debian:x",
        },
    )
    r = up(py, scratch, adele, ws)
    assert r.returncode == 3 and r.stdout == ""
    line = one_error_line(r)
    assert (
        "image debian:x is not on the daemon, and Adele never pulls" in line
        and "the operator pulls it" in line
    )


def test_beyond_the_grant_is_exit_4_with_the_grant_envelope(
    py: str, scratch: Path, adele: FakeAdele, ws: Path
) -> None:
    extend = "docker exec timelike-adele adeled extend env instances 3"
    adele.answer(
        "POST",
        "/v1/requests",
        403,
        {
            "outcome": "refused",
            "grant": "env",
            "performed": False,
            "limit": {"name": "instances", "allowed": "2", "needed": "3"},
            "extend": extend,
            "ledger_id": 12,
            "host": "docker:local",
        },
    )
    r = up(py, scratch, adele, ws)
    assert r.returncode == 4
    env = doc_of(r)
    assert env["status"] == "grant_required" and env["grant"] == "env" and env["extend"] == extend
    assert env["limit"] == {"name": "instances", "allowed": "2", "needed": "3"}


@pytest.mark.parametrize("where", ["outside", "none"])
def test_no_workspace_or_a_dir_outside_it_is_usage_and_sends_nothing(
    py: str, scratch: Path, adele: FakeAdele, ws: Path, tmp_path: Path, where: str
) -> None:
    if where == "outside":
        r = go(py, scratch, adele, ws, "env", "up", str(tmp_path))
        assert "is not inside the workspace" in one_error_line(r)
    else:
        r = go(py, scratch, adele, None, "env", "up", str(ws / "proj"))
        assert "no workspace was mounted" in one_error_line(r)
    assert r.returncode == 2
    assert not [s for s in adele.received() if s.method == "POST"]


def test_down_reports_what_was_removed_read_back(py: str, scratch: Path, adele: FakeAdele, ws: Path) -> None:
    adele.answer(
        "POST",
        "/v1/requests",
        200,
        {
            "outcome": "ended",
            "resource": NAME,
            "left": 0,
            "ledger_id": 13,
            "removed": {"containers": 3, "networks": 2, "volumes": 1},
        },
    )
    r = go(py, scratch, adele, ws, "env", "down", NAME)
    assert r.returncode == 0, r.stderr
    assert r.stdout.splitlines()[1].endswith(
        "removed 3 containers, 2 networks, 1 volumes; 0 left, read back from the daemon"
    )
    sent = next(s for s in adele.received() if s.method == "POST").body
    assert sent["action"] == "down" and sent["params"]["name"] == NAME


def test_down_of_nothing_is_exit_3(py: str, scratch: Path, adele: FakeAdele, ws: Path) -> None:
    adele.answer("POST", "/v1/requests", 404, {"error": f"no environment named {NAME}"})
    r = go(py, scratch, adele, ws, "env", "down", NAME)
    assert r.returncode == 3


def test_status_lists_each_environment_and_its_services(py: str, scratch: Path, adele: FakeAdele) -> None:
    adele.answer(
        "GET",
        "/v1/envs",
        200,
        {
            "envs": [
                {
                    "name": NAME,
                    "grant": "env",
                    "session": "s1",
                    "expires_at": "2026-10-17T06:00:00Z",
                    "services": [svc("db", health="healthy", ports=[5432])],
                }
            ]
        },
    )
    r = go(py, scratch, adele, None, "env", "status")
    assert r.returncode == 0 and r.stdout.splitlines()[1].startswith("verdict: 1 environment live")
    assert "db  running (healthy)  127.0.0.1:5432" in r.stdout


def test_status_denial_without_an_operators_command_says_none(
    py: str, scratch: Path, adele: FakeAdele
) -> None:
    adele.answer(
        "GET",
        "/v1/denials",
        200,
        {
            "window_hours": 24,
            "per_host": 20,
            "count": 1,
            "denials": [
                {
                    "ledger_id": 11,
                    "at": "2026-10-17T04:00:00Z",
                    "host": "docker:local",
                    "grant": "env",
                    "limit": {
                        "name": "privileged",
                        "allowed": "no grant allows it",
                        "needed": "service db: true",
                    },
                    "extend": "",
                    "extend_by": "none",
                    "session": "s1",
                    "agent": "",
                }
            ],
        },
    )
    r = go(py, scratch, adele, None, "status")
    assert (
        "privileged allows no grant allows it, needed service db: true · operator's command: none" in r.stdout
    )


def test_adele_not_answering_within_the_bound_is_124_saying_what_she_does_with_it(
    py: str, scratch: Path, adele: FakeAdele, ws: Path
) -> None:
    # Lane 13s0a, item A: the bound counts from the agent's side, Adele's resolving and queueing included. The
    # remediation says what is true of an up she has not answered: started, she finishes and records it.
    adele.answer("POST", "/v1/requests", 200, up_body([svc("db", health="healthy")]), delay=10)
    r = up(py, scratch, adele, ws, "--wait", "1", timeout=20)
    assert r.returncode == 124
    line = one_error_line(r)
    assert f"Adele did not answer the bring-up of {NAME} within the 1 s bound" in line
    assert (
        "she finishes and records it" in line and f"adele env down {NAME} removes it once she is done" in line
    )


def test_adeles_timings_are_carried_into_the_data(py: str, scratch: Path, adele: FakeAdele, ws: Path) -> None:
    body = up_body([svc("db", health="healthy")])
    body["timings"] = {"resolve_ms": 900, "lock_wait_ms": 0, "compose_ms": 1200}
    adele.answer("POST", "/v1/requests", 200, body)
    r = up(py, scratch, adele, ws, "--json")
    assert r.returncode == 0, r.stderr
    assert doc_of(r)["adele_timings"] == body["timings"]
