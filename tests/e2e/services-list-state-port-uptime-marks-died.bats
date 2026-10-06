#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# SC-5 — "Listing services shows each registered service's state, port and uptime, and marks ones whose
# process has died". (Feature 010, slice 1; spec FR-8, Scenario 5; tasks.md T002;
# contracts/services-cli.md § list; data-model § State; research R5, R8.)
#
# Written from the contract before the tool existed. Each cell registers three real services (P005):
#   - `up`:   `python3 -m http.server PORT`, started with `--port PORT` (ready, running);
#   - `bad`:  `sh -c 'echo boom >&2; exit 3'`, which dies before it is ready (start exits 1; the entry
#             stays, research R5);
#   - `gone`: `sleep 300` without a port (ready once alive), then killed by the TEST from outside, with
#             SIGKILL on every process carrying its marker, so its death is one `services` never saw.
# The test waits until at least 1.5 s have passed since `up` was ready, then lists. Checked:
#   - JSON: exactly the three names; `up` is `running` with `port` PORT, its pid, and `uptime_s` >= 1;
#     `bad` is `died` with `exit` 3; `gone` is `died`;
#   - text: the `up` row reads `up running port PORT pid P up …`, the `bad` and `gone` rows `died`, and
#     the verdict counts 1 running and 2 died;
#   - against the state (P004), right after the list: `up`'s pid is alive with its marker and the port
#     accepts; no process carries `bad`'s or `gone`'s marker.
#
# Isolation: each cell has its own session (`sv5-<run id>-<check>-<style>`) and its own free port.
# teardown_file SIGKILLs every process carrying a marker of this run's sessions and removes their
# scratch directories. Cells: bash -c and bash -lc, `notty`.

SPREFIX=sv5
SDIR_NAME=services-sc5

load helpers

setup_file() {
  stamp_check
  SDIR="$(container_tmpdir "$SDIR_NAME")"
  RUN_ID="${SDIR##*.}"
  SROOT="$(scratch_root)"
  SRV_PY="$(server_python)"
  export SDIR RUN_ID SROOT SRV_PY
}

teardown_file() {
  kill_my_services
  rm_sessions
  container_rm "${SDIR:-}"
}

# ── helpers (this file's own; the 010 files repeat them so each reads alone) ─────────────────────

# scratch_root — the container's session scratch root, read in the container, never assumed.
scratch_root() {
  local r
  r="$(exec_plain sh -c 'printf "%s" "${TIMELIKE_SCRATCH_ROOT:-/tmp/timelike}"')" || return 1
  [[ "$r" == /?* ]] || { echo "scratch root in the container: '${r}'" >&2; return 1; }
  printf '%s' "$r"
}

# server_python — the interpreter the fixture servers run under, chosen in the container: the image's
# own (the image puts no python3 on PATH), else a python3 on PATH (the host stand-in only).
server_python() {
  local p
  p="$(exec_plain sh -c 'if [ -x /opt/timelike/python/bin/python3 ]; then echo /opt/timelike/python/bin/python3; else command -v python3; fi')" || true
  [[ "$p" == /?* ]] || { echo "no python3 in the container for the fixture servers" >&2; return 1; }
  printf '%s' "$p"
}

# The run's own session prefix: every session of this file is `<SPREFIX>-<RUN_ID>-<check>-<style>…`.
my_prefix() {
  [[ -n "${RUN_ID:-}" ]] || return 1
  printf '%s-%s-' "$SPREFIX" "$RUN_ID"
}

# rm_sessions — remove this run's session directories (SROOT/<prefix>*) and nothing else.
rm_sessions() {
  local p
  p="$(my_prefix)" || return 0
  [[ "${SROOT:-}" == /tmp/?* ]] || return 0
  exec_plain sh -c 'for d in "$1/$2"*; do [ -d "$d" ] && rm -rf -- "$d"; done; exit 0' \
    rm "$SROOT" "$p" >/dev/null 2>&1 || true
}

# PROC_PY MODE ARG… — /proc, read in the container (P004). Zombies (state Z) count as gone.
#   list MARK   one line per live process whose environ holds an entry starting TIMELIKE_SERVICE=MARK:
#               "pid starttime sid state comm"
#   kill MARK   SIGKILL each of them
#   alive P:S…  the given pid:starttime pairs still alive (same pid, same start time: no reuse)
PROC_PY='import os, signal, sys
mode, args = sys.argv[1], sys.argv[2:]
def procs():
    for d in os.listdir("/proc"):
        if not d.isdigit():
            continue
        try:
            with open("/proc/" + d + "/stat", "rb") as f:
                st = f.read()
            with open("/proc/" + d + "/environ", "rb") as f:
                env = f.read().split(b"\0")
        except OSError:
            continue
        comm = st[st.index(b"(") + 1:st.rindex(b")")].decode(errors="replace")
        rest = st[st.rindex(b")") + 2:].split()
        yield int(d), rest[0].decode(), int(rest[3]), rest[19].decode(), comm, env
