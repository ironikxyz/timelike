"""Start-up budget (quality-standards: < 100 ms p95 per call).

Run on whatever interpreter runs the tests. On the host lane that is the host's Python, so the
figure is ADVISORY; quality-standards C2 requires the authoritative measurement inside the image
with /opt/timelike/python/bin/python3 -I (task T042), which the Docker lane runs.

It prints one machine-readable line, `TIMELIKE_STARTUP p95_ms=… runs=… python=… interpreter=…`. The
Docker lane runs pytest with `-rP`, which shows a passing test's output, and tests/run.sh copies the
line into tests/out/startup.json (task T054, operator decision: print the in-image figure).
"""

from __future__ import annotations

import os
import platform
import statistics
import subprocess
import sys
import time
from pathlib import Path

import pytest
from conftest import AGENTIO_DIR

RUNS = 50
BUDGET_MS = 100.0

PROGRAM = f"""
import sys
sys.path.insert(0, {str(AGENTIO_DIR)!r})
import agentio
agentio.run(agentio.Tool(name="probe", target="startup", summary="start-up probe"),
            lambda a, c: agentio.Result("startup", "probe", "ok"), argv=["--json"])
"""


@pytest.mark.skipif(
    "COVERAGE_PROCESS_START" in os.environ or sys.gettrace() is not None,
    reason="coverage tracing inflates start-up; the budget is measured without it",
)
def test_tool_startup_p95_under_budget(tmp_path: Path) -> None:
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "TIMELIKE_SCRATCH_ROOT": str(tmp_path)}
    samples: list[float] = []
    for _ in range(RUNS):
        t0 = time.perf_counter()
        r = subprocess.run(
            [sys.executable, "-I", "-c", PROGRAM],
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=10,
        )
        samples.append((time.perf_counter() - t0) * 1000)
        assert r.returncode == 0, r.stderr
    p95 = statistics.quantiles(samples, n=20)[-1]
    print(
        f"\nTIMELIKE_STARTUP p95_ms={p95:.1f} runs={RUNS} python={platform.python_version()} "
        f"interpreter={sys.executable}"
    )
    assert p95 < BUDGET_MS, f"p95 {p95:.1f} ms exceeds {BUDGET_MS} ms"
