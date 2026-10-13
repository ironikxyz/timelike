"""report — the bench's comparison, per harness, of vanilla with timelike told and not told (slice 1).

The layout is specified in `.specswarm/features/002-speedup-bench/contracts/bench-cli.md` (§ Slice 1, "Report
layout, schema 2") and the verdict in `data-model.md` ("Comparison and report").

The report is built from traces alone (FR-10): `render` is a pure function of the traces and three
caller-supplied facts (each task's texts, the not-benchable scope note and the reproduce command), so a
trace set re-reported from disk reads exactly as it did when it was measured. The first line says what
produced it: a fake-agent run opens with the operator's own statement of what such a run is (FR-9), a
stand-in run says the harnesses drove a scripted stand-in, and a live run says it is one repetition.

**One section per harness** (FR-22). Arms are compared within a harness, never across harnesses, because each
harness counts turns from its own events. Each section opens with the **adoption** table (FR-20: timelike tool
calls per arm, and calls through timelike's shims and guards, which are never adoption) and the **failure
categories** table (FR-42), then the tasks: losing cases first (P6), then ties, then wins, then the runs that
were **not compared** because they stopped for an infrastructure reason (FR-36), which are never a loss.

**The verdict** (revision 8, FR-48) compares one timelike arm with vanilla: ending, then turns, then hangs,
then failed commands, each call counted once per row. Wall-clock and tool calls are shown and never decide.
The sentence quotes only counts in the table. A task is listed under the worse of its two verdicts (FR-49).

Every task block explains itself (send …-080659, F002): what it tests and what differs between the images,
the verdicts in words, the metrics, then what happened in each arm call by call. A note written with a task is
printed only when that arm ended the way it describes. Token and spend figures appear only under the appendix
heading. The catalog is not imported: the report depends on the trace schema alone. Stdlib only (H5).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from benchlib.categories import CATEGORIES, LABELS
from benchlib.keyfile import Gate
from benchlib.trace import Trace, load_traces

# Must equal fakeagent.FAKE_AGENT_NAME; a unit asserts it. Not imported, so the report can be built
# from traces without the fake agent's module (FR-10).
FAKE_AGENT_NAME = "timelike-fake-agent"

REPORT_NAME = "report.txt"

# The operator's text, verbatim (send …-080659, F001): it states what the run is. Do not reword it.
FAKE_LINE = (
    "FAKE-AGENT BENCH PIPELINE DEMO RUN -- This is not a test of timelike, rather a test of the bench "
    "test itself (its presentation and usefulness to the human user). "
    "The agent's policy was written by timelike's own builders."
)
STANDIN_LINE = (
    "STAND-IN MODEL RUN -- live harnesses drove a scripted model stand-in, not a model; "
    "this tests the bench's live path, not timelike."
)
LIVE_LINE = "LIVE RUN — n = 1 per cell: a single repetition, no spread (slice 2 adds repetitions)"
NO_TRACES_LINE = "NO TRACES — nothing was measured"
APPENDIX_HEADING = "# Appendix: tokens and spend"
FAKE_CANNOT_READ = (
    "The fake agent cannot read a placement: its told and not-told arms run the same policy, "
    "so they can only differ by what the environment does."
)
COUNTS_NOTE = "Counted from each call's command words, never from the model's words."
# Assumption 1: the comparison means only what its baseline is, so the header names it.
VANILLA_DEFINITION = "same base, user and git, without timelike's layers"

ARMS = ("vanilla", "not-told", "told")
ARM_LABELS = {"vanilla": "vanilla", "not-told": "timelike, not told", "told": "timelike, told"}
VERSUS = {"not-told": "Not told vs vanilla", "told": "Told vs vanilla"}

Verdict = Literal["loses", "tie", "wins", "incomplete", "not-compared"]


@dataclass(frozen=True)
class TaskText:
    """What the report says about a task beyond its traces: the catalog's words, passed in by the caller.

    `notes` maps "<environment>:<ending kind>" to an interpretation; it is printed under an arm of that
    environment only when the arm ended that way.
    """

    goal: str
    capability: str = ""
    difference: str = ""
    notes: Mapping[str, str] = field(default_factory=dict)


_NO_TEXT = TaskText(goal="(no goal given)")
_STDERR_LINE = 160  # characters of a failed call's first output line shown in the report

# Best first; a lower index is a better ending. `stopped` is never compared.
_ENDING_RANK = {kind: i for i, kind in enumerate(("completed", "escalated", "failed", "hung"))}
_WORSE_FIRST: tuple[Verdict, ...] = ("incomplete", "loses", "tie", "wins")
_SECTIONS: tuple[tuple[str, tuple[Verdict, ...]], ...] = (
    ("Timelike loses", ("loses", "incomplete")),  # a missing arm is never dropped, and never a win
    ("Ties", ("tie",)),
    ("Timelike wins", ("wins",)),
)
_GAP = 3  # spaces between table columns
# In the verdict's order (revision 8): turns, hangs, then failed commands; then what never decides.
_METRICS = (
    ("turns", "turns"),
    ("hangs", "hangs"),
    ("failed commands (hung included)", "nonzero_exits"),
    ("tool calls", "tool_calls"),
    ("wall-clock", "wall_clock"),
)

Cells = dict[str, Trace]  # arm -> trace, for one task under one harness


def harness_key(trace: Trace) -> str:
    name = trace.identity.harness_name
    return "fake" if name == FAKE_AGENT_NAME else name


def pair(traces: Iterable[Trace]) -> dict[str, dict[str, Cells]]:
    """Harness -> task id -> arm -> trace, harnesses in the order first seen. A second trace for a slot is
    refused: slice 1 runs one repetition, so two traces for one slot mean the set is not what it seems."""
    out: dict[str, dict[str, Cells]] = {}
    for trace in traces:
        ident = trace.identity
        slot = out.setdefault(harness_key(trace), {}).setdefault(ident.task_id, {})
        if ident.arm in slot:
            raise ValueError(f"two {harness_key(trace)} {ident.arm} traces for task {ident.task_id!r}")
        slot[ident.arm] = trace
    return out


def _sign(a: int, b: int) -> int:
    """+1 when timelike's `b` is lower (better) than vanilla's `a`, -1 when higher, 0 when equal."""
    return (a > b) - (a < b)


def verdict(vanilla: Trace | None, timelike: Trace | None) -> Verdict:
    """From timelike's side, revision 8's order: ending rank, then fewer turns, then fewer hangs, then fewer
    failed commands. Each call counts once per figure: a hung call is one hang and one failed command (it is a
    non-zero exit), never two failures. Wall-clock and tool calls never decide. A stopped side is not
    compared."""
    if vanilla is None or timelike is None:
        return "incomplete"
    if vanilla.ending.kind == "stopped" or timelike.ending.kind == "stopped":
        return "not-compared"
    v, t = vanilla.totals, timelike.totals
    for decided in (
        _sign(_ENDING_RANK[vanilla.ending.kind], _ENDING_RANK[timelike.ending.kind]),
        _sign(v.turns, t.turns),
        _sign(v.hangs, t.hangs),
        _sign(v.nonzero_exits, t.nonzero_exits),
    ):
        if decided:
            return "wins" if decided > 0 else "loses"
    return "tie"


def task_verdicts(cells: Cells) -> dict[str, Verdict]:
    """Each timelike arm present against vanilla."""
    return {
        arm: verdict(cells.get("vanilla"), cells.get(arm)) for arm in ("not-told", "told") if arm in cells
    }


def placement_of(cells: Cells) -> Verdict:
    """The section a task goes in: the worse of its compared verdicts; `not-compared` when none was."""
    verdicts = task_verdicts(cells)
    if "vanilla" not in cells or not verdicts:
        return "incomplete"
    compared = [v for v in verdicts.values() if v != "not-compared"]
    if not compared:
        return "not-compared"
    return min(compared, key=_WORSE_FIRST.index)


# --- rendering ----------------------------------------------------------------------------------


def _one(values: Iterable[str]) -> str:
    """The single value the traces agree on; "mixed (a, b)" when they don't; "none" when there are none."""
    distinct = sorted(set(values))
    if not distinct:
        return "none"
    if len(distinct) == 1:
        return distinct[0]
    return "mixed (" + ", ".join(distinct) + ")"


