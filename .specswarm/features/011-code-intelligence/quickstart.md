# Quickstart — `symbols` (011, slice 1)

```bash
symbols outline app/models.py      # classes and functions with line ranges; no bodies
symbols def save                   # where it is defined, best first; exit 3 if nowhere
symbols callers save               # call sites grouped by enclosing function (text-based)
symbols dependents app/models.py   # who imports it, ranked
```

- **The index** is built on the first call and checked on every call after that. Changed files are
  re-read, and the verdict says the cache was stale.
- **The index lives in the session scratch,** outside the workspace. It is rebuilt in a new session.
- **Precision:** Python is exact (its syntax tree). JS/TS, Go, Rust and shell are text-based, and the
  answer says so.
