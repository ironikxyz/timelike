#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# SC-5 — "The tool's exit code equals the wrapped command's exit code". This covers 0, 1, 42, 127
# (not found), 126 (not executable) and 137 (killed by SIGKILL). (Feature 003, slice 0; spec FR-17,
# FR-18, Scenario 4; contracts/run-cli.md § Exit; research R7.)
#
# Each case runs `run COMMAND` as the whole command string, with no wrapper, so the status bats sees is
# the one docker exec reports: the shell's, which is run's. Nothing echoes it back as text.
# The JSON cases read the result as data (fixtures/json_fields.py): `exit`, `cause` and `command_exit`
# must agree with the code, and the verdict must name it in words (Scenario 4.3).
# FR-1 / R7: `type -a run` resolves to exactly one file, /opt/timelike/bin/run, so `run` shadows
# nothing and nothing shadows it, under both styles (/etc/profile resets PATH under -lc, R1).
# Cells: bash -c and bash -lc in `notty`; a terminal does not change an exit code.

load helpers

setup_file() {
  stamp_check
  copy_into_container "${BATS_TEST_DIRNAME}/fixtures/json_fields.py" /tmp/json_fields.py
}

setup() {
  WORK="$(container_tmpdir sc5run)"
}

teardown() {
  container_rm "$WORK"
}

# check_exit STYLE EXPECTED COMMAND — `run COMMAND` exits EXPECTED.
check_exit() {
  run_in "$1" notty "run $3"
  assert_within 20
  assert_status "$2"
}

# check_not_executable STYLE — a file that exists but lacks the execute bit: 126, as the shell gives.
check_not_executable() {
  local f="${WORK}/not-executable.sh"
  # If it ran anyway, it would leave a marker beside itself.
  exec_plain sh -c 'printf "%s\n" "#!/bin/sh" ": > \"$2\"" > "$1" && chmod 0644 "$1"' put "$f" "${WORK}/ran"
  check_exit "$1" 126 "'${f}'"
  run exec_plain test -e "${WORK}/ran"
  [[ "$status" -ne 0 ]] || { echo "the non-executable file ran" >&2; return 1; }
}

# check_json STYLE CODE COMMAND VERDICT_TEXT — `run --json COMMAND` exits CODE, and its JSON says
# exit CODE, cause "command", command_exit CODE, with VERDICT_TEXT in the verdict string.
check_json() {
  run_in "$1" notty "run --json $3 > '${WORK}/r.json'; rc=\$?; echo \"rc=\$rc\"; \
${AGENT_PY} -I /tmp/json_fields.py '${WORK}/r.json' exit cause command_exit verdict; exit \$rc"
  assert_within 20
  assert_status "$2"
  assert_value rc "$2"
  assert_value json ok
  assert_value exit "$2"
  assert_value cause command
  assert_value command_exit "$2"
  local verdict
  verdict="$(value_of verdict)"
  [[ "$verdict" == *"$4"* ]] || { printf 'verdict lacks %q: %s\n' "$4" "$verdict" >&2; return 1; }
}

# check_type_a STYLE — exactly one `run`, and it is timelike's.
check_type_a() {
  run_in "$1" notty "type -a run"
  assert_within 20
  assert_status 0
  [[ ${#lines[@]} -eq 1 ]] || { printf 'type -a run printed %d lines, want 1:\n%s\n' "${#lines[@]}" "$output" >&2; return 1; }
  [[ "${lines[0]}" == "run is /opt/timelike/bin/run" ]] || { echo "type -a run: ${lines[0]}" >&2; return 1; }
}

# --- exit pass-through, bash -c ---
@test "SC-5 the tool's exit code equals the wrapped command's exit code: true → 0 [bash -c, notty]" { check_exit c 0 true; }
@test "SC-5 the tool's exit code equals the wrapped command's exit code: false → 1 [bash -c, notty]" { check_exit c 1 false; }
@test "SC-5 the tool's exit code equals the wrapped command's exit code: exit 42 → 42 [bash -c, notty]" { check_exit c 42 "sh -c 'exit 42'"; }
@test "SC-5 the tool's exit code equals the wrapped command's exit code: not found → 127 [bash -c, notty]" { check_exit c 127 no-such-command-xyz; }
@test "SC-5 the tool's exit code equals the wrapped command's exit code: not executable → 126 [bash -c, notty]" { check_not_executable c; }
@test "SC-5 the tool's exit code equals the wrapped command's exit code: SIGKILL → 137 [bash -c, notty]" { check_exit c 137 "sh -c 'kill -9 \$\$'"; }

# --- exit pass-through, bash -lc ---
@test "SC-5 the tool's exit code equals the wrapped command's exit code: true → 0 [bash -lc, notty]" { check_exit lc 0 true; }
@test "SC-5 the tool's exit code equals the wrapped command's exit code: false → 1 [bash -lc, notty]" { check_exit lc 1 false; }
@test "SC-5 the tool's exit code equals the wrapped command's exit code: exit 42 → 42 [bash -lc, notty]" { check_exit lc 42 "sh -c 'exit 42'"; }
@test "SC-5 the tool's exit code equals the wrapped command's exit code: not found → 127 [bash -lc, notty]" { check_exit lc 127 no-such-command-xyz; }
@test "SC-5 the tool's exit code equals the wrapped command's exit code: not executable → 126 [bash -lc, notty]" { check_not_executable lc; }
@test "SC-5 the tool's exit code equals the wrapped command's exit code: SIGKILL → 137 [bash -lc, notty]" { check_exit lc 137 "sh -c 'kill -9 \$\$'"; }

# --- the JSON result carries the same code, with cause "command" ---
@test "SC-5 the tool's exit code equals the wrapped command's exit code: JSON exit 42, cause command, command_exit 42 [bash -c, notty]" { check_json c 42 "sh -c 'exit 42'" "command exited 42"; }
@test "SC-5 the tool's exit code equals the wrapped command's exit code: JSON exit 42, cause command, command_exit 42 [bash -lc, notty]" { check_json lc 42 "sh -c 'exit 42'" "command exited 42"; }
@test "SC-5 the tool's exit code equals the wrapped command's exit code: JSON not found is 127 with cause command [bash -c, notty]" { check_json c 127 no-such-command-xyz "command not found: no-such-command-xyz"; }
@test "SC-5 the tool's exit code equals the wrapped command's exit code: JSON SIGKILL is 137 with cause command [bash -c, notty]" { check_json c 137 "sh -c 'kill -9 \$\$'" "command killed by signal 9"; }

# --- FR-1 / R7: one run on PATH, never shadowed ---
@test "SC-5 type -a run resolves to exactly /opt/timelike/bin/run [bash -c, notty]" { check_type_a c; }
@test "SC-5 type -a run resolves to exactly /opt/timelike/bin/run [bash -lc, notty]" { check_type_a lc; }
