# timelike bench — the VANILLA baseline image (feature 002, T010). Build context: the repository root.
#
# The bench compares a task run here against the same task run in timelike-agent:local, so what this
# image does NOT contain is its whole meaning (P6: a comparison means only what its baseline is).
# It shares with the agent image exactly: the pinned DEBIAN_IMAGE digest, the `agent` user (uid/gid
# 1000, empty home, bash), `USER agent`, and git — the catalog's one declared prerequisite (RB1).
# It deliberately has NONE of timelike's layers: no ENV block, no /etc/gitconfig, no shell-env hook, no
# profile.d files, no timelike interpreter, no timelike tools, no setuid sweep. Adding any of them here
# would make the bench measure timelike against a partial timelike.
# Since discovery revision 14 (feature 007 slice 1, spec FR-13 revised and FR-30) it carries the agent's
# runtimes, an agent Python and Node, built by the SAME `runtimes` stage as image/Dockerfile from the same
# pins, so both arms have the same binaries (RB1: a prerequisite goes into both images or neither). They
# keep their STOCK behaviour here: the interpreter keeps its EXTERNALLY-MANAGED marker, npm keeps its default
# prefix (/opt/agent/node), and none of timelike's configuration goes in (no pip.conf, no npmrc, no
# ~/.local/bin on PATH). So a bare `pip install` is refused and `npm install -g` fails without privilege
# here, as in an image that ships the runtimes without timelike. Only the seven names the agent image puts on
# PATH are linked, so both arms find the same commands. This is feature 002's file; 02 s1 records it.
# It also lacks procps, ca-certificates and less, which git recommends or timelike installs (RB1): a
# task may use only what BOTH images contain, and a prerequisite goes into both images or neither.
#
# Every pin arrives as a build argument from pins.env; this file repeats none of them. Research items
# cited below live in .specswarm/features/002-speedup-bench/research.md.

ARG DEBIAN_IMAGE
ARG UV_IMAGE

# The agent runtimes stage, copied byte for byte from image/Dockerfile (a unit test checks the two agree).
FROM ${UV_IMAGE} AS uv

# The agent's runtimes (feature 007 slice 1, discovery revision 14; 007 spec FR-25, D-14, D-15): an agent
# Python (uv-managed CPython at PYTHON_VERSION) and Node (the official tarball, NODE_VERSION, checked against
# NODE_SHA256), both under /opt/agent. Built in a stage of their own so bench/vanilla/Dockerfile can run the
# identical steps: the two bench arms carry the same binaries (RB1). Configuration is the final stage's job.
# The slim base has no curl and no xz, so the tarball comes by ADD and is the .tar.gz.
FROM ${DEBIAN_IMAGE} AS runtimes
SHELL ["/bin/bash", "-o", "errexit", "-o", "nounset", "-o", "pipefail", "-c"]
COPY --from=uv /uv /bin/uv
ARG PYTHON_VERSION
ARG NODE_VERSION
ARG NODE_SHA256
ADD https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-x64.tar.gz /tmp/node.tar.gz
RUN test -n "${PYTHON_VERSION:-}" && test -n "${NODE_VERSION:-}" \
      || { echo "error: PYTHON_VERSION or NODE_VERSION build arg is empty — pass them from pins.env" >&2; exit 1; } \
 && [[ "${NODE_SHA256:-}" =~ ^[0-9a-f]{64}$ ]] \
      || { echo "error: NODE_SHA256 build arg is not a SHA-256 — pass it from pins.env" >&2; exit 1; } \
 && printf '%s  %s\n' "${NODE_SHA256}" /tmp/node.tar.gz | sha256sum -c - \
      || { echo "error: node-v${NODE_VERSION}-linux-x64.tar.gz does not match NODE_SHA256 (pins.env) — refusing it" >&2; exit 1; } \
 && mkdir -p /opt/agent/node \
 && tar -xzf /tmp/node.tar.gz -C /opt/agent/node --strip-components=1 --no-same-owner \
 && rm -f /tmp/node.tar.gz \
 && test "$(/opt/agent/node/bin/node --version)" = "v${NODE_VERSION}" \
 && UV_NO_CACHE=1 UV_PYTHON_INSTALL_DIR=/opt/agent \
      uv python install "${PYTHON_VERSION}" --install-dir /opt/agent --no-bin --compile-bytecode \
 && test -x "/opt/agent/cpython-${PYTHON_VERSION}-linux-x86_64-gnu/bin/python3" \
 && ln -s "cpython-${PYTHON_VERSION}-linux-x86_64-gnu" /opt/agent/python \
 && find /opt/agent -mindepth 1 -maxdepth 1 \( -name '.*' -o -type l ! -name python \) -exec rm -rf {} + \
 && /opt/agent/python/bin/python3 -I -c \
      'import platform, sys; v = platform.python_version(); sys.exit(0 if v == sys.argv[1] else "error: agent interpreter is " + v + ", pinned " + sys.argv[1])' \
      "${PYTHON_VERSION}" \
 && chown -R root:root /opt/agent

FROM ${DEBIAN_IMAGE}

