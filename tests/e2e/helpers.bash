# shellcheck shell=bash
# Shared helpers for the Docker-lane bats suite (tasks.md T013; research R8; lore cross-stack P005).
#
# Every test drives the agent container from OUTSIDE, through `docker exec`, the way a harness does.
# Nothing here configures the shell under test: the command string reaches the container's shell
# verbatim, and no -e flag sets a default the environment is supposed to provide.
#
# ── Invocation styles (STYLE) ────────────────────────────────────────────────────────────────────
#   c   bash -c CMD        non-interactive, reads no startup file
#   lc  bash -lc CMD       login: /etc/profile (which resets PATH on Debian, R1), profile.d
#   ic  bash -ic CMD       interactive: /etc/bash.bashrc, ~/.bashrc
#   sh  sh -c CMD          POSIX sh (dash): reads nothing, ignores BASH_ENV
#
# ── Terminal modes (TTY) ─────────────────────────────────────────────────────────────────────────
#   notty  `docker exec` with neither -t nor -i: pipes, no controlling terminal (/dev/tty is ENXIO),
#          runner-side stdin from /dev/null. This is the harness's own invocation (spec Assumption 1).
#   tty    `docker exec -t` (without -i): Docker allocates a pty in the container; the command's
#          stdin/stdout/stderr are that pty and it is the controlling terminal. Nothing ever writes
#          to its input side, so anything that reads the terminal blocks forever — the timeout turns
#          that into rc 124. This is R8's decision and the most faithful exposure of the pager,
#          editor and prompt traps.
#   pty    `docker exec` (no -t) running `script -qec '<shell> "$TL_CMD"' /dev/null` inside the
#          container: util-linux script gives the command a fresh pty and controlling terminal.
#          Independent of how the runner was started, and of Docker's tty handling.
#
# Why both tty and pty (FLAGGED in decisions.md): docker exec -t WITHOUT -i does not need a TTY on the
# runner side — the CLI refuses "the input device is not a TTY" only when -i and -t are combined
# (docker/cli In.CheckTty(attachStdin, ttyMode); read from source, NOT verified here — no daemon, R10).
# So `tty` should work under a non-interactive
# `docker run` of the runner. `pty` is kept as a second, independent route because util-linux script
# writes an EOF to the pty when its own stdin (here /dev/null) ends while the child reads in
# canonical mode; a canonical-mode read (a credential prompt) then fails fast instead of hanging.
# That is why a test must never rely on `pty` alone to catch a prompt: tests assert the absence of
# the prompt TEXT as well, and `tty` catches the hang.
#
# In tty/pty modes the output comes through a pty: line endings are CRLF and stderr is merged into
# stdout. run_in strips every CR, so `$output` and `${lines[@]}` compare equal across modes.
#
# ── Iterating styles × terminal modes ────────────────────────────────────────────────────────────
# bats has no parametrised tests we can rely on across versions, so each .bats file writes one
# explicit @test per combination, each a one-line call to a check function taking (STYLE TTY):
#
#     @test "SC-1 git log exits within 20 seconds [bash -lc, tty]" { check_git_log lc tty; }
#
# style_label STYLE prints the human form ("bash -lc") for test names and messages. This keeps each
# combination a separate TAP line, so a failure names its exact style and mode (constitution H7).

bats_require_minimum_version 1.5.0

# The parallel lane's file lock (maint-lane-speed): a no-op unless tests/run.sh runs files side by side.
# shellcheck source=tests/e2e/lane.bash
source "${BATS_TEST_DIRNAME}/lane.bash"

AGENT_CONTAINER="${AGENT_CONTAINER:-timelike-agent}"
# shellcheck disable=SC2034 # used by the .bats files that load this
AGENT_PY=/opt/timelike/python/bin/python3
REVISION_LABEL=org.opencontainers.image.revision
# Runner-side limit per docker exec. Criteria assert far tighter bounds (20 s, 10 s); this exists so
# a hang becomes a failure (rc 124), never a wait (P2).
RUN_TIMEOUT="${RUN_TIMEOUT:-30}"
# The parser's own bound (pyq): test plumbing, so it belongs to no criterion, and it is kept apart from
# RUN_TIMEOUT so a throwaway container's start-up under load cannot fail a cell whose tool answered.
# The runner's timeout is BusyBox's (bats/bats is Alpine), which exits with the killed command's status
# (143 for SIGTERM), never GNU's 124: decide "timed out" by elapsed time, not by the exit code.
# (Lane batch-c, not ok 448; bridge/feedback/batch-20261006-234535-lane-b-three-failures.md § Failure 4.)
PYQ_TIMEOUT="${PYQ_TIMEOUT:-120}"
# Process names (comm, exact match) of pagers and editors that must never be left running.
PAGER_EDITOR_NAMES='less|more|most|pager|pg|vi|vim|vim\.basic|vim\.tiny|nvi|view|ex|nano|rnano|pico|editor|sensible-editor|emacs|jed|joe|mcedit|ne'

# style_label STYLE → "bash -c" | "bash -lc" | "bash -ic" | "sh -c"
style_label() {
  case "$1" in
    c) echo "bash -c" ;;
    lc) echo "bash -lc" ;;
    ic) echo "bash -ic" ;;
    sh) echo "sh -c" ;;
    *) echo "unknown style '$1'" >&2; return 2 ;;
  esac
}

