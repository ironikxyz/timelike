#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# SC-4 — "A snapshot whose content would exceed the size cap is refused or partial, and the verdict
# names what was excluded and why". (Feature 005, slice 0; spec FR-6 to FR-8, Scenario 3, D-8;
# tasks.md T006; contracts/recover-cli.md § Environment, Take, Refusals, "Outcomes are verdicts";
# data-model.md § Exclusion.)
#
# Written from the contract before the tools existed. The fixture repository (a few KiB) gains two
# large files: build/big-a.bin (200000 bytes, under an ignored directory) and assets/big-b.bin
# (100000 bytes). With TIMELIKE_SNAPSHOT_MAX_BYTES=50000 the largest-first cut must drop big-a, then
# big-b, and keep everything else. With TIMELIKE_SNAPSHOT_MAX_FILE_BYTES=150000 only big-a is over the
# per-file limit. Every expected count and byte total is measured by the test with find (P004).
#
#   - size cap: partial verdict, each excluded file with its reason (largest first), the raise line
#   - per-file limit: big-a alone, "over the per-file limit", the raise line names the per-file cap
#   - a later undo --yes restores a deleted captured file and leaves the excluded files as they are
#     now (one untouched, one changed after the snapshot): neither restored nor removed
#   - TIMELIKE_SNAPSHOT_MAX_ENTRIES=5: refused (exit 1, a verdict on stdout), nothing stored
#   - a value that is not a non-negative decimal integer: exit 2 naming the variable, nothing stored
# Cells: bash -c and bash -lc, `notty`.

load helpers

FIXTURE=/tmp/recover-repo-sc4.sh
CAP=50000
FILE_CAP=150000

setup_file() {
  stamp_check
  copy_into_container "${BATS_TEST_DIRNAME}/fixtures/recover-repo.sh" "$FIXTURE" 0755
}

