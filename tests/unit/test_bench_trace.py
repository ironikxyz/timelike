"""Units for benchlib.trace — the bench's run record (contract: trace-schema.md, rules 1–6).

Each rejection is tested one violation at a time on an otherwise valid trace, so a test that passes
proves that rule, not a neighbour.
"""

from __future__ import annotations

import dataclasses
import json
import os
from pathlib import Path
from typing import Any

import pytest
from benchlib import trace as t
from benchlib.categories import categorize

SHA = "a" * 40


def call(seq: int, exit_code: int = 0, hung: bool = False, turn: int | None = None) -> t.ToolCall:
    return t.ToolCall(
        seq=seq,
        turn=seq if turn is None else turn,
        command=f"step {seq}",
        exit_code=exit_code,
        duration_ms=10,
        hung=hung,
        stdout_bytes=5,
        stderr_bytes=3,
        passed_bytes=8,
        harness_cut=False,
        stderr_head="",
        category=categorize(exit_code, hung, ""),
    )


def identity(**over: Any) -> t.Identity:
    base: dict[str, Any] = {
        "bench_revision": SHA,
        "environment": "vanilla",
        "arm": "vanilla",
        "image_id": "sha256:" + "b" * 64,
        "image_revision": SHA,
        "base_digest": "debian:trixie-slim@sha256:" + "c" * 64,
        "harness_name": "timelike-fake-agent",
        "harness_version": "1",
        "harness_reported_version": "1",
        "model_id": "none (deterministic fake agent)",
        "models_answered": (),
        "invocation": "bash -c",
        "output_streams": "separate",
        "placement": "",
        "task_id": "git-rebase-continue",
        "task_version": 1,
        "call_limit_s": 30,
        "run_limit_s": 300,
        "turn_cap": 0,
        "timelike_tools": (),
        "reproduce": "make bench TASKS=git-rebase-continue",
    }
    base.update(over)
    return t.Identity(**base)


def make(calls: tuple[t.ToolCall, ...] | None = None, **over: Any) -> t.Trace:
    calls = (call(1), call(2, exit_code=1), call(3, exit_code=124, hung=True)) if calls is None else calls
    fields: dict[str, Any] = {
        "identity": identity(),
        "calls": calls,
        "totals": t.derive_totals(calls, 1840),
        "ending": t.Ending("completed", "check passed"),
        "tokens": t.Tokens(recorded=False, reason="the fake agent uses no model"),
        "spend": t.NO_SPEND,
        "extensions": {},
    }
    fields.update(over)
    return t.Trace(**fields)


def as_dict(trace: t.Trace) -> dict[str, Any]:
    result: dict[str, Any] = json.loads(t.to_json(trace))
    return result


# --- valid traces --------------------------------------------------------------------------------


def test_valid_trace_round_trips() -> None:
    trace = make(tokens=t.Tokens(recorded=True, input=10, output=0), extensions={"arm": "told"})
    assert t.validate(trace) == []
    text = t.to_json(trace)
    assert text.endswith("}\n")
    assert text == json.dumps(json.loads(text), sort_keys=True, indent=2) + "\n"
    assert t.from_json(text) == trace


def test_derive_totals_counts_hung_as_nonzero() -> None:
    totals = t.derive_totals((call(1), call(2, exit_code=1), call(3, exit_code=137, hung=True)), 99)
    assert totals == t.Totals(
        turns=3,
        tool_calls=3,
        nonzero_exits=2,
        hangs=1,
        wall_clock_ms=99,
        timelike_tool_calls=0,
        through_timelike_calls=0,
        by_category={"timeout": 1, "other": 1},
    )


def test_derive_totals_turns_is_max_turn() -> None:
    assert t.derive_totals((call(1, turn=2), call(2, turn=1)), 0).turns == 2


