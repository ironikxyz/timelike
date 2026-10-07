#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# SC-3 — "With one changed source file, the changed-only check runs the tests that import it and lints
# and type-checks only changed files, and states which were selected and why". (Feature 012, slice 1;
# spec Scenario 3, FR-6 to FR-11; contracts/verify-cli.md § changed; research R1, R4, R5, R7.)
#
# Written from the contract before the tool existed. pytest, ruff and mypy are REAL, in the image, at
# the pins.env versions, through the wrappers helpers.bash installs (research R1); the image has none
# of them. They need PyPI, as the lane's unit and lint steps do.
#
# The project is make-project.sh's pytest project (written by the container's bash), plus one file of
# this test's own, app/legacy.py, which carries a ruff finding and a mypy error and is imported by
# nobody. All of it is committed. Then ONE source file changes, app/models.py: an unused `import os`
# at its top (ruff F401 at line 1) and a function whose `-> int` returns a str (one mypy error). Neither
# changes what any test does. Every expected value is the test's own (P005), read from that project:
#   - selected tests: exactly tests/test_models.py (it imports app/models.py) and tests/test_orders.py
#     (it imports app/orders.py, which imports app/models.py); never tests/test_cli.py, which imports
#     only app/cli.py;
#   - pytest ran on those two files only: their `def test_` count (12), 3 of them failing by the
#     generator's design (SC-1's three), never the suite's 412;
#   - ruff and mypy ran on app/models.py only: no other path in their commands, and no finding in
#     app/legacy.py, which a whole-project lint or type-check would report. Each finding's line is read
#     by grep in the edited file;
#   - the exit is 1: a step failed (FR-11; several commands cannot pass one exit through).
#
# Isolation: each cell has its own workspace (a git repository holding the project) and its own
# TIMELIKE_SESSION (`vf3-<run id>-<check>-<style>`), checked to have no records before the cell
# starts. teardown_file removes this file's directory and this run's session directories (by that
# prefix) and nothing else. Cells: bash -c and bash -lc, `notty`.

load helpers

# This file's session prefix (sessions are `<prefix>-<run id>-<check>-<style>`).
SPREFIX=vf3
SDIR_NAME=verify-sc3

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

# ── fixture ───────────────────────────────────────────────────────────────────────────────────

# Committed, unchanged, imported by nobody: a whole-project ruff or mypy run would report it.
LEGACY_PY="$(
  cat <<'PY'
import sys


def legacy() -> int:
    return "legacy"
PY
)"

# Appended to app/models.py by the change: mypy reports its return line; nothing calls it.
LABEL_PY="$(
  cat <<'PY'


def label() -> int:
    return "label"
PY
)"

# The selection, by hand: test file, reason (contract § changed, the reason column).
SELECTED=(
  "tests/test_models.py|imports app/models.py"
  "tests/test_orders.py|imports app/orders.py, which imports app/models.py"
)

# new_changed_cell NAME STYLE — the committed project, then the one change to app/models.py. Sets
# TESTS_IN_SELECTION (the selected files' own test count), RUFF_LINE and MYPY_LINE (grep), and
# checks the precondition with git itself: exactly one changed path.
new_changed_cell() {
  new_cell "$1" "$2"
  gen pytest
  put app/legacy.py "$LEGACY_PY"
  git_init
  git_commit_all
  # Two blank lines after the import, so the only lint finding is the unused import whatever ruff selects (I001 too).
  exec_plain sh -c 'cd "$1" && { printf "import os\n\n\n"; cat app/models.py; printf "%s\n" "$2"; } >app/models.py.new &&
    mv app/models.py.new app/models.py' edit "$CELL" "$LABEL_PY" || flunk "could not edit app/models.py"
  local st
  st="$(exec_plain git -C "$CELL" status --porcelain --untracked-files=all)" || flunk "git status failed"
  [[ "$st" == " M app/models.py" ]] || flunk "the precondition is one modified file, git status says: ${st}"
  TESTS_IN_SELECTION="$(exec_plain sh -c 'cd "$1" && cat tests/test_models.py tests/test_orders.py | grep -c "^def test_"' n "$CELL")" ||
    flunk "cannot count the selected files' tests"
  RUFF_LINE="$(line_of app/models.py 'import os')" || flunk "no single 'import os' line"
  MYPY_LINE="$(line_of app/models.py 'return "label"')" || flunk "no single 'return \"label\"' line"
}

