# Quickstart — `view` and `search` (006)

```bash
view src/engine.py              # lines 1-120 of 412; ends with: more: view src/engine.py:121-240
view src/engine.py:121-240      # the next window
view src/engine.py:40           # lines 30-50, line 40 marked >
view build/app.o                # binary file: ELF, 18.2 KiB (18640 bytes); content not shown
view src/engine.py --limit 0    # the whole file, when you mean it

search parse_args               # hits under ., grouped by file, 50 shown; ends with narrow: and more:
search -F 'a.b(' src            # fixed string
search -i todo --no-ignore      # case-insensitive, ignored files included
search no_such_thing            # exit 0, 0 matches
search no_such_thing --strict   # exit 1, no match (strict)
```

Under a harness, stdout is a pipe, so both print JSON. Add `--text` to see the text layout.

## Host checks (no Docker)

```bash
PYTHONPATH=tools/agentio python3 tools/bin/view --text tools/bin/snapshot
PYTHONPATH=tools/agentio python3 tools/bin/search --text 'def ' tools
```
