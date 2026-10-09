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

- **Decision:** `probe = ("/etc/os-release", "--old", "PRETTY_NAME=", "--new", "PRETTY_NAME=", "--dry-run")`.
  - **Corrected during T006:** the first choice, `ID=`, also occurs inside `VERSION_ID=`. The test
    delegate found it from the contract. `--old == --new` now answers `no change` before uniqueness is
    asked, since nothing is written either way, and the probe uses a key that occurs once.
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

---

# Slice 1 (Cycle 2, send `bridge/sends/06-rev1-20261009-102433.md`)

Measured on the dev host (Python 3.12.3, the cp312 binding wheel; the grammars are abi3 and are the same
wheels as the image's) on 2026-10-09, unless an entry says otherwise. The image (CPython 3.14.7, the cp314
binding wheel) decides in the lane.

## R9 · The checkers, and how they arrive without a compiler (send seam 1; spec FR-19)

- **Decision:** three checkers, all timelike's own and none on the agent's `PATH`.
  - **Python:** the compiler of timelike's own interpreter: `compile(src, name, "exec",
    ast.PyCF_ONLY_AST, dont_inherit=True)`, with warnings ignored. It parses and runs nothing. It is
    CPython 3.14.7, the same version as the agent's runtime (`PYTHON_VERSION`), so it is the language's
    own judgement of the language the agent runs.
  - **Shell:** `/bin/bash -n` with `--norc --noprofile`, in an environment without `BASH_ENV`. It is
    bash's own parser, and with `-n` it reads and runs nothing.
  - **TypeScript, TSX, Go, Rust:** tree-sitter, through its **Python binding** (`tree-sitter` 0.26.0,
    the cp314 manylinux wheel) and **prebuilt grammar wheels** (`tree-sitter-typescript` 0.23.2,
    `tree-sitter-go` 0.25.0, `tree-sitter-rust` 0.24.2; abi3 manylinux, MIT). A tree with an `ERROR` or
    `MISSING` node is a syntax error at that node.
- **How they arrive:**
  - Each wheel is pinned in `pins.env` by version and by the SHA-256 PyPI publishes for that exact file.
    The four hashes were checked on 2026-10-09 against `pypi.org/pypi/<name>/<version>/json`.
  - The build installs them with `uv pip install --target <purelib> --require-hashes --no-deps
    --only-binary :all:` into **timelike's interpreter's site-packages**, where `agentio` already lives.
  - The build then imports each grammar and parses one line, and fails loudly otherwise.
  - The image has no C compiler, and the wheels need none.
- **Why the Python binding and not the CLI** (the send's "or why the Python binding is the better
  carrier"):
  - `tree-sitter parse` loads a grammar by compiling its `parser.c` with the host's C compiler on first
    use (or emscripten for wasm). The image has neither, and adding one is a toolchain.
  - The binding loads prebuilt shared objects from wheels pinned by hash, so it needs no compiler.
  - It also runs inside the checker's own process, so one child holds all three grammars, with one
    time limit and no per-file process.
- **Why Python and shell are not tree-sitter:**
  - **Python:** measured, the tree-sitter Python grammar (0.25.0) accepts `def f():\nreturn 1` (an
    `IndentationError` to CPython). It cannot be exact about indentation. The interpreter's compiler is
    exact, and it is already in the image.
  - **Shell:** `bash -n` is bash's own grammar, and it is already in the image.
  - So two of the five languages need nothing new, and the image gains three grammars, not five.
- **Why not each language's own checker** (`tsc`, `gofmt`, `rustc`; the send's option b): each is a
  large new toolchain, and none is named in `stack.md`. That would be Item 22. It is not needed:
  tree-sitter is in the stack, and a wrong refusal is bounded by R10 and R12.
- **Where it lives:** the wheels go in timelike's interpreter, never the agent's (`/opt/agent`) and never
  the vanilla image, so bench parity (RB1, FR-13, P6) is untouched. The `runtimes` stage, which must be
  identical in both Dockerfiles, is untouched too.
- **`make scan`:** step 3 lists timelike's interpreter's distributions. It now finds four, so pip-audit
  audits them where it reported "no third-party packages". Syft's SBOM, and Grype over it, see them as
  Python packages. Nothing in `scan/` changes.

## R10 · Which way each checker errs (send seam 2), measured

Fixtures were written by hand from each language's documented syntax, independently of the checker (P005).

| Language | Checker | Valid modern syntax accepted | Valid syntax wrongly refused (false error) | Invalid syntax missed |
|---|---|---|---|---|
| Python | CPython 3.14.7 compiler | all (by definition, for 3.14) | none (by definition) | none |
| shell | bash `-n` | all bash | none for bash. A `#!/bin/sh` script is checked as bash, which accepts some bashisms dash rejects (errs toward not refusing) | bashisms in a sh script |
| TypeScript | tree-sitter-typescript 0.23.2 (2024-11) | `satisfies`, `using`/`await using`, `const` type parameters, `accessor`, decorators, import attributes, `infer … extends`, template literal types, `override`, `asserts`, private `#x in`, abstract constructor types | **`export type * from`** (TS 5.0), **`in out` variance annotations** (TS 4.7) | not measured |
| TSX | the same, TSX grammar | JSX, `<T,>` generic arrows | as TypeScript | — |
| Go | tree-sitter-go 0.25.0 (2025-08) | generics, constraints with `~`, generic aliases, range over int, `iter.Seq`, `min`/`max`/`clear` | none found | none found |
| Rust | tree-sitter-rust 0.24.2 (2026-03) | let chains, async closures, `unsafe extern`, raw lifetimes, `use<'a>`, `&raw const`, inline `const {}`, C strings, `let … else`, `#[unsafe(…)]` | **`safe fn` in `unsafe extern` blocks** (Rust 1.82) | not measured |

