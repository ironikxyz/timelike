"""The agent runtimes (feature 007, slice 1, cycle 4; spec FR-25 to FR-30, D-12 to D-15, FR-13 revised).

Written from the spec before the Dockerfiles change. These are static checks over the build files: the
pins, the checksum step, the interpreter's own configuration (pip.conf, the EXTERNALLY-MANAGED marker),
Node's npmrc, the seven links on PATH, the ENV block's PATH and the login-shell profile, and the bench
parity of the vanilla image. What the built images do is the e2e cells' (FR-31); nothing here builds one.

Every check reads text with regular expressions over logical instructions (continuation lines joined),
so a reformatted Dockerfile still passes and a missing step still fails. Comment lines are ignored where
a comment could state an absence ("no pip.conf") that a plain substring check would read as presence.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest
from conftest import REPO

AGENT_DOCKERFILE = REPO / "image" / "Dockerfile"
VANILLA_DOCKERFILE = REPO / "bench" / "vanilla" / "Dockerfile"
DOCKERFILES = {"agent": AGENT_DOCKERFILE, "vanilla": VANILLA_DOCKERFILE}
PINS = REPO / "pins.env"
COMPOSE = REPO / "compose.yaml"
MAKEFILE = REPO / "Makefile"
PROFILE_PATH = REPO / "image" / "rootfs" / "etc" / "profile.d" / "00-timelike-path.sh"

RUNTIME_NAMES = ("python3", "python", "pip", "pip3", "node", "npm", "npx")
# Executables the prefixes also hold, which must not reach PATH (D-12).
NOT_LINKED = ("corepack", "idle3", "pydoc3", "python3-config")
AGENT_LOCAL_BIN = "/home/agent/.local/bin"
TIMELIKE_BIN = "/opt/timelike/bin"
NODE_URL = "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-x64.tar.gz"
NPM_URL = "https://registry.npmjs.org/npm/-/npm-${NPM_VERSION}.tgz"
# PIP_BREAK_SYSTEM_PACKAGES and the pip.conf / command-line spelling, in any case (FR-28).
BREAK_SYSTEM = re.compile(r"break[-_]system[-_]packages", re.IGNORECASE)
# Where it must never appear (FR-28: "anywhere"); directories are walked.
BREAK_SCAN_ROOTS = (REPO / "image", REPO / "bench", COMPOSE, MAKEFILE, PINS)
SKIP_DIRS = {"__pycache__", "out", ".git"}  # bench/out holds run outputs, git-ignored
# Debian trixie's /etc/profile PATH for a non-root uid (tests/host/test_env_layer.sh, R1).
TRIXIE_PROFILE_PATH = "/usr/local/bin:/usr/bin:/bin:/usr/local/games:/usr/games"


# --- helpers ---------------------------------------------------------------------------------------


def read(path: Path) -> str:
    assert path.is_file(), f"missing: {path.relative_to(REPO)}"
    return path.read_text(encoding="utf-8")


def instructions(path: Path) -> list[str]:
    """The Dockerfile's logical instructions: comment lines dropped, backslash continuations joined.

    Comment lines inside a continued RUN are dropped too, as the Dockerfile parser does.
    """
    out: list[str] = []
    current = ""
    for raw in read(path).splitlines():
        stripped = raw.strip()
        if stripped.startswith("#") or (not stripped and not current):
            continue
        if stripped.endswith("\\"):
            current += stripped[:-1].rstrip() + " "
            continue
        current += stripped
        if current.strip():
            out.append(current.strip())
        current = ""
    if current.strip():
        out.append(current.strip())
    return out


def code_text(path: Path) -> str:
    """The Dockerfile without its comments, one logical instruction per line."""
    return "\n".join(instructions(path))


def segments(instruction: str) -> list[str]:
    """Shell commands of one instruction, split on &&, ||, ; and newlines (good enough for a scan)."""
    out = []
    for s in re.split(r"&&|\|\||;|\n", instruction):
        s = re.sub(r"^(?:(?:RUN|do|then|else)\s+|[{(]\s*)+", "", s.strip())
        if s:
            out.append(s)
    return out


def final_stage(path: Path) -> list[str]:
    """The instructions after the last FROM: what the shipped image is built from."""
    ins = instructions(path)
    froms = [i for i, line in enumerate(ins) if re.match(r"FROM\s", line, re.IGNORECASE)]
    assert froms, f"{path.relative_to(REPO)} has no FROM"
    return ins[froms[-1] :]


def link_segments(path: Path) -> list[str]:
    """Shell segments of every instruction that makes links into /usr/local/bin (D-12)."""
    out: list[str] = []
    for ins in instructions(path):
        if re.search(r"\bln\s+-[a-zA-Z]*s", ins) and "/usr/local/bin" in ins:
            out.extend(segments(ins))
    return out


def names_in(segment_list: list[str], name: str) -> bool:
    """Whether `name` appears as a link name: a whole word in a loop list, or the last path component
    after a `bin/` directory. `python` inside `/opt/agent/python/bin` does not count."""
    pat = re.compile(r"(?:(?<=[\s\"'])|(?<=bin/)|^)" + re.escape(name) + r"(?=[\s\"';]|$)")
    return any(pat.search(s) for s in segment_list)


def env_block(path: Path) -> dict[str, str]:
    """Parse the single ENV instruction the way tests/host/test_env_layer.sh does: one instruction,
    KEY="VALUE" per line, backslash continuations, no `$`, backslash or quote inside a value."""
    lines = read(path).splitlines()
    starts = [i for i, line in enumerate(lines) if re.match(r"ENV\s", line)]
    assert len(starts) == 1, f"expected exactly one ENV instruction in image/Dockerfile, found {len(starts)}"
    out: dict[str, str] = {}
    i = starts[0]
    first = True
    while i < len(lines):
        line = lines[i]
        if first:
            line = line[len("ENV") :]
            first = False
        cont = bool(re.search(r"\\\s*$", line))
        if cont:
            line = re.sub(r"\\\s*$", "", line)
        line = line.strip()
        if line:
            m = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)=(.*)", line)
            assert m, f"ENV line not KEY=VALUE: {line!r}"
            key, val = m.group(1), m.group(2)
            q = re.fullmatch(r'"(.*)"', val)
            if q:
                val = q.group(1)
            assert not re.search(r"[$\\'\"]", val), (
                f"ENV value for {key} uses $, a backslash or a quote; the ENV block takes none (D-13)"
            )
            out[key] = val
        if not cont:
            break
        i += 1
    assert out, "the ENV instruction parsed to zero variables"
    return out


def make_recipe_command(target: str, needle: str) -> str:
    """The logical recipe line of Makefile `target` that contains `needle` (continuations joined)."""
    text = read(MAKEFILE)
    m = re.search(rf"^{re.escape(target)}:.*\n((?:\t.*\n?)+)", text, re.MULTILINE)
    assert m, f"Makefile has no recipe for {target}"
    joined = re.sub(r"\\\n\s*", " ", m.group(1))
    hits = [line for line in joined.splitlines() if needle in line]
    assert len(hits) == 1, f"expected one {target} command containing {needle!r}, found {len(hits)}"
    return hits[0]


def pins() -> dict[str, str]:
    out: dict[str, str] = {}
    for line in read(PINS).splitlines():
        m = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)=(.*)", line.strip())
        if m:
            out[m.group(1)] = m.group(2)
    return out


# --- pins.env (FR-25) ------------------------------------------------------------------------------


def test_pins_carry_node_version() -> None:
    p = pins()
    assert "NODE_VERSION" in p, "pins.env has no NODE_VERSION (FR-25)"
    assert re.fullmatch(r"\d+\.\d+\.\d+", p["NODE_VERSION"]), (
        f"NODE_VERSION {p['NODE_VERSION']!r} is not an exact x.y.z version"
    )


def test_pins_carry_node_sha256() -> None:
    p = pins()
    assert "NODE_SHA256" in p, "pins.env has no NODE_SHA256 (FR-25)"
    assert re.fullmatch(r"[0-9a-f]{64}", p["NODE_SHA256"]), (
        f"NODE_SHA256 is not 64 lowercase hex characters: {p['NODE_SHA256']!r}"
    )


def test_pins_carry_npm_version_and_sha512() -> None:
    """Lane 007s1-a, item 3: npm itself is pinned, by version and the registry's sha512 (as hex)."""
    p = pins()
    assert re.fullmatch(r"\d+\.\d+\.\d+", p.get("NPM_VERSION", "")), (
        f"NPM_VERSION {p.get('NPM_VERSION')!r} is not an exact x.y.z version"
    )
    assert re.fullmatch(r"[0-9a-f]{128}", p.get("NPM_SHA512", "")), (
        f"NPM_SHA512 is not 128 lowercase hex characters: {p.get('NPM_SHA512')!r}"
    )


