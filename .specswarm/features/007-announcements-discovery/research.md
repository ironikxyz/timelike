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
