"""Units for benchlib.report, schema 2 (contract: bench-cli.md § Slice 1, "Report layout, schema 2").

Traces are built in memory with `run`; totals always come from `derive_totals`, so a fixture cannot carry
counts its calls disagree with. SC-4 (adoption per arm), SC-5 (results per harness), SC-6 (revision 8's
ranking and the sentence) and SC-7 (categories) each have tests here; the end-to-end versions run in the
Docker lane.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
from benchlib import fakeagent
from benchlib import report as r
from benchlib import trace as t
from benchlib.categories import categorize
from benchlib.keyfile import Gate, GateRefused

SHA = "a" * 40
FAKE = "timelike-fake-agent"
GOALS = {"a-task": "Do the first thing.", "b-task": "Do the second thing.", "c-task": "Do the third thing."}
TASKS = {task_id: r.TaskText(goal=goal) for task_id, goal in GOALS.items()}
NOT_BENCHABLE = (("TZ=UTC", "Slim's tzdata already defaults to UTC"),)
REPRODUCE = "make bench"


def run(
    task_id: str,
    arm: str,
    *,
    exits: tuple[int, ...] = (0,),
    hung: tuple[int, ...] = (),
    kind: str = "completed",
    reason: str = "check passed",
    cause: str = "",
    wall_ms: int = 1000,
    harness: str = FAKE,
    turns: tuple[int, ...] | None = None,
    commands: tuple[str, ...] | None = None,
    tools: tuple[tuple[str, ...], ...] | None = None,
    through: tuple[tuple[str, ...], ...] | None = None,
    stderr: tuple[str, ...] | None = None,
    spend: t.Spend | None = None,
    tokens: t.Tokens | None = None,
    standin: bool = False,
) -> t.Trace:
    """One valid trace. `exits` is one exit code per call; `hung` lists hung call indexes (0-based)."""
    calls = tuple(
        t.ToolCall(
            seq=i + 1,
            turn=(i + 1) if turns is None else turns[i],
            command=commands[i] if commands else f"step {i + 1}",
            exit_code=code,
            duration_ms=10,
            hung=i in hung,
            stdout_bytes=0,
            stderr_bytes=len(stderr[i]) if stderr else 0,
            passed_bytes=len(stderr[i]) if stderr else 0,
            harness_cut=False,
            stderr_head=stderr[i] if stderr else "",
            category=categorize(code, i in hung, stderr[i] if stderr else ""),
            timelike_tools=tools[i] if tools else (),
            through_timelike=through[i] if through else (),
        )
        for i, code in enumerate(exits)
    )
    environment = "vanilla" if arm == "vanilla" else "timelike"
    live = harness != FAKE
    ident = t.Identity(
        bench_revision=SHA,
        environment=environment,
        arm=arm,
        image_id=f"sha256:{environment[0] * 64}",
        image_revision=SHA,
        base_digest="debian:trixie-slim@sha256:" + "c" * 64,
        harness_name=harness,
        harness_version="1.19.0" if live else "1",
        harness_reported_version="1.19.0" if live else "1",
        model_id="deepseek/deepseek-v4-pro-0813" if live else "none (deterministic fake agent)",
        models_answered=("deepseek/deepseek-v4-pro-0813",) if live else (),
        invocation=f"{harness} bash tool" if live else "bash -c",
        output_streams="merged" if live else "separate",
        placement="codex: placed; opencode: placed" if arm == "told" else "",
        task_id=task_id,
        task_version=1,
        call_limit_s=120,
        run_limit_s=900 if live else 300,
        turn_cap=30 if live else 0,
        timelike_tools=("run", "view"),
        reproduce=f"make bench TASKS={task_id}",
    )
    trace = t.Trace(
        identity=ident,
        calls=calls,
        totals=t.derive_totals(calls, wall_ms),
        ending=t.Ending(kind=kind, reason=reason, cause=cause),
        tokens=tokens or t.Tokens(recorded=False, reason="the fake agent uses no model"),
        spend=spend or t.NO_SPEND,
        extensions={"standin": True} if standin else {},
    )
    assert t.validate(trace) == [], t.validate(trace)
    return trace


def render(traces: list[t.Trace], **over: Any) -> list[str]:
    kw: dict[str, Any] = {"tasks": TASKS, "not_benchable": NOT_BENCHABLE, "reproduce": REPRODUCE}
    kw.update(over)
    return r.render(traces, **kw)


def section(lines: list[str], title: str, harness: str = "") -> list[str]:
    """The lines of `## <title> (N)` within the harness section named `harness` (the first, by default)."""
    start = 0
    if harness:
        start = next(i for i, line in enumerate(lines) if line.startswith(f"# Harness: {harness} "))
    head = next(i for i in range(start, len(lines)) if lines[i].startswith(f"## {title}"))
    end = next((i for i in range(head + 1, len(lines)) if lines[i].startswith(("## ", "# "))), len(lines))
    return lines[head + 1 : end]


def three(task_id: str, **per_arm: dict[str, Any]) -> list[t.Trace]:
    return [
        run(task_id, arm, **per_arm.get(arm.replace("-", "_"), {})) for arm in ("vanilla", "not-told", "told")
    ]


def cols(line: str) -> list[str]:
    return re.split(r"\s{3,}", line)


# --- the verdict (SC-6, revision 8) ---------------------------------------------------------------

RANKED = ("completed", "escalated", "failed", "hung")


@pytest.mark.parametrize(("good", "bad"), [(a, b) for i, a in enumerate(RANKED) for b in RANKED[i + 1 :]])
def test_ending_rank_decides_first(good: str, bad: str) -> None:
    assert r.verdict(run("x", "vanilla", kind=good), run("x", "told", kind=bad, exits=())) == "loses"
    assert r.verdict(run("x", "vanilla", kind=bad, exits=()), run("x", "told", kind=good)) == "wins"


def _same_turns(exits: tuple[int, ...], hung: tuple[int, ...] = ()) -> dict[str, Any]:
    return {"exits": exits, "hung": hung, "turns": tuple(1 for _ in exits)}


@pytest.mark.parametrize(
    ("column", "worse", "better"),
    [
        ("ending", {"kind": "failed", "reason": "check failed: x"}, {}),
        ("turns", {"exits": (0, 0)}, {"exits": (0,)}),
        ("hangs", _same_turns((124,), (0,)), _same_turns((1,))),
        ("failed commands", _same_turns((1, 1)), _same_turns((1, 0))),
    ],
)
def test_rows_differing_in_one_column_are_decided_by_that_column(
    column: str, worse: dict[str, Any], better: dict[str, Any]
) -> None:
    assert r.verdict(run("x", "vanilla", **worse), run("x", "not-told", **better)) == "wins", column
    assert r.verdict(run("x", "vanilla", **better), run("x", "not-told", **worse)) == "loses", column


def test_hangs_are_compared_before_failed_commands_and_counted_once() -> None:
    """Slice 0's summed tiebreak said timelike loses here (2 against 3); revision 8 compares hangs first."""
    vanilla = run("x", "vanilla", **_same_turns((124, 0, 0), (0,)))
    timelike = run("x", "told", **_same_turns((1, 1, 1)))
    assert (vanilla.totals.hangs, vanilla.totals.nonzero_exits) == (1, 1)
    assert (timelike.totals.hangs, timelike.totals.nonzero_exits) == (0, 3)
    assert r.verdict(vanilla, timelike) == "wins"


