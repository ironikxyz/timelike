# Impact Analysis: Modification to Feature 001

**Feature**: Agent shell baseline & output contract
**Modification**: slice 1 (natural) of prompt 01, from `bridge/sends/01-rev2-20260928-214635.md`
**Analysis Date**: 2026-09-28
**Analyst**: `/specswarm:modify` (specswarm 4.0.1-botbaubble.2.13.0), code instance
**Branch**: `modify/001-slice-1`, off `master` at `dca60ff`

---

## Proposed Changes

Four criteria the spec never carried (they were out of scope for slice 0), natural-intensity coverage of
the seven slice-0 criteria, and three operator decisions.

**Change categories**:
- **Functional (environment layer):**
  - build parallelism derived from the container's CPU limit
  - secret-shaped environment variables stripped unless allow-listed
  - timezone UTC
  - REPLs in their basic, scriptable prompt mode
- **Tests:**
  - one e2e test per new criterion per invocation style
  - the common failure added where a slice-0 test covers only the happy path
  - the start-up test's p95 surfaced into `tests/out/`
- **Governance-only:**
  - the in-image start-up figure recorded in `quality-standards.md` (operator decision 1)
  - `FOR-MENTOR.md` Items 1–3 closed (decision 3)
- **Data model / API:** none. The output contract (rules 1–16) is unchanged: "slice 1 does not redefine
  it".
- **Manual criterion (contract predictability):** needs a person. It is reported `unconfirmed`, and the
  contract document is made findable for that reader.

---

## Affected Components

### Direct Dependencies

| Component | Type | Impact | Notes |
|---|---|---|---|
| `image/Dockerfile` § 7, the ENV block | Image | Medium | Adds `TZ`, `PYTHON_BASIC_REPL` and `BASH_ENV` as static values. `tests/host/test_env_layer.sh` parses this block, so its rules hold (one ENV, KEY="value") |
| New `/etc/timelike/` shell hook | Image | High | Holds the CPU-derived job counts and the secret strip, which depend on the running container, so a static ENV cannot hold them. Reached through `BASH_ENV` (bash -c), `/etc/profile.d` (bash -lc) and `/etc/bash.bashrc` (interactive) |
| `/etc/bash.bashrc`, `/etc/profile.d/` | Image | Low | One line each that sources the hook |
| `tests/e2e/*.bats` | Tests | Medium | New bats file(s) for the slice-1 criteria. Common-failure cells added to the existing six files |
| `tests/host/test_env_layer.sh` | Tests | Low | The host lane checks the new ENV keys and the hook |
| `tests/unit/test_agentio_startup.py`, `tests/run.sh` | Tests | Low | A parseable p95 line, and `tests/out/startup.json` |
| `.specswarm/quality-standards.md` | Governance | Low | C2's figure. Governance-only, so no audit entry |
| `FOR-MENTOR.md` | Register | Low | Items 1–3 closed |

**Total direct dependencies**: 8

### Indirect Dependencies

| Component | Type | Impact | Notes |
|---|---|---|---|
| Supply-chain scan | Gate | Low | No package is added. If one were, a new High or Critical would block (stack note 15) |
| The credential-class baseline Criticals (CVE-2026-11856, -19931, -8926) | Governance | Low | They are accepted because the agent holds no credentials. **This modification strengthens that premise** (secret-shaped variables are stripped) and gives the agent no credential, netrc or proxy |
| Every later timelike tool | Tools | None | The hook changes the environment, not the contract |

---

## Breaking Changes Assessment

### Breaking Changes Identified: No

No criterion is removed and no contract rule changes. Two behaviour changes are visible to a user:

- **Secret-shaped variables disappear** from shells. That is the criterion. The escape hatch is the
  allow-list (`TIMELIKE_ENV_ALLOW`).
- **Job-count variables** (`MAKEFLAGS` and the like) are **set only when unset**, so an explicit choice
  wins. This matches the gitconfig fallback's rule: "The environment changes defaults, not explicit
  choices" (spec edge cases).

---

## Backward Compatibility Strategy

### Option 1 (recommended): additive defaults with explicit-choice precedence

