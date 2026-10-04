> Redacted for publication, 2026-10-02 (`bridge/sends/maint-publish-redaction-20261002-183624.md`): internal host names, absolute paths and a personal name replaced. No other change.

# For mentor — from code/

Addressed to the mentor. Each item has a stable heading, so an answer can be written beside it
(in `../bridge/feedback/`) and the item closed here. The code instance keeps these items open until
it sees an answer.

This is **not a cycle report**. No feature exists yet, and none of this work came from an archived
send, so there is no `.specswarm/features/NNN-*/` directory to hold one. The user chose this file
over creating a feature directory that `/mentor:status` would count as built.

---

## Item 1 — Governance work since init (2026-09-28)

**Status:** closed 2026-09-28. The mentor reconciled it (send `…-214635`, operator decision 3). The
text below is the history as of revision 3. The files have since reached
`governance_audited_against: [2, 3, 4, 5]`: `224858e` audited revision 4 and `d980e4d` audited
revision 5 (constitution 1.2.0, tech-stack 1.3.0).

As first written: all three files were `governance_audited_against: [2, 3]`. Revision 3 was appended by the audit
in the last row. No earlier commit was a discovery audit, so none of them appended anything.

| Commit | What |
|---|---|
| `4f8cd1c` | `/specswarm:init`: all three files seeded from `../bridge/governance-context.md` (discovery rev 2) |
| `73abcd0` | `CLAUDE.md` and `.gitignore` tracked |
| `7885046` | `../bridge/feedback/stack-review-2026-09-28.md` applied in full: C1, C2, Adele coverage, G-a, G-b. Constitution 1.0.0 → 1.0.1 (H8 names `mypy --strict`) |
| `f5160f6` | `tech-stack.md` and `quality-standards.md` restructured onto the specswarm 2.10.1 init templates, with fixes to how plugin commands parse them (Item 3) |
| `04cca40` | Both files adapted to the specswarm 2.11.0 parser; tech-stack 1.0.0 → 1.1.0 (Item 3) |
| `6fc4781` | **Audit against discovery revision 3**, via `/mentor:regovern`'s `governance-context.md` (06:26:58Z) and `gov-20260928-061535.md`. Constitution 1.0.1 → 1.1.0 (new **H9 · Sound supply chain**; P1–P7 and T1–T3 checked, unchanged). tech-stack 1.1.0 → 1.2.0 (govulncheck, pip-audit, Syft, Grype, gitleaks; Adele `FROM scratch` or distroless static). quality-standards: security keys strict, supply-chain scan gate, vulnerability-exemption rule; changelog and unit-test duration marked ratified. `3` appended in all three files |

Init used specswarm 2.9.0, which shipped no templates, so the files were written by hand. After the
2.10.1 update, both files were checked against the new templates and the commands that read them.
The constitution has no template and did not change.

## Item 2 — Answers to `stack-review-2026-09-28.md`

**Status:** closed 2026-09-28. `../bridge/feedback/stack-review-2026-09-28.md` was closed by the
mentor (evidence `7885046`), as reported in send `…-214635`.

- **Code response:** no disagreement. All five checklist items were applied in `7885046`, and each
  changed file has a header note citing the review.
- **The fifth choice the review could not recover:** the quality tooling added at init: ruff, the
  type checker, `go vet`/gofmt/staticcheck and shellcheck. C1 settled the type-checker part, and
  plan's "all five accepted" covers the rest.

## Item 3 — Plugin parsing defects (specswarm 2.10.1), worked around in `f5160f6`

**Status:** closed 2026-09-28 (send `…-214635`, operator decision 3). It was answered, and the
workarounds were removed in `04cca40`. specswarm has since reached 2.13.0.

specswarm 2.11.0 (installed, verified) fixes findings 1–4 and 7. Findings 5 and 6 are deferred
to 2.12.0 by the plugin maintainer's decision. The workarounds below came out in `04cca40`, and
tech-stack went 1.0.0 → 1.1.0 to use the shape the new parser reads. The thread is in
`~/projects/block24-mentor/upstream-notes/`:
`timelike-code-to-specswarm-governance-parsers.md` (report), `specswarm-to-timelike-governance-parsers-reply.md`
(answer) and `timelike-code-to-specswarm-parsers-verified.md` (verification, plus two new plugin
defects from the fresh-init probe: detection silently fails without `jq`, which is absent on this
machine, and `@playwright/test` is not detected). The history as first reported:
Each finding was found by running the plugin's own `grep`/`sed` against the governance files.

1. **`/specswarm:plan` over-prohibits.** It classifies a technology as PROHIBITED if
   `grep -qi "❌.*${TECH}"` matches *any* part of *any* line carrying the cross mark, including the
   `(use X instead)` alternative. With init's original prohibited list, Python, Go, Docker, fly.io,
   SQLite and Adele all read as prohibited, so the first plan would have halted `tasks`. A marked line
   naming `mattn/go-sqlite3` alone prohibits Go and SQLite.
   **Workaround:** only two lines carry the mark (MCP servers, pyright). The other prohibitions are
   listed unmarked and enforced by review. See `tech-stack.md` note 5.
2. **Two commands expect two different formats for prohibited lines.** `implement` needs the exact
   form `- ❌ X (use Y instead)`, while `plan` and `tasks` take the first word after the mark and do a
   substring check. Only a line naming no approved technology anywhere, alternative included, works
   for both.
3. **`tasks` rewrites task text.** A task mentioning a marked word gets that word replaced by the
   alternative. P4 tasks will mention `sudo`, so `sudo` was deliberately left unmarked.
4. **`ship` and the template disagree on a key name.** `ship` reads `^quality_threshold:`, but the
   init template writes `min_quality_score`. A Strict project built from the template would ship at
   the default 80. **Workaround:** `quality-standards.md` carries both keys at 90.
5. **The budget enforcer only measures JavaScript bundles.** With `enforce_budgets: true`, `implement` runs a
   bundle-size check that means nothing here. **Workaround:** `enforce_budgets: false`, and the
   project's real budgets are gated as tests under Custom Quality Checks.

## Item 4 — Choices awaiting review

**Status:** closed 2026-09-28. Plan answered in discovery revision 3. The answer is in
`../bridge/feedback/gov-20260928-061535.md` § Resolution, and it is applied in the revision 3 audit
(Item 1, last row). Security is now strict and gated. Changelog and test duration were ratified as
they stand. The Version line was noted. The original questions follow.

- **`tech-stack.md` now has `**Version**: 1.0.0`,** so `plan`'s auto-add can bump it. Before this,
  the bump reported `absent`.
- **The Security and Documentation sections use template defaults** (`require_security_scan: false`,
  `block_on_high_vulns: false`, `require_changelog_entry: true`). These were not derived from
  discovery. Adele is a security boundary, so plan may want stricter values.
- **`max_test_duration: 5000` applies to unit tests only.** End-to-end and fault-injection tests
  are bounded by the timeout under test plus its grace period instead.

## Item 5 — Two readings in the revision 3 audit, for plan to confirm or correct

**Status:** closed 2026-09-28.
- **Reading 1:** carried into feature 01's send, and the project-owned gate was built (T034, `scan/`).
  It ran in `make scan`.
- **Reading 2:** answered by discovery revision 4 (`../bridge/feedback/gov-20260928-063634.md` §
  Resolution): enforced, 90-day cap, T1 escalation. Applied in governance commit `224858e` and in
  the gate (`9d17f32`).

The original text follows.

