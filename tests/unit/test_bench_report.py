"""Units for benchlib.report — vanilla against timelike (contract: bench-cli.md, "Report layout").

Traces are built in memory with `run`; totals always come from `derive_totals`, so a fixture cannot
carry counts its calls disagree with.
"""

from __future__ import annotations

import itertools
import os
from pathlib import Path
from typing import Any

import pytest
from benchlib import report as r
from benchlib import trace as t

SHA = "a" * 40
FAKE = "timelike-fake-agent"
GOALS = {
    "a-task": "Do the first thing.",
    "b-task": "Do the second thing.",
    "c-task": "Do the third thing.",
    "d-task": "Do the fourth thing.",
}
TASKS = {task_id: r.TaskText(goal=goal) for task_id, goal in GOALS.items()}
NOT_BENCHABLE = (
    ("TZ=UTC", "Slim's tzdata already defaults to UTC"),
    ("Credentialed fetch", "A tie on exit code"),
)
REPRODUCE = "make bench"


def run(
    task_id: str,
    environment: str,
    *,
    exits: tuple[int, ...] = (0,),
    hung: tuple[int, ...] = (),
    kind: str = "completed",
    reason: str = "check passed",
    wall_ms: int = 1000,
    tokens: t.Tokens | None = None,
    turns: tuple[int, ...] | None = None,
    **ident: Any,
) -> t.Trace:
    """One valid trace. `exits` is one exit code per call; `hung` lists hung call indexes (0-based)."""
    calls = tuple(
        t.ToolCall(
            seq=i + 1,
            turn=(i + 1) if turns is None else turns[i],
            command=f"step {i + 1}",
            exit_code=code,
            duration_ms=10,
            hung=i in hung,
            stdout_bytes=0,
            stderr_bytes=0,
            passed_bytes=0,
            harness_cut=False,
            stderr_head="",
        )
        for i, code in enumerate(exits)
    )
    fields: dict[str, Any] = {
        "bench_revision": SHA,
        "environment": environment,
        "image_id": f"sha256:{environment[0] * 64}",
        "image_revision": SHA,
        "base_digest": "debian:trixie-slim@sha256:" + "c" * 64,
        "harness_name": FAKE,
        "harness_version": "1",
        "model_id": "none (deterministic fake agent)",
        "invocation": "bash -c",
        "task_id": task_id,
        "task_version": 1,
        "call_limit_s": 30,
        "run_limit_s": 300,
        "reproduce": f"make bench TASKS={task_id}",
    }
    fields.update(ident)
    if fields["image_revision"] != fields["bench_revision"]:
        fields["image_revision"] = fields["bench_revision"]
    trace = t.Trace(
        identity=t.Identity(**fields),
        calls=calls,
        totals=t.derive_totals(calls, wall_ms),
        ending=t.Ending(kind=kind, reason=reason),
        tokens=tokens or t.Tokens(recorded=False, reason="the fake agent uses no model"),
    )
    assert t.validate(trace) == []
    return trace


def four() -> list[t.Trace]:
    """RB4's four shapes under neutral ids: one loss, one tie, one win, one missing pair."""
    return [
        # a: timelike loses on ending (completed vs failed).
        run("a-task", "vanilla", exits=(1, 0, 0), wall_ms=1900),
        run("a-task", "timelike", kind="failed", reason="check failed: TODO in tree", wall_ms=400),
        # b: tie.
        run("b-task", "vanilla", exits=(0, 0)),
        run("b-task", "timelike", exits=(0, 0)),
        # c: timelike wins on turns.
        run("c-task", "vanilla", exits=(124, 0), hung=(0,), wall_ms=30100),
        run("c-task", "timelike", wall_ms=200),
        # d: only vanilla ran.
        run("d-task", "vanilla"),
    ]


def render(traces: list[t.Trace], **over: Any) -> list[str]:
    kw: dict[str, Any] = {"tasks": TASKS, "not_benchable": NOT_BENCHABLE, "reproduce": REPRODUCE}
    kw.update(over)
    return r.render(traces, **kw)


def section(lines: list[str], title: str) -> list[str]:
    """The lines of the `## <title> (N)` section, heading excluded, up to the next `## ` heading."""
    start = next(i for i, line in enumerate(lines) if line.startswith(f"## {title}"))
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return lines[start + 1 : end]