# --- both Dockerfiles: the same runtimes from the same pins (FR-25, FR-30, D-14, D-15) --------------


@pytest.mark.parametrize("which", sorted(DOCKERFILES))
@pytest.mark.parametrize(
    "arg", ["NODE_VERSION", "NODE_SHA256", "NPM_VERSION", "NPM_SHA512", "PYTHON_VERSION", "UV_IMAGE"]
)
def test_dockerfile_declares_runtime_build_arg(which: str, arg: str) -> None:
    code = code_text(DOCKERFILES[which])
    assert re.search(rf"^ARG\s+{arg}\b", code, re.MULTILINE), (
        f"{which} Dockerfile declares no ARG {arg}: the pin must arrive as a build argument"
    )


@pytest.mark.parametrize("which", sorted(DOCKERFILES))
def test_dockerfile_fetches_the_pinned_node_tarball(which: str) -> None:
    code = code_text(DOCKERFILES[which])
    assert NODE_URL in code, f"{which} Dockerfile does not fetch {NODE_URL} (FR-25, D-14: .tar.gz)"


@pytest.mark.parametrize("which", sorted(DOCKERFILES))
def test_dockerfile_checks_node_with_sha256sum_c(which: str) -> None:
    hits = [
        ins
        for ins in instructions(DOCKERFILES[which])
        if re.match(r"RUN\s", ins) and re.search(r"sha256sum\s+(?:-[a-z]*\s+)*-c\b|sha256sum\s+--check", ins)
    ]
    assert hits, f"{which} Dockerfile has no RUN with `sha256sum -c` (D-14)"
    assert any("NODE_SHA256" in ins for ins in hits), (
        f"{which} Dockerfile's `sha256sum -c` is not fed NODE_SHA256 (FR-25)"
    )


