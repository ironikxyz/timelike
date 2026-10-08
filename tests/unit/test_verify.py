"""verify (feature 012, slice 1, T001) against contracts/verify-cli.md, data-model.md, research R1-R7.

Written from the contract alone, before the tool. Two kinds of input, and neither is written by hand:
- **Recorded runner output** (`tests/fixtures/verify/recorded/*.out`, real pytest, jest, vitest, go, cargo,
  ruff, mypy, tsc and eslint output, each with its `.source` sidecar). It reaches the parser through the
  real chain: `verify test -- sh -c 'cat REC; exit E'`, where E is the exit the sidecar recorded, so
  `run` executes a command whose output IS the runner's.
- **Projects written by `tests/fixtures/verify/make-project.sh`**, the generator the recordings were made
  from. Every expected count, test name, file and line comes from what the generator wrote (P005): a line
  is found by locating a needle in the generated text, never read from `verify`'s output (P004).

How the tools are run: `verify` finds `run` and `symbols` beside itself, and their shebang names the
image's interpreter. Each test copies `tools/bin/{verify,run,symbols,search}` into its own directory with
the shebang rewritten to the host interpreter (test_conform's pattern), and runs `python verify …` with
conftest's environment. A test about `verify`'s handling of a `run` result copies `verify` alone, beside a
stub `run` (a Python script), so the stub is what `verify` finds.

Ambiguities settled here (the contract is the authority; the report lists them):
- Contract amendment (tool author, via the coordinator): global flags go before the subcommand; any first
  word other than `test`/`changed` is the command (`verify sh -c …` is `verify test -- sh -c …`);
  `verify test` options without `--` are a usage error; the manifest has `passes_exit: true`, no
  `takes_command` key, `dry_run: false`, probe `["true"]`; outside a repository `changed` is a usage
  error on stderr (exit 2), not a header/verdict result.
- A failure's `test` is compared exactly for pytest (node id), go and cargo; for jest and vitest the
  generator's title must be contained in it (a "title path" may carry the file or a `>`/`›` prefix).
- `file` is compared after dropping a leading `./` (jest prints `FAIL ./math.test.js`).
- Failures are compared as a set: the order of the blocks is not pinned.
- The verdict's `exit N` may carry `run`'s own words after it (`exit 1 (command exited 1) · 0.0 s · 56
  lines · log …`): spec SC-1 says "then run's exit, duration and log path", and the contract's table
  row abbreviates it.
- A count the summary does not mention when it would be zero (pytest's `failed` on an all-passed run,
  `skipped` everywhere) may be 0 or null; a count the format cannot report (go's passes without `-v`,
  every count of an unknown format) must be null.
- Assertion lines: at most 5 per failure, and they contain the generator's own message where the test
  has one (`1 + 2 should round to 4`, `empty order`, `not a number: abc`, `abc should parse`, …).
- `--limit N` bounds the failure blocks (N=1: one block header) and the omission line is rule 3's,
  starting `… omitted`; it must name `run`'s log, as spec "More failures than --limit" says.
- The session event's `ref` is compared by value (`run`'s log path), not by its key.
- Redaction unavailable is produced with the REAL `run`: TIMELIKE_REDACTION_RULES naming a missing file
  makes `run` withhold its output and mark `redaction.state = unavailable`. `verify` must then keep counts,
  names and locations, and withhold the assertion lines (each failure's `lines` is empty).
- Linter recordings (ruff, mypy, tsc, eslint) are not test formats: through `verify test` they are
  `format unknown`. Their diagnostics are read in `verify changed`, where a stub linter on PATH replays the
  recording on the lint project (`<PROJECT>` put back to the project's path).
- A deleted file's dependents are still found (spec edge case), so deleting `app/cli.py` selects
  `tests/test_cli.py` with the reason `imports app/cli.py`.
- A step's diagnostics or failures are located anywhere inside the step's JSON (`report` or a
  `diagnostics` list: the data model names both), by `file` and `line`. A diagnostic's `file` is
  relative to the workspace, as the contract's example (`app/models.py:1:8`), even where the linter
  printed an absolute path (eslint's stylish format).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
import schema
from conftest import FIXTURES, TOOLS_DIR, base_env, events

VERIFY = TOOLS_DIR / "verify"
SESSION = "verify-t001"
GEN = FIXTURES / "verify" / "make-project.sh"
REC = FIXTURES / "verify" / "recorded"
Proc = subprocess.CompletedProcess[str]

pytestmark = pytest.mark.skipif(not VERIFY.exists(), reason="tools/bin/verify is not written yet (T003)")

SUMMARY_UNKNOWN = "format unknown: no pytest, jest, vitest, go test or cargo test summary"
BLOCK_HEAD = re.compile(r"^(\S+?):(\d+)  (\S.*)$")


# ── the projects, from the generator ────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def projects(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    root = tmp_path_factory.mktemp("projects")
    out = {}
    for kind in ("pytest", "jest", "vitest", "go", "cargo", "lint"):
        subprocess.run(["bash", str(GEN), kind, str(root / kind)], check=True, timeout=60)
        out[kind] = root / kind
    return out


def line_of(src: str, needle: str) -> int:
    """The 1-based line of the one line of the generated text holding `needle`."""
    hits = [i for i, text in enumerate(src.splitlines(), 1) if needle in text]
    assert len(hits) == 1, (needle, hits)
    return hits[0]


@dataclass(frozen=True)
class Fail:
    test: str  # the runner's name (exact), or the generator's title (contained) for jest/vitest
    file: str  # the generated file the failure is raised in
    needle: str  # the generated line it is raised at
    message: str | None  # the generator's own message, expected among the assertion lines


PYTEST_FAILS = (
    Fail(
        "tests/test_models.py::test_total_rounds",
        "tests/test_models.py",
        "assert order.total() == 4",
        "1 + 2 should round to 4",
    ),
    Fail(
        "tests/test_orders.py::test_checkout_total_is_wrong",
        "tests/test_orders.py",
        "assert checkout([100, 100]) == 300",
        "300",
    ),
    Fail(
        "tests/test_orders.py::test_checkout_empty",
        "tests/test_orders.py",
        "assert checkout([]) == 0",
        "empty order",
    ),
)
JS_FAILS = (
    Fail("adds wrongly", "math.test.js", "expect(add(2, 2)).toBe(5);", None),
    Fail("parses into the wrong shape", "math.test.js", "unit: 'cm' });", "cm"),
    Fail("rejects text", "math.test.js", "parse('abc');", "not a number: abc"),
)
GO_FAILS = (
    Fail("TestAddWrongly", "calc_test.go", 't.Errorf("Add(2, 2)', "want 5"),
    Fail("TestParseText", "calc_test.go", "t.Fatalf(", 'Parse("abc")'),
    Fail("TestTable/2+2", "calc_test.go", 't.Errorf("Add(%d', "want 5"),
)
CARGO_FAILS = (
    Fail("tests::adds_wrongly", "src/lib.rs", "assert_eq!(add(2, 2), 5);", None),
    Fail("tests::gives_up", "src/lib.rs", 'panic!("not implemented yet");', "not implemented yet"),
    Fail("tests::parses_text", "src/lib.rs", 'assert!(parse("abc").is_some()', "abc should parse"),
)


@dataclass(frozen=True)
class Expect:
    project: str
    format: str
    failed: int
    passed: int | None
    fails: tuple[Fail, ...]
    passing_needle: str  # a passing test's name: never in the report (P2: only the failures)
    exact_names: bool = True


# The generator's counts (make-project.sh header): pytest 412/3; jest and vitest 12/3; go 12/3 with a
# failing subtest (passes reported only with -v: 12 - 3 = 9); cargo 12 unit (3 failing) and 2 integration:
# a plain run stops after the failing lib binary (9 passed), --no-fail-fast adds 2 integration + 0 doc.
EXPECT: dict[str, Expect] = {
    "pytest-default": Expect("pytest", "pytest", 3, 412 - 3, PYTEST_FAILS, "[100%]"),
    "pytest-q": Expect("pytest", "pytest", 3, 412 - 3, PYTEST_FAILS, "[100%]"),
    "pytest-tb-short": Expect("pytest", "pytest", 3, 412 - 3, PYTEST_FAILS, "[100%]"),
    "pytest-pass-one": Expect("pytest", "pytest", 0, 400, (), "[100%]"),
    "jest": Expect("jest", "jest", 3, 12 - 3, JS_FAILS, "adds one and one", exact_names=False),
    "vitest": Expect("vitest", "vitest", 3, 12 - 3, JS_FAILS, "adds one and one", exact_names=False),
    "go-test": Expect("go", "go", 3, None, GO_FAILS, "TestAddOne"),
    "go-test-v": Expect("go", "go", 3, 12 - 3, GO_FAILS, "TestAddOne"),
    "cargo-test": Expect("cargo", "cargo", 3, 12 - 3, CARGO_FAILS, "adds_one_and_one"),
    "cargo-test-no-fail-fast": Expect("cargo", "cargo", 3, 12 - 3 + 2, CARGO_FAILS, "adds_one_and_one"),
}
LINT_RECORDINGS = ("ruff", "mypy", "tsc", "eslint")


def test_every_recording_is_covered() -> None:
    names = {p.stem for p in REC.glob("*.out")}
    assert names == set(EXPECT) | set(LINT_RECORDINGS), names


def recorded_exit(name: str) -> int:
    for line in (REC / f"{name}.source").read_text().splitlines():
        if line.startswith("exit: "):
            return int(line.split(": ", 1)[1])
    raise AssertionError(f"{name}.source names no exit")


def replay(name: str) -> list[str]:
    """A command whose output is the recording and whose exit is the recorded one."""
    return ["sh", "-c", 'cat "$1"; exit "$2"', "sh", str(REC / f"{name}.out"), str(recorded_exit(name))]


# ── the lab: tools copied with a host shebang, a home, a workspace and a scratch root ───────────


def install(dest: Path, names: tuple[str, ...] = ("verify", "run", "symbols", "search")) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    for name in names:
        lines = (TOOLS_DIR / name).read_text().splitlines(keepends=True)
        assert lines[0].startswith("#!"), name
        (dest / name).write_text(f"#!{sys.executable}\n" + "".join(lines[1:]))
        (dest / name).chmod(0o755)
    return dest


@dataclass
class Lab:
    tmp: Path
    home: Path
    ws: Path
    scratch: Path
    bin: Path
    extra: dict[str, str] = field(default_factory=dict)

    def env(self, **extra: str) -> dict[str, str]:
        e = base_env(self.scratch, SESSION, HOME=str(self.home), COLUMNS="1000", GIT_CONFIG_NOSYSTEM="1")
        e.update(self.extra)
        e.update(extra)
        return e


def make_lab(tmp_path: Path) -> Lab:
    tmp = Path(os.path.realpath(tmp_path))
    lab = Lab(tmp, tmp / "home", tmp / "ws", tmp / "scratch", install(tmp / "tools"))
    lab.home.mkdir()
    lab.ws.mkdir()
    return lab


@pytest.fixture
def lab(tmp_path: Path) -> Lab:
    return make_lab(tmp_path)


def verify(lab: Lab, *args: str, cwd: Path | None = None, timeout: float = 60, **env: str) -> Proc:
    """conftest.run's conventions (stdin /dev/null, no controlling terminal, a timeout), plus a cwd."""
    return subprocess.run(
        [sys.executable, str(lab.bin / "verify"), *args],
        cwd=str(cwd or lab.ws),
        env=lab.env(**env),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=timeout,
        start_new_session=True,
    )


