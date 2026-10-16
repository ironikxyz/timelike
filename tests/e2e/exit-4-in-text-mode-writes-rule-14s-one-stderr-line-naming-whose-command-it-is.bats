#!/usr/bin/env bats
# Feature 004 slice 1, FOR-MENTOR Item 14 (b) (spec FR-38; plan's ruling, 2026-10-16: rule 14 applied to exit 4, a
# clarification): under --text a refusal writes rule 14's one line on stderr, naming the operator and the
# envelope's own extend command; stdout is the same envelope as under --json; --json adds nothing on stderr.
# The refusal is Adele's, under the grant `deny`. No time is asserted: spread (lane.conf needs no line).

load helpers

GRANT=deny

setup_file() {
  stamp_check
  stamp_check_adele
}

# refuse STYLE MODE NAME PORT — one refused request from the agent; prints stdout, a `stderr_lines=N rc=R`
# line, then stderr; status = rc.
refuse() {
  local style="$1" mode="$2" name="$3" port="$4"
  run_in -e TIMELIKE_SESSION=x4-line "$style" notty \
    "o=\$(mktemp); e=\$(mktemp); adele ${mode} request standin.box create --grant ${GRANT} --name ${name} --ttl 30m --port ${port} >\"\$o\" 2>\"\$e\"; rc=\$?; cat \"\$o\"; echo \"stderr_lines=\$(wc -l <\"\$e\") rc=\$rc\"; cat \"\$e\"; command rm -f \"\$o\" \"\$e\"; exit \$rc"
}

ledger_id_of() { printf '%s' "$1" | grep -oE '"ledger_id": [0-9]+' | grep -oE '[0-9]+' | head -1; }

@test "Item 14 (b) 004 under --text a refusal writes rule 14's one stderr line naming the operator; stdout is the --json envelope; --json adds nothing [bash -c]" {
  local text_out json_out id i
  refuse c --text t-line 22
  [[ "$status" -eq 4 ]] || { echo "the --text refusal exited $status: $output" >&2; return 1; }
  text_out="${lines[0]}"
  id="$(ledger_id_of "$text_out")"
  [[ "${lines[1]}" == "stderr_lines=1 rc=4" ]] || { echo "stderr is not one line under --text: $output" >&2; return 1; }
  [[ "${lines[2]}" == "error: beyond grant ${GRANT}: ports allows 8080, needs 22; nothing was performed (code 4) — only the operator can extend it: docker exec timelike-adele adeled extend ${GRANT} ports 22; ledger #${id}" ]] ||
    { echo "the stderr line: ${lines[2]}" >&2; return 1; }

  refuse c --json t-line 22
  [[ "$status" -eq 4 && "${lines[1]}" == "stderr_lines=0 rc=4" && "${#lines[@]}" -eq 2 ]] ||
    { echo "under --json stderr is not empty: $output" >&2; return 1; }
  json_out="${lines[0]}"
  # The same envelope, but for the ledger row each refusal made.
  i="$(ledger_id_of "$json_out")"
  [[ "${text_out/\"ledger_id\": ${id}/\"ledger_id\": ${i}}" == "$json_out" ]] ||
    { printf 'stdout differs between --text and --json beyond ledger_id:\n%s\n%s\n' "$text_out" "$json_out" >&2; return 1; }
}
