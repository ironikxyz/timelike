"""adele (feature 004, T012) against contracts/adele-cli.md and contracts/adele-http.md.

The client runs as a real subprocess, like every other tool test (conftest.py), against an in-process
fake of Adele's request interface: a stdlib ThreadingHTTPServer on 127.0.0.1 at a random port, reached
through TIMELIKE_ADELE_URL. The fake records every request it receives, so a test asserts what the
client SENT, not only what it printed. It is started and stopped by a fixture, in this process; nothing
is ever found or killed by matching a command line.

The exit-4 refusal is the grant envelope on stdout (FOR-MENTOR Item 13, discovery revision 10; T018),
validated against 001's grant-envelope.schema.json and timelike-conform's own C9 check.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import shlex
import socket
import subprocess
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest
import schema
from conftest import TOOLS_DIR, base_env, events, run
from test_conform import conform, env_for, install

ADELE = TOOLS_DIR / "adele"
SESSION = "adele-t012"
REVISION = "4d6e1f0c9b2a"
URL_ENV = "TIMELIKE_ADELE_URL"
VANTAGE = "from the agent container"
UNBLOCK = "make up (docker compose up -d) on the host"

PERFORMED = {
    "outcome": "performed",
    "grant": "demo",
    "resource": "tl-1",
    "cost_cents": 25,
    "expires_at": "2026-10-02T13:00:00Z",
    "ledger_id": 6,
    "undo": "docker exec timelike-adele adeled undo 6",
}
EXTEND = "docker exec timelike-adele adeled extend demo ports 22"
REFUSED = {
    "outcome": "refused",
    "grant": "demo",
    "limit": {"name": "ports", "allowed": "8080", "needed": "22"},
    "extend": EXTEND,
    "performed": False,
    "ledger_id": 7,
}
GRANTS = {
    "grants": [
        {
            "name": "demo",
            "capabilities": ["standin.box"],
            "budget_cents": 100,
            "spent_cents": 25,
            "ttl": "1h",
            "instances": 2,
            "live": 1,
            "ports": "8080, 9000-9010",
        },
        {
            "name": "wide",
            "capabilities": ["standin.box"],
            "budget_cents": 1050,
            "spent_cents": 0,
            "ttl": "2h",
            "instances": 5,
            "live": 0,
            "ports": "8080",
        },
    ]
}
Proc = subprocess.CompletedProcess[str]
CREATE = ["request", "standin.box", "create", "--name", "tl-1"]


# ── the fake Adele ─────────────────────────────────────────────────────────────────────────────


@dataclass
class Seen:
    method: str
    path: str
    body: Any


@dataclass
class Route:
    status: int
    body: bytes
    delay: float = 0.0


@dataclass
class FakeAdele:
    """What the fake answers per (method, path), and every request it received, in order."""

    url: str = ""
    routes: dict[tuple[str, str], Route] = field(default_factory=dict)
    seen: list[Seen] = field(default_factory=list)
    stop: threading.Event = field(default_factory=threading.Event)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def answer(self, method: str, path: str, status: int, body: Any, delay: float = 0.0) -> None:
        raw = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.routes[(method, path)] = Route(status, raw, delay)

    def received(self) -> list[Seen]:
        with self.lock:
            return list(self.seen)


def _handler(fake: FakeAdele) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def _serve(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b""
            try:
                body: Any = json.loads(raw) if raw else None
            except ValueError:
                body = raw
            with fake.lock:
                fake.seen.append(Seen(self.command, self.path, body))
            route = fake.routes.get((self.command, self.path), Route(404, b'{"error":"no such route"}'))
            if route.delay and fake.stop.wait(route.delay):
                return  # torn down while sleeping: never answer
            self.send_response(route.status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(route.body)))
            self.end_headers()
            self.wfile.write(route.body)

        do_GET = _serve
        do_POST = _serve

        def log_message(self, format: str, *args: Any) -> None:
            pass

    return Handler


@pytest.fixture
def adele() -> Iterator[FakeAdele]:
    fake = FakeAdele()
    fake.answer("GET", "/v1/health", 200, {"service": "adele", "revision": REVISION, "grants": ["demo"]})
    fake.answer("GET", "/v1/grants", 200, GRANTS)
    fake.answer("POST", "/v1/requests", 200, PERFORMED)
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler(fake))
    server.daemon_threads = True
    server.block_on_close = False  # a handler still sleeping must not hold up teardown
    fake.url = f"http://127.0.0.1:{server.server_address[1]}"
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    thread.start()
    try:
        yield fake
    finally:
        fake.stop.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.fixture
def closed_url() -> str:
    """A URL on 127.0.0.1 where nothing listens: the port was bound, then released."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    return f"http://127.0.0.1:{port}"


