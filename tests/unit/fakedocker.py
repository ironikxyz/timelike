"""A stand-in `docker` for timelike-bench's host-lane units (T009). NOT a docker emulator.

It answers exactly the calls benchlib.docker and DockerExecutor make, from a JSON config named by
FAKE_DOCKER_CONFIG, and runs `exec` commands LOCALLY in a per-container directory with the environment
the config gives that image (the vanilla / timelike emulations of test_bench_catalog.py). It proves
the CLI wires docker.py, runner.py and report.py together; it proves nothing about Docker (R10).

Config: {"root": dir, "images": {ref: {"id", "revision", "env": [..], "exec_env": {..}}}, "tools": [..]}

Slice 1 adds: the timelike tool list (`docker run --rm --entrypoint …/timelike IMAGE tools --json`, from
"tools"), the told placement (`exec … timelike announce --install --json`, every harness placed unless the
image sets "placement_fails"), and the OOM count (`exec CID cat …/memory.events`, always 0 here).

Lane 02s1-a adds two setup edges, matched by the setup's own first git command: "setup_sleep" (seconds the
setup takes before it starts, as a slow container's did) and "setup_fails" (the setup exits 3 at once).
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
    if argv[0] == "run" and "--rm" in argv:
        entry = argv[argv.index("--entrypoint") + 1] if "--entrypoint" in argv else ""
        if entry.endswith("/timelike") and argv[-2:] == ["tools", "--json"]:
            names = cfg.get("tools", ["run", "view", "search", "timelike"])
            print(json.dumps({"tools": [{"name": n, "kind": "timelike", "installed": True} for n in names]}))
            return 0
        print(f"fakedocker: unexpected run --rm {argv}", file=sys.stderr)
        return 1
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
        # exec [-u USER] [-w DIR] [-e NAME[=VALUE]]... CID CMD...
        i, workdir = 1, None
        while argv[i].startswith("-"):
            if argv[i] == "-w":
                workdir = argv[i + 1]
            i += 2 if argv[i] in ("-u", "-w", "-e") else 1
        cid, cmd = argv[i], argv[i + 1 :]
        img = by_id[(root / cid / "image").read_text()]
        if cmd == ["cat", "/sys/fs/cgroup/memory.events"]:
            print("low 0\nhigh 0\nmax 0\noom 0\noom_kill 0")
            return 0
        if cmd[:3] == ["/opt/timelike/bin/timelike", "announce", "--install"]:
            if img.get("placement_fails"):
                print("timelike: announce failed", file=sys.stderr)
                return 1
            states = [{"harness": h, "state": "placed"} for h in ("claude-code", "codex", "opencode")]
            print(json.dumps({"placements": states}))
            return 0
        home = root / cid / "home"
        cwd = home if workdir in (None, "/home/agent") else home / "task"
        env = {k: v.replace("@HOME@", str(home)) for k, v in img["exec_env"].items()}
        if "git init -q -b main" in cmd[-1]:  # a task's setup (catalog _PRELUDE), run through the wrapper
            if img.get("setup_fails"):
                cmd = [*cmd[:-1], "echo 'fatal: setup (fakedocker)' >&2; exit 3"]
            elif img.get("setup_sleep"):
                cmd = [*cmd[:-1], f"sleep {img['setup_sleep']}; {cmd[-1]}"]
        if cmd[:2] == ["mkdir", "-p"]:
            (home / cmd[2]).mkdir(exist_ok=True)
            return 0
        return subprocess.run(cmd, cwd=cwd, env=env, stdin=subprocess.DEVNULL, check=False).returncode
    print(f"fakedocker: unexpected call {argv}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
