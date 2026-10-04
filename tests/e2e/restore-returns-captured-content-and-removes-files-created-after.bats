#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# SC-2 — "Restoring a snapshot returns every captured file to its captured content and removes files
# created after it, and a dry run lists exactly those changes first". (Feature 005, slice 0; spec
# FR-14 to FR-19, Scenarios 1 and 2, D-1, D-10; tasks.md T004; contracts/recover-cli.md § undo;
# data-model.md § Plan.)
#
# Written from the contract before the tools existed. After a snapshot of the fixture repository the
# test makes five changes itself:
#   - ./rmsrc.sh deletes src/ (a directory removed by a script)  → restore dir src, restore dir src/util,
#                                                                   restore file src/main.py,
#                                                                   restore file src/util/helper.py
#   - an edit of README.md                                       → restore file README.md
#   - chmod 0644 secret.cfg (it was 0600)                        → restore file secret.cfg
#   - a new file notes.txt                                       → remove file notes.txt
#   - a new directory newdir/ holding a.txt                      → remove dir newdir, remove file newdir/a.txt
# The dry run's plan must be exactly that set (6 to restore, 3 to remove), sorted by path. Every
# "nothing changed" and "restored" is decided by the test's own manifest (path, kind, mode, sha256 or
# link target, every .git pruned), never by the tool's message (lore cross-stack P004).
#
# Default `undo` restores the newest snapshot that is not a safety snapshot (FR-14, amended in implement:
# rule 7), so a repeated bare `undo --yes` changes nothing. A safety snapshot is restored by its ID.
# Cells: bash -c and bash -lc, `notty` (output is JSON when piped; --text is passed where text is read).

load helpers

FIXTURE=/tmp/recover-repo-sc2.sh

# The plan the five changes require, in display order (sorted by path; remove before restore).
EXPECTED_PLAN=(
  "restore file README.md"
  "remove dir newdir"
  "remove file newdir/a.txt"
  "remove file notes.txt"
  "restore file secret.cfg"
  "restore dir src"
  "restore file src/main.py"
  "restore dir src/util"
  "restore file src/util/helper.py"
)

setup_file() {
  stamp_check
  copy_into_container "${BATS_TEST_DIRNAME}/fixtures/recover-repo.sh" "$FIXTURE" 0755
}

