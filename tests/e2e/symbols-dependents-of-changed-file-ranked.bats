#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# SC-4 — "A dependents lookup for a changed file returns the files that import it, ranked". (Feature
# 011, slice 1; spec FR-2, FR-7, Scenario 4; tasks.md T002; contracts/symbols-cli.md § dependents;
# research R2, R4, R7.)
#
# Written from the contract before the tool existed. Every expected value is the test's own (P005):
#   - the fixture package `app/`: `models.py` defines Order, Customer and Item. Three files import it
#     directly, each a different number of names, so R4's order is total: `orders.py` (3 names,
#     `from app.models import …`), `billing.py` (2, the relative `from .models import …`), `report.py`
#     (1). `main.py` imports only `app.orders`, so it depends on `models.py` indirectly, via
#     `app/orders.py`. `notes.py` names `app.models` in a docstring, a comment and a string, and imports
#     nothing of the workspace; `__init__.py` is empty. Neither may be listed;
#   - a first `symbols dependents app/models.py` builds the cache; then `models.py` CHANGES (a class
#     appended, its mtime moved forward), and the next `symbols dependents app/models.py` is the one
#     checked: the verdict reports the cache stale (the change was seen);
#   - `--json`: `dependents` is exactly orders, billing, report (depth 1) then main (depth 2, via
#     `app/orders.py`), in that order (R4: direct first, then by names imported, then path); each direct
#     one's names are the fixture's (a list or its count);
#   - `--text`: the verdict says `4 files import app/models.py`; the body lines are the same four paths
#     in the same order, the first three `direct`, the last `indirect`, and nothing else.
#
# Fixtures are written by the container's printf (P005), never by `symbols`. Isolation: each cell has its
# own workspace (a directory holding `.git`) and its own TIMELIKE_SESSION
# (`sy4-<run id>-<check>-<style>`), checked to have no records before the cell starts. teardown_file
# removes the workspaces and this run's session directories (by that prefix) and nothing else.
# Cells: bash -c and bash -lc, `notty`.

load helpers

# This file's session prefix (sessions are `<prefix>-<run id>-<check>-<style>`).
SPREFIX=sy4
SDIR_NAME=symbols-sc4

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

MODELS_PY="$(
  cat <<'PY'
class Order:
    pass


class Customer:
    pass


class Item:
    pass
PY
)"

# The change: one class appended (the file's size and mtime both move).
MODELS_CHANGED_PY="${MODELS_PY}

$(
  cat <<'PY'

class Invoice:
    pass
PY
)"

ORDERS_PY="$(
  cat <<'PY'
from app.models import Order, Customer, Item


def place():
    return Order(), Customer(), Item()
PY
)"

BILLING_PY="$(
  cat <<'PY'
from .models import Order, Customer


def bill():
    return Order(), Customer()
PY
)"

REPORT_PY="$(
  cat <<'PY'
from app.models import Item


def report():
    return Item()
PY
)"

MAIN_PY="$(
  cat <<'PY'
from app.orders import place


def main():
    return place()
PY
)"

NOTES_PY="$(
  cat <<'PY'
"""from app.models import Order is prose here."""
import os

# from app.models import Customer
TEXT = "import app.models"
PY
)"

# The dependents of app/models.py, ranked by hand: path depth via-or-names (names comma-separated).
RANKED=(
  "app/orders.py 1 Order,Customer,Item"
  "app/billing.py 1 Order,Customer"
  "app/report.py 1 Item"
  "app/main.py 2 app/orders.py"
)

# new_dependents_cell NAME STYLE — the package, a first call to build the cache, then the change.
new_dependents_cell() {
  new_cell "$1" "$2"
  put app/__init__.py ""
  put app/models.py "$MODELS_PY"
  put app/orders.py "$ORDERS_PY"
  put app/billing.py "$BILLING_PY"
  put app/report.py "$REPORT_PY"
  put app/main.py "$MAIN_PY"
  put app/notes.py "$NOTES_PY"
  in_session "$2" "symbols dependents app/models.py --json"
  expect_status 0
  put app/models.py "$MODELS_CHANGED_PY"
  bump app/models.py || flunk "could not move app/models.py's mtime"
}

