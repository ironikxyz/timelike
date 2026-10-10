# Data model — 008 Edit (prompt 06, slice 0)

`edit` keeps no state. These are its in-memory shapes, plus the manifest fields this cycle adds to 001.

## Source (one read of the file)

| Field | Meaning |
|---|---|
| `path`, `abs_path` | As given, and `realpath` (the file written) |
| `raw` | The bytes, read once (≤ 16 MiB) |
| `sha256` | Of `raw`; compared again just before the rename (R5) |
| `st` | `os.stat` of the real file: mode, uid, gid, nlink |
| `lines` | `raw` split after each line ending, endings kept (`b"…\r\n"`, `b"…\n"`, `b"…\r"`, or a last line without one) |
| `ending` | The most common ending, used when a region has none of its own |

## Match

| Field | Meaning |
|---|---|
| `level` | `exact` · `line_endings` · `indentation` (R2) |
| `byte_start`, `byte_end` | The bytes replaced in `raw` |
| `line_start`, `line_end` | 1-based lines of the old region |
| `mapping` | Level 3 only: `(agent_unit, file_unit)`, each `("space", n)` or `("tab", 1)` |
| `region_ending` | The first matched line's ending (R3) |

Matches are found at one level. **Several** matches at that level are a refusal (exit 3). **Zero** matches
at every level lead to `Candidate`s.

## Candidate

| Field | Meaning |
|---|---|
| `start`, `end` | Lines; the window is as long as `--old` |
| `similarity` | `SequenceMatcher.ratio()` on the joined text, ≥ 0.5 (R4) |
| `difference` | `line endings` · `indentation` · `trailing whitespace` · `line N differs` |
| `lines` | Numbered as `view` numbers them |

## Edit result

| Field | Meaning |
|---|---|
| `new_raw` | `raw[:byte_start] + converted_new + raw[byte_end:]` |
| `start`, `end`, `total` | The new text's lines in the new file, and the new line count |
| `shown` | Lines `start-3` to `end+3`, numbered, `>` on the new text's lines |
| `sha256_before`, `sha256_after` | `sha256_after` is null on a dry run and when nothing changed |
| `diff` | Dry run only: the unified diff lines |

## Manifest fields (001's schema; R1)

| Field | Type | Absent means | Set by |
|---|---|---|---|
| `confirm_protocol` | boolean | equal to `mutating` | `agentio.Tool(confirm_protocol=…)`; default `None` → `mutating` |
| `dry_run` | boolean | `"--dry-run" in flags` | `agentio`: true exactly when the parser has `--dry-run` (`destructive`) |

**Invariants that conform checks (C2):**
- `confirm_protocol` ⇒ `mutating`.
- `--yes` ∈ `flags` ⇔ the tool confirms.
- `confirmation_required` ∈ `envelopes` ⇔ the tool confirms.
- `mutating ∧ ¬confirm_protocol` ⇒ `dry_run ∧ --dry-run ∈ flags`.
- `dry_run` (when present) ⇔ `--dry-run` ∈ `flags`.

| Tool | mutating | confirm_protocol | dry_run |
|---|---|---|---|
| `edit` | true | **false** | true |
| `undo` | true | true (explicit) | true |
| every other tool | false | false | as now (`destructive`) |

---

## Slice 1 (Cycle 2; spec FR-13 to FR-27)

Nothing is stored. Per call:

| Entity | Fields |
|---|---|
| **Anchor spec** (`--at`) | `start: (line, anchor)`, `end: (line, anchor)`; A ≤ B; anchor = `view.anchor_of(view.line_body(raw_line))`, lines split on `\n` as `view` does |
| **Anchor check** | `changed: [{line, expected, now \| null}]`, `moved_to: {start, end} \| null`; applied only when `changed` is empty |
| **Syntax check** | `language` (`python`, `shell`, `typescript`, `tsx`, `go`, `rust`, or null), `checker`, `status` (`ok`, `refused`, `skipped`, `not checked`, `already failed`), `errors`, `original_errors`, `reason` |
| **Syntax error** | `line` (1-based, in the text checked), `column` (1-based, or null for `bash -n`), `message`; identity for R12 = `(message, stripped text of line)` |
| **Written lines** | `S-E`: the new text's lines in the result, as FR-8 reports them; for a deletion, the line it collapsed to |

**Order of an edit** (P2: whole or not at all):
1. read;
2. address (`--old` levels, or `--at`);
3. compute the result;
4. check (child, ≤ 10 s);
5. on a refusal, return it (exit 1), with nothing written;
6. otherwise write it atomically (FR-7), or print the dry run.
