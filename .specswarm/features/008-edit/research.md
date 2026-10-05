# Research — 008 Edit (prompt 06, slice 0)

Each entry: decision, rationale, alternatives. Measured on the host (Python 3.12) unless it says otherwise;
the image (3.14.x) decides in the lane.

## R1 · Rule 9 for `edit`, and what this cycle changes outside 008 (spec FR-12)

- **Decision:** discovery revision 13's ruling, as code-track § Resume after pause-06 delivers it. `edit`
  declares `mutating: true`, `confirm_protocol: false`, and has `--dry-run`. It has no `--yes`.
- **`confirm_protocol` in 001's manifest** (restored from report 03 Appendix B: "true if mutating and
  honours --yes / exit 4 envelope"):
  - `agentio.Tool` gains `confirm_protocol: bool | None = None`. **`None` means "the same as
    `mutating`"**, so a tool written before revision 13 keeps rule 9 whole without a change. `undo`
    still says `confirm_protocol=True` explicitly, as the code track asks.
  - `confirm_protocol=True` without `mutating=True` is a programming error (`ValueError`, as an exit code
    outside the vocabulary already is).
  - `--yes` is added to the parser, exit 4 `confirmation required` to `codes()`, and
    `confirmation_required` to `envelopes()` **only when `confirm_protocol` is true**.
    `confirm_required()` raises when the tool does not confirm: it cannot print an envelope the manifest
    does not declare.
  - The manifest always carries `confirm_protocol`, and also `dry_run` (true exactly when `--dry-run`
    is among the flags). The ruling's wording is `dry_run: true`, so the manifest states it directly
    rather than leaving a reader to infer it from `destructive`.
  - `agent-info.schema.json` gains both properties, **not required**: absent `confirm_protocol` means
    `mutating`, absent `dry_run` means `"--dry-run" in flags`. This follows `envelopes`' precedent
    (revision 10), so a manifest written before them still validates.
- **`timelike-conform`, C2 (manifest)**, where the flags and `envelopes` checks already live:
  1. `--yes` is required in `flags` exactly when the tool confirms (`confirm_protocol`, or `mutating`
     when absent), and **forbidden** when it does not. A `--yes` that does nothing trains the reflex
     the ruling warns about.
  2. `confirmation_required` is in `envelopes` exactly when the tool confirms. Today the check says
     "exactly when mutating".
  3. `confirm_protocol: true` requires `mutating: true`.
  4. **The new rule:** `mutating: true` with `confirm_protocol: false` requires `dry_run: true` and
     `--dry-run` in `flags`. A manifest cannot say whether a tool overwrites or removes, so every
     mutating tool that does not confirm is held to it. A tool that only creates declares
     `mutating: false`, as `snapshot` does.
  5. `dry_run`, when present, agrees with `--dry-run` in `flags`.
  The negative case is a unit test: a manifest with `mutating: true`, `confirm_protocol: false` and no
  `--dry-run` fails C2, and the finding names the rule (quality-standards § Output contract, the bullet
  added at revision 13).
