"""The guards (feature 005 slice 1, T032; spec FR-42 to FR-47, D-19; FOR-MENTOR Item 22's ruling).

The whole chain on the host: a `bash -c` with the repository's /etc/timelike/shell-env.bash as BASH_ENV
(the `rm` and `git` functions), the repository's guard helper (through TIMELIKE_GUARD, the test-only
override, a shim running it with this interpreter), and git pointed at the repository's hook dispatcher
the way the image's GIT_CONFIG_* does. The destructive commands are the REAL `rm`, `git reset --hard`,
`git clean` and `git push --force`, against a real repository and a real local bare remote (cross-stack
P005), and what a snapshot or the trash brings back is judged by the test's own walk (P004). The image is
the Docker lane's (tests/e2e/a-guarded-destructive-command-*.bats).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO, base_env
from test_snapshot import tree, write

HOOK = REPO / "image" / "rootfs" / "etc" / "timelike" / "shell-env.bash"
DISPATCH_DIR = REPO / "image" / "rootfs" / "opt" / "timelike" / "git-hooks"
GUARD = REPO / "tools" / "libexec" / "guard"
UNDO = REPO / "tools" / "bin" / "undo"


@dataclass
class Box:
    tmp: Path
    home: Path
    ws: Path  # a git repository with one commit, pushed to `remote` as main
    remote: Path  # a bare repository
    scratch: Path
    shim: Path

    @property
    def state(self) -> Path:
        return self.scratch.with_name(self.scratch.name + "-state")

    def env(self, **extra: str) -> dict[str, str]:
        env = base_env(
            self.scratch,
            "guards",
            HOME=str(self.home),
            BASH_ENV=str(HOOK),
            TIMELIKE_GUARD=str(self.shim),
            TIMELIKE_SNAPSHOT_INTERVAL="off",  # the scheduled snapshot is its own test's
            GIT_CONFIG_NOSYSTEM="1",
            GIT_CONFIG_COUNT="1",
            GIT_CONFIG_KEY_0="core.hooksPath",
            GIT_CONFIG_VALUE_0=str(DISPATCH_DIR),
            GIT_AUTHOR_NAME="t",
            GIT_AUTHOR_EMAIL="t@example.invalid",
            GIT_COMMITTER_NAME="t",
            GIT_COMMITTER_EMAIL="t@example.invalid",
        )
        env.update(extra)
        return env

    def sh(self, cmd: str, cwd: Path | None = None, **extra: str) -> subprocess.CompletedProcess[str]:
        """`bash -c CMD` as a harness runs the agent's command: the hook reached through BASH_ENV."""
        return subprocess.run(
            ["bash", "-c", cmd],
            cwd=str(cwd or self.ws),
            env=self.env(**extra),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=60,
            start_new_session=True,
        )

    def records(self, ws: Path | None = None) -> list[dict[str, Any]]:
        import hashlib

        real = os.path.realpath(ws or self.ws)
        d = self.state / "workspaces" / hashlib.sha256(real.encode()).hexdigest()[:16] / "snaps"
        if not d.is_dir():
            return []
        return sorted((json.loads(p.read_text()) for p in d.glob("*.json")), key=lambda r: int(r["id"]))

    def trash_items(self) -> list[dict[str, Any]]:
        d = self.state / "trash" / "items"
        return sorted((json.loads(p.read_text()) for p in d.glob("*.json")), key=lambda r: int(r["id"]))

    def git(self, *args: str, cwd: Path | None = None) -> str:
        r = subprocess.run(
            ["git", *args],
            cwd=str(cwd or self.ws),
            env=self.env(BASH_ENV=""),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        return r.stdout.strip()

    def undo(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(UNDO), *args],
            cwd=str(self.ws),
            env=self.env(BASH_ENV=""),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=60,
        )


