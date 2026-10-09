#!/usr/bin/env bash
# Host lane driver (`make test-host`; research R10). ADVISORY: evidence about the Python units and the
# env-layer files, never about the image. The Docker lane (tests/run.sh) is authoritative.
# Runs every step even if an earlier one fails; exits non-zero if any fails. An empty unit suite
# (pytest exit 5, "no tests collected") counts as a failure: nothing ran, so nothing passed.
set -euo pipefail

echo "host lane (advisory): proves agentio/conform units, the env-layer files and the shell-env hook's logic, not the image"

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${repo}"

rc=0

echo "## pytest tests/unit (${PYTHON:-python3})"
if "${PYTHON:-python3}" -m pytest -q tests/unit; then
  :
else
  status=$?
  if [[ ${status} -eq 5 ]]; then
    echo "host lane: pytest collected no tests in tests/unit (exit 5) — counted as a failure" >&2
  fi
  rc=1
fi

echo "## tests/host/test_env_layer.sh"
if ! tests/host/test_env_layer.sh </dev/null; then
  rc=1
fi

# The container-derived hook's logic (slice 1, T052: SC-8, SC-9) against fake cgroup/status files.
echo "## tests/host/test_shell_env_hook.sh"
if ! tests/host/test_shell_env_hook.sh </dev/null; then
  rc=1
fi

# The command-not-found handler's logic (feature 007 slice 1, SC-5) against bash itself, per style.
echo "## tests/host/test_command_not_found.sh"
if ! tests/host/test_command_not_found.sh </dev/null; then
  rc=1
fi

if [[ ${rc} -ne 0 ]]; then
  echo "host lane (advisory): FAILED" >&2
else
  echo "host lane (advisory): passed — files, units and hook logic only, not the image"
fi
exit "${rc}"