# ── running the client ─────────────────────────────────────────────────────────────────────────


def go(py: str, scratch: Path, url: str, *args: str, timeout: float = 20) -> Proc:
    return run([py, str(ADELE), *args], base_env(scratch, session=SESSION, **{URL_ENV: url}), timeout=timeout)


def doc_of(r: Proc) -> dict[str, Any]:
    doc: dict[str, Any] = json.loads(r.stdout)
    return doc


def no_traceback(r: Proc) -> None:
    assert "Traceback" not in r.stderr and "Traceback" not in r.stdout, r.stderr
    assert "internal error" not in r.stderr, r.stderr


def one_error_line(r: Proc) -> str:
    lines = r.stderr.splitlines()
    assert len(lines) == 1, r.stderr
    return lines[0]


# ── status: the conformance probe (research R8) ────────────────────────────────────────────────


def test_status_reachable_json(py: str, scratch: Path, adele: FakeAdele) -> None:
    r = go(py, scratch, adele.url, "--json", "status")
    assert r.returncode == 0, r.stderr
    doc = doc_of(r)
    assert list(doc)[:3] == ["tool", "target", "scope"]
    assert (doc["tool"], doc["target"], doc["scope"]) == ("adele", "adele", "status")
    assert doc["reachable"] is True
    assert doc["revision"] == REVISION
    assert doc["grants"] == ["demo"]
    assert doc["url"] == adele.url
    assert [(s.method, s.path) for s in adele.received()] == [("GET", "/v1/health")]


def test_status_reachable_text(py: str, scratch: Path, adele: FakeAdele) -> None:
    r = go(py, scratch, adele.url, "--text", "status")
    assert r.returncode == 0, r.stderr
    out = r.stdout.splitlines()
    assert out[0] == "adele: adele [status]"
    assert out[1].startswith("verdict: ")
    for words in (adele.url, VANTAGE, f"revision {REVISION}"):
        assert words in out[1], out[1]
    assert r.stderr == ""


@pytest.mark.parametrize("mode", ["--json", "--text"])
def test_status_unreachable_is_still_a_result(py: str, scratch: Path, closed_url: str, mode: str) -> None:
    r = go(py, scratch, closed_url, mode, "status")
    assert r.returncode == 1
    no_traceback(r)
    if mode == "--json":
        doc = doc_of(r)
        assert (doc["tool"], doc["target"], doc["scope"]) == ("adele", "adele", "status")
        assert doc["reachable"] is False
        verdict = doc["verdict"]
    else:
        out = r.stdout.splitlines()
        assert out[0] == "adele: adele [status]"
        verdict = out[1].removeprefix("verdict: ")
    assert verdict.startswith("unreachable:"), verdict
    for words in (closed_url, VANTAGE, UNBLOCK):
        assert words in verdict, verdict


# ── grants ─────────────────────────────────────────────────────────────────────────────────────


def test_grants_json(py: str, scratch: Path, adele: FakeAdele) -> None:
    r = go(py, scratch, adele.url, "--json", "grants")
    assert r.returncode == 0, r.stderr
    doc = doc_of(r)
    assert (doc["target"], doc["scope"]) == ("adele", "grants")
    assert doc["count"] == 2
    assert doc["grants"] == GRANTS["grants"]
    assert doc["verdict"] == "2 grants"
    assert "budget 1.00 USD (spent 0.25 USD)" in doc["lines"][0]
    assert "budget 10.50 USD (spent 0.00 USD)" in doc["lines"][1]


