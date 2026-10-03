#!/usr/bin/env bash
# Docker lane driver (`make test`; tasks.md T014; research R8, R10). AUTHORITATIVE for SC-1..SC-6.
#
# Steps, in order. Every step runs unless a step it depends on failed (then it is recorded as
# skipped, with the reason), so one run gives a complete report:
#   build   make build: docker compose build --build-arg GIT_SHA=<HEAD> (refuses an empty stamp, H8)
#   up      docker compose --profile standin up -d --build --force-recreate (lore docker-compose Q004:
#           never a stale container; the rebuild is a cache hit after `build`), then Adele and the
#           stand-in must report healthy within 90 s (feature 004)
#   runner  docker build of tests/runner (bats-core + docker CLI, pinned in pins.env)
#   benchimg  make bench-images: the bench's vanilla baseline and driver images (feature 002), stamped
#           with the same GIT_SHA. e2e does NOT wait on it: if it fails, tests/e2e/speedup-bench.bats
#           fails loudly on its own, and feature 001's suite still runs and reports
#   e2e     bats tests/e2e from the runner container, with the Docker socket and the repository
#           (read-only) mounted; the tests drive the agent container from OUTSIDE (cross-stack P005)
#   gounit  go test -cover over adele/ (feature 004) in the pinned GO_IMAGE; NEEDS NETWORK ACCESS to the
#           Go module proxy. Output: tests/out/go-unit.txt
#   unit    pytest tests/unit on the agent image's own interpreter (/opt/timelike/python), in a
#           throwaway container of the built image. pytest is fetched by the pinned uv
#           (PYTEST_VERSION): this step NEEDS NETWORK ACCESS to PyPI
#
# Results land in tests/out/ (git-ignored) so the code instance can read them after the operator
# runs this on a host with Docker:
#   tests/out/run-<UTC>.log   everything this script printed
#   tests/out/latest.log      a copy of the newest run log
#   tests/out/e2e.tap         the bats TAP stream
#   tests/out/report.xml      bats JUnit report
#   tests/out/unit.txt        pytest output (with -rP, so the start-up test's figure is shown)
#   tests/out/startup.json    the in-image start-up p95 from that line (quality-standards C2), or
#                             {"measured": false, "reason": ...} when the test did not print it
#   tests/out/summary.json    {git_sha, started, finished, exit, steps:[{name, rc, status, seconds,
#                             note}], ...} — machine-readable; rc is null for a skipped step
#
# Exit status: 0 only if every step ran and passed.
#
# The agent container is LEFT RUNNING afterwards (for `make demo` and for inspection). `make down`
# stops it.
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo}"
out="${repo}/tests/out"
mkdir -p "${out}"

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
log="${out}/run-${stamp}.log"

RUNNER_IMAGE=timelike-test-runner:local
AGENT_CONTAINER=timelike-agent
ADELE_CONTAINER=timelike-adele
STANDIN_CONTAINER=timelike-adele-standin

declare -a STEP_NAMES=() STEP_RCS=() STEP_STATUS=() STEP_SECS=() STEP_NOTES=()
declare -A RESULT=()

json_escape() {
  local s="$1"
  s="${s//\\/\\\\}"
  s="${s//\"/\\\"}"
  s="${s//$'\n'/ }"
  s="${s//$'\t'/ }"
  printf '%s' "$s"
}

# record NAME RC STATUS SECONDS NOTE
record() {
  STEP_NAMES+=("$1")
  STEP_RCS+=("$2")
  STEP_STATUS+=("$3")
  STEP_SECS+=("$4")
  STEP_NOTES+=("$5")
  RESULT[$1]="$3"
}

# step NAME CMD... — run one step, never abort the script, record rc and duration.
step() {
  local name="$1"
  shift
  echo
  echo "════ step ${name}: $* ════"
  local start end rc
  start="$(date +%s)"
  "$@" && rc=0 || rc=$?
  end="$(date +%s)"
  if [[ ${rc} -eq 0 ]]; then
    record "${name}" "${rc}" pass "$((end - start))" ""
  else
    record "${name}" "${rc}" fail "$((end - start))" "exit ${rc}"
  fi
  echo "════ step ${name}: rc=${rc} ($((end - start)) s) ════"
}

