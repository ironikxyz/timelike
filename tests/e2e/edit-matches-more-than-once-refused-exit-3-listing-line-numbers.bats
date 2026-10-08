#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# SC-3 — "Text that matches more than once is refused with exit 3, listing each match's line number".
# The file's hash is unchanged. (Feature 008, slice 0; spec FR-4, FR-11; tasks.md T005;
# contracts/edit-cli.md § Outcomes: More than one match; research R2, R8.)
#
# Written from the contract before the tool existed. Every expected value is the test's own (P004):
#   - the file is built by the container's printf (P005); the line numbers of `return x` are the
#     fixture's own, read by `grep -n -F` before the edit (2, 7 and 12), never the tool's;
#   - "unchanged" is the file's sha256sum, in the container, before and after, never `edit`'s word.
# The refusal is an outcome on stdout (FR-11), so stderr stays empty; nothing is left in the directory.
#
# Isolation: every cell creates its own directory and file, named after the check, the style and the
# terminal mode; `mkdir` without -p refuses a path that exists, so no cell can reuse another's fixture.
# Cells: bash -c and bash -lc, `notty` (JSON is the default when stdout is not a terminal).

load helpers

setup_file() {
  stamp_check
  EDIT_DIR="$(container_tmpdir edit-sc3)"
  export EDIT_DIR
}

teardown_file() {
  container_rm "${EDIT_DIR:-}"
}

# ── helpers (this file's own; the 008 files repeat them so each reads alone) ─────────────────────

# new_cell NAME STYLE TTY — this cell's own paths, created now. Sets:
#   CELL   a directory that holds only the file under edit
#   FILE   the file's name, relative to CELL (edit is run from CELL, so FILE is printed as given)
#   CELL.want, CELL.stderr, CELL.scratch beside it
new_cell() {
  CELL="${EDIT_DIR}/$1-$2-$3"
  FILE="$1-$2-$3.py"
  exec_plain mkdir "$CELL" "${CELL}.scratch" || { echo "cell path ${CELL} exists: cells must not share a fixture" >&2; return 1; }
}

# put PATH FORMAT — write FORMAT with the container's printf (P005). \r, \n and \t in FORMAT are
# escapes; FORMAT carries no % directive.
put() {
  [[ "$2" != *%* ]] || { echo "put: FORMAT carries a %" >&2; return 1; }
  exec_plain sh -c 'printf "$2" >"$1"' put "$1" "$2"
}

# sha PATH — sha256sum in the container, the hash alone.
sha() {
  local out
  out="$(exec_plain sha256sum "$1")" || { echo "sha256sum $1 failed" >&2; return 1; }
  printf '%s' "${out%% *}"
}

