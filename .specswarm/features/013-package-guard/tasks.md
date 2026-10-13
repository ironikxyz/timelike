# Tasks — 013 Package guard (prompt 15, slice 1)

<!-- Tech Stack Validation: PASSED -->
<!-- Validated against: .specswarm/tech-stack.md -->
<!-- No prohibited technologies found -->
<!-- 0 unapproved technologies require runtime validation -->

**Spec:** `spec.md` · **Plan:** `plan.md` · **Contract:** `contracts/package-guard-cli.md`
**Send:** `bridge/sends/15-rev2-20261012-001145.md`

**Held for FOR-MENTOR Item 24, and not in this list:** the bare-command route (wrappers or functions), pnpm in
the image, and the event's `override` field. Those tasks are written once the ruling is in.

## Phase 1 — Setup

- [X] T001 The registry stand-in, `tests/fixtures/registry-standin.py`, stdlib only (FR-33, R2, R6):
  - PEP 691 JSON (api-version 1.4) and PEP 503 HTML, with the wheel files;
  - npm package documents with `time`, plus the tarballs (`integrity` computed);
  - a catalog file, with upload times given as offsets from now;
  - faults per package: a delay, a 5xx, a dropped connection;
  - a JSON-lines request log; `--port 0` writes the port to a file.

  `tests/unit/test_registry_standin.py` checks its answers against R2's field names and date formats, and that
  the host's real `pip download` and `npm pack` can fetch from it.

## Phase 2 — Foundational: reading the command (pure functions, units first)

- [X] T002 [P] Versions and ranges (R4): a PEP 440 parse, its ordering and its specifiers; npm semver versions and
  ranges. In `tools/bin/package-guard`, as module-level functions. `tests/unit/test_package_guard_versions.py`.
- [X] T003 The command parse (FR-5 to FR-9), in `tools/bin/package-guard`. Covers:
  - the pip, `python -m pip`, uv, npm, npx, `npm init`/`create` and pnpm forms;
  - names with versions, extras, markers, scopes and dist-tags;
  - `-r`/`-c` files; manifests for bare installs;
  - local, URL and VCS sources; `--no-index`;
  - lockfile-only forms; unknown options → unreadable.

  `tests/unit/test_package_guard_parse.py`.
- [X] T004 The registries (FR-10 to FR-13):
  - pip's configuration order (global, user, site of the interpreter, `PIP_CONFIG_FILE`, env, CLI;
    `[install]` over `[global]`);
  - uv's flags, env, `[[tool.uv.index]]` and `uv.toml`;
  - npm/pnpm's command line, env (any case), project, user, global (from Node's real path) and builtin npmrc,
    with `@scope:registry` and `${VAR}`;
  - credentials redacted for display.

  `tests/unit/test_package_guard_registry.py`.

## Phase 3 — The checks (SC-1, SC-2, SC-3), against the stand-in

- [X] T005 Lookups (FR-14 to FR-17, R7, R8):
  - the Simple API (JSON, then HTML) and the npm document;
  - concurrent, one deadline, the 64 MiB cap, the guard's user agent;
  - absent (404, 410, nothing installable) vs unreachable (timeout, refused, DNS, TLS, 401/403/407, 5xx,
    unparseable), each named with "from this container".

  `tests/unit/test_package_guard_check.py`.
- [X] T006 Age (FR-19 to FR-22): the release the installer would pick (newest final, not yanked; `latest`; named
  or range; dist-tag); the release date from `upload-time` or `time`; `age unknown`; the newest release old
  enough, as an install command. Same test file.
- [X] T007 Lockfiles (FR-23 to FR-27, R5): `uv.lock`, `pylock.toml`, hashed requirements, `package-lock.json` (v1
  to v3), `npm-shrinkwrap.json`, `pnpm-lock.yaml`; the project root; a version that differs; an unreadable
  file; lockfile-only forms make no lookup. Same test file.
