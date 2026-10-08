"""agentio against the output contract, rule by rule.

Source of truth: .specswarm/features/001-agent-shell-baseline/contracts/output-contract.md.
Each test names the rule it holds agentio to. Tools run as subprocesses (see conftest.py).
"""

from __future__ import annotations

import json
import os
import re
import stat
from collections.abc import Callable
from pathlib import Path
from typing import Any

import agentio
import pytest
import schema
from conftest import base_env, events, run

HEADER_RE = re.compile(r"^[a-z][a-z0-9-]*: .+ \[[^]]+\]$")
OMISSION_RE = re.compile(r"^… omitted (\d+) lines \((\d+) bytes\) — full output: (\S+); more: (.+)$")
TEXT_ERROR_RE = re.compile(r"^error: .+ \(code (\d+)\) — .+$")
ISO_TS_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}")

BODY = """
if args.boom:
    raise RuntimeError("kaboom")
if args.fail:
    raise agentio.ToolError(1, "the thing failed", "run it again with --verbose")
lines = [f"line {i}" for i in range(args.lines)]
return agentio.Result(target="thing", scope="all", verdict="ok", lines=lines, data={"count": len(lines)})
"""

ToolMaker = Callable[..., Path]


@pytest.fixture
def tool(make_tool: ToolMaker) -> Path:
    return make_tool("sample", BODY)


def go(py: str, tool: Path, scratch: Path, *args: str, **env: str) -> Any:
    return run([py, str(tool), *args], base_env(scratch, **env))


# ── rule 1: structured when piped, text on a terminal, flags override ──────────────────────────


def test_rule1_pipe_defaults_to_json(py: str, tool: Path, scratch: Path) -> None:
    r = go(py, tool, scratch)
    assert r.returncode == 0, r.stderr
    doc = json.loads(r.stdout)
    assert list(doc)[:3] == ["tool", "target", "scope"]
    assert doc["tool"] == "sample"


def test_rule1_text_flag_forces_text_when_piped(py: str, tool: Path, scratch: Path) -> None:
    r = go(py, tool, scratch, "--text", "--lines", "2")
    assert r.returncode == 0
    assert r.stdout.splitlines()[0] == "sample: thing [all]"
    assert "line 1" in r.stdout


def test_rule1_json_flag_forces_json(py: str, tool: Path, scratch: Path) -> None:
    r = go(py, tool, scratch, "--json")
    assert json.loads(r.stdout)["verdict"] == "ok"


# ── rules 2 and 3: cap, omission line, never middle-truncate ───────────────────────────────────


def test_rule2_default_cap_and_omission_line(py: str, tool: Path, scratch: Path) -> None:
    r = go(py, tool, scratch, "--text", "--lines", "500")
    out = r.stdout.splitlines()
    assert len(out) <= 200 + 8
    m = OMISSION_RE.match(out[-1])
    assert m, out[-1]
    omitted, _bytes, full, more = m.groups()
    assert int(omitted) > 0
    assert Path(full).read_text().count("\n") >= 500
    assert "--limit 0" in more


def test_rule2_limit_zero_is_uncapped(py: str, tool: Path, scratch: Path) -> None:
    r = go(py, tool, scratch, "--text", "--lines", "500", "--limit", "0")
    assert "line 499" in r.stdout
    assert "omitted" not in r.stdout


def test_rule2_env_limit(py: str, tool: Path, scratch: Path) -> None:
    r = go(py, tool, scratch, "--text", "--lines", "100", TIMELIKE_OUTPUT_LIMIT="10")
    assert OMISSION_RE.match(r.stdout.splitlines()[-1])
    assert len(r.stdout.splitlines()) <= 10 + 8


