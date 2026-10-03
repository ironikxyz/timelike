"""Print top-level fields of a JSON object as KEY=VALUE lines (e2e fixture; runs in the container).

    python3 -I json_fields.py FILE KEY...

For each KEY: a string or number prints as is, a list prints its length as KEY#=N, an absent key
prints KEY=<absent>. Also prints `json=ok`, or `json=invalid` (exit 1) when FILE is not one JSON
object. Stdlib only. Lets the bats tests read tool output as data rather than grep it as text.
"""

from __future__ import annotations

import json
import sys


def main() -> int:
    path, keys = sys.argv[1], sys.argv[2:]
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        print("json=invalid")
        print(f"json_error={exc}")
        return 1
    if not isinstance(data, dict):
        print("json=invalid")
        return 1
    print("json=ok")
    print("first_keys=" + ",".join(list(data)[:3]))
    for key in keys:
        if key not in data:
            print(f"{key}=<absent>")
        elif isinstance(data[key], list):
            print(f"{key}#={len(data[key])}")
        else:
            print(f"{key}={data[key]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
