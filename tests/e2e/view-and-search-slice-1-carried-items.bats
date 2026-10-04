#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# Carried from slice 0 into slice 1 (feature 006; spec FR-36, FR-37, FR-38; tasks.md T018;
# contracts/view-search-cli.md § view "Partial window: a cut", § Slice 1 "search plurals"; research R10):
#   FR-38  a window ending at the file's end (`view big.txt:400-412` of a 412-line file) is a cut whose
#          `more` is the window before it, `view big.txt:280-399`, in text and in JSON;
#   FR-36  search's verdict uses the singular for 1: `1 match in 1 file (searched 1 file)`, never
#          `1 files`;
#   FR-37  search speed in the image over a generated corpus of about 40 MiB: the search concludes
#          within 30 s and exits 0. The measured MB/s goes into the TAP stream as a diagnostic for the
#          lane's record (`# search speed: …`). It is a measurement, not a criterion: no bound on the
#          figure is asserted.
#
# Written from the contract before the slice-1 tool existed (tasks.md Phase 6, tests first). Every
# expected figure is the test's own (lore cross-stack P004, P005): line and byte counts by wc and sed,
# expected lines formatted by awk, match counts by grep, the corpus size by wc -c, and the elapsed time
# taken by the container's own bash ($EPOCHREALTIME) around the one search call, so docker exec's
# overhead is not in the figure.
#
# Files: fixtures/bounded-read.sh (big.txt, slice 0's) and fixtures/bounded-read-slice1.sh (`plural`,
# `corpus`), built inside the check that needs them, afresh per test.
# Cells: bash -c and bash -lc, `notty`.

load helpers

FIXTURE0=/tmp/bounded-read-slice1-carried-0.sh
FIXTURE1=/tmp/bounded-read-slice1-carried-1.sh

setup_file() {
  stamp_check
  copy_into_container "${BATS_TEST_DIRNAME}/fixtures/bounded-read.sh" "$FIXTURE0" 0755
  copy_into_container "${BATS_TEST_DIRNAME}/fixtures/bounded-read-slice1.sh" "$FIXTURE1" 0755
}

