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

- **FR-23** Snapshots live outside the workspace, in the per-workspace state root (rule 10, revision 11;
  FR-25), one store per workspace, shared by every session and agent working in it. Content is stored by copy, addressed by its hash, so identical content is stored once
  across snapshots. No hard links (an in-place edit would change the snapshot), no snapshotting
  filesystem and no container commit. *(Cycle 2: confirmed by discovery revision 11, which keeps the
  store's slice-0 location — outside the workspace — and moves it to a per-workspace state root in
  slice 1.)*
  *(Amended in Cycle 3, declared, by copy, as the Cycle 2 note anticipated: slice 0 read "in the
  session's scratch directory (rule 10), one store per workspace". Slice 1 moves the store to the state
  root; the rest of the requirement stands as written.)*
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
- **Store** — one per workspace, under the state root (FR-25), shared by every session and agent: the
  snapshot records and the content they refer to. *(Amended in Cycle 3, declared: slice 0 read "one per
  workspace per session, under the session scratch directory".)*
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

**D-7 · Where snapshots live, and what survives.** *(Superseded in Cycle 3 by D-11 and D-12: the store
is in the state root. The text below is slice 0's, kept as decided.)* In the session scratch directory
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

## Slice 1 (Cycle 3, send `bridge/sends/07-rev11-20261010-050829.md`; natural)

Added work on a body that stays true, recorded here, declared. One exception, which is the point of the
slice: FR-23 (and the Store entity, D-7) said the store lives in the session scratch, and is amended
above by declared copy. Revision 11 is already in `audited_against` (modify row 4); nothing is appended.

Slice 1's six criteria, verbatim from the send:
- *"A recursive delete, a hard reset with uncommitted changes, a force push, and a clean of untracked
  files each take an automatic snapshot before running, and the verdict names it"* _(slice 1)_ —
  **held for FOR-MENTOR Item 22** (Q1, Q2): how the guards reach `rm` and `git`.
- *"A directory removed by a script (not by the shell's delete command) is restorable from the most
  recent automatic or scheduled snapshot"* _(slice 1)_.
- *"A snapshot taken in one session is listed and restorable from a new session, and after the agent's
  container is recreated"* _(slice 1; revision 11)_.
- *"A restore first snapshots the workspace, so the restore itself can be undone, and its verdict names
  that snapshot"* _(slice 1; revision 11)_ — FR-19 already does this; re-established against the new store.
- *"Deleted files are moved to a restorable trash that is purged by age and size limits"* _(slice 1)_ —
  the trash's store, purge and restore are built here; **what feeds it is held for Item 22** (Q3).
- *DEMO: "the Agent runs a guarded destructive command, a snapshot is taken automatically, and the Agent
  restores from it"* (D16, Manual) _(slice 1)_.

### Scenarios (slice 1)

**Scenario 6: a script deletes a directory (criterion 2).** The agent runs `bash -c 'python3 tidy.py'`.
The shell's start finds the workspace's last scheduled snapshot older than the interval and takes one
(reason `scheduled`) before the command runs. The script removes `src/` with `shutil.rmtree`, which no
guard sees. The agent runs `snapshot list`, finds the scheduled snapshot, and `undo <id> --yes` brings
`src/` back, verified.

**Scenario 7: a new session, then a new container (criterion 3).** Agent A in session `s1` takes a
snapshot. Agent B, in session `s2`, runs `snapshot list` in the same workspace and sees it, with the
session and agent that took it (`--verbose`, JSON). The operator recreates the container
(`docker compose up --force-recreate`): the state volume outlives the container, and the snapshot is
still listed and restorable.

**Scenario 8: a plain `docker run`, no volume (seam 1).** The state root is then the container's own
directory. Every `snapshot` and `undo` verdict carries one line saying the recovery state is not
persistent and how to make it so. Nothing else changes.

**Scenario 9: the store fills (seam 8).** Each take ends with a purge of the state root: snapshots older
than the age limit go, then the oldest until the state root fits its size cap. The newest snapshot of
each workspace is never removed. The verdict names each snapshot it dropped.

### Functional requirements (slice 1)

**The state root (seam 1; rule 10 at revision 11)**
- **FR-25** Recovery state and caches live in the **state root**: `TIMELIKE_STATE_ROOT`, default
  `/var/lib/timelike`. It is read from the environment by timelike's own code (agentio), never from the
  agent's PATH or a workspace file (P002). Layout (data-model § State root): `VERSION` (the layout's
  version, P003), `workspaces/<key>/` (one store per workspace), `stamps/` (the scheduled snapshot's
  due times), `trash/`.
- **FR-26** The image creates `/var/lib/timelike` owned by `agent`, mode `0700`, so a fresh named volume
  mounted there takes that ownership on first mount (lore `docker-compose` Q003). `compose.yaml` mounts
  the named volume `timelike-state` there on the agent service only. Vanilla gets nothing (P6).
- **FR-27** **Persistence is stated, never implied (T2, P5).** The state root is **persistent** when it
  lies on a different filesystem from the container's root (`st_dev` differs from `/`'s): a named
  volume or a bind mount. When it is not, every `snapshot` and `undo` result (take, list, dry run,
  restore, refusals after the workspace check) carries the line
  `not persistent: <root> is not a mounted volume, so this recovery state dies with the container; mount
  one at <root> (compose.yaml: timelike-state)` (within rule 13's 200 columns at the default root), and
  JSON `data.state` = `{"root": …, "persistent": false}` (`true` otherwise, with no line). One line per
  result, every result: a per-session "first time only" would need state the warning is about.
- **FR-28** A state root that cannot be created or written is an error (exit 1) naming the path and
  `TIMELIKE_STATE_ROOT`. A state root inside the workspace is refused (FR-3, now naming
  `TIMELIKE_STATE_ROOT`).

**Keying (seam 2)**
- **FR-29** A workspace's store is keyed by its **real path** (the first 16 hex of its sha256, as in
  slice 0). A workspace mounted at the same path in a recreated container finds its snapshots. A
  workspace moved or mounted elsewhere is a different workspace: `snapshot list` and `undo` there say
  `0 snapshots` / `no snapshot`, and name every other workspace in the state root that has snapshots,
  with its path and count (`other workspaces with snapshots: <path> (<n>)`, up to the output cap), so a
  moved workspace is told where its history is. Nothing is written into the workspace to key it (rule 10).

