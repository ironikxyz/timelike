<!-- Tech Stack Validation: PASSED — plan § Tech Stack Compliance Report: Python stdlib, pytest, bats-core; none added -->

# Tasks: 011 Code intelligence (prompt 10, slice 1)

**Input:** spec.md, plan.md, research.md, data-model.md, contracts/symbols-cli.md. **Tests are required**
(H7). Conventions are as in 003–010:
- one commit per task, `[011] Tnnn: …`;
- a `decisions.md` section per task, with a SCOPE line from the installed `scope-check` block;
- delegates own disjoint files, don't commit, and stay out of `tools/`, `image/`, `.specswarm/`,
  `../bridge` and `../plan`.

**Story map:**
- US1: outline (SC-1)
- US2: def (SC-2)
- US3: callers (SC-3)
- US4: dependents (SC-4)
- US5: a stale cache (SC-5)
- D19: the demo

## Phase 1: Tests first (from the contract; delegated)

- [X] T001 [P] [US1] [US2] [US3] [US4] [US5] `tests/unit/test_symbols.py`, per research R7. Fixtures are
  written by the test, and counts come from the test's own list. Cover:
  - a 14-definition Python fixture: nested, decorated, async, multi-line signatures, and no body line in
    the output;
  - `def` ranking and exit 3;
  - `callers`: 3 call sites, comments and strings excluded, the text-based header;
  - `dependents`: direct and indirect, ranked;
  - a stale cache rebuilt, answering from the new content;
  - each text-based language (JS/TS, Go, Rust, shell);
  - a parse failure falling back to text;
  - binary and large files skipped;
  - a generated 1,000-file warm timing under 2 s;
  - the manifest.
- [X] T002 [P] [US1] [US2] [US3] [US4] [US5] e2e, each under `bash -c` and `bash -lc`, with its own
  workspace and session:
  - `tests/e2e/symbols-outline-fixture-14-definitions-line-ranges-no-bodies.bats` (SC-1)
  - `tests/e2e/symbols-def-file-and-line-first-exit-3-not-found-under-2s-warm.bats` (SC-2)
  - `tests/e2e/symbols-callers-3-call-sites-grouped-text-based-header.bats` (SC-3)
  - `tests/e2e/symbols-dependents-of-changed-file-ranked.bats` (SC-4)
  - `tests/e2e/symbols-stale-cache-rebuilt-answers-from-new-content.bats` (SC-5)
  - `tests/e2e/symbols-name-and-manifest.bats`: `type -a symbols`, and the manifest

## Phase 2: Implementation

- [X] T003 [US1] [US2] [US3] [US4] [US5] `tools/bin/symbols`, per `contracts/symbols-cli.md`:
  - the index in the session scratch, with freshness on every call (R1), using `search`'s walk and ignore
    rules loaded from `tools/bin/search`;
  - Python via `ast` (R2), and the text-based languages (R3);
  - `outline`, `def` (ranked, R4), `callers` (grouped), `dependents` (ranked, R4);
  - the bounds.
- [X] T004 `FOR-MENTOR.md`: Item 20, the index and the state root (seam 1): the cache lives in the session
  scratch and is rebuilt per session until 07 slice 1's state root exists.
- [X] T005 `pyproject.toml` (ruff and mypy lists), `Makefile` (`SHELLCHECK_FILES`: the e2e files),
  `README.md` (a symbols section).

## Phase 3: Polish

- [ ] T006 Host lane: lint, units with coverage, `make test-host`, host conformance, the e2e host
  stand-in, start-up. Results in `decisions.md`.
- [ ] T007 `cycle-report.md` § Cycle 1, implement step 10, `.specswarm/metrics.json`, the marker.

## Dependencies

- T003 → T005 → T006 → T007. T004 stands alone.
- T001 and T002 depend only on the contract, and run beside T003.
