# Implementation Plan: 004 Adele & grants (prompt 12, slice 0)

**Branch:** `004-adele-grants` (from `master` at `8846d77`, which is ≥ `3d891ae` as the send requires)
· **Spec:** `spec.md` · **Send:** `../bridge/sends/12-rev2-20261002-042951.md` (prompt revision 2,
discovery revision 9) · **specswarm:** 4.0.1-botbaubble.2.24.0

## Summary

Adele is a new Go service in her own container. She is static, `FROM scratch`, with SQLite through
`modernc.org/sqlite`. She reads the operator's grant file at start and serves a JSON request interface
on an internal network that only the agent and she share. She brokers one capability, the stand-in's
`standin.box`, using a canary credential the agent never sees. She refuses over-grant requests before
anything is performed, and records every outcome in an append-only ledger with an undo.

The agent side is a new agentio tool, `tools/bin/adele`.

The lane gains:
- Adele's image and her stamp check
- the stand-in, under compose profile `standin`
- a `go test` step
- Adele in the scan gate, with a `govulncheck` step

One piece is held: the client's exit-4 envelope, which waits for FOR-MENTOR Item 13 (research R7).

## Technical Context

| Item | Value |
|---|---|
| Languages | Go 1.27.1 (`adele/`, Adele and the stand-in); Python 3.14.x for the `adele` client (agentio, `-I`, stdlib) |
| Dependencies | Go: stdlib + `modernc.org/sqlite` v1.60.1 (tech-stack approved). Python: stdlib (`urllib.request`, `json`) |
| Storage | SQLite at `/var/lib/adele/adele.db` (volume `adele-state`, Adele only); the stand-in's JSON record in volume `standin-state` |
| Transport | HTTP/1.1 JSON on compose networks `adele-request` (agent ↔ Adele) and `adele-standin` (Adele ↔ stand-in), both `internal: true` |
| Testing | `go test -cover` (units, including the real stand-in handler in-process); pytest (`tests/unit/test_adele_cli.py`); bats e2e, one file per criterion, `bash -c` and `bash -lc` |
| Lint and types | gofmt, go vet, staticcheck (pinned, in `GO_IMAGE`); ruff, `mypy --strict`; shellcheck (new bats files are added to `SHELLCHECK_FILES`) |
| Performance | The client's start-up stays under 100 ms p95 (urllib is imported lazily, R6). A request's round trip is bounded by the client's 30 s limit; Adele's servers have read and write timeouts |
| Unknowns | none, except the envelope shape (Item 13; R7) |

## Constitution Check

| Principle | Check | Result |
|---|---|---|
| P1 Unaided completion | Inside the grant, the agent acts freely. Beyond it, exit 4 names the grant, the limit and the operator's exact command (T1). Unreachable Adele names who unblocks it | ✅ (the envelope's shape is pending Item 13) |
| P2 Every call concludes | Client limit 30 s → 124; `status` 3 s; server timeouts; `up --wait` with a healthcheck | ✅ |
| P3 Found where agents look | `adele <verb>` in the `<service> <verb>` habit; listed by `timelike`; conform-checked | ✅ |
| P4 Reach only by grant | This is the P4 feature: an authority in her own container, a credential never in the agent, the grant file and the extend command out of the agent's reach, refusal before performing | ✅ |
| P5 Recoverable | An undo is recorded on every performed row (FR-15) | ✅ |
| P6 Claims measured | No claim of value is made | n/a |
| P7 Harness-agnostic | A plain shell command; no MCP | ✅ |
| T1 | P4 wins; P1 is met by the escalation | ✅ |
| H1 | Adele is the only reaching component. Nothing of hers is mounted into the agent, which is tested (SC-4, isolation file) | ✅ |
| H2 | `adele` emits through agentio. The exit-4 shape is held (Item 13) | ⚠ pending |
| H3 | "performed" is checked against the stand-in's own record; `status` names its vantage point | ✅ |
| H4 | The client is non-interactive; tested under `bash -c` and `bash -lc` | ✅ |
| H5 | `-I` shebang, single file, stdlib. Go static, `CGO_ENABLED=0`; the one third-party module is the approved driver | ✅ |
| H6 | No daemon inside a tool; Adele is a separate service, as the stack intends | ✅ |
| H7 | One test file per criterion, named after its text; D8 Manual | ✅ |
| H8 | Adele stamped (label + `-ldflags -X`); the lane refuses a stale image; go vet + staticcheck | ✅ |
| H9 | Adele's image scanned (Syft/Grype + govulncheck); scratch final stage | ✅ |