# --- verdict ------------------------------------------------------------------------------------

RANKED = ("completed", "escalated", "failed", "hung")


@pytest.mark.parametrize(("good_kind", "bad_kind"), list(itertools.combinations(RANKED, 2)))
def test_verdict_ending_rank_decides_first(good_kind: str, bad_kind: str) -> None:
    # The better ending takes more turns and more failures: the ending still decides.
    good = run("x", "timelike", exits=(1, 1, 1), kind=good_kind)
    bad = run("x", "vanilla", kind=bad_kind)
    assert r.verdict(bad, good) == "wins"
    assert r.verdict(good, bad) == "loses"


def test_verdict_turns_break_an_ending_tie() -> None:
    assert r.verdict(run("x", "vanilla", exits=(0, 0)), run("x", "timelike", exits=(1,))) == "wins"
    assert r.verdict(run("x", "vanilla", exits=(1,)), run("x", "timelike", exits=(0, 0))) == "loses"


def test_verdict_failures_break_a_turns_tie() -> None:
    # Same turns (both calls in one turn), same ending; vanilla has a hang, timelike a non-zero exit.
    vanilla = run("x", "vanilla", exits=(124, 1), hung=(0,), turns=(1, 1))
    timelike = run("x", "timelike", exits=(1, 0), turns=(1, 1))
    assert vanilla.totals.turns == timelike.totals.turns == 1
    assert r.verdict(vanilla, timelike) == "wins"
    assert r.verdict(timelike, vanilla) == "loses"


def test_verdict_hangs_count_as_failures() -> None:
    hanging = run("x", "vanilla", exits=(0,), hung=(0,))  # a hang with exit 0 still counts once
    assert r.verdict(hanging, run("x", "timelike")) == "wins"


def test_verdict_true_tie() -> None:
    assert r.verdict(run("x", "vanilla", exits=(1, 0)), run("x", "timelike", exits=(0, 1))) == "tie"


def test_verdict_ignores_wall_clock() -> None:
    assert r.verdict(run("x", "vanilla", wall_ms=1), run("x", "timelike", wall_ms=999_999)) == "tie"
    assert r.verdict(run("x", "vanilla", wall_ms=999_999), run("x", "timelike", wall_ms=1)) == "tie"


def test_verdict_missing_side_is_incomplete() -> None:
    assert r.verdict(None, run("x", "timelike")) == "incomplete"
    assert r.verdict(run("x", "vanilla"), None) == "incomplete"
    assert r.verdict(None, None) == "incomplete"


# --- pair ---------------------------------------------------------------------------------------


def test_pair_groups_by_task_and_environment() -> None:
    pairs = r.pair(four())
    assert sorted(pairs) == ["a-task", "b-task", "c-task", "d-task"]
    assert sorted(pairs["a-task"]) == ["timelike", "vanilla"]
    assert list(pairs["d-task"]) == ["vanilla"]


def test_pair_refuses_a_duplicate_slot() -> None:
    with pytest.raises(ValueError, match="two vanilla traces for task 'x'"):
        r.pair([run("x", "vanilla"), run("x", "vanilla")])


# --- render: header -----------------------------------------------------------------------------


def test_first_line_fake_agent() -> None:
    lines = render(four())
    # The operator's text, verbatim (send …-080659, F001).
    assert lines[0] == (
        "FAKE-AGENT BENCH PIPELINE DEMO RUN -- This is not a test of timelike, rather a test of the bench "
        "test itself (its presentation and usefulness to the human user). The agent's policy was written "
        "by timelike's own builders."
    )


def test_first_line_fake_when_any_trace_is_fake() -> None:
    traces = [run("x", "vanilla", harness_name="claude-code"), run("x", "timelike")]
    assert render(traces)[0] == r.FAKE_LINE


def test_first_line_live() -> None:
    live = {"harness_name": "claude-code", "harness_version": "2.1.0", "model_id": "claude-x"}
    traces = [run("x", "vanilla", **live), run("x", "timelike", **live)]
    assert render(traces)[0] == (
        "LIVE RUN — claude-code 2.1.0, model claude-x; a single repetition, no spread (slice 2)"
    )


