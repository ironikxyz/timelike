#!/usr/bin/env python3
"""Supply-chain gate evaluator (constitution H9, quality-standards "Supply-chain scan").

Stdlib only. scan/scan.sh runs it inside timelike-agent:local with `python3 -I`, never on the host.
It reads the scanners' JSON results, never their exit messages (H3), and applies discovery revision 5:

- a High or Critical with a fix available blocks. A fix listed only as a pre-release (e.g. 3.14.0b1)
  is not a stable fix by itself; the finding may be baselined, and the escalation says to upgrade
  instead if a stable release at or after it exists
- a High or Critical with no fix passes only through the reviewed baseline for the image,
  scan/baseline/<image>.json: every identifier with its package and origin, a reason per origin
  group, a reason for each Critical, one review date at most 90 days after the review, recorded for
  the pinned base digest. The baseline accepts nothing when it is malformed, unreviewed, overdue,
  past the cap or for another digest
- the baseline never hides a change: a finding not in it blocks, and so does a baselined finding
  that gains a fix, or that became Critical without a reason of its own
- every blocking finding is a T1 escalation: it names the identifier, image and package, the date
  concerned, and the exact file and field to update
- every scan prints one baseline summary line, and writes scan/out/baseline.proposed.json: the
  baseline as this scan would need it, reasons carried over, new ones left as placeholders
- any gitleaks finding blocks; Medium and below never block, nor does Grype's "Unknown"
- pip-audit carries no severity, so each of its findings is treated as High ("unrated"). It runs
  twice: over timelike's interpreter (step pip-audit) and over the agent interpreter, /opt/agent/python
  (step pip-audit-agent, discovery revision 14), each its own result line
- a library bundled inside a component installed as one unit (npm's own node_modules; pip's vendored
  packages) is fixable only when a stable release of that COMPONENT ships the fix (discovery revision 15).
  Its baseline entry is of the bundled class: it names the component, the library and the upstream fix,
  and carries its own review date at most 30 days out. `releases` checks the component's released
  manifests on every scan, and `report` lets the finding through only when that check answered that no
  release ships the fix; a release that does, or a check that could not run, blocks (it fails closed)
- govulncheck (Adele only) carries no severity either (research R5): a vulnerable function Adele's
  code reaches is treated as High, so with a fix it blocks; one only imported or only required is
  recorded below High and never blocks

Subcommands: `dists` lists the interpreter's installed distributions (and, with --requirements, writes
them as exact pins for pip-audit -r); `releases` runs the bundled-class release check (the one subcommand
that uses the network); `report` writes the verdict.
One file on purpose: scan.sh runs it with `-I`, which keeps the script directory off sys.path, so a
second module could not be imported. That puts it over max_file_lines (300), which quality-standards
allows for a single-file tool when the feature plan justifies it.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import importlib.metadata
import io
import json
import re
import sys
import sysconfig
import tarfile
import urllib.request
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# pip-audit reports no severity, so its findings are "unrated" and gated conservatively.
GATED = frozenset({"critical", "high", "unrated"})
# govulncheck reports no severity either; it reports how far in a vulnerability reaches (research R5).
# Its trace starts at the vulnerable symbol: a function there means Adele's code calls it (REACHABLE,
# gated as High); a package only, that Adele imports the package without calling the symbol; a module
# only, that Adele requires the module without importing the package. The last two are below High.
GO_LEVELS = ("required", "imported", "high")  # index = how far in: module, package, function
CAP = dt.timedelta(days=90)  # discovery revision 4: a review date at most 90 days after the review
BUNDLED_CAP = dt.timedelta(days=30)  # discovery revision 15: a bundled-class entry's own review
NPM_REGISTRY = "https://registry.npmjs.org"
BUNDLED_FIELDS = ("component", "component_version", "library_version", "fixed_version", "fixed_date")
RULE = "reviewed baseline per image digest (discovery revision 5)"
DEFAULT_IMAGE = "timelike-agent:local"
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
PRERELEASE_RE = re.compile(r"\d(a|b|rc|dev)\d*$|[.-](alpha|beta|rc|pre|dev)", re.IGNORECASE)
BASE = "base layer"
PLACE_ORIGIN = "<why the findings from this origin are tolerated>"
PLACE_CRITICAL = "<why this Critical is tolerated, on its own>"
PLACE_REVIEWED = "<YYYY-MM-DD: the day a person reviews this baseline>"
PLACE_REVIEW_BY = "<YYYY-MM-DD: at most 90 days after reviewed>"


class ParseError(ValueError):
    """An input the gate cannot read. The gate fails on it, never passes."""


@dataclass(frozen=True)
class Vuln:
    source: str
    identifier: str
    aliases: tuple[str, ...]
    component: str
    severity: str
    fix_versions: tuple[str, ...]
    artifact_id: str = ""

    def ids(self) -> set[str]:
        return {i.lower() for i in (self.identifier, *self.aliases) if i}

    @property
    def package(self) -> str:
        return self.component.split(" ", 1)[0]

    @property
    def stable_fixes(self) -> tuple[str, ...]:
        return tuple(v for v in self.fix_versions if not PRERELEASE_RE.search(v))


@dataclass(frozen=True, order=True)
class Finding:
    """One line of the verdict. A blocking one is a T1 escalation: `update` names the exact edit."""

    source: str
    identifier: str
    component: str
    severity: str
    message: str
    image: str = ""
    date: str = ""  # the review date that passed or exceeds the cap, or a future "reviewed"
    update: str = ""


@dataclass(frozen=True)
class Bundled:
    """A bundled-class entry's extra fields (discovery revision 15). The library is the entry's package."""

    component: str
    component_version: str
    library_version: str
    fixed_version: str
    fixed_date: str


@dataclass(frozen=True)
class Entry:
    """One baselined finding. A bundled-class entry also carries its own review dates."""

    identifier: str
    package: str
    severity: str
    origin: str
    reason: str = ""
    bundled: Bundled | None = None
    reviewed: dt.date | None = None
    review_by: dt.date | None = None

    @property
    def key(self) -> tuple[str, str]:
        return self.identifier.lower(), self.package.lower()


@dataclass
class Baseline:
    """scan/baseline/<image>.json. `problems` are (message, field) pairs; any one voids it."""

    path: str
    image: str = ""
    base_digest: str = ""
    reviewed: dt.date | None = None
    review_by: dt.date | None = None
    origins: dict[str, str] = field(default_factory=dict)
    entries: list[Entry] = field(default_factory=list)
    problems: list[tuple[str, str]] = field(default_factory=list)
    present: bool = True
    unreadable: str = ""  # set when the file exists but could not be read as a baseline

    def find(self, v: Vuln) -> Entry | None:
        pkg = v.package.lower()
        return next((e for e in self.entries if e.package.lower() == pkg and e.key[0] in v.ids()), None)


@dataclass
class Verdict:
    blocking: list[Finding] = field(default_factory=list)
    allowed: list[Finding] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    gated: int = 0
    ungated: int = 0
    voided: int = 0  # findings an unusable baseline lists, which therefore block

    @property
    def passed(self) -> bool:
        return not self.blocking


def _placeholder(text: object) -> bool:
    return not isinstance(text, str) or not text.strip() or text.strip().startswith("<")


def _date(doc: dict[str, Any], key: str, problems: list[tuple[str, str]]) -> dt.date | None:
    value = doc.get(key)
    try:
        if isinstance(value, str) and DATE_RE.match(value):
            return dt.date.fromisoformat(value)
    except ValueError:
        pass
    said = "is missing" if value in (None, "") else f"{value!r} is not a YYYY-MM-DD date"
    problems.append((f'"{key}" {said}', key))
    return None


def _entry(raw: Any, n: int, origins: dict[str, str], problems: list[tuple[str, str]]) -> Entry | None:
    where = f"findings[{n}]"
    if not isinstance(raw, dict):
        problems.append((f"{where} is not an object", where))
        return None
    got = {k: str(raw.get(k) or "").strip() for k in ("id", "package", "severity", "origin", "reason")}
    entry = Entry(got["id"], got["package"], got["severity"].lower(), got["origin"], got["reason"])
    name = f"{where} ({entry.identifier or '?'} in {entry.package or '?'})"
    for key in ("id", "package", "origin"):
        if not got[key]:
            problems.append((f'{name}: "{key}" is missing', f"{where}.{key}"))
    if entry.severity not in GATED:
        problems.append(
            (f'{name}: "severity" {got["severity"]!r} is not high, critical or unrated', f"{where}.severity")
        )
    if entry.origin and entry.origin not in origins:
        problems.append(
            (f'{name}: origin {entry.origin!r} has no entry in "origins"', f"origins.{entry.origin}")
        )
    if entry.severity == "critical" and _placeholder(entry.reason):
        problems.append((f"{name}: a Critical needs its own reason", f"{where}.reason"))
    if "bundled" in raw:
        entry = _bundled_entry(raw, entry, name, where, problems)
    return entry


def _bundled_entry(
    raw: dict[str, Any], entry: Entry, name: str, where: str, problems: list[tuple[str, str]]
) -> Entry:
    """A bundled-class entry: every field present, versions x.y.z, dates real, and a reason of its own."""
    bundled = raw.get("bundled")
    if not isinstance(bundled, dict):
        problems.append((f'{name}: "bundled" is not an object', f"{where}.bundled"))
        return entry
    got = {k: str(bundled.get(k) or "").strip() for k in BUNDLED_FIELDS}
    for key, value in got.items():
        if not value:
            problems.append((f'{name}: "bundled.{key}" is missing', f"{where}.bundled.{key}"))
        elif key.endswith("_version") and _semver_or_none(value) is None:
            problems.append((f'{name}: "bundled.{key}" {value!r} is not x.y.z', f"{where}.bundled.{key}"))
    if got["fixed_date"] and not DATE_RE.match(got["fixed_date"]):
        problems.append((f'{name}: "bundled.fixed_date" is not YYYY-MM-DD', f"{where}.bundled.fixed_date"))
    if _placeholder(entry.reason):
        problems.append((f"{name}: a bundled-class entry needs its own reason", f"{where}.reason"))
    found: list[tuple[str, str]] = []
    reviewed, review_by = _date(raw, "reviewed", found), _date(raw, "review_by", found)
    problems += [(f"{name}: {message}", f"{where}.{key}") for message, key in found]
    base = (entry.identifier, entry.package, entry.severity, entry.origin, entry.reason)
    return Entry(*base, Bundled(**got), reviewed, review_by)


def parse_baseline(text: str, path: str) -> Baseline:
    """A baseline from its JSON. Unreadable shapes raise; readable defects become `problems`."""
    try:
        doc = json.loads(text)
    except ValueError as exc:
        raise ParseError(f"{path} is not JSON: {exc}") from exc
    if not isinstance(doc, dict) or not isinstance(doc.get("origins"), dict):
        raise ParseError(f'{path} has no "origins" object')
    if not isinstance(doc.get("findings"), list):
        raise ParseError(f'{path} has no "findings" list')
    b = Baseline(path, str(doc.get("image") or ""), str(doc.get("base_digest") or ""))
    b.origins = {str(k): str(v) for k, v in doc["origins"].items()}
    b.reviewed, b.review_by = _date(doc, "reviewed", b.problems), _date(doc, "review_by", b.problems)
    b.problems += [
        (f"origin {o!r} has no reason", f"origins.{o}") for o, r in b.origins.items() if _placeholder(r)
    ]
    seen: set[tuple[str, str]] = set()
    for n, raw in enumerate(doc["findings"]):
        entry = _entry(raw, n, b.origins, b.problems)
        if entry is None:
            continue
        if entry.key in seen:
            b.problems.append(
                (f"findings[{n}] repeats {entry.identifier} in {entry.package}", f"findings[{n}]")
            )
        seen.add(entry.key)
        b.entries.append(entry)
    return b


def load_baseline(path: Path, label: str) -> Baseline:
    """The baseline file, or an absent one. An absent baseline accepts nothing and is no defect."""
    if not path.exists():
        return Baseline(label, present=False)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ParseError(f"{label} unreadable: {exc}") from exc
    return parse_baseline(text, label)


def defects(b: Baseline, image: str, digest: str, today: dt.date) -> list[tuple[str, str, str]]:
    """(message, date, field) for each reason the baseline cannot accept anything today."""
    if b.unreadable:
        return [(b.unreadable, "", "the whole file")]
    out = [(m, "", f) for m, f in b.problems]
    repo = image.split(":", 1)[0]
    if b.image != repo:
        out.append((f'"image" is {b.image or "(none)"!r}, this scan is of {repo!r}', "", "image"))
    if b.base_digest != digest:
        said = f"recorded for base digest {b.base_digest[:19] or '(none)'}, the image uses {digest[:19]}"
        out.append((f"{said}: a moved digest means a new review", "", "base_digest"))
    if b.reviewed and b.reviewed > today:
        out.append((f'"reviewed" {b.reviewed} is in the future', str(b.reviewed), "reviewed"))
    if b.review_by and b.review_by < today:
        out.append((f"overdue since {b.review_by}: a person re-reviews it", str(b.review_by), "review_by"))
    if b.reviewed and b.review_by and b.review_by - b.reviewed > CAP:
        latest = b.reviewed + CAP
        out.append(
            (
                f"review date {b.review_by} exceeds the 90-day cap (latest {latest})",
                str(b.review_by),
                "review_by",
            )
        )
    return out


def _review(b: Baseline) -> str:
    return (
        f'have a person re-review {b.path}: set "reviewed" to that day and "review_by" at most 90 days after'
    )


def _upgrade(v: Vuln, image: str, fixed: str) -> str:
    """The exact edit a fix asks for. A Go finding is fixed in the source, not in the image."""
    if v.source == "govulncheck" and v.package == "stdlib":
        return f"pins.env: GO_IMAGE to a Go {fixed} or later image (its digest too), then rebuild {image}"
    if v.source == "govulncheck":
        return f"adele/go.mod: require {v.package} {fixed} or later (go get), then rebuild {image}"
    return f"rebuild {image} with {v.package} at {fixed} or later"


def _fixable(v: Vuln, hit: Entry | None, image: str, b: Baseline) -> Finding:
    fixed = ", ".join(v.stable_fixes)
    message = f"fix available in {fixed}: upgrade {v.package} in {image}"
    update = _upgrade(v, image, fixed)
    if hit is not None:
        message += "; it is baselined, but the baseline never hides a finding that gains a fix"
        update += f"; drop {hit.identifier} in {hit.package} from {b.path}"
    return Finding(v.source, v.identifier, v.component, v.severity, message, image, "", update)


def _unlisted(v: Vuln, image: str, b: Baseline) -> Finding:
    pre = ", ".join(v.fix_versions)
    message = "no stable fix available and not in the reviewed baseline"
    if pre:
        message += (
            f" (fixed only in pre-release {pre}; if a stable release at or after it exists, upgrade instead)"
        )
    entry = f"add {v.identifier} in {v.package} (its entry is in scan/out/baseline.proposed.json)"
    update = f"{b.path}: {entry}; {_review(b)}"
    return Finding(v.source, v.identifier, v.component, v.severity, message, image, "", update)


Releases = dict[tuple[str, str], dict[str, Any]]


def _bundled_block(v: Vuln, e: Entry, bd: Bundled, today: dt.date) -> str | None:
    """Why a bundled-class entry cannot let its finding through today, or None when it can."""
    lib = e.package
    if e.reviewed and e.reviewed > today:
        return f'the entry\'s "reviewed" {e.reviewed} is in the future'
    if e.review_by and e.review_by < today:
        return f"the entry is overdue since {e.review_by}: a person re-reviews it"
    if e.reviewed and e.review_by and e.review_by - e.reviewed > BUNDLED_CAP:
        latest = e.reviewed + BUNDLED_CAP
        return f"the entry's review date {e.review_by} exceeds the 30-day cap (latest {latest})"
    seen = v.component.split(" ", 1)[1] if " " in v.component else "?"
    if seen != bd.library_version:
        return (
            f"the entry records {lib} {bd.library_version}, the image has {lib} {seen}: re-review the entry"
        )
    if v.stable_fixes and _min_version(v.stable_fixes) != bd.fixed_version:
        said = _min_version(v.stable_fixes)
        said = f"the scanner says {said}; re-review the entry"
        return f"the entry's fixed version {bd.fixed_version} disagrees: {said}"
    return None


def _min_version(versions: tuple[str, ...]) -> str:
    parsed = [(s, v) for v in versions if (s := _semver_or_none(v)) is not None]
    return min(parsed)[1] if parsed else versions[0]


def _bundled_one(
    v: Vuln,
    e: Entry,
    bd: Bundled,
    image: str,
    b: Baseline,
    today: dt.date,
    releases: Releases | None,
    verdict: Verdict,
) -> None:
    """A finding a bundled-class entry matches (discovery revision 15): it passes only on the release
    check's answer that no release of the component ships the fix. Everything else blocks."""
    lib = e.package
    base = (v.source, v.identifier, v.component, v.severity)
    date = str(e.review_by or "")
    where = f"{b.path}, the entry for {e.identifier} in {e.package}"
    blocked = _bundled_block(v, e, bd, today)
    if blocked:
        update = (
            f'{where}, fields "reviewed", "review_by" and "bundled": a person re-reviews it (30 days at most)'
        )
        verdict.blocking.append(Finding(*base, f"bundled in {bd.component}: {blocked}", image, date, update))
        return
    got = (releases or {}).get(e.key)
    fresh = got is not None and got.get("fixed_version") == bd.fixed_version
    state = str(got.get("state")) if fresh and got else ""
    if state == "no-release":
        n = len(got.get("examined") or []) if got else 0
        message = (
            f"no {bd.component} release ships {lib} {bd.fixed_version} ({n} releases checked); "
            f"baselined (bundled in {bd.component} {bd.component_version}) until {e.review_by}"
        )
        verdict.allowed.append(Finding(*base, message, image, date))
    elif state == "fix-released" and got:
        release = got.get("release")
        message = f"fix available in {bd.component} {release}, which ships {lib} {bd.fixed_version} or later"
        update = (
            f"pins.env: NPM_VERSION={release} and NPM_SHA512 (the registry's integrity, as hex), then "
            f"rebuild {image}; drop {e.identifier} in {e.package} from {b.path}"
        )
        verdict.blocking.append(Finding(*base, message, image, date, update))
    else:
        why = (got or {}).get("reason") if fresh else "no result for this entry in release-check.json"
        message = (
            f"release check could not run for {lib} bundled in {bd.component} {bd.component_version}: "
            f"{why or 'no result'}; it fails closed"
        )
        update = (
            f"run make scan where the scan can reach the {bd.component} registry ({NPM_REGISTRY}), or have a "
            f"person re-review {where}"
        )
        verdict.blocking.append(Finding(*base, message, image, date, update))


