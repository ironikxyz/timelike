#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# FR-13 and FR-14 — the name and the manifest. (Feature 009, slice 1; spec FR-13, FR-14; tasks.md T004;
# contracts/journal-cli.md § Manifest; research R6.)
#   - FR-13: `type -a journal` names exactly /opt/timelike/bin/journal, one line. The name is the habit of
#     `journalctl`; this cell keeps the image free of any other `journal` (research R6: Debian's systemd
#     installs none, and the cell decides).
#   - FR-14: `journal --agent-info` declares `mutating: false`, `confirm_protocol: false`,
#     `destructive: false`, `reads_stdin: true` (only `--ledger -`), `probe: []` (the current session),
#     and the exit codes 0, 1, 2 and 3, as the contract fixes them.
#
# The manifest is read in a session of the cell's own (`j5-<run id>-<check>-<style>`; the run id is the
# random suffix of this file's container_tmpdir), so the tool's own session event lands in no other
# cell's records. teardown_file removes this run's session directories (by that prefix) and nothing else.
# Cells: bash -c and bash -lc, `notty`.

load helpers

# This file's session prefix (sessions are `<prefix>-<run id>-<check>-<style>`).
JPREFIX=j5

setup_file() {
  stamp_check
  JDIR="$(container_tmpdir journal-name)"
  RUN_ID="${JDIR##*.}"
  SROOT="$(scratch_root)"
  export JDIR RUN_ID SROOT
}

teardown_file() {
  container_rm "${JDIR:-}"
  rm_sessions "$JPREFIX"
}

# ── helpers (this file's own; the 009 files repeat them so each reads alone) ─────────────────────

# scratch_root — the container's session scratch root, read in the container, never assumed.
scratch_root() {
  local r
  r="$(exec_plain sh -c 'printf "%s" "${TIMELIKE_SCRATCH_ROOT:-/tmp/timelike}"')" || return 1
  [[ "$r" == /?* ]] || { echo "scratch root in the container: '${r}'" >&2; return 1; }
  printf '%s' "$r"
}

# rm_sessions PREFIX — remove this run's session directories (SROOT/PREFIX-RUN_ID-*) and nothing else.
rm_sessions() {
  [[ -n "${RUN_ID:-}" && "${SROOT:-}" == /tmp/?* ]] || return 0
  exec_plain sh -c 'for d in "$1/$2-$3-"*; do [ -d "$d" ] && rm -rf -- "$d"; done; exit 0' \
    rm "$SROOT" "$1" "$RUN_ID" >/dev/null 2>&1 || true
}

# new_cell NAME STYLE — this cell's fixture directory (CELL, with CELL.stderr beside it) and its own
# session (SESSION), which must have no records yet.
new_cell() {
  CELL="${JDIR}/$1-$2"
  SESSION="${JPREFIX}-${RUN_ID}-$1-$2"
  exec_plain mkdir "$CELL" || { echo "cell path ${CELL} exists: cells must not share a fixture" >&2; return 1; }
  if exec_plain test -e "${SROOT}/${SESSION}"; then
    echo "session ${SESSION} already has records: cells must not share a session" >&2
    return 1
  fi
}

# put PATH FORMAT — write FORMAT with the container's printf (P005). FORMAT carries no % directive.
put() {
  [[ "$2" != *%* ]] || { echo "put: FORMAT carries a %" >&2; return 1; }
  exec_plain sh -c 'printf "$2" >"$1"' put "$1" "$2"
}

# in_session [-e K=V]... STYLE CMD — run CMD as the agent would, in this cell's session; stderr goes to
# CELL.stderr so stdout stays one document.
in_session() {
  local -a envs=()
  while [[ "${1:-}" == -e ]]; do
    envs+=(-e "$2")
    shift 2
  done
  run_in -e "TIMELIKE_SESSION=${SESSION}" "${envs[@]}" "$1" notty "$2 2>>'${CELL}.stderr'"
  assert_within 20
}

# timed STYLE CMD — in_session, with the runner-side window around it appended to T_BEFORE / T_AFTER.
timed() {
  local b
  b="$(now_ms)"
  in_session "$1" "$2"
  T_BEFORE+=("$b")
  T_AFTER+=("$(now_ms)")
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
# dotted path, top-level first, then under `data`. Output in $JPY.
jpy() {
  JPY="$(printf '%s' "$output" | pyq "import json,sys
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
$1")" || flunk "stdout is not the JSON expected"
}

# jfields KEY... — KEY=VALUE lines into $JPY (strings raw, everything else as JSON).
jfields() {
  local ks
  ks="$(printf '"%s",' "$@")"
  jpy "for k in [${ks}]:
    v = g(k)
    print(k + '=' + (v if isinstance(v, str) else json.dumps(v, sort_keys=True)))"
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

# ── checks ────────────────────────────────────────────────────────────────────────────────────

# check_type_a STYLE — exactly one `journal` on PATH, and it is timelike's.
check_type_a() {
  run_in "$1" notty "type -a journal"
  assert_within 20
  assert_status 0
  [[ ${#lines[@]} -eq 1 ]] || { printf 'type -a journal printed %d lines, want 1:\n%s\n' "${#lines[@]}" "$output" >&2; return 1; }
  [[ "${lines[0]}" == "journal is /opt/timelike/bin/journal" ]] || { echo "type -a journal: ${lines[0]}" >&2; return 1; }
}

# check_manifest STYLE — the manifest's fields, as the contract fixes them.
check_manifest() {
  new_cell manifest "$1"
  in_session "$1" "journal --agent-info"
  expect_status 0
  jpy "print('tool=' + json.dumps(g('tool')))
print('mutating=' + json.dumps(g('mutating')))
print('confirm_protocol=' + json.dumps(g('confirm_protocol')))
print('destructive=' + json.dumps(g('destructive')))
print('reads_stdin=' + json.dumps(g('reads_stdin')))
print('probe=' + json.dumps(g('probe')))
print('exit_codes=' + json.dumps(sorted(g('exit_codes', {}) or {})))"
  expect_j tool '"journal"'
  expect_j mutating false
  expect_j confirm_protocol false
  expect_j destructive false
  expect_j reads_stdin true
  expect_j probe '[]'
  expect_j exit_codes '["0", "1", "2", "3"]'
}

@test "FR-13 [bash -c, notty] type -a journal names exactly /opt/timelike/bin/journal — one line, no other journal on PATH" { check_type_a c; }
@test "FR-13 [bash -lc, notty] type -a journal names exactly /opt/timelike/bin/journal — one line, no other journal on PATH" { check_type_a lc; }
@test "FR-14 [bash -c, notty] journal --agent-info declares mutating false, confirm_protocol false, reads_stdin true, probe [] — not destructive, exit codes 0-3" { check_manifest c; }
@test "FR-14 [bash -lc, notty] journal --agent-info declares mutating false, confirm_protocol false, reads_stdin true, probe [] — not destructive, exit codes 0-3" { check_manifest lc; }