def test_no_calls_is_valid_with_zero_totals() -> None:
    trace = make(calls=(), ending=t.Ending("failed", "setup failed: boom"))
    assert trace.totals == t.Totals(0, 0, 0, 0, 1840, 0, 0, {})
    assert t.validate(trace) == []


def test_validate_accepts_dict() -> None:
    assert t.validate(as_dict(make())) == []


# --- rule 1: stamps ------------------------------------------------------------------------------

STR_FIELDS = [f.name for f in dataclasses.fields(t.Identity) if f.type == "str" and f.name != "placement"]
INT_FIELDS = ["task_version", "call_limit_s", "run_limit_s"]


@pytest.mark.parametrize("name", STR_FIELDS)
@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_identity_string_rejected(name: str, blank: str) -> None:
    fields = {name: blank}
    if name == "bench_revision":
        fields["image_revision"] = blank  # isolate emptiness from the revision rule
    violations = t.validate(make(identity=identity(**fields)))
    assert f"identity.{name}: empty" in violations


@pytest.mark.parametrize("name", INT_FIELDS)
@pytest.mark.parametrize("value", [0, -1])
def test_nonpositive_identity_int_rejected(name: str, value: int) -> None:
    assert t.validate(make(identity=identity(**{name: value}))) == [
        f"identity.{name}: must be > 0, got {value}"
    ]


@pytest.mark.parametrize("name", STR_FIELDS + INT_FIELDS)
def test_missing_identity_field_rejected(name: str) -> None:
    data = as_dict(make())
    del data["identity"][name]
    assert t.validate(data) == [f"identity.{name}: missing"]


def test_revision_mismatch_rejected() -> None:
    assert t.validate(make(identity=identity(image_revision="b" * 40))) == [
        "identity.image_revision: must equal bench_revision"
    ]


def test_bad_digest_rejected() -> None:
    assert t.validate(make(identity=identity(base_digest="debian:trixie-slim"))) == [
        "identity.base_digest: must contain '@sha256:'"
    ]


def test_unknown_environment_rejected() -> None:
    assert t.validate(make(identity=identity(environment="docker"))) == [
        "identity.environment: must be one of vanilla, timelike"
    ]


def test_identity_wrong_types_rejected() -> None:
    data = as_dict(make())
    data["identity"]["task_version"] = True
    data["identity"]["model_id"] = None
    data["identity"]["extra"] = "x"
    assert t.validate(data) == [
        "identity.extra: unknown key",
        "identity.model_id: must be str, got NoneType",
        "identity.task_version: must be int, got bool",
    ]


def test_identity_not_object_rejected() -> None:
    data = as_dict(make())
    data["identity"] = "x"
    assert t.validate(data) == ["identity: must be an object"]


# --- rule 2: totals ------------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["turns", "tool_calls", "nonzero_exits", "hangs"])
def test_totals_disagreement_rejected(name: str) -> None:
    trace = make()
    wrong = dataclasses.replace(trace.totals, **{name: getattr(trace.totals, name) + 1})
    assert t.validate(dataclasses.replace(trace, totals=wrong)) == [
        f"totals.{name}: {getattr(wrong, name)} disagrees with calls ({getattr(trace.totals, name)})"
    ]


def test_negative_wall_clock_rejected() -> None:
    trace = make()
    trace = dataclasses.replace(trace, totals=dataclasses.replace(trace.totals, wall_clock_ms=-1))
    assert t.validate(trace) == ["totals.wall_clock_ms: must be >= 0"]


def test_malformed_call_skips_totals_check() -> None:
    data = as_dict(make())
    data["calls"][0] = "x"
    data["totals"]["turns"] = 99
    assert t.validate(data) == ["calls[0]: must be an object"]


def test_calls_not_list_rejected() -> None:
    data = as_dict(make())
    data["calls"] = {}
    assert t.validate(data) == ["calls: must be a list"]