def _is_standin(trace: Trace) -> bool:
    return bool(trace.extensions.get("standin"))


def _first_line(traces: Sequence[Trace]) -> str:
    if not traces:
        return NO_TRACES_LINE
    if any(t.identity.harness_name == FAKE_AGENT_NAME for t in traces):
        return FAKE_LINE
    if any(_is_standin(t) for t in traces):
        return STANDIN_LINE
    return LIVE_LINE


def _identity_line(traces: Sequence[Trace]) -> str:
    vanilla = [t for t in traces if t.identity.environment == "vanilla"]
    arms = [ARM_LABELS[a] for a in ARMS if any(t.identity.arm == a for t in traces)]
    return (
        f"Timelike {_one(t.identity.bench_revision for t in traces)}"
        f" · vanilla {_one(t.identity.image_id for t in vanilla)}"
        f" (base {_one(t.identity.base_digest for t in vanilla)}; {VANILLA_DEFINITION})"
        f" · model {_one(t.identity.model_id for t in traces)}"
        f" · arms: {', '.join(arms) or 'none'}"
    )


def _harness_line(traces: Sequence[Trace]) -> str:
    name = traces[0].identity.harness_name
    pinned = _one(t.identity.harness_version for t in traces)
    reported = _one(
        t.identity.harness_reported_version
        for t in traces
        if t.identity.harness_reported_version != "not run"
    )
    answered = _one(m for t in traces for m in t.identity.models_answered)
    answered = "no answer recorded" if answered == "none" else answered
    invocation = _one(t.identity.invocation for t in traces)
    return (
        f"# Harness: {name} {pinned} (reported {reported}) · answered by {answered} · invocation {invocation}"
    )


