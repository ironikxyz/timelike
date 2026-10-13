"""categories — one category per failed call (feature 002 slice 1, spec FR-40 to FR-43, SC-7).

A failed call is one that exited non-zero or hung. It gets exactly one category, decided in this order from
what the trace already holds (its exit code, its hang flag and the head of its output) and one fact about its
container (whether the kernel's OOM count rose during the run):

1. ``timeout`` — it hung (the bench's limit, or the harness's own), exited 124 (GNU timeout's verdict, and
   003's ``run`` when its own limit fires), or carries 003's ``(timeout after …)`` verdict;
2. ``memory-kill`` — exited 137, or carries 003's ``(out of memory: …)``, **and** the container's
   ``memory.events`` ``oom_kill`` count rose. Exit 137 alone is also what ``kill -9`` gives, so without that
   evidence a 137 is ``other``;
3. ``command-not-found`` — exited 127, or the output says ``command not found`` (bash's own message, and the
   lines 007's handler prints after it);
4. ``module-not-found`` — Python's ``ModuleNotFoundError`` / ``No module named``, Node's
   ``Cannot find module`` / ``ERR_MODULE_NOT_FOUND``;
5. ``network-denial`` — connection refused or unreachable, a DNS failure, Adele's refusal, or the package
   guard's ``unreachable`` verdict. Always from the task container, where the call ran (cross-stack P001);
6. ``other`` — shown in the report, never dropped.

The texts matched are the environment's own (research RB16): bash, glibc, git, curl, pip and Node as they
print them, and timelike's own verdict words from 003's ``run``, 004's ``adele``, 007's handler and 013's
``package-guard``. Matching is on fixed substrings, case-sensitive where the source is, so a reader can
predict it. Stdlib only (constitution H5).
"""

from __future__ import annotations

import re

TIMEOUT = "timeout"
MEMORY_KILL = "memory-kill"
COMMAND_NOT_FOUND = "command-not-found"
MODULE_NOT_FOUND = "module-not-found"
NETWORK_DENIAL = "network-denial"
OTHER = "other"

# In the order they are decided, which is also the report's row order.
CATEGORIES = (TIMEOUT, MEMORY_KILL, COMMAND_NOT_FOUND, MODULE_NOT_FOUND, NETWORK_DENIAL, OTHER)

LABELS = {
    TIMEOUT: "timeout",
    MEMORY_KILL: "memory kill",
    COMMAND_NOT_FOUND: "command not found",
    MODULE_NOT_FOUND: "module not found",
    NETWORK_DENIAL: "network denial (from the task container)",
    OTHER: "other",
}

TIMEOUT_EXIT = 124
KILLED_EXIT = 137
NOT_FOUND_EXIT = 127

# 003's `run` verdict: `exit 124 (timeout after 1 s (--timeout); …)` and `exit 137 (out of memory: …)`.
_RUN_TIMEOUT = re.compile(r"\(timeout after [0-9.]+ s\b")
_RUN_OOM = "(out of memory:"

_COMMAND_NOT_FOUND = (
    "command not found",  # bash, every form; 007's handler prints its hint after this line
    "timelike: install it yourself:",  # 007's handler, when the name is a known installable
    "which is not installed",  # 007's handler, an OS package
)
_MODULE_NOT_FOUND = ("ModuleNotFoundError", "No module named", "Cannot find module", "ERR_MODULE_NOT_FOUND")
_NETWORK_DENIAL = (
    "Connection refused",
    "connection refused",
    "Network is unreachable",
    "network is unreachable",
    "No route to host",
    "Could not resolve host",  # git, curl
    "Temporary failure in name resolution",  # glibc, pip, python
    "Name or service not known",
    "getaddrinfo ENOTFOUND",  # node
    "getaddrinfo EAI_AGAIN",
    "ECONNREFUSED",
    "ENETUNREACH",
    "EAI_AGAIN",
    "Failed to establish a new connection",  # pip / urllib3
    "unreachable from this container",  # 013's package guard
    "registry unreachable",  # 013's package guard
    "nothing performed; the operator extends it",  # Adele's denial: agentio's grant envelope (004, rule 9)
)


def categorize(exit_code: int, hung: bool, output: str, oom_rose: bool = False) -> str:
    """The call's category, or "" for a call that succeeded (exit 0 and no hang). See the module doc."""
    if exit_code == 0 and not hung:
        return ""
    if hung or exit_code == TIMEOUT_EXIT or _RUN_TIMEOUT.search(output):
        return TIMEOUT
    if (exit_code == KILLED_EXIT or _RUN_OOM in output) and oom_rose:
        return MEMORY_KILL
    if exit_code == NOT_FOUND_EXIT or any(s in output for s in _COMMAND_NOT_FOUND):
        return COMMAND_NOT_FOUND
    if any(s in output for s in _MODULE_NOT_FOUND):
        return MODULE_NOT_FOUND
    if any(s in output for s in _NETWORK_DENIAL):
        return NETWORK_DENIAL
    return OTHER


def describe() -> list[str]:
    """The rules, in decision order, for `timelike-bench categories`."""
    return [
        f"1. {LABELS[TIMEOUT]}: hung (the bench's or the harness's limit), exit {TIMEOUT_EXIT}, "
        "or 003's '(timeout after N s' verdict",
        f"2. {LABELS[MEMORY_KILL]}: exit {KILLED_EXIT} or 003's '(out of memory:', and the container's "
        "oom_kill count rose (exit 137 alone is 'other')",
        f"3. {LABELS[COMMAND_NOT_FOUND]}: exit {NOT_FOUND_EXIT}, or 'command not found' "
        "(bash, and 007's handler lines)",
        "4. " + LABELS[MODULE_NOT_FOUND] + ": " + ", ".join(f"'{s}'" for s in _MODULE_NOT_FOUND),
        f"5. {LABELS[NETWORK_DENIAL]}: refused, unreachable, DNS failure, Adele's refusal, "
        "the package guard's 'unreachable'",
        f"6. {LABELS[OTHER]}: anything else; shown, never dropped",
    ]
