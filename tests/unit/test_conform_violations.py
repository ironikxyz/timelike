"""Each conformance check must be able to fail (lore cross-stack P004: a check never seen failing
proves nothing). One hand-written tool conforms fully; each case breaks exactly one thing, and
timelike-conform must name the check that thing belongs to.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from test_conform import TOOLS_DIR, conform, env_for, install

TEMPLATE = r"""
import json, os, sys, time
NAME = "timelike-probe"
MUT = {mut!r}
args = sys.argv[1:]

def event(code, n=1):
    if MUT == "no_event":
        return
    root = os.environ["TIMELIKE_SCRATCH_ROOT"]
    session = os.environ["TIMELIKE_SESSION"]
    d = os.path.join(root, session)
    os.makedirs(d, mode=0o700, exist_ok=True)
    line = json.dumps({{"v": 1, "tool": NAME, "args": args, "cwd": os.getcwd(), "exit": code,
                       "duration_ms": 0, "session": session}}) + "\n"
    with open(os.path.join(d, "events.jsonl"), "a") as f:
        f.write(line * (2 if MUT == "two_events" else 1))

def done(code):
    event(code)
    sys.exit(code)

if "--help" in args:
    print(f"{{NAME}}: probe [help]")
    print("\x1b[1musage\x1b[0m: timelike-probe" if MUT == "ansi" else "usage: timelike-probe")
    done(0)

if "--agent-info" in args:
    m = {{"tool": NAME, "target": "manifest", "scope": "agent-info", "contract": 1, "summary": "probe",
         "usage": NAME, "flags": ["--agent-info", "--help", "--json", "--limit", "--text", "--verbose"],
         "exit_codes": {{"0": "ok", "1": "failure", "2": "usage"}}, "mutating": False,
         "destructive": False, "reads_stdin": False, "probe": []}}
    if MUT == "manifest_missing":
        del m["summary"]
    if MUT == "manifest_codes":
        m["exit_codes"]["42"] = "odd"
    if MUT == "manifest_flags":
        m["flags"].remove("--limit")
    if MUT == "manifest_tool":
        m["tool"] = "someone-else"
    if MUT == "manifest_contract":
        m["contract"] = 2
    if MUT == "manifest_mutating":
        m["mutating"] = True
    if MUT == "manifest_probe":
        m["probe"] = "not-a-list"
    if MUT.startswith("pass_"):
        m["passes_exit"] = "yes" if MUT == "pass_flag_str" else True
    if MUT.startswith("env_"):
        m["exit_codes"]["4"] = "confirm"
        m["envelopes"] = ["grant_required"] if MUT.startswith("env_grant") else ["confirmation_required"]
        if MUT.startswith("env_confirm"):
            m["mutating"] = True
            m["flags"].append("--yes")
        if MUT == "env_grant_undeclared":
            m["envelopes"] = []
    if MUT == "manifest_envelopes":
        m["envelopes"] = ["please_confirm"]
    if MUT == "manifest_envelopes_mutating":
        m["envelopes"] = ["confirmation_required"]  # but not mutating
    if MUT.startswith("rule9_"):
        # discovery revision 13: edit's shape, then each way of getting it wrong (all C2)
        m.update(mutating=True, confirm_protocol=False, destructive=True, dry_run=True)
        m["flags"].append("--dry-run")
        if MUT == "rule9_no_dry_run":
            m.update(destructive=False, dry_run=False)
            m["flags"].remove("--dry-run")
        if MUT == "rule9_yes_without_confirm":
            m["flags"].append("--yes")
        if MUT == "rule9_confirm_not_mutating":
            m.update(mutating=False, confirm_protocol=True, envelopes=["confirmation_required"])
            m["flags"].append("--yes")
        if MUT == "rule9_dry_run_disagrees":
            m["flags"].remove("--dry-run")
            m["destructive"] = False
        if MUT == "rule9_envelope_not_confirming":
            m["envelopes"] = ["confirmation_required"]
        if MUT == "rule9_not_bool":
            m["confirm_protocol"] = "no"
    if MUT == "manifest_order":
        m = dict(reversed(list(m.items())))
    print("not json" if MUT == "manifest_text" else json.dumps(m))
    done(0)

known = {{"--json", "--text", "--limit", "--verbose"}}
bad = [a for a in args if a.startswith("--") and a not in known]
if bad:
    if "--json" in args and MUT != "json_error_text":
        print(json.dumps({{"tool": NAME, "error": "unknown flag", "code": 2, "remediation": "see --help"}}),
              file=sys.stderr)
    else:
        print("error: unknown flag (code 2) — see --help", file=sys.stderr)
    done(2)

