# Modification: Feature 001 — Agent shell baseline & output contract, slice 1 (natural)

**Status**: Active
**Created**: 2026-09-28
**Original Feature**: `.specswarm/features/001-agent-shell-baseline/spec.md`
**Impact Analysis**: `.specswarm/features/001-agent-shell-baseline/impact-analysis.md`
**Send**: `bridge/sends/01-rev2-20260928-214635.md` (prompt 01 revision 2, discovery revision 5, slice 1)
**Branch**: `modify/001-slice-1`

---

## Modification Summary

**What we're changing:** we add prompt 01's slice-1 criteria to feature 001, harden slice 0 to natural
intensity, and carry out three operator decisions.

**Why:**
- **Slice 1 is in scope.** A slice-N send covers every criterion marked `_(slice N)_` or lower.
- **Natural intensity** is "what a real user expects, including the common failures".
- **The operator decided** to print the in-image start-up figure and to close FOR-MENTOR Items 1–3.

---

## Current State

Slice 0 is merged (`39d3b74`). The environment's defaults are static: one Dockerfile `ENV` block plus
`/etc/gitconfig`, with `/etc/profile.d` restoring PATH for login shells.

**Current limitations**, which prompt this modification:
- no job-count defaults: build tools size themselves from the host's CPU count
- secret-shaped variables pass straight into the agent's shells
- the timezone and REPL mode are left at the base image's defaults
- slice-0 tests mostly cover the happy path

---

## Proposed Changes

### Functional Changes

**F001: build parallelism from the container's CPU limit** (SC-8, FR-15)
- **Current:** nothing is set. `make`, `cargo` and `pytest-xdist` size themselves from the host's CPUs.
- **Proposed:** a bash hook, `/etc/timelike/shell-env.bash`, computes `TIMELIKE_CPUS`.
  - It is `ceil(quota / period)` from cgroup v2 `/sys/fs/cgroup/cpu.max`, capped by the CPU-affinity
    count from `/proc/self/status` `Cpus_allowed_list`.
  - It falls back to the affinity count when `cpu.max` reads `max`, and it is at least 1.
  - It exports **only when unset**: `MAKEFLAGS=-jN`, `CMAKE_BUILD_PARALLEL_LEVEL=N`,
    `CARGO_BUILD_JOBS=N`, `GOMAXPROCS=N`, `PYTEST_XDIST_AUTO_NUM_WORKERS=N` and `PYTHON_CPU_COUNT=N`
    (Python ≥ 3.13 returns it from `os.cpu_count()`).
- **Breaking:** no. An explicit value wins.

**F002: secret-shaped environment variables stripped unless allow-listed** (SC-9, FR-16)
- **Current:** every variable the container or `docker exec -e` provides reaches the agent's shell.
- **Proposed:** the same hook unsets every exported variable whose name is secret-shaped, unless the
  name is listed in `TIMELIKE_ENV_ALLOW`.
  - **Secret-shaped:** the name is split on `_` and upper-cased. A component either **is** one of
    `KEY`, `KEYS`, `APIKEY`, `ACCESSKEY`, `PRIVATEKEY`, `PASSPHRASE`, `PASS`, `CREDENTIAL`,
    `CREDENTIALS`, or **ends with** one of `PASSWORD`, `PASSWORDS`, `PASSWD`, `TOKEN`, `TOKENS`,
    `SECRET`, `SECRETS`.
  - Matching is anchored at component ends, never a bare substring. That keeps `GIT_ASKPASS`,
    `TOKENIZERS_PARALLELISM` and `MONKEY`, and it catches `PGPASSWORD` and `GHTOKEN`.
  - *Amended in review of T050:* whole-component matching alone missed `PGPASSWORD`.
  - **Always kept:** `GIT_CONFIG_KEY_<n>`. It contains the component `KEY`, but it is git's config-key
    name. Unsetting the image's `GIT_CONFIG_KEY_0` would make every git command fail.
  - `TIMELIKE_ENV_ALLOW` holds exact names, separated by commas or whitespace.
- **Breaking:** no. This is the criterion, and the allow-list is the escape hatch.

**F003: timezone UTC and basic, scriptable REPLs** (SC-10, FR-17)
- **Current:** unset.
- **Proposed:** static ENV `TZ="UTC"` and `PYTHON_BASIC_REPL="1"`.
  - Python ≥ 3.13 would otherwise start PyREPL, with colour, line editing and escape sequences.
  - Python is the only language interpreter in the image. perl has no default REPL.
  - Other REPLs an agent may install later are not configured. The claim is limited to what can be
    tested.
- **Breaking:** no.