def test_rule3_truncation_order(py: str, make_tool: ToolMaker, scratch: Path) -> None:
    body = """
lines = [f"line {i}" for i in range(300)]
return agentio.Result(target="thing", scope="all", verdict="failed: 2 errors", lines=lines,
                      errors=["first error", "second error"], exit=1)
"""
    t = make_tool("ordered", body)
    r = go(py, t, scratch, "--text", "--limit", "20")
    out = r.stdout.splitlines()
    assert r.returncode == 1
    assert out[0] == "ordered: thing [all]"
    assert out[1] == "verdict: failed: 2 errors"
    assert out[2] == "line 0"  # head
    i_err = out.index("first error")
    i_tail = out.index("line 299")
    i_exit = out.index("exit: 1")
    i_full = next(i for i, x in enumerate(out) if x.startswith("full output: "))
    assert 2 < i_err < i_tail < i_exit < i_full < len(out) - 1
    assert OMISSION_RE.match(out[-1])


def test_rule2_json_truncated_object_stays_valid(py: str, tool: Path, scratch: Path) -> None:
    r = go(py, tool, scratch, "--json", "--lines", "500", "--limit", "20")
    doc = json.loads(r.stdout)
    tr = doc["truncated"]
    assert tr["omitted_lines"] > 0 and tr["omitted_bytes"] > 0
    assert Path(tr["full_output"]).exists()
    assert "--limit 0" in tr["more"]


# ── rule 4: never the terminal, a pager, an editor, a prompt, or stdin ─────────────────────────


def test_rule4_no_tty_or_stdin_access(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], scratch: Path
) -> None:
    import builtins

    import agentio

    monkeypatch.setenv("TIMELIKE_SCRATCH_ROOT", str(scratch))
    monkeypatch.setenv("TIMELIKE_SESSION", "inproc")

    real_open, real_os_open = builtins.open, os.open

    def guard(path: Any, *a: Any, **k: Any) -> Any:
        if str(path) == "/dev/tty":
            raise AssertionError("opened /dev/tty")
        return real_open(path, *a, **k)

    def guard_os(path: Any, *a: Any, **k: Any) -> Any:
        if str(path) == "/dev/tty":
            raise AssertionError("os.open(/dev/tty)")
        return real_os_open(path, *a, **k)

    class NoStdin:
        def read(self, *a: Any) -> str:
            raise AssertionError("read stdin")

        readline = read

        def isatty(self) -> bool:
            raise AssertionError("isatty on stdin")

        def fileno(self) -> int:
            raise AssertionError("stdin fileno")

    monkeypatch.setattr(builtins, "open", guard)
    monkeypatch.setattr(os, "open", guard_os)
    monkeypatch.setattr("sys.stdin", NoStdin())
    tool = agentio.Tool(name="inproc", target="x", summary="in-process")
    with pytest.raises(SystemExit) as e:
        agentio.run(tool, lambda a, c: agentio.Result("x", "y", "ok"), argv=["--json"])
    assert e.value.code == 0
    assert json.loads(capsys.readouterr().out)["tool"] == "inproc"


# ── rule 5: exit vocabulary; an unexpected exception is exit 1 with a structured error ─────────


def test_rule5_tool_error_is_exit_1(py: str, tool: Path, scratch: Path) -> None:
    r = go(py, tool, scratch, "--fail")
    assert r.returncode == 1
    assert TEXT_ERROR_RE.match(r.stderr.strip())


def test_rule5_uncaught_exception_is_exit_1_not_a_bare_traceback(py: str, tool: Path, scratch: Path) -> None:
    r = go(py, tool, scratch, "--boom", "--json")
    assert r.returncode == 1
    err = json.loads(r.stderr)
    assert schema.errors(err, schema.load("error.schema.json")) == []
    assert "kaboom" in err["error"]
    assert "Traceback" not in r.stderr


def test_rule5_usage_error_is_exit_2(py: str, tool: Path, scratch: Path) -> None:
    r = go(py, tool, scratch, "--no-such-flag")
    assert r.returncode == 2
    m = TEXT_ERROR_RE.match(r.stderr.strip())
    assert m and m.group(1) == "2"


def test_rule5_exit_codes_constant_is_the_vocabulary() -> None:
    import agentio

    assert set(agentio.EXIT_CODES) == {0, 1, 2, 3, 4, 124}


