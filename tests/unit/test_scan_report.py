"""The supply-chain gate's report path (collect, report, dists, main) over synthetic scan/out dirs.

Host-runnable, no Docker: each test writes what scan/scan.sh's steps would have left in scan/out
(steps.tsv plus each scanner's JSON) and checks the verdict evaluate.py reaches from it. Whether the
real scanners write these shapes is the Docker lane's to show (T036).
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
import re
import subprocess
import sys
import sysconfig
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[2]
TODAY = dt.date(2026, 9, 28)
IMAGE = "timelike-agent:local"
IMAGE_ID = "sha256:" + "ab" * 32
DIGEST = "sha256:" + "a9" * 32
LABEL = "scan/baseline/timelike-agent.json"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("scan_evaluate_report", REPO / "scan" / "evaluate.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ev = _load()


def high(vid: str, fixed: bool, name: str = "openssl") -> dict[str, Any]:
    fix = {"state": "fixed", "versions": ["3.5.1"]} if fixed else {"state": "not-fixed", "versions": []}
    return {
        "vulnerability": {"id": vid, "severity": "High", "fix": fix},
        "artifact": {"id": f"art-{name}", "name": name, "version": "3.5.0"},
    }


def baseline_file(tmp_path: Path, reviewed: str = "2026-09-20", review_by: str = "2026-12-01") -> Path:
    """A reviewed baseline accepting CVE-2026-0300 in openssl."""
    doc = {
        "image": "timelike-agent",
        "base_digest": DIGEST,
        "reviewed": reviewed,
        "review_by": review_by,
        "origins": {"base layer": "not reachable"},
        "findings": [
            {"id": "CVE-2026-0300", "package": "openssl", "severity": "high", "origin": "base layer"}
        ],
    }
    path = tmp_path / "timelike-agent.json"
    path.write_text(json.dumps(doc))
    return path


NO_AGENT_PY = (
    f"no agent interpreter in image: {IMAGE} has no /opt/agent/python/bin/python3, "
    "so pip-audit had nothing to audit"
)


def scan_out(
    tmp_path: Path,
    *,
    steps: dict[str, tuple[str, str]] | None = None,
    sbom: Any = None,
    grype: Any = None,
    pip_audit: Any = None,
    pip_audit_agent: Any = None,
    gitleaks: Any = None,
    govulncheck: str | None = None,
) -> Path:
    """A scan/out directory as a clean run leaves it; keyword arguments override one piece."""
    out = tmp_path / "out"
    out.mkdir()
    rows = {
        "sbom": ("ran", "syft"),
        "grype": ("ran", "grype"),
        "pip-audit": ("ran", "1 distributions in /site"),
        "pip-audit-agent": ("none", NO_AGENT_PY),
        "release-check": ("none", "no bundled-class entries in timelike-agent.json"),
        "govulncheck": ("none", "not a Go image: govulncheck runs over Adele's source only"),
        "gitleaks": ("ran", "gitleaks"),
    }
    rows.update(steps or {})
    (out / "steps.tsv").write_text("".join(f"{n}\t{s}\t{d}\n" for n, (s, d) in rows.items()))
    files = {
        "sbom.syft.json": sbom
        if sbom is not None
        else {"source": {"metadata": {"imageID": IMAGE_ID}}, "artifacts": [{}, {}]},
        "grype.json": grype if grype is not None else {"matches": []},
        "pip-audit.json": pip_audit
        if pip_audit is not None
        else {"dependencies": [{"name": "pip", "version": "25.2", "vulns": []}]},
        "gitleaks.json": gitleaks if gitleaks is not None else [],
    }
    if pip_audit_agent is not None:
        files["pip-audit-agent.json"] = pip_audit_agent
    for name, content in files.items():
        (out / name).write_text(content if isinstance(content, str) else json.dumps(content))
    if govulncheck is not None:
        (out / "govulncheck.json").write_text(govulncheck)
    return out


def run_report(
    out: Path, capsys: pytest.CaptureFixture[str], baseline: Path | None = None
) -> tuple[int, list[str]]:
    path = baseline if baseline is not None else out.parent / "absent.json"
    code = ev.report(out, ev.Target(IMAGE, IMAGE_ID, DIGEST, path, LABEL), TODAY)
    return code, capsys.readouterr().out.splitlines()


def step(out: Path, name: str) -> dict[str, str]:
    steps = json.loads((out / "verdict.json").read_text())["steps"]
    found: dict[str, str] = next(s for s in steps if s["name"] == name)
    return found


def test_clean_run_passes_writes_verdict_json_and_leads_with_the_verdict(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = scan_out(tmp_path)
    code, lines = run_report(out, capsys)
    assert code == 0
    assert lines[0] == f"scan: {IMAGE} [supply-chain] — PASS"
    verdict = json.loads((out / "verdict.json").read_text())
    assert verdict["verdict"] == "PASS"
    assert verdict["blocking"] == []
    assert [s["status"] for s in verdict["steps"]] == ["PASS"] * 8
    assert step(out, "sbom")["detail"] == "2 packages catalogued from sha256:abababababab"
    assert step(out, "baseline")["detail"] == "none"
    assert lines[9] == f"baseline: {LABEL} — none, accepts nothing"
    assert verdict["baseline"]["summary"] == lines[9]
    assert verdict["rule"] == "reviewed baseline per image digest (discovery revision 5)"
    assert json.loads((out / "baseline.proposed.json").read_text())["findings"] == []


ESCALATION_KEYS = {"source", "identifier", "component", "severity", "message", "image", "date", "update"}


def blocking(out: Path) -> list[dict[str, str]]:
    found: list[dict[str, str]] = json.loads((out / "verdict.json").read_text())["blocking"]
    return found


def test_fixable_high_fails_and_names_the_upgrade(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = scan_out(tmp_path, grype={"matches": [high("CVE-2026-0200", fixed=True)]})
    code, lines = run_report(out, capsys)
    assert code == 1
    assert lines[0].endswith("— FAIL")
    assert "blocking:" in lines
    assert (
        "  grype  CVE-2026-0200  high  openssl 3.5.0 in timelike-agent:local — fix available in 3.5.1: "
        "upgrade openssl in timelike-agent:local → update: rebuild timelike-agent:local with openssl at "
        "3.5.1 or later"
    ) in lines
    (entry,) = blocking(out)
    assert set(entry) == ESCALATION_KEYS
    assert step(out, "grype")["status"] == "FAIL"
    assert step(out, "baseline")["status"] == "PASS"


def test_unfixable_high_not_baselined_fails_and_the_proposal_holds_its_entry(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = scan_out(tmp_path, grype={"matches": [high("CVE-2026-0300", fixed=False)]})
    code, lines = run_report(out, capsys)
    assert code == 1
    (entry,) = blocking(out)
    assert (entry["identifier"], entry["component"], entry["image"]) == (
        "CVE-2026-0300",
        "openssl 3.5.0",
        "timelike-agent:local",
    )
    assert entry["update"].startswith(f"{LABEL}: add CVE-2026-0300 in openssl")
    assert any(
        line.startswith("  grype  CVE-2026-0300") and "→ update: scan/baseline/" in line for line in lines
    )
    assert step(out, "grype")["status"] == "FAIL"
    assert step(out, "baseline")["status"] == "PASS"  # no baseline is no defect; grype has the finding
    proposal = json.loads((out / "baseline.proposed.json").read_text())
    assert proposal["findings"] == [
        {"id": "CVE-2026-0300", "package": "openssl", "severity": "high", "origin": "grype package"}
    ]


def test_baselined_unfixable_high_passes_and_is_listed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = scan_out(tmp_path, grype={"matches": [high("CVE-2026-0300", fixed=False)]})
    code, lines = run_report(out, capsys, baseline_file(tmp_path))
    assert code == 0
    assert "baselined:" in lines
    assert step(out, "grype")["detail"].endswith("; 1 baselined")
    assert step(out, "baseline")["detail"] == "1 entries"
    assert lines[9] == (
        f"baseline: {LABEL} — accepts 1 High; base digest {DIGEST[:19]}; "
        "reviewed 2026-09-20, review by 2026-12-01"
    )


@pytest.mark.parametrize(
    ("reviewed", "review_by", "said"),
    [
        ("2026-08-01", "2026-09-01", "overdue since 2026-09-01"),
        ("2026-09-20", "2026-12-20", "review date 2026-12-20 exceeds the 90-day cap"),
    ],
)
def test_overdue_or_capped_baseline_is_an_escalation_in_text_and_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], reviewed: str, review_by: str, said: str
) -> None:
    out = scan_out(tmp_path, grype={"matches": [high("CVE-2026-0300", fixed=False)]})
    code, lines = run_report(out, capsys, baseline_file(tmp_path, reviewed, review_by))
    assert code == 1
    assert step(out, "baseline") == {"name": "baseline", "status": "FAIL", "detail": "1 entries; 1 blocking"}
    (entry,) = blocking(out)
    assert set(entry) == ESCALATION_KEYS
    assert said in entry["message"] and "(1 findings it lists block until then)" in entry["message"]
    assert (entry["source"], entry["identifier"], entry["date"]) == ("baseline", LABEL, review_by)
    assert entry["update"].startswith(f'{LABEL}, field "review_by"; have a person re-review')
    (text,) = [line for line in lines if line.startswith(f"  baseline  {LABEL}")]
    assert text.endswith(f"→ update: {entry['update']}")
    assert lines[9] == f"baseline: {LABEL} — accepts nothing until re-reviewed (see blocking)"


def test_unreadable_baseline_fails(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bad = tmp_path / "timelike-agent.json"
    bad.write_text("{not json")
    out = scan_out(tmp_path)
    code, _ = run_report(out, capsys, bad)
    assert code == 1
    assert step(out, "baseline")["status"] == "FAIL"
    assert "is not JSON" in step(out, "baseline")["detail"]
    (entry,) = blocking(out)
    assert entry["component"] == "the whole file"


def test_no_proposal_when_grype_did_not_run(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = scan_out(tmp_path, steps={"grype": ("error", "not run: no SBOM (step 1 failed)")})
    run_report(out, capsys)
    assert not (out / "baseline.proposed.json").exists()


def test_origins_reach_the_proposal_through_the_sbom(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sbom = {
        "source": {"metadata": {"imageID": IMAGE_ID, "layers": [{"digest": "L0"}]}},
        "artifacts": [
            {"id": "art-openssl", "name": "openssl", "type": "deb", "locations": [{"layerID": "L0"}]}
        ],
    }
    out = scan_out(tmp_path, sbom=sbom, grype={"matches": [high("CVE-2026-0300", fixed=False)]})
    run_report(out, capsys)
    proposal = json.loads((out / "baseline.proposed.json").read_text())
    assert proposal["findings"][0]["origin"] == "base layer"
    assert proposal["origins"] == {"base layer": "<why the findings from this origin are tolerated>"}


def test_a_step_recorded_as_error_fails(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = scan_out(tmp_path, steps={"grype": ("error", "grype failed (exit 1): no db")})
    code, lines = run_report(out, capsys)
    assert code == 1
    assert lines[0].endswith("— FAIL")
    assert step(out, "grype") == {"name": "grype", "status": "FAIL", "detail": "grype failed (exit 1): no db"}


def test_a_step_missing_from_steps_tsv_fails(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = scan_out(tmp_path)
    (out / "steps.tsv").write_text("sbom\tran\tsyft\n")
    code, _ = run_report(out, capsys)
    assert code == 1
    assert step(out, "gitleaks")["detail"] == "the step recorded no result"


def test_sbom_of_another_image_fails(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = scan_out(tmp_path, sbom={"source": {"metadata": {"imageID": "sha256:ffff"}}, "artifacts": []})
    code, _ = run_report(out, capsys)
    assert code == 1
    assert "SBOM describes image sha256:ffff" in step(out, "sbom")["detail"]


@pytest.mark.parametrize(
    ("override", "name", "expected"),
    [
        ({"grype": "{not json"}, "grype", "grype.json unreadable"),
        ({"grype": {"matches": "nope"}}, "grype", "grype JSON has no matches list"),
        ({"pip_audit": {"deps": []}}, "pip-audit", "pip-audit JSON has no dependencies list"),
        ({"gitleaks": {"not": "a list"}}, "gitleaks", "gitleaks report is not a JSON list"),
        ({"sbom": {"artifacts": []}}, "sbom", "malformed result: KeyError"),
        ({"sbom": {"source": None}}, "sbom", "malformed result: TypeError"),
    ],
)
def test_malformed_json_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], override: dict[str, Any], name: str, expected: str
) -> None:
    out = scan_out(tmp_path, **override)
    code, _ = run_report(out, capsys)
    assert code == 1
    assert step(out, name)["status"] == "FAIL"
    assert expected in step(out, name)["detail"]


def test_pip_audit_none_passes_and_says_so(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = scan_out(
        tmp_path, steps={"pip-audit": ("none", "no third-party packages — pip-audit had nothing to audit")}
    )
    (out / "pip-audit.json").unlink()  # a `none` step writes no report, and none is read
    code, _ = run_report(out, capsys)
    assert code == 0
    assert step(out, "pip-audit") == {
        "name": "pip-audit",
        "status": "PASS",
        "detail": "no third-party packages — pip-audit had nothing to audit",
    }


def test_pip_audit_skip_and_gitleaks_finding_reach_the_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = scan_out(
        tmp_path,
        pip_audit={"dependencies": [{"name": "agentio", "version": "0", "skip_reason": "not on PyPI"}]},
        gitleaks=[{"RuleID": "generic-api-key", "File": "a.env", "StartLine": 1, "Commit": "c0ffee"}],
    )
    code, lines = run_report(out, capsys)
    assert code == 1
    assert "note: pip-audit skipped agentio 0: not on PyPI" in lines
    assert step(out, "gitleaks")["detail"] == "1 findings across git history; 1 blocking"


def test_pip_audit_agent_finding_blocks_on_its_own_line_and_timelike_s_pip_audit_still_passes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    vuln = {"id": "PYSEC-2026-1", "fix_versions": ["26.3"], "aliases": ["CVE-2026-0001"]}
    out = scan_out(
        tmp_path,
        steps={"pip-audit-agent": ("ran", "2 distributions in /agent-site (agent interpreter)")},
        pip_audit_agent={
            "dependencies": [
                {"name": "pip", "version": "26.2.1", "vulns": [vuln]},
                {"name": "local", "version": "0", "skip_reason": "not on PyPI"},
            ]
        },
    )
    code, lines = run_report(out, capsys)
    assert code == 1
    assert step(out, "pip-audit")["status"] == "PASS"
    assert step(out, "pip-audit-agent") == {
        "name": "pip-audit-agent",
        "status": "FAIL",
        "detail": "2 distributions in /agent-site (agent interpreter); 1 matches; 1 blocking",
    }
    (blocking,) = json.loads((out / "verdict.json").read_text())["blocking"]
    assert (blocking["source"], blocking["identifier"], blocking["component"]) == (
        "pip-audit-agent",
        "PYSEC-2026-1",
        "pip 26.2.1",
    )
    assert "note: pip-audit-agent skipped local 0: not on PyPI" in lines


def test_pip_audit_agent_missing_from_steps_tsv_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = scan_out(tmp_path)
    rows = [r for r in (out / "steps.tsv").read_text().splitlines() if not r.startswith("pip-audit-agent\t")]
    (out / "steps.tsv").write_text("\n".join(rows) + "\n")  # as a scan.sh without the step would leave it
    code, _ = run_report(out, capsys)
    assert code == 1
    assert step(out, "pip-audit-agent") == {
        "name": "pip-audit-agent",
        "status": "FAIL",
        "detail": "the step recorded no result",
    }


def _fake_site(root: Path, names: list[str]) -> Path:
    site = root / "site-packages"
    site.mkdir()
    for name in names:
        info = site / f"{name}-1.0.dist-info"
        info.mkdir()
        (info / "METADATA").write_text(f"Metadata-Version: 2.1\nName: {name}\nVersion: 1.0\n")
    return site


@pytest.mark.parametrize("names", [[], ["pip", "zeta"]])
def test_dists_counts_what_the_interpreter_sees(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, names: list[str]
) -> None:
    site = _fake_site(tmp_path, names)
    # The fake site first, then the stdlib only: reading METADATA imports email (and, from Python 3.14,
    # quopri lazily), so the stdlib must stay importable, while the interpreter's own site-packages
    # must not, or its distributions would be counted too.
    stdlib = sysconfig.get_path("stdlib")
    keep = [p for p in sys.path if p.startswith(stdlib) and "site-packages" not in p]
    monkeypatch.setattr(sys, "path", [str(site), *keep])
    monkeypatch.setattr(ev.sysconfig, "get_path", lambda _name: str(site))
    record, pins = tmp_path / "dists.json", tmp_path / "requirements.txt"
    assert ev.main(["dists", "--out", str(record), "--requirements", str(pins)]) == 0
    assert capsys.readouterr().out == f"{len(names)} {site}\n"
    assert json.loads(record.read_text()) == [{"name": n, "version": "1.0"} for n in sorted(names)]
    # The pins pip-audit-agent audits with -r --no-deps --disable-pip: exact versions, one per line.
    assert pins.read_text() == "".join(f"{n}==1.0\n" for n in sorted(names))


def test_main_report_runs_end_to_end(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = scan_out(tmp_path)
    argv = ["report", "--out", str(out), "--baseline", str(tmp_path / "timelike-agent.json")]
    argv += ["--base-digest", DIGEST, "--image", IMAGE, "--image-id", IMAGE_ID, "--today", "2026-09-28"]
    assert ev.main(argv) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == f"scan: {IMAGE} [supply-chain] — PASS"
    assert lines[9] == f"baseline: {LABEL} — none, accepts nothing"
    assert json.loads((out / "verdict.json").read_text())["today"] == "2026-09-28"


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["bogus"],
        ["dists"],
        ["report", "--out", "x"],
        [
            "report",
            "--out",
            "x",
            "--baseline",
            "b",
            "--base-digest",
            "sha256:short",
            "--image",
            "i",
            "--image-id",
            "d",
        ],
        [
            "report",
            "--out",
            "x",
            "--baseline",
            "b.json",
            "--base-digest",
            "sha256:" + "0" * 64,
            "--image",
            "i",
            "--image-id",
            "d",
            "--today",
            "28/09",
        ],
    ],
)
def test_main_rejects_bad_arguments_with_exit_2(argv: list[str], capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        ev.main(argv)
    assert exc.value.code == 2
    assert "usage:" in capsys.readouterr().err


def test_main_turns_a_crash_into_exit_2_with_no_verdict_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """scan.sh reads 0 as PASS and 1 as FAIL; any other code means no verdict was reached."""
    argv = ["report", "--out", str(tmp_path / "absent"), "--baseline", str(tmp_path / "b.json")]
    assert ev.main([*argv, "--base-digest", DIGEST, "--image", IMAGE, "--image-id", IMAGE_ID]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "error: evaluate.py report failed" in captured.err


# --- Adele (feature 004, research R5): govulncheck, the per-image base digest, no interpreter -------

ADELE = "timelike-adele:local"
ADELE_LABEL = "scan/baseline/timelike-adele.json"
GO_DIGEST = "sha256:" + "3b" * 32


def gv_stream(*findings: dict[str, Any]) -> str:
    """govulncheck -format json as v1.8.0 writes it: indented objects, one after another."""
    messages: list[dict[str, Any]] = [
        {
            "config": {
                "protocol_version": "v1.0.0",
                "scanner_name": "govulncheck",
                "scanner_version": "v1.8.0",
            }
        },
        {"progress": {"message": "Checking the code against the vulnerabilities..."}},
        {"osv": {"id": "GO-2026-4001", "aliases": ["CVE-2026-4001"], "affected": []}},
        *({"finding": f} for f in findings),
    ]
    return "\n".join(json.dumps(m, indent=2) for m in messages) + "\n"


def reachable(fixed: str = "") -> dict[str, Any]:
    frame = {"module": "stdlib", "version": "v1.27.1", "package": "net/http", "function": "Serve"}
    caller = {"module": "timelike/adele", "package": "timelike/adele/cmd/adeled", "function": "main"}
    return {"osv": "GO-2026-4001", **({"fixed_version": fixed} if fixed else {}), "trace": [frame, caller]}


def adele_out(tmp_path: Path, stream: str) -> Path:
    no_python = "no interpreter in image: timelike-adele:local has no /opt/timelike/python/bin/python3"
    steps = {
        "pip-audit": ("none", no_python + ", so pip-audit had nothing to audit"),
        "govulncheck": ("ran", "govulncheck v1.8.0 over adele/ (golang:1.27.1-trixie)"),
    }
    out = scan_out(tmp_path, steps=steps, govulncheck=stream)
    (out / "pip-audit.json").unlink()  # a `none` step writes no report
    return out


def run_adele(
    out: Path, capsys: pytest.CaptureFixture[str], baseline: Path | None = None, digest: str = GO_DIGEST
) -> tuple[int, list[str]]:
    path = baseline if baseline is not None else out.parent / "absent.json"
    code = ev.report(out, ev.Target(ADELE, IMAGE_ID, digest, path, ADELE_LABEL), TODAY)
    return code, capsys.readouterr().out.splitlines()


def test_adele_with_a_clean_govulncheck_and_no_interpreter_passes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = adele_out(tmp_path, gv_stream())
    code, lines = run_adele(out, capsys)
    assert code == 0
    assert lines[0] == f"scan: {ADELE} [supply-chain] — PASS"
    assert step(out, "govulncheck") == {
        "name": "govulncheck",
        "status": "PASS",
        "detail": "govulncheck v1.8.0 over adele/ (golang:1.27.1-trixie); 0 vulnerabilities, 0 reachable",
    }
    assert step(out, "pip-audit")["status"] == "PASS"
    assert step(out, "pip-audit")["detail"].startswith("no interpreter in image: ")
    # every step name fits its column, the longest (pip-audit-agent) included
    assert "  govulncheck      PASS  govulncheck v1.8.0" in "\n".join(lines)
    assert f"  pip-audit-agent  PASS  {NO_AGENT_PY}" in "\n".join(lines)
    verdict = json.loads((out / "verdict.json").read_text())
    assert verdict["base_digest"] == GO_DIGEST
    assert lines[9] == f"baseline: {ADELE_LABEL} — none, accepts nothing"


def test_a_reachable_go_vulnerability_with_a_fix_blocks_and_names_go_image(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = adele_out(tmp_path, gv_stream(reachable(fixed="v1.27.2")))
    code, _ = run_adele(out, capsys)
    assert code == 1
    (entry,) = blocking(out)
    assert set(entry) == ESCALATION_KEYS
    assert (entry["source"], entry["identifier"], entry["component"], entry["severity"]) == (
        "govulncheck",
        "GO-2026-4001",
        "stdlib v1.27.1",
        "high",
    )
    assert entry["update"].startswith("pins.env: GO_IMAGE to a Go v1.27.2 or later image")
    assert step(out, "govulncheck")["status"] == "FAIL"
    assert step(out, "govulncheck")["detail"].endswith("; 1 vulnerabilities, 1 reachable; 1 blocking")


def test_a_reachable_go_vulnerability_without_a_fix_is_proposed_and_a_go_digest_baseline_accepts_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = adele_out(tmp_path, gv_stream(reachable()))
    code, _ = run_adele(out, capsys)
    assert code == 1
    proposal = json.loads((out / "baseline.proposed.json").read_text())
    assert proposal["base_digest"] == GO_DIGEST
    assert proposal["image"] == "timelike-adele"
    (item,) = proposal["findings"]
    assert (item["id"], item["package"], item["severity"]) == ("GO-2026-4001", "stdlib", "high")
    proposal |= {"reviewed": "2026-09-27", "review_by": "2026-12-01"}
    proposal["origins"] = {o: "not reachable from a request Adele accepts" for o in proposal["origins"]}
    reviewed = tmp_path / "timelike-adele.json"
    reviewed.write_text(json.dumps(proposal))
    assert run_adele(out, capsys, reviewed)[0] == 0
    # The same reviewed baseline under the Debian digest is for another base: it accepts nothing.
    code, lines = run_adele(out, capsys, reviewed, digest=DIGEST)
    assert code == 1
    assert lines[9] == f"baseline: {ADELE_LABEL} — accepts nothing until re-reviewed (see blocking)"


@pytest.mark.parametrize(
    ("stream", "expected"),
    [
        ("{not json", "govulncheck.json is not a JSON stream"),
        ("", "no govulncheck config message"),
        (json.dumps({"progress": {"message": "x"}}), "no govulncheck config message"),
        (gv_stream({"osv": "GO-2026-4001", "trace": []}), "govulncheck finding without an osv id or a trace"),
        (gv_stream() + "[1, 2]\n", "a message that is not an object"),
    ],
)
def test_a_malformed_govulncheck_stream_fails_its_step_and_is_no_crash(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], stream: str, expected: str
) -> None:
    out = adele_out(tmp_path, stream)
    code, lines = run_adele(out, capsys)
    assert code == 1
    assert lines[0].endswith("— FAIL")
    assert step(out, "govulncheck")["status"] == "FAIL"
    assert expected in step(out, "govulncheck")["detail"]


def test_a_govulncheck_step_that_ran_but_left_no_file_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = adele_out(tmp_path, gv_stream())
    (out / "govulncheck.json").unlink()
    assert run_adele(out, capsys)[0] == 1
    assert "govulncheck.json unreadable" in step(out, "govulncheck")["detail"]


def test_govulncheck_none_on_a_non_go_image_passes_and_a_missing_record_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = scan_out(tmp_path)
    assert run_report(out, capsys)[0] == 0
    assert step(out, "govulncheck") == {
        "name": "govulncheck",
        "status": "PASS",
        "detail": "not a Go image: govulncheck runs over Adele's source only",
    }
    rows = [r for r in (out / "steps.tsv").read_text().splitlines() if not r.startswith("govulncheck\t")]
    (out / "steps.tsv").write_text("\n".join(rows) + "\n")  # as a scan.sh without the step would leave it
    assert run_report(out, capsys)[0] == 1
    assert step(out, "govulncheck") == {
        "name": "govulncheck",
        "status": "FAIL",
        "detail": "the step recorded no result",
    }


# --- scan/scan.sh itself, over a stand-in docker (no daemon: this shows its wiring, not Docker's) ----

FAKE_DOCKER = r'''#!{python}
"""A stand-in `docker` for scan.sh. NOT an emulator: it answers the calls scan.sh makes and logs them."""
import json, os, re, subprocess, sys
from pathlib import Path

state = Path(os.environ["FAKE_STATE"])
AGENT_PY = "/opt/agent/python/bin/python3"
pins = dict(re.findall(r"^([A-Z_]+)=(.*)$", Path(os.environ["FAKE_PINS"]).read_text(), re.M))
images = json.loads(os.environ["FAKE_IMAGES"])
argv = sys.argv[1:]
if argv[:2] == ["image", "inspect"]:
    name = argv[-1]
    if name not in images:
        sys.exit("Error: No such image: " + name)
    print(images[name]["id"] if "--format" in argv else "[{}]")
    sys.exit(0)
if argv[0] == "save":
    Path(argv[2]).write_text("tar")
    (state / "saved").write_text(images[argv[3]]["id"])
    sys.exit(0)
assert argv[0] == "run", argv
opts = {"-e": [], "-v": []}
i, entry = 1, ""
while argv[i].startswith("-"):
    if argv[i] in ("--rm", "-i"):
        i += 1
        continue
    key, value = argv[i], argv[i + 1]
    opts.setdefault(key, []).append(value)
    i += 2
image, args = argv[i], argv[i + 1:]
mounts = {}
for v in opts["-v"]:
    host, ctr = v.split(":")[:2]
    mounts[ctr] = host
with (state / "runs.jsonl").open("a") as fh:
    fh.write(json.dumps({"image": image, "opts": opts, "args": args}) + "\n")


def host(arg):
    for ctr in sorted(mounts, key=len, reverse=True):
        if arg == ctr or arg.startswith(ctr + "/"):
            return mounts[ctr] + arg[len(ctr):]
    return arg


if image == pins["SYFT_IMAGE"]:
    print(json.dumps({"source": {"metadata": {"imageID": (state / "saved").read_text()}}, "artifacts": []}))
elif image == pins["GRYPE_IMAGE"]:
    print(json.dumps({"matches": []}))
elif image == pins["GITLEAKS_IMAGE"]:
    Path(host("/out/gitleaks.json")).write_text("[]")
elif image == pins["GO_IMAGE"]:
    sys.stdout.write((state / "govulncheck.json").read_text())
elif opts.get("--entrypoint") == ["/bin/uv"]:
    Path(host(args[args.index("--output") + 1])).write_text(json.dumps({"dependencies": []}))
elif not images[image]["agent_python" if opts.get("--entrypoint") == [AGENT_PY] else "python"]:
    sys.exit(127)  # docker run: the entrypoint cannot be found in the image
elif args[:2] == ["-I", "-c"]:
    sys.exit(0)
elif "dists" in args:
    if "--requirements" in args:
        Path(host(args[args.index("--requirements") + 1])).write_text("pip==26.2.1\n")
    print("1 /site")
else:
    sys.exit(subprocess.run([sys.executable, *map(host, args[1:])]).returncode)
'''


def scan_tree(tmp_path: Path, images: list[str], stream: str) -> tuple[Path, dict[str, str]]:
    """A copy of the parts of the checkout scan.sh reads, so the real scan/out is never touched."""
    root = tmp_path / "repo"
    (root / "scan" / "baseline").mkdir(parents=True)
    (root / "adele").mkdir()
    for rel in ("scan/scan.sh", "scan/evaluate.py", "scan/denylist.py", "pins.env"):
        (root / rel).write_bytes((REPO / rel).read_bytes())
    (root / "scan" / "scan.sh").chmod(0o755)
    # A real repository: the publish deny-list step reads `git archive HEAD` (maintenance send).
    git = ["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@example.invalid"]
    subprocess.run([*git, "init", "-q"], check=True)
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run([*git, "commit", "-q", "-m", "fixture"], check=True)
    bin_dir, state = tmp_path / "bin", tmp_path / "state"
    bin_dir.mkdir()
    state.mkdir()
    (bin_dir / "docker").write_text(FAKE_DOCKER.replace("{python}", sys.executable))
    (bin_dir / "docker").chmod(0o755)
    (state / "govulncheck.json").write_text(stream)
    known = {
        "timelike-agent:local": {"id": "sha256:" + "a1" * 32, "python": True, "agent_python": True},
        ADELE: {"id": "sha256:" + "ad" * 32, "python": False, "agent_python": False},
        "timelike-vanilla:local": {"id": "sha256:" + "0a" * 32, "python": False, "agent_python": True},
        "timelike-bench-driver:local": {"id": "sha256:" + "bd" * 32, "python": True, "agent_python": False},
    }
    env = {
        "PATH": f"{bin_dir}:/usr/bin:/bin",
        "FAKE_STATE": str(state),
        "FAKE_PINS": str(root / "pins.env"),
        "FAKE_IMAGES": json.dumps({k: v for k, v in known.items() if k in images}),
    }
    return root, env


def run_scan(root: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(root / "scan" / "scan.sh")],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        stdin=subprocess.DEVNULL,
        check=False,
    )


def pins() -> dict[str, str]:
    return dict(re.findall(r"^([A-Z_]+)=(.*)$", (REPO / "pins.env").read_text(), re.M))


ALL_IMAGES = [IMAGE, ADELE, "timelike-vanilla:local", "timelike-bench-driver:local"]


def test_scan_sh_scans_four_images_with_their_own_base_digest_and_govulncheck_for_adele_only(
    tmp_path: Path,
) -> None:
    root, env = scan_tree(tmp_path, ALL_IMAGES, gv_stream())
    done = run_scan(root, env)
    assert done.returncode == 0, done.stderr
    assert [line for line in done.stdout.splitlines() if "[supply-chain]" in line] == [
        f"scan: {img} [supply-chain] — PASS" for img in ALL_IMAGES
    ]
    p, top = pins(), root / "scan" / "out"
    dirs = {IMAGE: top, **{img: top / img.split(":")[0] for img in ALL_IMAGES[1:]}}
    for img, d in dirs.items():
        verdict = json.loads((d / "verdict.json").read_text())
        expected = p["GO_IMAGE"] if img == ADELE else p["DEBIAN_IMAGE"]
        assert verdict["base_digest"] == expected.split("@")[1], img
        steps = {r.split("\t")[0]: r.split("\t")[1:] for r in (d / "steps.tsv").read_text().splitlines()}
        assert list(steps) == [
            "sbom",
            "grype",
            "pip-audit",
            "pip-audit-agent",
            "release-check",
            "govulncheck",
            "gitleaks",
        ], img
        if img == ADELE:
            assert steps["govulncheck"] == [
                "ran",
                f"govulncheck v1.8.0 over adele/ ({p['GO_IMAGE'].split('@')[0]})",
            ]
        else:
            assert steps["govulncheck"] == [
                "none",
                "not a Go image: govulncheck runs over Adele's source only",
            ]
    py = "/opt/timelike/python/bin/python3"
    for img in (ADELE, "timelike-vanilla:local"):
        pip = (dirs[img] / "steps.tsv").read_text().splitlines()[2]
        said = f"no interpreter in image: {img} has no {py}, so pip-audit had nothing to audit"
        assert pip == f"pip-audit\tnone\t{said}"
    # pip-audit-agent: each image carrying /opt/agent/python (agent, vanilla) audits it; the rest say none.
    agent_py = "/opt/agent/python/bin/python3"
    for img, d in dirs.items():
        row = (d / "steps.tsv").read_text().splitlines()[3]
        if img in (IMAGE, "timelike-vanilla:local"):
            assert row == "pip-audit-agent\tran\t1 distributions in /site (agent interpreter)", img
            assert (d / "agent-requirements.txt").read_text() == "pip==26.2.1\n", img
        else:
            said = f"no agent interpreter in image: {img} has no {agent_py}"
            assert row == f"pip-audit-agent\tnone\t{said}, so pip-audit had nothing to audit", img
    runs = [json.loads(r) for r in (tmp_path / "state" / "runs.jsonl").read_text().splitlines()]
    audits = [r for r in runs if r["opts"].get("--entrypoint") == ["/bin/uv"] and "-r" in r["args"]]
    # Two agent-interpreter audits (agent, vanilla), both run from the agent image, which holds uv:
    # over the scanned image's own list, resolving and installing nothing.
    assert [r["image"] for r in audits] == [IMAGE, IMAGE]
    for r in audits:
        assert {"-r", "/out/agent-requirements.txt", "--no-deps", "--disable-pip"} <= set(r["args"])
        assert r["args"][r["args"].index("--output") + 1] == "/out/pip-audit-agent.json"
    listings = [r for r in runs if r["opts"].get("--entrypoint") == [agent_py] and "dists" in r["args"]]
    assert [r["image"] for r in listings] == [IMAGE, "timelike-vanilla:local"]
    assert all(r["opts"]["--network"] == ["none"] for r in listings)
    # release-check: no image here has a baseline, so none has bundled-class entries to check.
    for img, d in dirs.items():
        row = (d / "steps.tsv").read_text().splitlines()[4]
        said = f"no baseline (scan/baseline/{img.split(':')[0]}.json), so no bundled-class entries to check"
        assert row == f"release-check\tnone\t{said}", img
    (go,) = [r for r in runs if r["image"] == p["GO_IMAGE"]]
    assert go["opts"]["--entrypoint"] == ["go"]
    assert go["args"] == [
        "run",
        f"golang.org/x/vuln/cmd/govulncheck@{p['GOVULNCHECK_VERSION']}",
        "-format",
        "json",
        "./...",
    ]
    assert {
        "GOTOOLCHAIN=local",
        "GOFLAGS=-mod=readonly",
        "GOCACHE=/tmp/go-cache",
        "GOMODCACHE=/tmp/go-mod",
    } <= set(go["opts"]["-e"])
    assert go["opts"]["-v"] == [f"{root}/adele:/src:ro"]
    assert (dirs[ADELE] / "govulncheck.json").read_text() == gv_stream()  # stdout, as written


def test_scan_sh_runs_the_release_check_from_the_agent_image_with_network_and_records_what_it_checked(
    tmp_path: Path,
) -> None:
    root, env = scan_tree(tmp_path, ALL_IMAGES[:2], gv_stream())
    # A pip-component bundled entry: the check answers `unknown` without reaching any registry, which is
    # what lets this run offline; npm's path is covered against a file-served registry in
    # test_scan_release_check.py.
    entry = {
        "id": "PYSEC-2026-9",
        "package": "urllib3",
        "severity": "high",
        "origin": "files under /opt/agent",
        "reason": "vendored in pip",
        "bundled": {
            "component": "pip",
            "component_version": "26.2.1",
            "library_version": "2.5.0",
            "fixed_version": "2.6.0",
            "fixed_date": "2026-09-01",
        },
        "reviewed": "2026-10-08",
        "review_by": "2026-11-07",
    }
    doc = {
        "image": "timelike-agent",
        "base_digest": pins()["DEBIAN_IMAGE"].split("@")[1],
        "reviewed": "2026-10-01",
        "review_by": "2026-12-27",
        "origins": {"files under /opt/agent": "the agent runtimes"},
        "findings": [entry],
    }
    (root / "scan" / "baseline" / "timelike-agent.json").write_text(json.dumps(doc))
    done = run_scan(root, env)
    out = root / "scan" / "out"
    row = (out / "steps.tsv").read_text().splitlines()[4]
    assert row.startswith("release-check\tran\t1 bundled-class entries checked"), done.stdout + done.stderr
    assert row.endswith(": 1 unknown")
    result = json.loads((out / "release-check.json").read_text())["results"][0]
    assert (result["state"], result["component"]) == ("unknown", "pip")
    runs = [json.loads(r) for r in (tmp_path / "state" / "runs.jsonl").read_text().splitlines()]
    (check,) = [r for r in runs if "releases" in r["args"]]
    assert check["image"] == IMAGE
    assert "--network" not in check["opts"]  # the registry is the point
    assert check["args"][check["args"].index("--node-version") + 1] == pins()["NODE_VERSION"]


def test_scan_sh_publish_denylist_is_unknown_without_a_list_and_does_not_fail(tmp_path: Path) -> None:
    root, env = scan_tree(tmp_path, ALL_IMAGES[:2], gv_stream())
    env["TIMELIKE_PUBLISH_DENYLIST"] = str(tmp_path / "no-such-list.txt")
    done = run_scan(root, env)
    assert done.returncode == 0, done.stdout + done.stderr
    (line,) = [x for x in done.stdout.splitlines() if x.startswith("publish deny-list")]
    assert line.startswith("publish deny-list [tracked tree]: unknown — no deny-list available")
    assert json.loads((root / "scan" / "out" / "denylist.json").read_text())["state"] == "unknown"


def test_scan_sh_publish_denylist_fails_the_scan_on_a_tracked_match_by_id_only(tmp_path: Path) -> None:
    root, env = scan_tree(tmp_path, ALL_IMAGES[:2], gv_stream())
    lst = tmp_path / "list.txt"
    lst.write_text("T1\tkestrel-?box\n", encoding="utf-8")  # synthetic; never a real entry
    (root / "notes.md").write_text("one\nKestrelbox two\n", encoding="utf-8")
    git = ["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@example.invalid"]
    subprocess.run([*git, "add", "notes.md"], check=True)
    subprocess.run([*git, "commit", "-q", "-m", "plant"], check=True)
    env["TIMELIKE_PUBLISH_DENYLIST"] = str(lst)
    done = run_scan(root, env)
    assert done.returncode == 1
    assert "FAIL T1 notes.md:2" in done.stdout.splitlines()
    assert "kestrelbox" not in done.stdout.lower()
    # the per-image verdicts are unaffected: only the deny-list step failed
    assert f"scan: {IMAGE} [supply-chain] — PASS" in done.stdout.splitlines()


def test_scan_sh_fails_on_a_reachable_fixable_go_vulnerability_in_adele_alone(tmp_path: Path) -> None:
    root, env = scan_tree(tmp_path, ALL_IMAGES[:2], gv_stream(reachable(fixed="v1.27.2")))
    done = run_scan(root, env)
    assert done.returncode == 1
    lines = done.stdout.splitlines()
    assert f"scan: {IMAGE} [supply-chain] — PASS" in lines
    assert f"scan: {ADELE} [supply-chain] — FAIL" in lines
    assert any(
        line.startswith("  govulncheck  GO-2026-4001  high  stdlib v1.27.1 in timelike-adele:local")
        for line in lines
    )
    for absent in ALL_IMAGES[2:]:
        assert (
            f"scan: {absent} [supply-chain] — not present (build it with make bench-images); not scanned"
            in lines
        )


def test_scan_sh_fails_before_scanning_when_adele_is_missing(tmp_path: Path) -> None:
    root, env = scan_tree(tmp_path, [IMAGE], gv_stream())
    done = run_scan(root, env)
    assert done.returncode == 1
    assert done.stdout == f"scan: {ADELE} [supply-chain] — FAIL\n"
    assert f"image {ADELE} not found (code 1) — build it with make build first" in done.stderr
    assert not (tmp_path / "state" / "runs.jsonl").exists()


def test_scan_sh_maps_each_image_to_its_base_digest_in_one_place() -> None:
    """research R5: Adele's final stage is FROM scratch, so its base digest is the Go builder's."""
    text = (REPO / "scan" / "scan.sh").read_text()
    (fn,) = re.findall(r"^base_digest_of\(\) \{\n.*?^\}\n", text, re.M | re.S)
    script = f'. "{REPO}/pins.env"\nadele={ADELE}\n{fn}'
    script += "for i in timelike-agent:local timelike-adele:local timelike-vanilla:local; do\n"
    script += "  base_digest_of $i\ndone\n"
    done = subprocess.run(["bash", "-c", script], capture_output=True, text=True, check=True, timeout=10)
    p = pins()
    go, debian = p["GO_IMAGE"].split("@")[1], p["DEBIAN_IMAGE"].split("@")[1]
    assert done.stdout.split() == [debian, go, debian]
    assert text.count("${GO_IMAGE##*@}") == 1 and text.count("${DEBIAN_IMAGE##*@}") == 1
