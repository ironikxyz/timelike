"""`timelike budget` (feature 007, slice 1; contracts/timelike-announce-tools.md § `timelike budget`).

Written from the contract (T014-T023 cycle). Every value is chosen here, apart from the reader (lore
cross-stack P005): the fake cgroup files are written by the test under TIMELIKE_CGROUP_ROOT, the fake
/proc/self/status under TIMELIKE_PROC_STATUS, and every expected figure and text is a literal or is
computed here from the contract's own rule, never read back from the tool and asserted against itself.

The CPU job count has two homes, agentio (Python) and the shell hook (bash, no fork at shell start).
They are kept in agreement by feeding both the same two files (spec FR-22); the hook half of that table
runs against the hook that exists today.

agentio merges a result's data into the top level of the JSON document (there is no `data` key), so the
figures are read as doc["memory"], doc["cpu"] and so on.
"""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from conftest import AGENTIO_DIR, REPO, TOOLS_DIR

HOOK = REPO / "image" / "rootfs" / "etc" / "timelike" / "shell-env.bash"

# The test's own values (P005). Sizes in text are written out by hand from the contract's rule.
MEM_MAX = 314572800  # 300.0 MiB
MEM_CUR = 12345678  # 11.8 MiB
MEM_PEAK = 23456789  # 22.4 MiB
PIDS_MAX = 123
PIDS_CUR = 7
CPU_MAX = "150000 100000"  # 1.50 CPUs, ceil 2
AFFINITY = "0-3,8,10-11"  # 7 CPUs
DEFAULTS: dict[str, str] = {
    "memory.max": f"{MEM_MAX}\n",
    "memory.current": f"{MEM_CUR}\n",
    "memory.peak": f"{MEM_PEAK}\n",
    "pids.max": f"{PIDS_MAX}\n",
    "pids.current": f"{PIDS_CUR}\n",
    "cpu.max": f"{CPU_MAX}\n",
}
MEMORY_LINE = "memory: limit 300.0 MiB · in use 11.8 MiB · peak 22.4 MiB"
CPU_LINE = "cpu: limit 1.50 CPUs · job count 2 (TIMELIKE_CPUS)"
PROCESSES_LINE = f"processes: limit {PIDS_MAX} · running {PIDS_CUR}"

FIGURE_KEYS = {"state", "value", "source", "reason"}
CPU_KEYS = {"limit", "affinity", "jobs", "shell_value", "agrees"}
DISK_KEYS = {"role", "path", "measured", "exists", "free_bytes", "total_bytes", "reason"}
SIZE_RE = r"(?:\d+ B|\d+\.\d (?:KiB|MiB|GiB|TiB))"
FREE_SLACK = 256 * 1024 * 1024  # free space moves between the tool's statvfs and the test's


def size(n: int) -> str:
    """The contract's size rule: below 1 KiB `N B`, else one decimal with KiB/MiB/GiB/TiB."""
    if n < 1024:
        return f"{n} B"
    value = n / 1024
    units = ["KiB", "MiB", "GiB", "TiB"]
    while value >= 1024 and len(units) > 1:
        value /= 1024
        units.pop(0)
    return f"{value:.1f} {units[0]}"


def install(src: Path, bindir: Path) -> Path:
    """As test_announce.install: the shipped tool with the image's shebang swapped for this interpreter."""
    bindir.mkdir(parents=True, exist_ok=True)
    lines = src.read_text().splitlines(keepends=True)
    assert lines[0].startswith("#!/opt/timelike/python/bin/python3"), f"{src} has an unexpected shebang"
    dst = bindir / src.name
    dst.write_text(f"#!{sys.executable}\n" + "".join(lines[1:]))
    dst.chmod(0o755)
    return dst


