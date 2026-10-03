#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# shellcheck disable=SC2030,SC2031 # sections interleave checks and @tests; bats runs each @test in its own subshell by design
# Slice 1 (natural) environment criteria (tasks.md T051; modify.md F001–F004; spec FR-15–FR-18):
#   SC-8  "Build parallelism defaults (make jobs, test-runner workers, compiler jobs) are derived from
#         the container's CPU limit rather than the host's CPU count."
#   SC-9  "Secret-shaped environment variables (names matching key, token, secret, password patterns)
#         are absent from the agent's environment unless explicitly allow-listed."
#   SC-10 "The timezone defaults to UTC and interactive language REPLs default to their basic,
#         scriptable prompt mode."
#
# Every command is started from OUTSIDE the image through the styles in helpers.bash (bash -c,
# bash -lc, bash -ic; sh -c where the default is static), and only READS: nothing here sources the
# hook or sets a default the environment is supposed to provide (spec Assumption 1). A `-e` flag
# appears only where it is the INPUT a criterion is about: the secret-shaped variables of SC-9, the
# explicit value of SC-8's explicit-wins case, and TERM for the REPL (see SC-10).
#
# SC-8 cannot be shown in the compose service: it sets no CPU limit, so its figure IS the host's.
# setup_file starts throwaway containers from the verified image instead (helpers.bash):
#   quota   --cpus (L-1).5, L = 2 when the host has >= 3 CPUs, else 1. The hook must give L:
#           ceil(quota/period) rounds the half up, and L is below the host's count by construction
#   cpuset  --cpuset-cpus <one CPU>, no quota: cpu.max reads "max", so the affinity cap alone gives 1
# "The host's CPU count" is read from the daemon (docker info NCPU) and from the affinity the agent
# container actually has; the smaller one bounds L, so a daemon restricted by cpuset cannot make the
# test vacuous. Both limits are read back directly from the throwaway containers' cgroup and status
# files before any assertion relies on them (lore cross-stack P001).
#
# FLAGGED (T051): on a host with fewer than 2 usable CPUs no limit can sit below the host's count, so
# "rather than the host's" cannot be shown. The SC-8 tests then FAIL with that reason, rather than
# skip: a bats skip leaves the lane green with the criterion unexecuted, and the cycle's success
# metric is "all executed". SC-9 and SC-10 are unaffected.
#
# Limit, recorded rather than tested (spec Out of Scope; modify.md F004): plain `sh -c` and direct
# execs of non-shell binaries read no startup file, so SC-8 and SC-9 are not claimed there.

load helpers

# The limited containers' names are unique per run; the label lets remove_stale_throwaways clean up
# after a run that died before teardown_file.
setup_file() {
  stamp_check
  remove_stale_throwaways
  SC8_ERROR=""
  SC8_QUOTA="timelike-sc8-quota-${RANDOM}${RANDOM}"
  SC8_CPUSET="timelike-sc8-cpuset-${RANDOM}${RANDOM}"
  export SC8_ERROR SC8_QUOTA SC8_CPUSET
  sc8_prepare || true
  export SC8_ERROR SC8_EXPECT SC8_HOST_CPUS
}

teardown_file() {
  remove_throwaway "${SC8_QUOTA:-}" "${SC8_CPUSET:-}"
}

teardown() {
  kill_strays
}

