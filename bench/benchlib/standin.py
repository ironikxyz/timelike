"""standin — timelike's model stand-in: a scripted model behind the providers' own protocols (FR-47).

The live path (harness image, placement, relay, parsers, report) has to run in the lane, which never has a
key. The stand-in takes the model's place there. It speaks what the two live harnesses send (research RB12):
- OpenAI **chat completions** (`…/chat/completions`), OpenCode's protocol;
- OpenAI **Responses** (`…/responses`), Codex CLI's;

streamed (server-sent events) or not, and answers each request that offers tools with the **next command of
its script** as a call to the harness's own shell tool, picked from the tools the request offers (`bash`,
`exec_command`, `shell`, `shell_command`). How far along the script a conversation is comes from the
request itself (the number of tool results it carries), so the stand-in keeps no conversation state. When the
script is done it answers with plain text, which ends the harness's run. A request offering no tools
(OpenCode's title request) gets a short text answer.

Every answer carries `usage` with `cost`, as OpenRouter's always does, so the relay's accounting runs on the
same shape. Units can make it answer an error status for the next N requests, to stand in for 429s and 5xx.

What it cannot show (P005, llm-apis Q001): that a real model's output parses. It is the harness's own output
that the transcripts record, and the first live run is a test tier of its own. Stdlib only (constitution H5).
"""

from __future__ import annotations

import json
import threading
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

FINAL_TEXT = "done"
TITLE_TEXT = "Bench task"
STANDIN_MODEL_NOTE = "timelike-model-standin"

# Chat completions: OpenCode's shell tool. Responses: Codex's, in the order tried.
_CHAT_SHELLS = ("bash", "shell")
_RESPONSES_SHELLS = ("exec_command", "shell_command", "shell", "local_shell")


@dataclass
class Fault:
    status: int
    remaining: int
    message: str = "stand-in fault"


@dataclass
class State:
    script: tuple[str, ...] = ()
    cost_per_response: float = 0.0
    model_answer: str = ""  # the model id to answer with; "" echoes the request's
    faults: list[Fault] = field(default_factory=list)
    requests: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)


def _tool_names(tools: Any) -> list[str]:
    names: list[str] = []
    for t in tools or []:
        if isinstance(t, dict):
            name = t.get("name") or (t.get("function") or {}).get("name")
            if isinstance(name, str):
                names.append(name)
    return names


def _results_in(items: Any) -> int:
    """Tool results already in the conversation: chat `role: tool`, Responses `function_call_output`."""
    n = 0
    for it in items or []:
        if isinstance(it, dict) and (it.get("role") == "tool" or it.get("type") == "function_call_output"):
            n += 1
    return n


def _usage_chat(cost: float) -> dict[str, Any]:
    return {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15, "cost": cost}


