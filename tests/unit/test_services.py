"""services (feature 010, slice 1, T001) against contracts/services-cli.md, data-model.md, research R1-R8.

Written from the contract alone, before the tool. Every fixture is a real process (P005):
- `python3 -m http.server PORT --bind 127.0.0.1` on a free port found by binding port 0;
- `sh -c` trees whose background child escapes with `setsid` (a grandchild in its own session);
- commands that exit early, and `sleep 300` waiting on a closed port.

Every claim is checked against the state it claims (P004), never against the verdict alone: the port
accepts a connection or not, the pids are alive or gone in /proc (a zombie counts as gone), the marker
`TIMELIKE_SERVICE=<session>/<name>/<instance>` is an exact entry of /proc/<pid>/environ, the registry
file's JSON, the log's contents.

Hygiene: each test's sessions carry the test's own tag, and the `lab` fixture SIGKILLs, at teardown and
even on failure, every process whose marker names one of those sessions, plus any listener the test
started itself. Secrets are generated at run time (test_agentio_redaction's generators); none is a literal.

Ambiguities settled here (the contract is the authority; the report lists them):
- Global flags (`--text`, `--json`) are placed before the subcommand; JSON is the piped default and
  is otherwise not asked for.
- The registry's top level is data-model's `{"v": 1, "services": {name: entry}}`.
- A start that died keeps its registry entry with its exit (R5: "a died entry stays until it is stopped
  or started again"); a start refused or not found registers nothing (spec edge cases).
- A start that timed out without `--keep` is checked for its processes only, not for its entry, which
  the contract does not pin.
- An invalid name is refused with exit 1 or 2 (FR-4 gives the pattern, not the exit).
- The session event's `ref` kind is not pinned: its value is the log path.
- `uptime_s` is read as a number; the test waits past one second so an integer is above 0 too.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import secrets
import shlex
import signal
import socket
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from conftest import TOOLS_DIR, base_env, events
from test_agentio_redaction import gh

SERVICES = TOOLS_DIR / "services"
MARKER = "TIMELIKE_SERVICE"
Proc = subprocess.CompletedProcess[str]

pytestmark = pytest.mark.skipif(not SERVICES.exists(), reason="tools/bin/services is not written yet (T003)")


# ── /proc and the port ────────────────────────────────────────────────────────────────────────────


def stat_of(pid: int) -> tuple[str, int, int] | None:
    """(state, pgrp, session) from /proc/<pid>/stat, or None when the pid is gone."""
    try:
        raw = Path(f"/proc/{pid}/stat").read_text(errors="replace")
    except OSError:
        return None
    fields = raw[raw.rfind(")") + 2 :].split()
    return fields[0], int(fields[2]), int(fields[3])


def alive(pid: int) -> bool:
    """A pid that exists and is not a zombie (a zombie counts as gone)."""
    st = stat_of(pid)
    return st is not None and st[0] != "Z"


def environ(pid: int) -> list[str]:
    try:
        return Path(f"/proc/{pid}/environ").read_bytes().decode(errors="replace").split("\0")
    except OSError:
        return []


def marked(match: Callable[[str], bool]) -> dict[int, str]:
    """Live processes whose environ carries a marker value accepted by `match`: {pid: value}."""
    found: dict[int, str] = {}
    for name in os.listdir("/proc"):
        if not name.isdigit() or int(name) == os.getpid():
            continue
        for entry in environ(int(name)):
            if entry.startswith(f"{MARKER}=") and match(entry.split("=", 1)[1]):
                if alive(int(name)):
                    found[int(name)] = entry.split("=", 1)[1]
                break
    return found


def service_pids(session: str, name: str) -> dict[int, str]:
    return marked(lambda v: v.startswith(f"{session}/{name}/"))


def accepts(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), 0.5):
            return True
    except OSError:
        return False


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port: int = s.getsockname()[1]
        return port


def wait_until(pred: Callable[[], bool], timeout: float = 10.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if pred():
            return True
        time.sleep(0.05)
    return pred()


def http(port: int) -> list[str]:
    return ["python3", "-m", "http.server", str(port), "--bind", "127.0.0.1"]


def tree(port: int) -> list[str]:
    """A server whose shell first spawns a `setsid` escapee: the grandchild leaves the group (R1)."""
    return ["sh", "-c", f"setsid sh -c 'sleep 300' & exec python3 -m http.server {port} --bind 127.0.0.1"]


# ── the lab: a scratch root, a workspace, and sessions tagged per test ───────────────────────────


@dataclass
class Lab:
    tmp: Path
    scratch: Path  # TIMELIKE_SCRATCH_ROOT
    ws: Path  # every call's working directory
    tag: str
    listeners: list[subprocess.Popen[bytes]] = field(default_factory=list)

    def session(self, name: str = "a") -> str:
        return f"{name}-{self.tag}"

    def env(self, session: str, **extra: str) -> dict[str, str]:
        return base_env(self.scratch, session, COLUMNS="1000", **extra)

    def svc(self, *args: str, session: str | None = None, timeout: float = 40, **extra: str) -> Proc:
        return subprocess.run(
            [sys.executable, str(SERVICES), *args],
            cwd=str(self.ws),
            env=self.env(session or self.session(), **extra),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=timeout,
            start_new_session=True,
        )

    def registry_path(self, session: str | None = None) -> Path:
        return self.scratch / (session or self.session()) / "services" / "registry.json"

    def registry(self, session: str | None = None) -> dict[str, Any]:
        path = self.registry_path(session)
        if not path.exists():
            return {}
        entries: dict[str, Any] = json.loads(path.read_text())["services"]
        return entries

    def listen(self, port: int) -> subprocess.Popen[bytes]:
        """An unregistered listener the test owns: no marker, killed at teardown."""
        p = subprocess.Popen(
            [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
            cwd=str(self.ws),
            env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        self.listeners.append(p)
        assert wait_until(lambda: accepts(port)), "the test's own listener never accepted"
        return p

    def ours(self) -> dict[int, str]:
        return marked(lambda v: v.split("/", 1)[0].endswith(f"-{self.tag}"))


@pytest.fixture
def lab(tmp_path: Path) -> Iterator[Lab]:
    tmp = Path(os.path.realpath(tmp_path))
    lab = Lab(tmp, tmp / "scratch", tmp / "ws", secrets.token_hex(4))
    lab.ws.mkdir()
    try:
        yield lab
    finally:
        for p in lab.listeners:
            with contextlib.suppress(OSError):
                p.kill()
            with contextlib.suppress(subprocess.TimeoutExpired):
                p.wait(timeout=5)
        for _ in range(3):  # a fork between scan and kill is caught by the next round
            for pid in lab.ours():
                with contextlib.suppress(ProcessLookupError, PermissionError):
                    os.kill(pid, signal.SIGKILL)
            if wait_until(lambda: not lab.ours(), timeout=2):
                break


# ── reading results ──────────────────────────────────────────────────────────────────────────────


def said(r: Proc) -> str:
    return f"exit {r.returncode}\nstdout: {r.stdout}\nstderr: {r.stderr}"


def doc_of(r: Proc) -> dict[str, Any]:
    try:
        d: dict[str, Any] = json.loads(r.stdout)
    except ValueError:
        raise AssertionError(f"stdout is not one JSON object:\n{said(r)}") from None
    return d


def result(r: Proc, code: int, scope: str | None = None) -> dict[str, Any]:
    assert r.returncode == code, said(r)
    d = doc_of(r)
    assert d["tool"] == "services", d
    if code != 4:
        assert d["exit"] == code, d
    if scope is not None:
        assert d["scope"] == scope, d
    return d


def flat(value: Any) -> list[int]:
    """Pids as a list, or keyed by service name (the contract names `pids`, not its shape)."""
    if not value:
        return []
    if isinstance(value, dict):
        return [p for pids in value.values() for p in flat(pids)]
    return list(value)


def died_exit(d: dict[str, Any]) -> Any:
    """The contract's data `exit` (died) is agentio's reserved top-level key, so the tool carries it
    under another name; accept `exit_status` or `command_exit`."""
    return d.get("exit_status", d.get("command_exit"))


def start(lab: Lab, name: str, cmd: list[str], *opts: str, session: str | None = None, **env: str) -> Proc:
    return lab.svc("start", name, *opts, "--", *cmd, session=session, **env)


def started(lab: Lab, name: str, cmd: list[str], *opts: str, session: str | None = None) -> dict[str, Any]:
    """A start that must succeed (ready or started)."""
    r = start(lab, name, cmd, *opts, session=session)
    assert r.returncode == 0, said(r)
    return doc_of(r)


# ── start: ready by port (SC-1) ──────────────────────────────────────────────────────────────────


def test_start_ready_by_port_names_name_pid_port_log_and_the_port_answers(lab: Lab) -> None:
    s, port = lab.session(), free_port()
    assert not accepts(port)
    r = start(lab, "web", http(port), "--port", str(port))
    d = result(r, 0, "ready")
    assert accepts(port), "start returned ready while the port did not accept"  # checked at once
    pid, log = d["pid"], d["log"]
    assert d["name"] == "web" and d["session"] == s and d["port"] == port and d["ready"] == "port"
    assert isinstance(pid, int) and alive(pid)
    v = d["verdict"]
    assert v.startswith(f"web ready: pid {pid}, port {port} accepting, log {log}"), v
    assert f"registered in session {s}" in v and "rule 10" in v
    # the log is the session scratch's, beside the registry
    assert Path(log) == lab.scratch / s / "services" / "web.log" and Path(log).exists()
    # the marker: exact NAME=VALUE in the first process's environ, with the registry's instance
    entry = lab.registry()["web"]
    assert entry["pid"] == pid and entry["port"] == port and entry["log"] == log
    assert entry["ready"] == "port" and entry["command"] == http(port)
    assert f"{MARKER}={s}/web/{entry['instance']}" in environ(pid)
    # FR-1: a new session (process group), whose group the registry records
    st = stat_of(pid)
    assert st is not None and st[1] == d["pgid"] == entry["pgid"] and st[2] == pid
    assert lab.registry_path().stat().st_mode & 0o777 == 0o600
    # one session event per call, pointing at the log
    evs = events(lab.scratch, s)
    assert len(evs) == 1 and evs[0]["tool"] == "services" and evs[0]["exit"] == 0
    assert log in evs[0].get("ref", {}).values(), evs[0]


def test_start_ready_text_verdict(lab: Lab) -> None:
    port = free_port()
    r = lab.svc("--text", "start", "web", "--port", str(port), "--", *http(port))
    assert r.returncode == 0, said(r)
    out = r.stdout.splitlines()
    assert out[0].startswith("services: ") and out[0].endswith("[ready]"), out
    pid = next(iter(service_pids(lab.session(), "web")))
    assert out[1].startswith(f"verdict: web ready: pid {pid}, port {port} accepting, log "), out
    assert accepts(port)


def test_start_ready_by_log_line_waits_for_the_line(lab: Lab) -> None:
    cmd = ["sh", "-c", "sleep 0.5; echo listening now; exec sleep 300"]
    d = result(start(lab, "app", cmd, "--ready-log", "listening"), 0, "ready")
    assert d["ready"] == "log"
    assert "log line matched /listening/" in d["verdict"], d["verdict"]
    assert d["verdict"].startswith(f"app ready: pid {d['pid']}, ")
    assert "listening now" in Path(d["log"]).read_text()  # the line it claims is in the log
    assert d["seconds"] >= 0.4  # it waited for the line, not for the process
    assert alive(d["pid"]) and d["pid"] in service_pids(lab.session(), "app")


def test_start_without_a_condition_is_started_not_ready(lab: Lab) -> None:
    d = result(start(lab, "idle", ["sleep", "300"]), 0, "started")
    assert d["ready"] == "none"
    assert d["verdict"].startswith(f"idle started: pid {d['pid']}, readiness not checked"), d["verdict"]
    assert alive(d["pid"]) and d["pid"] in service_pids(lab.session(), "idle")
    assert lab.registry()["idle"]["ready"] == "none"


# ── start: died before ready (SC-2) ──────────────────────────────────────────────────────────────


def test_start_that_dies_first_exits_1_with_its_status_and_redacted_tail(lab: Lab) -> None:
    port, token = free_port(), gh("p")
    cmd = ["sh", "-c", 'echo first; echo "token=$SVC_SECRET"; echo boom >&2; exit 3']
    r = start(lab, "bad", cmd, "--port", str(port), SVC_SECRET=token)
    d = result(r, 1, "died")
    assert died_exit(d) == 3
    v = d["verdict"]
    assert v.startswith("bad died before ready (exit 3) after "), v
    assert d["tail"] == ["first", "token=[REDACTED:token]", "boom"]
    assert d["lines"][:3] == d["tail"]
    assert token not in r.stdout and token not in r.stderr
    assert "services logs bad" in r.stdout  # do instead
    assert "boom" in Path(d["log"]).read_text()  # the tail is the log's
    assert not service_pids(lab.session(), "bad") and not accepts(port)
    entry = lab.registry()["bad"]  # R5: a died entry stays, so list can mark it
    assert entry["exit"] == 3
    assert "; last 3 log lines below" in v  # the contract's wording, checked last


# ── start: not ready in time (exit 124) ──────────────────────────────────────────────────────────


def test_start_not_ready_in_time_is_124_and_stopped(lab: Lab) -> None:
    port = free_port()
    cmd = ["sh", "-c", "echo waiting; exec sleep 300"]
    r = start(lab, "slow", cmd, "--port", str(port), "--timeout", "1")
    d = result(r, 124, "not ready")
    v = d["verdict"]
    assert v.startswith("slow not ready after 1"), v
    assert f"port {port} not accepting" in v and "stopped" in v and "--keep" in v
    assert "waiting" in d["tail"]
    assert "services logs slow" in r.stdout
    assert not alive(d["pid"]), "the timed-out service was left running"
    assert not service_pids(lab.session(), "slow")


def test_start_not_ready_with_keep_leaves_it_running_and_listed(lab: Lab) -> None:
    port = free_port()
    r = start(lab, "slow", ["sleep", "300"], "--port", str(port), "--timeout", "1", "--keep")
    d = result(r, 124, "not ready")
    pid = d["pid"]
    assert alive(pid) and pid in service_pids(lab.session(), "slow")
    ls = result(lab.svc("list"), 0)
    rows = {e["name"]: e for e in ls["services"]}
    assert rows["slow"]["state"] == "running" and rows["slow"]["pid"] == pid
    result(lab.svc("stop", "slow"), 0, "stopped")
    assert not alive(pid)


# ── start: refused (SC-3, FR-3, FR-4) ────────────────────────────────────────────────────────────


def test_port_held_by_a_registered_service_is_refused_naming_it(lab: Lab) -> None:
    s, port = lab.session(), free_port()
    web = started(lab, "web", http(port), "--port", str(port))
    r = start(lab, "web2", http(port), "--port", str(port))
    d = result(r, 1, "refused")
    assert (
        d["verdict"]
        == f"port {port} is held by service web in session {s}, pid {web['pid']}; nothing started"
    )
    assert d["holder"] == {"name": "web", "session": s, "pid": web["pid"]}
    assert not service_pids(s, "web2") and "web2" not in lab.registry()
    assert accepts(port) and alive(web["pid"])


def test_port_held_by_another_sessions_service_is_refused_naming_its_session(lab: Lab) -> None:
    other, port = lab.session("b"), free_port()
    web = started(lab, "web", http(port), "--port", str(port), session=other)
    d = result(start(lab, "mine", http(port), "--port", str(port)), 1, "refused")
    assert f"held by service web in session {other}, pid {web['pid']}" in d["verdict"]
    assert d["holder"] == {"name": "web", "session": other, "pid": web["pid"]}
    assert not service_pids(lab.session(), "mine") and "mine" not in lab.registry()


def test_port_held_by_an_unregistered_listener_is_refused_naming_its_pid(lab: Lab) -> None:
    port = free_port()
    holder = lab.listen(port)
    d = result(start(lab, "x", http(port), "--port", str(port)), 1, "refused")
    assert d["verdict"].startswith(f"port {port} is held by pid {holder.pid} ("), d["verdict"]
    assert d["verdict"].endswith("; nothing started")
    assert d["holder"]["pid"] == holder.pid and "http.server" in d["holder"]["command"]
    assert not service_pids(lab.session(), "x") and "x" not in lab.registry()
    assert holder.poll() is None  # the holder is left alone


def test_a_live_name_is_refused_naming_its_pid(lab: Lab) -> None:
    s = lab.session()
    first = started(lab, "web", ["sleep", "300"])
    d = result(start(lab, "web", ["sleep", "301"]), 1, "refused")
    v = d["verdict"]
    assert (
        v == f"web is already running in session {s} (pid {first['pid']}); stop it first or use another name"
    )
    assert list(service_pids(s, "web")) == [first["pid"]]  # nothing else started under the name
    assert lab.registry()["web"]["pid"] == first["pid"]


def test_a_command_not_found_is_refused_and_nothing_registered(lab: Lab) -> None:
    missing = "no-such-command-" + lab.tag
    d = result(start(lab, "ghost", [missing]), 1, "refused")
    assert d["verdict"].startswith("cannot start ghost: ") and "not found" in d["verdict"], d["verdict"]
    assert "ghost" not in lab.registry() and not service_pids(lab.session(), "ghost")


def test_a_command_not_executable_is_refused_and_nothing_registered(lab: Lab) -> None:
    script = lab.ws / "plain.sh"
    script.write_text("#!/bin/sh\nsleep 300\n")
    script.chmod(0o644)
    d = result(start(lab, "ghost", [str(script)]), 1, "refused")
    assert d["verdict"].startswith("cannot start ghost: ") and "not executable" in d["verdict"]
    assert "ghost" not in lab.registry() and not service_pids(lab.session(), "ghost")


def test_start_without_a_command_is_usage(lab: Lab) -> None:
    r = lab.svc("start", "web", "--port", str(free_port()))
    assert r.returncode == 2, said(r)
    assert "web" not in lab.registry()


def test_an_invalid_name_is_refused_and_nothing_started(lab: Lab) -> None:
    r = start(lab, "../escape", ["sleep", "300"])
    assert r.returncode in (1, 2), said(r)
    assert not lab.ours()
    assert (
        not (lab.scratch / "escape.log").exists()
        and not (lab.scratch / lab.session() / "escape.log").exists()
    )


# ── stop (SC-4, FR-5, FR-6) ──────────────────────────────────────────────────────────────────────


def tree_up(lab: Lab, name: str, port: int, session: str | None = None) -> tuple[dict[str, Any], set[int]]:
    """Start the setsid tree and wait for its escapee; return the start's data and every marker pid."""
    s = session or lab.session()
    d = started(lab, name, tree(port), "--port", str(port), session=s)

    def escaped() -> bool:
        sid = stat_of(d["pid"])
        return sid is not None and any(
            (st := stat_of(p)) is not None and st[2] != sid[2] for p in service_pids(s, name)
        )

    assert wait_until(escaped), "the fixture's setsid grandchild never appeared"
    pids = set(service_pids(s, name))
    assert d["pid"] in pids and len(pids) >= 2
    return d, pids