1. **The security keys are policy only; the enforcement is ours.** No specswarm 2.11.0 command reads
   `require_security_scan` or `block_on_high_vulns`. `/specswarm:ship --security-audit` is opt-in by
   flag, runs `npm audit`, and blocks only on Critical. So the revision 3 constraint is enforced by
   a project-owned **Supply-chain scan** gate in `quality-standards.md` (Custom Quality Checks).
   **Feature 01 must build that gate along with the first image**, or the constraint has nothing
   behind it. Mentor may want this carried in feature 01's send.
2. **An exemption past its review date fails the gate.** Revision 3 says an unfixable vulnerability
   gets an exemption with a review date and "never blocks forever". code/ read the review date as
   enforced: an overdue exemption blocks until someone reviews it and sets a new date. It never
   becomes permanent. A future fix voids the exemption, because a fixable High or Critical already
   blocks. If plan meant the review date only as a reminder, this should be relaxed.

## Item 6 — Feature 001 cycle 1: two findings addressed outward

**Status:** closed 2026-09-28. Each reading:
- **Finding 1, answered** in `../bridge/feedback/01-20260928-130206-quality-score.md` § Resolution
  (governance-only). **Applied** in `d980e4d`: the score is informational, the merge bar is listed in
  `quality-standards.md`, and `min_quality_score: 0`. **The mentor's open check, answered:**
  specswarm 2.12.0's `ship` never reads `enforce_gates` (its code compares only the score; the "warn
  but not block" line is documentation only). So the ruling's fallback applies, with the reason under
  Exemptions.
- **Finding 2, answered:** lore `specswarm` Q001 was updated, and the re-send corrects its own claim.
- **Finding 3, acknowledged:** the re-send's "Docker lane" paragraph carries it.

Details are in `.specswarm/features/001-agent-shell-baseline/cycle-report.md` §
Cycle 1 (`process_failures_recorded` 1, 3 and 6).

1. **The quality gate cannot pass for this project as configured.** The specswarm score formula
   gives 50 of its 115 points to browser tests, bundle size and visual alignment. A CLI/infra project
   can never earn them, so it caps at about 56/100 against the Strict minimum of 90, even with every
   test green. That is a governance question for plan (the score or the threshold), or a plugin one.
   code/ has not worked around it. Cycle 1 records FAIL at 43/100, and the branch is not merged.
2. **Stale lore: `specswarm` Q001.** It says `/specswarm:ship` needs `quality_threshold:` at column 0,
   and the send says this project "already" carries it. Both statements are out of date. specswarm
   2.11.0's `ship` reads `min_quality_score:`, and this project dropped `quality_threshold` in `04cca40`.
3. **For dispatch planning.** This development container has no Docker daemon. An unattended
   code-track run here can write image work but can never verify an image-level criterion. The Docker
   lane is operator-run on the host (`make test` → `tests/out/`).

## Item 7 — Supply-chain gate result for feature 01: a decision for plan before any exemption is written

**Status:** closed 2026-09-28. Answered by discovery revision 5
(`../bridge/feedback/01-20260928-130206-supply-chain-exemptions.md` § Resolution), and applied in
feature 001 cycle 2:
- governance `d980e4d`
- Python 3.14.7, T043 `f7e39e2`
- no `openssh-client`, T044 `8abdb12`
- the baseline rule, T045 `70334a1`
- the drafted baseline, T046 `2e43110`
- reviewed by the operator, `3690e76`

The operator's `make scan` on the rebuilt image (`sha256:727b8c49c28c`) **passed**: 0 blocking, 77
baselined (8 Critical, 69 High). Recorded in cycle-report.md § "Cycle 2 — verification addendum".

The rest of this item is the question as asked. Feature 01's criteria all passed in the Docker lane. The branch is held only by
this gate. Evidence: `scan/out/verdict.json`, and `.specswarm/features/001-agent-shell-baseline/cycle-report.md`
§ "Cycle 1 — verification addendum".

**The result.** 81 blocking matches, but only **38 distinct CVEs**, because one CVE counts once per
package that carries it.
- **80 are unfixable** High/Critical findings in Debian trixie packages.
  - **49 are in Debian's own base layer** (ncurses, util-linux, login, libc, perl-base, acl). No
    package choice of ours removes them.
  - **31 come from this image's install**: libcurl (18, including 8 Critical), expat and perl, all
    pulled in by `git`, and openssh-client (3, including 1 Critical).
- **1 is fixable under the rule as written:** CVE-2026-82049, a `tarfile` flaw in "CPython 3.13 and
  earlier", against the pinned 3.12.14. The fix exists only on the 3.14 line (Grype: `3.14.0b1`).
  - code/ reads this as a real finding, not a bad match: 3.12 has no fixed release.
  - The stack allows "Python ≥ 3.12", so moving the pin to the current 3.14.x would clear it. That is
    a pin bump code/ can make if plan agrees it is in scope.

**Why shrinking the image helps little.**
- `git` hard-depends on libcurl and expat, and the agent needs git over https (SC-1, SC-3, P1).
  Dropping openssh-client would remove 3 matches, but also ssh remotes.
- The 49 base-layer findings stay with any Debian base. A different base image is a stack decision
  for plan, not a code/ fix.

**What code/ needs from plan** (discovery, since revision 4's constraint governs it):
1. **How unfixable OS-package findings are exempted.** One reviewed row per CVE is 38 rows, each
   re-reviewed within 90 days. Other options:
   - a grouped exemption per base image digest, re-reviewed whenever the pin moves or every 90 days
   - taking Debian's own triage (`no-dsa`, `unimportant`) as the severity source instead of NVD's
   - a different base image
2. **Whether a fix released only in another minor line counts as "fixed" for H9.** If yes, code/
   bumps the interpreter to 3.14.x. If no, CVE-2026-82049 becomes the 39th unfixable finding.

Until then, code/ will not write exemptions. The gate's escalation output already names the exact
row to add for each one (`scan/evaluate.py`, revision 4).

## Item 8 — Contract gap met while building SC-11: an uncapped text output has no fixed last line

**Status:** closed 2026-09-28. Answered by discovery revision 6, a clarification
(`../bridge/feedback/01-20260928-225646-uncapped-last-line.md` § Resolution, plan `3a46478`). Plan chose
option (b), made explicit. Rule 3's order is the shape of output a tool cuts, and uncapped text ends on
its own last result line. SC-11's "last line" means a predictable kind. **Applied** in feature 001
cycle 4 on `modify/001-slice-1`: the contract states the uncapped case and plan's table (`fc95cdf`), the
README is aligned, and the spec records revision 6 (`f9797b0`). No code changed: what was built already
matched.

As first raised: for the mentor, and plan if it is a contract question. Found building feature 001
slice 1 (send `…-214635`, T055).

SC-11 (Manual) asks that a person reading the output contract can predict a tool's **first line, last
line and exit codes**. Two of the three are fixed:
- the first line, `<tool>: <target> [<scope>]` (rule 12)
- the exit codes (rule 5)

The last line is fixed only in two cases:
- **when output is capped:** the omission line (rule 2)
- **for JSON:** the object always carries `exit`

**An uncapped text output simply ends on its last result line** (`agentio.py`, the text branch). Rule
3's order ends with "exit code, and a path to the full artefact", but `contracts/output-contract.md`
applies that order only when output is capped.

code/ has not changed it: the contract comes from the prompt, and "slice 1 does not redefine it". Two
options:
- **(a)** Every text output ends with `exit: <code>`. That is one line in `agentio`, and every tool
  inherits it; the conformance check would then verify it.
- **(b)** Accept that the uncapped last line is the tool's own. The README says so now.

SC-11 is reported `unconfirmed` either way until a person has looked. With (b), that person will find
the last line predictable only in the capped case.

---

## Item 9 — Prompt 03's exit pass-through vs the contract's exit vocabulary: an amendment for plan

**Status:** closed 2026-10-01. Feature 003 merged into `master` at `58b7d11` (`--no-ff`, from
`003-concluding-run` at `8cb0130`; signed off by the mentor at `864f778`). It was answered by discovery
revision 9: option (a), pass-through (`../bridge/feedback/03-20260930-235857-exit-pass-through.md`
§ Resolution). It was applied in feature 003's cycle (send `../bridge/sends/03-rev1-20261001-043339.md`,
spec FR-17 to FR-24), and SC-5's pass-through cells passed in the Docker lane at `fd9315e`.

