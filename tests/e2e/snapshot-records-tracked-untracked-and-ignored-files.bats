#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# SC-1 — "Taking a snapshot records tracked, untracked and ignored-but-not-excluded files of the
# workspace and prints its identifier, file count and size". (Feature 005, slice 0; spec FR-1, FR-4,
# FR-5, FR-9, FR-13, D-3; tasks.md T003; contracts/recover-cli.md § snapshot, Take.)
#
# Written from the contract before the tools existed (tasks.md Phase 2). The test decides by what it
# measures itself (lore cross-stack P004): the file count, byte total, link and directory counts come
# from `find` over the workspace with every `.git` pruned, and a restore is judged by sha256sum and a
# full manifest (path, kind, mode, sha256 or link target), never by the tool's message.
#
# The repository is built by git (fixtures/recover-repo.sh, P005). Each test gets its own store:
# TIMELIKE_SCRATCH_ROOT is a sibling of the repository, never inside it (FR-3 would refuse that).
# Cells: bash -c and bash -lc, `notty` (the harness's own invocation; output is JSON by default).

load helpers

FIXTURE=/tmp/recover-repo-sc1.sh

setup_file() {
  stamp_check
  copy_into_container "${BATS_TEST_DIRNAME}/fixtures/recover-repo.sh" "$FIXTURE" 0755
}

setup() {
  WORK="$(container_tmpdir sc1snap)"
  REPO="${WORK}/repo"
  SCRATCH="${WORK}/scratch"
  exec_plain sh "$FIXTURE" "$REPO" >/dev/null
  REPO_REAL="$(exec_plain realpath "$REPO")"
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

# COUNTS_SH DIR — files, bytes, links and dirs of the workspace, every .git pruned (FR-4, FR-5).
COUNTS_SH='set -eu
cd "$1"
printf "files=%s\n" "$(find . -name .git -prune -o -type f -print | wc -l)"
printf "bytes=%s\n" "$(find . -name .git -prune -o -type f -printf "%s\n" | awk "{s+=\$1} END {print s+0}")"
printf "links=%s\n" "$(find . -name .git -prune -o -type l -print | wc -l)"
printf "dirs=%s\n" "$(find . -mindepth 1 -name .git -prune -o -type d -print | wc -l)"'

# ── checks ────────────────────────────────────────────────────────────────────────────────────

# check_take STYLE — `snapshot` exits 0; its verdict names snapshot 1, the file count and the size
# the test measured; the JSON counts agree; nothing is excluded; the workspace is unchanged (FR-13).
check_take() {
  manifest before
  local counts files bytes links dirs
  counts="$(exec_plain sh -c "$COUNTS_SH" counts "$REPO")"
  JPY="$counts"
  files="$(jval files)"
  bytes="$(jval bytes)"
  links="$(jval links)"
  dirs="$(jval dirs)"
  # the fixture's own shape: tracked, untracked, ignored and nested files are all in the count
  ((files >= 11)) || { echo "fixture has only ${files} files outside .git" >&2; return 1; }

  in_repo "$1" "snapshot"
  expect_status 0
  jfields tool target scope verdict id reason files links dirs bytes partial excluded excluded_bytes
  expect_j tool snapshot
  expect_j target "$REPO_REAL"
  expect_j scope take
  expect_j id 1
  expect_j reason "on demand"
  expect_j files "$files"
  expect_j bytes "$bytes"
  expect_j links "$links"
  expect_j dirs "$dirs"
  expect_j partial false
  expect_j excluded "[]"
  expect_j excluded_bytes 0

  local verdict
  verdict="$(jval verdict)"
  [[ "$verdict" =~ ^snapshot\ 1\ taken:\ ([0-9]+)\ files,\ (.+)\ \(complete\)$ ]] \
    || flunk "verdict is not 'snapshot 1 taken: <F> files, <size> (complete)': $verdict"
  [[ "${BASH_REMATCH[1]}" == "$files" ]] || flunk "verdict names ${BASH_REMATCH[1]} files, the workspace has $files"
  size_matches "${BASH_REMATCH[2]}" "$bytes" || flunk "verdict size '${BASH_REMATCH[2]}' is not ${bytes} bytes"

  manifest after
  same_manifest before after
}

# check_restore_three_kinds STYLE — delete one tracked, one untracked and one ignored file; `undo 1
# --yes` brings each back byte-identical, and the whole workspace matches the manifest before.
check_restore_three_kinds() {
  local kinds
  # the three kinds, as git itself sees them
  kinds="$(exec_plain sh -c 'cd "$1" &&
    git ls-files --error-unmatch src/main.py >/dev/null && echo tracked
    [ -z "$(git ls-files notes/todo.txt)" ] && echo untracked
    git check-ignore -q build/out.bin && echo ignored' kinds "$REPO")"
  [[ "$kinds" == $'tracked\nuntracked\nignored' ]] || { echo "fixture kinds wrong: $kinds" >&2; return 1; }

  manifest before
  local sums_before sums_after
  sums_before="$(exec_plain sh -c 'cd "$1" && sha256sum src/main.py notes/todo.txt build/out.bin' sums "$REPO")"

  in_repo "$1" "snapshot"
  expect_status 0
  exec_plain sh -c 'cd "$1" && rm src/main.py notes/todo.txt build/out.bin' del "$REPO"

  in_repo "$1" "undo 1 --yes"
  expect_status 0
  jfields id verified
  expect_j id 1
  expect_j verified true

  sums_after="$(exec_plain sh -c 'cd "$1" && sha256sum src/main.py notes/todo.txt build/out.bin' sums "$REPO" 2>&1)" \
    || { printf 'a deleted file was not restored:\n%s\n' "$sums_after" >&2; return 1; }
  [[ "$sums_after" == "$sums_before" ]] || { printf 'restored content differs:\nbefore:\n%s\nafter:\n%s\n' "$sums_before" "$sums_after" >&2; return 1; }
  manifest after
  same_manifest before after
}

@test "SC-1 taking a snapshot records tracked, untracked and ignored-but-not-excluded files of the workspace and prints its identifier, file count and size [bash -c, notty]" { check_take c; }
@test "SC-1 taking a snapshot records tracked, untracked and ignored-but-not-excluded files of the workspace and prints its identifier, file count and size [bash -lc, notty]" { check_take lc; }
@test "SC-1 taking a snapshot records tracked, untracked and ignored-but-not-excluded files: a deleted tracked, untracked and ignored file each come back byte-identical [bash -c, notty]" { check_restore_three_kinds c; }
@test "SC-1 taking a snapshot records tracked, untracked and ignored-but-not-excluded files: a deleted tracked, untracked and ignored file each come back byte-identical [bash -lc, notty]" { check_restore_three_kinds lc; }
