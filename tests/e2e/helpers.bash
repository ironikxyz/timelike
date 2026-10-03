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

AGENT_CONTAINER="${AGENT_CONTAINER:-timelike-agent}"
# shellcheck disable=SC2034 # used by the .bats files that load this
AGENT_PY=/opt/timelike/python/bin/python3
REVISION_LABEL=org.opencontainers.image.revision
# Runner-side limit per docker exec. Criteria assert far tighter bounds (20 s, 10 s); this exists so
# a hang becomes a failure (rc 124), never a wait (P2).
RUN_TIMEOUT="${RUN_TIMEOUT:-30}"
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

# exec_in [-e K=V]... STYLE TTY CMD
# Runs CMD in the agent container, bounded by RUN_TIMEOUT on the runner side. No `run` wrapper: the
# exit status is the command's (or 124 on timeout). Prints the container output unmodified.
# Sets EXEC_ELAPSED_MS.
exec_in() {
  local -a envs=()
  while [[ "${1:-}" == -e ]]; do
    envs+=(-e "$2")
    shift 2
  done
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

# run_in [-e K=V]... STYLE TTY CMD — the entry point tests use.
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

# exec_plain CMD... — `docker exec` (no shell, no tty) for setup, teardown and control reads.
# Bounded like everything else. Not a style under test.
exec_plain() {
  timeout "$RUN_TIMEOUT" docker exec "$AGENT_CONTAINER" "$@" </dev/null
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
  procs="$(exec_plain pgrep -a -x "$PAGER_EDITOR_NAMES")" || true
  if [[ -n "$procs" ]]; then
    printf 'pager/editor processes left running in the container:\n%s\n' "$procs" >&2
    return 1
  fi
}

# kill_strays — best effort: kill any pager/editor left by a hung command, so one failure does not
# cascade into every later test.
kill_strays() {
  exec_plain pkill -KILL -x "$PAGER_EDITOR_NAMES" >/dev/null 2>&1 || true
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
# before the image. Prints nothing on success; docker's error on failure.
start_throwaway() {
  local name="$1" image
  shift
  image="$(docker inspect --format '{{.Image}}' "$AGENT_CONTAINER" 2>&1)" || {
    echo "start_throwaway: cannot read the image of ${AGENT_CONTAINER}: ${image}" >&2
    return 1
  }
  timeout "$RUN_TIMEOUT" docker run -d --rm --name "$name" --label "${THROWAWAY_LABEL}=1" \
    --cap-drop ALL --security-opt no-new-privileges:true --init \
    "$@" "$image" sleep infinity </dev/null >/dev/null
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
remove_stale_throwaways() {
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
pyq() {
  local image
  image="$(agent_image)" || return 1
  timeout "$RUN_TIMEOUT" docker run --rm -i --network none --cap-drop ALL --label "${THROWAWAY_LABEL}=1" \
    --entrypoint "$AGENT_PY" "$image" -I -c "$1"
}
