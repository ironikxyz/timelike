# Cycle report — 013 package guard

## Cycle 1 — bridge/sends/15-rev2-20261012-001145.md

**Written:** 2026-10-12, on `013-package-guard` (from `master` `50dd84d` = `public/main`, `v0.18.0`). specswarm
**4.0.1-botbaubble.2.44.0**: the expanded commands' `PLUGIN_DIR` named that cache path (lore `specswarm` Q002).
An attended run: specify, plan, tasks, then implement without `--dispatch`. **Nothing was pushed or merged.**
None of this has run in the image: lane decides it.

**Status in one line:**
- **Built:** the checks, the lookups, the lockfile reading, the verdict, the confirm and its record, the
  registry stand-in and the tests, as one tool, `package-guard -- CMD`.
- **Held for FOR-MENTOR Item 24, raised before any of it was built:**
  - how the bare `pip install` / `npm install` reach that tool;
  - pnpm in the image;
  - the event-field alternative for the override.

### Group A — cited from `.implement-complete`

Group A: not applicable — no marker on this path.

### Group B — copied from the send

- source_send: `bridge/sends/15-rev2-20261012-001145.md`
- source_prompt: `plan/.discover/prompts/15-package-guard.md`
- prompt_revision: 2
- discovery_revision: 15
- slice: 1 (natural)

### Provenance (specify)

`spec.md` records:
- `source_prompt: plan/.discover/prompts/15-package-guard.md`;
- `source_send: bridge/sends/15-rev2-20261012-001145.md` (from `--from-send`);
- `prompt_revision: 2`, `discovery_revision: 15`, `audited_against: [2]`.

Specify allocated **013**, as the send expected. Governance is at `[2..15]` and discovery at 15, so no audit
was needed.

### What was built

| Task | Commit | What |
|---|---|---|
| specify, plan, Item 24 | `5740354` | spec (FR-1 to FR-36, D-1 to D-11), plan, research R1 to R10, the contract; **FOR-MENTOR Item 24 raised** |
| T001 | `1fa2714` | the registry stand-in (PyPI Simple API JSON/HTML, npm documents, real wheels and tarballs, a request log) |
| T002, T003 | `f3f7f8a` | `tools/bin/package-guard`, first draft; PEP 440 and npm semver; reading the install command |
| T004 | `6c266de` | the registry each installer would use |
| T005 to T008 | `f2d9b64` | lookups, age, lockfiles, the plan |
| T009 to T011 | `6dc230a` | the tool as a process; the host's real pip, npm and pnpm; pnpm asked for its own registry |
| T012 to T017 | `71a1454` | e2e helpers and four criterion files (17 cells); the shellcheck list; the command reference; the measurement |
| T018 | this commit | this report; `reboot.md` |

### Group C — written by the code instance

**delegations:** `[]`. No subagent ran, and no other feature's code was used beyond `run` (called as a command,
as `verify` calls it).

**criteria_reestablished** (each citation matches exactly one line of the send, `grep -cF` = 1 for all five).
Nothing has run in the image, so every mode is `unconfirmed`. Host evidence is listed beside each, and changes
no mode.

- `15 · "before anything is downloaded, naming the package and the registry checked _(traces to: P4)_"` —
  **unconfirmed.**
  - Cells:
    `tests/e2e/installing-a-package-name-absent-from-its-registry-is-refused-with-exit-4-before-anything-is-downloaded.bats`,
    5 cells: pip in `bash -c` and `-lc`, `uv pip install`, npm, and a 503 registry called unreachable, not absent.
  - Shown through `package-guard -- pip install …`. The bare command is Item 24's.
  - Host: the tool, check and real-installer units.
- `15 · "is refused with exit 4, naming the release date _(traces to: P4)_"` — **unconfirmed.**
  - Cells:
    `tests/e2e/installing-a-package-whose-newest-release-is-younger-than-the-minimum-age-is-refused-naming-the-release-date.bats`,
    5 cells:
    - pip (two styles) and npm refused, naming the date the stand-in itself serves;
    - the named older release installs;
    - a minimum age of 0 installs the newest.
