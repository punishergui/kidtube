from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def backup_sqlite(src: Path, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(src) as src_conn:
        with sqlite3.connect(out) as out_conn:
            src_conn.backup(out_conn)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a SQLite backup using online backup API")
    parser.add_argument("--src", required=True, help="Source SQLite DB path")
    parser.add_argument("--out", required=True, help="Output backup DB path")
    args = parser.parse_args()

    src = Path(args.src)
    out = Path(args.out)

    if not src.exists():
        raise SystemExit(f"Source DB does not exist: {src}")

    backup_sqlite(src, out)
    print(f"backup_created={out}")


if __name__ == "__main__":
    main()