# skip NAME REASON
skip() {
  echo
  echo "════ step $1: SKIPPED — $2 ════"
  record "$1" null skipped 0 "$2"
}

passed() { [[ "${RESULT[$1]:-}" == pass ]]; }

write_summary() {
  local started="$1" finished="$2" exit_rc="$3" i sep=""
  {
    printf '{\n'
    printf '  "lane": "docker",\n'
    printf '  "git_sha": "%s",\n' "$(json_escape "${GIT_SHA:-}")"
    printf '  "started": "%s",\n' "${started}"
    printf '  "finished": "%s",\n' "${finished}"
    printf '  "exit": %s,\n' "${exit_rc}"
    printf '  "log": "tests/out/run-%s.log",\n' "${stamp}"
    printf '  "bats_tap": "tests/out/e2e.tap",\n'
    printf '  "junit_path": "tests/out/report.xml",\n'
    printf '  "unit_output": "tests/out/unit.txt",\n'
    printf '  "startup": "tests/out/startup.json",\n'
    printf '  "go_unit_output": "tests/out/go-unit.txt",\n'
    printf '  "container_left_running": "%s",\n' "${AGENT_CONTAINER} ${ADELE_CONTAINER} ${STANDIN_CONTAINER}"
    printf '  "steps": ['
    for i in "${!STEP_NAMES[@]}"; do
      printf '%s\n    {"name": "%s", "rc": %s, "status": "%s", "seconds": %s, "note": "%s"}' \
        "${sep}" "${STEP_NAMES[$i]}" "${STEP_RCS[$i]}" "${STEP_STATUS[$i]}" "${STEP_SECS[$i]}" \
        "$(json_escape "${STEP_NOTES[$i]}")"
      sep=","
    done
    printf '\n  ]\n}\n'
  } >"${out}/summary.json"
}

