# Quickstart — 013 package guard

```bash
# Check what an install would do, without running it
package-guard --dry-run -- pip install requests six

# Install through the guard: it runs pip only if every name passes
package-guard -- npm install left-pad@1.3.0

# A refusal is exit 4 with an envelope; its "confirm" proceeds and records the override
package-guard -- pip install tl-absent-pkg ; echo $?          # 4
package-guard --yes -- pip install tl-absent-pkg              # pip runs; override recorded
journal                                                        # shows the call; its ref names the record

# Settings
TIMELIKE_PACKAGE_MIN_AGE_DAYS=7 package-guard -- pip install fresh-pkg
TIMELIKE_PACKAGE_TIMEOUT=3 package-guard -- npm install express
package-guard --agent-info                                     # the forms, the age, the limits, the lockfiles
```

Tests:
- `tests/unit/test_package_guard*.py`, on the host against `tests/fixtures/registry-standin.py`;
- the e2e files named after SC-1 to SC-4, in the image.

The bare `pip install` / `npm install` reach the guard only after FOR-MENTOR Item 24.