def _table(rows: Sequence[tuple[str, ...]]) -> list[str]:
    """Columns left-aligned, each padded to its widest cell plus a gap; no trailing spaces."""
    widths = [max(len(row[i]) for row in rows) + _GAP for i in range(len(rows[0]) - 1)]
    return ["".join(cell.ljust(w) for cell, w in zip(row, widths, strict=False)) + row[-1] for row in rows]


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def _arms_in(tasks: Mapping[str, Cells]) -> list[str]:
    return [a for a in ARMS if any(a in cells for cells in tasks.values())]


def _adoption(tasks: Mapping[str, Cells], fake: bool) -> list[str]:
    rows: list[tuple[str, ...]] = [
        ("arm", "runs", "tool calls", "timelike tool calls", "tools used", "through timelike")
    ]
    for arm in _arms_in(tasks):
        runs = [cells[arm] for cells in tasks.values() if arm in cells]
        calls = sum(t.totals.tool_calls for t in runs)
        if arm == "vanilla":
            rows.append((ARM_LABELS[arm], str(len(runs)), str(calls), "—", "—", "—"))
            continue
        used: dict[str, int] = {}
        for t in runs:
            for c in t.calls:
                for name in c.timelike_tools:
                    used[name] = used.get(name, 0) + 1
        tools = ", ".join(f"{n} {used[n]}" for n in sorted(used)) or "none"
        adopted = sum(t.totals.timelike_tool_calls for t in runs)
        through = sum(t.totals.through_timelike_calls for t in runs)
        rows.append((ARM_LABELS[arm], str(len(runs)), str(calls), str(adopted), tools, str(through)))
    lines = ["## Adoption: timelike tool calls per arm", *_table(rows), COUNTS_NOTE]
    if fake:
        lines.append(FAKE_CANNOT_READ)
    return lines


