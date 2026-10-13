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

**The relay holds the key** (FOR-MENTOR Item 25, ruled (b) at 2026-10-13T07:12:57Z in
`bridge/feedback/02-20261013-071257-item-25-the-relay-holds-the-key.md`). Every harness is given
`harness.KEY_PLACEHOLDER` for its key variable; the relay drops any `Authorization` (and any other
credential-carrying header) a request arrives with, never forwarding the incoming value, and adds its own
`Authorization: Bearer <key>` from the key the driver read from the key file. With the model stand-in there
is no key, and the relay adds none. Nothing here logs, stores or writes a request header or the key, and the
accounting holds none.

**It forwards only what a harness needs** (the ruling's condition 4): to its one upstream, only on ROUTES
(chat completions, Responses, generation stats), and a model request only for the pinned model id. Anything
else is refused with a named verdict and recorded under `refused`, never forwarded: `route-not-allowed`
(another method or path, or a request naming another host in absolute form), `no-model` (a model request
naming no model), `other-model` (another model; the run then ends `stopped`, cause `model-refused`).

**Every request counts, whoever sent it** (condition 5). An agent's command shares the task container, its
network and its environment with the harness, so it can reach the relay; that is use, not reading, and it is
bounded by the same caps. The relay cannot tell a harness's request from a command's: both come from the same
address carrying the same placeholder, and any token the harness held the agent could read too. So nothing is
attributed to a sender, and the run's summary says so (`senders`).

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
# What a harness may ask for (the ruling's condition 4): method, path under the relay. Both harnesses' base
# URL is the relay's /api/v1. Model requests carry a body naming the model; generation stats are a GET by id.
MODEL_ROUTES = frozenset({("POST", "/api/v1/chat/completions"), ("POST", "/api/v1/responses")})
ROUTES = MODEL_ROUTES | {("GET", "/api/v1/generation")}
REFUSALS = ("route-not-allowed", "no-model", "other-model")
SENDERS = "not told apart: the harness and the agent's commands share one container, address and environment"
# Request headers that carry a credential: never forwarded, whatever they hold (condition 1).
_CREDENTIAL = frozenset({"authorization", "x-api-key", "api-key", "cookie"})
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
    refused: dict[str, int] = field(default_factory=dict)  # REFUSALS verdict → count, never forwarded
    other_model: str = ""  # the first model id refused as not the pinned one, cut to 100 characters

    def summary(self) -> dict[str, Any]:
        return {
            "requests": self.requests,
            "turns": self.turns,
            "statuses": dict(sorted(self.statuses.items())),
            "generations": len(self.generations),
            "models": list(self.models),
            "stopped_by": self.stopped_by,
            "refused": dict(sorted(self.refused.items())),
            "senders": SENDERS,
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
        model: str,
        key: str | None = None,
        host: str = "0.0.0.0",  # noqa: S104 — the internal network's interface; nothing else can reach it
        port: int = PORT,
    ) -> None:
        parts = urllib.parse.urlsplit(upstream)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise ValueError(f"upstream {upstream!r} is not an http(s) URL")
        if not model:
            raise ValueError("the relay needs the pinned model id: it forwards no other")
        self.upstream = parts
        self.model = model
        self._key = key  # in memory only; None with the stand-in. Never in a repr, a log or the accounting
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

    def authorization(self) -> dict[str, str]:
        """The one credential header the upstream sees: the relay's own, or none against the stand-in."""
        return {"Authorization": f"Bearer {self._key}"} if self._key else {}


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


def screen(method: str, target: str, body: Any, model: str) -> tuple[str, str]:
    """("", "") when the relay may forward this request, else (verdict, why) — condition 4."""
    path = target.split("?", 1)[0]
    if not target.startswith("/") or (method, path) not in ROUTES:
        return "route-not-allowed", f"{method} {target[:120]} is not a route a harness uses"
    if (method, path) not in MODEL_ROUTES:
        return "", ""
    asked = body.get("model") if isinstance(body, dict) else None
    if not isinstance(asked, str) or not asked:
        return "no-model", f"{method} {path} names no model"
    if asked != model:
        return "other-model", f"{asked[:100]!r} is not the pinned model {model}"
    return "", ""


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

    def _read_body(self) -> tuple[bytes, Any]:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        raw = self.rfile.read(min(length, _BODY_CAP)) if length > 0 else b""
        try:
            return raw, json.loads(raw) if raw else None
        except (json.JSONDecodeError, UnicodeDecodeError):
            return raw, None

    def _screened(self, body: Any) -> bool:
        """Refuses and records a request the relay does not forward (condition 4); True when it was."""
        relay = self.server.relay
        verdict, why = screen(self.command, self.path, body, relay.model)
        if not verdict:
            return False
        with relay.lock:
            acct = relay.run
            acct.requests += 1
            acct.refused[verdict] = acct.refused.get(verdict, 0) + 1
            if verdict == "other-model" and not acct.other_model:
                asked = body.get("model") if isinstance(body, dict) else ""
                acct.other_model = str(asked)[:100]
        msg = f"timelike-bench relay: refused ({verdict}): {why}"
        self._send_json(403, json.dumps({"error": {"message": msg, "code": 403}}).encode())
        return True

    def _refuse_method(self) -> None:
        self._read_body()
        self._screened(None)

    do_PUT = do_PATCH = do_DELETE = do_HEAD = do_OPTIONS = do_CONNECT = do_TRACE = _refuse_method

    def do_GET(self) -> None:
        if not self._screened(None):
            with self.server.relay.lock:
                self.server.relay.run.requests += 1
            self._forward(b"", None)

    def do_POST(self) -> None:
        raw, body = self._read_body()
        if self._screened(body):
            return
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
        # Condition 1: whatever credential the request arrived with is dropped, never forwarded; the relay's
        # own is the only one the upstream sees.
        headers = {k: v for k, v in self.headers.items() if k.lower() not in _HOP | _CREDENTIAL}
        headers.update(relay.authorization())
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
