# timelike bench — the DRIVER image (feature 002, T011; research RB6). Build context: the repository root.
#
# The driver runs timelike-bench, which starts one container per run from the agent and vanilla images
# and drives them through `docker exec` (RB2, RB5). It is a third image, built from DEBIAN_IMAGE rather
# than from the agent image: the Docker socket must never be mounted into a timelike image (H1), and the
# driver must not be one of the environments it measures (lore cross-stack P005). It is the only
# container that holds the socket.
#
# Every pin arrives as a build argument from pins.env; this file repeats none of them. Research items
# cited below live in .specswarm/features/002-speedup-bench/research.md; §2 and §3 mirror
# image/Dockerfile (feature 001, research R6).
#
# RB10 risk: /usr/local/bin/docker is a Go binary. Grype will likely report fixable Go-stdlib Highs in
# it, which block the scan gate until DOCKER_CLI_IMAGE is bumped. Recorded, not fixed here.

ARG DEBIAN_IMAGE
ARG UV_IMAGE
ARG DOCKER_CLI_IMAGE

# uv ships as a distroless image holding /uv and /uvx (001 R6).
FROM ${UV_IMAGE} AS uv
# The docker CLI, as tests/runner/Dockerfile takes it (RB6).
FROM ${DOCKER_CLI_IMAGE} AS dockercli

FROM ${DEBIAN_IMAGE}

# Build-time shell only; it does not affect the running container's shells.
SHELL ["/bin/bash", "-o", "errexit", "-o", "nounset", "-o", "pipefail", "-c"]

# --- 1. OS packages: none installed; three upgraded ---------------------------------------------------
# No package is installed. The driver talks only to the local socket (no TLS, so no ca-certificates),
# needs no git (RB8: bench/run.sh passes GIT_SHA), and the base image already has coreutils and dash.
# Every package added here would be one more thing for the scan gate (RB10) to report.
# Targeted upgrade (operator, 2026-10-01; FOR-MENTOR Item 12): Debian fixed OpenSSL (CVE-2026-54873,
# -72897, -84782, -84784 in 3.5.7-1~deb13u3) and PCRE2 (CVE-2026-103111 in 10.46-1~deb13u3) in packages
# the base image already has, and no published trixie-slim carries them yet (the pinned digest is the
# newest build). --only-upgrade replaces those and installs nothing new. This step comes out when a
# trixie-slim newer than a99cfc517144 ships OpenSSL 3.5.7-1~deb13u3 and PCRE2 10.46-1~deb13u3 or later
# (watch item).
RUN DEBIAN_FRONTEND=noninteractive apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends --only-upgrade \
      libssl3t64 openssl-provider-legacy libpcre2-8-0 \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

# --- 2. Pinned interpreter at a fixed path (as image/Dockerfile §2; 001 R6) ---------------------------
# The same path as the agent image, because the tools' shebang is #!/opt/timelike/python/bin/python3 -I.
COPY --from=uv /uv /bin/uv

ARG PYTHON_VERSION
RUN test -n "${PYTHON_VERSION:-}" \
      || { echo "error: PYTHON_VERSION build arg is empty (code 1) — pass it from pins.env" >&2; exit 1; } \
 && UV_NO_CACHE=1 UV_PYTHON_INSTALL_DIR=/opt/uv-python \
      uv python install "${PYTHON_VERSION}" --install-dir /opt/uv-python --no-bin --compile-bytecode \
 && pydir="/opt/uv-python/cpython-${PYTHON_VERSION}-linux-x86_64-gnu" \
 && if [ ! -x "${pydir}/bin/python3" ]; then \
      echo "error: expected interpreter at ${pydir}/bin/python3 is missing (code 1) — uv may not offer CPython ${PYTHON_VERSION} (001 research R6/R9 caveat), or this is not linux/x86_64. Found:" >&2; \
      ls -1 /opt/uv-python >&2 || true; \
      echo "remediation: pin a CPython version the pinned uv offers (uv python list) in pins.env and 001 research.md R9" >&2; \
      exit 1; fi \
 && mkdir -p /opt/timelike \
 && ln -s "${pydir}" /opt/timelike/python \
 && /opt/timelike/python/bin/python3 -I -c 'import sys' \
 && /opt/timelike/python/bin/python3 -I -c \
      'import platform, sys; v = platform.python_version(); sys.exit(0 if v == sys.argv[1] else "error: interpreter is " + v + ", pinned " + sys.argv[1])' \
      "${PYTHON_VERSION}"

# --- 3. The docker CLI (RB6; as tests/runner/Dockerfile) ----------------------------------------------
COPY --from=dockercli /usr/local/bin/docker /usr/local/bin/docker
RUN chown root:root /usr/local/bin/docker \
 && chmod 0755 /usr/local/bin/docker \
 && /usr/local/bin/docker --version

