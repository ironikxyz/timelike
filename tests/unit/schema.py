"""A stdlib-only JSON Schema subset validator, enough for the contract schemas in
.specswarm/features/001-agent-shell-baseline/contracts/. No third-party dependency (constitution H5).

Supported keywords: type, required, properties, additionalProperties (bool or schema), const, enum,
pattern, items, minimum, maximum, minLength, maxLength, propertyNames. Anything else is ignored — the
contract schemas use nothing else, and test_schema_keywords_are_supported guards that.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

CONTRACTS = Path(__file__).resolve().parents[2] / ".specswarm/features/001-agent-shell-baseline/contracts"
SUPPORTED = {
    "$schema", "$id", "title", "description", "format",
    "type", "required", "properties", "additionalProperties", "const", "enum",
    "pattern", "items", "minimum", "maximum", "minLength", "maxLength", "propertyNames",
}  # fmt: skip

_TYPES: dict[str, type | tuple[type, ...]] = {
    "object": dict,
    "array": list,
    "string": str,
    "integer": int,
    "boolean": bool,
}


def load(name: str) -> dict[str, Any]:
    schema: dict[str, Any] = json.loads((CONTRACTS / name).read_text())
    return schema


def errors(instance: Any, schema: dict[str, Any], path: str = "$") -> list[str]:
    out: list[str] = []
    t = schema.get("type")
    if t is not None:
        py = _TYPES[t]
        ok = isinstance(instance, py) and not (t == "integer" and isinstance(instance, bool))
        if not ok:
            return [f"{path}: expected {t}, got {type(instance).__name__}"]
    if "const" in schema and (
        instance != schema["const"] or isinstance(instance, bool) != isinstance(schema["const"], bool)
    ):  # False == 0 in Python; a schema's false is not 0
        out.append(f"{path}: expected const {schema['const']!r}, got {instance!r}")
    if "enum" in schema and instance not in schema["enum"]:
        out.append(f"{path}: {instance!r} not in {schema['enum']!r}")
    if isinstance(instance, str):
        if "pattern" in schema and not re.search(schema["pattern"], instance):
            out.append(f"{path}: {instance!r} does not match {schema['pattern']}")
        if "minLength" in schema and len(instance) < schema["minLength"]:
            out.append(f"{path}: shorter than {schema['minLength']}")
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            out.append(f"{path}: longer than {schema['maxLength']}")
    if (
        isinstance(instance, int)
        and not isinstance(instance, bool)
        and instance < schema.get("minimum", instance)
    ):
        out.append(f"{path}: {instance} < {schema['minimum']}")
    if (
        isinstance(instance, int)
        and not isinstance(instance, bool)
        and instance > schema.get("maximum", instance)
    ):
        out.append(f"{path}: {instance} > {schema['maximum']}")
    if isinstance(instance, list) and "items" in schema:
        for i, item in enumerate(instance):
            out += errors(item, schema["items"], f"{path}[{i}]")
    if isinstance(instance, dict):
        for key in schema.get("required", []):
            if key not in instance:
                out.append(f"{path}: missing required {key!r}")
        props: dict[str, Any] = schema.get("properties", {})
        extra = schema.get("additionalProperties", True)
        names = schema.get("propertyNames")
        for key, value in instance.items():
            if names is not None:
                out += errors(key, names, f"{path}.<name {key}>")
            if key in props:
                out += errors(value, props[key], f"{path}.{key}")
            elif extra is False:
                out.append(f"{path}: unexpected property {key!r}")
            elif isinstance(extra, dict):
                out += errors(value, extra, f"{path}.{key}")
    return out


def keywords(schema: Any) -> set[str]:
    """Every keyword used anywhere in a schema (property NAMES excluded)."""
    found: set[str] = set()
    if isinstance(schema, dict):
        for k, v in schema.items():
            found.add(k)
            if k == "properties":
                for sub in v.values():
                    found |= keywords(sub)
            elif isinstance(v, dict):
                found |= keywords(v)
    return found
