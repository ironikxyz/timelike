"""relay — the only road from a live harness to the model, run inside the bench driver (FR-25, FR-26).

A live run's task containers sit on an internal network whose only other member is the driver. A harness's
base URL is the relay (`http://bench-relay:<port>/api/v1`); the relay forwards each request to the upstream
(`https://openrouter.ai`, or the model stand-in) and streams the answer back as it arrives. It exists because
three things the send asks for are only visible in the plaintext exchange (research RB15):

- **spend**, read from each answer's `usage.cost` (OpenRouter always includes it), so the spend cap can
  stop the next request; a generation without one is named for a generation-stats lookup afterwards;
- **turns**, counted the same way under every harness: a request that offers tools is a turn (a harness's
  title request offers none). The turn cap stops the next one;
- **what answered**: each status (429, 5xx and 401/403 name a `stopped` row's cause), the model id the
  provider answered with (cross-stack P003), and whether its last answer asked for tool calls, which tells
  "a call was in flight" from "the harness hung" when the run limit fires (FR-36).

**Headers are forwarded and never recorded.** The `Authorization` header the harness sends carries the key
(FOR-MENTOR Item 25 asks whether the relay should add it instead); nothing here logs, stores or writes a
request header, and the accounting holds none.

A cap answers HTTP 400 with `{"error": {"message": "timelike-bench: <cap> reached …"}}`, and every later
request of that run gets the same answer without reaching the upstream, whatever the harness does with it.
Stdlib only (constitution H5).
"""

from __future__ import annotations

import http.client
import json
import threading
import urllib.parse
from collections.abc import Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

PORT = 8417
ALIAS = "bench-relay"
UPSTREAM_TIMEOUT_S = 300.0
_HOP = frozenset(
    {
        "connection", "keep-alive", "transfer-encoding", "te", "trailer", "upgrade", "host",
        "content-length", "accept-encoding", "proxy-authorization", "proxy-connection",
    }
)  # fmt: skip
_BODY_CAP = 64 * 1024 * 1024  # a non-streamed answer is read up to this size, never without a bound


@dataclass
class Accounting:
    """One run's view from the relay. No header, and nothing a header held, is ever stored here."""

    requests: int = 0
    turns: int = 0
    statuses: dict[str, int] = field(default_factory=dict)
    generations: list[str] = field(default_factory=list)
    models: list[str] = field(default_factory=list)
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    cost_unknown: list[str] = field(default_factory=list)  # generation ids whose answer carried no cost
    last_status: str = ""
    last_asked_tools: bool = False
    waiting: int = 0  # requests still waiting on the upstream
    stopped_by: str = ""  # "", "turn-cap", "spend-cap"

    def summary(self) -> dict[str, Any]:
        return {
            "requests": self.requests,
            "turns": self.turns,
            "statuses": dict(sorted(self.statuses.items())),
            "generations": len(self.generations),
            "models": list(self.models),
            "stopped_by": self.stopped_by,
        }


def offers_tools(body: Any) -> bool:
    return isinstance(body, dict) and bool(body.get("tools"))


def _note_usage(acct: Accounting, usage: Any, gen: str) -> None:
    if not isinstance(usage, dict):
        if gen:
            acct.cost_unknown.append(gen)
        return
    tin = usage.get("prompt_tokens", usage.get("input_tokens"))
    tout = usage.get("completion_tokens", usage.get("output_tokens"))
    acct.tokens_in += tin if isinstance(tin, int) and not isinstance(tin, bool) else 0
    acct.tokens_out += tout if isinstance(tout, int) and not isinstance(tout, bool) else 0
    cost = usage.get("cost")
    if isinstance(cost, int | float) and not isinstance(cost, bool) and cost >= 0:
        acct.cost_usd += float(cost)
    elif gen:
        acct.cost_unknown.append(gen)


def _inner(doc: dict[str, Any]) -> dict[str, Any]:
    """A Responses stream event wraps the response; a chat completion or plain answer is the thing itself."""
    inner = doc.get("response")
    return inner if isinstance(inner, dict) else doc


