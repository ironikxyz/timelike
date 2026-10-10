#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# SC-7 — "A directory removed by a script (not by the shell's delete command) is restorable from the most
# recent automatic or scheduled snapshot". (Feature 005, slice 1; spec FR-32 to FR-35, Scenario 6;
# tasks.md T028; contracts/recover-cli.md § The scheduled snapshot.)
#
# The script is a real Python script (shutil.rmtree), which no argument-inspecting guard sees (P005: the
# real interpreter, a real repository built by git). The snapshot is the one the shell's start takes
# (/etc/timelike/shell-env.bash, FR-32), with TIMELIKE_SNAPSHOT_INTERVAL=0 so it is due at that start;
# "restored" is decided by the test's own manifest of the workspace, never by the tool's message (P004).
# A further cell runs under the DEFAULT interval: the first shell start takes one, the next does not.
# Which command lines take none (`snapshot`, `undo`) is the hook's logic, tested on the host (test_shell_env_hook.sh K6, K7).
# Each test has its own state root on the agent's state volume (helpers.bash state_root_dir).
# Cells: bash -c, bash -lc and bash -ic, `notty`.

load helpers

FIXTURE=/tmp/recover-repo-sc7.sh

setup_file() {
  stamp_check
  copy_into_container "${BATS_TEST_DIRNAME}/fixtures/recover-repo.sh" "$FIXTURE" 0755
}

setup() {
  WORK="$(container_tmpdir sc7sched)"
  REPO="${WORK}/repo"
  STATE="$(state_root_dir sc7sched)"
  exec_plain sh "$FIXTURE" "$REPO" >/dev/null
}

teardown() {
  container_rm "$WORK"
  state_root_rm "$STATE"
}

# MANIFEST_SH DIR OUT — every entry outside every .git: kind, path, mode, sha256 or link target.
MANIFEST_SH='set -eu
cd "$1"
find . -mindepth 1 -name .git -prune -o -print | LC_ALL=C sort | while IFS= read -r p; do
  if [ -L "$p" ]; then printf "link %s -> %s\n" "$p" "$(readlink "$p")"
  elif [ -d "$p" ]; then printf "dir %s %s\n" "$p" "$(stat -c %a "$p")"
  elif [ -f "$p" ]; then printf "file %s %s %s\n" "$p" "$(stat -c %a "$p")" "$(sha256sum <"$p" | cut -d" " -f1)"
  else printf "other %s\n" "$p"; fi
done >"$2"'

manifest() {
  exec_plain sh -c "$MANIFEST_SH" manifest "$REPO" "${WORK}/$1.manifest"
}

same_manifest() {
  local d
  d="$(exec_plain diff -u "${WORK}/$1.manifest" "${WORK}/$2.manifest" 2>&1)" && return 0
  printf 'workspace manifest "%s" differs from "%s":\n%s\n' "$2" "$1" "$d" >&2
  return 1
}

# in_repo STYLE INTERVAL CMD — CMD in a shell STARTED in the repository (-w: the hook snapshots the
# workspace of the shell's starting directory, as a harness starts the agent's shell in its workspace;
# a `cd` inside the command comes after the hook), with this test's state root and the given
# TIMELIKE_SNAPSHOT_INTERVAL ("" = unset in effect: the hook's default); stderr to $WORK/stderr.
in_repo() {
  run_in -e "TIMELIKE_STATE_ROOT=${STATE}" -e "TIMELIKE_SNAPSHOT_INTERVAL=$2" -e "TIMELIKE_SESSION=sc7" \
    -w "$REPO" "$1" notty "$3 2>'${WORK}/stderr'"
  assert_within 30
}

flunk() {
  local err
  err="$(exec_plain cat "${WORK}/stderr" 2>&1)" || true
  printf '%s\nexit %s; stdout:\n%s\nstderr:\n%s\n' "$1" "$status" "$output" "$err" >&2
  return 1
}

# scheduled_ids — the ids of this workspace's snapshots whose reason is `scheduled`, newest first, from
# `snapshot list --text` (a command line starting with `snapshot` takes no scheduled snapshot itself).
# Returns 0 whatever the last line was: the callers count SCHEDULED, never this function's status
# (lane 005s1-a: a `[[ … ]] && …` as a loop's last command made the function return a non-match).
scheduled_ids() {
  in_repo c off "snapshot list --text"
  [[ "$status" == 0 ]] || flunk "snapshot list failed"
  SCHEDULED=()
  local l
  for l in "${lines[@]}"; do
    if [[ "$l" =~ ^([0-9]+)\ \ scheduled\ \  ]]; then SCHEDULED+=("${BASH_REMATCH[1]}"); fi
  done
  return 0
}

check_script_delete() {
  local style="$1"
  manifest base
  in_repo "$style" 0 "python3 -c 'import shutil; shutil.rmtree(\"src\")'"
  [[ "$status" == 0 ]] || flunk "the script failed"
  [[ -z "$(exec_plain cat "${WORK}/stderr")" ]] || flunk "a complete scheduled snapshot is silent (FR-33)"
  exec_plain test ! -e "${REPO}/src" || flunk "the script did not remove src/"

  scheduled_ids
  [[ ${#SCHEDULED[@]} == 1 ]] || flunk "want one scheduled snapshot, got: ${SCHEDULED[*]}"
  in_repo "$style" off "undo ${SCHEDULED[0]} --yes --text"
  [[ "$status" == 0 ]] || flunk "undo ${SCHEDULED[0]} --yes failed"
  [[ "${lines[1]}" == "verdict: restored to snapshot ${SCHEDULED[0]}: "* ]] || flunk "unexpected verdict"
  manifest after
  same_manifest base after
}

@test "SC-7 [bash -c, notty] a directory removed by a script is restorable from the scheduled snapshot taken at the shell's start" { check_script_delete c; }
@test "SC-7 [bash -lc, notty] a directory removed by a script is restorable from the scheduled snapshot taken at the shell's start" { check_script_delete lc; }
@test "SC-7 [bash -ic, notty] a directory removed by a script is restorable from the scheduled snapshot taken at the shell's start" { check_script_delete ic; }

@test "SC-7 [bash -c, notty] under the default interval the first shell start takes one and the next does not" {
  in_repo c "" ":"
  [[ "$status" == 0 ]] || flunk "the first shell failed"
  scheduled_ids
  [[ ${#SCHEDULED[@]} == 1 ]] || flunk "the first shell start in the workspace took ${#SCHEDULED[@]} scheduled snapshots, want 1"
  in_repo c "" ":"
  scheduled_ids
  [[ ${#SCHEDULED[@]} == 1 ]] || flunk "a second shell start inside the interval took another (${SCHEDULED[*]})"
  local stamps
  stamps="$(exec_plain sh -c 'ls "$1"/stamps' stamps "$STATE")"
  [[ "$stamps" == *"repo" ]] || flunk "no stamp for the workspace under ${STATE}/stamps: '${stamps}'"
}
