# Adele's request interface (HTTP, network `adele-request`) and the stand-in's (network `adele-standin`)

All bodies are JSON (`Content-Type: application/json`). Both servers bound every request: read 10 s,
write 30 s, body 64 KiB.

## Adele: `http://adele:8480`

### `GET /v1/health`
`200 {"service":"adele","revision":"<GIT_SHA>","grants":["demo",…]}`

### `GET /v1/grants`
`200 {"grants":[{"name","capabilities":[…],"budget_cents","spent_cents","ttl","instances","live","ports":"8080, 9000-9010"}]}`

This is what the agent may know about its limits (P1). It contains no credential.

### `POST /v1/requests`
Request body: data-model § Request.

| Status | Body | Meaning |
|---|---|---|
| 200 | `{"outcome":"performed","grant","resource","cost_cents","expires_at","ledger_id","undo"}` | performed |
| 403 | `{"outcome":"refused","grant","limit":{"name","allowed","needed"},"extend":"<exact operator command>","performed":false,"ledger_id"}` | beyond the grant; nothing performed |
| 400 | `{"error":"<what>","remediation":"<how>","grants":[…]?}` | malformed request, or an ambiguous grant (the candidate grants are listed) |
| 404 | `{"error":"no grant named <g>","grants":[…]}` | an unknown grant was named |
| 502 | `{"error":"stand-in failed: …","performed":false}` | the capability's upstream failed; nothing was recorded as performed |

`limit.name` is one of `capabilities`, `ttl`, `ports`, `instances` or `budget`. `allowed` and `needed`
are strings in the grant file's own syntax:
- `budget`: allowed is what remains, as `0.40 USD`; needed is this request's cost
- `ttl`: `1h` / `2h`
- `ports`: `8080, 9000-9010` / `22`
- `instances`: `2` / `3`
- `capabilities`: the list / the requested one

`extend` is exactly `docker exec timelike-adele adeled extend <grant> <limit> <value>`, with the value
that makes this request allowed:
- `budget`: spent plus this request's cost, as the new total
- `ttl`: the requested ttl
- `ports`: the missing port
- `instances`: live + 1
- `capabilities`: the capability

## Adele: operator commands (inside her container: `docker exec timelike-adele adeled …`)

| Command | Effect | Exit |
|---|---|---|
| `adeled serve` | the container's entrypoint: parse the grants (exit 2 on a malformed file), open the ledger, serve | — |
| `adeled check [--grants FILE]` | parse only; prints `ok: N grants` or the error | 0 / 2 |
| `adeled extend <grant> <limit> <value>` | validate the value in grant-file syntax (budget is a new total; ports and capabilities are added), store the extension, append an `extended` ledger row, print the new effective value | 0 / 2 (bad value) / 3 (no such grant) |
| `adeled ledger [--json]` | print every ledger row | 0 |
| `adeled version` | print the build revision | 0 |

The operator commands open the same SQLite file, under WAL and busy_timeout, while `serve` runs. That is
safe: SQLite serialises writers.

## The stand-in: `http://adele-standin:8481` (profile `standin`)

Every request must carry `Authorization: Bearer <canary>`. Without it, or with a wrong value: `401
{"error":"missing or wrong credential"}`, and nothing changes.

| Method, path | Body | Response |
|---|---|---|
| `POST /v1/quote` | `{"ttl_seconds"}` | `200 {"cost_cents"}` |
| `POST /v1/boxes` | `{"name","ttl_seconds","ports":[…]}` | `201 {"name","created_at","cost_cents"}`, or `409` if the name exists |
| `DELETE /v1/boxes/{name}` | — | `204`, or `404` |
| `GET /v1/boxes` | — | `200 [ … ]` |

`adele-standin list` (run inside its container) prints the record file as JSON without going through
HTTP. Tests use it as the stand-in's own account (cross-stack P004).