**Post-design re-check:** unchanged. The one ⚠ is the declared Item 13 hold. It is not a violation,
because the send itself prescribes raising it.

**Observation, not acted on:** quality-standards sets `require_changelog_entry: true`, and this
repository has no `CHANGELOG.md`. Features 001–003 shipped without one. code/ notes it for the mentor and
does not create one in this cycle (scope).

## Project Structure

### Documentation (this feature)
```
.specswarm/features/004-adele-grants/
  spec.md  plan.md  research.md  data-model.md  quickstart.md  tasks.md (next)
  contracts/adele-http.md  contracts/adele-cli.md
  checklists/requirements.md
```

### Source code
```
adele/                       Go module timelike/adele (new)
  go.mod go.sum Dockerfile   two final stages: adele, standin
  cmd/adeled/                serve · check · extend · ledger · version · health
  cmd/adele-standin/         serve · list
  internal/grants/           parser (line-numbered errors), effective grant
  internal/ledger/           SQLite schema, append, extensions
  internal/broker/           check order, quote, perform, refuse (+ the extend command text)
  internal/standin/          handler, record, pricing
  grants.example.conf        committed; grants.conf and canary are git-ignored
tools/bin/adele              the client (new)
compose.yaml                 adele, adele-standin (profile), networks, volumes, secret
pins.env                     GO_IMAGE, STATICCHECK_VERSION, GOVULNCHECK_VERSION
Makefile                     canary, grants, up/down with the profile, Go lint
tests/run.sh                 up --profile standin --wait; gounit step; containers left running
tests/e2e/helpers.bash       ADELE_CONTAINER, stamp_check_adele, adeled/standin wrappers, start_adele_with
tests/e2e/*.bats             six new files (research R4)
tests/unit/test_adele_cli.py client units against an in-process fake HTTP server (stdlib http.server)
scan/scan.sh, scan/evaluate.py   Adele required; per-image base digest; govulncheck step
.gitignore                   adele/grants.conf (the canary lives in a Docker volume, spec D-8)
```

## Phase 0: Research
`research.md`, R1–R8. All unknowns are resolved, except the envelope (Item 13).

## Phase 1: Design
`data-model.md` (grant grammar, check order, ledger, stand-in record, canary), `contracts/adele-http.md`
and `contracts/adele-cli.md`, and `quickstart.md`.

## Phase 2: Task approach (for /specswarm:tasks)
1. **Setup:** pins, the module skeleton, `.gitignore`, the Makefile's canary and grants targets.
2. **Go core, test-first, parallelisable by package:**
   - grants parser (each malformation with its line)
   - ledger
   - stand-in (refuses without the canary; pricing; record)
   - broker (check order; refusal body with the extend command; perform through the real stand-in
     handler)
   - `adeled` commands
3. **Images and compose:** `adele/Dockerfile`, compose services, networks, volumes, the secret, the
   healthcheck.
4. **The client** `tools/bin/adele` (status, grants, request: performed, and the interim exit 4) with
   pytest units.
5. **The lane:** run.sh (`up` profile, gounit), helpers, stamp check.
6. **e2e:** SC-1, SC-2, SC-4, SC-5, the isolation file, and SC-3's within-grant and nothing-performed
   cells. The envelope cells are written held, then enabled after Item 13.
7. **The scan gate:** Adele required, base digest, govulncheck parsing, units.
8. **Lint wiring** (Go lint in the Makefile, shellcheck list), README (Adele, the grant file, the extend
   command), the cycle report.
9. **Held (Item 13):** the envelope schema or contract edit, `agentio`'s envelope helper, the client's
   exit-4 emission, and the envelope e2e cells.

**Delegation:** independent Go packages (grants, ledger, stand-in) and the scan-gate change go to
subagents, each with its own files. The broker, `adeled`, compose, the client and the e2e suite are done
by this instance. It reviews every delegate's work and commits it, one task per commit.

## Verification lanes (001 R10)

| Lane | Where | What it proves |
|---|---|---|
| Host (advisory) | this container: scratch Go 1.27.1 toolchain, scratch venv | `go test -cover`, gofmt, go vet, staticcheck, govulncheck; pytest units; ruff, mypy, shellcheck |
| Docker (authoritative) | the mentor's host: `make test`, `make scan` | images, compose, networks, every e2e criterion, the image-level no-leak scan, the scan gate |

Nothing image-level is reported as passed from the host lane.

## Complexity Tracking

