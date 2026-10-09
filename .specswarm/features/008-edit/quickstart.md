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

## Slice 1: anchors and the syntax check

```bash
view --anchors src/app.py:40-48                          # each line: number, anchor, text
edit src/app.py --at 42:a3f9c1..48:0b11e2 --new $'…'     # replace lines 42-48 if both ends are unchanged
edit src/app.py --at 42:a3f9c1 --new 'return x + 1'      # one line
edit src/app.py --old 'def f(x):' --new 'def f(x)'       # exit 1: the edit would break the syntax; nothing written
```

- **Stale anchors:** exit 3, naming the changed lines and showing them now, with fresh anchors.
- **A syntax error the edit would introduce:** exit 1, with the checker's message and the lines around
  it.
- **Checked languages:**
  - Python (the interpreter's own compiler);
  - shell (`bash -n`);
  - TypeScript, TSX, Go and Rust (tree-sitter).

  Anything else says `syntax: not checked (language unknown)`.
- **Host lane:** Python and shell are checked anywhere. TypeScript, Go and Rust need the pinned wheels: in
  the image, or in a venv made with `pip install --require-hashes -r <generated from pins.env>`.
  Otherwise the verdict says `not checked (checker failed: no tree-sitter grammar …)`, and the units that
  need a grammar skip.
