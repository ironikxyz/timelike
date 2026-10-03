#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# shellcheck disable=SC2030,SC2031 # bats runs each @test in its own subshell by design
# SC-4 (feature 004) — "No credential held by Adele appears in the agent's environment, filesystem,
# process arguments or any tool output, checked by a scan after a full request cycle" (send 12-rev2,
# slice 0; spec FR-18, D-8; tasks.md T019).
#
# The credential is the environment's canary (`tlcanary-` + 32 hex), read from Adele's secret volume by a
# throwaway container, so the search is for its EXACT bytes. setup_file runs a full request cycle from
# the agent — performed, refused (a port), extended by the operator, retried — keeping every client
# output (JSON and text) the runner saw. Then the canary is searched for in:
#   - every output of that cycle, as the runner received it
#   - `env` under bash -c and bash -lc
#   - every /proc/<pid>/environ and /proc/<pid>/cmdline the agent can read
#   - everything the agent can read on its filesystem (tar of /, excluding /proc, /sys and /dev), which
#     includes its scratch space and session event log
# The canary is NEVER passed into the agent container, not even as a search pattern: that would put it
# in the agent's own /proc/self/cmdline. Every search streams the agent's data OUT and greps on the
# runner (cross-stack P005: the check runs through the agent's real paths, not a helper of Adele's).
# Control: the same pipelines find the canary where it IS — in a throwaway container holding it — so a
# zero is a result and not a broken search.

load helpers

setup_file() {
  stamp_check
  stamp_check_adele
  CANARY="$(canary_bytes)"
  [[ "$CANARY" =~ ^tlcanary-[0-9a-f]{32}$ ]] || { echo "canary_bytes gave '${CANARY}'" >&2; return 1; }
  export CANARY
  CYCLE_OUT="${BATS_FILE_TMPDIR}/cycle.out"
  export CYCLE_OUT
  local style port
  for style in c lc; do
    port=2
    [[ "$style" == lc ]] && port=22
    {
      exec_in -e TIMELIKE_SESSION=sc4 "$style" notty "adele --json request standin.box create --grant leak --name t-sc4-a-${style} --ttl 1h --port 8080" || true
      exec_in -e TIMELIKE_SESSION=sc4 "$style" notty "adele --text request standin.box create --grant leak --name t-sc4-b-${style} --ttl 1h --port ${port}" || true
      exec_in -e TIMELIKE_SESSION=sc4 "$style" notty "adele --json grants; adele --text grants; adele --json status; adele --text status" || true
    } >>"$CYCLE_OUT" 2>&1
  done
  # the operator extends, and the refused requests are retried
  {
    adeled extend leak ports 2
    adeled extend leak ports 22
    exec_in -e TIMELIKE_SESSION=sc4 c notty "adele --json request standin.box create --grant leak --name t-sc4-b-c --ttl 1h --port 2"
    exec_in -e TIMELIKE_SESSION=sc4 lc notty "adele --text request standin.box create --grant leak --name t-sc4-b-lc --ttl 1h --port 22"
  } >>"$CYCLE_OUT" 2>&1
}

# count_in — how many times the canary occurs in stdin (binary-safe, on the runner).
count_in() { grep -aoF "$CANARY" | wc -l | tr -d ' '; }

@test "SC-4 004 the full request cycle ran: performed, refused, extended, retried" {
  grep -q '"outcome": "performed"' "$CYCLE_OUT" || { cat "$CYCLE_OUT" >&2; return 1; }
  grep -qF '"status": "grant_required"' "$CYCLE_OUT" || { echo "no refusal (grant envelope) in the cycle" >&2; return 1; }
  grep -q 'extended leak ports' "$CYCLE_OUT" || { echo "no extension in the cycle" >&2; return 1; }
  run standin_names
  for b in t-sc4-a-c t-sc4-a-lc t-sc4-b-c t-sc4-b-lc; do
    grep -qx "$b" <<<"$output" || { echo "the stand-in has no $b" >&2; return 1; }
  done
}

@test "SC-4 004 no credential held by Adele appears in any tool output of the cycle" {
  [[ "$(count_in <"$CYCLE_OUT")" -eq 0 ]] || { echo "the canary appeared in the client's output" >&2; return 1; }
}

check_env() {
  run exec_in "$1" notty 'env'
  [[ "$status" -eq 0 ]] || return 1
  [[ "$(count_in <<<"$output")" -eq 0 ]] || { echo "the canary is in the agent's environment ($(style_label "$1"))" >&2; return 1; }
}
@test "SC-4 004 no credential held by Adele appears in the agent's environment [bash -c]" { check_env c; }
@test "SC-4 004 no credential held by Adele appears in the agent's environment [bash -lc]" { check_env lc; }

@test "SC-4 004 no credential held by Adele appears in any process's arguments or environment the agent can read" {
  local n
  n="$(timeout "$RUN_TIMEOUT" docker exec "$AGENT_CONTAINER" bash -c 'for f in /proc/[0-9]*/cmdline /proc/[0-9]*/environ; do cat "$f" 2>/dev/null; echo; done' </dev/null | count_in)"
  [[ "$n" -eq 0 ]] || { echo "the canary is in /proc ($n occurrences)" >&2; return 1; }
}

@test "SC-4 004 no credential held by Adele appears anywhere on the agent's filesystem it can read" {
  local n
  n="$(timeout 120 docker exec "$AGENT_CONTAINER" tar -cf - --exclude=/proc --exclude=/sys --exclude=/dev --ignore-failed-read / 2>/dev/null </dev/null | count_in)"
  [[ "$n" -eq 0 ]] || { echo "the canary is on the agent's filesystem ($n occurrences)" >&2; return 1; }
}

@test "SC-4 004 control: the same searches find the canary where it is" {
  local image name n
  image="$(agent_image)"
  name="sc4-control-$$"
  # a throwaway of the agent's image with the canary in a file, an env var and a process's arguments
  # (sh stays alive while sleep runs, so its own command line, holding the canary, is in /proc)
  timeout "$RUN_TIMEOUT" docker run -d --rm --name "$name" --label "${THROWAWAY_LABEL}=1" --network none \
    -e "PLANTED=${CANARY}" "$image" sh -c "printf '%s' '${CANARY}' > /tmp/planted; sleep 300; : '${CANARY}'" </dev/null >/dev/null
  n="$(timeout "$RUN_TIMEOUT" docker exec "$name" bash -c 'for f in /proc/[0-9]*/cmdline /proc/[0-9]*/environ; do cat "$f" 2>/dev/null; echo; done' </dev/null | count_in)"
  local fs
  fs="$(timeout 120 docker exec "$name" tar -cf - --exclude=/proc --exclude=/sys --exclude=/dev --ignore-failed-read / 2>/dev/null </dev/null | count_in)"
  remove_throwaway "$name"
  [[ "$n" -ge 1 ]] || { echo "control: the /proc search did not find a planted canary" >&2; return 1; }
  [[ "$fs" -ge 1 ]] || { echo "control: the filesystem search did not find a planted canary" >&2; return 1; }
}