# sc8_prepare — sets SC8_EXPECT and SC8_HOST_CPUS, starts both throwaway containers and reads their
# limits back; on any problem sets SC8_ERROR (so only the SC-8 tests fail, with the reason).
sc8_prepare() {
  local ncpu status_out line list="" affinity base limit_arg quota_line cpuset_line first
  SC8_EXPECT=""
  SC8_HOST_CPUS=""
  ncpu="$(timeout "$RUN_TIMEOUT" docker info --format '{{.NCPU}}' </dev/null 2>&1)"
  if ! [[ "$ncpu" =~ ^[0-9]+$ ]]; then
    SC8_ERROR="cannot read the host's CPU count from the daemon (docker info NCPU): ${ncpu}"
    return 1
  fi
  status_out="$(exec_plain cat /proc/self/status 2>&1)" || {
    SC8_ERROR="cannot read /proc/self/status in ${AGENT_CONTAINER}: ${status_out}"
    return 1
  }
  while IFS= read -r line; do
    [[ "$line" == Cpus_allowed_list:* ]] && list="${line#Cpus_allowed_list:}"
  done <<<"$status_out"
  affinity="$(cpu_list_count "$list")" || {
    SC8_ERROR="unparseable Cpus_allowed_list '${list}' in ${AGENT_CONTAINER}"
    return 1
  }
  base=$((ncpu < affinity ? ncpu : affinity))
  SC8_HOST_CPUS="$base"
  if ((base < 2)); then
    SC8_ERROR="this host offers ${base} CPU (daemon NCPU ${ncpu}, affinity ${affinity}): no CPU limit can sit below the host's count, so SC-8 ('rather than the host's CPU count') cannot be shown here. Run the Docker lane on a host with at least 2 CPUs (FAIL, not skip: see this file's header)"
    return 1
  fi
  if ((base >= 3)); then SC8_EXPECT=2; else SC8_EXPECT=1; fi
  limit_arg="$((SC8_EXPECT - 1)).5"

  local err
  err="$(start_throwaway "$SC8_QUOTA" --cpus "$limit_arg" 2>&1)" || {
    SC8_ERROR="cannot start ${SC8_QUOTA} with --cpus ${limit_arg}: ${err}"
    return 1
  }
  quota_line="$(timeout "$RUN_TIMEOUT" docker exec "$SC8_QUOTA" cat /sys/fs/cgroup/cpu.max </dev/null 2>&1)"
  if [[ "$quota_line" != "$((SC8_EXPECT * 100000 - 50000)) 100000" ]]; then
    SC8_ERROR="--cpus ${limit_arg} is not visible as cgroup v2 cpu.max in ${SC8_QUOTA} (read '${quota_line}', want '$((SC8_EXPECT * 100000 - 50000)) 100000'). A cgroup v1 host or a non-default period breaks spec Assumption 8's reading"
    return 1
  fi

  first="${list//[[:space:]]/}"
  first="${first%%[,-]*}"
  err="$(start_throwaway "$SC8_CPUSET" --cpuset-cpus "$first" 2>&1)" || {
    SC8_ERROR="cannot start ${SC8_CPUSET} with --cpuset-cpus ${first}: ${err}"
    return 1
  }
  cpuset_line="$(timeout "$RUN_TIMEOUT" docker exec "$SC8_CPUSET" cat /sys/fs/cgroup/cpu.max </dev/null 2>&1)"
  status_out="$(timeout "$RUN_TIMEOUT" docker exec "$SC8_CPUSET" cat /proc/self/status </dev/null 2>&1)"
  list=""
  while IFS= read -r line; do
    [[ "$line" == Cpus_allowed_list:* ]] && list="${line#Cpus_allowed_list:}"
  done <<<"$status_out"
  if [[ "$cpuset_line" != "max "* || "$(cpu_list_count "$list")" != 1 ]]; then
    SC8_ERROR="${SC8_CPUSET} does not show 'no quota, one CPU' (cpu.max '${cpuset_line}', Cpus_allowed_list '${list}')"
    return 1
  fi
}

sc8_ready() {
  if [[ -n "${SC8_ERROR:-}" ]]; then
    echo "SC-8 precondition: ${SC8_ERROR}" >&2
    return 1
  fi
}