def test_wall_clock_and_tool_calls_never_decide() -> None:
    assert r.verdict(run("x", "vanilla", wall_ms=1), run("x", "told", wall_ms=999_999)) == "tie"


def test_a_stopped_side_is_not_compared_and_a_missing_one_is_incomplete() -> None:
    stopped = run("x", "told", exits=(), kind="stopped", reason="429", cause="api-rate-limit")
    assert r.verdict(run("x", "vanilla"), stopped) == "not-compared"
    assert r.verdict(None, run("x", "told")) == "incomplete"


def test_the_verdict_sentence_quotes_only_counts_in_the_table() -> None:
    traces = [
        run("a-task", "vanilla", **_same_turns((124, 1), (0,))),
        run("a-task", "not-told", **_same_turns((1, 1, 1))),
    ]
    block = section(render(traces), "Timelike wins")
    sentence = next(line for line in block if line.startswith("Not told vs vanilla: "))
    assert sentence.endswith("timelike, not told had 0 hangs to vanilla's 1.")
    assert "failed or hung" not in sentence
    rows = {cols(line)[0]: cols(line)[1:] for line in block if cols(line)[0] in ("turns", "hangs")}
    assert rows == {"turns": ["1", "1"], "hangs": ["1", "0"]}


def test_verdict_words_for_turns_failed_commands_and_tie() -> None:
    by_turns = section(
        render([run("a-task", "vanilla", exits=(1, 0)), run("a-task", "told")]), "Timelike wins"
    )
    assert (
        "Told vs vanilla: Verdict: Timelike wins — both completed; timelike, told took 1 turn to vanilla's 2."
        in by_turns
    )
    by_fail = section(
        render([run("a-task", "vanilla", exits=(0, 0)), run("a-task", "told", exits=(1, 0), turns=(1, 2))]),
        "Timelike loses",
    )
    assert (
        "Told vs vanilla: Verdict: Timelike loses — both completed in 2 turns with 0 hangs; "
        "timelike, told had 1 failed command to vanilla's 0." in by_fail
    )
    tie = section(render([run("a-task", "vanilla"), run("a-task", "told")]), "Ties")
    assert (
        "Told vs vanilla: Verdict: Tie — both completed, in 1 turn, with 0 hangs and 0 failed commands."
        in tie
    )