if MUT.startswith("pass_") and args[-3:] == ["sh", "-c", "exit 42"]:
    # the C6 pass-through probe (discovery revision 9): run the command, report it, pass its exit on
    doc = {{"tool": NAME, "target": "sh -c 'exit 42'", "scope": "run", "verdict": "command exited 42",
           "exit": 42, "cause": "command", "command_exit": 42}}
    if MUT == "pass_no_command_exit":
        del doc["command_exit"]
    if MUT == "pass_wrong_cause":
        doc["cause"] = "timeout"
    if MUT == "pass_vague_verdict":
        doc["verdict"] = "command failed"
    print(json.dumps(doc))
    done(1 if MUT == "pass_exit_1" else 42)
if MUT == "exit_42":
    done(42)
if "--text" in args:
    print("no header here" if MUT == "text_header" else f"{{NAME}}: probe [probe]")
    done(0)
if MUT.startswith("env_") and "--json" in args:
    # the C3 probe meets the exit-4 path (discovery revision 10): one envelope on stdout, exit 4
    extend = "docker exec timelike-adele adeled extend demo ports 22"
    if MUT.startswith("env_grant"):
        env = {{"tool": NAME, "target": "standin.box", "scope": "create", "status": "grant_required",
               "grant": "demo", "limit": {{"name": "ports", "allowed": "8080", "needed": "22"}},
               "extend": extend, "extend_by": "operator", "performed": False,
               "request": {{"capability": "standin.box", "action": "create"}}}}
    else:
        env = {{"tool": NAME, "target": "thing", "scope": "all", "status": "confirmation_required",
               "plan": ["delete thing"], "confirm": "timelike-probe --json --yes"}}
    if MUT == "env_grant_with_confirm":
        env["confirm"] = extend  # the operator's command, where the agent's habit runs it
    if MUT == "env_confirm_other_command":
        env["confirm"] = "rm -rf /tmp/thing"
    if MUT == "env_confirm_chained":
        env["confirm"] = "timelike-probe --yes; rm -rf /tmp/thing"
    if MUT == "env_grant_no_limit":
        del env["limit"]
    if MUT == "env_grant_extend_by_agent":
        env["extend_by"] = "agent"
    if MUT == "env_grant_performed":
        env["performed"] = True
    if MUT == "env_grant_status":
        env["status"] = "denied"
    print("beyond the grant" if MUT == "env_grant_text" else json.dumps(env))
    done(4)
if MUT == "json_text":
    print("plain words")
elif MUT == "json_keys":
    print(json.dumps({{"verdict": "ok", "tool": NAME, "target": "t", "scope": "s"}}))
else:
    print(json.dumps({{"tool": NAME, "target": "probe", "scope": "probe"}}))
