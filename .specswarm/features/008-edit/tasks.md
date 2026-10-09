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
- [X] T005 [P] [US1] [US2] [US3] [US4] e2e, each under `bash -c` and `bash -lc`. Fixtures are built by
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
- [X] T007 `pyproject.toml` (the mypy and ruff lists), `Makefile` (`SHELLCHECK_FILES` gains the e2e files),
  and `README.md` (an `edit` section).

## Phase 4: Polish

- [X] T008 Host lane: lint (ruff, mypy, shellcheck), units with coverage (90%), `make test-host`,
  `timelike-conform` over `tools/bin`, and start-up timings. Results in `decisions.md`.
- [X] T009 `cycle-report.md` § Cycle 1, implement step 10, `.specswarm/metrics.json`, the marker.

## Dependencies

- T001 → T002 → T003. T001 → T006 (the manifest fields). T006 → T007 → T008 → T009.
- T004 and T005 depend only on the contract, and run beside T001–T006.

## Parallel

- One delegate writes T004 and another T005, while T001–T003 and T006 are built here.

## Strategy

MVP is US1 (exact match, shown after). US2 to US4 are the same tool and land in T006, which is tested
against T004 and T005 before T008.

---

# Cycle 2 — slice 1 (send `bridge/sends/06-rev1-20261009-102433.md`)

<!-- Tech Stack Validation: PASSED — plan § Tech Stack Compliance Report (Cycle 2): tree-sitter binding and three grammars approved in tech-stack 1.6.0; none prohibited; the installed tech-stack-taskscan block found no prohibited technology in these tasks -->

**Input:** spec § Slice 1, plan § Cycle 2, research R9 to R16, contract § Slice 1, data-model § Slice 1.
Conventions are as Cycle 1's: one commit per task, `[008] Tnnn: …`, a `decisions.md` section per task with
a SCOPE line, delegates own disjoint files and do not commit.

**Story map:** US5 is anchors (SC-7). US6 is the syntax check (SC-8, D15). US7 is the carried items
(FR-28).

## Phase 5: Setup

- [ ] T010 Pins and the image (R9):
  - `pins.env` gains `TREE_SITTER_VERSION`/`_SHA256`, `TREE_SITTER_TYPESCRIPT_*`, `TREE_SITTER_GO_*` and
    `TREE_SITTER_RUST_*`, with the cp314 manylinux wheel's hash for the binding;
  - `compose.yaml` passes them as build args;
  - `image/Dockerfile`, in the final stage after § 3, declares the `ARG`s and rejects empty or malformed
    ones. It installs the wheels into timelike's purelib with the pinned `uv`
    (`--target --require-hashes --no-deps --only-binary :all:`), imports each grammar and parses a line,
    and copies `tools/libexec/` to `/opt/timelike/libexec/` (root, 0755);
  - `tests/unit/test_agent_runtimes.py`'s pin, `ARG` and compose lists gain the new keys.

  The `runtimes` stage and `bench/vanilla/Dockerfile` are untouched.

## Phase 6: Tests first (delegated, from the contract)

- [ ] T011 [P] [US5] [US6] Units, `tests/unit/test_edit_slice1.py`, from `contracts/edit-cli.md` § Slice 1:
  - the anchors: applied, a changed end, past the end, a move, an ambiguous move, the usage errors, CRLF;
    the expected anchors are computed with `hashlib` in the test (P005);
  - the languages (extension, shebang, unknown);
  - each language: refused (with line and message), applied and ok;
  - an already-broken file (no new error applies, a new error in the written lines refuses);
  - the dry run that would be refused;
  - the checker's failures, via a lab copy of `edit` with a fake `libexec/syntax-check` (missing, crash,
    garbage output, hang at the 10 s limit);
  - the skip, and that no refusal names the skip flag;
  - the JSON `syntax` object;
  - a decoy `python3` and `bash` on PATH (P002).

  Grammar-dependent cases skip when `tree_sitter_typescript` is not importable.
- [ ] T012 [P] [US5] [US6] [US7] e2e in the image, from the contract:
  - `tests/e2e/edit-anchored-lines-unchanged-applies-changed-lines-refused-naming-them.bats` (SC-7);
  - `tests/e2e/edit-would-fail-syntax-check-refused-with-checker-error-file-byte-identical.bats` (SC-8:
    five languages and TSX, hash before and after, a decoy `python3`/`bash` in `~/.local/bin`, Go's
    valid fixture confirmed by `gofmt -e` in `GO_IMAGE` when set);
  - `tests/e2e/edit-slice-0-carried-items.bats` (FR-28: `type -a edit` under `bash -lc`, the owner branch
    under uid 1001);
  - `bash -lc` cells added to the five slice-0 criterion files;
  - each new file in `Makefile`'s `SHELLCHECK_FILES`.

## Phase 7: US5 — anchors (SC-7)

- [ ] T013 [US5] `tools/bin/view`: `line_body()` factored out of `window()` (output unchanged). `tools/bin/edit`:
  `--at` parsing and usage errors, the anchor check with `view.anchor_of`/`view.line_body`, the
  replacement, the stale and moved refusals with `view --anchors`-format lines, and `level: "anchors"`.

## Phase 8: US6 — the syntax check (SC-8, D15)

- [ ] T014 [US6] `tools/libexec/syntax-check`: the child (Python compile, `bash -n`, tree-sitter), per the
  contract's protocol.
- [ ] T015 [US6] `tools/bin/edit`:
  - language detection;
  - the child's run (own session, group killed at 10 s);
  - R12's refusal rule;
  - the refusal and the dry run that would be refused;
  - fail-open on the checker's failure;
  - `--skip-syntax-check`;
  - `syntax` in every verdict and in the JSON;
  - the manifest extras and exit-code texts;
  - `tests/unit/test_edit.py`'s `test_manifest`, updated.

## Phase 9: Polish

- [ ] T016 Lint and docs:
  - `pyproject.toml` (`syntax-check` in the ruff and mypy lists; `tree_sitter*` untyped imports);
  - `README.md`: the command reference via `scripts/readme_reference.py --write`, and the send's README
    status block **only if** SC-7, SC-8 and the D15 path are built;
  - `reboot.md`.
- [ ] T017 Host lane:
  - ruff, mypy and shellcheck;
  - units with the wheels in a scratch venv and without them;
  - `make test-host`;
  - `timelike-conform` over `tools/bin`;
  - the child's start-up cost, measured.

  Results go in `decisions.md`.
- [ ] T018 `cycle-report.md` § Cycle 2 (the send's block), and the final scope record. No commit after the
  report until the mentor says the lane has ended.

## Dependencies (Cycle 2)

- T010 is first, for the pin names.
- T011 and T012 depend on the contract only, and run beside T013 to T015.
- T013 comes before T015, since both edit `tools/bin/edit`. T014 comes before T015.
- T016 depends on T015. T017 comes after T011 to T016. T018 is last.

## Parallel (Cycle 2)

Two delegates write T011 and T012 while T013 to T015 are built here. Their files are disjoint from
`tools/` and `.specswarm/`.

## Strategy (Cycle 2)

The MVP is US6 (the syntax check), because it carries the Manual demo D15. US5 comes first only because
it touches `edit` with a smaller diff. US7 is tests only.
