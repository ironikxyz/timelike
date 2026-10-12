# Research — 013 package guard (prompt 15, slice 1)

Read on 2026-10-12. "Measured" means run here, on the host. "Read" means read from the named source. Nothing
here ran in the image (no Docker on this host): every image fact is the Docker lane's to confirm.

## R1 · The guard is a pass-through tool that runs the installer through `run` (seam 1, FR-1 to FR-3)

- **Decision:** `package-guard` is an `agentio` tool with `passes_exit=True`. The installer runs through
  timelike's `run --json` (003's concluding run), as `verify test -- CMD` does
  (`tools/bin/verify` `run_command`).
- **Why:**
  - **The call concludes (P2).** An install that hangs, or outlives `run`'s limit, ends in `run`'s verdict, and
    `package-guard --timeout S` passes the limit through.
  - **Contract output.** The installer's output is the body, cut by rule 3, with `run`'s log as the full
    output.
  - **One session event.** `run` writes its event inside this session's scratch (verify's `CHILD_ENV`), so
    rule 16 sees one call (conform C7).
  - **The exit passes through.** The tool's exit is the installer's (discovery revision 9; conform C6's
    `sh -c 'exit 42'` probe). A command that installs nothing runs the same way, unchecked.
- **The envelope is built here, not by `agentio.confirm_required`.** That helper appends `--yes` after the
  argv, which here would put it after `--`, so the installer would receive it. The guard builds the same
  `confirmation_required` envelope with `--yes` in the tool's position: `package-guard --yes -- CMD…`. That is
  still 001's rule 9: the original command plus `--yes`.
- **`--dry-run`:** the tool adds it itself (`configure`), because an install is not `destructive` in
  agentio's sense. Conform's rule-8 check accepts a flag the manifest lists.
- **Alternatives:**
  - Exec the installer directly with its output untouched. That is right for a front for the bare commands
    (Item 24), and wrong for a contract tool, whose stdout must be its own (rule 12).
  - Re-implement `run`'s bounding. Rejected: duplication, as verify's research R1 found.

## R2 · What the real registries return (seam 9, lore P005), read 2026-10-12

Read with `curl` from the host. This is research, not a test: no test reaches a public registry.
- **PyPI's Simple API, PEP 691 JSON**, from `GET https://pypi.org/simple/six/` with
  `Accept: application/vnd.pypi.simple.v1+json`:
  - top-level keys `files`, `meta`, `name`, `project-status`, `versions`;
  - `meta` is `{"_last-serial": …, "api-version": "1.4"}`;
  - `versions` is `["1.15.0", "1.16.0", "1.17.0", …]`;
  - each file has `core-metadata`, `data-dist-info-metadata`, `filename`, `hashes`, `provenance`,
    `requires-python`, `size`, `upload-time` and `url`, plus `yanked`;
  - `upload-time` reads `2024-12-04T17:35:28.174320Z` (PEP 700: ISO 8601, `Z`, microseconds).
  - A name PyPI does not have answers **404**.
- **npm's package document**, from `GET https://registry.npmjs.org/is-odd` with `Accept: application/json`:
  - top-level `_id`, `_rev`, `name`, `dist-tags` (`{"latest": "3.0.1"}`), `versions` and `time`, among others;
  - `time` holds `created`, `modified` and one entry per version, e.g. `"0.1.0": "2015-02-24T05:53:13.392Z"`
    (milliseconds, `Z`);
  - `versions[v].dist` has `tarball` (`<registry>/<name>/-/<name>-<v>.tgz`), `integrity` (`sha512-…`) and
    `shasum`;
  - a name npm does not have answers **404** with body `{"error":"Not found"}`;
  - a scoped name is requested as `@scope%2fname` (`GET https://registry.npmjs.org/@types%2fnode` → 200,
    `application/json`).
  - The abbreviated document (`application/vnd.npm.install-v1+json`) leaves out `time`, so the guard asks for
    the full one.
- **The stand-in serves these fields, in these formats** (FR-33), and nothing it does not need.

## R3 · Which registry each installer would use (seam 3, FR-10 to FR-12)

