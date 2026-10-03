#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# shellcheck disable=SC2030,SC2031 # bats runs each @test in its own subshell by design
# SC-1 (feature 004) — "The agent image and Adele start together from one compose file, and the agent
# reaches Adele only through its request interface" (send 12-rev2, slice 0; spec FR-1..FR-3, FR-23;
# tasks.md T014).
#
# From the agent, under bash -c and bash -lc: `adele status` answers with the build revision (Adele is
# reached through her interface), while the stand-in, which only Adele may reach, neither resolves by
# name nor accepts a connection on its address (it sits on a network the agent is not on). From the
# outside: the three containers belong to one compose project, Adele is on internal networks only, and
# the agent's networks are its default plus Adele's request network — nothing else.

load helpers

setup_file() {
  stamp_check
  stamp_check_adele
}

# the stand-in's address on its own network, read from outside (the agent cannot read it)
standin_ip() {
  docker inspect --format '{{range $n, $v := .NetworkSettings.Networks}}{{$v.IPAddress}}{{end}}' "$STANDIN_CONTAINER"
}

check_status() {
  run_in "$1" notty 'adele --text status'
  [[ "$status" -eq 0 ]] || { echo "adele status exited $status: $output" >&2; return 1; }
  [[ "${lines[0]}" == "adele: adele [status]" ]] || { echo "header: ${lines[0]}" >&2; return 1; }
  assert_output_has "Adele reachable at http://adele:8480 from the agent container"
  assert_output_has "revision ${GIT_SHA}"
}

check_standin_unreachable() {
  local ip
  ip="$(standin_ip)"
  [[ -n "$ip" ]] || { echo "could not read the stand-in's address" >&2; return 1; }
  # name: getent exits 2 when the name is unknown
  run_in "$1" notty 'getent hosts adele-standin >/dev/null; echo "resolve_rc=$?"'
  assert_output_has "resolve_rc=2"
  # address: a TCP connect from the agent must fail (no route on any of its networks)
  run_in "$1" notty "timeout 5 bash -c 'exec 3<>/dev/tcp/${ip}/8481' 2>/dev/null; echo \"connect_rc=\$?\""
  if [[ "$output" == *"connect_rc=0"* ]]; then
    echo "the agent connected to the stand-in at ${ip}:8481 — it must reach it only through Adele" >&2
    return 1
  fi
}

@test "SC-1 004 the agent reaches Adele through her request interface: adele status names the revision [bash -c]" { check_status c; }
@test "SC-1 004 the agent reaches Adele through her request interface: adele status names the revision [bash -lc]" { check_status lc; }
@test "SC-1 004 the agent cannot reach the stand-in, by name or by address [bash -c]" { check_standin_unreachable c; }
@test "SC-1 004 the agent cannot reach the stand-in, by name or by address [bash -lc]" { check_standin_unreachable lc; }

@test "SC-1 004 the agent image and Adele start together from one compose file: one project" {
  local c project
  for c in "$AGENT_CONTAINER" "$ADELE_CONTAINER" "$STANDIN_CONTAINER"; do
    project="$(docker inspect --format '{{ index .Config.Labels "com.docker.compose.project" }}' "$c")"
    [[ "$project" == timelike ]] || { echo "$c belongs to compose project '$project', not timelike" >&2; return 1; }
  done
}

@test "SC-1 004 Adele is on internal networks only; the agent on its default and Adele's request network" {
  local nets
  nets="$(docker inspect --format '{{range $n, $v := .NetworkSettings.Networks}}{{$n}} {{end}}' "$ADELE_CONTAINER")"
  [[ "$nets" == "timelike_adele-request timelike_adele-standin " ]] || { echo "Adele's networks: $nets" >&2; return 1; }
  for n in timelike_adele-request timelike_adele-standin; do
    [[ "$(docker network inspect --format '{{.Internal}}' "$n")" == true ]] || { echo "$n is not internal" >&2; return 1; }
  done
  nets="$(docker inspect --format '{{range $n, $v := .NetworkSettings.Networks}}{{$n}} {{end}}' "$AGENT_CONTAINER")"
  [[ "$nets" == "timelike_adele-request timelike_default " ]] || { echo "the agent's networks: $nets" >&2; return 1; }
}