As first raised 2026-09-30: raised before specifying feature 03, as send
`../bridge/sends/03-rev1-20260930-223345.md` § "One conflict to resolve before specifying" asks. Feature 03
was not started then: no branch, no spec.

**The conflict.** Prompt 03 slice 0: *"The tool's exit code equals the wrapped command's exit code"*.
Against it, `.specswarm/features/001-agent-shell-baseline/contracts/output-contract.md`:
- § Exit codes (rule 5), line 36: *"No other exit code is permitted from a timelike tool's own logic."*
- § Predicting the last line, line 83: *"The exit code is **always** one of those listed under Exit codes."*

**code/'s reading: the contract has to be amended. There is no reading of its current text that lets both
hold.** Line 36 alone would allow it: a wrapped command's exit is arguably not the tool's "own logic". But
line 83 is unconditional, and three places enforce the unconditional form:
- `contracts/agent-info.schema.json`: the manifest's `exit_codes` keys are an enum of
  `0 1 2 3 4 124`. A pass-through tool cannot declare what it returns.
- `contracts/conformance.md` C6: *"Every exit code observed in C1–C5 is in {0, 1, 2, 3, 4, 124}"*.
- `agentio`: `Tool.codes()` raises on any code outside the vocabulary.

Adopting pass-through under line 36's wording would narrow line 83. The send says that is plan's to
confirm (the contract is revisable only by bench evidence), so code/ has not adopted it.

**What `timelike-conform` would do: pass the tool, and prove nothing.** C3 and C4 run the tool with the
manifest's own `probe` arguments, which would be a command that exits 0, so C6 never sees a pass-through code.
It would report the tool conformant while the tool returns 137 in real use (cross-stack P005: a check can
only prove that whatever built it agrees with itself). Under option (a) the conformance check has to change
as well.

**Options.** code/ does not choose.
- **(a) Pass-through; the contract is scoped to the tool's own outcomes.** Line 83 is reworded. The
  manifest gains a way to say "passes the wrapped command's exit through" (for example `"passes_exit":
  true`), and C6 excludes the wrapped command's code on such tools. This is how `timeout`, `env`, `nice`
  and `xargs` behave, the habit agents were trained on (P3), so `run make && next` keeps its meaning.
  **What it costs:** the codes collide. A wrapped command that exits 2 or 124 by itself cannot be told
  apart, by exit code alone, from the tool's usage error or its timeout. The verdict line and the JSON
  (for example a `cause` field and a separate `command_exit`) would have to be what tells them apart. GNU
  `timeout` has the same collision and reserves 125 for its own failure. The contract has no 125.
- **(b) The vocabulary stays; prompt 03's criterion is amended.** The tool exits 0 when the command
  succeeds, 1 when it fails and 124 on timeout, and it names the command's real exit (137, 42, …) in the
  verdict line and in the JSON. `&&` chains still work, and the contract is unchanged. **What it costs:**
  the exact code is gone from `$?`, against the habit (P3), and "exit 137" becomes a line the agent has to
  read.
- **(c) (b) by default, (a) on a flag** (for example `--pass-exit`). The default output stays within the
  contract, and the exit is passed through only when asked for.

**Either way:** prompt 03's own timeout criterion (*"exits 124"*) agrees with the contract, and all the
other slice-0 criteria are unaffected. Once this is answered, feature 03 starts with `/specswarm:specify
--from-send` on the current send, or on a re-send if the prompt changes.

---

## Item 10 — Rule 11 and `run`'s duration: a reading for plan to confirm (not blocking)

**Status:** closed 2026-10-01. Plan confirmed option (a), with no discovery revision
(`../bridge/feedback/03-20261001-052418-run-duration-rule-11.md` § Resolution). A wrapped command's
duration is a result `run` reports, not a timestamp. **Applied** on `003-concluding-run`:
`output-contract.md` line 18 now reads plan's sentence. `run` is unchanged.

As first raised 2026-10-01: not blocking. Feature 003 went ahead on the reading below
(spec § Decisions; `research.md`). Had plan ruled otherwise, the duration would have moved behind
`--verbose`, a one-line change.

Prompt 03's Feature text gives the verdict as *"(exit, duration, lines, log path)"*. Two texts govern
timing:
- **Prompt 01's rule 11** (as sent in `01-rev7`, line 421): *"Deterministic, sorted output; no
  **timestamps** except behind `--verbose`."*
- **001's `output-contract.md` line 18**, written by code/: *"`--verbose`: May add timestamps **and
  timing**. Nothing else may add them (rule 11)."*

**code/'s reading:** a wrapped command's duration is the result `run` reports, as `time(1)` reports it. It is not
a timestamp, so rule 11 allows it. Line 18's "and timing" is wider than rule 11, the same pattern
plan found at line 83 (code/'s wording broader than the prompt's). code/ has **not** reworded line 18.
The duration appears in `run`'s verdict only, never in another tool's output.

**The cost, stated:** `run`'s output is not byte-for-byte deterministic across two runs. It never was:
the command's own output and the log path differ too.

**Options:** (a) confirm the reading, and line 18 is narrowed to "timestamps, and a tool's timing of
itself"; (b) the duration goes behind `--verbose` and the prompt's Feature text is amended.

---

## Item 11 — The scan gate blocks on three new OpenSSL CVEs outside the baseline (a person's call)

