---
parent_branch: master
feature_number: "004"
status: In Progress
created_at: 2026-10-02T04:55:00+00:00
source_prompt: plan/.discover/prompts/12-adele-grants.md
source_send: bridge/sends/12-rev2-20261002-042951.md
prompt_revision: 2
discovery_revision: 9
audited_against: [2]
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