- [X] T008 The verdict and the envelope (FR-28, contract): all or nothing; one plan line per package, with its
  registry; the two closing lines; `confirm` = `package-guard --yes -- CMD…`; no "did you mean" (D-4). Same test
  file.

## Phase 4 — The tool (SC-4), and the real installers on the host

- [X] T009 The tool's main:
  - `agentio.Tool`: `mutating`, `confirm_protocol`, `passes_exit`, `event_ref` log;
  - `--dry-run`, `--timeout`, `--yes`;
  - CMD resolved on PATH without `TIMELIKE_BIN_DIRS` (FR-2);
  - CMD run through the sibling `run --json`, with a child scratch inside the session (R1), and the result
    shown;
  - not-an-install forms run unchecked;
  - the manifest's `--agent-info` extras (forms, age, timeout, lockfiles, version).
- [X] T010 `--yes` and the override record (FR-29 to FR-31, R9): checked again; the record written before CMD and
  rewritten with its exit; `ref.log` points at it; no record when nothing is overridden.
  `tests/unit/test_package_guard_tool.py`, plus conform over the tool on the host.
- [X] T011 The real host installers through the tool against the stand-in (FR-34, lore P004, P005):
  - `pip install --target`, `npm install` and `pnpm add`;
  - absent refused, with no file request in the log and nothing on disk;
  - too new refused, while the named old release installs;
  - pinned, with no guard request (lockfiles written by the host's own npm and pnpm);
  - `--yes` installs and records;
  - a decoy `python3` and `package-guard` on PATH (FR-35).

  `tests/unit/test_package_guard_real.py`.

## Phase 5 — e2e in the image, and polish

- [X] T012 `tests/e2e/helpers.bash`: `standin_start` (copies the stand-in and a catalog into the container and
  starts it on loopback with timelike's interpreter), `standin_stop`, `standin_log`.
- [X] T013 [P] SC-1:
  `tests/e2e/installing-a-package-name-absent-from-its-registry-is-refused-with-exit-4-before-anything-is-downloaded.bats`
  — pip, `uv pip install`, npm; exit 4; the envelope's package and the stand-in's URL; no file request; nothing
  new in site-packages or node_modules; an unreachable registry is not called absent.
- [X] T014 [P] SC-2:
  `tests/e2e/installing-a-package-whose-newest-release-is-younger-than-the-minimum-age-is-refused-naming-the-release-date.bats`
  — the one-day-old newest release refused through pip and npm, naming the stand-in's date; the named older
  release installs; `TIMELIKE_PACKAGE_MIN_AGE_DAYS=0` passes.
- [X] T015 [P] SC-3:
  `tests/e2e/installing-packages-already-pinned-in-the-projects-lockfile-proceeds-without-registry-checks.bats`
  — `uv lock` and `npm install` write real lockfiles; then the guarded install, `npm ci` and `uv sync --locked`
  make no request with the guard's user agent, and the installer runs.
- [X] T016 [P] SC-4:
  `tests/e2e/re-running-a-refused-install-with-the-confirm-flag-proceeds-and-records-the-override.bats`
  — run the refusal's own `confirm`: the installer's exit and the package on disk; `events.jsonl` has the
  tool's event with `ref.log`; the record names the package, ecosystem, registry, reason and session.
- [X] T017 Polish:
  - the Makefile's `SHELLCHECK_FILES` (the four bats files);
  - `scripts/readme_reference.py --write` (the command reference);
  - the measurement (R8 Measurements: one and five passing packages; a hung registry);
  - ruff, mypy `--strict`, shellcheck;
  - the host lane.
- [X] T018 The cycle report (`.specswarm/features/013-package-guard/cycle-report.md`, Cycle 1) and `reboot.md`;
  the README status block only if all four Automated criteria are met (they are not, until Item 24: say
  why); commit everything.

**Order:**
T001 → (T002, T003) → T004 → T005 → T006 → T007 → T008 → T009 → T010 → T011 → T012 → (T013 to T016) → T017 → T018.

**MVP:** T001 to T008 plus T009: the tool refuses an absent name before the installer starts (SC-1).

## Cycle 1 addendum: Item 24's ruling and lane 013s1-a2's findings (2026-10-12)

From `bridge/feedback/15-20261012-015246-item-24-bare-installs-reach-the-guard.md` (the ruling) and
`bridge/feedback/15-20261012-034908-lane-013s1-a2-target-cells-and-a-gnutls-critical.md` (items 1 and 2).

- [X] T019 Q4: 001's `event.schema.json` gains an optional `override` object; `agentio`'s
  `Context.event_override` writes it; 001's `output-contract.md` says so; the guard sets it when `--yes`
  proceeds over a refusal (`tools/agentio/agentio.py`, `tools/bin/package-guard`).
- [X] T020 Q1 (b′): `package-guard --gate`; `TIMELIKE_SHIMS` removed from PATH when CMD is resolved; the
  manifest's `shims` block naming the gaps; the usage lines.
- [X] T021 Q1 (b′): `image/rootfs/opt/timelike/libexec/install-shim` (POSIX sh); the Dockerfile's § 5a links
  six names in `/opt/timelike/shims`; the image `ENV` PATH and `00-timelike-path.sh` put it first;
  `tests/host/test_env_layer.sh` reads the new head of PATH.
- [X] T022 The announcement's rule lines for the guard (`tools/bin/timelike`), with the minimum age read from the
  guard's manifest; a unit for them.
- [X] T023 Condition 7 and item 1: the four criterion files run the installers by their bare names (`bash -c`,
  `-lc`, `-ic`, a bash script); pip makes its user install into the cell's own `HOME` (no `--target` or
  `--prefix` to pip anywhere in 013's files); `run_bare` in `tests/e2e/helpers.bash`; Q3: a cell installs the
  stand-in's `pnpm` into `~/.local/bin` (the stand-in's npm packages may now carry a `bin`).
- [X] T024 Declared changes to other features' cells: 007's SC-6 runtimes cell (the shim first, then the
  `/usr/local/bin` link); the agent-cannot-alter list (the shim, the guard, `/opt/timelike/shims`).
- [X] T025 Item 2: CVE-2026-88647 in both baselines (`scan/baseline/timelike-agent.json`,
  `timelike-vanilla.json`), origin `git`, `review_by` unchanged, with the operator's words in the review note.
- [X] T026 Units (`test_package_guard_shim.py`; the tool's gate, override and shim-skip units); the measurement
  (R11); the contract; the README (status block, the guard's section, the PATH sentence, each marked); the
  command reference; shellcheck, ruff, mypy; the host lane; the cycle report's addendum; FOR-MENTOR Item 24
  closed; `reboot.md`; commit everything.

**Order:** T019 → T020 → T021 → T022 → T023 → T024 → T025 → T026.

### Addendum 2 — lane 013s1-b: a shim resolves when its installer is absent

- [X] T027 Item 1: the checks look for a real installer past `/opt/timelike/shims`, as the shim does — one helper
  for the units (`tests/unit/realcmd.py`, `real_which`) used by the skips and setup calls in
  `test_package_guard_real.py`, `_check.py`, `_tool.py` and `test_registry_standin.py`; one for e2e
  (`REAL_ON_PATH_SH` in `tests/e2e/helpers.bash`). 007's SC-5 listing cell (declared): installed means a real one;
  a listed name with only its shim resolves to it and, run, exits 127 with its row's line.
- [X] T028 Item 2: every installer the guard looks up or runs for itself goes through `resolver()` (the
  `#!/usr/bin/env` interpreter was the one that did not); units: the resolver skips the shims for all six names
  and node, and `package-guard --dry-run -- pnpm add` asks the real pnpm, never a trap in the shim's place.
- [X] T029 Item 3: one announcement line and `--agent-info`'s `shims.resolves_when_absent`; units; the contract,
  FR-43, the README's guard section (marked, the previous marks cleared); the host lane; the cycle report's
  Addendum 2; `reboot.md`; commit everything.

**Order:** T027 → T028 → T029.
