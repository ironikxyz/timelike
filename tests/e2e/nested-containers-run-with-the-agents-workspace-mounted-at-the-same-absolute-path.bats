#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# shellcheck disable=SC2030,SC2031 # bats runs each @test in its own subshell by design
# Feature 13 slice 0, criterion 2 — "The Infra provider (the local Docker daemon) runs the nested environment's
# containers with the agent's workspace mounted at the same absolute path" (send 13-rev17; spec FR-13; research
# R9; lore docker-compose P001 item 1: a bind source is resolved by the daemon, on the host).
#
# The fixture's db binds its project directory at the same path. Checked three ways, none of them Adele's word:
#   - the daemon's own record of the nested container's mounts: a bind whose source and destination are the
#     project's absolute path;
#   - a file the agent writes there is read inside the nested container, and one the nested container writes
#     is read by the agent: the same directory, not a copy;
#   - the runner, which has the lane's workspace at that same path on the host, reads the agent's file too:
#     the host path the daemon resolved is the agent's path.
# And the agent's own workspace mount is a bind of that host directory at that path.

load helpers
load nested

setup_file() {
  stamp_check
  stamp_check_adele
}

teardown() { nested_teardown; }

@test "13 the agent's workspace is a bind of the host's directory at the same absolute path" {
  nested_ready
  local m
  m="$(docker inspect --format '{{range .Mounts}}{{if eq .Type "bind"}}{{.Source}}={{.Destination}};{{end}}{{end}}' "$AGENT_CONTAINER")"
  [[ "$m" == *"${TIMELIKE_WORKSPACE}=${TIMELIKE_WORKSPACE};"* ]] || { echo "agent's binds: $m" >&2; return 1; }
  run_in c notty 'printf "%s\n" "$TIMELIKE_WORKSPACE"'
  assert_status 0
  [[ "$output" == "$TIMELIKE_WORKSPACE" ]]
}

check_same_path() {
  local style="$1" tok_a tok_n db
  nested_project "path-${style}" basic
  env_run "$style" "--text env up --project ${NP_NAME} --grant nested"
  assert_status 0
  db="$(nested_container "$NP_NAME" db)"
  local m
  m="$(docker inspect --format '{{range .Mounts}}{{if eq .Type "bind"}}{{.Source}}={{.Destination}};{{end}}{{end}}' "$db")"
  [[ "$m" == *"${NP_DIR}=${NP_DIR};"* ]] || { echo "the nested container's binds: $m (want ${NP_DIR} at itself)" >&2; return 1; }
  tok_a="agent-$$-${RANDOM}"
  tok_n="nested-$$-${RANDOM}"
  run_in "$style" notty "printf '%s' '${tok_a}' > '${NP_DIR}/from-agent'"
  assert_status 0
  # The nested container reads the agent's file at the same path, and writes one as the agent's uid.
  [[ "$(timeout "$PLUMBING_TIMEOUT" docker exec -u 1000 "$db" cat "${NP_DIR}/from-agent")" == "$tok_a" ]]
  timeout "$PLUMBING_TIMEOUT" docker exec -u 1000 "$db" sh -c "printf '%s' '${tok_n}' > '${NP_DIR}/from-nested'"
  run_in "$style" notty "cat '${NP_DIR}/from-nested'"
  assert_status 0
  [[ "$output" == "$tok_n" ]] || { echo "the agent read: $output" >&2; return 1; }
  # The host's directory at that path holds the agent's file: the runner has the lane's workspace mounted from it.
  [[ "$(cat "${NP_DIR}/from-agent")" == "$tok_a" ]] || { echo "the host path does not hold the agent's file" >&2; return 1; }
}
@test "13 the daemon runs the nested environment's containers with the agent's workspace mounted at the same absolute path [bash -c]" { check_same_path c; }
@test "13 the daemon runs the nested environment's containers with the agent's workspace mounted at the same absolute path [bash -lc]" { check_same_path lc; }
