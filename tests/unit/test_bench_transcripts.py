"""Units for benchlib.transcripts (feature 002 slice 1, FR-44, FR-46).

The parsers, on transcripts the pinned harnesses wrote themselves (tests/fixtures/transcripts; how they were
made is in its README), and on input that is truncated or foreign, which must be refused visibly and never
read as zero calls.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from benchlib import transcripts as tr
from benchlib.categories import categorize

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "transcripts"


def oc(scenario: str) -> str:
    return (FIX / "opencode" / f"opencode--{scenario}.stdout.jsonl").read_text()


def cx(scenario: str) -> tuple[str, str]:
    base = FIX / "codex" / f"codex--{scenario}"
    return Path(f"{base}.rollout.jsonl").read_text(), Path(f"{base}.stdout.jsonl").read_text()


def script(harness: str, scenario: str) -> list[str]:
    meta = json.loads((FIX / harness / f"{harness}--{scenario}.meta.json").read_text())
    return list(meta["script"])


@pytest.mark.parametrize("harness", ["opencode", "codex"])
def test_the_pass_run_reads_as_two_successful_commands(harness: str) -> None:
    parsed = tr.parse_opencode(oc("pass")) if harness == "opencode" else tr.parse_codex(*cx("pass"))
    assert [c.command for c in parsed.calls] == script(harness, "pass")
    assert [c.exit_code for c in parsed.calls] == [0, 0]
    assert [c.turn for c in parsed.calls] == [1, 2]
    assert parsed.calls[1].output == "hello\n"
    assert parsed.final_text == "done"
    assert parsed.tokens_in and parsed.tokens_out
    assert parsed.errors == ()


FAILURES_EXITS = {
    "opencode": [127, 1, 1, 124, 128, 1, tr.NO_EXIT, 2],
    "codex": [127, 1, 1, 124, 128, 1, 137, 2],
}
FAILURES_CATEGORIES = {
    "opencode": ["command-not-found", "module-not-found", "module-not-found", "timeout", "network-denial",
                 "network-denial", "timeout", "other"],
    "codex": ["command-not-found", "module-not-found", "module-not-found", "timeout", "network-denial",
              "network-denial", "other", "other"],
}  # fmt: skip


@pytest.mark.parametrize("harness", ["opencode", "codex"])
def test_the_failures_run_reads_each_call_its_exit_and_its_category(harness: str) -> None:
    parsed = tr.parse_opencode(oc("failures")) if harness == "opencode" else tr.parse_codex(*cx("failures"))
    assert [c.command for c in parsed.calls] == script(harness, "failures")
    assert [c.exit_code for c in parsed.calls] == FAILURES_EXITS[harness]
    cats = [categorize(c.exit_code, c.hung, c.output) for c in parsed.calls]
    assert cats == FAILURES_CATEGORIES[harness]
    assert [c.turn for c in parsed.calls] == list(range(1, 9))


def test_opencode_s_own_timeout_is_a_hung_call_with_no_exit() -> None:
    killed = tr.parse_opencode(oc("failures")).calls[6]
    assert killed.hung and killed.exit_code == tr.NO_EXIT and killed.duration_ms >= 120_000


@pytest.mark.parametrize("harness", ["opencode", "codex"])
def test_the_turn_cap_run_shows_the_harness_s_error(harness: str) -> None:
    parsed = tr.parse_opencode(oc("turn-cap")) if harness == "opencode" else tr.parse_codex(*cx("turn-cap"))
    assert [c.command for c in parsed.calls] == ["echo one"]
    assert any("timelike-bench: turn-cap reached" in e for e in parsed.errors)


def test_codex_s_429_is_an_error_with_no_call() -> None:
    parsed = tr.parse_codex(*cx("rate-limit"))
    assert parsed.calls == ()
    assert parsed.errors == ("exceeded retry limit, last status: 429 Too Many Requests",)


def test_codex_counts_turns_from_its_response_records() -> None:
    parsed = tr.parse_codex(*cx("failures"))
    assert parsed.turns == 9  # eight calls, one response each, and the final answer


# --- refused, never zero calls --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "why"),
    [
        ("", "is empty"),
        ("{not json\n", "line 1 is not JSON"),
        ('{"type": "step_start"}\n[1, 2]\n', "line 2 is not a JSON object"),
        ('{"type": "tool_use", "part": {"tool": "bash", "state": {}}}\n', "before any step_start"),
        ('{"type": "unrelated"}\n', "no model response"),
    ],
)
def test_unreadable_opencode_output_is_refused(text: str, why: str) -> None:
    with pytest.raises(tr.TranscriptUnreadable, match=why):
        tr.parse_opencode(text)


def test_a_truncated_opencode_transcript_is_refused_where_it_breaks() -> None:
    text = oc("failures")
    cut = text[: len(text) // 2]
    with pytest.raises(tr.TranscriptUnreadable, match=r"line \d+ is not JSON"):
        tr.parse_opencode(cut)


def test_codex_s_stdout_alone_is_not_a_rollout() -> None:
    _, stdout = cx("pass")
    with pytest.raises(tr.TranscriptUnreadable, match="no model response, no call and no error"):
        tr.parse_codex(stdout.replace('"type"', '"kind"'), "")


def test_a_codex_call_that_never_completed_is_recorded_with_no_exit() -> None:
    rollout, stdout = cx("pass")
    lines = [line for line in rollout.splitlines() if '"CommandExecution"' not in line]
    parsed = tr.parse_codex("\n".join(lines), stdout)
    assert [c.exit_code for c in parsed.calls] == [tr.NO_EXIT, tr.NO_EXIT]