def _one(
    v: Vuln,
    image: str,
    b: Baseline,
    usable: bool,
    verdict: Verdict,
    today: dt.date,
    releases: Releases | None,
) -> Entry | None:
    """Judges one gated finding. Returns the baseline entry it matched, if any."""
    hit = b.find(v)
    base = (v.source, v.identifier, v.component, v.severity)
    if hit is not None and hit.bundled is not None:
        if not usable:
            verdict.voided += 1
        else:
            _bundled_one(v, hit, hit.bundled, image, b, today, releases, verdict)
        return hit
    if v.stable_fixes:
        verdict.blocking.append(_fixable(v, hit, image, b))
    elif hit is None:
        verdict.blocking.append(_unlisted(v, image, b))
    elif not usable:
        verdict.voided += 1
    elif v.severity == "critical" and _placeholder(hit.reason):
        where = f'{b.path}, the entry for {hit.identifier} in {hit.package}, field "reason"'
        message = f"baselined as {hit.severity}, now Critical: a Critical needs its own reason"
        verdict.blocking.append(Finding(*base, message, image, "", f"{where}; {_review(b)}"))
    else:
        pre = f"; fixed only in pre-release {', '.join(v.fix_versions)}" if v.fix_versions else ""
        until = f"no stable fix; baselined ({hit.origin}) until {b.review_by}{pre}"
        verdict.allowed.append(Finding(*base, until, image, str(b.review_by)))
    return hit


