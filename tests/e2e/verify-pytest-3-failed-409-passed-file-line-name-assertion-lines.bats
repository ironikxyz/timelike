#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# SC-1 — "Running a pytest suite with 3 failing and 409 passing tests reports "3 failed, 409 passed"
# and, for each failure, its file, line, test name and first assertion lines". (Feature 012, slice 1;
# spec Scenario 1, FR-1 to FR-3, FR-5; contracts/verify-cli.md § test; research R1, R3, R7.)
#
# Written from the contract before the tool existed. The suite is REAL pytest (pins.env PYTEST_VERSION)
# in the agent image, run by the image's uv through the wrappers helpers.bash installs (research R1):
# the image itself has no pytest. It needs PyPI, as the lane's unit step does.
#
# Every expected value is the test's own (P005), read from the project tests/fixtures/verify/make-project.sh
# writes into the cell (by the container's bash), never from what `verify` printed:
#   - the total is the number of `def test_` lines in its tests/ (412);
#   - the three failures are the generator's, each by design: `Order([1, 2]).total()` is 3, not 4;
#     `checkout([100, 100])` rounds 200 to 200, not 300; `checkout([])` raises ValueError("empty
#     order"). Each one's line is found by grep in the generated file: the failing assert in the
#     test file (for the ValueError, the test's own frame, not app/orders.py's);
#   - passed = total - 3 (409); exit 1 is pytest's own, passed through;
#   - no passing test is named anywhere in the output: the 409 names, read from the fixture, are
#     matched as whole words.
#
# Isolation: each cell has its own workspace (a git repository holding the project) and its own
# TIMELIKE_SESSION (`vf1-<run id>-<check>-<style>`), checked to have no records before the cell
# starts. teardown_file removes this file's directory and this run's session directories (by that
# prefix) and nothing else. Cells: bash -c and bash -lc, `notty`.

load helpers

# This file's session prefix (sessions are `<prefix>-<run id>-<check>-<style>`).
SPREFIX=vf1
SDIR_NAME=verify-sc1

