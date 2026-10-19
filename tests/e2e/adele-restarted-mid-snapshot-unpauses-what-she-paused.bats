#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# shellcheck disable=SC2030,SC2031 # bats runs each @test in its own subshell by design
# Feature 13 slice 2 — Adele dies while a service is paused (spec Scenario 15, FR-40, FR-41; research R28, R30, R33).
# Her container is killed from the runner while db is paused and the copy into a snapshot volume runs; she is then
# started again. Her start's recovery pass must, read back by the runner from the daemon and the ledger (P004):
#   - unpause db, which her open pause row names, and end that row with an unpause row;
#   - remove the snapshot volume the copy left, which has no record (a partial), with a snapshot-rm row on
#     `<env>/<id>` whose cause says it was partial.
# What the agent's own `adele env snapshot` printed is not asserted beyond its not being 0: Adele died under it.
#
# Serial (lane.conf): Adele is killed and started again, so every Adele file a neighbour runs would fail while she is
# down. teardown_file starts her whatever happened (as adele-reaps-after-restart-*.bats does), so nothing after this
# file inherits a stopped Adele.
#
# Deterministic as the kill cell is: 30000 empty files (inodes, no data blocks) copied into a tmpfs store of 256 MiB
# (lane grant nested-snapmem), so the copy runs in memory and long enough. The poller kills Adele only once db is
# paused, the snapshot volume exists and the copy helper runs; it reads db's pause again after the kill, and if the
# pause had already ended the cell FAILS saying so. It is never retried.

load helpers
load nested

# adele_started — start Adele if stopped, and wait for her healthcheck, bounded by PLUMBING_TIMEOUT.
adele_started() {
  local state deadline=$((SECONDS + PLUMBING_TIMEOUT))
  timeout "$PLUMBING_TIMEOUT" docker start "$ADELE_CONTAINER" >/dev/null </dev/null || { echo "docker start ${ADELE_CONTAINER} failed" >&2; return 1; }
  while :; do
    state="$(timeout "$PLUMBING_TIMEOUT" docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$ADELE_CONTAINER" 2>&1)"
    [[ "$state" == healthy ]] && return 0
    if ((SECONDS >= deadline)); then
      echo "${ADELE_CONTAINER} is not healthy after ${PLUMBING_TIMEOUT}s (${state})" >&2
      return 1
    fi
    sleep 1
  done
}

setup_file() {
  stamp_check
  stamp_check_adele
}

teardown_file() {
  adele_started || true
}

teardown() {
  [[ -z "${KILLER_STOP:-}" ]] || : >"$KILLER_STOP"
  [[ -z "${KILLER_PID:-}" ]] || wait "$KILLER_PID" 2>/dev/null || true
  adele_started || true
  # The agent's snapshot, if a failed cell left it waiting: bounded by its own PLUMBING_TIMEOUT (exec_in).
  [[ -z "${SNAP_PID:-}" ]] || wait "$SNAP_PID" 2>/dev/null || true
  nested_teardown
}

# kill_adele_mid_copy NAME DB OUT STOP — until STOP exists, poll the daemon; once DB is paused, NAME has a snapshot
# volume and a copy helper runs, kill Adele's container and write "killed SNAPVOL paused_after=BOOL" to OUT (db's
# pause read right after the kill). Bounded by PLUMBING_TIMEOUT; writes "none" when the moment never came.
kill_adele_mid_copy() {
  local name="$1" db="$2" out="$3" stop="$4" deadline=$((SECONDS + PLUMBING_TIMEOUT)) vol
  while [[ ! -e "$stop" ]] && ((SECONDS < deadline)); do
    nested_paused "$db" || continue
    vol="$(nested_snapshot_volumes "$name" | head -1)"
    [[ -n "$vol" && -n "$(nested_copy_helpers "$name")" ]] || continue
    docker kill "$ADELE_CONTAINER" >/dev/null 2>&1 || continue
    printf 'killed %s paused_after=%s\n' "$vol" "$(docker inspect --format '{{.State.Paused}}' "$db" 2>/dev/null)" >"$out"
    return 0
  done
  echo none >"$out"
}

