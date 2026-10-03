"""A stand-in `docker` for timelike-bench's host-lane units (T009). NOT a docker emulator.

It answers exactly the calls benchlib.docker and DockerExecutor make, from a JSON config named by
FAKE_DOCKER_CONFIG, and runs `exec` commands LOCALLY in a per-container directory with the environment
the config gives that image (the vanilla / timelike emulations of test_bench_catalog.py). It proves
the CLI wires docker.py, runner.py and report.py together; it proves nothing about Docker (R10).

Config: {"root": dir, "images": {ref: {"id", "revision", "env": [..], "exec_env": {..}}}}
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path


def main(argv: list[str]) -> int:
    cfg = json.loads(Path(os.environ["FAKE_DOCKER_CONFIG"]).read_text())
    root = Path(cfg["root"])
    root.mkdir(parents=True, exist_ok=True)
    by_id = {img["id"]: img for img in cfg["images"].values()}
    log = root / "calls.log"
    with log.open("a") as fh:
        fh.write(" ".join(argv[:4]) + "\n")

    if argv[:2] == ["image", "inspect"]:
        img = cfg["images"].get(argv[2])
        if img is None:
            print(f"Error: No such image: {argv[2]}", file=sys.stderr)
            return 1
        labels = {"org.opencontainers.image.revision": img["revision"]} if img["revision"] else {}
        print(json.dumps([{"Id": img["id"], "Config": {"Labels": labels, "Env": img["env"]}}]))
        return 0
    if argv[0] == "run":
        image_id = argv[-2]
        cid = uuid.uuid4().hex
        (root / cid / "home" / "task").mkdir(parents=True)
        (root / cid / "image").write_text(image_id)
        print(cid)
        return 0
    if argv[:2] == ["container", "inspect"]:
        img = by_id[(root / argv[2] / "image").read_text()]
        print(json.dumps([{"Config": {"Env": img["env"] + img.get("container_env", [])}}]))
        return 0
    if argv[0] == "rm":
        with (root / "removed.log").open("a") as fh:
            fh.write(argv[-1] + "\n")
        return 0
    if argv[0] == "exec":
        # exec -u agent [-w DIR] CID CMD...
        rest = argv[3:]
        workdir = None
        if rest[0] == "-w":
            workdir, rest = rest[1], rest[2:]
        cid, cmd = rest[0], rest[1:]
        img = by_id[(root / cid / "image").read_text()]
        home = root / cid / "home"
        cwd = home if workdir in (None, "/home/agent") else home / "task"
        env = {k: v.replace("@HOME@", str(home)) for k, v in img["exec_env"].items()}
        if cmd[:2] == ["mkdir", "-p"]:
            (home / cmd[2]).mkdir(exist_ok=True)
            return 0
        return subprocess.run(cmd, cwd=cwd, env=env, stdin=subprocess.DEVNULL, check=False).returncode
    print(f"fakedocker: unexpected call {argv}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