if mode == "alive":
    want = set(args)
    for pid, state, sid, start, comm, env in procs():
        if state != "Z" and str(pid) + ":" + start in want:
            print(pid, start, sid, state, comm)
else:
    mark = ("TIMELIKE_SERVICE=" + args[0]).encode()
    for pid, state, sid, start, comm, env in procs():
        if state == "Z" or not any(e.startswith(mark) for e in env):
            continue
        if mode == "kill":
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
        else:
            print(pid, start, sid, state, comm)
'

# marker_procs MARK — the live processes carrying a TIMELIKE_SERVICE=MARK… entry, one line each.
marker_procs() {
  exec_plain "$AGENT_PY" -I -c "$PROC_PY" list "$1"
}

# alive PID:START… — those still alive, one line each.
alive() {
  exec_plain "$AGENT_PY" -I -c "$PROC_PY" alive "$@"
}

# kill_markers MARK — SIGKILL every live process carrying MARK, twice (a pass may race a fork).
kill_markers() {
  [[ -n "$1" ]] || return 0
  exec_plain "$AGENT_PY" -I -c "$PROC_PY" kill "$1" >/dev/null 2>&1 || true
  exec_plain "$AGENT_PY" -I -c "$PROC_PY" kill "$1" >/dev/null 2>&1 || true
}

# kill_my_services — teardown: every process carrying a marker of this run's sessions.
kill_my_services() {
  local p
  p="$(my_prefix)" || return 0
  kill_markers "$p"
}

# free_port — a port free in the container now, chosen by the image's python.
free_port() {
  local p
  p="$(exec_plain "$AGENT_PY" -I -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1])')" || return 1
  p="${p//$'\r'/}"
  [[ "$p" =~ ^[0-9]+$ ]] || { echo "free port: '${p}'" >&2; return 1; }
  printf '%s' "$p"
}

# CONNECT_PY PORT — one TCP connect to 127.0.0.1:PORT; prints `accepted` or `refused <error>`.
CONNECT_PY='import socket, sys
try:
    socket.create_connection(("127.0.0.1", int(sys.argv[1])), 1).close()
    print("accepted")
except OSError as e:
    print("refused", e)
'

# port_state PORT — `accepted` or `refused …`, from the container.
port_state() {
  exec_plain "$AGENT_PY" -I -c "$CONNECT_PY" "$1"
}

# new_cell NAME STYLE — this cell's fixture directory (CELL, with CELL.stderr beside it), its own
# session (SESSION, which must have no records yet) and its own free port (PORT).
new_cell() {
  CELL="${SDIR}/$1-$2"
  SESSION="${SPREFIX}-${RUN_ID}-$1-$2"
  exec_plain mkdir "$CELL" || { echo "cell path ${CELL} exists: cells must not share a fixture" >&2; return 1; }
  if exec_plain test -e "${SROOT}/${SESSION}"; then
    echo "session ${SESSION} already has records: cells must not share a session" >&2
    return 1
  fi
  # shellcheck disable=SC2034 # read by the checks (the manifest file has no port to use)
  PORT="$(free_port)" || return 1
}

