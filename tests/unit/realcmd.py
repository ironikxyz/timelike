"""A real installer on PATH, found the way the shim finds one (feature 013; lane 013s1-b).

In the agent image /opt/timelike/shims is first on PATH and holds pip, pip3, uv, npm, npx and pnpm whether
or not the installer itself is installed. So `shutil.which("pnpm")` finds the shim in an image with no pnpm,
and a test that asks "is pnpm here?" that way runs against a wrapper that answers 127. `real_which` asks what
the shim asks: the first NAME on PATH outside the shims directory (image/rootfs/opt/timelike/libexec/
install-shim).
"""

from __future__ import annotations

import os

SHIMS_ENV = "TIMELIKE_SHIMS"
DEFAULT_SHIMS = "/opt/timelike/shims"


def _same_dir(a: str, b: str) -> bool:
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def real_which(name: str, path: str | None = None) -> str | None:
    """The first executable NAME on PATH (or `path`) whose directory is not a shims directory, else None."""
    shims = [d for d in (os.environ.get(SHIMS_ENV) or DEFAULT_SHIMS).split(":") if d]
    for d in (os.environ.get("PATH", "") if path is None else path).split(":"):
        d = d or "."
        if any(_same_dir(d, s) for s in shims):
            continue
        c = os.path.join(d, name)
        if os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    return None
