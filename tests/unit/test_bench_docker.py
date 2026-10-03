"""Units for bench/benchlib/docker.py (T007), against fake `inspect` JSON — no daemon here (R10)."""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from benchlib import docker as dk

SHA = "a" * 40


class FakeDocker:
    """Records every argv; answers from a table keyed by the first four argv words."""

    def __init__(self, answers: dict[tuple[str, ...], dk.Completed]) -> None:
        self.answers = answers
        self.calls: list[list[str]] = []

    def __call__(self, argv: Sequence[str]) -> dk.Completed:
        self.calls.append(list(argv))
        for n in (4, 3, 2):
            hit = self.answers.get(tuple(argv[:n]))
            if hit is not None:
                return hit
        return dk.Completed(1, "", f"unexpected call {argv}")


def inspect(obj: dict[str, Any]) -> dk.Completed:
    return dk.Completed(0, json.dumps([obj]), "")


def image(
    rev: str | None, env: list[str] | None = None, image_id: str = "sha256:" + "1" * 64
) -> dict[str, Any]:
    labels = {} if rev is None else {dk.REVISION_LABEL: rev}
    return {"Id": image_id, "Config": {"Labels": labels, "Env": env or ["PATH=/usr/bin"]}}


def test_image_identity_reads_id_label_and_env() -> None:
    fake = FakeDocker({("docker", "image", "inspect", "img"): inspect(image(SHA, ["A=1", "B=x=y"]))})
    ident = dk.image_identity("img", fake)
    assert ident.image_id.startswith("sha256:")
    assert ident.revision == SHA
    assert ident.env == {"A": "1", "B": "x=y"}


def test_image_identity_tolerates_null_labels_and_env() -> None:
    obj = {"Id": "sha256:x", "Config": {"Labels": None, "Env": None}}
    ident = dk.image_identity("img", FakeDocker({("docker", "image", "inspect", "img"): inspect(obj)}))
    assert (ident.revision, ident.env) == ("", {})


@pytest.mark.parametrize(
    ("answer", "match"),
    [
        (dk.Completed(1, "", "Error: No such image: img\nmore"), "No such image"),
        (dk.Completed(1, "", ""), "no stderr"),
        (dk.Completed(0, "not json", ""), "not JSON"),
        (dk.Completed(0, "[]", ""), "expected one object"),
    ],
)
def test_inspect_failures_are_named(answer: dk.Completed, match: str) -> None:
    with pytest.raises(dk.DockerError, match=match):
        dk.image_identity("img", FakeDocker({("docker", "image", "inspect", "img"): answer}))


def ident(ref: str, rev: str, image_id: str = "sha256:1") -> dk.ImageIdentity:
    return dk.ImageIdentity(ref=ref, image_id=image_id, revision=rev, env={})


def test_check_identity_passes_when_every_stamp_matches() -> None:
    assert dk.check_identity(SHA, [ident("a", SHA), ident("b", SHA)]) == []


def test_check_identity_names_both_revisions_on_a_stale_image() -> None:
    problems = dk.check_identity(SHA, [ident("timelike-agent:local", "b" * 40)])
    assert len(problems) == 1
    assert SHA in problems[0] and "b" * 40 in problems[0] and "stale" in problems[0]


def test_check_identity_refuses_empty_stamps_and_empty_expectation() -> None:
    problems = dk.check_identity("", [ident("x", ""), ident("y", SHA, image_id="")])
    assert any("BENCH_GIT_SHA is empty" in p for p in problems)
    assert any("x: image carries no" in p for p in problems)
    assert any("y: image has no Id" in p for p in problems)


def test_start_container_uses_identical_flags_and_the_image_id() -> None:
    fake = FakeDocker({("docker", "run"): dk.Completed(0, "cid123\n", "")})
    assert dk.start_container("sha256:abc", fake) == "cid123"
    argv = fake.calls[0]
    for flag in ("--init", "--cap-drop", "no-new-privileges", "none"):
        assert flag in argv
    assert "-v" not in argv and "--volume" not in argv and "-t" not in argv and "-i" not in argv
    assert argv[-2:] == ["sha256:abc", "infinity"]


def test_start_container_without_an_id_is_an_error() -> None:
    with pytest.raises(dk.DockerError, match="no container id"):
        dk.start_container("img", FakeDocker({("docker", "run"): dk.Completed(0, "  \n", "")}))


def test_prepare_remove_env_and_term() -> None:
    fake = FakeDocker(
        {
            ("docker", "exec", "-u", "agent"): dk.Completed(0, "", ""),
            ("docker", "rm"): dk.Completed(0, "", ""),
            ("docker", "container", "inspect", "cid"): inspect({"Config": {"Env": ["TOKEN_X=1"]}}),
        }
    )
    dk.prepare_task_dir("cid", fake)
    assert fake.calls[-1][-3:] == ["mkdir", "-p", "task"]
    dk.remove_container("cid", fake)
    assert fake.calls[-1] == ["docker", "rm", "-f", "cid"]
    assert dk.container_env("cid", fake) == {"TOKEN_X": "1"}
    assert dk.exec_term("cid", fake) == ""


def test_container_env_without_env_list() -> None:
    fake = FakeDocker({("docker", "container", "inspect", "cid"): inspect({"Config": {}})})
    assert dk.container_env("cid", fake) == {}


def test_subprocess_runner_replaces_argv0_and_reports_missing_binary(tmp_path: Path) -> None:
    fake = tmp_path / "docker"
    fake.write_text('#!/bin/sh\necho "$@"\n')
    fake.chmod(0o755)
    done = dk.subprocess_runner(str(fake))(["docker", "ps", "-q"])
    assert (done.returncode, done.stdout) == (0, "ps -q\n")
    missing = dk.subprocess_runner(str(tmp_path / "nope"))(["docker", "ps"])
    assert missing.returncode == 127


def test_subprocess_runner_times_out(tmp_path: Path) -> None:
    fake = tmp_path / "docker"
    fake.write_text("#!/bin/sh\nexec sleep 10\n")
    fake.chmod(0o755)
    done = dk.subprocess_runner(str(fake), timeout_s=0.3)(["docker", "ps"])
    assert done.returncode == 124 and "timed out" in done.stderr
    assert os.path.exists(fake)
