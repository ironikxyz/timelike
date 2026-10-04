#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# shellcheck disable=SC2030,SC2031 # setup_file exports; bats runs each @test in its own subshell by design
# SC-9 — "A command that fails because the scratch or workspace filesystem is full produces a verdict
# naming the full filesystem and its free space". (Feature 003, slice 1; spec FR-29 to FR-31,
# Scenario 6; contracts/run-cli.md § Slice 1; research R17.)
#
# Both cases run in throwaway containers from the verified image (helpers.bash start_throwaway), each
# with one small tmpfs, so a full filesystem is made on purpose and nothing else in the lane fills:
#   workspace  --tmpfs /work:size=1m,mode=1777. The current directory is /work and `dd` writes 4 MiB
#              into it, so dd fails on ENOSPC (exit 1) and leaves its partial file (R17), and /work
#              reads 0 B free.
#   scratch    --tmpfs /scratch:size=256k,mode=1777, and TIMELIKE_SCRATCH_ROOT=/scratch passed to the
#              docker exec (it is this criterion's input, so `-e` is legitimate here). The command
#              writes about 2 MB to stdout, which is run's log on /scratch: the write fails, the
#              command exits non-zero, and the verdict must also say the log may be incomplete (FR-31).
#              A 256 KiB filesystem is below `disk_full_bytes` (1 MiB) even when empty, so by FR-30 it
#              is full from the start; the command failing on its write is what makes the case real.
# mode=1777: Docker's tmpfs is root-owned, and the image runs as the unprivileged agent (uid 1000), so
# without it the agent could not write to /work or create its session directory under /scratch. Both
# are read back before they are relied on (lore cross-stack P001): the size from statvfs, the mode
# from stat, and a write by the agent user. A precondition that does not hold makes that case's tests
# FAIL with the reason, never skip.
#
# Artefacts decide: the exit status docker exec reports, the JSON result read as data in the
# throwaway (slice 0 puts `data`'s fields at the top level, so `data.disk` is the key `disk`), and the
# free space read back with statvfs after the command. The verdict's free space is checked against JSON
# `free_bytes`, formatted by the contract's size rule (below 1 KiB an integer `B`, otherwise one decimal
# in KiB/MiB/GiB/TiB).
# Cells: bash -c and bash -lc in `notty`.

load helpers

# at_most VALUE MAX — VALUE is a non-negative integer and at most MAX.
at_most() { [[ "$1" =~ ^[0-9]+$ ]] && (($1 <= $2)); }

FULL_BYTES=1048576       # contracts/run-cli.md: disk_full_bytes, the default
WORK_SIZE=1048576        # --tmpfs /work:size=1m
SCRATCH_SIZE=262144      # --tmpfs /scratch:size=256k

# Prints JSON fields as PATH=VALUE lines, read in the container (the runner has no python or jq).
# PATH is dotted; `key=value` selects the first list element whose key equals value. A prefix
# `size:` formats an integer by the contract's size rule, `len:` gives a length, `sorted:` a sorted
# JSON list. Strings print raw, everything else as JSON (true, null, 3); an absent path is <absent>.
JSON_PATHS_PY="$(
  cat <<'PY'
import json
import sys

ABSENT = object()


def size(n):
    if not isinstance(n, int) or isinstance(n, bool) or n < 0:
        return "<not a size>"
    if n < 1024:
        return f"{n} B"
    v = float(n)
    for unit in ("KiB", "MiB", "GiB", "TiB"):
        v /= 1024
        if v < 1024 or unit == "TiB":
            return f"{v:.1f} {unit}"


def get(doc, path):
    cur = doc
    for part in path.split("."):
        if isinstance(cur, list) and "=" in part:
            key, want = part.split("=", 1)
            cur = next((x for x in cur if isinstance(x, dict) and str(x.get(key)) == want), ABSENT)
        elif isinstance(cur, list) and part.isdigit():
            cur = cur[int(part)] if int(part) < len(cur) else ABSENT
        elif isinstance(cur, dict):
            cur = cur.get(part, ABSENT)
        else:
            cur = ABSENT
        if cur is ABSENT:
            return ABSENT
    return cur


