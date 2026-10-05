# timelike agent image — slice 0 (feature 001). Build context: the repository root (compose.yaml).
#
# Every pin arrives as a build argument from pins.env (via the Makefile and compose.yaml); this file
# repeats none of them, so pins.env stays the single source (T002). Research items cited below live in
# .specswarm/features/001-agent-shell-baseline/research.md.
#
# Order is chosen for layer caching: packages, interpreter, users and hardening first; the static ENV
# block next; the per-commit GIT_SHA stamp last, so a new commit rebuilds only the final layers.

ARG DEBIAN_IMAGE
ARG UV_IMAGE

# uv ships as a distroless image holding /uv and /uvx (R6).
FROM ${UV_IMAGE} AS uv

FROM ${DEBIAN_IMAGE}

# Build-time shell only; it does not affect the running container's shells.
SHELL ["/bin/bash", "-o", "errexit", "-o", "nounset", "-o", "pipefail", "-c"]

# --- 1. OS packages (T009 step 2; R7: no sudo, nft or iptables) --------------------------------------
# util-linux provides setsid and setpriv (conformance probes); procps provides pgrep (SC-1 tests).
# No openssh-client (stack note 15, discovery revision 5): under P4 the agent holds no SSH keys, and
# credentialed git goes over https through Adele. git and its libcurl stay: https fetch is P1.
# Targeted upgrade (operator, 2026-10-01; FOR-MENTOR Item 12): Debian fixed CVE-2026-103111 in
# libpcre2-8-0 10.46-1~deb13u3, and no published trixie-slim carries it yet (the pinned digest is the
# newest build). OpenSSL arrives fixed already, through ca-certificates. This line comes out when a
# trixie-slim newer than a99cfc517144 ships libpcre2-8-0 10.46-1~deb13u3 or later (watch item).
RUN DEBIAN_FRONTEND=noninteractive apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      git ca-certificates util-linux procps \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends --only-upgrade libpcre2-8-0 \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/* \
 && if command -v sudo || command -v nft || command -v iptables; then \
      echo "error: sudo, nft or iptables is present in the image (R7 forbids them)" >&2; exit 1; fi \
 && if command -v ssh; then \
      echo "error: an ssh client is present in the image (stack note 15 removes it)" >&2; exit 1; fi

# --- 2. Pinned interpreter at a fixed path (T009 step 3; R6) ------------------------------------------
COPY --from=uv /uv /bin/uv

ARG PYTHON_VERSION
RUN test -n "${PYTHON_VERSION:-}" \
      || { echo "error: PYTHON_VERSION build arg is empty — pass it from pins.env" >&2; exit 1; } \
 && UV_NO_CACHE=1 UV_PYTHON_INSTALL_DIR=/opt/uv-python \
      uv python install "${PYTHON_VERSION}" --install-dir /opt/uv-python --no-bin --compile-bytecode \
 && pydir="/opt/uv-python/cpython-${PYTHON_VERSION}-linux-x86_64-gnu" \
 && if [ ! -x "${pydir}/bin/python3" ]; then \
      echo "error: expected interpreter at ${pydir}/bin/python3 is missing — uv may not offer CPython ${PYTHON_VERSION} (research R6/R9 caveat), or this is not linux/x86_64. Found:" >&2; \
      ls -1 /opt/uv-python >&2 || true; \
      echo "remediation: pin a CPython version the pinned uv offers (uv python list) in pins.env and research.md R9" >&2; \
      exit 1; fi \
 && mkdir -p /opt/timelike \
 && ln -s "${pydir}" /opt/timelike/python \
 && /opt/timelike/python/bin/python3 -I -c 'import sys' \
 && /opt/timelike/python/bin/python3 -I -c \
      'import platform, sys; v = platform.python_version(); sys.exit(0 if v == sys.argv[1] else "error: interpreter is " + v + ", pinned " + sys.argv[1])' \
      "${PYTHON_VERSION}"

# --- 3. agentio into the interpreter's own site-packages; tools onto /opt/timelike/bin (step 4) -------
# A plain file copy, not pip, so an EXTERNALLY-MANAGED marker cannot block it; its presence is only
# reported. -I keeps the interpreter's site-packages importable (-I does not imply -S; R6).
COPY --chmod=0644 tools/agentio/agentio.py /tmp/timelike-build/agentio.py
RUN site="$(/opt/timelike/python/bin/python3 -I -c 'import sysconfig; print(sysconfig.get_path("purelib"))')" \
 && { test -d "${site}" || { echo "error: interpreter purelib '${site}' is not a directory" >&2; exit 1; }; } \
 && marker="$(find /opt/timelike/python/lib -maxdepth 2 -name EXTERNALLY-MANAGED -print -quit)" \
 && echo "EXTERNALLY-MANAGED marker: ${marker:-none} (does not affect a direct file copy)" \
 && install -o root -g root -m 0644 /tmp/timelike-build/agentio.py "${site}/agentio.py" \
 && rm -rf /tmp/timelike-build \
 && /opt/timelike/python/bin/python3 -I -m compileall -q "${site}/agentio.py" \
 && cd / && /opt/timelike/python/bin/python3 -I -c 'import agentio'

COPY --chmod=0755 tools/bin/ /opt/timelike/bin/
RUN chown -R root:root /opt/timelike/bin

# Git-hook dispatchers (cycle 5, discovery revision 7; research R11). GIT_CONFIG_* below points
# core.hooksPath here: each hook name is a link to `dispatch`, which runs the repository's own hook
# under a time limit. Copied without --chmod, because COPY keeps a directory's links as links and
# --chmod would apply to them too; modes and ownership are set and checked here instead.
COPY image/rootfs/opt/timelike/git-hooks/ /opt/timelike/git-hooks/
RUN chown -hR root:root /opt/timelike/git-hooks \
 && chmod 0755 /opt/timelike/git-hooks /opt/timelike/git-hooks/dispatch \
 && test "$(readlink /opt/timelike/git-hooks/pre-commit)" = dispatch \
 && test -x /opt/timelike/git-hooks/pre-commit \
 && test "$(find /opt/timelike/git-hooks -type l | wc -l)" -eq 25 \
 && command -v timeout >/dev/null

# --- 4. Users (step 5; data-model.md) ----------------------------------------------------------------
# adele: reserved placeholder identity (feature 12 replaces the fixture), no login shell.
# agent: uid 1000, empty home (no /etc/skel dotfiles: no defaults may live in rc files, FR-1), no
# supplementary groups. Fail loudly if the base image already uses either id (lore docker-compose Q003).
RUN for id in 1000 10001; do \
      if getent passwd "${id}" >/dev/null || getent group "${id}" >/dev/null; then \
        echo "error: uid/gid ${id} already exists in the base image — refusing to create a colliding user" >&2; \
        getent passwd "${id}" >&2 || true; getent group "${id}" >&2 || true; exit 1; fi; \
    done \
 && groupadd --gid 10001 adele \
 && useradd --uid 10001 --gid adele --no-create-home --home-dir /var/lib/adele \
      --shell /usr/sbin/nologin --no-log-init adele \
 && install -d -o adele -g adele -m 0700 /var/lib/adele \
 && printf '%s\n' 'adele-fixture: the agent must not be able to read this' > /var/lib/adele/fixture.secret \
 && chown adele:adele /var/lib/adele/fixture.secret \
 && chmod 0600 /var/lib/adele/fixture.secret \
 && groupadd --gid 1000 agent \
 && useradd --uid 1000 --gid agent --no-create-home --home-dir /home/agent \
      --shell /bin/bash --no-log-init agent \
 && install -d -o agent -g agent -m 0750 /home/agent \
 && test "$(id -u agent):$(id -G agent)" = "1000:1000" \
 && test "$(stat -c '%a %U:%G' /var/lib/adele)" = "700 adele:adele" \
 && test "$(stat -c '%a %U:%G' /var/lib/adele/fixture.secret)" = "600 adele:adele"

# --- 5. Fallback config layer (step 9; R1, R2–R4) -----------------------------------------------------
# Copied file by file with an explicit mode, so the build context's umask cannot leak into /etc.
COPY --chmod=0644 image/rootfs/etc/gitconfig /etc/gitconfig
COPY --chmod=0644 image/rootfs/etc/profile.d/00-timelike-path.sh /etc/profile.d/00-timelike-path.sh
# Container-derived defaults (slice 1: SC-8 job counts from the CPU limit, SC-9 secret strip; modify.md
# F001, F002, F004). One bash hook, reached by bash -c through BASH_ENV (§ 7), by bash -lc through
# profile.d, and by interactive bash through the line appended to /etc/bash.bashrc. Debian's
# bash.bashrc returns early unless the shell is interactive, so the line goes at the end. The line is
# repeated verbatim in tests/host/test_env_layer.sh, which checks it is here.
COPY --chmod=0644 image/rootfs/etc/timelike/shell-env.bash /etc/timelike/shell-env.bash
COPY --chmod=0644 image/rootfs/etc/profile.d/10-timelike-shell-env.sh /etc/profile.d/10-timelike-shell-env.sh
# The redaction rule set (contract rule 15; feature 003 slice 1, spec FR-33): read by `run` through
# agentio, and by make scan's gitleaks step from the checkout, so the two cannot diverge.
COPY --chmod=0644 image/rootfs/etc/timelike/redaction.toml /etc/timelike/redaction.toml
# The announcement's inputs (feature 007): the curated standard tools for `timelike tools`, and the
# entrypoint that places the announcement in each harness's user-level context file on container start.
COPY --chmod=0644 image/rootfs/etc/timelike/standard-tools.json /etc/timelike/standard-tools.json
COPY --chmod=0755 image/rootfs/opt/timelike/libexec/entrypoint /opt/timelike/libexec/entrypoint
RUN test -f /etc/bash.bashrc \
      || { echo "error: /etc/bash.bashrc is missing — interactive bash would not reach the timelike hook" >&2; exit 1; } \
 && printf '\n# timelike: container-derived defaults for interactive bash (modify.md F004)\n%s\n' \
      'if [ -r /etc/timelike/shell-env.bash ]; then . /etc/timelike/shell-env.bash; fi' >> /etc/bash.bashrc \
 && chmod 0755 /etc/timelike \
 && bash -n /etc/timelike/shell-env.bash \
 && { env -i BASH_ENV=/etc/timelike/shell-env.bash GITHUB_TOKEN=x /bin/bash -c \
        'test -z "${GITHUB_TOKEN+set}" && test "${TIMELIKE_CPUS:-0}" -ge 1' </dev/null \
      || { echo "error: /etc/timelike/shell-env.bash did not strip GITHUB_TOKEN or set TIMELIKE_CPUS in a bash -c smoke run" >&2; exit 1; }; }

# --- 6. No setuid or setgid anywhere (step 6; R7). After every install. -------------------------------
RUN find / -xdev -perm /6000 -type f -exec chmod a-s {} + \
 && leftover="$(find / -xdev -perm /6000 -type f)" \
 && { test -z "${leftover}" || { echo "error: setuid/setgid files remain: ${leftover}" >&2; exit 1; }; }

# --- 7. Non-interactive defaults (step 8; R1–R5). ONE instruction, one KEY=VALUE per line. -----------
# tests/host/test_env_layer.sh parses this block: keep it a single ENV, no comments inside, and only
# double quotes (no $, backslash or single quote in values). PATH is also restored for login shells by
# /etc/profile.d/00-timelike-path.sh, because Debian's /etc/profile resets it (R1).
# Slice 1: BASH_ENV points non-interactive bash at the container-derived hook (§ 5; F004). TZ and
# PYTHON_BASIC_REPL are static, so they live here and reach sh -c and direct execs as well (F003,
# SC-10): TZ="UTC" needs no zoneinfo file (glibc reads it as a POSIX TZ string, offset 0), and
# PYTHON_BASIC_REPL keeps Python >= 3.13 out of PyREPL (colour, line editing, escape sequences).
# From here on the build's own RUN shells (bash) read BASH_ENV too; the hook only adds job counts and
# strips secret-shaped names, and § 8's GIT_SHA is not one.
ENV PATH="/opt/timelike/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" \
    TIMELIKE_BIN_DIRS="/opt/timelike/bin" \
    GIT_EDITOR="true" \
    GIT_SEQUENCE_EDITOR="true" \
    GIT_MERGE_AUTOEDIT="no" \
    GIT_PAGER="cat" \
    PAGER="cat" \
    MANPAGER="cat" \
    SYSTEMD_PAGER="cat" \
    GIT_TERMINAL_PROMPT="0" \
    GIT_ASKPASS="" \
    SSH_ASKPASS="" \
    GCM_INTERACTIVE="never" \
    GIT_CONFIG_COUNT="1" \
    GIT_CONFIG_KEY_0="core.hooksPath" \
    GIT_CONFIG_VALUE_0="/opt/timelike/git-hooks" \
    NO_COLOR="1" \
    DEBIAN_FRONTEND="noninteractive" \
    PIP_NO_INPUT="1" \
    PIP_DISABLE_PIP_VERSION_CHECK="1" \
    GH_PAGER="cat" \
    GH_PROMPT_DISABLED="1" \
    AWS_PAGER="" \
    npm_config_yes="true" \
    NO_UPDATE_NOTIFIER="1" \
    BASH_ENV="/etc/timelike/shell-env.bash" \
    TZ="UTC" \
    PYTHON_BASIC_REPL="1"

# --- 8. Build stamp (step 7; H8, lore cross-stack P003). Last, so only this layer changes per commit. -
ARG GIT_SHA
RUN if [ -z "${GIT_SHA:-}" ]; then \
      echo "GIT_SHA build arg is empty — refusing to build an unstamped image (H8)" >&2; exit 1; fi \
 && if ! [[ "${GIT_SHA}" =~ ^[0-9a-f]{7,64}$ ]]; then \
      echo "GIT_SHA build arg '${GIT_SHA}' is not a git revision — refusing to stamp it (H8)" >&2; exit 1; fi \
 && printf '%s' "${GIT_SHA}" > /opt/timelike/REVISION \
 && chown root:root /opt/timelike/REVISION \
 && chmod 0444 /opt/timelike/REVISION
LABEL org.opencontainers.image.revision=$GIT_SHA

# --- 8b. The announcement (feature 007, spec FR-1 to FR-3; lore cross-stack P003) ---------------------
# Generated from every installed tool's own --agent-info, after the stamp so it names this revision, and
# checked: an image whose announcement misses a tool is not built. The tools run here as root, so they
# get a scratch root of their own, removed after: a root-owned /tmp/timelike would lock the agent out of
# its scratch space.
RUN scratch="$(mktemp -d)" \
 && TIMELIKE_SCRATCH_ROOT="${scratch}" /opt/timelike/bin/timelike announce --write /etc/timelike/announcement.md \
 && TIMELIKE_SCRATCH_ROOT="${scratch}" /opt/timelike/bin/timelike announce --check \
 && rm -rf "${scratch}" \
 && chmod 0444 /etc/timelike/announcement.md \
 && test "$(wc -l < /etc/timelike/announcement.md)" -le 60 \
 && test ! -e /tmp/timelike

# --- 9. Run as the unprivileged agent (step 10) ------------------------------------------------------
# The session journal's shell record (feature 009): copied after the last RUN, so no build step is
# captured (the hook sets its trap only when this file is readable) and /tmp/timelike stays absent.
COPY --chmod=0644 image/rootfs/etc/timelike/journal-exit.bash /etc/timelike/journal-exit.bash

USER agent
WORKDIR /home/agent
# Places the announcement for each harness on every container start, then execs the command (feature
# 007, spec FR-5 to FR-8). `docker exec` does not run it; it runs once per container start.
ENTRYPOINT ["/opt/timelike/libexec/entrypoint"]
