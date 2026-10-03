"""report — the bench's comparison of vanilla with timelike, one task at a time.

The layout is specified in `.specswarm/features/002-speedup-bench/contracts/bench-cli.md` ("Report
layout") and the verdict in `data-model.md` ("Comparison and report").

The report is built from traces alone (FR-10): `render` is a pure function of the traces and three
caller-supplied facts (each task's texts, the not-benchable scope note and the reproduce command), so
a trace set re-reported from disk reads exactly as it did when it was measured. The first line says
what produced it: a report touched by any fake-agent run opens with the operator's own statement of
what such a run is (FR-9; send …-080659, F001). Losing cases come first (P6). Wall-clock time is shown
but never decides a verdict, and token counts appear only under the appendix heading.

Every task section explains itself, for a reader who has only the report (send …-080659, F002): what
the task tests and what differs between the images, the verdict in words, the metrics, then what
happened in each arm call by call and how it ended. All of that is derived from the traces, except
the task's own texts, and a note written with the task is printed only when that arm actually ended
the way the note describes, so prepared text can never narrate a run that did not happen (P005).

The catalog is deliberately not imported: task texts and the not-benchable list are parameters, so the
report depends on the trace schema and nothing else. Stdlib only (constitution H5).
"""

from __future__ import annotations

import contextlib
import os
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from benchlib.trace import ENDING_KINDS, Trace, load_traces

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
NO_TRACES_LINE = "NO TRACES — nothing was measured"
APPENDIX_HEADING = "## Appendix: tokens"
# Assumption 1: the comparison means only what its baseline is, so the header names it.
VANILLA_DEFINITION = "same base, user and git, without timelike's layers"

Verdict = Literal["loses", "tie", "wins", "incomplete"]


@dataclass(frozen=True)
class TaskText:
    """What the report says about a task beyond its traces: the catalog's words, passed in by the caller.

    `notes` maps "<environment>:<ending kind>" to an interpretation; it is printed under that arm only
    when the arm ended that way.
    """

    goal: str
    capability: str = ""
    difference: str = ""
    notes: Mapping[str, str] = field(default_factory=dict)


_NO_TEXT = TaskText(goal="(no goal given)")
_STDERR_LINE = 160  # characters of a failed call's first stderr line shown in the report

# Best first; a lower index is a better ending.
_ENDING_RANK = {kind: i for i, kind in enumerate(ENDING_KINDS)}
_SECTIONS: tuple[tuple[str, tuple[Verdict, ...]], ...] = (
    ("Timelike loses", ("loses", "incomplete")),  # a missing pair is never dropped, and never a win
    ("Ties", ("tie",)),
    ("Timelike wins", ("wins",)),
)
_GAP = 3  # spaces between table columns
# Row label -> Totals field ("wall_clock" is rendered from wall_clock_ms, in seconds).
_METRICS = (
    ("turns", "turns"),
    ("failed commands (hung included)", "nonzero_exits"),
    ("hangs", "hangs"),
    ("tool calls", "tool_calls"),
    ("wall-clock", "wall_clock"),
)


def pair(traces: Iterable[Trace]) -> dict[str, dict[str, Trace]]:
    """Task id -> environment -> trace. A second trace for the same task and environment is refused.

    Slice 0 runs one repetition, so two traces for one slot mean the trace set is not what the report
    thinks it is; picking one silently would decide the verdict by file order.
    """
    out: dict[str, dict[str, Trace]] = {}
    for trace in traces:
        ident = trace.identity
        slot = out.setdefault(ident.task_id, {})
        if ident.environment in slot:
            raise ValueError(f"two {ident.environment} traces for task {ident.task_id!r}")
        slot[ident.environment] = trace
    return out


def _sign(a: int, b: int) -> int:
    """+1 when timelike's `b` is lower (better) than vanilla's `a`, -1 when higher, 0 when equal."""
    return (a > b) - (a < b)


def verdict(vanilla: Trace | None, timelike: Trace | None) -> Verdict:
    """From timelike's side: ending rank, then fewer turns, then fewer failures. Wall-clock never decides."""
    if vanilla is None or timelike is None:
        return "incomplete"
    v, t = vanilla.totals, timelike.totals
    for decided in (
        _sign(_ENDING_RANK[vanilla.ending.kind], _ENDING_RANK[timelike.ending.kind]),
        _sign(v.turns, t.turns),
        _sign(v.nonzero_exits + v.hangs, t.nonzero_exits + t.hangs),
    ):
        if decided:
            return "wins" if decided > 0 else "loses"
    return "tie"


# --- rendering ----------------------------------------------------------------------------------


