#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# shellcheck disable=SC2030,SC2031 # bats runs each @test in its own subshell by design
# Feature 13 slice 1 — the failures slice 1 owns, which no criterion line names alone (spec Scenario 9, FR-16, FR-18,
# FR-19, FR-21, FR-22, FR-24, FR-30; research R12, R13, R15, R16). One project per failure, each asking for it and
# nothing else (cross-stack P005). For each: the exit code, the cause named in rule 14's one stderr line with nothing on
# stdout, and, read from the daemon by the runner (cross-stack P004), nothing labelled with the environment where
# nothing is to be created:
#   - a devcontainer.json that does not parse: exit 2, naming its line, counted in the original text (comments kept);
#   - initializeCommand and features: exit 2, naming the setting;
#   - a compose build's secrets, and a Dockerfile RUN mounting a secret: exit 2, naming build secrets;
#   - a base image not on the daemon: exit 3, naming the operator's docker pull, and still no such image afterwards;
#   - a build step that fails: exit 1, naming the step, and no image left;
#   - a lifecycle command that fails: exit 1, naming the command and `adele env down NAME`, and the environment still up.
# Not tested here: a build or lifecycle command past its bound (5 min and 120 s; 124), which would measure the
# machine for minutes. exec into what does not exist is in criterion 7's file.

load helpers
load nested

setup_file() {
  stamp_check
  stamp_check_adele
}

teardown() { nested_teardown; }

# up_split — `adele --text env up` in the cell's project, its exit, stdout and stderr kept apart: lines[0] is rc=N,
# lines[1] is stdout= (and what stdout held), the rest is stderr.
up_split() {
  RUN_TIMEOUT="$PLUMBING_TIMEOUT" run_in -w "$NP_DIR" c notty \
    "out=\$(adele --text env up --project ${NP_NAME} --grant nested 2>/tmp/tl-err-${NP_NAME}); rc=\$?; printf 'rc=%s\nstdout=%s\n' \"\$rc\" \"\$out\"; cat /tmp/tl-err-${NP_NAME}; command rm -f /tmp/tl-err-${NP_NAME}"
}

