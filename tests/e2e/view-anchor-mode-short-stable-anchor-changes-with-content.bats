#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# SC-7 — "The viewer's anchor mode shows a short, stable anchor per line that changes when the line's
# content changes". (Feature 006, slice 1; spec FR-32 to FR-35, D-9; tasks.md T018;
# contracts/view-search-cli.md § Slice 1, `view --anchors`.)
#
# Written from the contract before the tool existed (tasks.md Phase 6, tests first). The anchors are
# the test's own (lore cross-stack P004, P005): this file's oracle, the image's Python, reads the
# file's raw bytes, splits them at \n, drops a \r before it, and takes the first 6 hex characters of
# hashlib.sha256 of each line; the expected text lines are formatted from the same bytes as
# `{n:>W}{marker}{anchor} {text}` (W = digits of the file's line count, text decoded with U+FFFD
# replacement, and a line longer than COLUMNS cut to COLUMNS characters plus ` …[cut N bytes]`).
# Stability is checked by a second view, by inserting 3 lines at the top (each line keeps its anchor
# at N+3), and by changing one line (only its anchor changes).
#
# The file is built by fixtures/bounded-read-slice1.sh (`anchors`): 60 lines with a CRLF line and its
# LF copy, a 305-byte line, a line with an invalid UTF-8 byte and two empty lines; afresh per test.
# Cells: bash -c and bash -lc, `notty`.

load helpers

FIXTURE=/tmp/bounded-read-slice1-sc7.sh

# The oracle: argv = FILE A B TARGET COLUMNS (TARGET 0 = none). Prints, for lines A..B of FILE,
# `a:N:hhhhhh` (the anchor in its JSON form) and `t:<line>` (the text line as view must print it).
read -r -d '' ANCHOR_ORACLE <<'PY' || true
import hashlib, sys
path, a, b, target, columns = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
raw = open(path, "rb").read().split(b"\n")
if raw and raw[-1] == b"":
    raw.pop()
width = len(str(len(raw)))
for n in range(a, min(b, len(raw)) + 1):
    line = raw[n - 1]
    if line.endswith(b"\r"):
        line = line[:-1]
    anchor = hashlib.sha256(line).hexdigest()[:6]
    shown = "%*d%s%s %s" % (width, n, ">" if n == target else " ", anchor, line.decode("utf-8", "replace"))
    if columns and len(shown) > columns:
        shown = shown[:columns] + " …[cut %d bytes]" % len(shown[columns:].encode("utf-8"))
    print("a:%d:%s" % (n, anchor))
    print("t:" + shown)
PY

setup_file() {
  stamp_check
  copy_into_container "${BATS_TEST_DIRNAME}/fixtures/bounded-read-slice1.sh" "$FIXTURE" 0755
}

setup() {
  WORK="$(container_tmpdir sc7anchors)"
  FX="${WORK}/fx"
  SCRATCH="${WORK}/scratch"
  exec_plain sh "$FIXTURE" anchors "$FX" >/dev/null
}

teardown() {
  container_rm "$WORK"
}

# ── helpers (this file's own; the 006 files repeat them so each reads alone) ─────────────────────

# in_dir STYLE DIR CMD [K=V]... — run CMD in DIR with this test's session scratch; stderr goes to
# $WORK/stderr so stdout stays one JSON document.
in_dir() {
  local style="$1" dir="$2" cmd="$3" kv
  shift 3
  local -a envs=(-e "TIMELIKE_SCRATCH_ROOT=${SCRATCH}" -e "TIMELIKE_SESSION=boundedread")
  for kv in "$@"; do envs+=(-e "$kv"); done
  run_in "${envs[@]}" "$style" notty "cd '${dir}' && { ${cmd}; } 2>'${WORK}/stderr'"
  assert_within 20
}

# flunk MESSAGE — fail with the last run's exit, stdout and stderr.
flunk() {
  local err
  err="$(exec_plain cat "${WORK}/stderr" 2>&1)" || true
  printf '%s\nexit %s; stdout:\n%s\nstderr:\n%s\n' "$1" "$status" "$output" "$err" >&2
  return 1
}

expect_status() {
  [[ "$status" == "$1" ]] || flunk "expected exit $1, got $status"
}

# jpy SCRIPT — Python over the last run's stdout, parsed as JSON into `d`; `g(k)` reads a field by a
# dotted path (`truncated.more`), top-level first, then under `data`. Output in $JPY.
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