**F004: the hook reaches every bash invocation style** (FR-1 carried to F001 and F002)
- `ENV BASH_ENV="/etc/timelike/shell-env.bash"` covers non-interactive `bash -c`.
- `/etc/profile.d/10-timelike-shell-env.sh` covers `bash -lc`.
- A line appended to `/etc/bash.bashrc` covers interactive bash.
- The hook is idempotent, uses bash builtins only (no subprocess per shell start), and is a no-op
  outside bash.
- **Limit, recorded rather than hidden:** plain `sh -c` (dash) and a direct `docker exec` of a
  non-shell binary read no startup file, so they get neither F001 nor F002. F003 is static and reaches
  them.

**F005: natural intensity for SC-1–SC-6.** Add the common failure next to each happy-path test. Where a
failure exposes a product gap, report it; do not widen scope silently.

**F006: the in-image start-up figure.** The start-up test prints one parseable line,
`TIMELIKE_STARTUP p95_ms=… runs=… python=… interpreter=…`. `tests/run.sh` runs the unit step with
`-rP` and writes `tests/out/startup.json`. `quality-standards.md` C2 records the 3.14.7 figure
(governance-only).

**F007: register.** Close `FOR-MENTOR.md` Items 1–3, as the send reports the mentor reconciled them.

### Data Model Changes

None.

### API/Contract Changes

None. Contract rules 1–16 are unchanged.

---

## Backward Compatibility Strategy

Additive defaults with explicit-choice precedence (impact analysis, Option 1). No deprecation.

---

## Migration Plan

None. Operators who need a secret-shaped variable in the agent's shell add its name to
`TIMELIKE_ENV_ALLOW` (compose `environment:` or `docker exec -e`).

---

## Testing Strategy

- **Regression:** the existing 118 e2e and 174 unit tests stay green.
- **New:**
  - SC-8–SC-10, one test per criterion per invocation style (`bash -c`, `bash -lc`, `bash -ic`), from
    outside the image
  - common-failure cells for SC-1–SC-6
  - an explicit-wins test and a false-positive test
- **Host lane:** `tests/host/test_env_layer.sh` checks the new ENV keys and the hook's wiring.

---

## Rollout Plan

One merge after the operator's Docker lane (`make test`, `make scan`). Rollback is a revert of the
merge commit.

---

## Success Metrics

| Metric | Target | Measurement |
|---|---|---|
| Slice-0 and slice-1 automated criteria | all executed | e2e TAP in `tests/out/` |
| Unit | all pass on 3.14.7 | `tests/out/unit.txt` |
| In-image start-up p95 | < 100 ms, printed | `tests/out/startup.json` |
| Supply-chain scan | PASS, no new baseline entry | `scan/out/verdict.json` |
| Python coverage | ≥ 90% per file | workspace run (operator decision 2) |

---

## Risks and Mitigation

See impact-analysis.md § Risk Assessment: false positives, the `sh -c` limit, `/proc/1/environ`, the
CPU-count dependency, and the missing daemon.

---

## Alternative Approaches Considered

- **`nproc` and `make` shims:** rejected. A shim on PATH is a timelike tool bound by the contract, which
  breaks `nproc`'s output, and it covers job counts only.
- **Compute at container start and write into the environment:** impossible. A `docker exec` process
  inherits the container's configured environment, not PID 1's.
- **Substring secret matching:** rejected for false positives (`GIT_ASKPASS`, `TOKENIZERS_PARALLELISM`).

---

## Tech Stack Compliance

Compliant (tech-stack 1.3.0). No new technology or package.

---

## Metadata

**Workflow**: Modify (Impact-Analysis-First)
**Original Feature**: Feature 001
**Provenance**: row 4. Revision 2 is already in `audited_against`, so nothing is reconciled.
`source_send` moves to this send: the mentor noted the next modify may record it. The body's generating
send was `bridge/sends/01-rev2-20260928-063549.md`, and both are prompt revision 2.

---

# Cycle 4: revision 6, a clarification (send `bridge/sends/01-rev6-20260928-231531.md`)

**Status**: Active. **Created**: 2026-09-28. **Continues** the slice-1 cycle on `modify/001-slice-1`.

## Modification summary

Record discovery and prompt revision 6 on feature 001, and make plan's three wording changes. No
behaviour changes. Plan ruled option (b), made explicit.

## Proposed changes

- **F101: `contracts/output-contract.md` states the uncapped case.** SC-11 is about "a person reading
  the output contract", so the document itself must say:
  - rule 3's order is the shape of **cut** output
  - the omission line appears only when output was capped
  - uncapped text ends on its own last result line
  - JSON carries `exit` (and `truncated` when capped)
- **F102: README.** Remove "The contract does not fix that line yet", and describe the last line by its
  *kind*, as plan's SC-11 table does.
