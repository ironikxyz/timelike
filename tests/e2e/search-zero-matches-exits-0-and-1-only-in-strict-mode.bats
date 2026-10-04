#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# SC-4 — "A search with zero matches exits 0 with a zero-count header, and exits 1 only in strict
# mode". A failure is distinguishable from both. (Feature 006, slice 0; spec FR-18, FR-20, D-4, D-10;
# tasks.md T006; contracts/view-search-cli.md § search: Zero matches, With --strict, Errors.)
#
# Written from the contract before the tool existed (tasks.md Phase 2). Zero is the fixture's own
# fact, checked by grep before each search: zz_absent_token appears nowhere in the repository, .git
# included. The file count in the verdict is git's reading of what the ignore rules leave
# (`git ls-files -co --exclude-standard`), never the tool's (P004).
# The failure used is a PATH that does not exist (exit 3, `no such path:`), with and without --strict,
# so a strict no-match (exit 1) can never be mistaken for it.
#
# The repository is built by git (fixtures/bounded-read.sh, P005), afresh per test.
# Cells: bash -c and bash -lc, `notty`.

load helpers

FIXTURE=/tmp/bounded-read-sc4.sh

setup_file() {
  stamp_check
  copy_into_container "${BATS_TEST_DIRNAME}/fixtures/bounded-read.sh" "$FIXTURE" 0755
}

