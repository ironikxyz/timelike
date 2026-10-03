# Research — 005 Recover (slice 0)

Facts were gathered from the repository by two read-only delegates and re-read here where a decision
rests on them. Measurements were made on this host (Python 3.12.3; the image has 3.14.7).

## R1 · Cap defaults, measured

**Decision:** size cap `TIMELIKE_SNAPSHOT_MAX_BYTES` = 268435456 (256 MiB) of content per snapshot;
per-file limit `TIMELIKE_SNAPSHOT_MAX_FILE_BYTES` = 67108864 (64 MiB); entry cap
`TIMELIKE_SNAPSHOT_MAX_ENTRIES` = 50000. `0` disables a cap. Lock wait 10 s.

**Measured** (a prototype walk with `os.scandir`, sha256 in 1 MiB chunks, copy into a content store):

| Tree | Files | Bytes | Walk | Hash + copy | Re-hash (all stored) |
|---|---|---|---|---|---|
| this repository's working tree, `.git` skipped | 591 | 85,588,004 | 0.007 s | 0.453 s | 0.275 s |
| synthetic `node_modules` shape: 200 packages × 100 files | 20,000 | 16,990,000 | 0.280 s | 0.928 s | 0.556 s |

So about 190 MB/s for content and about 16,000 files/s for small files. At the defaults the worst
snapshot is about 1.5 s of content or about 3 s of entries on this host: within P2's latency, and the
cap bites before a `node_modules`-sized tree turns a snapshot into a stall. The repository's own tree
(66 MiB, mostly one ignored 56 MB binary) fits whole; its tracked source is 2.1 MB in 247 files.

**Alternatives:** a cap on raw `du` (bites on the binary and drops nothing smaller); no entry cap (a
million-file tree would walk for a minute before saying anything).

## R2 · The store: content-addressed copies, not git

**Decision:** stdlib Python. Content is copied into `objects/<first 2 hex>/<sha256>`, written to a temporary
name and renamed, so a crash never leaves a half-written object under its final name. Snapshot records
are JSON. Identical content is stored once across snapshots.

**Rationale** (spec D-5): a git shadow store records only modes `100644`/`100755`, records a directory
holding its own `.git` as a gitlink (its files uncaptured), and its index writes fire `post-index-change`
through 001's dispatcher (`Dockerfile:162-164`, `dispatch:35-71`). The copy store runs no git at all.

**Alternatives:** git plumbing with `GIT_DIR`, `GIT_INDEX_FILE` and `-c core.hooksPath=` overrides (still
loses modes and nested repositories); `tar` archives per snapshot (no dedup; restore needs the whole
archive read); hard links (rejected by the send: an in-place edit changes the snapshot too).

## R3 · Paths: who resolves them (cross-stack P002)

- **The workspace** is resolved by the tool: `os.path.realpath(os.getcwd())`, then parents are checked
  with `os.lstat(<dir>/.git)`. No `git` process is involved, so no git configuration is read.
- **Home** is taken from both `$HOME` and the password database (`pwd.getpwuid(os.getuid()).pw_dir`), each
  through `realpath`. Either one refuses. The image's agent home is `/home/agent` (`Dockerfile:105-109`).
- **The store** is `agentio`'s session scratch (`<TIMELIKE_SCRATCH_ROOT or /tmp/timelike>/<session>/`,
  `agentio.py:668-684`), realpath'd. If the workspace contains it, the workspace is refused.
- **Inside the workspace**, the tool never calls `realpath` on a path it is about to write. It walks
  the components from the workspace root with `os.lstat`: each must be a real directory. A symlink or file
  in that position is not in the snapshot (or its type changed), so the plan has already removed it; if
  one is still there, the restore stops with exit 1 rather than write through it.
- Files are written to a temporary name in the target directory (`O_CREAT|O_EXCL|O_NOFOLLOW`, mode set
  with `fchmod`) and renamed over the target. `rename` replaces a symlink at the target rather than
  following it.
- Any path with a component named `.git` is refused by the write and remove helpers themselves, not only
  by the planner (defence in depth for D-4).

## R4 · The output contract for a destructive tool