# ── rule 6: --help ≤ 40 lines, --json, --agent-info ────────────────────────────────────────────


def test_rule6_help_at_most_40_lines_with_header(py: str, tool: Path, scratch: Path) -> None:
    r = go(py, tool, scratch, "--help")
    assert r.returncode == 0
    lines = r.stdout.splitlines()
    assert 0 < len(lines) <= 40
    assert HEADER_RE.match(lines[0]), lines[0]


def test_rule6_help_over_40_lines_is_refused(py: str, make_tool: ToolMaker, scratch: Path) -> None:
    t = make_tool("wordy", BODY, usage=[f"usage line {i}" for i in range(45)])
    r = go(py, t, scratch, "--help")
    assert r.returncode == 1  # agentio will not print a non-conforming help
    assert TEXT_ERROR_RE.match(r.stderr.strip())


def test_rule6_agent_info_validates(py: str, tool: Path, scratch: Path) -> None:
    r = go(py, tool, scratch, "--agent-info")
    assert r.returncode == 0
    doc = json.loads(r.stdout)
    assert schema.errors(doc, schema.load("agent-info.schema.json")) == []
    assert {"--help", "--json", "--text", "--agent-info", "--limit", "--verbose"} <= set(doc["flags"])
    assert "--lines" in doc["flags"]


def test_schema_keywords_are_supported() -> None:
    for name in ["event", "agent-info", "error", "confirm-envelope", "grant-envelope"]:
        used = schema.keywords(schema.load(f"{name}.schema.json"))
        assert used <= schema.SUPPORTED, used - schema.SUPPORTED


# ── rule 9: mutating without --yes exits 4 with an envelope ────────────────────────────────────


def test_rule9_confirm_envelope(py: str, make_tool: ToolMaker, scratch: Path) -> None:
    body = """
if not args.yes:
    return agentio.confirm_required(ctx, target="thing", scope="all", plan=["delete thing"])
return agentio.Result(target="thing", scope="all", verdict="deleted")
"""
    t = make_tool("mutator", body, mutating=True, destructive=True)
    r = go(py, t, scratch, "--text")  # even in text mode the envelope is JSON on stdout
    assert r.returncode == 4
    env = json.loads(r.stdout)
    assert schema.errors(env, schema.load("confirm-envelope.schema.json")) == []
    assert env["confirm"].endswith("--yes")
    assert list(env)[:4] == ["tool", "target", "scope", "status"]  # rule 12 (it was sorted before 004)
    r2 = go(py, t, scratch, "--yes", "--json")
    assert r2.returncode == 0 and json.loads(r2.stdout)["verdict"] == "deleted"
    info = json.loads(go(py, t, scratch, "--agent-info").stdout)
    assert {"--yes", "--dry-run"} <= set(info["flags"])
    assert info["envelopes"] == ["confirmation_required"]
    assert "grant" not in env  # discovery revision 10: a missing grant has its own envelope


# ── rule 9 at discovery revision 13: confirm_protocol ─────────────────────────────────────────


def test_rule9_confirm_protocol_defaults_to_mutating(py: str, make_tool: ToolMaker, scratch: Path) -> None:
    """A tool written before revision 13 keeps rule 9 whole: confirm_protocol absent means mutating."""
    t = make_tool("mutator", 'return agentio.Result(target="t", scope="s", verdict="ok")', mutating=True)
    info = json.loads(go(py, t, scratch, "--agent-info").stdout)
    assert info["confirm_protocol"] is True
    assert "--yes" in info["flags"] and info["exit_codes"]["4"].startswith("confirmation required")
    assert schema.errors(info, schema.load("agent-info.schema.json")) == []
    plain = make_tool("plain", 'return agentio.Result(target="t", scope="s", verdict="ok")')
    info = json.loads(go(py, plain, scratch, "--agent-info").stdout)
    assert info["confirm_protocol"] is False and "--yes" not in info["flags"]


