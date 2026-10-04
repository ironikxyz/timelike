# Data model — 005 Recover (slice 0)

All state is files under the session scratch directory (rule 10). Nothing is written to the workspace
except by a confirmed restore.

## Store

```
<scratch root>/<session>/snapshots/<key>/        mode 0700
  workspace                 the workspace's real path, one line (the key is derived from it)
  lock                      flock(2) target; holds no data
  next                      the next identifier, decimal, one line
  snaps/<id>.json           one record per snapshot, written once (temp + rename), mode 0600
  objects/<aa>/<sha256>     content, written once (temp + rename), mode 0400
  artefacts/                full listings for cut output (Cut.full_output)
```

- `<scratch root>` is `TIMELIKE_SCRATCH_ROOT`, default `/tmp/timelike`. `<session>` is
  `TIMELIKE_SESSION`, default `default` (`agentio`).
- `<key>` is the first 16 hex digits of the sha256 of the workspace's real path. Two workspaces never
  share a store. If `workspace` names a different path from the one hashed (a collision), the store is
  refused (exit 1); this is never expected.
- Identifiers come from `next`, read and incremented under the lock: 1, 2, 3, and never reused.
- **Verification before "taken"** *(Cycle 2, revision 11; stack note 12)*: after the record is written
  it is read back and compared, every entry path must be one a restore may write, and every object it
  names must be a regular file of the recorded size whose sha256 is its name. On any failure the record
  is deleted (its identifier stays used), a damaged object is removed so the next snapshot stores it
  again, and the snapshot is not taken.

## Snapshot record (`snaps/<id>.json`)

| Field | Type | Meaning |
|---|---|---|
| `v` | int | record format, `1` |
| `id` | int | the identifier |
| `reason` | string | `on demand`, or `before undo <id>` (slice 1 adds more) |
| `label` | string or null | `-m TEXT` |
| `workspace` | string | the workspace's real path |
| `taken_at` | string | ISO 8601 UTC; shown only with `--verbose` (rule 11) |
| `entries` | list | sorted by `path` |
| `excluded` | list | sorted by `path` |
| `files`, `links`, `dirs` | int | counts of captured entries by kind |
| `bytes` | int | total size of captured file content |
| `stored_bytes` | int | bytes this snapshot added to the store: content not already in it, counted once *(Cycle 2, revision 11)* |
| `size_cap_needed` | int | only when the size cap was applied: the new content it would have taken to capture every candidate *(Cycle 2)* |
| `excluded_bytes` | int | total size of excluded files |
| `partial` | bool | `excluded` is not empty |
| `caps` | object | `{max_bytes, max_file_bytes, max_entries}` in force when taken |

**Entry:** `{path, kind}` plus, by kind:
- `file`: `sha256`, `size`, `mode`;
- `link`: `target` (the link text, never resolved);
- `dir`: `mode`.

`path` is relative to the workspace, `/`-separated, never empty, never absolute, never containing `.`,
`..` or a `.git` component. `mode` is the permission bits only (`st_mode & 0o7777`, as an int). The
workspace root itself is not an entry.

**Exclusion:** `{path, size, reason}` with `reason` one of:
- `over the per-file limit (<n> bytes)`;
- `over the size cap: largest files left out first (<n> bytes)`. The cap counts bytes new to the
  store (*Cycle 2, discovery revision 11*): content already stored costs nothing, and content repeated
  within the snapshot counts once. Files sharing one content are left out together, largest content
  first, ties by the smallest path;
- `not a regular file, symlink or directory (<kind>)`, where kind is socket, fifo, block device or
  character device;
- `unreadable: <strerror>`.

## What the walk sees

- Starting at the workspace root, `os.scandir` without following symlinks; children are sorted by name.
- Any entry named `.git` (directory, file or symlink) is skipped with everything under it. It is never
  listed as an exclusion: it is out of scope, not excluded.
- A symlink to a directory is a `link` entry. It is not descended into.
- The entry cap counts every entry seen, `.git` excluded. Exceeding it stops the walk and refuses the
  snapshot (exit 1). Nothing is stored.

## Plan (computed, never stored)

The workspace walked now (`current`) against a record (`snap`):

| Condition | Change |
|---|---|
| `snap` entry absent from `current` | `restore <kind> <path>` |
| both `file`: sha256 or mode differ | `restore file <path>` |
| both `link`: target differs | `restore link <path>` |
| both `dir`: mode differs | `restore dir <path>` |
| kinds differ | `remove <current kind> <path>`, then `restore <snap kind> <path>` |
| `current` entry absent from `snap`, not in `snap.excluded`, and not under an excluded path | `remove <kind> <path>` |
| `current` entry in `snap.excluded` | no change: it was not captured, so it is neither restored nor removed |

- The current file content is compared by size first, then by sha256.
- A directory planned for removal that still holds something a restore must keep (a `.git`, or an
  excluded file) is not removed. The plan lists it as `keep dir <path> (holds <what>)`, and that is
  not counted as a change.
- **Order of application:** removals deepest first (files and links unlinked, then directories
  `rmdir`ed), then directories shallowest first, then files and links.
- **Display order:** sorted by path, and for one path `remove` before `restore`.

## Lock

`flock(LOCK_EX)` on `lock`, tried every 50 ms for up to 10 s. Holding it covers the walk, the store
writes, the record write, and (for `undo --yes`) the safety snapshot, the apply and the verify. On
timeout: exit 1, `another snapshot or undo is running on this workspace (lock held for 10 s)`.