def judge(
    vulns: list[Vuln],
    b: Baseline,
    digest: str,
    today: dt.date,
    image: str = DEFAULT_IMAGE,
    releases: Releases | None = None,
) -> Verdict:
    """The H9 rule over vulnerabilities from any scanner, against one image's baseline. `releases` is
    the release check's result per bundled-class entry; None means it did not run, which blocks them."""
    verdict = Verdict()
    found = defects(b, image, digest, today) if b.present else []
    usable = b.present and not found
    matched: set[tuple[str, str]] = set()
    for v in sorted(set(vulns), key=lambda x: (x.source, x.identifier, x.component)):
        if v.severity not in GATED:
            verdict.ungated += 1
            continue
        verdict.gated += 1
        hit = _one(v, image, b, usable, verdict, today, releases)
        matched.update({hit.key} if hit else set())
    for message, date, key in found:
        where = f'{b.path}, field "{key}"'
        said = f"baseline accepts nothing: {message}"
        said += f" ({verdict.voided} findings it lists block until then)" if verdict.voided else ""
        verdict.blocking.append(
            Finding("baseline", b.path, key, "-", said, image, date, f"{where}; {_review(b)}")
        )
    stale = sum(e.key not in matched for e in b.entries)
    if stale:
        verdict.notes.append(
            f"{stale} baseline entries match no finding in this scan (drop them at the next review)"
        )
    verdict.blocking.sort()
    verdict.allowed.sort()
    return verdict


