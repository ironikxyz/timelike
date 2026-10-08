"""journal (feature 009, slice 1, T003) against contracts/journal-cli.md, data-model.md, research R1-R5, R7.

Written from the contract alone, before the tool. Every record the journal reads is made by running the
real writers under a temporary scratch root (P005):
- tool events by running the real tools (`run`, `snapshot`, `view`, `adele`) as subprocesses;
- shell entries by running `bash -c` / `bash -lc` with 001's hook as BASH_ENV and the trap file at
  TIMELIKE_JOURNAL_EXIT (R1). Inside those shells a tool is reached by its name through a two-line `sh`
  shim in the lab's bin directory, which `exec`s the repository's tool, so the process keeps the pid the
  shell forked and its event's `ppid` is the shell's `pid`, as in the image.
Only malformed and foreign lines are written by hand, and the ledger, which is the operator's piped input
(R4: `adeled ledger --json`, one JSON array).

Expected values come from the state the test made, never from the journal's own words (P004): the exits
the subprocesses returned, the ids and log paths the tools reported, and the times and pids in the records
they wrote.

Most calls read the fixtures' session `work` with `--session work` from the session `reader`, so the
journal's own session event (one per call) never lands among the entries it is asked about. The tests of
the default session read the current one and account for that event from the record.

Ambiguities settled here (the contract is the authority; the report lists them):
- A permission-unreadable events.jsonl / shell.jsonl is exit 0, named in the verdict (contract § Refusals,
  more specific than the manifest's "1 a record … could not be read as a whole").
- The shell record's times are `start_us`/`end_us` (data-model, the plan's), not FR-7's `start_ms`.
- The style of a nested child in JSON, the agent of an agentless entry (`-`, "" or null) and the scope
  when the session holds fewer entries than the tail are not pinned.
- The verdict's counts are of the entries shown (the contract's example: 20 shown = 14 + 5 + 1).
"""

from __future__ import annotations

import json
import math
import os
import re
import shlex
import socket
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO, TOOLS_DIR, base_env
from test_agentio_redaction import aws, gcp, gh, github_fine_grained, gitlab, jwt, npm, openai, stripe

JOURNAL = TOOLS_DIR / "journal"
ETC = REPO / "image" / "rootfs" / "etc" / "timelike"
SHELL_ENV = ETC / "shell-env.bash"
JOURNAL_EXIT = ETC / "journal-exit.bash"
SHIMMED = ("adele", "edit", "run", "snapshot", "undo", "view")
Proc = subprocess.CompletedProcess[str]

pytestmark = pytest.mark.skipif(not JOURNAL.exists(), reason="tools/bin/journal is not written yet (T005)")
needs_hook = pytest.mark.skipif(
    not JOURNAL_EXIT.exists(), reason="image/rootfs/etc/timelike/journal-exit.bash is not written yet (T002)"
)

ISO_MS = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}(Z|\+00:00)$")
# An entry's text line: the time, an optional [agent/session] label, then the kind (indented when nested).
ENTRY = re.compile(r"^(\d{2}:\d{2}:\d{2}\.\d{3})\s+(\[([^/\]]*)/([^\]]*)\]\s+)?(tool|shell|grant)\b")
DATE_LINE = re.compile(r"^── (\d{4}-\d{2}-\d{2}) ──$")
ENTRY_KEYS = {
    "start", "end", "kind", "style", "agent", "session", "command", "exit", "duration_ms", "ref", "pid",
    "ppid", "children", "collapsed",
}  # fmt: skip
DATA_KEYS = {"session", "sessions", "agents", "total", "shown", "counts", "unreadable", "sources", "entries"}


# ── the lab: home, workspace, scratch root and a bin of shims, as siblings in tmp_path ──────────


@dataclass
class Lab:
    tmp: Path
    home: Path
    ws: Path  # every call's working directory
    scratch: Path  # TIMELIKE_SCRATCH_ROOT
    bin: Path  # shims: `snapshot` etc. by name, for the shells

    def env(self, session: str, agent: str | None = None, **extra: str) -> dict[str, str]:
        env = base_env(self.scratch, session, HOME=str(self.home), COLUMNS="1000", **extra)
        env["PATH"] = f"{self.bin}:{env['PATH']}"
        if agent is not None:
            env["TIMELIKE_AGENT"] = agent
        return env

    def events(self, session: str) -> list[dict[str, Any]]:
        return read_jsonl(self.scratch / session / "events.jsonl")

    def shells(self, session: str) -> list[dict[str, Any]]:
        return read_jsonl(self.scratch / session / "shell.jsonl")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


@pytest.fixture
def lab(tmp_path: Path) -> Lab:
    tmp = Path(os.path.realpath(tmp_path))  # real paths, so the no-records verdict compares exactly
    lab = Lab(tmp, tmp / "home", tmp / "ws", tmp / "scratch", tmp / "bin")
    for d in (lab.home, lab.ws, lab.bin):
        d.mkdir()
    for name in SHIMMED:
        shim = lab.bin / name
        tool = shlex.quote(str(TOOLS_DIR / name))
        shim.write_text(f'#!/bin/sh\nexec {shlex.quote(sys.executable)} {tool} "$@"\n')
        shim.chmod(0o755)
    (lab.ws / "x").write_text("one\ntwo\n")
    return lab


# ── running the writers and the reader ──────────────────────────────────────────────────────────


def tool(lab: Lab, session: str, name: str, *args: str, agent: str | None = None, **env: str) -> Proc:
    """A real tool, run directly (no shell): its event's ppid is this test process."""
    return subprocess.run(
        [sys.executable, str(TOOLS_DIR / name), *args],
        cwd=str(lab.ws),
        env=lab.env(session, agent, **env),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=30,
        start_new_session=True,
    )


def shell(lab: Lab, session: str, cmd: str, *, login: bool = False, agent: str | None = None) -> Proc:
    """`bash -c CMD` (or `bash -lc`) with 001's hook and the journal's trap file (R1)."""
    env = lab.env(session, agent, BASH_ENV=str(SHELL_ENV), TIMELIKE_JOURNAL_EXIT=str(JOURNAL_EXIT))
    return subprocess.run(
        ["bash", "-lc" if login else "-c", cmd],
        cwd=str(lab.ws),
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=30,
        start_new_session=True,
    )


