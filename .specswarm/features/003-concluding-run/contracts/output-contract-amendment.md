# Amendment to 001's output contract — discovery revision 9 (carried by 003)

Applied to `.specswarm/features/001-agent-shell-baseline/contracts/` in this cycle (spec FR-20–FR-24).
001's spec is not edited and its `audited_against` does not move here.

| File | Change |
|---|---|
| `output-contract.md` § Exit codes | Add: the vocabulary is a tool's **own** outcomes. A tool that runs a command the agent named passes that command's exit through (126, 127, 128+n included), 124 only when its own limit fired, and declares `"passes_exit": true`. Its verdict and JSON `cause` (`command`, `timeout`, `usage`, `internal`, open) and `command_exit` (int or null) tell the two apart. No 125. Line 36 kept. |
| `output-contract.md` line 83 | "The exit code is always one of those listed under *Exit codes*" → "…is one of those listed, or — for a tool that declares pass-through — the command's own exit, with `cause: command`" |
| `agent-info.schema.json` | Optional `passes_exit: boolean`; `exit_codes` unchanged (own outcomes) |
| `event.schema.json` | `exit`: integer 0–255 (was the six-code enum); description says a non-vocabulary value is valid only from a pass-through tool, and C7 checks that |
| `conformance.md` C6 | Tools declaring `passes_exit` are also run as `<tool> --json sh -c 'exit 42'`: exit 42, `command_exit` 42, `cause` `command`, verdict names 42. Every other observed exit stays in the six. C7 for that call: event `exit` 42 |
| `agentio.py` | `Tool(passes_exit=…)`, manifest key; `Result(cause=…, command_exit=…)`; `_emit_result` admits exit ∉ vocabulary only when the tool passes exit, cause is `command` and exit == command_exit; `Tool.codes()` unchanged; argv split for pass-through tools (research R6); tool-supplied cut (sections + more) for tools that cut their own output |
