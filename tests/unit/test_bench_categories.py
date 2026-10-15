"""Units for benchlib.categories (feature 002 slice 1, FR-40).

SC-7: "Failed commands are grouped into categories including command not found, module not found, timeout,
memory kill and network denial".

Where this host can produce the failure, it does: the outputs below come from running real commands (bash,
python3, node, git), not from strings written to match the rules (cross-stack P005). timelike's own verdict
texts are read from the files that print them, so a reworded verdict breaks a test here rather than silently
falling into `other`. The Docker lane produces every category again, in both images
(`timelike-bench categories --probe`, tests/e2e).
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest
from benchlib import categories as c

REPO = Path(__file__).resolve().parents[2]


def real(argv: list[str], timeout: float = 30) -> tuple[int, str]:
    """Run a real command with no network-dependent success path; its exit code and merged output."""
    p = subprocess.run(
        argv, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL, check=False
    )
    return p.returncode, p.stdout + p.stderr


def test_success_has_no_category() -> None:
    assert c.categorize(0, False, "fine") == ""


def test_a_hung_call_exiting_zero_is_still_a_timeout() -> None:
    assert c.categorize(0, True, "") == c.TIMEOUT


def test_real_command_not_found_from_bash() -> None:
    code, out = real(["bash", "-c", "nosuch-bench-cmd-7f3a"])
    assert code == 127 and "command not found" in out
    assert c.categorize(code, False, out) == c.COMMAND_NOT_FOUND


def test_real_command_not_found_inside_a_script_with_a_later_exit() -> None:
    # The message is there even when the call's own exit is not 127.
    code, out = real(["bash", "-c", "nosuch-bench-cmd-7f3a; exit 3"])
    assert code == 3
    assert c.categorize(code, False, out) == c.COMMAND_NOT_FOUND


def test_real_python_module_not_found() -> None:
    code, out = real(["python3", "-c", "import nosuch_bench_mod_7f3a"])
    assert code == 1 and "ModuleNotFoundError" in out
    assert c.categorize(code, False, out) == c.MODULE_NOT_FOUND


@pytest.mark.skipif(shutil.which("node") is None, reason="no node on this host; the Docker lane runs it")
def test_real_node_module_not_found() -> None:
    code, out = real(["node", "-e", "require('nosuch-bench-mod-7f3a')"])
    assert code != 0 and "Cannot find module" in out
    assert c.categorize(code, False, out) == c.MODULE_NOT_FOUND


def test_real_timeout_from_gnu_timeout() -> None:
    code, out = real(["timeout", "0.2", "sleep", "5"])
    assert code == 124
    assert c.categorize(code, False, out) == c.TIMEOUT


def test_real_connection_refused() -> None:
    # Port 9 (discard) on loopback: nothing listens there on a normal host, so the kernel refuses.
    code, out = real(["bash", "-c", "exec 3<>/dev/tcp/127.0.0.1/9"])
    assert code != 0 and "refused" in out.lower()
    assert c.categorize(code, False, out) == c.NETWORK_DENIAL


def test_real_dns_failure_from_git() -> None:
    # .invalid never resolves (RFC 6761), so this fails at name resolution whatever the network is.
    code, out = real(["git", "ls-remote", "https://bench-7f3a.invalid/x.git"], timeout=60)
    assert code != 0 and "resolve host" in out
    assert c.categorize(code, False, out) == c.NETWORK_DENIAL


def test_exit_137_needs_oom_evidence() -> None:
    code, out = real(["bash", "-c", "kill -KILL $$"])
    assert code in (137, -9)
    code = 137 if code == -9 else code
    assert c.categorize(code, False, out, oom_rose=False) == c.OTHER  # a kill -9 is not a memory kill
    assert c.categorize(code, False, out, oom_rose=True) == c.MEMORY_KILL


def test_other_is_shown_never_dropped() -> None:
    code, out = real(["ls", "/nonexistent-bench-7f3a"])
    assert code != 0
    assert c.categorize(code, False, out) == c.OTHER


# --- timelike's own verdict texts, read from the files that print them ---------------------------


def _source(rel: str) -> str:
    return (REPO / rel).read_text()


def test_003_run_timeout_verdict() -> None:
    src = _source("tools/bin/run")
    assert 'f"timeout after {limit:g} s ({source}); raise with --timeout' in src
    verdict = "exit 124 (timeout after 1 s (--timeout); raise with --timeout or TIMELIKE_RUN_TIMEOUT) · 1.0 s"
    # 003's verdict line carries the words even when a wrapper reports a different exit.
    assert c.categorize(1, False, verdict) == c.TIMEOUT


def test_003_run_out_of_memory_verdict() -> None:
    assert 'outcome.words = f"out of memory: {limit}"' in _source("tools/bin/run")
    verdict = "exit 137 (out of memory: 64.0 MiB) · 0.3 s · 0 lines"
    assert c.categorize(137, False, verdict, oom_rose=True) == c.MEMORY_KILL
    assert c.categorize(137, False, verdict, oom_rose=False) == c.OTHER


def test_007_handler_lines() -> None:
    src = _source("image/rootfs/etc/timelike/shell-env.bash")
    assert "timelike: install it yourself:" in src and "which is not installed" in src
    out = (
        "bash: line 1: rg: command not found\n"
        "timelike: rg is in the Debian package ripgrep, which is not installed."
    )
    assert c.categorize(127, False, out) == c.COMMAND_NOT_FOUND


def test_013_guard_unreachable() -> None:
    src = _source("tools/bin/package-guard")
    assert 'f"{lk.registry} unreachable from this container: {lk.how}"' in src
    out = "package-guard: refused: https://pypi.org/simple unreachable from this container: DNS failure"
    assert c.categorize(4, False, out) == c.NETWORK_DENIAL


def test_004_adele_denial() -> None:
    src = _source("tools/agentio/agentio.py")
    assert "nothing performed; the operator extends it" in src
    out = "adele: beyond grant fly-deploy: limit machines; nothing performed; the operator extends it"
    assert c.categorize(4, False, out) == c.NETWORK_DENIAL


# --- the order: one category per call ------------------------------------------------------------


@pytest.mark.parametrize(
    ("args", "want"),
    [
        ((124, False, "No module named x"), c.TIMEOUT),  # a hang outranks what it printed
        ((137, False, "command not found"), c.COMMAND_NOT_FOUND),  # 137 without OOM evidence falls through
        ((127, False, "ModuleNotFoundError"), c.COMMAND_NOT_FOUND),
        ((1, False, "ModuleNotFoundError … Connection refused"), c.MODULE_NOT_FOUND),
    ],
)
def test_one_category_per_call_in_the_stated_order(args: tuple[int, bool, str], want: str) -> None:
    assert c.categorize(*args) == want


def test_every_category_is_described_in_order() -> None:
    lines = c.describe()
    assert len(lines) == len(c.CATEGORIES)
    for i, (line, cat) in enumerate(zip(lines, c.CATEGORIES, strict=True), start=1):
        assert re.match(rf"{i}\. {re.escape(c.LABELS[cat])}:", line), line


# --- the harnesses' own texts, from the recorded transcripts (tests/fixtures/transcripts, T041) -----

TRANSCRIPTS = REPO / "tests/fixtures/transcripts"


def _opencode_outputs(scenario: str) -> dict[str, tuple[int | None, str]]:
    import json

    out: dict[str, tuple[int | None, str]] = {}
    for line in (TRANSCRIPTS / f"opencode/opencode--{scenario}.stdout.jsonl").read_text().splitlines():
        event = json.loads(line)
        if event["type"] == "tool_use":
            state = event["part"]["state"]
            out[state["input"]["command"]] = (state["metadata"]["exit"], state["output"])
    return out


def test_opencode_s_own_timeout_is_a_timeout() -> None:
    exit_code, output = _opencode_outputs("failures")["bash -c 'kill -KILL $$'"]
    assert exit_code is None and "shell tool terminated command after exceeding timeout" in output
    assert c.categorize(-1, False, output) == c.TIMEOUT


def test_git_s_failed_to_connect_is_a_network_denial() -> None:
    exit_code, output = _opencode_outputs("failures")["git ls-remote https://bench-7f3a.invalid/x.git"]
    assert exit_code == 128 and "Failed to connect to" in output
    assert c.categorize(exit_code, False, output) == c.NETWORK_DENIAL
