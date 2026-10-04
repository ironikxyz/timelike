#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# SC-3 — "A search with 262 matches shows 50, grouped by file, with a footer stating the 212 omitted and
# a concrete way to narrow". (Feature 006, slice 0; spec FR-12, FR-14, FR-15, FR-16, FR-17, FR-22, D-3,
# D-5; tasks.md T005; contracts/view-search-cli.md § search; data-model.md § Order, § Narrowing.)
#
# Written from the contract before the tool existed (tasks.md Phase 2). The oracle is git's own reading
# of the ignore rules, never the tool's (P004): `git ls-files -co --exclude-standard` (tracked and
# untracked, not ignored), sorted in byte order (LC_ALL=C), each file's hits by `grep -Hn`, which is
# exactly the saved list's `path:line:text` form in display order. From it the test computes the total
# (262), the files matched, the first 50, the bytes of hits 51-262, and the narrowing by
# data-model.md's rule (the directory or file below the root with the most hits but not all of them,
# shallowest on ties), and checks that the fixture leaves no tie for that rule to break.
#
# The repository is built by git (fixtures/bounded-read.sh, P005): 262 hits outside the ignored paths,
# 30 more in build/ and app.log (ignored), 9 inside .git (never searched), afresh per test.
# Cells: bash -c and bash -lc, `notty`.

load helpers

FIXTURE=/tmp/bounded-read-sc3.sh

setup_file() {
  stamp_check
  copy_into_container "${BATS_TEST_DIRNAME}/fixtures/bounded-read.sh" "$FIXTURE" 0755
}

