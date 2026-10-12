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
# The installers run by their BARE names (FOR-MENTOR Item 24, condition 7), through /opt/timelike/shims. pip
# makes the user install the image's pip.conf asks for (007 FR-26), into the cell's own HOME: lane 013s1-a2
# showed that pip will not combine that setting with --target, so no cell passes --target or --prefix to pip
# (its item 1). A passing install's output is pip's or npm's own: the shim drops the guard's verdict and
# execs the installer (Item 24, condition 2).
#
# Cells: pip refused in bash -c, bash -lc, bash -ic and a bash script; npm refused; the named older release
# installs (pip and npm); TIMELIKE_PACKAGE_MIN_AGE_DAYS=0 installs the newest. `notty`.

load helpers

setup_file() {
  stamp_check
}

setup() {
  WORK="$(container_tmpdir pg-sc2)"
  standin_start "$WORK"
  exec_plain sh -c 'mkdir -p "$1/np" "$1/home" && printf "{\"name\": \"p\", \"version\": \"1.0.0\"}\n" >"$1/np/package.json" &&
    printf "registry=%s\nupdate-notifier=false\naudit=false\nfund=false\ncache=%s/npm-cache\n" "$2" "$1" >"$1/np/.npmrc" &&
    touch "$1/marker"' s "$WORK" "$STANDIN_NPM"
  # shellcheck disable=SC2034 # read by run_bare (helpers.bash)
  ENVS=(-e "HOME=${WORK}/home" -e "PIP_INDEX_URL=${STANDIN_SIMPLE}" -e PIP_NO_CACHE_DIR=1
    -e PIP_DISABLE_PIP_VERSION_CHECK=1 -e "TIMELIKE_SCRATCH_ROOT=${WORK}/scratch" -e TIMELIKE_SESSION=pg-sc2)
}

teardown() {
  standin_stop
  container_rm "${WORK:-}"
}

flunk() {
  printf '%s\nexit %s; output:\n%s\n' "$1" "$status" "$output" >&2
  return 1
}

# user_site_version MODULE — the VERSION of MODULE in the cell's own user site, $WORK/home/.local, or "none"
user_site_version() {
  exec_plain sh -c 'for f in "$1"/home/.local/lib/python3.*/site-packages/"$2"/__init__.py; do
    [ -f "$f" ] && sed -n "s/^VERSION = \"\(.*\)\"$/\1/p" "$f" && exit 0; done; echo none' s "$WORK" "$1"
}

# landed_only_in_cell MODULE — MODULE is in no site the agent's python reads outside the cell's HOME, and
# nothing under the agent's own ~/.local changed
landed_only_in_cell() {
  local elsewhere
  elsewhere="$(exec_plain sh -c 'ls -d /home/agent/.local/lib/python3.*/site-packages/"$2" \
    /opt/agent/python/lib/python3.*/site-packages/"$2" 2>/dev/null; find /home/agent/.local -newer "$1/marker" -print 2>/dev/null' \
    s "$WORK" "$1")"
  [[ -z "$elsewhere" ]] || flunk "the install landed outside the cell's HOME: $elsewhere"
}

check_pip_too_new() {
  local style="$1" date
  date="$(standin_released pypi tl-fresh 1.1.0)"
  [[ "$date" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]] || flunk "the stand-in's date: $date"
  run_bare "$style" "$WORK" "pip install tl-fresh"
  assert_within 60
  [[ "$status" == 4 ]] || flunk "want exit 4"
  [[ "$output" == *"refused: tl-fresh — too new: newest release 1.1.0 was released ${date} "* ]] ||
    flunk "the refusal does not name the newest release's date, ${date}"
  [[ "$output" == *"the minimum age is 2 days (TIMELIKE_PACKAGE_MIN_AGE_DAYS)"* ]] || flunk "the minimum age and its variable"
  [[ "$output" == *"pin it as tl-fresh==1.0.0"* ]] || flunk "the release old enough to pin"
  [[ "$(standin_count files)" == 0 ]] || flunk "a file was downloaded"
  [[ "$(user_site_version tl_fresh)" == none ]] || flunk "something was installed"
}

@test "SC-2 [bash -c, notty] bare pip install: the newest release one day old is refused with exit 4, naming its release date" {
  check_pip_too_new c
}

@test "SC-2 [bash -lc, notty] bare pip install: the newest release one day old is refused with exit 4, naming its release date" {
  check_pip_too_new lc
}

@test "SC-2 [bash -ic, notty] bare pip install: the newest release one day old is refused with exit 4, naming its release date" {
  check_pip_too_new ic
}

@test "SC-2 [a bash script, notty] bare pip install: the newest release one day old is refused with exit 4, naming its release date" {
  check_pip_too_new script
}

@test "SC-2 [bash -c, notty] bare npm install: the newest release one day old is refused with exit 4, naming its release date" {
  local date
  date="$(standin_released npm tl-fresh 1.1.0)"
  run_bare c "${WORK}/np" "npm install tl-fresh"
  assert_within 60
  [[ "$status" == 4 ]] || flunk "want exit 4"
  [[ "$output" == *"refused: tl-fresh — too new: newest release 1.1.0 was released ${date} "* ]] ||
    flunk "the refusal does not name ${date}"
  [[ "$output" == *"pin it as tl-fresh@1.0.0"* ]] || flunk "the release old enough to pin"
  exec_plain test ! -e "${WORK}/np/node_modules" || flunk "node_modules was written"
}

@test "SC-2 [bash -c, notty] the named older release passes and installs as the agent installs (its own age is checked; the output is the installer's own)" {
  run_bare c "$WORK" "pip install tl-fresh==1.0.0"
  assert_within 120
  [[ "$status" == 0 ]] || flunk "want pip's exit 0"
  [[ "$output" == *"Successfully installed tl-fresh-1.0.0"* ]] || flunk "pip's own output"
  [[ "$output" != *'"tool": "package-guard"'* && "$output" != *"gate passed"* ]] || flunk "the guard's output reached the caller"
  [[ "$(user_site_version tl_fresh)" == 1.0.0 ]] || flunk "1.0.0 is not what pip installed into the user site"
  landed_only_in_cell tl_fresh
  run_bare c "${WORK}/np" "npm install tl-fresh@1.0.0"
  assert_within 120
  [[ "$status" == 0 ]] || flunk "want npm's exit 0"
  [[ "$output" != *'"tool": "package-guard"'* ]] || flunk "the guard's output reached the caller"
  [[ "$(exec_plain cat "${WORK}/np/node_modules/tl-fresh/index.js")" == *'tl-fresh@1.0.0'* ]] || flunk "npm installed another"
}

@test "SC-2 [bash -c, notty] TIMELIKE_PACKAGE_MIN_AGE_DAYS=0 turns the age check off: the newest installs as the agent installs" {
  run_bare c "$WORK" "pip install tl-fresh" -e TIMELIKE_PACKAGE_MIN_AGE_DAYS=0
  assert_within 120
  [[ "$status" == 0 ]] || flunk "want pip's exit 0"
  [[ "$(user_site_version tl_fresh)" == 1.1.0 ]] || flunk "1.1.0 is not what pip installed into the user site"
  landed_only_in_cell tl_fresh
}