def test_rule9_mutating_without_confirm_protocol(py: str, make_tool: ToolMaker, scratch: Path) -> None:
    """edit's shape: mutating, applied in one call; no --yes, no exit 4, no confirmation envelope."""
    body = 'return agentio.Result(target="t", scope="s", verdict="edited")'
    t = make_tool("editor", body, mutating=True, destructive=True, confirm_protocol=False)
    info = json.loads(go(py, t, scratch, "--agent-info").stdout)
    assert info["mutating"] is True and info["confirm_protocol"] is False
    assert info["dry_run"] is True and "--dry-run" in info["flags"]
    assert "--yes" not in info["flags"]
    assert "4" not in info["exit_codes"]
    assert info["envelopes"] == []
    assert schema.errors(info, schema.load("agent-info.schema.json")) == []
    r = go(py, t, scratch, "--json")
    assert r.returncode == 0 and json.loads(r.stdout)["verdict"] == "edited"
    r = go(py, t, scratch, "--yes", "--json")  # a --yes that would do nothing is refused (exit 2)
    assert r.returncode == 2


def test_rule9_undeclared_confirmation_is_refused(py: str, make_tool: ToolMaker, scratch: Path) -> None:
    """A tool with confirm_protocol=False cannot print a confirmation envelope: internal error, not 4."""
    body = 'return agentio.confirm_required(ctx, target="t", scope="s", plan=["x"])'
    t = make_tool("editor", body, mutating=True, destructive=True, confirm_protocol=False)
    r = go(py, t, scratch, "--json")
    assert r.returncode == 1 and r.stdout == ""
    assert "confirmation_required" in r.stderr


def test_rule9_confirm_protocol_needs_mutating() -> None:
    with pytest.raises(ValueError, match="needs mutating=True"):
        agentio.Tool("x", "t", "s", confirm_protocol=True)
    assert agentio.Tool("x", "t", "s", mutating=True, confirm_protocol=True).confirm_protocol is True
    assert agentio.Tool("x", "t", "s", mutating=True).confirm_protocol is True
    assert agentio.Tool("x", "t", "s").confirm_protocol is False


def test_manifest_dry_run_follows_the_flag(py: str, make_tool: ToolMaker, scratch: Path) -> None:
    body = 'return agentio.Result(target="t", scope="s", verdict="ok")'
    for kwargs, want in (({}, False), ({"destructive": True}, True)):
        info = json.loads(go(py, make_tool("t", body, **kwargs), scratch, "--agent-info").stdout)
        assert info["dry_run"] is want and ("--dry-run" in info["flags"]) is want


def test_confirm_required_takes_no_grant(py: str, make_tool: ToolMaker, scratch: Path) -> None:
    """The confirm envelope's `grant` field is removed (FOR-MENTOR Item 13): no caller ever set it."""
    body = """
return agentio.confirm_required(ctx, target="thing", scope="all", plan=["x"], grant="demo")
"""
    t = make_tool("mutator", body, mutating=True)
    r = go(py, t, scratch, "--json")
    assert r.returncode == 1
    assert "unexpected keyword argument 'grant'" in r.stderr


# ── discovery revision 10: exit 4's grant envelope, the operator's command ─────────────────────

GRANT_BODY = """
return agentio.grant_required(
    ctx, target="standin.box", scope="create", grant="demo",
    limit={"name": "ttl", "allowed": "1h", "needed": "2h"},
    extend="docker exec timelike-adele adeled extend demo ttl 2h",
    request={"capability": "standin.box", "action": "create"}, ledger_id=3,
)
"""


