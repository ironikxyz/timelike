#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# shellcheck disable=SC2030,SC2031 # setup_file exports; bats runs each @test in its own subshell by design
# SC-8 — "A command killed by the container's memory limit produces a verdict naming the memory limit
# and peak usage". (Feature 003, slice 1; spec FR-25 to FR-28, Scenario 5; contracts/run-cli.md
# § Slice 1; research R16.)
#
# The compose service sets no memory limit, so setup_file starts a throwaway container from the
# verified image (helpers.bash start_throwaway) with `--memory 96m --memory-swap 96m`: no swap, so the
# allocation cannot page out and the kernel's OOM killer stops it. Before any assertion relies on the
# limit it is read back from the throwaway's own cgroup, located the way the contract says `run` finds
# it (`/sys/fs/cgroup` joined with /proc/self/cgroup's `0::` path): memory.max must be 100663296, and
# memory.peak and memory.events' oom_kill must be readable (memory.peak needs kernel >= 5.19). A
# precondition that does not hold makes these tests FAIL with the reason, never skip: a skip leaves the
# lane green with the criterion unexecuted.
#
# The command is the image's own Python, allocating 8 MiB blocks (written, so the pages are resident)
# until it is killed. It is run's direct child, so `$?` is 137 (128 + SIGKILL), as it would have been
# without run. Artefacts decide:
#   - the exit status docker exec reports (run's own, passed through);
#   - the JSON result read as data in the throwaway (cause, command_exit, data.memory). Slice 0 puts
#     `data`'s fields at the top level of the JSON document, so `data.memory` is the key `memory`;
#   - the verdict's peak is checked against JSON `peak_bytes`, formatted by the contract's size rule
#     (below 1 KiB an integer `B`, otherwise one decimal in KiB/MiB/GiB/TiB).
# memory.peak is the container's peak since it started (R16), so it is asserted > 0 and consistent
# with the verdict, never against a figure guessed here.
# Cells: bash -c and bash -lc in `notty`, for --json and --text.

load helpers

# at_least VALUE MIN — VALUE is a non-negative integer and at least MIN.
at_least() { [[ "$1" =~ ^[0-9]+$ ]] && (($1 >= $2)); }

LIMIT_BYTES=100663296 # --memory 96m

# Allocates until the OOM killer stops it. b"x" * n writes every page (bytearray(n) would not).
ALLOC='import itertools; h = [b"x" * (8 << 20) for _ in itertools.count()]'

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

# Reads the cgroup files where the contract says run finds them, as the agent user.
READ_CGROUP='p="$(sed -n "s/^0:://p" /proc/self/cgroup)"; d="/sys/fs/cgroup${p%/}"
echo "dir=${d}"
echo "max=$(cat "${d}/memory.max" 2>&1)"
echo "peak=$(cat "${d}/memory.peak" 2>&1)"
echo "oom_kill=$(sed -n "s/^oom_kill //p" "${d}/memory.events" 2>&1)"'

setup_file() {
  stamp_check
  remove_stale_throwaways
  SC8_ERROR=""
  SC8_BOX="timelike-run-sc8-memory-${RANDOM}${RANDOM}"
  SC8_WORK=""
  export SC8_ERROR SC8_BOX SC8_WORK
  sc8_prepare || true
  export SC8_ERROR SC8_WORK
}

teardown_file() {
  remove_throwaway "${SC8_BOX:-}"
}

# sc8_prepare — start the limited throwaway, read its limit back, put the JSON reader in it. On any
# problem sets SC8_ERROR, so every test fails with the reason.
sc8_prepare() {
  local err out max peak oom
  err="$(start_throwaway "$SC8_BOX" --memory 96m --memory-swap 96m 2>&1)" || {
    SC8_ERROR="cannot start ${SC8_BOX} with --memory 96m --memory-swap 96m: ${err}"
    return 1
  }
  out="$(AGENT_CONTAINER="$SC8_BOX" exec_plain sh -c "$READ_CGROUP" 2>&1)" || {
    SC8_ERROR="cannot read the cgroup files in ${SC8_BOX}: ${out}"
    return 1
  }
  max="$(sed -n 's/^max=//p' <<<"$out")"
  peak="$(sed -n 's/^peak=//p' <<<"$out")"
  oom="$(sed -n 's/^oom_kill=//p' <<<"$out")"
  if [[ "$max" != "$LIMIT_BYTES" ]]; then
    SC8_ERROR="--memory 96m is not visible as cgroup v2 memory.max ${LIMIT_BYTES} in ${SC8_BOX} (read: ${out//$'\n'/; }). A cgroup v1 host breaks spec FR-25's reading"
    return 1
  fi
  if ! [[ "$peak" =~ ^[0-9]+$ && "$oom" =~ ^[0-9]+$ ]]; then
    SC8_ERROR="memory.peak or memory.events' oom_kill is not readable in ${SC8_BOX} (read: ${out//$'\n'/; }); memory.peak needs kernel >= 5.19 (research R16)"
    return 1
  fi
  SC8_WORK="$(AGENT_CONTAINER="$SC8_BOX" container_tmpdir sc8run 2>&1)" || {
    SC8_ERROR="cannot make a work directory in ${SC8_BOX}: ${SC8_WORK}"
    return 1
  }
  err="$(AGENT_CONTAINER="$SC8_BOX" exec_plain sh -c 'printf "%s\n" "$2" > "$1"' put \
    "${SC8_WORK}/json_paths.py" "$JSON_PATHS_PY" 2>&1)" || {
    SC8_ERROR="cannot write the JSON reader into ${SC8_BOX}: ${err}"
    return 1
  }
}

