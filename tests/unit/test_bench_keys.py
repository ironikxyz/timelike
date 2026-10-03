"""benchlib.keys: the API-key refusal rule for fake-agent runs (feature 002, FR-12; research RB9).

The name table is built from EVERY name case in tests/host/test_shell_env_hook.sh, with the verdict
that lane expects of image/rootfs/etc/timelike/shell-env.bash (F002), so the two rules cannot drift
apart silently. The only deliberate differences are marked where they occur: no TIMELIKE_ENV_ALLOW
bypass, and names that are not shell identifiers are judged too.
"""

from __future__ import annotations

import pytest
from benchlib.keys import env_list_to_mapping, is_key_shaped, key_shaped

# tests/host/test_shell_env_hook.sh SECRETS (case S1): stripped there, key-shaped here.
HOOK_SECRETS = [
    "GITHUB_TOKEN",
    "MY_API_KEY",
    "DB_PASSWORD",
    "npm_config__authToken",
    "AWS_SECRET_ACCESS_KEY",
    "deploy_passphrase",
    "SMTP_PASS",
    "SERVICE_CREDENTIALS",
    "OPENAI_APIKEY",
    "PRIVATEKEY",
    "SSH_PASSWD",
    "X_TOKENS",
    "Y_SECRETS",
    "Z_PASSWORDS",
    "a_credential",
    "K_KEYS",
    "ACCESSKEY",
    "AUTHTOKEN",
    "_KEY",
    "Api__Key",
    "PGPASSWORD",
    "GHTOKEN",
    "OAUTH_CLIENTSECRET",
    # case Q4 / Q1 inputs, stripped by the hook
    "A_KEY",
    # cases S3/S4: D_TOKEN is stripped there; A_TOKEN, B_KEY and C_SECRET are KEPT there only because
    # TIMELIKE_ENV_ALLOW lists them (S3), and B_TOKEN / A_TOKEN are stripped under a non-matching
    # allow-list (S4). A fake-agent run honours no allow-list, so all of them are key-shaped here.
    "D_TOKEN",
    "A_TOKEN",
    "B_KEY",
    "C_SECRET",
    "B_TOKEN",
]

# tests/host/test_shell_env_hook.sh LOOKALIKES (case S2): kept there, not key-shaped here.
HOOK_LOOKALIKES = [
    "GIT_ASKPASS",
    "SSH_ASKPASS",
    "TOKENIZERS_PARALLELISM",
    "KEYBOARD_LAYOUT",
    "MONKEY",
    "PASSAGE_COUNT",
    "KEYTIMEOUT",
    "GIT_CONFIG_KEY_0",
    "GIT_CONFIG_KEY_12",
    "TIMELIKE_ENV_ALLOW",
]

# Every other variable name the host lane passes through the hook and expects to survive
# (C/E job counts, S5's git layer, the harness's own variables).
HOOK_KEPT_OTHER = [
    "TIMELIKE_CPUS",
    "MAKEFLAGS",
    "CMAKE_BUILD_PARALLEL_LEVEL",
    "CARGO_BUILD_JOBS",
    "GOMAXPROCS",
    "PYTEST_XDIST_AUTO_NUM_WORKERS",
    "PYTHON_CPU_COUNT",
    "GIT_CONFIG_COUNT",
    "GIT_CONFIG_VALUE_0",
    "GIT_CONFIG_SYSTEM",
    "GIT_CONFIG_GLOBAL",
    "TIMELIKE_CGROUP_CPU_MAX",
    "TIMELIKE_PROC_STATUS",
    "BASH_ENV",
    "HOOK",
    "PATH",
    "HOME",
]