- **pip:**
  - **Read:** pip's own source, `pip/_internal/configuration.py` (pip 24.0 on the host).
    - `OVERRIDE_ORDER = GLOBAL, USER, SITE, ENV, ENV_VAR`.
    - User files are skipped when `PIP_CONFIG_FILE` names an existing file.
  - **Measured:** `pip config debug` lists the files:
    - global: `/etc/xdg/pip/pip.conf`, `/etc/pip.conf`;
    - site: `<sys.prefix>/pip.conf`;
    - user: `~/.pip/pip.conf`, `~/.config/pip/pip.conf`.
  - Within the merged result, a `[install]` key overrides the `[global]` one. The command line is above all of
    them.
  - The site file belongs to **the interpreter that runs pip**. The guard finds it as follows:
    - a `pip` script: its shebang's interpreter;
    - `python -m pip`: that interpreter;
    - `sys.prefix` is the venv's directory (it holds `pyvenv.cfg`) or the interpreter's prefix.
  - For the agent's own pip that is `/opt/agent/python/pip.conf` (007 FR-26).
- **npm:**
  - **Measured on the host:** `globalconfig = <prefix>/etc/npmrc`, `userconfig = ~/.npmrc`, default registry
    `https://registry.npmjs.org/`.
  - Read in 007 D-12: npm finds its global config from Node's real path, so the agent's is
    `/opt/agent/node/etc/npmrc`.
  - The builtin npmrc sits in npm's own package directory.
  - The order, highest first: command line, `npm_config_*` environment (any case), the project's `.npmrc`
    (beside the nearest `package.json`), user, global, builtin.
  - `@scope:registry` keys apply to that scope.
- **pnpm:**
  - **Measured:** `pnpm config get registry` reads the same `.npmrc` files (pnpm 11.5.1 on the host).
- **uv:** read from uv's documentation of `--index`, `--default-index`, `UV_INDEX`, `UV_DEFAULT_INDEX`,
  `UV_INDEX_URL`, `UV_EXTRA_INDEX_URL`, `[[tool.uv.index]]` and `uv.toml` (user, system).
  - The index strategy is `first-index`: the first index that has the name wins.
  - **Not measured:** uv is not on this host. The image's uv answers in the lane.

## R4 · Versions: PEP 440 and npm semver, stdlib only (FR-15, FR-19, FR-24)

- No packaging library is in timelike's interpreter, and the stack is stdlib-first (H5), so both orderings are
  implemented in the tool.
- **PEP 440:**
  - parsing epoch, release, pre, post, dev and local, with the spec's ordering;
  - specifiers `==` (with `.*`), `!=`, `<`, `<=`, `>`, `>=`, `~=` and `===`;
  - pre-releases excluded unless asked for, as pip does.

  A version string that does not parse is skipped. If none parse, the result is `unreadable`.
