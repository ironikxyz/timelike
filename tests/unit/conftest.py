"""Shared fixtures for the unit tests.

Tools are run as real subprocesses — the contract is about what a process does on its streams and
exit code, so in-process calls would prove the wrong thing. Each run has stdin at /dev/null, a new
session with no controlling terminal (setsid), a scratch root under tmp_path, and a timeout: a test
that hangs is a failure, never a wait (P2).

On the host lane, tools are run with the host interpreter plus PYTHONPATH pointing at agentio; in
the image, agentio sits in the interpreter's site-packages and tools run with `python3 -I`.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[2]
AGENTIO_DIR = REPO / "tools" / "agentio"
TOOLS_DIR = REPO / "tools" / "bin"
FIXTURES = REPO / "tests" / "fixtures"

sys.path.insert(0, str(AGENTIO_DIR))
sys.path.insert(0, str(REPO / "bench"))  # benchlib (feature 002)
sys.path.insert(0, str(Path(__file__).parent))


def base_env(scratch: Path, session: str = "test", **extra: str) -> dict[str, str]:
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(scratch.parent),
        "PYTHONPATH": str(AGENTIO_DIR),
        "TIMELIKE_SCRATCH_ROOT": str(scratch),
        "TIMELIKE_SESSION": session,
        "LC_ALL": "C.UTF-8",
        # run (003 slice 1) withholds its output when the redaction rules are unavailable (FR-39). The
        # image installs them at /etc/timelike/redaction.toml; the unit lanes run outside the agent
        # image, so every tool test reads the repository's copy, the same file the image installs.
        "TIMELIKE_REDACTION_RULES": str(REPO / "image" / "rootfs" / "etc" / "timelike" / "redaction.toml"),
    }
    if "COVERAGE_PROCESS_START" in os.environ:  # measure tools run as subprocesses (make coverage)
        env["COVERAGE_PROCESS_START"] = os.environ["COVERAGE_PROCESS_START"]
    env.update(extra)
    return env


def run(argv: list[str], env: dict[str, str], timeout: float = 20) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=timeout,
        start_new_session=True,
    )


def events(scratch: Path, session: str = "test") -> list[dict[str, Any]]:
    path = scratch / session / "events.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines()]


@pytest.fixture
def scratch(tmp_path: Path) -> Path:
    root = tmp_path / "scratch"
    return root


@pytest.fixture
def make_tool(tmp_path: Path) -> Callable[..., Path]:
    """Write a small agentio tool into tmp_path/bin and return its path."""
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)

    def _make(name: str, body: str, **tool_kwargs: Any) -> Path:
        kwargs = {"name": name, "target": "fixture", "summary": f"{name} test tool", **tool_kwargs}
        kw = ", ".join(f"{k}={v!r}" for k, v in kwargs.items())
        src = (
            textwrap.dedent(
                f"""\
            import agentio

            TOOL = agentio.Tool({kw})

            def configure(p):
                p.add_argument("--lines", type=int, default=0)
                p.add_argument("--fail", action="store_true")
                p.add_argument("--boom", action="store_true")

            def main(args, ctx):
            """
            )
            + textwrap.indent(textwrap.dedent(body), "    ")
            + textwrap.dedent(
                """
            if __name__ == "__main__":
                agentio.run(TOOL, main, configure=configure)
            """
            )
        )
        path = bindir / name
        path.write_text(src)
        path.chmod(0o755)
        return path

    return _make


@pytest.fixture
def py() -> str:
    return sys.executable