**Status:** closed 2026-10-01. The operator reviewed and accepted the three CVEs by interview with the mentor (`../bridge/history.md`, operator-approved, 2026-10-01T05:52:09Z): the affected paths are a TLS server's SSL_set_SSL_CTX, DTLS and QUIC, and timelike's images act as TLS clients only. **Applied** at `6053b30` on `003-concluding-run`, in all three baselines (agent +9, vanilla +6, bench-driver +6), reviewed 2026-10-01 and review by 2026-12-27. Each image's entries come from its own scan output (`scan/out/baseline.proposed.json`, `scan/out/timelike-vanilla/` and `scan/out/timelike-bench-driver/baseline.proposed.json`). An offline re-evaluation against the 05:43Z outputs gave PASS with 0 blocking for each image. The mentor's `make scan` re-run confirms it. (As first raised: open, blocking 003's merge under the Supply-chain scan gate.)

`make scan` at 05:43Z (`scan/out/verdict.json`) gave **FAIL** with 9 blocking grype matches:
CVE-2026-72897, CVE-2026-84782 and CVE-2026-84784, each in `libssl3t64`, `openssl` and
`openssl-provider-legacy` 3.5.7-1~deb13u3. All are High, with no stable fix, in the base layer, and
absent from the baseline reviewed 2026-09-28 (whether they were published since is not checked here). They are unrelated to 003's changes. The
proposed entries are in `scan/out/baseline.proposed.json`.

The gate's remedy is to add them to `scan/baseline/timelike-agent.json` and **have a person
re-review** the baseline (set `reviewed`, and `review_by` at most 90 days later). code/ has not done
this, because the rule asks for a person.

**Options:** (a) the operator reviews and accepts them (code/ applies the proposed entries plus the
new review dates on instruction); (b) wait for a Debian fix and hold 003's merge.

**Correction (2026-10-01, after the mentor's 05:50:47Z lane entry):** this item named only the agent
image. The same three CVEs also block **`timelike-vanilla`** and **`timelike-bench-driver`**, with 6
matches each in `libssl3t64` and `openssl-provider-legacy` 3.5.7-1~deb13u2 (`scan/out/timelike-vanilla/`
and `scan/out/timelike-bench-driver/verdict.json`, each with its own `baseline.proposed.json`). So all
three baselines (`scan/baseline/timelike-{agent,vanilla,bench-driver}.json`) need the person's
re-review. The CVEs sit in the base layer, so `master` is blocked as well, not only 003. Cycle 1's lane
addendum 1 says "9 blocking" for the agent image only; the next addendum carries this correction.

---

## Item 12 — The scan gate blocks on Debian's new fixes and one new unfixed gcc CVE (a person's call)

**Status:** closed 2026-10-02. It was resolved by the operator's option **(b′)**
(`../bridge/history.md`, operator-approved, 2026-10-01T21:09:43Z). The re-decision followed the
follow-up below: no newer trixie-slim exists, so the instructed refresh could not be done. The
maintenance branch `maint/base-targeted-upgrades` made the targeted `--only-upgrade` of the fixed
OpenSSL and PCRE2 (`dd75f1e`), and accepted CVE-2026-102010 while dropping the Item 11 OpenSSL entries
(`09e2c0b`). The mentor gave its OK (2026-10-01T22:05:12Z), and it merged into `master` at **`4b2b5b1`**
(`--no-ff`). `master` then merged into `modify/001-rev9-scope-and-t4` at `f2eaf82`, and the mentor's
`make scan` there **passed on all three images**, 0 blocking (agent 80, vanilla 79, bench-driver 51
baselined; `../bridge/.make-scan-001-rev9-b.log`, 2026-10-02T01:20Z). See 001's cycle report,
§ Cycle 6 — Docker lane addendum 2. The upgrade lines come out when a trixie-slim newer than
`a99cfc517144` ships the fixes (a watch item). (As first answered: 2026-10-01, `../bridge/history.md`,
operator-approved, 21:05:37Z; ironik.xyz by interview with the mentor. The first decision:)
- **Accept CVE-2026-102010** into all three baselines, review by 2026-12-27. The trigger is narrow (a
  specific libstdc++ API under attacker control), it is in the base layer, Debian has no fix, and
  timelike ships no C++ that uses it.
- **Refresh the base layer as separate maintenance, first:** on its own branch from `master`, bump the
  pinned `DEBIAN_IMAGE` to a current trixie-slim digest, drop the baseline entries whose findings gained
  fixes, and add the gcc entries. Lane-test it and merge it.
- Then 001 cycle 6's branch merges `master` in, and the lane re-runs.

**Closes when the refresh merges and the scan passes.**

As first raised: open, blocking 001 cycle 6's merge and `master` under the Supply-chain scan gate.
Every finding is in the base layer, not in this cycle's changes (spec, README, a bats file, the
Makefile).

`make scan` at `474a48b` (`scan/out/`, ~20:56Z) gave **FAIL** on all three images: agent 4 blocking,
vanilla 12, bench-driver 12. Debian moved since this morning's Item 11 review:

| Finding | Packages | State | Images that block |
|---|---|---|---|
| CVE-2026-72897, -84782, -84784 (accepted in Item 11) | `libssl3t64`, `openssl-provider-legacy` 3.5.7-1~deb13u2 | **now fixed** in 3.5.7-1~deb13u3; the baseline never hides a finding that gains a fix | vanilla, bench-driver |
| CVE-2026-54873 (new) | `libssl3t64`, `openssl-provider-legacy` 3.5.7-1~deb13u2 | fixed in deb13u3 | vanilla, bench-driver |
| CVE-2026-103111 (new) | `libpcre2-8-0` 10.46-1~deb13u2 | fixed in 10.46-1~deb13u3 | all three |
| CVE-2026-102010 (new) | `gcc-14-base`, `libgcc-s1`, `libstdc++6` 14.2.0-19 | **no fix**, not in any baseline | all three |

**Why the agent image differs:** it installs `git ca-certificates …`, so apt fetches the current
OpenSSL (its SBOM shows `libssl3t64`/`openssl` 3.5.7-1~deb13u3). Its 9 Item 11 OpenSSL entries no longer
match anything, which is why it accepts 77 rather than 86. Vanilla installs git only, and the driver runs
no apt at all, so both keep the base image's deb13u2. Nothing reinstalls pcre2 or the gcc runtime in any
image.

**Options for the fixable ones** (code/ can do any of these on instruction):
- **(a) Bump `DEBIAN_IMAGE` in `pins.env`** to a trixie-slim digest that carries the fixes. One pin
  moves all three images.
  - **Cost:** the baselines are keyed to the base digest, so all three need a person's re-review
    against the new digest.
  - **Cost:** the bench's earlier results were taken on the old base.
  - **Unknown:** whether such a digest exists yet. code/ cannot pull images here.
- **(b) Targeted upgrades in each Dockerfile:** `apt-get install --only-upgrade` of the fixed packages
  (vanilla and driver: `libssl3t64 openssl-provider-legacy libpcre2-8-0`; agent: `libpcre2-8-0`). The
  digest and the baselines stay.
  - **Cost:** vanilla stops being exactly "Debian + git" (security updates only), and the driver
    gains its first `apt-get` (002 RB10 wanted none).
- **(c) Hold** the merge (and `master`) until a base image ships the fixes.

**For CVE-2026-102010 (no fix):** the gate's remedy is a person accepting it into all three baselines
(entries in each `baseline.proposed.json`), or waiting for a fix. That is the same shape as Item 11.

**Not affected:** `make test` at `474a48b` **passed**: 198/198 e2e, including the four new `env -i`
cells, 676 units, and start-up p95 87.7 ms.

**Follow-up (2026-10-01, ~21:15Z): the base refresh cannot be done today, because there is no newer
base.** Checked against Docker Hub's registry API (anonymous token, index digests):
- `debian:trixie-slim`, `13.7-slim` and `13-slim` all resolve to **`sha256:a99cfc517144…`**, which is
  the digest already pinned in `pins.env`.
- The newest dated build, `trixie-20260918-slim`, is that same digest. The one before it,
  `trixie-20260824-slim`, is `sha256:d7e12182…`, which is older. The dated builds have come roughly every
  3–4 weeks (0713, 0803, 0824, 0918).

So OpenSSL deb13u3 and PCRE2 deb13u3 are not in any published base image yet. code/ has started
nothing: no maintenance branch, and no baseline edits. **The instruction needs a re-decision:**
- **(b′) Targeted upgrades on the maintenance branch:** `apt-get install --only-upgrade` of the fixed
  packages in the vanilla and driver Dockerfiles (`libssl3t64 openssl-provider-legacy libpcre2-8-0`)
  and the agent's (`libpcre2-8-0`). The digest stays, so the baselines keep their key.
  - Drop the Item 11 OpenSSL entries (they would match nothing), and add CVE-2026-102010.
  - **Costs:** vanilla stops being exactly "Debian + git", and the driver gains its first `apt-get`.
  - Once a base ships the fixes, the upgrade lines can come out again.
- **(c′) Wait for the next trixie-slim build** (likely mid-October), then do the refresh as instructed.
  Both 001 cycle 6 and `master` stay blocked until then.
- Either way, the CVE-2026-102010 acceptance can go in on its own. On its own it does not clear the gate,
  because the fixable findings still block.

## Item 13 — Feature 12's exit-4 envelope vs 001's confirm envelope: the boundary, for a ruling before code/ builds it

**Status:** closed 2026-10-02. Answered by **discovery revision 10** (plan `8d58050`), a clarification:
option **(b)**, with the confirm envelope's `grant` field removed; `mutating: false` confirmed and rule 8
kept. The answer is beside the question, in `../bridge/feedback/12-20261002-054636-grant-envelope.md`
§ Resolution, and was carried by send `../bridge/sends/12-rev2-20261002-055142.md`. **Applied** at
`b7a6ea6` on `004-adele-grants` (T018): 001's `grant-envelope.schema.json`, the confirm envelope without
`grant` (no caller set it: the one call, `tests/unit/test_agentio.py:244`, passed none),
`agentio.grant_required()`, conform C9, and `adele` printing the envelope on stdout. Governance was
audited to 10 at `cb943d3`. Recorded in 004's cycle report § Cycle 2. The image-level check is the
mentor's post-T018 lane. (As first raised: open, raised 2026-10-02 on `004-adele-grants` (the send's instruction: *"if it changes
001's contract or schema at all, raise it in FOR-MENTOR.md before building that part"*). **It is not
blocking the rest of slice 0.** code/ builds everything else (compose, Adele, the grant file, the
ledger, the stand-in, the no-leak scan) and holds only the client's exit-4 emission, its envelope
tests, and any edit to 001's files until this is answered.)

**The conflict.** Prompt 12 (slice 0): *"a request exceeding any limit exits 4 with an envelope naming
the grant, the limit and the operator's extend command, and nothing is performed"*. 001's contract
already owns exit 4:
- `contracts/output-contract.md:33`: exit 4 is `confirm`, and *"stdout carries the envelope
  (`confirm-envelope.schema.json`)"*. § Confirmation (rule 9), line 110: *"It names the plan and the
  exact command that confirms it."*
- `confirm-envelope.schema.json` requires `tool, target, scope, status, plan, confirm`:
  - `status` is the constant `confirmation_required`
  - `confirm` is *"the original command plus --yes"*, the agent's own command
  - there is no field for the exceeded limit
  - its optional `grant` (*"Set when a grant … is what's missing (P4; Adele, feature 12)"*) anticipated
    this case, but gives it no shape

**code/'s reading: no honest envelope fits the schema as written.**
- The required `confirm` would have to hold the **operator's** command (`docker exec timelike-adele
  adeled extend …`), which is not "the original command plus --yes" and which the agent cannot run.
  An agent trained on rule 9 would run the `confirm` value and fail.
- `status: confirmation_required` would say a confirmation is missing when a grant is.
- The schema allows extra properties, so a `limit` could be added without a schema error. But the
  required fields would still mean the wrong thing, which is a contract change in all but name.

**Options.** code/ recommends (b), but does not choose.
- **(a) A second status in the same schema.**
  - `confirm-envelope.schema.json` becomes a `oneOf`:
    - `confirmation_required`, unchanged
    - `grant_required`, with required `grant`, `limit` (`{name, allowed, needed}`), `extend` (the
      operator's exact command), `performed: false`, and no `confirm`
  - output-contract line 33 and § Confirmation name both.
  - **Cost:** the project's stdlib schema subset (`tests/unit/schema.py`) has no `oneOf`, so it grows
    a keyword. One file then has two shapes, told apart by `status`.
- **(b) A separate schema that exit 4 may also carry. Recommended.**
  - Add `contracts/grant-envelope.schema.json` beside the confirm envelope, with:
    - the header keys `tool, target, scope` first (rule 12)
    - `status: "grant_required"` (const)
    - `grant`
    - `limit {name, allowed, needed}`
    - `extend`, with `extend_by: "operator"`
    - `performed: false`
    - the refused `request`
  - output-contract line 33 becomes *"Confirmation or a grant is required. stdout carries the envelope:
    `confirm-envelope.schema.json` for a confirmation (rule 9), `grant-envelope.schema.json` for a
    grant (P4, T1); `status` says which."*
  - § Confirmation gains one paragraph saying that a grant envelope's command is the operator's, never
    the agent's.
  - `agentio` gains `grant_required(...)` beside `confirm_required(...)`.
  - The confirm envelope's optional `grant` field is either left as it is, or removed as superseded.
    That is the mentor's call; code/ would leave it, since removing it changes nothing anyone emits.
  - **Cost:** two edits to 001's contract text, one new file in 001's `contracts/`, and one new
    agentio function. These are recorded under `changed_other_features`. Existing tools and their
    envelope are untouched, and the schema subset needs nothing new.
- **(c) Keep 001 as it is, and give feature 12 its own exit code or stdout shape.**
  - Rejected by code/: the prompt says exit 4, and 001 already reserves 4 for exactly *"Confirmation
    or a grant"*. A new code is outside the vocabulary (rule 5; discovery revision 9's rule 5 applies
    only to wrapped commands, and a refused grant is the client's **own** outcome).

**What code/ needs back:** (a), (b) or another shape. If (b), also whether the confirm envelope's
`grant` field stays.

**A related reading, which code/ has adopted and which the mentor may overrule:** the client `adele`
declares `mutating: false`. In agentio, `mutating: true` means *"exit 4 with the confirm envelope
unless `--yes`"*. For a grant-brokered request that would be the agent confirming to itself (an agent
always adds `--yes`) in front of the operator's real confirmation, which is the grant. With `mutating:
false`, exit 4 from `adele` means one thing: beyond the grant.

## Item 14 — `adele --text` prints the refusal envelope as JSON: intended, and whether the person reading it should get more

**Status:** closed 2026-10-02. **The operator chose (b) at slice 1** (`../bridge/history.md`
operator-approved, 13:54:07Z): a text-mode stderr line beside the unchanged stdout envelope. 12 s0
merges on (a). The mentor carries it to the 12 slice 1 send (state `carry_forward` 12-slice-1), routed to
plan there. Nothing is built for it in 12 s0. (As first raised: open, raised 2026-10-02 on
`004-adele-grants`, answering the mentor's question from the D8 observation (`../bridge/history.md`
13:46:41Z). Not blocking 12 s0's merge: nothing here is a defect, and the lane fix for SC-4 (`4d1c9fe`) is
separate.)

**The question.** Under `--text`, a refused request prints the grant envelope as JSON, byte-identical to
`--json`, while a successful request prints a text verdict. Is that intended?

**The answer: yes, intended. It is 001's convention, not a choice T018 made.**
- agentio prints every exit-4 envelope as JSON on stdout **in every mode**
  (`tools/agentio/agentio.py`, `_emit_result`: *"the envelope is JSON on stdout in every mode (rule
  9)"*). It has done so for the confirmation envelope since 001 slice 0, and
  `tests/unit/test_agentio.py`'s rule-9 test asserts it (*"even in text mode the envelope is JSON on
  stdout"*).
- 004's CLI contract says the same of the grant envelope (`contracts/adele-cli.md`, refused (4): *"as JSON
  in every mode (rule 9's convention)"*), written in Cycle 1 and kept by Cycle 2.
- The reason: the envelope is the one thing on exit 4 that a caller must act on, so it has one shape.
  A text rendering would be a second format for the same fact, and it could drift from the schema.
- Under a harness stdout is a pipe, so the agent gets JSON by default anyway (rule 1). `--text`, or a
  terminal, is how a **person** reads it.

**What the D8 interview suggests, though.** It was a person in text mode who was unsure who runs
`extend` (`extend_by: operator`), what `status` tells apart, and where the record lives (Adele's ledger).
The envelope is written for the agent. Options, for the mentor and the operator, not decided here:
- **(a) Keep it as it is.** The envelope stays the whole of exit 4's output in every mode. The person's
  explanation goes in docs (`adele --help`, the README). Cost: none in code; the D8 gaps stay outside
  the tool.
- **(b) In text mode only, add one human line on stderr**, for example `refused: beyond grant e2e (ports
  allows 8080, 9000-9010; needs 5432). Nothing was performed. Only the operator can extend it: <extend>.
  Adele's ledger holds it as #46.` stdout stays exactly the envelope, so no parser and no schema
  changes. The ruling already allowed it (*"The interim stderr line may stay, as long as stdout carries
  exactly the envelope"*). Cost: agentio needs a way for a Result with an envelope to print a stderr
  line, and the confirmation envelope should probably get the same in text mode, for symmetry. That is
  a 001 change. Whether it is a clarification or bench-gated is plan's call: it adds output to a mode
  harnesses don't use by default.
- **(c) A text rendering of the envelope on stdout under `--text`.** code/ advises against it: `--text`
  is forced by some callers even when piped, and an envelope that changes shape by mode breaks rule
  9's promise that exit 4's stdout is the envelope.

**code/'s recommendation: (b), at slice 1, not in 12 s0.** It addresses what the operator actually
missed, keeps the contract's stdout intact, and slice 1 is where prompt 12 already asks for plain
explanations (network denials). 12 s0 can merge on (a).

## Item 15 — Publish redaction (maintenance send `maint-publish-redaction-20261002-183624`): report, by id only

**Status:** closed 2026-10-02. The mentor's lane on `f73ac79` passed and signed it off
(`../bridge/history.md`, `lane` and `sign-off`, 20:03:52Z): make test passed; make scan PASS on all four
images with the baselined counts unchanged (80/79/51/none); the deny-list step PASS, 7 entries and 246
tracked files with every id at 0/0. The image check found every id at 0 in metadata, history and the
exported filesystem of all six images. Merged into `master` by hand (`--no-ff`). The publishing step
itself is the operator's, later. The cycle report is `.specswarm/maintenance/publish-redaction/cycle-report.md`.
(As first raised: open, raised 2026-10-02 on `maint/publish-redaction`, for the mentor's lane and
sign-off.)

**Matches before and after, per id, over the tracked files** (counted with `git grep -E -i` and with the
new check, which agree; files/matches):

| id | `3c10d11` (before) | `8f2d72d` (after the redaction) | `26dc987` (with the check, 245 files) |
|---|---|---|---|
| P1 | 3/4 | 0/0 | 0/0 |
| P2 | 5/12 | 0/0 | 0/0 |
| P3 | 0/0 | 0/0 | 0/0 |
| P4 | 0/0 | 0/0 | 0/0 |
| P5 | 0/0 | 0/0 | 0/0 |
| P6 | 6/6 | 0/0 | 0/0 |
| P7 | 3/3 | 0/0 | 0/0 |

The "before" column equals the send's table exactly.

**Files edited (10, `8f2d72d`)**, each changed only at the matched strings, with the send's one-line note
added:
- the cycle reports of 001, 002, 003 and 004; `.specswarm/quality-analysis-20260930-052430.md`;
  `FOR-MENTOR.md`; `reboot.md`. In these, P2 is the repository's absolute path in pasted command output,
  now repo-relative (or `.` for the root), and one mention of the home directory, now described. P6
  became `ironik.xyz`.
- `scan/baseline/timelike-{agent,vanilla,bench-driver}.json`: `reviewed_by` (P6, P7 and P1 together) is
  `ironik.xyz`, and one review note's host (P1) is "the host". JSON cannot carry a header line, so the
  note is a new first key, `redaction`, which `evaluate.py` ignores. Every field the gate reads (ids,
  packages, origins, `reviewed`, `review_by`, `base_digest`) was checked equal before and after; the
  number of review notes is unchanged. The baselined counts therefore stay agent 80, vanilla 79,
  bench-driver 51, Adele none, for the lane to confirm.

**The check's shape (`26dc987`): `make scan`, once, after the per-image verdicts.** I chose `scan`
over `lint` because the merge gate is the lane, the lane runs `make scan`, and `scan` already holds
gitleaks:
- `scan/denylist.py` reads `git archive HEAD` (the tree as committed, whatever the working tree holds),
  checks its entry count against `git ls-tree -r HEAD` (a future `export-ignore` would be an error, not
  a silent pass), and greps regular files and symlink targets with GNU `grep -E -i`, the matcher the
  list was counted with. It runs on the agent image's interpreter, with no network.
- The list is `TIMELIKE_PUBLISH_DENYLIST`, default `../bridge/publish-denylist.txt`, mounted read-only
  only when it exists.
- **Output names ids and file:line only:** `FAIL P2 path:line`, a per-id `files/matches` line, and
  `scan/out/denylist.json`. No pattern or matched string is printed, written or stored; grep's stderr is
  discarded so a bad expression cannot be echoed either.
- **States:**
  - `pass`: the list was read, the self-test saw every entry, and nothing matched.
  - `fail` (exit 1, fails the scan): a tracked line matches.
  - `unknown — no deny-list available` (exit 0, does not fail): there is no list, so nothing was
    checked, and the line says so. It is never shown as PASS.
  - `error` (exit 2, fails the scan): an unusable list (no tab, a duplicate id, no entries), an
    invalid regex, an archive that leaves files out, or a failed self-test.
- **A self-test every run:** before any tree is judged, one line per entry is generated from that
  entry's own regex at run time, in a private temp directory, and must be found by the same matcher.
  A check that cannot see an entry cannot pass a tree.

**How it was seen failing:**
- the real list over the pre-redaction tree `3c10d11`: FAIL, with the per-id counts above. That is
  also a unit test, which runs wherever the list is available and skips elsewhere, saying why;
- a scratch clone with one generated plant per real entry, run through `scan.sh`'s own section (with a
  `docker` shim mapping its mounts): seven `FAIL Pn docs-plant.md:N` lines, one per id, and scan exit 1.
  The clone was deleted;
- 41 units with synthetic entries of each kind (a host name, a path with an alternation, a name with a
  class, an address), plants built at run time. They cover each kind failing, case, two matches on one
  line, symlink targets, unknown, every error, and a broken matcher caught by the self-test;
- `scan.sh` end to end through its unit fake: unknown passes, and a tracked match fails the scan by id;
- a bug of mine, caught on the way: with no list, the check returned before reading stdin, so `git
  archive` died of SIGPIPE and `pipefail` failed the scan (exit 141). It now drains stdin on every path,
  and a test pins it.

**Two limits:**
- **Hosts whose `grep` is not GNU grep.** In `make scan` the check runs inside the agent image, so it
  uses GNU grep. If someone runs `scan/denylist.py` directly on a host where `grep` is another
  implementation, an entry that implementation rejects is an **error**, which fails, and is never a pass.
  (This workspace's interactive `grep` is a ugrep wrapper, which rejects P2's syntax; the check itself
  calls the GNU binary on PATH.)
- **Not run under real Docker.** Its first image-level run is the mentor's `make scan`.

**Step 3, read-only:**
- **Images (static reading; not inspected, since there is no Docker here).** The only per-build input
  any image takes is `GIT_SHA`, which every Dockerfile validates as hex. The rest are pinned digests
  and `COPY` of tracked files (now clean), and Go builds with `-trimpath`. Two things I cannot settle
  from the source: compose's own `com.docker.compose.*` labels, and BuildKit's history or provenance
  records. Either could name a build context path. A read-only check for the lane, by id only:
  ```
  L=../bridge/publish-denylist.txt
  for img in timelike-agent:local timelike-adele:local timelike-adele-standin:local timelike-vanilla:local timelike-bench-driver:local timelike-test-runner:local; do
    c=$(docker create "$img"); docker export "$c" > /tmp/dl-fs.tar; docker rm -f "$c" >/dev/null
    docker image inspect "$img" > /tmp/dl-meta.json; docker history --no-trunc --format '{{.CreatedBy}}' "$img" > /tmp/dl-hist.txt
    while IFS=$'\t' read -r id re; do case $id in ''|\#*) continue;; esac
      printf '%s %s meta=%s history=%s fs=%s\n' "$img" "$id" "$(grep -ciE -e "$re" /tmp/dl-meta.json)" \
        "$(grep -ciE -e "$re" /tmp/dl-hist.txt)" "$(grep -caiE -e "$re" /tmp/dl-fs.tar)"
    done < "$L"
  done; rm -f /tmp/dl-fs.tar /tmp/dl-meta.json /tmp/dl-hist.txt
  ```
  `docker export` gives the flat, uncompressed filesystem, which `docker save`'s layer blobs may not be.
- **History (counted, not rewritten):** 284 commits on all refs, with one author and committer
  identity. P1 and P7 appear in that identity on **all 284**. P6 appears in **2** commit messages, and
  P1–P5 and P7 in none. Past trees hold the redacted strings too, 24 lines at `3c10d11` alone. All of
  it is the publishing step's to leave behind with the new root.

**Also, a correction to 004's ship section**, which the mentor's discharge noted: *"8 beside 8
unscored"* was 003's 2.22.0 ship, not 001's cycle 6, which was already `0/8`. 004's cycle report is
append-only, so the correction is recorded here and in this cycle's report.

## Item 16 — Publish cutover (maintenance send `maint-publish-cutover-20261003-003150`): the first public commit, by id only

**Status:** closed 2026-10-03. The mentor verified the remote independently and discharged the cutover
(`../bridge/history.md`, discharge, 2026-10-03T00:37:29Z), clearing the bookkeeping commit `81fe8f3` for
push on the operator's OK. The operator gave it, and `81fe8f3` is pushed (see **The bookkeeping push**
below). The cycle report is `.specswarm/maintenance/publish-cutover/cycle-report.md`. (As first raised:
open, for the mentor's independent check of the remote; the bookkeeping commits unpushed.)

**Before starting:** `master` was at `7e050fd` with a clean tree, there were no remotes, and the
deny-list over HEAD, with the list read, was **PASS** (7 entries, 246 files, every id 0/0). The public
repository had no refs (`git ls-remote public` printed nothing).

**The root:**
- `$ROOT` = **`466206080bba42f532d4d0ddd273fdb32cadd371`**
- its tree = **`f1de497a1dea93b4227a13ca329935f64acfe8e6`**
- `7e050fd`'s tree = **`f1de497a1dea93b4227a13ca329935f64acfe8e6`**: equal (the same `f1de497…` as the mentor's scratch build)
- `git rev-list --count $ROOT` = **1**, with no parents
- author and committer: `ironik.xyz <262467776+BotBauble@users.noreply.github.com>` (this repository's
  `user.name` and `user.email`, set locally)