# in_cell STYLE CMD — run CMD from CELL as the agent would, with this cell's session scratch; stderr
# goes to CELL.stderr so stdout stays one JSON document.
in_cell() {
  run_in -e "TIMELIKE_SCRATCH_ROOT=${CELL}.scratch" -e "TIMELIKE_SESSION=edit-e2e" "$1" notty \
    "cd '${CELL}' && { $2; } 2>'${CELL}.stderr'"
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

no_stderr() {
  [[ -z "$(exec_plain cat "${CELL}.stderr")" ]] || flunk "an outcome is a result on stdout, but stderr is not empty"
}

# expect_sha WHAT GOT WANT
expect_sha() {
  [[ -n "$2" && "$2" == "$3" ]] || flunk "$1: sha256 ${2:-<none>}, want ${3:-<none>}"
}

# only_file — the cell directory holds the file under edit and nothing else (no temporary file left).
only_file() {
  local got
  got="$(exec_plain ls -A "$CELL")" || flunk "cannot list ${CELL}"
  [[ "$got" == "$FILE" ]] || flunk "the directory holds more than ${FILE}: $(printf '%s' "$got" | tr '\n' ' ')"
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

# same_text WHAT EXPECTED GOT — equal, or fail naming the first line that differs.
same_text() {
  [[ "$2" == "$3" ]] && return 0
  local -a e g
  local i
  mapfile -t e <<<"$2"
  mapfile -t g <<<"$3"
  for ((i = 0; i < ${#e[@]} || i < ${#g[@]}; i++)); do
    if [[ "${e[i]-<none>}" != "${g[i]-<none>}" ]]; then
      flunk "$1: ${#g[@]} lines, want ${#e[@]}; first difference at line $((i + 1)): want '${e[i]-<none>}', got '${g[i]-<none>}'"
      return 1
    fi
  done
  flunk "$1 differs"
}

# numbered PATH A B [MA MB] — lines A..B of PATH as `view` numbers them: the number right-aligned to the
# width of the file's line count, `>` on lines MA..MB and a space elsewhere, one space, the text (a
# trailing CR is not shown). Formatted by awk from the file itself.
numbered() {
  exec_plain awk -v a="$2" -v b="$3" -v ma="${4:-0}" -v mb="${5:-0}" '
    NR == FNR { n++; next }
    FNR == 1 { w = length(n "") }
    { sub(/\r$/, "") }
    FNR >= a && FNR <= b { printf "%" w "d%s %s\n", FNR, (FNR >= ma && FNR <= mb ? ">" : " "), $0 }' "$1" "$1"
}

# ── the fixture ────────────────────────────────────────────────────────────────────────────────

# 12 lines, LF. `return x` occurs three times, on lines 2, 7 and 12.
ORIG='def a(x):\n    return x\n\n\ndef b(x):\n    log(x)\n    return x\n\n\ndef c(x):\n    x = x + 2\n    return x\n'
EDIT_ARGS="--old 'return x' --new 'return x + 1'"

# make_fixture NAME STYLE TTY — a fresh cell; checks the fixture's own facts (P004). Sets SHA_ORIG.
make_fixture() {
  new_cell "$1" "$2" "$3"
  put "${CELL}/${FILE}" "$ORIG"
  local at
  at="$(exec_plain sh -c 'grep -n -F "return x" "$1" | cut -d: -f1 | tr "\n" " "' n "${CELL}/${FILE}")" || true
  [[ "$at" == "2 7 12 " ]] || { echo "fixture: 'return x' should be on lines 2, 7 and 12; grep -n: '${at}'" >&2; return 1; }
  SHA_ORIG="$(sha "${CELL}/${FILE}")"
  [[ -n "$SHA_ORIG" ]]
}

# unchanged — the file's sha256sum is the one taken before the edit, and nothing else is in the directory.
unchanged() {
  expect_sha "the file after a refused edit" "$(sha "${CELL}/${FILE}")" "$SHA_ORIG"
  only_file
}

# ── checks ────────────────────────────────────────────────────────────────────────────────────

VERDICT="--old matches 3 times (matched exactly), at lines 2, 7, 12; nothing written"
REMEDY_PREFIX="add lines of context to --old"

# check_json STYLE — JSON: exit 3, scope `ambiguous`, every match's line (2, 7, 12) in `matches`, the
# level, the verdict and a remedy; the file's hash unchanged.
check_json() {
  make_fixture sc3-json "$1" notty
  in_cell "$1" "edit ${FILE} ${EDIT_ARGS}"
  expect_status 3
  unchanged
  no_stderr

  jfields exit scope level verdict remedy
  expect_j exit 3
  expect_j scope ambiguous
  expect_j level exact
  expect_j verdict "$VERDICT"
  [[ "$(jval remedy)" == "${REMEDY_PREFIX}"* ]] || flunk "remedy: $(jval remedy)"
  jpy "m = g('matches', [])
print('starts=' + ' '.join(str(x.get('start')) for x in m))
print('ends=' + ' '.join(str(x.get('end')) for x in m))"
  expect_j starts "2 7 12"
  expect_j ends "2 7 12"
}

# check_text STYLE — --text: the header with scope `ambiguous`, the verdict listing 2, 7 and 12, and
# `do instead:` saying to add context and how to view the first; the file's hash unchanged.
check_text() {
  make_fixture sc3-text "$1" notty
  in_cell "$1" "edit ${FILE} ${EDIT_ARGS} --text"
  expect_status 3
  unchanged
  no_stderr

  [[ "${lines[0]:-}" == "edit: ${FILE} [ambiguous]" ]] || flunk "header line: ${lines[0]:-<none>}"
  [[ "${lines[1]:-}" == "verdict: ${VERDICT}" ]] || flunk "verdict line: ${lines[1]:-<none>}"
  local line found=0
  for line in "${lines[@]:2}"; do
    [[ "$line" == "do instead: ${REMEDY_PREFIX}"*"view ${FILE}:2 "* ]] && found=1
  done
  ((found == 1)) || flunk "no line 'do instead: ${REMEDY_PREFIX} … view ${FILE}:2 …'"
}

@test "SC-3 [bash -c, notty] Text that matches more than once is refused with exit 3, listing each match's line number — JSON: matches at 2, 7, 12; file sha256 unchanged" { check_json c; }
@test "SC-3 [bash -lc, notty] Text that matches more than once is refused with exit 3, listing each match's line number — JSON: matches at 2, 7, 12; file sha256 unchanged" { check_json lc; }
@test "SC-3 [bash -c, notty] Text that matches more than once is refused with exit 3, listing each match's line number — text: verdict lists 2, 7, 12 and do instead adds context; file sha256 unchanged" { check_text c; }
@test "SC-3 [bash -lc, notty] Text that matches more than once is refused with exit 3, listing each match's line number — text: verdict lists 2, 7, 12 and do instead adds context; file sha256 unchanged" { check_text lc; }