def said(r: Proc) -> str:
    return f"exit {r.returncode}\n{r.stdout}\n{r.stderr}"


def doc_of(r: Proc) -> dict[str, Any]:
    try:
        d: dict[str, Any] = json.loads(r.stdout)
    except ValueError:
        raise AssertionError(f"stdout is not one JSON object:\n{said(r)}") from None
    assert list(d)[:3] == ["tool", "target", "scope"], d
    assert d["tool"] == "verify"
    assert d["exit"] == r.returncode, said(r)
    return d


def text_of(r: Proc) -> list[str]:
    out = r.stdout.splitlines()
    assert out[0].startswith("verify: ") and out[1].startswith("verdict: "), said(r)
    return out


def fail_key(f: dict[str, Any]) -> tuple[str, str | None, int | None]:
    file = f["file"].removeprefix("./") if isinstance(f["file"], str) else None
    return f["test"], file, f["line"]


def check_failures(got: list[dict[str, Any]], exp: Expect, proj: Path, withheld: bool = False) -> None:
    assert len(got) == len(exp.fails), got
    for f in got:
        assert set(f) >= {"test", "file", "line", "lines"}, f
        assert len(f["lines"]) <= 5, f
        if withheld:
            assert f["lines"] == [], f
    wanted = {(x.test, x.file, line_of((proj / x.file).read_text(), x.needle)) for x in exp.fails}
    if exp.exact_names:
        assert {fail_key(f) for f in got} == wanted, (got, wanted)
    else:
        for x in exp.fails:
            line = line_of((proj / x.file).read_text(), x.needle)
            hits = [f for f in got if x.test in f["test"]]
            assert len(hits) == 1, (x, got)
            assert fail_key(hits[0])[1:] == (x.file, line), (x, hits[0])
    if not withheld:
        for x in exp.fails:
            if x.message is None:
                continue
            hit = next(f for f in got if x.test in f["test"])
            assert any(x.message in line for line in hit["lines"]), (x, hit)


