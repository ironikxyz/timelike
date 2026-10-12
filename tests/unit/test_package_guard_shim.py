"""The install shims (feature 013 slice 1; FOR-MENTOR Item 24, Q1 (b')): image/rootfs/opt/timelike/libexec/
install-shim, linked as pip, pip3, uv, npm, npx and pnpm in a shims directory first on PATH.

The lab lays the image out in a temporary directory: shims/<name> → ../libexec/install-shim and bin/
package-guard (with run), so the shim finds the guard where the image puts it, beside its own directory. The
"real" installers are decoys that print their arguments, a variable and their stdin, so what reached them,
and how, is read from what they print, not from the shim (lore P004). One test runs the host's real pip.

Item 24's conditions, each tested here:
  1. pass-through is free: a command that cannot be an install reaches the real one with no guard call (no
     session event is written);
  2. the real command is untouched: found on PATH without the shims (a decoy alias of the shims directory
     and a second link are skipped, never run); its output, stdin, environment and exit are its own, and a
     BASH_ENV that would change the environment is not read;
  and a refusal is the guard's envelope, exit 4, with the decoy never run.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from conftest import REPO, TOOLS_DIR, base_env
from standin import CATALOG, Standin

SHIM = REPO / "image/rootfs/opt/timelike/libexec/install-shim"
NAMES = ("pip", "pip3", "uv", "npm", "npx", "pnpm")
SESSION = "shim"

DECOY = """#!/bin/sh
printf 'decoy %s ran: %s\\n' "${0##*/}" "$*"
printf 'FOO=%s\\n' "${FOO-unset}"
if [ -n "${READ_STDIN-}" ]; then printf 'stdin=%s\\n' "$(cat)"; fi
exit "${DECOY_EXIT:-0}"
"""


@dataclass
class Lab:
    root: Path
    shims: Path
    bin: Path
    real: Path
    ws: Path
    scratch: Path
    reg: Standin

    def env(self, **extra: str) -> dict[str, str]:
        e = base_env(self.scratch, SESSION, HOME=str(self.root / "home"), COLUMNS="1000")
        e.update(
            PATH=f"{self.shims}:{self.bin}:{self.real}:/usr/bin:/bin",
            TIMELIKE_BIN_DIRS=str(self.bin),
            TIMELIKE_SHIMS=str(self.shims),
            PIP_INDEX_URL=self.reg.simple,
            PIP_NO_CACHE_DIR="1",
            PIP_DISABLE_PIP_VERSION_CHECK="1",
            npm_config_registry=self.reg.npm,
        )
        e.update(extra)
        return e

    def sh(self, cmd: str, stdin: str | None = None, **extra: str) -> subprocess.CompletedProcess[str]:
        """CMD in sh -c, as a Makefile or subprocess would run it."""
        return subprocess.run(
            ["/bin/sh", "-c", cmd],
            cwd=self.ws,
            env=self.env(**extra),
            input=stdin,
            stdin=None if stdin is not None else subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=120,
            start_new_session=True,
        )

    def events(self) -> list[dict[str, object]]:
        p = self.scratch / SESSION / "events.jsonl"
        return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []


@pytest.fixture(scope="module")
def reg(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Standin]:
    with Standin(tmp_path_factory.mktemp("reg"), CATALOG) as s:
        yield s


@pytest.fixture
def lab(tmp_path: Path, reg: Standin) -> Lab:
    root = Path(os.path.realpath(tmp_path))
    libexec, shims, bin_, real, ws = (root / d for d in ("libexec", "shims", "bin", "real", "ws"))
    for d in (libexec, shims, bin_, real, ws, root / "home"):
        d.mkdir()
    shutil.copy(SHIM, libexec / "install-shim")
    (libexec / "install-shim").chmod(0o755)
    for name in NAMES:
        (shims / name).symlink_to("../libexec/install-shim")
    for name in ("package-guard", "run"):
        lines = (TOOLS_DIR / name).read_text().splitlines(keepends=True)
        (bin_ / name).write_text(f"#!{sys.executable}\n" + "".join(lines[1:]))
        (bin_ / name).chmod(0o755)
    for name in ("pip", "npm", "uv", "npx"):
        (real / name).write_text(DECOY)
        (real / name).chmod(0o755)
    reg.clear()
    return Lab(root, shims, bin_, real, ws, root / "scratch", reg)


def said(r: subprocess.CompletedProcess[str]) -> str:
    return f"exit {r.returncode}\nstdout:\n{r.stdout}\nstderr:\n{r.stderr}"


@pytest.mark.parametrize(
    "cmd",
    [
        "pip --version",
        "pip list",
        "pip3 --version",
        "npm run test",
        "npm --version",
        "uv venv",
        "uv lock",
        "npx --version",
    ],
)
def test_pass_through_reaches_the_real_command_with_no_guard_call(lab: Lab, cmd: str) -> None:
    (lab.real / "pip3").symlink_to("pip")
    r = lab.sh(cmd, DECOY_EXIT="7", FOO="kept")
    name, *args = cmd.split()
    assert r.returncode == 7, said(r)
    assert r.stdout == f"decoy {name} ran: {' '.join(args)}\nFOO=kept\n" and r.stderr == ""
    assert lab.events() == []  # the guard was not asked (Item 24, condition 1)


def test_the_real_command_keeps_its_environment_stdin_and_exit(lab: Lab) -> None:
    """A BASH_ENV that unsets FOO is not read (the shim is sh); stdin reaches the real command; its exit."""
    (lab.root / "bashenv").write_text("unset FOO\n")
    r = lab.sh("pip freeze", stdin="from-stdin", FOO="kept", READ_STDIN="1", DECOY_EXIT="3",
               BASH_ENV=str(lab.root / "bashenv"))  # fmt: skip
    assert r.returncode == 3, said(r)
    assert r.stdout == "decoy pip ran: freeze\nFOO=kept\nstdin=from-stdin\n"


def test_an_install_that_passes_is_the_installers_own_output_and_exit(lab: Lab) -> None:
    r = lab.sh("pip install tl-old", DECOY_EXIT="5")
    assert r.returncode == 5, said(r)
    # nothing of the guard's: its verdict is dropped on a pass
    assert r.stdout == "decoy pip ran: install tl-old\nFOO=unset\n" and r.stderr == ""
    (ev,) = lab.events()
    assert ev["tool"] == "package-guard" and ev["exit"] == 0
    assert ev["args"] == ["--gate", "--json", "--", "pip", "install", "tl-old"]


def test_an_install_that_passes_keeps_stdin_for_the_installer(lab: Lab) -> None:
    """The guard's question is asked with stdin closed, so the installer still reads what was piped."""
    r = lab.sh("pip install tl-old", stdin="for-pip", READ_STDIN="1")
    assert r.returncode == 0, said(r)
    assert r.stdout.endswith("stdin=for-pip\n")


