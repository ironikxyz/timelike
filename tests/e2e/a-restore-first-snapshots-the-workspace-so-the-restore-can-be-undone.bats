#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# SC-9 — "A restore first snapshots the workspace, so the restore itself can be undone, and its verdict
# names that snapshot". (Feature 005, slice 1, revision 11; spec FR-19, D-10; tasks.md T028.)
#
# FR-19 already did this in slice 0; this cell re-establishes it against the state-root store. The
# workspace the restore replaced is measured by the test's own manifest before the restore, and after
# `undo S --yes` (S as the verdict names it) it must be exactly that again (P004).
# Cells: bash -c and bash -lc, `notty`.

load helpers

FIXTURE=/tmp/recover-repo-sc9.sh

setup_file() {
  stamp_check
  copy_into_container "${BATS_TEST_DIRNAME}/fixtures/recover-repo.sh" "$FIXTURE" 0755
}

setup() {
  WORK="$(container_tmpdir sc9undo)"
  REPO="${WORK}/repo"
  STATE="$(state_root_dir sc9undo)"
  exec_plain sh "$FIXTURE" "$REPO" >/dev/null
}

teardown() {
  container_rm "$WORK"
  state_root_rm "$STATE"
}

MANIFEST_SH='set -eu
cd "$1"
find . -mindepth 1 -name .git -prune -o -print | LC_ALL=C sort | while IFS= read -r p; do
  if [ -L "$p" ]; then printf "link %s -> %s\n" "$p" "$(readlink "$p")"
  elif [ -d "$p" ]; then printf "dir %s %s\n" "$p" "$(stat -c %a "$p")"
  elif [ -f "$p" ]; then printf "file %s %s %s\n" "$p" "$(stat -c %a "$p")" "$(sha256sum <"$p" | cut -d" " -f1)"
  else printf "other %s\n" "$p"; fi
done'

flunk() {
  printf '%s\nexit %s; output:\n%s\n' "$1" "$status" "$output" >&2
  return 1
}

in_repo() {
  run_in -e "TIMELIKE_STATE_ROOT=${STATE}" -e TIMELIKE_SESSION=sc9 -e TIMELIKE_SNAPSHOT_INTERVAL=off \
    "$1" notty "cd '${REPO}' && $2"
  assert_within 30
}

check_restore_is_undoable() {
  local style="$1" replaced now s
  in_repo "$style" "snapshot --text"
  [[ "$status" == 0 ]] || flunk "snapshot"
  in_repo "$style" "sh rmsrc.sh && echo changed >README.md && echo new >new.txt"
  replaced="$(exec_plain sh -c "$MANIFEST_SH" m "$REPO")"

  in_repo "$style" "undo 1 --yes --text"
  [[ "$status" == 0 ]] || flunk "undo 1 --yes"
  [[ "${lines[1]}" =~ ^verdict:\ restored\ to\ snapshot\ 1:\ .*\ verified\;\ the\ state\ before\ is\ snapshot\ ([0-9]+)$ ]] ||
    flunk "the verdict does not name the snapshot of the state it replaced"
  s="${BASH_REMATCH[1]}"
  now="$(exec_plain sh -c "$MANIFEST_SH" m "$REPO")"
  [[ "$now" != "$replaced" ]] || flunk "the restore changed nothing"

  in_repo "$style" "undo ${s} --yes --text"
  [[ "$status" == 0 ]] || flunk "undo ${s} --yes"
  now="$(exec_plain sh -c "$MANIFEST_SH" m "$REPO")"
  [[ "$now" == "$replaced" ]] || { diff <(echo "$replaced") <(echo "$now") >&2; flunk "undo ${s} did not return the replaced state"; }
}

@test "SC-9 [bash -c, notty] a restore first snapshots the workspace, and undoing that snapshot returns the state it replaced" { check_restore_is_undoable c; }
@test "SC-9 [bash -lc, notty] a restore first snapshots the workspace, and undoing that snapshot returns the state it replaced" { check_restore_is_undoable lc; }
