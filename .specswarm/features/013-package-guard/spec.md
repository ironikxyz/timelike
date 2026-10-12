---
parent_branch: master
feature_number: "013"
status: In Progress
created_at: 2026-10-12T00:20:29+00:00
source_prompt: plan/.discover/prompts/15-package-guard.md
source_send: bridge/sends/15-rev2-20261012-001145.md
prompt_revision: 2
discovery_revision: 15
audited_against: [2]
slice: 1
---

# Feature: Package guard (prompt 15, slice 1: natural)

## Overview

Agents install packages by name, and some of those names were invented by the model that suggested them.
About 5–6% of frontier-model package suggestions name nothing, and 43% of those recur deterministically, so
anyone can register them (pre-mortem (b), G10). A name registered for that purpose is usually days old. An
install pulls code from outside the environment and usually runs it (P4).

The **package guard** checks each package an install names **before the installer starts**:

- **Does it exist** in the registry the install would use? A name the registry says it does not have is
  refused, naming the package and the registry.
- **Is it old enough?** A package whose newest release (or the release named) is younger than a minimum age
  is refused, naming the release date the registry gives.
- **Is it already pinned** in the project's lockfile? Then it passes, and no registry is asked.

A refusal is 001's exit-4 confirmation envelope (rule 9). Its `confirm` command proceeds past the refusal and
records the override in the session's event log.

Slice 1 covers Python (`pip`, `uv`) and Node (`npm`, `pnpm`), with the common failures: an unreachable or
slow registry, a typo, names carrying versions or extras, several names in one command, a requirements file,
and a project without a lockfile. The caching proxy under Adele is slice 2's.

**What this cycle builds, and what waits on FOR-MENTOR Item 24.** The checks, the registry lookups, the
lockfile reading, the verdict, the confirm-and-record path and their tests are built here. They are built
as one timelike tool, `package-guard`, which any agent or script can call. **How the agent's own `pip install`
reaches that tool is held** (seam 1). Every option for it either puts timelike in front of a standard command
name, or changes the image beyond timelike's own files. Both are things the send says to raise first. Until
Item 24 is answered, the guard is reached only through `package-guard` itself. Five criteria say "installing
a package", and their tests run the real installers through `package-guard`; the cells that run the
installer by its bare name are written once the ruling says how.

## The seams (send), decided or raised

| # | Seam | Decided here | Raised in Item 24 |
|---|---|---|---|
| 1 | How the guard sees an install | The guard is one tool, `package-guard -- CMD…` (FR-1). | Which of (a) functions, (b) wrappers, (c) runtime configuration puts it in front of the bare commands. This includes `python -m pip`, an activated venv, and the 007 test that pins the seven links. |
| 2 | Which commands are installs | The forms (FR-5 to FR-9), including `npx`, `uvx` and `npm init`/`create` as installs, and `-r` files read | Adding pnpm to the image |
| 3 | Which registry | The configured registry, read the way the installer reads it (FR-10 to FR-13); extra indexes (D-6) | — |
| 4 | Absent vs unreachable | Unreachable refuses, naming what failed and from where (FR-16 to FR-18); every lookup is bounded | — |
| 5 | The minimum age | 2 days, `TIMELIKE_PACKAGE_MIN_AGE_DAYS`; newest, or the named release (FR-19 to FR-22) | — |
| 6 | Pinned in the lockfile | Which files count, the root, a different version (FR-23 to FR-27) | — |
| 7 | Confirm and record | The confirm goes through the tool (`package-guard --yes -- CMD…`), so no flag reaches the installer. The record is built without changing 001's event schema (FR-28 to FR-32). | The alternative: an optional `override` field in 001's session event (a contract change). |
| 8 | Adele | Lookups go out the way the install does. Nothing claims Adele enforces registry access (FR-36). | — (not read as requiring Adele now) |
| 9 | The registry stand-in | timelike's own server, run inside the agent container during a cell, from the tests' files (D-10) | — (no third-party image; no compose service) |

## User Scenarios

### Actors

- **The agent** (primary): installs dependencies, by name, often names a model suggested.
- **The operator**: sets the minimum age and the registries, and reads the overrides afterwards.

### Scenario 1: a name the registry does not have (criterion 1; D24)

