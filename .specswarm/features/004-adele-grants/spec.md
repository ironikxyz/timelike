---
parent_branch: master
feature_number: "004"
status: In Progress
created_at: 2026-10-02T04:55:00+00:00
source_prompt: plan/.discover/prompts/12-adele-grants.md
source_send: bridge/sends/12-rev2-20261002-042951.md
prompt_revision: 2
discovery_revision: 9
audited_against: [2, 16]
slice: 0
---

# Feature: Adele & grants (prompt 12, slice 0: skeletal)

## Overview

Adele is the one authority, outside the agent's privilege, that stands between the agent and anything
beyond its environment (P4). She holds every credential, checks every reaching request against a grant
the operator wrote, performs what the grant allows, refuses what it does not with an escalation the
operator can act on (T1), and records everything in a ledger (P5).

Slice 0 is the thinnest end-to-end path:
- Adele runs as her own container, composed with the agent image.
- She reads the operator's grant file at start.
- She brokers **one** capability: a **stand-in** that lives inside the compose project and is plainly
  not a provider. It authenticates with a synthetic **canary** credential, never a real one. This is the
  operator's decision, delegated to the mentor on 2026-10-02.
- She refuses a request beyond its grant with exit 4 and an envelope naming the grant, the exceeded
  limit and the operator's exact extend command.
- She records each performed request, with what undoes it.

The agent never holds, sees or can read the credential.

Not in slice 0:
- reaping expired resources and plain network denials (slice 1)
- the egress allowlist and hostile content (slice 2)
- any real provider: the Docker socket comes at 13, fly.io at 14

Slice 0 records each resource's real expiry, because slice 1 reaps by it.

**Feature numbering.** This directory is `004`, the next number in this repository's own sequence. It
is built from prompt **12**. Directory and prompt numbers are independent; `source_prompt` above is the
pairing.

## User Scenarios

### Scenario 1: a request within its grant (Agent)
1. The operator's grant `demo` allows the stand-in capability, with a budget, a resource lifetime, an
   instance ceiling and a set of ports.
2. The agent runs the client from bash, asking for one stand-in resource within those limits.
3. Adele checks the request against `demo`, asks the stand-in for a price, and checks the budget. She
   then creates the resource **with the canary**, which the agent never sees.
4. The agent receives the result: the resource's name, its estimated cost and its expiry. The client
   exits 0.
5. The ledger holds one row for the request: the grant, the session, the resource, the cost, the
   expiry, and how to undo it.

### Scenario 2: a request beyond its grant, then extended (Agent, then Operator) — D8
1. The agent asks for something the grant does not allow, for example a resource whose estimated cost
   would exceed the remaining budget.
2. The client exits **4**. stdout carries an envelope naming the grant (`demo`), the limit exceeded
   (`budget`, with allowed and requested values) and the operator's exact command to extend it.
3. Nothing is performed. The stand-in's own record shows no new resource.
4. The agent cannot run the extend command. It is the operator's, and the agent has no route to it.
5. The operator runs the printed command on the host. The extension is recorded in the ledger.
6. The agent retries the same request, and it proceeds as in Scenario 1.

### Scenario 3: a malformed grant file (Operator)
1. The operator writes a grant with a typo (an unknown key, a bad duration, a negative budget).
2. Adele refuses to start. Her container exits non-zero, and her log names the grant file, the line
   number at fault, and what is wrong with it.

### Scenario 4: the agent tries to reach around Adele (Agent, Hostile content)
1. The agent tries to reach the stand-in directly, to read Adele's grant file, ledger or credential, or
   to find the canary anywhere it can look.
2. All of it fails. The stand-in is not on any network the agent is on. Adele's state is in her own
   container. The canary appears nowhere in the agent's environment, filesystem, process arguments or
   tool output.

## Functional Requirements

### Composition and the request interface
- **FR-1** The agent image and Adele start together from one compose file (`compose.yaml`). Nothing is
  installed on the host.
- **FR-2** The agent reaches Adele **only** through her request interface: HTTP on a compose network
  that is internal (no outside route) and joined only by the agent and Adele.
- **FR-3** The stand-in sits on a second internal network, joined only by Adele and the stand-in. The
  agent is not on it, so it cannot resolve or connect to the stand-in.
