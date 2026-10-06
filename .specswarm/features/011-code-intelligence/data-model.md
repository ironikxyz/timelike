# Data model — 011 Code intelligence (prompt 10, slice 1)

## Index (`<scratch>/<session>/symbols/<key>.json`)

```json
{"v": 1, "workspace": "/work/repo", "built_at": 1791200000.0,
 "files": {"app/models.py": {
   "size": 4120, "mtime_ns": 1791199999000000000, "lang": "python", "precision": "exact",
   "defs": [{"name": "Order", "qual": "Order", "kind": "class", "start": 12, "end": 48,
             "sig": "class Order(Base)", "parent": null},
            {"name": "save", "qual": "Order.save", "kind": "method", "start": 30, "end": 41,
             "sig": "def save(self, force: bool = False) -> None", "parent": "Order"}],
   "imports": [{"target": "app/db.py", "module": "app.db", "names": ["connect"], "line": 3}],
   "calls": [{"name": "connect", "line": 33}]}}}
```

| Field | Meaning |
|---|---|
| `precision` | `exact` (Python, parsed) or `text-based` |
| `kind` | `class`, `function`, `method`, `nested` (Python), `type` (Go/Rust), `function` (others) |
| `imports[].target` | the workspace file the import resolves to, or null when it does not resolve (external) |

## Answers

- **Location:** `path:line`, `kind`, `qual`, `sig`, `start`, `end`, `precision`.
- **Call site:** `path`, `line`, `enclosing` (`qual`, `start`, `end`, or `(top level)`).
- **Dependent:** `path`, `depth` (1 or 2), `via` (the import line text, or the direct importer for depth 2),
  `names` (count).