def test_grants_text(py: str, scratch: Path, adele: FakeAdele) -> None:
    r = go(py, scratch, adele.url, "--text", "grants")
    assert r.returncode == 0, r.stderr
    out = r.stdout.splitlines()
    assert out[:2] == ["adele: adele [grants]", "verdict: 2 grants"]
    demo, wide = out[2:]
    assert demo.startswith("demo: standin.box")
    for words in ("budget 1.00 USD", "spent 0.25 USD", "ttl 1h", "instances 1/2", "ports 8080, 9000-9010"):
        assert words in demo, demo
    for words in ("budget 10.50 USD", "spent 0.00 USD", "instances 0/5", "ports 8080"):
        assert words in wide, wide


def test_grants_unreachable_is_exit_1(py: str, scratch: Path, closed_url: str) -> None:
    r = go(py, scratch, closed_url, "--text", "grants")
    assert r.returncode == 1
    assert r.stdout == ""
    line = one_error_line(r)
    assert line.startswith(f"error: cannot reach Adele at {closed_url} ({VANTAGE})"), line
    assert line.endswith(UNBLOCK), line


# ── request: what is sent ──────────────────────────────────────────────────────────────────────


def test_request_sends_exactly_the_request(py: str, scratch: Path, adele: FakeAdele) -> None:
    r = go(py, scratch, adele.url, "--json", *CREATE, "--ttl", "1h", "--port", "8080", "--grant", "demo")
    assert r.returncode == 0, r.stderr
    [seen] = adele.received()
    assert (seen.method, seen.path) == ("POST", "/v1/requests")
    assert seen.body == {
        "session": SESSION,
        "grant": "demo",
        "capability": "standin.box",
        "action": "create",
        "params": {"name": "tl-1", "ttl": "1h", "ports": [8080]},
    }


def test_request_defaults_are_null_and_empty(py: str, scratch: Path, adele: FakeAdele) -> None:
    r = go(py, scratch, adele.url, "--json", *CREATE)
    assert r.returncode == 0, r.stderr
    [seen] = adele.received()
    assert seen.body["grant"] is None
    assert seen.body["params"] == {"name": "tl-1", "ttl": None, "ports": []}


def test_request_sends_every_port_in_order(py: str, scratch: Path, adele: FakeAdele) -> None:
    r = go(py, scratch, adele.url, "--json", *CREATE, "--port", "9001", "--port", "8080")
    assert r.returncode == 0, r.stderr
    assert adele.received()[0].body["params"]["ports"] == [9001, 8080]


# ── request: performed (200) ───────────────────────────────────────────────────────────────────


def test_performed_json(py: str, scratch: Path, adele: FakeAdele) -> None:
    r = go(py, scratch, adele.url, "--json", *CREATE, "--grant", "demo")
    assert r.returncode == 0, r.stderr
    doc = doc_of(r)
    assert (doc["tool"], doc["target"], doc["scope"]) == ("adele", "standin.box", "create")
    for key, value in PERFORMED.items():
        assert doc[key] == value, key
    assert r.stderr == ""


def test_performed_text(py: str, scratch: Path, adele: FakeAdele) -> None:
    r = go(py, scratch, adele.url, "--text", *CREATE, "--grant", "demo")
    assert r.returncode == 0, r.stderr
    out = r.stdout.splitlines()
    assert out[0] == "adele: standin.box [create]"
    verdict = out[1]
    for words in ("performed under grant demo", "box tl-1", "0.25 USD", f"expires {PERFORMED['expires_at']}"):
        assert words in verdict, verdict


# ── request: refused (403) — exit 4 with the grant envelope (discovery revision 10; T018) ──────