- **FR-4** Adele's state (her ledger database) lives in a volume mounted only into her container. Her
  configuration (the grant file, read-only) and the canary (a read-only volume, D-8) are also mounted only
  into her container, and the canary into the stand-in's. Nothing is mounted into the agent's container
  (constitution H1; stack rule 1).

### Grants
- **FR-5** A grant file defines one or more named grants. Each grant states:
  - **capabilities**: what may be requested (slice 0 knows one, the stand-in's `standin.box`)
  - **budget**: an amount of money, in USD to the cent
  - **ttl**: the longest lifetime any resource created under the grant may have
  - **instances**: the most resources under the grant that may be live at once
  - **ports**: the ports a resource may expose, as single ports or ranges
- **FR-6** Adele parses the grant file at start. A malformed file stops her: she exits non-zero, naming
  the file, the **line number** at fault and what is wrong. Malformed means a syntax error, an unknown
  key, a missing required key, an unparsable value, a duplicate grant or key, or an unknown capability.
  She never starts on a partially valid file.
- **FR-7** Nothing the agent can do changes a grant (P4; feature 01). The agent cannot write or read the
  grant file, and cannot run the extend command.

### Requests
- **FR-8** The agent-side client, **`adele`**, sends a request naming the capability, the action and its
  parameters. It may name the grant, optionally. It sends the agentio session id, and it follows 001's
  output contract (`timelike-conform` checks it).
- **FR-9** Adele chooses the grant: the one named, else the single grant allowing the capability. If
  several allow it, she asks the agent to name one, with a usage error listing them.
- **FR-10** A request within its grant is performed with the credential the agent never sees. The
  client returns the result and exits 0.
- **FR-11** A request that exceeds **any** limit is refused **before anything is performed**. The limits
  are: a capability not granted, the budget, the ttl, the instance ceiling, and a port outside the
  grant. A named grant that does not exist is not a refusal but exit 3 (not found), listing the grants
  that exist. The client exits **4**, and stdout carries the envelope (FR-12). The stand-in's
  own record shows nothing was created (cross-stack P004).
- **FR-12** The exit-4 envelope names:
  - the grant
  - the exceeded limit: its name, its allowed value, and what the request needed
  - the operator's exact extend command, which the operator can run unchanged to make this request
    allowed
  - that nothing was performed

  **Its shape is the grant envelope** (`grant-envelope.schema.json` in 001's `contracts/`), told apart
  from the confirmation envelope by `status: grant_required`. The extend command is in `extend`, with
  `extend_by: "operator"`, and never in `confirm`. *(Recorded in place in Cycle 2, 2026-10-02: FOR-MENTOR
  Item 13's ruling, discovery revision 10. It fills in what this requirement left open; no criterion
  changed.)* See D-5.
- **FR-13** If Adele cannot be reached, or the stand-in fails, the client exits 1. Its error names what
  failed, and who can unblock it: the operator, by starting the compose project (P1, P2). The client
  never hangs. It has a time limit, and exit 124 is its own limit firing.

### Ledger
- **FR-14** Every performed request is recorded in the ledger with:
  - the grant
  - the requesting session
  - the resource created
  - the estimated cost
  - the expiry, as an absolute time: the creation time plus the requested or granted ttl
- **FR-15** Every ledger row of a performed request records what undoes it: the stand-in action that
  deletes the named resource (P5). Slice 1's reaper uses it.
- **FR-16** Refused requests and operator extensions are recorded too, each with its outcome, so the
  ledger is the whole account.
- **FR-17** The operator reads the ledger with one command, `docker exec timelike-adele adeled ledger`.
  The agent cannot read it.

### Credential isolation
- **FR-18** No credential Adele holds appears in any of these, checked by a scan after a full request
  cycle (performed, refused, extended, retried):
  - the agent's environment (every process it can read)
  - its filesystem (everything it can read)
  - its process arguments
  - any tool output, the client's JSON and text included, and its session event log

### The stand-in (test and demo only)
- **FR-19** It is named so that no operator can mistake it for a provider: `adele-standin`, and its
  capability is `standin.box`. It runs only under the compose profile `standin`, so it is never part of
  `docker compose up` without that profile. It is not in the agent image.
- **FR-20** It refuses every request that does not carry the canary credential. This is tested directly
  against the stand-in, not through Adele.
- **FR-21** It prices a box at a fixed rate per hour, so an estimate is the rate times the lifetime. It
  creates a box under a name, and keeps its own record of the boxes it holds. Tests read that record to
  verify "performed" and "not performed".
- **FR-22** It deletes a box by name. That is the undo FR-15 records.

### Build revision
- **FR-23** Adele's image carries the build revision (`GIT_SHA`) it was built from, and Adele reports it.
  The lane refuses a stale or unstamped Adele image, as it does the agent's (constitution H8; cross-stack
  P003; lore docker-compose Q004).

## Success Criteria

Each slice-0 criterion of the send, with the distinguishing text used to cite it.

| SC | Criterion (send, slice 0) | How it is shown |
|---|---|---|
| SC-1 | "The agent image and Adele start together from one compose file, and the agent reaches Adele only through its request interface" | e2e: one `compose up`. From the agent, Adele's interface answers, and the stand-in neither resolves nor connects |
| SC-2 | "Adele rejects a malformed grant at start with the line at fault" | e2e: Adele started on each of several malformed files exits non-zero, naming file:line. A valid file starts. Go units cover each malformation |
| SC-3 | "a request exceeding any limit exits 4 with an envelope naming the grant, the limit and the operator's extend command, and nothing is performed" | e2e: a request within the grant exits 0 and the stand-in's record holds the box. One refusal per limit exits 4 with the envelope, and the stand-in's record is unchanged. The extend command, run as printed, lets the retry proceed |
| SC-4 | "No credential held by Adele appears in the agent's environment, filesystem, process arguments or any tool output, checked by a scan after a full request cycle" | e2e: after a full cycle, a search for the canary's exact bytes through the agent's real paths (`bash -c`, `bash -lc`, `/proc/*/environ`, `/proc/*/cmdline`, the readable filesystem, the client's JSON and text output, the event log) finds nothing. Control: the same search finds the canary in Adele's container |
| SC-5 | "Every performed request is recorded in the ledger with grant, requesting session, resource created, estimated cost and expiry" | e2e: the ledger row for a performed request carries all five, matching the request, the stand-in's record and the session that asked; the expiry equals creation plus ttl, and the undo is present |
| SC-6 (Manual, D8) | "the Agent's reaching request beyond its grant exits 4 naming the grant, and the Operator extends the grant so the retried request proceeds" | Observed by the mentor with the operator after the Docker lane. `unconfirmed` until then |

Also required (not criteria of their own):
- The stand-in refuses a request without the canary (FR-20).
- `timelike-conform` passes on the new client.
- `make scan` covers Adele's image, with `govulncheck` over her Go code.
- The agent cannot write or read the grant file, and cannot run the extend command (FR-7).

## Key Entities

- **Grant**: a name, the capabilities, a budget (USD, cents), a ttl, an instance ceiling, and the
  allowed ports. Defined in the grant file. An operator's extensions are layered on it and recorded in
  the ledger.
- **Grant file**: the operator's text file, read-only to Adele, mounted only into her container.
- **Request**: from the agent, through the client. It has a session, an optional grant, a capability,
  an action and parameters (a box name, a lifetime, ports).
- **Envelope**: the exit-4 refusal. It has the grant, the exceeded limit (its name, allowed, needed),
  the extend command, `extend_by: "operator"`, `performed: false` and the refused request. It is the
  grant envelope (D-5, discovery revision 10).
- **Ledger row**: a timestamp, an outcome (`performed`, `refused` or `extended`), the grant, the session,
  the capability and action, the resource, the estimated cost, the expiry, the undo, and the limit (on
  a refusal).
- **Canary**: a generated value, unique per environment, that is never a real secret. Adele and the
  stand-in hold it; the agent never does.
- **Box**: the stand-in's resource. It has a name, a lifetime, ports, a cost, and a creation time.

## Decisions (the points the send left open, decided here on purpose)

**D-1 · The client is named `adele`** (P3).
- An agent's trained habit for an outside authority is `<service> <verb>`: `gh pr create`,
  `fly deploy`, `docker run`. The service here is Adele, so `adele request …` and `adele grants` read as
  that habit.
- It shadows no existing command: Debian ships no `adele`, and none is on the agent's PATH.
- The envelope, the ledger and the operator's command all name Adele, so the agent and the operator
  read one name.
- Adele's own binary, in her container, is `adeled`, the daemon convention. It also carries the
  operator's subcommands (`extend`, `ledger`, `check`).

**D-2 · Transport: HTTP on internal compose networks, not a unix socket on a shared volume.**
- A shared volume would put something of Adele's into the agent's container. Stack rule 1 forbids
  that, and lore Q003/Q006 (uid alignment, setgid and ACLs) would apply.
- A network keeps "nothing mounted into the agent" literally true. Two `internal: true` networks:
  - `adele-request`: the agent and Adele
  - `adele-standin`: Adele and the stand-in
- **What it leaves open:** the agent keeps compose's default network, with egress, as today. Slice 2
  builds the allowlist. Adele herself has **no** outside route in slice 0: she is on internal networks
  only, and needs none until 13 and 14.
- **This changes the agent container's networks**: it gains `adele-request`. That is a fact for the
  credential-class CVE review below.

**D-3 · The grant file: an operator's file, bind-mounted read-only into Adele only.**
- Default host path `./adele/grants.conf`. It is git-ignored, and a committed `adele/grants.example.conf`
  documents the format. It is overridable with `ADELE_GRANTS` for tests and other setups.
- Line-based, `[grant NAME]` sections with `key = value` lines and `#` comments. This makes "the line at
  fault" exact, and needs no dependency (stdlib only; tech-stack). TOML would need a third-party parser.
- The agent's container has no mount of it, and the agent cannot reach the host. Tests show that
  directly.

**D-4 · The operator's extend command: `docker exec timelike-adele adeled extend <grant> <limit> <value>`.**
- It sets the limit to the value. The envelope prints the value that makes **this** request allowed.
- It uses `docker exec` with the fixed container name, rather than `docker compose exec`. That makes it
  exact from any directory and needs nothing installed on the host.
- The extension is stored in Adele's database, layered over the grant file, and recorded in the ledger.
  Restarting Adele keeps it. Editing the file replaces the base values and keeps the extensions.
- The agent cannot run it: it has no Docker socket (H1).

**D-5 · The exit-4 envelope: raised, not settled.** 001's contract (`output-contract.md:33`) makes
exit 4 carry `confirm-envelope.schema.json`. As written, that schema cannot hold this envelope:
- `status` is the constant `confirmation_required`
- `confirm` is required, and is the agent's own command plus `--yes`
- there is no field for the exceeded limit
- `plan` and `target` are required, with no stated meaning for a refused grant

Writing the operator's command into `confirm` would make it say something false. Every honest shape
changes 001's schema or contract. So this is **FOR-MENTOR Item 13**, with options and a recommendation.
The envelope's emission (the client's exit-4 path) is built only after the answer. Everything else in
this slice is built first.

A refused grant is the client's **own** outcome (discovery revision 9, rule 5): exit 4 is in its
vocabulary, and the client passes no exit through.

**D-5, settled (recorded in place in Cycle 2, 2026-10-02).** Plan ruled on Item 13 as **discovery
revision 10**, a clarification (`../bridge/feedback/12-20261002-054636-grant-envelope.md` § Resolution):
- **Option (b):** exit 4 carries one of two envelopes, told apart by `status`. This client prints the
  sibling **grant envelope**, `grant-envelope.schema.json`: `tool`, `target`, `scope` first (rule 12),
  then `status: "grant_required"`, `grant`, `limit {name, allowed, needed}`, `extend`,
  `extend_by: "operator"`, `performed: false` and the refused `request` (plus Adele's `ledger_id`).
- An operator's command never appears in `confirm`, or in any field the agent's habit runs.
- The confirm envelope's optional `grant` field is **removed**: no tool set it (confirmed in Cycle 2).
- `mutating: false` is confirmed: the grant is the confirmation (P4). Rule 8 still binds; slice 0
  exposes no destructive request, so the client has no `--dry-run` yet.

Built in T018, which changes 001's contract files (declared in the cycle report).

**D-6 · 001's placeholder `adele` identity stays in the agent image, unchanged.**
- 001's test `agent-cannot-run-as-root-change-firewall-or-read-adele.bats` reads `/var/lib/adele` as a
  negative fixture for file permissions inside the agent's own filesystem. That is still a true and
  useful check.
- Removing the fixture would change a merged feature's test for no gain in slice 0.
- The real checks (no Adele mount, no route to her state, no canary anywhere) are new tests in this
  feature.
- Adele's container runs as the same uid, 10001, so "adele" means one identity across both.
- No 001 file changes for this.

**D-7 · Undo.** Each performed `standin.box create` records the undo `standin.box delete name=<box>`.
Adele can perform it with the canary, and the slice 1 reaper will.

**D-8 · The canary.**
- Generated per environment, as `tlcanary-` followed by 32 random hex characters.
- *(Revised in implement, T010, FLAGGED.)* A one-shot compose service (`adele-secret`, on the pinned
  Debian image, with no network) writes it, if absent, into the named volume `adele-secret`, owned
  `root:10001` and mode 0440.
- Adele and the stand-in, both uid and gid 10001, mount that volume read-only. Each reads the canary
  by group and cannot replace it, which is lore Q007's preferred form: root-owned, readable, not
  writable.
- The canary never touches the host's disk.
- **Why not a host file mounted as a compose secret, as first planned:** the file would be owned by
  the operator's uid at 0600, and compose's file secrets are bind mounts. Adele (10001) could not read
  it without `setfacl` or `chown` on the host, and nothing is installed on the host.
- Tests read the exact bytes through the volume, from a throwaway container. So the search for the
  canary is still for its exact bytes.

**D-9 · Sessions are self-declared** in slice 0. The client sends agentio's session id, and Adele records
it. Authenticating sessions would need a credential inside the agent's container, which P4 forbids.
Several agents in one container share one boundary, so the session is attribution, not authority.

## What the stand-in proves, and what it cannot (cross-stack P005)

**It proves:**
- the grant path: parse, choose, check, perform or refuse, record
- that a credential the agent never sees is what authorises the action, because the stand-in refuses
  without it
- the isolation of that credential from every path the agent has

**It cannot prove** anything about a real provider:
- its authentication
- its pricing
- its latency
- its failures
- its own idea of TTL or spend

Those are 13's and 14's to test, against the real Docker Engine API and fly.io.

## Supply chain

- Adele's image is `FROM scratch`, with a static Go binary (`CGO_ENABLED=0`; SQLite through
  `modernc.org/sqlite`, never `mattn/go-sqlite3`).
- The Go toolchain image and the base are pinned in `pins.env`.
- `make scan` scans Adele's image, and `govulncheck` covers her code.
- The stand-in is test-only and not shipped, so it is out of the scan gate. Its image is built from the
  same module.

**Credential-class CVEs: facts for the operator's review before merge.** These are CVE-2026-11856,
-19931 and -8926 (libcurl), accepted on the premise that the agent holds no credentials. The facts will
be reported, and those baseline entries are not edited:
1. whether any credential reaches the agent's container (SC-4 is the evidence)
2. that the agent's networks changed (D-2)
3. whether the agent's libcurl is in the path to Adele: the client is Python stdlib HTTP, not curl
4. the scan's current entries for the three IDs

## Assumptions

- Money is USD only in slice 0. The stand-in's rate is fixed and known to the tests.
- A grant's `ttl` bounds each resource's lifetime. A request may ask for less, and the default is the
  grant's ttl.
- `instances` counts resources created under the grant and not yet deleted. Slice 0 never deletes, so it
  counts created resources (no reaper yet).
- One grant file, read once at start. Changing it means restarting Adele, and a restart re-validates it.
- The client's time limit is 30 s by default.
- Out of scope, by the slice:
  - the reaper, network-denial explanations and the status command (slice 1)
  - the egress allowlist, standing grants for registries and source hosts, and hostile content
    (slice 2)
  - real providers (13, 14)

## Slice 1 (Cycle 3, send `bridge/sends/12-rev2-20261016-091249.md`; corrected in Cycle 4, send `bridge/sends/12-rev16-20261016-102708.md`; natural)

> **Corrected in place, declared (Cycle 4, prompt revision 16).** Revision 16 struck the slice-1 criterion "A
> denied outbound connection returns a plain message …" and split it: a status command over Adele's refusals stays
> in slice 1, and the denied-connection message moves to slice 2 with the allowlist (plan's ruling on FOR-MENTOR
> Item 26, `bridge/feedback/12-20261016-100519-item-26-what-denies-in-slice-1.md`). This section described the struck
> criterion, so it said something false; the lines that did are corrected below (the criteria list, the
> denials-and-status heading, FR-35 to FR-37 and SC-8), each marked *(revision 16)*. Nothing else moved, and slice
> 0's body above was true throughout. Corrected by `/specswarm:modify`, not regenerated, as the send directs: the
> correction makes the spec ask for less, not claim more.

Added work on a body that stays true, recorded here, declared. Prompt 12 is at revision 2, already in
`audited_against` (modify row 4), so nothing is appended. Two lines above become out of date and are left as
written, because the body is append-only per cycle: the Overview's "Not in slice 0" list, and the assumption
that `instances` counts every creation (FR-34 below replaces it from this slice on).

Slice 1's three criteria, verbatim from the send:
- *"Adele destroys resources whose time-to-live has expired, including after the requesting agent's container
  has stopped, and records each reap"* _(slice 1)_.
- *"A status command explains each of Adele's recent refusals by host, naming the grant and limit, what was allowed
  and what was needed, the operator's command, and where the record lives; a host with none says so"* _(slice 1)_
  *(revision 16; it replaces the struck criterion, whose connection half is slice 2's now and is no obligation of
  this slice)*. **The agent's own outbound connections are not filtered until slice 2**: nothing in slice 1 denies
  them, so nothing here explains them.
- *DEMO: "Adele destroys a resource whose TTL expired after the Agent's session ended, and the Operator sees the
  reap in the ledger"* (D21, Manual) _(slice 1)_.

Carried into this cycle by the send, all built: Item 14 (b), ruled a clarification by plan
(`bridge/feedback/12-20261016-091249-adele-text-mode-human-line.md` § Resolution); agentio's guard on
`mutating` + `grant_envelope`; the agent's name on ledger rows (D17's finding).