- **001's output contract** (`contracts/output-contract.md`): § Invocation surface's `--yes` row and
  § Confirmation gain revision 13's sentence and the three cases. 001's spec is not modified (it is
  UNAUDITED at 11–13, with no criterion changed; that stays the mentor's to route).
- **Who else changes:** `undo` (005) declares `confirm_protocol=True` (unchanged behaviour). `adele`
  (004) is not mutating; its grant envelope is untouched. No other tool is mutating. All of it goes in
  the cycle report's `changed_other_features`.
- **Alternatives:** `confirm: false` (a new field; the ruling says to restore the bundle's own); making
  `confirm_protocol` required in the schema (it would fail every manifest printed before it, for no
  safety gain, since absent already means the safe reading).

## R2 · Matching: three levels, and what each one tolerates (spec FR-3, FR-4; send seam 3)

The tolerance has to be exact, or "unique match" cannot be decided.

- **Level 1, exact:** `--old`, encoded as UTF-8, is searched for in the file's bytes. All
  non-overlapping occurrences are counted. A fragment within a line is fine.
- **Level 2, line endings:** both sides are normalised: CRLF and a lone CR become LF, and trailing spaces
  and tabs are stripped from every line. Then a substring search runs on the normalised text. An index
  map takes each normalised character back to its byte offset in the file. A fragment within a line is
  still fine at this level.
- **Level 3, indentation:** whole lines only. Indentation tolerance means nothing for a fragment that
  starts in the middle of a line. `--old`'s lines (normalised as at level 2) are compared with each run
  of the same number of consecutive file lines.
  - A pair of lines matches when the text after the leading whitespace is equal.
  - The leading whitespace must also map. All lines in the region share **one** mapping of the agent's
    unit (`a` spaces, or one tab) to the file's unit (`f` spaces, or one tab). Each line's level
    `k = len(lead_agent) / a = len(lead_file) / f` must be a whole number, and the same `k` on both sides.
  - Lines that are blank on both sides are skipped.
  - A line whose leading whitespace mixes tabs and spaces maps only if it is identical on both sides.
- **The units are inferred, not configured:**
  - **The file's unit:** a tab if the region's indented lines use tabs. Otherwise the GCD of their
    space counts.
  - **The agent's unit:** `a = f × (len(lead_agent) / len(lead_file))`, which must be one integer for
    every indented line.
  - **No mapping:** when all the region's lines are at level 0, level 3 is the same as level 2, and it
    does not run.
- **The deciding level is the first one with any match.** More than one match at that level is exit 3
  (FR-4), with all their line numbers. So two regions that differ only in indentation do not make an
  exact match ambiguous.
- **Not tolerated:** a difference inside a line (other than trailing whitespace), a difference in blank
  lines, Unicode normalisation, or a smart quote. Those are FR-5's candidates.
- **Alternatives:**
  - aider's fuzzy chain (a whitespace-insensitive match, then a SequenceMatcher match above a ratio). A
    match by similarity can apply an edit to a region the agent did not mean, which is a reach outside
    "named exactly" (revision 13, case 1).
  - Ignoring all whitespace. That makes `a b` match `ab`.

## R3 · Applying the new text in the file's conventions (spec FR-6)

- **Line ending:**
  - **Level 1:** `--new` is inserted as given (FR-6).
  - **Levels 2 and 3:** each LF in `--new` becomes the line ending of the **first line of the matched
    region** (CRLF, CR or LF). If the region has no line break, the file's most common ending is used.
- **Indentation (level 3):** each line of `--new` that is indented in the agent's unit becomes
  `k × file unit`, where `k = len(lead) // a`. The remainder (`len(lead) % a`, an alignment run) is kept
  as given. A line indented with tabs when the agent's unit is spaces is kept as given.
- **Trailing whitespace** in the replaced region (levels 2 and 3) goes with it. Lines around the region
  are untouched.
- **What is replaced:**
  - **Level 1:** exactly the matched bytes.
  - **Level 2:** the bytes from the first matched character to the last, mapped back.
  - **Level 3:** the whole lines, up to but not including the last line's ending, so the file keeps its
    own ending after the region.

## R4 · Nearest candidates (spec FR-5): measured, and bounded (P2)

- **Measured (2026-10-05, host):**
  - **Rejected,** `difflib.SequenceMatcher` over every same-length window: 2.8 s on 2,000 lines and
    28.7 s on 20,000 lines. The `quick_ratio` bounds prune almost nothing on source code, because every
    window has a similar character mix.
  - **Chosen, two stages:**
    1. Rank windows by the mean per-line token Jaccard of their aligned lines. Tokens are `\w+` runs and
       single punctuation marks, as sets per line, computed once.
    2. Rerank the top 20 with `SequenceMatcher.ratio()` on the joined text, with `autojunk=False`.

    On 2,000 lines this took 55 ms; on 20,000 lines, 240 ms; on 200,000 lines, 2.35 s. The planted
    region (one word misspelt on each of 5 lines) came first, with ratio 0.989.
- **Output:**
  - **The candidates:** at most 3 with ratio ≥ 0.5. Overlapping windows are suppressed: a window that
    overlaps a better one is dropped.
  - **Each candidate:** its line range and ratio, its lines numbered as `view` numbers them, and the
    detectable difference. That is the first of:
    - `line endings` (it would match at level 2, but level 2 did not run on that region);
    - `indentation` (the text after the indentation is equal, but no single mapping fits);
    - `trailing whitespace`;
    - `line N differs` (the first differing line, against `--old`'s line number).
- **Bound (P2):**
  - A deadline of 5 s for the candidate stage. Past it, the verdict says `candidates searched in lines
    1-N of M (time limit)`, and the candidates found so far are shown.
  - Files over 16 MiB are refused before matching (exit 1, `too large to edit`, with the size).
    `view`'s reading stops at nothing, but an edit holds the whole file in memory twice.
- **Alternatives:** `rapidfuzz` (not stdlib; H5); per-line SequenceMatcher (too slow, as for whole
  windows).

## R5 · Atomic write (spec FR-7; send seam 2)

- **Decision:**
  1. Resolve the path with `os.path.realpath`. An edit through a symlink edits its target, and the
     verdict says `via symlink`. A rename over the link itself would replace the link with a regular
     file.
  2. Read the bytes and their SHA-256.
  3. Refuse with exit 1 before writing, in each of these cases:
     - not a regular file;
     - binary (a NUL in the first 8 KiB, as `view`);
     - not writable by the agent (`os.access(W_OK)`). The directory may be writable, and then a
       rename would succeed and silently replace a file the agent cannot write;
     - larger than 16 MiB.
  4. `tempfile.mkstemp(dir=<target's dir>, prefix=".<name>.edit-")`. Write, `flush`, `os.fsync`.
  5. `os.fchmod` to the target's mode bits.
  6. `os.fchown` to the target's uid and gid when they differ from the temp file's. On `EPERM`, the
     owner cannot be kept, so the edit is refused with exit 1 and nothing is written. Changing a file's
     owner as a side effect is not an edit the agent named.
  7. **Concurrent-change check:** read the target again, and compare SHA-256 with step 2. If it
     differs, exit 1 (`changed since it was read`), and the temp file is removed.
  8. `os.replace(temp, target)`, then `fsync` the directory.
  On any failure, the temp file is unlinked in a `finally`.
- **Known limits, stated in the verdict and the docs:**
  - **A hard-linked file loses its link** (the rename makes a new inode), as with `sed -i`. When
    `st_nlink > 1`, the verdict notes `hard link broken (N links)`. Rewriting in place would break
    atomicity, and the send asks for it.
  - **Extended attributes and ACLs are not copied** (stdlib only, H5). That is noted in the docs, not
    checked.
- **Checked by hashes in the tests:** the SHA-256 in JSON (`sha256_before`, `sha256_after`) is computed
  by the tool, so every e2e test also hashes the file itself with `sha256sum` (P004: the claim is not
  the check).
- **Alternatives:** writing in place with `r+` (not atomic); a temp file in `/tmp` (the rename crosses
  filesystems and stops being atomic).

## R6 · Name, PATH and the image (spec FR-2)

- **Decision:** `tools/bin/edit`, copied by the Dockerfile's existing `COPY tools/bin/`. No image package
  changes, so `make scan`'s inputs are unchanged.
- **The `type -a` cell:** an e2e test asserts that `type -a edit` names exactly
  `/opt/timelike/bin/edit`. Debian's `mailcap` package installs `/usr/bin/edit` (a `run-mailcap`
  alias). The image does not install `mailcap`, and the cell keeps it that way.
- **The announcement (007):** `edit` appears in it automatically (`timelike announce` lists every
  executable in `/opt/timelike/bin`, from its `--agent-info` summary). That is one more line, and the
  60-line bound is checked by 007's own e2e. `view`'s usage already mentions `edit` (006 slice 1).

## R7 · Conformance probe

- **Decision:** `probe = ("/etc/os-release", "--old", "ID=", "--new", "ID=", "--dry-run")`.
  - It is read-only twice over: `--old` equals `--new`, so there is nothing to do (exit 0, `no change`).
    `--dry-run` writes nothing in any case.
  - It ends in one session event.
  - Conform runs it with `--json` and `--text`.
- **Alternatives:** a probe that edits a temp file (conform has no fixture directory for tools to
  write in).

## R8 · Testing

- **Units:** `tests/unit/test_edit.py`. They cover:
  - levels 1–3 and their uniqueness;
  - the indentation inference (spaces↔tab, 2↔4 spaces, the alignment remainder, mixed lines);
  - line endings (CRLF, CR, a mix);
  - candidates (ranking, the floor, overlap suppression, the deadline, simulated with a clock);
  - the atomic write: a concurrent change, made between the read and the rename with a hook; an
    unwritable file; a symlink; a hard link; mode kept;
  - BOM and non-UTF-8 bytes kept byte for byte;
  - `--old == --new`, an empty `--old`, a missing file, a binary file.
- **agentio and conform:** units in `tests/unit/test_agentio.py` and the conform tests:
  - `confirm_protocol`'s three values and its default;
  - `--yes` present only when the tool confirms;
  - `envelopes`;
  - the manifest fields;
  - C2's five checks, each shown failing on a manifest that breaks it.
- **e2e:** one bats file per criterion, named after its text, each under `bash -c` and `bash -lc`:
  - SC-1 to SC-5. The file's bytes are compared with `sha256sum` in the container, and the expected
    bytes are built by the test with `printf` (P005), never by `edit`;
  - the `type -a` cell and `edit --agent-info`'s `confirm_protocol: false`, in a contract file.
- **Fixtures:** generated by shell in the test (`printf` with `\r\n` and `\t`), independent of the tool.
