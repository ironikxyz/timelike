#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# shellcheck disable=SC2030,SC2031 # bats runs each @test in its own subshell by design
# SC-6 — "A recursive delete, a hard reset with uncommitted changes, a force push, and a clean of untracked
# files each take an automatic snapshot before running, and the verdict names it". (Feature 005, slice 1;
# spec FR-42 to FR-47, D-19; FOR-MENTOR Item 22's ruling; tasks.md T032.)
#
# The commands are the REAL rm, git reset --hard, git clean and git push --force, typed into the agent's
# own shell (the functions /etc/timelike/shell-env.bash defines), against a real repository built by git
# (fixtures/recover-repo.sh) and a real bare remote in the container (cross-stack P005). "Taken" and
# "restored" are judged by the test: the snapshot's record and the store read back, the workspace's
# manifest, the remote's ref (P004). Never by the line alone.
#   - each shell starts in the repository (-w), as a harness starts the agent's shell in its workspace;
#   - a script the agent's shell starts is NOT guarded (the ruling's depth bound): its delete keeps its
#     exit code and is recoverable from the scheduled snapshot instead (criterion 2's case);
#   - the guard's helpers come from timelike's location, not PATH (P002): a decoy first on PATH is
#     never run.
# Cells: bash -c, bash -lc and bash -ic, `notty`.

load helpers

FIXTURE=/tmp/recover-repo-sc6.sh

setup_file() {
  stamp_check
  copy_into_container "${BATS_TEST_DIRNAME}/fixtures/recover-repo.sh" "$FIXTURE" 0755
}

