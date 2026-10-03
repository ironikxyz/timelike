#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# SC-2 — "When the whole output fits within the head and tail, it is printed in full with no section
# markers". (Feature 003, slice 0; spec FR-15, Scenario 1.5; contracts/run-cli.md § Text output,
# uncapped body; research R8.)
#
# The fixture prints `line 1` … `line 120`: fewer than head + tail (50 + 100) and than the cap (200).
# run's text output must be exactly the header, the verdict, and the 120 lines — no `── ` section
# marker, no `more:` line, no `… omitted` line, and nothing after the last line (FR-15).
# Artefacts: run's output file has exactly 122 lines, and its last 120 are byte-identical to the
# fixture's own output.
# --text is explicit: under a pipe the default is JSON (contract rule).
# Cells: bash -c and bash -lc in `notty`.

load helpers

GEN_SCRIPT='#!/bin/bash
for ((i = 1; i <= 120; i++)); do echo "line $i"; done'

setup_file() {
  stamp_check
}

setup() {
  WORK="$(container_tmpdir sc2run)"
  exec_plain sh -c 'printf "%s\n" "$2" > "$1" && chmod 0755 "$1"' put "${WORK}/gen.sh" "$GEN_SCRIPT"
}

teardown() {
  container_rm "$WORK"
}

check_full_output() {
  run_in "$1" notty "run --text '${WORK}/gen.sh' > '${WORK}/out.txt' 2> '${WORK}/err.txt'; rc=\$?; echo \"rc=\$rc\"; exit \$rc"
  assert_within 20
  assert_status 0
  assert_value rc 0

  # Read the file run wrote (bats `lines` would drop empty lines).
  local out
  out="$(exec_plain cat "${WORK}/out.txt")" || { echo "cannot read run's output" >&2; return 1; }
  local -a rl
  mapfile -t rl <<<"${out//$'\r'/}"

  ((${#rl[@]} == 122)) || { printf 'expected 122 lines (header, verdict, 120), got %d:\n%s\n' "${#rl[@]}" "$out" >&2; return 1; }
  [[ "${rl[0]}" == "run: ${WORK}/gen.sh [run]" ]] || { echo "line 1 is not the header: ${rl[0]}" >&2; return 1; }
  [[ "${rl[1]}" == "verdict: exit 0 (command exited 0) · "* && "${rl[1]}" == *" · 120 lines · log /"* ]] ||
    { echo "line 2 is not an exit-0 verdict counting 120 lines: ${rl[1]}" >&2; return 1; }
  local n
  for ((n = 1; n <= 120; n++)); do
    [[ "${rl[n + 1]}" == "line $n" ]] || { printf 'line %d: expected %q, got %q\n' $((n + 2)) "line $n" "${rl[n + 1]}" >&2; return 1; }
  done
  local line
  for line in "${rl[@]}"; do
    if [[ "$line" == "── "* || "$line" == "more: "* || "$line" == "… omitted"* ]]; then
      printf 'unexpected section marker or omission line: %s\n' "$line" >&2
      return 1
    fi
  done

  # Byte-exact: the file's body is the command's output, and nothing follows its last line.
  run exec_plain sh -c '
    w="$1"
    echo "out_lines=$(wc -l < "$w/out.txt")"
    "$w/gen.sh" > "$w/ref.txt"
    tail -n 120 "$w/out.txt" > "$w/body.txt"
    if cmp -s "$w/body.txt" "$w/ref.txt"; then echo body=same; else echo body=differs; fi
  ' check "$WORK"
  [[ "$status" -eq 0 ]] || { printf 'artefact check failed to run:\n%s\n' "$output" >&2; return 1; }
  assert_value out_lines 122
  assert_value body same
}

@test "SC-2 when the whole output fits within the head and tail, it is printed in full with no section markers [bash -c, notty]" { check_full_output c; }
@test "SC-2 when the whole output fits within the head and tail, it is printed in full with no section markers [bash -lc, notty]" { check_full_output lc; }