# in_session STYLE CMD — run CMD as the agent would, in this cell's session (SESSION); stderr goes to
# CELL.stderr so stdout stays one document.
in_session() {
  run_in -e "TIMELIKE_SESSION=${SESSION}" "$1" notty "{ $2; } 2>>'${CELL}.stderr'"
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

# expect_has WHAT TEXT PART… — TEXT contains every PART.
expect_has() {
  local what="$1" text="$2" part
  shift 2
  for part in "$@"; do
    [[ "$text" == *"$part"* ]] || flunk "${what} does not name '${part}': ${text}"
  done
}

# no_marker MARK WHAT — no live process carries MARK.
no_marker() {
  local left
  left="$(marker_procs "$1")" || flunk "cannot scan /proc for ${1}"
  [[ -z "$left" ]] || flunk "$2: processes carrying TIMELIKE_SERVICE=$1 remain (pid start sid state comm):
${left}"
}

# expect_marker_pid PID MARK — PID is alive and carries MARK.
expect_marker_pid() {
  local procs
  procs="$(marker_procs "$2")" || flunk "cannot scan /proc for ${2}"
  [[ $'\n'"$procs" == *$'\n'"$1 "* ]] || flunk "pid $1 is not a live process carrying TIMELIKE_SERVICE=$2; those carrying it:
${procs:-<none>}"
}

# ── checks ────────────────────────────────────────────────────────────────────────────────────

# register_three STYLE — up (running), bad (died before ready), gone (killed from outside). Sets UP_PID.
register_three() {
  in_session "$1" "services start up --port ${PORT} -- '${SRV_PY}' -m http.server ${PORT} --bind 127.0.0.1 --directory '${CELL}'"
  expect_status 0
  local ready_ms
  ready_ms="$(now_ms)"
  jfields pid
  UP_PID="$(jval pid)"
  [[ "$UP_PID" =~ ^[1-9][0-9]*$ ]] || flunk "up's pid: '${UP_PID}'"

  in_session "$1" "services start bad --port $(free_port) -- sh -c 'echo boom >&2; exit 3'"
  expect_status 1

  in_session "$1" "services start gone -- sleep 300"
  expect_status 0
  expect_marker_pid "$(jval_now pid)" "${SESSION}/gone/"
  kill_markers "${SESSION}/gone/"
  local i
  for ((i = 0; i < 30; i++)); do
    [[ -z "$(marker_procs "${SESSION}/gone/")" ]] && break
    sleep 0.1
  done
  no_marker "${SESSION}/gone/" "gone, killed by the test"

  local waited=$(($(now_ms) - ready_ms))
  ((waited >= 1500)) || sleep "$(ms_to_s $((1500 - waited)))"
}

# jval_now KEY — a field of the last run's JSON.
jval_now() {
  jfields "$1"
  jval "$1"
}

# listed_state — right after a list: up alive and serving; nothing of bad or gone alive.
listed_state() {
  expect_marker_pid "$UP_PID" "${SESSION}/up/"
  [[ "$(port_state "$PORT")" == accepted ]] || flunk "up's port ${PORT} does not accept"
  no_marker "${SESSION}/bad/" "bad, which died"
  no_marker "${SESSION}/gone/" "gone, which was killed"
}

# check_list_json STYLE — list --json: the states, port, pid and uptime.
check_list_json() {
  new_cell list-json "$1"
  register_three "$1"
  in_session "$1" "services list --json"
  expect_status 0
  listed_state
  jpy "svcs = g('services', []) or []
by = {s.get('name'): s for s in svcs}
print('names=' + json.dumps(sorted(by)))
for n in ('up', 'bad', 'gone'):
    s = by.get(n, {})
    for k in ('state', 'port', 'pid', 'exit'):
        print(n + '.' + k + '=' + json.dumps(s.get(k, '<absent>')))
u = by.get('up', {}).get('uptime_s')
print('up.uptime_ok=' + json.dumps(isinstance(u, (int, float)) and not isinstance(u, bool) and u >= 1))
print('up.uptime_s=' + json.dumps(u))"
  expect_j names '["bad", "gone", "up"]'
  expect_j up.state '"running"'
  expect_j up.port "$PORT"
  expect_j up.pid "$UP_PID"
  [[ "$(jval up.uptime_ok)" == true ]] || flunk "up's uptime_s is $(jval up.uptime_s), want a number >= 1 (it has been up for 1.5 s)"
  expect_j bad.state '"died"'
  expect_j bad.exit 3
  expect_j gone.state '"died"'
}

# check_list_text STYLE — list --text: the rows and the verdict's counts.
check_list_text() {
  new_cell list-text "$1"
  register_three "$1"
  in_session "$1" "services list --text"
  expect_status 0
  listed_state
  [[ "${lines[1]:-}" == "verdict: "* ]] || flunk "verdict line: ${lines[1]:-<none>}"
  expect_has "the verdict" "${lines[1]}" "1 running" "2 died"
  local line up_row=false bad_row=false gone_row=false
  for line in "${lines[@]:2}"; do
    [[ "$line" =~ ^up\ +running\ +port\ ${PORT}\ +pid\ ${UP_PID}\ +up\ [0-9] ]] && up_row=true
    [[ "$line" =~ ^bad\ +died\  ]] && bad_row=true
    [[ "$line" =~ ^gone\ +died\  ]] && gone_row=true
  done
  [[ "$up_row" == true ]] || flunk "no row 'up running port ${PORT} pid ${UP_PID} up …'"
  [[ "$bad_row" == true ]] || flunk "no row 'bad died …'"
  [[ "$gone_row" == true ]] || flunk "no row 'gone died …'"
}

@test "SC-5 [bash -c, notty] Listing services shows each registered service's state, port and uptime, and marks ones whose process has died — JSON: up running with port, pid, uptime >= 1 s; bad died exit 3; gone (killed outside) died" { check_list_json c; }
@test "SC-5 [bash -lc, notty] Listing services shows each registered service's state, port and uptime, and marks ones whose process has died — JSON: up running with port, pid, uptime >= 1 s; bad died exit 3; gone (killed outside) died" { check_list_json lc; }
@test "SC-5 [bash -c, notty] Listing services shows each registered service's state, port and uptime, and marks ones whose process has died — text: up row running, port, pid, up; bad and gone rows died; 1 running, 2 died" { check_list_text c; }
@test "SC-5 [bash -lc, notty] Listing services shows each registered service's state, port and uptime, and marks ones whose process has died — text: up row running, port, pid, up; bad and gone rows died; 1 running, 2 died" { check_list_text lc; }