def test_stop_ends_the_whole_tree_including_the_setsid_escapee(lab: Lab) -> None:
    port = free_port()
    d0, pids = tree_up(lab, "web", port)
    r = lab.svc("stop", "web")
    d = result(r, 0, "stopped")
    # the claim, checked in /proc at once: none of the tree remains
    assert not [p for p in pids if alive(p)], "processes of the tree survived the stop"
    assert not service_pids(lab.session(), "web")
    assert not accepts(port)
    assert pids <= set(flat(d["pids"])), (pids, d["pids"])
    assert flat(d["survivors"]) == []
    v = d["verdict"]
    assert v.startswith(f"web stopped: {len(flat(d['pids']))} processes (") and "none remains" in v, v
    for p in pids:
        assert str(p) in v
    # the restart command starts the same service again
    restart = d["restart"]["web"] if isinstance(d["restart"], dict) else d["restart"]  # shape not pinned
    assert v.endswith(f"start again: {restart}")
    argv = shlex.split(restart)
    assert argv[:3] == ["services", "start", "web"]
    assert argv[argv.index("--port") + 1] == str(port)
    assert argv[argv.index("--") + 1 :] == tree(port)
    assert "web" not in lab.registry()
    assert d0["log"] in [str(x) for x in events(lab.scratch, lab.session())[-1].get("ref", {}).values()]


