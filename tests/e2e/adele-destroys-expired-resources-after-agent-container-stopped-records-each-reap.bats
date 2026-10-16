#!/usr/bin/env bats
# SC-7, feature 004 slice 1 (spec FR-24 to FR-29): "Adele destroys resources whose time-to-live has expired,
# including after the requesting agent's container has stopped, and records each reap".
#
# setup_file asks Adele for six boxes with the grant file's shortest lifetime (1m), under the grant `reap`,
# which no other file uses:
#   - one from a THROWAWAY agent container on Adele's request network, which is then removed: the requesting
#     agent's container is gone before the box expires (the criterion's own case). The compose agent is never
#     stopped, so no other file loses it (lore docker-compose Q004);
#   - two from the agent's own shell, bash -c and bash -lc, each in its own session;
#   - one deleted at the stand-in first, as a provider's console would (FR-26: `gone`);
#   - two the stand-in is made to fail deleting, with its own faults: an HTTP 500, and a dropped connection
#     (cross-stack P005: the failure paths against the stand-in made to fail).
# Each cell then waits for the reap in the ledger the operator reads (`adeled ledger --json`), bounded by
# PLUMBING_TIMEOUT, and asserts no time: a reap waits for a ttl and an interval (lane.conf's rule). "Destroyed"
# is read from the stand-in's own record, never from Adele's word (cross-stack P004).
#
# The fault cells come first: a faulted box fails once per pass with a doubling wait, and the serving reaper
# gives up after 5 failed passes (FR-25). If a slow lane reaches that bound before the cell clears its fault,
# the cell runs the operator's `adeled reap` (FR-28) and says so; either way the reap is recorded, with its cause.
#
# Not here: Adele stopped across an expiry and the stand-in stopped whole, which stop shared containers
# (adele-reaps-after-restart-and-records-standin-unreachable.bats, serial).

# shellcheck disable=SC2153 # REAP_ROW and REAP_ROWS are set by helpers.bash (wait_reap)
load helpers

GRANT=reap
AWAY=tl-sc7-away

setup_file() {
  stamp_check
  stamp_check_adele
  local ids="${BATS_FILE_TMPDIR}/ids" id
  : >"$ids"
  # the requesting agent's container, removed before the box expires
  remove_throwaway "$AWAY"
  start_throwaway "$AWAY" --network timelike_adele-request -e TIMELIKE_ADELE_URL=http://adele:8480 || return 1
  local out
  out="$(timeout "$PLUMBING_TIMEOUT" docker exec -e TIMELIKE_SESSION=sc7-away -e TIMELIKE_AGENT=agent-away "$AWAY" \
    bash -lc "adele --json request standin.box create --grant ${GRANT} --name t-sc7-away --ttl 1m" </dev/null)" ||
    { echo "the throwaway agent's request failed: ${out}" >&2; remove_throwaway "$AWAY"; return 1; }
  remove_throwaway "$AWAY"
  if timeout "$PLUMBING_TIMEOUT" docker inspect "$AWAY" >/dev/null 2>&1; then
    echo "the throwaway agent container ${AWAY} is still there" >&2
    return 1
  fi
  id="$(printf '%s' "$out" | grep -oE '"ledger_id": [0-9]+' | grep -oE '[0-9]+' | head -1)"
  [[ -n "$id" ]] || { echo "no ledger_id from the throwaway agent: ${out}" >&2; return 1; }
  echo "away=${id}" >>"$ids"

  id="$(box_request c sc7-c agent-c "$GRANT" t-sc7-own-c)" || return 1
  echo "own_c=${id}" >>"$ids"
  id="$(box_request lc sc7-lc - "$GRANT" t-sc7-own-lc)" || return 1
  echo "own_lc=${id}" >>"$ids"
  id="$(box_request c sc7-gone - "$GRANT" t-sc7-gone)" || return 1
  echo "gone=${id}" >>"$ids"
  standin_cmd delete t-sc7-gone >/dev/null || { echo "the stand-in did not delete t-sc7-gone" >&2; return 1; }
  id="$(box_request c sc7-error - "$GRANT" t-sc7-error)" || return 1
  echo "error=${id}" >>"$ids"
  standin_cmd fault t-sc7-error error >/dev/null || return 1
  id="$(box_request c sc7-drop - "$GRANT" t-sc7-drop)" || return 1
  echo "drop=${id}" >>"$ids"
  standin_cmd fault t-sc7-drop drop >/dev/null || return 1
}

teardown_file() {
  remove_throwaway "$AWAY"
  standin_cmd fault t-sc7-error clear >/dev/null 2>&1 || true
  standin_cmd fault t-sc7-drop clear >/dev/null 2>&1 || true
}

id_of() { sed -n "s/^$1=//p" "${BATS_FILE_TMPDIR}/ids"; }

holds() { standin_names | grep -qx "$1"; }

# check_reaped REF BOX SESSION AGENT — REF's ending is `reaped`, for SESSION and AGENT ("-": none), its
# cause says the record was read back, and the stand-in's own record no longer holds BOX.
check_reaped() {
  local ref="$1" box="$2" session="$3" agent="$4"
  wait_reap "$ref" reaped gone || return 1
  [[ "$(reap_field 1)" == reaped ]] || { echo "ledger #${ref} ended '$(reap_field 1)', want reaped: ${REAP_ROW}" >&2; return 1; }
  [[ "$(reap_field 2)" == "$session" && "$(reap_field 3)" == "$agent" ]] ||
    { echo "the reap row names session/agent '$(reap_field 2)/$(reap_field 3)', want ${session}/${agent}" >&2; return 1; }
  [[ "$(reap_field 5)" == *"read back"* ]] || { echo "the cause does not say the record was read back: $(reap_field 5)" >&2; return 1; }
  if holds "$box"; then
    echo "the ledger says reaped, yet the stand-in still holds ${box} (P004)" >&2
    return 1
  fi
}

