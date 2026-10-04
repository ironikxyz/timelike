---
parent_branch: master
feature_number: "005"
status: In Progress
created_at: 2026-10-03T01:58:00+00:00
source_prompt: plan/.discover/prompts/07-recover.md
source_send: bridge/sends/07-rev1-20261003-013915.md
prompt_revision: 1
discovery_revision: 10
audited_against: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
slice: 0
---

# Feature: Recover — snapshots and undo (prompt 07, slice 0: skeletal)

## Overview

What the project's name promises: when the agent takes a wrong turn inside its workspace, it can take
the workspace back to an earlier state itself, in one command, without the operator (P5). That includes
files version control does not track or ignores, and changes made by scripts rather than by the agent's
own commands.

Slice 0 is on demand. The agent takes a snapshot of its workspace, lists its snapshots, and restores
any one of them. A restore first shows exactly what it will change, and it never touches the project's
own version-control state. Snapshots are capped in size: when a workspace is bigger than the cap, the
snapshot says what it left out and why, so recovery is never implied silently (T2).

Two commands, named after what the agent would reach for:
- **`snapshot`** takes a snapshot of the workspace (`snapshot list` lists them);
- **`undo`** restores one (the newest by default), after a dry run or a confirmation.

Slices 1 and 2 build on this record: automatic snapshots before destructive commands, a restorable
trash, and replays of the documented incident classes. They are out of scope here, but two things are
kept open for them: every snapshot records **why** it was taken, and a restore works from **any**
snapshot, not only the newest.

**Principles served:** P5 (wrong turns are recoverable), P2 (every call concludes; the cap is stated,
never implied, T2), P3 (found where agents look), P7 (works in any shell, no harness hook).

**Actors:** the Agent (Primary) takes, lists and restores snapshots of its own work. The Operator
(Administrative) observes the demo (D7). Peer agents (concurrent) keep their own snapshots.

**Depends on:** feature 001 (the output contract, the confirmation envelope, the scratch root, session
events, `timelike-conform`). Built and current at revision 10.

## User Scenarios

### Scenario 1: the agent deletes the wrong directory and undoes it (Agent) — D7

1. The agent works in a project under its home directory. Before a risky change it runs `snapshot`.
   The verdict names the snapshot's identifier, how many files it holds and their size, and anything it
   left out.
2. The agent runs a script that deletes `src/` (the wrong directory), and writes a new file `notes.txt`.
3. The agent runs `undo --dry-run`. It lists exactly the changes a restore would make: `src/` and its
   files come back, `notes.txt` goes. Nothing changes yet.
4. The agent runs `undo --yes`. The workspace is back as it was at the snapshot: `src/` with its
   contents, no `notes.txt`. The verdict says the restore was **verified** against the snapshot, and
   names the snapshot it took of the state it just replaced, so the undo can itself be undone.

### Scenario 2: the agent runs `undo` without confirming (Agent)

The agent runs `undo` alone. Restore is destructive (it removes files created after the snapshot), so
by contract rule 9 it changes nothing and exits 4 with the confirmation envelope. The envelope's plan is
the dry run's list, and its `confirm` is the agent's own command with `--yes`. Running that is the one
undo command.

### Scenario 3: a workspace bigger than the cap (Agent)

The workspace holds a large build artefact. `snapshot` takes a **partial** snapshot: it leaves out the
largest files until the rest fits under the cap. The verdict says the snapshot is partial and names
what was excluded, why, and how to raise the cap. A later `undo` leaves the excluded files alone: they
were not created after the snapshot, so it neither restores nor removes them.

### Scenario 4: the agent snapshots its home directory (Agent)

The agent runs `snapshot` from `/home/agent`, the image's default working directory, outside any
project. The workspace would be the home directory, which is refused (P5, G1). The verdict says why and
what to do instead: change into the project directory and run it again.

### Scenario 5: the project's own git state (Agent)

The workspace is a git repository with commits, staged changes, a stash, ignored files and untracked
files. Taking a snapshot and restoring it leaves the repository's history, index, stash and everything
else inside `.git/` byte-identical. Files that git ignores are captured like any other file.

## Functional Requirements

### The workspace

- **FR-1** The workspace is the nearest directory, from the current directory upward, that contains a
  `.git` entry (a directory or a file), else the current directory itself. It is resolved to a real
  path (symlinks resolved) before anything else is decided.
