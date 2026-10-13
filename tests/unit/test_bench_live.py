"""Units for the live path of benchlib.runner (feature 002 slice 1, FR-24 to FR-37).

`live_ending` is pure, so every branch is driven directly. `run_live` is driven end to end on the host with
the real relay and the real model stand-in on loopback, and a session that stands in for the task container:
its "harness" makes the requests a harness makes and leaves behind a transcript the real harness wrote
(tests/fixtures/transcripts). The harness binaries themselves run in the Docker lane (--standin).
"""

from __future__ import annotations

import http.client
import json
from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest
from benchlib import catalog, runner, trace
from benchlib import harness as hz
from benchlib.executor import CallResult, Executor
from benchlib.keyfile import Gate, GateRefused
from benchlib.relay import Accounting, Relay
from benchlib.standin import StandIn

SHA = "c" * 40
DIGEST = "debian:trixie-slim@sha256:" + "d" * 64
CTX = runner.RunContext(SHA, DIGEST, "make bench-live", runner.Limits(2, 60), ("run", "view"))
FIX = Path(__file__).resolve().parents[1] / "fixtures" / "transcripts"
KEY = "not-a-key-unique-value-7f3a91"
OK = CallResult(0, 5, False, 0, 0, b"", b"")


def observed(**over: object) -> runner.Observed:
    base: dict[str, object] = {
        "acct": Accounting(),
        "harness_exit": 0,
        "hit_run_limit": False,
        "parsed": None,
        "parse_error": "",
        "check_ok": True,
        "check_why": "check passed",
    }
    base.update(over)
    return runner.Observed(**base)  # type: ignore[arg-type]


def failing(**over: object) -> runner.Observed:
    return observed(check_ok=False, check_why="check failed: x", **over)


def acct(**over: object) -> Accounting:
    a = Accounting()
    for k, v in over.items():
        setattr(a, k, v)
    return a


@pytest.mark.parametrize(
    ("o", "kind", "cause"),
    [
        (observed(acct=acct(stopped_by="turn-cap")), "stopped", "turn-cap"),
        (observed(acct=acct(stopped_by="spend-cap"), check_ok=True), "stopped", "spend-cap"),
        (observed(hit_run_limit=True, acct=acct(waiting=1)), "stopped", "api-unreachable"),
        (observed(hit_run_limit=True, acct=acct(last_asked_tools=True)), "hung", ""),
        (observed(hit_run_limit=True), "stopped", "harness-unresponsive"),
        (observed(parse_error="line 3 is not JSON"), "stopped", "transcript-unreadable"),
        (observed(acct=acct(last_status="429"), harness_exit=1), "completed", ""),  # the check decides first
        (failing(acct=acct(last_status="401")), "stopped", "key-rejected"),
        (failing(acct=acct(last_status="429")), "stopped", "api-rate-limit"),
        (failing(acct=acct(last_status="502")), "stopped", "api-error"),
        (failing(acct=acct(last_status="unreachable")), "stopped", "api-unreachable"),
        (failing(harness_exit=1, harness_said="boom"), "stopped", "harness-exit"),
        (failing(acct=acct(last_status="200")), "failed", ""),
    ],
)
def test_live_ending_in_data_model_order(o: runner.Observed, kind: str, cause: str) -> None:
    ending = runner.live_ending(o, 900, "opencode")
    assert (ending.kind, ending.cause) == (kind, cause), ending
    assert ending.reason.splitlines() == [ending.reason]


def test_harness_exit_names_what_the_harness_said() -> None:
    o = observed(
        check_ok=False, check_why="check failed: x", harness_exit=1, harness_said="exceeded retry limit"
    )
    assert runner.live_ending(o, 900, "codex").reason == "codex exited 1: exceeded retry limit"


# --- run_live, end to end on loopback -----------------------------------------------------------


@pytest.fixture
def standin() -> Iterator[StandIn]:
    s = StandIn().start()
    s.state.cost_per_response = 0.01
    yield s
    s.stop()


@pytest.fixture
def relay(standin: StandIn) -> Iterator[Relay]:
    r = Relay(standin.url, turn_cap=30, spend_cap_usd=10.0, host="127.0.0.1", port=0).start()
    yield r
    r.stop()


class Harness:
    """Stands in for the harness exec: asks the relay what OpenCode asked, then 'exits'."""

    def __init__(self, relay: Relay, requests: int, key: str) -> None:
        self.relay, self.requests, self.key = relay, requests, key

    def run(self, command: str, limit_s: int) -> CallResult:
        tools = [{"type": "function", "function": {"name": "bash"}}]
        for i in range(self.requests):
            msgs = [{"role": "user", "content": "go"}] + [{"role": "tool", "content": "x"}] * i
            conn = http.client.HTTPConnection("127.0.0.1", self.relay.port, timeout=10)
            body = {
                "model": "deepseek/deepseek-v4-pro-0813",
                "stream": True,
                "tools": tools,
                "messages": msgs,
            }
            conn.request(
                "POST", "/api/v1/chat/completions", json.dumps(body), {"Authorization": f"Bearer {self.key}"}
            )
            conn.getresponse().read()
            conn.close()
        return OK


