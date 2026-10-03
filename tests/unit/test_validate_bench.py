"""Units for tests/e2e/fixtures/validate_bench.py (T013): it accepts what benchlib writes, and fails
on each thing it checks. The good trace is written by benchlib's own writer, so the two agree on the
real format; every bad case is a hand mutation, so the validator's rules are exercised on their own.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from benchlib import catalog, report, runner, trace
from conftest import REPO

SHA = "e" * 40
TASK = "git-inspect"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "validate_bench", REPO / "tests/e2e/fixtures/validate_bench.py"
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


vb = _load()


def good_trace(env: str) -> trace.Trace:
    ident = trace.Identity(
        SHA, env, "sha256:" + "1" * 64, SHA, "debian:trixie-slim@sha256:" + "2" * 64, "timelike-fake-agent",
        "1", "none (deterministic fake agent)", "bash -c", TASK, 1, 30, 300, "make bench",
    )  # fmt: skip
    call = trace.ToolCall(1, 1, "git log", 0, 10, False, 5, 0, 5, False, "")
    ending = trace.Ending("completed", "check passed")
    return trace.Trace(ident, (call,), trace.derive_totals([call], 10), ending, runner.NO_TOKENS)


@pytest.fixture
def out(tmp_path: Path) -> Path:
    for env in ("vanilla", "timelike"):
        trace.write_trace(good_trace(env), runner.trace_path(tmp_path, TASK, env))
    texts = {
        t.id: report.TaskText(t.goal, t.capability, t.difference, dict(t.notes)) for t in catalog.CATALOG
    }
    report.build_report(tmp_path, tasks=texts, not_benchable=catalog.NOT_BENCHABLE, reproduce="make bench")
    return tmp_path


def mutate(out: Path, env: str, change: Any) -> None:
    path = runner.trace_path(out, TASK, env)
    doc = json.loads(path.read_text())
    change(doc)
    path.write_text(json.dumps(doc))


def test_accepts_what_benchlib_writes(out: Path) -> None:
    assert vb.main(["traces", str(out), SHA, TASK]) == 0
    assert vb.main(["report", str(out)]) == 0


@pytest.mark.parametrize(
    ("change", "text"),
    [
        (lambda d: d["identity"].update(model_id=""), "identity.model_id is empty"),
        (lambda d: d["identity"].update(image_revision="f" * 40), "are not"),
        (lambda d: d["identity"].update(environment="timelike"), "identity names"),
        (lambda d: d["identity"].update(base_digest="debian:latest"), "no @sha256:"),
        (lambda d: d["totals"].update(hangs=1), "totals.hangs"),
        (lambda d: d["totals"].pop("wall_clock_ms"), "wall_clock_ms missing"),
        (lambda d: d.update(ending={"kind": "done", "reason": "x"}), "not a known kind"),
        (lambda d: d.update(tokens={"recorded": False, "reason": "r", "input": 0}), "counts present"),
        (lambda d: d.update(schema_version=2), "schema_version"),
        (lambda d: d.update(calls={}), "calls is not a list"),
    ],
)
def test_rejects_each_trace_fault(
    out: Path, change: Any, text: str, capsys: pytest.CaptureFixture[str]
) -> None:
    mutate(out, "vanilla", change)
    assert vb.main(["traces", str(out), SHA, TASK]) == 1
    assert text in capsys.readouterr().out


def test_rejects_a_missing_trace_and_a_non_object(out: Path, capsys: pytest.CaptureFixture[str]) -> None:
    runner.trace_path(out, TASK, "timelike").unlink()
    runner.trace_path(out, TASK, "vanilla").write_text("[]")
    assert vb.main(["traces", str(out), SHA, TASK]) == 1
    printed = capsys.readouterr().out
    assert "wanted" in printed and "not a JSON object" in printed


@pytest.mark.parametrize(
    ("edit", "text"),
    [
        (lambda ls: ["LIVE RUN — x", *ls[1:]], "fake-agent statement"),
        (lambda ls: [ls[0], "Measured by someone", *ls[2:]], "maintainer"),
        (lambda ls: [ls[0], ls[1], "one token here", *ls[2:]], "before the appendix"),
        (lambda ls: [x for x in ls if x != "## Appendix: tokens"], "no '## Appendix"),
        (lambda ls: [x for x in ls if not x.startswith("## Ties")], "out of order"),
        (lambda ls: [ls[0] + " (reworded)", *ls[1:]], "fake-agent statement"),
        (lambda ls: [x for x in ls if not x.startswith("Tests: ")], "no line starting 'Tests:'"),
        (lambda ls: [x for x in ls if not x.startswith("Verdict: ")], "no line starting 'Verdict:'"),
        (lambda ls: [x for x in ls if x != "What happened in timelike:"], "What happened in timelike:"),
    ],
)
def test_rejects_each_report_fault(
    out: Path, edit: Any, text: str, capsys: pytest.CaptureFixture[str]
) -> None:
    path = out / "report.txt"
    path.write_text("\n".join(edit(path.read_text().splitlines())) + "\n")
    assert vb.main(["report", str(out)]) == 1
    assert text in capsys.readouterr().out


def test_report_missing(tmp_path: Path) -> None:
    assert vb.main(["report", str(tmp_path)]) == 1


@pytest.mark.parametrize(
    ("name", "shaped"),
    [("ANTHROPIC_API_KEY", True), ("GH_TOKEN", True), ("DB_PASSWORD", True), ("GIT_CONFIG_KEY_0", False),
     ("MONKEY", False), ("KEYBOARD_LAYOUT", False), ("PATH", False)],
)  # fmt: skip
def test_env(tmp_path: Path, name: str, shaped: bool) -> None:
    f = tmp_path / "env"
    f.write_text(f"HOME=/tmp\n{name}=x\n")
    assert vb.main(["env", str(f)]) == (1 if shaped else 0)


def test_usage() -> None:
    assert vb.main(["nonsense"]) == 2


def hang_trace(out: Path, duration_ms: int, hung: bool = True) -> None:
    def change(d: Any) -> None:
        d["calls"][0].update(hung=hung, duration_ms=duration_ms, exit_code=124 if hung else 0)
        d["totals"].update(hangs=int(hung), nonzero_exits=int(hung))

    mutate(out, "vanilla", change)


def test_hang_within_the_limit(out: Path) -> None:
    hang_trace(out, 31000)
    assert vb.main(["hang", str(out), TASK]) == 0


@pytest.mark.parametrize(("ms", "hung"), [(45000, True), (1000, True), (10, False)])
def test_hang_outside_the_limit_or_absent(out: Path, ms: int, hung: bool) -> None:
    hang_trace(out, ms, hung)
    assert vb.main(["hang", str(out), TASK]) == 1


def test_hang_missing_trace(tmp_path: Path) -> None:
    assert vb.main(["hang", str(tmp_path), TASK]) == 1