# py_words LINE — the words of LINE ending in .py, sorted, space-separated.
py_words() {
  local w
  local -a out=()
  for w in $1; do
    [[ "$w" == *.py ]] && out+=("$w")
  done
  printf '%s\n' "${out[@]}" | sort | tr '\n' ' ' | sed 's/ $//'
}

# ── checks ────────────────────────────────────────────────────────────────────────────────────

# check_json STYLE — the JSON data: what changed, what was selected and why, and each step's command,
# exit and findings.
check_json() {
  new_changed_cell json "$1"
  in_session "$1" "verify changed"
  expect_status 1
  local want="" s
  for s in "${SELECTED[@]}"; do
    want+="'${s}',"
  done
  jpy "want = sorted(tuple(s.split('|')) for s in [${want}])
sel = g('selected', {}) or {}
print('changed=' + json.dumps(sorted([rel(c.get('path')), c.get('status')] for c in (g('changed', []) or []))))
print('tests=' + json.dumps(sorted((rel(t.get('path')), t.get('reason')) for t in (sel.get('tests') or [])) == want))
print('tests_got=' + json.dumps([[rel(t.get('path')), t.get('reason')] for t in (sel.get('tests') or [])]))
print('runners=' + json.dumps(sorted({t.get('runner') for t in (sel.get('tests') or [])})))
print('lint=' + json.dumps([rel(p) for p in (sel.get('lint') or [])]))
print('typecheck=' + json.dumps([rel(p) for p in (sel.get('typecheck') or [])]))
print('untested=' + json.dumps(sel.get('untested')))
steps = g('steps', []) or []
print('tools=' + json.dumps([s.get('tool') for s in steps]))
for s in steps:
    t = s.get('tool')
    rep = s.get('report') or {}
    fs = rep.get('failures') or []
    print(t + '_paths=' + json.dumps(cmd_paths(s.get('command'))))
    print(t + '_exit=' + json.dumps(s.get('exit')))
    print(t + '_state=' + str(s.get('state')))
    print(t + '_counts=' + json.dumps([(rep.get('counts') or {}).get('failed'), (rep.get('counts') or {}).get('passed')]))
    print(t + '_at=' + json.dumps(sorted({'%s:%s' % (rel(f.get('file')), f.get('line')) for f in fs})))
    print(t + '_tests=' + json.dumps(sorted(str(f.get('test')) for f in fs)))
print('names_cli=' + json.dumps('test_cli' in json.dumps(d)))
print('names_legacy=' + json.dumps('legacy.py' in json.dumps(steps)))"
  expect_j changed '[["app/models.py", "modified"]]'
  expect_j tests true || flunk "selected tests: $(jval tests_got)"
  expect_j runners '["pytest"]'
  expect_j lint '["app/models.py"]'
  expect_j typecheck '["app/models.py"]'
  expect_j untested '[]'
  expect_j tools '["pytest", "ruff", "mypy"]'
  expect_j pytest_paths '["tests/test_models.py", "tests/test_orders.py"]'
  expect_j pytest_exit 1
  expect_j pytest_counts "[3, $((TESTS_IN_SELECTION - 3))]"
  expect_j pytest_tests '["tests/test_models.py::test_total_rounds", "tests/test_orders.py::test_checkout_empty", "tests/test_orders.py::test_checkout_total_is_wrong"]'
  expect_j ruff_paths '["app/models.py"]'
  expect_j ruff_exit 1
  expect_j ruff_at "[\"app/models.py:${RUFF_LINE}\"]"
  expect_j mypy_paths '["app/models.py"]'
  expect_j mypy_exit 1
  expect_j mypy_at "[\"app/models.py:${MYPY_LINE}\"]"
  [[ "$(jval pytest_state)" == "3 failed"* ]] || flunk "pytest's state: $(jval pytest_state)"
  [[ "$(jval ruff_state)" == "1 diagnostic"* ]] || flunk "ruff's state: $(jval ruff_state)"
  [[ "$(jval mypy_state)" == "1 diagnostic"* ]] || flunk "mypy's state: $(jval mypy_state)"
  expect_j names_cli false || flunk "tests/test_cli.py is named: it imports nothing that changed"
  expect_j names_legacy false || flunk "a step names app/legacy.py: lint or type-check went beyond the changed file"
}