The agent runs `package-guard -- pip install requests-oauth2-helperz`. The guard asks the configured index,
which answers 404. The guard exits 4 with a `confirmation_required` envelope whose plan names the package,
the registry URL and the answer ("not found: HTTP 404"). `pip` is never started, so nothing is downloaded:
the registry's log holds no file request, and `site-packages` is unchanged.

### Scenario 2: a package released yesterday (criterion 2)

The newest release of `fresh-pkg` was uploaded one day ago, and the minimum age is 2 days. The guard exits 4
naming the release, its upload date as the registry gives it, the minimum age and its variable. When an older
release passes, the plan names it as the one to pin (`fresh-pkg==1.0.0`). Installing that named release
passes, because its own age is what is checked.

### Scenario 3: everything already pinned (criterion 3)

The project's `uv.lock` (or `package-lock.json`, `pnpm-lock.yaml`, `pylock.toml`, or a hashed requirements file
the command reads) pins every package the install names. The guard makes **no registry request**, which the
stand-in's log shows, and the installer runs.

### Scenario 4: proceeding past a refusal (criterion 4)

The agent runs the envelope's `confirm` command, `package-guard --yes -- pip install fresh-pkg`. The guard
checks again so it can name what it overrides, writes the override record (package, ecosystem, registry,
reason, session), and runs the installer. The tool's own session event points at the record. The installer's
exit is the tool's exit.

### Scenario 5: the registry does not answer

The registry times out, refuses the connection, is denied, or answers 5xx. The guard exits 4, saying the
registry was **unreachable from this container**, with what failed and the time limit. It never says the
package does not exist. `--yes` proceeds, and the override names "registry unreachable" as its reason.

### Scenario 6: a mixed command

`package-guard -- npm install left-pad@1.3.0 lodahs express`. `left-pad` and `express` pass; `lodahs` is not in
the registry. The whole command is refused (the installer runs all or nothing), and the plan lists each name
with its result.

### Edge cases

- A typo'd name is an absent name (scenario 1). The guard suggests nothing: a "did you mean" would be a name
  the guard invented.
- Versions and extras: `pkg==1.2`, `pkg>=1,<2`, `pkg[extra]`, `pkg; python_version<"3.13"`, `pkg@1.2`,
  `pkg@^1`, `pkg@latest`, `@scope/pkg`, `@scope/pkg@2`.
- A requirements file (`-r`, nested `-r`), including a missing one (refused: the guard cannot see what it
  installs).
- A project without a lockfile: every name is checked.
- Local paths, archives and directories (`pip install ./dist/x.whl`, `npm install ../lib`, `pip install -e .`):
  nothing comes from a registry, so there is nothing to check (FR-8).
- URLs and VCS references (`git+https://…`, `https://…/x.tgz`, `github:user/repo`) reach outside, but no
  registry can vouch for them: refused as unchecked, with the confirm (FR-8).
- A command the guard cannot read (an unknown option that might take a value, for example) is refused,
  saying what it could not read. It is never passed silently (FR-9).
- Commands that install nothing (`pip list`, `pip show`, `npm run`, `npm test`, `uv run` without `--with`)
  are run unchanged, with no lookup.

## Functional Requirements

### The tool (FR-1 to FR-4)

- **FR-1 · `package-guard [--yes] [--dry-run] -- CMD [ARG…]`.** A timelike tool on the agent's PATH, on
  `agentio`.
  - It reads `CMD [ARG…]` as an install command, checks each package it names, and runs the command only
    when every check passes or `--yes` is given.
  - The command's exit is the tool's exit (pass-through, discovery revision 9), so a passing install leaves
    `$?` as the installer left it.
  - `--dry-run` checks and reports and runs nothing.
  - The options before `--` are the tool's own: none of them reaches the installer.
- **FR-2 · The installer is resolved explicitly (lore P002).** `CMD` is looked up on `PATH` with timelike's
  own directories (`TIMELIKE_BIN_DIRS`) removed, so the guard never runs itself. The guard's own helpers are
  found from its own location, never from `PATH`.
- **FR-3 · Output.**
  - A pass: the installer's own output, untouched (its stdout and stderr are the tool's), then the contract's
    header and verdict on stdout: the packages checked, the registries asked, and the installer's exit.
  - A refusal: the envelope only (FR-28).
  - `--dry-run`: the header, a verdict (`would proceed` or `would be refused: …`), and one line per package.
