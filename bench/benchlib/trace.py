"""trace — the bench's run record, schema version 1.

One trace per run, written by the driver only. The schema is specified in
`.specswarm/features/002-speedup-bench/contracts/trace-schema.md`; the rule numbers in the comments
below refer to it.

The trace is the only input to the report (FR-10), so everything a report or a later slice relies on
is enforced here, before a byte is written: every identity stamp is present (FR-8), totals are
derived from the calls and never counted separately, a token count is either recorded or explicitly
absent and never a zero stand-in (FR-7), and unknown keys are refused everywhere except under
`extensions` (FR-14). `write_trace` validates first, so an invalid trace never reaches disk.

Validation works on the JSON form, so a `Trace` built in memory and a file read back are judged by
the same rules. Stdlib only (constitution H5).
"""

from __future__ import annotations

import contextlib
import dataclasses
import json
import os
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
ENDING_KINDS = ("completed", "escalated", "failed", "hung")
ENVIRONMENTS = ("vanilla", "timelike")
DIGEST_MARK = "@sha256:"


class TraceInvalid(ValueError):
    """A trace broke the schema. `violations` is the full list, one human-readable line each."""

    def __init__(self, violations: Sequence[str]) -> None:
        self.violations = list(violations)
        super().__init__("invalid trace: " + "; ".join(self.violations))


@dataclass(frozen=True)
class ToolCall:
    seq: int
    turn: int
    command: str
    exit_code: int
    duration_ms: int
    hung: bool
    stdout_bytes: int
    stderr_bytes: int
    passed_bytes: int
    harness_cut: bool
    stderr_head: str


@dataclass(frozen=True)
class Identity:
    bench_revision: str
    environment: str
    image_id: str
    image_revision: str
    base_digest: str
    harness_name: str
    harness_version: str
    model_id: str
    invocation: str
    task_id: str
    task_version: int
    call_limit_s: int
    run_limit_s: int
    reproduce: str


@dataclass(frozen=True)
class Ending:
    kind: str
    reason: str


@dataclass(frozen=True)
class Tokens:
    """Either recorded with both counts, or not recorded with a reason and no counts (FR-7)."""

    recorded: bool
    reason: str | None = None
    input: int | None = None
    output: int | None = None


@dataclass(frozen=True)
class Totals:
    turns: int
    tool_calls: int
    nonzero_exits: int
    hangs: int
    wall_clock_ms: int


@dataclass(frozen=True)
class Trace:
    identity: Identity
    calls: tuple[ToolCall, ...]
    totals: Totals
    ending: Ending
    tokens: Tokens
    extensions: dict[str, Any] = field(default_factory=dict)
    schema_version: int = SCHEMA_VERSION


def derive_totals(calls: Sequence[ToolCall], wall_clock_ms: int) -> Totals:
    """Rule 2: the only way totals are made. A hung call is also a non-zero exit."""
    return Totals(
        turns=max((c.turn for c in calls), default=0),
        tool_calls=len(calls),
        nonzero_exits=sum(1 for c in calls if c.exit_code != 0),
        hangs=sum(1 for c in calls if c.hung),
        wall_clock_ms=wall_clock_ms,
    )


# --- JSON form ----------------------------------------------------------------------------------

# Field name -> JSON type, derived from the dataclasses so the two can never disagree.
_KINDS: dict[str, type] = {"str": str, "int": int, "bool": bool}


def _schema(cls: type) -> dict[str, type]:
    return {f.name: _KINDS[str(f.type)] for f in dataclasses.fields(cls)}


_CALL_FIELDS = _schema(ToolCall)
_IDENTITY_FIELDS = _schema(Identity)
_ENDING_FIELDS = _schema(Ending)
_TOTALS_FIELDS = _schema(Totals)
_TOP_LEVEL = frozenset(f.name for f in dataclasses.fields(Trace))
_IDENTITY_POSITIVE = ("task_version", "call_limit_s", "run_limit_s")  # limits and versions: > 0
_COUNT_FIELDS = ("input", "output")


def _tokens_dict(tokens: Tokens) -> dict[str, Any]:
    # Only what is there: a count left as None is absent, never written as 0 (FR-7).
    out: dict[str, Any] = {"recorded": tokens.recorded}
    for name in ("reason", *_COUNT_FIELDS):
        value = getattr(tokens, name)
        if value is not None:
            out[name] = value
    return out


