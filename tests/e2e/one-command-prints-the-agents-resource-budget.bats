#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# shellcheck disable=SC2030,SC2031 # setup_file exports what the @tests read; bats runs each @test in its own subshell by design
# Feature 007 (prompt 04, slice 1), SC-7 (tasks.md T014; spec FR-20 to FR-23; contract § Slice 1,
# `timelike budget`):
#   SC-7 "One command prints the agent's resource budget: memory limit and use, CPU limit, process limit,
#        and free space on the workspace and scratch filesystems"
#
# Two containers, from outside (lore cross-stack P005):
#   limited  a throwaway from the verified image (helpers.bash start_throwaway) with limits THIS TEST
#            chose: --memory 300m (314572800 bytes), --cpus 1.5 (cpu.max "150000 100000"),
#            --pids-limit 123. They are read back from the throwaway's own cgroup before any assertion
#            relies on them (cross-stack P001), and the CPU affinity it actually has is read from its
#            /proc/self/status, so the expected job count is min(2, affinity) — ceil(1.5) capped by
#            affinity, the hook's rule — never a guess about the host. A precondition that does not hold
#            FAILS the cells with the reason, never skips (a skip leaves the criterion unexecuted).
#   agent    the running agent container (compose sets limits of its own, or none). Every figure is
#            compared with the cgroup file read directly in the same shell: `max` must come out as
#            state none, value null and "no limit" in the text, a number as that number. Which of
#            memory.max, pids.max and cpu.max say `max` is the compose file's business, so each check is
#            conditional on the raw file and says which branch it took when it fails. The CPU job count
#            must equal that shell's $TIMELIKE_CPUS, and `agrees` must be true.
# Workspace and scratch (agent container): a fresh git repository in /tmp, budget run from a
# subdirectory names the repository root; outside any repository it names the current directory. A
# TIMELIKE_SCRATCH_ROOT that does not exist yet is reported exists:false, measured at its nearest
# existing ancestor, and the text line says "does not exist yet". The JSON and text runs use DIFFERENT
# not-yet-existing roots: agentio writes its session event under the scratch root after printing, so a
# second run against the same root would find it created by the first.
#
# The JSON is agentio's envelope with `data` merged at the TOP LEVEL (memory, cpu, pids, disks, cgroup
# are keys of the document; there is no "data" key). Not a terminal, so JSON is the default and the text
# form is asked for with --text. The JSON is read in the container by the image's interpreter (-I).
# Cells: bash -c and bash -lc in `notty`.

load helpers

SC7_LIMIT_BYTES=314572800 # --memory 300m
SC7_PIDS=123
# A size by the contract's rule (run's size()): below 1 KiB "N B", else one decimal and a binary unit.
SC7_SIZE='([0-9]+ B|[0-9]+\.[0-9] (KiB|MiB|GiB|TiB))'

setup_file() {
  stamp_check
  remove_stale_throwaways
  SC7_ERROR=""
  SC7_BOX="timelike-sc7-budget-${RANDOM}${RANDOM}"
  SC7_AFFINITY=""
  SC7_JOBS=""
  export SC7_BOX
  sc7_prepare || true
  export SC7_ERROR SC7_AFFINITY SC7_JOBS
}

teardown_file() {
  remove_throwaway "${SC7_BOX:-}"
}

teardown() {
  container_rm "${SC7_RM:-}"
}

