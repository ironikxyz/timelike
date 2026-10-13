"""Units for benchlib.relay (feature 002 slice 1, FR-25, FR-26, FR-33, FR-36): the relay in front of the
model stand-in, both on loopback, with a client speaking as a harness does.
"""

from __future__ import annotations

import dataclasses
import http.client
import json
from collections.abc import Iterator
from typing import Any

import pytest
from benchlib.relay import Relay, generation_cost
from benchlib.standin import FINAL_TEXT, StandIn

KEY = "not-a-key-but-unique-7f3a91"
CHAT_TOOLS = [{"type": "function", "function": {"name": "bash", "parameters": {}}}]
RESP_TOOLS = [{"type": "function", "name": "exec_command", "parameters": {}}]


@pytest.fixture
def standin() -> Iterator[StandIn]:
    s = StandIn().start()
    s.set_script(["echo one", "echo two", "echo three"])
    s.state.cost_per_response = 0.25
    yield s
    s.stop()


def relay_for(standin: StandIn, turn_cap: int = 30, spend_cap: float = 10.0) -> Relay:
    return Relay(standin.url, turn_cap=turn_cap, spend_cap_usd=spend_cap, host="127.0.0.1", port=0).start()


@pytest.fixture
def relay(standin: StandIn) -> Iterator[Relay]:
    r = relay_for(standin)
    r.begin_run()
    yield r
    r.stop()


def ask(relay: Relay, path: str, body: dict[str, Any]) -> tuple[int, str, str]:
    conn = http.client.HTTPConnection("127.0.0.1", relay.port, timeout=10)
    try:
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {KEY}"}
        conn.request("POST", path, body=json.dumps(body), headers=headers)
        r = conn.getresponse()
        return r.status, r.getheader("Content-Type") or "", r.read().decode()
    finally:
        conn.close()


def chat(relay: Relay, results: int = 0, stream: bool = True, tools: bool = True) -> tuple[int, str, str]:
    msgs: list[dict[str, Any]] = [{"role": "user", "content": "go"}]
    msgs += [{"role": "tool", "content": "x"}] * results
    body: dict[str, Any] = {"model": "deepseek/deepseek-v4-pro-0813", "stream": stream, "messages": msgs}
    if tools:
        body["tools"] = CHAT_TOOLS
    return ask(relay, "/api/v1/chat/completions", body)


def test_a_streamed_answer_passes_through_and_is_accounted(relay: Relay) -> None:
    status, ctype, text = chat(relay)
    assert (status, ctype) == (200, "text/event-stream")
    assert '"echo one"' in text.replace("\\", "") and "[DONE]" in text
    acct = relay.end_run()
    assert (acct.requests, acct.turns, acct.statuses) == (1, 1, {"200": 1})
    assert acct.models == ["deepseek/deepseek-v4-pro-0813"]
    assert len(acct.generations) == 1 and acct.cost_usd == pytest.approx(0.25)
    assert (acct.tokens_in, acct.tokens_out) == (10, 5)
    assert acct.last_asked_tools is True
    assert relay.spent_usd == pytest.approx(0.25)


def test_a_request_without_tools_is_not_a_turn(relay: Relay) -> None:
    chat(relay, tools=False)
    acct = relay.end_run()
    assert (acct.requests, acct.turns) == (1, 0)
    assert acct.last_asked_tools is False


def test_responses_are_accounted_too(relay: Relay) -> None:
    body = {"model": "m/x-0813", "stream": True, "tools": RESP_TOOLS, "input": [], "store": False}
    status, _, _ = ask(relay, "/api/v1/responses", body)
    assert status == 200
    acct = relay.end_run()
    assert acct.turns == 1 and acct.cost_usd == pytest.approx(0.25) and acct.last_asked_tools is True


def test_the_final_text_answer_clears_last_asked_tools(relay: Relay) -> None:
    chat(relay, results=3, stream=False)
    acct = relay.end_run()
    assert acct.last_asked_tools is False