### Scenarios (slice 1)

**Scenario 5: a box outlives its session (Agent, then Adele, then Operator) — D21.** The agent asks for a box
with `--ttl 1m` and its session ends; its container stops or is removed. Adele's reaper, which runs in her own
container whatever the agent does, finds the expired row, deletes the box at the stand-in with her credential,
reads the stand-in's record back to see it gone, and records a `reaped` row naming the box, the grant, the
session and agent that asked, and the performed row it undoes. The operator runs
`docker exec timelike-adele adeled ledger` and reads it.

**Scenario 6: the stand-in fails during a reap.** It is unreachable, or answers an error. The pass retries on a
bound, then records `reap-failed` with the cause and the attempts. Later passes retry with a growing wait, up to
a bound; the last says it gave up and names the operator's command. Nothing is dropped silently.

**Scenario 7: Adele restarts with expired boxes outstanding.** Her first pass at start reads the ledger (not her
memory) and reaps every expired, unreaped box.

**Scenario 8: the box is already gone.** Someone (or something) deleted it at the provider first. The reap reads
that, records `gone`, and never retries it.

**Scenario 9: a person reads a refusal in text mode (Item 14 (b)).** Under `--text`, stdout is still the
envelope, byte for byte; stderr carries one line saying, in rule 14's shape, what was refused and that only the
operator can extend it, with the command.

