"""validate_bench — the Docker lane's independent check of a bench run's artifacts (T013, T049; H3, P004).

It shares NO code with bench/benchlib: a validator that imported the trace writer's own rules would only
prove the writer agrees with itself (cross-stack P005). Its rules are re-derived from the contracts
(trace-schema.md, schema 2; bench-cli.md § Slice 1), deliberately narrower and written differently.

    python3 validate_bench.py traces OUT SHA HARNESS TASK [TASK ...]  three traces a task, stamped, recounted
    python3 validate_bench.py report OUT [fake|standin|live]          first lines, sections, token placement
    python3 validate_bench.py verdicts OUT HARNESS                    revision 8's ranking, recomputed here
    python3 validate_bench.py adoption OUT HARNESS                    timelike tool calls per arm, recounted
    python3 validate_bench.py env FILE                                no key-shaped names in `env`-style lines
    python3 validate_bench.py hang OUT TASK                           vanilla hung, and ended near its limit

HARNESS is `fake`, `opencode` or `codex`, as the trace file names have it. Runs on the bench driver image's
interpreter (the bats runner has no Python), stdlib only. Prints one line per problem and exits 1 if any, else
prints `ok: …` and exits 0.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ARMS = ("vanilla", "not-told", "told")
LABEL = {"vanilla": "vanilla", "not-told": "timelike, not told", "told": "timelike, told"}
VERSUS = {"not-told": "Not told vs vanilla: ", "told": "Told vs vanilla: "}
HARNESS_NAME = {"fake": "timelike-fake-agent", "opencode": "opencode", "codex": "codex"}
IDENTITY_KEYS = (
    "bench_revision", "environment", "arm", "image_id", "image_revision", "base_digest", "harness_name",
    "harness_version", "harness_reported_version", "model_id", "invocation", "output_streams", "task_id",
    "task_version", "call_limit_s", "run_limit_s", "reproduce",
)  # fmt: skip
ENDINGS = {"completed", "escalated", "failed", "hung", "stopped"}  # schema 2 adds stopped, with a cause
RANK = {"completed": 0, "escalated": 1, "failed": 2, "hung": 3}
# The operator's text, verbatim (send …-080659). Compared whole: a reworded first line is a failure.
FAKE_FIRST = (
    "FAKE-AGENT BENCH PIPELINE DEMO RUN -- This is not a test of timelike, rather a test of the bench test "
    "itself (its presentation and usefulness to the human user). The agent's policy was written by "
    "timelike's own builders."
)
FIRST_PREFIX = {"fake": FAKE_FIRST, "standin": "STAND-IN MODEL RUN -- ", "live": "LIVE RUN — n = 1"}
APPENDIX = "# Appendix: tokens and spend"
SECTION_ORDER = [
    "## Adoption: timelike tool calls per arm",
    "## Failure categories per arm",
    "## Timelike loses",
    "## Ties",
    "## Timelike wins",
    "## Not compared: infrastructure",
]
# A name is key-shaped if an underscore-separated word is one of these, or ends with one of the suffixes.
KEY_WORDS = {
    "KEY",
    "KEYS",
    "APIKEY",
    "ACCESSKEY",
    "PRIVATEKEY",
    "PASSPHRASE",
    "PASS",
    "CREDENTIAL",
    "CREDENTIALS",
}
KEY_SUFFIXES = ("PASSWORD", "PASSWORDS", "PASSWD", "TOKEN", "TOKENS", "SECRET", "SECRETS")
GIT_CONFIG_KEY = re.compile(r"GIT_CONFIG_KEY_[0-9]+")


def trace_file(out: Path, task: str, harness: str, arm: str) -> Path:
    return out / "traces" / f"{task}--{harness}--{arm}.json"


def load(out: Path, task: str, harness: str, arm: str) -> dict[str, Any] | None:
    p = trace_file(out, task, harness, arm)
    if not p.exists():
        return None
    doc = json.loads(p.read_text(encoding="utf-8"))
    return doc if isinstance(doc, dict) else None


def check_trace(doc: Any, sha: str, task: str, arm: str, harness: str = "fake") -> list[str]:
    where = f"{task}--{harness}--{arm}"
    if not isinstance(doc, dict):
        return [f"{where}: not a JSON object"]
    out: list[str] = []
    if doc.get("schema_version") != 2:
        out.append(f"{where}: schema_version is {doc.get('schema_version')!r}, not 2")
    ident = doc.get("identity") or {}
    for key in IDENTITY_KEYS:
        value = ident.get(key)
        if value in (None, "", 0) or (isinstance(value, str) and not value.strip()):
            out.append(f"{where}: identity.{key} is empty")
    if ident.get("bench_revision") != sha or ident.get("image_revision") != sha:
        out.append(
            f"{where}: revisions {ident.get('bench_revision')}/{ident.get('image_revision')} are not {sha}"
        )
    if (ident.get("task_id"), ident.get("arm")) != (task, arm):
        out.append(f"{where}: identity names {ident.get('task_id')}/{ident.get('arm')}")
    if ident.get("harness_name") != HARNESS_NAME.get(harness):
        out.append(f"{where}: harness_name is {ident.get('harness_name')!r}")
    if (ident.get("arm") == "vanilla") != (ident.get("environment") == "vanilla"):
        out.append(
            f"{where}: arm {ident.get('arm')!r} does not match environment {ident.get('environment')!r}"
        )
    if (ident.get("arm") == "told") != bool(str(ident.get("placement", "")).strip()):
        out.append(f"{where}: placement {ident.get('placement')!r} for arm {ident.get('arm')!r}")
    if "@sha256:" not in str(ident.get("base_digest", "")):
        out.append(f"{where}: base_digest has no @sha256:")
    calls = doc.get("calls")
    totals = doc.get("totals") or {}
    if not isinstance(calls, list):
        return [*out, f"{where}: calls is not a list"]
    for c in calls:
        failed = c.get("exit_code") != 0 or c.get("hung") is True
        if failed != bool(c.get("category")):
            out.append(f"{where}: call {c.get('seq')} has category {c.get('category')!r} (failed: {failed})")
        if ident.get("arm") == "vanilla" and (c.get("timelike_tools") or c.get("through_timelike")):
            out.append(f"{where}: call {c.get('seq')} counts timelike tools in the vanilla arm")
    recount = {
        "tool_calls": len(calls),
        "nonzero_exits": sum(1 for c in calls if c.get("exit_code") != 0),
        "hangs": sum(1 for c in calls if c.get("hung") is True),
        "turns": max((c.get("turn", 0) for c in calls), default=0),
        "timelike_tool_calls": sum(1 for c in calls if c.get("timelike_tools")),
        "through_timelike_calls": sum(1 for c in calls if c.get("through_timelike")),
    }
    for key, value in recount.items():
        if totals.get(key) != value:
            out.append(f"{where}: totals.{key} is {totals.get(key)!r}, recounted {value}")
    if not isinstance(totals.get("wall_clock_ms"), int):
        out.append(f"{where}: totals.wall_clock_ms missing")
    ending = doc.get("ending") or {}
    if ending.get("kind") not in ENDINGS or not str(ending.get("reason", "")).strip():
        out.append(f"{where}: ending {ending!r} is not a known kind with a reason")
    if (ending.get("kind") == "stopped") != bool(ending.get("cause")):
        out.append(f"{where}: ending {ending!r}: a cause exactly when stopped")
    for part in ("tokens", "spend"):
        rec = doc.get(part) or {}
        if rec.get("recorded") is False and ({"input", "output", "usd"} & set(rec)):
            out.append(f"{where}: {part} not recorded but counts present")
    return out


def cmd_traces(out_dir: Path, sha: str, harness: str, tasks: list[str]) -> list[str]:
    problems: list[str] = []
    found = sorted(p.name for p in (out_dir / "traces").glob(f"*--{harness}--*.json"))
    wanted = sorted(trace_file(out_dir, t, harness, a).name for t in tasks for a in ARMS)
    if found != wanted:
        problems.append(f"traces present {found}, wanted {wanted}")
    for task in tasks:
        for arm in ARMS:
            path = trace_file(out_dir, task, harness, arm)
            if path.exists():
                problems += check_trace(json.loads(path.read_text(encoding="utf-8")), sha, task, arm, harness)
    return problems


def _sections(lines: list[str]) -> list[tuple[int, int]]:
    heads = [n for n, line in enumerate(lines) if line.startswith("# Harness: ")]
    if not heads:
        return []
    last = next((n for n, x in enumerate(lines) if x.startswith("# Not benchable")), len(lines))
    return list(zip(heads, [*heads[1:], last], strict=True))


def cmd_report(out_dir: Path, kind: str = "fake") -> list[str]:
    path = out_dir / "report.txt"
    if not path.exists():
        return [f"{path} does not exist"]
    lines = path.read_text(encoding="utf-8").splitlines()
    problems: list[str] = []
    first = FIRST_PREFIX[kind]
    if not lines or not (lines[0] == first if kind == "fake" else lines[0].startswith(first)):
        problems.append(f"line 1 is not the {kind} statement: {lines[:1]!r}")
    second = lines[1] if len(lines) > 1 else ""
    if "Measured by the project's own maintainer" not in second or "Reproduce:" not in second:
        problems.append(f"line 2 lacks the maintainer statement or the reproduce command: {lines[1:2]!r}")
    if APPENDIX not in lines:
        problems.append(f"no {APPENDIX!r} heading")
    else:
        cut = lines.index(APPENDIX)
        leaked = [n + 1 for n, line in enumerate(lines[:cut]) if "token" in line.lower() or "$" in line]
        if leaked:
            problems.append(f"'token' or a spend figure appears before the appendix on lines {leaked}")
    sections = _sections(lines)
    if not sections:
        problems.append("no '# Harness: ' section")
    for start, end in sections:
        block = lines[start:end]
        order = [x.split(" (")[0] for x in block if x.startswith("## ")]
        if order != SECTION_ORDER:
            problems.append(f"{lines[start]!r}: sections out of order: {order}")
        heads = [n for n, line in enumerate(block) if line.startswith("### ")]
        for n, h in enumerate(heads):
            stop = heads[n + 1] if n + 1 < len(heads) else len(block)
            task = [x for x in block[h:stop] if not x.startswith("## ")]
            for want in ("Tests: ", "What happened in vanilla:"):
                if not any(x.startswith(want) for x in task):
                    problems.append(
                        f"{block[h]!r} does not explain itself: no line starting {want.strip()!r}"
                    )
            if not any(" vs vanilla: " in x for x in task):
                problems.append(f"{block[h]!r} does not explain itself: no verdict line")
    return problems


def _verdict(v: dict[str, Any], t: dict[str, Any]) -> str:
    """Revision 8's order, written again here: ending, turns, hangs, failed commands; not wall-clock."""
    if v["ending"]["kind"] == "stopped" or t["ending"]["kind"] == "stopped":
        return "Not compared"
    pairs = [
        (RANK[v["ending"]["kind"]], RANK[t["ending"]["kind"]]),
        (v["totals"]["turns"], t["totals"]["turns"]),
        (v["totals"]["hangs"], t["totals"]["hangs"]),
        (v["totals"]["nonzero_exits"], t["totals"]["nonzero_exits"]),
    ]
    for a, b in pairs:
        if a != b:
            return "Verdict: Timelike wins" if b < a else "Verdict: Timelike loses"
    return "Verdict: Tie"


