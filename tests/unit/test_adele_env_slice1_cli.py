"""adele env, slice 1 (014 contracts/adele-env.md § Slice 1; plan R12, R13, R17, R19, R20), against a fake.

The harness is test_adele_env_cli's: the client runs as a real subprocess against the in-process fake of
Adele's request interface, which records what it was SENT. What Adele does with the daemon (devcontainers,
builds, lifecycle commands, exec, collection) is the e2e lane's.
"""

from __future__ import annotations

import argparse
import importlib.machinery
import importlib.util
import json
import subprocess
import threading
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest
from conftest import base_env
from test_adele_cli import (
    ADELE,
    SESSION,
    URL_ENV,
    FakeAdele,
    Proc,
    adele,
    doc_of,
    no_traceback,
    one_error_line,
)
from test_adele_env_cli import NAME, go, listener, svc, up, up_body, ws

__all__ = ["adele", "listener", "ws"]  # the fixtures, imported for their names


def load_adele() -> ModuleType:
    loader = importlib.machinery.SourceFileLoader("adele_tool_s1", str(ADELE))
    spec = importlib.util.spec_from_loader("adele_tool_s1", loader)
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def later(seconds: float, fn: Any) -> threading.Timer:
    t = threading.Timer(seconds, fn)
    t.daemon = True
    t.start()
    return t


def sent_post(fake: FakeAdele, path: str = "/v1/requests") -> dict[str, Any]:
    body: dict[str, Any] = next(s for s in fake.received() if s.method == "POST" and s.path == path).body
    return body


# ── readiness, decision C (R20) ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("service", "word", "words"),
    [
        (svc("job", state="exited", code=0), "completed", "completed (exit 0)"),
        (svc("job", state="exited", code=2), "failed", "exited 2"),
        (svc("db", health="healthy"), "ready", "ready (healthy)"),
        (svc("db", health="starting"), "waiting", "running (starting)"),
        (svc("db", state="created"), "waiting", "created"),
        ({**svc("migrate"), "one_shot": True}, "waiting", "running (one-shot: waiting for its exit)"),
        (svc("worker"), "unchecked", "running, no readiness check"),
        ({**svc("worker"), "one_shot": False}, "unchecked", "running, no readiness check"),
    ],
    ids=["exit-0", "exit-2", "healthy", "starting", "not-running", "one-shot", "no-check", "not-one-shot"],
)
def test_each_readiness_word(service: dict[str, Any], word: str, words: str) -> None:
    assert load_adele().readiness(service) == (word, words)


def test_a_running_service_with_ports_is_probed(listener: int) -> None:
    mod = load_adele()
    assert mod.readiness(svc("web", ports=[listener])) == ("ready", "ready (running, ports accept)")


def test_a_service_with_no_readiness_check_does_not_block_and_is_never_counted_ready(
    py: str, scratch: Path, adele: FakeAdele, ws: Path
) -> None:
    adele.answer("POST", "/v1/requests", 200, up_body([svc("db", health="healthy"), svc("worker")]))
    r = up(py, scratch, adele, ws, "--wait", "60", timeout=20)
    no_traceback(r)
    assert r.returncode == 0, r.stderr
    head = r.stdout.splitlines()[1]
    assert head.startswith(f"verdict: up {NAME}: 1 ready, 1 running with no readiness check in "), head
    assert "worker  running, no readiness check" in r.stdout
    assert not [s for s in adele.received() if s.method == "GET"]  # concluded at once: nothing polled
    doc = doc_of(up(py, scratch, adele, ws, "--json"))
    assert {s["service"]: s["ready"] for s in doc["services"]} == {"db": "ready", "worker": "unchecked"}


def test_nothing_unchecked_keeps_slice_0s_verdict(py: str, scratch: Path, adele: FakeAdele, ws: Path) -> None:
    adele.answer("POST", "/v1/requests", 200, up_body([svc("db", health="healthy")]))
    head = up(py, scratch, adele, ws).stdout.splitlines()[1]
    assert head.startswith(f"verdict: up {NAME}: 1 ready in ") and "readiness check" not in head