def summary_line(b: Baseline, verdict: Verdict, digest: str) -> str:
    """The one line every scan prints about what the baseline accepts."""
    if not b.present:
        return f"baseline: {b.path} — none, accepts nothing"
    if any(f.source == "baseline" for f in verdict.blocking):
        return f"baseline: {b.path} — accepts nothing until re-reviewed (see blocking)"
    counts: dict[str, int] = defaultdict(int)
    for f in verdict.allowed:
        counts[f.severity] += 1
    parts = [f"{counts[s]} {s.capitalize()}" for s in ("critical", "high", "unrated") if counts[s]]
    accepts = ", ".join(parts) or "nothing this scan"
    dates = f"reviewed {b.reviewed}, review by {b.review_by}"
    return f"baseline: {b.path} — accepts {accepts}; base digest {digest[:19]}; {dates}"


# --- origins and the proposed baseline ---------------------------------------------------------------


def origins_from_sbom(sbom: Any) -> dict[str, str]:
    """Syft artifact id → origin: "base layer", the top-level installed package(s) that pulled a deb in
    (e.g. "git"), or for other artifacts the directory they sit under."""
    layers = sbom["source"]["metadata"].get("layers") or []
    base = layers[0].get("digest") if layers else None
    arts = {a["id"]: a for a in sbom["artifacts"] if a.get("id")}  # origins only feed the proposal
    debs = {i for i, a in arts.items() if a.get("type") == "deb"}
    in_base = {i for i in debs if any(loc.get("layerID") == base for loc in arts[i].get("locations") or [])}
    added = debs - in_base
    users: dict[str, set[str]] = defaultdict(set)  # package → the added packages depending on it
    for r in sbom.get("artifactRelationships") or []:
        if r.get("type") == "dependency-of" and r.get("parent") in debs and r.get("child") in added:
            users[r["parent"]].add(r["child"])
    roots = {i for i in added if not users[i]}
    out = {i: BASE for i in in_base}
    for i in added:
        seen, stack, top = {i}, [i], set()
        while stack:
            x = stack.pop()
            top.update({arts[x]["name"]} if x in roots else set())
            fresh = users[x] - seen
            seen |= fresh
            stack += fresh
        out[i] = " + ".join(sorted(top)) or arts[i]["name"]
    for i, a in arts.items():
        if i not in debs:
            path = ((a.get("locations") or [{}])[0].get("path") or "/").strip("/").split("/")
            out[i] = "files under /" + "/".join(path[:2])
    return out


