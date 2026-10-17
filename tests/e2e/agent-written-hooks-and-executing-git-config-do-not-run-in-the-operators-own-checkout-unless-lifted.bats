#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside a container
# shellcheck disable=SC2030,SC2031 # bats runs each @test in its own subshell by design
# Feature 13 slice 0, criterion 4 (revision 8) — "A pre-commit hook and a core.hooksPath or core.fsmonitor setting
# written by the Agent in its workspace do not run when the Operator runs git in their own checkout on the host,
# unless the Operator lifted this at launch, and the launch configuration shows whether it was lifted" (send
# 13-rev17; spec FR-14; Item 27 Q2: a private clone the operator fetches from, TIMELIKE_HOST_GIT).
#
# The agent writes, in a repository in its workspace: .git/hooks/pre-commit, core.hooksPath (a directory with its
# own pre-commit), core.fsmonitor (a script), and uploadpack.packObjectsHook. Each one, if run, appends its name to
# a marker file and says so on stderr, so "it ran" and "it ran and could not write" differ. The operator is played by
# a real git outside the agent (cross-stack P004: never by reading the agent's config back): a throwaway of
# OPERATOR_GIT_IMAGE, the pinned DOCKER_CLI_IMAGE's git (2.54 at 29.9.0), which the lane's runner step builds so
# no cell pulls it (lane 13s0a, item C), run as the runner's uid with the workspace at the same path. It models a
# current git, not the host's 2.43: the git the operator is told to expect.
#   - enforced (the lane's launch): the operator clones the agent's repository into a checkout of their own, and
#     commit, status, fetch and pull there run none of them;
#   - control: the agent's own git, in its repository, does run its hooks, so the hooks are real;
#   - lifted: an operator who works in the agent's repository itself (what TIMELIKE_HOST_GIT=lifted permits) runs
#     them. The launcher's refusal and permission are scripts/workspace.sh's units (tests/unit/test_workspace_launcher.py);
#   - the launch shows the setting: the agent's label xyz.ironik.timelike.host-git and its TIMELIKE_HOST_GIT.
# Serial (lane.conf): Item 27 Q5 places the git-boundary cells there.
#
# git 2.45.1 and later refuse a local repository owned by another uid unless safe.directory names it: for a local
# clone or fetch, its .git directory as well as its work tree. The operator passes both, for exactly that
# repository, on the command line of each command that reads it, as the README says; nothing else is trusted.

load helpers
load nested

setup_file() {
  stamp_check
  nested_ready
}

teardown() { nested_teardown; }

# operator_git SCRIPT — run SCRIPT (sh) as the operator: a real git outside the agent, as the runner's uid, with
# the workspace at the same path. Prints what SCRIPT prints.
operator_git() {
  timeout "$PLUMBING_TIMEOUT" docker run --rm --pull never --network none --cap-drop ALL --label "${THROWAWAY_LABEL}=1" \
    -u "$(id -u):$(id -g)" --group-add "${TIMELIKE_WORKSPACE_GID:-$(id -g)}" -e HOME=/tmp \
    -v "${TIMELIKE_WORKSPACE}:${TIMELIKE_WORKSPACE}" --entrypoint sh "${OPERATOR_GIT_IMAGE:-timelike-operator-git:local}" \
    -c "umask 002; $1"
}

# safe — the operator's -c safe.directory for exactly the agent's repository: its work tree and its .git.
safe() { printf "%s" "-c safe.directory='${NP_DIR}' -c safe.directory='${NP_DIR}/.git'"; }

# agent_repo — the agent makes a repository in its project with every executing thing it can write.
agent_repo() {
  nested_project "$1"
  local d="$NP_DIR"
  run_in -w "$d" c notty "
umask 002
git init -q . && git config user.email agent@example.invalid && git config user.name agent
mk() { printf '#!/bin/sh\necho \"hook %s ran\" >&2\necho %s >> \"\${TL_MARK:-/tmp/tl-ran}\" || echo \"hook %s could not write its marker\" >&2\nexit 0\n' \"\$2\" \"\$2\" \"\$2\" > \"\$1\" && chmod 0775 \"\$1\"; }
mk .git/hooks/pre-commit hooks-dir
mkdir -p .githooks && mk .githooks/pre-commit hooks-path
mk .git/fsmon fsmonitor
mk .git/pack-hook pack-objects
git config core.hooksPath '${d}/.githooks'
git config core.fsmonitor '${d}/.git/fsmon'
git config uploadpack.packObjectsHook '${d}/.git/pack-hook'
echo one > a && git add a && TL_MARK=/dev/null git commit -q --no-verify -m one && echo made"
  assert_status 0
  assert_output_has made
}

@test "13 the operator's git in their own checkout runs none of the agent's hooks or executing config (enforced)" {
  agent_repo enforced
  run operator_git "
git --version || exit 9
set -e
cd /tmp && git $(safe) clone -q '${NP_DIR}' op && cd op
git config user.email op@example.invalid && git config user.name op
echo two > b && git add b && git commit -q -m two
git status --short >/dev/null
git $(safe) fetch -q origin
git $(safe) pull -q --no-rebase origin HEAD
git log --format=%s | tr '\n' ' ' && echo
echo \"ran: \$(cat /tmp/tl-ran 2>/dev/null | tr '\n' ' ')\""
  assert_status 0
  # The operator's own commit and the agent's, through clone, fetch and pull: the git operations happened.
  assert_output_has "two one"
  if [[ "$output" == *"hook "*" ran"* ]]; then echo "a hook of the agent's ran: $output" >&2; return 1; fi
  [[ "${lines[0]}" == "git version "* ]] || { echo "no git in OPERATOR_GIT_IMAGE: $output" >&2; return 1; }
  [[ "${lines[-1]}" == "ran: " ]] || { echo "the operator's git ran the agent's: ${lines[-1]}" >&2; return 1; }
}

@test "13 control: the agent's own git in its repository does run the hooks it wrote" {
  agent_repo control
  run_in -w "$NP_DIR" c notty "command rm -f /tmp/tl-ran-control; echo three > c && git add c && TL_MARK=/tmp/tl-ran-control git commit -q -m three; cat /tmp/tl-ran-control"
  assert_status 0
  assert_output_has hooks-path
}

@test "13 lifted: an operator who works in the agent's repository itself runs what the agent wrote" {
  agent_repo lifted
  run operator_git "
cd '${NP_DIR}' && echo four > d && git $(safe) add d &&
TL_MARK=/tmp/tl-ran git $(safe) -c user.email=op@example.invalid -c user.name=op commit -q -m four && echo committed
echo \"ran: \$(cat /tmp/tl-ran 2>/dev/null | tr '\n' ' ')\""
  assert_output_has committed
  assert_output_has "hook hooks-path ran"
  [[ "${lines[-1]}" == *hooks-path* ]] || { echo "the hook ran but its marker was not written: $output" >&2; return 1; }
}

@test "13 the launch configuration shows the host-git setting: the agent's label and its environment" {
  local label
  label="$(docker inspect --format '{{ index .Config.Labels "xyz.ironik.timelike.host-git" }}' "$AGENT_CONTAINER")"
  [[ "$label" == enforced ]] || { echo "label: '$label'" >&2; return 1; }
  run_in c notty 'printf "%s\n" "$TIMELIKE_HOST_GIT"'
  assert_status 0
  [[ "$output" == enforced ]]
  run_in lc notty 'printf "%s\n" "$TIMELIKE_HOST_GIT"'
  [[ "$output" == enforced ]]
}
