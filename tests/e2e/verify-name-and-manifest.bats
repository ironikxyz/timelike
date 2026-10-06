#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# FR-13 — the name and the manifest. (Feature 012, slice 1; spec FR-13, FR-11; contracts/verify-cli.md
# § Manifest, as amended by the tool's author during the cycle; research R6.)
#   - `type -a verify` names exactly /opt/timelike/bin/verify, one line: the image has no other
#     `verify` (R6: Debian's trixie-slim has none).
#   - `verify --agent-info` declares `tool: verify`, `mutating: false`, `reads_stdin: false`,
#     `passes_exit: true` (`verify test`), `dry_run: false` (`--dry-run` is an option of `changed`
#     only), `probe: ["true"]`, and no `takes_command` key; its exit codes include 0, 1, 2 and 124.
#   - `verify changed` outside a git repository is a usage error: exit 2, said on stderr (naming the
#     git repository it needs), nothing on stdout.
#
# Each cell runs in a session of its own (`vf6-<run id>-<check>-<style>`), in a workspace of its own,
# so the tool's own session event lands in no other cell's records. teardown_file removes this file's
# directory and this run's session directories (by that prefix) and nothing else. No pytest, ruff or
# mypy is needed here, so no wrappers are installed. Cells: bash -c and bash -lc, `notty`.

load helpers

# This file's session prefix (sessions are `<prefix>-<run id>-<check>-<style>`).
SPREFIX=vf6
SDIR_NAME=verify-name

setup_file() {
  NO_WRAPPERS=1 setup_verify_file
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

# ── checks ────────────────────────────────────────────────────────────────────────────────────

# check_type_a STYLE — exactly one `verify` on PATH, and it is timelike's.
check_type_a() {
  run_in "$1" notty "type -a verify"
  assert_within 20
  assert_status 0
  [[ ${#lines[@]} -eq 1 ]] || { printf 'type -a verify printed %d lines, want 1:\n%s\n' "${#lines[@]}" "$output" >&2; return 1; }
  [[ "${lines[0]}" == "verify is /opt/timelike/bin/verify" ]] || { echo "type -a verify: ${lines[0]}" >&2; return 1; }
}

# check_manifest STYLE — the manifest's fields, as the (amended) contract fixes them.
check_manifest() {
  new_cell manifest "$1"
  git_init
  in_session "$1" "verify --agent-info"
  expect_status 0
  jpy "codes = g('exit_codes', {}) or {}
print('tool=' + json.dumps(g('tool')))
print('mutating=' + json.dumps(g('mutating')))
print('reads_stdin=' + json.dumps(g('reads_stdin')))
print('passes_exit=' + json.dumps(g('passes_exit')))
print('dry_run=' + json.dumps(g('dry_run')))
print('probe=' + json.dumps(g('probe')))
print('takes_command=' + json.dumps('takes_command' in d))
print('exit_codes=' + json.dumps([c for c in ['0', '1', '2', '124'] if c not in {str(k) for k in codes}]))"
  expect_j tool '"verify"'
  expect_j mutating false
  expect_j reads_stdin false
  expect_j passes_exit true
  expect_j dry_run false
  expect_j probe '["true"]'
  expect_j takes_command false
  expect_j exit_codes '[]' || flunk "exit_codes lacks the codes listed"
}

# check_not_a_repository STYLE — `verify changed` where no git repository is: exit 2 (usage), the
# reason on stderr, stdout empty.
check_not_a_repository() {
  new_cell norepo "$1"
  if exec_plain git -C "$CELL" rev-parse --git-dir >/dev/null 2>&1; then
    flunk "the precondition is no repository, and git finds one above ${CELL}"
  fi
  in_session "$1" "verify changed"
  expect_status 2
  [[ -z "$output" ]] || flunk "a usage error prints nothing on stdout"
  local err
  err="$(exec_plain cat "${CELL}.stderr")" || flunk "cannot read stderr"
  expect_has "stderr" "$err" "git repository"
}

@test "FR-13 [bash -c, notty] type -a verify names exactly /opt/timelike/bin/verify — one line, no other verify on PATH" { check_type_a c; }
@test "FR-13 [bash -lc, notty] type -a verify names exactly /opt/timelike/bin/verify — one line, no other verify on PATH" { check_type_a lc; }
@test "FR-13 [bash -c, notty] verify --agent-info declares tool verify, mutating false, reads_stdin false, passes_exit true, dry_run false, probe [true], no takes_command — exit codes include 0, 1, 2, 124" { check_manifest c; }
@test "FR-13 [bash -lc, notty] verify --agent-info declares tool verify, mutating false, reads_stdin false, passes_exit true, dry_run false, probe [true], no takes_command — exit codes include 0, 1, 2, 124" { check_manifest lc; }
@test "FR-11 [bash -c, notty] verify changed outside a git repository is a usage error — exit 2, the reason on stderr, nothing on stdout" { check_not_a_repository c; }
@test "FR-11 [bash -lc, notty] verify changed outside a git repository is a usage error — exit 2, the reason on stderr, nothing on stdout" { check_not_a_repository lc; }
