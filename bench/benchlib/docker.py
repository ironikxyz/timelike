"""docker — image identity, the staleness check, and task-container lifecycle (FR-2, FR-5, FR-8; RB5, RB8).

Every docker call goes through an injectable `run` function, so the logic is unit-tested on the host
lane against fake `inspect` JSON (no daemon there, research R10) and runs unchanged in the driver.

Identity is read from the images themselves, never from a success message (H3, cross-stack P004):
- the revision is the `org.opencontainers.image.revision` label, and it must equal the revision the
  bench was asked to measure. An empty label or a mismatch refuses the run, naming both values
  (docker-compose Q004: a stale image is the silent failure here)
- the image is pinned by its `.Id` once, and every container is started BY THAT ID, so a rebuild in
  between cannot swap it. A local build has no RepoDigests, so the ID is recorded as `image_id` and
  never called a registry digest.

Task containers are identical for both images: fresh per run, `--init`, no network, no capabilities,
no new privileges, no mounts, no socket (H1). Only the driver holds the socket.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from benchlib.keys import env_list_to_mapping

REVISION_LABEL = "org.opencontainers.image.revision"
TASK_HOME = "/home/agent"
TASK_DIR_NAME = "task"

Runner = Callable[[Sequence[str]], "Completed"]


@dataclass(frozen=True)
class Completed:
    returncode: int
    stdout: str
    stderr: str


class DockerError(RuntimeError):
    """A docker call failed. The message names the call and docker's own first stderr line."""


@dataclass(frozen=True)
class ImageIdentity:
    ref: str
    image_id: str
    revision: str
    env: dict[str, str]


def subprocess_runner(docker: str = "docker", timeout_s: float = 120.0) -> Runner:
    """The real runner: argv[0] is replaced by the docker binary; stdin at EOF, time-limited (P2)."""

    def run(argv: Sequence[str]) -> Completed:
        full = [docker, *argv[1:]] if argv and argv[0] == "docker" else list(argv)
        try:
            p = subprocess.run(
                full, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout_s, check=False
            )
        except subprocess.TimeoutExpired:
            return Completed(124, "", f"timed out after {timeout_s:.0f} s: {' '.join(full[:3])} …")
        except FileNotFoundError:
            return Completed(127, "", f"{docker}: command not found")
        return Completed(p.returncode, p.stdout, p.stderr)

    return run


def _call(run: Runner, argv: Sequence[str]) -> str:
    done = run(argv)
    if done.returncode != 0:
        first = (done.stderr.strip().splitlines() or ["no stderr"])[0]
        raise DockerError(f"{' '.join(argv[:3])} failed (exit {done.returncode}): {first}")
    return done.stdout


def _inspect_one(run: Runner, kind: str, ref: str) -> dict[str, Any]:
    out = _call(run, ["docker", kind, "inspect", ref])
    try:
        data = json.loads(out)
    except json.JSONDecodeError as e:
        raise DockerError(f"docker {kind} inspect {ref}: output is not JSON ({e.msg})") from e
    if not isinstance(data, list) or len(data) != 1 or not isinstance(data[0], dict):
        raise DockerError(f"docker {kind} inspect {ref}: expected one object, got {type(data).__name__}")
    return data[0]


def _config(obj: dict[str, Any]) -> dict[str, Any]:
    cfg = obj.get("Config")
    return cfg if isinstance(cfg, dict) else {}


def image_identity(ref: str, run: Runner) -> ImageIdentity:
    obj = _inspect_one(run, "image", ref)
    cfg = _config(obj)
    labels_raw, env_raw = cfg.get("Labels"), cfg.get("Env")
    labels: dict[str, Any] = labels_raw if isinstance(labels_raw, dict) else {}
    env: list[Any] = env_raw if isinstance(env_raw, list) else []
    return ImageIdentity(
        ref=ref,
        image_id=str(obj.get("Id") or ""),
        revision=str(labels.get(REVISION_LABEL) or ""),
        env=env_list_to_mapping(str(e) for e in env),
    )


def check_identity(expected_revision: str, images: Sequence[ImageIdentity]) -> list[str]:
    """Violations that refuse the run (FR-2, FR-8). Empty means every stamp is present and current."""
    problems: list[str] = []
    if not expected_revision.strip():
        problems.append("the bench was given no revision to measure (BENCH_GIT_SHA is empty)")
    for img in images:
        if not img.image_id:
            problems.append(f"{img.ref}: image has no Id")
        if not img.revision:
            problems.append(f"{img.ref}: image carries no {REVISION_LABEL} label (unstamped, H8)")
        elif expected_revision.strip() and img.revision != expected_revision:
            problems.append(
                f"{img.ref}: image is revision {img.revision}, the checkout is {expected_revision}"
                " — stale image; rebuild with make bench-images"
            )
    return problems


def start_container(image_id: str, run: Runner) -> str:
    """A fresh task container, started by image ID, with flags identical for every image (RB5)."""
    argv = [
        "docker", "run", "-d", "--init", "--network", "none", "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges", "--entrypoint", "sleep", image_id, "infinity",
    ]  # fmt: skip
    cid = _call(run, argv).strip()
    if not cid:
        raise DockerError(f"docker run {image_id}: printed no container id")
    return cid


def prepare_task_dir(container_id: str, run: Runner) -> None:
    """`docker exec -w` needs the directory to exist; create it as the agent, outside the counted run."""
    _call(run, ["docker", "exec", "-u", "agent", "-w", TASK_HOME, container_id, "mkdir", "-p", TASK_DIR_NAME])


def remove_container(container_id: str, run: Runner) -> None:
    """Best effort, always attempted: a leftover container is reported by docker, not by the bench."""
    run(["docker", "rm", "-f", container_id])


def container_env(container_id: str, run: Runner) -> dict[str, str]:
    env = _config(_inspect_one(run, "container", container_id)).get("Env")
    return env_list_to_mapping(str(e) for e in env) if isinstance(env, list) else {}


def exec_term(container_id: str, run: Runner) -> str:
    """TERM as a tool call sees it (RB2: must be empty — moby sets it only for a TTY exec)."""
    out = _call(run, ["docker", "exec", "-u", "agent", container_id, "sh", "-c", 'printf %s "${TERM-}"'])
    return out.strip()
