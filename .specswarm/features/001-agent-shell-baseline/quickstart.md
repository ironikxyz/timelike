# Quickstart — 001 agent shell baseline (slice 0)

## Needs

- A Docker daemon (Docker Engine with Compose v2), reachable by the `docker` CLI
- Nothing else on the host: builds, tests and scans all run in pinned containers

## Build and run

```bash
make build            # docker compose build --build-arg GIT_SHA=$(git rev-parse HEAD); fails on an empty SHA
make up               # start the agent container (cap_drop ALL, no-new-privileges)
docker exec timelike-agent bash -c 'timelike'          # environment info, as the harness would call it
docker exec timelike-agent bash -c 'timelike --agent-info'   # manifest, with the build revision
```

## Verify

```bash
make test             # Docker lane: bats e2e from the runner image, plus pytest in the image (authoritative)
make test-host        # host lane: agentio/conform units plus an env-layer file check (advisory; no Docker)
make lint             # shellcheck, ruff, mypy --strict (pinned containers)
make scan             # supply-chain gate: Syft+Grype, pip-audit, gitleaks (blocks on fixable High/Critical or a secret)
```

## Demo (SC-7 → D1, Manual)

```bash
make demo
```

This runs `git commit` (no message), `git rebase --continue` and `git log` inside the container, both
with and without a TTY. It prints each command's exit code and elapsed time.

**Expected:**
- each command returns within seconds
- no editor, pager or prompt appears
- `git commit` exits 1 with "Aborting commit due to empty commit message"

The demo is **observed** by a person. It is recorded as such in the cycle report, and as
`unconfirmed` when no one watched.
