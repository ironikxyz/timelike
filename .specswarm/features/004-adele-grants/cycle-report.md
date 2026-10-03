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