# The Docker socket the runner mounts: DOCKER_HOST=unix://..., else the default path. A tcp:// or
# ssh:// DOCKER_HOST is passed through with host networking (TLS material is not forwarded).
# shellcheck disable=SC2329 # invoked through mapfile in run_e2e
docker_endpoint_args() {
  local host="${DOCKER_HOST:-}" sock gid
  if [[ -z "${host}" || "${host}" == unix://* ]]; then
    sock="${host#unix://}"
    sock="${sock:-/var/run/docker.sock}"
    gid="$(stat -c %g "${sock}" 2>/dev/null || stat -f %g "${sock}")"
    printf '%s\n' -v "${sock}:/var/run/docker.sock" --group-add "${gid}"
  else
    printf '%s\n' --network host -e "DOCKER_HOST=${host}"
  fi
}

# shellcheck disable=SC2329 # invoked indirectly, by step
run_e2e() {
  local -a endpoint
  mapfile -t endpoint < <(docker_endpoint_args)
  rm -f "${out}/e2e.tap" "${out}/report.xml"
  # The speedup bench (feature 002) writes here; mounted at the SAME absolute path, because the bench
  # driver bind-mounts it again by that path from the Docker host (research RB7, lore P001/P002).
  local bench_out="${repo}/bench/out/e2e"
  mkdir -p "${bench_out}"
  # Runs as the invoking user (so files in tests/out stay theirs), in the socket's group.
  docker run --rm \
    -u "$(id -u):$(id -g)" \
    "${endpoint[@]}" \
    -v "${repo}:/code:ro" \
    -v "${out}:/out" \
    -v "${bench_out}:${bench_out}" \
    -w /code \
    -e HOME=/tmp \
    -e GIT_SHA \
    -e DEBIAN_IMAGE \
    -e "REPO_HOST=${repo}" \
    -e "BENCH_E2E_OUT=${bench_out}" \
    -e "RUN_TIMEOUT=${RUN_TIMEOUT:-30}" \
    -e "ADELE_CONTAINER=${ADELE_CONTAINER}" \
    -e "STANDIN_CONTAINER=${STANDIN_CONTAINER}" \
    "${RUNNER_IMAGE}" \
    --formatter tap --report-formatter junit --output /out --timing \
    tests/e2e | tee "${out}/e2e.tap"
}

# shellcheck disable=SC2329 # invoked indirectly, by step
# compose_up — the whole stack, the stand-in's profile included (feature 004), recreated from the images
# just built (lore docker-compose Q004), then wait for Adele's and the stand-in's healthchecks. Not
# `--wait`: the one-shot adele-secret exits by design (feature 004 research R3).
#
# The lane starts Adele on its OWN grant file (tests/e2e/fixtures/adele/grants.conf), never the operator's
# adele/grants.conf, and first removes her volumes (ledger, stand-in record, canary): every run starts
# from an empty ledger, so no run's spending or extensions reach the next. Slice 0 holds no real
# resource or credential, so nothing is lost; run `make up` afterwards for the operator's own grants.
compose_up() {
  docker compose --profile standin down --volumes --remove-orphans || return 1
  ADELE_GRANTS="${repo}/tests/e2e/fixtures/adele/grants.conf" \
    docker compose --profile standin up -d --build --force-recreate || return 1
  wait_healthy "${ADELE_CONTAINER}" "${STANDIN_CONTAINER}"
}

# shellcheck disable=SC2329 # invoked from compose_up, itself invoked indirectly by step
# wait_healthy CONTAINER... — each must report healthy within 90 s; on failure, say which and show
# the tail of its log (a malformed grant file names its line there).
wait_healthy() {
  local c state deadline=$((SECONDS + 90))
  for c in "$@"; do
    while :; do
      state="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$c" 2>&1)"
      [[ "${state}" == healthy ]] && break
      if ((SECONDS > deadline)); then
        echo "up: ${c} is not healthy after 90 s (${state}); its log ends:" >&2
        docker logs --tail 5 "$c" >&2 2>&1 || true
        return 1
      fi
      sleep 1
    done
  done
}

# shellcheck disable=SC2329 # invoked indirectly, by step
# run_go_unit — Adele's Go units (feature 004), in the pinned GO_IMAGE with the module read-only.
# NEEDS NETWORK ACCESS to the Go module proxy (GOFLAGS=-mod=readonly: go.sum decides what is fetched).
run_go_unit() {
  docker run --rm \
    -u "$(id -u):$(id -g)" \
    -v "${repo}/adele:/src:ro" \
    -w /src \
    -e HOME=/tmp \
    -e GOCACHE=/tmp/gocache \
    -e GOMODCACHE=/tmp/gomod \
    -e GOFLAGS=-mod=readonly \
    -e GOTOOLCHAIN=local \
    -e CGO_ENABLED=0 \
    "${GO_IMAGE}" \
    go test -count=1 -cover ./... 2>&1 | tee "${out}/go-unit.txt"
  return "${PIPESTATUS[0]}"
}

# shellcheck disable=SC2329 # invoked indirectly, by step
run_unit() {
  local tools="${out}/.tools" cid
  mkdir -p "${tools}"
  # uv from the pinned uv image (pins.env), independent of whether the agent image keeps it.
  cid="$(docker create "${UV_IMAGE}" /uv)" || { echo "unit: cannot create a container from ${UV_IMAGE}" >&2; return 1; }
  docker cp "${cid}:/uv" "${tools}/uv" || { docker rm "${cid}" >/dev/null; echo "unit: cannot copy uv out of ${UV_IMAGE}" >&2; return 1; }
  docker rm "${cid}" >/dev/null || true
  docker run --rm \
    -v "${repo}:/src:ro" \
    -v "${tools}/uv:/usr/local/bin/uv:ro" \
    -w /src \
    -e UV_CACHE_DIR=/tmp/uv-cache \
    -e UV_PYTHON_DOWNLOADS=never \
    -e PYTHONDONTWRITEBYTECODE=1 \
    timelike-agent:local \
    uv run --no-project --python /opt/timelike/python/bin/python3 --with "pytest==${PYTEST_VERSION}" \
    python -m pytest -q -rP -p no:cacheprovider tests/unit 2>&1 | tee "${out}/unit.txt"
  local rc=${PIPESTATUS[0]}
  write_startup "${out}/unit.txt"
  return "${rc}"
}

# shellcheck disable=SC2329 # invoked from run_unit, itself invoked indirectly by step
# write_startup UNIT_TXT — tests/out/startup.json from the start-up test's TIMELIKE_STARTUP line
# (tests/unit/test_agentio_startup.py). A missing line is recorded as not measured, never as a pass.
write_startup() {
  local line re='TIMELIKE_STARTUP p95_ms=([0-9.]+) runs=([0-9]+) python=([^ ]+) interpreter=([^ ]+)'
  line="$(grep -m1 -E 'TIMELIKE_STARTUP ' "$1" 2>/dev/null || true)"
  if [[ "${line}" =~ ${re} ]]; then
    printf '{"measured": true, "p95_ms": %s, "runs": %s, "budget_ms": 100, "python": "%s", "interpreter": "%s", "source": "tests/out/unit.txt"}\n' \
      "${BASH_REMATCH[1]}" "${BASH_REMATCH[2]}" "$(json_escape "${BASH_REMATCH[3]}")" \
      "$(json_escape "${BASH_REMATCH[4]}")" >"${out}/startup.json"
  else
    printf '{"measured": false, "reason": "no TIMELIKE_STARTUP line in tests/out/unit.txt (the start-up test failed, was skipped or did not run)"}\n' \
      >"${out}/startup.json"
  fi
}

# main runs on the left of a pipe (tee), i.e. in a subshell with errexit off: every step's status is
# captured explicitly by step(), and nothing in main may rely on set -e.
main() {
  local started finished exit_rc=0
  started="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "timelike Docker lane (authoritative for SC-1..SC-6) — ${started}"
  echo "log: ${log}"

  if ! docker info >/dev/null 2>&1; then
    echo "error: no Docker daemon reachable (code 1) — run this on a host with Docker, mount the host socket, or set DOCKER_HOST; see .specswarm/features/001-agent-shell-baseline/research.md R10" >&2
    record preflight 1 fail 0 "no Docker daemon reachable"
    finished="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    write_summary "${started}" "${finished}" 1
    return 1
  fi
  record preflight 0 pass 0 "docker info ok"

  set -a
  # shellcheck source=pins.env # (relative to the repository root, where make lint runs shellcheck)
  . "${repo}/pins.env"
  set +a
  GIT_SHA="$(git rev-parse HEAD)"
  export GIT_SHA
  if [[ -z "${GIT_SHA}" ]]; then
    echo "error: git rev-parse HEAD is empty (code 1) — run from a git checkout" >&2
    record stamp 1 fail 0 "empty GIT_SHA"
    finished="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    write_summary "${started}" "${finished}" 1
    return 1
  fi
  echo "GIT_SHA=${GIT_SHA}"

  step build make build

  if passed build; then
    step up compose_up
  else
    skip up "build failed"
  fi

  step runner docker build -t "${RUNNER_IMAGE}" \
    --build-arg BATS_IMAGE --build-arg DOCKER_CLI_IMAGE tests/runner

  if passed build; then
    step benchimg make bench-images
  else
    skip benchimg "build failed"
  fi

  if passed up && passed runner; then
    step e2e run_e2e
  else
    skip e2e "needs up and runner (up=${RESULT[up]:-?}, runner=${RESULT[runner]:-?})"
  fi

  if passed build; then
    step unit run_unit
  else
    skip unit "build failed"
  fi

  # Adele's Go units (feature 004) need no image of ours: only the pinned GO_IMAGE and the module.
  step gounit run_go_unit

  local s
  for s in "${STEP_STATUS[@]}"; do
    [[ "${s}" == pass ]] || exit_rc=1
  done
  finished="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  write_summary "${started}" "${finished}" "${exit_rc}"

  echo
  echo "════ summary ════"
  local i
  for i in "${!STEP_NAMES[@]}"; do
    printf '  %-9s %-8s rc=%-4s %s\n' "${STEP_NAMES[$i]}" "${STEP_STATUS[$i]}" "${STEP_RCS[$i]}" "${STEP_NOTES[$i]}"
  done
  echo "  results: tests/out/summary.json, tests/out/e2e.tap, tests/out/report.xml, tests/out/unit.txt, tests/out/go-unit.txt"
  echo "  the ${AGENT_CONTAINER} container is left running (make demo; make down to stop it)"
  if [[ ${exit_rc} -eq 0 ]]; then
    echo "Docker lane: PASSED"
  else
    echo "Docker lane: FAILED" >&2
  fi
  return "${exit_rc}"
}

set +e
main "$@" 2>&1 | tee "${log}"
rc=${PIPESTATUS[0]}
set -e
cp "${log}" "${out}/latest.log"
exit "${rc}"
