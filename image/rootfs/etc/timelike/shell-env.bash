# shellcheck shell=bash
# /etc/timelike/shell-env.bash — container-derived shell defaults (feature 001, slice 1: SC-8, SC-9;
# modify.md F001, F002, F004; spec FR-15, FR-16, FR-18, Assumptions 7 and 8).
#
# Reached by every bash invocation style (F004; research R1):
#   bash -c            BASH_ENV (image ENV)
#   bash -lc           /etc/profile.d/10-timelike-shell-env.sh, then BASH_ENV again (bash reads it
#                      after the profile files in a non-interactive login shell)
#   bash -i / -ic      the line appended to /etc/bash.bashrc (interactive shells ignore BASH_ENV)
# NOT reached, recorded rather than hidden (spec Out of Scope): plain `sh -c` (dash) and a direct
# `docker exec` of a non-shell binary read no startup file. The static ENV defaults (TZ,
# PYTHON_BASIC_REPL, FR-17) reach them; this file's job counts and secret strip do not.
#
# Rules for this file, because it runs at the start of every bash process:
#   - bash builtins only: no command substitution, pipe, process substitution or external command,
#     so a shell start costs no fork (it works with PATH empty — tests/host/test_shell_env_hook.sh)
#   - silent: all of its stderr is discarded, including xtrace lines when the caller runs `bash -x`
#   - never fails the shell: errexit, nounset and xtrace are switched off locally (`local -`), and it
#     returns 0 whatever it read
#   - idempotent: sourcing it twice leaves the same environment as sourcing it once (bash -lc does)
#   - leaves nothing behind but what it means to: the defaults function is unset after its single
#     call, with local variables only; command_not_found_handle stays defined on purpose (feature
#     007 slice 1), and costs nothing until a command is not found
#   - a no-op in any shell other than bash (the guard below is POSIX)
#
# ── F001: build parallelism from the container's CPU limit (SC-8, FR-15) ─────────────────────────
# TIMELIKE_CPUS = ceil(quota / period) from cgroup v2 cpu.max, capped by the CPU count in the
# process's affinity (Cpus_allowed_list in /proc/self/status). A quota of "max" (no limit), or an
# unreadable cpu.max (e.g. a cgroup v1 host), leaves the affinity count. Neither readable: 1. Never
# below 1. TIMELIKE_CPUS itself is always recomputed and exported, as the figure the defaults came
# from. The six job-count variables are exported only when unset or empty, so an explicit value wins
# (spec edge cases: "the environment changes defaults, not explicit choices"). An exported value a
# parent shell's hook set is inherited like any explicit value; it is the same figure unless the child
# moved to another cgroup, which a container's shells do not.
#
# Test-only overrides: TIMELIKE_CGROUP_CPU_MAX and TIMELIKE_PROC_STATUS replace the two source paths,
# so the host lane can feed fake files. They change only the job-count figure (never the strip), and
# nothing in the image sets them.
#
# ── F002: secret-shaped variables stripped unless allow-listed (SC-9, FR-16) ─────────────────────
# The name is split on "_" and each part upper-cased. An exported variable is unset when a component
#   - IS one of:        KEY KEYS APIKEY ACCESSKEY PRIVATEKEY PASSPHRASE PASS CREDENTIAL CREDENTIALS
#   - or ENDS WITH one: PASSWORD PASSWORDS PASSWD TOKEN TOKENS SECRET SECRETS
# Anchored at component ends, never a bare substring: GIT_ASKPASS, TOKENIZERS_PARALLELISM, MONKEY and
# KEYBOARD_LAYOUT stay; npm_config__authToken (AUTHTOKEN), PGPASSWORD and GHTOKEN go. The key family
# is whole-component only, because a suffix match would take MONKEY and HOTKEY (review of T050).
# Kept regardless:
#   - names listed in TIMELIKE_ENV_ALLOW: exact, case-sensitive names separated by commas and/or
#     whitespace (spec Assumption 7), e.g. TIMELIKE_ENV_ALLOW="NPM_TOKEN, HF_TOKEN"
#   - GIT_CONFIG_KEY_<n>: git's command-scope config names (the image's own GIT_CONFIG_KEY_0 points
#     core.hooksPath at the hook dispatchers, R3/R11). Its value is a config key's name, not a secret, and with GIT_CONFIG_COUNT
#     still set, unsetting it makes every git command fail ("missing config key")
# Limits:
#   - a name only a person would call secret-shaped but that matches none of the criterion's key /
#     token / secret / password patterns (SSHPASS, MYSQL_PWD, GITHUB_PAT) is kept; allow-listing is
#     the only escape the other way, so the rule stays narrow on purpose
#   - an environment entry whose name is not a shell identifier (e.g. MY-TOKEN) is not a bash
#     variable at all: bash cannot unset it and passes it through to its children
#   - the strip governs the agent's shells; it cannot remove what the container itself was started
#     with (/proc/1/environ, spec Assumption 7)
#   - every bash process strips again, including one the agent starts itself: an agent that exports
#     FOO_TOKEN and runs `bash script.sh` loses it there unless FOO_TOKEN is in TIMELIKE_ENV_ALLOW