- **FR-4 · Announced and self-describing (P3, lore P003).** The tool's manifest (`--agent-info`) lists:
  - the forms it reads;
  - the minimum age, its variable and its current value;
  - the lookup time limit and its variable;
  - the lockfiles it reads;
  - its version.

  The announcement gets the tool from its manifest (007).

### Which commands are installs (FR-5 to FR-9; seam 2)

- **FR-5 · Python forms.**
  - `pip install`, `pip3 install`, `pipX.Y install`, `python -m pip install`, `python3 -m pip install`, and a
    path to any of these.
  - `uv pip install`, `uv add`, `uv tool install`, `uv sync`, `uv pip sync`.
  - `uv run --with PKG` and `uvx PKG` / `uv tool run PKG`: these fetch and run a package, which is P4's own
    case, so they are installs.
- **FR-6 · Node forms.**
  - `npm install` and every alias npm accepts for it (`i`, `in`, `add`, `isntall` and the rest), `npm ci`.
  - `npx PKG`, `npm exec PKG`, `npm x PKG`, and `npm init NAME` / `npm create NAME`, which fetch and run
    `create-NAME`.
  - `pnpm add`, `pnpm install`/`i`, `pnpm dlx PKG`, `pnpm create NAME`.
- **FR-7 · Names come from the command line, and from the files it reads.**
  - pip's `-r FILE` is read for names, recursively.
  - `-c FILE` constrains versions and names nothing.
  - A bare `npm install` / `pnpm install` / `uv sync` names the manifest's dependencies (`package.json`'s
    dependency sections; `pyproject.toml`'s `[project] dependencies` and `[dependency-groups]`). FR-24
    passes those already in the lockfile without a lookup.
- **FR-8 · What is not a registry name.**
  - Local paths, archives and directories are not checked: nothing comes from a registry.
  - URLs and VCS references are refused as `unchecked source`, because no registry vouches for them, with the
    confirm to proceed.
  - `--no-index` (pip, uv) with `--find-links`/`-f` installs from local directories only: no registry, nothing
    to check.
- **FR-9 · Never passed silently.** A command the guard cannot read is refused (exit 4). Examples:
  - an option it does not know, where the next word could be its value or a package;
  - a requirements file that does not exist;
  - a `package.json` that does not parse.

  The plan says what could not be read. A form not listed in FR-5 and FR-6 (for example `pip download`,
  `npm update`) installs no new name and is run unchanged.

### Which registry (FR-10 to FR-13; seam 3, P001)

- **FR-10 · pip.** In pip's own order of precedence (highest first):
  - the command's `--index-url`/`-i`, `--extra-index-url`, `--no-index`;
  - `PIP_INDEX_URL`, `PIP_EXTRA_INDEX_URL`, `PIP_NO_INDEX`;
  - pip's configuration files: `PIP_CONFIG_FILE`; the site file of the interpreter that runs pip (the venv's
    own, or `/opt/agent/python/pip.conf`); the user files; then the global files. `[install]` overrides
    `[global]`.
  - Otherwise `https://pypi.org/simple`.
- **FR-11 · uv.**
  - Highest first: `--index`, `--default-index`, `--index-url`, `--extra-index-url`; `UV_INDEX`,
    `UV_DEFAULT_INDEX`, `UV_INDEX_URL`, `UV_EXTRA_INDEX_URL`; the project's `[[tool.uv.index]]`; `uv.toml`
    (user, then system).
  - Otherwise `https://pypi.org/simple`.
  - In uv's first-index order.
- **FR-12 · npm and pnpm.**
  - Highest first: `--registry`; `npm_config_registry` (any case); the project's `.npmrc`; the user's
    (`npm_config_userconfig`, else `~/.npmrc`); the global npmrc of the Node that runs it; npm's builtin
    npmrc.
  - Otherwise `https://registry.npmjs.org/`.
  - A scope's `@scope:registry` applies to that scope's packages.
  - `${VAR}` in a value expands as npm expands it.
- **FR-13 · Named in every result.** Each package's line names the registry URL it was checked against.
  Credentials in a URL are redacted (rule 15). The guard sends no credentials of its own.

### What is checked (FR-14 to FR-22; seams 4 and 5)

