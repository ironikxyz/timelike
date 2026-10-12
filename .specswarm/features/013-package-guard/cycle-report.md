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
