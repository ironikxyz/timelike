#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# shellcheck disable=SC2030,SC2031 # bats runs each @test in its own subshell by design
# Feature 13 slice 2 — nothing is left behind (spec Scenarios 14 and 15, FR-39, FR-40, FR-41; research R25, R26,
# R28, R30, R33), read from the daemon and the ledger by the runner (cross-stack P004):
#   - the copy helper killed mid-copy (the runner finds it by its name and command, R25, and `docker kill`s it):
#     snapshot exits 1 naming the helper's end; the partial snapshot volume is gone, read back; db is unpaused and
#     running, read back, and its pause row is ended by an unpause row;
#   - an environment with a snapshot whose session has ended is collected: the snapshot volume goes with it, read
#     back, and the snapshot's row is ended by a reaped row.
# Adele's own death mid-snapshot stops her for everyone, so it is the serial file's
# (adele-restarted-mid-snapshot-unpauses-what-she-paused.bats).
#
# The kill is made deterministic without big fixtures (the host is disk-bound, cross-stack P006): the volume holds
# 30000 EMPTY files (inodes, no data blocks), and the environment's grant, nested-snapmem, holds snapshots in a tmpfs
# of 256 MiB, so the copy works in memory and its time is spent creating, owning and timing 30000 entries and
# digesting both trees. A poller on the runner kills the helper the moment it appears. If the snapshot finished before
# the kill, the cell FAILS saying so: it is never retried, which would hide a race behind a pass.
# Not serial (lane.conf): the poller kills only a helper named for this cell's own environment.

load helpers
load nested

setup_file() {
  stamp_check
  stamp_check_adele
}

teardown() {
  [[ -z "${KILLER_STOP:-}" ]] || : >"$KILLER_STOP"
  [[ -z "${KILLER_PID:-}" ]] || wait "$KILLER_PID" 2>/dev/null || true
  nested_teardown
}

# kill_copy_helper NAME DB OUT STOP — until STOP exists, poll the daemon for NAME's copy helper; kill the first one
# seen and write "killed ID paused=BOOL" (db's pause, read just before the kill) to OUT. Bounded by PLUMBING_TIMEOUT;
# writes "none" when it saw no copy helper. Run in the background, its output to OUT only.
kill_copy_helper() {
  local name="$1" db="$2" out="$3" stop="$4" deadline=$((SECONDS + PLUMBING_TIMEOUT)) id paused
  while [[ ! -e "$stop" ]] && ((SECONDS < deadline)); do
    for id in $(nested_copy_helpers "$name"); do
      paused="$(docker inspect --format '{{.State.Paused}}' "$db" 2>/dev/null)"
      if docker kill "$id" >/dev/null 2>&1; then
        printf 'killed %s paused=%s\n' "$id" "$paused" >"$out"
        return 0
      fi
    done
  done
  echo none >"$out"
}

@test "13 the copy helper killed mid-copy: snapshot exits 1 naming it, the partial snapshot is gone, db is unpaused" {
  local db out rows
  nested_project kill snapshot-plain
  nested_files snapshot-plain
  env_run c "--text env up --project ${NP_NAME} --grant nested-snapmem"
  assert_status 0
  db="$(nested_container "$NP_NAME" db)"
  env_run c "--text env exec ${NP_NAME} --service db -- sh ${NP_DIR}/fill.sh many"
  assert_status 0
  assert_value filled many

  out="${BATS_TEST_TMPDIR}/killer"
  KILLER_STOP="${BATS_TEST_TMPDIR}/killer.stop"
  kill_copy_helper "$NP_NAME" "$db" "$out" "$KILLER_STOP" >/dev/null 2>&1 3>&- &
  KILLER_PID=$!
  env_run c "--text env snapshot ${NP_NAME} db-data 2>&1"
  : >"$KILLER_STOP"
  wait "$KILLER_PID" || true
  KILLER_PID=""
  if [[ "$status" == 0 ]]; then
    echo "the snapshot finished before the runner could kill its copy helper (killer: $(cat "$out" 2>/dev/null)): 30000 entries were not enough on this host; not retried. Output: $output" >&2
    return 1
  fi
  [[ "$(cat "$out")" == killed\ * ]] || { echo "no copy helper was killed ($(cat "$out")); snapshot exited ${status}: $output" >&2; return 1; }
  echo "# 13 kill: $(cat "$out")" >&3
  assert_status 1
  printf '%s\n' "$output" | grep -qi 'helper' || { echo "the verdict does not name the helper: $output" >&2; return 1; }

  # Read back: no partial snapshot volume, no copy helper, db running and unpaused.
  [[ "$(nested_snapshot_count "$NP_NAME")" == 0 ]] || { echo "partial snapshot left: $(nested_snapshot_volumes "$NP_NAME" | tr '\n' ' ')" >&2; return 1; }
  [[ -z "$(nested_copy_helpers "$NP_NAME")" ]] || { echo "a copy helper still runs: $(nested_copy_helpers "$NP_NAME")" >&2; return 1; }
  nested_running_unpaused "$db"
  run ledger_rows_for "$NP_NAME"
  assert_status 0
  rows="$output"
  printf '%s\n' "$rows" | grep -q $'^performed\tpause\t' || { echo "no pause row: $rows" >&2; return 1; }
  printf '%s\n' "$rows" | grep -q $'^performed\tunpause\t' || { echo "the pause was not ended by an unpause row: $rows" >&2; return 1; }
  ! printf '%s\n' "$rows" | grep -q $'^performed\tsnapshot\t' || { echo "a killed snapshot has a performed row: $rows" >&2; return 1; }
}

@test "13 an environment whose session has ended is collected with its snapshots, each ended in the ledger" {
  local sid snapvol
  nested_project collect snapshot-plain
  nested_files snapshot-plain
  nested_session snap-collect
  env_run c "--text env up --project ${NP_NAME} --grant nested"
  assert_status 0
  env_run c "--json env snapshot ${NP_NAME} db-data 2>/dev/null"
  assert_status 0
  sid="$(printf '%s' "$output" | pyq "
import json, sys
print(json.load(sys.stdin)['snapshot']['id'])")" || return 1
  snapvol="${NP_NAME}-snap-${sid#s-}"
  [[ "$(docker volume inspect --format '{{index .Labels "xyz.ironik.timelike.session"}}' "$snapvol")" == "$NP_SESSION" ]] ||
    { echo "${snapvol} is not labelled with the session ${NP_SESSION}" >&2; return 1; }

  RUN_TIMEOUT="$PLUMBING_TIMEOUT" run_in -e "TIMELIKE_SESSION=${NP_SESSION}" -w "$NP_DIR" c notty \
    'adele --text session end; echo "rc1=$?"; adele --text env collect; echo "rc2=$?"'
  assert_status 0
  assert_value rc1 0
  assert_value rc2 0
  nested_collected "$NP_NAME" "session ${NP_SESSION} ended at "
  echo "# 13 collect with a snapshot: ${NP_NAME} was collected by ${NP_COLLECTED_BY}" >&3
  run docker volume inspect "$snapvol"
  [[ "$status" != 0 ]] || { echo "${snapvol} outlived its environment" >&2; return 1; }
  run ledger_rows_for "${NP_NAME}/${sid}"
  assert_status 0
  printf '%s\n' "$output" | grep -q $'^reaped\tdelete\t' || { echo "no reaped row for ${sid}: $output" >&2; return 1; }
}
