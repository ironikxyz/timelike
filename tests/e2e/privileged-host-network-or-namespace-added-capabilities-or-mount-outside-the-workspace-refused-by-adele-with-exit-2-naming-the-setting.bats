#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# shellcheck disable=SC2030,SC2031 # bats runs each @test in its own subshell by design
# Feature 13 slice 0, criterion 3 (revision 17) — "A request for a privileged container, host networking or process
# namespace, added capabilities, or a mount outside the workspace is refused by Adele with exit 2 and rule 14's
# structured error, naming the setting and stating that no grant allows it, without an operator's command;
# nothing is created" (send 13-rev17; spec FR-8; research R3). The struck exit-4 reading is not tested.
#
# One fixture per setting, each asking for it and nothing else (cross-stack P005: the refusal of each dangerous
# setting is shown with a project that asks for it). For each:
#   - exit 2, nothing on stdout, and stderr is rule 14's one line:
#     error: <setting> is not allowed (code 2) — no grant allows it; <how to change the request> (service S: …)
#     with no operator's command in it;
#   - nothing labelled with the environment exists on the daemon, read from the runner;
#   - Adele's ledger holds a refused row naming the setting, with no extend command.
# The neighbours Item 27 Q1 accepted are refused the same way: a device, the Docker socket, a volume's driver
# options binding a host path, a link out of the workspace, and an env_file outside it (the resolution sandbox
# cannot see it, so Adele's secret is never read).

load helpers
load nested

setup_file() {
  stamp_check
  stamp_check_adele
}

teardown() { nested_teardown; }

# refused CELL SETTING STYLE COMPOSE — bring up a project asking for SETTING and check the refusal.
refused() {
  nested_project "$1"
  nested_compose "$4"
  check_refused "$2" "$3"
}

# check_refused SETTING STYLE — bring up the cell's project as it stands and check the refusal.
check_refused() {
  local setting="$1" style="$2"
  RUN_TIMEOUT="$PLUMBING_TIMEOUT" run_in -w "$NP_DIR" "$style" notty \
    "out=\$(adele --text env up --project ${NP_NAME} --grant nested 2>/tmp/tl-err-${NP_NAME}); rc=\$?; printf 'rc=%s\nstdout=%s\n' \"\$rc\" \"\$out\"; cat /tmp/tl-err-${NP_NAME}; command rm -f /tmp/tl-err-${NP_NAME}"
  [[ "${lines[0]}" == rc=2 ]] || { echo "want exit 2; got: $output" >&2; return 1; }
  [[ "${lines[1]}" == stdout= ]] || { echo "stdout is not empty: $output" >&2; return 1; }
  [[ ${#lines[@]} -eq 3 ]] || { echo "stderr is not one line: $output" >&2; return 1; }
  [[ "${lines[2]}" == "error: ${setting} is not allowed (code 2) — no grant allows it; "* ]] ||
    { echo "rule 14's line: ${lines[2]}" >&2; return 1; }
  [[ "${lines[2]}" != *"docker exec"* && "${lines[2]}" != *"adeled"* && "${lines[2]}" != *"operator"* ]] ||
    { echo "names an operator's command: ${lines[2]}" >&2; return 1; }
  [[ "$(nested_counts "$NP_NAME")" == "0 0 0" ]] || { echo "created: $(nested_counts "$NP_NAME")" >&2; return 1; }
  run ledger_rows_for "$NP_NAME"
  assert_status 0
  [[ "$output" == refused$'\t'up$'\t'"${setting}"$'\t'$'\t'* ]] ||
    { echo "ledger: $output" >&2; return 1; }
}

svc() { printf 'services:\n  app:\n    image: ${FIXTURE_IMAGE:?}\n    command: ["sleep", "infinity"]\n%s\n' "$1"; }

@test "13 privileged is refused by Adele with exit 2 naming the setting, nothing created [bash -c]" {
  refused priv-c privileged c "$(svc '    privileged: true')"
}
@test "13 privileged is refused by Adele with exit 2 naming the setting, nothing created [bash -lc]" {
  refused priv-lc privileged lc "$(svc '    privileged: true')"
}
@test "13 host networking is refused with exit 2 naming network_mode" {
  refused netmode network_mode c "$(svc '    network_mode: host')"
}
@test "13 the host's pid namespace is refused with exit 2 naming pid" {
  refused pid pid c "$(svc '    pid: host')"
}
@test "13 the host's ipc namespace is refused with exit 2 naming ipc" {
  refused ipc ipc c "$(svc '    ipc: host')"
}
@test "13 an added capability is refused with exit 2 naming cap_add" {
  refused capadd cap_add c "$(svc '    cap_add: [NET_ADMIN]')"
}
@test "13 a bind mount from outside the workspace is refused with exit 2 naming volumes" {
  refused bindetc volumes c "$(svc '    volumes: ["/etc:/host-etc:ro"]')"
}
@test "13 the Docker socket as a mount is refused with exit 2 naming volumes" {
  refused sock volumes c "$(svc '    volumes: ["/var/run/docker.sock:/var/run/docker.sock"]')"
}
@test "13 a device is refused with exit 2 naming devices" {
  refused dev devices c "$(svc '    devices: ["/dev/kvm:/dev/kvm"]')"
}
@test "13 a volume whose driver options bind a host path is refused with exit 2 naming volumes" {
  refused drvopts volumes c "$(svc '    volumes: [hostbind:/data]')
volumes:
  hostbind:
    driver_opts: {type: none, o: bind, device: /etc}"
}
@test "13 a link inside the workspace that points out of it is refused with exit 2 naming volumes" {
  nested_project link
  exec_plain ln -s /etc "${NP_DIR}/out"
  nested_compose "$(svc '    volumes: ["./out:/host-etc:ro"]')"
  check_refused volumes c
}
@test "13 an env_file outside the workspace is refused with exit 2 naming env_file, and Adele's secret is not read" {
  refused envfile env_file c "$(svc '    env_file: [/run/adele-secret/canary]')"
}

@test "13 a forbidden setting under --json is one JSON object on stderr naming it, nothing on stdout" {
  nested_project json
  nested_compose "$(svc '    privileged: true')"
  RUN_TIMEOUT="$PLUMBING_TIMEOUT" run_in -w "$NP_DIR" c notty \
    "out=\$(adele --json env up --project ${NP_NAME} --grant nested 2>/tmp/tl-err-${NP_NAME}); rc=\$?; printf 'rc=%s\nstdout=%s\n' \"\$rc\" \"\$out\"; cat /tmp/tl-err-${NP_NAME}; command rm -f /tmp/tl-err-${NP_NAME}"
  [[ "${lines[0]}" == rc=2 && "${lines[1]}" == stdout= ]] || { echo "$output" >&2; return 1; }
  printf '%s' "${lines[2]}" | pyq "
import json, sys
d = json.load(sys.stdin)
assert d['code'] == 2 and d['error'] == 'privileged is not allowed', d
assert d['remediation'].startswith('no grant allows it; '), d
assert 'docker exec' not in json.dumps(d), d
"
  [[ "$(nested_counts "$NP_NAME")" == "0 0 0" ]]
}
