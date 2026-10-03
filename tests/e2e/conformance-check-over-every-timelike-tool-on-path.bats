#!/usr/bin/env bats
# SC-5 — "A conformance check runs against every timelike tool on PATH. It fails when any tool lacks
# any of: --help within 40 lines, --json, --agent-info, the exit-code vocabulary, a self-labelling
# first line, or a session event per invocation." (tasks.md T030; spec FR-9, FR-14;
# contracts/conformance.md.)
#
# In the image, from outside (lore cross-stack P005):
#   1. timelike-conform exits 0 over the shipped PATH, and the number of tools it checked equals the
#      number of executables actually in /opt/timelike/bin (read directly), at least 3
#      (timelike, timelike-conform itself and, since feature 003, run). run declares passes_exit, so
#      conform also runs it wrapping `sh -c 'exit 42'` (C6, discovery revision 9): a pass here
#      includes that exercise.
#   2. With the deliberately broken fixture tests/fixtures/bad-tool/timelike-bad added to PATH and
#      TIMELIKE_BIN_DIRS, it exits 1 and names timelike-bad with C1, C5 and C7 — the check can fail.
#   3. timelike --agent-info carries the revision the image was built from (FR-14, H8).
# conform probes every tool several times, so its runs get a 60 s runner limit instead of 30.
# Only formats fixed by contracts/conformance.md are asserted: the text line
# `FAIL <tool> C<n> <check>: ...` and the JSON keys verdict / checked / failures.
#
# Common failures (slice 1, natural intensity; modify.md F005; tasks.md T053). What a real user gets
# wrong when placing a new tool on PATH (Scenario 5) is its interpreter, not a subtle contract rule —
# the subtle rules are each already shown failing in tests/unit/test_conform_violations.py (C1–C9),
# and a tool that never concludes in tests/unit/test_conform.py, so neither is repeated here:
#   4. fixtures/timelike-envpython: `#!/usr/bin/env python3`, the everyday shebang. The image has no
#      python3 on PATH (H5), so every probe exits 127. conform must exit 1 naming the tool with C1
#      (help) and C6 (127 is outside the exit vocabulary), and still pass the shipped tools.
#   5. fixtures/timelike-nointerp: an absolute shebang to an interpreter that does not exist, so exec
#      itself fails (ENOENT) before the tool runs. Same expectation. This was a PRODUCT GAP, found by T053
#      and reproduced on the host lane: timelike-conform did not catch the exec failure (run_probe
#      called subprocess.Popen unguarded), crashed with "error: internal error: FileNotFoundError",
#      named no tool or rule and dropped every other tool's verdict. Fixed in T059: an exec failure
#      is now that tool's probe result (127 not found, 126 not executable), judged like any other.
# Cells: bash -c and bash -lc in `notty`. conform detaches every probe from the terminal
# (start_new_session), so a terminal changes nothing for a tool that cannot even start; the happy
# path above already runs conform under `tty`.

load helpers

setup_file() {
  stamp_check
  copy_into_container "${BATS_TEST_DIRNAME}/fixtures/json_fields.py" /tmp/json_fields.py
}

setup() {
  WORK="$(container_tmpdir sc5)"
}

teardown() {
  kill_strays
  container_rm "$WORK"
}

check_conform_passes_over_shipped_path() {
  RUN_TIMEOUT=60 run_in "$1" "$2" "timelike-conform --json > '${WORK}/conform.json'; echo \"rc=\$?\"; \
${AGENT_PY} -I /tmp/json_fields.py '${WORK}/conform.json' tool verdict checked failures; \
echo \"shipped=\$(find /opt/timelike/bin -maxdepth 1 -type f -perm -u+x | wc -l)\""
  assert_within 60
  assert_status 0
  assert_value rc 0
  assert_value json ok
  assert_value tool timelike-conform
  assert_value verdict pass
  assert_value 'failures#' 0
  local checked shipped
  checked="$(value_of checked)"
  shipped="$(value_of shipped)"
  [[ "$checked" =~ ^[0-9]+$ && "$checked" -ge 3 ]] || { echo "checked '$checked' tools, want >= 3" >&2; return 1; }
  [[ "$checked" == "$shipped" ]] ||
    { echo "checked $checked tools but /opt/timelike/bin holds $shipped executables: not every tool on PATH was checked" >&2; return 1; }
}

check_conform_fails_naming_bad_tool() {
  local bad="${WORK}/badbin"
  exec_plain mkdir -p "$bad"
  copy_into_container "${BATS_TEST_DIRNAME}/../fixtures/bad-tool/timelike-bad" "${bad}/timelike-bad" 0755
  RUN_TIMEOUT=60 run_in "$1" "$2" "PATH='${bad}':\"\$PATH\" TIMELIKE_BIN_DIRS='/opt/timelike/bin:${bad}' timelike-conform --text"
  assert_within 60
  assert_status 1
  local c
  for c in C1 C5 C7; do
    assert_line_matching "^FAIL timelike-bad ${c}[ :]"
  done
  # The shipped tools still pass: the failures belong to the fixture alone.
  assert_no_line_matching '^FAIL timelike(-conform)? '
}

