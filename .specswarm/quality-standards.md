---
governance_audited_against: [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]
---

> **Amended 2026-09-28** per `../bridge/feedback/stack-review-2026-09-28.md` (plan's review of
> the choices made at init). This is not a discovery revision, so `governance_audited_against` is unchanged.
> Changed: C1 (`mypy --strict`), C2 (re-measure the start-up baseline in the image), Adele
> integration coverage, and gates G-a (invocation matrix) and G-b (snapshot restore round-trip).
>
> **Amended 2026-09-28** to match the init template shipped in specswarm 2.10.1 and the keys the
> plugin's commands read. Thresholds and gates are unchanged. Added: the machine-readable keys
> (`quality_threshold` included, which `/specswarm:ship` reads), and the template's Security and
> Documentation sections at their defaults. The plugin's bundle-size enforcer is switched off; see
> Performance Budgets. This is not a discovery revision, so `governance_audited_against` is
> unchanged.
>
> **Amended 2026-09-28** for specswarm 2.11.0: `/specswarm:ship` now reads `min_quality_score`, so
> the duplicate `quality_threshold` key was removed. The threshold is unchanged at 90. This is not a
> discovery revision, so `governance_audited_against` is unchanged.
>
> **Audited against discovery revision 3** (2026-09-28), via `../bridge/governance-context.md` and
> `../bridge/feedback/gov-20260928-061535.md`. Security moved from template defaults to strict:
> `require_security_scan: true`, `block_on_high_vulns: true`, a merge-blocking supply-chain gate,
> and a dated-exemption rule for unfixable vulnerabilities. `require_changelog_entry: true` and the
> unit-only `max_test_duration` were ratified as they stand. Revision 3 is appended to
> `governance_audited_against`.
>
> **Audited against discovery revision 4** (2026-09-28), via `../bridge/governance-context.md` and
> `../bridge/feedback/gov-20260928-063634.md`. The review date is now enforced by discovery (it was
> code/'s provisional reading). Added: a review date at most 90 days after the last review (a new
> `Reviewed` column), and the gate's failure output as an escalation naming the identifier, image
> and package, date, and the file and field to update. Revision 4 is appended to
> `governance_audited_against`.
>
> **Amended 2026-09-28** (not discovery-driven): C2's start-up re-measurement in the image is
> recorded under Performance Budgets.
>
> **Audited against discovery revision 5** (2026-09-28), via `../bridge/governance-context.md`
> (`/mentor:regovern`, 13:13:20Z) and `../bridge/feedback/01-20260928-130206-supply-chain-exemptions.md`
> § Resolution. Per-vulnerability exemption rows are replaced by a reviewed baseline per image digest
> (a reason per origin group, a separate reason per Critical, one review date, a one-line summary on
> every scan; new or newly fixable findings block), and "fix available" is defined. Revision 5 is
> appended to `governance_audited_against`.
>
> **Amended 2026-09-28** (governance-only, not a discovery revision, so no audit entry of its own)
> per `../bridge/feedback/01-20260928-130206-quality-score.md` § Resolution: the averaged quality
> score is informational and never a merge gate, and the merge bar is listed under Quality Gates.
> `min_quality_score` is 0, with the reason under Exemptions.
>
> **Amended 2026-09-28** (governance-only, under the same ruling, so no audit entry) per the same
> feedback file, § Correction after closure. specswarm 2.13.0's `ship` reads `enforce_gates`, and with
> `true` an unparsable (`unknown`) score exits without merging, even at `min_quality_score: 0`. The
> ruling is now expressed as `enforce_gates: false`. The Exemptions row is corrected.
>
> **Audited against discovery revision 6** (2026-09-28), via `../bridge/governance-context.md`
> (`/mentor:regovern`, 23:08:03Z), § "What Changed In Those Revisions", and
> `../bridge/feedback/01-20260928-225646-uncapped-last-line.md` § Resolution. Revision 6 clarifies
> output-contract rules 2 and 3: rule 3's order is the shape of output a tool **cuts**, and uncapped
> output ends on its own last line. The *Output contract (H2)* gate now says what verifies that shape.
> No threshold moved. Revision 6 is appended to `governance_audited_against`.
>
> **Amended 2026-09-29** (governance-only, not a discovery revision, so `governance_audited_against`
> is unchanged) per `../bridge/feedback/gov-20260929-093556-block-merge-on-failure.md`:
> `block_merge_on_failure` is changed from `true` to **`false`**. It rests on plan's discovery-revision-5
> ruling (`plan/research/resolution-01-20260928-130206-quality-score.md`): *"The averaged quality score
> is not a merge gate … It never blocks a merge."*
> - **Why `true` contradicted the ruling:** under specswarm 2.18.0, `implement` step 10i's score is
>   `unknown` on every run. Its test and coverage components need `lib/test-framework-detector.sh`,
>   which no version of the fork ships, and `unknown` counts as a failure for this key. So `true`
>   halted every cycle on a score nobody can measure.
> - **What `false` does instead:** a send-path cycle warns and asks a person; a `--dispatch` cycle
>   records the score and continues.
> - **Unchanged:** `require_passing_tests`, `require_lint_pass` and `require_type_check_pass` are the
>   real bar, enforced by the lanes.
>
> **Audited against discovery revision 7** (2026-09-30), via `../bridge/governance-context.md`
> (`/mentor:regovern`, 2026-09-29T09:40:34Z), § "What Changed In Those Revisions". No change needed:
> revision 7 touched no Constraints section, and no gate here states the old hooks-off default. The new
> constraint ("the environment never silently removes a project's own checks") lives in prompt 01 and
> reaches code through the 01 modify send, as acceptance criteria rather than a quality gate. Revision 7
> is appended to `governance_audited_against`.
>
> **Audited against discovery revision 8** (2026-09-30), via `../bridge/governance-context.md`
> (`/mentor:regovern`, 2026-09-30T06:15:21Z), § "What Changed In Those Revisions". **Amended:**
> revision 8 adds a Hard constraint ("Nothing the agent writes executes on the operator's host unless
> the operator could see it in the change"), and this file derives from Constraints. So a Boundary
> gate is added, **Host git state (P4)**. It applies from the first feature that mounts a workspace
> (13); no feature built so far mounts one, so it changes nothing for 001 or 002. T4's clarification
> needs no gate: the hook limit is 001's criterion SC-13, and the `env -i` case arrives with 01's next
> send. No threshold moved. Revision 8 is appended to `governance_audited_against`.
>
> **Audited against discovery revision 9** (2026-10-01), via `../bridge/governance-context.md`
> (`/mentor:regovern`, 2026-10-01T04:32:58Z), § "What Changed In Those Revisions". **Amended:**
> revision 9 clarifies the Agent output contract soft constraint: the exit vocabulary is a tool's own
> outcomes, and a tool that runs a command the agent named passes its exit through and declares it.
> This file derives from Constraints, and its *Output contract (H2)* gate cites the conformance check,
> which exercised only exits inside the vocabulary. So the gate gains one bullet: a pass-through tool
> is run wrapping a command that exits outside the vocabulary. The check itself changes in feature
> 03's cycle. No threshold moved. Revision 9 is appended to `governance_audited_against`.
>
> **Audited against discovery revision 10** (2026-10-02), via `../bridge/governance-context.md`
> (`/mentor:regovern`, 2026-10-02T05:50:50Z), § "What Changed In Those Revisions", and
> `../bridge/feedback/12-20261002-054636-grant-envelope.md` § Resolution. **Amended:** revision 10
> clarifies the Agent output contract soft constraint: exit 4 carries a confirmation envelope or a
> grant envelope, told apart by `status`, and an operator's command never appears in a field the
> agent's habit runs. This file derives from Constraints, and its *Output contract (H2)* gate cites
> the conformance check, which knew only the confirmation envelope. So the gate gains one bullet: a
> grant envelope is checked against its own schema, and no envelope's `confirm` may name a command
> outside the agent's own tool, a negative case that must be able to fail. The *Refusals (P4)* gate
> already requires cap excess to exit 4 with an escalation; it now names the grant envelope. The
> check itself changes in feature 004's Cycle 2 (12 s0). No threshold moved. Revision 10 is
> appended to `governance_audited_against`.
>
> **Audited against discovery revision 11** (2026-10-04), via `../bridge/governance-context.md`
> (`/mentor:regovern`, 2026-10-04T00:24:17Z), § "What Changed In Those Revisions", and
> `../bridge/feedback/07-20261003-022613-snapshot-store-and-persistence.md` § Resolution. **No change
> needed:** revision 11 revises the Agent output contract's rule 10 (two state locations, a
> per-session scratch directory and a per-workspace state root outside the workspace; the
> in-workspace project cache is withdrawn). This file derives from Constraints, but no gate restates
> rule 10's state locations. The *Snapshots (T2)* budget and the *Snapshot restore round-trip (P5)*
> gate name no store technology, so the stack's move from git to a stdlib store leaves them true.
> The state root's survival criteria reach code as 07 slice-1 acceptance criteria, not as a gate.
> No threshold moved. Revision 11 is appended to `governance_audited_against`.
>
> **Audited against discovery revision 12** (2026-10-04), via `../bridge/governance-context.md`
> (`/mentor:regovern`, 2026-10-04T08:54:45Z), § "What Changed In Those Revisions", and
> `../bridge/feedback/05-20261004-062732-view-search-rule3-and-byte-bound.md` § Q3. **No change
> needed:** revision 12 clarifies the Agent output contract's rule 13 (the line cut applies in both
> modes; in JSON each content string, with the cut byte count as data). This file derives from
> Constraints, but no gate restates rule 13 as text-only or names a JSON exemption. The *Output contract
> (H2)* gate cites the conformance check (C8 checks ANSI, not the line cut). The cut itself changes in
> `agentio` in feature 006's cycle. No threshold moved. Revision 12 is appended to
> `governance_audited_against`.
>
> **Audited against discovery revision 13** (2026-10-05), via `../bridge/governance-context.md`
> (`/mentor:regovern`, 2026-10-04T23:28:30Z), § "What Changed In Those Revisions", and
> `../bridge/feedback/batch-20261004-232148-rule9-scope-and-workspace-context-file.md` § Resolution.
> **Amended:** revision 13 clarifies the Agent output contract's rule 9. A change to an exactly named
> target, applied whole or not at all, that shows what it changed, is not confirmed; such a tool
> declares `mutating: true` and `confirm_protocol: false`, and rule 8 (`--dry-run`) still binds it when
> it overwrites or removes. No gate restated rule 9 as "every mutating tool confirms", but the *Output
> contract (H2)* gate lists the conformance check's rules by revision, and this one adds a rule. So the
> gate gains one bullet: `confirm_protocol: false` on a tool that overwrites or removes requires
> `dry_run: true`, shown failing on a manifest that breaks it. The check itself is built in feature
> 008's cycle (prompt 06), with `confirm_protocol` restored in 001's manifest schema. No threshold
> moved. Revision 13 is appended to `governance_audited_against`.
>
> **Audited against discovery revision 14** (2026-10-08), via `../bridge/governance-context.md`
> (`/mentor:regovern` for revision 14), § "What Changed In Those Revisions" (relied on), and
> `../bridge/feedback/04-20261008-173021-agent-runtimes-for-package-installs.md` § Resolution (Q1–Q3).
> **Amended:** revision 14 adds the agent runtimes (an agent Python and Node) to the agent image, and the
> same binaries to the bench's vanilla image. Checked: whether any gate states the image's package set
> (none does; stack note 15 is cited nowhere here), the vanilla image's contents (none does), and the
> *Supply-chain scan* gate, which said "scan both images (agent and Adele)". `make scan` already scans
> four images (agent, Adele, vanilla, bench driver), and two of them now carry the runtimes. So the gate
> names the four images and says the runtimes, Node's bundled npm dependencies included, are in each
> SBOM that Grype reads, under the same baseline rule; pip-audit stays over timelike's own interpreter.
> No threshold moved. Revision 14 is appended to `governance_audited_against`.

