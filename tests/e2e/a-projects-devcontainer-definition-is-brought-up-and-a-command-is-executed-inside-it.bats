#!/usr/bin/env bats
# shellcheck disable=SC2016 # single-quoted strings here are commands expanded inside the container
# shellcheck disable=SC2030,SC2031 # bats runs each @test in its own subshell by design
# Feature 13 slice 1, criterion 7 — "A project's devcontainer definition is brought up and a command is executed
# inside it" (send 13-rev17's slice 1; spec Scenarios 7, 8 and 10, FR-16 to FR-19, FR-23, FR-25; research R12, R13,
# R15-R17, R22). D22, the demo, is Manual and is not this file.
#
# From inside the agent, in a project with only a .devcontainer/devcontainer.json (no root compose file, so `adele env
# up` chooses the devcontainer itself, R12 "Which file"), under bash -c and bash -lc:
#   - the image form (fixtures/nested/devcontainer: JSONC with comments and trailing commas, remoteUser, remoteEnv,
#     workspaceFolder, forwardPorts, postCreateCommand, postStartCommand, postAttachCommand): up exits 0, its verdict
#     says devcontainer, each lifecycle command is named with its exit, the one never run is named, and the forwarded
#     port is an address reached from the agent's container;
#   - `adele env exec -- CMD` runs CMD in it as the remoteUser, in the workspace folder (the project's own absolute
#     path), with remoteEnv set, and passes CMD's exit status through (0 and 7);
#   - the postCreateCommand ran there as that user: the file it wrote is read from the agent's side;
#   - the daemon, read from the runner (cross-stack P004), has the container labelled as the devcontainer with its
#     remote user and folder, and the project directory bound at its own path.
# The build form (fixtures/nested/devcontainer-build: a two-layer Dockerfile whose base is a build arg) is built with
# nothing pulled, exec reads what the build wrote, a second up builds nothing and reuses the image, the image is on
# the daemon labelled with the environment, and `adele env down` removes it, read back.
# And exec names what does not exist: no environment, or no such service, is exit 3.

load helpers
load nested

setup_file() {
  stamp_check
  stamp_check_adele
}

teardown() { nested_teardown; }

# devcontainer_project CELL FIXTURE — a project holding only the fixture's files, written by the agent.
devcontainer_project() {
  nested_project "$1"
  nested_files "$2"
}

