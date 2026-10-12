# Decisions Log — Feature 013
> Generated at 2026-10-12T00:27:30Z (read from the clock)
> Spec: .specswarm/features/013-package-guard/spec.md
> specswarm: 4.0.1-botbaubble.2.44.0 (the expanded PLUGIN_DIR); an attended run, no --dispatch

## Decision Key

| Tag | Meaning |
|-----|---------|
| ASSUMED | Assumption made without explicit spec guidance (confidence: high/medium/low) |
| DEFERRED | Decision postponed — noted for later resolution |
| FLAGGED | Judgment call between alternatives — requires review |
| ABSENT | What was NOT done and why — forced reflection on gaps |
| INHERITED | Assumption carried forward from a prior task's output |

---

### T001: The registry stand-in and its shape units
**Started:** 2026-10-12T00:27:30Z | **Completed:** 2026-10-12T00:29:49Z

INHERITED: (none — first task)
ASSUMED: one loopback server for both registries, PyPI under /simple/ and /files/, npm under /npm/ (the npm registry URL carries the path, which npm, pnpm and uv-free installs accept) — keeps one process per cell (confidence: high)
ASSUMED: upload times as offsets from the stand-in's start, so "one day old" holds when the installer asks; the formats are R2's (PyPI microseconds Z, npm milliseconds Z) (confidence: high)
FLAGGED: the stand-in writes its own pid file and the tests stop it by that pid — chose that over any process-name match after I broke the standing rule while smoke-testing: a pkill -f whose pattern matched my own command killed my shell (exit 144). No stand-in was left running (checked through /proc) (confidence: high)
ABSENT: an uv check against the stand-in on the host (no uv here; the image's uv meets it in the e2e cells); the HTML-only index mode has no unit of its own yet (T005 uses it)
Verification: tests/unit/test_registry_standin.py 7 passed (3.14.8 venv), including the host's real pip 24.0 installing tl-old 1.2.0 into --target and npm 10.9.7 installing tl-left and @tl/scoped; pnpm 11.5.1 installed from it by hand and wrote a v9 pnpm-lock.yaml