# check_failed CODE PREFIX — up exits CODE with nothing on stdout and one stderr line starting PREFIX (ERR_LINE).
check_failed() {
  up_split
  [[ "${lines[0]}" == "rc=$1" ]] || { echo "want exit $1; got: $output" >&2; return 1; }
  [[ "${lines[1]}" == stdout= ]] || { echo "stdout is not empty: $output" >&2; return 1; }
  [[ ${#lines[@]} -eq 3 ]] || { echo "stderr is not one line: $output" >&2; return 1; }
  ERR_LINE="${lines[2]}"
  [[ "$ERR_LINE" == "$2"* ]] || { echo "rule 14's line: ${ERR_LINE} (want it to start: $2)" >&2; return 1; }
}

# check_setting SETTING — refused with exit 2 naming SETTING, nothing created, and a refused ledger row naming it.
check_setting() {
  check_failed 2 "error: $1 is not allowed (code 2) — no grant allows it; "
  nested_gone "$NP_NAME"
  run ledger_rows_for "$NP_NAME"
  assert_status 0
  [[ "$output" == refused$'\t'up$'\t'"$1"$'\t'* ]] || { echo "ledger: $output" >&2; return 1; }
}

devcontainer() { nested_write .devcontainer/devcontainer.json "$1"; }

@test "13 a devcontainer.json that does not parse is exit 2 naming the line at fault, nothing created" {
  nested_project dc-parse
  # Line 5 is at fault: the block comment over lines 2 and 3 is blanked, never removed, so lines keep their numbers.
  devcontainer '{
  /* a block comment
     over two lines */
  "image": "'"${DEBIAN_IMAGE}"'",
  "name": "broken" "here",
}'
  check_failed 2 "error: devcontainer.json line 5: "
  [[ "$ERR_LINE" == *" (code 2) — "* ]] || { echo "rule 14's line: ${ERR_LINE}" >&2; return 1; }
  nested_gone "$NP_NAME"
}

@test "13 a devcontainer's initializeCommand is refused with exit 2 naming it, nothing created" {
  nested_project dc-init
  devcontainer '{"image": "'"${DEBIAN_IMAGE}"'", "initializeCommand": "echo on the host"}'
  check_setting initializeCommand
  [[ "$ERR_LINE" == *"initializeCommand runs on the host"* ]] || { echo "rule 14's line: ${ERR_LINE}" >&2; return 1; }
}

@test "13 a devcontainer's features are refused with exit 2 naming features, nothing created" {
  nested_project dc-features
  devcontainer '{"image": "'"${DEBIAN_IMAGE}"'", "features": {"ghcr.io/devcontainers/features/go:1": {}}}'
  check_setting features
}

@test "13 a compose build's secrets are refused with exit 2 naming build secrets, nothing built" {
  nested_project b-secrets
  nested_write Dockerfile "FROM ${DEBIAN_IMAGE}"
  nested_write token.txt 'not a secret: a fixture'
  nested_compose 'services:
  app:
    build:
      context: .
      secrets: [token]
    command: ["sleep", "infinity"]
secrets:
  token:
    file: ./token.txt'
  check_setting "build secrets"
  [[ "$ERR_LINE" == *"(service app: "* ]] || { echo "rule 14's line: ${ERR_LINE}" >&2; return 1; }
}

@test "13 a Dockerfile RUN mounting a secret is refused with exit 2 naming build secrets, nothing built" {
  nested_project b-mount
  nested_write Dockerfile "FROM ${DEBIAN_IMAGE}
RUN --mount=type=secret,id=x true"
  nested_compose 'services:
  app:
    build: .
    command: ["sleep", "infinity"]'
  check_setting "build secrets"
  [[ "$ERR_LINE" == *"--mount=type=secret"* ]] || { echo "rule 14's line: ${ERR_LINE}" >&2; return 1; }
}

@test "13 a base image not on the daemon is exit 3 naming the operator's docker pull, and nothing is pulled" {
  nested_project b-nobase
  run docker image inspect timelike-absent-base:never
  [[ "$status" != 0 ]] || { echo "the daemon already has timelike-absent-base:never" >&2; return 1; }
  nested_write Dockerfile 'FROM timelike-absent-base:never
RUN true'
  nested_compose 'services:
  app:
    build: .
    command: ["sleep", "infinity"]'
  check_failed 3 "error: base image timelike-absent-base:never is not on the daemon, and a build pulls nothing"
  [[ "$ERR_LINE" == *"(code 3) — the operator pulls it on the host: docker pull timelike-absent-base:never; the agent cannot"* ]] ||
    { echo "rule 14's line: ${ERR_LINE}" >&2; return 1; }
  nested_gone "$NP_NAME"
  run ! docker image inspect timelike-absent-base:never
  run ledger_rows_for "$NP_NAME"
  assert_status 0
  [[ "$output" == refused$'\t'up$'\t'FROM$'\t''docker pull timelike-absent-base:never'$'\t'* ]] || { echo "ledger: $output" >&2; return 1; }
}

@test "13 a build step that fails is exit 1 naming the step, and nothing is left" {
  nested_project b-step
  nested_write Dockerfile "FROM ${DEBIAN_IMAGE}
RUN false"
  nested_compose 'services:
  app:
    build: .
    command: ["sleep", "infinity"]'
  # Lane 13s1a: the instruction and its position in the Dockerfile, never the daemon's "Step N/M" (its M counts the
  # LABEL steps it adds for Adele's labels), and that step's own output rather than the build's whole log.
  check_failed 1 "error: ${NP_NAME}: build of app failed at instruction 2 of the Dockerfile, RUN false: "
  [[ "$ERR_LINE" == *"RUN false: The command '"*"' returned a non-zero code: 1 (code 1) — nothing was created; "* ]] ||
    { echo "rule 14's line: ${ERR_LINE}" >&2; return 1; }
  [[ "$ERR_LINE" != *"Step "* && "$ERR_LINE" != *"--->"* ]] || { echo "the daemon's log in the verdict: ${ERR_LINE}" >&2; return 1; }
  nested_gone "$NP_NAME"
}

@test "13 a lifecycle command that fails is exit 1 naming it, the environment stays up, and the remedy is down" {
  local c
  nested_project dc-life
  devcontainer '{
  "image": "'"${DEBIAN_IMAGE}"'",
  "postCreateCommand": "echo about to fail; exit 4",
  "postStartCommand": "echo not reached",
}'
  check_failed 1 "error: ${NP_NAME}: lifecycle command postCreateCommand exited 4 (last lines: about to fail) (code 1)"
  [[ "$ERR_LINE" == *" — the environment stays up; remove it with adele env down ${NP_NAME}" ]] ||
    { echo "rule 14's line: ${ERR_LINE}" >&2; return 1; }
  # Still a performed environment: its container is running, read back from the daemon, and the ledger has it.
  c="$(nested_container "$NP_NAME" devcontainer)"
  [[ -n "$c" && "$(docker inspect --format '{{.State.Status}}' "$c")" == running ]] ||
    { echo "the devcontainer is not running: '${c}' $(nested_counts "$NP_NAME")" >&2; return 1; }
  run ledger_rows_for "$NP_NAME"
  assert_status 0
  [[ "${lines[0]}" == performed$'\t'up$'\t'* ]] || { echo "ledger: $output" >&2; return 1; }
}