def show(fn, v):
    if v is ABSENT:
        return "<absent>"
    if fn == "size":
        return size(v)
    if fn == "len":
        return str(len(v))
    if fn == "sorted":
        return json.dumps(sorted(v))
    if isinstance(v, str):
        return v.replace("\n", "\\n")
    return json.dumps(v, sort_keys=True)


def main():
    try:
        with open(sys.argv[1], encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError) as exc:
        print("json=invalid")
        print(f"json_error={exc}")
        return 1
    print("json=ok")
    for spec in sys.argv[2:]:
        fn, _, path = spec.rpartition(":")
        print(f"{spec}={show(fn, get(doc, path))}")
    return 0


sys.exit(main())
PY
)"

# statvfs of a path, as an unprivileged writer sees it (R17: f_bavail * f_frsize).
STATVFS_PY='import os, sys
s = os.statvfs(sys.argv[1])
print(f"total={s.f_blocks * s.f_frsize}")
print(f"free={s.f_bavail * s.f_frsize}")'

setup_file() {
  stamp_check
  remove_stale_throwaways
  SC9_WS_BOX="timelike-run-sc9-work-${RANDOM}${RANDOM}"
  SC9_SC_BOX="timelike-run-sc9-scratch-${RANDOM}${RANDOM}"
  SC9_WS_ERROR=""
  SC9_SC_ERROR=""
  SC9_WS_WORK=""
  SC9_SC_WORK=""
  export SC9_WS_BOX SC9_SC_BOX SC9_WS_ERROR SC9_SC_ERROR SC9_WS_WORK SC9_SC_WORK
  sc9_prepare "$SC9_WS_BOX" /work 1m "$WORK_SIZE" SC9_WS_ERROR SC9_WS_WORK || true
  sc9_prepare "$SC9_SC_BOX" /scratch 256k "$SCRATCH_SIZE" SC9_SC_ERROR SC9_SC_WORK || true
  export SC9_WS_ERROR SC9_SC_ERROR SC9_WS_WORK SC9_SC_WORK
}

teardown_file() {
  remove_throwaway "${SC9_WS_BOX:-}" "${SC9_SC_BOX:-}"
}

# sc9_prepare BOX MOUNT SIZE BYTES ERROR_VAR WORK_VAR — start BOX with `--tmpfs MOUNT:size=SIZE,mode=1777`,
# read its size (BYTES), mode and writability back, and put the readers in a work directory under the
# box's /tmp. On any problem sets ERROR_VAR, so only that case's tests fail, with the reason.
sc9_prepare() {
  local box="$1" mount="$2" opt="$3" bytes="$4" error_var="$5" work_var="$6" err out total mode work
  printf -v "$error_var" '%s' ""
  err="$(start_throwaway "$box" --tmpfs "${mount}:size=${opt},mode=1777" 2>&1)" || {
    printf -v "$error_var" '%s' "cannot start ${box} with --tmpfs ${mount}:size=${opt},mode=1777: ${err}"
    return 1
  }
  out="$(AGENT_CONTAINER="$box" exec_plain "$AGENT_PY" -I -c "$STATVFS_PY" "$mount" 2>&1)" || {
    printf -v "$error_var" '%s' "cannot statvfs ${mount} in ${box}: ${out}"
    return 1
  }
  total="$(sed -n 's/^total=//p' <<<"$out")"
  if [[ "$total" != "$bytes" ]]; then
    printf -v "$error_var" '%s' "${mount} in ${box} is not a ${bytes}-byte filesystem (statvfs: ${out//$'\n'/; })"
    return 1
  fi
  mode="$(AGENT_CONTAINER="$box" exec_plain stat -c '%a' "$mount" 2>&1)"
  if [[ "$mode" != 1777 ]]; then
    printf -v "$error_var" '%s' "${mount} in ${box} has mode '${mode}', not 1777"
    return 1
  fi
  err="$(AGENT_CONTAINER="$box" exec_plain sh -c ': > "$1/.probe" && rm -f "$1/.probe"' probe "$mount" 2>&1)" || {
    printf -v "$error_var" '%s' "the agent user cannot write to ${mount} in ${box}: ${err}"
    return 1
  }
  work="$(AGENT_CONTAINER="$box" container_tmpdir sc9run 2>&1)" || {
    printf -v "$error_var" '%s' "cannot make a work directory in ${box}: ${work}"
    return 1
  }
  printf -v "$work_var" '%s' "$work"
  err="$(AGENT_CONTAINER="$box" exec_plain sh -c 'printf "%s\n" "$2" > "$1/json_paths.py" && printf "%s\n" "$3" > "$1/statvfs.py"' \
    put "$work" "$JSON_PATHS_PY" "$STATVFS_PY" 2>&1)" || {
    printf -v "$error_var" '%s' "cannot write the readers into ${box}: ${err}"
    return 1
  }
}

