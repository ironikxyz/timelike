"""Read two peer sessions' scratch trees and print what is there, as KEY=VALUE facts (SC-6 fixture).

    python3 -I sc6_check.py ROOT SESSION_A SESSION_B

Runs INSIDE the agent container after both peers finished. It judges nothing: it reports counts
read from the filesystem, and the bats test asserts on them (lore cross-stack P004). For each side
X in (a, b), with O the other session:

  X_dir_exists / X_dir_mode      ROOT/X exists; its permission bits in octal
  X_events_lines                 lines in ROOT/X/events.jsonl
  X_events_unparsed              lines that are not a JSON object
  X_events_own_session           lines whose "session" is X
  X_events_tool_timelike         lines whose "tool" is "timelike"
  X_out_files                    files named out-X-*.json anywhere under ROOT/X
  X_out_valid                    of those, how many hold a JSON object whose "tool" is "timelike"
  X_out_elsewhere                files named out-X-*.json anywhere under ROOT but outside ROOT/X
  X_holds_other_names            paths under ROOT/X whose name contains O
  X_holds_other_content          files under ROOT/X whose bytes contain O
  root_strays                    entries directly under ROOT other than the two session dirs
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def files_under(path: Path) -> list[Path]:
    return sorted(p for p in path.rglob("*") if p.is_file()) if path.is_dir() else []


def side(root: Path, me: str, other: str, tag: str) -> list[str]:
    home = root / me
    facts = [f"{tag}_dir_exists={int(home.is_dir())}"]
    facts.append(f"{tag}_dir_mode={oct(home.stat().st_mode & 0o7777)[2:] if home.is_dir() else '<absent>'}")

    lines: list[str] = []
    events = home / "events.jsonl"
    if events.is_file():
        lines = events.read_text(encoding="utf-8", errors="replace").splitlines()
    unparsed = own = tool = 0
    for line in lines:
        try:
            obj = json.loads(line)
        except ValueError:
            unparsed += 1
            continue
        if not isinstance(obj, dict):
            unparsed += 1
            continue
        own += obj.get("session") == me
        tool += obj.get("tool") == "timelike"
    facts += [
        f"{tag}_events_lines={len(lines)}",
        f"{tag}_events_unparsed={unparsed}",
        f"{tag}_events_own_session={own}",
        f"{tag}_events_tool_timelike={tool}",
    ]

    prefix = f"out-{me}-"
    mine = [p for p in files_under(home) if p.name.startswith(prefix) and p.suffix == ".json"]
    valid = 0
    for p in mine:
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            continue
        valid += isinstance(obj, dict) and obj.get("tool") == "timelike"
    elsewhere = [p for p in files_under(root) if p.name.startswith(prefix) and home not in p.parents]
    facts += [
        f"{tag}_out_files={len(mine)}",
        f"{tag}_out_valid={valid}",
        f"{tag}_out_elsewhere={len(elsewhere)}",
    ]

    names = [p for p in home.rglob("*") if other in p.name] if home.is_dir() else []
    needle = other.encode()
    content = [p for p in files_under(home) if needle in p.read_bytes()]
    facts += [f"{tag}_holds_other_names={len(names)}", f"{tag}_holds_other_content={len(content)}"]
    for p in names + content:
        facts.append(f"{tag}_foreign={p}")
    return facts


def main() -> int:
    root, a, b = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
    facts = side(root, a, b, "a") + side(root, b, a, "b")
    strays = sorted(set(os.listdir(root)) - {a, b}) if root.is_dir() else []
    facts.append(f"root_strays={len(strays)}")
    facts += [f"root_stray={name}" for name in strays]
    print("\n".join(facts))
    print("sc6-check=done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