# --- pairing, first lines, harness sections (SC-5) ------------------------------------------------


def test_pair_groups_by_harness_task_and_arm_and_refuses_a_duplicate() -> None:
    traces = [*three("a-task"), run("a-task", "vanilla", harness="opencode")]
    paired = r.pair(traces)
    assert list(paired) == ["fake", "opencode"]
    assert list(paired["fake"]["a-task"]) == ["vanilla", "not-told", "told"]
    with pytest.raises(ValueError, match="two fake told traces"):
        r.pair([run("a-task", "told"), run("a-task", "told")])


def test_first_lines() -> None:
    assert render([])[0] == r.NO_TRACES_LINE
    assert render(three("a-task"))[0] == r.FAKE_LINE
    assert render([run("a-task", "vanilla", harness="codex", standin=True)])[0] == r.STANDIN_LINE
    assert render([run("a-task", "vanilla", harness="codex")])[0] == r.LIVE_LINE
    assert render(three("a-task"))[1] == f"Measured by the project's own maintainer. Reproduce: {REPRODUCE}"


def test_the_identity_line_names_the_arms_and_the_model() -> None:
    line = render(three("a-task"))[2]
    assert line.endswith(
        "· model none (deterministic fake agent) · arms: vanilla, timelike, not told, timelike, told"
    )


def test_one_section_per_harness_with_its_own_verdicts() -> None:
    oc = [
        run("a-task", "vanilla", harness="opencode"),
        run("a-task", "told", harness="opencode", exits=(1, 0)),
    ]
    cx = [run("a-task", "vanilla", harness="codex", exits=(1, 0)), run("a-task", "told", harness="codex")]
    lines = render(oc + cx)
    heads = [line for line in lines if line.startswith("# Harness: ")]
    assert [h.split()[2] for h in heads] == ["opencode", "codex"]
    assert heads[0] == (
        "# Harness: opencode 1.19.0 (reported 1.19.0) · answered by deepseek/deepseek-v4-pro-0813"
        " · invocation opencode bash tool"
    )
    assert any(line.startswith("### a-task") for line in section(lines, "Timelike loses", "opencode"))
    assert any(line.startswith("### a-task") for line in section(lines, "Timelike wins", "codex"))