sc8_ready() {
  if [[ -n "${SC8_ERROR:-}" ]]; then
    echo "SC-8 precondition: ${SC8_ERROR}" >&2
    return 1
  fi
}

# check_memory_json STYLE — `run --json` over the allocation in the 96 MiB throwaway.
check_memory_json() {
  sc8_ready
  local out="${SC8_WORK}/r-$1.json"
  AGENT_CONTAINER="$SC8_BOX" run_in "$1" notty \
    "run --json ${AGENT_PY} -I -c '${ALLOC}' > '${out}'; rc=\$?; echo \"rc=\$rc\"; exit \$rc"
  assert_within 20
  assert_status 137
  assert_value rc 137

  AGENT_CONTAINER="$SC8_BOX" run exec_plain "$AGENT_PY" -I "${SC8_WORK}/json_paths.py" "$out" \
    exit cause command_exit verdict memory.state memory.limit_bytes memory.peak_bytes memory.oom_kills \
    size:memory.limit_bytes size:memory.peak_bytes
  [[ "$status" -eq 0 ]] || { printf 'cannot read the JSON result:\n%s\n' "$output" >&2; return 1; }
  assert_value json ok
  assert_value exit 137
  assert_value cause memory
  assert_value command_exit 137
  assert_value memory.state read
  assert_value memory.limit_bytes "$LIMIT_BYTES"
  assert_value size:memory.limit_bytes "96.0 MiB"

  local peak oom verdict want
  peak="$(value_of memory.peak_bytes)"
  oom="$(value_of memory.oom_kills)"
  at_least "$peak" 1 ||
    { printf 'data.memory.peak_bytes is not a positive integer: %s\n%s\n' "$peak" "$output" >&2; return 1; }
  at_least "$oom" 1 ||
    { printf 'data.memory.oom_kills is not >= 1: %s\n%s\n' "$oom" "$output" >&2; return 1; }

  verdict="$(value_of verdict)"
  want="exit 137 (out of memory: limit 96.0 MiB, peak $(value_of size:memory.peak_bytes)) · "
  [[ "$verdict" == "$want"* ]] ||
    { printf 'verdict does not start %q:\n%s\n' "$want" "$verdict" >&2; return 1; }
}

# check_memory_text STYLE — the same in --text: line 2 is the verdict naming the limit and the peak.
check_memory_text() {
  sc8_ready
  local out="${SC8_WORK}/t-$1.txt"
  AGENT_CONTAINER="$SC8_BOX" run_in "$1" notty \
    "run --text ${AGENT_PY} -I -c '${ALLOC}' > '${out}' 2> '${out}.err'; rc=\$?; echo \"rc=\$rc\"; exit \$rc"
  assert_within 20
  assert_status 137
  assert_value rc 137

  local text
  text="$(AGENT_CONTAINER="$SC8_BOX" exec_plain cat "$out")" || { echo "cannot read run's output" >&2; return 1; }
  local -a rl
  mapfile -t rl <<<"${text//$'\r'/}"
  ((${#rl[@]} >= 2)) || { printf 'fewer than 2 lines of output:\n%s\n' "$text" >&2; return 1; }
  [[ "${rl[0]}" == "run: ${AGENT_PY} -I -c "*" [run]" ]] || { echo "line 1 is not the header: ${rl[0]}" >&2; return 1; }
  [[ "${rl[1]}" == "verdict: exit 137 (out of memory: limit 96.0 MiB, peak "* ]] ||
    { echo "line 2 does not name the memory limit: ${rl[1]}" >&2; return 1; }
  [[ "${rl[1]}" =~ ^verdict:\ exit\ 137\ \(out\ of\ memory:\ limit\ 96\.0\ MiB,\ peak\ ([0-9]+\ B|[0-9]+\.[0-9]\ (KiB|MiB|GiB|TiB))\)\ ·\  ]] ||
    { echo "line 2 does not name the peak as a size: ${rl[1]}" >&2; return 1; }
}

@test "SC-8 a command killed by the container's memory limit produces a verdict naming the memory limit and peak usage: JSON [bash -c, notty]" { check_memory_json c; }
@test "SC-8 a command killed by the container's memory limit produces a verdict naming the memory limit and peak usage: JSON [bash -lc, notty]" { check_memory_json lc; }
@test "SC-8 a command killed by the container's memory limit produces a verdict naming the memory limit and peak usage: text [bash -c, notty]" { check_memory_text c; }
@test "SC-8 a command killed by the container's memory limit produces a verdict naming the memory limit and peak usage: text [bash -lc, notty]" { check_memory_text lc; }