@pytest.mark.parametrize("mode", ["--text", "--json"])
def test_grant_envelope(mode: str, py: str, make_tool: ToolMaker, scratch: Path) -> None:
    t = make_tool("broker", GRANT_BODY, grant_envelope=True)
    r = go(py, t, scratch, mode)
    assert r.returncode == 4
    env = json.loads(r.stdout)  # JSON in every mode, like the confirmation envelope
    assert schema.errors(env, schema.load("grant-envelope.schema.json")) == []
    assert schema.errors(env, schema.load("confirm-envelope.schema.json")) != []  # told apart by status
    assert list(env)[:3] == ["tool", "target", "scope"]
    assert (env["status"], env["extend_by"], env["performed"]) == ("grant_required", "operator", False)
    assert env["limit"] == {"name": "ttl", "allowed": "1h", "needed": "2h"}
    assert "confirm" not in env
    info = json.loads(go(py, t, scratch, "--agent-info").stdout)
    assert info["envelopes"] == ["grant_required"]
    assert info["mutating"] is False and "--yes" not in info["flags"]
    assert "4" in info["exit_codes"]
    assert schema.errors(info, schema.load("agent-info.schema.json")) == []


def test_grant_envelope_needs_the_declaration(py: str, make_tool: ToolMaker, scratch: Path) -> None:
    t = make_tool("undeclared", GRANT_BODY)
    r = go(py, t, scratch, "--json")
    assert r.returncode == 1
    assert r.stdout == ""
    assert "grant_envelope=True" in r.stderr


def test_an_undeclared_envelope_is_never_printed(py: str, make_tool: ToolMaker, scratch: Path) -> None:
    """A confirm envelope from a tool that is not mutating is an internal error, not exit 4."""
    body = """
return agentio.confirm_required(ctx, target="thing", scope="all", plan=["x"])
"""
    t = make_tool("not-mutating", body)
    r = go(py, t, scratch, "--json")
    assert r.returncode == 1
    assert r.stdout == ""
    assert "confirmation_required" in r.stderr


@pytest.mark.parametrize(
    ("change", "words"),
    [
        ('limit={"name": "ttl"}', "limit lacks"),
        ('extend=""', "extend command are required"),
        ('grant=""', "extend command are required"),
    ],
)
def test_grant_envelope_refuses_to_be_incomplete(
    change: str, words: str, py: str, make_tool: ToolMaker, scratch: Path
) -> None:
    key = change.split("=", 1)[0]
    if key == "limit":
        body = GRANT_BODY.replace('limit={"name": "ttl", "allowed": "1h", "needed": "2h"}', change)
    elif key == "extend":
        body = GRANT_BODY.replace('extend="docker exec timelike-adele adeled extend demo ttl 2h"', change)
    else:
        body = GRANT_BODY.replace('grant="demo"', change)
    t = make_tool("broker", body, grant_envelope=True)
    r = go(py, t, scratch, "--json")
    assert r.returncode == 1
    assert r.stdout == ""
    assert words in r.stderr


# ── rule 10: state only under the scratch directory ────────────────────────────────────────────


def test_rule10_scratch_dir_is_private(py: str, tool: Path, scratch: Path) -> None:
    go(py, tool, scratch)
    mode = stat.S_IMODE((scratch / "test").stat().st_mode)
    assert mode == 0o700


# ── rule 11: deterministic, no timestamps unless --verbose ─────────────────────────────────────


def test_rule11_deterministic_and_no_timestamps(py: str, tool: Path, scratch: Path) -> None:
    a = go(py, tool, scratch, "--lines", "5").stdout
    b = go(py, tool, scratch, "--lines", "5").stdout
    assert a == b
    assert not ISO_TS_RE.search(a)
    assert "duration_ms" not in a
    v = go(py, tool, scratch, "--lines", "5", "--verbose").stdout
    assert "duration_ms" in json.loads(v)


def test_rule11_json_body_keys_sorted_after_header(py: str, make_tool: ToolMaker, scratch: Path) -> None:
    body = 'return agentio.Result("t", "s", "ok", data={"zeta": 1, "alpha": 2, "mid": 3})'
    t = make_tool("sorter", body)
    keys = list(json.loads(go(py, t, scratch).stdout))
    assert keys[:3] == ["tool", "target", "scope"]
    rest = keys[3:]
    assert rest == sorted(rest)


# ── rule 12: self-labelling first line ─────────────────────────────────────────────────────────


