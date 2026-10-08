"""run (feature 003) slice 1: the memory cause, the disk cause, redaction (contracts/run-cli.md § Slice 1).

The tool runs as a real subprocess, as in test_run.py. The system is faked on the host:
- memory: TIMELIKE_CGROUP_ROOT points at a directory of fake cgroup files, and the wrapped command
  itself rewrites memory.events to simulate an OOM kill during the command;
- disk: TIMELIKE_RUN_DISK_FULL_BYTES moves the "full" threshold (huge: everything is full; 0: nothing);
- redaction: TIMELIKE_REDACTION_RULES points at the repository's rule file.

Every secret-shaped value is generated at run time; none is a literal in this file (spec SC-10), so
`make scan`'s gitleaks step stays at 0 findings. Processes are found only through marker files.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import secrets
import signal
import string
from pathlib import Path
from typing import Any

import pytest
import schema
from conftest import REPO, TOOLS_DIR, base_env, events, run

RUN = TOOLS_DIR / "run"
RULES = REPO / "image" / "rootfs" / "etc" / "timelike" / "redaction.toml"
VERDICT_RE = re.compile(r"^verdict: exit (\d+) \((.+?)\) · (\d+\.\d) s · (\d+) lines · log (/\S+)")
MIB_96 = 100663296
PEAK = 99614720  # 95.0 MiB
EVENTS_QUIET = "low 0\nhigh 0\nmax 12\noom 3\noom_kill 3\noom_group_kill 0\n"
EVENTS_KILLED = "low 0\nhigh 0\nmax 14\noom 4\noom_kill 4\noom_group_kill 0\n"
MEMORY_KEYS = {"state", "limit_bytes", "peak_bytes", "oom_kills", "command_max_rss_bytes", "reason"}
DISK_KEYS = {"role", "path", "mount", "free_bytes", "free_inodes", "full"}
REDACTION_KEYS = {"state", "counts", "rules", "log_rewritten", "reason"}
RULE_IDS = [
    "anthropic-admin-api-key",
    "anthropic-api-key",
    "aws-access-token",
    "gcp-api-key",
    "github-app-token",
    "github-fine-grained-pat",
    "github-oauth",
    "github-pat",
    "github-refresh-token",
    "gitlab-pat",
    "jwt",
    "npm-access-token",
    "openai-api-key",
    "private-key",
    "pypi-upload-token",
    "slack-bot-token",
    "slack-user-token",
    "stripe-access-token",
]
HUGE = str(10**18)


# ── helpers ────────────────────────────────────────────────────────────────────────────────────


def go(py: str, scratch: Path, *args: str, timeout: float = 30, **env: str) -> Any:
    """run as a subprocess. Unless a test says otherwise, the rule file is the repository's and the
    cgroup is a quiet fake (so the host's real cgroup never decides a result)."""
    env.setdefault("TIMELIKE_REDACTION_RULES", str(RULES))
    # The verdict's slice-1 parts follow the log path, and pytest's scratch paths are long: under the
    # default COLUMNS (200) rule 13 cuts the text verdict before them. The image's log path is short.
    env.setdefault("COLUMNS", "1000")
    if "TIMELIKE_CGROUP_ROOT" not in env:
        env["TIMELIKE_CGROUP_ROOT"] = str(cgroup(scratch.parent / "cgroup-quiet"))
    return run([py, str(RUN), *args], base_env(scratch, **env), timeout=timeout)


def doc_of(r: Any) -> dict[str, Any]:
    doc: dict[str, Any] = json.loads(r.stdout)
    return doc


def cgroup(d: Path, events_text: str = EVENTS_QUIET, limit: str = str(MIB_96), peak: int = PEAK) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    (d / "memory.events").write_text(events_text)
    (d / "memory.max").write_text(limit + "\n")
    (d / "memory.peak").write_text(f"{peak}\n")
    return d


def oom_then(d: Path, tail: str) -> list[str]:
    """A command that simulates an OOM kill during itself (the count rises), then does `tail`."""
    return ["sh", "-c", f'printf "%s" "$1" > "$2/memory.events"; {tail}', "_", EVENTS_KILLED, str(d)]


def size(n: int) -> str:
    """The contract's sizes: binary units, an integer below 1 KiB, else one decimal."""
    if n < 1024:
        return f"{n} B"
    value = float(n)
    for unit in ("KiB", "MiB", "GiB", "TiB"):
        value /= 1024
        if value < 1024 or unit == "TiB":
            return f"{value:.1f} {unit}"
    raise AssertionError("unreachable")


def mount_of(path: Path) -> str:
    """The longest mount point in /proc/self/mountinfo that is a prefix of the resolved path (R17)."""
    target = str(path.resolve())
    best = "/"
    for line in Path("/proc/self/mountinfo").read_text().splitlines():
        raw = line.split()[4]
        point = re.sub(r"\\([0-7]{3})", lambda m: chr(int(m.group(1), 8)), raw)
        inside = target == point or target.startswith(point.rstrip("/") + "/")
        if inside and len(point) > len(best):
            best = point
    return best


def kill_quietly(pids: list[int]) -> None:
    for pid in pids:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.kill(pid, signal.SIGKILL)


ALNUM = string.ascii_letters + string.digits
BASE32 = string.ascii_uppercase + "234567"
B64 = string.ascii_letters + string.digits + "+/"


def gh_token() -> str:
    return "gh" + "p_" + "".join(secrets.choice(ALNUM) for _ in range(36))


def aws_key_id() -> str:
    return "AK" + "IA" + "".join(secrets.choice(BASE32) for _ in range(16))


def private_key() -> list[str]:
    """30 lines: the header, 28 body lines, the footer. Built at run time, never a literal."""
    kind = "RSA " + "PRIVATE " + "KEY"
    body = ["".join(secrets.choice(B64) for _ in range(64)) for _ in range(28)]
    return ["-----" + "BEGIN " + kind + "-----", *body, "-----" + "END " + kind + "-----"]


def secrets_file(tmp_path: Path) -> tuple[Path, list[str], list[str]]:
    """A file holding a token, an access key id and a private key among ordinary lines.

    Returns (path, its lines, the secret strings that must never be shown or stored)."""
    token, aws, key = gh_token(), aws_key_id(), private_key()
    lines = ["start", f"token={token}", f"aws id {aws} here", *key, "end"]
    path = tmp_path / "out.txt"
    path.write_text("\n".join(lines) + "\n")
    return path, lines, [token, aws, *key[1:-1]]


# ── US5 · the memory cause (FR-25 to FR-28) ─────────────────────────────────────────────────────


def test_oom_kill_and_sigkill_is_memory_with_limit_and_peak(py: str, scratch: Path, tmp_path: Path) -> None:
    d = cgroup(tmp_path / "cg")
    r = go(py, scratch, "--json", *oom_then(d, "kill -9 $$"), TIMELIKE_CGROUP_ROOT=str(d))
    assert r.returncode == 137, r.stderr
    doc = doc_of(r)
    assert (doc["exit"], doc["cause"], doc["command_exit"]) == (137, "memory", 137)
    assert doc["verdict"].startswith("exit 137 (out of memory: limit 96.0 MiB, peak 95.0 MiB) · ")
    mem = doc["memory"]
    assert set(mem) == MEMORY_KEYS
    assert (mem["state"], mem["limit_bytes"], mem["peak_bytes"], mem["oom_kills"]) == (
        "read",
        MIB_96,
        PEAK,
        1,
    )
    assert isinstance(mem["command_max_rss_bytes"], int) and mem["command_max_rss_bytes"] > 0
    assert mem["reason"] is None
    assert events(scratch)[-1]["exit"] == 137


def test_oom_kill_text_verdict(py: str, scratch: Path, tmp_path: Path) -> None:
    d = cgroup(tmp_path / "cg")
    r = go(py, scratch, "--text", *oom_then(d, "kill -9 $$"), TIMELIKE_CGROUP_ROOT=str(d))
    m = VERDICT_RE.match(r.stdout.splitlines()[1])
    assert m, r.stdout
    assert m.group(1, 2) == ("137", "out of memory: limit 96.0 MiB, peak 95.0 MiB")


@pytest.mark.parametrize("code", [1, 137])
def test_oom_kill_and_a_failing_exit_is_memory_and_the_exit_passes_through(
    py: str, scratch: Path, tmp_path: Path, code: int
) -> None:
    d = cgroup(tmp_path / "cg")
    r = go(py, scratch, "--json", *oom_then(d, f"exit {code}"), TIMELIKE_CGROUP_ROOT=str(d))
    assert r.returncode == code
    doc = doc_of(r)
    assert (doc["exit"], doc["cause"], doc["command_exit"]) == (code, "memory", code)
    assert doc["verdict"].startswith(f"exit {code} (out of memory: limit 96.0 MiB, peak 95.0 MiB) · ")


def test_the_rise_is_counted_not_the_total(py: str, scratch: Path, tmp_path: Path) -> None:
    d = cgroup(tmp_path / "cg", events_text="oom 3\noom_kill 3\n")
    cmd = ["sh", "-c", 'printf "oom 5\\noom_kill 5\\n" > "$1/memory.events"; exit 1', "_", str(d)]
    doc = doc_of(go(py, scratch, "--json", *cmd, TIMELIKE_CGROUP_ROOT=str(d)))
    assert doc["cause"] == "memory"
    assert doc["memory"]["oom_kills"] == 2


def test_only_oom_kill_is_read(py: str, scratch: Path, tmp_path: Path) -> None:
    d = cgroup(tmp_path / "cg")
    rising_group = EVENTS_QUIET.replace("oom_group_kill 0", "oom_group_kill 9").replace("oom 3", "oom 9")
    cmd = ["sh", "-c", 'printf "%s" "$1" > "$2/memory.events"; kill -9 $$', "_", rising_group, str(d)]
    doc = doc_of(go(py, scratch, "--json", *cmd, TIMELIKE_CGROUP_ROOT=str(d)))
    assert doc["cause"] == "command"
    assert doc["memory"]["oom_kills"] == 0


def test_no_limit_set(py: str, scratch: Path, tmp_path: Path) -> None:
    d = cgroup(tmp_path / "cg", limit="max")
    doc = doc_of(go(py, scratch, "--json", *oom_then(d, "kill -9 $$"), TIMELIKE_CGROUP_ROOT=str(d)))
    assert doc["cause"] == "memory"
    assert doc["verdict"].startswith("exit 137 (out of memory: no limit set, peak 95.0 MiB) · ")
    assert doc["memory"]["limit_bytes"] is None
    assert doc["memory"]["peak_bytes"] == PEAK


def test_oom_kill_under_exit_0_stays_command_and_says_so(py: str, scratch: Path, tmp_path: Path) -> None:
    d = cgroup(tmp_path / "cg")
    r = go(py, scratch, "--json", *oom_then(d, "exit 0"), TIMELIKE_CGROUP_ROOT=str(d))
    assert r.returncode == 0
    doc = doc_of(r)
    assert (doc["cause"], doc["command_exit"]) == ("command", 0)
    assert doc["verdict"].startswith("exit 0 (command exited 0) · ")
    assert " · OOM kill during the command (limit 96.0 MiB, peak 95.0 MiB)" in doc["verdict"]
    assert (doc["memory"]["state"], doc["memory"]["oom_kills"]) == ("read", 1)


def test_sigkill_with_no_rise_is_the_commands(py: str, scratch: Path, tmp_path: Path) -> None:
    d = cgroup(tmp_path / "cg")
    r = go(py, scratch, "--json", "sh", "-c", "kill -9 $$", TIMELIKE_CGROUP_ROOT=str(d))
    assert r.returncode == 137
    doc = doc_of(r)
    assert doc["cause"] == "command"
    assert doc["verdict"].startswith("exit 137 (command killed by signal 9 (SIGKILL)) · ")
    assert "out of memory" not in doc["verdict"] and "memory: unknown" not in doc["verdict"]
    assert (doc["memory"]["state"], doc["memory"]["oom_kills"]) == ("read", 0)
    assert doc["memory"]["limit_bytes"] == MIB_96


@pytest.mark.parametrize("command", [["sh", "-c", "kill -9 $$"], ["sh", "-c", "exit 137"]])
def test_unreadable_cgroup_under_sigkill_is_unknown_and_named(
    py: str, scratch: Path, tmp_path: Path, command: list[str]
) -> None:
    empty = tmp_path / "no-cgroup"
    empty.mkdir()
    r = go(py, scratch, "--json", *command, TIMELIKE_CGROUP_ROOT=str(empty))
    assert r.returncode == 137
    doc = doc_of(r)
    assert doc["cause"] == "command"  # a cause is never guessed (send seam 1)
    mem = doc["memory"]
    assert set(mem) == MEMORY_KEYS
    assert mem["state"] == "unknown"
    reason = mem["reason"]
    assert isinstance(reason, str)
    assert reason.startswith(str(empty) + "/memory.")
    assert reason.endswith(": No such file or directory")
    assert f" · memory: unknown ({reason})" in doc["verdict"]
    assert "out of memory" not in doc["verdict"]


def test_unreadable_cgroup_under_exit_1_is_unknown_without_verdict_words(
    py: str, scratch: Path, tmp_path: Path
) -> None:
    empty = tmp_path / "no-cgroup"
    empty.mkdir()
    doc = doc_of(go(py, scratch, "--json", "false", TIMELIKE_CGROUP_ROOT=str(empty)))
    assert (doc["exit"], doc["cause"]) == (1, "command")
    assert doc["memory"]["state"] == "unknown"
    assert "memory: unknown" not in doc["verdict"]  # only under SIGKILL / 137


def test_exit_0_with_nothing_is_not_looked_at(py: str, scratch: Path) -> None:
    doc = doc_of(go(py, scratch, "--json", "true"))
    assert set(doc["memory"]) == MEMORY_KEYS
    assert doc["memory"]["state"] == "not looked at"
    assert "OOM" not in doc["verdict"]


def test_memory_is_tested_before_disk(py: str, scratch: Path, tmp_path: Path) -> None:
    d = cgroup(tmp_path / "cg")
    cmd = oom_then(d, "kill -9 $$")
    doc = doc_of(
        go(py, scratch, "--json", *cmd, TIMELIKE_CGROUP_ROOT=str(d), TIMELIKE_RUN_DISK_FULL_BYTES=HUGE)
    )
    assert doc["cause"] == "memory"
    assert doc["exit"] == 137


# ── US6 · the disk cause (FR-29 to FR-32) ───────────────────────────────────────────────────────


def check_disk_entries(doc: dict[str, Any], scratch: Path, full: bool) -> dict[str, dict[str, Any]]:
    disk = doc["disk"]
    assert [e["role"] for e in disk] == ["workspace", "scratch"]
    by_role = {e["role"]: e for e in disk}
    for e in disk:
        assert set(e) == DISK_KEYS
        assert isinstance(e["free_bytes"], int) and isinstance(e["free_inodes"], int)
        assert e["full"] is full
        assert e["mount"] == mount_of(Path(e["path"]))
    assert Path(by_role["workspace"]["path"]).resolve() == Path.cwd().resolve()
    assert Path(doc["log"]).resolve().is_relative_to(Path(by_role["scratch"]["path"]).resolve())
    return by_role


def test_full_filesystems_are_the_disk_cause(py: str, scratch: Path) -> None:
    r = go(py, scratch, "--json", "false", TIMELIKE_RUN_DISK_FULL_BYTES=HUGE)
    assert r.returncode == 1
    doc = doc_of(r)
    assert (doc["exit"], doc["cause"], doc["command_exit"]) == (1, "disk", 1)
    by_role = check_disk_entries(doc, scratch, full=True)
    m = re.match(r"exit 1 \((disk full: .+?)\) · ", doc["verdict"])
    assert m, doc["verdict"]
    words = m.group(1)
    for e in by_role.values():
        assert f"{e['mount']} has {size(e['free_bytes'])} free" in words
    assert " · log may be incomplete" in doc["verdict"]  # the scratch filesystem is full


def test_full_disk_text_verdict(py: str, scratch: Path) -> None:
    r = go(py, scratch, "--text", "sh", "-c", "echo partial; exit 3", TIMELIKE_RUN_DISK_FULL_BYTES=HUGE)
    assert r.returncode == 3
    m = VERDICT_RE.match(r.stdout.splitlines()[1])
    assert m, r.stdout
    assert m.group(2).startswith("disk full: ")
    assert " · log may be incomplete" in r.stdout.splitlines()[1]


@pytest.mark.parametrize("message", ["No space left on device", "Disk quota exceeded"])
def test_the_enospc_message_in_the_output_is_the_disk_cause(py: str, scratch: Path, message: str) -> None:
    cmd = ["sh", "-c", f'echo "cp: error writing out.bin: {message}" >&2; exit 1']
    doc = doc_of(go(py, scratch, "--json", *cmd, TIMELIKE_RUN_DISK_FULL_BYTES="0"))
    assert (doc["exit"], doc["cause"], doc["command_exit"]) == (1, "disk", 1)
    by_role = check_disk_entries(doc, scratch, full=False)
    ws, sc = by_role["workspace"], by_role["scratch"]
    words = (
        f'disk full: "{message}" in the output; '
        f"{ws['mount']} has {size(ws['free_bytes'])} free, {sc['mount']} has {size(sc['free_bytes'])} free"
    )
    assert doc["verdict"].startswith(f"exit 1 ({words}) · "), doc["verdict"]
    assert "log may be incomplete" not in doc["verdict"]


def test_a_failure_with_room_and_no_message_is_the_commands(py: str, scratch: Path) -> None:
    doc = doc_of(go(py, scratch, "--json", "sh", "-c", "echo nope; exit 1", TIMELIKE_RUN_DISK_FULL_BYTES="0"))
    assert (doc["exit"], doc["cause"]) == (1, "command")
    assert doc["verdict"].startswith("exit 1 (command exited 1) · ")
    check_disk_entries(doc, scratch, full=False)


def test_the_default_threshold_on_a_roomy_host_is_not_full(py: str, scratch: Path) -> None:
    doc = doc_of(go(py, scratch, "--json", "false"))
    assert doc["cause"] == "command"
    assert all(e["full"] is False for e in doc["disk"])


def test_exit_0_checks_no_disk(py: str, scratch: Path) -> None:
    cmd = ["sh", "-c", "echo 'No space left on device'; exit 0"]
    doc = doc_of(go(py, scratch, "--json", *cmd, TIMELIKE_RUN_DISK_FULL_BYTES=HUGE))
    assert (doc["exit"], doc["cause"]) == (0, "command")
    assert doc["disk"] == []
    assert "disk full" not in doc["verdict"] and "log may be incomplete" not in doc["verdict"]


@pytest.mark.parametrize("value", ["-1", "abc", "1.5"])
def test_bad_disk_threshold_is_usage_and_runs_nothing(
    py: str, scratch: Path, tmp_path: Path, value: str
) -> None:
    marker = tmp_path / "ran"
    r = go(py, scratch, "touch", str(marker), TIMELIKE_RUN_DISK_FULL_BYTES=value)
    assert r.returncode == 2
    assert "TIMELIKE_RUN_DISK_FULL_BYTES" in r.stderr
    assert not r.stdout.startswith("run: ")  # no verdict
    assert not marker.exists()


# ── US7 · redaction (FR-33 to FR-40) ─────────────────────────────────────────────────────────────


def test_secrets_are_redacted_in_shown_lines_and_log_json(py: str, scratch: Path, tmp_path: Path) -> None:
    path, lines, hidden = secrets_file(tmp_path)
    r = go(py, scratch, "--json", "cat", str(path))
    assert r.returncode == 0, r.stderr
    doc = doc_of(r)
    log = Path(doc["log"])
    stored = log.read_text()
    for s in hidden:
        assert s not in r.stdout
        assert s not in stored
    assert stored.count("\n") == len(lines)  # the log keeps its line count (FR-36)
    assert doc["line_count"] == len(lines)
    assert doc["lines"] == stored.splitlines()  # shown output is read from the redacted log (FR-37)
    assert doc["lines"][0] == "start" and doc["lines"][-1] == "end"
    assert doc["lines"][1] == "token=[REDACTED:token]"
    assert doc["lines"][2] == "aws id [REDACTED:credential] here"
    assert "[REDACTED:key]" in stored
    assert doc["verdict"].endswith(" · redacted 3 (credential 1, key 1, token 1)")
    red = doc["redaction"]
    assert set(red) == REDACTION_KEYS
    assert red["state"] == "applied"
    assert red["counts"] == {"credential": 1, "key": 1, "token": 1}
    assert red["rules"] == str(RULES)
    assert red["log_rewritten"] is True
    assert red["reason"] is None


def test_secrets_are_redacted_in_text_mode(py: str, scratch: Path, tmp_path: Path) -> None:
    path, lines, hidden = secrets_file(tmp_path)
    r = go(py, scratch, "--text", "cat", str(path))
    out = r.stdout.splitlines()
    for s in hidden:
        assert s not in r.stdout
    assert out[1].endswith(" · redacted 3 (credential 1, key 1, token 1)")
    assert out[2:4] == ["start", "token=[REDACTED:token]"]
    assert len(out) == 2 + len(lines)
    assert "[REDACTED:key]" in out


def test_nothing_to_redact_leaves_the_log_alone(py: str, scratch: Path) -> None:
    doc = doc_of(go(py, scratch, "--json", "sh", "-c", "echo one; echo two"))
    assert " · redacted" not in doc["verdict"]
    red = doc["redaction"]
    assert (red["state"], red["counts"], red["log_rewritten"]) == ("applied", {}, False)
    assert Path(doc["log"]).read_text() == "one\ntwo\n"


def test_a_secret_argument_is_redacted_in_header_target_and_event(py: str, scratch: Path) -> None:
    token = gh_token()
    r = go(py, scratch, "--text", "echo", token)
    out = r.stdout.splitlines()
    assert token not in r.stdout
    assert out[0] == "run: echo '[REDACTED:token]' [run]" or out[0] == "run: echo [REDACTED:token] [run]"
    assert out[2] == "[REDACTED:token]"
    ev = events(scratch)[-1]
    assert token not in json.dumps(ev)
    assert any("[REDACTED:token]" in a for a in ev["args"])

    doc = doc_of(go(py, scratch, "--json", "echo", token))
    assert token not in doc["target"]
    assert "[REDACTED:token]" in doc["target"]
    assert token not in json.dumps(events(scratch)[-1])
    assert schema.errors(events(scratch)[-1], schema.load("event.schema.json")) == []


def test_a_private_key_in_capped_output_keeps_line_numbers_true(
    py: str, scratch: Path, tmp_path: Path
) -> None:
    key = private_key()
    lines = [f"line {k}" for k in range(1, 301)]
    lines[119:149] = key  # lines 120–149: inside the gap of the default cap (200: head 50, tail 100)
    lines[199] = "error: after the key"  # line 200, last of the gap
    src = tmp_path / "big.txt"
    src.write_text("\n".join(lines) + "\n")
    r = go(py, scratch, "--text", "cat", str(src))
    out = r.stdout.splitlines()
    m = VERDICT_RE.match(out[1])
    assert m, r.stdout
    assert m.group(4) == "300"
    assert out[1].endswith(" · redacted 1 (key 1)")
    log = Path(m.group(5))
    stored = log.read_text().splitlines()
    assert len(stored) == 300
    assert stored[199] == "error: after the key"
    assert stored[118] == "line 119" and stored[149] == "line 150"
    assert all("[REDACTED:key]" in x for x in stored[119:149])
    assert "L200: error: after the key" in out
    more = next(x for x in out if x.startswith("more: "))[len("more: ") :]
    assert more == f"sed -n 51,200p {log}"
    rest = run(["sh", "-c", more], base_env(scratch)).stdout
    assert rest.splitlines() == stored[50:200]
    for x in key[1:-1]:
        assert x not in rest and x not in r.stdout


@pytest.mark.parametrize("bad", ["missing", "unparsable"])
def test_unavailable_rules_withhold_the_output(py: str, scratch: Path, tmp_path: Path, bad: str) -> None:
    rules = tmp_path / "rules.toml"
    if bad == "unparsable":
        rules.write_text("this is [ not toml\n")
    src = tmp_path / "out.txt"
    token = gh_token()
    src.write_text(f"shown? {token}\nsecond\n")
    cmd = ["sh", "-c", f"cat {src}; exit 3"]

    r = go(py, scratch, "--json", *cmd, TIMELIKE_REDACTION_RULES=str(rules))
    assert r.returncode == 3  # the exit is still the command's
    doc = doc_of(r)
    assert (doc["cause"], doc["command_exit"]) == ("command", 3)
    assert doc["lines"] == []
    assert token not in r.stdout
    assert " · output withheld: redaction rules unavailable (" in doc["verdict"]
    assert doc["verdict"].endswith("); the log is unredacted")
    if bad == "missing":
        assert str(rules) in doc["verdict"]
    red = doc["redaction"]
    assert set(red) == REDACTION_KEYS
    assert (red["state"], red["rules"], red["log_rewritten"]) == ("unavailable", str(rules), False)
    assert isinstance(red["reason"], str) and red["reason"]
    assert token in Path(doc["log"]).read_text()  # what the verdict says: the log is unredacted

    t = go(py, scratch, "--text", *cmd, TIMELIKE_REDACTION_RULES=str(rules))
    assert t.returncode == 3
    out = t.stdout.splitlines()
    assert len(out) == 2, out  # the header and the verdict; no body
    assert "output withheld: redaction rules unavailable (" in out[1]
    assert token not in t.stdout


def test_a_detached_holder_of_a_rewritten_log_is_told(py: str, scratch: Path, tmp_path: Path) -> None:
    path, _, hidden = secrets_file(tmp_path)
    marker = tmp_path / "child.pid"
    cmd = ["sh", "-c", f"sleep 30 & echo $! > {marker}; cat {path}"]
    r = go(py, scratch, "--json", *cmd)
    doc = doc_of(r)
    pids = [d["pid"] for d in doc["detached"]]
    try:
        child = int(marker.read_text())
        assert child in pids
        assert doc["redaction"]["log_rewritten"] is True
        assert "detached output after this is not kept" in doc["verdict"]
        v = doc["verdict"]
        assert v.index(" · redacted 3 ") < v.index("detached output after this is not kept")
        for s in hidden:
            assert s not in Path(doc["log"]).read_text()
    finally:
        kill_quietly(pids)
        with contextlib.suppress(OSError, ValueError):
            kill_quietly([int(marker.read_text())])


def test_a_detached_holder_without_redaction_is_not_warned(py: str, scratch: Path, tmp_path: Path) -> None:
    marker = tmp_path / "child.pid"
    doc = doc_of(go(py, scratch, "--json", "sh", "-c", f"sleep 30 & echo $! > {marker}; echo hi"))
    pids = [d["pid"] for d in doc["detached"]]
    try:
        assert doc["redaction"]["log_rewritten"] is False
        assert "not kept" not in doc["verdict"]
    finally:
        kill_quietly(pids)
        with contextlib.suppress(OSError, ValueError):
            kill_quietly([int(marker.read_text())])


# ── the manifest and help (FR-40) ───────────────────────────────────────────────────────────────


def test_manifest_names_the_rules_and_the_disk_threshold(py: str, scratch: Path) -> None:
    doc = doc_of(go(py, scratch, "--agent-info"))
    rr = doc["redaction_rules"]
    assert isinstance(rr["path"], str) and rr["path"].endswith("redaction.toml")
    assert sorted(rr["ids"]) == RULE_IDS
    assert doc["disk_full_bytes"] == 1048576
    assert schema.errors(doc, schema.load("agent-info.schema.json")) == []


def test_help_has_a_line_on_redaction(py: str, scratch: Path) -> None:
    out = go(py, scratch, "--help").stdout.splitlines()
    assert len(out) <= 40
    assert sum("redact" in x.lower() for x in out) >= 1
