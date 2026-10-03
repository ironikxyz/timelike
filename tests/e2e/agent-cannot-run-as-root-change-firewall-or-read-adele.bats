#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# SC-4 — "The agent's user cannot run any command as root, cannot change firewall rules, and cannot
# read files owned by Adele." (tasks.md T023; spec FR-5, FR-6, FR-7; research R7.)
#
# Vantage point (lore cross-stack P001): every read below is made by a process the harness would
# start — `docker exec timelike-agent bash -c|-lc ...` as the image's default user — reading the
# kernel's own record of that process (/proc/self/status), the filesystem's modes, and the kernel's
# answer to a netfilter request. None of it is inferred from a connection attempt or a message.
# Every assertion runs under bash -c and bash -lc.
#
# Firewall: the image has no nft or iptables (R7), so tests/fixtures/nfprobe.py talks to the kernel
# directly: one nfnetlink request on AF_NETLINK/NETLINK_NETFILTER. The kernel checks CAP_NET_ADMIN
# before handling any nfnetlink message, reads included; EPERM is the expected answer.
#
# Common failures (slice 1, natural intensity; modify.md F005; tasks.md T053) — the two routes a real
# agent reaches for first when sudo and su are gone, neither covered above:
#   - a container-runtime socket. A reachable Docker (or containerd, podman, buildkit) socket is root
#     on the host in one command, and mounting one "for convenience" is the commonest container
#     escalation there is. compose.yaml mounts none (H1: only Adele holds it). Read directly: every
#     unix socket on the filesystem is listed (outside /proc and /sys) and none may be a runtime's;
#     DOCKER_HOST must be unset, so no TCP daemon is named either.
#   - rewriting its own guards instead of escalating: `git config --system` to re-enable hooks, a
#     line appended to a startup file or to the slice-1 hook, a tool on /opt/timelike/bin replaced, a
#     file planted in /etc/profile.d. Each write is attempted; each must be refused, and the files' checksums, read
#     before and after through a separate exec, must be unchanged (lore cross-stack P004).
# Cells: bash -c and bash -lc, as everywhere in this file.

load helpers

setup_file() {
  stamp_check
  copy_into_container "${BATS_TEST_DIRNAME}/../fixtures/nfprobe.py" /tmp/nfprobe.py
}

# Read /proc/self/status of the process the style starts (cat's own status: same credentials, same
# bounding set and no_new_privs as the shell that started it).
check_capabilities_and_no_new_privs() {
  run_in "$1" notty 'cat /proc/self/status'
  assert_status 0
  local line field value
  declare -A seen=()
  for line in "${lines[@]}"; do
    field="${line%%:*}"
    value="${line#*:}"
    value="${value//[[:space:]]/}"
    case "$field" in
      CapInh | CapPrm | CapEff | CapBnd | CapAmb | NoNewPrivs | Seccomp) seen[$field]="$value" ;;
    esac
  done
  for field in CapEff CapPrm CapBnd CapAmb; do
    [[ "${seen[$field]:-<absent>}" == 0000000000000000 ]] ||
      { echo "$field is '${seen[$field]:-<absent>}', want 0000000000000000" >&2; return 1; }
  done
  [[ "${seen[NoNewPrivs]:-}" == 1 ]] || { echo "NoNewPrivs is '${seen[NoNewPrivs]:-<absent>}', want 1" >&2; return 1; }
  [[ "${seen[Seccomp]:-}" == 2 ]] || { echo "Seccomp is '${seen[Seccomp]:-<absent>}', want 2 (filter)" >&2; return 1; }
}

check_identity() {
  run_in "$1" notty 'printf "uid=%s\n" "$(id -u)"; printf "groups=%s\n" "$(id -G)"'
  assert_status 0
  assert_value uid 1000
  local g
  for g in $(value_of groups); do
    case "$g" in
      0 | 27 | 10001) echo "agent user is in privileged group $g (id -G: $(value_of groups))" >&2; return 1 ;;
    esac
  done
}

