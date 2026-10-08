"""agentio — the timelike agent output contract, version 1.

Every timelike tool is built on this module, and `timelike-conform` checks that they obey it.
The contract (rules 1–16) and its concrete formats are specified in
`.specswarm/features/001-agent-shell-baseline/contracts/output-contract.md`; the rule numbers in
the comments below refer to it.

A tool declares itself with `Tool`, returns a `Result` from its `main`, and hands both to `run`,
which owns everything the contract fixes: flag parsing, output mode, capping and truncation order,
error rendering, the exit-code vocabulary and the session event. Stdlib only (constitution H5).
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import shlex
import sys
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, NoReturn

CONTRACT = 1

EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_USAGE = 2
EXIT_NOT_FOUND = 3
EXIT_CONFIRM = 4
EXIT_TIMEOUT = 124
EXIT_CODES: dict[int, str] = {
    EXIT_OK: "ok",
    EXIT_FAILURE: "failure",
    EXIT_USAGE: "usage",
    EXIT_NOT_FOUND: "not_found",
    EXIT_CONFIRM: "confirm",
    EXIT_TIMEOUT: "timeout",
}

DEFAULT_LIMIT = 200
DEFAULT_COLUMNS = 200
HELP_MAX_LINES = 40
DEFAULT_SCRATCH_ROOT = "/tmp/timelike"  # noqa: S108 — rule 10: the documented scratch location
REDACTION_TYPES = frozenset({"token", "password", "key", "secret", "credential"})
RESERVED_KEYS = frozenset(
    {"tool", "target", "scope", "verdict", "exit", "lines", "errors", "truncated"}
    | {"cause", "command_exit", "sections"}  # pass-through and tool-cut output (discovery revision 9)
    | {"cut_lines"}  # rule 13 in JSON: the content strings cut, by index (discovery revision 12)
)

# Exit 4's two envelopes, told apart by `status` (discovery revision 10)
CONFIRMATION_REQUIRED = "confirmation_required"  # rule 9: the agent's own command plus --yes
GRANT_REQUIRED = "grant_required"  # beyond a grant: the OPERATOR's command; nothing performed (T1)

_SESSION_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b[@-Z\\-_]")
_SECRET_ARG_RE = re.compile(
    r"^(--?[A-Za-z0-9_-]*?(token|secret|password|passwd|key)[A-Za-z0-9_-]*=)(.+)$", re.IGNORECASE
)
_SECRET_WORD_TYPE = {
    "token": "token",
    "secret": "secret",
    "password": "password",
    "passwd": "password",
    "key": "key",
}


# ── declarations ───────────────────────────────────────────────────────────────────────────────


class ToolError(Exception):
    """A failure the tool can name. Rendered on stderr per rule 14, exit `code` per rule 5."""

    def __init__(self, code: int, what: str, remediation: str) -> None:
        if code not in EXIT_CODES or code == EXIT_OK:
            raise ValueError(f"exit code {code} is not a failure code in the contract vocabulary")
        super().__init__(what)
        self.code = code
        self.what = what
        self.remediation = remediation


class UsageError(ToolError):
    def __init__(self, what: str, remediation: str) -> None:
        super().__init__(EXIT_USAGE, what, remediation)


# Plain classes, not dataclasses: `dataclasses` imports `inspect`, about 11 ms of every tool's
# start-up (quality-standards: < 100 ms p95 per call).


class Tool:
    __slots__ = (
        "confirm_protocol",
        "destructive",
        "exit_codes",
        "grant_envelope",
        "manifest_extra",
        "mutating",
        "name",
        "passes_exit",
        "probe",
        "reads_stdin",
        "summary",
        "target",
        "usage",
    )  # fmt: skip

    def __init__(
        self,
        name: str,
        target: str,
        summary: str,
        usage: Sequence[str] = (),
        mutating: bool = False,
        destructive: bool = False,
        reads_stdin: bool = False,
        probe: Sequence[str] = (),
        exit_codes: dict[int, str] | None = None,
        manifest_extra: Callable[[], dict[str, Any]] | None = None,
        passes_exit: bool = False,
        grant_envelope: bool = False,
        confirm_protocol: bool | None = None,
    ) -> None:
        self.name = name
        self.target = target
        self.summary = summary
        self.usage = tuple(usage)
        self.mutating = mutating
        self.destructive = destructive
        self.reads_stdin = reads_stdin
        self.probe = tuple(probe)
        self.exit_codes = exit_codes
        self.manifest_extra = manifest_extra
        # Discovery revision 9: the tool runs a command the agent named and returns that command's exit.
        # Its own outcomes stay in the vocabulary (`codes()`); argv splits at the command (`_split_command`).
        self.passes_exit = passes_exit
        # Discovery revision 10: a client whose requests an authority (Adele) brokers. Its exit 4 is the
        # grant envelope, and it is not --yes-confirmed by the agent: the grant is the confirmation.
        self.grant_envelope = grant_envelope
        # Discovery revision 13: rule 9 confirms a change whose scope the arguments do not name exactly,
        # that touches another agent's or session's work, or that cannot be reversed from what the tool
        # shows. A mutating tool outside those cases (edit) declares confirm_protocol=False: no --yes, no
        # confirmation envelope, and rule 8's --dry-run still binds it. None: the same as mutating, so a
        # tool written before revision 13 keeps rule 9 whole (report 03 Appendix B's field, restored).
        if confirm_protocol and not mutating:
            raise ValueError(f"{name}: confirm_protocol=True needs mutating=True")
        self.confirm_protocol = mutating if confirm_protocol is None else confirm_protocol

    def envelopes(self) -> list[str]:
        """The exit-4 envelopes this tool can print, by status (manifest `envelopes`, conform C9)."""
        return [CONFIRMATION_REQUIRED] * self.confirm_protocol + [GRANT_REQUIRED] * self.grant_envelope

    def codes(self) -> dict[int, str]:
        codes = dict(self.exit_codes or {EXIT_OK: "ok", EXIT_FAILURE: "failure", EXIT_USAGE: "usage"})
        if self.confirm_protocol:
            codes.setdefault(EXIT_CONFIRM, "confirmation required: rerun with --yes")
        if self.grant_envelope:
            codes.setdefault(EXIT_CONFIRM, "beyond the grant: nothing performed; the operator extends it")
        bad = set(codes) - set(EXIT_CODES)
        if bad:
            raise ValueError(f"{self.name}: exit codes {sorted(bad)} are outside the contract vocabulary")
        return dict(sorted(codes.items()))


class Cut:
    """Output a tool cut itself (rule 3's order), for a tool whose own sections beat a generic cut.

    `sections` are (label, lines) in display order. `more` is the exact command that prints what was
    omitted, and `full_output` the artefact holding all of it. agentio prints them in the contract's
    order and does not cut again.
    """

    __slots__ = ("full_output", "more", "omitted_bytes", "omitted_lines", "sections")

    def __init__(
        self,
        sections: Sequence[tuple[str, Sequence[str]]],
        omitted_lines: int,
        omitted_bytes: int,
        full_output: str,
        more: str,
    ) -> None:
        self.sections = [(label, list(lines)) for label, lines in sections]
        self.omitted_lines = omitted_lines
        self.omitted_bytes = omitted_bytes
        self.full_output = full_output
        self.more = more


class Result:
    __slots__ = (
        "cause",
        "command_exit",
        "cut",
        "data",
        "envelope",
        "errors",
        "exit",
        "footer",
        "lines",
        "scope",
        "target",
        "verdict",
    )  # fmt: skip

    def __init__(
        self,
        target: str,
        scope: str,
        verdict: str,
        lines: list[str] | None = None,
        errors: list[str] | None = None,
        data: dict[str, Any] | None = None,
        exit: int = EXIT_OK,
        envelope: dict[str, Any] | None = None,  # set by confirm_required or grant_required (exit 4)
        cause: str | None = None,  # command | timeout | usage | internal, open (discovery revision 9)
        command_exit: int | None = None,  # the wrapped command's own exit, None when it never ran
        cut: Cut | None = None,
        footer: int = 0,  # trailing body lines that are the tool's own closing commands, never cut (rule 13)
    ) -> None:
        self.target = target
        self.scope = scope
        self.verdict = verdict
        self.lines = list(lines or [])
        self.errors = list(errors or [])
        self.data = dict(data or {})
        self.exit = exit
        self.envelope = envelope
        self.cause = cause
        self.command_exit = command_exit
        self.cut = cut
        self.footer = footer


class Context:
    __slots__ = (
        "argv", "columns", "event_args", "limit", "mode", "scratch_root", "session", "tool", "verbose",
    )  # fmt: skip

    def __init__(
        self,
        tool: Tool,
        argv: list[str],
        session: str,
        scratch_root: Path,
        mode: str,  # "json" | "text"
        limit: int,  # 0 = uncapped
        verbose: bool,
        columns: int = DEFAULT_COLUMNS,  # rule 13's line cut; a tool may set it per call, 0 = no cut
    ) -> None:
        self.tool = tool
        self.argv = argv
        self.session = session
        self.scratch_root = scratch_root
        self.mode = mode
        self.limit = limit
        self.verbose = verbose
        self.columns = columns
        # The session event's args when a tool sets them: a tool whose argv may hold a secret records
        # them redacted (feature 003 slice 1, rule 15). None records argv, as before.
        self.event_args: list[str] | None = None

    def scratch(self) -> Path:
        """This session's private scratch directory, created on first use (rule 10)."""
        return _session_dir(self.scratch_root, self.session)


# ── public helpers ─────────────────────────────────────────────────────────────────────────────


def redact(value: str, kind: str) -> str:
    """Rule 15: a redacted value is visible as such, never silently removed."""
    if kind not in REDACTION_TYPES:
        raise ValueError(f"unknown redaction type {kind!r}; use one of {sorted(REDACTION_TYPES)}")
    return f"[REDACTED:{kind}]"


# ── rule 15's rule set (feature 003 slice 1; spec FR-33 to FR-39, research R15) ─────────────────────
# One file in gitleaks' own config format, read here and by `make scan`'s gitleaks, so the two cannot
# diverge. Each rule carries one `redact:<type>` tag naming rule 15's type. It is applied as gitleaks
# applies it: keywords as a case-insensitive prefilter, then the regex; the secret is the first
# non-empty capture group (else the whole match); the secret's Shannon entropy must reach the rule's
# `entropy`; and an allowlist regex that matches the secret excuses it.

REDACTION_RULES_ENV = "TIMELIKE_REDACTION_RULES"
DEFAULT_REDACTION_RULES = "/etc/timelike/redaction.toml"
_REDACT_TAG = "redact:"


class RulesUnavailable(Exception):
    """The rule set cannot be used, and why. A load fails as a whole: never a partial rule set."""


class Rule:
    __slots__ = ("allowlist", "entropy", "id", "keywords", "regex", "type")

    def __init__(
        self,
        rule_id: str,
        kind: str,
        regex: re.Pattern[str],
        keywords: tuple[str, ...],
        entropy: float | None,
        allowlist: tuple[re.Pattern[str], ...],
    ) -> None:
        self.id = rule_id
        self.type = kind
        self.regex = regex
        self.keywords = keywords
        self.entropy = entropy
        self.allowlist = allowlist


class RuleSet:
    __slots__ = ("path", "rules")

    def __init__(self, path: str, rules: tuple[Rule, ...]) -> None:
        self.path = path
        self.rules = rules

    def ids(self) -> list[str]:
        return [r.id for r in self.rules]

    def keywords(self) -> tuple[str, ...]:
        """Every rule's keywords, lower-cased; a rule without keywords makes this empty (always look)."""
        if any(not r.keywords for r in self.rules):
            return ()
        return tuple(sorted({k for r in self.rules for k in r.keywords}))


def redaction_rules_path() -> Path:
    return Path(os.environ.get(REDACTION_RULES_ENV) or DEFAULT_REDACTION_RULES)


def _rx(path: Path, rule_id: str, pattern: object) -> re.Pattern[str]:
    if not isinstance(pattern, str) or not pattern:
        raise RulesUnavailable(f"{path}: rule {rule_id}: no regex")
    import warnings  # deferred: only a rule load needs it

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # a FutureWarning on stderr is not the tool's output
            return re.compile(pattern, re.ASCII)  # gitleaks is Go RE2: \w and \b are ASCII there
    except re.error as e:
        raise RulesUnavailable(f"{path}: rule {rule_id}: regex does not compile: {e}") from None


def load_redaction_rules(path: str | Path) -> RuleSet:
    """Read the rule set (gitleaks' format). Raises RulesUnavailable(reason) on any problem."""
    import tomllib  # deferred: no tool's start-up pays for it (quality-standards: < 100 ms p95)

    p = Path(path)
    try:
        doc = tomllib.loads(p.read_bytes().decode("utf-8"))
    except OSError as e:
        raise RulesUnavailable(f"{p}: {e.strerror or e}") from None
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as e:
        raise RulesUnavailable(f"{p}: not valid TOML: {e}") from None
    entries = doc.get("rules")
    if not isinstance(entries, list) or not entries:
        raise RulesUnavailable(f"{p}: no [[rules]]")
    rules: list[Rule] = []
    seen: set[str] = set()
    for n, entry in enumerate(entries, 1):
        rule_id = entry.get("id") if isinstance(entry, dict) else None
        if not isinstance(entry, dict) or not isinstance(rule_id, str) or not rule_id:
            raise RulesUnavailable(f"{p}: rule {n} has no id")
        if rule_id in seen:
            raise RulesUnavailable(f"{p}: rule {rule_id} appears twice")
        seen.add(rule_id)
        tags = [t for t in entry.get("tags", []) if isinstance(t, str) and t.startswith(_REDACT_TAG)]
        if len(tags) != 1:
            have = len(tags)
            raise RulesUnavailable(f"{p}: rule {rule_id} needs exactly one redact:<type> tag, has {have}")
        kind = tags[0][len(_REDACT_TAG) :]
        if kind not in REDACTION_TYPES:
            raise RulesUnavailable(
                f"{p}: rule {rule_id}: type {kind!r} is not one of {', '.join(sorted(REDACTION_TYPES))}"
            )
        keywords = entry.get("keywords", [])
        entropy = entry.get("entropy")
        if not isinstance(keywords, list) or not all(isinstance(k, str) for k in keywords):
            raise RulesUnavailable(f"{p}: rule {rule_id}: keywords must be a list of strings")
        if entropy is not None and (isinstance(entropy, bool) or not isinstance(entropy, int | float)):
            raise RulesUnavailable(f"{p}: rule {rule_id}: entropy must be a number")
        allow: list[re.Pattern[str]] = []
        for a in entry.get("allowlists", []):
            for pattern in a.get("regexes", []) if isinstance(a, dict) else []:
                allow.append(_rx(p, rule_id, pattern))
        rules.append(
            Rule(
                rule_id,
                kind,
                _rx(p, rule_id, entry.get("regex")),
                tuple(k.lower() for k in keywords),
                None if entropy is None else float(entropy),
                tuple(allow),
            )
        )
    return RuleSet(str(p), tuple(rules))


def _shannon(text: str) -> float:
    import math  # deferred, like tomllib

    n = len(text)
    counts: dict[str, int] = {}
    for ch in text:
        counts[ch] = counts.get(ch, 0) + 1
    return -sum(c / n * math.log2(c / n) for c in counts.values())


def redact_text(text: str, rules: RuleSet) -> tuple[str, dict[str, int]]:
    """Replace every secret the rules find with [REDACTED:<type>]; return the text and counts per type.

    A secret spanning lines (a private key) becomes one marker per line it covered, with every newline
    kept, so the text's line count, and every line number computed from it, stays true (R18).
    """
    lowered = text.lower()
    spans: list[tuple[int, int, str]] = []
    for rule in rules.rules:
        if rule.keywords and not any(k in lowered for k in rule.keywords):
            continue
        for m in rule.regex.finditer(text):
            start, end = m.span()
            for g in range(1, (rule.regex.groups or 0) + 1):
                if m.group(g):
                    start, end = m.span(g)
                    break
            secret = text[start:end]
            if not secret:
                continue
            if rule.entropy is not None and _shannon(secret) < rule.entropy:
                continue
            if any(a.search(secret) for a in rule.allowlist):
                continue
            spans.append((start, end, rule.type))
    if not spans:
        return text, {}
    spans.sort(key=lambda x: (x[0], -x[1]))
    out: list[str] = []
    counts: dict[str, int] = {}
    at = 0
    for start, end, kind in spans:
        if start < at:
            continue  # inside a secret already replaced (two rules, one value)
        marker = redact("", kind)
        out.append(text[at:start])
        out.append("\n".join([marker] * (text.count("\n", start, end) + 1)))
        counts[kind] = counts.get(kind, 0) + 1
        at = end
    out.append(text[at:])
    return "".join(out), counts


def confirm_required(ctx: Context, *, target: str, scope: str, plan: list[str]) -> Result:
    """Rule 9: a mutation without --yes exits 4 with an envelope naming the plan and the confirm command."""
    envelope: dict[str, Any] = {
        "tool": ctx.tool.name,
        "target": target,
        "scope": scope,
        "status": CONFIRMATION_REQUIRED,
        "plan": list(plan),
        "confirm": shlex.join([ctx.tool.name, *ctx.argv, "--yes"]),
    }
    return Result(target, scope, "confirmation required", exit=EXIT_CONFIRM, envelope=envelope)


def grant_required(
    ctx: Context,
    *,
    target: str,
    scope: str,
    grant: str,
    limit: dict[str, str],
    extend: str,
    request: dict[str, Any],
    ledger_id: int | None = None,
) -> Result:
    """Discovery revision 10: a request beyond its grant exits 4 with the grant envelope. Nothing was
    performed. `extend` is the OPERATOR's command, so it is never in `confirm` or any field the agent's
    habit runs (grant-envelope.schema.json; T1)."""
    if not ctx.tool.grant_envelope:
        raise ValueError(f"{ctx.tool.name}: grant_required needs Tool(grant_envelope=True)")
    missing = {"name", "allowed", "needed"} - set(limit)
    if missing:
        raise ValueError(f"grant_required: limit lacks {sorted(missing)}")
    if not grant or not extend:
        raise ValueError("grant_required: the grant and the operator's extend command are required")
    envelope: dict[str, Any] = {
        "tool": ctx.tool.name,
        "target": target,
        "scope": scope,
        "status": GRANT_REQUIRED,
        "grant": grant,
        "limit": {k: str(limit[k]) for k in ("name", "allowed", "needed")},
        "extend": extend,
        "extend_by": "operator",
        "performed": False,
        "request": dict(request),
    }
    if ledger_id is not None:
        envelope["ledger_id"] = ledger_id
    verdict = f"beyond grant {grant}: limit {limit['name']}; nothing performed; the operator extends it"
    return Result(target, scope, verdict, exit=EXIT_CONFIRM, envelope=envelope)


def session_id() -> str:
    """The current session id (TIMELIKE_SESSION, default "default"); UsageError when invalid."""
    raw = os.environ.get("TIMELIKE_SESSION")
    if raw is None:
        return "default"
    if not _SESSION_RE.match(raw) or set(raw) == {"."}:
        raise UsageError(
            f"invalid session id {raw!r}",
            "set TIMELIKE_SESSION to 1-64 characters from [A-Za-z0-9._-], not only dots",
        )
    return raw


def scratch_root() -> Path:
    return Path(os.environ.get("TIMELIKE_SCRATCH_ROOT") or DEFAULT_SCRATCH_ROOT)


# ── the entry point ────────────────────────────────────────────────────────────────────────────

Main = Callable[[argparse.Namespace, Context], Result]
Configure = Callable[[argparse.ArgumentParser], None]


def run(
    tool: Tool, main: Main, *, configure: Configure | None = None, argv: list[str] | None = None
) -> NoReturn:
    """Run a tool under the contract and exit. Never returns."""
    started = time.monotonic()
    raw = list(sys.argv[1:] if argv is None else argv)
    own = _leading_options(raw) if tool.passes_exit else raw  # a command's own flags are not ours
    json_errors = "--json" in own  # rule 14 is decided before parsing can fail
    verbose = "--verbose" in own
    root = scratch_root()
    session: str | None = None
    ctx: Context | None = None
    code = EXIT_FAILURE
    try:
        session = session_id()
        parser = _parser(tool, configure)
        if tool.passes_exit:
            own, command = _split_command(parser, raw)
            args = parser.parse_args(own)
            args.command = command
        else:
            args = parser.parse_args(raw)
        if args.json and args.text:
            raise UsageError("--json and --text are mutually exclusive", f"run {tool.name} with one of them")
        mode = "json" if args.json else "text" if args.text else ("text" if _stdout_is_tty() else "json")
        limit = args.limit if args.limit is not None else _env_int("TIMELIKE_OUTPUT_LIMIT", DEFAULT_LIMIT)
        columns = _env_int("COLUMNS", DEFAULT_COLUMNS) or DEFAULT_COLUMNS
        ctx = Context(tool, raw, session, root, mode, limit, verbose, columns)
        if args.help:
            code = _emit_help(tool, parser)
        elif args.agent_info:
            code = _emit_manifest(tool, parser)
        else:
            code = _emit_result(main(args, ctx), ctx, started)
    except ToolError as e:
        code = e.code
        _emit_error(tool, e, json_errors)
    except Exception as e:
        code = EXIT_FAILURE
        where = _save_traceback(root, session, tool)
        remedy = (
            f"report this with the traceback in {where}" if where else "report this; no traceback was saved"
        )
        _emit_error(
            tool, ToolError(EXIT_FAILURE, f"internal error: {type(e).__name__}: {e}", remedy), json_errors
        )
    if session is not None:
        recorded = ctx.event_args if ctx is not None and ctx.event_args is not None else raw
        _write_event(root, session, tool, recorded, code, started, verbose)
    with contextlib.suppress(Exception):
        sys.stdout.flush()
    sys.exit(code)


# ── internals: parsing ─────────────────────────────────────────────────────────────────────────


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise UsageError(message, f"run {self.prog} --help")


def _nonneg_int(text: str) -> int:
    try:
        n = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{text!r} is not an integer") from None
    if n < 0:
        raise argparse.ArgumentTypeError("must be 0 (uncapped) or more")
    return n


def _parser(tool: Tool, configure: Configure | None) -> _Parser:
    p = _Parser(prog=tool.name, add_help=False, allow_abbrev=False)
    p.add_argument("--help", action="store_true", help="this help (at most 40 lines)")
    p.add_argument("--json", action="store_true", help="structured output (default when piped)")
    p.add_argument("--text", action="store_true", help="terse text output (default on a terminal)")
    p.add_argument("--agent-info", action="store_true", help="machine-readable manifest")
    p.add_argument("--limit", type=_nonneg_int, default=None, help="output cap in lines; 0 = no cap")
    p.add_argument("--verbose", action="store_true", help="add timing; warn about event-log failures")
    if tool.destructive:
        p.add_argument("--dry-run", action="store_true", help="show the plan, change nothing")
    if tool.confirm_protocol:  # discovery revision 13: --yes only where rule 9 confirms
        p.add_argument("--yes", action="store_true", help="confirm the mutation")
    if configure is not None:
        configure(p)
    return p


def _long_flags(p: argparse.ArgumentParser) -> list[str]:
    return sorted({o for a in p._actions for o in a.option_strings if o.startswith("--")})


def _leading_options(raw: list[str]) -> list[str]:
    """The words before the command, before a parser exists: options until a plain word or `--`."""
    out: list[str] = []
    for a in raw:
        if a == "--" or not a.startswith("-") or a == "-":
            break
        out.append(a)
    return out


def _split_command(p: argparse.ArgumentParser, raw: list[str]) -> tuple[list[str], list[str]]:
    """Split a pass-through tool's argv into its own options and the command (research 003 R6).

    The tool's options end at the first word that is not one of them, or at `--`; an option that takes
    a value consumes the next word. This is done here rather than with argparse.REMAINDER, whose
    handling of `--` and of options after a positional differs between Python 3.12 and 3.14. An
    unknown option stays in the prefix, so argparse still rejects it (usage, exit 2).
    """
    own: list[str] = []
    i = 0
    while i < len(raw):
        a = raw[i]
        if a == "--":
            return own, raw[i + 1 :]
        if not a.startswith("-") or a == "-":
            return own, raw[i:]
        own.append(a)
        action = p._option_string_actions.get(a.split("=", 1)[0])
        if action is not None and "=" not in a and action.nargs != 0 and i + 1 < len(raw):
            own.append(raw[i + 1])
            i += 1
        i += 1
    return own, []


# ── internals: rendering ───────────────────────────────────────────────────────────────────────


def _clean(text: str) -> str:
    """Rule 13: no ANSI escapes, and no embedded newlines inside a single output line."""
    return _ANSI_RE.sub("", text).replace("\r", "").replace("\n", " ")


def _cut(line: str, columns: int) -> str:
    """Rule 13: cut at COLUMNS with a marker and the byte count removed (no cut when columns is 0)."""
    if columns <= 0 or len(line) <= columns:
        return line
    rest = line[columns:]
    return f"{line[:columns]} …[cut {len(rest.encode())} bytes]"


def _clean_data(value: Any) -> Any:
    if isinstance(value, str):
        return _ANSI_RE.sub("", value)
    if isinstance(value, dict):
        return {str(k): _clean_data(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if isinstance(value, list | tuple):
        return [_clean_data(v) for v in value]
    return value


def _print_json(doc: dict[str, Any], stream: Any = None) -> None:
    print(json.dumps(doc, ensure_ascii=False), file=stream or sys.stdout)


def _emit_help(tool: Tool, p: argparse.ArgumentParser) -> int:
    columns = _env_int("COLUMNS", DEFAULT_COLUMNS) or DEFAULT_COLUMNS
    lines = [f"{tool.name}: {tool.target} [help]", tool.summary, "usage:"]
    lines += [f"  {u}" for u in (tool.usage or [f"{tool.name} [options]"])]
    lines.append("options:")
    for a in p._actions:
        if a.option_strings:
            lines.append(f"  {', '.join(a.option_strings)}  {a.help or ''}".rstrip())
    codes = f"exit codes: {', '.join(f'{k} {v}' for k, v in tool.codes().items())}"
    if tool.passes_exit:
        codes += "; otherwise the command's own exit"
    lines.append(codes)
    if len(lines) > HELP_MAX_LINES:
        raise ToolError(
            EXIT_FAILURE,
            f"help is {len(lines)} lines; the contract allows {HELP_MAX_LINES}",
            "shorten the tool's usage lines or option help (contract rule 6)",
        )
    print("\n".join(_cut(_clean(x), columns) for x in lines))
    return EXIT_OK


def _emit_manifest(tool: Tool, p: argparse.ArgumentParser) -> int:
    doc: dict[str, Any] = {"tool": tool.name, "target": "manifest", "scope": "agent-info"}
    body: dict[str, Any] = {
        "contract": CONTRACT,
        "summary": tool.summary,
        "usage": " | ".join(tool.usage) if tool.usage else f"{tool.name} [options]",
        "flags": _long_flags(p),
        "exit_codes": {str(k): v for k, v in tool.codes().items()},
        "mutating": tool.mutating,
        "confirm_protocol": tool.confirm_protocol,  # discovery revision 13
        "destructive": tool.destructive,
        "dry_run": tool.destructive,  # the parser adds --dry-run exactly when destructive (rule 8)
        "reads_stdin": tool.reads_stdin,
        "probe": list(tool.probe),
    }
    if tool.passes_exit:
        body["passes_exit"] = True
    body["envelopes"] = tool.envelopes()  # discovery revision 10; conform C9
    if tool.manifest_extra is not None:
        body.update(tool.manifest_extra())  # may raise ToolError: an invalid manifest is a failure
    doc.update(_clean_data(body))
    _print_json(doc)
    return EXIT_OK


def _emit_result(r: Result, ctx: Context, started: float) -> int:
    if r.exit not in EXIT_CODES and not (
        ctx.tool.passes_exit and r.command_exit is not None and r.command_exit == r.exit
    ):
        # Discovery revision 9: outside the six only as a declared pass-through of the command's exit.
        # The cause may be any (`command`, or 003 slice 1's `memory` and `disk`): it says why the
        # command ended, and the exit is still the command's own.
        raise ValueError(f"result exit {r.exit} is outside the contract vocabulary")
    if r.envelope is not None:  # exit 4: the envelope is JSON on stdout in every mode (rule 9)
        status = r.envelope.get("status")
        if r.exit != EXIT_CONFIRM or status not in ctx.tool.envelopes():
            # Discovery revision 10: only exit 4 carries an envelope, and only one the manifest declares
            declared = ctx.tool.envelopes()
            raise ValueError(f"{ctx.tool.name} declares {declared}, not {status!r} on exit {r.exit}")
        # The envelope's own key order, not sorted: rule 12's tool, target, scope come first, then its
        # status. Sorting the top level (as `_clean_data` does for data) put `confirm` first.
        _print_json({str(k): _clean_data(v) for k, v in r.envelope.items()})
        return r.exit
    clash = RESERVED_KEYS & set(r.data)
    if clash:
        raise ValueError(f"result data may not use reserved keys {sorted(clash)}")

    columns = ctx.columns
    header = f"{ctx.tool.name}: {_clean(r.target)} [{_clean(r.scope)}]"
    body = [_clean(x) for x in r.lines]
    errors = [_clean(x) for x in r.errors]
    capped = ctx.limit > 0 and len(body) > ctx.limit and r.cut is None

    shown, truncated = body, None
    if r.cut is not None:
        shown = [_clean(x) for _, lines in r.cut.sections for x in lines]
        truncated = {
            "omitted_lines": r.cut.omitted_lines,
            "omitted_bytes": r.cut.omitted_bytes,
            "full_output": r.cut.full_output,
            "more": r.cut.more,
        }
    elif capped:
        errs = errors[:3]
        head_n = max(1, (ctx.limit - len(errs)) // 2)
        tail_n = max(1, ctx.limit - head_n - len(errs))
        omitted = body[head_n : len(body) - tail_n]
        full = _save_artefact(ctx, [header, f"verdict: {r.verdict}", *body, *errors, f"exit: {r.exit}"])
        more = shlex.join([ctx.tool.name, *_without_limit(ctx.argv), "--limit", "0"])
        truncated = {
            "omitted_lines": len(omitted),
            "omitted_bytes": sum(len(x.encode()) + 1 for x in omitted),
            "full_output": full,
            "more": more,
        }
        shown = body[:head_n] + errs + body[len(body) - tail_n :]

    if ctx.mode == "json":
        # Discovery revision 12: rule 13's line cut applies to JSON's content strings too, with the same
        # marker, and the bytes cut are carried as data. Verdict, errors and data fields are not content.
        json_lines, cut_lines = [], []
        for i, x in enumerate(shown):
            c = x if i >= len(shown) - r.footer else _cut(x, columns)
            if c != x:
                cut_lines.append({"index": i, "cut_bytes": len(x[columns:].encode())})
            json_lines.append(c)
        doc: dict[str, Any] = {"tool": ctx.tool.name, "target": _clean(r.target), "scope": _clean(r.scope)}
        rest: dict[str, Any] = {
            "verdict": r.verdict,
            "exit": r.exit,
            "lines": json_lines,
            "errors": errors,
            **r.data,
        }
        if r.cause is not None:
            rest["cause"] = r.cause
            rest["command_exit"] = r.command_exit
        if r.cut is not None:
            rest["sections"] = [{"label": label, "count": len(lines)} for label, lines in r.cut.sections]
        if truncated is not None:
            rest["truncated"] = truncated
        if cut_lines:
            rest["cut_lines"] = cut_lines
        if ctx.verbose:
            rest["duration_ms"] = int((time.monotonic() - started) * 1000)
        doc.update(_clean_data(rest))
        _print_json(doc)
        return r.exit

    out = [header, f"verdict: {_clean(r.verdict)}"]
    keep = set(range(len(shown) - r.footer, len(shown)))  # shown-index of the tool's closing lines
    if truncated is None:
        out = [_cut(x, columns) for x in out]
        out += [x if i in keep else _cut(x, columns) for i, x in enumerate(body)]
        out += [_cut(x, columns) for x in errors]
    elif r.cut is not None:
        out = [_cut(x, columns) for x in out]
        i = 0
        for label, lines in r.cut.sections:
            out.append(_cut(f"── {_clean(label)} ──", columns))
            for x in lines:
                out.append(_clean(x) if i in keep else _cut(_clean(x), columns))
                i += 1
        out.append(_cut(f"more: {r.cut.more}", columns))
        out += [
            f"exit: {r.exit}",
            f"full output: {truncated['full_output']}",
            f"… omitted {truncated['omitted_lines']} lines ({truncated['omitted_bytes']} bytes)"
            f" — full output: {truncated['full_output']}; more: {truncated['more']}",
        ]
    else:
        out = [_cut(x, columns) for x in out + shown]
        out += [
            f"exit: {r.exit}",
            f"full output: {truncated['full_output']}",
            f"… omitted {truncated['omitted_lines']} lines ({truncated['omitted_bytes']} bytes)"
            f" — full output: {truncated['full_output']}; more: {truncated['more']}",
        ]
    if ctx.verbose:
        out.append(f"duration_ms: {int((time.monotonic() - started) * 1000)}")
    print("\n".join(out))
    return r.exit


def _emit_error(tool: Tool, e: ToolError, as_json: bool) -> None:
    """Rule 14: one JSON object with --json, else one line."""
    what, remedy = _clean(e.what), _clean(e.remediation)
    if as_json:
        _print_json({"tool": tool.name, "error": what, "code": e.code, "remediation": remedy}, sys.stderr)
    else:
        print(f"error: {what} (code {e.code}) — {remedy}", file=sys.stderr)


def _without_limit(argv: list[str]) -> list[str]:
    out: list[str] = []
    skip = False
    for a in argv:
        if skip:
            skip = False
            continue
        if a == "--limit":
            skip = True
            continue
        if a.startswith("--limit="):
            continue
        out.append(a)
    return out


# ── internals: state (rules 10 and 16) ─────────────────────────────────────────────────────────


def _session_dir(root: Path, session: str) -> Path:
    """<root>/<session>/, private (0700) and ours. Raises OSError when that cannot be guaranteed."""
    if not root.exists():
        root.mkdir(parents=True, exist_ok=True)
        with contextlib.suppress(OSError):
            root.chmod(0o1777)  # shared root, like /tmp: every user may create their own session dir
    d = root / session
    with contextlib.suppress(FileExistsError):
        d.mkdir(mode=0o700)
    st = d.lstat()
    if not d.is_dir() or d.is_symlink():
        raise NotADirectoryError(f"{d} is not a directory")
    if st.st_uid != os.getuid():
        raise PermissionError(f"{d} belongs to uid {st.st_uid}, not {os.getuid()}")
    if st.st_mode & 0o077:
        d.chmod(0o700)
    return d


def _save_artefact(ctx: Context, lines: list[str]) -> str:
    text = "\n".join(lines) + "\n"
    import hashlib  # deferred: only capped output needs it (start-up budget)

    digest = hashlib.sha256(text.encode()).hexdigest()[:12]
    try:
        d = ctx.scratch() / "artefacts"
        d.mkdir(mode=0o700, exist_ok=True)
        path = d / f"{ctx.tool.name}-{digest}.txt"
        path.write_text(text)
        return str(path)
    except OSError:
        return "unavailable"


def _save_traceback(root: Path, session: str | None, tool: Tool) -> str | None:
    if session is None:
        return None
    try:
        path = _session_dir(root, session) / f"{tool.name}-traceback.txt"
        import traceback  # deferred: only the failure path needs it (start-up budget)

        path.write_text(traceback.format_exc())
        return str(path)
    except Exception:
        return None


def _redact_arg(arg: str) -> str:
    m = _SECRET_ARG_RE.match(arg)
    if not m:
        return arg
    return m.group(1) + redact(m.group(3), _SECRET_WORD_TYPE[m.group(2).lower()])


def _write_event(
    root: Path, session: str, tool: Tool, argv: list[str], code: int, started: float, verbose: bool
) -> None:
    """Rule 16: one line per invocation. FR-11: a failure here never changes the tool's result."""
    try:
        event = {
            "v": 1,
            "tool": tool.name,
            "args": [_redact_arg(a) for a in argv],
            "cwd": os.getcwd(),
            "exit": code,
            "duration_ms": int((time.monotonic() - started) * 1000),
            "session": session,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "pid": os.getpid(),
        }
        line = (json.dumps(event, ensure_ascii=False) + "\n").encode()
        path = _session_dir(root, session) / "events.jsonl"
        fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_CLOEXEC, 0o600)
        try:
            os.write(fd, line)  # one write on an O_APPEND fd: lines never interleave
        finally:
            os.close(fd)
    except Exception as e:
        if verbose:
            with contextlib.suppress(Exception):
                print(f"warning: session event not written ({type(e).__name__}: {e})", file=sys.stderr)


# ── internals: environment ────────────────────────────────────────────────────────────────────


def _env_int(name: str, default: int) -> int:
    try:
        n = int(os.environ.get(name, ""))
    except ValueError:
        return default
    return n if n >= 0 else default


def _stdout_is_tty() -> bool:
    """Rule 1 only: choose text vs JSON. Never used to decide whether to prompt (rule 4)."""
    try:
        return sys.stdout.isatty()
    except (AttributeError, ValueError):
        return False
