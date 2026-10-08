# Quickstart — `services` (010, slice 1)

```bash
services start web --port 8000 -- python3 -m http.server 8000   # returns when 8000 accepts connections
services list                                                    # state, port, uptime; died ones marked
services logs web -n 20
services stop web --dry-run                                      # what would be signalled
services stop web                                                # the whole tree; checks none remains
```

- **A start always concludes:** ready (exit 0), died (exit 1, with the log's tail), or not ready in time
  (exit 124, stopped unless `--keep`).
- **No `--yes` for your own services.** Stopping another session's service (`--session S`), or `--all`,
  asks for `--yes` (rule 9, discovery revision 13).
- **The registry lives in the session scratch,** which is disposable. A service whose records were
  cleared shows in `list` as unlisted.

## Host checks

```bash
make test-host PYTHON=<venv python>          # tests/unit/test_services.py with real processes
```