- **FR-14 · Exists.** The guard asks each index for the package:
  - Python: the Simple API at `<index>/<normalized-name>/`, asking for PEP 691 JSON. It reads HTML (PEP 503)
    where that is all the index serves.
  - npm: the package document at `<registry>/<name>` (a scoped name escaped as npm escapes it).

  A 404 (or 410) is **absent**. A 200 that lists no installable release is absent too, and says so.
- **FR-15 · Every check is the one the installer would make.** Names are normalized as the ecosystem does
  (PEP 503 for Python; npm names as written). Python releases follow pip's choice:
  - pre-releases are excluded unless `--pre` is given or no final release exists;
  - yanked files are excluded.
- **FR-16 · Unreachable is not absent (P001).** None of the following is ever reported as absent:
  - a timeout, a refused connection, a DNS failure, a TLS failure;
  - a 401, 403 or 407 (denied);
  - a 5xx;
  - a 200 that does not parse.

  Each refuses (exit 4, fail closed), naming what failed, the registry, and that it was checked **from this
  container** (where the guard runs). The confirm proceeds past it (D-5).
- **FR-17 · Bounded (P2).**
  - Every lookup runs under `TIMELIKE_PACKAGE_TIMEOUT` seconds (default 10), and the lookups of one command
    run concurrently. The whole check is bounded by about one time limit, not one per package.
  - A response larger than 64 MiB is cut off and counts as unreadable.
- **FR-18 · Measured (P2).** What the guard adds to an install whose names all pass is measured on the host,
  against the stand-in, and recorded (research). No claim about the agent's speed is made from it (P6).
- **FR-19 · Old enough.** The minimum age is `TIMELIKE_PACKAGE_MIN_AGE_DAYS` (default **2**; decimals allowed;
  `0` turns the age check off).
  - **With no version named**, the release checked is the **newest** one the installer would pick:
    - Python: the highest final release that is not yanked;
    - npm and pnpm: `dist-tags.latest`.
  - **With a version or a range named**, it is the release that version or range selects: the named release,
    or the highest release the range admits.
  - A dist-tag (`@next`) selects that tag's release.
- **FR-20 · The release date is the registry's own.**
  - Python: the earliest `upload-time` (PEP 700) of the release's files.
  - npm: `time[<version>]` in the package document.

  The refusal names that date as an ISO date and the release's age in days.
- **FR-21 · No date, no pass.** An index that gives no upload times (an HTML-only index, or a document without
  `time`) cannot show age. It refuses as `age unknown`, naming the registry and the missing field, with the
  confirm. It never passes as old enough.
- **FR-22 · The way through, named.** An age refusal names the newest release that is old enough, if one
  exists, as the install command to pin it with.

### Pinned in the lockfile (FR-23 to FR-27; seam 6)

- **FR-23 · The files that count.**
  - Python: `uv.lock`, `pylock.toml` (PEP 751), and a requirements file the command reads with `-r` that
    carries `==` pins **with** `--hash`.
    - A requirements file with `==` and no hashes is **not** a lockfile: an agent writes such a file in the
      same breath as the name it invented.
  - Node: `package-lock.json`, `npm-shrinkwrap.json`, `pnpm-lock.yaml`.
- **FR-24 · Pinned means named there, at a version that satisfies the install.** A package passes without a
  lookup when the project's lockfile holds it, and:
  - no version was named; or
  - the named version or range admits the locked version.

  A different version is not pinned. That name is checked like any other (D-8).
- **FR-25 · The project root.**
  - Node: the nearest ancestor of the working directory (or `--prefix`/`-C`/`--dir`) holding
    `package.json`, as npm finds it. Its lockfile sits beside it.
  - Python: the nearest ancestor holding `pyproject.toml` (or `uv`'s `--project`/`--directory`).
    - `pylock.toml` sits beside it.
    - `uv.lock` sits beside it or at the nearest ancestor holding one, below the repository's root (a uv
      workspace).
  - With no project found, only a hashed requirements file read by the command can pin anything.
- **FR-26 · Lockfile-only installs make no lookup.** `npm ci`, `pnpm install --frozen-lockfile`,
  `uv sync --locked`/`--frozen` and `uv pip sync` on a hashed file install exactly what the lockfile says.
  The guard makes no registry request for them. The stand-in's log proves it, not a message (lore P004).
- **FR-27 · A lockfile that does not parse** is not a pin. Its names are checked, and the result says the
  file could not be read.

### The confirm and the override record (FR-28 to FR-32; seam 7)

