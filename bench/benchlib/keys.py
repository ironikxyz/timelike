"""API-key-shaped variable detection for fake-agent runs (feature 002, FR-12; research RB9).

A fake-agent run must refuse to start when an API-key-shaped variable is present: in the driver's own
environment, in each image's `Config.Env`, or in each task container's `Config.Env`. The rule is a
port of the F002 secret strip in `image/rootfs/etc/timelike/shell-env.bash` (feature 001, SC-9):

- the name is split on "_" and each part upper-cased;
- it is key-shaped when a part IS one of KEY KEYS APIKEY ACCESSKEY PRIVATEKEY PASSPHRASE PASS
  CREDENTIAL CREDENTIALS, or ENDS WITH one of PASSWORD PASSWORDS PASSWD TOKEN TOKENS SECRET SECRETS;
- `GIT_CONFIG_KEY_<n>` (exact case, decimal n) is exempt: its value names a git config key, and the
  image's own GIT_CONFIG_KEY_0 pins core.hooksPath.

So GIT_ASKPASS, TOKENIZERS_PARALLELISM, MONKEY and KEYBOARD_LAYOUT are not key-shaped, while
npm_config__authToken, PGPASSWORD and GHTOKEN are.

Unlike the shell hook there is NO `TIMELIKE_ENV_ALLOW` bypass: the hook keeps allow-listed names so a
person can pass a token on purpose, but a fake-agent run must not be talkable out of its refusal, so
no variable, allow-list or flag exempts a name here.

Two deliberate differences in scope, both towards refusing more: the hook only sees exported bash
identifiers (it cannot unset `MY-TOKEN` and passes it on), while this module judges any name a
container's `Config.Env` or `os.environ` can hold; and upper-casing is Python's `str.upper`, which
agrees with bash's `${name^^}` on every ASCII name. Stdlib only (constitution H5).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping

KEY_PARTS = frozenset(
    {"KEY", "KEYS", "APIKEY", "ACCESSKEY", "PRIVATEKEY", "PASSPHRASE", "PASS", "CREDENTIAL", "CREDENTIALS"}
)
KEY_SUFFIXES = ("PASSWORD", "PASSWORDS", "PASSWD", "TOKEN", "TOKENS", "SECRET", "SECRETS")

_GIT_CONFIG_KEY_RE = re.compile(r"GIT_CONFIG_KEY_[0-9]+")


def is_key_shaped(name: str) -> bool:
    """True when `name` is API-key-shaped under the F002 rule (no allow-list; see the module doc)."""
    if _GIT_CONFIG_KEY_RE.fullmatch(name):
        return False
    return any(part in KEY_PARTS or part.endswith(KEY_SUFFIXES) for part in name.upper().split("_"))


def key_shaped(env: Mapping[str, str]) -> list[str]:
    """The key-shaped names in `env`, sorted. Values are never read, so none can leak into a message."""
    return sorted(name for name in env if is_key_shaped(name))


def env_list_to_mapping(items: Iterable[str]) -> dict[str, str]:
    """docker inspect's `Config.Env` ("K=V" strings) as a mapping.

    The value is everything after the first "=", so it may itself contain "="; a bare "K" maps to "".
    A name listed twice keeps its last value.
    """
    env: dict[str, str] = {}
    for item in items:
        name, _, value = item.partition("=")
        env[name] = value
    return env
