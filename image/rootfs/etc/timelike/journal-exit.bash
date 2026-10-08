# shellcheck shell=bash
# /etc/timelike/journal-exit.bash — the session journal's shell record (feature 009, spec FR-7; research R1).
#
# Sourced by the EXIT trap that /etc/timelike/shell-env.bash sets in a non-interactive `bash -c` or
# `bash -lc` (BASH_EXECUTION_STRING set). Appends ONE JSON line to
# ${TIMELIKE_SCRATCH_ROOT:-/tmp/timelike}/<session>/shell.jsonl: the command line, its exit, its start
# and end (epoch µs), pid, ppid, session, agent, cwd and style. The journal (tools/bin/journal) reads it;
# nothing else writes it, and this file writes nothing else (seam 1: never shadows a command).
#
# Rules, as for 001's hook:
#   - bash builtins only, except `mkdir` the first time a session directory is missing (at exit, never
#     at shell start: F1's no-fork probe holds)
#   - silent (stderr discarded), and it never changes the shell's exit status: it ends without `exit`,
#     so bash exits with the status the command left (research R1, measured)
#   - not for root (EUID 0): root's commands are the operator's, and a root-owned session directory
#     would lock the agent out of its own records
# Limits (stated in the journal's manifest): a command that sets its own EXIT trap replaces this one;
# `sh -c`, interactive shells and direct execs are not captured.

__timelike_journal_rc=$?
{
  set +o errexit +o nounset +o xtrace
  __tj_s="${TIMELIKE_SESSION:-default}"
  if ((EUID != 0)) && [[ "$__tj_s" =~ ^[A-Za-z0-9._-]{1,64}$ && "$__tj_s" == *[!.]* ]]; then
    __tj_r="${TIMELIKE_SCRATCH_ROOT:-/tmp/timelike}"
    __tj_d="${__tj_r}/${__tj_s}"
    if [[ ! -d "$__tj_d" ]]; then
      # As agentio makes them (rule 10): a shared root, like /tmp, and a private session directory.
      [[ -d "$__tj_r" ]] || { command mkdir -p -- "$__tj_r" && command chmod 1777 -- "$__tj_r"; }
      command mkdir -m 0700 -- "$__tj_d"
    fi
    __tj_c="${BASH_EXECUTION_STRING:0:4096}"
    __tj_cut=$((${#BASH_EXECUTION_STRING} - ${#__tj_c}))
    __tj_c="${__tj_c//\\/\\\\}"
    __tj_c="${__tj_c//\"/\\\"}"
    __tj_c="${__tj_c//$'\n'/\\n}"
    __tj_c="${__tj_c//$'\t'/\\t}"
    __tj_c="${__tj_c//$'\r'/\\r}"
    __tj_c="${__tj_c//[$'\001'-$'\037']/?}"
    __tj_w="${PWD//\\/\\\\}"
    __tj_w="${__tj_w//\"/\\\"}"
    __tj_w="${__tj_w//[$'\001'-$'\037']/?}"
    __tj_a="${TIMELIKE_AGENT-}"
    [[ "$__tj_a" =~ ^[A-Za-z0-9._-]{1,64}$ ]] || __tj_a=""
    __tj_y="bash -c"
    shopt -q login_shell && __tj_y="bash -lc"
    umask 077
    printf '{"v":1,"kind":"shell","cmd":"%s","cut_bytes":%d,"exit":%d,"start_us":%s,"end_us":%s,"pid":%d,"ppid":%d,"session":"%s","agent":"%s","cwd":"%s","style":"%s"}\n' \
      "$__tj_c" "$__tj_cut" "$__timelike_journal_rc" "${__timelike_journal_t0:-0}" "${EPOCHREALTIME/./}" \
      "$$" "$PPID" "$__tj_s" "$__tj_a" "$__tj_w" "$__tj_y" >>"${__tj_d}/shell.jsonl"
  fi
} 2>/dev/null