setup_file() {
  setup_verify_file
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
  local jpy_rc=0 jpy_err="${BATS_TEST_TMPDIR}/jpy.stderr" jpy_t0
  jpy_t0="$(now_ms)"
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
$1" 2>"$jpy_err")" || jpy_rc=$?
  # Say why the parser failed (lanes batch-b and batch-c, not ok 432 and 448): its exit, its time, a
  # timeout by name, its stderr. "Timed out" is decided by elapsed time against PYQ_TIMEOUT, because
  # the runner's BusyBox timeout reports the killed command's 143, never 124 (helpers.bash).
  if ((jpy_rc != 0)); then
    local jpy_ms=$(($(now_ms) - jpy_t0))
    local why="the parser (pyq) exited ${jpy_rc} after ${jpy_ms} ms"
    ((jpy_ms >= PYQ_TIMEOUT * 1000)) && why+=": killed by its timeout (PYQ_TIMEOUT=${PYQ_TIMEOUT} s)"
    flunk "stdout is not the JSON expected — ${why}; its stderr: $(cat "$jpy_err" 2>/dev/null)"
  fi
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

# ── fixture ───────────────────────────────────────────────────────────────────────────────────

# The generator's three failing tests: node id, test file, the failing line's text, an assertion text.
FAILING=(
  "tests/test_models.py::test_total_rounds|tests/test_models.py|assert order.total() == 4|assert 3 == 4"
  "tests/test_orders.py::test_checkout_total_is_wrong|tests/test_orders.py|assert checkout([100, 100]) == 300|assert 200 == 300"
  "tests/test_orders.py::test_checkout_empty|tests/test_orders.py|assert checkout([]) == 0|ValueError: empty order"
)

# new_suite_cell NAME STYLE — the pytest project in a fresh repository; sets ENTRIES (expect_failures'
# form, lines read by grep), TOTAL and PASSED (from the fixture's own test definitions) and
# PASSING_FILE (the passing tests' names, one per line, on the runner side).
new_suite_cell() {
  new_cell "$1" "$2"
  gen pytest
  git_init
  local f id file text assertion line names
  ENTRIES=()
  for f in "${FAILING[@]}"; do
    IFS='|' read -r id file text assertion <<<"$f"
    line="$(line_of "$file" "$text")" || flunk "the fixture has no single line '${text}' in ${file}"
    ENTRIES+=("${id}|${file}|${line}|${assertion}")
  done
  names="$(exec_plain sh -c 'cd "$1" && grep -ho "^def test_[A-Za-z0-9_]*" tests/*.py | sed "s/^def //"' n "$CELL")" ||
    flunk "cannot list the fixture's tests"
  TOTAL="$(grep -c . <<<"$names")"
  ((TOTAL == 412)) || flunk "the fixture defines ${TOTAL} tests, the generator's header says 412"
  PASSED=$((TOTAL - ${#FAILING[@]}))
  PASSING_FILE="${BATS_TEST_TMPDIR}/passing-names"
  grep -vxF -e test_total_rounds -e test_checkout_total_is_wrong -e test_checkout_empty <<<"$names" >"$PASSING_FILE"
  (($(grep -c . "$PASSING_FILE") == PASSED)) || flunk "passing names: want ${PASSED}"
}

# expect_no_passing_test — no passing test's name appears in the output (whole words).
expect_no_passing_test() {
  local hit
  hit="$(grep -Fwo -f "$PASSING_FILE" <<<"$output" | head -n 3)" || true
  [[ -z "$hit" ]] || flunk "a passing test is shown: ${hit//$'\n'/, }"
}

# ── checks ────────────────────────────────────────────────────────────────────────────────────

# check_json STYLE — the harness default (stdout a pipe → JSON): counts, the three failures, the exit.
check_json() {
  new_suite_cell json "$1"
  in_session "$1" "verify test -- pytest"
  expect_status 1
  jpy "print('scope=' + str(g('scope')))
print('format=' + str(g('format')))
print('failed=' + json.dumps(g('counts.failed')))
print('passed=' + json.dumps(g('counts.passed')))
print('run_exit=' + json.dumps(g('run.exit')))
print('command_exit=' + json.dumps(g('run.command_exit')))
print('verdict=' + str(g('verdict')))"
  expect_j scope pytest
  expect_j format pytest
  expect_j failed 3
  expect_j passed "$PASSED"
  expect_j run_exit 1
  expect_j command_exit 1
  expect_has "the verdict" "$(jval verdict)" "3 failed, ${PASSED} passed (pytest)" "exit 1"
  expect_failures "${ENTRIES[@]}"
  expect_no_passing_test
}

# check_text STYLE — the text view: header, verdict, one block per failure (FILE:LINE and the test's
# name, then its assertion lines indented under it), and not one passing test.
check_text() {
  new_suite_cell text "$1"
  in_session "$1" "verify --text test -- pytest"
  expect_status 1
  # The header's target is the command, shell-quoted (contract § test, amended at implement), as run's is.
  [[ "${lines[0]:-}" == "verify: pytest [pytest]" ]] || flunk "the first line is not the header 'verify: pytest [pytest]'"
  local verdict
  verdict="$(text_line "verdict: ")"
  expect_has "the verdict" "$verdict" "3 failed, ${PASSED} passed (pytest)" "exit 1"
  body_lines
  local e id file line assertion i j found block
  for e in "${ENTRIES[@]}"; do
    IFS='|' read -r id file line assertion <<<"$e"
    found=-1
    for i in "${!BODY[@]}"; do
      if [[ "${BODY[$i]}" =~ ^${file//./\\.}:${line}[[:space:]] && "${BODY[$i]}" == *"${id##*::}"* ]]; then
        found=$i
        break
      fi
    done
    ((found >= 0)) || flunk "no block starts '${file}:${line}  … ${id##*::}'"
    block=""
    for ((j = found + 1; j < ${#BODY[@]}; j++)); do
      [[ "${BODY[$j]}" =~ ^[[:space:]] ]] || break
      block+="${BODY[$j]}"$'\n'
    done
    [[ -n "$block" ]] || flunk "the block for ${id} has no indented assertion lines"
    expect_has "the block for ${id}" "$block" "$assertion"
  done
  expect_no_passing_test
  assert_no_line_matching '\[ *[0-9]+%\]' || flunk "pytest's progress lines are shown"
}

@test "SC-1 [bash -c, notty] Running a pytest suite with 3 failing and 409 passing tests reports \"3 failed, 409 passed\" and, for each failure, its file, line, test name and first assertion lines — JSON, real pytest, exit 1 passed through" { check_json c; }
@test "SC-1 [bash -lc, notty] Running a pytest suite with 3 failing and 409 passing tests reports \"3 failed, 409 passed\" and, for each failure, its file, line, test name and first assertion lines — JSON, real pytest, exit 1 passed through" { check_json lc; }
@test "SC-1 [bash -c, notty] Running a pytest suite with 3 failing and 409 passing tests reports \"3 failed, 409 passed\" and, for each failure, its file, line, test name and first assertion lines — text: one block per failure, no passing test shown" { check_text c; }
@test "SC-1 [bash -lc, notty] Running a pytest suite with 3 failing and 409 passing tests reports \"3 failed, 409 passed\" and, for each failure, its file, line, test name and first assertion lines — text: one block per failure, no passing test shown" { check_text lc; }
