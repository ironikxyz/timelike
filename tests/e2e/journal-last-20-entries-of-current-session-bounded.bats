#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# SC-3 — "One command prints the last 20 journal entries of the current session in the bounded output
# format". (Feature 009, slice 1; spec FR-2, FR-4, FR-5, Scenario 1; tasks.md T004;
# contracts/journal-cli.md § Target, scope, verdict, § Text entries (the cut), § JSON; 001's
# output-contract.md § Body and truncation; research R3, R7.)
#
# Written from the contract before the tool existed. Every expected value is the test's own (P004):
#   - in one session of its own, the test makes 30 invocations, `view <cell>/f01.txt` … `view f30.txt`,
#     one `docker exec` each, in that order (the spec's figure; each is one entry: the shell's first word
#     is the tool, so its line is folded into the tool's, FR-9);
#   - `journal --json`, no argument but the format, in that session (TIMELIKE_SESSION: "the current
#     session"): the header (`tool` journal, `target` the session, `scope` `last 20 of 30`), `total` 30,
#     `shown` 20, and `entries` exactly views f11 … f30, oldest first, start times non-decreasing; the
#     cut (rule 3): `truncated.more` is `journal --all`, `omitted_lines` 10 (the cut counts entries),
#     `omitted_bytes` > 0, `full_output` a file in this session's scratch;
#   - `journal --text` next, in the same session, which now also holds the first journal call (31
#     entries): the header `journal: S [last 20 of 31]`, the verdict `20 of 31 entries in session S (`,
#     exactly 20 entry lines (f12 … f30, then the journal call), none of f01 … f11, and the `more:`
#     naming `journal --all`;
#   - the `more` command itself, `journal --all --json`: no cut; its first 30 entries are f01 … f30 in
#     order, every later one is a journal call, and the first call's 20 entries are its entries 11 to 30,
#     field for field (kind, style, agent, session, exit, command, pointer, start, end).
#
# Fixtures are made by running the real tool in the container (P005); no record is written by the test.
# Isolation: each cell has its own fixture directory and its own TIMELIKE_SESSION
# (`j3-<run id>-<check>-<style>`), checked to have no records before the cell starts; the run id is the
# random suffix of this file's container_tmpdir. teardown_file removes this run's session directories
# (by that prefix) and nothing else.
# Cells: bash -c and bash -lc, `notty`.

load helpers

# This file's session prefix (sessions are `<prefix>-<run id>-<check>-<style>`).
JPREFIX=j3

setup_file() {
  stamp_check
  JDIR="$(container_tmpdir journal-sc3)"
  RUN_ID="${JDIR##*.}"
  SROOT="$(scratch_root)"
  export JDIR RUN_ID SROOT
}

teardown_file() {
  container_rm "${JDIR:-}"
  rm_sessions "$JPREFIX"
}

# ── helpers (this file's own; the 009 files repeat them so each reads alone) ─────────────────────

# scratch_root — the container's session scratch root, read in the container, never assumed.
scratch_root() {
  local r
  r="$(exec_plain sh -c 'printf "%s" "${TIMELIKE_SCRATCH_ROOT:-/tmp/timelike}"')" || return 1
  [[ "$r" == /?* ]] || { echo "scratch root in the container: '${r}'" >&2; return 1; }
  printf '%s' "$r"
}

# rm_sessions PREFIX — remove this run's session directories (SROOT/PREFIX-RUN_ID-*) and nothing else.
rm_sessions() {
  [[ -n "${RUN_ID:-}" && "${SROOT:-}" == /tmp/?* ]] || return 0
  exec_plain sh -c 'for d in "$1/$2-$3-"*; do [ -d "$d" ] && rm -rf -- "$d"; done; exit 0' \
    rm "$SROOT" "$1" "$RUN_ID" >/dev/null 2>&1 || true
}

# new_cell NAME STYLE — this cell's fixture directory (CELL, with CELL.stderr beside it) and its own
# session (SESSION), which must have no records yet.
new_cell() {
  CELL="${JDIR}/$1-$2"
  SESSION="${JPREFIX}-${RUN_ID}-$1-$2"
  exec_plain mkdir "$CELL" || { echo "cell path ${CELL} exists: cells must not share a fixture" >&2; return 1; }
  if exec_plain test -e "${SROOT}/${SESSION}"; then
    echo "session ${SESSION} already has records: cells must not share a session" >&2
    return 1
  fi
}

# put PATH FORMAT — write FORMAT with the container's printf (P005). FORMAT carries no % directive.
put() {
  [[ "$2" != *%* ]] || { echo "put: FORMAT carries a %" >&2; return 1; }
  exec_plain sh -c 'printf "$2" >"$1"' put "$1" "$2"
}

