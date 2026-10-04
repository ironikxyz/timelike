"""agentio's slice-1 additions: the redaction rule loader, redact_text, the pass-through gate, event_args.

Source of truth: .specswarm/features/003-concluding-run/contracts/run-cli.md § Slice 1 ("agentio (001's
module) additions") and spec.md § Slice 1 (FR-33 to FR-40), research R15, R18, R19.

Every secret-shaped value here is generated at run time from split prefixes and random characters:
none is a literal, so `make scan`'s gitleaks step and push protection stay quiet (SC-10).
"""

from __future__ import annotations

import json
import math
import secrets
import string
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

import agentio
import pytest
from conftest import REPO, base_env, events, run

RULE_FILE = REPO / "image" / "rootfs" / "etc" / "timelike" / "redaction.toml"

ALNUM = string.ascii_letters + string.digits
LOWER_ALNUM = string.ascii_lowercase + string.digits
WORD = ALNUM + "_"
WORD_DASH = WORD + "-"
B32 = string.ascii_uppercase + "234567"
B64 = ALNUM + "+/"

ToolMaker = Callable[..., Path]


# ── helpers ──────────────────────────────────────────────────────────────────────────────────────


def entropy(s: str) -> float:
    n = len(s)
    return -sum(c / n * math.log2(c / n) for c in Counter(s).values())


def rand(alphabet: str, n: int, *, min_bits: float = 3.5, edge: str = ALNUM) -> str:
    """n random characters whose entropy clears min_bits; the first and last come from `edge`."""
    while True:
        body = "".join(secrets.choice(alphabet) for _ in range(max(n - 2, 0)))
        s = secrets.choice(edge) + body + secrets.choice(edge) if n >= 2 else body
        if entropy(s) >= min_bits:
            return s


def R(kind: str) -> str:
    return f"[REDACTED:{kind}]"


@pytest.fixture(scope="module")
def rules() -> Any:
    return agentio.load_redaction_rules(RULE_FILE)


def write_rules(tmp_path: Path, body: str, name: str = "rules.toml") -> Path:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


GOOD_RULE = """
[[rules]]
id = "demo"
regex = "zq_[a-z]{8}"
keywords = ["ZQ_"]
tags = ["redact:token"]
"""


# ── generated values, one family per rule (prefixes split so no literal is secret-shaped) ─────────


def gh(prefix_letter: str) -> str:
    return "gh" + prefix_letter + "_" + rand(ALNUM, 36)


def github_fine_grained() -> str:
    return "github" + "_pat_" + rand(WORD, 82)


def gitlab() -> str:
    return "glpat" + "-" + rand(ALNUM, 20)


def digits(n: int) -> str:
    return str(secrets.choice("123456789")) + "".join(secrets.choice(string.digits) for _ in range(n - 1))


def slack_bot() -> str:
    return "xox" + "b-" + digits(12) + "-" + digits(12) + "-" + rand(ALNUM, 24)


def slack_user() -> str:
    return "xox" + "p-" + "-".join(digits(12) for _ in range(3)) + "-" + rand(ALNUM, 32)


def aws() -> str:
    return "AK" + "IA" + rand(B32, 16, edge=B32)


def gcp() -> str:
    return "AI" + "za" + rand(WORD_DASH, 35, min_bits=4.5)


def npm() -> str:
    return "npm" + "_" + rand(LOWER_ALNUM, 36)


def pypi() -> str:
    return "pypi-" + "AgEIcHlwaS5" + "vcmc" + rand(WORD, 60)


def stripe() -> str:
    return "sk" + "_live_" + rand(ALNUM, 24)


def openai() -> str:
    return "sk-" + rand(ALNUM, 20) + "T3Blbk" + "FJ" + rand(ALNUM, 20)


def anthropic(kind: str) -> str:
    return "sk-ant-" + kind + "-" + rand(ALNUM, 93) + "AA"


def jwt() -> str:
    return "ey" + rand(ALNUM, 20) + "." + "ey" + rand(ALNUM, 40) + "." + rand(ALNUM, 43)


def private_key(lines: int = 30, label: str = "RSA") -> str:
    """A PEM-shaped block of `lines` lines in all: BEGIN, lines-2 body lines, END."""
    begin = "-----BEGIN " + label + " PRIVATE" + " KEY-----"
    end = "-----END " + label + " PRIVATE" + " KEY-----"
    body = [rand(B64, 64, min_bits=4.5) for _ in range(lines - 2)]
    return "\n".join([begin, *body, end])