# FR-12's own targets and the task's additions.
AGENT_KEYS = ["ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN", "OPENAI_API_KEY"]
LOWERCASE_KEYS = [
    "anthropic_api_key",
    "anthropic_auth_token",
    "claude_code_oauth_token",
    "openai_api_key",
    "Anthropic_Api_Key",
    "github_token",
    "pgpassword",
    # The GIT_CONFIG_KEY_<n> exemption is exact-case, as in the hook's `=~ ^GIT_CONFIG_KEY_[0-9]+$`.
    "git_config_key_0",
    "Git_Config_Key_0",
]
NOT_KEYS = [
    "MONKEY",
    "KEYBOARD",
    "PATH",
    "HOME",
    "TIMELIKE_CPUS",
    "monkey",
    "keyboard",
    "path",
    "HOTKEY",  # the key family is whole-component only (review of T050, per the hook's comment)
    # the hook's documented Limits: secret to a person, but outside the criterion's patterns
    "SSHPASS",
    "MYSQL_PWD",
    "GITHUB_PAT",
    "",
]
# The exemption needs a decimal index and nothing after it.
GIT_CONFIG_NEAR_MISSES = ["GIT_CONFIG_KEY_", "GIT_CONFIG_KEY_X", "GIT_CONFIG_KEY_0_", "GIT_CONFIG_KEY_0\n"]

CASES = (
    [(name, True) for name in HOOK_SECRETS]
    + [(name, False) for name in HOOK_LOOKALIKES]
    + [(name, False) for name in HOOK_KEPT_OTHER]
    + [(name, True) for name in AGENT_KEYS]
    + [(name, True) for name in LOWERCASE_KEYS]
    + [(name, False) for name in NOT_KEYS]
    + [(name, True) for name in GIT_CONFIG_NEAR_MISSES]
    # Not a shell identifier: bash cannot unset it, so the hook passes it on; the refusal judges it.
    + [("MY-TOKEN", True), ("MY-KEY", False)]
)


@pytest.mark.parametrize(("name", "expected"), CASES, ids=[repr(n) for n, _ in CASES])
def test_is_key_shaped(name: str, expected: bool) -> None:
    assert is_key_shaped(name) is expected


def test_no_allow_list_bypass() -> None:
    env = {"TIMELIKE_ENV_ALLOW": "ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY": "x"}
    assert key_shaped(env) == ["ANTHROPIC_API_KEY"]


def test_key_shaped_sorted_names_only() -> None:
    env = {
        "PATH": "/usr/bin",
        "OPENAI_API_KEY": "sk-a",
        "ANTHROPIC_AUTH_TOKEN": "t",
        "MONKEY": "1",
        "CLAUDE_CODE_OAUTH_TOKEN": "o",
        "ANTHROPIC_API_KEY": "sk-b",
        "GIT_CONFIG_KEY_0": "core.hooksPath",
    }
    assert key_shaped(env) == [
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_AUTH_TOKEN",
        "CLAUDE_CODE_OAUTH_TOKEN",
        "OPENAI_API_KEY",
    ]


def test_key_shaped_empty_and_clean() -> None:
    assert key_shaped({}) == []
    assert key_shaped({"PATH": "/bin", "HOME": "/root", "TIMELIKE_CPUS": "2"}) == []


def test_key_shaped_empty_value_still_counts() -> None:
    # Presence is what FR-12 refuses; an empty value is still a present variable.
    assert key_shaped({"ANTHROPIC_API_KEY": ""}) == ["ANTHROPIC_API_KEY"]


def test_env_list_to_mapping() -> None:
    items = ["PATH=/usr/bin:/bin", "OPTS=a=b=c", "BARE", "EMPTY=", "=weird", "DUP=1", "DUP=2"]
    assert env_list_to_mapping(items) == {
        "PATH": "/usr/bin:/bin",
        "OPTS": "a=b=c",
        "BARE": "",
        "EMPTY": "",
        "": "weird",
        "DUP": "2",
    }


def test_env_list_to_mapping_empty_and_generator() -> None:
    assert env_list_to_mapping([]) == {}
    assert env_list_to_mapping(s for s in ("A=1",)) == {"A": "1"}


def test_config_env_round_trip() -> None:
    env = env_list_to_mapping(["PATH=/bin", "ANTHROPIC_API_KEY=sk-x=y", "HF_TOKEN"])
    assert key_shaped(env) == ["ANTHROPIC_API_KEY", "HF_TOKEN"]
