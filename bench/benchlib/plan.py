"""plan — what a live run will do and roughly what it will cost, printed before any request (FR-27, FR-34).

A live run spends money, so its plan comes first: the cells (tasks × harnesses × arms), each harness and its
pin, the model, the caps, and an estimate. `--dry-run` prints only this.

The estimate is research RB18's: a per-turn token figure (both harnesses send a long system prompt and the
growing conversation) at the model's base price from `pins.env`. It is an estimate and says so, and it states
its basis (Item 25's ruling): the requests and tokens assumed per run, and the prices with the date they were
read, so the operator can check it against the cap. The spend the bench records is OpenRouter's own figure,
read from each response (FR-35), never this.

The model must be pinned to a dated id (FR-27): a moving alias would let the same command measure a different
model next week. Stdlib only (constitution H5).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

DEFAULT_MODEL = "deepseek/deepseek-v4-pro-0813"
TOKENS_IN_PER_TURN = 20_000
TOKENS_OUT_PER_TURN = 1_000
TYPICAL_TURNS = 8

_DATED = re.compile(r"-(\d{4}|\d{8})$")


def model_problem(model_id: str) -> str:
    """Why `model_id` is not a pin, or "" when it is one: provider/name ending in a 4- or 8-digit date."""
    if "/" not in model_id or model_id.startswith("/") or model_id.endswith("/"):
        return f"model {model_id!r} is not a provider/name id"
    if model_id.endswith("-latest") or model_id.startswith("~"):
        return f"model {model_id!r} is a moving alias; pin a dated id such as {DEFAULT_MODEL}"
    if not _DATED.search(model_id):
        return f"model {model_id!r} has no date suffix, so it is not a pin; use one such as {DEFAULT_MODEL}"
    return ""


@dataclass(frozen=True)
class Caps:
    turns: int
    run_s: int
    spend_usd: float


@dataclass(frozen=True)
class Plan:
    tasks: Sequence[str]
    harnesses: Sequence[tuple[str, str]]  # (name, pinned version)
    arms: Sequence[str]
    model: str
    caps: Caps
    price_in: float  # USD per million input tokens
    price_out: float  # USD per million output tokens
    standin: bool = False
    price_read: str = ""  # the date the prices were read (pins.env BENCH_MODEL_PRICE_READ)

    @property
    def runs(self) -> int:
        return len(self.tasks) * len(self.harnesses) * len(self.arms)

    @property
    def per_turn_usd(self) -> float:
        return (TOKENS_IN_PER_TURN * self.price_in + TOKENS_OUT_PER_TURN * self.price_out) / 1_000_000

    def estimate(self, turns: int) -> float:
        return self.runs * turns * self.per_turn_usd

    def _basis(self) -> str:
        typical_in, typical_out = TYPICAL_TURNS * TOKENS_IN_PER_TURN, TYPICAL_TURNS * TOKENS_OUT_PER_TURN
        read = (
            f"read from OpenRouter's model list on {self.price_read}"
            if self.price_read
            else "date read not recorded"
        )
        return (
            f"basis: per run, {TYPICAL_TURNS} requests typical or {self.caps.turns} at the turn cap, "
            f"each assumed {TOKENS_IN_PER_TURN} input and {TOKENS_OUT_PER_TURN} output tokens "
            f"({typical_in} + {typical_out} per typical run); "
            f"prices ${self.price_in:g} input and ${self.price_out:g} output per million tokens, {read}"
        )

    def lines(self) -> list[str]:
        harnesses = ", ".join(f"{n} {v}" for n, v in self.harnesses)
        out = [
            f"plan: {len(self.tasks)} tasks × {len(self.harnesses)} harnesses × {len(self.arms)} arms = "
            f"{self.runs} runs, n = 1 each",
            f"tasks: {', '.join(self.tasks)}",
            f"harnesses: {harnesses}",
            f"arms: {', '.join(self.arms)}",
            f"caps: {self.caps.turns} turns per run · {self.caps.run_s} s per run · "
            f"${self.caps.spend_usd:.2f} per invocation (spend cap)",
        ]
        if self.standin:
            out += [
                "model: timelike's model stand-in (scripted; no key, no request leaves the driver)",
                "estimate: $0.00 (the stand-in charges nothing)",
            ]
            return out
        typical, ceiling = self.estimate(TYPICAL_TURNS), self.estimate(self.caps.turns)
        binds = " — the spend cap binds first" if ceiling > self.caps.spend_usd else ""
        out += [
            f"model: {self.model} (${self.price_in:g} in, ${self.price_out:g} out, per million tokens)",
            f"estimate: about ${self.per_turn_usd:.3f} per turn ({TOKENS_IN_PER_TURN} in + "
            f"{TOKENS_OUT_PER_TURN} out tokens); ${typical:.2f} at {TYPICAL_TURNS} turns per run; "
            f"${ceiling:.2f} at the turn cap{binds}",
            self._basis(),
            "spend recorded is OpenRouter's own figure from each response, never this estimate",
        ]
        return out
