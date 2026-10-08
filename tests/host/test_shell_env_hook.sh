#!/usr/bin/env bash
# Host lane, ADVISORY (tasks.md T052; research R10). Unit-tests the LOGIC of the container-derived
# hook, image/rootfs/etc/timelike/shell-env.bash (modify.md F001, F002, F004; SC-8, SC-9), with
# the host's bash, against fake cgroup cpu.max and /proc/self/status files passed through the
# hook's test-only overrides TIMELIKE_CGROUP_CPU_MAX and TIMELIKE_PROC_STATUS. It does NOT prove
# the image: the Docker lane (tests/e2e/container-derived-defaults.bats) is authoritative.
#
# Every case starts a fresh `env -i` bash with stdin from /dev/null (a socket on stdin makes
# Debian/Ubuntu bash read /etc/bash.bashrc even under -c) and PATH=/nonexistent, so an external
# command in the hook would fail and show up as a missing value. The hook is reached through
# BASH_ENV, as `bash -c` reaches it in the image, unless a case sources it explicitly.
#
# Cases: CPU figure (C), explicit wins (E), secret strip (S), idempotent / silent / never fails /
# leaves nothing behind (Q), no fork (F), non-bash no-op (N).
# Self-checks (lore cross-stack P004/P005: a test that cannot fail proves nothing):
#   X1  the C, E and S assertions run against an EMPTY hook must all fail
#   X2  the no-fork probe must catch a hook variant that forks once, else it is reported as a skip
set -euo pipefail

echo "# ADVISORY host lane: the shell-env hook's logic on the host's bash, NOT the image"

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
hook_real="${repo}/image/rootfs/etc/timelike/shell-env.bash"
[[ -r "${hook_real}" ]] || { echo "Bail out! missing ${hook_real}"; exit 1; }
BASH_BIN="$(command -v bash)"

tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT
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

# fake NAME CONTENT — write a fake source file, print its path. CONTENT "-" = no such file.
fake() {
  if [[ "$2" == "-" ]]; then
    printf '%s' "${tmp}/absent-$1"
  else
    printf '%b' "$2" >"${tmp}/$1"
    printf '%s' "${tmp}/$1"
  fi
}

# run_hook CPU_MAX STATUS PROBE [VAR=VALUE]... — stdout+stderr of `bash -c PROBE` with the hook as
# BASH_ENV and the two fake files. CPU_MAX/STATUS are printf %b contents, or "-" for "no file".
run_hook() {
  local cm st probe="$3"
  cm="$(fake cpu.max "$1")"
  st="$(fake status "$2")"
  shift 3
  (cd "${tmp}" && env -i PATH=/nonexistent HOME="${tmp}" BASH_ENV="${hook}" \
    TIMELIKE_CGROUP_CPU_MAX="${cm}" TIMELIKE_PROC_STATUS="${st}" "$@" \
    "${BASH_BIN}" -c "${probe}" </dev/null 2>&1) || true
}

value_of() { # value_of KEY OUTPUT
  local key="$1" out="$2" l
  while IFS= read -r l; do
    if [[ "${l}" == "${key}="* ]]; then printf '%s' "${l#"${key}="}"; return 0; fi
  done <<<"${out}"
  printf '<missing>'
}

