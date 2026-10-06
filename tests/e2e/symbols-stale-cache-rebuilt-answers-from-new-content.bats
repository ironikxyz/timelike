#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# SC-5 — "After a file changes, the next lookup reports the cache as stale, rebuilds it, and answers from
# the new content". (Feature 011, slice 1; spec FR-1, FR-2, Scenario 5; tasks.md T002;
# contracts/symbols-cli.md § (cache state in every verdict); research R1, R7.)
#
# Written from the contract before the tool existed. Every expected value is the test's own (P005):
#   - the workspace holds two files. `app/store.py`'s first version defines `load_items` at line 4 and
#     `fetch_rows` at line 8; `app/other.py` is never touched;
#   - the first `symbols def load_items` says `cache: built (2 files)` and answers `app/store.py:4`; the
#     second says `cache: fresh` (nothing changed, so a stale report later is the change's, not noise);
#   - then `app/store.py` is rewritten: `fetch_rows` renamed `fetch_records` (line 4), `load_items` moved
#     to line 12; its mtime is moved 5 s forward as well;
#   - the next `symbols def load_items` ENDS its verdict with `; cache stale: 1 file(s) changed, 0
#     removed; rebuilt` (the contract: every verdict ends with the cache state, notes before it; under
#     `--json`, also `cache.changed` 1 and `cache.removed` 0: one file changed, none removed), and its
#     only definition is `app/store.py:12`; line 4 is gone;
#   - after it: `symbols def fetch_records` answers `app/store.py:4` with `cache: fresh` (the rebuild
#     was kept), and `symbols def fetch_rows`, the old name, exits 3.
#
# Fixtures are written by the container's printf (P005), never by `symbols`. Isolation: each cell has its
# own workspace (a directory holding `.git`) and its own TIMELIKE_SESSION
# (`sy5-<run id>-<check>-<style>`), checked to have no records before the cell starts. teardown_file
# removes the workspaces and this run's session directories (by that prefix) and nothing else.
# Cells: bash -c and bash -lc, `notty`.

load helpers

# This file's session prefix (sessions are `<prefix>-<run id>-<check>-<style>`).
SPREFIX=sy5
SDIR_NAME=symbols-sc5

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

STORE_V1="$(
  cat <<'PY'
"""Store, first version."""


def load_items(path):
    return [path]


def fetch_rows(n):
    return list(range(n))
PY
)"

STORE_V2="$(
  cat <<'PY'
"""Store, second version: load_items moved down, fetch_rows renamed."""


def fetch_records(n):
    return list(range(n))


def tidy(rows):
    return rows


def load_items(path):
    return [path]
PY
)"

OTHER_PY="$(
  cat <<'PY'
def unrelated():
    return 1
PY
)"

# new_stale_cell NAME STYLE — the two files.
new_stale_cell() {
  new_cell "$1" "$2"
  put app/store.py "$STORE_V1"
  put app/other.py "$OTHER_PY"
}

# change_store — the second version, and the mtime moved forward.
change_store() {
  put app/store.py "$STORE_V2"
  bump app/store.py || flunk "could not move app/store.py's mtime"
}

# jdefs — the last JSON run's definitions as FILE:LINE (JSON list), its verdict and its cache object.
jdefs() {
  jpy "defs = g('definitions', []) or []
print('defs=' + json.dumps(['%s:%s' % (rel(x.get('path')), x.get('line')) for x in defs]))
print('verdict=' + str(g('verdict')))
c = g('cache', {})
c = c if isinstance(c, dict) else {}
print('state=' + str(c.get('state')))
print('changed=' + json.dumps(c.get('changed')))
print('removed=' + json.dumps(c.get('removed')))"
}

# The verdict's cache clause after the change: one file changed (store.py), none removed.
STALE_1='cache stale: 1 files? changed, 0 removed; rebuilt'

# ── checks ────────────────────────────────────────────────────────────────────────────────────

check_stale_json() {
  new_stale_cell json "$1"
  in_session "$1" "symbols def load_items --json"
  expect_status 0
  jdefs
  expect_j defs '["app/store.py:4"]'
  expect_verdict_ends "the first verdict" "$(jval verdict)" "cache: built \\(2 files\\)"
  in_session "$1" "symbols def load_items --json"
  expect_status 0
  jdefs
  expect_verdict_ends "the second verdict (nothing changed)" "$(jval verdict)" "cache: fresh"

  change_store
  in_session "$1" "symbols def load_items --json"
  expect_status 0
  jdefs
  expect_verdict_ends "the verdict after the change" "$(jval verdict)" "$STALE_1"
  expect_has "cache.state after the change" "$(jval state)" "stale"
  expect_j changed 1
  expect_j removed 0
  expect_j defs '["app/store.py:12"]'

  in_session "$1" "symbols def fetch_records --json"
  expect_status 0
  jdefs
  expect_j defs '["app/store.py:4"]'
  expect_verdict_ends "the verdict after the rebuild" "$(jval verdict)" "cache: fresh"
  in_session "$1" "symbols def fetch_rows --json"
  expect_status 3
}

check_stale_text() {
  new_stale_cell text "$1"
  in_session "$1" "symbols def load_items --text"
  expect_status 0
  expect_verdict_ends "the first verdict" "$(text_line "verdict: ")" "cache: built \\(2 files\\)"
  body_lines
  [[ "${BODY[0]:-}" =~ ^app/store\.py:4([^0-9]|$) ]] || flunk "the first answer is not app/store.py:4: ${BODY[0]:-<none>}"

  change_store
  in_session "$1" "symbols def load_items --text"
  expect_status 0
  expect_verdict_ends "the verdict after the change" "$(text_line "verdict: ")" "$STALE_1"
  body_lines
  [[ "${BODY[0]:-}" =~ ^app/store\.py:12([^0-9]|$) ]] || flunk "the first answer is not app/store.py:12: ${BODY[0]:-<none>}"
  local line
  for line in "${BODY[@]}"; do
    [[ ! "$line" =~ ^app/store\.py:4([^0-9]|$) ]] || flunk "the old location app/store.py:4 is still answered: ${line}"
  done

  in_session "$1" "symbols def fetch_records --text"
  expect_status 0
  expect_verdict_ends "the verdict after the rebuild" "$(text_line "verdict: ")" "cache: fresh"
  body_lines
  [[ "${BODY[0]:-}" =~ ^app/store\.py:4([^0-9]|$) ]] || flunk "fetch_records is not answered at app/store.py:4: ${BODY[0]:-<none>}"
  in_session "$1" "symbols def fetch_rows --text"
  expect_status 3
}

@test "SC-5 [bash -c, notty] After a file changes, the next lookup reports the cache as stale, rebuilds it, and answers from the new content — JSON: cache stale, 1 changed, the moved line, the renamed name" { check_stale_json c; }
@test "SC-5 [bash -lc, notty] After a file changes, the next lookup reports the cache as stale, rebuilds it, and answers from the new content — JSON: cache stale, 1 changed, the moved line, the renamed name" { check_stale_json lc; }
@test "SC-5 [bash -c, notty] After a file changes, the next lookup reports the cache as stale, rebuilds it, and answers from the new content — text: stale verdict, the new line first, the old name exits 3" { check_stale_text c; }
@test "SC-5 [bash -lc, notty] After a file changes, the next lookup reports the cache as stale, rebuilds it, and answers from the new content — text: stale verdict, the new line first, the old name exits 3" { check_stale_text lc; }
