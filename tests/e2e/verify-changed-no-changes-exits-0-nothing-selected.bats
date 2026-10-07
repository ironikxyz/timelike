#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# SC-4 — "With no changes, the changed-only check exits 0 and says nothing was selected". (Feature 012,
# slice 1; spec Scenario 4, FR-6, FR-11; contracts/verify-cli.md § changed, "no changes"; research R4,
# R7.)
#
# Written from the contract before the tool existed. The project is make-project.sh's pytest project
# (written by the container's bash), committed. The REAL pytest, ruff and mypy wrappers (research R1)
# are first on PATH, so "nothing run" is not "nothing found": a run that selected anything would find
# them. Two workspaces:
#   - clean: nothing changed since the commit;
#   - ignored only: a committed .gitignore ignores *.log, and the only new file is debug.log. Ignored
#     files are not changes (FR-6).
# Each cell first checks its own precondition with git itself (`git status --porcelain` is empty, and
# for the second, `--ignored` lists debug.log), never with `verify`. And after the call, pytest's own
# cache directory does not exist in the workspace: pytest, had it run there, would have written it.
#
# Isolation: each cell has its own workspace (a git repository holding the project) and its own
# TIMELIKE_SESSION (`vf4-<run id>-<check>-<style>`), checked to have no records before the cell
# starts. teardown_file removes this file's directory and this run's session directories (by that
# prefix) and nothing else. Cells: bash -c and bash -lc, `notty`.

load helpers

# This file's session prefix (sessions are `<prefix>-<run id>-<check>-<style>`).
SPREFIX=vf4
SDIR_NAME=verify-sc4

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
  local jpy_rc=0 jpy_err="${BATS_TEST_TMPDIR}/jpy.stderr"
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
  # Say why the parser failed (lane batch-b, not ok 432): its exit, a timeout by name, its stderr.
  if ((jpy_rc != 0)); then
    local why="the parser (pyq) exited ${jpy_rc}"
    ((jpy_rc == 124)) && why+=": killed by timeout after ${RUN_TIMEOUT} s"
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

NOTHING='no changes against HEAD: nothing selected, nothing run'

# new_clean_cell NAME STYLE [ignored] — the committed project; with `ignored`, a committed .gitignore
# and one ignored file written after the commit. Checks the precondition with git.
new_clean_cell() {
  new_cell "$1" "$2"
  gen pytest
  [[ "${3:-}" == ignored ]] && put .gitignore '*.log'
  git_init
  git_commit_all
  local st
  if [[ "${3:-}" == ignored ]]; then
    put debug.log "an ignored file, written after the commit"
    st="$(exec_plain git -C "$CELL" status --porcelain --ignored --untracked-files=all)" || flunk "git status failed"
    [[ "$st" == "!! debug.log" ]] || flunk "the precondition is one ignored file, git status --ignored says: ${st}"
  fi
  st="$(exec_plain git -C "$CELL" status --porcelain --untracked-files=all)" || flunk "git status failed"
  [[ -z "$st" ]] || flunk "the precondition is a clean tree, git status says: ${st}"
}

# expect_nothing_ran — pytest's cache directory was not written into the workspace.
expect_nothing_ran() {
  if exec_plain test -e "${CELL}/.pytest_cache"; then
    flunk "${CELL}/.pytest_cache exists: pytest ran"
  fi
}

# ── checks ────────────────────────────────────────────────────────────────────────────────────

# check_json STYLE [ignored] — exit 0; nothing changed, nothing selected, no step; the verdict says so.
check_json() {
  new_clean_cell "json${2:+-$2}" "$1" "${2:-}"
  in_session "$1" "verify changed"
  expect_status 0
  jpy "sel = g('selected', {}) or {}
print('scope=' + str(g('scope')))
print('changed=' + json.dumps(g('changed')))
print('selected=' + json.dumps([sel.get('tests'), sel.get('lint'), sel.get('typecheck')]))
print('steps=' + json.dumps(g('steps')))
print('verdict=' + str(g('verdict')))"
  expect_j scope 'nothing selected'
  expect_j changed '[]'
  expect_j selected '[[], [], []]'
  expect_j steps '[]'
  expect_has "the verdict" "$(jval verdict)" "$NOTHING"
  expect_nothing_ran
}

# check_text STYLE [ignored] — the text view: header scope, the verdict, and no step line.
check_text() {
  new_clean_cell "text${2:+-$2}" "$1" "${2:-}"
  in_session "$1" "verify --text changed"
  expect_status 0
  [[ "${lines[0]:-}" == "verify: changed"* && "${lines[0]}" == *"[nothing selected]" ]] ||
    flunk "the first line is not the header 'verify: changed … [nothing selected]'"
  expect_has "the verdict" "$(text_line "verdict: ")" "$NOTHING"
  assert_no_line_matching '^── ' || flunk "a step line is printed: nothing should have run"
  assert_no_line_matching '^(test|lint|type|changed) ' || flunk "a selection line is printed: nothing should be selected"
  expect_nothing_ran
}

@test "SC-4 [bash -c, notty] With no changes, the changed-only check exits 0 and says nothing was selected — JSON, clean tree" { check_json c; }
@test "SC-4 [bash -lc, notty] With no changes, the changed-only check exits 0 and says nothing was selected — JSON, clean tree" { check_json lc; }
@test "SC-4 [bash -c, notty] With no changes, the changed-only check exits 0 and says nothing was selected — text, clean tree" { check_text c; }
@test "SC-4 [bash -lc, notty] With no changes, the changed-only check exits 0 and says nothing was selected — text, clean tree" { check_text lc; }
@test "SC-4 [bash -c, notty] With no changes, the changed-only check exits 0 and says nothing was selected — JSON, only an ignored file is new" { check_json c ignored; }
@test "SC-4 [bash -lc, notty] With no changes, the changed-only check exits 0 and says nothing was selected — JSON, only an ignored file is new" { check_json lc ignored; }