# The verdict's cache clause after the change: one file changed (models.py), none removed.
STALE_1='cache stale: 1 files? changed, 0 removed; rebuilt'

# ── checks ────────────────────────────────────────────────────────────────────────────────────

# check_dependents_json STYLE — exactly the four importers, ranked, after the change.
check_dependents_json() {
  new_dependents_cell json "$1"
  in_session "$1" "symbols dependents app/models.py --json"
  expect_status 0
  local want
  want="$(printf '"%s",' "${RANKED[@]}")"
  jpy "want = [w.split() for w in [${want}]]
deps = g('dependents', []) or []
print('order=' + json.dumps(['%s %s' % (rel(x.get('path')), x.get('depth')) for x in deps]))
problems = []
for i, w in enumerate(want):
    if i >= len(deps):
        break
    x = deps[i]
    if w[1] == '2':
        via = x.get('via')
        via = [rel(v) for v in via] if isinstance(via, list) else [rel(via)]
        if via != [w[2]]:
            problems.append('%s via: want %s, got %r' % (w[0], w[2], x.get('via')))
    else:
        names = x.get('names')
        exp = sorted(w[2].split(','))
        if isinstance(names, list):
            if sorted(names) != exp:
                problems.append('%s names: want %s, got %r' % (w[0], exp, names))
        elif names != len(exp):
            problems.append('%s names: want %s (%d), got %r' % (w[0], exp, len(exp), names))
print('problems=' + json.dumps(problems))
print('verdict=' + str(g('verdict')))"
  expect_j order "[$(for w in "${RANKED[@]}"; do read -r p d _ <<<"$w"; printf '"%s %s", ' "$p" "$d"; done | sed 's/, $//')]"
  expect_j problems '[]'
  expect_verdict_ends "the verdict" "$(jval verdict)" "$STALE_1"
}

# check_dependents_text STYLE — the text view: four lines, direct ones first, in the stated order.
check_dependents_text() {
  new_dependents_cell text "$1"
  in_session "$1" "symbols dependents app/models.py --text"
  expect_status 0
  [[ "${lines[0]:-}" == "symbols: "* ]] || flunk "the first line is not the header"
  local verdict
  verdict="$(text_line "verdict: ")"
  expect_has "the verdict" "$verdict" "4 files import app/models.py"
  expect_verdict_ends "the verdict" "$verdict" "$STALE_1"
  body_lines
  ((${#BODY[@]} == ${#RANKED[@]})) || flunk "${#BODY[@]} body lines, want ${#RANKED[@]} (one per dependent)"
  local i p d mark
  for i in "${!RANKED[@]}"; do
    read -r p d _ <<<"${RANKED[$i]}"
    mark=direct
    [[ "$d" == 2 ]] && mark=indirect
    [[ "${BODY[$i]}" =~ ^([^[:space:]]+)[[:space:]]+([a-z]+) ]] || flunk "body line $((i + 1)) is not 'PATH direct|indirect …': ${BODY[$i]}"
    [[ "${BASH_REMATCH[1]} ${BASH_REMATCH[2]}" == "${p} ${mark}" ]] ||
      flunk "body line $((i + 1)): want ${p} ${mark}, got: ${BODY[$i]}"
  done
}

@test "SC-4 [bash -c, notty] A dependents lookup for a changed file returns the files that import it, ranked — JSON: three direct by names imported, then one indirect via its importer" { check_dependents_json c; }
@test "SC-4 [bash -lc, notty] A dependents lookup for a changed file returns the files that import it, ranked — JSON: three direct by names imported, then one indirect via its importer" { check_dependents_json lc; }
@test "SC-4 [bash -c, notty] A dependents lookup for a changed file returns the files that import it, ranked — text: four lines, direct first, in the stated order" { check_dependents_text c; }
@test "SC-4 [bash -lc, notty] A dependents lookup for a changed file returns the files that import it, ranked — text: four lines, direct first, in the stated order" { check_dependents_text lc; }