def status_text(affinity: str | None) -> str:
    """A /proc/self/status stand-in; None for the Cpus_allowed_list line leaves the line out."""
    lines = ["Name:\tpython3", "State:\tR (running)"]
    if affinity is not None:
        lines.append(f"Cpus_allowed_list:\t{affinity}")
    lines.append("Threads:\t1")
    return "\n".join(lines) + "\n"


@dataclass
class Rig:
    tmp: Path
    tl: Path  # timelike's directory, on PATH
    cg: Path  # TIMELIKE_CGROUP_ROOT
    status: Path  # TIMELIKE_PROC_STATUS
    scratch: Path  # TIMELIKE_SCRATCH_ROOT (created: exists)
    ws: Path  # a workspace: holds a `.git` entry
    cwd: Path  # inside ws, two levels down
    home: Path

    def env(self, **extra: str | None) -> dict[str, str]:
        env = {
            "PATH": ":".join([str(self.tl), "/usr/bin", "/bin"]),
            "PYTHONPATH": str(AGENTIO_DIR),
            "HOME": str(self.home),
            "TIMELIKE_SCRATCH_ROOT": str(self.scratch),
            "TIMELIKE_SESSION": "test",
            "TIMELIKE_BIN_DIRS": str(self.tl),
            "TIMELIKE_REVISION": "89abcdef0123456789abcdef0123456789abcdef",
            "TIMELIKE_CGROUP_ROOT": str(self.cg),
            "TIMELIKE_PROC_STATUS": str(self.status),
            "LC_ALL": "C.UTF-8",
            "COLUMNS": "4000",  # pytest's paths are long; rule 13 must not cut a disk line
        }
        if "COVERAGE_PROCESS_START" in os.environ:
            env["COVERAGE_PROCESS_START"] = os.environ["COVERAGE_PROCESS_START"]
        for k, v in extra.items():
            if v is None:
                env.pop(k, None)
            else:
                env[k] = v
        return env

    def write(self, name: str, content: str | None) -> Path:
        """Write a fake cgroup file; None removes it (a missing file)."""
        p = self.cg / name
        if content is None:
            p.unlink(missing_ok=True)
        else:
            p.write_text(content)
        return p


@pytest.fixture
def rig(tmp_path: Path) -> Rig:
    root = tmp_path.resolve()
    r = Rig(
        tmp=root,
        tl=root / "tl",
        cg=root / "cg",
        status=root / "status",
        scratch=root / "scratch",
        ws=root / "ws",
        cwd=root / "ws" / "a" / "b",
        home=root / "home",
    )
    install(TOOLS_DIR / "timelike", r.tl)
    r.cg.mkdir()
    for name, content in DEFAULTS.items():
        r.write(name, content)
    r.status.write_text(status_text(AFFINITY))
    r.scratch.mkdir()
    r.cwd.mkdir(parents=True)
    (r.ws / ".git").mkdir()
    r.home.mkdir()
    return r


def budget(
    env: dict[str, str], *args: str, cwd: Path, timeout: float = 60
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["timelike", "budget", *args],
        env=env,
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=timeout,
        start_new_session=True,
    )