FAMILIES: list[tuple[str, Callable[[], str], str]] = [
    ("github-pat", lambda: gh("p"), "token"),
    ("github-oauth", lambda: gh("o"), "token"),
    ("github-app-token user", lambda: gh("u"), "token"),
    ("github-app-token server", lambda: gh("s"), "token"),
    ("github-refresh-token", lambda: gh("r"), "token"),
    ("github-fine-grained-pat", github_fine_grained, "token"),
    ("gitlab-pat", gitlab, "token"),
    ("slack-bot-token", slack_bot, "token"),
    ("slack-user-token", slack_user, "token"),
    ("aws-access-token", aws, "credential"),
    ("gcp-api-key", gcp, "key"),
    ("npm-access-token", npm, "token"),
    ("pypi-upload-token", pypi, "token"),
    ("stripe-access-token", stripe, "secret"),
    ("openai-api-key", openai, "key"),
    ("anthropic-api-key", lambda: anthropic("api03"), "key"),
    ("anthropic-admin-api-key", lambda: anthropic("admin01"), "key"),
    ("jwt", jwt, "token"),
]


# ── the rule file's path ─────────────────────────────────────────────────────────────────────────


def test_rules_path_constants() -> None:
    assert agentio.REDACTION_RULES_ENV == "TIMELIKE_REDACTION_RULES"
    assert agentio.DEFAULT_REDACTION_RULES == "/etc/timelike/redaction.toml"


def test_rules_path_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TIMELIKE_REDACTION_RULES", raising=False)
    assert agentio.redaction_rules_path() == Path("/etc/timelike/redaction.toml")


def test_rules_path_empty_env_is_the_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TIMELIKE_REDACTION_RULES", "")
    assert agentio.redaction_rules_path() == Path("/etc/timelike/redaction.toml")