@pytest.mark.parametrize("which", sorted(DOCKERFILES))
def test_dockerfile_replaces_npm_whole_from_the_pinned_checked_tarball(which: str) -> None:
    """Lane 007s1-a, item 3: the registry's npm package, checked with `sha512sum -c` against NPM_SHA512,
    replaces Node's bundled npm directory whole, and the build checks the version it got."""
    code = code_text(DOCKERFILES[which])
    assert NPM_URL in code, f"{which} Dockerfile does not fetch {NPM_URL}"
    runs = [ins for ins in instructions(DOCKERFILES[which]) if re.match(r"RUN\s", ins)]
    hits = [ins for ins in runs if re.search(r"sha512sum\s+(?:-[a-z]*\s+)*-c\b", ins) and "NPM_SHA512" in ins]
    assert hits, f"{which} Dockerfile's `sha512sum -c` is not fed NPM_SHA512"
    (run,) = hits
    npm_dir = "/opt/agent/node/lib/node_modules/npm"
    check, remove = run.index("sha512sum"), run.index(f"rm -rf {npm_dir}")
    unpack = run.index(f"-C {npm_dir} --strip-components=1")
    assert check < remove < unpack, f"{which}: npm must be checked, then its old tree removed, then unpacked"
    assert '--version)" = "${NPM_VERSION}"' in run, f"{which}: the build does not check npm's version"