def _block(lines: list[str], harness_name: str, task: str) -> list[str]:
    for start, end in _sections(lines):
        if lines[start].startswith(f"# Harness: {harness_name} "):
            head = next((n for n in range(start, end) if lines[n].startswith(f"### {task} ")), None)
            if head is None:
                return []
            stop = next((n for n in range(head + 1, end) if lines[n].startswith(("### ", "## "))), end)
            return lines[head:stop]
    return []


def cmd_verdicts(out_dir: Path, harness: str) -> list[str]:
    report = (out_dir / "report.txt").read_text(encoding="utf-8").splitlines()
    problems: list[str] = []
    tasks = sorted({p.name.split("--")[0] for p in (out_dir / "traces").glob(f"*--{harness}--vanilla.json")})
    if not tasks:
        return [f"no {harness} vanilla traces"]
    for task in tasks:
        v = load(out_dir, task, harness, "vanilla")
        block = _block(report, HARNESS_NAME[harness], task)
        cells = {
            c
            for row in block
            if row.startswith(("turns ", "hangs ", "failed commands"))
            for c in re.split(r"\s{3,}", row)[1:]
        }
        for arm in ("not-told", "told"):
            t = load(out_dir, task, harness, arm)
            if v is None or t is None:
                continue
            want = _verdict(v, t)
            line = next((x for x in block if x.startswith(VERSUS[arm])), "")
            if want not in line:
                problems.append(f"{task} {arm}: report says {line!r}, recomputed {want!r}")
            for pair_ in re.findall(r"(\d+) (?:turns?|hangs?|failed commands?) to vanilla's (\d+)", line):
                if not set(pair_) <= cells:
                    problems.append(
                        f"{task} {arm}: the sentence quotes {pair_}, which the table does not hold"
                    )
    return problems


