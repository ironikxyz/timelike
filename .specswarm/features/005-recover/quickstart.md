# Quickstart — 005 Recover (slice 0)

In the agent container (`docker exec -it -u agent timelike-agent bash`):

```
mkdir -p ~/proj && cd ~/proj && git init -q -b main && echo hi > a.txt && mkdir src && echo x > src/m.py
snapshot -m "before the refactor"      # snapshot 1 taken: 2 files, 5 B (complete)
rm -rf src && echo oops > notes.txt     # the wrong turn
undo --dry-run                          # restore dir src, restore file src/m.py, remove file notes.txt
undo --yes                              # restored to snapshot 1: …; verified; the state before is snapshot 2
snapshot list                           # 2 snapshots: 2 before undo 1, 1 on demand
undo 2 --yes                            # undo the undo
```

`cd ~ && snapshot` is refused (the home directory). `undo` alone prints the confirmation envelope.

Tests: the e2e files `tests/e2e/snapshot-*.bats` and `tests/e2e/restore-*.bats` (and the rest named in
`tasks.md`) run in `make test`. The units `tests/unit/test_snapshot.py` and `tests/unit/test_undo.py`
run in `make test-host`.
