"""validate_bench — the Docker lane's independent check of a bench run's artifacts (T013; H3, P004, P005).

It shares NO code with bench/benchlib: a validator that imported the trace writer's own rules would
only prove the writer agrees with itself (cross-stack P005). Its rules are re-derived from
contracts/trace-schema.md and contracts/bench-cli.md, deliberately narrower and written differently.

    python3 validate_bench.py traces OUT SHA TASK [TASK ...]   two traces per task, stamped, totals recomputed
    python3 validate_bench.py report OUT                          the report's first lines and token placement
    python3 validate_bench.py env FILE                           no key-shaped names in `env`-style lines
    python3 validate_bench.py hang OUT TASK                      vanilla has a hung call, ended near its limit

Runs on the bench driver image's interpreter (the bats runner has no Python), stdlib only. Prints one
line per problem and exits 1 if any, else prints `ok: …` and exits 0.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

IDENTITY_KEYS = (
    "bench_revision", "environment", "image_id", "image_revision", "base_digest", "harness_name",
    "harness_version", "model_id", "invocation", "task_id", "task_version", "call_limit_s", "run_limit_s",
    "reproduce",
)  # fmt: skip
ENDINGS = {"completed", "escalated", "failed", "hung"}
# The operator's text, verbatim (send …-080659). Compared whole: a reworded first line is a failure.
FAKE_FIRST = (
    "FAKE-AGENT BENCH PIPELINE DEMO RUN -- This is not a test of timelike, rather a test of the bench test "
    "itself (its presentation and usefulness to the human user). The agent's policy was written by "
    "timelike's own builders."
)
# Every task section explains itself (send …-080659): these lines must open some line of each section.
EXPLAINS = ("Tests: ", "Verdict: ", "What happened in vanilla:", "What happened in timelike:")
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


def check_trace(doc: Any, sha: str, task: str, env: str) -> list[str]:
    where = f"{task}--{env}"
    if not isinstance(doc, dict):
        return [f"{where}: not a JSON object"]
    out: list[str] = []
    if doc.get("schema_version") != 1:
        out.append(f"{where}: schema_version is {doc.get('schema_version')!r}, not 1")
    ident = doc.get("identity") or {}
    for key in IDENTITY_KEYS:
        value = ident.get(key)
        if value in (None, "", 0) or (isinstance(value, str) and not value.strip()):
            out.append(f"{where}: identity.{key} is empty")
    if ident.get("bench_revision") != sha or ident.get("image_revision") != sha:
        out.append(
            f"{where}: revisions {ident.get('bench_revision')}/{ident.get('image_revision')} are not {sha}"
        )
    if (ident.get("task_id"), ident.get("environment")) != (task, env):
        out.append(f"{where}: identity names {ident.get('task_id')}/{ident.get('environment')}")
    if "@sha256:" not in str(ident.get("base_digest", "")):
        out.append(f"{where}: base_digest has no @sha256:")
    calls = doc.get("calls")
    totals = doc.get("totals") or {}
    if not isinstance(calls, list):
        return [*out, f"{where}: calls is not a list"]
    recount = {
        "tool_calls": len(calls),
        "nonzero_exits": sum(1 for c in calls if c.get("exit_code") != 0),
        "hangs": sum(1 for c in calls if c.get("hung") is True),
        "turns": max((c.get("turn", 0) for c in calls), default=0),
    }
    for key, value in recount.items():
        if totals.get(key) != value:
            out.append(f"{where}: totals.{key} is {totals.get(key)!r}, recounted {value}")
    if not isinstance(totals.get("wall_clock_ms"), int):
        out.append(f"{where}: totals.wall_clock_ms missing")
    ending = doc.get("ending") or {}
    if ending.get("kind") not in ENDINGS or not str(ending.get("reason", "")).strip():
        out.append(f"{where}: ending {ending!r} is not a known kind with a reason")
    tokens = doc.get("tokens") or {}
    if tokens.get("recorded") is False and ({"input", "output"} & set(tokens)):
        out.append(f"{where}: tokens not recorded but counts present")
    return out


def cmd_traces(out_dir: Path, sha: str, tasks: list[str]) -> list[str]:
    problems: list[str] = []
    found = sorted(p.name for p in (out_dir / "traces").glob("*.json"))
    wanted = sorted(f"{t}--{e}.json" for t in tasks for e in ("vanilla", "timelike"))
    if found != wanted:
        problems.append(f"traces present {found}, wanted {wanted}")
    for task in tasks:
        for env in ("vanilla", "timelike"):
            path = out_dir / "traces" / f"{task}--{env}.json"
            if path.exists():
                problems += check_trace(json.loads(path.read_text(encoding="utf-8")), sha, task, env)
    return problems


def cmd_report(out_dir: Path) -> list[str]:
    path = out_dir / "report.txt"
    if not path.exists():
        return [f"{path} does not exist"]
    lines = path.read_text(encoding="utf-8").splitlines()
    problems: list[str] = []
    if not lines or lines[0] != FAKE_FIRST:
        problems.append(f"line 1 is not the fake-agent statement: {lines[:1]!r}")
    if (
        len(lines) < 2
        or "Measured by the project's own maintainer" not in lines[1]
        or "Reproduce:" not in lines[1]
    ):
        problems.append(f"line 2 lacks the maintainer statement or the reproduce command: {lines[1:2]!r}")
    if "## Appendix: tokens" not in lines:
        problems.append("no '## Appendix: tokens' heading")
    else:
        cut = lines.index("## Appendix: tokens")
        leaked = [n + 1 for n, line in enumerate(lines[:cut]) if "token" in line.lower()]
        if leaked:
            problems.append(f"'token' appears before the appendix on lines {leaked}")
    heads = [n for n, line in enumerate(lines) if line.startswith("### ")]
    for n, start in enumerate(heads):
        end = heads[n + 1] if n + 1 < len(heads) else len(lines)
        block = [line for line in lines[start:end] if not line.startswith("## ")]
        for want in EXPLAINS:
            if not any(line.startswith(want) for line in block):
                problems.append(
                    f"{lines[start]!r} does not explain itself: no line starting {want.strip()!r}"
                )
    order = [line for line in lines if line.startswith("## Timelike ") or line.startswith("## Ties")]
    if [o.split(" (")[0] for o in order] != ["## Timelike loses", "## Ties", "## Timelike wins"]:
        problems.append(f"sections out of order: {order}")
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
    path = out_dir / "traces" / f"{task}--vanilla.json"
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
    if len(argv) >= 4 and argv[0] == "traces":
        problems, what = cmd_traces(Path(argv[1]), argv[2], argv[3:]), f"{2 * len(argv[3:])} traces"
    elif len(argv) == 2 and argv[0] == "report":
        problems, what = cmd_report(Path(argv[1])), "report"
    elif len(argv) == 3 and argv[0] == "hang":
        problems, what = cmd_hang(Path(argv[1]), argv[2]), "hang"
    elif len(argv) == 2 and argv[0] == "env":
        problems, what = cmd_env(Path(argv[1])), "environment"
    else:
        print(
            "usage: validate_bench.py traces OUT SHA TASK... | report OUT | env FILE | hang OUT TASK",
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