# ── verify test: every recording, through run (SC-1, SC-2) ──────────────────────────────────────


@pytest.mark.parametrize("name", sorted(EXPECT))
def test_recording_json(lab: Lab, projects: dict[str, Path], name: str) -> None:
    exp = EXPECT[name]
    code = recorded_exit(name)
    r = verify(lab, "--json", "test", "--", *replay(name))
    assert r.returncode == code, said(r)  # the pass-through gate: the command's own exit
    d = doc_of(r)
    assert d["scope"] == exp.format, d["scope"]
    assert d["format"] == exp.format
    assert d["counts"]["failed"] in ((exp.failed,) if exp.failed else (0, None)), d["counts"]
    assert d["counts"]["passed"] == exp.passed, d["counts"]
    assert d["counts"]["skipped"] in (0, None), d["counts"]
    check_failures(d["failures"], exp, projects[exp.project])
    run = d["run"]
    assert set(run) >= {"exit", "command_exit", "cause", "seconds", "log", "verdict"}, run
    assert run["exit"] == run["command_exit"] == code and run["cause"] == "command", run
    assert Path(run["log"]).is_file()
    assert d["withheld"] is False


@pytest.mark.parametrize("name", sorted(EXPECT))
def test_recording_text(lab: Lab, name: str) -> None:
    exp = EXPECT[name]
    r = verify(lab, "--text", "--limit", "0", "test", "--", *replay(name))
    out = text_of(r)
    assert out[0].endswith(f"[{exp.format}]"), out[0]
    verdict = out[1]
    if exp.failed:
        assert f"{exp.failed} failed" in verdict, verdict
    if exp.passed is None:
        assert "passes not reported (go test without -v)" in verdict, verdict
        assert "0 passed" not in verdict, verdict
    else:
        assert f"{exp.passed} passed ({exp.format})" in verdict, verdict
    assert f"exit {recorded_exit(name)}" in verdict, verdict
    heads = [m for m in map(BLOCK_HEAD.match, out[2:]) if m]
    assert len(heads) == len(exp.fails), out
    assert not any(exp.passing_needle in line for line in out[2:]), out  # not one passing line


def test_sc1_text_verdict_and_block(lab: Lab, projects: dict[str, Path]) -> None:
    out = text_of(verify(lab, "--text", "test", "--", *replay("pytest-default")))
    # "then run's exit, duration and log path" (spec SC-1): run's own words may follow `exit 1`
    assert out[1].startswith("verdict: 3 failed, 409 passed (pytest) · exit 1"), out[1]
    assert re.search(r" · \d+\.\d s · (.* · )?log /\S+\.log", out[1]), out[1]
    line = line_of((projects["pytest"] / "tests/test_models.py").read_text(), "assert order.total() == 4")
    head = f"tests/test_models.py:{line}  tests/test_models.py::test_total_rounds"
    assert head in out, out
    below = out[out.index(head) + 1 :]
    assert below and below[0].startswith("    "), out
    assert any("1 + 2 should round to 4" in x for x in below[:5]), out


@pytest.mark.parametrize("name", LINT_RECORDINGS)
def test_linter_recordings_are_format_unknown(lab: Lab, name: str) -> None:
    r = verify(lab, "--json", "test", "--", *replay(name))
    assert r.returncode == recorded_exit(name), said(r)
    d = doc_of(r)
    assert d["scope"] == "format unknown"
    assert d["format"] == "unknown"
    assert all(v is None for v in d["counts"].values()), d["counts"]
    assert d["failures"] == []
    assert SUMMARY_UNKNOWN in d["verdict"], d["verdict"]


def test_real_pytest_on_the_generated_project(lab: Lab, projects: dict[str, Path]) -> None:
    """SC-1 as the criterion says it: running a suite, not replaying one (the host's pytest)."""
    r = verify(
        lab,
        "--json",
        "test",
        "--",
        sys.executable,
        "-m",
        "pytest",
        "-p",
        "no:cacheprovider",
        cwd=projects["pytest"],
    )
    assert r.returncode == 1, said(r)
    d = doc_of(r)
    assert d["format"] == "pytest"
    assert (d["counts"]["failed"], d["counts"]["passed"]) == (3, 409), d["counts"]
    check_failures(d["failures"], EXPECT["pytest-default"], projects["pytest"])


