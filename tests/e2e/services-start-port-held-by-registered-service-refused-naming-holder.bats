#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# SC-3 — "Starting a service on a port already in use by another registered service is refused, naming
# the holder". (Feature 010, slice 1; spec FR-3, Scenario 3; tasks.md T002; contracts/services-cli.md
# § start: port held; research R4, R8.)
#
# Written from the contract before the tool existed. The holder is a real `python3 -m http.server PORT`
# started by `services start web --port PORT` (P005). The second start asks for the same port with a
# command that would NOT die if it were started (`sleep 300`): a tool that skipped the holder check would
# find the port accepting (web's) and report it ready, exit 0, so a refusal cannot be a death or a
# readiness wait in disguise. Checked:
#   - exit 1; JSON `holder` is `{name: web, session, pid}` with the holder's own pid (the registered
#     holder, not an anonymous socket owner), and the verdict names `web`, its session and `pid P`;
#   - against the state (P004): no process carrying the second service's marker exists; the holder's
#     pid is still alive with its marker; the port still accepts.
# Two checks per style: the holder in the same session, and in another session of the same agent
# (FR-3: every registry the caller can read).
#
# Isolation: each cell has its own sessions (`sv3-<run id>-<check>-<style>[-peer]`) and its own free
# port. teardown_file SIGKILLs every process carrying a marker of this run's sessions and removes their
# scratch directories. Cells: bash -c and bash -lc, `notty`.

SPREFIX=sv3
SDIR_NAME=services-sc3

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

# start_holder STYLE — `web` on PORT in SESSION: exit 0 and the port accepting. Sets HOLDER_PID.
start_holder() {
  in_session "$1" "services start web --port ${PORT} -- '${SRV_PY}' -m http.server ${PORT} --bind 127.0.0.1 --directory '${CELL}'"
  expect_status 0
  jfields pid
  HOLDER_PID="$(jval pid)"
  [[ "$HOLDER_PID" =~ ^[1-9][0-9]*$ ]] || flunk "the holder's pid: '${HOLDER_PID}'"
  expect_marker_pid "$HOLDER_PID" "${SESSION}/web/"
  [[ "$(port_state "$PORT")" == accepted ]] || flunk "the holder's port ${PORT} does not accept"
}

# refused_naming STYLE HOLDER_SESSION — `web2` on the same port, in SESSION: refused, naming web in
# HOLDER_SESSION with HOLDER_PID; nothing of web2 exists; the holder is untouched.
refused_naming() {
  local holder_session="$2" verdict
  in_session "$1" "services start web2 --port ${PORT} -- sleep 300"
  expect_status 1
  jfields verdict holder.name holder.session holder.pid
  expect_j holder.name web
  expect_j holder.session "$holder_session"
  expect_j holder.pid "$HOLDER_PID"
  verdict="$(jval verdict)"
  expect_has "the verdict" "$verdict" "port ${PORT}" web "$holder_session" "pid ${HOLDER_PID}"
  no_marker "${SESSION}/web2/" "a refused start"
  expect_marker_pid "$HOLDER_PID" "${holder_session}/web/"
  [[ "$(port_state "$PORT")" == accepted ]] || flunk "the holder's port ${PORT} no longer accepts"
}

# check_same_session STYLE — the holder is in this session.
check_same_session() {
  new_cell held "$1"
  start_holder "$1"
  refused_naming "$1" "$SESSION"
}

# check_peer_session STYLE — the holder is in another session of the same agent.
check_peer_session() {
  new_cell held-peer "$1"
  local mine="$SESSION"
  SESSION="${mine}-peer"
  exec_plain test ! -e "${SROOT}/${SESSION}" || flunk "session ${SESSION} already has records"
  start_holder "$1"
  local holder_session="$SESSION"
  SESSION="$mine"
  refused_naming "$1" "$holder_session"
}

@test "SC-3 [bash -c, notty] Starting a service on a port already in use by another registered service is refused, naming the holder — same session: exit 1, holder web with its session and pid; no web2 process; holder still serving" { check_same_session c; }
@test "SC-3 [bash -lc, notty] Starting a service on a port already in use by another registered service is refused, naming the holder — same session: exit 1, holder web with its session and pid; no web2 process; holder still serving" { check_same_session lc; }
@test "SC-3 [bash -c, notty] Starting a service on a port already in use by another registered service is refused, naming the holder — holder in a peer session: exit 1, holder web with that session and pid; no web2 process" { check_peer_session c; }
@test "SC-3 [bash -lc, notty] Starting a service on a port already in use by another registered service is refused, naming the holder — holder in a peer session: exit 1, holder web with that session and pid; no web2 process" { check_peer_session lc; }
