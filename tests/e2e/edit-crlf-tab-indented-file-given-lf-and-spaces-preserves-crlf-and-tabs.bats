#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# SC-2 — "Replacing text in a CRLF file whose indentation is tabs, given the text with LF endings and
# spaces, succeeds and preserves CRLF endings and tabs". (Feature 008, slice 0; spec FR-3, FR-6, FR-7;
# tasks.md T005; contracts/edit-cli.md § Outcomes: Edited; research R2, R3, R8; the D6 demo's file.)
#
# Written from the contract before the tool existed. Every expected value is the test's own (P004):
#   - the CRLF, tab-indented original and the expected result (CRLF, tabs, at the same levels) are both
#     built by the container's printf with explicit \r\n and \t (P005), never by `edit`;
#   - success is the file's sha256sum, in the container, equal to the expected file's; `edit`'s JSON
#     (level, mapping, line ending, hashes) is ALSO checked, its hashes against sha256sum;
#   - the fixture's own facts first: every line ends in CRLF, and no line starts with a space.
# The text is passed as the agent passes it, in bash's $'…' quoting, with LF and four spaces per level.
#
# Two checks per style:
#   1. the criterion as stated: LF and spaces given, matched at level 3 (indentation; mapping 4 spaces =
#      1 tab), written back with CRLF and tabs (R3: replaced whole lines, the region's last CRLF kept);
#   2. the line-ending axis alone: LF and tabs given, matched at level 2, written back with CRLF.
#
# Contract ambiguity settled here: the level-3 verdict is written two ways in the contract
# (`… indentation (4 spaces = 1 tab)` in the level list, `… indentation: 4 spaces = 1 tab` in the
# example); the test asserts the range, the phrase `matched ignoring line endings and indentation` and
# `4 spaces = 1 tab`, not the punctuation between them.
#
# Isolation: every cell creates its own directory and file, named after the check, the style and the
# terminal mode; `mkdir` without -p refuses a path that exists, so no cell can reuse another's fixture.
# Cells: bash -c and bash -lc, `notty` (JSON is the default when stdout is not a terminal).

load helpers