sc9_ready() { # sc9_ready ERROR
  if [[ -n "$1" ]]; then
    echo "SC-9 precondition: $1" >&2
    return 1
  fi
}

# free_in BOX WORK MOUNT — prints MOUNT's free bytes in BOX, read with statvfs.
free_in() {
  local out free
  out="$(AGENT_CONTAINER="$1" exec_plain "$AGENT_PY" -I "$2/statvfs.py" "$3" 2>&1)" || {
    echo "cannot statvfs $3 in $1: ${out}" >&2
    return 1
  }
  free="$(sed -n 's/^free=//p' <<<"$out")"
  [[ "$free" =~ ^[0-9]+$ ]] || { echo "no free space read for $3 in $1: ${out}" >&2; return 1; }
  printf '%s' "$free"
}

# read_disk BOX WORK FILE ROLE — the JSON result's fields for the disk entry with role ROLE.
read_disk() {
  local sel="disk.role=$4"
  AGENT_CONTAINER="$1" run exec_plain "$AGENT_PY" -I "$2/json_paths.py" "$3" \
    exit cause command_exit verdict log "${sel}.mount" "${sel}.full" "${sel}.free_bytes" "size:${sel}.free_bytes"
  [[ "$status" -eq 0 ]] || { printf 'cannot read the JSON result:\n%s\n' "$output" >&2; return 1; }
  assert_value json ok
}

# check_workspace STYLE — dd fills /work, the current directory.
check_workspace() {
  sc9_ready "${SC9_WS_ERROR:-}"
  local box="$SC9_WS_BOX" work="$SC9_WS_WORK" out="${SC9_WS_WORK}/r-$1.json" before after
  # Each cell starts from an empty /work (the other style's cell left its partial file).
  AGENT_CONTAINER="$box" exec_plain rm -f /work/fill || { echo "cannot empty /work in ${box}" >&2; return 1; }
  before="$(free_in "$box" "$work" /work)" || return 1
  [[ "$before" == "$WORK_SIZE" ]] || { echo "/work is not empty before the command: ${before} bytes free of ${WORK_SIZE}" >&2; return 1; }

  AGENT_CONTAINER="$box" run_in "$1" notty \
    "cd /work && run --json dd if=/dev/zero of=/work/fill bs=64k count=64 > '${out}'; rc=\$?; echo \"rc=\$rc\"; exit \$rc"
  assert_within 20
  assert_status 1
  assert_value rc 1
  after="$(free_in "$box" "$work" /work)" || return 1
  ((after < FULL_BYTES)) || { echo "/work still has ${after} bytes free after dd: the case did not fill it" >&2; return 1; }

  read_disk "$box" "$work" "$out" workspace
  assert_value exit 1
  assert_value cause disk
  assert_value command_exit 1
  assert_value disk.role=workspace.mount /work
  assert_value disk.role=workspace.full true
  # run read the free space after the command; nothing has written to /work since.
  assert_value disk.role=workspace.free_bytes "$after"

  local verdict size
  verdict="$(value_of verdict)"
  size="$(value_of size:disk.role=workspace.free_bytes)"
  [[ "$verdict" == "exit 1 (disk full: "* ]] || { echo "verdict does not start 'exit 1 (disk full: ': ${verdict}" >&2; return 1; }
  [[ "$verdict" == *"/work has ${size} free"* ]] ||
    { printf 'verdict does not name /work and its free space (%s):\n%s\n' "$size" "$verdict" >&2; return 1; }
  # The scratch filesystem (the image's /tmp) is not the full one here.
  [[ "$verdict" != *"log may be incomplete"* ]] ||
    { echo "verdict says the log may be incomplete, but the scratch filesystem is not the full one: ${verdict}" >&2; return 1; }
}

