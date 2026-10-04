
### T001: image/rootfs/etc/timelike/standard-tools.json — the curated entries
**Started:** 2026-10-04T19:49:57Z | **Completed:** 2026-10-04T19:49:58Z

INHERITED: (none — first task)
FLAGGED: 20 entries over the classes research R4 names (pagers and editors, unbounded readers, REPLs, prompting commands, long or hanging runs, git) — chose data in the image over code, so an entry is a one-line change and the manifest's test reads the same file (confidence: high)
ASSUMED: `instead` for an editor is a non-interactive edit (sed -i or a heredoc); 06's edit tool is built later in this batch (008) and can be named here once it exists (confidence: medium)
ABSENT: entries for tools the image does not install — `installed` is computed at run time, so an entry for an absent tool still warns an agent that brings it
Verification: valid JSON, 20 entries, every field present
SCOPE: in (1 changed files)

### T004: timelike announce (generate, --write, --check) and timelike tools
**Started:** 2026-10-04T19:50:20Z | **Completed:** 2026-10-04T19:52:29Z

INHERITED: the curated file — from T001; 001's timelike (revision, bin dirs, TIMELIKE_REVISION hook) (confidence: high)
FLAGGED: subcommands of `timelike` (announce, tools), not new names on PATH — spec D-4 (confidence: high)
FLAGGED: a rule line in the announcement is written only when the tools it names are installed — chose that over static rules, so the announcement never names a tool that is not there (the drift FR-3 forbids, in the rules as well as the list) (confidence: high)
FLAGGED: tools/bin/view and tools/bin/search were committed as mode 100644 (006 Cycle 1); the image's COPY --chmod=0755 hid it, so the lane passed. The generator skips non-executables (correct), which is how it showed: 6 tools announced instead of 8. Fixed here (mode 0755), declared as changed_other_features (006) (confidence: high)
ASSUMED: a summary's whitespace is collapsed to one line (`" ".join(split())`), so a multi-line summary cannot break the one-line-per-tool layout (confidence: high)
ABSENT: placement (--install, --status) — T005; a placeholder refuses it with a usage error until then
Verification: ruff, format, mypy clean; on a fake bin dir with the 8 real tools: 23 lines, 8 tools, marker with the revision; --check equal → 0, a removed line → 1 "missing: undo"; tools: 8 timelike + 20 standard entries; plain `timelike` unchanged; test_conform*, test_view*, test_search: passed
SCOPE: in (3 changed files)