# Quality Standards - Timelike

**Last Updated**: 2026-09-28
**Auto-Generated**: No. Quality level Strict, chosen at `/specswarm:init`

---

## Quality Gates

These thresholds are enforced by `/specswarm:ship` before allowing merge to parent branch.

```yaml
# Overall Quality
min_quality_score: 0    # the score is informational, never a merge gate; see Exemptions
min_test_coverage: 90   # percentage, measured per language as below
enforce_gates: false    # the score only warns (ship, from specswarm 2.13.0); the merge bar below blocks
```

**The averaged quality score is informational.** It is still computed and reported for trend, and
it never blocks a merge. It cannot pass for this project: browser tests, bundle size and visual
alignment do not apply to a CLI and infrastructure project, and the plugin scores them as zero.

**The merge bar** (plan's ruling, `../bridge/feedback/01-20260928-130206-quality-score.md`). A merge
needs all five:
1. every Boundary and Safety gate under Custom Quality Checks
2. the supply-chain scan (H9, discovery revision 5)
3. coverage of 90% per language (Python, Go), as below
4. one test per acceptance criterion under each invocation style
5. Manual criteria reported as unconfirmed until someone observes them

`/specswarm:ship` enforces none of these itself. It compares only the score against
`min_quality_score`, and with `enforce_gates: false` a failing or unknown score warns and does not
block (specswarm 2.13.0). **For later cycles:** from 2.13.0, `implement` step 10i compares its own
score too. It is `unknown` on this project, so `block_merge_on_failure` is `false` (amended
2026-09-29, above): a send-path cycle warns and asks, and a `--dispatch` cycle records the score and
continues. The bar is enforced by the project's own lanes (`make test`, `make test-host`, `make scan`),
and a merge is not asked for until they pass.

Coverage is measured per language:
- Python (`tools/`, `agentio`): line + branch coverage via `coverage.py`
- Go (`adele/`): statement coverage via `go test -cover`. The Docker Engine API filter (including
  upgraded exec/attach streams) and the fly.io Machines calls MUST be covered by integration tests
  against the real services, never by mocks written to reach the 90% target. Either count those
  integration runs toward coverage on a runner with a Docker daemon (they skip where there is
  none), or exempt the paths with a justification in the feature plan
- Bash environment layer: no line-coverage metric. It is covered by bats-core tests, one per
  acceptance criterion, under each invocation style (`bash -c`, `bash -lc`, interactive)

Every acceptance criterion has a test named after its distinguishing text, or is marked Manual and
reported as unconfirmed until someone observes it.

---

## Performance Budgets

```yaml
# The plugin's enforcer measures JavaScript bundle sizes. Timelike ships no bundles, so it stays off.
# Timelike's own budgets are listed below and enforced as tests, which block merge.
enforce_budgets: false
```

- **Agent-side tool start-up:** stays well under 1% of an agent turn. A call slower than 100 ms
  p95 fails.
  - **Measured in the image (C2): p95 88.1 ms over 50 runs on Python 3.14.7**, within the budget by
    12 ms. From `tests/out/startup.json`, Docker lane at `01ee1ce`, image `sha256:7a1266f0e85d`,
    2026-09-28T22:39Z.
  - **Conditions of that figure.** It ran in the agent image on the image's CPython, but not on the
    tools' own path:
    - the unit step runs `uv run --no-project --python /opt/timelike/python/bin/python3 --with pytest`,
      so `sys.executable` was uv's ephemeral environment under `/tmp/uv-cache/…`
    - `PYTHONDONTWRITEBYTECODE=1` was set, and the repository was mounted read-only
    - so each of the 50 runs imported `agentio` by compiling it from the source copy in
      `tools/agentio/`

    A real tool runs `#!/opt/timelike/python/bin/python3 -I` and imports the copy in site-packages,
    which the Dockerfile precompiles (§ 3).
  - **Those conditions make the figure slower than real use, not faster.** Evidence: a host experiment
    on the same CPython 3.14.7 build (python-build-standalone 20260924) with the test's own program and
    p95 method, 3 × 50 runs per condition, repeated twice.
    - The test's conditions gave **88.5 ms**, and the real-tool path gave **77.2 ms**: about 11 ms apart.
    - Compiling `agentio` from source every run accounts for about 8 ms. uv's ephemeral environment
      accounts for about 3 ms: its overlay `.pth` survives `-I`.
    - A plain venv, `sys.path` insertion, and shebang versus `-c` each changed the result by 1 ms or
      less.
    - The experiment is host evidence, not an in-image figure: a different CPU, and no container.
  - **What would make the figure authoritative for the tools' path:** the same test run as the tools
    run, with `/opt/timelike/python/bin/python3 -I` and the precompiled `agentio`. Until then, the
    recorded figure errs on the safe side.
  - The host lane measured 56.7 ms p95 on 3.12 earlier. That is advisory only.
- **Every call concludes (P2):** no call exceeds its configured timeout plus a bounded grace period
  for verdict emission
- **Snapshots (T2):** a snapshot is capped in scope and size. Exceeding the cap produces a
  "not snapshotted: reason" verdict, never a silent skip or an unbounded copy

---

## Code Quality Metrics

```yaml
# Complexity Thresholds
complexity_threshold: 10
max_file_lines: 300       # single-file tools may exceed this with a justification in the feature plan
max_function_lines: 50
max_function_params: 5
```

Lint and type checks must be clean: ruff + `mypy --strict` (Python), `go vet` + staticcheck (Go),
shellcheck (Bash).

---

## Testing Requirements

```yaml
# Test Coverage
require_tests: true
test_types:
  - unit          # Required (pytest, go test)
  - integration   # Required for Adele's Docker filter and provider calls
  - e2e           # Required: bats-core, one test per acceptance criterion

# Test Quality
min_assertions_per_test: 1
max_test_duration: 5000  # milliseconds, unit tests only; see below
require_test_descriptions: true
```

Tests run inside the image, never against the host environment. End-to-end and fault-injection
tests deliberately wait out timeouts, so they are bounded by the timeout under test plus the grace
period above, never by `max_test_duration`. Plan ratified this as governance at discovery revision 3.

---

## Code Review Standards

```yaml
require_code_review: true
min_reviewers: 1   # solo maintainer working with AI: the maintainer reviews AI-written changes
require_tests_for_features: true
require_tests_for_bugfixes: true
```

---

## CI/CD Requirements

```yaml
block_merge_on_failure: false   # plan's revision-5 ruling: the score never blocks a merge (amended 2026-09-29)
require_passing_tests: true
require_lint_pass: true
require_type_check_pass: true   # mypy --strict
```

---

## Security Standards

Strict, from discovery revision 3's Hard constraint (constitution H9, P4).

```yaml
require_security_scan: true
block_on_critical_vulns: true
block_on_high_vulns: true       # High or Critical with a fixed version available blocks merge
max_dependency_age: 365         # days (warn if dependency >1 year old)
```

**Enforcement is the project's, not the plugin's.** No specswarm 2.11.0 command reads these keys.
`/specswarm:ship --security-audit` runs only when that flag is passed, and it scans with `npm
audit` and blocks only on Critical. The keys record the policy. The **Supply-chain scan** gate under
Custom Quality Checks enforces it, using the scanners in `tech-stack.md`. Feature 01 builds that
gate together with the first image.

---

## Documentation Standards

`require_changelog_entry: true` was ratified by plan at discovery revision 3 as governance, not as
a discovery constraint. It supports P6 and developers adopting an MIT project. The other two values
are template defaults.

```yaml
require_readme_updates: false
require_api_docs: false
require_changelog_entry: true
```

---

## Custom Quality Checks

### Boundary and Safety Gates (block merge)

These gates guard P2, P4, P5 and P7. They are pass/fail and do not count toward the score.

- **Isolation (H1/P4):** a test proves that the agent image cannot read Adele's volume, config,
  credentials or the Docker socket
- **Refusals (P4):** cap excess, attempts to modify Adele or its policy, and secret reads are
  refused, and cap excess exits 4 with an escalation (the grant envelope, discovery revision 10)
- **Fault injection (P2):** background child, timeout, memory cap, full `/tmp`, denied host and
  unknown command each yield a verdict naming the cause within the configured bound
- **Output contract (H2):** every agent-side tool passes the `agentio` conformance check
  (`timelike-conform`, C0–C9).
  - **Rules 2 and 3 (discovery revision 6):** a tool that cuts its output prints rule 3's order, and
    only cut output ends on the omission line. Uncapped text ends on its own last result line, and
    JSON carries `exit`, plus `truncated` when capped.
  - That shape is implemented once, in `agentio`, and verified by `agentio`'s unit tests
    (`tests/unit/test_agentio.py`, rule 2 cases). Every tool inherits it through H2.
  - The conformance check does **not** make a tool cut, so it cannot see a tool that bypasses
    `agentio`'s output path. Review catches that.
  - **Exit pass-through (discovery revision 9):** a tool whose manifest declares pass-through is
    also run wrapping a command that exits outside the vocabulary (for example `sh -c 'exit 42'`).
    Its exit, its JSON `command_exit`, and `cause: command` must all name that code, and so must the
    verdict. A probe that only ever exits 0 cannot pass a pass-through tool
  - **Exit-4 envelopes (discovery revision 10):** exit 4 carries a confirmation envelope
    (`status: confirmation_required`, its `confirm` the agent's own command plus `--yes`) or a grant
    envelope (`status: grant_required`: the grant, the exceeded limit, the operator's `extend`
    command, `performed: false`), each validated against its own schema. No envelope's `confirm`
    may name a command outside the agent's own tool. That is a negative case, and the check must be
    shown failing on an envelope that breaks it
  - **Confirmation scope (discovery revision 13):** a manifest declares `confirm_protocol`. Only a
    tool with `confirm_protocol: true` honours `--yes` and exits 4 with a confirmation envelope. A
    tool with `confirm_protocol: false` that overwrites or removes must declare `dry_run: true`. That
    is a negative case, and the check must be shown failing on a manifest that breaks it
- **Build stamp (H8):** the image label and `timelike --agent-info` carry a non-empty git revision
- **Invocation matrix (P2, P7, gap G13):** every environment default is in effect under
  non-interactive `bash -c`, login `bash -lc`, and an interactive shell. A default that lives only
  in an rc file or `PROMPT_COMMAND` passes an interactive check and never fires under a harness
- **Snapshot restore round-trip (P5):** a snapshot the tool reports as taken, when restored, leaves
  the workspace byte-identical to the moment it was taken and the project's own `.git` unchanged.
  Check the restored state, not the tool's success message
- **Host git state (P4; discovery revision 8, Hard constraint):** in any feature that mounts a
  workspace from the operator's host (13 is the first), a test proves that by default the agent's
  writes cannot reach that checkout's untracked git state: `.git/hooks/`, and the `.git/config` keys
  that execute (`core.hooksPath`, `core.fsmonitor`, `core.sshCommand`, `core.pager`, `core.editor`,
  `diff.external`, filter and merge drivers, `!` aliases, `credential.helper`). It also proves that
  the operator's per-workspace lift is visible at launch. Read the host checkout's state, not the
  tool's message
- **Performance budgets:** the three budgets above, run as tests
- **Supply-chain scan (H9, P4; discovery revisions 3–5, 14):** before every merge, scan the images
  (agent and Adele, and the bench's vanilla and driver images when built), their dependencies and the
  repository:
  - `govulncheck` for Adele
  - `pip-audit` for Python dependencies and tooling (timelike's own interpreter)
  - Grype over a Syft SBOM for each image's OS packages and the language packages in it. Since discovery
    revision 14 that includes the agent runtimes in the agent and vanilla images: the agent Python and its
    bundled pip, and Node with npm's bundled dependencies. They go through the same baseline rule as
    everything else; a new finding with no fix is a baseline change, raised for review
  - gitleaks for committed secrets

  A known High or Critical vulnerability with a fix available blocks, and so does any committed
  secret. A finding with no fix available passes only through the reviewed baseline under
  Exemptions. Every scan prints the baseline's one-line summary.

---

## Exemptions

*Request an exemption in the feature plan's complexity tracking, citing the principle it bends.*

| Exemption | Scope | Why | Reviewed | Review by |
|---|---|---|---|---|
| `enforce_gates: false`, `min_quality_score: 0` | `/specswarm:ship` score gate | Plan's ruling (quality-score feedback, § Resolution): the score is informational. From specswarm 2.13.0, `enforce_gates: false` makes a failing or unknown score warn instead of block; up to 2.12.0 no command read the key, and a threshold of 0 was the only lever. Both are kept, and 0 is harmless. The merge bar under Quality Gates replaces the score | 2026-09-28 | when the plugin excludes non-applicable categories |

**Vulnerability baseline (H9, discovery revision 5).** These are not exemption rows. A High or
Critical with no fix available passes only through a **reviewed baseline, one per image digest**,
generated by the scan gate and kept in the repository under `scan/baseline/`. Each baseline:
- lists every identifier with its image, package and origin: the base layer, or the installed
  package that pulled it in (for example `git → libcurl`)
- gives a reason per origin group, and **a separate reason for each Critical**
- carries when a person last reviewed it (`reviewed`) and one review date (`review_by`) **at most
  90 days after `reviewed`**, and is due again whenever the pinned digest moves

**Fix available** means a stable release inside what the stack permits. For a runtime or library,
any stable release inside the stack's version constraint counts, another minor line included. For an
OS package, only the pinned distribution release and its security updates count. A pre-release never
counts. **Severity** is the scanner's standard source. Distribution triage (`no-dsa`, `unimportant`)
may be quoted as a reason, never used to lower a severity.

The review date is enforced. A baseline past its review date, beyond the 90-day cap, or recorded
for a digest other than the one scanned fails the gate until a person reviews it again. **The
baseline never hides a change:** a High or Critical not in the reviewed baseline blocks, and so does
a baselined finding that gains a fix. Every scan prints one line summarising what the baseline
accepts: counts by severity, the digest, and the review date.

**A gate failure is an escalation, never a bare "failed" (T1).** It names:
- the vulnerability identifier
- the affected image and package
- the review date that passed, or the date that exceeds the 90-day cap
- the exact file and field to update: for a fixable finding, the fixed version to upgrade to; for a
  new unfixable finding, the baseline file, and that the baseline must be re-reviewed

---

## Notes

- Quality level: Strict at init (90/90). The score threshold is now 0 by plan's ruling; coverage stays 90
- Created by `/specswarm:init` and enforced by `/specswarm:ship` before merge
- The template's web budgets (bundle size, initial load, chunk size) do not apply to this project
  and were replaced with the budgets above

---

**Quality Enforcement**: These standards are enforced by SpecSwarm commands:
- `/specswarm:ship` - Blocks merge if quality gates fail
- `/specswarm:analyze-quality` - Reports quality score against these standards
- `/specswarm:build` - Can enforce quality gates with `--quality-gate` flag
