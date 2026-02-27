from __future__ import annotations

from pathlib import Path

from sqlalchemy import text


def run_migrations(engine, migrations_dir: Path) -> None:  # type: ignore[no-untyped-def]
    migrations = sorted(migrations_dir.glob("*.sql"))
    if not migrations:
        return

    with engine.begin() as conn:
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                filename TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        applied_rows = conn.execute(text("SELECT filename FROM schema_migrations")).all()
        applied = {row[0] for row in applied_rows}

        for migration in migrations:
            if migration.name in applied:
                continue

            sql = migration.read_text(encoding="utf-8")
            statements = [stmt.strip() for stmt in sql.split(";") if stmt.strip()]
            for statement in statements:
                conn.exec_driver_sql(statement)

            conn.execute(
                text("INSERT INTO schema_migrations (filename) VALUES (:filename)"),
                {"filename": migration.name},
            )
