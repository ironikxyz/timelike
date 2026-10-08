# Contract — `timelike announce` and `timelike tools` (007, slice 0)

Both are subcommands of `timelike` (001), following the output contract.

```
timelike                       unchanged: revision, contract, tools on PATH
timelike announce              print the announcement (generated from the installed tools' manifests)
timelike announce --write P    write it to P (the image build: /etc/timelike/announcement.md)
timelike announce --check [P]  exit 1 naming each installed tool missing from P (default /etc/timelike/announcement.md)
timelike announce --install    place /etc/timelike/announcement.md at each harness's user-level file (entrypoint)
timelike announce --status     report each placement
timelike tools                 the manifest: timelike tools and curated standard tools
```

**Environment:** `TIMELIKE_ANNOUNCEMENT` (default `/etc/timelike/announcement.md`) is the file `--install`,
`--status` and `--check` read, and `--check`'s default. `TIMELIKE_STANDARD_TOOLS` is the curated file.
`TIMELIKE_BIN_DIRS` gives the tools (as `timelike` already reads it), and `TIMELIKE_REVISION` gives the
revision (001's test hook).

## The announcement

- Line 1, the marker: `<!-- timelike announcement: revision <REV>; generated from the tools' manifests; do not edit -->`.
- Then a title, `# timelike`, and one line naming the environment and the revision.
- `## Tools`: one line per executable in the bin directories (`TIMELIKE_BIN_DIRS`), in name order:
  ``- `NAME` — SUMMARY``, with SUMMARY from `NAME --agent-info`'s `summary`.
- `## How to work here`: the rules (spec FR-2), at most 6 lines.
- A closing line: the tools work the same whether or not this file is read (P7).
- **At most 60 lines.** Generation fails (exit 1) if over, or if any tool's `--agent-info` fails (naming it).
- `--check`: the tool names in the file's `## Tools` lines against the bin directories' executables.
  Exit 0 when equal; exit 1 with `missing: a, b` / `extra: c` in the verdict.

## Placement (`--install`, `--status`)

| Harness | Path |
|---|---|
| claude-code | `$HOME/.claude/CLAUDE.md` |
| codex | `${CODEX_HOME:-$HOME/.codex}/AGENTS.md` (shadowed when `AGENTS.override.md` is non-empty there) |
| opencode | `$HOME/.config/opencode/AGENTS.md` |

States: `placed` (written now), `current` (byte-identical to the announcement; untouched), `replaced`
(timelike's marker, but not identical: another revision, or a hand-edited copy; rewritten, since the
marker says do not edit), `not placed: <reason>` (someone else's file, or an
error), `shadowed: <path>` (Codex override). `--install` always exits 0, and its verdict counts the
states. `--status` changes nothing and exits 0. The JSON for both carries `placements: [{harness, path,
state, reason}]`. Directories are created with mode 0700. Files are written to a temporary file beside
them and then renamed, mode 0644.

## The manifest (`timelike tools`)

Entry: `{name, kind: "timelike"|"standard", installed: bool, summary, json, interactive_risk, instead}`.
- `json`: `yes` | `partial: <how>` | `no`.
- `interactive_risk`: `none` or a comma list of `pager`, `editor`, `prompt`, `repl`, `waits`, `unbounded output`.
- `instead`: a command, or `""`.

Text: one line per entry, `NAME  [timelike|standard]  json=…  risk=…  instead: …`. JSON: `tools: [...]`.
The verdict is `N timelike tools, M standard tools (K installed)`.
Curated entries come from `/etc/timelike/standard-tools.json` (`TIMELIKE_STANDARD_TOOLS` overrides it):
`{"v": 1, "tools": [{name, summary, json, interactive_risk, instead}]}`. A malformed file is exit 1, naming it.

## The entrypoint

`/opt/timelike/libexec/entrypoint` (POSIX sh): `timelike announce --install >/dev/null 2>&1 || true`,
then `exec "$@"`. The image's `ENTRYPOINT ["/opt/timelike/libexec/entrypoint"]`, `CMD` unchanged.

## Settled at implementation (gaps the unit delegate found)

- **Rules are conditional:** a "How to work here" line that names a tool is written only when that tool
  is installed, so the announcement never names one that is not (the spec's measurable outcome).
- **`timelike tools` text:** `  instead: …` is omitted when `instead` is empty. In the verdict,
  `(K installed)` counts the standard tools found on PATH.
- **`--status` and `--install` text:** one line per harness, `HARNESS: STATE[: REASON] — PATH`.
- **The curated file's `v`** must be 1; any other value is malformed (exit 1).

- **A placement's state and reason** are separate JSON fields: `state: "not placed"`, `reason: "…"`. The
  text line joins them (`not placed: …`).
- **Flags may follow the subcommand** (`timelike tools --text`, `timelike announce --check PATH`), as
  argparse reads them.
- **A failed `--check`** is a result on stdout (rule 10's outcomes are verdicts), exit 1, with `missing`
  and `extra` in JSON. It is not a stderr error.
- **`announce --json`'s `lines`** are the announcement's lines, the file's content line by line.

---

# Slice 1 (modify Cycle 3, send `bridge/sends/04-rev13-20261008-161802.md`; spec § Slice 1)

## The command-not-found answer (FR-14 to FR-17a)

**Where:** `command_not_found_handle`, defined in `/etc/timelike/shell-env.bash`. It is reached by `bash -c`,
`bash -lc`, interactive bash, and any bash script they run. It is **not** reached by `sh -c` or a direct exec.

**Behaviour:** stderr only. Exit 127. It reads nothing from stdin, installs nothing and forks nothing (bash
builtins only). It turns off `errexit`, `nounset` and `xtrace` locally, so a caller's `set -eux` neither breaks
it nor traces it.

**Line 1, always: bash's own line, byte for byte.**

| Shell | Line |
|---|---|
| non-interactive (`bash -c`, `bash -lc`, a script, `bash -s`) | `<where>: line <BASH_LINENO[0]>: <name>: command not found`, with `<where>` = the caller's `BASH_SOURCE[1]` when set, else `$0` (`bash -c '…' myname` → `myname`; a function defined in a `-c` string → `environment`, as bash says) |
| interactive (`$-` contains `i`) | `<base name of $0>: <name>: command not found` (bash prints argv0's base name: `/usr/bin/bash` → `bash`, `-bash` stays; settled at implementation, T015's finding) |

**Then, for a known name, one line per data row whose `name` equals the command's name, in file order:**

| `kind` | Line (`<note>` part omitted when the note is `-`) |
|---|---|
| `instead` | `timelike: instead: <value>  (<note>)` |
| `debian` | `timelike: <name> is in the Debian package <value>, which is not installed. The agent cannot install OS packages (no root): the operator adds <value> to the image.` |
| `user` | `timelike: install it yourself: <value>  (<note>)` (no rows ship until FOR-MENTOR Item 21 is answered) |

Two spaces separate the command from `(<note>)`. A name with no row gets line 1 alone.

**The data:** `/etc/timelike/missing-commands.tsv`, overridden by `TIMELIKE_MISSING_COMMANDS` (tests only).
- UTF-8. Lines starting with `#`, and empty lines, are ignored.
- Otherwise exactly four tab-separated fields: `name`, `kind` (`instead` | `debian` | `user`), `value`, `note`
  (`-` for none).
- An unreadable or missing file, or a directory at the path, means line 1 alone. A malformed line, or an unknown kind, is skipped.
- `name` is a command word: no `/`, no whitespace.

**Validity (unit test, on the shipped file):**
- every line well-formed;
- every `instead` value's first word is an executable in `tools/bin/`;
- each `debian` value is a plausible package name (`[a-z0-9][a-z0-9+.-]+`);
- no duplicate (name, kind, value).

**e2e:** no listed name resolves with `command -v` in the image.

## `timelike budget` (FR-20 to FR-23)

`timelike budget [--json]`. Usage line in `timelike --help`:
`timelike budget            memory, CPU, process and disk limits, and what is in use`.
Exit 0 whatever it could read: an unknown is a result. Usage errors exit 2, as for the other subcommands
(`--write` and the rest stay `announce`'s).

**Sources:**
- **The cgroup directory:** `TIMELIKE_CGROUP_ROOT` if set, else `/sys/fs/cgroup/<0:: path of /proc/self/cgroup>`,
  else `/sys/fs/cgroup` (`agentio.cgroup_dir()`, moved from `run`).
- **memory:** `memory.max`, `memory.current`, `memory.peak`.
- **pids:** `pids.max`, `pids.current`.
- **CPU:** `TIMELIKE_CGROUP_CPU_MAX` if set, else `<cgroup>/cpu.max`, for the limit; `TIMELIKE_PROC_STATUS` if set,
  else `/proc/self/status`, for `Cpus_allowed_list`. These are the hook's own test overrides, so one file feeds both.

**A figure** (JSON):
`{"state": "value"|"none"|"unknown", "value": <int|float|null>, "source": "<path>", "reason": <str|null>}`
- `none`: the file says `max`. `value` is null, and the text says `no limit`;
- `unknown`: the file is missing, unreadable or unparseable. `value` is null, and `reason` is
  `"<path>: <strerror or what was wrong>"`. The text says `unknown (<reason>)`. **Never 0.**

**CPU** (`agentio.cpu_figure()`, the hook's rule, spec FR-22):
- `limit`: a figure with `value` = quota ÷ period, rounded to 2 decimals (a float), plus `quota` and `period`
  (ints) when its state is `value`. `cpu.max` has the form `<quota|max> <period>`;
- `affinity`: the CPU count in `Cpus_allowed_list` (e.g. `0-3,8,10-11` → 7), or null when unreadable;
- `jobs`: `affinity` (0 when null); if ⌈quota ÷ period⌉ > 0 and (jobs = 0 or ⌈quota ÷ period⌉ < jobs), then
  jobs = ⌈quota ÷ period⌉; never below 1. This **must equal** the hook's `TIMELIKE_CPUS` on the same two files;
- `shell_value`: this process's `TIMELIKE_CPUS` as an int, or null when unset or not an int;
- `agrees`: `shell_value == jobs`, or null when `shell_value` is null.

**A disk:** `{"role": "workspace"|"scratch", "path": "<p>", "measured": "<p'>", "exists": <bool>,
"free_bytes": <int|null>, "total_bytes": <int|null>, "reason": <str|null>}`
- **workspace:** `path` = `agentio.workspace()`: the nearest ancestor of the real current directory holding a
  `.git` entry (lstat, not git), else the current directory (005 FR-1, moved from `snapshot`).
- **scratch:** `path` = `TIMELIKE_SCRATCH_ROOT` or `/tmp/timelike`.
- `measured` is `path` when it exists, else its nearest existing ancestor (`exists` false).
- `free_bytes` = `f_bavail × f_frsize`, `total_bytes` = `f_blocks × f_frsize`. When `statvfs` fails, both are
  null and `reason` is set.

**JSON `data`** (agentio puts these keys at the top level of the JSON object, beside `verdict` and `lines`; there is no `data` key, settled at implementation T017):
```
{"cgroup": "<dir>",
 "memory": {"limit": FIG, "current": FIG, "peak": FIG},
 "cpu": {"limit": FIG(+quota, period), "affinity": int|null, "jobs": int, "shell_value": int|null, "agrees": bool|null},
 "pids": {"limit": FIG, "current": FIG},
 "disks": [DISK(workspace), DISK(scratch)]}
```

**Text lines** (exactly five, in this order; sizes as `run`'s `size()`: below 1 KiB `N B`, else one decimal
with KiB/MiB/GiB/TiB):
```
memory: limit <L> · in use <U> · peak <P>
cpu: limit <C> · job count <J> (TIMELIKE_CPUS)[ · this shell has TIMELIKE_CPUS=<n>, <agrees|disagrees>]
processes: limit <L> · running <R>
disk, workspace <path>: <free> free of <total>[ (measured at <measured>; <path> does not exist yet)]
disk, scratch <path>: <free> free of <total>[ (measured at <measured>; <path> does not exist yet)]
```
- `<C>` is `1.50 CPUs`, `no limit` or `unknown (…)`. A count in processes is a plain integer.
- A disk with no statvfs prints `unknown (<reason>)` in place of `<free> free of <total>`.

**Verdict:** `memory <L>, cpu <C>, processes <L>; free: workspace <free>, scratch <free>`. When any figure or
disk is unknown, `; <n> unknown` is appended (n counts unknown memory, CPU-limit and pids figures plus disks
with no statvfs).

## The announcement (FR-24)

Two rule lines go after the `timelike tools` line, each emitted only when `timelike` is installed:
```
- `timelike budget`: this container's memory, CPU, process and disk limits, and what is in use.
- In bash, a command that is not installed says what to use instead, or who can install it.
```