- **npm semver (node-semver's grammar):**
  - versions with pre-release tags;
  - ranges with `||`, hyphen ranges, x-ranges, `~`, `^`, comparators and `*`/`""`;
  - pre-release versions admitted only by a comparator on the same `major.minor.patch`, as node-semver does.

  A range that does not parse is `unreadable` (FR-9).
- Units cover each operator against tables written from the two specifications' own examples.

## R5 · Lockfiles (seam 6, FR-23 to FR-27)

- **`uv.lock`** (TOML, `tomllib`): `[[package]]` with `name`, `version`, `source`. The project's own entry
  (`source = { virtual | editable }`) is not a pin of a registry package.
- **`pylock.toml`** (PEP 751): `[[packages]]` with `name`, `version`.
- **A hashed requirements file:** a requirement line with `==` **and** a `--hash` option (pip-compile and
  `uv pip compile --generate-hashes` write exactly this).
- **`package-lock.json` / `npm-shrinkwrap.json`:**
  - v2 and v3: `packages["node_modules/<name>"].version`, top level only (a nested copy is a dependency's);
  - v1: `dependencies[<name>].version`.
- **`pnpm-lock.yaml`:**
  - There is no YAML parser in stdlib. A line reader takes the keys under `packages:` (`name@version:`,
    quoted when scoped) and the `importers` entries' `version:`.
  - Anything it cannot read makes the file unreadable (FR-27), never a pass.
  - Units read lockfiles the host's own `npm` and `pnpm` write against the stand-in. uv's are read in the
    image's e2e.

## R6 · The stand-in (seam 9, FR-33, D-10)

- **What it is:** `tests/fixtures/registry-standin.py`, stdlib `http.server` (`ThreadingHTTPServer`).
- **Its catalog:** given in a JSON file. At start it builds:
  - the wheels, with stdlib `zipfile`: `METADATA`, `WHEEL`, `RECORD` with real hashes, as 007's SC-6 cell builds
    one;
  - the npm tarballs, with stdlib `tarfile`: `package/package.json`, with `integrity` computed.
- **Upload times** are given per release as an offset from now, so "one day old" is one day old when the
  installer asks.
- **Faults on request** (per package): a delay, a 5xx, or a dropped connection.
- **The log:** one JSON line per request (method, path, user agent, status), which the cells read.
- **Where it runs:**
  - in the e2e cells, inside the agent container on `127.0.0.1`, started by the cell with timelike's
    interpreter;
  - on the host, in the units, on a free port.
- **Plain HTTP on loopback:**
  - pip treats loopback as a secure origin, so it needs no `--trusted-host`;
  - npm and uv take an `http://` registry.

## R7 · The guard's user agent (FR-26, FR-33)

Every lookup sends `User-Agent: timelike-package-guard/<version>`. The stand-in's log tells the guard's
requests apart from the installer's by it. "Made no registry check" is then "no line with that agent", read
from the log (lore P004).

## R8 · The time limit and the lookups (FR-16, FR-17)

- **The lookups:** stdlib `urllib.request` under `TIMELIKE_PACKAGE_TIMEOUT` (default 10 s), run in a thread pool
  of at most 8.
- **The whole check** has one deadline. A lookup still running at the deadline counts as a timeout.
- **What each failure is reported as:**
  - DNS: `URLError` with `gaierror`;
  - refused: `ConnectionRefusedError`;
  - TLS: `ssl.SSLError`;
  - denied: HTTP 401, 403 and 407;
  - server: HTTP 5xx;
  - unreadable: a body that does not parse.
- **The body cap:** 64 MiB. Some npm documents are tens of MiB, and the cap holds memory to a known bound.
- **Default 10 s:** below `run`'s 100 s, so a hung registry still leaves room for the install itself to report.
  It is in the manifest.
- **The added time:** measured once the tool exists (see Measurements).

## R9 · The override record and the event (seam 7, D-9)

- **Read:** `001…/contracts/event.schema.json` has `additionalProperties: false`, and `ref` is
  `{log: string} | {snapshot: integer}`.
- **The record:** the guard writes `override-<time>-<pid>.json` in the session scratch, and sets
  `ref: {"log": <path>}` through `Tool(event_ref=("log", "override_record"))`.
- **Without an override:** the ref is `run`'s log, as `verify` points at it.
- **Raised in Item 24:** the alternative of an optional `override` object in the event.

## R10 · Item 24: how the bare commands reach the guard (seam 1)

Analysed for the FOR-MENTOR item; nothing here is built.

- **The PATH, read in the Dockerfile § 7:**
  `/opt/timelike/bin:/home/agent/.local/bin:/usr/local/sbin:/usr/local/bin:…`.
- **`~/.local/bin` is ahead of `/usr/local/bin`.** So a wrapper at `/usr/local/bin` (the send's (b)) is shadowed
  the moment the agent runs `pip install --user pip` or `npm i -g npm`/`pnpm`. That is exactly how pnpm would
  arrive (seam 2).
- **`/opt/timelike/bin` is conform's directory.** `timelike-conform` checks every executable in it, so a
  `pip` there would have to be a timelike tool.
- **An activated venv** prepends its `bin` to PATH, so its `pip` shadows any PATH wrapper. A function is
  found before PATH.
- **`python -m pip`** never looks up `pip` on PATH. Only a `python` front, or the interpreter itself (a
  `sitecustomize` reading `sys.orig_argv`), sees it.
- **`type -a`** shows, for each form:
  - a function: `pip is a function`, then its body, then each PATH entry;
  - a PATH wrapper: the wrapper's path first.

  These were measured with bash 5.2 on the host, with a function and a decoy directory.

## Measurements

Filled in by T-measure once the tool exists (host, the stand-in on loopback, timelike's 3.14.8 interpreter).