def test_first_line_live_mixed_harness_is_named_not_picked() -> None:
    traces = [
        run("x", "vanilla", harness_name="h", harness_version="1", model_id="m1"),
        run("x", "timelike", harness_name="h", harness_version="2", model_id="m2"),
    ]
    assert render(traces)[0] == (
        "LIVE RUN — mixed (h 1, h 2), model mixed (m1, m2); a single repetition, no spread (slice 2)"
    )


def test_maintainer_and_reproduce_line() -> None:
    lines = render(four(), reproduce="make bench TASKS=a-task")
    assert lines[1] == "Measured by the project's own maintainer. Reproduce: make bench TASKS=a-task"


def test_identity_line() -> None:
    assert render(four())[2] == (
        f"Timelike {SHA} · vanilla sha256:{'v' * 64} (base debian:trixie-slim@sha256:{'c' * 64}; "
        "same base, user and git, without timelike's layers) · harness timelike-fake-agent 1 "
        "· model none (deterministic fake agent) · invocation bash -c, no TTY"
    )


def test_identity_line_reports_mixed_stamps() -> None:
    other = "b" * 40
    traces = [
        run("x", "vanilla"),
        run("x", "timelike", bench_revision=other, harness_version="2", model_id="m"),
    ]
    line = render(traces)[2]
    assert f"Timelike mixed ({SHA}, {other})" in line
    assert "harness mixed (timelike-fake-agent 1, timelike-fake-agent 2)" in line
    assert "model mixed (m, none (deterministic fake agent))" in line


def test_no_traces_is_honest_and_complete() -> None:
    lines = render([])
    assert lines[0] == "NO TRACES — nothing was measured"
    assert "Timelike none · vanilla none (base none;" in lines[2]
    for title in ("Timelike loses", "Ties", "Timelike wins"):
        assert f"## {title} (0)" in lines
    assert "## Not benchable on this path" in lines
    assert lines[-2:] == ["## Appendix: tokens", "no traces"]


# --- render: sections ---------------------------------------------------------------------------


def test_sections_in_order_with_counts() -> None:
    headings = [line for line in render(four()) if line.startswith("## ")]
    assert headings == [
        "## Timelike loses (2)",
        "## Ties (1)",
        "## Timelike wins (1)",
        "## Not benchable on this path",
        "## Appendix: tokens",
    ]


def test_sections_present_when_empty() -> None:
    headings = [
        line for line in render([run("b", "vanilla"), run("b", "timelike")]) if line.startswith("## ")
    ]
    assert headings[:3] == ["## Timelike loses (0)", "## Ties (1)", "## Timelike wins (0)"]


def test_incomplete_pair_listed_under_loses() -> None:
    loses = section(render(four()), "Timelike loses")
    assert "### d-task — Do the fourth thing. (incomplete: no timelike trace)" in loses
    assert "### a-task — Do the first thing." in loses
    only_timelike = section(render([run("z", "timelike")]), "Timelike loses")
    assert only_timelike[0] == "### z — (no goal given) (incomplete: no vanilla trace)"
    assert only_timelike[1].startswith("Verdict: incomplete — there is no vanilla trace")
    assert only_timelike[3] == "ending                            no trace   completed"
    assert "What happened in vanilla: no trace was written for this arm." in only_timelike


def test_tasks_sorted_by_id_within_a_section() -> None:
    traces = [
        tr
        for task_id in ("m", "c", "q")
        for tr in (run(task_id, "vanilla"), run(task_id, "timelike", kind="failed", reason="r"))
    ]
    blocks = [line for line in section(render(traces), "Timelike loses") if line.startswith("### ")]
    assert [b.split()[1] for b in blocks] == ["c", "m", "q"]


def test_metric_table_is_aligned() -> None:
    loses = section(render(four()), "Timelike loses")
    start = loses.index("### a-task — Do the first thing.")
    assert loses[start + 1].startswith("Verdict: Timelike loses — vanilla completed; timelike failed: ")
    assert loses[start + 2 : start + 9] == [
        "metric                            vanilla     timelike",
        "ending                            completed   failed",
        "turns                             3           1",
        "failed commands (hung included)   1           0",
        "hangs                             0           0",
        "tool calls                        3           1",
        "wall-clock                        1.9 s       0.4 s",
    ]


def test_hangs_and_wall_clock_rendered() -> None:
    wins = section(render(four()), "Timelike wins")
    assert "hangs                             1           0" in wins
    assert "failed commands (hung included)   1           0" in wins  # the hung call is also non-zero
    assert "wall-clock                        30.1 s      0.2 s" in wins