def _categories(tasks: Mapping[str, Cells]) -> list[str]:
    arms = _arms_in(tasks)
    rows: list[tuple[str, ...]] = [("category", *(ARM_LABELS[a] for a in arms))]
    for cat in CATEGORIES:
        counts = []
        for arm in arms:
            counts.append(
                str(
                    sum(cells[arm].totals.by_category.get(cat, 0) for cells in tasks.values() if arm in cells)
                )
            )
        rows.append((LABELS[cat], *counts))
    return ["## Failure categories per arm (where the failed call ran: the task container)", *_table(rows)]


def _cell(trace: Trace | None, pick: str) -> str:
    if trace is None:
        return "—"
    if pick == "ending":
        return trace.ending.kind
    if pick == "wall_clock":
        return f"{trace.totals.wall_clock_ms / 1000:.1f} s"
    return str(getattr(trace.totals, pick))


def _metric_rows(cells: Cells) -> list[tuple[str, ...]]:
    arms = [a for a in ARMS if a in cells or a == "vanilla"]
    rows: list[tuple[str, ...]] = [("metric", *(ARM_LABELS[a] for a in arms))]
    rows.append(("ending", *(_cell(cells.get(a), "ending") for a in arms)))
    rows += [(label, *(_cell(cells.get(a), pick) for a in arms)) for label, pick in _METRICS]
    return rows


def _outcome(trace: Trace) -> str:
    """How an arm ended, in words: "completed", or "<kind>: <reason>"."""
    return "completed" if trace.ending.kind == "completed" else f"{trace.ending.kind}: {trace.ending.reason}"


def _verdict_line(vanilla: Trace | None, timelike: Trace | None, arm: str) -> str:
    """The verdict in words, naming what decided it (the same order as `verdict`)."""
    name = ARM_LABELS[arm]
    if vanilla is None or timelike is None:
        missing = "vanilla" if vanilla is None else name
        return (
            f"Verdict: incomplete — there is no {missing} trace, so nothing can be compared. "
            "It is listed with the losses so that it is never missed."
        )
    stopped = [
        (who_, run) for who_, run in (("vanilla", vanilla), (name, timelike)) if run.ending.kind == "stopped"
    ]
    if stopped:
        who_, run = stopped[0]
        return (
            f"Not compared — {who_} stopped ({run.ending.cause}): {run.ending.reason}. "
            "An infrastructure stop is never a loss."
        )
    v, t = vanilla.totals, timelike.totals
    who = {
        "wins": "Timelike wins",
        "loses": "Timelike loses",
        "tie": "Tie",
        "incomplete": "",
        "not-compared": "",
    }
    decided = verdict(vanilla, timelike)
    if vanilla.ending.kind != timelike.ending.kind:
        better, worse = (vanilla, timelike) if decided == "loses" else (timelike, vanilla)
        bname = "vanilla" if better is vanilla else name
        wname = "vanilla" if worse is vanilla else name
        return (
            f"Verdict: {who[decided]} — {bname} {_outcome(better)}; {wname} {_outcome(worse)}. "
            f"A run that ends {worse.ending.kind} ranks below one that ends {better.ending.kind}, "
            "whatever the turns."
        )
    if v.turns != t.turns:
        return (
            f"Verdict: {who[decided]} — both {_outcome(vanilla)}; {name} took {_plural(t.turns, 'turn')} "
            f"to vanilla's {v.turns}."
        )
    # Only counts that are rows of the table are quoted (revision 8): "hangs", "failed commands".
    if v.hangs != t.hangs:
        return (
            f"Verdict: {who[decided]} — both {_outcome(vanilla)} in {_plural(t.turns, 'turn')}; {name} "
            f"had {_plural(t.hangs, 'hang')} to vanilla's {v.hangs}."
        )
    if v.nonzero_exits != t.nonzero_exits:
        return (
            f"Verdict: {who[decided]} — both {_outcome(vanilla)} in {_plural(t.turns, 'turn')} with "
            f"{_plural(t.hangs, 'hang')}; {name} had {_plural(t.nonzero_exits, 'failed command')} to "
            f"vanilla's {v.nonzero_exits}."
        )
    return (
        f"Verdict: Tie — both {_outcome(vanilla)}, in {_plural(t.turns, 'turn')}, "
        f"with {_plural(t.hangs, 'hang')} and {_plural(t.nonzero_exits, 'failed command')}."
    )


