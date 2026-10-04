#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# FR-2 — a workspace that resolves to the filesystem root, the agent's home directory, or an ancestor
# of either is refused, with what to do instead; and R7 — `snapshot` and `undo` each resolve to
# exactly one command, timelike's. (Feature 005, slice 0; spec FR-1, FR-2, FR-22, Scenario 4, D-2,
# D-6; tasks.md T007; contracts/recover-cli.md § Refusals and "Outcomes are verdicts, errors are
# errors"; research R3, R7.)
#
# Written from the contract before the tools existed. A refusal is a RESULT (contract amendment,
# T009): exit 1, the header and `verdict: refused: <path> is …` on stdout, then `do instead: <remedy>`;
# JSON carries `remedy`; nothing on stderr. `/home/agent` is the image's WORKDIR, so this is the call
# an agent makes when it has not changed into a project (Scenario 4).
#
# From `$HOME`, `/` and `/home` (none holds a `.git`, so each is its own workspace, FR-1):
#   ~      → "is your home directory"
#   /      → "is the filesystem root" (it also contains the store under /tmp; root is checked first,
#            as FR-2 precedes FR-3 and the contract lists it first)
#   /home  → "is an ancestor of your home directory"
# Nothing is written to the store: no entry exists under <scratch>/<session>/snapshots/ (the session
# event is agentio's and lives beside it, not in it). The test's own TIMELIKE_SCRATCH_ROOT keeps that
# measurement to this test.
# Cells: bash -c and bash -lc, `notty`.

load helpers

setup_file() {
  stamp_check
}

setup() {
  WORK="$(container_tmpdir frrefuse)"
  SCRATCH="${WORK}/scratch"
  HOME_REAL="$(exec_plain sh -c 'realpath "$HOME"')"
  [[ -n "$HOME_REAL" && "$HOME_REAL" != / ]] || { echo "agent HOME resolves to '${HOME_REAL}'" >&2; return 1; }
}

teardown() {
  container_rm "$WORK"
}

# in_dir STYLE DIR CMD — run CMD after `cd DIR` (DIR is expanded by the container's shell, so "$HOME"
# is the agent's), with this test's store; stderr to $WORK/stderr.
in_dir() {
  run_in -e "TIMELIKE_SCRATCH_ROOT=${SCRATCH}" -e "TIMELIKE_SESSION=refuse" "$1" notty \
    "cd $2 && $3 2>'${WORK}/stderr'"
  assert_within 20
}

flunk() {
  local err
  err="$(exec_plain cat "${WORK}/stderr" 2>&1)" || true
  printf '%s\nexit %s; stdout:\n%s\nstderr:\n%s\n' "$1" "$status" "$output" "$err" >&2
  return 1
}

