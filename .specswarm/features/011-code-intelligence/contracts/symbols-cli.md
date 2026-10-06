# CLI contract — `symbols` (011, slice 1)

`symbols` follows 001's output contract:
- the header `symbols: <target> [<scope>]`, then `verdict: …`;
- JSON when stdout is not a terminal;
- `--json`, `--text`, `--limit`, `--verbose`, `--help` (≤ 40 lines), `--agent-info`;
- one session event per call, and rule 13 on lines.

**Every verdict ends with the cache state:** `; cache: fresh`, `; cache stale: N files changed, M
removed; rebuilt`, or `; cache: built (N files)`.

```
symbols outline FILE
symbols def NAME            (NAME or Outer.NAME)
symbols callers NAME
symbols dependents FILE [FILE…]
```

## Manifest

| Field | Value |
|---|---|
| `mutating` | `false` |
| `confirm_protocol` | `false` |
| `destructive` | `false` |
| `reads_stdin` | `false` |
| `probe` | `["outline", "/opt/timelike/bin/symbols"]` |
| `exit_codes` | `0` answered · `1` the index could not be read or written · `2` usage · `3` not found · `124` the index walk hit its limit |
| extra | `languages: {"python": "exact", "javascript": "text-based", "typescript": "text-based", "go": "text-based", "rust": "text-based", "shell": "text-based"}`, `index: "<scratch>/<session>/symbols/<key>.json"` |

## outline

```
symbols: app/models.py [14 definitions, exact (python)]
verdict: 14 definitions in app/models.py (exact: python syntax tree); cache: fresh
 12-48   class    class Order(Base)
 30-41     method   def save(self, force: bool = False) -> None
 …
```

- **Each line:** `START-END`, the kind, then the signature, indented two spaces per nesting level.
- **Bodies:** never shown.
- **Data:** `path`, `precision`, `definitions: [{name, qual, kind, start, end, sig, depth}]`.
- **A missing file:** exit 3.

## def

```
symbols: save [3 definitions, exact (python)]
verdict: save is defined in 3 places; best first: app/orders.py:30 Order.save; cache: fresh
app/orders.py:30   method   Order.save   def save(self, force: bool = False) -> None
…
```

- **The first body line is the best definition.**
- **Data:** `definitions` (ranked, as above, with `path`, `line`, `precision`) and `ranking` (the stated
  order).
- **Not found:** exit 3, scope `not found`, verdict `no definition of NAME in N indexed files`, with
  `do instead: search -w NAME`.
- **The scope** is `exact (python)`, `text-based` or `mixed`, whichever applies to the definitions shown.

## callers

```
symbols: save [3 call sites, text-based]
verdict: 3 call sites of save in 2 functions and the top level (text-based: name matches followed by "(", not resolved calls; comments and strings excluded for Python only); cache: fresh
── Order.checkout (app/orders.py:55-71) ──
app/orders.py:60    self.save()
── (top level) app/cli.py ──
app/cli.py:12       order.save(force=True)
```

- **Grouped by enclosing function:** each group is headed by its qualified name, file and range, or
  `(top level) FILE`. Under it, each line is `path:line` and the stripped source line.
- **The scope always says `text-based`.**
- **Data:** `call_sites: [{path, line, enclosing: {qual, start, end} | null, text}]`, `groups` (count) and
  `precision: "text-based"`.
- **None:** exit 0, `0 call sites of NAME`.

## dependents

```
symbols: app/models.py [4 dependents]
verdict: 4 files import app/models.py: 3 directly, 1 through them (ranked: direct first, then by names imported); cache: fresh
app/orders.py      direct     from app.models import Order, Customer   (2 names)
app/cli.py         direct     import app.models                         (1 name)
…
app/main.py        indirect   via app/orders.py
```

- **Data:** `dependents: [{path, depth, via, names}]`, `targets`.
- **A file nothing imports:** exit 0, `0 dependents`.
- **A given file outside the index:** exit 3.