def _first_output(text: str) -> str:
    line = next((x.strip() for x in text.splitlines() if x.strip()), "")
    return line if len(line) <= _STDERR_LINE else line[: _STDERR_LINE - 1] + "…"


def _call_line(trace: Trace, i: int) -> str:
    call = trace.calls[i]
    head = f"  {call.seq}. `{call.command}` →"
    if call.hung:
        return f"{head} hung [timeout]: ended at the {trace.identity.call_limit_s} s limit"
    if call.exit_code == 0:
        return f"{head} exit 0"
    exit_word = "no exit reported" if call.exit_code < 0 else f"exit {call.exit_code}"
    said = _first_output(call.stderr_head)
    tag = f" [{LABELS.get(call.category, call.category)}]"
    return f"{head} {exit_word}{tag}: {said}" if said else f"{head} {exit_word}{tag} (no message)"


def _arm(arm: str, trace: Trace | None, text: TaskText) -> list[str]:
    name = ARM_LABELS[arm]
    if trace is None:
        return [f"What happened in {name}: no trace was written for this arm."]
    lines = [f"What happened in {name}:"]
    lines += [_call_line(trace, i) for i in range(len(trace.calls))] or ["  (no tool calls)"]
    if trace.ending.kind == "completed":
        lines.append("  Ended: completed — the check confirmed the goal.")
    elif trace.ending.kind == "stopped":
        lines.append(f"  Ended: stopped ({trace.ending.cause}) — {trace.ending.reason}.")
    else:
        lines.append(f"  Ended: {trace.ending.kind} — {trace.ending.reason}.")
    note = text.notes.get(f"{trace.identity.environment}:{trace.ending.kind}")
    if note:
        lines.append(f"  Why: {note}.")
    return lines


def _task_block(task_id: str, text: TaskText, cells: Cells) -> list[str]:
    heading = f"### {task_id} — {text.goal}"
    timelike_arms = [a for a in ("not-told", "told") if a in cells]
    if "vanilla" not in cells:
        heading += " (incomplete: no vanilla trace)"
    elif not timelike_arms:
        heading += " (incomplete: no timelike trace)"
    lines = [heading]
    if text.capability or text.difference:
        tests = ". ".join(x.rstrip(".") for x in (text.capability, text.difference) if x)
        lines.append(f"Tests: {tests}.")
    for compared in timelike_arms or ["not-told"]:
        line = _verdict_line(cells.get("vanilla"), cells.get(compared), compared)
        lines.append(f"{VERSUS[compared]}: {line}")
    lines += _table(_metric_rows(cells))
    for arm in ARMS:
        if arm in cells or arm == "vanilla":
            lines += ["", *_arm(arm, cells.get(arm), text)]
    return lines


def _harness_section(
    tasks: Mapping[str, Cells], texts: Mapping[str, TaskText], traces: Sequence[Trace]
) -> list[str]:
    fake = traces[0].identity.harness_name == FAKE_AGENT_NAME
    lines = ["", _harness_line(traces), "", *_adoption(tasks, fake), "", *_categories(tasks)]
    placed = {task_id: placement_of(cells) for task_id, cells in tasks.items()}
    for title, kinds in _SECTIONS:
        members = sorted(task_id for task_id, v in placed.items() if v in kinds)
        lines += ["", f"## {title} ({len(members)})"]
        for i, task_id in enumerate(members):
            if i:
                lines.append("")
            lines += _task_block(task_id, texts.get(task_id, _NO_TEXT), tasks[task_id])
    stopped = [
        (task_id, arm, t)
        for task_id in sorted(tasks)
        for arm, t in sorted(tasks[task_id].items(), key=lambda kv: ARMS.index(kv[0]))
        if t.ending.kind == "stopped"
    ]
    lines += ["", f"## Not compared: infrastructure ({len(stopped)})"]
    lines += [
        f"- {task_id} · {ARM_LABELS[arm]}: stopped ({t.ending.cause}) — {t.ending.reason}"
        for task_id, arm, t in stopped
    ]
    if stopped:
        lines.append("A run that stopped for an infrastructure reason is never counted as a loss or a win.")
    return lines


