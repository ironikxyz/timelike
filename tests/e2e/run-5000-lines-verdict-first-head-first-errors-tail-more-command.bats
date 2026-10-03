#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# SC-1 — "Running a command that prints 5,000 lines returns a verdict line first, then the first
# lines, the first error lines with their line numbers, the last lines, and the exact command to view
# the rest". Running that command prints exactly the lines it names. (Feature 003, slice 0; spec
# FR-11 to FR-16, Scenario 1; contracts/run-cli.md § Text output; research R8, R9.)
#
# The fixture prints `line 1` … `line 5000`, except lines 700, 1800 and 3000, which read
# `error: boom <n>`: beyond the head (50), before the tail (last 100), and the only lines matching any
# R9 pattern. With the contract's cap of 200 (R8: head ⌊L/4⌋ = 50, errors ≤ ⌊L/10⌋ = 20, tail
# ⌊L/2⌋ = 100) run's text output must be, line by line:
#   1        run: <command> [run]                       (FR-11: the header, then the verdict)
#   2        verdict: exit 0 (command exited 0) · … · 5000 lines · log <path>
#   3        ── <head marker>
#   4–53     line 1 … line 50
#   54       ── <first-errors marker>
#   55–57    L700: error: boom 700, L1800: …, L3000: …
#   58       ── <tail marker>
#   59–158   line 4901 … line 5000
#   159      more: <command>
#   160–161  exit: 0, full output: <log>
#   162      … omitted … (the last line)
# Marker wording is checked only by its `── ` prefix; the lines between are checked exactly.
# Artefacts: the log itself equals the fixture's output byte for byte (FR-16), and the `more:` command,
# executed in the container as an agent would paste it, prints exactly the omitted lines of that log.
# --text is explicit: under a pipe the default is JSON (contract rule).
# Cells: bash -c and bash -lc in `notty`.

load helpers

GEN_SCRIPT='#!/bin/bash
for ((i = 1; i <= 5000; i++)); do
  case $i in
    700 | 1800 | 3000) echo "error: boom $i" ;;
    *) echo "line $i" ;;
  esac
done'

setup_file() {
  stamp_check
}

setup() {
  WORK="$(container_tmpdir sc1run)"
  exec_plain sh -c 'printf "%s\n" "$2" > "$1" && chmod 0755 "$1"' put "${WORK}/gen.sh" "$GEN_SCRIPT"
}

teardown() {
  container_rm "$WORK"
}

# ── A cursor over run's own output (RL), so every line is accounted for in order ─────────────────
# Read from the file run wrote, not from $output: bats `lines` drops empty lines, and this test must
# see every line exactly.
load_run_output() {
  local out
  out="$(exec_plain cat "${WORK}/out.txt")" || { echo "cannot read run's output" >&2; return 1; }
  mapfile -t RL <<<"${out//$'\r'/}"
  CUR=0
}

show_run_output() {
  printf '%s\n' "${RL[@]}" >&2
}

# expect_line TEXT — the line at the cursor is exactly TEXT; advance.
expect_line() {
  if [[ "${RL[CUR]-<end of output>}" != "$1" ]]; then
    printf 'run output line %d: expected %q, got %q; output:\n' $((CUR + 1)) "$1" "${RL[CUR]-<end of output>}" >&2
    show_run_output
    return 1
  fi
  CUR=$((CUR + 1))
}

# expect_prefix PREFIX — the line at the cursor starts with PREFIX; advance. Sets GOT to the line.
expect_prefix() {
  GOT="${RL[CUR]-<end of output>}"
  if [[ "$GOT" != "$1"* ]]; then
    printf 'run output line %d: expected a line starting %q, got %q; output:\n' $((CUR + 1)) "$1" "$GOT" >&2
    show_run_output
    return 1
  fi
  CUR=$((CUR + 1))
}

