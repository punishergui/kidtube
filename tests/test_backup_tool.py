from __future__ import annotations

import sqlite3
from pathlib import Path

from app.tools.backup_db import backup_sqlite


def test_backup_tool_creates_backup_file(tmp_path: Path) -> None:
    src = tmp_path / "kidtube.db"
    out = tmp_path / "backups" / "kidtube-copy.db"

    with sqlite3.connect(src) as conn:
        conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO test (name) VALUES ('kidtube')")
        conn.commit()

    backup_sqlite(src, out)

    assert out.exists()
    with sqlite3.connect(out) as conn:
        count = conn.execute("SELECT COUNT(*) FROM test").fetchone()[0]
    assert count == 1
