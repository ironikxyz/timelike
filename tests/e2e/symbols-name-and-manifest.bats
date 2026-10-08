#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# FR-8 and FR-9 — the name and the manifest. (Feature 011, slice 1; spec FR-8, FR-9; tasks.md T002;
# contracts/symbols-cli.md § Manifest; research R6.)
#   - FR-8: `type -a symbols` names exactly /opt/timelike/bin/symbols, one line. The cell keeps the
#     image free of any other `symbols` (R6).
#   - FR-8: `symbols --agent-info` declares `mutating: false`, `confirm_protocol: false`,
#     `destructive: false`, `reads_stdin: false`, `probe: ["outline", "/opt/timelike/bin/symbols"]`
#     (its own source); FR-9's exit codes are 0, 1, 2, 3 and 124.
#
# The manifest is read in a session of the cell's own (`sy6-<run id>-<check>-<style>`), in a workspace
# of its own, so the tool's own session event lands in no other cell's records. teardown_file removes
# the workspaces and this run's session directories (by that prefix) and nothing else.
# Cells: bash -c and bash -lc, `notty`.

load helpers

# This file's session prefix (sessions are `<prefix>-<run id>-<check>-<style>`).
SPREFIX=sy6
SDIR_NAME=symbols-name

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

# ── checks ────────────────────────────────────────────────────────────────────────────────────

# check_type_a STYLE — exactly one `symbols` on PATH, and it is timelike's.
check_type_a() {
  run_in "$1" notty "type -a symbols"
  assert_within 20
  assert_status 0
  [[ ${#lines[@]} -eq 1 ]] || { printf 'type -a symbols printed %d lines, want 1:\n%s\n' "${#lines[@]}" "$output" >&2; return 1; }
  [[ "${lines[0]}" == "symbols is /opt/timelike/bin/symbols" ]] || { echo "type -a symbols: ${lines[0]}" >&2; return 1; }
}

# check_manifest STYLE — the manifest's fields, as the contract fixes them.
check_manifest() {
  new_cell manifest "$1"
  in_session "$1" "symbols --agent-info"
  expect_status 0
  jpy "print('tool=' + json.dumps(g('tool')))
print('mutating=' + json.dumps(g('mutating')))
print('confirm_protocol=' + json.dumps(g('confirm_protocol')))
print('destructive=' + json.dumps(g('destructive')))
print('reads_stdin=' + json.dumps(g('reads_stdin')))
print('probe=' + json.dumps(g('probe')))
print('exit_codes=' + json.dumps(sorted(g('exit_codes', {}) or {}, key=int)))"
  expect_j tool '"symbols"'
  expect_j mutating false
  expect_j confirm_protocol false
  expect_j destructive false
  expect_j reads_stdin false
  expect_j probe '["outline", "/opt/timelike/bin/symbols"]'
  expect_j exit_codes '["0", "1", "2", "3", "124"]'
}

@test "FR-8 [bash -c, notty] type -a symbols names exactly /opt/timelike/bin/symbols — one line, no other symbols on PATH" { check_type_a c; }
@test "FR-8 [bash -lc, notty] type -a symbols names exactly /opt/timelike/bin/symbols — one line, no other symbols on PATH" { check_type_a lc; }
@test "FR-8 [bash -c, notty] symbols --agent-info declares mutating false, confirm_protocol false, reads_stdin false, probe [outline, /opt/timelike/bin/symbols] — not destructive, exit codes 0-3 and 124" { check_manifest c; }
@test "FR-8 [bash -lc, notty] symbols --agent-info declares mutating false, confirm_protocol false, reads_stdin false, probe [outline, /opt/timelike/bin/symbols] — not destructive, exit codes 0-3 and 124" { check_manifest lc; }