- **FR-2** A workspace that resolves to the filesystem root, to the agent's home directory, or to an
  ancestor of either, is refused with exit 1. The verdict names the resolved path, says why it is
  refused, and names what to do instead (change into the project directory). Nothing is written.
- **FR-3** A workspace that contains the snapshot store is refused the same way.

### What a snapshot holds

- **FR-4** A snapshot records every regular file, symlink and directory in the workspace, whatever their
  version-control status (tracked, untracked or ignored), except what FR-5 to FR-7 leave out. For each
  file it records the path relative to the workspace, the content, and the permission bits; for each
  symlink, its target text (never followed); for each directory, that it existed.
- **FR-5** **Out of scope, never captured and never restored:** every directory named `.git` and
  everything under it, and every file named `.git`, at any depth. This is version control's own state,
  which belongs to the project (revision 8's git-state boundary).
- **FR-6** **Excluded** (captured as a name and size only, never as content):
  - a file larger than the per-file limit;
  - when the remaining content would exceed the snapshot's size cap, the **largest** remaining files,
    one at a time, until it fits (ties broken by path). *(Amended in Cycle 2, declared, for discovery
    revision 11's condition 3: the cap counts the bytes the snapshot **adds to the store**, after
    deduplication. Content already stored counts as nothing, content repeated within the snapshot
    counts once, and files sharing one content are left out together.)*
  - anything that is not a regular file, symlink or directory (sockets, FIFOs, devices);
  - a file that cannot be read.

  Each exclusion carries its reason. The snapshot is then **partial**, and says so.
- **FR-7** A workspace with more entries than the entry cap is refused with exit 1, naming the cap and its
  variable, and nothing is stored: the walk itself would cost more latency than P2 allows. The walk stops
  at the cap, so the verdict says "more than <cap>" rather than an exact count. *(Amended in implement.)*
- **FR-8** The caps have defaults and are set by environment variables (one per cap). A cap of 0 means
  no limit for that cap.

### Taking, listing and identifying

- **FR-9** `snapshot` takes a snapshot of the workspace. Its verdict names the identifier, the file count
  and the size captured; when partial, the number and size of what was excluded; and its first lines of
  output list the exclusions, largest first, each with its reason, bounded by the output cap. With
  `--json` the exclusions are listed in full. *(Amended in Cycle 2, declared, for discovery revision
  11's condition 4 and `stack.md` note 12:)* the verdict says **taken** only after the snapshot is
  verified restorable: its record is read back, and every object it names is re-hashed against its
  name. A snapshot that fails verification is not taken: no record stays, the verdict says so and why,
  and exit is 1.
- **FR-10** A snapshot may carry a short label (`-m TEXT`). It always records **why** it was taken:
  `on demand` for `snapshot`, `before undo <id>` for the safety snapshot of FR-15. Slice 1 adds further
  reasons.
- **FR-11** Identifiers are small integers, numbered per workspace in the order taken, starting at 1, and
  never reused within a store.
- **FR-12** `snapshot list` lists the workspace's snapshots, newest first: identifier, reason, label,
  files, size and whether partial. Output is sorted and deterministic; times appear only with
  `--verbose` (rule 11).
- **FR-13** Taking or listing never changes the workspace.

### Restoring

- **FR-14** `undo [ID]` restores snapshot `ID`, or, when no `ID` is given, the newest snapshot that is not
  a safety snapshot (FR-19). An unknown `ID`, or a workspace with no snapshots, exits 3 and names what
  exists. *(Amended in implement: defaulting to the newest of all would make a second `undo --yes`
  undo the first, so undo would not be idempotent (rule 7). Safety snapshots stay reachable by `ID`.)*
- **FR-15** The restore plan is computed by comparing the workspace now with the snapshot:
  - **restore**: a captured file or symlink that is missing, or whose content, target or permission
    bits differ; a captured directory that is missing;
  - **remove**: a file, symlink or directory present now that the snapshot does not hold, unless it is
    out of scope (FR-5) or was excluded from the snapshot (FR-6);
  - an entry whose type changed (a file that is now a directory, for example) is removed and then
    restored.
- **FR-16** `undo --dry-run` prints the plan, one change per line, sorted, with counts, and changes
  nothing.
- **FR-17** `undo` without `--yes` changes nothing and exits 4 with the confirmation envelope (rule 9).
  Its plan is the dry run's list; its `confirm` is the agent's own command with `--yes`.
- **FR-18** `undo --yes` with an empty plan changes nothing and says so.
- **FR-19** `undo --yes` with a non-empty plan first takes a snapshot of the current workspace (reason
  `before undo <id>`), then applies the plan, then **verifies** the workspace against the snapshot by
  re-reading it. Its verdict says "restored" only when verification finds no difference; otherwise it
  exits 1 and names every difference left. It names the safety snapshot's identifier.
- **FR-20** A restore never writes, removes or follows anything inside an out-of-scope `.git` (FR-5), and
  never writes through a symlink: before writing a path, every parent component inside the workspace is
  checked to be a real directory, and a symlink found there is removed (it was created after the
  snapshot) before the directory is restored.

### Contract

- **FR-21** Both commands follow the agent output contract of feature 001: the header line, JSON when
  piped, the output cap, the exit-code vocabulary, `--help` within 40 lines, `--agent-info`, structured
  errors, and one session event per invocation. `undo` declares itself mutating and destructive, so it
  has `--yes` and `--dry-run`. `snapshot` declares neither: it writes only to the snapshot store, never
  to the workspace. `timelike-conform` passes on both.
- **FR-22** Both commands are announced where agents look: `timelike`'s tool list (automatic) and the
  README, alongside `run` and `adele`. Neither name shadows an existing command in the image.

### Storage

- **FR-23** Snapshots live outside the workspace, in the session's scratch directory (rule 10), one store
  per workspace. Content is stored by copy, addressed by its hash, so identical content is stored once
  across snapshots. No hard links (an in-place edit would change the snapshot), no snapshotting
  filesystem and no container commit. *(Cycle 2: confirmed by discovery revision 11, which keeps the
  store's slice-0 location — outside the workspace — and moves it to a per-workspace state root in
  slice 1.)*
- **FR-24** Two invocations against the same store never interleave: a second waits for the first, up to
  a bounded time, and then exits 1 naming the holder.

## Success Criteria

Each is one test, named after its distinguishing text, in the image (bats e2e per invocation style) and
on the host (pytest).

- **SC-1** *"Taking a snapshot records tracked, untracked and ignored-but-not-excluded files of the
  workspace and prints its identifier, file count and size"* — in a real git repository with tracked,
  untracked and ignored files, `snapshot` exits 0 and its verdict names an identifier, a file count and a
  size equal to the workspace's files outside `.git`; a restore of each of the three kinds brings it back
  byte-identical. *(slice 0)*
- **SC-2** *"Restoring a snapshot returns every captured file to its captured content and removes files
  created after it, and a dry run lists exactly those changes first"* — after edits, deletes (including a
  directory removed by a script), mode changes and new files, `undo --dry-run` lists exactly the set of
  changes the test made, and `undo --yes` leaves the workspace byte-identical to the snapshot, checked by
  the test comparing contents itself, never by the tool's message (P004). A restore that should change
  nothing changes nothing. *(slice 0)*
- **SC-3** *"The project's own version-control history, index and stash are unchanged by taking or
  restoring a snapshot"* — `.git/` is byte-identical (every file's path, content and mode) before and
  after `snapshot` and `undo --yes`, in a repository with commits, a staged index, a stash, and its own
  hooks. *(slice 0)*
- **SC-4** *"A snapshot whose content would exceed the size cap is refused or partial, and the verdict
  names what was excluded and why"* — with a small cap, the snapshot is partial, names each excluded file
  and its reason, and a later `undo --yes` leaves those files in place; a workspace over the entry cap is
  refused, naming the cap and its variable. *(slice 0)*
- **SC-5** *DEMO: "the Agent deletes the wrong directory and restores it with one undo command"* (D7) —
  Manual: observed by the operator in a real exchange. *(slice 0)*

Further, from the contract and the decisions below (not criteria of the prompt):
- `timelike-conform` passes on `snapshot` and `undo` in the image;
- a snapshot of the home directory, of `/`, and of `/home` is refused with what to do instead;
- `type -a snapshot` and `type -a undo` each resolve to exactly one command, timelike's.

## Key Entities

- **Workspace** — the directory a snapshot covers (FR-1 to FR-3), identified by its real path.
- **Store** — one per workspace per session, under the session scratch directory: the snapshot records
  and the content they refer to.
- **Snapshot** — identifier, reason, label, the workspace's real path, the entries captured (path, kind,
  content hash or link target, permission bits), the exclusions (path, size, reason), the counts and
  sizes, whether partial, and when it was taken.
