#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# shellcheck disable=SC2030,SC2031 # bats runs each @test in its own subshell by design
# Feature 13 slice 1, decision C (the operator, at slice 0's sign-off) — "a one-shot is never ready while it runs"
# (spec Scenario 12, FR-11 as corrected in slice 1, D-13; research R20; contracts/adele-env.md § Slice 1, Readiness).
#
#   - A service with no healthcheck and no port gives no readiness signal: up exits 0 and reports it as running with
#     no readiness check, never "ready", and the verdict counts it apart (N ready, M running with no readiness check).
#   - A service another depends on with condition service_completed_successfully is a one-shot for certain: up waits
#     for its exit, and an exit 0 is completed. The daemon, read from the runner, has it labelled as a one-shot and
#     exited 0 (cross-stack P004).
#   - A one-shot that exits non-zero fails up with exit 1, naming it: when another service depends on it, compose
#     itself refuses to start that service, Adele removes what compose created and says so; and a service with no
#     readiness signal that exits non-zero while up still waits fails up naming it and its last lines.
# Waits are plumbing; nothing asserts a time.

load helpers
load nested

setup_file() {
  stamp_check
  stamp_check_adele
}

teardown() { nested_teardown; }

check_no_readiness_signal() {
  local style="$1" seed idle
  nested_project "oneshot-${style}" oneshot
  env_run "$style" "--text env up --project ${NP_NAME} --grant nested"
  assert_status 0
  [[ "${lines[1]}" == "verdict: up ${NP_NAME}: 1 ready, 2 running with no readiness check in "* ]] ||
    { echo "verdict: ${lines[1]}" >&2; return 1; }
  assert_output_has "idle  running, no readiness check"
  assert_output_has "app  running, no readiness check"
  assert_output_has "seed  completed (exit 0)"
  assert_no_line_matching '^(idle|app)  ready'
  # The daemon's own record: seed is the one-shot, exited 0; idle and app are running, and not one-shots.
  seed="$(nested_container "$NP_NAME" seed)"
  idle="$(nested_container "$NP_NAME" idle)"
  [[ -n "$seed" && -n "$idle" ]] || { echo "containers: seed=${seed} idle=${idle}" >&2; return 1; }
  [[ "$(docker inspect --format '{{.State.Status}} {{.State.ExitCode}} {{index .Config.Labels "xyz.ironik.timelike.one-shot"}}' "$seed")" == "exited 0 1" ]] ||
    { echo "seed: $(docker inspect --format '{{.State.Status}} {{.State.ExitCode}} {{json .Config.Labels}}' "$seed")" >&2; return 1; }
  [[ "$(docker inspect --format '{{.State.Status}} {{index .Config.Labels "xyz.ironik.timelike.one-shot"}}' "$idle")" == "running " ]] ||
    { echo "idle: $(docker inspect --format '{{.State.Status}} {{json .Config.Labels}}' "$idle")" >&2; return 1; }
  # The JSON says the same, per service: unchecked is never ready.
  env_run "$style" "--json env up --project ${NP_NAME} --grant nested"
  assert_status 0
  printf '%s' "$output" | pyq "
import json, sys
d = json.load(sys.stdin)
s = {x['service']: x for x in d['services']}
assert s['idle']['ready'] == 'unchecked' and s['app']['ready'] == 'unchecked', s
assert s['seed']['ready'] == 'completed' and s['seed']['one_shot'] is True and s['idle']['one_shot'] is False, s
"
}
@test "13 a service with no readiness signal is never reported ready while it runs, and a one-shot is waited for [bash -c]" { check_no_readiness_signal c; }
@test "13 a service with no readiness signal is never reported ready while it runs, and a one-shot is waited for [bash -lc]" { check_no_readiness_signal lc; }

@test "13 a one-shot another service waits on that exits 1 fails up with exit 1 naming it" {
  nested_project oneshot-fail oneshot-fail
  RUN_TIMEOUT="$PLUMBING_TIMEOUT" run_in -w "$NP_DIR" c notty "adele --text env up --project ${NP_NAME} --grant nested 2>&1 >/dev/null"
  assert_status 1
  assert_output_has "seed"
  # Which path answers is compose's: with seed failed, compose up -d refuses to start app (exit 1), and Adele answers
  # 502 "compose up failed" with what was left, read back, after removing what it created (broker/env.go). Should
  # compose return before seed's exit instead, the client's own rule fails up on seed's exit, naming its last lines,
  # and the environment stays up for teardown to remove. Either is exit 1 naming seed; each is checked for its own.
  if [[ "$output" == *"compose up failed"* ]]; then
    [[ "$output" == *"what it created was removed; the daemon, read back, has 0 objects labelled ${NP_NAME} left"* ]] ||
      { echo "remedy: $output" >&2; return 1; }
    nested_gone "$NP_NAME"
  else
    assert_output_has "${NP_NAME}: service seed exited 1, read back from the daemon; it will not become ready (last lines: seed failed: no fixture data)"
  fi
  echo "# 13 failed one-shot: answered by $([[ "$output" == *"compose up failed"* ]] && echo "compose (502)" || echo "the client's readiness rule")" >&3
}

@test "13 a service with no readiness signal that exits 1 while up waits fails up naming it and its last lines" {
  nested_project oneshot-exits oneshot-exits
  RUN_TIMEOUT="$PLUMBING_TIMEOUT" run_in -w "$NP_DIR" c notty "adele --text env up --project ${NP_NAME} --grant nested 2>&1 >/dev/null"
  assert_status 1
  assert_output_has "error: ${NP_NAME}: service broke exited 1, read back from the daemon; it will not become ready (last lines: broke: the fixture says so) (code 1)"
  assert_output_has " — look at the project's service; the environment is still up: adele env down ${NP_NAME}"
  [[ "$(nested_counts "$NP_NAME")" != "0 0 0" ]] || { echo "the environment did not stay up" >&2; return 1; }
}
