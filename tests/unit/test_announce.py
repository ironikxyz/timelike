"""`timelike announce` and `timelike tools` (feature 007, slice 0; contracts/timelike-announce-tools.md).

Written from the contract before the code (T002). Every expected value is computed here: the fake
tools' manifests, the announcement a placement copies, the curated file. Nothing is read back from
the tool under test and then asserted against itself (cross-stack P004/P005).

Fake tools are small POSIX sh scripts whose `--agent-info` prints a JSON manifest. `timelike` itself
is installed into a directory on PATH but outside TIMELIKE_BIN_DIRS, so the announcement covers
exactly the fakes, and no expected line depends on timelike's own summary.
"""

from __future__ import annotations

import json
import os
import re
import stat
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from conftest import AGENTIO_DIR, REPO, TOOLS_DIR, run

REVISION = "89abcdef0123456789abcdef0123456789abcdef"
OTHER_REVISION = "fedcba9876543210fedcba9876543210fedcba98"
MAX_LINES = 60
HARNESSES = ("claude-code", "codex", "opencode")
CURATED_FILE = REPO / "image" / "rootfs" / "etc" / "timelike" / "standard-tools.json"
VANILLA_DOCKERFILE = REPO / "bench" / "vanilla" / "Dockerfile"
RISKS = {"pager", "editor", "prompt", "repl", "waits", "unbounded output"}

# Fake timelike tools, deliberately created out of name order.
FAKES = {
    "charlie": "count the charlie things in a bounded window",
    "alpha": "show the alpha view of a file; ends with the next command",
    "bravo": "search bravo text across files",
}

# Curated entries the tests write themselves (TIMELIKE_STANDARD_TOOLS).
CURATED: list[dict[str, str]] = [
    {
        "name": "tlstd-pager",
        "summary": "a pager that waits for a key",
        "json": "no",
        "interactive_risk": "pager",
        "instead": "view FILE",
    },
    {
        "name": "tlstd-absent",
        "summary": "a command that prompts",
        "json": "partial: with --format json",
        "interactive_risk": "prompt",
        "instead": "",
    },
]
CURATED_PRESENT = {"tlstd-pager"}  # placed in a directory on PATH; tlstd-absent is nowhere


def marker(rev: str) -> str:
    return f"<!-- timelike announcement: revision {rev}; generated from the tools' manifests; do not edit -->"


def tool_line(name: str, summary: str) -> str:
    return f"- `{name}` — {summary}"


def expected_tool_lines(tools: dict[str, str]) -> list[str]:
    return [tool_line(n, tools[n]) for n in sorted(tools)]


def announcement_text(rev: str, tools: dict[str, str]) -> str:
    """An announcement in the contract's layout, built here (the source a placement copies)."""
    lines = [
        marker(rev),
        "",
        "# timelike",
        "",
        f"This container is timelike, revision {rev}.",
        "",
        "## Tools",
        "",
        *expected_tool_lines(tools),
        "",
        "## How to work here",
        "",
        "- Every command takes --json.",
        "",
        "The tools work the same whether or not this file is read.",
    ]
    return "\n".join(lines) + "\n"


def install(src: Path, bindir: Path) -> Path:
    """As test_conform.install: the shipped tool with the image's shebang swapped for this interpreter."""
    bindir.mkdir(parents=True, exist_ok=True)
    lines = src.read_text().splitlines(keepends=True)
    assert lines[0].startswith("#!/opt/timelike/python/bin/python3"), f"{src} has an unexpected shebang"
    dst = bindir / src.name
    dst.write_text(f"#!{sys.executable}\n" + "".join(lines[1:]))
    dst.chmod(0o755)
    return dst


def fake_tool(bindir: Path, name: str, summary: str, *, fail: bool = False) -> Path:
    """A tool whose `--agent-info` prints a manifest shaped like a real one (see `view --agent-info`)."""
    bindir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "tool": name,
        "target": "fixture",
        "scope": "agent-info",
        "contract": 1,
        "destructive": False,
        "envelopes": [],
        "exit_codes": {"0": "ok", "1": "failure", "2": "usage"},
        "flags": ["--agent-info", "--help", "--json", "--limit", "--text", "--verbose"],
        "mutating": False,
        "probe": [],
        "reads_stdin": False,
        "summary": summary,
        "usage": f"{name} [--json|--text]",
    }
    if fail:
        on_info = 'echo "manifest unavailable" >&2\n    exit 1'
    else:
        on_info = f"cat <<'MANIFEST'\n{json.dumps(manifest)}\nMANIFEST\n    exit 0"
    script = (
        "#!/bin/sh\n"
        'for a in "$@"; do\n'
        '  if [ "$a" = "--agent-info" ]; then\n'
        f"    {on_info}\n"
        "  fi\n"
        "done\n"
        f'echo "{name}: fixture" ; exit 0\n'
    )
    path = bindir / name
    path.write_text(script)
    path.chmod(0o755)
    return path