- **Plan** — the list of `restore` and `remove` changes between the workspace now and a snapshot.

## Decisions (the seams and open points the send named, decided here on purpose)

**D-1 · Rule 9 against D7's "one undo command": the envelope reading.** Restore removes files, so it is
destructive and mutating. `undo` alone prints the confirmation envelope (exit 4), whose plan is the dry
run and whose `confirm` is `undo … --yes`. **The one undo command is `undo --yes`** (or `undo ID --yes`):
a single invocation that restores, which the agent can also run directly without the envelope first.
This keeps rule 9 whole, and since revision 10 made `confirm` the agent's own command, `undo --yes` is
exactly the habit rule 9 trains. No contract changes and no criterion is read more narrowly: the demo is
one command. Raised in FOR-MENTOR Item 17 for the mentor to confirm, not to block on.

**D-2 · The workspace.** The nearest ancestor containing `.git`, else the current directory (FR-1). Found
by walking parent directories in the tool itself, not by running `git`, so finding the workspace reads
no git configuration. Refused at `/`, the home directory, and their ancestors (FR-2), and when it would
contain the store (FR-3). The image's `WORKDIR` is the home directory, so `snapshot` from there is
refused with "change into the project directory". A project whose git top level is the home directory
itself (a dotfiles repository) is refused too: a home-directory snapshot is exactly what G1 rules out.