@pytest.fixture
def box(tmp_path: Path) -> Box:
    home = tmp_path / "home"
    home.mkdir()
    shim = tmp_path / "bin" / "guard"
    shim.parent.mkdir()
    shim.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{GUARD}" "$@"\n')
    shim.chmod(0o755)
    b = Box(tmp_path, home, tmp_path / "ws", tmp_path / "remote.git", tmp_path / "scratch", shim)
    b.git("init", "-q", "--bare", str(b.remote), cwd=tmp_path)
    b.git("init", "-q", "-b", "main", str(b.ws), cwd=tmp_path)
    write(b.ws / "src" / "app.py", "print('hi')\n")
    write(b.ws / "README.md", "readme\n")
    write(b.ws / ".gitignore", "build/\n")
    b.git("add", "-A")
    b.git("commit", "-qm", "base")
    b.git("remote", "add", "origin", str(b.remote))
    b.git("push", "-q", "origin", "main")
    return b


def guard_lines(r: subprocess.CompletedProcess[str]) -> list[str]:
    return [x for x in r.stderr.splitlines() if x.startswith("timelike: ") and "not persistent" not in x]


# ── rm (FR-42, FR-45) ──────────────────────────────────────────────────────────────────────────


def test_a_recursive_delete_takes_a_snapshot_named_in_its_line_and_undo_restores_it(box: Box) -> None:
    write(box.ws / "build" / "out.bin", os.urandom(500))
    write(box.ws / "src" / "extra.txt", "untracked\n")
    before = tree(box.ws)
    r = box.sh("rm -rf src build")
    assert r.returncode == 0, r.stderr
    assert not (box.ws / "src").exists() and not (box.ws / "build").exists()
    recs = box.records()
    assert len(recs) == 1 and recs[0]["reason"] == "before rm -rf src build"
    lines = guard_lines(r)
    assert lines[0] == (
        f"timelike: snapshot 1 of {os.path.realpath(box.ws)} taken before rm -rf src build:"
        " undo 1 --yes puts the workspace back"
    )
    assert lines[1].startswith("timelike: trash item 1 keeps 3 files (")
    u = box.undo("--yes", "--text")  # the newest the agent did not take as an undo's safety copy
    assert u.returncode == 0, u.stdout
    assert tree(box.ws) == before


def test_rm_keeps_its_own_output_and_exit_code(box: Box) -> None:
    plain = subprocess.run(
        ["rm", "missing.txt"], cwd=box.ws, capture_output=True, text=True, env={"LC_ALL": "C.UTF-8"}
    )
    r = box.sh("rm missing.txt")
    assert r.returncode == plain.returncode == 1
    assert r.stderr == plain.stderr  # nothing there: the guard says nothing, rm says its own
    r = box.sh("rm -rf missing-dir; echo rc=$?")
    assert r.stdout == "rc=0\n" and box.records() == []


def test_a_single_file_delete_goes_to_the_trash_without_a_snapshot(box: Box) -> None:
    write(box.ws / "notes.txt", "keep me\n", 0o640)
    before = tree(box.ws)
    r = box.sh("rm notes.txt")
    assert r.returncode == 0 and not (box.ws / "notes.txt").exists()
    assert box.records() == []  # not recursive: the trash, not a snapshot (criterion 1 names rm -r)
    assert guard_lines(r) == [
        "timelike: trash item 1 keeps 1 files (8 B): undo --trash 1 --yes puts them back"
    ]
    assert box.undo("--trash", "1", "--yes", "--text").returncode == 0
    assert tree(box.ws) == before


def test_rm_without_r_on_a_directory_keeps_nothing_and_rm_fails_as_itself(box: Box) -> None:
    r = box.sh("rm src")
    assert r.returncode == 1 and "Is a directory" in r.stderr
    assert box.records() == [] and not (box.state / "trash" / "items").exists()


def test_an_option_the_guard_cannot_read_is_treated_as_recursive(box: Box) -> None:
    r = box.sh("rm --rec --force src")  # GNU rm takes the abbreviation; the guard does not parse it
    assert r.returncode == 0 and not (box.ws / "src").exists()
    assert [x["reason"] for x in box.records()] == ["before rm --rec --force src"]