- `archive/pre-publish` = `7e050fd` keeps the old lineage

**The deny-list over every pushed object** (`git rev-list --objects $ROOT`, each object through
`git cat-file -p`: 279 objects, 222 blobs, 56 trees and 1 commit, plus 278 path names; GNU `grep -E -i`,
**the list read**, 7 ids):

| id | objects | path names |
|---|---|---|
| P1 | 0 | 0 |
| P2 | 0 | 0 |
| P3 | 0 | 0 |
| P4 | 0 | 0 |
| P5 | 0 | 0 |
| P6 | 0 | 0 |
| P7 | 0 | 0 |

**The control:** the same script over the old lineage from `3c10d11` (2,409 objects) finds P1 in 293
objects, P2 in 35, P6 in 24 and P7 in 293. So a zero is a result, not a matcher that sees nothing. One
fault of my own on the way: the first version of the script stopped silently under `pipefail` when grep
found nothing. It printed no per-id line, not a pass. It was fixed and re-run, and now ends by listing
the ids it checked.

**The push** (one ref, no force; the token through a throwaway `GIT_ASKPASS` that read the `.env` file,
with `-c credential.helper=`; the script was deleted afterwards; the token appeared in no output, which
was checked before printing):
```
$ git -c credential.helper= push public $ROOT:refs/heads/main      (exit 0)
To https://github.com/ironikxyz/timelike.git
 * [new branch]      466206080bba42f532d4d0ddd273fdb32cadd371 -> main
```