setup() {
  WORK="$(container_tmpdir sc4search)"
  FX="${WORK}/fx"
  REPO="${FX}/repo"
  SCRATCH="${WORK}/scratch"
  exec_plain sh "$FIXTURE" "$FX" >/dev/null
  if exec_plain grep -r -q zz_absent_token "$REPO"; then
    echo "fixture carries zz_absent_token" >&2
    return 1
  fi
  exec_plain test ! -e "${REPO}/no-such-dir" || { echo "fixture has no-such-dir" >&2; return 1; }
  NSEARCHED="$(exec_plain sh -c 'cd "$1" && git ls-files -co --exclude-standard | wc -l' n "$REPO")"
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

# ── checks ────────────────────────────────────────────────────────────────────────────────────

STRICT_REMEDY="drop --strict to treat no match as a result"

# no_stderr — an outcome is a result on stdout; stderr stays empty.
no_stderr() {
  [[ -z "$(exec_plain cat "${WORK}/stderr")" ]] || flunk "an outcome is a result on stdout, but stderr is not empty"
}

# check_zero_text STYLE — zero matches: exit 0, the header, a verdict starting `0 matches (searched N
# files` with git's file count, and no other line.
check_zero_text() {
  in_dir "$1" "$REPO" "search zz_absent_token --text"
  expect_status 0
  [[ "${lines[0]:-}" == "search: . [zz_absent_token]" ]] || flunk "header line: ${lines[0]:-<none>}"
  [[ "${lines[1]:-}" == "verdict: 0 matches (searched ${NSEARCHED} files"* ]] || flunk "verdict line: ${lines[1]:-<none>}"
  [[ ${#lines[@]} -eq 2 ]] || flunk "zero matches printed ${#lines[@]} lines, want 2 (header and verdict)"
  no_stderr
}

# check_zero_json STYLE — zero matches in JSON: exit 0, count 0, no lines, nothing truncated.
check_zero_json() {
  in_dir "$1" "$REPO" "search zz_absent_token"
  expect_status 0
  jfields exit count lines verdict truncated strict
  expect_j exit 0
  expect_j count 0
  expect_j lines "[]"
  expect_j truncated "<absent>"
  expect_j strict false
  [[ "$(jval verdict)" == "0 matches (searched ${NSEARCHED} files"* ]] || flunk "verdict: $(jval verdict)"
}

# check_strict_text STYLE — the same search with --strict: exit 1, the verdict says `no match (strict)`
# before the zero count, and `do instead:` follows.
check_strict_text() {
  in_dir "$1" "$REPO" "search zz_absent_token --strict --text"
  expect_status 1
  [[ "${lines[0]:-}" == "search: . [zz_absent_token]" ]] || flunk "header line: ${lines[0]:-<none>}"
  [[ "${lines[1]:-}" == "verdict: no match (strict): 0 matches (searched ${NSEARCHED} files"* ]] || flunk "verdict line: ${lines[1]:-<none>}"
  [[ "${lines[2]:-}" == "do instead: ${STRICT_REMEDY}" ]] || flunk "do-instead line: ${lines[2]:-<none>}"
  [[ ${#lines[@]} -eq 3 ]] || flunk "a strict no-match printed ${#lines[@]} lines, want 3"
  no_stderr
}

# check_strict_json STYLE — --strict in JSON: exit 1, count 0, the strict verdict and its remedy.
check_strict_json() {
  in_dir "$1" "$REPO" "search zz_absent_token --strict"
  expect_status 1
  jfields exit count verdict remedy strict
  expect_j exit 1
  expect_j count 0
  expect_j remedy "$STRICT_REMEDY"
  expect_j strict true
  [[ "$(jval verdict)" == "no match (strict): 0 matches (searched ${NSEARCHED} files"* ]] || flunk "verdict: $(jval verdict)"
}

# check_strict_with_hits STYLE — --strict changes only no-match: a search that finds hits still exits 0.
check_strict_with_hits() {
  local want
  want="$(exec_plain sh -c 'cd "$1" && git ls-files -co --exclude-standard -z | xargs -0 grep -h needle_fn | wc -l' n "$REPO")"
  in_dir "$1" "$REPO" "search needle_fn --strict"
  expect_status 0
  jfields exit count
  expect_j exit 0
  expect_j count "$want"
}

# check_missing_path STYLE [FLAG] — a PATH that does not exist exits 3 with `no such path: PATH`, with
# or without --strict: a failure, told apart from a no-match by its exit and its verdict.
check_missing_path() {
  local style="$1" flag="${2:-}"
  in_dir "$style" "$REPO" "search zz_absent_token no-such-dir ${flag} --text"
  expect_status 3
  [[ "${lines[0]:-}" == "search: no-such-dir [zz_absent_token]" ]] || flunk "header line: ${lines[0]:-<none>}"
  [[ "${lines[1]:-}" == "verdict: no such path: no-such-dir" ]] || flunk "verdict line: ${lines[1]:-<none>}"
  assert_no_line_matching '(0 matches|no match)' || flunk "a missing path reads as a no-match"
  no_stderr

  in_dir "$style" "$REPO" "search zz_absent_token no-such-dir ${flag}"
  expect_status 3
  jfields exit verdict
  expect_j exit 3
  expect_j verdict "no such path: no-such-dir"
}

@test "SC-4 a search with zero matches exits 0 with a zero-count header [bash -c, notty]" { check_zero_text c; }
@test "SC-4 a search with zero matches exits 0 with a zero-count header [bash -lc, notty]" { check_zero_text lc; }
@test "SC-4 a search with zero matches exits 0: JSON count 0 [bash -c, notty]" { check_zero_json c; }
@test "SC-4 a search with zero matches exits 0: JSON count 0 [bash -lc, notty]" { check_zero_json lc; }
@test "SC-4 a search with zero matches exits 1 only in strict mode, saying no match (strict) [bash -c, notty]" { check_strict_text c; }
@test "SC-4 a search with zero matches exits 1 only in strict mode, saying no match (strict) [bash -lc, notty]" { check_strict_text lc; }
@test "SC-4 a search with zero matches exits 1 only in strict mode: JSON count 0, exit 1 and the remedy [bash -c, notty]" { check_strict_json c; }
@test "SC-4 a search with zero matches exits 1 only in strict mode: JSON count 0, exit 1 and the remedy [bash -lc, notty]" { check_strict_json lc; }
@test "SC-4 exits 1 only in strict mode: a strict search that finds matches exits 0 [bash -c, notty]" { check_strict_with_hits c; }
@test "SC-4 exits 1 only in strict mode: a strict search that finds matches exits 0 [bash -lc, notty]" { check_strict_with_hits lc; }
@test "SC-4 a failure is distinguishable: a path that does not exist exits 3 with no such path [bash -c, notty]" { check_missing_path c; }
@test "SC-4 a failure is distinguishable: a path that does not exist exits 3 with no such path [bash -lc, notty]" { check_missing_path lc; }
@test "SC-4 a failure is distinguishable: a path that does not exist exits 3 even with --strict [bash -c, notty]" { check_missing_path c --strict; }
@test "SC-4 a failure is distinguishable: a path that does not exist exits 3 even with --strict [bash -lc, notty]" { check_missing_path lc --strict; }
