#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# SC-3 — "The project's own version-control history, index and stash are unchanged by taking or
# restoring a snapshot". (Feature 005, slice 0; spec FR-5, FR-20, Scenario 5, D-4, D-5; tasks.md T005;
# data-model.md § What the walk sees.)
#
# Written from the contract before the tools existed. The test measures `.git` itself (lore
# cross-stack P004): every entry under every `.git` at any depth (the repository's and the nested
# vendor/lib's), with its kind, mode and sha256, plus `git log`, `git stash list` and `git diff
# --cached` of the outer repository and `git log` of the nested one. Git is read with
# GIT_OPTIONAL_LOCKS=0, so the reads themselves never refresh the index. The repository's own
# .git/hooks/pre-commit writes a marker beside the repository if it ever runs: it must never run.
#
#   - snapshot: .git is byte-identical before and after
#   - undo --yes after a script deleted src/ and new files appeared: .git byte-identical again
#   - a change git makes AFTER the snapshot (a tag) survives undo --yes: .git is out of scope, so a
#     restore neither captures nor rewinds it (FR-5)
# Cells: bash -c and bash -lc, `notty`.

load helpers

FIXTURE=/tmp/recover-repo-sc3.sh

setup_file() {
  stamp_check
  copy_into_container "${BATS_TEST_DIRNAME}/fixtures/recover-repo.sh" "$FIXTURE" 0755
}

setup() {
  WORK="$(container_tmpdir sc3git)"
  REPO="${WORK}/repo"
  SCRATCH="${WORK}/scratch"
  exec_plain sh "$FIXTURE" "$REPO" >/dev/null
}

teardown() {
  container_rm "$WORK"
}

# ── helpers (this file's own; the five 005 files repeat them so each reads alone) ────────────────

# in_repo STYLE CMD [K=V]... — run CMD in the repository with this test's store; stderr goes to
# $WORK/stderr so stdout stays one JSON document.
in_repo() {
  local style="$1" cmd="$2" kv
  shift 2
  local -a envs=(-e "TIMELIKE_SCRATCH_ROOT=${SCRATCH}" -e "TIMELIKE_SESSION=recover")
  for kv in "$@"; do envs+=(-e "$kv"); done
  run_in "${envs[@]}" "$style" notty "cd '${REPO}' && ${cmd} 2>'${WORK}/stderr'"
  assert_within 20
}

# flunk MESSAGE — fail with the last run's exit, stdout and stderr.
flunk() {
  local err
  err="$(exec_plain cat "${WORK}/stderr" 2>&1)" || true
  printf '%s\nexit %s; stdout:\n%s\nstderr:\n%s\n' "$1" "$status" "$output" "$err" >&2
  return 1
}

expect_status() {
  [[ "$status" == "$1" ]] || flunk "expected exit $1, got $status"
}

# jpy SCRIPT — Python over the last run's stdout, parsed as JSON into `d`; `g(k)` reads a result
# field whether it is top-level (agentio merges `data`) or under `data`. Output in $JPY.
jpy() {
  JPY="$(printf '%s' "$output" | pyq "import json,sys
d=json.load(sys.stdin)
def g(k, default='<absent>'):
    if k in d: return d[k]
    return (d.get('data') or {}).get(k, default)
$1")" || flunk "stdout is not the JSON expected"
}

# jfields KEY... — KEY=VALUE lines into $JPY (strings raw, everything else as JSON).
jfields() {
  local ks
  ks="$(printf '"%s",' "$@")"
  jpy "for k in [${ks}]:
    v = g(k)
    print(k + '=' + (v if isinstance(v, str) else json.dumps(v, sort_keys=True)))"
}

jval() {
  local line
  while IFS= read -r line; do
    if [[ "$line" == "$1="* ]]; then
      printf '%s' "${line#"$1="}"
      return 0
    fi
  done <<<"$JPY"
  printf '<absent>'
}

expect_j() {
  local got
  got="$(jval "$1")"
  [[ "$got" == "$2" ]] || flunk "$1: expected '$2', got '$got'"
}

