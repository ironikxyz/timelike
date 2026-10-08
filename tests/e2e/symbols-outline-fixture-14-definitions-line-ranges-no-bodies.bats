#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# SC-1 — "A signatures view of a fixture file lists exactly its 14 classes and functions with line ranges
# and no function bodies". (Feature 011, slice 1; spec FR-4, Scenario 1; tasks.md T002;
# contracts/symbols-cli.md § outline; research R2, R7.)
#
# Written from the contract before the tool existed. Every expected value is the test's own (P005):
#   - the fixture `app/models.py` (OUTLINE_PY below) holds exactly 14 definitions: top-level functions, a
#     sync and an async one, classes (one decorated), methods (one under two decorators, one async, one
#     with a signature spanning six lines), a nested function inside a method and two nested levels
#     inside a decorated function. A string and a docstring each carry `def NAME(` text that is not a
#     definition. OUTLINE_EXPECTED is that fixture's list, written by hand: qualified name, kind, first
#     line (the first decorator's, R2), last line, nesting depth, in source order;
#   - every body line the fixture has that could leak carries `BODY_MARK_`, and none may appear;
#   - `symbols outline app/models.py --json`: `definitions` is exactly OUTLINE_EXPECTED (name, qual, kind,
#     start, end, and depth relative to the top level), each `sig` one line; the regenerated signature
#     of `Base.save` is the contract's own example, spacing around `=` aside (the contract shows
#     `bool = False`, R2's `ast.unparse` gives `bool=False`; the criterion fixes neither); the async method's is `async def fetch(…`; the
#     six-line signature carries all of its parameters on one line;
#   - `symbols outline app/models.py --text`: the header's scope says `14 definitions` and `exact`, the
#     verdict starts `14 definitions`, and the body is exactly 14 lines, `START-END kind signature`,
#     ranges and kinds as OUTLINE_EXPECTED, in order;
#   - neither output carries a body line, the string's or the docstring's text.
#
# The fixture is written by the container's printf (P005), never by `symbols`. Isolation: each cell
# has its own workspace (a directory holding `.git`) and its own TIMELIKE_SESSION
# (`sy1-<run id>-<check>-<style>`), checked to have no records before the cell starts; the run id is
# the random suffix of this file's container_tmpdir. teardown_file removes the workspaces and this
# run's session directories (by that prefix) and nothing else.
# Cells: bash -c and bash -lc, `notty`.

load helpers

# This file's session prefix (sessions are `<prefix>-<run id>-<check>-<style>`).
SPREFIX=sy1
SDIR_NAME=symbols-sc1

setup_file() {
  stamp_check
  SDIR="$(container_tmpdir "$SDIR_NAME")"
  RUN_ID="${SDIR##*.}"
  SROOT="$(scratch_root)"
  export SDIR RUN_ID SROOT
}

teardown_file() {
  container_rm "${SDIR:-}"
  rm_sessions
}

# ── helpers (this file's own; the 011 files repeat them so each reads alone) ─────────────────────

# scratch_root — the container's session scratch root, read in the container, never assumed.
scratch_root() {
  local r
  r="$(exec_plain sh -c 'printf "%s" "${TIMELIKE_SCRATCH_ROOT:-/tmp/timelike}"')" || return 1
  [[ "$r" == /?* ]] || { echo "scratch root in the container: '${r}'" >&2; return 1; }
  printf '%s' "$r"
}

# rm_sessions — remove this run's session directories (SROOT/SPREFIX-RUN_ID-*) and nothing else.
rm_sessions() {
  [[ -n "${RUN_ID:-}" && "${SROOT:-}" == /tmp/?* ]] || return 0
  exec_plain sh -c 'for d in "$1/$2-$3-"*; do [ -d "$d" ] && rm -rf -- "$d"; done; exit 0' \
    rm "$SROOT" "$SPREFIX" "$RUN_ID" >/dev/null 2>&1 || true
}

