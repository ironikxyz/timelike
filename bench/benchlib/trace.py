"""trace — the bench's run record, schema version 2 (slice 1).

One trace per run, written by the driver only. The schema is specified in
`.specswarm/features/002-speedup-bench/contracts/trace-schema.md`; the rule numbers in the comments
below refer to it (schema 2's rules, which extend schema 1's).

The trace is the only input to the report (FR-10), so everything a report relies on is enforced here,
before a byte is written: every identity stamp is present (FR-8), the arm agrees with the environment,
totals and their category and adoption counts are derived from the calls and never counted separately, a
token count or a spend figure is either recorded or explicitly absent and never a zero stand-in (FR-7,
FR-35), an infrastructure ending names its cause (FR-36), and unknown keys are refused everywhere except
under `extensions` (FR-14). `write_trace` validates first and writes through the key gate (FR-31), so an
invalid trace, or one holding the key, never reaches disk.

Schema 1 (slice 0) is not read by this build: its traces are refused with a message naming the revision
that re-reports them, which keeps FR-10 ("re-reported without re-running") true per revision.

Validation works on the JSON form, so a `Trace` built in memory and a file read back are judged by the
same rules. Stdlib only (constitution H5).
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from benchlib.categories import CATEGORIES
from benchlib.keyfile import Gate

SCHEMA_VERSION = 2
ENDING_KINDS = ("completed", "escalated", "failed", "hung", "stopped")
STOP_CAUSES = (
    "api-rate-limit",
    "api-error",
    "api-unreachable",
    "key-rejected",
    "harness-exit",
    "harness-unresponsive",
    "turn-cap",
    "spend-cap",
    "placement",
    "transcript-unreadable",
)
ENVIRONMENTS = ("vanilla", "timelike")
ARMS = ("vanilla", "not-told", "told")
OUTPUT_STREAMS = ("separate", "merged")
DIGEST_MARK = "@sha256:"
SCHEMA_1_MESSAGE = "schema_version: 1 is slice 0's trace; re-report it with a slice-0 build of the bench"


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
    category: str  # "" for a call that succeeded; else one of categories.CATEGORIES (rule 3)
    timelike_tools: tuple[str, ...] = ()
    through_timelike: tuple[str, ...] = ()


@dataclass(frozen=True)
class Identity:
    bench_revision: str
    environment: str
    arm: str
    image_id: str
    image_revision: str
    base_digest: str
    harness_name: str
    harness_version: str
    harness_reported_version: str
    model_id: str
    models_answered: tuple[str, ...]
    invocation: str
    output_streams: str
    placement: str  # told: the placement's result; otherwise "" (rule 1)
    task_id: str
    task_version: int
    call_limit_s: int
    run_limit_s: int
    turn_cap: int  # 0: no cap (the fake agent)
    timelike_tools: tuple[str, ...]
    reproduce: str


@dataclass(frozen=True)
class Ending:
    kind: str
    reason: str
    cause: str = ""  # non-empty exactly when kind is "stopped" (rule 5)


@dataclass(frozen=True)
class Tokens:
    """Either recorded with both counts, or not recorded with a reason and no counts (FR-7)."""

    recorded: bool
    reason: str | None = None
    input: int | None = None
    output: int | None = None


@dataclass(frozen=True)
class Spend:
    """OpenRouter's figure, or not recorded with a reason (FR-35). Never an estimate or a zero stand-in."""

    recorded: bool
    reason: str | None = None
    usd: float | None = None
    source: str | None = None
    unknown_generations: int | None = None


NO_SPEND = Spend(recorded=False, reason="the fake agent uses no model")


@dataclass(frozen=True)
class Totals:
    turns: int
    tool_calls: int
    nonzero_exits: int
    hangs: int
    wall_clock_ms: int
    timelike_tool_calls: int
    through_timelike_calls: int
    by_category: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class Trace:
    identity: Identity
    calls: tuple[ToolCall, ...]
    totals: Totals
    ending: Ending
    tokens: Tokens
    spend: Spend
    extensions: dict[str, Any] = field(default_factory=dict)
    schema_version: int = SCHEMA_VERSION


