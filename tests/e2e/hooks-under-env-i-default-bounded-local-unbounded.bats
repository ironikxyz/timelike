#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# T4's limit under `env -i` (discovery revision 8; feature 001 cycle 6; research R12). No criterion of
# its own: this pins the limitation the revision-8 ruling accepted, "so it cannot widen silently":
#   - a repository using the default `.git/hooks` still runs its hooks bounded, through /etc/gitconfig
#     (system scope is all that is left once `env -i` drops GIT_CONFIG_*);
#   - a repository with a local `core.hooksPath` runs its hooks unbounded, as without timelike (local
#     scope outranks system scope).
# If either case changes, this fails, and the README's paragraph on the limit changes with it.
#
# git runs through the image's real shells and its real /etc/gitconfig (lore cross-stack P005: no
# helper that sets its own environment). After `env -i` the invocation style cannot matter; two styles
# show that it does not.
#
# The unbounded case is unbounded by design, so the TEST bounds it: `timeout -k 1 10` around git, which
# signals git's whole process group, the hook included. Survival and timing are read from files the
# hook writes for itself (its pid, its start second, its last heartbeat second), never from the process
# table, and teardown kills by that pid (cycle 5 process failure 2: never pgrep/pkill -f).

load helpers

LIMIT=2            # timelike.hookTimeout in each fixture repository
GRACE=5            # the dispatcher's `timeout -k 5`: the latest a bounded hook can still be running
WATCHDOG=10        # the test's own bound on the unbounded case, above LIMIT + GRACE

setup_file() {
  stamp_check
}

# prepare_repo KIND — KIND is `default` (.git/hooks) or `local` (core.hooksPath .hooks). A staged file,
# a local identity (env -i drops HOME, so no global config is read), the repository limit, and a
# pre-commit hook that never finishes. The hook writes to absolute paths under ${WORK}/m, because
# `env -i` leaves it no variables to find them by.
prepare_repo() {
  WORK="$(container_tmpdir envihooks)"
  REPO_DIR="${WORK}/repo"
  MARK="${WORK}/m"
  exec_plain sh -c '
    set -eu
    repo=$1 mark=$2 kind=$3 limit=$4
    mkdir -p "$mark"
    git init -q -b main "$repo"
    cd "$repo"
    git config user.name "timelike test"
    git config user.email "test@timelike.invalid"
    git config timelike.hookTimeout "$limit"
    if [ "$kind" = local ]; then
      mkdir .hooks
      git config core.hooksPath .hooks
      hook=.hooks/pre-commit
    else
      hook=.git/hooks/pre-commit
    fi
    printf "%s\n" "#!/bin/sh" \
      "echo \$\$ > $mark/hook.pid" \
      "date +%s > $mark/hook.start" \
      "while :; do date +%s > $mark/hook.last; sleep 0.2; done" > "$hook"
    chmod 0755 "$hook"
    echo content > file.txt
    git add file.txt
  ' envi-fixture "$REPO_DIR" "$MARK" "$1" "$LIMIT" >/dev/null
}

teardown() {
  # Only by the pid the hook wrote for itself.
  if [[ -n "${MARK:-}" ]]; then
    exec_plain sh -c 'p=$(cat "$1/hook.pid" 2>/dev/null) && [ -n "$p" ] && kill -KILL "$p" 2>/dev/null; :' \
      envi-teardown "$MARK" >/dev/null 2>&1 || true
  fi
  container_rm "${WORK:-}"
}

# assert_no_commit — the hook never finished, so no commit exists.
assert_no_commit() {
  run exec_plain git -C "$REPO_DIR" rev-parse -q --verify HEAD
  [[ "$status" -ne 0 ]] || { echo "a commit was made although the hook never finished" >&2; return 1; }
}

