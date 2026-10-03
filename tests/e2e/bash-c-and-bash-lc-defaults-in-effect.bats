#!/usr/bin/env bats
# SC-2 — "The Harness invokes a command through non-interactive bash -c or bash -lc, and the
# environment's pager, editor, prompt and colour defaults are all in effect. This is verified by one
# test per invocation style." (tasks.md T018; spec FR-1; research R1–R4.)
#
# One @test per invocation style — bash -c, bash -lc, bash -ic and sh -c — each in the three
# terminal modes of helpers.bash. Each test's name carries its style. The command below only READS
# values: it sets nothing, sources nothing, and is identical for every style, so a value missing in
# one style can only come from how that shell starts (R1: /etc/profile resets PATH under -lc;
# BASH_ENV is ignored by sh and interactive shells; rc files are skipped by -c).
#
# Values are read from git itself where git has the final say (`git var`, `git config --get`),
# which resolves the whole precedence chain (env over system config), not just one layer (P001).
#
# Common failure (slice 1, natural intensity; modify.md F005; tasks.md T053): the agent, or a script
# it runs, unsets the variables. Research R2 keeps /etc/gitconfig as a fallback layer for exactly
# this case ("in case the agent unsets a variable"), and nothing end to end has read it yet: the happy
# path above resolves every git value from ENV, which would hide an empty or unread /etc/gitconfig.
# The command unsets every git-relevant ENV default that the file backs (editor, sequence editor,
# pager, the GIT_CONFIG_* hooks layer) and reads git's resolved values again. One test per invocation
# style, as the criterion asks; notty only, because these are config reads that no terminal changes.
# Not covered, and not claimed: GIT_TERMINAL_PROMPT has no gitconfig equivalent, so an agent that
# unsets it has explicitly re-enabled terminal prompts (recorded as ABSENT in the T053 report).

load helpers

setup_file() {
  stamp_check
}

# POSIX sh on purpose: the same string must run under dash. ${VAR-<unset>} distinguishes unset from
# empty. `cd /` keeps git out of any repository, so only environment and system config apply.
# shellcheck disable=SC2016 # expanded in the container
READ_DEFAULTS='cd / || exit 97
printf "timelike=%s\n" "$(command -v timelike)"
printf "GIT_EDITOR=%s\n" "$(git var GIT_EDITOR)"
printf "GIT_PAGER=%s\n" "$(git var GIT_PAGER)"
printf "PAGER=%s\n" "${PAGER-<unset>}"
printf "color.ui=%s\n" "$(git config --get color.ui)"
printf "NO_COLOR=%s\n" "${NO_COLOR-<unset>}"
printf "GIT_TERMINAL_PROMPT=%s\n" "${GIT_TERMINAL_PROMPT-<unset>}"
printf "DEBIAN_FRONTEND=%s\n" "${DEBIAN_FRONTEND-<unset>}"
printf "core.hooksPath=%s\n" "$(git config --get core.hooksPath)"
printf "read-defaults=done\n"'

check_defaults() {
  run_in "$1" "$2" "$READ_DEFAULTS"
  assert_within 20
  assert_status 0
  assert_value read-defaults "done"
  # PATH: catches the /etc/profile reset under bash -lc (R1) and a PATH kept only in profile.d.
  assert_value timelike /opt/timelike/bin/timelike
  # Editor and pager (R2), resolved by git.
  assert_value GIT_EDITOR true
  assert_value GIT_PAGER cat
  assert_value PAGER cat
  # Colour (R4): NO_COLOR has no effect on git, so git's own setting is read as well.
  assert_value color.ui never
  assert_value NO_COLOR 1
  # Prompts (R2, R5).
  assert_value GIT_TERMINAL_PROMPT 0
  assert_value DEBIAN_FRONTEND noninteractive
  # Hooks run through timelike's dispatchers, bounded (R11; R3's command-scope GIT_CONFIG_* layer).
  assert_value core.hooksPath /opt/timelike/git-hooks
}

# --- bash -c ---
@test "SC-2 bash -c: pager, editor, prompt and colour defaults in effect [notty]" { check_defaults c notty; }
@test "SC-2 bash -c: pager, editor, prompt and colour defaults in effect [tty]" { check_defaults c tty; }
@test "SC-2 bash -c: pager, editor, prompt and colour defaults in effect [pty]" { check_defaults c pty; }

