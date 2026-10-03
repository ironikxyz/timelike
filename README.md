# timelike

A containerised shell environment for coding agents. Everything the agent runs behaves
non-interactively however the harness starts the shell, the agent holds no privilege, and every
timelike tool speaks one output contract.

This repository holds the environment. Its governance is in `.specswarm/`: the constitution, the tech
stack and the quality standards. Each feature has its specification, plan, contracts and decision log
under `.specswarm/features/`.

## Status

**Feature 001, slice 0: agent shell baseline and output contract.**
- The image: Debian trixie-slim with a pinned interpreter, an unprivileged `agent` user, no sudo or
  setuid binaries, and non-interactive defaults in the process environment.
- `agentio`: the output-contract module.
- `timelike`: environment info and build revision.
- `timelike-conform`: the conformance check.
- A supply-chain scan gate.

**Feature 002, slice 0: speedup bench (skeletal).** One command runs catalog tasks in a vanilla
image and in the timelike image, under a deterministic fake agent, and writes a trace per run and a
report. See "Speedup bench" below.

**Feature 003, slice 0: concluding run (skeletal).** `run COMMAND` always ends with a verdict:
- it returns when the command exits, even if something the command backgrounded still holds the
  output
- at its limit it stops the command's whole process tree
- it shows the head, the first errors and the tail of long output, with the exact command for the
  rest
- `$?` is the command's own exit

See "run" below.

**Feature 004 (prompt 12), slice 0: Adele and grants (skeletal).** Adele is the one authority,
outside the agent's privilege, that holds credentials and enforces the operator's grants. In slice 0
she brokers one capability, an in-compose **stand-in** that is not a provider, with a synthetic
credential the agent never sees. See "Adele" below.

This README makes no claims about timelike's value. Those are made only from reproducible bench
results (constitution P6).

## Needs

- **A Docker daemon** (Docker Engine with Compose v2) for building, testing and scanning. Nothing
  else is installed on the host: every tool runs in a pinned container (`pins.env`).
- Python 3.12 or later and pytest, only for the advisory host lane below. The image pins its own
  interpreter (3.14.x, `pins.env`).

## Build, test, scan

```bash
make build        # stamps the image with `git rev-parse HEAD`; refuses an empty stamp or a dirty tree
make test         # Docker lane (authoritative): bats end-to-end from outside the container + unit tests
make test-host    # host lane (advisory): agentio/conform unit tests + a check of the env-layer files
make lint         # shellcheck, ruff, mypy --strict; gofmt, go vet, staticcheck (Adele)
make up          # agent + Adele + the stand-in, on the operator's adele/grants.conf
make scan         # supply-chain gate: Syft+Grype, pip-audit, govulncheck (Adele), gitleaks
make demo         # the manual demo: git commit / rebase --continue / log return in seconds
make bench        # the speedup bench (feature 002): vanilla vs timelike; traces and report in bench/out/
```

`make test` writes its results to `tests/out/`: `summary.json`, the bats TAP and JUnit output, and
the full log.

### Two verification lanes

| Lane | Proves | Authoritative for |
|---|---|---|
| **Docker** (`make test`) | the built image, driven from outside the way a harness drives it | the acceptance criteria, the build stamp, the scan gate |
| **Host** (`make test-host`) | `agentio` and `timelike-conform` behaviour; the env-layer *files* | nothing on its own: file evidence, not image evidence |

A host-lane pass never counts as an acceptance-criterion pass.

## Environment defaults

Every shell the harness starts (`bash -c`, `bash -lc`, interactive) is non-interactive by default:
no pager, editor or prompt, and no colour.

**A repository's own git hooks run, each under a time limit.** Hooks in `.git/hooks`, or in the
repository's own `core.hooksPath` (husky, for example), run as they would without timelike. A hook
that has not finished after **60 s** is stopped, and the git command fails with a verdict naming the
hook and the limit. To raise the limit, set `TIMELIKE_HOOK_TIMEOUT=<seconds>` for a shell, or run
`git config timelike.hookTimeout <seconds>` for a repository. timelike never switches a project's
checks off. The dispatchers are in `image/rootfs/opt/timelike/git-hooks/`.

