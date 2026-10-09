# Impact Analysis: Modification to Feature 008 (edit)

Append-only: one section per modify cycle. Cycle 1 was built by `/specswarm:specify` and needs none.

---

## Cycle 2 — `bridge/sends/06-rev1-20261009-102433.md` (prompt 06 revision 1, discovery revision 15; slice 1)

**Feature:** Edit (`edit`). **Command:** `/specswarm:modify 008 --from-send bridge/sends/06-rev1-20261009-102433.md`,
run on `modify/008-slice-1`. The branch was cut from `master` at `ce1eaf2`, which is `bbb2c46` (the send's
base) plus one `reboot.md` commit. specswarm **4.0.1-botbaubble.2.40.0** was loaded: the expanded command
named that cache path. Written 2026-10-09T10:41:54Z (read from the clock).

### Provenance (modify Step 2)

The installed `provenance-inputs` and `provenance-row` blocks ran:
- `FEATURE_NUM 008`, from the branch; `PROMPT_VIA from-send`;
- `OLD_SOURCE` = `NEW_SOURCE` = `plan/.discover/prompts/06-edit.md`;
- `PROMPT_REV 1`, `AUDITED [1]`, `N 1`.

That is **row 4**: revision 1 is already audited, and Step 9 appends nothing. The slice-1 criteria were in
revision 1 from the start, marked *(slice 1)*. This is added work on a body that stays true, as the send
says. No re-specify, no regenerate.

### What this cycle changes

The send's slice-1 scope is three criteria (two Automated, one Manual):
1. An edit addressed by viewer anchors applies when the anchored lines are unchanged and is refused,
   naming the changed lines, when they are not.
2. An edit that would make a Python, TypeScript, Go, Rust or shell file fail its syntax check is refused
   with the checker's error, and the file is byte-identical.
3. DEMO D15 (Manual): the Agent's edit that would break the file's syntax is rejected with the error and
   the file is left unchanged.

Plus 008 Cycle 1's carried `not_verified`: `bash -lc` cells, the `type -a edit` cell, and the atomic
write's owner branch under a real second uid.

### Affected components

| Component | Impact | Notes |
|---|---|---|
| `tools/bin/edit` | High | `--at` (anchors), the syntax check, `--skip-syntax-check`, the manifest's new fields |
| `tools/libexec/syntax-check` (new) | High | The checker, run as a child of `edit` by `edit`'s own interpreter with `-I`; never on `PATH` |
| `tools/bin/view` | Low | `line_body()` factored out of `window()` so `edit` reuses view's line split as well as `anchor_of` (one definition, 006 FR-34). Output unchanged; `test_view*.py` is the regression |
| `image/Dockerfile`, `pins.env`, `compose.yaml`, `Makefile` | Medium | Four pinned wheels (the tree-sitter binding and the TypeScript, Go and Rust grammars) into timelike's interpreter, hash-checked; `/opt/timelike/libexec/syntax-check`. The vanilla image and the `runtimes` stage are untouched (RB1) |
| `make scan` | Low | No change: step 3 audits timelike's interpreter's site-packages, which now holds four distributions instead of none. Grype sees them through syft's SBOM |
| `.specswarm/tech-stack.md` | Low | The four packages under Approved Libraries, with the justification (the stack's rule for any addition) |
| Announcement, `timelike tools`, README command reference | Low | Regenerated from `--agent-info` and `--help` |
| Other features' contracts | None | No contract changes. `view`'s change is internal |

### Breaking changes: none

Everything is additive:
- `--at` and `--skip-syntax-check` are new flags;
- JSON gains a `syntax` object, and `level` gains the value `anchors`.

The exit-code set stays {0, 1, 2, 3}. One behaviour does change: an edit that slice 0 applied can now be
refused, but only when it would make a file of a checked language fail its check. That change is the
criterion.

### Risk

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| A grammar rejects valid modern syntax (a false refusal blocks the agent) | Medium for newly added constructs (measured: three cases in R10) | Medium | Only errors the edit **introduces** refuse. The refusal names the checker and its version. `--skip-syntax-check` exists, visible in the command (T4) |
| The checker hangs or crashes | Low | High (P2) | A child process with a 10 s limit, killed on expiry. The edit then applies, and the verdict says the check did not run |
| The wheels fail to install in the build | Low | Medium | Hash-checked with `--require-hashes`, and import-checked in the build. The build fails loudly |
| New packages bring vulnerabilities | Low | Medium | `make scan` step 3 audits them, and Grype covers them |

### Tech stack compliance

`stack.md` names the **tree-sitter CLI** (structural search, pinned). This cycle uses tree-sitter's
**Python binding and prebuilt grammar wheels** instead. The send allows that choice ("or why the Python
binding is the better carrier"), and research R9 gives the reasons:
- the CLI compiles grammars with a C compiler at first use, and the image has none;
- the wheels are prebuilt, and are pinned by hash.

Python and shell need nothing new: timelike's own interpreter and `/bin/bash` are their checkers. The
four packages are added to `tech-stack.md` § Approved Libraries with that justification.
