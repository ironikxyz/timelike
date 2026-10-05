#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# FR-2 and FR-12 — the name and the manifest. (Feature 008, slice 0; spec FR-2, FR-12; tasks.md T005;
# contracts/edit-cli.md § Manifest; research R1, R6, R8.)
#   - FR-2: `type -a edit` names exactly /opt/timelike/bin/edit, one line. Debian's mailcap package
#     installs /usr/bin/edit (a run-mailcap alias); the image does not install it, and this cell keeps it
#     that way.
#   - FR-12 (discovery revision 13: edit is not confirmed): `edit --agent-info` declares
#     `mutating: true`, `confirm_protocol: false`, `destructive: true`, `dry_run: true`,
#     `reads_stdin: false`, `envelopes: []`; its flags carry `--dry-run` and no `--yes`; no exit code 4.
#   - `--yes` is not a flag: `edit FILE --old … --new … --yes` is a usage error (exit 2), and the file's
#     sha256sum is unchanged. The control, in its own cell directory: the same edit without `--yes` exits
#     0 and changes the file to the bytes the test built, so the exit 2 is `--yes`'s alone.
#
# Fixtures are built by the container's printf (P005), and every "unchanged" or "changed to" is
# sha256sum in the container against a file the test built (P004).
# Isolation: every cell creates its own directories and files, named after the check, the style and the
# terminal mode; `mkdir` without -p refuses a path that exists, so no cell can reuse another's fixture.
# Cells: bash -c and bash -lc, `notty`.

load helpers

setup_file() {
  stamp_check
  EDIT_DIR="$(container_tmpdir edit-name)"
  export EDIT_DIR
}

teardown_file() {
  container_rm "${EDIT_DIR:-}"
}

# ── helpers (this file's own; the 008 files repeat them so each reads alone) ─────────────────────

# new_cell NAME STYLE TTY — this cell's own paths, created now. Sets:
#   CELL   a directory that holds only the file under edit
#   FILE   the file's name, relative to CELL (edit is run from CELL, so FILE is printed as given)
#   CELL.want, CELL.stderr, CELL.scratch beside it
new_cell() {
  CELL="${EDIT_DIR}/$1-$2-$3"
  FILE="$1-$2-$3.py"
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

# ── checks ────────────────────────────────────────────────────────────────────────────────────

ORIG='alpha = 1\nbeta = 2\n'
WANT='alpha = 1\nbeta = 3\n'
EDIT_ARGS="--old 'beta = 2' --new 'beta = 3'"

# check_type_a STYLE — exactly one `edit` on PATH, and it is timelike's.
check_type_a() {
  run_in "$1" notty "type -a edit"
  assert_within 20
  assert_status 0
  [[ ${#lines[@]} -eq 1 ]] || { printf 'type -a edit printed %d lines, want 1 (is mailcap installed?):\n%s\n' "${#lines[@]}" "$output" >&2; return 1; }
  [[ "${lines[0]}" == "edit is /opt/timelike/bin/edit" ]] || { echo "type -a edit: ${lines[0]}" >&2; return 1; }
}

# check_manifest STYLE — the manifest's rule-9 and rule-8 fields, as the contract fixes them.
check_manifest() {
  new_cell manifest "$1" notty
  in_cell "$1" "edit --agent-info"
  expect_status 0
  jpy "flags = g('flags', [])
print('mutating=' + json.dumps(g('mutating')))
print('confirm_protocol=' + json.dumps(g('confirm_protocol')))
print('destructive=' + json.dumps(g('destructive')))
print('dry_run=' + json.dumps(g('dry_run')))
print('reads_stdin=' + json.dumps(g('reads_stdin')))
print('envelopes=' + json.dumps(g('envelopes')))
print('flag_dry_run=' + json.dumps('--dry-run' in flags))
print('flag_yes=' + json.dumps('--yes' in flags))
print('exit_4=' + json.dumps('4' in (g('exit_codes', {}) or {})))"
  expect_j mutating true
  expect_j confirm_protocol false
  expect_j destructive true
  expect_j dry_run true
  expect_j reads_stdin false
  expect_j envelopes "[]"
  expect_j flag_dry_run true
  expect_j flag_yes false
  expect_j exit_4 false
}

# check_yes STYLE — `--yes` is a usage error (exit 2, nothing on stdout that reads as an outcome, the
# error naming --yes on stderr) and the file is unchanged; the control without --yes edits it.
check_yes() {
  new_cell yes "$1" notty
  put "${CELL}/${FILE}" "$ORIG"
  local sha_orig
  sha_orig="$(sha "${CELL}/${FILE}")"
  in_cell "$1" "edit ${FILE} ${EDIT_ARGS} --yes"
  expect_status 2
  expect_sha "the file after a usage error" "$(sha "${CELL}/${FILE}")" "$sha_orig"
  only_file
  [[ "$output" != *'"status"'* && "$output" != *"verdict"* ]] || flunk "a usage error printed an outcome or an envelope on stdout"
  [[ "$(exec_plain cat "${CELL}.stderr")" == *"--yes"* ]] || flunk "stderr does not name --yes"

  # Control: the same edit without --yes, in a cell of its own.
  new_cell yes-control "$1" notty
  put "${CELL}/${FILE}" "$ORIG"
  put "${CELL}.want" "$WANT"
  in_cell "$1" "edit ${FILE} ${EDIT_ARGS}"
  expect_status 0
  expect_sha "the control edit (without --yes)" "$(sha "${CELL}/${FILE}")" "$(sha "${CELL}.want")"
  only_file
}

@test "FR-2 [bash -c, notty] type -a edit names exactly /opt/timelike/bin/edit — no mailcap /usr/bin/edit" { check_type_a c; }
@test "FR-2 [bash -lc, notty] type -a edit names exactly /opt/timelike/bin/edit — no mailcap /usr/bin/edit" { check_type_a lc; }
@test "FR-12 [bash -c, notty] edit --agent-info declares mutating, confirm_protocol false, dry_run, no envelopes — --dry-run in flags, no --yes, no exit 4" { check_manifest c; }
@test "FR-12 [bash -lc, notty] edit --agent-info declares mutating, confirm_protocol false, dry_run, no envelopes — --dry-run in flags, no --yes, no exit 4" { check_manifest lc; }
@test "FR-12 [bash -c, notty] edit with --yes is a usage error — exit 2, file sha256 unchanged; without --yes the same edit applies" { check_yes c; }
@test "FR-12 [bash -lc, notty] edit with --yes is a usage error — exit 2, file sha256 unchanged; without --yes the same edit applies" { check_yes lc; }