def derive_totals(calls: Sequence[ToolCall], wall_clock_ms: int) -> Totals:
    """Rules 2 and 4: the only way totals are made. A hung call is also a non-zero exit."""
    by_category: dict[str, int] = {}
    for c in calls:
        if c.category:
            by_category[c.category] = by_category.get(c.category, 0) + 1
    return Totals(
        turns=max((c.turn for c in calls), default=0),
        tool_calls=len(calls),
        nonzero_exits=sum(1 for c in calls if c.exit_code != 0),
        hangs=sum(1 for c in calls if c.hung),
        wall_clock_ms=wall_clock_ms,
        timelike_tool_calls=sum(1 for c in calls if c.timelike_tools),
        through_timelike_calls=sum(1 for c in calls if c.through_timelike),
        by_category={k: by_category[k] for k in CATEGORIES if k in by_category},
    )


# --- JSON form ----------------------------------------------------------------------------------

# The JSON kinds a field may hold. "strs" is a list of strings; "counts" an object of string -> int ≥ 0.
STR, INT, BOOL, STRS, COUNTS = "str", "int", "bool", "strs", "counts"

_CALL_FIELDS = {
    "seq": INT,
    "turn": INT,
    "command": STR,
    "exit_code": INT,
    "duration_ms": INT,
    "hung": BOOL,
    "stdout_bytes": INT,
    "stderr_bytes": INT,
    "passed_bytes": INT,
    "harness_cut": BOOL,
    "stderr_head": STR,
    "category": STR,
    "timelike_tools": STRS,
    "through_timelike": STRS,
}
_IDENTITY_FIELDS = {
    "bench_revision": STR,
    "environment": STR,
    "arm": STR,
    "image_id": STR,
    "image_revision": STR,
    "base_digest": STR,
    "harness_name": STR,
    "harness_version": STR,
    "harness_reported_version": STR,
    "model_id": STR,
    "models_answered": STRS,
    "invocation": STR,
    "output_streams": STR,
    "placement": STR,
    "task_id": STR,
    "task_version": INT,
    "call_limit_s": INT,
    "run_limit_s": INT,
    "turn_cap": INT,
    "timelike_tools": STRS,
    "reproduce": STR,
}
_ENDING_FIELDS = {"kind": STR, "reason": STR, "cause": STR}
_TOTALS_FIELDS = {
    "turns": INT,
    "tool_calls": INT,
    "nonzero_exits": INT,
    "hangs": INT,
    "wall_clock_ms": INT,
    "timelike_tool_calls": INT,
    "through_timelike_calls": INT,
    "by_category": COUNTS,
}
_TOP_LEVEL = frozenset(f.name for f in dataclasses.fields(Trace))
_IDENTITY_POSITIVE = ("task_version", "call_limit_s", "run_limit_s")  # limits and versions: > 0
_MAY_BE_EMPTY = frozenset({"placement"})  # rule 1: non-empty exactly when the arm is told
_COUNT_FIELDS = ("input", "output")


def _optional_dict(obj: Tokens | Spend, names: Sequence[str]) -> dict[str, Any]:
    # Only what is there: a value left as None is absent, never written as 0 (FR-7).
    out: dict[str, Any] = {"recorded": obj.recorded}
    for name in names:
        value = getattr(obj, name)
        if value is not None:
            out[name] = value
    return out


def _listify(d: dict[str, Any]) -> dict[str, Any]:
    return {k: list(v) if isinstance(v, tuple) else v for k, v in d.items()}


def to_dict(trace: Trace) -> dict[str, Any]:
    return {
        "schema_version": trace.schema_version,
        "identity": _listify(dataclasses.asdict(trace.identity)),
        "calls": [_listify(dataclasses.asdict(c)) for c in trace.calls],
        "totals": dataclasses.asdict(trace.totals),
        "ending": dataclasses.asdict(trace.ending),
        "tokens": _optional_dict(trace.tokens, ("reason", *_COUNT_FIELDS)),
        "spend": _optional_dict(trace.spend, ("reason", "usd", "source", "unknown_generations")),
        "extensions": dict(trace.extensions),
    }


