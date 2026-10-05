#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# SC-1 — "The journal lists, in order, every timelike tool invocation of a session with time, tool,
# arguments, exit and a pointer to its log or snapshot". (Feature 009, slice 1; spec FR-1, FR-3, FR-5,
# FR-6, Scenario 2; tasks.md T004; contracts/journal-cli.md § JSON, § Text entries; research R2, R3, R7.)
#
# Written from the contract before the tool existed. Every expected value is the test's own (P004):
#   - in one session of its own, the test runs `snapshot`, `run -- sh -c 'exit 3'`, `view`, `edit` and
#     `undo --dry-run`, one `docker exec` each, in that order, and keeps what each printed (the snapshot
#     id, run's log path, undo's snapshot id) and its exit status;
#   - `journal --all --json` must list exactly those five tool invocations (entries of kind other than
#     `shell`: under the image's hook each `cd … && tool` shell is a shell entry with the tool nested
#     under it, research R3), in the order made, each with:
#       time      `start`/`end` ISO 8601 UTC with milliseconds, inside the runner-side window the test
#                 measured around that invocation (100 ms slack for rounding);
#       tool and  the entry's `command`, split as a shell would split it, equals the argv the test
#       arguments passed (so the check does not depend on the tool's quoting style);
#       exit      the status the test saw (`run` exits 3, the wrapped command's);
#       pointer   `run`: `ref.log` equals the log path run printed, and that path is a file in the
#                 container (`test -f`); `snapshot`: `ref.snapshot` equals the id it printed; `undo`:
#                 `ref.snapshot` equals the id its dry run named; `view`, `edit`: no pointer (null);
#   - `journal --all --text` shows the same pointers in the text form (`log <path>`, `snapshot <id>`,
#     `—`), with `COLUMNS` wide enough that no line is cut.
#
# Fixtures are made by running the real tools in the container (P005); no record is written by the test.
# Isolation: each cell has its own fixture directory and its own TIMELIKE_SESSION
# (`j1-<run id>-<check>-<style>`), checked to have no records before the cell starts; the run id is the
# random suffix of this file's container_tmpdir, so a rerun never reads an earlier run's records.
# teardown_file removes this run's session directories (by that prefix) and nothing else.
# Cells: bash -c and bash -lc, `notty`.

load helpers

# This file's session prefix (sessions are `<prefix>-<run id>-<check>-<style>`).
JPREFIX=j1

