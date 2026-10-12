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
# Cells: bash -c and bash -lc, `notty`.

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
  ENVS=(-e "UV_DEFAULT_INDEX=${STANDIN_SIMPLE}" -e "UV_CACHE_DIR=${WORK}/uv-cache" -e UV_NO_PROGRESS=1
    -e "TIMELIKE_SCRATCH_ROOT=${WORK}/scratch" -e TIMELIKE_SESSION=pg-sc3)
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
  # setup: the image's npm writes package-lock.json, pinning tl-left at 1.3.0 (not through the guard)
  run_in "${ENVS[@]}" -w "${WORK}/np" c notty "npm install tl-left@1.3.0"
  [[ "$status" == 0 ]] || flunk "setup: npm install"
  exec_plain grep -q '"node_modules/tl-left"' "${WORK}/np/package-lock.json" || flunk "setup: no lock entry"
  exec_plain rm -rf "${WORK}/np/node_modules"
  standin_clear
  run_in "${ENVS[@]}" -w "${WORK}/np" "$style" notty "package-guard -- npm install tl-left"
  assert_within 120
  [[ "$status" == 0 ]] || flunk "want npm's exit 0"
  [[ "$(standin_count guard)" == 0 ]] || flunk "the guard asked the registry about a pinned package"
  [[ "$output" == *"pinned: tl-left — pinned in ${WORK}/np/package-lock.json; no registry was asked"* ]] || flunk "plan"
  [[ "$(exec_plain cat "${WORK}/np/node_modules/tl-left/index.js")" == *'tl-left@1.3.0'* ]] || flunk "not installed"
}

@test "SC-3 [bash -c, notty] npm: a name pinned in package-lock.json installs with no request from the guard" {
  check_npm_pinned c
}

@test "SC-3 [bash -lc, notty] npm: a name pinned in package-lock.json installs with no request from the guard" {
  check_npm_pinned lc
}

@test "SC-3 [bash -c, notty] npm ci installs exactly the lockfile with no request from the guard" {
  run_in "${ENVS[@]}" -w "${WORK}/np" c notty "npm install tl-left@1.3.0"
  [[ "$status" == 0 ]] || flunk "setup: npm install"
  exec_plain rm -rf "${WORK}/np/node_modules"
  standin_clear
  run_in "${ENVS[@]}" -w "${WORK}/np" c notty "package-guard -- npm ci"
  assert_within 120
  [[ "$status" == 0 ]] || flunk "want npm's exit 0"
  [[ "$(standin_count guard)" == 0 ]] || flunk "the guard asked the registry for npm ci"
  [[ "$(exec_plain cat "${WORK}/np/node_modules/tl-left/index.js")" == *'tl-left@1.3.0'* ]] || flunk "not installed"
}

@test "SC-3 [bash -c, notty] uv: uv.lock written by uv pins its packages; uv sync --locked and an install of a pinned name ask nothing" {
  run_in "${ENVS[@]}" -w "${WORK}/up" c notty "uv lock"
  [[ "$status" == 0 ]] || flunk "setup: uv lock"
  exec_plain grep -q 'name = "tl-old"' "${WORK}/up/uv.lock" || flunk "setup: uv.lock has no tl-old"
  standin_clear
  run_in "${ENVS[@]}" -w "${WORK}/up" c notty "package-guard -- uv sync --locked"
  assert_within 180
  [[ "$status" == 0 ]] || flunk "want uv's exit 0"
  [[ "$(standin_count guard)" == 0 ]] || flunk "the guard asked the registry for uv sync --locked"
  exec_plain sh -c 'ls -d "$1"/up/.venv/lib/python*/site-packages/tl_old' s "$WORK" >/dev/null || flunk "not installed"
  standin_clear
  run_in "${ENVS[@]}" -w "${WORK}/up" c notty "package-guard -- uv pip install --target '${WORK}/t' tl-old"
  assert_within 180
  [[ "$status" == 0 ]] || flunk "want uv's exit 0"
  [[ "$(standin_count guard)" == 0 ]] || flunk "the guard asked the registry about a name uv.lock pins"
  [[ "$output" == *"pinned: tl-old — pinned in ${WORK}/up/uv.lock"* ]] || flunk "plan"
}
