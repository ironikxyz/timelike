# Decisions Log — Feature 004
> Generated at 2026-10-02T04:42:35+00:00
> Spec: .specswarm/features/004-adele-grants/spec.md

## Decision Key

| Tag | Meaning |
|-----|---------|
| ASSUMED | Assumption made without explicit spec guidance (confidence: high/medium/low) |
| DEFERRED | Decision postponed — noted for later resolution |
| FLAGGED | Judgment call between alternatives — requires review |
| ABSENT | What was NOT done and why — forced reflection on gaps |
| INHERITED | Assumption carried forward from a prior task's output |

---

### T001: Go module skeleton and pins
**Started:** 2026-10-02T04:43:36+00:00 | **Completed:** 2026-10-02T04:43:36+00:00

INHERITED: (none — first task)
ASSUMED: `go 1.27` in go.mod and `GOTOOLCHAIN=local` in the lanes — the pinned GO_IMAGE is 1.27.1, so no toolchain download is wanted (confidence: high)
FLAGGED: go.mod starts with no requirements; T004's delegate adds modernc.org/sqlite when the ledger first imports it — chose that over requiring it now, because `go mod tidy` would drop an unimported requirement and two parallel delegates writing go.mod would collide (confidence: high)
FLAGGED: STATICCHECK_VERSION is the module version v0.8.1, not the release name 2026.2.1 — `go install …@2026.2.1` is not a valid module query; verified `staticcheck -version` prints "2026.2.1 (0.8.1)" (confidence: high)
ABSENT: no Dockerfile, compose or Makefile change — those are T002, T009, T010, T013
ABSENT: GO_IMAGE's digest was read from Docker Hub's registry API, not pulled — no Docker here; the lane's first build is its first real use
Verification: on the host (scratch Go 1.27.1), `CGO_ENABLED=0 go build ./...`, `go vet ./...`, gofmt and staticcheck v0.8.1 are all clean over the two stubs
SCOPE: out — .gitignore (1 of 5 changed files) (task has FLAGGED: yes)

### T002: Example grant file and the Makefile's canary and grants targets
**Started:** 2026-10-02T04:44:56+00:00 | **Completed:** 2026-10-02T04:44:56+00:00

INHERITED: `.gitignore` entries for adele/grants.conf and adele/canary — from T001 (confidence: high)
ASSUMED: the example grant is the quickstart's `demo` (1.00 USD, 1h, 2 instances, port 8080), so a first `make up` gives the D8 demo a grant that one 1h box (25 cents) fits and a port-22 request exceeds (confidence: high)
FLAGGED: the canary is made by `od -An -N16 -tx1 /dev/urandom` in the Makefile, not by a Go or Python helper — chose the shell form because it needs nothing installed on the host and runs before any image exists (confidence: high)
ABSENT: `up`/`down` do not depend on the targets yet beyond `build` (up depends on build) — the profile and --wait come in T013
ABSENT: no check that an operator-written grants.conf parses before `make up` — Adele herself refuses a malformed file at start (FR-6), which is the criterion under test
Verification: `make canary grants` wrote both files (canary matches ^tlcanary-[0-9a-f]{32}$, mode 600); a second run printed nothing and changed nothing; `git check-ignore` confirms both are ignored
SCOPE: in (2 changed files)

### T011: The agent-side client tools/bin/adele
**Started:** 2026-10-02T04:46:28+00:00 | **Completed:** 2026-10-02T04:46:28+00:00

INHERITED: the HTTP contract (contracts/adele-http.md) and the CLI contract (contracts/adele-cli.md) — from plan (confidence: high)
INHERITED: `mutating: false` and `probe: ["status"]` — from plan, raised in FOR-MENTOR Item 13 (confidence: medium)
FLAGGED: the exit-4 path is the INTERIM form (research R7): `ToolError(4, …)` on stderr naming the grant, the limit (allowed, needed) and the operator's extend command, nothing on stdout — chose a structured error over an envelope on stdout because every envelope shape changes 001's contract, which the send says to raise first (Item 13). T018 replaces it, it is not extended (confidence: high)
FLAGGED: the verb is optional to argparse and required by main() — chose that over a required positional because argparse refuses --help and --agent-info before agentio sees them when a positional is required (found by running --help: it exited 2) (confidence: high)
FLAGGED: `status` returns a Result on unreachable (exit 1, verdict names the URL and "from the agent container") rather than raising — conform's C3/C4 need the header on stdout either way (research R8) (confidence: high)
ASSUMED: `--ttl` is validated client-side only for shape (`[Nh][Nm]`); range and the grant's ttl are Adele's to check, so the refusal names the grant (confidence: high)
ASSUMED: urllib's `TimeoutError` (and `URLError(reason=TimeoutError)`) maps to exit 124 — the client's own limit fired (confidence: high)
ABSENT: no units yet — T012 (in-process fake of the HTTP contract, both conformance cases)
ABSENT: `grants`, `request` were not run against a live Adele — Adele's server is T007; e2e is T014–T017
Verification: ruff check, ruff format --check, mypy (16 files) clean; `--help` 20 lines — its exit-codes line was first cut at 200 columns (219 bytes; caught by checking, after a first claim of "no cut marker" that was wrong), so the labels were shortened and it now prints whole; `--agent-info` JSON; no verb → exit 2; `request` without --name → exit 2; `timelike-conform` over a bin dir holding only adele, with TIMELIKE_ADELE_URL pointing at a closed port: "verdict: pass · ok adele"
SCOPE: in (2 changed files)