def propose(
    vulns: list[Vuln], b: Baseline, origins: dict[str, str], digest: str, image: str
) -> dict[str, Any]:
    """The baseline this scan would need: every gated finding without a stable fix, reasons carried over."""
    entries: dict[tuple[str, str], dict[str, Any]] = {}
    for v in sorted(set(vulns), key=lambda x: (x.package, x.identifier)):
        hit = b.find(v)
        bundled = hit is not None and hit.bundled is not None
        if v.severity not in GATED or (v.stable_fixes and not bundled):
            continue
        origin = origins.get(v.artifact_id) or (hit.origin if hit else "") or f"{v.source} package"
        item: dict[str, Any] = {"id": v.identifier, "package": v.package, "severity": v.severity}
        item["origin"] = origin
        if v.severity == "critical":
            item["reason"] = hit.reason if hit and not _placeholder(hit.reason) else PLACE_CRITICAL
        if hit is not None and hit.bundled is not None:  # carried over whole: a person reviewed it
            item["reason"] = hit.reason
            item["bundled"] = asdict(hit.bundled)
            item["reviewed"], item["review_by"] = str(hit.reviewed), str(hit.review_by)
        elif v.fix_versions:  # only pre-releases, or it would have a stable fix and not be here
            item["note"] = (
                f"fixed in pre-release {', '.join(v.fix_versions)}: upgrade if a stable release has it"
            )
        entries.setdefault((v.identifier.lower(), v.package.lower()), item)
    used = sorted({e["origin"] for e in entries.values()})
    reasons = {o: b.origins[o] if not _placeholder(b.origins.get(o)) else PLACE_ORIGIN for o in used}
    return {
        "image": image.split(":", 1)[0],
        "base_digest": digest,
        "reviewed": PLACE_REVIEWED,
        "review_by": PLACE_REVIEW_BY,
        "origins": reasons,
        "findings": list(entries.values()),
    }


# --- the release check for bundled-class entries (discovery revision 15) --------------------------------


SEMVER_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")
PARTIAL_RE = re.compile(r"^v?(\d+|[xX*])(?:\.(\d+|[xX*]))?(?:\.(\d+|[xX*]))?$")
COMPARATOR_RE = re.compile(r"^(>=|<=|>|<|=|\^|~)?\s*(.*)$")
Version = tuple[int, int, int]


def _semver_or_none(text: str) -> Version | None:
    m = SEMVER_RE.match(text.strip())
    return (int(m[1]), int(m[2]), int(m[3])) if m else None


def _partial(text: str) -> list[int]:
    """The numbers of a partial version ("24", "24.21", "24.x"): fewer than three means a wildcard."""
    m = PARTIAL_RE.match(text)
    if not m:
        raise ValueError(f"not a version: {text!r}")
    out: list[int] = []
    for part in m.groups():
        if part is None or part in "xX*":
            break
        out.append(int(part))
    return out


def _bump(nums: list[int]) -> Version:
    """The first version above every version the partial `nums` covers (24.21 → 24.22.0)."""
    if not nums:
        return (1 << 30, 0, 0)
    return _floor([*nums[:-1], nums[-1] + 1])


def _floor(nums: list[int]) -> Version:
    padded = [*nums, 0, 0, 0]
    return padded[0], padded[1], padded[2]


def _comparator(text: str) -> tuple[Version, Version]:
    """[low, high) for one comparator. Pre-release tags are refused: a range with one is unparseable."""
    m = COMPARATOR_RE.match(text)
    if m is None:
        raise ValueError(f"not a comparator: {text!r}")
    op, rest = m[1] or "", m[2]
    nums = _partial(rest)
    lo, hi = (0, 0, 0), (1 << 30, 0, 0)
    if op in ("", "="):  # 24.21 covers 24.21.x; 24.21.0 covers itself
        return _floor(nums), _bump(nums)
    if op == ">=":
        return _floor(nums), hi
    if op == ">":
        return _bump(nums), hi
    if op == "<":
        return lo, _floor(nums)
    if op == "<=":
        return lo, _bump(nums)
    if op == "~":
        return _floor(nums), _bump(nums[:2] if len(nums) >= 2 else nums)
    # ^: the left-most non-zero part may not change
    first = next((i for i, n in enumerate(nums) if n != 0), len(nums) - 1)
    return _floor(nums), _bump(nums[: first + 1]) if nums else hi


def engines_admit(spec: str, node: str) -> bool:
    """Whether an npm `engines` range admits the exact version `node`. Raises ValueError when the range
    uses anything this reader does not know, so the caller can fail closed instead of guessing."""
    have = _semver_or_none(node)
    if have is None:
        raise ValueError(f"not an exact version: {node!r}")
    for alternative in spec.split("||"):
        text = alternative.strip()
        if text in ("", "*", "x", "X"):
            return True
        if " - " in text:
            left, right = (s.strip() for s in text.split(" - ", 1))
            ranges = [(_floor(_partial(left)), _bump(_partial(right)))]
        else:
            parts = re.findall(r"(?:>=|<=|>|<|=|\^|~)?\s*[^\s<>=^~]+", text)
            if not parts or "".join(p.replace(" ", "") for p in parts) != text.replace(" ", ""):
                raise ValueError(f"unparseable range: {text!r}")
            ranges = [_comparator(p.strip()) for p in parts]
        if all(lo <= have < hi for lo, hi in ranges):
            return True
    return False


def _fetch(url: str) -> bytes:
    if not url.startswith(("https://", "file://")):  # the registry, or a test's file-served one
        raise OSError(f"refusing to fetch {url!r}: only https:// and file:// are read")
    req = urllib.request.Request(url, headers={"User-Agent": "timelike-scan release-check"})  # noqa: S310
    with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310
        data: bytes = resp.read()
    return data


def _bundled_copies(tarball: bytes, library: str) -> list[str]:
    """Every version of `library` an npm release tarball bundles, nested copies included."""
    name = re.compile(rf"^package/(?:.*/)?node_modules/{re.escape(library)}/package\.json$")
    found: list[str] = []
    with tarfile.open(fileobj=io.BytesIO(tarball), mode="r:gz") as tar:
        for member in tar:
            if member.isfile() and name.match(member.name):
                handle = tar.extractfile(member)
                if handle is None:
                    raise ValueError(f"{member.name} could not be read")
                found.append(str(json.loads(handle.read())["version"]))
    return found