def doc_of(r: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    try:
        doc: dict[str, Any] = json.loads(r.stdout)
    except json.JSONDecodeError:
        pytest.fail(f"stdout is not one JSON document (exit {r.returncode}): {r.stdout!r} / {r.stderr!r}")
    assert r.returncode == 0, f"a report exits 0 whatever it read (exit {r.returncode}): {doc}"
    return doc


def json_of(rig: Rig, cwd: Path | None = None, **extra: str) -> dict[str, Any]:
    return doc_of(budget(rig.env(**extra), "--json", cwd=cwd or rig.cwd))


def text_of(rig: Rig, cwd: Path | None = None, **extra: str) -> tuple[str, str, list[str]]:
    """(header, verdict, body) of `timelike budget --text`."""
    r = budget(rig.env(**extra), "--text", cwd=cwd or rig.cwd)
    assert r.returncode == 0, (r.returncode, r.stdout, r.stderr)
    out = r.stdout.splitlines()
    assert len(out) >= 2, out
    assert out[0].startswith("timelike: "), f"the output contract's header comes first: {out}"
    assert out[1].startswith("verdict: "), f"then the verdict: {out}"
    return out[0], out[1][len("verdict: ") :], out[2:]


def assert_figure(fig: Any, state: str, value: Any, source: Path) -> None:
    assert isinstance(fig, dict), fig
    assert set(fig) >= FIGURE_KEYS, f"a figure carries state, value, source and reason: {fig}"
    assert fig["state"] == state, fig
    assert fig["value"] == value, fig
    assert type(fig["value"]) is type(value), f"value type: {fig}"
    assert fig["source"] == str(source), fig
    if state != "unknown":
        assert fig["reason"] is None, fig


def assert_unknown(fig: Any, source: Path, *, strerror: str | None = None) -> str:
    """An unknown figure: value null, never 0; reason `<path>: <why>`. Returns the reason."""
    assert isinstance(fig, dict), fig
    assert fig["state"] == "unknown", fig
    assert fig["value"] is None, f"an unknown is null, never 0 (FR-23): {fig}"
    assert fig["source"] == str(source), fig
    reason = fig["reason"]
    assert isinstance(reason, str), fig
    assert reason.startswith(f"{source}: "), f"the reason names the file first: {reason!r}"
    assert len(reason) > len(f"{source}: "), f"the reason says what was wrong: {reason!r}"
    if strerror is not None:
        assert strerror in reason, f"the reason carries the strerror {strerror!r}: {reason!r}"
    return reason


# ── JSON: all values ───────────────────────────────────────────────────────────────────────────


def test_budget_json_all_values(rig: Rig) -> None:
    doc = json_of(rig)
    assert doc["tool"] == "timelike"
    assert doc["cgroup"] == str(rig.cg)
    mem = doc["memory"]
    assert set(mem) == {"limit", "current", "peak"}, mem
    assert_figure(mem["limit"], "value", MEM_MAX, rig.cg / "memory.max")
    assert_figure(mem["current"], "value", MEM_CUR, rig.cg / "memory.current")
    assert_figure(mem["peak"], "value", MEM_PEAK, rig.cg / "memory.peak")
    pids = doc["pids"]
    assert set(pids) == {"limit", "current"}, pids
    assert_figure(pids["limit"], "value", PIDS_MAX, rig.cg / "pids.max")
    assert_figure(pids["current"], "value", PIDS_CUR, rig.cg / "pids.current")
    cpu = doc["cpu"]
    assert set(cpu) == CPU_KEYS, cpu
    assert_figure(cpu["limit"], "value", 1.5, rig.cg / "cpu.max")
    assert cpu["limit"]["quota"] == 150000
    assert cpu["limit"]["period"] == 100000
    assert cpu["affinity"] == 7
    assert cpu["jobs"] == 2
    assert cpu["shell_value"] is None
    assert cpu["agrees"] is None


def test_budget_json_shape(rig: Rig) -> None:
    doc = json_of(rig)
    for key in ("cgroup", "memory", "cpu", "pids", "disks", "verdict", "lines"):
        assert key in doc, f"no {key!r} at the top level: {sorted(doc)}"
    assert "data" not in doc, "agentio merges data into the top level"
    assert isinstance(doc["cgroup"], str)
    for group in ("memory", "pids"):
        for name, fig in doc[group].items():
            assert set(fig) == FIGURE_KEYS, f"{group}.{name}: {fig}"
            assert fig["state"] in {"value", "none", "unknown"}
            assert fig["value"] is None or type(fig["value"]) is int, f"{group}.{name}: {fig}"
            assert isinstance(fig["source"], str)
            assert fig["reason"] is None or isinstance(fig["reason"], str)
    lim = doc["cpu"]["limit"]
    assert set(lim) >= FIGURE_KEYS
    assert set(lim) <= FIGURE_KEYS | {"quota", "period"}, lim
    assert type(lim["value"]) is float, f"the CPU limit is a float (two decimals): {lim}"
    assert type(lim["quota"]) is int and type(lim["period"]) is int, lim
    assert type(doc["cpu"]["jobs"]) is int
    assert type(doc["cpu"]["affinity"]) is int
    disks = doc["disks"]
    assert isinstance(disks, list) and len(disks) == 2, disks
    assert [d["role"] for d in disks] == ["workspace", "scratch"], disks
    for d in disks:
        assert set(d) == DISK_KEYS, d
        assert isinstance(d["path"], str) and isinstance(d["measured"], str)
        assert type(d["exists"]) is bool
        assert type(d["free_bytes"]) is int and type(d["total_bytes"]) is int, d
        assert d["reason"] is None, d
    assert doc["lines"] == text_of(rig)[2], "JSON lines are the text body"


# ── text ───────────────────────────────────────────────────────────────────────────────────────


def disk_line_re(role: str, path: Path | str, total: int, suffix: str = "") -> str:
    return (
        rf"^disk, {role} {re.escape(str(path))}: {SIZE_RE} free of {re.escape(size(total))}"
        + re.escape(suffix)
        + "$"
    )


def test_budget_text_five_lines_in_order(rig: Rig) -> None:
    _header, _verdict, body = text_of(rig)
    assert len(body) == 5, f"exactly five lines after the header and verdict: {body}"
    assert body[0] == MEMORY_LINE
    assert body[1] == CPU_LINE
    assert body[2] == PROCESSES_LINE
    ws_total = os.statvfs(rig.ws).f_blocks * os.statvfs(rig.ws).f_frsize
    sc_total = os.statvfs(rig.scratch).f_blocks * os.statvfs(rig.scratch).f_frsize
    assert re.match(disk_line_re("workspace", rig.ws, ws_total), body[3]), body[3]
    assert re.match(disk_line_re("scratch", rig.scratch, sc_total), body[4]), body[4]


def test_budget_verdict_all_values(rig: Rig) -> None:
    _h, verdict, _b = text_of(rig)
    want = (
        rf"^memory 300\.0 MiB, cpu 1\.50 CPUs, processes {PIDS_MAX}; "
        rf"free: workspace {SIZE_RE}, scratch {SIZE_RE}$"
    )
    assert re.match(want, verdict), verdict
    assert "unknown" not in verdict


# ── `max`: no limit ────────────────────────────────────────────────────────────────────────────


def test_budget_max_is_no_limit(rig: Rig) -> None:
    rig.write("memory.max", "max\n")
    rig.write("pids.max", "max\n")
    rig.write("cpu.max", "max 100000\n")
    doc = json_of(rig)
    assert_figure(doc["memory"]["limit"], "none", None, rig.cg / "memory.max")
    assert_figure(doc["pids"]["limit"], "none", None, rig.cg / "pids.max")
    lim = doc["cpu"]["limit"]
    assert_figure(lim, "none", None, rig.cg / "cpu.max")
    assert lim.get("quota") is None and lim.get("period") is None, lim
    assert doc["cpu"]["jobs"] == 7, "no quota: the affinity count"
    _h, verdict, body = text_of(rig)
    assert body[0] == "memory: limit no limit · in use 11.8 MiB · peak 22.4 MiB"
    assert body[1] == "cpu: limit no limit · job count 7 (TIMELIKE_CPUS)"
    assert body[2] == f"processes: limit no limit · running {PIDS_CUR}"
    assert verdict.startswith("memory no limit, cpu no limit, processes no limit; free: "), verdict
    assert "unknown" not in verdict
    assert not re.search(r"\b(?:limit|memory|processes) 0\b", "\n".join([verdict, *body]))


# ── unknown: missing, unreadable, unparseable ──────────────────────────────────────────────────

FILES = [
    ("memory.max", ("memory", "limit")),
    ("memory.current", ("memory", "current")),
    ("memory.peak", ("memory", "peak")),
    ("pids.max", ("pids", "limit")),
    ("pids.current", ("pids", "current")),
    ("cpu.max", ("cpu", "limit")),
]


def others_are_values(doc: dict[str, Any], skip: tuple[str, str]) -> None:
    for _f, (group, name) in FILES:
        if (group, name) != skip:
            assert doc[group][name]["state"] == "value", f"{group}.{name} should be untouched: {doc[group]}"


def assert_unknown_everywhere(rig: Rig, fname: str, where: tuple[str, str], strerror: str | None) -> None:
    doc = json_of(rig)
    group, name = where
    reason = assert_unknown(doc[group][name], rig.cg / fname, strerror=strerror)
    others_are_values(doc, where)
    if fname == "cpu.max":
        assert doc["cpu"]["jobs"] == 7, "no readable quota: the affinity count"
    _h, verdict, body = text_of(rig)
    assert len(body) == 5, body
    assert f"unknown ({reason})" in "\n".join(body), f"the text names the reason: {body}"
    assert verdict.endswith("; 1 unknown"), verdict


@pytest.mark.parametrize(("fname", "where"), FILES, ids=[f for f, _ in FILES])
def test_budget_missing_file_is_unknown(rig: Rig, fname: str, where: tuple[str, str]) -> None:
    rig.write(fname, None)
    assert_unknown_everywhere(rig, fname, where, "No such file or directory")


def test_budget_memory_peak_missing_alone(rig: Rig) -> None:
    """A kernel before 5.19 has no memory.peak: that figure alone is unknown; the rest stand."""
    rig.write("memory.peak", None)
    doc = json_of(rig)
    assert_unknown(doc["memory"]["peak"], rig.cg / "memory.peak", strerror="No such file or directory")
    assert_figure(doc["memory"]["limit"], "value", MEM_MAX, rig.cg / "memory.max")
    assert_figure(doc["memory"]["current"], "value", MEM_CUR, rig.cg / "memory.current")
    _h, verdict, body = text_of(rig)
    assert body[0].startswith("memory: limit 300.0 MiB · in use 11.8 MiB · peak unknown ("), body[0]
    assert body[1:3] == [CPU_LINE, PROCESSES_LINE]
    assert verdict.startswith("memory 300.0 MiB, cpu 1.50 CPUs, "), verdict
    assert verdict.endswith("; 1 unknown"), verdict


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads a mode-000 file")
@pytest.mark.parametrize(("fname", "where"), FILES, ids=[f for f, _ in FILES])
def test_budget_unreadable_file_is_unknown(rig: Rig, fname: str, where: tuple[str, str]) -> None:
    (rig.cg / fname).chmod(0)
    try:
        assert_unknown_everywhere(rig, fname, where, "Permission denied")
    finally:
        (rig.cg / fname).chmod(0o644)


GARBAGE = [
    ("memory.max", "lots\n"),
    ("memory.current", "-5\n"),
    ("memory.peak", "1.5e9\n"),
    ("pids.max", "12x\n"),
    ("pids.current", ""),
    ("cpu.max", "abc def\n"),
    ("cpu.max", "150000\n"),
]


@pytest.mark.parametrize(("fname", "content"), GARBAGE, ids=[f"{f}={c.strip()!r}" for f, c in GARBAGE])
def test_budget_garbage_is_unknown(rig: Rig, fname: str, content: str) -> None:
    rig.write(fname, content)
    where = dict(FILES)[fname]
    assert_unknown_everywhere(rig, fname, where, None)


def test_budget_several_unknowns_are_counted(rig: Rig) -> None:
    rig.write("memory.peak", None)
    rig.write("pids.current", "lots\n")
    rig.write("cpu.max", None)
    doc = json_of(rig)
    assert doc["memory"]["peak"]["state"] == "unknown"
    assert doc["pids"]["current"]["state"] == "unknown"
    assert doc["cpu"]["limit"]["state"] == "unknown"
    _h, verdict, _b = text_of(rig)
    assert verdict.endswith("; 3 unknown"), verdict


# ── CPU: the hook's rule, in agentio and in the hook ───────────────────────────────────────────


@dataclass(frozen=True)
class CpuCase:
    id: str
    cpu_max: str | None  # file content; None = no such file
    affinity: str | None  # Cpus_allowed_list; None = no status file; "" = a status file without the line
    jobs: int
    state: str  # the limit's state
    limit: float | None
    count: int | None  # the affinity count


CPU_CASES = [
    CpuCase("quota-1.5-of-8", "150000 100000\n", "0-7", 2, "value", 1.5, 8),
    CpuCase("max-affinity-7", "max 100000\n", AFFINITY, 7, "none", None, 7),
    CpuCase("affinity-caps-quota", "800000 100000\n", "0-1", 2, "value", 8.0, 2),
    CpuCase("half-cpu-rounds-up", "50000 100000\n", "0-7", 1, "value", 0.5, 8),
    CpuCase("just-over-one", "100001 100000\n", "0-63", 2, "value", 1.0, 64),
    CpuCase("two-decimals", "333333 100000\n", "0-15", 4, "value", 3.33, 16),
    CpuCase("no-cpu-max", None, "0-5", 6, "unknown", None, 6),
    CpuCase("nothing-readable", None, None, 1, "unknown", None, None),
    CpuCase("garbage-cpu-max", "abc def\n", "0-3", 4, "unknown", None, 4),
    CpuCase("garbage-affinity", "200000 100000\n", "bogus", 2, "value", 2.0, None),
    CpuCase("zero-period", "300000 0\n", "0-4", 5, "unknown", None, 5),
    CpuCase("no-affinity-line", "250000 100000\n", "", 3, "value", 2.5, None),
]


def cpu_files(rig: Rig, case: CpuCase) -> tuple[Path, Path]:
    """The two files both readers are given: a cpu.max and a status, each possibly absent."""
    cm = rig.tmp / f"cpu.max-{case.id}"
    st = rig.tmp / f"status-{case.id}"
    if case.cpu_max is not None:
        cm.write_text(case.cpu_max)
    if case.affinity is not None:
        st.write_text(status_text(case.affinity or None))
    return cm, st


def hook_cpus(cpu_max: Path, status: Path, home: Path) -> str:
    """TIMELIKE_CPUS as the real hook computes it, in a fresh `env -i bash -c` that sources it."""
    env_bin = shutil.which("env") or "/usr/bin/env"
    bash = shutil.which("bash") or "/bin/bash"
    r = subprocess.run(
        [
            env_bin,
            "-i",
            "PATH=/nonexistent",
            f"HOME={home}",
            f"HOOK={HOOK}",
            f"TIMELIKE_CGROUP_CPU_MAX={cpu_max}",
            f"TIMELIKE_PROC_STATUS={status}",
            "TIMELIKE_JOURNAL_EXIT=/nonexistent",
            bash,
            "-c",
            '. "$HOOK"; printf "%s" "${TIMELIKE_CPUS-<unset>}"',
        ],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=30,
        start_new_session=True,
        cwd=home,
    )
    return r.stdout


@pytest.mark.parametrize("case", CPU_CASES, ids=[c.id for c in CPU_CASES])
def test_hook_cpus_table(rig: Rig, case: CpuCase) -> None:
    """The hook's half of the agreement table, against the hook that exists today."""
    cm, st = cpu_files(rig, case)
    assert hook_cpus(cm, st, rig.home) == str(case.jobs)


@pytest.mark.parametrize("case", CPU_CASES, ids=[c.id for c in CPU_CASES])
def test_budget_cpu_table(rig: Rig, case: CpuCase) -> None:
    cm, st = cpu_files(rig, case)
    doc = json_of(rig, TIMELIKE_CGROUP_CPU_MAX=str(cm), TIMELIKE_PROC_STATUS=str(st))
    cpu = doc["cpu"]
    assert cpu["jobs"] == case.jobs, cpu
    assert cpu["affinity"] == case.count, cpu
    lim = cpu["limit"]
    assert lim["state"] == case.state, lim
    assert lim["source"] == str(cm), lim
    if case.limit is None:
        assert lim["value"] is None, lim
    else:
        assert type(lim["value"]) is float and lim["value"] == pytest.approx(case.limit), lim
    if case.state == "unknown":
        assert_unknown(lim, cm)
    if case.state == "value":
        quota, period = (int(x) for x in (case.cpu_max or "").split())
        assert (lim["quota"], lim["period"]) == (quota, period), lim
        assert math.ceil(quota / period) >= 1
    _h, _v, body = text_of(rig, TIMELIKE_CGROUP_CPU_MAX=str(cm), TIMELIKE_PROC_STATUS=str(st))
    if case.state == "value":
        assert case.limit is not None
        assert body[1] == f"cpu: limit {case.limit:.2f} CPUs · job count {case.jobs} (TIMELIKE_CPUS)"
    elif case.state == "none":
        assert body[1] == f"cpu: limit no limit · job count {case.jobs} (TIMELIKE_CPUS)"
    else:
        assert body[1].startswith(f"cpu: limit unknown ({cm}: "), body[1]
        assert body[1].endswith(f") · job count {case.jobs} (TIMELIKE_CPUS)"), body[1]


@pytest.mark.parametrize("case", CPU_CASES, ids=[c.id for c in CPU_CASES])
def test_budget_jobs_agree_with_hook(rig: Rig, case: CpuCase) -> None:
    """FR-22: the same two files fed to both give the same job count."""
    cm, st = cpu_files(rig, case)
    doc = json_of(rig, TIMELIKE_CGROUP_CPU_MAX=str(cm), TIMELIKE_PROC_STATUS=str(st))
    assert str(doc["cpu"]["jobs"]) == hook_cpus(cm, st, rig.home)


def test_budget_cpu_max_override_wins_over_cgroup(rig: Rig) -> None:
    override = rig.tmp / "cpu.max-override"
    override.write_text("50000 100000\n")
    rig.write("cpu.max", "300000 100000\n")
    doc = json_of(rig, TIMELIKE_CGROUP_CPU_MAX=str(override))
    assert_figure(doc["cpu"]["limit"], "value", 0.5, override)
    assert doc["cpu"]["jobs"] == 1


# ── the shell's TIMELIKE_CPUS ──────────────────────────────────────────────────────────────────


def test_budget_shell_value_agrees(rig: Rig) -> None:
    doc = json_of(rig, TIMELIKE_CPUS="2")
    assert doc["cpu"]["shell_value"] == 2
    assert doc["cpu"]["agrees"] is True
    _h, _v, body = text_of(rig, TIMELIKE_CPUS="2")
    assert body[1] == f"{CPU_LINE} · this shell has TIMELIKE_CPUS=2, agrees"


def test_budget_shell_value_disagrees(rig: Rig) -> None:
    doc = json_of(rig, TIMELIKE_CPUS="5")
    assert doc["cpu"]["shell_value"] == 5
    assert doc["cpu"]["agrees"] is False
    _h, _v, body = text_of(rig, TIMELIKE_CPUS="5")
    assert body[1] == f"{CPU_LINE} · this shell has TIMELIKE_CPUS=5, disagrees"


def test_budget_shell_value_unset(rig: Rig) -> None:
    doc = json_of(rig)
    assert doc["cpu"]["shell_value"] is None
    assert doc["cpu"]["agrees"] is None
    assert text_of(rig)[2][1] == CPU_LINE


def test_budget_shell_value_not_an_int(rig: Rig) -> None:
    doc = json_of(rig, TIMELIKE_CPUS="two")
    assert doc["cpu"]["shell_value"] is None
    assert doc["cpu"]["agrees"] is None
    assert text_of(rig, TIMELIKE_CPUS="two")[2][1] == CPU_LINE


# ── disks ──────────────────────────────────────────────────────────────────────────────────────


def assert_disk(d: dict[str, Any], role: str, path: Path, measured: Path, exists: bool) -> None:
    assert d["role"] == role, d
    assert d["path"] == str(path), d
    assert os.path.realpath(d["measured"]) == os.path.realpath(measured), d
    assert d["exists"] is exists, d
    st = os.statvfs(measured)
    assert d["total_bytes"] == st.f_blocks * st.f_frsize, d
    assert abs(d["free_bytes"] - st.f_bavail * st.f_frsize) <= FREE_SLACK, d
    assert d["reason"] is None, d


def test_budget_workspace_is_the_git_ancestor(rig: Rig) -> None:
    doc = json_of(rig)
    ws, scratch = doc["disks"]
    assert_disk(ws, "workspace", rig.ws, rig.ws, True)
    assert_disk(scratch, "scratch", rig.scratch, rig.scratch, True)


def test_budget_workspace_git_file_counts(rig: Rig) -> None:
    """A `.git` entry, by lstat: a worktree's `.git` file counts as much as a directory."""
    other = rig.tmp / "wt"
    (other / "src").mkdir(parents=True)
    (other / ".git").write_text("gitdir: /nowhere\n")
    doc = json_of(rig, cwd=other / "src")
    assert_disk(doc["disks"][0], "workspace", other, other, True)


def test_budget_workspace_without_git_is_cwd(rig: Rig) -> None:
    plain = rig.tmp / "plain" / "deeper"
    plain.mkdir(parents=True)
    held = [p for p in plain.parents if os.path.lexists(p / ".git")]
    if held:
        pytest.skip(f"an ancestor of the test's tmp dir holds .git: {held[0]}")
    doc = json_of(rig, cwd=plain)
    assert_disk(doc["disks"][0], "workspace", plain, plain, True)
    _h, _v, body = text_of(rig, cwd=plain)
    st = os.statvfs(plain)
    assert re.match(disk_line_re("workspace", plain, st.f_blocks * st.f_frsize), body[3]), body[3]


def test_budget_scratch_root_not_there_yet(rig: Rig) -> None:
    missing = rig.tmp / "not-yet" / "scratch"
    doc = json_of(rig, TIMELIKE_SCRATCH_ROOT=str(missing))
    assert_disk(doc["disks"][1], "scratch", missing, rig.tmp, False)
    missing2 = rig.tmp / "not-yet-either" / "scratch"
    _h, verdict, body = text_of(rig, TIMELIKE_SCRATCH_ROOT=str(missing2))
    st = os.statvfs(rig.tmp)
    suffix = f" (measured at {rig.tmp}; {missing2} does not exist yet)"
    assert re.match(disk_line_re("scratch", missing2, st.f_blocks * st.f_frsize, suffix), body[4]), body[4]
    assert "unknown" not in verdict, "a scratch root not made yet is measured, not unknown"


# ── usage ──────────────────────────────────────────────────────────────────────────────────────


def test_budget_write_is_a_usage_error(rig: Rig) -> None:
    out = rig.tmp / "x"
    r = budget(rig.env(), "--write", str(out), cwd=rig.cwd)
    assert r.returncode == 2, (r.returncode, r.stdout, r.stderr)
    assert not out.exists()


def test_help_lists_budget(rig: Rig) -> None:
    r = subprocess.run(
        ["timelike", "--help"],
        env=rig.env(),
        cwd=rig.cwd,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=60,
        start_new_session=True,
    )
    assert r.returncode == 0, r.stderr
    want = "timelike budget            memory, CPU, process and disk limits, and what is in use"
    assert want in [x.strip() for x in r.stdout.splitlines()], r.stdout