**`git remote -v`:**
```
history	https://github.com/ironikxyz/timelike-history.git (fetch)
history	no-push (push)
public	https://github.com/ironikxyz/timelike.git (fetch)
public	https://github.com/ironikxyz/timelike.git (push)
```

**`master`'s new upstream:** `public/main`, with `push.default` = `upstream`.
`master` = `public/main` = `466206080bba` after `git fetch public`. `git checkout -B master $ROOT`
changed no file: the tree equals `archive/pre-publish`'s.

**The push rule** is now rule 5 in `CLAUDE.md`. The old local branches are unchanged, and the tag
`feature-001-complete` stays local, both archived in `timelike-history`.

**The bookkeeping push** (2026-10-03, on the operator's OK relayed with the mentor's check). Only
`81fe8f3`, the commit the mentor checked; the `reboot.md` commit after it stays local. Before it, per
rule 5: the deny-list over `81fe8f3` with the list read was **PASS** (7 entries, 247 files, P1–P7 all
0/0), and `git log public/main..81fe8f3 --format='%an %ae %cn %ce'` showed only the ironik.xyz noreply
identity. The token went through a throwaway `GIT_ASKPASS` with `-c credential.helper=`; the script was
deleted, and the output was checked for the token before printing:
```
$ git -c credential.helper= push public 81fe8f3:refs/heads/main      (exit 0)
To https://github.com/ironikxyz/timelike.git
   4662060..81fe8f3  81fe8f3 -> main
```
After `git fetch public`: `public/main` = `81fe8f379d8d`.

