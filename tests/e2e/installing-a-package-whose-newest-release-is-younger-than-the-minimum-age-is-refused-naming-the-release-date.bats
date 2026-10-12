#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are expanded inside the container
# Feature 013 (prompt 15, slice 1), SC-2: "Installing a package whose newest release is younger than the
# configured minimum age is refused with exit 4, naming the release date" (spec FR-19 to FR-22, D-7).
#
# The stand-in serves `tl-fresh` whose NEWEST release, 1.1.0, was uploaded one day before it started, and an
# older 1.0.0 (120 days). The date the refusal must name is read from the stand-in's own answer (PyPI's
# upload-time, npm's time[1.1.0]), never from the guard (lore P004). The named older release installs, and is
# read back from disk: what was installed, not what was said.
#
# Cells: bash -c and bash -lc, `notty`.

load helpers

setup_file() {
  stamp_check
}

setup() {
  WORK="$(container_tmpdir pg-sc2)"
  standin_start "$WORK"
  exec_plain sh -c 'mkdir -p "$1/np" && printf "{\"name\": \"p\", \"version\": \"1.0.0\"}\n" >"$1/np/package.json" &&
    printf "registry=%s\nupdate-notifier=false\naudit=false\nfund=false\ncache=%s/npm-cache\n" "$2" "$1" >"$1/np/.npmrc"' \
    s "$WORK" "$STANDIN_NPM"
  ENVS=(-e "PIP_INDEX_URL=${STANDIN_SIMPLE}" -e PIP_NO_CACHE_DIR=1 -e PIP_DISABLE_PIP_VERSION_CHECK=1
    -e "TIMELIKE_SCRATCH_ROOT=${WORK}/scratch" -e TIMELIKE_SESSION=pg-sc2)
}

teardown() {
  standin_stop
  container_rm "${WORK:-}"
}

flunk() {
  printf '%s\nexit %s; output:\n%s\n' "$1" "$status" "$output" >&2
  return 1
}

check_pip_too_new() {
  local style="$1" date
  date="$(standin_released pypi tl-fresh 1.1.0)"
  [[ "$date" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]] || flunk "the stand-in's date: $date"
  run_in "${ENVS[@]}" "$style" notty "package-guard -- pip install --target '${WORK}/t' tl-fresh"
  assert_within 60
  [[ "$status" == 4 ]] || flunk "want exit 4"
  [[ "$output" == *"refused: tl-fresh — too new: newest release 1.1.0 was released ${date} "* ]] ||
    flunk "the refusal does not name the newest release's date, ${date}"
  [[ "$output" == *"the minimum age is 2 days (TIMELIKE_PACKAGE_MIN_AGE_DAYS)"* ]] || flunk "the minimum age and its variable"
  [[ "$output" == *"pin it as tl-fresh==1.0.0"* ]] || flunk "the release old enough to pin"
  [[ "$(standin_count files)" == 0 ]] || flunk "a file was downloaded"
  exec_plain test ! -e "${WORK}/t" || flunk "the target was written"
}

@test "SC-2 [bash -c, notty] pip: the newest release one day old is refused with exit 4, naming its release date" {
  check_pip_too_new c
}

@test "SC-2 [bash -lc, notty] pip: the newest release one day old is refused with exit 4, naming its release date" {
  check_pip_too_new lc
}

@test "SC-2 [bash -c, notty] npm: the newest release one day old is refused with exit 4, naming its release date" {
  local date
  date="$(standin_released npm tl-fresh 1.1.0)"
  run_in "${ENVS[@]}" -w "${WORK}/np" c notty "package-guard -- npm install tl-fresh"
  assert_within 60
  [[ "$status" == 4 ]] || flunk "want exit 4"
  [[ "$output" == *"refused: tl-fresh — too new: newest release 1.1.0 was released ${date} "* ]] ||
    flunk "the refusal does not name ${date}"
  exec_plain test ! -e "${WORK}/np/node_modules" || flunk "node_modules was written"
}

@test "SC-2 [bash -c, notty] the named older release passes and installs (its own age is checked)" {
  run_in "${ENVS[@]}" c notty "package-guard -- pip install --target '${WORK}/t' tl-fresh==1.0.0"
  assert_within 120
  [[ "$status" == 0 ]] || flunk "want pip's exit 0"
  [[ "$(exec_plain cat "${WORK}/t/tl_fresh/__init__.py")" == *'VERSION = "1.0.0"'* ]] || flunk "1.0.0 is not what was installed"
  run_in "${ENVS[@]}" -w "${WORK}/np" c notty "package-guard -- npm install tl-fresh@1.0.0"
  assert_within 120
  [[ "$status" == 0 ]] || flunk "want npm's exit 0"
  [[ "$(exec_plain cat "${WORK}/np/node_modules/tl-fresh/index.js")" == *'tl-fresh@1.0.0'* ]] || flunk "npm installed another"
}

@test "SC-2 [bash -c, notty] TIMELIKE_PACKAGE_MIN_AGE_DAYS=0 turns the age check off" {
  run_in "${ENVS[@]}" -e TIMELIKE_PACKAGE_MIN_AGE_DAYS=0 c notty \
    "package-guard -- pip install --target '${WORK}/t' tl-fresh"
  assert_within 120
  [[ "$status" == 0 ]] || flunk "want pip's exit 0"
  [[ "$(exec_plain cat "${WORK}/t/tl_fresh/__init__.py")" == *'VERSION = "1.1.0"'* ]] || flunk "1.1.0 is not installed"
}
