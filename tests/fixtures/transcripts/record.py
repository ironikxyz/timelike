"""record — how tests/fixtures/transcripts/ were made (feature 002 slice 1, T041; spec FR-46).

Runs a pinned live harness on this machine against timelike's model stand-in, through the bench's own relay,
with no key and no network beyond loopback, and keeps exactly what the harness wrote: its stdout, its stderr,
its exit code and, for Codex, its session rollout file. The parsers are tested on these (P005: a fixture made
by the harness, not by the bench).

    python3 -I record.py OPENCODE_BIN CODEX_BIN WORKROOT OUTDIR

WORKROOT is an empty directory for the harnesses' homes and work directories (a scratch directory). The
recordings carry WORKROOT's absolute path; it is rewritten to the paths the bench uses in a task container
(`/home/agent/task` and `/home/agent`), and the README says so. Nothing else is changed.

Scenarios: `pass` (two commands that succeed), `failures` (one real failing command per category this host can
produce without limits), `turn-cap` (the relay's cap at 1 turn, to see how each harness takes the 400) and
`rate-limit` (the stand-in answers 429 three times, then the script).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "bench"))

from benchlib.relay import Relay  # noqa: E402
from benchlib.standin import StandIn  # noqa: E402

MODEL = "deepseek/deepseek-v4-pro-0813"
PLACEHOLDER = "recording-placeholder-not-a-key"
SCENARIOS: dict[str, tuple[str, ...]] = {
    "pass": ("mkdir -p out && printf 'hello\\n' > out/a.txt", "cat out/a.txt"),
    "failures": (
        "nosuch-bench-cmd-7f3a",
        "python3 -c 'import nosuch_bench_mod_7f3a'",
        "node -e \"require('nosuch-bench-mod-7f3a')\"",
        "timeout 1 sleep 10",
        "git ls-remote https://bench-7f3a.invalid/x.git",
        "exec 3<>/dev/tcp/127.0.0.1/9",
        "bash -c 'kill -KILL $$'",
        "ls /nonexistent-bench-7f3a",
    ),
    "turn-cap": ("echo one", "echo two", "echo three"),
    "rate-limit": ("echo after-the-429s",),
}


def opencode_env(home: Path, relay_port: int) -> dict[str, str]:
    config = {
        "$schema": "https://opencode.ai/config.json",
        "provider": {
            "openrouter": {
                "options": {
                    "baseURL": f"http://127.0.0.1:{relay_port}/api/v1",
                    "apiKey": "{env:OPENROUTER_API_KEY}",
                },
                "models": {MODEL: {}},
            }
        },
        "model": f"openrouter/{MODEL}",
        "small_model": f"openrouter/{MODEL}",
        "permission": {"*": "allow"},
        "share": "disabled",
        "autoupdate": False,
    }
    return {
        "OPENCODE_CONFIG_CONTENT": json.dumps(config),
        "OPENCODE_DISABLE_MODELS_FETCH": "1",
        "OPENCODE_DISABLE_DEFAULT_PLUGINS": "1",
        "OPENCODE_DISABLE_LSP_DOWNLOAD": "1",
        "OPENCODE_DISABLE_CLAUDE_CODE": "1",
        "OPENCODE_DISABLE_SHARE": "1",
        "OPENCODE_DISABLE_AUTOUPDATE": "1",
    }


def codex_args(relay_port: int) -> list[str]:
    base = f"http://127.0.0.1:{relay_port}/api/v1"
    provider = f'{{name="OpenRouter", base_url="{base}", env_key="OPENROUTER_API_KEY", wire_api="responses"}}'
    overrides = [
        f'model="{MODEL}"',
        'model_provider="openrouter"',
        f"model_providers.openrouter={provider}",
        'web_search="disabled"',
        "analytics.enabled=false",
        "check_for_update_on_startup=false",
    ]
    return [arg for o in overrides for arg in ("-c", o)]


def run(harness: str, binary: str, scenario: str, root: Path, out: Path) -> None:
    home, work = root / f"home-{harness}-{scenario}", root / f"work-{harness}-{scenario}"
    shutil.rmtree(home, ignore_errors=True)
    shutil.rmtree(work, ignore_errors=True)
    home.mkdir(parents=True)
    work.mkdir(parents=True)
    standin = StandIn().start()
    standin.set_script(SCENARIOS[scenario])
    standin.state.cost_per_response = 0.0
    if scenario == "rate-limit":
        standin.fail_next(429, 3, "rate limited (stand-in)")
    relay = Relay(standin.url, turn_cap=1 if scenario == "turn-cap" else 30, spend_cap_usd=10.0,
                  host="127.0.0.1", port=0).start()  # fmt: skip
    relay.begin_run()
    proxy = (
        "http://127.0.0.1:9"  # a dead port: any request but loopback fails, so nothing leaves this machine
    )
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(home),
        "CODEX_HOME": str(home / ".codex"),
        "OPENROUTER_API_KEY": PLACEHOLDER,
        "HTTP_PROXY": proxy, "HTTPS_PROXY": proxy, "http_proxy": proxy, "https_proxy": proxy,
        "NO_PROXY": "127.0.0.1", "no_proxy": "127.0.0.1",
    }  # fmt: skip
    (home / ".codex").mkdir()
    prompt = "Do the task in this directory. Run each step with your shell tool."
    if harness == "opencode":
        env.update(opencode_env(home, relay.port))
        argv = [binary, "run", "--pure", "--format", "json", prompt]
    else:
        argv = [binary, "exec", "--json", "--strict-config", "--skip-git-repo-check",
                "--dangerously-bypass-approvals-and-sandbox", *codex_args(relay.port), prompt]  # fmt: skip
    try:
        p = subprocess.run(
            argv, cwd=work, env=env, stdin=subprocess.DEVNULL, capture_output=True, timeout=180
        )
        code: int | str = p.returncode
        stdout, stderr = p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")
    except subprocess.TimeoutExpired as e:
        code = "timeout"
        stdout = (e.stdout or b"").decode("utf-8", "replace")
        stderr = (e.stderr or b"").decode("utf-8", "replace")
    acct = relay.end_run()
    relay.stop()
    standin.stop()

    def clean(text: str) -> str:
        return text.replace(str(work), "/home/agent/task").replace(str(home), "/home/agent")

    stem = out / f"{harness}--{scenario}"
    out.mkdir(parents=True, exist_ok=True)
    Path(f"{stem}.stdout.jsonl").write_text(clean(stdout))
    Path(f"{stem}.stderr.txt").write_text(clean(stderr))
    meta = {"exit": code, "relay": acct.summary(), "script": list(SCENARIOS[scenario])}
    Path(f"{stem}.meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n")
    if harness == "codex":
        rollouts = sorted((home / ".codex" / "sessions").rglob("rollout-*.jsonl"))
        if rollouts:
            Path(f"{stem}.rollout.jsonl").write_text(clean(rollouts[-1].read_text()))
    print(f"{harness} {scenario}: exit {code}, relay {acct.summary()}")


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print(__doc__, file=sys.stderr)
        return 2
    opencode, codex, root, out = argv[0], argv[1], Path(argv[2]).resolve(), Path(argv[3]).resolve()
    for scenario in SCENARIOS:
        run("opencode", opencode, scenario, root, out / "opencode")
        run("codex", codex, scenario, root, out / "codex")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
