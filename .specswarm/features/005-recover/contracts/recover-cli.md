# CLI contract — `snapshot` and `undo` (005, slice 0)

Both follow 001's output contract (`.specswarm/features/001-agent-shell-baseline/contracts/output-contract.md`):
- the header line `<tool>: <target> [<scope>]`, then the verdict line;
- JSON when piped, text on a TTY;
- `--json`, `--text`, `--limit N`, `--verbose`, `--help` (at most 40 lines) and `--agent-info`;
- structured errors on stderr;
- one session event per invocation.

`<target>` is always the workspace's real path. When the workspace is refused, `<target>` is the
resolved path that was refused.

**Outcomes are verdicts, errors are errors** (amended in implement, T009; FLAGGED in `decisions.md`).
A refusal, a missing snapshot, and a restore that fails verification are each a **result**:
- the header and the verdict on stdout;
- the first line `do instead: <remedy>`, then any detail lines;
- JSON `data.remedy`;
- the exit code (1 or 3).

`adele status` reports an unreachable Adele the same way. This was forced by `timelike-conform`:
its probes (`snapshot list`, `undo --dry-run`) run in conform's own working directory, which in the
image is the home directory, and C3/C4 need a header on stdout.

Usage errors (exit 2), the lock timeout and I/O failures remain structured errors on stderr
(rule 14): `error: <what> (code N) — <remediation>`.

## Environment

| Variable | Default | Meaning |
|---|---|---|
| `TIMELIKE_SNAPSHOT_MAX_BYTES` | `268435456` | size cap on the bytes a snapshot adds to the store, after deduplication (content already stored costs nothing; repeated content counts once; *Cycle 2, revision 11*); `0` = none |
| `TIMELIKE_SNAPSHOT_MAX_FILE_BYTES` | `67108864` | per-file limit; `0` = none |
| `TIMELIKE_SNAPSHOT_MAX_ENTRIES` | `50000` | entry cap on the walk; `0` = none |
| `TIMELIKE_SCRATCH_ROOT`, `TIMELIKE_SESSION` | agentio's | where the store lives |

A value that is not a non-negative decimal integer is a usage error (exit 2) that names the variable.

## `snapshot`

```
snapshot [-m TEXT]        take a snapshot of the workspace
snapshot list             list this workspace's snapshots, newest first
```

Manifest: `mutating: false`, `destructive: false`, probe `["list"]`. Exit codes: 0, 1, 2.

**Take**, scope `take`:
- *(Cycle 2, revision 11.)* The verdict says `taken` only after the snapshot is verified restorable:
  the record read back, and every object it names re-hashed. If verification fails, nothing is taken:
  exit 1, a verdict `snapshot <id> not taken: it could not be verified restorable: <what>`, then
  `do instead: run snapshot again; if this repeats, the store <store> is damaged: remove it and take a
  new snapshot`. The identifier stays used.
- Verdict, complete: `snapshot <id> taken: <F> files, <size> (complete)`.
- Verdict, partial: `snapshot <id> taken (partial): <F> files, <size>; excluded <E> files, <esize> — see below`.
- `<size>` is human-readable bytes (`512 B`, `2.1 KiB`, `3.4 MiB`, `1.2 GiB`, one decimal).
- Lines, one per exclusion, largest first then by path: `excluded: <path> (<size>) — <reason>`. A last
  line names how to raise the cap that bit: `raise with TIMELIKE_SNAPSHOT_MAX_BYTES=<n>` and/or
  `TIMELIKE_SNAPSHOT_MAX_FILE_BYTES=<n>`, where `<n>` is the value that would have captured everything.
  For the size cap that is the content new to this store (files over the per-file limit counted whole),
  so a second snapshot names less than the first when the first stored part of it.
- Over the size cap, the largest new content is left out first, ties by path; files sharing one content
  are left out together.
- Over the output limit, the cut keeps the verdict, and `more` is a `sed -n` over the full list
  (`<store>/artefacts/…`), never a re-run.
- JSON `data`: `id`, `reason` (`"on demand"`), `label`, `files`, `links`, `dirs`, `bytes`, `stored_bytes`
  (bytes this snapshot added to the store), `partial`, `excluded` (the full list of
  `{path, size, reason}`), `excluded_bytes`, `verified` (true), `store`. *(`stored_bytes` and
  `verified` added in Cycle 2.)*

**List**, scope `list`:
- Verdict: `<N> snapshots` (`0 snapshots` when none, exit 0).
- One line per snapshot, newest first: `<id>  <reason>  <files> files  <size>  <complete|partial>`, then
  `  "<label>"` if it has one.