def test_call_rules() -> None:
    bad = dataclasses.replace(call(1), turn=0, duration_ms=-1, harness_cut=True)
    trace = make(calls=(bad, dataclasses.replace(call(2), seq=5)))
    assert t.validate(trace) == [
        "calls[0].turn: must be >= 1, got 0",
        "calls[0].duration_ms: must be >= 0",
        "calls[0].harness_cut: must be true exactly when passed_bytes is below the total",
        "calls[1].seq: must be 2 (1-based, in order), got 5",
    ]


def test_harness_cut_when_passed_below_total_is_valid() -> None:
    cut = dataclasses.replace(call(1), passed_bytes=4, harness_cut=True)
    assert t.validate(make(calls=(cut,))) == []


# --- rule 3: endings -----------------------------------------------------------------------------


def test_unknown_ending_rejected() -> None:
    assert t.validate(make(ending=t.Ending("aborted", "x"))) == [
        "ending.kind: unknown 'aborted' (one of completed, escalated, failed, hung, stopped)"
    ]


@pytest.mark.parametrize("reason", ["line one\nline two", "a\rb", "trailing\n", "a b"])
def test_multiline_reason_rejected(reason: str) -> None:
    assert t.validate(make(ending=t.Ending("failed", reason))) == ["ending.reason: must be a single line"]


@pytest.mark.parametrize("reason", ["", " \t"])
def test_empty_reason_rejected(reason: str) -> None:
    assert t.validate(make(ending=t.Ending("failed", reason))) == ["ending.reason: empty"]


@pytest.mark.parametrize("kind", t.ENDING_KINDS)
def test_every_ending_kind_accepted(kind: str) -> None:
    cause = "api-rate-limit" if kind == "stopped" else ""
    assert t.validate(make(ending=t.Ending(kind, "why", cause))) == []


# --- rule 4: tokens ------------------------------------------------------------------------------


def test_tokens_not_recorded_serialises_without_counts() -> None:
    data = as_dict(make())
    assert data["tokens"] == {"recorded": False, "reason": "the fake agent uses no model"}


def test_tokens_not_recorded_with_counts_rejected() -> None:
    tokens = t.Tokens(recorded=False, reason="none", input=0, output=0)
    assert t.validate(make(tokens=tokens)) == ["tokens.input: unknown key", "tokens.output: unknown key"]


@pytest.mark.parametrize("reason", [None, "", "  "])
def test_tokens_not_recorded_needs_reason(reason: str | None) -> None:
    violations = t.validate(make(tokens=t.Tokens(recorded=False, reason=reason)))
    want = (
        "tokens.reason: missing"
        if reason is None
        else "tokens.reason: empty (say why the counts were not recorded)"
    )
    assert violations == [want]


def test_tokens_recorded_needs_both_counts() -> None:
    assert t.validate(make(tokens=t.Tokens(recorded=True, input=5))) == ["tokens.output: missing"]


def test_tokens_recorded_rejects_reason_and_negatives() -> None:
    tokens = t.Tokens(recorded=True, reason="x", input=-1, output=2)
    assert t.validate(make(tokens=tokens)) == ["tokens.reason: unknown key"]
    assert t.validate(make(tokens=t.Tokens(recorded=True, input=-1, output=2))) == [
        "tokens.input: must be >= 0"
    ]


@pytest.mark.parametrize("tokens", ["x", {"reason": "x"}, {"recorded": 0, "reason": "x"}])
def test_tokens_shape_rejected(tokens: object) -> None:
    data = as_dict(make())
    data["tokens"] = tokens
    want = "tokens: must be an object" if tokens == "x" else "tokens.recorded: must be bool"
    assert t.validate(data) == [want]


# --- rule 5: extension ---------------------------------------------------------------------------


def test_unknown_top_level_key_rejected() -> None:
    data = as_dict(make())
    data["arm"] = "told"
    assert t.validate(data) == ["arm: unknown top-level key (new fields go under extensions)"]


