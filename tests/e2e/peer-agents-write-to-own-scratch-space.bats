#!/usr/bin/env bats
# SC-6 — "Two Peer agents running concurrently each write to their own scratch space, and neither's
# output files or event log entries appear in the other's." (tasks.md T032; spec FR-12, FR-13;
# data-model.md Session.)
#
# Two `docker exec` processes, started together from the runner, each with its own TIMELIKE_SESSION
# (and a shared TIMELIKE_SCRATCH_ROOT, as peers in one environment would have). Each runs `timelike`
# 20 times and writes each output as an artefact file into ITS OWN scratch directory, the path it
# computes from TIMELIKE_SCRATCH_ROOT/TIMELIKE_SESSION (timelike itself writes only the event).
# The artefact names carry the session id, so a misplaced file is recognisable wherever it lands.
#
# Then fixtures/sc6_check.py reads both trees and reports counts; this file asserts on them:
#   - each events.jsonl has exactly 20 lines, all JSON, all with its own session id, all tool=timelike
#   - each session's 20 artefacts are under its own directory and nowhere else under the root
#   - neither tree holds a file named after, or containing, the other session's id
#   - each session directory is mode 0700, and nothing else appeared under the root
# The two runs are also shown to have overlapped in time (start of each before the end of the other),
# so "concurrently" is measured rather than assumed.
#
# Peer isolation is separation, not security (spec Assumption 4): both peers are the agent user.
# The scratch root is a fresh directory per test, so no earlier run's state can satisfy a count.
#
# Common failure (slice 1, natural intensity; modify.md F005; tasks.md T053): a harness that does not
# set TIMELIKE_SESSION at all. Spec edge case and Assumption 5: the tool still works and its events go
# to the default session ("default"). So one peer runs with no session id beside a named peer, under
# the same checks: the unnamed peer's events and files land in ROOT/default, and neither tree holds
# the other's. Unit tests cover the default session alone (test_default_session_when_unset); what is
# new is the default session running CONCURRENTLY with a named one, in the image, from outside.
# The peer script's scratch path and file names fall back to "default" the way timelike's does, so
# the same script serves both peers. Cells: bash -c and bash -lc, as the happy path.

load helpers

RUNS=20

setup_file() {
  stamp_check
  copy_into_container "${BATS_TEST_DIRNAME}/fixtures/sc6_check.py" /tmp/sc6_check.py
}

setup() {
  WORK="$(container_tmpdir sc6)"
  ROOT="${WORK}/scratch"
  # Same shape as the image's default root (/tmp/timelike, mode 1777): shared, sticky.
  exec_plain mkdir -m 1777 "$ROOT"
}

teardown() {
  container_rm "$WORK"
}

# The peer's own work, identical for both peers. It computes its scratch path the way an agent would
# and never creates it: the first timelike run must.
# shellcheck disable=SC2016 # expanded in the container
# With no TIMELIKE_SESSION it uses "default", as timelike does (spec Assumption 5).
PEER_SCRIPT='session="${TIMELIKE_SESSION:-default}"
scratch="$TIMELIKE_SCRATCH_ROOT/$session"
fails=0
i=1
while [ "$i" -le '"$RUNS"' ]; do
  if out="$(timelike --json)"; then :; else fails=$((fails + 1)); fi
  printf "%s\n" "$out" > "$scratch/out-$session-$i.json" || fails=$((fails + 1))
  i=$((i + 1))
done
echo "fails=$fails"
[ "$fails" -eq 0 ]'

# run_peer TAG SESSION STYLE — background job body: run the peer and record rc and timings.
# SESSION "default" means: pass no TIMELIKE_SESSION at all (the image sets none), so the tool's own
# fallback is what is tested, not a variable that happens to say "default".
run_peer() {
  local tag="$1" session="$2" style="$3" rc
  local -a envs=(-e "TIMELIKE_SCRATCH_ROOT=${ROOT}")
  [[ "$session" == default ]] || envs+=(-e "TIMELIKE_SESSION=${session}")
  now_ms >"${BATS_TEST_TMPDIR}/${tag}.start"
  exec_in "${envs[@]}" \
    "$style" notty "$PEER_SCRIPT" >"${BATS_TEST_TMPDIR}/${tag}.out" 2>&1 && rc=0 || rc=$?
  now_ms >"${BATS_TEST_TMPDIR}/${tag}.end"
  echo "$rc" >"${BATS_TEST_TMPDIR}/${tag}.rc"
}

# check_peers STYLE [A_SESSION] — A_SESSION "default" runs peer a with no session id.
check_peers() {
  local style="$1"
  local a="${2:-peer-a-${BATS_SUITE_TEST_NUMBER:-0}-${RANDOM}}" b="peer-b-${BATS_SUITE_TEST_NUMBER:-0}-${RANDOM}"

  run_peer a "$a" "$style" 3>&- &
  local pa=$!
  run_peer b "$b" "$style" 3>&- &
  local pb=$!
  wait "$pa" || true
  wait "$pb" || true

  local t
  for t in a b; do
    local rc
    rc="$(cat "${BATS_TEST_TMPDIR}/${t}.rc")"
    if [[ "$rc" != 0 ]]; then
      printf 'peer %s exited %s; output:\n%s\n' "$t" "$rc" "$(cat "${BATS_TEST_TMPDIR}/${t}.out")" >&2
      return 1
    fi
  done

  local as ae bs be
  as="$(cat "${BATS_TEST_TMPDIR}/a.start")" ae="$(cat "${BATS_TEST_TMPDIR}/a.end")"
  bs="$(cat "${BATS_TEST_TMPDIR}/b.start")" be="$(cat "${BATS_TEST_TMPDIR}/b.end")"
  if ! ((as < be && bs < ae)); then
    echo "the peers did not overlap in time (a ${as}–${ae} ms, b ${bs}–${be} ms): not a concurrency test" >&2
    return 1
  fi

  run exec_plain "$AGENT_PY" -I /tmp/sc6_check.py "$ROOT" "$a" "$b"
  assert_status 0
  assert_value sc6-check "done"
  local x
  for x in a b; do
    assert_value "${x}_dir_exists" 1
    assert_value "${x}_dir_mode" 700
    assert_value "${x}_events_lines" "$RUNS"
    assert_value "${x}_events_unparsed" 0
    assert_value "${x}_events_own_session" "$RUNS"
    assert_value "${x}_events_tool_timelike" "$RUNS"
    assert_value "${x}_out_files" "$RUNS"
    assert_value "${x}_out_valid" "$RUNS"
    assert_value "${x}_out_elsewhere" 0
    assert_value "${x}_holds_other_names" 0
    assert_value "${x}_holds_other_content" 0
  done
  assert_value root_strays 0
}

@test "SC-6 two peer agents running concurrently each write to their own scratch space, neither's output files or event log entries in the other's [bash -c]" {
  check_peers c
}

@test "SC-6 two peer agents running concurrently each write to their own scratch space, neither's output files or event log entries in the other's [bash -lc]" {
  check_peers lc
}

# --- common failure (slice 1): one peer sets no session id ---
@test "SC-6 a peer with no session id (default session) running concurrently with a named peer: each writes to its own scratch space, neither's output files or event log entries in the other's [bash -c]" {
  check_peers c default
}

@test "SC-6 a peer with no session id (default session) running concurrently with a named peer: each writes to its own scratch space, neither's output files or event log entries in the other's [bash -lc]" {
  check_peers lc default
}
