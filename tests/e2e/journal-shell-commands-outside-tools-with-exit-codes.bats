#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# SC-2 — "Shell commands run outside timelike tools in the same session appear in the journal with their
# exit codes". (Feature 009, slice 1; spec FR-7, FR-8, FR-9, Scenario 3; tasks.md T004;
# contracts/journal-cli.md § JSON, § Text entries; research R1, R3, R7.)
#
# Written from the contract before the tool existed. Every expected value is the test's own (P004). In
# one session of its own, one `docker exec` each, in this order:
#   1. view A      a timelike tool                          (cell style)
#   2. exit 7      a shell command, exit 7                  (cell style)
#   3. false       a shell command, exit 1                  (cell style)
#   4. view B      a timelike tool                          (cell style)
#   5. true        a shell command, exit 0, in the OTHER style (bash -lc in the bash -c cell, and back)
#   6. ls MISSING  a shell command, exit 2 (GNU ls: a missing operand)   (cell style)
#   7. view C      a timelike tool                          (cell style)
# The test checks each exit status it saw against these. Then `journal --all --json` (read before its
# own entry exists) must hold exactly seven entries, in this order:
#   - the shell commands as kind `shell`, `command` the exact command line the shell ran, `exit` the
#     status the test saw, `style` the style it was run under;
#   - the tools as one entry each (FR-9: the shell's first word names the tool, so the shell line is
#     folded into the tool's), `style` the shell's, the argv as made, `exit` 0;
#   - every start/end inside the runner-side window measured around that command (100 ms slack).
# `journal --all --text` shows the same seven lines, kind, style, command and `exit N`, in order.
#
# Fixtures are made by running real shells and tools in the container (P005); no record is written by
# the test. Shell entries are written by the image's hook (/etc/timelike/shell-env.bash's EXIT trap), so
# this file needs the image: a host stand-in without the hook has no shell entries, and fails here.
# Isolation: each cell has its own fixture directory and its own TIMELIKE_SESSION
# (`j2-<run id>-<check>-<style>`), checked to have no records before the cell starts; the run id is the
# random suffix of this file's container_tmpdir. teardown_file removes this run's session directories
# (by that prefix) and nothing else.
# Cells: bash -c and bash -lc, `notty`.

load helpers

# This file's session prefix (sessions are `<prefix>-<run id>-<check>-<style>`).
JPREFIX=j2

