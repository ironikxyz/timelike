# Research — 002 speedup bench (slice 0)

Two research subagents answered these questions in parallel on 2026-09-29, and the coordinator
consolidated their answers here. **This workspace has no Docker daemon** (001 research R10), so nothing
here was run in an image.

Each claim is tagged by its source:
- **[V]** verified locally, by experiment on the host (git 2.43.0, bash 5.2.21, no controlling
  terminal, `env -i`, a scratch HOME and `GIT_CONFIG_NOSYSTEM=1`), or by reading the repository
- **[C]** cited
- **[I]** inferred

The image's git is 2.47.3. Its editor, pager and prompt logic follows the same code path as the host's
[I].

---

### RB1 · What the vanilla image contains (spec Assumption 1)

**Decision.** The vanilla image is built from the pinned `DEBIAN_IMAGE` digest, with:
- the same `agent` user, uid 1000 and an empty home
- `USER agent`
- the git revision label
- the OS packages the catalog declares, which is `git` installed with `--no-install-recommends` and
  nothing else

It has none of timelike's ENV, `/etc/gitconfig`, shell-env hook, profile.d files, interpreter or tools.

**Evidence.**
- The trixie slim rootfs manifest has coreutils (`timeout`), util-linux, dash, perl-base and tzdata.
  It has **no** vim, nano, sensible-utils, less, procps, ca-certificates or openssh-client [C:
  docker-debian-artifacts `dist-amd64/trixie/slim/rootfs.manifest`, the current tip, not the pinned
  digest's own manifest]. Nothing provides `/usr/bin/editor` [I].
- git (1:2.47.3-0+deb13u1) recommends ca-certificates, less, patch and ssh-client. None of them is
  installed under `--no-install-recommends` [C: packages.debian.org/trixie/git].
- Debian's git defaults to the editor `editor` and the pager `pager` [V: `git var GIT_EDITOR`].

**Consequence.** A task may use only what **both** images contain. Timelike additionally has procps,
ca-certificates and `/opt/timelike/python`. Neither image has `make`, or a `python3` on PATH. A task
that used any of those would rig the result, so the catalog declares its prerequisites, and a
prerequisite is installed into both images or into neither.

**Alternative rejected.** Installing git's recommends in vanilla. It is a defensible "developer image"
reading, but it adds `less` and ssh-client, which timelike deliberately lacks, so the two images would
differ by more than timelike's layers.

### RB2 · The invocation path: `docker exec`, no `-t`, no `-i`, no TERM (FR-3)

**Decision.** Each tool call is:

```
docker exec -u agent -w /home/agent/task <container-id> \
  sh -c '<wrapper>' <limit> '<command>'
```

The wrapper and its arguments are identical for both images.

**Rationale.**
- `TERM` decides whether git tries an editor at all. moby adds `TERM=xterm` only when the exec itself
  has a TTY [I, from moby's `CreateDaemonEnvironment`], so a preflight asserts that `TERM` is empty in
  both images.
- With vim, `TERM=xterm` and an open idle stdin, the host hung (rc 124). With stdin at EOF, vim exited
  at once [V]. So we use no `-i`: stdin is at EOF, and `-i` would add a hang class that no harness
  path needs.
- The wrapper is dash (`sh`). It reads no startup file and adds no second bash. The command itself
  runs as `bash -c`, so timelike's `BASH_ENV` hook applies exactly as it does for a real harness.

**Alternatives rejected.**
- `-i` with an idle pipe. It changes nothing for git without TERM [V], and it adds a hang class.
- `bash -lc` for slice 0. It is recorded as the trace's `invocation` field, so slice 1 can add it as a
  variant.

### RB3 · Behaviour per command, vanilla and timelike

Vanilla was verified by `env -i` emulation [V]. Timelike was verified by replaying its ENV [V]; the
image itself was not run [I].

| Command (no TTY, no TERM) | Vanilla | Timelike |
|---|---|---|
| `git commit`, no `-m` | rc 1, fast: "Terminal is dumb, but EDITOR unset" | rc 1, fast: "Aborting commit due to empty commit message" — **tie** |
| `rebase --continue` needing a message | **rc 1**, rebase left stopped | **rc 0** |
| `git log`, `git diff` | rc 0; no pager, because stdout is not a TTY | rc 0 — **tie** |
| https fetch hitting 401, no helper | rc 128 in under 0.1 s | rc 128 — **tie** on exit code |
| a pre-commit hook that fails | rc 1 | rc 0, the hook skipped |
| a pre-commit hook that sleeps | **hang** until the limit (rc 124) | rc 0 |

**Finding (it corrects spec Assumption 5).** On this path, vanilla git's interactive traps **fail fast
rather than hang**. The only guaranteed vanilla hang is a repository hook that does not return. The
pager, the REPL mode and a vim hang all need a TTY, and this path has none.

### RB4 · The slice-0 catalog

Each task:
- is **identical in both images**
- has a setup and a check that run outside the counted run
- has a fake-agent policy that **takes no environment argument**

The fake agent takes one tool call per turn.

**Tasks.**

| Id | Capability | Setup | Policy | Completion check (artifacts) | Predicted: vanilla / timelike |
|---|---|---|---|---|---|
| `git-inspect` | Pager defaults (control) | A repo with history and an unstaged change | `git log -n 5 > out/log.txt`, then `git diff > out/diff.txt` | Both files are non-empty | 2 calls, 0 non-zero / the same. **Tie.** A pager needs a TTY, and the report says so |
| `git-rebase-continue` | Editor defaults | `main` and `side` edit the same line; a repo-local identity | `git rebase main`; write the resolution; `git add f`; `git rebase --continue`; if it fails, `git -c core.editor=true rebase --continue` | No `.git/rebase-merge`; `main` is an ancestor of `side`; `f` resolved | 5 calls, 2 non-zero / 4 calls, 1 non-zero. **Timelike wins** |
| `git-commit-hook-hangs` | Hooks off | The change is staged; `pre-commit` runs `sleep 3600` | `git commit -m M`; if it hangs or fails, `git commit --no-verify -m M` | HEAD's message is M, and its tree has the change | 2 calls, 1 hang / 1 call. **Timelike wins.** The guaranteed vanilla hang |
| `git-commit-hook-rejects` | Hooks off (**the cost**) | The staged change contains `TODO`; `pre-commit` rejects `TODO` | `git commit -m M`; if it fails, remove the `TODO` lines, `git add`, and commit again; if it hangs, `--no-verify` | HEAD has the change **and** no `TODO` in its tree (the repository's own policy) | 4 calls, 1 non-zero, completed / 1 call, **failed** (the check fails). **Timelike loses** *(corrected at T005 from 3: the policy is 4 commands)* |

The fourth task is kept on purpose. Timelike's `core.hooksPath=/dev/null` commits content the
repository's own hook would have rejected. That is the price of FR-4 in feature 001. P6 wants losing
cases shown, and listed first.

**Capabilities with no observable difference on this path.** These are recorded in the catalog's
`not_benchable` list, not built as tasks:

| Capability | Why there is no difference |
|---|---|
| The output contract and `timelike` tools | Vanilla lacks the tools. A not-told agent would never call them. Slice 1's told/not-told arm measures this |
| Job counts from `cpu.max` | Needs a build tool, and neither image has one |
| `TZ=UTC` | Slim's tzdata already defaults to UTC [I] |
| `PYTHON_BASIC_REPL` | Needs a TTY, and a `python3` on PATH |
| The secret strip | Changes the environment, not turns or exits. Planting a token-shaped variable would also collide with FR-12's refusal |
| Credentialed fetch | A tie on exit code, and it needs a local server |

### RB5 · Killing a hung call (FR-4)

**Evidence.**
- The exec API cannot kill an exec'd process (moby #35703, #8488) [C].
- Killing the CLI leaves the process running inside the container. The repository already records this
  (`tests/e2e/helpers.bash:130`) [V].

**Decision.** The limit lives **inside** the container, in an identical wrapper:

```
sh -c 'timeout -s TERM -k 2 "$0" bash -c "$1" & t=$!; wait $t; rc=$?; kill -KILL -$t 2>/dev/null; exit $rc' <limit> <command>
```

- GNU `timeout` makes itself a process-group leader, and signals the group when the limit expires [C,
  coreutils]. On the host, a hook's `sleep` child was gone and no `index.lock` was left [V].
- The unconditional `kill -KILL -$t` after `wait` also kills a background child that outlived a normal
  exit. Such a child would hold stdout open and keep `docker exec` waiting for EOF [I].
- A **hang** is recorded when the exit code is 124 or 137 **and** the elapsed time is at least the
  limit. The time test matters because a command may itself exit 124; `helpers.bash` already does the
  same.
- **Corrected at T006 [V].** The wrapper first read `kill -KILL -- -$t`. dash's `kill` builtin
  rejects `--` ("Illegal number: -"), so the group kill silently never ran, and a detached child held the
  call open until the backstop fired. The executor unit caught it; the form is now `kill -KILL -$t`.
- **Backstop.** The driver's own subprocess deadline is the limit plus 10 s. If it fires, the driver
  records a hang, removes the run's container with `docker rm -f`, and ends the run as `hung`.
- **Streams.** Two pipes, drained by a selector. Every byte is counted, and only a capped head and
  tail are kept. Wall-clock is measured by the driver with `time.monotonic()`, and includes the same
  exec overhead for both images.
- **One fresh container per run**, started with `docker run -d --init --network none --cap-drop ALL
  --security-opt no-new-privileges --entrypoint sleep <image-id> infinity` and removed afterwards. The
  flags are identical for both images.

**Alternatives rejected.**
- `docker kill` on every hang: the run could not continue.
- `docker exec pkill`: needs procps, which vanilla lacks, and matches by name.
- Plain `setsid`: it has the same pipe problem.

### RB6 · The bench driver image (FR-5, FR-15)

**Decision.** `bench/driver/Dockerfile` is built from `DEBIAN_IMAGE`:
- **Interpreter:** uv-installed CPython `PYTHON_VERSION` at `/opt/timelike/python`, exactly as in
  `image/Dockerfile` §2.
- **Docker CLI:** `/usr/local/bin/docker`, copied from `DOCKER_CLI_IMAGE` as `tests/runner/Dockerfile`
  does.
- **Python code:** `agentio` and the `benchlib` package are copied into site-packages. The tools'
  shebang is `python3 -I`, which ignores `PYTHONPATH`.
- **Tools:** `timelike-bench` goes in `/opt/timelike-bench/bin`, and a copy of `timelike-conform` goes
  beside it.
- **Stamp:** `GIT_SHA` is baked into the label and `/opt/timelike-bench/REVISION`.

**Rationale.** Building from the agent image would put the socket into a timelike image (H1), and would
make the driver one of the environments it measures (P005).

**Alternative rejected.** Running the bench code from a read-only repository mount. It avoids a
rebuild, but the `-I` shebang breaks the `agentio` import.

### RB7 · Trace paths (cross-stack P002, docker-compose P001)

**Decision.**
- Output goes to `bench/out/<run-id>/`, which is git-ignored like `tests/out/`.
- `bench/run.sh` resolves the output path with `realpath` **on the host**. It bind-mounts it into the
  driver **at the same absolute path**, so every path in a trace or report exists on the host.
- **Only the driver writes files.** Task containers get no mounts.
- The driver runs as `-u $(id -u):$(id -g) --group-add <socket gid>`, as the e2e runner does.

### RB8 · Identity and staleness (FR-2, FR-6, FR-8; docker-compose Q004)

**Decision.**
- `bench/run.sh` passes `GIT_SHA`, and `make`'s `stamp-check` refuses a dirty tree. The driver needs no
  git.
- The driver reads `org.opencontainers.image.revision` from the timelike, vanilla and driver images.
  Each must equal `GIT_SHA`. An empty value or a mismatch refuses the run, naming both revisions.
- Each image's `.Id` is captured once, and containers are started **by ID**, so a rebuild in between
  can't swap one.
- A local build has no `RepoDigests` [C]. So vanilla is recorded as `image_id` (the content-addressed
  config digest) plus `base_digest` (from `pins.env`), under those names. The image ID is never called
  a registry digest.

### RB9 · API-key refusal (FR-12)

**Decision.** Port the F002 rule from `shell-env.bash` exactly:
- Split the name on `_`, and uppercase each part.
- Refuse if any part **is** KEY, KEYS, APIKEY, ACCESSKEY, PRIVATEKEY, PASSPHRASE, PASS, CREDENTIAL or
  CREDENTIALS.
- Refuse if any part **ends with** PASSWORD(S), PASSWD, TOKEN(S) or SECRET(S).
- Exempt `GIT_CONFIG_KEY_n`.

This matches `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, `CLAUDE_CODE_OAUTH_TOKEN` and
`OPENAI_API_KEY`. A fake-agent run does **not** honour `TIMELIKE_ENV_ALLOW`.

**What is checked:**
- the driver's own `os.environ`
- each image's `Config.Env`
- each task container's `Config.Env`

`bench/run.sh` passes an explicit `-e` list, and never forwards the host environment.

### RB10 · Supply-chain gate (FR-16)

**Finding.** `scan/scan.sh` scans only `timelike-agent:local` [V].

**Decision.**
- Loop over the agent, vanilla and driver images, with a separate output directory for each and one
  baseline per repository name (`evaluate.py` already keys baselines by repository and base digest [V]).
- `evaluate.py` and the dists listing run in the **agent** image's interpreter, because vanilla has no
  Python.
- pip-audit records `none` for vanilla.

**Risk.** The driver carries the Docker CLI, which is a Go binary. Grype will likely report fixable
Go-stdlib Highs in it, and those block until `DOCKER_CLI_IMAGE` is bumped [I]. The e2e runner image
already holds the same CLI unscanned [V]. That is recorded, not fixed here.

### RB11 · What the fake agent cannot reveal (cross-stack P005)

1. **Its policy is written by the people who built timelike.** The recoveries it takes
   (`-c core.editor=true`, `--no-verify`) are ones a real model might not find, or might find in
   another way. How big vanilla's penalty is gets **written**, not measured.
2. **The tasks were selected** because timelike differs there. The catalog shows where a difference
   can occur, not how often one does.
3. **Messages go unread.** A real agent's cost depends on how clear the error text is. The fake agent
   reacts only to exit codes and hangs.
4. **TTY-dependent capabilities are invisible** on this path.
5. **Token and context costs are not modelled.**

These five limits are why every fake-agent report says, on its first line, that it proves the pipeline
and not the value.
