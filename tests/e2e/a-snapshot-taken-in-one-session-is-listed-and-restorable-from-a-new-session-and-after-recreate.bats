#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# shellcheck disable=SC2030,SC2031 # bats runs each @test in its own subshell by design
# SC-8 — "A snapshot taken in one session is listed and restorable from a new session, and after the
# agent's container is recreated". (Feature 005, slice 1, revision 11; spec FR-23 as amended, FR-25 to
# FR-31, Scenarios 7 and 8; tasks.md T028.)
#
#   - New session: one session takes a snapshot, another lists it (with the session and agent that took
#     it, FR-31) and restores it, in the running agent container.
#   - Recreate: the lane recreates the container, never a simulation inside one (the send; lore
#     docker-compose Q004: the image the lane just built). A throwaway container from the verified image
#     gets two FRESH named volumes, the state root (/var/lib/timelike, as compose.yaml mounts it) and a
#     home holding the project (/home/agent, so the project survives too). A snapshot is taken; the
#     container is removed; a new one starts on the same volumes; the snapshot is listed there and
#     restored, and the workspace is compared with the test's own manifest (P004). The state volume is
#     fresh, so its first mount also shows the image's ownership reaching it (lore Q003, FR-26).
#   - Persistence is stated (FR-27): with the volume, no not-persistent line; in a throwaway with no
#     volume (a plain docker run), the line, naming the state root and the remedy.
# Cells: bash -c and bash -lc, `notty`.

load helpers

FIXTURE=/tmp/recover-repo-sc8.sh

setup_file() {
  stamp_check
  remove_stale_throwaways
  copy_into_container "${BATS_TEST_DIRNAME}/fixtures/recover-repo.sh" "$FIXTURE" 0755
}

setup() {
  WORK="$(container_tmpdir sc8sess)"
  REPO="${WORK}/repo"
  STATE="$(state_root_dir sc8sess)"
  exec_plain sh "$FIXTURE" "$REPO" >/dev/null
  RC_NAME="timelike-sc8-recreate-$$-${RANDOM}"
  RC_STATE="timelike-sc8-state-$$-${RANDOM}"
  RC_HOME="timelike-sc8-home-$$-${RANDOM}"
}

