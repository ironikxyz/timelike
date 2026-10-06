#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# SC-2 — "Failures are parsed for pytest, jest or vitest, go test and cargo test; an unrecognised format
# falls back to the concluding-run verdict marked format unknown". (Feature 012, slice 1; spec
# Scenario 2, FR-1 to FR-5; contracts/verify-cli.md § test; research R1, R3, R7.)
#
# Written from the contract before the tool existed. Three parts:
#   1. pytest, REAL, in the image (pins.env PYTEST_VERSION through the image's uv, as SC-1; research
#      R1), here with `-q --tb=short`, the common flags the spec's Assumptions name;
#   2. jest, vitest, go test (with and without -v) and cargo test (with and without --no-fail-fast).
#      THESE RUNNERS ARE NOT IN THE IMAGE, AND NOTHING IS ADDED TO IT (spec seam 1). Their output is
#      REPLAYED: `verify test -- cat FILE`, where FILE is tests/fixtures/verify/recorded/NAME.out, the
#      real runner's output on make-project.sh's project, recorded on the host by record.sh. Each
#      recording's source (runner, version, command, exit, time) is in NAME.source beside it. It is
#      real output, not run in the image; the cycle report names this in not_verified. The exit
#      passed through is therefore cat's, 0;
#   3. an unknown format, from a command the image has (`sh -c`, exit 3): `run`'s verdict, marked
#      `format unknown`, the exit (3) passed through, counts null.
#
# Every expected value is the test's own (P005), read from the project make-project.sh writes into the
# cell (by the container's bash), never from what `verify` printed: the totals by counting the test
# definitions (`def test_`, `test(`, `func Test`, `#[test]`); the three failures by design (named in
# the generator's header), each one's line by grep in the generated test file; passed = total - 3. go
# test without -v reports no passes, so `passed` is null and the verdict says so, never `0 passed`.
#
# Isolation: each cell has its own workspace (a git repository holding the project) and its own
# TIMELIKE_SESSION (`vf2-<run id>-<check>-<style>`), checked to have no records before the cell
# starts. teardown_file removes this file's directory and this run's session directories (by that
# prefix) and nothing else. Cells: bash -c and bash -lc, `notty`.

load helpers

# This file's session prefix (sessions are `<prefix>-<run id>-<check>-<style>`).
SPREFIX=vf2
SDIR_NAME=verify-sc2

# The recordings replayed (tests/fixtures/verify/recorded/NAME.out).
RECORDINGS=(jest vitest go-test go-test-v cargo-test cargo-test-no-fail-fast)

setup_file() {
  setup_verify_file
  local r
  exec_plain mkdir "${SDIR}/recorded"
  for r in "${RECORDINGS[@]}"; do
    copy_into_container "${BATS_TEST_DIRNAME}/../fixtures/verify/recorded/${r}.out" "${SDIR}/recorded/${r}.out"
  done
}

teardown_file() {
  container_rm "${SDIR:-}"
  rm_sessions
}

# ── helpers (this file's own; the 012 files repeat them so each reads alone) ─────────────────────

# scratch_root — the container's session scratch root, read in the container, never assumed.
scratch_root() {
  local r
  r="$(exec_plain sh -c 'printf "%s" "${TIMELIKE_SCRATCH_ROOT:-/tmp/timelike}"')" || return 1
  [[ "$r" == /?* ]] || { echo "scratch root in the container: '${r}'" >&2; return 1; }
  printf '%s' "$r"
}

# rm_sessions — remove this run's session directories (SROOT/SPREFIX-RUN_ID-*) and nothing else.
rm_sessions() {
  [[ -n "${RUN_ID:-}" && "${SROOT:-}" == /tmp/?* ]] || return 0
  exec_plain sh -c 'for d in "$1/$2-$3-"*; do [ -d "$d" ] && rm -rf -- "$d"; done; exit 0' \
    rm "$SROOT" "$SPREFIX" "$RUN_ID" >/dev/null 2>&1 || true
}

# setup_verify_file — this file's directory in the container (SDIR), the generator copied into it,
# and, unless NO_WRAPPERS is set, the real pytest, ruff and mypy wrappers in SDIR/bin (WRAP).
setup_verify_file() {
  stamp_check
  SDIR="$(container_tmpdir "$SDIR_NAME")"
  RUN_ID="${SDIR##*.}"
  SROOT="$(scratch_root)"
  WRAP="${SDIR}/bin"
  export SDIR RUN_ID SROOT WRAP
  copy_into_container "${BATS_TEST_DIRNAME}/../fixtures/verify/make-project.sh" "${SDIR}/make-project.sh" 0755
  if [[ -z "${NO_WRAPPERS:-}" ]]; then
    install_uv_tool_wrappers "$WRAP"
  fi
}

