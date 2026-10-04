#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# SC-1 — "Viewing a 412-line file with no range shows lines 1–120 with right-aligned line numbers, a
# header naming the file and range out of 412, and a footer naming the next range command". A file of
# 120 lines or fewer is shown whole, with no omission line. (Feature 006, slice 0; spec FR-1, FR-3,
# FR-4, FR-5, D-1, D-2; tasks.md T003; contracts/view-search-cli.md § view.)
#
# Written from the contract before the tool existed (tasks.md Phase 2). The test decides by what it
# measures itself (lore cross-stack P004): the expected numbered lines are formatted by awk from the
# fixture (`{n:>W}{marker} {text}`, W = digits of the file's line count), and the omission figures are
# the fixture's own line and byte counts (sed | wc -c), never the tool's.
#
# The files are built by fixtures/bounded-read.sh (seq, printf, awk, git; P005), afresh per test.
# Cells: bash -c and bash -lc, `notty` (the harness's own invocation; output is JSON by default).

load helpers

FIXTURE=/tmp/bounded-read-sc1.sh

setup_file() {
  stamp_check
  copy_into_container "${BATS_TEST_DIRNAME}/fixtures/bounded-read.sh" "$FIXTURE" 0755
}

setup() {
  WORK="$(container_tmpdir sc1view)"
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

# check_window_text STYLE — `view big.txt --text`: header and verdict name lines 1-120 of 412, the
# shown lines are exactly lines 1-120 right-aligned to 3 digits, and the closing lines are the next
# window's command, exit, the file itself as full output, and the omission line with the fixture's
# figures for lines 121-412.
check_window_text() {
  local total abs omitted bytes expected
  total="$(line_count big.txt)"
  [[ "$total" == 412 ]] || { echo "fixture big.txt has ${total} lines, want 412" >&2; return 1; }
  abs="$(exec_plain realpath "${FX}/big.txt")"
  omitted=$((total - 120))
  bytes="$(range_bytes big.txt 121 "$total")"
  expected="$(numbered big.txt 1 120)"
  [[ "$(head -c 6 <<<"$expected")" == "  1  l" ]] || { echo "oracle formatting is wrong: ${expected:0:20}" >&2; return 1; }

  in_dir "$1" "$FX" "view big.txt --text"
  expect_status 0
  [[ "${lines[0]:-}" == "view: big.txt [lines 1-120 of 412]" ]] || flunk "header line: ${lines[0]:-<none>}"
  [[ "${lines[1]:-}" == "verdict: lines 1-120 of 412" ]] || flunk "verdict line: ${lines[1]:-<none>}"
  [[ "${lines[2]:-}" == "── lines 1-120 of 412 ──" ]] || flunk "section label: ${lines[2]:-<none>}"
  text_body
  same_text "shown lines" "$expected" "$BODY"

  local n=${#lines[@]}
  ((n == 3 + 120 + 4)) || flunk "text output has ${n} lines, want 127 (header, verdict, label, 120 lines, 4 closing)"
  [[ "${lines[n - 4]}" == "more: view big.txt:121-240" ]] || flunk "more line: ${lines[n - 4]}"
  [[ "${lines[n - 3]}" == "exit: 0" ]] || flunk "exit line: ${lines[n - 3]}"
  [[ "${lines[n - 2]}" == "full output: ${abs}" ]] || flunk "full output line: ${lines[n - 2]}"
  [[ "${lines[n - 1]}" == "… omitted ${omitted} lines (${bytes} bytes) — full output: ${abs}; more: view big.txt:121-240" ]] \
    || flunk "omission line: ${lines[n - 1]} (want ${omitted} lines, ${bytes} bytes)"
}

# check_more_runs STYLE — the `more:` command, pasted as printed into the same shell, shows exactly
# lines 121-240 (read from its JSON, the default under the harness's pipe).
check_more_runs() {
  in_dir "$1" "$FX" "view big.txt --text"
  expect_status 0
  local more="" line
  for line in "${lines[@]}"; do
    [[ "$line" == "more: "* ]] && { more="${line#more: }"; break; }
  done
  [[ "$more" == "view big.txt:121-240" ]] || flunk "more command: '${more}'"

  in_dir "$1" "$FX" "$more"
  expect_status 0
  jfields scope start end total
  expect_j scope "lines 121-240 of 412"
  expect_j start 121
  expect_j end 240
  expect_j total 412
  json_lines
  same_text "lines shown by '${more}'" "$(numbered big.txt 121 240)" "$JPY"
}

# check_window_json STYLE — `view big.txt` under the pipe is JSON (D-1): the window as data, `lines`
# the same numbered strings, and the cut's figures in `truncated`, with `truncated.more == next`.
check_window_json() {
  local abs bytes
  abs="$(exec_plain realpath "${FX}/big.txt")"
  bytes="$(range_bytes big.txt 121 412)"

  in_dir "$1" "$FX" "view big.txt"
  expect_status 0
  jfields tool target target_line scope exit path abs_path start end total next \
    truncated.more truncated.omitted_lines truncated.omitted_bytes truncated.full_output cut_lines
  expect_j tool view
  expect_j target big.txt
  expect_j target_line null
  expect_j scope "lines 1-120 of 412"
  expect_j exit 0
  expect_j path big.txt
  expect_j abs_path "$abs"
  expect_j start 1
  expect_j end 120
  expect_j total 412
  expect_j next "view big.txt:121-240"
  expect_j truncated.more "view big.txt:121-240"
  expect_j truncated.omitted_lines 292
  expect_j truncated.omitted_bytes "$bytes"
  expect_j truncated.full_output "$abs"
  # no line is longer than COLUMNS, so nothing was cut (rule 13 in JSON, discovery revision 12)
  expect_j cut_lines "<absent>"
  json_lines
  same_text "JSON lines" "$(numbered big.txt 1 120)" "$JPY"
}

# check_whole_file STYLE — small.txt (100 lines) is shown whole: lines 1-100 of 100, "(whole file)",
# no omission line, no `more:`, and the text ends on the file's last line; JSON has no `truncated`
# and `next` null.
check_whole_file() {
  local total expected last
  total="$(line_count small.txt)"
  [[ "$total" == 100 ]] || { echo "fixture small.txt has ${total} lines, want 100" >&2; return 1; }
  expected="$(numbered small.txt 1 100)"
  last="$(numbered small.txt 100 100)"

  in_dir "$1" "$FX" "view small.txt --text"
  expect_status 0
  [[ "${lines[0]:-}" == "view: small.txt [lines 1-100 of 100]" ]] || flunk "header line: ${lines[0]:-<none>}"
  [[ "${lines[1]:-}" == "verdict: lines 1-100 of 100 (whole file)" ]] || flunk "verdict line: ${lines[1]:-<none>}"
  text_body
  same_text "shown lines" "$expected" "$BODY"
  [[ "${lines[${#lines[@]} - 1]}" == "$last" ]] || flunk "text does not end on the file's last line: ${lines[${#lines[@]} - 1]}"
  assert_no_line_matching '^(… omitted |more: |full output: |exit: )' || flunk "a whole-file view carries closing lines"

  in_dir "$1" "$FX" "view small.txt"
  expect_status 0
  jfields scope start end total next truncated
  expect_j scope "lines 1-100 of 100"
  expect_j start 1
  expect_j end 100
  expect_j total 100
  expect_j next null
  expect_j truncated "<absent>"
  json_lines
  same_text "JSON lines" "$expected" "$JPY"
}

@test "SC-1 viewing a 412-line file with no range shows lines 1-120 with right-aligned line numbers, a header naming the file and range out of 412, and a footer naming the next range command [bash -c, notty]" { check_window_text c; }
@test "SC-1 viewing a 412-line file with no range shows lines 1-120 with right-aligned line numbers, a header naming the file and range out of 412, and a footer naming the next range command [bash -lc, notty]" { check_window_text lc; }
@test "SC-1 viewing a 412-line file: the footer's next range command, when run, shows lines 121-240 [bash -c, notty]" { check_more_runs c; }
@test "SC-1 viewing a 412-line file: the footer's next range command, when run, shows lines 121-240 [bash -lc, notty]" { check_more_runs lc; }
@test "SC-1 viewing a 412-line file with no range: JSON carries lines 1-120, start, end, total, next and truncated.more equal to next [bash -c, notty]" { check_window_json c; }
@test "SC-1 viewing a 412-line file with no range: JSON carries lines 1-120, start, end, total, next and truncated.more equal to next [bash -lc, notty]" { check_window_json lc; }
@test "SC-1 a file of 120 lines or fewer is shown whole, with no omission line [bash -c, notty]" { check_whole_file c; }
@test "SC-1 a file of 120 lines or fewer is shown whole, with no omission line [bash -lc, notty]" { check_whole_file lc; }