**Grammar versions against the languages:** each grammar predates its language's newest syntax.
- tree-sitter-typescript 0.23.2 is from 2024-11, when TypeScript 5.7 was current.
- tree-sitter-rust 0.24.2 is from 2026-03.
- tree-sitter-go 0.25.0 is from 2025-08. Go's syntax has not changed since 1.22's range over int.

**How the cost is bounded:**
- R12 refuses only an error the edit **introduces**. A false error therefore costs exactly the edit
  that adds the unsupported construct, never edits elsewhere in a file that already uses it.
- The refusal names the checker and its grammar version (FR-22), so the agent can judge whether the
  checker or its text is wrong.
- `--skip-syntax-check` (R14) lets the agent override it, visibly in its own command.

**Compiler confirmation (lore P005):**
- **Python and shell:** the checker is the language's own parser.
- **Go:** confirmed by `gofmt -e` in `GO_IMAGE`, the lane host's Go toolchain, from the e2e runner when
  `GO_IMAGE` is set. Otherwise the cell says it was skipped and why.
- **TypeScript and Rust:** **not confirmed**. Neither the dev host nor the lane host has `tsc` or
  `rustc`. Node 22 on the dev host has no type stripping under `--check`. The image's Node 24 is not
  relied on for it.

## R11 · Anchors in `edit` (send seam 7; spec FR-13 to FR-17)

- **The form:** `--at N:hhhhhh` or `--at A:aaaaaa..B:bbbbbb`, with `--new`. It is the form `view --anchors`
  prints (006 FR-34), so the agent copies two tokens from one view.