### T003: adele/internal/grants — parser and effective grant (delegated)
**Started:** 2026-10-02T04:50:30+00:00 | **Completed:** 2026-10-02T04:50:30+00:00

INHERITED: the grammar, limits and value syntax — from data-model.md and contracts/adele-http.md (confidence: high)
ASSUMED: no inline comments; `#` after a value makes it unparsable (the grammar allows comment lines only) (confidence: high)
ASSUMED: section headers tolerate inner whitespace (`[ grant  ci-2 ]`); a capability listed twice is de-duplicated, not rejected (not in the data model's malformed list) (confidence: medium)
ASSUMED: PortSet keeps the operator's order; the canonical form joins items with ", "; empty is `none` (confidence: medium)
FLAGGED: Effective skips extensions for other grants rather than erroring — the caller passes the whole table (confidence: medium)
FLAGGED: a `ports` extension accepts exactly one port or range, not a list — the extend command only ever offers the single missing port (confidence: medium)
ABSENT: not wired into adeled — T007
ABSENT: the delegate's TestParseMalformed is 69 lines (its case table, 38 rows); every non-test function is ≤ 50 lines
Delegation: a general-purpose subagent wrote the package; this instance reviewed it, re-ran the checks, and exercised Load on adele/grants.example.conf and three malformed files (`grants.conf:6: unknown key "portz" — …`, `grants.conf:1: "x" is outside any [grant NAME] section — …`, `grants.conf:2: negative amount …`)
Verification: gofmt, go vet, staticcheck clean; `go test -cover` 98.1%, 54 tests and subtests
SCOPE: in (7 changed files)

### T004: adele/internal/ledger — SQLite through modernc.org/sqlite (delegated)
**Started:** 2026-10-02T04:50:45+00:00 | **Completed:** 2026-10-02T04:50:45+00:00

INHERITED: go.mod with no requirements — from T001, which left the sqlite requirement to this task (confidence: high)
FLAGGED: pragmas (busy_timeout 5000, WAL, foreign_keys) in the DSN with `_txlock=immediate`, rather than one PRAGMA after open — database/sql opens several connections and each needs them; immediate locking makes a second writer wait instead of failing (confidence: high)
FLAGGED: Extended refuses a limit outside the contract's five (confidence: medium)
FLAGGED: the column is named `grant` as in the data model, quoted in every statement (GRANT is an SQL keyword) (confidence: high)
ASSUMED: empty optional text is stored NULL and read back as ""; only cost and expiry are pointers (confidence: medium)
ASSUMED: `extensions` has its own id for insertion order; `ledger` has an index on (grant, outcome) (confidence: high)
ABSENT: no `-race` run — it needs cgo, which is prohibited; concurrency evidence is the two-handle test (50 rows + 50 extensions concurrently), repeated 20 times by the delegate with no busy error
ABSENT: ledger_test.go is 422 lines, over the 300-line guide; left as one file (the task named one)
Delegation: a general-purpose subagent wrote the package and go.mod/go.sum; this instance reviewed the DSN and the API, and re-ran the checks
Verification: `CGO_ENABLED=0 go build ./...`; gofmt, go vet, staticcheck clean; `go test -cover` 93.0% (14 tests); `go mod verify`: all modules verified; go.sum has no mattn/go-sqlite3 (mattn/go-isatty is modernc's terminal check, a different module)
SCOPE: in (6 changed files)

### T005: adele/internal/standin — the stand-in (delegated)
**Started:** 2026-10-02T04:50:45+00:00 | **Completed:** 2026-10-02T04:50:45+00:00

INHERITED: the stand-in's HTTP contract and pricing — from contracts/adele-http.md and data-model.md (confidence: high)
FLAGGED: the credential check runs before routing, so an unknown path or wrong method without the canary is 401, not 404/405 — nothing is said to a caller without the credential (confidence: high)
FLAGGED: routing by hand rather than ServeMux method patterns — the mux's own 404/405 bodies are plain text, the contract is JSON (confidence: high)
FLAGGED: a body over 64 KiB is 413 (JSON), the contract names no status (confidence: medium)
ASSUMED: `Bearer ` is matched exactly, case included — stricter than RFC 7235, and Adele is the only legitimate caller (confidence: medium)
ASSUMED: ReadCanary trims surrounding whitespace, reads at most 4 KiB, and its errors name the path, never the content (confidence: high)
ABSENT: no logging in the package at all, so the canary and the Authorization header cannot reach a log
ABSENT: server timeouts are not set here — Handler returns a handler; the http.Server with 10 s/30 s is T008
ABSENT: standin_test.go is 318 lines, 18 over the guide
Delegation: a general-purpose subagent wrote the package; this instance reviewed authorized() (an empty canary refuses everything; constant-time compare) and re-ran the checks
Verification: gofmt, go vet, staticcheck clean; `go test -cover` 93.9% (20 tests, 35 with subtests; the delegate also ran -race in its own run — this instance did not, cgo); FR-20's refusal is tested directly for six bad credentials on every endpoint, with the record unchanged each time
SCOPE: in (4 changed files)

### T012: Client units — tests/unit/test_adele_cli.py (delegated) and four fixes to tools/bin/adele
**Started:** 2026-10-02T04:53:14+00:00 | **Completed:** 2026-10-02T04:53:14+00:00

INHERITED: the client from T011, including the interim exit-4 form (confidence: high)
ASSUMED: the 403 tests pin the INTERIM form (exit 4, stdout empty, one stderr line in text, one {tool,error,code,remediation} object in JSON) — T018 replaces both the form and these tests (confidence: high)
FLAGGED: the fake Adele is a stdlib ThreadingHTTPServer in-process, recording every request — chose a fake of the HTTP contract for the CLIENT's units because the Adele side is covered by Go units against the real stand-in (T006) and by e2e; the fake is the contract's client-side double, not a provider mock (confidence: high)
FLAGGED: the delegate found, and this instance fixed in tools/bin/adele: (1) `--timeout nan`/`inf` crashed as an internal error, now a usage error (`math.isfinite`), as `run` does; (2) `status` on a non-200 answer said "unreachable" — she was reached, so it now says "answered … but not healthy (HTTP N: <her error>)" with `reachable: true`; (3) `grants` dropped Adele's error text, now routed through answered_error; (4) the performed verdict now says `box <name>` as contracts/adele-cli.md does (confidence: high)
ABSENT: no test of malformed 200 bodies (non-numeric cost) — the contract does not define them
ABSENT: `status` ignoring --timeout (its own 3 s, R8) is not tested
Delegation: a general-purpose subagent wrote the test file (34 tests) and reported the bugs without fixing them, as briefed; this instance fixed the tool and added 4 tests (nan, inf, unhealthy status, grants error text)
Verification: `pytest tests/unit/test_adele_cli.py` 38 passed in 8.4 s (includes timelike-conform passing with Adele reachable and unreachable, one event per invocation); the delegate's full unit run: 710 passed; ruff, ruff format, mypy (project config) and mypy --strict on the test file clean
SCOPE: in (2 changed files)

### T009: adele/Dockerfile — two FROM scratch stages (adele, standin)
**Started:** 2026-10-02T04:56:24+00:00 | **Completed:** 2026-10-02T04:56:24+00:00

INHERITED: GO_IMAGE from pins.env (T001); the binaries' entry points and the `main.revision` stamp variable (T007/T008, in the tree, not yet committed) (confidence: high)
FLAGGED: one builder, two final stages selected by compose `target` — the stand-in never enters Adele's image (FR-19) while one go.sum serves both (research R2) (confidence: high)
FLAGGED: the build fails unless `adeled version` prints exactly GIT_SHA — the stamp is checked inside the build, not only refused when empty (H8; cross-stack P003) (confidence: high)
FLAGGED: root `.dockerignore` now also excludes adele/canary and adele/grants.conf — the agent image's build context is the repository root, and although its COPYs never name them, the canary should not travel in any context (FR-18); adele/.dockerignore excludes them from Adele's context too (confidence: high)
ASSUMED: `/var/lib/adele` and `/var/lib/standin` are created in the builder with `install -d -o 10001 -m 0700` and copied with --chown, so a named volume mounted there is initialised owned by 10001 (lore Q003: the creator owns) (confidence: medium — Docker's volume-initialisation from image content is the documented behaviour, but it is not observed until the lane)
ABSENT: no `docker build` here (no daemon; R10). Verified instead on the host: a copy of the context with test files excluded (as adele/.dockerignore does) builds both binaries with the Dockerfile's flags; `adeled version` equals the stamp; `ldd`: not a dynamic executable
ABSENT: no /etc/passwd in the scratch images — USER is numeric (10001:10001), nothing needs a name
SCOPE: out — .dockerignore (1 of 3 changed files) (task has FLAGGED: yes)

### T010: compose.yaml — Adele, the stand-in (profile), the canary volume, two internal networks
**Started:** 2026-10-02T04:58:24+00:00 | **Completed:** 2026-10-02T04:58:24+00:00

INHERITED: the images and targets from T009; `make grants` from T002 (confidence: high)
FLAGGED: **spec D-8 revised.** The canary is generated by a one-shot service `adele-secret` (pinned DEBIAN_IMAGE, network none, caps CHOWN/FOWNER only) into the volume `adele-secret`, `root:10001` 0440, mounted read-only into Adele and the stand-in — chose that over the planned host file mounted as a compose secret, because a file written by `make` is owned by the operator's uid at 0600, compose file secrets are bind mounts, and uid 10001 could not read it without setfacl/chown on the host ("nothing installed on the host"). The new form is lore Q007's preferred one: root-owned, readable, not replaceable, and the canary never touches the host's disk. `make canary` and the adele/canary ignore entries are retired; T001/T002/T009's decisions above stand as written then (append-only) (confidence: high)
FLAGGED: no `--wait` on `up` — the one-shot `adele-secret` exits by design, and `--wait`'s treatment of an exited dependency varies by compose version; T013 waits on Adele's healthcheck instead (confidence: medium)
FLAGGED: the binaries' default canary path is now /run/adele-secret/canary (changed in the T007/T008 files, committed with them) (confidence: high)
ASSUMED: `internal: true` networks give no route out and still resolve service names among members (compose's documented behaviour) — first observed in the lane (confidence: high)
ASSUMED: the agent keeps `default` plus `adele-request`; Adele and the stand-in are on internal networks only (spec D-2) (confidence: high)
ABSENT: no `docker compose config` run (no Docker here); the YAML parses (PyYAML: 4 services, 2 networks, 3 volumes), and the canary command was executed on the host with the volume path substituted: `tlcanary-<32 hex>\n`, mode 0440, a second run a no-op
ABSENT: the stand-in has no tmpfs — its atomic write uses its own volume, and Go needs no /tmp for it
SCOPE: out — .dockerignore, .gitignore (2 of 5 changed files) (task has FLAGGED: yes)

### T013: The lane — Makefile, tests/run.sh, tests/e2e/helpers.bash
**Started:** 2026-10-02T04:59:57+00:00 | **Completed:** 2026-10-02T04:59:57+00:00

INHERITED: compose services, the profile and container names from T010; the canary volume (D-8 revised) (confidence: high)
FLAGGED: `up` (run.sh and make) is `--profile standin` then `wait_healthy` on Adele and the stand-in (90 s; on failure the container's last log lines, where a malformed grant file names its line) — not `--wait`, because the one-shot adele-secret exits by design (confidence: medium)
FLAGGED: `gounit` runs in the pinned GO_IMAGE against adele/ read-only, independent of our images (no "needs build"): Go units do not need them. It needs network for modules (said in the header, as the unit step says for PyPI) (confidence: high)
FLAGGED: helpers read the canary from the volume through a throwaway of the AGENT's image (root, no network, cap-drop ALL) — Adele's image is scratch (no cat), and the test must know the exact bytes (SC-4) (confidence: high)
FLAGGED: `adele_run_with_grants` runs a throwaway Adele foreground with `--network none`, a tmpfs ledger and the fixture file bind-mounted from REPO_HOST — malformed files exit at once; a valid one serves until the 10 s bound (124) (confidence: medium)
ASSUMED: compose names the volume `timelike_adele-secret` (project name `timelike` from compose.yaml) — overridable by ADELE_SECRET_VOLUME (confidence: high)
ASSUMED: `make lint` gains a Go lint line (gofmt, go vet, staticcheck@STATICCHECK_VERSION in GO_IMAGE) and SHELLCHECK_FILES names the six new bats files, which T014–T020 create (confidence: high)
ABSENT: summary.json's `container_left_running` stays one string (now three names), so its readers do not change shape
ABSENT: no Go coverage figure is parsed into summary.json — go-unit.txt carries `coverage: N%` per package; the cycle report reads it
Verification: `bash -n` and shellcheck (-x) clean on tests/run.sh and helpers.bash; `make -n up` and `make -n lint` show the profile and the staticcheck line. Nothing ran against Docker (R10)
SCOPE: in (3 changed files)

### T021: The scan gate — Adele required, per-image base digest, govulncheck (delegated)
**Started:** 2026-10-02T05:05:24+00:00 | **Completed:** 2026-10-02T05:05:24+00:00

INHERITED: Adele's image name and GO_IMAGE pin — from T001/T009/T010 (confidence: high)
FLAGGED: Adele is a REQUIRED image like the agent (missing → the scan fails before anything runs), not skipped like the bench images — a skip would pass a gate that never looked (research R5) (confidence: high)
FLAGGED: `base_digest_of` maps Adele to GO_IMAGE's digest, everything else to DEBIAN_IMAGE's — her final stage is FROM scratch; the builder is her only base (confidence: high)
FLAGGED: govulncheck findings: a called vulnerable function is gated as High (govulncheck carries no severity; research R5); imported-only and required-only are labelled `imported`/`required` and never block — chose those labels over inventing medium/low (confidence: medium)
FLAGGED: an empty or config-less govulncheck stream fails the step (no evidence a scan happened, H3); a normal stream with no findings is a pass (confidence: high)
FLAGGED: the pip-audit probe runs the interpreter as the entrypoint (scratch has no /bin/sh); docker's 126/127 → `none (no interpreter in image)`, any other failure → error — the 126/127 mapping is Docker's documented behaviour, not observed here (confidence: medium)
ASSUMED: the step-name column widened from 11 to 13 characters; nothing parses it (the delegate checked) (confidence: high)
ABSENT: no scan/baseline/timelike-adele.json — correct per R5; the first real scan proposes one if a finding needs a person
ABSENT: nothing ran against Docker; the delegate drove scan.sh through a stand-in `docker` in unit tests (four tests that fail against the old scan.sh)
ABSENT: a note for the lane: Grype will also report Go stdlib vulnerabilities in Adele's binary whether reachable or not, so a fixable stdlib High can block through Grype even when govulncheck rates it not called
Delegation: a general-purpose subagent made the change; this instance read the scan.sh diff and re-ran the checks. Observed: real govulncheck v1.8.0 over adele/ (`-format json`) reports no findings today
Verification: `pytest tests/unit/test_scan_report.py tests/unit/test_scan_baseline.py` 110 passed; ruff, ruff format, mypy (16 files), shellcheck clean
SCOPE: in (4 changed files)

### T022: README — Adele, the grant file, the extend command, the stand-in's limits
**Started:** 2026-10-02T05:05:50+00:00 | **Completed:** 2026-10-02T05:05:50+00:00

INHERITED: the client's commands and the interim refusal form (T011/T012); the operator commands (T007); the canary in a volume (T010) (confidence: high)
FLAGGED: the README shows the refusal as it is today (stderr, exit 4) and says the envelope waits on 001's exit-4 contract — rather than documenting an envelope that does not exist yet (confidence: high)
ASSUMED: "the Docker socket at 13, fly.io at 14" is the operator's recorded decision (the send) and fit to state (confidence: high)
ABSENT: no CHANGELOG.md — quality-standards' require_changelog_entry is noted for the mentor in plan.md; 001–003 shipped without one
ABSENT: no announcement in harness context files (T3 boundary allows it; slice 0 announces through `timelike`'s tool list and `--help`)
SCOPE: in (1 changed files)

### T006: adele/internal/broker — the request path (this instance), tests (delegated)
**Started:** 2026-10-02T05:11:28+00:00 | **Completed:** 2026-10-02T05:11:28+00:00

INHERITED: grants (T003), ledger (T004), stand-in (T005) APIs; the HTTP contract and check order (plan) (confidence: high)
FLAGGED: requests are serialised by one mutex around check-then-perform — chose that over per-grant locks or optimistic re-checks, because two concurrent requests could otherwise each fit a budget only one fits; slice 0's volume makes the cost irrelevant (confidence: high)
FLAGGED: the check order is capability → ttl → ports → instances → budget; only the budget check quotes, and the quote is a read — nothing is performed before the last check passes (P004 tested against the stand-in's own record) (confidence: high)
FLAGGED: with no grant named: the single allowing grant; several → 400 listing them; none and only one grant exists → refused on capabilities against it; none among several → 400 (data-model; FR-9) (confidence: medium)
FLAGGED: "performed upstream, ledger write failed" answers 500 with `performed: true` and the box's name — the one state that must never be silent (P5); the test confirms the box really exists (confidence: high)
FLAGGED: the extend value is printed unquoted (`… budget 0.50 USD`); adeled extend joins its remaining arguments, so the printed command works pasted (D-4) (confidence: high)
FLAGGED: StandinClient errors are passed through redact() before they can reach the agent, so a canary echoed in an upstream error never leaves Adele (FR-18) (confidence: high)
ASSUMED: expiry = the stand-in's created_at + ttl, truncated to the second (confidence: high)
ABSENT: two branches stay uncovered on purpose: a zero created_at from the stand-in and a 200 with unreadable JSON — the real stand-in produces neither, and faking the provider is what the tests must not do
ABSENT: no -race run (needs cgo); the mutex is tested by outcomes: 8 concurrent requests against a budget that fits 3 → exactly 3 performed, 3 boxes in the stand-in's record
Delegation: this instance wrote broker.go, check.go and http.go; a general-purpose subagent wrote the tests (64 incl. subtests) against the REAL stand-in handler via httptest and the real StandinClient, temp-file ledger, and reported one latent bug, fixed here: a capabilities refusal against a grant with an empty capability list was a 500 (ledger rejects an empty `allowed`); `allowed` is now `none`, as an empty port set prints — the grant file cannot express such a grant today
Verification: gofmt, go vet, staticcheck clean; `go test -cover ./internal/broker/` 99.0%; host integration (T008's binaries, the real Python client): performed, refused on ports/ttl/instances, the printed extend command, retry performed, 7 ledger rows, stand-in 401 without the canary, canary in no client output
SCOPE: in (9 changed files)

### T007: adele/cmd/adeled — serve and the operator's commands (this instance), tests (delegated)
**Started:** 2026-10-02T05:11:28+00:00 | **Completed:** 2026-10-02T05:11:28+00:00

INHERITED: the broker (T006); the canary volume path /run/adele-secret/canary (T010) (confidence: high)
FLAGGED: Adele refuses to start when unstamped (H8), on a malformed grant file (exit 2, the parser's file:line message — FR-6), on an unreadable or malformed canary (exit 2, never echoing its content), or an unopenable ledger (exit 1) — every one before listening (confidence: high)
FLAGGED: `health` is Adele checking herself over loopback (scratch has no shell or curl) and is compose's healthcheck (confidence: high)
FLAGGED: `ledger --json` has its own snake_case shape (the data model's column names, undo as an object) — the ledger package's Row has no JSON tags, and the e2e tests read this (confidence: high)
FLAGGED: `ready` is sent after signal.NotifyContext (the test delegate's suggestion): a signal sent on ready is handled, never fatal (confidence: high)
ASSUMED: an `extended` ledger row's text form says "was X, set to Y" or "was X, added Y" (ports and capabilities add) — the first draft's "X → Y" read as a replacement (seen in the host integration run) (confidence: high)
ABSENT: srv.Serve failing after start, Shutdown failing, and the ledger failing after extend's checks are not covered — no in-process fault injection; most of the 5.9% gap
ABSENT: no TLS on the request interface — an internal network joined only by the agent and Adele; slice 2 revisits the network
Delegation: a general-purpose subagent wrote cmd_test.go, serve_test.go and ops_test.go; serve's full lifecycle is tested by a guarded self-SIGINT (the test registers its own signal channel first; the signal is sent only after a request was answered)
Verification: gofmt, go vet, staticcheck clean; `go test -cover ./cmd/adeled` 94.1%
SCOPE: in (6 changed files)

### T008: adele/cmd/adele-standin — serve, list, health (this instance), tests (delegated)
**Started:** 2026-10-02T05:11:28+00:00 | **Completed:** 2026-10-02T05:11:28+00:00

INHERITED: the stand-in handler and store (T005) (confidence: high)
FLAGGED: `list` reads the record file directly, not through HTTP — it is the stand-in's own account (P004), and needs no canary (confidence: high)
FLAGGED: `health` only connects (every HTTP request needs the canary, and the healthcheck must not hold it) (confidence: high)
FLAGGED: serve proves at start that the record directory is writable (a temp file, created and removed) — the test delegate found it started on a read-only directory and then failed every create with a 500 (confidence: high)
ABSENT: the stand-in logs one start line and nothing per request — no canary or Authorization header can reach a log
Delegation: a general-purpose subagent wrote main_test.go and reported the unwritable-directory finding; fixed here, and its test now fails rather than skips if it regresses
Verification: gofmt, go vet, staticcheck clean; `go test -cover ./cmd/adele-standin` 96.1%
SCOPE: in (2 changed files)

### T014: e2e SC-1 — one compose project; the agent reaches Adele only through her interface (+ the lane's grant file and state reset)
**Started:** 2026-10-02T05:11:59+00:00 | **Completed:** 2026-10-02T05:11:59+00:00

INHERITED: compose topology (T010); helpers and compose_up (T013) (confidence: high)
FLAGGED: **the lane resets Adele's state.** tests/run.sh now runs `docker compose --profile standin down --volumes` before `up`, and starts Adele on tests/e2e/fixtures/adele/grants.conf (ADELE_GRANTS), never the operator's file — chose that over sharing the demo grant, because the ledger and the stand-in's record persist in volumes: a second run against `demo` (2 instances, 1.00 USD) would refuse everything. Slice 0 holds no real resource or credential, so nothing is lost; the README says to run `make up` afterwards (confidence: high)
FLAGGED: the lane's grant file has one grant per refusal cell and style (ttl-c, ttl-lc, …), so no cell's spending or extension reaches another; `adeled check` on the host: ok, 10 grants (confidence: high)
FLAGGED: "reaches Adele only through her interface" is shown from both sides: from the agent, the stand-in neither resolves (getent rc 2) nor connects on its address (read from outside); from outside, Adele is on the two internal networks only and the agent on its default + adele-request (confidence: high)
FLAGGED: helpers gain `pyq` — Python from the agent's image in a throwaway with no network, reading stdin — because the runner has no jq or python, and the agent container must never see the ledger (confidence: high)
ASSUMED: Go templates range over maps in key order, so the network lists compare as fixed strings (confidence: high)
ABSENT: nothing here ran (no Docker; R10) — shellcheck (-x) is clean over the file and helpers; the lane is its first execution
SCOPE: in (4 changed files)

### T015: e2e SC-5 — every performed request recorded in the ledger
**Started:** 2026-10-02T05:11:59+00:00 | **Completed:** 2026-10-02T05:11:59+00:00

INHERITED: `adeled ledger --json`'s shape (T007); `standin_list` (T013) (confidence: high)
FLAGGED: the row is checked against the stand-in's OWN record, not Adele's response: cost = the box's charged cost (38 cents for 90 m), expiry = the stand-in's created_at + 90 m, to the second (P004) (confidence: high)
ABSENT: not run (no Docker); shellcheck clean
SCOPE: in (1 changed files)

### T016: e2e SC-2 — a malformed grant rejected at start with the line at fault
**Started:** 2026-10-02T05:11:59+00:00 | **Completed:** 2026-10-02T05:11:59+00:00

INHERITED: adele_run_with_grants (T013), the parser's messages (T003) (confidence: high)
FLAGGED: six malformations through the real image (unknown key, bad duration, negative budget, pair outside a section, duplicate grant, unknown capability), each with its exact line; the grammar's full table is Go-unit-tested — checked on the host: `adeled check` gives exactly the asserted file:line for all six (confidence: high)
FLAGGED: the bound is decided by elapsed time (the runner's timeout may be busybox's, 128+signal), and the valid-file cell expects "still serving at the bound" (confidence: medium)
ABSENT: one style (operator side): no agent shell is involved in starting Adele
SCOPE: in (7 changed files)

### T017: e2e SC-3 — within the grant performed; beyond it exit 4, nothing performed, extended as printed, retried
**Started:** 2026-10-02T05:11:59+00:00 | **Completed:** 2026-10-02T05:11:59+00:00

INHERITED: the interim refusal form (T011, R7) (confidence: high)
FLAGGED: the extend command is run EXACTLY as the refusal printed it, from the runner (`bash -c "$cmd"`), then the identical request is retried — the D8 exchange automated; the Manual D8 demo stays the operator's with the mentor (confidence: high)
FLAGGED: the capabilities limit is not e2e-tested: slice 0 knows one capability and no grant the parser accepts can lack it; Go units cover it (T006) (confidence: high)
FLAGGED: the envelope cells are present and `skip`ped ("held: FOR-MENTOR Item 13"), so they cannot be forgotten (confidence: high)
ASSUMED: agentio's stderr error line is not cut at 200 columns — checked on the host: a 214-character refusal arrives whole (confidence: high)
ABSENT: not run (no Docker); shellcheck clean
SCOPE: in (1 changed files)

### T019: e2e SC-4 — no credential held by Adele appears in the agent
**Started:** 2026-10-02T05:11:59+00:00 | **Completed:** 2026-10-02T05:11:59+00:00

INHERITED: canary_bytes (T013), the canary volume (T010) (confidence: high)
FLAGGED: the canary is NEVER passed into the agent container, even as a search pattern (it would then be in /proc/self/cmdline): every search streams the agent's env, /proc, filesystem (tar of / minus /proc /sys /dev, as the agent user) and the cycle's outputs OUT and greps on the runner (cross-stack P005) (confidence: high)
FLAGGED: a control plants the canary in a throwaway of the agent's image (file, env, a live process's cmdline) and the same pipelines must find it — so a zero is a result (confidence: high)
FLAGGED: fixed while writing: the refused port for the bash -c cell was computed as `2c` (a bash substitution slip); now 2 and 22 (confidence: high)
ABSENT: not run (no Docker); shellcheck clean
SCOPE: in (1 changed files)

### T020: e2e isolation — nothing of Adele's in the agent; the stand-in refuses without the credential
**Started:** 2026-10-02T05:12:00+00:00 | **Completed:** 2026-10-02T05:12:00+00:00

FLAGGED: "nothing of Adele's is mounted" is read from outside (`docker inspect` Mounts = 0) — a path the agent cannot stat proves nothing (001's /var/lib/adele placeholder is unlistable to the agent by design, spec D-6) (confidence: high)
FLAGGED: the stand-in's refusal is tested from a throwaway ON its network (the agent is not on it), without and with a wrong credential: 401 both, and no box created (FR-20) (confidence: high)
ABSENT: not run (no Docker); shellcheck clean
SCOPE: in (1 changed files)

### T023: Host lane, implement step 10, metrics, cycle report
**Started:** 2026-10-02T05:16:20+00:00 | **Completed:** 2026-10-02T05:16:20+00:00

INHERITED: every task above; T018 is held (FOR-MENTOR Item 13) (confidence: high)
FLAGGED: implement step 10's component reasons are written in the plugin's own attribution wording ("could not be run on this machine") so 2.24.0's D74 split counts them as the machine's, not SpecSwarm's — the first run used other words and they fell into "unattributed" (confidence: high)
FLAGGED: the plugin's own `visual-alignment — unavailable: screenshot analysis is not implemented` (the command's literal) is counted "unattributed" by 2.24.0's unmeasured-explains-itself block — a defect for the mentor to relay; not worked around (confidence: high)
FLAGGED: the coverage-traced unit run had 2 failures, both test_bench_cli "setup failed: hung" (002's known load-dependent watch item; the run overlapped a delegate's Go test runs); test_bench_cli.py alone then passed 24/24 three times; this branch's diff touches no bench or agentio file — recorded as the watch item, not changed (confidence: high)
ASSUMED: the scratch venv's mypy is 2.4.0 (pins.env pins 2.3.1 for the image lane); the host lane is advisory (confidence: high)
ABSENT: nothing image-level is reported as passed: the Docker lane (make test, make scan) has not run
ABSENT: T018 not started — held for the mentor's answer to Item 13
Verification: quality score of record `unknown` (every component excluded; no component filled by hand); project figures beside it in .specswarm/metrics.json `004`: Python 744/747 (2 load flakes, then 24/24 ×3), coverage 97% (adele client 97%); Go 6 packages ok, 95.8% total; ruff, mypy, shellcheck (34 files), gofmt, go vet, staticcheck, govulncheck clean; host integration cycle passes at a135f91
SCOPE: in (1 changed files)

### T018: the exit-4 grant envelope (FOR-MENTOR Item 13's ruling, discovery revision 10; send 12-rev2-20261002-055142)
**Started:** 2026-10-02T06:37:00+00:00 | **Completed:** 2026-10-02T06:55:00+00:00

INHERITED: the ruling, verbatim in `../bridge/feedback/12-20261002-054636-grant-envelope.md` § Resolution: option (b), a sibling `grant-envelope.schema.json` told apart by `status`; the confirm envelope's `grant` field removed if no tool sets it; `mutating: false` confirmed, rule 8 kept (confidence: high)
INHERITED: governance audited to revision 10 on master (`cb943d3`), merged here (`3f3c520`); quality-standards' Output contract gate names the check this task builds (confidence: high)
FLAGGED: the confirm envelope's `grant` field is removed: no caller sets it. `grep -rn 'confirm_required\|grant=' tools tests bench scan image` at `3f3c520` finds one call, `tests/unit/test_agentio.py:244`, without `grant`; `adele`'s `"grant"` keys are its request body and its 200 data, not the confirm envelope. `confirm_required()` loses the parameter, and a unit shows a caller passing it now fails (confidence: high)
FLAGGED: found while testing, a 001 defect: agentio printed every envelope through `_clean_data`, which SORTS keys, so the confirm envelope's first keys were `confirm, plan, scope` — never rule 12's `tool, target, scope` (shown on the pre-change tree). Fixed in the envelope path only: the envelope keeps its own key order, values still cleaned. A unit pins the order for both envelopes. Declared under changed_other_features (confidence: high)
FLAGGED: conform gains **C9 envelopes**: every exit 4 it observes must be one envelope of a status the manifest declares (new manifest key `envelopes`, emitted by agentio for every tool), with that status's keys and rule 12's first keys; a grant envelope has limit {name, allowed, needed}, `extend_by: operator`, `performed: false`, and no `confirm`; no `confirm` may name a command outside the tool (first word; no `;` `&&` `|` … chaining, split with shlex punctuation_chars). C2 checks `envelopes` lists confirmation_required exactly when mutating (confidence: high)
FLAGGED: the negative rule is seen failing (cross-stack P005): 11 new violation cases in `tests/unit/test_conform_violations.py`, and a mutation run that disabled C9's `confirm` rule failed 4 tests (env_confirm_chained, env_confirm_other_command, env_grant_with_confirm, and adele's own C9 test) before the file was restored byte-for-byte (confidence: high)
FLAGGED: conform cannot PROVOKE a grant envelope: its probes are read-only and a refusal needs a grant to exceed and writes Adele's ledger. So C9 judges any exit 4 it observes, and adele's envelope is judged by `tests/unit/test_adele_cli.py` (against the schema and conform's own `check_envelope`) and by SC-3's e2e cells in the image. Written into conformance.md's "Not checked here" table (confidence: medium)
FLAGGED: the interim stderr line is dropped, not kept: stdout is exactly the envelope and stderr is empty, in --text and --json; the e2e takes the extend command from the envelope's `extend` (confidence: high)
FLAGGED: a 403 that cannot fill the envelope (no grant, limit or extend, or `performed` not false) is exit 1 with a structured error, never a guessed envelope (H3) (confidence: high)
FLAGGED: agentio refuses to print an envelope its tool does not declare (a confirm envelope from a non-mutating tool, a grant envelope without `Tool(grant_envelope=True)`, any envelope on an exit other than 4): an internal error, exit 1 — the same guard style as revision 9's pass-through (confidence: high)
FLAGGED: rule 8: slice 0's client exposes no destructive request, so it has no `--dry-run`; said in its docstring and adele-cli.md (confidence: high)
FLAGGED: SC-3's envelope cells use the roomy `e2e` grant (port 22, not extended), so no other cell's grant or count moves; adding a grant would have broken the malformed-grant test's "10 grants" (confidence: high)
ASSUMED: the e2e validates with `tests/unit/schema.py` exec'd inside a throwaway of the agent image's interpreter (pyq), fed the schema file from the read-only repository; dry-run on the host with stubbed `run`/`pyq`, it passes a good envelope and fails a wrong limit, a `confirm`, and `performed: 0` (confidence: medium)
FLAGGED: fixed while testing, `tests/unit/schema.py`'s `const` treated 0 as false (Python's False == 0); a schema's false now requires a boolean (confidence: high)
ABSENT: not run in the image (no Docker): SC-3's envelope cells and the changed refusal cells wait for the mentor's lane
ABSENT: host integration against the real Go binaries not re-run: the Go code is unchanged since a135f91's passing cycle, and the client reads the same 403 fields as before (grant, limit, extend) plus performed and ledger_id
Verification: host lane — Python 775 passed, 1 skipped (traced; coverage 97%: agentio 95%, timelike-conform 92%, adele 97%, run 96%, timelike 96%, bench 98%, scan 99%); ruff, ruff format, mypy (16 files) and shellcheck clean; the C9 mutation run failed 4 tests as it should, then the file was restored (cmp); e2e not run (no Docker)
SCOPE: out (15 changed files outside the feature's artifacts; 5 out: tests/e2e/conformance-check-over-every-timelike-tool-on-path.bats, tests/unit/schema.py, tests/unit/test_agentio.py, tests/unit/test_conform_violations.py, tools/agentio/agentio.py) — FLAGGED yes: all five are 001 files the send directs under "What this cycle builds" (agentio, its units, the conformance check's units, the schema subset, one comment), declared under changed_other_features; tasks.md was not widened to make the check pass

### Lane fix 1 (Cycle 2): SC-4's setup cell checked the pre-T018 refusal marker
**Started:** 2026-10-02T13:50:00+00:00 | **Completed:** 2026-10-02T13:52:00+00:00

INHERITED: the mentor's lane on `66adbae` (`../bridge/history.md` 07:47:50Z): 238/239, the one failure `SC-4 004 the full request cycle ran`, which grepped the cycle's output for `(code 4)` — the interim stderr line's code, which T018 removed (confidence: high)
FLAGGED: the cell now greps for `"status": "grant_required"`, the bytes agentio's `json.dumps` prints (checked: `grep -cF` = 1 on its output). The cycle's refusals are `--text` requests, which print the envelope as JSON (confidence: high)
FLAGGED: T018 missed this marker: its sweep for interim forms searched for `interim`, `Item 13`, `stdout_bytes` and `operator extends it`, not for `(code 4)`. A sweep for `code 4`, `stdout_bytes` and `operator extends it` over tests/, scripts/ and tools/ now finds no other e2e use (confidence: high)
ABSENT: not run in the image (no Docker); shellcheck clean
SCOPE: in (1 changed files)
