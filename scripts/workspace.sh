#!/usr/bin/env bash
# The agent's workspace and the host-git boundary (feature 13 slice 0; 014 research R9; FOR-MENTOR Item 27 Q2, Q6).
#
#   scripts/workspace.sh env     print the launch's variables as KEY=VALUE lines, for `eval` before compose up
#   scripts/workspace.sh check   the same checks and the same output, but nothing is created (a dry run)
#
# The workspace is a directory on the host, one per launch, mounted into the agent at the SAME absolute path, so
# a bind mount a nested project asks for resolves on the host to what the agent sees (lore docker-compose P001,
# item 1). Inputs, from the environment or the git-ignored local.env (the environment wins):
#   TIMELIKE_WORKSPACES  the parent, set by the operator. It is never written into this repository.
#   TIMELIKE_WORKSPACE   optional: an existing directory to use instead of a new one under the parent.
#   TIMELIKE_HOST_GIT    enforced (the default) or lifted.
#
# The boundary (prompt 13, revision 8). The operator's host git must not run what the agent writes into
# .git/hooks/ or a repository's .git/config. With `enforced` the agent's repositories are never the operator's
# checkout: a workspace inside a git work tree is refused, so the operator clones or fetches from the agent's
# repositories and works in a checkout of their own. With `lifted` the operator may point the workspace at their
# own checkout, and git there runs whatever the agent wrote. Either way the setting is shown on the agent's
# container (label xyz.ironik.timelike.host-git), in its environment (TIMELIKE_HOST_GIT) and in adele env up's
# verdict.
#
# Output (stdout): TIMELIKE_WORKSPACE, TIMELIKE_HOST_GIT and TIMELIKE_WORKSPACE_GID (the parent's group, which
# the agent is given with group_add so that uid 1000 can write where the parent's setgid group owns). Notes go
# to stderr. Exit 0, or 2 with the reason and what to do.
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mode="${1:-}"
case "${mode}" in
  env | check) ;;
  *)
    echo "usage: scripts/workspace.sh env|check" >&2
    exit 2
    ;;
esac

refuse() {
  echo "workspace: $1 (code 2) — $2" >&2
  exit 2
}

# local.env: KEY=VALUE lines, read without executing them; the environment takes precedence.
local_value() {
  local key="$1" line
  [[ -f "${repo}/local.env" ]] || return 0
  while IFS= read -r line || [[ -n "${line}" ]]; do
    if [[ "${line}" == "${key}="* ]]; then printf '%s' "${line#*=}"; fi
  done <"${repo}/local.env"
  return 0 # a key the file lacks is unset, not a failure (set -e would end the launch silently)
}

parent="${TIMELIKE_WORKSPACES:-$(local_value TIMELIKE_WORKSPACES)}"
given="${TIMELIKE_WORKSPACE:-$(local_value TIMELIKE_WORKSPACE)}"
host_git="${TIMELIKE_HOST_GIT:-$(local_value TIMELIKE_HOST_GIT)}"
host_git="${host_git:-enforced}"

case "${host_git}" in
  enforced | lifted) ;;
  *) refuse "TIMELIKE_HOST_GIT is '${host_git}'" "set it to enforced (the default) or lifted" ;;
esac

if [[ -z "${parent}" ]]; then
  refuse "TIMELIKE_WORKSPACES is not set" \
    "the operator sets it to the workspace parent, in the environment or in local.env (git-ignored), e.g. TIMELIKE_WORKSPACES=/path/to/workspaces"
fi
[[ "${parent}" == /* ]] || refuse "TIMELIKE_WORKSPACES '${parent}' is not an absolute path" "give the parent's absolute path"
[[ -d "${parent}" ]] || refuse "the workspace parent ${parent} does not exist" \
  "the operator creates it (FOR-MENTOR Item 27 Q6: owner 2001:2001, mode 2775)"

# A path git would read as inside a work tree. The host's own git answers, because it is the git the boundary is
# about. Without one there is nothing on this host to run the agent's hooks, and the check is said not made.
inside_work_tree() {
  local d="$1"
  git -C "${d}" rev-parse --is-inside-work-tree 2>/dev/null | grep -qx true
}

if [[ -n "${given}" ]]; then
  [[ "${given}" == /* ]] || refuse "TIMELIKE_WORKSPACE '${given}' is not an absolute path" "give an absolute path"
  [[ -d "${given}" ]] || refuse "TIMELIKE_WORKSPACE ${given} does not exist" "create it, or unset it for a new one"
  ws="$(cd "${given}" && pwd -P)"
else
  ws="$(cd "${parent}" && pwd -P)/$(date -u +%Y%m%dT%H%M%SZ)-$(od -An -N3 -tx1 /dev/urandom | tr -d ' \n')"
fi

if command -v git >/dev/null 2>&1; then
  for d in "${parent}" "${ws}"; do
    [[ -d "${d}" ]] || continue
    if inside_work_tree "${d}"; then
      if [[ "${host_git}" == enforced ]]; then
        refuse "${d} is inside a git work tree, and the host-git boundary is enforced" \
          "use a workspace outside every checkout of yours and clone or fetch from it; or launch with TIMELIKE_HOST_GIT=lifted, and git in that checkout will run what the agent writes there"
      fi
      echo "workspace: ${d} is inside a git work tree; TIMELIKE_HOST_GIT=lifted, so the operator's git there runs the agent's hooks and executing config" >&2
    fi
  done
else
  echo "workspace: no git on this host, so whether the workspace is inside a git work tree was not checked" >&2
fi

gid="$(stat -c %g "${parent}" 2>/dev/null || stat -f %g "${parent}")"

if [[ "${mode}" == env && ! -d "${ws}" ]]; then
  mkdir -m 2775 "${ws}" || refuse "cannot create ${ws}" "check that the parent is writable by $(id -un)"
fi

echo "workspace: ${ws} (host git ${host_git})" >&2
printf 'TIMELIKE_WORKSPACE=%q\nTIMELIKE_HOST_GIT=%q\nTIMELIKE_WORKSPACE_GID=%q\n' "${ws}" "${host_git}" "${gid}"