# check_scratch STYLE — the command's own output fills the scratch filesystem, which holds run's log.
check_scratch() {
  sc9_ready "${SC9_SC_ERROR:-}"
  local box="$SC9_SC_BOX" work="$SC9_SC_WORK" out="${SC9_SC_WORK}/r-$1.json" before after rc
  # Each cell starts from an empty /scratch (the other style's cell left its session directory).
  AGENT_CONTAINER="$box" exec_plain sh -c 'rm -rf /scratch/* /scratch/.[!.]*' ||
    { echo "cannot empty /scratch in ${box}" >&2; return 1; }
  before="$(free_in "$box" "$work" /scratch)" || return 1
  [[ "$before" == "$SCRATCH_SIZE" ]] || { echo "/scratch is not empty before the command: ${before} bytes free of ${SCRATCH_SIZE}" >&2; return 1; }

  AGENT_CONTAINER="$box" run_in -e TIMELIKE_SCRATCH_ROOT=/scratch "$1" notty \
    "run --json sh -c 'yes 0123456789abcdef | head -c 2000000' > '${out}'; rc=\$?; echo \"rc=\$rc\"; exit \$rc"
  assert_within 20
  rc="$status"
  if [[ "$rc" == 0 || "$rc" == 124 ]]; then
    printf 'expected the command to fail on its write (non-zero, not a timeout), got %s; output:\n%s\n' "$rc" "$output" >&2
    return 1
  fi
  assert_value rc "$rc"
  after="$(free_in "$box" "$work" /scratch)" || return 1
  ((after < FULL_BYTES)) || { echo "/scratch has ${after} bytes free after the command" >&2; return 1; }

  read_disk "$box" "$work" "$out" scratch
  assert_value exit "$rc"
  assert_value cause disk
  assert_value command_exit "$rc"
  assert_value disk.role=scratch.mount /scratch
  assert_value disk.role=scratch.full true
  local free log verdict size
  free="$(value_of disk.role=scratch.free_bytes)"
  at_most "$free" "$SCRATCH_SIZE" ||
    { echo "data.disk scratch free_bytes is not within the ${SCRATCH_SIZE}-byte filesystem: ${free}" >&2; return 1; }
  log="$(value_of log)"
  [[ "$log" == /scratch/?* ]] || { echo "the log is not on the scratch filesystem: ${log}" >&2; return 1; }

  verdict="$(value_of verdict)"
  size="$(value_of size:disk.role=scratch.free_bytes)"
  [[ "$verdict" == "exit ${rc} (disk full: "* ]] || { echo "verdict does not start 'exit ${rc} (disk full: ': ${verdict}" >&2; return 1; }
  [[ "$verdict" == *"/scratch has ${size} free"* ]] ||
    { printf 'verdict does not name /scratch and its free space (%s):\n%s\n' "$size" "$verdict" >&2; return 1; }
  [[ "$verdict" == *" · log may be incomplete"* ]] ||
    { echo "verdict does not say the log may be incomplete: ${verdict}" >&2; return 1; }
}

@test "SC-9 a command that fails because the scratch or workspace filesystem is full produces a verdict naming the full filesystem and its free space: workspace [bash -c, notty]" { check_workspace c; }
@test "SC-9 a command that fails because the scratch or workspace filesystem is full produces a verdict naming the full filesystem and its free space: workspace [bash -lc, notty]" { check_workspace lc; }
@test "SC-9 a command that fails because the scratch or workspace filesystem is full produces a verdict naming the full filesystem and its free space: scratch [bash -c, notty]" { check_scratch c; }
@test "SC-9 a command that fails because the scratch or workspace filesystem is full produces a verdict naming the full filesystem and its free space: scratch [bash -lc, notty]" { check_scratch lc; }
