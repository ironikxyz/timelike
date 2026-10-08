<!-- Tech Stack Validation: PASSED — plan § Tech Stack Compliance Report: stdlib and POSIX sh, none added -->

# Tasks: 007 Announcements and discovery (prompt 04, slice 0)

**Input:** spec.md, plan.md, research.md, contracts/timelike-announce-tools.md. **Tests are required**
(H7). Conventions are as in 003–006:
- one commit per task, `[007] Tnnn: …`;
- a `decisions.md` section per task, with a SCOPE line from the installed `scope-check` block;
- delegates own disjoint files, don't commit, and stay out of `tools/`, `.specswarm/`, `../bridge` and
  `../plan`.

**Story map:** US1 the announcement and its check (SC-2) · US2 placement on start (SC-1, SC-4 D4) · US3 the
manifest (SC-3).

## Phase 1: Setup

- [X] T001 `image/rootfs/etc/timelike/standard-tools.json`: the curated entries (spec FR-11, research R4).

## Phase 2: Tests first (from the contract; delegated)

- [X] T002 [P] [US1] [US2] [US3] `tests/unit/test_announce.py`:
  - generation from fake tools' manifests (a temporary bin directory), the 60-line bound, a failing
    `--agent-info`;
  - `--check` (missing, extra, equal);
  - `--install` and `--status` over a temporary HOME (absent, current, replaced, someone else's, a
    directory in the way, unwritable, Codex's override);
  - `tools` (timelike and curated fields, `installed`, a malformed file);
  - the vanilla Dockerfile untouched.
- [X] T003 [P] [US1] [US2] [US3] e2e, each under `bash -c` and `bash -lc`:
  - `tests/e2e/announcement-at-most-60-lines-in-each-harness-user-level-context-on-start.bats` (SC-1,
    throwaways);
  - `tests/e2e/announcement-generated-from-manifests-missing-tool-fails.bats` (SC-2);
  - `tests/e2e/timelike-tools-manifest-json-interactivity-risk-safer-alternative.bats` (SC-3, and the
    vanilla image's home).

## Phase 3: Implementation

- [X] T004 [US1] [US3] `tools/bin/timelike`: `announce` (`--write`, `--check`) and `tools`.
- [X] T005 [US2] `tools/bin/timelike`: `announce --install` and `--status`; `image/rootfs/opt/timelike/libexec/entrypoint`.
- [X] T006 `image/Dockerfile`: COPY the curated file and the entrypoint; generate and check after the
  stamp; `ENTRYPOINT`. Update `tests/unit/test_timelike*.py` and the 001 e2e cells if one asserts the
  old usage.
- [X] T007 `README.md`: an announcements section; `Makefile` `SHELLCHECK_FILES` gains the entrypoint
  and the e2e files.

## Phase 4: Polish

- [X] T008 Host lane: lint, units with coverage, `make test-host`, start-up. Results in `decisions.md`.
- [X] T009 `cycle-report.md` § Cycle 1, implement step 10, `.specswarm/metrics.json`, the marker.

## Phase 5: Cycle 2 — revision 13 recorded; the workspace clause struck (send `bridge/sends/04-rev13-20261008-095251.md`, via `/specswarm:modify`)

<!-- Tech Stack Validation (cycle 2): PASSED — plan.md § Tech Stack Compliance Report (Cycle 2) has no
conflict or prohibition; the task scan (lib/tech-stack-parser.sh, ts_mentions) found no prohibited
technology in the task text below. The tasks change Markdown only -->

Governance is current at `[2..13]`, so there is no audit task. Nothing outside
`.specswarm/features/007-announcements-discovery/` changes, so there is no Docker lane.

- [ ] T010 `spec.md` SC-1 (`:161–163`) and its note (`:170–171`): quote revision 13's criterion verbatim, the workspace
  clause kept struck with its marker; the note becomes "struck at revision 13, nothing to build". FR-7's
  "narrows the criterion" note (`:113–116`) and Out of scope (`:232`) say the clause is struck at revision 13.
- [ ] T011 `spec.md` D-1 (`:200–210`): keep the reasoning as written; append *resolved by discovery revision 13 (Q3,
  option (b)), plan `394c33e` — the FLAGGED decision is now the rule, not a deviation from it*.
- [ ] T012 Provenance (modify Step 9): compute the append with the installed `audit-append` block, mode `scoped`
  (revision 13 rewords one criterion by a strike, so `full` would list it as unverified; its own change is what this
  cycle addresses), expecting 13 alone; write `audited_against` in `spec.md` frontmatter; create `audit-log.md` with
  its header, a seed row for specify's `[1]` and this cycle's row. Never touch `prompt_revision`,
  `discovery_revision` or `source_prompt`.
- [ ] T013 `cycle-report.md` § Cycle 2 (the send's block): Group A not applicable; Group B from the send; the three
  slice-0 Automated criteria cited from the mentor's lane readme-c at `10ddd3a` (an identical tree); D4 observed by the
  operator (Addendum 2); implement steps 10 and 9b.

**Parallel:** T010 and T011 touch the same file, so they run in order. T012 follows them, and T013 comes last.

## Dependencies

- T001 → T004. T004 → T005 → T006 → T007 → T008 → T009.
- T002 and T003 depend only on the contract, and run beside T004–T006.
