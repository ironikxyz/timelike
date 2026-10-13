#!/usr/bin/env bats
# Feature 002 (speedup bench) — slice 0's SC-1 and SC-2, and slice 1's SC-4, SC-6 and SC-7 on the fake agent's
# run, in the Docker lane (tasks.md T014, T049). SC-5 (two harnesses) is
# the-same-task-catalog-runs-under-two-harnesses-and-the-report-shows-results-per-harness.bats; SC-7's probe in
# both images is failed-commands-are-grouped-into-categories-….bats.
#
# SC-1 "One command runs a task in both a vanilla image and the timelike image and writes a per-run
#       trace with turns, tool calls, non-zero exits, hangs and wall-clock time."
# SC-2 "The bench runs end to end in CI against a deterministic fake agent without any API key."
#
# The one command is the real one: bench/run.sh, which `make bench` calls, run from this runner with
# the host's socket. It starts the bench driver, which starts one task container per run; nothing
# here reaches inside a container under test (cross-stack P005).
#
# Artifacts are judged, never the exit message (H3, cross-stack P004), by
# tests/e2e/fixtures/validate_bench.py — an independent validator sharing no code with the bench's own
# writer — run on the driver image's interpreter, because this runner has no Python.
#
# Each refusal is shown to be able to fire: a planted key and a mismatched stamp must both stop a run
# before any trace exists.
#
# Needs, from tests/run.sh: GIT_SHA, DEBIAN_IMAGE, REPO_HOST (the repository's path on the Docker
# host, for -v sources) and BENCH_E2E_OUT (a host directory mounted here at the same absolute path).

DRIVER=timelike-bench-driver:local
TASKS=(git-inspect git-rebase-continue git-commit-hook-hangs git-commit-hook-rejects python-missing-module)
PY=/opt/timelike/python/bin/python3

setup_file() {
  : "${GIT_SHA:?}" "${DEBIAN_IMAGE:?}" "${REPO_HOST:?}" "${BENCH_E2E_OUT:?}"
  export RUN_OUT="${BENCH_E2E_OUT}/run-${GIT_SHA:0:12}-$$"
  # The one command, over the whole catalog. Its output and status are kept for the tests below.
  bench/run.sh --out "${RUN_OUT}" >"${BENCH_E2E_OUT}/run.stdout" 2>"${BENCH_E2E_OUT}/run.stderr"
  echo $? >"${BENCH_E2E_OUT}/run.rc"
}

# validate ARGS... — the independent validator, on the driver's interpreter, reading the run read-only.
validate() {
  docker run --rm \
    -v "${BENCH_E2E_OUT}:${BENCH_E2E_OUT}:ro" \
    -v "${REPO_HOST}/tests/e2e/fixtures/validate_bench.py:/validate_bench.py:ro" \
    --entrypoint "${PY}" "${DRIVER}" -I /validate_bench.py "$@"
}

