#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# SC-2 — "Viewing `file:40-80`, `file:40` with surrounding context, and a missing file (exit 3) each
# behave as specified; a binary file prints its type and size instead of content". (Feature 006,
# slice 0; spec FR-2, FR-3, FR-5, FR-8, FR-9, D-10; tasks.md T004; contracts/view-search-cli.md § view.)
# Also FR-7 — a line longer than COLUMNS is cut in both modes with `…[cut N bytes]`, JSON carries
# `cut_lines`, and the `long lines cut:` line's command reads it whole (contract as amended for
# discovery revision 12, which answered FOR-MENTOR Item 18 Q3).
#
# Written from the contract before the tool existed (tasks.md Phase 2). Expected lines are formatted by
# awk from the fixture; byte counts are the fixture's own (sed | wc -c, wc -c), never the tool's (P004).
# "No content bytes" is checked on the raw stdout bytes in the container: no NUL, no 0x7f, no 0x89, no
# 0x1a, and not the ASCII marker the fixture placed after the NULs (BOUNDED_READ_CONTENT_MARKER).
#
# The files are built by fixtures/bounded-read.sh (seq, printf, awk, git; P005), afresh per test.
# Cells: bash -c and bash -lc, `notty`.

load helpers

FIXTURE=/tmp/bounded-read-sc2.sh

setup_file() {
  stamp_check
  copy_into_container "${BATS_TEST_DIRNAME}/fixtures/bounded-read.sh" "$FIXTURE" 0755
}

setup() {
  WORK="$(container_tmpdir sc2view)"
  FX="${WORK}/fx"
  SCRATCH="${WORK}/scratch"
  exec_plain sh "$FIXTURE" "$FX" >/dev/null
}

teardown() {
  container_rm "$WORK"
}

# ── helpers (this file's own; the 006 files repeat them so each reads alone) ─────────────────────

# in_dir STYLE DIR CMD [K=V]... — run CMD in DIR with this test's session scratch; stderr goes to
# $WORK/stderr so stdout stays one JSON document.
in_dir() {
  local style="$1" dir="$2" cmd="$3" kv
  shift 3
  local -a envs=(-e "TIMELIKE_SCRATCH_ROOT=${SCRATCH}" -e "TIMELIKE_SESSION=boundedread")
  for kv in "$@"; do envs+=(-e "$kv"); done
  run_in "${envs[@]}" "$style" notty "cd '${dir}' && { ${cmd}; } 2>'${WORK}/stderr'"
  assert_within 20
}

# flunk MESSAGE — fail with the last run's exit, stdout and stderr.
flunk() {
  local err
  err="$(exec_plain cat "${WORK}/stderr" 2>&1)" || true
  printf '%s\nexit %s; stdout:\n%s\nstderr:\n%s\n' "$1" "$status" "$output" "$err" >&2
  return 1
}

expect_status() {
  [[ "$status" == "$1" ]] || flunk "expected exit $1, got $status"
}

# jpy SCRIPT — Python over the last run's stdout, parsed as JSON into `d`; `g(k)` reads a field by a
# dotted path (`truncated.more`), top-level first, then under `data`. Output in $JPY.
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

