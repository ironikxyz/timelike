#!/usr/bin/env bash
# bench/run.sh — the host side of `make bench` (feature 002; contracts/bench-cli.md, research RB7, RB9).
#
# Runs `timelike-bench run` inside the bench driver container. The driver is the only container that
# holds the Docker socket (H1); the vanilla and timelike task containers it starts get none.
#
#   bench/run.sh [--out DIR] [--task ID ...]
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
declare -a pass=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --out)
      [[ $# -ge 2 ]] || die "--out needs a directory" 2 "bench/run.sh --out DIR"
      out="$2"
      shift 2
      ;;
    --task)
      [[ $# -ge 2 ]] || die "--task needs a task id" 2 "bench/run.sh --task git-inspect"
      pass+=(--task "$2")
      shift 2
      ;;
    *) die "unknown argument '$1'" 2 "bench/run.sh [--out DIR] [--task ID ...]" ;;
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

reproduce="make bench"
if [[ ${#pass[@]} -gt 0 ]]; then
  tasks=""
  for ((i = 1; i < ${#pass[@]}; i += 2)); do tasks+="${tasks:+ }${pass[i]}"; done
  reproduce="make bench TASKS='${tasks}'"
fi

exec docker run --rm \
  -u "$(id -u):$(id -g)" --group-add "${sock_gid}" \
  -v "${SOCKET}:/var/run/docker.sock" \
  -v "${mount}:${mount}" \
  -e BENCH_GIT_SHA="${GIT_SHA}" \
  -e BENCH_OUT="${mount}" \
  -e BENCH_BASE_DIGEST="${DEBIAN_IMAGE}" \
  -e BENCH_REPRODUCE="${reproduce}" \
  "${DRIVER_IMAGE}" run "${pass_out[@]}" "${pass[@]}"
