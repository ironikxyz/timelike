"""The relay's own HTTPS client, in the driver image: does it verify a certificate against the system store?

Live run 1 (`bridge/feedback/02-20261014-031353-live-run-1-the-driver-has-no-ca-certificates.md`, item 1):
the driver image had no CA certificates, so every request the relay forwarded to OpenRouter failed
verification, and no lane cell could see it, because every cell used the stand-in over plain HTTP. This
drives the relay as a live run does, against the model stand-in served over TLS, with no network: the
stand-in's certificate is issued by a throwaway CA made for the cell and never kept. Run as root inside the
driver image (it has no USER):

    relay_tls.py store               the system store is there and not empty
    relay_tls.py make DIR            a throwaway CA, and a certificate for localhost it issued (openssl)
    relay_tls.py check DIR refused   CA not in the store: the relay refuses the peer, forwards nothing
    relay_tls.py check DIR verified  CA added to the store: the relay verifies the peer and forwards

Verification is never turned off here; the relay is given no context of its own, as in a live run. The relay's
key is a unique string, not a key. Stdlib and the openssl that ca-certificates depends on.
"""

from __future__ import annotations

import http.client
import json
import os
import ssl
import subprocess
import sys
from pathlib import Path

from benchlib.relay import Relay
from benchlib.standin import StandIn

MODEL = "deepseek/deepseek-v4-pro-0813"
KEY = "not-a-key-relay-tls-cell-5c1e"
TOOLS = [{"type": "function", "function": {"name": "bash", "parameters": {}}}]


def fail(msg: str) -> None:
    print(f"relay_tls: {msg}", file=sys.stderr)
    sys.exit(1)


def store() -> None:
    paths = ssl.get_default_verify_paths()
    print(f"default verify paths: cafile={paths.cafile} capath={paths.capath}")
    capath = Path(paths.capath or paths.openssl_capath)
    hashed = sorted(p.name for p in capath.glob("*.[0-9]")) if capath.is_dir() else []
    if not hashed:
        fail(f"{capath} holds no hashed CA certificate (is ca-certificates installed?)")
    # The default context reads capath lazily, so its cert_store_stats() counts 0 until a lookup: the bundle
    # the same package writes is loaded on its own here, to count what the store holds.
    bundle = capath / "ca-certificates.crt"
    if not bundle.is_file():
        fail(f"{bundle} is missing")
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.load_verify_locations(cafile=str(bundle))
    cas = ctx.cert_store_stats()["x509_ca"]
    if cas <= 0:
        fail(f"{bundle} holds no CA certificate")
    print(f"ok: {len(hashed)} hashed entries in {capath}; {cas} CA certificates in {bundle.name}")


def make(d: Path) -> None:
    def openssl(*args: str) -> None:
        subprocess.run(["openssl", *args], check=True, capture_output=True, cwd=d)

    openssl("req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", "ca.key", "-out", "ca.pem",
            "-days", "1", "-subj", "/CN=timelike bench relay TLS cell CA (throwaway)",
            "-addext", "basicConstraints=critical,CA:TRUE",
            "-addext", "keyUsage=critical,keyCertSign")  # fmt: skip
    openssl("req", "-newkey", "rsa:2048", "-nodes", "-keyout", "server.key", "-out", "server.csr",
            "-subj", "/CN=localhost")  # fmt: skip
    (d / "server.ext").write_text("subjectAltName=DNS:localhost\nextendedKeyUsage=serverAuth\n")
    openssl("x509", "-req", "-in", "server.csr", "-CA", "ca.pem", "-CAkey", "ca.key", "-CAcreateserial",
            "-out", "server.pem", "-days", "1", "-extfile", "server.ext")  # fmt: skip
    print(f"ok: a throwaway CA and a localhost certificate it issued, in {d}")


def check(d: Path, expect: str) -> None:
    standin = StandIn()
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.load_cert_chain(str(d / "server.pem"), str(d / "server.key"))
    standin._server.socket = tls.wrap_socket(standin._server.socket, server_side=True)
    standin.start()
    standin.set_script(["echo one"])
    # As a live run: an https upstream and no context given to the relay, so http.client uses the default one.
    relay = Relay(f"https://localhost:{standin.port}", turn_cap=30, spend_cap_usd=10.0, model=MODEL, key=KEY,
                  host="127.0.0.1", port=0).start()  # fmt: skip
    try:
        relay.begin_run()
        conn = http.client.HTTPConnection("127.0.0.1", relay.port, timeout=30)
        body = {
            "model": MODEL,
            "stream": False,
            "tools": TOOLS,
            "messages": [{"role": "user", "content": "go"}],
        }
        conn.request("POST", "/api/v1/chat/completions", body=json.dumps(body),
                     headers={"Content-Type": "application/json"})  # fmt: skip
        r = conn.getresponse()
        status, text = r.status, r.read().decode()
        conn.close()
        acct = relay.end_run()
    finally:
        relay.stop()
        standin.stop()
    reached = standin.state.requests
    if expect == "refused":
        if status != 502 or "CERTIFICATE_VERIFY_FAILED" not in text or reached != 0:
            fail(
                f"expected the relay to refuse an unknown CA; got {status}, {reached} forwarded: {text[:300]}"
            )
        if (acct.turns, acct.unanswered) != (0, 1):
            fail(f"an unverified peer's request counted as a turn: {acct.summary()}")
        print("ok: with the CA not in the store, the relay refused the peer and forwarded nothing")
    elif expect == "verified":
        if status != 200 or reached != 1:
            fail(f"expected the relay to verify and forward; got {status}, {reached} forwarded: {text[:300]}")
        if acct.turns != 1 or acct.statuses != {"200": 1}:
            fail(f"the answered request was not accounted: {acct.summary()}")
        print("ok: with the CA in the system store, the relay verified the peer and forwarded the request")
    else:
        fail(f"unknown expectation {expect!r}")


def main(argv: list[str]) -> None:
    if os.environ.get("SSL_CERT_FILE") or os.environ.get("SSL_CERT_DIR"):
        fail("SSL_CERT_FILE or SSL_CERT_DIR is set: this cell is about the system store, so neither may be")
    if argv[:1] == ["store"]:
        store()
    elif argv[:1] == ["make"] and len(argv) == 2:
        make(Path(argv[1]))
    elif argv[:1] == ["check"] and len(argv) == 3:
        check(Path(argv[1]), argv[2])
    else:
        fail("usage: relay_tls.py store | make DIR | check DIR refused|verified")


if __name__ == "__main__":
    main(sys.argv[1:])