def _one(values: Iterable[str]) -> str:
    """The single value the traces agree on; "mixed (a, b)" when they don't; "none" when there are none.

    A report never picks one stamp out of several: a mixed trace set says so on its header.
    """
    distinct = sorted(set(values))
    if not distinct:
        return "none"
    if len(distinct) == 1:
        return distinct[0]
    return "mixed (" + ", ".join(distinct) + ")"


def _harness(traces: Sequence[Trace]) -> str:
    return _one(f"{t.identity.harness_name} {t.identity.harness_version}" for t in traces)


def _model(traces: Sequence[Trace]) -> str:
    return _one(t.identity.model_id for t in traces)


def _first_line(traces: Sequence[Trace]) -> str:
    if not traces:
        return NO_TRACES_LINE
    if any(t.identity.harness_name == FAKE_AGENT_NAME for t in traces):
        return FAKE_LINE
    return f"LIVE RUN — {_harness(traces)}, model {_model(traces)}; a single repetition, no spread (slice 2)"


def _identity_line(traces: Sequence[Trace]) -> str:
    vanilla = [t for t in traces if t.identity.environment == "vanilla"]
    return (
        f"Timelike {_one(t.identity.bench_revision for t in traces)}"
        f" · vanilla {_one(t.identity.image_id for t in vanilla)}"
        f" (base {_one(t.identity.base_digest for t in vanilla)}; {VANILLA_DEFINITION})"
        f" · harness {_harness(traces)}"
        f" · model {_model(traces)}"
        f" · invocation {_one(t.identity.invocation for t in traces)}, no TTY"
    )


def _ending(trace: Trace | None) -> str:
    """The table cell: the ending kind alone. Its reason is told in words below the table."""
    return "no trace" if trace is None else trace.ending.kind


def _metric_rows(vanilla: Trace | None, timelike: Trace | None) -> list[tuple[str, str, str]]:
    rows = [("metric", "vanilla", "timelike"), ("ending", _ending(vanilla), _ending(timelike))]
    rows += [(label, _cell(vanilla, pick), _cell(timelike, pick)) for label, pick in _METRICS]
    return rows


def _cell(trace: Trace | None, pick: str) -> str:
    if trace is None:
        return "—"
    if pick == "wall_clock":
        return f"{trace.totals.wall_clock_ms / 1000:.1f} s"
    return str(getattr(trace.totals, pick))


def _table(rows: Sequence[tuple[str, ...]]) -> list[str]:
    """Columns left-aligned, each padded to its widest cell plus a gap; no trailing spaces."""
    widths = [max(len(row[i]) for row in rows) + _GAP for i in range(len(rows[0]) - 1)]
    return ["".join(cell.ljust(w) for cell, w in zip(row, widths, strict=False)) + row[-1] for row in rows]


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def _outcome(trace: Trace) -> str:
    """How an arm ended, in words: "completed", or "<kind>: <reason>"."""
    return "completed" if trace.ending.kind == "completed" else f"{trace.ending.kind}: {trace.ending.reason}"


def _verdict_line(vanilla: Trace | None, timelike: Trace | None) -> str:
    """The verdict in words, naming what decided it (the same order as `verdict`)."""
    if vanilla is None or timelike is None:
        missing = "vanilla" if vanilla is None else "timelike"
        return (
            f"Verdict: incomplete — there is no {missing} trace, so nothing can be compared. "
            "It is listed with the losses so that it is never missed."
        )
    v, t = vanilla.totals, timelike.totals
    who = {"wins": "Timelike wins", "loses": "Timelike loses", "tie": "Tie", "incomplete": ""}
    decided = verdict(vanilla, timelike)
    if vanilla.ending.kind != timelike.ending.kind:
        better, worse = (vanilla, timelike) if decided == "loses" else (timelike, vanilla)
        return (
            f"Verdict: {who[decided]} — {better.identity.environment} {_outcome(better)}; "
            f"{worse.identity.environment} {_outcome(worse)}. A run that ends {worse.ending.kind} "
            f"ranks below one that ends {better.ending.kind}, whatever the turns."
        )
    if v.turns != t.turns:
        return (
            f"Verdict: {who[decided]} — both {_outcome(vanilla)}; timelike took "
            f"{_plural(t.turns, 'turn')} to vanilla's {v.turns}."
        )
    vf, tf = v.nonzero_exits + v.hangs, t.nonzero_exits + t.hangs
    if vf != tf:
        return (
            f"Verdict: {who[decided]} — both {_outcome(vanilla)} in {_plural(t.turns, 'turn')}; timelike "
            f"had {tf} failed or hung commands to vanilla's {vf}."
        )
    return (
        f"Verdict: Tie — both {_outcome(vanilla)}, in {_plural(t.turns, 'turn')}, "
        f"with {_plural(t.nonzero_exits, 'failed command')} and {_plural(t.hangs, 'hang')}."
    )


