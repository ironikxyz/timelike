---
governance_audited_against: [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]
---

<!--
SYNC IMPACT REPORT
- Version change: none (1.4.2 stands; a no-change audit amends nothing)
- Audit against discovery revision 13, no change needed. Source: ../bridge/governance-context.md
  (/mentor:regovern 2026-10-04T23:28:30Z), § "What Changed In Those Revisions", and
  ../bridge/feedback/batch-20261004-232148-rule9-scope-and-workspace-context-file.md § Resolution.
  Revision 13 appended to governance_audited_against: a no-change audit is a recorded result
- What revision 13 moved: one clarification of the Agent output contract's rule 9. Confirmation binds
  a change whose scope the arguments do not name exactly, that touches another agent's or session's
  work, or that cannot be reversed from what the tool shows. A change to an exactly named target,
  applied whole or not at all, that shows what it changed, is not confirmed: such a tool declares
  mutating: true and confirm_protocol: false, and rule 8 (--dry-run) still binds it when it overwrites
  or removes
- Checked: no article restates rule 9 as "every mutating tool confirms" or makes --yes required of
  every tool that changes a file. H2 describes the confirmation envelope's shape (the agent's own
  command plus --yes), not when it is required, so it holds under revision 13 as written. H3 and H4 do
  not mention confirmation
- WHY principle statements P1–P7 and tensions T1–T4: checked, unchanged (per the evidence section)
- HOW H1–H9: checked, unchanged
- Dependent artifacts: tech-stack.md audited, no change (stack.md unchanged); quality-standards.md
  audited, amended (the H2 gate gains one bullet: confirm_protocol: false with an overwriting or
  removing tool requires dry_run: true). In flight: 008-edit (06 s0) carries confirm_protocol in 001's
  schema, agentio and timelike-conform in its cycle, not here
- Deferred TODOs: none

- Version change: none (1.4.2 stands; a no-change audit amends nothing)
- Audit against discovery revision 12, no change needed. Source: ../bridge/governance-context.md (/mentor:regovern 2026-10-04T08:54:45Z), § "What Changed In Those Revisions", and
  ../bridge/feedback/05-20261004-062732-view-search-rule3-and-byte-bound.md § Q3.
  Revision 12 appended to governance_audited_against: a no-change audit is a recorded result
- What revision 12 moved: one clarification of the Agent output contract's rule 13. The line cut
  applies in both modes; in JSON it cuts each content string a tool emits, with the same marker, and
  carries the cut byte count as data. A long line is read whole only on explicit request
- Checked: no article restates rule 13 (the line cut or ANSI stripping) as text-only or names a JSON
  exemption. H2 points at the output contract rather than restating its rules (as at revisions 10 and
  11). H3 and H4 do not mention output shape
- WHY principle statements P1–P7 and tensions T1–T4: checked, unchanged (per the evidence section)
- HOW H1–H9: checked, unchanged
- Dependent artifacts: tech-stack.md audited, no change (stack.md unchanged since 0f6e1ed);
  quality-standards.md audited, no change (no gate restates rule 13). In flight: 006-bounded-read
  (05 s0) carries the agentio change and 001's contract-text sentence in its cycle, not here
- Deferred TODOs: none

- Version change: none (1.4.2 stands; a no-change audit amends nothing)
- Audit against discovery revision 11, no change needed. Source: ../bridge/governance-context.md
  (/mentor:regovern 2026-10-04T00:24:17Z), § "What Changed In Those Revisions", and
  ../bridge/feedback/07-20261003-022613-snapshot-store-and-persistence.md § Resolution. Revision 11
  appended to governance_audited_against: a no-change audit is a recorded result
- What revision 11 moved: the Agent output contract's rule 10 is revised (two state locations, a
  per-session scratch directory and a per-workspace state root outside the workspace; the
  in-workspace project cache is withdrawn), and stack.md's Snapshots and P5 rows move from git to a
  stdlib content-addressed store
- Checked: no article restates rule 10's state locations or the project cache. H2 points at the
  output contract rather than restating its rules (as at revision 10). P5 and T2 name no store
  technology, and their text did not move (the ruling rests on both). H5 (stdlib-first) already
  covers the stdlib store