Static ENV additions for values that don't depend on the container: `TZ`, `PYTHON_BASIC_REPL`,
`BASH_ENV`. One shell hook holds the dynamic pair: job counts from cgroup `cpu.max` and affinity, and the
secret strip. The hook is bash builtins only, idempotent, and sourced by all three bash invocation
styles.

- **Pros:** it reaches bash -c, bash -lc and interactive shells, as FR-1 requires. It costs no
  subprocess per shell. Explicit values win.
- **Cons:** plain `sh -c` (dash) and a direct `docker exec` of a non-shell binary read no hook, so they
  get neither the job counts nor the strip. The container's PID 1 environment holds whatever the
  container was started with (see Risks).

### Option 2: `nproc`/`make` shims on PATH

Rejected. A shim in `/opt/timelike/bin` is a "timelike tool on PATH" and would have to satisfy the
contract (a header first line, `--json`, `--agent-info`). That breaks `nproc`'s own output, and it covers
job counts only, not secrets.

---

## Migration Requirements

None. There is no data. Configuration: operators who need a secret-shaped variable inside the agent's
shell list it in `TIMELIKE_ENV_ALLOW`. That is documented in the README and in the hook.

---

## Risk Assessment

### Risk Level: Low–Medium

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| The hook's name patterns strip a legitimate non-secret variable (e.g. `TOKENIZERS_PARALLELISM`) | Medium | Low | Match whole name components (split on `_`), not substrings. A test pins the false-positive guard. The allow-list is the escape hatch |
| `sh -c` or a direct exec misses the hook | Medium | Medium | The spec defines the harness invocation as `bash -c` / `bash -lc` (Assumption 1). Record the limit in decisions and in the cycle report's `not_verified` |
| `/proc/1/environ` still shows a secret the operator passed to the container | Low | Medium | The strip governs what agent shells hold. It cannot remove what the operator gave the container. Recorded; the operator should not pass secrets to the agent container at all (P4) |
| A CPU-limit test depends on the host's CPU count (a 1-CPU host cannot show "rather than the host's") | Medium | Low | Start the test container with a limit below the host count. Where the host has too few CPUs, the test says so instead of passing vacuously |
| No Docker daemon here | Certain | Medium | Everything image-level is written here and verified in the operator's Docker lane (research R10) |

**Overall Risk Score**: 3/10

---

## Testing Requirements

### Existing tests to update
- `tests/unit/test_agentio_startup.py`: a parseable p95 line
- `tests/run.sh`: `-rP` on the unit step; write `tests/out/startup.json`
- `tests/host/test_env_layer.sh`: the new ENV keys and the hook wiring

### New tests required
- **SC-8, parallelism:** in a container started with a CPU limit below the host count, the job-count
  defaults equal the limit under `bash -c`, `bash -lc` and `bash -ic`. An explicit value wins.
- **SC-9, secrets:** secret-shaped names are absent under each style, an allow-listed name is present,
  and a non-secret look-alike is present.
- **SC-10, UTC and REPL:** `date +%Z` gives UTC under each style. Python's REPL in a pty shows the basic
  `>>> ` prompt with no escape sequences.
- **Natural intensity, SC-1–SC-6:** the common failure next to each happy path (e.g. `git commit --amend`,
  a merge of diverged branches, `git rebase -i`, `git tag -a` without `-m`, a URL with an embedded user,
  `git clone` against a 401).

### Integration testing
- The whole e2e suite runs from outside the image through the invocation styles the harness uses (lore
  cross-stack P005).

---

## Rollout Strategy

**Recommended approach**: one branch, one merge after the operator's Docker lane (`make test`,
`make scan`). There are no feature flags. **Rollback**: revert the merge commit. No data is involved.

---

## Recommendations

1. Keep the three dynamic concerns in one bash-only hook, and keep static values in the ENV block.
2. Pin a false-positive test for the secret patterns, and an explicit-wins test for job counts.
3. Record the `sh -c` / direct-exec limit rather than claim coverage there.

**Proceed with Modification**: Yes.

---

## Tech Stack Compliance

**Tech Stack File**: `.specswarm/tech-stack.md` (1.3.0)
**Validation Status**: Compliant. No new technology and no new package: bash and Debian base files only.
**Concerns**: none.

