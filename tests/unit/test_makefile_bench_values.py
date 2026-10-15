"""The Makefile's bench values (maint-lane-speed item 3): the environment outranks pins.env.

`include pins.env` used to override the environment, so `BENCH_MODEL=… make bench-live` measured the pinned
model and dropped the value without a word (02 slice 1's live run, 2026-10-14). The Makefile now notes the
environment's values before the include and puts them back after it, and records each one's source in
BENCH_<NAME>_SOURCE for the bench's plan. These run the real Makefile through GNU make with `--eval`, which
adds a target that prints the values and starts nothing else. They need make on PATH: the host lane has it,
the agent image (the Docker lane's unit step) does not, and there they are skipped, saying so.
"""

from __future__ import annotations

import os
import shutil
import subprocess

import pytest
from conftest import REPO

MAKE = shutil.which("make")
pytestmark = pytest.mark.skipif(MAKE is None, reason="GNU make is not on PATH (the agent image has none)")

NAMES = ("BENCH_MODEL", "BENCH_MODEL_PRICE_IN", "BENCH_MODEL_PRICE_OUT", "BENCH_MODEL_PRICE_READ")
SHOW = "show-bench-values: ; @" + " ".join(f'echo "{n}=$({n})|$({n}_SOURCE)";' for n in NAMES)


def pinned(name: str) -> str:
    for line in (REPO / "pins.env").read_text().splitlines():
        if line.startswith(f"{name}="):
            return line.split("=", 1)[1]
    raise AssertionError(f"pins.env has no {name}")


def values(env: dict[str, str], *make_args: str) -> dict[str, tuple[str, str]]:
    base = {k: v for k, v in os.environ.items() if k not in NAMES and not k.startswith("BENCH_")}
    p = subprocess.run(
        [str(MAKE), "-s", "-C", str(REPO), *make_args, "--eval", SHOW, "show-bench-values"],
        env={**base, **env}, capture_output=True, text=True, timeout=60,
    )  # fmt: skip
    assert p.returncode == 0, p.stderr
    out = {}
    for line in p.stdout.splitlines():
        name, rest = line.split("=", 1)
        value, source = rest.rsplit("|", 1)
        out[name] = (value, source)
    return out


def test_unset_in_the_environment_the_pins_apply() -> None:
    got = values({})
    assert got == {n: (pinned(n), "pins.env") for n in NAMES}


def test_the_environment_outranks_pins_env() -> None:
    got = values({"BENCH_MODEL": "deepseek/deepseek-v4-flash-0731", "BENCH_MODEL_PRICE_IN": "0.27"})
    assert got["BENCH_MODEL"] == ("deepseek/deepseek-v4-flash-0731", "the environment")
    assert got["BENCH_MODEL_PRICE_IN"] == ("0.27", "the environment")
    assert got["BENCH_MODEL_PRICE_OUT"] == (pinned("BENCH_MODEL_PRICE_OUT"), "pins.env")


def test_an_empty_environment_value_counts_as_unset() -> None:
    assert values({"BENCH_MODEL": ""})["BENCH_MODEL"] == (pinned("BENCH_MODEL"), "pins.env")


def test_a_make_command_line_value_still_wins() -> None:
    got = values({"BENCH_MODEL": "a/from-env-0101"}, "BENCH_MODEL=a/from-cli-0202")
    assert got["BENCH_MODEL"] == ("a/from-cli-0202", "the make command line")
