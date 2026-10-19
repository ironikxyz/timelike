#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# shellcheck disable=SC2030,SC2031 # bats runs each @test in its own subshell by design
# Feature 13 slice 2, criterion 10 — "A named volume of a running nested environment is snapshotted and later
# restored to its snapshotted content" (send 13-rev17's slice 2; spec Scenario 13, FR-31 to FR-38, FR-41, FR-42;
# research R23, R24, R26, R27, R30, R33).
#
# The fixture (fixtures/nested/snapshot) is a `db` service keeping 4100 bytes of rows in 13 entries on its named
# volume `db-data`, owned by uid 999, with a symbolic link and modes of its own. Read back by the runner, from the
# daemon and the ledger, never from a verdict alone (cross-stack P004), and from the volume through
# `adele env exec` (fixtures' manifest.sh: owners, modes, sizes, times to the nanosecond, link targets, SHA-256):
#   - `adele env snapshot NAME db-data` exits 0: the snapshot `s-` and 8 hex, its bytes and files the fixture's, its
#     digest, `paused` naming db, the grant's default cap (1 GiB, in volumes); on the daemon a volume
#     `<env>-snap-<hex>` carrying every label (the env, the snapshot, the volume it was taken from, the session,
#     grant and requester the environment's own containers carry, and when); db running and unpaused afterwards;
#     a performed snapshot row on `<env>/<id>`, and a pause row ended by an unpause row;
#   - `adele env snapshots` lists it, with its note and the cap used;
#   - the data is corrupted through exec (a row changed, one deleted, one given to root, a mode, a stray row);
#   - `restore` without --yes exits 4, confirmation_required, naming the volume and db, with the agent's own command
#     plus --yes; `--dry-run` exits 0 with the same plan; after both, db was never restarted and the data is still
#     corrupt;
#   - `restore --yes` exits 0 with db ready; db was restarted; the data equals the snapshotted data, owners and all;
#     stop, start and restore rows;
#   - `snapshot-rm --yes` frees its bytes, and the volume is gone, read back, with a reaped row;
#   - a second snapshot is taken (its text verdict read), and `down` leaves nothing labelled with the environment:
#     0 snapshot volumes, and that snapshot's row ended.
# Not serial (lane.conf): every name is the cell's own. Envs' lock serialises snapshots against every environment's
# up and down, which slows a neighbour and changes nothing it reads.

load helpers
load nested

setup_file() {
  stamp_check
  stamp_check_adele
}

teardown() { nested_teardown; }

# manifest STYLE — the volume's manifest, read in db through `adele env exec` (manifest.sh), into MANIFEST.
manifest() {
  env_run "$1" "--text env exec ${NP_NAME} --service db -- sh ${NP_DIR}/manifest.sh"
  assert_status 0
  MANIFEST="$(printf '%s\n' "${lines[@]}" | grep '^m ')" || { echo "no manifest lines: $output" >&2; return 1; }
}

