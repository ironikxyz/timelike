#!/usr/bin/env bash
# Host lane, ADVISORY (feature 007 slice 1; spec FR-14 to FR-17; contract § The command-not-found
# answer; research R5). Unit-tests the LOGIC of command_not_found_handle, defined by the repository's
# image/rootfs/etc/timelike/shell-env.bash, with the host's bash, against a data file this test writes
# (TIMELIKE_MISSING_COMMANDS, the handler's test-only override). It does NOT prove the image: the Docker
# lane (tests/e2e/command-not-installed-exits-127-and-prints-the-install-command.bats) is authoritative.
#
# Line 1 is never written down here: for every style it is what the SAME bash prints for the SAME input
# with no handler defined, and the handler's stderr must be that, byte for byte, followed by the
# contract's `timelike:` lines for the fixture's rows, in file order (lore cross-stack P005).
#
# Every case starts a fresh `env -i` bash with PATH=/nonexistent (an external command in the handler
# would fail) and stdin from /dev/null unless the case is about stdin. The hook is reached through
# BASH_ENV, as `bash -c` and scripts reach it in the image; interactive shells ignore BASH_ENV, so those
# cases source it explicitly, as /etc/bash.bashrc does in the image.
#
# Cases: styles (A), fixture rows (R), caller options and stdin (E), the data file (D), PATH (P),
# no fork (F). Self-checks (P004: a test that cannot fail proves nothing):
#   X1  the R1 comparison against an EMPTY hook must fail
#   X2  the no-fork probe must let a builtin-only handler through and catch one that forks, else F1 is
#       reported as a skip
set -euo pipefail

echo "# ADVISORY host lane: command_not_found_handle's logic on the host's bash, NOT the image"

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
hook_real="${repo}/image/rootfs/etc/timelike/shell-env.bash"
[[ -r "${hook_real}" ]] || { echo "Bail out! missing ${hook_real}"; exit 1; }
BASH_BIN="$(command -v bash)"

tmp="$(mktemp -d)"
trap 'chmod -R u+rwX "${tmp}" 2>/dev/null; rm -rf "${tmp}"' EXIT
: >"${tmp}/empty-hook.bash"
hook="${hook_real}"

n=0
failures=0
tap() { # tap OK(0|1) DESCRIPTION
  n=$((n + 1))
  if [[ "$1" == "0" ]]; then
    echo "ok ${n} - $2"
  else
    echo "not ok ${n} - $2"
    failures=$((failures + 1))
  fi
}

# ── The fixture: all three kinds, a `-` note, a comment, an empty line and malformed lines ─────────
fx="${tmp}/missing-commands.tsv"
{
  printf '%s\n' '# a comment line: ignored'
  printf '%s\t%s\t%s\t%s\n' tlmc-both instead 'view DIR' 'budgeted overview'
  printf '\n'
  printf '%s\t%s\n' tlmc-both instead # malformed (two fields): skipped, order of the rest kept
  printf '%s\t%s\t%s\t%s\n' tlmc-both debian tlmc-pkg -
  printf '%s\t%s\t%s\t%s\n' tlmc-plain instead 'run tlmc-thing --flag' -
  printf '%s\t%s\t%s\t%s\n' tlmc-user user 'uv tool install tlmc-user' -
  printf '%s\t%s\t%s\n' tlmc-short instead 'view FILE'                # three fields
  printf '%s\t%s\t%s\t%s\t%s\n' tlmc-long instead 'view FILE' note extra # five fields
  printf '%s\t%s\t%s\t%s\n' tlmc-kind apt tlmc-kind -                   # unknown kind
  printf '%s\t%s\t%s\t%s\n' tlmc-both user 'uv tool install tlmc-both' 'from PyPI'
} >"${fx}"

BOTH=(
  "timelike: instead: view DIR  (budgeted overview)"
  "timelike: tlmc-both is in the Debian package tlmc-pkg, which is not installed. The agent cannot install OS packages (no root): the operator adds tlmc-pkg to the image."
  "timelike: install it yourself: uv tool install tlmc-both  (from PyPI)"
)
PLAIN=("timelike: instead: run tlmc-thing --flag")
USER_ROW=("timelike: install it yourself: uv tool install tlmc-user")
UNKNOWN="tlmc-unknown-$$"

