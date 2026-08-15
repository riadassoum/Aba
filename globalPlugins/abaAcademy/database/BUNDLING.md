# Storage bundling — why this add-on needs nothing installed

This add-on ships its own storage engine so the user does not have to install
any dependency, and so a missing binary can never stop the academy opening.

`sqlite3` looks like a standard-library module but is actually a C extension
(`_sqlite3.pyd`) that links against `sqlite3.dll`. Trimmed or embedded Python
runtimes — the kind a screen reader ships — do not always carry those two
binaries, and then `import sqlite3` fails deep inside module import.

Two design choices remove the dependency entirely:

1. **Guarded import.** `store.py` imports `sqlite3` inside a `try/except`. If it
   is present, the fast `SQLiteStore` is used. If not, we fall back to…

2. **A bundled pure-Python engine.** `purestore.py` implements the exact same
   API over plain dicts persisted as one atomic JSON document. No compiled
   code, no external file, no install step. It is selected automatically and
   the learner sees no difference.

Bundling `_sqlite3.pyd` + `sqlite3.dll` was rejected on purpose: those binaries
are compiled per CPython minor version *and* per CPU architecture, so a copy
that works on one NVDA release breaks on the next. Carrying our own engine is
the only durable, architecture-independent fix.
