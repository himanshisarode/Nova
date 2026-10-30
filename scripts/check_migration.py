"""Check the Level 2 migration on a COPY of a Nova database.

    python scripts/check_migration.py path/to/nova.db
    python scripts/check_migration.py before.db --after after.db

First form (before deploying): copies the file (the original is only
ever read), opens the copy with today's code (which runs db.migrate()),
then compares every table that existed before, row by row, on the
columns that existed before. Prints row counts; exits non-zero if
anything differs.

Second form (after deploying): compares a backup taken before the
deploy with a copy downloaded after it, the same way — proving the live
data survived. README "Upgrading to Level 2" has the full steps.
"""
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import db  # noqa: E402


def snapshot(conn: sqlite3.Connection) -> dict[str, tuple[list[str], list[tuple]]]:
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    out = {}
    for t in tables:
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({t})")]
        rows = conn.execute(f"SELECT {', '.join(cols)} FROM {t} ORDER BY rowid").fetchall()
        out[t] = (cols, rows)
    return out


def _read_only_snapshot(path: Path) -> dict:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        return snapshot(conn)
    finally:
        conn.close()


def main(source: str, after_file: str | None = None) -> int:
    source_path = Path(source)
    for p in (source_path, Path(after_file) if after_file else source_path):
        if not p.is_file():
            print(f"no such file: {p}")
            return 2
    added = []
    if after_file:
        before, after = _read_only_snapshot(source_path), _read_only_snapshot(Path(after_file))
        return report(before, after, added)
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / "copy.db"
        # SQLite's backup API gives a consistent copy even if the source is open.
        src = sqlite3.connect(f"file:{source_path}?mode=ro", uri=True)
        dst = sqlite3.connect(copy)
        src.backup(dst)
        src.close()
        before = snapshot(dst)
        dst.close()

        conn = db.connect(copy)
        added = db.migrate(conn)  # already applied by connect(); a second run must add nothing
        after = snapshot(conn)
        conn.close()
    return report(before, after, added)


def report(before: dict, after: dict, added: list[str]) -> int:
    ok = True
    print(f"{'table':<16}{'rows before':>12}{'rows after':>12}  status")
    for table, (cols, rows) in before.items():
        if table not in after:
            ok = False
            print(f"{table:<16}{len(rows):>12}{'-':>12}  MISSING")
            continue
        after_cols, after_rows = after[table]
        idx = [after_cols.index(c) for c in cols]
        same = [tuple(r[i] for i in idx) for r in after_rows] == rows
        ok &= same
        print(f"{table:<16}{len(rows):>12}{len(after_rows):>12}  {'unchanged' if same else 'CHANGED'}")
    new_tables = sorted(set(after) - set(before))
    new_cols = {t: [c for c in after[t][0] if c not in before[t][0]] for t in before if t in after}
    print("new tables:", ", ".join(new_tables) or "none")
    print("new columns:", ", ".join(f"{t}.{c}" for t, cs in new_cols.items() for c in cs) or "none")
    if added:
        ok = False
        print("second migrate() added", added, "- should be none")
    print("RESULT:", "OK - every existing row is unchanged" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) == 1:
        sys.exit(main(args[0]))
    if len(args) == 3 and args[1] == "--after":
        sys.exit(main(args[0], args[2]))
    print(__doc__)
    sys.exit(2)