setup_file() {
  stamp_check
  EDIT_DIR="$(container_tmpdir edit-sc2)"
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

# 10 lines, every one ending CRLF, indented with tabs. Lines 7-8 are `\t\tif x:` and `\t\t\treturn x`.
ORIG='class App:\r\n\tdef load(self):\r\n\t\treturn read("APP")\r\n\r\n\tdef run(self):\r\n\t\tx = self.load()\r\n\t\tif x:\r\n\t\t\treturn x\r\n\t\tlog("none")\r\n\t\treturn None\r\n'
# The same file with lines 7-8 replaced, written out in the file's conventions: CRLF, tabs, same levels.
WANT='class App:\r\n\tdef load(self):\r\n\t\treturn read("APP")\r\n\r\n\tdef run(self):\r\n\t\tx = self.load()\r\n\t\tif x is not None:\r\n\t\t\treturn x + 1\r\n\t\tlog("none")\r\n\t\treturn None\r\n'

# The agent's text, in bash $'…' quoting as it reaches the container's shell: LF endings, 4 spaces per
# level (check 1), or LF endings and tabs (check 2).
SPACES_ARGS="--old \$'        if x:\\n            return x' --new \$'        if x is not None:\\n            return x + 1'"
TABS_ARGS="--old \$'\\t\\tif x:\\n\\t\\t\\treturn x' --new \$'\\t\\tif x is not None:\\n\\t\\t\\treturn x + 1'"

# make_fixture NAME STYLE TTY — a fresh cell: the CRLF, tab-indented original, the expected bytes, and
# the fixture's own facts checked (P004). Sets SHA_ORIG and SHA_WANT.
make_fixture() {
  new_cell "$1" "$2" "$3"
  put "${CELL}/${FILE}" "$ORIG"
  put "${CELL}.want" "$WANT"
  local f facts
  for f in "${CELL}/${FILE}" "${CELL}.want"; do
    # lines, lines ending in CR, lines starting with a space, lines starting with a tab
    facts="$(exec_plain sh -c 'printf "%s %s %s %s" "$(wc -l <"$1")" "$(grep -c "$(printf "\r")\$" "$1")" "$(grep -c "^ " "$1")" "$(grep -c "$(printf "^\t")" "$1")"' n "$f")" || true
    [[ "$facts" == "10 10 0 8" ]] || { echo "fixture ${f}: lines, CRLF lines, space-indented, tab-indented = '${facts}', want '10 10 0 8'" >&2; return 1; }
  done
  SHA_ORIG="$(sha "${CELL}/${FILE}")"
  SHA_WANT="$(sha "${CELL}.want")"
  [[ -n "$SHA_ORIG" && -n "$SHA_WANT" && "$SHA_ORIG" != "$SHA_WANT" ]] || { echo "fixture: original and expected hashes" >&2; return 1; }
}

# ── checks ────────────────────────────────────────────────────────────────────────────────────

# check_spaces STYLE — the criterion: LF and four spaces given; exit 0; the file's bytes are exactly the
# expected CRLF, tab-indented bytes (sha256sum); JSON names level 3 and its mapping, CRLF as the ending
# given to the new text, lines 7-8, and hashes that agree with sha256sum.
check_spaces() {
  make_fixture sc2-spaces "$1" notty
  in_cell "$1" "edit ${FILE} ${SPACES_ARGS}"
  expect_status 0
  expect_sha "the file after the edit (CRLF and tabs kept)" "$(sha "${CELL}/${FILE}")" "$SHA_WANT"
  only_file

  jfields exit start end total match_start match_end level mapping line_ending changed sha256_before sha256_after verdict
  expect_j exit 0
  expect_j level indentation
  expect_j mapping '{"agent": "4 spaces", "file": "1 tab"}'
  expect_j line_ending CRLF
  expect_j start 7
  expect_j end 8
  expect_j total 10
  expect_j match_start 7
  expect_j match_end 8
  expect_j changed true
  expect_j sha256_before "$SHA_ORIG"
  expect_j sha256_after "$SHA_WANT"
  local v
  v="$(jval verdict)"
  [[ "$v" == "edited lines 7-8 of 10 (matched ignoring line endings and indentation"*"4 spaces = 1 tab"* ]] || flunk "verdict: ${v}"
}

# check_tabs STYLE — the line-ending axis alone: LF and tabs given; exit 0, matched at level 2, and the
# file's bytes are exactly the expected CRLF bytes (sha256sum).
check_tabs() {
  make_fixture sc2-tabs "$1" notty
  in_cell "$1" "edit ${FILE} ${TABS_ARGS}"
  expect_status 0
  expect_sha "the file after the edit (CRLF kept)" "$(sha "${CELL}/${FILE}")" "$SHA_WANT"
  only_file

  jfields exit start end level mapping line_ending sha256_after verdict
  expect_j exit 0
  expect_j level line_endings
  expect_j mapping null
  expect_j line_ending CRLF
  expect_j start 7
  expect_j end 8
  expect_j sha256_after "$SHA_WANT"
  [[ "$(jval verdict)" == "edited lines 7-8 of 10 (matched ignoring line endings)" ]] || flunk "verdict: $(jval verdict)"
}

@test "SC-2 [bash -c, notty] Replacing text in a CRLF file whose indentation is tabs, given the text with LF endings and spaces, succeeds and preserves CRLF endings and tabs — file sha256 equals the expected CRLF, tab-indented bytes; level indentation, 4 spaces = 1 tab" { check_spaces c; }
@test "SC-2 [bash -lc, notty] Replacing text in a CRLF file whose indentation is tabs, given the text with LF endings and spaces, succeeds and preserves CRLF endings and tabs — file sha256 equals the expected CRLF, tab-indented bytes; level indentation, 4 spaces = 1 tab" { check_spaces lc; }
@test "SC-2 [bash -c, notty] Replacing text in a CRLF file whose indentation is tabs, given the text with LF endings and spaces, succeeds and preserves CRLF endings and tabs — line endings alone: LF and tabs given, file sha256 equals the expected CRLF bytes" { check_tabs c; }
@test "SC-2 [bash -lc, notty] Replacing text in a CRLF file whose indentation is tabs, given the text with LF endings and spaces, succeeds and preserves CRLF endings and tabs — line endings alone: LF and tabs given, file sha256 equals the expected CRLF bytes" { check_tabs lc; }
