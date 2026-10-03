#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# shellcheck disable=SC2030,SC2031 # bats runs each @test in its own subshell by design
# SC-3 (feature 004) — "A request within its grant is performed and returns the result; a request
# exceeding any limit exits 4 with an envelope naming the grant, the limit and the operator's extend
# command, and nothing is performed" (send 12-rev2, slice 0; spec FR-10..FR-12, D-4; tasks.md T017).
#
# Under bash -c and bash -lc, against the lane's grant file (tests/e2e/fixtures/adele/grants.conf; one
# grant per limit and style, so no cell's spending reaches another):
#   - within the grant: exit 0, and the box is in the stand-in's OWN record (cross-stack P004)
#   - one refusal per limit (ttl, ports, instances, budget): exit 4, and stdout is exactly the grant
#     envelope (FOR-MENTOR Item 13, discovery revision 10; grant-envelope.schema.json), validated against
#     the schema file, naming the grant, the limit, what it allows and what the request needs, with
#     nothing on stderr; and the stand-in's record does NOT hold the box — "nothing is performed" is
#     checked against the capability, never Adele's word
#   - the operator's extend command, taken from the envelope's `extend` and run EXACTLY as printed, from
#     the host side; then the same request
#     is retried and proceeds (the D8 exchange, automated; the Manual D8 demo stays the operator's)
#   - the agent cannot run that command: it has neither adeled nor docker
# The `capabilities` limit is covered by Go units (adele/internal/broker): slice 0 knows one capability,
# so no grant the parser accepts can refuse it end to end.
#
# The envelope cells (last two) check the envelope itself in both output modes, under the roomy `e2e`
# grant and with no extension, so they spend nothing another cell counts: stdout is one JSON envelope in
# --text and --json alike, `status: grant_required`, `extend_by: operator`, `performed: false`, and no
# `confirm` — an operator's command never sits where the agent's habit runs it (discovery revision 10).
# Validation runs in a throwaway of the agent image's interpreter (pyq) with tests/unit/schema.py, the
# same stdlib validator the units use; the runner reads both files from the read-only repository.

load helpers

setup_file() {
  stamp_check
  stamp_check_adele
}

# request STYLE NAME [--json|--text] ARGS... — one request; prints stdout, then `stderr_bytes=N rc=R`,
# then stderr; status = rc. The mode defaults to --text.
request() {
  local style="$1" name="$2" mode=--text
  shift 2
  if [[ "${1:-}" == --json || "${1:-}" == --text ]]; then
    mode="$1"
    shift
  fi
  run_in "$style" notty "o=\$(mktemp); e=\$(mktemp); adele ${mode} request standin.box create --name ${name} $* >\"\$o\" 2>\"\$e\"; rc=\$?; cat \"\$o\"; echo \"stderr_bytes=\$(wc -c <\"\$e\") rc=\$rc\"; cat \"\$e\"; rm -f \"\$o\" \"\$e\"; exit \$rc"
}

SCHEMA_PY="${BATS_TEST_DIRNAME}/../unit/schema.py"
GRANT_SCHEMA="${BATS_TEST_DIRNAME}/../../.specswarm/features/001-agent-shell-baseline/contracts/grant-envelope.schema.json"

# envelope_ok GRANT LIMIT ALLOWED NEEDED — after `request`: stdout (all of it, before the stderr_bytes
# line) is exactly one grant envelope, valid against grant-envelope.schema.json, naming GRANT, the limit
# and the values; stderr is empty. Leaves the envelope's `extend` in EXTEND. ALLOWED '*' means any.
envelope_ok() {
  local grant="$1" limit="$2" allowed="$3" needed="$4" i out=() envelope
  for i in "${!lines[@]}"; do
    [[ "${lines[$i]}" == stderr_bytes=* ]] && break
    out+=("${lines[$i]}")
  done
  [[ "${#out[@]}" -eq 1 ]] || { echo "stdout is ${#out[@]} lines, want exactly the envelope: ${out[*]}" >&2; return 1; }
  envelope="${out[0]}"
  assert_output_has "stderr_bytes=0 rc=4"
  run pyq "
import json, sys
src, sch, env = sys.stdin.read().split('\x1e')
ns = {'__file__': '/schema/x/y/schema.py', '__name__': 'schema'}
exec(compile(src, 'schema.py', 'exec'), ns)
env = json.loads(env)
errs = ns['errors'](env, json.loads(sch))
want = {'tool': 'adele', 'target': 'standin.box', 'scope': 'create', 'status': 'grant_required',
        'grant': '${grant}', 'extend_by': 'operator', 'performed': False}
errs += [f'{k}={env.get(k)!r}, want {v!r}' for k, v in want.items() if env.get(k) != v]
if list(env)[:3] != ['tool', 'target', 'scope']:
    errs.append(f'first keys {list(env)[:3]}')
lim = env.get('limit', {})
if lim.get('name') != '${limit}' or lim.get('needed') != '${needed}' or ('${allowed}' != '*' and lim.get('allowed') != '${allowed}'):
    errs.append(f'limit {lim!r}')
if 'confirm' in env:
    errs.append('the grant envelope carries confirm: an operator command where the agent runs commands')
if not str(env.get('extend', '')).startswith('docker exec timelike-adele adeled extend ${grant} ${limit} '):
    errs.append(f'extend {env.get(\"extend\")!r}')
print('ok' if not errs else 'FAILED ' + '; '.join(errs))
print(env.get('extend', ''))
" < <(printf '%s\x1e%s\x1e%s' "$(cat "$SCHEMA_PY")" "$(cat "$GRANT_SCHEMA")" "$envelope")
  [[ "$status" -eq 0 && "${lines[0]}" == ok ]] || { echo "envelope: ${output}" >&2; echo "stdout was: ${envelope}" >&2; return 1; }
  EXTEND="${lines[1]}"
}