mkdir -p "${tmp}/d"
envs() { # the common environment of every case, then extras
  printf '%s\n' PATH=/nonexistent "HOME=${tmp}" "TIMELIKE_MISSING_COMMANDS=${fx}" \
    TIMELIKE_JOURNAL_EXIT=/nonexistent TIMELIKE_CGROUP_CPU_MAX=/nonexistent TIMELIKE_PROC_STATUS=/nonexistent
}
mapfile -t ENVS < <(envs)

# go STYLE NAME HOOKFILE OUTPREFIX — run NAME in STYLE; HOOKFILE "" = no handler (bash's own line).
# Writes OUTPREFIX.err (filtered as below), OUTPREFIX.out and OUTPREFIX.rc.
go() {
  local style="$1" name="$2" h="$3" o="$4" rc=0 be=()
  [[ -n "${h}" ]] && be=("BASH_ENV=${h}")
  case "${style}" in
    c) (cd "${tmp}" && env -i "${ENVS[@]}" "${be[@]}" "${BASH_BIN}" -c "true; ${name}" \
      </dev/null >"${o}.out" 2>"${o}.raw") || rc=$? ;;
    c-line3) (cd "${tmp}" && env -i "${ENVS[@]}" "${be[@]}" "${BASH_BIN}" -c $'true\n\n'"${name}" \
      </dev/null >"${o}.out" 2>"${o}.raw") || rc=$? ;;
    c-name) (cd "${tmp}" && env -i "${ENVS[@]}" "${be[@]}" "${BASH_BIN}" -c "${name}" myname \
      </dev/null >"${o}.out" 2>"${o}.raw") || rc=$? ;;
    c-function) (cd "${tmp}" && env -i "${ENVS[@]}" "${be[@]}" "${BASH_BIN}" -c "f() { ${name}; }; f" \
      </dev/null >"${o}.out" 2>"${o}.raw") || rc=$? ;;
    script)
      printf 'true\ntrue\n%s\n' "${name}" >"${tmp}/d/top.sh"
      (cd "${tmp}" && env -i "${ENVS[@]}" "${be[@]}" "${BASH_BIN}" d/top.sh \
        </dev/null >"${o}.out" 2>"${o}.raw") || rc=$? ;;
    script-function)
      printf 'f() {\n  true\n  %s\n}\nf\n' "${name}" >"${tmp}/d/fn.sh"
      (cd "${tmp}" && env -i "${ENVS[@]}" "${be[@]}" "${BASH_BIN}" d/fn.sh \
        </dev/null >"${o}.out" 2>"${o}.raw") || rc=$? ;;
    stdin)
      printf 'true\n\n%s\n' "${name}" >"${tmp}/d/in.sh"
      (cd "${tmp}" && env -i "${ENVS[@]}" "${be[@]}" "${BASH_BIN}" -s \
        <"${tmp}/d/in.sh" >"${o}.out" 2>"${o}.raw") || rc=$? ;;
    interactive | interactive-path)
      # --noediting: no readline, so the input is not echoed. PS1/PS2 empty: no prompts on stderr (set
      # in the launching shell, since a non-interactive bash unsets both).
      local argv0=bash
      [[ "${style}" == interactive-path ]] && argv0="${BASH_BIN}"
      if [[ -n "${h}" ]]; then
        # shellcheck disable=SC2016 # expanded by the bash under test
        printf '. "$HOOK"\n%s\n' "${name}" >"${tmp}/d/i.sh"
      else
        printf '%s\n' "${name}" >"${tmp}/d/i.sh"
      fi
      # shellcheck disable=SC2016 # expanded by the bash under test
      (cd "${tmp}" && timeout 20 env -i "${ENVS[@]}" PS1= PS2= "HOOK=${h}" "A0=${argv0}" "${BASH_BIN}" -c \
        'export PS1= PS2=; exec -a "$A0" "$0" --norc --noediting -i' "${BASH_BIN}" \
        <"${tmp}/d/i.sh" >"${o}.out" 2>"${o}.raw") || rc=$? ;;
    *) echo "Bail out! unknown style ${style}"; exit 1 ;;
  esac
  printf '%s' "${rc}" >"${o}.rc"
  if [[ "${style}" == interactive* ]]; then
    # An interactive bash without a terminal says so twice at start, and `exit` at end of input.
    grep -v -e ': cannot set terminal process group (' -e ': no job control in this shell$' -e '^exit$' \
      "${o}.raw" >"${o}.err" || true
  else
    cp "${o}.raw" "${o}.err"
  fi
}

