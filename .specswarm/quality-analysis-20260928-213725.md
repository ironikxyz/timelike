# Quality Analysis Report — timelike (feature 001, branch 001-agent-shell-baseline)

**Generated:** 2026-09-28T21:37:25Z by `/specswarm:analyze-quality`, run from `/specswarm:ship`.
**Informational only.** Plan's ruling makes the score a trend figure, never a merge gate. The merge bar
is listed in `quality-standards.md` § Quality Gates.

## Project type

Python (stdlib, 3.14.7 in the image) plus Bash plus Docker. There is no `package.json` or
`tsconfig.json`, so the command's web-oriented checks do not apply and were **not scored as zero**:
LSP semantic analysis, React anti-patterns, SSR, bundle size, lazy loading, images. Test framework:
pytest (units) and bats-core (e2e, in the image).

## Test coverage

- **Sources:** 8 files.
  - Python: `tools/agentio/agentio.py`, `tools/bin/timelike`, `tools/bin/timelike-conform`,
    `scan/evaluate.py`
  - Shell: `scan/scan.sh`, `scripts/demo.sh`, `image/rootfs/.../00-timelike-path.sh`
  - `image/Dockerfile`
- **Test files:** 25. The Docker lane at `12b7f9c` ran 174 unit tests and 118 e2e tests, all passing.
- **Python line+branch coverage** (host lane, `12b7f9c`): 95% overall.
  - `evaluate.py` 99%, `agentio.py` 92%, `timelike` 96%, `timelike-conform` 93%.
- **Untested by automation:** `scripts/demo.sh`, the SC-7 demo. It is Manual by design, and the
  operator observed it on 2026-09-28.

## Architecture

- Constitution H1–H9 hold in this feature. The agent image holds nothing of Adele's (SC-4, 18/18).
  Every tool goes through `agentio` (SC-5, 10/10). Defaults reach `bash -c` and `bash -lc` (SC-2, 12/12).
- Two files exceed `max_file_lines: 300`, each justified in `plan.md` Complexity Tracking:
  `scan/evaluate.py` (650) and `tools/agentio/agentio.py`.
- Anti-patterns found: none. ruff, `mypy --strict` and shellcheck are clean.

## Documentation

- Every Python file has a module docstring and full type annotations (`mypy --strict`).
- Public functions with docstrings:
  - `agentio.py`: 6 of 13
  - `timelike`: 2 of 4
  - `timelike-conform`: 1 of 15
  - `evaluate.py`: 15 of 28
- The contract is documented in `contracts/output-contract.md`. README present. LICENSE (MIT) present.

## Performance

- Agent-side tool start-up: under 100 ms p95 in the image (unit step, passed; the figure is not
  printed). The host measured 56.7 ms p95.
- e2e runs: every git call in SC-1 concludes within 20 s. The demo's calls took 0.09–0.13 s.

## Security

- **gitleaks:** 0 findings across git history. Secret-pattern grep over tracked files: 0.
- **Supply-chain scan:** PASS on image `sha256:727b8c49c28c`, with 0 blocking and 77 baselined (8 Critical,
  69 High, all unfixable in trixie). The baseline was reviewed by the operator and is due by 2026-12-27.
  Feature 12 must re-review the credential-class Criticals.
- No sudo, nft or iptables, no setuid or setgid, every capability dropped, no-new-privileges, no ssh client.

## Module scores (the command's rubric: tests 25, docs 15, architecture 20, security 20, performance 20)

| Module | Tests | Docs | Arch | Security | Perf | Total |
|---|---|---|---|---|---|---|
| tools/agentio | 25 | 10 | 20 | 20 | 20 | 95 |
| tools/bin | 25 | 8 | 20 | 20 | 20 | 93 |
| scan | 25 | 12 | 20 | 20 | 20 | 97 |
| image | 25 | 15 | 20 | 15 | 20 | 95 |
| scripts (demo) | 0 | 15 | 20 | 20 | 20 | 75 |

Security for `image` is scored 15, not 20: it carries 77 accepted findings, 8 of them Critical,
under a reviewed baseline. `scripts` scores 0 for tests because the demo is a Manual criterion,
observed by a person rather than automated.

**Overall Quality: 91%**

## Recommendations

- **High, scheduled:**
  - Re-review the baseline by 2026-12-27, or sooner if the base digest moves.
  - Feature 12 must re-review CVE-2026-11856, CVE-2026-19931 and CVE-2026-8926 before it merges.
- **Medium:** add docstrings to `timelike-conform`'s public functions (1 of 15 documented).
- **Low:**
  - Print the in-image start-up figure (run `tests/run.sh` with pytest `-s` for that test).
  - The demo stays Manual by design.

Issues found: Critical 0, High 0 (2 scheduled reviews), Medium 1, Low 1.
