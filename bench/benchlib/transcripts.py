"""transcripts — reading a live harness's own record of a run (spec FR-44; research RB17).

Each harness reports its tool calls its own way. The bench reads turns, calls, commands, exit codes and output
sizes from what the harness wrote, never from the model's words:

- **OpenCode** (`run --format json`): one JSON event per line. `step_start` opens a model response (a turn);
  `tool_use` carries a call (`part.tool`, `part.state.input.command`, `.output`, `.metadata.exit`, `.time`);
  `step_finish` carries the response's tokens. Its `cost` is OpenCode's own price-table figure, so it is not
  read: spend is OpenRouter's (FR-35), read by the relay.
- **Codex CLI** (the session rollout file, `$CODEX_HOME/sessions/…/rollout-*.jsonl`): a `function_call`
  response item per call, a `token_usage_record` closing each model response, and an `item_completed`
  `CommandExecution` with `exit_code`, `aggregated_output` and `duration`. `exec --json` on stdout has no
  response boundaries, so it is read only for the errors the harness reported.

Both report a call's output with stdout and stderr merged (Assumption 11); the merged head is what a trace
keeps. A call the harness ended on its own limit is recorded as hung (OpenCode says so in the output it hands
the model). An exit code the harness did not report is -1, never 0.

Live output carries decorations a stand-in never produces (llm-apis Q001): unknown event types are skipped,
and only the fields named above are relied on. What cannot be read raises `TranscriptUnreadable`, naming what
failed; it is never scored as zero calls. Stdlib only (constitution H5).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from benchlib.categories import HARNESS_TIMEOUTS

NO_EXIT = -1  # the harness reported no exit code
OUTPUT_KEEP = 4096  # characters of a call's merged output kept, as the fake path keeps a head


class TranscriptUnreadable(ValueError):
    """The harness's own record could not be read. The message says what, in one line."""


@dataclass(frozen=True)
class ParsedCall:
    turn: int
    command: str
    exit_code: int
    hung: bool
    output: str  # the merged head, at most OUTPUT_KEEP characters
    output_bytes: int  # the whole output's size, as the harness reported it
    passed_bytes: int  # what the harness handed the model
    duration_ms: int


@dataclass(frozen=True)
class Parsed:
    calls: tuple[ParsedCall, ...]
    turns: int  # model responses the harness recorded
    tokens_in: int | None
    tokens_out: int | None
    final_text: str
    errors: tuple[str, ...] = field(default_factory=tuple)  # what the harness itself reported as an error


def _lines(text: str, what: str) -> list[dict[str, Any]]:
    if not text.strip():
        raise TranscriptUnreadable(f"{what} is empty")
    docs: list[dict[str, Any]] = []
    for n, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            doc = json.loads(line)
        except json.JSONDecodeError as e:
            raise TranscriptUnreadable(f"{what} line {n} is not JSON ({e.msg})") from None
        if not isinstance(doc, dict):
            raise TranscriptUnreadable(f"{what} line {n} is not a JSON object")
        docs.append(doc)
    return docs


def _obj(doc: Any, key: str) -> dict[str, Any]:
    """`doc[key]` when it is an object, else an empty one: a decoration or a gap never raises here."""
    value = doc.get(key) if isinstance(doc, dict) else None
    return value if isinstance(value, dict) else {}


def _int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _call(
    turn: int, command: str, exit_code: Any, output: str, full: str | None, duration_ms: int
) -> ParsedCall:
    code = _int(exit_code)
    hung = any(s in output for s in HARNESS_TIMEOUTS)
    total = len((full if full is not None else output).encode())
    return ParsedCall(
        turn=turn,
        command=command,
        exit_code=NO_EXIT if code is None else code,
        hung=hung,
        output=output[:OUTPUT_KEEP],
        output_bytes=total,
        passed_bytes=min(len(output.encode()), total),
        duration_ms=max(0, duration_ms),
    )


# --- OpenCode ------------------------------------------------------------------------------------


def parse_opencode(stdout: str) -> Parsed:
    events = _lines(stdout, "opencode's --format json output")
    calls: list[ParsedCall] = []
    turns = 0
    tin = tout = 0
    saw_tokens = False
    final = ""
    errors: list[str] = []
    for ev in events:
        kind = ev.get("type")
        part = _obj(ev, "part")
        if kind == "step_start":
            turns += 1
        elif kind == "tool_use":
            if turns == 0:
                raise TranscriptUnreadable("opencode reported a tool call before any step_start")
            state = part.get("state")
            if not isinstance(state, dict):
                raise TranscriptUnreadable(f"opencode tool_use without a state (call {len(calls) + 1})")
            tool = str(part.get("tool") or "?")
            inputs = _obj(state, "input")
            meta = _obj(state, "metadata")
            times = _obj(state, "time")
            duration = (_int(times.get("end")) or 0) - (_int(times.get("start")) or 0)
            if tool == "bash":
                command = inputs.get("command")
                if not isinstance(command, str):
                    raise TranscriptUnreadable(f"opencode bash call {len(calls) + 1} has no command")
                output = str(state.get("output") or state.get("error") or "")
                full = meta.get("output") if isinstance(meta.get("output"), str) else None
                exit_code: Any = meta.get("exit")
                if state.get("status") == "error" and _int(exit_code) is None:
                    exit_code = NO_EXIT
                calls.append(_call(turns, command, exit_code, output, full, duration))
            else:
                # Not a shell command: a tool call all the same (a read, an edit), counted with its outcome.
                failed = state.get("status") == "error"
                title = str(state.get("title") or "").strip()
                output = str(state.get("error") or "") if failed else ""
                code = 1 if failed else 0
                calls.append(_call(turns, f"[{tool}] {title}".rstrip(), code, output, None, duration))
        elif kind == "step_finish":
            tokens = _obj(part, "tokens")
            if _int(tokens.get("input")) is not None and _int(tokens.get("output")) is not None:
                tin += tokens["input"]
                tout += tokens["output"]
                saw_tokens = True
        elif kind == "text":
            final = str(part.get("text") or final)
        elif kind == "error":
            err = ev.get("error")
            msg = err.get("data", err).get("message") if isinstance(err, dict) else err
            errors.append(str(msg or ev.get("message") or "error"))
    if turns == 0 and not errors:
        raise TranscriptUnreadable("opencode's output has no step_start and no error: no model response")
    return Parsed(
        calls=tuple(calls),
        turns=turns,
        tokens_in=tin if saw_tokens else None,
        tokens_out=tout if saw_tokens else None,
        final_text=final,
        errors=tuple(errors),
    )


