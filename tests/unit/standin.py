"""The registry stand-in, started for a test (feature 013; tests/fixtures/registry-standin.py).

`Standin(tmp_path, catalog)` starts it on a free loopback port with the host interpreter. `.url` is its base,
`.simple` and `.npm` the two registries' roots, and `.requests()` its log. It is stopped by its own pid,
never by a process-name match.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from types import TracebackType
from typing import Any

STANDIN = Path(__file__).resolve().parents[1] / "fixtures" / "registry-standin.py"
GUARD_AGENT = "timelike-package-guard/"


class Standin:
    def __init__(self, tmp: Path, catalog: dict[str, Any], name: str = "standin") -> None:
        self.dir = tmp / name
        self.dir.mkdir(parents=True, exist_ok=True)
        cat = self.dir / "catalog.json"
        cat.write_text(json.dumps(catalog), encoding="utf-8")
        self.proc = subprocess.Popen(
            [sys.executable, "-I", str(STANDIN), "--catalog", str(cat), "--dir", str(self.dir / "run")],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=open(self.dir / "stderr", "wb"),  # noqa: SIM115 — closed with the process
            start_new_session=True,
        )
        port_file = self.dir / "run" / "port"
        deadline = time.monotonic() + 20
        while not (port_file.exists() and port_file.read_text().strip()):
            if self.proc.poll() is not None or time.monotonic() > deadline:
                err = (self.dir / "stderr").read_text(errors="replace")
                self.stop()
                raise RuntimeError(f"the registry stand-in did not start: {err}")
            time.sleep(0.05)
        self.port = int(port_file.read_text())
        self.url = f"http://127.0.0.1:{self.port}"
        self.simple = f"{self.url}/simple"
        self.npm = f"{self.url}/npm/"

    def requests(self) -> list[dict[str, Any]]:
        log = self.dir / "run" / "requests.jsonl"
        if not log.exists():
            return []
        return [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines() if x.strip()]

    def guard_requests(self) -> list[dict[str, Any]]:
        return [r for r in self.requests() if str(r.get("user_agent", "")).startswith(GUARD_AGENT)]

    def file_requests(self) -> list[dict[str, Any]]:
        """Requests for a wheel or a tarball: anything downloaded."""
        return [r for r in self.requests() if r["path"].startswith("/files/") or "/-/" in r["path"]]

    def clear(self) -> None:
        log = self.dir / "run" / "requests.jsonl"
        if log.exists():
            log.write_text("", encoding="utf-8")

    def stop(self) -> None:
        if self.proc.poll() is None:
            os.kill(self.proc.pid, signal.SIGTERM)
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.kill(self.proc.pid, signal.SIGKILL)
                self.proc.wait(timeout=10)

    def __enter__(self) -> Standin:
        return self

    def __exit__(
        self, et: type[BaseException] | None, ev: BaseException | None, tb: TracebackType | None
    ) -> None:
        self.stop()


# The catalog every guard test starts from (research R6): a package that exists and is old, one whose newest
# release is a day old (an older one is not), one yanked at its newest, and the same on npm, with a scope.
CATALOG: dict[str, Any] = {
    "pypi": {
        "tl-old": {"releases": [{"version": "1.0.0", "age_days": 400}, {"version": "1.2.0", "age_days": 300}]},
        "tl-fresh": {"releases": [{"version": "1.0.0", "age_days": 120}, {"version": "1.1.0", "age_days": 1}]},
        "tl-brandnew": {"releases": [{"version": "0.1.0", "age_days": 0.5}]},
        "tl-yanked": {
            "releases": [{"version": "1.0.0", "age_days": 200}, {"version": "2.0.0", "age_days": 100, "yanked": True}]
        },
        "tl-pre": {"releases": [{"version": "1.0.0", "age_days": 300}, {"version": "2.0.0rc1", "age_days": 1}]},
        "tl-nodates": {"releases": [{"version": "1.0.0", "age_days": 300}], "no_upload_time": True},
        "tl-slow": {"releases": [{"version": "1.0.0", "age_days": 300}], "fault": {"delay": 30}},
        "tl-broken": {"releases": [{"version": "1.0.0", "age_days": 300}], "fault": {"status": 503}},
        "tl-denied": {"releases": [{"version": "1.0.0", "age_days": 300}], "fault": {"status": 403}},
        "tl-drop": {"releases": [{"version": "1.0.0", "age_days": 300}], "fault": {"drop": True}},
    },
    "npm": {
        "tl-left": {"releases": [{"version": "1.0.0", "age_days": 400}, {"version": "1.3.0", "age_days": 300}]},
        "tl-fresh": {"releases": [{"version": "1.0.0", "age_days": 120}, {"version": "1.1.0", "age_days": 1}]},
        "@tl/scoped": {"releases": [{"version": "2.0.0", "age_days": 30}]},
        "tl-tagged": {
            "releases": [{"version": "1.0.0", "age_days": 200}, {"version": "2.0.0-beta.1", "age_days": 1}],
            "dist_tags": {"latest": "1.0.0", "next": "2.0.0-beta.1"},
        },
        "tl-notime": {"releases": [{"version": "1.0.0", "age_days": 300}], "no_time": True},
        "create-tl-app": {"releases": [{"version": "1.0.0", "age_days": 300}]},
        "tl-slow": {"releases": [{"version": "1.0.0", "age_days": 300}], "fault": {"delay": 30}},
        "tl-broken": {"releases": [{"version": "1.0.0", "age_days": 300}], "fault": {"status": 502}},
    },
}