{ [ -n "${BASH_VERSION-}" ] || return 0; } 2>/dev/null

{
  __timelike_shell_env() {
    local -
    set +o errexit +o nounset +o xtrace
    local IFS=$' \t\n'

    # ${!name@a} (attributes of the named variable) needs bash 4.4.
    if ((BASH_VERSINFO[0] < 4 || (BASH_VERSINFO[0] == 4 && BASH_VERSINFO[1] < 4))); then
      return 0
    fi

    # --- F001: CPU figure ------------------------------------------------------------------------
    local cpu_max="${TIMELIKE_CGROUP_CPU_MAX:-/sys/fs/cgroup/cpu.max}"
    local status_file="${TIMELIKE_PROC_STATUS:-/proc/self/status}"
    local quota="" period="" line list item lo hi
    local quota_cpus=0 affinity_cpus=0 cpus

    if read -r quota period _ <"$cpu_max"; then
      if [[ "$quota" =~ ^[0-9]+$ && "$period" =~ ^[0-9]+$ ]] && ((10#$period > 0 && 10#$quota > 0)); then
        quota_cpus=$(((10#$quota + 10#$period - 1) / 10#$period))
      fi
    fi

    # Cpus_allowed_list: comma-separated CPU numbers and inclusive ranges, e.g. "0-3,8,10-11".
    list=""
    while read -r line; do
      case "$line" in
        Cpus_allowed_list:*)
          list="${line#Cpus_allowed_list:}"
          break
          ;;
      esac
    done <"$status_file"
    list="${list//[[:space:]]/}"
    if [[ "$list" =~ ^[0-9]+(-[0-9]+)?(,[0-9]+(-[0-9]+)?)*$ ]]; then
      list+=","
      while [[ -n "$list" ]]; do
        item="${list%%,*}"
        list="${list#*,}"
        lo="${item%-*}"
        hi="${item#*-}"
        if ((10#$hi >= 10#$lo)); then
          affinity_cpus=$((affinity_cpus + 10#$hi - 10#$lo + 1))
        fi
      done
    fi

    cpus=$affinity_cpus
    if ((quota_cpus > 0 && (cpus == 0 || quota_cpus < cpus))); then
      cpus=$quota_cpus
    fi
    ((cpus >= 1)) || cpus=1

    export TIMELIKE_CPUS="$cpus"
    [[ -n "${MAKEFLAGS-}" ]] || export MAKEFLAGS="-j${cpus}"
    [[ -n "${CMAKE_BUILD_PARALLEL_LEVEL-}" ]] || export CMAKE_BUILD_PARALLEL_LEVEL="$cpus"
    [[ -n "${CARGO_BUILD_JOBS-}" ]] || export CARGO_BUILD_JOBS="$cpus"
    [[ -n "${GOMAXPROCS-}" ]] || export GOMAXPROCS="$cpus"
    [[ -n "${PYTEST_XDIST_AUTO_NUM_WORKERS-}" ]] || export PYTEST_XDIST_AUTO_NUM_WORKERS="$cpus"
    # Python >= 3.13 returns PYTHON_CPU_COUNT from os.cpu_count() and os.process_cpu_count().
    [[ -n "${PYTHON_CPU_COUNT-}" ]] || export PYTHON_CPU_COUNT="$cpus"

    # --- F002: secret strip ----------------------------------------------------------------------
    local allow=" ${TIMELIKE_ENV_ALLOW-} " name upper
    allow="${allow//[,$'\t\n\r']/ }"
    # Every variable name, by first character (${!prefix@} lists names starting with prefix; a
    # name cannot start with a digit). A builtin enumeration: `compgen -e` would need a fork to read.
    for name in ${!A@} ${!B@} ${!C@} ${!D@} ${!E@} ${!F@} ${!G@} ${!H@} ${!I@} ${!J@} ${!K@} \
      ${!L@} ${!M@} ${!N@} ${!O@} ${!P@} ${!Q@} ${!R@} ${!S@} ${!T@} ${!U@} ${!V@} ${!W@} ${!X@} \
      ${!Y@} ${!Z@} ${!a@} ${!b@} ${!c@} ${!d@} ${!e@} ${!f@} ${!g@} ${!h@} ${!i@} ${!j@} ${!k@} \
      ${!l@} ${!m@} ${!n@} ${!o@} ${!p@} ${!q@} ${!r@} ${!s@} ${!t@} ${!u@} ${!v@} ${!w@} ${!x@} \
      ${!y@} ${!z@} ${!_@}; do
      [[ "${!name@a}" == *x* ]] || continue
      [[ "$allow" != *" $name "* ]] || continue
      [[ ! "$name" =~ ^GIT_CONFIG_KEY_[0-9]+$ ]] || continue
      upper="_${name^^}_"
      case "$upper" in
        *_KEY_* | *_KEYS_* | *_APIKEY_* | *_ACCESSKEY_* | *_PRIVATEKEY_* | \
          *_PASSPHRASE_* | *_PASS_* | *_CREDENTIAL_* | *_CREDENTIALS_* | \
          *TOKEN_* | *TOKENS_* | *SECRET_* | *SECRETS_* | \
          *PASSWORD_* | *PASSWORDS_* | *PASSWD_*)
          unset -v "$name"
          ;;
      esac
    done
    return 0
  }
  __timelike_shell_env
  unset -f __timelike_shell_env
} 2>/dev/null

# ── Feature 007 slice 1: a command that is not installed (spec FR-14 to FR-17; contract § The
# command-not-found answer; research R5, R6) ──────────────────────────────────────────────────────
# bash calls command_not_found_handle, in a subshell, when a name is found nowhere; its status is the
# command's. It prints bash's own line first, byte for byte (the prolog bash would have written: the
# caller's BASH_SOURCE, else $0, and BASH_LINENO[0]; no line number when interactive), then, for a name
# listed in the data file, one `timelike:` line per row: the timelike equivalent, the Debian package
# and who can add it, or a user-level install. An unknown name gets bash's line alone. Exit 127.
# Builtins only (read, printf): a typo costs no fork. It never reads stdin, never installs, never asks.
# Reached by bash -c, bash -lc, interactive bash and the scripts they run; NOT by sh -c (dash) or a
# direct exec, which keep their own messages (D-7). TIMELIKE_MISSING_COMMANDS is a test-only override
# of the data file's path, like the overrides above; nothing in the image sets it.
{
  command_not_found_handle() {
    { local -; set +o errexit +o nounset +o xtrace; } 2>/dev/null
    local IFS=$' \t\n' name="${1-}" row kind value note rest
    local data="${TIMELIKE_MISSING_COMMANDS:-/etc/timelike/missing-commands.tsv}"
    if [[ "$-" == *i* ]]; then
      printf '%s: %s: command not found\n' "${0##*/}" "$name" >&2  # interactive: bash prints argv0's base name
    else
      printf '%s: line %s: %s: command not found\n' "${BASH_SOURCE[1]:-$0}" "${BASH_LINENO[0]}" "$name" >&2
    fi
    if [[ -n "$name" && -f "$data" && -r "$data" ]]; then  # a directory there is unreadable, not an error
      while IFS=$'\t' read -r row kind value note rest || [[ -n "$row" ]]; do
        [[ "$row" == "$name" && -n "$value" && -n "$note" && -z "$rest" ]] || continue
        case "$kind" in
          instead)
            if [[ "$note" == - ]]; then
              printf 'timelike: instead: %s\n' "$value"
            else
              printf 'timelike: instead: %s  (%s)\n' "$value" "$note"
            fi
            ;;
          debian)
            printf 'timelike: %s is in the Debian package %s, which is not installed. The agent cannot install OS packages (no root): the operator adds %s to the image.\n' \
              "$name" "$value" "$value"
            ;;
          user)
            if [[ "$note" == - ]]; then
              printf 'timelike: install it yourself: %s\n' "$value"
            else
              printf 'timelike: install it yourself: %s  (%s)\n' "$value" "$note"
            fi
            ;;
        esac
      done <"$data" >&2
    fi
    return 127
  }
} 2>/dev/null

# ── Feature 009: the session journal's shell record (spec FR-7, FR-8; research R1) ──────────────────
# In a non-interactive bash with an execution string (`bash -c`, `bash -lc`), set an EXIT trap that
# sources the journal's exit file, which appends one line per command. Builtins only here (no fork at
# shell start); set once, so the login path's second source (profile.d, then BASH_ENV) changes nothing.
# Leaves one non-exported variable (the start time) and the trap. TIMELIKE_JOURNAL_EXIT is a test-only
# override of the exit file's path (as TIMELIKE_CGROUP_CPU_MAX above); nothing in the image sets it.
{
  if [[ -z "${__timelike_journal_t0-}" && -n "${BASH_EXECUTION_STRING-}" && "$-" != *i* ]] &&
    [[ -r "${TIMELIKE_JOURNAL_EXIT:-/etc/timelike/journal-exit.bash}" ]]; then
    __timelike_journal_t0="${EPOCHREALTIME/./}"
    # shellcheck disable=SC2064 # the path is fixed now, on purpose
    trap ". '${TIMELIKE_JOURNAL_EXIT:-/etc/timelike/journal-exit.bash}'" EXIT
  fi
} 2>/dev/null