- **F103: spec.** Record revision 6 in `audited_against` by modify Step 9. The rule list gains the two
  clarifying sentences, copied from the prompt. **Not a regeneration.** `prompt_revision` stays 2 and
  `discovery_revision` stays 3: only `/specswarm:specify` writes those, and modify Step 9 forbids
  touching them. `source_send` moves to this send, as in Cycle 3.
- **F104: `FOR-MENTOR.md` Item 8 closed**, answered by revision 6.
- **F105: quality-standards C2.** Record the in-image start-up p95 (88.1 ms over 50 runs, 3.14.7,
  `tests/out/startup.json` at `01ee1ce`) together with its measurement conditions. Say, with
  evidence, whether those conditions make the figure slower than real tool use (operator decision; the
  send's step 4).

## API / contract changes

None. The contract's behaviour is unchanged. Its document now states what the implementation already
does.

## Testing strategy

No code, test or image changes, so the host lane at `01ee1ce` stands. The workspace lint and unit runs
are repeated as a check that nothing moved.

---

# Cycle 5: repository hooks run, bounded (send `bridge/sends/01-rev7-20260929-094055.md`)

## Modification summary

**What:** repository hooks run, each under a time limit, instead of being switched off.

**Why:** discovery revision 7 (plan `734f22e`). Tension T4: the environment never silently removes a
project's own checks. The bench raised this: `git-commit-hook-rejects` was a loss caused by the
hooks-off default (`bridge/feedback/02-20260929-092443-hooks-off-default.md`).

## Proposed changes

- **F001 · Hooks run.**
  - **Current:** `core.hooksPath=/dev/null` in command scope (R3).
  - **Proposed:** `core.hooksPath=/opt/timelike/git-hooks`, whose dispatchers run the repository's
    own hooks (R11).
  - **Breaking:** yes, intended.
- **F002 · Bounded, with a verdict.**
  - **Limit:** 60 s by default, raised by `TIMELIKE_HOOK_TIMEOUT` or `git config
    timelike.hookTimeout`.
  - **Verdict:** names the hook, the limit and how to raise it, and never how to skip.
- **F003 · Tests.**
  - The hooks-off test inverts.
  - New e2e tests for SC-12 and SC-13, one per invocation style (`bash -c`, `bash -lc`, `bash -ic`)
    in `notty`: a terminal does not change whether a hook runs.
  - New host units for the dispatcher.
- **F004 · Feature 002 follows.**
  - `git-commit-hook-rejects` becomes a tie.
  - `git-commit-hook-hangs` ends on timelike's bounded verdict. The bench's default call limit rises
    from 30 s to 120 s (Claude Code's default), so the 60 s hook verdict arrives inside a call, as it
    would under the harness it is sized for.

## Contract changes

None to the output contract. The verdict follows rule 14's error shape. It is a hook message, not a
timelike tool.

# Cycle 6: rule 5's scope recorded; T4's `env -i` limit stated and pinned (send `bridge/sends/01-rev9-20261001-191224.md`)

## Modification summary

**What:** three items carried since discovery revisions 8 and 9. No criterion changes, and no
behaviour changes.

**Why:**
- Revision 9 (plan's ruling, `bridge/feedback/03-20260930-235857-exit-pass-through.md` § Resolution):
  the exit-code vocabulary is a tool's own outcomes. 003 amended the contract at `58b7d11`; this
  cycle checks 001's spec against it and records it.
- Revision 8 (`bridge/feedback/01-20260930-060721-unbounded-if-env-unset.md` § Resolution, option (c)):
  T4's limit holds in the environment timelike provides. The README must say so, and a test must pin
  the limitation "so it cannot widen silently".

## Proposed changes

- **F001 · Rule 5's scope in the spec.**
  - **Current:** spec rule 5 lists the six codes, unscoped.
  - **Proposed:** revision 9's clarification is appended in place, as revision 6's were to rules 2
    and 3.
  - **Breaking:** no.
- **F002 · README states T4's limit.**
  - Where the README describes the hook limit: under `env -i` (or anything that discards the
    environment) a repository with a local `core.hooksPath` gets git's own behaviour, unbounded;
    `.git/hooks` stays bounded through `/etc/gitconfig`.
  - When in doubt, run git through `run --timeout N` (feature 003), which stops the whole tree.
- **F003 · A test pins both cases.**
  - Run through the image's real shells (`bash -c`, `bash -lc`, `notty`), git under `env -i`, with
    the image's own `/etc/gitconfig` (lore P005: no helper that sets its own environment).
  - Default `.git/hooks`: stopped at the repository's limit, with the verdict.
  - Local `core.hooksPath`: still running past the limit plus the dispatcher's grace, with no verdict.
    The test's own `timeout` ends it, and teardown kills by the hook's own pid.

## Contract changes

None. The contract was amended by 003 (`58b7d11`). The spec now quotes the same scope.