# --- SC-8 ------------------------------------------------------------------------------------------
# os.cpu_count() is the effect a Python build tool sees (Python >= 3.13 honours PYTHON_CPU_COUNT).
# Not `python3 -I`: -I implies -E, which ignores every PYTHON* variable by design.
READ_JOBS='printf "TIMELIKE_CPUS=%s\n" "${TIMELIKE_CPUS-<unset>}"
printf "MAKEFLAGS=%s\n" "${MAKEFLAGS-<unset>}"
printf "CMAKE_BUILD_PARALLEL_LEVEL=%s\n" "${CMAKE_BUILD_PARALLEL_LEVEL-<unset>}"
printf "CARGO_BUILD_JOBS=%s\n" "${CARGO_BUILD_JOBS-<unset>}"
printf "GOMAXPROCS=%s\n" "${GOMAXPROCS-<unset>}"
printf "PYTEST_XDIST_AUTO_NUM_WORKERS=%s\n" "${PYTEST_XDIST_AUTO_NUM_WORKERS-<unset>}"
printf "PYTHON_CPU_COUNT=%s\n" "${PYTHON_CPU_COUNT-<unset>}"
printf "os.cpu_count=%s\n" "$(/opt/timelike/python/bin/python3 -c "import os; print(os.cpu_count())")"
printf "read-jobs=done\n"'

# assert_jobs N [MAKEFLAGS_WANT [GOMAXPROCS_WANT]]
assert_jobs() {
  local n="$1" make_want="${2:--j$1}" go_want="${3:-$1}"
  assert_status 0
  assert_value read-jobs "done"
  assert_value TIMELIKE_CPUS "$n"
  assert_value MAKEFLAGS "$make_want"
  assert_value CMAKE_BUILD_PARALLEL_LEVEL "$n"
  assert_value CARGO_BUILD_JOBS "$n"
  assert_value GOMAXPROCS "$go_want"
  assert_value PYTEST_XDIST_AUTO_NUM_WORKERS "$n"
  assert_value PYTHON_CPU_COUNT "$n"
  assert_value os.cpu_count "$n"
}

check_jobs_from_limit() {
  sc8_ready
  AGENT_CONTAINER="$SC8_QUOTA" run_in "$1" "$2" "$READ_JOBS"
  assert_within 20
  if [[ "$(value_of TIMELIKE_CPUS)" == "$SC8_HOST_CPUS" ]]; then
    echo "TIMELIKE_CPUS is the host's count (${SC8_HOST_CPUS}), not the limit (${SC8_EXPECT})" >&2
    return 1
  fi
  assert_jobs "$SC8_EXPECT"
}

check_jobs_from_affinity() {
  sc8_ready
  AGENT_CONTAINER="$SC8_CPUSET" run_in "$1" "$2" "$READ_JOBS"
  assert_within 20
  assert_jobs 1
}

# An explicit value already in the environment wins (FR-15); the others are still derived.
check_explicit_wins() {
  sc8_ready
  AGENT_CONTAINER="$SC8_QUOTA" run_in -e MAKEFLAGS=-j7 -e GOMAXPROCS=5 "$1" "$2" "$READ_JOBS"
  assert_within 20
  assert_jobs "$SC8_EXPECT" -j7 5
}

@test "SC-8 bash -c: build parallelism defaults derived from the container's CPU limit, not the host's [notty]" { check_jobs_from_limit c notty; }
@test "SC-8 bash -lc: build parallelism defaults derived from the container's CPU limit, not the host's [notty]" { check_jobs_from_limit lc notty; }
@test "SC-8 bash -ic: build parallelism defaults derived from the container's CPU limit, not the host's [notty]" { check_jobs_from_limit ic notty; }
@test "SC-8 bash -ic: build parallelism defaults derived from the container's CPU limit, not the host's [tty]" { check_jobs_from_limit ic tty; }
@test "SC-8 bash -c: build parallelism defaults capped by CPU affinity when no quota is set [notty]" { check_jobs_from_affinity c notty; }
@test "SC-8 bash -c: an explicit MAKEFLAGS and GOMAXPROCS win over the derived default [notty]" { check_explicit_wins c notty; }
@test "SC-8 bash -lc: an explicit MAKEFLAGS and GOMAXPROCS win over the derived default [notty]" { check_explicit_wins lc notty; }
@test "SC-8 bash -ic: an explicit MAKEFLAGS and GOMAXPROCS win over the derived default [notty]" { check_explicit_wins ic notty; }

