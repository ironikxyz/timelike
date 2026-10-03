"""run (feature 003) against its spec and contracts/run-cli.md.

The tool runs as a real subprocess, like every other tool test (conftest.py). Commands that fork or
hang are bounded by the subprocess timeout in `conftest.run`, and processes are found only through
marker files they write, never by matching command lines (001 cycle 5, process failures 1 and 2).
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import signal
import stat
import time
from pathlib import Path
from typing import Any

import pytest
import schema
from conftest import TOOLS_DIR, base_env, events, run

RUN = TOOLS_DIR / "run"
VERDICT_RE = re.compile(r"^verdict: exit (\d+) \((.+?)\) · (\d+\.\d) s · (\d+) lines · log (/\S+)")


def go(py: str, scratch: Path, *args: str, timeout: float = 30, **env: str) -> Any:
    return run([py, str(RUN), *args], base_env(scratch, **env), timeout=timeout)


def doc_of(r: Any) -> dict[str, Any]:
    return json.loads(r.stdout)


# ── US1 · SC-5: "The tool's exit code equals the wrapped command's exit code" ──────────────────


@pytest.mark.parametrize(
    ("command", "code", "words"),
    [
        (["true"], 0, "command exited 0"),
        (["false"], 1, "command exited 1"),
        (["sh", "-c", "exit 42"], 42, "command exited 42"),
        (["sh", "-c", "kill -9 $$"], 137, "command killed by signal 9 (SIGKILL)"),
        (["no-such-command-xyz"], 127, "command not found: no-such-command-xyz"),
    ],
)
def test_exit_equals_the_wrapped_commands_exit_code(
    py: str, scratch: Path, command: list[str], code: int, words: str
) -> None:
    r = go(py, scratch, "--json", *command)
    assert r.returncode == code, r.stderr
    doc = doc_of(r)
    assert (doc["exit"], doc["cause"], doc["command_exit"]) == (code, "command", code)
    assert doc["verdict"].startswith(f"exit {code} ({words})")
    ev = events(scratch)[-1]
    assert (ev["tool"], ev["exit"]) == ("run", code)
    assert schema.errors(ev, schema.load("event.schema.json")) == []


def test_not_executable_is_126_and_never_runs(py: str, scratch: Path, tmp_path: Path) -> None:
    marker = tmp_path / "ran"
    script = tmp_path / "noexec.sh"
    script.write_text(f"#!/bin/sh\ntouch {marker}\n")
    script.chmod(stat.S_IRUSR | stat.S_IWUSR)
    r = go(py, scratch, "--json", str(script))
    assert r.returncode == 126
    assert doc_of(r)["verdict"].startswith(f"exit 126 (command not executable: {script}")
    assert not marker.exists()


def test_text_header_and_verdict(py: str, scratch: Path) -> None:
    r = go(py, scratch, "--text", "sh", "-c", "echo one; echo two >&2; exit 3")
    out = r.stdout.splitlines()
    assert r.returncode == 3
    assert out[0] == "run: sh -c 'echo one; echo two >&2; exit 3' [run]"
    m = VERDICT_RE.match(out[1])
    assert m, out[1]
    assert m.group(1, 2, 4) == ("3", "command exited 3", "2")
    log = Path(m.group(5))
    assert log.is_absolute()
    assert log.read_text() == "one\ntwo\n"  # stdout and stderr in one log, in write order (R2)
    assert stat.S_IMODE(log.stat().st_mode) == 0o600
    assert out[2:] == ["one", "two"]


def test_json_carries_the_verdict_fields(py: str, scratch: Path) -> None:
    doc = doc_of(go(py, scratch, "--json", "printf", "a\nb"))
    assert list(doc)[:3] == ["tool", "target", "scope"]
    assert (doc["tool"], doc["target"], doc["scope"]) == ("run", "printf 'a b'", "run")  # rule 13: one line
    assert doc["line_count"] == 2  # a final line with no newline still counts (R14)
    assert doc["lines"] == ["a", "b"]
    assert doc["timeout_s"] == 100.0
    assert Path(doc["log"]).parent == scratch / "test" / "run"


def test_stdin_is_empty(py: str, scratch: Path) -> None:
    r = go(py, scratch, "--json", "sh", "-c", "read x; echo rc=$?")
    assert doc_of(r)["lines"] == ["rc=1"]  # end-of-file at once, never a wait (R13)


def test_a_flag_after_the_command_is_the_commands(py: str, scratch: Path) -> None:
    r = go(py, scratch, "--json", "echo", "--json", "--timeout")
    assert doc_of(r)["lines"] == ["--json --timeout"]


def test_double_dash_ends_runs_options(py: str, scratch: Path) -> None:
    r = go(py, scratch, "--json", "--", "sh", "-c", "exit 5")
    assert r.returncode == 5


# ── usage and run's own failures ───────────────────────────────────────────────────────────────


def test_no_command_is_usage(py: str, scratch: Path) -> None:
    r = go(py, scratch)
    assert r.returncode == 2
    assert r.stderr.startswith("error: no command given (code 2)")


@pytest.mark.parametrize("value", ["0", "-1", "soon", "inf", "nan"])
def test_bad_timeout_flag_is_usage(py: str, scratch: Path, value: str) -> None:
    r = go(py, scratch, "--timeout", value, "true")
    assert r.returncode == 2
    assert "--timeout" in r.stderr


def test_bad_timeout_variable_is_usage_naming_it(py: str, scratch: Path) -> None:
    r = go(py, scratch, "true", TIMELIKE_RUN_TIMEOUT="later")
    assert r.returncode == 2
    assert "TIMELIKE_RUN_TIMEOUT" in r.stderr


@pytest.mark.parametrize(
    ("flag", "env", "limit"),
    [
        ([], {}, 100.0),
        ([], {"TIMELIKE_RUN_TIMEOUT": "7.5"}, 7.5),
        (["--timeout", "3"], {"TIMELIKE_RUN_TIMEOUT": "7"}, 3.0),
    ],
)
def test_timeout_precedence(
    py: str, scratch: Path, flag: list[str], env: dict[str, str], limit: float
) -> None:
    assert doc_of(go(py, scratch, "--json", *flag, "true", **env))["timeout_s"] == limit


def test_unwritable_scratch_runs_nothing(py: str, scratch: Path, tmp_path: Path) -> None:
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("")
    marker = tmp_path / "ran"
    r = go(py, scratch, "touch", str(marker), TIMELIKE_SCRATCH_ROOT=str(blocker))
    assert r.returncode == 1
    assert "the command was not run" in r.stderr
    assert not marker.exists()


def test_manifest_declares_pass_through(py: str, scratch: Path) -> None:
    doc = doc_of(go(py, scratch, "--agent-info"))
    assert doc["passes_exit"] is True
    assert set(doc["exit_codes"]) == {"0", "1", "2", "124"}
    assert schema.errors(doc, schema.load("agent-info.schema.json")) == []


def test_help_fits_and_says_the_exit_passes_through(py: str, scratch: Path) -> None:
    out = go(py, scratch, "--help").stdout.splitlines()
    assert out[0] == "run: command [help]"
    assert len(out) <= 40
    assert any("the command's own exit" in x for x in out)


def test_log_names_are_unique_per_call(py: str, scratch: Path) -> None:
    a = doc_of(go(py, scratch, "--json", "true"))["log"]
    b = doc_of(go(py, scratch, "--json", "true"))["log"]
    assert a != b
    assert os.path.exists(a) and os.path.exists(b)


# ── US2 · SC-3: "A command that backgrounds a child holding stdout and then exits returns its
#    verdict within 2 seconds and names the detached child's process ID" ─────────────────────────


def load_run() -> Any:
    """run as a module, for its pure /proc helpers (the file has no .py suffix)."""
    import importlib.machinery
    import importlib.util

    loader = importlib.machinery.SourceFileLoader("run_tool", str(RUN))
    spec = importlib.util.spec_from_loader("run_tool", loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def kill_quietly(pids: list[int]) -> None:
    for pid in pids:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.kill(pid, signal.SIGKILL)


@pytest.mark.parametrize(
    ("script", "name"),
    [
        ("(sleep 30; echo late) & echo $! > {m}; echo hi", None),  # a subshell holds the output
        ("sleep 30 & echo $! > {m}; echo hi", "sleep"),
    ],
)
def test_backgrounded_child_verdict_within_2_seconds_names_its_pid(
    py: str, scratch: Path, tmp_path: Path, script: str, name: str | None
) -> None:
    marker = tmp_path / "child.pid"
    started = time.monotonic()
    r = go(py, scratch, "--json", "sh", "-c", script.format(m=marker))
    elapsed = time.monotonic() - started
    doc = doc_of(r)
    pids = [d["pid"] for d in doc["detached"]]
    try:
        assert r.returncode == 0
        assert elapsed < 2.0, elapsed
        child = int(marker.read_text())
        assert child in pids
        assert f"detached: {child} " in doc["verdict"]
        if name is not None:
            assert {"pid": child, "name": name} in doc["detached"]
        assert doc["lines"][0] == "hi"
    finally:
        kill_quietly(pids)


def test_nothing_detached_when_every_child_has_ended(py: str, scratch: Path) -> None:
    doc = doc_of(go(py, scratch, "--json", "sh", "-c", "sleep 0.05 & wait; echo done"))
    assert doc["detached"] == []
    assert " · detached:" not in doc["verdict"]  # (the tmp path itself may say "detached")


def test_parse_stat_reads_comm_with_spaces_and_parentheses() -> None:
    run_tool = load_run()
    assert run_tool.parse_stat("123 (a (b) c) S 1 123 123 0 -1") == (1, "S", "a (b) c")
    assert run_tool.parse_stat("garbage") is None
    assert run_tool.parse_stat("1 (x) S") is None


def test_descendants_follow_parent_links() -> None:
    run_tool = load_run()
    table = {10: (1, "S", "run"), 11: (10, "S", "sh"), 12: (11, "S", "sleep"), 13: (1, "S", "other")}
    assert run_tool.descendants(10, table) == {11, 12}


def test_log_writers_are_writers_only(tmp_path: Path) -> None:
    run_tool = load_run()
    log = tmp_path / "x.log"
    log.write_text("")
    with log.open("r"):
        assert os.getpid() not in run_tool.log_writers(log)
    with log.open("a"):
        assert os.getpid() in run_tool.log_writers(log)
    assert run_tool.log_writers(tmp_path / "missing.log") == set()


def test_verdict_names_at_most_five_detached_children(py: str, scratch: Path, tmp_path: Path) -> None:
    marker = tmp_path / "pids"
    script = f"for i in 1 2 3 4 5 6 7; do sleep 30 & echo $! >> {marker}; done"
    doc = doc_of(go(py, scratch, "--json", "sh", "-c", script))
    pids = [d["pid"] for d in doc["detached"]]
    try:
        assert sorted(int(x) for x in marker.read_text().split()) == sorted(pids)
        assert doc["verdict"].endswith(" (+2 more)")
        assert doc["verdict"].count(" sleep") == 5
    finally:
        kill_quietly(pids)


# ── US3 · SC-4: "A command exceeding its timeout exits 124, the verdict says timeout, and no process
#    from its process group survives" ─────────────────────────────────────────────────────────────

TREE = r"""#!/bin/bash
# Every descendant appends to its own heartbeat file; a stopped tree stops every heartbeat.
D=$1
beat() { while :; do echo x >> "$D/$1"; sleep 0.2; done; }
beat plain &
timeout 50 bash -c "while :; do echo x >> '$D/nested-timeout'; sleep 0.2; done" &
setsid bash -c "while :; do echo x >> '$D/setsid'; sleep 0.2; done" &
bash -c "trap '' TERM; while :; do echo x >> '$D/ignores-term'; sleep 0.2; done" &
sleep 1000
"""


def heartbeats(d: Path) -> dict[str, int]:
    return {p.name: p.stat().st_size for p in sorted(d.iterdir())}


def test_timeout_exits_124_and_no_process_of_the_tree_survives(
    py: str, scratch: Path, tmp_path: Path
) -> None:
    script = tmp_path / "tree.sh"
    script.write_text(TREE)
    script.chmod(0o755)
    beats = tmp_path / "beats"
    beats.mkdir()
    started = time.monotonic()
    r = go(py, scratch, "--json", "--timeout", "1", str(script), str(beats))
    elapsed = time.monotonic() - started
    doc = doc_of(r)
    assert r.returncode == 124, r.stderr
    assert (doc["cause"], doc["command_exit"], doc["not_stopped"]) == ("timeout", None, [])
    assert doc["verdict"].startswith(
        "exit 124 (timeout after 1 s (--timeout); raise with --timeout or TIMELIKE_RUN_TIMEOUT)"
    )
    assert elapsed < 1 + 5 + 2, elapsed  # limit + the stop sequence's bound + interpreter slack
    assert set(heartbeats(beats)) == {"plain", "nested-timeout", "setsid", "ignores-term"}
    before = heartbeats(beats)
    time.sleep(1.5)
    assert heartbeats(beats) == before  # nothing still beating: the whole tree was stopped


def test_timeout_stops_a_forking_loop(py: str, scratch: Path, tmp_path: Path) -> None:
    pids = tmp_path / "pids"
    loop = f"while :; do sh -c 'echo $$ >> {pids}; exec sleep 30' & sleep 0.02; done"
    r = go(py, scratch, "--json", "--timeout", "0.5", "bash", "-c", loop)
    assert r.returncode == 124
    assert doc_of(r)["not_stopped"] == []
    spawned = [int(x) for x in pids.read_text().split()]
    assert len(spawned) > 5
    alive = []
    for pid in spawned:
        try:
            state = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
        except (OSError, IndexError):
            continue
        if state != "Z":
            alive.append(pid)
    kill_quietly(alive)
    assert alive == []


def test_timeout_from_the_environment_is_named(py: str, scratch: Path) -> None:
    doc = doc_of(go(py, scratch, "--json", "sleep", "30", TIMELIKE_RUN_TIMEOUT="0.3"))
    assert doc["verdict"].startswith("exit 124 (timeout after 0.3 s (TIMELIKE_RUN_TIMEOUT);")


# ── US4 · SC-1: "Running a command that prints 5,000 lines returns a verdict line first, then the
#    first lines, the first error lines with their line numbers, the last lines, and the exact
#    command to view the rest" · SC-2: "When the whole output fits within the head and tail, it is
#    printed in full with no section markers" ───────────────────────────────────────────────────────

GEN = (
    'for i in $(seq 1 {n}); do case $i in 700|1800|3000) echo "error: boom $i";;'
    ' *) echo "line $i";; esac; done'
)
OMISSION_RE = re.compile(r"^… omitted (\d+) lines \((\d+) bytes\) — full output: (\S+); more: (.+)$")


def test_5000_lines_verdict_first_head_first_errors_tail_and_more(py: str, scratch: Path) -> None:
    r = go(py, scratch, "--text", "bash", "-c", GEN.format(n=5000))
    out = r.stdout.splitlines()
    assert r.returncode == 0
    assert out[0].startswith("run: bash -c ") and out[0].endswith(" [run]")
    m = VERDICT_RE.match(out[1])
    assert m and m.group(4) == "5000", out[1]
    log = Path(m.group(5))
    i = 2
    assert out[i] == "── lines 1–50 of 5000 ──"
    assert out[i + 1 : i + 51] == [f"line {k}" for k in range(1, 51)]
    i += 51
    assert out[i] == "── first errors (lines 51–4900) ──"
    assert out[i + 1 : i + 4] == [
        "L700: error: boom 700",
        "L1800: error: boom 1800",
        "L3000: error: boom 3000",
    ]
    i += 4
    assert out[i] == "── lines 4901–5000 of 5000 ──"
    assert out[i + 1 : i + 101] == [f"line {k}" for k in range(4901, 5001)]
    i += 101
    assert out[i] == f"more: sed -n 51,4900p {log}"
    assert out[i + 1 : i + 3] == ["exit: 0", f"full output: {log}"]
    om = OMISSION_RE.match(out[i + 3])
    assert om, out[i + 3]
    assert om.group(1) == str(4850 - 3)  # the gap, less the three error lines already shown
    assert om.group(3) == str(log)
    assert om.group(4) == f"sed -n 51,4900p {log}"
    assert len(out) == i + 4
    # the more command, run, prints exactly the gap from the log
    rest = run(["sh", "-c", om.group(4)], base_env(scratch)).stdout
    assert rest == "".join(f"{x}\n" for x in log.read_text().splitlines()[50:4900])
    omitted_bytes = sum(len(x) + 1 for k, x in enumerate(log.read_text().splitlines(), 1) if 51 <= k <= 4900)
    assert int(om.group(2)) == omitted_bytes - sum(len(f"error: boom {k}") + 1 for k in (700, 1800, 3000))


def test_json_capped_carries_sections_and_truncated(py: str, scratch: Path) -> None:
    doc = doc_of(go(py, scratch, "--json", "bash", "-c", GEN.format(n=5000)))
    assert [s["label"] for s in doc["sections"]] == [
        "lines 1–50 of 5000",
        "first errors (lines 51–4900)",
        "lines 4901–5000 of 5000",
    ]
    assert [s["count"] for s in doc["sections"]] == [50, 3, 100]
    assert doc["truncated"]["more"] == f"sed -n 51,4900p {doc['log']}"
    assert doc["truncated"]["full_output"] == doc["log"]
    assert doc["line_count"] == 5000


def test_output_within_the_cap_is_printed_in_full_with_no_markers(py: str, scratch: Path) -> None:
    r = go(py, scratch, "--text", "seq", "1", "120")
    out = r.stdout.splitlines()
    assert out[2:] == [str(k) for k in range(1, 121)]
    assert len(out) == 122
    assert not any(x.startswith(("── ", "more: ", "… omitted")) for x in out)


def test_errors_inside_the_head_or_tail_are_not_repeated(py: str, scratch: Path) -> None:
    script = (
        "for i in $(seq 1 400); do if [ $i = 3 ] || [ $i = 399 ]; then echo error $i; else echo $i; fi; done"
    )
    out = go(py, scratch, "--text", "bash", "-c", script).stdout.splitlines()
    assert not any(x.startswith("── first errors") for x in out)
    assert "error 3" in out and "error 399" in out


def test_small_limit_and_limit_zero(py: str, scratch: Path) -> None:
    out = go(py, scratch, "--text", "--limit", "10", "seq", "1", "30").stdout.splitlines()
    assert out[2] == "── lines 1–2 of 30 ──"
    assert "── lines 26–30 of 30 ──" in out
    whole = go(py, scratch, "--text", "--limit", "0", "seq", "1", "300").stdout.splitlines()
    assert whole[2:] == [str(k) for k in range(1, 301)]
    one = go(py, scratch, "--text", "--limit", "1", "seq", "1", "2").stdout.splitlines()
    assert one[2:4] == ["── lines 1–1 of 2 ──", "1"]  # a cap below head + tail shortens the tail
    assert one[4].startswith("more: sed -n 2,2p ")  # never an empty gap, never a re-run


def test_crlf_final_line_and_empty_output(py: str, scratch: Path) -> None:
    doc = doc_of(go(py, scratch, "--json", "printf", "a\r\nb\r\nc"))
    assert (doc["lines"], doc["line_count"]) == (["a", "b", "c"], 3)
    empty = doc_of(go(py, scratch, "--json", "true"))
    assert (empty["lines"], empty["line_count"]) == ([], 0)
    assert " · 0 lines · " in empty["verdict"]


def test_a_very_long_line_is_cut_on_screen_and_kept_whole_in_the_log(py: str, scratch: Path) -> None:
    r = go(py, scratch, "--text", "python3", "-c", "print('x' * 300000)")
    out = r.stdout.splitlines()
    assert out[2].startswith("x" * 200 + " …[cut ")
    log = Path(VERDICT_RE.match(out[1]).group(5))  # type: ignore[union-attr]
    assert log.read_text() == "x" * 300000 + "\n"


def test_manifest_lists_the_error_patterns(py: str, scratch: Path) -> None:
    doc = doc_of(go(py, scratch, "--agent-info"))
    assert "error" in doc["error_patterns"] and "Traceback" in doc["error_patterns"]
