#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# SC-7 — "An edit addressed by viewer anchors applies when the anchored lines are unchanged and is
# refused, naming the changed lines, when they are not". (Feature 008, slice 1; spec FR-13 to FR-17;
# contracts/edit-cli.md § Slice 1: Anchored edit applied, Anchors stale; research R11.)
#
# Written from the contract before the tool existed. Every expected value is the test's own (P004, P005):
#   - the anchors are this file's oracle, the image's Python with hashlib, never `view`: it reads the
#     file's raw bytes, splits them at \n, drops one \r before it, and takes the first 6 hex characters
#     of sha256 of each line (006 FR-33's definition, written out again here); it also formats the
#     lines as `view --anchors` shows them, `{n:>W}{m}{anchor} {text}`, with `>` on the given lines;
#   - the original and the expected bytes are both built by the container's printf, and "applies" is
#     the file's sha256sum equal to the expected file's; every refusal is the file's sha256sum equal to
#     the one taken just before the edit (after the test's own change, when there is one).
# Cases: unchanged (a range, and a single line: applies); a changed end (exit 3, the line named with its
# old and new anchor); an end past the end of the file (exit 3, named); a move (exit 3, naming where the
# lines are now, with the rerun command, which then applies).
#
# The fixture is a .txt file, so the syntax check has no language (`syntax: not checked (language
# unknown)`): this file is about anchors, and SC-8's file is about the check.
#
# Isolation: every cell creates its own directory and file, named after the check, the style and the
# terminal mode; `mkdir` without -p refuses a path that exists, so no cell can reuse another's fixture.
# Cells: bash -c and bash -lc, `notty` (JSON is the default when stdout is not a terminal).

load helpers