# sc7_prepare — start the limited throwaway and read its limits back. Sets SC7_AFFINITY and SC7_JOBS;
# on any problem sets SC7_ERROR, so only the limited cells fail, with the reason.
sc7_prepare() {
  local err out line mem="" cpu="" pids="" list=""
  err="$(start_throwaway "$SC7_BOX" --memory 300m --cpus 1.5 --pids-limit "$SC7_PIDS" 2>&1)" || {
    SC7_ERROR="cannot start ${SC7_BOX} with --memory 300m --cpus 1.5 --pids-limit ${SC7_PIDS}: ${err} (--cpus 1.5 needs a host with at least 2 CPUs)"
    return 1
  }
  out="$(timeout "$RUN_TIMEOUT" docker exec "$SC7_BOX" sh -c '
p="$(sed -n "s/^0:://p" /proc/self/cgroup)"; d="/sys/fs/cgroup${p%/}"
echo "mem=$(cat "$d/memory.max" 2>&1)"
echo "cpu=$(cat "$d/cpu.max" 2>&1)"
echo "pids=$(cat "$d/pids.max" 2>&1)"
echo "list=$(sed -n "s/^Cpus_allowed_list:[[:space:]]*//p" /proc/self/status)"' </dev/null 2>&1)"
  while IFS= read -r line; do
    case "$line" in
      mem=*) mem="${line#mem=}" ;;
      cpu=*) cpu="${line#cpu=}" ;;
      pids=*) pids="${line#pids=}" ;;
      list=*) list="${line#list=}" ;;
    esac
  done <<<"$out"
  if [[ "$mem" != "$SC7_LIMIT_BYTES" || "$cpu" != "150000 100000" || "$pids" != "$SC7_PIDS" ]]; then
    SC7_ERROR="the limits are not visible as cgroup v2 files in ${SC7_BOX} (memory.max '${mem}', want ${SC7_LIMIT_BYTES}; cpu.max '${cpu}', want '150000 100000'; pids.max '${pids}', want ${SC7_PIDS}); output: ${out}"
    return 1
  fi
  SC7_AFFINITY="$(cpu_list_count "$list")" || {
    SC7_ERROR="unparseable Cpus_allowed_list '${list}' in ${SC7_BOX}"
    return 1
  }
  if ((SC7_AFFINITY >= 2)); then SC7_JOBS=2; else SC7_JOBS="$SC7_AFFINITY"; fi
}

sc7_ready() {
  if [[ -n "${SC7_ERROR:-}" ]]; then
    echo "SC-7 precondition: ${SC7_ERROR}" >&2
    return 1
  fi
}

# READ_BUDGET — under the style under test. Optional inputs, passed with -e:
#   SC7_CWD           cd here first
#   SC7_SCRATCH_JSON  TIMELIKE_SCRATCH_ROOT for the --json run only
#   SC7_SCRATCH_TEXT  TIMELIKE_SCRATCH_ROOT for the --text run only
# Prints the raw cgroup files (the contract's cgroup directory), the shell's own figures, the JSON's
# fields as PATH=VALUE (strings raw, everything else as JSON: null, true, 1.5), and the text body (the
# lines after `verdict:`) as body.N.
read -r -d '' READ_BUDGET <<'EOF' || true
if [ -n "${SC7_CWD:-}" ]; then cd "$SC7_CWD" || { printf "cd=failed\n"; exit 3; }; fi
cg_p="$(sed -n "s/^0:://p" /proc/self/cgroup)"
cg="/sys/fs/cgroup${cg_p%/}"
printf "cg=%s\n" "$cg"
for f in memory.max pids.max cpu.max; do
  printf "raw.%s=%s\n" "$f" "$(head -n 1 "$cg/$f" 2>&1)"
done
printf "shell.TIMELIKE_CPUS=%s\n" "${TIMELIKE_CPUS-<unset>}"
printf "shell.scratch=%s\n" "${TIMELIKE_SCRATCH_ROOT:-/tmp/timelike}"
printf "shell.pwd=%s\n" "$(pwd -P)"
t="$(mktemp -d)"
if [ -n "${SC7_SCRATCH_JSON:-}" ]; then
  TIMELIKE_SCRATCH_ROOT="$SC7_SCRATCH_JSON" timelike budget --json >"$t/json" 2>"$t/err"
else
  timelike budget --json >"$t/json" 2>"$t/err"
fi
printf "json_rc=%s\n" "$?"
if [ -n "${SC7_SCRATCH_TEXT:-}" ]; then
  TIMELIKE_SCRATCH_ROOT="$SC7_SCRATCH_TEXT" timelike budget --text >"$t/text" 2>>"$t/err"