def test_a_devcontainer_with_no_readiness_check_names_both(
    py: str, scratch: Path, adele: FakeAdele, ws: Path
) -> None:
    body = {**up_body([svc("devcontainer")]), "kind": "devcontainer"}
    adele.answer("POST", "/v1/requests", 200, body)
    r = up(py, scratch, adele, ws)
    assert r.returncode == 0, r.stderr
    head = r.stdout.splitlines()[1]
    assert head.startswith(f"verdict: up {NAME}: devcontainer, 1 running with no readiness check in "), head


def test_a_one_shot_is_waited_for_until_it_exits_0(
    py: str, scratch: Path, adele: FakeAdele, ws: Path
) -> None:
    running = [{**svc("migrate"), "one_shot": True}, svc("db", health="healthy")]
    done = [{**svc("migrate", state="exited", code=0), "one_shot": True}, svc("db", health="healthy")]
    adele.answer("POST", "/v1/requests", 200, up_body(running))
    adele.answer("GET", f"/v1/envs/{NAME}", 200, {"name": NAME, "services": running})
    later(1.5, lambda: adele.answer("GET", f"/v1/envs/{NAME}", 200, {"name": NAME, "services": done}))
    r = up(py, scratch, adele, ws, "--wait", "30", timeout=40)
    assert r.returncode == 0, r.stderr
    assert r.stdout.splitlines()[1].startswith(f"verdict: up {NAME}: 2 ready in ")
    assert "migrate  completed (exit 0)" in r.stdout
    assert len([s for s in adele.received() if s.method == "GET"]) >= 2


def test_a_one_shot_still_running_at_the_bound_is_124_waiting(
    py: str, scratch: Path, adele: FakeAdele, ws: Path
) -> None:
    running = [{**svc("migrate"), "one_shot": True}]
    adele.answer("POST", "/v1/requests", 200, up_body(running))
    adele.answer("GET", f"/v1/envs/{NAME}", 200, {"name": NAME, "services": running})
    r = up(py, scratch, adele, ws, "--wait", "2", "--json")
    assert r.returncode == 124, r.stderr
    doc = doc_of(r)
    assert doc["services"][0]["ready"] == "waiting" and doc["services"][0]["one_shot"] is True
    assert "running (one-shot: waiting for its exit)" in doc["lines"][0]


def test_a_one_shot_that_exits_non_zero_is_exit_1_with_its_last_lines(
    py: str, scratch: Path, adele: FakeAdele, ws: Path
) -> None:
    running = [{**svc("migrate"), "one_shot": True}]
    failed = [
        {
            **svc("migrate", state="exited", code=4),
            "one_shot": True,
            "last_lines": ["applying 0003", "error: relation exists", ""],
        }
    ]
    adele.answer("POST", "/v1/requests", 200, up_body(running))
    adele.answer("GET", f"/v1/envs/{NAME}", 200, {"name": NAME, "services": running})
    later(1.0, lambda: adele.answer("GET", f"/v1/envs/{NAME}", 200, {"name": NAME, "services": failed}))
    r = up(py, scratch, adele, ws, "--wait", "30", timeout=40)
    assert r.returncode == 1, r.stderr
    line = one_error_line(r)
    assert "service migrate exited 4" in line
    assert "(last lines: applying 0003 · error: relation exists)" in line
    assert f"adele env down {NAME}" in line


def test_last_lines_are_bounded_keeping_the_end() -> None:
    mod = load_adele()
    text = mod._last([f"line {i} " + "x" * 40 for i in range(50)])
    assert len(text) == mod.LAST_LINES_MAX and text.startswith("…") and text.endswith("line 49 " + "x" * 40)