def _spend_line(trace: Trace) -> str:
    i = trace.identity
    where = f"{harness_key(trace)} · {i.task_id} · {i.arm}"
    tokens = trace.tokens
    tok = (
        f"input {tokens.input}, output {tokens.output}"
        if tokens.recorded
        else f"tokens not recorded ({tokens.reason})"
    )
    spend = trace.spend
    if spend.recorded:
        unknown = (
            f", {spend.unknown_generations} generations without a cost" if spend.unknown_generations else ""
        )
        money = f"spend ${spend.usd:.4f} ({spend.source}{unknown})"
    else:
        money = f"spend not recorded ({spend.reason})"
    return f"- {where}: {tok}; {money}"


def _appendix(traces: Sequence[Trace]) -> list[str]:
    ordered = sorted(traces, key=lambda t: (harness_key(t), t.identity.task_id, ARMS.index(t.identity.arm)))
    lines = ["", APPENDIX_HEADING, *([_spend_line(t) for t in ordered] or ["no traces"])]
    recorded = [t for t in traces if t.spend.recorded]
    if recorded:
        total = sum(t.spend.usd or 0.0 for t in recorded)
        unknown = sum(t.spend.unknown_generations or 0 for t in recorded)
        sources = _one(t.spend.source or "" for t in recorded)
        lines.append(
            f"Total spend: ${total:.4f} over {len(recorded)} runs"
            f" ({sources}; {unknown} generations not reported)"
        )
    return lines


def render(
    traces: Sequence[Trace],
    *,
    tasks: Mapping[str, TaskText],
    not_benchable: Sequence[tuple[str, str]],
    reproduce: str,
) -> list[str]:
    """The report's lines, without newlines. Pure: the same inputs always give the same lines.

    `tasks` maps task id to its texts (a task with none says "(no goal given)" rather than being dropped);
    `not_benchable` is the catalog's (capability, reason) list; `reproduce` is the command that
    reproduces the whole report. Every section is present even when it is empty.
    """
    by_harness = pair(traces)
    lines = [
        _first_line(traces),
        f"Measured by the project's own maintainer. Reproduce: {reproduce}",
        _identity_line(traces) if traces else "No identity: there are no traces.",
    ]
    for key, tasks_of in by_harness.items():
        lines += _harness_section(tasks_of, tasks, [t for t in traces if harness_key(t) == key])
    lines += ["", "# Not benchable on this path"]
    lines += [f"- {capability}: {reason}" for capability, reason in not_benchable]
    lines += _appendix(traces)
    return lines


# --- files --------------------------------------------------------------------------------------


def write_report(directory: Path, lines: Sequence[str], gate: Gate | None = None) -> Path:
    """Write `<directory>/report.txt` atomically through the key gate (FR-31)."""
    return (gate or Gate()).write_text(directory / REPORT_NAME, "\n".join(lines) + "\n")


def build_report(
    directory: Path,
    *,
    tasks: Mapping[str, TaskText],
    not_benchable: Sequence[tuple[str, str]],
    reproduce: str,
    gate: Gate | None = None,
) -> list[str]:
    """Load `<directory>/traces/*.json`, render, write `<directory>/report.txt`; return the lines (FR-10)."""
    lines = render(load_traces(directory), tasks=tasks, not_benchable=not_benchable, reproduce=reproduce)
    write_report(directory, lines, gate)
    return lines