@pytest.mark.parametrize(
    ("cmd", "confirm"),
    [
        ("pip install tl-surely-absent", "package-guard --yes -- pip install tl-surely-absent"),
        ("pip3 install tl-fresh", "package-guard --yes -- pip3 install tl-fresh"),
        ("npm install tl-fresh", "package-guard --yes -- npm install tl-fresh"),
        ("npm i tl-surely-absent", "package-guard --yes -- npm i tl-surely-absent"),
        ("npx tl-surely-absent", "package-guard --yes -- npx tl-surely-absent"),
        ("uv pip install tl-fresh", "package-guard --yes -- uv pip install tl-fresh"),
    ],
)
def test_a_refused_install_is_the_envelope_and_the_installer_never_runs(
    lab: Lab, cmd: str, confirm: str
) -> None:
    (lab.real / "pip3").symlink_to("pip")
    r = lab.sh(cmd, UV_DEFAULT_INDEX=lab.reg.simple)
    assert r.returncode == 4, said(r)
    env = json.loads(r.stdout)
    assert env["status"] == "confirmation_required" and env["confirm"] == confirm
    assert "decoy" not in r.stdout + r.stderr
    assert lab.reg.file_requests() == []


def test_on_a_terminal_a_refusal_is_still_the_envelope(lab: Lab) -> None:
    """The guard's output is captured, so the shim passes the caller's own choice (a terminal: --text); the
    refusal is the JSON envelope in every mode all the same (rule 9), exit 4."""
    script = lab.root / "on_a_terminal.py"
    script.write_text(
        "import os, pty, sys\n"
        "pid, fd = pty.fork()\n"
        "if pid == 0:\n"
        "    os.execvp('/bin/sh', ['/bin/sh', '-c', 'pip install tl-fresh'])\n"
        "out = b''\n"
        "while True:\n"
        "    try:\n"
        "        b = os.read(fd, 4096)\n"
        "    except OSError:\n"
        "        break\n"
        "    if not b:\n"
        "        break\n"
        "    out += b\n"
        "_, st = os.waitpid(pid, 0)\n"
        "sys.stdout.write(out.decode(errors='replace'))\n"
        "sys.exit(os.waitstatus_to_exitcode(st))\n"
    )
    r = subprocess.run(
        [sys.executable, "-I", str(script)], cwd=lab.ws, env=lab.env(), capture_output=True, text=True,
        timeout=120, stdin=subprocess.DEVNULL,
    )  # fmt: skip
    assert r.returncode == 4, said(r)
    env = json.loads(r.stdout.replace("\r\n", "\n"))
    assert env["status"] == "confirmation_required" and "decoy" not in r.stdout
    (ev,) = lab.events()
    assert ev["args"][:2] == ["--gate", "--text"]