holds() { standin_names | grep -qx "$1"; }

check_within() {
  local box="t-sc3-within-$1"
  request "$1" "$box" --grant e2e --ttl 1h --port 8080
  [[ "$status" -eq 0 ]] || { echo "within the grant exited $status: $output" >&2; return 1; }
  holds "$box" || { echo "Adele reported success but the stand-in has no box ${box} (P004)" >&2; return 1; }
}

# check_limit STYLE GRANT LIMIT ALLOWED NEEDED PRE ARGS... — PRE=yes performs one request first, to use
# up the limit (instances, budget).
check_limit() {
  local style="$1" grant="$2" limit="$3" allowed="$4" needed="$5" pre="$6" box="t-sc3-$2"
  shift 6
  if [[ "$pre" == yes ]]; then
    request "$style" "${box}-first" --grant "$grant" "$@"
    [[ "$status" -eq 0 ]] || { echo "the first request (within the grant) exited $status: $output" >&2; return 1; }
  fi

  request "$style" "$box" --grant "$grant" "$@"
  [[ "$status" -eq 4 ]] || { echo "beyond the grant exited $status (want 4): $output" >&2; return 1; }
  envelope_ok "$grant" "$limit" "$allowed" "$needed"
  if holds "$box"; then
    echo "refused, yet the stand-in holds ${box}: something was performed" >&2
    return 1
  fi

  local cmd="$EXTEND"
  run timeout "$RUN_TIMEOUT" bash -c "$cmd" </dev/null # exactly as printed (spec D-4)
  [[ "$status" -eq 0 ]] || { echo "the printed command failed ($status): $cmd → $output" >&2; return 1; }
  assert_output_has "extended ${grant} ${limit}: "

  request "$style" "$box" --grant "$grant" "$@"
  [[ "$status" -eq 0 ]] || { echo "the retry after the extension exited $status: $output" >&2; return 1; }
  holds "$box" || { echo "the retry succeeded but the stand-in has no ${box}" >&2; return 1; }
}

check_agent_cannot_extend() {
  run_in "$1" notty 'command -v adeled docker; echo "found_rc=$?"'
  assert_output_has "found_rc=1"
}

@test "SC-3 004 a request within its grant is performed and returns the result [bash -c]" { check_within c; }
@test "SC-3 004 a request within its grant is performed and returns the result [bash -lc]" { check_within lc; }
@test "SC-3 004 beyond its ttl exits 4 naming grant, limit and extend command; nothing performed; extended, the retry proceeds [bash -c]" { check_limit c ttl-c ttl 1h 2h no --ttl 2h --port 8080; }
@test "SC-3 004 beyond its ttl exits 4 naming grant, limit and extend command; nothing performed; extended, the retry proceeds [bash -lc]" { check_limit lc ttl-lc ttl 1h 2h no --ttl 2h --port 8080; }
@test "SC-3 004 beyond its ports exits 4 naming grant, limit and extend command; nothing performed; extended, the retry proceeds [bash -c]" { check_limit c ports-c ports 8080 22 no --ttl 30m --port 22; }
@test "SC-3 004 beyond its ports exits 4 naming grant, limit and extend command; nothing performed; extended, the retry proceeds [bash -lc]" { check_limit lc ports-lc ports 8080 22 no --ttl 30m --port 22; }
@test "SC-3 004 beyond its instances exits 4 naming grant, limit and extend command; nothing performed; extended, the retry proceeds [bash -c]" { check_limit c inst-c instances 1 2 yes --ttl 30m; }
@test "SC-3 004 beyond its instances exits 4 naming grant, limit and extend command; nothing performed; extended, the retry proceeds [bash -lc]" { check_limit lc inst-lc instances 1 2 yes --ttl 30m; }
@test "SC-3 004 beyond its budget exits 4 naming grant, limit and extend command; nothing performed; extended, the retry proceeds [bash -c]" { check_limit c budget-c budget '0.05 USD' '0.25 USD' yes --ttl 1h; }
@test "SC-3 004 beyond its budget exits 4 naming grant, limit and extend command; nothing performed; extended, the retry proceeds [bash -lc]" { check_limit lc budget-lc budget '0.05 USD' '0.25 USD' yes --ttl 1h; }
@test "SC-3 004 the agent cannot run the operator's extend command: no adeled, no docker [bash -c]" { check_agent_cannot_extend c; }
@test "SC-3 004 the agent cannot run the operator's extend command: no adeled, no docker [bash -lc]" { check_agent_cannot_extend lc; }

# check_envelope STYLE — beyond the roomy `e2e` grant's ports, in --text and --json: the envelope, and
# nothing performed. Not extended, so no other cell's grant or count moves.
check_envelope() {
  local mode box
  for mode in --text --json; do
    box="t-sc3-env-$1${mode#--}"
    request "$1" "$box" "$mode" --grant e2e --ttl 30m --port 22
    [[ "$status" -eq 4 ]] || { echo "beyond the grant (${mode}) exited $status (want 4): $output" >&2; return 1; }
    envelope_ok e2e ports '*' 22
    if holds "$box"; then
      echo "refused (${mode}), yet the stand-in holds ${box}: something was performed" >&2
      return 1
    fi
  done
}

@test "SC-3 004 the refusal's envelope on stdout names the grant, the limit and the extend command [bash -c]" { check_envelope c; }
@test "SC-3 004 the refusal's envelope on stdout names the grant, the limit and the extend command [bash -lc]" { check_envelope lc; }
