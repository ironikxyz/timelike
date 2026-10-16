#!/usr/bin/env bats
# Feature 004 slice 1: the status command (spec FR-35 to FR-37, D-15) and Item 14 (b)'s line (FR-38; plan's
# ruling, 2026-10-16), end to end in the agent container.
#   - `adele status HOST` (the agent's) and `adeled status HOST` (the operator's) explain each recent denial
#     of HOST: when, the policy (grant and limit, allowed and needed), the operator's command, the ledger
#     row; none is said in so many words; several are listed newest first.
#   - A refusal under --text writes rule 14's one line on stderr, naming the operator and the envelope's own
#     extend command; stdout is the same envelope as under --json; --json adds nothing on stderr.
#
# The denials here are Adele's grant refusals, under the grant `deny` (ports 8080 only, never extended). What
# else counts as a denial in slice 1 is FOR-MENTOR Item 26; nothing here depends on its answer. Other files'
# refusals reach the same host (the stand-in), so cells find their own by ledger id and never count the
# host's total. No time is asserted: spread (lane.conf needs no line).

load helpers

GRANT=deny
HOST=adele-standin:8481

setup_file() {
  stamp_check
  stamp_check_adele
}

# refuse STYLE MODE NAME PORT — one refused request from the agent; prints stdout, a `stderr_lines=N rc=R`
# line, then stderr; status = rc.
refuse() {
  local style="$1" mode="$2" name="$3" port="$4"
  run_in -e TIMELIKE_SESSION=sc8-status -e TIMELIKE_AGENT=agent-s "$style" notty \
    "o=\$(mktemp); e=\$(mktemp); adele ${mode} request standin.box create --grant ${GRANT} --name ${name} --ttl 30m --port ${port} >\"\$o\" 2>\"\$e\"; rc=\$?; cat \"\$o\"; echo \"stderr_lines=\$(wc -l <\"\$e\") rc=\$rc\"; cat \"\$e\"; rm -f \"\$o\" \"\$e\"; exit \$rc"
}

ledger_id_of() { printf '%s' "$1" | grep -oE '"ledger_id": [0-9]+' | grep -oE '[0-9]+' | head -1; }

@test "status 004 the agent's adele status HOST says so when HOST has no recent denial [bash -c]" {
  run_in c notty 'adele --json status nobody.invalid:1'
  [[ "$status" -eq 0 ]] || { echo "adele status exited $status: $output" >&2; return 1; }
  assert_output_has "no denial of nobody.invalid:1 in 24 h · record: adeled ledger"
  assert_output_has "Adele's ledger, which the operator reads with: docker exec timelike-adele adeled ledger"
  assert_output_has "\"denials\": []"
}

@test "status 004 the agent's adele status HOST explains several recent denials, newest first, with the operator's command [bash -lc]" {
  local first second
  refuse lc --json t-status-a 22
  [[ "$status" -eq 4 ]] || { echo "the first refusal exited $status: $output" >&2; return 1; }
  first="$(ledger_id_of "$output")"
  refuse lc --json t-status-b 23
  [[ "$status" -eq 4 ]] || { echo "the second refusal exited $status: $output" >&2; return 1; }
  second="$(ledger_id_of "$output")"
  [[ -n "$first" && -n "$second" ]] || { echo "no ledger ids: ${first:-?} ${second:-?}" >&2; return 1; }

  run_in lc notty "adele --text status ${HOST}"
  [[ "$status" -eq 0 ]] || { echo "adele status exited $status: $output" >&2; return 1; }
  [[ "${lines[0]}" == "adele: adele [status]" ]] || { echo "header: ${lines[0]}" >&2; return 1; }
  assert_output_has "denials of ${HOST} in 24 h (≤20/host) · record: adeled ledger"
  local a b i
  for i in "${!lines[@]}"; do
    [[ "${lines[$i]}" == "#${first} "* ]] && a=$i
    [[ "${lines[$i]}" == "#${second} "* ]] && b=$i
  done
  [[ -n "${a:-}" && -n "${b:-}" ]] || { echo "the two denials #${first} and #${second} are not both listed: $output" >&2; return 1; }
  ((b < a)) || { echo "not newest first: #${second} at line ${b}, #${first} at line ${a}" >&2; return 1; }
  [[ "${lines[$b]}" == *"${HOST}: grant ${GRANT}, ports allows 8080, needed 23 — only the operator allows it: docker exec timelike-adele adeled extend ${GRANT} ports 23 (session sc8-status, agent agent-s)" ]] ||
    { echo "the newest denial's line: ${lines[$b]}" >&2; return 1; }
}

@test "status 004 the operator's adeled status HOST explains the same denials, with Adele's revision" {
  refuse c --json t-status-op 24
  [[ "$status" -eq 4 ]] || { echo "the refusal exited $status: $output" >&2; return 1; }
  local id
  id="$(ledger_id_of "$output")"
  run adeled status "$HOST"
  [[ "$status" -eq 0 ]] || { echo "adeled status exited $status: $output" >&2; return 1; }
  [[ "${lines[0]}" == "Adele revision ${GIT_SHA} · reaper: "*" · the record: adeled ledger" ]] || { echo "verdict: ${lines[0]}" >&2; return 1; }
  assert_output_has "#${id} "
  assert_output_has "${HOST}: grant ${GRANT}, ports allows 8080, needed 24 — the operator allows it: docker exec timelike-adele adeled extend ${GRANT} ports 24 (session sc8-status, agent agent-s)"
}

@test "exit-4 004 under --text a refusal writes rule 14's one stderr line naming the operator; stdout is the --json envelope; --json adds nothing [bash -c]" {
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