check_devcontainer_up_and_exec() {
  local style="$1" c m
  devcontainer_project "dc-${style}" devcontainer
  # The postCreateCommand writes into the project as the remote user (nobody), which is not in the workspace's group.
  exec_plain chmod 2777 "$NP_DIR"
  env_run "$style" "--text env up --project ${NP_NAME} --grant nested"
  assert_status 0
  [[ "${lines[1]}" == "verdict: up ${NP_NAME}: devcontainer, 1 ready in "* ]] || { echo "verdict: ${lines[1]}" >&2; return 1; }
  assert_output_has "read back, ports probed from the agent container · local: no cost · host git enforced"
  assert_output_has "devcontainer  ready (running, ports accept)  devcontainer.${NP_NAME}:8080"
  assert_output_has "postCreateCommand  exit 0"
  assert_output_has "postStartCommand  exit 0"
  assert_output_has "not run: postAttachCommand (no attach)"
  # The forwarded port is an address on timelike-nested, reached again from the agent's container (cross-stack P001).
  run_in "$style" notty "$AGENT_PY -I -c 'import urllib.request as u; print(u.urlopen(\"http://devcontainer.${NP_NAME}:8080/\", timeout=10).status)'"
  assert_status 0
  [[ "$output" == 200 ]] || { echo "GET devcontainer.${NP_NAME}:8080 from the agent: $output" >&2; return 1; }

  # A command inside it: the remote user, the workspace folder, remoteEnv; and the lifecycle's file, read there.
  env_run "$style" "--text env exec ${NP_NAME} -- sh -c 'echo pwd=\$(pwd); echo user=\$(id -un); echo greeting=\$TL_GREETING; echo marker=\$(cat .tl-postcreate)'"
  assert_status 0
  [[ "${lines[1]}" == "verdict: exec ${NP_NAME} devcontainer as nobody: exit 0 in "* ]] || { echo "exec verdict: ${lines[1]}" >&2; return 1; }
  assert_value pwd "$NP_DIR"
  assert_value user nobody
  assert_value greeting "hello from remoteEnv"
  assert_value marker nobody
  # The exit status passes through (03's run): 7 is the agent's 7, with the command's own output.
  env_run "$style" "--text env exec ${NP_NAME} -- sh -c 'echo before seven; exit 7'"
  assert_status 7
  [[ "${lines[1]}" == "verdict: exec ${NP_NAME} devcontainer as nobody: exit 7 in "* ]] || { echo "exec verdict: ${lines[1]}" >&2; return 1; }
  assert_output_has "before seven"
  # The postCreateCommand's file, read from the agent's side of the same directory: it ran there, as nobody.
  run_in "$style" notty "cat '${NP_DIR}/.tl-postcreate'"
  assert_status 0
  [[ "$output" == nobody ]] || { echo "the agent read .tl-postcreate: $output" >&2; return 1; }

  # The daemon's own record: one container, the devcontainer, labelled as such, its project bound at its own path.
  c="$(nested_container "$NP_NAME" devcontainer)"
  [[ -n "$c" ]] || { echo "no devcontainer container labelled ${NP_NAME}" >&2; return 1; }
  [[ "$(docker inspect --format '{{index .Config.Labels "xyz.ironik.timelike.devcontainer"}} {{index .Config.Labels "xyz.ironik.timelike.remote-user"}} {{index .Config.Labels "xyz.ironik.timelike.workdir"}}' "$c")" == "1 nobody ${NP_DIR}" ]] ||
    { echo "labels: $(docker inspect --format '{{json .Config.Labels}}' "$c")" >&2; return 1; }
  [[ "$(docker inspect --format '{{.State.Status}}' "$c")" == running ]]
  m="$(docker inspect --format '{{range .Mounts}}{{if eq .Type "bind"}}{{.Source}}={{.Destination}};{{end}}{{end}}' "$c")"
  [[ "$m" == *"${NP_DIR}=${NP_DIR};"* ]] || { echo "the devcontainer's binds: $m (want ${NP_DIR} at itself)" >&2; return 1; }
  # Each exec is a performed ledger row with no undo, naming the service, the command and its exit (R17).
  run ledger_rows_for "$NP_NAME"
  assert_status 0
  assert_output_has $'performed\texec\t'
  assert_output_has "exec in service devcontainer as nobody: sh -c echo before seven; exit 7: exit 7"
}
@test "13 a project's devcontainer definition is brought up and a command is executed inside it [bash -c]" { check_devcontainer_up_and_exec c; }
@test "13 a project's devcontainer definition is brought up and a command is executed inside it [bash -lc]" { check_devcontainer_up_and_exec lc; }