def test_stop_dry_run_signals_nothing(lab: Lab) -> None:
    port = free_port()
    _, pids = tree_up(lab, "web", port)
    r = lab.svc("stop", "web", "--dry-run")
    d = result(r, 0, "dry run")
    v = d["verdict"]
    assert v.startswith("would stop web: ") and v.endswith("nothing signalled"), v
    for p in pids:
        assert str(p) in r.stdout
    assert all(alive(p) for p in pids), "a dry run signalled a process"
    assert accepts(port)
    assert "web" in lab.registry()


def test_stop_of_another_sessions_service_needs_yes(lab: Lab) -> None:
    other = lab.session("b")
    web = started(lab, "web", ["sleep", "300"], session=other)
    r = lab.svc("stop", "web", "--session", other)
    assert r.returncode == 4, said(r)
    env = doc_of(r)
    assert env["status"] == "confirmation_required"
    assert env["confirm"].endswith("--yes")
    assert any("web" in line and str(web["pid"]) in line for line in env["plan"]), env["plan"]
    assert alive(web["pid"]), "the unconfirmed stop signalled the service"
    assert "web" in lab.registry(other)
    # the confirm command, run as given, stops it
    confirm = shlex.split(env["confirm"])
    assert confirm[0] == "services"
    d = result(lab.svc(*confirm[1:]), 0, "stopped")
    assert not alive(web["pid"]) and not service_pids(other, "web")
    assert "web" not in lab.registry(other)
    assert web["pid"] in flat(d["pids"])