# --- SC-9 ------------------------------------------------------------------------------------------
# Secret-shaped names (a component that is, or for password/token/secret ends with, a listed word;
# any case), each with a value carrying a marker; the
# full `env` dump is then searched for the marker, so a secret surviving under ANY name is caught.
SC9_SECRETS=(GITHUB_TOKEN MY_API_KEY DB_PASSWORD npm_config__authToken AWS_SECRET_ACCESS_KEY
  deploy_passphrase SMTP_PASS SERVICE_CREDENTIALS PGPASSWORD GHTOKEN)
# Allow-listed (both separators of TIMELIKE_ENV_ALLOW) and look-alikes that must stay (FR-16):
# TOKENIZERS_PARALLELISM and KEYBOARD_LAYOUT (a component only starts with TOKEN / KEY), the image's
# own GIT_ASKPASS and SSH_ASKPASS, and GIT_CONFIG_KEY_0 (git's config-key name; without it every git
# command fails, so git is exercised as well).
SC9_KEPT=(ALLOWED_TOKEN SECOND_ALLOWED_KEY TOKENIZERS_PARALLELISM KEYBOARD_LAYOUT GIT_ASKPASS
  SSH_ASKPASS GIT_CONFIG_KEY_0 TIMELIKE_ENV_ALLOW)

READ_SECRETS='for n in '"${SC9_SECRETS[*]} ${SC9_KEPT[*]}"'; do
  if [ -n "${!n+x}" ]; then printf "%s=present\n" "$n"; else printf "%s=absent\n" "$n"; fi
done
printf "hooksPath=%s\n" "$(cd / && git config --get core.hooksPath)"
printf "git_editor=%s\n" "$(cd / && git var GIT_EDITOR)"
printf "read-secrets=done\n"
env'

check_secrets() {
  local -a envs=(-e "TIMELIKE_ENV_ALLOW=ALLOWED_TOKEN, SECOND_ALLOWED_KEY"
    -e ALLOWED_TOKEN=sc9kept1 -e SECOND_ALLOWED_KEY=sc9kept2
    -e TOKENIZERS_PARALLELISM=false -e KEYBOARD_LAYOUT=us)
  local n
  for n in "${SC9_SECRETS[@]}"; do
    envs+=(-e "${n}=sc9secret-${n}")
  done
  run_in "${envs[@]}" "$1" "$2" "$READ_SECRETS"
  assert_within 20
  assert_status 0
  assert_value read-secrets "done"
  for n in "${SC9_SECRETS[@]}"; do
    assert_value "$n" absent
  done
  for n in "${SC9_KEPT[@]}"; do
    assert_value "$n" present
  done
  assert_value hooksPath /opt/timelike/git-hooks
  assert_value git_editor true
  if [[ "$output" == *sc9secret* ]]; then
    echo "a secret value is still visible in the environment:" >&2
    grep -F sc9secret <<<"$output" >&2
    return 1
  fi
  assert_output_has "ALLOWED_TOKEN=sc9kept1"
  assert_output_has "SECOND_ALLOWED_KEY=sc9kept2"
}

@test "SC-9 bash -c: secret-shaped variables absent unless allow-listed; look-alikes kept [notty]" { check_secrets c notty; }
@test "SC-9 bash -lc: secret-shaped variables absent unless allow-listed; look-alikes kept [notty]" { check_secrets lc notty; }
@test "SC-9 bash -ic: secret-shaped variables absent unless allow-listed; look-alikes kept [notty]" { check_secrets ic notty; }
@test "SC-9 bash -ic: secret-shaped variables absent unless allow-listed; look-alikes kept [tty]" { check_secrets ic tty; }

# --- SC-10: timezone ------------------------------------------------------------------------------
# POSIX sh on purpose, so sh -c runs the same string: TZ and PYTHON_BASIC_REPL are static ENV.
READ_TIME='printf "TZ=%s\n" "${TZ-<unset>}"
printf "zone=%s\n" "$(date +%Z)"
printf "offset=%s\n" "$(date +%z)"
printf "python_zone=%s\n" "$(/opt/timelike/python/bin/python3 -c "import time; print(time.tzname[0], time.timezone)")"
printf "PYTHON_BASIC_REPL=%s\n" "${PYTHON_BASIC_REPL-<unset>}"
printf "read-time=done\n"'