# ── identification: order, never by command name; the unknown fallback ─────────────────────────


@pytest.mark.parametrize(
    ("first", "second", "fmt", "passed"),
    [
        ("jest", "pytest-pass-one", "pytest", 400),  # pytest is identified before jest
        ("cargo-test", "go-test-v", "go", 9),  # go before cargo
        ("cargo-test", "vitest", "vitest", 9),  # vitest before cargo
    ],
)
def test_identification_order(lab: Lab, first: str, second: str, fmt: str, passed: int) -> None:
    r = verify(lab, "--json", "test", "--", "cat", str(REC / f"{first}.out"), str(REC / f"{second}.out"))
    assert r.returncode == 0, said(r)
    d = doc_of(r)
    assert d["format"] == fmt, d["format"]
    assert d["counts"]["passed"] == passed, d["counts"]


def test_identified_by_summary_not_by_command_name(lab: Lab) -> None:
    fake = lab.tmp / "names" / "jest"
    fake.parent.mkdir()
    fake.write_text(f"#!/bin/sh\ncat '{REC / 'pytest-q.out'}'\nexit 1\n")
    fake.chmod(0o755)
    d = doc_of(verify(lab, "--json", "test", "--", str(fake)))
    assert d["format"] == "pytest" and d["exit"] == 1, d


def test_unknown_format_passes_exit_through(lab: Lab) -> None:
    r = verify(lab, "--json", "test", "--", "sh", "-c", "echo x; exit 7")
    assert r.returncode == 7, said(r)
    d = doc_of(r)
    assert d["scope"] == "format unknown" and d["format"] == "unknown"
    assert all(v is None for v in d["counts"].values()), d["counts"]  # never zero
    # Amended at implement: the clause first (rule 13's cut never takes it), then run's verdict as verify
    # words every format's (its line count dropped): the exit and run's log are in it.
    assert d["verdict"].startswith(f"{SUMMARY_UNKNOWN} · exit 7"), d["verdict"]
    assert f"log {d['run']['log']}" in d["verdict"], d["verdict"]
    assert d["run"]["command_exit"] == 7
    t = verify(lab, "--text", "test", "--", "sh", "-c", "echo x; exit 7")
    assert t.returncode == 7 and "x" in text_of(t)[2:], said(t)  # the body is run's bounded lines


def test_unknown_format_exit_0(lab: Lab) -> None:
    r = verify(lab, "--json", "test", "--", "printf", "all good\\nnothing to see\\n")
    assert r.returncode == 0, said(r)
    assert doc_of(r)["format"] == "unknown"


def test_bare_command_is_test_mode(lab: Lab) -> None:
    """Amendment 1: any first word other than test/changed is the command."""
    r = verify(lab, "--json", "sh", "-c", "echo x; exit 7")
    assert r.returncode == 7, said(r)
    assert doc_of(r)["format"] == "unknown"
    d = doc_of(verify(lab, "--json", *replay("pytest-q")))
    assert d["format"] == "pytest" and d["counts"]["passed"] == 409


def test_a_command_named_test(lab: Lab) -> None:
    r = verify(lab, "--json", "test", "--", "test", "1", "=", "2")
    assert r.returncode == 1, said(r)
    assert doc_of(r)["run"]["command_exit"] == 1


@pytest.mark.parametrize(
    "args",
    [[], ["test"], ["test", "--"], ["test", "-f", "x"], ["changed", "--bogus"]],
    ids=["none", "test-alone", "test-empty", "test-no-dashdash", "changed-bogus"],
)
def test_usage_errors_are_exit_2(lab: Lab, args: list[str]) -> None:
    subprocess.run(["git", "init", "-q", str(lab.ws)], check=True, env=lab.env())
    r = verify(lab, "--json", *args)
    assert r.returncode == 2, said(r)
    assert r.stdout == "", said(r)


# ── --limit, timeout, redaction unavailable, events ─────────────────────────────────────────────


def test_limit_bounds_failure_blocks(lab: Lab) -> None:
    out = text_of(verify(lab, "--text", "--limit", "1", "test", "--", *replay("pytest-default")))
    log = re.search(r" · log (\S+)", out[1])
    assert log, out[1]
    assert len([x for x in out[2:] if BLOCK_HEAD.match(x)]) == 1, out
    omitted = [x for x in out if x.startswith("… omitted")]
    assert len(omitted) == 1, out
    assert log[1] in omitted[0], omitted


def test_timeout_is_124_with_failures_so_far(lab: Lab, projects: dict[str, Path]) -> None:
    # The first seven lines of the go recording hold all three failures; then the command hangs.
    cmd = f"head -n 7 '{REC / 'go-test.out'}'; exec sleep 30"
    r = verify(lab, "--json", "test", "--timeout", "1", "--", "sh", "-c", cmd)
    assert r.returncode == 124, said(r)
    d = doc_of(r)
    assert d["format"] == "go"
    check_failures(d["failures"], EXPECT["go-test"], projects["go"])
    assert "timeout" in d["verdict"], d["verdict"]
    assert "3 failed so far" in d["verdict"], d["verdict"]  # contract § test, timeout row


def test_redaction_unavailable_withholds_assertion_lines(lab: Lab, projects: dict[str, Path]) -> None:
    missing = lab.tmp / "no-such-rules.toml"
    r = verify(lab, "--json", "test", "--", *replay("pytest-default"), TIMELIKE_REDACTION_RULES=str(missing))
    assert r.returncode == 1, said(r)
    d = doc_of(r)
    assert d["withheld"] is True
    assert (d["counts"]["failed"], d["counts"]["passed"]) == (3, 409), d["counts"]
    check_failures(d["failures"], EXPECT["pytest-default"], projects["pytest"], withheld=True)
    assert "output withheld" in d["verdict"], d["verdict"]
    assert "should round to 4" not in r.stdout  # the program's data, not the runner's structure


