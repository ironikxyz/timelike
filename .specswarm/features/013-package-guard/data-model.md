# Data model — 013 package guard

All in memory, per call, except the override record (a file in the session scratch, rule 10).

| Entity | Fields | Notes |
|---|---|---|
| InstallRequest | ecosystem (`pypi`/`npm`), tool (`pip`/`uv`/`npm`/`pnpm`), argv, cwd, project root, registries (ordered), packages, lockfile_only, unreadable (reason or none) | From the argv parse (FR-5 to FR-9) and the configuration (FR-10 to FR-12) |
| PackageRequest | name (as written), key (normalized), spec (version, range, tag or none), source (`registry`/`local`/`url`), origin (`argv`/`-r FILE`/`manifest`) | `key` is PEP 503's for pypi, the name itself for npm |
| Registry | url (credentials redacted for display), kind (`simple`/`npm`), scope (npm scope or none) | — |
| Release | version, uploaded (UTC datetime or none), yanked | From the Simple API files or npm's `time` |
| Lookup | registry, status (`found`/`absent`/`unreachable`/`unreadable`), how (timeout, refused, DNS, TLS, HTTP n), releases | One per name per registry, run concurrently |
| Lock | path, kind (`uv.lock`/`pylock.toml`/`requirements`/`package-lock`/`pnpm-lock`), pins {key: version}, readable | — |
| CheckResult | package, result (`ok`/`pinned`/`absent`/`too-new`/`unreachable`/`age-unknown`/`unchecked-source`/`unreadable`/`unchecked`), registry, release, released, detail, suggestion | `refused` iff result ∉ {ok, pinned, unchecked} |
| OverrideRecord | v, time, session, agent, cwd, command, overridden[{package, ecosystem, registry, reason, detail}], command_exit | Rewritten once CMD has exited |

## The override in the session event (Cycle 1 addendum; Item 24 Q4)

`override`, optional in 001's `event.schema.json`, written only by a call that proceeded over a refusal:

| Field | Type | Meaning |
|---|---|---|
| `ecosystem` | `pypi` \| `npm` | |
| `packages` | list | each `{name, version?, registry, reason, released?, detail}`: `version` the version or range the command named; `reason` the refusal's word; `released` the date of a dated release (too new) |
| `command` | list of strings | the command run over the refusal, credentials in URLs and secret-shaped words redacted |

The record file stays (above), and the event's `ref.log` still points at it.
