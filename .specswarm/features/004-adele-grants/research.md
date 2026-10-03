# Research — 004 Adele & grants (slice 0)

Each entry gives the decision, the reason, and the alternatives considered. Spec decisions D-1 to D-9
are not repeated here, only what plan adds to them.

## R1 · Go toolchain, driver and pins
- **Decision:**
  - Go **1.27.1**: `GO_IMAGE=golang:1.27.1-trixie@sha256:3b77fc618ec235a1ab412de7737f120dd507c57e8d87de4cbb7994fb94275ed5`,
    the index digest read from Docker Hub on 2026-10-02
  - `modernc.org/sqlite` **v1.60.1** (SQLite 3.53.4)
  - `STATICCHECK_VERSION=2026.2.1` (module `honnef.co/go/tools` v0.8.1)
  - `GOVULNCHECK_VERSION=v1.8.0` (module `golang.org/x/vuln`)

  All of these go in `pins.env`.
- **Evidence:** a scratchpad prototype built with `CGO_ENABLED=0 go build -trimpath` produced a static
  6.6 MB binary that answered `select sqlite_version()` with 3.53.4. `go.sum` has 20 lines, and the
  module graph 26 modules.
- **Alternatives:**
  - `ncruces/go-sqlite3` (WebAssembly): the tech-stack note 1 names it the only other pure-Go option,
    but it has no advantage here
  - JSON files in place of SQLite: tech-stack names SQLite for the ledger, and concurrent writes from
    `serve` and `extend` need its locking

## R2 · One Go module, two binaries
- **Decision:** the module `timelike/adele` is in `adele/`, with these packages:
  - `cmd/adeled`: the server and the operator commands
  - `cmd/adele-standin`: the stand-in
  - `internal/grants`: parser and effective grant
  - `internal/ledger`: SQLite
  - `internal/broker`: the check order, quote, perform and refuse logic
  - `internal/standin`: the stand-in's handler and its record

  One Dockerfile, `adele/Dockerfile`, has two final stages: `adele` (scratch + `adeled`) and `standin`
  (scratch + `adele-standin`).
- **Why:**
  - The stand-in is tiny and shares JSON types with the broker.
  - Two final stages keep the stand-in out of Adele's image (spec FR-19), while one module keeps one
    `go.sum`.
  - Go units can run the real stand-in handler in-process through `httptest`, so the broker's provider
    path is tested against the real counterpart, not a mock (quality-standards Test types).
- **Alternatives:**
  - The stand-in in Python in the agent image: rejected, because FR-19 keeps it out of the agent image
    and the agent's networks.
  - Two modules: rejected, as two `go.sum` files for no gain.

## R3 · Compose wiring
- **Decision:**
  - Service `adele`: `container_name: timelike-adele`, image `timelike-adele:local`, built from
    `adele/Dockerfile`, target `adele`, with build args `GO_IMAGE` and `GIT_SHA`. Then:
    - `cap_drop: ALL` and `no-new-privileges`
    - `read_only: true`, with `tmpfs` at `/tmp`
    - user `10001:10001`
    - networks `adele-request` and `adele-standin`
    - volume `adele-state:/var/lib/adele`
    - bind `${ADELE_GRANTS:-./adele/grants.conf}:/etc/adele/grants.conf:ro`
    - secret `adele_canary`
    - a healthcheck through `adeled health`. It needs no shell: Go's own GET of `/v1/health`.
  - Service `adele-standin`: `container_name: timelike-adele-standin`, profile `standin`, target
    `standin`, network `adele-standin` only, secret `adele_canary`, volume `standin-state`.
  - `agent` gains `networks: [default, adele-request]` and `TIMELIKE_ADELE_URL=http://adele:8480`.
  - Both networks are `internal: true`.
  - The canary: the one-shot service `adele-secret` writes it into the volume `adele-secret`
    (`root:10001`, 0440), which Adele and the stand-in mount read-only. *(Revised at T010 from a host-file
    secret, which uid 10001 could not read: spec D-8.)*
- **Why:**
  - The volume's mountpoint is created in the image, owned by 10001, so the named volume is
    initialised with that owner (lore Q003: the creator owns).
  - The canary's volume is mounted read-only and the file is root-owned 0440, so the process cannot
    replace it (Q007).
  - `${VAR:-}` everywhere, as the compose header requires (Q002).
