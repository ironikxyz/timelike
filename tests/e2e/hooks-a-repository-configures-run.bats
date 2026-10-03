#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# SC-12 — "The hooks a repository configures (its core.hooksPath, or .git/hooks) run under git commands,
# and a commit a pre-commit hook rejects fails with the hook's output, as it would without timelike."
# (Cycle 5, discovery revision 7, tension T4; spec FR-19; research R11. Replaces SC-3's struck hooks
# clause, whose tests asserted the opposite.)
#
# Driven from outside, per invocation style (bash -c, bash -lc, bash -ic), in `notty`: a terminal does
# not change whether git runs a hook, and the harness has none. Artefacts decide: each hook writes a
# marker file, and the commit's existence is read from git, not from a message (lore cross-stack P004).
#
#   - husky's shape: a LOCAL core.hooksPath (.husky) with a pre-commit that refuses → the commit fails
#     with the hook's own output, the marker is written, and no commit exists
#   - git's default location, .git/hooks and no core.hooksPath: five hook types across a commit and a
#     checkout (what `pre-commit install` and git-lfs write) → every marker is written
#   - a passing hook lets the commit through

load helpers

setup_file() {
  stamp_check
}

# prepare_husky_repo — a staged file, a refusing pre-commit in .husky, and a LOCAL core.hooksPath.
prepare_husky_repo() {
  WORK="$(container_tmpdir sc12husky)"
  REPO_DIR="${WORK}/repo"
  exec_plain sh -c '
    set -eu
    git init -q -b main "$1"
    cd "$1"
    git config user.name "timelike test"
    git config user.email "test@timelike.invalid"
    mkdir .husky
    printf "%s\n" "#!/bin/sh" ": > .git/hook-ran" "echo \"pre-commit: refused by the repository hook\" >&2" "exit 1" > .husky/pre-commit
    chmod 0755 .husky/pre-commit
    git config core.hooksPath .husky
    echo content > file.txt
    git add file.txt
  ' sc12-husky "$REPO_DIR" >/dev/null
}

check_rejecting_hook_runs() {
  prepare_husky_repo
  run_in "$1" notty "cd '${REPO_DIR}' && git commit -q -m x"
  assert_within 20
  [[ "$status" -ne 0 ]] || { printf 'the refusing hook did not stop the commit; output:\n%s\n' "$output" >&2; return 1; }
  assert_output_has "pre-commit: refused by the repository hook"
  run exec_plain test -e "${REPO_DIR}/.git/hook-ran"
  [[ "$status" -eq 0 ]] || { echo "the repository's pre-commit hook did not run (no marker)" >&2; return 1; }
  run exec_plain git -C "$REPO_DIR" rev-parse -q --verify HEAD
  [[ "$status" -ne 0 ]] || { echo "a commit was made although the hook refused" >&2; return 1; }
}

# DEFAULT_HOOKS — hook types a commit and a checkout fire, each writing .git/hook-ran-<name>.
DEFAULT_HOOKS=(pre-commit prepare-commit-msg commit-msg post-commit post-checkout)

prepare_default_hooks_repo() {
  WORK="$(container_tmpdir sc12dhooks)"
  REPO_DIR="${WORK}/repo"
  exec_plain sh -c '
    set -eu
    git init -q -b main "$1"
    cd "$1"
    git config user.name "timelike test"
    git config user.email "test@timelike.invalid"
    shift
    for h in "$@"; do
      printf "%s\n" "#!/bin/sh" ": > .git/hook-ran-$h" > ".git/hooks/$h"
      chmod 0755 ".git/hooks/$h"
    done
    if git config --local --get core.hooksPath; then echo "fixture: local core.hooksPath is set" >&2; exit 1; fi
    echo content > file.txt
    git add file.txt
  ' sc12-dhooks "$REPO_DIR" "${DEFAULT_HOOKS[@]}" >/dev/null
}

check_default_location_hooks_run() {
  prepare_default_hooks_repo
  run_in "$1" notty "cd '${REPO_DIR}' && git commit -q -m x && git checkout -q -b other"
  assert_within 20
  assert_status 0
  run exec_plain sh -c 'cd "$1/.git" && ls | grep "^hook-ran-" || true' sc12 "$REPO_DIR"
  local h
  for h in "${DEFAULT_HOOKS[@]}"; do
    [[ " ${lines[*]} " == *" hook-ran-${h} "* ]] || { echo "the $h hook in .git/hooks did not run" >&2; return 1; }
  done
}

check_passing_hook_lets_commit_through() {
  prepare_default_hooks_repo
  run_in "$1" notty "cd '${REPO_DIR}' && git commit -q -m x"
  assert_within 20
  assert_status 0
  run exec_plain git -C "$REPO_DIR" rev-list --count HEAD
  [[ "$output" == 1 ]] || { echo "expected one commit, rev-list says '$output'" >&2; return 1; }
}

@test "SC-12 the hooks a repository configures run under git commands, and a commit a pre-commit hook rejects fails with the hook's output: local core.hooksPath [bash -c, notty]" { check_rejecting_hook_runs c; }
@test "SC-12 the hooks a repository configures run under git commands, and a commit a pre-commit hook rejects fails with the hook's output: local core.hooksPath [bash -lc, notty]" { check_rejecting_hook_runs lc; }
@test "SC-12 the hooks a repository configures run under git commands, and a commit a pre-commit hook rejects fails with the hook's output: local core.hooksPath [bash -ic, notty]" { check_rejecting_hook_runs ic; }
@test "SC-12 the hooks a repository configures run under git commands: default .git/hooks location, five hook types [bash -c, notty]" { check_default_location_hooks_run c; }
@test "SC-12 the hooks a repository configures run under git commands: default .git/hooks location, five hook types [bash -lc, notty]" { check_default_location_hooks_run lc; }
@test "SC-12 the hooks a repository configures run under git commands: default .git/hooks location, five hook types [bash -ic, notty]" { check_default_location_hooks_run ic; }
@test "SC-12 the hooks a repository configures run under git commands: a passing hook lets the commit through [bash -c, notty]" { check_passing_hook_lets_commit_through c; }
