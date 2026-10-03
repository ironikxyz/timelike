#!/usr/bin/env bash
# Host lane, ADVISORY (research R10, tasks T020, T052). Proves the environment-layer FILES — the single
# ENV instruction in image/Dockerfile, image/rootfs/etc/gitconfig,
# image/rootfs/etc/profile.d/00-timelike-path.sh and, from slice 1, the container-derived hook
# image/rootfs/etc/timelike/shell-env.bash with its three wirings (BASH_ENV in ENV,
# profile.d/10-timelike-shell-env.sh, the line the Dockerfile appends to /etc/bash.bashrc) — give
# T018's defaults and SC-8/SC-9/SC-10's in each invocation style. It does NOT prove the image: the
# host's bash, git and /etc/bash.bashrc stand in for the image's. The hook's own logic is tested in
# tests/host/test_shell_env_hook.sh; here only that each style reaches it.
#
# Image paths are rewritten to the repository's copies: BASH_ENV and the profile.d file name
# /etc/timelike/shell-env.bash, which the host does not have. The interactive style cannot edit the
# host's /etc/bash.bashrc, so `bash -ic` runs with --rcfile holding the Dockerfile's appended line
# (read from the Dockerfile, path rewritten); Debian/Ubuntu bash still reads /etc/bash.bashrc first,
# so the line runs after it, as it does appended at the end. The CPU figure comes from fake cgroup
# and status files through the hook's test-only overrides.
#
# Login-shell simulation: this script cannot edit the host's /etc/profile, and the host's (Ubuntu) one
# does not reset PATH as Debian trixie's does. So the "bash -lc" case runs `bash -c` that first sources
# a temporary stand-in profile which (a) resets PATH exactly as trixie's /etc/profile does for a
# non-root uid and (b) sources a temporary profile.d holding a copy of 00-timelike-path.sh — the two
# parts of /etc/profile that decide PATH (R1).
#
# Self-checks (lore cross-stack P004/P005: a test that cannot fail proves nothing):
#   N1  the same assertions with neither ENV nor gitconfig must ALL fail
#   N2  the stand-in profile without profile.d must drop /opt/timelike/bin (the reset is real)
#   N3  ENV without gitconfig must fail color.ui (NO_COLOR does not reach git 2.43, R4)
#   N4  ENV without BASH_ENV, profile.d without 10-timelike-shell-env.sh and no bashrc line must fail
#       every hook-derived value in every style, while TZ still holds (static, F003)
set -euo pipefail

echo "# ADVISORY host lane: proves the env-layer files (Dockerfile ENV, gitconfig, profile.d, shell-env hook wiring), NOT the image; login and interactive shells are simulated (see header)"

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
dockerfile="${repo}/image/Dockerfile"
gitconfig="${repo}/image/rootfs/etc/gitconfig"
profile_d_src="${repo}/image/rootfs/etc/profile.d/00-timelike-path.sh"
hook_src="${repo}/image/rootfs/etc/timelike/shell-env.bash"
profile_d_hook_src="${repo}/image/rootfs/etc/profile.d/10-timelike-shell-env.sh"
HOOK_IMAGE_PATH=/etc/timelike/shell-env.bash
# The line image/Dockerfile appends to /etc/bash.bashrc, verbatim (checked below).
BASHRC_LINE="if [ -r ${HOOK_IMAGE_PATH} ]; then . ${HOOK_IMAGE_PATH}; fi"

tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT
mkdir -p "${tmp}/home" "${tmp}/work" "${tmp}/profile.d" "${tmp}/profile-no-hook.d"
cp "${profile_d_src}" "${tmp}/profile.d/00-timelike-path.sh"
cp "${profile_d_src}" "${tmp}/profile-no-hook.d/00-timelike-path.sh"
hook_d_text="$(<"${profile_d_hook_src}")"
printf '%s\n' "${hook_d_text//"${HOOK_IMAGE_PATH}"/"${hook_src}"}" >"${tmp}/profile.d/10-timelike-shell-env.sh"
printf '%s\n' "${BASHRC_LINE//"${HOOK_IMAGE_PATH}"/"${hook_src}"}" >"${tmp}/bashrc-line"
: >"${tmp}/bashrc-empty"
# Fake container: a 2.5-CPU quota on 8 CPUs, so the hook's figure is 3 (never the host's).
printf '250000 100000\n' >"${tmp}/cpu.max"
printf 'Name:\tbash\nCpus_allowed_list:\t0-7\n' >"${tmp}/status"