def test_a_path_in_no_workspace_is_kept_in_the_trash_and_the_line_says_no_snapshot(box: Box) -> None:
    other = box.tmp / "loose"
    write(other / "a.txt", "a\n")
    r = box.sh(f"rm -r {other}", cwd=box.ws)
    assert r.returncode == 0 and not other.exists()
    assert box.records() == []
    lines = guard_lines(r)
    assert lines[0].startswith("timelike: no snapshot before rm -r ")  # the command, cut at 60 characters
    assert lines[0].endswith(f": {other} is in no workspace (the trash keeps it)")
    assert lines[1].startswith("timelike: trash item 1 keeps 1 files")


def test_errexit_in_the_callers_shell_never_stops_the_real_rm(box: Box) -> None:
    write(box.ws / "x" / "f", "f\n")
    r = box.sh("set -e; rm -rf x; echo after", TIMELIKE_GUARD=str(box.tmp / "absent-guard"))
    assert r.returncode == 0 and r.stdout == "after\n" and not (box.ws / "x").exists()
    assert f"timelike: not guarded: {box.tmp / 'absent-guard'} is missing: no snapshot, no trash" in r.stderr


def test_type_a_shows_the_function_first_then_the_binary_and_command_rm_escapes(box: Box) -> None:
    r = box.sh("type -a rm; type -a git")
    out = r.stdout.splitlines()
    assert out[0] == "rm is a function" and out[out.index("git is a function") - 1].startswith("rm is /")
    assert any(x.startswith("git is /") for x in out[out.index("git is a function") :])
    write(box.ws / "y" / "f", "f\n")
    r = box.sh("command rm -r y")
    assert r.returncode == 0 and box.records() == [] and guard_lines(r) == []


# ── git (FR-43, FR-44, FR-45) ──────────────────────────────────────────────────────────────────


def test_a_hard_reset_with_uncommitted_changes_takes_a_snapshot_and_git_keeps_its_output(box: Box) -> None:
    (box.ws / "README.md").write_text("changed, not committed\n")
    before = tree(box.ws)
    r = box.sh("git reset --hard")
    assert r.returncode == 0 and r.stdout.startswith("HEAD is now at ")
    assert (box.ws / "README.md").read_text() == "readme\n"
    assert [x["reason"] for x in box.records()] == ["before git reset --hard"]
    assert guard_lines(r)[0].startswith("timelike: snapshot 1 of ")
    assert box.undo("1", "--yes", "--text").returncode == 0
    assert tree(box.ws) == before


def test_a_hard_reset_with_nothing_uncommitted_takes_none(box: Box) -> None:
    r = box.sh("git reset --hard")
    assert r.returncode == 0 and box.records() == [] and guard_lines(r) == []


def test_git_clean_takes_a_snapshot_and_keeps_every_file_it_deletes_in_the_trash(box: Box) -> None:
    write(box.ws / "build" / "out.o", "obj\n")  # ignored
    write(box.ws / "scratch.txt", "untracked\n")
    write(box.ws / "tmp dir" / "weïrd name.txt", "w\n")
    before = tree(box.ws)
    r = box.sh("git clean -fdx")
    assert r.returncode == 0 and "Removing scratch.txt" in r.stdout
    assert not (box.ws / "build").exists() and not (box.ws / "scratch.txt").exists()
    assert [x["reason"] for x in box.records()] == ["before git clean -fdx"]
    item = box.trash_items()[0]
    assert item["files"] == 3 and item["command"] == ["git", "clean", "-fdx"]
    assert box.undo("--trash", "1", "--yes", "--text").returncode == 0
    assert tree(box.ws) == before