@test "13 Adele killed while a service is paused: her next start unpauses it and removes the partial snapshot, with rows" {
  local db out got vol sid deadline rows snap_out snap_rc
  nested_project adele-dies snapshot-plain
  nested_files snapshot-plain
  env_run c "--text env up --project ${NP_NAME} --grant nested-snapmem"
  assert_status 0
  db="$(nested_container "$NP_NAME" db)"
  env_run c "--text env exec ${NP_NAME} --service db -- sh ${NP_DIR}/fill.sh many"
  assert_status 0
  assert_value filled many

  out="${BATS_TEST_TMPDIR}/killer"
  KILLER_STOP="${BATS_TEST_TMPDIR}/killer.stop"
  kill_adele_mid_copy "$NP_NAME" "$db" "$out" "$KILLER_STOP" >/dev/null 2>&1 3>&- &
  KILLER_PID=$!
  # The agent's snapshot runs in the background: Adele dies under it, and its client may wait out its own bound.
  snap_out="${BATS_TEST_TMPDIR}/snapshot.out"
  (RUN_TIMEOUT="$PLUMBING_TIMEOUT" exec_in -w "$NP_DIR" c notty "adele --text env snapshot ${NP_NAME} db-data" >"$snap_out" 2>&1) >/dev/null 2>&1 3>&- &
  SNAP_PID=$!
  wait "$KILLER_PID" || true
  KILLER_PID=""
  got="$(cat "$out")"
  echo "# 13 Adele mid-snapshot: ${got}" >&3
  [[ "$got" == killed\ * ]] || {
    : >"$KILLER_STOP"
    wait "$SNAP_PID" || true
    SNAP_PID=""
    echo "Adele was never killed mid-copy (${got}): the snapshot ended first; not retried. It printed: $(cat "$snap_out")" >&2
    return 1
  }
  [[ "$got" == *" paused_after=true" ]] ||
    { echo "db's pause had ended by the time Adele was killed (${got}): the moment was missed; not retried" >&2; return 1; }
  read -r _ vol _ <<<"$got"
  sid="$(docker volume inspect --format '{{index .Labels "xyz.ironik.timelike.snapshot"}}' "$vol" 2>/dev/null)" || sid=""
  [[ "$sid" =~ ^s-[0-9a-f]{8}$ ]] || { echo "the partial volume ${vol} carries snapshot label '${sid}'" >&2; return 1; }

  adele_started
  # Her start's pass: db unpaused, read back; the partial volume removed, read back. Polled, bounded as plumbing.
  deadline=$((SECONDS + PLUMBING_TIMEOUT))
  until nested_running_unpaused "$db" 2>/dev/null && [[ "$(nested_snapshot_count "$NP_NAME")" == 0 ]]; do
    ((SECONDS < deadline)) || {
      echo "after Adele's restart: db $(nested_state "$db"); snapshot volumes $(nested_snapshot_volumes "$NP_NAME" | tr '\n' ' ')" >&2
      return 1
    }
    sleep 2
  done
  wait "$SNAP_PID" && snap_rc=0 || snap_rc=$?
  SNAP_PID=""
  echo "# 13 Adele mid-snapshot: the agent's snapshot exited ${snap_rc}: $(tail -1 "$snap_out")" >&3
  [[ "$snap_rc" != 0 ]] || { echo "the snapshot Adele died under exited 0: $(cat "$snap_out")" >&2; return 1; }

  run ledger_rows_for "$NP_NAME"
  assert_status 0
  rows="$output"
  printf '%s\n' "$rows" | grep -q $'^performed\tpause\t' || { echo "no pause row: $rows" >&2; return 1; }
  printf '%s\n' "$rows" | grep -q $'^performed\tunpause\t' || { echo "the recovery pass wrote no unpause row: $rows" >&2; return 1; }
  run ledger_rows_for "${NP_NAME}/${sid}"
  assert_status 0
  printf '%s\n' "$output" | grep $'^performed\tsnapshot-rm\t' | grep -qi 'partial' ||
    { echo "no partial-removed row for ${sid}: $output" >&2; return 1; }
  ! printf '%s\n' "$output" | grep -q $'^performed\tsnapshot\t' || { echo "the cut-short copy has a snapshot row: $output" >&2; return 1; }
}
