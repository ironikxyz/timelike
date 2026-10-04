#!/usr/bin/env bats
# FR-23 — `view` and `search` are announced where agents look (`timelike`'s tool list), pass
# `timelike-conform`, and each name resolves to exactly one command on PATH, timelike's (R7, `type -a`).
# (Feature 006, slice 0; spec FR-21, FR-23, D-6; tasks.md T007; contracts/view-search-cli.md.)
#
# Written from the contract before the tools existed (tasks.md Phase 2). The `type -a` cells are this
# feature's own e2e checks, as 005's were, not part of timelike-conform (spec D-6): the image installs
# no vim (whose `view` alias would shadow or be shadowed) and no other `search`, so exactly one line
# each. conform's text lines (`ok   <tool>` / `FAIL <tool> C<n> ...`) are the format
# contracts/conformance.md fixes; only the two tools' own verdicts are asserted, so another tool's
# finding does not fail this file (SC-5 of 001 covers the whole PATH). conform probes every tool several
# times, so its runs get a 60 s runner limit instead of 30, as the SC-5 file does.
# Cells: bash -c and bash -lc, `notty`.

load helpers

setup_file() {
  stamp_check
}

# check_type_a STYLE NAME — exactly one NAME on PATH, and it is timelike's.
check_type_a() {
  run_in "$1" notty "type -a $2"
  assert_within 20
  assert_status 0
  [[ ${#lines[@]} -eq 1 ]] || { printf 'type -a %s printed %d lines, want 1:\n%s\n' "$2" "${#lines[@]}" "$output" >&2; return 1; }
  [[ "${lines[0]}" == "$2 is /opt/timelike/bin/$2" ]] || { echo "type -a $2: ${lines[0]}" >&2; return 1; }
}

# check_conform STYLE NAME — timelike-conform checks NAME and finds nothing wrong with it.
check_conform() {
  RUN_TIMEOUT=60 run_in "$1" notty "timelike-conform --text --limit 0"
  assert_within 60
  local line ok=0
  for line in "${lines[@]}"; do
    [[ "$line" =~ ^ok\ +$2$ ]] && ok=1
  done
  assert_no_line_matching "^FAIL $2 " || { printf 'output:\n%s\n' "$output" >&2; return 1; }
  ((ok == 1)) || { printf 'timelike-conform has no "ok   %s" line: it did not check it, or it failed; output:\n%s\n' "$2" "$output" >&2; return 1; }
}

# check_listed STYLE NAME — `timelike` lists NAME among the tools on PATH: in text as an indented line,
# and in JSON in `tools`.
check_listed() {
  run_in "$1" notty "timelike --text"
  assert_within 20
  assert_status 0
  local line found=0
  for line in "${lines[@]}"; do
    [[ "$line" == "  $2" ]] && found=1
  done
  ((found == 1)) || { printf 'timelike --text does not list %s:\n%s\n' "$2" "$output" >&2; return 1; }

  run_in "$1" notty "timelike --json"
  assert_within 20
  assert_status 0
  local got
  got="$(printf '%s' "$output" | pyq "import json,sys
d=json.load(sys.stdin)
tools = d.get('tools', (d.get('data') or {}).get('tools', []))
print('listed' if '$2' in tools else 'missing: ' + json.dumps(tools))")" || { echo "timelike --json is not JSON: ${output}" >&2; return 1; }
  [[ "$got" == listed ]] || { echo "timelike --json tools: ${got}" >&2; return 1; }
}

@test "FR-23 R7 type -a view resolves to exactly /opt/timelike/bin/view [bash -c, notty]" { check_type_a c view; }
@test "FR-23 R7 type -a view resolves to exactly /opt/timelike/bin/view [bash -lc, notty]" { check_type_a lc view; }
@test "FR-23 R7 type -a search resolves to exactly /opt/timelike/bin/search [bash -c, notty]" { check_type_a c search; }
@test "FR-23 R7 type -a search resolves to exactly /opt/timelike/bin/search [bash -lc, notty]" { check_type_a lc search; }
@test "FR-23 timelike-conform passes on view [bash -c, notty]" { check_conform c view; }
@test "FR-23 timelike-conform passes on view [bash -lc, notty]" { check_conform lc view; }
@test "FR-23 timelike-conform passes on search [bash -c, notty]" { check_conform c search; }
@test "FR-23 timelike-conform passes on search [bash -lc, notty]" { check_conform lc search; }
@test "FR-23 timelike's tool list names view [bash -c, notty]" { check_listed c view; }
@test "FR-23 timelike's tool list names view [bash -lc, notty]" { check_listed lc view; }
@test "FR-23 timelike's tool list names search [bash -c, notty]" { check_listed c search; }
@test "FR-23 timelike's tool list names search [bash -lc, notty]" { check_listed lc search; }