setup() {
  WORK="$(container_tmpdir sc3search)"
  FX="${WORK}/fx"
  REPO="${FX}/repo"
  SCRATCH="${WORK}/scratch"
  ORACLE="${WORK}/oracle.txt"
  exec_plain sh "$FIXTURE" "$FX" >/dev/null
  oracle
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

# json_lines — the JSON `lines` array, one per line, into $JPY.
json_lines() {
  jpy "print('\n'.join(g('lines', [])))"
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

# ── the oracle ───────────────────────────────────────────────────────────────────────────────

# oracle — write every hit git's ignore rules leave, in display order, to $ORACLE (outside the
# repository), and set the figures the checks compare against.
oracle() {
  exec_plain sh -c 'cd "$1" && git ls-files -co --exclude-standard | LC_ALL=C sort | while IFS= read -r f; do
    grep -Hn needle_fn "$f" || true
  done >"$2"' oracle "$REPO" "$ORACLE"
  TOTAL="$(exec_plain sh -c 'wc -l <"$1"' n "$ORACLE")"
  [[ "$TOTAL" == 262 ]] || { echo "oracle finds ${TOTAL} hits, want 262: the fixture drifted" >&2; return 1; }
  OMITTED=$((TOTAL - 50))
  NFILES="$(exec_plain sh -c 'cut -d: -f1 "$1" | sort -u | wc -l' n "$ORACLE")"
  NSEARCHED="$(exec_plain sh -c 'cd "$1" && git ls-files -co --exclude-standard | wc -l' n "$REPO")"
  FIRST50="$(exec_plain head -n 50 "$ORACLE")"
  REST="$(exec_plain sed -n "51,${TOTAL}p" "$ORACLE")"
  REST_BYTES="$(exec_plain sh -c 'sed -n "51,$2p" "$1" | wc -c' n "$ORACLE" "$TOTAL")"
  # The narrowing, by data-model.md's rule, from the oracle: "<path> <hits> <ties>".
  local narrow
  narrow="$(exec_plain awk -F: -v total="$TOTAL" '
    { n = split($1, part, "/"); acc = ""
      for (i = 1; i <= n; i++) { acc = (i == 1 ? part[1] : acc "/" part[i]); c[acc]++; depth[acc] = i } }
    END {
      best = ""
      for (k in c) if (c[k] < total && (best == "" || c[k] > c[best] || (c[k] == c[best] && depth[k] < depth[best]))) best = k
      ties = 0
      for (k in c) if (c[k] == c[best] && depth[k] == depth[best]) ties++
      print best, c[best], ties
    }' "$ORACLE")"
  read -r NPATH NCOUNT NTIES <<<"$narrow"
  [[ "$NTIES" == 1 ]] || { echo "the fixture leaves a tie for the narrowing (${narrow}); the rule does not break it" >&2; return 1; }
  ((NCOUNT < TOTAL)) || { echo "narrowing ${narrow} is not smaller than ${TOTAL}" >&2; return 1; }
}

# file_hits PATH — hits the oracle has in PATH.
file_hits() {
  exec_plain awk -F: -v p="$1" '$1 == p { n++ } END { print n + 0 }' "$ORACLE"
}

# ignored_state — the repository's status, ignored files included: FR-22, nothing is written there.
ignored_state() {
  exec_plain sh -c 'cd "$1" && git status --porcelain --ignored --untracked-files=all' st "$REPO"
}

# ── checks ────────────────────────────────────────────────────────────────────────────────────

# check_cap_text STYLE — `search needle_fn --text` from the repository root: the verdict states 262 in
# the oracle's file count, 50 shown and 212 omitted; the body is sections of hits that, read back as
# path:line:text, are exactly the oracle's first 50, each label carrying the file's own hit count (and
# `<shown> of <in file>` where the cut falls); `narrow:` is the last body line and names the oracle's
# narrowing; the closing lines give `sed -n 51,262p` over a saved list in the session scratch (never in
# the repository), and the omission line's bytes are the oracle's for hits 51-262. The saved list is
# the oracle: every hit, no ignored path, nothing from .git.
check_cap_text() {
  local before after
  before="$(ignored_state)"

  in_dir "$1" "$REPO" "search needle_fn --text"
  expect_status 0
  # The scope is shlex.quote(pattern): needle_fn needs no quoting.
  [[ "${lines[0]:-}" == "search: . [needle_fn]" ]] || flunk "header line: ${lines[0]:-<none>}"
  local want="verdict: ${TOTAL} matches in ${NFILES} files; 50 shown, ${OMITTED} omitted (searched ${NSEARCHED} files"
  local after_want="${lines[1]#"$want"}"
  [[ "${lines[1]:-}" == "$want"* && ( "$after_want" == ";"* || "$after_want" == ")"* ) ]] \
    || flunk "verdict line: ${lines[1]:-<none>} (want it to start '${want}' then ; or ))"

  local i path="" label_shown=0 label_in=0 in_section=0 shown=() seen=" "
  for ((i = 2; i < ${#lines[@]}; i++)); do
    local line="${lines[i]}"
    if [[ "$line" =~ ^──\ (.+)\ \(([0-9]+)(\ of\ ([0-9]+))?\)\ ──$ ]]; then
      ((in_section == label_shown)) || flunk "section ${path} shows ${in_section} hits, its label says ${label_shown}"
      path="${BASH_REMATCH[1]}"
      label_shown="${BASH_REMATCH[2]}"
      label_in="${BASH_REMATCH[4]:-${BASH_REMATCH[2]}}"
      if [[ -n "${BASH_REMATCH[3]}" ]]; then
        ((label_shown < label_in)) || flunk "label '${line}': '<shown> of <in file>' with nothing cut"
      fi
      [[ "$seen" != *" ${path} "* ]] || flunk "file ${path} has two sections: not grouped by file"
      seen+="${path} "
      [[ "$label_in" == "$(file_hits "$path")" ]] || flunk "label '${line}': the file has $(file_hits "$path") hits"
      in_section=0
    elif [[ "$line" =~ ^([0-9]+):\ (.*)$ ]]; then
      [[ -n "$path" ]] || flunk "hit line before any section label: ${line}"
      shown+=("${path}:${BASH_REMATCH[1]}:${BASH_REMATCH[2]}")
      in_section=$((in_section + 1))
    elif [[ "$line" == "narrow: "* ]]; then
      break
    else
      flunk "unexpected body line: ${line}"
    fi
  done
  ((in_section == label_shown)) || flunk "section ${path} shows ${in_section} hits, its label says ${label_shown}"
  [[ ${#shown[@]} -eq 50 ]] || flunk "${#shown[@]} hits shown, want 50"
  same_text "shown hits, in display order (files by path, hits by line)" "$FIRST50" "$(printf '%s\n' "${shown[@]}")"

  # footer: narrow:, then the closing lines, and nothing else
  local n=${#lines[@]}
  ((i == n - 5)) || flunk "narrow: is at line $((i + 1)) of ${n}; it must be the last body line, before the 4 closing lines"
  [[ "${lines[i]}" == "narrow: search needle_fn ${NPATH}  (${NCOUNT} of the ${TOTAL})" ]] \
    || flunk "narrow line: ${lines[i]} (want 'narrow: search needle_fn ${NPATH}  (${NCOUNT} of the ${TOTAL})')"
  [[ "${lines[i + 1]}" =~ ^more:\ sed\ -n\ 51,${TOTAL}p\ (.+)$ ]] || flunk "more line: ${lines[i + 1]}"
  local list="${BASH_REMATCH[1]}"
  [[ "$list" == "${SCRATCH}/"* ]] || flunk "the saved hit list ${list} is not in the session scratch ${SCRATCH}"
  [[ "$list" != "${REPO}/"* ]] || flunk "the saved hit list is in the repository"
  [[ "${lines[i + 2]}" == "exit: 0" ]] || flunk "exit line: ${lines[i + 2]}"
  [[ "${lines[i + 3]}" == "full output: ${list}" ]] || flunk "full output line: ${lines[i + 3]}"
  [[ "${lines[i + 4]}" == "… omitted ${OMITTED} lines (${REST_BYTES} bytes) — full output: ${list}; more: sed -n 51,${TOTAL}p ${list}" ]] \
    || flunk "omission line: ${lines[i + 4]} (want ${OMITTED} lines, ${REST_BYTES} bytes)"

  assert_no_line_matching '(^|[ /])(\.git/|build/|app\.log)' || flunk "an ignored path or .git appears in the output"
  same_text "the saved hit list" "$(exec_plain cat "$ORACLE")" "$(exec_plain cat "$list")"

  after="$(ignored_state)"
  [[ "$before" == "$after" ]] || flunk "the repository changed: before:
${before}
after:
${after}"
}

# cap_footer STYLE — run the capped search in text and set MORE and NARROW to the commands printed.
cap_footer() {
  in_dir "$1" "$REPO" "search needle_fn --text"
  expect_status 0
  MORE=""
  NARROW=""
  local line
  for line in "${lines[@]}"; do
    [[ "$line" == "narrow: "* ]] && NARROW="${line#narrow: }" && NARROW="${NARROW%%  (*}"
    [[ "$line" == "more: "* ]] && MORE="${line#more: }"
  done
  [[ -n "$MORE" && -n "$NARROW" ]] || flunk "no more: or narrow: line"
}

# check_more_runs STYLE — the `more:` command, pasted as printed, prints exactly the 212 omitted hits:
# the oracle's hits 51-262.
check_more_runs() {
  cap_footer "$1"
  [[ "$MORE" == "sed -n 51,${TOTAL}p "* ]] || flunk "more command: ${MORE}"
  in_dir "$1" "$REPO" "$MORE"
  expect_status 0
  [[ ${#lines[@]} -eq $OMITTED ]] || flunk "'${MORE}' printed ${#lines[@]} lines, want ${OMITTED}"
  same_text "the omitted hits printed by more:" "$REST" "$output"
}

# check_narrow_runs STYLE — the `narrow:` command, pasted as printed, returns fewer matches than 262:
# exactly the oracle's count for the path it names.
check_narrow_runs() {
  cap_footer "$1"
  [[ "$NARROW" == "search needle_fn ${NPATH}" ]] || flunk "narrow command: ${NARROW}"
  in_dir "$1" "$REPO" "$NARROW"
  expect_status 0
  jfields count
  expect_j count "$NCOUNT"
  (($(jval count) < TOTAL)) || flunk "the narrowing returned $(jval count) matches, not fewer than ${TOTAL}"
}

# check_cap_json STYLE — JSON (the default under the pipe): count 262, shown 50, truncated's figures,
# `lines` the 50 hit lines (`line: text`, in display order) plus the `narrow:` line, `narrow` naming the
# command, and no `cut_lines` (no hit line is longer than COLUMNS).
check_cap_json() {
  in_dir "$1" "$REPO" "search needle_fn"
  expect_status 0
  jfields tool exit count shown files_matched files_searched truncated.omitted_lines truncated.omitted_bytes \
    truncated.full_output truncated.more narrow cut_lines
  expect_j tool search
  expect_j exit 0
  expect_j count "$TOTAL"
  expect_j shown 50
  expect_j files_matched "$NFILES"
  expect_j files_searched "$NSEARCHED"
  expect_j truncated.omitted_lines "$OMITTED"
  expect_j truncated.omitted_bytes "$REST_BYTES"
  expect_j truncated.more "sed -n 51,${TOTAL}p $(jval truncated.full_output)"
  expect_j cut_lines "<absent>"
  # `narrow` is "the narrowing command"; whether it carries the share "(N of the T)" is not fixed.
  [[ "$(jval narrow)" == "search needle_fn ${NPATH}" || "$(jval narrow)" == "search needle_fn ${NPATH}  (${NCOUNT} of the ${TOTAL})" ]] \
    || flunk "narrow: $(jval narrow)"

  jpy "L = g('lines', [])
print('n=%d' % len(L))
print('last=' + (L[-1] if L else '<absent>'))
print('hits=' + json.dumps(L[:50]))"
  expect_j n 51
  expect_j last "narrow: search needle_fn ${NPATH}  (${NCOUNT} of the ${TOTAL})"
  local want
  want="$(cut -d: -f2- <<<"$FIRST50" | sed 's/:/: /' | pyq 'import json,sys; print(json.dumps(sys.stdin.read().splitlines()))')"
  expect_j hits "$want"
}

# check_no_ignore STYLE — `--no-ignore` searches the ignored paths too (262 + 30, plain grep's count
# outside .git) and still never enters .git: the saved list names build/ and app.log, never .git/.
check_no_ignore() {
  local all
  all="$(exec_plain sh -c 'cd "$1" && grep -r --exclude-dir=.git -o needle_fn . | wc -l' n "$REPO")"
  [[ "$all" == 292 ]] || { echo "fixture has ${all} hits outside .git, want 292" >&2; return 1; }

  in_dir "$1" "$REPO" "search needle_fn --no-ignore"
  expect_status 0
  jfields count truncated.full_output
  expect_j count "$all"
  local list
  list="$(exec_plain cat "$(jval truncated.full_output)")" || flunk "cannot read the saved hit list"
  [[ "$(grep -c '^build/out\.txt:' <<<"$list")" == 25 ]] || flunk "the saved list lacks build/out.txt's 25 hits"
  [[ "$(grep -c '^app\.log:' <<<"$list")" == 5 ]] || flunk "the saved list lacks app.log's 5 hits"
  ! grep -q '^\.git/\|/\.git/' <<<"$list" || flunk "the saved list carries a hit from inside .git"
}

@test "SC-3 a search with 262 matches shows 50, grouped by file, with a footer stating the 212 omitted and a concrete way to narrow [bash -c, notty]" { check_cap_text c; }
@test "SC-3 a search with 262 matches shows 50, grouped by file, with a footer stating the 212 omitted and a concrete way to narrow [bash -lc, notty]" { check_cap_text lc; }
@test "SC-3 a search with 262 matches: the more command prints exactly the 212 omitted hits [bash -c, notty]" { check_more_runs c; }
@test "SC-3 a search with 262 matches: the more command prints exactly the 212 omitted hits [bash -lc, notty]" { check_more_runs lc; }
@test "SC-3 a search with 262 matches: the narrowing command, when run, returns fewer matches [bash -c, notty]" { check_narrow_runs c; }
@test "SC-3 a search with 262 matches: the narrowing command, when run, returns fewer matches [bash -lc, notty]" { check_narrow_runs lc; }
@test "SC-3 a search with 262 matches: JSON count 262, shown 50, truncated.omitted_lines 212, the 50 hit lines and the narrow line [bash -c, notty]" { check_cap_json c; }
@test "SC-3 a search with 262 matches: JSON count 262, shown 50, truncated.omitted_lines 212, the 50 hit lines and the narrow line [bash -lc, notty]" { check_cap_json lc; }
@test "SC-3 matches in an ignored directory are not counted; with --no-ignore they are, and .git is still never searched [bash -c, notty]" { check_no_ignore c; }
@test "SC-3 matches in an ignored directory are not counted; with --no-ignore they are, and .git is still never searched [bash -lc, notty]" { check_no_ignore lc; }