# --- adoption (SC-4) and categories (SC-7) ---------------------------------------------------------


def test_the_adoption_table_counts_timelike_tool_calls_per_arm() -> None:
    told_calls = {"commands": ("run a", "view b", "run c"), "tools": (("run",), ("view",), ("run",))}
    traces = [
        run("a-task", "vanilla", exits=(0, 0)),
        run("a-task", "not-told", exits=(0, 0), tools=((), ()), through=(("shim:pip",), ())),
        run("a-task", "told", exits=(0, 0, 0), **told_calls),  # type: ignore[arg-type]
    ]
    lines = render(traces)
    start = lines.index("## Adoption: timelike tool calls per arm")
    table = lines[start + 1 : start + 5]
    assert cols(table[0])[0] == "arm"
    assert cols(table[1]) == ["vanilla", "1", "2", "—", "—", "—"]
    assert cols(table[2]) == ["timelike, not told", "1", "2", "0", "none", "1"]
    assert cols(table[3]) == ["timelike, told", "1", "3", "3", "run 2, view 1", "0"]
    assert lines[start + 5] == r.COUNTS_NOTE
    assert lines[start + 6] == r.FAKE_CANNOT_READ


def test_a_live_section_has_no_fake_agent_note() -> None:
    assert r.FAKE_CANNOT_READ not in render([run("a-task", "vanilla", harness="opencode")])


def test_the_categories_table_has_every_category_per_arm() -> None:
    traces = [
        run("a-task", "vanilla", exits=(127, 1), stderr=("bash: x: command not found", "Connection refused")),
        run("a-task", "told", exits=(124,), hung=(0,), stderr=("",)),
    ]
    lines = render(traces)
    start = next(i for i, line in enumerate(lines) if line.startswith("## Failure categories per arm"))
    rows = {cols(line)[0]: cols(line)[1:] for line in lines[start + 2 : start + 8]}
    assert list(rows) == [
        "timeout",
        "memory kill",
        "command not found",
        "module not found",
        "network denial (from the task container)",
        "other",
    ]
    assert rows["command not found"] == ["1", "0"]
    assert rows["network denial (from the task container)"] == ["1", "0"]
    assert rows["timeout"] == ["0", "1"] and rows["other"] == ["0", "0"]


# --- sections, blocks, the not-compared rows -------------------------------------------------------


def test_sections_in_order_and_a_task_goes_under_its_worse_verdict() -> None:
    traces = [
        *three("a-task", not_told={"exits": (0, 0)}, told={"exits": ()}),  # loses (not told), wins (told)
        *three("b-task"),
        *three("c-task", vanilla={"exits": (0, 0)}),
    ]
    lines = render(traces)
    titles = [x.split(" (")[0] for x in lines if x.startswith("## ") and not x.startswith("## Adoption")]
    assert titles == [
        "## Failure categories per arm",
        "## Timelike loses",
        "## Ties",
        "## Timelike wins",
        "## Not compared: infrastructure",
    ]
    assert any(x.startswith("### a-task") for x in section(lines, "Timelike loses"))
    assert any(x.startswith("### b-task") for x in section(lines, "Ties"))
    assert any(x.startswith("### c-task") for x in section(lines, "Timelike wins"))


def test_a_stopped_run_is_listed_as_not_compared_never_as_a_loss() -> None:
    stopped = {
        "exits": (),
        "kind": "stopped",
        "reason": "the provider answered 429",
        "cause": "api-rate-limit",
    }
    lines = render(three("a-task", not_told=stopped, told=stopped))
    assert [x for x in section(lines, "Timelike loses") if x] == []
    assert [x for x in section(lines, "Not compared: infrastructure") if x] == [
        "- a-task · timelike, not told: stopped (api-rate-limit) — the provider answered 429",
        "- a-task · timelike, told: stopped (api-rate-limit) — the provider answered 429",
        "A run that stopped for an infrastructure reason is never counted as a loss or a win.",
    ]


