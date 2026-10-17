#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# shellcheck disable=SC2030,SC2031 # bats runs each @test in its own subshell by design
# Isolation (feature 004) — spec FR-4, FR-7, FR-20; stack rule 1: "Nothing in the agent image may read
# Adele's volume, config or credentials — test it (feature 12)"; tasks.md T020.
#
#   - Nothing of Adele's is mounted into the agent: its container's one mount is its own state root
#     (the named volume timelike-state at /var/lib/timelike; feature 005 slice 1, FR-26, declared there
#     as a change to this cell, which read "no mounts at all"), read from outside (the authoritative
#     view — a path the agent cannot stat proves nothing about whether it exists). So the grant file,
#     the ledger and the canary have no path in the agent's filesystem, and nothing the agent does can
#     change a grant.
#   - Adele's own files are hers: her state, her grant file (read-only) and the canary volume are mounted
#     into her container only.
#   - The stand-in refuses a request that does not carry the canary — tested directly against it, from
#     a throwaway on the stand-in's own network, without the credential and with a wrong one — and its
#     record is unchanged afterwards (FR-20; cross-stack P005: the credential is what authorises).

load helpers

setup_file() {
  stamp_check
  stamp_check_adele
}

# Feature 13 added the workspace: a bind of the host's directory at the same absolute path (014 research R9). The
# agent's mounts are exactly those two, and none of them is Adele's: not her state, her secret, her grant file, or
# the Docker socket (constitution H1).
@test "004 nothing of Adele's is mounted into the agent: its mounts are its own state volume and its workspace" {
  local mounts ws="${TIMELIKE_WORKSPACE:-}"
  mounts="$(docker inspect --format '{{range .Mounts}}{{.Type}} {{.Name}} {{.Source}} {{.Destination}};{{end}}' "$AGENT_CONTAINER")"
  [[ -n "$ws" ]] || { echo "no TIMELIKE_WORKSPACE in the runner (tests/run.sh's up step sets it)" >&2; return 1; }
  local want_state='volume [A-Za-z0-9_.-]*timelike-state [^ ]* /var/lib/timelike;'
  [[ "$mounts" =~ $want_state ]] || { echo "no state volume: $mounts" >&2; return 1; }
  [[ "$mounts" == *"bind  ${ws} ${ws};"* ]] || { echo "no workspace bind at the same path: $mounts" >&2; return 1; }
  [[ "$(grep -o ';' <<<"$mounts" | wc -l | tr -d ' ')" == 2 ]] || { echo "more than two mounts: $mounts" >&2; return 1; }
  [[ "$mounts" != *adele* && "$mounts" != *docker.sock* ]] || { echo "one of Adele's: $mounts" >&2; return 1; }
}

check_no_adele_paths() {
  run_in "$1" notty 'for p in /etc/adele /run/adele-secret /var/lib/adele/adele.db; do [ -e "$p" ] && echo "present: $p"; done; echo done'
  assert_output_has "done"
  if [[ "$output" == *present:* ]]; then
    echo "$output" >&2
    return 1
  fi
}
@test "004 the grant file, the ledger and the canary have no path in the agent's filesystem [bash -c]" { check_no_adele_paths c; }
@test "004 the grant file, the ledger and the canary have no path in the agent's filesystem [bash -lc]" { check_no_adele_paths lc; }

@test "004 Adele's state, grant file, canary and (feature 13) the Docker socket are mounted into her container, read-only where they are config" {
  local m
  m="$(docker inspect --format '{{range .Mounts}}{{.Destination}}:{{.RW}} {{end}}' "$ADELE_CONTAINER")"
  for want in /var/lib/adele:true /etc/adele/grants.conf:false /run/adele-secret:false /var/run/docker.sock:true; do
    [[ " $m " == *" ${want} "* ]] || { echo "Adele's mounts: $m (want ${want})" >&2; return 1; }
  done
}

# from a throwaway on the stand-in's own network (the agent is not on it); prints the HTTP status
standin_post() {
  local auth="$1" image
  image="$(agent_image)"
  timeout "$PLUMBING_TIMEOUT" docker run --rm --network timelike_adele-standin --cap-drop ALL \
    --label "${THROWAWAY_LABEL}=1" --entrypoint "$AGENT_PY" "$image" -I -c "
import urllib.request, urllib.error
req = urllib.request.Request('http://adele-standin:8481/v1/boxes', method='POST',
    data=b'{\"name\": \"t-iso-intruder\", \"ttl_seconds\": 3600, \"ports\": []}',
    headers={'Content-Type': 'application/json', **({'Authorization': '${auth}'} if '${auth}' else {})})
try:
    print(urllib.request.urlopen(req, timeout=5).status)
except urllib.error.HTTPError as e:
    print(e.code)
" </dev/null
}

@test "004 the stand-in refuses a request without the credential, and creates nothing" {
  run standin_post ""
  [[ "$output" == 401 ]] || { echo "without a credential: $output" >&2; return 1; }
  run standin_post "Bearer tlcanary-00000000000000000000000000000000"
  [[ "$output" == 401 ]] || { echo "with a wrong credential: $output" >&2; return 1; }
  if standin_names | grep -qx t-iso-intruder; then
    echo "the stand-in created a box for a request without the credential" >&2
    return 1
  fi
}