def cmd_adoption(out_dir: Path, harness: str) -> list[str]:
    report = (out_dir / "report.txt").read_text(encoding="utf-8").splitlines()
    name = HARNESS_NAME[harness]
    start = next((s for s, _ in _sections(report) if report[s].startswith(f"# Harness: {name} ")), None)
    if start is None:
        return [f"no section for {harness}"]
    head = report.index("## Adoption: timelike tool calls per arm", start)
    rows = {re.split(r"\s{3,}", x)[0]: re.split(r"\s{3,}", x)[1:] for x in report[head + 2 : head + 5]}
    problems: list[str] = []
    for arm in ("not-told", "told"):
        docs = [json.loads(p.read_text()) for p in (out_dir / "traces").glob(f"*--{harness}--{arm}.json")]
        if not docs:
            continue
        adopted = sum(1 for d in docs for c in d["calls"] if c.get("timelike_tools"))
        through = sum(1 for d in docs for c in d["calls"] if c.get("through_timelike"))
        row = rows.get(LABEL[arm])
        if row is None or row[2] != str(adopted) or row[4] != str(through):
            problems.append(
                f"{arm}: report row {row}, recounted {adopted} timelike tool calls, {through} through"
            )
    vanilla = rows.get("vanilla")
    if vanilla is not None and vanilla[2:] != ["—", "—", "—"]:
        problems.append(f"vanilla row counts timelike tools: {vanilla}")
    return problems


