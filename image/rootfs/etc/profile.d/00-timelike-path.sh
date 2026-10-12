# shellcheck shell=sh
# /etc/profile.d/00-timelike-path.sh — sourced by /etc/profile in every login shell (research R1).
# Debian's /etc/profile resets PATH unconditionally, dropping the image ENV's /opt/timelike/bin, so
# login shells (bash -lc) get it back here. Idempotent: prepends only when absent. POSIX sh, because
# /etc/profile may be read by sh as well as bash.
# Feature 007 slice 1 (discovery revision 14; 007 spec FR-28): /home/agent/.local/bin, where bare pip and
# npm -g installs put commands, comes back too, after /opt/timelike/bin (an install never shadows a
# timelike tool) and before the rest, as in the image ENV.
# Feature 013 slice 1 (FOR-MENTOR Item 24, Q1 (b')): /opt/timelike/shims, the install shims in front of pip,
# pip3, uv, npm, npx and pnpm, comes back first of all, so a pip or pnpm installed into ~/.local/bin is
# still behind the package guard. Each entry is added only when absent, so sourcing this twice changes
# nothing.
case ":${PATH:-}:" in
  *:/home/agent/.local/bin:*) ;;
  *) PATH="/home/agent/.local/bin${PATH:+:${PATH}}" ;;
esac
case ":${PATH:-}:" in
  *:/opt/timelike/bin:*) ;;
  *) PATH="/opt/timelike/bin:${PATH}" ;;
esac
case ":${PATH:-}:" in
  *:/opt/timelike/shims:*) ;;
  *) PATH="/opt/timelike/shims:${PATH}" ;;
esac
export PATH
