# timelike bench — the HARNESS image (feature 002 slice 1, FR-23 and FR-24; research RB14). Build context: the
# repository root.
#
# It holds the pinned live harnesses the bench measures, and nothing else. It is never run. Per bench
# invocation the driver `docker create`s one container from it, and every task container (vanilla and timelike
# alike) takes its volume read-only (`--volumes-from <it>:ro`) at /opt/bench-harness. So a harness runs inside the
# task container, as the agent's tool calls must, while neither image under test gains anything (P6; send seam 2).
#
# Each harness is the native linux-x64 binary from its npm package, checked against the registry's sha512
# integrity (in pins.env as hex) before it is unpacked:
#   OpenCode   opencode-linux-x64@OPENCODE_VERSION             package/bin/opencode (glibc; Bun-compiled)
#   Codex CLI  @openai/codex@CODEX_VERSION-linux-x64           package/vendor/x86_64-unknown-linux-musl/bin/codex
# The binary is run directly, not through the npm launcher script, so neither harness needs Node.
#
# Every pin arrives as a build argument from pins.env; this file repeats none of them.

ARG DEBIAN_IMAGE

FROM ${DEBIAN_IMAGE} AS fetch
SHELL ["/bin/bash", "-o", "errexit", "-o", "nounset", "-o", "pipefail", "-c"]
ARG OPENCODE_VERSION
ARG OPENCODE_SHA512
ARG CODEX_VERSION
ARG CODEX_SHA512
ADD https://registry.npmjs.org/opencode-linux-x64/-/opencode-linux-x64-${OPENCODE_VERSION}.tgz /tmp/opencode.tgz
ADD https://registry.npmjs.org/@openai/codex/-/codex-${CODEX_VERSION}-linux-x64.tgz /tmp/codex.tgz
RUN for pair in "OPENCODE:${OPENCODE_SHA512:-}" "CODEX:${CODEX_SHA512:-}"; do \
      [[ "${pair#*:}" =~ ^[0-9a-f]{128}$ ]] \
        || { echo "error: ${pair%%:*}_SHA512 build arg is not a SHA-512 — pass it from pins.env" >&2; exit 1; }; \
    done \
 && printf '%s  %s\n' "${OPENCODE_SHA512}" /tmp/opencode.tgz | sha512sum -c - \
      || { echo "error: opencode-linux-x64-${OPENCODE_VERSION}.tgz does not match OPENCODE_SHA512 — refusing it" >&2; exit 1; } \
 && printf '%s  %s\n' "${CODEX_SHA512}" /tmp/codex.tgz | sha512sum -c - \
      || { echo "error: codex-${CODEX_VERSION}-linux-x64.tgz does not match CODEX_SHA512 — refusing it" >&2; exit 1; } \
 && mkdir -p /tmp/oc /tmp/cx /opt/bench-harness/opencode/bin /opt/bench-harness/codex/bin \
 && tar -xzf /tmp/opencode.tgz -C /tmp/oc --no-same-owner package/bin/opencode \
 && tar -xzf /tmp/codex.tgz -C /tmp/cx --no-same-owner package/vendor/x86_64-unknown-linux-musl/bin/codex \
 && install -o root -g root -m 0755 /tmp/oc/package/bin/opencode /opt/bench-harness/opencode/bin/opencode \
 && install -o root -g root -m 0755 /tmp/cx/package/vendor/x86_64-unknown-linux-musl/bin/codex \
      /opt/bench-harness/codex/bin/codex \
 && rm -rf /tmp/oc /tmp/cx /tmp/opencode.tgz /tmp/codex.tgz \
 && got="$(HOME=/tmp /opt/bench-harness/opencode/bin/opencode --version)" \
 && [ "${got##* }" = "${OPENCODE_VERSION}" ] \
      || { echo "error: opencode reports '${got}', the pin is ${OPENCODE_VERSION}" >&2; exit 1; } \
 && got="$(HOME=/tmp CODEX_HOME=/tmp/codex-home /opt/bench-harness/codex/bin/codex --version 2>/dev/null)" \
 && [ "${got##* }" = "${CODEX_VERSION}" ] \
      || { echo "error: codex reports '${got}', the pin is ${CODEX_VERSION}" >&2; exit 1; } \
 && rm -rf /tmp/codex-home /tmp/.cache /tmp/.local /tmp/.config

# The build stamp (RB8, H8), checked here because the final stage has no shell to check it in.
ARG GIT_SHA
RUN if [ -z "${GIT_SHA:-}" ]; then \
      echo "error: GIT_SHA build arg is empty (code 1) — refusing to build an unstamped image (H8); build through make, which passes it" >&2; exit 1; fi \
 && if ! [[ "${GIT_SHA}" =~ ^[0-9a-f]{7,64}$ ]]; then \
      echo "error: GIT_SHA build arg '${GIT_SHA}' is not a git revision (code 1) — pass git rev-parse HEAD (H8)" >&2; exit 1; fi

FROM scratch
COPY --from=fetch /opt/bench-harness /opt/bench-harness
# `docker create` fills an anonymous volume from this path once per invocation; task containers mount it read-only.
VOLUME /opt/bench-harness
ARG GIT_SHA
ARG OPENCODE_VERSION
ARG CODEX_VERSION
LABEL org.opencontainers.image.revision=$GIT_SHA \
      org.opencontainers.image.title="timelike bench harnesses" \
      org.opencontainers.image.description="OpenCode ${OPENCODE_VERSION} and Codex CLI ${CODEX_VERSION}, mounted read-only into bench task containers; never run itself (feature 002 FR-24)"
