"""The shipped /etc/timelike/missing-commands.tsv (feature 007, slice 1; spec FR-16; contract § The
command-not-found answer, "Validity").

The file is read by bash builtins in command_not_found_handle on every typo, so nothing checks it at run
time: a malformed line is silently skipped there. These tests are where a bad line is caught. That every
listed name is absent from the image is an e2e cell, not a unit test.
"""

from __future__ import annotations

import os
import re

import pytest
from conftest import REPO, TOOLS_DIR

DATA = REPO / "image" / "rootfs" / "etc" / "timelike" / "missing-commands.tsv"
KINDS = {"instead", "debian", "user"}
DEBIAN_NAME = re.compile(r"[a-z0-9][a-z0-9+.-]+")
MUST_COVER = {"tree", "rg", "jq"}

# FOR-MENTOR Item 21 (unprivileged installs) was answered by discovery revision 14 (spec FR-18, FR-29):
# `user` rows ship, each a command the agent can run as itself. Kept as a flag so a reversal is one line.
USER_ROWS_ALLOWED = True
USER_PREFIXES = ("pip install ", "npm install -g ")
# The names the image now ships (spec FR-25, FR-29): no answer may list them.
RUNTIME_NAMES = {"python3", "python", "pip", "pip3", "node", "npm", "npx"}

Row = tuple[int, str, str, str, str]  # line number, name, kind, value, note


def data_lines() -> list[tuple[int, str]]:
    """(line number, text) of every line that is not a comment or empty."""
    assert DATA.is_file(), f"the data file is missing: {DATA.relative_to(REPO)}"
    raw = DATA.read_bytes()
    text = raw.decode("utf-8")  # the contract says UTF-8: a decode error fails here
    out = []
    for n, line in enumerate(text.split("\n"), 1):
        if line == "" or line.startswith("#"):
            continue
        out.append((n, line))
    return out


def rows() -> list[Row]:
    out: list[Row] = []
    for n, line in data_lines():
        fields = line.split("\t")
        if len(fields) == 4:
            out.append((n, fields[0], fields[1], fields[2], fields[3]))
    return out


def test_data_file_is_not_empty() -> None:
    assert data_lines(), "no answer rows in the data file"


def test_data_file_ends_with_a_newline() -> None:
    raw = DATA.read_bytes()
    assert raw.endswith(b"\n"), "a last line without a newline is easy to lose"
    assert b"\r" not in raw, "CRLF would put a carriage return into every note"


def test_every_line_has_four_tab_separated_fields() -> None:
    bad = [(n, line) for n, line in data_lines() if len(line.split("\t")) != 4]
    assert not bad, f"lines without exactly four TAB-separated fields: {bad}"


def test_no_field_is_empty_or_padded() -> None:
    """bash's `read` with IFS=TAB collapses empty fields and trims, so an empty or padded field would
    shift or change what the handler reads."""
    bad = [
        (n, name, kind, value, note)
        for n, name, kind, value, note in rows()
        if any(f == "" or f != f.strip() for f in (name, kind, value, note))
    ]
    assert not bad, f"empty or space-padded fields: {bad}"


def test_every_kind_is_known() -> None:
    bad = [(n, kind) for n, _name, kind, _v, _note in rows() if kind not in KINDS]
    assert not bad, f"kinds outside {sorted(KINDS)}: {bad}"


def test_every_name_is_a_command_word() -> None:
    bad = [(n, name) for n, name, *_ in rows() if "/" in name or re.search(r"\s", name) or not name]
    assert not bad, f"names with '/' or whitespace: {bad}"


def test_every_instead_names_a_timelike_tool() -> None:
    insteads = [(n, value) for n, _name, kind, value, _note in rows() if kind == "instead"]
    assert insteads, "no `instead` row at all"
    bad = []
    for n, value in insteads:
        first = value.split()[0] if value.split() else ""
        tool = TOOLS_DIR / first
        if not first or "/" in first or not tool.is_file() or not os.access(tool, os.X_OK):
            bad.append((n, first))
    assert not bad, f"`instead` values whose first word is not an executable in tools/bin/: {bad}"


def test_every_debian_value_is_a_plausible_package_name() -> None:
    bad = [
        (n, value)
        for n, _name, kind, value, _note in rows()
        if kind == "debian" and not DEBIAN_NAME.fullmatch(value)
    ]
    assert not bad, f"`debian` values that are not package names: {bad}"


def test_no_duplicate_answer() -> None:
    seen: dict[tuple[str, str, str], int] = {}
    dups = []
    for n, name, kind, value, _note in rows():
        key = (name, kind, value)
        if key in seen:
            dups.append((seen[key], n, key))
        seen[key] = n
    assert not dups, f"duplicate (name, kind, value): {dups}"


def test_no_user_rows_until_item_21() -> None:
    users = [(n, name, value) for n, name, kind, value, _note in rows() if kind == "user"]
    if USER_ROWS_ALLOWED:
        pytest.skip("user rows are allowed (Item 21 answered)")
    assert not users, f"`user` rows ship only after FOR-MENTOR Item 21 is answered: {users}"


@pytest.mark.parametrize("name", sorted(MUST_COVER))
def test_covers_the_common_names(name: str) -> None:
    assert name in {r[1] for r in rows()}, f"{name} has no answer"


def user_rows() -> list[tuple[int, str, str]]:
    return [(n, name, value) for n, name, kind, value, _note in rows() if kind == "user"]


def test_every_user_value_is_an_unprivileged_install() -> None:
    """Each `user` value is `pip install X` or `npm install -g X`, one package and no options: the bare
    command goes to the agent's own location by the runtimes' configuration (FR-26, FR-27, FR-29)."""
    if not USER_ROWS_ALLOWED:
        pytest.skip("user rows are not allowed")
    bad = []
    for n, name, value in user_rows():
        prefix = next((p for p in USER_PREFIXES if value.startswith(p)), None)
        rest = value[len(prefix) :] if prefix else ""
        if prefix is None or not re.fullmatch(r"[A-Za-z0-9@][A-Za-z0-9@/._+=<>~-]*", rest):
            bad.append((n, name, value))
    assert not bad, f"`user` values not of the form {[p + 'PACKAGE' for p in USER_PREFIXES]}: {bad}"


@pytest.mark.parametrize("prefix", USER_PREFIXES)
def test_user_rows_cover_both_runtimes(prefix: str) -> None:
    if not USER_ROWS_ALLOWED:
        pytest.skip("user rows are not allowed")
    assert any(value.startswith(prefix) for _n, _name, value in user_rows()), (
        f"no `user` row is a {prefix.strip()!r} install (FR-29: common Python and Node CLIs)"
    )


def test_no_runtime_name_is_listed() -> None:
    """The image ships these now (FR-25), and every listed name must be absent from the image."""
    listed = [(n, name) for n, name, *_ in rows() if name in RUNTIME_NAMES]
    assert not listed, f"rows for names the image ships (FR-29): {listed}"