**Slice 0's stores (seam 3)**
- **FR-30** On a workspace's first use of the state root (any `snapshot` or `undo`), every slice-0 store
  for the same workspace found under the scratch root (`<scratch root>/<session>/snapshots/<key>/`, any
  session this user can read) is **imported**: each record, in its old order, gets the next identifier,
  keeps its reason, label and time, and records `imported: {session, id}`; its objects are copied
  (deduplicated) and each imported record is verified as a take is. The old store is left in place
  with a file `imported` naming the new identifiers, so it is never imported twice. The result carries
  `imported <n> snapshots from session <s> (were <a>–<b>, now <c>–<d>)`. A record that fails
  verification is not imported and is named. Nothing a user took vanishes silently.

**Attribution (revision 11)**
- **FR-31** Every record names the `session` and `agent` (`TIMELIKE_AGENT`, or null) that took it.
  `snapshot list --verbose` shows them; JSON always carries them.

**The scheduled snapshot (seam 6, criterion 2)**
- **FR-32** At the start of an agent bash (`bash -c`, `bash -lc`, interactive; 001's hook paths),
  `/etc/timelike/shell-env.bash` decides with **builtins only** whether a scheduled snapshot is due:
  not for root; not when the workspace (the nearest ancestor of `$PWD` holding `.git`, else `$PWD`) is
  `/`, `$HOME` or an ancestor of either; not when the command line starts with `snapshot` or `undo`
  (a snapshot of the state the agent is about to inspect or restore would become the newest and hide
  the one it needs); not when `TIMELIKE_SNAPSHOT_INTERVAL` is `off`; and only when the workspace's stamp
  (`<state>/stamps/<encoded path>`, holding the epoch seconds of the last scheduled attempt) is older
  than the interval or absent. Only then does it fork, once:
  `/opt/timelike/libexec/scheduled-snapshot <workspace>` (absolute path, P002), synchronously, before
  the command runs.
- **FR-33** The helper writes the stamp first (so a failure is retried per interval, never per shell),
  takes a snapshot with reason `scheduled`, waiting at most 1 s for the workspace's lock (if another
  take or undo holds it, it skips), and is **silent on a complete snapshot**. A partial or refused
  snapshot prints one stderr line: `timelike: scheduled snapshot <id> of <ws> is partial: excluded <E>
  files (snapshot list; undo <id> --dry-run)` or `timelike: scheduled snapshot of <ws> refused: <why>`.
  It never changes the shell's command, its output or its exit code.
