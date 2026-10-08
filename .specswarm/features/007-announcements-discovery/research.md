# Research — 007 Announcements and discovery (prompt 04, slice 0)

## R1 · Where each harness reads user-level context (send seam 1)

From each harness's own documentation, read 2026-10-04:
- **Claude Code:** `~/.claude/CLAUDE.md`, user memory, loaded for every project ([docs](https://docs.anthropic.com/en/docs/claude-code/memory)).
- **Codex CLI:** in its home, `$CODEX_HOME` (default `~/.codex`), it reads `AGENTS.override.md` if that
  file exists and is non-empty, otherwise `AGENTS.md` ([docs](https://developers.openai.com/codex/guides/agents-md)).
  An override therefore shadows the announcement, which `--status` reports.
- **OpenCode:** `~/.config/opencode/AGENTS.md`, global rules. It falls back to `~/.claude/CLAUDE.md`
  unless that is disabled ([docs](https://opencode.ai/docs/rules/)).

None is verified against a running harness here: no harness runs in this container. The D4 demo is
where reading is observed.

## R2 · When to place it (seam 1, D-2)

The agent image has no volume (compose), so writing into `/home/agent` at build would be present at
start. But an operator mounting a home, a future state-root volume (07 slice 1), or a harness recreating
its directory would hide or remove build-time files. An entrypoint that places the files on every
container start is correct in all those cases, and costs one short process per start. It runs as
`agent` (the image's `USER`), under `init: true`'s docker-init, and `exec`s the command, so the
container's PID tree is unchanged.

## R3 · The 60-line budget

There are 8 tools in `tools/bin` as of this branch (`adele`, `run`, `search`, `snapshot`, `timelike`,
`timelike-conform`, `undo`, `view`; counted with `ls`), one line each, and later features in this batch add more. The header,
the rules and the closing take about 14 lines, which leaves room for about 40 more tools. The generator
fails at build if the result exceeds 60 lines, so the bound is checked, not hoped.

## R4 · Curated standard tools (FR-11)

The entries cover the classes discovery names as traps:
- the pager and editor traps of 001;
- the unbounded readers 006 replaces;
- REPLs and prompting commands (rule 4);
- long or hanging runs that 003's `run` concludes.

Each entry's `instead` is a timelike tool or a standard non-interactive form (`python3 -c`,
`npm init -y`, `git --no-pager`). The list is data in the image (`standard-tools.json`), not code, so
adding an entry is a one-line change, and the manifest's test reads the same file.

---

# Slice 1 (modify Cycle 3, send `…-161802`)

## R5 · What bash prints for a missing command, and how a handler can print the same (seam 2, FR-15)

Probed on host bash 5.2.21 (the image's trixie bash is 5.2.37; the e2e compares in the image):
- no handler, `bash -c 'true; x'`: `bash: line 1: x: command not found`; with a newline before it, `line 2`;
- a script `d/s.sh`: `d/s.sh: line 2: …`. `bash -c 'x' myname`: `myname: line 1: …`. A function defined in a
  `-c` string: `environment: line 1: …`. `bash -s` from stdin: `bash: line 2: …`;
- interactive (`bash -i`, also `-il`): `bash: x: command not found`, with no line number;
- `sh -c x` (dash): `sh: 1: x: not found`.

bash's prolog is `get_name_for_error()`: when non-interactive, `BASH_SOURCE[0]` of the failing context, else
`$0`. Then `line <executing_line_number>`. Inside the handler that context is `BASH_SOURCE[1]` (index 0 is the
hook file), and the line is `BASH_LINENO[0]`. Measured, every case above matches: `SRC=[hook d/s.sh] L=[2 0]` →
`d/s.sh: line 2`; `SRC=[hook environment] L=[1 1]` → `environment: line 1`; `SRC=[hook] L=[1]`, `$0=bash` →
`bash: line 1`. Since bash 4.0 the handler runs in a subshell, so its exit status (127) is the command's.

## R6 · The data's shape and size (seam 3, FR-16, D-8)

- **Debian's `command-not-found`** needs `apt-file` contents, fetched over the network and indexed as root. The
  agent has no root and the image does not change after build. Not used.
- **A JSON section in `standard-tools.json`** would need a process to read, on every typo. Not used.
- **A TSV read by `while read`** forks nothing. At about 100 lines, its cost is in plan § Measurements.

The set covers the commands agents reach for that the slim image lacks, from two sources:
- the curated traps (`standard-tools.json`) that are absent here;
- the common Unix tools trixie-slim does not install (`tree`, `rg`, `jq`, `curl`, `wget`, `less`, `vim`, `file`,
  `unzip`, `zip`, `make`, `gcc`, `rsync` …), each checked against Debian's package name.

It grows by one line per answer, and an e2e cell keeps every listed name absent from the image.

## R7 · Installs, the runtimes and recovery (seams 1, 4 and 5) — see FOR-MENTOR Item 21

- **The image** has timelike's interpreter (`-I`, never the agent's), `uv`, and no agent `python3`, `pip`, `node`
  or `npm`.
- **Pinned `uv` 0.12.19 as an ordinary user** (host, throwaway home): `uv python install 3.14.7 --default` puts
  `python`, `python3` and `python3.14` in `~/.local/bin` in 2.9 s. That Python is `EXTERNALLY-MANAGED` and has
  `python3 -m pip` (26.2.1) but no `pip` executable.
- **Recovery:** with no repository, the workspace is `~`, which 005 refuses to snapshot. `verify changed` needs
  git. Inside a repository, `~/.local` is outside the workspace. So installs are undone by their own uninstall
  (FR-19).

## R8 · The budget's sources (seam 6)

- `run` already reads `memory.max` and `.peak` under `cgroup_dir()` (`tools/bin/run:369–437`) and `statvfs`
  (`:507`). 001's hook computes `TIMELIKE_CPUS` from `cpu.max` and affinity (`shell-env.bash:76–117`).
- `memory.peak` exists from Linux 5.19. `pids.max` and `pids.current` come with the pids controller, which Docker
  enables.
- **Moving the readers into `agentio`** gives `run`, `budget` and the hook rule one Python home. The hook stays bash
  (no fork at shell start), so agreement is tested, not shared: the same files go to both.