- With `--verbose`, each line also carries `taken <taken_at>`.
- JSON `data`: `snapshots`, a list of `{id, reason, label, files, bytes, partial}` plus `taken_at` only
  with `--verbose`.

**Refusals** (exit 1, nothing written; a verdict, scope `take` or `list`):
- `refused: <path> is the filesystem root` / `… is your home directory` / `… is an ancestor of your home
  directory` / `… contains the snapshot store (<store>)`.
- Each has the remediation `change into the project directory (a directory below <home>) and run snapshot again`.
  For the store case it is `set TIMELIKE_SCRATCH_ROOT outside the workspace`.
- Over the entry cap: `refused: <path> has more than <cap> entries (TIMELIKE_SNAPSHOT_MAX_ENTRIES)`, with
  the remediation `snapshot a smaller directory, or raise TIMELIKE_SNAPSHOT_MAX_ENTRIES`.

The remediation is the `do instead:` line.

## `undo`

```
undo [ID] [--dry-run] [--yes]     restore snapshot ID (default: the newest that is not a safety snapshot)
```

Manifest: `mutating: true`, `destructive: true`, probe `["--dry-run"]`, envelopes
`["confirmation_required"]`. Exit codes: 0, 1, 2, 3, 4.

Scope: `restore <id>`.

**Default ID:** the newest snapshot whose reason is not `before undo …`, so a repeated `undo --yes` changes
nothing (rule 7). `undo <S> --yes` restores a safety snapshot, which undoes an undo.
- **No snapshot / unknown ID:** exit 3, a verdict (scope `restore <ID>` or `restore newest`):
  `no snapshot <ID> for <ws>` (or `no snapshot for <ws>`), then `do instead: snapshots here: <ids,
  newest first>` or `do instead: take one with: snapshot`. A non-numeric ID is a usage error (exit 2).
- **`--dry-run`:** exit 0. Verdict
  `dry run: snapshot <id> — <R> to restore, <X> to remove; nothing changed`. Lines are the plan, one
  change per line: `restore file <path>`, `restore link <path>`, `restore dir <path>`, `remove file
  <path>`, `remove link <path>`, `remove dir <path>`, and `keep dir <path> (holds <what>)` (not
  counted). An empty plan gives the verdict `dry run: snapshot <id> — nothing to change`. JSON `data`:
  `id`, `restore` (count), `remove` (count), `plan` (list of `{change, kind, path}`; `change` is one of
  `restore`, `remove`, `keep`).
- **Neither flag:** exit 4, the confirmation envelope on stdout (rule 9). `plan` is the dry run's lines,
  bounded at the output limit; when bounded, its last item is
  `… and <n> more: undo <id> --dry-run --limit 0`. `confirm` is the agent's own argv plus `--yes`.
  Nothing changes. An empty plan does **not** need confirmation: exit 0, verdict
  `nothing to restore: the workspace matches snapshot <id>`.
- **`--yes`, empty plan:** exit 0, same verdict as above. No safety snapshot is taken.
- **`--yes`, non-empty plan:**
  1. take the safety snapshot `S` (reason `before undo <id>`), verified as for `snapshot`. If it cannot
     be verified, nothing is applied: exit 1, a verdict `restore of snapshot <id> not started: the
     snapshot of the state it would replace failed: <its verdict>`, then `do instead: nothing was
     changed; run undo <id> --yes again; …` *(Cycle 2)*;
  2. apply the plan;
  3. walk again and re-plan against the snapshot.
  - If the re-plan is empty: exit 0, verdict
    `restored to snapshot <id>: <R> restored, <X> removed; verified; the state before is snapshot <S>`,
    plus `(partial)` after `<S>` if the safety snapshot was partial. Lines: the applied plan, cut over
    the limit with `more` over the artefact list, never a re-run.
  - If not: exit 1, a verdict `restore of snapshot <id> left <n> differences; the state before is
    snapshot <S>`, then `do instead: undo <S> --yes returns to the state before; …`, then one line per
    remaining difference.
  - JSON `data`: `id`, `restored`, `removed`, `verified` (true), `before` (`S`), `before_partial`.
- **A refused workspace:** as for `snapshot`, exit 1.
- **A write that would go through a symlink, or into `.git`:** exit 1, naming the path. Nothing further
  is written; the safety snapshot `S` is named.
- `--dry-run` with `--yes`: `--dry-run` wins (exit 0, nothing changes).

## Session events

One per invocation, written by agentio (`events.jsonl`), as for every tool.
