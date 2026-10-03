"""Peer-agent isolation at the agentio level (SC-6; FR-12, FR-13; data-model.md § Session).

Two sessions run concurrently as separate processes. Each must write only its own scratch space and
event log. Isolation here is separation, not security (spec Assumption 4): peers may share a uid.
"""

from __future__ import annotations

import json
import stat
import subprocess
import sys
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from conftest import base_env

RUNS = 50

BODY = """
out = ctx.scratch() / f"out-{args.lines}.txt"
out.write_text(ctx.session)
return agentio.Result("peer", ctx.session, "ok", [str(out)], data={"artefact": str(out)})
"""


def burst(py: str, tool: Path, scratch: Path, session: str) -> list[int]:
    env = base_env(scratch, session=session)
    codes = []
    for i in range(RUNS):
        r = subprocess.run(
            [py, str(tool), "--json", "--lines", str(i)],
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=20,
            start_new_session=True,
        )
        codes.append(r.returncode)
    return codes


def test_two_concurrent_sessions_write_only_their_own_scratch_and_events(
    make_tool: Callable[..., Path], scratch: Path
) -> None:
    tool = make_tool("peer", BODY)
    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(burst, sys.executable, tool, scratch, "peer-a")
        b = pool.submit(burst, sys.executable, tool, scratch, "peer-b")
        assert a.result() == [0] * RUNS
        assert b.result() == [0] * RUNS

    for me, other in (("peer-a", "peer-b"), ("peer-b", "peer-a")):
        d = scratch / me
        assert stat.S_IMODE(d.stat().st_mode) == 0o700
        lines = (d / "events.jsonl").read_text().splitlines()
        assert len(lines) == RUNS, f"{me}: {len(lines)} events"
        events = [json.loads(x) for x in lines]  # every line parses: no interleaving
        assert {e["session"] for e in events} == {me}
        artefacts = sorted(p.name for p in d.glob("out-*.txt"))
        assert len(artefacts) == RUNS
        assert all((d / n).read_text() == me for n in artefacts)
        assert not any(other in p.read_text() for p in d.rglob("*") if p.is_file())


def test_same_session_concurrent_writers_never_interleave_lines(
    make_tool: Callable[..., Path], scratch: Path
) -> None:
    tool = make_tool("peer", BODY)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: burst(sys.executable, tool, scratch, "shared"), range(4)))
    assert all(r == [0] * RUNS for r in results)
    lines = (scratch / "shared" / "events.jsonl").read_text().splitlines()
    assert len(lines) == 4 * RUNS
    for line in lines:
        json.loads(line)


def test_session_id_cannot_escape_the_scratch_root(make_tool: Callable[..., Path], scratch: Path) -> None:
    tool = make_tool("peer", BODY)
    r = subprocess.run(
        [sys.executable, str(tool)],
        env=base_env(scratch, session="../escape"),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert r.returncode == 2
    assert not (scratch.parent / "escape").exists()