@pytest.mark.parametrize("which", sorted(DOCKERFILES))
def test_dockerfile_copies_opt_agent_into_the_final_stage(which: str) -> None:
    stage = final_stage(DOCKERFILES[which])
    hits = [ins for ins in stage if re.match(r"COPY\s", ins) and "--from=" in ins and "/opt/agent" in ins]
    assert hits, f"{which} Dockerfile's final stage does not COPY --from=<stage> /opt/agent (D-15)"


@pytest.mark.parametrize("which", sorted(DOCKERFILES))
def test_dockerfile_installs_agent_python_with_uv_in_a_build_stage(which: str) -> None:
    ins = instructions(DOCKERFILES[which])
    hits = [i for i in ins if re.search(r"\buv\s+python\s+install\b", i) and "/opt/agent" in i]
    assert hits, f"{which} Dockerfile has no `uv python install` into /opt/agent (FR-25, D-15)"
    stage = final_stage(DOCKERFILES[which])
    assert not any(i in stage for i in hits), (
        f"{which} Dockerfile installs the agent interpreter in its final stage; D-15 puts it in a build stage"
    )


def test_vanilla_final_stage_has_no_uv() -> None:
    stage = final_stage(VANILLA_DOCKERFILE)
    bad = [i for i in stage if re.search(r"(?:^|[\s/])uvx?(?:\s|$)", i) or "/bin/uv" in i]
    assert not bad, f"the vanilla image must not gain uv (D-15, stock behaviour): {bad}"


@pytest.mark.parametrize("which", sorted(DOCKERFILES))
@pytest.mark.parametrize("name", RUNTIME_NAMES)
def test_dockerfile_links_runtime_name_into_usr_local_bin(which: str, name: str) -> None:
    segs = link_segments(DOCKERFILES[which])
    assert segs, f"{which} Dockerfile makes no `ln -s` into /usr/local/bin (FR-25, D-12)"
    assert names_in(segs, name), f"{which} Dockerfile does not link {name} into /usr/local/bin (FR-25)"


@pytest.mark.parametrize("which", sorted(DOCKERFILES))
@pytest.mark.parametrize("name", NOT_LINKED)
def test_dockerfile_does_not_link_other_prefix_executables(which: str, name: str) -> None:
    segs = [s for s in link_segments(DOCKERFILES[which]) if re.match(r"(?:ln|for)\s", s)]
    assert not any(name in s for s in segs), (
        f"{which} Dockerfile links {name}; only the seven runtime names go on PATH (D-12)"
    )


@pytest.mark.parametrize("which", sorted(DOCKERFILES))
def test_links_point_into_the_agent_prefixes(which: str) -> None:
    """No wrapper (FR-28): the links are to the runtimes' own executables under /opt/agent."""
    lns = [s for s in link_segments(DOCKERFILES[which]) if re.match(r"ln\s", s)]
    assert lns, f"{which} Dockerfile has no ln command"
    bad = [s for s in lns if "/opt/agent" not in s and "$" not in s]
    assert not bad, f"{which} Dockerfile links to something outside /opt/agent: {bad}"
    assert any("/opt/agent/python" in s for s in link_segments(DOCKERFILES[which])), (
        f"{which} Dockerfile links nothing from /opt/agent/python"
    )
    assert any("/opt/agent/node" in s for s in link_segments(DOCKERFILES[which])), (
        f"{which} Dockerfile links nothing from /opt/agent/node"
    )


# --- agent image only: the interpreter's and Node's own configuration (FR-26, FR-27) ---------------


