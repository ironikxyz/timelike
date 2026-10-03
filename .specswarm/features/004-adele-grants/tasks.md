<!-- Tech Stack Validation: PASSED -->
<!-- Validated against: .specswarm/tech-stack.md v1.3.0 -->
<!-- No prohibited technologies found (mattn/go-sqlite3 and cgo appear only as what is avoided) -->
<!-- 0 unapproved technologies require runtime validation (urllib.request is Python stdlib; plan § Tech Stack Compliance) -->

# Tasks: 004 Adele & grants (prompt 12, slice 0)

**Input:** [plan.md](plan.md), [spec.md](spec.md), [data-model.md](data-model.md),
[contracts/](contracts/), [research.md](research.md), [quickstart.md](quickstart.md)

**Tests are required.** Constitution H7 makes every acceptance criterion a test. The merge bar is 90%
coverage per language, Go included (quality-standards). Units come before or beside each package.

**Conventions (features 001–003):**
- One commit per task, `[004] Tnnn: …`.
- Each task gets a `decisions.md` section: INHERITED, FLAGGED, ASSUMED and ABSENT lines, a Verification
  line, and a `SCOPE:` line computed with implement's `scope-check` block.
- Tick the task here.
- Delegates own disjoint files, don't commit, and don't touch `../bridge`, `../plan`, `.specswarm/` or
  each other's files. This instance reviews their work and commits it.
- **Process safety:**
  - Servers started in host experiments run under `setsid --wait timeout -k 5 N … </dev/null`.
  - Never `pgrep -f` or `pkill -f`. Find processes by the pid files they write.
- **Host Go:** `<scratchpad>/go/bin/go` (1.27.1), with `GOCACHE`, `GOMODCACHE` and `GOPATH` under the
  scratchpad. Nothing is installed on the host.

**Stories.** The spec's scenarios map to stories as follows:
- **US1** = Scenario 1 + SC-1 + SC-5: a request within its grant, performed and recorded. This is the MVP
- **US2** = Scenario 3 + SC-2: a malformed grant is rejected at start, with the line
- **US3** = Scenario 2 + SC-3 + D8: beyond the grant, exit 4, nothing performed, extended, retried.
  **The envelope part is held for FOR-MENTOR Item 13**
- **US4** = Scenario 4 + SC-4 + FR-7 + FR-20: credential isolation and reach-around attempts

## Phase 1: Setup

- [X] T001 The Go module skeleton and the pins:
  - `adele/go.mod` (module `timelike/adele`, go 1.27, `modernc.org/sqlite v1.60.1`) and `adele/go.sum`
  - `adele/cmd/adeled/main.go` and `adele/cmd/adele-standin/main.go`, stubs that exit 1, "not
    implemented"
  - `pins.env`: `GO_IMAGE`, `STATICCHECK_VERSION`, `GOVULNCHECK_VERSION` (research R1)
  - `.gitignore`: `adele/grants.conf`, `adele/canary`
  - Verify: `CGO_ENABLED=0 go build ./...` on the host
- [X] T002 *(its `canary` target was retired at T010; the canary is generated in Docker, spec D-8)* `adele/grants.example.conf`: the quickstart's `demo` grant, with a comment header documenting
  the format (data-model § Grant file).
  Then the Makefile targets `canary` (`tlcanary-` + 32 hex from `/dev/urandom` into `adele/canary`, mode
  0600, never overwritten) and `grants` (copy the example to `adele/grants.conf` if absent). Both are
  prerequisites of `build` and `up`.

## Phase 2: Foundational (blocks every story)

- [X] T003 [P] `adele/internal/grants/`: the parser and the effective grant.
  - `grants.go`, `grants_test.go`
  - Every malformation in data-model § Grant file yields `<file>:<line>: <what> — <how>`, with the
    exact line, and is table-tested one case per row.
  - `Effective(grant, extensions)` overlays extensions.
  - Value formatters return grant-file syntax (`0.40 USD`, `1h`, `8080, 9000-9010`).
  - Coverage ≥ 90%.
- [X] T004 [P] `adele/internal/ledger/`: SQLite through `modernc.org/sqlite`.
  - `ledger.go`, `ledger_test.go`
  - Schema v1 (`ledger`, `extensions`, `meta`); WAL; `busy_timeout`.
  - Append-only API: `Performed`, `Refused`, `Extended`, `Rows`, `Spent(grant)`, `Live(grant)`,
    `Extensions(grant)`.
  - Units against a temp file. That covers concurrent writers from two handles, as `serve` and
    `extend` are.
  - Coverage ≥ 90%.
- [X] T005 [P] `adele/internal/standin/`: the stand-in.
  - `standin.go`, `standin_test.go`
  - The handler for quote, create, delete and list, requiring `Authorization: Bearer <canary>` (401
    otherwise, with nothing changed).
  - Pricing `ceil(minutes × 25 / 60)` cents. A 409 on a duplicate name.
  - The JSON record file is written atomically (temp + rename).
  - Units through `httptest`, including the refusal without and with a wrong credential (FR-20).
  - Coverage ≥ 90%.