setup_file() {
  stamp_check
  JDIR="$(container_tmpdir journal-sc2)"
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
SLACK_MS=100

# ── checks ────────────────────────────────────────────────────────────────────────────────────

# shell_timed STYLE CMD — CMD exactly as given (no redirection added, so the shell's recorded command
# line is CMD), in this cell's session, with its runner-side window appended to T_BEFORE / T_AFTER.
shell_timed() {
  local b
  b="$(now_ms)"
  run_in -e "TIMELIKE_SESSION=${SESSION}" "$1" notty "$2"
  assert_within 20
  T_BEFORE+=("$b")
  T_AFTER+=("$(now_ms)")
}

# wl FIELD... — FIELDs joined by tabs.
wl() {
  local IFS=$'\t'
  printf '%s' "$*"
}

# make_session STYLE OTHER — the seven commands above, in a fresh cell. Sets WANT (one line per
# expected entry: kind, style, exit, command in ENTRIES_PY's form), T_BEFORE and T_AFTER.
make_session() {
  local st ot missing
  st="$(style_label "$1")"
  ot="$(style_label "$2")"
  missing="/nonexistent-${SESSION}"
  exec_plain sh -c 'for f in a b c; do printf "%s\n" "$f" >"$1/$f.txt"; done' put "$CELL"
  T_BEFORE=()
  T_AFTER=()

  timed "$1" "view ${CELL}/a.txt >/dev/null"
  expect_status 0
  shell_timed "$1" 'exit 7'
  expect_status 7
  shell_timed "$1" 'false'
  expect_status 1
  timed "$1" "view ${CELL}/b.txt >/dev/null"
  expect_status 0
  shell_timed "$2" 'true'
  expect_status 0
  shell_timed "$1" "ls ${missing}"
  expect_status 2
  timed "$1" "view ${CELL}/c.txt >/dev/null"
  expect_status 0

  WANT=(
    "$(wl tool "$st" 0 "[\"view\", \"${CELL}/a.txt\"]")"
    "$(wl shell "$st" 7 'exit 7')"
    "$(wl shell "$st" 1 'false')"
    "$(wl tool "$st" 0 "[\"view\", \"${CELL}/b.txt\"]")"
    "$(wl shell "$ot" 0 'true')"
    "$(wl shell "$st" 2 "ls ${missing}")"
    "$(wl tool "$st" 0 "[\"view\", \"${CELL}/c.txt\"]")"
  )
}

# check_sc2_json STYLE OTHER — `journal --all --json`: exactly the seven entries, in order, with kind,
# style, exit, command and a time inside the test's window.
check_sc2_json() {
  new_cell sc2-json "$1"
  make_session "$1" "$2"
  in_session "$1" "journal --all --json"
  expect_status 0
  jentries
  ((${#ENTRIES[@]} == 7)) || flunk "the session holds 7 commands (3 tools, 4 shell); the journal lists ${#ENTRIES[@]} entries"
  local kind style session exit cmd ref start end i
  for ((i = 0; i < 7; i++)); do
    IFS=$'\t' read -r kind style _ session exit cmd ref start end <<<"${ENTRIES[i]}"
    [[ "${kind}"$'\t'"${style}"$'\t'"${exit}"$'\t'"${cmd}" == "${WANT[i]}" ]] ||
      flunk "entry $((i + 1)): kind, style, exit, command '${kind} | ${style} | ${exit} | ${cmd}', want '${WANT[i]//$'\t'/ | }'"
    [[ "$session" == "$SESSION" ]] || flunk "entry $((i + 1)): session '${session}', want ${SESSION}"
    [[ "$ref" == '<none>' ]] || flunk "entry $((i + 1)): pointer '${ref}', want none (a shell command and a view have none)"
    [[ "$start" =~ ^[0-9]+$ && "$end" =~ ^[0-9]+$ ]] || flunk "entry $((i + 1)): start/end not ISO 8601 UTC with ms: ${start} / ${end}"
    ((start <= end)) || flunk "entry $((i + 1)): start ${start} after end ${end}"
    ((start >= T_BEFORE[i] - SLACK_MS && end <= T_AFTER[i] + SLACK_MS)) ||
      flunk "entry $((i + 1)) (${WANT[i]//$'\t'/ | }): ${start}..${end} ms lies outside the window the test measured around it, ${T_BEFORE[i]}..${T_AFTER[i]}"
  done
  jfields counts.shell
  expect_j counts.shell 4
}

# check_sc2_text STYLE OTHER — `journal --all --text`: the seven entry lines in order, each with its
# kind, its style, its command and `exit N`.
check_sc2_text() {
  new_cell sc2-text "$1"
  make_session "$1" "$2"
  in_session -e COLUMNS=1000 "$1" "journal --all --text"
  expect_status 0
  [[ "${lines[0]:-}" == "journal: ${SESSION} [all 7]" ]] || flunk "header line: ${lines[0]:-<none>}"
  [[ "${lines[1]:-}" == "verdict: 7 of 7 entries in session ${SESSION} ("* ]] || flunk "verdict line: ${lines[1]:-<none>}"
  local line kind style exit cmd i
  local -a el=()
  for line in "${lines[@]}"; do
    [[ "$line" =~ $ENTRY_LINE_RE ]] && el+=("$line")
  done
  ((${#el[@]} == 7)) || flunk "${#el[@]} entry lines, want 7"
  for ((i = 0; i < 7; i++)); do
    IFS=$'\t' read -r kind style exit cmd <<<"${WANT[i]}"
    if [[ "$kind" == tool ]]; then
      # the tool's line shows `view <path>`: check the word and the file name
      cmd="${cmd##*/}"
      cmd="${cmd%\"]}"
      [[ "${el[i]}" == *" view "*"/${cmd}"* ]] || flunk "line $((i + 1)) is not the view of ${cmd}: ${el[i]}"
    fi
    [[ "${el[i]}" =~ ^[0-9:.]+\ +${kind}\  ]] || flunk "line $((i + 1)) is not a ${kind} entry: ${el[i]}"
    [[ "${el[i]}" == *" ${style} "*"${cmd}"*" exit ${exit} "* ]] ||
      flunk "line $((i + 1)) lacks style '${style}', command '${cmd}' or 'exit ${exit}', in that order: ${el[i]}"
  done
}

@test "SC-2 [bash -c, notty] Shell commands run outside timelike tools in the same session appear in the journal with their exit codes — JSON: exit 7, false, bash -lc true, ls missing (2) as shell entries, in order among view entries" { check_sc2_json c lc; }
@test "SC-2 [bash -lc, notty] Shell commands run outside timelike tools in the same session appear in the journal with their exit codes — JSON: exit 7, false, bash -c true, ls missing (2) as shell entries, in order among view entries" { check_sc2_json lc c; }
@test "SC-2 [bash -c, notty] Shell commands run outside timelike tools in the same session appear in the journal with their exit codes — text: seven lines in order, kind, style, command and exit N" { check_sc2_text c lc; }
@test "SC-2 [bash -lc, notty] Shell commands run outside timelike tools in the same session appear in the journal with their exit codes — text: seven lines in order, kind, style, command and exit N" { check_sc2_text lc c; }
