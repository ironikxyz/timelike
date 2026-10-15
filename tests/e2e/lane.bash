# shellcheck shell=bash
# The parallel lane's file lock (bridge/sends/maint-lane-speed-20261015-062546.md, part 1a).
#
# tests/run.sh runs e2e files side by side (`bats --jobs N --no-parallelize-within-files`) when E2E_JOBS > 1,
# and then exports:
#   TL_E2E_LOCK          the lock file, on the tests/out mount (the host and the runner see the same inode)
#   TL_E2E_SERIAL_FILES  the files that must run with no other file beside them (tests/e2e/lane.conf)
# Every file holds the lock while it runs: shared, or exclusive for a serial file. So a serial file waits until
# no other file runs, and nothing starts beside it. A turnstile in front of the lock gives a waiting exclusive
# holder its turn: without it, a serial file could wait for as long as shared files keep arriving.
#
# The lock is taken once per file, in bats-exec-file, the process that runs setup_file, every test and
# teardown_file, and it is released when that process exits. Not in bats-gather-tests, which sources every
# file in one process to count the tests, and not again in bats-exec-test, which inherits TL_E2E_LOCK_HELD.
# The bottom of BASH_SOURCE names the bats program doing the sourcing.
#
# With E2E_JOBS=1 tests/run.sh sets neither variable, nothing here runs, and the lane is the serial one.
# It also exports TL_E2E_FILE_ID, the file's own name, which helpers.bash uses to keep a file's
# whole-container process checks to that file's own processes (kill_strays, assert_no_pager_or_editor).

lane_lock() {
  [[ -n "${TL_E2E_LOCK:-}" && -z "${TL_E2E_LOCK_HELD:-}" ]] || return 0
  [[ "${BASH_SOURCE[-1]##*/}" == bats-exec-file ]] || return 0
  local name="${BATS_TEST_FILENAME##*/}" mode=shared turn fd f
  for f in ${TL_E2E_SERIAL_FILES:-}; do
    [[ "$f" == "$name" ]] && mode=exclusive
  done
  exec {turn}>>"${TL_E2E_LOCK}.turn" || return 1
  flock -x "$turn" || return 1
  exec {fd}>>"${TL_E2E_LOCK}" || return 1
  if [[ "$mode" == exclusive ]]; then flock -x "$fd" || return 1; else flock -s "$fd" || return 1; fi
  exec {turn}>&-
  # shellcheck disable=SC2034 # kept open for the life of this process, which is what holds the lock
  TL_E2E_LOCK_FD="$fd"
  export TL_E2E_LOCK_HELD="$mode" TL_E2E_FILE_ID="$name"
}

lane_lock