else
  timelike budget --text >"$t/text" 2>>"$t/err"
fi
printf "text_rc=%s\n" "$?"
printf "stderr=%s\n" "$(head -c 300 "$t/err" | tr "\n" " ")"
/opt/timelike/python/bin/python3 -I -c '
import json, sys
sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
MISSING = object()
def get(doc, path):
    cur = doc
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        elif isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
            cur = cur[int(part)]
        else:
            return MISSING
    return cur
def show(v):
    if v is MISSING:
        return "<absent>"
    if isinstance(v, str):
        return v.replace("\n", "\\n")
    return json.dumps(v)
try:
    with open(sys.argv[1], encoding="utf-8") as fh:
        doc = json.load(fh)
except (OSError, ValueError) as exc:
    print("json=invalid: %s" % exc)
    doc = None
if isinstance(doc, dict):
    print("json=ok")
    paths = ["cgroup"]
    for fig in ("memory.limit", "memory.current", "memory.peak", "cpu.limit", "pids.limit", "pids.current"):
        paths += [fig + ".state", fig + ".value", fig + ".source", fig + ".reason"]
    paths += ["cpu.limit.quota", "cpu.limit.period", "cpu.affinity", "cpu.jobs", "cpu.shell_value", "cpu.agrees"]
    for i in (0, 1):
        for k in ("role", "path", "measured", "exists", "free_bytes", "total_bytes", "reason"):
            paths.append("disks.%d.%s" % (i, k))
    for p in paths:
        print("%s=%s" % (p, show(get(doc, p))))
    disks = doc.get("disks")
    print("disks=%s" % (len(disks) if isinstance(disks, list) else "<absent>"))
    jl = doc.get("lines")
    print("json.lines=%s" % (len(jl) if isinstance(jl, list) else "<absent>"))
try:
    with open(sys.argv[2], encoding="utf-8") as fh:
        text = fh.read().splitlines()
except OSError as exc:
    print("text=unreadable: %s" % exc)
    text = None
if text is not None:
    at = next((i for i, x in enumerate(text) if x.startswith("verdict: ")), None)
    if at is None:
        print("body=<no verdict line>")
    else:
        body = text[at + 1:]
        print("body=%d" % len(body))
        for i, x in enumerate(body):
            print("body.%d=%s" % (i, x))
' "$t/json" "$t/text"
rm -rf "$t"
printf "read=done\n"
EOF

run_budget() { # run_budget [-e K=V]... STYLE
  local -a envs=()
  while [[ "${1:-}" == -e ]]; do
    envs+=(-e "$2")
    shift 2
  done
  run_in "${envs[@]}" "$1" notty "$READ_BUDGET"
  assert_within 20
  assert_status 0
  assert_value read "done"
  assert_value json_rc 0
  assert_value text_rc 0
  assert_value json ok
  assert_value disks 2
  assert_value json.lines 5
  assert_value body 5
}

# assert_int KEY OP N — KEY's value is a non-negative integer and (VALUE OP N) holds (gt, ge).
assert_int() {
  local v
  v="$(value_of "$1")"
  local ok=0
  if [[ "$v" =~ ^[0-9]+$ ]]; then
    case "$2" in
      gt) ((v > $3)) && ok=1 ;;
      ge) ((v >= $3)) && ok=1 ;;
    esac
  fi
  if ((ok == 0)); then
    printf '%s: expected an integer %s %s, got %q; output:\n%s\n' "$1" "$2" "$3" "$v" "$output" >&2
    return 1
  fi
}

# assert_body_matches N ERE — text body line N matches ERE.
assert_body_matches() {
  local got
  got="$(value_of "body.$1")"
  if ! [[ "$got" =~ $2 ]]; then
    printf 'text line %d: %q does not match /%s/; output:\n%s\n' "$(($1 + 1))" "$got" "$2" "$output" >&2
    return 1
  fi
}