def load_conform() -> Any:
    loader = importlib.machinery.SourceFileLoader("timelike_conform", str(TOOLS_DIR / "timelike-conform"))
    spec = importlib.util.spec_from_loader("timelike_conform", loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


@pytest.mark.parametrize("mode", ["--text", "--json"])
def test_refused_is_exit_4_with_the_grant_envelope_on_stdout(
    mode: str, py: str, scratch: Path, adele: FakeAdele
) -> None:
    adele.answer("POST", "/v1/requests", 403, REFUSED)
    r = go(py, scratch, adele.url, mode, *CREATE, "--port", "22", "--grant", "demo")
    assert r.returncode == 4
    assert r.stderr == ""
    env = json.loads(r.stdout)  # JSON in every mode, and nothing else on stdout (rule 9's convention)
    assert schema.errors(env, schema.load("grant-envelope.schema.json")) == []
    assert list(env)[:4] == ["tool", "target", "scope", "status"]  # rule 12, then the status
    assert (env["tool"], env["target"], env["scope"]) == ("adele", "standin.box", "create")
    assert env["status"] == "grant_required"
    assert env["grant"] == "demo"
    assert env["limit"] == {"name": "ports", "allowed": "8080", "needed": "22"}
    assert (env["extend"], env["extend_by"], env["performed"]) == (EXTEND, "operator", False)
    assert env["ledger_id"] == 7
    sent = adele.received()[-1].body
    assert env["request"] == sent  # the refused request, exactly as the client sent it
    assert "confirm" not in env  # the operator's command never sits where the agent's habit runs it


def test_the_envelope_passes_conform_c9_and_its_negative_case_fails(
    py: str, scratch: Path, adele: FakeAdele
) -> None:
    """conform's C9 judges the real client's envelope, and the same check fails the same envelope once
    the operator's command is put where the agent runs commands (cross-stack P005: seen failing)."""
    adele.answer("POST", "/v1/requests", 403, REFUSED)
    r = go(py, scratch, adele.url, "--json", *CREATE, "--port", "22", "--grant", "demo")
    c = load_conform()
    declared = {"grant_required"}
    assert c.check_envelope("adele", r.stdout, declared) == []
    bad = dict(json.loads(r.stdout), confirm=EXTEND)
    assert c.check_envelope("adele", json.dumps(bad), declared) != []
    assert c.check_envelope("adele", r.stdout, set()) != []  # undeclared in the manifest


def test_manifest_declares_the_grant_envelope_and_not_mutating(py: str, scratch: Path) -> None:
    info = json.loads(go(py, scratch, "http://127.0.0.1:9", "--agent-info").stdout)
    assert schema.errors(info, schema.load("agent-info.schema.json")) == []
    assert info["envelopes"] == ["grant_required"]
    assert info["mutating"] is False and info["destructive"] is False  # rule 8: nothing destructive yet
    assert "--yes" not in info["flags"]
    assert info["exit_codes"]["4"] == "beyond the grant, nothing performed"


@pytest.mark.parametrize(
    "body",
    [
        {k: v for k, v in REFUSED.items() if k != "extend"},
        {k: v for k, v in REFUSED.items() if k != "limit"},
        {**REFUSED, "limit": {"name": "ports"}},
        {**REFUSED, "performed": True},
        {**REFUSED, "grant": ""},
    ],
    ids=["no-extend", "no-limit", "partial-limit", "performed", "no-grant"],
)
def test_a_403_that_cannot_fill_the_envelope_is_a_failure_not_a_guess(
    body: dict[str, Any], py: str, scratch: Path, adele: FakeAdele
) -> None:
    adele.answer("POST", "/v1/requests", 403, body)
    r = go(py, scratch, adele.url, "--text", *CREATE, "--port", "22", "--grant", "demo")
    assert r.returncode == 1
    assert r.stdout == ""
    line = one_error_line(r)
    assert "does not name the grant, the limit and the operator's extend command" in line, line


def test_the_extend_command_is_not_runnable_as_the_agents_own(
    py: str, scratch: Path, adele: FakeAdele
) -> None:
    """The extend command is Adele's verbatim, and it is not an adele command (rule 9's promise)."""
    adele.answer("POST", "/v1/requests", 403, REFUSED)
    r = go(py, scratch, adele.url, "--json", *CREATE, "--port", "22", "--grant", "demo")
    env = json.loads(r.stdout)
    assert shlex.split(env["extend"])[0] != "adele"


# ── request: Adele's other answers ─────────────────────────────────────────────────────────────


def test_ambiguous_grant_is_usage_naming_the_grants(py: str, scratch: Path, adele: FakeAdele) -> None:
    adele.answer(
        "POST",
        "/v1/requests",
        400,
        {
            "error": "more than one grant allows this",
            "remediation": "name one with --grant",
            "grants": ["demo", "wide"],
        },
    )
    r = go(py, scratch, adele.url, "--text", *CREATE)
    assert r.returncode == 2
    assert r.stdout == ""
    line = one_error_line(r)
    assert line.startswith("error: more than one grant allows this (code 2) — name one with --grant"), line
    assert "grants: demo, wide" in line, line


def test_unknown_grant_is_exit_3(py: str, scratch: Path, adele: FakeAdele) -> None:
    adele.answer("POST", "/v1/requests", 404, {"error": "no grant named nope", "grants": ["demo", "wide"]})
    r = go(py, scratch, adele.url, "--json", *CREATE, "--grant", "nope")
    assert r.returncode == 3
    assert r.stdout == ""
    doc = json.loads(r.stderr)
    assert (doc["code"], doc["error"]) == (3, "no grant named nope")
    assert "grants: demo, wide" in doc["remediation"]


def test_upstream_failure_is_exit_1(py: str, scratch: Path, adele: FakeAdele) -> None:
    adele.answer("POST", "/v1/requests", 502, {"error": "stand-in failed: 500", "performed": False})
    r = go(py, scratch, adele.url, "--text", *CREATE)
    assert r.returncode == 1
    assert r.stdout == ""
    line = one_error_line(r)
    assert line.startswith("error: stand-in failed: 500 (code 1) — nothing was performed"), line
    no_traceback(r)


def test_non_json_500_is_exit_1_with_a_clear_message(py: str, scratch: Path, adele: FakeAdele) -> None:
    adele.answer("POST", "/v1/requests", 500, b"<html>Internal Server Error</html>")
    r = go(py, scratch, adele.url, "--text", *CREATE)
    assert r.returncode == 1
    assert r.stdout == ""
    no_traceback(r)
    assert "not JSON" in one_error_line(r)


def test_request_unreachable_is_exit_1(py: str, scratch: Path, closed_url: str) -> None:
    r = go(py, scratch, closed_url, "--json", *CREATE)
    assert r.returncode == 1
    assert r.stdout == ""
    doc = json.loads(r.stderr)
    assert doc["error"].startswith(f"cannot reach Adele at {closed_url} ({VANTAGE})")
    assert UNBLOCK in doc["remediation"]


# ── the client's own limit ─────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("mode", ["--json", "--text"])
def test_own_limit_is_exit_124_naming_it(py: str, scratch: Path, adele: FakeAdele, mode: str) -> None:
    adele.answer("POST", "/v1/requests", 200, PERFORMED, delay=10)
    t0 = time.monotonic()
    r = go(py, scratch, adele.url, mode, *CREATE, "--timeout", "0.5", timeout=10)
    elapsed = time.monotonic() - t0
    assert r.returncode == 124, r.stderr
    assert elapsed < 3, f"took {elapsed:.1f} s against a 0.5 s limit"
    assert r.stdout == ""
    no_traceback(r)
    text = r.stderr if mode == "--text" else json.loads(r.stderr)["error"]
    assert "no answer within 0.5 s" in text, text
    assert len(adele.received()) == 1


# ── usage: refused before anything is sent ─────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("args", "words"),
    [
        ([], "no verb given"),
        (["request"], "a capability and an action"),
        (["request", "standin.box"], "a capability and an action"),
        (["request", "standin.box", "create"], "--name"),
        ([*CREATE, "--ttl", "5x"], "--ttl '5x'"),
        ([*CREATE, "--ttl", ""], "--ttl ''"),
        ([*CREATE, "--timeout", "0"], "--timeout"),
        ([*CREATE, "--timeout", "-1"], "--timeout"),
        ([*CREATE, "--timeout", "nan"], "--timeout"),
        ([*CREATE, "--timeout", "inf"], "--timeout"),
        ([*CREATE, "--port", "http"], "--port"),
        (["delete"], "VERB"),
    ],
)
def test_usage_is_exit_2_and_sends_nothing(
    py: str, scratch: Path, adele: FakeAdele, args: list[str], words: str
) -> None:
    r = go(py, scratch, adele.url, "--text", *args)
    assert r.returncode == 2
    assert r.stdout == ""
    line = one_error_line(r)
    assert line.startswith("error: ") and "(code 2)" in line, line
    assert words in line, line
    assert adele.received() == []


