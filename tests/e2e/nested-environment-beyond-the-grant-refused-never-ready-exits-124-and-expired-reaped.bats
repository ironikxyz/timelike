#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# shellcheck disable=SC2030,SC2031 # bats runs each @test in its own subshell by design
# Feature 13 slice 0 — the spec's Scenarios 4 and 6 and Item 27 Q4's reaper (the operator's decision: reap in
# slice 0), which no criterion line names alone; each is the edge of criterion 1 or 5 it sits beside:
#   - beyond the grant's instances: exit 4, stdout the grant envelope (12's), naming the grant, the limit and the
#     operator's extend command; nothing created;
#   - a service that never becomes ready: exit 124 at the bound, each service's state, `adele env down` named,
#     and the environment still up (the verdict says it stays);
#   - an environment past its ttl is reaped by Adele's reaper, through the compose provider: a reaped ledger row,
#     and 0 objects left on the daemon, read from the runner;
#   - a missing image: Adele never pulls; exit 3 naming the operator's docker pull (FOR-MENTOR Item 29,
#     provisional), and nothing created.
# Serial (lane.conf): the never-ready cell measures its bound once, quietly, as the send asks.

load helpers
load nested

setup_file() {
  stamp_check
  stamp_check_adele
}

teardown() {
  nested_teardown
  if [[ -n "${NP_OTHER:-}" ]]; then NP_NAME="$NP_OTHER" NP_DIR="$NP_OTHER_DIR" nested_teardown; fi
}

@test "13 a bring-up beyond the grant's instances exits 4 with the grant envelope, and nothing is created" {
  nested_project inst-a basic
  env_run c "--text env up --project ${NP_NAME} --grant nested-one"
  assert_status 0
  NP_OTHER="$NP_NAME"
  NP_OTHER_DIR="$NP_DIR"
  nested_project inst-b basic
  env_run c "--json env up --project ${NP_NAME} --grant nested-one 2>/dev/null"
  assert_status 4
  printf '%s' "$output" | pyq "
import json, sys
d = json.load(sys.stdin)
assert d['status'] == 'grant_required' and d['grant'] == 'nested-one' and d['extend_by'] == 'operator', d
assert d['limit'] == {'name': 'instances', 'allowed': '1', 'needed': '2'}, d
assert d['extend'] == 'docker exec timelike-adele adeled extend nested-one instances 2', d
assert d['performed'] is False, d
"
  [[ "$(nested_counts "$NP_NAME")" == "0 0 0" ]] || { echo "created: $(nested_counts "$NP_NAME")" >&2; return 1; }
}

@test "13 a service that never becomes ready ends at the bound with exit 124, its state, and the environment left up" {
  nested_project never never-ready
  RUN_TIMEOUT="$PLUMBING_TIMEOUT" run_in -w "$NP_DIR" c notty "adele --text env up --project ${NP_NAME} --grant nested --wait 8"
  assert_status 124
  [[ "${lines[1]}" == "verdict: up ${NP_NAME}: not ready within 8 s (0 of 1 ready, read back from the daemon) — it stays up; remove it with adele env down ${NP_NAME}" ]] ||
    { echo "verdict: ${lines[1]}" >&2; return 1; }
  assert_output_has "stuck  running (unhealthy)"
  # The bound the verdict claims, measured once here (serial): the resolution, compose and 8 s, with room. Not
  # assert_within, which reads any 124 as the runner's own timeout; this 124 is the client's.
  ((ELAPSED_MS < 40000)) || { echo "took ${ELAPSED_S}s for an 8 s bound" >&2; return 1; }
  [[ "$(nested_counts "$NP_NAME")" != "0 0 0" ]] || { echo "the environment did not stay up" >&2; return 1; }
}

@test "13 an environment past its ttl is reaped by Adele through the compose provider, read back" {
  nested_project reap basic
  env_run c "--json env up --project ${NP_NAME} --grant nested-reap --ttl 1m"
  assert_status 0
  local id
  id="$(printf '%s' "$output" | grep -oE '"ledger_id": [0-9]+' | grep -oE '[0-9]+' | head -1)"
  [[ -n "$id" ]] || { echo "no ledger id: $output" >&2; return 1; }
  wait_reap "$id" reaped
  [[ "$(reap_field 5)" == *"the daemon's labelled objects"* ]] || { echo "reap: ${REAP_ROW}" >&2; return 1; }
  [[ "$(nested_counts "$NP_NAME")" == "0 0 0" ]] || { echo "left: $(nested_counts "$NP_NAME")" >&2; return 1; }
}

@test "13 a missing image is refused: Adele never pulls, exit 3 names the operator's docker pull, nothing created" {
  nested_project noimage
  nested_compose 'services:
  app:
    image: timelike-no-such-image:never'
  RUN_TIMEOUT="$PLUMBING_TIMEOUT" run_in -w "$NP_DIR" c notty "adele --text env up --project ${NP_NAME} --grant nested 2>&1 >/dev/null"
  assert_status 3
  assert_output_has "image timelike-no-such-image:never is not on the daemon, and Adele never pulls"
  assert_output_has "the operator pulls it on the host: docker pull timelike-no-such-image:never; the agent cannot"
  [[ "$(nested_counts "$NP_NAME")" == "0 0 0" ]]
  run ! docker image inspect timelike-no-such-image:never
}
