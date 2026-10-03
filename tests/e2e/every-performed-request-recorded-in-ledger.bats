#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# shellcheck disable=SC2030,SC2031 # bats runs each @test in its own subshell by design
# SC-5 (feature 004) — "Every performed request is recorded in the ledger with grant, requesting
# session, resource created, estimated cost and expiry" (send 12-rev2, slice 0; spec FR-14..FR-17;
# tasks.md T015).
#
# The agent performs one request within the `e2e` grant, from a session named for the cell. The
# operator's ledger (`docker exec timelike-adele adeled ledger --json`) must hold exactly one
# `performed` row for that box, carrying: the grant, that session, the box, the cost the stand-in's OWN
# record says it charged (cross-stack P004), an expiry equal to the stand-in's creation time plus the
# requested ttl (to the second), and an undo naming the delete of that box (P5).

load helpers

setup_file() {
  stamp_check
  stamp_check_adele
}

check_recorded() {
  local style="$1" box="t-sc5-$1" session="sc5-$1"
  run_in -e "TIMELIKE_SESSION=${session}" "$style" notty \
    "adele --json request standin.box create --grant e2e --name ${box} --ttl 90m --port 8080"
  [[ "$status" -eq 0 ]] || { echo "request exited $status: $output" >&2; return 1; }

  local ledger record
  ledger="$(adeled ledger --json)" || { echo "adeled ledger failed" >&2; return 1; }
  record="$(standin_list)" || { echo "the stand-in's record could not be read" >&2; return 1; }
  run pyq "
import json, sys, datetime as dt
raw = sys.stdin.read().split('\x1e')
ledger, record = json.loads(raw[0]), json.loads(raw[1])
box, session = '${box}', '${session}'
rows = [r for r in ledger if r['outcome'] == 'performed' and r['resource'] == box]
assert len(rows) == 1, f'{len(rows)} performed rows for {box}'
r = rows[0]
boxes = [b for b in record if b['name'] == box]
assert len(boxes) == 1, f'the stand-in records {len(boxes)} boxes named {box}'
b = boxes[0]
created = dt.datetime.fromisoformat(b['created_at'].replace('Z', '+00:00'))
want = (created + dt.timedelta(minutes=90)).replace(microsecond=0)
got = dt.datetime.fromisoformat(r['expires_at'].replace('Z', '+00:00'))
checks = {
  'grant': r['grant'] == 'e2e',
  'session': r['session'] == session,
  'resource': r['resource'] == box,
  'cost': r['cost_cents'] == b['cost_cents'] == 38,
  'expiry': got == want,
  'undo': r['undo'] == {'capability': 'standin.box', 'action': 'delete', 'params': {'name': box}},
}
bad = [k for k, ok in checks.items() if not ok]
print('ok' if not bad else 'FAILED ' + ', '.join(bad) + f' row={r} box={b} want_expiry={want.isoformat()}')
" <<<"${ledger}"$'\x1e'"${record}"
  [[ "$status" -eq 0 && "$output" == ok ]] || { echo "$output" >&2; return 1; }
}

@test "SC-5 004 every performed request is recorded in the ledger with grant, session, resource, cost and expiry [bash -c]" { check_recorded c; }
@test "SC-5 004 every performed request is recorded in the ledger with grant, session, resource, cost and expiry [bash -lc]" { check_recorded lc; }