def test_non_completed_ending_carries_its_reason() -> None:
    traces = [run("x", "vanilla", kind="hung", reason="run limit 300 s"), run("x", "timelike")]
    wins = section(render(traces), "Timelike wins")
    assert any(line.startswith("ending ") and line.split()[1:] == ["hung", "completed"] for line in wins)
    assert "  Ended: hung — run limit 300 s." in wins
    assert wins[1].startswith("Verdict: Timelike wins — timelike completed; vanilla hung: run limit 300 s.")


def test_no_trailing_whitespace() -> None:
    assert all(line == line.rstrip() for line in render(four()))


def test_not_benchable_bullets() -> None:
    assert section(render(four()), "Not benchable on this path") == [
        "- TZ=UTC: Slim's tzdata already defaults to UTC",
        "- Credentialed fetch: A tie on exit code",
        "",
    ]
    assert section(render(four(), not_benchable=()), "Not benchable on this path") == [""]


# --- render: tokens -----------------------------------------------------------------------------


def test_the_word_token_appears_only_from_the_appendix() -> None:
    traces = [
        run("x", "vanilla", tokens=t.Tokens(recorded=True, input=1200, output=340)),
        run("x", "timelike"),
    ]
    for lines in (render(four()), render(traces), render([])):
        appendix = lines.index(r.APPENDIX_HEADING)
        assert not any("token" in line.lower() for line in lines[:appendix])


def test_tokens_appendix_contents() -> None:
    traces = [
        run("x", "timelike"),
        run("x", "vanilla", tokens=t.Tokens(recorded=True, input=1200, output=340)),
    ]
    lines = render(traces)
    assert lines[lines.index(r.APPENDIX_HEADING) + 1 :] == [
        "- x · vanilla: input 1200, output 340",
        "- x · timelike: not recorded — the fake agent uses no model",
    ]


def test_appendix_is_last_and_covers_every_trace() -> None:
    lines = render(four())
    tail = lines[lines.index(r.APPENDIX_HEADING) + 1 :]
    assert len(tail) == len(four())
    assert tail[0] == "- a-task · vanilla: not recorded — the fake agent uses no model"


# --- files --------------------------------------------------------------------------------------


def test_build_report_from_files_equals_render_from_memory(tmp_path: Path) -> None:
    traces = four()
    for i, trace in enumerate(traces):
        t.write_trace(trace, tmp_path / "traces" / f"{i:02}-{trace.identity.task_id}.json")
    kw: dict[str, Any] = {"tasks": TASKS, "not_benchable": NOT_BENCHABLE, "reproduce": REPRODUCE}
    lines = r.build_report(tmp_path, **kw)
    assert lines == r.render(traces, **kw)
    assert (tmp_path / "report.txt").read_text(encoding="utf-8") == "\n".join(lines) + "\n"


def test_build_report_order_independent(tmp_path: Path) -> None:
    traces = four()
    for i, trace in enumerate(reversed(traces)):
        t.write_trace(trace, tmp_path / "traces" / f"{i:02}.json")
    kw: dict[str, Any] = {"tasks": TASKS, "not_benchable": NOT_BENCHABLE, "reproduce": REPRODUCE}
    assert r.build_report(tmp_path, **kw) == r.render(traces, **kw)


def test_write_report_replaces_and_leaves_no_temp(tmp_path: Path) -> None:
    out = tmp_path / "run"
    assert r.write_report(out, ["old"]) == out / "report.txt"
    r.write_report(out, ["new", "lines"])
    assert (out / "report.txt").read_text(encoding="utf-8") == "new\nlines\n"
    assert sorted(os.listdir(out)) == ["report.txt"]


def test_write_report_failure_leaves_no_temp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(src: str, dst: Path) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(r.os, "replace", boom)
    with pytest.raises(OSError, match="disk full"):
        r.write_report(tmp_path, ["x"])
    assert os.listdir(tmp_path) == []


def test_fake_agent_name_matches_the_fake_agent() -> None:
    fakeagent = pytest.importorskip("benchlib.fakeagent")
    assert r.FAKE_AGENT_NAME == fakeagent.FAKE_AGENT_NAME


# --- the explanation block (send …-080659, F002) ------------------------------------------------