**The limit holds in the environment timelike provides.** An agent or tool that discards that
environment, for example with `env -i`, gets git's own behaviour, as without timelike. The hooks still
run. Hooks in `.git/hooks` stay bounded, through `/etc/gitconfig`. Hooks in a repository's own
`core.hooksPath` run **unbounded**, because that setting then outranks timelike's. When in doubt, run
git through [`run`](#run--the-concluding-run), which stops the whole process tree at its own limit:
`run --timeout 300 git commit -m "…"`. (Discovery revision 8, tension T4. Pinned by
`tests/e2e/hooks-under-env-i-default-bounded-local-unbounded.bats`.)

From slice 1, it also gets these:

- **Job counts from the container's CPU limit.** `TIMELIKE_CPUS` is taken from cgroup `cpu.max`,
  capped by the CPU affinity. From it come `MAKEFLAGS=-jN`, `CMAKE_BUILD_PARALLEL_LEVEL`,
  `CARGO_BUILD_JOBS`, `GOMAXPROCS`, `PYTEST_XDIST_AUTO_NUM_WORKERS` and `PYTHON_CPU_COUNT`. Each is set
  only if it is not already set, so an explicit value wins.
- **No secret-shaped variables.**
  - A variable whose name has a component `KEY`, `PASS`, `CREDENTIAL(S)` or similar is removed.
  - So is one whose name has a component ending in `PASSWORD`, `TOKEN` or `SECRET`.
  - To let one through, list its exact name in `TIMELIKE_ENV_ALLOW`, e.g.
    `docker exec -e TIMELIKE_ENV_ALLOW=NPM_TOKEN -e NPM_TOKEN=... timelike-agent bash -c '...'`.
  - The strip applies to the agent's shells. It cannot remove what the container itself was started
    with, so don't pass secrets to the agent container (P4).
- **`TZ=UTC`**, and Python's REPL in its basic, scriptable mode (`PYTHON_BASIC_REPL=1`).

Plain `sh -c` and a direct exec of a non-shell binary get the static defaults (including `TZ`), but not
the job counts or the strip. The details are in `image/rootfs/etc/timelike/shell-env.bash`.

## The output contract

Every timelike tool follows rules 1–16 in
`.specswarm/features/001-agent-shell-baseline/contracts/output-contract.md`. In brief:
- JSON when piped, text on a terminal
- a self-labelling first line
- capped output that says what was left out and how to get it
- one exit-code vocabulary (0, 1, 2, 3, 4, 124) for a tool's own outcomes; a tool that runs a
  command you named passes that command's exit through (discovery revision 9)
- structured errors
- never a prompt, pager, editor or terminal read
- one session event per invocation

`timelike-conform` checks every timelike tool on PATH against it.

**Predicting a tool you have not seen.** Three things hold for every timelike tool:

- **First line.** On a terminal or with `--text`: `<tool>: <target> [<scope>]`, then
  `verdict: <verdict>`. With JSON (the default under a harness, where stdout is a pipe): an object whose
  first keys are `tool`, `target`, `scope`, then `verdict` and `exit`.
- **Last line**, predicted by its kind:
  - **Capped text:** always
    `… omitted <N> lines (<B> bytes) — full output: <path>; more: <command>`. It appears only when
    output was cut, so its absence means nothing was omitted.
  - **Uncapped text:** the result's own last line. Nothing trails it.
  - **JSON:** the object carries `exit` (and `truncated` when capped).
  - The contract document gives the full rules (discovery revision 6).
- **Exit codes:**

  | Code | Meaning |
  |---|---|
  | 0 | success (zero search results is 0, with a count of zero) |
  | 1 | failure |
  | 2 | usage |
  | 3 | not found, or unsure |
  | 4 | confirmation or a grant is required |
  | 124 | timeout |

  These are a tool's **own** outcomes. A tool that runs a command you named, such as `run`, passes that
  command's exit through instead, as `timeout` and `env` do: 126, 127 and 128+n included, and 124
  only when the tool's own limit fired. Its manifest says `"passes_exit": true`, and its JSON carries
  `cause` (`command`, `timeout`, …) and `command_exit`, which tell the two apart.

  Errors go to stderr as `error: <what> (code N) — <remediation>`, or as one JSON object with `--json`.

## run — the concluding run

Put `run` in front of any command whose output may be long or which may hang:

```bash
run make test                        # verdict, then head / first errors / tail; $? is make's
run --timeout 300 ./slow-job.sh      # or TIMELIKE_RUN_TIMEOUT=300; the default is 100 s
run sh -c 'make 2>&1 | grep -v noise'  # shell syntax goes through a shell: run takes argv, like timeout(1)
```

- **The verdict comes first,** on the line after the header. It gives the exit code and its cause in
  words, the duration, the line count and the log path:
  `verdict: exit 1 (command exited 1) · 4.2 s · 5000 lines · log /tmp/timelike/default/run/….log`.
- **Long output is never cut in the middle without saying so.** Over the cap (200 lines, or
  `--limit N`), `run` shows:
  - the first 50 lines
  - up to 20 later lines that look like errors, each prefixed with its line number in the log (`L700:`)
  - the last 100 lines
  - `more: sed -n A,Bp <log>`, the exact command that prints the rest. It reads the log; it never
    runs the command again.

  The full output is always in the log.
- **A backgrounded child cannot hold the call.** `run` returns as soon as the command exits, and the
  verdict names anything the command left running (`detached: 1234 node`). It does not stop those
  processes.
- **At the limit, the whole tree stops.** That includes grandchildren, nested `timeout`s and `setsid`
  children. The exit is 124, and the verdict says `timeout` and how to raise the limit. Keep the limit
  below your harness's own call limit (Claude Code: 120 s). Otherwise the harness kills the call before
  `run` can conclude it.
- **`$?` is the command's own:** 0, 1, 42, 126 (cannot execute), 127 (not found), 137 (SIGKILL), and
  so on. `run`'s own outcomes are 2 (usage, before anything runs), 1 (`run` itself failed) and 124 (its
  limit).
