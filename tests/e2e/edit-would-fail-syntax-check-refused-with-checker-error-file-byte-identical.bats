#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# SC-8 — "An edit that would make a Python, TypeScript, Go, Rust or shell file fail its syntax check is
# refused with the checker's error, and the file is byte-identical". (Feature 008, slice 1; spec FR-18
# to FR-22, FR-26; contracts/edit-cli.md § Slice 1: The syntax check, Refused by the syntax check;
# research R9, R10, R15.)
#
# Written from the contract before the tool existed. Every expected value is the test's own (P004, P005):
#   - each language's fixture is a valid file written by the container's printf, from the language's
#     documented syntax, never produced by the checker under test; the breaking edit and the valid edit
#     are plain --old/--new replacements whose results the test also builds itself;
#   - "byte-identical" is the file's sha256sum, read by the test before and after the refused edit;
#     "applies" is the file's sha256sum equal to the bytes the test built;
#   - the checker named must be the contract's: `python X.Y.Z compile` with X.Y.Z read from timelike's
#     interpreter by the test, `bash -n`, `tree-sitter-typescript V`, `tree-sitter-typescript V (tsx)`,
#     `tree-sitter-go V`, `tree-sitter-rust V`.
# Python and shell break on a line the test knows (the language's own parser reports it): the error's
# line is asserted. Tree-sitter's recovery places ERROR/MISSING nodes where it can, so for TypeScript,
# TSX, Go and Rust the test asserts a `line N` in the verdict and at least one error, not its number.
#
# Compiler confirmation of the fixtures (lore cross-stack P005; research R10):
#   - Python and shell: the checker is the language's own parser, so no second opinion exists.
#   - Go: the last cell runs the original, the valid edit's result and the breaking edit's result
#     through `gofmt -e` in GO_IMAGE. tests/run.sh does not pass GO_IMAGE into the runner, so it is read
#     from the environment if set, else from pins.env in the mounted repository (as helpers.bash's
#     install_uv_tool_wrappers reads its pins). The cell is skipped, saying why, when neither has it or
#     the image is not on the Docker host.
#   - TypeScript, TSX and Rust: NOT confirmed. Neither the dev host nor the lane host has tsc or rustc
#     (research R10), so these fixtures rest on the languages' documentation alone.
#
# P002 (decoys): the agent's PATH must not decide which checker runs. The decoy cells put executables
# named `python3` and `bash` FIRST on PATH, in the cell's own command, each writing a marker and
# exiting 0; the breaking Python and shell edits are still refused, and the marker never appears. A
# control first runs `python3` under the same PATH and sees the marker, so the decoy is known to be the
# one PATH finds. They are not written into /home/agent/.local/bin: `docker exec CONTAINER bash -c …`
# resolves `bash` through the container's PATH, where ~/.local/bin precedes /usr/bin, so a decoy `bash`
# there would replace the shell of this test's own cells and of every later file's. First on PATH is a
# stronger position than ~/.local/bin's (which is ahead of /usr/local/bin and /usr/bin, behind
# /opt/timelike/bin).
#
# Isolation: every cell creates its own directory and file, named after the check, the language, the
# style and the terminal mode; `mkdir` without -p refuses a path that exists.
# Cells: bash -c and bash -lc, `notty` (JSON is the default when stdout is not a terminal), plus two
# text cells.

load helpers