class _Npm:
    """npm's released manifests: the registry's packument, and each candidate release's tarball, checked
    against its published integrity before it is read. Never a branch, never a pre-release."""

    def __init__(self, registry: str, node: str) -> None:
        self.registry, self.node = registry.rstrip("/"), node
        self.packument: dict[str, Any] | None = None
        self.tarballs: dict[str, bytes] = {}

    def _doc(self) -> dict[str, Any]:
        if self.packument is None:
            try:
                doc = json.loads(_fetch(f"{self.registry}/npm"))
            except (OSError, ValueError) as exc:
                raise LookupError(f"could not read npm's packument from {self.registry}: {exc}") from exc
            if not isinstance(doc, dict):
                raise LookupError("npm's packument is not an object")
            self.packument = doc
        return self.packument

    def candidates(self, since: str) -> list[str]:
        """Stable, non-deprecated releases published on or after `since` whose engines admit the Node."""
        doc = self._doc()
        versions, times = doc.get("versions"), doc.get("time")
        if not isinstance(versions, dict) or not isinstance(times, dict):
            raise LookupError("npm's packument has no versions or time map")
        out: list[tuple[Version, str]] = []
        for version, manifest in versions.items():
            parsed = _semver_or_none(version)
            if parsed is None or manifest.get("deprecated") or str(times.get(version, ""))[:10] < since:
                continue
            spec = str((manifest.get("engines") or {}).get("node") or "")
            try:
                if not engines_admit(spec, self.node):
                    continue
            except ValueError as exc:
                raise LookupError(f"npm {version}'s engines range is unreadable ({exc})") from exc
            out.append((parsed, version))
        return [v for _, v in sorted(out)]

    def copies(self, version: str, library: str) -> list[str]:
        if version not in self.tarballs:
            dist = self._doc()["versions"][version].get("dist") or {}
            integrity = str(dist.get("integrity") or "")
            if not integrity.startswith("sha512-"):
                raise LookupError(f"npm {version} publishes no sha512 integrity")
            try:
                data = _fetch(str(dist["tarball"]))
            except (OSError, KeyError) as exc:
                raise LookupError(f"could not download npm {version}: {exc}") from exc
            if base64.b64encode(hashlib.sha512(data).digest()).decode() != integrity[len("sha512-") :]:
                raise LookupError(f"npm {version}'s tarball does not match its integrity")
            self.tarballs[version] = data
        try:
            return _bundled_copies(self.tarballs[version], library)
        except (tarfile.TarError, OSError, ValueError, KeyError) as exc:
            raise LookupError(f"npm {version}'s tarball could not be read: {exc}") from exc


# What a component's reader would need, for a component the check does not read yet. Each answers unknown,
# which blocks (fails closed), until its reader exists.
NOT_YET = {
    "pip": (
        "the release check reads npm's registry only; pip needs PyPI's JSON (/pypi/pip/json) for stable "
        "releases whose requires_python admits the agent interpreter, and each candidate wheel's "
        "pip/_vendor/vendor.txt"
    ),
}


def check_entry(e: Entry, bd: Bundled, npm: _Npm) -> dict[str, Any]:
    """One bundled-class entry's answer: no-release, fix-released (naming the release) or unknown."""
    result: dict[str, Any] = {
        "id": e.identifier,
        "package": e.package,
        "component": bd.component,
        "component_version": bd.component_version,
        "fixed_version": bd.fixed_version,
        "state": "unknown",
        "release": "",
        "reason": "",
        "examined": [],
    }
    if bd.component != "npm":
        result["reason"] = NOT_YET.get(
            bd.component, f"the release check does not read {bd.component!r} releases"
        )
        return result
    fixed = _semver_or_none(bd.fixed_version)
    try:
        for version in npm.candidates(bd.fixed_date):
            result["examined"].append(version)
            copies = npm.copies(version, e.package)
            parsed = [_semver_or_none(c) for c in copies]
            if any(p is None for p in parsed):
                raise LookupError(f"npm {version} bundles {e.package} at a version this check cannot read")
            if fixed is not None and all(p is not None and p >= fixed for p in parsed):
                result["state"], result["release"] = "fix-released", version
                said = ", ".join(copies) if copies else f"does not bundle {e.package}"
                result["reason"] = f"npm {version}: {said}"
                return result
    except LookupError as exc:
        result["reason"] = str(exc)
        return result
    result["state"] = "no-release"
    result["reason"] = f"no stable npm release since {bd.fixed_date} admitting Node {npm.node} ships it"
    return result


def releases(baseline: Path, out: Path, node: str, registry: str) -> int:
    """Prints `<n> <summary>` for scan.sh and writes every bundled-class entry's answer to `out`."""
    b = load_baseline(baseline, str(baseline))
    npm = _Npm(registry, node)
    results = [check_entry(e, e.bundled, npm) for e in b.entries if e.bundled is not None]
    doc = {"registry": registry, "node": node, "results": results}
    out.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    if not results:
        print(f"0 no bundled-class entries in {baseline.name}")
        return 0
    states: dict[str, int] = defaultdict(int)
    for r in results:
        states[r["state"]] += 1
    said = ", ".join(f"{n} {s}" for s, n in sorted(states.items()))
    examined = sorted(
        {v for r in results for v in r["examined"]}, key=lambda v: _semver_or_none(v) or (0, 0, 0)
    )
    print(
        f"{len(results)} bundled-class entries checked against npm's released tarballs "
        f"(Node {node}; releases examined: {', '.join(examined) or 'none'}): {said}"
    )
    return 0


# --- scanner outputs ---------------------------------------------------------------------------------


def grype_vulns(grype_json: Any) -> list[Vuln]:
    if not isinstance(grype_json, dict) or not isinstance(grype_json.get("matches"), list):
        raise ParseError("grype JSON has no matches list")
    out: list[Vuln] = []
    for m in grype_json["matches"]:
        vul, art = m.get("vulnerability") or {}, m.get("artifact") or {}
        if not vul.get("id"):
            raise ParseError("grype match without a vulnerability id")
        fix = vul.get("fix") or {}
        fixed = tuple(str(x) for x in fix.get("versions") or []) if fix.get("state") == "fixed" else ()
        aliases = tuple(str(r["id"]) for r in m.get("relatedVulnerabilities") or [] if r.get("id"))
        comp = f"{art.get('name', '?')} {art.get('version', '?')}"
        severity = str(vul.get("severity") or "unknown").lower()
        out.append(Vuln("grype", str(vul["id"]), aliases, comp, severity, fixed, str(art.get("id") or "")))
    return out


def pip_audit_vulns(doc: Any, notes: list[str], source: str = "pip-audit") -> list[Vuln]:
    """pip-audit's findings, named by the step that produced them, so each blocks on its own line."""
    if not isinstance(doc, dict) or not isinstance(doc.get("dependencies"), list):
        raise ParseError(f"{source} JSON has no dependencies list")
    out: list[Vuln] = []
    for dep in doc["dependencies"]:
        comp = f"{dep.get('name', '?')} {dep.get('version', '?')}"
        if dep.get("skip_reason"):
            notes.append(f"{source} skipped {comp}: {dep['skip_reason']}")
        for v in dep.get("vulns") or []:
            aliases = tuple(str(a) for a in v.get("aliases") or [])
            fixes = tuple(str(x) for x in v.get("fix_versions") or [])
            out.append(Vuln(source, str(v["id"]), aliases, comp, "unrated", fixes))
    return out


