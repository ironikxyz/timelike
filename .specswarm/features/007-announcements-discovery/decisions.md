
### T001: image/rootfs/etc/timelike/standard-tools.json — the curated entries
**Started:** 2026-10-04T19:49:57Z | **Completed:** 2026-10-04T19:49:58Z

INHERITED: (none — first task)
FLAGGED: 20 entries over the classes research R4 names (pagers and editors, unbounded readers, REPLs, prompting commands, long or hanging runs, git) — chose data in the image over code, so an entry is a one-line change and the manifest's test reads the same file (confidence: high)
ASSUMED: `instead` for an editor is a non-interactive edit (sed -i or a heredoc); 06's edit tool is built later in this batch (008) and can be named here once it exists (confidence: medium)
ABSENT: entries for tools the image does not install — `installed` is computed at run time, so an entry for an absent tool still warns an agent that brings it
Verification: valid JSON, 20 entries, every field present
SCOPE: in (1 changed files)
