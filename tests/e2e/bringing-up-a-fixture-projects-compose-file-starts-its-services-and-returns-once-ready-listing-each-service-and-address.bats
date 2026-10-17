#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# shellcheck disable=SC2030,SC2031 # bats runs each @test in its own subshell by design
# Feature 13 slice 0, criterion 1 — "Bringing up a fixture project's compose file from inside the agent container
# starts its services and returns once they are ready, with a verdict listing each service and its address"
# (send 13-rev17; spec FR-1..FR-3, FR-11; research R7).
#
# From inside the agent, in a project in its workspace, under bash -c and bash -lc: `adele env up` exits 0 once
# each of the fixture's three services is ready by its own kind (db healthy, web's port accepting, job completed),
# and its verdict and lines name each service and the address of each port. Then each address is reached FROM
# THE AGENT'S CONTAINER (cross-stack P001): the readiness probe is the client's own, so a second, independent
# connection checks it. The daemon is read from the runner for what Adele said she started (cross-stack P004).

load helpers
load nested

setup_file() {
  stamp_check
  stamp_check_adele
}

teardown() { nested_teardown; }

check_up_ready() {
  local style="$1"
  nested_project "up-${style}" basic
  env_run "$style" "--text env up --project ${NP_NAME} --grant nested"
  assert_status 0
  [[ "${lines[1]}" == "verdict: up ${NP_NAME}: 3 ready in "* ]] || { echo "verdict: ${lines[1]}" >&2; return 1; }
  assert_output_has "read back, ports probed from the agent container · local: no cost · host git enforced"
  assert_output_has "db  ready (healthy)"
  assert_output_has "web  ready (running, ports accept)  web.${NP_NAME}:8080"
  assert_output_has "job  completed (exit 0)"
  # The address, reached again from the agent's container, independently of the client's own probe.
  run_in "$style" notty "$AGENT_PY -I -c 'import urllib.request as u; print(u.urlopen(\"http://web.${NP_NAME}:8080/\", timeout=10).status)'"
  assert_status 0
  [[ "$output" == 200 ]] || { echo "GET web.${NP_NAME}:8080 from the agent: $output" >&2; return 1; }
  # The daemon has what the verdict says: db running and healthy, web running, job exited 0, each labelled.
  local db web job
  db="$(nested_container "$NP_NAME" db)"
  web="$(nested_container "$NP_NAME" web)"
  job="$(nested_container "$NP_NAME" job)"
  [[ -n "$db" && -n "$web" && -n "$job" ]] || { echo "containers: db=$db web=$web job=$job" >&2; return 1; }
  [[ "$(docker inspect --format '{{.State.Status}} {{.State.Health.Status}}' "$db")" == "running healthy" ]]
  [[ "$(docker inspect --format '{{.State.Status}}' "$web")" == running ]]
  [[ "$(docker inspect --format '{{.State.Status}} {{.State.ExitCode}}' "$job")" == "exited 0" ]]
}
@test "13 bringing up a fixture project's compose file starts its services and returns once ready, listing each service and address [bash -c]" { check_up_ready c; }
@test "13 bringing up a fixture project's compose file starts its services and returns once ready, listing each service and address [bash -lc]" { check_up_ready lc; }

@test "13 the verdict's JSON lists each service, its readiness and its addresses, and the performed ledger row" {
  nested_project up-json basic
  env_run c "--json env up --project ${NP_NAME} --grant nested"
  assert_status 0
  printf '%s' "$output" | pyq "
import json, sys
d = json.load(sys.stdin)
assert d['ready'] is True and d['outcome'] == 'performed' and d['grant'] == 'nested', d
assert d['vantage'] == 'from the agent container' and d['host_git'] == 'enforced', d
s = {x['service']: x for x in d['services']}
assert set(s) == {'db', 'web', 'job'}, s
assert s['web']['addresses'] == ['web.${NP_NAME}:8080'] and s['db']['ready'] == 'ready' and s['job']['ready'] == 'completed', s
assert isinstance(d['ledger_id'], int) and json.loads(d['undo'])['action'] == 'down', d
t = d['adele_timings']
assert {'resolve_ms', 'lock_wait_ms', 'compose_ms', 'adele_ms', 'sandbox_ms'} <= set(t), t
print('# 13 bring-up (json): %.1f s from the agent; Adele: resolve %d ms (sandbox create %d, start %d, wait %d, logs %d),'
      ' lock wait %d ms, compose %d ms (measured, not asserted)' % (d['seconds'], t['resolve_ms'], t['sandbox_ms']['create'],
      t['sandbox_ms']['start'], t['sandbox_ms']['wait'], t['sandbox_ms']['logs'], t['lock_wait_ms'], t['compose_ms']))
" >&3
  run ledger_rows_for "$NP_NAME"
  assert_status 0
  [[ "${lines[0]}" == performed$'\t'up$'\t'* ]] || { echo "ledger: $output" >&2; return 1; }
}
