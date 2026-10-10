#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# FR-28 — carried from slice 0 (008 Cycle 1's `not_verified`). (Feature 008, slice 1; spec FR-28, FR-2,
# FR-7; contracts/edit-cli.md § Refusals: owner cannot be kept; research R5, R16.)
#   - `type -a edit` under `bash -lc`, where Debian's /etc/profile resets PATH and profile.d restores it:
#     exactly one line, `edit is /opt/timelike/bin/edit` (the expectation edit-name-and-manifest.bats
#     fixes). This is the cell that catches mailcap's /usr/bin/edit shadowing ours. bash -c is kept
#     beside it as the control.
#   - The atomic write's owner branch under a real second uid. The agent container runs with
#     `cap_drop: [ALL]` (compose.yaml), so `docker exec -u 0` is root WITHOUT CAP_CHOWN, CAP_FOWNER or
#     CAP_DAC_OVERRIDE: root can neither chown a file to another uid nor enter or write an agent-owned
#     directory its mode does not open to others (research R16's uid-1001 recipe cannot run here). So:
#     the agent makes the cell directory 0777 (and the file's parent directory 0755, since mktemp made
#     it 0700); root creates the file in it, owned by uid 0, mode 0666, so the agent can write it. The
#     agent's edit then cannot fchown its temporary file to uid 0 (EPERM), and is refused: exit 1,
#     `cannot keep FILE's owner (uid 0)`, the file's sha256sum unchanged, no temporary file left.
#     If the lane's `docker exec` cannot run as root, the cell is skipped, and says that the owner
#     branch stays unverified.
#
# Fixtures are built by the container's printf (P005); "unchanged" is sha256sum in the container,
# read by the test before and after (P004). The owner and mode root left are read with stat first.
# Isolation: every cell creates its own directories and files, named after the check, the style and the
# terminal mode; `mkdir` without -p refuses a path that exists.
# Cells: bash -c and bash -lc, `notty`.

load helpers

setup_file() {
  stamp_check
  EDIT_DIR="$(container_tmpdir edit-carried)"
  export EDIT_DIR
}

teardown_file() {
  container_rm "${EDIT_DIR:-}"
}

# ── helpers (this file's own; the 008 files repeat them so each reads alone) ─────────────────────

# new_cell NAME STYLE TTY [EXT] — this cell's own paths, created now. Sets:
#   CELL   a directory that holds only the file under edit
#   FILE   the file's name, ending .EXT (default py), relative to CELL (edit is run from CELL, so FILE
#          is printed as given)
#   CELL.want, CELL.stderr, CELL.scratch beside it
new_cell() {
  CELL="${EDIT_DIR}/$1-$2-$3"
  FILE="$1-$2-$3.${4:-py}"
  exec_plain mkdir "$CELL" "${CELL}.scratch" || { echo "cell path ${CELL} exists: cells must not share a fixture" >&2; return 1; }
}

# put PATH FORMAT — write FORMAT with the container's printf (P005). \r, \n and \t in FORMAT are
# escapes; FORMAT carries no % directive.
put() {
  [[ "$2" != *%* ]] || { echo "put: FORMAT carries a %" >&2; return 1; }
  exec_plain sh -c 'printf "$2" >"$1"' put "$1" "$2"
}

# sha PATH — sha256sum in the container, the hash alone.
sha() {
  local out
  out="$(exec_plain sha256sum "$1")" || { echo "sha256sum $1 failed" >&2; return 1; }
  printf '%s' "${out%% *}"
}