## Item 17 — Feature 07 slice 0 (`005-recover`): the seams decided in the spec, for the mentor to confirm (not blocking)

**Status:** closed 2026-10-04, on the corrected re-send `bridge/sends/07-rev11-20261004-030207.md`
("close FOR-MENTOR **Item 17**"). Decisions 4 and 5 are answered by **discovery revision 11** (plan
`0f6e1ed`); the answer of record is
`../bridge/feedback/07-20261003-022613-snapshot-store-and-persistence.md` § Resolution. See
*Resolution* at the end of this item. Raised 2026-10-03 on `005-recover` (send
`bridge/sends/07-rev1-20261003-013915.md`).
Each is decided in `spec.md` § Decisions, with its reason. None changes the output contract or reads a
criterion more narrowly, so I am building on them; each can be changed behind the two commands.

1. **Rule 9 and "one undo command" (D-1): the envelope reading.** `undo` alone exits 4 with the
   confirmation envelope (plan = the dry run). `undo --yes` is the one undo command, and the agent can run
   it directly. Rule 9 stays whole.
2. **The workspace (D-2):** the nearest ancestor holding `.git`, else the current directory, found
   without running git. Refused at `/`, the home directory, their ancestors, and when it would contain
   the store; the verdict says to change into the project directory. The image's `WORKDIR` is the home
   directory, so a bare `snapshot` there is refused.
