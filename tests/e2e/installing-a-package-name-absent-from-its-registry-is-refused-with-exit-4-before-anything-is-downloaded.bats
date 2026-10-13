#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are expanded inside the container
# Feature 013 (prompt 15, slice 1), SC-1: "Installing a package name absent from its registry is refused with
# exit 4 before anything is downloaded, naming the package and the registry checked" (spec FR-14, FR-16,
# FR-28; lore cross-stack P001, P004, P005).
#
# The installers are the image's real pip, uv, npm and npx, run by their BARE names as the agent runs them
# (FOR-MENTOR Item 24, condition 7): each reaches the guard through /opt/timelike/shims, as the image wires
# it, and nothing here names package-guard. They ask the registry stand-in running inside the agent container
# (tests/fixtures/registry-standin.py; spec D-10). "Before anything is downloaded" is read from the stand-in's
# own request log (no wheel or tarball request) and from disk (nothing new under ~/.local, the cell's HOME,
# the venv or node_modules), never from the guard's message (P004).
#
# pip makes its user install, as the image's pip.conf says (007 FR-26), into the cell's own HOME (item 1 of
# lane 013s1-a2's findings): nothing in these cells passes --target or --prefix to pip.
#
# Cells: pip in bash -c, bash -lc, bash -ic and a bash script; uv pip install into a venv; npm; npx; pnpm
# installed into ~/.local/bin as the agent would; a 503 registry called unreachable, not absent. `notty`.

load helpers

setup_file() {
  stamp_check
}

setup() {
  WORK="$(container_tmpdir pg-sc1)"
  standin_start "$WORK"
  exec_plain sh -c 'mkdir -p "$1/np" "$1/home" "$1/up" && printf "{\"name\": \"p\", \"version\": \"1.0.0\"}\n" >"$1/np/package.json" &&
    printf "registry=%s\nupdate-notifier=false\naudit=false\nfund=false\ncache=%s/npm-cache\n" "$2" "$1" >"$1/np/.npmrc" &&
    touch "$1/marker"' s "$WORK" "$STANDIN_NPM"
  # shellcheck disable=SC2034 # read by run_bare (helpers.bash)
  ENVS=(-e "HOME=${WORK}/home" -e "PIP_INDEX_URL=${STANDIN_SIMPLE}" -e "UV_DEFAULT_INDEX=${STANDIN_SIMPLE}"
    -e "UV_CACHE_DIR=${WORK}/uv-cache" -e UV_PYTHON_DOWNLOADS=never -e PIP_NO_CACHE_DIR=1
    -e PIP_DISABLE_PIP_VERSION_CHECK=1 -e "TIMELIKE_SCRATCH_ROOT=${WORK}/scratch" -e TIMELIKE_SESSION=pg-sc1)
}

teardown() {
  standin_stop
  if [[ -n "${PNPM_INSTALLED:-}" ]]; then
    exec_plain npm uninstall -g --offline pnpm >/dev/null 2>&1 || true
  fi
  container_rm "${WORK:-}"
}

flunk() {
  printf '%s\nexit %s; output:\n%s\nstand-in log:\n%s\n' "$1" "$status" "$output" \
    "$(exec_plain cat "${WORK}/run/requests.jsonl" 2>&1)" >&2
  return 1
}

# nothing_new — nothing under the agent's ~/.local or the cell's HOME is newer than the cell's marker
nothing_new() {
  [[ -z "$(exec_plain sh -c 'find /home/agent/.local "$1/home" -newer "$1/marker" -print 2>/dev/null' s "$WORK")" ]] ||
    flunk "something under ~/.local or the cell's HOME changed: $(exec_plain sh -c 'find /home/agent/.local "$1/home" -newer "$1/marker" -print 2>/dev/null | head' s "$WORK")"
}

check_pip_absent() {
  local style="$1" plan confirm
  run_bare "$style" "$WORK" "pip install tl-absent-pkg tl-old"
  assert_within 60
  [[ "$status" == 4 ]] || flunk "want exit 4"
  plan="$(pyj 'import json, sys; print("\n".join(json.load(sys.stdin)["plan"]))')"
  [[ "$plan" == *"refused: tl-absent-pkg — not found: not in ${STANDIN_SIMPLE} (HTTP 404)"* ]] ||
    flunk "the plan does not name the package and the registry: $plan"
  confirm="$(pyj 'import json, sys; print(json.load(sys.stdin)["confirm"])')"
  [[ "$confirm" == "package-guard --yes -- pip install tl-absent-pkg tl-old" ]] || flunk "confirm: $confirm"
  [[ "$(pyj 'import json, sys; print(json.load(sys.stdin)["status"])')" == confirmation_required ]] || flunk "status"
  [[ "$(standin_count files)" == 0 ]] || flunk "a file was downloaded"
  [[ "$(standin_count guard)" == "$(standin_count all)" ]] || flunk "something other than the guard asked the registry"
  nothing_new
}

@test "SC-1 [bash -c, notty] bare pip install: an absent name is refused with exit 4, naming it and the registry, nothing downloaded" {
  check_pip_absent c
}

@test "SC-1 [bash -lc, notty] bare pip install: an absent name is refused with exit 4, naming it and the registry, nothing downloaded" {
  check_pip_absent lc
}

@test "SC-1 [bash -ic, notty] bare pip install: an absent name is refused with exit 4, naming it and the registry, nothing downloaded" {
  check_pip_absent ic
}

@test "SC-1 [a bash script, notty] bare pip install: an absent name is refused with exit 4, naming it and the registry, nothing downloaded" {
  check_pip_absent script
}

