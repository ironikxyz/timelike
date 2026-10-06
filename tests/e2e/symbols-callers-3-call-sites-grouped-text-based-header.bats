#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# SC-3 — "A callers lookup on a fixture with exactly 3 call sites returns those 3, grouped by enclosing
# function, with a header stating it is text-based". (Feature 011, slice 1; spec FR-6, Scenario 3;
# tasks.md T002; contracts/symbols-cli.md § callers; research R2, R7.)
#
# Written from the contract before the tool existed. Every expected value is the test's own (P005):
#   - the fixture calls `save` exactly 3 times: twice in `Order.checkout` (`app/orders.py:8` and `:9`;
#     the method spans 5-9) and once in `ship` (`app/cli.py:7`; spans 5-8). `save`'s own definition
#     line, two comments, two strings and a docstring all carry `save(` text and none is a call
#     (comments and strings are excluded for Python, FR-6);
#   - `symbols callers save --json`: `call_sites` are exactly those 3 (path, line, enclosing qual,
#     start, end), `groups` is 2, `precision` is `text-based`, the scope says `3 call sites` and
#     `text-based`, the verdict says `3 call sites of save` and `text-based`;
#   - `symbols callers save --text`: the header line says `text-based`; the body is two group headings
#     (`── Order.checkout (app/orders.py:5-9) ──`, `── ship (app/cli.py:5-8) ──`) with exactly the 3
#     `FILE:LINE` lines, each under its own enclosing function, each showing its call.
#
# Fixtures are written by the container's printf (P005), never by `symbols`. Isolation: each cell has its
# own workspace (a directory holding `.git`) and its own TIMELIKE_SESSION
# (`sy3-<run id>-<check>-<style>`), checked to have no records before the cell starts. teardown_file
# removes the workspaces and this run's session directories (by that prefix) and nothing else.
# Cells: bash -c and bash -lc, `notty`.

load helpers

# This file's session prefix (sessions are `<prefix>-<run id>-<check>-<style>`).
SPREFIX=sy3
SDIR_NAME=symbols-sc3

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

ORDERS_PY="$(
  cat <<'PY'
class Order:
    def save(self):
        return True

    def checkout(self):
        # self.save() in a comment is not a call
        note = "save() in a string is not a call"
        self.save()
        return self.save()


def unrelated():
    return "nothing here calls save() either"
PY
)"

CLI_PY="$(
  cat <<'PY'
"""cli: save() named in a docstring is not a call."""
from app.orders import Order


def ship(order):
    # order.save() commented out
    order.save()
    return order
PY
)"

# The 3 call sites, by hand: FILE:LINE, the enclosing function's qualified name and range, the call.
SITES=(
  "app/orders.py:8 Order.checkout 5 9 self.save()"
  "app/orders.py:9 Order.checkout 5 9 self.save()"
  "app/cli.py:7 ship 5 8 order.save()"
)

new_callers_cell() {
  new_cell "$1" "$2"
  put app/orders.py "$ORDERS_PY"
  put app/cli.py "$CLI_PY"
}

# ── checks ────────────────────────────────────────────────────────────────────────────────────

# check_callers_json STYLE — exactly the 3 call sites, each with its enclosing function.
check_callers_json() {
  new_callers_cell json "$1"
  in_session "$1" "symbols callers save --json"
  expect_status 0
  local want
  want="$(printf '"%s",' "${SITES[@]}")"
  jpy "want = sorted(' '.join(w.split()[:4]) for w in [${want}])
got = []
for c in g('call_sites', []) or []:
    e = c.get('enclosing') or {}
    got.append('%s:%s %s %s %s' % (rel(c.get('path')), c.get('line'), e.get('qual'), e.get('start'), e.get('end')))
got.sort()
print('sites_ok=' + json.dumps(got == want))
print('sites=' + json.dumps(got))
print('groups=' + json.dumps(g('groups')))
print('precision=' + str(g('precision')))
print('scope=' + str(g('scope')))
print('verdict=' + str(g('verdict')))"
  [[ "$(jval sites_ok)" == true ]] || flunk "call_sites: want ${SITES[*]}; got $(jval sites)"
  expect_j groups 2
  expect_j precision text-based
  expect_has "the scope" "$(jval scope)" "3 call sites" "text-based"
  expect_has "the verdict" "$(jval verdict)" "3 call sites of save" "text-based"
}

# check_callers_text STYLE — the text view: text-based header, two groups, each site under its own.
check_callers_text() {
  new_callers_cell text "$1"
  in_session "$1" "symbols callers save --text"
  expect_status 0
  [[ "${lines[0]:-}" == "symbols: save "* ]] || flunk "the first line is not the header for save"
  expect_has "the header" "${lines[0]}" "text-based"
  body_lines
  local line group="" headings=0 site
  local -a got=()
  for line in "${BODY[@]}"; do
    if [[ "$line" == "──"* ]]; then
      group="$line"
      headings=$((headings + 1))
    elif [[ "$line" =~ ^([^[:space:]]+:[0-9]+)[[:space:]]+(.*)$ ]]; then
      got+=("${BASH_REMATCH[1]}|${BASH_REMATCH[2]}|${group}")
    else
      flunk "a body line that is neither a group heading nor FILE:LINE: ${line}"
    fi
  done
  ((headings == 2)) || flunk "${headings} group headings, want 2"
  ((${#got[@]} == ${#SITES[@]})) || flunk "${#got[@]} call-site lines, want ${#SITES[@]}"
  local w loc qual start end call found
  for w in "${SITES[@]}"; do
    read -r loc qual start end call <<<"$w"
    found=0
    for site in "${got[@]}"; do
      [[ "$site" == "${loc}|"* ]] || continue
      found=1
      [[ "$site" == *"${call}"*"|"* ]] || flunk "${loc} does not show its call ${call}: ${site}"
      [[ "${site##*|}" == *"${qual} (${loc%%:*}:${start}-${end})"* ]] ||
        flunk "${loc} is not under ${qual} (${loc%%:*}:${start}-${end}): its heading is '${site##*|}'"
    done
    ((found)) || flunk "the call site ${loc} is missing"
  done
}

@test "SC-3 [bash -c, notty] A callers lookup on a fixture with exactly 3 call sites returns those 3, grouped by enclosing function, with a header stating it is text-based — JSON: call_sites, enclosing, groups, precision" { check_callers_json c; }
@test "SC-3 [bash -lc, notty] A callers lookup on a fixture with exactly 3 call sites returns those 3, grouped by enclosing function, with a header stating it is text-based — JSON: call_sites, enclosing, groups, precision" { check_callers_json lc; }
@test "SC-3 [bash -c, notty] A callers lookup on a fixture with exactly 3 call sites returns those 3, grouped by enclosing function, with a header stating it is text-based — text: two group headings, each site under its own" { check_callers_text c; }
@test "SC-3 [bash -lc, notty] A callers lookup on a fixture with exactly 3 call sites returns those 3, grouped by enclosing function, with a header stating it is text-based — text: two group headings, each site under its own" { check_callers_text lc; }
