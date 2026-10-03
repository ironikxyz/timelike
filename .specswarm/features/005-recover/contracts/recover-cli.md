# CLI contract — `snapshot` and `undo` (005, slice 0)

Both follow 001's output contract (`.specswarm/features/001-agent-shell-baseline/contracts/output-contract.md`):
- the header line `<tool>: <target> [<scope>]`, then the verdict line;
- JSON when piped, text on a TTY;
- `--json`, `--text`, `--limit N`, `--verbose`, `--help` (at most 40 lines) and `--agent-info`;
- structured errors on stderr;
- one session event per invocation.

`<target>` is always the workspace's real path. When the workspace is refused, `<target>` is the
resolved path that was refused.

## Environment

| Variable | Default | Meaning |
|---|---|---|
| `TIMELIKE_SNAPSHOT_MAX_BYTES` | `268435456` | size cap on a snapshot's stored content; `0` = none |
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
- Verdict, complete: `snapshot <id> taken: <F> files, <size> (complete)`.
- Verdict, partial: `snapshot <id> taken (partial): <F> files, <size>; excluded <E> files, <esize> — see below`.
- `<size>` is human-readable bytes (`512 B`, `2.1 KiB`, `3.4 MiB`, `1.2 GiB`, one decimal).
- Lines, one per exclusion, largest first then by path: `excluded: <path> (<size>) — <reason>`. A last
  line names how to raise the cap that bit: `raise with TIMELIKE_SNAPSHOT_MAX_BYTES=<n>` and/or
  `TIMELIKE_SNAPSHOT_MAX_FILE_BYTES=<n>`, where `<n>` is the value that would have captured everything.
- Over the output limit, the cut keeps the verdict, and `more` is a `sed -n` over the full list
  (`<store>/artefacts/…`), never a re-run.
- JSON `data`: `id`, `reason` (`"on demand"`), `label`, `files`, `links`, `dirs`, `bytes`, `partial`,
  `excluded` (the full list of `{path, size, reason}`), `excluded_bytes`, `store`.

**List**, scope `list`:
- Verdict: `<N> snapshots` (`0 snapshots` when none, exit 0).
- One line per snapshot, newest first: `<id>  <reason>  <files> files  <size>  <complete|partial>`, then
  `  "<label>"` if it has one.
- With `--verbose`, each line also carries `taken <taken_at>`.
- JSON `data`: `snapshots`, a list of `{id, reason, label, files, bytes, partial}` plus `taken_at` only
  with `--verbose`.

**Refusals** (exit 1, nothing written):
- `refused: <path> is the filesystem root` / `… is your home directory` / `… is an ancestor of your home
  directory` / `… contains the snapshot store (<store>)`.
- Each has the remediation `change into the project directory (a directory below <home>) and run snapshot again`.
  For the store case it is `set TIMELIKE_SCRATCH_ROOT outside the workspace`.
- Over the entry cap: `refused: <path> has more than <cap> entries (TIMELIKE_SNAPSHOT_MAX_ENTRIES)`, with
  the remediation `snapshot a smaller directory, or raise TIMELIKE_SNAPSHOT_MAX_ENTRIES`.

Errors are agentio `ToolError`s: `error: <what> (code 1) — <remediation>` on stderr, or the JSON form.

## `undo`

```
undo [ID] [--dry-run] [--yes]     restore snapshot ID (default: the newest)
```

Manifest: `mutating: true`, `destructive: true`, probe `["--dry-run"]`, envelopes
`["confirmation_required"]`. Exit codes: 0, 1, 2, 3, 4.

Scope: `restore <id>`.
- **No snapshot / unknown ID:** exit 3. `error: no snapshot <ID> for <ws> (code 3) — snapshots here:
  <ids, newest first>` or `… — take one with: snapshot`.
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
  1. take the safety snapshot `S` (reason `before undo <id>`);
  2. apply the plan;
  3. walk again and re-plan against the snapshot.
  - If the re-plan is empty: exit 0, verdict
    `restored to snapshot <id>: <R> restored, <X> removed; verified; the state before is snapshot <S>`,
    plus `(partial)` after `<S>` if the safety snapshot was partial. Lines: the applied plan, cut over
    the limit with `more` over the artefact list, never a re-run.
  - If not: exit 1, `error: restore of snapshot <id> left <n> differences (code 1) — the state before is
    snapshot <S>; differences: <first few>`.
  - JSON `data`: `id`, `restored`, `removed`, `verified` (true), `before` (`S`), `before_partial`.
- **A refused workspace:** as for `snapshot`, exit 1.
- **A write that would go through a symlink, or into `.git`:** exit 1, naming the path. Nothing further
  is written; the safety snapshot `S` is named.
- `--dry-run` with `--yes`: `--dry-run` wins (exit 0, nothing changes).

## Session events

One per invocation, written by agentio (`events.jsonl`), as for every tool.