def test_one_event_per_call_referring_to_runs_log(lab: Lab) -> None:
    logs = []
    for name in ("pytest-q", "jest"):
        d = doc_of(verify(lab, "--json", "test", "--", *replay(name)))
        logs.append(d["run"]["log"])
        mine = [e for e in events(lab.scratch, SESSION) if e["tool"] == "verify"]
        assert len(mine) == len(logs)
        assert list(mine[-1].get("ref", {}).values()) == [logs[-1]], mine[-1]


# ── run's failures: verify copied beside a stub run ─────────────────────────────────────────────


def stub_lab(tmp_path: Path, run_body: str | None) -> Lab:
    lab = make_lab(tmp_path)
    shutil.rmtree(lab.bin)
    lab.bin = install(lab.tmp / "stubbed", ("verify",))
    if run_body is not None:
        (lab.bin / "run").write_text(f"#!{sys.executable}\nimport sys\n{run_body}\n")
        (lab.bin / "run").chmod(0o755)
    return lab


@pytest.mark.parametrize(
    "body",
    [None, "print('run: boom', file=sys.stderr); sys.exit(1)", "print('not json at all'); sys.exit(0)"],
    ids=["missing", "fails", "unreadable"],
)
def test_run_failures_are_exit_1_internal(tmp_path: Path, body: str | None) -> None:
    lab = stub_lab(tmp_path, body)
    r = verify(lab, "--json", "test", "--", "true")
    assert r.returncode == 1, said(r)
    d = doc_of(r)  # contract § test: `run` failed → exit 1, scope `internal`, a verdict naming the path
    assert d["scope"] == "internal", d
    assert str(lab.bin / "run") in d["verdict"], d["verdict"]


# ── verify changed: git repositories the tests build ────────────────────────────────────────────


GITIGNORE = ".venv/\n__pycache__/\n.mypy_cache/\n.ruff_cache/\n.pytest_cache/\n*.log\n"


def git(lab: Lab, *args: str) -> str:
    who = {
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.invalid",
    }
    r = subprocess.run(
        ["git", *args], cwd=lab.ws, env=lab.env(**who), capture_output=True, text=True, timeout=30
    )
    assert r.returncode == 0, (args, r.stderr)
    return r.stdout


@pytest.fixture
def repo(lab: Lab) -> Lab:
    """The generator's pytest project, committed: app/{models,orders,cli}.py and their tests."""
    subprocess.run(["bash", str(GEN), "pytest", str(lab.ws)], check=True, timeout=60)
    (lab.ws / ".gitignore").write_text(GITIGNORE)
    git(lab, "init", "-q", "-b", "main")
    git(lab, "add", "-A")
    git(lab, "commit", "-q", "-m", "initial")
    return lab


def dry(lab: Lab, *args: str, **env: str) -> dict[str, Any]:
    r = verify(lab, "--json", "changed", "--dry-run", *args, **env)
    assert r.returncode == 0, said(r)
    d = doc_of(r)
    assert d["scope"] == "dry run", d["scope"]
    return d


def selected_tests(d: dict[str, Any]) -> dict[str, str]:
    return {t["path"]: t["reason"] for t in d["selected"]["tests"]}


def append(lab: Lab, rel: str, text: str) -> None:
    with (lab.ws / rel).open("a") as f:
        f.write(text)


def test_clean_tree_selects_nothing_exit_0(repo: Lab) -> None:
    (repo.ws / "ignored.log").write_text("ignored files are not changes\n")
    r = verify(repo, "--json", "changed")
    assert r.returncode == 0, said(r)
    d = doc_of(r)
    assert d["scope"] == "nothing selected"
    assert d["verdict"] == "no changes against HEAD: nothing selected, nothing run"
    assert d["changed"] == [] and d["steps"] == []


def test_not_a_repository_is_usage_exit_2(lab: Lab) -> None:
    r = verify(lab, "--json", "changed")
    assert r.returncode == 2, said(r)
    assert r.stdout == ""
    assert "verify test" in r.stderr and "git" in r.stderr, r.stderr


def test_sc3_dry_run_selection_and_reasons(repo: Lab) -> None:
    append(repo, "app/models.py", "\n\nVERSION = 2\n")
    d = dry(repo)
    assert d["against"] == "HEAD"
    assert d["changed"] == [{"path": "app/models.py", "status": "modified"}]
    assert selected_tests(d) == {
        "tests/test_models.py": "imports app/models.py",
        "tests/test_orders.py": "imports app/orders.py, which imports app/models.py",
    }
    assert d["selected"]["lint"] == ["app/models.py"]
    assert d["selected"]["typecheck"] == ["app/models.py"]
    assert "superset" in d["verdict"], d["verdict"]
    # --dry-run runs nothing: no run event, and run's log directory never written
    assert not [e for e in events(repo.scratch, SESSION) if e["tool"] == "run"]
    t = verify(repo, "--text", "changed", "--dry-run")
    assert t.returncode == 0, said(t)
    out = text_of(t)
    assert out[0].startswith("verify: changed against HEAD"), out[0]
    assert any(re.match(r"^test\s+tests/test_models\.py\s+imports app/models\.py$", x) for x in out), out
    assert any(
        re.match(r"^test\s+tests/test_orders\.py\s+imports app/orders\.py, which imports app/models\.py$", x)
        for x in out
    ), out


def test_dry_run_starts_no_runner(repo: Lab) -> None:
    marker = repo.tmp / "ran"
    stubs = repo.tmp / "stubs"
    stubs.mkdir()
    for name in ("pytest", "ruff", "mypy"):
        (stubs / name).write_text(f"#!/bin/sh\necho {name} >> '{marker}'\n")
        (stubs / name).chmod(0o755)
    append(repo, "app/models.py", "\nX = 1\n")
    dry(repo, PATH=f"{stubs}:/usr/bin:/bin")
    assert not marker.exists()


