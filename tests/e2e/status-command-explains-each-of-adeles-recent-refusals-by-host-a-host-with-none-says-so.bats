#!/usr/bin/env bats
# SC-8, feature 004 slice 1 (prompt 12 revision 16; spec FR-35 to FR-37, D-15): "A status command explains each of
# Adele's recent refusals by host, naming the grant and limit, what was allowed and what was needed, the operator's
# command, and where the record lives; a host with none says so".
#   - `adele status HOST` (the agent's, run from the agent's container: cross-stack P001) and `adeled status HOST`
#     (the operator's) explain each recent refusal of HOST: when, the grant and limit, allowed and needed, the
#     operator's command, the ledger row; the verdict names where the record lives; a host with none says so;
#     several are listed newest first, with a count.
#
# The refusals are Adele's, under the grant `deny` (ports 8080 only, never extended). The agent's own outbound
# connections are not filtered until slice 2 (plan's ruling on Item 26), so nothing here concerns them. Other
# files' refusals reach the same host (the stand-in), so cells find their own by ledger id and never count the
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

@test "SC-8 004 the agent's adele status HOST says so when HOST has no recent denial [bash -c]" {
  run_in c notty 'adele --json status nobody.invalid:1'
  [[ "$status" -eq 0 ]] || { echo "adele status exited $status: $output" >&2; return 1; }
  assert_output_has "no denial of nobody.invalid:1 in 24 h · record: adeled ledger"
  assert_output_has "Adele's ledger, which the operator reads with: docker exec timelike-adele adeled ledger"
  assert_output_has "\"denials\": []"
}

@test "SC-8 004 the agent's adele status HOST explains several recent denials, newest first, with the operator's command [bash -lc]" {
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

@test "SC-8 004 the operator's adeled status HOST explains the same denials, with Adele's revision" {
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
