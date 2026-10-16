#!/usr/bin/env bats
# Feature 002 slice 1 — SC-7 "Failed commands are grouped into categories including command not found, module
# not found, timeout, memory kill and network denial" (tasks.md T051; spec FR-40 to FR-43).
#
# `timelike-bench categories --probe` starts one task container of each image (no network, a 64 MiB memory
# limit) and runs one real failing command per category in it, through the bench's own wrapper: the commands
# fail for real, in both images, and the categoriser reads what they printed (cross-stack P005). The fake
# agent's python task produces module not found and network denial again inside a bench run
# (speedup-bench.bats).
#
# Needs, from tests/run.sh: BENCH_E2E_OUT and the bench images (make bench-images).

DRIVER=timelike-bench-driver:local

# The parallel lane's file lock (maint-lane-speed); this file loads no helpers.bash, which would source it.
load lane

probe() {
  local gid
  gid="$(stat -c %g /var/run/docker.sock)"
  docker run --rm -u "$(id -u):$(id -g)" --group-add "${gid}" \
    -v /var/run/docker.sock:/var/run/docker.sock \
    "${DRIVER}" categories --probe --text --limit 0
}

setup_file() {
  : "${BENCH_E2E_OUT:?}"
  probe >"${BENCH_E2E_OUT}/probe.out" 2>"${BENCH_E2E_OUT}/probe.err"
  echo $? >"${BENCH_E2E_OUT}/probe.rc"
}

@test "SC-7 failed commands are grouped into categories including command not found, module not found, timeout, memory kill and network denial" {
  cat "${BENCH_E2E_OUT}/probe.out" "${BENCH_E2E_OUT}/probe.err"
  [[ "$(cat "${BENCH_E2E_OUT}/probe.rc")" -eq 0 ]]
  local img cat
  for img in vanilla timelike; do
    for cat in command-not-found module-not-found timeout memory-kill network-denial other; do
      grep -q "^${img} · ${cat} · ${cat} · " "${BENCH_E2E_OUT}/probe.out"
    done
  done
  run grep -c MISMATCH "${BENCH_E2E_OUT}/probe.out"
  [[ "${output}" -eq 0 ]]
}

@test "SC-7 a memory kill is named only with the kernel's evidence" {
  grep -q '^vanilla · memory-kill · memory-kill · .* · exit 137, oom_kill rose$' "${BENCH_E2E_OUT}/probe.out"
  grep -q '^timelike · memory-kill · memory-kill · .* · exit 137, oom_kill rose$' "${BENCH_E2E_OUT}/probe.out"
}