@dataclass
class Rig:
    tmp: Path
    fakebin: Path  # TIMELIKE_BIN_DIRS
    tldir: Path  # timelike itself: on PATH, not in TIMELIKE_BIN_DIRS
    stddir: Path  # curated tools that are "installed"
    home: Path
    scratch: Path
    tools: dict[str, str] = field(default_factory=dict)

    def env(
        self,
        bin_dirs: list[Path] | None = None,
        path_dirs: list[Path] | None = None,
        **extra: str,
    ) -> dict[str, str]:
        dirs = [self.fakebin] if bin_dirs is None else bin_dirs
        on_path = [*dirs, self.tldir, self.stddir] if path_dirs is None else path_dirs
        env = {
            "PATH": ":".join([*(str(d) for d in on_path), "/usr/bin", "/bin"]),
            "PYTHONPATH": str(AGENTIO_DIR),
            "HOME": str(self.home),
            "TIMELIKE_SCRATCH_ROOT": str(self.scratch),
            "TIMELIKE_SESSION": "test",
            "TIMELIKE_BIN_DIRS": ":".join(str(d) for d in dirs),
            "TIMELIKE_REVISION": REVISION,
            "LC_ALL": "C.UTF-8",
        }
        if "COVERAGE_PROCESS_START" in os.environ:
            env["COVERAGE_PROCESS_START"] = os.environ["COVERAGE_PROCESS_START"]
        env.update(extra)
        return env


@pytest.fixture
def rig(tmp_path: Path) -> Rig:
    r = Rig(
        tmp=tmp_path,
        fakebin=tmp_path / "fakebin",
        tldir=tmp_path / "tl",
        stddir=tmp_path / "std",
        home=tmp_path / "home",
        scratch=tmp_path / "scratch",
    )
    install(TOOLS_DIR / "timelike", r.tldir)
    for name, summary in FAKES.items():
        fake_tool(r.fakebin, name, summary)
    r.tools = dict(FAKES)
    # Not tools: a non-executable file and a directory (directories carry the x bit).
    (r.fakebin / "zz-notes").write_text("not a tool\n")
    (r.fakebin / "zz-notes").chmod(0o644)
    (r.fakebin / "subdir").mkdir()
    for name in CURATED_PRESENT:
        fake_tool(r.stddir, name, "a curated stand-in")
    r.home.mkdir()
    return r


