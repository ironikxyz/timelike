"""The supply-chain gate's rules (constitution H9, discovery revision 5), over sample baselines and
synthetic Grype, pip-audit, govulncheck, gitleaks and Syft JSON.

scan/evaluate.py is not a package, so it is loaded from its path. These tests hold the pure logic
only. Whether the scanners run and write what evaluate.py expects is the Docker lane's to show.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[2]
TODAY = dt.date(2026, 9, 28)
IMAGE = "timelike-agent:local"
DIGEST = "sha256:" + "a9" * 32
PATH = "scan/baseline/timelike-agent.json"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("scan_evaluate", REPO / "scan" / "evaluate.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses resolve their module through sys.modules
    spec.loader.exec_module(module)
    return module


ev = _load()


def match(
    vid: str,
    severity: str = "High",
    state: str = "wont-fix",
    versions: list[str] | None = None,
    name: str = "libfoo",
    related: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "vulnerability": {
            "id": vid,
            "severity": severity,
            "fix": {"state": state, "versions": versions or []},
        },
        "relatedVulnerabilities": [{"id": r} for r in related or []],
        "artifact": {"id": f"art-{name}", "name": name, "version": "1.0", "type": "deb"},
    }


def entry(vid: str = "CVE-2026-1111", package: str = "libfoo", **extra: str) -> dict[str, str]:
    return {"id": vid, "package": package, "severity": "high", "origin": BASE_LAYER, **extra}


BASE_LAYER = "base layer"


def doc(*findings: dict[str, Any], **top: Any) -> dict[str, Any]:
    baseline = {
        "image": "timelike-agent",
        "base_digest": DIGEST,
        "reviewed": "2026-09-20",
        "review_by": "2026-12-01",
        "origins": {BASE_LAYER: "no fix in trixie; not reachable from the agent's use"},
        "findings": list(findings) if findings else [entry()],
    }
    baseline.update(top)
    return baseline


def baseline(*findings: dict[str, Any], **top: Any) -> Any:
    return ev.parse_baseline(json.dumps(doc(*findings, **top)), PATH)


def verdict_for(*matches: dict[str, Any], b: Any = None, today: dt.date = TODAY) -> Any:
    vulns = ev.grype_vulns({"matches": list(matches) or [match("CVE-2026-1111")]})
    return ev.judge(vulns, b if b is not None else baseline(), DIGEST, today, IMAGE)


# --- the baseline accepts ------------------------------------------------------------------------------


def test_reviewed_baseline_accepts_an_unfixable_high() -> None:
    verdict = verdict_for()
    assert verdict.passed
    (allowed,) = verdict.allowed
    assert allowed.message == "no stable fix; baselined (base layer) until 2026-12-01"
    assert allowed.date == "2026-12-01"


def test_baseline_matches_through_a_related_alias() -> None:
    assert verdict_for(match("GHSA-aaaa-bbbb-cccc", related=["CVE-2026-1111"])).passed


def test_baseline_entry_is_for_one_package_only() -> None:
    verdict = verdict_for(match("CVE-2026-1111", name="libbar"))
    (block,) = verdict.blocking
    assert block.message == "no stable fix available and not in the reviewed baseline"


def test_baseline_due_today_still_holds() -> None:
    assert verdict_for(b=baseline(review_by="2026-09-28")).passed


def test_review_date_exactly_90_days_after_review_passes() -> None:
    assert verdict_for(b=baseline(reviewed="2026-09-28", review_by="2026-12-27")).passed


def test_a_critical_with_its_own_reason_is_accepted() -> None:
    b = baseline(entry(severity="critical", reason="only reachable with a client certificate, never used"))
    assert verdict_for(match("CVE-2026-1111", "Critical"), b=b).passed


def test_a_fix_only_in_a_pre_release_can_be_baselined_and_says_so() -> None:
    verdict = verdict_for(match("CVE-2026-1111", state="fixed", versions=["3.14.0b1"]))
    (allowed,) = verdict.allowed
    assert allowed.message.endswith("; fixed only in pre-release 3.14.0b1")


@pytest.mark.parametrize("severity", ["Medium", "Low", "Negligible", "Unknown"])
def test_below_high_never_blocks(severity: str) -> None:
    verdict = verdict_for(match("CVE-2026-9999", severity, state="fixed", versions=["2.0"]), b=baseline())
    assert verdict.passed and verdict.ungated == 1


# --- the baseline never hides a change ---------------------------------------------------------------


def test_a_finding_not_in_the_baseline_blocks_and_names_the_file_and_the_proposal() -> None:
    (block,) = verdict_for(match("CVE-2026-2222")).blocking
    assert block.message == "no stable fix available and not in the reviewed baseline"
    assert block.update == (
        f"{PATH}: add CVE-2026-2222 in libfoo (its entry is in scan/out/baseline.proposed.json); "
        f'have a person re-review {PATH}: set "reviewed" to that day and "review_by" at most 90 days after'
    )


def test_a_pre_release_only_fix_not_in_the_baseline_says_to_upgrade_if_it_can() -> None:
    (block,) = verdict_for(match("CVE-2026-2222", state="fixed", versions=["3.14.0rc2"])).blocking
    assert "fixed only in pre-release 3.14.0rc2; if a stable release at or after it exists" in block.message


def test_a_baselined_finding_that_gains_a_fix_blocks() -> None:
    (block,) = verdict_for(match("CVE-2026-1111", state="fixed", versions=["1.1"])).blocking
    assert block.message == (
        f"fix available in 1.1: upgrade libfoo in {IMAGE}; it is baselined, "
        "but the baseline never hides a finding that gains a fix"
    )
    assert (
        block.update
        == f"rebuild {IMAGE} with libfoo at 1.1 or later; drop CVE-2026-1111 in libfoo from {PATH}"
    )


def test_a_fixable_critical_names_the_upgrade() -> None:
    (block,) = verdict_for(match("CVE-2026-3333", "Critical", state="fixed", versions=["2.0"])).blocking
    assert block.update == f"rebuild {IMAGE} with libfoo at 2.0 or later"


def test_a_baselined_high_that_became_critical_needs_its_own_reason() -> None:
    (block,) = verdict_for(match("CVE-2026-1111", "Critical")).blocking
    assert block.message == "baselined as high, now Critical: a Critical needs its own reason"
    assert block.update.startswith(f'{PATH}, the entry for CVE-2026-1111 in libfoo, field "reason"')


def test_blocking_findings_are_sorted() -> None:
    verdict = verdict_for(match("CVE-2026-5"), match("CVE-2026-3"), match("CVE-2026-4"))
    assert [f.identifier for f in verdict.blocking] == ["CVE-2026-3", "CVE-2026-4", "CVE-2026-5"]


def test_an_entry_matching_nothing_is_a_note_not_a_block() -> None:
    verdict = verdict_for(match("CVE-2026-1111"), b=baseline(entry(), entry("CVE-2026-7777")))
    assert verdict.passed
    assert verdict.notes == [
        "1 baseline entries match no finding in this scan (drop them at the next review)"
    ]


# --- when the baseline accepts nothing ---------------------------------------------------------------


def _only_defect(b: Any, today: dt.date = TODAY) -> Any:
    verdict = verdict_for(b=b, today=today)
    (defect,) = verdict.blocking
    assert defect.source == "baseline" and defect.identifier == PATH
    assert verdict.allowed == []
    assert "(1 findings it lists block until then)" in defect.message
    return defect


def test_overdue_baseline_accepts_nothing_and_names_the_date_and_field() -> None:
    defect = _only_defect(baseline(review_by="2026-09-27"))
    assert defect.message.startswith("baseline accepts nothing: overdue since 2026-09-27")
    assert defect.date == "2026-09-27"
    assert defect.update.startswith(f'{PATH}, field "review_by"; have a person re-review')


def test_review_date_91_days_after_review_exceeds_the_cap() -> None:
    defect = _only_defect(baseline(reviewed="2026-09-28", review_by="2026-12-28"))
    assert "review date 2026-12-28 exceeds the 90-day cap (latest 2026-12-27)" in defect.message


def test_reviewed_in_the_future_is_a_defect() -> None:
    defect = _only_defect(baseline(reviewed="2026-09-29", review_by="2026-10-01"))
    assert '"reviewed" 2026-09-29 is in the future' in defect.message
    assert defect.date == "2026-09-29"


def test_a_moved_base_digest_means_a_new_review() -> None:
    defect = _only_defect(baseline(base_digest="sha256:" + "00" * 32))
    assert "a moved digest means a new review" in defect.message
    assert defect.component == "base_digest"


def test_a_baseline_for_another_image_accepts_nothing() -> None:
    defect = _only_defect(baseline(image="adele"))
    assert "\"image\" is 'adele', this scan is of 'timelike-agent'" in defect.message


@pytest.mark.parametrize(
    ("change", "said", "key"),
    [
        ({"reviewed": "<YYYY-MM-DD: the day a person reviews this baseline>"}, '"reviewed"', "reviewed"),
        ({"review_by": ""}, '"review_by" is missing', "review_by"),
        ({"reviewed": "2026-02-30"}, "'2026-02-30' is not a YYYY-MM-DD date", "reviewed"),
        ({"origins": {BASE_LAYER: "<why>"}}, "origin 'base layer' has no reason", "origins.base layer"),
    ],
)
def test_an_unreviewed_or_malformed_top_level_field_is_a_defect(
    change: dict[str, Any], said: str, key: str
) -> None:
    defect = _only_defect(baseline(**change))
    assert said in defect.message and defect.component == key


@pytest.mark.parametrize(
    ("bad", "said", "key"),
    [
        (entry(severity="critical"), "a Critical needs its own reason", "findings[0].reason"),
        (
            entry(severity="critical", reason="<why this Critical is tolerated>"),
            "own reason",
            "findings[0].reason",
        ),
        (entry(origin="git"), "origin 'git' has no entry in \"origins\"", "origins.git"),
        (entry(severity="medium"), "'medium' is not high, critical or unrated", "findings[0].severity"),
        (entry(package=""), '"package" is missing', "findings[0].package"),
    ],
)
def test_a_malformed_entry_is_a_defect_naming_its_field(bad: dict[str, str], said: str, key: str) -> None:
    verdict = verdict_for(b=baseline(bad))
    defects = [f for f in verdict.blocking if f.source == "baseline"]
    assert any(said in f.message and f.component == key for f in defects), defects
    assert verdict.allowed == []


def test_a_repeated_entry_and_a_non_object_entry_are_defects() -> None:
    b = baseline(entry(), entry(), "CVE-2026-1")  # type: ignore[arg-type]
    assert ("findings[1] repeats CVE-2026-1111 in libfoo", "findings[1]") in b.problems
    assert ("findings[2] is not an object", "findings[2]") in b.problems


@pytest.mark.parametrize(
    ("text", "said"),
    [
        ("{not json", "is not JSON"),
        ("[]", 'has no "origins" object'),
        ('{"origins": {}}', 'has no "findings" list'),
    ],
)
def test_an_unreadable_baseline_is_a_parse_error(text: str, said: str) -> None:
    with pytest.raises(ev.ParseError, match=said):
        ev.parse_baseline(text, PATH)


def test_an_absent_baseline_accepts_nothing_and_is_no_defect(tmp_path: Path) -> None:
    b = ev.load_baseline(tmp_path / "none.json", PATH)
    assert not b.present
    verdict = verdict_for(b=b)
    (block,) = verdict.blocking
    assert block.source == "grype"
    assert ev.summary_line(b, verdict, DIGEST) == f"baseline: {PATH} — none, accepts nothing"


# --- the summary line ----------------------------------------------------------------------------------


def test_summary_line_counts_what_the_baseline_accepts() -> None:
    b = baseline(entry(), entry("CVE-2026-2", severity="critical", reason="unreachable"))
    verdict = verdict_for(match("CVE-2026-1111"), match("CVE-2026-2", "Critical"), b=b)
    assert ev.summary_line(b, verdict, DIGEST) == (
        f"baseline: {PATH} — accepts 1 Critical, 1 High; base digest {DIGEST[:19]}; "
        "reviewed 2026-09-20, review by 2026-12-01"
    )


def test_summary_line_of_an_unusable_baseline_says_it_accepts_nothing() -> None:
    b = baseline(review_by="2026-01-01")
    verdict = verdict_for(b=b)
    assert (
        ev.summary_line(b, verdict, DIGEST)
        == f"baseline: {PATH} — accepts nothing until re-reviewed (see blocking)"
    )


# --- origins, from the SBOM ----------------------------------------------------------------------------


def _art(
    aid: str, name: str, layer: str, kind: str = "deb", path: str = "/var/lib/dpkg/status"
) -> dict[str, Any]:
    return {"id": aid, "name": name, "type": kind, "locations": [{"path": path, "layerID": layer}]}


def sbom() -> dict[str, Any]:
    dep = [("libcurl", "git"), ("libperl", "perl"), ("perl", "git"), ("libc6", "git"), ("libshared", "git")]
    dep += [("libshared", "procps")]
    return {
        "source": {"metadata": {"layers": [{"digest": "L0"}, {"digest": "L1"}]}},
        "artifacts": [
            {**_art("libc6", "libc6", "L1"), "locations": [{"layerID": "L0"}, {"layerID": "L1"}]},
            _art("git", "git", "L1"),
            _art("libcurl", "libcurl3t64-gnutls", "L1"),
            _art("perl", "perl", "L1"),
            _art("libperl", "libperl5.40", "L1"),
            _art("procps", "procps", "L1"),
            _art("libshared", "libshared", "L1"),
            _art("py", "python", "L2", "binary", "/opt/uv-python/cpython-3.14.7/bin/python3.14"),
        ],
        "artifactRelationships": [{"parent": p, "child": c, "type": "dependency-of"} for p, c in dep]
        + [{"parent": "git", "child": "libc6", "type": "contains"}],
    }


def test_origins_name_the_base_layer_the_installing_package_or_the_directory() -> None:
    assert ev.origins_from_sbom(sbom()) == {
        "libc6": "base layer",
        "git": "git",
        "libcurl": "git",
        "perl": "git",
        "libperl": "git",
        "procps": "procps",
        "libshared": "git + procps",
        "py": "files under /opt/uv-python",
    }


# --- the proposed baseline -----------------------------------------------------------------------------


def test_proposal_lists_what_needs_a_baseline_and_carries_reviewed_reasons_over() -> None:
    b = baseline(entry(), entry("CVE-2026-2", severity="critical", reason="kept reason"))
    vulns = ev.grype_vulns(
        {
            "matches": [
                match("CVE-2026-1111"),
                match("CVE-2026-2", "Critical"),
                match("CVE-2026-3", "Critical", name="git"),
                match("CVE-2026-4", state="fixed", versions=["2.0"]),
                match("CVE-2026-5", "Medium"),
                match("CVE-2026-6", state="fixed", versions=["3.14.0b1"], name="python"),
            ]
        }
    )
    origins = {"art-libfoo": "base layer", "art-git": "git"}
    proposal = ev.propose(vulns, b, origins, DIGEST, IMAGE)
    assert proposal["image"] == "timelike-agent" and proposal["base_digest"] == DIGEST
    assert proposal["reviewed"].startswith("<") and proposal["review_by"].startswith("<")
    assert proposal["origins"] == {
        "base layer": "no fix in trixie; not reachable from the agent's use",
        "git": ev.PLACE_ORIGIN,
        "grype package": ev.PLACE_ORIGIN,
    }
    by_id = {f["id"]: f for f in proposal["findings"]}
    assert sorted(by_id) == ["CVE-2026-1111", "CVE-2026-2", "CVE-2026-3", "CVE-2026-6"]
    assert by_id["CVE-2026-2"]["reason"] == "kept reason"
    assert by_id["CVE-2026-3"] == {
        "id": "CVE-2026-3",
        "package": "git",
        "severity": "critical",
        "origin": "git",
        "reason": ev.PLACE_CRITICAL,
    }
    assert by_id["CVE-2026-6"]["note"].startswith("fixed in pre-release 3.14.0b1")


def test_a_proposal_filled_in_by_a_person_is_a_valid_baseline() -> None:
    vulns = ev.grype_vulns({"matches": [match("CVE-2026-1111"), match("CVE-2026-2", "Critical")]})
    absent = ev.Baseline(PATH, present=False)
    proposal = ev.propose(vulns, absent, {"art-libfoo": "base layer"}, DIGEST, IMAGE)
    proposal.update(reviewed="2026-09-28", review_by="2026-12-27", origins={"base layer": "reviewed"})
    proposal["findings"][1]["reason"] = "reviewed on its own"
    b = ev.parse_baseline(json.dumps(proposal), PATH)
    assert b.problems == []
    assert ev.judge(vulns, b, DIGEST, TODAY, IMAGE).passed


# --- the scanners --------------------------------------------------------------------------------------


def test_grype_json_without_matches_is_a_parse_error_not_a_pass() -> None:
    with pytest.raises(ev.ParseError, match="no matches list"):
        ev.grype_vulns({"descriptor": {}})


def test_grype_match_without_an_id_is_a_parse_error() -> None:
    with pytest.raises(ev.ParseError, match="without a vulnerability id"):
        ev.grype_vulns({"matches": [{"vulnerability": {}, "artifact": {}}]})


def test_pip_audit_finding_with_a_fix_blocks_and_one_without_needs_the_baseline() -> None:
    notes: list[str] = []
    report = {
        "dependencies": [
            {"name": "pip", "version": "25.0", "vulns": [{"id": "PYSEC-2026-1", "fix_versions": ["25.3"]}]},
            {
                "name": "x",
                "version": "1",
                "vulns": [{"id": "GHSA-abcd-efgh-2345", "aliases": ["CVE-2026-1111"]}],
            },
            {"name": "local", "version": "0", "skip_reason": "not on PyPI"},
        ]
    }
    vulns = ev.pip_audit_vulns(report, notes)
    b = baseline(entry(package="x", severity="unrated"))
    verdict = ev.judge(vulns, b, DIGEST, TODAY, IMAGE)
    assert [f.identifier for f in verdict.blocking] == ["PYSEC-2026-1"]
    assert verdict.blocking[0].update == f"rebuild {IMAGE} with pip at 25.3 or later"
    assert [f.identifier for f in verdict.allowed] == ["GHSA-abcd-efgh-2345"]
    assert notes == ["pip-audit skipped local 0: not on PyPI"]


def test_any_gitleaks_finding_blocks_and_names_the_remedy() -> None:
    leak = {"RuleID": "generic-api-key", "File": "a.env", "StartLine": 3, "Commit": "0123456789abcdef"}
    (finding,) = ev.gitleaks_findings(json.loads(json.dumps([leak])))
    assert finding.component == "a.env:3 @ 0123456789ab"
    assert finding.image == "repository"
    assert finding.update.startswith("remove a.env from git history (commit 0123456789ab)")
    assert ev.gitleaks_findings([]) == []


# --- govulncheck (Adele; research R5) -----------------------------------------------------------------

ADELE = "timelike-adele:local"
GO_CONFIG = {
    "config": {"protocol_version": "v1.0.0", "scanner_name": "govulncheck", "scanner_version": "v1.8.0"}
}


def gv_finding(
    osv: str = "GO-2026-4001", level: str = "function", fixed: str = "", module: str = "golang.org/x/net"
) -> dict[str, Any]:
    """A govulncheck `finding` message. trace[0] is the vulnerable frame; how far it reaches is its level."""
    frame: dict[str, str] = {"module": module, "version": "v0.40.0"}
    if level in ("package", "function"):
        frame["package"] = f"{module}/html"
    if level == "function":
        frame["function"] = "Parse"
    caller = {"module": "timelike/adele", "package": "timelike/adele/internal/grants", "function": "Load"}
    trace = [frame, caller] if level == "function" else [frame]
    return {"finding": {"osv": osv, **({"fixed_version": fixed} if fixed else {}), "trace": trace}}


def gv(*messages: dict[str, Any]) -> list[Any]:
    """The messages as govulncheck -format json writes them (indented, one after another), read back."""
    head = [GO_CONFIG, {"progress": {"message": "Scanning your code..."}}]
    osv = {"osv": {"id": "GO-2026-4001", "aliases": ["CVE-2026-4001", "GHSA-xxxx-yyyy-zzzz"]}}
    text = "\n".join(json.dumps(m, indent=2) for m in [*head, osv, *messages])
    stream: list[Any] = ev.json_stream(text, "govulncheck.json")
    return stream


def go_baseline(*findings: dict[str, Any]) -> Any:
    return baseline(*findings, image="timelike-adele")


def test_a_reachable_go_vulnerability_with_a_fix_is_a_blocking_high() -> None:
    (v,) = ev.govulncheck_vulns(gv(gv_finding(fixed="v0.41.0")))
    assert (v.source, v.identifier, v.package, v.component) == (
        "govulncheck",
        "GO-2026-4001",
        "golang.org/x/net",
        "golang.org/x/net v0.40.0",
    )
    assert (v.severity, v.fix_versions, v.aliases) == (
        "high",
        ("v0.41.0",),
        ("CVE-2026-4001", "GHSA-xxxx-yyyy-zzzz"),
    )
    verdict = ev.judge([v], go_baseline(entry("GO-2026-4001", "golang.org/x/net")), DIGEST, TODAY, ADELE)
    (block,) = verdict.blocking
    assert block.message.startswith(
        "fix available in v0.41.0: upgrade golang.org/x/net in timelike-adele:local"
    )
    assert block.message.endswith("but the baseline never hides a finding that gains a fix")
    assert block.update.startswith("adele/go.mod: require golang.org/x/net v0.41.0 or later (go get)")


def test_a_reachable_stdlib_vulnerability_with_a_fix_names_go_image() -> None:
    (v,) = ev.govulncheck_vulns(gv(gv_finding(fixed="v1.27.2", module="stdlib")))
    (block,) = ev.judge([v], go_baseline(), DIGEST, TODAY, ADELE).blocking
    assert block.update.startswith("pins.env: GO_IMAGE to a Go v1.27.2 or later image (its digest too)")


def test_a_reachable_go_vulnerability_without_a_fix_needs_the_baseline_and_matches_by_alias() -> None:
    vulns = ev.govulncheck_vulns(gv(gv_finding()))
    (block,) = ev.judge(vulns, go_baseline(), DIGEST, TODAY, ADELE).blocking
    assert block.message == "no stable fix available and not in the reviewed baseline"
    b = go_baseline(entry("CVE-2026-4001", "golang.org/x/net"))
    verdict = ev.judge(vulns, b, DIGEST, TODAY, ADELE)
    assert verdict.passed
    assert [f.identifier for f in verdict.allowed] == ["GO-2026-4001"]
    proposal = ev.propose(vulns, go_baseline(), {}, DIGEST, ADELE)
    assert proposal["findings"] == [
        {
            "id": "GO-2026-4001",
            "package": "golang.org/x/net",
            "severity": "high",
            "origin": "govulncheck package",
        }
    ]


@pytest.mark.parametrize("level", ["package", "module"])
def test_a_go_vulnerability_imported_or_required_but_not_called_never_blocks(level: str) -> None:
    (v,) = ev.govulncheck_vulns(gv(gv_finding(level=level, fixed="v0.41.0")))
    assert v.severity == {"package": "imported", "module": "required"}[level]
    verdict = ev.judge([v], go_baseline(), DIGEST, TODAY, ADELE)
    assert verdict.passed
    assert (verdict.gated, verdict.ungated) == (0, 1)
    assert ev.propose([v], go_baseline(), {}, DIGEST, ADELE)["findings"] == []


def test_one_vulnerability_found_at_every_level_counts_once_at_the_deepest() -> None:
    found = gv(gv_finding(level="module"), gv_finding(level="function"), gv_finding(level="package"))
    (v,) = ev.govulncheck_vulns(found)
    assert v.severity == "high"
    other = ev.govulncheck_vulns(gv(gv_finding(), gv_finding(module="golang.org/x/text")))
    assert [x.package for x in other] == ["golang.org/x/net", "golang.org/x/text"]


def test_a_govulncheck_stream_without_findings_has_none() -> None:
    assert ev.govulncheck_vulns(gv()) == []


@pytest.mark.parametrize(
    ("messages", "said"),
    [
        ([], "no govulncheck config message"),
        ([{"progress": {"message": "x"}}], "no govulncheck config message"),
        ([{"config": {"scanner_name": "other"}}], "no govulncheck config message"),
        ([GO_CONFIG, "text"], "a message that is not an object"),
        ([GO_CONFIG, {"finding": {"osv": "GO-2026-4001", "trace": []}}], "without an osv id or a trace"),
        ([GO_CONFIG, {"finding": {"trace": [{"module": "m"}]}}], "without an osv id or a trace"),
        ([GO_CONFIG, {"finding": "GO-2026-4001"}], "without an osv id or a trace"),
        ([GO_CONFIG, {"finding": {"osv": "GO-2026-4001", "trace": ["m"]}}], "without an osv id or a trace"),
    ],
)
def test_a_malformed_govulncheck_stream_is_a_parse_error_not_a_pass(messages: list[Any], said: str) -> None:
    with pytest.raises(ev.ParseError, match=said):
        ev.govulncheck_vulns(messages)


@pytest.mark.parametrize("text", ["{not json", '{"config": {}} {', "[1] ]"])
def test_a_broken_json_stream_is_a_parse_error(text: str) -> None:
    with pytest.raises(ev.ParseError, match=r"govulncheck\.json is not a JSON stream"):
        ev.json_stream(text, "govulncheck.json")


def test_a_json_stream_reads_indented_and_single_line_objects_alike() -> None:
    text = (
        json.dumps(GO_CONFIG, indent=2) + "\n" + json.dumps({"progress": {}}) + json.dumps({"osv": {}}) + "\n"
    )
    assert ev.json_stream(text, "x") == [GO_CONFIG, {"progress": {}}, {"osv": {}}]
    assert ev.json_stream(" \n", "x") == []


# --- the committed baseline ----------------------------------------------------------------------------


def test_committed_baseline_is_well_formed_and_waits_only_on_a_persons_review() -> None:
    """Everything the code instance can write is valid. Only a person sets "reviewed" and "review_by"."""
    path = REPO / "scan" / "baseline" / "timelike-agent.json"
    b = ev.parse_baseline(path.read_text(), PATH)
    assert b.image == "timelike-agent"
    assert {key for _, key in b.problems} <= {"reviewed", "review_by"}
    assert all(not ev._placeholder(e.reason) for e in b.entries if e.severity == "critical")