@test "13 a devcontainer with a build is built with nothing pulled, a second up reuses it, and down removes the image" {
  local tag
  devcontainer_project dc-build devcontainer-build
  env_run c "--text env up --project ${NP_NAME} --grant nested"
  assert_status 0
  [[ "${lines[1]}" == "verdict: up ${NP_NAME}: devcontainer, 1 running with no readiness check in "* ]] ||
    { echo "verdict: ${lines[1]}" >&2; return 1; }
  assert_output_has "devcontainer  running, no readiness check"
  assert_output_has "built devcontainer: ${NP_NAME}-devcontainer:"
  assert_output_has " s (nothing pulled)"
  env_run c "--text env exec ${NP_NAME} -- cat /built"
  assert_status 0
  [[ "${lines[1]}" == "verdict: exec ${NP_NAME} devcontainer as the image's user: exit 0 in "* ]] || { echo "exec verdict: ${lines[1]}" >&2; return 1; }
  [[ "${lines[2]:-}" == built ]] || { echo "cat /built: $output" >&2; return 1; }
  # The image, on the daemon, labelled with the environment and tagged under its name (FR-23).
  [[ "$(nested_image_count "$NP_NAME")" == 1 ]] || { echo "images labelled ${NP_NAME}: $(nested_image_count "$NP_NAME")" >&2; return 1; }
  tag="$(docker image ls --filter "label=${NESTED_LABEL}=${NP_NAME}" --format '{{.Repository}}:{{.Tag}}')"
  [[ "$tag" == "${NP_NAME}-devcontainer:"* ]] || { echo "the built image's tag: $tag" >&2; return 1; }

  # Unchanged: nothing built, created or recorded; the image is reused, by its key.
  env_run c "--text env up --project ${NP_NAME} --grant nested"
  assert_status 0
  [[ "${lines[1]}" == "verdict: up ${NP_NAME}: devcontainer, 1 running with no readiness check, unchanged (nothing created or recorded) in "* ]] ||
    { echo "second verdict: ${lines[1]}" >&2; return 1; }
  assert_output_has "reused devcontainer: ${tag} (unchanged)"
  [[ "$output" != *"built devcontainer:"* ]] || { echo "the second up built again: $output" >&2; return 1; }
  [[ "$(nested_image_count "$NP_NAME")" == 1 ]]

  # down removes the image too, after its container, read back.
  env_run c "--text env down ${NP_NAME}"
  assert_status 0
  [[ "${lines[1]}" == "verdict: down ${NP_NAME}: removed 1 containers, "*", 1 images; 0 left, read back from the daemon" ]] ||
    { echo "down: ${lines[1]}" >&2; return 1; }
  nested_gone "$NP_NAME"
  run ! docker image inspect "$tag"
}

@test "13 exec into an environment that does not exist is exit 3 and runs nothing" {
  nested_project dc-none
  env_run c "--text env exec ${NP_NAME} -- true"
  assert_status 3
  assert_output_has "error: no live environment named ${NP_NAME} (code 3) — list them with adele env status"
}

@test "13 exec into a service the environment does not have is exit 3 naming its services" {
  nested_project dc-nosvc
  nested_compose 'services:
  app:
    image: ${FIXTURE_IMAGE:?}
    command: ["sleep", "infinity"]'
  env_run c "--text env up --project ${NP_NAME} --grant nested"
  assert_status 0
  env_run c "--text env exec ${NP_NAME} --service nosuch -- true"
  assert_status 3
  assert_output_has "error: ${NP_NAME} has no service nosuch (code 3) — its services: app"
}

# Kept apart from criterion 7's cell: R12 keeps ${containerEnv:X} literally in remoteEnv for exec to resolve, and the
# remote-env label carrying it goes through compose's own interpolation when Adele brings the model up (compose.Inject),
# which does not know that form. If that is refused, this cell says so, and criterion 7's cell is not hidden by it.
@test "13 a remoteEnv value naming containerEnv:X is read from the devcontainer's own environment" {
  nested_project dc-cenv
  nested_write .devcontainer/devcontainer.json '{
  // containerEnv is the container environment; remoteEnv reads it back for exec (014 plan R12).
  "image": "'"${DEBIAN_IMAGE}"'",
  "containerEnv": {"TL_FROM_CONTAINER": "set-by-containerEnv"},
  "remoteEnv": {"TL_ECHO": "${containerEnv:TL_FROM_CONTAINER}/via-remoteEnv"},
}'
  env_run c "--text env up --project ${NP_NAME} --grant nested"
  assert_status 0
  env_run c "--text env exec ${NP_NAME} -- sh -c 'echo echo=\$TL_ECHO'"
  assert_status 0
  assert_value echo "set-by-containerEnv/via-remoteEnv"
}
