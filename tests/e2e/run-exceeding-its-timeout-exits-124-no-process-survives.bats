#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# SC-4 — "A command exceeding its timeout exits 124, the verdict says timeout, and no process from its
# process group survives". The nested case is included: a descendant that leads its own process group
# (a nested `timeout`). Survival is checked by a marker each descendant would write if still alive.
# (Feature 003, slice 0; spec FR-6, FR-7, Scenario 3; research R4.)
#
# The fixture is a tree whose every member appends to its own heartbeat marker every 0.2 s, forever:
#   main            the script itself
#   plain           a plain background loop (same process group)
#   nested-timeout  under `timeout 50 …`, which leads its own process group
#   setsid          under `setsid`, a new session and group
#   trap-term       a subshell that ignores SIGTERM (so only the forced stop ends it)
# Each also writes its own pid to <name>.pid when it starts.
# `run --timeout 2` must exit 124 with a timeout verdict. Then:
#   1. control: every heartbeat marker exists and is non-empty, so every member really started;
#   2. survival by heartbeat: marker sizes are recorded, 1.5 s pass, and none has grown;
#   3. survival by pid: no pid a member wrote for itself is still a live (non-zombie) process. This
#      catches a member left stopped (SIGSTOP without SIGKILL, R4), which writes no heartbeat.
# Never pgrep/pkill -f or any match on a command line (cycle 5 process failure 2): the tree is found
# only through the files its members wrote.
# Bound: R4's worst case is the limit + 5 s (2 s TERM grace, ≤ 3 s kill and re-scan); the runner's
# own limit is 30 s, far above that, so a hang in run shows as a failure, not a wait.
# Cells: bash -c and bash -lc in `notty`.

load helpers

HANG_SCRIPT='#!/bin/bash
# hang.sh DIR — every member of this tree beats DIR/<name>.beat every 0.2 s, forever.
d="$1"
beat() {
  echo "$BASHPID" > "$d/$1.pid"
  while :; do printf . >> "$d/$1.beat"; sleep 0.2; done
}
export -f beat
export d
beat plain &
timeout 50 bash -c "beat nested-timeout" &
setsid bash -c "beat setsid" &
( trap "" TERM; beat trap-term ) &
beat main'

MEMBERS=(main plain nested-timeout setsid trap-term)

setup_file() {
  stamp_check
}

setup() {
  WORK="$(container_tmpdir sc4run)"
  exec_plain mkdir "${WORK}/m"
  exec_plain sh -c 'printf "%s\n" "$2" > "$1" && chmod 0755 "$1"' put "${WORK}/hang.sh" "$HANG_SCRIPT"
}

teardown() {
  # Best effort, and only by the pids the members wrote for themselves.
  exec_plain sh -c 'for f in "$1"/*.pid; do [ -s "$f" ] && kill -KILL "$(cat "$f")" 2>/dev/null; done; :' \
    killpids "${WORK}/m" >/dev/null 2>&1 || true
  container_rm "$WORK"
}

check_timeout() {
  # shellcheck disable=SC2034 # read by run_in/exec_in in helpers.bash
  local RUN_TIMEOUT=30 # well above 2 s + 5 s grace
  run_in "$1" notty "run --text --timeout 2 '${WORK}/hang.sh' '${WORK}/m' > '${WORK}/out.txt' 2> '${WORK}/err.txt'; \
rc=\$?; echo \"rc=\$rc\"; exit \$rc"
  # Not assert_within: it reads status 124 as the runner's own timeout, and 124 is the exit expected
  # here. The runner's timeout is decided by elapsed time instead, as run_in itself decides it.
  ((ELAPSED_MS < RUN_TIMEOUT * 1000)) ||
    { echo "timed out after ${ELAPSED_S}s (runner limit ${RUN_TIMEOUT}s): run waited on something" >&2; return 1; }
  local limit_s=$((2 + 5 + 2)) # limit + R4's grace + docker exec overhead
  ((ELAPSED_MS < limit_s * 1000)) || { echo "took ${ELAPSED_S}s, limit ${limit_s}s" >&2; return 1; }
  assert_status 124
  assert_value rc 124

  local out
  out="$(exec_plain cat "${WORK}/out.txt")"
  local -a run_lines
  mapfile -t run_lines <<<"${out//$'\r'/}"
  [[ "${run_lines[0]:-}" == "run: "*" [run]" ]] || { printf 'line 1 is not the header:\n%s\n' "$out" >&2; return 1; }
  [[ "${run_lines[1]:-}" =~ ^verdict:\ exit\ 124\ \(timeout\ after\ 2(\.0+)?\ s ]] ||
    { echo "line 2 is not a timeout verdict naming the 2 s limit: ${run_lines[1]:-}" >&2; return 1; }
  [[ "${run_lines[1]}" == *"--timeout"* && "${run_lines[1]}" == *"TIMELIKE_RUN_TIMEOUT"* ]] ||
    { echo "the verdict does not name both ways to raise the limit: ${run_lines[1]}" >&2; return 1; }
  [[ "${run_lines[1]}" != *"not stopped"* ]] || { echo "run itself reports survivors: ${run_lines[1]}" >&2; return 1; }

  # 1–3 in one container call, so the 1.5 s window is the container's own clock.
  run exec_plain sh -c '
    d="$1"; shift
    for n in "$@"; do
      if [ -s "$d/$n.beat" ]; then echo "started-$n=yes"; else echo "started-$n=no"; fi
    done
    before=$(for n in "$@"; do printf "%s=%s\n" "$n" "$(stat -c %s "$d/$n.beat" 2>/dev/null)"; done)
    sleep 1.5
    after=$(for n in "$@"; do printf "%s=%s\n" "$n" "$(stat -c %s "$d/$n.beat" 2>/dev/null)"; done)
    for n in "$@"; do
      b=$(printf "%s\n" "$before" | sed -n "s/^$n=//p")
      a=$(printf "%s\n" "$after" | sed -n "s/^$n=//p")
      if [ "$a" = "$b" ]; then echo "beating-$n=no"; else echo "beating-$n=yes ($b -> $a bytes)"; fi
      p=$(cat "$d/$n.pid" 2>/dev/null)
      st=""
      [ -n "$p" ] && st=$(sed -n "s/^.*) \(.\).*/\1/p" "/proc/$p/stat" 2>/dev/null)
      case "$st" in
        "" | Z) echo "alive-$n=no" ;;
        *) echo "alive-$n=yes (pid $p state $st)" ;;
      esac
    done
  ' survive "${WORK}/m" "${MEMBERS[@]}"
  [[ "$status" -eq 0 ]] || { printf 'survival check failed to run:\n%s\n' "$output" >&2; return 1; }
  local n
  for n in "${MEMBERS[@]}"; do
    assert_value "started-$n" yes
  done
  for n in "${MEMBERS[@]}"; do
    assert_value "beating-$n" no
    assert_value "alive-$n" no
  done
}

@test "SC-4 a command exceeding its timeout exits 124, the verdict says timeout, and no process from its process group survives [bash -c, notty]" { check_timeout c; }
@test "SC-4 a command exceeding its timeout exits 124, the verdict says timeout, and no process from its process group survives [bash -lc, notty]" { check_timeout lc; }