def test_a_dry_run_clean_and_an_unforced_one_take_nothing(box: Box) -> None:
    write(box.ws / "scratch.txt", "untracked\n")
    assert guard_lines(box.sh("git clean -n")) == []
    r = box.sh("git clean -d")  # clean.requireForce: git refuses, deletes nothing
    assert r.returncode != 0 and (box.ws / "scratch.txt").exists()
    assert box.records() == [] and not (box.state / "trash" / "items").exists()


def test_status_and_log_run_with_no_helper(box: Box) -> None:
    r = box.sh("git status --short; git log --oneline | wc -l", TIMELIKE_GUARD=str(box.tmp / "absent"))
    assert r.returncode == 0 and "not guarded" not in r.stderr and r.stdout.strip().endswith("1")


def _diverge(box: Box) -> tuple[str, str]:
    """main on the remote at A; locally amended to B, which is not a fast-forward of A."""
    prior = box.git("rev-parse", "HEAD")
    (box.ws / "README.md").write_text("rewritten\n")
    box.git("commit", "-qam", "rewrite", "--amend")
    return prior, box.git("rev-parse", "HEAD")


def test_a_force_push_takes_exactly_one_snapshot_recording_the_remotes_prior_commit(box: Box) -> None:
    prior, new = _diverge(box)
    r = box.sh("git push --force -q origin main")
    assert r.returncode == 0, r.stderr
    assert box.git("rev-parse", "main", cwd=box.remote) == new
    recs = box.records()
    assert len(recs) == 1  # the pre-push step's; the git function leaves a push without --no-verify alone
    assert recs[0]["push"] == [
        {
            "remote": "origin",
            "ref": "refs/heads/main",
            "prior": prior,
            "source": "the remote, as git read it for this push",
            "deleted": False,
            "local_ref": "refs/heads/main",
        }
    ]
    put_back = f"git push --force origin {prior}:refs/heads/main"
    line = f"timelike: forced push: origin refs/heads/main was {prior}; put it back with: {put_back}"
    assert line in r.stderr
    assert box.sh(put_back).returncode == 0
    assert box.git("rev-parse", "main", cwd=box.remote) == prior


def test_a_fast_forward_push_takes_none(box: Box) -> None:
    write(box.ws / "more.txt", "m\n")
    box.git("add", "more.txt")
    box.git("commit", "-qm", "more")
    r = box.sh("git push -q origin main")
    assert r.returncode == 0 and box.records() == [] and guard_lines(r) == []


def test_a_force_push_with_no_verify_is_recorded_by_the_function_from_the_tracking_ref(box: Box) -> None:
    box.git("fetch", "-q", "origin")
    prior, new = _diverge(box)
    r = box.sh("git push --no-verify --force -q origin main")
    assert r.returncode == 0 and box.git("rev-parse", "main", cwd=box.remote) == new
    recs = box.records()
    assert len(recs) == 1 and recs[0]["reason"] == "before git push --no-verify --force -q origin main"
    assert recs[0]["push"][0]["prior"] == prior
    assert recs[0]["push"][0]["source"].startswith("refs/remotes/origin/main, read before the push")
    assert (
        f"timelike: forced push: origin refs/heads/main was {prior} (from the remote-tracking ref, which may"
        f" be stale); put it back with: git push --force origin {prior}:refs/heads/main"
    ) in r.stderr


def test_the_repositorys_own_pre_push_hook_still_reads_gits_lines_after_the_step(box: Box) -> None:
    hook = box.ws / ".git" / "hooks" / "pre-push"
    hook.write_text('#!/bin/sh\nn=0; while read -r l; do n=$((n+1)); done; echo "lines=$n" >&2; exit 1\n')
    hook.chmod(0o755)
    _diverge(box)
    r = box.sh("git push --force -q origin main")
    assert r.returncode != 0 and "lines=1" in r.stderr  # the hook rejected it, with git's input intact
    assert len(box.records()) == 1  # recorded before the hook ran; the step never decides the push


