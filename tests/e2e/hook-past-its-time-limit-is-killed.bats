#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# SC-13 — "A hook that runs past its time limit is killed and the git command exits non-zero within the
# limit plus a few seconds, with a verdict naming the hook, the limit and how to raise it, and never
# suggesting a way to skip the hook." (Cycle 5, discovery revision 7, tension T4; spec FR-20; research R11.)
#
# The fixture hook starts a background child that would write .git/survived three seconds after the
# limit, then sleeps far past it. Artefacts decide: the commit does not exist, and the child's marker
# never appears, so the whole process group was stopped (lore cross-stack P004).
#
# The limit comes from each place the verdict names: the repository (git config timelike.hookTimeout),
# the environment (TIMELIKE_HOOK_TIMEOUT), and the 60 s default. The default case needs the runner's
# per-command limit raised above 60 s, which is local to that test.
# Per invocation style in `notty` (a terminal does not change whether a hook runs or how it is stopped).

load helpers

SKIP_WORDS='--no-verify| -n |hooksPath|skip|bypass|disable'

setup_file() {
  stamp_check
}

# prepare_hanging_repo EFFECTIVE_LIMIT [REPO_LIMIT] — a staged file and a pre-commit hook that never
# finishes. Its background child writes .git/survived three seconds after EFFECTIVE_LIMIT (computed
# here, when the fixture is built). REPO_LIMIT, if given, is set as timelike.hookTimeout.
prepare_hanging_repo() {
  WORK="$(container_tmpdir sc13hang)"
  REPO_DIR="${WORK}/repo"
  exec_plain sh -c '
    set -eu
    git init -q -b main "$1"
    cd "$1"
    git config user.name "timelike test"
    git config user.email "test@timelike.invalid"
    [ -z "$3" ] || git config timelike.hookTimeout "$3"
    printf "%s\n" "#!/bin/sh" "(sleep $(($2 + 3)); : > .git/survived) &" "sleep 600" > .git/hooks/pre-commit
    chmod 0755 .git/hooks/pre-commit
    echo content > file.txt
    git add file.txt
  ' sc13-hang "$REPO_DIR" "$1" "${2:-}" >/dev/null
}

# assert_verdict LIMIT SOURCE — the one-line verdict names the hook, the limit, its source and both
# ways to raise it, and suggests no way to skip the hook.
assert_verdict() {
  local line
  line="$(grep -m1 '^error: git hook pre-commit ' <<<"$output" || true)"
  [[ -n "$line" ]] || { printf 'no verdict line; output:\n%s\n' "$output" >&2; return 1; }
  [[ "$line" == *"did not finish within $1 s and was stopped (code 124)"* ]] || { echo "verdict does not name the limit: $line" >&2; return 1; }
  [[ "$line" == *"the limit is $1 s ($2)"* ]] || { echo "verdict does not name the limit's source: $line" >&2; return 1; }
  [[ "$line" == *"TIMELIKE_HOOK_TIMEOUT=<seconds>"* && "$line" == *"git config timelike.hookTimeout <seconds>"* ]] \
    || { echo "verdict does not say how to raise the limit: $line" >&2; return 1; }
  if grep -qiE -- "$SKIP_WORDS" <<<"$output"; then
    printf 'the output suggests a way to skip the hook:\n%s\n' "$output" >&2
    return 1
  fi
}

# assert_stopped LIMIT — no commit was made, and the hook's background child did not survive.
assert_stopped() {
  run exec_plain git -C "$REPO_DIR" rev-parse -q --verify HEAD
  [[ "$status" -ne 0 ]] || { echo "a commit was made although the hook never finished" >&2; return 1; }
  sleep 4 # the child would have written its marker 3 s after the limit
  run exec_plain test -e "${REPO_DIR}/.git/survived"
  [[ "$status" -ne 0 ]] || { echo "the hook's background child outlived the limit" >&2; return 1; }
}

check_repository_limit() {
  prepare_hanging_repo 3 3
  run_in "$1" notty "cd '${REPO_DIR}' && git commit -q -m x"
  assert_within $((3 + 5))
  [[ "$status" -ne 0 ]] || { echo "git commit succeeded although its hook never finished" >&2; return 1; }
  assert_verdict 3 "git config timelike.hookTimeout"
  assert_stopped
}

check_environment_limit() {
  prepare_hanging_repo 2
  run_in "$1" notty "cd '${REPO_DIR}' && TIMELIKE_HOOK_TIMEOUT=2 git commit -q -m x"
  assert_within $((2 + 5))
  [[ "$status" -ne 0 ]] || { echo "git commit succeeded although its hook never finished" >&2; return 1; }
  assert_verdict 2 TIMELIKE_HOOK_TIMEOUT
  assert_stopped
}

check_default_limit() {
  # shellcheck disable=SC2034 # read by run_in/exec_in in helpers.bash
  local RUN_TIMEOUT=90 # above the 60 s default, below Claude Code's 120 s call timeout
  prepare_hanging_repo 60
  run_in "$1" notty "cd '${REPO_DIR}' && git commit -q -m x"
  assert_within $((60 + 5))
  [[ "$status" -ne 0 ]] || { echo "git commit succeeded although its hook never finished" >&2; return 1; }
  assert_verdict 60 "the default"
  assert_stopped
}

@test "SC-13 a hook that runs past its time limit is killed and the git command exits non-zero within the limit plus a few seconds, with a verdict: repository limit [bash -c, notty]" { check_repository_limit c; }
@test "SC-13 a hook that runs past its time limit is killed and the git command exits non-zero within the limit plus a few seconds, with a verdict: repository limit [bash -lc, notty]" { check_repository_limit lc; }
@test "SC-13 a hook that runs past its time limit is killed and the git command exits non-zero within the limit plus a few seconds, with a verdict: repository limit [bash -ic, notty]" { check_repository_limit ic; }
@test "SC-13 a hook that runs past its time limit is killed and the git command exits non-zero within the limit plus a few seconds, with a verdict: environment limit [bash -c, notty]" { check_environment_limit c; }
@test "SC-13 a hook that runs past its time limit is killed and the git command exits non-zero within the limit plus a few seconds, with a verdict: the 60 s default [bash -c, notty]" { check_default_limit c; }