# check DESCRIPTION OUTPUT KEY=WANT... — one TAP line; lists every mismatch.
check() {
  local desc="$1" out="$2" e key want got bad=()
  shift 2
  for e in "$@"; do
    key="${e%%=*}"
    want="${e#*=}"
    got="$(value_of "${key}" "${out}")"
    [[ "${got}" == "${want}" ]] || bad+=("${key}: want '${want}' got '${got}'")
  done
  if [[ ${#bad[@]} -eq 0 ]]; then
    tap 0 "${desc}"
  else
    local IFS=';'
    tap 1 "${desc} (${bad[*]})"
  fi
}

# shellcheck disable=SC2016 # expanded by the bash under test
JOBS='for v in TIMELIKE_CPUS MAKEFLAGS CMAKE_BUILD_PARALLEL_LEVEL CARGO_BUILD_JOBS GOMAXPROCS PYTEST_XDIST_AUTO_NUM_WORKERS PYTHON_CPU_COUNT; do printf "%s=%s\n" "$v" "${!v-<unset>}"; done'

jobs_all() { # jobs_all N → the seven KEY=WANT pairs for a figure of N
  printf '%s\n' "TIMELIKE_CPUS=$1" "MAKEFLAGS=-j$1" "CMAKE_BUILD_PARALLEL_LEVEL=$1" "CARGO_BUILD_JOBS=$1" \
    "GOMAXPROCS=$1" "PYTEST_XDIST_AUTO_NUM_WORKERS=$1" "PYTHON_CPU_COUNT=$1"
}

# presence probe for secret-strip cases: NAME=present|absent for each listed name
presence_probe() {
  # shellcheck disable=SC2016 # expanded by the bash under test
  printf 'for v in %s; do if [ -n "${!v+x}" ]; then printf "%%s=present\\n" "$v"; else printf "%%s=absent\\n" "$v"; fi; done' "$*"
}

SECRETS=(GITHUB_TOKEN MY_API_KEY DB_PASSWORD npm_config__authToken AWS_SECRET_ACCESS_KEY
  deploy_passphrase SMTP_PASS SERVICE_CREDENTIALS OPENAI_APIKEY PRIVATEKEY SSH_PASSWD X_TOKENS
  Y_SECRETS Z_PASSWORDS a_credential K_KEYS ACCESSKEY AUTHTOKEN _KEY Api__Key PGPASSWORD GHTOKEN
  OAUTH_CLIENTSECRET)
LOOKALIKES=(GIT_ASKPASS SSH_ASKPASS TOKENIZERS_PARALLELISM KEYBOARD_LAYOUT MONKEY PASSAGE_COUNT
  KEYTIMEOUT GIT_CONFIG_KEY_0 GIT_CONFIG_KEY_12 TIMELIKE_ENV_ALLOW)

# ── The assertions (run against the real hook, and again against an empty one for X1) ──────────
# Each prints TAP lines through check/tap. X1 counts how many of them fail.
run_cases() {
  local out args=() v

  # C: the CPU figure
  out="$(run_hook '150000 100000\n' 'Name:\tbash\nCpus_allowed_list:\t0-7\n' "${JOBS}")"
  mapfile -t args < <(jobs_all 2)
  check "C1 quota 1.5 CPUs of 8: ceil gives 2, all six defaults follow" "${out}" "${args[@]}"
  out="$(run_hook 'max 100000\n' 'Cpus_allowed_list:\t0-3,8,10-11\n' "${JOBS}")"
  mapfile -t args < <(jobs_all 7)
  check "C2 no quota (max): the affinity count of 0-3,8,10-11 is 7" "${out}" "${args[@]}"
  out="$(run_hook '800000 100000\n' 'Cpus_allowed_list:\t0-1\n' "${JOBS}")"
  check "C3 quota 8 CPUs, affinity 2: affinity caps it" "${out}" TIMELIKE_CPUS=2 MAKEFLAGS=-j2
  out="$(run_hook '50000 100000\n' 'Cpus_allowed_list:\t0-7\n' "${JOBS}")"
  check "C4 quota 0.5 CPU rounds up to 1" "${out}" TIMELIKE_CPUS=1 GOMAXPROCS=1
  out="$(run_hook '100001 100000\n' 'Cpus_allowed_list:\t0-63\n' "${JOBS}")"
  check "C5 quota just over 1 CPU rounds up to 2" "${out}" TIMELIKE_CPUS=2
  out="$(run_hook '-' 'Cpus_allowed_list:\t0-5\n' "${JOBS}")"
  check "C6 no cpu.max (cgroup v1 host): affinity 6" "${out}" TIMELIKE_CPUS=6 CARGO_BUILD_JOBS=6
  out="$(run_hook '-' '-' "${JOBS}")"
  check "C7 neither file readable: 1" "${out}" TIMELIKE_CPUS=1 MAKEFLAGS=-j1
  out="$(run_hook 'abc def\n' 'Cpus_allowed_list:\t0-3\n' "${JOBS}")"
  check "C8 unparseable cpu.max is ignored: affinity 4" "${out}" TIMELIKE_CPUS=4
  out="$(run_hook '200000 100000\n' 'Cpus_allowed_list:\tbogus\n' "${JOBS}")"
  check "C9 unparseable affinity is ignored: quota 2" "${out}" TIMELIKE_CPUS=2
  out="$(run_hook '300000 0\n' 'Cpus_allowed_list:\t0-4\n' "${JOBS}")"
  check "C10 a zero period is ignored: affinity 5" "${out}" TIMELIKE_CPUS=5

  # E: explicit values win; empty counts as unset; TIMELIKE_CPUS is always recomputed
  out="$(run_hook '200000 100000\n' 'Cpus_allowed_list:\t0-7\n' "${JOBS}" \
    MAKEFLAGS=-j9 GOMAXPROCS=3 CARGO_BUILD_JOBS=4)"
  check "E1 explicit MAKEFLAGS, GOMAXPROCS, CARGO_BUILD_JOBS win; the rest derived" "${out}" \
    MAKEFLAGS=-j9 GOMAXPROCS=3 CARGO_BUILD_JOBS=4 CMAKE_BUILD_PARALLEL_LEVEL=2 PYTHON_CPU_COUNT=2
  out="$(run_hook '200000 100000\n' 'Cpus_allowed_list:\t0-7\n' "${JOBS}" MAKEFLAGS= PYTHON_CPU_COUNT=)"
  check "E2 an empty MAKEFLAGS or PYTHON_CPU_COUNT counts as unset" "${out}" MAKEFLAGS=-j2 PYTHON_CPU_COUNT=2
  out="$(run_hook '200000 100000\n' 'Cpus_allowed_list:\t0-7\n' "${JOBS}" TIMELIKE_CPUS=99)"
  check "E3 TIMELIKE_CPUS itself is recomputed, not taken from the caller" "${out}" TIMELIKE_CPUS=2
  out="$(run_hook '200000 100000\n' 'Cpus_allowed_list:\t0-7\n' "${JOBS}" \
    'MAKEFLAGS= -j4 --jobserver-auth=fifo:/tmp/x')"
  check "E4 a parent make's MAKEFLAGS (jobserver) is left alone; the rest derived" "${out}" \
    'MAKEFLAGS= -j4 --jobserver-auth=fifo:/tmp/x' CMAKE_BUILD_PARALLEL_LEVEL=2

  # S: the secret strip
  args=()
  for v in "${SECRETS[@]}" "${LOOKALIKES[@]}"; do args+=("${v}=value-${v}"); done
  out="$(run_hook 'max 100000\n' 'Cpus_allowed_list:\t0\n' \
    "$(presence_probe "${SECRETS[@]}" "${LOOKALIKES[@]}")" "${args[@]}")"
  local want=()
  for v in "${SECRETS[@]}"; do want+=("${v}=absent"); done
  check "S1 secret-shaped names are stripped (any case, camelCase, leading/double underscores)" "${out}" "${want[@]}"
  want=()
  for v in "${LOOKALIKES[@]}"; do want+=("${v}=present"); done
  check "S2 look-alikes stay (ASKPASS, TOKENIZERS_, KEYBOARD_, GIT_CONFIG_KEY_n, ...)" "${out}" "${want[@]}"

  out="$(run_hook 'max 100000\n' 'Cpus_allowed_list:\t0\n' \
    "$(presence_probe A_TOKEN B_KEY C_SECRET D_TOKEN)" \
    $'TIMELIKE_ENV_ALLOW=A_TOKEN,B_KEY\t C_SECRET\n' A_TOKEN=1 B_KEY=2 C_SECRET=3 D_TOKEN=4)"
  check "S3 TIMELIKE_ENV_ALLOW keeps exact names split on commas, tabs, spaces and newlines" "${out}" \
    A_TOKEN=present B_KEY=present C_SECRET=present D_TOKEN=absent
  out="$(run_hook 'max 100000\n' 'Cpus_allowed_list:\t0\n' \
    "$(presence_probe A_TOKEN B_TOKEN)" 'TIMELIKE_ENV_ALLOW=a_token B_TOK' A_TOKEN=1 B_TOKEN=2)"
  check "S4 the allow-list is exact: another case or a prefix does not match" "${out}" \
    A_TOKEN=absent B_TOKEN=absent

  # The image's own git layer survives the strip: GIT_CONFIG_KEY_0 names core.hooksPath.
  # shellcheck disable=SC2016 # expanded by the bash under test
  out="$(run_hook 'max 100000\n' 'Cpus_allowed_list:\t0\n' \
    'cd / && printf "hooks=%s\n" "$(/usr/bin/git config --get core.hooksPath 2>&1)"' \
    GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.hooksPath GIT_CONFIG_VALUE_0=/opt/timelike/git-hooks \
    GIT_CONFIG_SYSTEM=/dev/null GIT_CONFIG_GLOBAL=/dev/null)"
  check "S5 git still reads the image's GIT_CONFIG_* layer after the strip" "${out}" hooks=/opt/timelike/git-hooks
}

run_cases

# Why S5 matters: git refuses to run when GIT_CONFIG_COUNT names a key that is gone.
if (cd / && env -i PATH=/usr/bin:/bin GIT_CONFIG_COUNT=1 GIT_CONFIG_VALUE_0=/dev/null \
  git config --get core.hooksPath </dev/null >/dev/null 2>&1); then
  tap 1 "S6 control: git with GIT_CONFIG_COUNT=1 and no GIT_CONFIG_KEY_0 unexpectedly works"
else
  tap 0 "S6 control: without GIT_CONFIG_KEY_0 git fails outright — why the hook exempts GIT_CONFIG_KEY_<n>"
fi

# ── Q: idempotent, silent, never fails the shell, leaves nothing behind ──────────────────────────
cm="$(fake cpu.max '200000 100000\n')"
st="$(fake status 'Cpus_allowed_list:\t0-7\n')"
# shellcheck disable=SC2016 # expanded by the bash under test
q_out="$(cd "${tmp}" && env -i PATH=/nonexistent HOME="${tmp}" TIMELIKE_CGROUP_CPU_MAX="${cm}" \
  TIMELIKE_PROC_STATUS="${st}" GITHUB_TOKEN=x MAKEFLAGS= HOOK="${hook}" "${BASH_BIN}" -c '
  set -euo pipefail
  opts_before="$-|$(shopt -po)"
  once_out="$(. "$HOOK" 2>&1; printf "status=%s" "$?")"
  . "$HOOK"
  env1="$(declare -px)"
  . "$HOOK"
  env2="$(declare -px)"
  opts_after="$-|$(shopt -po)"
  printf "once=%s\n" "$once_out"
  [ "$env1" = "$env2" ] && printf "idempotent=yes\n" || printf "idempotent=no\n"
  [ "$opts_before" = "$opts_after" ] && printf "options=unchanged\n" || printf "options=changed\n"
  left=""
  for v in cpu_max status_file quota period line list item lo hi quota_cpus affinity_cpus cpus allow name upper; do
    [ -z "${!v+x}" ] || left+="$v "
  done
  printf "leftover_vars=%s\n" "${left:-none}"
  # command_not_found_handle stays defined on purpose (feature 007 slice 1, spec FR-14); nothing else may.
  funcs="$(declare -F)"
  [ "${funcs}" != "${funcs/declare -f command_not_found_handle/}" ] && printf "cnf_handler=defined\n" || printf "cnf_handler=absent\n"
  funcs="${funcs/declare -f command_not_found_handle/}"
  printf "leftover_funcs=%s\n" "${funcs:-none}"
' </dev/null 2>&1)" || true
check "Q1 sourcing twice equals sourcing once; errexit/nounset/pipefail survive unchanged; silent, status 0" \
  "${q_out}" once=status=0 idempotent=yes options=unchanged
check "Q2 no local variable or function is left behind but command_not_found_handle (007 s1, kept on purpose)" "${q_out}" leftover_vars=none leftover_funcs=none cnf_handler=defined

# Silent and non-fatal even when both sources are missing or are directories, under -eux.
q_out="$(cd "${tmp}" && env -i PATH=/nonexistent HOME="${tmp}" TIMELIKE_CGROUP_CPU_MAX="${tmp}" \
  TIMELIKE_PROC_STATUS="${tmp}/absent" BASH_ENV="${hook}" "${BASH_BIN}" -euxc ':' </dev/null 2>&1)" && rc=0 || rc=$?
# xtrace of the probe itself (`+ :`) is the caller's own trace, not the hook's.
q_out="${q_out//+ :/}"
q_out="${q_out//$'\n'/}"
if [[ ${rc} -eq 0 && -z "${q_out}" ]]; then
  tap 0 "Q3 unreadable sources under bash -eux: no output, shell continues (rc 0)"
else
  tap 1 "Q3 unreadable sources under bash -eux: rc ${rc}, output '${q_out}'"
fi

# The login-shell double source (profile.d, then BASH_ENV) gives the same environment as one.
# shellcheck disable=SC2016 # expanded by the bash under test
one="$(cd "${tmp}" && env -i PATH=/nonexistent HOME="${tmp}" TIMELIKE_CGROUP_CPU_MAX="${cm}" \
  TIMELIKE_PROC_STATUS="${st}" A_KEY=1 BASH_ENV="${hook}" "${BASH_BIN}" -c 'declare -px' </dev/null 2>&1)"
# shellcheck disable=SC2016 # expanded by the bash under test
two="$(cd "${tmp}" && env -i PATH=/nonexistent HOME="${tmp}" TIMELIKE_CGROUP_CPU_MAX="${cm}" \
  TIMELIKE_PROC_STATUS="${st}" A_KEY=1 BASH_ENV="${hook}" HOOK="${hook}" "${BASH_BIN}" -c '. "$HOOK"; unset HOOK; declare -px' </dev/null 2>&1)"
if [[ "${one}" == "${two}" ]]; then
  tap 0 "Q4 BASH_ENV plus an explicit source (the bash -lc path) equals BASH_ENV alone"
else
  tap 1 "Q4 BASH_ENV plus an explicit source differs from BASH_ENV alone"
fi

# ── F: no fork per shell start ──────────────────────────────────────────────────────────────────
# RLIMIT_NPROC=1 makes every fork by this uid fail (the uid already runs more than one process), so
# a hook that forks — a command substitution, a pipe, an external command — loses its values or
# stalls in bash's fork retries (bounded by timeout). Root is exempt from RLIMIT_NPROC; X2 reports it.
nofork_probe() { # nofork_probe HOOKFILE → "TIMELIKE_CPUS=..." or a timeout marker
  local h="$1"
  # shellcheck disable=SC2016 # expanded by the bash under test
  (cd "${tmp}" && timeout 5 env -i PATH=/nonexistent HOME="${tmp}" TIMELIKE_CGROUP_CPU_MAX="${cm}" \
    TIMELIKE_PROC_STATUS="${st}" HOOK="${h}" "${BASH_BIN}" -c \
    'ulimit -u 1 2>/dev/null; . "$HOOK"; printf "TIMELIKE_CPUS=%s\n" "${TIMELIKE_CPUS-<unset>}"' \
    </dev/null 2>/dev/null) || echo "rc=$?"
}
# shellcheck disable=SC2016 # a line of shell code, written to the variant hook verbatim
{ cat "${hook_real}"; printf '%s\n' 'TIMELIKE_CPUS="$(printf %s "${TIMELIKE_CPUS-}")"'; } >"${tmp}/forking-hook.bash"
control="$(nofork_probe "${tmp}/forking-hook.bash")"
if [[ "$(value_of TIMELIKE_CPUS "${control}")" == 2 ]]; then
  tap 0 "X2 # SKIP the no-fork probe cannot fail here (uid $(id -u) is not held to RLIMIT_NPROC); F1 not run"
else
  tap 0 "X2 the no-fork probe catches a hook that forks once (got '${control//$'\n'/ }')"
  out="$(nofork_probe "${hook_real}")"
  check "F1 the hook runs with forking impossible (bash builtins only)" "${out}" TIMELIKE_CPUS=2
fi

# ── N: a no-op outside bash ─────────────────────────────────────────────────────────────────────
sh_bin="$(command -v dash || command -v sh)"
# shellcheck disable=SC2016 # expanded by the shell under test
out="$(cd "${tmp}" && env -i PATH=/nonexistent GITHUB_TOKEN=kept HOOK="${hook}" "${sh_bin}" -c \
  '. "$HOOK"; printf "rc=%s\n" "$?"; printf "GITHUB_TOKEN=%s\n" "${GITHUB_TOKEN-<unset>}"; printf "TIMELIKE_CPUS=%s\n" "${TIMELIKE_CPUS-<unset>}"' \
  </dev/null 2>&1)" || true
check "N1 sourced by ${sh_bin##*/}: returns 0, silent, changes nothing" "${out}" rc=0 GITHUB_TOKEN=kept TIMELIKE_CPUS='<unset>'
if [[ "$(grep -cv '^\(rc\|GITHUB_TOKEN\|TIMELIKE_CPUS\)=' <<<"${out}")" != 0 ]]; then
  tap 1 "N2 sourced by ${sh_bin##*/}: printed something (${out//$'\n'/ | })"
else
  tap 0 "N2 sourced by ${sh_bin##*/}: printed nothing"
fi

# ── J: the session journal's shell record (feature 009; research R1) ─────────────────────────────
# The hook sets an EXIT trap sourcing TIMELIKE_JOURNAL_EXIT (test-only override of
# /etc/timelike/journal-exit.bash) in a non-interactive bash with an execution string. Each case gets
# its own scratch root; the record is read back and parsed as JSON by the host's python3.
jexit="${repo}/image/rootfs/etc/timelike/journal-exit.bash"
[[ -r "${jexit}" ]] || { echo "Bail out! missing ${jexit}"; exit 1; }
# jrun STYLE CMD [VAR=VALUE]... — run CMD under the hook with a fresh scratch root; prints "rc=N" then the
# root's path on the next line. STYLE: c | lc-double (BASH_ENV plus an explicit source: the -lc path).
jrun() {
  local style="$1" cmd="$2" root rc
  shift 2
  # mktemp, not a counter: jrun runs in a command substitution, so a counter would never advance
  root="$(mktemp -d "${tmp}/jroot.XXXXXX")" && rmdir "${root}"
  if [[ "${style}" == c ]]; then
    (cd "${tmp}" && env -i PATH=/usr/bin:/bin HOME="${tmp}" BASH_ENV="${hook_real}" TIMELIKE_JOURNAL_EXIT="${jexit}" \
      TIMELIKE_SCRATCH_ROOT="${root}" "$@" "${BASH_BIN}" -c "${cmd}" </dev/null >/dev/null 2>&1) && rc=0 || rc=$?
  else
    # shellcheck disable=SC2016 # expanded by the bash under test
    (cd "${tmp}" && env -i PATH=/usr/bin:/bin HOME="${tmp}" BASH_ENV="${hook_real}" TIMELIKE_JOURNAL_EXIT="${jexit}" \
      TIMELIKE_SCRATCH_ROOT="${root}" HOOK="${hook_real}" "$@" "${BASH_BIN}" -c ". \"\$HOOK\"; ${cmd}" \
      </dev/null >/dev/null 2>&1) && rc=0 || rc=$?
  fi
  printf 'rc=%s\n%s\n' "${rc}" "${root}"
}
# jread ROOT SESSION — one "key=value" line per fact of ROOT/SESSION/shell.jsonl
jread() {
  python3 -I - "$1" "$2" <<'PY'
import json, os, stat, sys
root, session = sys.argv[1], sys.argv[2]
f = os.path.join(root, session, "shell.jsonl")
if not os.path.exists(f):
    print("lines=0")
    sys.exit(0)
raw = open(f, "rb").read().decode()
lines = raw.splitlines()
print(f"lines={len(lines)}")
print(f"root_mode={stat.S_IMODE(os.stat(root).st_mode):o}")
print(f"dir_mode={stat.S_IMODE(os.stat(os.path.dirname(f)).st_mode):o}")
print(f"file_mode={stat.S_IMODE(os.stat(f).st_mode):o}")
for i, line in enumerate(lines):
    try:
        d = json.loads(line)
    except ValueError:
        print(f"bad_json={i}")
        continue
    for k in ("exit", "style", "session", "agent", "cut_bytes", "kind", "v"):
        print(f"{i}.{k}={d.get(k)}")
    print(f"{i}.cmd_len={len(d.get('cmd', ''))}")
    print(f"{i}.cmd={d.get('cmd')!r}")
    print(f"{i}.ordered={int(d['end_us']) >= int(d['start_us']) > 0}")
PY
}

# J1 exit status preserved, and the entry records it — each case its own shell
for jc in 'false:1' 'exit 7:7' 'ls /nonexistent-dir-j1:2' 'sh -c "exit 3":3' 'set -e; false; echo no:1' 'true:0'; do
  jcmd="${jc%:*}" jwant="${jc##*:}"
  r="$(jrun c "${jcmd}" TIMELIKE_SESSION=j1)"
  facts="$(jread "$(sed -n 2p <<<"${r}")" j1)"
  check "J1 '${jcmd}': the shell still exits ${jwant}, and the one entry records exit ${jwant}" \
    "$(head -1 <<<"${r}")
${facts}" "rc=${jwant}" lines=1 "0.exit=${jwant}" 0.style='bash -c' 0.kind=shell 0.v=1 0.ordered=True
done

# J2 the login path sources the hook twice: still one entry; agent and session recorded
r="$(jrun lc-double 'true' TIMELIKE_SESSION=j2 TIMELIKE_AGENT=a1)"
facts="$(jread "$(sed -n 2p <<<"${r}")" j2)"
check "J2 hook sourced twice (the bash -lc path): one entry, agent and session recorded" "${facts}" \
  lines=1 0.session=j2 0.agent=a1 0.exit=0

# J3 modes: the root as agentio makes it (1777), the session private (0700), the record 0600
r="$(jrun c ':' TIMELIKE_SESSION=j3)"
facts="$(jread "$(sed -n 2p <<<"${r}")" j3)"
check "J3 a missing root is made 1777, the session 0700, the record 0600" "${facts}" \
  root_mode=1777 dir_mode=700 file_mode=600

# J4 a hostile command line: quotes, backslashes, control bytes, tab, newline, over 4096 characters
long="$(printf 'x%.0s' $(seq 5000))"
hostile=$'printf "%s" "a\\"b\\\\c\x01d\te" >/dev/null\n: '"${long}"
r="$(jrun c "${hostile}" TIMELIKE_SESSION=j4)"
facts="$(jread "$(sed -n 2p <<<"${r}")" j4)"
check "J4 a hostile command line is one valid JSON line, cut at 4096 with its cut count" "${facts}" \
  lines=1 0.cmd_len=4096 "0.cut_bytes=$((${#hostile} - 4096))"
if grep -q '^bad_json' <<<"${facts}"; then tap 1 "J4b the hostile line is not valid JSON"; else tap 0 "J4b no invalid JSON line"; fi

# J5 not captured: an interactive shell, a command with its own EXIT trap, an invalid session, an agent
# value outside the character set (recorded as empty)
r="$(jrun c 'trap "echo mine" EXIT; true' TIMELIKE_SESSION=j5)"
check "J5 a command that sets its own EXIT trap replaces ours: no entry (a stated limit)" \
  "$(jread "$(sed -n 2p <<<"${r}")" j5)" lines=0
root="${tmp}/jroot-i"
(cd "${tmp}" && env -i PATH=/usr/bin:/bin HOME="${tmp}" BASH_ENV="${hook_real}" TIMELIKE_JOURNAL_EXIT="${jexit}" \
  TIMELIKE_SCRATCH_ROOT="${root}" TIMELIKE_SESSION=j5i "${BASH_BIN}" --norc -i -c 'true' </dev/null >/dev/null 2>&1) || true
# an interactive shell ignores BASH_ENV; source the hook explicitly to test its own guard
# shellcheck disable=SC2016 # expanded by the bash under test
(cd "${tmp}" && env -i PATH=/usr/bin:/bin HOME="${tmp}" HOOK="${hook_real}" TIMELIKE_JOURNAL_EXIT="${jexit}" \
  TIMELIKE_SCRATCH_ROOT="${root}" TIMELIKE_SESSION=j5i "${BASH_BIN}" --norc -i -c '. "$HOOK"; true' </dev/null >/dev/null 2>&1) || true
check "J5b an interactive shell is not captured" "$(jread "${root}" j5i)" lines=0
r="$(jrun c 'true' 'TIMELIKE_SESSION=bad session')"
if [[ -e "$(sed -n 2p <<<"${r}")" ]]; then
  tap 1 "J5c an invalid session id: something was written under the root"
else
  tap 0 "J5c an invalid session id: nothing written (no root made)"
fi
r="$(jrun c 'true' TIMELIKE_SESSION=j5d 'TIMELIKE_AGENT=has space')"
check "J5d an agent outside the character set is recorded as empty" "$(jread "$(sed -n 2p <<<"${r}")" j5d)" \
  lines=1 0.agent=

# J6 no fork at shell start with the trap set (F1's probe); the session directory exists already, so
# the exit file needs no mkdir either
mkdir -p "${tmp}/jroot-f/j6" && chmod 700 "${tmp}/jroot-f/j6"
# shellcheck disable=SC2016 # expanded by the bash under test
out="$(cd "${tmp}" && timeout 5 env -i PATH=/nonexistent HOME="${tmp}" TIMELIKE_CGROUP_CPU_MAX="${cm}" \
  TIMELIKE_PROC_STATUS="${st}" HOOK="${hook_real}" TIMELIKE_JOURNAL_EXIT="${jexit}" \
  TIMELIKE_SCRATCH_ROOT="${tmp}/jroot-f" TIMELIKE_SESSION=j6 "${BASH_BIN}" -c \
  'ulimit -u 1 2>/dev/null; . "$HOOK"; printf "TIMELIKE_CPUS=%s\n" "${TIMELIKE_CPUS-<unset>}"' \
  </dev/null 2>/dev/null)" || out="rc=$?"
if [[ "$(value_of TIMELIKE_CPUS "${control}")" == 2 ]]; then
  tap 0 "J6 # SKIP the no-fork probe cannot fail here (as X2)"
else
  check "J6 with the journal's trap set, the hook and the exit file run with forking impossible" \
    "${out}
$(jread "${tmp}/jroot-f" j6)" TIMELIKE_CPUS=2 lines=1 0.exit=0
fi

# ── X1: the same C/E/S assertions against an EMPTY hook must all fail ───────────────────────────
real_n=${n}
real_failures=${failures}
hook="${tmp}/empty-hook.bash"
x1_out="$(run_cases)"
hook="${hook_real}"
x1_total="$(grep -c '^\(ok\|not ok\) ' <<<"${x1_out}" || true)"
x1_passed="$(grep '^ok ' <<<"${x1_out}" | sed 's/^ok [0-9]* - //' || true)"
n=${real_n}
failures=${real_failures}
# S2 and S5 hold without any hook by nature (nothing is stripped, git untouched), so
# only the assertions that need the hook are required to fail.
x1_unexpected="$(grep -v '^\(S2\|S5\) ' <<<"${x1_passed}" || true)"
if [[ -z "${x1_unexpected}" && "${x1_total}" -gt 0 ]]; then
  tap 0 "X1 with an empty hook, every C, E, S1, S3 and S4 assertion fails (${x1_total} run)"
else
  tap 1 "X1 with an empty hook these still pass — they cannot fail: ${x1_unexpected//$'\n'/; }"
fi

echo "1..${n}"
if [[ ${failures} -ne 0 ]]; then
  echo "# FAILED ${failures} of ${n} (advisory host lane)"
  exit 1
fi
echo "# passed ${n} of ${n} (advisory host lane: the hook's logic, not the image)"