setup_file() {
  stamp_check
  EDIT_DIR="$(container_tmpdir edit-sc8)"
  export EDIT_DIR
  # The Python checker's version, read by the test from timelike's interpreter (edit's own).
  PYVER="$(exec_plain "$AGENT_PY" -I -c 'import platform; print(platform.python_version())')"
  PYVER="${PYVER//$'\r'/}"
  [[ "$PYVER" =~ ^3\.[0-9]+\.[0-9]+$ ]] || { echo "cannot read timelike's Python version: '${PYVER}'" >&2; return 1; }
  export PYVER
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

# q TEXT — TEXT quoted for the container's bash (both styles under test are bash).
q() {
  printf '%q' "$1"
}

# ── the fixtures (one per language) ────────────────────────────────────────────────────────────

# lang LANGUAGE — set the language's fixture:
#   EXT              the file's extension
#   ORIG             the valid file, a printf format (\n, \t escapes; no %)
#   BREAK_OLD/NEW    the breaking edit (each --old occurs once in ORIG)
#   OK_OLD/NEW       a valid edit
#   ERR_LINE         the error's line, where the language's own parser fixes it (else empty)
#   ERR_MSG          text the first error's message carries (else empty)
#   CHECKER_RE       the checker's name, as an anchored ERE
# shellcheck disable=SC2034 # the variables are read by the checks
lang() {
  ERR_LINE="" ERR_MSG=""
  case "$1" in
    python)
      EXT=py
      ORIG='import os\n\n\ndef f(x):\n    return x + 1\n\n\nprint(f(2), os.sep)\n'
      BREAK_OLD='def f(x):' BREAK_NEW='def f(x)'
      OK_OLD='return x + 1' OK_NEW='return x + 2'
      ERR_LINE=4 ERR_MSG="expected ':'"
      CHECKER_RE="^python ${PYVER//./\\.} compile\$"
      ;;
    shell)
      EXT="sh"
      ORIG='#!/bin/bash\nx="$1"\nif [ -n "$x" ]; then\n  echo "got $x"\nfi\n'
      BREAK_OLD='then' BREAK_NEW='then )'
      OK_OLD='got' OK_NEW='have'
      ERR_LINE=3 ERR_MSG="unexpected token"
      CHECKER_RE='^bash -n$'
      ;;
    typescript)
      EXT=ts
      ORIG='interface P {\n  x: number;\n}\n\nexport function f(p: P): number {\n  return p.x + 1;\n}\n'
      BREAK_OLD='p.x + 1;' BREAK_NEW='p.x + ;'
      OK_OLD='p.x + 1' OK_NEW='p.x + 2'
      CHECKER_RE='^tree-sitter-typescript [0-9][0-9A-Za-z.]*$'
      ;;
    tsx)
      EXT=tsx
      ORIG='export function App(props: { name: string }) {\n  return <div className="app">{props.name}</div>;\n}\n'
      BREAK_OLD='<div className="app">' BREAK_NEW='<div className="app"'
      OK_OLD='className="app"' OK_NEW='className="main"'
      CHECKER_RE='^tree-sitter-typescript [0-9][0-9A-Za-z.]* \(tsx\)$'
      ;;
    go)
      EXT=go
      ORIG='package main\n\nimport "fmt"\n\nfunc main() {\n\tfmt.Println("hi")\n}\n'
      BREAK_OLD='fmt.Println("hi")' BREAK_NEW='fmt.Println("hi"'
      OK_OLD='"hi"' OK_NEW='"hello"'
      CHECKER_RE='^tree-sitter-go [0-9][0-9A-Za-z.]*$'
      ;;
    rust)
      EXT=rs
      ORIG='fn add(a: i32, b: i32) -> i32 {\n    a + b\n}\n\nfn main() {\n    println!("{}", add(1, 2));\n}\n'
      BREAK_OLD='a + b' BREAK_NEW='a +'
      OK_OLD='a + b' OK_NEW='b + a'
      CHECKER_RE='^tree-sitter-rust [0-9][0-9A-Za-z.]*$'
      ;;
    *) echo "unknown language '$1'" >&2; return 1 ;;
  esac
  # The results, built by the test (bash's literal replacement of the one occurrence), not by edit.
  BROKEN="${ORIG/"$BREAK_OLD"/"$BREAK_NEW"}"
  WANT="${ORIG/"$OK_OLD"/"$OK_NEW"}"
}