def test_unknown_key_under_extensions_accepted() -> None:
    data = as_dict(make())
    data["extensions"] = {"arm": "told", "nested": {"anything": [1, 2]}}
    assert t.validate(data) == []
    assert t.from_dict(data).extensions == data["extensions"]


def test_extensions_not_object_rejected() -> None:
    data = as_dict(make())
    data["extensions"] = []
    assert t.validate(data) == ["extensions: must be an object"]


def test_missing_top_level_key_rejected() -> None:
    data = as_dict(make())
    for k in ("calls", "ending", "extensions", "identity", "tokens", "totals"):
        del data[k]
    assert t.validate(data) == [
        "calls: missing",
        "ending: missing",
        "extensions: missing",
        "identity: missing",
        "tokens: missing",
        "totals: missing",
    ]


@pytest.mark.parametrize("version", [0, 3, "2", True, None])
def test_unknown_schema_version_rejected(version: object) -> None:
    data = as_dict(make())
    data["schema_version"] = version
    assert t.validate(data) == [f"schema_version: unknown {version!r} (this reader knows 2)"]


def test_schema_1_is_refused_naming_the_revision_that_re_reports_it() -> None:
    data = as_dict(make())
    data["schema_version"] = 1
    assert t.validate(data) == [
        "schema_version: 1 is slice 0's trace; re-report it with a slice-0 build of the bench"
    ]


def test_non_object_rejected() -> None:
    assert t.validate([]) == ["trace: must be an object"]  # type: ignore[arg-type]


# --- parsing and files ---------------------------------------------------------------------------


def test_from_json_rejects_invalid() -> None:
    with pytest.raises(t.TraceInvalid) as exc:
        t.from_json(t.to_json(make(ending=t.Ending("nope", "x"))))
    assert exc.value.violations == [
        "ending.kind: unknown 'nope' (one of completed, escalated, failed, hung, stopped)"
    ]
    assert "invalid trace: ending.kind" in str(exc.value)


def test_from_json_rejects_non_json() -> None:
    with pytest.raises(t.TraceInvalid, match="not JSON"):
        t.from_json("{")


def test_write_trace_writes_valid(tmp_path: Path) -> None:
    trace = make()
    path = tmp_path / "out" / "traces" / "git-rebase-continue--vanilla.json"
    t.write_trace(trace, path)
    assert path.read_text(encoding="utf-8") == t.to_json(trace)
    assert sorted(p.name for p in path.parent.iterdir()) == [path.name]  # no temp file left


def test_write_trace_invalid_writes_nothing(tmp_path: Path) -> None:
    path = tmp_path / "traces" / "x.json"
    with pytest.raises(t.TraceInvalid) as exc:
        t.write_trace(make(identity=identity(model_id="")), path)
    assert exc.value.violations == ["identity.model_id: empty"]
    assert not path.exists()
    assert not (tmp_path / "traces").exists()


def test_write_trace_failure_leaves_no_temp(tmp_path: Path) -> None:
    trace = make(extensions={"bad": object()})  # valid by the rules, but not JSON-serialisable
    trace_ok = make()
    path = tmp_path / "x.json"
    t.write_trace(trace_ok, path)
    with pytest.raises(TypeError):
        t.write_trace(trace, path)
    assert path.read_text(encoding="utf-8") == t.to_json(trace_ok)
    assert [p.name for p in tmp_path.iterdir()] == ["x.json"]


def test_write_trace_replace_failure_removes_temp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(src: str, dst: str) -> None:
        raise OSError("no")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError, match="no"):
        t.write_trace(make(), tmp_path / "x.json")
    assert list(tmp_path.iterdir()) == []


def test_load_traces_sorted_by_name(tmp_path: Path) -> None:
    names = ["b-task--vanilla", "a-task--timelike", "a-task--vanilla"]
    for name in names:
        t.write_trace(make(identity=identity(task_id=name)), tmp_path / "traces" / f"{name}.json")
    (tmp_path / "traces" / "notes.txt").write_text("ignored")
    assert [tr.identity.task_id for tr in t.load_traces(tmp_path)] == sorted(names)