# ── which file: the devcontainer choice (R12) ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("files", "extra", "expected"),
    [
        ([".devcontainer/devcontainer.json"], [], True),
        ([".devcontainer.json"], [], True),
        ([".devcontainer/devcontainer.json", "compose.yaml"], [], False),
        ([".devcontainer.json", "docker-compose.yml"], [], False),
        ([".devcontainer/devcontainer.json"], ["-f", "other.yaml"], False),
        ([], [], False),
        (["compose.yml"], ["--devcontainer"], True),
    ],
    ids=["dir-json", "root-json", "compose-wins", "docker-compose-wins", "f-given", "neither", "flag"],
)
def test_the_devcontainer_is_chosen_only_as_r12_says(
    py: str, scratch: Path, adele: FakeAdele, ws: Path, files: list[str], extra: list[str], expected: bool
) -> None:
    for f in files:
        p = ws / "proj" / f
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("{}\n")
    adele.answer("POST", "/v1/requests", 200, up_body([svc("db", health="healthy")]))
    r = up(py, scratch, adele, ws, *extra)
    assert r.returncode == 0, r.stderr
    params = sent_post(adele)["params"]
    if expected:
        assert params["devcontainer"] is True
    else:
        assert "devcontainer" not in params


# ── up's new answer fields (R13, R15, R18) ─────────────────────────────────────────────────────


def test_builds_lifecycle_commands_not_run_and_an_unknown_requester_are_each_a_line(
    py: str, scratch: Path, adele: FakeAdele, ws: Path
) -> None:
    body = {
        **up_body([svc("devcontainer")]),
        "kind": "devcontainer",
        "built": [
            {
                "service": "devcontainer",
                "image": f"{NAME}-devcontainer:4f1e",
                "reused": False,
                "seconds": 6.24,
            },
            {"service": "api", "image": f"{NAME}-api:9c0d", "reused": True, "seconds": 0},
        ],
        "lifecycle": [
            {"name": "onCreateCommand", "exit_code": 0, "last_lines": [], "timed_out": False},
            {"name": "postCreateCommand.deps", "exit_code": 0, "last_lines": ["ok"], "timed_out": False},
        ],
        "not_run": ["postAttachCommand (no attach)"],
        "requester": {"unknown": "no timelike agent container has the address 10.0.0.9"},
    }
    adele.answer("POST", "/v1/requests", 200, body)
    r = up(py, scratch, adele, ws)
    assert r.returncode == 0, r.stderr
    out = r.stdout.splitlines()
    assert f"built devcontainer: {NAME}-devcontainer:4f1e in 6.2 s (nothing pulled)" in out
    assert f"reused api: {NAME}-api:9c0d (unchanged)" in out
    assert "onCreateCommand  exit 0" in out and "postCreateCommand.deps  exit 0" in out
    assert "not run: postAttachCommand (no attach)" in out
    assert (
        "requester: unknown (no timelike agent container has the address 10.0.0.9) — only adele session end"
        " or the ttl can end it"
    ) in out
    doc = doc_of(up(py, scratch, adele, ws, "--json"))
    assert doc["kind"] == "devcontainer" and doc["built"] == body["built"]
    assert doc["lifecycle"] == body["lifecycle"] and doc["not_run"] == body["not_run"]
    assert doc["requester"] == body["requester"]


def test_a_found_requester_is_data_only(py: str, scratch: Path, adele: FakeAdele, ws: Path) -> None:
    body = {**up_body([svc("db", health="healthy")]), "requester": {"container": "abc123"}}
    adele.answer("POST", "/v1/requests", 200, body)
    r = up(py, scratch, adele, ws)
    assert r.returncode == 0 and "requester" not in r.stdout
    assert doc_of(up(py, scratch, adele, ws, "--json"))["requester"] == {"container": "abc123"}


def test_a_failed_lifecycle_command_is_exit_1_naming_it_and_down(
    py: str, scratch: Path, adele: FakeAdele, ws: Path
) -> None:
    body = {
        **up_body([svc("devcontainer")]),
        "lifecycle": [
            {"name": "onCreateCommand", "exit_code": 0, "last_lines": [], "timed_out": False},
            {"name": "postCreateCommand", "exit_code": 2, "last_lines": ["npm ERR! 404"], "timed_out": False},
        ],
    }
    adele.answer("POST", "/v1/requests", 200, body)
    r = up(py, scratch, adele, ws)
    assert r.returncode == 1 and r.stdout == ""
    line = one_error_line(r)
    assert f"{NAME}: lifecycle command postCreateCommand exited 2 (last lines: npm ERR! 404)" in line
    assert f"the environment stays up; remove it with adele env down {NAME}" in line