# new_cell NAME STYLE — this cell's workspace (CELL: a fresh directory; CELL.stderr beside it, outside
# the workspace) and its own session (SESSION), which must have no records yet.
new_cell() {
  CELL="${SDIR}/$1-$2"
  SESSION="${SPREFIX}-${RUN_ID}-$1-$2"
  exec_plain mkdir "$CELL" || { echo "cell path ${CELL} exists: cells must not share a workspace" >&2; return 1; }
  if exec_plain test -e "${SROOT}/${SESSION}"; then
    echo "session ${SESSION} already has records: cells must not share a session" >&2
    return 1
  fi
}

# put RELPATH CONTENT — write CONTENT and a final newline to CELL/RELPATH with the container's printf
# (P005), making its directory first.
put() {
  exec_plain sh -c 'mkdir -p "$(dirname "$1")" && printf "%s\n" "$2" >"$1"' put "${CELL}/$1" "$2"
}

# gen KIND — make-project.sh KIND, run by the container's bash, writes the project into CELL.
gen() {
  local out
  out="$(exec_plain bash "${SDIR}/make-project.sh" "$1" "$CELL" 2>&1)" ||
    { printf 'make-project.sh %s failed:\n%s\n' "$1" "$out" >&2; return 1; }
}

# git_init — make CELL a git repository (the workspace root), with a local identity only.
git_init() {
  local out
  out="$(exec_plain sh -c 'cd "$1" && git init -q && git config user.name e2e &&
    git config user.email e2e@example.invalid && git config commit.gpgsign false' gi "$CELL" 2>&1)" ||
    { printf 'git init in %s failed:\n%s\n' "$CELL" "$out" >&2; return 1; }
}

# git_commit_all — commit everything in CELL (hooks not run: the fixture is not under test).
git_commit_all() {
  local out
  out="$(exec_plain sh -c 'cd "$1" && git add -A && git commit -q --no-verify -m fixture' gc "$CELL" 2>&1)" ||
    { printf 'git commit in %s failed:\n%s\n' "$CELL" "$out" >&2; return 1; }
}

# line_of RELPATH TEXT — the line number of the one line of CELL/RELPATH containing TEXT (fixed
# string), read by grep in the container. Fails unless exactly one line contains it.
line_of() {
  local got
  got="$(exec_plain grep -nF -- "$2" "${CELL}/$1" | cut -d: -f1)" || true
  [[ "$got" =~ ^[0-9]+$ ]] || { printf 'line_of %s: want one line containing %q, got: %s\n' "$1" "$2" "${got:-none}" >&2; return 1; }
  printf '%s' "$got"
}