def test_load_traces_missing_dir_is_empty(tmp_path: Path) -> None:
    assert t.load_traces(tmp_path) == []


def test_load_traces_names_bad_file(tmp_path: Path) -> None:
    (tmp_path / "traces").mkdir()
    (tmp_path / "traces" / "x.json").write_text("{")
    with pytest.raises(t.TraceInvalid) as exc:
        t.load_traces(tmp_path)
    assert exc.value.violations[0].startswith("x.json: not JSON")


# --- schema 2 (slice 1): arms, categories, adoption, stopped, spend -------------------------------


def told_identity(**over: Any) -> t.Identity:
    base: dict[str, Any] = {
        "environment": "timelike",
        "arm": "told",
        "placement": "codex: placed; opencode: placed",
        "timelike_tools": ("run", "view"),
    }
    base.update(over)
    return identity(**base)


def tool_call(
    seq: int, command: str, tools: tuple[str, ...] = (), through: tuple[str, ...] = ()
) -> t.ToolCall:
    return dataclasses.replace(call(seq), command=command, timelike_tools=tools, through_timelike=through)


@pytest.mark.parametrize(
    ("environment", "arm", "ok"),
    [
        ("vanilla", "vanilla", True),
        ("timelike", "not-told", True),
        ("timelike", "told", True),
        ("vanilla", "told", False),
        ("timelike", "vanilla", False),
    ],
)
def test_the_arm_agrees_with_the_environment(environment: str, arm: str, ok: bool) -> None:
    placement = "codex: placed" if arm == "told" else ""
    violations = t.validate(make(identity=identity(environment=environment, arm=arm, placement=placement)))
    if ok:
        assert violations == []
    else:
        assert violations == ["identity.arm: is vanilla exactly when the environment is vanilla"]


def test_an_unknown_arm_is_refused() -> None:
    assert t.validate(make(identity=identity(environment="timelike", arm="half-told"))) == [
        "identity.arm: must be one of vanilla, not-told, told"
    ]


@pytest.mark.parametrize(("arm", "placement"), [("told", ""), ("not-told", "codex: placed")])
def test_placement_is_present_exactly_when_told(arm: str, placement: str) -> None:
    ident = identity(environment="timelike", arm=arm, placement=placement)
    assert t.validate(make(identity=ident)) == ["identity.placement: non-empty exactly when the arm is told"]


def test_a_successful_call_has_no_category_and_a_failed_one_has_exactly_one() -> None:
    ok_with_category = dataclasses.replace(call(1), category="other")
    failed_without = dataclasses.replace(call(1, exit_code=2), category="")
    failed_unknown = dataclasses.replace(call(1, exit_code=2), category="flaky")
    assert t.validate(make(calls=(ok_with_category,), totals=t.derive_totals((ok_with_category,), 1))) == [
        "calls[0].category: must be empty for a call that exited 0 and did not hang"
    ]
    for bad in (failed_without, failed_unknown):
        assert t.validate(make(calls=(bad,), totals=t.derive_totals((bad,), 1))) == [
            "calls[0].category: must be one of timeout, memory-kill, command-not-found, module-not-found, "
            "network-denial, other for a failed call"
        ]


def test_the_vanilla_arm_has_no_timelike_tools() -> None:
    calls = (tool_call(1, "run make", ("run",)),)
    assert t.validate(make(calls=calls, totals=t.derive_totals(calls, 1))) == [
        "calls[0]: the vanilla arm has no timelike tools and nothing through timelike"
    ]


