"""Netfilter probe for SC-4: can this process change firewall rules? (research R7, lore cross-stack P001).

The image ships no `nft` or `iptables`, so the control is read directly: open an
AF_NETLINK/NETLINK_NETFILTER socket and send one nfnetlink request (an nftables GETTABLE dump).
The kernel checks CAP_NET_ADMIN in `nfnetlink_rcv()` before looking at any nfnetlink message,
reads included, so a process without that capability gets EPERM — either raised by a syscall or
returned as an NLMSG_ERROR carrying -EPERM.

Output (one line) and exit status:
  EPERM         exit 0  the kernel refused: this process cannot touch netfilter (SC-4 holds)
  OK            exit 1  the dump was answered: CAP_NET_ADMIN is present (SC-4 fails)
  <ERRNO NAME>  exit 1  any other outcome, e.g. EPROTONOSUPPORT when nfnetlink is not available
  TIMEOUT       exit 1  no answer within the socket timeout

Stdlib only; run as `python3 -I nfprobe.py`. The message builder and the reply classifier are pure
functions so they can be unit-tested without a netlink socket (tests/unit/test_nfprobe.py).
"""

from __future__ import annotations

import errno
import socket
import struct
import sys

NETLINK_NETFILTER = 12
NFNL_SUBSYS_NFTABLES = 10
NFT_MSG_GETTABLE = 1
NFNETLINK_V0 = 0

NLM_F_REQUEST = 0x1
NLM_F_ACK = 0x4
NLM_F_DUMP = 0x300  # NLM_F_ROOT | NLM_F_MATCH

NLMSG_NOOP = 0x1
NLMSG_ERROR = 0x2
NLMSG_DONE = 0x3

NLMSGHDR = struct.Struct("=IHHII")  # len, type, flags, seq, pid — host byte order
NLMSG_ALIGNTO = 4

SEQ = 0x7F10_0001
TIMEOUT_S = 5.0


def nlmsg_align(n: int) -> int:
    return (n + NLMSG_ALIGNTO - 1) & ~(NLMSG_ALIGNTO - 1)


def build_request(seq: int = SEQ) -> bytes:
    """One nfnetlink message: nlmsghdr + nfgenmsg, an nftables GETTABLE dump for every family."""
    msg_type = (NFNL_SUBSYS_NFTABLES << 8) | NFT_MSG_GETTABLE
    # struct nfgenmsg { __u8 nfgen_family; __u8 version; __be16 res_id; }
    nfgenmsg = struct.pack("=BB", socket.AF_UNSPEC, NFNETLINK_V0) + struct.pack(">H", 0)
    length = NLMSGHDR.size + len(nfgenmsg)
    header = NLMSGHDR.pack(length, msg_type, NLM_F_REQUEST | NLM_F_DUMP, seq, 0)
    return header + nfgenmsg


def errno_name(code: int) -> str:
    return errno.errorcode.get(code, f"ERRNO{code}")


def classify(reply: bytes, seq: int = SEQ) -> str:
    """Classify the kernel's reply to build_request(seq).

    Returns "EPERM" when an NLMSG_ERROR for our sequence carries -EPERM, "OK" when the kernel answered
    with data or NLMSG_DONE (the dump was allowed), the errno name for any other NLMSG_ERROR, "ACK" for
    a zero-error acknowledgement, and "EMPTY" / "MALFORMED" when the reply cannot be read.
    """
    if not reply:
        return "EMPTY"
    offset = 0
    saw_data = False
    while offset + NLMSGHDR.size <= len(reply):
        length, msg_type, _flags, msg_seq, _pid = NLMSGHDR.unpack_from(reply, offset)
        if length < NLMSGHDR.size or offset + length > len(reply):
            return "MALFORMED"
        if msg_seq == seq:
            if msg_type == NLMSG_ERROR:
                if length < NLMSGHDR.size + 4:
                    return "MALFORMED"
                (err,) = struct.unpack_from("=i", reply, offset + NLMSGHDR.size)
                if err == 0:
                    return "ACK"
                return errno_name(-err)
            if msg_type == NLMSG_DONE:
                return "OK"
            if msg_type != NLMSG_NOOP:
                saw_data = True
        offset += nlmsg_align(length)
    if saw_data:
        return "OK"
    return "MALFORMED" if offset < len(reply) else "EMPTY"


def probe() -> str:
    try:
        with socket.socket(socket.AF_NETLINK, socket.SOCK_RAW, NETLINK_NETFILTER) as sock:
            sock.settimeout(TIMEOUT_S)
            sock.bind((0, 0))
            sock.sendto(build_request(), (0, 0))
            return classify(sock.recv(65536))
    except PermissionError:
        return "EPERM"
    except TimeoutError:
        return "TIMEOUT"
    except OSError as exc:
        return errno_name(exc.errno) if exc.errno is not None else "OSERROR"


def main() -> int:
    result = probe()
    print(result)
    return 0 if result == "EPERM" else 1


if __name__ == "__main__":
    sys.exit(main())
