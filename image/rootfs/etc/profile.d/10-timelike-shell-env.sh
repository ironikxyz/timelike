# shellcheck shell=sh
# /etc/profile.d/10-timelike-shell-env.sh — sourced by /etc/profile in every login shell (research R1;
# modify.md F004). Brings the container-derived defaults of /etc/timelike/shell-env.bash (job counts
# from the CPU limit, the secret strip: SC-8, SC-9) to `bash -lc` and interactive login shells.
# `bash -lc` also reads BASH_ENV after the profile files, so the hook runs twice there; it is
# idempotent. POSIX sh, because /etc/profile may be read by sh too: the hook is bash-only, so it is
# sourced only under bash. Numbered after 00-timelike-path.sh, though it does not depend on PATH.
if [ -n "${BASH_VERSION-}" ] && [ -r /etc/timelike/shell-env.bash ]; then
  # shellcheck disable=SC1091 # an image path; checked on its own as image/rootfs/etc/timelike/shell-env.bash
  . /etc/timelike/shell-env.bash
fi
