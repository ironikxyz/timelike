# Quickstart: a nested environment (slice 0)

**The operator, once:**
1. Set `TIMELIKE_WORKSPACES` to the workspace parent, either in the environment or in the git-ignored `local.env`.
2. Add a grant that allows `docker.compose` to `adele/grants.conf`, for example:

   ```
   [grant local-env]
   capabilities = docker.compose
   budget = 0.00 USD
   ttl = 4h
   instances = 3
   ports = none
   ```
3. Run `make up`. It makes a new workspace and prints its path, and the host-git setting (`enforced` unless
   `TIMELIKE_HOST_GIT=lifted`).

**The agent, inside its container:**

```
cd "$TIMELIKE_WORKSPACE" && git clone … proj && cd proj
adele env up                  # waits until ready; lists each service and its address
pytest                        # against db.<project>:5432 and the others
adele env down                # removes everything it created, read back
```

**The operator's git:** never in the workspace. Clone or fetch from it, e.g.
`git clone <workspace>/proj ~/review/proj`. With git ≥ 2.45.1 a repository owned by another uid needs
`-c safe.directory=<path>` for that command.
