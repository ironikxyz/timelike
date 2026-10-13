#!/usr/bin/env bats
# Feature 002 slice 1 — SC-5 "The same task catalog runs under two harnesses and the report shows results per
# harness" (tasks.md T050; spec FR-21 to FR-28, FR-44 to FR-47).
#
# The live path end to end, with no key: OpenCode and Codex CLI, from the harness image, run inside the task
# containers of both images, on a per-invocation internal network whose only other member is the bench driver,
# and talk to the model only through the driver's relay. Here the relay's upstream is timelike's model stand-in
# (--standin), which answers with each task's own commands. So this proves the harnesses run, are configured,
# are reached and are parsed; it proves nothing about a model (llm-apis Q001: the mentor's live run is its own
# tier). Two tasks keep it short: git-inspect, and python-missing-module, whose install meets the internal
# network's lack of a route out.
#
# Needs, from tests/run.sh: GIT_SHA, DEBIAN_IMAGE, REPO_HOST and BENCH_E2E_OUT, as speedup-bench.bats does.

DRIVER=timelike-bench-driver:local
TASKS=(git-inspect python-missing-module)
PY=/opt/timelike/python/bin/python3

setup_file() {
  : "${GIT_SHA:?}" "${DEBIAN_IMAGE:?}" "${REPO_HOST:?}" "${BENCH_E2E_OUT:?}"
  # The harness pins, as make passes them (bench/run.sh forwards OPENCODE_VERSION and CODEX_VERSION).
  set -a
  # shellcheck source=/dev/null
  . ./pins.env
  set +a
  export LIVE_OUT="${BENCH_E2E_OUT}/live-${GIT_SHA:0:12}-$$"
  bench/run.sh --out "${LIVE_OUT}" --harness opencode --harness codex --standin \
    --task git-inspect --task python-missing-module \
    >"${BENCH_E2E_OUT}/live.stdout" 2>"${BENCH_E2E_OUT}/live.stderr"
  echo $? >"${BENCH_E2E_OUT}/live.rc"
}

validate() {
  docker run --rm \
    -v "${BENCH_E2E_OUT}:${BENCH_E2E_OUT}:ro" \
    -v "${REPO_HOST}/tests/e2e/fixtures/validate_bench.py:/validate_bench.py:ro" \
    --entrypoint "${PY}" "${DRIVER}" -I /validate_bench.py "$@"
}

@test "SC-5 the same task catalog runs under two harnesses and the report shows results per harness" {
  rc="$(cat "${BENCH_E2E_OUT}/live.rc")"
  [[ "${rc}" -eq 0 ]] || { tail -n 40 "${BENCH_E2E_OUT}/live.stderr"; false; }
  local h
  for h in opencode codex; do
    run validate traces "${LIVE_OUT}" "${GIT_SHA}" "${h}" "${TASKS[@]}"
    echo "${output}"
    [[ "${status}" -eq 0 && "${output}" == "ok: 6 traces valid" ]]
  done
  run validate report "${LIVE_OUT}" standin
  echo "${output}"
  [[ "${status}" -eq 0 ]]
  [[ "$(grep -c '^# Harness: ' "${LIVE_OUT}/report.txt")" -eq 2 ]]
  grep -q '^# Harness: opencode 1.19.0 (reported 1.19.0) ' "${LIVE_OUT}/report.txt"
  grep -q '^# Harness: codex 0.162.1 (reported 0.162.1) ' "${LIVE_OUT}/report.txt"
  for h in opencode codex; do
    run validate verdicts "${LIVE_OUT}" "${h}"
    echo "${output}"
    [[ "${status}" -eq 0 ]]
    run validate adoption "${LIVE_OUT}" "${h}"
    echo "${output}"
    [[ "${status}" -eq 0 ]]
  done
}

@test "SC-5 each harness ran the task's commands itself, and its own transcript was read and kept" {
  local h
  for h in opencode codex; do
    f="${LIVE_OUT}/traces/git-inspect--${h}--told.json"
    grep -q '"command": "git log -n 5 > out/log.txt"' "${f}"
    grep -q '"command": "git diff > out/diff.txt"' "${f}"
    grep -q '"output_streams": "merged"' "${f}"
    grep -q '"kind": "completed"' "${f}"
    [[ -s "${LIVE_OUT}/transcripts/git-inspect--${h}--told.stdout.jsonl" ]]
  done
  [[ -s "${LIVE_OUT}/transcripts/git-inspect--codex--told.rollout.jsonl" ]]
}

@test "SC-5 the live path has no route out but the relay: the guarded install meets network denial under both harnesses" {
  # In the timelike arms pip goes through the package guard, which asks the registry from the task container
  # and finds no route; vanilla's pip refuses earlier (externally managed), so it is checked for the module.
  local h arm f
  for h in opencode codex; do
    for arm in vanilla not-told told; do
      f="${LIVE_OUT}/traces/python-missing-module--${h}--${arm}.json"
      grep -q '"category": "module-not-found"' "${f}"
    done
    for arm in not-told told; do
      grep -q '"category": "network-denial"' "${LIVE_OUT}/traces/python-missing-module--${h}--${arm}.json"
    done
  done
}

@test "SC-5 a stand-in run is labelled as one, records the stand-in's synthetic spend, and leaves nothing behind" {
  head -n 1 "${LIVE_OUT}/report.txt" | grep -q '^STAND-IN MODEL RUN -- '
  grep -q "the model stand-in's usage (synthetic)" "${LIVE_OUT}/report.txt"
  # The per-invocation network and the harness container are removed with the run.
  run docker network ls --filter name=timelike-bench- --format '{{.Name}}'
  [[ -z "${output}" ]]
  run docker ps -a --filter name=timelike-bench-harness- --format '{{.Names}}'
  [[ -z "${output}" ]]
}

@test "SC-5 the relay forwarded every request both harnesses made in a container, and refused none (Item 25 (b))" {
  # The relay holds the key and forwards only chat completions, Responses and generation stats for the pinned
  # model (bridge/feedback/02-20261013-071257-item-25-the-relay-holds-the-key.md, condition 4). Run in the
  # containers here, as on the host when the cycle was built: nothing a harness asked for was refused.
  local f
  for f in "${LIVE_OUT}"/traces/*.json; do
    grep -q '"refused": {}' "${f}" || { echo "${f}"; grep -A3 '"refused"' "${f}"; false; }
    grep -q '"senders": "not told apart: ' "${f}"
  done
}

# The key-file refusals (FR-29) are units on the host lane (tests/unit/test_bench_run_sh.py): here the repository
# is mounted at /code while the bench output keeps its host path, so a key file written there would not count as
# inside the repository, and the run would go on to reach the provider. The lane never does that.
