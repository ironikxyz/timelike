#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# SC-3 — "A command that backgrounds a child holding stdout and then exits returns its verdict within
# 2 seconds and names the detached child's process ID". The ID named is the child's. That is checked
# against a file the child itself wrote, not by matching command lines. (Feature 003, slice 0; spec
# FR-8, FR-9, FR-10, Scenario 2; research R5.)
#
# The fixture script backgrounds a child that inherits its stdout, writes its own pid to a marker
# (then execs `sleep 30`, so the pid stays the same and its name is `sleep`), waits until that marker
# exists, prints one line and exits 0. Elapsed time is measured INSIDE the container, around the `run`
# call alone (date +%s%N), so docker exec start-up does not count against the 2 s; the runner-side
# bound is only a backstop against a hang.
# Artefacts decide: run's exit status, the verdict's `detached:` list against the marker, and that the
# child is still alive after run returned (FR-9: run does not stop what the command left running).
# Process safety (R5; cycle 5 process failure 2): the child is found and killed by the pid in its own
# marker, never by pgrep/pkill -f or any match on a command line.
# Cells: bash -c and bash -lc in `notty`.

load helpers

# The command under test. $1 is the marker path. The child holds the script's stdout (the log).
BG_SCRIPT='#!/bin/sh
sh -c '"'"'echo $$ > "$1.tmp" && mv "$1.tmp" "$1" && exec sleep 30'"'"' child "$1" &
while [ ! -s "$1" ]; do sleep 0.05; done
echo hi'

setup_file() {
  stamp_check
}

setup() {
  WORK="$(container_tmpdir sc3run)"
  exec_plain sh -c 'printf "%s\n" "$2" > "$1" && chmod 0755 "$1"' put "${WORK}/bg.sh" "$BG_SCRIPT"
}

teardown() {
  # Kill the child by the pid it wrote itself, if it is still there.
  exec_plain sh -c 'p="$(cat "$1" 2>/dev/null)" && [ -n "$p" ] && kill -KILL "$p"' kill "${WORK}/pid" >/dev/null 2>&1 || true
  container_rm "$WORK"
}

check_detached() {
  run_in "$1" notty "s=\$(date +%s%N); run --text '${WORK}/bg.sh' '${WORK}/pid' > '${WORK}/out.txt' 2> '${WORK}/err.txt'; \
rc=\$?; e=\$(date +%s%N); echo \"rc=\$rc\"; echo \"elapsed_ms=\$(( (e - s) / 1000000 ))\"; \
p=\$(cat '${WORK}/pid' 2>/dev/null); echo \"pid=\$p\"; \
if [ -n \"\$p\" ] && kill -0 \"\$p\" 2>/dev/null; then echo alive=yes; else echo alive=no; fi"
  assert_within 20
  assert_status 0
  assert_value rc 0

  local elapsed pid
  elapsed="$(value_of elapsed_ms)"
  pid="$(value_of pid)"
  [[ "$elapsed" =~ ^[0-9]+$ ]] || { printf 'no elapsed time measured; output:\n%s\n' "$output" >&2; return 1; }
  ((elapsed < 2000)) || { echo "run took ${elapsed} ms to conclude, limit 2000 ms" >&2; return 1; }
  [[ "$pid" =~ ^[0-9]+$ ]] || { printf 'the child wrote no pid marker; output:\n%s\n' "$output" >&2; return 1; }
  assert_value alive yes # FR-9: the detached child is named, not stopped

  # The verdict (line 2 of run's own output) names that pid as detached.
  local out verdict detached item found=""
  out="$(exec_plain cat "${WORK}/out.txt")"
  local -a run_lines
  mapfile -t run_lines <<<"${out//$'\r'/}"
  [[ "${run_lines[0]:-}" == "run: "*" [run]" ]] || { printf 'line 1 is not the header:\n%s\n' "$out" >&2; return 1; }
  verdict="${run_lines[1]:-}"
  [[ "$verdict" == "verdict: exit 0 (command exited 0) · "* ]] || { echo "line 2 is not an exit-0 verdict: $verdict" >&2; return 1; }
  [[ "$verdict" == *" · detached: "* ]] || { echo "the verdict names no detached child: $verdict" >&2; return 1; }
  detached="${verdict#* · detached: }"
  detached="${detached%% · *}"
  local -a items
  IFS=',' read -r -a items <<<"$detached"
  for item in "${items[@]}"; do
    item="${item# }"
    if [[ "$item" == "$pid sleep" ]]; then
      found=1
    fi
  done
  [[ -n "$found" ]] || { echo "detached list '${detached}' does not name the child's pid ${pid} (sleep)" >&2; return 1; }
}

@test "SC-3 a command that backgrounds a child holding stdout and then exits returns its verdict within 2 seconds and names the detached child's process ID [bash -c, notty]" { check_detached c; }
@test "SC-3 a command that backgrounds a child holding stdout and then exits returns its verdict within 2 seconds and names the detached child's process ID [bash -lc, notty]" { check_detached lc; }