# --- bash -lc ---
@test "SC-2 bash -lc: pager, editor, prompt and colour defaults in effect [notty]" { check_defaults lc notty; }
@test "SC-2 bash -lc: pager, editor, prompt and colour defaults in effect [tty]" { check_defaults lc tty; }
@test "SC-2 bash -lc: pager, editor, prompt and colour defaults in effect [pty]" { check_defaults lc pty; }

# --- bash -ic ---
@test "SC-2 bash -ic: pager, editor, prompt and colour defaults in effect [notty]" { check_defaults ic notty; }
@test "SC-2 bash -ic: pager, editor, prompt and colour defaults in effect [tty]" { check_defaults ic tty; }
@test "SC-2 bash -ic: pager, editor, prompt and colour defaults in effect [pty]" { check_defaults ic pty; }

# --- sh -c ---
@test "SC-2 sh -c: pager, editor, prompt and colour defaults in effect [notty]" { check_defaults sh notty; }
@test "SC-2 sh -c: pager, editor, prompt and colour defaults in effect [tty]" { check_defaults sh tty; }
@test "SC-2 sh -c: pager, editor, prompt and colour defaults in effect [pty]" { check_defaults sh pty; }

# --- common failure (slice 1): the agent unsets the ENV defaults; /etc/gitconfig still holds ---

# POSIX sh, like READ_DEFAULTS. `git var GIT_SEQUENCE_EDITOR` resolves GIT_SEQUENCE_EDITOR, then
# sequence.editor, then the editor chain. credential.helper is printed in brackets: the fallback's
# empty value (which resets the helper list, R2) must read as "[]" AND be present (rc 0): an absent
# key would also print "[]", but exits 1.
# shellcheck disable=SC2016 # expanded in the container
READ_FALLBACK='cd / || exit 97
unset GIT_EDITOR GIT_SEQUENCE_EDITOR GIT_PAGER PAGER GIT_CONFIG_COUNT GIT_CONFIG_KEY_0 GIT_CONFIG_VALUE_0
printf "env-cleared=%s\n" "${GIT_EDITOR-u}${GIT_PAGER-u}${GIT_CONFIG_COUNT-u}"
printf "GIT_EDITOR=%s\n" "$(git var GIT_EDITOR)"
printf "GIT_SEQUENCE_EDITOR=%s\n" "$(git var GIT_SEQUENCE_EDITOR)"
printf "GIT_PAGER=%s\n" "$(git var GIT_PAGER)"
printf "color.ui=%s\n" "$(git config --get color.ui)"
printf "core.hooksPath=%s\n" "$(git config --get core.hooksPath)"
printf "credential.helper=[%s]\n" "$(git config --get-all credential.helper)"
git config --get-all credential.helper >/dev/null
printf "credential.helper-rc=%s\n" "$?"
printf "read-fallback=done\n"'

check_fallback_defaults() {
  run_in "$1" "$2" "$READ_FALLBACK"
  assert_within 20
  assert_status 0
  assert_value read-fallback "done"
  # Control: the variables really are gone in this shell, so every value below came from the file.
  assert_value env-cleared uuu
  assert_value GIT_EDITOR true
  assert_value GIT_SEQUENCE_EDITOR true
  assert_value GIT_PAGER cat
  assert_value color.ui never
  assert_value core.hooksPath /opt/timelike/git-hooks
  assert_value credential.helper "[]"
  assert_value credential.helper-rc 0
}

@test "SC-2 bash -c: editor, pager, colour and hooks defaults hold from /etc/gitconfig when the agent unsets the variables [notty]" { check_fallback_defaults c notty; }
@test "SC-2 bash -lc: editor, pager, colour and hooks defaults hold from /etc/gitconfig when the agent unsets the variables [notty]" { check_fallback_defaults lc notty; }
@test "SC-2 bash -ic: editor, pager, colour and hooks defaults hold from /etc/gitconfig when the agent unsets the variables [notty]" { check_fallback_defaults ic notty; }
@test "SC-2 sh -c: editor, pager, colour and hooks defaults hold from /etc/gitconfig when the agent unsets the variables [notty]" { check_fallback_defaults sh notty; }
