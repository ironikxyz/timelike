<!-- Tech Stack Validation: PASSED — plan § Tech Stack Compliance Report: Python stdlib, pytest, bats-core; none added -->

# Tasks: 008 Edit (prompt 06, slice 0)

**Input:** spec.md, plan.md, research.md, data-model.md, contracts/edit-cli.md. **Tests are required** (H7).
Conventions are as in 003–007:
- one commit per task, `[008] Tnnn: …`;
- a `decisions.md` section per task, with a SCOPE line from the installed `scope-check` block;
- delegates own disjoint files, don't commit, and stay out of `tools/`, `.specswarm/`, `../bridge` and
  `../plan`.

**Story map:**
- US1 a unique replacement, shown after (SC-1)
- US2 CRLF and tabs (SC-2, D6)
- US3 refusals, ambiguous and no match with candidates (SC-3, SC-4)
- US4 the dry run (SC-5)
- US0 rule 9 at revision 13, shared (FR-12)

## Phase 1: Foundational — rule 9 at revision 13 (outside 008; blocks `edit`'s manifest)

- [X] T001 [US0] `tools/agentio/agentio.py` and `tools/bin/snapshot` (R1, data-model § Manifest fields):
  - `Tool(confirm_protocol=None)`, where `None` means the same as `mutating`; true without `mutating` is
    a `ValueError`;
  - `--yes` in the parser, exit 4 in `codes()`, and `confirmation_required` in `envelopes()`, only when
    the tool confirms;
  - `confirm_required()` raises for a tool that does not confirm;
  - the manifest carries `confirm_protocol` and `dry_run`;
  - `UNDO_TOOL` gains `confirm_protocol=True`.

  Extend `tests/unit/test_agentio.py`: the three values and the default, flags, codes, envelopes, the
  manifest fields, and the `ValueError`.
- [X] T002 [US0] `tools/bin/timelike-conform` C2: R1's five checks. In `tests/unit/test_conform_violations.py`,
  each check is shown failing on a manifest that breaks it, and `edit`'s and `undo`'s shapes pass.
- [X] T003 [US0] 001's contracts:
  - `agent-info.schema.json`: `confirm_protocol` and `dry_run`, both optional, with "absent means" in
    their descriptions; `flags`' description changes to `--yes if confirm_protocol`;
  - `output-contract.md`: the `--yes` row, and § Confirmation's revision-13 sentence with the three
    cases.

## Phase 2: Tests first (from the contract; delegated)

- [X] T004 [P] [US1] [US2] [US3] [US4] `tests/unit/test_edit.py`, per research R8: the levels and
  uniqueness, the indentation inference, line endings, candidates (ranking, floor, overlap, deadline),
  the atomic write (concurrent change, unwritable, symlink, hard link, mode, owner), BOM and non-UTF-8,
  and the usage and refusal cases. Text and JSON shapes come from `contracts/edit-cli.md`.
- [ ] T005 [P] [US1] [US2] [US3] [US4] e2e, each under `bash -c` and `bash -lc`. Fixtures are built by
  `printf` in the test, and every byte claim is checked with `sha256sum` in the container:
  - `tests/e2e/edit-replacing-text-appearing-once-changes-only-that-text-prints-edited-region.bats` (SC-1)
  - `tests/e2e/edit-crlf-tab-indented-file-given-lf-and-spaces-preserves-crlf-and-tabs.bats` (SC-2)
  - `tests/e2e/edit-matches-more-than-once-refused-exit-3-listing-line-numbers.bats` (SC-3)
  - `tests/e2e/edit-matches-nowhere-refused-exit-3-nearest-candidates.bats` (SC-4)
  - `tests/e2e/edit-dry-run-prints-unified-diff-file-byte-identical.bats` (SC-5)
  - `tests/e2e/edit-name-and-manifest.bats`: `type -a edit` is exactly `/opt/timelike/bin/edit`; the
    manifest has `mutating: true`, `confirm_protocol: false`, `dry_run: true`; `--yes` is exit 2

## Phase 3: Implementation (US1–US4: one tool)

- [X] T006 [US1] [US2] [US3] [US4] `tools/bin/edit`:
  - reading and the refusals (R5);
  - the three levels (R2) and the file's conventions (R3);
  - the atomic write with the concurrent-change check (R5);
  - the after-view (`view`'s numbering);
  - the dry run's unified diff;
  - the candidates (R4).

  Output per `contracts/edit-cli.md`.
- [ ] T007 `pyproject.toml` (the mypy and ruff lists), `Makefile` (`SHELLCHECK_FILES` gains the e2e files),
  and `README.md` (an `edit` section).

## Phase 4: Polish

- [ ] T008 Host lane: lint (ruff, mypy, shellcheck), units with coverage (90%), `make test-host`,
  `timelike-conform` over `tools/bin`, and start-up timings. Results in `decisions.md`.
- [ ] T009 `cycle-report.md` § Cycle 1, implement step 10, `.specswarm/metrics.json`, the marker.

## Dependencies

- T001 → T002 → T003. T001 → T006 (the manifest fields). T006 → T007 → T008 → T009.
- T004 and T005 depend only on the contract, and run beside T001–T006.

## Parallel

- One delegate writes T004 and another T005, while T001–T003 and T006 are built here.

## Strategy

MVP is US1 (exact match, shown after). US2 to US4 are the same tool and land in T006, which is tested
against T004 and T005 before T008.