def to_json(trace: Trace) -> str:
    return json.dumps(to_dict(trace), sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def _tuples(d: Mapping[str, Any], fields: Mapping[str, str]) -> dict[str, Any]:
    return {k: tuple(v) if fields[k] == STRS else v for k, v in d.items()}


def from_dict(data: Mapping[str, Any]) -> Trace:
    """Build a `Trace` from its JSON form. Raises `TraceInvalid` unless the form is fully valid."""
    violations = validate(data)
    if violations:
        raise TraceInvalid(violations)
    tokens, spend = data["tokens"], data["spend"]
    return Trace(
        schema_version=data["schema_version"],
        identity=Identity(**_tuples(data["identity"], _IDENTITY_FIELDS)),
        calls=tuple(ToolCall(**_tuples(c, _CALL_FIELDS)) for c in data["calls"]),
        totals=Totals(**data["totals"]),
        ending=Ending(**data["ending"]),
        tokens=Tokens(
            recorded=tokens["recorded"],
            reason=tokens.get("reason"),
            input=tokens.get("input"),
            output=tokens.get("output"),
        ),
        spend=Spend(
            recorded=spend["recorded"],
            reason=spend.get("reason"),
            usd=spend.get("usd"),
            source=spend.get("source"),
            unknown_generations=spend.get("unknown_generations"),
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


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)  # bool is an int to Python, not the schema


def _is_kind(value: object, kind: str) -> bool:
    if kind == INT:
        return _is_int(value)
    if kind == BOOL:
        return isinstance(value, bool)
    if kind == STR:
        return isinstance(value, str)
    if kind == STRS:
        return isinstance(value, list) and all(isinstance(x, str) and x for x in value)
    if kind == COUNTS:
        return isinstance(value, Mapping) and all(
            isinstance(k, str) and _is_int(v) and v > 0 for k, v in value.items()
        )
    raise AssertionError(kind)


_KIND_WORDS = {
    STR: "str",
    INT: "int",
    BOOL: "bool",
    STRS: "a list of non-empty str",
    COUNTS: "counts of int > 0",
}


def _check_object(obj: object, where: str, fields: Mapping[str, str], out: list[str]) -> bool:
    """Shape only: a JSON object with exactly `fields`, each of its kind. True when the shape holds."""
    if not isinstance(obj, Mapping):
        out.append(f"{where}: must be an object")
        return False
    before = len(out)
    out.extend(f"{where}.{k}: missing" for k in fields if k not in obj)
    out.extend(f"{where}.{k}: unknown key" for k in sorted(set(obj) - set(fields), key=str))
    for k, kind in fields.items():
        if k in obj and not _is_kind(obj[k], kind):
            out.append(f"{where}.{k}: must be {_KIND_WORDS[kind]}, got {type(obj[k]).__name__}")
    return len(out) == before


def _check_identity(ident: Mapping[str, Any], out: list[str]) -> None:
    # Rule 1 (FR-8): every stamp non-empty; the image is the bench's own revision; the base is pinned.
    for k, kind in _IDENTITY_FIELDS.items():
        if kind == STR and k not in _MAY_BE_EMPTY and not ident[k].strip():
            out.append(f"identity.{k}: empty")
    for k in _IDENTITY_POSITIVE:
        if ident[k] <= 0:
            out.append(f"identity.{k}: must be > 0, got {ident[k]}")
    if ident["turn_cap"] < 0:
        out.append(f"identity.turn_cap: must be >= 0 (0: no cap), got {ident['turn_cap']}")
    env, arm = ident["environment"], ident["arm"]
    if env.strip() and env not in ENVIRONMENTS:
        out.append(f"identity.environment: must be one of {', '.join(ENVIRONMENTS)}")
    if arm.strip() and arm not in ARMS:
        out.append(f"identity.arm: must be one of {', '.join(ARMS)}")
    elif env in ENVIRONMENTS and (env == "vanilla") != (arm == "vanilla"):
        out.append("identity.arm: is vanilla exactly when the environment is vanilla")  # rule 2
    if (arm == "told") != bool(ident["placement"].strip()):
        out.append("identity.placement: non-empty exactly when the arm is told")
    if ident["output_streams"].strip() and ident["output_streams"] not in OUTPUT_STREAMS:
        out.append(f"identity.output_streams: must be one of {', '.join(OUTPUT_STREAMS)}")
    if ident["image_revision"] != ident["bench_revision"]:
        out.append("identity.image_revision: must equal bench_revision")
    if ident["base_digest"].strip() and DIGEST_MARK not in ident["base_digest"]:
        out.append(f"identity.base_digest: must contain {DIGEST_MARK!r}")


def _check_calls(calls: object, vanilla: bool, out: list[str]) -> list[ToolCall] | None:
    """The calls, when every one is well-formed; None otherwise (totals can't be judged then)."""
    if not isinstance(calls, list):
        out.append("calls: must be a list")
        return None
    good: list[ToolCall] = []
    for i, call in enumerate(calls):
        where = f"calls[{i}]"
        if not _check_object(call, where, _CALL_FIELDS, out):
            continue
        c = ToolCall(**_tuples(call, _CALL_FIELDS))
        if c.seq != i + 1:
            out.append(f"{where}.seq: must be {i + 1} (1-based, in order), got {c.seq}")
        if c.turn < 1:
            out.append(f"{where}.turn: must be >= 1, got {c.turn}")
        for k in ("duration_ms", "stdout_bytes", "stderr_bytes", "passed_bytes"):
            if getattr(c, k) < 0:
                out.append(f"{where}.{k}: must be >= 0")
        if c.harness_cut != (c.passed_bytes < c.stdout_bytes + c.stderr_bytes):
            out.append(f"{where}.harness_cut: must be true exactly when passed_bytes is below the total")
        failed = c.exit_code != 0 or c.hung
        if not failed and c.category:
            out.append(f"{where}.category: must be empty for a call that exited 0 and did not hang")
        elif failed and c.category not in CATEGORIES:
            out.append(f"{where}.category: must be one of {', '.join(CATEGORIES)} for a failed call")
        if vanilla and (c.timelike_tools or c.through_timelike):
            out.append(f"{where}: the vanilla arm has no timelike tools and nothing through timelike")
        good.append(c)
    return good if len(good) == len(calls) else None


def _check_recorded(
    obj: object, where: str, present: Mapping[str, str], out: list[str], what: str = "it was"
) -> bool:
    """Rules 4 and 6: the fields in `present` exactly when recorded; otherwise a non-empty reason."""
    if not isinstance(obj, Mapping):
        out.append(f"{where}: must be an object")
        return False
    if not isinstance(obj.get("recorded"), bool):
        out.append(f"{where}.recorded: must be bool")
        return False
    fields: dict[str, str] = {"recorded": BOOL}
    if obj["recorded"]:
        fields.update(present)
    else:
        fields["reason"] = STR
    if not _check_object(obj, where, fields, out):
        return False
    if not obj["recorded"] and not obj["reason"].strip():
        out.append(f"{where}.reason: empty (say why {what} not recorded)")
        return False
    return bool(obj["recorded"])


def _check_tokens(tokens: object, out: list[str]) -> None:
    if _check_recorded(tokens, "tokens", dict.fromkeys(_COUNT_FIELDS, INT), out, "the counts were"):
        assert isinstance(tokens, Mapping)  # noqa: S101 — _check_recorded established it
        out.extend(f"tokens.{k}: must be >= 0" for k in _COUNT_FIELDS if tokens[k] < 0)


def _check_spend(spend: object, out: list[str]) -> None:
    """Rule 6. `usd` is the schema's one number that may be fractional; 0 is a real zero, so it is allowed."""
    if not isinstance(spend, Mapping) or not isinstance(spend.get("recorded"), bool) or not spend["recorded"]:
        _check_recorded(spend, "spend", {}, out)
        return
    fields = ("recorded", "usd", "source", "unknown_generations")
    out.extend(f"spend.{k}: missing" for k in fields if k not in spend)
    out.extend(f"spend.{k}: unknown key" for k in sorted(set(spend) - set(fields), key=str))
    usd = spend.get("usd")
    if "usd" in spend and (isinstance(usd, bool) or not isinstance(usd, int | float) or usd < 0):
        out.append("spend.usd: must be a number >= 0")
    source = spend.get("source")
    if "source" in spend and (not isinstance(source, str) or not source.strip()):
        out.append("spend.source: must say where the figure came from")
    unknown = spend.get("unknown_generations")
    good = isinstance(unknown, int) and _is_int(unknown) and unknown >= 0
    if "unknown_generations" in spend and not good:
        out.append("spend.unknown_generations: must be an int >= 0")


def validate(trace: Trace | Mapping[str, Any]) -> list[str]:
    """Every rule the trace breaks, one line each. Empty means valid."""
    data = to_dict(trace) if isinstance(trace, Trace) else trace
    out: list[str] = []
    if not isinstance(data, Mapping):
        return ["trace: must be an object"]
    version = data.get("schema_version")
    if _is_int(version) and version == 1:
        return [SCHEMA_1_MESSAGE]
    if not _is_int(version) or version != SCHEMA_VERSION:
        # Nothing else is judged under a schema this reader does not know.
        return [f"schema_version: unknown {version!r} (this reader knows {SCHEMA_VERSION})"]
    out.extend(f"{k}: missing" for k in sorted(_TOP_LEVEL - set(data)))
    out.extend(
        f"{k}: unknown top-level key (new fields go under extensions)"
        for k in sorted(set(data) - _TOP_LEVEL, key=str)
    )

    vanilla = False
    if "identity" in data and _check_object(data["identity"], "identity", _IDENTITY_FIELDS, out):
        _check_identity(data["identity"], out)
        vanilla = data["identity"]["arm"] == "vanilla"

    calls = _check_calls(data["calls"], vanilla, out) if "calls" in data else None

    if "totals" in data and _check_object(data["totals"], "totals", _TOTALS_FIELDS, out):
        totals = Totals(**data["totals"])
        if totals.wall_clock_ms < 0:
            out.append("totals.wall_clock_ms: must be >= 0")
        if calls is not None:
            want = derive_totals(calls, totals.wall_clock_ms)
            for k in (
                "turns",
                "tool_calls",
                "nonzero_exits",
                "hangs",
                "timelike_tool_calls",
                "through_timelike_calls",
                "by_category",
            ):
                if getattr(totals, k) != getattr(want, k):
                    out.append(f"totals.{k}: {getattr(totals, k)} disagrees with calls ({getattr(want, k)})")

    if "ending" in data and _check_object(data["ending"], "ending", _ENDING_FIELDS, out):
        kind, reason, cause = data["ending"]["kind"], data["ending"]["reason"], data["ending"]["cause"]
        if kind not in ENDING_KINDS:
            out.append(f"ending.kind: unknown {kind!r} (one of {', '.join(ENDING_KINDS)})")
        if not reason.strip():
            out.append("ending.reason: empty")
        elif reason.splitlines() != [reason]:
            out.append("ending.reason: must be a single line")
        if kind == "stopped" and cause not in STOP_CAUSES:
            out.append(f"ending.cause: a stopped run names one of {', '.join(STOP_CAUSES)}, got {cause!r}")
        elif kind != "stopped" and cause:
            out.append("ending.cause: only a stopped run has a cause")

    if "tokens" in data:
        _check_tokens(data["tokens"], out)
    if "spend" in data:
        _check_spend(data["spend"], out)

    if "extensions" in data and not isinstance(data["extensions"], Mapping):
        out.append("extensions: must be an object")
    return out


# --- files --------------------------------------------------------------------------------------


def write_trace(trace: Trace, path: Path, gate: Gate | None = None) -> None:
    """Validate, then write atomically through the key gate. An invalid trace raises `TraceInvalid`, and
    one holding the key raises `GateRefused`; neither writes anything."""
    violations = validate(trace)
    if violations:
        raise TraceInvalid(violations)
    (gate or Gate()).write_text(path, to_json(trace))


def load_traces(directory: Path) -> list[Trace]:
    """Every `<directory>/traces/*.json`, by file name. A malformed file raises `TraceInvalid`."""
    traces: list[Trace] = []
    for p in sorted((directory / "traces").glob("*.json"), key=lambda p: p.name):
        try:
            traces.append(from_json(p.read_text(encoding="utf-8")))
        except TraceInvalid as exc:
            raise TraceInvalid([f"{p.name}: {v}" for v in exc.violations]) from exc
    return traces
