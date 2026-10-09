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

# The agent's runtimes (feature 007 slice 1, discovery revision 14; 007 spec FR-25, D-14, D-15): an agent
# Python (uv-managed CPython at PYTHON_VERSION) and Node (the official tarball, NODE_VERSION, checked against
# NODE_SHA256), both under /opt/agent. Node's bundled npm is replaced whole by the registry's package at
# NPM_VERSION, checked against NPM_SHA512 (lane 007s1-a: fixes in npm's bundled dependencies). Built in a
# stage of their own so bench/vanilla/Dockerfile can run the identical steps: the two bench arms carry the
# same binaries (RB1). Configuration is the final stage's job. The slim base has no curl and no xz, so the
# tarballs come by ADD, and Node's is the .tar.gz.
FROM ${DEBIAN_IMAGE} AS runtimes
SHELL ["/bin/bash", "-o", "errexit", "-o", "nounset", "-o", "pipefail", "-c"]
COPY --from=uv /uv /bin/uv
ARG PYTHON_VERSION
ARG NODE_VERSION
ARG NODE_SHA256
ARG NPM_VERSION
ARG NPM_SHA512
ADD https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-x64.tar.gz /tmp/node.tar.gz
ADD https://registry.npmjs.org/npm/-/npm-${NPM_VERSION}.tgz /tmp/npm.tgz
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
 && [[ "${NPM_VERSION:-}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ && "${NPM_SHA512:-}" =~ ^[0-9a-f]{128}$ ]] \
      || { echo "error: NPM_VERSION or NPM_SHA512 build arg is missing or malformed — pass them from pins.env" >&2; exit 1; } \
 && printf '%s  %s\n' "${NPM_SHA512}" /tmp/npm.tgz | sha512sum -c - \
      || { echo "error: npm-${NPM_VERSION}.tgz does not match NPM_SHA512 (pins.env) — refusing it" >&2; exit 1; } \
 && rm -rf /opt/agent/node/lib/node_modules/npm \
 && mkdir /opt/agent/node/lib/node_modules/npm \
 && tar -xzf /tmp/npm.tgz -C /opt/agent/node/lib/node_modules/npm --strip-components=1 --no-same-owner \
 && rm -f /tmp/npm.tgz \
 && test "$(/opt/agent/node/bin/node /opt/agent/node/bin/npm --version)" = "${NPM_VERSION}" \
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

# --- 3a. edit's syntax checker (feature 008 slice 1; research R9) ------------------------------------
# tree-sitter's Python binding and three prebuilt grammar wheels (TypeScript/TSX, Go, Rust) go into
# timelike's interpreter's own site-packages, beside agentio. They are never put in the agent's runtime and
# never in the vanilla image (RB1). Each wheel is pinned by version and by the SHA-256 PyPI publishes
# (pins.env): --require-hashes refuses any other file, --no-deps admits nothing unpinned, and
# --only-binary means no compiler is needed, which the image has none of. Python and shell need nothing
# here: the checker uses this interpreter's compiler and /bin/bash -n. The checker itself lives in
# /opt/timelike/libexec, off PATH; edit runs it from its own location (lore P002).
ARG TREE_SITTER_VERSION
ARG TREE_SITTER_SHA256
ARG TREE_SITTER_TYPESCRIPT_VERSION
ARG TREE_SITTER_TYPESCRIPT_SHA256
ARG TREE_SITTER_GO_VERSION
ARG TREE_SITTER_GO_SHA256
ARG TREE_SITTER_RUST_VERSION
ARG TREE_SITTER_RUST_SHA256
COPY --chmod=0755 tools/libexec/ /opt/timelike/libexec/
RUN for pin in "tree-sitter:${TREE_SITTER_VERSION:-}:${TREE_SITTER_SHA256:-}" \
               "tree-sitter-typescript:${TREE_SITTER_TYPESCRIPT_VERSION:-}:${TREE_SITTER_TYPESCRIPT_SHA256:-}" \
               "tree-sitter-go:${TREE_SITTER_GO_VERSION:-}:${TREE_SITTER_GO_SHA256:-}" \
               "tree-sitter-rust:${TREE_SITTER_RUST_VERSION:-}:${TREE_SITTER_RUST_SHA256:-}"; do \
      IFS=: read -r name version sha <<<"${pin}"; \
      [[ "${version}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ && "${sha}" =~ ^[0-9a-f]{64}$ ]] \
        || { echo "error: ${name}'s version or SHA-256 build arg is missing or malformed — pass them from pins.env" >&2; exit 1; }; \
      printf '%s==%s --hash=sha256:%s\n' "${name}" "${version}" "${sha}"; \
    done >/tmp/syntax-check.requirements \
 && site="$(/opt/timelike/python/bin/python3 -I -c 'import sysconfig; print(sysconfig.get_path("purelib"))')" \
 && UV_NO_CACHE=1 uv pip install --python /opt/timelike/python/bin/python3 --target "${site}" \
      --require-hashes --no-deps --only-binary :all: -r /tmp/syntax-check.requirements \
      || { echo "error: the syntax checker's wheels did not install as pinned (pins.env TREE_SITTER_*)" >&2; exit 1; } \
 && rm -f /tmp/syntax-check.requirements \
 && chown -R root:root "${site}" /opt/timelike/libexec \
 && cd / && /opt/timelike/python/bin/python3 -I -c \
      'import importlib.metadata as md, sys, tree_sitter as ts, tree_sitter_typescript as t, tree_sitter_go as g, tree_sitter_rust as r
want = dict(zip(["tree-sitter", "tree-sitter-typescript", "tree-sitter-go", "tree-sitter-rust"], sys.argv[1:]))
for name, version in want.items():
    if md.version(name) != version:
        sys.exit(f"error: {name} is {md.version(name)}, pinned {version}")
for lang in (t.language_typescript, t.language_tsx, g.language, r.language):
    if ts.Parser(ts.Language(lang())).parse(b"x").root_node is None:
        sys.exit("error: a grammar parsed nothing")' \
      "${TREE_SITTER_VERSION}" "${TREE_SITTER_TYPESCRIPT_VERSION}" "${TREE_SITTER_GO_VERSION}" "${TREE_SITTER_RUST_VERSION}" \
 && test -x /opt/timelike/libexec/syntax-check \
 && for probe in 'python:def f(x)' $'go:package p\nfunc f() {' 'shell:if true; then'; do \
      lang="${probe%%:*}"; src="${probe#*:}"; \
      out="$(printf '%s\n' "${src}" | /opt/timelike/python/bin/python3 -I /opt/timelike/libexec/syntax-check "${lang}" "$(( ${#src} + 1 ))")"; \
      [[ "${out}" == *'"result": [{'* ]] \
        || { echo "error: the syntax checker did not find the error in a broken ${lang} line: ${out}" >&2; exit 1; }; \
    done

# --- 3b. The agent's runtimes, configured for user locations (007 spec FR-25 to FR-28; discovery revision 14)
# For the agent, never for timelike's tools (stack note 3: they run /opt/timelike/python with -I, which never
# reads the user site). Root owns both prefixes. The configuration is scoped to each runtime (ruling Q3):
#   - the agent interpreter loses its EXTERNALLY-MANAGED marker: no external manager owns it (timelike put it
#     there for the agent to install into)
#   - its own pip.conf (pip's site configuration for that prefix) makes a bare `pip install` a user install
#   - Node's own npmrc (the global config npm finds from node's real path) puts `npm install -g` under
#     ~/.local; npm expands ${HOME} itself
#   - seven links on PATH, to the runtimes' own executables: no wrapper (feature 15 sits in front later).
#     corepack, idle3, pydoc3 and python3-config are not linked (D-12)
# Never PIP_BREAK_SYSTEM_PACKAGES. ~/.local/bin is on PATH through § 7 and profile.d (FR-28).
COPY --from=runtimes /opt/agent /opt/agent
RUN marker="$(find /opt/agent/python/lib -maxdepth 2 -name EXTERNALLY-MANAGED -print -quit)" \
 && { test -n "${marker}" || { echo "error: the agent interpreter carries no EXTERNALLY-MANAGED marker to remove — has uv changed?" >&2; exit 1; }; } \
 && rm -f "${marker}" \
 && printf '[install]\nuser = true\n' >/opt/agent/python/pip.conf \
 && mkdir -p /opt/agent/node/etc \
 && printf 'prefix=${HOME}/.local\n' >/opt/agent/node/etc/npmrc \
 && chmod 0644 /opt/agent/python/pip.conf /opt/agent/node/etc/npmrc \
 && for n in python3 python pip pip3; do ln -s "/opt/agent/python/bin/${n}" "/usr/local/bin/${n}"; done \
 && for n in node npm npx; do ln -s "/opt/agent/node/bin/${n}" "/usr/local/bin/${n}"; done \
 && test -z "$(find /opt/agent/python/lib -maxdepth 2 -name EXTERNALLY-MANAGED -print -quit)" \
 && /usr/local/bin/pip --version >/dev/null && /usr/local/bin/npm --version >/dev/null \
 && test "$(/usr/local/bin/python3 -I -c 'import sys; print(sys.prefix)')" != "$(readlink -f /opt/timelike/python)"

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
# What a command that is not installed answers in bash (feature 007 slice 1, spec FR-16): read by the
# hook's command_not_found_handle, with builtins only.
COPY --chmod=0644 image/rootfs/etc/timelike/missing-commands.tsv /etc/timelike/missing-commands.tsv
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
# /etc/profile.d/00-timelike-path.sh, because Debian's /etc/profile resets it (R1). /home/agent/.local/bin
# (007 FR-28, discovery revision 14) is where bare pip and npm -g installs put commands: after timelike's
# tools, so an install never shadows one, and before /usr/local/bin.
# Slice 1: BASH_ENV points non-interactive bash at the container-derived hook (§ 5; F004). TZ and
# PYTHON_BASIC_REPL are static, so they live here and reach sh -c and direct execs as well (F003,
# SC-10): TZ="UTC" needs no zoneinfo file (glibc reads it as a POSIX TZ string, offset 0), and
# PYTHON_BASIC_REPL keeps Python >= 3.13 out of PyREPL (colour, line editing, escape sequences).
# From here on the build's own RUN shells (bash) read BASH_ENV too; the hook only adds job counts and
# strips secret-shaped names, and § 8's GIT_SHA is not one.
ENV PATH="/opt/timelike/bin:/home/agent/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" \
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