# nothing_stored — no snapshot store entry exists for any workspace, and stderr was empty.
nothing_stored() {
  local found err
  found="$(exec_plain sh -c '[ -d "$1" ] || exit 0; find "$1" -path "*/snapshots/*" -print' found "$SCRATCH")"
  [[ -z "$found" ]] || flunk "the refused call wrote to the store: ${found}"
  err="$(exec_plain cat "${WORK}/stderr")"
  [[ -z "$err" ]] || flunk "a refusal is a result on stdout, but stderr carries: ${err}"
}

# resolved DIR — the path the refusal must name.
resolved() {
  case "$1" in
    '"$HOME"') printf '%s' "$HOME_REAL" ;;
    *) exec_plain realpath "$1" ;;
  esac
}

# check_refused STYLE TOOL DIR REASON — TOOL from DIR is refused: exit 1, the text header, verdict and
# do-instead lines; then the JSON verdict, target and remedy; nothing stored.
check_refused() {
  local style="$1" tool="$2" dir="$3" reason="$4" path
  path="$(resolved "$dir")"

  in_dir "$style" "$dir" "${tool} --text"
  [[ "$status" == 1 ]] || flunk "${tool} from ${path}: expected exit 1, got ${status}"
  [[ "${lines[0]:-}" == "${tool}: ${path} ["*"]" ]] || flunk "header line: ${lines[0]:-<none>}"
  [[ "${lines[1]:-}" == "verdict: refused: ${path} ${reason}" ]] || flunk "verdict line: ${lines[1]:-<none>}"
  [[ "${lines[2]:-}" == "do instead: change into the project directory"* ]] || flunk "do-instead line: ${lines[2]:-<none>}"
  if [[ "$tool" == snapshot ]]; then
    [[ "${lines[2]}" == "do instead: change into the project directory (a directory below ${HOME_REAL}) and run snapshot again" ]] \
      || flunk "do-instead line: ${lines[2]}"
  fi
  nothing_stored

  in_dir "$style" "$dir" "${tool} --json"
  [[ "$status" == 1 ]] || flunk "${tool} --json from ${path}: expected exit 1, got ${status}"
  local got
  got="$(printf '%s' "$output" | pyq 'import json,sys
d=json.load(sys.stdin)
def g(k):
    return d[k] if k in d else (d.get("data") or {}).get(k, "<absent>")
for k in ("tool", "target", "verdict", "remedy", "exit"):
    print(k + "=" + str(g(k)))')" || flunk "stdout is not JSON"
  [[ "$got" == *"tool=${tool}"* ]] || flunk "JSON tool: ${got}"
  [[ "$got" == *"target=${path}"$'\n'* ]] || flunk "JSON target: ${got}"
  [[ "$got" == *"verdict=refused: ${path} ${reason}"$'\n'* ]] || flunk "JSON verdict: ${got}"
  [[ "$got" == *"remedy=change into the project directory"* ]] || flunk "JSON remedy: ${got}"
  [[ "$got" == *"exit=1" ]] || flunk "JSON exit: ${got}"
  nothing_stored
}

# check_type_a STYLE NAME — exactly one NAME on PATH, and it is timelike's.
check_type_a() {
  run_in "$1" notty "type -a $2"
  assert_within 20
  assert_status 0
  [[ ${#lines[@]} -eq 1 ]] || { printf 'type -a %s printed %d lines, want 1:\n%s\n' "$2" "${#lines[@]}" "$output" >&2; return 1; }
  [[ "${lines[0]}" == "$2 is /opt/timelike/bin/$2" ]] || { echo "type -a $2: ${lines[0]}" >&2; return 1; }
}

HOME_DIR='"$HOME"'
HOME_REASON="is your home directory"
ROOT_REASON="is the filesystem root"
ANCESTOR_REASON="is an ancestor of your home directory"

@test "FR-2 snapshot from the home directory is refused with what to do instead [bash -c, notty]" { check_refused c snapshot "$HOME_DIR" "$HOME_REASON"; }
@test "FR-2 snapshot from the home directory is refused with what to do instead [bash -lc, notty]" { check_refused lc snapshot "$HOME_DIR" "$HOME_REASON"; }
@test "FR-2 snapshot from / is refused with what to do instead [bash -c, notty]" { check_refused c snapshot / "$ROOT_REASON"; }
@test "FR-2 snapshot from / is refused with what to do instead [bash -lc, notty]" { check_refused lc snapshot / "$ROOT_REASON"; }
@test "FR-2 snapshot from /home is refused with what to do instead [bash -c, notty]" { check_refused c snapshot /home "$ANCESTOR_REASON"; }
@test "FR-2 snapshot from /home is refused with what to do instead [bash -lc, notty]" { check_refused lc snapshot /home "$ANCESTOR_REASON"; }
@test "FR-2 undo from the home directory is refused with what to do instead [bash -c, notty]" { check_refused c undo "$HOME_DIR" "$HOME_REASON"; }
@test "FR-2 undo from the home directory is refused with what to do instead [bash -lc, notty]" { check_refused lc undo "$HOME_DIR" "$HOME_REASON"; }
@test "FR-2 undo from / is refused with what to do instead [bash -c, notty]" { check_refused c undo / "$ROOT_REASON"; }
@test "FR-2 undo from / is refused with what to do instead [bash -lc, notty]" { check_refused lc undo / "$ROOT_REASON"; }
@test "FR-2 undo from /home is refused with what to do instead [bash -c, notty]" { check_refused c undo /home "$ANCESTOR_REASON"; }
@test "FR-2 undo from /home is refused with what to do instead [bash -lc, notty]" { check_refused lc undo /home "$ANCESTOR_REASON"; }
@test "R7 type -a snapshot resolves to exactly /opt/timelike/bin/snapshot [bash -c, notty]" { check_type_a c snapshot; }
@test "R7 type -a snapshot resolves to exactly /opt/timelike/bin/snapshot [bash -lc, notty]" { check_type_a lc snapshot; }
@test "R7 type -a undo resolves to exactly /opt/timelike/bin/undo [bash -c, notty]" { check_type_a c undo; }
@test "R7 type -a undo resolves to exactly /opt/timelike/bin/undo [bash -lc, notty]" { check_type_a lc undo; }