# assert_body_prefix N PREFIX — text body line N starts with PREFIX (fixed string).
assert_body_prefix() {
  local got
  got="$(value_of "body.$1")"
  if [[ "$got" != "$2"* ]]; then
    printf 'text line %d: %q does not start with %q; output:\n%s\n' "$(($1 + 1))" "$got" "$2" "$output" >&2
    return 1
  fi
}

# assert_disk N ROLE — the disk entry has the role, free > 0 and total >= free, and its text line
# (body 3 + N) names the path, then "<free> free of <total>", then the not-yet note when exists is false.
assert_disk() {
  local n="$1" role="$2" path measured exists rest got
  assert_value "disks.${n}.role" "$role"
  assert_int "disks.${n}.free_bytes" gt 0
  assert_int "disks.${n}.total_bytes" ge "$(value_of "disks.${n}.free_bytes")"
  path="$(value_of "disks.${n}.path")"
  measured="$(value_of "disks.${n}.measured")"
  exists="$(value_of "disks.${n}.exists")"
  got="$(value_of "body.$((3 + n))")"
  if [[ "$got" != "disk, ${role} "* ]]; then
    printf 'text line %d: %q does not start with %q\n' "$((4 + n))" "$got" "disk, ${role} " >&2
    return 1
  fi
  rest="${got#"disk, ${role} "}"
  rest="${rest#*: }"
  if ! [[ "$rest" =~ ^${SC7_SIZE}\ free\ of\ ${SC7_SIZE}(\ \(measured\ at\ .+;\ .+\ does\ not\ exist\ yet\))?$ ]]; then
    printf 'text line %d: %q is not "<path>: <free> free of <total>[ (measured at …; … does not exist yet)]"\n' \
      "$((4 + n))" "$got" >&2
    return 1
  fi
  if [[ "$exists" == true && "$measured" != "$path" ]]; then
    printf 'disks.%d: exists but measured %q differs from path %q\n' "$n" "$measured" "$path" >&2
    return 1
  fi
}

# --- the limited throwaway: figures equal the limits this test chose ---------------------------------
check_limited_json() {
  sc7_ready
  AGENT_CONTAINER="$SC7_BOX" run_budget "$1"
  assert_value cgroup "$(value_of cg)"
  assert_value memory.limit.state value
  assert_value memory.limit.value "$SC7_LIMIT_BYTES"
  assert_value memory.current.state value
  assert_int memory.current.value gt 0
  assert_value cpu.limit.state value
  assert_value cpu.limit.value 1.5
  assert_value cpu.limit.quota 150000
  assert_value cpu.limit.period 100000
  assert_value cpu.affinity "$SC7_AFFINITY"
  assert_value cpu.jobs "$SC7_JOBS"
  assert_value shell.TIMELIKE_CPUS "$SC7_JOBS"
  assert_value cpu.shell_value "$SC7_JOBS"
  assert_value cpu.agrees true
  assert_value pids.limit.state value
  assert_value pids.limit.value "$SC7_PIDS"
  assert_value pids.current.state value
  assert_int pids.current.value gt 0
  assert_value disks.0.path "$(value_of shell.pwd)" # the throwaway's WORKDIR holds no repository
  assert_value disks.1.path "$(value_of shell.scratch)"
  assert_disk 0 workspace
  assert_disk 1 scratch
}

check_limited_text() {
  sc7_ready
  AGENT_CONTAINER="$SC7_BOX" run_budget "$1"
  assert_body_matches 0 "^memory: limit 300\.0 MiB · in use ${SC7_SIZE} · peak (${SC7_SIZE}|unknown \(.+\))$"
  local j="$SC7_JOBS"
  assert_value body.1 "cpu: limit 1.50 CPUs · job count ${j} (TIMELIKE_CPUS) · this shell has TIMELIKE_CPUS=${j}, agrees"
  assert_body_matches 2 "^processes: limit ${SC7_PIDS} · running [0-9]+$"
  assert_body_prefix 3 "disk, workspace $(value_of disks.0.path): "
  assert_body_prefix 4 "disk, scratch $(value_of disks.1.path): "
  assert_disk 0 workspace
  assert_disk 1 scratch
}

