"""package-guard's choice of registry: the one the installer would use (feature 013, T004; FR-10 to FR-13;
research R3).

Each test builds the configuration files in a temporary home and checks the order pip, uv and npm document.
The machine's own /etc files are not written; the host has none (research R3, `pip config debug`).
"""

from __future__ import annotations

import os
from pathlib import Path

from pgmod import PG


def pip_inst(cmd: str, cwd: Path, interpreter: str | None = None) -> object:
    inst = PG.classify(cmd.split(), cwd, {}, lambda _: None)
    if interpreter:
        inst.interpreter = interpreter
    return inst


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def test_pip_default_is_pypi(tmp_path: Path) -> None:
    idx, used = PG.pip_indexes(pip_inst("pip install x", tmp_path), {"HOME": str(tmp_path)})
    assert idx == ["https://pypi.org/simple"] and used == []


def test_pip_order_user_site_env_file_env_cli(tmp_path: Path) -> None:
    home = tmp_path / "home"
    venv = tmp_path / "venv"
    write(venv / "pyvenv.cfg", "home = /usr\n")
    write(venv / "bin" / "python", "")
    write(home / ".config" / "pip" / "pip.conf", "[global]\nindex-url = https://user.example/simple\n")
    env = {"HOME": str(home)}
    inst = pip_inst("pip install x", tmp_path, str(venv / "bin" / "python"))
    assert PG.pip_indexes(inst, env)[0] == ["https://user.example/simple"]
    # the site file (the venv's own pip.conf) beats the user's; [install] beats [global]
    write(
        venv / "pip.conf",
        "[global]\nindex-url = https://site.example/simple\n[install]\nindex-url = https://site-install.example/simple\n",
    )
    assert PG.pip_indexes(inst, env)[0] == ["https://site-install.example/simple"]
    # PIP_CONFIG_FILE beats the site file, and when it exists the user file is not read at all
    f = write(tmp_path / "custom.conf", "[global]\nextra-index-url = https://extra.example/simple\n")
    env2 = {**env, "PIP_CONFIG_FILE": str(f)}
    assert PG.pip_indexes(inst, env2)[0] == [
        "https://site-install.example/simple",
        "https://extra.example/simple",
    ]
    # the environment beats every file; the command line beats the environment
    env3 = {**env2, "PIP_INDEX_URL": "https://env.example/simple"}
    assert PG.pip_indexes(inst, env3)[0][0] == "https://env.example/simple"
    cli = pip_inst("pip install -i https://cli.example/simple x", tmp_path, str(venv / "bin" / "python"))
    assert PG.pip_indexes(cli, env3)[0][0] == "https://cli.example/simple"
    assert str(venv / "pip.conf") in PG.pip_indexes(inst, env)[1]


def test_pip_site_file_of_a_plain_interpreter(tmp_path: Path) -> None:
    prefix = tmp_path / "opt" / "python"
    write(prefix / "bin" / "python3", "")
    write(prefix / "pip.conf", "[install]\nindex-url = https://agent.example/simple\n")
    inst = pip_inst("pip install x", tmp_path, str(prefix / "bin" / "python3"))
    assert PG.pip_indexes(inst, {"HOME": str(tmp_path)})[0] == ["https://agent.example/simple"]


def test_pip_no_index_and_isolated(tmp_path: Path) -> None:
    env = {"HOME": str(tmp_path), "PIP_NO_INDEX": "1"}
    assert PG.pip_indexes(pip_inst("pip install x", tmp_path), env)[0] == []
    env = {"HOME": str(tmp_path), "PIP_INDEX_URL": "https://env.example/simple"}
    assert PG.pip_indexes(pip_inst("pip install --isolated x", tmp_path), env)[0] == [
        "https://pypi.org/simple"
    ]


def test_shebang_names_pips_interpreter(tmp_path: Path) -> None:
    pip = write(tmp_path / "bin" / "pip", "#!/opt/agent/python/bin/python3\nimport pip\n")
    assert PG._shebang_python(str(pip), lambda _: None) == "/opt/agent/python/bin/python3"
    # `#!/usr/bin/env NAME` is looked up with the guard's own resolver, the one that skips the shims
    envpip = write(tmp_path / "bin" / "pip3", "#!/usr/bin/env python3\nimport pip\n")
    assert PG._shebang_python(str(envpip), {"python3": "/real/python3"}.get) == "/real/python3"


def uv_inst(cmd: str, cwd: Path) -> object:
    return PG.classify(cmd.split(), cwd, {}, lambda _: None)