check_agent_info_revision() {
  run_in "$1" "$2" "timelike --agent-info > '${WORK}/info.json'; echo \"rc=\$?\"; \
${AGENT_PY} -I /tmp/json_fields.py '${WORK}/info.json' tool revision"
  assert_within 20
  assert_status 0
  assert_value rc 0
  assert_value json ok
  assert_value tool timelike
  [[ -n "${GIT_SHA:-}" ]] || { echo "GIT_SHA empty" >&2; return 1; }
  assert_value revision "$GIT_SHA"
}

# check_conform_names_broken_interpreter FIXTURE STYLE TTY — FIXTURE (a file in fixtures/) is added
# to PATH and TIMELIKE_BIN_DIRS beside the shipped tools; conform must name it and still judge those.
check_conform_names_broken_interpreter() {
  local tool="$1" bad="${WORK}/badbin"
  exec_plain mkdir -p "$bad"
  copy_into_container "${BATS_TEST_DIRNAME}/fixtures/${tool}" "${bad}/${tool}" 0755
  RUN_TIMEOUT=60 run_in "$2" "$3" "PATH='${bad}':\"\$PATH\" TIMELIKE_BIN_DIRS='/opt/timelike/bin:${bad}' timelike-conform --text --limit 0"
  assert_within 60
  assert_status 1
  assert_no_line_matching '^error: internal error'
  local c
  for c in C1 C6; do
    assert_line_matching "^FAIL ${tool} ${c}[ :]"
  done
  # The broken tool costs its own verdict only: the shipped tools are still checked, and pass.
  assert_line_matching '^ok +timelike$'
  assert_line_matching '^ok +timelike-conform$'
  assert_no_line_matching '^FAIL timelike(-conform)? '
}

# assert_line_matching ERE — some line of $output matches.
assert_line_matching() {
  local line
  for line in "${lines[@]}"; do
    [[ "$line" =~ $1 ]] && return 0
  done
  printf 'no line matches /%s/; output:\n%s\n' "$1" "$output" >&2
  return 1
}

@test "SC-5 conformance check runs against every timelike tool on PATH and passes [bash -c, notty]" { check_conform_passes_over_shipped_path c notty; }
@test "SC-5 conformance check runs against every timelike tool on PATH and passes [bash -c, tty]" { check_conform_passes_over_shipped_path c tty; }
@test "SC-5 conformance check runs against every timelike tool on PATH and passes [bash -lc, notty]" { check_conform_passes_over_shipped_path lc notty; }
@test "SC-5 conformance check runs against every timelike tool on PATH and passes [bash -lc, tty]" { check_conform_passes_over_shipped_path lc tty; }

@test "SC-5 conformance check fails naming the tool and rule: timelike-bad C1 C5 C7 [bash -c, notty]" { check_conform_fails_naming_bad_tool c notty; }
@test "SC-5 conformance check fails naming the tool and rule: timelike-bad C1 C5 C7 [bash -c, tty]" { check_conform_fails_naming_bad_tool c tty; }
@test "SC-5 conformance check fails naming the tool and rule: timelike-bad C1 C5 C7 [bash -lc, notty]" { check_conform_fails_naming_bad_tool lc notty; }
@test "SC-5 conformance check fails naming the tool and rule: timelike-bad C1 C5 C7 [bash -lc, tty]" { check_conform_fails_naming_bad_tool lc tty; }

@test "SC-5 timelike --agent-info carries the build revision [bash -c]" { check_agent_info_revision c notty; }
@test "SC-5 timelike --agent-info carries the build revision [bash -lc]" { check_agent_info_revision lc notty; }

# --- common failures (slice 1): a new tool whose interpreter is missing ---
@test "SC-5 conformance check fails naming the tool and rule: #!/usr/bin/env python3 tool, no python3 on PATH [bash -c, notty]" { check_conform_names_broken_interpreter timelike-envpython c notty; }
@test "SC-5 conformance check fails naming the tool and rule: #!/usr/bin/env python3 tool, no python3 on PATH [bash -lc, notty]" { check_conform_names_broken_interpreter timelike-envpython lc notty; }
# PRODUCT GAP found by T053, fixed in T059: timelike-conform now judges an exec failure — see header item 5.
@test "SC-5 conformance check fails naming the tool and rule: tool whose interpreter path does not exist [bash -c, notty]" { check_conform_names_broken_interpreter timelike-nointerp c notty; }
@test "SC-5 conformance check fails naming the tool and rule: tool whose interpreter path does not exist [bash -lc, notty]" { check_conform_names_broken_interpreter timelike-nointerp lc notty; }