From `agentio.py` (delegate report, re-read at `:263-273`, `:407-421`, `:562-586`):
- `--dry-run` exists only when `destructive=True`, `--yes` only when `mutating=True`; the tool reads
  `args.dry_run` and `args.yes` itself.
- `confirm_required(ctx, target=, scope=, plan=)` builds `confirm` as the agent's own argv plus `--yes`.
  The plan is the dry-run list. It is bounded at the output limit, and its last item names the count left
  and `undo N --dry-run --limit 0`, which is safe to re-run.
- **agentio's generic cap offers "re-run with `--limit 0`"**, which for `undo --yes` would restore again,
  and for `snapshot` would take another snapshot. Both commands therefore cut their own output over the
  limit with an `agentio.Cut`. They write the full list to an artefact file, and `more` is a `sed -n` over
  that file, as `run` does (`run:236-250`). `undo --dry-run` and `snapshot list` change nothing, so the
  generic cap is safe for them.
- No subcommand support in agentio: the verb is an optional positional with `choices`, enforced in
  `main` (the `adele` pattern, `adele:67-69`, `:276-285`).

## R5 · `timelike-conform` on these two tools

Conform runs each tool's manifest `probe` in **its own working directory**, with a temporary scratch root
and never with `--yes` or `--dry-run` added (`timelike-conform:126-138, 213-215`).
- `snapshot`'s probe is `("list",)`: read-only. In a directory with no snapshots it exits 0 with zero
  snapshots; at a refused workspace it exits 1 with the refusal. Both are in the vocabulary.
- `undo`'s probe is `("--dry-run",)`: it changes nothing. It exits 3 (no snapshots) or 1 (refused).
- C2 requires `--yes` and `--dry-run` in `undo`'s manifest flags and `confirmation_required` in its
  envelopes. Neither is in `snapshot`'s, because `snapshot` is neither mutating nor destructive (spec
  FR-21).
- The e2e conformance file counts the tools on PATH against `/opt/timelike/bin`, so both new tools are
  checked without changing it.

## R6 · Persistence

The agent service has no volumes and no tmpfs (`compose.yaml:224`). The default scratch root
`/tmp/timelike` is in the container's writable layer: it survives `docker restart` and is lost on
recreate (`make up` and `tests/run.sh` both recreate). Rule 10 allows state only under the scratch
directory or an undefined "project cache", so the store goes under the session scratch (spec D-7).

## R7 · Names

There is no `undo`, `snapshot`, `checkpoint`, `rewind`, `restore` or `revert` executable in the image's
116 Debian packages (SBOM `scan/out/sbom.syft.json`, read by the delegate). `git restore` and `git revert`
are git subcommands, not executables. Precedent: 003 tests `type -a run` (003 `research.md:124-131`). The
e2e suite asserts `type -a snapshot` and `type -a undo` each resolve to exactly one command.

## R8 · Two tools, one implementation, single files (H5)

**Decision:** `tools/bin/snapshot` holds the workspace, store, walk, plan and restore code, plus the
`snapshot` command. `tools/bin/undo` is a short file that loads `snapshot` from its own real directory
(`importlib.machinery.SourceFileLoader`) and runs the `undo` command.
- Both are single stdlib files with the image shebang.
- The Dockerfile copies `tools/bin/` whole, so they always ship together.
- The unit and conform tests install both.

**Alternatives:**
- a shared module next to `agentio.py`: that changes the image's install step, and the module would be
  more than the contract;
- duplicating the code: two copies of the path-safety code would drift;
- an `argv[0]` symlink: how `COPY --chmod` treats symlinks is unverified without Docker here.

## R9 · Tests against real repositories (cross-stack P005)

The fixture is built by **git itself** inside the container (`git init`, commits, `.gitignore`, staged
changes, `git stash`, a repository hook, a nested repository), plus files the tool has never seen: a
`0600` file, an executable script, a symlink, and a script that deletes a directory. The tests compare
contents themselves (`find`, `sha256sum`, `stat -c %a`, and a listing of `.git` with each file's
checksum), never the tool's message (P004). A restore that should change nothing, and one that should
change everything, are both tested.
