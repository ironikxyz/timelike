"""package-guard's reading of install commands (feature 013, T003; spec FR-5 to FR-9).

Which installer, which packages, which versions, and when the guard says it cannot tell. A command the guard
does not read as an install raises NotInstall, so it runs unchanged; a command it cannot read is
`unreadable`, so it is refused, never passed silently (FR-9).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pgmod import PG


def resolve_none(_: str) -> str | None:
    return None


def classify(argv: str | list[str], cwd: Path, **env: str) -> object:
    words = argv.split() if isinstance(argv, str) else argv
    return PG.classify(words, cwd, {"HOME": str(cwd), **env}, resolve_none)


def names(inst: object) -> list[tuple[str, str, str]]:
    return [(r.key, r.spec, r.source) for r in inst.packages]  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    "cmd",
    [
        "pip install tl-old",
        "pip3 install tl-old",
        "pip3.14 install tl-old",
        "/opt/agent/python/bin/pip install tl-old",
        "python -m pip install tl-old",
        "python3 -I -m pip install tl-old",
        "python3.14 -mpip install tl-old",
        "pip --disable-pip-version-check install tl-old",
    ],
)
def test_pip_forms(tmp_path: Path, cmd: str) -> None:
    inst = classify(cmd, tmp_path)
    assert (inst.ecosystem, inst.tool) == ("pypi", "pip")
    assert names(inst) == [("tl-old", "", "registry")]


@pytest.mark.parametrize(
    "cmd",
    [
        "pip list",
        "pip show x",
        "pip download x",
        "pip",
        "python -c 'print(1)'",
        "python script.py install x",
        "python -m venv .venv",
        "npm run test",
        "npm test",
        "npm update",
        "npm init",
        "uv run pytest",
        "uv lock",
        "pnpm run build",
        "ls -la",
        "npx",
    ],
)
def test_not_installs_run_unchanged(tmp_path: Path, cmd: str) -> None:
    with pytest.raises(PG.NotInstall):
        classify(cmd, tmp_path)


def test_pip_names_versions_extras_markers(tmp_path: Path) -> None:
    inst = classify(
        [
            "pip",
            "install",
            "-U",
            "Tl_Old==1.2",
            "tl-fresh[extra]>=1,<2",
            "tl-x; python_version<'3.13'",
            "--pre",
        ],
        tmp_path,
    )
    assert names(inst) == [
        ("tl-old", "==1.2", "registry"),
        ("tl-fresh", ">=1,<2", "registry"),
        ("tl-x", "", "registry"),
    ]
    assert inst.allow_pre is True and not inst.unreadable


def test_pip_local_url_and_vcs(tmp_path: Path) -> None:
    (tmp_path / "proj").mkdir()
    (tmp_path / "proj" / "pyproject.toml").write_text("[project]\nname='p'\n")
    inst = classify(
        [
            "pip",
            "install",
            "./dist/x-1.0-py3-none-any.whl",
            "proj",
            "-e",
            ".",
            "git+https://example.com/r.git",
            "name @ https://example.com/x.whl",
            "https://example.com/y.tar.gz",
        ],
        tmp_path,
    )
    assert [r.source for r in inst.packages] == ["local", "local", "local", "url", "url", "url"]


def test_pip_index_options(tmp_path: Path) -> None:
    inst = classify(
        "pip install -i https://a.example/simple --extra-index-url https://b.example/simple x", tmp_path
    )
    assert inst.index_url == "https://a.example/simple" and inst.extra_index_urls == [
        "https://b.example/simple"
    ]
    assert classify("pip install --no-index -f ./wheels x", tmp_path).no_index is True


def test_requirements_files_nested_and_hashed(tmp_path: Path) -> None:
    (tmp_path / "base.txt").write_text("tl-left-py==1.0.0 \\\n    --hash=sha256:aaa\n")
    (tmp_path / "req.txt").write_text(
        "# a comment\n-r base.txt\ntl-old>=1.0  # inline\n-i https://idx.example/simple\n-c constraints.txt\n"
        "tl-fresh==1.1.0 --hash=sha256:bbb\n-e ./local\n"
    )
    inst = classify("pip install -r req.txt", tmp_path)
    assert names(inst) == [
        ("tl-left-py", "==1.0.0", "registry"),
        ("tl-old", ">=1.0", "registry"),
        ("tl-fresh", "==1.1.0", "registry"),
        ("./local", "", "local"),
    ]
    assert inst.index_url == "https://idx.example/simple"
    assert inst.hashed_pins == {"tl-left-py": {"1.0.0"}, "tl-fresh": {"1.1.0"}}


def test_requirements_without_hashes_is_not_a_lock(tmp_path: Path) -> None:
    (tmp_path / "r.txt").write_text("tl-old==1.0.0\n")
    inst = classify("pip install -r r.txt", tmp_path)
    assert inst.hashed_pins == {} and names(inst) == [("tl-old", "==1.0.0", "registry")]


def test_missing_requirements_file_is_unreadable(tmp_path: Path) -> None:
    inst = classify("pip install -r nope.txt", tmp_path)
    assert inst.unreadable and "nope.txt" in inst.unreadable[0]


def test_unknown_option_before_a_word_is_unreadable(tmp_path: Path) -> None:
    inst = classify("pip install --frobnicate tl-old", tmp_path)
    assert inst.unreadable and "--frobnicate" in inst.unreadable[0]
    inst = classify("npm install --wat tl-left", tmp_path)
    assert inst.unreadable and "--wat" in inst.unreadable[0]


def test_unreadable_version(tmp_path: Path) -> None:
    assert classify("pip install tl-old==1..2", tmp_path).unreadable
    assert classify("npm install tl-left@^a.b", tmp_path).unreadable


@pytest.mark.parametrize(
    ("cmd", "want"),
    [
        ("uv pip install tl-old==1.0", [("tl-old", "==1.0", "registry")]),
        ("uv add tl-old tl-fresh>=1", [("tl-old", "", "registry"), ("tl-fresh", ">=1", "registry")]),
        ("uv tool install ruff@0.5.0", [("ruff", "==0.5.0", "registry")]),
        ("uvx ruff@0.5.0 check .", [("ruff", "==0.5.0", "registry")]),
        ("uvx --from black==24.1 blackd", [("black", "==24.1", "registry")]),
        ("uv tool run cowsay -t hi", [("cowsay", "", "registry")]),
        (
            "uv run --with tl-old,tl-fresh python x.py",
            [("tl-old", "", "registry"), ("tl-fresh", "", "registry")],
        ),
        ("uv --directory sub pip install tl-old", [("tl-old", "", "registry")]),
    ],
)
def test_uv_forms(tmp_path: Path, cmd: str, want: list[tuple[str, str, str]]) -> None:
    inst = classify(cmd, tmp_path)
    assert (inst.ecosystem, inst.tool) == ("pypi", "uv") and not inst.unreadable
    assert names(inst) == want


def test_uv_sync_reads_pyproject_unless_locked(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "p"\ndependencies = ["tl-old>=1"]\n[dependency-groups]\ndev = ["tl-fresh"]\n'
    )
    assert names(classify("uv sync", tmp_path)) == [
        ("tl-old", ">=1", "registry"),
        ("tl-fresh", "", "registry"),
    ]
    locked = classify("uv sync --locked", tmp_path)
    assert locked.lockfile_only and locked.packages == []


@pytest.mark.parametrize(
    ("cmd", "want"),
    [
        ("npm install tl-left", [("tl-left", "", "registry")]),
        ("npm i tl-left@1.3.0", [("tl-left", "1.3.0", "registry")]),
        ("npm add @tl/scoped@^2", [("@tl/scoped", "^2", "registry")]),
        ("npm isntall -D tl-left@next", [("tl-left", "next", "registry")]),
        ("npm install my-alias@npm:tl-left@1", [("tl-left", "1", "registry")]),
        (
            "npm install ../lib ./x.tgz file:../y",
            [("../lib", "", "local"), ("./x.tgz", "", "local"), ("file:../y", "", "local")],
        ),
        (
            "npm install github:u/r u/r git+https://e.example/r.git",
            [("github:u/r", "", "url"), ("u/r", "", "url"), ("git+https://e.example/r.git", "", "url")],
        ),
        ("npm --registry http://r.example/ install tl-left", [("tl-left", "", "registry")]),
        ("npx tl-left --flag", [("tl-left", "", "registry")]),
        (
            "npx -p tl-left -p @tl/scoped some-cmd",
            [("tl-left", "", "registry"), ("@tl/scoped", "", "registry")],
        ),
        ("npm exec --package=tl-left -- cmd", [("tl-left", "", "registry")]),
        ("npm init tl-app", [("create-tl-app", "", "registry")]),
        ("npm create @tl", [("@tl/create", "", "registry")]),
        ("npm init @tl/app@2", [("@tl/create-app", "2", "registry")]),
        ("pnpm add tl-left", [("tl-left", "", "registry")]),
        ("pnpm dlx tl-left", [("tl-left", "", "registry")]),
        ("pnpm create tl-app", [("create-tl-app", "", "registry")]),
    ],
)
def test_node_forms(tmp_path: Path, cmd: str, want: list[tuple[str, str, str]]) -> None:
    inst = classify(cmd, tmp_path)
    assert inst.ecosystem == "npm" and not inst.unreadable
    assert names(inst) == want


def test_npm_registry_and_scope_options(tmp_path: Path) -> None:
    inst = classify(
        ["npm", "install", "--registry", "http://r.example/", "--@tl:registry=http://s.example/", "x"],
        tmp_path,
    )
    assert inst.registry == "http://r.example/" and inst.scoped_registries == {"@tl": "http://s.example/"}


def test_bare_install_reads_package_json(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(
        '{"name": "p", "dependencies": {"tl-left": "^1.0.0"}, "devDependencies": {"@tl/scoped": "2.0.0"},'
        ' "optionalDependencies": {"x": "file:../x"}}'
    )
    assert names(classify("npm install", tmp_path)) == [
        ("tl-left", "^1.0.0", "registry"),
        ("x", "file:../x", "local"),
        ("@tl/scoped", "2.0.0", "registry"),
    ]
    assert [n for n, _, _ in names(classify("npm install --omit=dev", tmp_path))] == ["tl-left", "x"]
    assert names(classify("pnpm install", tmp_path))[0] == ("tl-left", "^1.0.0", "registry")
    sub = tmp_path / "src"
    sub.mkdir()
    assert names(classify("npm install", sub))[0][0] == "tl-left"  # the project root is found upward


def test_bare_install_without_a_readable_package_json_is_unreadable(tmp_path: Path) -> None:
    # The search goes upward, as npm's does, so "none at all" is asked from / (a host's /tmp may hold one).
    assert classify("npm install --prefix /", tmp_path).unreadable
    (tmp_path / "package.json").write_text("{not json")
    assert "cannot read" in classify("npm install", tmp_path).unreadable[0]


def test_lockfile_only_forms(tmp_path: Path) -> None:
    for cmd in ("npm ci", "npm clean-install", "pnpm install --frozen-lockfile"):
        inst = classify(cmd, tmp_path)
        assert inst.lockfile_only and inst.packages == [], cmd