def test_stop_all_needs_yes_and_stops_only_this_session(lab: Lab) -> None:
    s, other = lab.session(), lab.session("b")
    one = started(lab, "one", ["sleep", "300"])
    two = started(lab, "two", ["sleep", "300"])
    theirs = started(lab, "one", ["sleep", "300"], session=other)
    r = lab.svc("stop", "--all")
    assert r.returncode == 4, said(r)
    env = doc_of(r)
    assert env["status"] == "confirmation_required" and env["confirm"].endswith("--yes")
    plan = "\n".join(env["plan"])
    assert "one" in plan and "two" in plan and str(one["pid"]) in plan and str(two["pid"]) in plan
    assert alive(one["pid"]) and alive(two["pid"]) and alive(theirs["pid"])
    result(lab.svc("stop", "--all", "--yes"), 0)
    assert not service_pids(s, "one") and not service_pids(s, "two")
    assert not alive(one["pid"]) and not alive(two["pid"])
    assert alive(theirs["pid"]), "stop --all reached another session"
    assert "one" not in lab.registry() and "two" not in lab.registry()
    assert "one" in lab.registry(other)


def test_stop_of_a_service_that_died_at_start_says_it_had_ended(lab: Lab) -> None:
    result(start(lab, "bad", ["sh", "-c", "exit 3"], "--port", str(free_port())), 1, "died")
    d = result(lab.svc("stop", "bad"), 0, "stopped")
    assert d["verdict"] == "bad had already ended (exit 3); entry removed"
    assert "bad" not in lab.registry()