# hook_state — one container call reading the hook's own files: started, its start and last-beat
# seconds, whether the heartbeat still moves over 1.5 s, and whether its pid is a live process.
hook_state() {
  run exec_plain sh -c '
    m=$1
    [ -s "$m/hook.pid" ] && echo started=yes || echo started=no
    echo "start=$(cat "$m/hook.start" 2>/dev/null)"
    a=$(cat "$m/hook.last" 2>/dev/null); sleep 1.5; b=$(cat "$m/hook.last" 2>/dev/null)
    echo "last=$b"
    [ "$a" = "$b" ] && echo beating=no || echo beating=yes
    p=$(cat "$m/hook.pid" 2>/dev/null)
    st=""
    [ -n "$p" ] && st=$(sed -n "s/^.*) \(.\).*/\1/p" "/proc/$p/stat" 2>/dev/null)
    case "$st" in "" | Z) echo alive=no ;; *) echo "alive=yes (pid $p state $st)" ;; esac
  ' envi-state "$MARK"
  [[ "$status" -eq 0 ]] || { printf 'reading the hook state failed:\n%s\n' "$output" >&2; return 1; }
}

check_default_bounded() {
  prepare_repo default
  run_in "$1" notty "cd '${REPO_DIR}' && env -i git commit -q -m x"
  assert_within $((LIMIT + GRACE))
  [[ "$status" -ne 0 ]] || { echo "git commit succeeded although its hook never finished" >&2; return 1; }
  local verdict
  verdict="$(grep -m1 '^error: git hook pre-commit ' <<<"$output" || true)"
  [[ -n "$verdict" ]] || { printf 'no timelike verdict under env -i; output:\n%s\n' "$output" >&2; return 1; }
  [[ "$verdict" == *"did not finish within $LIMIT s and was stopped (code 124)"* &&
    "$verdict" == *"the limit is $LIMIT s (git config timelike.hookTimeout)"* ]] ||
    { echo "the verdict does not name the repository's $LIMIT s limit: $verdict" >&2; return 1; }
  assert_no_commit
  hook_state
  assert_value started yes
  assert_value beating no
  assert_value alive no
}

check_local_unbounded() {
  prepare_repo local
  # The watchdog is the test's, not timelike's: under env -i nothing of timelike's bounds this hook.
  run_in "$1" notty "cd '${REPO_DIR}' && s=\$(date +%s); timeout -k 1 $WATCHDOG env -i git commit -q -m x; \
rc=\$?; echo \"git_start=\$s\"; echo \"rc=\$rc\"; exit 0"
  [[ "$status" -eq 0 ]] || { printf 'the command around the watchdog failed (%s):\n%s\n' "$status" "$output" >&2; return 1; }
  assert_value rc 124 # the test's watchdog ended git; timelike did not
  if grep -q '^error: git hook ' <<<"$output"; then
    printf 'a timelike verdict appeared under env -i with a local core.hooksPath (the limit widened?):\n%s\n' \
      "$output" >&2
    return 1
  fi
  local git_start
  git_start="$(value_of git_start)"
  assert_no_commit
  hook_state
  assert_value started yes
  local last
  last="$(value_of last)"
  [[ "$git_start" =~ ^[0-9]+$ && "$last" =~ ^[0-9]+$ ]] ||
    { printf 'unreadable times (git_start=%s last=%s):\n%s\n' "$git_start" "$last" "$output" >&2; return 1; }
  (( last - git_start >= LIMIT + GRACE )) ||
    { echo "the hook's last beat came $((last - git_start)) s after git started, under $((LIMIT + GRACE)) s: it was bounded" >&2; return 1; }
}

@test "T4 under env -i: a repository using .git/hooks still runs its hooks bounded, through /etc/gitconfig [bash -c, notty]" { check_default_bounded c; }
@test "T4 under env -i: a repository using .git/hooks still runs its hooks bounded, through /etc/gitconfig [bash -lc, notty]" { check_default_bounded lc; }
@test "T4 under env -i: a repository with a local core.hooksPath runs its hooks unbounded, as without timelike [bash -c, notty]" { check_local_unbounded c; }
@test "T4 under env -i: a repository with a local core.hooksPath runs its hooks unbounded, as without timelike [bash -lc, notty]" { check_local_unbounded lc; }