# size_matches TEXT BYTES — TEXT is the contract's human-readable form of BYTES: "<n> B" below
# 1 KiB, else one decimal in the largest binary unit that keeps the number at least 1. Rounding or
# truncating to the tenth are both accepted (the contract does not say which).
size_matches() {
  local text="$1" bytes="$2" factor tenths exact
  if [[ "$text" =~ ^([0-9]+)\ B$ ]]; then
    ((bytes < 1024)) && [[ "${BASH_REMATCH[1]}" == "$bytes" ]]
    return
  fi
  [[ "$text" =~ ^([0-9]+)\.([0-9])\ (KiB|MiB|GiB)$ ]] || return 1
  case "${BASH_REMATCH[3]}" in
    KiB) factor=1024 ;;
    MiB) factor=1048576 ;;
    GiB) factor=1073741824 ;;
  esac
  ((bytes >= factor)) || return 1
  [[ "$factor" == 1073741824 ]] || ((bytes < factor * 1024)) || return 1
  tenths=$((10#${BASH_REMATCH[1]} * 10 + 10#${BASH_REMATCH[2]}))
  exact=$((bytes * 10 / factor))
  ((tenths == exact || tenths == exact + 1))
}

# MANIFEST_SH DIR OUT — every entry of the workspace outside every .git (at any depth): kind, path,
# mode, and sha256 for a file or the target for a link. The workspace root itself is not an entry.
MANIFEST_SH='set -eu
cd "$1"
find . -mindepth 1 -name .git -prune -o -print | LC_ALL=C sort | while IFS= read -r p; do
  if [ -L "$p" ]; then printf "link %s -> %s\n" "$p" "$(readlink "$p")"
  elif [ -d "$p" ]; then printf "dir %s %s\n" "$p" "$(stat -c %a "$p")"
  elif [ -f "$p" ]; then printf "file %s %s %s\n" "$p" "$(stat -c %a "$p")" "$(sha256sum <"$p" | cut -d" " -f1)"
  else printf "other %s\n" "$p"; fi
done >"$2"'

# manifest NAME — write the workspace manifest to $WORK/NAME.manifest (outside the workspace).
manifest() {
  exec_plain sh -c "$MANIFEST_SH" manifest "$REPO" "${WORK}/$1.manifest"
}

# same_manifest A B — the two manifests are identical.
same_manifest() {
  local d
  d="$(exec_plain diff -u "${WORK}/$1.manifest" "${WORK}/$2.manifest" 2>&1)" && return 0
  printf 'workspace manifest "%s" differs from "%s":\n%s\n' "$2" "$1" "$d" >&2
  return 1
}

# GIT_MANIFEST_SH DIR OUT — every entry under every .git in DIR (path, kind, mode, sha256 or link
# target), then the outer repository's history, stash and staged diff and the nested one's history.
GIT_MANIFEST_SH='set -eu
cd "$1"
{
  find . \( -name .git -o -path "*/.git/*" \) -print | LC_ALL=C sort | while IFS= read -r p; do
    if [ -L "$p" ]; then printf "link %s -> %s\n" "$p" "$(readlink "$p")"
    elif [ -d "$p" ]; then printf "dir %s %s\n" "$p" "$(stat -c %a "$p")"
    elif [ -f "$p" ]; then printf "file %s %s %s\n" "$p" "$(stat -c %a "$p")" "$(sha256sum <"$p" | cut -d" " -f1)"
    else printf "other %s\n" "$p"; fi
  done
  echo "== git log"
  git --no-pager log --format=%H
  echo "== git stash list"
  git --no-pager stash list
  echo "== git diff --cached"
  git --no-pager diff --cached
  echo "== vendor/lib git log"
  git -C vendor/lib --no-pager log --format=%H
} >"$2"'

# git_manifest NAME — write the .git manifest to $WORK/NAME.git (outside the workspace).
git_manifest() {
  exec_plain env GIT_OPTIONAL_LOCKS=0 sh -c "$GIT_MANIFEST_SH" git-manifest "$REPO" "${WORK}/$1.git"
}

# same_git A B — the two .git manifests are identical.
same_git() {
  local d
  d="$(exec_plain diff -u "${WORK}/$1.git" "${WORK}/$2.git" 2>&1)" && return 0
  printf '.git manifest "%s" differs from "%s":\n%s\n' "$2" "$1" "$d" >&2
  return 1
}

# no_hook_marker — the repository's pre-commit hook never ran.
no_hook_marker() {
  if exec_plain test -e "${WORK}/hook-ran"; then
    echo "the repository's pre-commit hook ran (marker ${WORK}/hook-ran exists)" >&2
    return 1
  fi
}

# fixture_git_shape — the manifest really covers what SC-3 names: two commits, a stash entry, a
# staged change, the hook, and the nested repository's .git.
fixture_git_shape() {
  local m
  m="$(exec_plain cat "${WORK}/$1.git")"
  [[ "$m" == *"file ./.git/index "* ]] || { echo "no .git/index in the manifest" >&2; return 1; }
  [[ "$m" == *"file ./.git/hooks/pre-commit 755 "* ]] || { echo "no executable .git/hooks/pre-commit in the manifest" >&2; return 1; }
  [[ "$m" == *"file ./vendor/lib/.git/HEAD "* ]] || { echo "the nested repository's .git is not in the manifest" >&2; return 1; }
  [[ "$m" == *$'== git stash list\nstash@{0}: '* ]] || { echo "no stash entry in the manifest" >&2; return 1; }
  [[ "$m" == *"+Staged line."* ]] || { echo "no staged change in the manifest" >&2; return 1; }
}

# change_workspace — a script deletes src/, a file is edited and new files appear (outside .git).
change_workspace() {
  exec_plain sh -c 'set -eu
    cd "$1"
    ./rmsrc.sh
    printf "%s\n" "an edit after the snapshot" >>README.md
    printf "%s\n" "created after the snapshot" >notes.txt
    mkdir -p newdir && printf "%s\n" "x" >newdir/a.txt' change "$REPO"
}

# check_snapshot_and_restore_leave_git STYLE — .git identical before snapshot, after it, and after a
# restore that had real work to do; the workspace itself is restored (so the restore did run).
check_snapshot_and_restore_leave_git() {
  git_manifest g0
  fixture_git_shape g0
  manifest w0

  in_repo "$1" "snapshot"
  expect_status 0
  git_manifest g1
  same_git g0 g1

  change_workspace
  git_manifest g2
  same_git g0 g2

  in_repo "$1" "undo --yes"
  expect_status 0
  jfields verified
  expect_j verified true
  git_manifest g3
  same_git g0 g3
  manifest w3
  same_manifest w0 w3
  no_hook_marker
}

# check_git_change_after_snapshot_survives STYLE — a tag made after the snapshot is still there after
# undo --yes, and .git equals its state just before the undo, not the snapshot's.
check_git_change_after_snapshot_survives() {
  in_repo "$1" "snapshot"
  expect_status 0
  exec_plain git -C "$REPO" tag after-snapshot
  git_manifest tagged
  local m
  m="$(exec_plain cat "${WORK}/tagged.git")"
  [[ "$m" == *"./.git/refs/tags/after-snapshot "* ]] || { echo "the tag was not written as a loose ref" >&2; return 1; }

  change_workspace
  in_repo "$1" "undo --yes"
  expect_status 0
  git_manifest after_undo
  same_git tagged after_undo
  no_hook_marker
}

@test "SC-3 the project's own version-control history, index and stash are unchanged by taking or restoring a snapshot [bash -c, notty]" { check_snapshot_and_restore_leave_git c; }
@test "SC-3 the project's own version-control history, index and stash are unchanged by taking or restoring a snapshot [bash -lc, notty]" { check_snapshot_and_restore_leave_git lc; }
@test "SC-3 the project's own version-control state is out of scope: a change git made after the snapshot survives the restore [bash -c, notty]" { check_git_change_after_snapshot_survives c; }
@test "SC-3 the project's own version-control state is out of scope: a change git made after the snapshot survives the restore [bash -lc, notty]" { check_git_change_after_snapshot_survives lc; }