- **One definition** (006 FR-34's promise):
  - `edit` calls `view.anchor_of` and `view.line_body`, loaded from the `view` beside it (the loader
    `edit` already has for `file_type`);
  - `line_body` is factored out of `view.window()` (strip `\n`, then one `\r`) with no change in
    `view`'s output, and `test_view_slice1.py` is the regression;
  - lines are split as `view` splits them: on `\n`, as a binary file's iteration does. A CR-only file is
    one line to both;
  - so the anchor `edit` computes is the anchor `view` printed, by construction.
- **Ends only:** the form carries the two ends, so `edit` checks the two ends. An interior line changed in
  place, with the line count unchanged, is not detected. Anything that inserts or deletes lines inside
  or above the range moves the end anchor and is detected. The verdict says what was checked. Asking
  for every interior anchor would make the common call long, for a case `--dry-run` shows anyway.
- **`--at` with `--old`:** a usage error. Two addressing modes in one call would need a rule for what
  happens when they disagree, and the slice does not need one.
- **A moved line is refused, naming where it moved.**
  - Applying at the new place would usually be right, but the agent's `--new` was composed against a
    view that is now stale: lines above changed, and the agent has not seen how.
  - P2's verdict names the cause, and slice 0's `do instead:` gives the one command that succeeds
    (`--at` at the new numbers).
  - The criterion's words fit too: line 42, as addressed, no longer holds those bytes, so line 42
    changed. The verdict says it moved rather than that it was edited.
  - A move is recognised only when both ends are found at the same shift and each occurs once
    elsewhere. An ambiguous move (the anchored line is `}` and occurs often) is reported as changed, with
    `view --anchors` as the way on.
- **The stale refusal** shows lines A−3 to B+3 as they are now, in `view --anchors`'s format, so the next
  call can copy fresh anchors from it.

## R12 · An already-broken file (send seam 3; spec FR-21)

- **Decision:**
  - **A clean original** refuses any error in the result. A missing `}` reported at the end of the file
    is still caught.
  - **A broken original** refuses only a result error that lies inside the lines the edit writes and
    whose identity (message plus the text of its line, stripped) is not among the original's errors.
- **Why not a count:** CPython's compiler and `bash -n` report the **first** error only. A count is 0 or 1
  for them and cannot see a second error. For tree-sitter, error recovery after an edit can split or
  merge `ERROR` nodes far from the edit, so a count or a full set comparison refuses repair steps that
  introduced nothing.
- **Why "inside the lines written":** a repair that fixes the first error and uncovers the next (hidden
  until then by first-error-only checkers) must not be refused. The uncovered error lies outside the
  written lines. An error inside them is one the agent just typed.
- **Why identity is text, not line number:** an edit above an existing error shifts its line number. The
  same message on the same line text is the same error.
- **Which way it errs:** toward applying (seam 2's preference). The verdict always says the file still
  fails, and where, so nothing is silent.

## R13 · The checker's own failure, and its limit (send seam 5; spec FR-24)

- **A child process:** `edit` runs `libexec/syntax-check` with `subprocess.run([sys.executable, "-I",
  CHECKER, LANGUAGE], input=…, timeout=10)`. Two things follow:
  - a grammar that crashes (a segfault in a shared object) or loops takes the child down, never `edit`;
  - the limit is a wall-clock kill, which an in-process parse cannot offer for `compile()`.

  The child is started in its own session and killed with its group at the limit (`run`'s pattern), so
  a hung `bash -n` cannot outlive it.
- **The limit: 10 s.**
  - A 200,000-line Python file parses in 1.07 s with tree-sitter on the dev host (measured).
  - `compile()` and `bash -n` are faster per byte, and `edit` refuses files over 16 MiB anyway.
  - 10 s is ten times the measured worst case, and well inside any harness's command timeout.
- **Fail open** (seam 5's first choice): a missing checker, a crash, a missing grammar or the limit lets
  the edit apply, with `syntax: not checked (checker failed: REASON)`.
  - A check that did not run knows nothing about the file.
  - Refusing would turn timelike's fault into the agent's blocked work (P2: the checker's failure is
    not the file's).
  - T4 forbids **silently** removing a check. The verdict and JSON say it did not run, and why.
- **The write stays atomic:** the result is computed, then checked, then written by FR-7's path.
- **Start-up cost:** one child per edit of a checked language, measured by T013 in the host lane:
  - the interpreter's start;
  - the binding's import, for tree-sitter languages only;
  - the parse.

  Unknown languages and `--skip-syntax-check` start no child.

## R14 · The skip (send seam 6; spec FR-25)

- **Decision:** `--skip-syntax-check` exists.
- **Why add one:** R10 measured three valid constructs that the grammars refuse. Without a skip, an agent
  writing `export type * from` has no path but `sed -i`, which is the bash-only fallback this tool
  exists to replace (P1).
- **T4's terms are met:**
  - the skip is in the agent's own command, so it appears in the session event's `args` (agentio
    records argv);
  - the verdict says `syntax: skipped (--skip-syntax-check)`, and JSON `syntax.status "skipped"`;
  - the refusal names the checker and its version, and its `do instead:` never names the flag. A unit
    asserts the flag's name appears in no refusal.
- **Its name:** spelled out, so it reads as what it does in a transcript.

## R15 · Language detection (send seam 4; spec FR-18)

- **By extension:**
  - `.py` and `.pyi` (stubs are Python syntax) are Python;
  - `.ts`, `.mts` and `.cts` are TypeScript: the ESM and CJS variants have the same syntax, and differ
    only in module resolution;
  - `.tsx` is the **TSX grammar**. JSX and TypeScript's angle-bracket casts conflict (`<T>x`), so a
    `.tsx` file parsed as TypeScript fails on its JSX, and the reverse;
  - `.go` is Go, `.rs` is Rust, and `.sh` and `.bash` are shell.
- **By shebang, for an extensionless file only:** the first line's interpreter is matched, directly or
  through `env` (including `env -S`):
  - `python`, `python3` or `python3.N` is Python;
  - `bash` or `sh` is shell (checked by `bash -n`: R10).
- **An extension wins over a shebang:** a `.py` file with a bash shebang is still Python, as editors treat
  it.
- **Not in the five** (`.js`, `.json`, `.c`): unknown, so `not checked (language unknown)`. Adding a
  language is a grammar wheel and a table row.

## R16 · Carried from Cycle 1 (spec FR-28)

- **`bash -lc` cells:** each slice-0 e2e file gains them. Debian's `/etc/profile` resets `PATH`, and
  profile.d restores it (001 R1). The `type -a edit` cell under `bash -lc` is the one that can catch
  `mailcap`'s `/usr/bin/edit` shadowing ours.
- **The owner branch under a real second uid:**
  - as root (`docker exec -u 0`), the test creates a file owned by uid 1001, mode 0666, in a directory
    the agent owns;
  - the agent's edit cannot `fchown` the temporary file to 1001 (EPERM), so it is refused with
    `cannot keep FILE's owner (uid 1001, …); nothing written`;
  - the test reads the hash before and after.

  If the lane's `docker exec` cannot run as root, the cell is skipped, and says that the owner branch
  stays unverified.