setup() {
  WORK="$(container_tmpdir sc4cap)"
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

# COUNTS_SH DIR — files and bytes of the workspace, every .git pruned.
COUNTS_SH='set -eu
cd "$1"
printf "files=%s\n" "$(find . -name .git -prune -o -type f -print | wc -l)"
printf "bytes=%s\n" "$(find . -name .git -prune -o -type f -printf "%s\n" | awk "{s+=\$1} END {print s+0}")"'

# prepare_big — add the two large files; set FILES and BYTES (the whole workspace, measured) and
# check the cap really bites as designed: everything but the two large files fits under CAP.
prepare_big() {
  exec_plain sh -c 'set -eu
    cd "$1"
    mkdir -p build assets
    head -c 200000 /dev/urandom >build/big-a.bin
    head -c 100000 /dev/urandom >assets/big-b.bin' big "$REPO"
  JPY="$(exec_plain sh -c "$COUNTS_SH" counts "$REPO")"
  FILES="$(jval files)"
  BYTES="$(jval bytes)"
  ((BYTES - 300000 < CAP)) || { echo "fixture too large for the cap: ${BYTES} bytes" >&2; return 1; }
}

# excluded_text_lines — the `excluded:` lines of the last run, in order.
excluded_text_lines() {
  local l
  EXCLUDED_LINES=()
  for l in "${lines[@]}"; do
    if [[ "$l" == "excluded: "* ]]; then EXCLUDED_LINES+=("$l"); fi
  done
}

# check_size_cap_partial STYLE — JSON: partial, the measured counts less the two large files, and
# exactly those two excluded with the size-cap reason. Text: their lines largest first, then the
# raise line naming the value that would have captured everything.
check_size_cap_partial() {
  prepare_big
  manifest before

  in_repo "$1" "snapshot" "TIMELIKE_SNAPSHOT_MAX_BYTES=${CAP}"
  expect_status 0
  jfields id partial files bytes excluded_bytes verdict
  expect_j id 1
  expect_j partial true
  expect_j files "$((FILES - 2))"
  expect_j bytes "$((BYTES - 300000))"
  expect_j excluded_bytes 300000
  local verdict
  verdict="$(jval verdict)"
  local re='^snapshot 1 taken \(partial\): ([0-9]+) files, (.+); excluded ([0-9]+) files, (.+) — see below$'
  [[ "$verdict" =~ $re ]] || flunk "verdict is not the partial form: $verdict"
  # size_matches runs its own =~, so keep this match's groups before calling it
  local n_files="${BASH_REMATCH[1]}" captured="${BASH_REMATCH[2]}" n_excl="${BASH_REMATCH[3]}" excl="${BASH_REMATCH[4]}"
  [[ "$n_files" == "$((FILES - 2))" ]] || flunk "verdict names ${n_files} files"
  [[ "$n_excl" == 2 ]] || flunk "verdict names ${n_excl} excluded files, want 2"
  size_matches "$captured" "$((BYTES - 300000))" || flunk "captured size '${captured}' is not $((BYTES - 300000)) bytes"
  size_matches "$excl" 300000 || flunk "excluded size '${excl}' is not 300000 bytes"
  jpy 'for e in sorted(g("excluded"), key=lambda e: e["path"]):
    print(e["path"], e["size"], e["reason"].startswith("over the size cap: largest files left out first ("))'
  [[ "$JPY" == $'assets/big-b.bin 100000 True\nbuild/big-a.bin 200000 True' ]] || flunk "JSON excluded list: $JPY"

  in_repo "$1" "snapshot --text" "TIMELIKE_SNAPSHOT_MAX_BYTES=${CAP}"
  expect_status 0
  excluded_text_lines
  [[ ${#EXCLUDED_LINES[@]} -eq 2 ]] || flunk "want 2 'excluded:' lines, got ${#EXCLUDED_LINES[@]}"
  [[ "${EXCLUDED_LINES[0]}" == "excluded: build/big-a.bin ("*") — over the size cap"* ]] || flunk "first excluded line (largest first): ${EXCLUDED_LINES[0]}"
  [[ "${EXCLUDED_LINES[1]}" == "excluded: assets/big-b.bin ("*") — over the size cap"* ]] || flunk "second excluded line: ${EXCLUDED_LINES[1]}"
  local last="${lines[${#lines[@]} - 1]}"
  # The cap counts bytes new to the store (discovery revision 11): the first run stored everything but
  # the two large files, so this second snapshot would add exactly their 300000 bytes.
  [[ "$last" == *"raise with TIMELIKE_SNAPSHOT_MAX_BYTES=300000"* ]] || flunk "last line does not raise the size cap to 300000 (the bytes new to the store): $last"
  [[ "$last" != *"TIMELIKE_SNAPSHOT_MAX_FILE_BYTES"* ]] || flunk "last line names the per-file cap, which did not bite: $last"

  manifest after
  same_manifest before after
}

# check_per_file_limit STYLE — only big-a is over the per-file limit; the raise line names it.
check_per_file_limit() {
  prepare_big

  in_repo "$1" "snapshot" "TIMELIKE_SNAPSHOT_MAX_FILE_BYTES=${FILE_CAP}"
  expect_status 0
  jfields partial files bytes excluded_bytes
  expect_j partial true
  expect_j files "$((FILES - 1))"
  expect_j bytes "$((BYTES - 200000))"
  expect_j excluded_bytes 200000
  jpy 'for e in g("excluded"):
    print(e["path"], e["size"], e["reason"].startswith("over the per-file limit ("))'
  [[ "$JPY" == "build/big-a.bin 200000 True" ]] || flunk "JSON excluded list: $JPY"

  in_repo "$1" "snapshot --text" "TIMELIKE_SNAPSHOT_MAX_FILE_BYTES=${FILE_CAP}"
  expect_status 0
  excluded_text_lines
  [[ ${#EXCLUDED_LINES[@]} -eq 1 && "${EXCLUDED_LINES[0]}" == "excluded: build/big-a.bin ("*") — over the per-file limit"* ]] \
    || flunk "excluded lines: ${EXCLUDED_LINES[*]}"
  local last="${lines[${#lines[@]} - 1]}"
  [[ "$last" == *"TIMELIKE_SNAPSHOT_MAX_FILE_BYTES=200000"* ]] || flunk "last line does not raise the per-file cap to 200000: $last"
  [[ "$last" != *"TIMELIKE_SNAPSHOT_MAX_BYTES="* ]] || flunk "last line names the size cap, which did not bite: $last"
}

# check_undo_leaves_excluded STYLE — after a partial snapshot, a deleted captured file comes back,
# big-a (untouched) keeps its content, and big-b (changed after the snapshot) keeps its NEW content:
# excluded files are neither restored nor removed. The dry run plans the deleted file alone.
check_undo_leaves_excluded() {
  prepare_big
  local sums_before sums_after main_before main_after
  main_before="$(exec_plain sha256sum "${REPO}/src/main.py")"

  in_repo "$1" "snapshot" "TIMELIKE_SNAPSHOT_MAX_BYTES=${CAP}"
  expect_status 0
  jfields partial
  expect_j partial true

  exec_plain sh -c 'set -eu
    cd "$1"
    rm src/main.py
    head -c 100000 /dev/urandom >assets/big-b.bin' change "$REPO"
  sums_before="$(exec_plain sh -c 'cd "$1" && sha256sum build/big-a.bin assets/big-b.bin' sums "$REPO")"

  in_repo "$1" "undo --dry-run" "TIMELIKE_SNAPSHOT_MAX_BYTES=${CAP}"
  expect_status 0
  jpy 'for e in g("plan"): print(e["change"], e["kind"], e["path"])'
  [[ "$JPY" == "restore file src/main.py" ]] || flunk "dry-run plan, want only 'restore file src/main.py': $JPY"

  in_repo "$1" "undo --yes" "TIMELIKE_SNAPSHOT_MAX_BYTES=${CAP}"
  expect_status 0
  jfields verified restored removed before before_partial verdict
  expect_j verified true
  expect_j restored 1
  expect_j removed 0
  expect_j before 2
  expect_j before_partial true
  expect_j verdict "restored to snapshot 1: 1 restored, 0 removed; verified; the state before is snapshot 2 (partial)"

  main_after="$(exec_plain sha256sum "${REPO}/src/main.py")" || { echo "src/main.py was not restored" >&2; return 1; }
  [[ "$main_after" == "$main_before" ]] || { echo "src/main.py restored with different content" >&2; return 1; }
  sums_after="$(exec_plain sh -c 'cd "$1" && sha256sum build/big-a.bin assets/big-b.bin' sums "$REPO" 2>&1)" \
    || { printf 'an excluded file was removed:\n%s\n' "$sums_after" >&2; return 1; }
  [[ "$sums_after" == "$sums_before" ]] || { printf 'an excluded file was changed by the restore:\nbefore:\n%s\nafter:\n%s\n' "$sums_before" "$sums_after" >&2; return 1; }
}

# no_snapshots_stored STYLE — `snapshot list` (no caps) reports none for this workspace.
no_snapshots_stored() {
  in_repo "$1" "snapshot list"
  expect_status 0
  jfields verdict snapshots
  expect_j verdict "0 snapshots"
  expect_j snapshots "[]"
}

# check_entry_cap_refused STYLE — over the entry cap: exit 1, a verdict on stdout naming the
# workspace, the cap and its variable, the remedy line, and nothing stored.
check_entry_cap_refused() {
  manifest before
  in_repo "$1" "snapshot --text" "TIMELIKE_SNAPSHOT_MAX_ENTRIES=5"
  expect_status 1
  [[ "${lines[0]:-}" == "snapshot: ${REPO_REAL} [take]" ]] || flunk "header line: ${lines[0]:-<none>}"
  [[ "${lines[1]:-}" == "verdict: refused: ${REPO_REAL} has more than 5 entries (TIMELIKE_SNAPSHOT_MAX_ENTRIES)" ]] \
    || flunk "verdict line: ${lines[1]:-<none>}"
  [[ "${lines[2]:-}" == "do instead: snapshot a smaller directory, or raise TIMELIKE_SNAPSHOT_MAX_ENTRIES" ]] \
    || flunk "do-instead line: ${lines[2]:-<none>}"

  in_repo "$1" "snapshot" "TIMELIKE_SNAPSHOT_MAX_ENTRIES=5"
  expect_status 1
  jfields target scope verdict remedy exit
  expect_j target "$REPO_REAL"
  expect_j scope take
  expect_j verdict "refused: ${REPO_REAL} has more than 5 entries (TIMELIKE_SNAPSHOT_MAX_ENTRIES)"
  expect_j remedy "snapshot a smaller directory, or raise TIMELIKE_SNAPSHOT_MAX_ENTRIES"
  expect_j exit 1

  no_snapshots_stored "$1"
  manifest after
  same_manifest before after
}

# check_non_integer_cap STYLE — a cap that is not a non-negative decimal integer is a usage error
# (exit 2) naming the variable, for each of the three variables; nothing is stored.
check_non_integer_cap() {
  local kv
  for kv in TIMELIKE_SNAPSHOT_MAX_BYTES=10MB TIMELIKE_SNAPSHOT_MAX_FILE_BYTES=-1 TIMELIKE_SNAPSHOT_MAX_ENTRIES=1e3; do
    in_repo "$1" "snapshot" "$kv"
    expect_status 2
    local err
    err="$(exec_plain cat "${WORK}/stderr")"
    [[ "$err" == *"${kv%%=*}"* ]] || flunk "the usage error does not name ${kv%%=*}"
  done
  no_snapshots_stored "$1"
}

@test "SC-4 a snapshot whose content would exceed the size cap is partial, and the verdict names what was excluded and why [bash -c, notty]" { check_size_cap_partial c; }
@test "SC-4 a snapshot whose content would exceed the size cap is partial, and the verdict names what was excluded and why [bash -lc, notty]" { check_size_cap_partial lc; }
@test "SC-4 a snapshot whose content would exceed the size cap is partial: a file over the per-file limit is named with its reason [bash -c, notty]" { check_per_file_limit c; }
@test "SC-4 a snapshot whose content would exceed the size cap is partial: a file over the per-file limit is named with its reason [bash -lc, notty]" { check_per_file_limit lc; }
@test "SC-4 a snapshot whose content would exceed the size cap is partial: a later undo --yes leaves the excluded files in place [bash -c, notty]" { check_undo_leaves_excluded c; }
@test "SC-4 a snapshot whose content would exceed the size cap is partial: a later undo --yes leaves the excluded files in place [bash -lc, notty]" { check_undo_leaves_excluded lc; }
@test "SC-4 a snapshot of a workspace over the entry cap is refused with the cap and its variable [bash -c, notty]" { check_entry_cap_refused c; }
@test "SC-4 a snapshot of a workspace over the entry cap is refused with the cap and its variable [bash -lc, notty]" { check_entry_cap_refused lc; }
@test "SC-4 a cap that is not a non-negative decimal integer is a usage error naming the variable [bash -c, notty]" { check_non_integer_cap c; }
@test "SC-4 a cap that is not a non-negative decimal integer is a usage error naming the variable [bash -lc, notty]" { check_non_integer_cap lc; }
