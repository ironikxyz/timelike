"""Units for benchlib.plan (feature 002 slice 1, FR-27 and FR-34): the dated model rule and the plan."""

from __future__ import annotations

import pytest
from benchlib import plan as p


@pytest.mark.parametrize("model", ["deepseek/deepseek-v4-pro-0813", "openai/gpt-x-20260813", "a/b-c-1234"])
def test_dated_ids_are_pins(model: str) -> None:
    assert p.model_problem(model) == ""


@pytest.mark.parametrize(
    ("model", "why"),
    [
        ("deepseek/deepseek-v4-pro", "no date suffix"),
        ("deepseek/deepseek-v4-pro-latest", "moving alias"),
        ("~openai/gpt-sol-latest", "moving alias"),
        ("deepseek-v4-pro-0813", "not a provider/name id"),
        ("deepseek/deepseek-v4-pro-813", "no date suffix"),
    ],
)
def test_moving_or_undated_ids_are_refused(model: str, why: str) -> None:
    assert why in p.model_problem(model)


def full() -> p.Plan:
    return p.Plan(
        tasks=["a", "b", "c", "d", "e"],
        harnesses=[("opencode", "1.19.0"), ("codex", "0.162.1")],
        arms=["vanilla", "not-told", "told"],
        model=p.DEFAULT_MODEL,
        caps=p.Caps(turns=30, run_s=900, spend_usd=10.0),
        price_in=1.32,
        price_out=3.96,
        price_read="2026-10-13",
    )


def test_the_full_catalog_is_thirty_runs_and_its_estimate() -> None:
    plan = full()
    assert plan.runs == 30
    assert plan.per_turn_usd == pytest.approx(0.03036)
    assert plan.estimate(8) == pytest.approx(7.2864)
    assert plan.estimate(30) == pytest.approx(27.324)


def test_the_plan_names_cells_harnesses_model_caps_and_the_estimate() -> None:
    lines = full().lines()
    text = "\n".join(lines)
    assert lines[0] == "plan: 5 tasks × 2 harnesses × 3 arms = 30 runs, n = 1 each"
    assert "harnesses: opencode 1.19.0, codex 0.162.1" in text
    assert "caps: 30 turns per run · 900 s per run · $10.00 per invocation (spend cap)" in text
    assert "model: deepseek/deepseek-v4-pro-0813 ($1.32 in, $3.96 out, per million tokens)" in text
    assert "$7.29 at 8 turns per run; $27.32 at the turn cap — the spend cap binds first" in text
    assert "never this estimate" in text
    assert (
        "basis: per run, 8 requests typical or 30 at the turn cap, each assumed 20000 input and 1000 output "
        "tokens (160000 + 8000 per typical run); prices $1.32 input and $3.96 output per million tokens, "
        "read from OpenRouter's model list on 2026-10-13"
    ) in lines


def test_the_basis_says_when_the_price_date_is_missing() -> None:
    lines = p.Plan(**{**full().__dict__, "price_read": ""}).lines()
    assert any(line.startswith("basis: ") and line.endswith("date read not recorded") for line in lines)


def test_a_standin_plan_costs_nothing() -> None:
    plan = full()
    lines = p.Plan(**{**plan.__dict__, "standin": True}).lines()
    assert "estimate: $0.00 (the stand-in charges nothing)" in lines
    assert not any(line.startswith("model: deepseek") for line in lines)