---

## Metadata

**Workflow**: Modify (Impact-Analysis-First)
**Provenance**: row 4. Prompt revision 2 is already in `audited_against: [2]`, so nothing is reconciled
and Step 9 is skipped.

---

# Cycle 4 addendum: revision 6 (send `bridge/sends/01-rev6-20260928-231531.md`)

**Analysis date**: 2026-09-28. **Branch**: `modify/001-slice-1`, continued from `01ee1ce` ("continue that
cycle; don't restart it").

**What moved:** discovery revision 6 and prompt 01 revision 6. It is a **clarification** of
output-contract rules 2 and 3. Rule 3's order is the shape of output a tool cuts. The omission line
appears only when output was capped. Uncapped text ends on its own last result line. JSON carries `exit`.

**Criteria diff** (the Constraints-to-Criteria section of the revision-2 and revision-6 sends): only
rules 2 and 3 gain one annotation each. **No criterion is added, removed or reworded.** Revisions 3–5
did not touch prompt 01.

**Classification (modify, row 7):** revision 6 **needs no body change**. The spec's rules 2 and 3 are
still true.

**Affected components:**

| Component | Change | Code? |
|---|---|---|
| `contracts/output-contract.md` | states the uncapped case (plan's wording change) | no |
| `README.md` | removes "The contract does not fix that line yet" | no |
| `spec.md` | `audited_against`, plus the two clarifying sentences in its rule list | no |
| `FOR-MENTOR.md` | Item 8 closed | no |
| `.specswarm/quality-standards.md` | C2: the in-image start-up figure and the conditions it was measured under | no |
| `agentio`, tools, tests, image | **none**. Plan: "what code/ built already matches" | — |

**Breaking changes:** none. **Risk:** low. **Host results at `01ee1ce` stand**, because no code, test or
image file changes (the send: "unless you change code, tests or the image").

---

# Cycle 5: repository hooks run, bounded (send `bridge/sends/01-rev7-20260929-094055.md`, discovery revision 7)

**Provenance:** modify row 7. The prompt is at revision 7; `audited_against` is `[2, 3, 4, 5, 6]`.
- **SUPERSEDED:** the struck hooks clause (FR-4, SC-3, Scenario 3, research R3). It is corrected **in
  place through this modify, declared**, as the send and the project's CLAUDE.md say. The plugin's
  row-7 rule says to stop and regenerate; that is not followed here, because the send says not to (the
  correction needs the work done, and R3's reasoning is reused).
- **INCOMPLETE:** the two added criteria (SC-12, SC-13). The work is done in this cycle.

**Proposed change:** replace `core.hooksPath=/dev/null` with a dispatcher directory. A repository's
own hooks then run, each under a limit, with a verdict when the limit is passed (research R11).

| Component | Change | Impact |
|---|---|---|
| `image/Dockerfile` ENV | `GIT_CONFIG_VALUE_0` changes from `/dev/null` to `/opt/timelike/git-hooks`; COPY the directory, keeping its links | **Behaviour change for every git command in the image:** hooks run. That is the intended fix to P1 |
| `image/rootfs/etc/gitconfig` | `hooksPath` changes from `/dev/null` to the dispatcher directory (the fallback when the environment variable is unset) | Low |
| `image/rootfs/opt/timelike/git-hooks/` (new) | `dispatch` and 25 links | New |
| `tests/e2e/credentials-fail-fast-and-hooks-off.bats` | Its hooks half inverts, and it keeps the credentials half | Rename. The test names change with the criteria |
| New e2e tests for SC-12 and SC-13 | One test per criterion per invocation style | New |
| Host units for the dispatcher | pytest with real git | New |
| **Feature 002 (merged)** | Catalog texts and notes for both hook tasks, their expected verdicts, the bench's default call limit, and the timelike emulation in its units | `changed_other_features` |

**Breaking changes:** yes, and intended. A repository's hooks now run where they did not. An agent
that relied on hooks being off sees them run. That is the ruling (T4).

**Risks:**
- **A dispatcher that loops.** This happened in an experiment. It is fixed, and a unit guards it.
- **Cost per git command:** about 30–40 ms per commit, measured.
- **Hooks that ask for a terminal:** under the limit they time out with a verdict, where before they
  never ran. That is the ruling's intent.
- **Bind-mounted workspaces:** not widened (R11).

**Proceed:** yes, with caution. The Docker lane is authoritative.

# Cycle 6: rule 5's scope recorded; T4's `env -i` limit stated and pinned (send `bridge/sends/01-rev9-20261001-191224.md`, discovery revision 9)

**Provenance:** modify row 7. The prompt is at revision 9, `prompt_revision` is 2, and `audited_against`
is `[2, 3, 4, 5, 6, 7]`. The unaudited revisions are 8 and 9.
- **Revision 8:** prompt 01 did not change (the send says so; T4's clarification is discovery-level).
  Nothing in the body to classify.
- **Revision 9: needs no body change.** Rule 5 gains a clarifying sentence: the vocabulary is a tool's
  own outcomes, and a wrapper passes its command's exit through. **No criterion changed:** the
  Acceptance Criteria of `01-rev7-20260929-094055.md` and `01-rev9-20261001-191224.md` are
  byte-identical (13 criteria), so removals and rewordings are visible and none occurred.
  - **No spec line states the unconditional "always one of" reading.** Spec rule 5 (lines 170–171)
    lists the six codes without a scope, the same wording as the prompt before revision 9. That is
    not false under revision 9, which scopes the list rather than contradicting it.
  - As with revision 6's annotations to rules 2 and 3, revision 9's clarification is **copied into the
    spec's rule 5, declared**, so the spec states the scope its contract (`output-contract.md`, amended
    by 003 at `58b7d11`) already states.
  - FR-9 and SC-5 ("the exit-code vocabulary") stay true: conformance C6/C7 already check
    pass-through tools against their declared exits (003).
- **SUPERSEDED / INCOMPLETE:** none.

**Proposed change:** documentation and a test only. No behaviour changes.

| Component | Change | Impact |
|---|---|---|
| `spec.md` contract rule 5 | Revision 9's clarification appended in place, declared | None on behaviour |
| `README.md` hook paragraph | States T4's limit: it holds in the environment timelike provides; under `env -i` a local `core.hooksPath` runs unbounded, `.git/hooks` stays bounded through `/etc/gitconfig`; points at `run` as the bounded way | None on behaviour |
| New `tests/e2e/hooks-under-env-i-default-bounded-local-unbounded.bats` | Pins both `env -i` cases through the image's real shells, the unbounded case bounded by the test's own watchdog | New |
| `Makefile` `SHELLCHECK_FILES`, if it lists bats files | The new file is added | Low |
| Other features | None. `run` (003) is only named in the README | — |

**Host experiment (sandboxed, git 2.43.0):** under `env -i` with `GIT_CONFIG_SYSTEM` = the image's
`/etc/gitconfig` (hooksPath pointed at the checkout's dispatchers), a hanging `.git/hooks/pre-commit`
was stopped at 2.0 s with the verdict (git exit 1). The same hook under a local `core.hooksPath` ran
with no verdict until the experiment's 8 s watchdog. The image (git 2.47.3) decides.

**Breaking changes:** none.

**Risks:**
- **A test that hangs the lane.** The unbounded case is unbounded by design. The test bounds it with
  its own `timeout` (which stops the process group), and teardown kills by the pid the hook wrote.
- **The test widening silently in the other direction.** If a future change bounded the local case
  too, the test fails, and the README and this test are updated together. That is what pinning means.

**Proceed:** yes. The Docker lane is authoritative.

---

# Cycle 7: rule 9's clarification recorded (send `bridge/sends/01-rev10-20261003-003933.md`, discovery revision 10)

**Provenance:** modify row 7. The prompt is at revision 10, `prompt_revision` is 2, and `audited_against`
is `[2, 3, 4, 5, 6, 7, 8, 9]`. The only unaudited revision is 10.
- **Revision 10: needs no body change.** Rule 9 gains a clarifying sentence: exit 4 carries a
  confirmation envelope or a grant envelope, told apart by `status`, and an operator's command never
  appears in `confirm`. **No criterion changed:** the Acceptance Criteria of `01-rev9-20261001-191224.md`
  and `01-rev10-20261003-003933.md` are byte-identical (13 criteria, sha256 `7d42021a…`), so removals
  and rewordings are visible and none occurred.
  - **Spec rule 9 (line 181) is the body's only statement about exit 4's envelope**, and it states the
    confirmation envelope only. That is still true under revision 10, which adds a second envelope
    rather than contradicting the first. No spec line mentions the confirm envelope's old `grant`
    field, which 004's T018 removed. So this is **not SUPERSEDED**, and the spec is not regenerated.
  - As with revision 9's sentence in rule 5 (T074), revision 10's is **copied into the spec's rule 9,
    declared**.
- **SUPERSEDED / INCOMPLETE:** none.

**001's contract already says the same (lore P004: what was compared).** 004's T018 changed it at
`b7a6ea6` (on `archive/pre-publish`; unchanged since, `git diff archive/pre-publish HEAD` is empty for
these paths). Read clause by clause against revision 10's sentence, by a delegate, with the key lines
re-read here:

| File | What it says | Against revision 10 |
|---|---|---|
| `contracts/output-contract.md:33` (exit table) | exit 4: "stdout carries one envelope, told apart by `status`: `confirmation_required` … or `grant_required`" | agrees |
| `contracts/output-contract.md:112–125` (§ Confirmation) | the confirmation envelope (:112–114); "A missing grant is the other exit-4 envelope": the grant, `limit {name, allowed, needed}`, `extend`, `extend_by: "operator"`, `performed: false`; the operator's command is "never in `confirm`"; not `--yes`-confirmed, "the grant is the confirmation"; "Rule 8 still binds it" | agrees, every clause |
| `contracts/grant-envelope.schema.json` | requires `grant`, `limit`, `extend`, `extend_by` (const `operator`), `performed` (const `false`), `status` const `grant_required`; :28 no `confirm` key, checked by C9 and the agentio units (the schema subset has no `not`) | agrees |
| `contracts/confirm-envelope.schema.json` | properties `tool, target, scope, status, plan, confirm`; `status` const `confirmation_required`; **no `grant`** | agrees; silent on operator commands in `confirm` (no `additionalProperties: false`), which C9 enforces |
| `tools/agentio/agentio.py` `grant_required()` (:276–312) | refuses unless `Tool(grant_envelope=True)`; emits the grant envelope with `extend_by="operator"`, `performed=False`, exit 4; `confirm_required()` builds `confirm` from the tool's own argv plus `--yes` | agrees |
| `contracts/conformance.md:34` C9 and `tools/bin/timelike-conform` `check_envelope` | every exit 4 prints one envelope of a declared `status`; a grant envelope has `limit`, `extend_by: "operator"`, `performed: false` and no `confirm`; no `confirm` names a command outside the tool's own | agrees |

**Disagreements: none.** Two observations, neither a disagreement, recorded and not acted on:
- Rule 8's clause for a grant client is stated only in `output-contract.md:123–124`. The schemas,
  C9 and agentio are silent: agentio ties `--dry-run` to `destructive` alone, which is rule 8 for
  every tool, so nothing is missing.
- Nothing forbids declaring a tool both `mutating=True` and `grant_envelope=True`, which would give a
  grant client `--yes`. No tool does (`adele` leaves `mutating` at False). In that combination
  `Tool.codes()` would describe exit 4 as confirmation only. A guard belongs to whichever cycle adds a
  second grant client; it is noted for the mentor, not built here.

**Proposed change:** the spec's rule 9 only. No code, test or contract change, so nothing outside
`.specswarm/` changes and no Docker lane is needed (send § 2).

| Component | Change | Impact |
|---|---|---|
| `spec.md` contract rule 9 | Revision 10's clarification appended in place, declared | None on behaviour |
| `spec.md` frontmatter `audited_against` | 10 appended (Step 9, full) | Provenance only |
| `audit-log.md` | one `full` row | Provenance only |
| Other features | None. 004's T018 already changed 001's contract and recorded it under its `changed_other_features` | — |

**Breaking changes:** none. **Risk:** low; documentation only.

**Proceed:** yes.