def test_a_partly_stopped_task_is_placed_by_the_comparison_that_was_made() -> None:
    stopped = {"exits": (), "kind": "stopped", "reason": "turn cap", "cause": "turn-cap"}
    lines = render(three("a-task", vanilla={"exits": (0, 0)}, told=stopped))
    block = section(lines, "Timelike wins")
    assert any(
        x.startswith("Told vs vanilla: Not compared — timelike, told stopped (turn-cap)") for x in block
    )


def test_a_task_block_explains_itself_across_three_arms() -> None:
    text = r.TaskText(
        "Commit it.",
        "Hooks off (the cost)",
        "Timelike skips hooks.",
        {"timelike:completed": ("fine", ("step 1",))},
    )
    block = section(render(three("a-task"), tasks={"a-task": text}), "Ties")
    assert block[0] == "### a-task — Commit it."
    assert block[1] == "Tests: Hooks off (the cost). Timelike skips hooks."
    assert block[2].startswith("Not told vs vanilla: Verdict: Tie") and block[3].startswith(
        "Told vs vanilla: "
    )
    assert cols(block[4]) == ["metric", "vanilla", "timelike, not told", "timelike, told"]
    assert [cols(x)[0] for x in block[5:11]] == [
        "ending",
        "turns",
        "hangs",
        "failed commands (hung included)",
        "tool calls",
        "wall-clock",
    ]
    for arm in ("vanilla", "timelike, not told", "timelike, told"):
        assert f"What happened in {arm}:" in block
    assert block.count("  Why: fine.") == 2  # the note is the timelike environment's, printed per arm


def test_each_call_is_told_with_its_exit_its_category_or_its_hang() -> None:
    stderr = ("bash: rg: command not found\nmore", "", "", "no exit")
    v = run("a-task", "vanilla", exits=(127, 124, 0, -1), hung=(1,), stderr=stderr)
    block = section(render([v, run("a-task", "told")]), "Timelike wins")
    arm = block[block.index("What happened in vanilla:") :]
    assert arm[1:5] == [
        "  1. `step 1` → exit 127 [command not found]: bash: rg: command not found",
        "  2. `step 2` → hung [timeout]: ended at the 120 s limit",
        "  3. `step 3` → exit 0",
        "  4. `step 4` → no exit reported [other]: no exit",
    ]


def test_a_missing_vanilla_is_incomplete_and_listed_with_the_losses() -> None:
    block = section(render([run("a-task", "told")]), "Timelike loses")
    assert block[0] == "### a-task — Do the first thing. (incomplete: no vanilla trace)"
    assert "What happened in vanilla: no trace was written for this arm." in block


# --- the appendix, files, odds and ends -------------------------------------------------------------


def test_token_and_spend_figures_only_in_the_appendix() -> None:
    spend = t.Spend(recorded=True, usd=0.1159, source="openrouter usage", unknown_generations=1)
    traces = [
        run(
            "a-task", "vanilla", harness="opencode", spend=spend, tokens=t.Tokens(True, input=100, output=20)
        ),
        run("a-task", "told", harness="opencode"),
    ]
    lines = render(traces)
    cut = lines.index(r.APPENDIX_HEADING)
    assert not [x for x in lines[:cut] if "token" in x.lower() or "$" in x]
    assert lines[cut + 1 :] == [
        "- opencode · a-task · vanilla: input 100, output 20; spend $0.1159 (openrouter usage, "
        "1 generations without a cost)",
        "- opencode · a-task · told: tokens not recorded (the fake agent uses no model); "
        "spend not recorded (the fake agent uses no model)",
        "Total spend: $0.1159 over 1 runs (openrouter usage; 1 generations not reported)",
    ]


def test_not_benchable_and_no_trailing_whitespace() -> None:
    lines = render(three("a-task"))
    i = lines.index("# Not benchable on this path")
    assert lines[i + 1] == "- TZ=UTC: Slim's tzdata already defaults to UTC"
    assert all(line == line.rstrip() for line in lines)