def json_stream(text: str, name: str) -> list[Any]:
    """Concatenated JSON values, as govulncheck -format json writes them (indented, one per message)."""
    decoder, i = json.JSONDecoder(), 0
    out: list[Any] = []
    while True:
        while i < len(text) and text[i].isspace():
            i += 1
        if i == len(text):
            return out
        try:
            value, i = decoder.raw_decode(text, i)
        except ValueError as exc:
            raise ParseError(f"{name} is not a JSON stream: {exc}") from exc
        out.append(value)


def govulncheck_vulns(messages: list[Any]) -> list[Vuln]:
    """One Vuln per (OSV id, module), at the deepest level any of its findings reached (GO_LEVELS).

    A stream with no govulncheck `config` message is no evidence of a scan, so it is an error (H3).
    """
    if not all(isinstance(m, dict) for m in messages):
        raise ParseError("govulncheck JSON has a message that is not an object")
    config: dict[str, Any] = next((m["config"] for m in messages if isinstance(m.get("config"), dict)), {})
    if config.get("scanner_name") != "govulncheck":
        raise ParseError("govulncheck JSON has no govulncheck config message, so no scan is shown")
    aliases = {
        str(m["osv"]["id"]): tuple(str(a) for a in m["osv"].get("aliases") or [])
        for m in messages
        if isinstance(m.get("osv"), dict) and m["osv"].get("id")
    }
    deepest: dict[tuple[str, str], tuple[int, str, str]] = {}  # (osv, module) → (level, version, fix)
    for m in messages:
        if "finding" not in m:
            continue
        f = m["finding"]
        trace = f.get("trace") if isinstance(f, dict) else None
        if not isinstance(f, dict) or not f.get("osv") or not trace or not isinstance(trace[0], dict):
            raise ParseError("govulncheck finding without an osv id or a trace")
        frame = trace[0]
        level = 2 if frame.get("function") else 1 if frame.get("package") else 0
        key = (str(f["osv"]), str(frame.get("module") or "?"))
        found = (level, str(frame.get("version") or "?"), str(f.get("fixed_version") or ""))
        if key not in deepest or found[0] > deepest[key][0]:
            deepest[key] = found
    return [
        Vuln("govulncheck", osv, aliases.get(osv, ()), f"{mod} {ver}", GO_LEVELS[lvl], (fix,) if fix else ())
        for (osv, mod), (lvl, ver, fix) in sorted(deepest.items())
    ]


def gitleaks_findings(doc: Any) -> list[Finding]:
    if not isinstance(doc, list):
        raise ParseError("gitleaks report is not a JSON list")
    return [
        Finding(
            "gitleaks",
            str(f.get("RuleID", "?")),
            f"{f.get('File', '?')}:{f.get('StartLine', '?')} @ {str(f.get('Commit', ''))[:12]}",
            "-",
            f"committed secret: {f.get('Description') or f.get('RuleID', '?')}",
            "repository",
            "",
            f"remove {f.get('File', '?')} from git history (commit {str(f.get('Commit', ''))[:12]}) "
            "and rotate the secret; deleting it in a new commit is not enough",
        )
        for f in doc
    ]


def _load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ParseError(f"{path.name} unreadable: {exc}") from exc


STEPS = ("sbom", "grype", "pip-audit", "pip-audit-agent", "release-check", "govulncheck", "gitleaks")


@dataclass
class Collected:
    """The steps' results. errors[step] is "" when the step ran (or had nothing to do) and parsed."""

    errors: dict[str, str] = field(default_factory=dict)
    details: dict[str, str] = field(default_factory=dict)
    vulns: list[Vuln] = field(default_factory=list)
    secrets: list[Finding] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    origins: dict[str, str] = field(default_factory=dict)
    releases: Releases | None = None  # None: the release check did not run, so bundled entries block


def _read_step(name: str, out: Path, image_id: str, got: Collected) -> None:
    if name == "sbom":
        sbom = _load(out / "sbom.syft.json")
        seen = str(sbom["source"]["metadata"].get("imageID", ""))
        if seen != image_id:
            raise ParseError(f"SBOM describes image {seen or '(none)'}, expected {image_id} (H3)")
        got.details[name] = f"{len(sbom['artifacts'])} packages catalogued from {image_id[:19]}"
        got.origins = origins_from_sbom(sbom)
    elif name == "release-check":
        doc = _load(out / "release-check.json")
        if not isinstance(doc, dict) or not isinstance(doc.get("results"), list):
            raise ParseError("release-check.json has no results list")
        got.releases = {(str(r["id"]).lower(), str(r["package"]).lower()): r for r in doc["results"]}
    elif name == "gitleaks":
        got.secrets = gitleaks_findings(_load(out / "gitleaks.json"))
        got.details[name] = f"{len(got.secrets)} findings across git history"
    elif name == "govulncheck":
        try:
            text = (out / "govulncheck.json").read_text(encoding="utf-8")
        except OSError as exc:
            raise ParseError(f"govulncheck.json unreadable: {exc}") from exc
        found = govulncheck_vulns(json_stream(text, "govulncheck.json"))
        got.vulns += found
        reached = sum(v.severity == "high" for v in found)
        got.details[name] += f"; {len(found)} vulnerabilities, {reached} reachable"
    else:
        found = (
            grype_vulns(_load(out / "grype.json"))
            if name == "grype"
            else pip_audit_vulns(_load(out / f"{name}.json"), got.notes, name)
        )
        got.vulns += found
        got.details[name] += f"; {len(found)} matches"


def collect(out: Path, image_id: str) -> Collected:
    """Reads scan/out/steps.tsv (`step<TAB>ran|none|error<TAB>detail`, from scan.sh), then each JSON."""
    steps: dict[str, list[str]] = {}
    for row in (out / "steps.tsv").read_text(encoding="utf-8").splitlines():
        cols = row.split("\t", 2)
        steps[cols[0]] = [*cols[1:], "", ""][:2]
    got = Collected()
    for name in STEPS:
        state, detail = steps.get(name, ["error", "the step recorded no result"])
        got.errors[name], got.details[name] = "", detail
        if state not in ("ran", "none"):
            got.errors[name] = detail or "the step failed"
        elif state == "ran":
            try:
                _read_step(name, out, image_id, got)
            except ParseError as exc:
                got.errors[name] = str(exc)
            except (AttributeError, KeyError, TypeError, IndexError) as exc:
                got.errors[name] = f"malformed result: {type(exc).__name__} {exc}"
    return got