- **FR-28 · The refusal is 001's `confirmation_required` envelope.** It is JSON on stdout, exit 4:
  - `tool` is `package-guard`;
  - `target` is the project root (or the working directory);
  - `scope` is `install <ecosystem>`;
  - `plan` has one item per package: name, version named, registry, and the result with its reason (absent;
    too new, with the date and the minimum age; unreachable, and how; age unknown; unchecked source;
    unreadable). It ends with what proceeding would run;
  - `confirm` is the command plus `--yes`, in the tool's own position: `package-guard --yes -- CMD…`.

  It is not `grant_required`: no grant exists for this yet. The installer never starts (lore P004).
- **FR-29 · `--yes` proceeds.** With `--yes` the guard checks again, so it can name what it overrides, then
  runs the command whatever the checks say. Its bound is FR-17's.
- **FR-30 · The override record.** When `--yes` overrides at least one refusal, the guard writes one record
  to the session scratch (rule 10). The record:
  - names, per overridden package: the package, ecosystem, registry, the reason it was refused, and the
    session;
  - names the command and the time.

  The tool's own session event (rule 16) points at it, `ref: {"log": <record path>}`, as `run`'s does at its
  log. **001's event schema is unchanged** (D-9). Item 24 asks whether the mentor wants the fields inside
  the event instead.
- **FR-31 · Nothing overridden, nothing recorded.** `--yes` on a command whose checks all pass runs it, and
  writes no override record.
- **FR-32 · 009's command record.** The agent's shell command (`package-guard --yes -- pip install x`) is in
  009's shell-command record with its exit. The tool's event is linked to it by `ppid`, as every tool's is.
  The journal shows both.

### The registry stand-in and the tests (FR-33 to FR-35; seam 9, lore P004, P005)

- **FR-33 · A registry stand-in from timelike's own files** (`tests/fixtures/registry-standin.py`, stdlib
  only). It serves:
  - PyPI's Simple API, in PEP 691 JSON (api-version 1.4) and PEP 503 HTML, with `files`, `versions`,
    `upload-time` and `yanked`, plus the wheel files;
  - npm's package document (`name`, `dist-tags`, `versions[v].dist.tarball`/`.integrity`, and `time` with
    `created`, `modified` and each version), plus the tarballs.

  Its fields and date formats are those the real registries returned on 2026-10-12, cited in research R2.
  - It serves packages that exist, names that do not, and a package whose newest release is one day old.
  - It answers slowly, or with 5xx, on request.
  - It **records every request** (path, method, user agent), so a cell reads which requests were the
    guard's (its user agent names it) and whether any file or tarball was fetched.
- **FR-34 · The real installers.** The cells run the image's real `pip`, `uv` and `npm` against the stand-in,
  through `package-guard`.
  - "Installed" and "nothing downloaded" are read from `site-packages`, `node_modules` and the stand-in's
    log, never from the guard's message (P004).
  - pnpm is not in the image. Its forms are tested on the host, against the host's pnpm and the stand-in, and
    not in the image until Item 24 says otherwise.
- **FR-35 · A decoy on PATH** (lore P002). A `python3` and a `package-guard` earlier on `PATH` are never
  what the guard runs itself with.

### Adele (FR-36; seam 8)

- **FR-36 · No claim about Adele.**
  - Lookups go out the way the install does: the agent keeps compose's default network with egress (004
    D-2).
  - Nothing the guard prints, announces or documents says registry access is a grant under Adele. The
    README says it is not yet.
  - The standing grant is 12 slice 2's, recorded in `not_verified`.

## Success Criteria

Each Automated criterion is one e2e file in the image, named after its distinguishing text, plus host units.

- **SC-1** · *"Installing a package name absent from its registry is refused with exit 4 before anything is
  downloaded, naming the package and the registry checked"*
  - **Shown by:** pip, `uv pip install` and npm through `package-guard`.
  - **Each exits:** 4 with the envelope naming the package and the stand-in's URL.
  - **The stand-in's log:** no file or tarball request.
  - **On disk:** no new file under `site-packages` or `node_modules`.
- **SC-2** · *"Installing a package whose newest release is younger than the configured minimum age is
  refused with exit 4, naming the release date"*
  - **Shown by:** the stand-in's one-day-old newest release, through pip and npm: exit 4, the stand-in's date
    in the plan.
  - **Also shown:** the named older release passes and installs.
  - **Also shown:** `TIMELIKE_PACKAGE_MIN_AGE_DAYS=0` passes.