# ── conformance (C1-C7) with Adele reachable and not ───────────────────────────────────────────


@pytest.mark.parametrize("reachable", [True, False], ids=["reachable", "unreachable"])
def test_conform_passes_either_way(
    tmp_path: Path, scratch: Path, adele: FakeAdele, closed_url: str, reachable: bool
) -> None:
    tools = tmp_path / "adele-bin"
    install(ADELE, tools)
    conf = tmp_path / "conf"
    install(TOOLS_DIR / "timelike-conform", conf)
    url = adele.url if reachable else closed_url
    env = env_for(scratch, [tools], on_path=[tools, conf], **{URL_ENV: url})
    r = conform(env, "--json", timeout=30)
    doc = json.loads(r.stdout)
    assert r.returncode == 0, doc["failures"]
    assert (doc["verdict"], doc["checked"], doc["tools"]) == ("pass", 1, ["adele"])
    probes = [s for s in adele.received() if s.path == "/v1/health"]
    assert bool(probes) is reachable


# ── rule 16: one session event per invocation ──────────────────────────────────────────────────


def test_one_event_per_invocation(py: str, scratch: Path, adele: FakeAdele, closed_url: str) -> None:
    expected: list[int] = []

    def call(url: str, *args: str) -> None:
        r = go(py, scratch, url, *args)
        expected.append(r.returncode)
        assert len(events(scratch, SESSION)) == len(expected), args

    call(adele.url, "--json", "status")
    call(closed_url, "--json", "status")
    call(adele.url, "--json", "grants")
    call(adele.url, "--json", *CREATE)
    adele.answer("POST", "/v1/requests", 403, REFUSED)
    call(adele.url, "--json", *CREATE, "--port", "22")
    call(adele.url, "--json", "request")
    assert expected == [0, 1, 0, 0, 4, 2]
    evs = events(scratch, SESSION)
    assert [e["exit"] for e in evs] == expected
    event_schema = schema.load("event.schema.json")
    for ev in evs:
        assert (ev["tool"], ev["session"]) == ("adele", SESSION)
        assert schema.errors(ev, event_schema) == []


# ── answered, but not well: reached is not "unreachable", and Adele's own error text is shown ───


def test_status_answered_unhealthy_is_reached_not_unreachable(
    py: str, scratch: Path, adele: FakeAdele
) -> None:
    adele.answer("GET", "/v1/health", 500, {"error": "the ledger failed: disk I/O error"})
    r = go(py, scratch, adele.url, "--json", "status")
    assert r.returncode == 1, r.stderr
    doc = doc_of(r)
    assert doc["reachable"] is True
    assert "unreachable" not in doc["verdict"]
    assert "answered from the agent container but not healthy" in doc["verdict"]
    assert "the ledger failed: disk I/O error" in doc["verdict"]


def test_grants_error_shows_adeles_text(py: str, scratch: Path, adele: FakeAdele) -> None:
    adele.answer("GET", "/v1/grants", 500, {"error": "the ledger failed: locked", "remediation": "retry"})
    r = go(py, scratch, adele.url, "--text", "grants")
    assert r.returncode == 1
    line = one_error_line(r)
    assert "the ledger failed: locked" in line and "retry" in line, line