# Stand-in for Debian trixie /etc/profile (base-files 13.8): the PATH reset, then profile.d.
write_profile() { # $1 = output file, $2 = profile.d dir
  cat >"$1" <<EOF
if [ "\$(id -u)" -eq 0 ]; then
  PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
else
  PATH="/usr/local/bin:/usr/bin:/bin:/usr/local/games:/usr/games"
fi
export PATH
if [ -d "$2" ]; then
  for i in "$2"/*.sh; do
    if [ -r "\$i" ]; then . "\$i"; fi
  done
  unset i
fi
EOF
}
write_profile "${tmp}/profile" "${tmp}/profile.d"
mkdir -p "${tmp}/empty.d"
write_profile "${tmp}/profile-no-d" "${tmp}/empty.d"
write_profile "${tmp}/profile-no-hook" "${tmp}/profile-no-hook.d"

# --- Parse the single ENV instruction --------------------------------------------------------------
fail_parse() { echo "Bail out! $*"; exit 1; }
env_count="$(grep -c '^ENV[[:space:]]' "${dockerfile}" || true)"
[[ "${env_count}" == "1" ]] || fail_parse "expected exactly one ENV instruction in image/Dockerfile, found ${env_count}"

env_vars=()
in_env=0
while IFS= read -r line || [[ -n "${line}" ]]; do
  if [[ ${in_env} -eq 0 ]]; then
    [[ "${line}" =~ ^ENV[[:space:]] ]] || continue
    in_env=1
    line="${line#ENV}"
  fi
  cont=0
  if [[ "${line}" =~ \\[[:space:]]*$ ]]; then
    cont=1
    line="${line%\\*}"
  fi
  # trim
  line="${line#"${line%%[![:space:]]*}"}"
  line="${line%"${line##*[![:space:]]}"}"
  if [[ -n "${line}" ]]; then
    [[ "${line}" =~ ^([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]] || fail_parse "ENV line not KEY=VALUE: ${line}"
    key="${BASH_REMATCH[1]}"
    val="${BASH_REMATCH[2]}"
    if [[ "${val}" =~ ^\"(.*)\"$ ]]; then val="${BASH_REMATCH[1]}"; fi
    case "${val}" in
      *'$'* | *\\* | *"'"* | *'"'*) fail_parse "ENV value for ${key} uses \$, backslash or a quote; this parser does not model Dockerfile escaping" ;;
    esac
    env_vars+=("${key}=${val}")
  fi
  [[ ${cont} -eq 1 ]] || break
done <"${dockerfile}"
[[ ${#env_vars[@]} -gt 0 ]] || fail_parse "ENV instruction parsed to zero variables"
echo "# parsed ${#env_vars[@]} variables from the ENV instruction"

# --- The probe: prints one key=value per asserted fact --------------------------------------------
# shellcheck disable=SC2016  # expanded by the shell under test, not here
probe='
printf "path_first=%s\n" "${PATH%%:*}"
printf "git_var_editor=%s\n" "$(git var GIT_EDITOR 2>/dev/null)"
printf "git_var_pager=%s\n" "$(git var GIT_PAGER 2>/dev/null)"
printf "pager=%s\n" "${PAGER-<unset>}"
printf "color_ui=%s\n" "$(git config --get color.ui 2>/dev/null)"
printf "no_color=%s\n" "${NO_COLOR-<unset>}"
printf "git_terminal_prompt=%s\n" "${GIT_TERMINAL_PROMPT-<unset>}"
printf "debian_frontend=%s\n" "${DEBIAN_FRONTEND-<unset>}"
printf "hooks_path=%s\n" "$(git config --get core.hooksPath 2>/dev/null)"
printf "tz=%s\n" "${TZ-<unset>}"
printf "python_basic_repl=%s\n" "${PYTHON_BASIC_REPL-<unset>}"
printf "timelike_cpus=%s\n" "${TIMELIKE_CPUS-<unset>}"
printf "makeflags=%s\n" "${MAKEFLAGS-<unset>}"
if [ -n "${GITHUB_TOKEN+x}" ]; then echo secret=present; else echo secret=absent; fi
if [ -n "${ALLOWED_TOKEN+x}" ]; then echo allowed=present; else echo allowed=absent; fi
'

expected=(
  "path_first=/opt/timelike/bin"
  "git_var_editor=true"
  "git_var_pager=cat"
  "pager=cat"
  "color_ui=never"
  "no_color=1"
  "git_terminal_prompt=0"
  "debian_frontend=noninteractive"
  "hooks_path=/opt/timelike/git-hooks"
  "tz=UTC"
  "python_basic_repl=1"
  "timelike_cpus=3"
  "makeflags=-j3"
  "secret=absent"
)
# Hold without any env layer too (nothing strips them), so they are asserted positively only.
expected_kept=("allowed=present")
# The values only the hook provides (N4).
hook_keys=(timelike_cpus makeflags secret)

# run_style STYLE WITH_ENV(1|0|nobashenv) SYSCONFIG PROFILE [RCFILE] → probe output on stdout
# Every run also carries the fake container files and SC-9's inputs: a secret-shaped GITHUB_TOKEN and
# an allow-listed ALLOWED_TOKEN (what docker exec -e would pass).
run_style() {
  local style="$1" with_env="$2" sysconfig="$3" profile="$4" rcfile="${5:-${tmp}/bashrc-line}"
  local -a vars=("HOME=${tmp}/home") e
  if [[ "${with_env}" == "0" ]]; then
    vars+=("PATH=/usr/local/bin:/usr/bin:/bin")
  else
    for e in "${env_vars[@]}"; do
      case "${e}" in
        BASH_ENV=*) [[ "${with_env}" == "nobashenv" ]] || vars+=("BASH_ENV=${hook_src}") ;;
        *) vars+=("${e}") ;;
      esac
    done
  fi
  vars+=("GIT_CONFIG_SYSTEM=${sysconfig}" "GIT_CONFIG_GLOBAL=/dev/null"
    "TIMELIKE_CGROUP_CPU_MAX=${tmp}/cpu.max" "TIMELIKE_PROC_STATUS=${tmp}/status"
    "GITHUB_TOKEN=sc9-secret" "TIMELIKE_ENV_ALLOW=ALLOWED_TOKEN" "ALLOWED_TOKEN=sc9-kept")
  local -a cmd
  case "${style}" in
    "bash -c") cmd=(/bin/bash -c "${probe}") ;;
    "bash -lc") cmd=(/bin/bash -c ". '${profile}'; ${probe}") ;;
    "bash -ic") cmd=(/bin/bash --rcfile "${rcfile}" -ic "${probe}") ;;
    *) echo "unknown style ${style}" >&2; return 1 ;;
  esac
  (cd "${tmp}/work" && env -i "${vars[@]}" "${cmd[@]}" </dev/null 2>/dev/null) || true
}

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

value_of() { # value_of KEY OUTPUT
  local key="$1" out="$2" l
  while IFS= read -r l; do
    if [[ "${l}" == "${key}="* ]]; then printf '%s' "${l#"${key}="}"; return 0; fi
  done <<<"${out}"
  printf '<missing>'
}

# --- Wiring: the ENV keys and the Dockerfile lines that install the hook (slice 1, F003/F004) -----
env_has() { # env_has KEY=VALUE — exactly this entry in the parsed ENV instruction
  local e
  for e in "${env_vars[@]}"; do [[ "${e}" == "$1" ]] && return 0; done
  return 1
}
for kv in "BASH_ENV=${HOOK_IMAGE_PATH}" "TZ=UTC" "PYTHON_BASIC_REPL=1"; do
  if env_has "${kv}"; then tap 0 "ENV sets ${kv}"; else tap 1 "ENV sets ${kv} (absent or different)"; fi
done
dockerfile_text="$(<"${dockerfile}")"
for line in \
  "COPY --chmod=0644 image/rootfs/etc/timelike/shell-env.bash ${HOOK_IMAGE_PATH}" \
  "COPY --chmod=0644 image/rootfs/etc/profile.d/10-timelike-shell-env.sh /etc/profile.d/10-timelike-shell-env.sh" \
  "'${BASHRC_LINE}' >> /etc/bash.bashrc"; do
  if [[ "${dockerfile_text}" == *"${line}"* ]]; then
    tap 0 "Dockerfile has: ${line}"
  else
    tap 1 "Dockerfile has: ${line} (not found)"
  fi
done

# --- Positive: the files give every default in every style ----------------------------------------
for style in "bash -c" "bash -lc" "bash -ic"; do
  out="$(run_style "${style}" 1 "${gitconfig}" "${tmp}/profile")"
  for e in "${expected[@]}" "${expected_kept[@]}"; do
    key="${e%%=*}"
    want="${e#*=}"
    got="$(value_of "${key}" "${out}")"
    if [[ "${got}" == "${want}" ]]; then
      tap 0 "${style}: ${key} = ${want}"
    else
      tap 1 "${style}: ${key} = ${want} (got '${got}')"
    fi
  done
done

# --- W1: under bash -lc, profile.d alone brings the hook (no BASH_ENV) ---------------------------
out="$(run_style "bash -lc" nobashenv "${gitconfig}" "${tmp}/profile")"
got="$(value_of timelike_cpus "${out}")/$(value_of secret "${out}")"
if [[ "${got}" == "3/absent" ]]; then
  tap 0 "W1 bash -lc: profile.d/10-timelike-shell-env.sh alone reaches the hook (no BASH_ENV)"
else
  tap 1 "W1 bash -lc: profile.d/10-timelike-shell-env.sh alone does not reach the hook (timelike_cpus/secret '${got}')"
fi

# --- N1: without ENV and gitconfig, every assertion must fail -------------------------------------
for style in "bash -c" "bash -lc" "bash -ic"; do
  out="$(run_style "${style}" 0 /dev/null "${tmp}/profile-no-d" "${tmp}/bashrc-empty")"
  passed_anyway=()
  missing=()
  for e in "${expected[@]}"; do
    key="${e%%=*}"
    want="${e#*=}"
    got="$(value_of "${key}" "${out}")"
    [[ "${got}" != "<missing>" ]] || missing+=("${key}")
    [[ "${got}" != "${want}" ]] || passed_anyway+=("${key}")
  done
  if [[ ${#missing[@]} -ne 0 ]]; then
    tap 1 "self-check N1 ${style}: probe did not report ${missing[*]} — a silent probe cannot show failure"
  elif [[ ${#passed_anyway[@]} -eq 0 ]]; then
    tap 0 "self-check N1 ${style}: all ${#expected[@]} assertions fail without the ENV block and gitconfig"
  else
    tap 1 "self-check N1 ${style}: assertions passed with no env layer: ${passed_anyway[*]}"
  fi
done

# --- N2: the stand-in profile really resets PATH, so profile.d is what restores it ----------------
out="$(run_style "bash -lc" 1 "${gitconfig}" "${tmp}/profile-no-d")"
got="$(value_of path_first "${out}")"
if [[ "${got}" != "/opt/timelike/bin" && "${got}" != "<missing>" ]]; then
  tap 0 "self-check N2 bash -lc: without profile.d the PATH reset drops /opt/timelike/bin (first entry '${got}')"
else
  tap 1 "self-check N2 bash -lc: PATH kept /opt/timelike/bin without profile.d — the stand-in reset is not real"
fi

# --- N3: NO_COLOR alone does not turn git colour off; gitconfig is load-bearing (R4) --------------
out="$(run_style "bash -c" 1 /dev/null "${tmp}/profile")"
got="$(value_of color_ui "${out}")"
if [[ "${got}" != "never" && "${got}" != "<missing>" ]]; then
  tap 0 "self-check N3 bash -c: without gitconfig, color.ui is not never (got '${got}')"
else
  tap 1 "self-check N3 bash -c: color.ui = never without gitconfig — the assertion cannot fail"
fi

# --- N4: without the hook's three wirings, every hook-derived value fails; TZ (static) still holds -
for style in "bash -c" "bash -lc" "bash -ic"; do
  out="$(run_style "${style}" nobashenv "${gitconfig}" "${tmp}/profile-no-hook" "${tmp}/bashrc-empty")"
  held=()
  for key in "${hook_keys[@]}"; do
    for e in "${expected[@]}"; do
      [[ "${e%%=*}" == "${key}" ]] || continue
      [[ "$(value_of "${key}" "${out}")" != "${e#*=}" ]] || held+=("${key}")
    done
  done
  tz="$(value_of tz "${out}")"
  if [[ ${#held[@]} -eq 0 && "${tz}" == "UTC" ]]; then
    tap 0 "self-check N4 ${style}: without the hook's wiring ${hook_keys[*]} all fail; tz still UTC"
  else
    tap 1 "self-check N4 ${style}: without the hook's wiring these held: ${held[*]:-none}; tz '${tz}'"
  fi
done

echo "1..${n}"
if [[ ${failures} -ne 0 ]]; then
  echo "# FAILED ${failures} of ${n} (advisory host lane)"
  exit 1
fi
echo "# passed ${n} of ${n} (advisory host lane: files, not the image)"