- WHY principle statements P1–P7 and tensions T1–T4: checked, unchanged (per the evidence section)
- HOW H1–H9: checked, unchanged
- Dependent artifacts: tech-stack.md amended at this audit (its git line said "snapshots, shadow
  store"; stack.md's Snapshots row now names the stdlib store); quality-standards.md audited, no
  change (no gate restates rule 10). In-flight: 005-recover (07 s0) records revision 11 in its own
  modify cycle; 001's contract wording for rule 10 changes in 07 slice 1
- Deferred TODOs: none

- Version change: 1.4.1 → 1.4.2 (PATCH: H2 names exit 4's two envelopes; a clarification)
- Audit against discovery revision 10, amended. Source: ../bridge/governance-context.md
  (/mentor:regovern 2026-10-02T05:50:50Z), § "What Changed In Those Revisions", and
  ../bridge/feedback/12-20261002-054636-grant-envelope.md § Resolution. Revision 10 appended to
  governance_audited_against
- Modified: H2 gains revision 10's envelope sentence. Exit 4 carries a confirmation envelope (the
  agent's own command plus --yes) or a grant envelope (the grant, the exceeded limit, the operator's
  extend command, nothing performed), told apart by `status`; an operator's command never appears in
  a field the agent's habit runs. H2's example "4 = cap exceeded, with escalation" named only the
  grant case; without the sentence it reads as if exit 4 had one shape
- Not added to H2: "a client Adele brokers is not --yes-confirmed by the agent" and rule 8. They are
  contract-level detail (001's output-contract.md § Confirmation and the adele client), and H2 points
  at the contract rather than restating its rules; P4's grant text (l.192) already says cap excess
  exits 4 naming the grant and how the operator extends it
- WHY principle statements P1–P7 and tensions T1–T4: checked, unchanged (revision 10 touches only the
  Agent output contract soft constraint, per the evidence section; the ruling cites T1 and P4, whose
  text did not move)
- HOW H1, H3–H9: checked, unchanged
- Dependent artifacts: ✅ quality-standards.md (the Output contract gate gains the grant-envelope
  check and its negative case); tech-stack.md audited, no change (stack.md unchanged since d606ed1).
  In-flight features: 004-adele-grants (12 s0) carries the contract, schema, agentio and conformance
  changes in its Cycle 2, not here
- Deferred TODOs: none

- Version change: 1.4.0 → 1.4.1 (PATCH: H2 states the exit vocabulary's scope; a clarification)
- Audit against discovery revision 9, amended. Source: ../bridge/governance-context.md
  (/mentor:regovern 2026-10-01T04:32:58Z), § "What Changed In Those Revisions", and
  ../bridge/feedback/03-20260930-235857-exit-pass-through.md § Resolution. Revision 9 appended to
  governance_audited_against
- Modified: H2 gains revision 9's scope sentence. The exit-code vocabulary is a tool's own outcomes;
  a tool that runs a command the agent named passes that command's exit through and declares it. H2's
  existing sentence ("Exit codes are part of the contract") stays true; without the scope it could be
  read as the unconditional form plan found in 001's contract (line 83)
- WHY principle statements P1–P7 and tensions T1–T4: checked, unchanged (revision 9 touches only the
  Agent output contract soft constraint, per the evidence section)
- HOW H1, H3–H9: checked, unchanged
- Dependent artifacts: ✅ quality-standards.md (the Output contract gate gains the pass-through
  exercise); tech-stack.md audited, no change (stack.md 0 lines). In-flight features: none; 03 is
  specified after this audit. The contract text, schema, agentio and conformance C6 changes arrive
  through 03's cycle, not here
- Deferred TODOs: none

- Version change: 1.3.0 → 1.4.0 (MINOR: P4 gains guidance for deferred reach, and T4 is clarified)
- Audit against discovery revision 8, amended. Source: ../bridge/governance-context.md
  (/mentor:regovern 2026-09-30T06:15:21Z), § "What Changed In Those Revisions", and the three feedback
  resolutions it cites. Revision 8 appended to governance_audited_against
- Modified: T4 takes discovery's clarifying sentence, verbatim (the limit holds in the environment
  timelike provides; under `env -i`, git's own behaviour, and P2 rests on feature 03's concluding run
  and the harness's timeout). P4 gains one bullet: revision 8's new Hard constraint names a write into
  the operator's checkout's untracked git state "deferred reach (P4)"
- WHY principle statements P1–P7 and tensions T1–T3: checked, unchanged (no statement moved in
  revision 8, per the evidence section)
- HOW H1–H9: checked, unchanged. H1's boundary (only Adele reaches beyond the environment) already
  covers it; the constraint is enforced per feature (13 is the first that mounts a workspace), and
  gated in quality-standards
- Dependent artifacts: ✅ quality-standards.md (a Boundary gate for the host-git-state constraint,
  applying from the first feature that mounts a workspace); tech-stack.md audited, no change (stack.md
  0 lines). In-flight features: none (001 and 002 merged). 01's README line and `env -i` test, 02 slice
  1's verdict order and 13's criterion arrive through later sends, not here
- Deferred TODOs: none

- Version change: 1.2.0 → 1.3.0 (MINOR: a tension resolution added, materially expanding guidance)
- Audit against discovery revision 7, amended. Source: ../bridge/governance-context.md
  (/mentor:regovern 2026-09-29T09:40:34Z), § "What Changed In Those Revisions", and
  ../bridge/feedback/02-20260929-092443-hooks-off-default.md § Resolution. Revision 7 appended to
  governance_audited_against
- Added: tension T4 (P1 vs P2, a project's own check that is slow, hangs or rejects) to the tension
  table, copied from discovery's resolution; P1 and P2 each name it, as P1 names T1
- WHY principle statements P1–P7 and tensions T1–T3: checked, unchanged (no statement moved in
  revision 7, per the evidence section)
- HOW H1–H9: checked, unchanged. No text states the old hooks-off default (grep -i hook finds none).
  H4 (non-interactive by construction) is compatible: a bounded hook with a verdict is non-interactive
- Dependent artifacts: tech-stack.md audited, no change (stack.md unchanged, 0 lines);
  quality-standards.md audited, no change (revision 7 touched no Constraints section). ⚠ In-flight:
  feature 001 (research R3 "hooks off", SC-3's hooks clause, the hooks test) and feature 002 (the two
  hook tasks' texts and expected verdicts) change through the 01 modify send
  (bridge/sends/01-rev7-20260929-094055.md), not here
- Deferred TODOs: none

- Audit against discovery revision 6, no amendment (version unchanged at 1.2.0). Source:
  ../bridge/governance-context.md (/mentor:regovern 2026-09-28T23:08:03Z), § "What Changed In Those
  Revisions", and ../bridge/feedback/01-20260928-225646-uncapped-last-line.md § Resolution. Revision 6
  was appended to governance_audited_against: checked, and no change was needed
- WHY principles P1–P7 and tensions T1–T3: checked, unchanged (byte-identical in revision 6, per the
  evidence section)
- H2 · One output contract: checked, unchanged. Revision 6 clarifies contract rules 2 and 3: rule 3's
  order is the shape of output a tool cuts, and uncapped output ends on its own last line. H2 does not
  restate rules 2 or 3, and it already routes every tool through agentio, which implements the shape.
  Naming the distinction here would duplicate the contract (contracts/output-contract.md)
- Dependent artifacts: ✅ quality-standards.md (the Output contract gate now says what verifies the cut
  shape); tech-stack.md checked, no change (stack.md unchanged). In-flight feature 001:
  contracts/output-contract.md states the uncapped case (plan's wording change, cycle 4)
- Deferred TODOs: none

Previous report (1.2.0):
- Version change: 1.1.1 → 1.2.0 (MINOR: materially expanded principle)
- Source: audit against discovery revision 5, via ../bridge/governance-context.md (/mentor:regovern
  2026-09-28T13:13:20Z) and ../bridge/feedback/01-20260928-130206-supply-chain-exemptions.md
  § Resolution. Revision 5 appended to governance_audited_against: checked against it and amended
- WHY principles P1–P7 and tensions T1–T3: checked, unchanged (byte-identical in revision 5)
- Modified principle: H9 replaces per-vulnerability exemptions with a reviewed baseline per image
  digest (a reason per origin group, one review date at most 90 days out and again on every digest
  move, a separate reason for each Critical). The baseline never hides a new or newly fixable
  finding. H9 also defines "fix available" (a stable release inside the stack's constraint,
  another minor line included for runtimes; for OS packages only the pinned distribution release
  and its security updates; never a pre-release) and keeps severity with the scanner's source
- Not in this file: the quality-score ruling (../bridge/feedback/01-20260928-130206-quality-score.md)
  is governance-only and lives in quality-standards.md. No principle referred to the score
- Dependent artifacts: ✅ quality-standards.md (baseline rule, score informational, merge bar);
  ✅ tech-stack.md (Python pin 3.14.x, stack notes 15 and 16). In-flight feature 001:
  scan/evaluate.py, pins.env and image/Dockerfile follow in the 001 cycle for this send
- Deferred TODOs: none

Previous report (1.1.1):
- Version change: 1.1.0 → 1.1.1 (PATCH: clarification)
- Source: audit against discovery revision 4, via ../bridge/governance-context.md (/mentor:regovern
  2026-09-28T06:40:04Z) and ../bridge/feedback/gov-20260928-063634.md. Revision 4 appended to
  governance_audited_against: checked against it and amended
- WHY principles P1–P7 and tensions T1–T3: checked, unchanged (byte-identical in revision 4)
- Modified principle: H9 now states that the review date is enforced (at most 90 days after the
  last review), and that a gate failure is an escalation naming what to change and where
- Dependent artifacts: ✅ quality-standards.md (90-day cap, Reviewed column, escalation fields);
  tech-stack.md checked, no change. In-flight feature 001: scan/evaluate.py implements the rule
- Deferred TODOs: none

Previous report (1.1.0):
- Version change: 1.0.1 → 1.1.0 (MINOR: new HOW principle)
- Source: audit against discovery revision 3, via ../bridge/governance-context.md (/mentor:regovern
  2026-09-28T06:26:58Z) and ../bridge/feedback/gov-20260928-061535.md. Revision 3 appended to
  governance_audited_against, since this file was checked against it and amended
- WHY principles P1–P7 and tensions T1–T3: checked, unchanged (byte-identical in revision 3)
- Added principle: H9 · Sound supply chain, from revision 3's new Hard constraint (scanning before
  merge), which bears on P4
- Struck soft constraint (static single binaries for hot-path tools): no effect here. H5 already
  records Python agent-side and Go only for Adele
- Dependent artifacts: ✅ tech-stack.md (scanners, Adele base image), ✅ quality-standards.md
  (security keys, supply-chain gate, exemption rule). No in-flight features
- Deferred TODOs: none

Previous report (1.0.1):
- Version change: 1.0.0 → 1.0.1 (PATCH: clarification)
- Source: ../bridge/feedback/stack-review-2026-09-28.md (plan's review of init choices). Not a
  discovery revision, so governance_audited_against is unchanged
- Modified principles: H8 now names the Python type checker (`mypy --strict`, review item C1)
- Companion changes: tech-stack.md (C1), quality-standards.md (C1, C2, Adele integration
  coverage, gates G-a and G-b)
- Deferred TODOs: none

Previous report (1.0.0):
- Version change: (none) → 1.0.0 (initial ratification)
- Principles added: P1–P7 (WHY, from discovery revision 2 via ../bridge/governance-context.md),
  H1–H8 (HOW, derived from the recommended stack and its notes for the code instance)
- Tension resolutions added: T1–T3
- Sections added: WHY — Governing Principles, HOW — Core Coding Principles, Governance
- Sections intentionally omitted: UX — Interaction Principles (no user-facing GUI; the
  agent-facing output contract is governed by H2)
- Templates requiring updates: none present in this repository (plugin ships no templates)
- Deferred TODOs: none
-->

# Timelike Constitution

Timelike is a containerised shell environment that lets a coding agent take work to a verified
result from bash, non-interactively, reaching beyond its environment only under grants that an
authority it cannot alter (Adele) enforces.

## WHY — Governing Principles

These come from discovery (revision 5; unchanged since revision 2), relayed through
`../bridge/governance-context.md`. They
are non-negotiable. Every feature traces to at least one of them.

### P1 · Unaided completion

Anything the operator could do from a shell to take work to a verified result, the agent MUST be
able to do from bash non-interactively. Where it cannot, it MUST be told exactly why and who can
unblock it (what, why, which grant, the operator's exact command).

- **Test:** Every bench task ends completed or in a named escalation. It never ends in a hang, a
  silent dead end, or a request for manual setup.
- Yields to P4 (T1). Boundary with P2 over a project's own checks (T4).

### P2 · Every call concludes

No command may block indefinitely or end without a verdict naming its outcome and cause. That
includes timeout, memory kill, disk full, network denial, a detached child, and a missing command.

- **Test:** A fault-injection suite (background child, sleep past timeout, memory cap, full `/tmp`,
  denied host, unknown command) yields a verdict naming each cause within a bounded time.
- Boundary with P1 over a project's own checks (T4): P2 is met by a bounded run and its verdict, never
  by skipping the check.

### P3 · Found where agents look

A capability the agent does not find unprompted does not exist. Capabilities MUST be announced in
the places agents already read and named after habits agents were trained on.

- **Test:** In a bench arm where the agent is told nothing about timelike, timelike tools appear in
  the traces. Adoption is reported against a "told" arm.
- Context boundary with P7 (T3).

### P4 · Reach only by grant

Actions confined to the environment need no grant. Any action that reaches beyond it (daemons,
providers, networks, remote models, money) MUST run under an explicit, capped, expiring grant.
An authority the agent cannot alter enforces the grant. The agent can use granted credentials but
can never read them.

- **Test:** Attempts to exceed a cap, modify Adele or its policy, or read a secret are all refused.
  A cap excess exits 4 with an escalation naming the grant and how the operator extends it.
- Wins over P1 (T1). Standing grants (e.g. the default egress allowlist) are still grants:
  explicit, visible, revocable.
- **Deferred reach** *(discovery revision 8, Hard constraint)*: a write that later executes on the
  operator's host outside anything the operator reviews is reach, even though nothing leaves the
  environment when it is written. In a workspace that is a host directory, that means the checkout's
  untracked git state: `.git/hooks/`, and `.git/config` keys that execute. By default the agent's
  writes never reach it; the operator may lift that per workspace at launch, visibly, as a standing
  grant. Tracked files that host tools execute are in the diff, and are the operator's to review.

### P5 · Wrong turns are recoverable

The agent MUST be able to return any change it makes inside the environment to a prior state.
Every reaching action MUST record what is needed to undo it.

- **Test:** Replays of the documented incident classes (recursive delete via script, `reset --hard`
  with uncommitted work, overwrite-by-move) each end with the agent restoring the prior state.
- Context boundary with P2 (T2). Recovery is never implied silently.

### P6 · Claims are measured

Claims about timelike's value are made only from reproducible comparisons against a vanilla
environment, in completions, turns and failures, with losing cases shown first.

- **Test:** Every value claim in public docs traces to a bench result with the command to
  reproduce it.

### P7 · Harness-agnostic

Capabilities MUST live in the shell environment, not in any one harness's extension points.

- **Test:** The same task catalog passes under at least two harnesses.
- Context boundary with P3 (T3).

### Tension resolutions

| # | Tension | Resolution |
|---|---|---|
| T1 | P1 vs P4 | **P4 wins.** P1 is satisfied by a named escalation (what, why, which grant, the exact command to extend it). |
| T2 | P5 vs P2 | **Boundary.** Snapshots have a capped scope and size. Beyond the cap the verdict names what was not snapshotted and why. P2 wins on latency. |
| T3 | P3 vs P7 | **Boundary.** Announcements may be written into any harness's context files. Nothing may *work* only through them. |
| T4 | P1 vs P2 — a project's own check (a git hook, for example) is slow, hangs or rejects | **Boundary.** The environment never silently removes a project's own check. It runs the check under a time limit; beyond the limit the verdict names the check, the limit and how to raise it. P2 is met by that verdict, not by skipping the check. The agent may still skip a check itself, visibly, in its own command; the environment never suggests it. *(Added at discovery revision 7.)* The limit holds in the environment timelike provides. An agent or tool that discards that environment (for example `env -i`) gets git's own behaviour, as without timelike; the check still runs, and P2 then rests on feature 03's concluding run and the harness's own timeout. *(Clarified at discovery revision 8.)* |

## HOW — Core Coding Principles

### H1 · Two components, one boundary

`image/` and `tools/` (Python, Bash) run inside the agent's environment. `adele/` (Go) is the only
component that reaches beyond it. Nothing in the agent image may read Adele's volume, config or
credentials, and only Adele holds the Docker socket. Tests MUST enforce this boundary. It is not
a convention. *(P4)*

### H2 · One output contract

Every agent-side tool emits its verdict through the shared `agentio` module. The verdict gives
the outcome, the cause and, where applicable, the escalation. `agentio` and its conformance check
MUST exist before the first tool. Exit codes are part of the contract (e.g. 4 = cap exceeded,
with escalation). The vocabulary covers a tool's **own** outcomes: a tool that runs a command the
agent named passes that command's exit through (126, 127 and 128+n included), returns 124 only when
its own limit fired, and declares the pass-through in its manifest; the verdict and a JSON `cause`
tell its outcomes from the command's. Exit 4 carries one of two envelopes, told apart by `status`:
a **confirmation** envelope, whose command is the agent's own plus `--yes`, or a **grant** envelope,
naming the grant, the exceeded limit and the operator's extend command, with nothing performed. An
operator's command never appears in a field the agent's habit runs. *(P1, P2, P4, T1; scope
clarified at discovery revision 9, exit-4 envelopes at revision 10)*

### H3 · Verify artifacts, not messages

A tool says "started", "deployed" or "restored" only after it has checked the resulting state.
Reachability probes MUST name their vantage point. *(P2, P6)*

### H4 · Non-interactive by construction

Defaults MUST reach `bash -c` and `bash -lc`, not only interactive shells. That means Dockerfile
`ENV`, `BASH_ENV` and system gitconfig, not rc files alone. Each invocation style is tested
separately. Nothing may block on a prompt, a pager or a backgrounded child's open pipe.
*(P1, P2)*

### H5 · Stdlib-first, pinned interpreter

Agent-side tools are single-file Python on the stdlib where practical, with
`#!/opt/timelike/python/bin/python3 -I`. They never use the system Python or an agent venv.
Adele is static Go (`CGO_ENABLED=0`) on the stdlib where practical. A third-party dependency
MUST be justified in the feature's plan and added to `tech-stack.md`. *(P4, P7)*

### H6 · No hidden machinery

There is no MCP, no LLM in deterministic tiers, and no daemons in tools. Capabilities are shell
commands that any harness can call. *(P7, P3)*

### H7 · Every acceptance criterion is a test

Each acceptance criterion becomes a test named after its distinguishing text: bats-core end to
end in the image, pytest for Python units, `go test` for Adele. A criterion that cannot be
automated is marked Manual and stays visible as unconfirmed until someone observes it. *(P6)*

### H8 · Stamped and typed

Builds stamp the git revision into the image label and `timelike --agent-info`. An empty stamp is
a failure. Python is fully type-annotated and passes `mypy --strict`. Go passes `go vet`. Bash passes
`shellcheck`.

### H9 · Sound supply chain

timelike's own artifacts MUST be scanned before every merge: both images (agent and Adele), their
dependencies, and the repository. A known High or Critical vulnerability with a fix available
blocks the merge. "Fix available" means a stable release inside what the stack permits: for a
runtime or library, any stable release inside the stack's version constraint, including another
minor line; for an OS package, only the pinned distribution release and its security updates. A
pre-release never counts. Severity is the scanner's standard source. Distribution triage (e.g.
Debian `no-dsa`) may be quoted as a reason, never used to lower a severity.

A High with no fix available passes only through a reviewed **baseline** generated per image
digest. It lists every identifier with its image, package and origin (the base layer, or the
installed package that pulled it in), gives a reason per origin group, and carries one review
date, at most 90 days after the last review and due again whenever the pinned digest moves. A
Critical with no fix available carries its own reason. The review date is enforced: a baseline
past it, beyond the 90-day cap, or for a digest other than the one scanned fails the gate until a
person reviews it again. **The baseline never hides a change:** a High or Critical not in the
reviewed baseline blocks, and so does a baselined finding that gains a fix. Every scan prints a
one-line summary of what the baseline accepts (counts by severity, digest, review date).

A gate failure is an escalation, never a bare "failed": it names the identifier, the image and
package, the date concerned, and the exact file and field to update; for a new finding, the
baseline file and that it must be re-reviewed (T1). A committed secret blocks the merge. Adele's
image is built `FROM scratch` or distroless static, so it carries almost no OS packages to scan.
*(P4: every grant depends on Adele and the agent image being sound. Discovery revision 3, Hard
constraint; clarified in revision 4; refined in revision 5.)*

## Governance

- **Authority:** This constitution overrides conflicting guidance in specs, plans or tasks. WHY
  principles change only through discovery (`plan/`), relayed via the bridge. They are never
  edited here directly.
- **Amendment procedure:** HOW principles may be amended in `code/` with a Sync Impact Report and
  a version bump. A WHY change arrives as a new discovery revision and is applied by a governance
  re-derivation (`/mentor:regovern`, then a re-derivation in `code/`).
- **Versioning:** Semantic. MAJOR for principle removals or redefinitions, MINOR for additions or
  material expansions, PATCH for clarifications.
- **Provenance:** `governance_audited_against` lists the discovery revisions checked against this
  file. Append a revision only when it was actually checked. Reset on a from-scratch
  re-derivation. Preserve verbatim on every other edit.
- **Compliance review:** `/specswarm:plan` runs a Constitution Check against P1–P7 and H1–H9.
  A violation MUST be justified in the plan's complexity tracking or the design MUST change.

**Version**: 1.4.2 | **Ratified**: 2026-09-28 | **Last Amended**: 2026-10-02