check_snapshot_and_restore() {
  local style="$1" db agent sid digest snapvol srcvol labels before corrupt started rows want got
  local -a lab
  nested_project "snap-${style}" snapshot
  nested_files snapshot
  env_run "$style" "--text env up --project ${NP_NAME} --grant nested"
  assert_status 0
  db="$(nested_container "$NP_NAME" db)"
  [[ -n "$db" ]] || { echo "no db container labelled ${NP_NAME}" >&2; return 1; }
  manifest "$style"
  before="$MANIFEST"
  # The fixture is what this cell says it is: 14 entries (the root and 13), owned by uid 999, a 0700 directory, a link.
  [[ "$(printf '%s\n' "$before" | wc -l | tr -d ' ')" == 14 ]] || { printf 'manifest:\n%s\n' "$before" >&2; return 1; }
  [[ -z "$(printf '%s\n' "$before" | awk '$5 != "999:999"')" ]] || { printf 'not all owned by 999:999:\n%s\n' "$before" >&2; return 1; }
  printf '%s\n' "$before" | grep -q '^m ./rows d 700 999:999 ' || { printf 'rows is not 0700:\n%s\n' "$before" >&2; return 1; }
  printf '%s\n' "$before" | grep -q '^m ./latest l .* rows/r1 -$' || { printf 'no link latest -> rows/r1:\n%s\n' "$before" >&2; return 1; }

  # ── snapshot ──
  env_run "$style" "--json env snapshot ${NP_NAME} db-data --note e2e-before 2>/dev/null"
  assert_status 0
  got="$(printf '%s' "$output" | pyq "
import json, re, sys
d = json.load(sys.stdin)
s = d['snapshot']
assert d['name'] == '${NP_NAME}', d
assert re.fullmatch(r's-[0-9a-f]{8}', s['id']), s
assert s['volume'] == 'db-data' and s['note'] == 'e2e-before', s
assert s['bytes'] == 4100 and s['files'] == 13 and s['sockets'] == 0, s
assert re.fullmatch(r'sha256:[0-9a-f]{64}', s['digest']), s
assert s['taken_at'], s
assert d['paused'] == ['db'], d
assert isinstance(d['paused_s'], (int, float)) and d['paused_s'] >= 0, d
c = d['cap']
assert c['bytes'] == 1 << 30 and c['store'] == 'volume' and c['used'] == 4100 and c['left'] == c['bytes'] - 4100, c
assert isinstance(d['ledger_id'], int), d
print(s['id'], s['digest'])
")" || return 1
  read -r sid digest <<<"$got"
  echo "# 13 snapshot (${style}): ${sid}, ${digest}" >&3

  # On the daemon: the snapshot volume, named for the id's hex, with every label; db running and unpaused.
  snapvol="${NP_NAME}-snap-${sid#s-}"
  [[ "$(nested_snapshot_volumes "$NP_NAME")" == "$snapvol" ]] ||
    { echo "snapshot volumes of ${NP_NAME}: $(nested_snapshot_volumes "$NP_NAME" | tr '\n' ' '), want ${snapvol}" >&2; return 1; }
  srcvol="$(nested_volume "$NP_NAME" db-data)" || return 1
  agent="$(docker inspect --format '{{.Id}}' "$AGENT_CONTAINER")"
  labels="$(nested_snapshot_labels "$snapvol")" || return 1
  want="$(docker inspect --format '{{index .Config.Labels "xyz.ironik.timelike.session"}}' "$db")"
  IFS=$'\t' read -r -a lab <<<"$labels"
  [[ "${lab[0]}" == "$NP_NAME" && "${lab[1]}" == "$sid" && "${lab[2]}" == "$srcvol" && "${lab[3]}" == "$want" &&
    "${lab[4]}" == nested && "${lab[5]}" == "$agent" && "${lab[6]}" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T ]] ||
    { printf 'labels of %s (env snapshot snapshot-of session grant requester created):\n%s\nwant %s %s %s %s nested %s <RFC 3339>\n' \
      "$snapvol" "$labels" "$NP_NAME" "$sid" "$srcvol" "$want" "$agent" >&2; return 1; }
  nested_running_unpaused "$db"
  run ledger_rows_for "${NP_NAME}/${sid}"
  assert_status 0
  [[ "$(printf '%s\n' "$output" | grep -c $'^performed\tsnapshot\t')" == 1 ]] || { echo "the snapshot's rows: $output" >&2; return 1; }
  run ledger_rows_for "$NP_NAME"
  assert_status 0
  rows="$output"
  printf '%s\n' "$rows" | grep -q $'^performed\tpause\t' || { echo "no pause row: $rows" >&2; return 1; }
  printf '%s\n' "$rows" | grep -q $'^performed\tunpause\t' || { echo "no unpause row ending the pause: $rows" >&2; return 1; }

  # ── listed ──
  env_run "$style" "--json env snapshots ${NP_NAME} 2>/dev/null"
  assert_status 0
  printf '%s' "$output" | pyq "
import json, sys
d = json.load(sys.stdin)
assert d['name'] == '${NP_NAME}', d
assert [(s['id'], s['volume'], s['bytes'], s['files'], s['digest'], s['note']) for s in d['snapshots']] == [
    ('${sid}', 'db-data', 4100, 13, '${digest}', 'e2e-before')], d['snapshots']
assert d['snapshots'][0]['taken_at'], d
assert d['cap']['used'] == 4100 and d['cap']['bytes'] == 1 << 30, d['cap']
assert 'db-data' in d['volumes'], d['volumes']
"

  # ── corrupt ──
  env_run "$style" "--text env exec ${NP_NAME} --service db -- sh ${NP_DIR}/corrupt.sh"
  assert_status 0
  manifest "$style"
  corrupt="$MANIFEST"
  [[ "$corrupt" != "$before" ]] || { echo "corrupt.sh changed nothing the manifest reads" >&2; return 1; }
  printf '%s\n' "$corrupt" | grep -q '^m ./rows/r9 ' || { printf 'no stray row:\n%s\n' "$corrupt" >&2; return 1; }
  started="$(nested_state "$db")"

  # ── restore without --yes: the confirmation envelope, nothing stopped ──
  env_run "$style" "--json env restore ${NP_NAME} ${sid} 2>/dev/null"
  assert_status 4
  printf '%s' "$output" | pyq "
import json, sys
d = json.load(sys.stdin)
assert d['status'] == 'confirmation_required', d
plan = ' '.join(d['plan'])
assert 'db-data' in plan and 'db' in plan.replace('db-data', ''), d['plan']
c = d['confirm']
assert c.startswith('adele ') and c.endswith(' --yes') and ' restore ' in c and '${sid}' in c and '${NP_NAME}' in c, c
"
  [[ "$(nested_state "$db")" == "$started" ]] || { echo "db changed without --yes: ${started} -> $(nested_state "$db")" >&2; return 1; }
  manifest "$style"
  [[ "$MANIFEST" == "$corrupt" ]] || { printf 'the data changed without --yes:\n%s\n' "$MANIFEST" >&2; return 1; }

  # ── --dry-run: the plan, nothing changed ──
  env_run "$style" "--json env restore ${NP_NAME} ${sid} --dry-run 2>/dev/null"
  assert_status 0
  printf '%s' "$output" | pyq "
import json, sys
d = json.load(sys.stdin)
assert d['dry_run'] is True and d['stop'] == ['db'], d
"
  [[ "$(nested_state "$db")" == "$started" ]] || { echo "db changed on --dry-run: ${started} -> $(nested_state "$db")" >&2; return 1; }
  manifest "$style"
  [[ "$MANIFEST" == "$corrupt" ]] || { printf 'the data changed on --dry-run:\n%s\n' "$MANIFEST" >&2; return 1; }

  # ── restore --yes: stopped, replaced, started, ready; the data is the snapshot's ──
  env_run "$style" "--json env restore ${NP_NAME} ${sid} --yes 2>/dev/null"
  assert_status 0
  printf '%s' "$output" | pyq "
import json, sys
d = json.load(sys.stdin)
assert d['name'] == '${NP_NAME}' and d['volume'] == 'db-data' and d['dry_run'] is False, d
snap = d['snapshot']
assert (snap['id'] if isinstance(snap, dict) else snap) == '${sid}', snap
assert d['stopped'] == ['db'] and d['digest'] == '${digest}', d
s = {x['service']: x for x in d['services']}
assert s['db']['ready'] == 'ready', s
"
  [[ "$(nested_container "$NP_NAME" db)" == "$db" ]] || { echo "db is a new container: the restore recreated it" >&2; return 1; }
  nested_running_unpaused "$db"
  [[ "$(nested_state "$db")" != "$started" ]] || { echo "db was not restarted by the restore: $(nested_state "$db")" >&2; return 1; }
  manifest "$style"
  [[ "$MANIFEST" == "$before" ]] ||
    { printf 'restored data differs from the snapshotted data:\n%s\n' "$(diff <(printf '%s\n' "$before") <(printf '%s\n' "$MANIFEST"))" >&2; return 1; }
  run ledger_rows_for "$NP_NAME"
  assert_status 0
  rows="$output"
  for want in stop start restore; do
    printf '%s\n' "$rows" | grep -q "^performed"$'\t'"${want}"$'\t' || { echo "no performed ${want} row: $rows" >&2; return 1; }
  done
  printf '%s\n' "$rows" | grep $'^performed\trestore\t' | grep -qF "$sid" || { echo "the restore row does not name ${sid}: $rows" >&2; return 1; }

  # ── snapshot-rm: confirmed, then removed, read back ──
  env_run "$style" "--json env snapshot-rm ${NP_NAME} ${sid} 2>/dev/null"
  assert_status 4
  printf '%s' "$output" | pyq "
import json, sys
d = json.load(sys.stdin)
assert d['status'] == 'confirmation_required' and d['confirm'].endswith(' --yes'), d
"
  docker volume inspect "$snapvol" >/dev/null || { echo "${snapvol} went without --yes" >&2; return 1; }
  env_run "$style" "--json env snapshot-rm ${NP_NAME} ${sid} --yes 2>/dev/null"
  assert_status 0
  printf '%s' "$output" | pyq "
import json, sys
d = json.load(sys.stdin)
assert d['name'] == '${NP_NAME}' and d['snapshot'] == '${sid}' and d['freed_bytes'] == 4100, d
"
  run docker volume inspect "$snapvol"
  [[ "$status" != 0 ]] || { echo "${snapvol} is still on the daemon after snapshot-rm" >&2; return 1; }
  [[ "$(nested_snapshot_count "$NP_NAME")" == 0 ]]
  run ledger_rows_for "${NP_NAME}/${sid}"
  assert_status 0
  printf '%s\n' "$output" | grep -q $'^reaped\tdelete\t' || { echo "no reaped row for the removed snapshot: $output" >&2; return 1; }

  # ── a second snapshot, then down takes it with the environment ──
  env_run "$style" "--text env snapshot ${NP_NAME} db-data"
  assert_status 0
  [[ "${lines[1]}" == "verdict: snapshot ${NP_NAME} db-data: s-"* ]] || { echo "verdict: ${lines[1]}" >&2; return 1; }
  sid="$(printf '%s' "${lines[1]}" | grep -oE 's-[0-9a-f]{8}' | head -1)"
  [[ "$(nested_snapshot_volumes "$NP_NAME")" == "${NP_NAME}-snap-${sid#s-}" ]] ||
    { echo "snapshot volumes: $(nested_snapshot_volumes "$NP_NAME" | tr '\n' ' ')" >&2; return 1; }
  env_run "$style" "--text env down ${NP_NAME}"
  assert_status 0
  nested_gone "$NP_NAME"
  [[ "$(nested_snapshot_count "$NP_NAME")" == 0 ]]
  run ledger_rows_for "${NP_NAME}/${sid}"
  assert_status 0
  printf '%s\n' "$output" | grep -q $'^reaped\tdelete\t' || { echo "down did not end ${sid}'s row: $output" >&2; return 1; }
}
@test "13 a named volume of a running nested environment is snapshotted and later restored to its snapshotted content [bash -c]" { check_snapshot_and_restore c; }
@test "13 a named volume of a running nested environment is snapshotted and later restored to its snapshotted content [bash -lc]" { check_snapshot_and_restore lc; }
