# `timelike-conform` — the conformance check (SC-5)

This check is itself a timelike tool and is bound by the contract. It verifies every timelike tool on
PATH against `output-contract.md`, and fails naming each tool and each rule broken.

## Which tools are checked

Every executable file in a directory listed in `TIMELIKE_BIN_DIRS` (colon-separated, default
`/opt/timelike/bin`) that is **also on PATH**. `timelike-conform` checks itself too.

A directory in `TIMELIKE_BIN_DIRS` that is not on PATH is reported, not silently skipped: a tool the
agent cannot find does not exist (P3). The negative test adds a fixture directory holding a
deliberately broken tool to both variables, and expects failure.

## Checks per tool

Every probe run:
- has stdin at `/dev/null`
- has no controlling terminal (`setsid`)
- has a fresh session id
- is limited to 10 s. Exceeding that is itself a failure ("did not conclude"), because P2 applies to
  the checker too

| # | Check | Passes when | Rule |
|---|---|---|---|
| C1 | help | `--help` exits 0, prints ≤ 40 lines, and line 1 matches the text header regex | 6, 12 |
| C2 | agent-info | `--agent-info` exits 0 and prints JSON valid against `agent-info.schema.json`. `exit_codes` keys are all in the vocabulary. `flags` include the required set. **Confirmation scope (discovery revision 13; added in feature 008):** `--yes` is in `flags` exactly when the tool confirms (`confirm_protocol`, or `mutating` when absent); `confirm_protocol: true` needs `mutating: true`; `dry_run`, when present, agrees with `--dry-run` in `flags`; and a mutating tool with `confirm_protocol: false` declares `dry_run: true` with `--dry-run` (rule 8). Each case is shown failing in `tests/unit/test_conform_violations.py` (`rule9_*`) | 6, 5, 8, 9 |
| C3 | json | `--json <probe>` exits in the vocabulary. stdout is one JSON object whose first keys are `tool`, `target`, `scope`, and `tool` equals the file name | 1, 12 |
| C4 | text | `--text <probe>` exits in the vocabulary, and line 1 matches the text header regex | 1, 12 |
| C5 | usage | `--no-such-flag-conform` exits **2**. With `--json`, stderr is one JSON object valid against `error.schema.json`. Without it, stderr matches `^error: .+ \(code 2\) — .+` | 5, 14 |
| C6 | exit vocabulary | Every exit code observed in C1–C5 is in {0, 1, 2, 3, 4, 124}. **A tool whose manifest declares `passes_exit`** (discovery revision 9) is also run as `<tool> --json sh -c 'exit 42'`: its exit must be 42, its JSON `command_exit` 42 and `cause` `command`, and its verdict must name 42. That probe's exit is the command's, so it is the one observed exit allowed outside the six. A probe that only ever exits 0 cannot pass a pass-through tool | 5 |
| C7 | events | Each of the invocations above appended **exactly one** line to the probe session's `events.jsonl`, valid against `event.schema.json`, with a matching `tool` and `exit` . The pass-through probe's event records `exit` 42 | 16 |
| C8 | no ANSI | No output from C1–C5 contains an ESC byte | 13 |
| C9 | envelopes | **Every exit 4 observed above** (discovery revision 10; added in feature 004) prints one JSON envelope whose `status` is `confirmation_required` or `grant_required`, which the manifest declares in `envelopes` (absent: `confirmation_required` if the tool confirms), with that status's required keys and `tool`, `target`, `scope` first. A grant envelope has `limit {name, allowed, needed}`, `extend_by: "operator"`, `performed: false` and **no `confirm`**. **No envelope's `confirm` may name a command outside the tool's own**: its first word is the tool, and no shell control operator (`;`, `&&`, `|` …) chains a second command. C2 also checks that `envelopes` lists `confirmation_required` exactly when the tool confirms (revision 13). Every case is shown failing in `tests/unit/test_conform_violations.py` | 9 |

## Output

- **Verdict:** `pass` or `fail`, with counts of tools checked and failures. Failures are sorted by tool
  and then by check (rule 11).
- **Exit codes:**
  - 0: every tool passes
  - 1: any failure, including zero tools found (an empty PATH directory is not a pass)
  - 2: usage error
- **Text failure line:** `FAIL <tool> C<n> <check>: <what>`
- **JSON:** `{"tool":"timelike-conform","target":"<dirs>","scope":"conformance","verdict":...,"checked":N,"failures":[{"tool","check","rule","detail"}]}`

## Not checked here (and why)

| Rule | Why | Where it is checked |
|---|---|---|
| 2, 3 (cap and truncation order) | Needs tool-specific large output | Unit-tested in `agentio` |
| 7 (idempotence), 8, 9 (dry-run, confirm) | Only meaningful for mutating tools | Checked per tool when its manifest declares `mutating` or `destructive`. Slice 0 ships none |
| 9, provoking an envelope (discovery revision 10) | C9 judges every exit 4 it observes, but its probes are read-only and cannot provoke one: a grant refusal needs a grant to exceed and is recorded in the authority's ledger | `adele`'s envelope: `tests/unit/test_adele_cli.py` (against the schema and C9's own `check_envelope`, with its negative case) and feature 004's SC-3 e2e cells, in the image |
| 10, 15 (no daemons, redaction) | Not externally observable with a generic probe | `agentio` unit tests |