def test_stop_of_a_service_that_died_after_ready_says_it_had_ended(lab: Lab) -> None:
    d0 = started(lab, "brief", ["sh", "-c", "echo up; sleep 0.3"], "--ready-log", "up")
    assert wait_until(lambda: not service_pids(lab.session(), "brief"))
    d = result(lab.svc("stop", "brief"), 0, "stopped")
    assert d["verdict"].startswith("brief had already ended") and d["verdict"].endswith("entry removed")
    assert "brief" not in lab.registry() and not alive(d0["pid"])


def test_stop_and_logs_of_no_such_service_are_exit_3(lab: Lab) -> None:
    s = lab.session()
    r = lab.svc("stop", "nope")
    d = result(r, 3, "not found")
    assert d["verdict"] == f"no service nope in session {s}"
    assert "services list" in r.stdout
    assert lab.svc("logs", "nope").returncode == 3


# ── list (SC-5, FR-8) ────────────────────────────────────────────────────────────────────────────


def test_list_shows_running_with_port_pid_uptime_and_marks_the_dead(lab: Lab) -> None:
    s, port, port2 = lab.session(), free_port(), free_port()
    web = started(lab, "web", http(port), "--port", str(port))
    t0 = time.monotonic()
    result(start(lab, "bad", ["sh", "-c", "echo boom >&2; exit 3"], "--port", str(port2)), 1, "died")
    brief = started(lab, "brief", ["sh", "-c", "echo up; sleep 0.3"], "--ready-log", "up")
    assert wait_until(lambda: not alive(brief["pid"]) and not service_pids(s, "brief"))
    wait_until(lambda: time.monotonic() - t0 > 1.1, timeout=2)  # uptime above a second

    d = result(lab.svc("list"), 0)
    rows = {e["name"]: e for e in d["services"]}
    assert set(rows) == {"web", "bad", "brief"}
    w = rows["web"]
    assert w["state"] == "running" and w["port"] == port and w["pid"] == web["pid"] and w["session"] == s
    assert w["uptime_s"] > 0 and w["log"] == web["log"]
    assert alive(web["pid"]) and accepts(port)  # what "running" claims
    assert rows["bad"]["state"] == "died" and rows["bad"]["exit"] == 3 and rows["bad"]["port"] == port2
    assert rows["brief"]["state"] == "died"  # its process has gone since it was started
    v = d["verdict"]
    assert v.startswith(f"3 services in session {s}: ") and "1 running" in v and "2 died" in v, v

    t = lab.svc("--text", "list")
    assert t.returncode == 0, said(t)
    lines = t.stdout.splitlines()
    assert re.match(
        rf"^web\s+running\s+port {port}\s+pid {web['pid']}\s+up \d",
        next(x for x in lines if x.startswith("web")),
    ), lines
    assert re.match(
        rf"^bad\s+died\s+port {port2}\s+exit 3\b", next(x for x in lines if x.startswith("bad"))
    ), lines
    assert re.match(r"^brief\s+died\b", next(x for x in lines if x.startswith("brief"))), lines