### Functional requirements (slice 1)

**The reaper**
- **FR-24** `adeled serve` runs a reaper beside the request interface: one pass at start, then one every
  `ADELE_REAP_INTERVAL` (default 5 s). It runs in Adele's container, so no agent action, container or session
  starts, stops or delays it (P4; 001's boundary).
- **FR-25** A row is **due** when it is `performed`, its `expires_at` is at or before now, and no `reaped` or
  `gone` row refers to it (`ref`). A due row with failed passes waits `interval × 2^(failures−1)` (at most
  5 min) after its last failure. After `ADELE_REAP_PASSES` (default 5) failed passes it is **given up**: no
  automatic pass touches it again.
- **FR-26** One pass over one row: read the stand-in's record; if the box is there **and is the same box** (its
  creation time plus its lifetime equals the row's `expires_at`), delete it, with up to 3 attempts (1 s, then
  2 s apart, each bounded by the upstream's 10 s); then read the record back. The outcome is recorded only from
  that read-back (cross-stack P004):
  - `reaped`: the delete answered and the box is no longer in the record;
  - `gone`: the box was not in the record, or was another box of that name (not touched), or the delete
    answered "no such box" and the read-back agrees;
  - `reap-failed`: the stand-in did not answer, answered an error, or still holds the box after the delete.
    The row's `cause` names which, from Adele's container (P001).
- **FR-27** Each reap row carries: the time, the outcome, the grant, the session and agent of the performed row,
  the capability and `delete`, the resource, `ref` (the performed row's id), `cause` and `attempts`. The
  given-up row's cause ends with the operator's command.
- **FR-28** `docker exec timelike-adele adeled reap [--json]` is the operator's: one pass now over every due row,
  given-up ones included, waits ignored; it prints each outcome. It is safe beside the serving reaper: an outcome
  is written only while the row is still unreaped, read in the same transaction.
- **FR-29** The agent cannot alter the ledger, stop a reap or run `adeled reap` (H1: no Docker socket; nothing of
  Adele's in its container; the request interface has no reap or ledger write).

**The ledger, schema 2**
- **FR-30** New outcomes `reaped`, `gone` and `reap-failed`; new columns `ref`, `agent`, `cause`, `attempts` and
  `host`. A schema-1 file is migrated on open, in one transaction, keeping every row and id; a schema-2 file is
  refused by a schema-1 Adele (slice 0's rule).
- **FR-31** `adeled ledger` prints the new rows; `--json` adds the new columns (null when absent).

**Attribution (carried item 3)**
- **FR-32** The client sends `agent` (`TIMELIKE_AGENT`, when it matches agentio's rule; omitted otherwise).
  Adele checks it with the same pattern and records it on `performed` and `refused` rows, and reap rows copy
  it. It is self-declared attribution, like the session (D-9), never authority.
- **FR-33** The journal (009) reads `agent` from the ledger rows the operator pipes in, so a grant entry is
  labelled with its agent.

**Instances**
- **FR-34** `live` counts `performed` rows not yet `reaped` or `gone`; `spent` is unchanged (money spent stays
  spent).

**Refusals and status (seam 3; Item 26 Q2, confirmed by the mentor; revision 16)**
- **FR-35** Each refusal records `host`, where the refused request would have reached, from Adele's own
  configuration (`standin.box` → the stand-in's host and port), and `extend`, the operator's command as the refusal
  printed it. Slice 2's allowlist denials land in the same record with the same fields.
- **FR-36** `adele status [HOST]` (agent side) and `adeled status [HOST]` (operator side) report Adele's
  reachability and revision as before (P003), and **Adele's recent refusals**: those in the last 24 hours, at most
  20 per host, newest first, with a count. With `HOST`, each is explained: when, the grant and limit, what was
  allowed and what was needed, the operator's command, the ledger row. A host with none says so (exit 0). Both
  figures are printed in the verdict, and so is **where the record lives** (Adele's ledger, read with `adeled
  ledger`; the mentor's addition to Item 26 Q2, now the criterion's own words). Output contract (001): verdict line
  first, JSON when piped. `status` reports on Adele's refusals from her ledger, not on the agent's own connections
  (cross-stack P001).
- **FR-37** The agent's client reads them through `GET /v1/denials` on the request interface, read-only. The path's
  name is kept for slice 2, whose allowlist denials it will also return.

**The human line (Item 14 (b); plan's ruling)**
- **FR-38** agentio: a Result carrying an exit-4 envelope prints, **in text mode only**, one line on stderr in
  rule 14's form; stdout stays exactly the envelope in every mode, and `--json` adds nothing on stderr.
  - grant: `error: beyond grant <grant>: <limit> allows <allowed>, needs <needed>; nothing was performed
    (code 4) — only the operator can extend it: <extend>; ledger #<n>`
  - confirmation: `error: confirmation required: <plan summary> (code 4) — to proceed, run: <confirm>`
  - Past `COLUMNS` (rule 13), the remediation points at the envelope (`see "extend" on stdout`, `see "confirm"
    on stdout`) instead of cutting the command.
- **FR-39** 001's contract gains one sentence saying so (§ Confirmation).
- **FR-40** `adele --help` and `adeled --help` say who runs `extend` (the operator, on the host) and where the
  record is (Adele's ledger, `adeled ledger`), as (a) would have; additive.

**agentio's guard (carried item 2)**
- **FR-41** `Tool(mutating=True, grant_envelope=True)` is refused at declaration (ValueError), with a unit test.

**The stand-in's faults, for tests (cross-stack P005)**
- **FR-42** `adele-standin fault NAME error|drop|clear` and `adele-standin delete NAME`, run inside the stand-in's
  container (the operator's or a test's `docker exec`): a delete of NAME then answers 500, or drops the
  connection unanswered, until cleared. They live in the stand-in's own state volume. The agent cannot reach
  the stand-in (FR-3).

### Success criteria (slice 1)

| SC | Criterion (send, slice 1) | How it is shown |
|---|---|---|
| SC-7 | "Adele destroys resources whose time-to-live has expired, including after the requesting agent's container has stopped, and records each reap" | e2e: boxes with a 1 m lifetime asked for from a throwaway agent container, which is then removed, and from the agent: each is gone from the stand-in's own record and the ledger has its `reaped` row with ref, session and agent. Already gone → `gone`; erroring and dropping stand-in → `reap-failed` with the cause, then `reaped` once cleared; Adele stopped past the expiry and started → reaped from the ledger; the stand-in stopped → `reap-failed` naming it unreachable, then `reaped`. Go units for every outcome, the bound, give-up, the same-box check and the migration |
| SC-8 | "A status command explains each of Adele's recent refusals by host, naming the grant and limit, what was allowed and what was needed, the operator's command, and where the record lives; a host with none says so" *(revision 16)* | e2e, from the agent's container: `adele status HOST` with none (says so), and with several (newest first, each with grant, limit, allowed, needed, the operator's command, session and agent); the record's place in the verdict; the operator's `adeled status HOST` explaining the same rows with Adele's revision. Units for the window, the cap, an Adele that cannot say ("unknown", never "none") and rule 13's columns |
| SC-9 (Manual, D21) | "Adele destroys a resource whose TTL expired after the Agent's session ended, and the Operator sees the reap in the ledger" | Observed by the mentor with the operator after the lane. `unconfirmed` until then |

Also required: Item 14 (b)'s three tests (stdout identical across modes for exit 4; one rule-14 line on stderr
in `--text` and nothing new in `--json`; a grant line names the operator and its command is never in `confirm`);
the guard's unit; the journal labels a ledger row's agent.

### Decisions (slice 1)

**D-10 · The reaper is in `adeled serve`, with an operator command beside it.** A separate reaper container
would be a second holder of the canary. The operator's `adeled reap` exists so that a given-up row has a
remedy that is not "restart Adele".

**D-11 · A reap is recorded from the provider's record, never from the delete's answer** (P004). That is why
there is a read before (the same-box check, so a new box reusing an expired name is never deleted) and a read
after.

**D-12 · Bounds.** 3 attempts per pass; 5 passes; waits doubling from the interval to 5 min. A dead stand-in
costs at most five rows per box, then one given-up row, then silence until the operator acts. The figures are
environment settings (`ADELE_REAP_INTERVAL`, `ADELE_REAP_PASSES`) with these defaults; compose sets none.

**D-13 · The ledger moves to schema 2 by table rebuild.** SQLite cannot change a CHECK constraint in place. The
rebuild copies every row with its id, in one immediate transaction, so a reader never sees half of it.

**D-14 · `agent` is attribution, like `session`.** Proving it would need a credential in the agent's
container (P4).

**D-15 · "Recent" is 24 hours, at most 20 per host.** A day covers a working session and its review; 20 keeps
one host's flood readable. Both are printed so the window is never implicit.

**D-16 · TTLs in tests stay at the grant file's 1 m minimum.** The grant format does not change for tests; the
reaper cells wait on the ledger with the plumbing bound and assert no time (lane.conf's rule: a reap wait is not
a budget).
