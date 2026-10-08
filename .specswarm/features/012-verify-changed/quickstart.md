# Quickstart — 012 Verify changed

In the agent container:

```bash
# a test command, failures only (the exit is pytest's)
verify test -- pytest -q

# any runner; the format is read from the output, not the command
verify test -- npm test
verify test -- go test ./...
verify test --timeout 600 -- cargo test

# after an edit: what could it have broken?
verify changed --dry-run        # the selection and why, nothing run
verify changed                  # run it: tests importing the change, lint and type-check of the change
verify changed --since main     # against a branch instead of HEAD
```

**On the host** (advisory; the image decides), with the tools copied beside a venv interpreter:
`tests/unit/test_verify.py`. To re-record the fixtures, after changing `make-project.sh` or a runner
version: `tests/fixtures/verify/record.sh tests/fixtures/verify/recorded`, with `PYTEST`, `RUFF`, `MYPY`,
`GO`, `CARGO` and `JS_MODULES` set.

**D20 (manual, after the lane):**
1. In a project with tests, edit one source file so that one test fails.
2. Run `verify changed`.
3. The verdict names the tests importing the file, and the lint and type-check of that file only. The
   failure comes with its file and line.