- `15 · "already pinned in the project's lockfile proceeds without registry checks _(traces to: P2)_"` —
  **unconfirmed.**
  - Cells:
    `tests/e2e/installing-packages-already-pinned-in-the-projects-lockfile-proceeds-without-registry-checks.bats`,
    4 cells, with lockfiles written by the image's own npm and uv:
    - a pinned npm install (two styles);
    - `npm ci`;
    - `uv sync --locked`, and a pinned `uv pip install`.

    Each is read as no request with the guard's user agent in the stand-in's log.
- `15 · "with the confirm flag proceeds and records the override in the session event log _(traces to: P4)_"` —
  **unconfirmed.**
  - Cells:
    `tests/e2e/re-running-a-refused-install-with-the-confirm-flag-proceeds-and-records-the-override.bats`,
    3 cells:
    - the refusal's own `confirm` string, run for pip and for npm: it installs, and the session's `events.jsonl`
      leads by `ref.log` to the record (package, ecosystem, registry, reason, session);
    - `--yes` over nothing records nothing.
  - Item 24 Q4 asks whether the fields belong inside the event line.
- `15 · "is refused with an explanation before any install runs _(traces to: D24)_"` — **unconfirmed** (Manual).
  The mentor captures it after the lane. It is the agent's own install, so it also waits for Item 24's route.

**reconcile_mode:** `full`. This is a first build: the spec carries every criterion of the send, and each
slice-1 Automated criterion has cells.

**not_verified**
- **Everything in the image:** the 17 cells, conform over `package-guard` in the image, the stand-in under
  timelike's interpreter there, the image's uv against it.
- **The bare commands** (`pip install`, `npm install`, `uv`, `npx`, `pnpm`): not routed to the guard until
  Item 24.
- **uv's index order:** it follows uv's documentation, not a measurement (no uv on the host). The cells use one
  index.
- **pnpm in the image:** absent (Item 24 Q3). Its forms ran only against the host's pnpm 11.5.1.
- **The standing grant for registries under Adele** lands with 12 slice 2. Nothing claims Adele enforces
  registry access, and the manifest says it does not yet.
- **Dependency confusion:** a name on two configured indexes is named, not refused (D-6).
- **Not evaluated:** environment markers; the dependencies the named packages pull in (the installer resolves
  those); a private registry needing credentials (the guard sends none, so 401/403 refuse as "denied", D-11).
- **Not guarded:** `uv run` without `--with` (it may sync a project); `pip download`; `npm update`.
- **The added time in the image**, and against a real registry: measured on the host only (research
  Measurements: about 300 to 350 ms added to a passing install, ~200 ms of it the check).
- **Untested:** a registry document over 64 MiB, and a registry dripping bytes slowly.

**changed_other_features**
- **README.md:** the generated command reference only (`scripts/readme_reference.py --write`: `package-guard`'s
  section). Its drift test requires it, and so does CLAUDE.md's rule.
  - The send's `## README status` block is **not** applied. Its condition (all four slice-1 Automated criteria
    met) waits for Item 24's route for "installing a package". The What row, the Status paragraph and the
    guard section are untouched.
  - The command reference is generated, so it carries no `<mark>` highlighting; its changed tool is
    `package-guard` (new).
- **`tests/e2e/helpers.bash`:** stand-in helpers (`standin_start`, `standin_stop`, `standin_count`,
  `standin_clear`, `standin_released`, `pyj`). Nothing existing changed.
- **`Makefile`:** the four new bats files in `SHELLCHECK_FILES`.
- **`pyproject.toml`:** `tools/bin/package-guard` in mypy's file list.
- **The announcement (007)** lists the new tool from its manifest, with no change to the generator. Its rule
  lines for package installs wait for Item 24.
- **`FOR-MENTOR.md`:** Item 24.

**process_failures_recorded**
1. **I broke the standing rule against `pkill -f` with my own command's pattern.** While smoke-testing the
   stand-in, a `pkill -f` whose pattern matched my own command killed my shell (exit 144). No stand-in was left
   running (checked through `/proc`). The stand-in now writes its pid, and every stop uses it.
2. **T001's commit (`1fa2714`) was made before the deny-list ran.** It ran on HEAD at once: PASS, 495 files,
   P1–P7 0/0. Every later commit went through a helper that runs the deny-list on the staged tree first.