- **SC-3** · *"Installing packages already pinned in the project's lockfile proceeds without registry checks"*
  - **Shown by:** a project with `uv.lock` (and one with `package-lock.json`) pinning the names.
  - **The stand-in's log:** no request with the guard's user agent.
  - **The install:** completes, with the installer's own exit 0.
  - **Also shown:** `npm ci` and `uv sync --locked` make no guard request either.
- **SC-4** · *"Re-running a refused install with the confirm flag proceeds and records the override in the
  session event log"*
  - **Shown by:** running the refusal's own `confirm` string, which exits with the installer's 0 and installs
    the package.
  - **The session's `events.jsonl`:** holds `package-guard`'s event, with `ref.log` naming a record.
  - **The record:** names the package, the ecosystem, the registry, the reason and the session.
- **SC-5** · D24 *(Manual)*: the agent tries to install a package that does not exist and is refused with an
  explanation before any install runs. **Unconfirmed** this cycle. It also needs the Item 24 ruling: the
  demo is the agent's own install, not one it routed through `package-guard` because it was told to.
- **Measured:**
  - the guard's added time on a passing install of one, and of five, packages (FR-18);
  - lookups bounded by the time limit when the registry hangs (FR-17).

## Key Entities

- **Install request**:
  - the ecosystem (`pypi` | `npm`);
  - the installer argv;
  - the working directory and project root;
  - the registries (primary first);
  - the package requests;
  - whether it is lockfile-only.
- **Package request**:
  - the name as written and normalized;
  - the version or range named, or a dist-tag;
  - the source (registry | local | url);
  - where it came from (command line, `-r` file, manifest).
- **Check result**, per package:
  - `pinned` (lockfile, version);
  - `ok` (release, date, registry);
  - `absent`;
  - `too-new` (release, date, minimum age, the newest old-enough release);
  - `unreachable` (registry, how, from where);
  - `age-unknown`;
  - `unchecked-source`;
  - `unreadable`.
- **Override record**:
  - the time, session, agent and command;
  - the overridden packages, each with its package, ecosystem, registry and reason;
  - the installer's exit.

## Decisions

- **D-1 · One tool, reached explicitly until Item 24** *(Item 24 answered: the bare commands reach it
  through the shims, FR-37 to FR-40 below).* `package-guard -- CMD` is buildable, testable and
  announceable now. It changes no standard command and no other feature's contract. Whatever Item 24 rules
  will route the bare commands into it, so nothing built here is thrown away.
