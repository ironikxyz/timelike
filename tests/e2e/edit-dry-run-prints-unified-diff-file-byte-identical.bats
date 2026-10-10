#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# SC-5 — "A dry run prints the unified diff and leaves the file byte-identical". The hash is unchanged,
# and the diff equals one the test computes itself. (Feature 008, slice 0; spec FR-9; tasks.md T005;
# contracts/edit-cli.md § Outcomes: Dry run, as amended: the diff is the body, JSON `lines`, and line
# endings are not shown in it; research R8.)
#
# Written from the contract before the tool existed. Every expected value is the test's own (P004):
#   - the original and the bytes the edit would produce are both built by the container's printf
#     (P005), never by `edit`;
#   - the expected diff is GNU `diff -u` in the container (a different engine from the tool's difflib),
#     with `--label a/FILE --label b/FILE`, so its header lines are exactly the contract's
#     `--- a/FILE` / `+++ b/FILE`, and 3 lines of context (-u's default, and the contract's). The
#     contract's diff is over the lines' text without their endings, so for the CRLF file both sides are
#     CR-stripped copies (`tr -d '\r'`) before diffing;
#   - "byte-identical" is the file's sha256sum, in the container, before and after, never `edit`'s word
#     (its `sha256_before` is ALSO checked, against sha256sum).
#
# Two checks per style:
#   1. an LF file, exact match: the whole diff (headers and hunks) equals the test's, in JSON `lines` and
#      in --text after the verdict;
#   2. a CRLF, tab-indented file given LF and spaces (level 3): the diff equals the test's over the
#      CR-stripped text, the verdict claims no line-ending change (none is made: CRLF is kept), and the
#      file is byte-identical.
#
# Isolation: every cell creates its own directory and file, named after the check, the style and the
# terminal mode; `mkdir` without -p refuses a path that exists, so no cell can reuse another's fixture.
# Cells: bash -c and bash -lc, `notty` (JSON is the default when stdout is not a terminal).

load helpers