def test_rules_path_env_overrides(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("TIMELIKE_REDACTION_RULES", str(tmp_path / "r.toml"))
    assert agentio.redaction_rules_path() == tmp_path / "r.toml"


# ── the loader (FR-39: missing, unparsable or invalid fails as a whole) ──────────────────────────


def test_loader_reads_a_minimal_rule(tmp_path: Path) -> None:
    body = """
[[rules]]
id = "demo"
regex = "zq_([a-z]{8})"
entropy = 2.5
keywords = ["ZQ_", "Other"]
tags = ["redact:secret"]
[[rules.allowlists]]
regexes = ["^allowed", "zzz$"]
"""
    path = write_rules(tmp_path, body)
    rs = agentio.load_redaction_rules(str(path))
    assert rs.path == str(path)
    assert rs.ids() == ["demo"]
    assert isinstance(rs.rules, tuple)
    (rule,) = rs.rules
    assert (rule.id, rule.type) == ("demo", "secret")
    assert rule.regex.pattern == "zq_([a-z]{8})"
    assert rule.keywords == ("zq_", "other")
    assert rule.entropy == 2.5
    assert [a.pattern for a in rule.allowlist] == ["^allowed", "zzz$"]
    assert all(hasattr(a, "search") for a in rule.allowlist)


def test_loader_accepts_a_path_object_and_keeps_rule_order(tmp_path: Path) -> None:
    second = GOOD_RULE.replace('id = "demo"', 'id = "second"')
    path = write_rules(tmp_path, GOOD_RULE + second)
    rs = agentio.load_redaction_rules(path)
    assert rs.ids() == ["demo", "second"]
    assert rs.rules[0].entropy is None
    assert rs.rules[0].allowlist == ()


def test_loader_missing_file_names_the_path(tmp_path: Path) -> None:
    path = tmp_path / "absent.toml"
    with pytest.raises(agentio.RulesUnavailable) as e:
        agentio.load_redaction_rules(path)
    assert str(path) in str(e.value)


@pytest.mark.parametrize(
    ("case", "body"),
    [
        ("unparsable", "[[rules]\nid = \n"),
        ("no rules", 'title = "nothing"\n[extend]\nuseDefault = true\n'),
        ("empty", ""),
        ("no tags", GOOD_RULE.replace('tags = ["redact:token"]\n', "")),
        ("no redact tag", GOOD_RULE.replace('"redact:token"', '"provider"')),
        ("two redact tags", GOOD_RULE.replace('"redact:token"', '"redact:token", "redact:key"')),
        ("type outside rule 15", GOOD_RULE.replace('"redact:token"', '"redact:cookie"')),
        ("empty type", GOOD_RULE.replace('"redact:token"', '"redact:"')),
        ("regex does not compile", GOOD_RULE.replace("zq_[a-z]{8}", "zq_([a-z")),
    ],
)
def test_loader_rejects(tmp_path: Path, case: str, body: str) -> None:
    path = write_rules(tmp_path, body)
    with pytest.raises(agentio.RulesUnavailable) as e:
        agentio.load_redaction_rules(path)
    assert str(e.value).strip(), case  # a human reason, never empty


def test_loader_fails_as_a_whole_never_partially(tmp_path: Path) -> None:
    bad = GOOD_RULE.replace('id = "demo"', 'id = "bad"').replace('"redact:token"', '"redact:cookie"')
    path = write_rules(tmp_path, GOOD_RULE + bad)
    with pytest.raises(agentio.RulesUnavailable):
        agentio.load_redaction_rules(path)


def test_rules_unavailable_is_an_exception() -> None:
    assert issubclass(agentio.RulesUnavailable, Exception)
    assert str(agentio.RulesUnavailable("why not")) == "why not"


# ── redact_text: gitleaks semantics on small rules (FR-35) ───────────────────────────────────────


def test_keyword_gates_the_rule(tmp_path: Path) -> None:
    body = GOOD_RULE.replace('keywords = ["ZQ_"]', 'keywords = ["absent-word"]')
    rs = agentio.load_redaction_rules(write_rules(tmp_path, body))
    text = "value zq_abcdefgh here\n"
    assert agentio.redact_text(text, rs) == (text, {})


def test_keyword_is_case_insensitive(tmp_path: Path) -> None:
    body = GOOD_RULE.replace("zq_[a-z]{8}", "ZQ_[a-z]{8}").replace('["ZQ_"]', '["zq_"]')
    rs = agentio.load_redaction_rules(write_rules(tmp_path, body))
    assert agentio.redact_text("a ZQ_abcdefgh b", rs) == (f"a {R('token')} b", {"token": 1})


def test_secret_is_the_first_non_empty_group(tmp_path: Path) -> None:
    body = GOOD_RULE.replace("zq_[a-z]{8}", "zq_(x*)([a-z]{8})(;?)")
    rs = agentio.load_redaction_rules(write_rules(tmp_path, body))
    # group 1 is empty, so the secret is group 2; the prefix and group 3 stay
    assert agentio.redact_text("k=zq_abcdefgh;", rs) == (f"k=zq_{R('token')};", {"token": 1})


def test_whole_match_when_no_group(tmp_path: Path) -> None:
    rs = agentio.load_redaction_rules(write_rules(tmp_path, GOOD_RULE))
    assert agentio.redact_text("k=zq_abcdefgh!", rs) == (f"k={R('token')}!", {"token": 1})


def test_entropy_below_the_rules_is_kept(tmp_path: Path) -> None:
    body = GOOD_RULE.replace('tags = ["redact:token"]', 'entropy = 3\ntags = ["redact:token"]')
    rs = agentio.load_redaction_rules(write_rules(tmp_path, body))
    low = "zq_aaaaaaaa"  # entropy well below 3
    assert agentio.redact_text(low, rs) == (low, {})
    high = "zq_" + "abcdefgh"
    assert entropy(high) >= 3
    assert agentio.redact_text(high, rs) == (R("token"), {"token": 1})


def test_allowlist_is_searched_in_the_secret(tmp_path: Path) -> None:
    body = GOOD_RULE + '[[rules.allowlists]]\nregexes = ["fine"]\n'
    rs = agentio.load_redaction_rules(write_rules(tmp_path, body))
    assert agentio.redact_text("zq_xxfinexx", rs) == ("zq_xxfinexx", {})
    assert agentio.redact_text("zq_abcdefgh", rs) == (R("token"), {"token": 1})


# ── redact_text with the repository's rule file ──────────────────────────────────────────────────


@pytest.mark.parametrize(("family", "make", "kind"), FAMILIES, ids=[f[0] for f in FAMILIES])
def test_family_is_redacted(rules: Any, family: str, make: Callable[[], str], kind: str) -> None:
    secret = make()
    text = f"before {secret} after\n"
    out, counts = agentio.redact_text(text, rules)
    assert out == f"before {R(kind)} after\n", family
    assert counts == {kind: 1}
    assert secret not in out


@pytest.mark.parametrize(("family", "make", "kind"), FAMILIES, ids=[f[0] for f in FAMILIES])
def test_family_at_end_of_text_without_newline(
    rules: Any, family: str, make: Callable[[], str], kind: str
) -> None:
    out, counts = agentio.redact_text("x=" + make(), rules)
    assert (out, counts) == ("x=" + R(kind), {kind: 1}), family


@pytest.mark.parametrize(
    ("make", "kind", "before", "after"),
    [
        (lambda: gh("p"), "token", "export GH_TOKEN=", ";echo done"),
        (stripe, "secret", "key: '", "' # stripe"),
        (gcp, "key", 'GOOGLE="', '"'),
        (npm, "token", "//registry/:_authToken=", ";"),
        (aws, "credential", "id=", ",next"),
        (jwt, "token", "Authorization: Bearer ", " (expires)"),
    ],
)
def test_only_the_secret_is_replaced(
    rules: Any, make: Callable[[], str], kind: str, before: str, after: str
) -> None:
    out, counts = agentio.redact_text(f"{before}{make()}{after}\nnext line\n", rules)
    assert out == f"{before}{R(kind)}{after}\nnext line\n"
    assert counts == {kind: 1}


def test_low_entropy_value_of_the_right_shape_is_kept(rules: Any) -> None:
    value = "gh" + "p_" + "a" * 36
    assert entropy(value) < 3
    text = f"token {value}\n"
    assert agentio.redact_text(text, rules) == (text, {})


def test_aws_allowlisted_example_is_kept(rules: Any) -> None:
    value = "AK" + "IA" + rand(B32, 9, min_bits=3.0, edge=B32) + "EXAMPLE"
    assert len(value) == 20
    assert entropy(value) >= 3  # so the allowlist, not the entropy floor, is what keeps it
    text = f"aws_access_key_id = {value}\n"
    assert agentio.redact_text(text, rules) == (text, {})


def test_private_key_keeps_the_line_count_and_counts_once(rules: Any) -> None:
    pem = private_key(30)
    text = "start\npem: " + pem + " end\nafter\n"
    out, counts = agentio.redact_text(text, rules)
    assert counts == {"key": 1}
    assert out.count("\n") == text.count("\n")
    lines = out.split("\n")
    assert lines[0] == "start"
    assert lines[1] == "pem: " + R("key")
    assert lines[2:30] == [R("key")] * 28
    assert lines[30] == R("key") + " end"
    assert lines[31:] == ["after", ""]


@pytest.mark.parametrize("label", ["RSA", "EC", "OPENSSH", ""])
def test_private_key_labels(rules: Any, label: str) -> None:
    pem = private_key(6, label) if label else private_key(6).replace("RSA ", "")
    out, counts = agentio.redact_text(pem + "\n", rules)
    assert (out, counts) == ("\n".join([R("key")] * 6) + "\n", {"key": 1})


def test_scenario7_counts_by_type(rules: Any) -> None:
    text = "\n".join(["gh: " + gh("p"), "aws: " + aws(), private_key(5), "done", ""])
    out, counts = agentio.redact_text(text, rules)
    assert counts == {"credential": 1, "key": 1, "token": 1}
    assert out.count("\n") == text.count("\n")
    assert out.splitlines()[:2] == ["gh: " + R("token"), "aws: " + R("credential")]


def test_counts_are_one_per_secret(rules: Any) -> None:
    text = f"{gh('p')} {gh('o')}\n{gitlab()}\n{stripe()}\n{stripe()} end\n"
    out, counts = agentio.redact_text(text, rules)
    assert counts == {"token": 3, "secret": 2}
    assert out == f"{R('token')} {R('token')}\n{R('token')}\n{R('secret')}\n{R('secret')} end\n"


def test_two_private_keys_count_two(rules: Any) -> None:
    text = private_key(4) + "\nbetween\n" + private_key(4) + "\n"
    out, counts = agentio.redact_text(text, rules)
    assert counts == {"key": 2}
    assert out.splitlines() == [R("key")] * 4 + ["between"] + [R("key")] * 4


def test_nothing_to_redact_is_identical(rules: Any) -> None:
    text = "compiling key.c\nghp is not a token\nsk_live without a value\n-----BEGIN nothing\n\n"
    out, counts = agentio.redact_text(text, rules)
    assert out == text
    assert counts == {}


def test_empty_text(rules: Any) -> None:
    assert agentio.redact_text("", rules) == ("", {})


def test_redaction_is_idempotent(rules: Any) -> None:
    text = "\n".join(
        [f"{name}: {make()}" for name, make, _ in FAMILIES] + ["k: " + private_key(10), "tail", ""]
    )
    once, counts = agentio.redact_text(text, rules)
    assert sum(counts.values()) == len(FAMILIES) + 1
    assert agentio.redact_text(once, rules) == (once, {})


def test_redacted_marker_matches_agentio_redact(rules: Any) -> None:
    out, _ = agentio.redact_text("t " + gh("p"), rules)
    assert out == "t " + agentio.redact("x", "token")


# ── the pass-through gate (contract: exit == command_exit, command_exit not null, for any cause) ──


def gated(cause: str, exit: int, command_exit: str) -> str:
    return (
        f'return agentio.Result(target="t", scope="run", verdict="v", exit={exit},'
        f' cause="{cause}", command_exit={command_exit})'
    )


def go(py: str, tool: Path, scratch: Path, *args: str) -> Any:
    return run([py, str(tool), *args], base_env(scratch))


@pytest.mark.parametrize(("cause", "code"), [("memory", 137), ("disk", 42), ("command", 137)])
def test_gate_accepts_any_cause_when_exit_is_the_commands(
    py: str, make_tool: ToolMaker, scratch: Path, cause: str, code: int
) -> None:
    t = make_tool("gate", gated(cause, code, str(code)), passes_exit=True)
    r = go(py, t, scratch, "--json", "x")
    assert r.returncode == code, r.stderr
    assert "outside the contract vocabulary" not in r.stderr
    doc = json.loads(r.stdout)
    assert (doc["exit"], doc["cause"], doc["command_exit"]) == (code, cause, code)
    assert events(scratch)[-1]["exit"] == code


def test_gate_rejects_null_command_exit(py: str, make_tool: ToolMaker, scratch: Path) -> None:
    t = make_tool("gate", gated("memory", 137, "None"), passes_exit=True)
    r = go(py, t, scratch, "--json", "x")
    assert r.returncode == 1
    assert "outside the contract vocabulary" in r.stderr


def test_gate_rejects_a_different_command_exit(py: str, make_tool: ToolMaker, scratch: Path) -> None:
    t = make_tool("gate", gated("memory", 137, "1"), passes_exit=True)
    r = go(py, t, scratch, "--json", "x")
    assert r.returncode == 1
    assert "outside the contract vocabulary" in r.stderr


def test_gate_rejects_a_tool_without_pass_through(py: str, make_tool: ToolMaker, scratch: Path) -> None:
    t = make_tool("gate", gated("memory", 137, "137"))
    r = go(py, t, scratch, "--json")
    assert r.returncode == 1
    assert "outside the contract vocabulary" in r.stderr


# ── Context.event_args (FR-37: the session event's arguments) ────────────────────────────────────


def test_context_event_args_defaults_to_none(tmp_path: Path) -> None:
    tool = agentio.Tool(name="t", target="fixture", summary="t test tool")
    ctx = agentio.Context(tool, ["a"], "test", tmp_path, "json", 0, False)
    assert ctx.event_args is None
    ctx.event_args = ["b"]
    assert ctx.event_args == ["b"]


EVENT_ARGS_BODY = """
ctx.event_args = ["--json", "shown", "[REDACTED:token]"]
return agentio.Result(target="t", scope="s", verdict="ok")
"""


def test_event_records_event_args_when_set(py: str, make_tool: ToolMaker, scratch: Path) -> None:
    t = make_tool("evargs", EVENT_ARGS_BODY)
    r = go(py, t, scratch, "--json", "--lines", "3")
    assert r.returncode == 0, r.stderr
    assert events(scratch)[-1]["args"] == ["--json", "shown", "[REDACTED:token]"]


def test_event_records_event_args_on_a_pass_through_tool(
    py: str, make_tool: ToolMaker, scratch: Path
) -> None:
    body = 'ctx.event_args = ["echo", "[REDACTED:key]"]\n' + gated("command", 0, "0")
    t = make_tool("evpass", body, passes_exit=True)
    r = go(py, t, scratch, "--json", "echo", "visible")
    assert r.returncode == 0, r.stderr
    assert events(scratch)[-1]["args"] == ["echo", "[REDACTED:key]"]


def test_event_records_argv_when_event_args_unset(py: str, make_tool: ToolMaker, scratch: Path) -> None:
    t = make_tool("plain", 'return agentio.Result(target="t", scope="s", verdict="ok")')
    assert go(py, t, scratch, "--json", "--lines", "3").returncode == 0
    assert events(scratch)[-1]["args"] == ["--json", "--lines", "3"]
