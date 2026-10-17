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
# a marker file. The operator is played by a real git outside the agent (cross-stack P004: never by reading the
# agent's config back): a throwaway of DOCKER_CLI_IMAGE, which carries git, run as the runner's uid with the
# workspace at the same path.
#   - enforced (the lane's launch): the operator clones the agent's repository into a checkout of their own, and
#     commit, status, fetch and pull there run none of them;
#   - control: the agent's own git, in its repository, does run its hooks, so the hooks are real;
#   - lifted: an operator who works in the agent's repository itself (what TIMELIKE_HOST_GIT=lifted permits) runs
#     them. The launcher's refusal and permission are scripts/workspace.sh's units (tests/unit/test_workspace_launcher.py);
#   - the launch shows the setting: the agent's label xyz.ironik.timelike.host-git and its TIMELIKE_HOST_GIT.
# Serial (lane.conf): Item 27 Q5 places the git-boundary cells there.
#
# git 2.45.1 and later refuse a local repository owned by another uid unless safe.directory names it; the operator
# passes it on the command line for that one command, as the README says.

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
  timeout "$PLUMBING_TIMEOUT" docker run --rm --network none --cap-drop ALL --label "${THROWAWAY_LABEL}=1" \
    -u "$(id -u):$(id -g)" --group-add "${TIMELIKE_WORKSPACE_GID:-$(id -g)}" -e HOME=/tmp \
    -v "${TIMELIKE_WORKSPACE}:${TIMELIKE_WORKSPACE}" --entrypoint sh "$DOCKER_CLI_IMAGE" -c "umask 002; $1"
}

# agent_repo — the agent makes a repository in its project with every executing thing it can write.
agent_repo() {
  nested_project "$1"
  local d="$NP_DIR"
  run_in -w "$d" c notty "
umask 002
git init -q . && git config user.email agent@example.invalid && git config user.name agent
mk() { printf '#!/bin/sh\necho %s >> \"\${TL_MARK:-/tmp/tl-ran}\"\nexit 0\n' \"\$2\" > \"\$1\" && chmod 0775 \"\$1\"; }
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
cd /tmp && git -c safe.directory='${NP_DIR}' clone -q '${NP_DIR}' op && cd op
git config user.email op@example.invalid && git config user.name op
echo two > b && git add b && git commit -q -m two
git status --short >/dev/null
git -c safe.directory='${NP_DIR}' fetch -q origin
git -c safe.directory='${NP_DIR}' pull -q --no-rebase origin HEAD
echo \"ran: \$(cat /tmp/tl-ran 2>/dev/null | tr '\n' ' ')\""
  assert_status 0
  [[ "${lines[0]}" == "git version "* ]] || { echo "no git in DOCKER_CLI_IMAGE: $output" >&2; return 1; }
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
cd '${NP_DIR}' && echo four > d && git -c safe.directory='${NP_DIR}' add d &&
TL_MARK=/tmp/tl-ran git -c safe.directory='${NP_DIR}' -c user.email=op@example.invalid -c user.name=op commit -q -m four
echo \"ran: \$(cat /tmp/tl-ran 2>/dev/null | tr '\n' ' ')\""
  [[ "${lines[-1]}" == *hooks-path* ]] || { echo "the hook did not run in the agent's repository: $output" >&2; return 1; }
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