setup_file() {
  stamp_check
  EDIT_DIR="$(container_tmpdir edit-sc7)"
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

# ── the oracle ───────────────────────────────────────────────────────────────────────────────

# argv = FILE TARGETS (comma-separated line numbers, may be empty). Prints, for every line of FILE,
# `a:N:hhhhhh` (the anchor in its `--at` form) and `t:<line>` (the line as `view --anchors` shows it,
# `>` on the TARGETS).
read -r -d '' ANCHOR_ORACLE <<'PY' || true
import hashlib, sys
path = sys.argv[1]
targets = {int(t) for t in sys.argv[2].split(",") if t}
raw = open(path, "rb").read().split(b"\n")
if raw and raw[-1] == b"":
    raw.pop()
width = len(str(len(raw)))
for n, line in enumerate(raw, 1):
    if line.endswith(b"\r"):
        line = line[:-1]
    anchor = hashlib.sha256(line).hexdigest()[:6]
    print("a:%d:%s" % (n, anchor))
    print("t:%*d%s%s %s" % (width, n, ">" if n in targets else " ", anchor, line.decode("utf-8", "replace")))
PY

# oracle PATH [TARGETS] — run the oracle over PATH in the container; output in $ORA.
oracle() {
  ORA="$(exec_plain "$AGENT_PY" -I -c "$ANCHOR_ORACLE" "$1" "${2:-}")" || { echo "the oracle failed: ${ORA}" >&2; return 1; }
}

# anchor N — line N's anchor (6 hex) from $ORA.
anchor() {
  sed -n "s/^a:$1://p" <<<"$ORA"
}

# anchors_at A B — `N:hhhhhh` for lines A..B, one per line, from $ORA.
anchors_at() {
  sed -n 's/^a://p' <<<"$ORA" | sed -n "$1,$2p"
}

# shown_at A B — the `view --anchors` lines A..B, from $ORA.
shown_at() {
  sed -n 's/^t://p' <<<"$ORA" | sed -n "$1,$2p"
}

# text_body — the lines of the last text run after the verdict, without `── ` section labels, up to
# the `do instead:` line; into $BODY.
text_body() {
  local i out=()
  for ((i = 2; i < ${#lines[@]}; i++)); do
    case "${lines[i]}" in
      "── "*) continue ;;
      "do instead: "*) break ;;
    esac
    out+=("${lines[i]}")
  done
  BODY="$(printf '%s\n' "${out[@]}")"
}

# ── the fixture ────────────────────────────────────────────────────────────────────────────────

# 12 lines, LF, each line's content distinct (so each anchor occurs once).
ORIG='alpha one\nbravo two\ncharlie three\ndelta four\necho five\nfoxtrot six\ngolf seven\nhotel eight\nindia nine\njuliet ten\nkilo eleven\nlima twelve\n'
# Lines 5-7 replaced by two lines: written out, not derived from the tool.
WANT_RANGE='alpha one\nbravo two\ncharlie three\ndelta four\nNEW five\nNEW six\nhotel eight\nindia nine\njuliet ten\nkilo eleven\nlima twelve\n'
# Line 3 replaced.
WANT_ONE='alpha one\nbravo two\ncharlie THREE\ndelta four\necho five\nfoxtrot six\ngolf seven\nhotel eight\nindia nine\njuliet ten\nkilo eleven\nlima twelve\n'
# Three lines inserted at the top (the move), and the same file after the rerun at the new numbers.
TOP='new top one\nnew top two\nnew top three\n'
NEW_RANGE="$(printf '%q' $'NEW five\nNEW six')"

# make_fixture NAME STYLE — a fresh cell with the 12-line original; its own facts checked (P004); the
# oracle run over it. Sets SHA_ORIG, H3, H5, H7, H11, H12.
make_fixture() {
  new_cell "$1" "$2" notty txt
  put "${CELL}/${FILE}" "$ORIG"
  [[ "$(exec_plain sh -c 'wc -l <"$1"' n "${CELL}/${FILE}")" == 12 ]] || { echo "fixture: not 12 lines" >&2; return 1; }
  oracle "${CELL}/${FILE}"
  H3="$(anchor 3)" H5="$(anchor 5)" H7="$(anchor 7)" H11="$(anchor 11)" H12="$(anchor 12)"
  local h
  for h in "$H3" "$H5" "$H7" "$H11" "$H12"; do
    [[ "$h" =~ ^[0-9a-f]{6}$ ]] || { echo "fixture: oracle anchor '${h}'" >&2; return 1; }
  done
  [[ "$(sed -n 's/^a:[0-9]*://p' <<<"$ORA" | sort | uniq -d)" == "" ]] || { echo "fixture: two lines share an anchor" >&2; return 1; }
  SHA_ORIG="$(sha "${CELL}/${FILE}")"
  [[ -n "$SHA_ORIG" ]]
}

# unchanged WHAT — the file's sha256sum is SHA_ORIG (taken just before the edit), and nothing else is in
# the directory.
unchanged() {
  expect_sha "$1" "$(sha "${CELL}/${FILE}")" "$SHA_ORIG"
  only_file
}

# ── checks ────────────────────────────────────────────────────────────────────────────────────

# check_unchanged STYLE — `--at 5:h5..7:h7` with both anchors unchanged: exit 0; the file's bytes are
# exactly the expected bytes; JSON level `anchors`, the anchors as given, the new text at lines 5-6 of
# 11; the verdict says it was addressed by anchors and checked at lines 5 and 7; `lines` is the edited
# region with 3 lines of context (2-9), numbered as view numbers them, 5-6 marked.
check_unchanged() {
  make_fixture sc7-unchanged "$1"
  put "${CELL}.want" "$WANT_RANGE"
  local sha_want
  sha_want="$(sha "${CELL}.want")"
  in_cell "$1" "edit ${FILE} --at 5:${H5}..7:${H7} --new ${NEW_RANGE}"
  expect_status 0
  expect_sha "the file after the anchored edit" "$(sha "${CELL}/${FILE}")" "$sha_want"
  only_file

  jfields exit level mapping start end total changed anchors.start anchors.end sha256_before sha256_after verdict
  expect_j exit 0
  expect_j level anchors
  expect_j mapping null
  expect_j start 5
  expect_j end 6
  expect_j total 11
  expect_j changed true
  expect_j anchors.start "5:${H5}"
  expect_j anchors.end "7:${H7}"
  expect_j sha256_before "$SHA_ORIG"
  expect_j sha256_after "$sha_want"
  local v
  v="$(jval verdict)"
  [[ "$v" == "edited lines 5-6 of 11 (addressed by anchors"* && "$v" == *"checked at lines 5 and 7"* ]] || flunk "verdict: ${v}"

  local want
  want="$(numbered "${CELL}.want" 2 9 5 6)"
  jpy "print('\n'.join(g('lines', [])))"
  same_text "JSON lines (the edited region)" "$want" "$JPY"
}

# check_single STYLE — `--at 3:h3`, one line, unchanged: exit 0; the file's bytes are exactly the
# expected bytes; both JSON anchors are `3:h3`.
check_single() {
  make_fixture sc7-single "$1"
  put "${CELL}.want" "$WANT_ONE"
  in_cell "$1" "edit ${FILE} --at 3:${H3} --new 'charlie THREE'"
  expect_status 0
  expect_sha "the file after the one-line anchored edit" "$(sha "${CELL}/${FILE}")" "$(sha "${CELL}.want")"
  only_file
  jfields level anchors.start anchors.end verdict
  expect_j level anchors
  expect_j anchors.start "3:${H3}"
  expect_j anchors.end "3:${H3}"
  [[ "$(jval verdict)" =~ ^edited\ lines?\ 3(-3)?\ of\ 12\ \(addressed\ by\ anchors ]] || flunk "verdict: $(jval verdict)"
}

# change_line_7 — the test's own change: line 7 gains ` changed`; the oracle re-run with 5 and 7 marked.
# Sets H7NOW and SHA_ORIG (the bytes just before the edit).
change_line_7() {
  exec_plain sed -i '7s/$/ changed/' "${CELL}/${FILE}"
  oracle "${CELL}/${FILE}" 5,7
  H7NOW="$(anchor 7)"
  [[ "$H7NOW" =~ ^[0-9a-f]{6}$ && "$H7NOW" != "$H7" && "$(anchor 5)" == "$H5" ]] || { echo "fixture: line 7's anchor did not change alone" >&2; return 1; }
  SHA_ORIG="$(sha "${CELL}/${FILE}")"
}

# check_changed STYLE — line 7 (the range's end) changed after the anchors were taken: exit 3, scope
# `anchors stale`, the verdict names line 7 with its old and new anchor, `changed` says the same, the
# remedy is `view --anchors FILE:5-7`, `anchors_now` are the oracle's for lines 2-10 (3 lines of context);
# the file's hash is the one taken before the edit.
check_changed() {
  make_fixture sc7-changed "$1"
  change_line_7
  in_cell "$1" "edit ${FILE} --at 5:${H5}..7:${H7} --new ${NEW_RANGE}"
  expect_status 3
  unchanged "the file after an edit refused for a changed anchor"
  no_stderr

  jfields exit scope verdict remedy moved_to changed
  expect_j exit 3
  expect_j scope "anchors stale"
  expect_j verdict "anchored lines changed: line 7 (anchor ${H7}, now ${H7NOW}); nothing written"
  expect_j moved_to null
  expect_j changed "[{\"expected\": \"${H7}\", \"line\": 7, \"now\": \"${H7NOW}\"}]"
  [[ "$(jval remedy)" == *"view --anchors ${FILE}:5-7"* ]] || flunk "remedy: $(jval remedy)"
  jpy "print('\n'.join(g('anchors_now', [])))"
  same_text "anchors_now (the oracle's, lines 2-10)" "$(anchors_at 2 10)" "$JPY"
}

# check_changed_text STYLE — the same refusal in text: header scope `anchors stale`, the verdict, lines
# 2-10 exactly as `view --anchors` shows them (the oracle's), `>` on 5 and 7, and `do instead:` naming
# `view --anchors FILE:5-7`; the file's hash unchanged.
check_changed_text() {
  make_fixture sc7-changed-text "$1"
  change_line_7
  in_cell "$1" "edit ${FILE} --at 5:${H5}..7:${H7} --new ${NEW_RANGE} --text"
  expect_status 3
  unchanged "the file after an edit refused for a changed anchor"
  no_stderr

  [[ "${lines[0]:-}" == "edit: ${FILE} [anchors stale]" ]] || flunk "header line: ${lines[0]:-<none>}"
  [[ "${lines[1]:-}" == "verdict: anchored lines changed: line 7 (anchor ${H7}, now ${H7NOW}); nothing written" ]] || flunk "verdict line: ${lines[1]:-<none>}"
  text_body
  same_text "the lines shown (the oracle's view --anchors lines 2-10)" "$(shown_at 2 10)" "$BODY"
  local line found=0
  for line in "${lines[@]:2}"; do
    [[ "$line" == "do instead: "*"view --anchors ${FILE}:5-7"* ]] && found=1
  done
  ((found == 1)) || flunk "no line 'do instead: … view --anchors ${FILE}:5-7 …'"
}

# check_past_end STYLE — `--at 11:h11..14:h12` on a 12-line file (the agent's view had two more lines):
# exit 3, the verdict names line 14 as past the end (12 lines), `changed` carries `now: null`; the
# file's hash unchanged.
check_past_end() {
  make_fixture sc7-past-end "$1"
  in_cell "$1" "edit ${FILE} --at 11:${H11}..14:${H12} --new 'x'"
  expect_status 3
  unchanged "the file after an edit refused for an end past the end"
  no_stderr
  jfields scope verdict changed moved_to
  expect_j scope "anchors stale"
  expect_j verdict "anchored lines changed: line 14 is past the end (12 lines); nothing written"
  expect_j changed "[{\"expected\": \"${H12}\", \"line\": 14, \"now\": null}]"
  expect_j moved_to null
}

# check_moved STYLE — three lines inserted at the top after the anchors were taken, so lines 5-7 are
# now 8-10: exit 3, the verdict names the move, `moved_to` is 8-10, the remedy carries the exact
# `--at 8:h5..10:h7`, `anchors_now` are the oracle's for 5-13; the file's hash unchanged. Then the
# rerun at the new numbers applies, and the file's bytes are exactly the expected bytes.
check_moved() {
  make_fixture sc7-moved "$1"
  exec_plain sh -c 'cd "$1" && { printf "$2"; cat "$3"; } >moved.tmp && mv moved.tmp "$3"' ins "$CELL" "$TOP" "$FILE"
  oracle "${CELL}/${FILE}"
  [[ "$(exec_plain sh -c 'wc -l <"$1"' n "${CELL}/${FILE}")" == 15 && "$(anchor 8)" == "$H5" && "$(anchor 10)" == "$H7" ]] \
    || { echo "fixture: the move did not put lines 5-7 at 8-10" >&2; return 1; }
  SHA_ORIG="$(sha "${CELL}/${FILE}")"

  in_cell "$1" "edit ${FILE} --at 5:${H5}..7:${H7} --new ${NEW_RANGE}"
  expect_status 3
  unchanged "the file after an edit refused for moved lines"
  no_stderr
  jfields exit scope verdict remedy moved_to
  expect_j exit 3
  expect_j scope "anchors stale"
  expect_j verdict "anchored lines moved: lines 5-7 are now lines 8-10; nothing written"
  expect_j moved_to '{"end": 10, "start": 8}'
  [[ "$(jval remedy)" == *"--at 8:${H5}..10:${H7}"* ]] || flunk "remedy lacks the rerun '--at 8:${H5}..10:${H7}': $(jval remedy)"
  jpy "print('\n'.join(g('anchors_now', [])))"
  same_text "anchors_now (the oracle's, lines 5-13)" "$(anchors_at 5 13)" "$JPY"

  # The rerun the remedy names.
  put "${CELL}.want" "${TOP}${WANT_RANGE}"
  in_cell "$1" "edit ${FILE} --at 8:${H5}..10:${H7} --new ${NEW_RANGE}"
  expect_status 0
  expect_sha "the file after the rerun at the new numbers" "$(sha "${CELL}/${FILE}")" "$(sha "${CELL}.want")"
  only_file
}

@test "SC-7 [bash -c, notty] An edit addressed by viewer anchors applies when the anchored lines are unchanged and is refused, naming the changed lines, when they are not — unchanged range 5-7: applies; file sha256 equals the expected bytes; level anchors" { check_unchanged c; }
@test "SC-7 [bash -lc, notty] An edit addressed by viewer anchors applies when the anchored lines are unchanged and is refused, naming the changed lines, when they are not — unchanged range 5-7: applies; file sha256 equals the expected bytes; level anchors" { check_unchanged lc; }
@test "SC-7 [bash -c, notty] An edit addressed by viewer anchors applies when the anchored lines are unchanged and is refused, naming the changed lines, when they are not — unchanged single line 3: applies; file sha256 equals the expected bytes" { check_single c; }
@test "SC-7 [bash -lc, notty] An edit addressed by viewer anchors applies when the anchored lines are unchanged and is refused, naming the changed lines, when they are not — unchanged single line 3: applies; file sha256 equals the expected bytes" { check_single lc; }
@test "SC-7 [bash -c, notty] An edit addressed by viewer anchors applies when the anchored lines are unchanged and is refused, naming the changed lines, when they are not — changed end: exit 3 naming line 7 with old and new anchor; file sha256 unchanged" { check_changed c; }
@test "SC-7 [bash -lc, notty] An edit addressed by viewer anchors applies when the anchored lines are unchanged and is refused, naming the changed lines, when they are not — changed end: exit 3 naming line 7 with old and new anchor; file sha256 unchanged" { check_changed lc; }
@test "SC-7 [bash -c, notty] An edit addressed by viewer anchors applies when the anchored lines are unchanged and is refused, naming the changed lines, when they are not — changed end, text: lines 2-10 as view --anchors shows them, 5 and 7 marked; file sha256 unchanged" { check_changed_text c; }
@test "SC-7 [bash -lc, notty] An edit addressed by viewer anchors applies when the anchored lines are unchanged and is refused, naming the changed lines, when they are not — changed end, text: lines 2-10 as view --anchors shows them, 5 and 7 marked; file sha256 unchanged" { check_changed_text lc; }
@test "SC-7 [bash -c, notty] An edit addressed by viewer anchors applies when the anchored lines are unchanged and is refused, naming the changed lines, when they are not — end past the end: exit 3 naming line 14 past the end (12 lines); file sha256 unchanged" { check_past_end c; }
@test "SC-7 [bash -lc, notty] An edit addressed by viewer anchors applies when the anchored lines are unchanged and is refused, naming the changed lines, when they are not — end past the end: exit 3 naming line 14 past the end (12 lines); file sha256 unchanged" { check_past_end lc; }
@test "SC-7 [bash -c, notty] An edit addressed by viewer anchors applies when the anchored lines are unchanged and is refused, naming the changed lines, when they are not — move: exit 3, lines 5-7 are now lines 8-10, rerun command named; file sha256 unchanged; the rerun applies" { check_moved c; }
@test "SC-7 [bash -lc, notty] An edit addressed by viewer anchors applies when the anchored lines are unchanged and is refused, naming the changed lines, when they are not — move: exit 3, lines 5-7 are now lines 8-10, rerun command named; file sha256 unchanged; the rerun applies" { check_moved lc; }
