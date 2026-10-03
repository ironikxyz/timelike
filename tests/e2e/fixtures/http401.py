"""A local HTTP server that demands credentials on every request (SC-3 fixture; tasks.md T021).

Runs INSIDE the agent container with the image's interpreter:
    python3 -I http401.py STATE_DIR
It binds 127.0.0.1 on a free port, writes "<pid> <port>" to STATE_DIR/server, and appends one line
per request ("<method> <path> 401") to STATE_DIR/requests. Every answer is 401 with
`WWW-Authenticate: Basic realm="timelike-sc3"`, which is exactly what makes git look for a username.

The request log is the artefact the test reads (lore cross-stack P004): it proves git reached the
credential challenge, so a fast failure is a refused prompt, not a network error.
Stdlib only; no network beyond loopback.
"""

from __future__ import annotations

import http.server
import os
import sys
from pathlib import Path


def main() -> int:
    state = Path(sys.argv[1])
    requests = state / "requests"

    class Handler(http.server.BaseHTTPRequestHandler):
        def _deny(self) -> None:
            with requests.open("a") as log:
                log.write(f"{self.command} {self.path} 401\n")
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Basic realm="timelike-sc3"')
            self.send_header("Content-Length", "0")
            self.end_headers()

        do_GET = _deny  # BaseHTTPRequestHandler dispatches on these names
        do_POST = _deny
        do_HEAD = _deny

        def log_message(self, format: str, *args: object) -> None:
            return

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    tmp = state / "server.tmp"
    tmp.write_text(f"{os.getpid()} {server.server_address[1]}\n")
    tmp.rename(state / "server")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