def test_the_turn_cap_answers_400_naming_it_and_stops_the_run(standin: StandIn) -> None:
    relay = relay_for(standin, turn_cap=2)
    try:
        relay.begin_run()
        assert chat(relay)[0] == 200
        assert chat(relay, results=1)[0] == 200
        status, _, text = chat(relay, results=2)
        assert status == 400 and "timelike-bench: turn-cap reached (2 turns per run)" in text
        assert chat(relay, tools=False)[0] == 400  # once stopped, nothing more goes upstream
        acct = relay.end_run()
        assert acct.stopped_by == "turn-cap" and standin.state.requests == 2
    finally:
        relay.stop()


def test_the_spend_cap_spans_runs(standin: StandIn) -> None:
    relay = relay_for(standin, spend_cap=0.5)
    try:
        relay.begin_run()
        assert chat(relay)[0] == 200
        relay.end_run()
        relay.begin_run()
        assert chat(relay)[0] == 200  # 0.25 spent before this one: under the cap
        status, _, text = chat(relay)
        assert status == 400 and "spend-cap reached ($0.50 per invocation)" in text
        assert relay.end_run().stopped_by == "spend-cap"
        assert relay.spend_cap_reached
    finally:
        relay.stop()


@pytest.mark.parametrize("code", [429, 500, 401])
def test_error_statuses_pass_through_and_are_counted(relay: Relay, standin: StandIn, code: int) -> None:
    standin.fail_next(code)
    assert chat(relay)[0] == code
    acct = relay.end_run()
    assert acct.statuses == {str(code): 1} and acct.last_status == str(code)
    assert acct.generations == [] and acct.cost_usd == 0


def test_an_upstream_that_does_not_answer_is_a_502_named_unreachable() -> None:
    relay = Relay("http://127.0.0.1:9", turn_cap=30, spend_cap_usd=10, host="127.0.0.1", port=0).start()
    try:
        relay.begin_run()
        status, _, text = chat(relay)
        assert status == 502 and "the upstream did not answer" in text
        assert relay.end_run().statuses == {"unreachable": 1}
    finally:
        relay.stop()


def test_a_missing_cost_is_named_not_estimated(relay: Relay, standin: StandIn) -> None:
    standin.state.cost_per_response = -1.0  # the stand-in then reports a cost the relay must not believe
    chat(relay)
    acct = relay.end_run()
    assert acct.cost_usd == 0 and acct.cost_unknown == acct.generations and len(acct.generations) == 1


def test_no_header_value_is_ever_recorded(relay: Relay) -> None:
    chat(relay)
    chat(relay, results=1, stream=False)
    acct = relay.end_run()
    assert KEY not in repr(dataclasses.asdict(acct)) and KEY not in json.dumps(acct.summary())


def test_the_key_reaches_the_upstream_unchanged(standin: StandIn, relay: Relay) -> None:
    # The stand-in does not check keys; this checks the header arrives, through a stand-in that records it.
    seen: list[str] = []
    original = standin._server.RequestHandlerClass.do_POST  # type: ignore[attr-defined]

    def spy(handler: Any) -> None:
        seen.append(handler.headers.get("Authorization", ""))
        original(handler)

    standin._server.RequestHandlerClass.do_POST = spy  # type: ignore[attr-defined]
    try:
        chat(relay)
    finally:
        standin._server.RequestHandlerClass.do_POST = original  # type: ignore[attr-defined]
    assert seen == [f"Bearer {KEY}"]


def test_generation_cost_reads_openrouter_s_figure_or_nothing() -> None:
    assert generation_cost("http://127.0.0.1:9", "gen-x", KEY, timeout_s=2) is None


def test_the_final_answer_text_is_relayed_whole(relay: Relay) -> None:
    status, _, text = chat(relay, results=3, stream=False)
    assert status == 200 and json.loads(text)["choices"][0]["message"]["content"] == FINAL_TEXT