def test_change_kinds(repo: Lab) -> None:
    (repo.ws / "app/new.py").write_text("NEW = 1\n")
    git(repo, "add", "app/new.py")
    (repo.ws / "app/untracked.py").write_text("U = 1\n")
    git(repo, "mv", "app/orders.py", "app/ordering.py")
    git(repo, "rm", "-q", "app/cli.py")
    append(repo, "app/models.py", "\nY = 1\n")
    d = dry(repo)
    assert sorted((c["path"], c["status"]) for c in d["changed"]) == [
        ("app/cli.py", "deleted"),
        ("app/models.py", "modified"),
        ("app/new.py", "added"),
        ("app/ordering.py", "renamed"),
        ("app/untracked.py", "untracked"),
    ]
    assert "app/cli.py" not in d["selected"]["lint"]  # deleted: not linted
    assert "app/cli.py" not in d["selected"]["typecheck"]
    assert {"app/new.py", "app/untracked.py", "app/ordering.py", "app/models.py"} <= set(
        d["selected"]["lint"]
    )
    assert selected_tests(d).get("tests/test_cli.py") == "imports app/cli.py", selected_tests(
        d
    )  # deleted: still used


def test_changed_test_file_and_untested_file(repo: Lab) -> None:
    append(repo, "tests/test_cli.py", "\n\ndef test_extra():\n    assert double(0) == 0\n")
    (repo.ws / "app/lonely.py").write_text("def alone() -> int:\n    return 1\n")
    d = dry(repo)
    assert selected_tests(d) == {"tests/test_cli.py": "changed"}
    assert [u["path"] for u in d["selected"]["untested"]] == ["app/lonely.py"]  # amended: {path, reason}
    out = text_of(verify(repo, "--text", "changed", "--dry-run"))
    assert any(re.match(r"^none\s+app/lonely\.py\s+no test imports it$", x) for x in out), out


def test_since_ref(repo: Lab) -> None:
    append(repo, "app/cli.py", "\n\ndef triple(n: int) -> int:\n    return n * 3\n")
    git(repo, "commit", "-q", "-am", "second")
    assert verify(repo, "--json", "changed").returncode == 0  # clean against HEAD
    (repo.ws / "app/extra.py").write_text("E = 1\n")
    d = dry(repo, "--since", "HEAD~1")
    assert {c["path"] for c in d["changed"]} == {"app/cli.py", "app/extra.py"}  # untracked still count
    assert selected_tests(d) == {"tests/test_cli.py": "imports app/cli.py"}
    r = verify(repo, "--json", "changed", "--since", "no-such-ref")
    assert r.returncode == 2, said(r)
    assert "no-such-ref" in r.stderr, r.stderr


def tool_path(tmp: Path) -> Path | None:
    """pytest, ruff and mypy found on the host (beside this interpreter, then PATH), or None."""
    here = str(Path(sys.executable).parent)
    found = {n: shutil.which(n, path=here) or shutil.which(n) for n in ("pytest", "ruff", "mypy")}
    if not all(found.values()):
        return None
    d = tmp / "toolpath"
    d.mkdir()
    for name, path in found.items():
        assert path is not None
        (d / name).symlink_to(path)
    return d


def find(obj: Any, **want: Any) -> bool:
    if isinstance(obj, dict):
        if all(obj.get(k) == v for k, v in want.items()):
            return True
        return any(find(v, **want) for v in obj.values())
    if isinstance(obj, list):
        return any(find(v, **want) for v in obj)
    return False


def test_sc3_real_steps(repo: Lab) -> None:
    tools = tool_path(repo.tmp)
    if tools is None:
        pytest.skip("pytest, ruff or mypy not found beside this interpreter or on PATH")
    src = (repo.ws / "app/models.py").read_text()
    (repo.ws / "app/models.py").write_text("import os\n" + src)  # ruff F401 at line 1; mypy still passes
    r = verify(repo, "--json", "changed", PATH=f"{tools}:/usr/bin:/bin", timeout=180)
    assert r.returncode == 1, said(r)
    d = doc_of(r)
    steps = {s["tool"]: s for s in d["steps"]}
    assert [s["kind"] for s in d["steps"]] == ["test", "lint", "type"], d["steps"]
    assert set(steps) == {"pytest", "ruff", "mypy"}, steps
    py = steps["pytest"]
    assert py["exit"] == 1
    # generator: test_models.py 6 tests, 1 failing; test_orders.py 6, 2 failing
    assert (py["report"]["counts"]["failed"], py["report"]["counts"]["passed"]) == (3, 9), py["report"]
    check_failures(py["report"]["failures"], EXPECT["pytest-default"], repo.ws)
    assert "test_cli" not in str(py["command"])
    assert find(steps["ruff"], file="app/models.py", line=1), steps["ruff"]
    assert steps["ruff"]["exit"] == 1
    assert steps["mypy"]["state"] == "passed" and steps["mypy"]["exit"] == 0, steps["mypy"]
    mine = [e for e in events(repo.scratch, SESSION) if e["tool"] == "verify"]
    assert len(mine) == 1 and list(mine[0].get("ref", {}).values()) == [py["log"]], mine


def test_venv_runner_is_found_first_and_given_the_selected_files(repo: Lab) -> None:
    marker = repo.tmp / "argv"
    venv = repo.ws / ".venv" / "bin"
    venv.mkdir(parents=True)
    (venv / "pytest").write_text(
        f"#!/bin/sh\nprintf '%s\\n' \"$@\" > '{marker}'\ncat '{REC / 'pytest-pass-one.out'}'\n"
    )
    (venv / "pytest").chmod(0o755)
    append(repo, "app/models.py", "\nZ = 1\n")
    r = verify(repo, "--json", "changed", PATH="/usr/bin:/bin")
    d = doc_of(r)
    assert marker.exists(), said(r)
    assert set(marker.read_text().split()) == {"tests/test_models.py", "tests/test_orders.py"}
    assert {s["tool"]: s for s in d["steps"]}["pytest"]["state"] == "passed", d["steps"]


