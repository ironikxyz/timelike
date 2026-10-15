"""adoption — which calls ran a timelike tool by name, and which went through timelike (spec FR-19, SC-4).

The bench counts **adoption** from the trace's own commands, never from the model's words: a call invokes a
timelike tool when one of its *command words* has a base name in the run's timelike tool list (read from the
timelike image's `timelike tools --json`). A call that runs a shimmed installer or a guarded command by name
is **through timelike** instead: timelike stands in front of it, but the agent did not choose a tool, so it is
counted separately and never as adoption.

A command word is the first word of each simple command: the command is split on `;`, `&&`, `||`, `|`, `&`,
parentheses and newlines outside quotes, and in each piece leading `NAME=value` words and the wrappers
`command`, `exec`, `env`, `nohup`, `time` and `timeout <n>` are skipped. `echo run` invokes nothing; `cd x &&
run make` invokes `run`. A command nested inside a string (`bash -c 'run x'`) is not looked into: that is the
agent running bash, and the report says counts come from command words.

Stdlib only (constitution H5).
"""

from __future__ import annotations

import os
import shlex
from collections.abc import Iterable

# 013's shims (/opt/timelike/shims): the installers a bare call reaches the package guard through.
SHIMMED = ("pip", "pip3", "uv", "npm", "npx", "pnpm")

_SEPARATORS = frozenset({";", "&&", "||", "|", "&", "|&", ";;", "(", ")", "{", "}", "!", "\n"})
_WRAPPERS = frozenset({"command", "exec", "nohup", "builtin"})
# git's global options that take a separate value: `git -C dir reset --hard`.
_GIT_OPTS_WITH_VALUE = frozenset({"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"})


def _split_lines(command: str) -> str:
    """Newlines outside quotes become `;`, so each line is its own simple command; quoted ones stay."""
    out: list[str] = []
    quote = ""
    escaped = False
    for ch in command:
        if escaped:
            escaped = False
        elif ch == "\\" and quote != "'":
            escaped = True
        elif quote:
            if ch == quote:
                quote = ""
        elif ch in ("'", '"'):
            quote = ch
        elif ch == "\n":
            out.append(" ; ")
            continue
        out.append(ch)
    return "".join(out)


def _tokens(command: str) -> list[str]:
    lexer = shlex.shlex(_split_lines(command), posix=True, punctuation_chars=";&|()")
    lexer.whitespace_split = True
    lexer.commenters = "#"
    try:
        return list(lexer)
    except ValueError:  # unbalanced quotes: fall back to whitespace, still counting command words
        return command.replace(";", " ; ").split()


def simple_commands(command: str) -> list[list[str]]:
    """The command's simple commands, each a list of words, wrappers and leading assignments removed."""
    pieces: list[list[str]] = [[]]
    toks = _tokens(command)
    i = 0
    while i < len(toks):
        tok = toks[i]
        prev = toks[i - 1] if i else ""
        if tok in ("&", ">&", "<&") and prev[-1:] in (">", "<"):
            pieces[-1].append(prev + tok)  # `2>&1`, `>&2`: a redirection, not a separator
            i += 2
            continue
        if tok in _SEPARATORS or (tok and set(tok) <= set(";&|()")):
            pieces.append([])
        else:
            pieces[-1].append(tok)
        i += 1
    return [words for words in (_strip(p) for p in pieces) if words]


def _strip(words: list[str]) -> list[str]:
    i = 0
    while i < len(words):
        w = words[i]
        if "=" in w and not w.startswith("=") and w.split("=", 1)[0].replace("_", "a").isalnum():
            i += 1  # NAME=value
        elif w in _WRAPPERS:
            i += 1
        elif w == "time":
            i += 1
            while i < len(words) and words[i].startswith("-"):
                i += 1
        elif w == "env":
            i += 1
            while i < len(words) and (words[i].startswith("-") or "=" in words[i]):
                i += 2 if words[i] in ("-u", "--unset", "-C", "--chdir") else 1
        elif w == "timeout":
            i += 1
            while i < len(words) and words[i].startswith("-"):
                i += 2 if words[i] in ("-s", "--signal", "-k", "--kill-after") else 1
            i += 1  # the duration
        else:
            break
    return words[i:]


def command_words(command: str) -> list[str]:
    """The base name of each simple command's first word, in order."""
    return [os.path.basename(words[0]) for words in simple_commands(command)]


def timelike_tools_in(command: str, tools: Iterable[str]) -> list[str]:
    """The timelike tools the command runs by name, in order, each name once."""
    known = set(tools)
    seen: list[str] = []
    for word in command_words(command):
        if word in known and word not in seen:
            seen.append(word)
    return seen


def _rm_recursive(args: list[str]) -> bool:
    for a in args:
        if a == "--":
            return False
        if a in ("--recursive", "-R", "-r"):
            return True
        if a.startswith("-") and not a.startswith("--") and ("r" in a or "R" in a):
            return True
    return False


def _git_guarded(args: list[str]) -> str:
    i = 0
    while i < len(args) and args[i].startswith("-"):
        i += 2 if args[i] in _GIT_OPTS_WITH_VALUE else 1
    if i >= len(args):
        return ""
    sub, rest = args[i], args[i + 1 :]
    if sub == "reset" and "--hard" in rest:
        return "guard:git reset --hard"
    if sub == "push" and any(a in ("-f", "--force") or a.startswith("--force") for a in rest):
        return "guard:git push --force"
    if sub == "clean":
        return "guard:git clean"
    return ""


def through_timelike(command: str) -> list[str]:
    """What in the command timelike stands in front of: `shim:<installer>`, or `guard:<form>` (005)."""
    found: list[str] = []
    for words in simple_commands(command):
        name, args = os.path.basename(words[0]), words[1:]
        label = ""
        if name in SHIMMED:
            label = f"shim:{name}"
        elif name == "rm" and _rm_recursive(args):
            label = "guard:rm -r"
        elif name == "git":
            label = _git_guarded(args)
        if label and label not in found:
            found.append(label)
    return found
