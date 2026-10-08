#!/usr/bin/env bash
# record.sh OUTDIR — records what the REAL runners print about make-project.sh's projects (feature 012,
# research R1; cross-stack P005). Host-only: the image has none of these runners, which is the reason
# the recordings exist. Run once by the code instance; the results are committed beside this file.
#
# Each recording is OUTDIR/NAME.out (stdout and stderr together, as `run`'s log holds them) and
# OUTDIR/NAME.source (where it came from: runner, version, command, date, generator, host).
# Absolute paths are replaced before writing: the project directory by <PROJECT>, the tool directories
# by <TOOLS>, the home directory by <HOME>. Nothing else is edited.
#
# Tools, from the environment (each required; the script stops naming the first one missing):
#   PYTEST RUFF MYPY GO CARGO   executables
#   JS_MODULES                  a node_modules directory holding jest, vitest, typescript and eslint
set -euo pipefail

out="${1:?usage: record.sh OUTDIR}"
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "${out}"
out="$(cd "${out}" && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "${work}"' EXIT
cur_proj="${work}"

for v in PYTEST RUFF MYPY GO CARGO JS_MODULES; do
  [ -n "${!v:-}" ] || {
    echo "record.sh: ${v} is not set" >&2
    exit 2
  }
done

tools_dirs=("$(dirname "${PYTEST}")" "$(dirname "${RUFF}")" "$(dirname "${MYPY}")" "$(dirname "${GO}")"
  "$(dirname "${CARGO}")" "${JS_MODULES}")

scrub() {
  local text d
  text="$(cat)"
  text="${text//${cur_proj}/<PROJECT>}"
  text="${text//${work}/<PROJECT>}"
  for d in "${tools_dirs[@]}"; do text="${text//${d}/<TOOLS>}"; done
  text="${text//${HOME}/<HOME>}"
  printf '%s\n' "${text}"
}

# record NAME KIND VERSION_TEXT CMD... — runs CMD in a fresh KIND project and keeps its output.
record() {
  local name="$1" kind="$2" version="$3"
  shift 3
  local proj="${work}/${name}"
  cur_proj="${proj}"
  rm -rf "${proj}"
  "${here}/make-project.sh" "${kind}" "${proj}"
  case "${kind}" in jest | vitest | lint) ln -s "${JS_MODULES}" "${proj}/node_modules" ;; esac
  local rc=0
  (cd "${proj}" && NO_COLOR=1 TERM=dumb "$@" </dev/null >"${proj}.raw" 2>&1) || rc=$?
  scrub <"${proj}.raw" >"${out}/${name}.out"
  # A path the scrub cannot see (a relative one, through the node_modules link) would still name this
  # host. Stop rather than keep it.
  if grep -qF -e "${USER:-$(id -un)}" -e "$(basename "${work}")" "${out}/${name}.out"; then
    echo "record.sh: ${name}.out still names this host's paths after scrubbing; not kept" >&2
    rm -f "${out}/${name}.out"
    exit 1
  fi
  {
    printf 'runner: %s\n' "${version}"
    printf 'command: %s\n' "$(printf '%q ' "$@" | scrub)"
    printf 'exit: %s\n' "${rc}"
    printf 'project: tests/fixtures/verify/make-project.sh %s\n' "${kind}"
    printf 'recorded_at: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf 'host: %s\n' "$(uname -sm)"
    printf 'recorded_by: tests/fixtures/verify/record.sh (stdout and stderr together, NO_COLOR=1, no terminal)\n'
    printf 'paths: the project directory is <PROJECT>, tool directories <TOOLS>, the home directory <HOME>\n'
  } >"${out}/${name}.source"
  echo "recorded ${name} (exit ${rc})"
}

jsbin="${JS_MODULES}/.bin"
py_v="pytest $("${PYTEST}" --version 2>&1 | awk '{print $2}')"
go_v="$("${GO}" version | awk '{print $1, $3}')"
cargo_v="$("${CARGO}" --version | awk '{print $1, $2}')"

record pytest-default pytest "${py_v}" "${PYTEST}" -p no:cacheprovider
record pytest-q pytest "${py_v}" "${PYTEST}" -q -p no:cacheprovider
record pytest-tb-short pytest "${py_v}" "${PYTEST}" --tb=short -p no:cacheprovider
record pytest-pass-one pytest "${py_v}" "${PYTEST}" -p no:cacheprovider tests/test_cli.py
record jest jest "jest $("${jsbin}/jest" --version)" "${jsbin}/jest"
record vitest vitest "$("${jsbin}/vitest" --version | awk '{print $1}')" "${jsbin}/vitest" run
record go-test go "${go_v}" "${GO}" test ./...
record go-test-v go "${go_v}" "${GO}" test -v ./...
record cargo-test cargo "${cargo_v}" "${CARGO}" test
record cargo-test-no-fail-fast cargo "${cargo_v}" "${CARGO}" test --no-fail-fast
record ruff lint "$("${RUFF}" --version)" "${RUFF}" check --no-cache --output-format concise bad.py
record mypy lint "$("${MYPY}" --version | awk '{print $1, $2}')" "${MYPY}" --no-incremental bad.py
record tsc lint "tsc $("${jsbin}/tsc" --version | awk '{print $2}')" "${jsbin}/tsc" --noEmit -p .
record eslint lint "eslint $("${jsbin}/eslint" --version)" "${jsbin}/eslint" bad.js