def test_not_found_steps_are_not_run_exit_1(repo: Lab) -> None:
    bare = "/usr/bin:/bin"
    if any(shutil.which(n, path=bare) for n in ("pytest", "ruff", "mypy")):
        pytest.skip("pytest, ruff or mypy is on /usr/bin:/bin here")
    # No python3 on the bare PATH (the image: its Python is under /opt) means verify's `python3 -m
    # pytest` fallback is unavailable too, so the precondition holds and the test runs (lane batch-b).
    py = shutil.which("python3", path=bare)
    if py:
        probe = subprocess.run([py, "-c", "import pytest"], env={"PATH": bare}, capture_output=True)
        if probe.returncode == 0:
            pytest.skip("python3 on /usr/bin:/bin can import pytest here")
    append(repo, "app/models.py", "\nW = 1\n")
    r = verify(repo, "--json", "changed", PATH=bare)
    assert r.returncode == 1, said(r)
    d = doc_of(r)
    states = {s["tool"]: s["state"] for s in d["steps"]}
    for name in ("pytest", "ruff", "mypy"):
        assert states[name].startswith(f"not run: {name} not found"), states
    assert "not run" in d["verdict"], d["verdict"]


def lint_repo(lab: Lab, projects: dict[str, Path]) -> Path:
    """The generator's lint project, committed, then its four files touched; stub linters replay the
    recordings (real output) with the project's path put back for <PROJECT>."""
    shutil.copytree(projects["lint"], lab.ws, dirs_exist_ok=True)
    (lab.ws / ".gitignore").write_text(GITIGNORE)
    git(lab, "init", "-q", "-b", "main")
    git(lab, "add", "-A")
    git(lab, "commit", "-q", "-m", "initial")
    for rel in ("bad.py", "bad.ts", "bad.js"):
        append(lab, rel, "\n")
    stubs = lab.tmp / "linters"
    stubs.mkdir()
    for name in LINT_RECORDINGS:
        rec = REC / f"{name}.out"
        (stubs / name).write_text(f"#!/bin/sh\nsed 's|<PROJECT>|{lab.ws}|g' '{rec}'\nexit 1\n")
        (stubs / name).chmod(0o755)
    return stubs


def test_linter_diagnostics_from_recordings(lab: Lab, projects: dict[str, Path]) -> None:
    stubs = lint_repo(lab, projects)
    r = verify(lab, "--json", "changed", PATH=f"{stubs}:/usr/bin:/bin")
    assert r.returncode == 1, said(r)
    d = doc_of(r)
    steps = {s["tool"]: s for s in d["steps"]}
    py, ts, js = (projects["lint"] / n for n in ("bad.py", "bad.ts", "bad.js"))
    assert find(steps["ruff"], file="bad.py", line=line_of(py.read_text(), "import os")), steps["ruff"]
    assert find(steps["mypy"], file="bad.py", line=line_of(py.read_text(), 'return ",".join')), steps["mypy"]
    assert find(steps["tsc"], file="bad.ts", line=line_of(ts.read_text(), 'items.join(",")')), steps["tsc"]
    assert find(steps["eslint"], file="bad.js", line=line_of(js.read_text(), "const unused")), steps["eslint"]


# ── the manifest and help (FR-13, amendment 3) ──────────────────────────────────────────────────


def test_manifest(lab: Lab) -> None:
    r = verify(lab, "--agent-info")
    assert r.returncode == 0, said(r)
    info = json.loads(r.stdout)
    assert schema.errors(info, schema.load("agent-info.schema.json")) == []
    assert info["tool"] == "verify"
    assert info["mutating"] is False
    assert info["reads_stdin"] is False
    assert info["passes_exit"] is True
    assert "takes_command" not in info
    assert info["dry_run"] is False
    assert info["probe"] == ["true"]
    assert set(info["exit_codes"]) == {"0", "1", "2", "124"}
    assert info["formats"] == ["pytest", "jest", "vitest", "go", "cargo"]
    assert info["assertion_lines"] == 5
    assert info["batch_dependents_over"] == 50


def test_probe_runs(lab: Lab) -> None:
    r = verify(lab, "--json", "true")
    assert r.returncode == 0, said(r)
    assert doc_of(r)["scope"] == "format unknown"


def test_help_is_within_40_lines(lab: Lab) -> None:
    r = verify(lab, "--help")
    assert r.returncode == 0, said(r)
    lines = r.stdout.splitlines()
    assert 0 < len(lines) <= 40 and lines[0].startswith("verify: ")


# ── T005 (host lane): the paths T001 did not reach, found by the traced run's missing lines ────────
# Runners that are not on this host are stubs that print their REAL recorded output (as lint_repo's
# linters do), so the parser still reads what the runner wrote; what is tested here is the selection,
# the command each step runs, and the step's state.


def runner_repo(lab: Lab, projects: dict[str, Path], kind: str) -> None:
    shutil.copytree(projects[kind], lab.ws, dirs_exist_ok=True)
    (lab.ws / ".gitignore").write_text(GITIGNORE + "node_modules/\ntarget/\n")
    git(lab, "init", "-q", "-b", "main")
    git(lab, "add", "-A")
    git(lab, "commit", "-q", "-m", "initial")


def replaying(where: Path, name: str, recording: str, code: int, log: Path | None = None) -> None:
    where.mkdir(parents=True, exist_ok=True)
    note = f"printf '%s\\n' \"$*\" >> '{log}'\n" if log else ""
    (where / name).write_text(f"#!/bin/sh\n{note}cat '{REC / recording}.out'\nexit {code}\n")
    (where / name).chmod(0o755)


