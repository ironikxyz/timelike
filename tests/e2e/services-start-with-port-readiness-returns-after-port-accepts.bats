#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# SC-1 — "Starting a service with a port readiness condition returns only after the port accepts
# connections, with a verdict naming the name, process ID, port and log path". (Feature 010, slice 1;
# spec FR-1, FR-2, Scenario 1; tasks.md T002; contracts/services-cli.md § start; research R3, R8.)
#
# Written from the contract before the tool existed. Every claim is checked against the state it claims
# (P004), in the container:
#   - "returns only after the port accepts": the SAME container shell connects to 127.0.0.1:PORT the
#     moment `services start` returns, before anything else runs, and the connect must succeed. A second
#     check puts a 2 s sleep in front of the server, so a start that returned early would find the port
#     refusing (and would return in under 2 s);
#   - the verdict and the JSON name the name, the pid, the port and the log path; the pid is a live
#     process carrying the marker `TIMELIKE_SERVICE=<session>/<name>/…` in /proc; the log path is
#     `<scratch>/<session>/services/<name>.log` (FR-1) and exists.
# The fixture server is a real `python3 -m http.server PORT --bind 127.0.0.1` (P005), on the image's
# interpreter (the image has no python3 on PATH).
#
# Isolation: each cell has its own session (`sv1-<run id>-<check>-<style>`; the run id is the random
# suffix of this file's container_tmpdir) and its own free port, chosen in the container. teardown_file
# SIGKILLs every process carrying a marker of this run's sessions and removes their scratch directories.
# Cells: bash -c and bash -lc, `notty` (JSON is the default when stdout is not a terminal).

SPREFIX=sv1
SDIR_NAME=services-sc1

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

# start_probed STYLE ARGS — `services start ARGS` in this cell's session; the same container shell
# then connects to PORT at once and writes the result to CELL.conn; stdout is start's alone, and the
# exit status is start's.
start_probed() {
  in_session "$1" "services start $2 >'${CELL}.out'; rc=\$?; '${SRV_PY}' -I -c '${CONNECT_PY}' ${PORT} >'${CELL}.conn' 2>&1; cat '${CELL}.out'; exit \$rc"
}

# connected_at_return — the connect made the moment start returned succeeded.
connected_at_return() {
  local c
  c="$(exec_plain cat "${CELL}.conn")" || flunk "no connect result in ${CELL}.conn"
  [[ "$c" == accepted ]] || flunk "start returned, but port ${PORT} did not accept at that moment: ${c}"
}

# ready_claims NAME — the JSON and the verdict name the name, the pid, the port and the log path; the pid
# is alive with this service's marker; the log is FR-1's path and exists. Sets SVC_PID.
ready_claims() {
  local name="$1" log_want="${SROOT}/${SESSION}/services/$1.log" verdict
  jfields name session pid port log ready verdict
  expect_j name "$name"
  expect_j session "$SESSION"
  expect_j port "$PORT"
  expect_j ready port
  expect_j log "$log_want"
  SVC_PID="$(jval pid)"
  [[ "$SVC_PID" =~ ^[1-9][0-9]*$ ]] || flunk "pid: '${SVC_PID}'"
  verdict="$(jval verdict)"
  expect_has "the verdict" "$verdict" "$name" "pid ${SVC_PID}" "port ${PORT}" "$log_want" ready
  expect_marker_pid "$SVC_PID" "${SESSION}/${name}/"
  exec_plain test -f "$log_want" || flunk "the log ${log_want} does not exist"
}

# check_ready STYLE — an http.server: exit 0; the port accepted when start returned; the claims.
check_ready() {
  new_cell ready "$1"
  start_probed "$1" "web --port ${PORT} -- '${SRV_PY}' -m http.server ${PORT} --bind 127.0.0.1 --directory '${CELL}'"
  expect_status 0
  connected_at_return
  ready_claims web
  [[ "$(port_state "$PORT")" == accepted ]] || flunk "port ${PORT} does not accept"
}

# check_ready_delayed STYLE — the server binds only after 2 s: start takes at least 2 s, and the port
# accepted when it returned; the claims.
check_ready_delayed() {
  new_cell ready-delayed "$1"
  local cmd='sleep 2; exec "$0" -m http.server "$1" --bind 127.0.0.1 --directory "$2"'
  start_probed "$1" "slow --port ${PORT} -- sh -c '${cmd}' '${SRV_PY}' ${PORT} '${CELL}'"
  expect_status 0
  ((ELAPSED_MS >= 2000)) || flunk "start returned after ${ELAPSED_S}s, before the server could have bound (2 s)"
  connected_at_return
  ready_claims slow
}

@test "SC-1 [bash -c, notty] Starting a service with a port readiness condition returns only after the port accepts connections, with a verdict naming the name, process ID, port and log path — http.server: port accepts at return; pid alive with its marker; log exists" { check_ready c; }
@test "SC-1 [bash -lc, notty] Starting a service with a port readiness condition returns only after the port accepts connections, with a verdict naming the name, process ID, port and log path — http.server: port accepts at return; pid alive with its marker; log exists" { check_ready lc; }
@test "SC-1 [bash -c, notty] Starting a service with a port readiness condition returns only after the port accepts connections, with a verdict naming the name, process ID, port and log path — server binding after 2 s: start waits, port accepts at return" { check_ready_delayed c; }
@test "SC-1 [bash -lc, notty] Starting a service with a port readiness condition returns only after the port accepts connections, with a verdict naming the name, process ID, port and log path — server binding after 2 s: start waits, port accepts at return" { check_ready_delayed lc; }