# in_session [-e K=V]... STYLE CMD — run CMD in the workspace as the agent would, in this cell's
# session, with the wrappers first on PATH (set in the command string, after any startup file);
# stderr goes to CELL.stderr so stdout stays one document.
in_session() {
  local -a envs=()
  while [[ "${1:-}" == -e ]]; do
    envs+=(-e "$2")
    shift 2
  done
  run_in -e "TIMELIKE_SESSION=${SESSION}" "${envs[@]}" "$1" notty \
    "{ cd '${CELL}' && export PATH='${WRAP}':\"\$PATH\" && $2; } 2>>'${CELL}.stderr'"
  assert_within 25
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
# dotted path, top-level first, then under `data`; `rel(p)` strips the workspace (WS) from a path, so
# a path given absolute, relative or as ./relative compares the same; `cmd_paths(c)` is the set of path arguments
# (ending .py) of a command given as a list or a string, each through rel. Output in $JPY.
jpy() {
  JPY="$(printf '%s' "$output" | pyq "import json,sys
WS='${CELL}'
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
def rel(p):
    p = str(p)
    p = p[2:] if p.startswith('./') else p
    return p[len(WS) + 1:] if p.startswith(WS + '/') else p
def cmd_paths(c):
    words = c if isinstance(c, list) else str(c).split()
    return sorted({rel(w) for w in words if str(w).endswith('.py')})
$1")" || flunk "stdout is not the JSON expected"
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

# expect_has WHAT TEXT PART… — TEXT contains every PART.
expect_has() {
  local what="$1" text="$2" part
  shift 2
  for part in "$@"; do
    [[ "$text" == *"$part"* ]] || flunk "${what} does not name '${part}': ${text}"
  done
}

# text_line PREFIX — the first line of the last run's output starting with PREFIX (or nothing).
text_line() {
  local line
  for line in "${lines[@]}"; do
    if [[ "$line" == "$1"* ]]; then
      printf '%s' "$line"
      return 0
    fi
  done
}

# body_lines — the last run's text lines after the `verdict:` line, blank lines dropped, into BODY.
body_lines() {
  local line seen=0
  BODY=()
  for line in "${lines[@]}"; do
    if ((seen)); then
      [[ -n "${line// /}" ]] && BODY+=("$line")
    elif [[ "$line" == "verdict: "* ]]; then
      seen=1
    fi
  done
  ((seen)) || flunk "no verdict: line in the text output"
}

# expect_failures ENTRY… — the last run's JSON `failures` are exactly these, one per ENTRY, each
# `TEST|FILE|LINE|TEXT`: one failure whose `test` contains TEST, at FILE (relative to the workspace)
# and LINE, with 1 to 5 assertion `lines`, one of which contains TEXT (when TEXT is not empty).
# ENTRY must hold no single quote or backslash (it is spliced into Python as a literal).
expect_failures() {
  local e list=""
  for e in "$@"; do
    list+="'${e}',"
  done
  jpy "exp = [e.split('|') for e in [${list}]]
fs = g('failures', []) or []
problems = []
if len(fs) != len(exp):
    problems.append('%d failures reported, want %d: %s' % (len(fs), len(exp), [x.get('test') for x in fs if isinstance(x, dict)]))
for t, f, l, txt in exp:
    m = [x for x in fs if isinstance(x, dict) and t in str(x.get('test'))]
    if len(m) != 1:
        problems.append('%s: named by %d failures' % (t, len(m)))
        continue
    x = m[0]
    if rel(x.get('file')) != f or str(x.get('line')) != l:
        problems.append('%s: at %s:%s, want %s:%s' % (t, x.get('file'), x.get('line'), f, l))
    ls = x.get('lines')
    if not isinstance(ls, list) or not 1 <= len(ls) <= 5:
        problems.append('%s: lines %r, want 1 to 5 assertion lines' % (t, ls))
    elif txt and not any(txt in str(s) for s in ls):
        problems.append('%s: no assertion line contains %r: %r' % (t, txt, ls))
print('problems=' + json.dumps(problems))"
  expect_j problems '[]'
}

# count_in RELPATH ERE — the number of lines of CELL/RELPATH matching ERE, read in the container.
count_in() {
  local n
  n="$(exec_plain grep -cE -- "$2" "${CELL}/$1")" || true
  [[ "$n" =~ ^[0-9]+$ ]] || { echo "count_in ${1}: '${n}'" >&2; return 1; }
  printf '%s' "$n"
}

# entry TEST FILE TEXT [ASSERTION] — one expect_failures entry, its line read from the fixture.
entry() {
  local line
  line="$(line_of "$2" "$3")" || flunk "the fixture has no single line '${3}' in ${2}"
  ENTRIES+=("${1}|${2}|${line}|${4:-}")
}

# expect_report FORMAT FAILED PASSED VERDICT_PART — scope, format, counts and verdict of the last run.
# PASSED is a number or `null`.
expect_report() {
  jpy "print('scope=' + str(g('scope')))
print('format=' + str(g('format')))
print('failed=' + json.dumps(g('counts.failed')))
print('passed=' + json.dumps(g('counts.passed')))
print('command_exit=' + json.dumps(g('run.command_exit')))
print('verdict=' + str(g('verdict')))"
  expect_j scope "$1"
  expect_j format "$1"
  expect_j failed "$2"
  expect_j passed "$3"
  expect_has "the verdict" "$(jval verdict)" "$4"
}

# ── checks ────────────────────────────────────────────────────────────────────────────────────

# check_pytest STYLE — REAL pytest in the image, -q --tb=short: counts and the three failures.
check_pytest() {
  new_cell pytest "$1"
  gen pytest
  git_init
  local total
  total="$(exec_plain sh -c 'cd "$1" && cat tests/*.py | grep -c "^def test_"' n "$CELL")" || flunk "cannot count the fixture's tests"
  ENTRIES=()
  entry tests/test_models.py::test_total_rounds tests/test_models.py 'assert order.total() == 4' 'assert 3 == 4'
  entry tests/test_orders.py::test_checkout_total_is_wrong tests/test_orders.py 'assert checkout([100, 100]) == 300' 'assert 200 == 300'
  entry tests/test_orders.py::test_checkout_empty tests/test_orders.py 'assert checkout([]) == 0' 'ValueError: empty order'
  in_session "$1" "verify test -- pytest -q --tb=short"
  expect_status 1
  expect_report pytest 3 "$((total - 3))" "3 failed, $((total - 3)) passed (pytest)"
  expect_j command_exit 1
  expect_failures "${ENTRIES[@]}"
}

# check_replay NAME STYLE — the recording NAME (real output of a runner the image does not have)
# replayed through `verify test -- cat`, in a cell holding the project it was recorded on.
check_replay() {
  local name="$1" kind format total passed verdict
  case "$name" in
    jest | vitest) kind="$name" ;;
    go-test | go-test-v) kind=go ;;
    cargo-test | cargo-test-no-fail-fast) kind=cargo ;;
    *) flunk "no expectations for recording ${name}" ;;
  esac
  new_cell "$name" "$2"
  gen "$kind"
  git_init
  ENTRIES=()
  case "$name" in
    jest | vitest)
      format="$name"
      total="$(count_in math.test.js '^test\(')" || flunk "cannot count the fixture's tests"
      entry 'adds wrongly' math.test.js 'expect(add(2, 2)).toBe(5);'
      entry 'parses into the wrong shape' math.test.js "expect(parse('4')).toEqual({ value: 4, unit: 'cm' });"
      entry 'rejects text' math.test.js "parse('abc');" 'not a number: abc'
      ;;
    go-test | go-test-v)
      format=go
      total="$(count_in calc_test.go '^func Test')" || flunk "cannot count the fixture's tests"
      entry TestAddWrongly calc_test.go 't.Errorf("Add(2, 2) = %d, want 5", got)' 'want 5'
      entry TestParseText calc_test.go 't.Fatalf("Parse(\"abc\"): %v", err)' 'invalid syntax'
      # The subtest is the failure; its parent fails only through it and is not reported (R3).
      entry TestTable/2+2 calc_test.go 't.Errorf("Add(%d, %d) = %d, want %d", c.a, c.b, got, c.want)' 'want 5'
      ;;
    cargo-test | cargo-test-no-fail-fast)
      format=cargo
      total="$(count_in src/lib.rs '#\[test\]')" || flunk "cannot count the fixture's tests"
      if [[ "$name" == cargo-test-no-fail-fast ]]; then
        # --no-fail-fast also runs the integration tests (all passing); a plain run stops after the
        # failing unit-test binary.
        local integration
        integration="$(count_in tests/integration.rs '#\[test\]')" || flunk "cannot count the integration tests"
        total=$((total + integration))
      fi
      entry tests::adds_wrongly src/lib.rs 'assert_eq!(add(2, 2), 5);'
      entry tests::gives_up src/lib.rs 'panic!("not implemented yet");' 'not implemented yet'
      entry tests::parses_text src/lib.rs 'assert!(parse("abc").is_some(), "abc should parse");' 'abc should parse'
      ;;
  esac
  passed=$((total - ${#ENTRIES[@]}))
  verdict="3 failed, ${passed} passed (${format})"
  if [[ "$name" == go-test ]]; then
    passed=null
    verdict="3 failed, passes not reported (go test without -v)"
  fi
  in_session "$2" "verify test -- cat '${SDIR}/recorded/${name}.out'"
  expect_status 0
  expect_report "$format" 3 "$passed" "$verdict"
  expect_j command_exit 0
  if [[ "$passed" == null ]]; then
    [[ "$(jval verdict)" != *"0 passed"* ]] || flunk "go test without -v reports no passes, and the verdict says 0 passed"
  fi
  expect_failures "${ENTRIES[@]}"
}

UNKNOWN_CMD="sh -c 'echo hello from the fixture; echo second line; exit 3'"
UNKNOWN_CLAUSE='format unknown: no pytest, jest, vitest, go test or cargo test summary'

# check_unknown_json STYLE — no runner's summary: run's verdict, marked format unknown; exit 3 passed
# through; counts null (not zero) and no failures.
check_unknown_json() {
  new_cell unknown-json "$1"
  git_init
  in_session "$1" "verify test -- ${UNKNOWN_CMD}"
  expect_status 3
  jpy "v = str(g('verdict'))
rv = g('run.verdict')
print('scope=' + str(g('scope')))
print('format=' + str(g('format')))
print('counts=' + json.dumps([g('counts.failed', 0), g('counts.passed', 0)]))
print('failures=' + json.dumps(g('failures', [])))
print('run_exit=' + json.dumps(g('run.exit')))
print('command_exit=' + json.dumps(g('run.command_exit')))
print('run_verdict=' + str(rv))
# Amended at implement: the clause comes first (rule 13's cut never takes it), then run's verdict as
# verify words every format's: run's own parts, its line count dropped. Its exit and log are there.
log = str(g('run.log') or '')
clause = 'format unknown: no pytest, jest, vitest, go test or cargo test summary'
print('starts_with_run=' + json.dumps(isinstance(rv, str) and bool(rv) and v.startswith(clause + ' · exit 3') and bool(log) and ('log ' + log) in v))
print('verdict=' + v)"
  expect_j scope 'format unknown'
  expect_j format unknown
  expect_j counts '[null, null]'
  expect_j failures '[]'
  expect_j run_exit 3
  expect_j command_exit 3
  expect_has "run's verdict" "$(jval run_verdict)" "exit 3"
  expect_j starts_with_run true
  expect_has "the verdict" "$(jval verdict)" "$UNKNOWN_CLAUSE"
}

# check_unknown_text STYLE — the text view: header scope, verdict, and run's bounded lines as the body.
check_unknown_text() {
  new_cell unknown-text "$1"
  git_init
  in_session "$1" "verify --text test -- ${UNKNOWN_CMD}"
  expect_status 3
  # The header's target is the command, shell-quoted (contract § test, amended at implement).
  [[ "${lines[0]:-}" == "verify: sh -c "* && "${lines[0]}" == *"[format unknown]" ]] || flunk "the first line is not the header 'verify: sh -c … [format unknown]'"
  expect_has "the verdict" "$(text_line "verdict: ")" "exit 3" "$UNKNOWN_CLAUSE"
  body_lines
  expect_has "the body" "$(printf '%s\n' "${BODY[@]}")" "hello from the fixture" "second line"
}

@test "SC-2 [bash -c, notty] pytest (real, in the image, -q --tb=short): counts and the three failures with file, line and assertion lines" { check_pytest c; }
@test "SC-2 [bash -lc, notty] pytest (real, in the image, -q --tb=short): counts and the three failures with file, line and assertion lines" { check_pytest lc; }
@test "SC-2 [bash -c, notty] jest (recorded output replayed; jest is not in the image): 3 failed, 9 passed, each failure located" { check_replay jest c; }
@test "SC-2 [bash -lc, notty] jest (recorded output replayed; jest is not in the image): 3 failed, 9 passed, each failure located" { check_replay jest lc; }
@test "SC-2 [bash -c, notty] vitest (recorded output replayed; vitest is not in the image): 3 failed, 9 passed, each failure located" { check_replay vitest c; }
@test "SC-2 [bash -lc, notty] vitest (recorded output replayed; vitest is not in the image): 3 failed, 9 passed, each failure located" { check_replay vitest lc; }
@test "SC-2 [bash -c, notty] go test (recorded output replayed; go is not in the image): 3 failed, passes not reported, the subtest located" { check_replay go-test c; }
@test "SC-2 [bash -lc, notty] go test (recorded output replayed; go is not in the image): 3 failed, passes not reported, the subtest located" { check_replay go-test lc; }
@test "SC-2 [bash -c, notty] go test -v (recorded output replayed; go is not in the image): 3 failed, 9 passed, each failure located" { check_replay go-test-v c; }
@test "SC-2 [bash -lc, notty] go test -v (recorded output replayed; go is not in the image): 3 failed, 9 passed, each failure located" { check_replay go-test-v lc; }
@test "SC-2 [bash -c, notty] cargo test (recorded output replayed; cargo is not in the image): 3 failed, 9 passed, each panic located" { check_replay cargo-test c; }
@test "SC-2 [bash -lc, notty] cargo test (recorded output replayed; cargo is not in the image): 3 failed, 9 passed, each panic located" { check_replay cargo-test lc; }
@test "SC-2 [bash -c, notty] cargo test --no-fail-fast (recorded output replayed): every binary's result summed, 3 failed, 11 passed" { check_replay cargo-test-no-fail-fast c; }
@test "SC-2 [bash -lc, notty] cargo test --no-fail-fast (recorded output replayed): every binary's result summed, 3 failed, 11 passed" { check_replay cargo-test-no-fail-fast lc; }
@test "SC-2 [bash -c, notty] an unrecognised format falls back to the concluding-run verdict marked format unknown — JSON: exit 3 passed through, counts null" { check_unknown_json c; }
@test "SC-2 [bash -lc, notty] an unrecognised format falls back to the concluding-run verdict marked format unknown — JSON: exit 3 passed through, counts null" { check_unknown_json lc; }
@test "SC-2 [bash -c, notty] an unrecognised format falls back to the concluding-run verdict marked format unknown — text: run's lines as the body" { check_unknown_text c; }
@test "SC-2 [bash -lc, notty] an unrecognised format falls back to the concluding-run verdict marked format unknown — text: run's lines as the body" { check_unknown_text lc; }