def journal(
    lab: Lab,
    *args: str,
    session: str = "reader",
    agent: str | None = None,
    stdin: str | int | None = None,
) -> Proc:
    kw: dict[str, Any] = (
        {"input": stdin} if isinstance(stdin, str) else {"stdin": stdin or subprocess.DEVNULL}
    )
    return subprocess.run(
        [sys.executable, str(JOURNAL), *args],
        cwd=str(lab.ws),
        env=lab.env(session, agent),
        capture_output=True,
        text=True,
        timeout=30,
        start_new_session=True,
        **kw,
    )


def said(r: Proc) -> str:
    return f"exit {r.returncode}\n{r.stdout}\n{r.stderr}"


def doc_of(r: Proc) -> dict[str, Any]:
    try:
        d: dict[str, Any] = json.loads(r.stdout)
    except ValueError:
        raise AssertionError(f"stdout is not one JSON object:\n{said(r)}") from None
    return d


def ok(r: Proc) -> dict[str, Any]:
    """A result with exit 0 and the data the contract lists (§ JSON)."""
    assert r.returncode == 0, said(r)
    d = doc_of(r)
    assert list(d)[:3] == ["tool", "target", "scope"] and d["tool"] == "journal", d
    assert d["exit"] == 0
    missing = DATA_KEYS - set(d)
    assert not missing, f"data lacks {sorted(missing)}"
    for e in d["entries"]:
        assert set(e) >= ENTRY_KEYS, f"entry lacks {sorted(ENTRY_KEYS - set(e))}: {e}"
    return d


def text_entries(r: Proc) -> list[re.Match[str]]:
    return [m for m in map(ENTRY.match, r.stdout.splitlines()) if m]


def ms_of(iso: str) -> int:
    assert ISO_MS.match(iso), iso
    return round(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp() * 1000)