setup_file() {
  stamp_check
  JDIR="$(container_tmpdir journal-sc1)"
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

# A text entry line of kind `tool`: the time, then the kind (child lines are indented after the time).
TOOL_LINE_RE='^[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3} +tool '
SLACK_MS=100

# ── checks ────────────────────────────────────────────────────────────────────────────────────

# check_sc1_json STYLE — five tool invocations, then `journal --all --json`: exactly those five tool
# entries, in order, with time, tool, arguments, exit and pointer as the test observed them.
check_sc1_json() {
  new_cell sc1-json "$1"
  exec_plain mkdir "${CELL}/ws"
  put "${CELL}/ws/f.py" 'alpha = 1\nbeta = 2\n'
  T_BEFORE=()
  T_AFTER=()
  local ws="cd '${CELL}/ws' &&"

  timed "$1" "${ws} snapshot --json"
  expect_status 0
  jfields id
  local snap_id run_log undo_id
  snap_id="$(jval id)"
  [[ "$snap_id" =~ ^[A-Za-z0-9._-]+$ ]] || flunk "snapshot printed no id: '${snap_id}'"

  timed "$1" "${ws} run --json -- sh -c 'exit 3'"
  expect_status 3
  jfields log
  run_log="$(jval log)"
  [[ "$run_log" == /?* ]] || flunk "run printed no log path: '${run_log}'"

  timed "$1" "${ws} view f.py --json"
  expect_status 0
  timed "$1" "${ws} edit f.py --old 'beta = 2' --new 'beta = 3' --json"
  expect_status 0
  timed "$1" "${ws} undo --dry-run --json"
  expect_status 0
  jfields id
  undo_id="$(jval id)"
  [[ "$undo_id" == "$snap_id" ]] || flunk "undo --dry-run planned snapshot '${undo_id}', the test took '${snap_id}'"
  exec_plain test -f "$run_log" || flunk "run's log ${run_log} is not a file in the container"

  local -a want_argv=(
    '["snapshot", "--json"]'
    '["run", "--json", "--", "sh", "-c", "exit 3"]'
    '["view", "f.py", "--json"]'
    '["edit", "f.py", "--old", "beta = 2", "--new", "beta = 3", "--json"]'
    '["undo", "--dry-run", "--json"]'
  )
  local -a want_exit=(0 3 0 0 0)
  local -a want_ref=("snapshot=${snap_id}" "log=${run_log}" '<none>' '<none>' "snapshot=${undo_id}")

  in_session "$1" "journal --all --json"
  expect_status 0
  jentries
  local e kind session exit cmd ref start end i
  local -a tools=()
  for e in "${ENTRIES[@]}"; do
    [[ "${e%%$'\t'*}" == shell ]] || tools+=("$e")
  done
  ((${#tools[@]} == 5)) || flunk "the session holds 5 tool invocations; the journal lists ${#tools[@]} non-shell entries"
  for ((i = 0; i < 5; i++)); do
    IFS=$'\t' read -r kind _ _ session exit cmd ref start end <<<"${tools[i]}"
    [[ "$kind" == tool ]] || flunk "entry $((i + 1)): kind '${kind}', want tool"
    [[ "$cmd" == "${want_argv[i]}" ]] || flunk "entry $((i + 1)): tool and arguments ${cmd}, want ${want_argv[i]} (in the order made)"
    [[ "$exit" == "${want_exit[i]}" ]] || flunk "entry $((i + 1)) (${want_argv[i]}): exit '${exit}', want ${want_exit[i]}"
    [[ "$ref" == "${want_ref[i]}" ]] || flunk "entry $((i + 1)) (${want_argv[i]}): pointer '${ref}', want '${want_ref[i]}'"
    [[ "$session" == "$SESSION" ]] || flunk "entry $((i + 1)): session '${session}', want ${SESSION}"
    [[ "$start" =~ ^[0-9]+$ && "$end" =~ ^[0-9]+$ ]] || flunk "entry $((i + 1)): start/end not ISO 8601 UTC with ms: ${start} / ${end}"
    ((start <= end)) || flunk "entry $((i + 1)): start ${start} after end ${end}"
    ((start >= T_BEFORE[i] - SLACK_MS && end <= T_AFTER[i] + SLACK_MS)) ||
      flunk "entry $((i + 1)) (${want_argv[i]}): ${start}..${end} ms lies outside the window the test measured around it, ${T_BEFORE[i]}..${T_AFTER[i]}"
  done
}

# check_sc1_text STYLE — the same invocations, `journal --all --text`: the header, the verdict, and the
# five tool lines in order, each with its tool, its exit and its pointer (`snapshot <id>`, `log <path>`,
# `—`).
check_sc1_text() {
  new_cell sc1-text "$1"
  exec_plain mkdir "${CELL}/ws"
  put "${CELL}/ws/f.py" 'alpha = 1\nbeta = 2\n'
  local ws="cd '${CELL}/ws' &&" snap_id run_log undo_id

  in_session "$1" "${ws} snapshot --json"
  expect_status 0
  jfields id
  snap_id="$(jval id)"
  in_session "$1" "${ws} run --json -- sh -c 'exit 3'"
  expect_status 3
  jfields log
  run_log="$(jval log)"
  in_session "$1" "${ws} view f.py --json"
  expect_status 0
  in_session "$1" "${ws} edit f.py --old 'beta = 2' --new 'beta = 3' --json"
  expect_status 0
  in_session "$1" "${ws} undo --dry-run --json"
  expect_status 0
  jfields id
  undo_id="$(jval id)"
  [[ -n "$snap_id" && "$undo_id" == "$snap_id" && "$run_log" == /?* ]] || flunk "fixture: snapshot '${snap_id}', undo '${undo_id}', log '${run_log}'"

  in_session -e COLUMNS=1000 "$1" "journal --all --text"
  expect_status 0
  [[ "${lines[0]:-}" =~ ^journal:\ ${SESSION}\ \[all\ ([0-9]+)\]$ ]] || flunk "header line: ${lines[0]:-<none>}"
  local total="${BASH_REMATCH[1]}"
  [[ "${lines[1]:-}" == "verdict: ${total} of ${total} entries in session ${SESSION} ("* ]] || flunk "verdict line: ${lines[1]:-<none>}"

  local line
  local -a tl=()
  for line in "${lines[@]}"; do
    line="${line%"${line##*[![:space:]]}"}"
    [[ "$line" =~ $TOOL_LINE_RE ]] && tl+=("$line")
  done
  ((${#tl[@]} >= 5)) || flunk "${#tl[@]} tool lines, want at least the 5 invocations"
  local -a want_tool=(snapshot run view edit undo)
  local -a want_exit=(0 3 0 0 0)
  local -a want_ptr=("snapshot ${snap_id}" "log ${run_log}" "—" "—" "snapshot ${undo_id}")
  local i
  for ((i = 0; i < 5; i++)); do
    [[ "${tl[i]}" =~ \ ${want_tool[i]}\  ]] || flunk "tool line $((i + 1)) is not ${want_tool[i]}'s: ${tl[i]}"
    [[ "${tl[i]}" == *" exit ${want_exit[i]} "* ]] || flunk "tool line $((i + 1)) lacks 'exit ${want_exit[i]}': ${tl[i]}"
    [[ "${tl[i]}" == *" ${want_ptr[i]}" ]] || flunk "tool line $((i + 1)) does not end with its pointer '${want_ptr[i]}': ${tl[i]}"
  done
}

@test "SC-1 [bash -c, notty] The journal lists, in order, every timelike tool invocation of a session with time, tool, arguments, exit and a pointer to its log or snapshot — JSON: snapshot, run, view, edit, undo --dry-run as made; run's log is a file, snapshot's id as printed" { check_sc1_json c; }
@test "SC-1 [bash -lc, notty] The journal lists, in order, every timelike tool invocation of a session with time, tool, arguments, exit and a pointer to its log or snapshot — JSON: snapshot, run, view, edit, undo --dry-run as made; run's log is a file, snapshot's id as printed" { check_sc1_json lc; }
@test "SC-1 [bash -c, notty] The journal lists, in order, every timelike tool invocation of a session with time, tool, arguments, exit and a pointer to its log or snapshot — text: header, verdict, the five tool lines in order with exit and pointer" { check_sc1_text c; }
@test "SC-1 [bash -lc, notty] The journal lists, in order, every timelike tool invocation of a session with time, tool, arguments, exit and a pointer to its log or snapshot — text: header, verdict, the five tool lines in order with exit and pointer" { check_sc1_text lc; }