def _asked_tools(doc: dict[str, Any]) -> bool:
    for choice in doc.get("choices") or []:
        if isinstance(choice, dict):
            if choice.get("finish_reason") == "tool_calls":
                return True
            for part in ("delta", "message"):
                if isinstance(choice.get(part), dict) and choice[part].get("tool_calls"):
                    return True
    resp = _inner(doc)
    return any(isinstance(o, dict) and o.get("type") == "function_call" for o in resp.get("output") or [])


def read_answer(acct: Accounting, docs: Iterator[dict[str, Any]]) -> None:
    """Account for one answer, given its JSON documents (one, or each SSE `data:` event in order)."""
    gen = model = ""
    usage: Any = None
    asked = False
    for doc in docs:
        inner = _inner(doc)
        gen = str(inner.get("id") or gen)
        model = str(inner.get("model") or model)
        if inner.get("usage") is not None:
            usage = inner.get("usage")
        asked = asked or _asked_tools(doc)
    if gen:
        acct.generations.append(gen)
    if model and model not in acct.models:
        acct.models.append(model)
    if gen or usage is not None:
        _note_usage(acct, usage, gen)
    acct.last_asked_tools = asked


def sse_documents(lines: list[bytes]) -> Iterator[dict[str, Any]]:
    for line in lines:
        if line.startswith(b"data:"):
            data = line[5:].strip()
            if data and data != b"[DONE]":
                try:
                    doc = json.loads(data)
                except json.JSONDecodeError:
                    continue
                if isinstance(doc, dict):
                    yield doc


class Relay:
    """The relay on `host:port`, forwarding to `upstream`, with a turn cap per run and a spend cap overall."""

    def __init__(
        self,
        upstream: str,
        *,
        turn_cap: int,
        spend_cap_usd: float,
        host: str = "0.0.0.0",  # noqa: S104 — the internal network's interface; nothing else can reach it
        port: int = PORT,
    ) -> None:
        parts = urllib.parse.urlsplit(upstream)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise ValueError(f"upstream {upstream!r} is not an http(s) URL")
        self.upstream = parts
        self.turn_cap = turn_cap
        self.spend_cap_usd = spend_cap_usd
        self.spent_usd = 0.0
        self.lock = threading.Lock()
        self.run = Accounting()
        self._server = _Server((host, port), self)
        self._thread = threading.Thread(target=self._server.serve_forever, name="bench-relay", daemon=True)

    @property
    def port(self) -> int:
        return int(self._server.server_address[1])

    def start(self) -> Relay:
        self._thread.start()
        return self

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()

    def begin_run(self) -> None:
        with self.lock:
            self.run = Accounting()

    def end_run(self) -> Accounting:
        with self.lock:
            done, self.run = self.run, Accounting()
            self.spent_usd += done.cost_usd
            return done

    @property
    def spend_cap_reached(self) -> bool:
        with self.lock:
            return self.spent_usd + self.run.cost_usd >= self.spend_cap_usd

    def connection(self) -> http.client.HTTPConnection:
        host, port = self.upstream.hostname or "", self.upstream.port
        if self.upstream.scheme == "https":
            return http.client.HTTPSConnection(host, port, timeout=UPSTREAM_TIMEOUT_S)
        return http.client.HTTPConnection(host, port, timeout=UPSTREAM_TIMEOUT_S)

    def upstream_path(self, path: str) -> str:
        return self.upstream.path.rstrip("/") + path


def generation_cost(relay_upstream: str, generation: str, key: str, timeout_s: float = 30.0) -> float | None:
    """OpenRouter's generation stats for one id (`GET /api/v1/generation?id=…`): its total cost, or None.

    Asked by the driver after a run, for a generation whose answer carried no `usage.cost` (FR-35). The key is
    sent as a header and appears nowhere else.
    """
    parts = urllib.parse.urlsplit(relay_upstream)
    conn_cls = http.client.HTTPSConnection if parts.scheme == "https" else http.client.HTTPConnection
    conn = conn_cls(parts.hostname or "", parts.port, timeout=timeout_s)
    try:
        query = urllib.parse.urlencode({"id": generation})
        conn.request("GET", f"{parts.path.rstrip('/')}/api/v1/generation?{query}",
                      headers={"Authorization": f"Bearer {key}"})  # fmt: skip
        r = conn.getresponse()
        body = r.read()
        if r.status != 200:
            return None
        data = json.loads(body).get("data") or {}
        cost = data.get("total_cost")
        return float(cost) if isinstance(cost, int | float) and not isinstance(cost, bool) else None
    except (OSError, ValueError, http.client.HTTPException):
        return None
    finally:
        conn.close()


