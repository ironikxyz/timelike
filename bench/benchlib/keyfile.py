"""keyfile — the live run's key, read from a file, and the gate artifacts are written through (FR-29, FR-31).

The key is read from the file `BENCH_KEY_FILE` names, and from nowhere else: never argv, never an image's
`ENV`, never a container's `Config.Env`, never a file in the repository (P4). The file is refused unless it is
a regular file (not a symlink), mode exactly 0600, owned by the user running the bench, outside the
repository, and holds one non-empty line. Every refusal names the path and the property that failed. **No
message, here or anywhere in the bench, contains the value**: the module never formats it, and the gate below
exists to make sure nothing else does either.

`Gate` is the one way the bench writes a file. It refuses content containing the key's value, naming the file
and never the value, and writes nothing in that case. In the vanilla image nothing strips secret-shaped
variables from the agent's commands, so an agent can print the key; the gate is what keeps it out of the
record. A fake-agent run has no key, and its gate passes everything.

Stdlib only (constitution H5).
"""

from __future__ import annotations

import contextlib
import os
import stat
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path

MODE = 0o600


class KeyFileError(Exception):
    """The key file was refused. The message names the path and the property, never the value."""


class GateRefused(Exception):
    """A write was refused because its content holds the key. The message names the file only."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(
            f"refused to write {name}: it contains the key's value (the value is not shown); "
            "nothing was written to it"
        )


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def read_key(
    path_text: str,
    *,
    repo_root: Path | None = None,
    uid: int | None = None,
    lstat: Callable[[Path], os.stat_result] = os.lstat,
) -> str:
    """The key, after every check. `uid` and `lstat` exist so units can stand in another owner."""
    if not path_text.strip():
        raise KeyFileError("BENCH_KEY_FILE is empty: name the key file")
    path = Path(path_text)
    if not path.is_absolute():
        raise KeyFileError(f"{path}: BENCH_KEY_FILE must be an absolute path")
    try:
        st = lstat(path)
    except FileNotFoundError:
        raise KeyFileError(f"{path}: no such file") from None
    except OSError as e:
        raise KeyFileError(f"{path}: cannot be read ({e.strerror or e})") from None
    if stat.S_ISLNK(st.st_mode):
        raise KeyFileError(f"{path}: is a symbolic link; name the file itself")
    if not stat.S_ISREG(st.st_mode):
        raise KeyFileError(f"{path}: is not a regular file")
    mode = stat.S_IMODE(st.st_mode)
    if mode != MODE:
        raise KeyFileError(f"{path}: mode is {mode:04o}, must be 0600 (chmod 600 {path})")
    want_uid = os.getuid() if uid is None else uid
    if st.st_uid != want_uid:
        raise KeyFileError(
            f"{path}: owned by uid {st.st_uid}, not by the user running the bench ({want_uid})"
        )
    if repo_root is not None and _inside(path.resolve(), repo_root.resolve()):
        raise KeyFileError(f"{path}: is inside the repository; keep the key outside code/")
    try:
        raw = path.read_bytes()
    except OSError as e:
        raise KeyFileError(f"{path}: cannot be read ({e.strerror or e})") from None
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise KeyFileError(f"{path}: is not UTF-8 text") from None
    lines = text.splitlines()
    if len(lines) != 1 or not lines[0].strip():
        raise KeyFileError(f"{path}: must hold exactly one non-empty line (it holds {len(lines)})")
    key = lines[0].strip()
    if any(ch.isspace() for ch in key):
        raise KeyFileError(f"{path}: the line holds whitespace inside the key")
    return key


class Gate:
    """Writes files, refusing any whose content holds one of `secrets` (FR-31)."""

    def __init__(self, secrets: Sequence[str] = ()) -> None:
        self._secrets = tuple(s for s in secrets if s)

    @property
    def armed(self) -> bool:
        return bool(self._secrets)

    def check(self, text: str, name: str) -> None:
        if any(s in text for s in self._secrets):
            raise GateRefused(name)

    def write_text(self, path: Path, text: str) -> Path:
        """Check, then write atomically: a reader sees the old file or the new, never half of either."""
        self.check(text, str(path))
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(text)
            os.replace(tmp, path)
        except BaseException:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(tmp)
            raise
        return path
