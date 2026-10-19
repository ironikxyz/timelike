"""adele env, slice 2 (014 contracts/adele-env.md § Slice 2; plan R27, R31, R32), against a fake Adele.

The harness is test_adele_env_cli's and test_adele_env_slice1_cli's: the client runs as a real subprocess
against the in-process fake of Adele's request interface, which records what it was SENT and answers one
body per (method, path). Each case below needs one POST answer, so the fake's routing is enough: a restore
or a snapshot-rm without --yes asks only for the plan, and with --yes only for the act. What Adele does with
the daemon (pause, copy, digest, stop, start) is the e2e lane's.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import pytest
from conftest import TOOLS_DIR, base_env, run
from test_adele_cli import FakeAdele, Proc, adele, doc_of, load_conform, no_traceback, one_error_line
from test_adele_env_cli import NAME, go, listener, svc, up_body, ws
from test_adele_env_slice1_cli import later, load_adele, sent_post

__all__ = ["adele", "listener", "ws"]  # the fixtures, imported for their names

SNAP = "s-3f2a91c0"
DIGEST = "sha256:" + "ab" * 32
# 014 plan R32 A: a realistic name, `tl-` and a project name of 20 and its hash (30 characters).
LONG_NAME = "tl-timelike-agent-shell-0a1b2c"
CUT = re.compile(r"…\[cut \d+ bytes\]")

SNAPSHOT = {
    "id": SNAP,
    "volume": "db-data",
    "volume_name": f"{NAME}_db-data",
    "bytes": 49152,
    "files": 12,
    "sockets": 0,
    "digest": DIGEST,
    "taken_at": "2026-10-19T08:00:00Z",
    "note": "before the migration",
}
CAP = {"bytes": 1 << 30, "used": 102400, "left": (1 << 30) - 102400, "store": "volume"}


def snapshot_body(**over: Any) -> dict[str, Any]:
    return {
        "outcome": "performed",
        "grant": "nested",
        "resource": NAME,
        "snapshot": dict(SNAPSHOT),
        "paused": [{"service": "db", "container": "4f1e2d3c4b5a"}],
        "paused_ms": 400,
        "took_ms": 900,
        "cap": dict(CAP),
        "ledger_id": 150,
        "undo": '{"capability":"docker.compose","action":"snapshot-rm"}',
        "revision": "4d6e1f0c9b2a",
        **over,
    }


def plan_body(stop: list[str] | None = None) -> dict[str, Any]:
    return {
        "outcome": "plan",
        "snapshot": dict(SNAPSHOT),
        "volume": "db-data",
        "stop": ["db"] if stop is None else stop,
        "replace": "volume db-data",
    }


def restore_body(services: list[dict[str, Any]], **over: Any) -> dict[str, Any]:
    return {
        "outcome": "performed",
        "snapshot": dict(SNAPSHOT),
        "volume": "db-data",
        "stopped": ["db"],
        "stopped_ms": 3100,
        "digest": DIGEST,
        "services": services,
        "adele_readiness": {"db": "healthy"},
        "ledger_id": 151,
        "took_ms": 5000,
        **over,
    }


def listed_body() -> dict[str, Any]:
    second = {
        **SNAPSHOT,
        "id": "s-0b1c2d3e",
        "note": "",
        "taken_at": "2026-10-19T07:00:00Z",
        "ledger_id": 149,
    }
    return {
        "resource": NAME,
        "snapshots": [{**SNAPSHOT, "ledger_id": 150}, second],
        "cap": {**CAP, "used": 98304, "left": (1 << 30) - 98304},
        "volumes": ["db-data", "cache"],
    }


def env(py: str, scratch: Path, fake: FakeAdele, ws: Path | None, *args: str, timeout: float = 30) -> Proc:
    return go(py, scratch, fake, ws, "env", *args, timeout=timeout)


def head(r: Proc) -> str:
    return r.stdout.splitlines()[1]


# ── snapshot (FR-31, FR-35, R26) ───────────────────────────────────────────────────────────────


def test_snapshot_sends_the_volume_and_note_and_says_what_was_taken(
    py: str, scratch: Path, adele: FakeAdele
) -> None:
    adele.answer("POST", "/v1/requests", 200, snapshot_body())
    r = env(py, scratch, adele, None, "snapshot", NAME, "db-data", "--note", "before the migration")
    no_traceback(r)
    assert r.returncode == 0, r.stderr
    assert head(r) == (
        f"verdict: snapshot {NAME} db-data: {SNAP}, 48.0 KiB, 12 files · paused db for 0.4 s"
        " · cap 1 GiB, 1023.9 MiB left"
    )
    assert f"restore it: adele env restore {NAME} {SNAP} --yes" in r.stdout
    sent = sent_post(adele)
    assert sent["capability"] == "docker.compose" and sent["action"] == "snapshot"
    assert sent["params"] == {"name": NAME, "volume": "db-data", "note": "before the migration"}
    assert sent["grant"] == ""  # the environment's own grant (contract § Slice 2)


def test_snapshot_data_keeps_its_keys(py: str, scratch: Path, adele: FakeAdele) -> None:
    adele.answer("POST", "/v1/requests", 200, snapshot_body())
    doc = doc_of(env(py, scratch, adele, None, "--json", "snapshot", NAME, "db-data"))
    assert {"name", "snapshot", "paused", "paused_s", "cap", "ledger_id"} <= set(doc)
    assert set(doc["snapshot"]) == {"id", "volume", "bytes", "files", "sockets", "digest", "taken_at", "note"}
    assert doc["paused"] == ["db"] and doc["paused_s"] == 0.4 and doc["ledger_id"] == 150
    assert set(doc["cap"]) == {"bytes", "used", "left", "store"}


def test_snapshot_says_only_what_was_done(py: str, scratch: Path, adele: FakeAdele) -> None:
    """Nothing paused: no pause clause. No cap in the answer: no cap clause (each clause says what was
    done, FR-44). Sockets not copied are said (R24)."""
    body = snapshot_body(paused=[], paused_ms=0, snapshot={**SNAPSHOT, "sockets": 1})
    del body["cap"]
    adele.answer("POST", "/v1/requests", 200, body)
    r = env(py, scratch, adele, None, "snapshot", NAME, "db-data")
    assert r.returncode == 0, r.stderr
    assert head(r) == f"verdict: snapshot {NAME} db-data: {SNAP}, 48.0 KiB, 12 files, 1 socket not copied"


def test_snapshot_names_the_project_directorys_environment_by_default(
    py: str, scratch: Path, adele: FakeAdele, ws: Path
) -> None:
    adele.answer("POST", "/v1/requests", 200, snapshot_body())
    proj = str(ws / "proj")
    r = env(py, scratch, adele, ws, "snapshot", proj, "db-data")
    assert r.returncode == 0, r.stderr
    assert sent_post(adele)["params"]["name"] == load_adele().default_name(os.path.realpath(proj))


def test_snapshot_over_the_cap_is_the_grant_envelope(py: str, scratch: Path, adele: FakeAdele) -> None:
    extend = "docker exec timelike-adele adeled extend nested snapshots 2GiB"
    refusal = {
        "outcome": "refused",
        "performed": False,
        "grant": "nested",
        "limit": {
            "name": "snapshots",
            "allowed": "1 GiB (300 MiB used)",
            "needed": "volume db-data: 900 MiB",
        },
        "extend": extend,
        "ledger_id": 152,
    }
    adele.answer("POST", "/v1/requests", 403, refusal)
    r = env(py, scratch, adele, None, "--json", "snapshot", NAME, "db-data")
    assert r.returncode == 4, r.stderr
    envelope = json.loads(r.stdout)
    assert envelope["status"] == "grant_required" and envelope["extend"] == extend
    assert envelope["scope"] == "snapshot" and "confirm" not in envelope
    assert load_conform().check_envelope("adele", r.stdout, {"grant_required", "confirmation_required"}) == []


def test_an_unknown_volume_is_exit_3_naming_the_environments_own(
    py: str, scratch: Path, adele: FakeAdele
) -> None:
    adele.answer(
        "POST",
        "/v1/requests",
        404,
        {"error": "no such volume in this environment: ./data", "volumes": ["db-data", "cache"]},
    )
    r = env(py, scratch, adele, None, "snapshot", NAME, "./data")
    assert r.returncode == 3
    line = one_error_line(r)
    assert (
        "no such volume in this environment: ./data" in line and f"{NAME}'s volumes: db-data, cache" in line
    )


def test_an_unknown_environment_is_exit_3_naming_the_live_ones(
    py: str, scratch: Path, adele: FakeAdele
) -> None:
    adele.answer("POST", "/v1/requests", 404, {"error": f"no environment named {NAME}", "envs": []})
    r = env(py, scratch, adele, None, "snapshot", NAME, "db-data")
    assert r.returncode == 3 and "no environment is live" in one_error_line(r)


def test_a_snapshot_that_failed_partway_names_the_cause_and_what_was_undone(
    py: str, scratch: Path, adele: FakeAdele
) -> None:
    adele.answer(
        "POST",
        "/v1/requests",
        502,
        {
            "error": "the snapshot store is full (no space left on device)",
            "performed": False,
            "partial_removed": True,
            "unpaused": ["db"],
            "still_paused": [],
        },
    )
    r = env(py, scratch, adele, None, "snapshot", NAME, "db-data")
    assert r.returncode == 1
    line = one_error_line(r)
    assert "failed: the snapshot store is full (no space left on device)" in line
    assert "the partial snapshot was removed, read back gone; unpaused db, read back running" in line


def test_a_snapshot_past_its_bound_is_124(py: str, scratch: Path, adele: FakeAdele) -> None:
    adele.answer(
        "POST",
        "/v1/requests",
        504,
        {"error": "the copy did not finish in 5m0s", "timed_out": True, "partial_removed": True,
         "unpaused": ["db"], "still_paused": []},
    )  # fmt: skip
    r = env(py, scratch, adele, None, "snapshot", NAME, "db-data")
    assert r.returncode == 124 and "the copy did not finish in 5m0s" in one_error_line(r)


def test_a_snapshot_needs_a_volume_and_a_short_note(py: str, scratch: Path, adele: FakeAdele) -> None:
    r = env(py, scratch, adele, None, "snapshot")
    assert r.returncode == 2 and "env snapshot needs a VOLUME" in one_error_line(r)
    r = env(py, scratch, adele, None, "snapshot", NAME, "db-data", "--note", "x" * 201)
    assert r.returncode == 2 and "at most 200" in one_error_line(r)
    assert not [s for s in adele.received() if s.method == "POST"]


# ── snapshots ──────────────────────────────────────────────────────────────────────────────────


def test_snapshots_lists_each_with_the_cap_used(py: str, scratch: Path, adele: FakeAdele) -> None:
    adele.answer("POST", "/v1/requests", 200, listed_body())
    r = env(py, scratch, adele, None, "snapshots", NAME)
    assert r.returncode == 0, r.stderr
    assert head(r) == f"verdict: snapshots {NAME}: 2 · 96.0 KiB of 1 GiB used"
    out = r.stdout.splitlines()
    assert out[2] == f"{SNAP}  db-data  48.0 KiB  12 files  2026-10-19T08:00:00Z  before the migration"
    assert "volumes: db-data, cache" in out and "cap 1 GiB: 1023.9 MiB left (store: volume)" in out
    assert sent_post(adele)["params"] == {"name": NAME} and sent_post(adele)["action"] == "snapshots"
    doc = doc_of(env(py, scratch, adele, None, "--json", "snapshots", NAME))
    assert {"name", "snapshots", "cap", "volumes"} <= set(doc)
    assert set(doc["snapshots"][0]) == {"id", "volume", "bytes", "files", "digest", "taken_at", "note"}


# ── restore: rule 9 (FR-38, R27) ───────────────────────────────────────────────────────────────


def test_restore_without_yes_is_exit_4_naming_what_is_replaced_and_stopped(
    py: str, scratch: Path, adele: FakeAdele
) -> None:
    adele.answer("POST", "/v1/requests", 200, plan_body(["db", "web"]))
    r = env(py, scratch, adele, None, "--json", "restore", NAME, SNAP)
    no_traceback(r)
    assert r.returncode == 4, r.stderr
    envelope = json.loads(r.stdout)
    assert envelope["status"] == "confirmation_required"
    assert envelope["plan"][0] == (f"replace volume db-data of {NAME} with {SNAP}; stop db, web")
    assert envelope["confirm"] == f"adele env --json restore {NAME} {SNAP} --yes"  # the agent's own words
    assert load_conform().check_envelope("adele", r.stdout, {"grant_required", "confirmation_required"}) == []
    sent = sent_post(adele)
    assert sent["action"] == "restore" and sent["params"] == {"name": NAME, "snapshot": SNAP, "dry_run": True}
    assert len([s for s in adele.received() if s.method == "POST"]) == 1  # the plan only


def test_restore_without_yes_in_text_mode_is_rule_14s_line(py: str, scratch: Path, adele: FakeAdele) -> None:
    adele.answer("POST", "/v1/requests", 200, plan_body())
    r = env(py, scratch, adele, None, "restore", NAME, SNAP)
    assert r.returncode == 4
    line = one_error_line(r)
    assert line.startswith(
        f"error: confirmation required: replace volume db-data of {NAME} with {SNAP}; stop db"
    )
    assert line.endswith(f"to proceed, run: adele --text env restore {NAME} {SNAP} --yes")


def test_restore_dry_run_prints_the_plan_and_changes_nothing(
    py: str, scratch: Path, adele: FakeAdele
) -> None:
    adele.answer("POST", "/v1/requests", 200, plan_body())
    r = env(py, scratch, adele, None, "restore", NAME, SNAP, "--dry-run", "--yes")
    assert r.returncode == 0, r.stderr
    assert head(r) == f"verdict: restore {NAME} db-data from {SNAP}: dry run, nothing changed · would stop db"
    assert "the volume's present contents are not kept" in r.stdout
    assert sent_post(adele)["params"]["dry_run"] is True
    doc = doc_of(env(py, scratch, adele, None, "--json", "restore", NAME, SNAP, "--dry-run"))
    assert {k: doc[k] for k in ("name", "snapshot", "volume", "stop", "dry_run")} == {
        "name": NAME, "snapshot": SNAP, "volume": "db-data", "stop": ["db"], "dry_run": True,
    }  # fmt: skip


def test_restore_with_yes_waits_for_readiness_as_up_does(py: str, scratch: Path, adele: FakeAdele) -> None:
    starting, healthy = [svc("db", health="starting")], [svc("db", health="healthy")]
    adele.answer("POST", "/v1/requests", 200, restore_body(starting))
    adele.answer("GET", f"/v1/envs/{NAME}", 200, {"name": NAME, "services": starting})
    later(1.0, lambda: adele.answer("GET", f"/v1/envs/{NAME}", 200, {"name": NAME, "services": healthy}))
    r = env(py, scratch, adele, None, "restore", NAME, SNAP, "--yes", "--wait", "30", timeout=40)
    no_traceback(r)
    assert r.returncode == 0, r.stderr
    verdict = head(r)
    assert verdict.startswith(
        f"verdict: restore {NAME} db-data from {SNAP}: digest read back · stopped db for 3.1 s · 1 ready in "
    ), verdict
    assert verdict.endswith(" s of 30 s") and "probed" not in verdict  # no port was probed (D22 B)
    assert "db  ready (healthy)" in r.stdout
    assert len([s for s in adele.received() if s.method == "GET"]) >= 2
    assert sent_post(adele)["params"] == {"name": NAME, "snapshot": SNAP, "dry_run": False}


def test_restore_data_keeps_its_keys(py: str, scratch: Path, adele: FakeAdele, listener: int) -> None:
    adele.answer("POST", "/v1/requests", 200, restore_body([svc("db", ports=[listener])]))
    r = env(py, scratch, adele, None, "--json", "restore", NAME, SNAP, "--yes")
    assert r.returncode == 0, r.stderr
    doc = doc_of(r)
    assert {"name", "snapshot", "volume", "stopped", "digest", "services", "dry_run"} <= set(doc)
    assert doc["snapshot"] == SNAP and doc["stopped"] == ["db"] and doc["dry_run"] is False
    assert doc["services"][0]["ready"] == "ready" and doc["services"][0]["addresses"] == [
        f"127.0.0.1:{listener}"
    ]
    assert doc["verdict"].endswith(" · ports probed from the agent container")  # a port was probed (D22 B)


def test_a_service_not_ready_after_a_restore_is_exit_1_and_names_status_and_down(
    py: str, scratch: Path, adele: FakeAdele
) -> None:
    starting = [svc("db", health="starting")]
    adele.answer("POST", "/v1/requests", 200, restore_body(starting))
    adele.answer("GET", f"/v1/envs/{NAME}", 200, {"name": NAME, "services": starting})
    r = env(py, scratch, adele, None, "restore", NAME, SNAP, "--yes", "--wait", "1")
    assert r.returncode == 1, r.stderr
    verdict = head(r)
    assert verdict == (
        f"verdict: restore {NAME} db-data from {SNAP}: digest read back · not ready within 1 s (0 of 1 ready,"
        " read back); the data stays restored"
    )
    assert f"next: adele env status {NAME} shows it · adele env down {NAME} removes it" in r.stdout
    tail = verdict.split(f"{SNAP}: ", 1)[1].replace(
        "1 s (0 of 1", "600 s (9 of 9"
    )  # the longest, at R32's name
    assert len(f"verdict: restore {LONG_NAME} postgres-data from {SNAP}: {tail}") <= 200
    assert "db  running (starting)" in r.stdout


def test_a_service_that_fails_after_a_restore_is_exit_1(py: str, scratch: Path, adele: FakeAdele) -> None:
    adele.answer("POST", "/v1/requests", 200, restore_body([svc("db", state="exited", code=3)]))
    r = env(py, scratch, adele, None, "restore", NAME, SNAP, "--yes")
    assert r.returncode == 1
    line = one_error_line(r)
    assert "service db exited 3" in line and "the data stays restored" in line
    assert f"adele env status {NAME}" in line and f"adele env down {NAME}" in line


def test_a_digest_that_is_not_the_records_is_never_called_restored(
    py: str, scratch: Path, adele: FakeAdele
) -> None:
    adele.answer("POST", "/v1/requests", 200, restore_body([svc("db", health="healthy")], digest="sha256:00"))
    r = env(py, scratch, adele, None, "restore", NAME, SNAP, "--yes")
    assert r.returncode == 1 and "is not the snapshot's record" in one_error_line(r)


def test_an_unknown_snapshot_is_exit_3_naming_the_environments(
    py: str, scratch: Path, adele: FakeAdele
) -> None:
    adele.answer(
        "POST", "/v1/requests", 404, {"error": f"no snapshot s-00000000 in {NAME}", "snapshots": [SNAP]}
    )
    r = env(py, scratch, adele, None, "restore", NAME, "s-00000000")
    assert r.returncode == 3
    assert f"{NAME}'s snapshots: {SNAP}" in one_error_line(r)


@pytest.mark.parametrize(
    ("body", "said"),
    [
        (
            {"error": f"snapshot {SNAP} does not match its record: digest differs", "stopped": []},
            "nothing was stopped or changed",
        ),
        (
            {"error": "the copy failed: helper exit 1", "partial": True, "started": ["db"]},
            "the volume's contents are partial; started again: db",
        ),
    ],
    ids=["before", "after"],
)
def test_a_failed_restore_is_exit_1_saying_what_it_left(
    py: str, scratch: Path, adele: FakeAdele, body: dict[str, Any], said: str
) -> None:
    adele.answer("POST", "/v1/requests", 502, body)
    r = env(py, scratch, adele, None, "restore", NAME, SNAP, "--yes")
    assert r.returncode == 1
    assert said in one_error_line(r)


# ── snapshot-rm: rule 9 too (R31) ──────────────────────────────────────────────────────────────


def test_snapshot_rm_without_yes_is_exit_4_naming_the_snapshot_and_its_size(
    py: str, scratch: Path, adele: FakeAdele
) -> None:
    adele.answer("POST", "/v1/requests", 200, listed_body())
    r = env(py, scratch, adele, None, "--json", "snapshot-rm", NAME, SNAP)
    assert r.returncode == 4, r.stderr
    envelope = json.loads(r.stdout)
    assert envelope["status"] == "confirmation_required" and envelope["scope"] == "env snapshot-rm"
    assert envelope["plan"][0] == (
        f"remove snapshot {SNAP} of db-data (48.0 KiB, taken 2026-10-19T08:00:00Z):"
        " the only copy of that state"
    )
    assert envelope["confirm"].endswith(f"snapshot-rm {NAME} {SNAP} --yes")
    assert sent_post(adele)["action"] == "snapshots"  # read, never removed without --yes


def test_snapshot_rm_of_an_unknown_snapshot_is_exit_3(py: str, scratch: Path, adele: FakeAdele) -> None:
    adele.answer("POST", "/v1/requests", 200, listed_body())
    r = env(py, scratch, adele, None, "snapshot-rm", NAME, "s-00000000")
    assert r.returncode == 3
    assert f"{NAME}'s snapshots: {SNAP}, s-0b1c2d3e" in one_error_line(r)


def test_snapshot_rm_with_yes_removes_it_and_says_what_it_freed(
    py: str, scratch: Path, adele: FakeAdele
) -> None:
    adele.answer(
        "POST",
        "/v1/requests",
        200,
        {"outcome": "removed", "snapshot": SNAP, "bytes": 49152, "cap": dict(CAP), "ledger_id": 153},
    )
    r = env(py, scratch, adele, None, "snapshot-rm", NAME, SNAP, "--yes")
    assert r.returncode == 0, r.stderr
    assert head(r) == f"verdict: snapshot-rm {NAME} {SNAP}: removed, read back · 48.0 KiB freed"
    assert sent_post(adele)["params"] == {"name": NAME, "snapshot": SNAP}
    doc = doc_of(env(py, scratch, adele, None, "--json", "snapshot-rm", NAME, SNAP, "--yes"))
    assert {k: doc[k] for k in ("name", "snapshot", "freed_bytes")} == {
        "name": NAME, "snapshot": SNAP, "freed_bytes": 49152,
    }  # fmt: skip


# ── the flags belong to their verbs ────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("argv", "said"),
    [
        (["env", "up", "--yes"], "--yes belongs to adele env restore and adele env snapshot-rm"),
        (["env", "down", NAME, "--dry-run"], "--dry-run belongs to adele env restore"),
        (["request", "standin.box", "create", "--name", "tl-1", "--yes"], "--yes belongs to"),
        (["env", "snapshots", NAME, "--note", "x"], "--note belongs to adele env snapshot"),
        (["env", "down", NAME, "extra"], "unexpected argument 'extra'"),
    ],
    ids=["up-yes", "down-dry-run", "request-yes", "note", "operand"],
)
def test_a_flag_on_a_verb_it_does_not_belong_to_is_usage(
    py: str, scratch: Path, adele: FakeAdele, argv: list[str], said: str
) -> None:
    r = go(py, scratch, adele, None, *argv)
    assert r.returncode == 2 and said in one_error_line(r)
    assert not [s for s in adele.received() if s.method == "POST"]


# ── the manifest, help and announcement (P3, R31) ──────────────────────────────────────────────


def test_the_manifest_passes_conforms_checks(py: str, scratch: Path) -> None:
    info = json.loads(go(py, scratch, FakeAdele(url="http://127.0.0.1:9"), None, "--agent-info").stdout)
    assert load_conform().check_manifest("adele", info) == []
    assert "a nested environment's Docker volumes" in info["summary"]
    assert "snapshot, undo" in info["summary"]  # the workspace's own files, named (P3)


def test_help_names_the_slice_2_verbs_and_the_workspaces_tools(py: str, scratch: Path) -> None:
    r = go(py, scratch, FakeAdele(url="http://127.0.0.1:9"), None, "--help")
    assert r.returncode == 0 and len(r.stdout.splitlines()) <= 40
    for verb in ("snapshot", "snapshots", "restore", "snapshot-rm"):
        assert f"adele env {verb} [NAME]" in r.stdout
    assert "the workspace's own files are snapshot and undo" in r.stdout


@pytest.mark.parametrize("tool", ["snapshot", "undo"])
def test_the_workspaces_tools_point_at_adele_for_an_environments_volumes(
    py: str, scratch: Path, tool: str
) -> None:
    r = run([py, str(TOOLS_DIR / tool), "--agent-info"], base_env(scratch))
    assert r.returncode == 0, r.stderr
    assert "a nested environment's Docker volumes: adele env " in json.loads(r.stdout)["summary"]


# ── D22 observations A and B (FR-44, R32) ──────────────────────────────────────────────────────


def test_every_up_verdict_fits_at_a_30_character_name() -> None:
    """The longest of each kind (performed, unchanged, devcontainer, with unchecked services), each with a
    port probed and at the longest times --wait allows: within the 191 columns rule 13 leaves after
    "verdict: ", so the printed line is at most 200 and never cut (D22 A)."""
    mod = load_adele()
    assert len(LONG_NAME) == 30 and 200 - len("verdict: ") == mod.VERDICT_MAX
    web = {**svc("web", ports=[8080]), "alias": f"web.{LONG_NAME}"}
    ready = [
        (svc("db", health="healthy"), "ready", "ready (healthy)"),
        (web, "ready", "ready (running, ports accept)"),
    ]
    unchecked = [(svc(f"worker{i}"), "unchecked", "running, no readiness check") for i in range(2)]
    base = up_body([])
    kinds = {
        "performed": (base, ready),
        "unchanged": ({**base, "outcome": "unchanged"}, ready),
        "devcontainer": ({**base, "outcome": "unchanged", "kind": "devcontainer"}, ready + unchecked),
        "unchecked": ({**base, "host_git": "unknown"}, ready + unchecked),
        "two-digit": ({**base, "outcome": "unchanged", "kind": "devcontainer"}, ready * 6 + unchecked * 5),
    }
    for kind, (body, states) in kinds.items():
        verdict = mod.up_verdict(LONG_NAME, body, states, 599.9, 600.0)
        assert len("verdict: " + verdict) <= 200, (kind, len(verdict), verdict)
        assert "ports probed from the agent container" in verdict, kind
    full = mod.up_verdict(LONG_NAME, kinds["devcontainer"][0], ready + unchecked, 599.9, 600.0)
    assert "2 ready, 2 running, no readiness check" in full  # the long form, where it fits


def test_ports_probed_is_said_only_when_a_port_was_probed() -> None:
    mod = load_adele()
    states = [(svc("db", health="healthy"), "ready", "ready (healthy)"), (svc("w"), "unchecked", "x")]
    verdict = mod.up_verdict(NAME, up_body([]), states, 1.0, 120.0)
    assert "probed" not in verdict and verdict.endswith("in 1.0 s of 120 s · read back · host git enforced")
    exited = [(svc("job", state="exited", code=0, ports=[1]), "completed", "completed (exit 0)")]
    assert "probed" not in mod.up_verdict(NAME, up_body([]), exited, 1.0, 120.0)


def test_the_printed_up_verdict_has_no_cut_marker(py: str, scratch: Path, adele: FakeAdele, ws: Path) -> None:
    services = [svc("db", health="healthy"), svc("worker")]
    adele.answer(
        "POST", "/v1/requests", 200, {**up_body(services, outcome="unchanged"), "kind": "devcontainer"}
    )
    r = go(py, scratch, adele, ws, "env", "up", str(ws / "proj"), "--project", LONG_NAME, "--wait", "600")
    assert r.returncode == 0, r.stderr
    assert not CUT.search(r.stdout) and len(head(r)) <= 200, head(r)


def test_the_longest_restore_and_snapshot_verdicts_fit(
    py: str, scratch: Path, adele: FakeAdele, listener: int
) -> None:
    """A restore that stopped two services and waits for a ready one, a probed one and one unchecked, of a
    13-character volume; a snapshot that paused two and left two sockets. Each printed whole, with room
    for the longest time --wait allows (the test's own times are short: 2 more digits are counted)."""
    services = [svc("db", health="healthy"), svc("web", ports=[listener]), svc("worker")]
    snap = {**SNAPSHOT, "volume": "postgres-data", "bytes": (1 << 30) - 1024, "files": 123456, "sockets": 2}
    adele.answer(
        "POST",
        "/v1/requests",
        200,
        restore_body(
            services, volume="postgres-data", stopped=["db", "worker"], stopped_ms=12300, snapshot=snap
        ),
    )
    r = env(py, scratch, adele, None, "restore", LONG_NAME, SNAP, "--yes", "--wait", "600")
    assert r.returncode == 0, r.stderr
    restore = head(r)
    assert not CUT.search(restore) and len(restore) + 2 <= 200, (len(restore), restore)
    assert "ports probed from the agent container" in restore
    paused = [{"service": "db", "container": "a"}, {"service": "worker", "container": "b"}]
    adele.answer("POST", "/v1/requests", 200, snapshot_body(snapshot=snap, paused=paused, paused_ms=12300))
    r = env(py, scratch, adele, None, "snapshot", LONG_NAME, "postgres-data")
    assert r.returncode == 0, r.stderr
    snapshot = head(r)
    assert not CUT.search(snapshot) and len(snapshot) <= 200, (len(snapshot), snapshot)
    assert "paused db, worker for 12.3 s" in snapshot and "2 sockets not copied" in snapshot


def test_a_verdict_too_long_for_its_line_takes_its_short_forms() -> None:
    mod = load_adele()
    parts = [
        ("x" * 130, "x" * 130),
        (" · stopped db, web, worker, cache", " · stopped 4"),
        (" · y" * 10, " · y"),
    ]
    verdict = mod.fit(parts, [1, 2])
    assert verdict == "x" * 130 + " · stopped 4" + " · y" * 10 and len(verdict) <= mod.VERDICT_MAX
    assert mod.fit([*parts[:2], (" · y" * 20, " · y")], [1, 2]) == "x" * 130 + " · stopped 4 · y"
    assert mod.fit([("a", "b")], [0]) == "a"  # what fits keeps its long form


def test_a_restore_past_adeles_bound_is_124_and_her_word_is_not_the_readiness(
    py: str, scratch: Path, adele: FakeAdele
) -> None:
    """A 504 (`timed_out`) is 124. Adele's own read of readiness is carried as data only: the verdict is the
    client's poll, as up's is (here she said healthy, the daemon now says starting: not ready)."""
    adele.answer("POST", "/v1/requests", 504, {"error": "the copy did not finish in 5m0s", "timed_out": True})
    r = env(py, scratch, adele, None, "restore", NAME, SNAP, "--yes")
    assert r.returncode == 124 and "the copy did not finish in 5m0s" in one_error_line(r)
    starting = [svc("db", health="starting")]
    adele.answer("POST", "/v1/requests", 200, restore_body(starting, adele_readiness={"db": "healthy"}))
    adele.answer("GET", f"/v1/envs/{NAME}", 200, {"name": NAME, "services": starting})
    r = env(py, scratch, adele, None, "--json", "restore", NAME, SNAP, "--yes", "--wait", "1")
    assert r.returncode == 1
    doc = doc_of(r)
    assert doc["adele_readiness"] == {"db": "healthy"} and doc["services"][0]["ready"] == "waiting"


def test_restore_and_snapshot_give_adele_her_own_bound_apart_from_wait() -> None:
    mod = load_adele()
    assert mod.SNAPSHOT_HTTP_S >= 2 * 60 + 5 * 60 + 60  # her digest, copy, stops and read-back, with room
    assert mod.ENV_WAIT_S == 120.0  # --wait's default, as up's: the readiness wait after her answer