def test_rule12_text_header(py: str, tool: Path, scratch: Path) -> None:
    first = go(py, tool, scratch, "--text").stdout.splitlines()[0]
    assert HEADER_RE.match(first)


# ── rule 13: ANSI stripped, long lines cut at COLUMNS with a byte count ────────────────────────


def test_rule13_ansi_stripped_both_modes(py: str, make_tool: ToolMaker, scratch: Path) -> None:
    body = r"""
return agentio.Result("t", "s", "ok", lines=["\x1b[31mred\x1b[0m plain"], data={"k": "\x1b[1mbold\x1b[0m"})
"""
    t = make_tool("colour", body)
    for mode in ("--text", "--json"):
        r = go(py, t, scratch, mode)
        assert "\x1b" not in r.stdout
        assert "\\u001b" not in r.stdout
    assert "red plain" in go(py, t, scratch, "--text").stdout


def test_rule13_long_lines_cut_at_columns(py: str, make_tool: ToolMaker, scratch: Path) -> None:
    t = make_tool("wide", 'return agentio.Result("t", "s", "ok", lines=["x" * 500])')
    r = go(py, t, scratch, "--text", COLUMNS="100")
    line = r.stdout.splitlines()[2]
    assert line.startswith("x" * 100)
    assert line.endswith(" …[cut 400 bytes]")
    default = go(py, t, scratch, "--text").stdout.splitlines()[2]
    assert default.endswith(" …[cut 300 bytes]")


# ── rule 14: structured errors on stderr ───────────────────────────────────────────────────────


def test_rule14_error_json_with_flag(py: str, tool: Path, scratch: Path) -> None:
    r = go(py, tool, scratch, "--fail", "--json")
    err = json.loads(r.stderr)  # exactly one JSON object
    assert schema.errors(err, schema.load("error.schema.json")) == []
    assert err["code"] == 1


def test_rule14_error_text_without_flag_even_when_piped(py: str, tool: Path, scratch: Path) -> None:
    r = go(py, tool, scratch, "--fail")
    assert len(r.stderr.strip().splitlines()) == 1
    assert TEXT_ERROR_RE.match(r.stderr.strip())


# ── rule 15: redaction is visible ──────────────────────────────────────────────────────────────


def test_rule15_redact() -> None:
    import agentio

    assert agentio.redact("hunter2", "password") == "[REDACTED:password]"
    with pytest.raises(ValueError):
        agentio.redact("x", "nonsense")


def test_rule15_secret_shaped_args_are_redacted_in_events(py: str, tool: Path, scratch: Path) -> None:
    go(py, tool, scratch, "--no-such", "--api-token=abc123")
    ev = events(scratch)[-1]
    assert "abc123" not in json.dumps(ev)
    assert "--api-token=[REDACTED:token]" in ev["args"]


# ── rule 16: one event per invocation, whatever the invocation ─────────────────────────────────


@pytest.mark.parametrize(
    ("args", "code"),
    [([], 0), (["--help"], 0), (["--agent-info"], 0), (["--fail"], 1), (["--boom"], 1), (["--nope"], 2)],
)
def test_rule16_exactly_one_event_per_invocation(
    py: str, tool: Path, scratch: Path, args: list[str], code: int
) -> None:
    before = len(events(scratch))
    r = go(py, tool, scratch, *args)
    assert r.returncode == code
    evs = events(scratch)
    assert len(evs) == before + 1
    ev = evs[-1]
    assert schema.errors(ev, schema.load("event.schema.json")) == []
    assert ev["tool"] == "sample" and ev["exit"] == code and ev["session"] == "test"
    assert ev["args"] == args


def test_fr11_event_failure_never_changes_the_result(py: str, tool: Path, tmp_path: Path) -> None:
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("a file where the scratch root should be")
    ok = run([py, str(tool), "--json"], base_env(blocker))
    assert ok.returncode == 0 and json.loads(ok.stdout)["verdict"] == "ok"
    bad = run([py, str(tool), "--fail"], base_env(blocker))
    assert bad.returncode == 1


