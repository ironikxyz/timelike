#!/usr/bin/env bats
# SC-7, feature 004 slice 1 (Scenarios 6 and 7; spec FR-24 to FR-26): the reaper's two cases that stop a
# shared container, so this file is `serial` in lane.conf: it runs alone, after every other file.
#   - Adele restarts with expired boxes outstanding: they are reaped after the restart, from the ledger, not
#     from her memory;
#   - the stand-in is unreachable during a reap: the reap is recorded as reap-failed naming the cause, from
#     Adele's container (cross-stack P001), and reaped once the stand-in is back.
#
# One timeline serves both, so the expiry is waited for once. setup_file asks for two boxes with the grant file's
# shortest lifetime (1m) under the grant `reap-serial`, stops Adele, waits past the expiry (a wait on a ttl:
# nothing asserts its time), stops the stand-in, and starts Adele again. Her first pass finds both rows in
# the ledger and cannot reach the stand-in; the cells then start the stand-in and wait for the reaps.
# teardown_file starts both containers whatever happened, so nothing after this file inherits a stopped
# Adele or stand-in (lore docker-compose Q004).

# shellcheck disable=SC2153 # REAP_ROW and REAP_ROWS are set by helpers.bash (wait_reap)
load helpers

GRANT=reap-serial

# started CONTAINER — start it if stopped, and wait for its healthcheck, bounded by PLUMBING_TIMEOUT.
started() {
  local c="$1" state deadline=$((SECONDS + PLUMBING_TIMEOUT))
  timeout "$PLUMBING_TIMEOUT" docker start "$c" >/dev/null </dev/null || { echo "docker start ${c} failed" >&2; return 1; }
  while :; do
    state="$(timeout "$PLUMBING_TIMEOUT" docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$c" 2>&1)"
    [[ "$state" == healthy ]] && return 0
    if ((SECONDS >= deadline)); then
      echo "${c} is not healthy after ${PLUMBING_TIMEOUT}s (${state})" >&2
      return 1
    fi
    sleep 1
  done
}

stopped() {
  timeout "$PLUMBING_TIMEOUT" docker stop "$1" >/dev/null </dev/null || { echo "docker stop $1 failed" >&2; return 1; }
}

setup_file() {
  stamp_check
  stamp_check_adele
  local ids="${BATS_FILE_TMPDIR}/ids" id created
  : >"$ids"
  created=$SECONDS
  id="$(box_request c sc7-restart agent-r "$GRANT" t-sc7-restart)" || return 1
  echo "restart=${id}" >>"$ids"
  id="$(box_request lc sc7-unreach - "$GRANT" t-sc7-unreach)" || return 1
  echo "unreach=${id}" >>"$ids"
  stopped "$ADELE_CONTAINER" || return 1
  # past both expiries (1m), with a margin for the clock's second boundary
  while ((SECONDS - created < 70)); do sleep 2; done
  stopped "$STANDIN_CONTAINER" || return 1
  date -u +%Y-%m-%dT%H:%M:%SZ >"${BATS_FILE_TMPDIR}/restarted"
  started "$ADELE_CONTAINER" || return 1
}

teardown_file() {
  started "$STANDIN_CONTAINER" || true
  started "$ADELE_CONTAINER" || true
}

id_of() { sed -n "s/^$1=//p" "${BATS_FILE_TMPDIR}/ids"; }

holds() { standin_names | grep -qx "$1"; }

# reaped_or_operator REF BOX — wait for REF's ending to be `reaped`; if the serving reaper had given up
# (five failed passes on a slow lane), the operator's `adeled reap` runs first and says so.
reaped_or_operator() {
  local ref="$1" box="$2"
  REAP_ROWS="$(reap_rows "$ref")" || return 1
  if [[ "$REAP_ROWS" == *"gave up after"* ]]; then
    echo "# ledger #${ref} was given up while the stand-in was down; the operator's adeled reap runs" >&3
    run adeled reap
  fi
  wait_reap "$ref" reaped gone || return 1
  [[ "$(reap_field 1)" == reaped && "$(reap_field 5)" == *"read back"* ]] ||
    { echo "ledger #${ref} ended: ${REAP_ROW}, want reaped (read back)" >&2; return 1; }
  if holds "$box"; then
    echo "the ledger says reaped, yet the stand-in still holds ${box} (P004)" >&2
    return 1
  fi
}

@test "SC-7 004 the stand-in unreachable during a reap: recorded as reap-failed naming it from Adele's container, then reaped when it is back" {
  local ref
  ref="$(id_of unreach)"
  wait_reap "$ref" reap-failed || return 1
  [[ "$(reap_field 5)" == *"could not be read from Adele's container"* ]] ||
    { echo "the cause does not say the stand-in could not be reached from Adele's container: $(reap_field 5)" >&2; return 1; }
  started "$STANDIN_CONTAINER" || return 1
  holds t-sc7-unreach || { echo "the stand-in's record lost t-sc7-unreach across its restart" >&2; return 1; }
  reaped_or_operator "$ref" t-sc7-unreach
}

@test "SC-7 004 Adele restarted with an expired box outstanding reaps it after the restart, from the ledger" {
  local ref since
  ref="$(id_of restart)"
  started "$STANDIN_CONTAINER" || return 1
  reaped_or_operator "$ref" t-sc7-restart || return 1
  [[ "$(reap_field 2)" == sc7-restart && "$(reap_field 3)" == agent-r ]] ||
    { echo "the reap row names $(reap_field 2)/$(reap_field 3), want sc7-restart/agent-r" >&2; return 1; }
  # The restarted Adele did it: her log since the restart has this box's reap lines.
  since="$(cat "${BATS_FILE_TMPDIR}/restarted")"
  run timeout "$PLUMBING_TIMEOUT" docker logs --since "$since" "$ADELE_CONTAINER"
  assert_output_has "adeled: reap: "
  assert_output_has "t-sc7-restart (ledger #${ref}, grant ${GRANT}, session sc7-restart, agent agent-r)"
}