setup() {
  WORK="$(container_tmpdir sc6guard)"
  REPO="${WORK}/repo"
  STATE="$(state_root_dir sc6guard)"
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

manifest() {
  exec_plain sh -c "$MANIFEST_SH" m "$REPO"
}

flunk() {
  printf '%s\nexit %s; output:\n%s\n' "$1" "$status" "$output" >&2
  return 1
}

# in_repo STYLE CMD [INTERVAL] — CMD in a shell started in the repository, this test's state root. In the
# ic style, bash's own two no-terminal lines are dropped first (drop_ic_notty_lines, helpers.bash).
in_repo() {
  run_in -e "TIMELIKE_STATE_ROOT=${STATE}" -e TIMELIKE_SESSION=sc6 -e "TIMELIKE_SNAPSHOT_INTERVAL=${3:-off}" \
    -w "$REPO" "$1" notty "$2"
  if [[ "$1" == ic ]]; then drop_ic_notty_lines; fi
  assert_within 60
}

# has_line TEXT — one of the last run's lines is exactly TEXT.
has_line() {
  local l
  for l in "${lines[@]}"; do
    if [[ "$l" == "$1" ]]; then return 0; fi
  done
  return 1
}

# snapshot_reasons — this workspace's snapshots' reasons, newest first, one per line (from the store's
# own list, read after the command, never from the guard's line).
snapshot_reasons() {
  run_in -e "TIMELIKE_STATE_ROOT=${STATE}" -e TIMELIKE_SNAPSHOT_INTERVAL=off -w "$REPO" c notty \
    'snapshot list --json | python3 -c "import json,sys; [print(s[\"reason\"]) for s in json.load(sys.stdin)[\"snapshots\"]]"'
  [[ "$status" == 0 ]] || flunk "snapshot list failed"
}

check_rm() {
  local style="$1" before after
  before="$(manifest)"
  in_repo "$style" "rm -rf src notes"
  [[ "$status" == 0 ]] || flunk "rm -rf failed"
  exec_plain test ! -e "${REPO}/src" || flunk "rm did not delete src/"
  has_line "timelike: snapshot 1 of ${REPO} taken before rm -rf src notes: undo 1 --yes puts the workspace back" ||
    flunk "no line naming the snapshot"
  snapshot_reasons
  [[ "$output" == "before rm -rf src notes" ]] || flunk "the store does not hold one snapshot taken before rm"

  in_repo "$style" "undo 1 --yes --text"
  [[ "$status" == 0 && "${lines[1]}" == "verdict: restored to snapshot 1: "* ]] || flunk "undo 1 --yes"
  after="$(manifest)"
  [[ "$after" == "$before" ]] || { diff <(echo "$before") <(echo "$after") >&2; flunk "not restored"; }
}

@test "SC-6 [bash -c, notty] a recursive delete takes a snapshot first, the line names it, and undo restores it" { check_rm c; }
@test "SC-6 [bash -lc, notty] a recursive delete takes a snapshot first, the line names it, and undo restores it" { check_rm lc; }
@test "SC-6 [bash -ic, notty] a recursive delete takes a snapshot first, the line names it, and undo restores it" { check_rm ic; }

@test "SC-6 [bash -c, notty] a hard reset with uncommitted changes takes a snapshot first; git's output and exit code are its own" {
  local before after
  before="$(manifest)"
  in_repo c "git reset --hard"
  [[ "$status" == 0 ]] || flunk "git reset --hard failed"
  [[ "$output" == *"HEAD is now at "* ]] || flunk "git's own output is missing"
  [[ "$output" == *"timelike: snapshot 1 of ${REPO} taken before git reset --hard: undo 1 --yes puts the workspace back"* ]] ||
    flunk "no line naming the snapshot"
  in_repo c "git reset --hard"
  snapshot_reasons
  [[ "$output" == "before git reset --hard" ]] || flunk "want one snapshot: the second reset had nothing uncommitted"
  in_repo c "undo 1 --yes --text"
  after="$(manifest)"
  [[ "$after" == "$before" ]] || { diff <(echo "$before") <(echo "$after") >&2; flunk "not restored"; }
}

@test "SC-6 [bash -lc, notty] a clean of untracked files takes a snapshot first and keeps what it deletes in the trash" {
  local before after
  before="$(manifest)"
  in_repo lc "git clean -fdx"
  [[ "$status" == 0 && "$output" == *"Removing notes/"* ]] || flunk "git clean -fdx"
  exec_plain test ! -e "${REPO}/build/out.bin" || flunk "git clean did not delete the ignored file"
  [[ "$output" == *"timelike: snapshot 1 of ${REPO} taken before git clean -fdx: undo 1 --yes puts the workspace back"* ]] ||
    flunk "no line naming the snapshot"
  [[ "$output" == *"timelike: trash item 1 keeps "*" undo --trash 1 --yes puts them back"* ]] || flunk "no trash line"
  in_repo lc "undo --trash 1 --yes --text"
  [[ "$status" == 0 ]] || flunk "undo --trash 1 --yes"
  after="$(manifest)"
  [[ "$after" == "$before" ]] || { diff <(echo "$before") <(echo "$after") >&2; flunk "the trash did not put back what clean deleted"; }
}

# remote_setup — a bare remote holding main, then main amended locally so a push of it is not a fast-forward.
remote_setup() {
  exec_plain git init -q --bare "${WORK}/remote.git"
  exec_plain git -C "$REPO" remote add origin "${WORK}/remote.git"
  exec_plain git -C "$REPO" push -q origin main
  PRIOR="$(exec_plain git -C "$REPO" rev-parse HEAD)"
  PRIOR="${PRIOR//$'\r'/}"
  exec_plain git -C "$REPO" commit -q --amend -m "rewritten"
}

remote_main() {
  local s
  s="$(exec_plain git --git-dir "${WORK}/remote.git" rev-parse main)"
  printf '%s' "${s//$'\r'/}"
}

@test "SC-6 [bash -c, notty] a force push takes exactly one snapshot recording the remote's prior commit, and its command puts the ref back" {
  remote_setup
  in_repo c "git push --force -q origin main"
  [[ "$status" == 0 ]] || flunk "git push --force"
  [[ "$(remote_main)" != "$PRIOR" ]] || flunk "the push did not move the remote"
  local putback="git push --force origin ${PRIOR}:refs/heads/main"
  has_line "timelike: forced push: origin refs/heads/main was ${PRIOR}; put it back with: ${putback}" ||
    flunk "no line naming the prior commit and the command"
  snapshot_reasons
  [[ "$output" == "before git push --force origin refs/heads/main" ]] || flunk "want exactly one snapshot, taken before the push"
  exec_plain sh -c 'grep -q "\"prior\": \"$2\"" "$1"/workspaces/*/snaps/1.json' s "$STATE" "$PRIOR" ||
    flunk "the record does not hold the prior commit"
  in_repo c "$putback"
  [[ "$status" == 0 && "$(remote_main)" == "$PRIOR" ]] || flunk "the printed command did not put the ref back"
}

@test "SC-6 [bash -ic, notty] a force push with --no-verify is recorded by the shell's guard, once, from the tracking ref" {
  remote_setup
  in_repo ic "git push --no-verify --force -q origin main"
  [[ "$status" == 0 ]] || flunk "git push --no-verify --force"
  [[ "$output" == *"timelike: forced push: origin refs/heads/main was ${PRIOR} (from the remote-tracking ref, which may be stale)"* ]] ||
    flunk "no line naming the prior commit"
  snapshot_reasons
  [[ "$output" == "before git push --no-verify --force -q origin main" ]] || flunk "want exactly one snapshot"
}

@test "SC-6 [bash -c, notty] a script the agent's shell starts is not guarded: its exit code is its own, and the scheduled snapshot restores what it deleted" {
  local before after id
  before="$(manifest)"
  exec_plain sh -c 'printf "rm -r src\nexit 7\n" >"$1/del.sh"' s "$WORK"
  in_repo c "bash '${WORK}/del.sh'" 0
  [[ "$status" == 7 ]] || flunk "the script's exit code is not its own"
  exec_plain test ! -e "${REPO}/src" || flunk "the script did not delete src/"
  [[ "$output" != *"taken before rm"* ]] || flunk "a script's rm was guarded"
  # Interval 0: the shell's start takes one, and so does the bash it execs for the script (each bash
  # start is a shell start). Every one is scheduled; none was taken by a guard.
  snapshot_reasons
  [[ -n "$output" && "$(printf '%s\n' "${lines[@]}" | sort -u)" == "scheduled" ]] ||
    flunk "want only scheduled snapshots"
  in_repo c "snapshot list --text"
  # The newest snapshot's id: the first row of the list (`<id>  <reason>  …`), found by its form, not
  # its line number.
  id=""
  local l
  for l in "${lines[@]}"; do
    if [[ "$l" =~ ^([0-9]+)\ \ scheduled\ \  ]]; then id="${BASH_REMATCH[1]}"; break; fi
    if [[ "$l" =~ ^[0-9]+\ \  ]]; then break; fi
  done
  [[ -n "$id" ]] || flunk "the newest snapshot is not a scheduled one"
  in_repo c "undo ${id} --yes --text"
  after="$(manifest)"
  [[ "$after" == "$before" ]] || { diff <(echo "$before") <(echo "$after") >&2; flunk "not restored"; }
}

@test "SC-6 [bash -c, notty] a decoy guard and snapshot first on PATH are never what the guard runs (P002)" {
  exec_plain sh -c 'mkdir -p "$1/decoy" && for n in guard snapshot undo; do printf "#!/bin/sh\necho DECOY-%s >&2\n" "$n" >"$1/decoy/$n"; chmod 755 "$1/decoy/$n"; done' s "$WORK"
  in_repo c "PATH='${WORK}/decoy':\$PATH; rm -r src"
  [[ "$status" == 0 && "$output" != *DECOY* ]] || flunk "a decoy ran"
  has_line "timelike: snapshot 1 of ${REPO} taken before rm -r src: undo 1 --yes puts the workspace back" ||
    flunk "the real guard did not run"
}

check_type() {
  in_repo "$1" "type -a rm git"
  [[ "${lines[0]}" == "rm is a function" ]] || flunk "rm is not the guard's function first"
  [[ "$output" == *"rm is /"*"git is a function"*"git is /"* ]] || flunk "type -a does not show each binary after its function"
}

@test "SC-6 [bash -c, notty] type -a shows the guard functions first, then the binaries" { check_type c; }
@test "SC-6 [bash -lc, notty] type -a shows the guard functions first, then the binaries" { check_type lc; }
@test "SC-6 [bash -ic, notty] type -a shows the guard functions first, then the binaries" { check_type ic; }