- **FR-34** `TIMELIKE_SNAPSHOT_INTERVAL`: seconds, default **300**, set from the measured cost (research
  R11); `0` = every shell start; `off` = never. A value that is neither is named by the helper's one line
  and read as 300.
- **FR-35** **Unchanged files are not re-read** (P2): each store keeps a stat cache (path → size,
  mtime, ctime, inode, sha256) from its last take. A file whose stat matches and whose object is in the
  store is recorded without being read. Verification (FR-9, stack note 12) still re-hashes every object
  the record names. The cost is measured and reported (research R11).

**Purge (seam 8)**
- **FR-36** Every take (on demand, scheduled, safety, and later the guards') ends with a **purge** of the
  state root, under the time bound `TIMELIKE_PURGE_SECONDS` (default 2): first, snapshots older than
  `TIMELIKE_SNAPSHOT_MAX_AGE_DAYS` (default 30; 0 = none); then, while the state root's stored bytes
  exceed `TIMELIKE_STATE_MAX_BYTES` (default 4 GiB; 0 = none), the oldest snapshot of any workspace.
  **The newest snapshot of each workspace is never removed.** Content no remaining record names is
  deleted. Another workspace's store is purged only if its lock is free at that moment; a busy store is
  skipped and said.
- **FR-37** The result names every snapshot it dropped (`purged: snapshot <id> of <ws> (<why>)`, bounded
  by the output cap, the full list in JSON `data.purged`). If the time bound or the newest-snapshot rule
  stops it above the cap, it says so with the bytes still over.

**Concurrency (seam 9)**
- **FR-38** FR-24's lock is per workspace store, shared by every session and agent (it was per session
  in slice 0). It is `flock(2)`, which the kernel releases when its holder exits, so a lock held by a
  process that no longer exists does not exist: there is no stale-lock state to clear. The lock file
  carries the holder's pid, session and agent, and the timeout verdict names them. Taking the purge's
  locks on other stores never waits.

**The trash (seam 7; criterion 5, fed per Item 22)**
- **FR-39** The trash lives in `<state>/trash/`: items (one record per deletion: the original absolute
  paths, kinds, modes, content hashes or link targets, when, session, agent, and the command that
  deleted them) and their deduplicated content. An item is written before the deletion happens.
- **FR-40** `undo --trash` lists the trash, newest first (`<id>  <n> files  <size>  <first path>[ and <k>
  more]`). `undo --trash ID --dry-run` lists what it would put back. `undo --trash ID --yes` puts every
  path of the item back where it was, verified by re-reading; a path that now exists is refused, named,
  and nothing is written. Without `--yes`: exit 4 and the confirmation envelope, as for a restore.
- **FR-41** The trash is purged on write by age (`TIMELIKE_TRASH_MAX_AGE_DAYS`, default 30) and size
  (`TIMELIKE_TRASH_MAX_BYTES`, default 1 GiB), oldest first, never the item just written, naming what it
  dropped. It is never emptied silently.