def to_dict(trace: Trace) -> dict[str, Any]:
    return {
        "schema_version": trace.schema_version,
        "identity": dataclasses.asdict(trace.identity),
        "calls": [dataclasses.asdict(c) for c in trace.calls],
        "totals": dataclasses.asdict(trace.totals),
        "ending": dataclasses.asdict(trace.ending),
        "tokens": _tokens_dict(trace.tokens),
        "extensions": dict(trace.extensions),
    }


def to_json(trace: Trace) -> str:
    return json.dumps(to_dict(trace), sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def from_dict(data: Mapping[str, Any]) -> Trace:
    """Build a `Trace` from its JSON form. Raises `TraceInvalid` unless the form is fully valid."""
    violations = validate(data)
    if violations:
        raise TraceInvalid(violations)
    tokens = data["tokens"]
    return Trace(
        schema_version=data["schema_version"],
        identity=Identity(**data["identity"]),
        calls=tuple(ToolCall(**c) for c in data["calls"]),
        totals=Totals(**data["totals"]),
        ending=Ending(**data["ending"]),
        tokens=Tokens(
            recorded=tokens["recorded"],
            reason=tokens.get("reason"),
            input=tokens.get("input"),
            output=tokens.get("output"),
        ),
        extensions=dict(data["extensions"]),
    )


def from_json(text: str) -> Trace:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise TraceInvalid([f"not JSON: {exc}"]) from exc
    return from_dict(data)


# --- validation ---------------------------------------------------------------------------------


def _is_type(value: object, kind: type) -> bool:
    if kind is int:  # bool is an int to Python, never to the schema
        return isinstance(value, int) and not isinstance(value, bool)
    return isinstance(value, kind)


def _check_object(obj: object, where: str, fields: Mapping[str, type], out: list[str]) -> bool:
    """Shape only: a JSON object with exactly `fields`, each of its type. True when the shape holds."""
    if not isinstance(obj, Mapping):
        out.append(f"{where}: must be an object")
        return False
    before = len(out)
    out.extend(f"{where}.{k}: missing" for k in fields if k not in obj)
    out.extend(f"{where}.{k}: unknown key" for k in sorted(set(obj) - set(fields), key=str))
    for k, kind in fields.items():
        if k in obj and not _is_type(obj[k], kind):
            out.append(f"{where}.{k}: must be {kind.__name__}, got {type(obj[k]).__name__}")
    return len(out) == before


def _check_identity(ident: Mapping[str, Any], out: list[str]) -> None:
    # Rule 1 (FR-8): every stamp non-empty; the image is the bench's own revision; the base is pinned.
    for k, kind in _IDENTITY_FIELDS.items():
        if kind is str and not ident[k].strip():
            out.append(f"identity.{k}: empty")
    for k in _IDENTITY_POSITIVE:
        if ident[k] <= 0:
            out.append(f"identity.{k}: must be > 0, got {ident[k]}")
    if ident["environment"].strip() and ident["environment"] not in ENVIRONMENTS:
        out.append(f"identity.environment: must be one of {', '.join(ENVIRONMENTS)}")
    if ident["image_revision"] != ident["bench_revision"]:
        out.append("identity.image_revision: must equal bench_revision")
    if ident["base_digest"].strip() and DIGEST_MARK not in ident["base_digest"]:
        out.append(f"identity.base_digest: must contain {DIGEST_MARK!r}")


def _check_calls(calls: object, out: list[str]) -> list[ToolCall] | None:
    """The calls, when every one is well-formed; None otherwise (totals can't be judged then)."""
    if not isinstance(calls, list):
        out.append("calls: must be a list")
        return None
    good: list[ToolCall] = []
    for i, call in enumerate(calls):
        where = f"calls[{i}]"
        if not _check_object(call, where, _CALL_FIELDS, out):
            continue
        c = ToolCall(**call)
        if c.seq != i + 1:
            out.append(f"{where}.seq: must be {i + 1} (1-based, in order), got {c.seq}")
        if c.turn < 1:
            out.append(f"{where}.turn: must be >= 1, got {c.turn}")
        for k in ("duration_ms", "stdout_bytes", "stderr_bytes", "passed_bytes"):
            if getattr(c, k) < 0:
                out.append(f"{where}.{k}: must be >= 0")
        if c.harness_cut != (c.passed_bytes < c.stdout_bytes + c.stderr_bytes):
            out.append(f"{where}.harness_cut: must be true exactly when passed_bytes is below the total")
        good.append(c)
    return good if len(good) == len(calls) else None


def _check_tokens(tokens: object, out: list[str]) -> None:
    # Rule 4 (FR-7): counts present iff recorded; not recorded says why.
    if not isinstance(tokens, Mapping):
        out.append("tokens: must be an object")
        return
    if not _is_type(tokens.get("recorded"), bool):
        out.append("tokens.recorded: must be bool")
        return
    fields: dict[str, type] = {"recorded": bool}
    if tokens["recorded"]:
        fields.update(dict.fromkeys(_COUNT_FIELDS, int))
    else:
        fields["reason"] = str
    if not _check_object(tokens, "tokens", fields, out):
        return
    if tokens["recorded"]:
        out.extend(f"tokens.{k}: must be >= 0" for k in _COUNT_FIELDS if tokens[k] < 0)
    elif not tokens["reason"].strip():
        out.append("tokens.reason: empty (say why the counts were not recorded)")


def validate(trace: Trace | Mapping[str, Any]) -> list[str]:
    """Every rule the trace breaks, one line each. Empty means valid."""
    data = to_dict(trace) if isinstance(trace, Trace) else trace
    out: list[str] = []
    if not isinstance(data, Mapping):
        return ["trace: must be an object"]
    version = data.get("schema_version")
    if not _is_type(version, int) or version != SCHEMA_VERSION:
        # Rule 5: nothing else is judged under a schema this reader does not know.
        return [f"schema_version: unknown {version!r} (this reader knows {SCHEMA_VERSION})"]
    out.extend(f"{k}: missing" for k in sorted(_TOP_LEVEL - set(data)))
    out.extend(
        f"{k}: unknown top-level key (new fields go under extensions)"
        for k in sorted(set(data) - _TOP_LEVEL, key=str)
    )

    if "identity" in data and _check_object(data["identity"], "identity", _IDENTITY_FIELDS, out):
        _check_identity(data["identity"], out)

    calls = _check_calls(data["calls"], out) if "calls" in data else None

    if "totals" in data and _check_object(data["totals"], "totals", _TOTALS_FIELDS, out):
        totals = Totals(**data["totals"])
        if totals.wall_clock_ms < 0:
            out.append("totals.wall_clock_ms: must be >= 0")
        if calls is not None:
            want = derive_totals(calls, totals.wall_clock_ms)
            for k in ("turns", "tool_calls", "nonzero_exits", "hangs"):
                if getattr(totals, k) != getattr(want, k):
                    out.append(f"totals.{k}: {getattr(totals, k)} disagrees with calls ({getattr(want, k)})")

    if "ending" in data and _check_object(data["ending"], "ending", _ENDING_FIELDS, out):
        # Rule 3.
        kind, reason = data["ending"]["kind"], data["ending"]["reason"]
        if kind not in ENDING_KINDS:
            out.append(f"ending.kind: unknown {kind!r} (one of {', '.join(ENDING_KINDS)})")
        if not reason.strip():
            out.append("ending.reason: empty")
        elif reason.splitlines() != [reason]:
            out.append("ending.reason: must be a single line")

    if "tokens" in data:
        _check_tokens(data["tokens"], out)

    if "extensions" in data and not isinstance(data["extensions"], Mapping):
        out.append("extensions: must be an object")
    return out


# --- files --------------------------------------------------------------------------------------


def write_trace(trace: Trace, path: Path) -> None:
    """Validate, then write atomically. An invalid trace raises `TraceInvalid` and writes nothing."""
    violations = validate(trace)
    if violations:
        raise TraceInvalid(violations)
    text = to_json(trace)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp)
        raise


def load_traces(directory: Path) -> list[Trace]:
    """Every `<directory>/traces/*.json`, by file name. A malformed file raises `TraceInvalid`."""
    traces: list[Trace] = []
    for p in sorted((directory / "traces").glob("*.json"), key=lambda p: p.name):
        try:
            traces.append(from_json(p.read_text(encoding="utf-8")))
        except TraceInvalid as exc:
            raise TraceInvalid([f"{p.name}: {v}" for v in exc.violations]) from exc
    return traces
