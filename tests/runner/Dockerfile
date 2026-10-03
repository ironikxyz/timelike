# Test runner for the Docker lane (research.md R8). bats-core drives the agent container from
# OUTSIDE via `docker exec`, because a test running inside the image it verifies only proves that
# image agrees with itself (lore cross-stack P005). The host socket is mounted into THIS container
# only — never into the agent image (constitution H1, P4).
ARG BATS_IMAGE
ARG DOCKER_CLI_IMAGE
FROM ${DOCKER_CLI_IMAGE} AS dockercli
FROM ${BATS_IMAGE}
COPY --from=dockercli /usr/local/bin/docker /usr/local/bin/docker