setup() {
  WORK="$(container_tmpdir sc2undo)"
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

# expect_plan_lines TEXT — TEXT (one plan line per line) is exactly EXPECTED_PLAN, in that order.
expect_plan_lines() {
  local want
  want="$(printf '%s\n' "${EXPECTED_PLAN[@]}")"
  [[ "$1" == "$want" ]] || flunk "$(printf 'plan differs from the changes the test made:\nwant:\n%s\ngot:\n%s' "$want" "$1")"
}

# prepare_changed STYLE — manifest "base", snapshot 1 (through STYLE), the five changes, manifest
# "changed".
prepare_changed() {
  manifest base
  in_repo "$1" "snapshot"
  expect_status 0
  jfields id
  expect_j id 1
  exec_plain sh -c 'set -eu
    cd "$1"
    ./rmsrc.sh
    printf "%s\n" "an edit after the snapshot" >>README.md
    chmod 0644 secret.cfg
    printf "%s\n" "created after the snapshot" >notes.txt
    mkdir newdir
    printf "%s\n" "also created after" >newdir/a.txt' change "$REPO"
  manifest changed
  # the changes happened (the test's own measurement, not the tool's)
  ! same_manifest base changed 2>/dev/null || { echo "the test's changes did not change the workspace" >&2; return 1; }
}

# check_dry_run STYLE — `undo --dry-run` lists exactly the changes, counts them, and changes nothing;
# the text form lists the same lines; `--dry-run` wins over `--yes`.
check_dry_run() {
  prepare_changed "$1"

  in_repo "$1" "undo --dry-run"
  expect_status 0
  jfields tool target scope verdict id restore remove
  expect_j tool undo
  expect_j target "$REPO_REAL"
  expect_j scope "restore 1"
  expect_j id 1
  expect_j restore 6
  expect_j remove 3
  expect_j verdict "dry run: snapshot 1 — 6 to restore, 3 to remove; nothing changed"
  jpy 'for e in g("plan"): print(e["change"], e["kind"], e["path"])'
  expect_plan_lines "$JPY"
  manifest after_dry_run
  same_manifest changed after_dry_run

  in_repo "$1" "undo --dry-run --text"
  expect_status 0
  local l got=()
  for l in "${lines[@]}"; do
    if [[ "$l" =~ ^(restore|remove|keep)\ (file|link|dir)\  ]]; then got+=("$l"); fi
  done
  [[ ${#got[@]} -gt 0 ]] || flunk "the text dry run lists no plan lines"
  expect_plan_lines "$(printf '%s\n' "${got[@]}")"

  in_repo "$1" "undo 1 --dry-run --yes"
  expect_status 0
  jfields verdict
  expect_j verdict "dry run: snapshot 1 — 6 to restore, 3 to remove; nothing changed"
  manifest after_dry_run_yes
  same_manifest changed after_dry_run_yes
}

# check_envelope STYLE — `undo` alone changes nothing and exits 4 with the confirmation envelope: its
# plan is the dry run's lines and its confirm is the agent's own command plus --yes. Running that
# confirm is the one undo command (D-1): it restores.
check_envelope() {
  prepare_changed "$1"

  in_repo "$1" "undo"
  expect_status 4
  jfields tool target scope status confirm
  expect_j tool undo
  expect_j target "$REPO_REAL"
  expect_j scope "restore 1"
  expect_j status confirmation_required
  expect_j confirm "undo --yes"
  jpy 'print("\n".join(g("plan")))'
  expect_plan_lines "$JPY"
  manifest after_envelope
  same_manifest changed after_envelope

  local confirm
  jfields confirm  # jpy above replaced $JPY with the plan; read the envelope's confirm again
  confirm="$(jval confirm)"
  in_repo "$1" "$confirm"
  expect_status 0
  manifest after_confirm
  same_manifest base after_confirm
}

# check_yes_restores STYLE — `undo --yes` returns the workspace to the snapshot exactly, says it
# verified that, and names the safety snapshot it took first (2).
check_yes_restores() {
  prepare_changed "$1"

  in_repo "$1" "undo --yes"
  expect_status 0
  jfields id restored removed verified before before_partial verdict
  expect_j id 1
  expect_j restored 6
  expect_j removed 3
  expect_j verified true
  expect_j before 2
  expect_j before_partial false
  expect_j verdict "restored to snapshot 1: 6 restored, 3 removed; verified; the state before is snapshot 2"
  manifest after_undo
  same_manifest base after_undo
}

# check_restore_that_should_change_nothing STYLE — once restored, a repeated `undo --yes` changes
# nothing, says so, and takes no safety snapshot (rule 7); `undo 1` alone needs no confirmation for an
# empty plan.
check_restore_that_should_change_nothing() {
  prepare_changed "$1"
  in_repo "$1" "undo --yes"
  expect_status 0
  manifest restored

  in_repo "$1" "undo --yes"
  expect_status 0
  jfields verdict
  expect_j verdict "nothing to restore: the workspace matches snapshot 1"
  manifest after_second
  same_manifest restored after_second
  same_manifest base after_second

  in_repo "$1" "undo 1"
  expect_status 0
  jfields verdict
  expect_j verdict "nothing to restore: the workspace matches snapshot 1"

  in_repo "$1" "undo 1 --dry-run"
  expect_status 0
  jfields verdict restore remove
  expect_j verdict "dry run: snapshot 1 — nothing to change"
  expect_j restore 0
  expect_j remove 0

  # no safety snapshot for an empty plan: still only 1 and the first undo's 2
  in_repo "$1" "snapshot list"
  expect_status 0
  jpy 'print(" ".join(str(s["id"]) for s in g("snapshots")))'
  [[ "$JPY" == "2 1" ]] || flunk "snapshot list ids '$JPY', want '2 1' (newest first)"
  manifest after_all
  same_manifest base after_all
}

# check_undo_the_undo STYLE — the safety snapshot is a snapshot like any other: `undo 2 --yes` brings
# the changed state back, and the list records why each was taken, newest first.
check_undo_the_undo() {
  prepare_changed "$1"
  in_repo "$1" "undo --yes"
  expect_status 0
  jfields before
  expect_j before 2

  in_repo "$1" "undo 2 --yes"
  expect_status 0
  jfields id verified before
  expect_j id 2
  expect_j verified true
  expect_j before 3
  manifest after_redo
  same_manifest changed after_redo

  in_repo "$1" "snapshot list"
  expect_status 0
  jfields verdict
  expect_j verdict "3 snapshots"
  jpy 'for s in g("snapshots"): print(s["id"], s["reason"])'
  [[ "$JPY" == $'3 before undo 2\n2 before undo 1\n1 on demand' ]] || flunk "snapshot list: $JPY"
}

@test "SC-2 a dry run lists exactly the changes made after the snapshot and changes nothing [bash -c, notty]" { check_dry_run c; }
@test "SC-2 a dry run lists exactly the changes made after the snapshot and changes nothing [bash -lc, notty]" { check_dry_run lc; }
@test "SC-2 undo alone exits 4 with the confirmation envelope and changes nothing; its confirm restores [bash -c, notty]" { check_envelope c; }
@test "SC-2 undo alone exits 4 with the confirmation envelope and changes nothing; its confirm restores [bash -lc, notty]" { check_envelope lc; }
@test "SC-2 restoring a snapshot returns every captured file to its captured content and removes files created after it [bash -c, notty]" { check_yes_restores c; }
@test "SC-2 restoring a snapshot returns every captured file to its captured content and removes files created after it [bash -lc, notty]" { check_yes_restores lc; }
@test "SC-2 a restore that should change nothing changes nothing and says so [bash -c, notty]" { check_restore_that_should_change_nothing c; }
@test "SC-2 a restore that should change nothing changes nothing and says so [bash -lc, notty]" { check_restore_that_should_change_nothing lc; }
@test "SC-2 undo of the safety snapshot brings the changed state back [bash -c, notty]" { check_undo_the_undo c; }
@test "SC-2 undo of the safety snapshot brings the changed state back [bash -lc, notty]" { check_undo_the_undo lc; }
