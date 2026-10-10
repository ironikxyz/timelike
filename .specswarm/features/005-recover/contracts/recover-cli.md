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

---

## Slice 1 (Cycle 3)

### Environment (added)

| Variable | Default | Meaning |
|---|---|---|
| `TIMELIKE_STATE_ROOT` | `/var/lib/timelike` | where every workspace's store, the stamps and the trash live (replaces the scratch root for the store) |
| `TIMELIKE_SNAPSHOT_INTERVAL` | `300` (research R11) | seconds between scheduled snapshots of a workspace; `0` every shell start; `off` never |
| `TIMELIKE_SNAPSHOT_MAX_AGE_DAYS` | `30` | purge snapshots older than this; `0` = none |
| `TIMELIKE_STATE_MAX_BYTES` | `4294967296` | purge oldest snapshots while the snapshot content stored in the state root (every workspace's objects; the trash has its own cap) exceeds this; `0` = none |
| `TIMELIKE_PURGE_SECONDS` | `2` | time bound on one purge |
| `TIMELIKE_TRASH_MAX_AGE_DAYS` | `30` | purge trash items older than this; `0` = none |
| `TIMELIKE_TRASH_MAX_BYTES` | `1073741824` | purge oldest trash items while the trash exceeds this; `0` = none |

A value that is not a non-negative integer (or `off` for the interval) is a usage error (exit 2) naming it.

### Lines every result may carry, in this order, after any `do instead:` line

1. `not persistent: <root> is not a mounted volume, so this recovery state dies with the container; mount
   one at <root> (compose.yaml: timelike-state)` — when
   the state root is not on its own filesystem (FR-27). JSON `data.state = {root, persistent}` always.
2. `imported <n> snapshots from session <s> (were <a>–<b>, now <c>–<d>)` (a single id where the range is one) — once, on first use (FR-30); JSON `data.imported`: list of `{session, was, now}`;
   `not imported: <session> snapshot <id>: <why>` for one that fails verification.
3. `purged: snapshot <id> of <ws> (<older than N days | over TIMELIKE_STATE_MAX_BYTES>)`, and
   `purge stopped: <why>; the state root is <size> over TIMELIKE_STATE_MAX_BYTES` (FR-36, FR-37).
   JSON `data.purged`: list of `{workspace, id, why}`.

Then the result's own lines (exclusions, plan). The verdict line is unchanged.

### `snapshot list` (added)

- With no snapshots for this workspace, one line per other workspace in the state root that has some:
  `other workspace with snapshots: <path> (<n>)` (FR-29).
- `--verbose` adds `session <s>` and `agent <a>` to each line; JSON carries `session` and `agent` always.

### Refusals (changed)

- `… contains the snapshot store (<store>)` has the remedy `set TIMELIKE_STATE_ROOT outside the workspace`.
- A state root that cannot be created or written: error, exit 1, naming the path and `TIMELIKE_STATE_ROOT`.

### Lock timeout (changed)

`another snapshot or undo is running on this workspace (lock held for 10 s: <lock path>; holder pid <p>,
session <s>, agent <a>)` — the holder part when the lock file names one.

### `undo --trash` (FR-40)

```
undo --trash                       list the trash, newest first
undo --trash ID --dry-run          list what would be put back
undo --trash ID --yes              put item ID back where it was, verified
```

Scope `trash` (list) or `trash <id>`. Target: the workspace as for `undo`, though the trash is not
per workspace.
- List verdict `<N> items in the trash`; lines `<id>  <n> files  <size>  <first path>[ and <k> more]`.
- Dry run verdict `dry run: trash item <id> — <n> to put back; nothing changed`; lines `put back <kind>
  <abs path>`; a path that exists now: `refused: <abs path> exists` lines, verdict `… <m> blocked`.
- `--yes`: verdict `put back trash item <id>: <n> paths; verified`; any occupied path: exit 1,
  `refused: trash item <id> would overwrite <path>`, nothing written. Without `--yes`: exit 4, the
  confirmation envelope.
- Unknown ID: exit 3, `no trash item <id>`.

### The scheduled snapshot (FR-32–FR-35; not a command)

Taken by `/opt/timelike/libexec/scheduled-snapshot <workspace>` from the shell-start check. Silent when
complete; one stderr line when partial or refused (FR-33). Its record has reason `scheduled`.

### What "taken" and a restore verify (FR-35a; Item 22's ruling on stack note 12)

`taken` (and `verified` in the data) means: the record read back, every object new to this snapshot
re-hashed, and every object the last verified take proved (an unchanged file, through the stat cache)
present as a regular file of its size. A restore (`undo ID --yes`, `undo --trash ID --yes`) re-hashes
every object it will write before it writes any: a mismatch is exit 1,
`restore of snapshot <id> refused: object <sha12> (for <path>) does not match its hash (removed; the next
snapshot stores that content again); nothing was changed` (for the trash: `put back of trash item <id>
refused: …`), with nothing written and no safety snapshot taken.

### The guards (FR-42 to FR-47; not commands)

Bash functions `rm` and `git` in the agent's own shell (`type -a rm git`; `command rm` skips them). Each
prints on stderr, before the real command runs and with the real command's output and exit code
unchanged:
```
timelike: snapshot <id> of <ws> taken before <command>: undo <id> --yes puts the workspace back
timelike: no snapshot of <ws> before <command>: <why>
timelike: no snapshot before <command>: <path> is in no workspace (the trash keeps it)
timelike: trash item <id> keeps <n> files (<size>): undo --trash <id> --yes puts them back
timelike: not kept: <path> (<why>)                      (up to 5, then: not kept: <k> more (undo --trash <id> --dry-run lists them))
timelike: forced push: <remote> <ref> was <sha>[ (from the remote-tracking ref, which may be stale)]; put it back with: git push --force <remote> <sha>:<ref>
timelike: not guarded: <helper> is missing: no snapshot[, no trash]
```
plus the not-persistent line (FR-27) and any `purged:` line (FR-37, FR-41). `<command>` is the command
as typed, cut at 60 characters with `…`; the snapshot's reason is `before <command>`.

| Command | Snapshot | Trash |
|---|---|---|
| `rm` with `-r`/`-R`/`--recursive`, or an option the guard cannot read | each operand's workspace, once | everything it deletes |
| `rm` otherwise | none | the files and links it deletes (an empty dir with `-d`) |
| `git reset --hard` | the worktree, when tracked changes are uncommitted (or status fails) | none |
| `git clean` (not `-n`; `-f`, `-i`, or `clean.requireForce=false`) | the worktree | every path its `-n` lists |
| `git push` forcing a ref (pre-push step; `--no-verify`: the function) | the worktree, once per push | none |
| a git option before the subcommand the guard cannot read | the shell's workspace | none |
| anything else | none, and no fork | none |