3. **Three start times in `decisions.md` were composed, not read.** They were T004's, T005–T008's and
   T009–T011's, each later than its own completion. They were corrected to the previous commit's real time, and
   the correction is recorded there.
4. **A rewrapping script of mine dropped two tuple endings** in the tool's option tables, and the file did not
   parse. ruff found it, and the endings were restored before any commit.
5. **The first real-pnpm unit found the guard checking the wrong registry for pnpm.** pnpm 11 ignores
   `npm_config_registry`. This was caught before any commit of the e2e, and the fix asks pnpm itself.

**retired_prompts_seen:** none.

### Host lane

`make test-host`, timelike's 3.14.8 in a scratch venv, on the tree at `71a1454`. Only documentation changed after
that commit.
- pytest tests/unit: **2208 passed, 13 skipped** (532 s);
- `test_env_layer.sh` 60 of 60;
- `test_shell_env_hook.sh` 57 of 57;
- `test_command_not_found.sh` 33 of 33.

Exit 0.

The guard's own units are 215, including the stand-in's and the README reference's: they run the host's real
pip 24.0, npm 10.9.7 and pnpm 11.5.1, and conform over the tool. Other checks:
- ruff check and format: clean;
- mypy `--strict`: clean over 31 files;
- shellcheck 0.11.0: clean over the Makefile's 88 files;
- the deny-list: PASS before every commit but T001's, which was checked straight after (above).

Implement's step 10 (quality score) was not run: the installed blocks cannot run pytest here, and a score
would be `unknown`, as in earlier cycles.

### Then

Commit everything, and report done. No commit after that until the mentor says the lane has ended.
- **The lane:** `make test`, `make bench-images`, `make scan` with the deny-list read, and `make lint`.
- **After it:** the mentor's D24 capture, which also needs Item 24's ruling, then sign-off.
- **Merge:** `--no-ff`, after sign-off.

### Addendum 1 — Item 24's ruling built; lane 013s1-a2's items 1 and 2

**Written:** 2026-10-12T18:01:36Z (read from the clock), on `013-package-guard`. Same send, same cycle. Instructed by the
operator, relaying `../bridge/feedback/15-20261012-034908-lane-013s1-a2-target-cells-and-a-gnutls-critical.md`
(the lane's findings) and `../bridge/feedback/15-20261012-015246-item-24-bare-installs-reach-the-guard.md` (the
ruling). Lane 013s1-a2 had ended; nothing was edited while it ran. **Nothing was pushed or merged.** None of this
addendum's work has run in the image: lane 013s1-b decides it.

**Status in one line:** the bare `pip`, `pip3`, `uv`, `npm`, `npx` and `pnpm` now reach the guard through
`/opt/timelike/shims`, the override is in the event line itself, and every criterion's cells run the installer by
its bare name. The README status block is applied.

| Task | Commit | What |
|---|---|---|
| T019 to T022 | `3542eb3` | the event's `override` (001's schema and contract, agentio); `package-guard --gate` and the shims' directory skipped; the shim, the image's § 5a, the PATH (`ENV`, profile.d); the announcement's lines; their units; 007's PATH-order units |
| T023 to T025 | `f1814fa` | the four criterion files on bare names (28 cells), `run_bare`; the stand-in's `bin` and its `pnpm`; 007's SC-6 runtimes cell; the agent-cannot-alter list; CVE-2026-88647 in both baselines; the shellcheck list |
| T026 | this commit | the README; the spec (FR-37 to FR-42), research R11, the contract, the data model; this addendum; FOR-MENTOR Item 24 closed; `reboot.md` |

#### Item 24's ruling, as built