## Phase 3: US1 — a request within its grant (MVP)

- [X] T006 `adele/internal/broker/`: the request path.
  - `broker.go`, `broker_test.go`
  - Choose the grant (FR-9).
  - Check in order: capability → ttl → ports → instances → budget (the budget check uses the stand-in's
    quote).
  - Perform: create through the stand-in with the canary.
  - Record the performed row with its undo, and the refused row with its limit, allowed, needed and the
    exact extend command (contract `adele-http.md`).
  - Units run the **real** stand-in handler in-process (`httptest`), and check "performed" and "nothing
    performed" against the stand-in's own record (P004).
  - Coverage ≥ 90%.
- [X] T007 `adele/cmd/adeled/`: the server and the operator commands.
  - `main.go`, `serve.go`, `cmd_test.go`
  - `serve`: parse the grants (exit 2 and the error on stderr if malformed), read the canary from
    `ADELE_CANARY_FILE`, open the ledger, listen on `:8480`, with read, write and body limits.
  - Routes `/v1/health`, `/v1/grants`, `/v1/requests`.
  - `check`, `extend`, `ledger [--json]`, `version`, and `health` (the healthcheck client).
  - The revision is set through `-ldflags -X main.revision=`, and an empty one is refused at start (H8).
  - Units for each command.
- [X] T008 `adele/cmd/adele-standin/main.go`: `serve` (listen on `:8481`, canary from the file) and
  `list` (print the record file). A unit test for `list`.
- [X] T009 `adele/Dockerfile`:
  - a builder stage on `GO_IMAGE` with `CGO_ENABLED=0 -trimpath`, the stamp through ldflags, and a
    refusal of an empty or non-hex `GIT_SHA`
  - final stage `adele`: scratch, `/adeled` as `/usr/local/bin/adeled`, `/var/lib/adele` owned by
    10001, user 10001, the label `org.opencontainers.image.revision`
  - final stage `standin`: the same shape, with `/var/lib/standin`

  Also an `adele/.dockerignore` (build context `adele/`).
- [X] T010 `compose.yaml`:
  - the services `adele` and `adele-standin` (profile `standin`), per research R3
  - the networks `adele-request` and `adele-standin` (internal)
  - the volumes `adele-state` and `standin-state`
  - the secret `adele_canary`
  - the agent joins `adele-request` and gets `TIMELIKE_ADELE_URL`
  - Adele's healthcheck is `adeled health`
  - the header comment is updated
- [X] T011 `tools/bin/adele`: the client, per contract `adele-cli.md`.
  - `status`: always a Result, with a 3 s limit (R8).
  - `grants`.
  - `request standin.box create`:
    - performed → 0
    - 400 → 2
    - 404 → 3
    - 403 → the **interim** `ToolError(4, …)` (R7; FLAGGED)
    - unreachable or 502 → 1
    - its own limit → 124
  - urllib is imported lazily. `mutating: false`, `probe: ["status"]`.
  - `pyproject.toml`: add it to ruff `extend-include` and mypy `files`.
- [X] T012 `tests/unit/test_adele_cli.py`: the client's units against an in-process `http.server` fake
  of the HTTP contract.
  - each status mapping, the unreachable Result, the timeout, `--json` and `--text`
  - a conformance run of `timelike-conform` with `TIMELIKE_BIN_DIRS` pointing at the tool, in both the
    reachable and unreachable cases
  - the fake is the contract's client-side test double. The Adele side is covered by Go units against
    the real stand-in, and by e2e
- [X] T013 The lane:
  - `Makefile`: `build`, `up` and `down` gain `--profile standin`, `up --wait`, the Go lint target
    (gofmt, go vet, staticcheck in `GO_IMAGE`), and `SHELLCHECK_FILES` gains the new bats files.
  - `tests/run.sh`:
    - `up` with the profile and `--wait`
    - a new `gounit` step (`go test -cover ./...` in `GO_IMAGE`, to `tests/out/go-unit.txt`, with
      `go_coverage` in the summary)
    - `container_left_running` lists all three containers
    - the bats environment gains `ADELE_CONTAINER` and `STANDIN_CONTAINER`
  - `tests/e2e/helpers.bash`: `ADELE_CONTAINER`, `STANDIN_CONTAINER`, `stamp_check_adele`, `adeled`,
    `standin_list`, `start_adele_with`, and an `adele_request` wrapper
- [X] T014 [P] e2e `tests/e2e/adele-starts-with-agent-reached-only-through-request-interface.bats`
  (SC-1). Under `bash -c` and `bash -lc`:
  - `adele status` exits 0 from the agent, naming the revision = `GIT_SHA`
  - the stand-in's name does not resolve from the agent, and its address does not connect
  - one compose project holds all three