check_utc() {
  run_in "$1" "$2" "$READ_TIME"
  assert_within 20
  assert_status 0
  assert_value read-time "done"
  assert_value TZ UTC
  assert_value zone UTC
  assert_value offset +0000
  assert_value python_zone "UTC 0"
  assert_value PYTHON_BASIC_REPL 1
}

@test "SC-10 bash -c: the timezone defaults to UTC [notty]" { check_utc c notty; }
@test "SC-10 bash -lc: the timezone defaults to UTC [notty]" { check_utc lc notty; }
@test "SC-10 bash -ic: the timezone defaults to UTC [notty]" { check_utc ic notty; }
@test "SC-10 sh -c: the timezone defaults to UTC [notty]" { check_utc sh notty; }

# --- SC-10: REPL ----------------------------------------------------------------------------------
# A REPL only shows its prompt mode on a terminal, so it runs under util-linux `script` (a fresh pty,
# as helpers.bash's pty mode) inside the container, started by the style under test. TERM=xterm is
# what `docker exec -t` announces for a harness terminal; without a TERM, Python's PyREPL may fall
# back to the basic REPL by itself, and the test could not fail. Input is typed after a pause (so it
# reaches the running REPL), and the session ends itself with SystemExit.
#
# Basic mode is: the plain ">>> " prompt, the answer, and no escape sequence at all (PyREPL writes
# cursor, keypad and bracketed-paste sequences, and colour). The control test runs the same session
# with PYTHON_BASIC_REPL set empty (CPython treats empty as unset) and must SEE escape sequences — the
# evidence that this check can fail (lore cross-stack P004).
repl_session() { # repl_session STYLE [-e K=V]...
  local style="$1"
  shift
  local -a shell
  mapfile -t shell < <(_shell_argv "$style") || return 2
  {
    sleep 2
    printf 'print(6*7)\n'
    sleep 1
    printf 'raise SystemExit(0)\n'
    sleep 1
  } | timeout "$RUN_TIMEOUT" docker exec -i -e TERM=xterm "$@" "$AGENT_CONTAINER" \
    "${shell[@]}" "script -qec '${AGENT_PY} -q' /dev/null"
}

run_repl() {
  run repl_session "$@"
  output="${output//$'\r'/}"
  if [[ -n "$output" ]]; then mapfile -t lines <<<"$output"; else lines=(); fi
}

check_basic_repl() {
  run_repl "$1"
  if [[ "$status" == 124 ]]; then
    printf 'the REPL session timed out after %ss; output:\n%q\n' "$RUN_TIMEOUT" "$output" >&2
    return 1
  fi
  assert_status 0
  if [[ "$output" == *$'\e'* ]]; then
    printf 'escape sequences in the REPL output (PyREPL, or readline enabling meta/bracketed-paste for TERM=xterm):\n%q\n' "$output" >&2
    return 1
  fi
  assert_output_has ">>> "
  local line found=0
  for line in "${lines[@]}"; do
    [[ "$line" == "42" ]] && found=1
  done
  if [[ "$found" != 1 ]]; then
    printf 'no line "42" in the REPL output:\n%q\n' "$output" >&2
    return 1
  fi
}

@test "SC-10 bash -c: Python's REPL starts in its basic, scriptable prompt mode [pty]" { check_basic_repl c; }
@test "SC-10 bash -lc: Python's REPL starts in its basic, scriptable prompt mode [pty]" { check_basic_repl lc; }

@test "SC-10 control: with PYTHON_BASIC_REPL unset the same session shows escape sequences [bash -c, pty]" {
  run_repl c -e PYTHON_BASIC_REPL=
  if [[ "$output" != *$'\e'* ]]; then
    printf 'no escape sequence without PYTHON_BASIC_REPL: the basic-mode check above could not fail (status %s):\n%q\n' "$status" "$output" >&2
    return 1
  fi
}