3. **"Excluded" (D-3):** the per-file limit, the size cap's largest-first cut, non-regular files and
   unreadable files, each named with its reason. **No** built-in list of cache or build directories.
   Git-ignored files are captured like any other. `.git` is out of scope at every depth.
4. **The store does not use git (D-5) — a departure from `tech-stack.md`'s note** ("git 2.40+
   (snapshots, shadow store outside the workspace)"). A git store would lose permission bits other than
   the exec bit, record nested repositories as gitlinks (their files uncaptured), and fire
   `post-index-change` through 001's dispatcher. The store is a content-addressed copy store in stdlib
   Python (H5) and runs no git command. **For plan:** confirm, or ask for git and accept those three.
5. **Where snapshots live (D-7):** the session scratch directory, the only place rule 10 allows.
   They survive a container restart, not a recreate, and are **per session**: peer agents cannot undo
   each other's work, and a new `TIMELIKE_SESSION` starts empty. A cross-session store needs a state
   location the contract lacks (rule 10's "project cache" is undefined anywhere in the repository).
6. **An undo is undoable (D-10):** `undo --yes` snapshots the state it replaces first (reason
   `before undo <id>`), the first non-`on demand` reason slice 1 extends.

**Resolution (2026-10-04, Cycle 2 of `005-recover`).**
- **Decision 4 (D-5), confirmed:** option (a), the stdlib content-addressed store, with four
  conditions. Two held as built: cross-snapshot dedup, and symlinks as links. Two were built in Cycle 2:
  the size cap now counts bytes new to the store, after dedup (FR-6), and "taken" now follows a
  restorability check that reads the record back and re-hashes every object (FR-9). The evidence is in
  `005-recover/cycle-report.md` § Cycle 2. `tech-stack.md`'s git note was amended at the governance
  audit to revision 11 (`586e298`).
- **Decision 5 (D-7), answered:** slice 0 stays as built, outside the workspace. Rule 10 now names a
  per-workspace state root outside the workspace, and the project cache is withdrawn. That location,
  and survival across sessions and recreation, ride 07 slice 1.
- **Decisions 1, 2, 3 and 6:** no separate ruling was asked for or given. They stand as built (spec D-1
  to D-3, D-10), and the item closes on the send's instruction. A later ruling on any of them would be
  a new item.

## Item 18 — Feature 05 slice 0 (`006-bounded-read`): two readings of rule 3 to confirm before they are built; the other seams decided

**Status:** open for Q3 only. **Q1 and Q2 closed 2026-10-04: both answered (a)** by the mentor in
`../bridge/feedback/05-20261004-062732-view-search-rule3-and-byte-bound.md` (route code; no revision). **Q3** (is a window bounded in bytes in JSON, spec FR-7) was raised by
the mentor and routed to plan; it is pending there, and FR-7's JSON branch waits for it. Raised
2026-10-04 on `006-bounded-read` (send `bridge/sends/05-rev1-20261004-061518.md`).
Each seam is decided in `spec.md` § Decisions, with its reason. The send asks for anything near 001's
contract to be raised before that part is built, so **Q1 and Q2 wait for an answer.** The rest of 05 is
built first.

**Q1 · D-2: `view`'s window as a rule-3 cut, and what its `more:` is.** A window that shows less than the
whole file is treated as cut output. It ends with the omission line, whose figures count the file's lines
and bytes not shown, and whose full output is the file itself. A whole-file view has no omission line,
so its absence still means nothing was left out. The question is `more:`:
- **(a) recommended:** `more:` is **the next window's command** (`view FILE:121-240`). That is the prompt's
  "footer naming the next range command". It prints the next part of what was omitted, not all of it.
- **(b):** `more:` prints **everything omitted** (`view FILE:121-412 --limit 0`), as 003's and 005's
  `sed -n` over their artefacts do, and the next window goes on a line of its own before it. This is
  faithful to "the exact command that prints what was omitted", but two continue commands in one footer
  are one too many.

**Q2 · D-3: `search`'s narrowing line and rule 3's order.** The cap counts hits (50). Each hit is one
line, so the omission line's omitted lines equal the omitted hits. Its `more:` is `sed -n A,Bp` over the
saved hit list, never a re-run. The criterion also wants "a concrete way to narrow" in the footer, which
rule 3's order has no slot for.
- **(a) recommended:** a line `narrow: search … <dir>  (N of the 262)` as the last line before `more:`, so
  the footer reads narrow, more, exit, full output, omission line.
- **(b):** the narrowing goes in the verdict line only.

**Decided, not waiting** (no contract change, no narrower reading of a criterion):
1. **D-1:** JSON stays the default under a pipe. **The D5 demo's agent sees JSON by default.** Its `lines`
   are the same numbered lines text mode prints, with `start`, `end`, `total`, `target` and `next` as data.
2. **D-4:** `--strict` makes zero matches exit 1. It is declared in the manifest's `exit_codes`, and the
   verdict says `no match (strict)`.
3. **D-5:** ignore rules are read in the standard library (`.gitignore` per directory and
   `.git/info/exclude`). No git command runs, because 001's layer does not pin `core.fsmonitor`. The
   limits: no `core.excludesFile`, and no knowledge of which files are tracked.
4. **D-6:** the names are `view` (discovery's own P3 example; vim's alias, but the image has no vim) and
   `search`. **A correction to the send:** the `type -a` cells are e2e tests in each feature's bats files
   (005's R7), not part of `timelike-conform`.
5. **D-7, D-8:** fixed defaults of 120 lines and 50 hits (`-m N`); `FILE:N` shows 10 lines each side. The
   search is stdlib `re` with a 30-second limit and exit 124. No ripgrep is added.

**Answers (2026-10-04, `../bridge/feedback/05-20261004-062732-view-search-rule3-and-byte-bound.md`):**
- **Q1: closed, (a).** `more:` is the next window's command. A whole-file view has no omission line,
  and JSON's `truncated.more` equals the text's `more:`.
- **Q2: closed, (a).** The `narrow:` line goes after the hits, before the closing lines; the omission
  line stays last. `count`, `shown` and `truncated.omitted_lines` stay consistent (in hits).
- **Q3: open, with plan.** The mentor recommends (a), JSON follows text: a line longer than `COLUMNS` is
  cut in JSON too, and its full length is carried as data. Not built until plan answers.