def test_build_report_from_files_equals_render_from_memory(tmp_path: Path) -> None:
    traces = three("a-task")
    for tr_ in traces:
        t.write_trace(tr_, tmp_path / "traces" / f"a-task--fake--{tr_.identity.arm}.json")
    lines = r.build_report(tmp_path, tasks=TASKS, not_benchable=NOT_BENCHABLE, reproduce=REPRODUCE)
    assert lines == render(traces)
    assert (tmp_path / "report.txt").read_text() == "\n".join(lines) + "\n"


def test_the_report_goes_through_the_key_gate(tmp_path: Path) -> None:
    value = "not-a-key-unique-7f3a"
    with pytest.raises(GateRefused):
        r.write_report(tmp_path, ["fine", f"leaked {value}"], Gate([value]))
    assert not (tmp_path / "report.txt").exists()


def test_fake_agent_name_matches_the_fake_agent() -> None:
    assert r.FAKE_AGENT_NAME == fakeagent.FAKE_AGENT_NAME


# --- live run 2, item 1: under "What happened", only what the trace shows ----------------------------

REJECT_NOTE = "The hook rejected the first commit; the agent removed the TODO line and committed again"
REJECT_PATH = (
    "git commit -m 'bench: update f'",
    "sed -i '/TODO/d' f",
    "git add f",
    "git commit -m 'bench: update f'",
)
REJECT_TEXT = r.TaskText("Commit it.", notes={"vanilla:completed": (REJECT_NOTE, REJECT_PATH)})


def _why_lines(trace: t.Trace) -> list[str]:
    lines = render([trace], tasks={"a-task": REJECT_TEXT})
    return [x for x in lines if x.startswith("  Why:")]


@pytest.mark.parametrize("harness", ["opencode", "codex"])
def test_a_live_trace_whose_calls_contradict_a_note_never_prints_it(harness: str) -> None:
    # Live run 2, codex · git-commit-hook-rejects · vanilla: the TODO line removed before the only commit,
    # which nothing rejected. The note's story did not happen, so it is not printed as what happened.
    live = run("a-task", "vanilla", harness=harness, exits=(0, 0, 0),
               commands=("sed -i '/TODO/d' f", "git add f", "git commit -m 'bench: update f'"))  # fmt: skip
    assert _why_lines(live) == []
    assert all(REJECT_NOTE not in x for x in render([live], tasks={"a-task": REJECT_TEXT}))


def test_a_live_trace_is_never_given_a_note_even_on_the_scripted_path() -> None:
    live = run("a-task", "vanilla", harness="codex", exits=(1, 0, 0, 0), commands=REJECT_PATH)
    assert _why_lines(live) == []


def test_a_fake_trace_gets_its_note_only_on_the_path_the_note_describes() -> None:
    scripted = run("a-task", "vanilla", exits=(1, 0, 0, 0), commands=REJECT_PATH)
    assert _why_lines(scripted) == [f"  Why: {REJECT_NOTE}."]
    other = run("a-task", "vanilla", exits=(0,), commands=("git commit -m 'bench: update f'",))
    assert _why_lines(other) == []
    failed = run("a-task", "vanilla", exits=(1, 0, 0, 0), commands=REJECT_PATH, kind="failed", reason="no")
    assert _why_lines(failed) == []  # keyed by ending, as before


def test_item2_a_trace_from_an_older_task_version_is_named_under_the_newer_goal() -> None:
    # A changed goal is a changed task (live run 2, item 2): re-reported from disk, an older run's traces are
    # shown under today's goal, and the block says that the runs were measured at another version.
    text = r.TaskText("Write it to out/log.txt.", version=3)
    old = render(three("a-task"), tasks={"a-task": text})  # run() records task_version 1
    assert any(
        x.startswith("Task version: measured at v1; the goal and notes shown here are v3's") for x in old
    )
    current = r.TaskText("Write it to out/log.txt.", version=1)
    assert not any(x.startswith("Task version:") for x in render(three("a-task"), tasks={"a-task": current}))
