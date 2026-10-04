"""The repository's redaction rule file, as a file (feature 003 slice 1, FR-33, FR-34, research R15).

Source of truth: .specswarm/features/003-concluding-run/spec.md § Slice 1 and contracts/run-cli.md
§ Slice 1. The structural checks read the TOML with tomllib directly, so they hold whatever agentio's
loader does; the load itself goes through agentio. No sample secret is written in this file.
"""

from __future__ import annotations

import re
import tomllib
from typing import Any

import agentio
import pytest
from conftest import REPO

RULE_FILE = REPO / "image" / "rootfs" / "etc" / "timelike" / "redaction.toml"
RULE15_TYPES = {"token", "password", "key", "secret", "credential"}

# FR-33 names the rules; never paraphrased.
FR33_IDS = {
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
}


def _doc() -> dict[str, Any]:
    return tomllib.loads(RULE_FILE.read_text(encoding="utf-8"))


def _rules() -> list[dict[str, Any]]:
    rules = _doc()["rules"]
    assert isinstance(rules, list)
    return rules


def _redact_tags(rule: dict[str, Any]) -> list[str]:
    return [t for t in rule.get("tags", []) if t.startswith("redact:")]


def _allowlist(rule: dict[str, Any]) -> list[re.Pattern[str]]:
    return [re.compile(rx) for block in rule.get("allowlists", []) for rx in block.get("regexes", [])]


def test_fr33_rule_file_exists() -> None:
    assert RULE_FILE.is_file()


def test_fr33_rule_file_loads_through_agentio() -> None:
    rules = agentio.load_redaction_rules(RULE_FILE)
    assert rules.path == str(RULE_FILE)
    assert len(rules.rules) == 18
    assert set(rules.ids()) == FR33_IDS
    assert len(rules.ids()) == 18


def test_fr33_loaded_types_match_the_tags() -> None:
    rules = agentio.load_redaction_rules(RULE_FILE)
    by_id = {r.id: r.type for r in rules.rules}
    for raw in _rules():
        assert by_id[raw["id"]] == _redact_tags(raw)[0].removeprefix("redact:")


def test_fr33_eighteen_rules_with_unique_ids_named_by_the_spec() -> None:
    ids = [r["id"] for r in _rules()]
    assert len(ids) == 18
    assert len(set(ids)) == 18
    assert set(ids) == FR33_IDS


def test_fr33_every_rule_has_exactly_one_redact_tag_of_a_rule15_type() -> None:
    for rule in _rules():
        tags = _redact_tags(rule)
        assert len(tags) == 1, rule["id"]
        assert tags[0].removeprefix("redact:") in RULE15_TYPES, rule["id"]


def test_fr33_rule15_types_are_agentios() -> None:
    assert agentio.REDACTION_TYPES == RULE15_TYPES


def test_fr33_extends_gitleaks_defaults() -> None:
    assert _doc()["extend"]["useDefault"] is True


def test_fr34_no_generic_entropy_rule() -> None:
    assert "generic-api-key" not in {r["id"] for r in _rules()}


@pytest.mark.parametrize(
    ("rule_id", "kind"),
    [
        ("private-key", "key"),
        ("aws-access-token", "credential"),
        ("stripe-access-token", "secret"),
        ("github-pat", "token"),
        ("jwt", "token"),
        ("anthropic-api-key", "key"),
    ],
)
def test_fr33_rule_types(rule_id: str, kind: str) -> None:
    rule = next(r for r in _rules() if r["id"] == rule_id)
    assert _redact_tags(rule) == [f"redact:{kind}"]


def test_fr33_every_regex_and_allowlist_regex_compiles_under_python_re() -> None:
    for rule in _rules():
        re.compile(rule["regex"])
        _allowlist(rule)


def test_fr35_every_rule_has_lower_case_keywords() -> None:
    # gitleaks' keyword prefilter is a lower-cased substring test; a rule with none would never apply
    for rule in _rules():
        assert rule.get("keywords"), rule["id"]
        assert all(k == k.lower() for k in rule["keywords"]), rule["id"]


def test_fr33_file_carries_no_secret_of_its_own() -> None:
    """No line matches a rule, except a value the same rule allowlists (gitleaks' own example keys)."""
    rules = [(r["id"], re.compile(r["regex"]), _allowlist(r)) for r in _rules()]
    text = RULE_FILE.read_text(encoding="utf-8")
    found: list[str] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for rule_id, rx, allow in rules:
            for m in rx.finditer(line):
                secret = next((g for g in m.groups() if g), m.group(0))
                if not any(a.search(secret) for a in allow):
                    found.append(f"line {lineno}: {rule_id}")
    assert found == []
    # and the whole file, so a pasted multi-line value (a private key) is caught too
    for rule_id, rx, allow in rules:
        for m in rx.finditer(text):
            secret = next((g for g in m.groups() if g), m.group(0))
            assert any(a.search(secret) for a in allow), rule_id
