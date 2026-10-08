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