**Held for Item 22** (built after the ruling): what stands in front of `rm`, `git reset --hard` and
`git clean` (Q1); the `pre-push` record of a force push (Q2); what feeds the trash (Q3); their
announcement and `type -a` lines.

### Success criteria (slice 1)

One test per criterion, named after its distinguishing text, bats in the image per invocation style, and
pytest on the host where the host can reach it.
- **SC-6** *"A recursive delete, a hard reset with uncommitted changes, a force push, and a clean of
  untracked files each take an automatic snapshot before running, and the verdict names it"* — after
  Item 22.
- **SC-7** *"A directory removed by a script (not by the shell's delete command) is restorable from the
  most recent automatic or scheduled snapshot"* — a real Python script removes a directory with
  `shutil.rmtree` under `bash -c` and `bash -lc` with `TIMELIKE_SNAPSHOT_INTERVAL=0`; the scheduled
  snapshot taken at that shell's start restores it, compared by the test's own manifest (P004).
- **SC-8** *"A snapshot taken in one session is listed and restorable from a new session, and after the
  agent's container is recreated"* — another `TIMELIKE_SESSION` lists and restores it; then a throwaway
  container from the agent image, with a fresh named state volume and a named project volume, is
  removed and started again, and the snapshot is listed and restored, the content compared by the test.
- **SC-9** *"A restore first snapshots the workspace, so the restore itself can be undone, and its
  verdict names that snapshot"* — `undo --yes` names `S`; `undo S --yes` returns the workspace to the
  state the first restore replaced, compared by the test.
- **SC-10** *"Deleted files are moved to a restorable trash that is purged by age and size limits"* —
  the store, purge and restore through the helper now; through the guards after Item 22.
- **SC-11** D16, Manual: observed by the operator after the lane.

Further, from the decisions: the persistence line (FR-27) in a container without the volume and its
absence with it; import of a slice-0 store (FR-30); attribution (FR-31); purge never removing the newest
(FR-36); a stale-lock-free lock (FR-38); the scheduled hook's no-fork path (FR-32) and its measured cost.

### Decisions (the slice-1 seams; reasoning in `research.md` R10 to R16)

**D-11 · The state root's place.** `/var/lib/timelike`, outside every workspace and outside the agent's
home: a recursive delete under `~` (where projects live) cannot take the recovery state with it, and
`/var/lib/<name>` is where a service's persistent state belongs. Overridden by `TIMELIKE_STATE_ROOT`.

**D-12 · Persistence, every result.** A line on each result, rather than the first per session: the
first-per-session rule needs a record of having warned, kept where the warning says nothing persists.

**D-13 · Keying by real path.** Simple, collision-free in practice, writes nothing into the workspace.
It breaks on a remount elsewhere; FR-29 says so where it happens. Keying by something inside the workspace
(a marker file, a git config value) is refused by rule 10, and the root commit is absent outside git and
shared by every clone.

**D-14 · Import, not leave or ignore.** Leaving slice-0 stores would make a user's snapshots unreachable
from `undo`. Import keeps them reachable and leaves the originals in the disposable scratch.

**D-15 · A scheduled snapshot at shell start, no daemon (rule 10).** The send's natural reading. The
due check costs no fork; the cost when due is measured (R11) and bounded by the interval and FR-35.

**D-16 · Purge on write, time-bounded.** No schedule (no daemons). Age first, then size, never the
newest of a workspace, a busy store skipped rather than waited for (P2).

**D-17 · The lock.** Per workspace, `flock(2)`: a dead holder cannot hold it, so "stale" needs no rule
beyond naming a live holder.

**D-18 · The trash, fed per Item 22.** Its store, purge and restore are independent of what stands in
front of `rm`, and are built now through `/opt/timelike/libexec/guard trash-put`. The restore lives on
`undo` (`undo --trash`), so the destructive verb keeps one name (D-6).

**Carried into this cycle:** FOR-MENTOR Item 20 (`symbols` index to the state root, a second session
finds it warm); 001's rule 10 contract text (`output-contract.md`).