class Session:
    """A task container as run_live sees it, serving a transcript the real OpenCode wrote."""

    def __init__(
        self, relay: Relay, version: str = "1.19.0", stdout: str | None = None, check_ok: bool = True
    ) -> None:
        self.relay, self.version, self.check_ok = relay, version, check_ok
        self.stdout = (
            stdout if stdout is not None else (FIX / "opencode" / "opencode--pass.stdout.jsonl").read_text()
        )
        self.executor: Executor = self
        self.closed = False
        self.key_seen = ""

    def run(self, command: str, limit_s: int) -> CallResult:  # setup and check
        if command == TASK.check and not self.check_ok:
            return CallResult(1, 5, False, 0, 3, b"", b"no\n")
        return OK

    def close(self) -> None:
        self.closed = True

    def place(self) -> str:
        return "claude-code: placed; codex: placed; opencode: placed"

    def oom_kills(self) -> int | None:
        return 0

    def read(self, argv: Sequence[str]) -> tuple[int, str]:
        if tuple(argv) == hz.specs("1.19.0", "0.162.1")["opencode"].version_argv:
            return 0, self.version + "\n"
        if argv[-1] == hz.STDOUT:
            return 0, self.stdout
        return 0, ""

    def harness_executor(self, exec_env: dict[str, str], key: str) -> Executor:
        self.key_seen = key
        return Harness(self.relay, 3, key)


def live_for(
    relay: Relay, standin: StandIn | None, key: str | None = None, gate: Gate | None = None
) -> runner.Live:
    return runner.Live(
        spec=hz.specs("1.19.0", "0.162.1")["opencode"],
        relay=relay,
        relay_url="http://bench-relay:8417/api/v1",
        model="deepseek/deepseek-v4-pro-0813",
        turn_cap=30,
        run_limit_s=900,
        gate=gate or Gate([key] if key else []),
        key=key,
        upstream="http://127.0.0.1:9",
        standin=standin,
    )


def cell(arm: str, session: Session) -> runner.Cell:
    env = "vanilla" if arm == "vanilla" else "timelike"
    return runner.Cell(arm, runner.Environment(env, "sha256:" + "e" * 64, SHA, lambda: session))


TASK = catalog.by_id("git-inspect")


def test_a_told_live_run_is_traced_from_the_harness_s_own_transcript(
    relay: Relay, standin: StandIn, tmp_path: Path
) -> None:
    s = Session(relay)
    t = runner.run_live(TASK, cell("told", s), CTX, live_for(relay, standin), tmp_path)
    assert trace.validate(t) == [], trace.validate(t)
    assert (t.ending.kind, t.identity.arm, t.identity.harness_name) == ("completed", "told", "opencode")
    assert t.identity.placement.startswith("claude-code: placed") and t.identity.output_streams == "merged"
    assert [c.command for c in t.calls] == ["mkdir -p out && printf 'hello\\n' > out/a.txt", "cat out/a.txt"]
    assert t.identity.models_answered == ("deepseek/deepseek-v4-pro-0813",)
    assert t.spend.recorded and t.spend.usd == pytest.approx(0.03) and "stand-in" in str(t.spend.source)
    assert t.extensions["relay"]["turns"] == 3 and t.extensions["standin"] is True  # type: ignore[index]
    assert (tmp_path / "transcripts" / "git-inspect--opencode--told.stdout.jsonl").exists()
    assert s.key_seen == runner.KEY_PLACEHOLDER and s.closed
    assert standin.state.script == ("git log -n 5 > out/log.txt", "git diff > out/diff.txt")


def test_the_key_goes_to_the_harness_exec_and_the_gate_stops_it_reaching_a_file(
    relay: Relay, standin: StandIn, tmp_path: Path
) -> None:
    leaked = (FIX / "opencode" / "opencode--pass.stdout.jsonl").read_text().replace("hello", KEY)
    s = Session(relay, stdout=leaked)
    with pytest.raises(GateRefused) as e:
        runner.run_live(TASK, cell("not-told", s), CTX, live_for(relay, None, key=KEY), tmp_path)
    assert s.key_seen == KEY and KEY not in str(e.value) and s.closed
    assert not list((tmp_path / "transcripts").glob("*")) if (tmp_path / "transcripts").exists() else True


def test_a_harness_that_is_not_the_pin_refuses_the_run(
    relay: Relay, standin: StandIn, tmp_path: Path
) -> None:
    s = Session(relay, version="1.18.0")
    with pytest.raises(runner.HarnessMismatch, match=r"reports '1\.18\.0', the pin is 1\.19\.0"):
        runner.run_live(TASK, cell("vanilla", s), CTX, live_for(relay, standin), tmp_path)
    assert s.closed


def test_after_the_spend_cap_later_cells_are_recorded_not_started(
    relay: Relay, standin: StandIn, tmp_path: Path
) -> None:
    relay.spent_usd = 10.0
    s = Session(relay)
    t = runner.run_live(TASK, cell("told", s), CTX, live_for(relay, standin), tmp_path)
    assert (t.ending.kind, t.ending.cause) == ("stopped", "spend-cap")
    assert t.ending.reason.startswith("not started") and t.calls == () and not s.closed  # never opened
    assert trace.validate(t) == []


def test_a_rejected_key_stops_every_later_cell(relay: Relay, standin: StandIn, tmp_path: Path) -> None:
    standin.fail_next(401, 10, "invalid key")
    live = live_for(relay, standin)
    s = Session(relay, stdout='{"type": "error", "error": {"data": {"message": "401"}}}\n', check_ok=False)
    first = runner.run_live(TASK, cell("vanilla", s), CTX, live, tmp_path)
    assert (first.ending.kind, first.ending.cause) == ("stopped", "key-rejected"), first.ending
    later = runner.run_live(TASK, cell("not-told", Session(relay)), CTX, live, tmp_path)
    assert (later.ending.cause, later.calls) == ("key-rejected", ())
