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
  exec_plain bash -c 'command rm -rf -- "$1" && mkdir -p "$1"' mk "$NP_DIR" || return 1
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
# variables are set ($status, $output, ${lines[@]}).
env_run() {
  local style="$1"
  shift
  RUN_TIMEOUT="$PLUMBING_TIMEOUT" run_in -w "$NP_DIR" "$style" notty "adele $*"
}

# nested_counts NAME — "containers networks volumes" carrying the environment's label, read from the daemon.
nested_counts() {
  local c n v
  c="$(docker ps -aq --filter "label=${NESTED_LABEL}=$1" | wc -l | tr -d ' ')" || return 1
  n="$(docker network ls -q --filter "label=${NESTED_LABEL}=$1" | wc -l | tr -d ' ')" || return 1
  v="$(docker volume ls -q --filter "label=${NESTED_LABEL}=$1" | wc -l | tr -d ' ')" || return 1
  printf '%s %s %s\n' "$c" "$n" "$v"
}

# nested_container NAME SERVICE — the id of the environment's container for SERVICE.
nested_container() {
  docker ps -aq --filter "label=${NESTED_LABEL}=$1" --filter "label=com.docker.compose.service=$2" | head -1
}

# nested_teardown — the cell's own cleanup: `adele env down` (best effort), then the daemon must hold nothing
# labelled with the environment, read back (Item 27 Q5). Removes what is left by the label, and fails if
# anything was left, so a cell that leaks says so. Removes the project directory, as the agent.
nested_teardown() {
  [[ -n "${NP_NAME:-}" ]] || return 0
  RUN_TIMEOUT="$PLUMBING_TIMEOUT" exec_in c notty "adele --json env down ${NP_NAME}" >/dev/null 2>&1 || true
  local left ids
  left="$(nested_counts "$NP_NAME")"
  if [[ "$left" != "0 0 0" ]]; then
    ids="$(docker ps -aq --filter "label=${NESTED_LABEL}=${NP_NAME}")"
    # shellcheck disable=SC2086 # one id per word
    [[ -z "$ids" ]] || docker rm -f -v $ids >/dev/null 2>&1 || true
    docker network ls -q --filter "label=${NESTED_LABEL}=${NP_NAME}" | xargs -r docker network rm >/dev/null 2>&1 || true
    docker volume ls -q --filter "label=${NESTED_LABEL}=${NP_NAME}" | xargs -r docker volume rm >/dev/null 2>&1 || true
  fi
  [[ -n "${NP_DIR:-}" ]] && exec_plain bash -c 'command rm -rf -- "$1"' rm "$NP_DIR" >/dev/null 2>&1 || true
  if [[ "$left" != "0 0 0" ]]; then
    echo "teardown: ${NP_NAME} left ${left} (containers networks volumes) after adele env down" >&2
    return 1
  fi
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