setup_file() {
  stamp_check
  EDIT_DIR="$(container_tmpdir edit-sc5)"
  export EDIT_DIR
  # Since slice 1 a .py fixture's verdict carries `syntax: ok (python V compile)` (contracts/edit-cli.md
  # § Slice 1): V is read by the test from timelike's interpreter (edit's own), as the SC-8 file reads it.
  PYVER="$(exec_plain "$AGENT_PY" -I -c 'import platform; print(platform.python_version())')"
  PYVER="${PYVER//$'\r'/}"
  [[ "$PYVER" =~ ^3\.[0-9]+\.[0-9]+$ ]] || { echo "cannot read timelike's Python version: '${PYVER}'" >&2; return 1; }
  export PYVER
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

# ── the fixtures ───────────────────────────────────────────────────────────────────────────────

# 17 lines, LF, four-space indentation; lines 10-11 are `if x:` / `return x`, unique.
LF_ORIG='import os\n\n\nclass App:\n    def load(self):\n        return os.environ.get("APP")\n\n    def run(self):\n        x = self.load()\n        if x:\n            return x\n        log("none")\n        return None\n\n\ndef log(msg):\n    print(msg)\n'
LF_WANT='import os\n\n\nclass App:\n    def load(self):\n        return os.environ.get("APP")\n\n    def run(self):\n        x = self.load()\n        if x is not None:\n            return x + 1\n        log("none")\n        return None\n\n\ndef log(msg):\n    print(msg)\n'
# 10 lines, CRLF, tabs; lines 7-8 are `\t\tif x:` / `\t\t\treturn x`.
CRLF_ORIG='class App:\r\n\tdef load(self):\r\n\t\treturn read("APP")\r\n\r\n\tdef run(self):\r\n\t\tx = self.load()\r\n\t\tif x:\r\n\t\t\treturn x\r\n\t\tlog("none")\r\n\t\treturn None\r\n'
CRLF_WANT='class App:\r\n\tdef load(self):\r\n\t\treturn read("APP")\r\n\r\n\tdef run(self):\r\n\t\tx = self.load()\r\n\t\tif x is not None:\r\n\t\t\treturn x + 1\r\n\t\tlog("none")\r\n\t\treturn None\r\n'
# The agent's text: four spaces per level, LF, in bash $'…' quoting. Exact against the LF file (8 and 12
# spaces), level 3 against the tab file.
SPACES_ARGS="--old \$'        if x:\\n            return x' --new \$'        if x is not None:\\n            return x + 1'"

# make_fixture NAME STYLE TTY ORIG WANT — a fresh cell: the original, the bytes the edit would write,
# and the expected diff (CELL.diff), computed by `diff -u` over CR-stripped copies. Sets SHA_ORIG.
make_fixture() {
  new_cell "$1" "$2" "$3"
  put "${CELL}/${FILE}" "$4"
  put "${CELL}.want" "$5"
  SHA_ORIG="$(sha "${CELL}/${FILE}")"
  [[ -n "$SHA_ORIG" && "$SHA_ORIG" != "$(sha "${CELL}.want")" ]] || { echo "fixture: original and expected hashes" >&2; return 1; }
  # diff exits 1 when the files differ, which they must; 0 or 2 is a broken fixture.
  local rc=0
  exec_plain sh -c 'tr -d "\r" <"$1" >"$3.a" && tr -d "\r" <"$2" >"$3.b" &&
    diff -u --label "a/$4" --label "b/$4" "$3.a" "$3.b" >"$3"' n \
    "${CELL}/${FILE}" "${CELL}.want" "${CELL}.diff" "$FILE" || rc=$?
  ((rc == 1)) || { echo "fixture: diff -u exited ${rc}, want 1 (the files differ)" >&2; return 1; }
  WANT_DIFF="$(exec_plain cat "${CELL}.diff")"
  [[ "$WANT_DIFF" == "--- a/${FILE}"$'\n'"+++ b/${FILE}"$'\n''@@ '* ]] || { echo "fixture: expected diff: ${WANT_DIFF}" >&2; return 1; }
}

byte_identical() {
  expect_sha "the file after a dry run (byte-identical)" "$(sha "${CELL}/${FILE}")" "$SHA_ORIG"
  only_file
}

# json_dry_fields — the dry run's data, the hash before against sha256sum, and nothing claimed after.
json_dry_fields() {
  jfields exit dry_run changed sha256_before sha256_after verdict
  expect_j exit 0
  expect_j dry_run true
  expect_j changed false
  expect_j sha256_before "$SHA_ORIG"
  expect_j sha256_after null
}

# ── checks ────────────────────────────────────────────────────────────────────────────────────

# check_lf_json STYLE — LF file, exact: exit 0; JSON `lines` is exactly the test's diff; the verdict;
# the file byte-identical.
check_lf_json() {
  make_fixture sc5-lf-json "$1" notty "$LF_ORIG" "$LF_WANT"
  in_cell "$1" "edit ${FILE} ${SPACES_ARGS} --dry-run"
  expect_status 0
  byte_identical
  no_stderr

  json_dry_fields
  expect_j verdict "dry run: would edit lines 10-11 of 17 (matched exactly); syntax: ok (python ${PYVER} compile); nothing written"
  jpy "print('\n'.join(g('lines', [])))"
  same_text "the diff (JSON lines)" "$WANT_DIFF" "$JPY"
}

# check_lf_text STYLE — LF file, exact, --text: the header, the verdict, then exactly the test's diff.
check_lf_text() {
  make_fixture sc5-lf-text "$1" notty "$LF_ORIG" "$LF_WANT"
  in_cell "$1" "edit ${FILE} ${SPACES_ARGS} --dry-run --text"
  expect_status 0
  byte_identical
  no_stderr

  [[ "${lines[0]:-}" == "edit: ${FILE} ["*"]" ]] || flunk "header line: ${lines[0]:-<none>}"
  [[ "${lines[1]:-}" == "verdict: dry run: would edit lines 10-11 of 17 (matched exactly); syntax: ok (python ${PYVER} compile); nothing written" ]] || flunk "verdict line: ${lines[1]:-<none>}"
  same_text "the diff printed after the verdict" "$WANT_DIFF" "$(printf '%s\n' "${lines[@]:2}")"
}

# check_crlf_json STYLE — CRLF, tab-indented file, LF and spaces given: exit 0; JSON `lines` is the
# test's diff over the CR-stripped text; the verdict names level 3 and no line-ending change; the file
# byte-identical.
check_crlf_json() {
  make_fixture sc5-crlf-json "$1" notty "$CRLF_ORIG" "$CRLF_WANT"
  in_cell "$1" "edit ${FILE} ${SPACES_ARGS} --dry-run"
  expect_status 0
  byte_identical
  no_stderr

  json_dry_fields
  local v
  v="$(jval verdict)"
  [[ "$v" == "dry run: would edit lines 7-8 of 10 (matched ignoring line endings and indentation"*"; nothing written"* ]] || flunk "verdict: ${v}"
  [[ "$v" != *"line endings: "* ]] || flunk "the verdict claims a line-ending change, but CRLF is kept: ${v}"
  jpy "print('\n'.join(g('lines', [])))"
  same_text "the diff (JSON lines, endings not shown)" "$WANT_DIFF" "$JPY"
}

@test "SC-5 [bash -c, notty] A dry run prints the unified diff and leaves the file byte-identical — LF file, JSON: lines equal the test's diff -u; file sha256 unchanged" { check_lf_json c; }
@test "SC-5 [bash -lc, notty] A dry run prints the unified diff and leaves the file byte-identical — LF file, JSON: lines equal the test's diff -u; file sha256 unchanged" { check_lf_json lc; }
@test "SC-5 [bash -c, notty] A dry run prints the unified diff and leaves the file byte-identical — LF file, text: the diff after the verdict equals the test's diff -u; file sha256 unchanged" { check_lf_text c; }
@test "SC-5 [bash -lc, notty] A dry run prints the unified diff and leaves the file byte-identical — LF file, text: the diff after the verdict equals the test's diff -u; file sha256 unchanged" { check_lf_text lc; }
@test "SC-5 [bash -c, notty] A dry run prints the unified diff and leaves the file byte-identical — CRLF tab file, LF and spaces given: lines equal the test's diff over CR-stripped text; file sha256 unchanged" { check_crlf_json c; }
@test "SC-5 [bash -lc, notty] A dry run prints the unified diff and leaves the file byte-identical — CRLF tab file, LF and spaces given: lines equal the test's diff over CR-stripped text; file sha256 unchanged" { check_crlf_json lc; }