@pytest.mark.parametrize("runner", ["vitest", "jest"])
def test_js_change_runs_the_importing_test_with_the_workspace_runner(
    lab: Lab, projects: dict[str, Path], runner: str
) -> None:
    runner_repo(lab, projects, runner)
    calls = lab.tmp / "calls.log"
    replaying(lab.ws / "node_modules" / ".bin", runner, runner, 1, calls)
    append(lab, "math.js", "\n")
    r = verify(lab, "--json", "changed", PATH="/usr/bin:/bin")
    assert r.returncode == 1, said(r)
    d = doc_of(r)
    assert selected_tests(d) == {"math.test.js": "imports math.js"}, d["selected"]
    step = next(s for s in d["steps"] if s["kind"] == "test")
    assert step["tool"] == runner and step["files"] == ["math.test.js"], step
    want = "run math.test.js" if runner == "vitest" else "math.test.js"
    assert calls.read_text().strip() == want, calls.read_text()
    assert step["report"]["counts"]["failed"] == 3 and step["report"]["counts"]["passed"] == 9, step
    assert f"{runner}: 3 failed, 9 passed" in d["verdict"], d["verdict"]


def test_go_change_runs_go_test_on_its_package(lab: Lab, projects: dict[str, Path]) -> None:
    runner_repo(lab, projects, "go")
    stubs, calls = lab.tmp / "stubs", lab.tmp / "calls.log"
    replaying(stubs, "go", "go-test", 1, calls)
    append(lab, "calc.go", "\n")
    r = verify(lab, "--json", "changed", PATH=f"{stubs}:/usr/bin:/bin")
    assert r.returncode == 1, said(r)
    d = doc_of(r)
    step = next(s for s in d["steps"] if s["tool"] == "go")
    assert calls.read_text().strip() == "test .", calls.read_text()
    assert step["report"]["counts"]["passed"] is None, step  # go test without -v reports no passes
    assert "passes not reported" in step["state"], step


def test_rust_change_runs_cargo_test_in_the_crate(lab: Lab, projects: dict[str, Path]) -> None:
    runner_repo(lab, projects, "cargo")
    stubs, calls = lab.tmp / "stubs", lab.tmp / "calls.log"
    replaying(stubs, "cargo", "cargo-test", 101, calls)
    append(lab, "src/lib.rs", "\n")
    r = verify(lab, "--json", "changed", PATH=f"{stubs}:/usr/bin:/bin")
    assert r.returncode == 1, said(r)
    step = next(s for s in doc_of(r)["steps"] if s["tool"] == "cargo")
    assert calls.read_text().strip() == "test", calls.read_text()
    assert (step["report"]["counts"]["failed"], step["report"]["counts"]["passed"]) == (3, 9), step


def test_missing_js_runner_is_not_run(lab: Lab, projects: dict[str, Path]) -> None:
    runner_repo(lab, projects, "jest")
    append(lab, "math.js", "\n")
    r = verify(lab, "--json", "changed", PATH="/usr/bin:/bin")
    assert r.returncode == 1, said(r)
    step = next(s for s in doc_of(r)["steps"] if s["kind"] == "test")
    assert step["state"].startswith("not run: vitest or jest not found"), step


def test_changed_conftest_selects_the_tests_under_it(repo: Lab) -> None:
    (repo.ws / "tests" / "conftest.py").write_text("")
    d = dry(repo)
    assert selected_tests(d) == {"tests": "conftest.py for the tests under tests"}, d["selected"]


def test_a_step_past_its_limit_is_124_timed_out(repo: Lab) -> None:
    stubs = repo.tmp / "stubs"
    stubs.mkdir()
    for name in ("pytest", "ruff", "mypy"):
        (stubs / name).write_text("#!/bin/sh\nexec sleep 30\n")
        (stubs / name).chmod(0o755)
    append(repo, "app/models.py", "\n")
    r = verify(repo, "--json", "changed", "--timeout", "1", PATH=f"{stubs}:/usr/bin:/bin", timeout=120)
    assert r.returncode == 124, said(r)
    states = [s["state"] for s in doc_of(r)["steps"]]
    assert states and all(s.startswith("timed out: ") for s in states), states


@pytest.mark.parametrize("value", ["0", "-1", "soon"])
def test_timeout_must_be_a_positive_number(repo: Lab, value: str) -> None:
    for args in (["changed", "--timeout", value], ["test", "--timeout", value, "--", "true"]):
        r = verify(repo, "--json", *args)
        assert r.returncode == 2 and r.stdout == "", said(r)


def test_real_pytest_skipped_and_error_counts(lab: Lab) -> None:
    """A suite the test writes: 1 passing, 1 skipped, 1 erroring in a fixture; real pytest counts it."""
    here = str(Path(sys.executable).parent)
    if not (shutil.which("pytest", path=here) or shutil.which("pytest")):
        pytest.skip("no pytest on this host")
    (lab.ws / "test_mix.py").write_text(
        "import pytest\n\n\n@pytest.fixture\ndef broken():\n    raise RuntimeError('fixture broke')\n\n\n"
        "def test_ok():\n    assert True\n\n\n"
        "@pytest.mark.skip(reason='later')\ndef test_later():\n    pass\n\n\n"
        "def test_uses_broken(broken):\n    pass\n"
    )
    r = verify(
        lab, "--json", "test", "--", sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "test_mix.py"
    )
    assert r.returncode == 1, said(r)
    d = doc_of(r)
    assert d["format"] == "pytest"
    assert (d["counts"]["passed"], d["counts"]["skipped"], d["counts"]["errors"]) == (1, 1, 1), d["counts"]
    assert any("test_uses_broken" in f["test"] for f in d["failures"]), d["failures"]
    assert "1 error" in d["verdict"] and "1 skipped" in d["verdict"], d["verdict"]


def test_one_session_event_per_call_whatever_it_runs(repo: Lab) -> None:
    """Rule 16 (conform C7): run and symbols are tools too; their events stay out of the session's journal."""
    before = len(events(repo.scratch, SESSION))
    append(repo, "app/models.py", "\n")
    verify(repo, "--json", "changed", "--dry-run")  # symbols, once per changed file
    verify(repo, "--json", "test", "--", "true")  # run
    new = events(repo.scratch, SESSION)[before:]
    assert [e["tool"] for e in new] == ["verify", "verify"], new