**D-3 · "Ignored-but-not-excluded".** "Ignored" is version control's: a file git ignores is captured like
any other. "Excluded" is defined here, and only here: the per-file limit, the size cap's largest-first
cut, non-regular files and unreadable files (FR-6). There is **no** built-in list of cache or build
directories: such a list would silently decide what a restore can bring back. A large `node_modules`
falls to the size cap's cut, which says so by name. `.git` is not "excluded": it is out of scope
entirely (FR-5). The verdict shows the exclusions.

**D-4 · The git-state boundary.** Nothing inside any `.git` is captured, restored, removed or followed
(FR-5, FR-20), at any depth (nested repositories included). Restore checks every parent component
before writing, so a symlink planted after the snapshot cannot redirect a write into `.git` or out of
the workspace.

**D-5 · The store does not use git — a departure from the stack's note, raised.** `tech-stack.md`
approves "git 2.40+ (snapshots, shadow store outside the workspace)". A git shadow store would fail
three of this feature's requirements as stated:
- **permission bits** (FR-4): git records only `100644` or `100755`, so a `0600` file or a `0700` script
  would come back as something else, and SC-2's byte-and-mode comparison would fail;
- **nested repositories** (FR-4, D-4): `git add` records a directory holding its own `.git` as a gitlink,
  not its files, so a nested project's working files would not be captured at all;
- **seam 5**: index writes fire `post-index-change` through 001's dispatcher, and keeping the project's
  hooks and configuration out needs overrides in every call.

The store here is a content-addressed copy store written in the interpreter's standard library (H5): it
runs no `git` command, so no hook can fire and no project configuration is read. stdlib Python is
approved, and no prohibited technology is used; but it departs from the stack's stated design for
snapshots, so it is **raised in FOR-MENTOR Item 17** for plan to confirm. It is not blocking: it changes
no contract and no criterion, and the store sits behind the two commands, so it can be replaced without
changing them.

*(Cycle 2.)* **Confirmed by discovery revision 11** (plan `0f6e1ed`;
`../bridge/feedback/07-20261003-022613-snapshot-store-and-persistence.md` § Resolution, option (a)).
`stack.md`'s Snapshots row now names this store, and plan adds a fourth reason against git: it tracks
no empty directories. Plan's four conditions, as checked in Cycle 2: blobs deduplicated by content
across snapshots (met as built); symlinks stored as links, never followed (met as built); the size cap
counted after deduplication (built in Cycle 2, FR-6); "taken" only after a restorability check (built
in Cycle 2, FR-9). The evidence is in `cycle-report.md` § Cycle 2.

**D-6 · Names (P3).** `snapshot` and `undo`: the words an agent uses for the act, and the words
coding-agent harnesses use for the same idea. Neither exists in the image (no Debian package installs
either). `undo` restores; `snapshot` takes and lists. Restore lives on `undo` alone, so the destructive
verb has one name.

