#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# shellcheck disable=SC2030,SC2031 # bats runs each @test in its own subshell by design
# Feature 13 slice 0, criterion 5 — "Bringing the environment up twice is a no-op the second time, and tearing it
# down removes every container, network and volume it created" (send 13-rev17; spec FR-4, FR-5, FR-10; research
# R5, R6).
#
# Checked against the daemon and the ledger, never the verdict alone (cross-stack P004):
#   - the second `up` says so (unchanged: nothing created or recorded), and the daemon's containers for the
#     environment are the same ids, still running; the ledger holds one performed row for it;
#   - before `down`, the daemon holds the fixture's containers, its default network and its named volume, each
#     labelled with the environment; after `down`, it holds 0 of each, read from the runner; and the ledger
#     records the ending, naming adele env down and the 0 left.

load helpers
load nested

setup_file() {
  stamp_check
  stamp_check_adele
}

teardown() { nested_teardown; }

ids_of() { docker ps -aq --no-trunc --filter "label=${NESTED_LABEL}=$1" | sort | tr '\n' ' '; }

check_twice_then_down() {
  local style="$1" before after counts
  nested_project "twice-${style}" basic
  env_run "$style" "--text env up --project ${NP_NAME} --grant nested"
  assert_status 0
  before="$(ids_of "$NP_NAME")"
  env_run "$style" "--text env up --project ${NP_NAME} --grant nested"
  assert_status 0
  [[ "${lines[1]}" == "verdict: up ${NP_NAME}: 3 ready, unchanged (nothing created or recorded) in "* ]] ||
    { echo "second verdict: ${lines[1]}" >&2; return 1; }
  after="$(ids_of "$NP_NAME")"
  [[ -n "$before" && "$before" == "$after" ]] || { echo "containers before: $before; after: $after" >&2; return 1; }
  run ledger_rows_for "$NP_NAME"
  assert_status 0
  [[ "$(printf '%s\n' "$output" | grep -c '^performed')" == 1 ]] || { echo "ledger: $output" >&2; return 1; }

  counts="$(nested_counts "$NP_NAME")"
  read -r c n v <<<"$counts"
  ((c == 3 && n >= 1 && v >= 1)) || { echo "before down: $counts (containers networks volumes)" >&2; return 1; }
  env_run "$style" "--text env down ${NP_NAME}"
  assert_status 0
  [[ "${lines[1]}" == "verdict: down ${NP_NAME}: removed 3 containers, ${n} networks, ${v} volumes; 0 left, read back from the daemon" ]] ||
    { echo "down: ${lines[1]}" >&2; return 1; }
  [[ "$(nested_counts "$NP_NAME")" == "0 0 0" ]] || { echo "after down: $(nested_counts "$NP_NAME")" >&2; return 1; }
  run ledger_rows_for "$NP_NAME"
  assert_status 0
  assert_output_has $'reaped\tdelete\t'
  assert_output_has "(adele env down)"
  assert_output_has "0 left, read back from the daemon"
}
@test "13 bringing the environment up twice is a no-op the second time, and down removes every container, network and volume [bash -c]" { check_twice_then_down c; }
@test "13 bringing the environment up twice is a no-op the second time, and down removes every container, network and volume [bash -lc]" { check_twice_then_down lc; }

@test "13 down of an environment that does not exist is exit 3 and removes nothing" {
  nested_project nothing
  env_run c "--text env down ${NP_NAME}"
  assert_status 3
  assert_output_has "no environment named ${NP_NAME}"
}