def test_list_names_a_marker_process_whose_entry_was_cleared_as_unlisted(lab: Lab) -> None:
    s = lab.session()
    d0 = started(lab, "orphan", ["sleep", "300"])
    lab.registry_path().unlink()  # the scratch's records cleared under a running service (seam 2)
    assert alive(d0["pid"])
    d = result(lab.svc("list"), 0)
    rows = [e for e in d["services"] if e["state"] == "unlisted"]
    assert len(rows) == 1, d["services"]
    assert rows[0]["name"] == "orphan" and rows[0]["pid"] == d0["pid"] and rows[0]["session"] == s
    assert "1 unlisted" in d["verdict"]
    t = lab.svc("--text", "list")
    assert any(re.match(rf"^orphan\s+unlisted\b.*\b{d0['pid']}\b", x) for x in t.stdout.splitlines()), (
        t.stdout
    )


# ── logs (FR-9, rule 15) ─────────────────────────────────────────────────────────────────────────


def test_logs_tail_and_redaction(lab: Lab) -> None:
    token = gh("p")
    cmd = ["sh", "-c", 'i=1; while [ $i -le 30 ]; do echo line$i; i=$((i+1)); done; '
           'echo "token=$SVC_SECRET"; echo ready; exec sleep 300']  # fmt: skip
    r0 = start(lab, "talk", cmd, "--ready-log", "^ready$", SVC_SECRET=token)
    assert r0.returncode == 0, said(r0)
    raw = Path(doc_of(r0)["log"]).read_text().splitlines()
    assert raw[-1] == "ready" and len(raw) == 32

    r = lab.svc("logs", "talk", "-n", "5")
    d = result(r, 0)
    assert d["lines"] == ["line28", "line29", "line30", "token=[REDACTED:token]", "ready"]
    assert token not in r.stdout and token not in r.stderr

    full = result(lab.svc("logs", "talk"), 0)  # default 50: all 32 lines
    assert full["lines"][0] == "line1" and len(full["lines"]) == 32
    assert token not in json.dumps(full)

    other = result(
        lab.svc("logs", "talk", "-n", "1", "--session", lab.session(), session=lab.session("b")), 0
    )
    assert other["lines"] == ["ready"]