| Item | Bends | Justification |
|---|---|---|
| Go coverage of the stand-in counts toward Adele's 90% | the quality-standards intent that provider paths are covered against real services | the stand-in **is** the real counterpart in slice 0. Real providers (13, 14) bring their own integration tests |

## Tech Stack Compliance Report
<!-- Auto-generated by SpecSwarm tech stack validation -->

### ✅ Approved Technologies (already in stack)
Go (Adele only, `CGO_ENABLED=0`), `net/http`, SQLite, `modernc.org/sqlite`, Docker Compose v2, FROM
scratch, go test, go vet, gofmt, staticcheck, govulncheck, Syft + Grype, pytest, ruff, mypy, shellcheck,
bats. Python's `urllib.request` is stdlib, covered by "stdlib only" (as `ctypes` was at 003).

### ➕ New Technologies (auto-added)
None. `tech-stack.md` is unchanged, so `Version: not bumped — nothing added`. The new pins (`GO_IMAGE`,
`STATICCHECK_VERSION`, `GOVULNCHECK_VERSION`) are versions of approved tools, recorded in `pins.env`.

### ⚠️ Conflicting Technologies (require approval)
None.

### ❌ Prohibited Technologies (cannot use)
None used. `mattn/go-sqlite3` and cgo are avoided by construction (`CGO_ENABLED=0`).

---

## Cycle 3 — slice 1 (send `bridge/sends/12-rev2-20261016-091249.md`; spec § Slice 1)

### Technical context (slice 1)
- **Adele (Go, stdlib + `modernc.org/sqlite`, unchanged):** a new package `adele/internal/reaper` (the pass, its
  bounds, its outcome from the read-back); `ledger` to schema 2; the stand-in client gains `List` and `Delete`;
  `adeled` gains `reap` and `status`, and runs the reaper in `serve`. No new dependency.
- **Agent side (Python stdlib on agentio):** `adele` sends `agent`, and `status [HOST]` reads `/v1/denials`;
  agentio prints rule 14's line for exit 4 in text mode and refuses `mutating` + `grant_envelope`; the journal
  reads `agent`.
- **Compose:** unchanged. The reaper's settings have defaults in Go, so nothing is interpolated (lore
  docker-compose Q001/Q002/Q005 do not arise).
- **Tests:** Go units (fake upstream with every failure; a v1 ledger file migrated); pytest; bats, one file per
  criterion: the reap file spread (no budget asserted), the restart/unreachable file `serial` (it stops Adele and
  the stand-in, state neighbours read).

### Constitution check (slice 1)
- **P2:** every reap ends as a recorded outcome with a named cause; the bounded retries and the given-up row with
  the operator's command are what make "never silently dropped" true.
- **P4 / H1:** the reaper and its record are Adele's alone; the agent gains one read-only endpoint
  (`/v1/denials`) and no write.
- **P5:** each reap row points at the performed row it undoes (`ref`).
- **P003 / P004 / P005 (cross-stack):** `status` names Adele's revision; outcomes from the stand-in's record read
  back; failure paths tested against the stand-in made to fail, and `not_verified` says no real provider was
  reaped.
- **H8:** the stamp checks are unchanged; the reaper is in the stamped binary.

### Task approach
Phase A, Go: ledger schema 2 and migration → stand-in client List/Delete and stand-in faults → reaper → `adeled`
serve/reap/status, `/v1/denials`. Phase B, Python: agentio's line and guard (with the e2e grep), the client's
`agent` and `status`, the journal. Phase C, e2e and lane.conf. Phase D: README, the regenerated reference,
the host lane, the cycle report. The denial message's source waits on Item 26.

### Tech Stack Compliance Report (Cycle 3)
<!-- Auto-generated by SpecSwarm tech stack validation -->
- ✅ **Approved:** Go, SQLite, `modernc.org/sqlite`, Python (stdlib), bats, pytest — classified by
  `lib/tech-stack-parser.sh` (all `approved`, none prohibited, no unparsed prohibition reported).
- ➕ **New:** none. `Version: not bumped — nothing added`.
- ⚠️ **Conflicting:** none.
- ❌ **Prohibited:** none.

---

## Cycle 4 — re-send at prompt revision 16 (send `bridge/sends/12-rev16-20261016-102708.md`)

A delta, as the send asks; Cycle 3's plan stands. SC-8's cells exist (Cycle 3's status file, renamed after the new
criterion); the governance audit runs through `/specswarm:constitution`'s *Governance provenance*; the README block
applies. No new technology: `Version: not bumped — nothing added`.