def test_fr11_event_failure_warns_only_with_verbose(py: str, tool: Path, tmp_path: Path) -> None:
    blocker = tmp_path / "f"
    blocker.write_text("")
    quiet = run([py, str(tool)], base_env(blocker))
    assert quiet.stderr == ""
    loud = run([py, str(tool), "--verbose"], base_env(blocker))
    assert "event" in loud.stderr


# ── sessions ───────────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("bad", ["../x", "..", ".", "a/b", "", "x" * 65, "sp ace"])
def test_invalid_session_is_usage_error(py: str, tool: Path, scratch: Path, bad: str) -> None:
    r = run([py, str(tool)], base_env(scratch, session=bad))
    assert r.returncode == 2
    assert TEXT_ERROR_RE.match(r.stderr.strip())
    assert not (scratch.parent / "x").exists()


def test_default_session_when_unset(py: str, tool: Path, scratch: Path) -> None:
    env = base_env(scratch)
    del env["TIMELIKE_SESSION"]
    assert run([py, str(tool)], env).returncode == 0
    assert (scratch / "default" / "events.jsonl").exists()


# ── discovery revision 9 (feature 003): exit pass-through, the argv split, tool-supplied cut ────────

PASSER_BODY = """
cmd = args.command
code = int(cmd[0]) if cmd and cmd[0].isdigit() else 0
if args.fail:  # a pass-through tool claiming a non-vocabulary exit for a cause that is not the command
    return agentio.Result(target="x", scope="run", verdict="lie", exit=code, cause="timeout")
return agentio.Result(
    target=" ".join(cmd) or "-", scope="run", verdict=f"command exited {code}", exit=code,
    cause="command", command_exit=code, data={"argv": cmd, "lines_opt": args.lines},
)
"""


@pytest.fixture
def passer(make_tool: ToolMaker) -> Path:
    return make_tool("passer", PASSER_BODY, passes_exit=True)


def test_rev9_pass_through_tool_returns_the_commands_exit(py: str, passer: Path, scratch: Path) -> None:
    r = go(py, passer, scratch, "--json", "42")
    assert r.returncode == 42, r.stderr
    doc = json.loads(r.stdout)
    assert (doc["exit"], doc["cause"], doc["command_exit"]) == (42, "command", 42)
    ev = events(scratch)[-1]
    assert ev["exit"] == 42
    assert schema.errors(ev, schema.load("event.schema.json")) == []


def test_rev9_vocabulary_exit_from_a_pass_through_tool_still_carries_cause(
    py: str, passer: Path, scratch: Path
) -> None:
    doc = json.loads(go(py, passer, scratch, "--json", "0").stdout)
    assert (doc["exit"], doc["cause"], doc["command_exit"]) == (0, "command", 0)


def test_rev9_tool_without_pass_through_cannot_return_42(
    py: str, make_tool: ToolMaker, scratch: Path
) -> None:
    body = (
        'return agentio.Result(target="t", scope="s", verdict="v", exit=args.lines,'
        ' cause="command", command_exit=args.lines)'
    )
    liar = make_tool("liar", body)  # claims a command's exit, but passes_exit is not declared
    r = go(py, liar, scratch, "--json", "--lines", "42")
    assert r.returncode == 1
    assert "outside the contract vocabulary" in r.stderr


def test_rev9_pass_through_exit_only_with_cause_command(py: str, passer: Path, scratch: Path) -> None:
    r = go(py, passer, scratch, "--fail", "42")
    assert r.returncode == 1
    assert "outside the contract vocabulary" in r.stderr


def test_rev9_cause_and_command_exit_are_reserved(py: str, make_tool: ToolMaker, scratch: Path) -> None:
    t = make_tool("clash", 'return agentio.Result(target="t", scope="s", verdict="v", data={"cause": "x"})')
    assert go(py, t, scratch, "--json").returncode == 1