def test_a_lifecycle_command_past_its_bound_is_124_naming_it(
    py: str, scratch: Path, adele: FakeAdele, ws: Path
) -> None:
    body = {
        **up_body([svc("devcontainer")]),
        "lifecycle": [{"name": "postStartCommand", "exit_code": -1, "last_lines": [], "timed_out": True}],
    }
    adele.answer("POST", "/v1/requests", 200, body)
    r = up(py, scratch, adele, ws)
    assert r.returncode == 124
    line = one_error_line(r)
    assert f"{NAME}: lifecycle command postStartCommand did not finish within its bound" in line
    assert f"adele env down {NAME}" in line


# ── up's new failures (FR-16, FR-21, FR-24) ────────────────────────────────────────────────────


def test_a_failed_build_step_is_exit_1_naming_the_step_and_its_last_lines(
    py: str, scratch: Path, adele: FakeAdele, ws: Path
) -> None:
    adele.answer(
        "POST",
        "/v1/requests",
        502,
        {
            "error": "the build failed",
            "build": {
                "service": "api",
                "step": "Step 3/5 : RUN make",
                "last_lines": ["make: *** [all] Error 2"],
            },
        },
    )
    r = up(py, scratch, adele, ws)
    assert r.returncode == 1
    line = one_error_line(r)
    assert f"{NAME}: build of api failed at Step 3/5 : RUN make: make: *** [all] Error 2" in line


def test_a_build_past_its_bound_is_124_naming_the_step(
    py: str, scratch: Path, adele: FakeAdele, ws: Path
) -> None:
    adele.answer(
        "POST",
        "/v1/requests",
        504,
        {"timed_out": True, "build": {"service": "api", "step": "Step 4/5 : RUN ./slow"}},
    )
    r = up(py, scratch, adele, ws)
    assert r.returncode == 124
    line = one_error_line(r)
    assert f"{NAME}: build of api did not finish within its bound (at Step 4/5 : RUN ./slow)" in line


def test_a_base_image_not_on_the_daemon_is_exit_3_and_pulls_nothing(
    py: str, scratch: Path, adele: FakeAdele, ws: Path
) -> None:
    adele.answer(
        "POST",
        "/v1/requests",
        422,
        {
            "outcome": "refused",
            "refusal": "image",
            "setting": "FROM",
            "service": "api",
            "value": "python:3.14-slim",
            "remediation": "the operator pulls it on the host: docker pull python:3.14-slim",
            "operator_command": "docker pull python:3.14-slim",
            "performed": False,
        },
    )
    r = up(py, scratch, adele, ws)
    assert r.returncode == 3 and r.stdout == ""
    line = one_error_line(r)
    assert "base image python:3.14-slim is not on the daemon, and a build pulls nothing" in line
    assert "docker pull python:3.14-slim" in line


def test_a_devcontainer_json_that_does_not_parse_is_exit_2_with_the_line(
    py: str, scratch: Path, adele: FakeAdele, ws: Path
) -> None:
    adele.answer(
        "POST",
        "/v1/requests",
        422,
        {
            "outcome": "refused",
            "refusal": "setting",
            "setting": "devcontainer.json",
            "value": "line 7: invalid character '}' looking for beginning of object key string",
            "remediation": "fix .devcontainer/devcontainer.json",
            "performed": False,
        },
    )
    r = up(py, scratch, adele, ws, "--devcontainer")
    assert r.returncode == 2 and r.stdout == ""
    line = one_error_line(r)
    assert line.startswith("error: devcontainer.json line 7: invalid character '}'")
    assert "(code 2)" in line


# ── env exec (R17) ─────────────────────────────────────────────────────────────────────────────


def exec_body(code: int, stdout: str = "", stderr: str = "", **extra: Any) -> dict[str, Any]:
    return {
        "outcome": "performed",
        "exit_code": code,
        "stdout": stdout,
        "stderr": stderr,
        "dropped": {"stdout": 0, "stderr": 0},
        "service": "devcontainer",
        "user": "vscode",
        "ledger_id": 41,
        **extra,
    }