def explained(traces: list[t.Trace], text: r.TaskText, title: str) -> list[str]:
    return section(render(traces, tasks={traces[0].identity.task_id: text}), title)


def test_tests_line_names_the_capability_and_what_differs() -> None:
    text = r.TaskText("Commit it.", "Hooks off (the cost)", "Timelike skips hooks. In vanilla they run.")
    block = explained([run("h", "vanilla"), run("h", "timelike")], text, "Ties")
    assert block[1] == "Tests: Hooks off (the cost). Timelike skips hooks. In vanilla they run."


def test_no_tests_line_without_texts() -> None:
    block = section(render([run("h", "vanilla"), run("h", "timelike")]), "Ties")
    assert block[1].startswith("Verdict: Tie")


def test_each_call_is_told_with_its_exit_its_message_or_its_hang() -> None:
    vanilla = run("h", "vanilla", exits=(1, 124, 0, 2), hung=(1,))
    calls = list(vanilla.calls)
    calls[0] = t.ToolCall(
        1, 1, "git commit -m m", 1, 5, False, 0, 30, 0, False, "\npre-commit: TODO found\nmore"
    )
    calls[3] = t.ToolCall(4, 4, "quiet", 2, 5, False, 0, 0, 0, False, "")
    vanilla = t.Trace(
        vanilla.identity, tuple(calls), t.derive_totals(calls, 1000), vanilla.ending, vanilla.tokens
    )
    block = explained([vanilla, run("h", "timelike")], r.TaskText("g"), "Timelike wins")
    arm = block[block.index("What happened in vanilla:") :]
    assert arm[1:6] == [
        "  1. `git commit -m m` → exit 1: pre-commit: TODO found",
        "  2. `step 2` → hung: killed at the 30 s limit",
        "  3. `step 3` → exit 0",
        "  4. `quiet` → exit 2 (no message)",
        "  Ended: completed — the check confirmed the goal.",
    ]


def test_long_stderr_is_cut() -> None:
    call = t.ToolCall(1, 1, "c", 1, 5, False, 0, 400, 0, False, "x" * 400)
    trace = run("h", "vanilla")
    trace = t.Trace(trace.identity, (call,), t.derive_totals([call], 10), trace.ending, trace.tokens)
    block = explained([trace, run("h", "timelike", exits=(0, 0))], r.TaskText("g"), "Timelike loses")
    line = next(x for x in block if x.startswith("  1. `c`"))
    assert line.endswith("…") and len(line) < 200


def test_a_note_prints_only_when_the_arm_ended_that_way() -> None:
    text = r.TaskText("g", notes={"timelike:failed": "the hook was skipped", "vanilla:failed": "never shown"})
    traces = [run("h", "vanilla"), run("h", "timelike", kind="failed", reason="check failed: TODO")]
    block = explained(traces, text, "Timelike loses")
    assert "  Why: the hook was skipped." in block
    assert not any("never shown" in line for line in block)
    assert "  Ended: failed — check failed: TODO." in block


def test_verdict_words_for_turns_failures_and_tie() -> None:
    by_turns = explained(
        [run("h", "vanilla", exits=(1, 0)), run("h", "timelike")], r.TaskText("g"), "Timelike wins"
    )
    assert by_turns[1] == "Verdict: Timelike wins — both completed; timelike took 1 turn to vanilla's 2."
    by_fail = explained(
        [run("h", "vanilla", exits=(0, 0)), run("h", "timelike", exits=(1, 0), turns=(1, 2))],
        r.TaskText("g"),
        "Timelike loses",
    )
    assert by_fail[1] == (
        "Verdict: Timelike loses — both completed in 2 turns; "
        "timelike had 1 failed or hung commands to vanilla's 0."
    )
    tie = explained([run("h", "vanilla"), run("h", "timelike")], r.TaskText("g"), "Ties")
    assert tie[1] == "Verdict: Tie — both completed, in 1 turn, with 0 failed commands and 0 hangs."


def test_an_arm_with_no_calls_says_so() -> None:
    traces = [run("h", "vanilla"), run("h", "timelike", exits=(), kind="failed", reason="setup failed: x")]
    block = explained(traces, r.TaskText("g"), "Timelike loses")
    arm = block[block.index("What happened in timelike:") :]
    assert arm[1:3] == ["  (no tool calls)", "  Ended: failed — setup failed: x."]