def _line(f: Finding) -> str:
    """One finding on one line: what, where, and (when it blocks) the exact edit that unblocks it."""
    where = f"{f.component} in {f.image}" if f.image else f.component
    text = f"  {f.source}  {f.identifier}  {f.severity}  {where} — {f.message}"
    return text + (f" → update: {f.update}" if f.update else "")


@dataclass(frozen=True)
class Target:
    """What is being scanned, and against which baseline."""

    image: str
    image_id: str
    base_digest: str
    baseline: Path
    label: str


def _rows(got: Collected, verdict: Verdict, b: Baseline, error: str) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    for name in (*STEPS, "baseline"):
        mine = [f for f in verdict.blocking if f.source == name]
        err = got.errors.get(name, error if name == "baseline" else "")
        if name == "baseline":
            detail = f"{len(b.entries)} entries" if b.present else "none"
        else:
            detail = got.details.get(name, "")
        accepted = sum(f.source == name for f in verdict.allowed)
        detail += f"; {len(mine)} blocking" if mine else ""
        detail += f"; {accepted} baselined" if accepted else ""
        rows.append((name, "FAIL" if err or mine else "PASS", err or detail))
    return rows


def report(out: Path, target: Target, today: dt.date) -> int:
    got = collect(out, target.image_id)
    try:
        b, error = load_baseline(target.baseline, target.label), ""
    except ParseError as exc:
        b, error = Baseline(target.label, unreadable=str(exc)), str(exc)
    verdict = judge(got.vulns, b, target.base_digest, today, target.image, got.releases)
    verdict.blocking = sorted(verdict.blocking + got.secrets)
    rows = _rows(got, verdict, b, error)
    word = "PASS" if all(r[1] == "PASS" for r in rows) and verdict.passed else "FAIL"
    summary = summary_line(b, verdict, target.base_digest)
    text = [
        f"scan: {target.image} [supply-chain] — {word}",
        *(f"  {n:<17}{s:<6}{d}" for n, s, d in rows),
        summary,
    ]
    text += ["blocking:", *map(_line, verdict.blocking)] if verdict.blocking else []
    text += ["baselined:", *map(_line, verdict.allowed)] if verdict.allowed else []
    notes = got.notes + verdict.notes + [f"{verdict.ungated} matches below High (never block)"]
    text += [f"note: {n}" for n in notes]
    if not got.errors.get("grype"):
        proposal = propose(got.vulns, b, got.origins, target.base_digest, target.image)
        (out / "baseline.proposed.json").write_text(json.dumps(proposal, indent=2) + "\n", encoding="utf-8")
    result = {
        "image": target.image,
        "image_id": target.image_id,
        "base_digest": target.base_digest,
        "verdict": word,
        "today": today.isoformat(),
        "rule": RULE,
        "review_cap_days": CAP.days,
        "baseline": {"path": b.path, "present": b.present, "entries": len(b.entries), "summary": summary},
        "steps": [{"name": n, "status": s, "detail": d} for n, s, d in rows],
        "blocking": [asdict(f) for f in verdict.blocking],
        "baselined": [asdict(f) for f in verdict.allowed],
        "notes": notes,
    }
    (out / "verdict.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    sys.stdout.write("\n".join(text) + "\n")
    return 0 if word == "PASS" else 1


def dists(out: Path, requirements: Path | None = None) -> int:
    """Prints `<count> <purelib>` for scan.sh, and records the list itself in `out` (and, when asked,
    as `name==version` lines in `requirements`, which pip-audit audits with --no-deps --disable-pip)."""
    found = sorted({(d.metadata["Name"], d.version) for d in importlib.metadata.distributions()})
    out.write_text(json.dumps([{"name": n, "version": v} for n, v in found]) + "\n", encoding="utf-8")
    if requirements is not None:
        requirements.write_text("".join(f"{n}=={v}\n" for n, v in found), encoding="utf-8")
    print(len(found), sysconfig.get_path("purelib"))
    return 0


def _digest(value: str) -> str:
    if not DIGEST_RE.match(value):
        raise argparse.ArgumentTypeError(f"{value!r} is not a sha256:<64 hex> digest")
    return value


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="evaluate.py", description="supply-chain gate evaluator (H9)")
    sub = parser.add_subparsers(dest="cmd", required=True)
    dis = sub.add_parser("dists")
    dis.add_argument("--out", type=Path, required=True)
    dis.add_argument("--requirements", type=Path, help="also write the list as name==version lines here")
    rel = sub.add_parser("releases", help="the bundled-class release check (uses the network)")
    rel.add_argument("--baseline", type=Path, required=True)
    rel.add_argument("--out", type=Path, required=True, help="where to write release-check.json")
    rel.add_argument("--node-version", required=True, help="the pinned Node (pins.env NODE_VERSION)")
    rel.add_argument("--registry", default=NPM_REGISTRY)
    rep = sub.add_parser("report")
    rep.add_argument("--out", type=Path, required=True, help="the scan/out directory")
    rep.add_argument("--baseline", type=Path, required=True, help="scan/baseline/<image>.json")
    rep.add_argument(
        "--baseline-label", help="the path to name in escalations (default: scan/baseline/<file>)"
    )
    rep.add_argument("--base-digest", type=_digest, required=True, help="the pinned base image digest")
    rep.add_argument("--image", required=True)
    rep.add_argument("--image-id", required=True)
    rep.add_argument("--today", type=dt.date.fromisoformat, default=dt.date.today())
    args = parser.parse_args(argv)
    try:
        if args.cmd == "dists":
            return dists(args.out, args.requirements)
        if args.cmd == "releases":
            return releases(args.baseline, args.out, args.node_version, args.registry)
        label = args.baseline_label or f"scan/baseline/{args.baseline.name}"
        target = Target(args.image, args.image_id, args.base_digest, args.baseline, label)
        return report(args.out, target, args.today)
    except Exception as exc:  # an uncaught crash would exit 1, which scan.sh reads as a verdict
        print(f"error: evaluate.py {args.cmd} failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