def timelike(env: dict[str, str], *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    if cwd is None:
        return run(["timelike", *args], env, timeout=60)
    return subprocess.run(
        ["timelike", *args],
        env=env,
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=60,
        start_new_session=True,
    )


def doc_of(r: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    try:
        doc: dict[str, Any] = json.loads(r.stdout)
    except json.JSONDecodeError:
        pytest.fail(f"stdout is not one JSON document (exit {r.returncode}): {r.stdout!r} / {r.stderr!r}")
    return doc


def nonblank(lines: list[str]) -> list[str]:
    return [x for x in lines if x.strip()]


def section(lines: list[str], heading: str) -> list[str]:
    """The lines under `heading`, up to the next `## ` heading."""
    assert heading in lines, f"no {heading!r} line in {lines}"
    start = lines.index(heading) + 1
    out: list[str] = []
    for x in lines[start:]:
        if x.startswith("## "):
            break
        out.append(x)
    return out


def tree(root: Path) -> dict[str, tuple[str, bytes, int]]:
    """Every path under root with its kind, bytes and mtime: the evidence that nothing changed."""
    out: dict[str, tuple[str, bytes, int]] = {}
    for p in sorted(root.rglob("*")):
        st = p.lstat()
        if p.is_dir():
            out[str(p.relative_to(root))] = ("dir", b"", st.st_mtime_ns)
        else:
            out[str(p.relative_to(root))] = ("file", p.read_bytes(), st.st_mtime_ns)
    return out


# ── the announcement: generation ───────────────────────────────────────────────────────────────


def announce_lines(rig: Rig, bin_dirs: list[Path] | None = None) -> list[str]:
    r = timelike(rig.env(bin_dirs=bin_dirs), "announce", "--json")
    assert r.returncode == 0, (r.stdout, r.stderr)
    lines = doc_of(r)["lines"]
    assert isinstance(lines, list)
    return [str(x) for x in lines]


def test_announce_layout(rig: Rig) -> None:
    lines = announce_lines(rig)
    assert lines[0] == marker(REVISION)
    assert "# timelike" in lines
    title = lines.index("# timelike")
    tools_at = lines.index("## Tools")
    rules_at = lines.index("## How to work here")
    assert 0 < title < tools_at < rules_at
    assert any(REVISION in x for x in lines[title + 1 : tools_at]), "no line naming the revision"
    assert nonblank(section(lines, "## Tools")) == expected_tool_lines(rig.tools)
    after = nonblank(lines[rules_at + 1 :])
    assert "--json" in "\n".join(after), "the rules say --json is everywhere (spec FR-2)"
    assert len(after) <= 6 + 1, "at most 6 lines of rules, then the closing line"
    assert not after[-1].startswith("#"), "the last line is the closing line, not a heading"
    assert len(lines) <= MAX_LINES


def test_announce_rules_name_run_and_timelike_tools_only_when_installed(rig: Rig) -> None:
    """Spec FR-2's rules name `run` and `timelike tools`; its measurable outcome says the announcement
    never names a tool that is not installed. So each rule appears exactly when its tool does."""

    def rules(bin_dirs: list[Path]) -> str:
        lines = announce_lines(rig, bin_dirs)
        return "\n".join(lines[lines.index("## How to work here") + 1 :])

    without = rules([rig.fakebin])
    assert "`run" not in without
    assert "timelike tools" not in without
    rundir = rig.tmp / "rundir"
    fake_tool(rundir, "run", "run a command to a conclusion")
    with_both = rules([rig.fakebin, rundir, rig.tldir])
    assert "`run" in with_both, "FR-2: long or hanging commands go through run"
    assert "timelike tools" in with_both, "FR-2: timelike tools prints the full manifest"


def test_announce_ignores_non_executables_and_directories(rig: Rig) -> None:
    body = "\n".join(announce_lines(rig))
    assert "zz-notes" not in body
    assert "subdir" not in body


def test_announce_merges_bin_dirs_in_name_order(rig: Rig) -> None:
    second = rig.tmp / "fakebin2"
    fake_tool(second, "aardvark", "the first by name, in the second directory")
    fake_tool(second, "delta", "the last by name")
    tools = {
        **rig.tools,
        "aardvark": "the first by name, in the second directory",
        "delta": "the last by name",
    }
    r = timelike(rig.env(bin_dirs=[rig.fakebin, second]), "announce", "--json")
    assert r.returncode == 0, r.stderr
    assert nonblank(section(doc_of(r)["lines"], "## Tools")) == expected_tool_lines(tools)


def test_announce_text_prints_the_same_lines(rig: Rig) -> None:
    expected = announce_lines(rig)
    r = timelike(rig.env(), "announce", "--text")
    assert r.returncode == 0, r.stderr
    out = r.stdout.splitlines()
    n = len(expected)
    assert any(out[i : i + n] == expected for i in range(len(out) - n + 1)), out


def test_announce_json_carries_the_tool_list(rig: Rig) -> None:
    doc = doc_of(timelike(rig.env(), "announce", "--json"))
    names = sorted(rig.tools)

    def is_tool_list(v: Any) -> bool:
        if not isinstance(v, list) or not v:
            return False
        got = [x.get("name") if isinstance(x, dict) else x for x in v]
        return got == names

    assert any(is_tool_list(v) for k, v in doc.items() if k != "lines"), doc


def test_announce_over_sixty_lines_fails(rig: Rig) -> None:
    many = rig.tmp / "many"
    for i in range(MAX_LINES):
        fake_tool(many, f"tool{i:03d}", f"fixture tool {i}")
    out = rig.tmp / "out.md"
    r = timelike(rig.env(bin_dirs=[many]), "announce", "--write", str(out))
    assert r.returncode == 1, (r.stdout, r.stderr)
    assert str(MAX_LINES) in r.stdout + r.stderr, "the failure names the 60-line bound"
    assert not out.exists(), "a failed generation writes nothing"


def test_announce_failing_agent_info_names_the_tool(rig: Rig) -> None:
    fake_tool(rig.fakebin, "brokentool", "never shown", fail=True)
    out = rig.tmp / "out.md"
    r = timelike(rig.env(), "announce", "--write", str(out))
    assert r.returncode == 1, (r.stdout, r.stderr)
    assert "brokentool" in r.stdout + r.stderr
    assert not out.exists(), "a failed generation writes nothing"
    assert timelike(rig.env(), "announce", "--json").returncode == 1


def test_announce_write_writes_the_same_lines(rig: Rig) -> None:
    expected = announce_lines(rig)
    out = rig.tmp / "written.md"
    r = timelike(rig.env(), "announce", "--write", str(out))
    assert r.returncode == 0, r.stderr
    assert out.read_text() == "\n".join(expected) + "\n"


# ── the announcement: --check ──────────────────────────────────────────────────────────────────


def check(rig: Rig, path: Path, *extra: str) -> tuple[int, str]:
    r = timelike(rig.env(), "announce", "--check", str(path), "--json", *extra)
    return r.returncode, str(doc_of(r)["verdict"])


def test_check_equal_passes(rig: Rig) -> None:
    f = rig.tmp / "a.md"
    f.write_text(announcement_text(REVISION, rig.tools))
    code, verdict = check(rig, f)
    assert code == 0, verdict


def test_check_names_a_missing_tool(rig: Rig) -> None:
    f = rig.tmp / "a.md"
    f.write_text(announcement_text(REVISION, {k: v for k, v in rig.tools.items() if k != "bravo"}))
    code, verdict = check(rig, f)
    assert code == 1
    assert "missing: bravo" in verdict


def test_check_names_every_missing_tool(rig: Rig) -> None:
    f = rig.tmp / "a.md"
    f.write_text(announcement_text(REVISION, {"charlie": rig.tools["charlie"]}))
    code, verdict = check(rig, f)
    assert code == 1
    assert "missing: alpha, bravo" in verdict


def test_check_names_an_extra_tool(rig: Rig) -> None:
    f = rig.tmp / "a.md"
    f.write_text(announcement_text(REVISION, {**rig.tools, "ghost": "not installed anywhere"}))
    code, verdict = check(rig, f)
    assert code == 1
    assert "extra: ghost" in verdict
    assert "missing" not in verdict


def test_check_reads_timelike_announcement_by_default(rig: Rig) -> None:
    f = rig.tmp / "a.md"
    f.write_text(announcement_text(REVISION, {k: v for k, v in rig.tools.items() if k != "alpha"}))
    r = timelike(rig.env(TIMELIKE_ANNOUNCEMENT=str(f)), "announce", "--check", "--json")
    assert r.returncode == 1
    assert "missing: alpha" in str(doc_of(r)["verdict"])


def test_check_on_what_write_wrote_passes(rig: Rig) -> None:
    out = rig.tmp / "written.md"
    assert timelike(rig.env(), "announce", "--write", str(out)).returncode == 0
    code, verdict = check(rig, out)
    assert code == 0, verdict


# ── placement: --install and --status ──────────────────────────────────────────────────────────


def paths(home: Path, codex_home: Path | None = None) -> dict[str, Path]:
    return {
        "claude-code": home / ".claude" / "CLAUDE.md",
        "codex": (codex_home or home / ".codex") / "AGENTS.md",
        "opencode": home / ".config" / "opencode" / "AGENTS.md",
    }


@pytest.fixture
def source(rig: Rig) -> Path:
    """The announcement a placement copies: built by the test, at the image's revision."""
    f = rig.tmp / "etc" / "announcement.md"
    f.parent.mkdir()
    f.write_text(announcement_text(REVISION, rig.tools))
    return f


def place_env(rig: Rig, source: Path, codex_home: Path | None = None) -> dict[str, str]:
    env = rig.env(TIMELIKE_ANNOUNCEMENT=str(source))
    env.pop("CODEX_HOME", None)
    if codex_home is not None:
        env["CODEX_HOME"] = str(codex_home)
    return env


def placements(r: subprocess.CompletedProcess[str]) -> dict[str, dict[str, Any]]:
    assert r.returncode == 0, ("--install and --status always exit 0", r.stdout, r.stderr)
    entries = doc_of(r)["placements"]
    assert isinstance(entries, list)
    by_harness = {str(p["harness"]): p for p in entries}
    assert sorted(by_harness) == sorted(HARNESSES), entries
    for p in entries:
        assert set(p) >= {"harness", "path", "state", "reason"}, p
    return by_harness


def install_json(env: dict[str, str], cwd: Path | None = None) -> dict[str, dict[str, Any]]:
    return placements(timelike(env, "announce", "--install", "--json", cwd=cwd))


@pytest.mark.parametrize("codex", ["unset", "set"])
def test_install_places_all_three_byte_identical(rig: Rig, source: Path, codex: str) -> None:
    codex_home = rig.tmp / "codexhome" if codex == "set" else None
    got = install_json(place_env(rig, source, codex_home))
    want = paths(rig.home, codex_home)
    for h in HARNESSES:
        assert got[h]["state"] == "placed", got[h]
        assert got[h]["path"] == str(want[h])
        assert want[h].read_bytes() == source.read_bytes(), f"{h}: not byte-identical to the source"
        assert stat.S_IMODE(want[h].stat().st_mode) == 0o644
        assert len(want[h].read_text().splitlines()) <= MAX_LINES
    if codex_home is not None:
        assert not (rig.home / ".codex").exists(), "CODEX_HOME was set; ~/.codex is not Codex's home"


def test_install_creates_directories_0700_and_leaves_no_temporaries(rig: Rig, source: Path) -> None:
    install_json(place_env(rig, source))
    for d in (rig.home / ".claude", rig.home / ".codex", rig.home / ".config", rig.home / ".config/opencode"):
        assert stat.S_IMODE(d.stat().st_mode) == 0o700, d
    assert sorted(os.listdir(rig.home / ".claude")) == ["CLAUDE.md"]
    assert sorted(os.listdir(rig.home / ".codex")) == ["AGENTS.md"]
    assert sorted(os.listdir(rig.home / ".config" / "opencode")) == ["AGENTS.md"]


def test_install_verdict_counts_the_states(rig: Rig, source: Path) -> None:
    r = timelike(place_env(rig, source), "announce", "--install", "--json")
    verdict = str(doc_of(r)["verdict"])
    assert re.search(r"\b3 placed\b|\bplaced: 3\b", verdict), verdict


def test_install_never_writes_the_workspace(rig: Rig, source: Path) -> None:
    ws = rig.tmp / "workspace"
    ws.mkdir()
    install_json(place_env(rig, source), cwd=ws)
    assert os.listdir(ws) == [], "spec FR-7: the workspace's context files are never created"


def test_install_after_write_places_what_was_written(rig: Rig) -> None:
    written = rig.tmp / "written.md"
    assert timelike(rig.env(), "announce", "--write", str(written)).returncode == 0
    got = install_json(place_env(rig, written))
    for h, p in paths(rig.home).items():
        assert got[h]["state"] == "placed"
        assert p.read_bytes() == written.read_bytes()


def test_install_current_leaves_the_file_untouched(rig: Rig, source: Path) -> None:
    # Contract (settled at implementation): `current` is byte-identical to the announcement.
    want = paths(rig.home)
    for p in want.values():
        p.parent.mkdir(parents=True)
        p.write_bytes(source.read_bytes())
        os.utime(p, ns=(1_000_000_000, 1_000_000_000))
    got = install_json(place_env(rig, source))
    for h, p in want.items():
        assert got[h]["state"] == "current", got[h]
        assert p.read_bytes() == source.read_bytes()
        assert p.stat().st_mtime_ns == 1_000_000_000


def test_install_replaces_a_hand_edited_copy_at_the_same_revision(rig: Rig, source: Path) -> None:
    # The marker says "do not edit": a timelike file at this revision with another body is restored.
    want = paths(rig.home)
    old = marker(REVISION) + "\nan edited body at the same revision\n"
    for p in want.values():
        p.parent.mkdir(parents=True)
        p.write_text(old)
    got = install_json(place_env(rig, source))
    for h, p in want.items():
        assert got[h]["state"] == "replaced", got[h]
        assert p.read_bytes() == source.read_bytes()


def test_install_replaces_timelikes_file_at_another_revision(rig: Rig, source: Path) -> None:
    want = paths(rig.home)
    for p in want.values():
        p.parent.mkdir(parents=True)
        p.write_text(announcement_text(OTHER_REVISION, {"old": "a tool from an older image"}))
    got = install_json(place_env(rig, source))
    for h, p in want.items():
        assert got[h]["state"] == "replaced", got[h]
        assert p.read_bytes() == source.read_bytes()


def test_install_never_overwrites_someone_elses_file(rig: Rig, source: Path) -> None:
    want = paths(rig.home)
    theirs = want["claude-code"]
    theirs.parent.mkdir(parents=True)
    body = b"# my own instructions\n\nmentions timelike announcement but is not its marker\n"
    theirs.write_bytes(body)
    got = install_json(place_env(rig, source))
    assert str(got["claude-code"]["state"]).startswith("not placed"), got["claude-code"]
    assert got["claude-code"]["reason"], "a not-placed state carries its reason"
    assert theirs.read_bytes() == body
    assert got["codex"]["state"] == "placed"
    assert got["opencode"]["state"] == "placed"


def test_install_skips_a_directory_where_the_file_should_be(rig: Rig, source: Path) -> None:
    blocker = paths(rig.home)["opencode"]
    blocker.mkdir(parents=True)
    (blocker / "keep").write_text("x")
    got = install_json(place_env(rig, source))
    assert str(got["opencode"]["state"]).startswith("not placed"), got["opencode"]
    assert got["opencode"]["reason"]
    assert (blocker / "keep").read_text() == "x"
    assert got["claude-code"]["state"] == "placed"


@pytest.mark.skipif(os.geteuid() == 0, reason="root writes a 0500 directory")
def test_install_skips_an_unwritable_home(rig: Rig, source: Path) -> None:
    rig.home.chmod(0o500)
    try:
        got = install_json(place_env(rig, source))
        for h in HARNESSES:
            assert str(got[h]["state"]).startswith("not placed"), got[h]
            assert got[h]["reason"]
        assert os.listdir(rig.home) == []
    finally:
        rig.home.chmod(0o700)


@pytest.mark.skipif(os.geteuid() == 0, reason="root writes a 0500 directory")
def test_install_skips_one_unwritable_directory(rig: Rig, source: Path) -> None:
    claude = rig.home / ".claude"
    claude.mkdir()
    claude.chmod(0o500)
    try:
        got = install_json(place_env(rig, source))
        assert str(got["claude-code"]["state"]).startswith("not placed"), got["claude-code"]
        assert got["codex"]["state"] == "placed"
        assert got["opencode"]["state"] == "placed"
    finally:
        claude.chmod(0o700)


def test_install_exits_0_when_home_is_not_a_directory(rig: Rig, source: Path) -> None:
    home_file = rig.tmp / "home-is-a-file"
    home_file.write_text("not a directory\n")
    env = place_env(rig, source)
    env["HOME"] = str(home_file)
    got = install_json(env)
    for h in HARNESSES:
        assert str(got[h]["state"]).startswith("not placed"), got[h]
    assert home_file.read_text() == "not a directory\n"


def test_install_exits_0_when_the_source_is_missing(rig: Rig) -> None:
    got = install_json(place_env(rig, rig.tmp / "no-such-announcement.md"))
    for h, p in paths(rig.home).items():
        assert str(got[h]["state"]).startswith("not placed"), got[h]
        assert not p.exists()


@pytest.mark.parametrize("codex", ["unset", "set"])
def test_install_reports_codex_override_as_shadowed(rig: Rig, source: Path, codex: str) -> None:
    codex_home = rig.tmp / "codexhome" if codex == "set" else None
    override = (codex_home or rig.home / ".codex") / "AGENTS.override.md"
    override.parent.mkdir(parents=True)
    override.write_text("operator override\n")
    got = install_json(place_env(rig, source, codex_home))
    state = str(got["codex"]["state"])
    assert state.startswith("shadowed"), got["codex"]
    assert "AGENTS.override.md" in state + str(got["codex"]["reason"])
    assert override.read_text() == "operator override\n"
    assert got["claude-code"]["state"] == "placed"


def test_install_empty_codex_override_does_not_shadow(rig: Rig, source: Path) -> None:
    override = rig.home / ".codex" / "AGENTS.override.md"
    override.parent.mkdir(parents=True)
    override.write_text("")
    got = install_json(place_env(rig, source))
    assert got["codex"]["state"] == "placed", got["codex"]
    assert paths(rig.home)["codex"].read_bytes() == source.read_bytes()


def test_status_changes_nothing(rig: Rig, source: Path) -> None:
    theirs = paths(rig.home)["codex"]
    theirs.parent.mkdir(parents=True)
    theirs.write_text("someone else's\n")
    before = tree(rig.home)
    got = placements(timelike(place_env(rig, source), "announce", "--status", "--json"))
    assert tree(rig.home) == before
    for h, p in paths(rig.home).items():
        assert got[h]["path"] == str(p)
    assert str(got["codex"]["state"]).startswith("not placed")


def test_status_after_install_is_current(rig: Rig, source: Path) -> None:
    env = place_env(rig, source)
    install_json(env)
    before = tree(rig.home)
    got = placements(timelike(env, "announce", "--status", "--json"))
    for h in HARNESSES:
        assert got[h]["state"] == "current", got[h]
    assert tree(rig.home) == before


def test_status_text_names_each_placement(rig: Rig, source: Path) -> None:
    env = place_env(rig, source)
    install_json(env)
    r = timelike(env, "announce", "--status", "--text")
    assert r.returncode == 0
    for h, p in paths(rig.home).items():
        assert any(h in x and str(p) in x and "current" in x for x in r.stdout.splitlines()), r.stdout


# ── the manifest: timelike tools ───────────────────────────────────────────────────────────────


@pytest.fixture
def curated(rig: Rig) -> Path:
    f = rig.tmp / "standard-tools.json"
    f.write_text(json.dumps({"v": 1, "tools": CURATED}))
    return f


def expected_entries(rig: Rig, *, fakes_on_path: bool = True) -> list[dict[str, Any]]:
    ours = [
        {
            "name": n,
            "kind": "timelike",
            "installed": fakes_on_path,
            "summary": rig.tools[n],
            "json": "yes",
            "interactive_risk": "none",
            "instead": "",
        }
        for n in sorted(rig.tools)
    ]
    std = [
        {**c, "kind": "standard", "installed": c["name"] in CURATED_PRESENT}
        for c in sorted(CURATED, key=lambda c: c["name"])
    ]
    return ours + std


def test_tools_json_lists_timelike_and_curated_entries(rig: Rig, curated: Path) -> None:
    r = timelike(rig.env(TIMELIKE_STANDARD_TOOLS=str(curated)), "tools", "--json")
    assert r.returncode == 0, r.stderr
    got = doc_of(r)["tools"]
    keys = ("name", "kind", "installed", "summary", "json", "interactive_risk", "instead")
    assert [{k: e.get(k) for k in keys} for e in got] == expected_entries(rig)


def test_tools_installed_follows_path(rig: Rig, curated: Path) -> None:
    env = rig.env(TIMELIKE_STANDARD_TOOLS=str(curated), path_dirs=[rig.tldir])
    r = timelike(env, "tools", "--json")
    assert r.returncode == 0, r.stderr
    installed = {e["name"]: e["installed"] for e in doc_of(r)["tools"]}
    assert installed == {e["name"]: False for e in expected_entries(rig)}


def test_tools_verdict_counts(rig: Rig, curated: Path) -> None:
    r = timelike(rig.env(TIMELIKE_STANDARD_TOOLS=str(curated)), "tools", "--json")
    verdict = str(doc_of(r)["verdict"])
    m = re.search(r"(\d+) timelike tools, (\d+) standard tools \((\d+) installed\)", verdict)
    assert m, verdict
    assert int(m[1]) == len(FAKES)
    assert int(m[2]) == len(CURATED)
    # The contract does not say what K counts: the standard tools installed, or every entry installed.
    assert int(m[3]) in {len(CURATED_PRESENT), len(CURATED_PRESENT) + len(FAKES)}, verdict


def test_tools_text_one_line_per_entry(rig: Rig, curated: Path) -> None:
    r = timelike(rig.env(TIMELIKE_STANDARD_TOOLS=str(curated)), "tools", "--text")
    assert r.returncode == 0, r.stderr
    out = r.stdout.splitlines()
    for e in expected_entries(rig):
        # An empty `instead` may drop its `  instead:` field; the contract's template does not say.
        rx = re.compile(
            rf"^{re.escape(e['name'])}  \[{e['kind']}\]  json={re.escape(e['json'])}"
            rf"  risk={re.escape(e['interactive_risk'])}(?:  instead:(.*))?$"
        )
        hits = [m for m in map(rx.match, out) if m]
        assert len(hits) == 1, (e["name"], out)
        assert (hits[0][1] or "").strip() == e["instead"]


@pytest.mark.parametrize(
    "content",
    [
        "not json at all",
        json.dumps({"v": 2, "tools": CURATED}),
        json.dumps({"v": 1, "tools": "less"}),
        json.dumps({"v": 1, "tools": [{k: v for k, v in CURATED[0].items() if k != "instead"}]}),
    ],
    ids=["not-json", "wrong-version", "tools-not-a-list", "entry-missing-a-field"],
)
def test_tools_malformed_curated_file_fails_naming_it(rig: Rig, content: str) -> None:
    f = rig.tmp / "broken-standard-tools.json"
    f.write_text(content)
    r = timelike(rig.env(TIMELIKE_STANDARD_TOOLS=str(f)), "tools", "--json")
    assert r.returncode == 1, (r.stdout, r.stderr)
    assert "broken-standard-tools.json" in r.stdout + r.stderr


@pytest.mark.skipif(not CURATED_FILE.exists(), reason="T001 has not created standard-tools.json yet")
def test_repository_curated_file_shape() -> None:
    doc = json.loads(CURATED_FILE.read_text())
    assert doc["v"] == 1
    assert isinstance(doc["tools"], list) and doc["tools"]
    names: list[str] = []
    for e in doc["tools"]:
        assert set(e) >= {"name", "summary", "json", "interactive_risk", "instead"}, e
        assert isinstance(e["name"], str) and e["name"], e
        assert isinstance(e["summary"], str) and e["summary"], e
        assert e["json"] in {"yes", "no"} or re.fullmatch(r"partial: \S.*", e["json"]), e
        risk = e["interactive_risk"]
        assert risk == "none" or {x.strip() for x in risk.split(",")} <= RISKS, e
        assert isinstance(e["instead"], str), e
        names.append(e["name"])
    assert len(names) == len(set(names)), "duplicate curated names"
    first_words = {n.split()[0] for n in names}
    # Spec FR-11's single-word traps; multi-word ones (grep -r, npm init) are not asserted by name.
    for trap in ("less", "more", "vi", "nano", "cat", "find", "tree", "python3", "node", "ssh", "sudo"):
        assert trap in first_words, f"FR-11: {trap} is not curated"
    for trap in ("make", "pytest", "curl", "git"):
        assert trap in first_words, f"FR-11: {trap} is not curated"


# ── P6 and existing behaviour ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "needle", ["announcement", "standard-tools.json", "libexec/entrypoint", "timelike announce"]
)
def test_vanilla_dockerfile_references_none_of_this_feature(needle: str) -> None:
    assert VANILLA_DOCKERFILE.exists()
    assert needle not in VANILLA_DOCKERFILE.read_text(), f"P6: the vanilla image mentions {needle!r}"


def test_plain_timelike_is_unchanged(rig: Rig) -> None:
    env = rig.env(bin_dirs=[rig.fakebin, rig.tldir])
    r = timelike(env, "--json")
    assert r.returncode == 0, r.stderr
    doc = doc_of(r)
    names = sorted([*FAKES, "timelike"])
    assert doc["revision"] == REVISION
    assert doc["contract"] == 1
    assert doc["tools"] == names
    assert doc["count"] == len(names)
    assert doc["lines"] == [f"revision: {REVISION}", "contract: 1", f"tools: {len(names)}"] + [
        f"  {n}" for n in names
    ]
    assert doc["verdict"] == f"ok: {len(names)} timelike tools on PATH"
    assert (doc["target"], doc["scope"]) == ("environment", "summary")
    assert set(doc) == {
        "tool", "target", "scope", "verdict", "exit", "lines", "errors",
        "revision", "contract", "tools", "count",
    }  # fmt: skip