def _usage_responses(cost: float) -> dict[str, Any]:
    return {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15, "cost": cost}


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server: _Server

    def log_message(self, format: str, *args: Any) -> None:
        pass

    def _json(self, status: int, body: dict[str, Any]) -> None:
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _events(self, events: Sequence[tuple[str, Any]]) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()
        for name, data in events:
            if name:
                self.wfile.write(f"event: {name}\n".encode())
            payload = data if isinstance(data, str) else json.dumps(data)
            self.wfile.write(f"data: {payload}\n\n".encode())
            self.wfile.flush()
        self.close_connection = True

    def do_GET(self) -> None:
        if self.path.split("?", 1)[0].rstrip("/").endswith("/models"):
            self._json(200, {"object": "list", "data": [{"id": self.server.state.model_answer or "standin"}]})
        else:
            self._json(404, {"error": {"message": f"stand-in: no route {self.path}"}})

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._json(400, {"error": {"message": "stand-in: body is not JSON"}})
            return
        st = self.server.state
        with st.lock:
            st.requests += 1
            fault = next((f for f in st.faults if f.remaining > 0), None)
            if fault is not None:
                fault.remaining -= 1
        if fault is not None:
            self._json(fault.status, {"error": {"message": fault.message, "code": fault.status}})
            return
        path = self.path.split("?", 1)[0]
        if path.endswith("/chat/completions"):
            self._chat(body)
        elif path.endswith("/responses"):
            self._responses(body)
        else:
            self._json(404, {"error": {"message": f"stand-in: no route {path}"}})

    def _next(self, body: dict[str, Any], items: Any, shells: Sequence[str]) -> tuple[str, str]:
        """(tool, command) to call next, or ("", text) to answer with text."""
        offered = _tool_names(body.get("tools"))
        if not offered:
            return "", TITLE_TEXT
        tool = next((s for s in shells if s in offered), "")
        step = _results_in(items)
        script = self.server.state.script
        if not tool or step >= len(script):
            return "", FINAL_TEXT if tool else f"stand-in: no shell tool among {offered}"
        return tool, script[step]

    def _model(self, body: dict[str, Any]) -> str:
        return self.server.state.model_answer or str(body.get("model") or STANDIN_MODEL_NOTE)

    def _chat(self, body: dict[str, Any]) -> None:
        tool, value = self._next(body, body.get("messages"), _CHAT_SHELLS)
        model, cost = self._model(body), self.server.state.cost_per_response
        gen = "gen-" + uuid.uuid4().hex[:16]
        if tool:
            args = {"command": value, "description": "bench stand-in step"}
            delta: dict[str, Any] = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "index": 0,
                        "id": "call_" + uuid.uuid4().hex[:8],
                        "type": "function",
                        "function": {"name": tool, "arguments": json.dumps(args)},
                    }
                ],
            }
            finish = "tool_calls"
        else:
            delta, finish = {"role": "assistant", "content": value}, "stop"
        if body.get("stream"):
            self._events(
                [
                    (
                        "",
                        {
                            "id": gen,
                            "object": "chat.completion.chunk",
                            "model": model,
                            "choices": [{"index": 0, "delta": delta, "finish_reason": None}],
                        },
                    ),
                    (
                        "",
                        {
                            "id": gen,
                            "object": "chat.completion.chunk",
                            "model": model,
                            "choices": [{"index": 0, "delta": {}, "finish_reason": finish}],
                            "usage": _usage_chat(cost),
                        },
                    ),
                    ("", "[DONE]"),
                ]
            )
            return
        self._json(
            200,
            {
                "id": gen,
                "object": "chat.completion",
                "model": model,
                "choices": [{"index": 0, "message": delta, "finish_reason": finish}],
                "usage": _usage_chat(cost),
            },
        )

    def _responses(self, body: dict[str, Any]) -> None:
        tool, value = self._next(body, body.get("input"), _RESPONSES_SHELLS)
        model, cost = self._model(body), self.server.state.cost_per_response
        rid = "gen-" + uuid.uuid4().hex[:16]
        item: dict[str, Any]
        if tool:
            if tool == "exec_command":
                args: dict[str, Any] = {"cmd": value}
            elif tool == "shell_command":
                args = {"command": value}
            else:
                args = {"command": ["bash", "-lc", value]}
            item = {
                "type": "function_call",
                "id": "fc_" + uuid.uuid4().hex[:8],
                "status": "completed",
                "call_id": "call_" + uuid.uuid4().hex[:8],
                "name": tool,
                "arguments": json.dumps(args),
            }
        else:
            item = {
                "type": "message",
                "id": "msg_" + uuid.uuid4().hex[:8],
                "role": "assistant",
                "status": "completed",
                "content": [{"type": "output_text", "text": value, "annotations": []}],
            }
        resp = {
            "id": rid,
            "object": "response",
            "model": model,
            "status": "completed",
            "output": [item],
            "usage": _usage_responses(cost),
        }
        if body.get("stream"):
            self._events(
                [
                    (
                        "response.created",
                        {
                            "type": "response.created",
                            "response": {**resp, "status": "in_progress", "output": []},
                        },
                    ),
                    (
                        "response.output_item.added",
                        {"type": "response.output_item.added", "output_index": 0, "item": item},
                    ),
                    (
                        "response.output_item.done",
                        {"type": "response.output_item.done", "output_index": 0, "item": item},
                    ),
                    ("response.completed", {"type": "response.completed", "response": resp}),
                ]
            )
            return
        self._json(200, resp)


class _Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, addr: tuple[str, int], state: State) -> None:
        self.state = state
        super().__init__(addr, _Handler)


class StandIn:
    """The stand-in on `host:port` (0: any free port), in a daemon thread of this process."""

    def __init__(self, host: str = "127.0.0.1", port: int = 0) -> None:
        self.state = State()
        self._server = _Server((host, port), self.state)
        self._thread = threading.Thread(target=self._server.serve_forever, name="bench-standin", daemon=True)

    @property
    def port(self) -> int:
        return int(self._server.server_address[1])

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self) -> StandIn:
        self._thread.start()
        return self

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()

    def set_script(self, commands: Sequence[str]) -> None:
        with self.state.lock:
            self.state.script = tuple(commands)

    def fail_next(self, status: int, count: int = 1, message: str = "stand-in fault") -> None:
        with self.state.lock:
            self.state.faults.append(Fault(status, count, message))