# Build-time shell only; it does not affect the running container's shells.
SHELL ["/bin/bash", "-o", "errexit", "-o", "nounset", "-o", "pipefail", "-c"]

# --- 1. OS packages: git and nothing else (RB1) -------------------------------------------------------
# --no-install-recommends keeps out ca-certificates, less, patch and ssh-client (git's recommends). The
# checks after the install fail the build if any of them, or procps, arrived anyway, and confirm that
# `timeout` and `sh` (coreutils, dash — base image) are present for the in-container wrapper (RB5).
# Targeted upgrade (operator, 2026-10-01; FOR-MENTOR Item 12): Debian fixed OpenSSL (CVE-2026-54873,
# -72897, -84782, -84784 in 3.5.7-1~deb13u3) and PCRE2 (CVE-2026-103111 in 10.46-1~deb13u3), and no
# published trixie-slim carries them yet (the pinned digest is the newest build). --only-upgrade replaces
# packages the base already has and installs nothing new, so this stays "Debian + git". The agent image
# already carries the fixed OpenSSL, so the two bench arms stay comparable. This line comes out when a
# trixie-slim newer than a99cfc517144 ships OpenSSL 3.5.7-1~deb13u3 and PCRE2 10.46-1~deb13u3 or later
# (watch item).
RUN DEBIAN_FRONTEND=noninteractive apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends git \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends --only-upgrade \
      libssl3t64 openssl-provider-legacy libpcre2-8-0 \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/* \
 && git --version \
 && for pkg in ca-certificates less patch openssh-client procps; do \
      if dpkg -s "${pkg}" >/dev/null 2>&1; then \
        echo "error: ${pkg} is installed in the vanilla image (code 1) — RB1 allows git only; check the install for recommends" >&2; exit 1; fi; \
    done \
 && if ! command -v timeout || ! command -v sh; then \
      echo "error: timeout or sh is missing from the base image (code 1) — the bench's in-container limit wrapper needs both (RB5); re-check DEBIAN_IMAGE" >&2; exit 1; fi

# --- 1b. The agent's runtimes with stock behaviour (FR-13 revised, FR-30) ---------------------------------
# The same /opt/agent the agent image copies, and the same seven links; nothing else.
COPY --from=runtimes /opt/agent /opt/agent
RUN for n in python3 python pip pip3; do ln -s "/opt/agent/python/bin/${n}" "/usr/local/bin/${n}"; done \
 && for n in node npm npx; do ln -s "/opt/agent/node/bin/${n}" "/usr/local/bin/${n}"; done \
 && test -n "$(find /opt/agent/python/lib -maxdepth 2 -name EXTERNALLY-MANAGED -print -quit)" \
 && /usr/local/bin/python3 --version && /usr/local/bin/node --version

# --- 2. The agent user, as in image/Dockerfile §4 but without adele ----------------------------------
# uid/gid 1000, empty home (no /etc/skel dotfiles: vanilla has no rc-file defaults either), login shell
# /bin/bash, no supplementary groups. Fail loudly if the base image already uses the id (lore
# docker-compose Q003). No adele: the reserved identity is a timelike layer.
RUN for id in 1000; do \
      if getent passwd "${id}" >/dev/null || getent group "${id}" >/dev/null; then \
        echo "error: uid/gid ${id} already exists in the base image (code 1) — refusing to create a colliding user; re-check DEBIAN_IMAGE" >&2; \
        getent passwd "${id}" >&2 || true; getent group "${id}" >&2 || true; exit 1; fi; \
    done \
 && groupadd --gid 1000 agent \
 && useradd --uid 1000 --gid agent --no-create-home --home-dir /home/agent \
      --shell /bin/bash --no-log-init agent \
 && install -d -o agent -g agent -m 0750 /home/agent \
 && test "$(id -u agent):$(id -G agent)" = "1000:1000" \
 && test -z "$(find /home/agent -mindepth 1 -print -quit)"

# --- 3. Build stamp (RB8, H8). Last, so only this layer changes per commit. --------------------------
# Label only, no REVISION file: the driver reads the label (RB8), and a file would be one more thing in
# vanilla that Debian does not ship.
ARG GIT_SHA
RUN if [ -z "${GIT_SHA:-}" ]; then \
      echo "error: GIT_SHA build arg is empty (code 1) — refusing to build an unstamped image (H8); build through make, which passes it" >&2; exit 1; fi \
 && if ! [[ "${GIT_SHA}" =~ ^[0-9a-f]{7,64}$ ]]; then \
      echo "error: GIT_SHA build arg '${GIT_SHA}' is not a git revision (code 1) — pass git rev-parse HEAD (H8)" >&2; exit 1; fi
LABEL org.opencontainers.image.revision=$GIT_SHA \
      org.opencontainers.image.title="timelike bench vanilla baseline" \
      org.opencontainers.image.description="Debian + git + the agent runtimes (stock) + agent uid 1000, without any of timelike's layers (feature 002 RB1)"

# --- 4. Run as the unprivileged agent, like the agent image ------------------------------------------
USER agent
WORKDIR /home/agent