# --- Codex CLI -----------------------------------------------------------------------------------

_CODEX_SHELLS = ("exec_command", "shell", "shell_command", "local_shell")


def _codex_command(name: str, arguments: Any) -> str:
    try:
        args = json.loads(arguments) if isinstance(arguments, str) else arguments
    except json.JSONDecodeError:
        args = None
    if name in _CODEX_SHELLS and isinstance(args, dict):
        cmd = args.get("cmd", args.get("command"))
        if isinstance(cmd, list) and len(cmd) >= 3 and cmd[1] in ("-c", "-lc"):
            return str(cmd[-1])
        if isinstance(cmd, str):
            return cmd
        if isinstance(cmd, list):
            return " ".join(str(c) for c in cmd)
    summary = json.dumps(args, sort_keys=True)[:80] if args is not None else ""
    return f"[{name}] {summary}".rstrip()


def parse_codex(rollout: str, stdout: str = "") -> Parsed:
    records = _lines(rollout, "codex's rollout file")
    order: list[str] = []  # call ids, in the order the model asked for them
    asked: dict[str, tuple[int, str, str]] = {}  # call id -> (turn, name, command)
    done: dict[str, tuple[Any, str, int]] = {}  # call id -> (exit, output, duration ms)
    outputs: dict[str, str] = {}  # call id -> what the harness handed the model
    responses = 0
    tin = tout = 0
    saw_tokens = False
    final = ""
    for rec in records:
        kind = rec.get("type")
        p = _obj(rec, "payload")
        if kind == "token_usage_record":
            responses += 1
            usage = _obj(p, "usage")
            if _int(usage.get("input_tokens")) is not None and _int(usage.get("output_tokens")) is not None:
                tin += usage["input_tokens"]
                tout += usage["output_tokens"]
                saw_tokens = True
        elif kind == "response_item" and p.get("type") == "function_call":
            call_id = str(p.get("call_id") or "")
            if not call_id:
                raise TranscriptUnreadable(f"codex function_call without a call_id (call {len(order) + 1})")
            name = str(p.get("name") or "?")
            order.append(call_id)
            asked[call_id] = (responses + 1, name, _codex_command(name, p.get("arguments")))
        elif kind == "response_item" and p.get("type") == "function_call_output":
            outputs[str(p.get("call_id") or "")] = str(p.get("output") or "")
        elif kind == "response_item" and p.get("type") == "message" and p.get("role") == "assistant":
            for c in p.get("content") or []:
                if isinstance(c, dict) and c.get("type") == "output_text":
                    final = str(c.get("text") or final)
        elif kind == "event_msg" and p.get("type") == "item_completed":
            item = _obj(p, "item")
            if item.get("type") == "CommandExecution":
                d = _obj(item, "duration")
                ms = (_int(d.get("secs")) or 0) * 1000 + (_int(d.get("nanos")) or 0) // 1_000_000
                done[str(item.get("id") or "")] = (
                    item.get("exit_code"),
                    str(item.get("aggregated_output") or ""),
                    ms,
                )
    errors = _codex_errors(stdout)
    if responses == 0 and not order and not errors:
        raise TranscriptUnreadable("codex's rollout has no model response, no call and no error")
    calls: list[ParsedCall] = []
    for call_id in order:
        turn, name, command = asked[call_id]
        if call_id in done:
            exit_code, output, ms = done[call_id]
            calls.append(_call(turn, command, exit_code, output, None, ms))
        elif name in _CODEX_SHELLS:
            # Asked and never completed: the run ended while it ran (the run limit), or Codex dropped it.
            calls.append(_call(turn, command, None, outputs.get(call_id, ""), None, 0))
        else:
            out = outputs.get(call_id, "")
            calls.append(_call(turn, command, 0, out, None, 0))
    return Parsed(
        calls=tuple(calls),
        turns=responses,
        tokens_in=tin if saw_tokens else None,
        tokens_out=tout if saw_tokens else None,
        final_text=final,
        errors=errors,
    )


def _codex_errors(stdout: str) -> tuple[str, ...]:
    errors: list[str] = []
    for line in stdout.splitlines():
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(ev, dict) and ev.get("type") == "error":
            errors.append(str(ev.get("message") or "error"))
    return tuple(errors)
