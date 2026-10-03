"""The publish deny-list over the tracked tree (maintenance send, publish redaction, 2026-10-02).

Before this repository is published, no tracked file may name the operator's internal host, home
paths or personal name. The deny-list says what those are, and it lives OUTSIDE the repository
(default ../bridge/publish-denylist.txt, or TIMELIKE_PUBLISH_DENYLIST): a rule committed to a public
repository that spells the strings out would publish them. So this module never prints, writes or
stores a pattern or a matched string. It reports entries by id and findings as file:line.

Input:
- the deny-list: one entry per line, `<id><TAB><case-insensitive extended regex>`; `#` lines and
  blank lines are ignored
- the tree: a tar stream of the tracked files at HEAD (`git archive HEAD`), on stdin or from a file,
  with the number of entries `git ls-tree -r HEAD` lists, so a file the archive leaves out (a future
  `export-ignore`) is an error, not a silent pass

Matching is GNU `grep -E -i`, the matcher the deny-list was counted with, never a re-implementation.

Results (stdout line 1, and --out JSON):
- pass: the list was read, the self-test saw every entry, and nothing matched
- fail: an entry matched a tracked file (exit 1)
- unknown: no deny-list is available (a public clone has no ../bridge/). Nothing was checked, so it is
  never reported as a pass, and it does not fail (exit 0)
- error: the list or the tree could not be read, an entry is not a valid regex, or the self-test
  could not see an entry (exit 2)

The self-test (cross-stack P005; the send's "show it failing"): before the tree is judged, one line
per entry is generated from that entry's own regex at run time, written to a private temp directory,
and run through the same matcher. Every entry must find its plant. A check that cannot see an entry
cannot pass a tree. The plants are never printed or kept.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import re._parser as sre_parse  # type: ignore[import-not-found]  # builds self-test plants only
import shutil
import subprocess
import sys
import tarfile
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Any

ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,31}$")
DEFAULT_LIST = "../bridge/publish-denylist.txt"
LIST_ENV = "TIMELIKE_PUBLISH_DENYLIST"


class ListError(Exception):
    """The deny-list cannot be used. The message names a line or an id, never a pattern."""


@dataclass
class Entry:
    id: str
    pattern: str = field(repr=False)  # never printed


@dataclass
class Result:
    state: str  # pass | fail | unknown | error
    reason: str = ""
    entries: list[str] = field(default_factory=list)
    files_checked: int = 0
    findings: list[dict[str, Any]] = field(default_factory=list)  # {id, file, line}
    counts: dict[str, dict[str, int]] = field(default_factory=dict)  # id -> {files, lines, matches}

    def exit_code(self) -> int:
        return {"pass": 0, "unknown": 0, "fail": 1}.get(self.state, 2)

    def doc(self) -> dict[str, Any]:
        return {
            "check": "publish deny-list over the tracked tree",
            "state": self.state,
            "reason": self.reason,
            "entries": self.entries,
            "files_checked": self.files_checked,
            "counts": self.counts,
            "findings": self.findings,
        }


def parse_list(text: str) -> list[Entry]:
    entries: list[Entry] = []
    seen: set[str] = set()
    for n, raw in enumerate(text.splitlines(), 1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        ident, tab, pattern = raw.partition("\t")
        if not tab or not ID_RE.match(ident) or not pattern:
            raise ListError(f"deny-list line {n} is not <id><TAB><regex>")
        if ident in seen:
            raise ListError(f"deny-list line {n} repeats id {ident}")
        seen.add(ident)
        entries.append(Entry(ident, pattern))
    if not entries:
        raise ListError("the deny-list has no entries, so nothing would be checked")
    return entries


# ── the matcher: GNU grep, case-insensitive ERE ─────────────────────────────────────────────────


def _grep(
    opts: list[str], pattern: str, path: Path | None = None, stdin: bytes | None = None
) -> subprocess.CompletedProcess[bytes]:
    # -e keeps a pattern that starts with "-" a pattern, and the path goes after "--"; stderr is
    # discarded so grep's message about a bad expression cannot echo it.
    files = [] if path is None else ["--", str(path)]
    return subprocess.run(
        ["grep", "-E", "-i", "-a", *opts, "-e", pattern, *files],
        input=stdin,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def validate(entry: Entry) -> None:
    rc = _grep(["-q"], entry.pattern, stdin=b"").returncode
    if rc not in (0, 1):
        raise ListError(f"entry {entry.id} is not a valid extended regex (grep exit {rc})")


def match_lines(entry: Entry, path: Path) -> tuple[list[int], int]:
    """Line numbers that match, and how many matches (grep -o) there are. Only numbers come back."""
    r = _grep(["-n"], entry.pattern, path)
    if r.returncode not in (0, 1):
        raise ListError(f"entry {entry.id}: grep failed on a tracked file (exit {r.returncode})")
    lines = [int(row.split(b":", 1)[0]) for row in r.stdout.splitlines() if row[:1].isdigit()]
    if not lines:
        return [], 0
    o = _grep(["-o"], entry.pattern, path)
    return lines, len(o.stdout.splitlines())


def match_text(entry: Entry, text: str) -> bool:
    return _grep(["-q"], entry.pattern, stdin=text.encode()).returncode == 0


# ── self-test plants, generated from each entry's own regex ─────────────────────────────────────


def _example(parsed: Any) -> str:
    out: list[str] = []
    for op, av in parsed:
        name = str(op)
        if name == "LITERAL":
            out.append(chr(av))
        elif name == "NOT_LITERAL":
            out.append("x" if chr(av) != "x" else "y")
        elif name == "ANY":
            out.append("x")
        elif name == "IN":
            out.append(_class_member(av))
        elif name == "BRANCH":
            out.append(_example(av[1][0]))
        elif name == "SUBPATTERN":
            out.append(_example(av[-1]))
        elif name in ("MAX_REPEAT", "MIN_REPEAT", "POSSESSIVE_REPEAT"):
            low, _high, sub = av
            out.append(_example(sub) * max(int(low), 1))
        elif name in ("AT", "ASSERT", "ASSERT_NOT"):
            continue
        elif name == "CATEGORY":
            out.append(_category(str(av)))
        else:
            raise ListError(f"the self-test cannot build a plant for a {name} construct")
    return "".join(out)


def _class_member(items: Any) -> str:
    negate = False
    for op, av in items:
        name = str(op)
        if name == "NEGATE":
            negate = True
        elif negate:
            break
        elif name == "LITERAL":
            return chr(av)
        elif name == "RANGE":
            return chr(av[0])
        elif name == "CATEGORY":
            return _category(str(av))
    if negate:
        return "\x01"
    raise ListError("the self-test cannot build a plant for an empty class")


def _category(name: str) -> str:
    return {"CATEGORY_DIGIT": "0", "CATEGORY_SPACE": " ", "CATEGORY_WORD": "a"}.get(name, "a")


def plant_for(entry: Entry) -> str:
    try:
        parsed = sre_parse.parse(entry.pattern, re.IGNORECASE)
    except re.error as exc:
        raise ListError(f"the self-test cannot read entry {entry.id} as a regex") from exc
    plant = _example(parsed)
    if not plant or not match_text(entry, plant + "\n"):
        raise ListError(f"the self-test built no line that entry {entry.id} matches")
    return plant


def self_test(entries: list[Entry], work: Path) -> None:
    """Every entry must find a planted line of its own kind, through the same matcher and file path."""
    d = work / "self-test"
    d.mkdir()
    for e in entries:
        p = d / f"plant-{e.id}.txt"
        p.write_text(f"clean line\n{plant_for(e)}\n", encoding="utf-8")  # alone, so anchors hold
        lines, _ = match_lines(e, p)
        if lines != [2]:
            raise ListError(f"the self-test planted a line for {e.id} and the check did not see it")
    shutil.rmtree(d)


# ── the tree ────────────────────────────────────────────────────────────────────────────────────


def unpack(stream: IO[bytes], dest: Path, expect: int | None) -> tuple[list[str], dict[str, str]]:
    """Regular files extracted into dest, and symlink targets kept apart (they are text too)."""
    files: list[str] = []
    links: dict[str, str] = {}
    members = 0
    with tarfile.open(fileobj=stream, mode="r|") as tar:
        for m in tar:
            if m.isdir() or m.type == tarfile.XGLTYPE or m.name == "pax_global_header":
                continue
            members += 1
            name = m.name
            if name.startswith("/") or ".." in Path(name).parts:
                raise ListError(f"the archive holds an unsafe path at member {members}")
            if m.issym() or m.islnk():
                links[name] = m.linkname
            elif m.isfile():
                target = dest / name
                target.parent.mkdir(parents=True, exist_ok=True)
                src = tar.extractfile(m)
                if src is None:  # pragma: no cover — a regular member always has data
                    raise ListError(f"cannot read archive member {members}")
                with open(target, "wb") as fh:
                    shutil.copyfileobj(src, fh)
                files.append(name)
            else:
                raise ListError(
                    f"the archive holds a member of type {m.type!r}, which this check cannot read"
                )
    if expect is not None and members != expect:
        raise ListError(
            f"the archive holds {members} entries but HEAD tracks {expect}; some were not checked"
        )
    return sorted(files), links


def check_tree(entries: list[Entry], root: Path, files: list[str], links: dict[str, str]) -> Result:
    r = Result("pass", entries=[e.id for e in entries], files_checked=len(files) + len(links))
    for e in entries:
        hit_files, hit_lines, hits = 0, 0, 0
        for name in files:
            lines, n = match_lines(e, root / name)
            if lines:
                hit_files += 1
                hit_lines += len(lines)
                hits += n
                r.findings += [{"id": e.id, "file": name, "line": ln} for ln in lines]
        for name, target in sorted(links.items()):
            if match_text(e, target + "\n"):
                hit_files += 1
                hit_lines += 1
                hits += 1
                r.findings.append({"id": e.id, "file": name, "line": "symlink target"})
        r.counts[e.id] = {"files": hit_files, "lines": hit_lines, "matches": hits}
    if r.findings:
        r.state = "fail"
        r.reason = f"{len(r.findings)} tracked lines match the deny-list"
    else:
        r.reason = f"{len(entries)} entries, {r.files_checked} tracked files: no match"
    return r


def run(list_path: Path, label: str, stream: IO[bytes], expect: int | None) -> Result:
    if not list_path.is_file():
        return Result("unknown", f"no deny-list available ({label} is not there); nothing was checked")
    try:
        entries = parse_list(list_path.read_text(encoding="utf-8"))
        for e in entries:
            validate(e)
        with tempfile.TemporaryDirectory(prefix="denylist-") as tmp:
            work = Path(tmp)
            self_test(entries, work)
            tree = work / "tree"
            tree.mkdir()
            files, links = unpack(stream, tree, expect)
            return check_tree(entries, tree, files, links)
    except (ListError, OSError, tarfile.TarError, UnicodeDecodeError) as exc:
        return Result("error", str(exc) if isinstance(exc, ListError) else f"{type(exc).__name__}")


def render(r: Result) -> list[str]:
    head = f"publish deny-list [tracked tree]: {r.state.upper() if r.state != 'unknown' else 'unknown'}"
    lines = [f"{head} — {r.reason}"]
    for f in r.findings:
        lines.append(f"FAIL {f['id']} {f['file']}:{f['line']}")
    if r.counts:
        lines.append("per id: " + ", ".join(f"{k} {v['files']}/{v['matches']}" for k, v in r.counts.items()))
    return lines


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Run the publish deny-list over a tar of the tracked tree.")
    p.add_argument("--list", default=os.environ.get(LIST_ENV) or DEFAULT_LIST, help="the deny-list file")
    p.add_argument("--list-label", default=None, help="how to name the list in messages")
    p.add_argument("--tar", default="-", help="the tar of the tracked tree (`git archive HEAD`); - is stdin")
    p.add_argument("--expect-files", type=int, default=None, help="entries `git ls-tree -r HEAD` lists")
    p.add_argument("--out", default=None, help="write the result as JSON here")
    args = p.parse_args(argv)
    label = args.list_label or args.list
    if args.tar == "-":
        result = run(Path(args.list), label, sys.stdin.buffer, args.expect_files)
        # Read what is left, on every path: an early return (no list, a bad list) would otherwise close
        # the pipe under `git archive`, whose SIGPIPE fails `make scan` under pipefail (exit 141).
        while sys.stdin.buffer.read(1 << 16):
            pass
    else:
        with open(args.tar, "rb") as fh:
            result = run(Path(args.list), label, fh, args.expect_files)
    for line in render(result):
        print(line)
    if args.out:
        Path(args.out).write_text(json.dumps(result.doc(), indent=2) + "\n", encoding="utf-8")
    return result.exit_code()


if __name__ == "__main__":
    sys.exit(main())