def test_the_real_command_is_never_the_shim_itself(lab: Lab) -> None:
    """P002: an alias of the shims directory, and another link to the shim, earlier on PATH than the real pip,
    are skipped; nothing recurses."""
    alias = lab.root / "alias"
    alias.symlink_to(lab.shims)
    other = lab.root / "other"
    other.mkdir()
    (other / "pip").symlink_to(lab.shims / "pip")
    path = f"{lab.shims}:{alias}:{other}:{lab.bin}:{lab.real}:/usr/bin:/bin"
    r = lab.sh("pip --version", PATH=path)
    assert r.returncode == 0, said(r)
    assert r.stdout.startswith("decoy pip ran: --version")


def test_a_command_found_nowhere_else_is_not_found(lab: Lab) -> None:
    """pnpm is not installed: the shim answers as bash would without it, exit 127, and asks no guard."""
    r = lab.sh("pnpm add tl-old", BASH_ENV="", PATH=f"{lab.shims}:{lab.bin}:{lab.real}")  # no host pnpm
    assert r.returncode == 127, said(r)
    assert "pnpm: command not found" in r.stderr
    assert lab.events() == []


def test_a_command_found_nowhere_else_gets_the_handlers_answer(lab: Lab) -> None:
    """With the image's hook as BASH_ENV, bash's command-not-found handler answers (007): its own line and the
    data file's install hint for pnpm."""
    hook = REPO / "image/rootfs/etc/timelike/shell-env.bash"
    data = REPO / "image/rootfs/etc/timelike/missing-commands.tsv"
    r = lab.sh("pnpm add tl-old", BASH_ENV=str(hook), TIMELIKE_MISSING_COMMANDS=str(data),
               PATH=f"{lab.shims}:{lab.bin}:{lab.real}")  # fmt: skip
    assert r.returncode == 127, said(r)
    assert "pnpm: command not found" in r.stderr
    assert "npm install -g pnpm" in r.stdout + r.stderr


def test_a_missing_guard_fails_closed(lab: Lab) -> None:
    (lab.bin / "package-guard").unlink()
    r = lab.sh("pip install tl-old")
    assert r.returncode == 127, said(r)
    assert "the package guard is missing" in r.stderr and "decoy" not in r.stdout


@pytest.mark.skipif(shutil.which("pip", path="/usr/bin:/bin:/usr/local/bin") is None, reason="no host pip")
def test_the_hosts_real_pip_through_the_shim(lab: Lab) -> None:
    """The real installer, found after the shims: a passing install is pip's own output, a refused one never
    starts pip (no file request)."""
    for name in ("pip", "npm", "uv", "npx"):
        (lab.real / name).unlink()
    host = f"{lab.shims}:{lab.bin}:{os.environ.get('PATH', '/usr/bin:/bin')}"
    r = lab.sh("pip install --target t tl-old", PATH=host)
    assert r.returncode == 0, said(r)
    assert "Successfully installed tl-old-1.2.0" in r.stdout and '"tool"' not in r.stdout
    assert (lab.ws / "t" / "tl_old").is_dir()
    lab.reg.clear()
    r = lab.sh("pip install --target u tl-fresh", PATH=host)
    assert r.returncode == 4, said(r)
    assert lab.reg.file_requests() == [] and not (lab.ws / "u").exists()


def test_the_shim_lists_the_installers_the_guard_reads() -> None:
    """Every installer word the guard classifies is one the shim sends to it (a word the shim missed would be
    exec'd unchecked). Read from the guard's own sets, so the two cannot drift."""
    import pgmod

    pg = pgmod.load()
    text = SHIM.read_text()
    npm_words = pg.NPM_INSTALL | pg.NPM_INSTALL_TEST | pg.NPM_CI | pg.NPM_CI_TEST | pg.NPM_EXEC | pg.NPM_INIT
    for word in sorted(npm_words):
        assert f"npm:{word} " in text or f"npm:{word})" in text, word
    for word in ("add", "install", "i", "dlx", "create", "init"):
        assert f"pnpm:{word} " in text or f"pnpm:{word})" in text, word
    assert tuple(pg.SHIMMED) == NAMES
