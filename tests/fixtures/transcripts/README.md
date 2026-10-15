# Recorded harness transcripts (feature 002 slice 1, T041; spec FR-46)

The live harnesses' parsers (`bench/benchlib/transcripts.py`) are tested on these files. Each is what a pinned
harness wrote while it drove timelike's model stand-in through the bench's own relay. It is not output the bench
produced (cross-stack P005, lore `llm-apis` Q001).

**How they were made:** `record.py` in this directory, run on 2026-10-13 on the code instance's host (Linux
x86_64), with no key, and every request but loopback sent to a dead proxy port:

    python3 -I record.py <opencode> <codex> <scratch dir> tests/fixtures/transcripts

**The harnesses** came from the npm registry, each checked against the registry's own `sha512` integrity
before it ran:

| Harness | Package | Integrity |
|---|---|---|
| OpenCode 1.19.0 | `opencode-linux-x64@1.19.0` | `sha512-+UFxn2AbOqKEISBDqrWk5nHsZrPWBMVZ4H9R7tbnrt1+nYvEGejpg9tyt+QMrpBPYZP7F+D3Ym0vZbZcF7gSSw==` |
| Codex CLI 0.162.1 | `@openai/codex@0.162.1-linux-x64` | `sha512-cjK2mdHIfEepZ1lQ1MX3aTQC+8ncIsvnacl/6vI2dIIcfP8/MrhTQ2+qRlkXFNDzJSj1d36quIszP+3/4CUJWQ==` |

**What was changed after recording:** one thing only. The scratch directory's absolute paths were rewritten to
the paths the bench uses in a task container: the work directory to `/home/agent/task`, and the harness's home
to `/home/agent`. Nothing else was edited.

**Files**, per harness and scenario:
- `<harness>--<scenario>.stdout.jsonl`: OpenCode's `run --format json` events, or Codex's `exec --json` events;
- `<harness>--<scenario>.stderr.txt`;
- `<harness>--<scenario>.meta.json`: the harness's exit code, the relay's accounting, and the stand-in's
  script;
- `codex--<scenario>.rollout.jsonl`: Codex's session rollout file, which is what the parser reads, because it
  marks each model response.

**Scenarios:**
- `pass`: two commands that succeed.
- `failures`: one real failing command per category this host could produce without limits.
- `turn-cap`: the relay's turn cap at 1.
- `rate-limit`: the stand-in answers 429 three times.

**What the recordings showed** (beyond the shapes the parsers read):
- **Both harnesses stop on the relay's cap.** Each exits 1 at the cap's HTTP 400 and sends nothing more.
- **A 429:** OpenCode retried three 429s and finished. Codex stopped at the first 429, with `exceeded retry
  limit, last status: 429 Too Many Requests`, and exit 1.
- **A killed shell:** for `bash -c 'kill -KILL $$'`, OpenCode waited out its own 120 s call limit and reported
  `shell tool terminated command after exceeding timeout 120000 ms`, with `exit: null`. Codex reported exit 137
  at once.
- **The dead proxy reached git too.** Its DNS-failure probe printed `Failed to connect to 127.0.0.1 port 9`.
  In a task container with no network, the same probe prints `Could not resolve host`. Both are network
  denial.
