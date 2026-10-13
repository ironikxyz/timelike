"""Units for benchlib.standin, the model stand-in (feature 002 slice 1, FR-47), on loopback.

The harnesses themselves are run against it when the transcripts are recorded (T041, tests/fixtures/
transcripts/README.md); here each protocol shape is exercised over real HTTP.
"""

from __future__ import annotations

import http.client
import json
from collections.abc import Iterator
from typing import Any

import pytest
from benchlib import catalog, fakeagent
from benchlib.standin import FINAL_TEXT, TITLE_TEXT, StandIn


@pytest.fixture
def standin() -> Iterator[StandIn]:
    s = StandIn().start()
    s.set_script(["echo one", "echo two"])
    yield s
    s.stop()


def post(s: StandIn, path: str, body: dict[str, Any]) -> tuple[int, str, str]:
    conn = http.client.HTTPConnection("127.0.0.1", s.port, timeout=10)
    try:
        headers = {"Content-Type": "application/json", "Authorization": "Bearer not-a-key"}
        conn.request("POST", path, body=json.dumps(body), headers=headers)
        r = conn.getresponse()
        return r.status, r.getheader("Content-Type") or "", r.read().decode()
    finally:
        conn.close()


def sse(text: str) -> list[Any]:
    out = []
    for line in text.splitlines():
        if line.startswith("data: "):
            data = line[len("data: ") :]
            out.append(data if data == "[DONE]" else json.loads(data))
    return out


CHAT_TOOLS = [{"type": "function", "function": {"name": "bash", "parameters": {}}}]
RESP_TOOLS = [{"type": "function", "name": "exec_command", "parameters": {}}]


def test_chat_streams_the_next_command_as_a_bash_call(standin: StandIn) -> None:
    body = {
        "model": "m/x-0813",
        "stream": True,
        "tools": CHAT_TOOLS,
        "messages": [{"role": "user", "content": "go"}],
    }
    status, ctype, text = post(standin, "/api/v1/chat/completions", body)
    assert (status, ctype) == (200, "text/event-stream")
    events = sse(text)
    call = events[0]["choices"][0]["delta"]["tool_calls"][0]["function"]
    assert call["name"] == "bash" and json.loads(call["arguments"])["command"] == "echo one"
    assert events[1]["choices"][0]["finish_reason"] == "tool_calls"
    assert "cost" in events[1]["usage"] and events[-1] == "[DONE]"
    assert events[0]["model"] == "m/x-0813"


def test_progress_comes_from_the_tool_results_in_the_request(standin: StandIn) -> None:
    msgs = [{"role": "user", "content": "go"}, {"role": "tool", "content": "one"}]
    _, _, text = post(standin, "/api/v1/chat/completions", {"tools": CHAT_TOOLS, "messages": msgs})
    msg = json.loads(text)["choices"][0]["message"]
    assert json.loads(msg["tool_calls"][0]["function"]["arguments"])["command"] == "echo two"
    msgs.append({"role": "tool", "content": "two"})
    _, _, text = post(standin, "/api/v1/chat/completions", {"tools": CHAT_TOOLS, "messages": msgs})
    assert json.loads(text)["choices"][0] == {
        "index": 0,
        "message": {"role": "assistant", "content": FINAL_TEXT},
        "finish_reason": "stop",
    }


def test_a_request_without_tools_gets_a_title(standin: StandIn) -> None:
    _, _, text = post(standin, "/api/v1/chat/completions", {"messages": []})
    assert json.loads(text)["choices"][0]["message"]["content"] == TITLE_TEXT


def test_responses_streams_an_exec_command_call(standin: StandIn) -> None:
    body = {"model": "m/x-0813", "stream": True, "tools": RESP_TOOLS, "input": [], "store": False}
    status, ctype, text = post(standin, "/api/v1/responses", body)
    assert (status, ctype) == (200, "text/event-stream")
    events = sse(text)
    done = events[-1]
    assert done["type"] == "response.completed"
    item = done["response"]["output"][0]
    assert item["type"] == "function_call" and item["name"] == "exec_command"
    assert json.loads(item["arguments"]) == {"cmd": "echo one"}
    assert "cost" in done["response"]["usage"]


def test_responses_finishes_with_a_message(standin: StandIn) -> None:
    items = [{"type": "function_call_output", "call_id": "c", "output": "x"}] * 2
    _, _, text = post(standin, "/api/v1/responses", {"tools": RESP_TOOLS, "input": items})
    out = json.loads(text)["output"][0]
    assert out["type"] == "message" and out["content"][0]["text"] == FINAL_TEXT


def test_faults_answer_an_error_status_then_clear(standin: StandIn) -> None:
    standin.fail_next(429, 2, "rate limited")
    body = {"tools": CHAT_TOOLS, "messages": []}
    assert post(standin, "/api/v1/chat/completions", body)[0] == 429
    assert post(standin, "/api/v1/chat/completions", body)[0] == 429
    assert post(standin, "/api/v1/chat/completions", body)[0] == 200


def test_an_unknown_route_is_404(standin: StandIn) -> None:
    assert post(standin, "/api/v1/embeddings", {})[0] == 404


def test_the_script_for_a_task_is_its_fake_policy_happy_path() -> None:
    task = catalog.by_id("git-inspect")
    assert fakeagent.happy_path(task.policy) == ("git log -n 5 > out/log.txt", "git diff > out/diff.txt")
    for t in catalog.CATALOG:
        path = fakeagent.happy_path(t.policy)
        assert path and path[0] == t.policy.step(t.policy.start).command
