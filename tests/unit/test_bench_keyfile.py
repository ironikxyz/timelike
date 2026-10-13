"""Units for benchlib.keyfile (feature 002 slice 1, FR-29 and FR-31): the key file's rule and the write gate.

The value used here is a made-up string. No message may ever contain it, so every refusal is checked for it.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from benchlib import keyfile as k

VALUE = "test-value-not-a-key-0123456789abcdef"  # not key-shaped, not a real key


def keyfile(tmp_path: Path, text: str = VALUE + "\n", mode: int = 0o600) -> Path:
    p = tmp_path / "key"
    p.write_text(text)
    p.chmod(mode)
    return p


def refused(path: str, **kw: object) -> str:
    with pytest.raises(k.KeyFileError) as e:
        k.read_key(path, **kw)  # type: ignore[arg-type]
    msg = str(e.value)
    assert VALUE not in msg
    return msg


def test_a_good_file_is_read(tmp_path: Path) -> None:
    assert k.read_key(str(keyfile(tmp_path))) == VALUE


def test_no_trailing_newline_is_fine(tmp_path: Path) -> None:
    assert k.read_key(str(keyfile(tmp_path, VALUE))) == VALUE


@pytest.mark.parametrize("mode", [0o644, 0o640, 0o400, 0o700, 0o660])
def test_any_mode_but_0600_is_refused(tmp_path: Path, mode: int) -> None:
    msg = refused(str(keyfile(tmp_path, mode=mode)))
    assert f"mode is {mode:04o}, must be 0600" in msg


def test_a_symlink_is_refused(tmp_path: Path) -> None:
    target = keyfile(tmp_path)
    link = tmp_path / "link"
    link.symlink_to(target)
    assert "symbolic link" in refused(str(link))


def test_another_owner_is_refused(tmp_path: Path) -> None:
    msg = refused(str(keyfile(tmp_path)), uid=os.getuid() + 1)
    assert "not by the user running the bench" in msg


def test_a_file_inside_the_repository_is_refused(tmp_path: Path) -> None:
    repo = tmp_path / "code"
    repo.mkdir()
    p = keyfile(repo)
    assert "inside the repository" in refused(str(p), repo_root=repo)


@pytest.mark.parametrize("text", ["", "\n", VALUE + "\nsecond\n", "  \n", "two words\n"])
def test_not_exactly_one_clean_line_is_refused(tmp_path: Path, text: str) -> None:
    refused(str(keyfile(tmp_path, text)))


def test_missing_relative_empty_and_directory_are_refused(tmp_path: Path) -> None:
    assert "no such file" in refused(str(tmp_path / "absent"))
    assert "absolute path" in refused("relative/key")
    assert "is empty" in refused("")
    d = tmp_path / "dir"
    d.mkdir()
    assert "not a regular file" in refused(str(d))


# --- the gate -------------------------------------------------------------------------------------


def test_the_gate_writes_clean_content(tmp_path: Path) -> None:
    gate = k.Gate([VALUE])
    p = gate.write_text(tmp_path / "out" / "trace.json", "{}\n")
    assert p.read_text() == "{}\n"
    assert [x.name for x in p.parent.iterdir()] == ["trace.json"]


def test_the_gate_refuses_naming_the_file_never_the_value(tmp_path: Path) -> None:
    gate = k.Gate([VALUE])
    target = tmp_path / "transcripts" / "t.jsonl"
    with pytest.raises(k.GateRefused) as e:
        gate.write_text(target, f'{{"output": "OPENROUTER_API_KEY={VALUE}"}}\n')
    assert str(target) in str(e.value)
    assert VALUE not in str(e.value)
    assert not target.exists()
    assert not list(target.parent.glob("*"))  # no temporary left behind either


def test_the_gate_keeps_an_earlier_file_when_a_later_write_is_refused(tmp_path: Path) -> None:
    gate = k.Gate([VALUE])
    p = gate.write_text(tmp_path / "report.txt", "old\n")
    with pytest.raises(k.GateRefused):
        gate.write_text(p, VALUE)
    assert p.read_text() == "old\n"


def test_an_unarmed_gate_passes_everything(tmp_path: Path) -> None:
    gate = k.Gate()
    assert not gate.armed
    assert gate.write_text(tmp_path / "x", "anything " + VALUE).read_text().endswith(VALUE)