# new_cell NAME STYLE — this cell's workspace (CELL: a fresh directory holding `.git`, so it is the
# workspace root, FR-1; CELL.stderr beside it, outside the workspace) and its own session (SESSION),
# which must have no records yet.
new_cell() {
  CELL="${SDIR}/$1-$2"
  SESSION="${SPREFIX}-${RUN_ID}-$1-$2"
  exec_plain mkdir "$CELL" || { echo "cell path ${CELL} exists: cells must not share a workspace" >&2; return 1; }
  exec_plain mkdir "${CELL}/.git" || return 1
  if exec_plain test -e "${SROOT}/${SESSION}"; then
    echo "session ${SESSION} already has records: cells must not share a session" >&2
    return 1
  fi
}

# put RELPATH CONTENT — write CONTENT and a final newline to CELL/RELPATH with the container's printf
# (P005), making its directory first.
put() {
  exec_plain sh -c 'mkdir -p "$(dirname "$1")" && printf "%s\n" "$2" >"$1"' put "${CELL}/$1" "$2"
}

# bump RELPATH — move CELL/RELPATH's mtime 5 seconds forward, so a change is never hidden by the
# clock's granularity.
bump() {
  exec_plain "$AGENT_PY" -I -c 'import os, sys
st = os.stat(sys.argv[1])
os.utime(sys.argv[1], ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))' "${CELL}/$1"
}

# in_session [-e K=V]... STYLE CMD — run CMD in the workspace as the agent would, in this cell's
# session; stderr goes to CELL.stderr so stdout stays one document.
in_session() {
  local -a envs=()
  while [[ "${1:-}" == -e ]]; do
    envs+=(-e "$2")
    shift 2
  done
  run_in -e "TIMELIKE_SESSION=${SESSION}" "${envs[@]}" "$1" notty "{ cd '${CELL}' && $2; } 2>>'${CELL}.stderr'"
  assert_within 20
}

# flunk MESSAGE — fail with the last run's exit, stdout and stderr.
flunk() {
  local err
  err="$(exec_plain cat "${CELL}.stderr" 2>&1)" || true
  printf '%s\nexit %s; stdout:\n%s\nstderr:\n%s\n' "$1" "$status" "$output" "$err" >&2
  return 1
}

expect_status() {
  [[ "$status" == "$1" ]] || flunk "expected exit $1, got $status"
}

# jpy SCRIPT — Python over the last run's stdout, parsed as JSON into `d`; `g(k)` reads a field by a
# dotted path, top-level first, then under `data`; `rel(p)` strips the workspace (WS) from a path, so
# a path given absolute or relative compares the same. Output in $JPY.
jpy() {
  JPY="$(printf '%s' "$output" | pyq "import json,sys
WS='${CELL}'
d=json.load(sys.stdin)
def g(k, default='<absent>'):
    cur = d
    for i, part in enumerate(k.split('.')):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        elif i == 0 and part in (d.get('data') or {}):
            cur = d['data'][part]
        else:
            return default
    return cur
def rel(p):
    p = str(p)
    return p[len(WS) + 1:] if p.startswith(WS + '/') else p
$1")" || flunk "stdout is not the JSON expected"
}

jval() {
  local line
  while IFS= read -r line; do
    if [[ "$line" == "$1="* ]]; then
      printf '%s' "${line#"$1="}"
      return 0
    fi
  done <<<"$JPY"
  printf '<absent>'
}

expect_j() {
  local got
  got="$(jval "$1")"
  [[ "$got" == "$2" ]] || flunk "$1: expected '$2', got '$got'"
}

# expect_has WHAT TEXT PART… — TEXT contains every PART.
expect_has() {
  local what="$1" text="$2" part
  shift 2
  for part in "$@"; do
    [[ "$text" == *"$part"* ]] || flunk "${what} does not name '${part}': ${text}"
  done
}

# expect_verdict_ends WHAT VERDICT ERE — the cache clause ends the verdict (contract: "Every verdict
# ends with the cache state"; notes come before it). ERE is matched at the very end, after `; `.
expect_verdict_ends() {
  [[ "$2" =~ \;\ ($3)$ ]] || flunk "$1 does not end with the cache clause /; $3/: $2"
}

# text_line PREFIX — the first line of the last run's output starting with PREFIX (or nothing).
text_line() {
  local line
  for line in "${lines[@]}"; do
    if [[ "$line" == "$1"* ]]; then
      printf '%s' "$line"
      return 0
    fi
  done
}

