"""Unit tests for tests/fixtures/nfprobe.py (T024): the pure message builder and reply classifier.

The probe itself needs a kernel to answer; the SC-4 bats test runs it inside the image. These tests
pin the bytes it sends and the way it reads replies, so an EPERM verdict cannot come from a message
the kernel rejected for being malformed (that would be EINVAL, not EPERM).
"""

from __future__ import annotations

import errno
import importlib.util
import struct
import sys
from pathlib import Path
from types import ModuleType

import pytest

NFPROBE = Path(__file__).resolve().parents[1] / "fixtures" / "nfprobe.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("nfprobe", NFPROBE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["nfprobe"] = module
    spec.loader.exec_module(module)
    return module


nfprobe = _load()
HDR = struct.Struct("=IHHII")


def error_reply(err: int, seq: int = nfprobe.SEQ) -> bytes:
    """An NLMSG_ERROR as the kernel sends it: header, int error, then the offending request header."""
    original = nfprobe.build_request(seq)[: HDR.size]
    payload = struct.pack("=i", err) + original
    return HDR.pack(HDR.size + len(payload), nfprobe.NLMSG_ERROR, 0x100, seq, 0) + payload


def data_msg(msg_type: int, seq: int = nfprobe.SEQ, body: bytes = b"\0\0\0\0") -> bytes:
    return HDR.pack(HDR.size + len(body), msg_type, 0x2, seq, 0) + body


def test_request_bytes_are_one_nftables_gettable_dump() -> None:
    msg = nfprobe.build_request(0x01020304)
    assert len(msg) == 20
    length, msg_type, flags, seq, pid = HDR.unpack_from(msg, 0)
    assert length == len(msg) == 20
    assert msg_type == (10 << 8) | 1 == 0x0A01  # NFNL_SUBSYS_NFTABLES, NFT_MSG_GETTABLE
    assert flags == 0x1 | 0x300  # NLM_F_REQUEST | NLM_F_DUMP
    assert seq == 0x01020304
    assert pid == 0
    # nfgenmsg: family AF_UNSPEC, version NFNETLINK_V0, res_id 0 (big-endian)
    assert msg[16:] == b"\x00\x00\x00\x00"


def test_request_length_is_netlink_aligned() -> None:
    assert len(nfprobe.build_request()) % 4 == 0


def test_eperm_error_is_eperm() -> None:
    assert nfprobe.classify(error_reply(-errno.EPERM)) == "EPERM"


def test_other_error_is_named() -> None:
    assert nfprobe.classify(error_reply(-errno.EINVAL)) == "EINVAL"
    assert nfprobe.classify(error_reply(-errno.ENOENT)) == "ENOENT"


def test_zero_error_is_ack_not_eperm() -> None:
    assert nfprobe.classify(error_reply(0)) == "ACK"


def test_done_means_dump_allowed() -> None:
    assert nfprobe.classify(data_msg(nfprobe.NLMSG_DONE)) == "OK"


def test_table_data_then_done_means_dump_allowed() -> None:
    newtable = (10 << 8) | 0  # NFT_MSG_NEWTABLE
    assert nfprobe.classify(data_msg(newtable) + data_msg(nfprobe.NLMSG_DONE)) == "OK"


def test_error_for_another_sequence_is_ignored() -> None:
    assert nfprobe.classify(error_reply(-errno.EPERM, seq=99)) == "EMPTY"


def test_empty_and_malformed() -> None:
    assert nfprobe.classify(b"") == "EMPTY"
    assert nfprobe.classify(b"\x01\x02\x03") == "MALFORMED"
    bad_len = HDR.pack(500, nfprobe.NLMSG_ERROR, 0, nfprobe.SEQ, 0) + b"\0\0\0\0"
    assert nfprobe.classify(bad_len) == "MALFORMED"
    short_err = HDR.pack(HDR.size, nfprobe.NLMSG_ERROR, 0, nfprobe.SEQ, 0)
    assert nfprobe.classify(short_err) == "MALFORMED"


def test_unknown_errno_is_still_named() -> None:
    assert nfprobe.classify(error_reply(-9999)) == "ERRNO9999"


@pytest.mark.parametrize(("result", "code"), [("EPERM", 0), ("OK", 1), ("EINVAL", 1), ("TIMEOUT", 1)])
def test_exit_status_is_zero_only_for_eperm(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], result: str, code: int
) -> None:
    monkeypatch.setattr(nfprobe, "probe", lambda: result)
    assert nfprobe.main() == code
    assert capsys.readouterr().out == f"{result}\n"
