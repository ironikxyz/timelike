# Quality Analysis Report — 2026-09-29 (feature 002 ship)

**Overall Quality: 90%** (the average of 8 modules scored, 0 unscored). This is **informational**:
`enforce_gates: false` and `min_quality_score: 0`. The merge bar is quality-standards § Quality Gates,
and at `57a0942` it was met: the Docker lane passed, the scan passed, coverage was 97%, SC-3 was
observed, and the mentor signed off.

Scored with `lib/quality-scale.sh` (specswarm 4.0.1-botbaubble.2.15.0). Each component is scored
against its own weight.

| Module | Tests /25 | Docs /15 | Architecture /20 | Security /20 | Score |
|---|---|---|---|---|---|
| tools/agentio | 25 | 10 | 20 | 20 | 94 |
| tools/bin | 25 | 8 | 20 | 20 | 91 |
| scan | 25 | 12 | 20 | 20 | 96 |
| image | 25 | 15 | 20 | 15 | 94 |
| scripts | 0 | 15 | 20 | 20 | 69 |
| **bench/benchlib** (new) | 25 | 10 | 20 | 20 | 94 |
| **bench/bin** (new) | 25 | 8 | 20 | 20 | 91 |
| **bench images + run.sh** (new) | 25 | 15 | 20 | 15 | 94 |

**Performance is excluded from every module, not scored as 0:**
- bundle size is unavailable: `lib/bundle-size-monitor.sh` is not in this install
- lazy loading and images are not applicable (a CLI and container project, with no routes and no image
  assets)

**Evidence for the new modules:**
- **Tests:** 593 units in the Docker lane at `57a0942` and 592 on the host. Coverage is 96–100% per
  bench module. The e2e run was 176/176, with 5 bench tests.
- **Docs:**
  - every module has a docstring
  - `benchlib` documents 43 of 75 public functions and classes; the CLI 2 of 8
  - contracts: trace-schema and bench-cli
- **Architecture:** the rubric's React/SSR/inline-style patterns don't apply. There are no subprocess
  shells, `eval` or `innerHTML`.
- **Security:**
  - the "secret" grep hits only `keys.py`'s own word lists
  - the scan passes on all three images, with reviewed baselines
  - the bench images score 15, because the mentor noted the driver runs without `--cap-drop ALL` or
    `no-new-privileges`, and vanilla keeps Debian's setuid binaries (by design, as the comparison
    baseline)

**Recommendations**, none of them blocking:
1. 🟡 Harden the driver's `docker run` with `--cap-drop ALL` and `--security-opt no-new-privileges`
   (the mentor's note).
2. 🟢 Docstrings for public functions: `benchlib` (32 missing), `timelike-bench` (6), and
   `timelike-conform` (the 001 leftover).
3. 🟢 `scripts/`: `demo.sh` has no test; it is covered by the operator watching it run.