def marker_removals(path: Path) -> list[str]:
    """Shell segments that delete an EXTERNALLY-MANAGED marker: an `rm` or `find -delete` naming it, or an
    `rm` of a variable that the same instruction assigned from a command naming it."""
    out: list[str] = []
    for ins in instructions(path):
        if "EXTERNALLY-MANAGED" not in ins:
            continue
        segs = segments(ins)
        held = {
            m.group(1): seg
            for seg in segs
            if "EXTERNALLY-MANAGED" in seg and (m := re.match(r"([A-Za-z_][A-Za-z0-9_]*)=", seg))
        }
        for seg in segs:
            if "EXTERNALLY-MANAGED" in seg and (re.match(r"rm\s", seg) or "-delete" in seg):
                out.append(seg)
            elif re.match(r"rm\s", seg):
                for var, source in held.items():
                    if re.search(r"\$\{?" + var + r"\b", seg):
                        out.append(f"{source} -> {seg}")
    return out


def removes_marker(path: Path) -> bool:
    return bool(marker_removals(path))


def copied_source(path: Path, dest_suffix: str) -> str | None:
    """Text of a repository file COPYd to a destination ending in dest_suffix, if any."""
    for ins in instructions(path):
        if not re.match(r"COPY\s", ins) or "--from=" in ins:
            continue
        words = [w for w in ins.split()[1:] if not w.startswith("--")]
        if len(words) >= 2 and words[-1].endswith(dest_suffix):
            src = REPO / words[0]
            if src.is_file():
                return src.read_text(encoding="utf-8")
    return None


def test_agent_removes_externally_managed_marker() -> None:
    assert removes_marker(AGENT_DOCKERFILE), (
        "the agent Dockerfile does not remove the agent prefix's EXTERNALLY-MANAGED marker (FR-26, Q3)"
    )


def test_agent_marker_removal_is_in_the_agent_prefix_only() -> None:
    removals = marker_removals(AGENT_DOCKERFILE)
    bad = [r for r in removals if "/opt/timelike" in r or "/opt/agent" not in r]
    assert not bad, f"a marker removal outside the agent prefix (FR-26, FR-29): {bad}"


def test_agent_writes_pip_conf_user_true() -> None:
    code = code_text(AGENT_DOCKERFILE)
    assert "/opt/agent/python/pip.conf" in code, (
        "the agent Dockerfile does not write /opt/agent/python/pip.conf (FR-26)"
    )
    body = copied_source(AGENT_DOCKERFILE, "/opt/agent/python/pip.conf") or code
    assert re.search(r"\[install\]", body), "pip.conf has no [install] section (FR-26)"
    assert re.search(r"(?m)(?:^|\\n|['\"\s])user\s*=\s*true\b", body), "pip.conf does not set user = true"


def test_agent_writes_npmrc_with_home_local_prefix() -> None:
    code = code_text(AGENT_DOCKERFILE)
    assert "/opt/agent/node/etc/npmrc" in code, (
        "the agent Dockerfile does not write /opt/agent/node/etc/npmrc (FR-27)"
    )
    copied = copied_source(AGENT_DOCKERFILE, "/opt/agent/node/etc/npmrc")
    if copied is not None:
        assert re.search(r"(?m)^prefix\s*=\s*\$\{HOME\}/\.local\s*$", copied), (
            "the copied npmrc does not set prefix=${HOME}/.local"
        )
        return
    lines = [ins for ins in instructions(AGENT_DOCKERFILE) if "prefix=" in ins and "npmrc" in ins]
    assert lines, "no instruction writes prefix= into the npmrc (FR-27)"
    good = False
    for ins in lines:
        for m in re.finditer(r"prefix\s*=\s*(\\?)\$\{HOME\}/\.local", ins):
            escaped = m.group(1) == "\\"
            before = ins[: m.start()]
            last_quote = max(before.rfind("'"), before.rfind('"'))
            single = last_quote >= 0 and before[last_quote] == "'"
            if escaped or single:
                good = True
    assert good, (
        "the npmrc's prefix is not the literal ${HOME}/.local: it must be single-quoted or escaped, "
        "or the build's own shell expands it to root's home (FR-27, D-13)"
    )


