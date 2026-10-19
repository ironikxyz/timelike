#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# shellcheck disable=SC2030,SC2031 # bats runs each @test in its own subshell by design
# Feature 13 slice 2 — the failures a snapshot or a restore can meet, which no criterion line names alone (spec
# Scenario 14, FR-32, FR-34, FR-37, FR-38, FR-39, FR-42, FR-43; research R24, R26, R27, R29, R33). One project per
# failure, each asking for it and nothing else (cross-stack P005), on fixtures/nested/snapshot-plain: a `db` with the
# named volume `db-data` and the project bound at its own path. For each: the exit code, the cause named, and, read
# from the daemon and the ledger by the runner (cross-stack P004), nothing left half-done:
#   - past the grant's cap (lane grant nested-snapcap, 64 KiB; a 100 KiB volume): exit 4 with the grant envelope,
#     limit `snapshots`, the operator's extend; 0 snapshot volumes; a refused row;
#   - an unknown volume, a bind mount's path, another environment's volume: exit 3, naming this environment's own
#     volumes; 0 snapshot volumes; a refused row with the limit `volume`;
#   - an unknown snapshot, for restore and for snapshot-rm: exit 3 naming the snapshot that exists;
#   - the store fills partway (lane grant nested-snapfull): exit 1 naming the full store; 0 snapshot volumes left;
#     db running and unpaused, with its pause ended in the ledger;
#   - a snapshot whose content no longer matches its record (changed on the daemon by the runner): restore --yes is
#     exit 1 before anything is stopped: db is the same container, never restarted;
#   - a service that is not ready after a restore: exit 1 naming readiness, `adele env status` and `adele env down`;
#     the restored data stays restored.
# Not tested here: a copy past its 5 min bound (124), which would measure the machine for minutes. A killed helper,
# Adele killed mid-snapshot and collection are the recovery files'.
# Not serial (lane.conf): every environment, grant use and snapshot is the cell's own.

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

# plain_up CELL GRANT — the cell's project from snapshot-plain, brought up under GRANT; DB is its db container.
plain_up() {
  nested_project "$1" snapshot-plain
  nested_files snapshot-plain
  env_run c "--text env up --project ${NP_NAME} --grant $2"
  assert_status 0
  DB="$(nested_container "$NP_NAME" db)"
  [[ -n "$DB" ]] || { echo "no db container labelled ${NP_NAME}" >&2; return 1; }
}

# fill WHAT — fill.sh WHAT in db, through `adele env exec`.
fill() {
  env_run c "--text env exec ${NP_NAME} --service db -- sh ${NP_DIR}/fill.sh $1"
  assert_status 0
  assert_value filled "$1"
}

# snapshot_id — a snapshot of db-data, taken and parsed; prints its id.
snapshot_id() {
  env_run c "--json env snapshot ${NP_NAME} db-data 2>/dev/null"
  assert_status 0
  printf '%s' "$output" | pyq "
import json, sys
print(json.load(sys.stdin)['snapshot']['id'])"
}

# both ARGS — `adele --text ARGS` with stderr on stdout: the verdict, rule 14's line and the remediation in one
# $output, the exit kept.
both() { env_run c "--text $* 2>&1"; }

@test "13 a snapshot past the grant's cap is exit 4 with the grant envelope, and nothing is written" {
  plain_up cap nested-snapcap
  fill big
  env_run c "--json env snapshot ${NP_NAME} db-data 2>/dev/null"
  assert_status 4
  printf '%s' "$output" | pyq "
import json, sys
d = json.load(sys.stdin)
assert d['status'] == 'grant_required' and d['grant'] == 'nested-snapcap' and d['extend_by'] == 'operator', d
assert d['limit']['name'] == 'snapshots' and 'db-data' in d['limit']['needed'], d['limit']
assert d['extend'].startswith('docker exec timelike-adele adeled extend nested-snapcap snapshots '), d['extend']
assert d['performed'] is False, d
"
  [[ "$(nested_snapshot_count "$NP_NAME")" == 0 ]] || { echo "snapshot volumes: $(nested_snapshot_volumes "$NP_NAME" | tr '\n' ' ')" >&2; return 1; }
  nested_running_unpaused "$DB"
  run ledger_rows_for "$NP_NAME"
  assert_status 0
  printf '%s\n' "$output" | grep -q $'^refused\tsnapshot\tsnapshots\t' || { echo "no refused row with limit snapshots: $output" >&2; return 1; }
  ! printf '%s\n' "$output" | grep -q $'^performed\tpause\t' || { echo "a refused snapshot paused something: $output" >&2; return 1; }
}

@test "13 an unknown volume, a bind mount and another environment's volume are exit 3, naming this environment's own volumes" {
  local other
  plain_up other-env nested
  other="$(nested_volume "$NP_NAME" db-data)" || return 1
  NP_OTHER="$NP_NAME"
  NP_OTHER_DIR="$NP_DIR"
  plain_up vols nested

  both "env snapshot ${NP_NAME} nosuch"
  assert_status 3
  assert_output_has "nosuch"
  assert_output_has "db-data"
  # The project directory is bound into db: a path, not one of the environment's named volumes.
  both "env snapshot ${NP_NAME} ${NP_DIR}"
  assert_status 3
  assert_output_has "db-data"
  # The other environment's volume, by its daemon name: real, labelled, and not this environment's.
  both "env snapshot ${NP_NAME} ${other}"
  assert_status 3
  assert_output_has "db-data"

  [[ "$(nested_snapshot_count "$NP_NAME")" == 0 && "$(nested_snapshot_count "$NP_OTHER")" == 0 ]] ||
    { echo "snapshot volumes: $(nested_snapshot_volumes "$NP_NAME" | tr '\n' ' ') / $(nested_snapshot_volumes "$NP_OTHER" | tr '\n' ' ')" >&2; return 1; }
  run ledger_rows_for "$NP_NAME"
  assert_status 0
  [[ "$(printf '%s\n' "$output" | grep -c $'^refused\tsnapshot\tvolume\t')" == 3 ]] || { echo "want 3 refused rows with limit volume: $output" >&2; return 1; }
}