# body_lines — the last run's text lines after the `verdict:` line, blank lines dropped, into BODY.
body_lines() {
  local line seen=0
  BODY=()
  for line in "${lines[@]}"; do
    if ((seen)); then
      [[ -n "${line// /}" ]] && BODY+=("$line")
    elif [[ "$line" == "verdict: "* ]]; then
      seen=1
    fi
  done
  ((seen)) || flunk "no verdict: line in the text output"
}

# ── fixture ───────────────────────────────────────────────────────────────────────────────────

OUTLINE_PY="$(
  cat <<'PY'
"""SC-1 fixture: exactly 14 classes and functions."""
import functools

TEMPLATE = "def phantom(x): return x  # a string, not a definition"


def deco(fn):
    BODY_MARK_01 = "first body line of deco"
    return fn


class Base:
    def save(self, force: bool = False) -> None:
        BODY_MARK_02 = "first body line of save"
        return None


class Order(Base):
    """BODY_MARK_00 docstring of Order: def ghost(): is prose."""

    @deco
    @functools.wraps(deco)
    def checkout(self, items):
        BODY_MARK_03 = "first body line of checkout"

        def helper(item):
            BODY_MARK_04 = "first body line of helper"
            return item

        return [helper(i) for i in items]

    def total(
        self,
        quantity: int,
        price: float,
        discount: float = 0.0,
    ) -> float:
        BODY_MARK_05 = "first body line of total"
        return quantity * price - discount

    async def fetch(self, key: str) -> dict:
        BODY_MARK_06 = "first body line of fetch"
        return {}


async def async_load(path):
    BODY_MARK_07 = "first body line of async_load"
    return path


@deco
def build_report(
    title: str,
    *rows: str,
    sep: str = ", ",
) -> str:
    BODY_MARK_08 = "first body line of build_report"

    def inner(row):
        BODY_MARK_09 = "first body line of inner"

        def innermost(cell):
            BODY_MARK_10 = "first body line of innermost"
            return cell

        return innermost(row)

    return sep.join(inner(r) for r in rows)


@deco
class Customer:
    def __init__(self, name: str) -> None:
        BODY_MARK_11 = "first body line of __init__"
        self.name = name
PY
)"

# The fixture's 14 definitions, by hand: qualified name, kind, start, end, depth. In source order.
OUTLINE_EXPECTED=(
  "deco function 7 9 0"
  "Base class 12 15 0"
  "Base.save method 13 15 1"
  "Order class 18 43 0"
  "Order.checkout method 21 30 1"
  "Order.checkout.helper nested 26 28 2"
  "Order.total method 32 39 1"
  "Order.fetch method 41 43 1"
  "async_load function 46 48 0"
  "build_report function 51 68 0"
  "build_report.inner nested 59 66 1"
  "build_report.inner.innermost nested 62 64 2"
  "Customer class 71 75 0"
  "Customer.__init__ method 73 75 1"
)

# Text that is in the fixture but must never be in an outline: body lines, the string, the docstring.
LEAKS=(BODY_MARK_ "first body line" phantom ghost "docstring of Order" "return fn" "self.name = name")

new_outline_cell() {
  new_cell "$1" "$2"
  put app/models.py "$OUTLINE_PY"
}

# no_leaks — no fixture text other than names and signatures in the last run's output.
no_leaks() {
  local s
  for s in "${LEAKS[@]}"; do
    [[ "$output" != *"$s"* ]] || flunk "the outline carries fixture text '${s}', which is not a name or a signature"
  done
}

# ── checks ────────────────────────────────────────────────────────────────────────────────────

