# Decisions Log — Feature 008
> Generated at 2026-10-05T04:51:40+00:00
> Spec: .specswarm/features/008-edit/spec.md

## Decision Key

| Tag | Meaning |
|-----|---------|
| ASSUMED | Assumption made without explicit spec guidance (confidence: high/medium/low) |
| DEFERRED | Decision postponed — noted for later resolution |
| FLAGGED | Judgment call between alternatives — requires review |
| ABSENT | What was NOT done and why — forced reflection on gaps |
| INHERITED | Assumption carried forward from a prior task's output |

---

Run: `/specswarm:implement --dispatch`, specswarm 4.0.1-botbaubble.2.35.0 (`4ff8dcb`). Blocks are run from
the installed `commands/implement.md`, not from the expanded text: this expansion again replaced awk's
`$0` with the command's argument (`--dispatch`) in `scope-tally` and `decision-tally`.
Checklists: requirements.md 16/16 after its FR-12 item was ticked (decided by discovery revision 13).
Pause file path (step 1e): `<repo>/../bridge/dispatch/pause-008.md` (the checkout path quoted as `<repo>/`, P2).
Process slip, corrected before any further commit: this initialising commit was first made without the
deny-list gate and carried the absolute pause path (P2, line 21). It was amended locally (never pushed).
Every later commit goes through the gate in the commit helper.

### T001: agentio confirm_protocol (revision 13); undo declares it; manifest confirm_protocol and dry_run
**Started:** 2026-10-05T04:52:03Z | **Completed:** 2026-10-05T04:56:52Z

