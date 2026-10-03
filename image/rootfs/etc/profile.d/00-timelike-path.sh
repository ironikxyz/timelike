# shellcheck shell=sh
# /etc/profile.d/00-timelike-path.sh — sourced by /etc/profile in every login shell (research R1).
# Debian's /etc/profile resets PATH unconditionally, dropping the image ENV's /opt/timelike/bin, so
# login shells (bash -lc) get it back here. Idempotent: prepends only when absent. POSIX sh, because
# /etc/profile may be read by sh as well as bash.
case ":${PATH:-}:" in
  *:/opt/timelike/bin:*) ;;
  *) PATH="/opt/timelike/bin${PATH:+:${PATH}}" ;;
esac
export PATH
