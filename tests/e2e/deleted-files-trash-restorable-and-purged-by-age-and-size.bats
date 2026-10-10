#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# SC-10 — "Deleted files are moved to a restorable trash that is purged by age and size limits".
# (Feature 005, slice 1; spec FR-39 to FR-41; contracts/recover-cli.md § `undo --trash`; tasks.md T028.)
#
# PARTIAL until FOR-MENTOR Item 22 is answered: what feeds the trash in the agent's shell (the guards in
# front of rm and git clean) is held. These cells feed it as every guard design will, through
# /opt/timelike/libexec/guard trash-put, then delete with the REAL rm (P005), and judge the put-back by
# the test's own manifest (P004). The criterion is not met by these cells alone.
# Cells: bash -c and bash -lc, `notty`.

load helpers

GUARD=/opt/timelike/libexec/guard

setup_file() {
  stamp_check
}

setup() {
  WORK="$(container_tmpdir sc10trash)"
  STATE="$(state_root_dir sc10trash)"
  exec_plain sh -c 'mkdir -p "$1/ws/build/deep" && cd "$1/ws" && printf "a\n" >build/a.txt && chmod 640 build/a.txt &&
    head -c 3000 /dev/urandom >build/deep/b.bin && ln -s a.txt build/link && printf "n\n" >notes.txt' s "$WORK"
}

teardown() {
  container_rm "$WORK"
  state_root_rm "$STATE"
}

MANIFEST_SH='set -eu
cd "$1"
find . -mindepth 1 -print | LC_ALL=C sort | while IFS= read -r p; do
  if [ -L "$p" ]; then printf "link %s -> %s\n" "$p" "$(readlink "$p")"
  elif [ -d "$p" ]; then printf "dir %s %s\n" "$p" "$(stat -c %a "$p")"
  elif [ -f "$p" ]; then printf "file %s %s %s\n" "$p" "$(stat -c %a "$p")" "$(sha256sum <"$p" | cut -d" " -f1)"
  else printf "other %s\n" "$p"; fi
done'

flunk() {
  printf '%s\nexit %s; output:\n%s\n' "$1" "$status" "$output" >&2
  return 1
}

in_ws() {
  run_in -e "TIMELIKE_STATE_ROOT=${STATE}" -e TIMELIKE_SESSION=sc10 "$@"
  assert_within 30
}

check_trash_put_back() {
  local style="$1" before now
  before="$(exec_plain sh -c "$MANIFEST_SH" m "${WORK}/ws")"
  in_ws "$style" notty "cd '${WORK}/ws' && ${GUARD} trash-put --command 'rm -rf build notes.txt' -- build notes.txt && rm -rf build notes.txt"
  [[ "$status" == 0 ]] || flunk "guard trash-put, then rm"
  [[ "$output" == "timelike: trash item 1 keeps 3 files ("*"): undo --trash 1 --yes puts them back" ]] ||
    flunk "the guard's line does not name the item"
  exec_plain test ! -e "${WORK}/ws/build" || flunk "rm did not delete"

  in_ws "$style" notty "cd '${WORK}/ws' && undo --trash --text"
  [[ "${lines[1]}" == "verdict: 1 items in the trash" ]] || flunk "undo --trash does not list it"
  in_ws "$style" notty "cd '${WORK}/ws' && undo --trash 1 --yes --text"
  [[ "$status" == 0 && "${lines[1]}" == "verdict: put back trash item 1: 6 paths; verified" ]] || flunk "put back"
  now="$(exec_plain sh -c "$MANIFEST_SH" m "${WORK}/ws")"
  [[ "$now" == "$before" ]] || { diff <(echo "$before") <(echo "$now") >&2; flunk "not put back as it was"; }
}

@test "SC-10 [bash -c, notty] files deleted after the trash kept them are put back as they were (fed through guard trash-put)" { check_trash_put_back c; }
@test "SC-10 [bash -lc, notty] files deleted after the trash kept them are put back as they were (fed through guard trash-put)" { check_trash_put_back lc; }

@test "SC-10 [bash -c, notty] the trash is purged by size, oldest first, and names what it dropped" {
  local i
  for i in 1 2 3; do
    in_ws -e TIMELIKE_TRASH_MAX_BYTES=2500 c notty \
      "cd '${WORK}/ws' && head -c 1000 /dev/urandom >f${i}.bin && ${GUARD} trash-put --command 'rm f${i}.bin' -- f${i}.bin && rm f${i}.bin"
    [[ "$status" == 0 ]] || flunk "put ${i}"
  done
  [[ "$output" == *"timelike: purged: trash item 1 (over TIMELIKE_TRASH_MAX_BYTES)"* ]] || flunk "the purge is not named"
  in_ws c notty "undo --trash --text"
  [[ "${lines[1]}" == "verdict: 2 items in the trash" ]] || flunk "want items 2 and 3 left"
}

@test "SC-10 [bash -c, notty] the trash is purged by age and names what it dropped" {
  in_ws c notty "cd '${WORK}/ws' && ${GUARD} trash-put --command 'rm notes.txt' -- notes.txt && rm notes.txt"
  exec_plain touch -d '40 days ago' "${STATE}/trash/items/1.json"
  in_ws c notty "cd '${WORK}/ws' && ${GUARD} trash-put --command 'rm -rf build' -- build && rm -rf build"
  [[ "$output" == *"timelike: purged: trash item 1 (older than 30 days)"* ]] || flunk "the age purge is not named"
}