- **Q1 (b′), the shims.** `/opt/timelike/shims/{pip,pip3,uv,npm,npx,pnpm}` are links to one wrapper,
  `/opt/timelike/libexec/install-shim`, first on PATH in the image's `ENV` and in `00-timelike-path.sh`.
  - **It is POSIX sh, not bash** (Item 24 proposed bash). A bash script reads `BASH_ENV`, and the hook's secret
    strip would unset an exported `NPM_TOKEN` before npm ran: the real command's environment would change.
    dash reads no startup file. Builtins only before the exec, as proposed.
  - **Condition 1, pass-through is free:** a call with none of its installer's install words is `exec`'d at once.
    **Measured on the host** (research R11; medians; the real command `/bin/true`, so only the shim is timed):
    **about 0.9 to 1.05 ms added** to `pip --version` and `npm run test` (300 runs each, run twice). An install
    that passes adds **about 233 ms** (30 runs, `pip install tl-old` against the stand-in), the guard's check.
    The image's figures are the lane's to take.
  - **Condition 2, the real command untouched:** it is the first of its name on PATH that is not the shim (a
    decoy alias of the shims directory and a second link are skipped; units). On a pass the shim `exec`s it, so
    output, stdin, environment and exit are its own: units read them from a decoy installer, and one runs the
    host's real pip through the shim (`Successfully installed …`, nothing of the guard's). The guard is asked
    with stdin closed, so a piped install keeps its input.
  - **Condition 3, the gaps named:** in the announcement (one line), in `package-guard --agent-info`
    (`shims.not_reached`) and in `not_verified` below. Slice 2's proxy, (c), is carried as the slice 2 seam.
  - **Condition 4, `type -a`:** `type -a pip` shows `/opt/timelike/shims/pip` first; the announcement says so.
    The pnpm cell reads `type -a -P pnpm`.
  - **Condition 6:** the vanilla image is untouched (`bench/vanilla/Dockerfile` has no change).
  - **Condition 7:** see the criteria below.
  - **With no real installer** (pnpm before the agent installs it), the shim hands the name to 007's
    command-not-found handler, exit 127, with the data file's `npm install -g pnpm`. Its first line names the shim
    and line 1, where bash would name the caller.
- **`--gate`.** The shim asks `package-guard --gate -- NAME ARG…`, which checks and runs nothing. Exit 0: the
  shim drops the guard's output and execs the installer. Otherwise it prints the output (exit 4: the envelope)
  and exits with the guard's code. A missing guard fails closed and says so. `--gate` takes neither `--yes` nor
  `--dry-run`. The gate prints a verdict like any call (rule: every call ends with one), and the shim keeps it
  to itself; no quiet mode was added to agentio.
- **Q2:** the envelope's `confirm` is `package-guard --yes -- <the original command>`, without the shim's own
  `--gate` and format option (unit and cells).
- **Q3:** no pnpm in the image. The pnpm cell installs, with a bare `npm install -g pnpm` through its own shim,
  the stand-in's `pnpm` package into `~/.local/bin`, as the agent would. It is a script that says it ran, **not
  pnpm**: the stand-in has no pnpm, and the cell may not reach the public registry. It shows the shim in front of
  a pnpm the agent installed, `pnpm --version` reaching it, and `pnpm add <absent>` refused with pnpm never
  running. **pnpm's own install forms remain host evidence** (pnpm 11.5.1, `test_package_guard_real.py`).
