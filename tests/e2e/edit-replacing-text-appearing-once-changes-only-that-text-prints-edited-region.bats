#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# SC-1 — "Replacing text that appears exactly once changes only that text and prints the edited region
# with line numbers". (Feature 008, slice 0; spec FR-3, FR-6, FR-7, FR-8; tasks.md T005;
# contracts/edit-cli.md § Outcomes: Edited; research R8.)
#
# Written from the contract before the tool existed. Every expected value is the test's own (P004):
#   - the original and the expected bytes are both built by the container's printf (P005), never by
#     `edit`; "changes only that text" is the file's sha256sum, in the container, equal to the expected
#     file's, never `edit`'s message or its JSON hashes (those are ALSO checked, against sha256sum);
#   - the region is formatted by awk from the expected file as `view` numbers lines
#     (`{n:>W}{m} {text}`, W = the width of the line count, `>` on a changed line);
#   - the fixture's own facts are checked first: `return x` occurs once, on line 11.
# Atomicity leaves nothing behind: the cell directory holds only the file under edit afterwards.
#
# Isolation: every cell creates its own directory and file, named after the check, the style and the
# terminal mode (`sc1-json-c-notty/sc1-json-c-notty.py`); `mkdir` without -p refuses a path that exists,
# so no cell can reuse another's fixture.
#
# Contract ambiguity settled here: for a one-line edit the verdict may read `edited lines 11-11 of 17`
# or `edited line 11 of 17`; both are accepted. The header's scope is not asserted (the contract's
# example header range, 41-43, is neither the shown region nor the edited lines); its prefix is.
# Cells: bash -c and bash -lc, `notty` (JSON is the default when stdout is not a terminal).

load helpers

setup_file() {
  stamp_check
  EDIT_DIR="$(container_tmpdir edit-sc1)"
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

# ── the fixture ────────────────────────────────────────────────────────────────────────────────

# 17 lines, LF, four-space indentation. `return x` occurs once, on line 11.
ORIG='import os\n\n\nclass App:\n    def load(self):\n        return os.environ.get("APP")\n\n    def run(self):\n        x = self.load()\n        if x:\n            return x\n        log("none")\n        return None\n\n\ndef log(msg):\n    print(msg)\n'
# The same 17 lines, line 11 reading `return x + 1`: written out, not derived from the tool.
WANT='import os\n\n\nclass App:\n    def load(self):\n        return os.environ.get("APP")\n\n    def run(self):\n        x = self.load()\n        if x:\n            return x + 1\n        log("none")\n        return None\n\n\ndef log(msg):\n    print(msg)\n'
EDIT_ARGS="--old 'return x' --new 'return x + 1'"
# verdict_re — sets VERDICT_RE: the match, then the syntax part a .py fixture's verdict ends with since
# slice 1, anchored at both ends. Built in the cell, where setup_file's PYVER is set.
verdict_re() {
  VERDICT_RE="^edited lines? 11(-11)? of 17 \\(matched exactly\\); syntax: ok \\(python ${PYVER//./\\.} compile\\)\$"
}

# make_fixture NAME STYLE TTY — a fresh cell: the original file, the expected bytes, and the fixture's
# own facts checked (P004). Sets SHA_ORIG and SHA_WANT.
make_fixture() {
  new_cell "$1" "$2" "$3"
  put "${CELL}/${FILE}" "$ORIG"
  put "${CELL}.want" "$WANT"
  local hits
  hits="$(exec_plain grep -n -F 'return x' "${CELL}/${FILE}")" || true
  [[ "$hits" == "11:            return x" ]] || { echo "fixture: 'return x' should occur once, on line 11; grep -n: ${hits}" >&2; return 1; }
  [[ "$(exec_plain sh -c 'wc -l <"$1"' n "${CELL}/${FILE}")" == 17 ]] || { echo "fixture: not 17 lines" >&2; return 1; }
  SHA_ORIG="$(sha "${CELL}/${FILE}")"
  SHA_WANT="$(sha "${CELL}.want")"
  [[ -n "$SHA_ORIG" && -n "$SHA_WANT" && "$SHA_ORIG" != "$SHA_WANT" ]] || { echo "fixture: original and expected hashes" >&2; return 1; }
}

# ── checks ────────────────────────────────────────────────────────────────────────────────────

# check_json STYLE — JSON: exit 0; the file's bytes are exactly the expected bytes (sha256sum); the
# JSON says where, at which level, and its hashes agree with sha256sum; `lines` is the edited region
# 8-14 (3 lines of context each side) numbered as view numbers them, line 11 marked.
check_json() {
  make_fixture sc1-json "$1" notty
  in_cell "$1" "edit ${FILE} ${EDIT_ARGS}"
  expect_status 0
  expect_sha "the file after the edit (only that text changed)" "$(sha "${CELL}/${FILE}")" "$SHA_WANT"
  only_file

  jfields exit path start end total match_start match_end level mapping changed sha256_before sha256_after verdict
  expect_j exit 0
  expect_j path "$FILE"
  expect_j start 11
  expect_j end 11
  expect_j total 17
  expect_j match_start 11
  expect_j match_end 11
  expect_j level exact
  expect_j mapping null
  expect_j changed true
  expect_j sha256_before "$SHA_ORIG"
  expect_j sha256_after "$SHA_WANT"
  verdict_re
  [[ "$(jval verdict)" =~ $VERDICT_RE ]] || flunk "verdict: $(jval verdict)"

  local want
  want="$(numbered "${CELL}.want" 8 14 11 11)"
  jpy "print('\n'.join(g('lines', [])))"
  same_text "JSON lines (the edited region)" "$want" "$JPY"
}

# check_text STYLE — --text: the header, the verdict, then the edited region numbered as view numbers
# it and nothing else; the file's bytes are exactly the expected bytes.
check_text() {
  make_fixture sc1-text "$1" notty
  in_cell "$1" "edit ${FILE} ${EDIT_ARGS} --text"
  expect_status 0
  expect_sha "the file after the edit (only that text changed)" "$(sha "${CELL}/${FILE}")" "$SHA_WANT"
  only_file
  no_stderr

  [[ "${lines[0]:-}" == "edit: ${FILE} ["*"]" ]] || flunk "header line: ${lines[0]:-<none>}"
  verdict_re
  [[ "${lines[1]:-}" == "verdict: "* && "${lines[1]#verdict: }" =~ $VERDICT_RE ]] || flunk "verdict line: ${lines[1]:-<none>}"
  local want
  want="$(numbered "${CELL}.want" 8 14 11 11)"
  same_text "the region printed after the verdict" "$want" "$(printf '%s\n' "${lines[@]:2}")"
}

@test "SC-1 [bash -c, notty] Replacing text that appears exactly once changes only that text and prints the edited region with line numbers — JSON: file sha256 equals the expected bytes; region 8-14 numbered, line 11 marked" { check_json c; }
@test "SC-1 [bash -lc, notty] Replacing text that appears exactly once changes only that text and prints the edited region with line numbers — JSON: file sha256 equals the expected bytes; region 8-14 numbered, line 11 marked" { check_json lc; }
@test "SC-1 [bash -c, notty] Replacing text that appears exactly once changes only that text and prints the edited region with line numbers — text: header, verdict and the numbered region; file sha256 equals the expected bytes" { check_text c; }
@test "SC-1 [bash -lc, notty] Replacing text that appears exactly once changes only that text and prints the edited region with line numbers — text: header, verdict and the numbered region; file sha256 equals the expected bytes" { check_text lc; }
