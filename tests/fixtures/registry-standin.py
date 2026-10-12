#!/usr/bin/env python3
"""A package registry stand-in for the package guard's tests (feature 013, spec FR-33; research R2, R6).

It serves two registries from one loopback port, stdlib only, and never reaches a public registry (lore P005):

- **PyPI's Simple API** under `/simple/`:
  - PEP 691 JSON (api-version 1.4) when asked for `application/vnd.pypi.simple.v1+json`, and PEP 503 HTML
    otherwise;
  - the files themselves, under `/files/`.
- **npm's registry** under `/npm/`:
  - the full package document (`name`, `dist-tags`, `versions`, `time`);
  - the tarballs, under `/npm/<name>/-/<file>.tgz`.

The field names and date formats are the ones PyPI and npm returned on 2026-10-12 (research R2). Every
package is real and installable: the wheels and tarballs are built at start, with real hashes and integrity,
so the real pip, uv and npm install them (lore P005: the installers, not a fixture, decide).

**The catalog** is a JSON file:

    {"pypi": {"NAME": {"releases": [{"version": "1.0.0", "age_days": 400, "yanked": false}, …],
                       "fault": {"delay": 30} | {"status": 503} | {"drop": true} | null,
                       "no_upload_time": false}},
     "npm":  {"NAME": {"releases": [{"version": "1.0.0", "age_days": 400}, …],
                       "dist_tags": {"latest": "1.0.0"},   # default: the highest release
                       "fault": …, "no_time": false}},
     "html_only": false}

`age_days` is counted back from the moment the stand-in starts, so a release one day old is one day old when
the installer asks.

**Every request is logged** to `<dir>/requests.jsonl`, one JSON object per line: `t`, `method`, `path`,
`user_agent`, `accept`, `status`. A test reads this log, not any message, to see what was asked and whether a
file was fetched (lore P004).

Usage: `registry-standin.py --catalog FILE --dir DIR [--host 127.0.0.1] [--port 0]`. Its pid is written to
`<dir>/pid`, and the port it bound to `<dir>/port` once it is listening. It stops on SIGTERM or SIGINT.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import html
import io
import json
import os
import re
import signal
import tarfile
import threading
import time
import urllib.parse
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

PEP691 = "application/vnd.pypi.simple.v1+json"
NOW = dt.datetime.now(dt.UTC)
FIXED_MTIME = (2020, 1, 1, 0, 0, 0)


def normalize(name: str) -> str:
    """PEP 503's normalized name."""
    return re.sub(r"[-_.]+", "-", name).lower()


def released_at(release: dict[str, Any]) -> dt.datetime:
    return NOW - dt.timedelta(days=float(release.get("age_days", 400)))


