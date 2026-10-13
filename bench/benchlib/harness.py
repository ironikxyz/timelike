"""harness — the two live harnesses: where each is, how it is asked its version, how it runs (FR-21 to 28).

A live harness runs **inside the task container**, as `agent`, in the task directory, so its tool calls run
where the agent's would (FR-24). Its binary is mounted read-only at `/opt/bench-harness` from the harness
container; neither image under test carries it. Every arm runs the same harness the same way.

Configuration goes in at exec time and nothing is written into the task directory (FR-28):
- **OpenCode 1.19.0** through `OPENCODE_CONFIG_CONTENT`: provider `openrouter` at the relay, the key read
  from the environment, `model` and `small_model` both the pin, every permission allowed, sharing and
  autoupdate off; `--pure`, `--format json`, and the switches that stop its own fetches (research RB13);
- **Codex CLI 0.162.1** through `-c` overrides: provider `openrouter` at the relay over the Responses API
  (its config refuses `wire_api = "chat"`), `env_key`, the hosted web search off, analytics and the update
  check off; `--strict-config`, `--json`, `--skip-git-repo-check`, and
  `--dangerously-bypass-approvals-and-sandbox`, because the task container is the sandbox, which is the case
  that flag is for.

The key's variable is passed to the harness exec by name only (FR-30); its value never appears here.
Each harness writes its transcript where the runner collects it: stdout to `~/.bench/stdout.jsonl`, stderr to
`~/.bench/stderr.txt`, and Codex's own rollout under `$CODEX_HOME/sessions`. Stdlib only (constitution H5).
"""

from __future__ import annotations

import json
import shlex
from collections.abc import Callable
from dataclasses import dataclass

from benchlib import transcripts

MOUNT = "/opt/bench-harness"
HOME = "/home/agent"
CODEX_HOME = f"{HOME}/.codex"
OUT_DIR = f"{HOME}/.bench"
STDOUT = f"{OUT_DIR}/stdout.jsonl"
STDERR = f"{OUT_DIR}/stderr.txt"
KEY_VAR = "OPENROUTER_API_KEY"
PROMPT_TAIL = "You are in {dir}. Work there with your shell tool until the task is done."


@dataclass(frozen=True)
class HarnessSpec:
    name: str
    version: str  # the pin (pins.env)
    binary: str
    invocation: str
    call_limit_s: int  # the harness's own per-call limit, as recorded (identity.call_limit_s)
    version_argv: tuple[str, ...]
    _env: Callable[[str, str], dict[str, str]]
    _argv: Callable[[str, str, str], list[str]]
    _parse: Callable[[dict[str, str]], transcripts.Parsed]

    def exec_env(self, relay_url: str, model: str) -> dict[str, str]:
        """Variables set inside the harness exec (not secrets: they are on its argv)."""
        return {"HOME": HOME, "CODEX_HOME": CODEX_HOME, **self._env(relay_url, model)}

    def command(self, relay_url: str, model: str, prompt: str) -> str:
        """The bash command the wrapper runs: the harness, its output to files the runner collects."""
        argv = " ".join(shlex.quote(a) for a in self._argv(relay_url, model, prompt))
        return f"mkdir -p {OUT_DIR} && {argv} </dev/null >{STDOUT} 2>{STDERR}"

    def parse(self, files: dict[str, str]) -> transcripts.Parsed:
        return self._parse(files)

    def reported(self, version_output: str) -> str:
        """The version the binary printed: `codex-cli 0.162.1` and `1.19.0` both give the number."""
        words = version_output.strip().split()
        return words[-1] if words else ""


def opencode_config(relay_url: str, model: str) -> str:
    provider = {"options": {"baseURL": relay_url, "apiKey": "{env:" + KEY_VAR + "}"}, "models": {model: {}}}
    return json.dumps(
        {
            "$schema": "https://opencode.ai/config.json",
            "provider": {"openrouter": provider},
            "model": f"openrouter/{model}",
            "small_model": f"openrouter/{model}",
            "permission": {"*": "allow"},
            "share": "disabled",
            "autoupdate": False,
        },
        sort_keys=True,
    )


def _opencode_env(relay_url: str, model: str) -> dict[str, str]:
    return {
        "OPENCODE_CONFIG_CONTENT": opencode_config(relay_url, model),
        "OPENCODE_DISABLE_MODELS_FETCH": "1",
        "OPENCODE_DISABLE_DEFAULT_PLUGINS": "1",
        "OPENCODE_DISABLE_LSP_DOWNLOAD": "1",
        "OPENCODE_DISABLE_CLAUDE_CODE": "1",
        "OPENCODE_DISABLE_SHARE": "1",
        "OPENCODE_DISABLE_AUTOUPDATE": "1",
    }


def _opencode_argv(relay_url: str, model: str, prompt: str) -> list[str]:
    return [f"{MOUNT}/opencode/bin/opencode", "run", "--pure", "--format", "json", prompt]


def codex_overrides(relay_url: str, model: str) -> list[str]:
    provider = f'{{name="OpenRouter", base_url="{relay_url}", env_key="{KEY_VAR}", wire_api="responses"}}'
    overrides = [
        f'model="{model}"',
        'model_provider="openrouter"',
        f"model_providers.openrouter={provider}",
        'web_search="disabled"',
        "analytics.enabled=false",
        "check_for_update_on_startup=false",
    ]
    return [arg for o in overrides for arg in ("-c", o)]


def _codex_argv(relay_url: str, model: str, prompt: str) -> list[str]:
    return [
        f"{MOUNT}/codex/bin/codex", "exec", "--json", "--strict-config", "--skip-git-repo-check",
        "--dangerously-bypass-approvals-and-sandbox", *codex_overrides(relay_url, model), prompt,
    ]  # fmt: skip


def _parse_opencode(files: dict[str, str]) -> transcripts.Parsed:
    return transcripts.parse_opencode(files.get("stdout", ""))


def _parse_codex(files: dict[str, str]) -> transcripts.Parsed:
    return transcripts.parse_codex(files.get("rollout", ""), files.get("stdout", ""))


def specs(opencode_version: str, codex_version: str) -> dict[str, HarnessSpec]:
    return {
        "opencode": HarnessSpec(
            name="opencode",
            version=opencode_version,
            binary=f"{MOUNT}/opencode/bin/opencode",
            invocation="opencode bash tool",
            call_limit_s=120,  # OpenCode 1.19.0's own bash limit, as its transcript reported it (T041)
            version_argv=(f"{MOUNT}/opencode/bin/opencode", "--version"),
            _env=_opencode_env,
            _argv=_opencode_argv,
            _parse=_parse_opencode,
        ),
        "codex": HarnessSpec(
            name="codex",
            version=codex_version,
            binary=f"{MOUNT}/codex/bin/codex",
            invocation="codex exec_command",
            call_limit_s=0,  # no per-call limit observed; the runner records the run limit in its place
            version_argv=(f"{MOUNT}/codex/bin/codex", "--version"),
            _env=lambda relay_url, model: {},
            _argv=_codex_argv,
            _parse=_parse_codex,
        ),
    }


def prompt_for(goal: str, directory: str) -> str:
    return f"{goal}\n\n{PROMPT_TAIL.format(dir=directory)}"


# The Codex rollout is the newest file under $CODEX_HOME/sessions; a fresh container has no other.
_NEWEST = f"ls -1t {CODEX_HOME}/sessions/*/*/*/rollout-*.jsonl 2>/dev/null | head -n 1"
ROLLOUT_CMD = ("sh", "-c", f'f=$({_NEWEST}); test -n "$f" && cat "$f"')