def _first_stderr(text: str) -> str:
    line = next((x.strip() for x in text.splitlines() if x.strip()), "")
    return line if len(line) <= _STDERR_LINE else line[: _STDERR_LINE - 1] + "…"


def _call_line(trace: Trace, i: int) -> str:
    call = trace.calls[i]
    head = f"  {call.seq}. `{call.command}` →"
    if call.hung:
        return f"{head} hung: killed at the {trace.identity.call_limit_s} s limit"
    if call.exit_code == 0:
        return f"{head} exit 0"
    said = _first_stderr(call.stderr_head)
    return f"{head} exit {call.exit_code}: {said}" if said else f"{head} exit {call.exit_code} (no message)"


def _arm(env: str, trace: Trace | None, text: TaskText) -> list[str]:
    if trace is None:
        return [f"What happened in {env}: no trace was written for this arm."]
    lines = [f"What happened in {env}:"]
    lines += [_call_line(trace, i) for i in range(len(trace.calls))] or ["  (no tool calls)"]
    if trace.ending.kind == "completed":
        lines.append("  Ended: completed — the check confirmed the goal.")
    else:
        lines.append(f"  Ended: {trace.ending.kind} — {trace.ending.reason}.")
    note = text.notes.get(f"{env}:{trace.ending.kind}")
    if note:
        lines.append(f"  Why: {note}.")
    return lines


def _task_block(task_id: str, text: TaskText, envs: Mapping[str, Trace]) -> list[str]:
    vanilla, timelike = envs.get("vanilla"), envs.get("timelike")
    heading = f"### {task_id} — {text.goal}"
    missing = [env for env, trace in (("vanilla", vanilla), ("timelike", timelike)) if trace is None]
    if missing:
        heading += f" (incomplete: no {' or '.join(missing)} trace)"
    lines = [heading]
    if text.capability or text.difference:
        tests = ". ".join(x.rstrip(".") for x in (text.capability, text.difference) if x)
        lines.append(f"Tests: {tests}.")
    lines += [_verdict_line(vanilla, timelike), *_table(_metric_rows(vanilla, timelike))]
    lines += ["", *_arm("vanilla", vanilla, text), "", *_arm("timelike", timelike, text)]
    return lines


def _tokens_line(trace: Trace) -> str:
    where = f"{trace.identity.task_id} · {trace.identity.environment}"
    tokens = trace.tokens
    if tokens.recorded:
        return f"- {where}: input {tokens.input}, output {tokens.output}"
    return f"- {where}: not recorded — {tokens.reason}"


def _env_order(trace: Trace) -> tuple[str, int]:
    env = trace.identity.environment
    return (trace.identity.task_id, 0 if env == "vanilla" else 1)


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
    pairs = pair(traces)
    lines = [
        _first_line(traces),
        f"Measured by the project's own maintainer. Reproduce: {reproduce}",
        _identity_line(traces),
    ]
    verdicts = {
        task_id: verdict(envs.get("vanilla"), envs.get("timelike")) for task_id, envs in pairs.items()
    }
    for title, kinds in _SECTIONS:
        members = sorted(task_id for task_id, v in verdicts.items() if v in kinds)
        lines += ["", f"## {title} ({len(members)})"]
        for i, task_id in enumerate(members):
            if i:
                lines.append("")
            lines += _task_block(task_id, tasks.get(task_id, _NO_TEXT), pairs[task_id])
    lines += ["", "## Not benchable on this path"]
    lines += [f"- {capability}: {reason}" for capability, reason in not_benchable]
    lines += ["", APPENDIX_HEADING]
    lines += [_tokens_line(t) for t in sorted(traces, key=_env_order)] or ["no traces"]
    return lines


# --- files --------------------------------------------------------------------------------------


def write_report(directory: Path, lines: Sequence[str]) -> Path:
    """Write `<directory>/report.txt` atomically: a reader sees the old report or the new, never half."""
    path = directory / REPORT_NAME
    directory.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=f".{REPORT_NAME}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp)
        raise
    return path


def build_report(
    directory: Path,
    *,
    tasks: Mapping[str, TaskText],
    not_benchable: Sequence[tuple[str, str]],
    reproduce: str,
) -> list[str]:
    """Load `<directory>/traces/*.json`, render, write `<directory>/report.txt`; return the lines (FR-10)."""
    lines = render(load_traces(directory), tasks=tasks, not_benchable=not_benchable, reproduce=reproduce)
    write_report(directory, lines)
    return lines
