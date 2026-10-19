# shellcheck shell=bash
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# Helpers for feature 13's nested environments (.specswarm/features/014-nested-dev-env/; research R11).
#
# Each cell's project lives in the lane's own workspace (tests/run.sh gives the runner TIMELIKE_WORKSPACE at the
# same path) and is written BY THE AGENT, as the agent's own project would be. Its environment is named
# tl-<file-hash6>-<cell>, so no two cells or files share one (Item 27 Q5). Bring-up waits are plumbing
# (PLUMBING_TIMEOUT); nothing here asserts a time.
#
# The runner looks at the daemon directly, by timelike's label only (the host's rule), to check what Adele says
# against what is there (cross-stack P004).

NESTED_LABEL=xyz.ironik.timelike.env
NESTED_FIXTURES="${BATS_TEST_DIRNAME}/fixtures/nested"
# 6 hex of the file's own name: per file, so files in a parallel lane never share an environment name.
NESTED_ID="$(printf '%s' "${BATS_TEST_FILENAME##*/}" | sha256sum | cut -c1-6)"

# nested_ready — refuse, loudly, to run a nested cell without the lane's workspace.
nested_ready() {
  [[ -n "${TIMELIKE_WORKSPACE:-}" && -d "${TIMELIKE_WORKSPACE}" ]] ||
    { echo "no TIMELIKE_WORKSPACE in the runner: tests/run.sh's up step sets it (TIMELIKE_WORKSPACES must be set)" >&2; return 1; }
}

# nested_project CELL [FIXTURE] — make the cell's project directory in the workspace, as the agent, copy the
# fixture's compose.yaml there (none when FIXTURE is "-"), and write its .env. Sets NP_DIR and NP_NAME.
nested_project() {
  local cell="$1" fixture="${2:--}"
  nested_ready || return 1
  NP_NAME="tl-${NESTED_ID}-${cell}"
  NP_DIR="${TIMELIKE_WORKSPACE}/${NESTED_ID}-${cell}"
  # Group-writable and setgid, as the workspace is, so the operator (the runner's uid in its group) can work in
  # it where TIMELIKE_HOST_GIT=lifted permits (lane 13s0a, item C: the agent's umask made it 0755).
  exec_plain bash -c 'command rm -rf -- "$1" && mkdir -p "$1" && chmod 2775 "$1"' mk "$NP_DIR" || return 1
  if [[ "$fixture" != - ]]; then
    copy_into_container "${NESTED_FIXTURES}/${fixture}/compose.yaml" "${NP_DIR}/compose.yaml" || return 1
  fi
  local envf
  envf="$(mktemp)"
  printf 'FIXTURE_IMAGE=%s\nAGENT_IMAGE=timelike-agent:local\nPROJECT_DIR=%s\n' "$DEBIAN_IMAGE" "$NP_DIR" >"$envf"
  copy_into_container "$envf" "${NP_DIR}/.env" || { command rm -f "$envf"; return 1; }
  command rm -f "$envf"
}

# nested_compose TEXT — write TEXT as the cell's compose.yaml, through the agent.
nested_compose() {
  local f
  f="$(mktemp)"
  printf '%s\n' "$1" >"$f"
  copy_into_container "$f" "${NP_DIR}/compose.yaml" || { command rm -f "$f"; return 1; }
  command rm -f "$f"
}

# env_run STYLE ARGS — `adele ARGS` in the agent, in the project directory, bounded as plumbing. run_in's
# variables are set ($status, $output, ${lines[@]}). With NP_SESSION set (slice 1's collect cells), the command runs
# under that session id (TIMELIKE_SESSION, agentio.session_id), so the cell can end its own session and no other.
env_run() {
  local style="$1"
  shift
  local -a envs=()
  [[ -z "${NP_SESSION:-}" ]] || envs=(-e "TIMELIKE_SESSION=${NP_SESSION}")
  RUN_TIMEOUT="$PLUMBING_TIMEOUT" run_in ${envs[@]+"${envs[@]}"} -w "$NP_DIR" "$style" notty "adele $*"
}

# nested_session CELL — a session id of the cell's own (agentio's ^[A-Za-z0-9._-]{1,64}$), set as NP_SESSION. Ending
# it ends this cell's session only: every other cell runs under its own, or under "default", which no cell ends.
nested_session() {
  NP_SESSION="e2e-${NESTED_ID}-$1-${RANDOM}"
}

# nested_write REL TEXT — write TEXT as the project's file REL (its directories made), through the agent.
nested_write() {
  local f
  f="$(mktemp)"
  printf '%s\n' "$2" >"$f"
  exec_plain mkdir -p "$(dirname "${NP_DIR}/$1")" || { command rm -f "$f"; return 1; }
  copy_into_container "$f" "${NP_DIR}/$1" || { command rm -f "$f"; return 1; }
  command rm -f "$f"
}

# nested_files FIXTURE — copy every file of the fixture (any depth, dot-directories included) into the project,
# through the agent, with @DEBIAN_IMAGE@ and @AGENT_IMAGE@ replaced by the lane's references: a devcontainer.json
# has no .env, so a reference it needs is written in (slice 1, 014 plan R22). Nothing else is substituted.
nested_files() {
  local src="${NESTED_FIXTURES}/$1" f rel tmp
  [[ -d "$src" ]] || { echo "nested_files: no fixture $1" >&2; return 1; }
  while IFS= read -r f; do
    rel="${f#"${src}/"}"
    tmp="$(mktemp)"
    sed -e "s|@DEBIAN_IMAGE@|${DEBIAN_IMAGE}|g" -e 's|@AGENT_IMAGE@|timelike-agent:local|g' "$f" >"$tmp"
    exec_plain mkdir -p "$(dirname "${NP_DIR}/${rel}")" || { command rm -f "$tmp"; return 1; }
    copy_into_container "$tmp" "${NP_DIR}/${rel}" || { command rm -f "$tmp"; return 1; }
    command rm -f "$tmp"
  done < <(find "$src" -type f | sort)
}

# nested_counts NAME — "containers networks volumes" carrying the environment's label, read from the daemon.
nested_counts() {
  local c n v
  c="$(docker ps -aq --filter "label=${NESTED_LABEL}=$1" | wc -l | tr -d ' ')" || return 1
  n="$(docker network ls -q --filter "label=${NESTED_LABEL}=$1" | wc -l | tr -d ' ')" || return 1
  v="$(docker volume ls -q --filter "label=${NESTED_LABEL}=$1" | wc -l | tr -d ' ')" || return 1
  printf '%s %s %s\n' "$c" "$n" "$v"
}

# nested_image_count NAME — images carrying the environment's label (slice 1: what its builds made), read from the
# daemon. Separate from nested_counts, whose three numbers slice 0's cells read.
nested_image_count() {
  local ids
  ids="$(docker image ls -q --filter "label=${NESTED_LABEL}=$1")" || return 1
  printf '%s\n' "$ids" | sed '/^$/d' | sort -u | wc -l | tr -d ' '
}

# nested_objects NAME — one line per container, network, volume and image carrying the environment's label, read
# from the daemon by the runner: kind<TAB>id<TAB>session<TAB>grant<TAB>requester (slice 1, R21: the four kinds).
nested_objects() {
  local id got t=$'\t' p=xyz.ironik.timelike
  local lc="{{index .Config.Labels \"${p}.session\"}}${t}{{index .Config.Labels \"${p}.grant\"}}${t}{{index .Config.Labels \"${p}.requester\"}}"
  local ll="{{index .Labels \"${p}.session\"}}${t}{{index .Labels \"${p}.grant\"}}${t}{{index .Labels \"${p}.requester\"}}"
  for id in $(docker ps -aq --no-trunc --filter "label=${NESTED_LABEL}=$1"); do
    got="$(docker inspect --format "$lc" "$id")" || return 1
    printf 'container\t%s\t%s\n' "$id" "$got"
  done
  for id in $(docker network ls -q --no-trunc --filter "label=${NESTED_LABEL}=$1"); do
    got="$(docker network inspect --format "$ll" "$id")" || return 1
    printf 'network\t%s\t%s\n' "$id" "$got"
  done
  for id in $(docker volume ls -q --filter "label=${NESTED_LABEL}=$1"); do
    got="$(docker volume inspect --format "$ll" "$id")" || return 1
    printf 'volume\t%s\t%s\n' "$id" "$got"
  done
  for id in $(docker image ls -q --no-trunc --filter "label=${NESTED_LABEL}=$1" | sort -u); do
    got="$(docker image inspect --format "$lc" "$id")" || return 1
    printf 'image\t%s\t%s\n' "$id" "$got"
  done
}

# nested_container NAME SERVICE — the id of the environment's container for SERVICE.
nested_container() {
  docker ps -aq --filter "label=${NESTED_LABEL}=$1" --filter "label=com.docker.compose.service=$2" | head -1
}

# nested_teardown — the cell's own cleanup: `adele env down` (best effort), then the daemon must hold nothing
# labelled with the environment, read back (Item 27 Q5). Removes what is left by the label, and fails if
# anything was left, so a cell that leaks says so. Removes the project directory, as the agent.
#
# Slice 1: images labelled with the environment (its builds) count too. They are removed after the containers, and
# any left is a failure, said with the other three.
nested_teardown() {
  [[ -n "${NP_NAME:-}" ]] || return 0
  RUN_TIMEOUT="$PLUMBING_TIMEOUT" exec_in c notty "adele --json env down ${NP_NAME}" >/dev/null 2>&1 || true
  local left images ids
  left="$(nested_counts "$NP_NAME")"
  images="$(nested_image_count "$NP_NAME")"
  if [[ "$left" != "0 0 0" || "$images" != 0 ]]; then
    ids="$(docker ps -aq --filter "label=${NESTED_LABEL}=${NP_NAME}")"
    # shellcheck disable=SC2086 # one id per word
    [[ -z "$ids" ]] || docker rm -f -v $ids >/dev/null 2>&1 || true
    docker network ls -q --filter "label=${NESTED_LABEL}=${NP_NAME}" | xargs -r docker network rm >/dev/null 2>&1 || true
    docker volume ls -q --filter "label=${NESTED_LABEL}=${NP_NAME}" | xargs -r docker volume rm >/dev/null 2>&1 || true
    docker image ls -q --filter "label=${NESTED_LABEL}=${NP_NAME}" | sort -u | xargs -r docker image rm -f >/dev/null 2>&1 || true
  fi
  [[ -n "${NP_DIR:-}" ]] && exec_plain bash -c 'command rm -rf -- "$1"' rm "$NP_DIR" >/dev/null 2>&1 || true
  if [[ "$left" != "0 0 0" || "$images" != 0 ]]; then
    echo "teardown: ${NP_NAME} left ${left} (containers networks volumes) and ${images} images after adele env down" >&2
    return 1
  fi
}

# nested_gone NAME — the daemon holds nothing labelled with the environment: no container, network, volume or image.
nested_gone() {
  local c i
  c="$(nested_counts "$1")" || return 1
  i="$(nested_image_count "$1")" || return 1
  [[ "$c" == "0 0 0" && "$i" == 0 ]] || { echo "the daemon still holds, labelled $1: ${c} (containers networks volumes), ${i} images" >&2; return 1; }
}

# ledger_rows_for NAME — Adele's ledger rows for the environment, one per line: outcome<TAB>action<TAB>limit<TAB>extend<TAB>cause
ledger_rows_for() {
  local json
  json="$(adeled ledger --json)" || return 1
  printf '%s' "$json" | pyq "
import json, sys
for r in json.load(sys.stdin):
    if r.get('resource') == '$1':
        print('\t'.join([r['outcome'], r.get('action') or '', r.get('limit_name') or '', r.get('extend') or '',
                         (r.get('cause') or '').replace('\t', ' ')]))"
}

# ── Slice 1: a second agent container, and collection (014 plan R18, R19, R22) ──────────────────────────────────
# nested_throwaway_agent NAME SESSION — start a throwaway agent container from the running agent's image (helpers.bash
# start_throwaway: its privilege boundary, its label, `sleep infinity`), labelled as the agent is launched
# (xyz.ironik.timelike.host-git, the label Adele finds requesters by), on the agent's own adele-request network and on
# timelike-nested, with the workspace at its own path, the agent's supplementary groups, and SESSION as its session
# id. Sets NP_TW (its name) and NP_TW_ID (its full id, which Adele must read back as the requester).
nested_throwaway_agent() {
  local name="$1" session="$2" nets net request="" nested="" gid
  nets="$(docker inspect --format '{{range $k, $v := .NetworkSettings.Networks}}{{$k}} {{end}}' "$AGENT_CONTAINER")" || return 1
  for net in $nets; do
    [[ "$net" != *adele-request ]] || request="$net"
    [[ "$net" != timelike-nested ]] || nested="$net"
  done
  [[ -n "$request" && -n "$nested" ]] ||
    { echo "nested_throwaway_agent: the agent's networks are '${nets}': no adele-request or timelike-nested" >&2; return 1; }
  local -a groups=()
  for gid in $(docker inspect --format '{{range .HostConfig.GroupAdd}}{{.}} {{end}}' "$AGENT_CONTAINER"); do
    groups+=(--group-add "$gid")
  done
  NP_TW="$name"
  start_throwaway "$name" --label xyz.ironik.timelike.host-git=enforced --network "$request" \
    -v "${TIMELIKE_WORKSPACE}:${TIMELIKE_WORKSPACE}" -e "TIMELIKE_WORKSPACE=${TIMELIKE_WORKSPACE}" \
    -e TIMELIKE_HOST_GIT=enforced -e TIMELIKE_ADELE_URL=http://adele:8480 -e "TIMELIKE_SESSION=${session}" \
    -e TIMELIKE_SNAPSHOT_INTERVAL=off ${groups[@]+"${groups[@]}"} || return 1
  timeout "$PLUMBING_TIMEOUT" docker network connect "$nested" "$name" </dev/null ||
    { echo "nested_throwaway_agent: cannot join ${name} to ${nested}" >&2; return 1; }
  # shellcheck disable=SC2034 # read by the .bats file that starts it
  NP_TW_ID="$(docker inspect --format '{{.Id}}' "$name")" || return 1
}

# tw_run CMD — CMD under bash -c in the throwaway agent, in the project directory, bounded as plumbing. bats' run
# variables are set.
tw_run() {
  run timeout "$PLUMBING_TIMEOUT" docker exec -w "$NP_DIR" "$NP_TW" bash -c "$1" </dev/null
}

# nested_collected NAME CAUSE — after an `adele --text env collect` (its $output): NAME's environment was collected
# for CAUSE (the start of the cause Adele gives), recorded in the ledger as a reaped row with that cause, and the
# daemon holds nothing labelled NAME, read back (cross-stack P004). Sets NP_COLLECTED_BY.
#
# Adele's reaper runs the same pass on its tick (5 s; spec FR-29, broker/collect.go Collect), so the pass that removed
# the environment may be the reaper's, run between the cell's last step and its collect: a pass that finds the row
# still live waits on Envs' lock and names it too, and one that comes after finds it gone and does not. Which one it
# was is said on fd 3; the ledger row, the cause and the daemon are asserted either way.
nested_collected() {
  local name="$1" cause="$2" rows
  # shellcheck disable=SC2154 # $output is the last run's, set by bats
  if printf '%s\n' "$output" | grep -qF "collected ${name}: ${cause}"; then
    # shellcheck disable=SC2034 # read by the .bats file, which says it on fd 3
    NP_COLLECTED_BY="this collect"
  else
    # shellcheck disable=SC2034 # read by the .bats file, which says it on fd 3
    NP_COLLECTED_BY="Adele's reaper, the same pass on its tick, before this collect"
  fi
  rows="$(ledger_rows_for "$name")" || return 1
  printf '%s\n' "$rows" | grep -F $'reaped\tdelete\t' | grep -F "collected: ${cause}" |
    grep -qF "0 left, read back from the daemon" ||
    { printf 'no reaped row for %s with the cause %s; its ledger rows:\n%s\ncollect said:\n%s\n' "$name" "$cause" "$rows" "$output" >&2; return 1; }
  nested_gone "$name"
}

# ── Slice 2: snapshots of an environment's volumes (014 plan R23-R33; data-model § Slice 2) ─────────────────────
# A snapshot is one volume on the daemon, `<env>-snap-<hex>` for the snapshot `s-<hex>`, labelled with the
# environment (so down, collection and the lane's sweep remove it with the rest), the snapshot's id, the volume it
# was taken from, and the session, grant and requester. Read here by the runner, by those labels only.
NESTED_SNAPSHOT_LABEL=xyz.ironik.timelike.snapshot

# nested_snapshot_volumes NAME — the environment's snapshot volumes on the daemon, one name per line, sorted.
nested_snapshot_volumes() {
  local v
  v="$(docker volume ls -q --filter "label=${NESTED_LABEL}=$1" --filter "label=${NESTED_SNAPSHOT_LABEL}")" || return 1
  printf '%s\n' "$v" | sed '/^$/d' | sort
}

# nested_snapshot_count NAME — how many snapshot volumes the environment has on the daemon.
nested_snapshot_count() {
  local v
  v="$(nested_snapshot_volumes "$1")" || return 1
  printf '%s\n' "$v" | sed '/^$/d' | wc -l | tr -d ' '
}

# nested_volume NAME KEY — the daemon's name for the environment's compose volume KEY (never a snapshot volume).
nested_volume() {
  local v
  for v in $(docker volume ls -q --filter "label=${NESTED_LABEL}=$1" --filter "label=com.docker.compose.volume=$2"); do
    [[ -n "$(docker volume inspect --format "{{index .Labels \"${NESTED_SNAPSHOT_LABEL}\"}}" "$v")" ]] || { printf '%s\n' "$v"; return 0; }
  done
  echo "nested_volume: no volume ${2} labelled ${1} on the daemon" >&2
  return 1
}

# nested_snapshot_labels VOLUME — the snapshot volume's labels, tab-separated:
# env<TAB>snapshot<TAB>snapshot-of<TAB>session<TAB>grant<TAB>requester<TAB>created
nested_snapshot_labels() {
  local p=xyz.ironik.timelike t=$'\t' k f=""
  for k in env snapshot snapshot-of session grant requester created; do
    f+="{{index .Labels \"${p}.${k}\"}}${t}"
  done
  docker volume inspect --format "${f%"${t}"}" "$1"
}

# nested_state CONTAINER — "STATUS PAUSED STARTED_AT" from the daemon: running false 2026-…
nested_state() {
  docker inspect --format '{{.State.Status}} {{.State.Paused}} {{.State.StartedAt}}' "$1"
}

# nested_running_unpaused CONTAINER — the container is running and not paused, read from the daemon.
nested_running_unpaused() {
  local s
  s="$(nested_state "$1")" || return 1
  [[ "$s" == "running false "* ]] || { echo "container $1 is not running unpaused: ${s}" >&2; return 1; }
}

# nested_volume_throwaway VOLUME USER CMD — CMD under sh -c in a throwaway container on the runner with VOLUME at /v:
# the lane's Debian image, no network, every capability dropped, as USER. A cell uses it to change what only the
# daemon holds (a snapshot's own content), which the agent cannot reach. It carries the throwaway label
# (helpers.bash THROWAWAY_LABEL), so tests/run.sh's sweep removes one a killed run left behind; it is --rm, and
# removed by name afterwards whatever happened. It never mounts a volume that carries no timelike label.
nested_volume_throwaway() {
  local vol="$1" user="$2" cmd="$3" name rc
  [[ -n "$(docker volume inspect --format "{{index .Labels \"${NESTED_LABEL}\"}}" "$vol")" ]] ||
    { echo "nested_volume_throwaway: ${vol} carries no ${NESTED_LABEL} label; the runner touches only timelike's" >&2; return 1; }
  name="tl-e2e-vol-${NESTED_ID}-$$-${RANDOM}"
  timeout "$PLUMBING_TIMEOUT" docker run --rm --name "$name" --label "${THROWAWAY_LABEL}=1" --network none \
    --cap-drop ALL --security-opt no-new-privileges:true --user "$user" -v "${vol}:/v" "$DEBIAN_IMAGE" \
    sh -c "$cmd" </dev/null && rc=0 || rc=$?
  remove_throwaway "$name"
  return "$rc"
}

# nested_copy_helpers NAME — the ids of the environment's running volume helpers that are copying (014 plan R25:
# named tl-sandbox-<env>-vol-<hex>, labelled …sandbox=volume, running `adeled volume copy`), read from the daemon.
# The measure and digest helpers carry the same name and label, so the command tells the copy apart.
nested_copy_helpers() {
  local id
  for id in $(docker ps -q --filter label=xyz.ironik.timelike.sandbox=volume --filter "name=tl-sandbox-$1-vol-" 2>/dev/null); do
    docker inspect --format '{{json .Config.Entrypoint}} {{json .Config.Cmd}}' "$id" 2>/dev/null | grep -qF '"copy"' &&
      printf '%s\n' "$id"
  done
  return 0
}

# nested_paused CONTAINER — the daemon says the container is paused.
nested_paused() {
  [[ "$(docker inspect --format '{{.State.Paused}}' "$1" 2>/dev/null)" == true ]]
}
