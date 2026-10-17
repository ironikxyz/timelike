# Test runner for the Docker lane (research.md R8). bats-core drives the agent container from
# OUTSIDE via `docker exec`, because a test running inside the image it verifies only proves that
# image agrees with itself (lore cross-stack P005). The host socket is mounted into THIS container
# only — never into the agent image (constitution H1, P4).
ARG BATS_IMAGE
ARG DOCKER_CLI_IMAGE
FROM ${DOCKER_CLI_IMAGE} AS dockercli

# The operator's git for feature 13's git-boundary cells (lane 13s0a, item C): the pinned CLI image, which carries
# git, built by the lane's runner step as timelike-operator-git:local, so no cell pulls it by digest.
FROM ${DOCKER_CLI_IMAGE} AS operator-git

FROM ${BATS_IMAGE}
COPY --from=dockercli /usr/local/bin/docker /usr/local/bin/docker
