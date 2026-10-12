#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are expanded inside the container
# Feature 013 (prompt 15, slice 1), SC-3: "Installing packages already pinned in the project's lockfile
# proceeds without registry checks" (spec FR-23 to FR-26).
#
# The lockfiles are written by the image's own npm and uv against the stand-in, so the guard reads what the
# installers write (lore P005), not a hand-made file. "Without registry checks" is the stand-in's log holding no
# request with the guard's user agent (timelike-package-guard/…), read after the install; the installer's own
# requests are its business. The install completes, read back from node_modules and the project's venv.
#
# The installers run by their BARE names (FOR-MENTOR Item 24, condition 7), through /opt/timelike/shims as the
# image wires them; nothing here names package-guard. The setup installs that write the lockfiles go through
# the shims too (they pass: tl-left 1.3.0 and tl-old are old enough), and the stand-in's log is cleared after
# them, so only the install under test is read.
#
# Cells: npm install of a pinned name in bash -c, bash -lc, bash -ic and a bash script; npm ci; uv sync
# --locked and uv pip install of a name uv.lock pins. `notty`.

load helpers

setup_file() {
  stamp_check
}

setup() {
  WORK="$(container_tmpdir pg-sc3)"
  standin_start "$WORK"
  exec_plain sh -c 'mkdir -p "$1/np" "$1/up" &&
    printf "{\"name\": \"p\", \"version\": \"1.0.0\"}\n" >"$1/np/package.json" &&
    printf "registry=%s\nupdate-notifier=false\naudit=false\nfund=false\ncache=%s/npm-cache\n" "$2" "$1" >"$1/np/.npmrc" &&
    printf "[project]\nname = \"up\"\nversion = \"0.1.0\"\nrequires-python = \">=3.12\"\ndependencies = [\"tl-old\"]\n" \
      >"$1/up/pyproject.toml"' s "$WORK" "$STANDIN_NPM"
  # shellcheck disable=SC2034 # read by run_bare (helpers.bash)
  ENVS=(-e "UV_DEFAULT_INDEX=${STANDIN_SIMPLE}" -e "UV_CACHE_DIR=${WORK}/uv-cache" -e UV_NO_PROGRESS=1
    -e UV_PYTHON_DOWNLOADS=never -e "TIMELIKE_SCRATCH_ROOT=${WORK}/scratch" -e TIMELIKE_SESSION=pg-sc3)
}

teardown() {
  standin_stop
  container_rm "${WORK:-}"
}

flunk() {
  printf '%s\nexit %s; output:\n%s\nstand-in log:\n%s\n' "$1" "$status" "$output" \
    "$(exec_plain cat "${WORK}/run/requests.jsonl" 2>&1)" >&2
  return 1
}

check_npm_pinned() {
  local style="$1"
  # setup: the image's npm writes package-lock.json, pinning tl-left at 1.3.0
  run_bare c "${WORK}/np" "npm install tl-left@1.3.0"
  [[ "$status" == 0 ]] || flunk "setup: npm install"
  exec_plain grep -q '"node_modules/tl-left"' "${WORK}/np/package-lock.json" || flunk "setup: no lock entry"
  exec_plain rm -rf "${WORK}/np/node_modules" "${WORK}/scratch/pg-sc3/events.jsonl"
  standin_clear
  run_bare "$style" "${WORK}/np" "npm install tl-left"
  assert_within 120
  [[ "$status" == 0 ]] || flunk "want npm's exit 0"
  [[ "$(standin_count guard)" == 0 ]] || flunk "the guard asked the registry about a pinned package"
  [[ "$output" != *'"tool": "package-guard"'* ]] || flunk "the guard's output reached the caller"
  # the guard's own record of what it decided: its session event (exit 0, --gate) and no lookup
  [[ "$(gate_events 0)" == 1 ]] || flunk "the session has no passing gate event for this install"
  [[ "$(exec_plain cat "${WORK}/np/node_modules/tl-left/index.js")" == *'tl-left@1.3.0'* ]] || flunk "not installed"
}

# gate_events EXIT — how many package-guard --gate events in the cell's session ended with EXIT
gate_events() {
  exec_plain "$STANDIN_PY" -I -c '
import json, sys
try:
    rows = [json.loads(x) for x in open(sys.argv[1], encoding="utf-8") if x.strip()]
except FileNotFoundError:
    rows = []
print(sum(1 for r in rows if r["tool"] == "package-guard" and "--gate" in r["args"] and r["exit"] == int(sys.argv[2])))' \
    "${WORK}/scratch/pg-sc3/events.jsonl" "$1"
}

@test "SC-3 [bash -c, notty] bare npm install: a name pinned in package-lock.json installs with no request from the guard" {
  check_npm_pinned c
}

@test "SC-3 [bash -lc, notty] bare npm install: a name pinned in package-lock.json installs with no request from the guard" {
  check_npm_pinned lc
}

@test "SC-3 [bash -ic, notty] bare npm install: a name pinned in package-lock.json installs with no request from the guard" {
  check_npm_pinned ic
}

@test "SC-3 [a bash script, notty] bare npm install: a name pinned in package-lock.json installs with no request from the guard" {
  check_npm_pinned script
}

@test "SC-3 [bash -c, notty] bare npm ci installs exactly the lockfile with no request from the guard" {
  run_bare c "${WORK}/np" "npm install tl-left@1.3.0"
  [[ "$status" == 0 ]] || flunk "setup: npm install"
  exec_plain rm -rf "${WORK}/np/node_modules"
  standin_clear
  run_bare c "${WORK}/np" "npm ci"
  assert_within 120
  [[ "$status" == 0 ]] || flunk "want npm's exit 0"
  [[ "$(standin_count guard)" == 0 ]] || flunk "the guard asked the registry for npm ci"
  [[ "$(exec_plain cat "${WORK}/np/node_modules/tl-left/index.js")" == *'tl-left@1.3.0'* ]] || flunk "not installed"
}

@test "SC-3 [bash -lc, notty] bare uv: uv.lock written by uv pins its packages; uv sync --locked and an install of a pinned name ask nothing" {
  run_bare lc "${WORK}/up" "uv lock"
  [[ "$status" == 0 ]] || flunk "setup: uv lock"
  exec_plain grep -q 'name = "tl-old"' "${WORK}/up/uv.lock" || flunk "setup: uv.lock has no tl-old"
  standin_clear
  run_bare lc "${WORK}/up" "uv sync --locked"
  assert_within 180
  [[ "$status" == 0 ]] || flunk "want uv's exit 0"
  [[ "$(standin_count guard)" == 0 ]] || flunk "the guard asked the registry for uv sync --locked"
  exec_plain sh -c 'ls -d "$1"/up/.venv/lib/python*/site-packages/tl_old' s "$WORK" >/dev/null || flunk "not installed"
  standin_clear
  run_bare lc "${WORK}/up" "uv pip install tl-old"
  assert_within 180
  [[ "$status" == 0 ]] || flunk "want uv's exit 0"
  [[ "$(standin_count guard)" == 0 ]] || flunk "the guard asked the registry about a name uv.lock pins"
  [[ "$(gate_events 0)" == 2 ]] || flunk "want two passing gate events (uv sync, uv pip install)"
}
