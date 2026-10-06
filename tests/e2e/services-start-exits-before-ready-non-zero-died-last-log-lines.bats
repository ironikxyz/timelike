#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# SC-2 — "Starting a service that exits before becoming ready returns non-zero with a verdict saying it
# died and its last log lines". (Feature 010, slice 1; spec FR-2, FR-11, Scenario 2; tasks.md T002;
# contracts/services-cli.md § start: died; research R3, R8.)
#
# Written from the contract before the tool existed. The service is a real `sh -c 'echo boom >&2;
# exit 3'` (P005) started with `--port PORT`, a port nothing listens on, so it can only die first.
# Checked:
#   - exit 1 (the contract's "died"; any non-zero would meet the criterion, and 124 would mean the tool
#     waited out its time limit instead of seeing the death), within 10 s;
#   - JSON: the verdict says `died`, the command's exit status is 3 (`exit_status`: the envelope's own
#     top-level `exit` is the tool's, 1), and `tail` holds the line the command printed (`boom`);
#     text: the verdict line says `died`, and a body line after it is `boom`;
#   - against the state (P004): the service's log, `<scratch>/<session>/services/<name>.log`, holds
#     `boom` (the tail shown is the log's); no process carrying the service's marker is alive; the port
#     does not accept.
#
# Isolation: each cell has its own session (`sv2-<run id>-<check>-<style>`) and its own free port.
# teardown_file SIGKILLs every process carrying a marker of this run's sessions and removes their
# scratch directories. Cells: bash -c and bash -lc, `notty`.

SPREFIX=sv2
SDIR_NAME=services-sc2

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

DIES="sh -c 'echo boom >&2; exit 3'"

# died_state — the log holds `boom`, nothing of the service is alive, and the port does not accept.
died_state() {
  local log="${SROOT}/${SESSION}/services/bad.log" content
  content="$(exec_plain cat "$log")" || flunk "cannot read the service's log ${log}"
  [[ $'\n'"$content"$'\n' == *$'\n'boom$'\n'* ]] || flunk "the log ${log} has no line 'boom': ${content}"
  no_marker "${SESSION}/bad/" "a service that died"
  [[ "$(port_state "$PORT")" != accepted ]] || flunk "port ${PORT} accepts, but the service died"
}

# check_died_json STYLE — exit 1 within 10 s; verdict `died`, exit 3, tail holds `boom`.
check_died_json() {
  new_cell died-json "$1"
  in_session "$1" "services start bad --port ${PORT} -- ${DIES}"
  expect_status 1
  assert_within 10
  jfields name verdict exit
  expect_j name bad
  expect_j exit 1
  [[ "$(jval verdict)" == *died* ]] || flunk "the verdict does not say died: $(jval verdict)"
  # The command's status: the envelope's own top-level `exit` is the tool's (1), so the contract's
  # `exit` (died) is read as `exit_status`, or as `exit` under `data` when the tool nests its data.
  jpy "e = d.get('exit_status', (d.get('data') or {}).get('exit', '<absent>'))
print('command_exit=' + json.dumps(e))"
  expect_j command_exit 3
  jpy "t = g('tail', None)
lines = t if isinstance(t, list) else (t.splitlines() if isinstance(t, str) else [])
print('boom_in_tail=' + json.dumps(any(str(x).strip() == 'boom' for x in lines)))"
  expect_j boom_in_tail true
  died_state
}

# check_died_text STYLE — --text: exit 1; the verdict line says `died`; a body line after it is `boom`.
check_died_text() {
  new_cell died-text "$1"
  in_session "$1" "services start bad --port ${PORT} --text -- ${DIES}"
  expect_status 1
  assert_within 10
  [[ "${lines[0]:-}" == "services: "* ]] || flunk "header line: ${lines[0]:-<none>}"
  [[ "${lines[1]:-}" == "verdict: "*died* ]] || flunk "verdict line: ${lines[1]:-<none>}"
  local line found=false
  for line in "${lines[@]:2}"; do
    line="${line#"${line%%[![:space:]]*}"}"
    [[ "$line" == boom ]] && found=true
  done
  [[ "$found" == true ]] || flunk "no line 'boom' after the verdict"
  died_state
}

@test "SC-2 [bash -c, notty] Starting a service that exits before becoming ready returns non-zero with a verdict saying it died and its last log lines — JSON: exit 1, exit 3, tail holds boom; log holds boom, no marker process" { check_died_json c; }
@test "SC-2 [bash -lc, notty] Starting a service that exits before becoming ready returns non-zero with a verdict saying it died and its last log lines — JSON: exit 1, exit 3, tail holds boom; log holds boom, no marker process" { check_died_json lc; }
@test "SC-2 [bash -c, notty] Starting a service that exits before becoming ready returns non-zero with a verdict saying it died and its last log lines — text: verdict says died, boom after it; log holds boom, no marker process" { check_died_text c; }
@test "SC-2 [bash -lc, notty] Starting a service that exits before becoming ready returns non-zero with a verdict saying it died and its last log lines — text: verdict says died, boom after it; log holds boom, no marker process" { check_died_text lc; }