def test_the_pre_push_step_never_fails_a_push(box: Box) -> None:
    _diverge(box)
    write(box.tmp / "not-a-dir", "x\n")  # a state root that cannot be created: no snapshot, still pushed
    r = box.sh("git push --force -q origin main", TIMELIKE_STATE_ROOT=str(box.tmp / "not-a-dir" / "x"))
    assert r.returncode == 0
    assert "timelike: no snapshot of " in r.stderr
    assert "timelike: forced push: origin refs/heads/main was " in r.stderr


# ── the depth bound (Item 22's ruling) ──────────────────────────────────────────────────────────


def test_a_script_the_agents_shell_starts_is_not_guarded_and_keeps_its_exit_code(box: Box) -> None:
    write(box.ws / "gen" / "f", "f\n")
    write(box.ws / "clean.sh", "rm -r gen\nexit 7\n")
    r = box.sh("bash clean.sh")
    assert r.returncode == 7 and not (box.ws / "gen").exists()
    assert box.records() == [] and guard_lines(r) == []


def test_a_bash_c_started_inside_the_agents_shell_is_not_guarded(box: Box) -> None:
    write(box.ws / "gen" / "f", "f\n")
    r = box.sh("bash -c 'type -t rm; rm -r gen'")
    assert r.stdout.strip() == "file" and box.records() == [] and not (box.ws / "gen").exists()


def test_a_bash_the_agents_shell_execs_in_its_place_is_not_guarded_either(box: Box) -> None:
    write(box.ws / "gen" / "f", "f\n")
    r = box.sh("bash -c 'type -t rm'")  # a lone simple command: bash execs it, keeping the pid
    assert r.stdout.strip() == "file" and box.records() == []


def test_the_bash_lc_double_source_keeps_the_guards(box: Box) -> None:
    r = box.sh(f". {HOOK}; type -t rm; . {HOOK}; type -t git")
    assert r.stdout.split() == ["function", "function"]


def test_a_marker_naming_a_shell_that_is_not_an_ancestor_does_not_stop_the_guards(box: Box) -> None:
    write(box.ws / "gen" / "f", "f\n")
    r = box.sh("type -t rm; rm -r gen", TIMELIKE_GUARD_SHELL="999999999")
    assert r.stdout.strip() == "function" and len(box.records()) == 1


def test_an_interactive_shell_is_guarded_and_a_harness_started_from_it_is_too(box: Box) -> None:
    r = subprocess.run(
        ["bash", "--norc", "-i", "-c", f". {HOOK}; type -t rm; bash -c 'type -t rm'"],
        cwd=str(box.ws),
        env=box.env(BASH_ENV=str(HOOK)),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=30,
        start_new_session=True,
    )
    assert r.stdout.split() == ["function", "function"], r.stderr


# ── where the helper comes from (P002) and the restore's re-hash (note 12) ───────────────────────


def test_a_decoy_snapshot_on_path_is_never_what_the_guard_runs(box: Box) -> None:
    decoy = box.tmp / "decoy"
    write(decoy / "snapshot", "#!/bin/sh\necho DECOY >&2\nexit 0\n", 0o755)
    write(box.ws / "gen" / "f", "f\n")
    r = box.sh("rm -r gen", PATH=f"{decoy}:{os.environ.get('PATH', '/usr/bin:/bin')}")
    assert "DECOY" not in r.stderr and len(box.records()) == 1


def test_a_trash_object_that_rotted_is_refused_before_anything_is_put_back(box: Box) -> None:
    write(box.ws / "a.txt", "content a\n")
    box.sh("rm a.txt")
    item = box.trash_items()[0]
    sha = item["entries"][0]["sha256"]
    obj = box.state / "trash" / "objects" / sha[:2] / sha
    obj.chmod(0o600)
    obj.write_text("content X\n")
    u = box.undo("--trash", "1", "--yes", "--text")
    assert u.returncode == 1 and not (box.ws / "a.txt").exists()
    want = f"put back of trash item 1 refused: object {sha[:12]} (for {box.ws / 'a.txt'}) does not match"
    assert want in u.stdout