# in_cell STYLE CMD — run CMD from CELL as the agent would, with this cell's session scratch; stderr
# goes to CELL.stderr so stdout stays one JSON document.
in_cell() {
  run_in -e "TIMELIKE_SCRATCH_ROOT=${CELL}.scratch" -e "TIMELIKE_SESSION=edit-e2e" "$1" notty \
    "cd '${CELL}' && { $2; } 2>'${CELL}.stderr'"
  assert_within 20
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

no_stderr() {
  [[ -z "$(exec_plain cat "${CELL}.stderr")" ]] || flunk "an outcome is a result on stdout, but stderr is not empty"
}

# expect_sha WHAT GOT WANT
expect_sha() {
  [[ -n "$2" && "$2" == "$3" ]] || flunk "$1: sha256 ${2:-<none>}, want ${3:-<none>}"
}

# only_file — the cell directory holds the file under edit and nothing else (no temporary file left).
only_file() {
  local got
  got="$(exec_plain ls -A "$CELL")" || flunk "cannot list ${CELL}"
  [[ "$got" == "$FILE" ]] || flunk "the directory holds more than ${FILE}: $(printf '%s' "$got" | tr '\n' ' ')"
}

# jpy SCRIPT — Python over the last run's stdout, parsed as JSON into `d`; `g(k)` reads a field by a
# dotted path, top-level first, then under `data`. Output in $JPY.
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

# numbered PATH A B [MA MB] — lines A..B of PATH as `view` numbers them: the number right-aligned to the
# width of the file's line count, `>` on lines MA..MB and a space elsewhere, one space, the text (a
# trailing CR is not shown). Formatted by awk from the file itself.
numbered() {
  exec_plain awk -v a="$2" -v b="$3" -v ma="${4:-0}" -v mb="${5:-0}" '
    NR == FNR { n++; next }
    FNR == 1 { w = length(n "") }
    { sub(/\r$/, "") }
    FNR >= a && FNR <= b { printf "%" w "d%s %s\n", FNR, (FNR >= ma && FNR <= mb ? ">" : " "), $0 }' "$1" "$1"
}

# exec_root CMD... — `docker exec -u 0` (root, but with the container's dropped capabilities), bounded
# like exec_plain. Setup only: never the command under test.
exec_root() {
  timeout "$RUN_TIMEOUT" docker exec -u 0 "$AGENT_CONTAINER" "$@" </dev/null
}

# ── checks ────────────────────────────────────────────────────────────────────────────────────

ORIG='alpha = 1\nbeta = 2\n'
EDIT_ARGS="--old 'beta = 2' --new 'beta = 3'"

# check_type_a STYLE — exactly one `edit` on PATH, and it is timelike's.
check_type_a() {
  run_in "$1" notty "type -a edit"
  assert_within 20
  assert_status 0
  [[ ${#lines[@]} -eq 1 ]] || { printf 'type -a edit printed %d lines, want 1 (is mailcap installed?):\n%s\n' "${#lines[@]}" "$output" >&2; return 1; }
  [[ "${lines[0]}" == "edit is /opt/timelike/bin/edit" ]] || { echo "type -a edit: ${lines[0]}" >&2; return 1; }
}

# check_owner STYLE — a file owned by another uid (root, 0), writable by the agent (0666), in a
# directory the agent can write: the edit is refused (exit 1, `cannot keep FILE's owner`, uid 0), the
# file's sha256sum and owner are unchanged, and the directory holds only the file.
check_owner() {
  new_cell owner "$1" notty
  exec_plain chmod 0755 "$EDIT_DIR"
  exec_plain chmod 0777 "$CELL"
  local who
  who="$(exec_root id -u 2>&1)" || skip "cannot docker exec -u 0 in ${AGENT_CONTAINER} (${who//$'\r'/}): the owner branch stays unverified"
  [[ "${who//$'\r'/}" == 0 ]] || skip "docker exec -u 0 ran as uid '${who}', not root: the owner branch stays unverified"
  exec_root sh -c 'printf "$2" >"$1" && chmod 0666 "$1"' put "${CELL}/${FILE}" "$ORIG" \
    || skip "root could not create a file in the agent's 0777 directory: the owner branch stays unverified"
  local st
  st="$(exec_plain stat -c '%u %a' "${CELL}/${FILE}")"
  [[ "${st//$'\r'/}" == "0 666" ]] || { echo "fixture: the file is '${st}' (uid mode), want '0 666'" >&2; return 1; }
  local sha_orig
  sha_orig="$(sha "${CELL}/${FILE}")"
  [[ -n "$sha_orig" ]] || return 1

  in_cell "$1" "edit ${FILE} ${EDIT_ARGS}"
  expect_status 1
  expect_sha "the file after the refused edit" "$(sha "${CELL}/${FILE}")" "$sha_orig"
  only_file
  st="$(exec_plain stat -c '%u %a' "${CELL}/${FILE}")"
  [[ "${st//$'\r'/}" == "0 666" ]] || flunk "the file's owner or mode changed: '${st}'"

  jfields exit scope verdict
  expect_j exit 1
  expect_j scope refused
  local v
  v="$(jval verdict)"
  [[ "$v" == *"cannot keep ${FILE}'s owner"* && "$v" == *"uid 0"* && "$v" == *"nothing written"* ]] \
    || flunk "verdict does not name the owner it cannot keep: ${v}"
}

@test "FR-28 [bash -c, notty] type -a edit names exactly /opt/timelike/bin/edit — one line, no mailcap /usr/bin/edit" { check_type_a c; }
@test "FR-28 [bash -lc, notty] type -a edit names exactly /opt/timelike/bin/edit — one line, no mailcap /usr/bin/edit, after /etc/profile resets PATH" { check_type_a lc; }
@test "FR-28 [bash -c, notty] the atomic write's owner branch under a real second uid: a file owned by another user, writable by the agent, is refused with cannot keep FILE's owner, and its hash is unchanged" { check_owner c; }
@test "FR-28 [bash -lc, notty] the atomic write's owner branch under a real second uid: a file owned by another user, writable by the agent, is refused with cannot keep FILE's owner, and its hash is unchanged" { check_owner lc; }