@test "SC-7 [bash -c, notty] One command prints the agent's resource budget: memory limit and use, CPU limit, process limit, and free space on the workspace and scratch filesystems — limited container: JSON memory 314572800, CPU 1.5 (150000/100000), jobs min(2, affinity), processes 123, both disks" { check_limited_json c; }
@test "SC-7 [bash -lc, notty] One command prints the agent's resource budget: memory limit and use, CPU limit, process limit, and free space on the workspace and scratch filesystems — limited container: JSON memory 314572800, CPU 1.5 (150000/100000), jobs min(2, affinity), processes 123, both disks" { check_limited_json lc; }
@test "SC-7 [bash -c, notty] One command prints the agent's resource budget: memory limit and use, CPU limit, process limit, and free space on the workspace and scratch filesystems — limited container: the five text lines in order, 300.0 MiB, 1.50 CPUs, 123" { check_limited_text c; }
@test "SC-7 [bash -lc, notty] One command prints the agent's resource budget: memory limit and use, CPU limit, process limit, and free space on the workspace and scratch filesystems — limited container: the five text lines in order, 300.0 MiB, 1.50 CPUs, 123" { check_limited_text lc; }

# --- the running agent container: every figure is the file it came from -----------------------------
# assert_figure_from_raw FIG RAW BODY_N PREFIX — RAW is the cgroup file's first line as read in the
# same shell. `max` → none, null, and "<PREFIX> limit no limit · " in the text; an integer → that value;
# anything else (unreadable) → unknown, null, never 0.
assert_figure_from_raw() {
  local fig="$1" raw="$2" n="$3" prefix="$4"
  case "$raw" in
    max)
      assert_value "${fig}.state" none
      assert_value "${fig}.value" null
      assert_body_prefix "$n" "${prefix} limit no limit · "
      ;;
    *[!0-9]* | "")
      assert_value "${fig}.state" unknown
      assert_value "${fig}.value" null
      assert_body_prefix "$n" "${prefix} limit unknown ("
      ;;
    *)
      assert_value "${fig}.state" value
      assert_value "${fig}.value" "$raw"
      ;;
  esac
}

check_agent() {
  run_budget "$1"
  assert_value cgroup "$(value_of cg)"
  local cpus
  cpus="$(value_of shell.TIMELIKE_CPUS)"
  if ! [[ "$cpus" =~ ^[0-9]+$ ]]; then
    printf 'this shell has no TIMELIKE_CPUS (%q): the hook did not run in %s\n' "$cpus" "$(style_label "$1")" >&2
    return 1
  fi
  assert_value cpu.jobs "$cpus"
  assert_value cpu.shell_value "$cpus"
  assert_value cpu.agrees true
  assert_body_matches 1 "^cpu: limit .+ · job count ${cpus} \(TIMELIKE_CPUS\) · this shell has TIMELIKE_CPUS=${cpus}, agrees$"

  assert_figure_from_raw memory.limit "$(value_of raw.memory.max)" 0 "memory:"
  assert_figure_from_raw pids.limit "$(value_of raw.pids.max)" 2 "processes:"
  local cpu_raw
  cpu_raw="$(value_of raw.cpu.max)"
  case "$cpu_raw" in
    "max "*)
      assert_value cpu.limit.state none
      assert_value cpu.limit.value null
      assert_body_prefix 1 "cpu: limit no limit · "
      ;;
    [0-9]*" "[0-9]*)
      assert_value cpu.limit.state value
      assert_value cpu.limit.quota "${cpu_raw% *}"
      assert_value cpu.limit.period "${cpu_raw#* }"
      ;;
    *)
      assert_value cpu.limit.state unknown
      assert_body_prefix 1 "cpu: limit unknown ("
      ;;
  esac
  assert_value memory.current.state value
  assert_int memory.current.value gt 0
  assert_value pids.current.state value
  assert_int pids.current.value gt 0
  assert_disk 0 workspace
  assert_disk 1 scratch
}