# compare DESC STYLE NAME [EXPECTED LINE]... — one TAP line: the handler's stderr is bash's own (from a
# run with no handler) followed by the expected lines, byte for byte; exit 127; nothing on stdout.
compare() {
  local desc="$1" style="$2" name="$3" bad=() b h
  shift 3
  b="${tmp}/base" h="${tmp}/hook"
  go "${style}" "${name}" "" "${b}"
  go "${style}" "${name}" "${hook}" "${h}"
  if [[ "$(wc -l <"${b}.err")" -ne 1 || "$(cat "${b}.err")" != *": ${name}: command not found" ]]; then
    bad+=("without a handler bash printed something unexpected: $(tr '\n' '|' <"${b}.raw")")
  fi
  [[ "$(cat "${b}.rc")" == 127 ]] || bad+=("without a handler the exit is $(cat "${b}.rc")")
  { cat "${b}.err"; [[ $# -eq 0 ]] || printf '%s\n' "$@"; } >"${tmp}/want"
  if ! cmp -s "${tmp}/want" "${h}.err"; then
    bad+=("stderr: want [$(tr '\n' '|' <"${tmp}/want")] got [$(tr '\n' '|' <"${h}.err")]")
  fi
  [[ "$(cat "${h}.rc")" == 127 ]] || bad+=("exit $(cat "${h}.rc"), not 127")
  [[ ! -s "${h}.out" ]] || bad+=("stdout not empty: $(tr '\n' '|' <"${h}.out")")
  if [[ ${#bad[@]} -eq 0 ]]; then
    tap 0 "${desc}"
  else
    local IFS=';'
    tap 1 "${desc} (${bad[*]})"
  fi
}

# ── A: every claimed style, a known name with all three kinds and an unknown name ────────────────
STYLES=(c c-line3 c-name c-function script script-function stdin interactive interactive-path)
for style in "${STYLES[@]}"; do
  compare "A ${style}: a known name prints bash's own line, then its three answers in file order" \
    "${style}" tlmc-both "${BOTH[@]}"
  compare "A ${style}: an unknown name prints bash's own line alone" "${style}" "${UNKNOWN}"
done

# ── R: the fixture's rows ────────────────────────────────────────────────────────────────────────
compare "R1 instead with a '-' note: no parenthesised note, no trailing spaces" c tlmc-plain "${PLAIN[@]}"
compare "R2 user with a '-' note" c tlmc-user "${USER_ROW[@]}"
compare "R3 a three-field line is skipped" c tlmc-short
compare "R4 a five-field line is skipped" c tlmc-long
compare "R5 an unknown kind is skipped" c tlmc-kind

# ── E: a caller's options, and stdin ────────────────────────────────────────────────────────────
# set -eux in the caller: the handler neither fails early nor traces itself. The caller's own trace
# line (`+ NAME`) is bash's, and appears in the no-handler run too.
b="${tmp}/eb" h="${tmp}/eh"
(cd "${tmp}" && env -i "${ENVS[@]}" "${BASH_BIN}" -c 'set -eux; tlmc-both; echo after' \
  </dev/null >"${b}.out" 2>"${b}.err") && brc=0 || brc=$?
(cd "${tmp}" && env -i "${ENVS[@]}" "BASH_ENV=${hook}" "${BASH_BIN}" -c 'set -eux; tlmc-both; echo after' \
  </dev/null >"${h}.out" 2>"${h}.err") && hrc=0 || hrc=$?
{ cat "${b}.err"; printf '%s\n' "${BOTH[@]}"; } >"${tmp}/want"
if cmp -s "${tmp}/want" "${h}.err" && [[ ${hrc} -eq 127 && ${brc} -eq 127 && ! -s "${h}.out" ]]; then
  tap 0 "E1 under the caller's set -eux: all lines, none traced, the caller's errexit then stops at 127"
else
  tap 1 "E1 under set -eux: rc ${hrc}, want [$(tr '\n' '|' <"${tmp}/want")] got [$(tr '\n' '|' <"${h}.err")] out [$(tr '\n' '|' <"${h}.out")]"
fi

# stdin: data left in a pipe is still there after the handler ran
# shellcheck disable=SC2016 # expanded by the bash under test
out="$(printf 'first\nsecond\n' | (cd "${tmp}" && env -i "${ENVS[@]}" "BASH_ENV=${hook}" "${BASH_BIN}" -c \
  'tlmc-both; IFS= read -r l; printf "stdin=%s\n" "$l"' 2>/dev/null))" || true
if [[ "${out}" == "stdin=first" ]]; then
  tap 0 "E2 the handler reads nothing from stdin: the caller's next read gets the first line"
else
  tap 1 "E2 the caller's next read got '${out}', not 'stdin=first'"
fi

# stdin of endless NULs: a handler that read stdin would never conclude
(cd "${tmp}" && timeout 10 env -i "${ENVS[@]}" "BASH_ENV=${hook}" "${BASH_BIN}" -c 'true; tlmc-both' \
  </dev/zero >/dev/null 2>"${tmp}/z.err") && zrc=0 || zrc=$?
{ printf '%s\n' "${BASH_BIN}: line 1: tlmc-both: command not found"; printf '%s\n' "${BOTH[@]}"; } >"${tmp}/want"
if [[ ${zrc} -eq 127 ]] && cmp -s "${tmp}/want" "${tmp}/z.err"; then
  tap 0 "E3 stdin from /dev/zero: concludes, exit 127, all lines"
else
  tap 1 "E3 stdin from /dev/zero: rc ${zrc} (124 = did not conclude), got [$(tr '\n' '|' <"${tmp}/z.err")]"
fi

# ── D: the data file unreadable or missing: line 1 alone, exit 127 ────────────────────────────────
data_case() { # data_case DESC PATH
  local desc="$1" path="$2" rc=0
  (cd "${tmp}" && env -i "${ENVS[@]}" "TIMELIKE_MISSING_COMMANDS=${path}" "BASH_ENV=${hook}" "${BASH_BIN}" \
    -c 'true; tlmc-both' </dev/null >"${tmp}/d.out" 2>"${tmp}/d.err") || rc=$?
  printf '%s\n' "${BASH_BIN}: line 1: tlmc-both: command not found" >"${tmp}/want"
  if [[ ${rc} -eq 127 ]] && cmp -s "${tmp}/want" "${tmp}/d.err" && [[ ! -s "${tmp}/d.out" ]]; then
    tap 0 "${desc}"
  else
    tap 1 "${desc} (rc ${rc}, got [$(tr '\n' '|' <"${tmp}/d.err")])"
  fi
}
data_case "D1 a missing data file: bash's line alone, exit 127" "${tmp}/no-such-file.tsv"
data_case "D2 a directory as the data file: bash's line alone, exit 127" "${tmp}/d"
cp "${fx}" "${tmp}/unreadable.tsv"
chmod 000 "${tmp}/unreadable.tsv"
if [[ -r "${tmp}/unreadable.tsv" ]]; then
  tap 0 "D3 # SKIP a mode-000 file is readable to uid $(id -u)"
else
  data_case "D3 an unreadable data file: bash's line alone, exit 127" "${tmp}/unreadable.tsv"
fi

# ── P: PATH ──────────────────────────────────────────────────────────────────────────────────────
# Every case above already runs with PATH=/nonexistent, so no external command was found. With PATH
# empty, bash does not search at all: it tries ./NAME, prints its own ENOENT line and never calls the
# handler. That is bash's behaviour, asserted so the claim stays honest: the hook adds nothing there.
# shellcheck disable=SC2016 # expanded by the bash under test
p0="$(cd "${tmp}" && env -i PATH= "TIMELIKE_MISSING_COMMANDS=${fx}" "${BASH_BIN}" -c 'tlmc-both' </dev/null 2>&1)" || true
# shellcheck disable=SC2016 # expanded by the bash under test
p1="$(cd "${tmp}" && env -i PATH= "TIMELIKE_MISSING_COMMANDS=${fx}" "BASH_ENV=${hook}" \
  TIMELIKE_JOURNAL_EXIT=/nonexistent "${BASH_BIN}" -c 'tlmc-both' </dev/null 2>&1)" || true
if [[ "${p0}" == "${p1}" ]]; then
  tap 0 "P1 PATH empty: bash never reaches the handler, and the output is bash's alone"
else
  tap 1 "P1 PATH empty: with the hook [${p1//$'\n'/|}] differs from without [${p0//$'\n'/|}]"
fi

# ── F: the handler forks nothing ─────────────────────────────────────────────────────────────────
# The missing name is the last command of a `-c` string, so bash runs it without forking (measured:
# bash 5.2). RLIMIT_NPROC=1 then makes any fork by the handler fail (a command substitution, a pipe,
# an external command), and bash's fork retries outlast the timeout. Root is exempt from RLIMIT_NPROC.
nofork() { # nofork HOOKFILE → stderr then "rc=N"
  # shellcheck disable=SC2016 # expanded by the bash under test
  (cd "${tmp}" && timeout 5 env -i "${ENVS[@]}" "HOOK=$1" "${BASH_BIN}" -c \
    'ulimit -u 1 2>/dev/null; . "$HOOK"; tlmc-both' </dev/null 2>&1) && echo "rc=0" || echo "rc=$?"
}
# shellcheck disable=SC2016 # handler bodies, written verbatim
{
  printf '%s\n' 'command_not_found_handle() { printf "stub %s\n" "$1" >&2; return 127; }' >"${tmp}/stub-builtin.bash"
  printf '%s\n' 'command_not_found_handle() { local x; x="$(printf y)"; printf "stub %s\n" "$x" >&2; return 127; }' >"${tmp}/stub-fork.bash"
}
c_builtin="$(nofork "${tmp}/stub-builtin.bash")"
c_fork="$(nofork "${tmp}/stub-fork.bash")"
if [[ "${c_builtin}" != $'stub tlmc-both\nrc=127' ]]; then
  tap 0 "X2 # SKIP bash itself forked before the handler here (got '${c_builtin//$'\n'/ }'); F1 not run"
elif [[ "${c_fork}" == *"stub y"* ]]; then
  tap 0 "X2 # SKIP the no-fork probe cannot fail here (uid $(id -u) is not held to RLIMIT_NPROC); F1 not run"
else
  tap 0 "X2 the no-fork probe lets a builtin-only handler through and catches one that forks"
  base="$(nofork "${tmp}/empty-hook.bash")"
  got="$(nofork "${hook_real}")"
  want="$(printf '%s\n' "${base%$'\n'rc=127}" "${BOTH[@]}" "rc=127")"
  if [[ "${base}" == *$'\nrc=127' && "${got}" == "${want}" ]]; then
    tap 0 "F1 the handler runs with forking impossible: all lines, exit 127"
  else
    tap 1 "F1 with forking impossible: want [${want//$'\n'/|}] got [${got//$'\n'/|}]"
  fi
fi

# ── X1: the same comparison against an EMPTY hook must fail ─────────────────────────────────────
real_n=${n}
real_failures=${failures}
hook="${tmp}/empty-hook.bash"
x1_out="$(compare "X1 probe" c tlmc-both "${BOTH[@]}")"
hook="${hook_real}"
n=${real_n}
failures=${real_failures}
if [[ "${x1_out}" == "not ok "* ]]; then
  tap 0 "X1 with an empty hook, the known-name comparison fails"
else
  tap 1 "X1 with an empty hook the known-name comparison still passes: it cannot fail"
fi

echo "1..${n}"
if [[ ${failures} -ne 0 ]]; then
  echo "# FAILED ${failures} of ${n} (advisory host lane)"
  exit 1
fi
echo "# passed ${n} of ${n} (advisory host lane: the handler's logic, not the image)"