# text_body — the shown file lines of the last text run, into $BODY: every line after the verdict,
# without `── ` section labels, up to the first closing line (more:, exit:, full output:, … omitted)
# or a `long lines cut:` line.
text_body() {
  local i out=()
  for ((i = 2; i < ${#lines[@]}; i++)); do
    case "${lines[i]}" in
      "── "*) continue ;;
      "more: "* | "exit: "* | "full output: "* | "… omitted "* | "long lines cut: "*) break ;;
    esac
    out+=("${lines[i]}")
  done
  BODY="$(printf '%s\n' "${out[@]}")"
}

# ── the oracle ───────────────────────────────────────────────────────────────────────────────

# expected FILE A B [TARGET] — the oracle over FILE (in the fixture directory); sets EXP_ANCHORS (one
# `N:hhhhhh` per line) and EXP_TEXT (one view line per line). COLUMNS is the default, 200.
expected() {
  local out
  out="$(exec_plain "$AGENT_PY" -I -c "$ANCHOR_ORACLE" "${FX}/$1" "$2" "$3" "${4:-0}" 200)" \
    || { echo "the oracle failed: ${out}" >&2; return 1; }
  EXP_ANCHORS="$(sed -n 's/^a://p' <<<"$out")"
  EXP_TEXT="$(sed -n 's/^t://p' <<<"$out")"
}

# json_anchors CMD STYLE — run CMD (a JSON view) in the fixture directory; the `anchors` array, one per
# line, into $GOT_ANCHORS, and check it is parallel to the file lines in `lines` and every entry is
# `N:` + 6 lowercase hex. `lines` also carries view's `long lines cut:` line as its last body line
# (contract § Long lines), which is not a line of the file and has no anchor.
json_anchors() {
  in_dir "$2" "$FX" "$1"
  expect_status 0
  jpy "a = g('anchors', None)
L = [x for x in g('lines', []) if not x.startswith('long lines cut: ')]
import re
if not isinstance(a, list):
    print('ERR anchors is ' + json.dumps(a))
elif len(a) != len(L):
    print('ERR %d anchors for %d lines' % (len(a), len(L)))
else:
    bad = [x for x in a if not re.fullmatch(r'[0-9]+:[0-9a-f]{6}', str(x))]
    print('ERR not N:hhhhhh: ' + json.dumps(bad[:3]) if bad else '\n'.join(a))"
  [[ "$JPY" != "ERR "* ]] || flunk "${1}: ${JPY}"
  GOT_ANCHORS="$JPY"
}

# anchor_of N — the hash part of line N's entry in $GOT_ANCHORS.
anchor_of() {
  sed -n "s/^$1://p" <<<"$GOT_ANCHORS"
}

# ── checks ────────────────────────────────────────────────────────────────────────────────────

# check_anchors_json STYLE — `view --anchors --json anchors.txt`: one anchor per line, each equal to the
# test's own sha256 prefix (CRLF line, long line, invalid byte and empty lines included); the CRLF
# line and its LF copy share an anchor, as do the two empty lines; a second view gives the same
# anchors; without --anchors there is no `anchors` key.
check_anchors_json() {
  expected anchors.txt 1 60
  json_anchors "view --anchors --json anchors.txt" "$1"
  same_text "anchors (the test's own sha256 prefixes)" "$EXP_ANCHORS" "$GOT_ANCHORS"
  [[ "$(anchor_of 10)" == "$(anchor_of 11)" ]] || flunk "the CRLF line 10 and its LF copy 11 differ: $(anchor_of 10) $(anchor_of 11)"
  [[ "$(anchor_of 45)" == "$(anchor_of 46)" ]] || flunk "the two empty lines 45 and 46 differ"
  local first="$GOT_ANCHORS"

  json_anchors "view --anchors --json anchors.txt" "$1"
  same_text "anchors on a second view" "$first" "$GOT_ANCHORS"

  in_dir "$1" "$FX" "view --json anchors.txt"
  expect_status 0
  jfields anchors
  expect_j anchors "<absent>"
}

# check_anchors_insert STYLE — 3 lines inserted at the top: every original line keeps its anchor at
# N+3, and the new file's anchors are the oracle's.
check_anchors_insert() {
  json_anchors "view --anchors --json anchors.txt" "$1"
  local before="$GOT_ANCHORS"
  exec_plain sh -c 'cd "$1" && { printf "%s\n" "inserted one" "inserted two" "inserted three"; cat anchors.txt; } >moved.tmp && mv moved.tmp anchors.txt' ins "$FX"
  [[ "$(exec_plain sh -c 'wc -l <"$1"' n "${FX}/anchors.txt")" == 63 ]] || { echo "the insertion did not make 63 lines" >&2; return 1; }

  expected anchors.txt 1 63
  json_anchors "view --anchors --json anchors.txt" "$1"
  same_text "anchors after inserting 3 lines (the oracle's)" "$EXP_ANCHORS" "$GOT_ANCHORS"
  local moved
  moved="$(awk -F: '{ printf "%d:%s\n", $1 + 3, $2 }' <<<"$before")"
  same_text "the original lines' anchors, now at N+3" "$moved" "$(sed -n '4,$p' <<<"$GOT_ANCHORS")"
}

# check_anchors_change STYLE — line 25's content changes: its anchor changes, every other line's stays.
check_anchors_change() {
  json_anchors "view --anchors --json anchors.txt" "$1"
  local before="$GOT_ANCHORS"
  exec_plain sed -i '25s/$/ changed/' "${FX}/anchors.txt"

  expected anchors.txt 1 60
  json_anchors "view --anchors --json anchors.txt" "$1"
  same_text "anchors after changing line 25 (the oracle's)" "$EXP_ANCHORS" "$GOT_ANCHORS"
  local -a b a
  local i diff=()
  mapfile -t b <<<"$before"
  mapfile -t a <<<"$GOT_ANCHORS"
  [[ ${#a[@]} -eq 60 && ${#b[@]} -eq 60 ]] || flunk "${#b[@]} anchors before, ${#a[@]} after; want 60"
  for ((i = 0; i < 60; i++)); do
    [[ "${a[i]}" == "${b[i]}" ]] || diff+=("$((i + 1))")
  done
  [[ "${diff[*]}" == 25 ]] || flunk "anchors changed on lines '${diff[*]}', want only line 25"
}

# check_anchors_text STYLE — text mode: each line is `{n:>W}{marker}{anchor} {text}`, exactly the
# oracle's (the long line cut at COLUMNS, the invalid byte as U+FFFD), and the long-lines command keeps
# --anchors; on `anchors.txt:30` the target line carries `>` before its anchor.
check_anchors_text() {
  expected anchors.txt 1 60
  in_dir "$1" "$FX" "view --anchors --text anchors.txt"
  expect_status 0
  [[ "${lines[0]:-}" == "view: anchors.txt [lines 1-60 of 60]" ]] || flunk "header line: ${lines[0]:-<none>}"
  text_body
  same_text "text lines with anchors" "$EXP_TEXT" "$BODY"
  local line long=""
  for line in "${lines[@]}"; do
    [[ "$line" == "long lines cut: "* ]] && long="$line"
  done
  [[ "$long" == "long lines cut: 1; read them whole with: view "* && " ${long} " == *" --anchors "* && " ${long} " == *" --columns 0 "* ]] \
    || flunk "the long-lines line does not keep --anchors: '${long}'"

  expected anchors.txt 20 40 30
  in_dir "$1" "$FX" "view --anchors --text anchors.txt:30"
  expect_status 0
  text_body
  same_text "text lines of anchors.txt:30 with anchors" "$EXP_TEXT" "$BODY"
  [[ "$BODY" == *$'\n'"30>"[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]" line 30: "* ]] || flunk "line 30 is not marked with > before its anchor"
}

# check_anchors_continue STYLE — `view --anchors anchors.txt:20-30`: the oracle's anchors for 20-30,
# and `next` and `truncated.more` keep --anchors; the next window, run as printed, shows 31-60's
# anchors.
check_anchors_continue() {
  expected anchors.txt 20 30
  json_anchors "view --anchors --json anchors.txt:20-30" "$1"
  same_text "anchors of lines 20-30" "$EXP_ANCHORS" "$GOT_ANCHORS"
  jfields next truncated.more
  local next more
  next="$(jval next)"
  more="$(jval truncated.more)"
  [[ "$next" == "$more" ]] || flunk "next '${next}' differs from truncated.more '${more}'"
  [[ "$next" == "view "* && " ${next} " == *" --anchors "* && " ${next} " == *" anchors.txt:31-150 "* ]] \
    || flunk "next window does not keep --anchors: '${next}'"

  expected anchors.txt 31 60
  json_anchors "$next" "$1"
  same_text "anchors shown by '${next}'" "$EXP_ANCHORS" "$GOT_ANCHORS"
}

# check_anchors_directory STYLE — `--anchors` on a directory is a usage error (exit 2).
check_anchors_directory() {
  in_dir "$1" "$FX" "view --anchors ."
  expect_status 2
}

@test "SC-7 the viewer's anchor mode shows a short, stable anchor per line that changes when the line's content changes [bash -c, notty]" { check_anchors_json c; }
@test "SC-7 the viewer's anchor mode shows a short, stable anchor per line that changes when the line's content changes [bash -lc, notty]" { check_anchors_json lc; }
@test "SC-7 anchor mode: inserting 3 lines above leaves every moved line's anchor unchanged at N+3 [bash -c, notty]" { check_anchors_insert c; }
@test "SC-7 anchor mode: inserting 3 lines above leaves every moved line's anchor unchanged at N+3 [bash -lc, notty]" { check_anchors_insert lc; }
@test "SC-7 anchor mode: changing one line's content changes that line's anchor only [bash -c, notty]" { check_anchors_change c; }
@test "SC-7 anchor mode: changing one line's content changes that line's anchor only [bash -lc, notty]" { check_anchors_change lc; }
@test "SC-7 anchor mode: text lines are number, marker, anchor, text, and the long-lines command keeps --anchors [bash -c, notty]" { check_anchors_text c; }
@test "SC-7 anchor mode: text lines are number, marker, anchor, text, and the long-lines command keeps --anchors [bash -lc, notty]" { check_anchors_text lc; }
@test "SC-7 anchor mode: next and more keep --anchors, and the next window shows its lines' anchors [bash -c, notty]" { check_anchors_continue c; }
@test "SC-7 anchor mode: next and more keep --anchors, and the next window shows its lines' anchors [bash -lc, notty]" { check_anchors_continue lc; }
@test "SC-7 anchor mode on a directory is a usage error (exit 2) [bash -c, notty]" { check_anchors_directory c; }
@test "SC-7 anchor mode on a directory is a usage error (exit 2) [bash -lc, notty]" { check_anchors_directory lc; }