@test "13 an unknown snapshot is exit 3 for restore and for snapshot-rm, naming the snapshot that exists" {
  local sid
  plain_up nosnap nested
  sid="$(snapshot_id)" || return 1
  [[ "$sid" =~ ^s-[0-9a-f]{8}$ ]] || { echo "snapshot id: ${sid}" >&2; return 1; }
  [[ "$sid" != s-00000000 ]] || skip "the snapshot's random id is the one this cell names as unknown"
  both "env restore ${NP_NAME} s-00000000 --yes"
  assert_status 3
  assert_output_has "s-00000000"
  assert_output_has "$sid"
  both "env snapshot-rm ${NP_NAME} s-00000000 --yes"
  assert_status 3
  assert_output_has "$sid"
  # Nothing was stopped or removed: the snapshot that exists is still there, and db still runs.
  [[ "$(nested_snapshot_volumes "$NP_NAME")" == "${NP_NAME}-snap-${sid#s-}" ]] ||
    { echo "snapshot volumes: $(nested_snapshot_volumes "$NP_NAME" | tr '\n' ' ')" >&2; return 1; }
  nested_running_unpaused "$DB"
}

# The store is a tmpfs of 1 MiB (nested-snapfull: snapshot-store = tmpfs, snapshots = 1MiB). 400 one-byte files are
# 400 bytes, under the cap, so the measure lets the copy start; on a tmpfs each takes a 4 KiB page, so the copy meets
# ENOSPC after about 256 of them. What fills is memory, bounded at 1 MiB by the volume's own size option: never the
# host's disk (014 plan R33; cross-stack P006).
@test "13 a store that fills partway is exit 1 naming the full store: the partial snapshot removed, db unpaused" {
  local rows
  plain_up full nested-snapfull
  fill tiny
  both "env snapshot ${NP_NAME} db-data"
  assert_status 1
  printf '%s\n' "$output" | grep -qiE 'full|no space' || { echo "the verdict does not name a full store: $output" >&2; return 1; }
  [[ "$(nested_snapshot_count "$NP_NAME")" == 0 ]] || { echo "partial snapshot left: $(nested_snapshot_volumes "$NP_NAME" | tr '\n' ' ')" >&2; return 1; }
  nested_running_unpaused "$DB"
  run ledger_rows_for "$NP_NAME"
  assert_status 0
  rows="$output"
  printf '%s\n' "$rows" | grep -q $'^performed\tpause\t' || { echo "no pause row: $rows" >&2; return 1; }
  printf '%s\n' "$rows" | grep -q $'^performed\tunpause\t' || { echo "the pause was not ended by an unpause row: $rows" >&2; return 1; }
  ! printf '%s\n' "$rows" | grep -q $'^performed\tsnapshot\t' || { echo "a failed snapshot has a performed row: $rows" >&2; return 1; }
}

@test "13 a snapshot whose content no longer matches its record is exit 1 before anything is stopped" {
  local sid snapvol before
  plain_up mismatch nested
  sid="$(snapshot_id)" || return 1
  snapvol="${NP_NAME}-snap-${sid#s-}"
  # The runner changes one byte of the snapshot's own content on the daemon, where the agent cannot reach: a
  # throwaway on a timelike-labelled volume (nested_volume_throwaway). serve.sh's row is root's, mode 0644.
  nested_volume_throwaway "$snapvol" 0:0 'printf y >>/v/f1' || return 1
  before="$(nested_state "$DB")"
  both "env restore ${NP_NAME} ${sid} --yes"
  assert_status 1
  assert_output_has "does not match its record"
  [[ "$(nested_container "$NP_NAME" db)" == "$DB" && "$(nested_state "$DB")" == "$before" ]] ||
    { echo "db was stopped or restarted: ${before} -> $(nested_state "$DB")" >&2; return 1; }
  run ledger_rows_for "$NP_NAME"
  assert_status 0
  ! printf '%s\n' "$output" | grep -qE $'^performed\t(stop|restore)\t' || { echo "a stop or restore row was written: $output" >&2; return 1; }
}

# The healthcheck fails while /data/unready exists. The snapshot is taken with it there (db is unhealthy, and still
# running, so it can be snapshotted); it is removed, db is healthy again, and the restore brings it back. After the
# restart db is inside its 30 s start_period, failing, so it reads "starting" past the 5 s wait.
@test "13 a service that is not ready after a restore is exit 1 naming status and down; the data stays restored" {
  local sid
  plain_up unready nested
  fill unready
  sid="$(snapshot_id)" || return 1
  fill ready
  both "env restore ${NP_NAME} ${sid} --yes --wait 5"
  assert_status 1
  printf '%s\n' "$output" | grep -qi 'ready' || { echo "the verdict does not name readiness: $output" >&2; return 1; }
  assert_output_has "adele env status"
  assert_output_has "adele env down"
  # The data is the snapshot's: the marker is back, read in db.
  env_run c "--text env exec ${NP_NAME} --service db -- sh -c 'test -e /data/unready && echo marker=present'"
  assert_status 0
  assert_value marker present
  nested_running_unpaused "$DB"
}
