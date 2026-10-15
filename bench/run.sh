#!/usr/bin/env bash
# bench/run.sh — the host side of `make bench` (feature 002; contracts/bench-cli.md, research RB7, RB9).
#
# Runs `timelike-bench run` inside the bench driver container. The driver is the only container that
# holds the Docker socket (H1); the vanilla and timelike task containers it starts get none.
#
#   bench/run.sh [--out DIR] [--task ID ...] [--harness H ...] [--arm A ...] [--dry-run] [--standin]
#                [--turn-cap N] [--spend-cap USD] [--run-limit S]
#
# - GIT_SHA and DEBIAN_IMAGE must be in the environment (the Makefile exports them from git and
#   pins.env). The driver refuses to measure images whose revision label differs from GIT_SHA.
# - Output layout (one rule, the same as `timelike-bench run --out`; fixed at Cycle 1, after the Docker
#   lane at 8ce6173 found run.sh passing DIR only as BENCH_OUT, which the tool treats as a base):
#     --out DIR   the run writes exactly DIR/traces/ and DIR/report.txt; a DIR already holding traces
#                 is refused by the tool, so two runs never mix in one report
#     (none)      the run writes bench/out/<UTC stamp>/, so repeated `make bench` runs never overwrite
# - The directory is resolved HERE, on the host, and mounted into the driver at the same absolute path,
#   so every path a trace or report names exists on the host (lore docker-compose P001, cross-stack
#   P002). A remote DOCKER_HOST would resolve that mount on another machine, so it is refused.
# - No host environment is forwarded: the driver gets exactly the -e list below, so an API key in the
#   operator's shell can never reach it by accident (RB9). A planted key must be passed deliberately.
# - Slice 1 (FR-29): a live run's key is read from the file BENCH_KEY_FILE names, checked HERE on the host
#   (a regular file, not a link, mode 0600, the user's own, outside this repository) and mounted read-only
#   at /run/timelike-bench/key; the driver checks it again there and holds the value in memory, for its relay
#   alone (FOR-MENTOR Item 25, ruled (b)). The value is never read by this script, never on an argv and never
#   in an -e. The bench's configuration (BENCH_MODEL, the caps, the prices, the
#   harness pins from pins.env) is forwarded by name and value, and none of it is key-shaped.
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo}"

DRIVER_IMAGE="${BENCH_DRIVER_IMAGE:-timelike-bench-driver:local}"
SOCKET="${BENCH_DOCKER_SOCKET:-/var/run/docker.sock}"  # the override exists for the host-lane unit only

die() {
  echo "error: $1 (code ${2:-1}) — $3" >&2
  exit "${2:-1}"
}

out=""
live=""
declare -a pass=() tasks_given=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --harness | --arm | --turn-cap | --spend-cap | --run-limit)
      [[ $# -ge 2 ]] || die "$1 needs a value" 2 "bench/run.sh $1 VALUE"
      [[ "$1" == --harness && "$2" != fake ]] && live=1
      pass+=("$1" "$2")
      shift 2
      ;;
    --dry-run | --standin)
      pass+=("$1")
      shift
      ;;
    --out)
      [[ $# -ge 2 ]] || die "--out needs a directory" 2 "bench/run.sh --out DIR"
      out="$2"
      shift 2
      ;;
    --task)
      [[ $# -ge 2 ]] || die "--task needs a task id" 2 "bench/run.sh --task git-inspect"
      pass+=(--task "$2")
      tasks_given+=("$2")
      shift 2
      ;;
    *) die "unknown argument '$1'" 2 "bench/run.sh [--out DIR] [--task ID ...] [--harness H ...] [--dry-run]" ;;
  esac
done

[[ -n "${GIT_SHA:-}" ]] || die "GIT_SHA is empty" 1 "run through make bench, which stamps the checkout's revision"
[[ -n "${DEBIAN_IMAGE:-}" ]] || die "DEBIAN_IMAGE is empty" 1 "run through make bench, which exports pins.env"
case "${DOCKER_HOST:-unix://${SOCKET}}" in
  "unix://${SOCKET}") ;;
  *) die "DOCKER_HOST=${DOCKER_HOST} is not the local socket" 1 "the bench bind-mounts its output directory, which a remote daemon would resolve on its own host; run on the Docker host" ;;
esac
[[ -S "${SOCKET}" ]] || die "no Docker socket at ${SOCKET}" 1 "run on a host with a Docker daemon (feature 001 research R10)"

declare -a pass_out=()
if [[ -n "${out}" ]]; then
  mkdir -p "${out}"
  mount="$(realpath "${out}")"
  pass_out=(--out "${mount}")
else
  mkdir -p bench/out
  mount="$(realpath bench/out)"
fi
sock_gid="$(stat -c %g "${SOCKET}")"

reproduce="make bench${live:+-live}"
if [[ ${#tasks_given[@]} -gt 0 ]]; then
  reproduce+=" TASKS='${tasks_given[*]}'"
fi

# The key file (FR-29): checked here, on the host that owns it; its value is never read by this script.
declare -a key_mount=()
if [[ -n "${BENCH_KEY_FILE:-}" ]]; then
  key="${BENCH_KEY_FILE}"
  [[ "${key}" == /* ]] || die "BENCH_KEY_FILE=${key} is not an absolute path" 4 "name the key file by its absolute path"
  [[ ! -L "${key}" ]] || die "${key} is a symbolic link" 4 "name the file itself"
  [[ -f "${key}" ]] || die "${key} is not a regular file" 4 "BENCH_KEY_FILE names the file holding the key, one line"
  mode="$(stat -c %a "${key}")"
  [[ "${mode}" == 600 ]] || die "${key}: mode is 0${mode}, must be 0600" 4 "chmod 600 ${key}"
  [[ "$(stat -c %u "${key}")" == "$(id -u)" ]] || die "${key} is not owned by $(id -un)" 4 "the key file must be yours"
  case "$(realpath "${key}")/" in
    "${repo}"/*) die "${key} is inside the repository" 4 "keep the key outside code/" ;;
  esac
  key_mount=(-v "$(realpath "${key}"):/run/timelike-bench/key:ro" -e BENCH_KEY_FILE=/run/timelike-bench/key)
fi

# The bench's configuration, by name and value; none of these names is key-shaped (RB9).
declare -a config=()
for name in BENCH_MODEL BENCH_UPSTREAM BENCH_TURN_CAP BENCH_SPEND_CAP_USD BENCH_MODEL_PRICE_IN BENCH_MODEL_PRICE_OUT \
  BENCH_MODEL_PRICE_READ; do
  [[ -z "${!name:-}" ]] || config+=(-e "${name}=${!name}")
done
[[ -z "${OPENCODE_VERSION:-}" ]] || config+=(-e "BENCH_OPENCODE_VERSION=${OPENCODE_VERSION}")
[[ -z "${CODEX_VERSION:-}" ]] || config+=(-e "BENCH_CODEX_VERSION=${CODEX_VERSION}")

exec docker run --rm \
  -u "$(id -u):$(id -g)" --group-add "${sock_gid}" \
  -v "${SOCKET}:/var/run/docker.sock" \
  -v "${mount}:${mount}" \
  -e BENCH_GIT_SHA="${GIT_SHA}" \
  -e BENCH_OUT="${mount}" \
  -e BENCH_BASE_DIGEST="${DEBIAN_IMAGE}" \
  -e BENCH_REPRODUCE="${reproduce}" \
  "${key_mount[@]}" "${config[@]}" \
  "${DRIVER_IMAGE}" run "${pass_out[@]}" "${pass[@]}"
