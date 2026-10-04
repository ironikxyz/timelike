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