setup() {
  WORK="$(container_tmpdir s1carried)"
  FX="${WORK}/fx"
  SCRATCH="${WORK}/scratch"
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

# numbered FILE A B — lines A..B of FILE (in the fixture directory) as view must print them: the number
# right-aligned to the width of the file's line count, a space for the marker, one space, the text.
numbered() {
  exec_plain awk -v a="$2" -v b="$3" '
    NR == FNR { n++; next }
    FNR == 1 { w = length(n "") }
    FNR >= a && FNR <= b { printf "%" w "d  %s\n", FNR, $0 }' "${FX}/$1" "${FX}/$1"
}

line_count() { exec_plain sh -c 'wc -l <"$1"' count "${FX}/$1"; }
range_bytes() { exec_plain sh -c 'sed -n "$2,$3p" "$1" | wc -c' bytes "${FX}/$1" "$2" "$3"; }

# text_body — the shown file lines of the last text run, into $BODY: every line after the verdict,
# without `── ` section labels, up to the first closing line or a `long lines cut:` line.
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

# ── FR-38: a window ending at the file's end ─────────────────────────────────────────────────

# end_window_fixture — build big.txt and set ABS and BEFORE_BYTES (lines 1-399, as stored).
end_window_fixture() {
  exec_plain sh "$FIXTURE0" "$FX" >/dev/null
  local total
  total="$(line_count big.txt)"
  [[ "$total" == 412 ]] || { echo "fixture big.txt has ${total} lines, want 412" >&2; return 1; }
  ABS="$(exec_plain realpath "${FX}/big.txt")"
  BEFORE_BYTES="$(range_bytes big.txt 1 399)"
}

# check_end_window_text STYLE — `view big.txt:400-412 --text`: lines 400-412 of 412, then the closing
# lines of a cut whose more is the window before, `view big.txt:280-399`, and whose omission counts
# lines 1-399 and their bytes.
check_end_window_text() {
  end_window_fixture
  in_dir "$1" "$FX" "view big.txt:400-412 --text"
  expect_status 0
  [[ "${lines[0]:-}" == "view: big.txt [lines 400-412 of 412]" ]] || flunk "header line: ${lines[0]:-<none>}"
  [[ "${lines[1]:-}" == "verdict: lines 400-412 of 412" ]] || flunk "verdict line: ${lines[1]:-<none>}"
  [[ "${lines[2]:-}" == "── lines 400-412 of 412 ──" ]] || flunk "section label: ${lines[2]:-<none>}"
  text_body
  same_text "shown lines" "$(numbered big.txt 400 412)" "$BODY"
  local n=${#lines[@]}
  ((n == 3 + 13 + 4)) || flunk "text output has ${n} lines, want 20 (header, verdict, label, 13 lines, 4 closing)"
  [[ "${lines[n - 4]}" == "more: view big.txt:280-399" ]] || flunk "more line: ${lines[n - 4]}"
  [[ "${lines[n - 3]}" == "exit: 0" ]] || flunk "exit line: ${lines[n - 3]}"
  [[ "${lines[n - 2]}" == "full output: ${ABS}" ]] || flunk "full output line: ${lines[n - 2]}"
  [[ "${lines[n - 1]}" == "… omitted 399 lines (${BEFORE_BYTES} bytes) — full output: ${ABS}; more: view big.txt:280-399" ]] \
    || flunk "omission line: ${lines[n - 1]} (want 399 lines, ${BEFORE_BYTES} bytes)"
}

# check_end_window_json STYLE — the same in JSON: truncated.more is the window before, nothing remains
# after the window so `next` is null; and the more command, run as printed, shows lines 280-399.
check_end_window_json() {
  end_window_fixture
  in_dir "$1" "$FX" "view big.txt:400-412"
  expect_status 0
  jfields scope start end total next truncated.more truncated.omitted_lines truncated.omitted_bytes truncated.full_output
  expect_j scope "lines 400-412 of 412"
  expect_j start 400
  expect_j end 412
  expect_j total 412
  expect_j next null
  expect_j truncated.more "view big.txt:280-399"
  expect_j truncated.omitted_lines 399
  expect_j truncated.omitted_bytes "$BEFORE_BYTES"
  expect_j truncated.full_output "$ABS"
  json_lines
  same_text "JSON lines" "$(numbered big.txt 400 412)" "$JPY"

  in_dir "$1" "$FX" "view big.txt:280-399"
  expect_status 0
  jfields start end total
  expect_j start 280
  expect_j end 399
  expect_j total 412
  json_lines
  same_text "lines shown by the more command" "$(numbered big.txt 280 399)" "$JPY"
}

# ── FR-36: plurals ───────────────────────────────────────────────────────────────────────────

# check_plural STYLE SUBDIR VERDICT — `search zz_plural_token` in SUBDIR of the plural fixture: the
# text verdict is exactly VERDICT, the JSON verdict the same, and no line says `1 files` or `1 matches`.
# The counts are grep's and find's, checked by the fixture.
check_plural() {
  exec_plain sh "$FIXTURE1" plural "$FX" >/dev/null
  in_dir "$1" "${FX}/$2" "search zz_plural_token --text"
  expect_status 0
  [[ "${lines[0]:-}" == "search: . [zz_plural_token]" ]] || flunk "header line: ${lines[0]:-<none>}"
  [[ "${lines[1]:-}" == "verdict: $3" ]] || flunk "verdict line: ${lines[1]:-<none>} (want 'verdict: $3')"
  assert_no_line_matching '(^|[^0-9])1 (files|matches)([^a-z]|$)' || flunk "a plural follows 1"

  in_dir "$1" "${FX}/$2" "search zz_plural_token"
  expect_status 0
  jfields verdict
  expect_j verdict "$3"
}

# ── FR-37: search speed ──────────────────────────────────────────────────────────────────────

# check_search_speed STYLE — `search needle_speed_token corpus` over the generated 40 MiB: exit 0 (not
# 124, its own time limit), concluded within 30 s as the container's bash measured it, and every one of
# grep's 40 hits counted over the 8 files. The MB/s figure is printed to the TAP stream.
check_search_speed() {
  local sp="${WORK}/sp" bytes hits files
  exec_plain sh "$FIXTURE1" corpus "$sp" >/dev/null
  bytes="$(exec_plain sh -c 'cat "$1"/corpus/*.txt | wc -c' n "$sp")"
  hits="$(exec_plain sh -c 'grep -r -o needle_speed_token "$1"/corpus | wc -l' n "$sp")"
  files="$(exec_plain sh -c 'find "$1"/corpus -type f | wc -l' n "$sp")"
  ((bytes >= 40 * 1024 * 1024 - 800)) || { echo "corpus is ${bytes} bytes, want about 40 MiB" >&2; return 1; }
  [[ "$hits" == 40 && "$files" == 8 ]] || { echo "corpus holds ${hits} hits in ${files} files, want 40 in 8" >&2; return 1; }

  # The runner's limit is 60 s so the 30 s bound below is the one that decides, measured inside.
  RUN_TIMEOUT=60 run_in -e "TIMELIKE_SCRATCH_ROOT=${SCRATCH}" -e "TIMELIKE_SESSION=boundedread" "$1" notty \
    "cd '${sp}' && s=\$EPOCHREALTIME && { search needle_speed_token corpus >'${WORK}/speed.json' 2>'${WORK}/stderr'; rc=\$?; } && e=\$EPOCHREALTIME && echo \"rc=\$rc\" && echo \"us=\$(( \${e/[.,]/} - \${s/[.,]/} ))\""
  assert_within 60
  assert_status 0
  local rc us
  rc="$(value_of rc)"
  us="$(value_of us)"
  [[ "$us" =~ ^[0-9]+$ && "$us" -gt 0 ]] || flunk "no elapsed time measured: '${us}'"

  local secs mbps mib
  secs="$(printf '%d.%03d' $((us / 1000000)) $((us % 1000000 / 1000)))"
  mbps="$(printf '%d.%d' $((bytes / us)) $((bytes * 10 / us % 10)))"
  mib="$(printf '%d.%d' $((bytes / 1048576)) $((bytes * 10 / 1048576 % 10)))"
  echo "# search speed: ${mbps} MB/s over ${mib} MiB (${secs} s, $(style_label "$1"), exit ${rc})" >&3

  [[ "$rc" == 0 ]] || flunk "search exited ${rc} after ${secs} s (124 is its own 30 s time limit)"
  ((us < 30000000)) || flunk "search took ${secs} s, over 30 s"
  local counts
  counts="$(exec_plain "$AGENT_PY" -I -c 'import json, sys
d = json.load(open(sys.argv[1]))
def g(k):
    return d.get(k, (d.get("data") or {}).get(k))
print("count=%s files_searched=%s" % (g("count"), g("files_searched")))' "${WORK}/speed.json")" \
    || flunk "the search's stdout is not JSON: $(exec_plain head -c 300 "${WORK}/speed.json")"
  [[ "$counts" == "count=${hits} files_searched=${files}" ]] || flunk "search reports '${counts}', want count=${hits} files_searched=${files}"
}

@test "FR-38 a window ending at the file's end (view big.txt:400-412) is a cut whose more is the window before, view big.txt:280-399 [bash -c, notty]" { check_end_window_text c; }
@test "FR-38 a window ending at the file's end (view big.txt:400-412) is a cut whose more is the window before, view big.txt:280-399 [bash -lc, notty]" { check_end_window_text lc; }
@test "FR-38 a window ending at the file's end: JSON truncated.more is view big.txt:280-399, next is null, and the more command shows lines 280-399 [bash -c, notty]" { check_end_window_json c; }
@test "FR-38 a window ending at the file's end: JSON truncated.more is view big.txt:280-399, next is null, and the more command shows lines 280-399 [bash -lc, notty]" { check_end_window_json lc; }
@test "FR-36 one match in one file: the verdict says 1 match in 1 file (searched 1 file), never 1 files [bash -c, notty]" { check_plural c one "1 match in 1 file (searched 1 file)"; }
@test "FR-36 one match in one file: the verdict says 1 match in 1 file (searched 1 file), never 1 files [bash -lc, notty]" { check_plural lc one "1 match in 1 file (searched 1 file)"; }
@test "FR-36 two matches in one of two files: the verdict says 2 matches in 1 file (searched 2 files) [bash -c, notty]" { check_plural c two "2 matches in 1 file (searched 2 files)"; }
@test "FR-36 two matches in one of two files: the verdict says 2 matches in 1 file (searched 2 files) [bash -lc, notty]" { check_plural lc two "2 matches in 1 file (searched 2 files)"; }
@test "FR-37 search over a generated 40 MiB corpus concludes within 30 s and exits 0; the measured MB/s is printed [bash -c, notty]" { check_search_speed c; }
@test "FR-37 search over a generated 40 MiB corpus concludes within 30 s and exits 0; the measured MB/s is printed [bash -lc, notty]" { check_search_speed lc; }
