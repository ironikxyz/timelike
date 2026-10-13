"""Units for benchlib.relay (feature 002 slice 1, FR-25, FR-26, FR-33, FR-36): the relay in front of the
model stand-in, both on loopback, with a client speaking as a harness does.

The relay holds the key (FOR-MENTOR Item 25, ruled (b)): the client below sends what a harness sends, the
placeholder, and the relay's own test key (never a real one) is the only credential the stand-in sees.
"""

from __future__ import annotations

import dataclasses
import http.client
import json
from collections.abc import Iterator
from typing import Any

import pytest
from benchlib.harness import KEY_PLACEHOLDER
from benchlib.relay import REFUSALS, SENDERS, Relay, generation_cost, screen
from benchlib.standin import FINAL_TEXT, StandIn

KEY = "not-a-key-but-unique-7f3a91"  # the relay's test key: unique, so a leak of it is findable
MODEL = "deepseek/deepseek-v4-pro-0813"
CHAT_TOOLS = [{"type": "function", "function": {"name": "bash", "parameters": {}}}]
RESP_TOOLS = [{"type": "function", "name": "exec_command", "parameters": {}}]


@pytest.fixture
def standin() -> Iterator[StandIn]:
    s = StandIn().start()
    s.set_script(["echo one", "echo two", "echo three"])
    s.state.cost_per_response = 0.25
    yield s
    s.stop()


def relay_for(standin: StandIn, turn_cap: int = 30, spend_cap: float = 10.0, key: str | None = KEY) -> Relay:
    return Relay(
        standin.url,
        turn_cap=turn_cap,
        spend_cap_usd=spend_cap,
        model=MODEL,
        key=key,
        host="127.0.0.1",
        port=0,
    ).start()


@pytest.fixture
def relay(standin: StandIn) -> Iterator[Relay]:
    r = relay_for(standin)
    r.begin_run()
    yield r
    r.stop()


def ask(
    relay: Relay,
    path: str,
    body: dict[str, Any] | None,
    method: str = "POST",
    extra: dict[str, str] | None = None,
) -> tuple[int, str, str]:
    """As a harness asks: with the placeholder it was given as its key."""
    conn = http.client.HTTPConnection("127.0.0.1", relay.port, timeout=10)
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {KEY_PLACEHOLDER}",
            **(extra or {}),
        }
        conn.request(method, path, body=json.dumps(body) if body is not None else None, headers=headers)
        r = conn.getresponse()
        return r.status, r.getheader("Content-Type") or "", r.read().decode()
    finally:
        conn.close()


def chat(relay: Relay, results: int = 0, stream: bool = True, tools: bool = True) -> tuple[int, str, str]:
    msgs: list[dict[str, Any]] = [{"role": "user", "content": "go"}]
    msgs += [{"role": "tool", "content": "x"}] * results
    body: dict[str, Any] = {"model": MODEL, "stream": stream, "messages": msgs}
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
    body = {"model": MODEL, "stream": True, "tools": RESP_TOOLS, "input": [], "store": False}
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
    relay = Relay(
        "http://127.0.0.1:9", turn_cap=30, spend_cap_usd=10, model=MODEL, key=KEY, host="127.0.0.1", port=0
    ).start()
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


class Spy:
    """Records the credential headers each request reaching the stand-in carried."""

    def __init__(self, standin: StandIn) -> None:
        self.seen: list[dict[str, str]] = []
        self.cls = standin._server.RequestHandlerClass  # type: ignore[attr-defined]
        self.originals = {m: getattr(self.cls, m) for m in ("do_GET", "do_POST")}

    def __enter__(self) -> Spy:
        for name, original in self.originals.items():

            def spy(handler: Any, original: Any = original) -> None:
                self.seen.append({k.lower(): v for k, v in handler.headers.items()})
                original(handler)

            setattr(self.cls, name, spy)
        return self

    def __exit__(self, *exc: object) -> None:
        for name, original in self.originals.items():
            setattr(self.cls, name, original)


# --- the ruling's conditions (Item 25 (b)), one or more units each ---------------------------------------


def test_c1_the_relay_replaces_the_authorization_a_request_arrives_with(
    standin: StandIn, relay: Relay
) -> None:
    with Spy(standin) as spy:
        chat(relay)  # the placeholder
        ask(
            relay,
            "/api/v1/chat/completions",
            {"model": MODEL, "messages": []},
            extra={"Authorization": "Bearer other"},
        )
        ask(
            relay,
            "/api/v1/responses",
            {"model": MODEL, "input": "go"},
            extra={"X-Api-Key": "k", "Cookie": "c=1"},
        )
    assert [h.get("authorization") for h in spy.seen] == [f"Bearer {KEY}"] * 3
    assert not any(k in h for h in spy.seen for k in ("x-api-key", "cookie", "api-key"))
    assert not any(KEY_PLACEHOLDER in v or v == "Bearer other" for h in spy.seen for v in h.values())


def test_c1_with_the_stand_in_no_credential_is_forwarded_at_all(standin: StandIn) -> None:
    relay = relay_for(standin, key=None)
    try:
        relay.begin_run()
        with Spy(standin) as spy:
            chat(relay)
        assert spy.seen and "authorization" not in spy.seen[0]
    finally:
        relay.stop()


