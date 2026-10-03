# Research — 001 agent shell baseline (slice 0)

Phase 0. Two research agents ran on 2026-09-28.

- **Shell and git behaviour** was verified by experiment on bash 5.2.21 and git 2.43.0, and against
  the actual Debian trixie `base-files` and `bash` packages.
- **Pins and privilege** were read from the registry APIs, upstream source and man pages on
  2026-09-28.

Each decision below cites what verified it. "Not verified here" marks a claim this environment could
not test, since it has no container runtime (see R10).

---

### R1 · How defaults reach every invocation style (FR-1, SC-2)

**Decision:** put every non-PATH default in Dockerfile `ENV`. Add `PATH` both in `ENV` and in
`/etc/profile.d/00-timelike-path.sh`. Keep a fallback copy of the git settings in `/etc/gitconfig`.
Do not rely on rc files, `BASH_ENV` or `PROMPT_COMMAND`.

**Rationale (verified by experiment):**

| Style | Reads | `BASH_ENV` |
|---|---|---|
| `bash -c` | nothing, except `$BASH_ENV` | yes |
| `bash -lc` | `/etc/profile`, then `~/.bash_profile`, `~/.bash_login` or `~/.profile`, then `$BASH_ENV` | yes, read after the profile files |
| interactive, not login | `/etc/bash.bashrc`, then `~/.bashrc` | no |
| interactive login | `/etc/profile`, then the first of the home files above | no |

- Debian trixie's `/etc/profile` (base-files 13.8) **resets PATH unconditionally**. For a non-root
  uid it becomes `/usr/local/bin:/usr/bin:/bin:/usr/local/games:/usr/games`, so a PATH set only in
  `ENV` is lost under `bash -lc`.
- `/etc/profile` sources `/etc/profile.d/*.sh` in every login shell. It sources `/etc/bash.bashrc`
  only when `PS1` is set.
- Environment variables other than PATH survive `/etc/profile`. `docker exec` inherits the
  container's environment (Docker docs; not verified here).

**Which test catches which mistake:**
- PATH only in `ENV` → `bash -lc 'command -v timelike'` fails.
- PATH only in profile.d → `bash -c` and `sh -c` fail.
- A variable only in `BASH_ENV` → the interactive run or `sh -c` fails.

**Alternatives rejected:**
- `BASH_ENV` alone: interactive shells and `sh` ignore it.
- rc files or `PROMPT_COMMAND`: non-interactive shells skip them (G13).

### R2 · Git never pages, never opens an editor, never prompts (FR-2, FR-3, SC-1, SC-3)

**Decision:** `ENV` carries:
- `GIT_EDITOR=true`, `GIT_SEQUENCE_EDITOR=true`, `GIT_MERGE_AUTOEDIT=no`
- `GIT_PAGER=cat`, `PAGER=cat`
- `GIT_TERMINAL_PROMPT=0`, `GIT_ASKPASS=` (empty), `SSH_ASKPASS=` (empty), `GCM_INTERACTIVE=never`
- ~~`GIT_SSH_COMMAND="ssh -o BatchMode=yes -o ConnectTimeout=15"`~~ removed in cycle 2 (T044), together
  with `openssh-client` (stack note 15). With no ssh client, git over ssh ends at once with
  "cannot run ssh"

`/etc/gitconfig` repeats these as fallbacks (`core.editor=true`, `core.pager=cat`,
`sequence.editor=true`), in case the agent unsets a variable.

**Rationale (verified by experiment, all with stdin at `/dev/null`):**

