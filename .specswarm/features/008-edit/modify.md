# Modification: Feature 008 — Edit (`edit`)

Append-only: one section per modify cycle.

---

## Cycle 2 — `bridge/sends/06-rev1-20261009-102433.md`

**Status:** Active | **Created:** 2026-10-09 | **Impact analysis:** `impact-analysis.md` § Cycle 2 |
**Spec:** `spec.md` § Slice 1 | **Contract:** `contracts/edit-cli.md` § Slice 1

### Summary

Build slice 1 (natural):
- edits addressed by `view --anchors`'s `N:hhhhhh`;
- a syntax check for Python, TypeScript, Go, Rust and shell, which refuses an edit that would introduce
  a syntax error and leaves the file byte-identical;
- the three items carried from Cycle 1's `not_verified`.

Provenance is row 4, so there is nothing to audit.

### Functional changes

- **F001: anchors** (spec FR-13 to FR-17). `edit FILE --at N:hhhhhh[..M:hhhhhh] --new TEXT` replaces those
  lines whole when both anchored ends are unchanged. Otherwise it exits 3, naming each changed line and
  showing the current lines with their anchors. A pure move is named, with the command that would apply
  it. The anchor is `view`'s own `anchor_of` over `view`'s own line split. **Breaking:** no.
- **F002: the syntax check** (FR-18 to FR-26). Each language gets a checker:
  - Python: timelike's interpreter's compiler;
  - shell: `bash -n`;
  - TypeScript (and TSX), Go and Rust: tree-sitter.

  The check runs in a child process with a 10 s limit. Only errors the edit introduces refuse it (exit 1),
  with the checker's message and the lines around it. A checker that fails lets the edit apply and says
  so. `--skip-syntax-check` is visible in the command, and no refusal suggests it. **Breaking:** an edit
  that breaks a checked file's syntax is now refused, which is the criterion.
- **F003: carried** (FR-28). `bash -lc` cells, the `type -a edit` cell under `bash -lc`, and the owner
  branch under a real second uid.

### Data model changes

None stored. JSON gains `syntax` (`status`, `checker`, `language`, `errors`, `reason`), and `anchors` in
anchor mode (data-model § Slice 1).

### API/contract changes

- New flags: `--at`, `--skip-syntax-check`.
- `level: "anchors"`.
- Manifest extras: `syntax_checkers`, `syntax_time_limit_s`, `anchor_form`.
- Exit 1 and exit 3 descriptions widened, with the same set of codes.

### Testing strategy

- **Regression:** `tests/unit/test_edit.py`, `test_view*.py`, the six slice-0 e2e files (which gain
  `bash -lc` cells).
- **New units**, written from the contract by a delegate (P005: fixtures and anchors computed by the
  test).
- **New e2e**, one per criterion:
  - `edit-anchored-lines-unchanged-applies-changed-lines-refused-naming-them.bats`;
  - `edit-would-fail-syntax-check-refused-with-checker-error-file-byte-identical.bats`.
- **Carried:** `edit-slice-0-carried-items.bats` (owner branch, `type -a` under `bash -lc`).

### Tech stack compliance

Compliant, with four approved additions (tree-sitter and three grammars, pinned by hash), entered in
`tech-stack.md`. No prohibited technology.
