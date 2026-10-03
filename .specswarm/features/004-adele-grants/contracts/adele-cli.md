# `adele` — the agent-side client (agentio contract v1)

Python, on `agentio`, installed at `/opt/timelike/bin/adele` like every timelike tool. It talks to
`TIMELIKE_ADELE_URL` (default `http://adele:8480`) with `urllib.request`, Python's stdlib HTTP client.
It does not use curl or libcurl.

```
adele: Adele, the authority for reaching actions [help]
usage: adele request <capability> <action> [--name N] [--ttl D] [--port P ...] [--grant G]
       adele grants
       adele status
```

| Subcommand | Does | Exit |
|---|---|---|
| `request standin.box create --name N [--ttl D] [--port P …] [--grant G]` | sends the request | 0 performed · **4 refused (the grant envelope on stdout; discovery revision 10)** · 2 usage or ambiguous grant · 3 unknown grant · 1 Adele unreachable or upstream failed · 124 the client's own limit |
| `grants` | lists the grants Adele will apply, with spent, live and limits | 0 · 1 unreachable |
| `status` | Adele's revision and reachability: the conformance probe. **Always a Result with the header, never a ToolError**, so conform's C3/C4 pass either way (research R8) | 0 reachable · 1 unreachable (the verdict names the URL **and the vantage point**, `from the agent container`) |

**Manifest:**
- `mutating: false`, decided in slice 0 (FLAGGED).
  - In agentio, `mutating: true` means *"exits 4 with the confirm envelope unless `--yes`"* (rule 9).
    Here the mutation is Adele's, performed under a grant: the operator's confirmation, given in
    advance.
  - A `--yes` would be the agent confirming to itself, and an agent always adds it, so it guards
    nothing. Exit 4 then means one thing for this tool: beyond the grant.
  - Raised beside the envelope in FOR-MENTOR Item 13, and **confirmed** by its ruling (discovery
    revision 10): the grant is the confirmation. Rule 8 still binds; slice 0 has nothing destructive.
  - The manifest declares `"envelopes": ["grant_required"]` (conform C9).
- `probe: ["status"]`

**Unreachable Adele (P1, P2):** exit 1, with the error `cannot reach Adele at <url>: <reason>` and the
remediation `the operator starts her: make up (docker compose up -d) on the host`.

**Time limit:** `--timeout`, default 30 s. On expiry: exit 124, with the verdict naming the limit.

**Output:**
- **performed (0):** header `adele: standin.box [create]`; then the verdict `performed under grant
  demo · box tl-1 · 0.25 USD · expires 2026-…Z`. JSON carries the 200 body's fields.
- **refused (4):** the grant envelope on stdout, as JSON in every mode (rule 9's convention), and
  nothing on stderr: `{"tool": "adele", "target": "standin.box", "scope": "create", "status":
  "grant_required", "grant", "limit": {"name", "allowed", "needed"}, "extend": "<the operator's exact
  command>", "extend_by": "operator", "performed": false, "request": {<as sent>}, "ledger_id"}`
  (`grant-envelope.schema.json`, 001's `contracts/`). A 403 that cannot fill it (no grant, limit or
  extend command, or `performed` not false) is exit 1, never a guessed envelope.