def test_adoption_and_categories_are_derived_from_the_calls() -> None:
    calls = (
        tool_call(1, "run make", ("run",)),
        tool_call(2, "pip install x", (), ("shim:pip",)),
        call(3, exit_code=127),
        call(4, exit_code=124, hung=True),
    )
    trace = make(identity=told_identity(), calls=calls, totals=t.derive_totals(calls, 5))
    assert t.validate(trace) == []
    assert (trace.totals.timelike_tool_calls, trace.totals.through_timelike_calls) == (1, 1)
    assert trace.totals.by_category == {"timeout": 1, "command-not-found": 1}
    data = as_dict(trace)
    data["totals"]["timelike_tool_calls"] = 2
    data["totals"]["by_category"] = {"timeout": 2}
    assert t.validate(data) == [
        "totals.timelike_tool_calls: 2 disagrees with calls (1)",
        "totals.by_category: {'timeout': 2} disagrees with calls ({'timeout': 1, 'command-not-found': 1})",
    ]


def test_list_fields_must_hold_non_empty_strings() -> None:
    data = as_dict(make(identity=told_identity()))
    data["identity"]["timelike_tools"] = ["run", ""]
    assert t.validate(data) == ["identity.timelike_tools: must be a list of non-empty str, got list"]


def test_a_stopped_run_names_its_cause_and_no_other_does() -> None:
    assert t.validate(make(ending=t.Ending("stopped", "OpenRouter answered 429"))) == [
        "ending.cause: a stopped run names one of " + ", ".join(t.STOP_CAUSES) + ", got ''"
    ]
    assert t.validate(make(ending=t.Ending("failed", "check failed: x", "turn-cap"))) == [
        "ending.cause: only a stopped run has a cause"
    ]


def test_turn_cap_zero_is_no_cap_and_negative_is_refused() -> None:
    assert t.validate(make(identity=identity(turn_cap=0))) == []
    assert t.validate(make(identity=identity(turn_cap=-1))) == [
        "identity.turn_cap: must be >= 0 (0: no cap), got -1"
    ]


def test_spend_recorded_round_trips_with_a_fractional_figure() -> None:
    spend = t.Spend(recorded=True, usd=0.1159, source="openrouter usage", unknown_generations=0)
    trace = make(spend=spend)
    assert t.validate(trace) == []
    assert t.from_json(t.to_json(trace)).spend == spend


@pytest.mark.parametrize(
    ("spend", "want"),
    [
        (
            {"recorded": True, "usd": -0.5, "source": "x", "unknown_generations": 0},
            "spend.usd: must be a number >= 0",
        ),
        (
            {"recorded": True, "usd": True, "source": "x", "unknown_generations": 0},
            "spend.usd: must be a number >= 0",
        ),
        (
            {"recorded": True, "usd": 1, "source": " ", "unknown_generations": 0},
            "spend.source: must say where",
        ),
        ({"recorded": True, "usd": 1, "source": "x"}, "spend.unknown_generations: missing"),
        (
            {"recorded": True, "usd": 1, "source": "x", "unknown_generations": 0, "est": 2},
            "spend.est: unknown key",
        ),
        ({"recorded": False}, "spend.reason: missing"),
        ({"recorded": False, "reason": "x", "usd": 0}, "spend.usd: unknown key"),
    ],
)
def test_spend_is_recorded_or_absent_never_a_stand_in(spend: dict[str, Any], want: str) -> None:
    data = as_dict(make())
    data["spend"] = spend
    assert any(v.startswith(want) for v in t.validate(data)), t.validate(data)


def test_write_trace_goes_through_the_gate(tmp_path: Path) -> None:
    from benchlib.keyfile import Gate, GateRefused

    value = "not-a-real-key-value-7f3a"
    trace = make(calls=(dataclasses.replace(call(1, exit_code=1), stderr_head=f"KEY={value}"),))
    trace = dataclasses.replace(trace, totals=t.derive_totals(trace.calls, 1))
    path = tmp_path / "traces" / "x.json"
    with pytest.raises(GateRefused) as e:
        t.write_trace(trace, path, Gate([value]))
    assert value not in str(e.value)
    assert not path.exists()