@pytest.mark.parametrize(
    ("argv", "command", "lines_opt"),
    [
        (["7", "--json", "x"], ["7", "--json", "x"], 0),  # a flag after the command is the command's
        (["--lines", "5", "--", "--weird"], ["--weird"], 5),  # `--` ends the tool's options
        (["--lines=3", "9"], ["9"], 3),
        (["--json", "--lines", "4", "sh", "-c", "exit 3"], ["sh", "-c", "exit 3"], 4),
        (["3", "--bogus"], ["3", "--bogus"], 0),
    ],
)
def test_rev9_argv_splits_at_the_command(
    py: str, passer: Path, scratch: Path, argv: list[str], command: list[str], lines_opt: int
) -> None:
    r = go(py, passer, scratch, "--json", *argv)
    doc = json.loads(r.stdout)
    assert (doc["argv"], doc["lines_opt"]) == (command, lines_opt)


def test_rev9_unknown_option_before_the_command_is_usage(py: str, passer: Path, scratch: Path) -> None:
    r = go(py, passer, scratch, "--bogus", "3")
    assert r.returncode == 2
    assert TEXT_ERROR_RE.match(r.stderr.strip()), r.stderr


def test_rev9_json_after_the_command_does_not_set_the_error_mode(
    py: str, passer: Path, scratch: Path
) -> None:
    r = go(py, passer, scratch, "--nope", "x", "--json")
    assert r.returncode == 2
    assert TEXT_ERROR_RE.match(r.stderr.strip()), r.stderr  # one text line, not a JSON object


def test_rev9_manifest_declares_pass_through(py: str, passer: Path, tool: Path, scratch: Path) -> None:
    doc = json.loads(go(py, passer, scratch, "--agent-info").stdout)
    assert doc["passes_exit"] is True
    assert schema.errors(doc, schema.load("agent-info.schema.json")) == []
    assert "passes_exit" not in json.loads(go(py, tool, scratch, "--agent-info").stdout)
    assert "the command's own exit" in go(py, passer, scratch, "--help").stdout


CUT_BODY = """
cut = agentio.Cut(
    [("lines 1–2 of 10", ["a", "b"]), ("lines 9–10 of 10", ["y", "\\x1b[31mz\\x1b[0m"])],
    omitted_lines=6, omitted_bytes=30, full_output="/x/log", more="sed -n '3,8p' /x/log",
)
return agentio.Result(target="t", scope="cut", verdict="cut by the tool", cut=cut)
"""


def test_rev9_tool_supplied_cut_text_order(py: str, make_tool: ToolMaker, scratch: Path) -> None:
    t = make_tool("cutter", CUT_BODY)
    out = go(py, t, scratch, "--text", "--limit", "1").stdout.splitlines()  # no re-cap by agentio
    assert out[:9] == [
        "cutter: t [cut]",
        "verdict: cut by the tool",
        "── lines 1–2 of 10 ──",
        "a",
        "b",
        "── lines 9–10 of 10 ──",
        "y",
        "z",
        "more: sed -n '3,8p' /x/log",
    ]
    assert out[9:11] == ["exit: 0", "full output: /x/log"]
    m = OMISSION_RE.match(out[11])
    assert m
    assert m.groups() == ("6", "30", "/x/log", "sed -n '3,8p' /x/log")
    assert len(out) == 12


def test_rev9_tool_supplied_cut_json(py: str, make_tool: ToolMaker, scratch: Path) -> None:
    t = make_tool("cutter", CUT_BODY)
    doc = json.loads(go(py, t, scratch, "--json").stdout)
    assert doc["lines"] == ["a", "b", "y", "z"]
    assert doc["sections"] == [
        {"label": "lines 1–2 of 10", "count": 2},
        {"label": "lines 9–10 of 10", "count": 2},
    ]
    assert doc["truncated"] == {
        "omitted_lines": 6,
        "omitted_bytes": 30,
        "full_output": "/x/log",
        "more": "sed -n '3,8p' /x/log",
    }
    assert "cause" not in doc  # only a tool that sets a cause reports one
