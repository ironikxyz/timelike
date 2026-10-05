#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# SC-4 — "Text that matches nowhere is refused with exit 3, showing up to three nearest candidate regions
# with line numbers". The hash is unchanged. (Feature 008, slice 0; spec FR-5, FR-11; tasks.md T005;
# contracts/edit-cli.md § Outcomes: No match; research R4, R8.)
#
# Written from the contract before the tool existed. Every expected value is the test's own (P004):
#   - the file is built by the container's printf (P005). It carries a planted near miss at lines
#     20-22 (`--old` with one word changed on its second line) and, EARLIER in the file, a weaker look-alike
#     at lines 9-11, so "the planted region first" is a ranking, not file order;
#   - the fixture's own facts first: the text of `--old`'s second line occurs nowhere, and lines 20-22
#     are the planted region;
#   - the first candidate's lines are formatted by awk from the file as `view` numbers them;
#   - "unchanged" is the file's sha256sum, in the container, before and after.
# Checked: exit 3; 1 to 3 candidates; the first is lines 20-22; each is as long as `--old` (3 lines), has
# a similarity of at least 0.5, ranked best first, and its lines carry their own line numbers in order.
#
# Contract ambiguity settled here: the first candidate's `difference` is asserted to name line 2 (R4:
# `line N differs`, against --old's numbering), not its exact wording.
#
# Isolation: every cell creates its own directory and file, named after the check, the style and the
# terminal mode; `mkdir` without -p refuses a path that exists, so no cell can reuse another's fixture.
# Cells: bash -c and bash -lc, `notty` (JSON is the default when stdout is not a terminal).

load helpers