| Editor setting | `git commit` with no `-m` | `rebase --continue` after a resolved conflict |
|---|---|---|
| `true` | rc 1, "Aborting commit due to empty commit message" | **rc 0**, keeps the existing message |
| `false` | rc 1 | rc 1, rebase left stopped |
| unset, `TERM=xterm` | **hangs in vi** (Debian's `editor` fallback) | same hang risk |

- `GIT_EDITOR` beats `core.editor`, which beats `VISUAL` and then `EDITOR`. `GIT_PAGER` beats
  `pager.<cmd>` and `core.pager`, which beat `PAGER`. Git treats `cat` as "no pager".
- **`GIT_TERMINAL_PROMPT=0` alone still calls askpass** if one is configured. An empty `GIT_ASKPASS`
  stops that (`prompt.c`).
- https with no credentials exits 128 in 0.3 s. ssh with `BatchMode=yes` exits 128 in 0.3 s.

**Known gaps, accepted:** `commit --amend` and `merge` succeed silently with the existing message.
That is correct non-interactive behaviour, not a hang.

### R3 · Repository hooks off unless explicitly enabled (FR-4, SC-3)

> **Superseded at discovery revision 7** (send `bridge/sends/01-rev7-20260929-094055.md`, cycle 5). Hooks
> now run, bounded: see **R11**. This entry is kept, because its precedence findings are what R11
> relies on: `GIT_CONFIG_*` (command scope) beats a repository's local `core.hooksPath`, and a system
> setting loses to it.

**Decision:** in `ENV`:
`GIT_CONFIG_COUNT=1`, `GIT_CONFIG_KEY_0=core.hooksPath`, `GIT_CONFIG_VALUE_0=/dev/null`.

Explicit enablement stays possible per command: `git -c core.hooksPath=.git/hooks …`.

**Rationale (verified by experiment):**
- A system `core.hooksPath=/dev/null` is **overridden by a repository's local `core.hooksPath`**, the
  kind of setting husky writes. So the system config alone does not satisfy "do not run unless
  explicitly enabled".
- `GIT_CONFIG_*` has "command" scope: it beats local config, and it loses to `git -c`. That makes
  `-c` the explicit enablement.

**Caveat:** an agent that sets its own `GIT_CONFIG_COUNT` replaces this. That is also explicit.

### R4 · Colour off (FR-1, SC-2)

**Decision:** `ENV NO_COLOR=1`, plus `color.ui=never` in `/etc/gitconfig`. `TERM` is not forced.

**Rationale (verified by experiment):** `NO_COLOR` **has no effect on git 2.43**. `color.ui=never`
does. `TERM=dumb` also works, but it changes other programs' behaviour and `color.ui=always`
overrides it. `NO_COLOR` covers the many other tools that honour it.

The SC-2 test asserts `git config --get color.ui` = `never` and that `NO_COLOR` is set, in each
invocation style.

### R5 · Other interactive traps defaulted off

**Decision:** `ENV` also sets:
- `DEBIAN_FRONTEND=noninteractive`
- `PIP_NO_INPUT=1`, `PIP_DISABLE_PIP_VERSION_CHECK=1`
- `MANPAGER=cat`, `SYSTEMD_PAGER=cat`
- `GH_PAGER=cat`, `GH_PROMPT_DISABLED=1`, `AWS_PAGER=`
- `npm_config_yes=true`, `NO_UPDATE_NOTIFIER=1`

These are documented variables, not verified here. A bare REPL waits on stdin whatever the variables
say, so harness stdin must be `/dev/null`. That is the harness's side, and REPL modes are slice 1.

### R6 · Interpreter at a fixed path (FR-8; tech-stack)

**Decision:**
1. `COPY --from=ghcr.io/astral-sh/uv:0.12.19@sha256:04d046b1… /uv /bin/uv`
2. `uv python install 3.14.7 --install-dir /opt/uv-python --no-bin --compile-bytecode`
3. `ln -s /opt/uv-python/cpython-3.14.7-linux-x86_64-gnu /opt/timelike/python`
4. `agentio.py` goes into that interpreter's `site-packages`

**Rationale:**
- uv names the directory itself. A symlink keeps the `_sysconfigdata` paths valid, where moving the
  directory would leave them stale (python-build-standalone quirks).
- `-I` implies `-E`, `-P` and `-s` (Python 3.12 docs). `PYTHONPATH`, user site and the script
  directory are dropped, but the interpreter's own site-packages stays importable, because `-I` does
  not imply `-S`.
- Check for an `EXTERNALLY-MANAGED` marker at build time.

**Alternative rejected:** a venv for tools. The constitution (H5) forbids an agent venv, and a
symlinked interpreter is simpler.

### R7 · Privilege boundary (FR-5, FR-6, SC-4)

**Decision:**
- **Image:**
  - no `sudo`
  - strip every setuid and setgid bit (`find / -xdev -perm /6000 -type f -exec chmod a-s {} +`),
    then assert the same find returns nothing
  - agent user uid 1000, in no privileged group
  - `adele` system user uid 10001, owning `/var/lib/adele` (0700)
- **Compose:** `cap_drop: [ALL]`, `security_opt: [no-new-privileges:true]`, the default seccomp
  profile.

**Rationale:**
- trixie-slim ships 8 setuid-root binaries (`chfn chsh gpasswd mount newgrp passwd su umount`) and 3
  setgid-shadow ones (`chage expiry unix_chkpwd`). This was listed from the actual amd64 layer.
- `no_new_privs` makes `execve` ignore setuid bits. An empty bounding set means capabilities can't be
  regained.
- Docker's default seccomp profile blocks `unshare`, and `clone` with `CLONE_NEWUSER`, without
  `CAP_SYS_ADMIN` (moby `profiles/seccomp/default.json`).

**Verification reads the controls directly** (lore cross-stack P001), from `/proc/self/status`:
- `CapEff`, `CapPrm`, `CapBnd` and `CapAmb` are all 0
- `NoNewPrivs` is 1
- `Seccomp` is 2
- bit 12 (`CAP_NET_ADMIN`) is 0 in `CapBnd`

**Firewall probe:** trixie-slim has no `nft` or `iptables`. A direct probe opens
`AF_NETLINK/NETLINK_NETFILTER` and sends one nfnetlink message, which must get `EPERM`. The kernel
requires `CAP_NET_ADMIN` even to read.

**Also asserted:**
- `su` fails
- `unshare -r true` fails
- `find / -xdev -perm /6000` is empty
- `cat /var/lib/adele/fixture.secret` fails with EACCES

### R8 · Tests run from outside the image (lore cross-stack P005; SC-1, SC-2)

**Decision:**
- **Runner image:** `FROM bats/bats:1.14.0@sha256:5322b877…`, plus the docker CLI copied from
  `docker:29.8.1-cli@sha256:018edbc9…`.
- The runner mounts the host socket (test harness only, never the agent image) and drives the system
  under test with `docker exec` (no `-t`), `docker exec -t`, and `docker compose exec -T`.
- Every criterion is tested in **both** TTY modes: a TTY is what exposes the pager, editor and prompt
  traps. Under `-t`, a `timeout` wrapper turns a hang into rc 124, which fails.

**Rationale:**
- A bats run inside the image proves only that image agrees with itself.
- The bats image has no docker CLI (its Dockerfile is `FROM bash`).
- Plain `docker exec` has no `-T` flag; leaving out `-t` means pipes and no controlling terminal
  (`/dev/tty` gives ENXIO).

**Unit tests:** pytest for `agentio` and `timelike-conform`, inside the image's interpreter.

### R9 · Pins (tech-stack: pin everything)

All read 2026-09-28.

| Component | Version | Reference |
|---|---|---|
| debian | trixie-slim (13.7) | `debian@sha256:a99cfc517144bc59b1978475ec53b46ecabec7e43635402ee5b77cc54cd1b20a` (index) |
| uv | 0.12.19 | `ghcr.io/astral-sh/uv:0.12.19@sha256:04d046b13e60d6bcec73cbc5e1cad25d680dea90c8573340950a0ac2d1aef424` |
| CPython | 3.14.7 | python-build-standalone 20260924, via uv; key `cpython-3.14.7-linux-x86_64-gnu` in uv 0.12.19's download metadata, and the newest stable release on python.org (read 2026-09-28). **Was 3.12.14** until discovery revision 5: CVE-2026-82049 is fixed only from 3.14, and a stable fix on another minor line counts as available (T043) |
| bats-core | 1.14.0 | `bats/bats:1.14.0@sha256:5322b877351fda0cc435de8c6116de7d0a2ec79d7c680132a0ef329a633bc66f` |
| docker CLI | 29.8.1 | `docker:29.8.1-cli@sha256:018edbc908e08fcc9dbf029c812c34251e9b4719e6f71ca0e5eae2a987d014ca` |
| shellcheck | 0.11.0 | `koalaman/shellcheck:v0.11.0@sha256:61862eba1fcf09a484ebcc6feea46f1782532571a34ed51fedf90dd25f925a8d`. **Not `latest`**, which is a development build |
| Syft | 1.52.0 | `anchore/syft:v1.52.0@sha256:500e2d872ac019436926e8322b4fc1f39441d94d21f6f4046c6ff29b30e8cb02` |
| Grype | 0.119.0 | `anchore/grype:v0.119.0@sha256:8c2c9234a345577a6d321a4753aa3ee1276d8975c8452d2344a56b57733ecad3` |
| gitleaks | 8.30.1 | `ghcr.io/gitleaks/gitleaks:v8.30.1@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f` |
| pip-audit | 2.10.1 | PyPI. There is no official image, so it runs through `uvx pip-audit==2.10.1` in a scan container |
| ruff / mypy | 0.16.9 / 2.3.1 | PyPI, in a dev/check image, never the agent image |

### R10 · This development environment has no container runtime

**Finding (probed 2026-09-28):**
- This session itself runs in a Docker container: `/.dockerenv` exists and the root is an `overlay2`
  layer.
- There is no socket, and `DOCKER_HOST` is unset.
- The capabilities are the Docker default set, without `CAP_SYS_ADMIN`, with seccomp active.
- `unshare -r` is blocked.
- Passwordless `sudo` works, but root still lacks `CAP_SYS_ADMIN`. So no daemon, no rootless
  podman or buildah, and no nested build can run here.

**Consequence:** the image can't be built and the authoritative (Docker-lane) tests can't run here.
This is the send's one external prerequisite, unmet. It is also P1's own violation example
("cannot start one from inside its container"), met while building timelike.

**Decision:** tests run in two lanes, never conflated.
1. **Docker lane** (`tests/run.sh`): authoritative for SC-1 to SC-6. It needs a daemon: the host's
   socket mounted into this dev container, a remote `DOCKER_HOST`, or CI.
2. **Host lane** (`tests/host/`), advisory:
   - pytest for `agentio` and `timelike-conform` on the host's Python 3.12
   - an environment-layer check that runs the **same** `ENV` list and `/etc/gitconfig` through
     `env -i` with `GIT_CONFIG_SYSTEM`, in `bash -c`, `bash -lc` and interactive styles

   It produces evidence about the files, not the image. The cycle report labels it so.


### R11 · Repository hooks run, bounded (FR-4 as amended, FR-19, FR-20; SC-3, SC-12, SC-13; T4)

*Cycle 5, discovery revision 7. Verified on the host with git 2.43.0, dash and GNU coreutils; the image
has git 2.47.3. Every experiment ran in its own session under a watchdog (see "What went wrong" below).*

**Decision: a timelike-owned hooks directory of dispatchers.**
- `GIT_CONFIG_VALUE_0` points `core.hooksPath` at `/opt/timelike/git-hooks`, in command scope as
  before (R3). That directory holds one script, `dispatch`, and a link to it for each hook name git
  runs from a hooks directory.
- **Which hook runs:** the one git would have run without timelike. That is the last `core.hooksPath`
  from any scope **except** `command` (`git config --show-scope --get-all core.hooksPath`: local,
  worktree, global, system). If there is none, it is git's default directory,
  `<git-common-dir>/hooks`.
  - [V] Husky's local `core.hooksPath` is listed beside the command-scope value, and runs.
  - [V] `.git/hooks` runs when nothing sets a path.
  - [V] Linked worktrees resolve to the common directory.
- **Arguments, stdin and environment pass through unchanged.** git gives a hook its input on stdin
  (pre-push's ref lines) [V]. The ruling's example said "stdin from /dev/null". Forwarding git's stdin
  is the faithful choice, because that stdin is never a terminal: it is git's pipe, or the stdin git
  was given.

**Decision: the limit is 60 s by default.**
- It is below Claude Code's 120 s default call timeout, with room for git's own work, so the hook's
  verdict arrives before the harness kills the call.
- **How to raise it:** set `TIMELIKE_HOOK_TIMEOUT=<seconds>` in the environment (this shell), or run
  `git config timelike.hookTimeout <seconds>` (this repository). The environment variable wins over
  the repository setting, and that wins over the default.
- A value that is not a positive integer is reported and the default used [V].

**The verdict** is one line on stderr, in the output contract's error shape:

    error: git hook pre-commit (.husky/pre-commit) did not finish within 60 s and was stopped (code 124) — the limit is 60 s (the default); raise it for this shell with TIMELIKE_HOOK_TIMEOUT=<seconds>, or for this repository with: git config timelike.hookTimeout <seconds>

- It names the hook, the limit, where the limit came from, and how to raise it.
- It never mentions `--no-verify`, `-n`, `core.hooksPath` or any other way to skip the hook (T4).
- The dispatcher exits 124, and git then fails the command. For a commit, git exits 1 [V].

**How a hook is stopped.**
- GNU `timeout -s TERM -k 5` leads its own process group and signals all of it on expiry. [V] A
  hook's background child dies with it.
- `timeout` runs in the background only so that its pid, the group id, is known for a `KILL` backstop.
- After a normal exit, a hook's own children are left alone.

**Hook names linked:** applypatch-msg, pre-applypatch, post-applypatch, pre-commit, pre-merge-commit,
prepare-commit-msg, commit-msg, post-commit, pre-rebase, post-checkout, post-merge, pre-push,
pre-receive, update, post-receive, post-update, reference-transaction, pre-auto-gc, post-rewrite,
sendemail-validate, post-index-change, p4-changelist, p4-prepare-changelist, p4-post-changelist,
p4-pre-submit.

**Not linked, on purpose — FLAGGED:**
- **`push-to-checkout` and `proc-receive`:** git changes its behaviour when these merely **exist**. A
  dispatcher that finds no repository hook cannot emulate their absence. Both matter only when this
  environment **receives** a push.
- **`fsmonitor-watchman`:** git does not reach it through `core.hooksPath`.

A repository's own hooks of those three names do not run here. That is named, not silent.

**Precedence relied on:** `GIT_CONFIG_*` (command) > worktree > local > global > system (R3's
finding). `/etc/gitconfig` now points at the same directory, as a fallback for an agent that unsets
the environment variables. In that case a local `core.hooksPath` wins, and that repository's hooks run
**unbounded**, exactly as without timelike. The dispatcher ignores a resolved directory that is its
own, so the fallback cannot make it call itself.

**Measured cost** [V, host, noisy]: about 5.5 ms per dispatch when no hook exists, about eight
dispatches per commit, so about 30–40 ms per commit. That is one `git config` per hook name, plus
`git rev-parse` outside the fast path, which is an ordinary repository with `.git` in the working
directory. Not optimised further: turns and failures, not milliseconds, are what the project measures
(P6).

**What went wrong on the way** (recorded, because each one is a way this design can fail):
1. **Recursion.** The first fallback was `git rev-parse --git-path hooks`. That honours
   `core.hooksPath`, so it returned the dispatcher directory and the dispatcher called itself. Each
   nested `timeout` leads its own group, so the outer limit could not stop the chain: about 1,000
   processes were reaped by hand. The fix is `<git-common-dir>/hooks` and a self-directory check.
   A unit asserts it.
2. **Draining stdin blocked.** A no-hook path that ran `cat >/dev/null` hung on post-index-change,
   which inherits the caller's stdin. Nothing reads stdin now.
3. **`<&0` is not a redirection in dash.** Pre-push saw 0 lines instead of 1. stdin now travels on
   fd 3.

**Bind-mounted workspaces (flagged by plan, not ruled):** the dispatcher runs whatever hook the
repository holds, **inside** the container. A hook the agent writes into a bind-mounted `.git/hooks`
also runs on the **host**, the next time the operator commits there. This cycle neither widens nor
closes that boundary. It is recorded in `not_verified`.

### R12 · Hooks under `env -i` (T4's limit, discovery revision 8; cycle 6)

*Cycle 6, send `bridge/sends/01-rev9-20261001-191224.md`. Measured on the host with git 2.43.0 under a
watchdog; the image has git 2.47.3, and the Docker lane decides.*

**Question:** an agent or tool that discards timelike's environment (`env -i`) loses `GIT_CONFIG_*`,
the command-scope layer that points `core.hooksPath` at the dispatchers (R3, R11). What does git do
then?

**Finding [V on the host]:**
- **A repository using `.git/hooks`** is still bounded. With no command scope, `/etc/gitconfig`'s
  `core.hooksPath = /opt/timelike/git-hooks` (system scope) is the only path, so git runs the
  dispatcher. The dispatcher needs no environment: `git` and `timeout` resolve through the shell's
  default path, and the limit comes from the repository (`timelike.hookTimeout`), or else 60 s.
  - Measured: a hanging `pre-commit`, limit 2: git exit 1 at 2.0 s, with the verdict line; the hook
    stopped.
- **A repository with a local `core.hooksPath`** (husky, for example) is unbounded. Local scope beats
  system scope, so git runs the repository's hook directly, as without timelike.
  - Measured: the same hook ran with no verdict until the experiment's 8 s watchdog stopped it.

**Decision:** document it (README), and pin it with a test (`tests/e2e/hooks-under-env-i-…bats`), as
the revision-8 ruling asks. Do not "fix" it: nothing in the environment survives `env -i` except files,
and making the local case bounded would mean the system layer overriding a repository's own
`core.hooksPath`. git has no such precedence. P2 then rests on `run` (003) and the harness's own
timeout.

**How the test stays safe:** the unbounded case is ended by the test's own `timeout` (GNU timeout
signals the process group, which includes the hook). Teardown kills by the pid the hook wrote for
itself. No `pgrep -f` (cycle 5 process failure 2).
