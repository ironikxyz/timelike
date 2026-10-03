# Data model — 004 Adele & grants (slice 0)

## Grant file (operator-written; read by Adele at start)

Grammar (line-based, so every error has a line):

```
file     := { blank | comment | section | pair }
blank    := whitespace only
comment  := optional whitespace, then "#", then anything
section  := "[grant " NAME "]"            NAME = [a-z][a-z0-9-]{0,62}
pair     := KEY ws? "=" ws? VALUE         only inside a section
```

| Key | Required | Value | Example | Meaning |
|---|---|---|---|---|
| `capabilities` | yes | comma-separated capability names, each known to Adele | `standin.box` | what may be requested |
| `budget` | yes | decimal with at most 2 places, then `USD` | `2.00 USD` | total estimated cost of performed requests |
| `ttl` | yes | Go-style duration, between 1m and 720h | `1h`, `90m` | longest lifetime of any resource created |
| `instances` | yes | integer, 0 or more | `2` | most live resources under this grant |
| `ports` | yes | comma-separated ports or ranges, 1–65535; `none` for none | `8080, 9000-9010` | ports a resource may expose |

**Malformed: Adele exits 2 at start.** stderr is one line, `adeled: <file>:<line>: <what> — <how to fix>`.
- a pair outside any section
- a line that is neither a section nor a pair
- a bad grant name
- a duplicate grant
- a duplicate key in one grant
- an unknown key
- an empty or unparsable value
- an unknown capability
- a negative or over-precise budget
- a non-USD currency
- a ttl out of range
- a port out of range
- a reversed range
- a grant missing a required key (reported at the section's line)
- a file with no grant (reported at line 1)
- an unreadable file (line 0, naming the OS error)

The first error found stops the parse. Nothing is half-loaded.

## Effective grant

The file's values, overlaid with the operator's extensions (latest wins per limit). Computed state:
- `spent`: the sum of `cost_cents` over the grant's `performed` rows
- `live`: the count of the grant's `performed` rows. Slice 0 has no reaper or delete, so this is every
  creation; slice 1 subtracts reaped ones.

## Request (agent → Adele)

| Field | Type | Notes |
|---|---|---|
| `session` | string | agentio session id (`^[A-Za-z0-9._-]{1,64}$`) |
| `grant` | string or null | optional |
| `capability` | string | slice 0: `standin.box` |
| `action` | string | slice 0: `create` |
| `params.name` | string | box name, `[a-z][a-z0-9-]{0,62}` |
| `params.ttl` | duration string or null | default: the grant's ttl |
| `params.ports` | list of int | default `[]` |

**Check order** (the first failure is the one reported): capability → ttl → ports → instances → budget.
The budget check needs the stand-in's quote, so the cheap checks come first. A quote is a read and
performs nothing.

## Ledger (SQLite, `/var/lib/adele/adele.db`, Adele's volume only)

Table `ledger`. Append-only: Adele never updates or deletes a row.

| Column | Type | performed | refused | extended |
|---|---|---|---|---|
| `id` | INTEGER PK | ✓ | ✓ | ✓ |
| `at` | TEXT RFC 3339 UTC | ✓ | ✓ | ✓ |
| `outcome` | TEXT | `performed` | `refused` | `extended` |
| `grant` | TEXT | ✓ | ✓ (may be empty when no grant resolved) | ✓ |
| `session` | TEXT | ✓ | ✓ | `operator` |
| `capability`, `action` | TEXT | ✓ | ✓ | — |
| `resource` | TEXT | box name | requested name | — |
| `cost_cents` | INTEGER | estimate | estimate if quoted, else NULL | — |
| `expires_at` | TEXT RFC 3339 UTC | created + ttl | — | — |
| `undo` | TEXT JSON | `{"capability":"standin.box","action":"delete","params":{"name":…}}` | — | — |
| `limit_name`, `allowed`, `needed` | TEXT | — | ✓ | the limit and its old and new value |

Table `extensions` (`grant`, `limit_name`, `value`, `at`): the overlay. Every row has a matching
`extended` ledger row.

Table `meta` (`key`, `value`): `schema_version = 1`.

## Stand-in record (its own container, `/var/lib/standin/boxes.json`)

A JSON array of `{name, created_at, ttl_seconds, ports, cost_cents}`. It is written by the stand-in on
create and delete, and read by `adele-standin list`. Tests read it to check "performed" and "nothing
performed" (cross-stack P004).

**Pricing:** 25 US cents per hour, pro rata per started minute: `ceil(ttl_minutes × 25 / 60)` cents.

## Canary

`tlcanary-` followed by 32 lowercase hex characters (128 bits, from `/dev/urandom`):
- written once by the compose service `adele-secret` into the volume `adele-secret`, at `canary`,
  owned `root:10001`, mode 0440
- mounted read-only at `/run/adele-secret/canary` in Adele and the stand-in only (spec D-8, revised at
  T010)