def pypi_time(t: dt.datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%S.%fZ")  # PyPI: 2024-12-04T17:35:28.174320Z


def npm_time(t: dt.datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%S.") + f"{t.microsecond // 1000:03d}Z"  # npm: 2015-02-24T05:53:13.392Z


def build_wheel(name: str, version: str) -> tuple[str, bytes]:
    """A real, installable pure wheel: a module printing its own name and version, with a true RECORD."""
    dist = re.sub(r"[-_.]+", "_", name)
    module = dist.lower()
    info = f"{dist}-{version}.dist-info"
    files = {
        f"{module}/__init__.py": f'NAME = "{name}"\nVERSION = "{version}"\n'.encode(),
        f"{info}/METADATA": f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n".encode(),
        f"{info}/WHEEL": b"Wheel-Version: 1.0\nGenerator: registry-standin\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
    }
    record = []
    for path, data in files.items():
        digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
        record.append(f"{path},sha256={digest},{len(data)}")
    record.append(f"{info}/RECORD,,")
    files[f"{info}/RECORD"] = ("\n".join(record) + "\n").encode()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for path, data in files.items():
            z.writestr(zipfile.ZipInfo(path, FIXED_MTIME), data)
    return f"{dist}-{version}-py3-none-any.whl", buf.getvalue()


def build_tarball(name: str, version: str) -> bytes:
    """A real npm tarball: package/package.json and package/index.js, which prints its name and version."""
    pkg = {"name": name, "version": version, "main": "index.js", "description": "registry stand-in package"}
    members = {
        "package/package.json": (json.dumps(pkg, indent=2) + "\n").encode(),
        "package/index.js": f"module.exports = {json.dumps(name + '@' + version)};\n".encode(),
    }
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz", format=tarfile.PAX_FORMAT) as t:
        for path, data in members.items():
            ti = tarfile.TarInfo(path)
            ti.size = len(data)
            ti.mtime = 1577836800
            ti.mode = 0o644
            t.addfile(ti, io.BytesIO(data))
    return buf.getvalue()


def version_key(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", v.split("-")[0])[:3])


class Registry:
    def __init__(self, catalog: dict[str, Any], base: str) -> None:
        self.catalog = catalog
        self.base = base  # http://127.0.0.1:PORT
        self.html_only = bool(catalog.get("html_only"))
        self.files: dict[str, bytes] = {}  # url path -> bytes
        self.pypi: dict[str, dict[str, Any]] = {}  # normalized -> {name, files, versions, entry}
        self.npm: dict[str, dict[str, Any]] = {}  # name -> package document, entry
        for name, entry in (catalog.get("pypi") or {}).items():
            self._add_pypi(name, entry)
        for name, entry in (catalog.get("npm") or {}).items():
            self._add_npm(name, entry)

    def _add_pypi(self, name: str, entry: dict[str, Any]) -> None:
        files, versions = [], []
        for rel in entry.get("releases", []):
            filename, data = build_wheel(name, rel["version"])
            path = f"/files/{filename}"
            self.files[path] = data
            f: dict[str, Any] = {
                "core-metadata": False,
                "data-dist-info-metadata": False,
                "filename": filename,
                "hashes": {"sha256": hashlib.sha256(data).hexdigest()},
                "provenance": None,
                "requires-python": None,
                "size": len(data),
                "url": self.base + path,
                "yanked": rel.get("yanked", False),
            }
            if not entry.get("no_upload_time"):
                f["upload-time"] = pypi_time(released_at(rel))
            files.append(f)
            versions.append(rel["version"])
        self.pypi[normalize(name)] = {"name": normalize(name), "files": files, "versions": versions, "entry": entry}

    def _add_npm(self, name: str, entry: dict[str, Any]) -> None:
        releases = entry.get("releases", [])
        versions: dict[str, Any] = {}
        times: dict[str, str] = {}
        base = name.split("/")[-1]
        for rel in releases:
            v = rel["version"]
            data = build_tarball(name, v)
            path = f"/npm/{name}/-/{base}-{v}.tgz"
            self.files[path] = data
            versions[v] = {
                "name": name,
                "version": v,
                "_id": f"{name}@{v}",
                "main": "index.js",
                "dist": {
                    "integrity": "sha512-" + base64.b64encode(hashlib.sha512(data).digest()).decode(),
                    "shasum": hashlib.sha1(data).hexdigest(),  # noqa: S324 — npm's own field, not a security use
                    "tarball": self.base + path,
                    "fileCount": 2,
                },
            }
            times[v] = npm_time(released_at(rel))
        latest = max(versions, key=version_key) if versions else None
        doc: dict[str, Any] = {
            "_id": name,
            "name": name,
            "dist-tags": entry.get("dist_tags") or ({"latest": latest} if latest else {}),
            "versions": versions,
        }
        if not entry.get("no_time") and times:
            created = min(times.values())
            doc["time"] = {"created": created, "modified": max(times.values()), **times}
        self.npm[name] = {"doc": doc, "entry": entry}


class Handler(BaseHTTPRequestHandler):
    registry: Registry
    log_path: Path
    log_lock = threading.Lock()
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 — the base class's name
        pass  # the JSON log below is the record

    def _log(self, status: int) -> None:
        line = {
            "t": dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "method": self.command,
            "path": self.path,
            "user_agent": self.headers.get("User-Agent", ""),
            "accept": self.headers.get("Accept", ""),
            "status": status,
        }
        with self.log_lock, open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(line) + "\n")

    def _send(self, status: int, body: bytes, ctype: str) -> None:
        self._log(status)
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _fault(self, entry: dict[str, Any] | None) -> bool:
        """Apply a package's fault. True when the request has been answered (or dropped)."""
        fault = (entry or {}).get("fault") or {}
        if fault.get("delay"):
            time.sleep(float(fault["delay"]))
        if fault.get("drop"):
            self._log(0)
            self.close_connection = True
            return True
        if fault.get("status"):
            self._send(int(fault["status"]), b'{"error":"stand-in fault"}', "application/json")
            return True
        return False

    def do_HEAD(self) -> None:
        self.do_GET()

    def do_GET(self) -> None:
        path = urllib.parse.urlsplit(self.path).path
        if path in self.registry.files:
            ctype = "application/octet-stream"
            self._send(200, self.registry.files[path], ctype)
        elif path.startswith("/simple/"):
            self._simple(path[len("/simple/") :].strip("/"))
        elif path.startswith("/npm/"):
            self._npm(urllib.parse.unquote(path[len("/npm/") :]).strip("/"))
        else:
            self._send(404, b'{"error":"Not found"}', "application/json")

    def _simple(self, project: str) -> None:
        if not project:
            names = sorted(self.registry.pypi)
            body = "".join(f'<a href="/simple/{n}/">{n}</a>\n' for n in names)
            self._send(200, f"<!DOCTYPE html><html><body>{body}</body></html>".encode(), "text/html")
            return
        p = self.registry.pypi.get(normalize(project))
        if p is None:
            self._send(404, b"404 Not Found", "text/plain")
            return
        if self._fault(p["entry"]):
            return
        accept = self.headers.get("Accept", "")
        if PEP691 in accept and not self.registry.html_only:
            doc = {
                "meta": {"_last-serial": 1, "api-version": "1.4"},
                "name": p["name"],
                "project-status": {"status": "active"},
                "versions": p["versions"],
                "files": p["files"],
            }
            self._send(200, json.dumps(doc).encode(), PEP691)
            return
        links = []
        for f in p["files"]:
            yanked = ' data-yanked=""' if f["yanked"] else ""
            href = html.escape(f"{f['url']}#sha256={f['hashes']['sha256']}")
            links.append(f'<a href="{href}"{yanked}>{html.escape(f["filename"])}</a><br />')
        body = (
            '<!DOCTYPE html>\n<html lang="en">\n  <head>\n'
            '    <meta name="pypi:repository-version" content="1.4">\n'
            f"    <title>Links for {p['name']}</title>\n  </head>\n  <body>\n"
            f"    <h1>Links for {p['name']}</h1>\n" + "\n".join(links) + "\n  </body>\n</html>\n"
        )
        self._send(200, body.encode(), "text/html")

    def _npm(self, name: str) -> None:
        p = self.registry.npm.get(name)
        if p is None:
            self._send(404, b'{"error":"Not found"}', "application/json")
            return
        if self._fault(p["entry"]):
            return
        self._send(200, json.dumps(p["doc"]).encode(), "application/json")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--catalog", required=True, type=Path)
    ap.add_argument("--dir", required=True, type=Path)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=0)
    a = ap.parse_args()
    a.dir.mkdir(parents=True, exist_ok=True)
    catalog = json.loads(a.catalog.read_text(encoding="utf-8"))
    server = ThreadingHTTPServer((a.host, a.port), Handler)
    server.daemon_threads = True
    port = server.server_address[1]
    Handler.registry = Registry(catalog, f"http://{a.host}:{port}")
    Handler.log_path = a.dir / "requests.jsonl"
    Handler.log_path.touch()
    (a.dir / "pid").write_text(f"{os.getpid()}\n", encoding="utf-8")
    tmp = a.dir / "port.tmp"
    tmp.write_text(f"{port}\n", encoding="utf-8")
    os.replace(tmp, a.dir / "port")

    def stop(_signum: int, _frame: Any) -> None:
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    server.serve_forever(poll_interval=0.2)
    server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