setup_file() {
  stamp_check
  EDIT_DIR="$(container_tmpdir edit-sc4)"
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

# 28 lines, LF. Lines 9-11: the weaker look-alike. Lines 20-22: the planted near miss.
ORIG='import sys\n\n\ndef load(path):\n    with open(path) as fh:\n        return fh.read()\n\ndef check(ready, value):\n    if ready:\n        return value\n    log("skip")\n\n\ndef parse(text):\n    parts = text.split(",")\n    return [p.strip() for p in parts]\n\n\ndef run(x):\n    if x:\n        return x\n    log("none")\n    return None\n\n\ndef log(msg):\n    print(msg, file=sys.stderr)\n    return None\n'
# --old differs from lines 20-22 only on its line 2 (`return y`).
EDIT_ARGS="--old \$'    if x:\\n        return y\\n    log(\"none\")' --new \$'    if x:\\n        return y + 1\\n    log(\"none\")'"
PLANTED_START=20
PLANTED_END=22

# make_fixture NAME STYLE TTY — a fresh cell; checks the fixture's own facts (P004). Sets SHA_ORIG.
make_fixture() {
  new_cell "$1" "$2" "$3"
  put "${CELL}/${FILE}" "$ORIG"
  local facts
  facts="$(exec_plain sh -c 'printf "%s|%s|" "$(wc -l <"$1")" "$(grep -c -F "return y" "$1")"; sed -n 20,22p "$1" | tr "\n" "|"' n "${CELL}/${FILE}")" || true
  [[ "$facts" == '28|0|    if x:|        return x|    log("none")|' ]] || { echo "fixture facts: '${facts}'" >&2; return 1; }
  SHA_ORIG="$(sha "${CELL}/${FILE}")"
  [[ -n "$SHA_ORIG" ]]
}

unchanged() {
  expect_sha "the file after a refused edit" "$(sha "${CELL}/${FILE}")" "$SHA_ORIG"
  only_file
}

VERDICT_PREFIX="--old matches nowhere (tried exact, line endings, indentation)"

# ── checks ────────────────────────────────────────────────────────────────────────────────────

# check_json STYLE — JSON: exit 3, scope `no match`; `candidates` holds 1 to 3 regions, the planted one
# first, each 3 lines long, similarity ≥ 0.5 and ranked best first, its `lines` numbered from its start;
# the first candidate's lines are exactly view's numbering of lines 20-22; the file's hash unchanged.
check_json() {
  make_fixture sc4-json "$1" notty
  in_cell "$1" "edit ${FILE} ${EDIT_ARGS}"
  expect_status 3
  unchanged
  no_stderr

  jfields exit scope verdict
  expect_j exit 3
  expect_j scope "no match"
  [[ "$(jval verdict)" == "${VERDICT_PREFIX}"*"nothing written"* ]] || flunk "verdict: $(jval verdict)"

  # One line of findings per rule; the cell fails on the first that is not `ok`.
  jpy "import re
c = g('candidates', None)
def check():
    if not isinstance(c, list) or not 1 <= len(c) <= 3:
        return 'candidates: want a list of 1 to 3, got %r' % (c,)
    prev = None
    for i, x in enumerate(c, 1):
        s, e, sim, ls = x.get('start'), x.get('end'), x.get('similarity'), x.get('lines')
        if not (isinstance(s, int) and isinstance(e, int) and e - s + 1 == 3):
            return 'candidate %d: lines %r-%r, want a 3-line region' % (i, s, e)
        if not (isinstance(sim, (int, float)) and 0.5 <= sim <= 1):
            return 'candidate %d: similarity %r, want 0.5 to 1' % (i, sim)
        if prev is not None and sim > prev:
            return 'candidate %d: similarity %r above the one before (%r): not ranked' % (i, sim, prev)
        prev = sim
        if not isinstance(ls, list) or len(ls) != 3:
            return 'candidate %d: lines %r, want 3 numbered lines' % (i, ls)
        for k, line in enumerate(ls):
            m = re.match(r'^ *([0-9]+)', line)
            if not m or int(m.group(1)) != s + k:
                return 'candidate %d: line %r does not carry line number %d' % (i, line, s + k)
    return 'ok'
print('rules=' + check())
first = c[0] if isinstance(c, list) and c else {}
print('first=%s-%s' % (first.get('start'), first.get('end')))
print('difference=%s' % first.get('difference'))
print('first_lines=' + json.dumps(first.get('lines')))"
  expect_j rules ok
  expect_j first "${PLANTED_START}-${PLANTED_END}"
  [[ "$(jval difference)" == *"line 2"* ]] || flunk "the first candidate's difference does not name line 2: $(jval difference)"

  local want got
  want="$(numbered "${CELL}/${FILE}" "$PLANTED_START" "$PLANTED_END")"
  got="$(jval first_lines | pyq 'import json,sys; print("\n".join(json.load(sys.stdin)))')" || flunk "first candidate's lines"
  same_text "the first candidate's numbered lines" "$want" "$got"
}

# check_text STYLE — --text: the header with scope `no match`, the verdict, 1 to 3 `── candidate N:`
# headings, the first `lines 20-22`, followed by those lines numbered as view numbers them; a closing
# `do instead:`; the file's hash unchanged.
check_text() {
  make_fixture sc4-text "$1" notty
  in_cell "$1" "edit ${FILE} ${EDIT_ARGS} --text"
  expect_status 3
  unchanged
  no_stderr

  [[ "${lines[0]:-}" == "edit: ${FILE} [no match]" ]] || flunk "header line: ${lines[0]:-<none>}"
  [[ "${lines[1]:-}" == "verdict: ${VERDICT_PREFIX}"*"nothing written"* ]] || flunk "verdict line: ${lines[1]:-<none>}"

  local i n=0 first=-1
  for ((i = 2; i < ${#lines[@]}; i++)); do
    if [[ "${lines[i]}" == "── candidate "* ]]; then
      n=$((n + 1))
      ((first >= 0)) || first=$i
    fi
  done
  ((n >= 1 && n <= 3)) || flunk "${n} candidate headings, want 1 to 3"
  [[ "${lines[first]}" == "── candidate 1: lines ${PLANTED_START}-${PLANTED_END}, similarity "* ]] || flunk "first candidate heading: ${lines[first]}"

  local want
  want="$(numbered "${CELL}/${FILE}" "$PLANTED_START" "$PLANTED_END")"
  same_text "the first candidate's numbered lines" "$want" "$(printf '%s\n' "${lines[@]:first+1:3}")"
  [[ "${lines[${#lines[@]} - 1]}" == "do instead: "* ]] || flunk "last line is not 'do instead:': ${lines[${#lines[@]} - 1]}"
}

@test "SC-4 [bash -c, notty] Text that matches nowhere is refused with exit 3, showing up to three nearest candidate regions with line numbers — JSON: 1-3 ranked candidates, the planted region 20-22 first; file sha256 unchanged" { check_json c; }
@test "SC-4 [bash -lc, notty] Text that matches nowhere is refused with exit 3, showing up to three nearest candidate regions with line numbers — JSON: 1-3 ranked candidates, the planted region 20-22 first; file sha256 unchanged" { check_json lc; }
@test "SC-4 [bash -c, notty] Text that matches nowhere is refused with exit 3, showing up to three nearest candidate regions with line numbers — text: candidate 1 is lines 20-22, numbered; file sha256 unchanged" { check_text c; }
@test "SC-4 [bash -lc, notty] Text that matches nowhere is refused with exit 3, showing up to three nearest candidate regions with line numbers — text: candidate 1 is lines 20-22, numbered; file sha256 unchanged" { check_text lc; }
