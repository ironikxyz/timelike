#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are expanded inside the container
# Feature 013 (prompt 15, slice 1), SC-4: "Re-running a refused install with the confirm flag proceeds and
# records the override in the session event log" (spec FR-28 to FR-32; 001 rule 9 and rule 16).
#
# The cell runs the refusal's OWN `confirm` string, read from its envelope, not one the test composes. What
# proceeding did is read from disk (the package installed) and from the session's events.jsonl, whose
# package-guard event points (ref.log) at the override record; the record names the package, the ecosystem,
# the registry, the reason and the session (spec FR-30, D-9). Item 24 asks whether those fields belong inside
# the event line instead.
#
# Cells: bash -c and bash -lc, `notty`.

load helpers

setup_file() {
  stamp_check
}

setup() {
  WORK="$(container_tmpdir pg-sc4)"
  standin_start "$WORK"
  exec_plain sh -c 'mkdir -p "$1/np" && printf "{\"name\": \"p\", \"version\": \"1.0.0\"}\n" >"$1/np/package.json" &&
    printf "registry=%s\nupdate-notifier=false\naudit=false\nfund=false\ncache=%s/npm-cache\n" "$2" "$1" >"$1/np/.npmrc"' \
    s "$WORK" "$STANDIN_NPM"
  SESSION="pg-sc4-${RANDOM}"
  ENVS=(-e "PIP_INDEX_URL=${STANDIN_SIMPLE}" -e PIP_NO_CACHE_DIR=1 -e PIP_DISABLE_PIP_VERSION_CHECK=1
    -e "TIMELIKE_SCRATCH_ROOT=${WORK}/scratch" -e "TIMELIKE_SESSION=${SESSION}")
}

teardown() {
  standin_stop
  container_rm "${WORK:-}"
}

flunk() {
  printf '%s\nexit %s; output:\n%s\nevents:\n%s\n' "$1" "$status" "$output" \
    "$(exec_plain cat "${WORK}/scratch/${SESSION}/events.jsonl" 2>&1)" >&2
  return 1
}

# the override the session's last package-guard event points at, as "package|ecosystem|registry|reason|session"
recorded_override() {
  exec_plain "$STANDIN_PY" -I -c '
import json, sys
events = [json.loads(x) for x in open(sys.argv[1], encoding="utf-8") if x.strip()]
ev = [e for e in events if e["tool"] == "package-guard"][-1]
rec = json.load(open(ev["ref"]["log"], encoding="utf-8"))
for o in rec["overridden"]:
    print("|".join([o["package"], o["ecosystem"], o["registry"], o["reason"], rec["session"], str(ev["exit"])]))' \
    "${WORK}/scratch/${SESSION}/events.jsonl"
}

check_confirm() {
  local style="$1" dir="$2" cmd="$3" eco="$4" registry="$5" confirm
  run_in "${ENVS[@]}" -w "$dir" "$style" notty "$cmd"
  assert_within 60
  [[ "$status" == 4 ]] || flunk "want the refusal first"
  confirm="$(pyj 'import json, sys; print(json.load(sys.stdin)["confirm"])')"
  [[ "$confirm" == "package-guard --yes -- ${cmd#package-guard -- }" ]] || flunk "confirm: $confirm"
  run_in "${ENVS[@]}" -w "$dir" "$style" notty "$confirm"
  assert_within 120
  [[ "$status" == 0 ]] || flunk "the confirm did not proceed (want the installer's exit 0)"
  [[ "$(recorded_override)" == "tl-fresh|${eco}|${registry}|too-new|${SESSION}|0" ]] ||
    flunk "the session's event log does not lead to the override: $(recorded_override 2>&1)"
}

@test "SC-4 [bash -c, notty] pip: the refusal's confirm proceeds, installs, and the session event log records the override" {
  # unquoted: the confirm is shlex.join's, which quotes only what needs it (container_tmpdir's path does not)
  check_confirm c "$WORK" "package-guard -- pip install --target ${WORK}/t tl-fresh" pypi "$STANDIN_SIMPLE"
  [[ "$(exec_plain cat "${WORK}/t/tl_fresh/__init__.py")" == *'VERSION = "1.1.0"'* ]] || flunk "not installed"
}

@test "SC-4 [bash -lc, notty] npm: the refusal's confirm proceeds, installs, and the session event log records the override" {
  check_confirm lc "${WORK}/np" "package-guard -- npm install tl-fresh" npm "$STANDIN_NPM"
  [[ "$(exec_plain cat "${WORK}/np/node_modules/tl-fresh/index.js")" == *'tl-fresh@1.1.0'* ]] || flunk "not installed"
}

@test "SC-4 [bash -c, notty] --yes over nothing refused records no override" {
  run_in "${ENVS[@]}" c notty "package-guard --yes -- pip install --target '${WORK}/t' tl-old"
  assert_within 120
  [[ "$status" == 0 ]] || flunk "want pip's exit 0"
  [[ -z "$(exec_plain sh -c 'ls "$1"/scratch/*/package-guard/override-*.json 2>/dev/null' s "$WORK")" ]] ||
    flunk "an override record was written though nothing was refused"
}