def iso_s(ms: int) -> str:
    """RFC 3339 to the second, as 004's ledger writes `at`."""
    return datetime.fromtimestamp(ms / 1000, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def hhmmss(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, UTC).strftime("%H:%M:%S.") + f"{ms % 1000:03d}"


def tool_start(ev: dict[str, Any]) -> int:
    """R3: a tool event's start is t_ms - duration_ms."""
    assert "t_ms" in ev, f"agentio wrote no t_ms (T001): {ev}"
    return int(ev["t_ms"]) - int(ev["duration_ms"])


def shell_start(rec: dict[str, Any]) -> int:
    return int(rec["start_us"]) // 1000


def command_of(name: str, *args: str) -> str:
    return shlex.join([name, *args])


def commands(d: dict[str, Any]) -> list[str]:
    return [e["command"] for e in d["entries"]]


def by_kind(d: dict[str, Any], kind: str) -> list[dict[str, Any]]:
    return [e for e in d["entries"] if e["kind"] == kind]


def blank(v: Any) -> bool:
    return v in (None, "", "—")


# ── the manifest and help ──────────────────────────────────────────────────────────────────────


def test_agent_info_declares_the_contract_manifest(lab: Lab) -> None:
    r = journal(lab, "--agent-info")
    assert r.returncode == 0, said(r)
    m = doc_of(r)
    assert (m["tool"], m["target"], m["scope"]) == ("journal", "manifest", "agent-info")
    assert m["mutating"] is False
    assert m["confirm_protocol"] is False
    assert m["destructive"] is False
    assert m["reads_stdin"] is True
    assert m["probe"] == []
    assert set(m["exit_codes"]) == {"0", "1", "2", "3"}
    assert m["tail"] == 20
    assert m["sources"] == ["events.jsonl", "shell.jsonl", "ledger (stdin or file)"]
    assert m["captures"] == ["bash -c", "bash -lc"]
    assert m["not_captured"] == [
        "sh -c",
        "interactive shells",
        "a command that sets its own EXIT trap",
        "direct exec",
    ]
    for flag in ("--all", "--session", "--all-sessions", "--agent", "--ledger"):
        assert flag in m["flags"], m["flags"]


def test_help_fits_forty_lines(lab: Lab) -> None:
    r = journal(lab, "--help")
    assert r.returncode == 0, said(r)
    assert 0 < len(r.stdout.splitlines()) <= 40


def test_probe_on_an_empty_current_session_is_exit_0(lab: Lab) -> None:
    r = journal(lab, "--json", session="never-used")
    assert r.returncode == 0, said(r)


# ── tool entries: time, command, exit, pointer, in order (SC-1) ───────────────────────────────


def test_tool_entries_in_order_with_their_record_fields(lab: Lab) -> None:
    calls = [("snapshot",), ("run", "--", "true"), ("view", "x"), ("run", "--", "sh", "-c", "exit 3")]
    exits = [tool(lab, "work", *c).returncode for c in calls]
    assert exits == [0, 0, 0, 3]
    evs = lab.events("work")
    assert [e["tool"] for e in evs] == ["snapshot", "run", "view", "run"]

    d = ok(journal(lab, "--json", "--all", "--session", "work"))
    assert d["session"] == "work"
    assert (d["total"], d["shown"]) == (4, 4)
    assert d["counts"] == {"tool": 4, "shell": 0, "grant": 0}
    assert d["unreadable"] == 0
    assert commands(d) == [command_of(*c) for c in calls]
    for e, ev, code in zip(d["entries"], evs, exits, strict=True):
        assert e["kind"] == "tool"
        assert e["session"] == "work"
        assert e["exit"] == code
        assert e["duration_ms"] == ev["duration_ms"]
        assert e["pid"] == ev["pid"]
        assert e["ppid"] == ev["ppid"] == os.getpid()
        assert ms_of(e["start"]) == tool_start(ev)
        assert ms_of(e["end"]) == ev["t_ms"]
        assert e["children"] in ([], None)
        assert not e["collapsed"]
        assert blank(e["style"])
    starts = [ms_of(e["start"]) for e in d["entries"]]
    assert starts == sorted(starts)
    assert d["entries"][2]["ref"] is None  # view declares no pointer (data-model § Tool event)
    assert len(d["lines"]) == 4 and all(ENTRY.match(x) for x in d["lines"]), d["lines"]


def test_pointers_are_the_log_and_the_id_the_tools_reported(lab: Lab) -> None:
    s = tool(lab, "work", "snapshot", "--json")
    assert s.returncode == 0, said(s)
    snap_id = doc_of(s)["id"]
    r = tool(lab, "work", "run", "--json", "--", "true")
    assert r.returncode == 0, said(r)
    log = doc_of(r)["log"]
    assert Path(log).is_file()

    d = ok(journal(lab, "--json", "--all", "--session", "work"))
    snap, run = d["entries"]
    assert snap["ref"] == {"snapshot": snap_id}
    assert run["ref"] == {"log": log}
    assert Path(run["ref"]["log"]).is_file()
    assert Path(run["ref"]["log"]).samefile(log)

    t = journal(lab, "--text", "--all", "--session", "work")
    assert t.returncode == 0, said(t)
    snap_line, run_line = (m.string for m in text_entries(t))
    assert snap_line.rstrip().endswith(f"snapshot {snap_id}"), snap_line
    assert f"log {log}" in run_line, run_line


def test_text_lines_carry_the_start_time_and_open_with_the_date(lab: Lab) -> None:
    tool(lab, "work", "run", "--", "true")
    tool(lab, "work", "run", "--", "false")
    evs = lab.events("work")
    t = journal(lab, "--text", "--all", "--session", "work")
    assert t.returncode == 0, said(t)
    out = t.stdout.splitlines()
    assert out[0] == "journal: work [all 2]"
    assert out[1].startswith("verdict: 2 of 2 entries in session work (2 tools, 0 shell, 0 grants)"), out[1]
    date = datetime.fromtimestamp(tool_start(evs[0]) / 1000, UTC).strftime("%Y-%m-%d")
    assert out[2] == f"── {date} ──"
    got = text_entries(t)
    assert [m.group(1) for m in got] == [hhmmss(tool_start(e)) for e in evs]
    assert "exit 0" in got[0].string and "exit 1" in got[1].string
    assert "log " in got[0].string  # run carries its log pointer
    assert "run -- false" in got[1].string
    # rule 2 (discovery revision 6): uncut text ends on its own last result line, with no closing lines
    assert out[-1] == got[1].string


# ── shell entries (SC-2), order and linking (R3) ─────────────────────────────────────────────


@needs_hook
def test_shell_commands_appear_with_their_exits_in_order_among_tools(lab: Lab) -> None:
    steps: list[tuple[str, Callable[[], Proc], str]] = [
        ("tool", lambda: tool(lab, "work", "run", "--", "true"), "run -- true"),
        ("shell", lambda: shell(lab, "work", "exit 7"), "exit 7"),
        ("shell", lambda: shell(lab, "work", "false"), "false"),
        ("tool", lambda: tool(lab, "work", "view", "x"), "view x"),
        ("shell", lambda: shell(lab, "work", "ls /nonexistent-009"), "ls /nonexistent-009"),
        ("shell", lambda: shell(lab, "work", "true", login=True), "true"),
    ]
    exits = [step().returncode for _, step, _ in steps]
    assert exits == [0, 7, 1, 0, 2, 0]
    recs = lab.shells("work")
    assert [x["exit"] for x in recs] == [7, 1, 2, 0]  # the writer's premise, before the reader's
    assert [x["style"] for x in recs] == ["bash -c"] * 3 + ["bash -lc"]

    d = ok(journal(lab, "--json", "--all", "--session", "work"))
    assert [e["kind"] for e in d["entries"]] == [k for k, _, _ in steps]
    assert commands(d) == [c for _, _, c in steps]
    assert [e["exit"] for e in d["entries"]] == exits
    assert d["counts"] == {"tool": 2, "shell": 4, "grant": 0}
    shells = by_kind(d, "shell")
    assert [e["style"] for e in shells] == ["bash -c"] * 3 + ["bash -lc"]
    for e, rec in zip(shells, recs, strict=True):
        assert e["pid"] == rec["pid"] and e["ppid"] == rec["ppid"]
        assert abs(ms_of(e["start"]) - shell_start(rec)) <= 1
        assert abs(ms_of(e["end"]) - int(rec["end_us"]) // 1000) <= 1
        assert not e["collapsed"] and e["children"] in ([], None)
    starts = [ms_of(e["start"]) for e in d["entries"]]
    assert starts == sorted(starts)

    t = journal(lab, "--text", "--all", "--session", "work")
    lines = [m.string for m in text_entries(t)]
    assert "bash -lc" in lines[5] and "exit 0" in lines[5]
    assert "bash -c" in lines[1] and "exit 7" in lines[1]


@needs_hook
def test_bash_c_running_one_tool_collapses_to_the_tool_entry(lab: Lab) -> None:
    r = shell(lab, "work", "snapshot")
    assert r.returncode == 0, said(r)
    snap_id = json.loads(r.stdout.splitlines()[0])["id"]
    (rec,) = lab.shells("work")
    (ev,) = lab.events("work")
    assert ev["ppid"] == rec["pid"]  # the link's premise (R1: bash forks under the trap)

    d = ok(journal(lab, "--json", "--all", "--session", "work"))
    (e,) = d["entries"]
    assert e["kind"] == "tool"
    assert e["style"] == "bash -c"
    assert e["collapsed"] is True
    assert e["command"] == "snapshot"
    assert e["ref"] == {"snapshot": snap_id}
    assert e["pid"] == ev["pid"]
    assert d["counts"] == {"tool": 1, "shell": 0, "grant": 0}
    assert (d["total"], d["shown"]) == (1, 1)

    t = journal(lab, "--text", "--all", "--session", "work")
    (line,) = (m.string for m in text_entries(t))
    assert re.search(r"\btool\s+bash -c\s+snapshot\b", line), line


@needs_hook
def test_bash_c_running_two_tools_nests_them_under_the_shell_entry(lab: Lab) -> None:
    r = shell(lab, "work", "snapshot; view x")
    assert r.returncode == 0, said(r)
    snap_id = json.loads(r.stdout.splitlines()[0])["id"]
    (rec,) = lab.shells("work")
    evs = lab.events("work")
    assert [(e["tool"], e["ppid"]) for e in evs] == [("snapshot", rec["pid"]), ("view", rec["pid"])]

    d = ok(journal(lab, "--json", "--all", "--session", "work"))
    assert [e["kind"] for e in d["entries"]] == ["shell", "tool", "tool"]
    sh, snap, view = d["entries"]
    assert sh["command"] == "snapshot; view x"
    assert sh["style"] == "bash -c"
    assert sh["collapsed"] is False
    assert sh["children"] == [1, 2]
    assert [d["entries"][i]["ppid"] for i in sh["children"]] == [sh["pid"], sh["pid"]]
    assert snap["ref"] == {"snapshot": snap_id} and view["ref"] is None
    # R3: a tool started by a shell sorts after the shell's start, and lies within it
    assert ms_of(sh["start"]) <= ms_of(snap["start"]) <= ms_of(view["start"]) <= ms_of(sh["end"])
    assert ms_of(snap["start"]) == tool_start(evs[0])
    assert d["counts"] == {"tool": 2, "shell": 1, "grant": 0}

    t = journal(lab, "--text", "--all", "--session", "work")
    ms = text_entries(t)
    assert [m.group(5) for m in ms] == ["shell", "tool", "tool"]
    assert ms[1].start(5) > ms[0].start(5) and ms[2].start(5) == ms[1].start(5), t.stdout  # indented


# ── the tail and its cut (SC-3, FR-4) ─────────────────────────────────────────────────────────


def make_runs(lab: Lab, session: str, n: int) -> list[str]:
    out = []
    for i in range(1, n + 1):
        args = ("--", "true", f"{i:02d}")
        assert tool(lab, session, "run", *args).returncode == 0
        out.append(command_of("run", *args))
    return out


def recorded_commands(lab: Lab, session: str) -> list[str]:
    return [command_of(e["tool"], *e["args"]) for e in lab.events(session)]


def test_the_default_is_the_last_20_of_the_current_session_oldest_first(lab: Lab) -> None:
    made = make_runs(lab, "work", 25)
    assert recorded_commands(lab, "work") == made

    r = journal(lab, "--json", session="work")
    assert r.returncode == 0, said(r)
    d = doc_of(r)
    assert (d["target"], d["scope"]) == ("work", "last 20 of 25")
    assert (d["total"], d["shown"]) == (25, 20)
    assert commands(d) == made[-20:]
    assert d["verdict"] == "20 of 25 entries in session work (20 tools, 0 shell, 0 grants)"
    cut = d["truncated"]
    assert cut["more"] == "journal --all"
    assert cut["omitted_lines"] == 5
    assert cut["omitted_bytes"] > 0
    full = Path(cut["full_output"])
    assert full.is_file() and full.resolve().is_relative_to((lab.scratch / "work").resolve())
    saved = full.read_text()
    assert all(c in saved for c in made)  # the artefact holds the whole session

    # the journal's own event is now the session's 26th record: read the record, not a guess
    now = recorded_commands(lab, "work")
    assert len(now) == 26 and now[-1].startswith("journal")
    t = journal(lab, "--text", session="work")
    assert t.returncode == 0, said(t)
    out = t.stdout.splitlines()
    assert out[0] == "journal: work [last 20 of 26]"
    assert out[1].startswith("verdict: 20 of 26 entries in session work (20 tools, 0 shell, 0 grants)")
    # rule 3's cut opens with its section label (agentio's Cut, as view's windows do), then the date line
    assert out[2] == "── last 20 of 26 ──", out[2]
    assert DATE_LINE.match(out[3]), out[3]
    shown = text_entries(t)
    assert len(shown) == 20
    for m, c in zip(shown, now[-20:], strict=True):
        assert c in m.string, (c, m.string)
    assert "more: journal --all" in out
    assert "exit: 0" in out


def test_n_sets_the_tail_and_its_more_reaches_the_earlier_entries(lab: Lab) -> None:
    made = make_runs(lab, "work", 25)
    d = doc_of(journal(lab, "--json", "-n", "5", "--session", "work"))
    assert d["exit"] == 0, d
    assert d["scope"] == "last 5 of 25"
    assert commands(d) == made[-5:]
    assert d["truncated"]["omitted_lines"] == 20
    more = shlex.split(d["truncated"]["more"])
    assert more[0] == "journal", more
    assert "work" in more  # --session as given (contract § The cut)
    m = ok(journal(lab, "--json", *more[1:]))
    assert made[-6] in commands(m)  # the entry just before the window is reachable
    assert set(made[-5:]) <= set(commands(m))


def test_all_prints_the_whole_session_without_a_cut(lab: Lab) -> None:
    made = make_runs(lab, "work", 25)
    d = ok(journal(lab, "--json", "--all", "--session", "work"))
    assert d["scope"] == "all 25"
    assert commands(d) == made
    assert (d["total"], d["shown"]) == (25, 25)
    assert "truncated" not in d
    assert d["verdict"].startswith("25 of 25 entries in session work (25 tools, 0 shell, 0 grants)")


# ── sessions ──────────────────────────────────────────────────────────────────────────────────


def test_session_reads_another_session(lab: Lab) -> None:
    made = make_runs(lab, "work", 2)
    tool(lab, "elsewhere", "run", "--", "true", "other")
    d = ok(journal(lab, "--json", "--all", "--session", "work", session="elsewhere"))
    assert d["session"] == "work"
    assert commands(d) == made
    assert {e["session"] for e in d["entries"]} == {"work"}


def test_session_that_does_not_exist_is_exit_3_with_the_remedy(lab: Lab) -> None:
    make_runs(lab, "work", 1)
    r = journal(lab, "--json", "--session", "nosuch")
    assert r.returncode == 3, said(r)
    assert r.stderr == ""
    d = doc_of(r)
    assert d["exit"] == 3
    assert "do instead: journal --all-sessions" in d["lines"], d
    assert not (lab.scratch / "nosuch").exists()  # the reader made nothing (seam 2)


@pytest.mark.parametrize("name", ["../work", "a/b", "...", "x" * 65])
def test_an_invalid_session_name_is_a_usage_error(lab: Lab, name: str) -> None:
    make_runs(lab, "work", 1)
    r = journal(lab, "--json", "--session", name)
    assert r.returncode == 2, said(r)
    assert r.stdout == ""


def test_no_records_is_exit_0_with_where_it_looked(lab: Lab) -> None:
    r = journal(lab, "--json", session="fresh")
    assert r.returncode == 0, said(r)
    d = doc_of(r)
    assert (d["target"], d["scope"]) == ("fresh", "none")
    assert d["verdict"] == (
        f"no records for session fresh in {lab.scratch}/fresh (the scratch is disposable: rule 10)"
    )
    assert d["entries"] == []


def test_all_sessions_labels_every_entry_with_agent_and_session(lab: Lab) -> None:
    tool(lab, "s1", "run", "--", "true", "one", agent="a1")
    tool(lab, "s2", "run", "--", "true", "two", agent="a2")
    d = ok(journal(lab, "--json", "--all-sessions", "--all"))
    assert d["target"] == "all sessions"
    assert {"s1", "s2"} <= set(d["sessions"])
    pairs = {(e["agent"], e["session"], e["command"]) for e in d["entries"]}
    assert ("a1", "s1", "run -- true one") in pairs and ("a2", "s2", "run -- true two") in pairs

    t = journal(lab, "--text", "--all-sessions", "--all")
    assert t.returncode == 0, said(t)
    ms = text_entries(t)
    assert ms and all(m.group(2) for m in ms), t.stdout  # every line labelled
    labelled = {(m.group(3), m.group(4)) for m in ms if "run -- true" in m.string}
    assert labelled == {("a1", "s1"), ("a2", "s2")}
    assert t.stdout.splitlines()[0].startswith("journal: all sessions ["), t.stdout


# ── agents (SC-4, FR-10) ──────────────────────────────────────────────────────────────────────


def scenario_4(lab: Lab, *, with_shells: bool) -> None:
    """a1 in s1; a2 in s2, then also in s1 (spec Scenario 4)."""
    assert tool(lab, "s1", "run", "--", "true", "a1-s1", agent="a1").returncode == 0
    assert tool(lab, "s2", "run", "--", "true", "a2-s2", agent="a2").returncode == 0
    assert tool(lab, "s1", "run", "--", "true", "a2-s1", agent="a2").returncode == 0
    if with_shells:
        assert shell(lab, "s1", "true a1-shell", agent="a1").returncode == 0
        assert shell(lab, "s1", "true a2-shell", agent="a2").returncode == 0
    for s in ("s1", "s2"):
        for ev in lab.events(s):
            assert ev.get("agent") in ("a1", "a2"), f"agentio wrote no agent (T001): {ev}"


def test_agent_filters_one_session(lab: Lab) -> None:
    scenario_4(lab, with_shells=False)
    d = ok(journal(lab, "--json", "--all", "--session", "s1", "--agent", "a1"))
    assert commands(d) == ["run -- true a1-s1"]
    assert {e["agent"] for e in d["entries"]} == {"a1"}


def test_agent_filters_across_sessions(lab: Lab) -> None:
    scenario_4(lab, with_shells=False)
    d = ok(journal(lab, "--json", "--all", "--all-sessions", "--agent", "a2"))
    assert sorted((e["session"], e["command"]) for e in d["entries"]) == [
        ("s1", "run -- true a2-s1"),
        ("s2", "run -- true a2-s2"),
    ]


@needs_hook
def test_agent_filter_covers_shell_entries(lab: Lab) -> None:
    scenario_4(lab, with_shells=True)
    assert [x["agent"] for x in lab.shells("s1")] == ["a1", "a2"]
    d = ok(journal(lab, "--json", "--all", "--session", "s1", "--agent", "a2"))
    assert commands(d) == ["run -- true a2-s1", "true a2-shell"]
    assert [e["kind"] for e in d["entries"]] == ["tool", "shell"]


def test_two_agents_in_a_session_are_named_and_labelled(lab: Lab) -> None:
    scenario_4(lab, with_shells=False)
    d = ok(journal(lab, "--json", "--all", "--session", "s1"))
    assert set(d["agents"]) == {"a1", "a2"}
    assert re.search(r"; agents: (a1, a2|a2, a1)(;|$)", d["verdict"]), d["verdict"]
    t = journal(lab, "--text", "--all", "--session", "s1")
    ms = text_entries(t)
    assert [(m.group(3), m.group(4)) for m in ms] == [("a1", "s1"), ("a2", "s1")], t.stdout


def test_entries_without_an_agent_are_counted_in_the_verdict(lab: Lab) -> None:
    tool(lab, "work", "run", "--", "true", "known", agent="a1")
    tool(lab, "work", "run", "--", "true", "anon1")
    tool(lab, "work", "run", "--", "true", "anon2")
    evs = lab.events("work")
    assert [("agent" in e) for e in evs] == [True, False, False]
    d = ok(journal(lab, "--json", "--all", "--session", "work"))
    assert "no agent recorded for 2 entries: separate agents with TIMELIKE_AGENT" in d["verdict"], d[
        "verdict"
    ]
    anon = [e for e in d["entries"] if "anon" in e["command"]]
    assert len(anon) == 2 and all(e["agent"] in ("-", "", None) for e in anon)


def test_one_agent_alone_adds_nothing_to_the_verdict(lab: Lab) -> None:
    make_runs(lab, "work", 2)  # no TIMELIKE_AGENT anywhere
    d = ok(journal(lab, "--json", "--all", "--session", "work"))
    assert d["verdict"] == "2 of 2 entries in session work (2 tools, 0 shell, 0 grants)"


# ── the ledger (FR-11, R4) ────────────────────────────────────────────────────────────────────


def ledger_row(
    ident: int, at_ms: int, outcome: str, session: str, resource: str = "web1", grant: str = "demo"
) -> dict[str, Any]:
    """One row as `adeled ledger --json` prints it (004's jsonRow): absent values null."""
    performed = outcome == "performed"
    return {
        "id": ident,
        "at": iso_s(at_ms),
        "outcome": outcome,
        "grant": grant,
        "session": session,
        "capability": "standin.box",
        "action": "create",
        "resource": resource,
        "cost_cents": 5 if performed else None,
        "expires_at": iso_s(at_ms + 3_600_000) if performed else None,
        "undo": {"op": "delete", "name": resource} if performed else None,
        "limit_name": "boxes" if outcome == "refused" else "",
        "allowed": "1" if outcome == "refused" else "",
        "needed": "2" if outcome == "refused" else "",
    }


def ledger_json(rows: list[dict[str, Any]]) -> str:
    return json.dumps(rows, indent=2) + "\n"  # adeled indents its array (ops.go: SetIndent)


def ledger_fixture(lab: Lab) -> tuple[list[str], list[dict[str, Any]]]:
    made = make_runs(lab, "work", 2)
    evs = lab.events("work")
    before = (tool_start(evs[0]) // 1000 - 60) * 1000
    after = (math.ceil(evs[-1]["t_ms"] / 1000) + 60) * 1000
    rows = [
        ledger_row(3, before, "performed", "work"),
        ledger_row(4, after, "refused", "work", resource="web2"),
        ledger_row(5, after, "performed", "someone-else", resource="web3"),
        ledger_row(6, after + 1000, "extended", "operator", resource=""),
    ]
    return made, rows


def check_ledger_merge(d: dict[str, Any], made: list[str], rows: list[dict[str, Any]]) -> None:
    assert [e["kind"] for e in d["entries"]] == ["grant", "tool", "tool", "grant"]
    first, *_, last = d["entries"]
    assert commands(d)[1:3] == made
    assert first["command"] == "standin.box.create web1" and last["command"] == "standin.box.create web2"
    assert first["exit"] == "performed" and last["exit"] == "refused"
    assert first["ref"] == {"ledger": 3, "outcome": "performed", "grant": "demo"}
    assert last["ref"] == {"ledger": 4, "outcome": "refused", "grant": "demo"}
    assert ms_of(first["start"]) == ms_of(rows[0]["at"].replace("Z", ".000Z"))
    assert ms_of(last["start"]) == ms_of(rows[1]["at"].replace("Z", ".000Z"))
    assert {e["session"] for e in d["entries"]} == {"work"}
    assert d["counts"] == {"tool": 2, "shell": 0, "grant": 2}


def test_ledger_file_rows_become_grant_entries_in_their_session(lab: Lab) -> None:
    made, rows = ledger_fixture(lab)
    path = lab.tmp / "ledger.json"
    path.write_text(ledger_json(rows))
    d = ok(journal(lab, "--json", "--all", "--session", "work", "--ledger", str(path)))
    check_ledger_merge(d, made, rows)
    assert d["verdict"].startswith("4 of 4 entries in session work (2 tools, 0 shell, 2 grants)")

    t = journal(lab, "--text", "--all", "--session", "work", "--ledger", str(path))
    assert t.returncode == 0, said(t)
    lines = [m.string for m in text_entries(t)]
    assert "ledger #3 performed demo" in lines[0] and "ledger #4 refused demo" in lines[3]
    assert re.search(r"\bgrant\s+—\s+standin\.box\.create web1\s+performed\b", lines[0]), lines[0]


def test_ledger_from_stdin_is_the_same_merge(lab: Lab) -> None:
    made, rows = ledger_fixture(lab)
    d = ok(journal(lab, "--json", "--all", "--session", "work", "--ledger", "-", stdin=ledger_json(rows)))
    check_ledger_merge(d, made, rows)


def test_ledger_with_all_sessions_shows_extensions_as_operator(lab: Lab) -> None:
    _, rows = ledger_fixture(lab)
    d = ok(journal(lab, "--json", "--all", "--all-sessions", "--ledger", "-", stdin=ledger_json(rows)))
    grants = {e["ref"]["ledger"]: e for e in by_kind(d, "grant")}
    assert set(grants) == {3, 4, 5, 6}
    assert grants[6]["session"] == "operator" and grants[6]["exit"] == "extended"
    assert grants[5]["session"] == "someone-else"


def test_stdin_is_not_read_without_ledger_dash(lab: Lab) -> None:
    made, rows = ledger_fixture(lab)
    d = ok(journal(lab, "--json", "--all", "--session", "work", stdin=ledger_json(rows)))
    assert commands(d) == made
    assert by_kind(d, "grant") == []


def test_ledger_dash_on_a_terminal_is_a_usage_error(lab: Lab) -> None:
    make_runs(lab, "work", 1)
    leader, follower = os.openpty()
    try:
        r = journal(lab, "--json", "--session", "work", "--ledger", "-", stdin=follower)
    finally:
        os.close(follower)
        os.close(leader)
    assert r.returncode == 2, said(r)


@pytest.mark.parametrize(
    ("body", "case"),
    [('{"rows": []}', "an object"), ("[{]", "not JSON"), ('"ledger"', "a string"), ("", "empty")],
)
def test_a_ledger_that_is_not_a_json_array_is_exit_1_naming_the_file(lab: Lab, body: str, case: str) -> None:
    make_runs(lab, "work", 1)
    path = lab.tmp / "bad-ledger.json"
    path.write_text(body)
    r = journal(lab, "--json", "--all", "--session", "work", "--ledger", str(path))
    assert r.returncode == 1, (case, said(r))
    d = doc_of(r)
    assert d["exit"] == 1
    assert str(path) in d["verdict"], d["verdict"]


def test_a_missing_ledger_file_is_exit_1_naming_it(lab: Lab) -> None:
    make_runs(lab, "work", 1)
    path = lab.tmp / "absent.json"
    r = journal(lab, "--json", "--all", "--session", "work", "--ledger", str(path))
    assert r.returncode == 1, said(r)
    assert str(path) in doc_of(r)["verdict"]


def slow_adele(lab: Lab, session: str, seconds: float) -> Proc:
    """A real `adele grants` call against a listener that never answers: it waits out its --timeout, so its
    event spans at least one whole second (R4 links a row by the second it falls in)."""
    with socket.socket() as srv:
        srv.bind(("127.0.0.1", 0))
        srv.listen(4)  # the handshake completes in the kernel; nobody ever replies
        url = f"http://127.0.0.1:{srv.getsockname()[1]}"
        return tool(lab, session, "adele", "grants", "--timeout", str(seconds), TIMELIKE_ADELE_URL=url)


def test_an_adele_event_is_a_grant_entry(lab: Lab) -> None:
    r = slow_adele(lab, "work", 0.2)
    assert r.returncode != 0  # unreachable: the event is still written, with its real exit
    (ev,) = lab.events("work")
    assert ev["tool"] == "adele"
    d = ok(journal(lab, "--json", "--all", "--session", "work"))
    (e,) = d["entries"]
    assert e["kind"] == "grant"
    assert e["command"] == "adele grants --timeout 0.2"
    assert e["exit"] == r.returncode
    assert d["counts"] == {"tool": 0, "shell": 0, "grant": 1}


def test_a_ledger_row_inside_an_adele_call_links_to_it(lab: Lab) -> None:
    r = slow_adele(lab, "work", 1.3)
    (ev,) = lab.events("work")
    start, end = tool_start(ev), ev["t_ms"]
    assert end - start >= 1000, ev  # the call spans a whole second boundary
    second = math.ceil(start / 1000) * 1000
    assert start <= second <= end
    rows = [ledger_row(7, second, "performed", "work")]
    d = ok(journal(lab, "--json", "--all", "--session", "work", "--ledger", "-", stdin=ledger_json(rows)))
    (e,) = d["entries"]  # one entry, not two
    assert e["kind"] == "grant"
    assert e["command"].startswith("adele grants")
    assert e["ref"] == {"ledger": 7, "outcome": "performed", "grant": "demo"}
    assert e["pid"] == ev["pid"]
    assert d["counts"] == {"tool": 0, "shell": 0, "grant": 1}
    assert r.returncode != 0
    t = journal(lab, "--text", "--all", "--session", "work", "--ledger", "-", stdin=ledger_json(rows))
    (line,) = (m.string for m in text_entries(t))
    assert "adele grants" in line and "ledger #7 performed demo" in line


# ── unreadable lines and records ──────────────────────────────────────────────────────────────


def test_malformed_and_foreign_lines_are_skipped_and_counted(lab: Lab) -> None:
    made = make_runs(lab, "work", 1)
    with (lab.scratch / "work" / "events.jsonl").open("a") as f:
        f.write("not json at all\n")
        f.write('{"foreign": "shape", "v": 9}\n')
    (lab.scratch / "work" / "shell.jsonl").write_text("[1, 2, 3]\n")
    d = ok(journal(lab, "--json", "--all", "--session", "work"))
    assert commands(d) == made
    assert d["unreadable"] == 3
    assert "3 unreadable lines skipped" in d["verdict"], d["verdict"]
    assert {Path(p).name for p in d["sources"]} >= {"events.jsonl", "shell.jsonl"}


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads a mode-000 file")
@needs_hook
def test_an_unreadable_record_is_named_and_the_other_is_shown(lab: Lab) -> None:
    assert tool(lab, "work", "run", "--", "true").returncode == 0
    assert shell(lab, "work", "exit 7").returncode == 7
    events_file = lab.scratch / "work" / "events.jsonl"
    events_file.chmod(0)
    try:
        d = ok(journal(lab, "--json", "--all", "--session", "work"))
    finally:
        events_file.chmod(0o600)
    assert "events.jsonl" in d["verdict"], d["verdict"]
    assert commands(d) == ["exit 7"]
    assert [e["exit"] for e in d["entries"]] == [7]


# ── redaction (FR-12, R5) ─────────────────────────────────────────────────────────────────────

SECRETS: list[tuple[str, Callable[[], str], str]] = [
    ("github-pat", lambda: gh("p"), "token"),
    ("github-fine-grained-pat", github_fine_grained, "token"),
    ("gitlab-pat", gitlab, "token"),
    ("npm-access-token", npm, "token"),
    ("jwt", jwt, "token"),
    ("aws-access-token", aws, "credential"),
    ("gcp-api-key", gcp, "key"),
    ("openai-api-key", openai, "key"),
    ("stripe-access-token", stripe, "secret"),
]


@needs_hook
def test_a_secret_in_a_shell_command_is_printed_redacted(lab: Lab) -> None:
    made = []
    for _, make, kind in SECRETS:
        secret = make()
        cmd = f"true deploy {shlex.quote(secret)}"
        assert shell(lab, "work", cmd).returncode == 0
        made.append((secret, kind))
    stored = (lab.scratch / "work" / "shell.jsonl").read_text()
    assert all(s in stored for s, _ in made)  # the premise: the hook stores the line as run (R5)

    d = ok(journal(lab, "--json", "--all", "--session", "work"))
    t = journal(lab, "--text", "--all", "--session", "work")
    assert t.returncode == 0, said(t)
    assert len(d["entries"]) == len(SECRETS)
    for (secret, kind), e, (family, _, _) in zip(made, d["entries"], SECRETS, strict=True):
        assert secret not in e["command"], family
        assert e["command"] == f"true deploy [REDACTED:{kind}]", (family, e["command"])
    for secret, _ in made:
        assert secret not in t.stdout and secret not in json.dumps(d)
    lines = [m.string for m in text_entries(t)]
    for line, (_, kind) in zip(lines, made, strict=True):
        assert f"true deploy [REDACTED:{kind}]" in line, line


# ── one session event per call (rule 16) ──────────────────────────────────────────────────────


def test_one_session_event_per_call_and_nothing_else_written(lab: Lab) -> None:
    make_runs(lab, "work", 2)
    work = lab.scratch / "work"
    before = {p.name: p.read_bytes() for p in work.iterdir() if p.is_file()}
    calls = [
        (("--json", "--all", "--session", "work"), 0),
        (("--agent-info",), 0),
        (("--json", "--session", "nosuch"), 3),
        (("--json", "--session", "../work"), 2),
        (("--json", "--all", "--session", "work", "--ledger", "-"), 0),
    ]
    for args, code in calls:
        r = journal(lab, *args, stdin="[]" if "-" in args else None)
        assert r.returncode == code, (args, said(r))
    mine = [e for e in lab.events("reader") if e["tool"] == "journal"]
    assert [e["exit"] for e in mine] == [c for _, c in calls]
    assert len(lab.events("reader")) == len(calls)
    after = {p.name: p.read_bytes() for p in work.iterdir() if p.is_file()}
    assert after == before  # the session it read is unchanged


def test_journal_event_carries_the_new_fields(lab: Lab) -> None:
    journal(lab, "--json", session="reader", agent="a9")
    (ev,) = lab.events("reader")
    assert ev["tool"] == "journal"
    assert ev["agent"] == "a9"
    assert ev["ppid"] == os.getpid()
    assert abs(ev["t_ms"] - time.time() * 1000) < 60_000


# ── internals, in process: parsing edges and refusals a fixture rarely reaches (T007, coverage) ───


def _journal_module() -> Any:
    import importlib.machinery
    import importlib.util

    loader = importlib.machinery.SourceFileLoader("timelike_journal_under_test", str(JOURNAL))
    spec = importlib.util.spec_from_loader("timelike_journal_under_test", loader)
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


JM = _journal_module()


def test_record_parsers_reject_malformed_records() -> None:
    assert JM.tool_entry({"tool": 1, "args": [], "exit": 0, "duration_ms": 1}, 0) is None
    assert JM.tool_entry({"tool": "x", "args": [], "exit": 0, "duration_ms": 1}, 0) is None  # no time at all
    assert JM.tool_entry({"tool": "x", "args": [], "exit": 0, "duration_ms": 1, "ts": "yesterday"}, 0) is None
    old = JM.tool_entry(
        {"tool": "x", "args": ["a"], "exit": 0, "duration_ms": 1000, "ts": "2026-10-05T06:00:00Z"}, 0
    )
    assert old is not None and old.end - old.start == 1000 and old.command == "x a"  # ts (seconds) as the end
    assert JM.shell_entry({"kind": "other"}, 0) is None
    assert JM.shell_entry({"kind": "shell", "cmd": "x", "exit": 0, "start_us": 1}, 0) is None
    cut = JM.shell_entry(
        {"kind": "shell", "cmd": "y" * 4096, "cut_bytes": 9, "exit": 0, "start_us": 1000, "end_us": 2000}, 0
    )
    assert cut is not None and cut.command.endswith(" …[cut 9 bytes]")
    assert JM.ledger_entry({"at": "nope", "outcome": "performed", "session": "s"}, 0) is None
    ext = JM.ledger_entry(
        {"id": 3, "at": "2026-10-05T06:00:00Z", "outcome": "extended", "session": "operator", "grant": "demo",
         "limit_name": "ports", "needed": "22"},
        0,
    )  # fmt: skip
    assert ext is not None and ext.command == "extend demo ports 22" and ext.exit == "extended"


@pytest.mark.parametrize(
    ("cmd", "want"),
    [
        ("snapshot", "snapshot"),
        ("exec env A=1 B=2 2>/dev/null /opt/timelike/bin/run -- true", "run"),
        ("time command view x", "view"),
        ("A=1", None),
        ("echo 'unterminated", None),
        ("# only a comment", None),
    ],
)
def test_first_word(cmd: str, want: str | None) -> None:
    assert JM.first_word(cmd) == want


def test_more_keeps_the_selection_flags() -> None:
    import argparse

    ns = argparse.Namespace(session=None, all_sessions=True, agent="a1", ledger="/x.json", n=None)
    assert JM._more(ns, 20) == "journal --all --all-sessions --agent a1 --ledger /x.json"
    ns = argparse.Namespace(session="s", all_sessions=False, agent=None, ledger="-", n=5)
    assert JM._more(ns, 5) == "journal -n 25 --session s"


@pytest.mark.parametrize(
    ("args", "words"),
    [
        (["-n", "0"], "N must be 1 or more"),
        (["--agent", "has space"], "is not an agent id"),
        (["--session", "s", "--all-sessions"], "exclusive"),
    ],
)
def test_usage_errors(lab: Lab, args: list[str], words: str) -> None:
    r = journal(lab, "--json", *args)
    assert r.returncode == 2 and words in r.stderr, said(r)


def test_ledger_too_large_and_unreadable(lab: Lab, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(JM, "MAX_LEDGER_BYTES", 10)
    big = lab.tmp / "big.json"
    big.write_text("[" + ",".join(["{}"] * 20) + "]")
    with pytest.raises(JM.Outcome) as e:
        JM.read_ledger(str(big))
    assert "too large" in e.value.verdict
    with pytest.raises(JM.Outcome) as e:
        JM.read_ledger(str(lab.tmp / "absent.json"))
    assert e.value.code == 1 and "cannot read the ledger" in e.value.verdict


def test_redaction_fails_closed(lab: Lab, monkeypatch: pytest.MonkeyPatch) -> None:
    tool(lab, "work", "run", "--", "true")
    r = journal(lab, "--json", "--all", "--session", "work")
    assert r.returncode == 0
    env = lab.env("reader", None, TIMELIKE_REDACTION_RULES=str(lab.tmp / "no-rules.toml"))
    r = subprocess.run(
        [sys.executable, str(JOURNAL), "--json", "--all", "--session", "work"],
        cwd=str(lab.ws), env=env, capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL,
    )  # fmt: skip
    d = doc_of(r)
    assert r.returncode == 0
    assert all(e["command"] == "[withheld: redaction rules unavailable]" for e in d["entries"])
    assert "commands withheld: redaction rules unavailable" in d["verdict"]


def test_an_unreadable_scratch_root_lists_no_sessions(lab: Lab) -> None:
    lab.scratch.mkdir()
    lab.scratch.chmod(0o000)
    try:
        r = journal(lab, "--json", "--all-sessions")
    finally:
        lab.scratch.chmod(0o700)
    if os.geteuid() == 0:
        pytest.skip("root reads a mode-000 directory")
    assert r.returncode == 0 and doc_of(r)["sessions"] == [], said(r)


def test_an_artefact_that_cannot_be_saved_is_named(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class Ctx:
        def scratch(self) -> Path:
            raise PermissionError(13, "Permission denied")

    assert JM.save(Ctx(), ["x"]).startswith("(not saved: ")