- **Q4:** 001's `event.schema.json` gains an optional `override` object, declared in 001's `output-contract.md`
  as 009's fields were: `ecosystem`, `packages` (each `name`, the `version` named if any, `registry`, `reason`,
  `released` for a dated release, `detail`) and `command`. agentio writes it from `Context.event_override`; the
  guard sets it only when `--yes` proceeds over a refusal. Every existing event stays valid (the field is
  optional; every tool's schema units pass). The record file stays, pointed at by `ref`.

#### Lane 013s1-a2, item 1: the `--target` cells

- **The four failing cells** (334, 335, 377, 379) and every other pip invocation in 013's files now install as the
  agent installs: a bare `pip install`, which the image's `pip.conf` makes a user install, with `HOME` set to the
  cell's own directory. The cells read the package from `$HOME/.local/lib/python3.*/site-packages`, and check that
  nothing landed in `/home/agent/.local` or the agent interpreter's own site-packages. **`pip.conf` and the
  guard's handling of `--user` are unchanged.**
- **Checked:** no file of 013's passes `--target` or `--prefix` to pip now. The two `uv pip install --target`
  cells (which passed in the lane, because the guard refused before uv ran, or uv took `--target`) install into a
  project venv instead (`uv venv`, then `uv pip install`), as the agent would. The pnpm cell alone uses the real
  home, because `~/.local/bin` is on PATH by its literal path; its teardown uninstalls it.
- **Rehearsed on the host** with a copy of a CPython 3.14.8 whose `pip.conf` says `user = true` and whose
  EXTERNALLY-MANAGED marker is removed, as the image does: the refusal, `Successfully installed tl-fresh-1.0.0`
  into `$HOME/.local`, the confirm, and the event readers' exact strings. uv was not rehearsed (no uv on the host).

#### Lane 013s1-a2, item 2: CVE-2026-88647

Added to `scan/baseline/timelike-agent.json` and `timelike-vanilla.json`, in the shape of the 2026-10-10 gnutls
entries: origin `git`, `review_by` unchanged (2026-12-27), severity critical. Its reason says plainly that it
bypasses host-name verification on the Common Name path, and states both bounds: the agent holds no credentials in
its fetches (P4); a forged peer on the path could still serve forged content to a git fetch over https, or read
what the agent fetches. The operator's words, `"accept it"` (2026-10-12T16:44:10Z), are in each file's review
note beside the entry's source. The scan's units pass (192); the lane's own grype run decides the gate.

### Group C — Addendum 1

**delegations:** `[]`.

**criteria_reestablished** (the same five citations as Cycle 1, each still a single `grep -cF` match; nothing has
run in the image, so every mode is `unconfirmed`):

- `15 · "before anything is downloaded, naming the package and the registry checked _(traces to: P4)_"` —
  **unconfirmed.** 9 cells: bare `pip install` in `bash -c`, `-lc`, `-ic` and a bash script; bare
  `uv pip install` into a venv; bare `npm install`; bare `npx` from a script; pnpm in `~/.local/bin`; a 503
  registry called unreachable.
- `15 · "is refused with exit 4, naming the release date _(traces to: P4)_"` — **unconfirmed.** 7 cells: bare pip
  in the four styles, bare npm; the named older release installing as the agent installs; a minimum age of 0.
- `15 · "already pinned in the project's lockfile proceeds without registry checks _(traces to: P2)_"` —
  **unconfirmed.** 6 cells: bare `npm install` of a pinned name in the four styles; bare `npm ci`; bare
  `uv sync --locked` and `uv pip install`. Each reads no guard request in the stand-in's log **and** a passing
  gate event in the session, so the guard was asked and asked nothing.
- `15 · "with the confirm flag proceeds and records the override in the session event log _(traces to: P4)_"` —
  **unconfirmed.** 6 cells: the bare pip refusal in the four styles and the bare npm refusal, each then running
  its own `confirm`; the event line's `override` read back (package, reason, the stand-in's release date,
  registry, ecosystem, command, exit) with the record's session; `--yes` over nothing writes neither.
- `15 · "is refused with an explanation before any install runs _(traces to: D24)_"` — **unconfirmed** (Manual).
  The route it needed is built: the agent's own `pip install` now reaches the guard.

**reconcile_mode:** `full`.

**not_verified**
- **Everything in the image:** the shims and their links, the PATH in a built container, the 28 cells, the pnpm
  cell, the agent-cannot-alter checks over the new files, the added time in the image.