# check_outline_json STYLE — `definitions` is exactly the fixture's 14, with their ranges.
check_outline_json() {
  new_outline_cell json "$1"
  in_session "$1" "symbols outline app/models.py --json"
  expect_status 0
  no_leaks
  local want
  want="$(printf '"%s",' "${OUTLINE_EXPECTED[@]}")"
  jpy "import re
want = [w.split() for w in [${want}]]
defs = g('definitions', []) or []
print('count=' + str(len(defs)))
depths = [x.get('depth') for x in defs if isinstance(x.get('depth'), int)]
base = min(depths) if depths else 0
problems = []
for i, w in enumerate(want):
    if i >= len(defs):
        problems.append('missing ' + w[0])
        continue
    x = defs[i]
    leaf = w[0].rsplit('.', 1)[-1]
    got = [x.get('qual'), x.get('kind'), x.get('start'), x.get('end'), x.get('depth')]
    exp = [w[0], w[1], int(w[2]), int(w[3]), int(w[4]) + base]
    if x.get('name') != leaf or got != exp:
        problems.append('entry %d: want name %s %s, got name %s %s' % (i, leaf, exp, x.get('name'), got))
    sig = x.get('sig')
    if not isinstance(sig, str) or '\n' in sig or leaf not in sig:
        problems.append('entry %d: sig is not one line naming %s: %r' % (i, leaf, sig))
for x in defs[len(want):]:
    problems.append('extra ' + json.dumps(x))
def eq(t):
    return re.sub(r'\s*=\s*', '=', str(t))
sigs = {x.get('qual'): x.get('sig') or '' for x in defs}
if eq(sigs.get('Base.save')) != eq('def save(self, force: bool = False) -> None'):
    problems.append('Base.save sig: %r' % sigs.get('Base.save'))
if not sigs.get('Order.fetch', '').startswith('async def fetch('):
    problems.append('Order.fetch sig: %r' % sigs.get('Order.fetch'))
t = sigs.get('Order.total', '')
if not all(eq(p) in eq(t) for p in ('def total(', 'self', 'quantity: int', 'price: float', 'discount: float = 0.0', '-> float')):
    problems.append('Order.total sig (six source lines, one signature): %r' % t)
if not sigs.get('Order', '').startswith('class Order(Base)'):
    problems.append('Order sig: %r' % sigs.get('Order'))
print('problems=' + json.dumps(problems))"
  expect_j count 14
  expect_j problems '[]'
}

# check_outline_text STYLE — the text view: 14 lines, `START-END kind signature`, nothing else.
check_outline_text() {
  new_outline_cell text "$1"
  in_session "$1" "symbols outline app/models.py --text"
  expect_status 0
  no_leaks
  [[ "${lines[0]:-}" == "symbols: "* ]] || flunk "the first line is not the header"
  expect_has "the header" "${lines[0]}" "14 definitions" "exact"
  local verdict
  verdict="$(text_line "verdict: ")"
  [[ "$verdict" == "verdict: 14 definitions"* ]] || flunk "the verdict does not start with '14 definitions': ${verdict}"
  body_lines
  ((${#BODY[@]} == 14)) || flunk "the body has ${#BODY[@]} lines, want 14 (one per definition, no other line)"
  local i w q kind start end depth
  for i in "${!OUTLINE_EXPECTED[@]}"; do
    w="${OUTLINE_EXPECTED[$i]}"
    read -r q kind start end depth <<<"$w"
    [[ "${BODY[$i]}" =~ ^\ *([0-9]+)-([0-9]+)\ +([a-z]+)\ +(.+)$ ]] ||
      flunk "body line $((i + 1)) is not 'START-END kind signature': ${BODY[$i]}"
    [[ "${BASH_REMATCH[1]}-${BASH_REMATCH[2]} ${BASH_REMATCH[3]}" == "${start}-${end} ${kind}" ]] ||
      flunk "body line $((i + 1)): want ${start}-${end} ${kind} (${q}, depth ${depth}), got: ${BODY[$i]}"
    [[ "${BASH_REMATCH[4]}" == *"${q##*.}"* ]] || flunk "body line $((i + 1)) does not name ${q##*.}: ${BODY[$i]}"
  done
}

@test "SC-1 [bash -c, notty] A signatures view of a fixture file lists exactly its 14 classes and functions with line ranges and no function bodies — JSON: definitions, ranges, kinds, depths, one-line signatures" { check_outline_json c; }
@test "SC-1 [bash -lc, notty] A signatures view of a fixture file lists exactly its 14 classes and functions with line ranges and no function bodies — JSON: definitions, ranges, kinds, depths, one-line signatures" { check_outline_json lc; }
@test "SC-1 [bash -c, notty] A signatures view of a fixture file lists exactly its 14 classes and functions with line ranges and no function bodies — text: 14 lines START-END kind signature, header and verdict" { check_outline_text c; }
@test "SC-1 [bash -lc, notty] A signatures view of a fixture file lists exactly its 14 classes and functions with line ranges and no function bodies — text: 14 lines START-END kind signature, header and verdict" { check_outline_text lc; }
