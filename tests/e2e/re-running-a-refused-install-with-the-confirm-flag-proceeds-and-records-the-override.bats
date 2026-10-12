#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are expanded inside the container
# Feature 013 (prompt 15, slice 1), SC-4: "Re-running a refused install with the confirm flag proceeds and
# records the override in the session event log" (spec FR-28 to FR-32; 001 rule 9 and rule 16; FOR-MENTOR
# Item 24, Q2 and Q4).
#
# The refused install is the agent's own: the installer by its BARE name, reaching the guard through
# /opt/timelike/shims (Item 24, condition 7). The cell then runs the refusal's OWN `confirm` string, read
# from its envelope, not one the test composes: `package-guard --yes -- <the original command>` (Q2). What
# proceeding did is read from disk (the package installed, pip's into the cell's own HOME as the image's
# pip.conf asks: no --target, lane 013s1-a2's item 1) and from the session's events.jsonl, whose package-guard
# event carries the override in the line itself (Q4: `override`, with the ecosystem, each package with the
# reason it was refused and the release date the stand-in serves, the registry, and the command); its `ref`
# still points at the override record.
#
# Cells: pip in bash -c, bash -lc, bash -ic and a bash script; npm in bash -c; --yes over nothing refused
# records no override. `notty`.

load helpers

setup_file() {
  stamp_check
}

setup() {
  WORK="$(container_tmpdir pg-sc4)"
  standin_start "$WORK"
  exec_plain sh -c 'mkdir -p "$1/np" "$1/home" && printf "{\"name\": \"p\", \"version\": \"1.0.0\"}\n" >"$1/np/package.json" &&
    printf "registry=%s\nupdate-notifier=false\naudit=false\nfund=false\ncache=%s/npm-cache\n" "$2" "$1" >"$1/np/.npmrc"' \
    s "$WORK" "$STANDIN_NPM"
  SESSION="pg-sc4-${RANDOM}"
  # shellcheck disable=SC2034 # read by run_bare (helpers.bash)
  ENVS=(-e "HOME=${WORK}/home" -e "PIP_INDEX_URL=${STANDIN_SIMPLE}" -e PIP_NO_CACHE_DIR=1
    -e PIP_DISABLE_PIP_VERSION_CHECK=1 -e "TIMELIKE_SCRATCH_ROOT=${WORK}/scratch" -e "TIMELIKE_SESSION=${SESSION}")
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

# recorded_override — from the session's last package-guard event, one line per overridden package:
#   name|reason|released date|registry|ecosystem|command|event exit|the record's session
recorded_override() {
  exec_plain "$STANDIN_PY" -I -c '
import json, sys
events = [json.loads(x) for x in open(sys.argv[1], encoding="utf-8") if x.strip()]
ev = [e for e in events if e["tool"] == "package-guard"][-1]
o = ev["override"]
rec = json.load(open(ev["ref"]["log"], encoding="utf-8"))
for p in o["packages"]:
    print("|".join([p["name"], p["reason"], p.get("released", "")[:10], p["registry"], o["ecosystem"],
                    " ".join(o["command"]), str(ev["exit"]), rec["session"]]))' \
    "${WORK}/scratch/${SESSION}/events.jsonl"
}

check_confirm() {
  local style="$1" dir="$2" cmd="$3" eco="$4" registry="$5" date="$6" confirm
  run_bare "$style" "$dir" "$cmd"
  assert_within 60
  [[ "$status" == 4 ]] || flunk "want the refusal first"
  confirm="$(pyj 'import json, sys; print(json.load(sys.stdin)["confirm"])')"
  [[ "$confirm" == "package-guard --yes -- ${cmd}" ]] || flunk "confirm: $confirm"
  run_bare "$style" "$dir" "$confirm"
  assert_within 120
  [[ "$status" == 0 ]] || flunk "the confirm did not proceed (want the installer's exit 0)"
  [[ "$(recorded_override)" == "tl-fresh|too-new|${date}|${registry}|${eco}|${cmd}|0|${SESSION}" ]] ||
    flunk "the session's event line does not carry the override: $(recorded_override 2>&1)"
}

check_pip_confirm() {
  local date
  date="$(standin_released pypi tl-fresh 1.1.0)"
  check_confirm "$1" "$WORK" "pip install tl-fresh" pypi "$STANDIN_SIMPLE" "$date"
  [[ "$(exec_plain sh -c 'cat "$1"/home/.local/lib/python3.*/site-packages/tl_fresh/__init__.py' s "$WORK")" == *'VERSION = "1.1.0"'* ]] ||
    flunk "not installed into the cell's user site"
}

@test "SC-4 [bash -c, notty] bare pip: the refusal's confirm proceeds, installs, and the session event line records the override" {
  check_pip_confirm c
}

@test "SC-4 [bash -lc, notty] bare pip: the refusal's confirm proceeds, installs, and the session event line records the override" {
  check_pip_confirm lc
}

@test "SC-4 [bash -ic, notty] bare pip: the refusal's confirm proceeds, installs, and the session event line records the override" {
  check_pip_confirm ic
}

@test "SC-4 [a bash script, notty] bare pip: the refusal's confirm proceeds, installs, and the session event line records the override" {
  check_pip_confirm script
}

@test "SC-4 [bash -c, notty] bare npm: the refusal's confirm proceeds, installs, and the session event line records the override" {
  local date
  date="$(standin_released npm tl-fresh 1.1.0)"
  check_confirm c "${WORK}/np" "npm install tl-fresh" npm "$STANDIN_NPM" "$date"
  [[ "$(exec_plain cat "${WORK}/np/node_modules/tl-fresh/index.js")" == *'tl-fresh@1.1.0'* ]] || flunk "not installed"
}

@test "SC-4 [bash -c, notty] --yes over nothing refused records no override" {
  run_bare c "$WORK" "package-guard --yes -- pip install tl-old"
  assert_within 120
  [[ "$status" == 0 ]] || flunk "want pip's exit 0"
  [[ -z "$(exec_plain sh -c 'ls "$1"/scratch/*/package-guard/override-*.json 2>/dev/null' s "$WORK")" ]] ||
    flunk "an override record was written though nothing was refused"
  [[ "$(exec_plain grep -c '"override"' "${WORK}/scratch/${SESSION}/events.jsonl")" == 0 ]] ||
    flunk "an event line carries an override though nothing was refused"
}