# wait_or_operator REF — after a fault is cleared: the serving reaper retries; if it has already given up
# (a slow lane: 5 failed passes before the cell cleared the fault), the operator's command reaps it.
wait_or_operator() {
  local ref="$1"
  REAP_ROWS="$(reap_rows "$ref")" || return 1
  if [[ "$REAP_ROWS" == *"gave up after"* ]]; then
    echo "# ledger #${ref} was given up before its fault was cleared; the operator's adeled reap runs" >&3
    run adeled reap
    assert_output_has "reaped "
  fi
}

# check_fault_then_reaped_with_fallback REF BOX WHAT — REF fails while its fault holds: a reap-failed row whose
# cause names WHAT and Adele's container, 3 attempts, the box still held; once cleared, it is reaped.
check_fault_then_reaped_with_fallback() {
  local ref="$1" box="$2" what="$3"
  wait_reap "$ref" reap-failed || return 1
  [[ "$(reap_field 5)" == *"from Adele's container"* && "$(reap_field 5)" == *"$what"* ]] ||
    { echo "the failure's cause does not name '${what}' from Adele's container: $(reap_field 5)" >&2; return 1; }
  [[ "$(reap_field 4)" == 3 ]] || { echo "attempts $(reap_field 4), want 3 per pass" >&2; return 1; }
  holds "$box" || { echo "a failed reap, yet the stand-in no longer holds ${box}" >&2; return 1; }
  standin_cmd fault "$box" clear >/dev/null || return 1
  wait_or_operator "$ref" || return 1
  wait_reap "$ref" reaped gone || return 1
  [[ "$(reap_field 1)" == reaped ]] || { echo "after the fault was cleared, ledger #${ref} ended '$(reap_field 1)', want reaped" >&2; return 1; }
  if holds "$box"; then
    echo "reaped, yet the stand-in still holds ${box}" >&2
    return 1
  fi
}

@test "SC-7 004 the stand-in erroring: the reap is recorded as reap-failed with its cause, and reaped once it recovers" {
  check_fault_then_reaped_with_fallback "$(id_of error)" t-sc7-error "500"
}

@test "SC-7 004 the stand-in dropping the connection: recorded as reap-failed with its cause, and reaped once it recovers" {
  check_fault_then_reaped_with_fallback "$(id_of drop)" t-sc7-drop "the delete failed"
}


@test "SC-7 004 Adele destroys a box whose ttl expired after the requesting agent's container was removed, and records the reap" {
  check_reaped "$(id_of away)" t-sc7-away sc7-away agent-away
}

@test "SC-7 004 Adele destroys an expired box asked for from the agent's own shell, and records the reap with its session and agent [bash -c]" {
  check_reaped "$(id_of own_c)" t-sc7-own-c sc7-c agent-c
}

@test "SC-7 004 Adele destroys an expired box asked for from the agent's own shell, and records the reap with its session [bash -lc]" {
  check_reaped "$(id_of own_lc)" t-sc7-own-lc sc7-lc -
}

@test "SC-7 004 a box already gone at the stand-in is recorded as gone, once, and never retried" {
  local ref
  ref="$(id_of gone)"
  wait_reap "$ref" reaped gone reap-failed || return 1
  [[ "$(reap_field 1)" == gone && "$(reap_field 5)" == *"already gone"* ]] ||
    { echo "ledger #${ref}: ${REAP_ROW}, want gone (already gone)" >&2; return 1; }
  sleep 12 # two more reaper intervals (5 s each): nothing else may be recorded for it
  REAP_ROWS="$(reap_rows "$ref")" || return 1
  [[ "$(printf '%s\n' "$REAP_ROWS" | grep -c .)" -eq 1 ]] || { echo "more than one reap row for ledger #${ref}: ${REAP_ROWS}" >&2; return 1; }
}

@test "SC-7 004 the operator reads each reap in the ledger: what was destroyed, under which grant, for which session" {
  local ref
  ref="$(id_of own_c)"
  wait_reap "$ref" reaped gone || return 1
  run adeled ledger
  [[ "$status" -eq 0 ]] || { echo "adeled ledger exited $status: $output" >&2; return 1; }
  assert_output_has "reaped grant=${GRANT} session=sc7-c agent=agent-c standin.box.delete resource=t-sc7-own-c of=#${ref} attempts=1"
}

@test "SC-7 004 the agent cannot reap or alter the ledger: no adeled, and the request interface has no reap or ledger route [bash -c]" {
  run_in c notty 'command -v adeled; echo "found_rc=$?"'
  assert_output_has "found_rc=1"
  # shellcheck disable=SC2016 # expanded by python in the container
  run_in c notty '/opt/timelike/python/bin/python3 -I -c "
import urllib.request, urllib.error
for method, path in ((\"POST\", \"/v1/reap\"), (\"POST\", \"/v1/ledger\"), (\"DELETE\", \"/v1/requests\")):
    req = urllib.request.Request(\"http://adele:8480\" + path, data=b\"{}\" if method == \"POST\" else None, method=method)
    try:
        urllib.request.urlopen(req, timeout=10)
        print(method, path, \"answered 2xx\")
    except urllib.error.HTTPError as e:
        print(method, path, e.code)
"'
  [[ "$status" -eq 0 ]] || { echo "the probe exited $status: $output" >&2; return 1; }
  assert_output_has "POST /v1/reap 404"
  assert_output_has "POST /v1/ledger 404"
  assert_output_has "DELETE /v1/requests 405"
}
