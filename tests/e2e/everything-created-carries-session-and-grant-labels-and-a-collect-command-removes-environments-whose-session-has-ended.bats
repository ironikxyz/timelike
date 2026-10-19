#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# shellcheck disable=SC2030,SC2031 # bats runs each @test in its own subshell by design
# Feature 13 slice 1, criterion 8 — "Everything created carries session and grant labels, and a collect command
# removes environments whose session has ended" (send 13-rev17's slice 1; spec Scenarios 8 and 11, FR-23, FR-26 to
# FR-29; research R16, R18, R19, R21, R22).
#
# Read from the daemon and the ledger by the runner, never from a verdict alone (cross-stack P004):
#   - a compose project with a build, a named volume and an image service, brought up under a session id of the
#     cell's own: every container, network, volume and image labelled with the environment carries that session,
#     the grant it came up under, and the requester Adele read from the daemon (the agent container's own id), and
#     each of the four kinds is there;
#   - `adele session end` ends that session once (a second says it was already ended, exit 0), and `adele env collect`
#     then removes the environment: nothing labelled with it is left, and the ledger has a reaped row whose cause is
#     the session's end;
#   - rule (a): an environment brought up by a second agent container (a throwaway, labelled and networked as the
#     agent is, R22) is collected once that container no longer exists, with that cause;
#   - collect with nothing of the cell's own to collect exits 0.
# Not serial (lane.conf): a collect pass runs over every live environment but removes only those of ended sessions,
# and the only sessions these cells end are their own (NP_SESSION), as is the only throwaway agent they remove.
# Adele's reaper runs the same pass on its 5 s tick, so the pass that removed an environment may be the reaper's;
# nested_collected says which, and asserts the ledger and the daemon either way.

load helpers
load nested

setup_file() {
  stamp_check
  stamp_check_adele
}

teardown() {
  remove_throwaway "${NP_TW:-}"
  nested_teardown
}

check_labels_then_collect() {
  local style="$1" agent objects kind want_kinds
  nested_project "labels-${style}" build
  nested_files build
  nested_session "labels-${style}"
  env_run "$style" "--text env up --project ${NP_NAME} --grant nested"
  assert_status 0
  [[ "${lines[1]}" == "verdict: up ${NP_NAME}: 2 running with no readiness check in "* ]] || { echo "verdict: ${lines[1]}" >&2; return 1; }
  assert_output_has "built app: ${NP_NAME}-app:"
  assert_output_has " s (nothing pulled)"

  # Every object, of all four kinds, carries the session, the grant and the requester: the agent's own container.
  agent="$(docker inspect --format '{{.Id}}' "$AGENT_CONTAINER")"
  objects="$(nested_objects "$NP_NAME")" || return 1
  for kind in container network volume image; do
    printf '%s\n' "$objects" | grep -q "^${kind}"$'\t' || { printf 'no %s labelled %s; objects:\n%s\n' "$kind" "$NP_NAME" "$objects" >&2; return 1; }
  done
  [[ "$(printf '%s\n' "$objects" | grep -c '^container')" == 2 ]] || { printf 'containers:\n%s\n' "$objects" >&2; return 1; }
  want_kinds="$(printf '%s\n' "$objects" | awk -F'\t' -v s="$NP_SESSION" -v a="$agent" '$3 != s || $4 != "nested" || $5 != a')"
  [[ -z "$want_kinds" ]] || { printf 'objects not labelled session %s, grant nested, requester %s:\n%s\n' "$NP_SESSION" "$agent" "$want_kinds" >&2; return 1; }

  # The session ends once; a second end says so and records nothing; then one collection pass, now.
  RUN_TIMEOUT="$PLUMBING_TIMEOUT" run_in -e "TIMELIKE_SESSION=${NP_SESSION}" -w "$NP_DIR" "$style" notty \
    'adele --text session end; echo "rc1=$?"; adele --text session end; echo "rc2=$?"; adele --text env collect; echo "rc3=$?"'
  assert_status 0
  assert_value rc1 0
  assert_value rc2 0
  assert_value rc3 0
  assert_output_has "verdict: session ${NP_SESSION} ended at "
  assert_output_has "verdict: session ${NP_SESSION} was already ended at "
  assert_output_has "; nothing new recorded"
  assert_output_has "verdict: collect: "
  nested_collected "$NP_NAME" "session ${NP_SESSION} ended at "
  echo "# 13 collect (${style}): ${NP_NAME} was collected by ${NP_COLLECTED_BY}" >&3
  # The end itself is a ledger row of its own: capability adele.session, the session as its resource.
  run ledger_rows_for "$NP_SESSION"
  assert_status 0
  [[ "$(printf '%s\n' "$output" | grep -c $'^performed\tend\t')" == 1 ]] || { echo "the session's rows: $output" >&2; return 1; }
}
@test "13 everything created carries session and grant labels, and a collect command removes environments whose session has ended [bash -c]" { check_labels_then_collect c; }
@test "13 everything created carries session and grant labels, and a collect command removes environments whose session has ended [bash -lc]" { check_labels_then_collect lc; }

@test "13 an environment whose agent container no longer exists is collected, with that cause" {
  local session
  nested_project gone
  nested_compose 'services:
  app:
    image: ${FIXTURE_IMAGE:?}
    command: ["sleep", "infinity"]'
  nested_session gone
  session="$NP_SESSION"
  NP_SESSION=""
  nested_throwaway_agent "tl-e2e-agent-${NESTED_ID}-$$-${RANDOM}" "$session"
  # The second agent brings the environment up; Adele reads it, by its address, as the requester (R18).
  tw_run "adele --text env up --project ${NP_NAME} --grant nested"
  assert_status 0
  [[ "${lines[1]}" == "verdict: up ${NP_NAME}: 1 running with no readiness check in "* ]] || { echo "verdict: ${lines[1]}" >&2; return 1; }
  [[ "$output" != *"requester: unknown"* ]] || { echo "Adele did not find the throwaway agent: $output" >&2; return 1; }
  [[ "$(docker inspect --format '{{index .Config.Labels "xyz.ironik.timelike.requester"}}' "$(nested_container "$NP_NAME" app)")" == "$NP_TW_ID" ]] ||
    { echo "requester label: $(docker inspect --format '{{json .Config.Labels}}' "$(nested_container "$NP_NAME" app)"); throwaway ${NP_TW_ID}" >&2; return 1; }

  # The container goes; the agent's collect removes what it brought up.
  remove_throwaway "$NP_TW"
  run docker inspect "$NP_TW"
  [[ "$status" != 0 ]] || { echo "the throwaway agent ${NP_TW} still exists" >&2; return 1; }
  env_run c "--text env collect"
  assert_status 0
  assert_output_has "verdict: collect: "
  nested_collected "$NP_NAME" "session ${session}'s agent container ${NP_TW_ID:0:12} no longer exists"
  echo "# 13 collect (container gone): ${NP_NAME} was collected by ${NP_COLLECTED_BY}" >&3
}

@test "13 collect with nothing of this cell's own to collect exits 0" {
  nested_project idle
  env_run c "--text env collect"
  assert_status 0
  # Another cell's ended session may be collected by this same pass (or the reaper's), so the count is not asserted,
  # nor the verdict's end: naming what it collected can take it past rule 13's 200 columns, where it is cut.
  [[ "${lines[1]}" =~ ^verdict:\ collect:\ [0-9]+\ collected ]] || { echo "verdict: ${lines[1]}" >&2; return 1; }
  [[ "$output" != *"collected ${NP_NAME}"* ]] || { echo "collected this cell's own name: $output" >&2; return 1; }
}