# json_lines — the JSON `lines` array, one per line, into $JPY.
json_lines() {
  jpy "print('\n'.join(g('lines', [])))"
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

# numbered FILE A B [TARGET] — lines A..B of FILE (in the fixture directory) as view must print them:
# the number right-aligned to the width of the file's line count, the marker (">" on TARGET, else a
# space), one space, the text. Formatted by awk from the file itself.
numbered() {
  exec_plain awk -v a="$2" -v b="$3" -v t="${4:-0}" '
    NR == FNR { n++; next }
    FNR == 1 { w = length(n "") }
    FNR >= a && FNR <= b { printf "%" w "d%s %s\n", FNR, (FNR == t ? ">" : " "), $0 }' "${FX}/$1" "${FX}/$1"
}

# line_count FILE / byte_count FILE / range_bytes FILE A B — measured in the container.
line_count() { exec_plain sh -c 'wc -l <"$1"' count "${FX}/$1"; }
byte_count() { exec_plain sh -c 'wc -c <"$1"' count "${FX}/$1"; }
range_bytes() { exec_plain sh -c 'sed -n "$2,$3p" "$1" | wc -c' bytes "${FX}/$1" "$2" "$3"; }

# text_body — the shown file lines of the last text run, into $BODY: every line after the verdict,
# without `── ` section labels, up to the first closing line (more:, exit:, full output:, … omitted)
# or a `long lines cut:` line.
text_body() {
  local i out=()
  for ((i = 2; i < ${#lines[@]}; i++)); do
    case "${lines[i]}" in
      "── "*) continue ;;
      "more: "* | "exit: "* | "full output: "* | "… omitted "* | "long lines cut: "*) break ;;
    esac
    out+=("${lines[i]}")
  done
  BODY="$(printf '%s\n' "${out[@]}")"
}

# ── checks ────────────────────────────────────────────────────────────────────────────────────

# closing_lines MORE OMITTED BYTES ABS — the last four text lines are the cut's closing lines.
closing_lines() {
  local n=${#lines[@]}
  [[ "${lines[n - 4]}" == "more: $1" ]] || flunk "more line: ${lines[n - 4]} (want 'more: $1')"
  [[ "${lines[n - 3]}" == "exit: 0" ]] || flunk "exit line: ${lines[n - 3]}"
  [[ "${lines[n - 2]}" == "full output: $4" ]] || flunk "full output line: ${lines[n - 2]}"
  [[ "${lines[n - 1]}" == "… omitted $2 lines ($3 bytes) — full output: $4; more: $1" ]] \
    || flunk "omission line: ${lines[n - 1]} (want $2 lines, $3 bytes)"
}

# check_range STYLE — `view big.txt:40-80` shows exactly lines 40-80. It is a partial window, so a cut:
# its `more:` is the next window (81-200) and the omitted figures are the file outside 40-80.
check_range() {
  local total all win abs expected
  total="$(line_count big.txt)"
  all="$(byte_count big.txt)"
  win="$(range_bytes big.txt 40 80)"
  abs="$(exec_plain realpath "${FX}/big.txt")"
  expected="$(numbered big.txt 40 80)"

  in_dir "$1" "$FX" "view big.txt:40-80 --text"
  expect_status 0
  # <target> is FILE as given, without the range (rule 12; contract § view, Target and scope).
  [[ "${lines[0]:-}" == "view: big.txt [lines 40-80 of 412]" ]] || flunk "header line: ${lines[0]:-<none>}"
  [[ "${lines[1]:-}" == "verdict: lines 40-80 of 412" ]] || flunk "verdict line: ${lines[1]:-<none>}"
  text_body
  same_text "lines shown for :40-80" "$expected" "$BODY"
  closing_lines "view big.txt:81-200" $((total - 41)) $((all - win)) "$abs"

  in_dir "$1" "$FX" "view big.txt:40-80"
  expect_status 0
  # JSON `target` is rule 12's FILE as given (agentio reserves the key); line N is `target_line`.
  jfields target target_line start end total next truncated.more
  expect_j target big.txt
  expect_j target_line null
  expect_j start 40
  expect_j end 80
  expect_j total 412
  expect_j next "view big.txt:81-200"
  expect_j truncated.more "view big.txt:81-200"
  json_lines
  same_text "JSON lines for :40-80" "$expected" "$JPY"
}

# check_context STYLE — `view big.txt:40` shows lines 30-50, with `>` in the marker column of line 40
# and of no other line.
check_context() {
  local expected marked
  expected="$(numbered big.txt 30 50 40)"

  in_dir "$1" "$FX" "view big.txt:40 --text"
  expect_status 0
  [[ "${lines[1]:-}" == "verdict: lines 30-50 of 412" ]] || flunk "verdict line: ${lines[1]:-<none>}"
  text_body
  same_text "lines shown for :40" "$expected" "$BODY"
  marked="$(grep -c '^ *[0-9][0-9]*>' <<<"$BODY")" || true
  [[ "$marked" == 1 ]] || flunk "${marked} lines carry the > marker, want 1"
  [[ "$(grep '^ *[0-9][0-9]*>' <<<"$BODY")" == " 40> "* ]] || flunk "the marked line is not line 40"
  closing_lines "view big.txt:51-170" $(($(line_count big.txt) - 21)) \
    $(($(byte_count big.txt) - $(range_bytes big.txt 30 50))) "$(exec_plain realpath "${FX}/big.txt")"

  in_dir "$1" "$FX" "view big.txt:40"
  expect_status 0
  jfields target target_line start end
  expect_j target big.txt
  expect_j target_line 40
  expect_j start 30
  expect_j end 50
  json_lines
  same_text "JSON lines for :40" "$expected" "$JPY"
}

# check_missing STYLE — a missing file is an outcome on stdout (D-10): exit 3, the verdict naming it,
# `do instead:` naming its basename for search, and nothing on stderr; JSON carries the remedy.
check_missing() {
  exec_plain test ! -e "${FX}/missing/bgi.txt" || { echo "fixture has missing/bgi.txt" >&2; return 1; }
  local remedy="check the name; search for it with: search -F bgi.txt ."

  in_dir "$1" "$FX" "view missing/bgi.txt --text"
  expect_status 3
  [[ "${lines[0]:-}" == "view: missing/bgi.txt ["*"]" ]] || flunk "header line: ${lines[0]:-<none>}"
  [[ "${lines[1]:-}" == "verdict: no such file: missing/bgi.txt" ]] || flunk "verdict line: ${lines[1]:-<none>}"
  [[ "${lines[2]:-}" == "do instead: ${remedy}" ]] || flunk "do-instead line: ${lines[2]:-<none>}"
  [[ -z "$(exec_plain cat "${WORK}/stderr")" ]] || flunk "a missing file is a result on stdout, but stderr is not empty"

  in_dir "$1" "$FX" "view missing/bgi.txt"
  expect_status 3
  jfields exit verdict remedy lines
  expect_j exit 3
  expect_j verdict "no such file: missing/bgi.txt"
  expect_j remedy "$remedy"
  expect_j lines "[]"
}

# raw_clean FILE — the stdout bytes saved in FILE carry no NUL, 0x7f, 0x89 or 0x1a byte.
raw_clean() {
  local counts
  counts="$(exec_plain sh -c 'tr -d "\000\177\211\032" <"$1" | wc -c; wc -c <"$1"' raw "$1")"
  [[ "$(sed -n 1p <<<"$counts")" == "$(sed -n 2p <<<"$counts")" ]] || flunk "stdout carries binary content bytes (sizes without/with them: ${counts//$'\n'/ \/ })"
}

# check_binary STYLE FILE TYPE — a binary file prints its type and size instead of content: exit 0,
# scope `binary`, verdict `binary file: TYPE, <human size> (<bytes> bytes); content not shown` with the
# fixture's byte count, no lines, and no content byte in stdout (text and JSON).
check_binary() {
  local style="$1" file="$2" type="$3" bytes
  bytes="$(byte_count "$file")"

  in_dir "$style" "$FX" "view ${file} --text >'${WORK}/out'; rc=\$?; cat '${WORK}/out'; exit \$rc"
  expect_status 0
  raw_clean "${WORK}/out"
  [[ ${#lines[@]} -eq 2 ]] || flunk "a binary view printed ${#lines[@]} lines, want 2 (header and verdict)"
  [[ "${lines[0]}" == "view: ${file} [binary]" ]] || flunk "header line: ${lines[0]}"
  # The human size's format is not fixed by the contract; the exact byte count is.
  [[ "${lines[1]}" =~ ^verdict:\ binary\ file:\ ${type},\ ([^,]+)\ \(([0-9]+)\ bytes\)\;\ content\ not\ shown$ ]] \
    || flunk "verdict line: ${lines[1]}"
  [[ "${BASH_REMATCH[2]}" == "$bytes" ]] || flunk "verdict names ${BASH_REMATCH[2]} bytes, the file has ${bytes}"
  [[ "$output" != *BOUNDED_READ_CONTENT_MARKER* ]] || flunk "the file's content was printed"

  in_dir "$style" "$FX" "view ${file} >'${WORK}/out.json'; rc=\$?; cat '${WORK}/out.json'; exit \$rc"
  expect_status 0
  raw_clean "${WORK}/out.json"
  [[ "$output" != *BOUNDED_READ_CONTENT_MARKER* ]] || flunk "the file's content is in the JSON"
  [[ "$output" != *'\u0000'* ]] || flunk "the JSON carries an escaped NUL: content was included"
  jfields scope exit binary type size lines
  expect_j scope binary
  expect_j exit 0
  expect_j binary true
  expect_j type "$type"
  expect_j size "$bytes"
  expect_j lines "[]"
}

# ── FR-7: a line longer than COLUMNS (long.txt: 3 lines, line 2 is 5000 bytes) ───────────────────
LONG_COLUMNS=120
LONG_WHOLE="view long.txt:1-3 --columns 0"

# cut_ok GOT FULL — GOT is FULL cut by rule 13: a prefix of FULL no longer than COLUMNS, then the
# marker `…[cut N bytes]`, where the kept characters and N add up to FULL's length (all ASCII). Sets
# CUT_BYTES. Whether the cut counts the line number with the text is not fixed, so both are accepted:
# either way the bytes are conserved.
cut_ok() {
  local got="$1" full="$2" kept
  [[ "$got" =~ ^(.*)…\[cut\ ([0-9]+)\ bytes\]$ ]] || flunk "line is not cut with '…[cut N bytes]': ${got:0:160}"
  kept="${BASH_REMATCH[1]}"
  CUT_BYTES="${BASH_REMATCH[2]}"
  kept="${kept% }"
  [[ "$full" == "$kept"* ]] || flunk "the kept part is not the line's start: ${kept:0:160}"
  ((${#kept} <= LONG_COLUMNS)) || flunk "kept ${#kept} characters, more than COLUMNS=${LONG_COLUMNS}"
  ((${#kept} > 3)) || flunk "no text kept before the cut: '${kept}'"
  ((${#kept} + CUT_BYTES == ${#full})) || flunk "kept ${#kept} + cut ${CUT_BYTES} != ${#full} bytes of the line"
}

# check_long_text STYLE — text: line 2 is cut, lines 1 and 3 are whole, and the last body line names
# the cut and the command that reads the window whole. The file is shown whole: no omission line.
check_long_text() {
  local full
  full="$(numbered long.txt 2 2)"
  ((${#full} == 5003)) || { echo "oracle line 2 is ${#full} bytes, want 5003" >&2; return 1; }

  in_dir "$1" "$FX" "view long.txt --text" "COLUMNS=${LONG_COLUMNS}"
  expect_status 0
  [[ "${lines[0]:-}" == "view: long.txt [lines 1-3 of 3]" ]] || flunk "header line: ${lines[0]:-<none>}"
  [[ "${lines[1]:-}" == "verdict: lines 1-3 of 3 (whole file)" ]] || flunk "verdict line: ${lines[1]:-<none>}"
  [[ "${lines[2]:-}" == "$(numbered long.txt 1 1)" ]] || flunk "line 1: ${lines[2]:-<none>}"
  cut_ok "${lines[3]:-}" "$full"
  [[ "${lines[4]:-}" == "$(numbered long.txt 3 3)" ]] || flunk "line 3: ${lines[4]:-<none>}"
  [[ "${lines[5]:-}" == "long lines cut: 1; read them whole with: ${LONG_WHOLE}" ]] || flunk "long-lines line: ${lines[5]:-<none>}"
  [[ ${#lines[@]} -eq 6 ]] || flunk "text output has ${#lines[@]} lines, want 6"
}

# check_long_json STYLE — JSON: the same cut in `lines`, and `cut_lines` naming index 1 with the
# marker's byte count.
check_long_json() {
  local full
  full="$(numbered long.txt 2 2)"

  in_dir "$1" "$FX" "view long.txt" "COLUMNS=${LONG_COLUMNS}"
  expect_status 0
  jpy "L = g('lines', [])
print('n=%d' % len(L))
for i in range(4):
    print('l%d=%s' % (i, L[i] if i < len(L) else '<absent>'))
print('cut_lines=' + json.dumps(g('cut_lines'), sort_keys=True))
print('truncated=' + json.dumps(g('truncated'), sort_keys=True))"
  expect_j l0 "$(numbered long.txt 1 1)"
  cut_ok "$(jval l1)" "$full"
  expect_j l2 "$(numbered long.txt 3 3)"
  # Whether JSON `lines` carries the `long lines cut:` body line is not fixed: absent, or that line.
  local l3
  l3="$(jval l3)"
  [[ "$l3" == "<absent>" || "$l3" == "long lines cut: 1; read them whole with: ${LONG_WHOLE}" ]] || flunk "JSON lines[3]: ${l3}"
  expect_j cut_lines "[{\"cut_bytes\": ${CUT_BYTES}, \"index\": 1}]"
  expect_j truncated '"<absent>"'
}

# check_long_whole STYLE — the `long lines cut:` command, run as printed, shows line 2 whole: all
# 5000 bytes, and no `cut_lines`.
check_long_whole() {
  in_dir "$1" "$FX" "view long.txt --text" "COLUMNS=${LONG_COLUMNS}"
  expect_status 0
  local cmd="" line
  for line in "${lines[@]}"; do
    [[ "$line" == "long lines cut: "*"; read them whole with: "* ]] && { cmd="${line#*; read them whole with: }"; break; }
  done
  [[ "$cmd" == "$LONG_WHOLE" ]] || flunk "long-lines command: '${cmd}'"

  in_dir "$1" "$FX" "$cmd" "COLUMNS=${LONG_COLUMNS}"
  expect_status 0
  jpy "L = g('lines', [])
print('n=%d' % len(L))
print('l1=' + (L[1] if len(L) > 1 else '<absent>'))
print('cut_lines=' + json.dumps(g('cut_lines'), sort_keys=True))"
  expect_j n 3
  expect_j l1 "$(numbered long.txt 2 2)"
  expect_j cut_lines '"<absent>"'
}

@test "SC-2 viewing file:40-80 shows exactly lines 40-80 [bash -c, notty]" { check_range c; }
@test "SC-2 viewing file:40-80 shows exactly lines 40-80 [bash -lc, notty]" { check_range lc; }
@test "SC-2 viewing file:40 with surrounding context shows lines 30-50 with line 40 marked [bash -c, notty]" { check_context c; }
@test "SC-2 viewing file:40 with surrounding context shows lines 30-50 with line 40 marked [bash -lc, notty]" { check_context lc; }
@test "SC-2 viewing a missing file exits 3 with do instead [bash -c, notty]" { check_missing c; }
@test "SC-2 viewing a missing file exits 3 with do instead [bash -lc, notty]" { check_missing lc; }
@test "SC-2 a binary file prints its type and size instead of content: ELF [bash -c, notty]" { check_binary c app.bin ELF; }
@test "SC-2 a binary file prints its type and size instead of content: ELF [bash -lc, notty]" { check_binary lc app.bin ELF; }
@test "SC-2 a binary file prints its type and size instead of content: PNG [bash -c, notty]" { check_binary c pic.png PNG; }
@test "SC-2 a binary file prints its type and size instead of content: PNG [bash -lc, notty]" { check_binary lc pic.png PNG; }
@test "FR-7 a line longer than COLUMNS is cut in text with …[cut N bytes] and a long-lines line naming how to read it whole [bash -c, notty]" { check_long_text c; }
@test "FR-7 a line longer than COLUMNS is cut in text with …[cut N bytes] and a long-lines line naming how to read it whole [bash -lc, notty]" { check_long_text lc; }
@test "FR-7 a line longer than COLUMNS is cut in JSON with …[cut N bytes] and cut_lines names it [bash -c, notty]" { check_long_json c; }
@test "FR-7 a line longer than COLUMNS is cut in JSON with …[cut N bytes] and cut_lines names it [bash -lc, notty]" { check_long_json lc; }
@test "FR-7 a line longer than COLUMNS: the long-lines command, when run, shows it whole with no cut_lines [bash -c, notty]" { check_long_whole c; }
@test "FR-7 a line longer than COLUMNS: the long-lines command, when run, shows it whole with no cut_lines [bash -lc, notty]" { check_long_whole lc; }