**D-7 · Where snapshots live, and what survives.** In the session scratch directory
(`<scratch root>/<session>/snapshots/<workspace key>/`), the only place rule 10 lets a tool keep state.
Consequences, stated rather than hidden:
- **a container restart keeps them** (the scratch root is in the container's writable layer);
  **recreating the container loses them**, as it loses everything the agent has;
- they are **per session**: peer agents in the same workspace keep separate stores and cannot undo each
  other's work; a new `TIMELIKE_SESSION` starts with none (most runs use the default session).

A cross-session or cross-container store would need a state location the contract does not have yet
(rule 10's "project cache" is undefined). Not built in slice 0; noted in Item 17.

*(Cycle 2.)* **Confirmed by discovery revision 11.** Rule 10 now has two state locations: the
per-session scratch directory and a per-workspace state root outside the workspace; the in-workspace
project cache is withdrawn. Plan: *"Slice 0 stays as built. D-7's location is already outside the
workspace."* The state root, its volume, sharing between agents, purging by size and age, and the
restore-snapshots-first criterion all ride slice 1.

**D-8 · The caps.** Per snapshot: a size cap on stored content, a per-file limit, and an entry cap on the
walk. Defaults are set from a measured workspace in plan (research), each with its environment variable.
Beyond the size cap the snapshot is **partial** (FR-6), not refused, because a partial snapshot of the
source still recovers the source; beyond the entry cap it is **refused** (FR-7), because there is no
cheap partial walk. Either way the verdict names what was not snapshotted and why (T2).

**D-9 · Identifiers and listing.** Per-workspace integers (FR-11): short enough to type, stable,
deterministic. Listing is newest first, bounded by the output cap, with times only under `--verbose`.

**D-10 · An undo is undoable.** Before applying a restore, `undo --yes` snapshots the current state (FR-19),
so the agent can go back if it restored the wrong snapshot. This is the first use of a non-`on demand`
reason, which slice 1 extends.

## Revision 11 (Cycle 2, send `bridge/sends/07-rev11-20261004-030207.md`)

Prompt 07 moved from revision 1 to 11 under this spec. Revision 11 **added** one constraint and two
slice-1 criteria; it removed and reworded nothing (the prompt copies in `07-rev1-20261003-013915.md`
and this send differ only by those additions, the revision note and the frontmatter). Nothing this
body says became false, so the spec is not superseded. Recorded here, declared:

- **The constraint**, verbatim: *"Recovery state is kept per workspace, not per session, in the state
  root of feature 01's rule 10: it survives a new session, a container restart and a container
  recreate, and every agent working in the workspace can list and restore it; each snapshot records the
  session and agent that took it (P5; T2 bounds it by size and age)."* Its slice-0 part, that recovery
  state is kept outside the workspace and never inside it or its `.git`, holds as built (FR-23, D-7).
  The rest (per workspace, surviving sessions and recreation, shared, attributed, purged) is slice 1's.
- **Two criteria, carried, not built** (slice 1; out of scope for this send):
  - *"A snapshot taken in one session is listed and restorable from a new session, and after the
    agent's container is recreated"* *(slice 1)*;
  - *"A restore first snapshots the workspace, so the restore itself can be undone, and its verdict
    names that snapshot"* *(slice 1)*. D-10 already does this for `undo --yes` (FR-19, the verdict
    names `S`); slice 1 makes it a criterion and is not extended here.
- **Plan's conditions on the store** (D-5) are checked in Cycle 2: two held as built, two were built
  (FR-6, FR-9).

## Out of scope (slice 0)

Automatic snapshots before destructive commands, scheduled snapshots, the restorable trash, store
pruning by age or size, and incident replays (slices 1 and 2). Restoring file times or ownership. A
cross-session store (slice 1's per-workspace state root, discovery revision 11).

## Assumptions

1. The agent's projects live below its home directory, or anywhere else except `/`, the home directory
   and their ancestors. No workspace is mounted in this image yet (feature 13).
2. The agent owns the files it works on (uid 1000), so the tool can read every file it is asked to
   snapshot; an unreadable file is an exclusion, not a failure.
3. Permission bits are restored; owners and times are not (the agent cannot change owners, and times do
   not decide recovery).
4. A snapshot is consistent only if the workspace is not being changed while it is taken. Slice 0 does
   not freeze the workspace; a file that changes during the walk is recorded as read.