# check_text STYLE — the text view states the selection and why, then each step's command and findings.
check_text() {
  new_changed_cell text "$1"
  in_session "$1" "verify --text changed"
  expect_status 1
  [[ "${lines[0]:-}" == "verify: changed against HEAD [2 tests, 1 lint, 1 type-check]" ]] ||
    flunk "the header is not 'verify: changed against HEAD [2 tests, 1 lint, 1 type-check]'"
  expect_has "the verdict" "$(text_line "verdict: ")" "1 changed file" "2 test files" "superset" \
    "pytest: 3 failed, $((TESTS_IN_SELECTION - 3)) passed" "ruff: 1 diagnostic" "mypy: 1 diagnostic"
  body_lines
  local text want s
  text="$(printf '%s\n' "${BODY[@]}")"
  for want in '^changed +app/models\.py +\(modified\)$' \
    '^test +tests/test_models\.py +imports app/models\.py$' \
    '^test +tests/test_orders\.py +imports app/orders\.py, which imports app/models\.py$' \
    '^lint +app/models\.py +ruff$' '^type +app/models\.py +mypy$' \
    "^tests/test_models\\.py:[0-9]+ .*test_total_rounds" \
    "^app/models\\.py:${RUFF_LINE}(:[0-9]+)? " "^app/models\\.py:${MYPY_LINE}(:[0-9]+)?:? "; do
    grep -qE -- "$want" <<<"$text" || flunk "no body line matches /${want}/"
  done
  assert_no_line_matching 'test_cli\.py' || flunk "tests/test_cli.py is named: it imports nothing that changed"
  assert_no_line_matching 'legacy\.py' || flunk "app/legacy.py is named: lint or type-check went beyond the changed file"
  local tool steps=""
  for s in "${BODY[@]}"; do
    [[ "$s" == "── "* ]] || continue
    s="${s%% · *}"
    for tool in pytest ruff mypy; do
      [[ "$s" =~ ^──\ ([^ ]*/)?${tool}\  ]] && steps+="${tool}=$(py_words "$s");"
    done
  done
  [[ "$steps" == "pytest=tests/test_models.py tests/test_orders.py;ruff=app/models.py;mypy=app/models.py;" ]] ||
    flunk "the step lines (tool=its .py arguments, in order): ${steps}"
}

@test "SC-3 [bash -c, notty] With one changed source file, the changed-only check runs the tests that import it and lints and type-checks only changed files, and states which were selected and why — JSON: two test files with reasons, pytest on them only, ruff and mypy on app/models.py only" { check_json c; }
@test "SC-3 [bash -lc, notty] With one changed source file, the changed-only check runs the tests that import it and lints and type-checks only changed files, and states which were selected and why — JSON: two test files with reasons, pytest on them only, ruff and mypy on app/models.py only" { check_json lc; }
@test "SC-3 [bash -c, notty] With one changed source file, the changed-only check runs the tests that import it and lints and type-checks only changed files, and states which were selected and why — text: the selection with its reasons, each step's command and findings" { check_text c; }
@test "SC-3 [bash -lc, notty] With one changed source file, the changed-only check runs the tests that import it and lints and type-checks only changed files, and states which were selected and why — text: the selection with its reasons, each step's command and findings" { check_text lc; }