@test "SC-1 [bash -c, notty] bare uv pip install into the project's venv: an absent name is refused with exit 4 before uv installs" {
  run_bare c "${WORK}/up" "uv venv -q"
  [[ "$status" == 0 ]] || flunk "setup: uv venv"
  standin_clear
  run_bare c "${WORK}/up" "uv pip install tl-absent-pkg"
  assert_within 60
  [[ "$status" == 4 ]] || flunk "want exit 4"
  [[ "$output" == *"refused: tl-absent-pkg — not found: not in ${STANDIN_SIMPLE} (HTTP 404)"* ]] || flunk "plan"
  [[ "$output" == *'"confirm": "package-guard --yes -- uv pip install tl-absent-pkg"'* ]] || flunk "confirm"
  [[ "$(standin_count files)" == 0 ]] || flunk "a file was downloaded"
  [[ "$(standin_count guard)" == "$(standin_count all)" ]] || flunk "uv asked the registry: it ran"
}

@test "SC-1 [bash -lc, notty] bare npm install: an absent name is refused with exit 4 before npm runs, no tarball, no node_modules" {
  run_bare lc "${WORK}/np" "npm install tl-left tl-absent-pkg"
  assert_within 60
  [[ "$status" == 4 ]] || flunk "want exit 4"
  [[ "$output" == *"refused: tl-absent-pkg — not found: not in ${STANDIN_NPM} (HTTP 404)"* ]] || flunk "plan"
  [[ "$output" == *"ok: tl-left 1.3.0"* ]] || flunk "the other name's line"
  [[ "$(standin_count files)" == 0 ]] || flunk "a tarball was downloaded"
  [[ "$(standin_count guard)" == "$(standin_count all)" ]] || flunk "npm asked the registry: it ran"
  exec_plain test ! -e "${WORK}/np/node_modules" || flunk "node_modules was written"
}

@test "SC-1 [a bash script, notty] bare npx: an absent package is refused with exit 4 before npx fetches it" {
  run_bare script "${WORK}/np" "npx tl-absent-pkg"
  assert_within 60
  [[ "$status" == 4 ]] || flunk "want exit 4"
  [[ "$output" == *"refused: tl-absent-pkg — not found: not in ${STANDIN_NPM} (HTTP 404)"* ]] || flunk "plan"
  [[ "$(standin_count files)" == 0 ]] || flunk "a tarball was downloaded"
  [[ "$(standin_count guard)" == "$(standin_count all)" ]] || flunk "npx asked the registry: it ran"
}

# pnpm is not in the image (Item 24 Q3). The agent installs it with a bare `npm install -g pnpm`, into
# ~/.local/bin; here the package is the stand-in's `pnpm`, a script that only says it ran (pnpm itself would
# need the public registry). What this shows is the shim reaching a pnpm the agent installed, ahead of it on
# PATH; pnpm's own install forms against the stand-in are the host's units, with the host's real pnpm.
@test "SC-1 [bash -c, notty] a pnpm the agent installed into ~/.local/bin: bare pnpm add of an absent name is refused with exit 4, and pnpm never runs" {
  local -a envs=(-e "npm_config_registry=${STANDIN_NPM}" -e "npm_config_cache=${WORK}/npm-cache"
    -e npm_config_audit=false -e npm_config_fund=false -e npm_config_update_notifier=false
    -e "TIMELIKE_SCRATCH_ROOT=${WORK}/scratch" -e TIMELIKE_SESSION=pg-sc1)
  exec_plain test ! -e /home/agent/.local/bin/pnpm || flunk "a pnpm is already in ~/.local/bin"
  PNPM_INSTALLED=1
  run_in "${envs[@]}" -w "$WORK" c notty "npm install -g pnpm"
  [[ "$status" == 0 ]] || flunk "setup: the bare npm install -g pnpm (through its own shim)"
  run_in "${envs[@]}" -w "${WORK}/np" c notty 'type -a -P pnpm; pnpm --version'
  [[ "${lines[0]}" == /opt/timelike/shims/pnpm && "${lines[1]}" == /home/agent/.local/bin/pnpm ]] ||
    flunk "type -a: want the shim, then ~/.local/bin/pnpm"
  [[ "$output" == *"stand-in pnpm ran: --version"* ]] || flunk "a pnpm that is not an install did not reach pnpm"
  standin_clear
  run_in "${envs[@]}" -w "${WORK}/np" c notty "pnpm add tl-absent-pkg"
  assert_within 60
  [[ "$status" == 4 ]] || flunk "want exit 4"
  [[ "$output" == *"refused: tl-absent-pkg — not found: not in ${STANDIN_NPM} (HTTP 404)"* ]] || flunk "plan"
  [[ "$output" != *"stand-in pnpm ran: add"* ]] || flunk "pnpm ran"
  [[ "$(standin_count files)" == 0 ]] || flunk "a tarball was downloaded"
}

@test "SC-1 [bash -c, notty] bare pip: a registry that answers 503 is unreachable, never absent (P001)" {
  run_bare c "$WORK" "pip install tl-broken"
  assert_within 60
  [[ "$status" == 4 ]] || flunk "want exit 4"
  [[ "$output" == *"tl-broken — registry unreachable: ${STANDIN_SIMPLE} unreachable from this container: HTTP 503"* ]] ||
    flunk "the plan does not say unreachable, and how"
  [[ "$output" != *"not found"* ]] || flunk "an unreachable registry was called absent"
  nothing_new
}