# make_fixture NAME LANGUAGE STYLE — a fresh cell with LANGUAGE's valid file; the fixture's own facts
# checked (each --old occurs once). Sets SHA_ORIG.
make_fixture() {
  lang "$2"
  new_cell "$1-$2" "$3" notty "$EXT"
  put "${CELL}/${FILE}" "$ORIG"
  local old n
  for old in "$BREAK_OLD" "$OK_OLD"; do
    n="$(exec_plain grep -c -F -e "$old" "${CELL}/${FILE}")" || true
    [[ "$n" == 1 ]] || { echo "fixture ${2}: '${old}' occurs on ${n:-0} lines, want 1" >&2; return 1; }
  done
  SHA_ORIG="$(sha "${CELL}/${FILE}")"
  [[ -n "$SHA_ORIG" ]]
}

# syntax_fields — the last run's JSON verdict and `syntax` object into $JPY: verdict, status, language,
# checker, nerrors, line1, message1.
syntax_fields() {
  jpy "s = g('syntax', {}) or {}
e = s.get('errors') or []
print('verdict=' + str(g('verdict')))
print('status=' + str(s.get('status')))
print('language=' + str(s.get('language')))
print('checker=' + str(s.get('checker')))
print('nerrors=' + str(len(e)))
print('line1=' + (str(e[0].get('line')) if e else '<none>'))
print('message1=' + (str(e[0].get('message')) if e else '<none>'))"
}

# ── checks ────────────────────────────────────────────────────────────────────────────────────

# check_refused LANGUAGE STYLE — the breaking edit: exit 1; the file's sha256sum is the one taken before;
# the verdict is `refused: the edit would make FILE fail its syntax check (CHECKER): line L…; nothing
# written`; JSON syntax.status `refused`, the language, at least one error (for Python and shell, on the
# line the test knows, with the message the language's parser gives); nothing suggests skipping (T4).
check_refused() {
  make_fixture sc8-refused "$1" "$2"
  in_cell "$2" "edit ${FILE} --old $(q "$BREAK_OLD") --new $(q "$BREAK_NEW")"
  expect_status 1
  expect_sha "the file after the refused edit (byte-identical)" "$(sha "${CELL}/${FILE}")" "$SHA_ORIG"
  only_file
  no_stderr

  syntax_fields
  expect_j status refused
  expect_j language "$1"
  local checker v
  checker="$(jval checker)"
  [[ "$checker" =~ $CHECKER_RE ]] || flunk "checker '${checker}' is not /${CHECKER_RE}/"
  v="$(jval verdict)"
  [[ "$v" == "refused: the edit would make ${FILE} fail its syntax check (${checker}): line "* && "$v" == *"; nothing written" ]] \
    || flunk "verdict: ${v}"
  [[ "$(jval nerrors)" =~ ^[1-9][0-9]*$ ]] || flunk "syntax.errors is empty"
  if [[ -n "$ERR_LINE" ]]; then
    expect_j line1 "$ERR_LINE"
    [[ "$v" == *": line ${ERR_LINE}"[,:]* ]] || flunk "the verdict does not name line ${ERR_LINE}: ${v}"
    [[ "$(jval message1)" == *"$ERR_MSG"* ]] || flunk "the first error's message lacks '${ERR_MSG}': $(jval message1)"
  fi
  [[ "$output" != *"--skip-syntax-check"* ]] || flunk "the refusal suggests --skip-syntax-check (T4)"
}

# check_valid LANGUAGE STYLE — a valid edit applies: exit 0; the file's bytes are exactly the bytes the
# test built; the verdict ends `; syntax: ok (CHECKER)`; JSON syntax.status `ok`.
check_valid() {
  make_fixture sc8-valid "$1" "$2"
  put "${CELL}.want" "$WANT"
  in_cell "$2" "edit ${FILE} --old $(q "$OK_OLD") --new $(q "$OK_NEW")"
  expect_status 0
  expect_sha "the file after the valid edit" "$(sha "${CELL}/${FILE}")" "$(sha "${CELL}.want")"
  only_file

  syntax_fields
  expect_j status ok
  expect_j language "$1"
  expect_j nerrors 0
  local checker
  checker="$(jval checker)"
  [[ "$checker" =~ $CHECKER_RE ]] || flunk "checker '${checker}' is not /${CHECKER_RE}/"
  [[ "$(jval verdict)" == *"; syntax: ok (${checker})" ]] || flunk "verdict: $(jval verdict)"
}