# driver_run OUT [-e VAR=VALUE ...] -- ARGS... — the driver as bench/run.sh starts it, plus extra -e
# flags; used only to plant what run.sh deliberately never forwards.
driver_run() {
  local out="$1" gid
  shift
  local -a extra=()
  while [[ $# -gt 0 && "$1" != "--" ]]; do extra+=("$1"); shift; done
  shift
  gid="$(stat -c %g /var/run/docker.sock)"
  mkdir -p "${out}"
  docker run --rm -u "$(id -u):$(id -g)" --group-add "${gid}" \
    -v /var/run/docker.sock:/var/run/docker.sock -v "${out}:${out}" \
    -e BENCH_GIT_SHA="${GIT_SHA}" -e BENCH_BASE_DIGEST="${DEBIAN_IMAGE}" -e BENCH_OUT="${out}" \
    "${extra[@]}" "${DRIVER}" "$@"
}

@test "SC-1 one command runs a task in both a vanilla image and the timelike image and writes a per-run trace" {
  rc="$(cat "${BENCH_E2E_OUT}/run.rc")"
  [[ "${rc}" -eq 0 ]] || { cat "${BENCH_E2E_OUT}/run.stderr"; false; }
  run validate traces "${RUN_OUT}" "${GIT_SHA}" fake "${TASKS[@]}"
  echo "${output}"
  [[ "${status}" -eq 0 ]]
  [[ "${output}" == "ok: $((3 * ${#TASKS[@]})) traces valid" ]]
}

@test "SC-1 a hanging call ends within its limit and is recorded" {
  run validate hang "${RUN_OUT}" git-commit-hook-hangs
  echo "${output}"
  [[ "${status}" -eq 0 ]]
}

@test "SC-1 a stamp that does not match the checkout refuses the run, naming both revisions" {
  local out="${BENCH_E2E_OUT}/stale-$$" wrong
  wrong="$(printf '%s' "${GIT_SHA}" | tr '0-9a-f' 'f0-9a-e')"
  run driver_run "${out}" -e BENCH_GIT_SHA="${wrong}" -- run --out "${out}" --task git-inspect
  echo "${output}"
  [[ "${status}" -eq 1 ]]
  [[ "${output}" == *"${wrong}"* && "${output}" == *"${GIT_SHA}"* ]]
  [[ ! -e "${out}/traces" ]]
}

@test "SC-2 the bench runs end to end in CI against a deterministic fake agent without any API key" {
  rc="$(cat "${BENCH_E2E_OUT}/run.rc")"
  [[ "${rc}" -eq 0 ]]
  # The driver's own output names the run as a demo of the bench pipeline, not a test of timelike (its
  # header scope; JSON here, because stdout is not a terminal). The report's full first line, and each
  # task's explanation, are checked by the validator below (send …-080659).
  grep -qF "FAKE-AGENT BENCH PIPELINE DEMO RUN -- not a test of timelike" "${BENCH_E2E_OUT}/run.stdout"
  run validate report "${RUN_OUT}" fake
  echo "${output}"
  [[ "${status}" -eq 0 ]]
  # No key-shaped variable in the driver's environment, nor baked into either image under test.
  docker run --rm --entrypoint /usr/bin/env "${DRIVER}" >"${BENCH_E2E_OUT}/driver.env"
  for img in timelike-agent:local timelike-vanilla:local; do
    docker image inspect --format '{{range .Config.Env}}{{println .}}{{end}}' "${img}"
  done >"${BENCH_E2E_OUT}/images.env"
  run validate env "${BENCH_E2E_OUT}/driver.env"
  echo "${output}"
  [[ "${status}" -eq 0 ]]
  run validate env "${BENCH_E2E_OUT}/images.env"
  echo "${output}"
  [[ "${status}" -eq 0 ]]
}

@test "SC-2 a planted API key refuses the run before any trace is written" {
  local out="${BENCH_E2E_OUT}/key-$$"
  run driver_run "${out}" -e ANTHROPIC_API_KEY=planted-by-the-test -- run --out "${out}" --task git-inspect
  echo "${output}"
  [[ "${status}" -eq 4 ]]
  [[ "${output}" == *ANTHROPIC_API_KEY* ]]
  [[ "${output}" != *planted-by-the-test* ]]
  [[ ! -e "${out}/traces" ]]
}

@test "SC-2 a set BENCH_KEY_FILE refuses a fake-agent run before any trace is written" {
  local out="${BENCH_E2E_OUT}/keyfile-$$"
  run driver_run "${out}" -e BENCH_KEY_FILE=/nonexistent -- run --out "${out}" --task git-inspect
  echo "${output}"
  [[ "${status}" -eq 4 ]]
  [[ "${output}" == *"BENCH_KEY_FILE is set for a fake-agent run"* ]]
  [[ ! -e "${out}/traces" ]]
}

@test "SC-4 each run is labelled told or not-told, and the report counts timelike tool invocations per arm" {
  # Every task ran in three arms, each trace labelled (the validator checks the arm, the environment and the
  # placement rule per trace above); the told runs carry the placement 007's announce made in the container.
  local task
  for task in "${TASKS[@]}"; do
    grep -q '"arm": "not-told"' "${RUN_OUT}/traces/${task}--fake--not-told.json"
    grep -q '"arm": "told"' "${RUN_OUT}/traces/${task}--fake--told.json"
    grep -q '"placement": ".*codex: placed.*opencode: placed' "${RUN_OUT}/traces/${task}--fake--told.json"
  done
  grep -qF "## Adoption: timelike tool calls per arm" "${RUN_OUT}/report.txt"
  # The adoption table's counts, recounted by the validator from the traces' own commands.
  run validate adoption "${RUN_OUT}" fake
  echo "${output}"
  [[ "${status}" -eq 0 ]]
  # The python task's install goes through 013's shim in both timelike arms: counted as through timelike.
  grep -q '"through_timelike_calls": 1' "${RUN_OUT}/traces/python-missing-module--fake--told.json"
  grep -q '"through_timelike_calls": 0' "${RUN_OUT}/traces/python-missing-module--fake--vanilla.json"
}

@test "SC-6 two arms that end the same way in the same turns are ranked by hangs, then failed commands, and the sentence states only table counts" {
  # The validator recomputes revision 8's order from the traces, written again in its own code, and checks
  # each verdict line, and that every count a sentence quotes is a cell of its table.
  run validate verdicts "${RUN_OUT}" fake
  echo "${output}"
  [[ "${status}" -eq 0 ]]
  run grep -qF "failed or hung" "${RUN_OUT}/report.txt"
  [[ "${status}" -ne 0 ]]
}

@test "SC-7 the python task's failed commands are categorised in both images: module not found, then network denial" {
  local arm f
  for arm in vanilla not-told told; do
    f="${RUN_OUT}/traces/python-missing-module--fake--${arm}.json"
    grep -q '"category": "module-not-found"' "${f}"
    grep -q '"category": "network-denial"' "${f}"
  done
}