done(0)
"""

CASES = {
    "none": set(),
    "manifest_missing": {"C2"},
    "manifest_codes": {"C2"},
    "manifest_flags": {"C2"},
    "manifest_tool": {"C2"},
    "manifest_contract": {"C2"},
    "manifest_mutating": {"C2"},  # declares mutating but offers no --yes
    "manifest_probe": {"C2"},
    "manifest_order": {"C2"},
    "manifest_text": {"C2"},
    "json_text": {"C3"},
    "json_keys": {"C3"},
    "text_header": {"C4"},
    "json_error_text": {"C5"},
    "exit_42": {"C3", "C4", "C6"},  # the probe runs exit outside the vocabulary
    # discovery revision 9: pass-through is exercised, and each way of getting it wrong is C6
    "pass_ok": set(),
    "pass_exit_1": {"C6"},  # declares pass-through, but swallows the command's 42 into its own 1
    "pass_no_command_exit": {"C6"},
    "pass_wrong_cause": {"C6"},
    "pass_vague_verdict": {"C6"},
    "pass_flag_str": {"C2"},  # passes_exit must be a boolean
    # discovery revision 10: exit 4's two envelopes (C9). The negative rule — an operator's command
    # never in a field the agent's habit runs — must be seen failing, not only passing (P005)
    "env_grant_ok": set(),
    "env_confirm_ok": set(),
    "env_grant_with_confirm": {"C9"},
    "env_confirm_other_command": {"C9"},
    "env_confirm_chained": {"C9"},
    "env_grant_undeclared": {"C9"},
    "env_grant_no_limit": {"C9"},
    "env_grant_extend_by_agent": {"C9"},
    "env_grant_performed": {"C9"},
    "env_grant_status": {"C9"},
    "env_grant_text": {"C3", "C9"},
    "manifest_envelopes": {"C2"},
    # discovery revision 13: confirm_protocol and rule 8 (quality-standards § Output contract)
    "rule9_edit_ok": set(),
    "rule9_no_dry_run": {"C2"},  # mutating, not confirmed, and no --dry-run: the ruling's negative case
    "rule9_yes_without_confirm": {"C2"},
    "rule9_confirm_not_mutating": {"C2"},
    "rule9_dry_run_disagrees": {"C2"},
    "rule9_envelope_not_confirming": {"C2"},
    "rule9_not_bool": {"C2"},
    "manifest_envelopes_mutating": {"C2"},
    "ansi": {"C8"},
    "two_events": {"C7"},
    "no_event": {"C7"},
}


def make(tmp_path: Path, mut: str) -> Path:
    d = tmp_path / "probe"
    d.mkdir()
    p = d / "timelike-probe"
    p.write_text(f"#!{sys.executable}\n" + TEMPLATE.format(mut=mut))
    p.chmod(0o755)
    return d


@pytest.mark.parametrize(("mut", "expected"), sorted(CASES.items()))
def test_each_check_can_fail(mut: str, expected: set[str], tmp_path: Path, scratch: Path) -> None:
    probe = make(tmp_path, mut)
    conf = tmp_path / "conf"
    install(TOOLS_DIR / "timelike-conform", conf)
    env = env_for(scratch, [probe], on_path=[probe, conf])
    r = conform(env, "--json")
    doc = json.loads(r.stdout)
    found = {f["check"] for f in doc["failures"] if f["tool"] == "timelike-probe"}
    if not expected:
        assert r.returncode == 0, doc["failures"]
        assert found == set()
    else:
        assert r.returncode == 1
        assert expected <= found, (mut, found, doc["failures"])
        assert found <= expected | {"C6"}, (mut, found)


def test_missing_bin_dir_is_reported(tmp_path: Path, scratch: Path) -> None:
    conf = tmp_path / "conf"
    install(TOOLS_DIR / "timelike-conform", conf)
    ghost = tmp_path / "ghost"
    r = conform(env_for(scratch, [conf, ghost], on_path=[conf, ghost]), "--json")
    assert r.returncode == 1
    assert any("does not exist" in f["detail"] for f in json.loads(r.stdout)["failures"])


@pytest.mark.parametrize("value", ["abc", "-3", "0"])
def test_invalid_probe_limit_falls_back_to_default(value: str, tmp_path: Path, scratch: Path) -> None:
    probe = make(tmp_path, "none")
    conf = tmp_path / "conf"
    install(TOOLS_DIR / "timelike-conform", conf)
    env = env_for(scratch, [probe], on_path=[probe, conf], TIMELIKE_CONFORM_TIMEOUT=value)
    assert conform(env, "--json").returncode == 0


@pytest.mark.parametrize(("interpreter", "rc"), [("missing", 127), ("not-executable", 126)])
def test_a_tool_that_cannot_execute_is_named_and_the_others_still_judged(
    interpreter: str, rc: int, tmp_path: Path, scratch: Path
) -> None:
    """Slice 1 (T059): an exec failure is that tool's failure, never a crash of the whole check.

    The tool itself is executable (so it is a tool on PATH); its shebang names an interpreter that
    does not exist (ENOENT) or is not executable (EACCES).
    """
    good = make(tmp_path, "none")
    bad = tmp_path / "bad"
    bad.mkdir()
    interp = tmp_path / "interp"
    if interpreter == "not-executable":
        interp.write_text("#!/bin/sh\n")
        interp.chmod(0o644)
    tool = bad / "timelike-broken"
    tool.write_text(f"#!{interp}\nprint('never runs')\n")
    tool.chmod(0o755)
    conf = tmp_path / "conf"
    install(TOOLS_DIR / "timelike-conform", conf)
    r = conform(env_for(scratch, [good, bad], on_path=[good, bad, conf]), "--json")
    assert r.returncode == 1
    assert "internal error" not in r.stderr
    doc = json.loads(r.stdout)
    broken = [f for f in doc["failures"] if f["tool"] == "timelike-broken"]
    assert {"C1", "C6"} <= {f["check"] for f in broken}
    assert any(f"exited {rc}" in f["detail"] for f in broken)
    assert not [f for f in doc["failures"] if f["tool"] == "timelike-probe"]