INHERITED: discovery revision 13's ruling, via code-track § Resume after pause-06 and spec FR-12; research R1 (confidence: high)
FLAGGED: `Tool(confirm_protocol=None)` with None meaning "the same as mutating" — chose a default that keeps rule 9 whole for every tool written before revision 13 over a default of False, which would have silently dropped `undo`'s confirmation had its declaration been missed (confidence: high)
FLAGGED: `--yes`, exit 4's "confirmation required" and `confirmation_required` in `envelopes()` now follow `confirm_protocol`, not `mutating` — a `--yes` that does nothing is refused as an unknown flag (exit 2), so the reflex the ruling warns about has nothing to land on (confidence: high)
FLAGGED: the manifest gains `dry_run`, equal to `destructive` (the parser adds `--dry-run` exactly then) — chose stating the ruling's own field over leaving a reader to infer it from `destructive` (confidence: medium)
ASSUMED: `confirm_required()` needs no new guard: `_emit_result` already refuses an envelope whose status is not in `tool.envelopes()` (internal error, exit 1), and `envelopes()` now follows `confirm_protocol` — a unit shows it (confidence: high)
ABSENT: the schema and conform changes — T002/T003; tasks.md's "confirm_required() raises" is met by that existing refusal rather than a raise inside it
Verification: 5 new units in tests/unit/test_agentio.py (default, edit's shape, the undeclared envelope, the ValueError, dry_run); test_agentio.py 72 passed; whole unit suite on the host 1315 passed; ruff, format, mypy clean
SCOPE: in (3 changed files)

### T002: timelike-conform C2 — the confirmation-scope checks (revision 13), each shown failing
**Started:** 2026-10-05T04:57:40Z | **Completed:** 2026-10-05T04:59:28Z

INHERITED: `confirm_protocol` and `dry_run` in the manifest, absent meaning `mutating` and "--dry-run in flags" — from T001 (confidence: high)
FLAGGED: the checks live in C2 (the manifest), not in a new C10 — they are properties of the manifest, beside the flags and envelopes checks that already were there; C9 still checks every exit-4 output, and `declared_envelopes` now defaults by `confirms()` (confidence: high)
FLAGGED: every mutating tool that does not confirm must declare `dry_run: true` with `--dry-run` — the ruling binds "when it overwrites or removes", and a manifest cannot say which; a tool that only creates declares mutating false (snapshot's shape) (confidence: medium)
FLAGGED: `--yes` offered by a tool that does not confirm is a C2 failure — chose refusing it over tolerating it, so a `--yes` never appears where it would do nothing (confidence: high)
ABSENT: a separate C-number and its catalogue entries (C2 keeps its rule list "5, 6"; the C2 finding names rule 8 and revision 13 in its text)
Verification: 7 new cases in tests/unit/test_conform_violations.py (edit's shape passes; no dry run, --yes without confirming, confirm without mutating, dry_run disagreeing with the flags, an envelope from a non-confirming tool, a non-boolean — each C2 and only C2); test_conform.py and test_conform_violations.py 63 passed; ruff, format, mypy clean
SCOPE: in (2 changed files)

### T003: 001's contracts — schema (confirm_protocol, dry_run), output contract § Confirmation (revision 13), conformance C2
**Started:** 2026-10-05T04:59:56Z | **Completed:** 2026-10-05T05:00:31Z

INHERITED: the manifest fields and their "absent means" defaults — from T001; C2's five checks — from T002 (confidence: high)
FLAGGED: both new schema properties are optional, with "absent means" in their descriptions — chose that over required, following `envelopes` (revision 10), so a manifest printed before revision 13 still validates (confidence: high)
FLAGGED: `conformance.md`'s C2 row also changes (not named in tasks.md's T003, which lists the schema and output-contract.md) — its text described the old "--yes if mutating" rule and would have been false after T002 (confidence: high)
ASSUMED: 001's spec.md is not modified: it is UNAUDITED at 11–13 with no criterion changed, and routing it is the mentor's (research R1) (confidence: high)
ABSENT: a change to `confirm-envelope.schema.json` — the envelope itself is unchanged; only which tools may print it
Verification: the schema parses as JSON; test_agentio.py (which validates manifests against it, the new edit-shaped one included) 72 passed. Host conformance over all 8 shipped tools (installed with the venv interpreter, scratchpad conform-all.sh): pass — undo with confirm_protocol true, the others false
SCOPE: in (3 changed files)

### T006: tools/bin/edit — three match levels, the file's conventions, atomic write, after-view, dry run, candidates
**Started:** 2026-10-05T05:02:18Z | **Completed:** 2026-10-05T05:06:54Z

INHERITED: `confirm_protocol=False` and the manifest's `dry_run` — from T001; C2's rule for that shape — from T002; the contract, research R2–R7 and data-model (confidence: high)
FLAGGED: level 2 is a substring search over the file with endings as LF and trailing whitespace stripped, mapped back per line (so a fragment inside a line still matches); level 3 is whole lines only — chose that split because indentation tolerance means nothing mid-line (R2) (confidence: high)
FLAGGED: a uniform base dedent is NOT tolerated (agent's lines at levels 0/1/0 against the file's 1/2/1): FR-3 asks for one consistent unit mapping per line level, and a base offset would be a wider, undeclared tolerance. Seen in a host smoke run of D6's shape: the refusal shows the region as the nearest candidate with difference "indentation", and the edit with the indentation as `view` shows it applies, CRLF and tabs kept (od -c). For the D6 demo: an agent that copies with its base indentation succeeds first time; one that dedents gets the candidate (confidence: medium)
FLAGGED: `--old == --new` answers "no change" before uniqueness is checked — nothing is written either way; and the probe uses `PRETTY_NAME=` (the contract's `ID=` also occurs inside `VERSION_ID=`: found by the T004 delegate from the contract). R7 and the contract amended (confidence: high)
FLAGGED: the dry-run diff is the body (`lines`), not a `data.diff` copy; an ending-only change is a verdict addition (`line endings: X → Y`), not a tag in the diff — contract amended before the delegates wrote assertions (confidence: high)
FLAGGED: the owner is kept by fchown, and when that is not permitted the edit is refused (exit 1) rather than written with a changed owner (R5) (confidence: medium)
ASSUMED: a BOM shows in the numbered lines as `view` shows it (checked: `view --text` on a BOM file prints the bytes EF BB BF before line 1's text) (confidence: high)
ASSUMED: argv text reaches the file as the shell passed its bytes (`os.fsencode`, surrogateescape) (confidence: high)
ABSENT: a hook to force a concurrent change in a test — the re-read-and-compare runs on every write but no unit forces the race; an extended-attribute or ACL copy (stdlib only, R5); several edits in one call (slice 0 scope)
Verification: tests/unit/test_edit.py (T004's 57) all pass against this tool; 14 failed on the first run, settled as tool deviations from the contract (12: wording of four verdicts, line_ending at level 1, the endings note, the 16 MiB phrase, the undecodable-bytes note, the dry-run verb, the probe) or test errors (2: BOM display, probe value), each recorded under T004; host conformance over all 9 tools: pass (edit included); timings on the host: the probe 81–84 ms, a no-match over 20,000 lines 254 ms, a near-miss 151 ms; ruff, format and mypy (strict) clean
SCOPE: in (1 changed files)

### T004: tests/unit/test_edit.py (delegated); 14 first-run failures settled
**Started:** delegated,_written_after_9294a5a_(its_start_was_not_read_from_a_clock) | **Completed:** 2026-10-05T05:07:14Z

INHERITED: the contract (contracts/edit-cli.md, amended once while it worked: the diff in `lines`, endings in the verdict), research R2–R8, and test_view.py's and test_snapshot.py's harness (confidence: high)
FLAGGED: written blind to the tool, from the contract; it ran only after T006 landed. 14 of 57 failed on the first run: 12 were tool deviations from the contract, fixed in tools/bin/edit (four verdicts carried an extra "; nothing written" or a level phrase the contract does not give, `line_ending` was null at level 1, the endings note did not fire for LF inserted into a CRLF line, "16.0 MiB" for "16 MiB", the "N undecodable bytes kept" note was missing, the dry run said "would edited", the probe); 2 were test errors, fixed here (a BOM shows in the numbered lines as `view` shows it — checked against `view`; the probe value after R7's correction) (confidence: high)
FLAGGED: the delegate's contract finding — the probe `ID=` also occurs inside `VERSION_ID=`, so it would exit 3 — was right, and changed R7 and the tool (confidence: high)
ASSUMED: the delegate's settlements of contract ambiguity are kept as written: the scope's shape only (`lines S-E of T`), exact verdicts only on multi-line edits, similarity within 0.01 of its own SequenceMatcher (confidence: medium)
ABSENT: a forced concurrent change, the 5 s deadline itself, an owner that cannot be kept (needs a second uid), the `line endings` / `trailing whitespace` candidate differences (unreachable: such a window matches at level 2), and `--limit` cutting the diff — named by the delegate as not tested
Verification: 57 passed; ruff and format clean
SCOPE: in (1 changed files)

### T005: e2e — SC-1 to SC-5 and the name and manifest (delegated), 28 cells, run on a host stand-in
**Started:** delegated,_written_after_9294a5a_(its_start_was_not_read_from_a_clock) | **Completed:** 2026-10-05T05:44:18Z

INHERITED: the contract as amended once while it worked (the diff in `lines`, endings in the verdict), helpers.bash, and the 006/007 files' layout (confidence: high)
FLAGGED: every cell makes its own directory with `mkdir` (no `-p`) and its own file — the lesson of lane batch-a's 007 cell (two cells sharing one 0444 copy) applied before the lane, not after (confidence: high)
FLAGGED: SC-5's expected diff is GNU `diff -u --label a/FILE --label b/FILE` over CR-stripped copies, an engine independent of the tool's difflib (P005) (confidence: high)
FLAGGED: run here before the lane on a host stand-in (scratchpad only, not committed): bats-core v1.11.1 cloned, and a `docker` stub that runs `exec` locally against tools/bin installed with the venv interpreter, maps the image's interpreter to the venv's, and turns `bash -lc` into `bash -c` (the host's /etc/profile resets PATH). Result: 26 of 28 ok; the 2 not ok are the `type -a` cells, which named the stand-in's path instead of /opt/timelike/bin/edit — image-only by design. This is not image evidence: the -lc cells ran as -c, and the image's interpreter, PATH and user are not the host's (confidence: high)
ASSUMED: the delegate's settlements are kept: a one-line verdict in either form, the header scope asserted by prefix only, the level-3 phrase by its parts, SC-4's difference containing "line 2" (confidence: medium)
ABSENT: tty and pty cells — edit is a non-interactive file tool and the criteria name no terminal mode; the contract's rule-1 JSON default under a pipe is what the notty cells exercise
Verification: shellcheck -x clean over the six files; 28 @tests; host stand-in 26/28 as above; no test directory left under /tmp after the run
SCOPE: in (6 changed files)

### T007: pyproject (ruff, mypy lists), Makefile (shellcheck list), README (an edit section)
**Started:** 2026-10-05T05:07:23Z | **Completed:** 2026-10-05T05:44:37Z

INHERITED: tools/bin/edit — from T006; the six e2e files — from T005 (confidence: high)
FLAGGED: committed after T005 rather than with T006, so the Makefile never names a file the tree lacks (confidence: high)
ASSUMED: the README's examples are the tool's real phrasing (checked against the host runs in T006: "edited lines 3-6 of 8 (matched ignoring line endings and indentation (4 spaces = 1 tab))") (confidence: high)
ABSENT: a Status bullet for 006/007/008 — the Status section lists features 001–004 only; bringing it up to date is not this task's
Verification: ruff and format clean; mypy (project config, now 22 files with edit) clean; shellcheck over the whole SHELLCHECK_FILES list clean, every listed file present
SCOPE: in (9 changed files)

### T008: host lane — lint, units with coverage, make test-host, conformance, start-up; edit's internals tested in process
**Started:** 2026-10-05T05:44:49Z | **Completed:** 2026-10-05T05:58:07Z

INHERITED: every earlier task's files; the coverage rc of reboot.md with 007's `tl/` path (confidence: high)
FLAGGED: tools/bin/edit was at 85% in the first traced run (the merge bar is 90% per language, which the total met at 94%). 27 in-process tests were added to tests/unit/test_edit.py for paths a subprocess cannot force — a concurrent change (`_reread` patched), an owner that cannot be kept (`fchown` raising EPERM, and another errno), no temp file possible, a directory that cannot be synced, a FIFO, an unreadable stat, view absent for the binary type, the candidate deadline (a deadline already past), `infer_mapping`'s twelve cases, level 2 ending mid-line and on a newline, level 3 with and without --new's final newline, a file with no line ending — and for the tool's own correctness, not the figure: all passed first time, so no tool change (confidence: high)
FLAGGED: T007's SCOPE line says "9 changed files": its start was recorded at e3deffc, before T005's commit, so its range included T005's six e2e files. T007 itself changed pyproject.toml, Makefile and README.md (`git diff --name-only 38d5b77 a5d2b0e`); all in scope either way. The record is left as written (append-only) and corrected here (confidence: high)
ASSUMED: the host stand-in run of the e2e files (T005) is advisory evidence for the files' logic only, never for the image (confidence: high)
ABSENT: the Docker lane (make test, make scan) — no daemon here; the mentor's lane after the batch
Verification:
- units under coverage (venv Python 3.12.3, pytest 8.4.2): 1405 passed, 1 skipped, 524 s; coverage line and branch: TOTAL 95%; tools/bin/edit 96%, agentio 94%, timelike-conform 93%, snapshot 92%
- make test-host: passed (units 1406 passed untraced; files 60/60; hook logic 29/29)
- lint: ruff 0.16.7 check and format (65 files) clean; mypy 2.4.0 strict over the project's 22 files clean; shellcheck 0.11.0 over the Makefile's SHELLCHECK_FILES (50 files, every one present) clean
- conformance on the host (all 9 tools installed with the venv interpreter): pass, edit included
- start-up on the host, 20 runs each, every exit asserted 0: `edit --help` p50 79 / p95 82 ms; the probe (`--dry-run`, no change) p50 79 / p95 81 ms; budget < 100 ms p95
SCOPE: in (1 changed files)

### T009: cycle-report.md § Cycle 1, implement step 10, .specswarm/metrics.json, the marker
**Started:** 2026-10-05T05:58:19Z | **Completed:** 2026-10-05T05:59:23Z

INHERITED: every task's record; the step-10 output of the installed blocks; the host-lane figures — from T008 (confidence: high)
FLAGGED: Group B copies the send (`discovery_revision: 12`), and the prose names revision 13 as delivered through code-track § Resume after pause-06 — the Resume section's instruction, over writing 13 into a copied field (confidence: high)
FLAGGED: every criterion `unconfirmed`, the D6 Manual one included; the host stand-in run of the e2e files is reported beside the citations as evidence for the files, and changes no mode (confidence: high)
ASSUMED: `delegations: []` — the two test writers were subagents, not sibling features (the send's definition) (confidence: high)
ABSENT: `demo_points_reached` (the mentor derives it); a lane result (no Docker here)
Verification: six citations, each `grep -cF` = 1 in the send; tallies from the installed blocks; step 10's output pasted verbatim; metrics.json gains only the 008 entry
SCOPE: in (1 changed files)

---

# Cycle 2 — slice 1 (send `bridge/sends/06-rev1-20261009-102433.md`; specswarm 4.0.1-botbaubble.2.40.0)

### T010: Pins and the image (R9)
**Started:** 2026-10-09T10:48:31Z | **Completed:** 2026-10-09T10:50:02Z

INHERITED: research R9's carrier (binding plus three grammar wheels in timelike's purelib; Python by compile, shell by bash -n) and the four hashes, read from PyPI's JSON for the exact wheel files on 2026-10-09 and matching sha256sum of the downloaded files — from plan (confidence: high)
FLAGGED: into timelike's interpreter's **purelib**, not a separate --target directory, chose purelib because make scan's step 3 (pip-audit) already lists and audits exactly that directory, so the scan sees the wheels with no change to scan/ (the send: "expect make scan to see it"); a separate directory would have needed a scan change and an import path (confidence: high)
FLAGGED: eight pins.env keys (version and SHA-256 per wheel) over one requirements lock file, because pins.env is "every pinned image and version, in one place" and the build already takes every pin as a build argument; the Dockerfile writes the requirements file from them (confidence: high)
ASSUMED: uv 0.12.19's `pip install --target --require-hashes --no-deps --only-binary :all:` fetches the cp314 manylinux wheel whose hash is pinned; only the lane's build can show it (confidence: medium)
ASSUMED: the build has network for PyPI, as it does for nodejs.org and the npm registry today (confidence: high)
ABSENT: an image build — no Docker here; the lane builds it. The Dockerfile's new RUN is unverified until then
ABSENT: bench/vanilla/Dockerfile and the runtimes stage — untouched by design (RB1); test_the_two_runtimes_stages_are_identical still passes, and a new test asserts the vanilla Dockerfile names no tree-sitter
Verification: tests/unit/test_agent_runtimes.py 91 passed (venv Python 3.12.3, pytest 8.4.2), with 13 new cases (pins, ARG, compose, hash-only install, vanilla clean); `make -p` reads the 8 new keys; `set -a; . ./pins.env` sources clean
SCOPE: in (4 changed files)

### T013: Anchors — view's line_body factored out; edit --at (R11, FR-13 to FR-17)
**Started:** 2026-10-09T10:50:02Z | **Completed:** 2026-10-09T10:52:04Z

INHERITED: R11's decisions (ends only; a move refused naming where; --at with --old a usage error), and edit's existing loader for view (`_view()`) — from plan (confidence: high)
FLAGGED: `line_body()` factored out of view's `window()` (a 006 file), over a copy of its three lines in edit, because FR-34's promise is one definition, and the split is half of it; output unchanged (test_view.py and test_view_slice1.py: 131 passed). Declared for changed_other_features (confidence: high)
FLAGGED: a "past the end" anchor whose bytes occur exactly once elsewhere is reported as a move ("line 40 is now line 6"), not as past the end, chose the move because it gives the agent the one command that works; the contract's "past the end" stays for anchors found nowhere (confidence: medium)
ASSUMED: anchors' lines split on \n only, as iterating a binary file splits them for view; edit's own numbering (split on CR too) is used for the shown region after an edit, so a CR-only file would number differently in the two — not a case in the criteria (confidence: medium)
ABSENT: interior anchors of a range are not checked (the form carries the ends; R11)
ABSENT: the syntax check on anchored edits — T015 adds it to both paths
Verification: a lab smoke run (applied range on a mixed CRLF/LF file with B's ending kept and A's ending given to --new; changed end exit 3; a move exit 3 with the --at to rerun; delete; two usage errors exit 2); test_edit.py 84 passed; ruff check and format clean on edit and view
SCOPE: in (2 changed files)