- [X] T015 [P] e2e `tests/e2e/every-performed-request-recorded-in-ledger.bats` (SC-5). A request within
  the grant, from a named session:
  - the ledger row's grant, session, resource and cost match the request and the stand-in's record
  - expiry = created_at + ttl
  - the undo is present

## Phase 4: US2 — a malformed grant rejected at start

- [X] T016 e2e `tests/e2e/adele-rejects-malformed-grant-with-line-at-fault.bats` (SC-2).
  - Through `start_adele_with`: six malformed files (unknown key, bad duration, negative budget, a pair
    outside a section, a duplicate grant, an unknown capability). Each exits non-zero, and its log
    names `grants.conf:<line>`.
  - A valid file starts healthy.
  - Single style: the operator side, with no agent shell involved.

## Phase 5: US3 — beyond the grant: exit 4, nothing performed, extended, retried

- [X] T017 e2e `tests/e2e/request-within-grant-performed-beyond-exits-4-nothing-performed.bats` (SC-3).
  Under `bash -c` and `bash -lc`:
  - within → 0, and the box is in the stand-in's record
  - one refusal per limit (capabilities, ttl, ports, instances, budget) → exit 4, and the stand-in's
    record unchanged
  - the extend command, run exactly as Adele printed it, makes the retry exit 0
  - the agent cannot run `adeled` and has no `docker`
  - **The envelope-shape cells are present and skipped**, with `skip "held: FOR-MENTOR Item 13"`
- [X] T018 **Was HELD (FOR-MENTOR Item 13); built in Cycle 2 on the ruling (discovery revision 10).**
  - The envelope schema or contract edit in `001-agent-shell-baseline/contracts/` (recorded under
    `changed_other_features`).
  - `agentio.grant_required(...)` and its units.
  - The client's exit-4 emission, replacing T011's interim form.
  - Un-skip T017's envelope cells.

## Phase 6: US4 — credential isolation and reach-around

- [X] T019 [P] e2e `tests/e2e/no-credential-held-by-adele-appears-in-agent.bats` (SC-4).
  - The test reads the environment's canary from the `adele-secret` volume through a throwaway
    container, so it knows the exact bytes. It runs a full cycle (performed,
    refused, extended, retried), then searches for the exact bytes through the agent's real paths:
    - `bash -c` and `bash -lc` `env`
    - every readable `/proc/*/environ` and `/proc/*/cmdline`
    - `grep -rF` over the readable filesystem (excluding `/proc` and `/sys`)
    - the client's JSON and text output
    - the session event log
  - Control: the same search finds the canary in Adele's container, so it is not vacuous.
- [X] T020 [P] e2e `tests/e2e/adele-isolation-grant-file-and-extend-unreachable-from-agent.bats`
  (FR-7, stack rule 1, FR-20):
  - From the agent: no path to `grants.conf`, `adele.db` or the canary exists.
  - A request to the stand-in from Adele's own network, made without the canary (through a throwaway
    on `adele-standin`), gets 401, and the record is unchanged.

## Phase 7: The scan gate

- [X] T021 `scan/scan.sh` and `scan/evaluate.py`:
  - `timelike-adele:local` is a required image
  - the per-image base digest (Adele: `GO_IMAGE`'s)
  - the `govulncheck` step, Adele only; others record `none`
  - the pip-audit message on an image with no interpreter
  - the parser for govulncheck JSON

  Units in `tests/unit/test_scan_report.py` and `tests/unit/test_scan_baseline.py`.

## Phase 8: Polish

- [X] T022 `README.md`: Adele, the grant file, the extend command, `make up`, and what the stand-in
  proves and does not.
- [X] T023 The host lane:
  - Go: `go test -cover`, gofmt, go vet, staticcheck, govulncheck
  - pytest, coverage, ruff, mypy, shellcheck
  - `.specswarm/metrics.json` `004.project_measurements_not_scored`
  - `cycle-report.md` § Cycle 1, including the credential-class CVE facts and the stderr report on
    `lib/features-location.sh`

## Dependencies

- T001 → T002 → (T003, T004, T005 in parallel) → T006 → T007, T008 → T009 → T010.
- T011 → T012.
- T010 + T011 → T013 → T014–T017, T019, T020 (e2e).
- T021 needs only T009.
- T018 waits on Item 13.
- T022 and T023 come last.

## Parallel execution

- **Delegated:** T003, T004 and T005 (one Go package each, disjoint files); T021 (scan gate, disjoint
  from everything else); and T014–T015 and T019–T020 once T013 lands (disjoint bats files, helpers
  owned by this instance).
- **This instance:** T006–T013 and T016–T017. They are the integration spine.

## Implementation strategy

- **MVP = US1** (T001–T015): a performed request, recorded, through the real compose topology.
- Then US2, US4 and the scan gate.
- US3's envelope lands when Item 13 is answered. Until then, SC-3's envelope cells report `unconfirmed`,
  and that is said in the cycle report.