check_long_output() {
  run_in "$1" notty "run --text '${WORK}/gen.sh' > '${WORK}/out.txt' 2> '${WORK}/err.txt'; rc=\$?; echo \"rc=\$rc\"; exit \$rc"
  assert_within 20
  assert_status 0
  assert_value rc 0
  load_run_output

  # Header, then the verdict first.
  expect_line "run: ${WORK}/gen.sh [run]"
  expect_prefix "verdict: exit 0 (command exited 0) · "
  local verdict="$GOT" log rest
  [[ "$verdict" == *" · 5000 lines · log "* ]] || { echo "the verdict does not count 5000 lines and name the log: $verdict" >&2; return 1; }
  rest="${verdict#* · log }"
  log="${rest%% · *}"
  [[ "$log" == /?* && "$log" != *" "* ]] || { echo "no absolute log path in the verdict: $verdict" >&2; return 1; }

  # Head: the first 50 lines.
  expect_prefix "── "
  local n
  for ((n = 1; n <= 50; n++)); do
    expect_line "line $n"
  done

  # First errors, each with its line number in the log, in order.
  expect_prefix "── "
  [[ "$GOT" == *error* ]] || { echo "the section after the head is not the first-errors section: $GOT" >&2; return 1; }
  expect_line "L700: error: boom 700"
  expect_line "L1800: error: boom 1800"
  expect_line "L3000: error: boom 3000"

  # Tail: the last 100 lines.
  expect_prefix "── "
  for ((n = 4901; n <= 5000; n++)); do
    expect_line "line $n"
  done

  # The exact command for the rest, then the contract's closing lines; the omission line is last.
  expect_prefix "more: "
  local more="${GOT#more: }"
  [[ "$more" == "sed -n "* ]] || { echo "the more command does not read the log with sed -n: $more" >&2; return 1; }
  [[ "$more" == *" ${log}" || "$more" == *" '${log}'" ]] || { echo "the more command does not read ${log}: $more" >&2; return 1; }
  expect_line "exit: 0"
  expect_line "full output: ${log}"
  expect_prefix "… omitted "
  [[ "$GOT" == *"more: ${more}" ]] || { echo "the omission line does not carry the same more command: $GOT" >&2; return 1; }
  ((CUR == ${#RL[@]})) || { printf 'lines follow the omission line (line %d of %d); output:\n' "$CUR" "${#RL[@]}" >&2; show_run_output; return 1; }

  # Artefacts: the log is the command's output, and the more command prints exactly the omitted lines.
  run exec_plain sh -c '
    w="$1"; log="$2"; more="$3"
    "$w/gen.sh" > "$w/ref.txt"
    if cmp -s "$log" "$w/ref.txt"; then echo log=same; else echo log=differs; fi
    bash -c "$more" > "$w/more.out"
    echo "more_rc=$?"
    sed -n 51,4900p "$log" > "$w/gap.txt"
    sed -n -e 51,699p -e 701,1799p -e 1801,2999p -e 3001,4900p "$log" > "$w/gap-minus-errors.txt"
    if cmp -s "$w/more.out" "$w/gap.txt"; then echo more=gap
    elif cmp -s "$w/more.out" "$w/gap-minus-errors.txt"; then echo more=gap-minus-errors
    else echo "more=differs ($(wc -l < "$w/more.out") lines)"; fi
  ' check "$WORK" "$log" "$more"
  [[ "$status" -eq 0 ]] || { printf 'artefact check failed to run:\n%s\n' "$output" >&2; return 1; }
  assert_value log same
  assert_value more_rc 0
  # Lines 51–4900 are the ones neither the head nor the tail shows. The three error lines inside that
  # gap were shown, so a more command may include them (contract example: one range, 51,4900) or
  # leave them out (R8: two or more ranges when the errors split the gap). Every log line is
  # distinct, so a byte-equal match proves exactly which lines were printed.
  local got
  got="$(value_of more)"
  [[ "$got" == gap || "$got" == gap-minus-errors ]] ||
    { echo "the more command (${more}) does not print exactly the omitted lines of ${log}: ${got}" >&2; return 1; }
}

@test "SC-1 running a command that prints 5,000 lines returns a verdict line first, then the first lines, the first error lines with their line numbers, the last lines, and the exact command to view the rest [bash -c, notty]" { check_long_output c; }
@test "SC-1 running a command that prints 5,000 lines returns a verdict line first, then the first lines, the first error lines with their line numbers, the last lines, and the exact command to view the rest [bash -lc, notty]" { check_long_output lc; }