# in_session [-e K=V]... STYLE CMD — run CMD as the agent would, in this cell's session; stderr goes to
# CELL.stderr so stdout stays one document.
in_session() {
  local -a envs=()
  while [[ "${1:-}" == -e ]]; do
    envs+=(-e "$2")
    shift 2
  done
  run_in -e "TIMELIKE_SESSION=${SESSION}" "${envs[@]}" "$1" notty "$2 2>>'${CELL}.stderr'"
  assert_within 20
}

# timed STYLE CMD — in_session, with the runner-side window around it appended to T_BEFORE / T_AFTER.
timed() {
  local b
  b="$(now_ms)"
  in_session "$1" "$2"
  T_BEFORE+=("$b")
  T_AFTER+=("$(now_ms)")
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

# ENTRIES_PY — one line per JSON entry, tab-separated:
#   kind style agent session exit command ref start_ms end_ms
# `command` is the shell's own command line for a shell entry, and for any other entry the JSON list of
# the words a shell would split it into (shlex), so tool and arguments compare exactly whatever quoting
# the tool chose. `ref` is `key=value` pairs, sorted. A time that is not ISO 8601 UTC with milliseconds
# prints as `bad:<value>`. An empty or null field prints as <none>.
ENTRIES_PY="$(
  cat <<'PY'
import datetime, re, shlex
ISO = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}(Z|\+00:00)$')
def ms(t):
    if not isinstance(t, str) or not ISO.match(t):
        return 'bad:' + repr(t)
    return str(round(datetime.datetime.fromisoformat(t.replace('Z', '+00:00')).timestamp() * 1000))
def ref(r):
    if isinstance(r, dict):
        return ' '.join('%s=%s' % (k, r[k]) for k in sorted(r))
    return r
def s(v):
    if v is None or v == '':
        return '<none>'
    v = v if isinstance(v, str) else json.dumps(v, sort_keys=True)
    return v.replace('\t', ' ').replace('\n', ' ')
for e in g('entries', []) or []:
    c = e.get('command')
    if e.get('kind') != 'shell' and isinstance(c, str):
        try:
            c = json.dumps(shlex.split(c))
        except ValueError:
            pass
    print('\t'.join(s(x) for x in (e.get('kind'), e.get('style'), e.get('agent'), e.get('session'),
                                   e.get('exit'), c, ref(e.get('ref')), ms(e.get('start')), ms(e.get('end')))))
PY
)"

# jentries — the last run's entries into ENTRIES (one line each, ENTRIES_PY's form).
jentries() {
  jpy "$ENTRIES_PY"
  ENTRIES=()
  [[ -z "$JPY" ]] || mapfile -t ENTRIES <<<"$JPY"
}


# An entry line in text: it starts with the time (date lines start with `──`).
ENTRY_LINE_RE='^[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3} '
N_MADE=30

# ── checks ────────────────────────────────────────────────────────────────────────────────────

# viewed N — the entry command (ENTRIES_PY's form) of the view of fNN.
viewed() {
  printf '["view", "%s/f%02d.txt"]' "$CELL" "$1"
}

# make_session STYLE — f01 … f30 in the cell, then 30 views of them, in order, in the cell's session.
make_session() {
  exec_plain sh -c 'i=1; while [ "$i" -le "$2" ]; do n=$(printf "%02d" "$i"); printf "line %s\n" "$n" >"$1/f$n.txt"; i=$((i + 1)); done' \
    put "$CELL" "$N_MADE"
  local i
  for ((i = 1; i <= N_MADE; i++)); do
    in_session "$1" "view $(printf '%s/f%02d.txt' "$CELL" "$i") >/dev/null"
    expect_status 0
  done
}

