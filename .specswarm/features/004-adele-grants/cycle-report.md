> Redacted for publication, 2026-10-02 (`bridge/sends/maint-publish-redaction-20261002-183624.md`): internal host names, absolute paths and a personal name replaced. No other change.

# Cycle report — Feature 004 (Adele & grants, built from prompt 12)

> Append-only. One section per cycle, headed by the send it built. Addenda follow a cycle's section.
> The path is the one the send names (`code/.specswarm/features/[NNN]-[slug]/cycle-report.md`). This
> project's CLAUDE.md names the same path, so there is one file, not two.

## Cycle 1 — bridge/sends/12-rev2-20261002-042951.md

**Written:** 2026-10-02. Not in dispatch mode. Built branch-first on `004-adele-grants` from `master` at
`8846d77` (≥ `3d891ae`, as the send requires) with:
- `/specswarm:specify --from-send bridge/sends/12-rev2-20261002-042951.md`
- `/specswarm:plan`, `/specswarm:tasks`, `/specswarm:implement`

**Plugin:** this session loaded **specswarm 4.0.1-botbaubble.2.24.0**. Every expanded command named the
2.24.0 cache directory (lore Q002). **Not merged:** the Docker lane has not run, and FOR-MENTOR Item 13
holds one task (T018).

**Status in one line:** slice 0 is built except the exit-4 envelope, which is held for Item 13.
- **Adele:** Go, FROM scratch. She serves on an internal network the agent shares. She reads the
  operator's grant file at start, refusing a malformed one with its line. She brokers the stand-in with
  a canary the agent never sees, refuses over-grant requests before performing anything, and records
  an append-only ledger with undo.
- **The client** `adele`.
- **The lane:** an Adele stamp check, a `go test` step, and Adele in the scan gate with `govulncheck`.
- **Evidence so far:** the host lane passes. Nothing has been re-established in the image.

**Directory numbering:** the directory is `004`, the next in this repository's sequence. It is built
from prompt **12**, and `spec.md` records `source_prompt`.

### Group A — cited from `.implement-complete`

Group A: not applicable — no marker on this path

### Group B — copied from the send

| Field | Value |
|---|---|
| source_send | bridge/sends/12-rev2-20261002-042951.md |
| source_prompt | plan/.discover/prompts/12-adele-grants.md |
| prompt_revision | 2 |
| discovery_revision | 9 |
| slice | 0 |

### Group C — written by the code instance

**delegations:** seven general-purpose subagents. Each owned disjoint files, did not commit, and
reported its decisions. This instance reviewed each delegate's work, re-ran its checks, and committed
it one task per commit.

| Delegate | Wrote | Found, and fixed by this instance |
|---|---|---|
| T003 | `adele/internal/grants` (parser, 98.1%) | — |
| T004 | `adele/internal/ledger` (SQLite, 93.0%), `go.mod`/`go.sum` | — |
| T005 | `adele/internal/standin` (93.9%) | — |
| T012 | `tests/unit/test_adele_cli.py` (34 tests) | four client defects: `--timeout nan`/`inf` crashed; an unhealthy `status` said "unreachable"; `grants` dropped Adele's error text; the verdict's wording differed from the contract |
| T021 | `scan/scan.sh`, `scan/evaluate.py` and their units | — |
| T006 (tests) | broker tests against the **real** stand-in (99.0%) | a capabilities refusal against an empty capability list was a 500 |
| T007/T008 (tests) | `adeled` and `adele-standin` command tests | the stand-in started on an unwritable record directory, then failed every create |

This instance wrote the broker, both commands, the Dockerfile, compose, the client, the lane, the six
e2e files and the README. Two Explore subagents mapped the lane and scan integration points and the
governance rules, read-only.

**criteria_reestablished.** Each citation matches exactly one line of the send (`grep -cF` = 1). The
SC-4 citation needs its longer form, because the shorter one also matches the send's slice-0 summary
bullet. **Every criterion is `unconfirmed`:** none has run in the image (no Docker here, 001 R10). The
host evidence beside each is advisory.

- `12 · "The agent image and Adele start together from one compose file, and the agent reaches Adele only through its request interface"` —
  **unconfirmed** (Docker lane pending). e2e: `tests/e2e/adele-starts-with-agent-reached-only-through-request-interface.bats`.
- `12 · "Adele rejects a malformed grant at start with the line at fault"` —
  **unconfirmed** (Docker lane pending). e2e: `tests/e2e/adele-rejects-malformed-grant-with-line-at-fault.bats`.
  Host: `adeled check` on each of the six fixtures prints exactly the file:line the test asserts. The
  Go units cover 38 malformations.
- `12 · "a request exceeding any limit exits 4 with an envelope naming the grant, the limit and the operator's extend command, and nothing is performed"` —
  **unconfirmed**. Two reasons: the Docker lane is pending, and **the envelope is held for FOR-MENTOR
  Item 13**. e2e: `tests/e2e/request-within-grant-performed-beyond-exits-4-nothing-performed.bats`.
  - Its envelope cells are present and skipped.
  - The interim refusal (exit 4, nothing on stdout, a stderr line naming the grant, the limit,
    allowed, needed and the exact extend command) is what the other cells test.
  - Host integration: performed, refused on ports, ttl and instances, the printed command run,
    retry performed. The stand-in's record was unchanged after each refusal.
- `12 · "No credential held by Adele appears in the agent's environment, filesystem, process arguments or any tool output, checked by a scan after a full request cycle"` —
  **unconfirmed** (Docker lane pending). e2e: `tests/e2e/no-credential-held-by-adele-appears-in-agent.bats`,
  with a planted control.
- `12 · "Every performed request is recorded in the ledger with grant, requesting session, resource created, estimated cost and expiry"` —
  **unconfirmed** (Docker lane pending). e2e: `tests/e2e/every-performed-request-recorded-in-ledger.bats`.
  Host integration: 7 ledger rows, each carrying these fields.
- `12 · "the Agent's reaching request beyond its grant exits 4 naming the grant, and the Operator extends the grant so the retried request proceeds"` —
  **unconfirmed**. Manual (D8). The mentor interviews the operator on the real exchange after the
  Docker lane, as the send says. SC-3's e2e automates the same exchange, but it is not the demo.

**reconcile_mode:** `full`. The spec was generated from prompt revision 2, so `audited_against` is
`[2]` (seeded by specify). The prompt changed no criterion between generation and this cycle.

**not_verified**
- **Nothing ran in the image.** That includes:
  - every e2e file
  - the Dockerfile (both stages)
  - compose: the networks, the `adele-secret` one-shot, the volume ownership on first mount, the
    healthchecks, and `internal: true` name resolution
  - the scan of Adele's image (Syft and Grype over a scratch Go image, and govulncheck in GO_IMAGE)
  - the lane's state reset