# --- 4. agentio and benchlib into the interpreter's own site-packages (RB6; image/Dockerfile §3) ------
# Plain file copies, not pip, so an EXTERNALLY-MANAGED marker cannot block them; its presence is only
# reported. They must be in site-packages because the -I shebang ignores PYTHONPATH (RB6), and -I does
# not imply -S (001 R6). benchlib is staged without --chmod (a 0644 directory would be untraversable)
# and given explicit modes after the copy, so the build context's umask cannot leak in.
COPY --chmod=0644 tools/agentio/agentio.py /tmp/timelike-build/agentio.py
COPY bench/benchlib/ /tmp/timelike-build/benchlib/
RUN site="$(/opt/timelike/python/bin/python3 -I -c 'import sysconfig; print(sysconfig.get_path("purelib"))')" \
 && { test -d "${site}" || { echo "error: interpreter purelib '${site}' is not a directory (code 1)" >&2; exit 1; }; } \
 && { test -f /tmp/timelike-build/benchlib/__init__.py \
      || { echo "error: bench/benchlib/__init__.py is missing from the build context (code 1) — build from the repository root" >&2; exit 1; }; } \
 && marker="$(find /opt/timelike/python/lib -maxdepth 2 -name EXTERNALLY-MANAGED -print -quit)" \
 && echo "EXTERNALLY-MANAGED marker: ${marker:-none} (does not affect a direct file copy)" \
 && install -o root -g root -m 0644 /tmp/timelike-build/agentio.py "${site}/agentio.py" \
 && rm -rf "${site}/benchlib" \
 && cp -R /tmp/timelike-build/benchlib "${site}/benchlib" \
 && find "${site}/benchlib" \( -name __pycache__ -o -name '*.pyc' \) -prune -exec rm -rf {} + \
 && chown -R root:root "${site}/benchlib" \
 && find "${site}/benchlib" -type d -exec chmod 0755 {} + \
 && find "${site}/benchlib" -type f -exec chmod 0644 {} + \
 && rm -rf /tmp/timelike-build \
 && /opt/timelike/python/bin/python3 -I -m compileall -q "${site}/agentio.py" "${site}/benchlib"

# --- 5. Tools on /opt/timelike-bench/bin (RB6) --------------------------------------------------------
# timelike-bench, plus a copy of timelike-conform so the bench's own tools can be checked against the
# output contract inside the image. Root-owned, not writable by the (non-root) runtime user.
COPY --chmod=0755 bench/bin/timelike-bench /opt/timelike-bench/bin/timelike-bench
COPY --chmod=0755 tools/bin/timelike-conform /opt/timelike-bench/bin/timelike-conform
RUN chown -R root:root /opt/timelike-bench \
 && chmod 0755 /opt/timelike-bench /opt/timelike-bench/bin

# --- 6. Runtime environment --------------------------------------------------------------------------
# No USER: bench/run.sh starts the driver with `-u $(id -u):$(id -g) --group-add <socket gid>` (RB7), so
# its files in bench/out are owned by the host user, and a baked USER would only be overridden. That uid
# usually has no passwd entry here, so HOME is set explicitly: /tmp is writable by any uid, and the
# docker CLI looks for its config under $HOME/.docker. Neither name is key-shaped (RB9 checks the image's
# Config.Env). PATH is spelled out, as in image/Dockerfile §7, rather than appended to an inherited value.
ENV PATH="/opt/timelike-bench/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" \
    TIMELIKE_BIN_DIRS="/opt/timelike-bench/bin" \
    HOME="/tmp"

# Build-time smoke: both modules import under the same -I the shebang uses, from outside the build dir.
RUN cd / && /opt/timelike/python/bin/python3 -I -c 'import agentio, benchlib'

# --- 7. Build stamp (RB8, H8). Last, so only this layer changes per commit. --------------------------
ARG GIT_SHA
RUN if [ -z "${GIT_SHA:-}" ]; then \
      echo "error: GIT_SHA build arg is empty (code 1) — refusing to build an unstamped image (H8); build through make, which passes it" >&2; exit 1; fi \
 && if ! [[ "${GIT_SHA}" =~ ^[0-9a-f]{7,64}$ ]]; then \
      echo "error: GIT_SHA build arg '${GIT_SHA}' is not a git revision (code 1) — pass git rev-parse HEAD (H8)" >&2; exit 1; fi \
 && printf '%s' "${GIT_SHA}" > /opt/timelike-bench/REVISION \
 && chown root:root /opt/timelike-bench/REVISION \
 && chmod 0444 /opt/timelike-bench/REVISION
LABEL org.opencontainers.image.revision=$GIT_SHA \
      org.opencontainers.image.title="timelike bench driver" \
      org.opencontainers.image.description="Runs timelike-bench against the agent and vanilla images; the only bench container holding the Docker socket (feature 002 RB6)"

ENTRYPOINT ["/opt/timelike-bench/bin/timelike-bench"]