@pytest.mark.parametrize("code", [0, 7])
def test_exec_passes_the_commands_exit_through_with_its_output(
    py: str, scratch: Path, adele: FakeAdele, code: int
) -> None:
    adele.answer("POST", "/v1/requests", 200, exec_body(code, "one\ntwo\n", "warn\n"))
    r = go(py, scratch, adele, None, "env", "exec", NAME, "--", "sh", "-c", f"exit {code}")
    no_traceback(r)
    assert r.returncode == code, r.stderr
    out = r.stdout.splitlines()
    assert out[1].startswith(f"verdict: exec {NAME} devcontainer as vscode: exit {code} in "), out[1]
    assert out[2:5] == ["one", "two", "warn"]
    sent = sent_post(adele)
    assert sent["action"] == "exec" and sent["capability"] == "docker.compose" and sent["grant"] == ""
    assert sent["params"] == {
        "name": NAME,
        "ttl": "",
        "ports": [],
        "cmd": ["sh", "-c", f"exit {code}"],
        "timeout_s": 100.0,
    }
    assert sent["session"] == SESSION


def test_exec_json_carries_cause_and_command_exit(py: str, scratch: Path, adele: FakeAdele) -> None:
    adele.answer("POST", "/v1/requests", 200, exec_body(7, "x\n", user=""))
    r = go(
        py,
        scratch,
        adele,
        None,
        "--json",
        "env",
        "exec",
        NAME,
        "--service",
        "api",
        "--timeout",
        "5",
        "--",
        "false",
    )
    assert r.returncode == 7, r.stderr
    doc = doc_of(r)
    assert doc["exit"] == 7 and doc["command_exit"] == 7 and doc["cause"] == "command"
    assert "as the image's user: exit 7" in doc["verdict"]
    params = sent_post(adele)["params"]
    assert params["service"] == "api" and params["timeout_s"] == 5.0 and params["cmd"] == ["false"]


def test_exec_names_dropped_output(py: str, scratch: Path, adele: FakeAdele) -> None:
    adele.answer("POST", "/v1/requests", 200, exec_body(0, "tail\n", dropped={"stdout": 2048, "stderr": 0}))
    r = go(py, scratch, adele, None, "env", "exec", NAME, "--", "cat", "big")
    assert r.returncode == 0
    assert " · dropped 2048 bytes of stdout, 0 of stderr (Adele keeps the last 1 MiB of each)" in r.stdout


def test_exec_past_its_bound_is_124_saying_the_process_may_still_run(
    py: str, scratch: Path, adele: FakeAdele
) -> None:
    adele.answer("POST", "/v1/requests", 504, {**exec_body(-1, "partial\n"), "timed_out": True})
    r = go(py, scratch, adele, None, "env", "exec", NAME, "--timeout", "3", "--", "sleep", "60")
    assert r.returncode == 124, r.stderr
    head = r.stdout.splitlines()[1]
    assert head == (
        f"verdict: exec {NAME} devcontainer: past its 3 s bound; it may still be running in the container"
        f" (the Engine API cannot stop an exec'd process) · adele env down {NAME} removes it"
    )
    assert len(head) <= 200
    assert "partial" in r.stdout


def test_exec_with_no_such_environment_or_service_is_exit_3(py: str, scratch: Path, adele: FakeAdele) -> None:
    adele.answer("POST", "/v1/requests", 404, {"error": f"no live environment named {NAME}"})
    r = go(py, scratch, adele, None, "env", "exec", NAME, "--", "true")
    assert r.returncode == 3
    assert f"no live environment named {NAME}" in one_error_line(r)


def test_exec_in_several_services_with_none_named_is_usage_listing_them(
    py: str, scratch: Path, adele: FakeAdele
) -> None:
    adele.answer("POST", "/v1/requests", 409, {"error": "more than one service", "services": ["api", "db"]})
    r = go(py, scratch, adele, None, "env", "exec", NAME, "--", "true")
    assert r.returncode == 2
    line = one_error_line(r)
    assert f"{NAME} has more than one service and none was named: api, db" in line and "--service api" in line