def test_uv_order(tmp_path: Path) -> None:
    env = {"HOME": str(tmp_path), "XDG_CONFIG_HOME": str(tmp_path / "xdg")}
    assert PG.uv_indexes(uv_inst("uv pip install x", tmp_path), env, tmp_path)[0] == [
        "https://pypi.org/simple"
    ]
    write(tmp_path / "pyproject.toml", '[project]\nname="p"\n[[tool.uv.index]]\nurl = "https://proj.example/simple"\n'
          '[[tool.uv.index]]\nurl = "https://default.example/simple"\ndefault = true\n')  # fmt: skip
    got = PG.uv_indexes(uv_inst("uv add x", tmp_path), env, tmp_path)[0]
    assert got == ["https://proj.example/simple", "https://default.example/simple"]
    env2 = {
        **env,
        "UV_INDEX": "named=https://envidx.example/simple",
        "UV_DEFAULT_INDEX": "https://envdef.example/simple",
    }
    got = PG.uv_indexes(uv_inst("uv add --index https://cli.example/simple x", tmp_path), env2, tmp_path)[0]
    assert got == ["https://cli.example/simple", "https://envidx.example/simple", "https://proj.example/simple",
                   "https://envdef.example/simple"]  # fmt: skip
    assert PG.uv_indexes(uv_inst("uv pip install --no-index x", tmp_path), env, tmp_path)[0] == []


def test_uv_user_config_file(tmp_path: Path) -> None:
    write(tmp_path / "xdg" / "uv" / "uv.toml", 'index-url = "https://uvtoml.example/simple"\n')
    env = {"HOME": str(tmp_path), "XDG_CONFIG_HOME": str(tmp_path / "xdg")}
    assert PG.uv_indexes(uv_inst("uv pip install x", tmp_path), env, tmp_path)[0] == [
        "https://uvtoml.example/simple"
    ]


def npm_world(tmp: Path) -> tuple[dict[str, str], object]:
    """A fake Node prefix with a global npmrc and an npm package holding a builtin npmrc, as the image lays
    it out."""
    node = write(tmp / "node" / "bin" / "node", "")
    npm_pkg = tmp / "node" / "lib" / "node_modules" / "npm"
    write(npm_pkg / "package.json", '{"name": "npm"}')
    cli = write(npm_pkg / "bin" / "npm-cli.js", "")
    link = tmp / "node" / "bin" / "npm"
    os.symlink(cli, link)
    write(npm_pkg / "npmrc", "registry=https://builtin.example/\n")
    paths = {"node": str(node), "npm": str(link)}
    return {"HOME": str(tmp / "home")}, (lambda name: paths.get(name))


def registry(cmd: str, cwd: Path, env: dict[str, str], resolve: object, scope: str | None = None) -> str:
    inst = PG.classify(cmd.split(), cwd, env, resolve)
    files = PG.npm_config_files(inst, env, cwd, resolve)
    return PG.npm_registry_for(inst, scope, env, files)[0]


def test_npm_order_builtin_global_user_project_env_cli(tmp_path: Path) -> None:
    env, resolve = npm_world(tmp_path)
    proj = tmp_path / "proj"
    write(proj / "package.json", "{}")
    assert registry("npm install x", proj, env, resolve) == "https://builtin.example/"
    write(tmp_path / "node" / "etc" / "npmrc", "prefix=${HOME}/.local\nregistry=https://global.example/\n")
    assert registry("npm install x", proj, env, resolve) == "https://global.example/"
    write(tmp_path / "home" / ".npmrc", 'registry = "https://user.example/"\n')
    assert registry("npm install x", proj, env, resolve) == "https://user.example/"
    write(proj / ".npmrc", "; a comment\nregistry=https://${REG_HOST}/\n")
    assert (
        registry("npm install x", proj, {**env, "REG_HOST": "proj.example"}, resolve)
        == "https://proj.example/"
    )
    env2 = {**env, "REG_HOST": "proj.example", "NPM_CONFIG_REGISTRY": "https://env.example/"}
    assert registry("npm install x", proj, env2, resolve) == "https://env.example/"
    assert (
        registry("npm install --registry https://cli.example/ x", proj, env2, resolve)
        == "https://cli.example/"
    )


def test_npm_scope_registry(tmp_path: Path) -> None:
    env, resolve = npm_world(tmp_path)
    write(tmp_path / "home" / ".npmrc", "@tl:registry=https://scope.example/\n")
    assert registry("npm install @tl/x", tmp_path, env, resolve, "@tl") == "https://scope.example/"
    # a scope's own registry is used even when --registry names another (npm's rule)
    assert (
        registry("npm install --registry https://cli.example/ @tl/x", tmp_path, env, resolve, "@tl")
        == "https://scope.example/"
    )
    assert registry("npm install @other/x", tmp_path, env, resolve, "@other") == "https://builtin.example/"


def test_credentials_are_redacted_in_display_and_never_sent(tmp_path: Path) -> None:
    assert (
        PG.display_url("https://u:p@reg.example/simple") == "https://[REDACTED:credential]@reg.example/simple"
    )
    assert PG.display_url("https://reg.example/simple") == "https://reg.example/simple"
    assert PG._clean_url("https://u:p@reg.example:8443/x") == "https://reg.example:8443/x"