# --- vanilla image only: stock behaviour (FR-13 revised) -------------------------------------------


def test_vanilla_keeps_externally_managed_marker() -> None:
    assert not removes_marker(VANILLA_DOCKERFILE), (
        "the vanilla Dockerfile removes EXTERNALLY-MANAGED; vanilla keeps stock behaviour (FR-13 revised)"
    )


@pytest.mark.parametrize("needle", ["pip.conf", "npmrc", ".local/bin", "/opt/timelike"])
def test_vanilla_carries_none_of_timelikes_runtime_configuration(needle: str) -> None:
    code = code_text(VANILLA_DOCKERFILE)
    assert needle not in code, f"the vanilla Dockerfile's instructions mention {needle!r} (FR-13 revised)"


def test_vanilla_has_no_env_path() -> None:
    code = code_text(VANILLA_DOCKERFILE)
    assert not re.search(r"^ENV\s", code, re.MULTILINE), (
        "the vanilla Dockerfile has an ENV instruction: no ~/.local/bin on PATH, no timelike layers"
    )


# --- never PIP_BREAK_SYSTEM_PACKAGES (FR-28) -------------------------------------------------------


def scanned_files() -> list[Path]:
    out: list[Path] = []
    for root in BREAK_SCAN_ROOTS:
        if root.is_file():
            out.append(root)
            continue
        assert root.is_dir(), f"missing: {root.relative_to(REPO)}"
        for p in sorted(root.rglob("*")):
            rel = p.relative_to(REPO).parts
            if any(part in SKIP_DIRS for part in rel) or not p.is_file() or p.is_symlink():
                continue
            out.append(p)
    return out


def test_no_break_system_packages_anywhere() -> None:
    """Not in any instruction, setting or code line (FR-28). Full-line comments are skipped."""
    files = scanned_files()
    assert files, "nothing was scanned"
    bad: list[str] = []
    for p in files:
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for n, line in enumerate(text.splitlines(), 1):
            # A comment saying "never" is not a use; every scanned file comments with `#`.
            if BREAK_SYSTEM.search(line) and not line.lstrip().startswith("#"):
                bad.append(f"{p.relative_to(REPO)}:{n}")
    assert not bad, f"PIP_BREAK_SYSTEM_PACKAGES / break-system-packages is forbidden (FR-28): {bad}"


def test_break_system_scan_can_fail() -> None:
    """The scan's pattern matches every spelling it is meant to forbid (cross-stack P004)."""
    for s in (
        "PIP_BREAK_SYSTEM_PACKAGES=1",
        "pip install --break-system-packages x",
        "break-system-packages = true",
    ):
        assert BREAK_SYSTEM.search(s), s


# --- ~/.local/bin on PATH (FR-28, D-13) ------------------------------------------------------------


def test_env_path_order() -> None:
    env = env_block(AGENT_DOCKERFILE)
    assert "PATH" in env, "the ENV block sets no PATH"
    parts = env["PATH"].split(":")
    assert parts[0] == TIMELIKE_BIN, f"PATH must start with {TIMELIKE_BIN}: {env['PATH']}"
    assert len(parts) > 1 and parts[1] == AGENT_LOCAL_BIN, (
        f"PATH's second entry must be {AGENT_LOCAL_BIN} (FR-28): {env['PATH']}"
    )
    assert "/usr/local/bin" in parts, f"PATH lost /usr/local/bin: {env['PATH']}"
    assert parts.index(AGENT_LOCAL_BIN) < parts.index("/usr/local/bin"), (
        f"{AGENT_LOCAL_BIN} must come before /usr/local/bin (FR-28): {env['PATH']}"
    )
    assert len(parts) == len(set(parts)), f"PATH repeats an entry: {env['PATH']}"