def test_exec_in_a_container_that_is_not_running_is_exit_1(py: str, scratch: Path, adele: FakeAdele) -> None:
    adele.answer("POST", "/v1/requests", 502, {"error": "the container of db is exited"})
    r = go(py, scratch, adele, None, "env", "exec", NAME, "--service", "db", "--", "true")
    assert r.returncode == 1 and "the container of db is exited" in one_error_line(r)


def test_exec_without_a_command_is_usage_and_sends_nothing(py: str, scratch: Path, adele: FakeAdele) -> None:
    r = go(py, scratch, adele, None, "env", "exec", NAME)
    assert r.returncode == 2 and "env exec needs a command after --" in one_error_line(r)
    assert not [s for s in adele.received() if s.method == "POST"]


def test_exec_defaults_to_the_cwd_projects_name(py: str, scratch: Path, adele: FakeAdele, ws: Path) -> None:
    adele.answer("POST", "/v1/requests", 200, exec_body(0))
    proj = (ws / "proj").resolve()
    env = base_env(scratch, session=SESSION, **{URL_ENV: adele.url, "TIMELIKE_WORKSPACE": str(ws)})
    r: Proc = subprocess.run(
        [py, str(ADELE), "--text", "env", "exec", "--", "pwd"],
        env=env,
        cwd=proj,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert r.returncode == 0, r.stderr
    assert sent_post(adele)["params"]["name"] == load_adele().default_name(str(proj))


def test_a_command_after_double_dash_belongs_to_exec_only(py: str, scratch: Path, adele: FakeAdele) -> None:
    r = go(py, scratch, adele, None, "env", "status", "--", "ls")
    assert r.returncode == 2 and "belong to env exec" in one_error_line(r)


def resolved_timeout(argv: list[str]) -> float:
    """The HTTP timeout main() hands to Adele's call for argv, with call() stubbed (no subprocess)."""
    mod = load_adele()
    agentio = mod.agentio
    seen: list[float] = []

    def fake_call(method: str, path: str, timeout: float, payload: Any = None) -> Any:
        seen.append(timeout)
        return mod.Reply(200, {"grants": [], "envs": [], **exec_body(0)})

    mod.call = fake_call
    parser = agentio._parser(mod.TOOL, mod.configure)
    cut = argv.index("--") if "--" in argv else len(argv)
    args: argparse.Namespace = parser.parse_args(argv[:cut])
    args.command = argv[cut + 1 :]
    ctx = SimpleNamespace(tool=SimpleNamespace(passes_exit=False))
    mod.main(args, ctx)
    return seen[0]


def test_exec_defaults_to_100_s_and_every_other_verb_keeps_30() -> None:
    assert (
        resolved_timeout(["env", "exec", NAME, "--", "true"]) == 100.0 + 30.0
    )  # its bound, plus Adele's slack
    assert resolved_timeout(["env", "exec", NAME, "--timeout", "7", "--", "true"]) == 7.0 + 30.0
    assert resolved_timeout(["grants"]) == 30.0
    assert resolved_timeout(["env", "status"]) == 30.0
    assert resolved_timeout(["grants", "--timeout", "4"]) == 4.0


def test_the_manifest_names_execs_default_and_declares_no_tool_wide_pass_through(
    py: str, scratch: Path
) -> None:
    r = go(py, scratch, FakeAdele(url="http://127.0.0.1:9"), None, "--agent-info")
    info = json.loads(r.stdout)
    assert info["default_timeout_s"] == 30.0 and info["exec_default_timeout_s"] == 100.0
    assert "passes_exit" not in info and "--devcontainer" in info["flags"] and "--service" in info["flags"]


def test_help_stays_within_40_lines_and_names_the_new_verbs(py: str, scratch: Path) -> None:
    r = go(py, scratch, FakeAdele(url="http://127.0.0.1:9"), None, "--help")
    assert r.returncode == 0, r.stderr
    assert len(r.stdout.splitlines()) <= 40
    assert (
        "adele env exec" in r.stdout and "adele env collect" in r.stdout and "adele session end" in r.stdout
    )


def test_an_unknown_env_verb_lists_them_all(py: str, scratch: Path, adele: FakeAdele) -> None:
    r = go(py, scratch, adele, None, "env", "nope")
    line = one_error_line(r)
    assert r.returncode == 2
    assert all(f"adele env {v}" in line for v in ("up", "status", "down", "exec", "collect"))


# ── env collect and session end (R19) ──────────────────────────────────────────────────────────


def test_collect_with_nothing_to_collect_is_exit_0(py: str, scratch: Path, adele: FakeAdele) -> None:
    adele.answer("POST", "/v1/envs/collect", 200, {"collected": [], "failed": [], "count": 0})
    r = go(py, scratch, adele, None, "env", "collect")
    assert r.returncode == 0, r.stderr
    assert r.stdout.splitlines()[1] == "verdict: collect: 0 collected · 0 failed · read back from the daemon"
    assert sent_post(adele, "/v1/envs/collect")["session"] == SESSION


def test_collect_names_each_environment_and_its_cause(py: str, scratch: Path, adele: FakeAdele) -> None:
    cause = "session s1 ended at 2026-10-18T12:00:00Z (adele session end, ledger #140)"
    adele.answer(
        "POST",
        "/v1/envs/collect",
        200,
        {
            "collected": [
                {
                    "name": NAME,
                    "cause": cause,
                    "removed": {"containers": 2, "networks": 1, "volumes": 0},
                    "ledger_id": 141,
                }
            ],
            "failed": [],
            "count": 1,
        },
    )
    r = go(py, scratch, adele, None, "env", "collect")
    assert r.returncode == 0, r.stderr
    out = r.stdout.splitlines()
    assert out[1] == f"verdict: collect: 1 collected ({NAME}: {cause}) · 0 failed · read back from the daemon"
    assert out[2] == f"collected {NAME}: {cause} · removed 2 containers, 1 networks, 0 volumes · ledger #141"


def test_collect_with_a_failure_is_exit_1_naming_it(py: str, scratch: Path, adele: FakeAdele) -> None:
    gone = "session s2's agent container 9f8e no longer exists"
    adele.answer(
        "POST",
        "/v1/envs/collect",
        200,
        {"collected": [], "failed": [{"name": "tl-other-1a2b3c", "cause": gone, "left": 1}], "count": 0},
    )
    r = go(py, scratch, adele, None, "env", "collect")
    assert r.returncode == 1
    out = r.stdout.splitlines()
    assert out[1] == (
        f"verdict: collect: 0 collected · 1 failed (tl-other-1a2b3c: {gone}) · read back from the daemon"
    )
    assert out[2] == f"failed tl-other-1a2b3c: {gone} · 1 left — tried again on the next pass"


@pytest.mark.parametrize(
    ("outcome", "said"),
    [
        ("ended", "verdict: session s1 ended at 2026-10-18T12:00:00Z (ledger #140)"),
        (
            "already ended",
            "verdict: session s1 was already ended at 2026-10-18T12:00:00Z (ledger #140);"
            " nothing new recorded",
        ),
    ],
)
def test_session_end_is_exit_0_ended_or_already(
    py: str, scratch: Path, adele: FakeAdele, outcome: str, said: str
) -> None:
    adele.answer(
        "POST",
        "/v1/sessions/end",
        200,
        {"outcome": outcome, "session": "s1", "ended_at": "2026-10-18T12:00:00Z", "ledger_id": 140},
    )
    r = go(py, scratch, adele, None, "session", "end")
    assert r.returncode == 0, r.stderr
    assert r.stdout.splitlines()[1] == said
    assert sent_post(adele, "/v1/sessions/end") == {"session": SESSION}


def test_session_without_end_is_usage(py: str, scratch: Path, adele: FakeAdele) -> None:
    r = go(py, scratch, adele, None, "session", "start")
    assert r.returncode == 2 and "use adele session end" in one_error_line(r)