check_no_setuid_or_setgid_files() {
  run_in "$1" notty 'find / -xdev -perm /6000 -type f 2>/dev/null; echo "find-done=1"'
  [[ "$status" != 124 ]] || { echo "find timed out" >&2; return 1; }
  assert_value find-done 1
  local line found=()
  for line in "${lines[@]}"; do
    [[ "$line" == find-done=1 ]] || found+=("$line")
  done
  if ((${#found[@]} > 0)); then
    { echo 'setuid/setgid files present:'; printf '  %s\n' "${found[@]}"; } >&2
    return 1
  fi
}

check_no_sudo() {
  run_in "$1" notty 'command -v sudo; echo "rc=$?"; test -e /usr/bin/sudo && echo present=yes || echo present=no'
  assert_status 0
  assert_value rc 1
  assert_value present no
}

check_su_fails() {
  run_in "$1" notty 'su -c true root'
  assert_within 20
  if [[ "$status" == 0 ]]; then
    echo "su -c true root succeeded" >&2
    return 1
  fi
}

check_unshare_fails() {
  run_in "$1" notty 'unshare -r true'
  assert_within 20
  if [[ "$status" == 0 ]]; then
    echo "unshare -r true succeeded: the agent can map itself to root in a user namespace" >&2
    return 1
  fi
}

check_firewall_netlink_eperm() {
  run_in "$1" notty "${AGENT_PY} -I /tmp/nfprobe.py"
  assert_within 20
  assert_status 0
  [[ "${lines[-1]:-}" == EPERM ]] || { echo "nfprobe said '${lines[-1]:-}', want EPERM" >&2; return 1; }
}

check_adele_file_unreadable() {
  # Control first: the directory exists and belongs to adele with 0700, so a failed read below is a
  # permission refusal and not a missing file.
  run_in "$1" notty 'stat -c "owner=%u mode=%a" /var/lib/adele | tr " " "\n"'
  assert_status 0
  assert_value owner 10001
  assert_value mode 700
  run_in "$1" notty 'cat /var/lib/adele/fixture.secret'
  if [[ "$status" == 0 ]]; then
    echo "the agent read Adele's fixture.secret" >&2
    return 1
  fi
  assert_output_has "Permission denied"
}

check_adele_dir_unlistable() {
  run_in "$1" notty 'ls /var/lib/adele'
  if [[ "$status" == 0 ]]; then
    printf 'the agent listed /var/lib/adele:\n%s\n' "$output" >&2
    return 1
  fi
  assert_output_has "Permission denied"
}

check_no_runtime_socket() {
  run_in "$1" notty 'find / \( -path /proc -o -path /sys \) -prune -o -type s -print 2>/dev/null
printf "DOCKER_HOST=%s\n" "${DOCKER_HOST-<unset>}"
echo "find-done=1"'
  [[ "$status" != 124 ]] || { echo "find timed out" >&2; return 1; }
  assert_value find-done 1
  assert_value DOCKER_HOST "<unset>"
  local line
  for line in "${lines[@]}"; do
    if [[ "$line" == /* && "${line,,}" =~ (docker|containerd|podman|buildkit|crio) ]]; then
      echo "a container-runtime socket is reachable from the agent: $line" >&2
      return 1
    fi
  done
}

# GUARDS — files the agent's defaults and tools come from, including slice 1's hook that strips
# secret-shaped variables (modify.md F002, F004), and since cycle 5 the git-hook dispatcher that
# enforces the hook limit (research R11), and since feature 003 run (the concluding run). Checksummed
# before and after.
GUARDS=(/etc/gitconfig /etc/bash.bashrc /etc/profile /etc/profile.d/00-timelike-path.sh
  /etc/profile.d/10-timelike-shell-env.sh /etc/timelike/shell-env.bash
  /opt/timelike/bin/timelike /opt/timelike/bin/timelike-conform /opt/timelike/bin/run /opt/timelike/REVISION
  /opt/timelike/git-hooks/dispatch)

check_cannot_alter_guards() {
  local before after
  before="$(exec_plain sha256sum "${GUARDS[@]}")" || { echo "cannot checksum the guard files" >&2; return 1; }
  # run_in takes one command string; the paths hold no spaces, so they are spliced in as words.
  run_in "$1" notty "for f in ${GUARDS[*]}; do"'
  if (printf "# agent was here\n" >>"$f") 2>/dev/null; then echo "appended=$f"; fi
done
for d in /etc /etc/profile.d /etc/timelike /opt/timelike /opt/timelike/bin /opt/timelike/git-hooks; do
  if (: >"$d/agent-planted") 2>/dev/null; then echo "created=$d/agent-planted"; fi
done
git config --system core.hooksPath .git/hooks
echo "git-system-rc=$?"
echo "writes-done=1"'
  assert_within 20
  assert_value writes-done 1
  assert_no_line_matching '^(appended|created)='
  # git's own refusal: it cannot take the lock on /etc/gitconfig.
  [[ "$(value_of git-system-rc)" != 0 ]] || { echo "git config --system succeeded" >&2; return 1; }
  assert_output_has "could not lock config file /etc/gitconfig"
  after="$(exec_plain sha256sum "${GUARDS[@]}")"
  [[ "$after" == "$before" ]] || { printf 'a guard file changed:\nbefore:\n%s\nafter:\n%s\n' "$before" "$after" >&2; return 1; }
  # The agent's write was refused, so the image's own value is unchanged: since 001 cycle 5 that is the
  # hook dispatchers (research R11), no longer /dev/null.
  run exec_plain git config --system --get core.hooksPath
  [[ "$output" == /opt/timelike/git-hooks ]] || { echo "system core.hooksPath is now '$output'" >&2; return 1; }
}

@test "SC-4 agent holds no capabilities, NoNewPrivs 1, seccomp filter on [bash -c]" { check_capabilities_and_no_new_privs c; }
@test "SC-4 agent holds no capabilities, NoNewPrivs 1, seccomp filter on [bash -lc]" { check_capabilities_and_no_new_privs lc; }

@test "SC-4 agent is uid 1000 in none of groups root, sudo or adele [bash -c]" { check_identity c; }
@test "SC-4 agent is uid 1000 in none of groups root, sudo or adele [bash -lc]" { check_identity lc; }

@test "SC-4 cannot run as root: no setuid or setgid file in the image [bash -c]" { check_no_setuid_or_setgid_files c; }
@test "SC-4 cannot run as root: no setuid or setgid file in the image [bash -lc]" { check_no_setuid_or_setgid_files lc; }

@test "SC-4 cannot run as root: no sudo [bash -c]" { check_no_sudo c; }
@test "SC-4 cannot run as root: no sudo [bash -lc]" { check_no_sudo lc; }

@test "SC-4 cannot run as root: su -c true root fails [bash -c]" { check_su_fails c; }
@test "SC-4 cannot run as root: su -c true root fails [bash -lc]" { check_su_fails lc; }

@test "SC-4 cannot run as root: unshare -r true fails [bash -c]" { check_unshare_fails c; }
@test "SC-4 cannot run as root: unshare -r true fails [bash -lc]" { check_unshare_fails lc; }

@test "SC-4 cannot change firewall rules: netfilter netlink answers EPERM [bash -c]" { check_firewall_netlink_eperm c; }
@test "SC-4 cannot change firewall rules: netfilter netlink answers EPERM [bash -lc]" { check_firewall_netlink_eperm lc; }

@test "SC-4 cannot read files owned by Adele: fixture.secret Permission denied [bash -c]" { check_adele_file_unreadable c; }
@test "SC-4 cannot read files owned by Adele: fixture.secret Permission denied [bash -lc]" { check_adele_file_unreadable lc; }

@test "SC-4 cannot read files owned by Adele: /var/lib/adele not listable [bash -c]" { check_adele_dir_unlistable c; }
@test "SC-4 cannot read files owned by Adele: /var/lib/adele not listable [bash -lc]" { check_adele_dir_unlistable lc; }

# --- common failures (slice 1) ---
@test "SC-4 cannot run as root: no Docker or other container-runtime socket reachable, DOCKER_HOST unset [bash -c]" { check_no_runtime_socket c; }
@test "SC-4 cannot run as root: no Docker or other container-runtime socket reachable, DOCKER_HOST unset [bash -lc]" { check_no_runtime_socket lc; }

@test "SC-4 cannot alter its own guards: /etc, /etc/profile.d, /opt/timelike and git config --system refuse writes [bash -c]" { check_cannot_alter_guards c; }
@test "SC-4 cannot alter its own guards: /etc, /etc/profile.d, /opt/timelike and git config --system refuse writes [bash -lc]" { check_cannot_alter_guards lc; }
