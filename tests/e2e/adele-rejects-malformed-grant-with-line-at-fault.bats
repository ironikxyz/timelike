#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# shellcheck disable=SC2030,SC2031 # bats runs each @test in its own subshell by design
# SC-2 (feature 004) — "A grant file defines allowed capabilities, a money budget, a time-to-live, and
# instance and port limits, and Adele rejects a malformed grant at start with the line at fault"
# (send 12-rev2, slice 0; spec FR-5, FR-6; tasks.md T016).
#
# Operator side, one style: each file under tests/e2e/fixtures/adele/malformed/ is given to a THROWAWAY
# Adele (the running Adele's image, no network, a private ledger, the real canary volume). She must
# exit at start — non-zero, and not the 10 s bound (124) — and her log must name `grants.conf:<line>`
# with the exact line at fault and what is wrong. A valid file (the lane's own) must start and serve:
# it is still running at the bound. The grammar's every malformation is unit-tested in Go
# (adele/internal/grants); these are six representative ones, through the real image.

load helpers

setup_file() {
  stamp_check_adele
}

# rejects FIXTURE LINE WORDS — Adele refuses FIXTURE at start, naming grants.conf:LINE and WORDS.
rejects() {
  run adele_run_with_grants "tests/e2e/fixtures/adele/malformed/$1"
  [[ "$status" -ne 0 && "$status" -ne 124 ]] || { echo "status $status (want a refusal at start): $output" >&2; return 1; }
  assert_output_has "grants.conf:$2: "
  assert_output_has "$3"
}

@test "SC-2 004 Adele rejects a malformed grant at start: an unknown key, at its line" { rejects unknown-key.conf 6 'unknown key "portz"'; }
@test "SC-2 004 Adele rejects a malformed grant at start: a bad duration, at its line" { rejects bad-duration.conf 4 'ttl "1 hour"'; }
@test "SC-2 004 Adele rejects a malformed grant at start: a negative budget, at its line" { rejects negative-budget.conf 4 'negative amount'; }
@test "SC-2 004 Adele rejects a malformed grant at start: a pair outside any section, at its line" { rejects pair-outside-section.conf 2 'outside any [grant NAME] section'; }
@test "SC-2 004 Adele rejects a malformed grant at start: a duplicate grant, at its line" { rejects duplicate-grant.conf 8 'duplicate grant "a"'; }
@test "SC-2 004 Adele rejects a malformed grant at start: an unknown capability, at its line" { rejects unknown-capability.conf 2 'unknown capability "docker.run"'; }

@test "SC-2 004 a grant file with capabilities, budget, ttl, instances and ports starts Adele" {
  run adele_run_with_grants tests/e2e/fixtures/adele/grants.conf
  [[ "$status" -eq 124 ]] || { echo "status $status (want: still serving at the bound): $output" >&2; return 1; }
  assert_output_has "adeled: serving on"
  assert_output_has "10 grants"
}