def test_profile_d_mentions_local_bin() -> None:
    assert AGENT_LOCAL_BIN in read(PROFILE_PATH), (
        f"00-timelike-path.sh does not name {AGENT_LOCAL_BIN} for login shells (FR-28)"
    )


def source_profile(path_value: str) -> str:
    r = subprocess.run(
        ["sh", "-c", '. "$1"; printf "%s" "$PATH"', "sh", str(PROFILE_PATH)],
        env={"PATH": path_value},
        capture_output=True,
        text=True,
        timeout=10,
        stdin=subprocess.DEVNULL,
        check=False,
    )
    assert r.returncode == 0, f"sourcing 00-timelike-path.sh failed: {r.stderr}"
    return r.stdout


def test_profile_d_restores_the_env_order_after_debians_reset() -> None:
    """After /etc/profile's reset, login shells get /opt/timelike/bin then ~/.local/bin, both before
    /usr/local/bin (FR-28)."""
    parts = source_profile(TRIXIE_PROFILE_PATH).split(":")
    assert parts[:2] == [TIMELIKE_BIN, AGENT_LOCAL_BIN], f"login-shell PATH order: {parts}"
    assert parts.index(AGENT_LOCAL_BIN) < parts.index("/usr/local/bin"), parts


def test_profile_d_is_idempotent_on_the_env_path() -> None:
    env_path = env_block(AGENT_DOCKERFILE)["PATH"]
    assert source_profile(env_path) == env_path, "sourcing the profile changed a PATH that was already right"


# --- compose and the Makefile pass the pins (FR-25, FR-30) -----------------------------------------


@pytest.mark.parametrize("arg", ["NODE_VERSION", "NODE_SHA256", "NPM_VERSION", "NPM_SHA512"])
def test_compose_agent_build_args(arg: str) -> None:
    text = read(COMPOSE)
    m = re.search(r"^  agent:\n((?:    .*\n|\s*\n)+)", text, re.MULTILINE)
    assert m, "compose.yaml has no agent service"
    block = m.group(1)
    a = re.search(r"^      args:\n((?:        .*\n)+)", block, re.MULTILINE)
    assert a, "compose.yaml's agent service has no build args"
    assert re.search(rf"^\s+{arg}:\s*\$\{{{arg}(?::-)?\}}\s*$", a.group(1), re.MULTILINE), (
        f"compose.yaml's agent build args do not pass {arg}: ${{{arg}:-}} (FR-25)"
    )


@pytest.mark.parametrize(
    "arg", ["UV_IMAGE", "PYTHON_VERSION", "NODE_VERSION", "NODE_SHA256", "NPM_VERSION", "NPM_SHA512"]
)
def test_makefile_vanilla_build_passes_runtime_pins(arg: str) -> None:
    cmd = make_recipe_command("bench-images", "bench/vanilla/Dockerfile")
    assert re.search(rf"--build-arg\s+{arg}=\$[({{]{arg}[)}}]", cmd), (
        f"bench-images builds the vanilla image without --build-arg {arg}=$({arg}) (FR-30)"
    )


def _runtimes_stage(text: str) -> str:
    start = text.index("FROM ${UV_IMAGE} AS uv")
    return text[start : text.index("\nFROM ${DEBIAN_IMAGE}\n", start)]


def test_the_two_runtimes_stages_are_identical() -> None:
    """D-15, RB1: both bench arms get their runtimes from byte-identical build steps (coordinator, T028)."""
    agent = _runtimes_stage(AGENT_DOCKERFILE.read_text())
    vanilla = _runtimes_stage(VANILLA_DOCKERFILE.read_text())
    assert "AS runtimes" in agent, "the agent Dockerfile has no `runtimes` stage"
    assert agent == vanilla, "bench/vanilla/Dockerfile's runtimes stage differs from image/Dockerfile's"