- **Docker behaviour assumed and not observed here:**
  - `docker run` exits 126/127 for a missing entrypoint (scan's pip-audit probe)
  - Go templates range over maps in key order (SC-1's network lists)
  - a named volume is initialised from the image's directory ownership (lore Q003)
  - `docker exec` resolves `adeled` on the default PATH of a scratch image (the printed extend command)
- **The host substitutes for the image:**
  - the binaries were built with the Dockerfile's flags on the host
  - Adele and the stand-in were run on loopback, not internal networks
  - the canary was a file, not the volume
- **Item 13's envelope** (T018).

**changed_other_features**
- **001 (the agent's runtime environment):**
  - The agent container joins the `adele-request` network.
  - It gains `TIMELIKE_ADELE_URL`.
  - `tools/bin/adele` ships through the Dockerfile's existing `COPY tools/bin/`.
- **001 (repository files):**
  - Root `.dockerignore` excludes `adele/grants.conf`.
  - None of 001's tests, contracts or the placeholder `adele` identity changed (spec D-6). The
    placeholder stays as a negative fixture.
- **The lane and gate shared by 001–003:**
  - `tests/run.sh`'s `up` now clears Adele's volumes, starts the stack with the stand-in's profile on
    the e2e grant file, and waits for health. It adds a `gounit` step.
  - `make build`, `up` and `down` gain the profile.
  - `make lint` gains Go lint.
  - The scan gate requires Adele's image, maps a base digest per image, adds a `govulncheck` step,
    and records pip-audit as `none` on an image with no interpreter. The step-name column widened.
- **003:** none. **002:** none.
- If Item 13 is answered with (a) or (b), 001's contract and schema change. That is held, and not
  done here.

**process_failures_recorded**
1. **Claims made before checking, then corrected:**
   - T011's decisions entry first said `--help` had "no cut marker". The check printed 1: the
     exit-codes line was cut at 200 columns. The labels were shortened, and the entry was corrected
     in the same commit.
2. **Bugs this instance wrote, caught by its own review before commit:**
   - compose's canary command carried doubled backslashes, which `printf` and `tr` would have read as
     two characters. Caught by executing the command.
   - SC-4's refused port for the bash -c cell was `2c`.
   - SC-4's control would have died at `exec sleep 300 <canary>`.
   - A `sed` that removed a delegate's two-line `t.Skip` broke the file. Repaired by hand.
3. **A design revised during implementation** (spec D-8, FLAGGED at T010): the canary moved from a
   host file to a Docker volume. Under compose's file secret, uid 10001 could not have read a 0600
   host file, and nothing is installed on the host to fix that.
4. **A load flake:** the coverage-traced unit run had 2 `test_bench_cli` "setup failed: hung"
   failures. This is 002's watch item, and the run overlapped a delegate's Go tests. The file then
   passed 24/24 three times alone. No bench file changed.
5. **Plugin observations under 2.24.0, for the mentor to relay** (decided from the files, not worked
   around in code):
   - `lib/features-location.sh` printed **nothing on stderr** in specify, plan, tasks and implement.
     Every resolution was direct (`004`), as the send asked to be told.
   - The expanded `/specswarm:specify` text still substituted the command's first argument into
     shell functions: `norm()` reads `sed … "--from-send"`, and `fm()` greps `"^--from-send:"`. 2.24.0
     called this a markdown-expansion issue and fixed it. In this session's expansion it is present.
     The blocks were run from the installed file instead, with `ARGUMENTS` set as a variable.
   - The scope matcher's path pattern needs a character before the dot, so a dotfile named in
     `tasks.md` (`.gitignore`, `.dockerignore`) never matches. T001, T009 and T010 recorded `SCOPE:
     out` for files their tasks name.
   - On the reuse-branch path, specify builds the directory slug from the description, not the
     branch (`004-12-adele-and-grants` against branch `004-adele-grants`). The directory was named to
     match the branch.
   - Implement step 10's `unmeasured-explains-itself` (D74) counts the plugin's own literal reason
     `visual-alignment — unavailable: screenshot analysis is not implemented` as **unattributed**.
     The literal says neither "this install" nor "this machine".
   - `ship.md` assigns no `FEATURE_DIR` (relayed 2026-10-02). This becomes relevant at this feature's
     ship.

**retired_prompts_seen:** none.

### The send's open points, decided (spec D-1 to D-9)

| Decision | |
|---|---|
| Client name | `adele`: the `<service> <verb>` habit, and it shadows nothing (D-1) |
| Transport | HTTP on two internal compose networks. Nothing is mounted into the agent. Adele has no outside route. The agent keeps its default network until slice 2 (D-2) |
| Grant file | The operator's `adele/grants.conf` (git-ignored, copied from the committed example), bind-mounted read-only into Adele only. Line-based, so each error names its line (D-3) |
| Extend command | `docker exec timelike-adele adeled extend <grant> <limit> <value>`, printed with the value that makes *this* request allowed (D-4) |
| Exit-4 envelope | **Raised as FOR-MENTOR Item 13** with options (a) to (c). (b), a separate `grant-envelope.schema.json`, is recommended. Also raised there: `mutating: false` for the client (D-5) |
| 001's placeholder `adele` identity | Stays, unchanged, as a negative fixture. Adele runs as the same uid, 10001 (D-6) |
| Undo | Each performed row records `standin.box delete name=<box>` (D-7) |
| The canary | A one-shot service writes it into a volume, `root:10001` 0440, read-only to Adele and the stand-in. It never touches the host's disk (D-8, revised) |
| Sessions | Self-declared attribution, not authority (D-9) |

### Credential-class CVEs: facts for the operator's review (do not edit the baselines)

The send asks for four facts before 12 merges. These are as of this cycle. The operator decides.

1. **Does any credential, real or canary, reach the agent container by any path?**
   - By design, no. The canary is in a volume mounted only into Adele and the stand-in. The agent has
     no mounts and no route to the stand-in.
   - Its evidence is SC-4's e2e, which has **not run yet**. Host integration found the canary in no
     client output and no event log.
2. **Did the agent container's network change?** **Yes.** It joined `adele-request` (internal, shared
   only with Adele) in addition to its default network, which keeps egress until slice 2.
3. **Is the agent's libcurl in the path of any request to Adele?** **No.** `adele` uses Python's
   stdlib `urllib.request`, not curl or libcurl. git's libcurl is not involved in reaching Adele, and
   no credential passes through the agent.
4. **The scan's current entries for the three IDs** (from `scan/out/`, the 2026-10-02 scan at `f2eaf82`):
   - CVE-2026-11856, CVE-2026-19931 and CVE-2026-8926 are each **Critical**, in `libcurl3t64-gnutls
     8.14.1-2+deb13u5`, in the agent and vanilla images.
   - Debian's fix state is **wont-fix** for all three.
   - None gained a fix. Each baseline reason ends "Re-review when Adele (feature 12) brokers
     credentials".

### Implement step 10 — quality validation (specswarm 2.24.0), as the library reported it

```
🧪 Running Quality Validation
=============================
- Detector:
{
  "frameworks": ["pytest"],
  "primary": "pytest",
  "count": 1
}
- run_tests pytest: rc=2
/usr/bin/python3: No module named pytest
run_tests: pytest is declared by this project but not installed here
- parse_test_results: total=unknown passed=unknown failed=unknown skipped=unknown
- run_coverage pytest: unknown (rc 1)
- components:
unit-tests|25|-|unavailable:pytest is declared but could not be run on this machine (run_tests returned 2: /usr/bin/python3 has no pytest; the suite runs in the image and a scratch venv)
coverage|25|-|unavailable:coverage could not be run on this machine (run_coverage printed unknown, rc 1)
integration-tests|15|-|not-applicable:no integration suite is detected by the plugin (e2e bats run in the Docker lane)
browser-tests|15|-|not-applicable:no web project detected, so there is nothing to drive a browser over
bundle-size|20|-|unavailable:lib/bundle-size-monitor.sh is not present in this install
visual-alignment|15|-|unavailable:screenshot analysis is not implemented

Quality Score: unknown — no component could be measured, so there is no score to compare
```

Then the block's attribution:
- 1 component is missing from this install.
- 2 could not be run on this machine.
- 2 do not apply.
- 1 is unattributed: the plugin's own visual-alignment literal (above).

`block_merge_on_failure=false`. The gate is **UNKNOWN**: it warns and does not halt. No component was
filled in by hand. The project's figures are recorded beside the score in `.specswarm/metrics.json` →
`004.project_measurements_not_scored`.

**Host lane** (advisory; scratch Go 1.27.1 and venv):

| Area | Result |
|---|---|
| Go | 6 packages ok; **95.8%** statements in total (cmd/adele-standin 94.7, cmd/adeled 94.1, internal/broker 99.0, internal/grants 98.1, internal/ledger 93.0, internal/standin 93.9). gofmt, go vet and staticcheck 2026.2.1 clean. govulncheck v1.8.0: "No vulnerabilities found" |
| Python | 744 passed, 2 failed (the load flake above), 1 skipped; coverage **97%** (the `adele` client 97%). ruff 0.16.7 and mypy --strict clean (16 files) |
| shellcheck | 0.11.0, clean over 34 files |
| `timelike-conform` | passes on `adele`, with Adele reachable and unreachable |
| Host integration at `a135f91` | the full cycle passes (see SC-3 and SC-5 above) |

**Implement step 9b: decision log** (the plugin's `scope-tally` and `decision-tally` over 004's
`tasks.md` and `decisions.md`, after T023):

```
scope: planned=23 recorded=22 unplanned=0 unrecorded=1 in=19 out=3 none=0 unknown=0 flagged=22 flagged_out=3 other=0 other_out=0
decisions: sections=22 flagged_sections=22 non_flagged_sections=0 sections_without_absent=0 flagged=63 assumed=24 deferred=0 absent=39 inherited=21 low_confidence=0 flagged_low_confidence=0
```

- The unrecorded task is T018, held for Item 13.
- The 3 `out` records are the dotfile-matcher gap above: `.gitignore` (T001), `.dockerignore` (T009),
  and both (T010).
- No decision was low-confidence.

### What the mentor needs to do next

1. **Answer FOR-MENTOR Item 13:** the exit-4 envelope's shape, and the client's `mutating: false`.
   T018 then builds the envelope, and its e2e cells are un-skipped.
2. **Run the Docker lane on this branch:** `make test` and `make scan`. Note that `make test` now
   clears Adele's volumes and runs on the e2e grant file.
3. **Review the credential-class CVEs** with the operator (above).
4. **The D8 demo** with the operator, after the lane.

### Cycle 1 lane addendum — the mentor's Docker lane on `5e759c6` (2026-10-02T06:29:07Z)

**Written:** 2026-10-02, on Cycle 2's send, before T018 changed anything the lane tested. Source: the
mentor's `lane` entry in `../bridge/history.md` (06:29:07Z) and this checkout's `tests/out/`
(`summary.json`: `git_sha` `5e759c60bbd1…`, every step `pass` except `unit`). Cycle 1 is not edited.

**Lane result, as the mentor recorded it:**
- `make test`: e2e **239/239 ok**, with 2 skipped (SC-3's envelope cells, held for Item 13). Go units
  pass. Python units **740 passed, 7 failed**, all `setup failed: hung` in `test_bench_cli` and
  `test_bench_runner`: the load-dependent watch item (host load ~5). 004 changes no bench file
  (`3d891ae..5e759c6`). The mentor's note stands: re-establish it in the post-T018 lane before
  reading it as a regression.
- `make scan`: **PASS on all four images.** timelike-adele has 10 packages, 0 grype matches,
  govulncheck 0 reachable, and a baseline that accepts nothing.

**criteria_reestablished, at `5e759c6`** (each citation matches exactly one line of Cycle 1's send and
of Cycle 2's, `grep -cF` = 1; the e2e names are the files in `tests/out/e2e.tap`):
- `12 · "The agent image and Adele start together from one compose file, and the agent reaches Adele only through its request interface"` —
  **executed** `tests/e2e/adele-starts-with-agent-reached-only-through-request-interface.bats` (6 ok),
  with `tests/e2e/adele-isolation-grant-file-and-extend-unreachable-from-agent.bats` (5 ok).
- `12 · "Adele rejects a malformed grant at start with the line at fault"` —
  **executed** `tests/e2e/adele-rejects-malformed-grant-with-line-at-fault.bats` (7 ok).
- `12 · "a request exceeding any limit exits 4 with an envelope naming the grant, the limit and the operator's extend command, and nothing is performed"` —
  **executed except its envelope** `tests/e2e/request-within-grant-performed-beyond-exits-4-nothing-performed.bats`
  (12 ok, 2 skipped). The interim refusal, nothing performed per the stand-in's own record, and the
  printed extend command run as printed with the retry proceeding all ran. **The envelope stays
  `unconfirmed`** until the post-T018 lane (Cycle 2).
- `12 · "No credential held by Adele appears in the agent's environment, filesystem, process arguments or any tool output, checked by a scan after a full request cycle"` —
  **executed** `tests/e2e/no-credential-held-by-adele-appears-in-agent.bats` (7 ok, with the planted
  control finding the canary where it is).
- `12 · "Every performed request is recorded in the ledger with grant, requesting session, resource created, estimated cost and expiry"` —
  **executed** `tests/e2e/every-performed-request-recorded-in-ledger.bats` (2 ok).
- `12 · "the Agent's reaching request beyond its grant exits 4 naming the grant, and the Operator extends the grant so the retried request proceeds"` —
  **unconfirmed**. Manual (D8): the mentor's interview with the operator, after the post-T018 lane.

**The credential-class CVEs:** the operator re-reviewed them at 06:33:56Z and the acceptance holds
(`../bridge/history.md`). The baselines are unchanged, and this instance did not touch them.

## Cycle 2 — bridge/sends/12-rev2-20261002-055142.md

**Written:** 2026-10-02. Not in dispatch mode. The re-send at **discovery revision 10** (prompt 12
unchanged at revision 2). It continued feature 004 on `004-adele-grants` with **no re-specify**, per the
send: the spec keeps Cycle 1's `source_send`, and its provenance fields were not touched.

**Plugin:** specswarm **4.0.1-botbaubble.2.24.0**, the version this session loaded (lore Q002).
`/specswarm:constitution` ran for the governance audit; T018 was built by hand under implement's
conventions (a decisions.md section, the installed `scope-check` block, a tick and one commit), because
this cycle has one task. `/specswarm:specify`, `plan` and `tasks` were not re-run.

**Commits:**
- `cb943d3` on `master`: the governance audit to discovery revision 10.
- `3f3c520`: `master` merged into `004-adele-grants` (`--no-ff`).
- `b7a6ea6`: T018.
- This report and FOR-MENTOR Item 13's closure follow in one bookkeeping commit.

**Not merged.** The post-T018 Docker lane has not run. The send says it re-runs in any case, because
SC-3's envelope cells have never run.

### Group A — cited from `.implement-complete`

Group A: not applicable — no marker on this path

### Group B — copied from the send

| Field | Value |
|---|---|
| source_send | bridge/sends/12-rev2-20261002-055142.md |
| source_prompt | plan/.discover/prompts/12-adele-grants.md |
| prompt_revision | 2 |
| discovery_revision | 10 |
| slice | 0 |

### Group C — written by the code instance

**delegations:** `[]`. No subagent was used in this cycle.

**The governance audit (9 → 10), on `master` at `cb943d3`.** Source: `../bridge/governance-context.md`
(`/mentor:regovern` 05:50:50Z), § "What Changed In Those Revisions", and the feedback file's §
Resolution. 10 is appended to `governance_audited_against` in all three files, each with a prose audit
note in its header:
- `constitution.md` 1.4.1 → **1.4.2** (PATCH). **H2** gains revision 10's envelope sentence: exit 4
  carries a confirmation envelope or a grant envelope, told apart by `status`, and an operator's command
  never appears in a field the agent's habit runs. H2's example "4 = cap exceeded, with escalation"
  named only the grant case. The sentence about a brokered client not being `--yes`-confirmed, and
  rule 8, were **not** put in H2: they are contract-level detail, and P4's text (l.192) already covers
  the escalation. P1–P7, T1–T4 and H1, H3–H9 were checked and are unchanged.
- `quality-standards.md`, **amended:** the *Output contract (H2)* gate gains an exit-4 envelopes bullet,
  including the negative case that must be shown failing, and the *Refusals (P4)* gate names the grant
  envelope. No threshold moved. On this branch only, T018 also corrected the gate's check range to
  `C0–C9` (frontmatter unchanged; it merges with the feature).
- `tech-stack.md`: audited, **no change** (`stack.md` unchanged since `d606ed1`).

**The ruling, as built (T018, `b7a6ea6`):**
- **The confirm envelope's `grant` field is removed**, on the ruling's condition. I confirmed that no
  caller sets it: at `3f3c520`, `grep -rn 'confirm_required\|grant=' tools tests bench scan image` finds
  one call, `tests/unit/test_agentio.py:244`, which passes no `grant`. `adele`'s `"grant"` keys are its
  request body and its 200 data, not the confirm envelope. `confirm_required()` lost the parameter, and
  a unit shows that a caller passing it now fails.
- **`grant-envelope.schema.json`** (new, in 001's `contracts/`): `tool, target, scope` first, then
  `status: "grant_required"`, `grant`, `limit {name, allowed, needed}`, `extend`, `extend_by:
  "operator"`, `performed: false`, `request`, and an optional `ledger_id`.
- **`agentio.grant_required()`**, for a tool declared `Tool(grant_envelope=True)`. The manifest gains
  `envelopes` (every tool emits it; `[]` when none). agentio refuses to print an envelope on any exit
  but 4, or one its tool does not declare.
- **`adele`** prints the grant envelope on stdout on a 403, in `--text` and `--json` alike, with nothing
  on stderr. The interim stderr line is gone. A 403 that cannot fill the envelope is exit 1, never a
  guessed envelope.
- **`mutating: false`, rule 8:** the client stays `mutating: false`, with no `--yes`. **Slice 0 exposes
  no destructive request, so the client has no `--dry-run`.** That is said in its docstring and in
  `contracts/adele-cli.md`, as the send asks.
- **Conformance, C9 envelopes:** every exit 4 conform observes must be one envelope of a declared
  status, with that status's keys. A grant envelope carries **no `confirm`**, and no envelope's
  `confirm` may name a command outside the tool's own (its first word, and no `;`, `&&` or `|`
  chaining). **The negative case is seen failing:** 11 new violation cases, and a mutation run that
  disabled the `confirm` rule failed 4 tests before the file was restored byte for byte. conform cannot
  *provoke* a grant envelope, because its probes are read-only. So `adele`'s own envelope is judged by
  its units (against the schema and conform's own `check_envelope`) and by SC-3's e2e cells. That limit
  is written into `conformance.md`.
- **The spec** records the ruling in place, declared: FR-12, the Envelope entity, and a "D-5,
  settled" paragraph. No criterion moved, and nothing was ticked by it.
- **A 001 defect found while testing, and fixed:** agentio printed every envelope through
  `_clean_data`, which **sorts keys**. So the confirm envelope's first keys were `confirm, plan,
  scope`, never rule 12's `tool, target, scope`. I showed it on the pre-change tree. The envelope now
  keeps its own key order. No tool shipped so far is mutating, so no shipped output changes.

**criteria_reestablished** (each citation matches exactly one line of this send, `grep -cF` = 1):
- `12 · "a request exceeding any limit exits 4 with an envelope naming the grant, the limit and the operator's extend command, and nothing is performed"` —
  **unconfirmed** (the post-T018 Docker lane is pending). e2e:
  `tests/e2e/request-within-grant-performed-beyond-exits-4-nothing-performed.bats`. Its two envelope
  cells are un-skipped, and every refusal cell now validates the envelope against
  `grant-envelope.schema.json` and takes the extend command from its `extend`. Host: the units pass.
  The e2e helper was dry-run on the host with stubbed `run` and `pyq`: it passes a good envelope and
  fails a wrong limit, a `confirm`, and `performed: 0`.
- `12 · "The agent image and Adele start together from one compose file, and the agent reaches Adele only through its request interface"`,
  `12 · "No credential held by Adele appears in the agent's environment, filesystem, process arguments or any tool output, checked by a scan after a full request cycle"` —
  **unconfirmed in this cycle.** They were executed at `5e759c6` (the addendum above), but T018 changed
  the client (`adele`) and agentio, which both use. SC-4's cycle output now holds the envelope. They are
  for the post-T018 lane to re-establish.
- `12 · "Adele rejects a malformed grant at start with the line at fault"`,
  `12 · "Every performed request is recorded in the ledger with grant, requesting session, resource created, estimated cost and expiry"` —
  **unconfirmed in this cycle.** T018 changed nothing they test (no Go file, no grant fixture), but
  the same lane re-runs them.
- `12 · "the Agent's reaching request beyond its grant exits 4 naming the grant, and the Operator extends the grant so the retried request proceeds"` —
  **unconfirmed**. Manual (D8). The mentor's interview with the operator follows the lane.

**reconcile_mode:** `scoped`. Discovery revision 10 changed only the Agent output contract soft
constraint, so the spec was checked against it where it speaks of exit 4 (FR-11, FR-12, D-5, the
Envelope entity, and `contracts/adele-cli.md`), not re-read throughout. The prompt is unchanged at
revision 2, and `audited_against` stays `[2]`: it records prompt revisions, and 2 is already in it.

**not_verified**
- **Nothing from this cycle has run in the image.** That covers SC-3's envelope cells and the changed
  refusal cells, the `pyq`-hosted schema validation, and conform's C9 over the image's tools.
- **Host integration against the real Go binaries was not re-run.** The Go code is unchanged since
  `a135f91`'s passing cycle. The client reads the same 403 fields as before (grant, limit, extend),
  plus `performed` and `ledger_id`, which the contract says Adele sends.
- **C9 does not parse command substitution:** a `confirm` like `tool $(other)` passes the first-word
  and control-operator test. agentio quotes every argument with `shlex.join`, so it cannot produce one;
  a hand-written tool could.
- **001's spec** is UNAUDITED at revision 10 until its next modify cycle, as the send says. Not touched.
- **Implement step 10** was not re-run for this cycle. Cycle 1's score of record (`unknown`) stands; the
  host figures are below.

**Host lane, at the T018 tree** (advisory; the project's figures, never a score):
- Python: **775 passed, 1 skipped**, traced, with no load flake. Coverage **97%**: agentio 95%,
  timelike-conform 92%, adele 97%, run 96%, timelike 96%, bench 98%, scan 99%.
- ruff, ruff format, mypy (16 files) and shellcheck (every shell and bats file): clean.

**changed_other_features**
- **001 (the output contract), declared as the send directs:**
  - `contracts/grant-envelope.schema.json` (new)
  - `contracts/confirm-envelope.schema.json`: the `grant` property removed; the title names the sibling
  - `contracts/agent-info.schema.json`: the optional `envelopes`
  - `contracts/output-contract.md`: line 33 names both envelopes; § Confirmation gains the grant
    paragraph
  - `contracts/conformance.md`: C9, and a "Not checked here" row for provoking an envelope
  - `tools/agentio/agentio.py`: `grant_required()`, `Tool(grant_envelope=…)`, `envelopes`, the
    exit-4 guard, `confirm_required()` without `grant`, and the key-order fix
  - `tools/bin/timelike-conform`: C9 and the C2 `envelopes` check
  - `tests/unit/test_agentio.py`, `tests/unit/test_conform_violations.py`, and `tests/unit/schema.py`
    (`const` no longer accepts 0 for false)
  - `tests/e2e/conformance-check-over-every-timelike-tool-on-path.bats`: a comment's check range
- **Governance (all features):** `cb943d3` on `master`, as above, plus the `C0–C9` range on this branch.
- **Every agent-side tool's manifest** now carries `envelopes` (`[]` for `timelike`, `timelike-conform`
  and `run`). No other output of theirs changed.
- **002, 003:** none.

**process_failures_recorded**
1. **A fixture bug of mine, caught by the test:** the C9 violation fixture chose "mutating" with
   `"confirm" in MUT`, which also matched `env_grant_with_confirm`. That case then reported an extra
   C2. The fixture now tests the name's prefix.
2. **A 001 defect found by the new test**, not by review: the sorted envelope keys (above). It
   predates this feature, and no shipped tool was affected.
3. **A gap in the project's schema subset:** `const: false` accepted `0`, because Python's
   `False == 0`. It was found while dry-running the e2e helper, and fixed.
4. **Scope:** T018's `SCOPE:` line reads **out**, 5 files. All five are 001 files the send directs
   (agentio, its units, conform's units, the schema subset, one comment). `tasks.md` was not widened to
   make the check pass.

**retired_prompts_seen:** none. Cycle 1's send (`bridge/sends/12-rev2-20261002-042951.md`) is
superseded on its discovery axis, not retired. It was read only for the parts this send says carry over.

### What the mentor needs to do next

1. The post-T018 Docker lane on `004-adele-grants` (`make test`, `make scan`). Its HEAD is the
   bookkeeping commit after `b7a6ea6`. It re-runs the bench units' watch item too.
2. Then D8: the interview with the operator on the real exchange.
3. Then sign-off. I then ship (with `FEATURE_DIR` set for `quality-source`), paste the output verbatim,
   and merge `--no-ff` by hand.

### Cycle 2 lane addendum — the mentor's Docker lanes on `66adbae` and `77f40a2`, and D8

**Written:** 2026-10-02, after the mentor's sign-off (`../bridge/history.md` 14:26:10Z). Sources: the
`lane` entries at 07:47:50Z and 14:26:10Z, the D8 `observation` at 13:46:41Z, and this checkout's
`tests/out/` (`summary.json`: `git_sha` `77f40a26ccc0…`, exit 0, every step `pass`; `report.xml`: 239
ok, 0 skipped, 0 failed) and `scan/out/verdict.json`. Cycle 2 above is not edited.

**`66adbae` (07:47:50Z): failed on one cell.** `SC-4 004 the full request cycle ran` grepped for
`(code 4)`, the interim stderr line that T018 removed. It was a stale test assertion, not a product
defect: every other SC-4 cell passed, and so did every SC-3 cell, the envelope cells included. Fixed at
`4d1c9fe` (lane fix 1 in `decisions.md`). That scan's only failure was a `govulncheck` fetch reset from
proxy.golang.org, an infrastructure failure rather than a finding.

**`77f40a2` (14:26:10Z): passed.** e2e **239/239, none skipped.** Python units 776/776 (no bench load
flake this time; load 0.7–2.3). Go units pass. `make scan` **PASS on all four images**: timelike-adele
has govulncheck v1.8.0 with 0 vulnerabilities and 0 reachable.

**criteria_reestablished, at `77f40a2`** (each citation matches exactly one line of this cycle's send,
`grep -cF` = 1):
- `12 · "The agent image and Adele start together from one compose file, and the agent reaches Adele only through its request interface"` —
  **executed** `tests/e2e/adele-starts-with-agent-reached-only-through-request-interface.bats` (6 ok),
  with `tests/e2e/adele-isolation-grant-file-and-extend-unreachable-from-agent.bats` (5 ok).
- `12 · "Adele rejects a malformed grant at start with the line at fault"` —
  **executed** `tests/e2e/adele-rejects-malformed-grant-with-line-at-fault.bats` (7 ok).
- `12 · "a request exceeding any limit exits 4 with an envelope naming the grant, the limit and the operator's extend command, and nothing is performed"` —
  **executed** `tests/e2e/request-within-grant-performed-beyond-exits-4-nothing-performed.bats` (14 ok,
  none skipped). Every refusal's envelope was validated against `grant-envelope.schema.json` in the
  image. The two envelope cells ran in `--text` and `--json`.
- `12 · "No credential held by Adele appears in the agent's environment, filesystem, process arguments or any tool output, checked by a scan after a full request cycle"` —
  **executed** `tests/e2e/no-credential-held-by-adele-appears-in-agent.bats` (7 ok, with the planted
  control, and the fixed cycle cell).
- `12 · "Every performed request is recorded in the ledger with grant, requesting session, resource created, estimated cost and expiry"` —
  **executed** `tests/e2e/every-performed-request-recorded-in-ledger.bats` (2 ok).
- `12 · "the Agent's reaching request beyond its grant exits 4 naming the grant, and the Operator extends the grant so the retried request proceeds"` —
  **observed by the operator**, at 13:46Z on the live stack from the `66adbae` lane (transcript
  `../bridge/.d8-demo-20261002T073256Z.txt`, interview by the mentor):
  - the request as the agent, on grant e2e for port 5432, exited 4 with the grant envelope, and the
    stand-in had no box;
  - the operator ran the printed `extend` command themselves (ledger #47);
  - the agent's identical retry exited 0, was performed, and was recorded with its undo (ledger #48).
  The interview found that the envelope is written for the agent: a person was unsure who runs `extend`,
  what `status` tells apart, and where the record lives. FOR-MENTOR Item 14 answers the related `--text`
  question, and the operator chose (b), a text-mode stderr line, **at slice 1** (13:54:07Z).

**reconcile_mode, provenance:** unchanged. The prompt is still at revision 2, and `spec.md`'s
`audited_against` is `[2]`, so there is nothing to append. 004 has no `audit-log.md`, because no
revision has been reconciled against it since generation.

**The credential-class CVEs:** re-reviewed by the operator at 06:33:56Z, and the acceptance holds. The
baselines are unchanged.

### Ship — 2026-10-02, specswarm 4.0.1-botbaubble.2.26.1

**Version in force:** the session reloaded plugins (`/reload-plugins`, twice) before ship, and
`/specswarm:ship` and `/specswarm:analyze-quality` both expanded from
`~/.claude/plugins/cache/specswarm-marketplace/specswarm/4.0.1-botbaubble.2.26.1`. `installed_plugins.json`
records that version with `gitCommitSha` **`7885add8b284e6f684ae099c8c5687964d1bf4b4`** (lastUpdated
2026-10-02T17:55:23Z). `quality-report.json`'s `generated_by_version` agrees.

**How it was run:** each command's blocks were extracted from the installed file with awk (`# >>> name`
… `# <<< name`), with up to three spaces of markdown list indent stripped, and run as scripts with
`CLAUDE_PLUGIN_ROOT` set to that cache path. analyze-quality: `analysis-context`,
`component-applicability`, `tests-agnostic-score`, `unknown-resolvability`, §2's substitution (written by
hand from its prose), `module-score` with `MODULES` = 001's eight plus `adele`, `overall-score`,
`quality-report`. ship, in a **fresh shell**: Step 1's banner, `quality-source`, `quality-threshold`
inside Step 3's `if`, the threshold echo lines, and `quality-gate`. **`FEATURE_DIR` was not set by hand**
anywhere (D77's first field run without it).

**D77, in the field: fixed.** ship's `quality-source` found `FEATURE_DIR` unset, resolved it from the
branch through `lib/features-location.sh` and `fnum_from_branch`, and read the feature's
`quality-report.json`. It then printed the report's `unknown_why` and *"re-running … will NOT change this
result"* (D72), with no hand-set variable. The ship script's own trace lines are marked `[…]` below.

**analyze-quality's output, verbatim:**

```
📊 Codebase Quality Analysis
============================

Analyzing: .
Started: 2026-10-02T17:59:14+00:00

🔤 Language: Python
AQ_MEASURABLE=no
AQ_TESTS_LINE=tests|25|?|measured:pytest
AQ_TESTS_SCORE=unavailable:pytest is declared but could not be run on this machine
MODULE_COMPONENTS:
  tests|25|-|unavailable:pytest is declared but could not be run on this machine
  docs|15|-|unavailable:sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector
  architecture|20|-|unavailable:sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector
  security|20|-|unavailable:sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector
  bundle|7|-|unavailable:lib/bundle-size-monitor.sh is not in this install
  lazy-loading|7|-|unavailable:sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector
  images|6|-|unavailable:sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector
MODULE_SCORES:
  tools/agentio|unknown
  tools/bin|unknown
  scan|unknown
  image|unknown
  scripts|unknown
  bench/benchlib|unknown
  bench/bin|unknown
  bench/images+run.sh|unknown
  adele|unknown
MODULE_EXCLUDED_NOTES: tools/agentio: tests — unavailable: pytest is declared but could not be run on this machine (25 points not counted either way)
docs — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (15 points not counted either way)
architecture — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
security — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
bundle — unavailable: lib/bundle-size-monitor.sh is not in this install (7 points not counted either way)
lazy-loading — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (7 points not counted either way)
images — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (6 points not counted either way)
tools/bin: tests — unavailable: pytest is declared but could not be run on this machine (25 points not counted either way)
docs — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (15 points not counted either way)
architecture — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
security — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
bundle — unavailable: lib/bundle-size-monitor.sh is not in this install (7 points not counted either way)
lazy-loading — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (7 points not counted either way)
images — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (6 points not counted either way)
scan: tests — unavailable: pytest is declared but could not be run on this machine (25 points not counted either way)
docs — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (15 points not counted either way)
architecture — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
security — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
bundle — unavailable: lib/bundle-size-monitor.sh is not in this install (7 points not counted either way)
lazy-loading — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (7 points not counted either way)
images — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (6 points not counted either way)
image: tests — unavailable: pytest is declared but could not be run on this machine (25 points not counted either way)
docs — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (15 points not counted either way)
architecture — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
security — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
bundle — unavailable: lib/bundle-size-monitor.sh is not in this install (7 points not counted either way)
lazy-loading — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (7 points not counted either way)
images — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (6 points not counted either way)
scripts: tests — unavailable: pytest is declared but could not be run on this machine (25 points not counted either way)
docs — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (15 points not counted either way)
architecture — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
security — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
bundle — unavailable: lib/bundle-size-monitor.sh is not in this install (7 points not counted either way)
lazy-loading — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (7 points not counted either way)
images — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (6 points not counted either way)
bench/benchlib: tests — unavailable: pytest is declared but could not be run on this machine (25 points not counted either way)
docs — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (15 points not counted either way)
architecture — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
security — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
bundle — unavailable: lib/bundle-size-monitor.sh is not in this install (7 points not counted either way)
lazy-loading — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (7 points not counted either way)
images — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (6 points not counted either way)
bench/bin: tests — unavailable: pytest is declared but could not be run on this machine (25 points not counted either way)
docs — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (15 points not counted either way)
architecture — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
security — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
bundle — unavailable: lib/bundle-size-monitor.sh is not in this install (7 points not counted either way)
lazy-loading — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (7 points not counted either way)
images — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (6 points not counted either way)
bench/images+run.sh: tests — unavailable: pytest is declared but could not be run on this machine (25 points not counted either way)
docs — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (15 points not counted either way)
architecture — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
security — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
bundle — unavailable: lib/bundle-size-monitor.sh is not in this install (7 points not counted either way)
lazy-loading — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (7 points not counted either way)
images — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (6 points not counted either way)
adele: tests — unavailable: pytest is declared but could not be run on this machine (25 points not counted either way)
docs — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (15 points not counted either way)
architecture — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
security — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (20 points not counted either way)
bundle — unavailable: lib/bundle-size-monitor.sh is not in this install (7 points not counted either way)
lazy-loading — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (7 points not counted either way)
images — unavailable: sections 2-6 match only JavaScript/TypeScript sources; there is no Python detector (6 points not counted either way)

Overall Quality: unknown (no module could be scored (9 unscored))
📄 Wrote .specswarm/features/004-adele-grants/quality-report.json (overall_state: unknown, written by 4.0.1-botbaubble.2.26.1)
AQ_UNKNOWN_IS=unresolvable
AQ_UNKNOWN_WHY=no component of this Python project could be measured: pytest is declared but could not be run on this machine
```

**`quality-report.json`, as written** (`.specswarm/features/004-adele-grants/quality-report.json`). Its
`unknown_why` line has lost its two-space indent. That is this instance's extraction: the
indent-strip reached the literal JSON line inside the block. It is not the plugin. The file is valid
JSON.

```
{
  "overall_score": null,
  "overall_state": "unknown",
  "unknown_is": "unresolvable",
"unknown_why": "no component of this Python project could be measured: pytest is declared but could not be run on this machine",
  "set": "no module could be scored (9 unscored)",
  "modules_scored": 0,
  "modules_total": 9,
  "generated_at": "2026-10-02T17:59:14+00:00",
  "generated_by": "/specswarm:analyze-quality",
  "generated_by_version": "4.0.1-botbaubble.2.26.1"
}
```

**ship's output through Step 3, verbatim:**

```
🚢 SpecSwarm Ship - Quality-Gated Merge
══════════════════════════════════════════

This command enforces quality standards before merge:
  1. Runs comprehensive quality analysis
  2. Checks quality score meets threshold
  3. If passing: merges to parent branch
  4. If failing: reports issues and blocks merge

📍 Current branch: 004-adele-grants

[FEATURE_DIR before quality-source: '<unset>']
NOTE: .specswarm/features/004-adele-grants/quality-report.json reports overall_state='unknown' - the score is not a measurement
[FEATURE_DIR after quality-source: .specswarm/features/004-adele-grants; QR=.specswarm/features/004-adele-grants/quality-report.json; QUALITY_SCORE=<empty>]
📋 Using project quality threshold: 0% (from min_quality_score)
ℹ️  enforce_gates: false — a failing gate will WARN, not block

🎯 Quality Threshold: 0%
📊 Actual Quality Score: unknown — nothing was measured

❔ Quality gate UNKNOWN — no "Overall Quality: NN%" line was produced

   Nothing was measured. This is NOT a 0% failure and NOT a pass:
   the analysis did not run, did not report a score, or could not measure this project.


🔧 What would change this:
  - no component of this Python project could be measured: pytest is declared but could not be run on this machine
  - re-running /specswarm:analyze-quality will NOT change this result

⚠️  enforce_gates: false — this gate WARNS and does not block the merge.
   Shipping with quality state 'unknown' is the project's recorded choice, not an oversight.

[quality-gate returned; QUALITY_STATE=unknown]
```

**Lines to flag, not edited:**
- *"no "Overall Quality: NN%" line was produced"* is literally true, but analyze-quality did produce its
  canonical line, `Overall Quality: unknown (…)`. The line was printed; it carried no number.
- `modules_scored: 0` beside `modules_total: 9`: D71 holds (it was `8` beside "8 unscored" at 001's
  cycle 6 ship).

**Step 4 (`/specswarm:complete`)** needs stdin, so the merge was done by hand: `git merge --no-ff` of
the signed-off branch into `master`. The merge commit and its tree check are reported to the mentor
with this commit. The sign-off's condition was that commits after `77f40a2` be bookkeeping only. They
are `5a68659` (this report's lane addendum and FOR-MENTOR Item 14) and this commit (this ship section
and `quality-report.json`).

## Cycle 3 — bridge/sends/12-rev2-20261016-091249.md

**Superseded at prompt revision 16, mid-build.** This send began the cycle (12 slice 1, prompt revision 2, discovery
15) on `modify/004-slice-1` from `master` `ba3107b`. It went stale when plan answered FOR-MENTOR Item 26 Q1 with
discovery revision 16, and the mentor re-sent 12 slice 1 as `bridge/sends/12-rev16-20261016-102708.md`, which keeps
the branch and the work. **The full record is § Cycle 4**; its Group C fields hold this send's work too, as the
re-send asks.

**Commits made under this send** (all ironik.xyz): `5882196` FOR-MENTOR Item 26 raised; `297c085` its Q3 corrected;
`af410a3` the design (spec § Slice 1, impact analysis, modify, plan, tasks); `3942418` T024; `f120e4f` T025;
`76c4f1e` T026; `fac6e74` T027; `10ee056` T028; `99671f1` T029; `57975cc` T030; `22bba5f` T031; `c75f5d9` T032;
`f764245` T033; `a2a00a3` a T024 follow-up test; `9d45b72` status names where the record lives (Item 26 Q2, the
mentor's addition); `77d087a` bookkeeping.

### Group A — cited from `.implement-complete`

Group A: not applicable — no marker on this path

### Group B — copied from the send

| Field | Value |
|---|---|
| source_send | bridge/sends/12-rev2-20261016-091249.md |
| source_prompt | plan/.discover/prompts/12-adele-grants.md |
| prompt_revision | 2 |
| discovery_revision | 15 |
| slice | 1 |

### Group C — written by the code instance

Held by § Cycle 4, as the re-send asks.

## Cycle 4 — bridge/sends/12-rev16-20261016-102708.md

**Written:** 2026-10-16T10:56:40Z (read from the clock). Attended, not in dispatch mode. **12 slice 1 (natural), re-sent at prompt
revision 16** to the cycle § Cycle 3 began; it holds that send's work too. A modify cycle of `004-adele-grants` on
`modify/004-slice-1`, from `master` `ba3107b`. This path is the one the send names; this project's CLAUDE.md names
the same one.

**Plugin:** specswarm **4.0.1-botbaubble.2.44.0**, the version this session loaded (lore `specswarm` Q002).
Under the first send: `/specswarm:modify 004 --from-send bridge/sends/12-rev2-20261016-091249.md` (provenance row
4), then `/specswarm:plan`, `/specswarm:tasks` and `/specswarm:implement` (attended), each appending a Cycle 3
section (`spec.md` § Slice 1, `impact-analysis.md`, `modify.md`, `plan.md`, `tasks.md` T024–T036, `decisions.md`).
Under this send: `/specswarm:modify 004 --from-send bridge/sends/12-rev16-20261016-102708.md` (**row 7**, below), then
plan and tasks as deltas (Cycle 4 sections; tasks T037–T040), and `/specswarm:constitution` for the governance
audit.

**Commits** (`master..HEAD`, all under the ironik.xyz identity):
- `5882196` FOR-MENTOR Item 26, raised before the denial part was built; `297c085` its Q3 corrected (below).
- `af410a3` the design; then one commit per task: `3942418` T024, `f120e4f` T025, `76c4f1e` T026, `fac6e74` T027,
  `10ee056` T028, `99671f1` T029, `57975cc` T030, `22bba5f` T031, `c75f5d9` T032, `f764245` T033, `a2a00a3` a
  T024 follow-up test, `9d45b72` status names where the record lives, `77d087a` bookkeeping (all under § Cycle 3's
  send).
- Under this send: `1e7612b` § Slice 1 corrected in place, `audited_against [2, 16]`, SC-8's file renamed;
  `e170872` the governance audit 15 → 16 (one commit); `635aae8` the README block and Item 26 closed; this report
  and `reboot.md` in the last commit.

### Group A — cited from `.implement-complete`

Group A: not applicable — no marker on this path

### Group B — copied from the send

| Field | Value |
|---|---|
| source_send | bridge/sends/12-rev16-20261016-102708.md |
| source_prompt | plan/.discover/prompts/12-adele-grants.md |
| prompt_revision | 16 |
| discovery_revision | 16 |
| slice | 1 |

### Group C — written by the code instance

**delegations:** `[]`. No subagent was used in this cycle.

**reconcile_mode:** `scoped`. Revision 16 is new to 004 (modify row 7) and **amended** a criterion that § Slice 1,
written under § Cycle 3's send, described. So that section was corrected in place, declared at its head, and **not
regenerated**, as the send directs: the correction asks for less, and slice 0's body was true throughout. The skill's
table calls an amended body SUPERSEDED and says to regenerate; the send's instruction was followed instead, and this
is said here and in `impact-analysis.md` § Cycle 4. Removals were visible (the two sends diffed). Revisions 3 to 15 did
not change prompt 12, so nothing of theirs is claimed. `audited_against` is now `[2, 16]`; `audit-log.md` has the row.

**What was built** (spec § Slice 1, FR-24 to FR-42; decisions D-10 to D-16):
- **The reaper** (`adele/internal/reaper`, Go, stdlib): in `adeled serve`, a pass at start and every 5 s
  (`ADELE_REAP_INTERVAL`). A row is due when performed, expired and not yet `reaped` or `gone`. One pass reads the
  stand-in's record, checks the box is the same one (created + lifetime = the row's expiry), deletes it with up to
  3 attempts (1 s, 2 s apart), reads the record back, and records the outcome **from the read-back** (cross-stack
  P004): `reaped`, `gone` (already gone, or a later box of that name, which is not touched) or `reap-failed` with
  its cause from Adele's container (P001). Failed passes wait 5 s doubling to 5 min; after 5 the row is given up and
  its last row names the operator's command, `docker exec timelike-adele adeled reap`. A reap cut short by Adele's
  own shutdown records nothing (found by a test, fixed in T027).
- **The ledger, schema 2:** outcomes `reaped`, `gone`, `reap-failed`; columns `ref` (the performed row), `agent`,
  `cause`, `attempts`, `host`, `extend`. A schema-1 file is rebuilt on open in one transaction, keeping every row and
  id (tested against slice 0's schema as shipped). One ending per resource, enforced in the transaction (tested with
  two handles). `live` no longer counts reaped boxes; `spent` is unchanged.
- **Attribution (carried item 3):** the client sends `agent` (TIMELIKE_AGENT when valid, `agentio.agent_name()`);
  Adele records it on performed and refused rows; reap rows copy it from the row they end; the journal (009) labels
  ledger rows with it, so `--agent A` finds A's grant uses and reaps.
- **Status (seam 3; Item 26 Q2, confirmed by the mentor):** `adele status [HOST]` (the agent's; read-only
  `GET /v1/denials` through Adele) and `adeled status [HOST]` (the operator's): Adele's revision (P003), the reaper's
  due and given-up rows (operator's), and the denials of the last 24 h, at most 20 per host, newest first, each with
  its time, grant, limit, allowed and needed, the operator's command and the ledger row. None is said in so many
  words; an Adele that cannot say is "unknown", never "none".
- **Item 14 (b), plan: a clarification:** agentio prints rule 14's one line on stderr for exit 4 in text mode, for
  both envelopes; stdout is unchanged; `--json` adds nothing. Past COLUMNS the remediation points at the envelope.
  001's contract gains the sentence (§ Confirmation). `adele --help` and `adeled --help` also say who runs `extend`
  and where the ledger is.
- **agentio's guard (carried item 2):** `Tool(mutating=True, grant_envelope=True)` raises at declaration.
- **The stand-in's faults (P005):** `adele-standin fault NAME error|drop|clear` and `adele-standin delete NAME`, in
  its own container.

**Seam 1 — what denies an outbound connection in slice 1: FOR-MENTOR Item 26, closed.** No timelike policy denies the
agent's own outbound connections before slice 2's allowlist, so every reading that built the old criterion read it
more narrowly than its text; raised, with (a) recommended. **Plan ruled it a revision** (discovery 16): the criterion
is struck and split, the status half stays in slice 1 and the connection half moves to slice 2. The record (`host`,
`extend` on each refusal) and `status` built under § Cycle 3's send are what the new slice-1 criterion asks for, and
where slice 2's denials will land. Nothing toward slice 2 was built. The README now says the agent's own connections
are not filtered until slice 2.

**Item 26, as answered so far** (`bridge/feedback/12-20261016-100519-item-26-what-denies-in-slice-1.md`,
10:05:40Z). **Q2, the mentor: confirmed as specified, plus one addition, built:** the verdict names where the record
lives. The agent's verdict ends `record: adeled ledger`, and its JSON `record` says it whole ("Adele's ledger, which
the operator reads with: docker exec timelike-adele adeled ledger"); the operator's ends `the record: adeled
ledger`. A first wording pushed the agent's by-host verdict to 297 columns, where rule 13 cut the pointer off, so the
denials phrase was tightened too (`N denials of HOST in 24 h (≤20/host)`): both of status's figures and the record
fit 200 columns with the stand-in's host and a 40-character revision, pinned by a unit. **Q1, plan:** a revision
(above).

**Item 26's Q3, corrected in place.** As first written it said Item 14's feedback file had no answer. I had read
that file at about 09:16Z; plan's ruling was copied in at 09:18:16Z, a minute before the item was raised. The
correction (`297c085`) says so; (b) is built.

**criteria_reestablished** (each citation matches exactly one line of the send; modes as of this report):
- `12 · "Adele destroys resources whose time-to-live has expired, including after the requesting agent's container has stopped, and records each reap"` —
  **unconfirmed** (the Docker lane is the mentor's). e2e:
  `tests/e2e/adele-destroys-expired-resources-after-agent-container-stopped-records-each-reap.bats` (spread) and
  `tests/e2e/adele-reaps-after-restart-and-records-standin-unreachable.bats` (serial). Go units for every outcome,
  the bound, give-up, the same-box check, restart from the ledger and the migration (`internal/reaper` 95.7%). On the
  host, the real `adeled` and `adele-standin` binaries and the real client ran the flow (scratchpad, not tracked):
  a 1m box reaped about a second after its expiry with its session and agent; a faulted box `reap-failed` with the
  500's cause, then `reaped` once cleared; live back to 0.
- `12 · "A status command explains each of Adele's recent refusals by host, naming the grant and limit, what was allowed and what was needed, the operator's command, and where the record lives; a host with none says so"` —
  **unconfirmed** (the Docker lane is the mentor's). e2e:
  `tests/e2e/status-command-explains-each-of-adeles-recent-refusals-by-host-a-host-with-none-says-so.bats` (renamed
  under this send after the criterion). Units: Go (`internal/broker` denials endpoint, `cmd/adeled` status), Python
  (the client: none, several, newest first, unknown never "none", rule 13's columns). On the host, the real binaries
  printed the lines the cells match. **The struck criterion is not cited.**
- `12 · "DEMO: Adele destroys a resource whose TTL expired after the Agent's session ended, and the Operator sees the reap in the ledger"` —
  **unconfirmed** (D21; Manual; the mentor's demo and the operator's interview after the lane).
- Slice 0's five, all **unconfirmed in this cycle** (the lane re-establishes them; each changed beneath it):
  - `12 · "The agent image and Adele start together from one compose file, and the agent reaches Adele only through its request interface"` —
    compose is unchanged; the request interface gained the read-only `/v1/denials`.
  - `12 · "Adele rejects a malformed grant at start with the line at fault"` — the grant parser is unchanged; the
    lane's grant file gained three grants.
  - `12 · "a request exceeding any limit exits 4 with an envelope naming the grant, the limit and the operator's extend command, and nothing is performed"` —
    the envelope is unchanged on stdout; under `--text` its cells now also assert rule 14's stderr line.
  - `12 · "No credential held by Adele appears in the agent's environment, filesystem, process arguments or any tool output, checked by a scan after a full request cycle"` —
    the client gained `agent` and `status [HOST]`; the canary path is unchanged.
- Item 14 (b), not a criterion: `tests/e2e/exit-4-in-text-mode-writes-rule-14s-one-stderr-line-naming-whose-command-it-is.bats`
  (moved under this send from the status file) and agentio's units.
  - `12 · "Every performed request is recorded in the ledger with grant, requesting session, resource created, estimated cost and expiry"` —
    the ledger is at schema 2; the five fields are unchanged and a unit shows a v1 file's rows survive.

**not_verified:**
- **Nothing ran in Docker** (no Docker in this session). Every e2e cell above is unrun; the host integration used the
  same binaries built on the host's go1.27.1, not the image's.
- **No real provider was reaped** (cross-stack P005): the stand-in is timelike's own fixture, made to fail with its
  own faults. A real provider's delete, its errors and its idea of "gone" arrive with 13 and 14.
- The reaper's waits under a loaded lane: the fault cells fall back to the operator's `adeled reap` if the serving
  reaper gives up first; whether that fallback is ever needed is unmeasured.
- The serial file's restart is `docker stop`/`docker start` of compose's containers; `docker compose restart` and a
  host reboot were not tried.
- govulncheck on the host reports 9 standard-library findings in go1.27.1, each fixed in go1.27.2, which is
  `GO_IMAGE`; `make scan` runs govulncheck on the image's toolchain.
- **A confirmation envelope's stdout is not byte-identical between `--text` and `--json`, and never was**: its
  `confirm` replays the caller's own arguments (`undo --text --yes`). Plan's test reads "stdout is byte-identical
  between `--text` and `--json` for exit 4"; that holds for the grant envelope (tested) and for the confirmation
  envelope up to that one field. This cycle did not change it; reported for the mentor.

**changed_other_features:**
- **001** (`agentio`, `contracts/output-contract.md`): rule 14's line on exit 4 in text mode; `agent_name()`; the
  declaration guard. Three of its dependents' units pinned "stderr is empty" under `--text` and were updated to the
  ruling's assertions: `test_adele_cli`, `test_undo` (005) and `test_package_guard_shim` (013, a terminal: the line
  comes first there, because the shim prints the guard's captured stdout after it exits).
- **009** (`journal`): reads `agent` from ledger rows.
- **002** (the bench): **no change.** Its network-denial category matches agentio's verdict text and the guard's,
  neither of which moved.
- **The README**: the send's status block (row 12 `slices 0–1 of 0–2`; **21 of 38 planned slices are built.**;
  Adele's reaper, who runs what, `status`, the agent's connections unfiltered until slice 2; `adeled ledger` also
  lists reaps), marked with `<mark>`, the last update's marks cleared; the generated reference regenerated because
  `adele --help` changed (drift test passes). The Next line is left as it is.
- **Governance** (`e170872`): discovery revision 16 audited in the constitution, tech-stack and quality standards,
  no change needed in any; 16 appended with a header note naming the context file's section.

**process_failures_recorded:**
- Item 26's Q3 was written from a stale read of the feedback file (above); corrected in place, same cycle.
- A decision-log time was composed (10:13:00Z) rather than read; replaced with the clock's 10:12:59Z in `77d087a`.
- The host lane's `timed` step failed once, on `9d45b72`: `test_agentio_startup.py::test_tool_startup_p95_under_budget`,
  p95 413.8 ms against 100 ms, with the host's load average at 5.5–5.8 (the `-n 8` step beside it took 254 s, against
  136 s an hour earlier). Rerun alone three times at once, it passed each time. Nothing in this cycle touches a tool's
  start-up path (agentio gained one function and two checks, imported nothing). Reported, not hidden; the final lane
  below reruns it.
- T029's scope record was first computed with its arguments in the wrong order (`SCOPE: none`) and replaced before
  the next task with the right line (`out`, four 001/005/013 files, declared above).
- `implement` step 6f's scope record was missed for T024 and appended after its commit, before T025.

**retired_prompts_seen:** none.

**Lane classes for the new e2e files** (the send's rule, per file):
- `adele-destroys-expired-resources-after-agent-container-stopped-records-each-reap.bats` — **spread**: no time
  budget is asserted (reaps are waited for with PLUMBING_TIMEOUT), its grant and box names are its own, and it stops
  no shared container (the requesting agent is a throwaway).
- `adele-reaps-after-restart-and-records-standin-unreachable.bats` — **serial**: it stops Adele and the stand-in.
- `status-command-explains-each-of-adeles-recent-refusals-by-host-a-host-with-none-says-so.bats` — **spread**: no
  budget; it finds its own refusals by ledger id, whatever neighbours refuse.
- `exit-4-in-text-mode-writes-rule-14s-one-stderr-line-naming-whose-command-it-is.bats` — **spread**: no budget, one
  refusal of its own.

**Host lane** (advisory: files, units and hook logic, not the image), on `635aae8`, the code this report describes:

| Run | Time (UTC) | Result |
|---|---|---|
| `make test-host` (serial) | 10:39:00Z–10:48:24Z | rc 0: pytest 2545 passed, 13 skipped (530 s); host suites 60/60, 57/57, 33/33 |
| `pytest -n 8 -m "not timed"` | 10:48:24Z–10:55:17Z | rc 0: 2529 passed, 13 skipped (412 s; load average 9.1 at the start) |
| `pytest -m timed` | –10:56:01Z | rc 0: 16 passed |
| `go test -race ./...` (Adele) | after | all seven packages ok |

Also: ruff check and format, mypy (39 files), shellcheck over the Makefile's 96 files and every e2e file with
helpers, gofmt, go vet, staticcheck: clean. Adele's Go coverage 94.0% (90% bar). Earlier runs this cycle: on
`a2a00a3`, serial 2544 passed, `-n 8` 2528, timed 16 (10:00:18Z–10:12:51Z); on `9d45b72`, serial 2545 passed, `-n 8`
2529, **timed 1 failed** (the start-up budget under load, above).

### Cycle 4 lane addendum 1 — the mentor's Docker lane on `df52dbf` (feedback `bridge/feedback/12-20261016-174206-slice-1-lane-fails.md`)

**Written:** 2026-10-16, from the mentor's log `bridge/.make-test-12s1a.log`, `bridge/.within-12s1a.tsv` and this
checkout's `tests/out/` from that lane. § Cycle 4 above is not edited. The lane: e2e 689 of 703 ok, 14 not ok; unit 1
failed; gounit `adele-standin` failed; scan and lint passed. Each cause, and its fix (tasks T041–T047; `decisions.md`
§ Cycle 4, addendum 1):

- **A (11 cells: 265, 313–320, 323–324). Cause: the cells, not a tool.** Each cell captured stderr into a temp
  file and removed both temp files with `rm -f` inside the captured command. In the agent shell `rm` is a function
  (`image/rootfs/etc/timelike/shell-env.bash`) that calls the guard, so 005's trash notice joined the capture, after
  `cat "$e"` in every failing cell. Before this cycle the cells checked `stderr_bytes=0` as a substring, so the
  trailing line passed unseen; counting rule 14's one line exposed it. The host has no such function, which is why
  the host lane passed. **Fix:** `command rm -f`, as the snapshot cell already does, in the three files that capture
  this way. The rule-14 line itself was right in all 11.
- **B (cell 446). Cause: the denial line's length, not the login shell.** The lane's denial line was 207 columns,
  and rule 13 cut it at 200. **The lane's width is 200 in both shells**: docker exec without a tty sets no `COLUMNS`,
  nothing in the image or the helpers sets it, and agentio defaults to 200. The `bash -c` cell lists no denial, so only
  `-lc` showed it. **Fix:** the line says `· operator: <command>` in place of `— only the operator allows it: <command>`,
  188 columns for that denial; a unit pins it (with a five-digit ledger id) within 200. A session or agent name past
  about 20 characters is still cut, with rule 13's marker, and is whole in JSON.
- **C (cell 594). Cause: a stale literal.** The cell asserted `10 grants`; the lane's grant file gained three in this
  cycle. **Fix:** the cell counts the `[grant ` lines of the file it starts Adele with.
- **D (cell 66). Cause: the cell is load-sensitive. The tools did not get slower.** `adele`'s conform probe is
  `status`, which now makes two calls (health, then denials): five calls each against a live `adeled` on the host
  took 142 ms on HEAD and 139 ms on master. The cell took 9.1–9.6 s in every lane-speed lane, and in this lane 62.3,
  24.8, 17.9 and 15.1 s in its four shells. The file was `first`, so it started beside the Go step, which took 260 s
  here against 33 s in the lane-speed lanes. The other early files were slow too (`a-restore-…` 10.8x), while the
  median cell matched the lane-speed lanes (ratio 0.99). What loaded those first minutes is **not established**:
  `within.tsv` and `report.xml` carry no per-file start time. **Fix:** the file is `serial` in `lane.conf`, with
  that reason. Its budget is unchanged. The cost is its cells' time in the serial phase, about 123 s quiet. Also, the
  new `wait_reap` ran pyq (a `docker run`) on every 2 s poll; it now polls the text ledger and parses only once a
  reap row is there. That is load removed; it is not shown to be the cause.
- **E (gounit, `TestDeleteAndFaultCommands`). Cause: plumbing, not a claim.** The test's first create, to its own
  in-process stand-in (which fsyncs its record), got no answer inside a 5 s client. This is lane-speed item 9's class,
  for which the broker's fixture already has a 120 s bound. Every package except `grants` took about 181 s in that
  container, against at most 1.7 s before. On the host the module takes 8 s without `-race`, and the new tests have
  about 6 s of real waits. The container's 181 s is not reproduced here (no Docker). **Fix:** the test's own client
  is 120 s plumbing. The stand-in's `delete` command waits 30 s, not 5 s: the stand-in is test infrastructure and
  nothing is claimed of its speed. **Found while reading, and fixed:** the reaper held the broker's request lock for
  the whole reap, across the provider's calls and the 1 s and 2 s waits between attempts. Every agent request beside
  a faulted reap (the spread file's `error` and `drop` cells) waited out its retries. It now holds the lock for the
  ledger write alone. The same-box check covers a name reused meanwhile, as it already did for the operator's
  lockless `adeled reap`. A unit (`TestARequestNeverWaitsOnAReapsRetries`) fails on the old code and passes on the
  new.
- **F (`tests/unit/test_bench_cli.py:151`). Not this cycle's; not changed.** The bench and its units are untouched on
  this branch, and the same test failed in lanes `02s1-a` and `007s1-b`. Its fake run uses `--call-limit 2`. In this
  lane a hooked `git commit` in the rejects task went past 2 s under the unit step's load, counted as a hang, and the
  fake agent's policy sent it to `--no-verify`, which failed. So the report did not say "Tie". The fix belongs to
  002's unit (its call limit is plumbing there, but raising it costs every hang task its limit's time), for the
  mentor to route.

**The mentor's indent note:** the ledger criterion
`12 · "Every performed request is recorded in the ledger with grant, requesting session, resource created, estimated cost and expiry"`
belongs in § Cycle 4's slice-0 list, beside the other four, with the same mode, **unconfirmed** (the ledger is at
schema 2; the five fields are unchanged). It is not part of the Item 14 (b) bullet.

**Modes after this addendum:** every criterion cited in § Cycle 4 stays **unconfirmed** until the mentor's next lane.
Nothing ran in Docker.

**Host lane** (advisory: files, units and hook logic, not the image), on `df52dbf` plus this addendum's working tree
(the commit below carries exactly that tree):

| Run | Time (UTC) | Result |
|---|---|---|
| `make test-host` (serial) | 19:14:35Z–19:26:06Z | rc 0: pytest 2546 passed, 13 skipped (657 s); host suites 60/60, 57/57, 33/33 |
| `pytest -n 8 -m "not timed"` | 19:26:06Z–19:28:22Z | rc 0: 2530 passed, 13 skipped (135 s) |
| `pytest -m timed` | –19:29:06Z | rc 0: 16 passed |
| `go test -race ./...` (Adele) | after | all seven packages ok |

Also: ruff check and format, mypy (39 files), shellcheck over the Makefile's files and the changed e2e files with
helpers, gofmt, go vet: clean. Adele's Go coverage is 94.5% (90% bar).