- **D-2 · The confirm goes through the tool, not a flag on the installer.**
  - `--yes` in the tool's position never reaches pip or npm, and it keeps 001's rule 9 form ("the original
    command plus `--yes`") exact.
  - A flag on the installer's own line would collide: `npx --yes PKG` is a common non-interactive habit, and a
    guard that read it as an override would wave through every such call.
- **D-3 · All or nothing.** One failing name refuses the whole command, because the installer installs all or
  nothing. The plan lists every name, so the agent can drop the bad one.
- **D-4 · No "did you mean".** A suggested name would be the guard's own invention. The plan says the name
  is not in that registry, and stops.
- **D-5 · Unreachable fails closed.** P4 makes reaching out the exception, and a guard that passes when it
  cannot see would pass every install in a network outage, the time it is least watched. The confirm is the
  way through, and the override names "registry unreachable". This is the send's natural reading.
- **D-6 · Extra indexes.** Every configured index is asked:
  - a name absent from all of them is absent;
  - the release checked for age is the one the installer would take (pip: the highest across all indexes;
    uv: the first index that has the name).

  A name present on more than one index (dependency confusion's shape) is **named** in the result line but not
  refused in slice 1. The seam stays open and is recorded in `not_verified`.
- **D-7 · The minimum age is 2 days.**
  - Malicious uploads are typically found and removed within hours to a few days. A week would refuse every
    install of a package that releases often (some release daily).
  - The criterion's "newest release" means an unpinned install of such a package is refused until it is
    pinned. The plan names the old-enough release to pin, so the way through costs one command (FR-22).
  - `0` turns the check off.
- **D-8 · A different version is not pinned.** The lockfile vouches for the release it holds, not for the name.
- **D-9 · The override record is a file the event points at** *(Item 24 Q4: the override is now also in the
  event line itself, FR-41; the file stays, pointed at by `ref`).* 001's event schema is closed
  (`additionalProperties: false`), and `ref.log` is its existing pointer. Fields inside the event would change
  001's contract, which the send says to raise. Item 24 offers it.
- **D-10 · The stand-in runs inside the agent container, started by the cell.**
  - It runs on the container's loopback, from the tests' own files, with timelike's interpreter. No compose
    service and no image change is needed, and no third-party registry image is used.
  - pip, uv and npm all accept plain HTTP on loopback.
  - The cell stops it and removes its files.
- **D-11 · The guard sends no credentials.** A private registry that needs them answers 401/403, which is
  "denied" (FR-16), and the confirm proceeds. Reading the agent's tokens to make lookups is not slice 1's.

## Out of scope (slice 1)

- The caching proxy, and the egress policy under Adele (slice 2's criterion).
- Standing grants for registries (12 slice 2).
- Incident replays and enforcement (slice 2).
- Package managers outside v1: yarn, bun, poetry, pipx, conda.
- `pip download`, `pip wheel`, `npm update`, `npm pack`: no new name is installed.
- Dependencies of the named packages: the installer resolves them from the registry. Only what the command
  names (or reads from a file or manifest) is checked.

## Assumptions

- The agent's registries answer the Simple API (PEP 691/503) and the npm registry API, as PyPI, npm and the
  common private registries do.
- The host has pip and npm, and pnpm, for host tests. The image has pip, uv and npm, and no pnpm (007 D-12).
- The session scratch and `events.jsonl` are 001's, and `agentio` writes the event (rule 16).

## Item 24's ruling, built (Cycle 1 addendum, 2026-10-12)

The ruling is `bridge/feedback/15-20261012-015246-item-24-bare-installs-reach-the-guard.md` (2026-10-12T01:52:46Z).
These requirements are added by it; nothing above is withdrawn except where D-1 and D-9 say so.

- **FR-37 · The shims (Q1 (b′)).** `/opt/timelike/shims` holds `pip`, `pip3`, `uv`, `npm`, `npx` and `pnpm`, each a
  link to one POSIX sh wrapper, `/opt/timelike/libexec/install-shim`. The directory is first on PATH in the image's
  `ENV` and in `/etc/profile.d/00-timelike-path.sh` (001's files, declared). The vanilla image gets nothing (P6).
- **FR-38 · Pass-through is free (condition 1).** A command with no install word for its installer is `exec`'d at
  once: no fork, no Python. Its added time is measured and reported.
- **FR-39 · The real command is untouched (condition 2).** The real installer is the first of its name on PATH
  that is not the shim (P002; tested with a decoy alias of the shims directory and a second link). For anything
  that passes, the shim `exec`s it, so its output, stdin, environment and exit are its own. The shim is sh, not
  bash, so `BASH_ENV`'s secret strip never changes the installer's environment. No installer found: bash's
  command-not-found handler answers, exit 127, as without the shim.
- **FR-40 · `--gate`.** An install asks `package-guard --gate -- NAME ARG…` (stdin closed). The gate checks and
  runs nothing: exit 0 lets the shim exec the installer; a refusal is the envelope, exit 4, printed by the shim,
  whose `confirm` is the tool form exactly (Q2). The gaps are named in the announcement, in `--agent-info`
  (`shims.not_reached`) and in `not_verified` (condition 3): `python -m pip`, an activated venv's own `pip`, and
  an installer by its full path such as `/usr/local/bin/pip`. Slice 2's proxy closes them.
- **FR-41 · The override in the event line (Q4).** 001's `event.schema.json` gains an optional `override` object
  (ecosystem; packages, each with name, the version named, registry, reason, release date and detail; the
  command), set through `agentio`'s `Context.event_override`. Every existing event stays valid.
- **FR-42 · The criteria's cells run the installers by their bare names (condition 7)**, in `bash -c`, `bash -lc`,
  `bash -ic` and a bash script. pip makes the user install the image's `pip.conf` asks for, into the cell's own
  `HOME`; no cell passes `--target` or `--prefix` to pip (lane 013s1-a2, item 1). pnpm is installed in its cell
  into `~/.local/bin` from the stand-in, as the agent would; the package is the stand-in's `pnpm`, a script, so
  pnpm's own forms stay the host's units (Q3).