teardown() {
  container_rm "$WORK"
  state_root_rm "$STATE"
  remove_throwaway "$RC_NAME" "${RC_NAME}-2" "${RC_NAME}-plain"
  timeout "$RUN_TIMEOUT" docker volume rm -f "$RC_STATE" "$RC_HOME" </dev/null >/dev/null 2>&1 || true
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

# in_repo STYLE SESSION AGENT CMD — CMD in the repository, this test's state root, no scheduled snapshot.
in_repo() {
  run_in -e "TIMELIKE_STATE_ROOT=${STATE}" -e "TIMELIKE_SESSION=$2" -e "TIMELIKE_AGENT=$3" \
    -e TIMELIKE_SNAPSHOT_INTERVAL=off "$1" notty "cd '${REPO}' && $4"
  assert_within 30
}

check_new_session() {
  local style="$1" before after l found=no
  in_repo "$style" s1 agent-a "snapshot --text"
  [[ "$status" == 0 && "${lines[1]}" == "verdict: snapshot 1 taken: "* ]] || flunk "session s1's snapshot"
  before="$(exec_plain sh -c "$MANIFEST_SH" m "$REPO")"
  exec_plain rm -rf "${REPO}/src" "${REPO}/README.md"

  in_repo "$style" s2 agent-b "snapshot list --verbose --text"
  [[ "$status" == 0 && "${lines[1]}" == "verdict: 1 snapshots" ]] || flunk "session s2 does not list it"
  for l in "${lines[@]}"; do
    if [[ "$l" == "1  on demand  "*"  session s1  agent agent-a" ]]; then found=yes; fi
  done
  [[ "$found" == yes ]] || flunk "s2's list does not name the session and agent that took snapshot 1"
  for l in "${lines[@]}"; do
    [[ "$l" != "not persistent: "* ]] || flunk "the state root is on the volume, yet a not-persistent line"
  done

  in_repo "$style" s2 agent-b "undo 1 --yes --text"
  [[ "$status" == 0 ]] || flunk "session s2 cannot restore session s1's snapshot"
  after="$(exec_plain sh -c "$MANIFEST_SH" m "$REPO")"
  [[ "$after" == "$before" ]] || { diff <(echo "$before") <(echo "$after") >&2; flunk "not restored"; }
}

@test "SC-8 [bash -c, notty] a snapshot taken in one session is listed and restorable from a new session" { check_new_session c; }
@test "SC-8 [bash -lc, notty] a snapshot taken in one session is listed and restorable from a new session" { check_new_session lc; }

# in_rc NAME CMD — CMD as the agent in throwaway NAME (bash -c), no scheduled snapshot.
in_rc() {
  run timeout "$RUN_TIMEOUT" docker exec -e TIMELIKE_SNAPSHOT_INTERVAL=off "$1" bash -c "$2" </dev/null
  output="${output//$'\r'/}"
  mapfile -t lines <<<"$output"
}

@test "SC-8 [bash -c, notty] a snapshot is listed and restorable after the agent's container is recreated" {
  local before after
  start_throwaway "$RC_NAME" -v "${RC_STATE}:/var/lib/timelike" -v "${RC_HOME}:/home/agent" ||
    flunk "cannot start the first container"
  in_rc "$RC_NAME" 'stat -c "%a %U" /var/lib/timelike'
  [[ "$output" == "700 agent" ]] || flunk "a fresh state volume did not take the image's ownership (Q003)"
  # as the agent user, as copy_into_container does (docker cp would create the file as root)
  timeout "$RUN_TIMEOUT" docker exec -i "$RC_NAME" sh -c 'cat >/tmp/recover-repo.sh' \
    <"${BATS_TEST_DIRNAME}/fixtures/recover-repo.sh" || flunk "cannot copy the fixture in"
  in_rc "$RC_NAME" 'sh /tmp/recover-repo.sh /home/agent/proj >/dev/null && cd /home/agent/proj && snapshot --text'
  [[ "$status" == 0 && "${lines[1]}" == "verdict: snapshot 1 taken: "* ]] || flunk "the first container's snapshot"
  before="$(timeout "$RUN_TIMEOUT" docker exec "$RC_NAME" sh -c "$MANIFEST_SH" m /home/agent/proj </dev/null)"

  remove_throwaway "$RC_NAME"
  start_throwaway "${RC_NAME}-2" -v "${RC_STATE}:/var/lib/timelike" -v "${RC_HOME}:/home/agent" ||
    flunk "cannot start the recreated container"
  # `command rm`: this cell is about the recreate, so the guard's own snapshot before rm -rf (SC-6) is kept
  # out of the count it reads
  in_rc "${RC_NAME}-2" 'cd /home/agent/proj && command rm -rf src tools && echo new >extra.txt && snapshot list --text'
  [[ "$status" == 0 && "${lines[1]}" == "verdict: 1 snapshots" ]] || flunk "the recreated container does not list it"
  in_rc "${RC_NAME}-2" 'cd /home/agent/proj && undo 1 --yes --text'
  [[ "$status" == 0 && "${lines[1]}" == "verdict: restored to snapshot 1: "* ]] || flunk "the restore after recreate"
  after="$(timeout "$RUN_TIMEOUT" docker exec "${RC_NAME}-2" sh -c "$MANIFEST_SH" m /home/agent/proj </dev/null)"
  [[ "$after" == "$before" ]] || { diff <(echo "$before") <(echo "$after") >&2; flunk "not restored"; }
}

@test "SC-8 [bash -c, notty] without the state volume every result says the recovery state is not persistent" {
  start_throwaway "${RC_NAME}-plain" || flunk "cannot start a plain container"
  in_rc "${RC_NAME}-plain" 'mkdir -p /tmp/p && cd /tmp/p && echo x >f && snapshot --text && snapshot list --text'
  [[ "$status" == 0 ]] || flunk "snapshot in a plain container"
  local want="not persistent: /var/lib/timelike is not a mounted volume, so this recovery state dies with the container; mount one at /var/lib/timelike (compose.yaml: timelike-state)"
  local n=0 l
  for l in "${lines[@]}"; do if [[ "$l" == "$want" ]]; then n=$((n + 1)); fi; done
  [[ "$n" == 2 ]] || flunk "want the not-persistent line once in each of the two results, got ${n}"
}