def _refusal(cap: str, detail: str) -> bytes:
    return json.dumps(
        {"error": {"message": f"timelike-bench: {cap} reached ({detail})", "code": 400}}
    ).encode()


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server: _Server

    def log_message(self, format: str, *args: Any) -> None:
        pass  # the stdlib would print the request line; a header must never reach a log, so nothing does

    def _send_json(self, status: int, data: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        self._forward(b"", None)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            body: Any = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            body = None
        relay = self.server.relay
        refusal = b""
        with relay.lock:
            acct = relay.run
            acct.requests += 1
            acct.last_asked_tools = False  # a new request: the harness has run what the last answer asked for
            if offers_tools(body):
                acct.turns += 1
            if acct.stopped_by:
                refusal = _refusal(acct.stopped_by, "this run was already stopped")
            elif relay.turn_cap and acct.turns > relay.turn_cap:
                acct.stopped_by = "turn-cap"
                refusal = _refusal("turn-cap", f"{relay.turn_cap} turns per run")
            elif relay.spent_usd + acct.cost_usd >= relay.spend_cap_usd:
                acct.stopped_by = "spend-cap"
                refusal = _refusal("spend-cap", f"${relay.spend_cap_usd:.2f} per invocation")
            if refusal:
                acct.statuses["400 cap"] = acct.statuses.get("400 cap", 0) + 1
                acct.last_status = "400 cap"
        if refusal:
            self._send_json(400, refusal)
            return
        self._forward(raw, body)

    def _forward(self, raw: bytes, body: Any) -> None:
        relay = self.server.relay
        headers = {k: v for k, v in self.headers.items() if k.lower() not in _HOP}
        headers["Accept-Encoding"] = "identity"  # the answer is read for accounting, so it is not compressed
        if raw:
            headers["Content-Length"] = str(len(raw))
        with relay.lock:
            acct = relay.run
            acct.waiting += 1
        conn = relay.connection()
        try:
            try:
                conn.request(self.command, relay.upstream_path(self.path), body=raw or None, headers=headers)
                resp = conn.getresponse()
            except (OSError, http.client.HTTPException) as e:
                with relay.lock:
                    acct.statuses["unreachable"] = acct.statuses.get("unreachable", 0) + 1
                    acct.last_status = "unreachable"
                msg = f"timelike-bench relay: the upstream did not answer ({type(e).__name__}: {e})"
                self._send_json(502, json.dumps({"error": {"message": msg, "code": 502}}).encode())
                return
            status = str(resp.status)
            with relay.lock:
                acct.statuses[status] = acct.statuses.get(status, 0) + 1
                acct.last_status = status
            self._relay_answer(resp, acct, accounted=self.command == "POST")
        finally:
            conn.close()
            with relay.lock:
                acct.waiting -= 1

    def _relay_answer(self, resp: http.client.HTTPResponse, acct: Accounting, accounted: bool) -> None:
        relay = self.server.relay
        ctype = resp.getheader("Content-Type") or ""
        self.send_response(resp.status)
        for k, v in resp.getheaders():
            if k.lower() not in _HOP:
                self.send_header(k, v)
        streaming = "text/event-stream" in ctype
        if streaming:
            self.send_header("Connection", "close")
            self.end_headers()
            lines: list[bytes] = []
            while True:
                line = resp.readline()
                if not line:
                    break
                self.wfile.write(line)
                if line.strip() == b"":
                    self.wfile.flush()
                lines.append(line)
            self.wfile.flush()
            self.close_connection = True
            docs: Iterator[dict[str, Any]] = sse_documents(lines)
        else:
            data = resp.read(_BODY_CAP + 1)
            if len(data) > _BODY_CAP:
                data = data[:_BODY_CAP]
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            try:
                doc = json.loads(data) if data else None
            except json.JSONDecodeError:
                doc = None
            docs = iter([doc] if isinstance(doc, dict) else [])
        if accounted and resp.status == 200:
            with relay.lock:
                read_answer(acct, docs)


class _Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, addr: tuple[str, int], relay: Relay) -> None:
        self.relay = relay
        super().__init__(addr, _Handler)
