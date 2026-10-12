#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are expanded inside the container
# Feature 013 (prompt 15, slice 1), SC-1: "Installing a package name absent from its registry is refused with
# exit 4 before anything is downloaded, naming the package and the registry checked" (spec FR-14, FR-16,
# FR-28; lore cross-stack P001, P004, P005).
#
# The installers are the image's real pip, uv and npm, through `package-guard`, against the registry stand-in
# running inside the agent container (tests/fixtures/registry-standin.py; spec D-10). "Before anything is
# downloaded" is read from the stand-in's own request log (no wheel or tarball request) and from disk (nothing
# new under ~/.local, the target, or node_modules), never from the guard's message (P004).
#
# The bare `pip install` reaching the guard is FOR-MENTOR Item 24's: these cells name `package-guard` in the
# command, as its envelope's confirm does.
#
# Cells: bash -c and bash -lc, `notty`, the harness's own invocation.

load helpers

setup_file() {
  stamp_check
}

setup() {
  WORK="$(container_tmpdir pg-sc1)"
  standin_start "$WORK"
  exec_plain sh -c 'mkdir -p "$1/np" && printf "{\"name\": \"p\", \"version\": \"1.0.0\"}\n" >"$1/np/package.json" &&
    printf "registry=%s\nupdate-notifier=false\naudit=false\nfund=false\ncache=%s/npm-cache\n" "$2" "$1" >"$1/np/.npmrc" &&
    touch "$1/marker"' s "$WORK" "$STANDIN_NPM"
  ENVS=(-e "PIP_INDEX_URL=${STANDIN_SIMPLE}" -e "UV_DEFAULT_INDEX=${STANDIN_SIMPLE}" -e "UV_CACHE_DIR=${WORK}/uv-cache"
    -e PIP_NO_CACHE_DIR=1 -e PIP_DISABLE_PIP_VERSION_CHECK=1 -e "TIMELIKE_SCRATCH_ROOT=${WORK}/scratch"
    -e TIMELIKE_SESSION=pg-sc1)
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

# the envelope's fields, read with timelike's interpreter from the last run's stdout
envelope_field() {
  pyj "import json, sys; d = json.load(sys.stdin); v = d[sys.argv[1]] if len(sys.argv) > 1 else d
print(v if isinstance(v, str) else json.dumps(v))" 2>/dev/null || true
}

check_pip_absent() {
  local style="$1" plan confirm
  run_in "${ENVS[@]}" "$style" notty "package-guard -- pip install tl-absent-pkg tl-old"
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
  [[ -z "$(exec_plain sh -c 'find /home/agent/.local -newer "$1/marker" -print 2>/dev/null' s "$WORK")" ]] ||
    flunk "something under ~/.local changed"
}

@test "SC-1 [bash -c, notty] pip: an absent name is refused with exit 4, naming it and the registry, nothing downloaded" {
  check_pip_absent c
}

@test "SC-1 [bash -lc, notty] pip: an absent name is refused with exit 4, naming it and the registry, nothing downloaded" {
  check_pip_absent lc
}

@test "SC-1 [bash -c, notty] uv pip install: an absent name is refused with exit 4 before uv runs" {
  run_in "${ENVS[@]}" c notty "package-guard -- uv pip install --target '${WORK}/t' tl-absent-pkg"
  assert_within 60
  [[ "$status" == 4 ]] || flunk "want exit 4"
  [[ "$output" == *"tl-absent-pkg — not found: not in ${STANDIN_SIMPLE} (HTTP 404)"* ]] || flunk "plan"
  [[ "$(standin_count files)" == 0 ]] || flunk "a file was downloaded"
  exec_plain test ! -e "${WORK}/t" || flunk "the target was written"
}

@test "SC-1 [bash -c, notty] npm: an absent name is refused with exit 4 before npm runs, no tarball, no node_modules" {
  run_in "${ENVS[@]}" -w "${WORK}/np" c notty "package-guard -- npm install tl-left tl-absent-pkg"
  assert_within 60
  [[ "$status" == 4 ]] || flunk "want exit 4"
  [[ "$output" == *"refused: tl-absent-pkg — not found: not in ${STANDIN_NPM} (HTTP 404)"* ]] || flunk "plan"
  [[ "$output" == *"ok: tl-left 1.3.0"* ]] || flunk "the other name's line"
  [[ "$(standin_count files)" == 0 ]] || flunk "a tarball was downloaded"
  exec_plain test ! -e "${WORK}/np/node_modules" || flunk "node_modules was written"
}

@test "SC-1 [bash -c, notty] a registry that answers 503 is unreachable, never absent (P001)" {
  run_in "${ENVS[@]}" c notty "package-guard -- pip install tl-broken"
  assert_within 60
  [[ "$status" == 4 ]] || flunk "want exit 4"
  [[ "$output" == *"tl-broken — registry unreachable: ${STANDIN_SIMPLE} unreachable from this container: HTTP 503"* ]] ||
    flunk "the plan does not say unreachable, and how"
  [[ "$output" != *"not found"* ]] || flunk "an unreachable registry was called absent"
}