- **The command gets no stdin.** A prompt fails fast instead of waiting. `cat x | run grep y` does not
  feed `grep`; write `run sh -c 'cat x | grep y'`.
- Slice 1 adds memory and disk causes, and secret redaction. Slice 2 adds log garbage collection and
  repeat detection.

## Speedup bench

```bash
make bench                              # every catalog task, in the vanilla image and the timelike image
make bench TASKS=git-rebase-continue    # one task (space-separated for several)
less bench/out/<run-id>/report.txt      # the report
```

`make bench` builds three images from the pinned base, all stamped with the checkout's revision:
- the agent image
- a **vanilla** baseline: the same base, the same unprivileged user and git, without any of
  timelike's layers
- the bench **driver**, the only container that holds the Docker socket

The driver refuses any image whose revision label differs from the checkout, and refuses to start if
an API-key-shaped variable is present. It runs each task in a fresh container for each environment, with
every tool call a non-interactive `bash -c` with no terminal. It writes one trace per run to
`bench/out/<run-id>/traces/` and a report to `bench/out/<run-id>/report.txt`. `timelike-bench report
<dir>` rebuilds the report from the traces alone.

**Read the report's first line.** Slice 0 drives the tasks with a deterministic fake agent, and every
report it produces begins:

> FAKE-AGENT BENCH PIPELINE DEMO RUN -- This is not a test of timelike, rather a test of the bench test
> itself (its presentation and usefulness to the human user). The agent's policy was written by
> timelike's own builders.

The fake agent's policy, the task selection and the recoveries it takes were all chosen by the people
who built timelike, so a fake-agent report shows that the bench runs, traces and reports. It is not
evidence that timelike helps.

After the maintainer statement, the reproduce command and the exact revisions, harness and model
compared, the report lists the tasks where timelike **loses** first, then the ties and the wins. Each
task says what it tests and what differs between the two images, gives the verdict in words, shows the
metrics, and then tells what happened in each image call by call and why the run ended as it did.
Tokens appear only in an appendix.

## Adele — reaching actions, by grant

Anything that reaches beyond the environment goes through Adele, her own container
(`timelike-adele`). She holds every credential, checks each request against a grant the operator
wrote, performs what the grant allows, refuses what it does not before anything happens, and records
everything in her ledger. The agent asks with `adele`:

```bash
adele status                                            # reachable from here? her build revision
adele grants                                            # the grants she applies: limits, spent, live
adele request standin.box create --name tl-1 --ttl 1h --port 8080
```

Beyond its grant, a request exits **4** and nothing is performed. The refusal names the grant, the
limit, what it allows, what the request needed, and the operator's exact command to extend it:

```
error: beyond grant demo: limit ports allows 8080, this request needs 22; nothing was performed (code 4) — the operator extends it: docker exec timelike-adele adeled extend demo ports 22
```

(Slice 0 prints this refusal on stderr. Its envelope on stdout waits on a decision about 001's exit-4
contract.)

**The operator** writes `adele/grants.conf` (`make up` copies `adele/grants.example.conf` there if it
is absent; the format is documented in that file). Adele reads it once, at start, read-only. A
malformed file stops her, naming the line at fault, in `docker logs timelike-adele`. While she runs:

```bash
docker exec timelike-adele adeled extend demo budget 2.00 USD   # budget, ttl, instances: set; ports, capabilities: add
docker exec timelike-adele adeled ledger                        # every request, refusal and extension
```

Nothing of Adele's is mounted into the agent's container: her ledger, her grant file and her
credential live in her container only. She has no outside network in slice 0.

**The stand-in** (`timelike-adele-standin`, compose profile `standin`) is a test and demo service.
It proves the grant path and that the credential never reaches the agent. It proves nothing about any
real provider: those arrive with the features that use them (the Docker socket at 13, fly.io at 14).
Its credential is a canary, generated inside Docker into a volume, never on the host's disk.

`make test` starts Adele on the lane's own grant file and clears her volumes first, so every run
starts from an empty ledger. Run `make up` afterwards for the operator's own grants.

## Layout

```
image/        Dockerfile and the fallback config layer (/etc/gitconfig, /etc/profile.d)
tools/        agentio (the contract) and the tools on PATH in the image
tests/        unit (pytest), e2e (bats, driven from outside), host (advisory), fixtures, runner
adele/        Adele (Go, FROM scratch): adeled, the test-only stand-in, grants.example.conf
scan/         the supply-chain gate (the agent, Adele, vanilla and driver images)
bench/        the speedup bench: benchlib, timelike-bench, the vanilla and driver images, run.sh
compose.yaml  the agent (no capabilities, no-new-privileges, no Docker socket), Adele, the stand-in
pins.env      every pinned image and version
```

## Licence

MIT.