def key_shaped(name: str) -> bool:
    if GIT_CONFIG_KEY.fullmatch(name):
        return False
    words = name.upper().split("_")
    return any(w in KEY_WORDS or w.endswith(KEY_SUFFIXES) for w in words)


def cmd_env(path: Path) -> list[str]:
    names = [line.split("=", 1)[0] for line in path.read_text(encoding="utf-8").splitlines() if line]
    return [f"key-shaped variable present: {n}" for n in names if key_shaped(n)]


def cmd_hang(out_dir: Path, task: str) -> list[str]:
    """The vanilla run of TASK recorded a hang, and every hung call ended within limit + 10 s (RB5)."""
    path = trace_file(out_dir, task, "fake", "vanilla")
    if not path.exists():
        return [f"{path} does not exist"]
    doc = json.loads(path.read_text(encoding="utf-8"))
    limit_ms = int(doc["identity"]["call_limit_s"]) * 1000
    hung = [c for c in doc["calls"] if c.get("hung") is True]
    if not hung:
        return [f"{task} vanilla recorded no hung call"]
    return [
        f"{task} call {c['seq']} hung for {c['duration_ms']} ms, past limit {limit_ms} ms + 10 s"
        for c in hung
        if not limit_ms <= c["duration_ms"] < limit_ms + 10000
    ]


def main(argv: list[str]) -> int:
    if len(argv) >= 5 and argv[0] == "traces" and argv[3] in HARNESS_NAME:
        problems, what = cmd_traces(Path(argv[1]), argv[2], argv[3], argv[4:]), f"{3 * len(argv[4:])} traces"
    elif len(argv) in (2, 3) and argv[0] == "report" and (len(argv) == 2 or argv[2] in FIRST_PREFIX):
        problems, what = cmd_report(Path(argv[1]), argv[2] if len(argv) == 3 else "fake"), "report"
    elif len(argv) == 3 and argv[0] == "verdicts" and argv[2] in HARNESS_NAME:
        problems, what = cmd_verdicts(Path(argv[1]), argv[2]), "verdicts"
    elif len(argv) == 3 and argv[0] == "adoption" and argv[2] in HARNESS_NAME:
        problems, what = cmd_adoption(Path(argv[1]), argv[2]), "adoption"
    elif len(argv) == 3 and argv[0] == "hang":
        problems, what = cmd_hang(Path(argv[1]), argv[2]), "hang"
    elif len(argv) == 2 and argv[0] == "env":
        problems, what = cmd_env(Path(argv[1])), "environment"
    else:
        print(
            "usage: validate_bench.py traces OUT SHA HARNESS TASK... | report OUT [fake|standin|live] | "
            "verdicts OUT HARNESS | adoption OUT HARNESS | env FILE | hang OUT TASK",
            file=sys.stderr,
        )
        return 2
    for p in problems:
        print(f"error: {p}")
    if problems:
        return 1
    print(f"ok: {what} valid")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