# check_refused_text STYLE — the Python refusal in text: header `[refused]`, the verdict, a section
# `── syntax error 1: line 4…` followed by lines 2-6 of the would-be result (built by the test) numbered
# as edit numbers lines, line 4 marked; `do instead:` says to correct --new; no line names
# --skip-syntax-check; the file's hash unchanged.
check_refused_text() {
  make_fixture sc8-refused-text python "$1"
  put "${CELL}.want" "$BROKEN"
  in_cell "$1" "edit ${FILE} --old $(q "$BREAK_OLD") --new $(q "$BREAK_NEW") --text"
  expect_status 1
  expect_sha "the file after the refused edit (byte-identical)" "$(sha "${CELL}/${FILE}")" "$SHA_ORIG"
  no_stderr

  [[ "${lines[0]:-}" == "edit: ${FILE} [refused]" ]] || flunk "header line: ${lines[0]:-<none>}"
  [[ "${lines[1]:-}" == "verdict: refused: the edit would make ${FILE} fail its syntax check (python ${PYVER} compile): line 4"* ]] \
    || flunk "verdict line: ${lines[1]:-<none>}"
  local i start=-1 out=()
  for ((i = 2; i < ${#lines[@]}; i++)); do
    if [[ "${lines[i]}" == "── syntax error 1: line 4"* ]]; then
      start=$i
      break
    fi
  done
  ((start >= 0)) || flunk "no section '── syntax error 1: line 4…'"
  for ((i = start + 1; i < ${#lines[@]}; i++)); do
    [[ "${lines[i]}" == "── "* || "${lines[i]}" == "do instead: "* ]] && break
    out+=("${lines[i]}")
  done
  same_text "the would-be result's lines 2-6 under the error" "$(numbered "${CELL}.want" 2 6 4 4)" "$(printf '%s\n' "${out[@]}")"
  local line found=0
  for line in "${lines[@]}"; do
    [[ "$line" == "do instead: correct --new"* ]] && found=1
    [[ "$line" != *"--skip-syntax-check"* ]] || flunk "a line names --skip-syntax-check (T4): ${line}"
  done
  ((found == 1)) || flunk "no line 'do instead: correct --new …'"
}

# install_decoys DIR MARKER — executables DIR/python3 and DIR/bash that append to MARKER and exit 0.
install_decoys() {
  local name body
  exec_plain mkdir "$1" || return 1
  for name in python3 bash; do
    body="#!/bin/sh
echo \"decoy ${name} ran: \$*\" >>'$2'
exit 0"
    exec_plain sh -c 'printf "%s\n" "$2" >"$1" && chmod 0755 "$1"' w "$1/${name}" "$body" || return 1
  done
}

# check_decoys LANGUAGE STYLE — P002: with a decoy python3 and bash first on PATH, the breaking Python or
# shell edit is still refused by the real checker, the file's hash is unchanged, and the marker never
# appears. Control first: under that PATH, `python3` and `bash` resolve to the decoys, and running
# python3 writes the marker (then it is removed).
check_decoys() {
  make_fixture sc8-decoy "$1" "$2"
  local decoy="${CELL}.decoy" marker="${CELL}.marker"
  install_decoys "$decoy" "$marker"
  local path_prefix="PATH='${decoy}':\"\$PATH\""

  run_in "$2" notty "${path_prefix}; command -v python3; command -v bash; python3 -c pass"
  assert_within 20
  assert_status 0
  [[ "${lines[0]:-}" == "${decoy}/python3" && "${lines[1]:-}" == "${decoy}/bash" ]] || flunk "the decoys are not what PATH finds: ${output}"
  exec_plain test -s "$marker" || flunk "control: the decoy python3 ran but wrote no marker"
  exec_plain rm -f "$marker"

  in_cell "$2" "${path_prefix} edit ${FILE} --old $(q "$BREAK_OLD") --new $(q "$BREAK_NEW")"
  expect_status 1
  expect_sha "the file after the refused edit (byte-identical)" "$(sha "${CELL}/${FILE}")" "$SHA_ORIG"
  only_file
  syntax_fields
  expect_j status refused
  [[ "$(jval checker)" =~ $CHECKER_RE ]] || flunk "checker '$(jval checker)' is not /${CHECKER_RE}/"
  expect_j line1 "$ERR_LINE"
  if exec_plain test -e "$marker"; then
    flunk "a decoy ran during the edit: $(exec_plain cat "$marker")"
  fi
}

# go_image — GO_IMAGE from the environment, else from pins.env in the mounted repository; empty if neither.
go_image() {
  local img="${GO_IMAGE:-}" pins="${BATS_TEST_DIRNAME}/../../pins.env"
  if [[ -z "$img" && -f "$pins" ]]; then
    img="$(sed -n 's/^GO_IMAGE=//p' "$pins" | head -n 1)"
  fi
  printf '%s' "$img"
}

# gofmt_e IMAGE FORMAT — the bytes printf FORMAT builds, through `gofmt -e` in IMAGE; gofmt's status.
gofmt_e() {
  # shellcheck disable=SC2059 # FORMAT is the fixture, a printf format by design
  printf "$2" | timeout "$RUN_TIMEOUT" docker run --rm -i --network none --cap-drop ALL \
    --label "${THROWAWAY_LABEL}=1" "$1" gofmt -e >/dev/null
}

# check_go_gofmt — lore P005: the Go fixture's original and valid-edit result parse under Go's own
# parser (gofmt -e exits 0), and the breaking edit's result does not.
check_go_gofmt() {
  local img
  img="$(go_image)"
  [[ -n "$img" ]] || skip "the Go fixture was not confirmed by gofmt: GO_IMAGE is not in the runner's environment (tests/run.sh does not pass it) and pins.env has none"
  timeout "$RUN_TIMEOUT" docker image inspect "$img" >/dev/null 2>&1 </dev/null \
    || skip "the Go fixture was not confirmed by gofmt: GO_IMAGE ${img} is not on the Docker host (not pulled)"
  lang go
  gofmt_e "$img" "$ORIG" || { echo "gofmt -e rejects the Go fixture's original" >&2; return 1; }
  gofmt_e "$img" "$WANT" || { echo "gofmt -e rejects the Go fixture's valid edit" >&2; return 1; }
  if gofmt_e "$img" "$BROKEN" 2>/dev/null; then
    echo "gofmt -e accepts the Go fixture's breaking edit: it does not break the syntax" >&2
    return 1
  fi
}

@test "SC-8 [bash -c, notty] An edit that would make a Python, TypeScript, Go, Rust or shell file fail its syntax check is refused with the checker's error, and the file is byte-identical — Python: exit 1, python compile, line 4 expected ':'; file sha256 unchanged" { check_refused python c; }
@test "SC-8 [bash -lc, notty] An edit that would make a Python, TypeScript, Go, Rust or shell file fail its syntax check is refused with the checker's error, and the file is byte-identical — Python: exit 1, python compile, line 4 expected ':'; file sha256 unchanged" { check_refused python lc; }
@test "SC-8 [bash -c, notty] An edit that would make a Python, TypeScript, Go, Rust or shell file fail its syntax check is refused with the checker's error, and the file is byte-identical — shell: exit 1, bash -n, line 3 unexpected token; file sha256 unchanged" { check_refused shell c; }
@test "SC-8 [bash -lc, notty] An edit that would make a Python, TypeScript, Go, Rust or shell file fail its syntax check is refused with the checker's error, and the file is byte-identical — shell: exit 1, bash -n, line 3 unexpected token; file sha256 unchanged" { check_refused shell lc; }
@test "SC-8 [bash -c, notty] An edit that would make a Python, TypeScript, Go, Rust or shell file fail its syntax check is refused with the checker's error, and the file is byte-identical — TypeScript: exit 1, tree-sitter-typescript, a line named; file sha256 unchanged" { check_refused typescript c; }
@test "SC-8 [bash -lc, notty] An edit that would make a Python, TypeScript, Go, Rust or shell file fail its syntax check is refused with the checker's error, and the file is byte-identical — TypeScript: exit 1, tree-sitter-typescript, a line named; file sha256 unchanged" { check_refused typescript lc; }
@test "SC-8 [bash -c, notty] An edit that would make a Python, TypeScript, Go, Rust or shell file fail its syntax check is refused with the checker's error, and the file is byte-identical — TSX: exit 1, tree-sitter-typescript (tsx), a line named; file sha256 unchanged" { check_refused tsx c; }
@test "SC-8 [bash -lc, notty] An edit that would make a Python, TypeScript, Go, Rust or shell file fail its syntax check is refused with the checker's error, and the file is byte-identical — TSX: exit 1, tree-sitter-typescript (tsx), a line named; file sha256 unchanged" { check_refused tsx lc; }
@test "SC-8 [bash -c, notty] An edit that would make a Python, TypeScript, Go, Rust or shell file fail its syntax check is refused with the checker's error, and the file is byte-identical — Go: exit 1, tree-sitter-go, a line named; file sha256 unchanged" { check_refused go c; }
@test "SC-8 [bash -lc, notty] An edit that would make a Python, TypeScript, Go, Rust or shell file fail its syntax check is refused with the checker's error, and the file is byte-identical — Go: exit 1, tree-sitter-go, a line named; file sha256 unchanged" { check_refused go lc; }
@test "SC-8 [bash -c, notty] An edit that would make a Python, TypeScript, Go, Rust or shell file fail its syntax check is refused with the checker's error, and the file is byte-identical — Rust: exit 1, tree-sitter-rust, a line named; file sha256 unchanged" { check_refused rust c; }
@test "SC-8 [bash -lc, notty] An edit that would make a Python, TypeScript, Go, Rust or shell file fail its syntax check is refused with the checker's error, and the file is byte-identical — Rust: exit 1, tree-sitter-rust, a line named; file sha256 unchanged" { check_refused rust lc; }
@test "SC-8 [bash -c, notty] An edit that would make a Python, TypeScript, Go, Rust or shell file fail its syntax check is refused with the checker's error, and the file is byte-identical — Python, text: the error section shows the would-be lines 2-6, line 4 marked; no skip suggested" { check_refused_text c; }
@test "SC-8 [bash -lc, notty] An edit that would make a Python, TypeScript, Go, Rust or shell file fail its syntax check is refused with the checker's error, and the file is byte-identical — Python, text: the error section shows the would-be lines 2-6, line 4 marked; no skip suggested" { check_refused_text lc; }
@test "SC-8 [bash -c, notty] An edit that would make a Python, TypeScript, Go, Rust or shell file fail its syntax check is refused with the checker's error, and the file is byte-identical — a valid Python edit applies with syntax: ok; file sha256 equals the expected bytes" { check_valid python c; }
@test "SC-8 [bash -lc, notty] An edit that would make a Python, TypeScript, Go, Rust or shell file fail its syntax check is refused with the checker's error, and the file is byte-identical — a valid Python edit applies with syntax: ok; file sha256 equals the expected bytes" { check_valid python lc; }
@test "SC-8 [bash -c, notty] An edit that would make a Python, TypeScript, Go, Rust or shell file fail its syntax check is refused with the checker's error, and the file is byte-identical — a valid shell edit applies with syntax: ok; file sha256 equals the expected bytes" { check_valid shell c; }
@test "SC-8 [bash -lc, notty] An edit that would make a Python, TypeScript, Go, Rust or shell file fail its syntax check is refused with the checker's error, and the file is byte-identical — a valid shell edit applies with syntax: ok; file sha256 equals the expected bytes" { check_valid shell lc; }
@test "SC-8 [bash -c, notty] An edit that would make a Python, TypeScript, Go, Rust or shell file fail its syntax check is refused with the checker's error, and the file is byte-identical — a valid TypeScript edit applies with syntax: ok; file sha256 equals the expected bytes" { check_valid typescript c; }
@test "SC-8 [bash -lc, notty] An edit that would make a Python, TypeScript, Go, Rust or shell file fail its syntax check is refused with the checker's error, and the file is byte-identical — a valid TypeScript edit applies with syntax: ok; file sha256 equals the expected bytes" { check_valid typescript lc; }
@test "SC-8 [bash -c, notty] An edit that would make a Python, TypeScript, Go, Rust or shell file fail its syntax check is refused with the checker's error, and the file is byte-identical — a valid TSX edit applies with syntax: ok; file sha256 equals the expected bytes" { check_valid tsx c; }
@test "SC-8 [bash -lc, notty] An edit that would make a Python, TypeScript, Go, Rust or shell file fail its syntax check is refused with the checker's error, and the file is byte-identical — a valid TSX edit applies with syntax: ok; file sha256 equals the expected bytes" { check_valid tsx lc; }
@test "SC-8 [bash -c, notty] An edit that would make a Python, TypeScript, Go, Rust or shell file fail its syntax check is refused with the checker's error, and the file is byte-identical — a valid Go edit applies with syntax: ok; file sha256 equals the expected bytes" { check_valid go c; }
@test "SC-8 [bash -lc, notty] An edit that would make a Python, TypeScript, Go, Rust or shell file fail its syntax check is refused with the checker's error, and the file is byte-identical — a valid Go edit applies with syntax: ok; file sha256 equals the expected bytes" { check_valid go lc; }
@test "SC-8 [bash -c, notty] An edit that would make a Python, TypeScript, Go, Rust or shell file fail its syntax check is refused with the checker's error, and the file is byte-identical — a valid Rust edit applies with syntax: ok; file sha256 equals the expected bytes" { check_valid rust c; }
@test "SC-8 [bash -lc, notty] An edit that would make a Python, TypeScript, Go, Rust or shell file fail its syntax check is refused with the checker's error, and the file is byte-identical — a valid Rust edit applies with syntax: ok; file sha256 equals the expected bytes" { check_valid rust lc; }
@test "SC-8 [bash -c, notty] An edit that would make a Python, TypeScript, Go, Rust or shell file fail its syntax check is refused with the checker's error, and the file is byte-identical — P002: decoy python3 and bash first on PATH; the Python edit is still refused, sha256 unchanged, no decoy ran" { check_decoys python c; }
@test "SC-8 [bash -lc, notty] An edit that would make a Python, TypeScript, Go, Rust or shell file fail its syntax check is refused with the checker's error, and the file is byte-identical — P002: decoy python3 and bash first on PATH; the Python edit is still refused, sha256 unchanged, no decoy ran" { check_decoys python lc; }
@test "SC-8 [bash -c, notty] An edit that would make a Python, TypeScript, Go, Rust or shell file fail its syntax check is refused with the checker's error, and the file is byte-identical — P002: decoy python3 and bash first on PATH; the shell edit is still refused, sha256 unchanged, no decoy ran" { check_decoys shell c; }
@test "SC-8 [bash -lc, notty] An edit that would make a Python, TypeScript, Go, Rust or shell file fail its syntax check is refused with the checker's error, and the file is byte-identical — P002: decoy python3 and bash first on PATH; the shell edit is still refused, sha256 unchanged, no decoy ran" { check_decoys shell lc; }
@test "SC-8 [lore P005, runner] the Go fixture is confirmed by Go's own parser: gofmt -e in GO_IMAGE accepts the original and the valid edit, and rejects the breaking edit" { check_go_gofmt; }