def test_c2_the_placeholder_is_fixed_documented_and_not_key_shaped() -> None:
    from benchlib import harness as hz

    # Fixed, and what harness.py documents; words, no provider prefix, no entropy, so never mistaken for a
    # key.
    assert KEY_PLACEHOLDER == "placeholder-the-bench-relay-adds-the-key"
    assert all(w.isalpha() and w.islower() for w in KEY_PLACEHOLDER.split("-"))
    assert not KEY_PLACEHOLDER.startswith(("sk-", "sk_", "or-"))
    # The same for every harness, and what each harness's environment carries for its key variable.
    for pins in (("1.19.0", "0.162.1"), ("9.9.9", "9.9.9")):
        for spec in hz.specs(*pins).values():
            env = spec.exec_env("http://bench-relay:8417/api/v1", MODEL)
            assert env[hz.KEY_VAR] == KEY_PLACEHOLDER, spec.name


@pytest.mark.parametrize(
    ("method", "target", "body", "verdict"),
    [
        ("POST", "/api/v1/chat/completions", {"model": MODEL}, ""),
        ("POST", "/api/v1/responses?x=1", {"model": MODEL}, ""),
        ("GET", "/api/v1/generation?id=gen-1", None, ""),
        ("GET", "/api/v1/models", None, "route-not-allowed"),
        ("POST", "/api/v1/embeddings", {"model": MODEL}, "route-not-allowed"),
        ("GET", "/api/v1/chat/completions", None, "route-not-allowed"),
        ("POST", "http://evil.example/api/v1/chat/completions", {"model": MODEL}, "route-not-allowed"),
        ("CONNECT", "evil.example:443", None, "route-not-allowed"),
        ("POST", "/api/v1/chat/completions", {"messages": []}, "no-model"),
        ("POST", "/api/v1/responses", None, "no-model"),
        ("POST", "/api/v1/chat/completions", {"model": "openai/gpt-x"}, "other-model"),
    ],
)
def test_c4_screen_forwards_only_the_harness_routes_and_the_pinned_model(
    method: str, target: str, body: Any, verdict: str
) -> None:
    got, why = screen(method, target, body, MODEL)
    assert got == verdict and (verdict in REFUSALS or (not verdict and not why))


def test_c4_refusals_are_named_recorded_and_never_forwarded(standin: StandIn, relay: Relay) -> None:
    before = standin.state.requests
    with Spy(standin) as spy:
        assert ask(relay, "/api/v1/models", None, method="GET")[0] == 403
        assert ask(relay, "/api/v1/chat/completions", {"messages": []})[0] == 403
        status, _, text = ask(
            relay, "/api/v1/chat/completions", {"model": "openai/gpt-x", "tools": CHAT_TOOLS}
        )
        assert ask(relay, "/api/v1/chat/completions", {"model": MODEL}, method="DELETE")[0] == 403
    assert status == 403 and "refused (other-model)" in text and MODEL in text
    assert spy.seen == [] and standin.state.requests == before
    acct = relay.end_run()
    assert acct.refused == {"route-not-allowed": 2, "no-model": 1, "other-model": 1}
    assert acct.other_model == "openai/gpt-x" and acct.requests == 4
    assert acct.summary()["refused"] == acct.refused


def test_c4_generation_stats_are_forwarded_with_the_relay_s_key(standin: StandIn, relay: Relay) -> None:
    with Spy(standin) as spy:
        status, _, _ = ask(relay, "/api/v1/generation?id=gen-1", None, method="GET")
    assert status == 404  # the stand-in has no such route; what matters is that it was reached, with the key
    assert [h.get("authorization") for h in spy.seen] == [f"Bearer {KEY}"]


def test_c5_every_request_counts_whoever_sent_it_and_the_summary_says_senders_are_not_told_apart(
    standin: StandIn,
) -> None:
    relay = relay_for(standin, turn_cap=2)
    try:
        relay.begin_run()
        chat(relay)  # "the harness"
        # "an agent's command" — curl from inside the container would look exactly like this
        ask(relay, "/api/v1/chat/completions", {"model": MODEL, "tools": CHAT_TOOLS, "messages": []},
            extra={"User-Agent": "curl/8.14.1"})  # fmt: skip
        status, _, text = chat(relay, results=1)
        assert status == 400 and "turn-cap reached" in text
        acct = relay.end_run()
        assert (acct.turns, acct.stopped_by) == (3, "turn-cap")
        assert acct.cost_usd == pytest.approx(0.5)  # both forwarded requests spent
        assert acct.summary()["senders"] == SENDERS and "not told apart" in SENDERS
    finally:
        relay.stop()


def test_c3_the_key_appears_in_no_accounting_summary_or_refusal(standin: StandIn, relay: Relay) -> None:
    chat(relay)
    texts = [ask(relay, "/api/v1/models", None, method="GET")[2], ask(relay, "/x", {"model": MODEL})[2]]
    acct = relay.end_run()
    assert KEY not in repr(dataclasses.asdict(acct)) + json.dumps(acct.summary()) + "".join(texts)
    assert KEY not in repr(relay) and KEY not in str(vars(relay).get("model"))


def test_the_relay_refuses_to_start_without_the_pinned_model(standin: StandIn) -> None:
    with pytest.raises(ValueError, match="pinned model"):
        Relay(standin.url, turn_cap=1, spend_cap_usd=1, model="", host="127.0.0.1", port=0)


def test_generation_cost_reads_openrouter_s_figure_or_nothing() -> None:
    assert generation_cost("http://127.0.0.1:9", "gen-x", KEY, timeout_s=2) is None


def test_the_final_answer_text_is_relayed_whole(relay: Relay) -> None:
    status, _, text = chat(relay, results=3, stream=False)
    assert status == 200 and json.loads(text)["choices"][0]["message"]["content"] == FINAL_TEXT