@test "SC-7 [bash -c, notty] One command prints the agent's resource budget: memory limit and use, CPU limit, process limit, and free space on the workspace and scratch filesystems — agent container: the job count is this shell's TIMELIKE_CPUS and agrees; each limit is its cgroup file, max printed as no limit" { check_agent c; }
@test "SC-7 [bash -lc, notty] One command prints the agent's resource budget: memory limit and use, CPU limit, process limit, and free space on the workspace and scratch filesystems — agent container: the job count is this shell's TIMELIKE_CPUS and agrees; each limit is its cgroup file, max printed as no limit" { check_agent lc; }

# --- the workspace: the repository root from a subdirectory, else the current directory -------------
check_workspace() {
  local d real_repo real_plain
  d="$(container_tmpdir sc7ws)"
  SC7_RM="$d" # removed by teardown
  exec_plain sh -c 'git init -q "$1/repo" && mkdir -p "$1/repo/a/b" "$1/plain"' sc7 "$d"
  real_repo="$(exec_plain sh -c 'cd "$1" && pwd -P' sc7 "$d/repo")"
  real_plain="$(exec_plain sh -c 'cd "$1" && pwd -P' sc7 "$d/plain")"

  run_budget -e "SC7_CWD=${d}/repo/a/b" "$1"
  assert_value shell.pwd "${real_repo}/a/b"
  assert_value disks.0.path "$real_repo"
  assert_value disks.0.measured "$real_repo"
  assert_value disks.0.exists true
  assert_body_prefix 3 "disk, workspace ${real_repo}: "
  assert_disk 0 workspace

  run_budget -e "SC7_CWD=${d}/plain" "$1"
  assert_value disks.0.path "$real_plain"
  assert_value disks.0.exists true
  assert_body_prefix 3 "disk, workspace ${real_plain}: "
  assert_disk 0 workspace
}

@test "SC-7 [bash -c, notty] One command prints the agent's resource budget: memory limit and use, CPU limit, process limit, and free space on the workspace and scratch filesystems — workspace: a repository's root from its subdirectory; outside any repository, the current directory" { check_workspace c; }
@test "SC-7 [bash -lc, notty] One command prints the agent's resource budget: memory limit and use, CPU limit, process limit, and free space on the workspace and scratch filesystems — workspace: a repository's root from its subdirectory; outside any repository, the current directory" { check_workspace lc; }

# --- the scratch root before it exists ---------------------------------------------------------------
check_scratch_not_yet() {
  local d
  d="$(container_tmpdir sc7scr)"
  SC7_RM="$d" # removed by teardown
  exec_plain mkdir "$d/j" "$d/t"

  run_budget -e "SC7_SCRATCH_JSON=${d}/j/not-yet" -e "SC7_SCRATCH_TEXT=${d}/t/not-yet" "$1"
  assert_value disks.1.role scratch
  assert_value disks.1.path "${d}/j/not-yet"
  assert_value disks.1.exists false
  assert_value disks.1.measured "${d}/j"
  assert_disk 1 scratch
  assert_body_matches 4 "^disk, scratch ${d}/t/not-yet: ${SC7_SIZE} free of ${SC7_SIZE} \(measured at ${d}/t; ${d}/t/not-yet does not exist yet\)$"
}

@test "SC-7 [bash -c, notty] One command prints the agent's resource budget: memory limit and use, CPU limit, process limit, and free space on the workspace and scratch filesystems — scratch root not created yet: exists false, measured at its nearest existing ancestor, the text says it does not exist yet" { check_scratch_not_yet c; }
@test "SC-7 [bash -lc, notty] One command prints the agent's resource budget: memory limit and use, CPU limit, process limit, and free space on the workspace and scratch filesystems — scratch root not created yet: exists false, measured at its nearest existing ancestor, the text says it does not exist yet" { check_scratch_not_yet lc; }