- **Not reached by the guard (named gaps, slice 2's proxy):** `python -m pip` and `python3 -m pip`; an
  activated venv's own `pip`, `uv` or `npm`; `/usr/local/bin/pip`, `/bin/uv` or any installer called by its full
  path (the visible escape). Also not shimmed: `uvx` (not in the image).
- **pnpm's own install forms in the image:** a stand-in script stands for pnpm there; the forms are host evidence.
- **`pip install -r /dev/stdin`** (or `-r -`): the installer reads the input, the guard does not (its stdin is
  closed), so those names are not checked.
- Carried from Cycle 1: uv's index order (documentation, not measurement); dependency confusion named, not
  refused (D-6); environment markers and dependencies of named packages; `uv run` without `--with`,
  `pip download`, `npm update`; a registry document over 64 MiB and a slowly dripping registry.

**changed_other_features** (each declared by the ruling or found by this build)
- **001:** `event.schema.json` (optional `override`), `output-contract.md` (its paragraph), agentio
  (`Context.event_override`, `_write_event`); the image `ENV` PATH and `00-timelike-path.sh` (the shims first;
  `/opt/timelike/bin` is now added when absent anywhere, so a second sourcing changes nothing);
  `tests/host/test_env_layer.sh` (the first three PATH entries); the Dockerfile's § 5a (new) and its comment on
  007's links.
- **007:** `tests/unit/test_agent_runtimes.py` (the ENV and login PATH orders); the SC-6 runtimes cell (the shim
  first for pip, pip3, npm and npx, then the `/usr/local/bin` link, which is still what they resolve to past the
  shim); the announcement (`tools/bin/timelike`: three lines when package-guard is installed, the minimum age read
  from its manifest) and `tests/unit/test_announce.py`.
- **001's SC-4 cell (agent-cannot-alter):** the shim, `package-guard` and `/opt/timelike/shims` added to what the
  agent must not change.
- **The scan baselines:** CVE-2026-88647 (item 2).
- **README.md:** the send's status block (row 15, the Status paragraph), the guard's section under "The tools",
  and the sentence in "The container and the `agent` user" that said `/opt/timelike/bin` was ahead of everything
  (now false). Each changed passage is in `<mark>`; there were no earlier marks to clear. The generated command
  reference changed for `package-guard` (`--gate`, the shims' lines). Noticed and **not** changed: "One gap to
  know: `python3` is not on the agent's PATH" (false since 007 slice 1, not this build's), and `view --help`'s
  "(/opt/timelike/bin is first on PATH)" (now true only against vim's `view`); both are another feature's.

**process_failures_recorded**
1. **My first shim test file was named `tty.py`** and shadowed the stdlib module it imported; renamed, and run
   with `-I`. Before any commit.
2. **One unit asserted the refusal in text on a terminal.** The envelope is JSON in every mode (rule 9); the test's
   premise was wrong, not the shim. Corrected before any commit.
3. **A smoke test reached the public registry:** with `/usr/bin` on PATH, a not-found check found the host's
   corepack `pnpm`, which downloaded pnpm 12.11.2 from registry.npmjs.org into the test's own HOME. No project
   file changed; the not-found units now run with a PATH that holds no host pnpm.
4. **I wrote a composed time into `reboot.md`** (the addendum's snapshot time, 17:53:00Z). Replaced at once with
   a time read from the clock, before any commit.

**retired_prompts_seen:** none.

#### Host lane

`make test-host`, timelike's 3.14.8 in a scratch venv, on the tree of `f1814fa` plus this commit's records (no
code changed after the run):
- pytest tests/unit: **2239 passed, 13 skipped** (408 s);
- `test_env_layer.sh` 60 of 60 (the first three PATH entries now asserted);
- `test_shell_env_hook.sh` 57 of 57;
- `test_command_not_found.sh` 33 of 33.

Exit 0. An earlier run in this addendum failed 2 units, both 007's PATH-order units the ruling's PATH change moved;
they were updated (declared above) and the full run repeated. The guard's units: 24 for the shim, 7 more in the
tool's file (the gate, the event's `override`, the shims' directory skipped), 1 in the announcement's. Other checks:
- ruff check and format: clean (266 files);
- mypy `--strict`: clean over 31 files;
- shellcheck 0.11.0: clean over the Makefile's 89 files (the shim added);
- `scripts/readme_reference.py --check`: current, 14 tools;
- the deny-list: PASS before each of this addendum's three commits (512 files, P1–P7 0/0).

#### Then

Commit everything, and report done. No commit after that until the mentor says lane 013s1-b has ended.
- **The lane:** `make test`, `make bench-images`, `make scan` with the deny-list read, and `make lint`.
- **After it:** the mentor's D24 capture (the agent's own install), then sign-off; merge `--no-ff` after it.

### Addendum 2 — lane 013s1-b: a shim resolves when its installer is absent

**Written:** 2026-10-13T01:16:25Z (read from the clock), on `013-package-guard`. Same send, same cycle. Instructed by the
operator, relaying the mentor's findings `../bridge/feedback/15-20261012-195021-lane-013s1-b-the-pnpm-shim-answers-which.md`.
Lane 013s1-b had ended; nothing was edited while it ran. **Nothing was pushed or merged.** None of this
addendum's work has run in the image: lane 013s1-c decides it.

**Status in one line:** the four failures had one cause, `/opt/timelike/shims/pnpm` resolving in an image with no
pnpm. The tests now ask for a real installer past the shims. The guard's own lookups already skipped the shims,
and units now hold that in place. The agent is told that a lookup succeeding is not an install.

| Task | Commit | What |
|---|---|---|
| T027 to T029 | this commit | the two helpers and the checks that use them; 007's SC-5 listing cell; the guard's shebang lookup through `resolver()`; its units; the announcement line and `shims.resolves_when_absent`; FR-43, the contract, the README sentence; this addendum; `reboot.md` |

#### Item 1: the checks look for a real installer, as the shim does

- **One helper per lane.**
  - **Units:** `tests/unit/realcmd.py`, `real_which(name)`. It returns the first executable NAME on PATH whose
    directory is not `TIMELIKE_SHIMS` (default `/opt/timelike/shims`), which is the shim's own rule.
  - **e2e:** `REAL_ON_PATH_SH` in `tests/e2e/helpers.bash`, a POSIX sh function `real_on_path NAME` that a cell
    prepends to its in-container script.
- **Units changed to use it:**
  - the skips in `test_package_guard_real.py` (`NODE`, `PNPM`), `test_package_guard_check.py` (npm, pnpm),
    `test_package_guard_tool.py` (pip) and `test_registry_standin.py` (pip, npm);
  - the setup calls in those files that ran `npm`, `pnpm` or `pip` by bare name. They now run the real one, so
    a setup step never goes through a shim's gate.
  - In the image, the three pnpm units skip again, because there is no real pnpm. The skip count there should
    return to 6.
- **007's SC-5 listing cell (declared):**
  `tests/e2e/command-not-installed-exits-127-and-prints-the-install-command.bats`, `check_listed_absent` and its
  `READ_LISTED` script.
  - "Installed" now means a real NAME past the shims.
  - A listed name that resolves only to its shim is run. The cell asserts exit 127 and its row's own line, built
    by `sc5_expected`, the same builder the other SC-5 cells use.
  - While the shipped data lists pnpm, the cell asserts that pnpm is among the shimmed names.
  - **Rehearsed on the host** with a shims directory laid out as the image's:
    - with the host's real `/usr/bin/pnpm` on PATH, the script reported it installed;
    - with only the shim, it reported `shimmed=pnpm|127`, plus `pnpm: command not found` without a handler or
      `timelike: install it yourself: npm install -g pnpm  (package manager)` with one.

#### Item 2: the guard's own installer calls skip the shims

- **Already so for the calls the findings named.** `main` builds one `resolver(env)`, which skips
  `TIMELIKE_BIN_DIRS`, `TIMELIKE_SHIMS` (or its default) and the guard's own directory. It passes that resolver
  to `classify` and `build_plan`, and every lookup goes through it:
  - `pnpm config get registry`;
  - npm's and node's paths, for npm's own npmrc files;
  - CMD itself.

  The lane's unit 4 shows the same thing. `PG.resolver(os.environ)` skipped the shims and found no pnpm, so
  "pnpm did not answer" meant the image has no pnpm, not that the guard reached the shim.
- **The one lookup outside it** was a `#!/usr/bin/env NAME` shebang, resolved to find pip's interpreter. It now
  uses the same resolver.
- **Units** (`test_package_guard_shim.py`):
  - The resolver returns None for each of the six names and node when only the shim is on PATH. With a real one
    after it, the resolver returns the real one.
  - `package-guard --dry-run --json -- pnpm add tl-left` is run with a trap in the pnpm shim's place and a real
    pnpm after it. The trap answers `http://shim.example/` and leaves a mark; the real pnpm answers the
    stand-in's registry; `npm_config_registry` points elsewhere. The guard asks the stand-in, the trap never
    runs, and neither wrong registry appears.
  - **Both tests fail when the shims' skip is removed from `_guard_dirs`** (checked by mutation, then restored).
  - `_shebang_python`'s unit covers the `env` form.

#### Item 3: the agent is told

- **The announcement**, when package-guard is installed, gains one line: "These six names always resolve:
  `command -v pnpm` succeeding does not mean pnpm is installed. `type -a pnpm` lists a real one after the check;
  an absent one exits 127 and says how to install it."
  - It covers the names, not pnpm alone, so it also holds for `uv` in an image without uv.
  - The announcement is now 37 lines of 60, and its longest line is 196 columns, under the 200-column cut.
- **`--agent-info`:** `shims.resolves_when_absent`, beside `not_reached`.
- **Units:** one assertion in `test_announce.py` and one in `test_package_guard_tool.py`.
- **FR-43** in the spec, and a paragraph in the contract.

### Group C — Addendum 2

**delegations:** `[]`.

**criteria_reestablished:** the same five citations as Addendum 1, each still a single `grep -cF` match. No
criterion cell changed in this addendum, and lane 013s1-b passed every one, but nothing of this addendum has run in
the image. So each mode stays as Addendum 1 recorded it, `unconfirmed`, until lane 013s1-c.
- `15 · "before anything is downloaded, naming the package and the registry checked _(traces to: P4)_"` — **unconfirmed.**
- `15 · "is refused with exit 4, naming the release date _(traces to: P4)_"` — **unconfirmed.**
- `15 · "already pinned in the project's lockfile proceeds without registry checks _(traces to: P2)_"` — **unconfirmed.**
- `15 · "with the confirm flag proceeds and records the override in the session event log _(traces to: P4)_"` — **unconfirmed.**
- `15 · "is refused with an explanation before any install runs _(traces to: D24)_"` — **unconfirmed** (Manual; the D24 capture follows lane 013s1-c).

**reconcile_mode:** `scoped` (the four failures, one cause, and the three items the findings ask for).

**not_verified**
- **Everything in the image:** SC-5's new cell, including whether the image's handler prints the row's line
  through the shim exactly as rehearsed; the pnpm units skipping there; the announcement line in the placed file.
- **A real pnpm installed after the shim in the image**, the case item 2 guards. It is shown only by units with a
  stand-in pnpm.
- **Everything Addendum 1 named is still not verified:** `python -m pip`, a venv's own installer, an installer
  by full path, `uvx`, `-r /dev/stdin`, and pnpm's own forms in the image.

**changed_other_features**
- **007:** the SC-5 listing cell (`check_listed_absent` and `READ_LISTED`), declared. The other SC-5 cells are
  unchanged.
- **007:** the announcement (`tools/bin/timelike`), one line, and its unit.
- **README.md:** one sentence in the guard's section, in `<mark>`. The previous update's 11 marks were cleared
  first. The generated command reference did not change (`--check`: current, 14 tools).

**process_failures_recorded:** none.

**retired_prompts_seen:** none.

#### Host lane

`make test-host`, timelike's 3.14.8 in a scratch venv, on this commit's tree (with shellcheck 0.11.0 on PATH):
- pytest tests/unit: **2242 passed, 12 skipped** (408 s). Addendum 1's run was 2239 passed and 13 skipped.
  - The two new units account for 2 more tests.
  - One test that skipped then ran this time, and I did not pin down which. Of the 9 skips I listed on this
    tree, 8 are missing tree-sitter grammars and 1 is `test_missing_commands.py`'s user-rows test. None is an
    installer check this addendum changed: on the host each of those finds a real pip, npm or pnpm and runs.
- `test_env_layer.sh` 60 of 60; `test_shell_env_hook.sh` 57 of 57; `test_command_not_found.sh` 33 of 33.

Exit 0. Other checks:
- ruff check and format: clean;
- mypy `--strict`: clean over 31 files;
- shellcheck 0.11.0: clean over the Makefile's 89 files;
- `scripts/readme_reference.py --check`: current, 14 tools;
- the deny-list: PASS before the commit (513 files, P1–P7 0/0).

#### Then

Commit everything, and report done. No commit after that until the mentor says lane 013s1-c has ended.
- **The lane:** `make test`, `make bench-images`, `make scan` with the deny-list read, and `make lint`.
- **After it:** the D24 capture, then sign-off. Merge `--no-ff` after the sign-off.