# check_sc3 STYLE — the tail in JSON, then in text, then the `more` command.
check_sc3() {
  new_cell sc3 "$1"
  make_session "$1"

  # 1. `journal --json`: the last 20 of 30, oldest first, with the cut.
  in_session "$1" "journal --json"
  expect_status 0
  jfields tool target scope session total shown truncated.more truncated.omitted_lines truncated.omitted_bytes truncated.full_output
  expect_j tool journal
  expect_j target "$SESSION"
  expect_j scope "last 20 of ${N_MADE}"
  expect_j session "$SESSION"
  expect_j total "$N_MADE"
  expect_j shown 20
  expect_j truncated.more "journal --all"
  expect_j truncated.omitted_lines $((N_MADE - 20))
  [[ "$(jval truncated.omitted_bytes)" =~ ^[1-9][0-9]*$ ]] || flunk "truncated.omitted_bytes: '$(jval truncated.omitted_bytes)', want a byte count > 0"
  local full
  full="$(jval truncated.full_output)"
  [[ "$full" == "${SROOT}/${SESSION}/"?* ]] || flunk "truncated.full_output '${full}' is not in this session's scratch ${SROOT}/${SESSION}/"
  jentries
  local -a tail=("${ENTRIES[@]}")
  ((${#tail[@]} == 20)) || flunk "${#tail[@]} entries shown, want 20"
  local kind cmd exit start prev=0 i
  for ((i = 0; i < 20; i++)); do
    IFS=$'\t' read -r kind _ _ _ exit cmd _ start _ <<<"${tail[i]}"
    [[ "$cmd" == "$(viewed $((N_MADE - 20 + 1 + i)))" ]] || flunk "entry $((i + 1)): ${cmd}, want $(viewed $((N_MADE - 20 + 1 + i))) (the last 20, oldest first)"
    [[ "$kind" == tool && "$exit" == 0 ]] || flunk "entry $((i + 1)): kind '${kind}', exit '${exit}', want tool, 0"
    [[ "$start" =~ ^[0-9]+$ ]] || flunk "entry $((i + 1)): start not ISO 8601 UTC with ms: ${start}"
    ((start >= prev)) || flunk "entry $((i + 1)) starts at ${start}, before the entry above it (${prev}): not oldest first"
    prev="$start"
  done
  exec_plain test -f "$full" || flunk "truncated.full_output ${full} is not a file in the container"

  # 2. `journal --text`: the session now also holds the first journal call.
  in_session -e COLUMNS=1000 "$1" "journal --text"
  expect_status 0
  local total=$((N_MADE + 1))
  [[ "${lines[0]:-}" == "journal: ${SESSION} [last 20 of ${total}]" ]] || flunk "header line: ${lines[0]:-<none>}"
  [[ "${lines[1]:-}" == "verdict: 20 of ${total} entries in session ${SESSION} ("* ]] || flunk "verdict line: ${lines[1]:-<none>}"
  local line more=0
  local -a el=()
  for line in "${lines[@]}"; do
    [[ "$line" =~ $ENTRY_LINE_RE ]] && el+=("$line")
    [[ "$line" == *"more: journal --all"* ]] && more=1
  done
  ((${#el[@]} == 20)) || flunk "${#el[@]} entry lines, want 20"
  for ((i = 0; i < 19; i++)); do
    [[ "${el[i]}" == *" view "*"$(printf '/f%02d.txt' $((total - 20 + 1 + i)))"* ]] ||
      flunk "entry line $((i + 1)) is not the view of $(printf 'f%02d' $((total - 20 + 1 + i))): ${el[i]}"
  done
  [[ "${el[19]}" == *" journal --json"* ]] || flunk "entry line 20 is not the first journal call: ${el[19]}"
  for ((i = 1; i <= total - 20; i++)); do
    [[ "$output" != *"$(printf '/f%02d.txt' "$i")"* ]] || flunk "$(printf 'f%02d' "$i") is shown, but it is not among the last 20"
  done
  ((more == 1)) || flunk "no 'more: journal --all' line: the cut does not name the command for the rest"

  # 3. The `more` command: the whole session, uncut.
  in_session "$1" "journal --all --json"
  expect_status 0
  jfields truncated
  expect_j truncated '<absent>'
  jentries
  ((${#ENTRIES[@]} >= N_MADE + 2)) || flunk "journal --all lists ${#ENTRIES[@]} entries, want the ${N_MADE} views and the 2 journal calls"
  for ((i = 0; i < N_MADE; i++)); do
    IFS=$'\t' read -r _ _ _ _ _ cmd _ _ _ <<<"${ENTRIES[i]}"
    [[ "$cmd" == "$(viewed $((i + 1)))" ]] || flunk "journal --all entry $((i + 1)): ${cmd}, want $(viewed $((i + 1)))"
  done
  for ((i = N_MADE; i < ${#ENTRIES[@]}; i++)); do
    IFS=$'\t' read -r _ _ _ _ _ cmd _ _ _ <<<"${ENTRIES[i]}"
    [[ "$cmd" == '["journal", '* ]] || flunk "journal --all entry $((i + 1)): ${cmd}, want only journal calls after the views"
  done
  for ((i = 0; i < 20; i++)); do
    [[ "${tail[i]}" == "${ENTRIES[N_MADE - 20 + i]}" ]] ||
      flunk "the tail's entry $((i + 1)) differs from journal --all's entry $((N_MADE - 20 + 1 + i)): '${tail[i]}' against '${ENTRIES[N_MADE - 20 + i]}'"
  done
}

@test "SC-3 [bash -c, notty] One command prints the last 20 journal entries of the current session in the bounded output format — 30 views: journal shows f11-f30 oldest first, cut with more: journal --all; text; the more command" { check_sc3 c; }
@test "SC-3 [bash -lc, notty] One command prints the last 20 journal entries of the current session in the bounded output format — 30 views: journal shows f11-f30 oldest first, cut with more: journal --all; text; the more command" { check_sc3 lc; }