# ── the registry under concurrent starts (R5) ───────────────────────────────────────────────────


def test_concurrent_starts_in_one_session_lose_no_entry(lab: Lab) -> None:
    s, names = lab.session(), ["c1", "c2", "c3", "c4"]
    procs = [
        subprocess.Popen(
            [sys.executable, str(SERVICES), "start", n, "--", "sleep", "300"],
            cwd=str(lab.ws),
            env=lab.env(s),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        for n in names
    ]
    docs = []
    for p in procs:
        out, err = p.communicate(timeout=40)
        assert p.returncode == 0, f"exit {p.returncode}\n{out}\n{err}"
        docs.append(json.loads(out))
    reg = lab.registry()
    assert set(names) <= set(reg), sorted(reg)
    for n, d in zip(names, docs, strict=True):
        assert reg[n]["pid"] == d["pid"] and alive(d["pid"])
        assert f"{MARKER}={s}/{n}/{reg[n]['instance']}" in environ(d["pid"])
    assert len({reg[n]["instance"] for n in names}) == len(names)


# ── the manifest (FR-10, FR-11) ──────────────────────────────────────────────────────────────────


def test_agent_info(lab: Lab) -> None:
    r = lab.svc("--agent-info")
    assert r.returncode == 0, said(r)
    m = doc_of(r)
    assert m["mutating"] is True and m["confirm_protocol"] is True
    assert m["destructive"] is True and m["dry_run"] is True and m["reads_stdin"] is False
    assert m["envelopes"] == ["confirmation_required"] and m["probe"] == ["list"]
    assert set(m["exit_codes"]) == {"0", "1", "2", "3", "4", "124"}
    assert m["ready_timeout_s"] == 60 and m["log_tail"] == 20 and m["marker"] == MARKER
    assert m["registry"].endswith("services/registry.json")
    assert "--dry-run" in m["flags"] and "--yes" in m["flags"]
    assert not lab.ours()


def test_the_probe_runs_clean_on_an_empty_session(lab: Lab) -> None:
    d = result(lab.svc("list"), 0)
    assert d["services"] == []


# ── T005: the paths the delegate's set did not reach (coverage), each against real processes ─────


@pytest.mark.parametrize(
    ("args", "words"),
    [
        ([], "needs an action"),
        (["restart", "web"], "unknown action"),
        (["list", "--", "x"], "belong to start"),
        (["logs", "bad name"], "not a service name"),
        (["logs", "web", "--session", "bad session"], "not a session id"),
        (["start", "web", "--port", "70000", "--", "true"], "is not a port"),
        (["start", "web", "--ready-log", "(", "--", "true"], "not a regular expression"),
        (["start", "web", "--timeout", "0", "--", "true"], "must be above 0"),
        (["stop"], "stop needs NAME"),
        (["stop", "web", "--all"], "--all stops every service"),
        (["logs"], "logs needs NAME"),
    ],
)
def test_usage_errors_exit_2(lab: Lab, args: list[str], words: str) -> None:
    r = lab.svc("--json", *args)
    assert r.returncode == 2, said(r)
    assert words in r.stderr, said(r)


def test_a_service_that_ignores_sigterm_is_frozen_and_killed(lab: Lab) -> None:
    """run's sweep past the grace: TERM ignored, so freeze, KILL, re-scan; nothing remains."""
    port = free_port()
    cmd = ["sh", "-c", f"trap '' TERM; {shlex.join(http(port))} & trap '' TERM; wait"]
    d = started(lab, "stubborn", cmd, "--port", str(port))
    pids = set(service_pids(lab.session(), "stubborn"))
    assert pids
    began = time.monotonic()
    r = lab.svc("--json", "stop", "stubborn")
    took = time.monotonic() - began
    assert r.returncode == 0, said(r)
    assert took >= 1.5, took  # the 2 s grace ran out before the KILL
    assert not any(alive(p) for p in pids)
    assert not accepts(port)
    assert d["pid"] in flat(doc_of(r)["pids"])


def test_a_start_killed_by_a_signal_names_it(lab: Lab) -> None:
    r = start(lab, "selfkill", ["sh", "-c", "echo going; kill -9 $$"], "--port", str(free_port()))
    d = result(r, 1, "died")
    assert "killed by SIGKILL" in d["verdict"], d["verdict"]
    assert d["signal"] == "SIGKILL"


def test_logs_longer_than_n_are_cut_with_the_full_log_as_output(lab: Lab) -> None:
    lines = "; ".join(f"echo line{i}" for i in range(30))
    started(lab, "chatty", ["sh", "-c", f"{lines}; exec sleep 300"])
    assert wait_until(lambda: "line29" in Path(lab.registry()["chatty"]["log"]).read_text())
    r = lab.svc("--json", "logs", "chatty", "-n", "5")
    d = result(r, 0)
    assert d["lines"] == [f"line{i}" for i in range(25, 30)]
    assert d["truncated"]["omitted_lines"] == 25
    assert d["truncated"]["full_output"] == lab.registry()["chatty"]["log"]
    assert lab.svc("--json", "logs", "chatty", "-n", "0").returncode == 2


def test_logs_withheld_when_the_redaction_rules_are_unavailable(lab: Lab) -> None:
    started(lab, "quiet", ["sh", "-c", "echo hello; exec sleep 300"])
    assert wait_until(lambda: "hello" in Path(lab.registry()["quiet"]["log"]).read_text())
    r = lab.svc("--json", "logs", "quiet", TIMELIKE_REDACTION_RULES=str(lab.tmp / "absent.toml"))
    d = result(r, 0)
    assert d["lines"] == ["[log lines withheld: redaction rules unavailable]"]
    assert "withheld: redaction rules unavailable" in d["verdict"]


def test_stop_all_with_nothing_registered_stops_nothing(lab: Lab) -> None:
    d = result(lab.svc("--json", "stop", "--all", "--yes"), 0)
    assert "nothing stopped" in d["verdict"]
