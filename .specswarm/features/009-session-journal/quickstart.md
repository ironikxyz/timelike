# Quickstart — `journal` (009, slice 1)

```bash
journal                          # the agent: the last 20 entries of this session, oldest first
journal --all                    # the whole session
journal --all-sessions --agent a1
# the operator, with grant uses from Adele's ledger:
docker exec timelike-adele adeled ledger --json | docker exec -i timelike-agent journal --all-sessions --ledger -
```

- **Sessions and agents:** a harness that runs several agents gives each one `TIMELIKE_SESSION` and
  `TIMELIKE_AGENT`. Without them, every agent writes to session `default` and agent `-`.
- **Captured:**
  - every timelike tool call (001's events);
  - every `bash -c` / `bash -lc` command (the exit trap set by `/etc/timelike/shell-env.bash`).
- **Not captured:** `sh -c`, interactive shells, and a command that sets its own EXIT trap.
- **The records live in the session scratch** (`/tmp/timelike/<session>/`) and are disposable (rule 10).

## Host checks (no Docker)

```bash
make test-host PYTHON=<venv python>       # units (test_journal.py, test_agentio.py) and the hook lane
```