# _shell_argv STYLE → the shell and its flag, one per line, for use with mapfile.
_shell_argv() {
  case "$1" in
    c) printf '%s\n' bash -c ;;
    lc) printf '%s\n' bash -lc ;;
    ic) printf '%s\n' bash -ic ;;
    sh) printf '%s\n' sh -c ;;
    *) echo "unknown style '$1' (want c|lc|ic|sh)" >&2; return 2 ;;
  esac
}

# now_ms: wall clock in milliseconds (bash 5 EPOCHREALTIME; no external date).
now_ms() {
  local t="${EPOCHREALTIME/[.,]/}"
  echo $((10#${t} / 1000))
}

# ms_to_s MS → "12.345"
ms_to_s() {
  printf '%d.%03d' $(($1 / 1000)) $(($1 % 1000))
}

# exec_in [-e K=V]... [-w DIR] STYLE TTY CMD
# Runs CMD in the agent container, bounded by RUN_TIMEOUT on the runner side. No `run` wrapper: the
# exit status is the command's (or 124 on timeout). Prints the container output unmodified.
# -w starts the shell in DIR (docker exec -w), as a harness starts the agent's shell in its workspace;
# without it the shell starts in the image's WORKDIR, /home/agent.
# Sets EXEC_ELAPSED_MS.
exec_in() {
  local -a envs=()
  local sched=default
  while [[ "${1:-}" == -e || "${1:-}" == -w ]]; do
    envs+=("$1" "$2")
    if [[ "$1" == -e && "$2" == TIMELIKE_SNAPSHOT_INTERVAL=* ]]; then sched=given; fi
    shift 2
  done
  # Feature 005 slice 1: a bash started inside a workspace takes a scheduled snapshot when one is due
  # (/etc/timelike/shell-env.bash, FR-32). Cells of other features measure their own behaviour, so the
  # harness turns it off unless a cell sets TIMELIKE_SNAPSHOT_INTERVAL itself; the scheduled snapshot's
  # own cells set it, the default interval included (a-directory-removed-by-a-script-*.bats).
  [[ "$sched" == given ]] || envs=(-e TIMELIKE_SNAPSHOT_INTERVAL=off "${envs[@]}")
  # In a parallel lane only (lane.bash): the file's name travels with every command it runs, so the
  # whole-container checks below can tell this file's processes from its neighbours'. A serial lane adds nothing.
  [[ -z "${TL_E2E_FILE_ID:-}" ]] || envs=(-e "TL_E2E_FILE=${TL_E2E_FILE_ID}" "${envs[@]}")
  local style="$1" tty="$2" cmd="$3"
  local -a shell docker_args
  mapfile -t shell < <(_shell_argv "$style") || return 2
  [[ ${#shell[@]} -eq 2 ]] || return 2

  case "$tty" in
    notty) docker_args=(exec "${envs[@]}" "$AGENT_CONTAINER" "${shell[@]}" "$cmd") ;;
    tty) docker_args=(exec -t "${envs[@]}" "$AGENT_CONTAINER" "${shell[@]}" "$cmd") ;;
    pty)
      # The command travels in TL_CMD so no quoting layer is added: script runs its -c string with
      # $SHELL (unset → /bin/sh), which expands "$TL_CMD" into exactly one argument.
      # shellcheck disable=SC2016 # expanded inside the container, on purpose
      docker_args=(exec -e "TL_CMD=${cmd}" "${envs[@]}" "$AGENT_CONTAINER"
        script -qec "${shell[0]} ${shell[1]} \"\$TL_CMD\"" /dev/null)
      ;;
    *) echo "unknown tty mode '$tty' (want notty|tty|pty)" >&2; return 2 ;;
  esac

  local start end rc
  start=$(now_ms)
  # The runner's timeout may be busybox's, which reports a kill as 128+signal, not 124. Elapsed time
  # decides instead: reaching the limit is a timeout, whatever status the killed CLI left.
  timeout "$RUN_TIMEOUT" docker "${docker_args[@]}" </dev/null && rc=0 || rc=$?
  end=$(now_ms)
  EXEC_ELAPSED_MS=$((end - start))
  if ((EXEC_ELAPSED_MS >= RUN_TIMEOUT * 1000)); then
    rc=124
    # Killing the docker CLI does not kill the process in the container; do not leave it behind.
    kill_strays
  fi
  return "$rc"
}

# run_in [-e K=V]... [-w DIR] STYLE TTY CMD — the entry point tests use.
# bats `run` around exec_in. Sets $status, $output (CRs stripped), ${lines[@]}, and:
#   ELAPSED_MS  wall time of the whole docker exec, measured on the runner side, in ms
#   ELAPSED_S   the same, as seconds with 3 decimals
# Timing is taken around `run` because `run` executes in a subshell (EXEC_ELAPSED_MS is lost there).
run_in() {
  local start end
  start=$(now_ms)
  run exec_in "$@"
  end=$(now_ms)
  ELAPSED_MS=$((end - start))
  ELAPSED_S="$(ms_to_s "$ELAPSED_MS")"
  if ((ELAPSED_MS >= RUN_TIMEOUT * 1000)) && [[ "$status" != 124 ]]; then
    status=124
  fi
  output="${output//$'\r'/}"
  if [[ -n "$output" ]]; then
    mapfile -t lines <<<"$output"
  else
    lines=()
  fi
}

# drop_ic_notty_lines — after a `bash -ic` run with no terminal, remove the two lines bash itself prints
# before anything else (job control has no terminal), and only those: each in its exact text (the
# process group is the one field allowed to vary: `-1` in docker exec, a pid elsewhere), at most once,
# in bash's order, and only at the very start. Rebuilds $output and ${lines[@]} from what is left, so a
# cell's positional reads mean what they mean in the -c and -lc styles. Lane 005s1-c: three ic cells
# read the restore's verdict and `type -a`'s first line two lines late.
IC_NOTTY_LINES=(
  '^bash: cannot set terminal process group \((-1|[0-9]+)\): Inappropriate ioctl for device$'
  '^bash: no job control in this shell$'
)
drop_ic_notty_lines() {
  local known
  for known in "${IC_NOTTY_LINES[@]}"; do
    if ((${#lines[@]} > 0)) && [[ "${lines[0]}" =~ $known ]]; then lines=("${lines[@]:1}"); fi
  done
  if ((${#lines[@]} > 0)); then output="$(printf '%s\n' "${lines[@]}")"; else output=""; fi
}

# exec_plain CMD... — `docker exec` (no shell, no tty) for setup, teardown and control reads.
# Bounded like everything else. Not a style under test.
# Reaching the bound is a failure (124) whatever status the killed CLI left, as in exec_in: a docker CLI
# stopped by the runner's timeout can exit 0, and the command it started carries on in the container. A
# fixture cut off that way let the git-log file's cells run against a half-built repository while its
# script went on committing beside them (feedback maint-20261015-115635, item 2).
exec_plain() {
  local start rc
  start=$(now_ms)
  timeout "$RUN_TIMEOUT" docker exec "$AGENT_CONTAINER" "$@" </dev/null && rc=0 || rc=$?
  if (($(now_ms) - start >= RUN_TIMEOUT * 1000)); then
    printf 'exec_plain: stopped at the %ss bound, so it did not finish: %s\n' "$RUN_TIMEOUT" "$*" >&2
    rc=124
  fi
  return "$rc"
}

# assert_within LIMIT_S — the last run_in concluded in under LIMIT_S seconds and did not time out.
assert_within() {
  local limit_s="$1"
  if [[ "$status" == 124 ]]; then
    echo "timed out after ${ELAPSED_S}s (runner limit ${RUN_TIMEOUT}s): the command waited on something" >&2
    return 1
  fi
  if ((ELAPSED_MS >= limit_s * 1000)); then
    echo "took ${ELAPSED_S}s, limit ${limit_s}s" >&2
    return 1
  fi
}

# assert_status N — exact exit status of the last run, with the output shown on mismatch.
assert_status() {
  if [[ "$status" != "$1" ]]; then
    printf 'expected exit %s, got %s after %ss; output:\n%s\n' "$1" "$status" "${ELAPSED_S:-?}" "$output" >&2
    return 1
  fi
}

# assert_output_has TEXT — fixed-string match anywhere in $output.
assert_output_has() {
  if [[ "$output" != *"$1"* ]]; then
    printf 'output lacks %q; output:\n%s\n' "$1" "$output" >&2
    return 1
  fi
}

# assert_no_line_matching ERE — no line of $output matches.
assert_no_line_matching() {
  local line
  for line in "${lines[@]}"; do
    if [[ "$line" =~ $1 ]]; then
      printf 'unexpected line matching /%s/: %s\n' "$1" "$line" >&2
      return 1
    fi
  done
}

# value_of KEY — the value from a "KEY=value" line in $output (first match), or "<absent>".
value_of() {
  local line
  for line in "${lines[@]}"; do
    if [[ "$line" == "$1="* ]]; then
      printf '%s' "${line#"$1="}"
      return 0
    fi
  done
  printf '<absent>'
}

# assert_value KEY EXPECTED
assert_value() {
  local got
  got="$(value_of "$1")"
  if [[ "$got" != "$2" ]]; then
    printf '%s: expected %q, got %q; output:\n%s\n' "$1" "$2" "$got" "$output" >&2
    return 1
  fi
}

# assert_no_pager_or_editor — reads the process table in the container directly (P001): no pager or
# editor process exists. pgrep -x matches the process name exactly, so the pattern cannot match the
# command line that carries it.
assert_no_pager_or_editor() {
  local procs
  procs="$(pager_editor_procs)" || true
  if [[ -n "$procs" ]]; then
    printf 'pager/editor processes left running in the container:\n%s\n' "$procs" >&2
    return 1
  fi
}

# pager_editor_procs — `pgrep -a -x` over the pager and editor names. In a parallel lane, only the processes
# this file started: those whose environment carries its TL_E2E_FILE (exec_in sets it). Other files run beside
# it there, and timelike's own `view` tool is a script, so its process is named `view`, which is on the list.
# Reading /proc/PID/environ needs the same uid, and every cell runs as the agent.
pager_editor_procs() {
  if [[ -z "${TL_E2E_FILE_ID:-}" ]]; then
    exec_plain pgrep -a -x "$PAGER_EDITOR_NAMES"
    return
  fi
  # shellcheck disable=SC2016 # expanded in the container
  exec_plain sh -c 'for p in $(pgrep -x "$1"); do
    if grep -qzx "TL_E2E_FILE=$2" "/proc/$p/environ" 2>/dev/null; then
      printf "%s %s\n" "$p" "$(tr "\0" " " <"/proc/$p/cmdline" 2>/dev/null)"
    fi
  done' s "$PAGER_EDITOR_NAMES" "$TL_E2E_FILE_ID"
}

# kill_strays — best effort: kill any pager/editor left by a hung command, so one failure does not
# cascade into every later test. In a parallel lane, only this file's own (pager_editor_procs).
kill_strays() {
  if [[ -z "${TL_E2E_FILE_ID:-}" ]]; then
    exec_plain pkill -KILL -x "$PAGER_EDITOR_NAMES" >/dev/null 2>&1 || true
    return 0
  fi
  local procs p
  procs="$(pager_editor_procs 2>/dev/null)" || true
  for p in $(printf '%s\n' "$procs" | cut -d' ' -f1); do
    exec_plain kill -KILL "$p" >/dev/null 2>&1 || true
  done
}

# container_tmpdir PREFIX — make a fresh directory under /tmp in the container (owned by the agent
# user) and print its path.
container_tmpdir() {
  local d
  d="$(exec_plain mktemp -d "/tmp/$1.XXXXXX")" || return 1
  d="${d//$'\r'/}"
  [[ "$d" == /tmp/"$1".* ]] || { echo "mktemp in container returned '$d'" >&2; return 1; }
  printf '%s' "$d"
}

# state_root_dir NAME — a per-test state root on the agent's state volume (feature 005 slice 1, FR-25):
# the test's own snapshot stores, isolated from every other test's, on the volume's filesystem, so a
# result carries no not-persistent line (FR-27), as in the configuration compose.yaml gives the agent.
state_root_dir() {
  local d
  d="$(exec_plain mktemp -d "/var/lib/timelike/e2e-$1.XXXXXX")" || return 1
  d="${d//$'\r'/}"
  [[ "$d" == /var/lib/timelike/e2e-"$1".* ]] || { echo "mktemp on the state volume returned '$d'" >&2; return 1; }
  printf '%s' "$d"
}

# state_root_rm PATH... — remove per-test state roots (only /var/lib/timelike/e2e-*).
state_root_rm() {
  local p
  for p in "$@"; do
    [[ -n "$p" && "$p" == /var/lib/timelike/e2e-?* ]] || continue
    exec_plain rm -rf -- "$p" >/dev/null 2>&1 || true
  done
}

# container_rm PATH... — remove paths created by a test (only under /tmp).
container_rm() {
  local p
  for p in "$@"; do
    [[ -n "$p" && "$p" == /tmp/?* ]] || continue
    exec_plain rm -rf -- "$p" >/dev/null 2>&1 || true
  done
}

# copy_into_container SRC DEST [MODE] — copy a runner-side file into the container, as the agent user.
# Streams through `docker exec -i ... cat` rather than `docker cp`: docker cp creates files as root,
# which the agent user could then neither chmod nor remove from /tmp (sticky). MODE defaults to 0644.
copy_into_container() {
  local src="$1" dest="$2" mode="${3:-0644}"
  [[ -f "$src" ]] || { echo "copy_into_container: no such file $src" >&2; return 1; }
  # In a parallel lane, written beside DEST and renamed into place, so a file reading DEST at the same moment
  # (two files copy the same fixture to one /tmp path; maint-lane-speed) sees the old copy or the new one,
  # never a partial one. A serial lane writes in place, as it always has.
  if [[ -n "${TL_E2E_FILE_ID:-}" ]]; then
    # shellcheck disable=SC2016 # expanded in the container
    timeout "$RUN_TIMEOUT" docker exec -i "$AGENT_CONTAINER" \
      sh -c 't="$1.tl-copy.$$" && cat > "$t" && chmod "$2" "$t" && mv -f "$t" "$1"' copy "$dest" "$mode" <"$src"
    return
  fi
  # shellcheck disable=SC2016 # expanded in the container
  timeout "$RUN_TIMEOUT" docker exec -i "$AGENT_CONTAINER" \
    sh -c 'cat > "$1" && chmod "$2" "$1"' copy "$dest" "$mode" <"$src"
}

# stamp_check — refuse to test a stale or unstamped image (H8; lore docker-compose Q004; cross-stack
# P004: verify the artefact). Reads, directly:
#   1. GIT_SHA exported by tests/run.sh (git rev-parse HEAD on the host; the runner has no git)
#   2. the revision label of the image the RUNNING container was created from (not the tag, which a
#      later build may have moved while an old container kept running)
#   3. /opt/timelike/REVISION inside the running container
# All three must be equal and non-empty.
stamp_check() {
  if [[ -z "${GIT_SHA:-}" ]]; then
    echo "stamp_check: GIT_SHA is empty — run the suite through tests/run.sh, which exports it" >&2
    return 1
  fi
  local image_id label file
  image_id="$(docker inspect --format '{{.Image}}' "$AGENT_CONTAINER" 2>&1)" || {
    echo "stamp_check: container ${AGENT_CONTAINER} not found: ${image_id}" >&2
    return 1
  }
  label="$(docker image inspect --format "{{ index .Config.Labels \"${REVISION_LABEL}\" }}" "$image_id" 2>&1)" || {
    echo "stamp_check: cannot inspect image ${image_id}: ${label}" >&2
    return 1
  }
  file="$(exec_plain cat /opt/timelike/REVISION 2>&1)" || {
    echo "stamp_check: cannot read /opt/timelike/REVISION in ${AGENT_CONTAINER}: ${file}" >&2
    return 1
  }
  if [[ -z "$label" || "$label" == "<no value>" ]]; then
    echo "stamp_check: image ${image_id} carries no ${REVISION_LABEL} label (H8)" >&2
    return 1
  fi
  if [[ "$label" != "$GIT_SHA" || "$file" != "$GIT_SHA" ]]; then
    echo "stamp_check: stale image — HEAD ${GIT_SHA}, running container's image label '${label}', /opt/timelike/REVISION '${file}'. Rebuild and recreate (tests/run.sh does both)." >&2
    return 1
  fi
}

# ── Throwaway containers (slice 1, T051: SC-8 needs a CPU limit the compose service does not set) ─
# They run the image the RUNNING agent container was created from — the one stamp_check verified —
# never the tag, which a later build may have moved. The privilege boundary is compose's (R7):
# cap_drop ALL, no-new-privileges, init, `sleep infinity`. Each carries the label below, so a run that
# died before its teardown leaves nothing the next run cannot find and remove.
THROWAWAY_LABEL=timelike.test.throwaway

# start_throwaway NAME [DOCKER RUN ARG]... — start one detached; extra args (e.g. --cpus 1.5) go
# before the image. Prints nothing on success; docker's error on failure, or, when docker printed none,
# its exit status and how long it took: a CLI stopped by the runner's timeout prints nothing (lane-speed
# par1, SC-8: "cannot start … with --cpus 1.5:" and no reason; feedback maint-20261015-115635, item 3).
# A start that failed part-way is removed, so a container it created is not left behind.
start_throwaway() {
  local name="$1" image err rc start
  shift
  image="$(docker inspect --format '{{.Image}}' "$AGENT_CONTAINER" 2>&1)" || {
    echo "start_throwaway: cannot read the image of ${AGENT_CONTAINER}: ${image}" >&2
    return 1
  }
  start=$(now_ms)
  err="$(timeout "$RUN_TIMEOUT" docker run -d --rm --name "$name" --label "${THROWAWAY_LABEL}=1" \
    --cap-drop ALL --security-opt no-new-privileges:true --init \
    "$@" "$image" sleep infinity </dev/null 2>&1 >/dev/null)" && return 0 || rc=$?
  printf '%s\n' "${err:-docker printed nothing: exit ${rc} after $(ms_to_s $(($(now_ms) - start)))s (bound ${RUN_TIMEOUT}s)}" >&2
  remove_throwaway "$name"
  return "$rc"
}

# remove_throwaway NAME... — best effort; a missing container is not an error.
remove_throwaway() {
  local name
  for name in "$@"; do
    [[ -n "$name" ]] || continue
    timeout "$RUN_TIMEOUT" docker rm -f "$name" </dev/null >/dev/null 2>&1 || true
  done
}

# remove_stale_throwaways — remove every container a previous run left behind (by label).
# In a parallel lane, no-op: other files' throwaways (pyq's included) carry the same label and are in use, so
# tests/run.sh removes the stale ones once, before the first file starts (maint-lane-speed).
remove_stale_throwaways() {
  [[ -z "${TL_E2E_LOCK:-}" ]] || return 0
  local ids
  ids="$(timeout "$RUN_TIMEOUT" docker ps -aq --filter "label=${THROWAWAY_LABEL}" </dev/null 2>/dev/null)" || return 0
  # shellcheck disable=SC2086 # one id per word, on purpose
  [[ -z "$ids" ]] || remove_throwaway $ids
}

# cpu_list_count LIST — the number of CPUs in a Cpus_allowed_list value ("0-3,8,10-11" → 7), or
# nothing (status 1) if LIST is not one. Mirrors the hook's parser, and is checked against it only
# through the image (the hook's own logic is unit-tested in tests/host/test_shell_env_hook.sh).
cpu_list_count() {
  local list="${1//[[:space:]]/}" item lo hi n=0
  [[ "$list" =~ ^[0-9]+(-[0-9]+)?(,[0-9]+(-[0-9]+)?)*$ ]] || return 1
  list+=","
  while [[ -n "$list" ]]; do
    item="${list%%,*}"
    list="${list#*,}"
    lo="${item%-*}"
    hi="${item#*-}"
    n=$((n + 10#$hi - 10#$lo + 1))
  done
  printf '%s' "$n"
}

# ── Adele (feature 004) ────────────────────────────────────────────────────────────────────────────
# Adele's and the stand-in's images are FROM scratch: no shell, no cat. Everything below execs their
# own binaries, or reads through a throwaway container of the AGENT's image (which has a userland).
ADELE_CONTAINER="${ADELE_CONTAINER:-timelike-adele}"
STANDIN_CONTAINER="${STANDIN_CONTAINER:-timelike-adele-standin}"
# compose project `timelike` (compose.yaml `name:`) + volume `adele-secret` (spec D-8)
ADELE_SECRET_VOLUME="${ADELE_SECRET_VOLUME:-timelike_adele-secret}"

# image_revision CONTAINER — the revision label of the image the running CONTAINER was created from.
image_revision() {
  local image_id
  image_id="$(docker inspect --format '{{.Image}}' "$1" 2>&1)" || {
    echo "image_revision: container $1 not found: ${image_id}" >&2
    return 1
  }
  docker image inspect --format "{{ index .Config.Labels \"${REVISION_LABEL}\" }}" "$image_id"
}

# stamp_check_adele — refuse to test a stale Adele or stand-in (H8; cross-stack P003; spec FR-23):
# GIT_SHA, both running containers' image labels, and `adeled version` must all be equal.
stamp_check_adele() {
  [[ -n "${GIT_SHA:-}" ]] || { echo "stamp_check_adele: GIT_SHA is empty — run through tests/run.sh" >&2; return 1; }
  local adele standin reported
  adele="$(image_revision "$ADELE_CONTAINER")" || return 1
  standin="$(image_revision "$STANDIN_CONTAINER")" || return 1
  reported="$(adeled version 2>&1)" || { echo "stamp_check_adele: adeled version failed: ${reported}" >&2; return 1; }
  if [[ "$adele" != "$GIT_SHA" || "$standin" != "$GIT_SHA" || "$reported" != "$GIT_SHA" ]]; then
    echo "stamp_check_adele: stale — HEAD ${GIT_SHA}, adele label '${adele}', stand-in label '${standin}', adeled version '${reported}'. Rebuild and recreate (tests/run.sh does both)." >&2
    return 1
  fi
}

# adeled ARG... — the operator's command, run inside Adele's container, exactly as an operator would.
adeled() {
  timeout "$RUN_TIMEOUT" docker exec "$ADELE_CONTAINER" /usr/local/bin/adeled "$@" </dev/null
}

# standin_list — the stand-in's OWN record (JSON), read by the stand-in from its file, not via HTTP
# (cross-stack P004: "performed" is checked against the capability's record, never Adele's word).
standin_list() {
  timeout "$RUN_TIMEOUT" docker exec "$STANDIN_CONTAINER" /usr/local/bin/adele-standin list </dev/null
}

# standin_names — one box name per line, from standin_list (the runner has no jq).
standin_names() {
  standin_list | grep -o '"name": "[^"]*"' | sed 's/^"name": "//; s/"$//'
}

# agent_image — the image the running agent container was created from (has a userland).
agent_image() { docker inspect --format '{{.Image}}' "$AGENT_CONTAINER"; }

# canary_bytes — the environment's canary, read from Adele's secret volume by a throwaway root
# container with no network (spec D-8). Tests search for these exact bytes (SC-4).
canary_bytes() {
  local image
  image="$(agent_image)" || return 1
  timeout "$RUN_TIMEOUT" docker run --rm --network none --user 0:0 --cap-drop ALL \
    --label "${THROWAWAY_LABEL}=1" -v "${ADELE_SECRET_VOLUME}:/s:ro" --entrypoint cat "$image" /s/canary </dev/null
}

# adele_run_with_grants FILE — run a THROWAWAY Adele (the running Adele's image) in the foreground on
# the grant file FILE (a path under the repository, as the Docker host sees it via REPO_HOST), with no
# network, a private /tmp ledger and the real canary volume. A malformed file makes it exit at once;
# a valid one serves, so the call is bounded and a valid file is expected to time out (124).
# The bound is decided by elapsed time, as exec_in does: the runner's timeout may be busybox's, which
# reports a kill as 128+signal rather than 124.
adele_run_with_grants() {
  local file="$1" image name rc start
  image="$(docker inspect --format '{{.Image}}' "$ADELE_CONTAINER")" || return 1
  name="adele-grants-$$-${RANDOM}"
  start=$SECONDS
  timeout 10 docker run --rm --name "$name" --network none --label "${THROWAWAY_LABEL}=1" \
    --cap-drop ALL --security-opt no-new-privileges:true --read-only --tmpfs /tmp \
    -e ADELE_DB=/tmp/adele.db -e ADELE_CANARY_FILE=/s/canary \
    -v "${ADELE_SECRET_VOLUME}:/s:ro" -v "${REPO_HOST}/${file}:/etc/adele/grants.conf:ro" \
    "$image" serve </dev/null 2>&1 && rc=0 || rc=$?
  if ((SECONDS - start >= 10)); then
    rc=124
  fi
  remove_throwaway "$name"
  return "$rc"
}

# pyq SCRIPT — run Python (the agent image's interpreter) in a THROWAWAY container with no network and
# nothing mounted, reading stdin: the runner has neither jq nor python. Used to read JSON that came
# from outside the agent (the ledger, the stand-in's record); the agent container never sees it.
# On failure it says so on stderr with its exit status and time: a cell that fails here failed in its own
# parsing, not in the tool it ran (lane-speed par1, SC-4's entry cap: the tool's answer was right and the
# parse failed after 295 s of a stalled daemon; feedback maint-20261015-115635, item 3).
pyq() {
  local image rc start
  image="$(agent_image)" || return 1
  start=$(now_ms)
  timeout "$PYQ_TIMEOUT" docker run --rm -i --network none --cap-drop ALL --label "${THROWAWAY_LABEL}=1" \
    --entrypoint "$AGENT_PY" "$image" -I -c "$1" && return 0 || rc=$?
  printf 'pyq: the parser exited %s after %ss (bound %ss)\n' "$rc" "$(ms_to_s $(($(now_ms) - start)))" "$PYQ_TIMEOUT" >&2
  return "$rc"
}

# ── Real pytest, ruff and mypy in the agent container (feature 012, research R1) ───────────────────
# install_uv_tool_wrappers DIR — write executable wrappers DIR/pytest, DIR/ruff and DIR/mypy inside the
# agent container (DIR must be under /tmp, e.g. from container_tmpdir), then warm them once.
#
# The image has no pytest, ruff or mypy (only uv and its Python). Each wrapper runs the REAL tool at
# the version pinned in pins.env (PYTEST_VERSION, RUFF_VERSION, MYPY_VERSION), fetched by the image's
# uv, exactly as the lane's own unit and lint steps fetch them: never a stub with canned output (P005).
# pins.env is read here, on the runner side, from the mounted repository: tests/run.sh passes none of
# its values into the runner. uv's cache and tool directories, and the mypy and ruff caches, live
# under DIR, so nothing lands in a cell's workspace except what pytest itself writes. Cells put DIR
# first on PATH in their own command string. NEEDS NETWORK ACCESS to PyPI on the first warm-up, as
# the unit step does; the warm-up is bounded by 300 s instead of RUN_TIMEOUT, and the cells after it
# then start from a warm cache (mypy's builtins cache included).
install_uv_tool_wrappers() {
  local dir="$1" pins="${BATS_TEST_DIRNAME}/../../pins.env" pair name key ver body out
  [[ "$dir" == /tmp/?* ]] || { echo "install_uv_tool_wrappers: DIR must be under /tmp: '${dir}'" >&2; return 1; }
  [[ -f "$pins" ]] || { echo "install_uv_tool_wrappers: no pins.env at ${pins}" >&2; return 1; }
  for pair in pytest:PYTEST_VERSION ruff:RUFF_VERSION mypy:MYPY_VERSION; do
    name="${pair%%:*}"
    key="${pair#*:}"
    ver="$(sed -n "s/^${key}=//p" "$pins" | head -n 1)"
    [[ "$ver" =~ ^[0-9][0-9A-Za-z.]*$ ]] || { echo "install_uv_tool_wrappers: ${key} in pins.env is '${ver}'" >&2; return 1; }
    body="#!/bin/sh
# the real ${name} ${ver} (pins.env ${key}), run by the image's uv: feature 012, research R1
export UV_CACHE_DIR='${dir}/.uv-cache' UV_TOOL_DIR='${dir}/.uv-tools' UV_PYTHON_DOWNLOADS=never
export MYPY_CACHE_DIR='${dir}/.mypy-cache' RUFF_CACHE_DIR='${dir}/.ruff-cache'
exec /bin/uv --quiet tool run --python ${AGENT_PY} '${name}@${ver}' \"\$@\""
    # shellcheck disable=SC2016 # expanded in the container
    exec_plain sh -c 'mkdir -p "$(dirname "$1")" && printf "%s\n" "$2" >"$1" && chmod 0755 "$1"' \
      wrapper "${dir}/${name}" "$body" || { echo "install_uv_tool_wrappers: cannot write ${dir}/${name}" >&2; return 1; }
  done
  # Warm-up: fetch each tool once and check it reports the pinned version (the wrapper is the tool).
  local RUN_TIMEOUT=300
  for pair in pytest:PYTEST_VERSION ruff:RUFF_VERSION mypy:MYPY_VERSION; do
    name="${pair%%:*}"
    ver="$(sed -n "s/^${pair#*:}=//p" "$pins" | head -n 1)"
    out="$(exec_plain "${dir}/${name}" --version 2>&1)" || { printf 'install_uv_tool_wrappers: %s --version failed:\n%s\n' "$name" "$out" >&2; return 1; }
    [[ "$out" == *"$ver"* ]] || { printf 'install_uv_tool_wrappers: %s --version does not report %s:\n%s\n' "$name" "$ver" "$out" >&2; return 1; }
  done
  # mypy's first check builds its builtins cache (seconds); do it here, not inside a timed cell.
  # shellcheck disable=SC2016 # expanded in the container
  out="$(exec_plain sh -c 'cd "$1" && printf "x: int = 1\n" >warm.py && ./mypy warm.py' warm "$dir" 2>&1)" ||
    { printf 'install_uv_tool_wrappers: mypy warm-up failed:\n%s\n' "$out" >&2; return 1; }
}

# ── A real installer, past the shims (feature 013; lane 013s1-b) ────────────────────────────────────
# /opt/timelike/shims is first on PATH and holds pip, pip3, uv, npm, npx and pnpm whether or not the
# installer is installed, so `command -v pnpm` finds the shim in an image with no pnpm. A cell asking "is NAME
# installed?" prepends REAL_ON_PATH_SH to its in-container script and calls `real_on_path NAME`, which asks
# what the shim asks (image/rootfs/opt/timelike/libexec/install-shim): the first NAME on PATH outside the
# shims directory. It prints that path, or nothing and exit 1. POSIX sh, so any cell's shell can run it.
# shellcheck disable=SC2016,SC2034 # expanded in the container; read by the cells that load helpers
REAL_ON_PATH_SH='real_on_path() {
  _rop_shims=${TIMELIKE_SHIMS:-/opt/timelike/shims}
  _rop_rest=${PATH-}:
  while [ -n "$_rop_rest" ]; do
    _rop_d=${_rop_rest%%:*}
    _rop_rest=${_rop_rest#*:}
    [ -n "$_rop_d" ] || _rop_d=.
    [ "$_rop_d" -ef "$_rop_shims" ] && continue
    if [ -f "$_rop_d/$1" ] && [ -x "$_rop_d/$1" ]; then printf "%s\n" "$_rop_d/$1"; return 0; fi
  done
  return 1
}'

# ── The registry stand-in (feature 013, the package guard; spec D-10, FR-33) ────────────────────────
# tests/fixtures/registry-standin.py, run INSIDE the agent container on its loopback with timelike's own
# interpreter, so no cell reaches a public registry (lore P005) and nothing is added to compose. It logs every
# request; a cell reads that log, never the guard's message, to see what was fetched (lore P004).
STANDIN_PY=/opt/timelike/python/bin/python3
GUARD_AGENT=timelike-package-guard/

# standin_start DIR [CATALOG] — copy the stand-in and a catalog (default tests/fixtures/registry-catalog.json)
# into DIR in the container and start it. Sets STANDIN_DIR, STANDIN_URL, STANDIN_SIMPLE (PyPI's Simple API
# root) and STANDIN_NPM (the npm registry root, with its trailing slash).
standin_start() {
  local dir="$1" catalog="${2:-${BATS_TEST_DIRNAME}/../fixtures/registry-catalog.json}" port="" i
  copy_into_container "${BATS_TEST_DIRNAME}/../fixtures/registry-standin.py" "${dir}/registry-standin.py" || return 1
  copy_into_container "$catalog" "${dir}/catalog.json" || return 1
  # shellcheck disable=SC2016 # expanded in the container
  exec_plain sh -c '"$1" -I "$2/registry-standin.py" --catalog "$2/catalog.json" --dir "$2/run" \
    </dev/null >"$2/standin.err" 2>&1 &' s "$STANDIN_PY" "$dir" || return 1
  for i in $(seq 100); do
    port="$(exec_plain cat "${dir}/run/port" 2>/dev/null)" && port="${port//[^0-9]/}" && [[ -n "$port" ]] && break
    sleep 0.1
  done
  if [[ -z "$port" ]]; then
    echo "standin_start: the stand-in did not start ($i tries): $(exec_plain cat "${dir}/standin.err" 2>&1)" >&2
    return 1
  fi
  STANDIN_DIR="$dir"
  STANDIN_URL="http://127.0.0.1:${port}"
  # shellcheck disable=SC2034 # read by the package guard's .bats files
  STANDIN_SIMPLE="${STANDIN_URL}/simple"
  # shellcheck disable=SC2034 # read by the package guard's .bats files
  STANDIN_NPM="${STANDIN_URL}/npm/"
}

# standin_stop — stop the stand-in by the pid it wrote (never by a name match).
standin_stop() {
  [[ -n "${STANDIN_DIR:-}" ]] || return 0
  # shellcheck disable=SC2016 # expanded in the container
  exec_plain sh -c 'p="$(cat "$1/run/pid" 2>/dev/null)" && kill "$p" 2>/dev/null; true' s "$STANDIN_DIR" || true
}

# standin_count WHAT — how many logged requests match: guard (the guard's user agent), files (a wheel or a
# tarball: anything downloaded), all. Read in the container from the stand-in's own log.
standin_count() {
  # shellcheck disable=SC2016 # python source, expanded by python
  exec_plain "$STANDIN_PY" -I -c '
import json, sys
what, agent = sys.argv[2], sys.argv[3]
rows = [json.loads(x) for x in open(sys.argv[1], encoding="utf-8") if x.strip()]
if what == "guard":
    rows = [r for r in rows if r["user_agent"].startswith(agent)]
elif what == "files":
    rows = [r for r in rows if r["path"].startswith("/files/") or "/-/" in r["path"]]
print(len(rows))' "${STANDIN_DIR}/run/requests.jsonl" "$1" "$GUARD_AGENT"
}

# standin_clear — empty the stand-in's log (between a cell's setup and what it measures).
standin_clear() {
  # shellcheck disable=SC2016 # expanded in the container
  exec_plain sh -c ': > "$1/run/requests.jsonl"' s "$STANDIN_DIR"
}

# standin_released ECOSYSTEM NAME VERSION — the release date the stand-in itself serves (PyPI's earliest
# upload-time, npm's time[VERSION]), as YYYY-MM-DD: what a refusal must name, read from the registry's data.
standin_released() {
  # shellcheck disable=SC2016 # python source, expanded by python
  exec_plain "$STANDIN_PY" -I -c '
import json, sys, urllib.request
eco, base, name, ver = sys.argv[1:5]
if eco == "pypi":
    req = urllib.request.Request(f"{base}/simple/{name}/", headers={"Accept": "application/vnd.pypi.simple.v1+json"})
    doc = json.load(urllib.request.urlopen(req, timeout=10))
    times = [f["upload-time"] for f in doc["files"] if f"-{ver}-" in f["filename"]]
    print(min(times)[:10])
else:
    doc = json.load(urllib.request.urlopen(f"{base}/npm/{name}", timeout=10))
    print(doc["time"][ver][:10])' "$1" "$STANDIN_URL" "$2" "$3"
}

# pyj CODE — run CODE with timelike's interpreter in the agent container, the last run's $output on stdin.
pyj() {
  printf '%s' "$output" | timeout "$RUN_TIMEOUT" docker exec -i "$AGENT_CONTAINER" "$STANDIN_PY" -I -c "$1"
}

# ── The agent's own install (feature 013 slice 1; FOR-MENTOR Item 24, condition 7) ──────────────────────
# run_bare STYLE DIR CMD [-e K=V ...] — CMD as the agent runs it, by the installer's bare name, so it reaches
# the guard through /opt/timelike/shims as the image wires it (nothing names package-guard). The cell's ENVS
# array and any -e words given after CMD are passed; DIR is the working directory.
#   c, lc, ic  bash -c / bash -lc / bash -ic CMD (ic: bash's two no-terminal lines dropped, so $output and
#              ${lines[@]} mean what they mean in the other styles)
#   script     CMD as the body of an executable bash script, DIR/.tl-install-<n>.sh, run by its path from
#              bash -c: a script the agent runs, where shell functions would not reach (Item 22's bound)
run_bare() {
  local style="$1" dir="$2" cmd="$3" file
  shift 3
  if [[ "$style" == script ]]; then
    file="${dir}/.tl-install-${RANDOM}.sh"
    # shellcheck disable=SC2016 # expanded in the container
    exec_plain sh -c 'printf "#!/bin/bash\n%s\n" "$2" >"$1" && chmod 0755 "$1"' s "$file" "$cmd" || return 1
    # shellcheck disable=SC2153 # ENVS is the calling cell file's own array
    run_in "${ENVS[@]}" "$@" -w "$dir" c notty "$file"
  else
    run_in "${ENVS[@]}" "$@" -w "$dir" "$style" notty "$cmd"
    [[ "$style" != ic ]] || drop_ic_notty_lines
  fi
}
