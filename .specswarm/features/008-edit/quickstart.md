# Quickstart — `edit` (008, slice 0)

```bash
# one unique replacement; prints the edited region, numbered as view numbers it
edit src/app.py --old 'return x' --new 'return x + 1'

# multi-line text: the shell's own quoting ($'…' or a quoted newline)
edit src/app.py --old $'if x:\n    return x' --new $'if x:\n    return x + 1'

# look first: the unified diff, nothing written
edit src/app.py --old 'return x' --new 'return x + 1' --dry-run

# a CRLF, tab-indented file: copy the text as view showed it (LF, spaces); edit maps both
edit win.c --old $'if (x) {\n    y();\n}' --new $'if (x) {\n    y(1);\n}'
```

- **Exit 0:** edited, or nothing to do. **Exit 3:** no such file, no match (with the nearest candidates),
  or several matches (with their line numbers). **Exit 1:** refused, with nothing written.
- **There is no `--yes`.** An edit names its target exactly, applies whole or not at all, and shows what
  it changed, so rule 9 does not confirm it (discovery revision 13). `snapshot` before a risky series,
  and `undo` after.

## Host checks (no Docker)

```bash
make test-host PYTHON=<venv python>                 # units, including tests/unit/test_edit.py
TIMELIKE_BIN_DIRS=$PWD/tools/bin PATH=$PWD/tools/bin:$PATH timelike-conform   # C0–C9, edit included
```

The e2e files (`tests/e2e/edit-*.bats`) run in the image, in the operator's Docker lane.