- **`make up` and the lane:** both use `--profile standin`, then wait for Adele's healthcheck. Not
  `--wait`: the one-shot `adele-secret` exits by design. The stand-in is test and demo only,
  and the D8 demo needs it. Without the profile, `docker compose up` starts the agent and Adele.
  - Adele with no grant file: the bind source must exist. `make grants`, a prerequisite of `build`,
    copies `adele/grants.example.conf` to `adele/grants.conf` if it is absent (git-ignored).
  - Neither ever overwrites an existing file.

## R4 · The lane: e2e, units and stamps
- `tests/run.sh`:
  - `up` uses `--profile standin`, then waits for Adele and the stand-in to be healthy.
  - New step `gounit`: `go test -cover ./...` in `GO_IMAGE`, with the repository read-only, output to
    `tests/out/go-unit.txt`. Recorded per package, and the total goes to `summary.json`
    `go_coverage`.
  - `container_left_running` lists all three containers.
  - It passes `ADELE_CONTAINER` and `STANDIN_CONTAINER` to bats.
- `helpers.bash` gains:
  - `ADELE_CONTAINER` and `STANDIN_CONTAINER`
  - `stamp_check_adele`: the image label, plus `adeled version` (no `cat` in scratch)
  - `adeled …` and `standin_list` wrappers
  - `start_adele_with GRANTS_FILE`: a throwaway Adele on a one-off network, for malformed-grant cells,
    without disturbing the running one
- **e2e files**, one per criterion, named after its distinguishing text (H7):
  - `adele-starts-with-agent-reached-only-through-request-interface.bats` (SC-1)
  - `adele-rejects-malformed-grant-with-line-at-fault.bats` (SC-2)
  - `request-within-grant-performed-beyond-exits-4-nothing-performed.bats` (SC-3; the exit-4 cells wait
    for Item 13)
  - `no-credential-held-by-adele-appears-in-agent.bats` (SC-4)
  - `every-performed-request-recorded-in-ledger.bats` (SC-5)
  - `adele-isolation-grant-file-and-extend-unreachable-from-agent.bats` (FR-7, stack rule 1, and
    the stand-in's own refusal FR-20)
- **Invocation styles:** each agent-side cell runs under `bash -c` and `bash -lc`, `notty`, as 001's
  tests do (quality-standards: one test per criterion per invocation style). The operator side
  (`docker exec timelike-adele …`) has one style.

## R5 · The scan gate
- `scan/scan.sh` scans `timelike-adele:local` as a **required** image, like the agent. A missing image
  is a failure, not a skip.
- Per-image base digest: Adele's is `GO_IMAGE`'s builder digest. A scratch final stage has no base
  layer, and Debian's digest would be false for it. The image-to-digest mapping is in `scan.sh`.
- New step `govulncheck`: Adele only, run from `GO_IMAGE` with `golang.org/x/vuln@GOVULNCHECK_VERSION`
  in `-json` mode over `adele/`. Findings are parsed in `evaluate.py` into the same `Vuln` record. A
  reachable vulnerability with a fix blocks, as the gate does for every other High or Critical; govulncheck
  carries no severity, so a reachable vulnerability is treated as High. Other images record the step as
  `none (not a Go image)`.
- No Adele baseline file unless the first scan finds an unfixable High or Critical. Then the gate
  proposes one, and a person reviews it (H9).
- pip-audit on a scratch image: the probe's failure is now recorded as `none (no interpreter in image)`
  rather than as a misleading message.

## R6 · Client start-up (C2 budget, 100 ms p95)
`adele` imports `urllib.request` lazily, inside the request path. `--help`, `--agent-info` and argument
errors stay on agentio's existing start-up path. It is measured in the image like the others.

## R7 · The exit-4 path while Item 13 is open
- Adele's 403 body is internal (contract `adele-http.md`) and carries every fact any envelope shape
  needs. It is built and tested in Go now.
- The client's mapping from the 403 body to stdout is the one piece held. Until the answer, `adele
  request` on a 403 raises a `ToolError(4, …)`, naming the grant, the limit and the extend command on
  stderr, with nothing on stdout. That meets "exits 4 … nothing is performed" but not "with an
  envelope", so SC-3's envelope cells stay `unconfirmed` until it is replaced.
- This is recorded as a FLAGGED decision. The interim form is not a contract shape, and is replaced, not
  extended.

## R8 · What `adele status` returns when Adele is unreachable
`adele status` returns a Result, never a ToolError, so conform's C3 and C4 see a header either way:
- **reachable:** exit 0, verdict `Adele reachable at <url> from the agent container · revision <sha>`
- **unreachable:** exit 1, verdict `unreachable: <url> from the agent container (<reason>)`, which names
  the vantage point (H3; cross-stack P001)

Its HTTP limit is 3 s, well under conform's 10 s.
