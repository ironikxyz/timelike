"""Units for benchlib.adoption (feature 002 slice 1, FR-19).

SC-4: "Each run is labelled told or not-told, and the report counts timelike tool invocations per arm".
Counts come from command words, so these pin what a command word is.
"""

from __future__ import annotations

import pytest
from benchlib import adoption as a

TOOLS = ("run", "view", "search", "edit", "journal", "snapshot", "undo", "package-guard", "timelike")


@pytest.mark.parametrize(
    ("command", "want"),
    [
        ("run make test", ["run"]),
        ("/opt/timelike/bin/view src/app.py", ["view"]),
        ("cd src && run pytest -q", ["run"]),
        ("search foo | head -5", ["search"]),
        ("view a.py; view b.py", ["view"]),  # each tool once per call
        ("FOO=1 BAR=2 run make", ["run"]),
        ("env -u X FOO=1 timeout 30 run make", ["run"]),
        ("time -p run make", ["run"]),
        ("nohup run make &", ["run"]),
        ("command view x", ["view"]),
        ("run make 2>&1 | tail -n 20", ["run"]),
        ("echo run view search", []),  # arguments are not command words
        ("grep -r 'run x' .", []),
        ("bash -c 'run make'", []),  # a nested command string is not looked into
        ("(cd x; edit f.py --old a --new b)", ["edit"]),
        ("git status\njournal", ["journal"]),
        ("echo 'a\nrun b'", []),  # a newline inside quotes is not a new command
        ("timelike tools", ["timelike"]),
        ("package-guard -- pip install x", ["package-guard"]),
        ("echo 'unbalanced", []),
    ],
)
def test_timelike_tools_are_command_words_only(command: str, want: list[str]) -> None:
    assert a.timelike_tools_in(command, TOOLS) == want


@pytest.mark.parametrize(
    ("command", "want"),
    [
        ("pip install requests", ["shim:pip"]),
        ("python3 -m pip install x", []),  # the escape 013 names; not through the shim
        ("npx cowsay hi && npm ci", ["shim:npx", "shim:npm"]),
        ("rm -rf build", ["guard:rm -r"]),
        ("rm -fr build", ["guard:rm -r"]),
        ("rm --recursive build", ["guard:rm -r"]),
        ("rm file.txt", []),
        ("rm -- -r", []),
        ("git reset --hard HEAD~1", ["guard:git reset --hard"]),
        ("git -C repo reset --hard", ["guard:git reset --hard"]),
        ("git reset --soft HEAD~1", []),
        ("git push -f origin main", ["guard:git push --force"]),
        ("git push --force-with-lease", ["guard:git push --force"]),
        ("git push origin main", []),
        ("git clean -fdx", ["guard:git clean"]),
        ("git commit -m 'rm -rf x'", []),
    ],
)
def test_through_timelike_names_the_shim_or_guard(command: str, want: list[str]) -> None:
    assert a.through_timelike(command) == want


def test_command_words_in_order() -> None:
    assert a.command_words("A=1 git add . && git commit -q -m x; run make | tee log") == [
        "git",
        "git",
        "run",
        "tee",
    ]
